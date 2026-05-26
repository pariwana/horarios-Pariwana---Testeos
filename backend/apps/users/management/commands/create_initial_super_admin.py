from django.core.management.base import BaseCommand, CommandError

from apps.users.models import User


class Command(BaseCommand):
    help = "Create the first super admin user safely."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        if User.objects.filter(email=email).exists():
            raise CommandError(f"User with email {email} already exists.")

        user = User.objects.create_superuser(
            email=email,
            password=options["password"],
            first_name=options["first_name"],
            last_name=options["last_name"],
            is_super_admin=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Super admin created: {user.email}"))
