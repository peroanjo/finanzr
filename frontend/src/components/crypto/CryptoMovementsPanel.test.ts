import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { applyLocale, registerMessages } from "../../i18n";
import { cryptoMessages } from "../../i18n/cryptoMessages";
import type { CryptoInstrument, CryptoOrder } from "../../types/api";
import CryptoMovementsPanel, {
  type CryptoMovementsPanelProps,
} from "./CryptoMovementsPanel.vue";

registerMessages(cryptoMessages);

const storage = new Map<string, string>();
vi.stubGlobal("localStorage", {
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
});

const instrument: CryptoInstrument = {
  id: "crypto-1",
  kind: "crypto",
  name: "Bitcoin",
  quote_currency: "EUR",
  identifiers: [
    {
      scheme: "crypto_symbol",
      value: "BTC",
      venue: "",
      is_primary: true,
    },
  ],
  asset_class: null,
  subtype: null,
  is_active: true,
};

const order: CryptoOrder = {
  id: "order-1",
  trade_date: "2026-01-01",
  settlement_date: null,
  quantity: 1,
  net_amount: 100,
  fee: 1,
  account_id: "account-1",
  account_name: "Kraken",
  platform: "Kraken",
  operation_type: "buy",
  cash_flow_type: "none",
  symbol: "BTC",
  asset_name: "Bitcoin",
  unit_price: 100,
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
};

const orders = Array.from({ length: 16 }, (_, index) => ({
  ...order,
  id: "order-" + index,
  trade_date: "2026-01-" + String((index % 9) + 1).padStart(2, "0"),
}));

const baseProps: CryptoMovementsPanelProps = {
  orders,
  instruments: [instrument],
  selectedAccountLabel: "All accounts",
  baseCurrency: "EUR",
  formatMoney: (value) => "€" + value,
  formatQuantity: (value) => String(value),
  displayDate: (value) => value,
  basePrice: (item) => item.base_unit_price ?? item.unit_price,
  baseAmount: (item) => item.base_net_amount ?? item.net_amount,
  baseFee: (item) => item.base_fee ?? item.fee,
};

describe("CryptoMovementsPanel", () => {
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

  it("owns filters, pagination, date drafts, and collapse persistence", async () => {
    const wrapper = mount(CryptoMovementsPanel, { props: baseProps });
    expect(wrapper.findAll(".movement-table tbody tr")).toHaveLength(15);
    expect(wrapper.get(".movement-pagination").text()).toContain("Page 1 of 2");
    await wrapper
      .get(".movement-pagination button:last-child")
      .trigger("click");
    expect(wrapper.get(".movement-pagination").text()).toContain("Page 2 of 2");

    await wrapper
      .get('select[aria-label="Filter transactions by currency"]')
      .setValue("missing");
    expect(wrapper.get(".fund-empty-compact").text()).toContain(
      "No transactions",
    );

    const collapse = wrapper.get(
      'button[aria-controls="crypto-movements-content"]',
    );
    await collapse.trigger("click");
    expect(collapse.attributes("aria-expanded")).toBe("false");
    expect(localStorage.getItem("finanzr-crypto-movements-collapsed")).toBe(
      "true",
    );
  });

  it("keeps date drafts local and emits CRUD actions", async () => {
    const wrapper = mount(CryptoMovementsPanel, {
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
      'dialog[aria-labelledby="movement-calendar-title"]',
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
  });

  it("renders original currency values against the reporting currency", () => {
    const foreignOrder = {
      ...order,
      currency: "GBP",
      base_unit_price: 80,
      base_net_amount: 80,
      base_fee: 0.8,
    };
    const wrapper = mount(CryptoMovementsPanel, {
      props: { ...baseProps, orders: [foreignOrder] },
    });
    expect(wrapper.get(".movement-table").text()).toContain("£100.00");
    expect(wrapper.get(".movement-table").text()).toContain("€80");
  });
});
