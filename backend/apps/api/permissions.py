from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.api.context import active_membership
from apps.users.models import User
from apps.workspaces.models import WorkspaceMembership


class IsAuthenticatedAndDemoReadOnly(BasePermission):
    """Require a session and keep the shared demo dataset immutable."""

    message = _("The demo account is read-only")
    write_allowlist = {
        "/api/auth/logout",
        "/api/auth/preferences",
        "/api/workspaces/current",
    }

    def has_permission(self, request: Request, view: object) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS or request.path in self.write_allowlist:
            return True
        return getattr(user, "role", User.Role.USER) != User.Role.DEMO


def forbidden_if_readonly(request: Request) -> Response | None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return None
    if active_membership(request).role == WorkspaceMembership.Role.VIEWER:
        return Response({"error": gettext("Insufficient permissions")}, status=403)
    return None
