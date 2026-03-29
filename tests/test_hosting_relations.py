from django.test import TestCase

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
