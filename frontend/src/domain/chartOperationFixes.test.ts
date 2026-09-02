import { describe, expect, it } from "vitest";
import type { StockOrder } from "../types/api";
import { applyAdHocChartOperationFixes } from "./chartOperationFixes";

const bydOrder = (date: string): StockOrder => ({
  id: `byd-${date}`,
  trade_date: date,
  settlement_date: null,
  quantity: 1,
  net_amount: 34.07,
  fee: 0,
  account_id: "00000000-0000-0000-0000-000000000001",
  account_name: "Trade Republic",
  platform: "Trade Republic",
  operation_type: "buy",
  cash_flow_type: "none",
  isin: "CNE100000296",
  asset_name: "BYD",
  unit_price: 34.07,
  is_saveback: false,
  currency: "EUR",
  base_currency: "EUR",
  base_unit_price: 34.07,
  base_net_amount: 34.07,
  base_fee: 0,
  fx_rate_to_base: 1,
  fx_rate_date: date,
  fx_source: "identity",
  market: "",
  provider_operation_type: "Compra",
});

describe("applyAdHocChartOperationFixes", () => {
  it("adjusts only BYD operations before June 10, 2025", () => {
    const february = bydOrder("2025-02-03");
    const juneNinth = bydOrder("2025-06-09");
    const splitDate = bydOrder("2025-06-10");

    const [adjustedFebruary, adjustedJuneNinth, untouchedSplitDate] =
      applyAdHocChartOperationFixes([february, juneNinth, splitDate]);

    expect(adjustedFebruary.quantity).toBe(3);
    expect(adjustedFebruary.unit_price).toBeCloseTo(34.07 / 3);
    expect(adjustedFebruary.chartAdjustment).toEqual({
      id: "byd-pre-june-10-2025-split-3-to-1",
      label: "Split BYD 3:1",
    });
    expect(adjustedJuneNinth.quantity).toBe(3);
    expect(adjustedJuneNinth.unit_price).toBeCloseTo(34.07 / 3);
    expect(untouchedSplitDate).toEqual(splitDate);
    expect(february.quantity).toBe(1);
    expect(february.unit_price).toBe(34.07);
  });

  it("does not modify other assets", () => {
    const other = { ...bydOrder("2025-02-03"), isin: "US67066G1040" };

    expect(applyAdHocChartOperationFixes([other])).toEqual([other]);
  });
});
