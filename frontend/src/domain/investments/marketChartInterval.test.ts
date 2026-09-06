import { describe, expect, it } from "vitest";
import {
  isMarketChartIntervalAvailable,
  marketChartInterval,
  marketChartIntervalForRange,
} from "./marketChartInterval";

describe("marketChartInterval", () => {
  it.each([
    ["2026-08-31", "2026-09-06", "15m"],
    ["2026-08-07", "2026-09-06", "1h"],
    ["2026-06-06", "2026-09-06", "4h"],
    ["2026-03-06", "2026-09-06", "1d"],
    ["2024-09-06", "2026-09-06", "1wk"],
    ["2020-09-06", "2026-09-06", "1mo"],
  ])("uses %s through %s at %s", (start, end, expected) => {
    expect(marketChartInterval(start, end)).toBe(expected);
  });

  it("uses TradingView-like automatic resolutions for preset ranges", () => {
    expect(marketChartIntervalForRange("6m")).toBe("1d");
    expect(marketChartIntervalForRange("1y")).toBe("1wk");
    expect(marketChartIntervalForRange("2y")).toBe("1wk");
  });

  it("guards provider lookback limits for intraday selections", () => {
    expect(isMarketChartIntervalAvailable("15m", 60)).toBe(true);
    expect(isMarketChartIntervalAvailable("15m", 61)).toBe(false);
    expect(isMarketChartIntervalAvailable("1h", 366)).toBe(true);
    expect(isMarketChartIntervalAvailable("1h", 731)).toBe(false);
    expect(isMarketChartIntervalAvailable("1d", 10_000)).toBe(true);
  });
});
