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
    tools_created: int = 0
    tools_updated: int = 0
    applications_created: int = 0
    applications_updated: int = 0
    tool_versions_created: int = 0
    application_versions_created: int = 0
    errors: list[str] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "tools_created": self.tools_created,
            "tools_updated": self.tools_updated,
            "applications_created": self.applications_created,
            "applications_updated": self.applications_updated,
            "tool_versions_created": self.tool_versions_created,
            "application_versions_created": self.application_versions_created,
            "errors": self.errors or [],
        }


def _read_manifest(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    for field in ("name", "slug"):
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
                "%(path)s: invalid version '%(version)s', expected semantic version"
            ) % {
                "path": path,
                "version": raw_version,
            }
            raise ValueError(msg)
        data["version"] = normalized.lstrip("v")
    return data


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

    for file_path in sorted((base / "tools").glob("*.json")):
        try:
            payload = _read_manifest(file_path)
            modules, missing = _extract_modules(payload)
            tool, created = Tool.objects.update_or_create(
                slug=str(payload["slug"]),
                defaults={
                    "name": str(payload["name"]),
                    "description": str(payload.get("description", "")),
                    "enabled": bool(payload.get("enabled", True)),
                },
            )
            tool.modules.set(modules)
            version = payload.get("version")
            if version:
                tool.current_version = str(version)
                tool.released_at = timezone.now()
                tool.save(
                    update_fields=["current_version", "released_at", "updated_at"]
                )
                _, version_created = tool.versions.update_or_create(
                    version=str(version),
                    defaults={
                        "notes": str(payload.get("version_notes", "")),
                        "source": "autodiscovery",
                    },
                )
                if version_created:
                    report.tool_versions_created += 1
            if created:
                report.tools_created += 1
            else:
                report.tools_updated += 1
            if missing:
                report.errors.append(
                    _("%(path)s: unknown module slugs: %(slugs)s")
                    % {"path": file_path, "slugs": ", ".join(missing)}
                )
        except (ValueError, json.JSONDecodeError) as exc:
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
                    "enabled": bool(payload.get("enabled", True)),
                },
            )
            application.modules.set(modules)
            version = payload.get("version")
            if version:
                application.current_version = str(version)
                application.released_at = timezone.now()
                application.save(
                    update_fields=["current_version", "released_at", "updated_at"]
                )
                _, version_created = application.versions.update_or_create(
                    version=str(version),
                    defaults={
                        "notes": str(payload.get("version_notes", "")),
                        "source": "autodiscovery",
                    },
                )
                if version_created:
                    report.application_versions_created += 1
            if created:
                report.applications_created += 1
            else:
                report.applications_updated += 1
            if missing:
                report.errors.append(
                    _("%(path)s: unknown module slugs: %(slugs)s")
                    % {"path": file_path, "slugs": ", ".join(missing)}
                )
        except (ValueError, json.JSONDecodeError) as exc:
            report.errors.append(str(exc))

    return report
