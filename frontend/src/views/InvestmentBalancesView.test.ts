import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { applyLocale, registerMessages } from "../i18n";
import { viewMessagesA } from "../i18n/viewMessagesA";
import InvestmentBalancesView from "./InvestmentBalancesView.vue";

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
      '<div :data-testid="`account-${mode}`">{{ labels.length }}-{{ series.length }}</div>',
  },
}));

const apiMock = vi.mocked(api);
const accounts = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    name: "Indexados",
    platform: "MyInvestor",
    type: "Fondos indexados",
    currency: "EUR",
  },
  {
    id: "22222222-2222-2222-2222-222222222222",
    name: "Gestionada",
    platform: "Finizens",
    type: "Cartera gestionada",
    currency: "EUR",
  },
];
const history = [
  {
    id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    account_id: "11111111-1111-1111-1111-111111111111",
    date: "2026-05-31",
    value: 2000,
    value_original: 2000,
    contribution: 0,
    contribution_original: 0,
    interest: 40,
    interest_original: 40,
    currency: "EUR",
    base_currency: "EUR",
    exchange_rate: 1,
    exchange_rate_date: "2026-05-31",
    exchange_rate_source: "identity",
  },
  {
    id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    account_id: "22222222-2222-2222-2222-222222222222",
    date: "2026-05-31",
    value: 3000,
    value_original: 3000,
    contribution: 0,
    contribution_original: 0,
    interest: -20,
    interest_original: -20,
    currency: "EUR",
    base_currency: "EUR",
    exchange_rate: 1,
    exchange_rate_date: "2026-05-31",
    exchange_rate_source: "identity",
  },
  {
    id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
    account_id: "11111111-1111-1111-1111-111111111111",
    date: "2026-06-30",
    value: 2500,
    value_original: 2500,
    contribution: 450,
    contribution_original: 450,
    interest: 50,
    interest_original: 50,
    currency: "EUR",
    base_currency: "EUR",
    exchange_rate: 1,
    exchange_rate_date: "2026-06-30",
    exchange_rate_source: "identity",
  },
  {
    id: "dddddddd-dddd-dddd-dddd-dddddddddddd",
    account_id: "22222222-2222-2222-2222-222222222222",
    date: "2026-06-30",
    value: 3200,
    value_original: 3200,
    contribution: 250,
    contribution_original: 250,
    interest: -50,
    interest_original: -50,
    currency: "EUR",
    base_currency: "EUR",
    exchange_rate: 1,
    exchange_rate_date: "2026-06-30",
    exchange_rate_source: "identity",
  },
];

describe("InvestmentBalancesView", () => {
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
    apiMock.mockReset();
    apiMock.mockImplementation(async (path) => {
      if (path === "/investments/accounts") return accounts;
      if (path === "/investments/history") return history;
      throw new Error(`Unexpected path: ${path}`);
    });
  });

  it("summarizes balances, contributions, and returns by platform", async () => {
    const wrapper = mount(InvestmentBalancesView);
    await flushPromises();

    expect(wrapper.text()).toContain("Una cifra por plataforma");
    expect(wrapper.get(".value-block").text()).toContain("5700,00");
    expect(wrapper.get(".closing-line").text()).toContain("+700,00");
    expect(wrapper.findAll(".platform-card")).toHaveLength(2);
    expect(wrapper.get('[data-testid="account-balance"]').text()).toBe("2-2");
    expect(wrapper.get('[data-testid="account-pnl"]').text()).toBe("2-2");
  });

  it("saves the month-end close and lets Django calculate P&L", async () => {
    const wrapper = mount(InvestmentBalancesView);
    await flushPromises();

    const newClose = wrapper
      .findAll(".hero-actions button")
      .find((button) => button.text().includes("Registrar cierre"));
    await newClose!.trigger("click");
    await wrapper
      .get('.balances-dialog[open] input[type="month"]')
      .setValue("2028-02");
    await wrapper
      .get('.balances-dialog[open] input[required][type="number"]')
      .setValue("2800");
    await wrapper.get(".balances-dialog[open] form").trigger("submit");
    await flushPromises();

    const saveCall = apiMock.mock.calls.find(
      ([path, init]) =>
        path === "/investments/history" && init?.method === "POST",
    );
    const payload = JSON.parse(String(saveCall?.[1]?.body));
    expect(payload).toMatchObject({
      date: "2028-02-29",
      account_id: accounts[0].id,
      value: 2800,
    });
    expect(payload).not.toHaveProperty("interest");
  });

  it("renders the view in English", async () => {
    applyLocale("en");
    const wrapper = mount(InvestmentBalancesView);
    await flushPromises();

    expect(wrapper.text()).toContain("One figure per platform");
    expect(wrapper.get(".value-block").text()).toContain("€5,700.00");
    expect(wrapper.get(".history-panel select").attributes("aria-label")).toBe(
      "Filter closes by account",
    );
  });
});
