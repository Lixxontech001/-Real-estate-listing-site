from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Contact(models.Model):
    """A buyer's inquiry about a listing, and the thread it spawns."""

    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.CASCADE,  # was DO_NOTHING -> orphaned rows
        related_name="contacts",
        verbose_name=_("Listing"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # was PROTECT -> users could never be deleted
        related_name="contacts",
        verbose_name=_("User"),
    )
    phone = models.CharField(max_length=100, blank=True, verbose_name=_("Phone"))
    message = models.TextField(blank=True, verbose_name=_("Message"))
    # Was `default=datetime.now`, which stores a naive local timestamp while
    # USE_TZ=True -- silently wrong by the server's UTC offset.
    contact_date = models.DateTimeField(
        default=timezone.now, verbose_name=_("Contact date")
    )
    can_access_documents = models.BooleanField(
        default=False, verbose_name=_("Docs access")
    )

    class Meta:
        ordering = ["-contact_date"]
        verbose_name = _("Contact")
        verbose_name_plural = _("Contacts")
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "user"],
                name="unique_inquiry_per_user_per_listing",
            )
        ]

    def __str__(self):
        return f"{self.listing} - {self.user}"

    def get_full_name(self):
        return self.user.get_full_name()

    get_full_name.short_description = _("Client")

    def get_email(self):
        return self.user.email

    get_email.short_description = _("Email")


class ChatMessage(models.Model):
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name=_("Contact listing"),
    )
    # Always set from request.user in the view, never from POST data.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_messages",
        verbose_name=_("User"),
    )
    message = models.TextField(verbose_name=_("Message"))
    timestamp = models.DateTimeField(default=timezone.now, verbose_name=_("Timestamp"))

    class Meta:
        ordering = ["timestamp"]
        verbose_name = _("Chat message")
        verbose_name_plural = _("Chat messages")

    def __str__(self):
        who = self.user.get_short_name() or self.user.email
        return f"{self.contact_id}: {who}"
