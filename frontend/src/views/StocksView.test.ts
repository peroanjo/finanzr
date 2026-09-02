import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import ImportStatementDialog from "../components/ImportStatementDialog.vue";
import { applyLocale, applyReportingCurrency, registerMessages } from "../i18n";
import { stocksMessages } from "../i18n/stocksMessages";
import type { StockOrder } from "../types/api";
import StocksView from "./StocksView.vue";

registerMessages(stocksMessages);

vi.mock("../api/client", () => ({
  api: vi.fn(),
  json: (method: string, body: unknown) => ({
    method,
    body: JSON.stringify(body),
  }),
}));
vi.mock("../components/CryptoCandlestickChart.vue", () => ({
  default: {
    props: ["points", "operations", "averagePrice", "operationMarkerShape"],
    template:
      '<div data-testid="stock-chart" :data-marker-shape="operationMarkerShape">{{ points.length }}-{{ operations.length }}</div>',
  },
}));
vi.mock("../components/FundPerformanceChart.vue", () => ({
  default: {
    props: ["points", "mode"],
    template:
      '<div data-testid="stock-performance-chart">{{ points.length }}-{{ mode }}</div>',
  },
}));
vi.mock("../components/ImportPanel.vue", () => ({
  default: { template: '<div data-testid="stock-import" />' },
}));

const apiMock = vi.mocked(api);
const stockImporter = {
  slug: "trade_republic",
  display_name: "Trade Republic Transactions",
  target: "stock_orders",
  target_label: "Acciones y ETF",
  description: "Importa transacciones.",
  source_instructions: "",
  input_kind: "records",
  accepted_extensions: [".csv"],
  required_fields: [],
  formats: [
    { extension: ".csv", label: "CSV de transacciones", description: "" },
  ],
  fields: [],
  rules: [],
};
const accountOneId = "00000000-0000-0000-0000-000000000001";
const accountTwoId = "00000000-0000-0000-0000-000000000002";
const account = {
  id: accountOneId,
  name: "Trade Republic",
  platform: "Trade Republic",
  type: "",
  currency: "EUR",
  importer_slug: "trade_republic",
  importer_name: "Trade Republic Transactions",
};
const secondAccount = {
  id: accountTwoId,
  name: "Second account",
  platform: "Broker Two",
  type: "",
  currency: "EUR",
  importer_slug: "trade_republic",
  importer_name: "Trade Republic Transactions",
};
const position = {
  isin: "US67066G1040",
  nombre: "NVIDIA",
  titulos: 1,
  coste_total: 100,
  precio_actual: 185,
  valor_actual: 185,
  pnl: 85,
  pnl_realizada: 10,
};
const secondAccountPosition = {
  ...position,
  isin: "SECOND",
  nombre: "Second account stock",
  valor_actual: 275,
  precio_actual: 275,
  pnl: 25,
};
const stockPositions = [
  position,
  ...[170, 160, 150, 140, 130].map((value, index) => ({
    isin: `TEST${index}`,
    nombre: `Test stock ${index}`,
    titulos: 1,
    coste_total: value - 10,
    precio_actual: value,
    valor_actual: value,
    pnl: 10,
    pnl_realizada: 0,
  })),
];
const order = {
  operacion_id: "stock-1",
  fecha_operacion: "2026-05-02",
  titulos: 1,
  importe_neto: 100,
  cuenta_id: accountOneId,
  cuenta_nombre: "Trade Republic",
  plataforma: "Trade Republic",
  tipo_operacion: "Compra",
  isin: "US67066G1040",
  nombre_activo: "NVIDIA",
  precio_compra: 100,
  comision: 1,
  es_saveback: true,
};
const stockOrders = [
  order,
  ...Array.from({ length: 15 }, (_, index) => ({
    ...order,
    operacion_id: `stock-${index + 2}`,
    fecha_operacion: `2026-04-${String(index + 1).padStart(2, "0")}`,
    isin: `TEST${index}`,
    nombre_activo: `Test stock ${index}`,
    es_saveback: false,
  })),
];
const closedPosition = {
  isin: "CLOSED",
  nombre: "Closed stock",
  titulos: 0,
  coste_total: 100,
  precio_actual: 120,
  valor_actual: 0,
  pnl: 0,
  pnl_realizada: 20,
};
const closedInstrument = {
  isin: closedPosition.isin,
  ticker: "CLOSED",
  nombre: closedPosition.nombre,
};
const secondAccountInstrument = {
  isin: secondAccountPosition.isin,
  ticker: "SECOND",
  nombre: secondAccountPosition.nombre,
};
const performance = {
  range: "1y",
  account_id: "all",
  moneda_base: "EUR",
  data: [
    { fecha: "2026-01-01", valor: 800, invertido: 800, pnl: 0, pnl_pct: 0 },
    {
      fecha: "2026-07-01",
      valor: 935,
      invertido: 800,
      pnl: 135,
      pnl_pct: 16.875,
    },
  ],
};
let positionsOverride: typeof stockPositions | null = null;
let ordersOverride: StockOrder[] | null = null;

