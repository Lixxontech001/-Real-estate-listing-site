from django.conf import settings
from django.contrib import admin
from django.db import models
from django.utils.html import format_html

from .models import ListingFile

pdf_img_path = settings.STATIC_URL + "img/pdf-preview.png"


class AdminFileWidgetPreview(admin.widgets.AdminFileWidget):
    """PDF/document icon preview for inline rows.

    Note: ``alt={file_name}"`` in the original was malformed markup, and the
    filename was interpolated with an f-string inside ``format_html``, which
    does not escape. Both are fixed by passing arguments instead.
    """

    def render(self, name, value, attrs=None, renderer=None):
        output = []
        if value and getattr(value, "url", None):
            output.append(
                format_html(
                    '<a href="{}" target="_blank" rel="noopener">'
                    '<img src="{}" width="50" height="50" '
                    'style="object-fit:cover;" alt="{}"></a> ',
                    value.url,
                    pdf_img_path,
                    str(value.name.rsplit("/", 1)[-1]),
                )
            )
        output.append(super().render(name, value, attrs))
        return format_html("".join(output))


class InlineListingFileAdmin(admin.StackedInline):
    model = ListingFile
    extra = 0
    fields = ("name", "short_description", "file", "for_customer")
    formfield_overrides = {models.FileField: {"widget": AdminFileWidgetPreview}}


@admin.register(ListingFile)
class ListingFileAdmin(admin.ModelAdmin):
    list_display = ("listing", "name", "short_description", "for_customer", "created")
    list_filter = ("for_customer",)
    search_fields = ("listing__title", "name")
    autocomplete_fields = ["listing"]
    readonly_fields = ("created", "updated")
