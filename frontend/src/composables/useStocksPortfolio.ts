import { computed, ref, type ComputedRef, type Ref } from "vue";
import {
  applyAdHocChartOperationFixes,
  type ChartOperation,
} from "../domain/chartOperationFixes";
import {
  toInvestmentOverviewPosition,
  type InvestmentOverviewPosition,
} from "../domain/investments";
import type { StockInstrument, StockOrder, StockPosition } from "../types/api";
import {
  instrumentById,
  instrumentIdentity,
  instrumentTicker,
} from "../domain/instruments";

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
  selectedInstrumentId: StockPortfolioSource<string>;
  locale: StockPortfolioSource<string>;
}

export interface UseStocksPortfolio {
  openPositions: ComputedRef<StockPosition[]>;
  topPositions: ComputedRef<StockPosition[]>;
  normalizedTopPositions: ComputedRef<InvestmentOverviewPosition[]>;
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
  const { positions, orders, instruments, selectedInstrumentId, locale } =
    options;
  const positionSortKey = ref<StockPositionSortKey>("value");
  const positionSortDirection = ref<StockSortDirection>("desc");

  const openPositions = computed(() =>
    [...positions.value]
      .filter((position) => position.quantity > 0)
      .sort((a, b) => (b.current_value ?? 0) - (a.current_value ?? 0)),
  );
  const topPositions = computed(() => openPositions.value.slice(0, 5));
  const totalValue = computed(() =>
    openPositions.value.reduce(
      (sum, position) => sum + (position.current_value ?? 0),
      0,
    ),
  );
  const totalCost = computed(() =>
    openPositions.value.reduce((sum, position) => sum + position.cost, 0),
  );
  const unrealizedPnl = computed(() =>
    openPositions.value.reduce(
      (sum, position) => sum + (position.unrealized_pnl ?? 0),
      0,
    ),
  );
  const realizedPnl = computed(() =>
    positions.value.reduce(
      (sum, position) => sum + (position.realized_pnl ?? 0),
      0,
    ),
  );
  const totalPnl = computed(() => unrealizedPnl.value + realizedPnl.value);
  const openReturn = computed(() =>
    totalCost.value ? unrealizedPnl.value / totalCost.value : 0,
  );
  const pricedPositions = computed(
    () =>
      positions.value.filter((position) => position.current_price != null)
        .length,
  );
  const normalizedTopPositions = computed(() =>
    topPositions.value.map((position) =>
      toInvestmentOverviewPosition(
        position,
        instrumentById(instruments.value, position.instrument_id),
        null,
      ),
    ),
  );
  const selectedPosition = computed(
    () =>
      positions.value.find(
        (position) => position.instrument_id === selectedInstrumentId.value,
      ) ?? null,
  );
  const selectedIdentity = computed(() =>
    instrumentIdentity(
      instrumentById(instruments.value, selectedInstrumentId.value),
    ),
  );
  const selectedOrders = computed(() =>
    orders.value.filter((order) => order.isin === selectedIdentity.value),
  );
  const selectedChartOrders = computed(() =>
    applyAdHocChartOperationFixes(
      selectedOrders.value.map((order) => ({
        ...order,
        // Chart tooltips use reporting-currency values while retaining source fields for the movement table.
        unit_price: order.base_unit_price ?? order.unit_price,
        net_amount: order.base_net_amount ?? order.net_amount,
        fee: order.base_fee ?? order.fee,
      })),
    ),
  );
  const averagePrice = computed(() =>
    selectedPosition.value?.quantity
      ? selectedPosition.value.cost / selectedPosition.value.quantity
      : null,
  );
  const sortedPositions = computed(() => {
    const collator = new Intl.Collator(locale.value, { sensitivity: "base" });
    const valueFor = (position: StockPosition): number | string | null => {
      const instrument = instrumentById(
        instruments.value,
        position.instrument_id,
      );
      const ticker =
        instrumentTicker(instrument) || instrumentIdentity(instrument);
      if (positionSortKey.value === "asset") return position.name;
      if (positionSortKey.value === "ticker") return ticker;
      if (positionSortKey.value === "cost") return position.cost;
      if (positionSortKey.value === "quantity") return position.quantity;
      if (positionSortKey.value === "averagePrice")
        return position.quantity ? position.cost / position.quantity : 0;
      if (positionSortKey.value === "currentPrice")
        return position.current_price;
      if (positionSortKey.value === "value") return position.current_value;
      if (positionSortKey.value === "pnl") return position.unrealized_pnl;
      return position.cost ? (position.unrealized_pnl ?? 0) / position.cost : 0;
    };
    return [...positions.value].sort((a, b) => {
      const left = valueFor(a);
      const right = valueFor(b);
      if (left == null && right == null)
        return collator.compare(a.name, b.name);
      if (left == null) return 1;
      if (right == null) return -1;
      const comparison =
        typeof left === "string" && typeof right === "string"
          ? collator.compare(left, right)
          : Number(left) - Number(right);
      return comparison === 0
        ? collator.compare(a.name, b.name)
        : positionSortDirection.value === "asc"
          ? comparison
          : -comparison;
    });
  });

  function baseAmount(order: StockOrder) {
    return order.base_net_amount ?? order.net_amount;
  }

  function basePrice(order: StockOrder) {
    return order.base_unit_price ?? order.unit_price;
  }

  function baseFee(order: StockOrder) {
    return order.base_fee ?? order.fee;
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
