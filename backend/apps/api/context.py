from __future__ import annotations

from typing import cast

from rest_framework.request import Request

from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership


def active_membership(request: Request) -> WorkspaceMembership:
    user = cast(User, request.user)
    memberships = WorkspaceMembership.objects.select_related("workspace").filter(
        user=user, workspace__archived_at__isnull=True
    )
    workspace_id = request.session.get("active_workspace_id")
    if workspace_id:
        selected = memberships.filter(workspace_id=workspace_id).first()
        if selected:
            return selected
    membership = memberships.first()
    if not membership:
        raise Workspace.DoesNotExist
    request.session["active_workspace_id"] = str(membership.workspace_id)
    return membership


def workspace(request: Request) -> Workspace:
    return active_membership(request).workspace
