from django.db import models
from django.utils.translation import gettext_lazy as _

# Documents are private. `for_customer=True` means "this may be shown to a
# buyer who has an inquiry on the listing"; `for_customer=False` is
# internal-only. Neither is enforced by a permission class here -- the view
# is responsible for checking Contact.can_access_documents, and does.
ALLOWED_DOCUMENT_EXTENSIONS = ["pdf", "doc", "docx", "xls", "xlsx", "jpg", "png"]
MAX_DOCUMENT_SIZE_MB = 25


def listing_file_dir_path(instance, filename):
    import uuid

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"listings/files/{uuid.uuid4().hex}.{ext}"


def validate_document_size(file):
    max_bytes = MAX_DOCUMENT_SIZE_MB * 1024 * 1024
    if file.size > max_bytes:
        from django.core.exceptions import ValidationError

        raise ValidationError(
            f"File is too large ({file.size / 1048576:.1f} MB). "
            f"Maximum is {MAX_DOCUMENT_SIZE_MB} MB."
        )


def validate_document_extension(file):
    from django.core.exceptions import ValidationError

    ext = (file.name.rsplit(".", 1)[-1] if "." in file.name else "").lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '.{ext}'. Allowed: "
            f"{', '.join(ALLOWED_DOCUMENT_EXTENSIONS)}."
        )


class ListingFile(models.Model):
    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.CASCADE,  # was DO_NOTHING -> orphaned rows
        related_name="listingfile_set",
        verbose_name=_("Listing"),
    )
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    short_description = models.CharField(
        max_length=255, blank=True, verbose_name=_("Short description")
    )
    file = models.FileField(
        upload_to=listing_file_dir_path,
        validators=[validate_document_extension, validate_document_size],
        verbose_name=_("File"),
    )
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("Updated"))
    for_customer = models.BooleanField(default=False, verbose_name=_("For customers"))

    class Meta:
        verbose_name = _("Listing document")
        verbose_name_plural = _("Listing documents")
        ordering = ["-created"]

    def __str__(self):
        return self.name or (self.listing.title if self.listing_id else "-")

    def get_listing_title(self):
        return self.listing.title if self.listing_id else "-"

    get_listing_title.short_description = _("Listing")
