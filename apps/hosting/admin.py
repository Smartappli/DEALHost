from django.contrib import admin

from .models import HostedApplication, Module, Tool


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "branch", "enabled", "created_at")
    list_filter = ("enabled", "branch")
    search_fields = ("name", "slug", "image")


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "enabled", "created_at")
    list_filter = ("enabled",)
    search_fields = ("name", "slug", "description")
    filter_horizontal = ("modules",)


@admin.register(HostedApplication)
class HostedApplicationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "enabled", "created_at")
    list_filter = ("enabled",)
    search_fields = ("name", "slug", "description")
    filter_horizontal = ("modules",)
