import logging

from django.contrib import auth, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, UpdateView

from contacts.models import Contact

from .forms import ProfileUpdateForm, UserCreationForm, UserLoginForm
from .models import CustomUser

logger = logging.getLogger(__name__)
User = get_user_model()


def _safe_redirect_target(request, url, fallback="dashboard"):
    """Only honour a `next` parameter that points back at this site."""
    if url and url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return url
    return reverse_lazy(fallback) if isinstance(fallback, str) else fallback


def register(request):
    """Create an account. Uses a real form, so validators always run."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Account created. You can now sign in."))
            return redirect("login")
    else:
        form = UserCreationForm()

    return render(
        request,
        "accounts/auth/register.html",
        {
            "form": form,
            "title": _("Register"),
            "page_title": _("Register Account"),
            "page_description": _("Create an account to save listings."),
        },
    )


def login(request):
    """Email + password sign-in with a validated `next` parameter."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            auth.login(request, form.get_user())
            messages.success(request, _("You are now logged in"))
            return redirect(_safe_redirect_target(request, request.POST.get("next")))
    else:
        form = UserLoginForm(request)

    return render(
        request,
        "accounts/auth/login.html",
        {
            "form": form,
            "title": _("Login"),
            "page_title": _("Account Login"),
            "page_description": _("Sign in to your Real-Estate account."),
        },
    )


@login_required
def logout(request):
    """POST-only logout, with a validated `next` target."""
    if request.method != "POST":
        return redirect("index")
    auth.logout(request)
    messages.success(request, _("You are now logged out"))
    return redirect(
        _safe_redirect_target(request, request.POST.get("next"), fallback="index")
    )


class PasswordResetRequestView(PasswordResetView):
    """Uses django.contrib.auth's own view.

    The hand-rolled version sent mail with a hardcoded domain and protocol,
    returned HTTP 200 on its error path, and had no rate limiting.
    """

    template_name = "accounts/auth/password_reset.html"
    email_template_name = "accounts/auth/password_reset_email.txt"
    subject_template_name = "accounts/auth/password_reset_subject.txt"
    success_url = reverse_lazy("password-reset-done")
    from_email = None  # falls back to settings.DEFAULT_FROM_EMAIL

    def form_valid(self, form):
        # Always the same response, whether or not the address exists, so the
        # form cannot be used to enumerate registered users.
        messages.info(
            self.request,
            _(
                "If an account exists for that address, "
                "you will receive a reset link shortly."
            ),
        )
        return super().form_valid(form)


password_reset_request = PasswordResetRequestView.as_view()


class ProfileUpdateView(SuccessMessageMixin, UpdateView):
    """Edit *your own* profile only.

    This view was a bare ``UpdateView`` on ``CustomUser`` behind
    ``login_required`` with a client-supplied ``<int:pk>`` in the URL and no
    ownership filter. Any authenticated user could load /accounts/profile/<id>
    for someone else and overwrite their email address -- a verified
    account-takeover path. The queryset is now scoped to the request user, and
    the URL no longer accepts an id.
    """

    model = CustomUser
    form_class = ProfileUpdateForm
    template_name = "accounts/profile.html"
    success_message = _("Profile updated successfully!")
    success_url = reverse_lazy("profile")

    # Without this, an anonymous GET built a ModelForm against
    # request.user (an AnonymousUser) and raised
    # "'AnonymousUser' object has no attribute '_meta'".
    @method_decorator(login_required, name="dispatch")
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # Defence in depth: even if a pk were reintroduced into the URL, this
        # can only ever return the requesting user.
        return CustomUser.objects.filter(pk=self.request.user.pk)

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["profile"] = True
        context["title"] = _("Manage Account")
        context["subtitle"] = _("Manage your Real-Estate account")
        context["page_title"] = _("Manage Account")
        context["page_description"] = _("Update your profile details.")
        return context


@login_required
def address(request):
    """Create or update the signed-in user's address."""
    from core.forms import AddressForm

    if request.method == "POST":
        form = AddressForm(request.POST, instance=request.user.address)
        if form.is_valid():
            address_obj = form.save(commit=False)
            address_obj.save()
            request.user.address = address_obj
            request.user.save(update_fields=["address"])
            messages.success(request, _("Address saved"))
            return redirect("user-address")
    else:
        form = AddressForm(instance=request.user.address)

    return render(
        request,
        "accounts/address.html",
        {
            "form": form,
            "address": True,
            "title": _("Address"),
            "page_title": _("Your address"),
            "page_description": _("Manage your address."),
        },
    )


@login_required
def dashboard(request):
    """Was unprotected: anonymous users got a 200 with an empty page."""
    user_contacts = (
        Contact.objects.filter(user=request.user)
        .select_related("listing", "listing__realtor")
        .order_by("-contact_date")
    )
    return render(
        request,
        "accounts/dashboard.html",
        {
            "contacts": user_contacts,
            "title": _("Dashboard"),
            "page_title": _("Dashboard"),
            "page_description": _("Your inquiries and saved properties."),
        },
    )


class PasswordResetDoneView(TemplateView):
    template_name = "accounts/auth/password_reset_done.html"
