"""allauth adapters for an email-only custom user model.

``CustomUser`` sets ``username = None`` and uses email as ``USERNAME_FIELD``.
allauth's default adapters still probe for a username field in several places,
which raises ``FieldDoesNotExist: CustomUser has no field named 'username'``
and 500s /accounts/signup/ and /accounts/google/login/.

These adapters tell allauth the username concept does not exist for this user
model instead of looking it up.
"""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class EmailOnlyAccountAdapter(DefaultAccountAdapter):
    """Treat a missing username as "not applicable" rather than an error."""

    def new_user(self, request):
        user = super().new_user(request)
        return user

    def save_user(self, request, user, form, commit=True):
        # CustomUser.email is the unique identifier; never let allauth try to
        # populate or look up `username` on this model.
        user.email = user.email.lower()
        if not commit:
            return user
        user.save()
        return user

    def clean_username(self, username, shallow=False):
        # The signup form asks for an email, never a username.
        return username

    def get_username_max_length(self):
        # No username field exists on this model.
        return None


class EmailOnlySocialAccountAdapter(DefaultSocialAccountAdapter):
    """Social logins map onto the same email-only user model."""

    def get_username_max_length(self):
        return None

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        if not user.email:
            user.email = sociallogin.account.extra_data.get("email", "")
        return user
