from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.api.context import workspace
from apps.api.instrument_queries import instrument_rows
from apps.api.market_data_projection import (
    instrument_row,
)
from apps.api.permissions import forbidden_if_readonly
from apps.api.request_data import payload
from apps.api.schemas import (
    normalize_instrument_identifier_value,
    validate_instrument_identifiers,
)
from apps.market_data.fx import (
    CurrencyConversionError,
    normalize_currency,
)
from apps.market_data.locking import instrument_identifier_lock_keys, lock_logical_keys
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    WorkspaceInstrument,
)
from apps.workspaces.models import Workspace


def instruments(request: Request, kind: str) -> Response:
    return Response(instrument_rows(request, kind))


@api_view(["GET"])
def funds(request: Request) -> Response:
    return instruments(request, Instrument.Kind.FUND)


def _instrument_request_serializer(kind: str, data: dict[str, Any], *, update: bool) -> Any:
    """Validate a native instrument body and contextualize identifier schemes."""
    from apps.api.schemas import InstrumentRequestSerializer, InstrumentUpdateRequestSerializer

    return (InstrumentUpdateRequestSerializer if update else InstrumentRequestSerializer)(
        data=data, context={"instrument_kind": kind}
    )


def _instrument_metadata(item: Instrument, values: dict[str, Any]) -> None:
    metadata = dict(item.metadata or {})
    for field, legacy_field in (("asset_class", "tipo"), ("subtype", "subtipo")):
        if field not in values:
            continue
        value = values[field]
        metadata.pop(legacy_field, None)
        if value in (None, ""):
            metadata.pop(field, None)
        else:
            metadata[field] = str(value).strip()
    item.metadata = metadata


def _instrument_is_shared(item: Instrument, current_workspace: Workspace) -> bool:
    return bool(
        item.workspace_links.exclude(workspace=current_workspace).exists()
        or item.transactions.exclude(account__workspace=current_workspace).exists()
    )


