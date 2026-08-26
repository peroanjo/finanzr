from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from apps.accounts.models import AccountSnapshot
from apps.market_data.fx import CurrencyConversionError, normalize_currency
from apps.market_data.models import Instrument
from apps.transactions.currency import conversion_snapshot
from apps.transactions.models import Transaction


class Command(BaseCommand):
    help = "Backfill historical transaction conversions into the workspace base currency"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--workspace", help="Workspace slug to process")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Resolve rates without writing transaction snapshots",
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Re-resolve transactions that already have a conversion snapshot",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        queryset = Transaction.objects.select_related("account__workspace", "instrument")
        workspace_slug = str(options.get("workspace") or "").strip()
        if workspace_slug:
            queryset = queryset.filter(account__workspace__slug=workspace_slug)
        pending = queryset.order_by("trade_date")
        if not options["refresh"]:
            pending = pending.filter(base_net_amount__isnull=True)
        processed = 0
        failed = 0
        for item in pending:
            trade_date = item.trade_date
            conversion = None
            try:
                conversion = conversion_snapshot(
                    account=item.account,
                    currency=normalize_currency(item.currency),
                    trade_date=trade_date,
                    settlement_date=item.settlement_date,
                    unit_price=item.unit_price or Decimal("0"),
                    net_amount=item.net_amount,
                    fee=item.fee,
                )
            except CurrencyConversionError as exc:
                failed += 1
                self.stderr.write(f"{item.external_id or item.pk}: {exc}")
                continue
            if not options["dry_run"]:
                with transaction.atomic():
                    Transaction.objects.filter(pk=item.pk).update(**conversion)
                    if item.instrument.quote_currency != normalize_currency(item.currency):
                        Instrument.objects.filter(pk=item.instrument_id).update(
                            quote_currency=normalize_currency(item.currency)
                        )
            processed += 1
        if failed:
            raise CommandError(
                f"Resolved {processed} transaction(s), but {failed} still need an exchange rate"
            )
        snapshots = AccountSnapshot.objects.select_related("account__workspace")
        if not options["refresh"]:
            snapshots = snapshots.filter(base_value__isnull=True)
        if workspace_slug:
            snapshots = snapshots.filter(account__workspace__slug=workspace_slug)
        snapshot_count = 0
        for snapshot in snapshots.order_by("date"):
            try:
                conversion = conversion_snapshot(
                    account=snapshot.account,
                    currency=normalize_currency(snapshot.currency or snapshot.account.currency),
                    trade_date=snapshot.date,
                    settlement_date=None,
                    unit_price=snapshot.value,
                    net_amount=snapshot.value,
                    fee=snapshot.earnings,
                )
            except CurrencyConversionError as exc:
                failed += 1
                self.stderr.write(f"snapshot {snapshot.pk}: {exc}")
                continue
            if not options["dry_run"]:
                with transaction.atomic():
                    AccountSnapshot.objects.filter(pk=snapshot.pk).update(
                        currency=normalize_currency(snapshot.currency or snapshot.account.currency),
                        base_currency=conversion["base_currency"],
                        base_value=conversion["base_unit_price"],
                        base_contribution=snapshot.contribution * conversion["fx_rate_to_base"],
                        base_earnings=snapshot.earnings * conversion["fx_rate_to_base"],
                        fx_rate_to_base=conversion["fx_rate_to_base"],
                        fx_rate_date=conversion["fx_rate_date"],
                        fx_source=conversion["fx_source"],
                    )
            snapshot_count += 1
        if failed:
            raise CommandError(
                f"Resolved {processed} transaction(s) and {snapshot_count} snapshot(s), "
                f"but {failed} conversion(s) failed"
            )
        mode = " (dry run)" if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Resolved {processed} transaction(s) and {snapshot_count} snapshot(s){mode}."
            )
        )
