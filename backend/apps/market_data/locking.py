"""Portable transaction-scoped locks for logical market-data identities."""

from collections.abc import Iterable

from django.db import connection


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
