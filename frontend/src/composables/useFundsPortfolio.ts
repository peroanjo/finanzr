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
import { instrumentById, instrumentIdentity } from "../domain/instruments";

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
  latestPriceByInstrumentId: ComputedRef<Map<string, FundPrice>>;
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
      .filter((item) => item.quantity > 0)
      .sort((a, b) => (b.current_value ?? 0) - (a.current_value ?? 0)),
  );
  const topPositions = computed(() => openPositions.value.slice(0, 5));
  const normalizedPosition = (position: FundPosition): NormalizedPosition =>
    adaptFundPosition(
      position,
      instrumentById(instruments.value, position.instrument_id),
      { baseCurrency: baseCurrency.value },
    );
  const normalizedTopPositions = computed(() =>
    topPositions.value.map(normalizedPosition),
  );
  const totalInvested = computed(() =>
    openPositions.value.reduce((total, item) => total + item.cost, 0),
  );
  const totalValue = computed(() =>
    openPositions.value.reduce(
      (total, item) => total + (item.current_value ?? 0),
      0,
    ),
  );
  const unrealizedPnl = computed(() =>
    openPositions.value.reduce(
      (total, item) => total + (item.unrealized_pnl ?? 0),
      0,
    ),
  );
  const openReturn = computed(() =>
    totalInvested.value ? unrealizedPnl.value / totalInvested.value : 0,
  );
  const realizedPnl = computed(() => calculateRealizedPnl(orders.value));
  const totalPnl = computed(() => unrealizedPnl.value + realizedPnl.value);
  const selectedFundPosition = computed(
    () =>
      positions.value.find(
        (item) => item.instrument_id === selectedFund.value,
      ) ?? null,
  );
  const selectedFundIdentity = computed(() =>
    instrumentIdentity(instrumentById(instruments.value, selectedFund.value)),
  );
  const selectedFundOrders = computed(() =>
    orders.value.filter((item) => item.isin === selectedFundIdentity.value),
  );
  const latestPriceByInstrumentId = computed(
    () => new Map(prices.value.map((item) => [item.instrument_id, item])),
  );
  const pricedPositions = computed(
    () =>
      positions.value.filter((item) => {
        const instrument = instrumentById(
          instruments.value,
          item.instrument_id,
        );
        return instrument
          ? latestPriceByInstrumentId.value.has(instrument.id)
          : false;
      }).length,
  );
  const sortedPositions = computed(() => {
    const collator = new Intl.Collator(locale.value, {
      numeric: true,
      sensitivity: "base",
    });
    const valueFor = (position: FundPosition): string | number | null => {
      switch (positionSortKey.value) {
        case "fund":
          return position.name;
        case "type":
          return `${position.asset_class} ${position.subtype}`.trim();
        case "contributed":
          return position.cost;
        case "shares":
          return position.quantity;
        case "averagePrice":
          return position.average_price;
        case "currentPrice":
          return position.current_price;
        case "value":
          return position.current_value;
        case "pnl":
          return position.unrealized_pnl;
        case "return":
          return position.return_percent;
      }
    };

    return [...positions.value].sort((left, right) => {
      const leftValue = valueFor(left);
      const rightValue = valueFor(right);
      if (leftValue == null && rightValue == null)
        return collator.compare(left.name, right.name);
      if (leftValue == null) return 1;
      if (rightValue == null) return -1;

      const comparison =
        typeof leftValue === "string" && typeof rightValue === "string"
          ? collator.compare(leftValue, rightValue)
          : Number(leftValue) - Number(rightValue);
      if (comparison === 0) return collator.compare(left.name, right.name);
      return positionSortDirection.value === "asc" ? comparison : -comparison;
    });
  });

  function baseAmount(item: FundOrder) {
    return item.base_net_amount ?? item.net_amount;
  }

  function calculateRealizedPnl(items: FundOrder[]) {
    const buyTypes = new Set(["buy", "transfer_in"]);
    const sellTypes = new Set(["transfer_out", "sell"]);
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
        if (buyTypes.has(item.operation_type)) {
          boughtQuantity += item.quantity;
          buyCost += baseAmount(item);
        } else if (sellTypes.has(item.operation_type)) {
          soldQuantity += item.quantity;
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
    latestPriceByInstrumentId,
    pricedPositions,
    positionSortKey,
    positionSortDirection,
    sortedPositions,
    baseAmount,
    sortPositions,
    positionAriaSort,
  };
}
