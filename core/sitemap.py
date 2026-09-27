"""Sitemap and robots.txt served against the configured SITE_URL.

django.contrib.sitemaps resolves absolute URLs through the django.contrib.sites
row for SITE_ID, which is created as "example.com" -- so out of the box every
sitemap entry pointed at a domain that does not exist. Here the domain and
protocol are taken from ``SITE_URL`` instead, which means no database row has to
be kept in sync with the deployment.
"""

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap as django_sitemap
from django.http import HttpResponse
from django.urls import path, reverse

from listings.models import Listing


def _site_parts():
    url = (getattr(settings, "SITE_URL", "") or "").strip()
    if not url:
        return None, None
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.hostname or "", parsed.scheme or "https"


class SiteAwareSitemap(Sitemap):
    """Base sitemap that takes its domain from SITE_URL.

    Django 5's ``Sitemap.get_domain()`` ignores the ``domain`` attribute
    entirely and reads ``site.domain``, which is the ``django_site`` row for
    SITE_ID -- created as "example.com". Overriding ``get_domain`` is the
    supported hook, and means no database row has to be kept in sync with the
    deployment.
    """

    def get_domain(self, site=None):
        domain, _scheme = _site_parts()
        if not domain:
            # Fall back to Django's own behaviour (the sites framework).
            return super().get_domain(site)
        return domain

    def get_protocol(self, protocol=None):
        if self.protocol:
            return self.protocol
        _domain, scheme = _site_parts()
        if scheme:
            return scheme
        return super().get_protocol(protocol)


# ------------------------------------------------------------------- sitemaps


class ListingSitemap(SiteAwareSitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return Listing.objects.filter(is_published=True).order_by("-created")

    def lastmod(self, obj):
        return obj.updated


class StaticSitemap(SiteAwareSitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        # Plain URL names: the app urlconfs are included without a namespace.
        return ["index", "about", "listings", "privacy", "impressum"]

    def location(self, item):
        return reverse(item)


sitemaps = {"listings": ListingSitemap, "static": StaticSitemap}


# --------------------------------------------------------------------- views


def sitemap_view(request, sitemaps=None, **kwargs):
    sitemaps = sitemaps or globals()["sitemaps"]
    if not _site_parts()[0]:
        return HttpResponse(
            "SITE_URL is not configured; no sitemap generated.\n",
            content_type="text/plain",
            status=503,
        )
    return django_sitemap(request, sitemaps=sitemaps, **kwargs)


def robots_txt(request):
    """Serve robots.txt from a view.

    The template previously hardcoded a dead domain in the Sitemap line and
    disallowed /snippets/, a directory that no longer exists.
    """
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /contacts/",
        "Disallow: /listings/search",
        "",
    ]
    if getattr(settings, "SITE_URL", ""):
        lines.append(f"Sitemap: {settings.SITE_URL.rstrip('/')}/sitemap.xml")
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


urlpatterns = [
    path("sitemap.xml", sitemap_view, name="sitemap"),
    path("robots.txt", robots_txt, name="robots-txt"),
]
