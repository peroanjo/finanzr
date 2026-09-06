import type { CryptoOrder, StockOrder, StockSplit } from "../types/api";

export interface ChartAdjustment {
  id: string;
  label: string;
}

export type ChartOperation = (CryptoOrder | StockOrder) & {
  chartAdjustment?: ChartAdjustment;
};

function splitLabel(split: StockSplit) {
  return `${split.ratio}:1 · ${split.effective_date}`;
}

/** Apply workspace-canonical stock splits to chart-only operation copies. */
export function applyStockSplitChartOperations(
  operations: StockOrder[],
  splits: StockSplit[],
): ChartOperation[] {
  const orderedSplits = [...splits].sort(
    (left, right) =>
      left.effective_date.localeCompare(right.effective_date) ||
      left.id.localeCompare(right.id),
  );
  return operations.map((source) => {
    const appliedSplits = orderedSplits.filter(
      (split) => source.trade_date.slice(0, 10) < split.effective_date,
    );
    if (!appliedSplits.length) return { ...source };

    let operation: StockOrder = { ...source };
    for (const split of appliedSplits) {
      operation = {
        ...operation,
        quantity: operation.quantity * split.ratio,
        unit_price: operation.unit_price / split.ratio,
      };
    }
    return {
      ...operation,
      chartAdjustment: {
        id: `stock-splits:${appliedSplits.map((split) => split.id).join(",")}`,
        label: `Stock splits · ${appliedSplits.map(splitLabel).join(" · ")}`,
      },
    };
  });
}
