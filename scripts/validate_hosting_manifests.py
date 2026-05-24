from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS_DIR = ROOT / "manifests"
APISIX_ROUTES_FILE = ROOT / "infra" / "apisix" / "routes.json"
RENOVATE_FILE = ROOT / "renovate.json"


def _load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return {}

    if not isinstance(payload, dict):
        errors.append(f"{path}: JSON root must be an object")
        return {}
    return payload


def _json_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.json"))


def _required_string(
    payload: dict[str, Any],
    path: Path,
    field: str,
    errors: list[str],
) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: missing or invalid string field '{field}'")
        return ""
    return value.strip()


def _required_int(
    payload: dict[str, Any],
    path: Path,
    field: str,
    errors: list[str],
) -> int | None:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{path}: missing or invalid integer field '{field}'")
        return None
    return value


def _validate_module_public_route(
    payload: dict[str, Any],
    path: Path,
    errors: list[str],
) -> bool:
    fields = ("public_path", "upstream_host", "upstream_port")
    present = [field for field in fields if payload.get(field) not in (None, "")]
    if not present:
        return False
    if len(present) != len(fields):
        errors.append(
            f"{path}: public modules must define public_path, "
            "upstream_host and upstream_port together",
        )
        return False

    _required_string(payload, path, "public_path", errors)
    _required_string(payload, path, "upstream_host", errors)
    _required_int(payload, path, "upstream_port", errors)
    return True


def _module_repository_full_name(payload: dict[str, Any]) -> str:
    owner = payload.get("repository_owner")
    name = payload.get("repository_name")
    if isinstance(owner, str) and isinstance(name, str) and owner and name:
        return f"{owner}/{name}"
    return ""


def _validate_modules(
    errors: list[str],
) -> tuple[set[str], dict[str, dict[str, Any]], dict[str, str]]:
    module_slugs: set[str] = set()
    public_modules: dict[str, dict[str, Any]] = {}
    module_repositories: dict[str, str] = {}

    for path in _json_files(MANIFESTS_DIR / "modules"):
        payload = _load_json(path, errors)
        name = _required_string(payload, path, "name", errors)
        slug = _required_string(payload, path, "slug", errors)
        _required_string(payload, path, "image", errors)
        if not name or not slug:
            continue
        if slug in module_slugs:
            errors.append(f"{path}: duplicate module slug '{slug}'")
            continue

        module_slugs.add(slug)
        repository = _module_repository_full_name(payload)
        if repository:
            module_repositories[slug] = repository
        if _validate_module_public_route(payload, path, errors):
            public_modules[slug] = payload

    if not module_slugs:
        errors.append("manifests/modules: no module manifest found")
    return module_slugs, public_modules, module_repositories


def _validate_module_refs(
    payload: dict[str, Any],
    path: Path,
    module_slugs: set[str],
    errors: list[str],
) -> None:
    refs = payload.get("module_slugs", [])
    if refs is None:
        return
    if not isinstance(refs, list):
        errors.append(f"{path}: module_slugs must be a list")
        return

    for ref in refs:
        if not isinstance(ref, str) or not ref:
            errors.append(f"{path}: module_slugs entries must be non-empty strings")
        elif ref not in module_slugs:
            errors.append(f"{path}: unknown module slug reference '{ref}'")


def _validate_tools_and_applications(
    module_slugs: set[str],
    errors: list[str],
) -> None:
    for category in ("tools", "applications"):
        for path in _json_files(MANIFESTS_DIR / category):
            payload = _load_json(path, errors)
            _required_string(payload, path, "name", errors)
            _required_string(payload, path, "slug", errors)
            _validate_module_refs(payload, path, module_slugs, errors)


def _validate_repository_manifests(
    module_slugs: set[str],
    public_modules: dict[str, dict[str, Any]],
    module_repositories: dict[str, str],
    errors: list[str],
) -> list[dict[str, Any]]:
    repository_manifests: list[dict[str, Any]] = []
    repositories_seen: set[str] = set()

    for path in _json_files(MANIFESTS_DIR / "repositories"):
        payload = _load_json(path, errors)
        repository = _required_string(payload, path, "repository_full_name", errors)
        if repository and repository in repositories_seen:
            errors.append(f"{path}: duplicate repository '{repository}'")
        repositories_seen.add(repository)

        allowed_events = payload.get("allowed_events", [])
        if not isinstance(allowed_events, list) or not allowed_events:
            errors.append(f"{path}: allowed_events must be a non-empty list")
        elif not all(isinstance(event, str) and event for event in allowed_events):
            errors.append(f"{path}: allowed_events entries must be non-empty strings")

        mappings = payload.get("path_mappings", [])
        if not isinstance(mappings, list) or not mappings:
            errors.append(f"{path}: path_mappings must be a non-empty list")
        else:
            for index, mapping in enumerate(mappings):
                if not isinstance(mapping, dict):
                    errors.append(f"{path}: path_mappings[{index}] must be an object")
                    continue
                prefix = _required_string(mapping, path, "prefix", errors)
                module_slug = _required_string(mapping, path, "module_slug", errors)
                if prefix and module_slug and module_slug not in module_slugs:
                    errors.append(
                        f"{path}: path mapping '{prefix}' references "
                        f"unknown module '{module_slug}'",
                    )

        route_default_slugs: set[str] = set()
        route_defaults = payload.get("route_defaults", [])
        if not isinstance(route_defaults, list):
            errors.append(f"{path}: route_defaults must be a list")
        else:
            for index, route in enumerate(route_defaults):
                if not isinstance(route, dict):
                    errors.append(f"{path}: route_defaults[{index}] must be an object")
                    continue
                module_slug = _required_string(route, path, "module_slug", errors)
                _required_string(route, path, "public_path", errors)
                _required_string(route, path, "upstream_host", errors)
                _required_int(route, path, "upstream_port", errors)
                if module_slug:
                    route_default_slugs.add(module_slug)
                    if module_slug not in module_slugs:
                        errors.append(
                            f"{path}: route default references unknown module "
                            f"'{module_slug}'",
                        )

        for module_slug in sorted(public_modules):
            if module_repositories.get(module_slug) != repository:
                continue
            if module_slug not in route_default_slugs:
                errors.append(
                    f"{path}: public module '{module_slug}' is missing from "
                    "route_defaults",
                )

        if repository:
            repository_manifests.append(payload)

    if not repository_manifests:
        errors.append("manifests/repositories: no repository manifest found")
    return repository_manifests


