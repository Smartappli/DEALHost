from django.contrib import admin
from django.urls import include, path

from apps.hosting.views import ManagementAutoDiscoverView, ManagementInterfaceView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/hosting/", include("apps.hosting.urls")),
    path("api/gateway/", include("apps.gateway.urls")),
    path("hosting/manage/", ManagementInterfaceView.as_view(), name="hosting-management"),
    path(
        "hosting/manage/autodiscover/",
        ManagementAutoDiscoverView.as_view(),
        name="hosting-management-autodiscover",
    ),
]
