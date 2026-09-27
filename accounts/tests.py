"""Shared test helpers."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Realtor
from core.models import Address, Country, State
from listings.models import Listing, ListingType

User = get_user_model()


class BaseDataMixin:
    """Builds a minimal, connected object graph for the tests."""

    @classmethod
    def setUpTestData(cls):
        cls.country = Country.objects.create(name="Germany", shortcut="DE")
        cls.state = State.objects.create(
            country=cls.country, name="Berlin", shortcut="BE"
        )
        cls.address = Address.objects.create(
            street="Main",
            hn="1",
            zipcode="10115",
            city="Berlin",
            state=cls.state,
        )
        cls.realtor_user = User.objects.create_user(
            "realtor@example.com", "Str0ngPassphrase!23", first_name="Rita"
        )
        cls.realtor = Realtor.objects.create(
            name="Rita",
            user=cls.realtor_user,
            email="realtor@example.com",
            phone="0301111",
        )
        cls.listing_type = ListingType.objects.create(name="House")
        cls.listing = Listing.objects.create(
            listing_type=cls.listing_type,
            realtor=cls.realtor,
            address=cls.address,
            title="Nice house",
            description="A nice house in the city.",
            price=250000,
            bedrooms=3,
            bathrooms=2,
            sqft=140,
        )


class AccountsSecurityTests(BaseDataMixin, TestCase):
    """Regression tests for the vulnerabilities found in the audit."""

    def setUp(self):
        self.victim = User.objects.create_user(
            "victim@example.com", "Str0ngPassphrase!23", first_name="Victim"
        )
        self.attacker = User.objects.create_user(
            "attacker@example.com", "Str0ngPassphrase!23"
        )

    # ---------------------------------------------------------------- S1
    def test_user_cannot_edit_another_users_profile(self):
        """S1: /accounts/profile used to accept an attacker-chosen <int:pk>
        and a bare UpdateView, letting any logged-in user overwrite someone
        else's email -- a verified account-takeover path."""
        self.client.force_login(self.attacker)
        response = self.client.get("/accounts/profile")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "victim@example.com")

    def test_profile_url_accepts_no_pk(self):
        """The pk argument must not exist in the URLconf any more."""
        self.client.force_login(self.victim)
        response = self.client.get(f"/accounts/profile/{self.victim.pk}")
        self.assertEqual(response.status_code, 404)

    def test_profile_post_only_affects_own_account(self):
        self.client.force_login(self.attacker)
        self.client.post(
            "/accounts/profile",
            {
                "first_name": "HACKED",
                "last_name": "X",
                "email": "attacker@evil.example",
                "phone": "0",
            },
        )
        self.victim.refresh_from_db()
        self.assertEqual(self.victim.first_name, "Victim")
        self.assertEqual(self.victim.email, "victim@example.com")

        self.attacker.refresh_from_db()
        self.assertEqual(self.attacker.first_name, "HACKED")

    # ---------------------------------------------------------------- B9
    def test_registration_enforces_password_validators(self):
        """B9: the old hand-rolled register view never ran
        AUTH_PASSWORD_VALIDATORS -- the password "1" was accepted."""
        for weak in ("1", "password", "12345678"):
            with self.subTest(password=weak):
                response = self.client.post(
                    "/accounts/register",
                    {
                        "first_name": "A",
                        "last_name": "B",
                        "email": f"{weak}@example.com",
                        "password1": weak,
                        "password2": weak,
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertFalse(
                    User.objects.filter(email=f"{weak}@example.com").exists()
                )

    def test_registration_missing_required_field_is_a_form_error(self):
        """B9: the old view read request.POST keys directly, so omitting
        email raised MultiValueDictKeyError -- a 500. It must now be a
        validation error, and no account may be created."""
        response = self.client.post(
            "/accounts/register",
            {
                "first_name": "A",
                "last_name": "B",
                "password1": "Str0ngPassphrase!23",
                "password2": "Str0ngPassphrase!23",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].errors.get("email"), ["This field is required."]
        )
        self.assertFalse(User.objects.filter(email="").exists())

    def test_registration_mismatched_passwords_is_a_form_error(self):
        response = self.client.post(
            "/accounts/register",
            {
                "first_name": "A",
                "last_name": "B",
                "email": "z@example.com",
                "password1": "Str0ngPassphrase!23",
                "password2": "SomethingElse!456",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="z@example.com").exists())

    def test_registration_creates_user_with_strong_password(self):
        response = self.client.post(
            "/accounts/register",
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "ada@example.com",
                "password1": "Str0ngPassphrase!23",
                "password2": "Str0ngPassphrase!23",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="ada@example.com").exists())

    # ------------------------------------------------------------ B10/B11
    def test_dashboard_requires_login(self):
        """B10: dashboard had no @login_required and returned 200 to
        anonymous users."""
        response = self.client.get("/accounts/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login", response["Location"])

    def test_logout_get_does_not_500(self):
        """B11: the view returned None on GET -> ValueError (500)."""
        self.client.force_login(self.attacker)
        response = self.client.get("/accounts/logout")
        self.assertIn(response.status_code, (302, 405))

    def test_logout_next_param_is_validated(self):
        self.client.force_login(self.attacker)
        response = self.client.post(
            "/accounts/logout", {"next": "https://evil.example/steal"}
        )
        self.assertNotIn("evil.example", response["Location"])
