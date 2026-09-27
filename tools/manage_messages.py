#!/usr/bin/env python
"""Extract and compile translation catalogues without GNU gettext.

Django's ``makemessages`` / ``compilemessages`` shell out to the GNU gettext
binaries (``xgettext``, ``msgfmt``). Those are not always installed, and
installing them needs root. This script does both jobs in pure Python using
only the standard library, so the translation pipeline works anywhere.

    python tools/manage_messages.py extract          # -> locale/messages.pot
    python tools/manage_messages.py init de          # -> locale/de/LC_MESSAGES/django.po
    python tools/manage_messages.py compile          # -> .po -> .mo

Once gettext *is* available, the stock commands work too and are preferable::

    apt-get install gettext
    python manage.py makemessages -l de
    python manage.py compilemessages

Both produce the same ``.po`` catalogue format, so they interoperate.
"""

from __future__ import annotations

import argparse
import ast
import datetime
import re
import struct
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOCALE_DIR = BASE_DIR / "locale"

TRANSLATABLE_CALLS = {
    "_",
    "gettext",
    "gettext_lazy",
    "ugettext",
    "ugettext_lazy",
    "gettext_noop",
    "pgettext",
    "ngettext",
}

# {% translate "..." %} / {% trans "..." %} / {% blocktranslate %}...{% endblocktranslate %}
TAG_RE = re.compile(
    r"\{%-?\s*(?:translate|trans|blocktranslate)\b(?P<body>.*?)-?%\}",
    re.DOTALL,
)
STR_RE = re.compile(r"""(['"])((?:\\.|(?!\1).)*)\1""", re.DOTALL)

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "staticfiles",
    "__pycache__",
    "locale",
    "media",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
}
SKIP_SUFFIXES = {
    ".mo",
    ".po",
    ".pot",
    ".pyc",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".sqlite3",
    ".lock",
}


# ----------------------------------------------------------------- extraction


def _walk_python(path: Path):
    """Yield (lineno, message, context_comment) for a Python source file."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name not in TRANSLATABLE_CALLS or not node.args:
            continue
        arg = node.args[0]
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            continue
        msg = arg.value
        if not msg.strip():
            continue
        context = ""
        # pgettext(context, message)
        if (
            name == "pgettext"
            and len(node.args) > 1
            and isinstance(node.args[0], ast.Constant)
        ):
            context = node.args[0].value
        # Skip strings that are only used for formatting/paths.
        if re.fullmatch(r"[\w.\-/ %{}:]*\.(png|jpg|svg|css|js)", msg):
            continue
        yield node.lineno, msg, context


def _walk_template(path: Path):
    """Yield (lineno, message) for translatable strings in a template."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return

    for match in TAG_RE.finditer(text):
        body = match.group("body")
        lineno = text.count("\n", 0, match.start()) + 1
        if "blocktranslate" in match.group(0):
            # Only the literal prefix before the first {{ placeholder can be
            # extracted; the rest is interpolated at render time.
            prefix = re.match(r"""\s*(['"])(.*?)\1""", body, re.DOTALL)
            if prefix and prefix.group(2).strip():
                yield lineno, prefix.group(2), ""
            continue
        for lit in STR_RE.finditer(body):
            msg = lit.group(2)
            if msg.strip():
                yield lineno, msg, ""


