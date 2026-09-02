import type {
  CryptoAccount,
  CryptoChartResponse,
  CryptoInstrument,
  CryptoOrder,
  CryptoPerformanceResponse,
  CryptoPosition,
  FundAccount,
  FundChartResponse,
  FundInstrument,
  FundOrder,
  FundPerformanceResponse,
  FundPosition,
  StockAccount,
  StockChartResponse,
  StockInstrument,
  StockOrder,
  StockPerformanceResponse,
  StockPosition,
} from "../../types/api";
import type {
  InvestmentCapabilities,
  InvestmentAdapterOptions,
  InvestmentKind,
  InvestmentMetadata,
  NormalizedAccount,
  NormalizedCandlestickChartPoint,
  NormalizedCandlestickChartResponse,
  NormalizedLineChartResponse,
  NormalizedMovement,
  NormalizedPerformanceResponse,
  NormalizedPosition,
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

function boolean(value: unknown): boolean {
  return value === true || value === "true" || value === 1;
}

function currency(...values: unknown[]): string {
  const value = values.find(
    (candidate) => typeof candidate === "string" && candidate.trim(),
  );
  return text(value, "EUR").toUpperCase();
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

function accountMetadata(
  account: LooseRecord,
  source: string,
): InvestmentMetadata {
  return {
    source,
    importerSlug: text(account.importer_slug) || null,
    importerName: text(account.importer_name) || null,
  };
}

function movementMetadata(
  item: LooseRecord,
  source: string,
  originalCurrencyCode: string | null,
): InvestmentMetadata {
  return {
    source,
    operationType: text(item.tipo_operacion) || null,
    accountId: item.cuenta_id ?? null,
    accountName: text(item.cuenta_nombre) || null,
    provider: text(item.plataforma) || null,
    settlementDate: text(item.fecha_liquidacion) || null,
    originalCurrency: originalCurrencyCode,
  };
}

export function adaptFundAccount(account: FundAccount): NormalizedAccount {
  const item = record(account);
  return {
    kind: "fund",
    id: text(item.id),
    name: text(item.name, "Unnamed fund account"),
    provider: text(item.platform, "Unknown provider"),
    type: text(item.type) || null,
    currency: currency(item.currency),
    metadata: accountMetadata(item, "fund-account"),
    capabilities: capabilities(FUND_CAPABILITIES),
  };
}

export function adaptStockAccount(account: StockAccount): NormalizedAccount {
  const item = record(account);
  return {
    kind: "stock",
    id: text(item.id),
    name: text(item.name, "Unnamed stock account"),
    provider: text(item.platform, "Unknown provider"),
    type: text(item.type) || null,
    currency: currency(item.currency),
    metadata: accountMetadata(item, "stock-account"),
    capabilities: capabilities(STOCK_CAPABILITIES),
  };
}

export function adaptCryptoAccount(account: CryptoAccount): NormalizedAccount {
  const item = record(account);
  return {
    kind: "crypto",
    id: text(item.id),
    name: text(item.name, "Unnamed crypto account"),
    provider: text(item.platform, "Unknown provider"),
    type: text(item.type) || null,
    currency: currency(item.currency),
    metadata: accountMetadata(item, "crypto-account"),
    capabilities: capabilities(CRYPTO_CAPABILITIES),
  };
}

export function adaptFundPosition(
  position: FundPosition,
  instrument?: FundInstrument,
  options?: InvestmentAdapterOptions,
): NormalizedPosition {
  const item = record(position);
  const assetId = text(item.isin, instrument?.isin ?? "");
  const currencies = currencyDetails(
    options,
    item.moneda_base,
    item.moneda,
    instrument?.moneda,
  );
  return {
    kind: "fund",
    assetId,
    assetKey: assetKey("fund", assetId),
    name: text(item.nombre, instrument?.nombre ?? assetId),
    type: text(item.tipo, instrument?.tipo ?? "") || null,
    subtype: text(item.subtipo, instrument?.subtipo ?? "") || null,
    quantity: number(item.participaciones),
    cost: number(item.total_invertido),
    currentPrice: nullableNumber(item.precio_actual),
    currentValue: nullableNumber(item.valor_actual),
    unrealizedPnl: nullableNumber(item.pnl),
    realizedPnl: nullableNumber(item.pnl_realizada),
    currency: currencies.currency,
    baseCurrency: currencies.baseCurrency,
    metadata: {
      source: "fund-position",
      ticker: text(instrument?.ticker) || null,
      returnPercent: nullableNumber(item.pnl_pct),
      originalCurrency: currencies.originalCurrency,
      currencySource: currencies.source,
    },
    capabilities: capabilities(FUND_CAPABILITIES),
  };
}

export function adaptStockPosition(
  position: StockPosition,
  instrument?: StockInstrument,
  options?: InvestmentAdapterOptions,
): NormalizedPosition {
  const item = record(position);
  const assetId = text(item.isin, instrument?.isin ?? "");
  const currencies = currencyDetails(
    options,
    item.moneda_base,
    item.moneda,
    instrument?.moneda,
  );
  return {
    kind: "stock",
    assetId,
    assetKey: assetKey("stock", assetId),
    name: text(item.nombre, instrument?.nombre ?? assetId),
    type: null,
    subtype: null,
    quantity: number(item.titulos),
    cost: number(item.coste_total),
    currentPrice: nullableNumber(item.precio_actual),
    currentValue: nullableNumber(item.valor_actual),
    unrealizedPnl: nullableNumber(item.pnl),
    realizedPnl: number(item.pnl_realizada),
    currency: currencies.currency,
    baseCurrency: currencies.baseCurrency,
    metadata: {
      source: "stock-position",
      ticker: text(instrument?.ticker) || null,
      isin: assetId,
      originalCurrency: currencies.originalCurrency,
      currencySource: currencies.source,
    },
    capabilities: capabilities(STOCK_CAPABILITIES),
  };
}

export function adaptCryptoPosition(
  position: CryptoPosition,
  instrument?: CryptoInstrument,
  options?: InvestmentAdapterOptions,
): NormalizedPosition {
  const item = record(position);
  const assetId = text(item.symbol, instrument?.symbol ?? "");
  const currencies = currencyDetails(
    options,
    item.moneda_base,
    item.moneda,
    instrument?.moneda,
  );
  return {
    kind: "crypto",
    assetId,
    assetKey: assetKey("crypto", assetId),
    name: text(item.nombre, instrument?.nombre ?? assetId),
    type: "crypto",
    subtype: null,
    quantity: number(item.titulos),
    cost: number(item.coste_total),
    currentPrice: nullableNumber(item.precio_actual),
    currentValue: nullableNumber(item.valor_actual),
    unrealizedPnl: nullableNumber(item.pnl),
    realizedPnl: number(item.pnl_realizada),
    currency: currencies.currency,
    baseCurrency: currencies.baseCurrency,
    metadata: {
      source: "crypto-position",
      ticker: text(instrument?.ticker) || null,
      symbol: assetId,
      originalCurrency: currencies.originalCurrency,
      currencySource: currencies.source,
    },
    capabilities: capabilities(CRYPTO_CAPABILITIES),
  };
}

export function adaptFundMovement(
  item: FundOrder,
  options?: InvestmentAdapterOptions,
): NormalizedMovement {
  const value = record(item);
  const assetId = text(value.isin);
  const currencies = currencyDetails(
    options,
    value.moneda_base,
    value.moneda,
    value.divisa,
  );
  const amount = number(value.importe_base, number(value.importe_neto));
  return {
    kind: "fund",
    id: text(value.operacion_id),
    assetId,
    assetKey: assetKey("fund", assetId),
    date: text(value.fecha_operacion),
    quantity: number(value.titulos),
    price: number(value.precio_base, number(value.precio_neto)),
    cost: amount,
    amount,
    fee: null,
    currency: currencies.currency,
    baseCurrency: currencies.baseCurrency,
    metadata: {
      ...movementMetadata(value, "fund-order", currencies.originalCurrency),
      currencySource: currencies.source,
    },
    capabilities: capabilities(FUND_CAPABILITIES),
  };
}

export function adaptStockMovement(
  item: StockOrder,
  options?: InvestmentAdapterOptions,
): NormalizedMovement {
  const value = record(item);
  const assetId = text(value.isin);
  const currencies = currencyDetails(options, value.moneda_base, value.moneda);
  const amount = number(value.importe_base, number(value.importe_neto));
  const saveback = boolean(value.es_saveback);
  return {
    kind: "stock",
    id: text(value.operacion_id),
    assetId,
    assetKey: assetKey("stock", assetId),
    date: text(value.fecha_operacion),
    quantity: number(value.titulos),
    price: number(value.precio_base, number(value.precio_compra)),
    cost: amount,
    amount,
    fee: nullableNumber(value.comision_base) ?? nullableNumber(value.comision),
    currency: currencies.currency,
    baseCurrency: currencies.baseCurrency,
    metadata: {
      ...movementMetadata(value, "stock-order", currencies.originalCurrency),
      saveback,
      splitAdjusted: boolean(value.split_adjusted),
      currencySource: currencies.source,
    },
    capabilities: capabilities(STOCK_CAPABILITIES),
  };
}

export function adaptCryptoMovement(
  item: CryptoOrder,
  options?: InvestmentAdapterOptions,
): NormalizedMovement {
  const value = record(item);
  const assetId = text(value.symbol);
  const currencies = currencyDetails(options, value.moneda_base, value.moneda);
  const amount = number(value.importe_base, number(value.importe_neto));
  return {
    kind: "crypto",
    id: text(value.operacion_id),
    assetId,
    assetKey: assetKey("crypto", assetId),
    date: text(value.fecha_operacion),
    quantity: number(value.titulos),
    price: number(value.precio_base, number(value.precio_compra)),
    cost: amount,
    amount,
    fee: nullableNumber(value.comision_base) ?? nullableNumber(value.comision),
    currency: currencies.currency,
    baseCurrency: currencies.baseCurrency,
    metadata: {
      ...movementMetadata(value, "crypto-order", currencies.originalCurrency),
      currencySource: currencies.source,
    },
    capabilities: capabilities(CRYPTO_CAPABILITIES),
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
    seriesKind: "candlestick",
    date: text(item.fecha),
    open,
    high,
    low,
    close,
  };
}

function adaptMarketChart(
  kind: InvestmentKind,
  response: StockChartResponse | CryptoChartResponse,
  options?: InvestmentAdapterOptions,
): NormalizedCandlestickChartResponse {
  const item = record(response);
  const assetId = kind === "stock" ? text(item.isin) : text(item.symbol);
  const currencies = currencyDetails(options, item.moneda_base, item.moneda);
  const chart: NormalizedCandlestickChartResponse = {
    kind,
    assetId,
    assetKey: assetKey(kind, assetId),
    ticker: text(item.ticker) || null,
    currency: currencies.currency,
    baseCurrency: currencies.baseCurrency,
    range: text(item.range),
    seriesKind: "candlestick",
    data: Array.isArray(item.data)
      ? item.data
          .map((point) => candlestickPoint(point))
          .filter(
            (point): point is NormalizedCandlestickChartPoint => point !== null,
          )
      : [],
    metadata: {
      source: `${kind}-chart`,
      originalCurrency: currencies.originalCurrency,
      currencySource: currencies.source,
    },
    capabilities: capabilities(
      kind === "stock" ? STOCK_CAPABILITIES : CRYPTO_CAPABILITIES,
    ),
  };
  return chart;
}

export function adaptStockChart(
  response: StockChartResponse,
  options?: InvestmentAdapterOptions,
): NormalizedCandlestickChartResponse {
  return adaptMarketChart("stock", response, options);
}

export function adaptCryptoChart(
  response: CryptoChartResponse,
  options?: InvestmentAdapterOptions,
): NormalizedCandlestickChartResponse {
  return adaptMarketChart("crypto", response, options);
}

export function adaptFundChart(
  response: FundChartResponse,
  options?: InvestmentAdapterOptions,
): NormalizedLineChartResponse {
  const item = record(response);
  const assetId = text(item.isin);
  const currencies = currencyDetails(options, item.moneda_base, item.moneda);
  const chart: NormalizedLineChartResponse = {
    kind: "fund",
    assetId,
    assetKey: assetKey("fund", assetId),
    ticker: text(item.ticker) || null,
    currency: currencies.currency,
    baseCurrency: currencies.baseCurrency,
    range: text(item.range),
    seriesKind: "line",
    data: Array.isArray(item.data)
      ? item.data.map((point) => {
          const value = record(point);
          return {
            seriesKind: "line" as const,
            date: text(value.fecha),
            // Prefer an explicitly converted value when the DTO exposes it.
            price: number(value.precio_base, number(value.precio)),
          };
        })
      : [],
    metadata: {
      source: "fund-chart",
      originalCurrency: currencies.originalCurrency,
      currencySource: currencies.source,
    },
    capabilities: capabilities(FUND_CAPABILITIES),
  };
  return chart;
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
