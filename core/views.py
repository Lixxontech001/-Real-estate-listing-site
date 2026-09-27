from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from accounts.models import Realtor
from listings.models import Listing, ListingType

from .models import State


def bad_request(request, exception=None):
    return render(request, "core/errors/400.html", status=400)


def permission_denied(request, exception=None):
    return render(request, "core/errors/403.html", status=403)


def page_not_found(request, exception=None):
    return render(request, "core/errors/404.html", status=404)


def server_error(request):
    return render(request, "core/errors/500.html", status=500)


class IndexView(TemplateView):
    template_name = "core/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["listings"] = (
            Listing.objects.filter(is_published=True)
            .select_related("address", "listing_type")
            .order_by("-created")[:3]
        )
        context["states"] = State.objects.select_related("country")
        context["list_types"] = ListingType.objects.all()
        context["index"] = True
        context["page_title"] = _("Real estate manager. Renting, buying and selling.")
        context["page_description"] = _(
            "Real estate manager. We offer real estate objects and take care "
            "of every aspect for you."
        )
        return context


class AboutView(TemplateView):
    template_name = "core/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["realtors"] = Realtor.objects.select_related("user").order_by(
            "-hire_date", "-id"
        )
        context["title"] = _("About us")
        context["subtitle"] = _("Real Estate and Consulting")
        context["page_title"] = _("About Us")
        context["page_description"] = _(
            "Our services include renting, selling, buying, consulting "
            "and much more."
        )
        return context


class PrivacyView(TemplateView):
    template_name = "core/privacy.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = _("Privacy")
        context["subtitle"] = _("Real-Estate")
        context["page_title"] = _("Privacy")
        context["page_description"] = _("Privacy policy")
        return context


class ImpressumView(TemplateView):
    template_name = "core/impressum.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = _("Impressum")
        context["subtitle"] = _("Real-Estate")
        context["page_title"] = _("Impressum")
        context["page_description"] = _("Legal notice")
        return context


class RobotsTXTView(TemplateView):
    """robots.txt referencing the real domain and the now-existing sitemap."""

    template_name = "core/robots.txt"
    content_type = "text/plain"
