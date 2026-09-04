import { computed, ref, type ComputedRef, type Ref } from "vue";
import {
  toInvestmentOverviewPosition,
  type InvestmentOverviewPosition,
} from "../domain/investments";
import type {
  CryptoInstrument,
  CryptoOrder,
  CryptoPosition,
} from "../types/api";
import {
  instrumentById,
  instrumentIdentity,
  instrumentTicker,
} from "../domain/instruments";

export type CryptoPositionSortKey =
  | "asset"
  | "ticker"
  | "cost"
  | "quantity"
  | "averagePrice"
  | "currentPrice"
  | "value"
  | "pnl"
  | "return";
export type CryptoSortDirection = "asc" | "desc";
export type CryptoPositionAriaSort = "none" | "ascending" | "descending";
export type CryptoPortfolioSource<T> = Ref<T> | ComputedRef<T>;

export interface UseCryptoPortfolioOptions {
  positions: CryptoPortfolioSource<CryptoPosition[]>;
  orders: CryptoPortfolioSource<CryptoOrder[]>;
  instruments: CryptoPortfolioSource<CryptoInstrument[]>;
  selectedInstrumentId: CryptoPortfolioSource<string>;
  locale: CryptoPortfolioSource<string>;
}

export interface UseCryptoPortfolio {
  openPositions: ComputedRef<CryptoPosition[]>;
  topPositions: ComputedRef<CryptoPosition[]>;
  normalizedTopPositions: ComputedRef<InvestmentOverviewPosition[]>;
  totalValue: ComputedRef<number>;
  totalCost: ComputedRef<number>;
  unrealizedPnl: ComputedRef<number>;
  realizedPnl: ComputedRef<number>;
  totalPnl: ComputedRef<number>;
  openReturn: ComputedRef<number>;
  pricedPositions: ComputedRef<number>;
  selectedPosition: ComputedRef<CryptoPosition | null>;
  selectedOrders: ComputedRef<CryptoOrder[]>;
  selectedChartOrders: ComputedRef<CryptoOrder[]>;
  averagePrice: ComputedRef<number | null>;
  positionSortKey: Ref<CryptoPositionSortKey>;
  positionSortDirection: Ref<CryptoSortDirection>;
  sortedPositions: ComputedRef<CryptoPosition[]>;
  baseAmount: (order: CryptoOrder) => number;
  basePrice: (order: CryptoOrder) => number;
  baseFee: (order: CryptoOrder) => number;
  sortPositions: (key: CryptoPositionSortKey) => void;
  ariaSort: (key: CryptoPositionSortKey) => CryptoPositionAriaSort;
}

export function useCryptoPortfolio(
  options: UseCryptoPortfolioOptions,
): UseCryptoPortfolio {
  const { positions, orders, instruments, selectedInstrumentId, locale } =
    options;
  const positionSortKey = ref<CryptoPositionSortKey>("value");
  const positionSortDirection = ref<CryptoSortDirection>("desc");

  const openPositions = computed(() =>
    [...positions.value]
      .filter((item) => item.quantity > 0)
      .sort((a, b) => (b.current_value ?? 0) - (a.current_value ?? 0)),
  );
  const topPositions = computed(() => openPositions.value.slice(0, 5));
  const normalizedTopPositions = computed(() =>
    topPositions.value.map((position) =>
      toInvestmentOverviewPosition(
        position,
        instrumentById(instruments.value, position.instrument_id),
        null,
      ),
    ),
  );
  const totalValue = computed(() =>
    openPositions.value.reduce(
      (sum, item) => sum + (item.current_value ?? 0),
      0,
    ),
  );
  const totalCost = computed(() =>
    openPositions.value.reduce((sum, item) => sum + item.cost, 0),
  );
  const unrealizedPnl = computed(() =>
    openPositions.value.reduce(
      (sum, item) => sum + (item.unrealized_pnl ?? 0),
      0,
    ),
  );
  const realizedPnl = computed(() =>
    positions.value.reduce((sum, item) => sum + (item.realized_pnl ?? 0), 0),
  );
  const totalPnl = computed(() => unrealizedPnl.value + realizedPnl.value);
  const openReturn = computed(() =>
    totalCost.value ? unrealizedPnl.value / totalCost.value : 0,
  );
  const selectedPosition = computed(
    () =>
      positions.value.find(
        (item) => item.instrument_id === selectedInstrumentId.value,
      ) ?? null,
  );
  const selectedIdentity = computed(() =>
    instrumentIdentity(
      instrumentById(instruments.value, selectedInstrumentId.value),
    ),
  );
  const selectedOrders = computed(() =>
    orders.value.filter((item) => item.symbol === selectedIdentity.value),
  );
  const selectedChartOrders = computed(() =>
    selectedOrders.value.map((order) => ({
      ...order,
      unit_price: order.base_unit_price ?? order.unit_price,
      net_amount: order.base_net_amount ?? order.net_amount,
      fee: order.base_fee ?? order.fee,
    })),
  );
  const averagePrice = computed(() => {
    const position = selectedPosition.value;
    return position && position.quantity > 0
      ? position.cost / position.quantity
      : null;
  });
  const pricedPositions = computed(
    () =>
      positions.value.filter((position) => position.current_price != null)
        .length,
  );
  const sortedPositions = computed(() => {
    const collator = new Intl.Collator(locale.value, {
      sensitivity: "base",
      numeric: true,
    });
    const valueFor = (position: CryptoPosition): number | string | null => {
      if (positionSortKey.value === "asset") return position.name;
      if (positionSortKey.value === "ticker") {
        const instrument = instrumentById(
          instruments.value,
          position.instrument_id,
        );
        return instrumentTicker(instrument) || instrumentIdentity(instrument);
      }
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
    return [...positions.value].sort((left, right) => {
      const a = valueFor(left);
      const b = valueFor(right);
      if (a == null && b == null)
        return collator.compare(left.name, right.name);
      if (a == null) return 1;
      if (b == null) return -1;
      const comparison =
        typeof a === "string" && typeof b === "string"
          ? collator.compare(a, b)
          : Number(a) - Number(b);
      return comparison === 0
        ? collator.compare(left.name, right.name)
        : positionSortDirection.value === "asc"
          ? comparison
          : -comparison;
    });
  });

  function baseAmount(order: CryptoOrder) {
    return order.base_net_amount ?? order.net_amount;
  }

  function basePrice(order: CryptoOrder) {
    return order.base_unit_price ?? order.unit_price;
  }

  function baseFee(order: CryptoOrder) {
    return order.base_fee ?? order.fee;
  }

  function sortPositions(key: CryptoPositionSortKey) {
    if (positionSortKey.value === key)
      positionSortDirection.value =
        positionSortDirection.value === "asc" ? "desc" : "asc";
    else {
      positionSortKey.value = key;
      positionSortDirection.value = "asc";
    }
  }

  function ariaSort(key: CryptoPositionSortKey): CryptoPositionAriaSort {
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
