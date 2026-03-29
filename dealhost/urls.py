from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/hosting/", include("apps.hosting.urls")),
    path("api/gateway/", include("apps.gateway.urls")),
]