@transaction.atomic
def create_instrument(request: Request, kind: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    serializer = _instrument_request_serializer(kind, payload(request), update=False)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    data = cast(dict[str, Any], serializer.validated_data)
    identifiers = [
        {
            **item,
            "value": normalize_instrument_identifier_value(item["scheme"], item["value"]),
        }
        for item in data["identifiers"]
    ]
    try:
        quote_currency = normalize_currency(data.get("quote_currency") or "EUR")
    except CurrencyConversionError as exc:
        return Response({"error": str(exc)}, status=400)
    lock_keys = [
        key
        for item in identifiers
        for key in instrument_identifier_lock_keys(item["scheme"], item["value"], item["venue"])
    ]
    lock_logical_keys(lock_keys)
    identities = [
        identity
        for item in identifiers
        for identity in [
            InstrumentIdentifier.objects.select_related("instrument")
            .select_for_update()
            .filter(scheme=item["scheme"], value=item["value"], venue=item["venue"])
            .first()
        ]
        if identity is not None
    ]
    current_workspace = workspace(request)
    instruments_by_id = {identity.instrument_id: identity.instrument for identity in identities}
    if any(item.kind != kind for item in instruments_by_id.values()):
        return Response(
            {"error": _("The identifier already belongs to another asset type")}, status=400
        )
    if len(instruments_by_id) > 1:
        return Response(
            {"error": _("Instrument identifiers belong to different assets")}, status=400
        )
    item = next(iter(instruments_by_id.values()), None)
    if item is not None:
        item = Instrument.objects.select_for_update().get(pk=item.pk)
        # The identity query above used a row lock; reload the relation after
        # locking the parent so all subsequent validation sees one snapshot.
        identities = list(
            InstrumentIdentifier.objects.select_for_update().filter(instrument=item).order_by("id")
        )
        instruments_by_id = {identity.instrument_id: item for identity in identities}
    if item is not None and (
        item.workspace_links.filter(workspace=current_workspace).exists()
        or item.transactions.filter(account__workspace=current_workspace).exists()
    ):
        return Response({"error": _("The asset is already configured")}, status=400)
    shared = item is not None and _instrument_is_shared(item, current_workspace)
    if shared:
        assert item is not None
        known = set(item.identifiers.values_list("scheme", "value", "venue"))
        submitted = {(row["scheme"], row["value"], row["venue"]) for row in identifiers}
        if not submitted <= known:
            return Response({"error": _("The shared catalog asset cannot be changed")}, status=409)
    # Any new identifier must not already belong to another catalog item.  The
    # database constraint remains the final race-safe guard.
    for row in identifiers:
        owner = (
            InstrumentIdentifier.objects.select_for_update()
            .filter(scheme=row["scheme"], value=row["value"], venue=row["venue"])
            .exclude(instrument=item)
            .exists()
        )
        if owner:
            return Response(
                {"error": _("The identifier already belongs to another asset")}, status=400
            )
    existing_rows = list(item.identifiers.all()) if item is not None else []
    existing_keys = {(row.scheme, row.value, row.venue) for row in existing_rows}
    existing_slots = {(row.scheme, row.venue): row for row in existing_rows}
    if item is not None:
        try:
            validate_instrument_identifiers(
                {"identifiers": [_identifier_payload(row) for row in existing_rows]},
                kind=kind,
                require_identity=True,
                allow_fund_blank_yahoo=True,
            )
        except serializers.ValidationError as exc:
            return Response(exc.detail, status=400)
    if item is not None and not shared:
        for row in identifiers:
            existing = existing_slots.get((row["scheme"], row["venue"]))
            if existing is not None and existing.value != row["value"]:
                return Response(
                    {"error": _("An existing instrument identifier cannot be changed")},
                    status=400,
                )
            if (
                row["is_primary"]
                and existing is None
                and any(
                    current.scheme == row["scheme"] and current.is_primary
                    for current in existing_rows
                )
            ):
                return Response(
                    {"error": _("Only one primary identifier per scheme is supported")},
                    status=400,
                )
    if item is None:
        item = Instrument.objects.create(
            kind=kind,
            name=data["name"].strip(),
            quote_currency=quote_currency,
            is_active=data.get("is_active", True),
        )
        _instrument_metadata(item, data)
        item.save(update_fields=("metadata", "updated_at"))
    else:
        # A catalog entry may be linked by another workspace.  Its canonical
        # fields and importer identities are intentionally immutable here.
        if not shared:
            item.name = data["name"].strip()
            item.quote_currency = quote_currency
            item.is_active = data.get("is_active", item.is_active)
            _instrument_metadata(item, data)
            item.save()
    assert item is not None
    if not shared:
        for row in identifiers:
            key = (row["scheme"], row["value"], row["venue"])
            if key not in existing_keys:
                InstrumentIdentifier.objects.create(instrument=item, **row)
    WorkspaceInstrument.objects.get_or_create(workspace=current_workspace, instrument=item)
    cache.clear()
    return Response(instrument_row(item), status=201)


@api_view(["GET", "POST"])
def stocks(request: Request) -> Response:
    if request.method == "POST":
        return create_instrument(request, Instrument.Kind.STOCK)
    return instruments(request, Instrument.Kind.STOCK)


@api_view(["GET", "POST"])
def cryptos(request: Request) -> Response:
    if request.method == "POST":
        return create_instrument(request, Instrument.Kind.CRYPTO)
    return instruments(request, Instrument.Kind.CRYPTO)


def _identifier_payload(item: InstrumentIdentifier) -> dict[str, Any]:
    return {
        "scheme": item.scheme,
        "value": item.value,
        "venue": item.venue,
        "is_primary": item.is_primary,
    }


def _effective_instrument_identifiers(
    kind: str,
    existing: list[InstrumentIdentifier],
    submitted: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]] | None, Response | None]:
    """Merge a native identifier patch and validate the complete resulting set."""

    existing_rows = [_identifier_payload(item) for item in existing]
    try:
        existing_rows = validate_instrument_identifiers(
            {"identifiers": existing_rows},
            kind=kind,
            require_identity=True,
            allow_fund_blank_yahoo=True,
        )["identifiers"]
    except serializers.ValidationError as exc:
        return None, Response(exc.detail, status=400)

    by_slot = {(row["scheme"], row["venue"]): row for row in existing_rows}
    for row in submitted:
        slot = (row["scheme"], row["venue"])
        if not row["value"]:
            # A blank Yahoo value is an explicit native clear operation for a
            # fund. It targets only this venue and never removes ISIN or other
            # importer identities.
            by_slot.pop(slot, None)
            continue
        current = by_slot.get(slot)
        if current is not None and current["value"] != row["value"]:
            if row["scheme"] != InstrumentIdentifier.Scheme.YAHOO:
                return None, Response(
                    {"error": _("The canonical instrument identifier cannot be changed")},
                    status=400,
                )
        by_slot[slot] = row

    try:
        effective = validate_instrument_identifiers(
            {"identifiers": list(by_slot.values())},
            kind=kind,
            require_identity=True,
            allow_fund_blank_yahoo=True,
        )["identifiers"]
    except serializers.ValidationError as exc:
        return None, Response(exc.detail, status=400)
    return effective, None


