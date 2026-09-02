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
    symbol: "CRYPTO-1",
    nombre: "Crypto 1",
    titulos: 2,
    coste_total: 100,
    precio_actual: 60,
    valor_actual: 120,
    pnl: 20,
    pnl_realizada: 5,
    ...overrides,
  };
}

function makeOrder(overrides: Partial<CryptoOrder> = {}): CryptoOrder {
  return {
    operacion_id: "operation-1",
    fecha_operacion: "2026-01-01",
    titulos: 1,
    importe_neto: 100,
    cuenta_id: "00000000-0000-0000-0000-000000000001",
    tipo_operacion: "Compra",
    symbol: "CRYPTO-1",
    nombre_activo: "Crypto 1",
    precio_compra: 100,
    comision: 1,
    ...overrides,
  };
}

function makeInstrument(
  overrides: Partial<CryptoInstrument> = {},
): CryptoInstrument {
  return {
    symbol: "CRYPTO-1",
    ticker: "CRYPTO1",
    nombre: "Crypto 1",
    ...overrides,
  };
}

function createPortfolio({
  positions: positionRows = [],
  orders: orderRows = [],
  instruments: instrumentRows = [],
  selectedSymbol: selectedAsset = "",
  baseCurrency: currency = "EUR",
  locale: currentLocale = "en",
}: {
  positions?: CryptoPosition[];
  orders?: CryptoOrder[];
  instruments?: CryptoInstrument[];
  selectedSymbol?: string;
  baseCurrency?: string;
  locale?: string;
} = {}) {
  const positions = ref(positionRows);
  const orders = ref(orderRows);
  const instruments = ref(instrumentRows);
  const selectedSymbol = ref(selectedAsset);
  const baseCurrency = ref(currency);
  const locale = ref(currentLocale);
  const portfolio = useCryptoPortfolio({
    positions,
    orders,
    instruments,
    selectedSymbol,
    baseCurrency,
    locale,
  });
  return {
    ...portfolio,
    positions,
    orders,
    instruments,
    selectedSymbol,
    baseCurrency,
    locale,
  };
}

