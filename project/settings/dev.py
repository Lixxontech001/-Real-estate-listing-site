"""Development settings. Loaded when ``DJANGO_ENV=dev`` (the default)."""

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Never point the dev database at production.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Local filesystem media is fine for development; production uses S3.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Convenience for local work. Hitting Nominatim on every page view is slow and
# rude, so caching is enabled here too.
GEOCODING_CACHE_SECONDS = env("GEOCODING_CACHE_SECONDS", 86400, cast=int)
NOMINATIM_USER_AGENT = env(
    "NOMINATIM_USER_AGENT", "realestate-dev/1.0 (set NOMINATIM_USER_AGENT)"
)