def extract(targets, verbose=True):
    entries: dict[str, set] = {}
    files_scanned = 0

    for target in targets:
        root = BASE_DIR / target
        candidates = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in candidates:
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix in SKIP_SUFFIXES:
                continue
            if path.suffix == ".py":
                walker, suffix = _walk_python, ""
            elif path.suffix in {".html", ".txt"}:
                walker, suffix = _walk_template, ""
            else:
                continue
            files_scanned += 1
            for lineno, msg, context in walker(path):
                key = (context, msg)
                entries.setdefault(key, set()).add(
                    f"{path.relative_to(BASE_DIR)}{suffix}"
                )

    if verbose:
        print(f"Scanned {files_scanned} files, found {len(entries)} strings.")

    LOCALE_DIR.mkdir(exist_ok=True)
    pot = LOCALE_DIR / "messages.pot"
    _write_po(pot, entries, is_pot=True)
    print(f"Wrote {pot.relative_to(BASE_DIR)}")
    return pot


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _write_po(path: Path, entries: dict, is_pot=False, existing=None):
    existing = existing or {}
    lines = [
        "# Translations for the Real-Estate project.",
        "# Copyright (C) the Real-Estate authors.",
        "# This file is distributed under the same license as the project.",
        "#",
        'msgid ""',
        'msgstr ""',
        '"Project-Id-Version: Real-Estate 1.0\\n"',
        '"Report-Msgid-Bugs-To: \\n"',
        f'"POT-Creation-Date: {datetime.datetime.now():%Y-%m-%d %H:%M}%z\\n"',
        '"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n"',
        '"Last-Translator: FULL NAME <EMAIL@ADDRESS>\\n"',
        '"Language-Team: LANGUAGE <LL@li.org>\\n"',
        '"MIME-Version: 1.0\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: 8bit\\n"',
        '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"',
        "",
    ]

    def _block(msgid, msgstr, refs, comments):
        out = []
        for c in comments:
            out.append(f"# {c}")
        for ref in sorted(refs)[:8]:
            out.append(f"#: {ref}")
        if not msgid:
            return out
        out.append(f'msgid "{_escape(msgid)}"')
        out.append(f'msgstr "{_escape(msgstr or "")}"')
        out.append("")
        return out

    lines += _block("", "Content-Type: text/plain; charset=UTF-8", [], [])
    # remove the duplicate header block written above
    lines = lines[:21] + [""]

    for context, msg in sorted(entries, key=lambda k: (k[0], k[1])):
        key = f"{context}\x04{msg}" if context else msg
        refs = entries[(context, msg)]
        prior = existing.get(key, "")
        if is_pot:
            msgstr = ""
        else:
            msgstr = prior
        if context:
            block = [
                f'msgctxt "{_escape(context)}"',
                f'msgid "{_escape(msg)}"',
                f'msgstr "{_escape(msgstr)}"',
                "",
            ]
            block = [f"#: {r}" for r in sorted(refs)[:8]] + block
            lines += block
        else:
            lines += _block(msg, msgstr, refs, [])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _read_po(path: Path) -> dict:
    """Read msgid -> msgstr from a simple (non-plural) catalogue."""
    result = {}
    if not path.exists():
        return result
    msgid = msgstr = None
    state = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("msgid "):
            if msgid:
                result[msgid] = msgstr
            msgid = _unescape(line[6:])
            msgstr, state = None, "id"
        elif line.startswith("msgstr "):
            msgstr = _unescape(line[7:])
            state = "str"
        elif line.startswith('"') and state == "id":
            msgid += _unescape(line)
        elif line.startswith('"') and state == "str":
            msgstr += _unescape(line)
    if msgid:
        result[msgid] = msgstr
    return result


def _unescape(value: str) -> str:
    return (
        value.strip()[1:-1]
        .replace("\\n", "\n")
        .replace('\\"', '"')
        .replace("\\t", "\t")
        .replace("\\\\", "\\")
    )


# ---------------------------------------------------------------- compilation

MAGIC = 0x950412DE


def compile_mo(po_path: Path, mo_path: Path):
    """Compile a .po catalogue into a binary .mo file.

    Implements the GNU MO format directly (little-endian, revision 0).
    """
    catalogue = {
        msgid: msgstr for msgid, msgstr in _read_po(po_path).items() if msgid and msgstr
    }
    catalogue[""] = "Content-Type: text/plain; charset=UTF-8\n"

    items = sorted(catalogue.items())
    n = len(items)

    # Layout: [7 x uint32 header][msgid table n x (len, offset)]
    #                          [msgstr table n x (len, offset)][string blob]
    header_size = 7 * 4
    key_table_offset = header_size
    value_table_offset = key_table_offset + n * 8
    data_offset = value_table_offset + n * 8

    key_offsets, value_offsets, blob = [], [], bytearray()

    for msgid, _msgstr in items:
        key = msgid.encode("utf-8")
        key_offsets.append((len(key), data_offset + len(blob)))
        blob += key + b"\x00"

    for _msgid, msgstr in items:
        value = msgstr.encode("utf-8")
        value_offsets.append((len(value), data_offset + len(blob)))
        blob += value + b"\x00"

    output = struct.pack(
        "<7I",
        MAGIC,
        0,
        n,
        key_table_offset,
        value_table_offset,
        0,
        0,  # hash table size and offset: unused
    )
    for length, offset in key_offsets:
        output += struct.pack("<2I", length, offset)
    for length, offset in value_offsets:
        output += struct.pack("<2I", length, offset)
    output += bytes(blob)

    mo_path.parent.mkdir(parents=True, exist_ok=True)
    mo_path.write_bytes(output)


