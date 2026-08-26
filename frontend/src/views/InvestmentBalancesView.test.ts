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
    id: 1,
    nombre: "Indexados",
    plataforma: "MyInvestor",
    tipo: "Fondos indexados",
  },
  {
    id: 2,
    nombre: "Gestionada",
    plataforma: "Finizens",
    tipo: "Cartera gestionada",
  },
];
const history = [
  { fecha: "2026-05-31", cuenta_id: 1, valor: 2000, aporte: 0, intereses: 40 },
  { fecha: "2026-05-31", cuenta_id: 2, valor: 3000, aporte: 0, intereses: -20 },
  {
    fecha: "2026-06-30",
    cuenta_id: 1,
    valor: 2500,
    aporte: 450,
    intereses: 50,
  },
  {
    fecha: "2026-06-30",
    cuenta_id: 2,
    valor: 3200,
    aporte: 250,
    intereses: -50,
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
    expect(payload).toMatchObject({ fecha: "2028-02-29", valor: 2800 });
    expect(payload).not.toHaveProperty("intereses");
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
