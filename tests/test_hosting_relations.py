from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.hosting.models import HostedApplication, Module, Tool


class HostingRelationsTests(TestCase):
    def test_tool_and_application_can_share_multiple_modules(self) -> None:
        module_auth = Module.objects.create(
            name="Auth",
            slug="auth",
            image="registry.example/auth:latest",
            branch="main",
            enabled=True,
        )
        module_billing = Module.objects.create(
            name="Billing",
            slug="billing",
            image="registry.example/billing:latest",
            branch="main",
            enabled=True,
        )

        tool = Tool.objects.create(name="Backoffice", slug="backoffice")
        app = HostedApplication.objects.create(name="Storefront", slug="storefront")

        tool.modules.set([module_auth, module_billing])
        app.modules.set([module_auth, module_billing])

        self.assertEqual(tool.modules.count(), 2)
        self.assertEqual(app.modules.count(), 2)


class HostingManagementApiTests(APITestCase):
    def setUp(self) -> None:
        self.module_auth = Module.objects.create(
            name="Auth",
            slug="auth",
            image="registry.example/auth:latest",
            branch="main",
            enabled=True,
        )
        self.module_billing = Module.objects.create(
            name="Billing",
            slug="billing",
            image="registry.example/billing:latest",
            branch="main",
            enabled=True,
        )
        self.tool = Tool.objects.create(name="Backoffice", slug="backoffice")
        self.application = HostedApplication.objects.create(name="Storefront", slug="storefront")

    def test_tool_attach_and_detach_module(self) -> None:
        attach_url = reverse("tools-attach-module", kwargs={"pk": self.tool.pk})
        detach_url = reverse("tools-detach-module", kwargs={"pk": self.tool.pk})

        attach_response = self.client.post(attach_url, {"module_id": self.module_auth.pk}, format="json")
        self.assertEqual(attach_response.status_code, 200)
        self.assertEqual(len(attach_response.data["modules"]), 1)

        detach_response = self.client.post(detach_url, {"module_id": self.module_auth.pk}, format="json")
        self.assertEqual(detach_response.status_code, 200)
        self.assertEqual(len(detach_response.data["modules"]), 0)

    def test_application_filter_by_module_slug(self) -> None:
        self.application.modules.add(self.module_billing)
        url = reverse("applications-list")
        response = self.client.get(url, {"module_slug": "billing"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["slug"], "storefront")