describe("StocksView", () => {
  beforeEach(() => {
    HTMLDialogElement.prototype.showModal = vi.fn(function (
      this: HTMLDialogElement,
    ) {
      this.setAttribute("open", "");
    });
    HTMLDialogElement.prototype.close = vi.fn(function (
      this: HTMLDialogElement,
    ) {
      this.removeAttribute("open");
    });
    vi.stubGlobal("localStorage", {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    });
    applyReportingCurrency("EUR");
    applyLocale("es-ES");
    positionsOverride = null;
    ordersOverride = null;
    apiMock.mockClear();
    window.history.replaceState({}, "", "/app/acciones");
    apiMock.mockImplementation(async (path, init) => {
      if (path === "/stock-accounts") return [account, secondAccount];
      if (path === "/importers") return [stockImporter];
      if (
        path === "/stock-analysis?ignore_savebacks=true" ||
        path ===
          `/stock-analysis?account_id=${accountOneId}&ignore_savebacks=true`
      )
        return positionsOverride ?? stockPositions;
      if (
        path ===
        `/stock-analysis?account_id=${accountTwoId}&ignore_savebacks=true`
      )
        return [secondAccountPosition];
      if (
        path === "/stock-orders" ||
        path === `/stock-orders?account_id=${accountOneId}`
      )
        return ordersOverride ?? stockOrders;
      if (path === `/stock-orders?account_id=${accountTwoId}`)
        return [
          {
            ...order,
            operacion_id: "second-account-1",
            cuenta_id: secondAccount.id,
            cuenta_nombre: secondAccount.name,
            isin: secondAccountPosition.isin,
            nombre_activo: secondAccountPosition.nombre,
          },
        ];
      if (path === "/stocks")
        return [
          {
            isin: position.isin,
            ticker: "NVDA",
            nombre: position.nombre,
          },
          closedInstrument,
          secondAccountInstrument,
        ];
      if (path === "/stock-prices")
        return [
          {
            isin: position.isin,
            precio: 185,
            updated: "2026-07-21",
            moneda: "EUR",
            precio_orig: 185,
          },
        ];
      if (path.startsWith(`/stock-chart/${position.isin}?`))
        return {
          isin: position.isin,
          ticker: "NVDA",
          moneda: "EUR",
          range: "1y",
          data: [
            {
              fecha: "2026-01-01",
              precio: 100,
              open: 99,
              high: 102,
              low: 98,
              close: 100,
            },
            {
              fecha: "2026-07-01",
              precio: 185,
              open: 180,
              high: 188,
              low: 179,
              close: 185,
            },
          ],
        };
      if (path.startsWith(`/stock-chart/${closedPosition.isin}?`))
        return {
          isin: closedPosition.isin,
          ticker: closedInstrument.ticker,
          moneda: "EUR",
          range: "1y",
          data: [
            {
              fecha: "2026-01-01",
              precio: 100,
              open: 99,
              high: 102,
              low: 98,
              close: 100,
            },
          ],
        };
      if (path.startsWith(`/stock-chart/${secondAccountPosition.isin}?`))
        return {
          isin: secondAccountPosition.isin,
          ticker: secondAccountInstrument.ticker,
          moneda: "EUR",
          range: "1y",
          data: [
            {
              fecha: "2026-01-01",
              precio: 250,
              open: 249,
              high: 252,
              low: 248,
              close: 250,
            },
          ],
        };
      if (path === `/stocks/${position.isin}` && init?.method === "PUT")
        return {
          isin: position.isin,
          ticker: "NVDA",
          nombre: position.nombre,
        };
      if (path === `/stocks/${closedPosition.isin}` && init?.method === "PUT")
        return closedInstrument;
      if (path.startsWith("/investment-performance/stock?")) return performance;
      throw new Error(`Unexpected path: ${path}`);
    });
  });

  it("uses the canonical investment structure and expands one stock row on demand", async () => {
    const wrapper = mount(StocksView);
    await flushPromises();

    expect(wrapper.text()).toContain("Principales activos");
    expect(wrapper.text()).not.toContain("Editar activo");
    expect(
      wrapper.findAll('button[aria-label="Editar activo"]').length,
    ).toBeGreaterThan(0);
    const addAssetButton = wrapper.get('button[aria-label="Añadir activo"]');
    expect(addAssetButton.text()).toContain("Añadir activo");
    expect(addAssetButton.attributes("title")).toBe("Añadir activo");
    expect(addAssetButton.get("svg path").attributes("d")).toBe(
      "M10 4v12M4 10h12",
    );
    expect(wrapper.text()).toContain("KPIs de cartera");
    expect(wrapper.text()).toContain("Evolución de inversiones");
    expect(wrapper.text()).toContain("Movimientos");
    expect(wrapper.find(".position-table-scroll").exists()).toBe(true);
    expect(wrapper.findAll(".fund-asset-row")).toHaveLength(5);
    expect(wrapper.find('[data-testid="stock-chart"]').exists()).toBe(false);
    const firstRow = wrapper.get('[aria-label="Mostrar histórico de NVIDIA"]');
    await firstRow.trigger("click");
    await flushPromises();
    expect(
      apiMock.mock.calls.filter(([path]) =>
        String(path).startsWith("/stock-chart/US67066G1040?"),
      ),
    ).toHaveLength(1);
    expect(wrapper.get('[data-testid="stock-chart"]').text()).toBe("2-1");
    expect(
      wrapper
        .get('[data-testid="stock-chart"]')
        .attributes("data-marker-shape"),
    ).toBe("pin");
    expect(wrapper.get(".asset-return-value").text()).toContain("85");
    await wrapper
      .get('[aria-label="Mostrar pérdidas y ganancias"]')
      .trigger("click");
    expect(wrapper.get(".asset-return-value").text()).toContain("P&L");
    expect(wrapper.get(".asset-return-value").text()).toContain("85,00");
    expect(wrapper.find(".cashback-control").exists()).toBe(false);
    expect(wrapper.findComponent(ImportStatementDialog).exists()).toBe(false);
    expect(
      wrapper.get('button[aria-label="Editar movimiento de NVIDIA"]'),
    ).toBeDefined();
    expect(
      wrapper.get('button[aria-label="Eliminar movimiento de NVIDIA"]'),
    ).toBeDefined();
    expect(wrapper.get(".operation-pill small").text()).toBe("Cashback");

    await wrapper
      .get('select[aria-label="Cuenta de acciones"]')
      .setValue(accountOneId);
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      `/stock-analysis?account_id=${accountOneId}&ignore_savebacks=true`,
    );
    expect(wrapper.get(".cashback-control").text()).toContain(
      "Cashback como beneficio",
    );
    expect(wrapper.findComponent(ImportStatementDialog).exists()).toBe(true);
    expect(apiMock).toHaveBeenCalledWith(
      `/investment-performance/stock?account_id=${accountOneId}&range=1y&ignore_savebacks=true`,
    );
    expect(window.location.search).toBe(`?account=${accountOneId}`);

    const importButton = wrapper
      .findAll(".scope-actions > button")
      .find((button) => button.text() === "Importar extracto");
    expect(importButton).toBeDefined();
    await importButton!.trigger("click");
    expect(
      document.body
        .querySelector(".import-statement-dialog")
        ?.hasAttribute("open"),
    ).toBe(true);
    expect(wrapper.find(".movement-pagination").exists()).toBe(true);
  });

  it("keeps a closed position expanded after editing its asset metadata", async () => {
    positionsOverride = [...stockPositions, closedPosition];
    const wrapper = mount(StocksView);
    await flushPromises();

    const closedRow = wrapper
      .findAll(".fund-position-row")
      .find((row) => row.text().includes("Closed stock"));
    expect(closedRow).toBeDefined();
    await closedRow!.get('button[aria-label="Editar activo"]').trigger("click");
    const editor = wrapper.get(".asset-editor-dialog");
    await editor.get("form").trigger("submit");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/stocks/CLOSED",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(apiMock).toHaveBeenCalledWith(
      "/stock-chart/CLOSED?range=1y&interval=1d",
    );
    expect(wrapper.get('[data-testid="stock-chart"]').text()).toBe("1-0");
    expect(wrapper.get(".fund-position-row.active").text()).toContain(
      "Closed stock",
    );
    expect(
      apiMock.mock.calls.filter(([path]) =>
        String(path).startsWith("/stock-chart/CLOSED?"),
      ),
    ).toHaveLength(1);
  });

  it("matches the fund expand and collapse indicators", async () => {
    const wrapper = mount(StocksView);
    await flushPromises();

    const positionsButton = wrapper.get(
      '[aria-controls="stock-positions-content"]',
    );
    const movementsButton = wrapper.get(
      '[aria-controls="stock-movements-content"]',
    );

    expect(positionsButton.get("svg").attributes("data-direction")).toBe("up");
    expect(movementsButton.get("svg").attributes("data-direction")).toBe("up");

    await positionsButton.trigger("click");
    await movementsButton.trigger("click");

    expect(positionsButton.classes()).toContain("collapsed");
    expect(positionsButton.attributes("aria-expanded")).toBe("false");
    expect(positionsButton.get("svg").attributes("data-direction")).toBe(
      "down",
    );
    expect(movementsButton.classes()).toContain("collapsed");
    expect(movementsButton.attributes("aria-expanded")).toBe("false");
    expect(movementsButton.get("svg").attributes("data-direction")).toBe(
      "down",
    );
  });

  it("loads one chart when editing an open position", async () => {
    const wrapper = mount(StocksView);
    await flushPromises();

    const nvidiaRow = wrapper
      .findAll(".fund-position-row")
      .find((row) => row.text().includes("NVIDIA"));
    expect(nvidiaRow).toBeDefined();
    await nvidiaRow!.get('button[aria-label="Editar activo"]').trigger("click");
    await wrapper.get(".asset-editor-dialog form").trigger("submit");
    await flushPromises();

    expect(
      apiMock.mock.calls.filter(([path]) =>
        String(path).startsWith("/stock-chart/US67066G1040?"),
      ),
    ).toHaveLength(1);
    expect(wrapper.get('[data-testid="stock-chart"]').text()).toBe("2-1");
  });

  it("requests canonical ranges, keeps the candle range when switching rows, and commits custom dates", async () => {
    const wrapper = mount(StocksView);
    await flushPromises();

    const performanceRanges = wrapper.get(
      ".stock-performance-panel .fund-range-control",
    );
    await performanceRanges
      .findAll("button")
      .find((button) => button.text() === "6M")!
      .trigger("click");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/investment-performance/stock?account_id=all&range=6m&ignore_savebacks=true",
    );

    await wrapper
      .get('[aria-label="Mostrar histórico de NVIDIA"]')
      .trigger("click");
    await flushPromises();
    const detail = wrapper.get(".fund-inline-price-panel");
    await detail
      .findAll(".fund-range-control button")
      .find((button) => button.text() === "2A")!
      .trigger("click");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/stock-chart/US67066G1040?range=2y&interval=1wk",
    );

    await wrapper
      .get('[aria-label="Mostrar histórico de Test stock 0"]')
      .trigger("click");
    await flushPromises();
    expect(wrapper.findAll(".fund-inline-price-panel")).toHaveLength(1);
    expect(
      wrapper
        .get(".fund-inline-price-panel .fund-range-control button.active")
        .text(),
    ).toBe("2A");

    const customPerformance = performanceRanges
      .findAll("button")
      .find((button) => button.text() === "Calendario")!;
    await customPerformance.trigger("click");
    const performanceDialog = wrapper.findAll("dialog.stock-dialog")[0];
    await performanceDialog
      .findAll('input[type="date"]')[0]
      .setValue("2026-01-01");
    await performanceDialog
      .findAll('input[type="date"]')[1]
      .setValue("2026-06-30");
    await performanceDialog.find("form").trigger("submit");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/investment-performance/stock?account_id=all&start=2026-01-01&end=2026-06-30&ignore_savebacks=true",
    );
  });

  it("updates translated labels, formats, and accessible names in English", async () => {
    const wrapper = mount(StocksView);
    await flushPromises();

    applyLocale("en");
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain("Top assets");
    expect(wrapper.text()).toContain("Portfolio KPIs");
    expect(wrapper.text()).toContain("Investment journey");
    expect(wrapper.text()).toContain("Transactions");
    expect(wrapper.text()).toContain("Buy");
    expect(wrapper.text()).toContain("€185.00");
    expect(
      wrapper
        .get('select[aria-label="Stock account"]')
        .attributes("aria-label"),
    ).toBe("Stock account");
    expect(wrapper.get(".fund-range-control").attributes("aria-label")).toBe(
      "Time range",
    );
    expect(
      wrapper.get('button[aria-label="Edit NVIDIA transaction"]'),
    ).toBeDefined();
    expect(
      wrapper.get('button[aria-label="Delete NVIDIA transaction"]'),
    ).toBeDefined();
  });

  it("uses the reporting currency and preserves original non-base amounts", async () => {
    applyLocale("en");
    applyReportingCurrency("USD");
    ordersOverride = [
      {
        ...order,
        moneda: "GBP",
        importe_base: 80,
        precio_base: 80,
        comision_base: 0.8,
      },
      ...stockOrders.slice(1),
    ];
    const wrapper = mount(StocksView);
    await flushPromises();

    expect(wrapper.text()).toContain("Prices in USD");
    const movementTable = wrapper.get(".movement-table");
    expect(movementTable.text()).toContain("Original: £100.00");
    expect(movementTable.text()).toContain("Original fee: £1.00");
    expect(movementTable.text()).toContain("$80.00");
  });

  it("names local dialogs and exposes account failures as alerts", async () => {
    const wrapper = mount(StocksView);
    await flushPromises();

    for (const id of [
      "stocks-performance-calendar-title",
      "stocks-candle-calendar-title",
      "stocks-movement-calendar-title",
      "stocks-account-dialog-title",
    ]) {
      const dialog = wrapper.get(`dialog[aria-labelledby="${id}"]`);
      expect(dialog.get(`#${id}`).element.tagName).toBe("H2");
    }

    (wrapper.vm as unknown as { accountError: string }).accountError =
      "Account service unavailable";
    await wrapper.vm.$nextTick();
    expect(wrapper.get(".dialog-error").attributes("role")).toBe("alert");
  });

  it("keeps the newest candle range when an older chart response resolves", async () => {
    const wrapper = mount(StocksView);
    await flushPromises();

    let resolveOldChart: (value: unknown) => void = () => undefined;
    const oldChart = new Promise((resolve) => {
      resolveOldChart = resolve;
    });
    const latestChart = {
      isin: position.isin,
      ticker: "NVDA",
      moneda: "EUR",
      range: "2y",
      data: [
        {
          fecha: "2026-07-01",
          precio: 185,
          open: 180,
          high: 188,
          low: 179,
          close: 185,
        },
      ],
    };
    apiMock.mockImplementation(async (path) => {
      if (
        path.startsWith(`/stock-chart/${position.isin}?`) &&
        path.includes("range=6m")
      )
        return oldChart;
      if (
        path.startsWith(`/stock-chart/${position.isin}?`) &&
        path.includes("range=2y")
      )
        return latestChart;
      if (path.startsWith(`/stock-chart/${position.isin}?`)) return latestChart;
      throw new Error(`Unexpected path: ${path}`);
    });

    await wrapper
      .get('[aria-label="Mostrar histórico de NVIDIA"]')
      .trigger("click");
    await flushPromises();
    const chartRanges = wrapper.get(
      ".fund-inline-price-panel .fund-range-control",
    );
    await chartRanges
      .findAll("button")
      .find((button) => button.text() === "6M")!
      .trigger("click");
    await chartRanges
      .findAll("button")
      .find((button) => button.text() === "2A")!
      .trigger("click");
    await flushPromises();

    expect(wrapper.get('[data-testid="stock-chart"]').text()).toBe("1-1");
    resolveOldChart({
      ...latestChart,
      range: "6m",
      data: [...latestChart.data, latestChart.data[0]],
    });
    await flushPromises();
    expect(wrapper.get('[data-testid="stock-chart"]').text()).toBe("1-1");
  });

  it("keeps the newest account dashboard when an older account resolves", async () => {
    const wrapper = mount(StocksView);
    await flushPromises();

    let resolveOldPositions: (value: unknown) => void = () => undefined;
    const oldPositions = new Promise((resolve) => {
      resolveOldPositions = resolve;
    });
    const latestPosition = {
      ...secondAccountPosition,
      nombre: "Second account current",
    };
    apiMock.mockImplementation(async (path) => {
      if (path === "/stock-accounts") return [account, secondAccount];
      if (path === "/importers") return [stockImporter];
      if (
        path ===
        `/stock-analysis?account_id=${accountOneId}&ignore_savebacks=true`
      )
        return oldPositions;
      if (
        path ===
        `/stock-analysis?account_id=${accountTwoId}&ignore_savebacks=true`
      )
        return [latestPosition];
      if (path === `/stock-orders?account_id=${accountOneId}`)
        return stockOrders;
      if (path === `/stock-orders?account_id=${accountTwoId}`) return [];
      if (path === "/stocks")
        return [
          {
            isin: position.isin,
            ticker: "NVDA",
            nombre: position.nombre,
          },
          secondAccountInstrument,
        ];
      if (path === "/stock-prices") return [];
      if (path.startsWith("/investment-performance/stock?")) {
        return {
          ...performance,
          account_id: new URLSearchParams(path.split("?")[1]).get("account_id"),
        };
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    const accountSelect = wrapper.get(
      'select[aria-label="Cuenta de acciones"]',
    );
    const selectElement = accountSelect.element as HTMLSelectElement;
    selectElement.value = accountOneId;
    selectElement.dispatchEvent(new Event("change", { bubbles: true }));
    await Promise.resolve();
    selectElement.value = accountTwoId;
    selectElement.dispatchEvent(new Event("change", { bubbles: true }));
    await flushPromises();

    expect(window.location.search).toBe(`?account=${accountTwoId}`);
    expect(wrapper.text()).toContain("Second account current");
    expect(wrapper.text()).not.toContain("Stale account one");

    resolveOldPositions([{ ...position, nombre: "Stale account one" }]);
    await flushPromises();
    expect(wrapper.text()).toContain("Second account current");
    expect(wrapper.text()).not.toContain("Stale account one");
  });

  it("keeps the latest performance response when an older range fails", async () => {
    const wrapper = mount(StocksView);
    await flushPromises();

    let rejectOldPerformance: (reason?: unknown) => void = () => undefined;
    const oldPerformance = new Promise<typeof performance>(
      (_resolve, reject) => {
        rejectOldPerformance = reject;
      },
    );
    const latestPerformance = { ...performance, range: "2y", data: [] };
    apiMock.mockImplementation(async (path) => {
      if (
        path.startsWith("/investment-performance/stock?") &&
        path.includes("range=6m")
      )
        return oldPerformance;
      if (
        path.startsWith("/investment-performance/stock?") &&
        path.includes("range=2y")
      )
        return latestPerformance;
      if (path.startsWith("/investment-performance/stock?")) return performance;
      throw new Error(`Unexpected path: ${path}`);
    });

    const performanceRanges = wrapper.get(
      ".stock-performance-panel .fund-range-control",
    );
    await performanceRanges
      .findAll("button")
      .find((button) => button.text() === "6M")!
      .trigger("click");
    await performanceRanges
      .findAll("button")
      .find((button) => button.text() === "2A")!
      .trigger("click");
    await flushPromises();

    expect(wrapper.get(".fund-chart-state").text()).toContain(
      "Histórico insuficiente",
    );
    rejectOldPerformance(new Error("Old performance failed"));
    await flushPromises();
    expect(wrapper.get(".fund-chart-state").text()).toContain(
      "Histórico insuficiente",
    );
    expect(wrapper.text()).not.toContain("Rendimiento no disponible");
  });
});
