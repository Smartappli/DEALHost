from rest_framework import viewsets

from .models import HostedApplication, Module, Tool
from .serializers import HostedApplicationSerializer, ModuleSerializer, ToolSerializer


class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.all().order_by("name")
    serializer_class = ModuleSerializer


class ToolViewSet(viewsets.ModelViewSet):
    queryset = Tool.objects.prefetch_related("modules").all().order_by("name")
    serializer_class = ToolSerializer


class HostedApplicationViewSet(viewsets.ModelViewSet):
    queryset = HostedApplication.objects.prefetch_related("modules").all().order_by("name")
    serializer_class = HostedApplicationSerializer
