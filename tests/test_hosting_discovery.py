import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase

from apps.hosting.discovery import auto_discover_tools_and_applications
from apps.hosting.models import HostedApplication, Module, Tool


class HostingDiscoveryTests(TestCase):
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

    def test_autodiscover_reports_missing_module_without_failing(self):
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

        self.assertEqual(report.tools_created, 1)
        self.assertEqual(report.tool_versions_created, 1)
        self.assertTrue(report.errors)
        tool = Tool.objects.get(slug="broken-tool")
        self.assertEqual(tool.modules.count(), 0)

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
        self.assertTrue(report.errors)
        self.assertFalse(HostedApplication.objects.filter(slug="bad-version").exists())
