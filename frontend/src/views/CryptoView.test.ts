import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { instrumentIdentity } from "../domain/instruments";
import { applyLocale, registerMessages } from "../i18n";
import { cryptoMessages } from "../i18n/cryptoMessages";
import type {
  CryptoAccount,
  CryptoInstrument,
  InstrumentIdentifier,
  CryptoOrder,
  CryptoPrice,
} from "../types/api";
import CryptoView from "./CryptoView.vue";

registerMessages(cryptoMessages);

vi.mock("../api/client", () => ({
  api: vi.fn(),
  json: (method: string, body: unknown) => ({
    method,
    body: JSON.stringify(body),
  }),
}));
vi.mock("../components/CryptoCandlestickChart.vue", () => ({
  default: {
    name: "CryptoCandlestickChart",
    props: ["points", "operations", "averagePrice", "operationMarkerShape"],
    template:
      '<div data-testid="crypto-chart" :data-marker-shape="operationMarkerShape">{{ points.length }}-{{ operations.length }}-{{ averagePrice }}</div>',
  },
}));
vi.mock("../components/FundPerformanceChart.vue", () => ({
  default: {
    name: "FundPerformanceChart",
    props: ["points", "mode"],
    template:
      '<div data-testid="performance-chart">{{ points.length }}-{{ mode }}</div>',
  },
}));

const apiMock = vi.mocked(api);
const testStorage = new Map<string, string>();
const localStorageStub = {
  getItem: (key: string) => testStorage.get(key) ?? null,
  setItem: (key: string, value: string) => {
    testStorage.set(key, value);
  },
  removeItem: (key: string) => {
    testStorage.delete(key);
  },
  clear: () => {
    testStorage.clear();
  },
};
const importer = {
  slug: "kraken_spot",
  display_name: "KrakenPro Spot Trades",
  target: "crypto_orders",
  target_label: "Crypto",
  description: "Imports KrakenPro spot transactions.",
  source_instructions: "",
  input_kind: "records",
  accepted_extensions: [".csv"],
  required_fields: [],
  formats: [{ extension: ".csv", label: "CSV Spot Trades", description: "" }],
  fields: [],
  rules: [],
};
const accountOneId = "00000000-0000-0000-0000-000000000001";
const accountTwoId = "00000000-0000-0000-0000-000000000002";
const accounts = [
  {
    id: accountOneId,
    name: "KrakenPro",
    platform: "KrakenPro",
    type: "",
    currency: "EUR",
    importer_slug: "kraken_spot",
    importer_name: "KrakenPro Spot Trades",
  },
];
const positions = [
  {
    symbol: "BTC",
    nombre: "Bitcoin",
    titulos: 0.01234567,
    coste_total: 1200,
    precio_actual: 70000,
    valor_actual: 1400,
    pnl: 200,
    pnl_realizada: 25,
  },
  ...Array.from({ length: 16 }, (_, index) => ({
    symbol: `T${String(index).padStart(2, "0")}`,
    nombre: `Test ${index}`,
    titulos: 1,
    coste_total: 100 + index,
    precio_actual: 110 + index,
    valor_actual: 110 + index,
    pnl: 10,
    pnl_realizada: 0,
  })),
];
const orders: CryptoOrder[] = [
  {
    id: "btc-1",
    trade_date: "2026-01-10",
    settlement_date: null,
    quantity: 0.01234567,
    net_amount: 1200,
    fee: 1,
    account_id: accountOneId,
    account_name: "KrakenPro",
    platform: "KrakenPro",
    operation_type: "buy",
    cash_flow_type: "none",
    symbol: "BTC",
    asset_name: "Bitcoin",
    unit_price: 60000,
    currency: "EUR",
    base_currency: "EUR",
    base_unit_price: 60000,
    base_net_amount: 1200,
    base_fee: 1,
    fx_rate_to_base: 1,
    fx_rate_date: "2026-01-10",
    fx_source: "identity",
    market: "",
    provider_operation_type: "Compra",
  },
  {
    id: "eth-1",
    trade_date: "2026-05-10",
    settlement_date: null,
    quantity: 0.5,
    net_amount: 1499,
    fee: 1,
    account_id: accountOneId,
    account_name: "KrakenPro",
    platform: "KrakenPro",
    operation_type: "sell",
    cash_flow_type: "none",
    symbol: "ETH",
    asset_name: "Ethereum",
    unit_price: 3000,
    currency: "USD",
    base_currency: "EUR",
    base_unit_price: 2800,
    base_net_amount: 1400,
    base_fee: 1.2,
    fx_rate_to_base: 0.93,
    fx_rate_date: "2026-05-10",
    fx_source: "test",
    market: "",
    provider_operation_type: "Venta",
  },
];
const performance = {
  range: "1y",
  account_id: "all",
  moneda_base: "EUR",
  data: [
    {
      fecha: "2026-01-10",
      valor: 1000,
      invertido: 900,
      pnl: 100,
      pnl_pct: 11.11,
    },
    {
      fecha: "2026-07-10",
      valor: 1400,
      invertido: 1200,
      pnl: 200,
      pnl_pct: 16.67,
    },
  ],
};
const candles = [
  {
    fecha: "2026-01-10",
    precio: 60000,
    open: 59000,
    high: 61000,
    low: 58000,
    close: 60000,
  },
  {
    fecha: "2026-07-10",
    precio: 70000,
    open: 68000,
    high: 71000,
    low: 67000,
    close: 70000,
  },
];

