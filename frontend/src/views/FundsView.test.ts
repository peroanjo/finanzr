import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import ImportStatementDialog from "../components/ImportStatementDialog.vue";
import { fundsMessages } from "../i18n/fundsMessages";
import { applyLocale, applyReportingCurrency, registerMessages } from "../i18n";
import type { FundPosition } from "../types/api";
import FundsView from "./FundsView.vue";

registerMessages(fundsMessages);

const storage = new Map<string, string>();
vi.stubGlobal("localStorage", {
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
});

vi.mock("../api/client", () => ({
  api: vi.fn(),
  json: (method: string, body: unknown) => ({
    method,
    body: JSON.stringify(body),
  }),
}));
vi.mock("../components/FundPerformanceChart.vue", () => ({
  default: {
    name: "FundPerformanceChart",
    props: ["points", "mode"],
    template:
      '<div data-testid="fund-performance-chart">{{ points.length }}-{{ mode }}</div>',
  },
}));
vi.mock("../components/FundPriceChart.vue", () => ({
  default: {
    name: "FundPriceChart",
    props: ["points", "orders", "averagePrice"],
    template:
      '<div data-testid="fund-price-chart">{{ points.length }}-{{ orders.length }}</div>',
  },
}));
vi.mock("../components/ImportPanel.vue", () => ({
  default: {
    name: "ImportPanel",
    template: '<div data-testid="fund-import" />',
  },
}));

const apiMock = vi.mocked(api);
const fundImporter = {
  slug: "fund_broker",
  display_name: "Fondos MyInvestor/Inversis",
  target: "fund_orders",
  target_label: "Fondos",
  description: "Importa movimientos de fondos.",
  source_instructions: "",
  input_kind: "text",
  accepted_extensions: [".csv", ".html", ".xls"],
  required_fields: [],
  formats: [{ extension: ".csv", label: "CSV", description: "" }],
  fields: [],
  rules: [],
};
const accountOneId = "00000000-0000-0000-0000-000000000001";
const accountTwoId = "00000000-0000-0000-0000-000000000002";
const accountThreeId = "00000000-0000-0000-0000-000000000003";
let accountRows = [
  {
    id: accountOneId,
    name: "Renta Fija",
    platform: "MyInvestor",
    type: "renta_fija",
    currency: "EUR",
    importer_slug: "fund_broker",
    importer_name: "Fondos MyInvestor/Inversis",
  },
  {
    id: accountTwoId,
    name: "Cartera Indexada",
    platform: "MyInvestor",
    type: "renta_variable",
    currency: "EUR",
    importer_slug: "fund_broker",
    importer_name: "Fondos MyInvestor/Inversis",
  },
];
const positions: FundPosition[] = [
  {
    isin: "TEST",
    nombre: "Fondo global",
    tipo: "Renta Variable",
    subtipo: "Global",
    total_invertido: 1000,
    participaciones: 10,
    precio_medio: 100,
    precio_actual: 120,
    valor_actual: 1200,
    pnl: 200,
    pnl_pct: 0.2,
  },
  ...[1100, 1000, 900, 800, 700].map((value, index) => ({
    isin: `TEST-${index}`,
    nombre: `Test fund ${index}`,
    tipo: "Renta Variable",
    subtipo: "Global",
    total_invertido: value - 100,
    participaciones: 10,
    precio_medio: value - 100,
    precio_actual: value,
    valor_actual: value,
    pnl: 100,
    pnl_pct: 0.1,
  })),
];
const accountTwoPositions: FundPosition[] = [
  {
    ...positions[0],
    nombre: "Fondo cuenta dos",
    valor_actual: 300,
    total_invertido: 250,
    precio_actual: 30,
    precio_medio: 25,
    pnl: 50,
    pnl_pct: 0.2,
  },
  {
    ...positions[1],
    isin: "SECOND",
    nombre: "Fondo solo cuenta dos",
    valor_actual: 100,
    total_invertido: 90,
    precio_actual: 10,
    precio_medio: 9,
    pnl: 10,
    pnl_pct: 0.1111,
  },
  {
    ...positions[2],
    isin: "CLOSED",
    nombre: "Fondo cerrado",
    participaciones: 0,
    valor_actual: 900,
  },
  {
    ...positions[3],
    isin: "NO-PRICE",
    nombre: "Fondo sin valoración",
    valor_actual: null,
  },
];
const orders = [
  {
    id: "buy-1",
    trade_date: "2026-01-01",
    settlement_date: "2026-01-02",
    operation_type: "buy",
    cash_flow_type: "contribution",
    isin: "TEST",
    asset_name: "Fondo global",
    quantity: 10,
    unit_price: 100,
    net_amount: 1000,
    fee: 0,
    account_id: accountOneId,
    account_name: "Renta Fija",
    platform: "MyInvestor",
    currency: "EUR",
    base_currency: "EUR",
    base_unit_price: 100,
    base_net_amount: 1000,
    base_fee: 0,
    fx_rate_to_base: 1,
    fx_rate_date: "2026-01-01",
    fx_source: "identity",
    market: "",
    provider_operation_type: "SUSCRIPCION",
  },
  {
    id: "sell-1",
    trade_date: "2026-02-01",
    settlement_date: "2026-02-02",
    operation_type: "sell",
    cash_flow_type: "withdrawal",
    isin: "TEST",
    asset_name: "Fondo global",
    quantity: 2,
    unit_price: 120,
    net_amount: 240,
    fee: 0,
    account_id: accountOneId,
    account_name: "Renta Fija",
    platform: "MyInvestor",
    currency: "EUR",
    base_currency: "EUR",
    base_unit_price: 120,
    base_net_amount: 240,
    base_fee: 0,
    fx_rate_to_base: 1,
    fx_rate_date: "2026-02-01",
    fx_source: "identity",
    market: "",
    provider_operation_type: "REEMBOLSO",
  },
];
const performance = {
  range: "1y",
  account_id: "all",
  moneda_base: "EUR",
  data: [
    { fecha: "2026-01-01", valor: 1000, invertido: 1000, pnl: 0, pnl_pct: 0 },
    {
      fecha: "2026-07-01",
      valor: 1200,
      invertido: 1000,
      pnl: 200,
      pnl_pct: 20,
    },
  ],
};
const instruments = [
  {
    id: "00000000-0000-0000-0000-000000000020",
    kind: "fund" as const,
    name: "Fondo global",
    quote_currency: "USD",
    identifiers: [
      { scheme: "isin" as const, value: "TEST", venue: "", is_primary: true },
      {
        scheme: "yahoo" as const,
        value: "TEST.DE",
        venue: "XETRA",
        is_primary: false,
      },
      {
        scheme: "yahoo" as const,
        value: "TEST.MC",
        venue: "BME",
        is_primary: true,
      },
    ],
    asset_class: "Renta Variable",
    subtype: "Global",
    is_active: true,
  },
];
const prices = [
  {
    id: "00000000-0000-0000-0000-000000000021",
    instrument_id: instruments[0].id,
    quoted_at: "2026-07-01T23:30:00-05:00",
    close: 100,
    currency: "GBP",
    base_close: 120,
    base_currency: "EUR",
    fx_rate_to_base: 1.2,
    fx_rate_date: "2026-07-01",
    fx_source: "test",
    source: "test",
  },
];
const chart = {
  isin: "TEST",
  ticker: "TEST.MC",
  moneda: "EUR",
  range: "1y",
  data: [
    { fecha: "2026-01-01", precio: 100 },
    { fecha: "2026-07-01", precio: 120 },
  ],
};
let positionsOverride: FundPosition[] | null = null;

