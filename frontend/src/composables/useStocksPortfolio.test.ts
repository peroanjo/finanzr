import { ref } from "vue";
import { describe, expect, it } from "vitest";
import { useStocksPortfolio } from "./useStocksPortfolio";
import type { StockPositionSortKey } from "./useStocksPortfolio";
import type { StockInstrument, StockOrder, StockPosition } from "../types/api";

function makePosition(overrides: Partial<StockPosition> = {}): StockPosition {
  return {
    isin: "STOCK-1",
    nombre: "Stock 1",
    titulos: 2,
    coste_total: 100,
    precio_actual: 60,
    valor_actual: 120,
    pnl: 20,
    pnl_realizada: 5,
    ...overrides,
  };
}

function makeOrder(overrides: Partial<StockOrder> = {}): StockOrder {
  return {
    operacion_id: "operation-1",
    fecha_operacion: "2026-01-01",
    titulos: 1,
    importe_neto: 100,
    cuenta_id: 1,
    tipo_operacion: "Compra",
    isin: "STOCK-1",
    nombre_activo: "Stock 1",
    precio_compra: 100,
    comision: 1,
    es_saveback: false,
    ...overrides,
  };
}

function makeInstrument(
  overrides: Partial<StockInstrument> = {},
): StockInstrument {
  return {
    isin: "STOCK-1",
    ticker: "STK1",
    nombre: "Stock 1",
    ...overrides,
  };
}

function createPortfolio({
  positions: positionRows = [],
  orders: orderRows = [],
  instruments: instrumentRows = [],
  selectedIsin: selectedAsset = "",
  baseCurrency: currency = "EUR",
  locale: currentLocale = "en",
}: {
  positions?: StockPosition[];
  orders?: StockOrder[];
  instruments?: StockInstrument[];
  selectedIsin?: string;
  baseCurrency?: string;
  locale?: string;
} = {}) {
  const positions = ref(positionRows);
  const orders = ref(orderRows);
  const instruments = ref(instrumentRows);
  const selectedIsin = ref(selectedAsset);
  const baseCurrency = ref(currency);
  const locale = ref(currentLocale);
  const portfolio = useStocksPortfolio({
    positions,
    orders,
    instruments,
    selectedIsin,
    baseCurrency,
    locale,
  });
  return {
    ...portfolio,
    positions,
    orders,
    instruments,
    selectedIsin,
    baseCurrency,
    locale,
  };
}