let mockAccounts: CryptoAccount[] = [...accounts];
let mockOrders: CryptoOrder[] = [...orders];
function makeCryptoInstrument(
  id: string,
  symbol: string,
  ticker: string,
  name: string,
): CryptoInstrument {
  return {
    id,
    kind: "crypto",
    name,
    quote_currency: "EUR",
    identifiers: [
      { scheme: "crypto_symbol", value: symbol, venue: "", is_primary: true },
      { scheme: "yahoo", value: ticker, venue: "", is_primary: true },
    ],
    asset_class: null,
    subtype: null,
    is_active: true,
  };
}

let mockInstruments: CryptoInstrument[] = [
  makeCryptoInstrument(
    "00000000-0000-0000-0000-000000000501",
    "BTC",
    "BTC-EUR",
    "Bitcoin",
  ),
  makeCryptoInstrument(
    "00000000-0000-0000-0000-000000000502",
    "ETH",
    "ETH-EUR",
    "Ethereum",
  ),
  makeCryptoInstrument(
    "00000000-0000-0000-0000-000000000520",
    "T15",
    "T15-EUR",
    "Test 15",
  ),
];
let mockPrices: CryptoPrice[] = [
  {
    id: "00000000-0000-0000-0000-000000000701",
    instrument_id: "00000000-0000-0000-0000-000000000501",
    quoted_at: "2026-07-10T00:00:00+00:00",
    close: 70000,
    currency: "EUR",
    base_close: 70000,
    base_currency: "EUR",
    fx_rate_to_base: 1,
    fx_rate_date: "2026-07-10",
    fx_source: "identity",
    source: "yahoo",
  },
];

function requestBody(init?: RequestInit) {
  if (!init?.body || typeof init.body !== "string") return {};
  return JSON.parse(init.body) as Record<string, unknown>;
}

