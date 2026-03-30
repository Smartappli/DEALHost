from pathlib import Path

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .discovery import auto_discover_tools_and_applications
from .models import Dataset, HostedApplication, Module, Tool
from .serializers import (
    ApplicationVersionSerializer,
    HostedApplicationSerializer,
    ModuleAttachSerializer,
    ModuleSerializer,
    ToolSerializer,
    ToolVersionSerializer,
    VersionCreateSerializer,
)


class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.all().order_by("name")
    serializer_class = ModuleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug", "branch"]
    ordering_fields = ["name", "slug", "created_at"]

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        enabled = self.request.query_params.get("enabled")
        if enabled is not None:
            queryset = queryset.filter(enabled=enabled.lower() == "true")
        return queryset


class ToolViewSet(viewsets.ModelViewSet):
    queryset = (
        Tool.objects.prefetch_related("modules", "versions").all().order_by("name")
    )
    serializer_class = ToolSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug", "description", "modules__slug", "current_version"]
    ordering_fields = ["name", "slug", "current_version", "created_at", "released_at"]

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        enabled = self.request.query_params.get("enabled")
        module_slug = self.request.query_params.get("module_slug")
        current_version = self.request.query_params.get("current_version")
        if enabled is not None:
            queryset = queryset.filter(enabled=enabled.lower() == "true")
        if module_slug:
            queryset = queryset.filter(modules__slug=module_slug)
        if current_version:
            queryset = queryset.filter(current_version=current_version)
        return queryset.distinct()

    @action(detail=True, methods=["post"], url_path="attach-module")
    def attach_module(self, request: Request, pk: str | None = None) -> Response:
        serializer = ModuleAttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tool = self.get_object()
        tool.modules.add(serializer.validated_data["module"])
        return Response(self.get_serializer(tool).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="detach-module")
    def detach_module(self, request: Request, pk: str | None = None) -> Response:
        serializer = ModuleAttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tool = self.get_object()
        tool.modules.remove(serializer.validated_data["module"])
        return Response(self.get_serializer(tool).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="modules")
    def modules(self, request: Request, pk: str | None = None) -> Response:
        tool = self.get_object()
        return Response(
            ModuleSerializer(tool.modules.all(), many=True).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get", "post"], url_path="versions")
    def versions(self, request: Request, pk: str | None = None) -> Response:
        tool = self.get_object()
        if request.method == "GET":
            data = ToolVersionSerializer(tool.versions.all(), many=True).data
            return Response(data, status=status.HTTP_200_OK)

        serializer = VersionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tool.current_version = serializer.validated_data["version"]
        tool.released_at = timezone.now()
        tool.save(update_fields=["current_version", "released_at", "updated_at"])
        version_obj, _ = tool.versions.update_or_create(
            version=serializer.validated_data["version"],
            defaults={
                "notes": serializer.validated_data.get("notes", ""),
                "source": serializer.validated_data.get("source", "manual"),
            },
        )
        return Response(
            ToolVersionSerializer(version_obj).data,
            status=status.HTTP_201_CREATED,
        )


class HostedApplicationViewSet(viewsets.ModelViewSet):
    queryset = (
        HostedApplication.objects.prefetch_related("modules", "versions")
        .all()
        .order_by("name")
    )
    serializer_class = HostedApplicationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug", "description", "modules__slug", "current_version"]
    ordering_fields = ["name", "slug", "current_version", "created_at", "released_at"]

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        enabled = self.request.query_params.get("enabled")
        module_slug = self.request.query_params.get("module_slug")
        current_version = self.request.query_params.get("current_version")
        if enabled is not None:
            queryset = queryset.filter(enabled=enabled.lower() == "true")
        if module_slug:
            queryset = queryset.filter(modules__slug=module_slug)
        if current_version:
            queryset = queryset.filter(current_version=current_version)
        return queryset.distinct()

    @action(detail=True, methods=["post"], url_path="attach-module")
    def attach_module(self, request: Request, pk: str | None = None) -> Response:
        serializer = ModuleAttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = self.get_object()
        application.modules.add(serializer.validated_data["module"])
        return Response(
            self.get_serializer(application).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="detach-module")
    def detach_module(self, request: Request, pk: str | None = None) -> Response:
        serializer = ModuleAttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = self.get_object()
        application.modules.remove(serializer.validated_data["module"])
        return Response(
            self.get_serializer(application).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="modules")
    def modules(self, request: Request, pk: str | None = None) -> Response:
        application = self.get_object()
        return Response(
            ModuleSerializer(application.modules.all(), many=True).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get", "post"], url_path="versions")
    def versions(self, request: Request, pk: str | None = None) -> Response:
        application = self.get_object()
        if request.method == "GET":
            data = ApplicationVersionSerializer(
                application.versions.all(),
                many=True,
            ).data
            return Response(data, status=status.HTTP_200_OK)

        serializer = VersionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application.current_version = serializer.validated_data["version"]
        application.released_at = timezone.now()
        application.save(update_fields=["current_version", "released_at", "updated_at"])
        version_obj, _ = application.versions.update_or_create(
            version=serializer.validated_data["version"],
            defaults={
                "notes": serializer.validated_data.get("notes", ""),
                "source": serializer.validated_data.get("source", "manual"),
            },
        )
        return Response(
            ApplicationVersionSerializer(version_obj).data,
            status=status.HTTP_201_CREATED,
        )


class AutoDiscoverView(APIView):
    def post(self, request: Request) -> Response:
        report = auto_discover_tools_and_applications()
        return Response(report.to_dict(), status=status.HTTP_200_OK)


class ManagementInterfaceView(LoginRequiredMixin, TemplateView):
    template_name = "hosting/manage.html"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["modules"] = Module.objects.all().order_by("name")
        context["tools"] = (
            Tool.objects.prefetch_related("modules").all().order_by("name")
        )
        context["applications"] = (
            HostedApplication.objects.prefetch_related("modules").all().order_by("name")
        )

        user = self.request.user
        datasets = Dataset.objects.prefetch_related("modules").filter(enabled=True)
        if not user.is_superuser:
            datasets = datasets.filter(
                Q(users=user) | Q(groups__in=user.groups.all()),
            ).distinct()
        context["datasets"] = datasets.order_by("name")
        return context


class ManagementAutoDiscoverView(View):
    def post(self, request, *args, **kwargs):
        manifests_dir = Path("manifests")
        report = auto_discover_tools_and_applications(manifests_dir=manifests_dir)
        messages.success(
            request,
            (
                _("Autodiscovery completed: ")
                + _(
                    "tools created=%(tools_created)s, tools updated=%(tools_updated)s, "
                    "apps created=%(apps_created)s, apps updated=%(apps_updated)s, "
                    "tool versions created=%(tool_versions_created)s, "
                    "application versions created=%(application_versions_created)s.",
                )
                % {
                    "tools_created": report.tools_created,
                    "tools_updated": report.tools_updated,
                    "apps_created": report.applications_created,
                    "apps_updated": report.applications_updated,
                    "tool_versions_created": report.tool_versions_created,
                    "application_versions_created": report.application_versions_created,
                }
            ),
        )
        for error in report.errors or []:
            messages.error(request, error)
        return redirect("hosting-management")