describe("FundsView", () => {
  beforeEach(() => {
    applyReportingCurrency("EUR");
    accountRows = [
      {
        id: accountOneId,
        name: "Renta Fija",
        platform: "MyInvestor",
        type: "renta_fija",
        currency: "EUR",
        importer_slug: "fund_broker",
        importer_name: "Fondos MyInvestor/Inversis",
      },
      {
        id: accountTwoId,
        name: "Cartera Indexada",
        platform: "MyInvestor",
        type: "renta_variable",
        currency: "EUR",
        importer_slug: "fund_broker",
        importer_name: "Fondos MyInvestor/Inversis",
      },
    ];
    positionsOverride = null;
    localStorage.clear();
    window.history.replaceState({}, "", "/app/fondos");
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
    apiMock.mockImplementation(async (path, init) => {
      if (path === "/fund-accounts" && init?.method === "POST") {
        const created = {
          id: accountThreeId,
          name: "Nueva cartera",
          platform: "MyInvestor",
          type: "renta_variable",
          currency: "EUR",
          importer_slug: "fund_broker",
          importer_name: "Fondos MyInvestor/Inversis",
        };
        accountRows.push(created);
        return created;
      }
      if (path === `/fund-accounts/${accountOneId}` && init?.method === "PUT") {
        accountRows[0] = { ...accountRows[0], name: "Cuenta editada" };
        return accountRows[0];
      }
      if (
        path === `/fund-accounts/${accountOneId}` &&
        init?.method === "DELETE"
      ) {
        accountRows = accountRows.filter((item) => item.id !== accountOneId);
        return { ok: true };
      }
      if (path === "/fund-accounts") return accountRows;
      if (path === "/importers") return [fundImporter];
      if (path === "/fund-analysis") return positionsOverride ?? positions;
      if (path === `/fund-analysis?account_id=${accountOneId}`)
        return positions;
      if (path === `/fund-analysis?account_id=${accountTwoId}`)
        return accountTwoPositions;
      if (path === "/orders" || path === `/orders?account_id=${accountOneId}`)
        return orders;
      if (path === `/orders?account_id=${accountTwoId}`) return [];
      if (
        path === `/fund-analysis?account_id=${accountThreeId}` ||
        path === `/orders?account_id=${accountThreeId}`
      )
        return [];
      if (path === "/funds") return instruments;
      if (path === "/fund-prices") return prices;
      if (path.startsWith("/fund-chart/")) return chart;
      if (path === "/fund-prices/fetch" && init?.method === "POST") {
        return {
          results: [
            {
              instrument_id: instruments[0].id,
              base_close: 121,
              close: 100.833333,
              currency: "USD",
              ticker: "TEST.MC",
              error: null,
            },
          ],
        };
      }
      if (path === `/funds/${instruments[0].id}` && init?.method === "PUT")
        return { ...instruments[0] };
      if (
        path === `/fund-prices/${instruments[0].id}` &&
        init?.method === "PUT"
      )
        return { ok: true };
      if (path === "/orders" && init?.method === "POST") {
        return { ...orders[0], id: "manual:fund" };
      }
      if (path === "/orders/buy-1" && init?.method === "PUT")
        return { ...orders[0] };
      if (path === "/orders/sell-1" && init?.method === "PUT")
        return { ...orders[1] };
      if (path === "/orders/sell-1" && init?.method === "DELETE")
        return { ok: true };
      if (path.startsWith("/investment-performance/fund?")) {
        return {
          ...performance,
          account_id:
            new URLSearchParams(path.split("?")[1]).get("account_id") ?? "all",
        };
      }
      throw new Error(`Unexpected path: ${path}`);
    });
  });

  it("renders account KPIs and changes performance mode and range", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    expect(wrapper.text()).toContain("Todas las cuentas");
    expect(wrapper.text()).toContain("Principales activos");
    expect(wrapper.findAll(".fund-asset-row")).toHaveLength(5);
    expect(wrapper.get(".fund-assets-panel").text()).not.toContain(
      "Test fund 4",
    );
    expect(wrapper.text()).toContain("1200,00");
    expect(wrapper.text()).toContain("1000,00");
    expect(wrapper.text()).toContain("20 %");
    expect(wrapper.text()).toContain("01/01/2026 → 01/07/2026");
    expect(wrapper.get(".fund-utility").text()).toContain("01 jul 2026");
    expect(wrapper.get('[data-testid="fund-performance-chart"]').text()).toBe(
      "2-value",
    );
    expect(wrapper.text()).not.toContain("Ganancia / pérdida por fondo");
    expect(wrapper.text()).not.toContain("Distribución de la cartera");
    expect(wrapper.find('[data-testid="fund-price-chart"]').exists()).toBe(
      false,
    );
    expect(
      apiMock.mock.calls.filter(([path]) =>
        String(path).startsWith("/fund-chart/"),
      ),
    ).toHaveLength(0);
    expect(wrapper.find('[data-testid="fund-import"]').exists()).toBe(false);

    const returnMode = wrapper
      .findAll(".fund-mode-control button")
      .find((button) => button.text() === "Rendimiento %");
    await returnMode!.trigger("click");
    expect(wrapper.get('[data-testid="fund-performance-chart"]').text()).toBe(
      "2-return",
    );

    const sixMonths = wrapper
      .findAll(".fund-range-control button")
      .find((button) => button.text() === "6M");
    await sixMonths!.trigger("click");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/investment-performance/fund?account_id=all&range=6m",
    );

    await wrapper.get(".fund-account-actions select").setValue(accountOneId);
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      `/fund-analysis?account_id=${accountOneId}`,
    );
    expect(apiMock).toHaveBeenCalledWith(`/orders?account_id=${accountOneId}`);
    expect(window.location.search).toBe(`?account=${accountOneId}`);
    expect(wrapper.findComponent(ImportStatementDialog).exists()).toBe(true);
  });

  it("uses the reactive workspace reporting currency for normalized dashboard labels", async () => {
    applyReportingCurrency("USD");
    const wrapper = mount(FundsView);
    await flushPromises();

    expect(wrapper.get(".fund-live").text()).toContain("USD");

    applyReportingCurrency("EUR");
    wrapper.unmount();
  });

  it("characterizes the dashboard hierarchy from account scope through movements", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    const page = wrapper.get(".funds-page");
    const directChildren = Array.from(page.element.children)
      .map((element) => element.className)
      .filter(
        (className): className is string => typeof className === "string",
      );
    expect(
      directChildren.slice(0, 5).map((className) => className.split(" ")[0]),
    ).toEqual([
      "fund-account-bar",
      "fund-top-grid",
      "fund-performance-panel",
      "fund-performance-panel",
      "fund-performance-panel",
    ]);

    expect(
      wrapper.get(".fund-top-grid").find(".fund-assets-panel").exists(),
    ).toBe(true);
    expect(wrapper.get(".fund-top-grid").find(".fund-kpi-panel").exists()).toBe(
      true,
    );
    expect(
      wrapper
        .get(
          ".fund-performance-panel:not(.positions-panel):not(.movements-panel) h2",
        )
        .text(),
    ).toBe("Evolución de la cartera");
    expect(wrapper.get(".positions-panel h2").text()).toBe("Fondos en cartera");
    expect(wrapper.get(".movements-panel h2").text()).toBe("Movimientos");
    expect(
      wrapper
        .get(".positions-panel")
        .element.compareDocumentPosition(
          wrapper.get(".movements-panel").element,
        ) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).not.toBe(0);
  });

  it("characterizes keyboard and ARIA contracts for account, charts, allocation, and tables", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    const accountSelect = wrapper.get(".fund-account-actions select");
    expect(accountSelect.attributes("aria-label")).toBe("Cuenta de fondos");
    expect(accountSelect.element.tagName).toBe("SELECT");

    const modeButtons = wrapper.findAll(".fund-mode-control button");
    expect(modeButtons).toHaveLength(2);
    expect(
      modeButtons.every((button) => button.attributes("aria-pressed")),
    ).toBe(true);
    expect(
      modeButtons
        .find((button) => button.attributes("aria-pressed") === "true")
        ?.text(),
    ).toBe("Valor cartera");

    const positionsToggle = wrapper.get(
      'button[aria-controls="fund-positions-content"]',
    );
    const movementsToggle = wrapper.get(
      'button[aria-controls="fund-movements-content"]',
    );
    expect(positionsToggle.attributes("aria-expanded")).toBe("true");
    expect(movementsToggle.attributes("aria-expanded")).toBe("true");

    const allocation = wrapper.get('[data-testid="fund-position-allocation"]');
    expect(allocation.attributes("role")).toBe("group");
    expect(allocation.findAll('[role="img"][tabindex="0"]')).toHaveLength(6);
    expect(allocation.find('[role="img"]').attributes("aria-label")).toContain(
      "Fondo global",
    );

    const firstDisclosure = wrapper.get(".fund-position-disclosure");
    expect(firstDisclosure.attributes("type")).toBe("button");
    expect(firstDisclosure.attributes("aria-expanded")).toBe("false");
    expect(firstDisclosure.attributes("aria-controls")).toBe(
      "fund-price-detail-test",
    );
    expect(wrapper.findAll(".fund-sort-button")).toHaveLength(9);
    expect(
      wrapper.findAll('select[aria-label="Filtrar por tipo"]'),
    ).toHaveLength(1);
  });

  it("characterizes loading and dashboard error states before the main hierarchy mounts", async () => {
    apiMock.mockImplementation(() => new Promise(() => undefined));
    const loadingWrapper = mount(FundsView);
    expect(loadingWrapper.get(".funds-loading").attributes("aria-label")).toBe(
      "Cargando fondos",
    );
    expect(loadingWrapper.find(".fund-account-bar").exists()).toBe(false);
    loadingWrapper.unmount();

    apiMock.mockImplementation(async (path) => {
      if (path === "/fund-accounts")
        throw new Error("Account service unavailable");
      throw new Error(`Unexpected path: ${path}`);
    });
    const errorWrapper = mount(FundsView);
    await flushPromises();
    expect(errorWrapper.get(".overview-error").attributes("role")).toBe(
      "alert",
    );
    expect(errorWrapper.get(".overview-error").text()).toContain(
      "Account service unavailable",
    );
    expect(errorWrapper.get(".overview-error button").text()).toBe(
      "Reintentar",
    );
  });

  it("characterizes empty positions and movements without relying on computed CSS", async () => {
    apiMock.mockImplementation(async (path) => {
      if (path === "/fund-accounts") return accountRows;
      if (path === "/importers") return [fundImporter];
      if (path === "/fund-analysis" || path === "/orders") return [];
      if (path === "/funds" || path === "/fund-prices") return [];
      if (path.startsWith("/investment-performance/fund?"))
        return { ...performance, data: [] };
      throw new Error(`Unexpected path: ${path}`);
    });
    const wrapper = mount(FundsView);
    await flushPromises();

    expect(
      wrapper.get(".fund-assets-panel .fund-empty-compact").text(),
    ).toContain("No hay posiciones abiertas");
    expect(wrapper.get(".fund-position-allocation").text()).toContain(
      "Aún no hay posiciones abiertas",
    );
    expect(
      wrapper.get(".movements-panel .fund-empty-compact").text(),
    ).toContain("No hay movimientos con estos filtros");
    expect(wrapper.findAll(".fund-position-allocation-segment")).toHaveLength(
      0,
    );
    expect(wrapper.findAll(".movement-table tbody tr")).toHaveLength(0);
  });

  it("characterizes responsive hooks as stable classes and data attributes", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    expect(wrapper.get(".funds-page").classes()).toContain("funds-page");
    expect(wrapper.get(".fund-top-grid").classes()).toContain("fund-top-grid");
    expect(wrapper.get(".fund-asset-table").classes()).toContain(
      "fund-asset-table",
    );
    expect(wrapper.get(".position-table-scroll").classes()).toContain(
      "position-table-scroll",
    );
    expect(wrapper.get(".fund-table").classes()).toContain("fund-table");
    expect(
      wrapper.findAll('.fund-position-row td[data-label="Tipo"]'),
    ).toHaveLength(6);
    expect(
      wrapper.findAll('.fund-position-row td[data-label="Valor"]'),
    ).toHaveLength(6);
    expect(wrapper.find(".fund-inline-detail-row").exists()).toBe(false);
    expect(
      wrapper.get(".fund-position-disclosure").attributes("aria-controls"),
    ).toBe("fund-price-detail-test");
  });

  it("opens one inline price detail from the full table and keeps the top list informational", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    const chartCalls = () =>
      apiMock.mock.calls.filter(([path]) =>
        String(path).startsWith("/fund-chart/"),
      );
    expect(chartCalls()).toHaveLength(0);
    expect(wrapper.find(".fund-price-panel").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("Evolución histórica del precio");
    expect(wrapper.findAll(".fund-asset-row")).toHaveLength(5);
    await wrapper.get(".fund-asset-row").trigger("click");
    expect(chartCalls()).toHaveLength(0);
    expect(wrapper.find(".fund-inline-price-panel").exists()).toBe(false);

    const firstRow = wrapper
      .findAll(".fund-position-row")
      .find((row) => row.text().includes("Fondo global"))!;
    const disclosure = firstRow.get(".fund-position-disclosure");
    expect(disclosure.attributes("aria-expanded")).toBe("false");
    expect(disclosure.attributes("aria-controls")).toBe(
      "fund-price-detail-test",
    );
    await firstRow.trigger("click");
    await flushPromises();

    expect(chartCalls()).toHaveLength(1);
    expect(chartCalls()[0][0]).toBe("/fund-chart/TEST?range=1y&interval=1d");
    expect(disclosure.attributes("aria-expanded")).toBe("true");
    expect(wrapper.findAll(".fund-inline-detail-row")).toHaveLength(1);
    expect(
      wrapper.get(".fund-inline-detail-row td").attributes("colspan"),
    ).toBe("10");
    expect(wrapper.get('[data-testid="fund-price-chart"]').text()).toBe("2-2");
    expect(wrapper.get(".fund-inline-price-panel").text()).not.toContain(
      "Precio y operaciones",
    );
    expect(wrapper.get(".fund-inline-price-panel").text()).not.toContain(
      "Evolución histórica del precio",
    );
    const toolbar = wrapper.get(".fund-inline-chart-toolbar");
    expect(toolbar.find(":scope > .fund-chart-legend").exists()).toBe(true);
    expect(toolbar.find(":scope > .fund-inline-range").exists()).toBe(true);

    const secondRow = wrapper
      .findAll(".fund-position-row")
      .find((row) => row.text().includes("Test fund 0"))!;
    await secondRow.trigger("click");
    await flushPromises();
    expect(wrapper.findAll(".fund-inline-detail-row")).toHaveLength(1);
    expect(wrapper.findAll(".fund-position-row.active")).toHaveLength(1);
    expect(chartCalls().at(-1)?.[0]).toBe(
      "/fund-chart/TEST-0?range=1y&interval=1d",
    );

    await secondRow.trigger("click");
    expect(wrapper.find(".fund-inline-price-panel").exists()).toBe(false);
    expect(wrapper.findAll(".fund-inline-detail-row")).toHaveLength(0);
  });

  it("supports row keyboard activation, keeps the price range across funds, and isolates Edit", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();
    const firstRow = wrapper
      .findAll(".fund-position-row")
      .find((row) => row.text().includes("Fondo global"))!;

    await firstRow.find('button[aria-label="Editar fondo"]').trigger("click");
    expect(
      wrapper
        .find('dialog[aria-labelledby="fund-editor-title"]')
        .attributes("open"),
    ).toBeDefined();
    expect(wrapper.find(".fund-inline-price-panel").exists()).toBe(false);

    const disclosure = firstRow.get(".fund-position-disclosure");
    await disclosure.trigger("keydown.enter");
    await flushPromises();
    expect(disclosure.attributes("aria-expanded")).toBe("true");
    expect(wrapper.find(".fund-inline-price-panel").exists()).toBe(true);

    await wrapper
      .get(".fund-inline-price-panel .fund-range-control button:first-child")
      .trigger("click");
    await flushPromises();
    expect(
      wrapper
        .find(".fund-inline-price-panel .fund-range-control button.active")
        .text(),
    ).toBe("6M");

    const secondRow = wrapper
      .findAll(".fund-position-row")
      .find((row) => row.text().includes("Test fund 0"))!;
    await secondRow.trigger("click");
    await flushPromises();
    expect(
      wrapper
        .find(".fund-inline-price-panel .fund-range-control button.active")
        .text(),
    ).toBe("6M");
    expect(apiMock.mock.calls.at(-1)?.[0]).toBe(
      "/fund-chart/TEST-0?range=6m&interval=1d",
    );

    await secondRow.get(".fund-position-disclosure").trigger("keydown.space");
    expect(wrapper.find(".fund-inline-price-panel").exists()).toBe(false);
  });

  it("preserves custom price dates while switching the expanded fund", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();
    const firstRow = wrapper
      .findAll(".fund-position-row")
      .find((row) => row.text().includes("Fondo global"))!;
    await firstRow.trigger("click");
    await flushPromises();

    await wrapper
      .get(".fund-inline-price-panel .fund-range-control button:last-child")
      .trigger("click");
    const calendar = wrapper.get(
      'dialog[aria-labelledby="fund-price-calendar-title"]',
    );
    const dates = calendar.findAll("input");
    await dates[0].setValue("2026-02-01");
    await dates[1].setValue("2026-06-30");
    await calendar.get("form").trigger("submit");
    await flushPromises();
    expect(apiMock.mock.calls.at(-1)?.[0]).toBe(
      "/fund-chart/TEST?start=2026-02-01&end=2026-06-30",
    );

    const secondRow = wrapper
      .findAll(".fund-position-row")
      .find((row) => row.text().includes("Test fund 0"))!;
    await secondRow.trigger("click");
    await flushPromises();
    expect(apiMock.mock.calls.at(-1)?.[0]).toBe(
      "/fund-chart/TEST-0?start=2026-02-01&end=2026-06-30",
    );
  });

  it("keeps an expanded closed position when dashboard data still contains it", async () => {
    positionsOverride = [
      ...positions,
      {
        ...positions[0],
        isin: "CLOSED",
        nombre: "Fondo cerrado",
        participaciones: 0,
        valor_actual: 0,
        precio_actual: 120,
        pnl: 0,
        pnl_pct: 0,
      },
    ];
    const wrapper = mount(FundsView);
    await flushPromises();

    const closedRow = wrapper
      .findAll(".fund-position-row")
      .find((row) => row.text().includes("Fondo cerrado"))!;
    await closedRow.trigger("click");
    await flushPromises();
    expect(wrapper.find(".fund-inline-price-panel").exists()).toBe(true);

    await wrapper.get(".fund-action-button").trigger("click");
    await flushPromises();
    expect(wrapper.find(".fund-inline-price-panel").exists()).toBe(true);
    expect(wrapper.find(".fund-position-row.active").text()).toContain(
      "Fondo cerrado",
    );
  });

  it("shows market-value proportions for open positions and follows the selected account", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    const distribution = wrapper.get(
      '[data-testid="fund-position-allocation"]',
    );
    const allSegments = distribution.findAll(
      ".fund-position-allocation-segment",
    );
    expect(allSegments).toHaveLength(6);
    const allWidths = allSegments.map((segment) =>
      Number.parseFloat(
        segment.attributes("style")?.match(/width:\s*([\d.]+)%/)?.[1] ?? "NaN",
      ),
    );
    expect(allWidths[0]).toBeCloseTo((1200 / 5700) * 100);
    expect(allWidths.reduce((sum, width) => sum + width, 0)).toBeCloseTo(100);
    expect(distribution.text()).toContain("Fondo global");
    expect(distribution.text()).toContain("Otros");
    expect(distribution.text()).not.toContain("Test fund 4");
    expect(allWidths.at(-1)).toBeCloseTo((700 / 5700) * 100);
    expect(distribution.find(".fund-position-allocation-legend").exists()).toBe(
      false,
    );
    expect(
      allSegments[0].get(".fund-position-allocation-tooltip").text(),
    ).toContain("Fondo global");
    expect(
      allSegments[0].get(".fund-position-allocation-tooltip").text(),
    ).toContain("1200,00");
    expect(distribution.attributes("aria-label")).toContain(
      "Todas las cuentas",
    );

    await wrapper.get(".fund-account-actions select").setValue(accountTwoId);
    await flushPromises();

    const accountDistribution = wrapper.get(
      '[data-testid="fund-position-allocation"]',
    );
    const accountSegments = accountDistribution.findAll(
      ".fund-position-allocation-segment",
    );
    expect(accountSegments).toHaveLength(2);
    const accountWidths = accountSegments.map((segment) =>
      Number.parseFloat(
        segment.attributes("style")?.match(/width:\s*([\d.]+)%/)?.[1] ?? "NaN",
      ),
    );
    expect(accountWidths[0]).toBeCloseTo(75);
    expect(accountWidths[1]).toBeCloseTo(25);
    expect(accountDistribution.text()).toContain("Cartera Indexada");
    expect(accountDistribution.text()).not.toContain("Fondo cerrado");
    expect(accountDistribution.text()).not.toContain("Fondo sin valoración");
    expect(accountDistribution.attributes("aria-label")).toContain(
      "Cartera Indexada",
    );
  });

  it("shows a quiet state when open positions have no positive market values", async () => {
    positionsOverride = positions.map((position) => ({
      ...position,
      valor_actual: null,
      precio_actual: null,
      pnl: null,
      pnl_pct: null,
    }));
    const wrapper = mount(FundsView);
    await flushPromises();

    expect(
      wrapper
        .get('[data-testid="fund-position-allocation"]')
        .find(".fund-position-allocation-empty")
        .text(),
    ).toContain("Aún no hay posiciones abiertas");
    expect(wrapper.findAll(".fund-position-allocation-segment")).toHaveLength(
      0,
    );
  });

  it("keeps the newest account data when dashboard responses resolve out of order", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();
    const performanceCallsBefore = apiMock.mock.calls.filter(([path]) =>
      String(path).startsWith("/investment-performance/fund?"),
    ).length;
    const fundChartCallsBefore = apiMock.mock.calls.filter(([path]) =>
      String(path).startsWith("/fund-chart/"),
    ).length;

    let resolveStalePositions: (value: FundPosition[]) => void = () =>
      undefined;
    const stalePositions = new Promise<FundPosition[]>((resolve) => {
      resolveStalePositions = resolve;
    });
    const oldPosition = {
      ...positions[0],
      nombre: "Cuenta uno antigua",
      valor_actual: 50,
    };
    const latestPosition = {
      ...positions[0],
      nombre: "Cuenta dos actual",
      valor_actual: 900,
    };
    apiMock.mockImplementation(async (path) => {
      if (path === "/fund-accounts") return accountRows;
      if (path === "/importers") return [fundImporter];
      if (path === `/fund-analysis?account_id=${accountOneId}`)
        return stalePositions;
      if (path === `/orders?account_id=${accountOneId}`) return orders;
      if (path === `/fund-analysis?account_id=${accountTwoId}`)
        return [latestPosition];
      if (path === `/orders?account_id=${accountTwoId}`) return [];
      if (path === "/funds") return instruments;
      if (path === "/fund-prices") return prices;
      if (path.startsWith("/investment-performance/fund?")) {
        return {
          ...performance,
          cuenta_id:
            new URLSearchParams(path.split("?")[1]).get("account_id") ?? "all",
        };
      }
      if (path.startsWith("/fund-chart/")) return chart;
      throw new Error(`Unexpected path: ${path}`);
    });

    const accountSelect = wrapper.get(".fund-account-actions select");
    const accountSelectElement = accountSelect.element as HTMLSelectElement;
    accountSelectElement.value = accountOneId;
    accountSelectElement.dispatchEvent(new Event("change", { bubbles: true }));
    await Promise.resolve();
    accountSelectElement.value = accountTwoId;
    accountSelectElement.dispatchEvent(new Event("change", { bubbles: true }));
    await flushPromises();

    const distribution = wrapper.get(
      '[data-testid="fund-position-allocation"]',
    );
    expect(window.location.search).toBe(`?account=${accountTwoId}`);
    expect(distribution.text()).toContain("Cuenta dos actual");
    expect(distribution.text()).not.toContain("Cuenta uno antigua");

    resolveStalePositions([oldPosition]);
    await flushPromises();

    expect(
      wrapper.get('[data-testid="fund-position-allocation"]').text(),
    ).toContain("Cuenta dos actual");
    expect(
      wrapper.get('[data-testid="fund-position-allocation"]').text(),
    ).not.toContain("Cuenta uno antigua");
    expect(
      apiMock.mock.calls.filter(([path]) =>
        String(path).startsWith("/investment-performance/fund?"),
      ),
    ).toHaveLength(performanceCallsBefore + 1);
    expect(
      apiMock.mock.calls.filter(([path]) =>
        String(path).startsWith("/fund-chart/"),
      ),
    ).toHaveLength(fundChartCallsBefore);
  });

  it("clears an in-flight chart when the newest account has no positions", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    let resolveOldChart: (value: typeof chart) => void = () => undefined;
    const oldChart = new Promise<typeof chart>((resolve) => {
      resolveOldChart = resolve;
    });
    apiMock.mockImplementation(async (path) => {
      if (path === "/fund-accounts") return accountRows;
      if (path === "/importers") return [fundImporter];
      if (path === `/fund-analysis?account_id=${accountTwoId}`) return [];
      if (path === `/orders?account_id=${accountTwoId}`) return [];
      if (path === "/funds") return instruments;
      if (path === "/fund-prices") return prices;
      if (path.startsWith("/investment-performance/fund?")) return performance;
      if (path.startsWith("/fund-chart/TEST?")) return oldChart;
      throw new Error(`Unexpected path: ${path}`);
    });

    const positionRow = wrapper
      .findAll(".fund-position-row")
      .find((row) => row.text().includes("Fondo global"));
    await positionRow!.trigger("click");
    const priceRange = wrapper
      .findAll(".fund-inline-price-panel .fund-range-control button")
      .find((button) => button.text() === "6M");
    await priceRange!.trigger("click");
    expect(
      wrapper.find(".fund-inline-price-panel .fund-chart-state").text(),
    ).toContain("Cargando histórico");

    await wrapper.get(".fund-account-actions select").setValue(accountTwoId);
    await flushPromises();

    expect(wrapper.find(".fund-inline-price-panel").exists()).toBe(false);

    resolveOldChart(chart);
    await flushPromises();
    expect(wrapper.find(".fund-inline-price-panel").exists()).toBe(false);
  });

  it("keeps the latest performance and chart requests after older ones fail", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    let rejectOldPerformance: (reason?: unknown) => void = () => undefined;
    let rejectOldChart: (reason?: unknown) => void = () => undefined;
    const oldPerformance = new Promise<typeof performance>(
      (resolve, reject) => {
        rejectOldPerformance = reject;
      },
    );
    const oldChart = new Promise<typeof chart>((resolve, reject) => {
      rejectOldChart = reject;
    });
    const latestPerformance = {
      ...performance,
      data: [
        { ...performance.data[0], valor: 2000 },
        { ...performance.data[1], valor: 2200 },
      ],
    };
    const latestChart = { ...chart, data: [chart.data[0]] };
    apiMock.mockImplementation(async (path) => {
      if (
        path.startsWith("/investment-performance/fund?") &&
        path.includes("range=6m")
      ) {
        return oldPerformance;
      }
      if (
        path.startsWith("/investment-performance/fund?") &&
        path.includes("range=2y")
      ) {
        return latestPerformance;
      }
      if (path.startsWith("/fund-chart/TEST?") && path.includes("range=6m"))
        return oldChart;
      if (path.startsWith("/fund-chart/TEST?") && path.includes("range=2y"))
        return latestChart;
      if (path.startsWith("/investment-performance/fund?")) return performance;
      if (path.startsWith("/fund-chart/TEST?")) return chart;
      throw new Error(`Unexpected path: ${path}`);
    });

    const performanceRanges = wrapper.findAll(
      ".fund-performance-header .fund-range-control button",
    );
    await performanceRanges
      .find((button) => button.text() === "6M")!
      .trigger("click");
    await performanceRanges
      .find((button) => button.text() === "2A")!
      .trigger("click");
    const positionRow = wrapper
      .findAll(".fund-position-row")
      .find((row) => row.text().includes("Fondo global"));
    await positionRow!.trigger("click");
    const priceRanges = wrapper.findAll(
      ".fund-inline-price-panel .fund-range-control button",
    );
    await priceRanges
      .find((button) => button.text() === "6M")!
      .trigger("click");
    await priceRanges
      .find((button) => button.text() === "2A")!
      .trigger("click");
    await flushPromises();

    expect(wrapper.get('[data-testid="fund-performance-chart"]').text()).toBe(
      "2-value",
    );
    expect(wrapper.get('[data-testid="fund-price-chart"]').text()).toBe("1-2");
    expect(
      wrapper.find(".fund-inline-price-panel .fund-chart-state").exists(),
    ).toBe(false);

    rejectOldPerformance(new Error("Old performance failed"));
    rejectOldChart(new Error("Old chart failed"));
    await flushPromises();

    expect(wrapper.get('[data-testid="fund-performance-chart"]').text()).toBe(
      "2-value",
    );
    expect(wrapper.get('[data-testid="fund-price-chart"]').text()).toBe("1-2");
    expect(
      wrapper.find(".fund-inline-price-panel .fund-chart-state").exists(),
    ).toBe(false);
  });

  it("renders the complete view and locale-aware formats in English", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();
    expect(wrapper.text()).toContain("Todas las cuentas");

    applyLocale("en");
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain("All accounts");
    expect(wrapper.text()).toContain("Portfolio performance");
    expect(wrapper.text()).toContain("Top assets");
    expect(wrapper.text()).toContain("Portfolio KPIs");
    expect(wrapper.text()).toContain("Portfolio value");
    expect(wrapper.text()).toContain("Market value distribution");
    expect(wrapper.text()).toContain("€1,200.00");
    expect(wrapper.text()).toContain("01/01/2026 → 07/01/2026");
    expect(wrapper.text()).toContain("Transactions");
    expect(wrapper.text()).toContain("Redemption");
    expect(
      wrapper
        .get('select[aria-label="Filter by type"]')
        .attributes("aria-label"),
    ).toBe("Filter by type");
    const editButton = wrapper.get('button[aria-label="Edit fund"]');
    expect(editButton.text()).toBe("");
    expect(editButton.get("svg").attributes("aria-hidden")).toBe("true");

    const calendar = wrapper
      .findAll(".fund-range-control button")
      .find((button) => button.text() === "Calendar");
    await calendar!.trigger("click");
    expect(
      wrapper.get('dialog[aria-labelledby="fund-calendar-title"]').text(),
    ).toContain("Select dates");
  });

  it("filters movements and opens the guarded deletion confirmation", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    expect(wrapper.findAll(".movement-table tbody tr")).toHaveLength(2);
    await wrapper.get('select[aria-label="Filtrar por tipo"]').setValue("out");
    expect(wrapper.findAll(".movement-table tbody tr")).toHaveLength(1);
    expect(wrapper.text()).toContain("Reembolso");

    await wrapper.get(".delete-order").trigger("click");
    const dialog = wrapper.get(
      'dialog[aria-labelledby="movement-delete-title"]',
    );
    expect(dialog.attributes("open")).toBeDefined();
    await dialog.get("form").trigger("submit");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith("/orders/sell-1", {
      method: "DELETE",
    });
  });

  it("collapses portfolio funds and movements and remembers both choices", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    const positionsToggle = wrapper.get(
      'button[aria-controls="fund-positions-content"]',
    );
    const movementsToggle = wrapper.get(
      'button[aria-controls="fund-movements-content"]',
    );
    expect(positionsToggle.attributes("aria-expanded")).toBe("true");
    expect(movementsToggle.attributes("aria-expanded")).toBe("true");
    expect(positionsToggle.get("svg").attributes("data-direction")).toBe("up");
    expect(movementsToggle.get("svg").attributes("data-direction")).toBe("up");

    await positionsToggle.trigger("click");
    await movementsToggle.trigger("click");

    expect(positionsToggle.attributes("aria-expanded")).toBe("false");
    expect(movementsToggle.attributes("aria-expanded")).toBe("false");
    expect(positionsToggle.get("svg").attributes("data-direction")).toBe(
      "down",
    );
    expect(movementsToggle.get("svg").attributes("data-direction")).toBe(
      "down",
    );
    expect(wrapper.get("#fund-positions-content").isVisible()).toBe(false);
    expect(wrapper.get("#fund-movements-content").isVisible()).toBe(false);
    expect(localStorage.getItem("finanzr-funds-positions-collapsed")).toBe(
      "true",
    );
    expect(localStorage.getItem("finanzr-funds-movements-collapsed")).toBe(
      "true",
    );

    wrapper.unmount();
    const restored = mount(FundsView);
    await flushPromises();
    expect(
      restored
        .get('button[aria-controls="fund-positions-content"]')
        .attributes("aria-expanded"),
    ).toBe("false");
    expect(
      restored
        .get('button[aria-controls="fund-movements-content"]')
        .attributes("aria-expanded"),
    ).toBe("false");
  });

  it("sorts portfolio funds in both directions and exposes all sortable columns", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    const rows = () => wrapper.findAll(".positions-panel tbody tr");
    const valueSort = wrapper.get('.fund-sort-button[data-sort-key="value"]');
    expect(valueSort.element.closest("th")?.getAttribute("aria-sort")).toBe(
      "descending",
    );
    expect(rows()[0].text()).toContain("Fondo global");

    await valueSort.trigger("click");
    expect(valueSort.element.closest("th")?.getAttribute("aria-sort")).toBe(
      "ascending",
    );
    expect(rows()[0].text()).toContain("Test fund 4");

    const fundSort = wrapper.get('.fund-sort-button[data-sort-key="fund"]');
    await fundSort.trigger("click");
    expect(fundSort.element.closest("th")?.getAttribute("aria-sort")).toBe(
      "ascending",
    );
    expect(rows()[0].text()).toContain("Fondo global");

    await fundSort.trigger("click");
    expect(fundSort.element.closest("th")?.getAttribute("aria-sort")).toBe(
      "descending",
    );
    expect(rows()[0].text()).toContain("Test fund 4");
    const returnSort = wrapper.get('.fund-sort-button[data-sort-key="return"]');
    await returnSort.trigger("click");
    expect(returnSort.element.closest("th")?.getAttribute("aria-sort")).toBe(
      "ascending",
    );
    expect(rows()[0].text()).toContain("Test fund 0");
    await returnSort.trigger("click");
    expect(rows()[0].text()).toContain("Fondo global");
    expect(wrapper.findAll(".fund-sort-button")).toHaveLength(9);
  });

  it("updates prices and edits fund metadata and its manual price", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    await wrapper.get(".fund-action-button").trigger("click");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith("/fund-prices/fetch", {
      method: "POST",
    });

    await wrapper.get('button[aria-label="Editar fondo"]').trigger("click");
    const dialog = wrapper.get('dialog[aria-labelledby="fund-editor-title"]');
    const inputs = dialog.findAll("input");
    expect(inputs[4].element.value).toBe("100");
    expect(dialog.text()).toContain("Precio manual (GBP)");
    await inputs[0].setValue("Fondo global editado");
    await inputs[4].setValue("125");
    await dialog.get("form").trigger("submit");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      `/funds/${instruments[0].id}`,
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          name: "Fondo global editado",
          quote_currency: "USD",
          identifiers: [
            { scheme: "isin", value: "TEST", venue: "", is_primary: true },
            {
              scheme: "yahoo",
              value: "TEST.DE",
              venue: "XETRA",
              is_primary: false,
            },
            {
              scheme: "yahoo",
              value: "TEST.MC",
              venue: "BME",
              is_primary: true,
            },
          ],
          asset_class: "Renta Variable",
          subtype: "Global",
        }),
      }),
    );
    expect(apiMock).toHaveBeenCalledWith(`/fund-prices/${instruments[0].id}`, {
      method: "PUT",
      body: JSON.stringify({ close: 125, currency: "GBP" }),
    });
  });

  it("clears the primary fund Yahoo ticker while preserving other venues", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    await wrapper.get('button[aria-label="Editar fondo"]').trigger("click");
    const dialog = wrapper.get('dialog[aria-labelledby="fund-editor-title"]');
    const inputs = dialog.findAll("input");
    await inputs[1].setValue("");
    await inputs[4].setValue("");
    await dialog.get("form").trigger("submit");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      `/funds/${instruments[0].id}`,
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          name: "Fondo global",
          quote_currency: "USD",
          identifiers: [
            { scheme: "isin", value: "TEST", venue: "", is_primary: true },
            {
              scheme: "yahoo",
              value: "TEST.DE",
              venue: "XETRA",
              is_primary: false,
            },
            { scheme: "yahoo", value: "", venue: "BME", is_primary: true },
          ],
          asset_class: "Renta Variable",
          subtype: "Global",
        }),
      }),
    );
  });

  it("saves an existing zero native price instead of treating it as missing", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    await wrapper.get('button[aria-label="Editar fondo"]').trigger("click");
    const dialog = wrapper.get('dialog[aria-labelledby="fund-editor-title"]');
    const inputs = dialog.findAll("input");
    await inputs[4].setValue("0");
    await dialog.get("form").trigger("submit");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(`/fund-prices/${instruments[0].id}`, {
      method: "PUT",
      body: JSON.stringify({ close: 0, currency: "GBP" }),
    });
  });

  it("keeps a nonprimary selected Yahoo feed and its venue on a name-only edit", async () => {
    const original = instruments[0];
    instruments[0] = {
      ...original,
      identifiers: [
        { scheme: "isin", value: "TEST", venue: "", is_primary: true },
        { scheme: "yahoo", value: "Z.MC", venue: "BME", is_primary: false },
        { scheme: "yahoo", value: "a.MC", venue: "BME", is_primary: false },
      ],
    };
    try {
      const wrapper = mount(FundsView);
      await flushPromises();

      await wrapper.get('button[aria-label="Editar fondo"]').trigger("click");
      const dialog = wrapper.get('dialog[aria-labelledby="fund-editor-title"]');
      const inputs = dialog.findAll("input");
      expect((inputs[1].element as HTMLInputElement).value).toBe("Z.MC");
      await inputs[0].setValue("Fondo ordinal editado");
      await inputs[4].setValue("");
      await dialog.get("form").trigger("submit");
      await flushPromises();

      expect(apiMock).toHaveBeenCalledWith(
        `/funds/${original.id}`,
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({
            name: "Fondo ordinal editado",
            quote_currency: "USD",
            identifiers: instruments[0].identifiers,
            asset_class: "Renta Variable",
            subtype: "Global",
          }),
        }),
      );
    } finally {
      instruments[0] = original;
    }
  });

  it("edits a selected account and protects account deletion with two steps", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();
    await wrapper.get(".fund-account-actions select").setValue(accountOneId);
    await flushPromises();

    const manage = wrapper
      .findAll(".fund-account-actions > button")
      .find((button) => button.text().includes("Gestionar cuenta"));
    await manage!.trigger("click");
    const dialog = wrapper.get(
      'dialog[aria-labelledby="fund-account-dialog-title"]',
    );
    await dialog.findAll("input")[0].setValue("Cuenta editada");
    await dialog.get("form").trigger("submit");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      `/fund-accounts/${accountOneId}`,
      expect.objectContaining({ method: "PUT" }),
    );

    await manage!.trigger("click");
    const deleteButton = wrapper.get(".ghost-danger");
    await deleteButton.trigger("click");
    expect(deleteButton.text()).toContain("Confirmar");
    await deleteButton.trigger("click");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(`/fund-accounts/${accountOneId}`, {
      method: "DELETE",
    });
    expect(window.location.search).toBe("");
  });

  it("creates and edits fund movements with the shared workflow", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    await wrapper.get(".movements-panel .add-movement").trigger("click");
    let editor = wrapper.get(".movement-editor-dialog");
    expect(editor.attributes("open")).toBeDefined();
    const createInputs = editor.findAll("input");
    await createInputs[0].setValue("2026-07-25");
    await createInputs[2].setValue("2");
    await createInputs[3].setValue("50");
    await createInputs[4].setValue("100");
    await editor.get("form").trigger("submit");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/orders",
      expect.objectContaining({ method: "POST" }),
    );

    await wrapper.get(".investment-movement-action--edit").trigger("click");
    editor = wrapper.get(".movement-editor-dialog");
    expect(editor.text()).toContain("Editar movimiento");
    const editInputs = editor.findAll("input");
    await editInputs[4].setValue("110");
    await editor.get("form").trigger("submit");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/orders/sell-1",
      expect.objectContaining({ method: "PUT" }),
    );
  });

  it("applies a custom range and creates a fund account", async () => {
    const wrapper = mount(FundsView);
    await flushPromises();

    const calendar = wrapper
      .findAll(".fund-range-control button")
      .find((button) => button.text() === "Calendario");
    await calendar!.trigger("click");
    expect(
      wrapper
        .get('dialog[aria-labelledby="fund-calendar-title"]')
        .attributes("open"),
    ).toBeDefined();

    const dates = wrapper.findAll(".fund-calendar-fields input");
    await dates[0].setValue("2026-02-01");
    await dates[1].setValue("2026-06-30");
    await wrapper
      .get('dialog[aria-labelledby="fund-calendar-title"] form')
      .trigger("submit");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/investment-performance/fund?account_id=all&start=2026-02-01&end=2026-06-30",
    );

    await wrapper.get(".fund-account-actions > button").trigger("click");
    const accountDialog = wrapper.get(
      'dialog[aria-labelledby="fund-account-dialog-title"]',
    );
    const inputs = accountDialog.findAll("input");
    await inputs[0].setValue("Nueva cartera");
    await inputs[1].setValue("MyInvestor");
    await inputs[2].setValue("renta_variable");
    await accountDialog.get("select").setValue("fund_broker");
    await accountDialog.get("form").trigger("submit");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/fund-accounts",
      expect.objectContaining({ method: "POST" }),
    );
    expect(window.location.search).toBe(`?account=${accountThreeId}`);
    expect(wrapper.get(".fund-account-copy").text()).toContain("Nueva cartera");
  });
});
