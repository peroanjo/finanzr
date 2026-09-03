"""Portable transaction-scoped locks for logical market-data identities."""

from collections.abc import Iterable

from django.db import connection


def instrument_identifier_lock_keys(scheme: str, value: str, venue: str = "") -> tuple[str, ...]:
    """Return the shared advisory keys for one instrument identity.

    Importers and HTTP CRUD must use the same logical namespace. Canonical
    identifiers use ``instrument:scheme:value`` at the default venue, while
    Yahoo values additionally use ``ticker:value``. Non-default venues retain
    their venue suffix so distinct market identities do not serialize each
    other unnecessarily.
    """

    if not value:
        return ()
    instrument_key = (
        f"instrument:{scheme}:{value}" if not venue else f"instrument:{scheme}:{value}:{venue}"
    )
    if scheme == "yahoo":
        return instrument_key, f"ticker:{value}"
    return (instrument_key,)


def lock_logical_keys(keys: Iterable[str]) -> None:
    """Serialize creation of logical identities on PostgreSQL.

    SQLite and other development databases intentionally remain no-ops. Keys
    are sorted so callers acquiring multiple locks cannot deadlock by order.
    PostgreSQL's stable ``hashtextextended`` supplies a deterministic int64 key.
    """
    if connection.vendor != "postgresql":
        return
    ordered = sorted(set(keys))
    with connection.cursor() as cursor:
        for key in ordered:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                [key],
            )
