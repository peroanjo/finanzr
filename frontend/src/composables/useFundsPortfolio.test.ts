import { ref } from "vue";
import { describe, expect, it } from "vitest";
import { useFundsPortfolio } from "./useFundsPortfolio";
import type {
  FundInstrument,
  FundOrder,
  FundPosition,
  FundPrice,
} from "../types/api";

function makePosition(overrides: Partial<FundPosition> = {}): FundPosition {
  return {
    isin: "FUND-1",
    nombre: "Fund 1",
    tipo: "Renta Variable",
    subtipo: "Global",
    total_invertido: 1000,
    participaciones: 10,
    precio_medio: 100,
    precio_actual: 120,
    valor_actual: 1200,
    pnl: 200,
    pnl_pct: 0.2,
    ...overrides,
  };
}

function makeOrder(overrides: Partial<FundOrder> = {}): FundOrder {
  return {
    id: "operation-1",
    trade_date: "2026-01-01",
    settlement_date: "2026-01-02",
    operation_type: "buy",
    cash_flow_type: "contribution",
    isin: "FUND-1",
    asset_name: "Fund 1",
    quantity: 1,
    unit_price: 100,
    net_amount: 100,
    fee: 0,
    account_id: "00000000-0000-0000-0000-000000000001",
    account_name: "Account",
    platform: "Platform",
    currency: "EUR",
    base_currency: "EUR",
    base_unit_price: 100,
    base_net_amount: 100,
    base_fee: 0,
    fx_rate_to_base: 1,
    fx_rate_date: "2026-01-01",
    fx_source: "identity",
    market: "",
    provider_operation_type: "SUSCRIPCION",
    ...overrides,
  };
}

function makeInstrument(
  overrides: Partial<FundInstrument> = {},
): FundInstrument {
  return {
    id: "00000000-0000-0000-0000-000000000301",
    kind: "fund",
    name: "Fund 1",
    quote_currency: "EUR",
    identifiers: [
      { scheme: "isin", value: "FUND-1", venue: "", is_primary: true },
      { scheme: "yahoo", value: "FUND1.MC", venue: "", is_primary: true },
    ],
    asset_class: "Renta Variable",
    subtype: "Global",
    is_active: true,
    ...overrides,
  };
}

function makePrice(overrides: Partial<FundPrice> = {}): FundPrice {
  return {
    isin: "FUND-1",
    precio: 120,
    updated: "2026-07-01",
    ...overrides,
  };
}

function createPortfolio({
  positions: positionRows = [],
  orders: orderRows = [],
  instruments: instrumentRows = [],
  prices: priceRows = [],
  selectedFund: selectedFundId = "",
  baseCurrency: currency = "EUR",
  locale: currentLocale = "en",
}: {
  positions?: FundPosition[];
  orders?: FundOrder[];
  instruments?: FundInstrument[];
  prices?: FundPrice[];
  selectedFund?: string;
  baseCurrency?: string;
  locale?: string;
} = {}) {
  const positions = ref(positionRows);
  const orders = ref(orderRows);
  const instruments = ref(instrumentRows);
  const prices = ref(priceRows);
  const selectedFund = ref(selectedFundId);
  const baseCurrency = ref(currency);
  const locale = ref(currentLocale);
  const portfolio = useFundsPortfolio({
    positions,
    orders,
    instruments,
    prices,
    selectedFund,
    baseCurrency,
    locale,
  });
  return {
    ...portfolio,
    positions,
    orders,
    instruments,
    prices,
    selectedFund,
    baseCurrency,
    locale,
  };
}

