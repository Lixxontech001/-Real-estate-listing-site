from django import template
from django.db.models import Count, Q

register = template.Library()


@register.filter(name="has_inquired")
def has_inquired(listing):
    """True when the current user already inquired about this listing.

    Replaces ``listing_exists``, which called ``crum.get_current_user()`` and
    issued a fresh ``Contact.objects.get()`` per listing per render (an N+1 on
    every listings page) and buried every failure -- including the TypeError
    from an AnonymousUser -- in a bare ``except Exception``.
    """
    from crum import get_current_user

    user = get_current_user()
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    contact_id = getattr(listing, "user_inquiry_id", None)
    return bool(contact_id)


@register.simple_tag(takes_context=True)
def user_inquiries(context):
    """Map of listing id -> contact id, for the current user.

    One query per page instead of one per listing.
    """
    request = context.get("request")
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}

    from contacts.models import Contact

    rows = Contact.objects.filter(user=user).values_list("listing_id", "id")
    return {listing_id: contact_id for listing_id, contact_id in rows}


@register.simple_tag
def customer_docs_count(listing):
    """Number of customer-visible documents on a listing."""
    return getattr(listing, "customer_docs_count", 0)
