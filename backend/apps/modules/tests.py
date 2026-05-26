from django.test import TestCase
from rest_framework.test import APIClient

from apps.modules.models import ModuleActivation
from apps.modules.services import ModuleActivationService
from apps.tenants.models import Property, Tenant, TenantSupportAccessSession
from apps.users.models import User


class ModuleActivationTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")

    def test_enable_disable_module(self):
        activation = ModuleActivationService.set_state(
            tenant=self.tenant,
            module_key="buk_export",
            is_enabled=True,
        )
        self.assertTrue(activation.is_enabled)
        self.assertEqual(
            ModuleActivation.objects.filter(tenant=self.tenant, module_key="buk_export").count(),
            1,
        )

        activation = ModuleActivationService.set_state(
            tenant=self.tenant,
            module_key="buk_export",
            is_enabled=False,
        )
        self.assertFalse(activation.is_enabled)


class ModuleActivationApiSupportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.other_tenant = Tenant.objects.create(name="Otro Tenant", slug="otro-tenant-mod")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.super_admin = User.objects.create_user(
            email="super-modules@pariwana.test",
            password="StrongPass123",
            is_super_admin=True,
            is_staff=True,
        )
        self.support_session = TenantSupportAccessSession.objects.create(
            tenant=self.tenant,
            property=self.property,
            started_by=self.super_admin,
            reason="support module toggle",
        )

    def test_toggle_module_works_with_support_session_without_tenant_id(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(
            "/api/modules/toggle/",
            {"module_key": "control", "is_enabled": True},
            format="json",
            HTTP_X_SUPPORT_SESSION_ID=str(self.support_session.id),
        )
        self.assertEqual(response.status_code, 200)
        activation = ModuleActivation.objects.get(tenant=self.tenant, module_key="control")
        self.assertTrue(activation.is_enabled)

    def test_module_list_with_support_session_is_scoped_to_support_tenant(self):
        ModuleActivation.objects.create(tenant=self.tenant, module_key="buk_export", is_enabled=True)
        ModuleActivation.objects.create(tenant=self.other_tenant, module_key="buk_export", is_enabled=True)
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(
            "/api/modules/",
            HTTP_X_SUPPORT_SESSION_ID=str(self.support_session.id),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["tenant"], self.tenant.id)

    def test_toggle_with_conflicting_tenant_id_and_support_session_is_denied(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(
            "/api/modules/toggle/",
            {
                "tenant_id": self.other_tenant.id,
                "module_key": "control",
                "is_enabled": True,
            },
            format="json",
            HTTP_X_SUPPORT_SESSION_ID=str(self.support_session.id),
        )
        self.assertEqual(response.status_code, 403)
