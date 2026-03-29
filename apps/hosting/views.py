from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .models import HostedApplication, Module, Tool
from .serializers import (
    HostedApplicationSerializer,
    ModuleAttachSerializer,
    ModuleSerializer,
    ToolSerializer,
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
    queryset = Tool.objects.prefetch_related("modules").all().order_by("name")
    serializer_class = ToolSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug", "description", "modules__slug"]
    ordering_fields = ["name", "slug", "created_at"]

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        enabled = self.request.query_params.get("enabled")
        module_slug = self.request.query_params.get("module_slug")
        if enabled is not None:
            queryset = queryset.filter(enabled=enabled.lower() == "true")
        if module_slug:
            queryset = queryset.filter(modules__slug=module_slug)
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
        return Response(ModuleSerializer(tool.modules.all(), many=True).data, status=status.HTTP_200_OK)


class HostedApplicationViewSet(viewsets.ModelViewSet):
    queryset = HostedApplication.objects.prefetch_related("modules").all().order_by("name")
    serializer_class = HostedApplicationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug", "description", "modules__slug"]
    ordering_fields = ["name", "slug", "created_at"]

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        enabled = self.request.query_params.get("enabled")
        module_slug = self.request.query_params.get("module_slug")
        if enabled is not None:
            queryset = queryset.filter(enabled=enabled.lower() == "true")
        if module_slug:
            queryset = queryset.filter(modules__slug=module_slug)
        return queryset.distinct()

    @action(detail=True, methods=["post"], url_path="attach-module")
    def attach_module(self, request: Request, pk: str | None = None) -> Response:
        serializer = ModuleAttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = self.get_object()
        application.modules.add(serializer.validated_data["module"])
        return Response(self.get_serializer(application).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="detach-module")
    def detach_module(self, request: Request, pk: str | None = None) -> Response:
        serializer = ModuleAttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = self.get_object()
        application.modules.remove(serializer.validated_data["module"])
        return Response(self.get_serializer(application).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="modules")
    def modules(self, request: Request, pk: str | None = None) -> Response:
        application = self.get_object()
        return Response(ModuleSerializer(application.modules.all(), many=True).data, status=status.HTTP_200_OK)
