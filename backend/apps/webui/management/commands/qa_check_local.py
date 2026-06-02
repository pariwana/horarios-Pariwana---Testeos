from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run local QA checks for demo environment (data/permissions + WebUI smoke)."

    def handle(self, *args, **options):
        self.stdout.write("1/2 validate_demo_setup")
        call_command("validate_demo_setup")
        self.stdout.write("2/2 smoke_test_webui")
        call_command("smoke_test_webui")
        self.stdout.write(self.style.SUCCESS("Local QA checks passed."))
