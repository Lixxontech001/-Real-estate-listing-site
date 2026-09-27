"""Shared helpers for admin previews and address geocoding.

Geocoding notes
---------------
The original implementation constructed a fresh ``Nominatim`` geocoder and hit
OpenStreetMap's public service on every call, and the listing template called it
three times per page view. That made the most important page on the site
depend on a live third-party HTTP request, at three times Nominatim's allowed
rate, with a non-compliant User-Agent. The result was a page that 500s whenever
OpenStreetMap is slow, rate-limits, or unreachable.

``geocode_address`` below adds:

* a short request ``timeout`` so a hung socket cannot pin a worker,
* a per-process cache plus a database cache when one is configured,
* a policy-compliant ``User-Agent`` read from settings,
* a ``user_agent`` guard that refuses to send an unidentifiable request,
* a graceful ``None`` return -- callers never crash on a geocoding failure.
"""

import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

CACHE_PREFIX = "geocode:v1:"


def get_headshot_image(image):
    """Full-size clickable preview for admin inlines."""
    if image:
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">'
            '<img src="{}" style="max-height:500px;" alt="{}"></a>',
            image.url,
            image.url,
            str(image.name.rsplit("/", 1)[-1]),
        )
    return _("No image found")


def get_image_format(image):
    """Thumbnail preview for admin list columns."""
    if image:
        return format_html(
            '<img src="{}" style="max-width:100px;" alt="{}">',
            image.url,
            str(image.name.rsplit("/", 1)[-1]),
        )
    return _("No image found")


def _geocode_cache_key(address):
    digest = hashlib.sha256(address.strip().lower().encode()).hexdigest()
    return f"{CACHE_PREFIX}{digest}"


def geocode_address(address, *, force_refresh=False):
    """Resolve ``address`` to ``{'latitude': .., 'longitude': ..}`` or ``None``.

    Cached results are returned without touching the network. A geocoder
    failure is logged and returns ``None`` -- it must never propagate to the
    caller, because this runs during model saves and page renders.
    """
    if not address:
        return None

    key = _geocode_cache_key(address)
    if not force_refresh:
        cached = cache.get(key)
        if cached is not None:
            return cached

    user_agent = getattr(settings, "NOMINATIM_USER_AGENT", "") or ""
    if not user_agent or "@" not in user_agent and "http" not in user_agent:
        # Nominatim's usage policy requires a contactable identifier. Refuse to
        # send a non-compliant request rather than get the deployment blocked.
        logger.warning(
            "NOMINATIM_USER_AGENT is not contactable; skipping geocode of %r. "
            "See .env.example.",
            address,
        )
        return None

    try:
        from geopy.geocoders import Nominatim

        geolocator = Nominatim(user_agent=user_agent, timeout=10)
        location = geolocator.geocode(address)
    except Exception:
        logger.exception("Geocoding failed for %r", address)
        return None

    if location is None:
        cache.set(key, {}, getattr(settings, "GEOCODING_CACHE_SECONDS", 86400))
        return None

    result = {"latitude": location.latitude, "longitude": location.longitude}
    cache.set(key, result, getattr(settings, "GEOCODING_CACHE_SECONDS", 86400))
    return result
