import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import IntegrityError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView

from listings.models import Listing

from .models import ChatMessage, Contact

logger = logging.getLogger(__name__)


@login_required
def user_contact(request):
    """Submit an inquiry about a listing.

    Three changes matter here:

    1. Authentication is now required. Previously this endpoint was open to
       anyone.
    2. ``realtor_email`` is resolved **server-side from the Listing's realtor**,
       never read from POST. The old code mailed a client-supplied address,
       which made this an unauthenticated open email relay and a
       listing-existence oracle.
    3. ``user_id`` comes from ``request.user``, never from POST.
    """
    if request.method != "POST":
        return redirect("index")

    listing = get_object_or_404(
        Listing, pk=request.POST.get("listing_id"), is_published=True
    )

    if Contact.objects.filter(listing=listing, user=request.user).exists():
        messages.error(request, _("You have already made an inquiry for this listing"))
        return redirect("listing", pk=listing.pk)

    contact = Contact(
        listing=listing,
        user=request.user,
        phone=request.POST.get("phone", "")[:100],
        message=request.POST.get("message", "")[:5000],
    )
    try:
        contact.save()
    except IntegrityError:
        # Lost a race against the unique constraint -- treat as a duplicate.
        messages.error(request, _("You have already made an inquiry for this listing"))
        return redirect("listing", pk=listing.pk)

    _notify_realtor(listing, contact)

    messages.success(
        request,
        _("Your request has been submitted, a realtor will get back " "to you soon"),
    )
    return redirect("listing", pk=listing.pk)


def _notify_realtor(listing, contact):
    """Email the realtor about a new inquiry.

    Never raises: a mail failure must not lose the inquiry or show the user a
    500. The previous version used ``fail_silently=False`` and mailed a
    hardcoded personal address as a blind CC on every lead.
    """
    recipient = listing.realtor.email
    if not recipient:
        logger.info(
            "Listing %s has no realtor email; skipping notification", listing.pk
        )
        return
    body = (
        f"A new inquiry was submitted for “{listing.title}”.\n\n"
        f"From: {contact.user.get_full_name()}\n"
        f"Email: {contact.user.email}\n"
        f"Phone: {contact.phone}\n\n"
        f"{contact.message}\n"
    )
    try:
        send_mail(
            subject=_("New property inquiry: %s") % listing.title,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
    except Exception:
        logger.exception(
            "Could not send inquiry notification for listing %s", listing.pk
        )


@login_required
def chat_message(request):
    """Post a message into an inquiry thread.

    The old version read ``user_id`` straight from ``request.POST``, so any
    logged-in user could post messages as any other user, into any thread.
    Identity and thread ownership are now both derived from the session.
    """
    if request.method != "POST":
        return redirect("index")

    contact = get_object_or_404(Contact, pk=request.POST.get("contact_id"))

    if contact.user_id != request.user.pk:
        # A realtor may reply to threads on their own listings.
        owns_listing = contact.listing.realtor.user_id == request.user.pk
        if not (owns_listing or request.user.is_staff):
            raise Http404

    message = (request.POST.get("message") or "").strip()
    if not message:
        messages.error(request, _("Message cannot be empty"))
        return redirect("chat-history", pk=contact.pk)

    ChatMessage.objects.create(contact=contact, user=request.user, message=message)
    messages.success(request, _("Message sent"))
    return redirect("chat-history", pk=contact.pk)


class MessageHistoryListView(DetailView):
    """A buyer's private message thread with the realtor.

    Previously reachable by any logged-in user with no ownership check, and by
    anonymous users at all, just by walking the integer id. It is now
    restricted to the thread's owner, the listing's realtor, and staff.
    """

    model = Contact
    template_name = "contacts/messages_history.html"
    context_object_name = "contact"

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Contact.objects.all()
        if user.is_authenticated:
            return Contact.objects.filter(Q(user=user) | Q(listing__realtor__user=user))
        return Contact.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contact = self.object
        context["messages_list"] = contact.messages.select_related("user")
        context["title"] = _("Message History")
        context["subtitle"] = contact.listing.title
        context["page_title"] = _("Message History")
        context["page_description"] = _("Your message history for this listing.")
        return context
