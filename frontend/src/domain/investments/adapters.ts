import type {
  CryptoChartResponse,
  CryptoPerformanceResponse,
  FundChartResponse,
  FundPerformanceResponse,
  NativePosition,
  StockChartResponse,
  StockPerformanceResponse,
} from "../../types/api";
import {
  instrumentIdentity,
  instrumentName,
  type NativeInstrument,
} from "../instruments";
import type {
  InvestmentCapabilities,
  InvestmentAdapterOptions,
  InvestmentKind,
  NormalizedCandlestickChartPoint,
  NormalizedLineChartPoint,
  NormalizedPerformanceResponse,
  InvestmentOverviewPosition,
} from "./normalized";

type LooseRecord = Record<string, unknown>;

const FUND_CAPABILITIES: InvestmentCapabilities = {
  fees: false,
  saveback: false,
  splits: false,
};
const STOCK_CAPABILITIES: InvestmentCapabilities = {
  fees: true,
  saveback: true,
  splits: true,
};
const CRYPTO_CAPABILITIES: InvestmentCapabilities = {
  fees: true,
  saveback: false,
  splits: false,
};

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

function reportedCurrency(value: unknown): string | null {
  return typeof value === "string" && value.trim()
    ? value.trim().toUpperCase()
    : null;
}

function currencyDetails(
  options: InvestmentAdapterOptions | undefined,
  reportedBase: unknown,
  ...reportedOriginal: unknown[]
) {
  const explicitBase = reportedCurrency(options?.baseCurrency);
  const dtoBase = reportedCurrency(reportedBase);
  const originalCode =
    reportedOriginal
      .map(reportedCurrency)
      .find((value): value is string => Boolean(value)) ?? null;
  // Without an explicit/base DTO currency, retain the reported source code and
  // leave baseCurrency null instead of silently presenting values as EUR.
  const effective = dtoBase ?? explicitBase ?? originalCode ?? "UNSPECIFIED";
  const base = dtoBase ?? explicitBase;
  return {
    currency: effective,
    baseCurrency: base,
    originalCurrency:
      originalCode && originalCode !== effective ? originalCode : null,
    source: dtoBase
      ? "dto-base"
      : explicitBase
        ? "option"
        : originalCode
          ? "reported"
          : "unspecified",
  };
}

function assetKey(kind: InvestmentKind, assetId: string): string {
  return `${kind}:${assetId}`;
}

function capabilities(value: InvestmentCapabilities): InvestmentCapabilities {
  return { ...value };
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

export function adaptFundPerformance(
  response: FundPerformanceResponse,
  options?: InvestmentAdapterOptions,
): NormalizedPerformanceResponse {
  const item = record(response);
  const currencies = currencyDetails(options, item.moneda_base, item.moneda);
  return {
    kind: "fund",
    accountId: text(item.account_id),
    range: text(item.range),
    currency: currencies.currency,
    baseCurrency: currencies.baseCurrency,
    data: Array.isArray(item.data)
      ? item.data.map((point) => {
          const value = record(point);
          return {
            date: text(value.fecha),
            value: number(value.valor),
            invested: number(value.invertido),
            pnl: number(value.pnl),
            pnlPercent: number(value.pnl_pct),
          };
        })
      : [],
    metadata: {
      source: "fund-performance",
      accountId: text(item.account_id),
      originalCurrency: currencies.originalCurrency,
      currencySource: currencies.source,
    },
    capabilities: capabilities(FUND_CAPABILITIES),
  };
}

export function adaptStockPerformance(
  response: StockPerformanceResponse,
  options?: InvestmentAdapterOptions,
): NormalizedPerformanceResponse {
  const item = record(response);
  const currencies = currencyDetails(options, item.moneda_base, item.moneda);
  return {
    kind: "stock",
    accountId: text(item.account_id),
    range: text(item.range),
    currency: currencies.currency,
    baseCurrency: currencies.baseCurrency,
    data: Array.isArray(item.data)
      ? item.data.map((point) => {
          const value = record(point);
          return {
            date: text(value.fecha),
            value: number(value.valor),
            invested: number(value.invertido),
            pnl: number(value.pnl),
            pnlPercent: number(value.pnl_pct),
          };
        })
      : [],
    metadata: {
      source: "stock-performance",
      accountId: text(item.account_id),
      originalCurrency: currencies.originalCurrency,
      currencySource: currencies.source,
    },
    capabilities: capabilities(STOCK_CAPABILITIES),
  };
}

export function adaptCryptoPerformance(
  response: CryptoPerformanceResponse,
  options?: InvestmentAdapterOptions,
): NormalizedPerformanceResponse {
  const item = record(response);
  const currencies = currencyDetails(options, item.moneda_base, item.moneda);
  return {
    kind: "crypto",
    accountId: text(item.account_id),
    range: text(item.range),
    currency: currencies.currency,
    baseCurrency: currencies.baseCurrency,
    data: Array.isArray(item.data)
      ? item.data.map((point) => {
          const value = record(point);
          return {
            date: text(value.fecha),
            value: number(value.valor),
            invested: number(value.invertido),
            pnl: number(value.pnl),
            pnlPercent: number(value.pnl_pct),
          };
        })
      : [],
    metadata: {
      source: "crypto-performance",
      accountId: text(item.account_id),
      originalCurrency: currencies.originalCurrency,
      currencySource: currencies.source,
    },
    capabilities: capabilities(CRYPTO_CAPABILITIES),
  };
}
