from __future__ import annotations

import hashlib
import hmac
from dataclasses import asdict

import httpx
from django.conf import settings


class GitHubService:
    def __init__(self) -> None:
        self.config = settings.GITHUB

    def headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.config.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def latest_commit(self, branch: str = "main") -> dict:
        url = (
            f"https://api.github.com/repos/{self.config.owner}/"
            f"{self.config.repository}/commits/{branch}"
        )
        response = httpx.get(url, headers=self.headers(), timeout=15)
        response.raise_for_status()
        return response.json()

    def verify_signature(self, payload: bytes, signature: str | None) -> bool:
        if not signature:
            return False

        digest = hmac.new(
            self.config.webhook_secret.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()
        expected = f"sha256={digest}"
        return hmac.compare_digest(expected, signature)


class ApisixService:
    def __init__(self) -> None:
        self.config = settings.APISIX

    def publish_route(self, module_slug: str) -> dict:
        route_id = f"module-{module_slug}"
        payload = {
            "uri": f"/{module_slug}/*",
            "name": route_id,
            "upstream": {
                "type": "roundrobin",
                "nodes": {
                    f"{self.config.upstream_host}:{self.config.upstream_port}": 1,
                },
            },
        }
        url = f"{self.config.admin_url}/apisix/admin/routes/{route_id}"
        headers = {"X-API-KEY": self.config.admin_key}
        response = httpx.put(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        return {"route_id": route_id, "payload": payload, "response": response.json()}

    def describe(self) -> dict:
        return asdict(self.config)
