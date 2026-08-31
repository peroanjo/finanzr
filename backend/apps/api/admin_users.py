from __future__ import annotations

from typing import Any, cast

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.api.views import active_membership, payload
from apps.audit.models import AuditEvent
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from apps.workspaces.services import provision_personal_workspace


def serialize_user(user: User, actor: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "is_self": user.pk == actor.pk,
        "date_joined": user.date_joined,
        "last_login": user.last_login,
    }


def require_admin(request: Request) -> tuple[User | None, Response | None]:
    user = cast(User, request.user)
    if user.role != User.Role.ADMIN:
        return None, Response({"error": _("Only an administrator can manage users")}, status=403)
    return user, None


def password_error(password: str, user: User) -> str | None:
    if len(password) < 12:
        return _("The password must be at least 12 characters long")
    try:
        validate_password(password, user=user)
    except ValidationError as exc:
        return " ".join(exc.messages)
    return None


@api_view(["GET", "POST"])
def users(request: Request) -> Response:
    actor, denied = require_admin(request)
    if denied is not None:
        return denied
    assert actor is not None
    if request.method == "GET":
        rows = User.objects.order_by("date_joined", "email")
        return Response([serialize_user(item, actor) for item in rows])

    data = payload(request)
    email = str(data.get("email", "")).strip().lower()
    display_name = str(data.get("display_name", "")).strip()
    role = str(data.get("role", User.Role.USER))
    password = str(data.get("password", ""))
    confirmation = str(data.get("password_confirmation", ""))
    try:
        validate_email(email)
    except ValidationError:
        return Response({"error": _("Enter a valid email address")}, status=400)
    if User.objects.filter(email__iexact=email).exists():
        return Response(
            {"error": _("An account with this email address already exists")}, status=409
        )
    if role not in {User.Role.ADMIN, User.Role.USER}:
        return Response({"error": _("The account role is not valid")}, status=400)
    if password != confirmation:
        return Response({"error": _("The passwords do not match")}, status=400)
    candidate = User(email=email, display_name=display_name, role=role)
    if error := password_error(password, candidate):
        return Response({"error": error}, status=400)

    membership = active_membership(request)
    with transaction.atomic():
        user = User.objects.create_user(
            email=email,
            password=password,
            display_name=display_name,
            role=role,
        )
        provision_personal_workspace(user)
        AuditEvent.objects.create(
            workspace=membership.workspace,
            actor=actor,
            event_type="user.created",
            object_type="user",
            object_id=user.id,
            metadata={"email": user.email, "role": user.role},
        )
    return Response(serialize_user(user, actor), status=201)


@api_view(["PATCH", "DELETE"])
def user_detail(request: Request, user_id: str) -> Response:
    actor, denied = require_admin(request)
    if denied is not None:
        return denied
    assert actor is not None
    target = get_object_or_404(User, pk=user_id)
    if target.pk == actor.pk:
        return Response({"error": _("You cannot block or delete your own account")}, status=400)
    membership = active_membership(request)

    if request.method == "PATCH":
        data = payload(request)
        update_fields: list[str] = []
        changed_fields: list[str] = []
        next_active = data.get("is_active", target.is_active)
        next_role = str(data.get("role", target.role))
        if not isinstance(next_active, bool):
            return Response({"error": _("The access status is not valid")}, status=400)
        if next_role not in {User.Role.ADMIN, User.Role.USER, User.Role.DEMO}:
            return Response({"error": _("The account role is not valid")}, status=400)
        removing_active_admin = (
            target.role == User.Role.ADMIN
            and target.is_active
            and (next_role != User.Role.ADMIN or not next_active)
        )
        if removing_active_admin:
            active_admins = User.objects.filter(role=User.Role.ADMIN, is_active=True).count()
            if active_admins <= 1:
                return Response(
                    {"error": _("At least one active administrator must remain")}, status=409
                )

        if "email" in data:
            email = str(data.get("email", "")).strip().lower()
            try:
                validate_email(email)
            except ValidationError:
                return Response({"error": _("Enter a valid email address")}, status=400)
            if User.objects.filter(email__iexact=email).exclude(pk=target.pk).exists():
                return Response(
                    {"error": _("An account with this email address already exists")}, status=409
                )
            if email != target.email:
                target.email = email
                update_fields.append("email")
                changed_fields.append("email")
        if "display_name" in data:
            display_name = str(data.get("display_name", "")).strip()
            if display_name != target.display_name:
                target.display_name = display_name
                update_fields.append("display_name")
                changed_fields.append("display_name")
        if next_role != target.role:
            target.role = next_role
            update_fields.append("role")
            changed_fields.append("role")
        if next_active != target.is_active:
            target.is_active = next_active
            update_fields.append("is_active")
            changed_fields.append("is_active")
        password = str(data.get("password", ""))
        if password:
            if password != str(data.get("password_confirmation", "")):
                return Response({"error": _("The passwords do not match")}, status=400)
            if error := password_error(password, target):
                return Response({"error": error}, status=400)
            target.set_password(password)
            update_fields.append("password")
            changed_fields.append("password")
        if not update_fields:
            return Response({"error": _("There are no changes to save")}, status=400)

        target.save(update_fields=update_fields)
        AuditEvent.objects.create(
            workspace=membership.workspace,
            actor=actor,
            event_type="user.updated",
            object_type="user",
            object_id=target.id,
            metadata={"email": target.email, "changed_fields": changed_fields},
        )
        return Response(serialize_user(target, actor))

    with transaction.atomic():
        locked_target = User.objects.select_for_update().get(pk=target.pk)
        owned_workspace_ids = list(
            locked_target.memberships.filter(role=WorkspaceMembership.Role.OWNER).values_list(
                "workspace_id", flat=True
            )
        )
        owned_workspaces = list(
            Workspace.objects.select_for_update().filter(pk__in=owned_workspace_ids)
        )
        if any(
            owned_workspace.memberships.exclude(user=locked_target).exists()
            for owned_workspace in owned_workspaces
        ):
            return Response(
                {"error": _("An account that owns a workspace cannot be deleted")},
                status=409,
            )
        target_id = locked_target.id
        target_email = locked_target.email
        archived_at = timezone.now()
        Workspace.objects.filter(pk__in=owned_workspace_ids).update(archived_at=archived_at)
        locked_target.delete()
        AuditEvent.objects.create(
            workspace=membership.workspace,
            actor=actor,
            event_type="user.deleted",
            object_type="user",
            object_id=target_id,
            metadata={"email": target_email},
        )
    return Response(status=204)
