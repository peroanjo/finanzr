export type MarketChartInterval = "15m" | "1h" | "4h" | "1d" | "1wk" | "1mo";
export type CandleIntervalSelection = "auto" | MarketChartInterval;

const DAY_MS = 86_400_000;

export const MARKET_CHART_INTERVALS: readonly MarketChartInterval[] = [
  "15m",
  "1h",
  "4h",
  "1d",
  "1wk",
  "1mo",
];

/** Yahoo only exposes intraday history for bounded lookback windows. */
const maximumLookbackDays: Partial<Record<MarketChartInterval, number>> = {
  "15m": 60,
  "1h": 730,
  "4h": 730,
};

export function marketChartDays(start: string, end: string) {
  const startTimestamp = Date.parse(start);
  const endTimestamp = Date.parse(end);
  return Math.max(
    1,
    Math.ceil(Math.abs(endTimestamp - startTimestamp) / DAY_MS),
  );
}

export function isMarketChartIntervalAvailable(
  interval: MarketChartInterval,
  days: number,
) {
  return days <= (maximumLookbackDays[interval] ?? Number.POSITIVE_INFINITY);
}

export function marketChartIntervalForRange(
  range: "6m" | "1y" | "2y",
): MarketChartInterval {
  if (range === "6m") return "1d";
  return "1wk";
}

/** Choose a provider interval fine enough to render roughly 100 OHLC candles. */
export function marketChartInterval(
  start: string,
  end: string,
): MarketChartInterval {
  const days = marketChartDays(start, end);

  if (days <= 7) return "15m";
  if (days <= 45) return "1h";
  if (days <= 120) return "4h";
  if (days <= 400) return "1d";
  if (days <= 1500) return "1wk";
  return "1mo";
}
