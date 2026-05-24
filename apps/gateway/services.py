from __future__ import annotations

import hashlib
import hmac
from dataclasses import asdict
from typing import Any

import httpx
from django.conf import settings

DEALIOT_PATH_MODULES = (
    ("mqtt-kafka-bridge/", "mqtt-kafka-bridge"),
    ("wildfi-decoder/", "wildfi-decoder"),
    ("airflow/", "airflow-orchestration"),
    ("pipelines/", "flink-runtime"),
    ("flink/", "flink-runtime"),
    ("beam/", "flink-runtime"),
    ("apicurio/", "schema-registry-contracts"),
    ("dealiot_contracts/", "schema-registry-contracts"),
    ("prometheus/", "observability"),
    ("grafana/", "observability"),
    ("deploy/", "dealiot-platform"),
    ("scripts/", "dealiot-platform"),
    (".github/workflows/build-and-push-images.yml", "dealiot-platform"),
    (".github/workflows/compose-deployment-test.yml", "dealiot-platform"),
    (".github/workflows/production-deployment-test.yml", "dealiot-platform"),
    ("docker-compose", "dealiot-platform"),
    (".env.example", "dealiot-platform"),
)


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


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

    def expected_repository_full_name(self) -> str:
        return f"{self.config.owner}/{self.config.repository}"

    def repository_full_name(self, payload: dict[str, Any]) -> str:
        repository = payload.get("repository")
        if not isinstance(repository, dict):
            return ""
        full_name = repository.get("full_name")
        return str(full_name) if full_name else ""

    def is_expected_repository(self, payload: dict[str, Any]) -> bool:
        repository = self.repository_full_name(payload)
        expected = self.expected_repository_full_name()
        return bool(repository) and repository.casefold() == expected.casefold()

    def changed_paths(self, payload: dict[str, Any]) -> list[str]:
        paths: list[str] = []
        for commit in payload.get("commits", []):
            if not isinstance(commit, dict):
                continue
            for key in ("added", "modified", "removed"):
                values = commit.get(key, [])
                if isinstance(values, list):
                    paths.extend(str(value) for value in values if value)

        head_commit = payload.get("head_commit")
        if isinstance(head_commit, dict):
            for key in ("added", "modified", "removed"):
                values = head_commit.get(key, [])
                if isinstance(values, list):
                    paths.extend(str(value) for value in values if value)

        return sorted(_deduplicate(paths))

    def module_slug_for_path(self, path: str) -> str | None:
        normalized = path.replace("\\", "/").lstrip("/")
        for prefix, slug in DEALIOT_PATH_MODULES:
            if normalized == prefix.rstrip("/") or normalized.startswith(prefix):
                return slug
        return None

    def module_slugs_for_webhook(self, payload: dict[str, Any]) -> list[str]:
        explicit_slug = payload.get("module_slug")
        if isinstance(explicit_slug, str) and explicit_slug.strip():
            return [explicit_slug.strip()]

        explicit_slugs = payload.get("module_slugs")
        if isinstance(explicit_slugs, list):
            return _deduplicate(
                [str(slug).strip() for slug in explicit_slugs if str(slug).strip()],
            )

        slugs = [
            slug
            for path in self.changed_paths(payload)
            if (slug := self.module_slug_for_path(path))
        ]
        return _deduplicate(slugs)


class ApisixService:
    def __init__(self) -> None:
        self.config = settings.APISIX

    def publish_route(self, module_slug: str) -> dict:
        route_id = f"module-{module_slug}"
        public_path = f"/{module_slug}"
        upstream_host = self.config.upstream_host
        upstream_port = self.config.upstream_port

        try:
            from apps.hosting.models import Module

            module = Module.objects.filter(slug=module_slug, enabled=True).first()
            if module is not None:
                if (
                    not module.public_path
                    or not module.upstream_host
                    or module.upstream_port is None
                ):
                    return {
                        "route_id": route_id,
                        "skipped": True,
                        "reason": "module has no public upstream",
                        "payload": None,
                        "response": None,
                    }
                public_path = module.public_path or public_path
                upstream_host = module.upstream_host or upstream_host
                upstream_port = module.upstream_port or upstream_port
        except Exception:
            pass

        public_path = "/" + public_path.strip("/")
        payload = {
            "uri": f"{public_path}/*",
            "name": route_id,
            "upstream": {
                "type": "roundrobin",
                "nodes": {
                    f"{upstream_host}:{upstream_port}": 1,
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
