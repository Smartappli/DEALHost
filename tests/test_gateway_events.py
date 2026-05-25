from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.gateway.views import (
    GitHubRepositoriesView,
    GitHubWebhookView,
    PublishRouteView,
    SyncGitHubView,
)


class GatewayEventPublishingTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(is_authenticated=True, is_staff=False)
        self.admin_user = SimpleNamespace(is_authenticated=True, is_staff=True)

    @patch("apps.gateway.views.publish_event")
    @patch("apps.gateway.views.ApisixService")
    def test_publish_route_emits_requested_and_completed(
        self,
        apisix_service_cls,
        publish_mock,
    ):
        apisix_service_cls.return_value.publish_route.return_value = {"route_id": "r-1"}
        request = self.factory.post(
            "/api/gateway/apisix/publish/",
            {"module_slug": "core"},
            format="json",
        )
        force_authenticate(request, user=self.admin_user)

        response = PublishRouteView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(publish_mock.call_count, 2)
        apisix_service_cls.return_value.publish_route.assert_called_once_with(
            "core",
            dry_run=False,
        )

    @patch("apps.gateway.views.GitHubService")
    def test_sync_github_accepts_repository_full_name(self, github_service_cls):
        github = MagicMock()
        github.is_allowed_repository_full_name.return_value = True
        github.latest_commit.return_value = {
            "sha": "sha-test",
            "repository": {"full_name": "Smartappli/DEALData"},
            "commit": {"message": "test commit"},
        }
        github_service_cls.return_value = github
        request = self.factory.post(
            "/api/gateway/github/sync/",
            {"branch": "main", "repository_full_name": "Smartappli/DEALData"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = SyncGitHubView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["repository"], "Smartappli/DEALData")
        github.latest_commit.assert_called_once_with(
            branch="main",
            repository_full_name="Smartappli/DEALData",
        )

    def test_github_repositories_lists_manifest_integrations(self):
        request = self.factory.get("/api/gateway/github/repositories/")
        force_authenticate(request, user=self.user)

        response = GitHubRepositoriesView.as_view()(request)

        repositories = {
            item["repository_full_name"]: item
            for item in response.data["repositories"]
        }
        self.assertEqual(response.status_code, 200)
        self.assertIn("Smartappli/DEALIoT", repositories)
        self.assertIn("Smartappli/DEALData", repositories)
        self.assertIn(
            "mqtt-kafka-bridge",
            repositories["Smartappli/DEALIoT"]["module_slugs"],
        )
        self.assertEqual(
            repositories["Smartappli/DEALIoT"]["source_dependency"]["version"],
            "v1.1.1",
        )

    @patch("apps.gateway.views.publish_event")
    @patch("apps.gateway.views.ApisixService")
    @patch("apps.gateway.views.GitHubService")
    def test_dealiot_webhook_maps_changed_paths_and_emits_events(
        self,
        github_service_cls,
        apisix_service_cls,
        publish_mock,
    ):
        github = MagicMock()
        github.verify_signature.return_value = True
        github.repository_full_name.return_value = "Smartappli/DEALIoT"
        github.expected_repository_full_name.return_value = "Smartappli/DEALIoT"
        github.allowed_repository_full_names.return_value = (
            "Smartappli/DEALIoT",
            "Smartappli/DEALData",
        )
        github.is_expected_repository.return_value = True
        github.is_allowed_event.return_value = True
        github.module_slugs_for_webhook.return_value = ["mqtt-kafka-bridge"]
        github_service_cls.return_value = github
        apisix_service_cls.return_value.publish_route.return_value = {"route_id": "r-2"}

        request = self.factory.post(
            "/api/gateway/github/webhook/",
            {
                "repository": {"full_name": "Smartappli/DEALIoT"},
                "commits": [
                    {
                        "modified": ["mqtt-kafka-bridge/bridge.py"],
                        "added": [],
                        "removed": [],
                    },
                ],
            },
            format="json",
            HTTP_X_HUB_SIGNATURE_256="sha256=ok",
            HTTP_X_GITHUB_EVENT="push",
        )

        response = GitHubWebhookView.as_view()(request)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(publish_mock.call_count, 3)
        apisix_service_cls.return_value.publish_route.assert_called_once_with(
            "mqtt-kafka-bridge",
            dry_run=False,
        )
        self.assertEqual(response.data["module_slugs"], ["mqtt-kafka-bridge"])

    @patch("apps.gateway.views.publish_event")
    @patch("apps.gateway.views.ApisixService")
    @patch("apps.gateway.views.GitHubService")
    def test_webhook_ignores_unsupported_event(
        self,
        github_service_cls,
        apisix_service_cls,
        publish_mock,
    ):
        github = MagicMock()
        github.verify_signature.return_value = True
        github.repository_full_name.return_value = "Smartappli/DEALIoT"
        github.expected_repository_full_name.return_value = "Smartappli/DEALIoT"
        github.allowed_repository_full_names.return_value = (
            "Smartappli/DEALIoT",
            "Smartappli/DEALData",
        )
        github.is_expected_repository.return_value = True
        github.is_allowed_event.return_value = False
        github.allowed_events_for_repository.return_value = ("push",)
        github_service_cls.return_value = github

        request = self.factory.post(
            "/api/gateway/github/webhook/",
            {"repository": {"full_name": "Smartappli/DEALIoT"}},
            format="json",
            HTTP_X_HUB_SIGNATURE_256="sha256=ok",
            HTTP_X_GITHUB_EVENT="pull_request",
        )

        response = GitHubWebhookView.as_view()(request)

        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.data["ignored"])
        publish_mock.assert_not_called()
        apisix_service_cls.return_value.publish_route.assert_not_called()

    @patch("apps.gateway.views.publish_event")
    @patch("apps.gateway.views.ApisixService")
    @patch("apps.gateway.views.GitHubService")
    def test_webhook_ignores_unexpected_repository(
        self,
        github_service_cls,
        apisix_service_cls,
        publish_mock,
    ):
        github = MagicMock()
        github.verify_signature.return_value = True
        github.repository_full_name.return_value = "Other/Repo"
        github.expected_repository_full_name.return_value = "Smartappli/DEALIoT"
        github.allowed_repository_full_names.return_value = (
            "Smartappli/DEALIoT",
            "Smartappli/DEALData",
        )
        github.is_expected_repository.return_value = False
        github_service_cls.return_value = github

        request = self.factory.post(
            "/api/gateway/github/webhook/",
            {"repository": {"full_name": "Other/Repo"}},
            format="json",
            HTTP_X_HUB_SIGNATURE_256="sha256=ok",
            HTTP_X_GITHUB_EVENT="push",
        )

        response = GitHubWebhookView.as_view()(request)

        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.data["ignored"])
        publish_mock.assert_not_called()
        apisix_service_cls.return_value.publish_route.assert_not_called()
