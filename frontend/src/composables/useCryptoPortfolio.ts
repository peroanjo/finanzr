import { computed, ref, type ComputedRef, type Ref } from "vue";
import {
  adaptCryptoPosition,
  type NormalizedPosition,
} from "../domain/investments";
import type {
  CryptoInstrument,
  CryptoOrder,
  CryptoPosition,
} from "../types/api";

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
  selectedSymbol: CryptoPortfolioSource<string>;
  baseCurrency: CryptoPortfolioSource<string>;
  locale: CryptoPortfolioSource<string>;
}

export interface UseCryptoPortfolio {
  openPositions: ComputedRef<CryptoPosition[]>;
  topPositions: ComputedRef<CryptoPosition[]>;
  normalizedTopPositions: ComputedRef<NormalizedPosition[]>;
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
  const {
    positions,
    orders,
    instruments,
    selectedSymbol,
    baseCurrency,
    locale,
  } = options;
  const positionSortKey = ref<CryptoPositionSortKey>("value");
  const positionSortDirection = ref<CryptoSortDirection>("desc");

  const openPositions = computed(() =>
    [...positions.value]
      .filter((item) => item.titulos > 0)
      .sort((a, b) => (b.valor_actual ?? 0) - (a.valor_actual ?? 0)),
  );
  const topPositions = computed(() => openPositions.value.slice(0, 5));
  const normalizedTopPositions = computed(() =>
    topPositions.value.map((position) =>
      adaptCryptoPosition(
        position,
        instruments.value.find(
          (instrument) => instrument.symbol === position.symbol,
        ),
        { baseCurrency: baseCurrency.value },
      ),
    ),
  );
  const totalValue = computed(() =>
    openPositions.value.reduce(
      (sum, item) => sum + (item.valor_actual ?? 0),
      0,
    ),
  );
  const totalCost = computed(() =>
    openPositions.value.reduce((sum, item) => sum + item.coste_total, 0),
  );
  const unrealizedPnl = computed(() =>
    openPositions.value.reduce((sum, item) => sum + (item.pnl ?? 0), 0),
  );
  const realizedPnl = computed(() =>
    positions.value.reduce((sum, item) => sum + item.pnl_realizada, 0),
  );
  const totalPnl = computed(() => unrealizedPnl.value + realizedPnl.value);
  const openReturn = computed(() =>
    totalCost.value ? unrealizedPnl.value / totalCost.value : 0,
  );
  const selectedPosition = computed(
    () =>
      positions.value.find((item) => item.symbol === selectedSymbol.value) ??
      null,
  );
  const selectedOrders = computed(() =>
    orders.value.filter((item) => item.symbol === selectedSymbol.value),
  );
  const selectedChartOrders = computed(() =>
    selectedOrders.value.map((order) => ({
      ...order,
      precio_compra: order.precio_base ?? order.precio_compra,
      importe_neto: order.importe_base ?? order.importe_neto,
      comision: order.comision_base ?? order.comision,
    })),
  );
  const averagePrice = computed(() => {
    const position = selectedPosition.value;
    return position && position.titulos > 0
      ? position.coste_total / position.titulos
      : null;
  });
  const pricedPositions = computed(
    () =>
      positions.value.filter((position) => position.precio_actual != null)
        .length,
  );
  const sortedPositions = computed(() => {
    const collator = new Intl.Collator(locale.value, {
      sensitivity: "base",
      numeric: true,
    });
    const valueFor = (position: CryptoPosition): number | string | null => {
      if (positionSortKey.value === "asset") return position.nombre;
      if (positionSortKey.value === "ticker")
        return (
          instruments.value.find((item) => item.symbol === position.symbol)
            ?.ticker ?? position.symbol
        );
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
    return [...positions.value].sort((left, right) => {
      const a = valueFor(left);
      const b = valueFor(right);
      if (a == null && b == null)
        return collator.compare(left.nombre, right.nombre);
      if (a == null) return 1;
      if (b == null) return -1;
      const comparison =
        typeof a === "string" && typeof b === "string"
          ? collator.compare(a, b)
          : Number(a) - Number(b);
      return comparison === 0
        ? collator.compare(left.nombre, right.nombre)
        : positionSortDirection.value === "asc"
          ? comparison
          : -comparison;
    });
  });

  function baseAmount(order: CryptoOrder) {
    return order.importe_base ?? order.importe_neto;
  }

  function basePrice(order: CryptoOrder) {
    return order.precio_base ?? order.precio_compra;
  }

  function baseFee(order: CryptoOrder) {
    return order.comision_base ?? order.comision;
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
