from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any, cast

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone, translation
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.api.views import active_membership, payload, percentage_rate
from apps.common.i18n import (
    activate_request_language,
    effective_language,
    installation_language,
    normalize_language,
)
from apps.common.models import InstallationSettings, SummaryPreference
from apps.common.summary_preferences import (
    SUMMARY_SOURCE_KEYS,
    default_summary_sources,
    effective_summary_sources,
    normalize_summary_sources,
)
from apps.users.models import User
from apps.workspaces.models import WorkspaceInvitation, WorkspaceMembership


def user_payload(user: User, request: Request) -> dict[str, Any]:
    memberships = WorkspaceMembership.objects.select_related("workspace").filter(user=user)
    active_id = request.session.get("active_workspace_id")
    installation = InstallationSettings.load()
    active_membership_item = (
        next(
            (item for item in memberships if str(item.workspace_id) == str(active_id)),
            None,
        )
        or memberships.first()
    )
    if active_membership_item is not None:
        active_id = str(active_membership_item.workspace_id)
        request.session["active_workspace_id"] = active_id
        summary_sources, summary_scope = effective_summary_sources(
            user, active_membership_item.workspace, installation
        )
    else:
        summary_sources, summary_scope = default_summary_sources(), "installation"
    try:
        installation_sources = normalize_summary_sources(installation.default_summary_sources)
    except ValidationError:
        installation_sources = default_summary_sources()
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "language": effective_language(user, request),
        "preferred_language": user.language or None,
        "default_language": installation_language(request),
        "default_crowdfunding_tax_rate": float(installation.default_crowdfunding_tax_rate),
        "summary_sources": summary_sources,
        "summary_sources_scope": summary_scope,
        "default_summary_sources": installation_sources,
        "summary_source_keys": list(SUMMARY_SOURCE_KEYS),
        "active_workspace_id": active_id,
        "workspaces": [
            {
                "id": str(item.workspace_id),
                "name": item.workspace.name,
                "slug": item.workspace.slug,
                "base_currency": item.workspace.base_currency,
                "role": item.role,
            }
            for item in memberships
        ],
    }


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def csrf(request: Request) -> Response:
    return Response({"csrfToken": get_token(request)})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@csrf_protect
def login_view(request: Request) -> Response:
    data = payload(request)
    user = authenticate(request, email=data.get("email", ""), password=data.get("password", ""))
    if user is None:
        return Response({"error": _("Incorrect email or password")}, status=400)
    login(request, user)
    activate_request_language(request, effective_language(user, request))
    membership = WorkspaceMembership.objects.filter(user=user).first()
    if membership:
        request.session["active_workspace_id"] = str(membership.workspace_id)
    return Response({**user_payload(user, request), "csrfToken": get_token(request)})


@api_view(["POST"])
def logout_view(request: Request) -> Response:
    logout(request)
    return Response({"ok": True})


@api_view(["GET"])
def me(request: Request) -> Response:
    active_membership(request)
    return Response(user_payload(cast(User, request.user), request))


@api_view(["PATCH"])
def update_preferences(request: Request) -> Response:
    user = cast(User, request.user)
    data = payload(request)
    if "language" not in data and "summary_sources" not in data:
        return Response({"error": _("You must provide a preference")}, status=400)
    language: str | None = None
    if "language" in data:
        raw_language = data.get("language")
        language = (
            "" if raw_language is None or raw_language == "" else normalize_language(raw_language)
        )
        if language is None:
            return Response({"error": _("The language is not valid")}, status=400)
    summary_sources: list[str] | None = None
    clear_summary_sources = False
    if "summary_sources" in data:
        if user.role == User.Role.DEMO:
            return Response({"error": _("The demo account is read-only")}, status=403)
        raw_sources = data.get("summary_sources")
        if raw_sources is None:
            clear_summary_sources = True
        else:
            try:
                summary_sources = normalize_summary_sources(raw_sources)
            except ValidationError as exc:
                return Response(
                    {
                        "error": exc.messages[0]
                        if exc.messages
                        else _("The selected summary source is not valid")
                    },
                    status=400,
                )
    membership = active_membership(request) if "summary_sources" in data else None
    with transaction.atomic():
        if language is not None:
            user.language = language
            user.save(update_fields=("language",))
        if membership is not None:
            if clear_summary_sources:
                SummaryPreference.objects.filter(user=user, workspace=membership.workspace).delete()
            else:
                SummaryPreference.objects.update_or_create(
                    user=user,
                    workspace=membership.workspace,
                    defaults={"included_sources": summary_sources or []},
                )
    if language is not None:
        activate_request_language(request, effective_language(user, request))
    return Response(user_payload(user, request))


