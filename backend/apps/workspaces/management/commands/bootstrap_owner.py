from __future__ import annotations

import sys
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.core.validators import validate_email
from django.db import transaction

from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership


class Command(BaseCommand):
    help = "Create or reconcile the first owner and workspace for a fresh installation"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--email", required=True)
        parser.add_argument("--password")
        parser.add_argument(
            "--password-stdin",
            action="store_true",
            help="Read the owner password from stdin without exposing it in process arguments",
        )
        parser.add_argument("--workspace", default="home")
        parser.add_argument("--workspace-name", default="My workspace")
        parser.add_argument("--base-currency", default="EUR")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        email = str(options["email"]).strip().lower()
        if options["password_stdin"] and options.get("password"):
            raise CommandError("Use either --password or --password-stdin, not both")
        password = (
            sys.stdin.readline().rstrip("\r\n")
            if options["password_stdin"]
            else str(options.get("password") or "")
        )
        slug = str(options["workspace"]).strip()
        name = str(options["workspace_name"]).strip()
        if not email or not password or not slug or not name:
            raise CommandError("Email, password, workspace slug, and workspace name are required")
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError("Enter a valid owner email address") from exc
        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user is None:
            candidate = User(email=email, display_name=name, role=User.Role.ADMIN)
            try:
                validate_password(password, user=candidate)
            except ValidationError as exc:
                raise CommandError(" ".join(exc.messages)) from exc
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"display_name": name, "role": User.Role.ADMIN},
        )
        if created:
            user.set_password(password)
            user.save(update_fields=("password", "display_name", "role"))
        else:
            update_fields: list[str] = []
            if not user.has_usable_password():
                user.set_password(password)
                update_fields.append("password")
            if user.role != User.Role.ADMIN:
                user.role = User.Role.ADMIN
                update_fields.append("role")
            if update_fields:
                user.save(update_fields=update_fields)
        workspace, _ = Workspace.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "base_currency": str(options["base_currency"]).upper()},
        )
        WorkspaceMembership.objects.update_or_create(
            workspace=workspace,
            user=user,
            defaults={"role": WorkspaceMembership.Role.OWNER},
        )
        self.stdout.write(self.style.SUCCESS(f"Owner bootstrap ready: {email} · {workspace.slug}"))
