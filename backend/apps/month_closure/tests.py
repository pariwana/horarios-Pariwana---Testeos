from django.test import TestCase

from apps.month_closure.models import MonthClosureStatus
from apps.month_closure.services import MonthClosureService
from apps.tenants.models import Property, Tenant
from apps.users.models import User


class MonthClosureServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="admin@pariwana.test", password="StrongPass123")
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")

    def test_close_and_reopen_month(self):
        closure = MonthClosureService.close_month(
            tenant=self.tenant,
            property_obj=self.property,
            year=2026,
            month=4,
            user=self.user,
        )
        self.assertEqual(closure.status, MonthClosureStatus.CLOSED)

        closure = MonthClosureService.reopen_month(
            tenant=self.tenant,
            property_obj=self.property,
            year=2026,
            month=4,
            user=self.user,
        )
        self.assertEqual(closure.status, MonthClosureStatus.OPEN)
