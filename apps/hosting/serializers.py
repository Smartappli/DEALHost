from rest_framework import serializers

from .models import HostedApplication, Module, Tool


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = [
            "id",
            "name",
            "slug",
            "image",
            "branch",
            "enabled",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ToolSerializer(serializers.ModelSerializer):
    module_ids = serializers.PrimaryKeyRelatedField(
        source="modules",
        queryset=Module.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = Tool
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "module_ids",
            "enabled",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class HostedApplicationSerializer(serializers.ModelSerializer):
    module_ids = serializers.PrimaryKeyRelatedField(
        source="modules",
        queryset=Module.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = HostedApplication
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "module_ids",
            "enabled",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
