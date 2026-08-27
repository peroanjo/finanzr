"""Validated source preferences used by the consolidated net-worth views."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Keep this order stable: it is the API contract and the order used by the
# settings transfer control. New sources should be appended deliberately.
SUMMARY_SOURCE_KEYS = (
    "savings",
    "manual_investments",
    "funds",
    "stocks",
    "crypto",
    "crowdfunding",
    "manual_assets",
)
DEFAULT_SUMMARY_SOURCES = (
    "savings",
    "manual_investments",
    "crowdfunding",
)


def normalize_summary_sources(value: Any) -> list[str]:
    """Validate and canonicalize the public source-key representation.

    An empty list is valid (the overview then represents an intentionally
    empty composition). Ordering follows the catalogue rather than request
    order, so equivalent preferences have one stable JSON representation.
    """

    if not isinstance(value, (list, tuple)):
        raise ValidationError(_("Summary sources must be a list"))
    requested = set()
    for item in value:
        if not isinstance(item, str) or item not in SUMMARY_SOURCE_KEYS:
            raise ValidationError(_("The selected summary source is not valid"))
        requested.add(item)
    return [key for key in SUMMARY_SOURCE_KEYS if key in requested]


def default_summary_sources() -> list[str]:
    return list(DEFAULT_SUMMARY_SOURCES)


def effective_summary_sources(
    user: Any, workspace: Any, installation: Any = None
) -> tuple[list[str], str]:
    """Return a user's effective preference and whether it is personal or inherited."""

    from .models import InstallationSettings, SummaryPreference

    installation = installation or InstallationSettings.load()
    preference = SummaryPreference.objects.filter(user=user, workspace=workspace).first()
    if preference is not None:
        try:
            return normalize_summary_sources(preference.included_sources), "personal"
        except ValidationError:
            try:
                return (
                    normalize_summary_sources(installation.default_summary_sources),
                    "installation",
                )
            except ValidationError:
                return default_summary_sources(), "installation"
    try:
        return normalize_summary_sources(installation.default_summary_sources), "installation"
    except ValidationError:
        return default_summary_sources(), "installation"
