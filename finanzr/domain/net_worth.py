"""Net worth calculations and monthly history."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .money import ZERO, as_float, cents, decimal
from .real_estate import live_capital_for_month, new_capital

Record = Mapping[str, Any]


def current_total(records: Iterable[Record], value_field: str) -> float:
    """Sum the most recent record for each account."""
    latest: dict[Any, Record] = {}
    for record in records:
        account_id = record.get("cuenta_id")
        previous = latest.get(account_id)
        if previous is None or str(record.get("fecha", "")) > str(previous.get("fecha", "")):
            latest[account_id] = record
    return as_float(sum((decimal(record.get(value_field)) for record in latest.values()), ZERO))


def _monthly_totals(records: list[Record], value_field: str) -> dict[str, Any]:
    """Return each account's latest monthly balance, carried across category months."""
    latest_in_month: dict[tuple[str, Any], Record] = {}
    months: set[str] = set()
    for record in records:
        month = str(record.get("fecha") or "")[:7]
        if not month:
            continue
        months.add(month)
        key = (month, record.get("cuenta_id"))
        previous = latest_in_month.get(key)
        if previous is None or str(record.get("fecha", "")) > str(previous.get("fecha", "")):
            latest_in_month[key] = record

    balances: dict[Any, Any] = {}
    totals: dict[str, Any] = {}
    for month in sorted(months):
        for (record_month, account_id), record in latest_in_month.items():
            if record_month == month:
                balances[account_id] = decimal(record.get(value_field))
        totals[month] = sum(balances.values(), ZERO)
    return totals


def _fill_calendar(totals: dict[str, Any], months: list[str]) -> None:
    last = ZERO
    for month in months:
        if month in totals:
            last = totals[month]
        else:
            totals[month] = last


def monthly_history(
    savings: Iterable[Record],
    investments: Iterable[Record],
    real_estate: Iterable[Record],
    source_series: Mapping[str, Iterable[Record]] | None = None,
) -> list[dict[str, Any]]:
    """Build the complete monthly history with carried-forward balances.

    ``source_series`` contains optional summary sources as records with
    ``fecha``, ``cuenta_id`` and ``valor``. These internal projection records
    are independent from the public real-estate contract.
    """
    savings_records = list(savings)
    investment_records = list(investments)
    projects = list(real_estate)
    extras = {key: list(records) for key, records in (source_series or {}).items()}

    savings_by_month = _monthly_totals(savings_records, "saldo")
    investments_by_month = _monthly_totals(investment_records, "valor")

    savings_interest: dict[str, Any] = {}
    savings_contributions: dict[str, Any] = {}
    for record in savings_records:
        month = str(record.get("fecha") or "")[:7]
        if month:
            savings_interest[month] = savings_interest.get(month, ZERO) + decimal(
                record.get("intereses")
            )
            savings_contributions[month] = savings_contributions.get(month, ZERO) + decimal(
                record.get("aporte")
            )

    investment_contributions: dict[str, Any] = {}
    for record in investment_records:
        month = str(record.get("fecha") or "")[:7]
        if month:
            investment_contributions[month] = investment_contributions.get(month, ZERO) + decimal(
                record.get("aporte")
            )

    real_estate_contributions: dict[str, Any] = {}
    real_estate_months: set[str] = set()
    for project in projects:
        month = str(project.get("start_date") or "")[:7]
        if month:
            real_estate_months.add(month)
            real_estate_contributions[month] = real_estate_contributions.get(month, ZERO) + decimal(
                new_capital(project)
            )
        # A crowdfunding-only composition still needs a calendar even when
        # its only records are project cash flows.  Returns are intentionally
        # included as calendar points too: live_capital_for_month applies the
        # same dated movements when calculating the balance for that month.
        movements = project.get("movements")
        if isinstance(movements, list):
            for movement in movements:
                if isinstance(movement, Mapping):
                    movement_month = str(movement.get("effective_date") or "")[:7]
                    if movement_month:
                        real_estate_months.add(movement_month)

    extra_by_month: dict[str, dict[str, Any]] = {}
    extra_contributions: dict[str, dict[str, Any]] = {}
    for source_key, records in extras.items():
        totals = _monthly_totals(records, "valor")
        contributions_by_month: dict[str, Any] = {}
        for record in records:
            month = str(record.get("fecha") or "")[:7]
            if month:
                contributions_by_month[month] = contributions_by_month.get(month, ZERO) + decimal(
                    record.get("aporte")
                )
        extra_by_month[source_key] = totals
        extra_contributions[source_key] = contributions_by_month

    months = sorted(
        set(savings_by_month)
        | set(investments_by_month)
        | real_estate_months
        | {month for totals in extra_by_month.values() for month in totals}
    )
    _fill_calendar(savings_by_month, months)
    _fill_calendar(investments_by_month, months)
    for totals in extra_by_month.values():
        _fill_calendar(totals, months)

    result: list[dict[str, Any]] = []
    for month in months:
        savings_total = savings_by_month.get(month, ZERO)
        balances_total = investments_by_month.get(month, ZERO)
        property_total = sum(
            (decimal(live_capital_for_month(project, month)) for project in projects), ZERO
        )
        balance_contributions = investment_contributions.get(month, ZERO)
        extra_totals = {
            source_key: totals.get(month, ZERO) for source_key, totals in extra_by_month.items()
        }
        extra_total = sum(extra_totals.values(), ZERO)
        investment_total = balances_total + property_total + extra_total
        contributions = balance_contributions + real_estate_contributions.get(month, ZERO)
        extra_source_contributions = {
            source_key: contributions_by_month.get(month, ZERO)
            for source_key, contributions_by_month in extra_contributions.items()
        }
        contributions += sum(extra_source_contributions.values(), ZERO)
        source_totals = {
            "savings": as_float(cents(savings_total)),
            "manual_investments": as_float(cents(balances_total)),
            "crowdfunding": as_float(cents(property_total)),
            **{source_key: as_float(cents(value)) for source_key, value in extra_totals.items()},
        }
        source_contributions = {
            "savings": as_float(cents(savings_contributions.get(month, ZERO))),
            "manual_investments": as_float(cents(balance_contributions)),
            "crowdfunding": as_float(cents(real_estate_contributions.get(month, ZERO))),
            **{
                source_key: as_float(cents(value))
                for source_key, value in extra_source_contributions.items()
            },
        }
        result.append(
            {
                "fecha": month,
                "ahorro": as_float(cents(savings_total)),
                "ahorro_intereses": as_float(cents(savings_interest.get(month, ZERO))),
                "balances": as_float(cents(balances_total)),
                "balance_aportes": as_float(cents(balance_contributions)),
                "inversiones": as_float(cents(investment_total)),
                "total": as_float(cents(savings_total + investment_total)),
                "inv_aportes": as_float(cents(contributions)),
                "source_totals": source_totals,
                "source_contributions": source_contributions,
            }
        )
    return result
