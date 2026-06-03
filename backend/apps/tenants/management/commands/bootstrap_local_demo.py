from django.core.management import BaseCommand, call_command
from django.core.management.base import CommandError


class Command(BaseCommand):
    help = "Bootstrap complete local demo data for Pariwana Scheduler in one command."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True, help="Password for demo users.")
        parser.add_argument("--days", type=int, default=15, help="Days of schedule assignments to seed (default: 15).")
        parser.add_argument(
            "--supervisor-areas",
            default="Recepción,Housekeeping",
            help="Comma-separated area names for supervisor scope.",
        )

    def handle(self, *args, **options):
        password = str(options["password"]).strip()
        days_opt = options.get("days")
        days = 15 if days_opt is None else int(days_opt)
        supervisor_areas = str(options["supervisor_areas"]).strip()
        if not password:
            raise CommandError("Password cannot be empty.")
        if days < 1:
            raise CommandError("Days must be >= 1.")

        self.stdout.write("1/3 Seed base tenant/properties/modules...")
        call_command("seed_initial_pariwana")
        self.stdout.write("2/3 Seed demo operational data (Cusco)...")
        call_command("seed_demo_cusco_data", days=days)
        self.stdout.write("3/3 Seed demo users by role...")
        call_command(
            "seed_demo_users",
            password=password,
            supervisor_areas=supervisor_areas,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Local demo bootstrap completed. "
                "Tenant=Pariwana Hostels, Properties=Lima/Cusco, demo users created/updated.",
            )
        )
