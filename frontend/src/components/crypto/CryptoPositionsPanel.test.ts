import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { applyLocale, registerMessages } from "../../i18n";
import { cryptoMessages } from "../../i18n/cryptoMessages";
import type { CryptoOrder, CryptoPosition } from "../../types/api";
import CryptoPositionsPanel, {
  type CryptoPositionsPanelProps,
} from "./CryptoPositionsPanel.vue";

registerMessages(cryptoMessages);

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
      '<div data-testid="crypto-position-chart" :data-marker-shape="operationMarkerShape">{{ points.length }}-{{ operations.length }}</div>',
  },
}));

const position: CryptoPosition = {
  instrument_id: "crypto-1",
  kind: "crypto",
  name: "Bitcoin",
  quantity: 0.5,
  cost: 1000,
  current_price: 2400,
  current_value: 1200,
  unrealized_pnl: 200,
  realized_pnl: 0,
  currency: "EUR",
  base_currency: "EUR",
};

const order = {
  id: "order-1",
  trade_date: "2026-01-01",
  settlement_date: null,
  quantity: 0.5,
  net_amount: 1000,
  fee: 1,
  account_id: "account-1",
  account_name: "Kraken",
  platform: "Kraken",
  operation_type: "buy",
  cash_flow_type: "none",
  symbol: "BTC",
  asset_name: "Bitcoin",
  unit_price: 2000,
  currency: "EUR",
  base_currency: "EUR",
  base_unit_price: 2000,
  base_net_amount: 1000,
  base_fee: 1,
  fx_rate_to_base: 1,
  fx_rate_date: "2026-01-01",
  fx_source: "identity",
  market: "",
  provider_operation_type: "Buy",
} satisfies CryptoOrder;

const baseProps: CryptoPositionsPanelProps = {
  positions: [position],
  pricedPositions: 1,
  selectedAccountLabel: "All accounts",
  baseCurrency: "EUR",
  allocationItems: [
    {
      key: "crypto-1",
      label: "Bitcoin",
      value: 1200,
      share: 1,
      color: "#7967f2",
    },
  ],
  allocationTotal: 1200,
  sortedPositions: [position],
  positionSortColumns: [
    { key: "asset", label: "Asset" },
    { key: "quantity", label: "Quantity" },
  ],
  positionSortKey: "value",
  positionSortDirection: "desc",
  selectedInstrumentId: "",
  selectedChartOrders: [order],
  averagePrice: 2000,
  chartPoints: [
    { date: "2026-01-01", open: 1900, high: 2100, low: 1800, close: 2000 },
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
  positionIdentity: () => "BTC",
  assetTicker: () => "BTC-EUR",
  marketValueSegmentAria: () => "Bitcoin 100%",
  positionAriaSort: (key) => (key === "value" ? "descending" : "none"),
  positionSortAria: (key) => `Sort ${key}`,
  detailId: (id) => `crypto-detail-${id}`,
};

describe("CryptoPositionsPanel", () => {
  beforeEach(() => {
    storage.clear();
    applyLocale("en");
  });

  it("owns collapse persistence and emits disclosure, add-asset, and sort events", async () => {
    const wrapper = mount(CryptoPositionsPanel, { props: baseProps });
    const collapse = wrapper.get(
      'button[aria-controls="crypto-positions-content"]',
    );

    expect(collapse.attributes("aria-expanded")).toBe("true");
    expect(wrapper.get(".fund-position-row").text()).toContain("Bitcoin");
    await collapse.trigger("click");
    expect(collapse.attributes("aria-expanded")).toBe("false");
    expect(localStorage.getItem("finanzr-crypto-positions-collapsed")).toBe(
      "true",
    );
    await wrapper.get(".fund-position-disclosure").trigger("click");
    await wrapper.get('button[aria-label="Add asset"]').trigger("click");
    await wrapper
      .get('.fund-sort-button[aria-label="Sort quantity"]')
      .trigger("click");
    expect(wrapper.emitted("toggle-position")).toEqual([["crypto-1"]]);
    expect(wrapper.emitted("add-asset")).toHaveLength(1);
    expect(wrapper.emitted("sort")).toEqual([["quantity"]]);
  });

  it("renders chart states and emits chart-range, retry, and edit events", async () => {
    const wrapper = mount(CryptoPositionsPanel, {
      props: { ...baseProps, selectedInstrumentId: "crypto-1" },
    });
    expect(wrapper.get('[data-testid="crypto-position-chart"]').text()).toBe(
      "1-1",
    );
    expect(
      wrapper
        .get('[data-testid="crypto-position-chart"]')
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
