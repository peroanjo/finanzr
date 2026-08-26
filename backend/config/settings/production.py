from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

if SECRET_KEY == "unsafe-development-only":  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required in production")

DEBUG = False
LAN_MODE = env_bool("FINANZR_LAN_MODE", False)  # noqa: F405
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True) and not LAN_MODE  # noqa: F405
SESSION_COOKIE_SECURE = not LAN_MODE
CSRF_COOKIE_SECURE = not LAN_MODE
SECURE_HSTS_SECONDS = 0 if LAN_MODE else int(env("DJANGO_SECURE_HSTS_SECONDS", "31536000"))  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = not LAN_MODE
SECURE_HSTS_PRELOAD = not LAN_MODE
SECURE_PROXY_SSL_HEADER = None if LAN_MODE else ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")  # noqa: F405
