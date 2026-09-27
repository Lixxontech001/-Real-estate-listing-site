"""
Settings package entrypoint.

``DJANGO_SETTINGS_MODULE=project.settings`` resolves here, and this module
picks the active environment module at import time based on ``DJANGO_ENV``.

This replaces the old pattern::

    try:
        from .production_settings import *
    except ImportError:
        pass

which could never succeed (relative import in a non-package) and, crucially,
swallowed its own failure -- so a production deploy silently ran with DEBUG on
and a committed secret key.
"""

import os

# Convenience for local development: if a .env file exists, load it before any
# settings module reads os.environ. In production the real environment wins --
# load_dotenv never overwrites a variable that is already set.
try:
    from dotenv import load_dotenv

    load_dotenv(
        os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ),
            ".env",
        )
    )
except ImportError:  # python-dotenv is a dev/ convenience dependency
    pass

_dj_env = os.environ.get("DJANGO_ENV", "dev").strip().lower()

if _dj_env in {"prod", "production"}:
    from .prod import *  # noqa: F401,F403
elif _dj_env in {"dev", "development", "local"}:
    from .dev import *  # noqa: F401,F403
else:
    raise ValueError(f"DJANGO_ENV must be one of 'dev' or 'prod', got {_dj_env!r}")
