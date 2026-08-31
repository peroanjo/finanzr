import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { applyLocale, registerMessages } from "../i18n";
import { viewMessagesA } from "../i18n/viewMessagesA";
import SavingsView from "./SavingsView.vue";

registerMessages(viewMessagesA);

vi.mock("../api/client", () => ({
  api: vi.fn(),
  json: (method: string, body: unknown) => ({
    method,
    body: JSON.stringify(body),
  }),
}));
vi.mock("../components/AccountSnapshotChart.vue", () => ({
  default: {
    props: ["labels", "series", "mode"],
    template:
      '<div :data-testid="`savings-${mode}`">{{ labels.length }}-{{ series.length }}</div>',
  },
}));

const apiMock = vi.mocked(api);
const accounts = [
  {
    id: "00000000-0000-0000-0000-000000000001",
    name: "Principal",
    bank: "Abanca",
    type: "Cuenta corriente",
    currency: "EUR",
  },
  {
    id: "00000000-0000-0000-0000-000000000002",
    name: "Remunerada",
    bank: "Trade Republic",
    type: "Cuenta remunerada",
    currency: "EUR",
  },
];
const history = [
  {
    id: "10000000-0000-0000-0000-000000000001",
    account_id: accounts[0].id,
    date: "2026-05-31",
    balance: 2000,
    balance_original: 2000,
    contribution: 0,
    contribution_original: 0,
    interest: 0,
    interest_original: 0,
    currency: "EUR",
    base_currency: "EUR",
    exchange_rate: 1,
    exchange_rate_date: "2026-05-31",
    exchange_rate_source: "identity",
  },
  {
    id: "10000000-0000-0000-0000-000000000002",
    account_id: accounts[1].id,
    date: "2026-05-31",
    balance: 3000,
    balance_original: 3000,
    contribution: 0,
    contribution_original: 0,
    interest: 5,
    interest_original: 5,
    currency: "EUR",
    base_currency: "EUR",
    exchange_rate: 1,
    exchange_rate_date: "2026-05-31",
    exchange_rate_source: "identity",
  },
  {
    id: "10000000-0000-0000-0000-000000000003",
    account_id: accounts[0].id,
    date: "2026-06-30",
    balance: 2500,
    balance_original: 2500,
    contribution: 500,
    contribution_original: 500,
    interest: 0,
    interest_original: 0,
    currency: "EUR",
    base_currency: "EUR",
    exchange_rate: 1,
    exchange_rate_date: "2026-06-30",
    exchange_rate_source: "identity",
  },
  {
    id: "10000000-0000-0000-0000-000000000004",
    account_id: accounts[1].id,
    date: "2026-06-30",
    balance: 3200,
    balance_original: 3200,
    contribution: 195,
    contribution_original: 195,
    interest: 5,
    interest_original: 5,
    currency: "EUR",
    base_currency: "EUR",
    exchange_rate: 1,
    exchange_rate_date: "2026-06-30",
    exchange_rate_source: "identity",
  },
];

describe("SavingsView", () => {
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
    apiMock.mockImplementation(async (path) => {
      if (path === "/savings/accounts") return accounts;
      if (path === "/savings/history") return history;
      throw new Error(`Unexpected path: ${path}`);
    });
  });

  it("summarizes liquidity, interest, and account evolution", async () => {
    const wrapper = mount(SavingsView);
    await flushPromises();

    expect(wrapper.text()).toContain("Tu efectivo, cuenta a cuenta");
    expect(wrapper.get(".cash-total").text()).toContain("5700,00");
    expect(wrapper.get(".savings-kpis").text()).toContain("3200,00");
    expect(wrapper.get(".savings-kpis").text()).toContain("+10,00");
    expect(wrapper.findAll(".cash-account")).toHaveLength(2);
    expect(wrapper.get('[data-testid="savings-balance"]').text()).toBe("2-2");
    expect(wrapper.get('[data-testid="savings-interest"]').text()).toBe("2-1");
  });

  it("filters history and opens a monthly close", async () => {
    const wrapper = mount(SavingsView);
    await flushPromises();

    await wrapper
      .get('select[aria-label="Filtrar histórico por cuenta"]')
      .setValue(accounts[1].id);
    expect(wrapper.findAll(".history-list > button")).toHaveLength(2);
    expect(wrapper.get(".history-list").text()).toContain("Remunerada");
    expect(wrapper.get(".history-list").text()).not.toContain("Principal");

    const newClose = wrapper
      .findAll(".hero-actions button")
      .find((button) => button.text().includes("Cierre mensual"));
    await newClose!.trigger("click");
    expect(wrapper.get(".savings-dialog[open]").text()).toContain(
      "Nuevo cierre mensual",
    );
  });

  it("saves monthly closes on the last calendar day", async () => {
    const wrapper = mount(SavingsView);
    await flushPromises();

    const newClose = wrapper
      .findAll(".hero-actions button")
      .find((button) => button.text().includes("Cierre mensual"));
    await newClose!.trigger("click");
    await wrapper
      .get('.savings-dialog[open] input[type="month"]')
      .setValue("2026-06");
    await wrapper
      .get('.savings-dialog[open] input[required][type="number"]')
      .setValue("2750");
    await wrapper.get(".savings-dialog[open] form").trigger("submit");
    await flushPromises();

    const saveCall = apiMock.mock.calls.find(
      ([path, init]) => path === "/savings/history" && init?.method === "POST",
    );
    expect(saveCall).toBeDefined();
    expect(JSON.parse(String(saveCall?.[1]?.body))).toMatchObject({
      date: "2026-06-30",
      account_id: accounts[0].id,
      balance: 2750,
    });
  });

  it("renders the view in English", async () => {
    applyLocale("en");
    const wrapper = mount(SavingsView);
    await flushPromises();

    expect(wrapper.text()).toContain("Your cash, account by account");
    expect(wrapper.get(".cash-total").text()).toContain("€5,700.00");
    expect(wrapper.get(".history-panel select").attributes("aria-label")).toBe(
      "Filter history by account",
    );
  });
});
