from __future__ import annotations

from django.db import transaction

from apps.users.models import User

from .models import Workspace, WorkspaceMembership


@transaction.atomic
def provision_personal_workspace(user: User) -> WorkspaceMembership:
    """Create the private workspace that belongs to a newly provisioned user."""
    slug = f"personal-{user.id.hex}"
    existing = (
        WorkspaceMembership.objects.select_related("workspace")
        .filter(user=user, workspace__slug=slug)
        .first()
    )
    if existing is not None:
        if existing.role != WorkspaceMembership.Role.OWNER:
            existing.role = WorkspaceMembership.Role.OWNER
            existing.save(update_fields=("role",))
        return existing

    workspace = Workspace.objects.create(
        name=user.display_name.strip() or user.email,
        slug=slug,
    )
    return WorkspaceMembership.objects.create(
        workspace=workspace,
        user=user,
        role=WorkspaceMembership.Role.OWNER,
    )
