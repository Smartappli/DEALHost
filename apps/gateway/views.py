from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.events import publish_event
from apps.common.events.subjects import (
    GATEWAY_GITHUB_WEBHOOK_RECEIVED,
    GATEWAY_ROUTE_PUBLISH_COMPLETED,
    GATEWAY_ROUTE_PUBLISH_FAILED,
    GATEWAY_ROUTE_PUBLISH_REQUESTED,
)

from .services import ApisixService, GitHubService


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok", "service": "gateway"})


class SyncGitHubView(APIView):
    def post(self, request):
        branch = request.data.get("branch", "main")
        commit = GitHubService().latest_commit(branch=branch)
        return Response(
            {
                "repository": f"{commit['repository']['full_name']}",
                "branch": branch,
                "sha": commit["sha"],
                "message": commit["commit"]["message"],
            },
        )


class PublishRouteView(APIView):
    def post(self, request):
        module_slug = request.data.get("module_slug")
        if not module_slug:
            return Response(
                {"detail": _("module_slug is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        publish_event(
            event_type=GATEWAY_ROUTE_PUBLISH_REQUESTED,
            data={"module_slug": module_slug},
            producer="apps.gateway.PublishRouteView",
        )
        try:
            result = ApisixService().publish_route(module_slug)
        except Exception as exc:
            publish_event(
                event_type=GATEWAY_ROUTE_PUBLISH_FAILED,
                data={"module_slug": module_slug, "error": str(exc)},
                producer="apps.gateway.PublishRouteView",
            )
            raise
        publish_event(
            event_type=GATEWAY_ROUTE_PUBLISH_COMPLETED,
            data={"module_slug": module_slug, "route_id": result.get("route_id")},
            producer="apps.gateway.PublishRouteView",
        )
        return Response(result, status=status.HTTP_201_CREATED)


class GitHubWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        raw_payload = request.body
        signature = request.headers.get("X-Hub-Signature-256")
        github = GitHubService()

        if not github.verify_signature(raw_payload, signature):
            return Response(
                {"detail": _("Invalid GitHub signature.")},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        module_slug = request.data.get("module_slug", "core")
        publish_event(
            event_type=GATEWAY_GITHUB_WEBHOOK_RECEIVED,
            data={
                "event": request.headers.get("X-GitHub-Event", "unknown"),
                "module_slug": module_slug,
            },
            producer="apps.gateway.GitHubWebhookView",
        )
        publish_event(
            event_type=GATEWAY_ROUTE_PUBLISH_REQUESTED,
            data={"module_slug": module_slug, "source": "github_webhook"},
            producer="apps.gateway.GitHubWebhookView",
        )
        route_status = ApisixService().publish_route(module_slug)
        publish_event(
            event_type=GATEWAY_ROUTE_PUBLISH_COMPLETED,
            data={"module_slug": module_slug, "route_id": route_status.get("route_id")},
            producer="apps.gateway.GitHubWebhookView",
        )
        return Response(
            {
                "event": request.headers.get("X-GitHub-Event", "unknown"),
                "module_slug": module_slug,
                "route": route_status["route_id"],
            },
            status=status.HTTP_202_ACCEPTED,
        )
