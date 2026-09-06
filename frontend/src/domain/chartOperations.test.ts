import { describe, expect, it } from "vitest";
import type { StockOrder, StockSplit } from "../types/api";
import { applyStockSplitChartOperations } from "./chartOperations";

const order = (
  date: string,
  overrides: Partial<StockOrder> = {},
): StockOrder => ({
  id: `operation-${date}`,
  trade_date: date,
  settlement_date: null,
  quantity: 2,
  net_amount: 60,
  fee: 1.5,
  account_id: "00000000-0000-0000-0000-000000000001",
  account_name: "Synthetic broker",
  platform: "Synthetic broker",
  operation_type: "buy",
  cash_flow_type: "none",
  isin: "SYNTHETIC-ISIN",
  asset_name: "Synthetic stock",
  unit_price: 30,
  is_saveback: false,
  currency: "EUR",
  base_currency: "EUR",
  base_unit_price: 30,
  base_net_amount: 60,
  base_fee: 1.5,
  fx_rate_to_base: 1,
  fx_rate_date: date,
  fx_source: "identity",
  market: "",
  provider_operation_type: "Buy",
  ...overrides,
});

const split = (
  id: string,
  instrument_id: string,
  effective_date: string,
  ratio: number,
): StockSplit => ({
  id,
  instrument_id,
  effective_date,
  ratio,
  source: "synthetic-test",
});

describe("applyStockSplitChartOperations", () => {
  it("adjusts only operations strictly before the canonical split date", () => {
    const before = order("2025-02-03");
    const sameDate = order("2025-06-10");
    const after = order("2025-06-11");
    const [adjusted, untouchedSameDate, untouchedAfter] =
      applyStockSplitChartOperations(
        [before, sameDate, after],
        [split("split-1", "instrument-1", "2025-06-10", 3)],
      );

    expect(adjusted).toMatchObject({
      quantity: 6,
      unit_price: 10,
      net_amount: 60,
      fee: 1.5,
      chartAdjustment: {
        id: "stock-splits:split-1",
        label: "Stock splits · 3:1 · 2025-06-10",
      },
    });
    expect(untouchedSameDate).toEqual(sameDate);
    expect(untouchedAfter).toEqual(after);
    expect(before).toMatchObject({ quantity: 2, unit_price: 30 });
    expect(adjusted.quantity * adjusted.unit_price).toBeCloseTo(
      before.quantity * before.unit_price,
    );
  });

  it("compounds multiple later splits deterministically without mutating inputs", () => {
    const before = order("2024-01-01");
    const [adjusted] = applyStockSplitChartOperations(
      [before],
      [
        split("split-2", "instrument-1", "2026-01-01", 2),
        split("split-1", "instrument-1", "2025-01-01", 3),
      ],
    );

    expect(adjusted).toMatchObject({ quantity: 12, unit_price: 5 });
    expect(adjusted.chartAdjustment?.id).toBe("stock-splits:split-1,split-2");
    expect(adjusted.net_amount).toBe(before.net_amount);
    expect(adjusted.fee).toBe(before.fee);
    expect(before).toMatchObject({ quantity: 2, unit_price: 30 });
  });

  it("supports a reverse split while preserving cost, net amount, fee, and inputs", () => {
    const before = order("2024-01-01");
    const [adjusted] = applyStockSplitChartOperations(
      [before],
      [split("split-reverse", "instrument-1", "2025-01-01", 0.5)],
    );

    expect(adjusted).toMatchObject({
      quantity: 1,
      unit_price: 60,
      net_amount: 60,
      fee: 1.5,
      chartAdjustment: {
        id: "stock-splits:split-reverse",
        label: "Stock splits · 0.5:1 · 2025-01-01",
      },
    });
    expect(adjusted.quantity * adjusted.unit_price).toBeCloseTo(60);
    expect(before).toMatchObject({
      quantity: 2,
      unit_price: 30,
      net_amount: 60,
      fee: 1.5,
    });
  });
});
