from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import HostedApplication, Module, Tool

SEMVER_PATTERN = r"^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$"


@dataclass(slots=True)
class DiscoveryReport:
    modules_created: int = 0
    modules_updated: int = 0
    tools_created: int = 0
    tools_updated: int = 0
    applications_created: int = 0
    applications_updated: int = 0
    tool_versions_created: int = 0
    application_versions_created: int = 0
    rolled_back: bool = False
    errors: list[str] | None = None

    def to_dict(self, *, include_errors: bool = True) -> dict[str, object]:
        errors = self.errors or []
        public_errors = errors
        if not include_errors and errors:
            public_errors = [
                _("Autodiscovery failed; details are available in server logs."),
            ]
        return {
            "modules_created": self.modules_created,
            "modules_updated": self.modules_updated,
            "tools_created": self.tools_created,
            "tools_updated": self.tools_updated,
            "applications_created": self.applications_created,
            "applications_updated": self.applications_updated,
            "tool_versions_created": self.tool_versions_created,
            "application_versions_created": self.application_versions_created,
            "rolled_back": self.rolled_back,
            "errors": public_errors,
        }


def _read_manifest(
    path: Path,
    required_fields: tuple[str, ...] = ("name", "slug"),
) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    for field in required_fields:
        if not data.get(field):
            msg = _("%(path)s: missing required field '%(field)s'") % {
                "path": path,
                "field": field,
            }
            raise ValueError(msg)
    raw_version = data.get("version")
    if raw_version:
        normalized = str(raw_version).strip()
        if not re.fullmatch(SEMVER_PATTERN, normalized):
            msg = _(
                "%(path)s: invalid version '%(version)s', expected semantic version",
            ) % {
                "path": path,
                "version": raw_version,
            }
            raise ValueError(msg)
        data["version"] = normalized.lstrip("v")
    return data


def _as_bool(value: object, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(str(value))


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _extract_modules(payload: dict[str, object]) -> tuple[list[Module], list[str]]:
    modules: list[Module] = []
    missing: list[str] = []
    for slug in payload.get("module_slugs", []):
        if not isinstance(slug, str):
            continue
        module = Module.objects.filter(slug=slug).first()
        if module is None:
            missing.append(slug)
            continue
        modules.append(module)
    return modules, missing


@transaction.atomic
def auto_discover_tools_and_applications(
    manifests_dir: Path | None = None,
) -> DiscoveryReport:
    base = manifests_dir or Path("manifests")
    report = DiscoveryReport(errors=[])

    for file_path in sorted((base / "modules").glob("*.json")):
        try:
            payload = _read_manifest(file_path, ("name", "slug", "image"))
            created = Module.objects.update_or_create(
                slug=str(payload["slug"]),
                defaults={
                    "name": str(payload["name"]),
                    "image": str(payload["image"]),
                    "branch": str(payload.get("branch", "main")),
                    "repository_owner": str(payload.get("repository_owner", "")),
                    "repository_name": str(payload.get("repository_name", "")),
                    "source_path": str(payload.get("source_path", "")),
                    "deployment_target": str(
                        payload.get(
                            "deployment_target",
                            Module.DeploymentTarget.COMPOSE.value,
                        ),
                    ),
                    "public_path": str(payload.get("public_path", "")),
                    "upstream_host": str(payload.get("upstream_host", "")),
                    "upstream_port": _as_int_or_none(payload.get("upstream_port")),
                    "healthcheck_path": str(payload.get("healthcheck_path", "")),
                    "contract_topics": _as_string_list(
                        payload.get("contract_topics", []),
                    ),
                    "enabled": _as_bool(payload.get("enabled"), True),
                },
            )[1]
            if created:
                report.modules_created += 1
            else:
                report.modules_updated += 1
        except (TypeError, ValueError) as exc:
            report.errors.append(str(exc))

    for file_path in sorted((base / "tools").glob("*.json")):
        try:
            payload = _read_manifest(file_path)
            modules, missing = _extract_modules(payload)
            tool, created = Tool.objects.update_or_create(
                slug=str(payload["slug"]),
                defaults={
                    "name": str(payload["name"]),
                    "description": str(payload.get("description", "")),
                    "enabled": _as_bool(payload.get("enabled"), True),
                },
            )
            tool.modules.set(modules)
            version = payload.get("version")
            if version:
                tool.current_version = str(version)
                tool.released_at = timezone.now()
                tool.save(
                    update_fields=["current_version", "released_at", "updated_at"],
                )
                version_created = tool.versions.update_or_create(
                    version=str(version),
                    defaults={
                        "notes": str(payload.get("version_notes", "")),
                        "source": "autodiscovery",
                    },
                )[1]
                if version_created:
                    report.tool_versions_created += 1
            if created:
                report.tools_created += 1
            else:
                report.tools_updated += 1
            if missing:
                report.errors.append(
                    _("%(path)s: unknown module slugs: %(slugs)s")
                    % {"path": file_path, "slugs": ", ".join(missing)},
                )
        except ValueError as exc:
            report.errors.append(str(exc))

    for file_path in sorted((base / "applications").glob("*.json")):
        try:
            payload = _read_manifest(file_path)
            modules, missing = _extract_modules(payload)
            application, created = HostedApplication.objects.update_or_create(
                slug=str(payload["slug"]),
                defaults={
                    "name": str(payload["name"]),
                    "description": str(payload.get("description", "")),
                    "enabled": _as_bool(payload.get("enabled"), True),
                },
            )
            application.modules.set(modules)
            version = payload.get("version")
            if version:
                application.current_version = str(version)
                application.released_at = timezone.now()
                application.save(
                    update_fields=["current_version", "released_at", "updated_at"],
                )
                version_created = application.versions.update_or_create(
                    version=str(version),
                    defaults={
                        "notes": str(payload.get("version_notes", "")),
                        "source": "autodiscovery",
                    },
                )[1]
                if version_created:
                    report.application_versions_created += 1
            if created:
                report.applications_created += 1
            else:
                report.applications_updated += 1
            if missing:
                report.errors.append(
                    _("%(path)s: unknown module slugs: %(slugs)s")
                    % {"path": file_path, "slugs": ", ".join(missing)},
                )
        except ValueError as exc:
            report.errors.append(str(exc))

    if report.errors:
        report.rolled_back = True
        report.modules_created = 0
        report.modules_updated = 0
        report.tools_created = 0
        report.tools_updated = 0
        report.applications_created = 0
        report.applications_updated = 0
        report.tool_versions_created = 0
        report.application_versions_created = 0
        transaction.set_rollback(True)
    return report
