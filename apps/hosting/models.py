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
