from rest_framework.routers import DefaultRouter

from .views import HostedApplicationViewSet, ModuleViewSet, ToolViewSet

router = DefaultRouter()
router.register("modules", ModuleViewSet, basename="modules")
router.register("tools", ToolViewSet, basename="tools")
router.register("applications", HostedApplicationViewSet, basename="applications")

urlpatterns = router.urls
