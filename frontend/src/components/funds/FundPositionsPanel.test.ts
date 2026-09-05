import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { applyLocale, registerMessages } from "../../i18n";
import { fundsMessages } from "../../i18n/fundsMessages";
import type { FundOrder, FundPosition } from "../../types/api";
import FundPositionsPanel, {
  type FundPositionsPanelProps,
} from "./FundPositionsPanel.vue";

registerMessages(fundsMessages);

const storage = new Map<string, string>();
vi.stubGlobal("localStorage", {
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
});

vi.mock("../../components/FundPriceChart.vue", () => ({
  default: {
    name: "FundPriceChart",
    props: ["points", "orders", "averagePrice"],
    template:
      '<div data-testid="fund-price-chart">{{ points.length }}-{{ orders.length }}</div>',
  },
}));

const position: FundPosition = {
  instrument_id: "fund-1",
  kind: "fund",
  name: "Global fund",
  asset_class: "Equity",
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
};

const order = {
  id: "order-1",
  account_id: "account-1",
  account_name: "Account",
  platform: "Broker",
  asset_name: "Global fund",
  trade_date: "2026-01-01",
  settlement_date: null,
  operation_type: "buy" as const,
  cash_flow_type: "contribution" as const,
  quantity: 10,
  unit_price: 100,
  net_amount: 1000,
  fee: 0,
  currency: "EUR",
  base_currency: "EUR",
  base_unit_price: 100,
  base_net_amount: 1000,
  base_fee: 0,
  fx_rate_to_base: 1,
  fx_rate_date: "2026-01-01",
  fx_source: "identity",
  market: "",
  provider_operation_type: "",
  isin: "FUND-ISIN",
} satisfies FundOrder;

const baseProps: FundPositionsPanelProps = {
  positions: [position],
  pricedPositions: 1,
  priceMessage: "",
  selectedAccountLabel: "All accounts",
  allocationItems: [
    {
      key: "fund-1",
      label: "Global fund",
      value: 1200,
      share: 1,
      color: "#3ddc97",
    },
  ],
  allocationTotal: 1200,
  sortedPositions: [position],
  positionSortColumns: [
    { key: "fund", label: "Fund" },
    { key: "value", label: "Value" },
  ],
  positionSortKey: "value",
  positionSortDirection: "desc",
  selectedFund: "",
  selectedFundPosition: null,
  selectedFundOrders: [order],
  fundChartPoints: [{ date: "2026-01-01", price: 100 }],
  fundChartLoading: false,
  fundChartError: "",
  fundChartRangeLabel: "1 year",
  ranges: [{ key: "1y", label: "1Y" }],
  fundRange: "1y",
  formatMoney: (value) => `€${value}`,
  formatPercentage: (value) => `${value * 100}%`,
  formatQuantity: (value) => String(value),
  formatSignedMoney: (value) => `+€${value}`,
  positionIdentity: () => "FUND-ISIN",
  marketValueSegmentAria: () => "Global fund 100%",
  positionAriaSort: (key) => (key === "value" ? "descending" : "none"),
  positionSortAria: (key) => `Sort ${key}`,
  fundDetailId: (id) => `fund-detail-${id}`,
};

describe("FundPositionsPanel", () => {
  beforeEach(() => {
    localStorage.clear();
    applyLocale("en");
  });

  it("owns collapse persistence and preserves table disclosure controls", async () => {
    const wrapper = mount(FundPositionsPanel, { props: baseProps });
    const collapse = wrapper.get(
      'button[aria-controls="fund-positions-content"]',
    );

    expect(collapse.attributes("aria-expanded")).toBe("true");
    expect(wrapper.get(".fund-position-row").text()).toContain("Global fund");

    await collapse.trigger("click");
    expect(collapse.attributes("aria-expanded")).toBe("false");
    expect(localStorage.getItem("finanzr-funds-positions-collapsed")).toBe(
      "true",
    );
    expect(wrapper.get("#fund-positions-content").isVisible()).toBe(false);

    const disclosure = wrapper.get(".fund-position-disclosure");
    await disclosure.trigger("click");
    expect(wrapper.emitted("toggle-fund")).toEqual([["fund-1"]]);
    await wrapper
      .get('.fund-sort-button[data-sort-key="value"]')
      .trigger("click");
    expect(wrapper.emitted("sort")).toEqual([["value"]]);
  });

  it("renders chart states and emits range, retry, and edit events", async () => {
    const wrapper = mount(FundPositionsPanel, {
      props: {
        ...baseProps,
        selectedFund: "fund-1",
        selectedFundPosition: position,
      },
    });
    expect(wrapper.get('[data-testid="fund-price-chart"]').text()).toBe("1-1");

    await wrapper.get(".fund-range-control button").trigger("click");
    await wrapper.get(".fund-edit-icon-button").trigger("click");
    expect(wrapper.emitted("select-range")).toEqual([["1y"]]);
    expect(wrapper.emitted("edit-fund")?.[0]).toEqual([position]);

    await wrapper.setProps({
      fundChartPoints: [],
      fundChartError: "Unavailable",
    });
    expect(wrapper.get(".fund-chart-state.error-state").text()).toContain(
      "Unavailable",
    );
    await wrapper.get(".fund-chart-state button").trigger("click");
    expect(wrapper.emitted("retry-chart")).toHaveLength(1);
  });
});
