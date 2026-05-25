import hashlib
import hmac
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.gateway.services import ApisixService, GitHubService
from apps.hosting.models import Module
from dealhost.settings.env import ApisixConfig, GitHubConfig


@override_settings(
    GITHUB=GitHubConfig(
        owner="Smartappli",
        repository="DEALIoT",
        token="token",
        webhook_secret="secret-test",
        allowed_repositories=("Smartappli/DEALIoT", "Smartappli/DEALData"),
    ),
)
class GitHubServiceTests(SimpleTestCase):
    def test_verify_signature_true(self):
        payload = b'{"ref":"refs/heads/main"}'
        digest = hmac.new(b"secret-test", payload, hashlib.sha256).hexdigest()
        signature = f"sha256={digest}"

        self.assertTrue(GitHubService().verify_signature(payload, signature))

    def test_verify_signature_false(self):
        payload = b"{}"
        self.assertFalse(GitHubService().verify_signature(payload, "sha256=wrong"))

    def test_expected_repository_matches_dealiot_payload(self):
        payload = {"repository": {"full_name": "Smartappli/DEALIoT"}}

        self.assertTrue(GitHubService().is_expected_repository(payload))

    def test_expected_repository_matches_dealdata_payload(self):
        payload = {"repository": {"full_name": "Smartappli/DEALData"}}

        self.assertTrue(GitHubService().is_expected_repository(payload))

    @patch("apps.gateway.services.httpx.get")
    def test_latest_commit_uses_selected_allowed_repository(self, get_mock):
        response = Mock()
        response.json.return_value = {
            "sha": "sha-test",
            "repository": {"full_name": "Smartappli/DEALData"},
            "commit": {"message": "test commit"},
        }
        get_mock.return_value = response

        result = GitHubService().latest_commit(
            branch="main",
            repository_full_name="Smartappli/DEALData",
        )

        self.assertEqual(result["sha"], "sha-test")
        self.assertIn(
            "/repos/Smartappli/DEALData/commits/main",
            get_mock.call_args.args[0],
        )
        response.raise_for_status.assert_called_once()

    @patch("apps.gateway.services.httpx.get")
    def test_latest_commit_url_encodes_branch_refs(self, get_mock):
        response = Mock()
        response.json.return_value = {
            "sha": "sha-test",
            "repository": {"full_name": "Smartappli/DEALIoT"},
            "commit": {"message": "test commit"},
        }
        get_mock.return_value = response

        GitHubService().latest_commit(
            branch="release/1.0",
            repository_full_name="Smartappli/DEALIoT",
        )

        self.assertIn(
            "/repos/Smartappli/DEALIoT/commits/release%2F1.0",
            get_mock.call_args.args[0],
        )

    def test_latest_commit_rejects_disallowed_repository(self):
        with self.assertRaises(ValueError):
            GitHubService().latest_commit(
                branch="main",
                repository_full_name="Other/Repo",
            )

    def test_allowed_events_are_loaded_from_repository_manifest(self):
        self.assertEqual(
            GitHubService().allowed_events_for_repository("Smartappli/DEALIoT"),
            ("push",),
        )

    def test_repository_integrations_summarize_manifest_links(self):
        integrations = GitHubService().repository_integrations()
        by_repository = {
            integration["repository_full_name"]: integration
            for integration in integrations
        }

        self.assertTrue(by_repository["Smartappli/DEALIoT"]["allowed"])
        self.assertIn(
            "airflow-orchestration",
            by_repository["Smartappli/DEALIoT"]["module_slugs"],
        )
        self.assertIn(
            "dealdata-core-layer",
            by_repository["Smartappli/DEALData"]["public_module_slugs"],
        )
        self.assertEqual(
            by_repository["Smartappli/DEALIoT"]["source_dependency"]["version"],
            "v1.1.1",
        )
        self.assertEqual(
            by_repository["Smartappli/DEALData"]["source_dependency"]["versioning"],
            "git-sha",
        )

    def test_module_slugs_for_dealiot_push_changed_paths(self):
        payload = {
            "repository": {"full_name": "Smartappli/DEALIoT"},
            "commits": [
                {
                    "modified": [
                        "mqtt-kafka-bridge/bridge.py",
                        "apicurio/bootstrap/raw.sensor.json",
                        "orchestration/Dockerfile",
                    ],
                    "added": ["deploy/kubernetes/base/kustomization.yaml"],
                    "removed": [],
                },
            ],
        }

        self.assertEqual(
            set(GitHubService().module_slugs_for_webhook(payload)),
            {
                "dealiot-platform",
                "schema-registry-contracts",
                "mqtt-kafka-bridge",
                "airflow-orchestration",
            },
        )

    def test_explicit_module_slug_is_preserved_for_manual_payloads(self):
        payload = {
            "repository": {"full_name": "Smartappli/DEALIoT"},
            "module_slug": "flink-runtime",
        }

        self.assertEqual(
            GitHubService().module_slugs_for_webhook(payload),
            ["flink-runtime"],
        )

    def test_module_slugs_for_dealdata_push_changed_paths(self):
        payload = {
            "repository": {"full_name": "Smartappli/DEALData"},
            "commits": [
                {
                    "modified": [
                        "core_layer/core_data/models.py",
                        "gps_layer/gps_data/models.py",
                    ],
                    "added": ["sensor_layer/sensor_data/models.py"],
                    "removed": [],
                },
            ],
        }

        self.assertEqual(
            set(GitHubService().module_slugs_for_webhook(payload)),
            {
                "dealdata-core-layer",
                "dealdata-gps-layer",
                "dealdata-sensor-layer",
            },
        )