describe("useStocksPortfolio", () => {
  it("filters open positions by positive quantity and limits the top five", () => {
    const positions = [
      makePosition({ isin: "STOCK-1", valor_actual: 100 }),
      makePosition({ isin: "STOCK-2", valor_actual: 600 }),
      makePosition({ isin: "STOCK-3", valor_actual: 500 }),
      makePosition({ isin: "STOCK-4", valor_actual: 400 }),
      makePosition({ isin: "STOCK-5", valor_actual: 300 }),
      makePosition({ isin: "STOCK-6", valor_actual: 200 }),
      makePosition({
        isin: "CLOSED",
        nombre: "Closed",
        titulos: 0,
        valor_actual: 900,
      }),
    ];
    const portfolio = createPortfolio({ positions });

    expect(portfolio.openPositions.value.map((item) => item.isin)).toEqual([
      "STOCK-2",
      "STOCK-3",
      "STOCK-4",
      "STOCK-5",
      "STOCK-6",
      "STOCK-1",
    ]);
    expect(portfolio.topPositions.value.map((item) => item.isin)).toEqual([
      "STOCK-2",
      "STOCK-3",
      "STOCK-4",
      "STOCK-5",
      "STOCK-6",
    ]);
  });

  it("calculates totals from open positions and realized P&L from every position", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          isin: "OPEN-1",
          coste_total: 1000,
          valor_actual: 1200,
          pnl: 200,
          pnl_realizada: 11,
        }),
        makePosition({
          isin: "OPEN-2",
          coste_total: 500,
          valor_actual: null,
          pnl: null,
          pnl_realizada: -3,
        }),
        makePosition({
          isin: "CLOSED",
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

  it("normalizes matching and missing instruments with nullable values and base currency", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({
          isin: "USD-STOCK",
          nombre: "Dollar stock",
          precio_actual: null,
          valor_actual: null,
          pnl: null,
          moneda: "USD",
          moneda_base: "EUR",
        }),
        makePosition({
          isin: "MISSING",
          nombre: "Missing instrument",
          titulos: 1,
          valor_actual: 90,
          moneda: "EUR",
        }),
      ],
      instruments: [
        makeInstrument({
          isin: "USD-STOCK",
          ticker: "USDSTK",
          nombre: "Dollar stock",
          moneda: "USD",
        }),
      ],
      baseCurrency: "EUR",
    });

    const normalized = portfolio.normalizedTopPositions.value;
    const dollarStock = normalized.find((item) => item.assetId === "USD-STOCK");
    const missing = normalized.find((item) => item.assetId === "MISSING");
    expect(dollarStock).toMatchObject({
      kind: "stock",
      name: "Dollar stock",
      currentPrice: null,
      currentValue: null,
      unrealizedPnl: null,
      currency: "EUR",
      baseCurrency: "EUR",
    });
    expect(dollarStock?.metadata).toMatchObject({
      ticker: "USDSTK",
      originalCurrency: "USD",
    });
    expect(missing).toMatchObject({
      name: "Missing instrument",
      assetId: "MISSING",
      currentValue: 90,
    });
    expect(missing?.metadata).toMatchObject({ ticker: null });

    portfolio.instruments.value[0] = makeInstrument({
      isin: "USD-STOCK",
      ticker: "USDSTK-UPDATED",
      nombre: "Dollar stock",
      moneda: "USD",
    });
    portfolio.positions.value[0] = makePosition({
      isin: "USD-STOCK",
      nombre: "Dollar stock",
      precio_actual: null,
      valor_actual: null,
      pnl: null,
      moneda: "USD",
      moneda_base: undefined,
    });
    portfolio.baseCurrency.value = "USD";
    expect(
      portfolio.normalizedTopPositions.value.find(
        (item) => item.assetId === "USD-STOCK",
      ),
    ).toMatchObject({
      currency: "USD",
      baseCurrency: "USD",
      metadata: { ticker: "USDSTK-UPDATED" },
    });
  });

  it("reacts to selection and source changes while counting only priced positions", () => {
    const portfolio = createPortfolio({
      positions: [
        makePosition({ isin: "STOCK-A", nombre: "Stock A" }),
        makePosition({
          isin: "STOCK-B",
          nombre: "Stock B",
          precio_actual: null,
        }),
      ],
      orders: [
        makeOrder({ isin: "STOCK-A" }),
        makeOrder({ isin: "STOCK-B", operacion_id: "operation-2" }),
      ],
      selectedIsin: "STOCK-A",
    });

    expect(portfolio.selectedPosition.value?.isin).toBe("STOCK-A");
    expect(portfolio.selectedOrders.value).toHaveLength(1);
    expect(portfolio.averagePrice.value).toBe(50);
    expect(portfolio.pricedPositions.value).toBe(1);

    portfolio.selectedIsin.value = "STOCK-B";
    expect(portfolio.selectedPosition.value?.isin).toBe("STOCK-B");
    expect(portfolio.selectedOrders.value[0].isin).toBe("STOCK-B");
    expect(portfolio.averagePrice.value).toBe(50);

    portfolio.orders.value = [
      makeOrder({ isin: "STOCK-B", operacion_id: "operation-3" }),
      makeOrder({ isin: "STOCK-B", operacion_id: "operation-4" }),
    ];
    expect(portfolio.selectedOrders.value).toHaveLength(2);

    portfolio.positions.value[1] = makePosition({
      isin: "STOCK-B",
      precio_actual: 70,
    });
    expect(portfolio.pricedPositions.value).toBe(2);
  });

  it("uses base currency fallbacks and preserves source orders before chart fixes", () => {
    const sourceWithBase = makeOrder({
      operacion_id: "byd-before-split",
      isin: "CNE100000296",
      fecha_operacion: "2025-02-03",
      titulos: 1,
      importe_neto: 34.07,
      importe_base: 30,
      precio_compra: 34.07,
      precio_base: 30,
      comision: 1,
      comision_base: 0.5,
    });
    const sourceWithoutBase = makeOrder({
      operacion_id: "fallback",
      importe_neto: 80,
      precio_compra: 40,
      comision: 0.8,
    });
    const sourceWithZeroBase = makeOrder({
      operacion_id: "zero-base",
      isin: "ZERO-BASE",
      importe_neto: 80,
      importe_base: 0,
      precio_compra: 40,
      precio_base: 0,
      comision: 0.8,
      comision_base: 0,
    });
    const portfolio = createPortfolio({
      orders: [sourceWithBase, sourceWithoutBase, sourceWithZeroBase],
      selectedIsin: "CNE100000296",
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
      importe_neto: 30,
      precio_compra: 10,
      comision: 0.5,
      titulos: 3,
      chartAdjustment: {
        id: "byd-pre-june-10-2025-split-3-to-1",
      },
    });
    expect(sourceWithBase).toMatchObject({
      importe_neto: 34.07,
      precio_compra: 34.07,
      titulos: 1,
    });

    portfolio.selectedIsin.value = "ZERO-BASE";
    expect(portfolio.selectedChartOrders.value[0]).toMatchObject({
      importe_neto: 0,
      precio_compra: 0,
      comision: 0,
      titulos: 1,
    });

    portfolio.selectedIsin.value = "STOCK-1";
    expect(portfolio.selectedChartOrders.value[0]).toMatchObject({
      importe_neto: 80,
      precio_compra: 40,
      comision: 0.8,
    });
  });

  it("sorts every stock column with null ordering, locale collation, and tie breaks", () => {
    const positions = [
      makePosition({
        isin: "ZETA",
        nombre: "Zeta",
        titulos: 4,
        coste_total: 400,
        precio_actual: 40,
        valor_actual: 160,
        pnl: 40,
      }),
      makePosition({
        isin: "ALPHA",
        nombre: "Alpha",
        titulos: 1,
        coste_total: 100,
        precio_actual: 100,
        valor_actual: 100,
        pnl: 10,
      }),
      makePosition({
        isin: "BETA",
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
        makeInstrument({ isin: "ZETA", ticker: "ZZ" }),
        makeInstrument({ isin: "ALPHA", ticker: "AA" }),
        makeInstrument({ isin: "BETA", ticker: "MM" }),
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
      expect(portfolio.sortedPositions.value.map((item) => item.isin)).toEqual(
        expected,
      );
      expect(portfolio.ariaSort(key)).toBe("ascending");
    }

    const nullPortfolio = createPortfolio({
      positions: [
        makePosition({
          isin: "NULL",
          nombre: "Null value",
          valor_actual: null,
        }),
        makePosition({ isin: "BETA", nombre: "Beta", valor_actual: 100 }),
        makePosition({ isin: "ALPHA", nombre: "Alpha", valor_actual: 100 }),
      ],
    });
    expect(
      nullPortfolio.sortedPositions.value.map((item) => item.isin),
    ).toEqual(["ALPHA", "BETA", "NULL"]);
    nullPortfolio.sortPositions("value");
    expect(
      nullPortfolio.sortedPositions.value.map((item) => item.isin),
    ).toEqual(["ALPHA", "BETA", "NULL"]);
    expect(nullPortfolio.ariaSort("value")).toBe("ascending");
    nullPortfolio.sortPositions("value");
    expect(nullPortfolio.positionSortDirection.value).toBe("desc");
    expect(nullPortfolio.ariaSort("value")).toBe("descending");
    expect(nullPortfolio.sortedPositions.value.at(-1)?.isin).toBe("NULL");
  });

  it("keeps ticker collation nonnumeric and recomputes names when locale changes", () => {
    const numericPortfolio = createPortfolio({
      positions: [
        makePosition({ isin: "A2", nombre: "A2" }),
        makePosition({ isin: "A10", nombre: "A10" }),
      ],
      instruments: [
        makeInstrument({ isin: "A2", ticker: "A2" }),
        makeInstrument({ isin: "A10", ticker: "A10" }),
      ],
    });
    numericPortfolio.sortPositions("ticker");
    expect(
      numericPortfolio.sortedPositions.value.map((item) => item.isin),
    ).toEqual(["A10", "A2"]);

    const localeNames = ["ñ", "n"];
    const englishCollator = new Intl.Collator("en", { sensitivity: "base" });
    const spanishCollator = new Intl.Collator("es", { sensitivity: "base" });
    const englishOrder = [...localeNames].sort(englishCollator.compare);
    const spanishOrder = [...localeNames].sort(spanishCollator.compare);
    expect(englishOrder).not.toEqual(spanishOrder);

    const localePortfolio = createPortfolio({
      positions: [
        makePosition({ isin: "TILDE", nombre: "ñ" }),
        makePosition({ isin: "PLAIN", nombre: "n" }),
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
