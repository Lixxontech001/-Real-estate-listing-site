from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    """User manager keyed on email rather than a username."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_("The Email must be set"))
        email = self.normalize_email(email).lower()
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    first_name = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("Firstname")
    )
    last_name = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("Lastname")
    )
    username = None
    phone = models.CharField(
        max_length=20, null=True, blank=True, verbose_name=_("Phone")
    )
    address = models.ForeignKey(
        "core.Address",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,  # was DO_NOTHING -> orphaned FK rows
        related_name="users",
        verbose_name=_("Address"),
    )
    email = models.EmailField(unique=True, verbose_name=_("Email"))

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return self.email

    def get_absolute_url(self):
        # No pk argument: the profile view is scoped to the request user.
        return reverse("profile")

    def get_full_name(self):
        """AbstractBaseUser convention: a method, not a property.

        It was a @property while callers used get_full_name(), which raised
        TypeError: 'str' object is not callable when mailing an inquiry.
        """
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    def get_short_name(self):
        return self.first_name or self.email

    def get_groups(self):
        return [group.name for group in self.groups.all()]

    get_groups.short_description = _("Groups")


class Realtor(models.Model):
    user = models.OneToOneField(
        "accounts.CustomUser",
        on_delete=models.CASCADE,
        related_name="realtor",
    )
    name = models.CharField(max_length=200)
    # Optional: AboutView renders realtors without one.
    photo = models.ImageField(
        upload_to="realtors/profile/", blank=True, null=True, verbose_name=_("Photo")
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))
    phone = models.CharField(max_length=20, blank=True, verbose_name=_("Phone"))
    email = models.EmailField(blank=True, verbose_name=_("Email"))
    is_mvp = models.BooleanField(default=False)
    hire_date = models.DateField(null=True, blank=True, verbose_name=_("Hire date"))

    class Meta:
        verbose_name = _("Realtor")
        verbose_name_plural = _("Realtors")

    def __str__(self):
        return self.name
