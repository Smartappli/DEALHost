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

    def test_module_slugs_for_dealiot_push_changed_paths(self):
        payload = {
            "repository": {"full_name": "Smartappli/DEALIoT"},
            "commits": [
                {
                    "modified": [
                        "mqtt-kafka-bridge/bridge.py",
                        "apicurio/bootstrap/raw.sensor.json",
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
    def test_publish_route_skips_known_module_without_public_upstream(self, put_mock):
        Module.objects.create(
            name="Bridge",
            slug="mqtt-kafka-bridge",
            image="ghcr.io/smartappli/dealiot-mqtt-kafka-bridge:sha-test",
        )

        result = ApisixService().publish_route("mqtt-kafka-bridge")

        self.assertTrue(result["skipped"])
        put_mock.assert_not_called()