describe("useFundsPortfolio", () => {
  it("filters open positions, orders them by value, and limits the top five", () => {
    const positions = [
      makePosition({ isin: "FUND-1", valor_actual: 100 }),
      makePosition({ isin: "FUND-2", valor_actual: 600 }),
      makePosition({ isin: "FUND-3", valor_actual: 500 }),
      makePosition({ isin: "FUND-4", valor_actual: 400 }),
      makePosition({ isin: "FUND-5", valor_actual: 300 }),
      makePosition({ isin: "FUND-6", valor_actual: 200 }),
      makePosition({ isin: "CLOSED", participaciones: 0, valor_actual: 900 }),
    ];
    const portfolio = createPortfolio({ positions });

    expect(portfolio.openPositions.value.map((item) => item.isin)).toEqual([
      "FUND-2",
      "FUND-3",
      "FUND-4",
      "FUND-5",
      "FUND-6",
      "FUND-1",
    ]);
    expect(portfolio.topPositions.value.map((item) => item.isin)).toEqual([
      "FUND-2",
      "FUND-3",
      "FUND-4",
      "FUND-5",
      "FUND-6",
    ]);
  });

  it("calculates open totals, return, and total P&L from open positions", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          isin: "OPEN-1",
          total_invertido: 1000,
          valor_actual: 1200,
          pnl: 200,
        }),
        makePosition({
          isin: "OPEN-2",
          total_invertido: 500,
          valor_actual: null,
          pnl: null,
        }),
        makePosition({
          isin: "CLOSED",
          participaciones: 0,
          total_invertido: 900,
          valor_actual: 900,
          pnl: 100,
        }),
      ],
    });

    expect(portfolio.totalInvested.value).toBe(1500);
    expect(portfolio.totalValue.value).toBe(1200);
    expect(portfolio.unrealizedPnl.value).toBe(200);
    expect(portfolio.openReturn.value).toBeCloseTo(200 / 1500);
    expect(portfolio.realizedPnl.value).toBe(0);
    expect(portfolio.totalPnl.value).toBe(200);
  });

  it("calculates realized P&L per ISIN with transfer types and base amounts", () => {
    const portfolio = createPortfolio({
      orders: [
        makeOrder({
          id: "a-buy",
          isin: "FUND-A",
          quantity: 4,
          net_amount: 400,
          base_net_amount: 400,
        }),
        makeOrder({
          id: "a-transfer-in",
          isin: "FUND-A",
          operation_type: "transfer_in",
          cash_flow_type: "internal",
          provider_operation_type: "SUSCR.POR TRASPASO I",
          quantity: 2,
          net_amount: 240,
          base_net_amount: 200,
        }),
        makeOrder({
          id: "a-transfer-out",
          isin: "FUND-A",
          operation_type: "transfer_out",
          cash_flow_type: "internal",
          provider_operation_type: "REEMB.POR TRASPASO I",
          quantity: 3,
          net_amount: 420,
          base_net_amount: 390,
        }),
        makeOrder({
          id: "b-buy",
          isin: "FUND-B",
          quantity: 2,
          net_amount: 100,
          base_net_amount: 100,
        }),
        makeOrder({
          id: "b-sale",
          isin: "FUND-B",
          operation_type: "sell",
          cash_flow_type: "withdrawal",
          provider_operation_type: "REEMBOLSO",
          quantity: 1,
          net_amount: 75,
          base_net_amount: 75,
        }),
        makeOrder({
          id: "ignored-buy",
          isin: "FUND-C",
          operation_type: "buy",
          quantity: 1,
          net_amount: 100,
        }),
        makeOrder({
          id: "ignored-sale",
          isin: "FUND-C",
          operation_type: "sell",
          quantity: 1,
          net_amount: 150,
        }),
      ],
    });

    expect(
      portfolio.baseAmount(
        makeOrder({ net_amount: 240, base_net_amount: 200 }),
      ),
    ).toBe(200);
    expect(
      portfolio.baseAmount(
        makeOrder({ net_amount: 240, base_net_amount: null }),
      ),
    ).toBe(240);
    expect(portfolio.realizedPnl.value).toBeCloseTo(115);
  });

  it("normalizes top positions with nullable values and the supplied base currency", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          isin: "USD-FUND",
          nombre: "Dollar fund",
          precio_actual: null,
          valor_actual: null,
          pnl: null,
          pnl_pct: null,
          moneda: "USD",
          moneda_base: "EUR",
        }),
      ],
      instruments: [
        makeInstrument({
          name: "Dollar fund",
          quote_currency: "USD",
          identifiers: [
            { scheme: "isin", value: "USD-FUND", venue: "", is_primary: true },
            { scheme: "yahoo", value: "USD-FUND", venue: "", is_primary: true },
          ],
        }),
      ],
      baseCurrency: "EUR",
    });

    expect(portfolio.normalizedTopPositions.value[0]).toMatchObject({
      kind: "fund",
      assetId: "USD-FUND",
      name: "Dollar fund",
      currentPrice: null,
      currentValue: null,
      unrealizedPnl: null,
      currency: "EUR",
      baseCurrency: "EUR",
    });
    expect(
      portfolio.normalizedTopPositions.value[0].metadata.originalCurrency,
    ).toBe("USD");
  });

  it("reacts to selected fund and price changes", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({ isin: "FUND-A", nombre: "Fund A" }),
        makePosition({ isin: "FUND-B", nombre: "Fund B" }),
      ],
      orders: [makeOrder({ isin: "FUND-A" })],
      prices: [makePrice({ isin: "FUND-A" })],
      selectedFund: "FUND-A",
    });

    expect(portfolio.selectedFundPosition.value?.isin).toBe("FUND-A");
    expect(portfolio.selectedFundOrders.value).toHaveLength(1);
    expect(portfolio.pricedPositions.value).toBe(1);
    expect(portfolio.latestPriceByIsin.value.get("FUND-A")?.precio).toBe(120);

    portfolio.selectedFund.value = "FUND-B";
    expect(portfolio.selectedFundPosition.value?.isin).toBe("FUND-B");
    expect(portfolio.selectedFundOrders.value).toHaveLength(0);

    portfolio.prices.value = [
      makePrice({ isin: "FUND-A" }),
      makePrice({ isin: "FUND-B", precio: 80 }),
    ];
    expect(portfolio.pricedPositions.value).toBe(2);
    expect(portfolio.latestPriceByIsin.value.get("FUND-B")?.precio).toBe(80);
  });

  it("preserves initial sort state, null ordering, locale collation, and handlers", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({ isin: "FUND-2", nombre: "Fund 2", valor_actual: 100 }),
        makePosition({
          isin: "FUND-10",
          nombre: "Fund 10",
          valor_actual: 100,
        }),
        makePosition({ isin: "FUND-A", nombre: "Alpha", valor_actual: null }),
        makePosition({ isin: "FUND-B", nombre: "Beta", valor_actual: 200 }),
      ],
    });

    expect(portfolio.positionSortKey.value).toBe("value");
    expect(portfolio.positionSortDirection.value).toBe("desc");
    expect(portfolio.sortedPositions.value.map((item) => item.nombre)).toEqual([
      "Beta",
      "Fund 2",
      "Fund 10",
      "Alpha",
    ]);

    portfolio.sortPositions("fund");
    expect(portfolio.positionSortDirection.value).toBe("asc");
    expect(portfolio.sortedPositions.value.map((item) => item.nombre)).toEqual([
      "Alpha",
      "Beta",
      "Fund 2",
      "Fund 10",
    ]);
    expect(portfolio.positionAriaSort("fund")).toBe("ascending");
    expect(portfolio.positionAriaSort("value")).toBe("none");

    portfolio.sortPositions("fund");
    expect(portfolio.positionSortDirection.value).toBe("desc");
    expect(portfolio.positionAriaSort("fund")).toBe("descending");
  });
});
