"""Backfill listing coordinates.

Coordinates are now resolved once, when a listing is first saved, and cached on
the model. Existing rows need populating. This command is safe to re-run and
respects Nominatim's usage policy by sleeping between requests.

    python manage.py backfill_geocoding
    python manage.py backfill_geocoding --force
    python manage.py backfill_geocoding --limit 50
"""

import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from listings.models import Listing


class Command(BaseCommand):
    help = "Resolve and store coordinates for listings that are missing them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-geocode listings that already have coordinates.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Process at most N listings (0 = no limit).",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.1,
            help="Seconds to sleep between requests. Nominatim's usage policy "
            "allows at most 1 request per second.",
        )

    def handle(self, *args, **options):
        qs = Listing.objects.select_related(
            "address", "address__state", "address__state__country"
        )
        if options["force"]:
            self.stdout.write("Re-geocoding every listing.")
        else:
            qs = qs.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True))

        listings = list(qs)
        if options["limit"]:
            listings = listings[: options["limit"]]

        if not listings:
            self.stdout.write(self.style.SUCCESS("Nothing to do."))
            return

        done = failed = 0
        for i, listing in enumerate(listings, start=1):
            listing.regeocode()
            if listing.latitude is not None:
                done += 1
                self.stdout.write(
                    f"[{i}/{len(listings)}] {listing.pk} -> "
                    f"{listing.latitude:.5f}, {listing.longitude:.5f}"
                )
            else:
                failed += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"[{i}/{len(listings)}] {listing.pk} -> no result"
                    )
                )
            time.sleep(options["delay"])

        self.stdout.write(
            self.style.SUCCESS(f"Done. resolved={done} unresolved={failed}")
        )
