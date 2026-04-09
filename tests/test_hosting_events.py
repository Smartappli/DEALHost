from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.test.client import RequestFactory

from apps.hosting.views import (
    AutoDiscoverView,
    HostedApplicationViewSet,
    ManagementAutoDiscoverView,
    ModuleViewSet,
    ToolViewSet,
)


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

        with patch(
            "rest_framework.viewsets.ModelViewSet.perform_destroy"
        ) as destroy_super:
            view.perform_destroy(instance)

        destroy_super.assert_called_once()
        publish_mock.assert_called_once()

    @patch("rest_framework.viewsets.ModelViewSet.get_queryset")
    def test_module_get_queryset_filters_enabled_query_param(self, super_queryset):
        queryset = Mock()
        queryset.filter.return_value = "filtered"
        super_queryset.return_value = queryset
        view = ModuleViewSet()
        view.request = SimpleNamespace(query_params={"enabled": "TRUE"})

        result = view.get_queryset()

        self.assertEqual(result, "filtered")
        queryset.filter.assert_called_once_with(enabled=True)

    @patch("rest_framework.viewsets.ModelViewSet.get_queryset")
    def test_tool_get_queryset_applies_all_filters(self, super_queryset):
        queryset = Mock()
        queryset.filter.return_value = queryset
        queryset.distinct.return_value = "distinct-queryset"
        super_queryset.return_value = queryset
        view = ToolViewSet()
        view.request = SimpleNamespace(
            query_params={
                "enabled": "false",
                "module_slug": "module-core",
                "current_version": "1.2.3",
            },
        )

        result = view.get_queryset()

        self.assertEqual(result, "distinct-queryset")
        queryset.filter.assert_any_call(enabled=False)
        queryset.filter.assert_any_call(modules__slug="module-core")
        queryset.filter.assert_any_call(current_version="1.2.3")
        queryset.distinct.assert_called_once()

    @patch("apps.hosting.views.ModuleAttachSerializer")
    def test_tool_attach_module_adds_module_and_returns_serialized_tool(
        self, serializer_class
    ):
        serializer_instance = Mock()
        serializer_instance.validated_data = {"module": "module-core"}
        serializer_class.return_value = serializer_instance
        tool = Mock()
        view = ToolViewSet()
        view.get_object = Mock(return_value=tool)
        view.get_serializer = Mock(return_value=SimpleNamespace(data={"slug": "tool"}))

        response = view.attach_module(SimpleNamespace(data={"module": 1}))

        serializer_class.assert_called_once_with(data={"module": 1})
        serializer_instance.is_valid.assert_called_once_with(raise_exception=True)
        tool.modules.add.assert_called_once_with("module-core")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"slug": "tool"})

    @patch("apps.hosting.views.ModuleAttachSerializer")
    def test_application_detach_module_removes_module(self, serializer_class):
        serializer_instance = Mock()
        serializer_instance.validated_data = {"module": "module-core"}
        serializer_class.return_value = serializer_instance
        application = Mock()
        view = HostedApplicationViewSet()
        view.get_object = Mock(return_value=application)
        view.get_serializer = Mock(
            return_value=SimpleNamespace(data={"slug": "storefront"})
        )

        response = view.detach_module(SimpleNamespace(data={"module": 1}))

        serializer_class.assert_called_once_with(data={"module": 1})
        serializer_instance.is_valid.assert_called_once_with(raise_exception=True)
        application.modules.remove.assert_called_once_with("module-core")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"slug": "storefront"})

    @patch("apps.hosting.views.auto_discover_tools_and_applications")
    def test_api_autodiscover_view_returns_report_dict(self, autodiscover):
        autodiscover.return_value = SimpleNamespace(to_dict=lambda: {"ok": True})
        view = AutoDiscoverView()

        response = view.post(SimpleNamespace())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"ok": True})

    @patch("apps.hosting.views.redirect")
    @patch("apps.hosting.views.messages.error")
    @patch("apps.hosting.views.messages.success")
    @patch("apps.hosting.views.auto_discover_tools_and_applications")
    def test_management_autodiscover_view_posts_messages_and_redirects(
        self,
        autodiscover,
        success_message,
        error_message,
        redirect_mock,
    ):
        report = SimpleNamespace(
            tools_created=1,
            tools_updated=2,
            applications_created=3,
            applications_updated=4,
            tool_versions_created=5,
            application_versions_created=6,
            errors=["manifest parse error"],
        )
        autodiscover.return_value = report
        redirect_mock.return_value = "redirected"
        request = RequestFactory().post("/hosting/manage/autodiscover/")

        response = ManagementAutoDiscoverView().post(request)

        self.assertEqual(response, "redirected")
        success_message.assert_called_once()
        error_message.assert_called_once_with(request, "manifest parse error")
        redirect_mock.assert_called_once_with("hosting-management")
