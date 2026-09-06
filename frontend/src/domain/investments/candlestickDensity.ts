import type { NormalizedCandlestickChartPoint } from "./normalized";

interface CandlestickDensityOptions {
  targetCount: number;
  maximumCount: number;
}

/**
 * Combine dense market series into readable OHLC candles.
 *
 * Sparse and already aggregated series are returned untouched. Dense series
 * retain the first open, highest high, lowest low and last close in each
 * consecutive bucket. Counting source samples instead of elapsed time keeps
 * density stable for both exchange sessions and continuously traded crypto.
 */
export function condenseCandlesticks(
  points: NormalizedCandlestickChartPoint[],
  { targetCount, maximumCount }: CandlestickDensityOptions,
): NormalizedCandlestickChartPoint[] {
  if (points.length <= maximumCount || targetCount < 1) return points;

  const bucketSize = Math.max(1, Math.ceil(points.length / targetCount));
  const condensed: NormalizedCandlestickChartPoint[] = [];

  for (const [index, point] of points.entries()) {
    const bucket = Math.floor(index / bucketSize);
    const current = condensed.at(-1);

    if (!current || bucket === condensed.length) {
      condensed.push({ ...point });
      continue;
    }

    current.high = Math.max(current.high, point.high);
    current.low = Math.min(current.low, point.low);
    current.close = point.close;
    current.date = point.date;
  }

  return condensed;
}