@override_settings(
    APISIX=ApisixConfig(
        admin_url="http://apisix:9180",
        admin_key="test-key",
        upstream_host="django-app",
        upstream_port=8000,
    ),
)
class ApisixServiceTests(TestCase):
    @patch("apps.gateway.services.httpx.put")
    def test_publish_route_uses_module_routing_metadata(self, put_mock):
        response = Mock()
        response.json.return_value = {"ok": True}
        put_mock.return_value = response
        Module.objects.create(
            name="Flink",
            slug="flink-runtime",
            image="ghcr.io/smartappli/dealiot-flink-pyflink:sha-test",
            public_path="/dealiot/flink",
            upstream_host="flink-jobmanager",
            upstream_port=8081,
        )

        result = ApisixService().publish_route("flink-runtime")

        self.assertEqual(result["route_id"], "module-flink-runtime")
        payload = put_mock.call_args.kwargs["json"]
        self.assertEqual(payload["uri"], "/dealiot/flink/*")
        self.assertEqual(
            payload["upstream"]["nodes"],
            {"flink-jobmanager:8081": 1},
        )
        response.raise_for_status.assert_called_once()

    @patch("apps.gateway.services.httpx.put")
    def test_publish_route_uses_dealiot_default_route_when_module_missing(
        self,
        put_mock,
    ):
        response = Mock()
        response.json.return_value = {"ok": True}
        put_mock.return_value = response

        result = ApisixService().publish_route("schema-registry-contracts")

        self.assertEqual(result["route_id"], "module-schema-registry-contracts")
        payload = put_mock.call_args.kwargs["json"]
        self.assertEqual(payload["uri"], "/dealiot/apicurio/*")
        self.assertEqual(
            payload["upstream"]["nodes"],
            {"apicurio-registry:8080": 1},
        )

    @patch("apps.gateway.services.httpx.put")
    def test_publish_route_uses_dealdata_default_route_when_module_missing(
        self,
        put_mock,
    ):
        response = Mock()
        response.json.return_value = {"ok": True}
        put_mock.return_value = response

        result = ApisixService().publish_route("dealdata-gps-layer")

        self.assertEqual(result["route_id"], "module-dealdata-gps-layer")
        payload = put_mock.call_args.kwargs["json"]
        self.assertEqual(payload["uri"], "/dealdata/gps/*")
        self.assertEqual(
            payload["upstream"]["nodes"],
            {"dealdata-gps:7001": 1},
        )

    @patch("apps.gateway.services.httpx.put")
    def test_publish_route_dry_run_returns_payload_without_calling_apisix(
        self,
        put_mock,
    ):
        result = ApisixService().publish_route("dealdata-core-layer", dry_run=True)

        self.assertEqual(result["route_id"], "module-dealdata-core-layer")
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["payload"]["uri"], "/dealdata/core/*")
        put_mock.assert_not_called()

    @patch("apps.gateway.services.httpx.put")
    def test_publish_route_keeps_prefixed_module_route_id(self, put_mock):
        result = ApisixService().publish_route("module-core", dry_run=True)

        self.assertEqual(result["route_id"], "module-core")
        put_mock.assert_not_called()

    @patch("apps.gateway.services.httpx.put")
    def test_publish_route_skips_known_module_without_public_upstream(self, put_mock):
        Module.objects.create(
            name="Bridge",
            slug="mqtt-kafka-bridge",
            image="ghcr.io/smartappli/dealiot-mqtt-kafka-bridge:sha-test",
        )

        result = ApisixService().publish_route("mqtt-kafka-bridge")

        self.assertTrue(result["skipped"])
        put_mock.assert_not_called()

    @patch("apps.gateway.services.httpx.put")
    def test_publish_route_skips_internal_dealiot_module_when_missing(self, put_mock):
        result = ApisixService().publish_route("mqtt-kafka-bridge")

        self.assertTrue(result["skipped"])
        put_mock.assert_not_called()
