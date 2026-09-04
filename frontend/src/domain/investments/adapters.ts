import type {
  CryptoChartResponse,
  FundChartResponse,
  NativePosition,
  StockChartResponse,
} from "../../types/api";
import {
  instrumentIdentity,
  instrumentName,
  type NativeInstrument,
} from "../instruments";
import type {
  InvestmentKind,
  NormalizedCandlestickChartPoint,
  NormalizedLineChartPoint,
  InvestmentOverviewPosition,
} from "./normalized";

type LooseRecord = Record<string, unknown>;

function record(value: unknown): LooseRecord {
  return value !== null && typeof value === "object"
    ? (value as LooseRecord)
    : {};
}

function text(value: unknown, fallback = ""): string {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return fallback;
}

function number(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function nullableNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function assetKey(kind: InvestmentKind, assetId: string): string {
  return `${kind}:${assetId}`;
}

export function toInvestmentOverviewPosition(
  position: NativePosition,
  instrument?: NativeInstrument,
  returnPercent?: number | null,
): InvestmentOverviewPosition {
  const item = record(position);
  const assetId = text(item.instrument_id, instrument?.id ?? "");
  return {
    assetKey: assetKey(position.kind, assetId),
    displayIdentifier: instrumentIdentity(instrument),
    name: text(item.name, instrumentName(instrument, assetId)),
    quantity: number(item.quantity),
    cost: number(item.cost),
    currentPrice: nullableNumber(item.current_price),
    currentValue: nullableNumber(item.current_value),
    unrealizedPnl: nullableNumber(item.unrealized_pnl),
    returnPercent: nullableNumber(returnPercent),
  };
}

function candlestickPoint(
  point: unknown,
): NormalizedCandlestickChartPoint | null {
  const item = record(point);
  const open = nullableNumber(item.open);
  const high = nullableNumber(item.high);
  const low = nullableNumber(item.low);
  const close = nullableNumber(item.close);
  if (open === null || high === null || low === null || close === null)
    return null;
  return {
    date: text(item.date),
    open,
    high,
    low,
    close,
  };
}

function adaptMarketChart(
  response: StockChartResponse | CryptoChartResponse,
): NormalizedCandlestickChartPoint[] {
  const data = record(response).data;
  return Array.isArray(data)
    ? data
        .map((point) => candlestickPoint(point))
        .filter(
          (point): point is NormalizedCandlestickChartPoint => point !== null,
        )
    : [];
}

export function adaptStockChart(
  response: StockChartResponse,
): NormalizedCandlestickChartPoint[] {
  return adaptMarketChart(response);
}

export function adaptCryptoChart(
  response: CryptoChartResponse,
): NormalizedCandlestickChartPoint[] {
  return adaptMarketChart(response);
}

export function adaptFundChart(
  response: FundChartResponse,
): NormalizedLineChartPoint[] {
  const data = record(response).data;
  return Array.isArray(data)
    ? data.map((point) => {
        const value = record(point);
        return {
          date: text(value.date),
          price: number(value.close),
        };
      })
    : [];
}