@api_view(["GET", "PATCH"])
@permission_classes([AllowAny])
def update_installation_preferences(request: Request) -> Response:
    installation = InstallationSettings.load()
    if request.method == "GET":
        return Response(
            {
                "default_language": installation_language(request),
                "default_crowdfunding_tax_rate": float(installation.default_crowdfunding_tax_rate),
            }
        )
    user = cast(User, request.user)
    if not user.is_authenticated or user.role != User.Role.ADMIN:
        return Response(
            {"error": _("Only an administrator can change the installation settings")},
            status=403,
        )
    data = payload(request)
    fields_to_update = ["updated_at"]
    if "default_language" in data:
        language = normalize_language(data.get("default_language"))
        if language is None:
            return Response({"error": _("The default language is not valid")}, status=400)
        installation.default_language = language
        fields_to_update.append("default_language")
        request.finanzr_default_language = language  # type: ignore[attr-defined]
        activate_request_language(request, effective_language(user, request))
    if "default_crowdfunding_tax_rate" in data:
        try:
            tax_rate = percentage_rate(data["default_crowdfunding_tax_rate"])
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        installation.default_crowdfunding_tax_rate = tax_rate
        fields_to_update.append("default_crowdfunding_tax_rate")
    if "default_summary_sources" in data:
        try:
            installation.default_summary_sources = normalize_summary_sources(
                data["default_summary_sources"]
            )
        except ValidationError as exc:
            return Response(
                {
                    "error": exc.messages[0]
                    if exc.messages
                    else _("The selected summary source is not valid")
                },
                status=400,
            )
        fields_to_update.append("default_summary_sources")
    with transaction.atomic():
        installation.save(update_fields=fields_to_update)
    return Response(
        {
            "default_language": installation.default_language,
            "default_crowdfunding_tax_rate": float(installation.default_crowdfunding_tax_rate),
            "language": request.LANGUAGE_CODE,
        }
    )


@api_view(["PATCH"])
def update_account(request: Request) -> Response:
    user = cast(User, request.user)
    data = payload(request)
    if not user.check_password(str(data.get("current_password", ""))):
        return Response({"error": _("The current password is incorrect")}, status=400)
    email = str(data.get("email", "")).strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return Response({"error": _("Enter a valid email address")}, status=400)
    if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
        return Response(
            {"error": _("An account with this email address already exists")}, status=409
        )
    display_name = str(data.get("display_name", user.display_name)).strip()
    if len(display_name) > 120:
        return Response({"error": _("The display name cannot exceed 120 characters")}, status=400)
    user.email = email
    user.display_name = display_name
    user.save(update_fields=("email", "display_name"))
    return Response(user_payload(user, request))


@api_view(["POST"])
def change_password(request: Request) -> Response:
    user = cast(User, request.user)
    data = payload(request)
    if not user.check_password(str(data.get("current_password", ""))):
        return Response({"error": _("The current password is incorrect")}, status=400)
    password = str(data.get("password", ""))
    if password != str(data.get("password_confirmation", "")):
        return Response({"error": _("The new passwords do not match")}, status=400)
    if len(password) < 12:
        return Response(
            {"error": _("The password must be at least 12 characters long")}, status=400
        )
    try:
        validate_password(password, user=user)
    except ValidationError as exc:
        return Response({"error": " ".join(exc.messages)}, status=400)
    user.set_password(password)
    user.save(update_fields=("password",))
    update_session_auth_hash(request._request, user)
    return Response({"ok": True})


