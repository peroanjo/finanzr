"""Explicit workspace membership and single-record resource sharing."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Account
from apps.api.auth import user_payload
from apps.api.context import active_membership, workspace
from apps.api.request_data import payload
from apps.portfolio.models import ManualAsset
from apps.real_estate.models import RealEstateInvestment
from apps.users.models import User
from apps.workspaces.models import AssetShare, Workspace, WorkspaceInvitation, WorkspaceMembership

RESOURCE_MODELS: dict[str, type[Account] | type[ManualAsset] | type[RealEstateInvestment]] = {
    "account": Account,
    "manual_asset": ManualAsset,
    "real_estate": RealEstateInvestment,
}


def owner(request: Request) -> WorkspaceMembership:
    membership = active_membership(request)
    if membership.role != WorkspaceMembership.Role.OWNER or membership.workspace.is_personal:
        raise PermissionDenied()
    return membership


@api_view(["POST"])
def create_workspace(request: Request) -> Response:
    data = payload(request)
    name = str(data.get("name", "")).strip()
    if not name or len(name) > 120:
        return Response({"error": _("Invalid workspace name")}, status=400)
    with transaction.atomic():
        item = Workspace.objects.create(
            name=name, slug=f"shared-{uuid4().hex}", base_currency=workspace(request).base_currency
        )
        WorkspaceMembership.objects.create(
            workspace=item, user=cast(User, request.user), role="owner"
        )
    request.session["active_workspace_id"] = str(item.pk)
    return Response(user_payload(cast(User, request.user), request), status=201)


@api_view(["GET", "PATCH", "DELETE"])
def workspace_settings(request: Request) -> Response:
    current = workspace(request)
    if request.method == "GET":
        members = current.memberships.select_related("user").order_by("created_at")
        invitations = current.invitations.filter(
            accepted_at__isnull=True, expires_at__gt=timezone.now()
        )
        return Response(
            {
                "id": str(current.pk),
                "name": current.name,
                "is_personal": current.is_personal,
                "role": active_membership(request).role,
                "members": [
                    {
                        "id": str(row.pk),
                        "name": row.user.display_name,
                        "email": row.user.email,
                        "role": row.role,
                        "is_self": row.user_id == request.user.pk,
                    }
                    for row in members
                ],
                "invitations": [
                    {
                        "id": str(row.pk),
                        "email": row.email,
                        "role": row.role,
                        "expires_at": row.expires_at,
                    }
                    for row in invitations
                ]
                if active_membership(request).role == "owner"
                else [],
            }
        )
    owner(request)
    if request.method == "DELETE":
        current.archived_at = timezone.now()
        current.save(update_fields=("archived_at", "updated_at"))
        request.session.pop("active_workspace_id", None)
    else:
        name = str(payload(request).get("name", "")).strip()
        if not name or len(name) > 120:
            return Response({"error": _("Invalid workspace name")}, status=400)
        current.name = name
        current.save(update_fields=("name", "updated_at"))
    return Response(user_payload(cast(User, request.user), request))


@api_view(["PATCH", "DELETE"])
@transaction.atomic
def member_detail(request: Request, member_id: UUID) -> Response:
    current = workspace(request)
    Workspace.objects.select_for_update().get(pk=current.pk)
    item = get_object_or_404(WorkspaceMembership, pk=member_id, workspace=current)
    actor = active_membership(request)
    leaving = request.method == "DELETE" and item.user_id == request.user.pk
    if current.is_personal or (not leaving and actor.role != "owner"):
        raise PermissionDenied()
    role = str(payload(request).get("role", "")) if request.method == "PATCH" else None
    if request.method == "PATCH" and role not in {"owner", "editor", "viewer"}:
        return Response({"error": _("Invalid role")}, status=400)
    if (
        item.role == "owner"
        and role != "owner"
        and current.memberships.filter(role="owner").count() == 1
    ):
        return Response({"error": _("The last owner cannot leave or be demoted")}, status=409)
    if request.method == "DELETE":
        item.delete()
    else:
        item.role = cast(str, role)
        item.save(update_fields=("role",))
    return Response(user_payload(cast(User, request.user), request))


@api_view(["DELETE"])
def invitation_detail(request: Request, invitation_id: UUID) -> Response:
    membership = owner(request)
    get_object_or_404(
        WorkspaceInvitation, pk=invitation_id, workspace=membership.workspace
    ).delete()
    return Response(status=204)


def share_row(item: AssetShare) -> dict[str, Any]:
    kind = next(key for key in RESOURCE_MODELS if getattr(item, f"{key}_id"))
    resource = getattr(item, kind)
    return {
        "id": str(item.pk),
        "kind": kind,
        "resource_id": str(resource.pk),
        "name": resource.name,
        "target_id": str(item.target_id),
        "target_name": item.target.name,
        "access": item.access,
    }


@api_view(["GET", "POST"])
def shares(request: Request) -> Response:
    user = cast(User, request.user)
    owned = Workspace.objects.filter(
        memberships__user=user, memberships__role="owner", archived_at__isnull=True
    )
    targets = Workspace.objects.filter(
        memberships__user=user,
        memberships__role__in=["owner", "editor"],
        archived_at__isnull=True,
        is_personal=False,
    )
    if request.method == "GET":
        resources = []
        outgoing_ids: set[UUID] = set()
        for kind, model in RESOURCE_MODELS.items():
            for item in model.objects.filter(workspace__in=owned, archived_at__isnull=True):
                resources.append(
                    {
                        "kind": kind,
                        "id": str(item.pk),
                        "name": item.name,
                        "workspace_id": str(item.workspace_id),
                    }
                )
            outgoing_ids.update(
                AssetShare.objects.filter(**{f"{kind}__workspace__in": owned}).values_list(
                    "pk", flat=True
                )
            )
        outgoing = AssetShare.objects.filter(pk__in=outgoing_ids).select_related(
            "target", *RESOURCE_MODELS
        )
        incoming = AssetShare.objects.filter(target=workspace(request)).select_related(
            "target", *RESOURCE_MODELS
        )
        return Response(
            {
                "resources": resources,
                "targets": [{"id": str(item.pk), "name": item.name} for item in targets],
                "outgoing": [share_row(item) for item in outgoing],
                "incoming": [share_row(item) for item in incoming],
            }
        )
    data = payload(request)
    kind = str(data.get("kind", ""))
    resource_model = RESOURCE_MODELS.get(kind)
    if resource_model is None or data.get("access") not in {"read", "edit"}:
        return Response({"error": _("Invalid share")}, status=400)
    try:
        resource_id, target_id = (
            UUID(str(data.get("resource_id"))),
            UUID(str(data.get("target_id"))),
        )
    except ValueError:
        return Response({"error": _("Invalid resource or workspace")}, status=400)
    item = cast(
        Account | ManualAsset | RealEstateInvestment,
        get_object_or_404(
            resource_model, pk=resource_id, workspace__in=owned, archived_at__isnull=True
        ),
    )
    target = get_object_or_404(targets, pk=target_id)
    if item.workspace_id == target.pk:
        return Response({"error": _("The resource already belongs to this workspace")}, status=400)
    if item.workspace.base_currency != target.base_currency:
        return Response(
            {"error": _("Shared workspaces must use the same reporting currency")}, status=400
        )
    lookup: dict[str, Any] = {"target": target, kind: item}
    grant, _created = AssetShare.objects.update_or_create(
        defaults={"access": data["access"]}, **lookup
    )
    return Response(share_row(grant), status=201)


@api_view(["DELETE"])
def share_detail(request: Request, share_id: UUID) -> Response:
    item = get_object_or_404(AssetShare, pk=share_id)
    kind = next(key for key in RESOURCE_MODELS if getattr(item, f"{key}_id"))
    resource = getattr(item, kind)
    if not WorkspaceMembership.objects.filter(
        user=cast(User, request.user), workspace_id=resource.workspace_id, role="owner"
    ).exists():
        raise PermissionDenied()
    item.delete()
    return Response(status=204)
