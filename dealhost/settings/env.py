from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GitHubConfig:
    owner: str
    repository: str
    token: str
    webhook_secret: str


@dataclass(frozen=True)
class ApisixConfig:
    admin_url: str
    admin_key: str
    upstream_host: str
    upstream_port: int


@dataclass(frozen=True)
class CacheConfig:
    valkey_url: str


def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def github_config() -> GitHubConfig:
    return GitHubConfig(
        owner=get_env("GITHUB_OWNER", "dealiot"),
        repository=get_env("GITHUB_REPOSITORY", "smartappli"),
        token=get_env("GITHUB_TOKEN", "replace-me"),
        webhook_secret=get_env("GITHUB_WEBHOOK_SECRET", "replace-me"),
    )


def apisix_config() -> ApisixConfig:
    return ApisixConfig(
        admin_url=get_env("APISIX_ADMIN_URL", "http://apisix:9180"),
        admin_key=get_env("APISIX_ADMIN_KEY", "replace-me"),
        upstream_host=get_env("APISIX_UPSTREAM_HOST", "django-app"),
        upstream_port=int(get_env("APISIX_UPSTREAM_PORT", "8000")),
    )


def cache_config() -> CacheConfig:
    return CacheConfig(
        valkey_url=get_env("VALKEY_URL", "redis://valkey:6379/1"),
    )
