from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.hosting.views import HostedApplicationViewSet, ModuleViewSet, ToolViewSet


class HostingEventPublishingTests(SimpleTestCase):
    @patch("apps.hosting.views.publish_event")
    def test_module_perform_create_emits_event(self, publish_mock):
        serializer = Mock()
        serializer.save.return_value = SimpleNamespace(id=1, slug="core", enabled=True)

        ModuleViewSet().perform_create(serializer)

        publish_mock.assert_called_once()

    @patch("apps.hosting.views.publish_event")
    def test_tool_perform_update_emits_event(self, publish_mock):
        serializer = Mock()
        serializer.save.return_value = SimpleNamespace(
            id=2,
            slug="catalog",
            enabled=False,
        )

        ToolViewSet().perform_update(serializer)

        publish_mock.assert_called_once()

    @patch("apps.hosting.views.publish_event")
    def test_application_perform_destroy_emits_event(self, publish_mock):
        instance = Mock(id=3, slug="frontend")
        view = HostedApplicationViewSet()

        with patch("rest_framework.viewsets.ModelViewSet.perform_destroy") as destroy_super:
            view.perform_destroy(instance)

        destroy_super.assert_called_once()
        publish_mock.assert_called_once()