def _validate_apisix_routes(
    public_modules: dict[str, dict[str, Any]],
    repository_manifests: list[dict[str, Any]],
    errors: list[str],
) -> None:
    payload = _load_json(APISIX_ROUTES_FILE, errors)
    routes = payload.get("routes", [])
    if not isinstance(routes, list) or not routes:
        errors.append(f"{APISIX_ROUTES_FILE}: routes must be a non-empty list")
        return

    route_ids: set[str] = set()
    routes_by_id: dict[str, dict[str, Any]] = {}
    for index, route in enumerate(routes):
        if not isinstance(route, dict):
            errors.append(f"{APISIX_ROUTES_FILE}: routes[{index}] must be an object")
            continue
        route_id = _required_string(route, APISIX_ROUTES_FILE, "id", errors)
        _required_string(route, APISIX_ROUTES_FILE, "uri", errors)
        _required_string(route, APISIX_ROUTES_FILE, "name", errors)
        if route_id in route_ids:
            errors.append(f"{APISIX_ROUTES_FILE}: duplicate route id '{route_id}'")
        route_ids.add(route_id)
        routes_by_id[route_id] = route

    for module_slug, module in sorted(public_modules.items()):
        route_id = f"module-{module_slug}"
        route = routes_by_id.get(route_id)
        if route is None:
            errors.append(
                f"{APISIX_ROUTES_FILE}: missing public route '{route_id}'",
            )
            continue
        expected_uri = "/" + str(module["public_path"]).strip("/") + "/*"
        if route.get("uri") != expected_uri:
            errors.append(
                f"{APISIX_ROUTES_FILE}: route '{route_id}' uri should be "
                f"'{expected_uri}'",
            )

    for manifest in repository_manifests:
        for route_default in manifest.get("route_defaults", []):
            if not isinstance(route_default, dict):
                continue
            module_slug = route_default.get("module_slug")
            route_id = f"module-{module_slug}"
            route = routes_by_id.get(route_id)
            if route is None:
                errors.append(
                    f"{APISIX_ROUTES_FILE}: missing default route '{route_id}'",
                )
                continue
            expected_node = (
                f"{route_default.get('upstream_host')}:"
                f"{route_default.get('upstream_port')}"
            )
            nodes = route.get("upstream", {}).get("nodes", {})
            if expected_node not in nodes:
                errors.append(
                    f"{APISIX_ROUTES_FILE}: route '{route_id}' should target "
                    f"'{expected_node}'",
                )


def _validate_renovate(errors: list[str]) -> None:
    payload = _load_json(RENOVATE_FILE, errors)
    enabled_managers = payload.get("enabledManagers", [])
    if "custom.regex" not in enabled_managers:
        errors.append(f"{RENOVATE_FILE}: custom.regex manager must stay enabled")

    managers = payload.get("customManagers", [])
    if not isinstance(managers, list) or not managers:
        errors.append(f"{RENOVATE_FILE}: customManagers must define manifest image scan")
        return

    has_module_image_manager = any(
        isinstance(manager, dict)
        and any(
            "manifests/modules" in str(pattern)
            for pattern in manager.get("managerFilePatterns", [])
        )
        and any("currentValue" in str(match) for match in manager.get("matchStrings", []))
        for manager in managers
    )
    if not has_module_image_manager:
        errors.append(
            f"{RENOVATE_FILE}: missing custom manager for manifests/modules images",
        )

    image_pattern = re.compile(
        r'"image"\s*:\s*"(?P<dep_name>[^":]+(?:/[^":]+)+):(?P<current_value>[^"@]+)"',
    )
    image_matches = [
        match
        for path in _json_files(MANIFESTS_DIR / "modules")
        for match in image_pattern.finditer(path.read_text(encoding="utf-8"))
    ]
    if not image_matches:
        errors.append(
            f"{RENOVATE_FILE}: custom module image regex does not match any module",
        )


def main() -> int:
    errors: list[str] = []
    module_slugs, public_modules, module_repositories = _validate_modules(errors)
    _validate_tools_and_applications(module_slugs, errors)
    repository_manifests = _validate_repository_manifests(
        module_slugs,
        public_modules,
        module_repositories,
        errors,
    )
    _validate_apisix_routes(public_modules, repository_manifests, errors)
    _validate_renovate(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Hosting manifests validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
