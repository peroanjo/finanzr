import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { applyLocale, registerMessages } from "../../i18n";
import { stocksMessages } from "../../i18n/stocksMessages";
import type { StockOrder, StockPosition } from "../../types/api";
import StockPositionsPanel, {
  type StockPositionsPanelProps,
} from "./StockPositionsPanel.vue";

registerMessages(stocksMessages);

const storage = new Map<string, string>();
vi.stubGlobal("localStorage", {
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
});

vi.mock("../CryptoCandlestickChart.vue", () => ({
  default: {
    props: ["points", "operations", "averagePrice", "operationMarkerShape"],
    template:
      '<div data-testid="stock-chart" :data-marker-shape="operationMarkerShape">{{ points.length }}-{{ operations.length }}</div>',
  },
}));

const position: StockPosition = {
  instrument_id: "stock-1",
  kind: "stock",
  name: "NVIDIA",
  quantity: 2,
  cost: 200,
  current_price: 125,
  current_value: 250,
  unrealized_pnl: 50,
  realized_pnl: 0,
  currency: "EUR",
  base_currency: "EUR",
};

const order: StockOrder = {
  id: "order-1",
  account_id: "account-1",
  account_name: "Account",
  platform: "Broker",
  asset_name: "NVIDIA",
  trade_date: "2026-01-01",
  settlement_date: null,
  operation_type: "buy",
  cash_flow_type: "none",
  quantity: 2,
  unit_price: 100,
  net_amount: 200,
  fee: 1,
  currency: "EUR",
  base_currency: "EUR",
  base_unit_price: 100,
  base_net_amount: 200,
  base_fee: 1,
  fx_rate_to_base: 1,
  fx_rate_date: "2026-01-01",
  fx_source: "identity",
  market: "",
  provider_operation_type: "Buy",
  isin: "US-ISIN",
  is_saveback: false,
};

const baseProps: StockPositionsPanelProps = {
  positions: [position],
  pricedPositions: 1,
  selectedAccountLabel: "All accounts",
  baseCurrency: "EUR",
  allocationItems: [
    {
      key: "stock-1",
      label: "NVIDIA",
      value: 250,
      share: 1,
      color: "#3ddc97",
    },
  ],
  allocationTotal: 250,
  sortedPositions: [position],
  positionSortColumns: [
    { key: "asset", label: "Asset" },
    { key: "value", label: "Value" },
  ],
  positionSortKey: "value",
  positionSortDirection: "desc",
  selectedInstrumentId: "",
  selectedChartOrders: [order],
  averagePrice: 100,
  chartPoints: [
    { date: "2026-01-01", open: 99, high: 102, low: 98, close: 100 },
  ],
  chartLoading: false,
  chartError: "",
  chartRangeLabel: "1 year",
  ranges: [{ key: "1y", label: "1Y" }],
  chartRange: "1y",
  formatMoney: (value) => `€${value}`,
  formatPercentage: (value) => `${value * 100}%`,
  formatQuantity: (value) => String(value),
  formatSignedMoney: (value) => `+€${value}`,
  positionIdentity: () => "US-ISIN",
  assetTicker: () => "NVDA",
  marketValueSegmentAria: () => "NVIDIA 100%",
  positionAriaSort: (key) => (key === "value" ? "descending" : "none"),
  positionSortAria: (key) => `Sort ${key}`,
  detailId: (id) => `stock-detail-${id}`,
};

describe("StockPositionsPanel", () => {
  beforeEach(() => {
    storage.clear();
    applyLocale("en");
  });

  it("owns collapse persistence and preserves disclosure and add-asset events", async () => {
    const wrapper = mount(StockPositionsPanel, { props: baseProps });
    const collapse = wrapper.get(
      'button[aria-controls="stock-positions-content"]',
    );

    expect(collapse.attributes("aria-expanded")).toBe("true");
    expect(wrapper.get(".fund-position-row").text()).toContain("NVIDIA");

    await collapse.trigger("click");
    expect(collapse.attributes("aria-expanded")).toBe("false");
    expect(localStorage.getItem("finanzr-stocks-positions-collapsed")).toBe(
      "true",
    );
    expect(wrapper.get("#stock-positions-content").isVisible()).toBe(false);

    await wrapper.get(".fund-position-disclosure").trigger("click");
    await wrapper.get('button[aria-label="Add asset"]').trigger("click");
    await wrapper
      .get('.fund-sort-button[aria-label="Sort value"]')
      .trigger("click");
    expect(wrapper.emitted("toggle-position")).toEqual([["stock-1"]]);
    expect(wrapper.emitted("add-asset")).toHaveLength(1);
    expect(wrapper.emitted("sort")).toEqual([["value"]]);
  });

  it("renders chart states and emits chart, retry, and edit events", async () => {
    const wrapper = mount(StockPositionsPanel, {
      props: { ...baseProps, selectedInstrumentId: "stock-1" },
    });
    expect(wrapper.get('[data-testid="stock-chart"]').text()).toBe("1-1");
    expect(
      wrapper
        .get('[data-testid="stock-chart"]')
        .attributes("data-marker-shape"),
    ).toBe("pin");

    await wrapper.get(".fund-range-control button").trigger("click");
    await wrapper.get(".fund-edit-icon-button").trigger("click");
    expect(wrapper.emitted("select-chart-range")).toEqual([["1y"]]);
    expect(wrapper.emitted("edit-position")?.[0]).toEqual([position]);

    await wrapper.setProps({ chartPoints: [], chartError: "Unavailable" });
    expect(wrapper.get(".fund-chart-state.error-state").text()).toContain(
      "Unavailable",
    );
    await wrapper.get(".fund-chart-state button").trigger("click");
    expect(wrapper.emitted("retry-chart")).toHaveLength(1);
  });
});
