import { computed, ref, type ComputedRef, type Ref } from "vue";
import {
  applyAdHocChartOperationFixes,
  type ChartOperation,
} from "../domain/chartOperationFixes";
import {
  adaptStockPosition,
  type NormalizedPosition,
} from "../domain/investments";
import type { StockInstrument, StockOrder, StockPosition } from "../types/api";

export type StockPositionSortKey =
  | "asset"
  | "ticker"
  | "cost"
  | "quantity"
  | "averagePrice"
  | "currentPrice"
  | "value"
  | "pnl"
  | "return";
export type StockSortDirection = "asc" | "desc";
export type StockPositionAriaSort = "none" | "ascending" | "descending";
export type StockPortfolioSource<T> = Ref<T> | ComputedRef<T>;

export interface UseStocksPortfolioOptions {
  positions: StockPortfolioSource<StockPosition[]>;
  orders: StockPortfolioSource<StockOrder[]>;
  instruments: StockPortfolioSource<StockInstrument[]>;
  selectedIsin: StockPortfolioSource<string>;
  baseCurrency: StockPortfolioSource<string>;
  locale: StockPortfolioSource<string>;
}

export interface UseStocksPortfolio {
  openPositions: ComputedRef<StockPosition[]>;
  topPositions: ComputedRef<StockPosition[]>;
  normalizedTopPositions: ComputedRef<NormalizedPosition[]>;
  totalValue: ComputedRef<number>;
  totalCost: ComputedRef<number>;
  unrealizedPnl: ComputedRef<number>;
  realizedPnl: ComputedRef<number>;
  totalPnl: ComputedRef<number>;
  openReturn: ComputedRef<number>;
  pricedPositions: ComputedRef<number>;
  selectedPosition: ComputedRef<StockPosition | null>;
  selectedOrders: ComputedRef<StockOrder[]>;
  selectedChartOrders: ComputedRef<ChartOperation[]>;
  averagePrice: ComputedRef<number | null>;
  positionSortKey: Ref<StockPositionSortKey>;
  positionSortDirection: Ref<StockSortDirection>;
  sortedPositions: ComputedRef<StockPosition[]>;
  baseAmount: (order: StockOrder) => number;
  basePrice: (order: StockOrder) => number;
  baseFee: (order: StockOrder) => number;
  sortPositions: (key: StockPositionSortKey) => void;
  ariaSort: (key: StockPositionSortKey) => StockPositionAriaSort;
}

