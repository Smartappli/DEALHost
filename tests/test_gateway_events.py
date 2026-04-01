from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.gateway.views import GitHubWebhookView, PublishRouteView


class GatewayEventPublishingTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("apps.gateway.views.publish_event")
    @patch("apps.gateway.views.ApisixService")
    def test_publish_route_emits_requested_and_completed(self, apisix_service_cls, publish_mock):
        apisix_service_cls.return_value.publish_route.return_value = {"route_id": "r-1"}
        request = self.factory.post(
            "/api/gateway/apisix/publish/",
            {"module_slug": "core"},
            format="json",
        )

        response = PublishRouteView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(publish_mock.call_count, 2)

    @patch("apps.gateway.views.publish_event")
    @patch("apps.gateway.views.ApisixService")
    @patch("apps.gateway.views.GitHubService")
    def test_webhook_emits_received_requested_completed(
        self,
        github_service_cls,
        apisix_service_cls,
        publish_mock,
    ):
        github = MagicMock()
        github.verify_signature.return_value = True
        github_service_cls.return_value = github
        apisix_service_cls.return_value.publish_route.return_value = {"route_id": "r-2"}

        request = self.factory.post(
            "/api/gateway/github/webhook/",
            {"module_slug": "core"},
            format="json",
            HTTP_X_HUB_SIGNATURE_256="sha256=ok",
            HTTP_X_GITHUB_EVENT="push",
        )

        response = GitHubWebhookView.as_view()(request)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(publish_mock.call_count, 3)
