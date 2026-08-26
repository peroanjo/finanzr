from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel, UUIDModel

if TYPE_CHECKING:
    from apps.users.models import User


class Workspace(TimeStampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80, unique=True)
    base_currency = models.CharField(max_length=3, default="EUR")
    timezone = models.CharField(max_length=64, default="Europe/Madrid")
    archived_at = models.DateTimeField(null=True, blank=True)
    members: models.ManyToManyField[User, WorkspaceMembership] = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="WorkspaceMembership",
        related_name="workspaces",
    )

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def has_currency_snapshots(self) -> bool:
        """Return whether changing the reporting currency would mix monetary bases."""
        return (
            self.accounts.filter(
                Q(snapshots__isnull=False) | Q(transactions__isnull=False)
            ).exists()
            or self.manual_assets.exists()
            or self.real_estate_investments.exists()
            or self.budget_lines.exists()
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.base_currency = str(self.base_currency).strip().upper()
        if self.pk:
            previous = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("base_currency", flat=True)
                .first()
            )
            if previous and previous != self.base_currency and self.has_currency_snapshots():
                raise ValidationError(
                    {
                        "base_currency": _(
                            "The reporting currency cannot be changed after financial data exists"
                        )
                    }
                )
        super().save(*args, **kwargs)


class WorkspaceMembership(UUIDModel):
    class Role(models.TextChoices):
        OWNER = "owner", _("Owner")
        EDITOR = "editor", _("Editor")
        VIEWER = "viewer", _("Viewer")

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "user"), name="workspace_membership_unique"
            )
        ]
        ordering = ("workspace", "user")

    def __str__(self) -> str:
        return f"{self.user} · {self.workspace} ({self.role})"


class WorkspaceInvitation(UUIDModel):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(
        max_length=10,
        choices=WorkspaceMembership.Role.choices,
        default=WorkspaceMembership.Role.VIEWER,
    )
    token_hash = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="workspace_invitations_sent",
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "email"),
                condition=Q(accepted_at__isnull=True),
                name="pending_workspace_invitation_unique",
            )
        ]

    def __str__(self) -> str:
        return f"{self.email} · {self.workspace}"
