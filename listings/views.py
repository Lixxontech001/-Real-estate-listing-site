from decimal import Decimal

from django import forms
from django.conf import settings
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Value
from django.shortcuts import render
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, ListView

from core.models import State

from .models import Listing, ListingType


class ListingSearchForm(forms.Form):
    """Validates every search parameter.

    Previously these came straight off ``request.GET`` into ORM lookups, so
    ``?bedrooms=abc`` raised ``ValueError: Field 'bedrooms' expected a number
    but got 'abc'`` and returned a 500 to anyone who typed a letter into the
    bedrooms box.
    """

    keywords = forms.CharField(required=False, max_length=200)
    city = forms.CharField(required=False, max_length=100)
    state = forms.ModelChoiceField(
        queryset=State.objects.all(), required=False, empty_label=None
    )
    listing_type = forms.ModelChoiceField(
        queryset=ListingType.objects.all(), required=False, empty_label=None
    )
    sqft = forms.IntegerField(required=False, min_value=0, label=_("Min. area"))
    price = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        max_digits=14,
        decimal_places=2,
        label=_("Max. price"),
    )
    bedrooms = forms.IntegerField(required=False, min_value=0)
    bathrooms = forms.IntegerField(required=False, min_value=0)

    def clean_keywords(self):
        return (self.cleaned_data.get("keywords") or "").strip()

    def clean_city(self):
        return (self.cleaned_data.get("city") or "").strip()


def published_listings(user=None):
    """Base queryset for public pages. Drafts are never publicly reachable.

    Annotates the per-user inquiry id and the customer-document count in the
    same query, so templates no longer fire one query per listing.
    """
    qs = (
        Listing.objects.filter(is_published=True)
        .select_related(
            "listing_type",
            "realtor",
            "address",
            "address__state",
            "address__state__country",
        )
        .order_by("-created")
        .annotate(
            customer_docs_count=Count(
                "listingfile_set",
                filter=Q(listingfile_set__for_customer=True),
                distinct=True,
            ),
        )
    )
    if user is not None and getattr(user, "is_authenticated", False):
        from contacts.models import Contact

        qs = qs.annotate(
            user_inquiry_id=Subquery(
                Contact.objects.filter(listing=OuterRef("pk"), user=user).values("id")[
                    :1
                ]
            )
        )
    else:
        # annotate() requires an expression, not a bare None.
        qs = qs.annotate(user_inquiry_id=Value(None, output_field=IntegerField()))
    return qs


class ListingListView(ListView):
    """Published listings, paginated.

    ``object_list`` was a *class attribute* holding a queryset, and
    ``get_context_data`` then assigned it over ``context['listings']``. That
    replaced the paginated queryset with a raw one, so ``paginate_by = 4`` did
    nothing and the template's ``listings.paginator.page_range`` resolved to
    nothing at all -- the site rendered every listing on a single page with no
    pagination controls.
    """

    model = Listing
    template_name = "listings/listings.html"
    context_object_name = "listings"
    paginate_by = 12

    def get_queryset(self):
        return published_listings(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = _("Browse our properties")
        context["states"] = State.objects.select_related("country")
        context["list_types"] = ListingType.objects.all()
        context["page_title"] = _("Browse Property Listings")
        context["page_description"] = _("Browse all properties we are offering.")
        return context


class ListingDetailView(DetailView):
    model = Listing
    template_name = "listings/listing.html"
    context_object_name = "listing"

    def get_queryset(self):
        # Previously unfiltered, so any draft listing was publicly viewable
        # by guessing its id.
        return published_listings(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        listing = self.object
        context["title"] = listing.title
        # format_html does not escape interpolated arguments, and the address
        # is user-supplied. Passing it as an argument (not an f-string) escapes
        # it.
        context["subtitle"] = format_html(
            '<i class="fas fa-map-marker"></i> {}', listing.get_address()
        )
        context["page_title"] = listing.title
        context["page_description"] = (
            listing.description[:160]
            if listing.description
            else _("Property listing details.")
        )
        context["google_maps_api_key"] = getattr(settings, "GOOGLE_MAPS_API_KEY", "")
        return context


def search(request):
    """Filter published listings by the search form."""
    form = ListingSearchForm(request.GET or None)
    queryset = published_listings(getattr(request, "user", None))

    if form.is_valid():
        data = form.cleaned_data
        keywords = data.get("keywords")
        city = data.get("city")
        if keywords:
            queryset = queryset.filter(
                Q(title__icontains=keywords) | Q(description__icontains=keywords)
            )
        if city:
            queryset = queryset.filter(address__city__icontains=city)
        if data.get("state"):
            queryset = queryset.filter(address__state=data["state"])
        if data.get("listing_type"):
            queryset = queryset.filter(listing_type=data["listing_type"])
        if data.get("bedrooms"):
            queryset = queryset.filter(bedrooms__gte=data["bedrooms"])
        if data.get("bathrooms"):
            queryset = queryset.filter(bathrooms__gte=data["bathrooms"])
        if data.get("sqft"):
            queryset = queryset.filter(sqft__gte=data["sqft"])
        if data.get("price"):
            queryset = queryset.filter(price__lte=data["price"])
    else:
        # An invalid query string falls back to "no results" rather than 500.
        queryset = queryset.none()

    context = {
        "form": form,
        "search_form": form,
        "states": State.objects.select_related("country"),
        "list_types": ListingType.objects.all(),
        "listings": queryset,
        "values": request.GET,
        "page_title": _("Search Results"),
        "page_description": _("Search our property listings."),
    }
    return render(request, "listings/search.html", context)
