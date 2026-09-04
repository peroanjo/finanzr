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
    instrument_id: "FUND-1",
    kind: "fund",
    name: "Fund 1",
    asset_class: "Renta Variable",
    subtype: "Global",
    quantity: 10,
    cost: 1000,
    average_price: 100,
    current_price: 120,
    current_value: 1200,
    unrealized_pnl: 200,
    realized_pnl: null,
    currency: "EUR",
    base_currency: "EUR",
    return_percent: 0.2,
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
  const identity = overrides.identifiers?.find(
    (item) => item.scheme === "isin",
  )?.value;
  return {
    id: identity ?? "FUND-1",
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
    id: "00000000-0000-0000-0000-000000000401",
    instrument_id: "FUND-1",
    quoted_at: "2026-07-01T00:00:00+00:00",
    close: 120,
    currency: "EUR",
    base_close: 120,
    base_currency: "EUR",
    fx_rate_to_base: 1,
    fx_rate_date: "2026-07-01",
    fx_source: "identity",
    source: "test",
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
      makePosition({ instrument_id: "FUND-1", current_value: 100 }),
      makePosition({ instrument_id: "FUND-2", current_value: 600 }),
      makePosition({ instrument_id: "FUND-3", current_value: 500 }),
      makePosition({ instrument_id: "FUND-4", current_value: 400 }),
      makePosition({ instrument_id: "FUND-5", current_value: 300 }),
      makePosition({ instrument_id: "FUND-6", current_value: 200 }),
      makePosition({
        instrument_id: "CLOSED",
        quantity: 0,
        current_value: 900,
      }),
    ];
    const portfolio = createPortfolio({ positions });

    expect(
      portfolio.openPositions.value.map((item) => item.instrument_id),
    ).toEqual(["FUND-2", "FUND-3", "FUND-4", "FUND-5", "FUND-6", "FUND-1"]);
    expect(
      portfolio.topPositions.value.map((item) => item.instrument_id),
    ).toEqual(["FUND-2", "FUND-3", "FUND-4", "FUND-5", "FUND-6"]);
  });

  it("calculates open totals, return, and total P&L from open positions", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          instrument_id: "OPEN-1",
          cost: 1000,
          current_value: 1200,
          unrealized_pnl: 200,
        }),
        makePosition({
          instrument_id: "OPEN-2",
          cost: 500,
          current_value: null,
          unrealized_pnl: null,
        }),
        makePosition({
          instrument_id: "CLOSED",
          quantity: 0,
          cost: 900,
          current_value: 900,
          unrealized_pnl: 100,
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
          instrument_id: "USD-FUND",
          name: "Dollar fund",
          current_price: null,
          current_value: null,
          unrealized_pnl: null,
          return_percent: null,
          currency: "USD",
          base_currency: "EUR",
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
        makePosition({ instrument_id: "FUND-A", name: "Fund A" }),
        makePosition({ instrument_id: "FUND-B", name: "Fund B" }),
      ],
      orders: [makeOrder({ isin: "FUND-A" })],
      instruments: [
        makeInstrument({
          id: "FUND-A",
          identifiers: [
            { scheme: "isin", value: "FUND-A", venue: "", is_primary: true },
          ],
        }),
        makeInstrument({
          id: "FUND-B",
          identifiers: [
            { scheme: "isin", value: "FUND-B", venue: "", is_primary: true },
          ],
        }),
      ],
      prices: [makePrice({ instrument_id: "FUND-A" })],
      selectedFund: "FUND-A",
    });

    expect(portfolio.selectedFundPosition.value?.instrument_id).toBe("FUND-A");
    expect(portfolio.selectedFundOrders.value).toHaveLength(1);
    expect(portfolio.pricedPositions.value).toBe(1);
    expect(portfolio.latestPriceByInstrumentId.value.get("FUND-A")?.close).toBe(
      120,
    );

    portfolio.selectedFund.value = "FUND-B";
    expect(portfolio.selectedFundPosition.value?.instrument_id).toBe("FUND-B");
    expect(portfolio.selectedFundOrders.value).toHaveLength(0);

    portfolio.prices.value = [
      makePrice({
        instrument_id: "FUND-A",
      }),
      makePrice({
        id: "00000000-0000-0000-0000-000000000402",
        instrument_id: "FUND-B",
        close: 80,
      }),
    ];
    portfolio.instruments.value = [
      makeInstrument({
        id: "FUND-A",
        identifiers: [
          { scheme: "isin", value: "FUND-A", venue: "", is_primary: true },
        ],
      }),
      makeInstrument({
        id: "FUND-B",
        identifiers: [
          { scheme: "isin", value: "FUND-B", venue: "", is_primary: true },
          { scheme: "yahoo", value: "FUND2.MC", venue: "", is_primary: true },
        ],
      }),
    ];
    expect(portfolio.pricedPositions.value).toBe(2);
    expect(portfolio.latestPriceByInstrumentId.value.get("FUND-B")?.close).toBe(
      80,
    );
  });

  it("preserves initial sort state, null ordering, locale collation, and handlers", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          instrument_id: "FUND-2",
          name: "Fund 2",
          current_value: 100,
        }),
        makePosition({
          instrument_id: "FUND-10",
          name: "Fund 10",
          current_value: 100,
        }),
        makePosition({
          instrument_id: "FUND-A",
          name: "Alpha",
          current_value: null,
        }),
        makePosition({
          instrument_id: "FUND-B",
          name: "Beta",
          current_value: 200,
        }),
      ],
    });

    expect(portfolio.positionSortKey.value).toBe("value");
    expect(portfolio.positionSortDirection.value).toBe("desc");
    expect(portfolio.sortedPositions.value.map((item) => item.name)).toEqual([
      "Beta",
      "Fund 2",
      "Fund 10",
      "Alpha",
    ]);

    portfolio.sortPositions("fund");
    expect(portfolio.positionSortDirection.value).toBe("asc");
    expect(portfolio.sortedPositions.value.map((item) => item.name)).toEqual([
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