function installApiMock() {
  mockAccounts = [...accounts];
  mockOrders = [...orders];
  mockInstruments = [
    makeCryptoInstrument(
      "00000000-0000-0000-0000-000000000501",
      "BTC",
      "BTC-EUR",
      "Bitcoin",
    ),
    makeCryptoInstrument(
      "00000000-0000-0000-0000-000000000502",
      "ETH",
      "ETH-EUR",
      "Ethereum",
    ),
    makeCryptoInstrument(
      "00000000-0000-0000-0000-000000000520",
      "T15",
      "T15-EUR",
      "Test 15",
    ),
  ];
  mockPrices = [
    {
      id: "00000000-0000-0000-0000-000000000701",
      instrument_id: "00000000-0000-0000-0000-000000000501",
      quoted_at: "2026-07-10T00:00:00+00:00",
      close: 70000,
      currency: "EUR",
      base_close: 70000,
      base_currency: "EUR",
      fx_rate_to_base: 1,
      fx_rate_date: "2026-07-10",
      fx_source: "identity",
      source: "yahoo",
    },
  ];
  apiMock.mockReset();
  apiMock.mockImplementation(async (path, init) => {
    const method = (init?.method ?? "GET").toUpperCase();
    if (path === "/crypto-accounts") {
      if (method === "GET") return mockAccounts;
      if (method === "POST") {
        const body = requestBody(init);
        const created: CryptoAccount = {
          id: accountTwoId,
          name: String(body.name ?? ""),
          platform: String(body.platform ?? ""),
          type: "",
          currency: String(body.currency ?? "EUR"),
          importer_slug: String(body.importer_slug ?? ""),
          importer_name: "Manual",
        };
        mockAccounts = [...mockAccounts, created];
        return created;
      }
    }
    if (path.startsWith("/crypto-accounts/") && method === "PUT") {
      const id = path.split("/").at(-1) ?? "";
      const body = requestBody(init);
      const current =
        mockAccounts.find((account) => account.id === id) ?? accounts[0];
      const updated = { ...current, ...body, id };
      mockAccounts = mockAccounts.map((account) =>
        account.id === id ? updated : account,
      );
      return updated;
    }
    if (path.startsWith("/crypto-accounts/") && method === "DELETE") {
      const id = path.split("/").at(-1) ?? "";
      mockAccounts = mockAccounts.filter((account) => account.id !== id);
      return undefined;
    }
    if (path === "/importers" && method === "GET") return [importer];
    if (path.startsWith("/crypto-analysis")) return positions;
    if (
      (path === "/crypto-orders" || path.startsWith("/crypto-orders?")) &&
      method === "GET"
    )
      return mockOrders;
    if (path === "/crypto-orders" && method === "POST") {
      const body = requestBody(init);
      const created: CryptoOrder = {
        id: `created-${mockOrders.length + 1}`,
        trade_date: String(body.trade_date ?? ""),
        settlement_date: null,
        quantity: Number(body.quantity ?? 0),
        net_amount: Number(body.net_amount ?? 0),
        fee: Number(body.fee ?? 0),
        account_id: String(body.account_id ?? ""),
        account_name: "KrakenPro",
        platform: "KrakenPro",
        operation_type: body.operation_type as CryptoOrder["operation_type"],
        cash_flow_type: "none",
        symbol: String(body.symbol ?? ""),
        asset_name:
          mockInstruments.find(
            (item) => instrumentIdentity(item) === body.symbol,
          )?.name ?? String(body.symbol ?? ""),
        unit_price: Number(body.unit_price ?? 0),
        currency: String(body.currency ?? "EUR"),
        base_currency: "EUR",
        base_unit_price: Number(body.unit_price ?? 0),
        base_net_amount: Number(body.net_amount ?? 0),
        base_fee: Number(body.fee ?? 0),
        fx_rate_to_base: 1,
        fx_rate_date: String(body.trade_date ?? "") || null,
        fx_source: "identity",
        market: "",
        provider_operation_type: "",
      };
      mockOrders = [...mockOrders, created];
      return created;
    }
    if (path.startsWith("/crypto-orders/") && method === "PUT") {
      const id = path.split("/").at(-1);
      const body = requestBody(init);
      mockOrders = mockOrders.map((order) =>
        order.id === id ? { ...order, ...body } : order,
      );
      return mockOrders.find((order) => order.id === id);
    }
    if (path.startsWith("/crypto-orders/") && method === "DELETE") {
      const id = path.split("?")[0].split("/").at(-1);
      mockOrders = mockOrders.filter((order) => order.id !== id);
      return undefined;
    }
    if (path === "/cryptos" && method === "GET") return mockInstruments;
    if (path === "/cryptos" && method === "POST") {
      const body = requestBody(init);
      const identifiers = (body.identifiers ?? []) as InstrumentIdentifier[];
      const created: CryptoInstrument = {
        id: "00000000-0000-0000-0000-000000000503",
        kind: "crypto",
        name: String(body.name ?? ""),
        quote_currency: String(body.quote_currency ?? "EUR"),
        identifiers,
        asset_class: (body.asset_class as string | null | undefined) ?? null,
        subtype: (body.subtype as string | null | undefined) ?? null,
        is_active: Boolean(body.is_active ?? true),
      };
      mockInstruments = [...mockInstruments, created];
      return created;
    }
    if (path.startsWith("/cryptos/") && method === "PUT") {
      const id = path.split("/").at(-1);
      const body = requestBody(init);
      mockInstruments = mockInstruments.map((item) => {
        if (item.id !== id) return item;
        return {
          ...item,
          name: String(body.name ?? item.name),
          quote_currency: String(body.quote_currency ?? item.quote_currency),
          identifiers: (body.identifiers ??
            item.identifiers) as InstrumentIdentifier[],
          asset_class:
            (body.asset_class as string | null | undefined) ?? item.asset_class,
          subtype: (body.subtype as string | null | undefined) ?? item.subtype,
          is_active: Boolean(body.is_active ?? item.is_active),
        };
      });
      return mockInstruments.find((item) => item.id === id);
    }
    if (path === "/crypto-prices" && method === "GET") return mockPrices;
    if (path === "/crypto-prices/fetch" && method === "POST")
      return { results: [] };
    if (path.startsWith("/investment-performance/crypto?"))
      return {
        ...performance,
        range: new URLSearchParams(path.split("?")[1]).get("range") ?? "custom",
      };
    if (path.startsWith("/crypto-chart/")) {
      const instrumentId = decodeURIComponent(
        path.split("/")[2]?.split("?")[0] ?? "BTC",
      );
      const symbol = mockInstruments.find((item) => item.id === instrumentId)
        ? instrumentIdentity(
            mockInstruments.find((item) => item.id === instrumentId)!,
          )
        : instrumentId;
      return {
        instrument_id: instrumentId,
        ticker: `${symbol}-EUR`,
        currency: "EUR",
        base_currency: "EUR",
        range: "1y",
        data: candles.map(({ fecha, precio: _precio, ...candle }) => ({
          date: fecha,
          ...candle,
        })),
      };
    }
    if (path.startsWith("/account-imports/crypto/") && method === "POST")
      return { imported: 1, skipped: 0 };
    throw new Error(`Unexpected path: ${path}`);
  });
}

