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
vi.mock("../components/MonthlyVariationChart.vue", () => ({
  default: {
    props: ["labels", "series", "values", "selectedIndex"],
    template:
      '<div data-testid="savings-interest">{{ labels.length }}-{{ series.length }} · {{ values.join(",") }} · {{ selectedIndex }}</div>',
  },
}));

vi.mock("../components/LineChart.vue", () => ({
  default: {
    props: ["labels", "values", "series"],
    template: '<div data-testid="savings-trend">{{ values.join(",") }}</div>',
  },
}));

const apiMock = vi.mocked(api);
const accounts = [
  {
    id: "00000000-0000-0000-0000-000000000001",
    name: "Principal",
    bank: "Abanca",
    type: "Cuenta no remunerada",
    currency: "EUR",
    workspace_id: "20000000-0000-0000-0000-000000000001",
    workspace_name: "Titular A",
  },
  {
    id: "00000000-0000-0000-0000-000000000002",
    name: "Remunerada",
    bank: "Trade Republic",
    type: "Cuenta remunerada",
    currency: "EUR",
    workspace_id: "20000000-0000-0000-0000-000000000002",
    workspace_name: "Titular B",
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
    applyLocale("es-ES");
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

    expect(wrapper.text()).toContain("Saldo total registrado");
    expect(wrapper.get(".cash-total").text()).toContain("5700,00");
    expect(wrapper.get(".savings-kpis").text()).toContain("3200,00");
    expect(wrapper.get(".savings-kpis").text()).toContain("+10,00");
    const accountCards = wrapper.findAll(".cash-account");
    expect(accountCards).toHaveLength(2);
    expect(accountCards[0].get(".account-owner").text()).toBe("Titular A");
    expect(accountCards[1].get(".account-owner").text()).toBe("Titular B");
    expect(accountCards[0].get(".account-owner").attributes("style")).not.toBe(
      accountCards[1].get(".account-owner").attributes("style"),
    );
    expect(accountCards[0].get(".account-column-interest").text()).toContain(
      "No remunerada",
    );
    expect(accountCards[1].get(".account-interest-bearing").text()).toBe(
      "Remunerada",
    );
    expect(wrapper.get('[data-testid="savings-trend"]').text()).toBe(
      "5000,5700",
    );
    expect(wrapper.get('[data-testid="savings-interest"]').text()).toBe(
      "2-1 · 5,5 · 1",
    );
  });

  it("sorts each data column in both directions and keeps unrecorded balances last", async () => {
    const missing = {
      ...accounts[0],
      id: "00000000-0000-0000-0000-000000000003",
      name: "Sin saldo",
      workspace_name: "Titular C",
    };
    apiMock.mockImplementation(async (path) => {
      if (path === "/savings/accounts")
        return [accounts[1], missing, accounts[0]];
      if (path === "/savings/history") return history;
      throw new Error(`Unexpected path: ${path}`);
    });
    const wrapper = mount(SavingsView);
    await flushPromises();
    const names = () =>
      wrapper.findAll(".account-identity strong").map((name) => name.text());
    const sort = async (key: string, direction: string, expected: string[]) => {
      const header = wrapper.get(`.account-columns .account-column-${key}`);
      await header.get("button").trigger("click");
      expect(header.attributes("aria-sort")).toBe(direction);
      expect(wrapper.findAll("[aria-sort]")).toHaveLength(1);
      expect(names()).toEqual(expected);
    };

    expect(names()).toEqual(["Principal", "Remunerada", "Sin saldo"]);
    await sort("name", "descending", ["Sin saldo", "Remunerada", "Principal"]);
    await sort("name", "ascending", ["Principal", "Remunerada", "Sin saldo"]);
    await sort("owner", "ascending", ["Principal", "Remunerada", "Sin saldo"]);
    await sort("owner", "descending", ["Sin saldo", "Remunerada", "Principal"]);
    await sort("interest", "ascending", [
      "Principal",
      "Sin saldo",
      "Remunerada",
    ]);
    await sort("interest", "descending", [
      "Remunerada",
      "Principal",
      "Sin saldo",
    ]);
    await sort("balance", "descending", [
      "Remunerada",
      "Principal",
      "Sin saldo",
    ]);
    await sort("balance", "ascending", [
      "Principal",
      "Remunerada",
      "Sin saldo",
    ]);
  });

  it("toggles each interest series and keeps the legend available when all are hidden", async () => {
    apiMock.mockImplementation(async (path) => {
      if (path === "/savings/accounts") return accounts;
      if (path === "/savings/history") {
        return [{ ...history[0], interest: 2 }, ...history.slice(1)];
      }
      throw new Error(`Unexpected path: ${path}`);
    });
    const wrapper = mount(SavingsView);
    await flushPromises();
    const panel = wrapper.get(".interest-panel");
    const chart = '[data-testid="savings-interest"]';
    const [first, second] = panel.findAll(".interest-legend button");

    expect(panel.get(chart).text()).toBe("2-2 · 7,5 · 1");
    expect(first.attributes("aria-pressed")).toBe("true");
    expect(second.attributes("aria-pressed")).toBe("true");

    await first.trigger("click");
    expect(first.attributes("aria-pressed")).toBe("false");
    expect(panel.get(chart).text()).toBe("2-1 · 5,5 · 1");
    expect(panel.get("header > span").text()).toContain("10,00");
    expect(wrapper.get(".savings-kpis").text()).toContain("+12,00");

    await second.trigger("click");
    expect(second.attributes("aria-pressed")).toBe("false");
    expect(panel.find(chart).exists()).toBe(false);
    expect(panel.text()).toContain("Activa un elemento de la leyenda");

    await first.trigger("click");
    expect(first.attributes("aria-pressed")).toBe("true");
    expect(panel.get(chart).text()).toBe("2-1 · 2,0 · 1");
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
      .find((button) => button.text().includes("Registrar saldo"));
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
      .find((button) => button.text().includes("Registrar saldo"));
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

  it("expands account history and opens the correct balance form", async () => {
    const wrapper = mount(SavingsView);
    await flushPromises();
    const row = wrapper.findAll(".cash-account")[1];
    await row.get(".account-identity").trigger("click");
    expect(row.get(".account-identity").attributes("aria-expanded")).toBe(
      "true",
    );
    expect(row.findAll(".account-detail-history button")).toHaveLength(2);
    await row.get(".update-balance").trigger("click");
    expect(
      (wrapper.get(".savings-dialog[open] select").element as HTMLSelectElement)
        .value,
    ).toBe(accounts[1].id);
    await row.get(".account-identity").trigger("click");
    expect(row.find(".account-detail").exists()).toBe(false);
  });

  it("updates period interest and comparison without changing current balances", async () => {
    const older = history.map((entry) => ({
      ...entry,
      date: "2025-01-31",
      balance: 100,
      interest: 50,
    }));
    apiMock.mockImplementation(async (path) =>
      path === "/savings/accounts"
        ? accounts
        : [...older.slice(0, 2), ...history],
    );
    const wrapper = mount(SavingsView);
    await flushPromises();
    await wrapper.findAll(".range-control button")[3].trigger("click");
    expect(wrapper.get(".savings-kpis").text()).toContain("+110,00");
    expect(wrapper.get(".savings-delta").text()).toContain("5500,00");
    expect(wrapper.get(".savings-delta").text()).toContain("2750");
    await wrapper.findAll(".range-control button")[0].trigger("click");
    expect(wrapper.get(".cash-total").text()).toContain("5700,00");
    expect(wrapper.get(".savings-kpis").text()).toContain("+10,00");
    expect(wrapper.get(".savings-delta").text()).toContain("700,00");
    expect(
      wrapper.get(".range-control button").attributes("aria-pressed"),
    ).toBe("true");
  });

  it("does not show a percentage for a zero starting balance", async () => {
    apiMock.mockImplementation(async (path) =>
      path === "/savings/accounts"
        ? accounts
        : history.map((entry) =>
            entry.date === "2026-05-31" ? { ...entry, balance: 0 } : entry,
          ),
    );
    const wrapper = mount(SavingsView);
    await flushPromises();
    expect(wrapper.get(".savings-delta").text()).toContain("5700,00");
    expect(wrapper.get(".savings-delta").text()).not.toContain("%");
  });

  it("guides empty accounts and avoids a fabricated change with one month", async () => {
    apiMock.mockResolvedValue([]);
    const empty = mount(SavingsView);
    await flushPromises();
    expect(empty.get(".empty-accounts").text()).toContain(
      "Crea tu primera cuenta",
    );
    expect(
      empty.get(".hero-actions .primary").attributes("disabled"),
    ).toBeDefined();
    apiMock.mockImplementation(async (path) =>
      path === "/savings/accounts" ? accounts : history.slice(0, 2),
    );
    const single = mount(SavingsView);
    await flushPromises();
    expect(single.get(".savings-delta").text()).toContain(
      "Registra al menos dos meses",
    );
    expect(single.get(".savings-delta").text()).not.toContain("%");
  });

  it("renders the view in English", async () => {
    applyLocale("en");
    const wrapper = mount(SavingsView);
    await flushPromises();

    expect(wrapper.text()).toContain("Total recorded balance");
    expect(wrapper.get(".cash-total").text()).toContain("€5,700.00");
    expect(wrapper.get(".history-panel select").attributes("aria-label")).toBe(
      "Filter history by account",
    );
  });
});
