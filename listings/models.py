import uuid
from datetime import date

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

LISTING_CHOICE = (
    ("R", _("Rent")),
    ("S", _("Sell")),
)


def listing_dir_path(instance, filename):
    """Build a collision-free upload path.

    The original implementation keyed the filename on ``instance.pk``, which
    meant ``Listing.image`` and ``ListingImage.image`` wrote to the same
    ``listings/<pk>.<ext>`` path and overwrote each other. Including the model
    name and a UUID component removes the collision entirely.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"listings/{instance._meta.model_name}/{uuid.uuid4().hex}.{ext}"


class ListingType(models.Model):
    """Apartment, maisonette, loft, house, ..."""

    name = models.CharField(max_length=100, unique=True, verbose_name=_("Name"))
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Listing type")
        verbose_name_plural = _("Listing types")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_nr_listings(self):
        return self.listings.count()


class Listing(models.Model):
    listing_type = models.ForeignKey(
        ListingType,
        on_delete=models.PROTECT,
        related_name="listings",
        verbose_name=_("Listing type"),
    )
    realtor = models.ForeignKey(
        "accounts.Realtor",
        on_delete=models.PROTECT,  # was DO_NOTHING -> orphaned FK rows
        related_name="listings",
        verbose_name=_("Realtor"),
    )
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    address = models.ForeignKey(
        "core.Address",
        on_delete=models.PROTECT,
        related_name="listings",
        verbose_name=_("Address"),
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))
    price = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name=_("Price")
    )
    ceiling_height = models.FloatField(
        blank=True, null=True, verbose_name=_("Ceiling height")
    )
    bedrooms = models.PositiveIntegerField(verbose_name=_("Bedrooms"))
    bathrooms = models.PositiveIntegerField(verbose_name=_("Bathrooms"))
    garage = models.PositiveIntegerField(default=0, verbose_name=_("Garage"))
    sqft = models.PositiveIntegerField(verbose_name=_("Area (m²)"))
    lot_size = models.FloatField(blank=True, null=True, verbose_name=_("Lot size"))
    image = models.ImageField(
        upload_to=listing_dir_path, blank=True, verbose_name=_("Image")
    )
    listing_for = models.CharField(
        max_length=1, choices=LISTING_CHOICE, default="S", verbose_name=_("Listing for")
    )
    protected = models.BooleanField(default=False, verbose_name=_("Monument protected"))
    is_published = models.BooleanField(default=True, verbose_name=_("Online"))
    free_from = models.DateField(
        default=date.today, blank=True, verbose_name=_("Free from")
    )
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True)

    # Coordinates are resolved once, on save, and cached here. The template
    # previously called the geocoding API three times per page view, which made
    # the listing page depend on a live third-party HTTP call and 500 whenever
    # that call was slow, rate-limited, or offline.
    latitude = models.FloatField(blank=True, null=True, db_index=True)
    longitude = models.FloatField(blank=True, null=True, db_index=True)
    geocoded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = _("Listing")
        verbose_name_plural = _("Listings")
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["-created"]),
            models.Index(fields=["is_published", "-created"]),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        """Required by django.contrib.sitemaps, and correct generally."""
        from django.urls import reverse

        return reverse("listing", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        # Geocode on first save, or whenever coordinates are missing. Address
        # changes are handled by the explicit `regeocode` admin action so a
        # network call never silently blocks an ordinary edit.
        if self._state.adding or (self.latitude is None or self.longitude is None):
            self._geocode()
        super().save(*args, **kwargs)

    def regeocode(self):
        """Force a fresh coordinate lookup (admin action / management command)."""
        self._geocode()
        self.save(update_fields=["latitude", "longitude", "geocoded_at"])

    def _geocode(self):
        from core.libs.core_libs import geocode_address

        if not self.address_id:
            return
        current = (
            f"{self.address.street} {self.address.hn}, "
            f"{self.address.zipcode} {self.address.city}"
        )
        result = geocode_address(current)
        if result:
            self.latitude = result.get("latitude")
            self.longitude = result.get("longitude")
            self.geocoded_at = timezone.now()
        # A geocoding failure must never prevent the listing from saving.

    def free_date(self):
        if self.free_from and self.free_from <= date.today():
            return _("Immediately")
        return self.free_from

    def get_total_rooms(self):
        # Was `bedrooms + bedrooms`.
        return (self.bedrooms or 0) + (self.bathrooms or 0)

    get_total_rooms.short_description = _("# Rooms")

    def get_address(self):
        if not self.address_id:
            return ""
        return (
            f"{self.address.street} {self.address.hn}, "
            f"{self.address.city}, {self.address.state.country.shortcut}"
        )

    get_address.short_description = _("Address")

    def get_price(self):
        return f"{self.price:,.2f} €"

    get_price.short_description = _("Price")

    def get_sqft(self):
        return _("{sqft} m²").format(sqft=self.sqft)

    get_sqft.short_description = _("Area")

    def get_ceiling_height(self):
        if not self.ceiling_height:
            return "-"
        return f"{self.ceiling_height} m"

    get_ceiling_height.short_description = _("Ceiling height")

    def get_image(self):
        from core.libs.core_libs import get_image_format

        return get_image_format(self.image)

    get_image.short_description = _("Image")

    def headshot_image(self):
        from core.libs.core_libs import get_headshot_image

        return get_headshot_image(self.image)

    headshot_image.short_description = _("Preview")

    def get_images(self):
        count = self.listingimage_set.count()
        return count + 1 if self.image else count

    get_images.short_description = _("# Images")

    def get_nr_files(self):
        return self.listingfile_set.count()

    get_nr_files.short_description = _("# Files")

    def get_customer_docs(self):
        return self.listingfile_set.filter(for_customer=True)


class ListingImage(models.Model):
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="listingimage_set",
        verbose_name=_("Listing"),
    )
    image = models.ImageField(
        upload_to=listing_dir_path, null=True, blank=True, verbose_name=_("Image")
    )
    short_description = models.CharField(
        max_length=255, blank=True, verbose_name=_("Short description")
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Listing image")
        verbose_name_plural = _("Listing images")
        ordering = ["created"]

    def __str__(self):
        return self.listing.title if self.listing_id else "-"

    def get_image(self):
        from core.libs.core_libs import get_image_format

        return get_image_format(self.image)

    get_image.short_description = _("Image")

    def headshot_image(self):
        from core.libs.core_libs import get_headshot_image

        return get_headshot_image(self.image)

    headshot_image.short_description = _("Preview")

    def get_listing_title(self):
        return self.listing.title if self.listing_id else "-"

    get_listing_title.short_description = _("Listing")
