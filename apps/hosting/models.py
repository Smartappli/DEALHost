from django.db import models


class Module(models.Model):
    """Un module déployable indépendamment (billing, auth, cms...)."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    image = models.CharField(max_length=255)
    branch = models.CharField(max_length=120, default="main")
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.branch})"


class Tool(models.Model):
    """Un outil technique consommant un ou plusieurs modules."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    modules = models.ManyToManyField(Module, related_name="tools", blank=True)
    current_version = models.CharField(max_length=32, default="0.1.0")
    released_at = models.DateTimeField(null=True, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class ToolVersion(models.Model):
    """Historique des versions publiées d'un outil."""

    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name="versions")
    version = models.CharField(max_length=32)
    notes = models.TextField(blank=True)
    source = models.CharField(max_length=32, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("tool", "version")
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.tool.slug}@{self.version}"


class HostedApplication(models.Model):
    """Une application métier pouvant composer un ou plusieurs modules."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    modules = models.ManyToManyField(Module, related_name="applications", blank=True)
    current_version = models.CharField(max_length=32, default="0.1.0")
    released_at = models.DateTimeField(null=True, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class ApplicationVersion(models.Model):
    """Historique des versions publiées d'une application hébergée."""

    application = models.ForeignKey(
        HostedApplication,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version = models.CharField(max_length=32)
    notes = models.TextField(blank=True)
    source = models.CharField(max_length=32, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("application", "version")
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.application.slug}@{self.version}"
