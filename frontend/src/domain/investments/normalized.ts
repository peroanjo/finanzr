export type InvestmentKind = "fund" | "stock" | "crypto";

/**
 * Optional workspace currency used when a DTO only exposes source-currency fields.
 * Adapters do not perform FX conversion: numeric DTO fields must already be in
 * the supplied base currency when this option is provided.
 */
export interface InvestmentAdapterOptions {
  baseCurrency?: string;
}

export interface InvestmentCapabilities {
  fees: boolean;
  saveback: boolean;
  splits: boolean;
}

export interface InvestmentMetadata {
  [key: string]: unknown;
}

export interface NormalizedAccount {
  kind: InvestmentKind;
  id: string;
  name: string;
  provider: string;
  type: string | null;
  currency: string;
  metadata: InvestmentMetadata;
  capabilities: InvestmentCapabilities;
}

export interface NormalizedPosition {
  kind: InvestmentKind;
  assetId: string;
  assetKey: string;
  displayIdentifier: string;
  name: string;
  type: string | null;
  subtype: string | null;
  quantity: number;
  cost: number;
  currentPrice: number | null;
  currentValue: number | null;
  unrealizedPnl: number | null;
  realizedPnl: number | null;
  currency: string;
  baseCurrency: string | null;
  metadata: InvestmentMetadata;
  capabilities: InvestmentCapabilities;
}

export interface NormalizedMovement {
  kind: InvestmentKind;
  id: string;
  assetId: string;
  assetKey: string;
  date: string;
  quantity: number;
  price: number;
  cost: number;
  amount: number;
  fee: number | null;
  currency: string;
  baseCurrency: string | null;
  metadata: InvestmentMetadata;
  capabilities: InvestmentCapabilities;
}

export interface NormalizedPerformancePoint {
  date: string;
  value: number;
  invested: number;
  pnl: number;
  pnlPercent: number;
}

export interface NormalizedPerformanceResponse {
  kind: InvestmentKind;
  accountId: string;
  range: string;
  currency: string;
  baseCurrency: string | null;
  data: NormalizedPerformancePoint[];
  metadata: InvestmentMetadata;
  capabilities: InvestmentCapabilities;
}

export interface NormalizedLineChartPoint {
  seriesKind: "line";
  date: string;
  price: number;
}

export interface NormalizedCandlestickChartPoint {
  seriesKind: "candlestick";
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export type NormalizedChartPoint =
  NormalizedLineChartPoint | NormalizedCandlestickChartPoint;

interface NormalizedChartResponseBase {
  kind: InvestmentKind;
  assetId: string;
  assetKey: string;
  ticker: string | null;
  currency: string;
  baseCurrency: string | null;
  range: string;
  metadata: InvestmentMetadata;
  capabilities: InvestmentCapabilities;
}

export interface NormalizedLineChartResponse extends NormalizedChartResponseBase {
  seriesKind: "line";
  data: NormalizedLineChartPoint[];
}

export interface NormalizedCandlestickChartResponse extends NormalizedChartResponseBase {
  seriesKind: "candlestick";
  data: NormalizedCandlestickChartPoint[];
}

export type NormalizedChartResponse =
  NormalizedLineChartResponse | NormalizedCandlestickChartResponse;
