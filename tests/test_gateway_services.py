import hashlib
import hmac

from django.test import SimpleTestCase, override_settings

from apps.gateway.services import GitHubService
from dealhost.settings.env import GitHubConfig


@override_settings(
    GITHUB=GitHubConfig(
        owner="dealiot",
        repository="smartappli",
        token="token",
        webhook_secret="secret-test",
    )
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
