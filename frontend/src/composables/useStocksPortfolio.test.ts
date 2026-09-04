import { ref } from "vue";
import { describe, expect, it } from "vitest";
import { useStocksPortfolio } from "./useStocksPortfolio";
import type { StockPositionSortKey } from "./useStocksPortfolio";
import type { StockInstrument, StockOrder, StockPosition } from "../types/api";

function makePosition(overrides: Partial<StockPosition> = {}): StockPosition {
  return {
    instrument_id: "STOCK-1",
    kind: "stock",
    name: "Stock 1",
    quantity: 2,
    cost: 100,
    current_price: 60,
    current_value: 120,
    unrealized_pnl: 20,
    realized_pnl: 5,
    currency: "EUR",
    base_currency: "EUR",
    ...overrides,
  };
}

function makeOrder(overrides: Partial<StockOrder> = {}): StockOrder {
  return {
    id: "operation-1",
    trade_date: "2026-01-01",
    settlement_date: null,
    quantity: 1,
    net_amount: 100,
    fee: 1,
    account_id: "00000000-0000-0000-0000-000000000001",
    account_name: "Account",
    platform: "Platform",
    operation_type: "buy",
    cash_flow_type: "none",
    isin: "STOCK-1",
    asset_name: "Stock 1",
    unit_price: 100,
    is_saveback: false,
    currency: "EUR",
    base_currency: "EUR",
    base_unit_price: 100,
    base_net_amount: 100,
    base_fee: 1,
    fx_rate_to_base: 1,
    fx_rate_date: "2026-01-01",
    fx_source: "identity",
    market: "",
    provider_operation_type: "Compra",
    ...overrides,
  };
}

function makeInstrument(
  overrides: Partial<StockInstrument> = {},
): StockInstrument {
  const identity = overrides.identifiers?.find(
    (item) => item.scheme === "isin",
  )?.value;
  return {
    id: identity ?? "STOCK-1",
    kind: "stock",
    name: "Stock 1",
    quote_currency: "EUR",
    identifiers: [
      { scheme: "isin", value: "STOCK-1", venue: "", is_primary: true },
      { scheme: "yahoo", value: "STK1", venue: "", is_primary: true },
    ],
    asset_class: null,
    subtype: null,
    is_active: true,
    ...overrides,
  };
}

function createPortfolio({
  positions: positionRows = [],
  orders: orderRows = [],
  instruments: instrumentRows = [],
  selectedInstrumentId: selectedAsset = "",
  locale: currentLocale = "en",
}: {
  positions?: StockPosition[];
  orders?: StockOrder[];
  instruments?: StockInstrument[];
  selectedInstrumentId?: string;
  locale?: string;
} = {}) {
  const positions = ref(positionRows);
  const orders = ref(orderRows);
  const instruments = ref(instrumentRows);
  const selectedInstrumentId = ref(selectedAsset);
  const locale = ref(currentLocale);
  const portfolio = useStocksPortfolio({
    positions,
    orders,
    instruments,
    selectedInstrumentId,
    locale,
  });
  return {
    ...portfolio,
    positions,
    orders,
    instruments,
    selectedInstrumentId,
    locale,
  };
}

