export type InvestmentKind = "fund" | "stock" | "crypto";

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
