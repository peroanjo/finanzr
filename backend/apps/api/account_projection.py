from __future__ import annotations

from typing import Any

from apps.accounts.models import Account
from apps.api.projection import provider_name
from finanzr.importers import importers


def account_row(account: Account) -> dict[str, Any]:
    """Return the native public projection for a traded account.

    ``external_id`` remains storage for imported legacy data, but it is not a
    public identity.  Account primary keys are UUIDs for every traded API
    consumer, including rows created from an older installation.
    """

    importer_name = ""
    if account.importer_slug:
        try:
            importer_name = importers.get(account.importer_slug).display_name
        except KeyError:
            importer_name = account.importer_slug
    row = {
        "id": str(account.id),
        "name": account.name,
        "platform": provider_name(account),
        "type": account.subtype,
        "currency": account.currency,
        "importer_slug": account.importer_slug,
        "importer_name": importer_name,
    }
    return row