describe("useCryptoPortfolio", () => {
  it("filters positive positions, sorts by value, and limits the top five", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({ symbol: "CRYPTO-1", valor_actual: 100 }),
        makePosition({ symbol: "CRYPTO-2", valor_actual: 600 }),
        makePosition({ symbol: "CRYPTO-3", valor_actual: 500 }),
        makePosition({ symbol: "CRYPTO-4", valor_actual: 400 }),
        makePosition({ symbol: "CRYPTO-5", valor_actual: 300 }),
        makePosition({ symbol: "CRYPTO-6", valor_actual: 200 }),
        makePosition({ symbol: "NULL-VALUE", valor_actual: null }),
        makePosition({
          symbol: "CLOSED",
          nombre: "Closed",
          titulos: 0,
          valor_actual: 900,
        }),
      ],
    });

    expect(portfolio.openPositions.value.map((item) => item.symbol)).toEqual([
      "CRYPTO-2",
      "CRYPTO-3",
      "CRYPTO-4",
      "CRYPTO-5",
      "CRYPTO-6",
      "CRYPTO-1",
      "NULL-VALUE",
    ]);
    expect(portfolio.topPositions.value.map((item) => item.symbol)).toEqual([
      "CRYPTO-2",
      "CRYPTO-3",
      "CRYPTO-4",
      "CRYPTO-5",
      "CRYPTO-6",
    ]);
  });

  it("calculates open totals and keeps server realized P&L for every position", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          symbol: "OPEN-1",
          coste_total: 1000,
          valor_actual: 1200,
          pnl: 200,
          pnl_realizada: 11,
        }),
        makePosition({
          symbol: "OPEN-2",
          coste_total: 500,
          valor_actual: null,
          pnl: null,
          pnl_realizada: -3,
        }),
        makePosition({
          symbol: "CLOSED",
          titulos: 0,
          coste_total: 900,
          valor_actual: 900,
          pnl: 100,
          pnl_realizada: 25,
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
      makePosition({ coste_total: 0, valor_actual: 10, pnl: 5 }),
    ];
    expect(portfolio.openReturn.value).toBe(0);
  });

  it("normalizes matching and missing instruments and reacts to source currencies", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          symbol: "USD-COIN",
          nombre: "Dollar coin",
          precio_actual: null,
          valor_actual: null,
          pnl: null,
          moneda: "USD",
          moneda_base: "EUR",
        }),
        makePosition({
          symbol: "MISSING",
          nombre: "Missing instrument",
          titulos: 1,
          valor_actual: 90,
          moneda: "EUR",
        }),
      ],
      instruments: [
        makeInstrument({
          symbol: "USD-COIN",
          ticker: "USDCOIN",
          nombre: "Dollar coin",
          moneda: "USD",
        }),
      ],
      baseCurrency: "EUR",
    });

    const normalized = portfolio.normalizedTopPositions.value;
    const dollarCoin = normalized.find((item) => item.assetId === "USD-COIN");
    const missing = normalized.find((item) => item.assetId === "MISSING");
    expect(dollarCoin).toMatchObject({
      kind: "crypto",
      name: "Dollar coin",
      currentPrice: null,
      currentValue: null,
      unrealizedPnl: null,
      currency: "EUR",
      baseCurrency: "EUR",
    });
    expect(dollarCoin?.metadata).toMatchObject({
      ticker: "USDCOIN",
      symbol: "USD-COIN",
      originalCurrency: "USD",
    });
    expect(missing).toMatchObject({
      name: "Missing instrument",
      assetId: "MISSING",
      currentValue: 90,
    });
    expect(missing?.metadata).toMatchObject({ ticker: null });

    portfolio.instruments.value[0] = makeInstrument({
      symbol: "USD-COIN",
      ticker: "USDCOIN-UPDATED",
      nombre: "Dollar coin",
      moneda: "USD",
    });
    portfolio.positions.value[0] = makePosition({
      symbol: "USD-COIN",
      nombre: "Dollar coin",
      precio_actual: null,
      valor_actual: null,
      pnl: null,
      moneda: "USD",
      moneda_base: undefined,
    });
    portfolio.baseCurrency.value = "USD";
    expect(
      portfolio.normalizedTopPositions.value.find(
        (item) => item.assetId === "USD-COIN",
      ),
    ).toMatchObject({
      currency: "USD",
      baseCurrency: "USD",
      metadata: { ticker: "USDCOIN-UPDATED" },
    });
  });

  it("keeps confusable symbols distinct across selection, orders, normalization, and sorting", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({ symbol: "BTC", nombre: "Bitcoin", valor_actual: 300 }),
        makePosition({
          symbol: "BTC-EUR",
          nombre: "Bitcoin pair",
          valor_actual: 200,
        }),
        makePosition({
          symbol: "btc",
          nombre: "Lowercase bitcoin",
          valor_actual: 100,
        }),
      ],
      orders: [
        makeOrder({ symbol: "BTC", operacion_id: "btc-order" }),
        makeOrder({ symbol: "BTC-EUR", operacion_id: "pair-order" }),
        makeOrder({ symbol: "btc", operacion_id: "lowercase-order" }),
      ],
      instruments: [
        makeInstrument({ symbol: "BTC", ticker: "000" }),
        makeInstrument({ symbol: "BTC-EUR", ticker: "100" }),
      ],
      selectedSymbol: "BTC-EUR",
    });

    expect(portfolio.selectedPosition.value?.symbol).toBe("BTC-EUR");
    expect(
      portfolio.selectedOrders.value.map((item) => item.operacion_id),
    ).toEqual(["pair-order"]);
    expect(
      portfolio.normalizedTopPositions.value.map((item) => item.assetId),
    ).toEqual(["BTC", "BTC-EUR", "btc"]);
    expect(
      portfolio.normalizedTopPositions.value.find(
        (item) => item.assetId === "BTC",
      )?.metadata.ticker,
    ).toBe("000");
    expect(
      portfolio.normalizedTopPositions.value.find(
        (item) => item.assetId === "BTC-EUR",
      )?.metadata.ticker,
    ).toBe("100");
    expect(
      portfolio.normalizedTopPositions.value.find(
        (item) => item.assetId === "btc",
      )?.metadata.ticker,
    ).toBeNull();

    portfolio.sortPositions("ticker");
    expect(portfolio.sortedPositions.value.map((item) => item.symbol)).toEqual([
      "BTC",
      "BTC-EUR",
      "btc",
    ]);

    portfolio.selectedSymbol.value = "btc";
    expect(portfolio.selectedPosition.value?.symbol).toBe("btc");
    expect(
      portfolio.selectedOrders.value.map((item) => item.operacion_id),
    ).toEqual(["lowercase-order"]);
  });

  it("tracks selected positions and orders and projects chart currency fallbacks without mutation", () => {
    const zeroBaseOrder = makeOrder({
      operacion_id: "zero-base",
      symbol: "CNE100000296",
      nombre_activo: "Crypto split-like symbol",
      titulos: 1,
      importe_neto: 80,
      importe_base: 0,
      precio_compra: 40,
      precio_base: 0,
      comision: 0.8,
      comision_base: 0,
    });
    const fallbackOrder = makeOrder({
      operacion_id: "fallback",
      symbol: "CNE100000296",
      importe_neto: 90,
      precio_compra: 45,
      comision: 0.9,
    });
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          symbol: "CNE100000296",
          nombre: "Crypto split-like symbol",
          titulos: 1,
          coste_total: 40,
        }),
      ],
      orders: [zeroBaseOrder, fallbackOrder],
      selectedSymbol: "CNE100000296",
    });

    expect(portfolio.selectedPosition.value?.symbol).toBe("CNE100000296");
    expect(
      portfolio.selectedOrders.value.map((item) => item.operacion_id),
    ).toEqual(["zero-base", "fallback"]);
    expect(portfolio.selectedChartOrders.value).toEqual([
      {
        ...zeroBaseOrder,
        operacion_id: "zero-base",
        precio_compra: 0,
        importe_neto: 0,
        comision: 0,
      },
      {
        ...fallbackOrder,
        operacion_id: "fallback",
        precio_compra: 45,
        importe_neto: 90,
        comision: 0.9,
      },
    ]);
    expect(portfolio.selectedChartOrders.value[0]).not.toBe(zeroBaseOrder);
    expect(portfolio.selectedChartOrders.value[0]).not.toHaveProperty(
      "chartAdjustment",
    );
    expect(zeroBaseOrder).toMatchObject({
      titulos: 1,
      precio_compra: 40,
      importe_neto: 80,
      comision: 0.8,
    });
    expect(portfolio.basePrice(zeroBaseOrder)).toBe(0);
    expect(portfolio.baseAmount(zeroBaseOrder)).toBe(0);
    expect(portfolio.baseFee(zeroBaseOrder)).toBe(0);
    expect(portfolio.basePrice(fallbackOrder)).toBe(45);
    expect(portfolio.baseAmount(fallbackOrder)).toBe(90);
    expect(portfolio.baseFee(fallbackOrder)).toBe(0.9);
    // Crypto orders do not receive the stock-only BYD split adjustment.
    expect(portfolio.selectedChartOrders.value[0].titulos).toBe(1);
  });

  it("reacts to selection, order, and price changes and averages only open positions", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({ symbol: "BTC", coste_total: 100, titulos: 2 }),
        makePosition({
          symbol: "ETH",
          nombre: "Ethereum",
          coste_total: 200,
          titulos: 0,
          precio_actual: null,
        }),
      ],
      orders: [
        makeOrder({ symbol: "BTC" }),
        makeOrder({ symbol: "ETH", operacion_id: "operation-2" }),
      ],
      selectedSymbol: "BTC",
    });

    expect(portfolio.selectedPosition.value?.symbol).toBe("BTC");
    expect(portfolio.selectedOrders.value).toHaveLength(1);
    expect(portfolio.averagePrice.value).toBe(50);
    expect(portfolio.pricedPositions.value).toBe(1);

    portfolio.selectedSymbol.value = "ETH";
    expect(portfolio.selectedPosition.value?.symbol).toBe("ETH");
    expect(portfolio.selectedOrders.value[0].symbol).toBe("ETH");
    expect(portfolio.averagePrice.value).toBeNull();

    portfolio.orders.value = [
      makeOrder({ symbol: "ETH", operacion_id: "operation-3" }),
      makeOrder({ symbol: "ETH", operacion_id: "operation-4" }),
    ];
    expect(portfolio.selectedOrders.value).toHaveLength(2);

    portfolio.positions.value[1] = makePosition({
      symbol: "ETH",
      nombre: "Ethereum",
      titulos: 2,
      precio_actual: 70,
    });
    expect(portfolio.pricedPositions.value).toBe(2);
    expect(portfolio.averagePrice.value).toBe(50);
  });

  it("sorts every key with nulls last, stable name ties, and initial/toggle directions", () => {
    const positions = [
      makePosition({
        symbol: "ZETA",
        nombre: "Zeta",
        titulos: 3,
        coste_total: 300,
        precio_actual: 60,
        valor_actual: 180,
        pnl: 30,
      }),
      makePosition({
        symbol: "ALPHA",
        nombre: "Alpha",
        titulos: 2,
        coste_total: 100,
        precio_actual: 120,
        valor_actual: 240,
        pnl: 20,
      }),
      makePosition({
        symbol: "BETA",
        nombre: "Beta",
        titulos: 2,
        coste_total: 200,
        precio_actual: 50,
        valor_actual: 100,
        pnl: -20,
      }),
    ];
    const portfolio = createPortfolio({
      positions,
      instruments: [
        makeInstrument({ symbol: "ZETA", ticker: "ZZ" }),
        makeInstrument({ symbol: "ALPHA", ticker: "AA" }),
        makeInstrument({ symbol: "BETA", ticker: "MM" }),
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
    expect(portfolio.sortedPositions.value.map((item) => item.symbol)).toEqual([
      "ALPHA",
      "ZETA",
      "BETA",
    ]);
    expect(portfolio.ariaSort("value")).toBe("descending");
    expect(portfolio.ariaSort("asset")).toBe("none");

    for (const key of Object.keys(expectedOrder) as CryptoPositionSortKey[]) {
      portfolio.sortPositions(key);
      expect(portfolio.positionSortKey.value).toBe(key);
      expect(portfolio.positionSortDirection.value).toBe("asc");
      expect(
        portfolio.sortedPositions.value.map((item) => item.symbol),
      ).toEqual(expectedOrder[key].asc);
      expect(portfolio.ariaSort(key)).toBe("ascending");
      portfolio.sortPositions(key);
      expect(portfolio.positionSortDirection.value).toBe("desc");
      expect(
        portfolio.sortedPositions.value.map((item) => item.symbol),
      ).toEqual(expectedOrder[key].desc);
      expect(portfolio.ariaSort(key)).toBe("descending");
    }

    const nullPortfolio = createPortfolio({
      positions: [
        makePosition({
          symbol: "NULL",
          nombre: "Null value",
          valor_actual: null,
        }),
        makePosition({ symbol: "BETA", nombre: "Beta", valor_actual: 100 }),
        makePosition({ symbol: "ALPHA", nombre: "Alpha", valor_actual: 100 }),
      ],
    });
    expect(
      nullPortfolio.sortedPositions.value.map((item) => item.symbol),
    ).toEqual(["ALPHA", "BETA", "NULL"]);
    nullPortfolio.sortPositions("value");
    expect(
      nullPortfolio.sortedPositions.value.map((item) => item.symbol),
    ).toEqual(["ALPHA", "BETA", "NULL"]);
    expect(nullPortfolio.ariaSort("value")).toBe("ascending");

    const nullableSortCases: Array<{
      key: CryptoPositionSortKey;
      positions: CryptoPosition[];
    }> = [
      {
        key: "currentPrice",
        positions: [
          makePosition({ symbol: "NULL", nombre: "Null", precio_actual: null }),
          makePosition({ symbol: "LOW", nombre: "Low", precio_actual: 10 }),
          makePosition({ symbol: "HIGH", nombre: "High", precio_actual: 20 }),
        ],
      },
      {
        key: "value",
        positions: [
          makePosition({ symbol: "NULL", nombre: "Null", valor_actual: null }),
          makePosition({ symbol: "LOW", nombre: "Low", valor_actual: 10 }),
          makePosition({ symbol: "HIGH", nombre: "High", valor_actual: 20 }),
        ],
      },
      {
        key: "pnl",
        positions: [
          makePosition({ symbol: "NULL", nombre: "Null", pnl: null }),
          makePosition({ symbol: "LOW", nombre: "Low", pnl: -10 }),
          makePosition({ symbol: "HIGH", nombre: "High", pnl: 20 }),
        ],
      },
    ];
    for (const { key, positions: nullablePositions } of nullableSortCases) {
      const nullablePortfolio = createPortfolio({
        positions: nullablePositions,
      });
      nullablePortfolio.sortPositions(key);
      expect(nullablePortfolio.sortedPositions.value.at(-1)?.symbol).toBe(
        "NULL",
      );
      nullablePortfolio.sortPositions(key);
      expect(nullablePortfolio.sortedPositions.value.at(-1)?.symbol).toBe(
        "NULL",
      );
    }
  });

  it("uses the raw symbol when an instrument ticker is missing", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({ symbol: "ZZ9", nombre: "Missing ticker" }),
        makePosition({ symbol: "KNOWN", nombre: "Known ticker" }),
      ],
      instruments: [makeInstrument({ symbol: "KNOWN", ticker: "A1" })],
    });

    portfolio.sortPositions("ticker");
    expect(portfolio.sortedPositions.value.map((item) => item.symbol)).toEqual([
      "KNOWN",
      "ZZ9",
    ]);
  });

  it("uses numeric crypto ticker collation and recomputes locale-sensitive names", () => {
    const numericPortfolio = createPortfolio({
      positions: [
        makePosition({ symbol: "A2", nombre: "A2" }),
        makePosition({ symbol: "A10", nombre: "A10" }),
      ],
      instruments: [
        makeInstrument({ symbol: "A2", ticker: "A2" }),
        makeInstrument({ symbol: "A10", ticker: "A10" }),
      ],
    });
    numericPortfolio.sortPositions("ticker");
    expect(
      numericPortfolio.sortedPositions.value.map((item) => item.symbol),
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
        makePosition({ symbol: "TILDE", nombre: "ñ" }),
        makePosition({ symbol: "PLAIN", nombre: "n" }),
      ],
    });
    localePortfolio.sortPositions("asset");
    expect(
      localePortfolio.sortedPositions.value.map((item) => item.nombre),
    ).toEqual(englishOrder);
    localePortfolio.locale.value = "es";
    expect(
      localePortfolio.sortedPositions.value.map((item) => item.nombre),
    ).toEqual(spanishOrder);
  });
});
