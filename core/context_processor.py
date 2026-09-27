from django.conf import settings
from django.utils.translation import gettext_lazy as _


def global_variables(request):
    """Values every template needs.

    The hardcoded ``https://real-estate.tornode.org`` here was baked into
    every canonical URL and robots.txt Sitemap line. It now comes from the
    environment, so staging and production do not advertise a dead domain.
    """
    return {
        "domain_name": getattr(settings, "SITE_NAME", "Real-Lex"),
        "domain": getattr(settings, "SITE_URL", "").rstrip("/"),
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
        "page_default_description": _(
            "Real estate manager. Renting, buying and selling."
        ),
    }
