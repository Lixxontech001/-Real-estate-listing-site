from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.health import healthz, metrics_info, readyz
from core.sitemap import robots_txt, sitemap_view

# robots.txt previously advertised a sitemap that did not exist, so crawlers
# were pointed straight at a 404. Both are served from core.sitemap now.


handler400 = "core.views.bad_request"
handler403 = "core.views.permission_denied"
handler404 = "core.views.page_not_found"
handler500 = "core.views.server_error"

# Language-prefixed URLs, with the default language (English) served from "/".
# The previous config called i18n_patterns() with no
# prefix_default_language=False, which turned the site root into a 302, moved
# the homepage to /en/, and split crawl equity across every prefix.
urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("readyz", readyz, name="readyz"),
    path("metrics", metrics_info, name="metrics"),
    path("i18n/", include("django_translation_flags.urls")),
    path("admin/", admin.site.urls),
    path("", include("django.conf.urls.i18n")),
    path("sitemap.xml", sitemap_view, name="sitemap"),
    path("robots.txt", robots_txt, name="robots-txt"),
]

urlpatterns += i18n_patterns(
    path("", include("core.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("allauth.urls")),
    path("listings/", include("listings.urls")),
    path("listings/", include("documents.urls")),
    path("contacts/", include("contacts.urls")),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
