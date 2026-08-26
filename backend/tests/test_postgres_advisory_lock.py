from __future__ import annotations

import threading
from unittest.mock import patch

from apps.accounts.models import Account
from apps.api import views
from apps.market_data.locking import lock_logical_keys
from apps.market_data.models import Instrument, InstrumentIdentifier, WorkspaceInstrument
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection, connections, transaction
from django.test import TransactionTestCase
from rest_framework.test import APIClient


class PostgresAdvisoryLockTests(TransactionTestCase):
    """Exercise transaction-scoped logical locking with independent connections."""

    def test_overlapping_crypto_ticker_locks_are_serialized(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-only concurrency test")

        locked = threading.Event()
        release = threading.Event()
        waiter_completed = threading.Event()
        errors: list[BaseException] = []

        def holder() -> None:
            close_old_connections()
            try:
                with transaction.atomic():
                    lock_logical_keys(("instrument:crypto_symbol:BTC", "ticker:BTC-EUR"))
                    locked.set()
                    if not release.wait(5):
                        raise TimeoutError("lock holder did not receive release signal")
            except BaseException as exc:
                errors.append(exc)
            finally:
                connections.close_all()

        def waiter() -> None:
            close_old_connections()
            try:
                if not locked.wait(5):
                    raise TimeoutError("lock holder did not acquire lock")
                with transaction.atomic():
                    lock_logical_keys(("ticker:BTC-EUR", "instrument:crypto_symbol:BTC"))
                    waiter_completed.set()
            except BaseException as exc:
                errors.append(exc)
            finally:
                connections.close_all()

        first = threading.Thread(target=holder)
        second = threading.Thread(target=waiter)
        first.start()
        self.assertTrue(locked.wait(5))
        second.start()
        self.assertFalse(waiter_completed.wait(0.2))
        release.set()
        self.assertTrue(waiter_completed.wait(5))
        first.join(5)
        second.join(5)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual([], errors)

    def test_yahoo_ticker_acquires_lock_inside_atomic_transaction(self) -> None:
        instrument = Instrument.objects.create(kind=Instrument.Kind.STOCK, name="Ticker lookup")
        InstrumentIdentifier.objects.create(
            instrument=instrument,
            scheme=InstrumentIdentifier.Scheme.ISIN,
            value="LOOKUP-STOCK",
            venue="",
            is_primary=True,
        )
        lock_states: list[bool] = []

        def observe_lock(_keys: object) -> None:
            lock_states.append(connection.in_atomic_block)

        with (
            patch("apps.api.views.search", return_value={"ticker": "LOOKUP.US"}),
            patch("apps.api.views.lock_logical_keys", side_effect=observe_lock),
        ):
            self.assertEqual("LOOKUP.US", views.yahoo_ticker(instrument))

        self.assertEqual([True], lock_states)
        self.assertTrue(
            InstrumentIdentifier.objects.filter(
                instrument=instrument,
                scheme=InstrumentIdentifier.Scheme.YAHOO,
                value="LOOKUP.US",
            ).exists()
        )

    def test_real_ticker_update_races_crypto_import_without_integrity_error(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-only concurrency test")

        workspace = Workspace.objects.create(name="Ticker race", slug="ticker-race")
        user = User.objects.create_user(email="ticker-race@example.test", password="safe-pass")
        WorkspaceMembership.objects.create(
            workspace=workspace, user=user, role=WorkspaceMembership.Role.OWNER
        )
        stock = Instrument.objects.create(kind=Instrument.Kind.STOCK, name="Race stock")
        InstrumentIdentifier.objects.create(
            instrument=stock,
            scheme=InstrumentIdentifier.Scheme.ISIN,
            value="RACE-STOCK",
            venue="",
            is_primary=True,
        )
        InstrumentIdentifier.objects.create(
            instrument=stock,
            scheme=InstrumentIdentifier.Scheme.YAHOO,
            value="RACE-OLD",
            venue="",
            is_primary=True,
        )
        WorkspaceInstrument.objects.create(workspace=workspace, instrument=stock)
        Account.objects.create(
            workspace=workspace,
            name="Kraken race",
            kind=Account.Kind.CRYPTO,
            importer_slug="kraken_spot",
            external_id="legacy:crypto:1",
        )

        barrier = threading.Barrier(2)
        results: dict[str, int] = {}
        errors: list[BaseException] = []
        content = (
            b"txid,pair,time,type,price,cost,fee,vol\n"
            b"race-tx,BTC/EUR,2026-08-25 12:00:00,buy,100000,100,1,0.001\n"
        )

        def update_ticker() -> None:
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '3000ms'")
                barrier.wait(timeout=5)
                client = APIClient()
                client.force_authenticate(user)
                response = client.put(
                    "/api/stocks/RACE-STOCK",
                    {"ticker": "BTC-EUR", "nombre": "Race stock"},
                    format="json",
                )
                results["update"] = response.status_code
            except BaseException as exc:
                errors.append(exc)
            finally:
                connections.close_all()

        def import_crypto() -> None:
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '3000ms'")
                barrier.wait(timeout=5)
                client = APIClient()
                client.force_authenticate(user)
                response = client.post(
                    "/api/crypto-orders/upload-kraken-pro",
                    {
                        "cuenta_id": "1",
                        "file": SimpleUploadedFile("race.csv", content, content_type="text/csv"),
                    },
                )
                results["import"] = response.status_code
            except BaseException as exc:
                errors.append(exc)
            finally:
                connections.close_all()

        first = threading.Thread(target=update_ticker)
        second = threading.Thread(target=import_crypto)
        first.start()
        second.start()
        first.join(8)
        second.join(8)
        self.assertFalse(first.is_alive() or second.is_alive(), "ticker race timed out")
        self.assertEqual([], errors)
        self.assertEqual({"update", "import"}, set(results))
        self.assertEqual({200, 400}, set(results.values()))
        self.assertEqual(
            1,
            InstrumentIdentifier.objects.filter(
                scheme=InstrumentIdentifier.Scheme.YAHOO,
                value="BTC-EUR",
                venue="",
            ).count(),
        )
