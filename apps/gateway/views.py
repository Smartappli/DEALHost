from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

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
            }
        )


class PublishRouteView(APIView):
    def post(self, request):
        module_slug = request.data.get("module_slug")
        if not module_slug:
            return Response(
                {"detail": "module_slug est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = ApisixService().publish_route(module_slug)
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
                {"detail": "Signature GitHub invalide."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        module_slug = request.data.get("module_slug", "core")
        route_status = ApisixService().publish_route(module_slug)
        return Response(
            {
                "event": request.headers.get("X-GitHub-Event", "unknown"),
                "module_slug": module_slug,
                "route": route_status["route_id"],
            },
            status=status.HTTP_202_ACCEPTED,
        )
