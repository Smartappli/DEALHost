from .dev import *  # noqa: F403

# Keep tests self-contained and independent from external Redis/Valkey.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "dealhost-tests",
    },
}
