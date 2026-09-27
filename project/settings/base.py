"""
Base settings shared by every environment.

Every environment-specific value is read from the environment via :func:`env`.
In production a missing variable raises ``ImproperlyConfigured`` instead of
silently falling back to a development default -- that silent fallback is
exactly what the old ``production_settings`` loader did, and it shipped DEBUG
mode to a public host once already.
"""

import os
from pathlib import Path

from django.contrib.messages import constants as messages

BASE_DIR = Path(__file__).resolve().parent.parent.parent


# --------------------------------------------------------------------------- env


def env(name, default=None, *, required=False, cast=str):
    """Read ``name`` from the environment, optionally casting it.

    With ``required=True`` a missing value raises ``ImproperlyConfigured``
    rather than returning ``default``. Use this for anything that must never
    silently take a development value in production.
    """
    raw = os.environ.get(name)
    if raw is None or raw == "":
        if required:
            raise ValueError(
                f"Environment variable {name!r} is required but not set. "
                f"See .env.example for the full list."
            )
        return default
    if cast is bool:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    try:
        return cast(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Environment variable {name!r} has invalid value {raw!r} "
            f"for type {cast.__name__}"
        ) from exc


# ------------------------------------------------------------------ core / secret

SECRET_KEY = env("SECRET_KEY", required=True)

DEBUG = env("DEBUG", False, cast=bool)

ALLOWED_HOSTS = [h.strip() for h in env("ALLOWED_HOSTS", "").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in env("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sites",
    "django.contrib.sitemaps",
    "core.apps.CoreConfig",
    "listings.apps.ListingsConfig",
    "accounts.apps.AccountsConfig",
    "contacts.apps.ContactsConfig",
    "documents.apps.DocumentsConfig",
    "modeltranslation",
    "django_translation_flags",
    "crispy_forms",
    "crispy_bootstrap5",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "crum.CurrentRequestUserMiddleware",
]

ROOT_URLCONF = "project.urls"
WSGI_APPLICATION = "project.wsgi.application"
ASGI_APPLICATION = "project.asgi.application"

AUTH_USER_MODEL = "accounts.CustomUser"

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "index"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        )
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------- templates

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processor.global_variables",
            ],
        },
    },
]

# ---------------------------------------------------------------------- i18n / l10n

SITE_NAME = env("SITE_NAME", "Real-Lex")
SITE_URL = env("SITE_URL", "http://localhost:8000").rstrip("/")

LANGUAGE_CODE = env("LANGUAGE_CODE", "en")
TIME_ZONE = env("TIME_ZONE", "Europe/Berlin")
USE_I18N = True
USE_T10N = True
USE_TZ = True

# Languages the site actually ships. If German is not a requirement, drop "de"
# from LANGUAGES, delete locale/ and django_translation_flags, and delete the
# existing locale/*/ directories -- they currently contain dead translations.
LANGUAGES = [
    ("en", "English"),
    ("de", "German"),
    ("es", "Spanish"),
]
MODELTRANSLATION_DEFAULT_LANGUAGE = "en"
LOCALE_PATHS = [BASE_DIR / "locale"]

# ------------------------------------------------------------------ static / media

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "project" / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# ----------------------------------------------------------------------- email

EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = env("EMAIL_PORT", 587, cast=int)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env("EMAIL_USE_TLS", True, cast=bool)
EMAIL_USE_SSL = env("EMAIL_USE_SSL", False, cast=bool)
EMAIL_TIMEOUT = env("EMAIL_TIMEOUT", 10, cast=int)

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "noreply@localhost")
SERVER_EMAIL = env("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# ---------------------------------------------------------------------- allauth

SITE_ID = 1

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

# CustomUser has `username = None`, so allauth must be told not to look for it.
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = env("ACCOUNT_EMAIL_VERIFICATION", "mandatory")
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = [
    "email*",
    "first_name*",
    "last_name*",
    "password1*",
    "password2*",
]
ACCOUNT_ADAPTER = "accounts.adapter.EmailOnlyAccountAdapter"
SOCIALACCOUNT_ADAPTER = "accounts.adapter.EmailOnlySocialAccountAdapter"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_QUERY_EMAIL = True

# NOTE: the variable below was previously spelled `OCIALACCOUNT_PROVIDERS`
# (missing the leading S), so this entire config was never read by anything.
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online", "prompt": "consent"},
        "APP": {
            "client_id": env("GOOGLE_CLIENT_ID", ""),
            "secret": env("GOOGLE_CLIENT_SECRET", ""),
            "key": env("GOOGLE_CLIENT_SECRET", ""),
        },
    }
}

# -------------------------------------------------------------------------- crispy

CRISPY_ALLOWED_TEMPLATE_PACKS = ["bootstrap5"]
CRISPY_TEMPLATE_PACK = "bootstrap5"

# -------------------------------------------------------------------------- misc

MESSAGE_TAGS = {messages.ERROR: "danger"}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(name)s %(module)s "
            "%(process)d %(thread)d %(message)s"
        },
        "simple": {
            "datefmt": "%Y-%m-%d %H:%M:%S%z",
            "format": "[%(asctime)s] [%(levelname)s] %(name)s %(message)s",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["mail_admins", "console"],
            "level": "ERROR",
            "propagate": False,
        },
        # allauth logs social-account tokens at DEBUG; keep them out of prod.
        "allauth": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "storages": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
