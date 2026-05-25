import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase

from apps.hosting.discovery import auto_discover_tools_and_applications
from apps.hosting.models import HostedApplication, Module, Tool


class HostingDiscoveryTests(TestCase):
    def test_autodiscover_creates_modules_from_manifests(self):
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "modules").mkdir(parents=True)
            (base / "modules" / "flink-runtime.json").write_text(
                json.dumps(
                    {
                        "name": "DEALIoT Flink Runtime",
                        "slug": "flink-runtime",
                        "image": "ghcr.io/smartappli/dealiot-flink-pyflink:sha-test",
                        "repository_owner": "Smartappli",
                        "repository_name": "DEALIoT",
                        "source_path": "pipelines",
                        "deployment_target": "kubernetes",
                        "public_path": "/dealiot/flink",
                        "upstream_host": "flink-jobmanager",
                        "upstream_port": 8081,
                        "contract_topics": ["raw.sensor", "state.latest"],
                    },
                ),
                encoding="utf-8",
            )

            report = auto_discover_tools_and_applications(manifests_dir=base)

        self.assertEqual(report.modules_created, 1)
        self.assertEqual(report.errors, [])
        module = Module.objects.get(slug="flink-runtime")
        self.assertEqual(module.repository_owner, "Smartappli")
        self.assertEqual(module.repository_name, "DEALIoT")
        self.assertEqual(module.source_path, "pipelines")
        self.assertEqual(module.deployment_target, "kubernetes")
        self.assertEqual(module.public_path, "/dealiot/flink")
        self.assertEqual(module.upstream_host, "flink-jobmanager")
        self.assertEqual(module.upstream_port, 8081)
        self.assertEqual(module.contract_topics, ["raw.sensor", "state.latest"])

    def test_autodiscover_creates_tools_and_applications_from_manifests(self):
        module = Module.objects.create(
            name="Core",
            slug="module-core",
            image="ghcr.io/dealiot/module-core:latest",
            branch="main",
        )

        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "tools").mkdir(parents=True)
            (base / "applications").mkdir(parents=True)
            (base / "tools" / "backoffice.json").write_text(
                json.dumps(
                    {
                        "name": "Backoffice",
                        "slug": "backoffice",
                        "description": "Tool for operations",
                        "module_slugs": ["module-core"],
                        "version": "1.0.0",
                    },
                ),
                encoding="utf-8",
            )
            (base / "applications" / "storefront.json").write_text(
                json.dumps(
                    {
                        "name": "Storefront",
                        "slug": "storefront",
                        "description": "Customer app",
                        "module_slugs": ["module-core"],
                        "version": "2.1.0",
                    },
                ),
                encoding="utf-8",
            )

            report = auto_discover_tools_and_applications(manifests_dir=base)

        self.assertEqual(report.tools_created, 1)
        self.assertEqual(report.applications_created, 1)
        self.assertEqual(report.tool_versions_created, 1)
        self.assertEqual(report.application_versions_created, 1)
        self.assertEqual(report.errors, [])

        tool = Tool.objects.get(slug="backoffice")
        application = HostedApplication.objects.get(slug="storefront")
        self.assertEqual(list(tool.modules.all()), [module])
        self.assertEqual(list(application.modules.all()), [module])
        self.assertEqual(tool.current_version, "1.0.0")
        self.assertEqual(application.current_version, "2.1.0")

    def test_autodiscover_rolls_back_when_module_reference_is_missing(self):
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "tools").mkdir(parents=True)
            (base / "tools" / "broken.json").write_text(
                json.dumps(
                    {
                        "name": "Broken Tool",
                        "slug": "broken-tool",
                        "module_slugs": ["missing-module"],
                        "version": "1.4.2",
                    },
                ),
                encoding="utf-8",
            )

            report = auto_discover_tools_and_applications(manifests_dir=base)

        self.assertEqual(report.tools_created, 0)
        self.assertEqual(report.tool_versions_created, 0)
        self.assertTrue(report.rolled_back)
        self.assertTrue(report.errors)
        self.assertFalse(Tool.objects.filter(slug="broken-tool").exists())

    def test_autodiscover_rejects_invalid_version(self):
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "applications").mkdir(parents=True)
            (base / "applications" / "bad-version.json").write_text(
                json.dumps(
                    {
                        "name": "BadVersion",
                        "slug": "bad-version",
                        "version": "release-1",
                    },
                ),
                encoding="utf-8",
            )

            report = auto_discover_tools_and_applications(manifests_dir=base)

        self.assertEqual(report.applications_created, 0)
        self.assertTrue(report.rolled_back)
        self.assertTrue(report.errors)
        self.assertFalse(HostedApplication.objects.filter(slug="bad-version").exists())
