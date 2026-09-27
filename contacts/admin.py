from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import ChatMessage, Contact


class InlineChatMessageAdmin(admin.StackedInline):
    model = ChatMessage
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        # Messages are written by users through the app, not by staff in the
        # admin, so the historical record stays append-only.
        return False

    def get_readonly_fields(self, request, obj=None):
        base = ("contact", "user", "message", "timestamp")
        return self.readonly_fields + base


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "contact", "user", "short_message", "timestamp")
    list_select_related = ("contact", "contact__listing", "user")
    search_fields = ("message", "user__email", "contact__listing__title")
    readonly_fields = ("contact", "user", "message", "timestamp")
    list_filter = ("timestamp",)
    date_hierarchy = "timestamp"

    @admin.display(description=_("Message"))
    def short_message(self, obj):
        text = obj.message or ""
        return text[:80] + ("…" if len(text) > 80 else "")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    inlines = [InlineChatMessageAdmin]
    autocomplete_fields = ("user", "listing")
    list_display = (
        "id",
        "get_full_name",
        "get_email",
        "listing",
        "phone",
        "message",
        "contact_date",
        "can_access_documents",
    )
    list_display_links = ("id", "get_full_name")
    list_editable = ("can_access_documents",)
    list_filter = ("can_access_documents", "listing")
    search_fields = (
        "user__first_name",
        "user__email",
        "listing__title",
        "phone",
        "message",
    )
    readonly_fields = ("contact_date",)
    list_per_page = 25
    date_hierarchy = "contact_date"
