from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Address


class BasicFormStyle(forms.ModelForm):
    """Applies Bootstrap 5 classes without overwriting existing ones."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            if "form-control" not in css:
                field.widget.attrs["class"] = f"{css} form-control".strip()


class AddressForm(BasicFormStyle):
    class Meta:
        model = Address
        # The original Meta listed 'last_login', which is not a field on
        # Address and raised FieldError the moment this form was built.
        fields = ["street", "hn", "zipcode", "city", "state"]
        widgets = {
            "street": forms.TextInput(
                attrs={"placeholder": _("Street"), "autocomplete": "address-line1"}
            ),
            "hn": forms.TextInput(
                attrs={
                    "placeholder": _("House number"),
                    "autocomplete": "address-line2",
                }
            ),
            "zipcode": forms.TextInput(
                attrs={"placeholder": _("Zipcode"), "autocomplete": "postal-code"}
            ),
            "city": forms.TextInput(
                attrs={"placeholder": _("City"), "autocomplete": "address-level2"}
            ),
        }
