import { ref } from "vue";
import { describe, expect, it } from "vitest";
import {
  useCryptoPortfolio,
  type CryptoPositionSortKey,
} from "./useCryptoPortfolio";
import type {
  CryptoInstrument,
  CryptoOrder,
  CryptoPosition,
} from "../types/api";

function makePosition(overrides: Partial<CryptoPosition> = {}): CryptoPosition {
  return {
    instrument_id: "CRYPTO-1",
    kind: "crypto",
    name: "Crypto 1",
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

function makeOrder(overrides: Partial<CryptoOrder> = {}): CryptoOrder {
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
    symbol: "CRYPTO-1",
    asset_name: "Crypto 1",
    unit_price: 100,
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
  overrides: Partial<CryptoInstrument> = {},
): CryptoInstrument {
  const identity = overrides.identifiers?.find(
    (item) => item.scheme === "crypto_symbol",
  )?.value;
  return {
    id: identity ?? "CRYPTO-1",
    kind: "crypto",
    name: "Crypto 1",
    quote_currency: "EUR",
    identifiers: [
      {
        scheme: "crypto_symbol",
        value: "CRYPTO-1",
        venue: "",
        is_primary: true,
      },
      { scheme: "yahoo", value: "CRYPTO1", venue: "", is_primary: true },
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
  positions?: CryptoPosition[];
  orders?: CryptoOrder[];
  instruments?: CryptoInstrument[];
  selectedInstrumentId?: string;
  locale?: string;
} = {}) {
  const positions = ref(positionRows);
  const orders = ref(orderRows);
  const instruments = ref(instrumentRows);
  const selectedInstrumentId = ref(selectedAsset);
  const locale = ref(currentLocale);
  const portfolio = useCryptoPortfolio({
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

describe("useCryptoPortfolio", () => {
  it("filters positive positions, sorts by value, and limits the top five", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({ instrument_id: "CRYPTO-1", current_value: 100 }),
        makePosition({ instrument_id: "CRYPTO-2", current_value: 600 }),
        makePosition({ instrument_id: "CRYPTO-3", current_value: 500 }),
        makePosition({ instrument_id: "CRYPTO-4", current_value: 400 }),
        makePosition({ instrument_id: "CRYPTO-5", current_value: 300 }),
        makePosition({ instrument_id: "CRYPTO-6", current_value: 200 }),
        makePosition({ instrument_id: "NULL-VALUE", current_value: null }),
        makePosition({
          instrument_id: "CLOSED",
          name: "Closed",
          quantity: 0,
          current_value: 900,
        }),
      ],
    });

    expect(
      portfolio.openPositions.value.map((item) => item.instrument_id),
    ).toEqual([
      "CRYPTO-2",
      "CRYPTO-3",
      "CRYPTO-4",
      "CRYPTO-5",
      "CRYPTO-6",
      "CRYPTO-1",
      "NULL-VALUE",
    ]);
    expect(
      portfolio.topPositions.value.map((item) => item.instrument_id),
    ).toEqual(["CRYPTO-2", "CRYPTO-3", "CRYPTO-4", "CRYPTO-5", "CRYPTO-6"]);
  });

  it("calculates open totals and keeps server realized P&L for every position", () => {
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

  it("normalizes matching and missing instruments and reacts to source currencies", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          instrument_id: "USD-COIN",
          name: "Dollar coin",
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
          id: "USD-COIN",
          name: "Dollar coin",
          quote_currency: "USD",
          identifiers: [
            {
              scheme: "crypto_symbol",
              value: "USD-COIN",
              venue: "",
              is_primary: true,
            },
            { scheme: "yahoo", value: "USDCOIN", venue: "", is_primary: true },
          ],
        }),
      ],
    });

    const normalized = portfolio.normalizedTopPositions.value;
    const dollarCoin = normalized.find(
      (item) => item.assetKey === "crypto:USD-COIN",
    );
    const missing = normalized.find(
      (item) => item.assetKey === "crypto:MISSING",
    );
    expect(dollarCoin).toMatchObject({
      assetKey: "crypto:USD-COIN",
      displayIdentifier: "USD-COIN",
      name: "Dollar coin",
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

  it("keeps confusable symbols distinct across selection, orders, normalization, and sorting", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          instrument_id: "BTC",
          name: "Bitcoin",
          current_value: 300,
        }),
        makePosition({
          instrument_id: "BTC-EUR",
          name: "Bitcoin pair",
          current_value: 200,
        }),
        makePosition({
          instrument_id: "btc",
          name: "Lowercase bitcoin",
          current_value: 100,
        }),
      ],
      orders: [
        makeOrder({ symbol: "BTC", id: "btc-order" }),
        makeOrder({ symbol: "BTC-EUR", id: "pair-order" }),
        makeOrder({ symbol: "btc", id: "lowercase-order" }),
      ],
      instruments: [
        makeInstrument({
          id: "BTC",
          identifiers: [
            {
              scheme: "crypto_symbol",
              value: "BTC",
              venue: "",
              is_primary: true,
            },
            { scheme: "yahoo", value: "000", venue: "", is_primary: true },
          ],
        }),
        makeInstrument({
          id: "BTC-EUR",
          identifiers: [
            {
              scheme: "crypto_symbol",
              value: "BTC-EUR",
              venue: "",
              is_primary: true,
            },
            { scheme: "yahoo", value: "100", venue: "", is_primary: true },
          ],
        }),
        makeInstrument({
          id: "btc",
          identifiers: [
            {
              scheme: "crypto_symbol",
              value: "btc",
              venue: "",
              is_primary: true,
            },
          ],
        }),
      ],
      selectedInstrumentId: "BTC-EUR",
    });

    expect(portfolio.selectedPosition.value?.instrument_id).toBe("BTC-EUR");
    expect(portfolio.selectedOrders.value.map((item) => item.id)).toEqual([
      "pair-order",
    ]);
    expect(
      portfolio.normalizedTopPositions.value.map((item) => item.assetKey),
    ).toEqual(["crypto:BTC", "crypto:BTC-EUR", "crypto:btc"]);

    portfolio.sortPositions("ticker");
    expect(
      portfolio.sortedPositions.value.map((item) => item.instrument_id),
    ).toEqual(["BTC", "BTC-EUR", "btc"]);

    portfolio.selectedInstrumentId.value = "btc";
    expect(portfolio.selectedPosition.value?.instrument_id).toBe("btc");
    expect(portfolio.selectedOrders.value.map((item) => item.id)).toEqual([
      "lowercase-order",
    ]);
  });

  it("tracks selected positions and orders and projects chart currency fallbacks without mutation", () => {
    const zeroBaseOrder = makeOrder({
      id: "zero-base",
      symbol: "CNE100000296",
      asset_name: "Crypto split-like symbol",
      quantity: 1,
      net_amount: 80,
      base_net_amount: 0,
      unit_price: 40,
      base_unit_price: 0,
      fee: 0.8,
      base_fee: 0,
    });
    const fallbackOrder = makeOrder({
      id: "fallback",
      symbol: "CNE100000296",
      net_amount: 90,
      base_net_amount: null,
      unit_price: 45,
      base_unit_price: null,
      fee: 0.9,
      base_fee: null,
    });
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          instrument_id: "CNE100000296",
          name: "Crypto split-like symbol",
          quantity: 1,
          cost: 40,
        }),
      ],
      orders: [zeroBaseOrder, fallbackOrder],
      selectedInstrumentId: "CNE100000296",
      instruments: [
        makeInstrument({
          id: "CNE100000296",
          identifiers: [
            {
              scheme: "crypto_symbol",
              value: "CNE100000296",
              venue: "",
              is_primary: true,
            },
          ],
        }),
      ],
    });

    expect(portfolio.selectedPosition.value?.instrument_id).toBe(
      "CNE100000296",
    );
    expect(portfolio.selectedOrders.value.map((item) => item.id)).toEqual([
      "zero-base",
      "fallback",
    ]);
    expect(portfolio.selectedChartOrders.value).toEqual([
      {
        ...zeroBaseOrder,
        id: "zero-base",
        unit_price: 0,
        net_amount: 0,
        fee: 0,
      },
      {
        ...fallbackOrder,
        id: "fallback",
        unit_price: 45,
        net_amount: 90,
        fee: 0.9,
      },
    ]);
    expect(portfolio.selectedChartOrders.value[0]).not.toBe(zeroBaseOrder);
    expect(portfolio.selectedChartOrders.value[0]).not.toHaveProperty(
      "chartAdjustment",
    );
    expect(zeroBaseOrder).toMatchObject({
      quantity: 1,
      unit_price: 40,
      net_amount: 80,
      fee: 0.8,
    });
    expect(portfolio.basePrice(zeroBaseOrder)).toBe(0);
    expect(portfolio.baseAmount(zeroBaseOrder)).toBe(0);
    expect(portfolio.baseFee(zeroBaseOrder)).toBe(0);
    expect(portfolio.basePrice(fallbackOrder)).toBe(45);
    expect(portfolio.baseAmount(fallbackOrder)).toBe(90);
    expect(portfolio.baseFee(fallbackOrder)).toBe(0.9);
    // Crypto orders do not receive the stock-only BYD split adjustment.
    expect(portfolio.selectedChartOrders.value[0].quantity).toBe(1);
  });

  it("reacts to selection, order, and price changes and averages only open positions", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({ instrument_id: "BTC", cost: 100, quantity: 2 }),
        makePosition({
          instrument_id: "ETH",
          name: "Ethereum",
          cost: 200,
          quantity: 0,
          current_price: null,
        }),
      ],
      orders: [
        makeOrder({ symbol: "BTC" }),
        makeOrder({ symbol: "ETH", id: "operation-2" }),
      ],
      selectedInstrumentId: "BTC",
      instruments: [
        makeInstrument({
          id: "BTC",
          identifiers: [
            {
              scheme: "crypto_symbol",
              value: "BTC",
              venue: "",
              is_primary: true,
            },
          ],
        }),
        makeInstrument({
          id: "ETH",
          identifiers: [
            {
              scheme: "crypto_symbol",
              value: "ETH",
              venue: "",
              is_primary: true,
            },
          ],
        }),
      ],
    });

    expect(portfolio.selectedPosition.value?.instrument_id).toBe("BTC");
    expect(portfolio.selectedOrders.value).toHaveLength(1);
    expect(portfolio.averagePrice.value).toBe(50);
    expect(portfolio.pricedPositions.value).toBe(1);

    portfolio.selectedInstrumentId.value = "ETH";
    expect(portfolio.selectedPosition.value?.instrument_id).toBe("ETH");
    expect(portfolio.selectedOrders.value[0].symbol).toBe("ETH");
    expect(portfolio.averagePrice.value).toBeNull();

    portfolio.orders.value = [
      makeOrder({ symbol: "ETH", id: "operation-3" }),
      makeOrder({ symbol: "ETH", id: "operation-4" }),
    ];
    expect(portfolio.selectedOrders.value).toHaveLength(2);

    portfolio.positions.value[1] = makePosition({
      instrument_id: "ETH",
      name: "Ethereum",
      quantity: 2,
      current_price: 70,
    });
    expect(portfolio.pricedPositions.value).toBe(2);
    expect(portfolio.averagePrice.value).toBe(50);
  });

  it("sorts every key with nulls last, stable name ties, and initial/toggle directions", () => {
    const positions = [
      makePosition({
        instrument_id: "ZETA",
        name: "Zeta",
        quantity: 3,
        cost: 300,
        current_price: 60,
        current_value: 180,
        unrealized_pnl: 30,
      }),
      makePosition({
        instrument_id: "ALPHA",
        name: "Alpha",
        quantity: 2,
        cost: 100,
        current_price: 120,
        current_value: 240,
        unrealized_pnl: 20,
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
            {
              scheme: "crypto_symbol",
              value: "ZETA",
              venue: "",
              is_primary: true,
            },
            { scheme: "yahoo", value: "ZZ", venue: "", is_primary: true },
          ],
        }),
        makeInstrument({
          identifiers: [
            {
              scheme: "crypto_symbol",
              value: "ALPHA",
              venue: "",
              is_primary: true,
            },
            { scheme: "yahoo", value: "AA", venue: "", is_primary: true },
          ],
        }),
        makeInstrument({
          identifiers: [
            {
              scheme: "crypto_symbol",
              value: "BETA",
              venue: "",
              is_primary: true,
            },
            { scheme: "yahoo", value: "MM", venue: "", is_primary: true },
          ],
        }),
      ],
    });
    const expectedOrder: Record<
      CryptoPositionSortKey,
      { asc: string[]; desc: string[] }
    > = {
      asset: {
        asc: ["ALPHA", "BETA", "ZETA"],
        desc: ["ZETA", "BETA", "ALPHA"],
      },
      ticker: {
        asc: ["ALPHA", "BETA", "ZETA"],
        desc: ["ZETA", "BETA", "ALPHA"],
      },
      cost: {
        asc: ["ALPHA", "BETA", "ZETA"],
        desc: ["ZETA", "BETA", "ALPHA"],
      },
      quantity: {
        asc: ["ALPHA", "BETA", "ZETA"],
        desc: ["ZETA", "ALPHA", "BETA"],
      },
      averagePrice: {
        asc: ["ALPHA", "BETA", "ZETA"],
        desc: ["BETA", "ZETA", "ALPHA"],
      },
      currentPrice: {
        asc: ["BETA", "ZETA", "ALPHA"],
        desc: ["ALPHA", "ZETA", "BETA"],
      },
      value: {
        asc: ["BETA", "ZETA", "ALPHA"],
        desc: ["ALPHA", "ZETA", "BETA"],
      },
      pnl: {
        asc: ["BETA", "ALPHA", "ZETA"],
        desc: ["ZETA", "ALPHA", "BETA"],
      },
      return: {
        asc: ["BETA", "ZETA", "ALPHA"],
        desc: ["ALPHA", "ZETA", "BETA"],
      },
    };

    expect(portfolio.positionSortKey.value).toBe("value");
    expect(portfolio.positionSortDirection.value).toBe("desc");
    expect(
      portfolio.sortedPositions.value.map((item) => item.instrument_id),
    ).toEqual(["ALPHA", "ZETA", "BETA"]);
    expect(portfolio.ariaSort("value")).toBe("descending");
    expect(portfolio.ariaSort("asset")).toBe("none");

    for (const key of Object.keys(expectedOrder) as CryptoPositionSortKey[]) {
      portfolio.sortPositions(key);
      expect(portfolio.positionSortKey.value).toBe(key);
      expect(portfolio.positionSortDirection.value).toBe("asc");
      expect(
        portfolio.sortedPositions.value.map((item) => item.instrument_id),
      ).toEqual(expectedOrder[key].asc);
      expect(portfolio.ariaSort(key)).toBe("ascending");
      portfolio.sortPositions(key);
      expect(portfolio.positionSortDirection.value).toBe("desc");
      expect(
        portfolio.sortedPositions.value.map((item) => item.instrument_id),
      ).toEqual(expectedOrder[key].desc);
      expect(portfolio.ariaSort(key)).toBe("descending");
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

    const nullableSortCases: Array<{
      key: CryptoPositionSortKey;
      positions: CryptoPosition[];
    }> = [
      {
        key: "currentPrice",
        positions: [
          makePosition({
            instrument_id: "NULL",
            name: "Null",
            current_price: null,
          }),
          makePosition({
            instrument_id: "LOW",
            name: "Low",
            current_price: 10,
          }),
          makePosition({
            instrument_id: "HIGH",
            name: "High",
            current_price: 20,
          }),
        ],
      },
      {
        key: "value",
        positions: [
          makePosition({
            instrument_id: "NULL",
            name: "Null",
            current_value: null,
          }),
          makePosition({
            instrument_id: "LOW",
            name: "Low",
            current_value: 10,
          }),
          makePosition({
            instrument_id: "HIGH",
            name: "High",
            current_value: 20,
          }),
        ],
      },
      {
        key: "pnl",
        positions: [
          makePosition({
            instrument_id: "NULL",
            name: "Null",
            unrealized_pnl: null,
          }),
          makePosition({
            instrument_id: "LOW",
            name: "Low",
            unrealized_pnl: -10,
          }),
          makePosition({
            instrument_id: "HIGH",
            name: "High",
            unrealized_pnl: 20,
          }),
        ],
      },
    ];
    for (const { key, positions: nullablePositions } of nullableSortCases) {
      const nullablePortfolio = createPortfolio({
        positions: nullablePositions,
      });
      nullablePortfolio.sortPositions(key);
      expect(
        nullablePortfolio.sortedPositions.value.at(-1)?.instrument_id,
      ).toBe("NULL");
      nullablePortfolio.sortPositions(key);
      expect(
        nullablePortfolio.sortedPositions.value.at(-1)?.instrument_id,
      ).toBe("NULL");
    }
  });

  it("uses the raw symbol when an instrument ticker is missing", () => {
    const missingTickerInstrumentId = "00000000-0000-0000-0000-000000000031";
    const knownTickerInstrumentId = "ffffffff-ffff-ffff-ffff-ffffffffffff";
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          instrument_id: missingTickerInstrumentId,
          name: "Missing ticker",
        }),
        makePosition({
          instrument_id: knownTickerInstrumentId,
          name: "Known ticker",
        }),
      ],
      instruments: [
        makeInstrument({
          id: missingTickerInstrumentId,
          identifiers: [
            {
              scheme: "crypto_symbol",
              value: "ZZ9",
              venue: "",
              is_primary: true,
            },
          ],
        }),
        makeInstrument({
          id: knownTickerInstrumentId,
          identifiers: [
            {
              scheme: "crypto_symbol",
              value: "KNOWN",
              venue: "",
              is_primary: true,
            },
            { scheme: "yahoo", value: "A1", venue: "", is_primary: true },
          ],
        }),
      ],
    });

    portfolio.sortPositions("ticker");
    expect(
      portfolio.sortedPositions.value.map((item) => item.instrument_id),
    ).toEqual([knownTickerInstrumentId, missingTickerInstrumentId]);
  });

  it("uses numeric crypto ticker collation and recomputes locale-sensitive names", () => {
    const numericPortfolio = createPortfolio({
      positions: [
        makePosition({ instrument_id: "A2", name: "A2" }),
        makePosition({ instrument_id: "A10", name: "A10" }),
      ],
      instruments: [
        makeInstrument({
          identifiers: [
            {
              scheme: "crypto_symbol",
              value: "A2",
              venue: "",
              is_primary: true,
            },
            { scheme: "yahoo", value: "A2", venue: "", is_primary: true },
          ],
        }),
        makeInstrument({
          identifiers: [
            {
              scheme: "crypto_symbol",
              value: "A10",
              venue: "",
              is_primary: true,
            },
            { scheme: "yahoo", value: "A10", venue: "", is_primary: true },
          ],
        }),
      ],
    });
    numericPortfolio.sortPositions("ticker");
    expect(
      numericPortfolio.sortedPositions.value.map((item) => item.instrument_id),
    ).toEqual(["A2", "A10"]);

    const localeNames = ["ñ", "n"];
    const englishCollator = new Intl.Collator("en", {
      sensitivity: "base",
      numeric: true,
    });
    const spanishCollator = new Intl.Collator("es", {
      sensitivity: "base",
      numeric: true,
    });
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
});
