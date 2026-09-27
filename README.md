# Real Estate Listing Site

A Django listings site where agents publish properties and buyers can search,
save an interest, and message the agent.

**Stack:** Django 5.2 · PostgreSQL · Bootstrap 5 · Docker · GitHub Actions

> **New to this repo?** Read [`MANUAL_SETUP.md`](MANUAL_SETUP.md) — it lists
> every credential you need to supply (SECRET_KEY, Maps key, SMTP, S3, OAuth)
> and exactly where to get each one.

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt

cp .env.example .env
# generate a key and paste it into SECRET_KEY:
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then create the reference data every listing depends on: a **Country**, a
**State**, and an **Address** (`State` is a non-null foreign key on `Address`).
`Country` and `State` have autocomplete wired in the admin, which requires a
searchable `admin.ModelAdmin` — both are configured.

## Tests

```bash
pytest
```

The suite is regression-focused: each test names the bug it prevents from
coming back (IDOR on the profile, chat impersonation, the open email relay,
unpublished listings leaking, the search endpoint 500ing on bad input, and so
on). Run it before every deploy.

## Production

```bash
DJANGO_ENV=prod python manage.py check --deploy   # must be clean
docker compose up -d --build
```

Settings are split into `project/settings/{base,dev,prod}.py`; `DJANGO_ENV`
selects between them. **In production a missing environment variable raises
rather than falling back to a development default.**

- `GET /healthz` — liveness
- `GET /readyz`  — readiness, checks the database, returns 503 if it is down
- `GET /metrics` — non-sensitive runtime info

## Translations

English, German, and Spanish. Template strings use `{% translate %}`.

```bash
# Extract strings (works without GNU gettext)
python tools/manage_messages.py extract
python tools/manage_messages.py init fr      # new language
python tools/manage_messages.py update fr    # pull in new strings
python tools/manage_messages.py compile

# Or, with gettext installed, the stock commands:
apt-get install gettext
python manage.py makemessages -l fr
python manage.py compilemessages
```

## Layout

```
accounts/     CustomUser (email login), Realtor, profile
listings/     Listing, ListingType, ListingImage + search
contacts/     Contact (inquiry), ChatMessage
documents/    ListingFile, with per-contact access control
core/         Country / State / Address, error pages, health, sitemap
project/      settings, urls, wsgi/asgi, static
tools/        gettext-free translation workflow
```

## Notes

- Media belongs in S3 in production. The container filesystem is wiped on
  every deploy.
- Listing coordinates are geocoded **once, on save**, and cached on the model.
  They are never fetched during a page render.
- An account is required to submit an inquiry. This is deliberate: it gives you
  a verified lead and removes an entire class of spam.
