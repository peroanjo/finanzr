import { computed, ref, type ComputedRef, type Ref } from "vue";
import type {
  FundInstrument,
  FundOrder,
  FundPosition,
  FundPrice,
} from "../types/api";
import {
  adaptFundPosition,
  type NormalizedPosition,
} from "../domain/investments";

export type FundPositionSortKey =
  | "fund"
  | "type"
  | "contributed"
  | "shares"
  | "averagePrice"
  | "currentPrice"
  | "value"
  | "pnl"
  | "return";

export type FundSortDirection = "asc" | "desc";
export type FundPositionAriaSort = "none" | "ascending" | "descending";

export interface UseFundsPortfolioOptions {
  positions: Ref<FundPosition[]>;
  orders: Ref<FundOrder[]>;
  instruments: Ref<FundInstrument[]>;
  prices: Ref<FundPrice[]>;
  selectedFund: Ref<string>;
  baseCurrency: Ref<string>;
  locale: Ref<string>;
}

export interface UseFundsPortfolio {
  openPositions: ComputedRef<FundPosition[]>;
  topPositions: ComputedRef<FundPosition[]>;
  normalizedTopPositions: ComputedRef<NormalizedPosition[]>;
  totalInvested: ComputedRef<number>;
  totalValue: ComputedRef<number>;
  unrealizedPnl: ComputedRef<number>;
  openReturn: ComputedRef<number>;
  realizedPnl: ComputedRef<number>;
  totalPnl: ComputedRef<number>;
  selectedFundPosition: ComputedRef<FundPosition | null>;
  selectedFundOrders: ComputedRef<FundOrder[]>;
  latestPriceByIsin: ComputedRef<Map<string, FundPrice>>;
  pricedPositions: ComputedRef<number>;
  positionSortKey: Ref<FundPositionSortKey>;
  positionSortDirection: Ref<FundSortDirection>;
  sortedPositions: ComputedRef<FundPosition[]>;
  baseAmount: (item: FundOrder) => number;
  sortPositions: (key: FundPositionSortKey) => void;
  positionAriaSort: (key: FundPositionSortKey) => FundPositionAriaSort;
}