describe("CryptoView canonical migration", () => {
  afterEach(() => {
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      value: localStorageStub,
    });
  });

  beforeEach(() => {
    applyLocale("es-ES", false);
    window.history.replaceState({}, "", "/app/crypto");
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      value: localStorageStub,
    });
    localStorageStub.clear();
    installApiMock();
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
  });

  it("loads the canonical account bar, overview and aggregate performance for all accounts", async () => {
    const wrapper = mount(CryptoView);
    await flushPromises();

    expect(wrapper.find(".investment-account-bar").exists()).toBe(true);
    expect(wrapper.find(".investment-overview").exists()).toBe(true);
    expect(wrapper.text()).toContain("Rendimiento Crypto");
    expect(wrapper.text()).toContain("Todas las posiciones Crypto");
    expect(apiMock).toHaveBeenCalledWith(
      "/investment-performance/crypto?account_id=all&range=1y",
    );
    expect(wrapper.text()).toContain("0,01234567");
    expect(wrapper.findAll(".fund-asset-row")).toHaveLength(5);
  });

  it("requests performance for the selected account and supports custom performance ranges", async () => {
    const wrapper = mount(CryptoView);
    await flushPromises();
    await wrapper.get(".investment-account-bar select").setValue(accountOneId);
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      `/investment-performance/crypto?account_id=${accountOneId}&range=1y`,
    );

    const calendarButton = wrapper
      .findAll(".fund-range-control button")
      .find((button) => button.text() === "Calendario");
    await calendarButton!.trigger("click");
    const dialog = wrapper.get(
      'dialog[aria-labelledby="calendar-dialog-title"]',
    );
    await dialog.findAll("input")[0].setValue("2026-02-01");
    await dialog.findAll("input")[1].setValue("2026-06-30");
    await dialog.get("form").trigger("submit");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      `/investment-performance/crypto?account_id=${accountOneId}&start=2026-02-01&end=2026-06-30`,
    );
  });

  it("persists Crypto performance range, custom dates and chart mode across remounts", async () => {
    const first = mount(CryptoView);
    await flushPromises();
    await first
      .findAll(".fund-mode-control button")
      .find((button) => button.text() === "Rendimiento")!
      .trigger("click");
    await first
      .findAll(".fund-range-control button")
      .find((button) => button.text() === "Calendario")!
      .trigger("click");
    const dialog = first.get('dialog[aria-labelledby="calendar-dialog-title"]');
    await dialog.findAll("input")[0].setValue("2026-02-01");
    await dialog.findAll("input")[1].setValue("2026-06-30");
    await dialog.get("form").trigger("submit");
    await flushPromises();
    first.unmount();

    apiMock.mockClear();
    const second = mount(CryptoView);
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/investment-performance/crypto?account_id=all&start=2026-02-01&end=2026-06-30",
    );
    expect(second.get('[data-testid="performance-chart"]').text()).toContain(
      "return",
    );
    expect(
      second
        .findAll(".fund-mode-control button")
        .find((button) => button.text() === "Rendimiento")!
        .attributes("aria-pressed"),
    ).toBe("true");
    second.unmount();
  });

  it("falls back safely when stored Crypto preferences are corrupt or use invalid enums", async () => {
    testStorage.set("finanzr:crypto:preferences:v1", "{not-json");
    const corrupt = mount(CryptoView);
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/investment-performance/crypto?account_id=all&range=1y",
    );
    corrupt.unmount();

    localStorageStub.clear();
    testStorage.set(
      "finanzr:crypto:preferences:v1",
      JSON.stringify({
        range: "forever",
        mode: "chart",
        customStart: "2026-02-01",
        customEnd: "2026-03-01",
      }),
    );
    apiMock.mockClear();
    const invalid = mount(CryptoView);
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/investment-performance/crypto?account_id=all&range=1y",
    );
    expect(invalid.get('[data-testid="performance-chart"]').text()).toContain(
      "value",
    );
    invalid.unmount();
  });

  it.each([
    ["an impossible calendar date", "2026-02-31", "2026-03-01"],
    ["an inverted custom range", "2026-05-01", "2026-04-01"],
  ])(
    "falls back to the valid one-year range for %s",
    async (_label, customStart, customEnd) => {
      testStorage.set(
        "finanzr:crypto:preferences:v1",
        JSON.stringify({
          range: "custom",
          mode: "return",
          customStart,
          customEnd,
        }),
      );
      const wrapper = mount(CryptoView);
      await flushPromises();
      expect(apiMock).toHaveBeenCalledWith(
        "/investment-performance/crypto?account_id=all&range=1y",
      );
      expect(wrapper.get('[data-testid="performance-chart"]').text()).toContain(
        "return",
      );
      expect(
        apiMock.mock.calls.some(
          ([path]) =>
            path.includes("2026-02-31") || path.includes("2026-05-01"),
        ),
      ).toBe(false);
      wrapper.unmount();
    },
  );

  it("rejects year zero in persisted custom preferences", async () => {
    testStorage.set(
      "finanzr:crypto:preferences:v1",
      JSON.stringify({
        range: "custom",
        customStart: "0000-01-01",
        customEnd: "2026-03-01",
      }),
    );
    const wrapper = mount(CryptoView);
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/investment-performance/crypto?account_id=all&range=1y",
    );
    expect(
      apiMock.mock.calls.some(([path]) => path.includes("0000-01-01")),
    ).toBe(false);
    wrapper.unmount();
  });

  it("keeps rendering when Crypto storage throws on read and write", async () => {
    const getItem = vi.fn(() => {
      throw new Error("storage read blocked");
    });
    const setItem = vi.fn(() => {
      throw new Error("storage write blocked");
    });
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      value: { getItem, setItem },
    });
    const wrapper = mount(CryptoView);
    await flushPromises();
    expect(wrapper.text()).toContain("Rendimiento Crypto");
    await wrapper
      .findAll(".fund-mode-control button")
      .find((button) => button.text() === "Rendimiento")!
      .trigger("click");
    await wrapper
      .findAll(".fund-range-control button")
      .find((button) => button.text() === "2A")!
      .trigger("click");
    await flushPromises();
    expect(getItem).toHaveBeenCalled();
    expect(setItem).toHaveBeenCalled();
    expect(wrapper.text()).toContain("Rendimiento Crypto");
    wrapper.unmount();
  });

  it("keeps one inline candlestick detail open and reloads it by range", async () => {
    const wrapper = mount(CryptoView);
    await flushPromises();
    const rows = wrapper.findAll(".fund-position-row");
    await rows[0].trigger("click");
    await flushPromises();
    expect(wrapper.findAll(".fund-inline-detail-row")).toHaveLength(1);
    expect(wrapper.get('[data-testid="crypto-chart"]').text()).toBe(
      "2-1-97200.0709560518",
    );
    expect(
      wrapper
        .get('[data-testid="crypto-chart"]')
        .attributes("data-marker-shape"),
    ).toBe("pin");

    const secondRow = rows.find((row) => row.text().includes("T15"))!;
    await secondRow.trigger("click");
    await flushPromises();
    expect(wrapper.findAll(".fund-inline-detail-row")).toHaveLength(1);
    expect(wrapper.find('[data-testid="crypto-chart"]').exists()).toBe(true);
    expect(apiMock).toHaveBeenCalledWith(
      "/crypto-chart/00000000-0000-0000-0000-000000000520?range=1y&interval=1d",
    );
  });

  it("sorts positions, collapses sections and preserves exact crypto quantities", async () => {
    const wrapper = mount(CryptoView);
    await flushPromises();
    const addAssetButton = wrapper.get('button[aria-label="Añadir activo"]');
    expect(addAssetButton.text()).toBe("Añadir activo");
    expect(addAssetButton.attributes("title")).toBe("Añadir activo");
    expect(addAssetButton.get("svg path").attributes("d")).toBe(
      "M10 4v12M4 10h12",
    );
    expect(wrapper.text()).not.toContain("Editar activo");
    expect(
      wrapper.findAll('button[aria-label="Editar activo Crypto"]'),
    ).toHaveLength(positions.length);
    expect(wrapper.find(".position-table-scroll").exists()).toBe(true);

    const quantitySort = wrapper
      .findAll(".fund-sort-button")
      .find((button) => button.text().includes("Cantidad"));
    await quantitySort!.trigger("click");
    expect(wrapper.get(".fund-sort-button").attributes("aria-label")).toContain(
      "ascendente",
    );
    expect(wrapper.findAll(".movement-table tbody tr")).toHaveLength(2);
    expect(wrapper.text()).toContain("0,01234567");

    const positionsButton = wrapper.get(
      '[aria-controls="crypto-positions-content"]',
    );
    const movementsButton = wrapper.get(
      '[aria-controls="crypto-movements-content"]',
    );
    expect(positionsButton.get("svg").attributes("data-direction")).toBe("up");
    expect(movementsButton.get("svg").attributes("data-direction")).toBe("up");

    await positionsButton.trigger("click");
    expect(wrapper.get("#crypto-positions-content").isVisible()).toBe(false);
    expect(positionsButton.classes()).toContain("collapsed");
    expect(positionsButton.get("svg").attributes("data-direction")).toBe(
      "down",
    );

    await movementsButton.trigger("click");
    expect(wrapper.get("#crypto-movements-content").isVisible()).toBe(false);
    expect(movementsButton.classes()).toContain("collapsed");
    expect(movementsButton.get("svg").attributes("data-direction")).toBe(
      "down",
    );
  });

  it("clamps movement pagination after deleting the only item on the last page", async () => {
    mockOrders = [
      ...orders,
      ...Array.from({ length: 14 }, (_, index) => ({
        ...orders[0],
        id: `page-${index}`,
        trade_date: `2026-02-${String(index + 1).padStart(2, "0")}`,
      })),
    ];
    const wrapper = mount(CryptoView);
    await flushPromises();
    expect(wrapper.get(".movement-pagination").text()).toContain(
      "Página 1 de 2",
    );
    expect(wrapper.get(".movement-pagination").text()).toContain("Anterior");
    expect(wrapper.get(".movement-pagination").text()).toContain("Siguiente");
    await wrapper
      .get(".movement-pagination button:last-child")
      .trigger("click");
    await flushPromises();
    const lastPageRow = wrapper.findAll(".movement-table tbody tr").at(-1)!;
    await lastPageRow.get(".delete-order").trigger("click");
    await wrapper.get(".movement-delete-dialog form").trigger("submit");
    await flushPromises();

    expect(wrapper.find(".movement-pagination").exists()).toBe(false);
    expect(wrapper.findAll(".movement-table tbody tr")).toHaveLength(15);
    expect(wrapper.text()).not.toContain(
      "No hay movimientos para estos filtros",
    );
  });

  it("preserves fees, original currency values and movement operations", async () => {
    const wrapper = mount(CryptoView);
    await flushPromises();
    const ethRow = wrapper.get('[data-testid="movement-eth-1"]');
    expect(ethRow.text()).toContain("1,20");
    expect(ethRow.text()).toContain("2800,00");
    expect(ethRow.text()).toContain("Venta");
    expect(ethRow.find("button").exists()).toBe(true);
  });

  it("keeps account, asset, movement and price CRUD paths wired to Crypto APIs", async () => {
    const wrapper = mount(CryptoView);
    await flushPromises();

    await wrapper
      .get('[data-testid="movement-btc-1"] .movement-row-actions button')
      .trigger("click");
    const existingMovementDialog = wrapper.get(".movement-editor-dialog");
    const existingMovementInputs = existingMovementDialog.findAll("input");
    await existingMovementInputs.at(-1)!.setValue("2");
    await existingMovementDialog.get("form").trigger("submit");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/crypto-orders/btc-1",
      expect.objectContaining({ method: "PUT" }),
    );

    const addAccount = wrapper
      .findAll(".investment-account-bar button")
      .find((button) => button.text().includes("Añadir cuenta"))!;
    await addAccount.trigger("click");
    const accountDialog = wrapper.get(".account-dialog");
    await accountDialog.findAll("input")[0].setValue("Trading account");
    await accountDialog.findAll("input")[1].setValue("KrakenPro");
    await accountDialog.findAll("input")[2].setValue("EUR");
    await accountDialog.get("select").setValue("kraken_spot");
    await accountDialog.get("form").trigger("submit");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/crypto-accounts",
      expect.objectContaining({ method: "POST" }),
    );

    const manageAccount = wrapper
      .findAll(".investment-account-bar button")
      .find((button) => button.text().includes("Gestionar cuenta"))!;
    await manageAccount.trigger("click");
    const manageDialog = wrapper.get(".account-dialog");
    await manageDialog.findAll("input")[0].setValue("Trading account updated");
    await manageDialog.get("form").trigger("submit");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      `/crypto-accounts/${accountTwoId}`,
      expect.objectContaining({ method: "PUT" }),
    );

    await wrapper.get('button[aria-label="Añadir activo"]').trigger("click");
    const assetDialog = wrapper.get(".asset-editor-dialog");
    await assetDialog.findAll("input")[0].setValue("SOL");
    await assetDialog.findAll("input")[1].setValue("Solana");
    await assetDialog.findAll("input")[2].setValue("SOL-EUR");
    await assetDialog.get("form").trigger("submit");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/cryptos",
      expect.objectContaining({ method: "POST" }),
    );

    await wrapper.get(".fund-edit-icon-button").trigger("click");
    const editAssetDialog = wrapper.get(".asset-editor-dialog");
    await editAssetDialog
      .get("select")
      .setValue("00000000-0000-0000-0000-000000000501");
    await editAssetDialog.findAll("input").at(-1)!.setValue("BTC-USD");
    await editAssetDialog.get("form").trigger("submit");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/cryptos/00000000-0000-0000-0000-000000000501",
      expect.objectContaining({ method: "PUT" }),
    );

    const addMovement = wrapper.find(".add-movement");
    await addMovement.trigger("click");
    const movementDialog = wrapper.get(".movement-editor-dialog");
    const movementInputs = movementDialog.findAll("input");
    await movementInputs[0].setValue("2026-07-20");
    await movementInputs[1].setValue("0.01");
    await movementInputs[2].setValue("70000");
    await movementInputs[3].setValue("700");
    await movementInputs[4].setValue("EUR");
    await movementInputs[5].setValue("1");
    await movementDialog.get("form").trigger("submit");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/crypto-orders",
      expect.objectContaining({ method: "POST" }),
    );

    const refresh = wrapper
      .findAll(".investment-overview .fund-action-button")
      .find((button) => button.text().includes("Actualizar"))!;
    await refresh.trigger("click");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/crypto-prices/fetch",
      expect.objectContaining({ method: "POST" }),
    );

    const manageAfterMutations = wrapper
      .findAll(".investment-account-bar button")
      .find((button) => button.text().includes("Gestionar cuenta"))!;
    await manageAfterMutations.trigger("click");
    const deleteDialog = wrapper.get(".account-dialog");
    const deleteAccount = deleteDialog
      .findAll("button")
      .find((button) => button.text().includes("Eliminar cuenta"))!;
    await deleteAccount.trigger("click");
    await deleteDialog
      .findAll("button")
      .find((button) => button.text().includes("Confirmar eliminación"))!
      .trigger("click");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      `/crypto-accounts/${accountTwoId}`,
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("keeps the KrakenPro importer contextual to the selected account", async () => {
    window.history.replaceState({}, "", `/app/crypto?account=${accountOneId}`);
    const wrapper = mount(CryptoView);
    await flushPromises();
    const importButton = wrapper
      .findAll(".investment-account-bar button")
      .find((button) => button.text().includes("Importar extracto"))!;
    await importButton.trigger("click");
    await wrapper.vm.$nextTick();
    const importDialog = document.body.querySelector(
      ".import-statement-dialog",
    )!;
    expect(importDialog.textContent).toContain("KrakenPro Spot Trades");
    const file = new File(["spot trades"], "kraken.csv", { type: "text/csv" });
    const fileInput = importDialog.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    Object.defineProperty(fileInput, "files", {
      configurable: true,
      value: [file],
    });
    fileInput.dispatchEvent(new Event("change", { bubbles: true }));
    importDialog
      .querySelector("form")!
      .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      `/account-imports/crypto/${accountOneId}`,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("shows translated performance errors and an explicit empty-history state", async () => {
    const fallback = apiMock.getMockImplementation()!;
    apiMock.mockImplementation(async (path, init) => {
      if (path.startsWith("/investment-performance/crypto?")) throw null;
      return fallback(path, init);
    });
    const errorWrapper = mount(CryptoView);
    await flushPromises();
    expect(errorWrapper.text()).toContain(
      "No se pudo cargar el rendimiento de la cartera",
    );
    errorWrapper.unmount();

    installApiMock();
    const emptyFallback = apiMock.getMockImplementation()!;
    apiMock.mockImplementation(async (path, init) => {
      if (path.startsWith("/investment-performance/crypto?"))
        return { ...performance, data: [] };
      if (path.startsWith("/crypto-analysis")) return [];
      return emptyFallback(path, init);
    });
    const emptyWrapper = mount(CryptoView);
    await flushPromises();
    expect(emptyWrapper.text()).toContain("Histórico insuficiente");
    expect(emptyWrapper.text()).toContain("No hay posiciones abiertas");
    emptyWrapper.unmount();
  });

  it("ignores stale performance responses after a newer range request", async () => {
    let resolveFirst: ((value: unknown) => void) | undefined;
    let resolveSecond: ((value: unknown) => void) | undefined;
    let performanceCalls = 0;
    apiMock.mockImplementation(async (path) => {
      if (path.startsWith("/investment-performance/crypto?")) {
        performanceCalls += 1;
        return new Promise((resolve) => {
          if (performanceCalls === 1) resolveFirst = resolve;
          else resolveSecond = resolve;
        });
      }
      if (path === "/crypto-accounts") return accounts;
      if (path === "/importers") return [importer];
      if (path.startsWith("/crypto-analysis")) return positions;
      if (path.startsWith("/crypto-orders")) return orders;
      if (path === "/cryptos")
        return [
          makeCryptoInstrument(
            "00000000-0000-0000-0000-000000000501",
            "BTC",
            "BTC-EUR",
            "Bitcoin",
          ),
        ];
      if (path === "/crypto-prices") return [];
      throw new Error(`Unexpected path: ${path}`);
    });
    const wrapper = mount(CryptoView);
    await flushPromises();
    const sixMonths = wrapper
      .findAll(".fund-range-control button")
      .find((button) => button.text() === "6M");
    await sixMonths!.trigger("click");
    await flushPromises();
    resolveSecond?.({
      ...performance,
      range: "6m",
      data: [
        { ...performance.data[0], pnl: -777 },
        ...performance.data.slice(1),
      ],
    });
    await flushPromises();
    resolveFirst?.({
      ...performance,
      range: "1y",
      data: [
        { ...performance.data[0], pnl: 111 },
        ...performance.data.slice(1),
      ],
    });
    await flushPromises();
    expect(wrapper.text()).toContain("+977,00");
    expect(wrapper.text()).not.toContain("+89,00");
  });

  it("ignores stale account dashboard data after a newer account selection", async () => {
    const wrapper = mount(CryptoView);
    await flushPromises();
    let resolveAccount: ((value: unknown) => void) | undefined;
    let resolveAll: ((value: unknown) => void) | undefined;
    const fallback = apiMock.getMockImplementation()!;
    apiMock.mockImplementation(async (path, init) => {
      if (path === `/crypto-analysis?account_id=${accountOneId}`) {
        return new Promise((resolve) => {
          resolveAccount = resolve;
        });
      }
      if (path === "/crypto-analysis") {
        return new Promise((resolve) => {
          resolveAll = resolve;
        });
      }
      return fallback(path, init);
    });
    const select = wrapper.get(".investment-account-bar select");
    await select.setValue(accountOneId);
    await select.setValue("all");
    await flushPromises();
    resolveAll?.(positions);
    await flushPromises();
    resolveAccount?.([]);
    await flushPromises();

    expect((select.element as HTMLSelectElement).value).toBe("all");
    expect(wrapper.text()).toContain("Bitcoin");
  });

  it("ignores a stale inline chart response after switching assets", async () => {
    let resolveFirst: ((value: unknown) => void) | undefined;
    let resolveSecond: ((value: unknown) => void) | undefined;
    let chartCalls = 0;
    const fallback = apiMock.getMockImplementation()!;
    apiMock.mockImplementation(async (path, init) => {
      if (path.startsWith("/crypto-chart/")) {
        chartCalls += 1;
        return new Promise((resolve) => {
          if (chartCalls === 1) resolveFirst = resolve;
          else resolveSecond = resolve;
        });
      }
      return fallback(path, init);
    });
    const wrapper = mount(CryptoView);
    await flushPromises();
    const rows = wrapper.findAll(".fund-position-row");
    await rows[0].trigger("click");
    await rows.find((row) => row.text().includes("T15"))!.trigger("click");
    resolveSecond?.({
      instrument_id: "00000000-0000-0000-0000-000000000520",
      ticker: "T15-EUR",
      currency: "EUR",
      base_currency: "EUR",
      range: "1y",
      data: [
        {
          date: candles[0].fecha,
          open: candles[0].open,
          high: candles[0].high,
          low: candles[0].low,
          close: candles[0].close,
        },
      ],
    });
    await flushPromises();
    resolveFirst?.({
      instrument_id: "00000000-0000-0000-0000-000000000501",
      ticker: "BTC-EUR",
      currency: "EUR",
      base_currency: "EUR",
      range: "1y",
      data: candles.map(({ fecha, precio: _precio, ...candle }) => ({
        date: fecha,
        ...candle,
      })),
    });
    await flushPromises();

    expect(wrapper.get('[data-testid="crypto-chart"]').text()).toBe("1-0-115");
  });
});