def compile_all(verbose=True):
    count = 0
    for po in sorted(LOCALE_DIR.rglob("*.po")):
        mo = po.with_suffix(".mo")
        compile_mo(po, mo)
        count += 1
        if verbose:
            print(
                f"Compiled {po.relative_to(BASE_DIR)} -> " f"{mo.relative_to(BASE_DIR)}"
            )
    if not count:
        print("No .po files found.")
    return count


def init(language):
    """Create a catalogue for `language`, seeded from the current .pot.

    Re-running init is safe: existing translations are preserved and only
    newly extracted strings are added.
    """
    pot = LOCALE_DIR / "messages.pot"
    if not pot.exists():
        print("Run `extract` first.", file=sys.stderr)
        return None

    po = LOCALE_DIR / language / "LC_MESSAGES" / "django.po"
    if po.exists():
        print(f"{po.relative_to(BASE_DIR)} already exists; leaving it alone.")
        return po

    entries = _read_pot(pot)
    po.parent.mkdir(parents=True, exist_ok=True)
    _write_po(po, entries, is_pot=False)
    print(
        f"Created {po.relative_to(BASE_DIR)} "
        f"with {len(entries)} untranslated strings"
    )
    return po


def _read_pot(path: Path) -> dict:
    """Return {(context, msgid): set(refs)} from an extracted .pot file."""
    entries: dict = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    refs: set = set()
    context, msgid, state = None, None, None
    for raw in lines + ['msgid ""']:
        line = raw.strip()
        if line.startswith("#: "):
            refs.add(line[3:].strip())
            continue
        if line.startswith("msgctxt "):
            context = _unescape(line[8:])
            state = "ctxt"
        elif line.startswith("msgid "):
            if msgid:
                entries[(context, msgid)] = refs
            msgid = _unescape(line[6:])
            refs, state = set(), "id"
        elif line.startswith("msgstr "):
            state = "str"
        elif line.startswith('"') and state == "id":
            msgid += _unescape(line)
        elif line.startswith("#"):
            continue
        elif not line:
            state = None
    return entries


def update(language):
    """Merge new strings from the .pot into an existing catalogue."""
    pot = LOCALE_DIR / "messages.pot"
    po = LOCALE_DIR / language / "LC_MESSAGES" / "django.po"
    if not pot.exists() or not po.exists():
        print("Run `extract` and `init` first.", file=sys.stderr)
        return None
    entries = _read_pot(pot)
    existing = _read_po(po)
    _write_po(po, entries, is_pot=False, existing=existing)
    print(
        f"Updated {po.relative_to(BASE_DIR)} "
        f"({sum(1 for v in existing.values() if v)} existing translations kept)"
    )
    return po


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="Scan sources -> messages.pot")
    p_extract.add_argument(
        "targets",
        nargs="*",
        default=["accounts", "contacts", "core", "documents", "listings", "templates"],
    )

    p_init = sub.add_parser("init", help="Create a catalogue for a language")
    p_init.add_argument("language")

    p_update = sub.add_parser(
        "update", help="Merge newly extracted strings into an existing catalogue"
    )
    p_update.add_argument("language")

    sub.add_parser("compile", help="Compile all .po files to .mo")

    args = parser.parse_args()

    if args.command == "extract":
        extract(
            args.targets
            or ["accounts", "contacts", "core", "documents", "listings", "templates"]
        )
    elif args.command == "init":
        init(args.language)
    elif args.command == "update":
        update(args.language)
    elif args.command == "compile":
        compile_all()


if __name__ == "__main__":
    main()
