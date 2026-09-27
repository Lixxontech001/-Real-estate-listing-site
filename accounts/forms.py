from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class BasicFormStyle(forms.ModelForm):
    """Base that applies Bootstrap 5 classes without clobbering existing ones.

    The original implementation assigned ``field.widget.attrs['class'] =
    "form-control"`` outright, wiping out any classes crispy-forms or
    django-widget-tweaks had set.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            if "form-control" not in css:
                field.widget.attrs["class"] = f"{css} form-control".strip()


class ProfileUpdateForm(BasicFormStyle):
    class Meta:
        model = User
        # `last_login` was editable here, letting a user rewrite their own
        # login timestamp. It is now displayed read-only in the template.
        fields = ["first_name", "last_name", "email", "phone"]
        widgets = {
            "first_name": forms.TextInput(
                attrs={"placeholder": _("Firstname"), "autocomplete": "given-name"}
            ),
            "last_name": forms.TextInput(
                attrs={"placeholder": _("Lastname"), "autocomplete": "family-name"}
            ),
            "email": forms.EmailInput(
                attrs={"placeholder": _("Email"), "autocomplete": "email"}
            ),
            "phone": forms.TelInput(
                attrs={"placeholder": _("Phone"), "autocomplete": "tel"}
            ),
        }


class UserCreationForm(forms.ModelForm):
    """Registration form.

    Replaces the hand-rolled POST handling, which read ``request.POST`` keys
    directly (500 on a missing field), never ran Django's password validators
    (the password "1" was accepted), and had no email verification.
    """

    password1 = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label=_("Password confirmation"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=_("Enter the same password as before, for verification."),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("An account with this email already exists."))
        return email

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError(_("The two password fields didn't match."))
        return p2

    def _post_clean(self):
        super()._post_clean()
        from django.contrib.auth.password_validation import validate_password

        password = self.cleaned_data.get("password2")
        if password:
            try:
                validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error("password2", error)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserLoginForm(AuthenticationForm):
    """Email + password login, wired to the custom USERNAME_FIELD."""

    username = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}),
    )
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": _(
            "Please enter a correct email address and password. Note that "
            "both fields may be case-sensitive."
        ),
        "inactive": _("This account is inactive."),
    }
