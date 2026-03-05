import os
from pathlib import Path

# ── Inline CSP Middleware (L2) ──────────────────────────────────────────────
# A restrictive Content-Security-Policy blocks inline script injection and
# limits resource origins.  Adjust the policy to match any CDNs you add.
class ContentSecurityPolicyMiddleware:
    """Attach a Content-Security-Policy header to every HTTP response."""

    # Tune this policy to match your actual asset/CDN requirements.
    _POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' unpkg.com cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
        "font-src 'self' fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = self._POLICY
        return response

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ["SECRET_KEY"]
DEBUG = os.environ.get("DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost").split(",")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "sensors",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "config.settings.ContentSecurityPolicyMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# No Django DB — all data flows through FastAPI
DATABASES = {}

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Redis cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/1"),
    }
}

# FastAPI base URL (internal docker network)
FASTAPI_URL = os.environ.get("FASTAPI_URL", "http://api:8001")

# API key for authenticated requests to FastAPI
API_KEY = os.environ.get("API_KEY", "")
# Demo-only mutation controls for seed/clear endpoints.
ENABLE_MUTATIONS = os.environ.get("ENABLE_MUTATIONS", "1" if DEBUG else "0") == "1"
# Comma-separated IPs allowed to call mutation endpoints (C3).
# Defaults to loopback only; set MUTATION_ALLOWED_IPS=* to allow all (not recommended).
MUTATION_ALLOWED_IPS = os.environ.get("MUTATION_ALLOWED_IPS", "127.0.0.1")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
# SECURE_BROWSER_XSS_FILTER is deprecated and removed (ignored by modern browsers)

# CSRF: no SessionMiddleware, so the token lives in the cookie.
# Keep CSRF_COOKIE_HTTPONLY=False (default) so HTMX can read the cookie value
# and send it in the X-CSRFToken request header.

# In production (DEBUG=False), enforce secure cookies and HSTS
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # SameSite=Strict prevents cross-site request forgery even before CSRF middleware fires
    SESSION_COOKIE_SAMESITE = "Strict"
    CSRF_COOKIE_SAMESITE = "Strict"

    # If running behind a TLS-terminating reverse proxy (e.g. nginx, Caddy)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 63072000  # 2 years
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Structured logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "sensors": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
