from __future__ import annotations

import hashlib
import time
import uuid
from collections import defaultdict, deque
from threading import Lock
from typing import Any, cast

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import translation
from django.utils.translation import gettext as _

from apps.audit.models import AuditEvent
from apps.common.i18n import language_from_accept_header, normalize_language
from apps.common.models import InstallationSettings
from apps.users.models import User
from apps.workspaces.models import WorkspaceMembership

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


class UserLanguageMiddleware:
    """Activate the effective UI language for every request and response."""

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        installation_language = InstallationSettings.load().default_language
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            language = normalize_language(getattr(user, "language", "")) or installation_language
        else:
            language = (
                language_from_accept_header(request.headers.get("Accept-Language", ""))
                or installation_language
            )
        request.LANGUAGE_CODE = language
        request.finanzr_default_language = installation_language  # type: ignore[attr-defined]
        translation.activate(language)
        try:
            response = cast(HttpResponse, self.get_response(request))
            response.headers["Content-Language"] = str(request.LANGUAGE_CODE)
            return response
        finally:
            translation.deactivate()


def client_ip(request: HttpRequest) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
    return str(forwarded or request.META.get("REMOTE_ADDR", "unknown"))


class ApiSecurityMiddleware:
    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:80]
        if request.path.startswith("/api/") and self._limited(request):
            response: HttpResponse = JsonResponse(
                {"error": _("Too many requests; please try again later")}, status=429
            )
        else:
            response = self.get_response(request)
        response["X-Request-ID"] = request_id
        response["Content-Security-Policy"] = settings.CONTENT_SECURITY_POLICY
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if (
            request.path.startswith("/api/")
            and request.method not in {"GET", "HEAD", "OPTIONS"}
            and getattr(request, "user", None)
            and request.user.is_authenticated
        ):
            self._audit(request, response, request_id)
        return response

    def _limited(self, request: HttpRequest) -> bool:
        sensitive = request.path.startswith("/api/auth/") or "upload" in request.path
        limit = settings.API_SENSITIVE_RATE_LIMIT if sensitive else settings.API_RATE_LIMIT
        window = 60.0
        key = f"{client_ip(request)}:{request.path}:{request.method}"
        now = time.monotonic()
        with _lock:
            bucket = _hits[key]
            while bucket and bucket[0] < now - window:
                bucket.popleft()
            if len(bucket) >= limit:
                return True
            bucket.append(now)
        return False

    @staticmethod
    def _audit(request: HttpRequest, response: HttpResponse, request_id: str) -> None:
        user = cast(User, request.user)
        workspace_id = str(request.session.get("active_workspace_id", ""))
        if not workspace_id:
            return
        membership = WorkspaceMembership.objects.filter(
            user=user,
            workspace_id=workspace_id,
        ).first()
        if not membership:
            return
        digest = hashlib.sha256(f"{settings.SECRET_KEY}:{client_ip(request)}".encode()).hexdigest()
        AuditEvent.objects.create(
            workspace=membership.workspace,
            actor=user,
            event_type=f"api.{str(request.method).lower()}",
            object_type=request.path[:100],
            metadata={"status": response.status_code, "request_id": request_id},
            ip_hash=digest,
        )
