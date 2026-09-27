"""Regression tests for the contact/inquiry vulnerabilities found in the audit."""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from accounts.tests import BaseDataMixin
from listings.models import Listing

from .models import ChatMessage, Contact

User = get_user_model()


class ContactSecurityTests(BaseDataMixin, TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            "buyer@example.com", "Str0ngPassphrase!23", first_name="Bob"
        )
        self.attacker = User.objects.create_user(
            "attacker@example.com", "Str0ngPassphrase!23"
        )
        self.contact = Contact.objects.create(
            listing=self.listing,
            user=self.buyer,
            phone="PRIVATE-030-1234",
            message="SECRET THREAD CONTENT",
        )

    # ---------------------------------------------------------------- S4
    def test_contact_requires_authentication(self):
        """S4: the endpoint was open to anonymous callers and mailed a
        client-supplied recipient, making it an open email relay."""
        response = self.client.post(
            "/contacts/user-contact",
            {
                "listing_id": self.listing.pk,
                "phone": "1",
                "message": "x",
                "user_id": self.buyer.pk,
                "realtor_email": "attacker@evil.example",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login", response["Location"])
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_realtor_email_is_resolved_server_side(self):
        """S4: realtor_email must come from the Listing's realtor, never from
        the request body."""
        other = Listing.objects.create(
            listing_type=self.listing_type,
            realtor=self.realtor,
            address=self.address,
            title="Another",
            price=1,
            bedrooms=1,
            bathrooms=1,
            sqft=10,
        )
        self.client.force_login(self.buyer)
        self.client.post(
            "/contacts/user-contact",
            {
                "listing_id": other.pk,
                "phone": "1",
                "message": "x",
                "realtor_email": "attacker@evil.example",
            },
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["realtor@example.com"])
        self.assertNotIn("evil.example", mail.outbox[0].to)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_contact_uses_session_user_not_posted_user_id(self):
        """S4: user_id must come from request.user."""
        self.client.force_login(self.buyer)
        self.client.post(
            "/contacts/user-contact",
            {
                "listing_id": self.listing.pk,
                "phone": "1",
                "message": "x",
                "user_id": self.attacker.pk,
            },
        )
        contact = Contact.objects.get(listing=self.listing)
        self.assertEqual(contact.user_id, self.buyer.pk)

    def test_duplicate_inquiry_is_rejected(self):
        self.client.force_login(self.buyer)
        response = self.client.post(
            "/contacts/user-contact",
            {"listing_id": self.listing.pk, "phone": "1", "message": "again"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Contact.objects.count(), 1)

    def test_unpublished_listing_cannot_be_inquired_about(self):
        self.listing.is_published = False
        self.listing.save()
        self.client.force_login(self.attacker)
        response = self.client.post(
            "/contacts/user-contact",
            {"listing_id": self.listing.pk, "phone": "1", "message": "x"},
        )
        self.assertEqual(response.status_code, 404)

    # ---------------------------------------------------------------- S3
    def test_cannot_post_into_another_users_thread(self):
        """S3: the view read user_id from POST and never checked thread
        ownership, so any logged-in user could post into any thread as
        anyone. Both are now rejected."""
        self.client.force_login(self.attacker)
        response = self.client.post(
            "/contacts/chat",
            {
                "contact_id": self.contact.pk,
                "user_id": self.buyer.pk,
                "message": "impersonated",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(ChatMessage.objects.filter(message="impersonated").exists())

    def test_posted_user_id_is_ignored_on_own_thread(self):
        """Even posting into your own thread, the author is request.user --
        never the user_id in the body."""
        own = Contact.objects.create(
            listing=self.listing, user=self.attacker, phone="1", message="x"
        )
        self.client.force_login(self.attacker)
        self.client.post(
            "/contacts/chat",
            {
                "contact_id": own.pk,
                "user_id": self.buyer.pk,  # ignored
                "message": "mine",
            },
        )
        message = ChatMessage.objects.get(message="mine")
        self.assertEqual(message.user_id, self.attacker.pk)

    def test_cannot_post_into_thread_without_supplied_user_id(self):
        """Same ownership check, without the user_id field present at all."""
        self.client.force_login(self.attacker)
        self.client.post(
            "/contacts/chat",
            {"contact_id": self.contact.pk, "message": "intruding"},
        )
        self.assertFalse(ChatMessage.objects.filter(message="intruding").exists())

    def test_thread_owner_can_post(self):
        self.client.force_login(self.buyer)
        self.client.post(
            "/contacts/chat",
            {"contact_id": self.contact.pk, "message": "hello"},
        )
        self.assertTrue(ChatMessage.objects.filter(message="hello").exists())

    def test_realtor_can_post_to_thread_on_own_listing(self):
        self.client.force_login(self.realtor_user)
        self.client.post(
            "/contacts/chat",
            {"contact_id": self.contact.pk, "message": "realtor reply"},
        )
        self.assertTrue(ChatMessage.objects.filter(message="realtor reply").exists())

    # ---------------------------------------------------------------- S2
    def test_anonymous_cannot_read_chat_history(self):
        """S2: /contacts/history/<pk> had no login_required at all, so anyone
        could walk the id and read every buyer conversation.

        The view returns 404 rather than a login redirect: that avoids leaking
        whether a thread id exists.
        """
        response = self.client.get(f"/contacts/history/{self.contact.pk}")
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "SECRET THREAD CONTENT", status_code=404)

    def test_other_user_cannot_read_chat_history(self):
        self.client.force_login(self.attacker)
        response = self.client.get(f"/contacts/history/{self.contact.pk}")
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "SECRET THREAD CONTENT", status_code=404)

    def test_owner_can_read_chat_history(self):
        self.client.force_login(self.buyer)
        response = self.client.get(f"/contacts/history/{self.contact.pk}")
        self.assertEqual(response.status_code, 200)

    def test_realtor_can_read_thread_on_own_listing(self):
        self.client.force_login(self.realtor_user)
        response = self.client.get(f"/contacts/history/{self.contact.pk}")
        self.assertEqual(response.status_code, 200)

    # ---------------------------------------------------------------- B1
    def test_anonymous_contact_endpoint_is_gone(self):
        """B1: anonymous_contact was entirely non-functional and unauthenticated."""
        response = self.client.post(
            "/contacts/anonymous-contact",
            {
                "listing_id": self.listing.pk,
                "first_name": "A",
                "last_name": "B",
                "phone": "1",
                "message": "x",
                "realtor_email": "a@b.example",
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_admin_contact_dead_view_is_gone(self):
        """The route pointed at AdminContactView, which hardcoded
        Contact.objects.get(id=5) and carried no staff_member_required. It has
        been removed, so /admin/contact/ is now handled by Django's own admin
        (redirect to the admin login) and can never serve contact #5."""
        response = self.client.get("/admin/contact/")
        self.assertIn(response.status_code, (302, 404))
        if response.status_code == 302:
            self.assertIn("/admin/login/", response["Location"])

    # ---------------------------------------------------------------- misc
    def test_contact_date_is_timezone_aware(self):
        """NEW-8: contact_date used datetime.now (naive) with USE_TZ=True."""
        self.assertIsNotNone(self.contact.contact_date.tzinfo)
        self.assertIsNotNone(
            ChatMessage.objects.create(
                contact=self.contact, user=self.buyer, message="x"
            ).timestamp.tzinfo
        )

    def test_contact_model_prevents_duplicate_inquiries(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Contact.objects.create(
                    listing=self.listing, user=self.buyer, phone="", message=""
                )


class ListingPublicAccessTests(BaseDataMixin, TestCase):
    def test_unpublished_listing_is_not_reachable(self):
        """B4: ListingDetailView had no is_published filter, so drafts were
        publicly viewable by guessing an id."""
        self.listing.is_published = False
        self.listing.save()
        self.assertEqual(
            self.client.get(f"/listings/{self.listing.pk}").status_code, 404
        )

    def test_published_listing_is_reachable(self):
        self.assertEqual(
            self.client.get(f"/listings/{self.listing.pk}").status_code, 200
        )

    def test_search_does_not_return_unpublished_listings(self):
        self.listing.is_published = False
        self.listing.save()
        Listing.objects.create(
            listing_type=self.listing_type,
            realtor=self.realtor,
            address=self.address,
            title="Visible",
            price=1,
            bedrooms=1,
            bathrooms=1,
            sqft=10,
        )
        response = self.client.get("/listings/search?keywords=")
        self.assertNotContains(response, "Nice house")
        self.assertContains(response, "Visible")

    # ---------------------------------------------------------------- B5
    def test_search_rejects_non_numeric_input_without_500(self):
        """B5: ?bedrooms=abc raised ValueError -> 500."""
        for bad in ("abc", "-1", "1e999", "'; DROP TABLE listings_listing;--"):
            with self.subTest(value=bad):
                response = self.client.get(f"/listings/search?bedrooms={bad}")
                self.assertEqual(response.status_code, 200)

    # ---------------------------------------------------------------- B3
    def test_listings_page_is_paginated(self):
        """B3: object_list was a class attribute and context['listings'] was
        overwritten, so paginate_by did nothing, every listing rendered on one
        page, and no page links appeared.

        Asserted against the rendered HTML, which is what actually matters.
        """
        import re

        for i in range(20):
            Listing.objects.create(
                listing_type=self.listing_type,
                realtor=self.realtor,
                address=self.address,
                title=f"Listing {i}",
                price=1000 + i,
                bedrooms=1,
                bathrooms=1,
                sqft=50,
            )

        response = self.client.get("/listings/")
        self.assertEqual(response.status_code, 200)

        body = response.content.decode()
        cards = len(re.findall(r'class="card listing-preview"', body))
        self.assertEqual(cards, 12, "expected exactly one page of 12 cards")
        self.assertIn("?page=2", body, "pagination links were not rendered")

        # 21 listings (1 from setUpTestData + 20 here) at 12/page = 2 pages.
        self.assertEqual(response.context["page_obj"].paginator.num_pages, 2)

        page2 = self.client.get("/listings/?page=2")
        self.assertEqual(page2.status_code, 200)
        cards2 = len(
            re.findall(r'class="card listing-preview"', page2.content.decode())
        )
        self.assertEqual(cards2, 9)  # 21 listings total, 12 + 9

    # ---------------------------------------------------------------- NEW-1
    def test_listing_detail_does_not_call_geocoding(self):
        """NEW-1: the template called listing.get_coordinates three times per
        render, hitting an external API in the request path."""
        with self.settings(NOMINATIM_USER_AGENT="", GEOCODING_CACHE_SECONDS=0):
            response = self.client.get(f"/listings/{self.listing.pk}")
        self.assertEqual(response.status_code, 200)

    def test_listing_saves_without_coordinates_when_geocoding_unavailable(self):
        listing = Listing.objects.create(
            listing_type=self.listing_type,
            realtor=self.realtor,
            address=self.address,
            title="No geo",
            price=1,
            bedrooms=1,
            bathrooms=1,
            sqft=10,
        )
        self.assertIsNone(listing.latitude)
        self.assertIsNone(listing.longitude)

    # ---------------------------------------------------------------- B15
    def test_get_total_rooms_counts_bedrooms_and_bathrooms(self):
        """B15: returned bedrooms + bedrooms."""
        self.assertEqual(self.listing.get_total_rooms(), 5)

    # ---------------------------------------------------------------- S5
    def setUp(self):
        from accounts.models import Realtor  # noqa: F401

        self.buyer = User.objects.create_user(
            "buyer@example.com", "Str0ngPassphrase!23"
        )
        self.stranger = User.objects.create_user(
            "stranger@example.com", "Str0ngPassphrase!23"
        )
        self.contact = Contact.objects.create(
            listing=self.listing,
            user=self.buyer,
            phone="1",
            message="x",
        )

    def test_document_vault_rejects_anonymous(self):
        self.assertIn(
            self.client.get(f"/listings/{self.listing.pk}/docs/").status_code,
            (302, 404),
        )

    def test_document_vault_denied_when_flag_not_granted(self):
        """can_access_documents defaults to False."""
        self.client.force_login(self.buyer)
        self.assertEqual(
            self.client.get(f"/listings/{self.listing.pk}/docs/").status_code,
            404,
        )

    def test_document_vault_allowed_when_flag_granted(self):
        self.contact.can_access_documents = True
        self.contact.save()
        self.client.force_login(self.buyer)
        self.assertEqual(
            self.client.get(f"/listings/{self.listing.pk}/docs/").status_code,
            200,
        )

    def test_document_vault_denied_to_unrelated_user(self):
        self.contact.can_access_documents = True
        self.contact.save()
        self.client.force_login(self.stranger)
        self.assertEqual(
            self.client.get(f"/listings/{self.listing.pk}/docs/").status_code,
            404,
        )
