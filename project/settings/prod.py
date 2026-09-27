"""Production settings. Loaded when ``DJANGO_ENV=prod``.

Nothing here has a development fallback: every value is read from the
environment, and a missing one raises rather than silently defaulting.
"""

import dj_database_url

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

# Security headers. These are unconditional in production -- the old setup
# depended on a settings file that silently failed to import, so none of them
# were ever active.
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

CONN_MAX_AGE = 60
CONN_HEALTH_CHECKS = True

DATABASES = {
    "default": dj_database_url.parse(
        env("DATABASE_URL", required=True),
        conn_max_age=CONN_MAX_AGE,
        conn_health_checks=True,
    )
}

# User uploads must not live on the app container's filesystem -- it is wiped on
# every deploy. Production requires object storage; see .env.example.
if env("AWS_STORAGE_BUCKET_NAME", ""):
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", required=True)
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", required=True)
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", "eu-central-1")
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", "") or None
    AWS_QUERYSTRING_AUTH = False
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    # Property photos and exposés are private until an authorised buyer asks.
    AWS_DEFAULT_ACL = "private"

# Google Maps key, served to the listing template via the context processor.
GOOGLE_MAPS_API_KEY = env("GOOGLE_MAPS_API_KEY", "")

GEOCODING_CACHE_SECONDS = env("GEOCODING_CACHE_SECONDS", 604800, cast=int)
NOMINATIM_USER_AGENT = env("NOMINATIM_USER_AGENT", required=True)
