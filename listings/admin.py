from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from documents.admin import InlineListingFileAdmin

from .models import Listing, ListingImage, ListingType


@admin.action(description=_("Publish selected listings"))
def set_online(modeladmin, request, queryset):
    queryset.update(is_published=True)


@admin.action(description=_("Unpublish selected listings"))
def set_offline(modeladmin, request, queryset):
    queryset.update(is_published=False)


@admin.action(description=_("Re-run geocoding for selected listings"))
def regeocode(modeladmin, request, queryset):
    """Coordinates are cached at save time; this refreshes them.

    Geocoding is no longer performed during page render, so this is the
    supported way to refresh coordinates after a bulk address change.
    """
    for listing in queryset.select_related("address"):
        listing.regeocode()


class AdminImageWidget(admin.widgets.AdminFileWidget):
    """Image preview for StackedInline rows."""

    def render(self, name, value, attrs=None, renderer=None):
        output = []
        if value and getattr(value, "url", None):
            # format_html escapes its *arguments*. The original used an
            # f-string inside format_html, which does not escape, and the
            # filename is user-supplied.
            output.append(
                format_html(
                    '<a href="{}" target="_blank" rel="noopener">'
                    '<img src="{}" width="150" height="150" '
                    'style="object-fit:cover;" alt="{}"></a> ',
                    value.url,
                    value.url,
                    str(value.name.rsplit("/", 1)[-1]),
                )
            )
        output.append(super().render(name, value, attrs))
        return format_html("".join(output))


class ListingImageInline(admin.StackedInline):
    model = ListingImage
    extra = 1
    fields = ("image", "short_description")
    formfield_overrides = {
        models.ImageField: {"widget": AdminImageWidget},
    }


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    inlines = [ListingImageInline, InlineListingFileAdmin]
    list_display = (
        "title",
        "is_published",
        "listing_type",
        "get_address",
        "get_total_rooms",
        "get_sqft",
        "get_price",
        "free_from",
        "realtor",
        "get_nr_files",
        "get_images",
        "get_image",
    )
    list_display_links = ("title",)
    list_filter = ("is_published", "listing_for", "listing_type", "realtor")
    list_editable = ("is_published",)
    actions = [set_online, set_offline, regeocode]
    readonly_fields = (
        "created",
        "updated",
        "headshot_image",
        "latitude",
        "longitude",
        "geocoded_at",
    )
    search_fields = (
        "title",
        "description",
        "realtor__name",
        "address__street",
        "address__city",
        "address__state__name",
        "address__zipcode",
    )
    autocomplete_fields = ["realtor", "address", "listing_type"]
    list_per_page = 25
    # `save_as = True` enabled "Save as new", making duplicate listings a
    # one-click accident.
    save_as = False
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "description",
                    "listing_type",
                    "listing_for",
                    "price",
                    "is_published",
                )
            },
        ),
        (
            _("Location"),
            {"fields": ("address", "latitude", "longitude", "geocoded_at")},
        ),
        (
            _("Details"),
            {
                "fields": (
                    "bedrooms",
                    "bathrooms",
                    "garage",
                    "sqft",
                    "lot_size",
                    "ceiling_height",
                    "free_from",
                    "protected",
                    "image",
                )
            },
        ),
        (_("Ownership"), {"fields": ("realtor",)}),
        (_("Timestamps"), {"fields": ("created", "updated", "headshot_image")}),
    )


@admin.register(ListingType)
class ListingTypeAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("id", "name", "get_nr_listings")
    list_editable = ("name",)
    readonly_fields = ("created", "updated")
    # The publish/unpublish actions were attached here too, but ListingType
    # has no is_published field, so running them raised FieldError.
    actions = []


@admin.register(ListingImage)
class ListingImageAdmin(admin.ModelAdmin):
    list_display = ("get_listing_title", "short_description", "get_image", "created")
    list_editable = ("short_description",)
    search_fields = ("listing__title",)
    autocomplete_fields = ["listing"]
    readonly_fields = ("headshot_image", "created")
