import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { applyLocale, registerMessages } from "../../i18n";
import { fundsMessages } from "../../i18n/fundsMessages";
import type { FundOrder, FundPosition } from "../../types/api";
import FundMovementsPanel, {
  type FundMovementsPanelProps,
} from "./FundMovementsPanel.vue";

registerMessages(fundsMessages);

const storage = new Map<string, string>();
vi.stubGlobal("localStorage", {
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
});

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

const positionOrders = Array.from({ length: 16 }, (_, index) => ({
  ...order,
  id: `order-${index}`,
  trade_date: `2026-01-${String((index % 9) + 1).padStart(2, "0")}`,
}));

const baseProps: FundMovementsPanelProps = {
  orders: positionOrders,
  positions: [position],
  selectedAccountLabel: "All accounts",
  accountKey: "all",
  formatMoney: (value) => `€${value}`,
  formatQuantity: (value) => String(value),
  displayDate: (value) => value,
  positionIdentity: () => "FUND-ISIN",
};

describe("FundMovementsPanel", () => {
  beforeEach(() => {
    storage.clear();
    applyLocale("en");
    if (!HTMLDialogElement.prototype.showModal) {
      HTMLDialogElement.prototype.showModal = function showModal() {
        this.setAttribute("open", "");
      };
    }
    if (!HTMLDialogElement.prototype.close) {
      HTMLDialogElement.prototype.close = function close() {
        this.removeAttribute("open");
      };
    }
  });

  it("owns filters, pagination, and collapse persistence", async () => {
    const wrapper = mount(FundMovementsPanel, { props: baseProps });
    expect(wrapper.findAll(".movement-table tbody tr")).toHaveLength(15);
    expect(wrapper.get(".movement-pagination").text()).toContain("Page 1 of 2");

    await wrapper
      .get(".movement-pagination button:last-child")
      .trigger("click");
    expect(wrapper.get(".movement-pagination").text()).toContain("Page 2 of 2");

    await wrapper
      .get('select[aria-label="Filter by fund"]')
      .setValue("missing-fund");
    expect(wrapper.get(".fund-empty-compact").text()).toContain(
      "No transactions",
    );

    const collapse = wrapper.get(
      'button[aria-controls="fund-movements-content"]',
    );
    await collapse.trigger("click");
    expect(collapse.attributes("aria-expanded")).toBe("false");
    expect(localStorage.getItem("finanzr-funds-movements-collapsed")).toBe(
      "true",
    );
  });

  it("keeps date drafts local and emits CRUD actions with the original order", async () => {
    const wrapper = mount(FundMovementsPanel, {
      props: { ...baseProps, orders: [order] },
    });

    await wrapper.get(".add-movement").trigger("click");
    await wrapper.get(".investment-movement-action--edit").trigger("click");
    await wrapper.get(".investment-movement-action--delete").trigger("click");
    expect(wrapper.emitted("add")).toHaveLength(1);
    expect(wrapper.emitted("edit")?.[0]).toEqual([order]);
    expect(wrapper.emitted("delete")?.[0]).toEqual([order]);

    await wrapper.get(".movement-filters > button:last-child").trigger("click");
    const dialog = wrapper.get(
      'dialog[aria-labelledby="movement-calendar-title"]',
    );
    expect(
      wrapper
        .find('dialog[aria-labelledby="movement-calendar-title"]')
        .exists(),
    ).toBe(true);
    const dates = dialog.findAll('input[type="date"]');
    await dates[0].setValue("2026-01-01");
    await dates[1].setValue("2026-01-01");
    await dialog.get("form").trigger("submit");
    expect(
      wrapper.get(".movement-filters > button:last-child").text(),
    ).toContain("2026-01-01");
  });
});
