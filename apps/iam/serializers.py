from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from rest_framework import serializers

User = get_user_model()


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "name", "codename", "content_type"]
        read_only_fields = fields


class GroupSerializer(serializers.ModelSerializer):
    permission_ids = serializers.PrimaryKeyRelatedField(
        source="permissions",
        queryset=Permission.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = Group
        fields = ["id", "name", "permissions", "permission_ids"]
        read_only_fields = ["id", "permissions"]


class UserSerializer(serializers.ModelSerializer):
    group_ids = serializers.PrimaryKeyRelatedField(
        source="groups",
        queryset=Group.objects.all(),
        many=True,
        required=False,
    )
    permission_ids = serializers.PrimaryKeyRelatedField(
        source="user_permissions",
        queryset=Permission.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "group_ids",
            "user_permissions",
            "permission_ids",
            "date_joined",
            "last_login",
        ]
        read_only_fields = ["id", "groups", "user_permissions", "date_joined", "last_login"]


class UserCreateSerializer(UserSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["password"]

    def create(self, validated_data):
        groups = validated_data.pop("groups", [])
        user_permissions = validated_data.pop("user_permissions", [])
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        if groups:
            user.groups.set(groups)
        if user_permissions:
            user.user_permissions.set(user_permissions)
        return user


class PasswordChangeSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)
