from rest_framework import serializers

from .models import HostedApplication, Module, Tool


class ModuleSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ["id", "name", "slug", "image", "branch", "enabled"]
        read_only_fields = fields


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
    modules = ModuleSummarySerializer(many=True, read_only=True)
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
            "modules",
            "module_ids",
            "enabled",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class HostedApplicationSerializer(serializers.ModelSerializer):
    modules = ModuleSummarySerializer(many=True, read_only=True)
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
            "modules",
            "module_ids",
            "enabled",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ModuleAttachSerializer(serializers.Serializer):
    module_id = serializers.PrimaryKeyRelatedField(
        source="module",
        queryset=Module.objects.all(),
    )
