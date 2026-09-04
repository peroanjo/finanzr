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

export interface InvestmentOverviewPosition {
  assetKey: string;
  displayIdentifier: string;
  name: string;
  quantity: number;
  cost: number;
  currentPrice: number | null;
  currentValue: number | null;
  unrealizedPnl: number | null;
  returnPercent: number | null;
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
  date: string;
  price: number;
}

export interface NormalizedCandlestickChartPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
}
