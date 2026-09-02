import type { CryptoOrder, StockOrder } from "../types/api";

export interface ChartAdjustment {
  id: string;
  label: string;
}

export type ChartOperation = (CryptoOrder | StockOrder) & {
  chartAdjustment?: ChartAdjustment;
};

interface AdHocChartOperationFix {
  id: string;
  label: string;
  appliesTo: (operation: ChartOperation) => boolean;
  adjust: (operation: ChartOperation) => ChartOperation;
}

// -----------------------------------------------------------------------------
// Documented ad hoc adjustments
//
// Add only confirmed exceptions that affect historical rendering here.
// These adjustments do not modify persisted transactions or portfolio
// calculations. Each rule must be limited by asset and date and have a test.
// -----------------------------------------------------------------------------
const AD_HOC_CHART_OPERATION_FIXES: AdHocChartOperationFix[] = [
  {
    id: "byd-pre-june-10-2025-split-3-to-1",
    label: "Split BYD 3:1",
    appliesTo: (operation) =>
      "isin" in operation &&
      operation.isin === "CNE100000296" &&
      operation.trade_date.slice(0, 10) < "2025-06-10",
    adjust: (operation) => ({
      ...operation,
      quantity: operation.quantity * 3,
      unit_price: operation.unit_price / 3,
    }),
  },
];

export function applyAdHocChartOperationFixes(
  operations: Array<CryptoOrder | StockOrder>,
): ChartOperation[] {
  return operations.map((source) => {
    let operation: ChartOperation = { ...source };
    for (const fix of AD_HOC_CHART_OPERATION_FIXES) {
      if (operation.chartAdjustment || !fix.appliesTo(operation)) continue;
      operation = {
        ...fix.adjust(operation),
        chartAdjustment: { id: fix.id, label: fix.label },
      };
    }
    return operation;
  });
}
