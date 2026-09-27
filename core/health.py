"""Liveness / readiness checks for container orchestration and uptime monitors."""

import logging

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


@never_cache
@csrf_exempt
def healthz(request):
    """Basic liveness. 200 as long as the process can serve a request."""
    return JsonResponse({"status": "ok"})


@never_cache
def readyz(request):
    """Readiness: checks the database and cache.

    Returns 503 when a dependency is down, so a load balancer stops sending
    traffic instead of serving errors.
    """
    checks = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:
        logger.exception("Database health check failed")
        checks["database"] = f"error: {exc.__class__.__name__}"

    try:
        cache.set("__healthcheck__", "1", 5)
        checks["cache"] = "ok" if cache.get("__healthcheck__") == "1" else "error"
    except Exception as exc:
        checks["cache"] = f"error: {exc.__class__.__name__}"

    healthy = all(v == "ok" for v in checks.values())
    payload = {
        "status": "ok" if healthy else "degraded",
        "checks": checks,
    }
    if not healthy:
        payload["environment"] = "unknown"
    return JsonResponse(payload, status=200 if healthy else 503)


@never_cache
@csrf_exempt
def metrics_info(request):
    """Non-sensitive runtime info, for debugging a deployment."""
    return JsonResponse(
        {
            "environment": "prod" if not settings.DEBUG else "dev",
            "django": (
                settings.VERSION_LABEL if hasattr(settings, "VERSION_LABEL") else "5.2"
            ),
            "database_engine": connection.settings_dict["ENGINE"],
            "static_root": str(settings.STATIC_ROOT),
        }
    )
