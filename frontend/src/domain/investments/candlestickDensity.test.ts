import { describe, expect, it } from "vitest";
import type { NormalizedCandlestickChartPoint } from "./normalized";
import { condenseCandlesticks } from "./candlestickDensity";

function dailyPoints(count: number): NormalizedCandlestickChartPoint[] {
  const start = Date.UTC(2025, 0, 1);
  return Array.from({ length: count }, (_, index) => {
    const value = 100 + index;
    return {
      date: new Date(start + index * 86_400_000).toISOString().slice(0, 10),
      open: value,
      high: value + 3,
      low: value - 2,
      close: value + 1,
    };
  });
}

describe("condenseCandlesticks", () => {
  it("preserves an already readable weekly-sized series", () => {
    const points = dailyPoints(104);

    expect(
      condenseCandlesticks(points, { targetCount: 104, maximumCount: 120 }),
    ).toBe(points);
  });

  it("condenses six daily months into two-day OHLC candles", () => {
    const points = dailyPoints(180);
    const condensed = condenseCandlesticks(points, {
      targetCount: 104,
      maximumCount: 120,
    });

    expect(condensed).toHaveLength(90);
    expect(condensed[0]).toEqual({
      date: "2025-01-02",
      open: 100,
      high: 104,
      low: 98,
      close: 102,
    });
  });

  it("condenses one daily year into four-day OHLC candles", () => {
    const condensed = condenseCandlesticks(dailyPoints(365), {
      targetCount: 104,
      maximumCount: 120,
    });

    expect(condensed).toHaveLength(92);
    expect(condensed.at(-1)?.date).toBe("2025-12-31");
  });
});