export function useFundsPortfolio(
  options: UseFundsPortfolioOptions,
): UseFundsPortfolio {
  const {
    positions,
    orders,
    instruments,
    prices,
    selectedFund,
    baseCurrency,
    locale,
  } = options;
  const positionSortKey = ref<FundPositionSortKey>("value");
  const positionSortDirection = ref<FundSortDirection>("desc");

  const openPositions = computed(() =>
    [...positions.value]
      .filter((item) => item.participaciones > 0)
      .sort((a, b) => (b.valor_actual ?? 0) - (a.valor_actual ?? 0)),
  );
  const topPositions = computed(() => openPositions.value.slice(0, 5));
  const normalizedPosition = (position: FundPosition): NormalizedPosition =>
    adaptFundPosition(
      position,
      instruments.value.find((item) => item.isin === position.isin),
      { baseCurrency: baseCurrency.value },
    );
  const normalizedTopPositions = computed(() =>
    topPositions.value.map(normalizedPosition),
  );
  const totalInvested = computed(() =>
    openPositions.value.reduce(
      (total, item) => total + item.total_invertido,
      0,
    ),
  );
  const totalValue = computed(() =>
    openPositions.value.reduce(
      (total, item) => total + (item.valor_actual ?? 0),
      0,
    ),
  );
  const unrealizedPnl = computed(() =>
    openPositions.value.reduce((total, item) => total + (item.pnl ?? 0), 0),
  );
  const openReturn = computed(() =>
    totalInvested.value ? unrealizedPnl.value / totalInvested.value : 0,
  );
  const realizedPnl = computed(() => calculateRealizedPnl(orders.value));
  const totalPnl = computed(() => unrealizedPnl.value + realizedPnl.value);
  const selectedFundPosition = computed(
    () =>
      positions.value.find((item) => item.isin === selectedFund.value) ?? null,
  );
  const selectedFundOrders = computed(() =>
    orders.value.filter((item) => item.isin === selectedFund.value),
  );
  const latestPriceByIsin = computed(
    () => new Map(prices.value.map((item) => [item.isin, item])),
  );
  const pricedPositions = computed(
    () =>
      positions.value.filter((item) => latestPriceByIsin.value.has(item.isin))
        .length,
  );
  const sortedPositions = computed(() => {
    const collator = new Intl.Collator(locale.value, {
      numeric: true,
      sensitivity: "base",
    });
    const valueFor = (position: FundPosition): string | number | null => {
      switch (positionSortKey.value) {
        case "fund":
          return position.nombre;
        case "type":
          return `${position.tipo} ${position.subtipo}`.trim();
        case "contributed":
          return position.total_invertido;
        case "shares":
          return position.participaciones;
        case "averagePrice":
          return position.precio_medio;
        case "currentPrice":
          return position.precio_actual;
        case "value":
          return position.valor_actual;
        case "pnl":
          return position.pnl;
        case "return":
          return position.pnl_pct;
      }
    };

    return [...positions.value].sort((left, right) => {
      const leftValue = valueFor(left);
      const rightValue = valueFor(right);
      if (leftValue == null && rightValue == null)
        return collator.compare(left.nombre, right.nombre);
      if (leftValue == null) return 1;
      if (rightValue == null) return -1;

      const comparison =
        typeof leftValue === "string" && typeof rightValue === "string"
          ? collator.compare(leftValue, rightValue)
          : Number(leftValue) - Number(rightValue);
      if (comparison === 0) return collator.compare(left.nombre, right.nombre);
      return positionSortDirection.value === "asc" ? comparison : -comparison;
    });
  });

  function baseAmount(item: FundOrder) {
    return item.importe_base ?? item.importe_neto;
  }

  function calculateRealizedPnl(items: FundOrder[]) {
    const buyTypes = new Set(["SUSCRIPCION", "SUSCR.POR TRASPASO I"]);
    const sellTypes = new Set(["REEMB.POR TRASPASO I", "REEMBOLSO"]);
    const grouped = new Map<string, FundOrder[]>();
    items.forEach((item) => {
      grouped.set(item.isin, [...(grouped.get(item.isin) ?? []), item]);
    });
    let total = 0;
    grouped.forEach((fundOrders) => {
      let boughtQuantity = 0;
      let buyCost = 0;
      let soldQuantity = 0;
      let saleValue = 0;
      fundOrders.forEach((item) => {
        if (buyTypes.has(item.tipo_operacion)) {
          boughtQuantity += item.titulos;
          buyCost += baseAmount(item);
        } else if (sellTypes.has(item.tipo_operacion)) {
          soldQuantity += item.titulos;
          saleValue += baseAmount(item);
        }
      });
      if (boughtQuantity > 0 && soldQuantity > 0) {
        total += saleValue - (buyCost / boughtQuantity) * soldQuantity;
      }
    });
    return total;
  }

  function sortPositions(key: FundPositionSortKey) {
    if (positionSortKey.value === key) {
      positionSortDirection.value =
        positionSortDirection.value === "asc" ? "desc" : "asc";
      return;
    }
    positionSortKey.value = key;
    positionSortDirection.value = "asc";
  }

  function positionAriaSort(key: FundPositionSortKey): FundPositionAriaSort {
    if (positionSortKey.value !== key) return "none";
    return positionSortDirection.value === "asc" ? "ascending" : "descending";
  }

  return {
    openPositions,
    topPositions,
    normalizedTopPositions,
    totalInvested,
    totalValue,
    unrealizedPnl,
    openReturn,
    realizedPnl,
    totalPnl,
    selectedFundPosition,
    selectedFundOrders,
    latestPriceByIsin,
    pricedPositions,
    positionSortKey,
    positionSortDirection,
    sortedPositions,
    baseAmount,
    sortPositions,
    positionAriaSort,
  };
}
