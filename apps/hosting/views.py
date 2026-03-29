from rest_framework import viewsets

from .models import Module
from .serializers import ModuleSerializer


class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.all().order_by("name")
    serializer_class = ModuleSerializer
