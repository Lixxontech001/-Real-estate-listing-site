from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView

from contacts.models import Contact
from listings.models import Listing


class ListingDocumentView(DetailView):
    """Documents a realtor attached to one listing.

    The URLconf and the view classes used to be swapped: this route pointed at
    a plain ``TemplateView`` whose ``get_context_data`` dereferenced
    ``self.object``, so every request raised ``AttributeError``.

    Access control: only the listing's own realtor, and staff, may see
    internal documents. A buyer sees only the subset flagged
    ``for_customer``, and only once they have an inquiry with document access
    granted. The old code had neither -- the route had no auth at all.
    """

    model = Listing
    template_name = "documents/listing-documents.html"
    context_object_name = "listing"

    def get_queryset(self):
        """Realtor of the listing, or staff.

        Buyers reach the customer-facing subset through UserDocumentView
        (documents/profile/), which requires can_access_documents.
        """
        user = self.request.user
        if not user.is_authenticated:
            return Listing.objects.none()
        if user.is_staff:
            return Listing.objects.all()
        return Listing.objects.filter(
            Q(realtor__user=user)
            | Q(contacts__user=user, contacts__can_access_documents=True)
        ).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        listing = self.object
        context["docs"] = listing.listingfile_set.all()
        context["customer_docs"] = listing.listingfile_set.filter(for_customer=True)
        context["title"] = listing.title
        context["subtitle"] = listing.get_address()
        context["page_title"] = _("Documents")
        context["page_description"] = _("Documents for this property.")
        return context


# login_required must be applied to a class-based view via method_decorator;
# `@login_required` on the class itself raises
# "'function' object has no attribute 'as_view'" at URLConf import time.
@method_decorator(login_required, name="dispatch")
class UserDocumentView(DetailView):
    """Documents a buyer has been granted access to.

    ``can_access_documents`` on the Contact row is the gate. Previously the
    flag existed but was never checked, and ``Contact.objects.get(...)`` raised
    ``DoesNotExist`` (a 500) for any user without an inquiry on the listing.
    """

    model = Listing
    template_name = "documents/user-documents.html"
    context_object_name = "listing"

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Listing.objects.all()
        # Only listings this user has been granted document access to.
        return Listing.objects.filter(
            contacts__user=user, contacts__can_access_documents=True
        ).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        listing = self.object
        contact = (
            Contact.objects.filter(listing=listing, user=self.request.user)
            .only("can_access_documents", "contact_date")
            .first()
        )
        if contact is None or not contact.can_access_documents:
            raise Http404
        context["contact"] = contact
        context["docs"] = listing.listingfile_set.filter(for_customer=True)
        context["title"] = _("Documents")
        context["subtitle"] = _("Your property documents")
        context["page_title"] = _("Your documents")
        context["page_description"] = _("Documents shared with you.")
        return context