@transaction.atomic
def update_instrument(request: Request, instrument_id: UUID, kind: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    current_workspace = workspace(request)
    visible_id = (
        Instrument.objects.filter(pk=instrument_id, kind=kind)
        .filter(
            Q(workspace_links__workspace=current_workspace)
            | Q(transactions__account__workspace=current_workspace)
        )
        .values_list("pk", flat=True)
        .first()
    )
    if visible_id is None:
        raise Http404
    item = get_object_or_404(Instrument.objects.get_queryset(), pk=visible_id, kind=kind)
    serializer = _instrument_request_serializer(kind, payload(request), update=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    data = cast(dict[str, Any], serializer.validated_data)
    if _instrument_is_shared(item, current_workspace):
        return Response(
            {"error": _("This catalog asset is configured in another workspace")}, status=409
        )
    identifiers = list(data.get("identifiers", []))
    existing_identifiers = list(item.identifiers.all())
    effective_identifiers, validation_error = _effective_instrument_identifiers(
        kind, existing_identifiers, identifiers
    )
    if validation_error is not None:
        return validation_error
    assert effective_identifiers is not None
    quote_currency: str | None = None
    if "quote_currency" in data:
        try:
            quote_currency = normalize_currency(data["quote_currency"])
        except CurrencyConversionError as exc:
            return Response({"error": str(exc)}, status=400)

    lock_keys = [
        key
        for row in [
            *[_identifier_payload(item) for item in existing_identifiers],
            *identifiers,
        ]
        for key in instrument_identifier_lock_keys(row["scheme"], row["value"], row["venue"])
    ]
    lock_logical_keys(lock_keys)

    # Advisory keys are acquired before any row lock. Re-read and validate the
    # locked snapshot so a concurrent importer or editor cannot invalidate the
    # no-write validation above.
    item = Instrument.objects.select_for_update().get(pk=visible_id, kind=kind)
    locked_identifiers = list(
        InstrumentIdentifier.objects.select_for_update().filter(instrument=item).order_by("id")
    )
    if _instrument_is_shared(item, current_workspace):
        return Response(
            {"error": _("This catalog asset is configured in another workspace")}, status=409
        )
    effective_identifiers, validation_error = _effective_instrument_identifiers(
        kind, locked_identifiers, identifiers
    )
    if validation_error is not None:
        return validation_error
    assert effective_identifiers is not None
    for row in effective_identifiers:
        if (
            InstrumentIdentifier.objects.select_for_update()
            .filter(scheme=row["scheme"], value=row["value"], venue=row["venue"])
            .exclude(instrument=item)
            .exists()
        ):
            return Response(
                {"error": _("The identifier already belongs to another asset")}, status=400
            )

    # All checks have completed. From this point on, writes cannot fail due to
    # request validation or identity conflicts.
    existing_by_slot = {(row.scheme, row.venue): row for row in locked_identifiers}
    desired_by_slot = {(row["scheme"], row["venue"]): row for row in effective_identifiers}
    cleared_slots = {(row["scheme"], row["venue"]) for row in identifiers if not row["value"]}
    for slot, existing in existing_by_slot.items():
        desired = desired_by_slot.get(slot)
        if slot in cleared_slots:
            existing.delete()
        elif desired is not None and existing.is_primary and not desired["is_primary"]:
            existing.is_primary = False
            existing.save(update_fields=("is_primary",))
    for slot, row in desired_by_slot.items():
        existing_row = existing_by_slot.get(slot)
        if existing_row is None:
            InstrumentIdentifier.objects.create(instrument=item, **row)
        elif existing_row.value != row["value"] or existing_row.is_primary != row["is_primary"]:
            existing_row.value = row["value"]
            existing_row.is_primary = row["is_primary"]
            existing_row.save(update_fields=("value", "is_primary"))
    if "name" in data:
        item.name = str(data["name"]).strip()
    if quote_currency is not None:
        item.quote_currency = quote_currency
    if "is_active" in data:
        item.is_active = data["is_active"]
    _instrument_metadata(item, data)
    item.save()
    item.refresh_from_db()
    cache.clear()
    return Response(instrument_row(item))


@api_view(["PUT"])
def fund_detail(request: Request, instrument_id: UUID) -> Response:
    return update_instrument(request, instrument_id, Instrument.Kind.FUND)


@api_view(["PUT"])
def stock_detail(request: Request, instrument_id: UUID) -> Response:
    return update_instrument(request, instrument_id, Instrument.Kind.STOCK)


@api_view(["PUT"])
def crypto_detail(request: Request, instrument_id: UUID) -> Response:
    return update_instrument(request, instrument_id, Instrument.Kind.CRYPTO)
