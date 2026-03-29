from django.urls import path

from .views import GitHubWebhookView, HealthView, PublishRouteView, SyncGitHubView

urlpatterns = [
    path("health/", HealthView.as_view(), name="gateway-health"),
    path("github/sync/", SyncGitHubView.as_view(), name="github-sync"),
    path("github/webhook/", GitHubWebhookView.as_view(), name="github-webhook"),
    path("apisix/publish/", PublishRouteView.as_view(), name="apisix-publish"),
]