export function useStocksPortfolio(
  options: UseStocksPortfolioOptions,
): UseStocksPortfolio {
  const { positions, orders, instruments, selectedIsin, baseCurrency, locale } =
    options;
  const positionSortKey = ref<StockPositionSortKey>("value");
  const positionSortDirection = ref<StockSortDirection>("desc");

  const openPositions = computed(() =>
    [...positions.value]
      .filter((position) => position.titulos > 0)
      .sort((a, b) => (b.valor_actual ?? 0) - (a.valor_actual ?? 0)),
  );
  const topPositions = computed(() => openPositions.value.slice(0, 5));
  const totalValue = computed(() =>
    openPositions.value.reduce(
      (sum, position) => sum + (position.valor_actual ?? 0),
      0,
    ),
  );
  const totalCost = computed(() =>
    openPositions.value.reduce(
      (sum, position) => sum + position.coste_total,
      0,
    ),
  );
  const unrealizedPnl = computed(() =>
    openPositions.value.reduce((sum, position) => sum + (position.pnl ?? 0), 0),
  );
  const realizedPnl = computed(() =>
    positions.value.reduce((sum, position) => sum + position.pnl_realizada, 0),
  );
  const totalPnl = computed(() => unrealizedPnl.value + realizedPnl.value);
  const openReturn = computed(() =>
    totalCost.value ? unrealizedPnl.value / totalCost.value : 0,
  );
  const pricedPositions = computed(
    () =>
      positions.value.filter((position) => position.precio_actual != null)
        .length,
  );
  const normalizedTopPositions = computed(() =>
    topPositions.value.map((position) =>
      adaptStockPosition(
        position,
        instruments.value.find(
          (instrument) => instrument.isin === position.isin,
        ),
        { baseCurrency: baseCurrency.value },
      ),
    ),
  );
  const selectedPosition = computed(
    () =>
      positions.value.find(
        (position) => position.isin === selectedIsin.value,
      ) ?? null,
  );
  const selectedOrders = computed(() =>
    orders.value.filter((order) => order.isin === selectedIsin.value),
  );
  const selectedChartOrders = computed(() =>
    applyAdHocChartOperationFixes(
      selectedOrders.value.map((order) => ({
        ...order,
        // Chart tooltips use reporting-currency values while retaining source fields for the movement table.
        precio_compra: order.precio_base ?? order.precio_compra,
        importe_neto: order.importe_base ?? order.importe_neto,
        comision: order.comision_base ?? order.comision,
      })),
    ),
  );
  const averagePrice = computed(() =>
    selectedPosition.value?.titulos
      ? selectedPosition.value.coste_total / selectedPosition.value.titulos
      : null,
  );
  const sortedPositions = computed(() => {
    const collator = new Intl.Collator(locale.value, { sensitivity: "base" });
    const valueFor = (position: StockPosition): number | string | null => {
      const ticker =
        instruments.value.find(
          (instrument) => instrument.isin === position.isin,
        )?.ticker ?? "";
      if (positionSortKey.value === "asset") return position.nombre;
      if (positionSortKey.value === "ticker") return ticker;
      if (positionSortKey.value === "cost") return position.coste_total;
      if (positionSortKey.value === "quantity") return position.titulos;
      if (positionSortKey.value === "averagePrice")
        return position.titulos ? position.coste_total / position.titulos : 0;
      if (positionSortKey.value === "currentPrice")
        return position.precio_actual;
      if (positionSortKey.value === "value") return position.valor_actual;
      if (positionSortKey.value === "pnl") return position.pnl;
      return position.coste_total
        ? (position.pnl ?? 0) / position.coste_total
        : 0;
    };
    return [...positions.value].sort((a, b) => {
      const left = valueFor(a);
      const right = valueFor(b);
      if (left == null && right == null)
        return collator.compare(a.nombre, b.nombre);
      if (left == null) return 1;
      if (right == null) return -1;
      const comparison =
        typeof left === "string" && typeof right === "string"
          ? collator.compare(left, right)
          : Number(left) - Number(right);
      return comparison === 0
        ? collator.compare(a.nombre, b.nombre)
        : positionSortDirection.value === "asc"
          ? comparison
          : -comparison;
    });
  });

  function baseAmount(order: StockOrder) {
    return order.importe_base ?? order.importe_neto;
  }

  function basePrice(order: StockOrder) {
    return order.precio_base ?? order.precio_compra;
  }

  function baseFee(order: StockOrder) {
    return order.comision_base ?? order.comision;
  }

  function sortPositions(key: StockPositionSortKey) {
    if (positionSortKey.value === key)
      positionSortDirection.value =
        positionSortDirection.value === "asc" ? "desc" : "asc";
    else {
      positionSortKey.value = key;
      positionSortDirection.value = "asc";
    }
  }

  function ariaSort(key: StockPositionSortKey): StockPositionAriaSort {
    return positionSortKey.value === key
      ? positionSortDirection.value === "asc"
        ? "ascending"
        : "descending"
      : "none";
  }

  return {
    openPositions,
    topPositions,
    normalizedTopPositions,
    totalValue,
    totalCost,
    unrealizedPnl,
    realizedPnl,
    totalPnl,
    openReturn,
    pricedPositions,
    selectedPosition,
    selectedOrders,
    selectedChartOrders,
    averagePrice,
    positionSortKey,
    positionSortDirection,
    sortedPositions,
    baseAmount,
    basePrice,
    baseFee,
    sortPositions,
    ariaSort,
  };
}