describe("useStocksPortfolio", () => {
  it("filters open positions by positive quantity and limits the top five", () => {
    const positions = [
      makePosition({ instrument_id: "STOCK-1", current_value: 100 }),
      makePosition({ instrument_id: "STOCK-2", current_value: 600 }),
      makePosition({ instrument_id: "STOCK-3", current_value: 500 }),
      makePosition({ instrument_id: "STOCK-4", current_value: 400 }),
      makePosition({ instrument_id: "STOCK-5", current_value: 300 }),
      makePosition({ instrument_id: "STOCK-6", current_value: 200 }),
      makePosition({
        instrument_id: "CLOSED",
        name: "Closed",
        quantity: 0,
        current_value: 900,
      }),
    ];
    const portfolio = createPortfolio({ positions });

    expect(
      portfolio.openPositions.value.map((item) => item.instrument_id),
    ).toEqual([
      "STOCK-2",
      "STOCK-3",
      "STOCK-4",
      "STOCK-5",
      "STOCK-6",
      "STOCK-1",
    ]);
    expect(
      portfolio.topPositions.value.map((item) => item.instrument_id),
    ).toEqual(["STOCK-2", "STOCK-3", "STOCK-4", "STOCK-5", "STOCK-6"]);
  });

  it("calculates totals from open positions and realized P&L from every position", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          instrument_id: "OPEN-1",
          cost: 1000,
          current_value: 1200,
          unrealized_pnl: 200,
          realized_pnl: 11,
        }),
        makePosition({
          instrument_id: "OPEN-2",
          cost: 500,
          current_value: null,
          unrealized_pnl: null,
          realized_pnl: -3,
        }),
        makePosition({
          instrument_id: "CLOSED",
          quantity: 0,
          cost: 900,
          current_value: 900,
          unrealized_pnl: 100,
          realized_pnl: 25,
        }),
      ],
    });

    expect(portfolio.totalCost.value).toBe(1500);
    expect(portfolio.totalValue.value).toBe(1200);
    expect(portfolio.unrealizedPnl.value).toBe(200);
    expect(portfolio.openReturn.value).toBeCloseTo(200 / 1500);
    expect(portfolio.realizedPnl.value).toBe(33);
    expect(portfolio.totalPnl.value).toBe(233);

    portfolio.positions.value = [
      makePosition({ cost: 0, current_value: 10, unrealized_pnl: 5 }),
    ];
    expect(portfolio.openReturn.value).toBe(0);
  });

  it("normalizes matching and missing instruments with nullable values and base currency", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          instrument_id: "USD-STOCK",
          name: "Dollar stock",
          current_price: null,
          current_value: null,
          unrealized_pnl: null,
          currency: "USD",
          base_currency: "EUR",
        }),
        makePosition({
          instrument_id: "MISSING",
          name: "Missing instrument",
          quantity: 1,
          current_value: 90,
          currency: "EUR",
        }),
      ],
      instruments: [
        makeInstrument({
          id: "USD-STOCK",
          name: "Dollar stock",
          quote_currency: "USD",
          identifiers: [
            { scheme: "isin", value: "USD-STOCK", venue: "", is_primary: true },
            { scheme: "yahoo", value: "USDSTK", venue: "", is_primary: true },
          ],
        }),
      ],
    });

    const normalized = portfolio.normalizedTopPositions.value;
    const dollarStock = normalized.find(
      (item) => item.assetKey === "stock:USD-STOCK",
    );
    const missing = normalized.find(
      (item) => item.assetKey === "stock:MISSING",
    );
    expect(dollarStock).toMatchObject({
      assetKey: "stock:USD-STOCK",
      displayIdentifier: "USD-STOCK",
      name: "Dollar stock",
      currentPrice: null,
      currentValue: null,
      unrealizedPnl: null,
      returnPercent: null,
    });
    expect(missing).toMatchObject({
      name: "Missing instrument",
      currentValue: 90,
    });
  });

  it("reacts to selection and source changes while counting only priced positions", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({ instrument_id: "STOCK-A", name: "Stock A" }),
        makePosition({
          instrument_id: "STOCK-B",
          name: "Stock B",
          current_price: null,
        }),
      ],
      instruments: [
        makeInstrument({
          id: "STOCK-A",
          identifiers: [
            { scheme: "isin", value: "STOCK-A", venue: "", is_primary: true },
          ],
        }),
        makeInstrument({
          id: "STOCK-B",
          identifiers: [
            { scheme: "isin", value: "STOCK-B", venue: "", is_primary: true },
          ],
        }),
      ],
      orders: [
        makeOrder({ isin: "STOCK-A" }),
        makeOrder({ isin: "STOCK-B", id: "operation-2" }),
      ],
      selectedInstrumentId: "STOCK-A",
    });

    expect(portfolio.selectedPosition.value?.instrument_id).toBe("STOCK-A");
    expect(portfolio.selectedOrders.value).toHaveLength(1);
    expect(portfolio.averagePrice.value).toBe(50);
    expect(portfolio.pricedPositions.value).toBe(1);

    portfolio.selectedInstrumentId.value = "STOCK-B";
    expect(portfolio.selectedPosition.value?.instrument_id).toBe("STOCK-B");
    expect(portfolio.selectedOrders.value[0].isin).toBe("STOCK-B");
    expect(portfolio.averagePrice.value).toBe(50);

    portfolio.orders.value = [
      makeOrder({ isin: "STOCK-B", id: "operation-3" }),
      makeOrder({ isin: "STOCK-B", id: "operation-4" }),
    ];
    expect(portfolio.selectedOrders.value).toHaveLength(2);

    portfolio.positions.value[1] = makePosition({
      instrument_id: "STOCK-B",
      current_price: 70,
    });
    expect(portfolio.pricedPositions.value).toBe(2);
  });

  it("uses base currency fallbacks and preserves source orders before chart fixes", () => {
    const sourceWithBase = makeOrder({
      id: "byd-before-split",
      isin: "CNE100000296",
      trade_date: "2025-02-03",
      quantity: 1,
      net_amount: 34.07,
      base_net_amount: 30,
      unit_price: 34.07,
      base_unit_price: 30,
      fee: 1,
      base_fee: 0.5,
    });
    const sourceWithoutBase = makeOrder({
      id: "fallback",
      net_amount: 80,
      unit_price: 40,
      fee: 0.8,
      base_net_amount: null,
      base_unit_price: null,
      base_fee: null,
    });
    const sourceWithZeroBase = makeOrder({
      id: "zero-base",
      isin: "ZERO-BASE",
      net_amount: 80,
      base_net_amount: 0,
      unit_price: 40,
      base_unit_price: 0,
      fee: 0.8,
      base_fee: 0,
    });
    const portfolio = createPortfolio({
      orders: [sourceWithBase, sourceWithoutBase, sourceWithZeroBase],
      selectedInstrumentId: "CNE100000296",
      instruments: [
        makeInstrument({
          id: "CNE100000296",
          identifiers: [
            {
              scheme: "isin",
              value: "CNE100000296",
              venue: "",
              is_primary: true,
            },
          ],
        }),
        makeInstrument({
          id: "STOCK-1",
          identifiers: [
            { scheme: "isin", value: "STOCK-1", venue: "", is_primary: true },
          ],
        }),
        makeInstrument({
          id: "ZERO-BASE",
          identifiers: [
            { scheme: "isin", value: "ZERO-BASE", venue: "", is_primary: true },
          ],
        }),
      ],
    });

    expect(portfolio.baseAmount(sourceWithBase)).toBe(30);
    expect(portfolio.basePrice(sourceWithBase)).toBe(30);
    expect(portfolio.baseFee(sourceWithBase)).toBe(0.5);
    expect(portfolio.baseAmount(sourceWithoutBase)).toBe(80);
    expect(portfolio.basePrice(sourceWithoutBase)).toBe(40);
    expect(portfolio.baseFee(sourceWithoutBase)).toBe(0.8);
    expect(portfolio.baseAmount(sourceWithZeroBase)).toBe(0);
    expect(portfolio.basePrice(sourceWithZeroBase)).toBe(0);
    expect(portfolio.baseFee(sourceWithZeroBase)).toBe(0);

    const [adjusted] = portfolio.selectedChartOrders.value;
    expect(adjusted).toMatchObject({
      net_amount: 30,
      unit_price: 10,
      fee: 0.5,
      quantity: 3,
      chartAdjustment: {
        id: "byd-pre-june-10-2025-split-3-to-1",
      },
    });
    expect(sourceWithBase).toMatchObject({
      net_amount: 34.07,
      unit_price: 34.07,
      quantity: 1,
    });

    portfolio.selectedInstrumentId.value = "ZERO-BASE";
    expect(portfolio.selectedChartOrders.value[0]).toMatchObject({
      net_amount: 0,
      unit_price: 0,
      fee: 0,
      quantity: 1,
    });

    portfolio.selectedInstrumentId.value = "STOCK-1";
    expect(portfolio.selectedChartOrders.value[0]).toMatchObject({
      net_amount: 80,
      unit_price: 40,
      fee: 0.8,
    });
  });

  it("sorts every stock column with null ordering, locale collation, and tie breaks", () => {
    const positions = [
      makePosition({
        instrument_id: "ZETA",
        name: "Zeta",
        quantity: 4,
        cost: 400,
        current_price: 40,
        current_value: 160,
        unrealized_pnl: 40,
      }),
      makePosition({
        instrument_id: "ALPHA",
        name: "Alpha",
        quantity: 1,
        cost: 100,
        current_price: 100,
        current_value: 100,
        unrealized_pnl: 10,
      }),
      makePosition({
        instrument_id: "BETA",
        name: "Beta",
        quantity: 2,
        cost: 200,
        current_price: 50,
        current_value: 100,
        unrealized_pnl: -20,
      }),
    ];
    const portfolio = createPortfolio({
      positions,
      instruments: [
        makeInstrument({
          identifiers: [
            { scheme: "isin", value: "ZETA", venue: "", is_primary: true },
            { scheme: "yahoo", value: "ZZ", venue: "", is_primary: true },
          ],
        }),
        makeInstrument({
          identifiers: [
            { scheme: "isin", value: "ALPHA", venue: "", is_primary: true },
            { scheme: "yahoo", value: "AA", venue: "", is_primary: true },
          ],
        }),
        makeInstrument({
          identifiers: [
            { scheme: "isin", value: "BETA", venue: "", is_primary: true },
            { scheme: "yahoo", value: "MM", venue: "", is_primary: true },
          ],
        }),
      ],
    });
    const expectedAscending: Record<StockPositionSortKey, string[]> = {
      asset: ["ALPHA", "BETA", "ZETA"],
      ticker: ["ALPHA", "BETA", "ZETA"],
      cost: ["ALPHA", "BETA", "ZETA"],
      quantity: ["ALPHA", "BETA", "ZETA"],
      averagePrice: ["ALPHA", "BETA", "ZETA"],
      currentPrice: ["ZETA", "BETA", "ALPHA"],
      value: ["ALPHA", "BETA", "ZETA"],
      pnl: ["BETA", "ALPHA", "ZETA"],
      return: ["BETA", "ALPHA", "ZETA"],
    };

    for (const key of Object.keys(
      expectedAscending,
    ) as StockPositionSortKey[]) {
      const expected = expectedAscending[key];
      portfolio.sortPositions(key);
      expect(portfolio.positionSortKey.value).toBe(key);
      expect(portfolio.positionSortDirection.value).toBe("asc");
      expect(
        portfolio.sortedPositions.value.map((item) => item.instrument_id),
      ).toEqual(expected);
      expect(portfolio.ariaSort(key)).toBe("ascending");
    }

    const nullPortfolio = createPortfolio({
      positions: [
        makePosition({
          instrument_id: "NULL",
          name: "Null value",
          current_value: null,
        }),
        makePosition({
          instrument_id: "BETA",
          name: "Beta",
          current_value: 100,
        }),
        makePosition({
          instrument_id: "ALPHA",
          name: "Alpha",
          current_value: 100,
        }),
      ],
    });
    expect(
      nullPortfolio.sortedPositions.value.map((item) => item.instrument_id),
    ).toEqual(["ALPHA", "BETA", "NULL"]);
    nullPortfolio.sortPositions("value");
    expect(
      nullPortfolio.sortedPositions.value.map((item) => item.instrument_id),
    ).toEqual(["ALPHA", "BETA", "NULL"]);
    expect(nullPortfolio.ariaSort("value")).toBe("ascending");
    nullPortfolio.sortPositions("value");
    expect(nullPortfolio.positionSortDirection.value).toBe("desc");
    expect(nullPortfolio.ariaSort("value")).toBe("descending");
    expect(nullPortfolio.sortedPositions.value.at(-1)?.instrument_id).toBe(
      "NULL",
    );
  });

  it("keeps ticker collation nonnumeric and recomputes names when locale changes", () => {
    const numericPortfolio = createPortfolio({
      positions: [
        makePosition({ instrument_id: "A2", name: "A2" }),
        makePosition({ instrument_id: "A10", name: "A10" }),
      ],
      instruments: [
        makeInstrument({
          identifiers: [
            { scheme: "isin", value: "A2", venue: "", is_primary: true },
            { scheme: "yahoo", value: "A2", venue: "", is_primary: true },
          ],
        }),
        makeInstrument({
          identifiers: [
            { scheme: "isin", value: "A10", venue: "", is_primary: true },
            { scheme: "yahoo", value: "A10", venue: "", is_primary: true },
          ],
        }),
      ],
    });
    numericPortfolio.sortPositions("ticker");
    expect(
      numericPortfolio.sortedPositions.value.map((item) => item.instrument_id),
    ).toEqual(["A10", "A2"]);

    const localeNames = ["ñ", "n"];
    const englishCollator = new Intl.Collator("en", { sensitivity: "base" });
    const spanishCollator = new Intl.Collator("es", { sensitivity: "base" });
    const englishOrder = [...localeNames].sort(englishCollator.compare);
    const spanishOrder = [...localeNames].sort(spanishCollator.compare);
    expect(englishOrder).not.toEqual(spanishOrder);

    const localePortfolio = createPortfolio({
      positions: [
        makePosition({ instrument_id: "TILDE", name: "ñ" }),
        makePosition({ instrument_id: "PLAIN", name: "n" }),
      ],
    });
    localePortfolio.sortPositions("asset");
    expect(
      localePortfolio.sortedPositions.value.map((item) => item.name),
    ).toEqual(englishOrder);
    localePortfolio.locale.value = "es";
    expect(
      localePortfolio.sortedPositions.value.map((item) => item.name),
    ).toEqual(spanishOrder);
  });

  it("sorts a missing Yahoo ticker by its canonical ISIN", () => {
    const firstId = "00000000-0000-0000-0000-000000000701";
    const secondId = "00000000-0000-0000-0000-000000000702";
    const portfolio = createPortfolio({
      positions: [
        makePosition({ instrument_id: firstId, name: "Zulu" }),
        makePosition({ instrument_id: secondId, name: "Alpha" }),
      ],
      instruments: [
        makeInstrument({
          id: firstId,
          identifiers: [
            { scheme: "isin", value: "ZZ000", venue: "", is_primary: true },
          ],
        }),
        makeInstrument({
          id: secondId,
          identifiers: [
            { scheme: "isin", value: "AA000", venue: "", is_primary: true },
          ],
        }),
      ],
    });

    portfolio.sortPositions("ticker");
    expect(
      portfolio.sortedPositions.value.map((item) => item.instrument_id),
    ).toEqual([secondId, firstId]);
  });
});
