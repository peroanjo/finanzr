import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { applyLocale, registerMessages } from "../../i18n";
import { stocksMessages } from "../../i18n/stocksMessages";
import type { StockOrder, StockPosition } from "../../types/api";
import StockMovementsPanel, {
  type StockMovementsPanelProps,
} from "./StockMovementsPanel.vue";

registerMessages(stocksMessages);

const storage = new Map<string, string>();
vi.stubGlobal("localStorage", {
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
});

const position: StockPosition = {
  instrument_id: "stock-1",
  kind: "stock",
  name: "NVIDIA",
  quantity: 1,
  cost: 100,
  current_price: 125,
  current_value: 125,
  unrealized_pnl: 25,
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
  quantity: 1,
  unit_price: 100,
  net_amount: 100,
  fee: 1,
  currency: "EUR",
  base_currency: "EUR",
  base_unit_price: 100,
  base_net_amount: 100,
  base_fee: 1,
  fx_rate_to_base: 1,
  fx_rate_date: "2026-01-01",
  fx_source: "identity",
  market: "",
  provider_operation_type: "Buy",
  isin: "US-ISIN",
  is_saveback: true,
};

const orders = Array.from({ length: 16 }, (_, index) => ({
  ...order,
  id: `order-${index}`,
  trade_date: `2026-01-${String((index % 9) + 1).padStart(2, "0")}`,
  is_saveback: index === 0,
}));

const baseProps: StockMovementsPanelProps = {
  orders,
  positions: [position],
  selectedAccountLabel: "All accounts",
  accountKey: "all",
  baseCurrency: "EUR",
  formatMoney: (value) => `€${value}`,
  formatQuantity: (value) => String(value),
  displayDate: (value) => value,
  positionIdentity: () => "US-ISIN",
};

describe("StockMovementsPanel", () => {
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
    const wrapper = mount(StockMovementsPanel, { props: baseProps });
    expect(wrapper.findAll(".movement-table tbody tr")).toHaveLength(15);
    expect(wrapper.get(".movement-pagination").text()).toContain("Page 1 of 2");

    await wrapper
      .get(".movement-pagination button:last-child")
      .trigger("click");
    expect(wrapper.get(".movement-pagination").text()).toContain("Page 2 of 2");

    await wrapper
      .get('select[aria-label="Filter transactions by asset"]')
      .setValue("missing-asset");
    expect(wrapper.get(".fund-empty-compact").text()).toContain(
      "No transactions",
    );

    const collapse = wrapper.get(
      'button[aria-controls="stock-movements-content"]',
    );
    await collapse.trigger("click");
    expect(collapse.attributes("aria-expanded")).toBe("false");
    expect(localStorage.getItem("finanzr-stocks-movements-collapsed")).toBe(
      "true",
    );
  });

  it("keeps date drafts local and emits CRUD actions with the original order", async () => {
    const wrapper = mount(StockMovementsPanel, {
      props: { ...baseProps, orders: [order] },
    });

    await wrapper.get(".add-movement").trigger("click");
    await wrapper.get(".investment-movement-action--edit").trigger("click");
    await wrapper.get(".investment-movement-action--delete").trigger("click");
    expect(wrapper.emitted("add")).toHaveLength(1);
    expect(wrapper.emitted("edit")?.[0]).toEqual([order]);
    expect(wrapper.emitted("delete")?.[0]).toEqual([order]);

    await wrapper
      .get('.movement-filters button[aria-label="Filter transactions by date"]')
      .trigger("click");
    const dialog = wrapper.get(
      'dialog[aria-labelledby="stocks-movement-calendar-title"]',
    );
    const dates = dialog.findAll('input[type="date"]');
    await dates[0].setValue("2026-01-01");
    await dates[1].setValue("2026-01-01");
    await dialog.get("form").trigger("submit");
    expect(
      wrapper
        .get(
          '.movement-filters button[aria-label="Filter transactions by date"]',
        )
        .text(),
    ).toContain("2026-01-01");
    expect(wrapper.get(".operation-pill").text()).toContain("Cashback");
  });

  it("renders original currency values against the reporting currency", () => {
    const foreignOrder = {
      ...order,
      currency: "GBP",
      base_unit_price: 80,
      base_net_amount: 80,
      base_fee: 0.8,
    };
    const wrapper = mount(StockMovementsPanel, {
      props: { ...baseProps, orders: [foreignOrder] },
    });

    expect(wrapper.get(".movement-table").text()).toContain("£100.00");
    expect(wrapper.get(".movement-table").text()).toContain("€80");
  });
});