@api_view(["PUT"])
def select_workspace(request: Request) -> Response:
    user = cast(User, request.user)
    membership = WorkspaceMembership.objects.filter(
        user=user, workspace_id=str(payload(request).get("workspace_id", ""))
    ).first()
    if not membership:
        return Response({"error": _("Workspace not available")}, status=404)
    request.session["active_workspace_id"] = str(membership.workspace_id)
    return Response(user_payload(user, request))


@api_view(["POST"])
def invite(request: Request) -> Response:
    membership = active_membership(request)
    user = cast(User, request.user)
    if membership.role != WorkspaceMembership.Role.OWNER:
        return Response({"error": _("Only the owner can send invitations")}, status=403)
    data = payload(request)
    role = str(data.get("role", WorkspaceMembership.Role.VIEWER))
    if role not in {WorkspaceMembership.Role.EDITOR, WorkspaceMembership.Role.VIEWER}:
        return Response({"error": _("Invalid role")}, status=400)
    raw_token = secrets.token_urlsafe(32)
    invitation = WorkspaceInvitation.objects.filter(
        workspace=membership.workspace,
        email=str(data.get("email", "")).strip().lower(),
        accepted_at__isnull=True,
    ).first()
    values = {
        "role": role,
        "token_hash": hashlib.sha256(raw_token.encode()).hexdigest(),
        "invited_by": user,
        "expires_at": timezone.now() + timedelta(days=7),
    }
    if invitation:
        for field, value in values.items():
            setattr(invitation, field, value)
        invitation.save()
    else:
        invitation = WorkspaceInvitation.objects.create(
            workspace=membership.workspace,
            email=str(data.get("email", "")).strip().lower(),
            **values,
        )
    return Response(
        {"id": str(invitation.id), "token": raw_token, "expires_at": invitation.expires_at},
        status=201,
    )


@api_view(["POST"])
def accept_invitation(request: Request) -> Response:
    user = cast(User, request.user)
    token_hash = hashlib.sha256(str(payload(request).get("token", "")).encode()).hexdigest()
    invitation = WorkspaceInvitation.objects.filter(
        token_hash=token_hash, accepted_at__isnull=True, expires_at__gt=timezone.now()
    ).first()
    if not invitation or invitation.email.casefold() != user.email.casefold():
        return Response({"error": _("The invitation is invalid or has expired")}, status=400)
    WorkspaceMembership.objects.update_or_create(
        workspace=invitation.workspace, user=user, defaults={"role": invitation.role}
    )
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=("accepted_at",))
    request.session["active_workspace_id"] = str(invitation.workspace_id)
    return Response(user_payload(user, request))


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def password_reset_request(request: Request) -> Response:
    user = User.objects.filter(email__iexact=payload(request).get("email", "")).first()
    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        with translation.override(effective_language(user, request)):
            send_mail(
                _("Reset your Finanzr password"),
                _("Use this link to reset it: %(url)s") % {"url": f"/reset-password/{uid}/{token}"},
                None,
                [user.email],
            )
    return Response({"ok": True})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def password_reset_confirm(request: Request) -> Response:
    data = payload(request)
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(data.get("uid", ""))))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return Response({"error": _("Invalid link")}, status=400)
    if not default_token_generator.check_token(user, str(data.get("token", ""))):
        return Response({"error": _("Invalid link")}, status=400)
    password = str(data.get("password", ""))
    if len(password) < 12:
        return Response(
            {"error": _("The password must be at least 12 characters long")}, status=400
        )
    user.set_password(password)
    user.save(update_fields=("password",))
    return Response({"ok": True})
