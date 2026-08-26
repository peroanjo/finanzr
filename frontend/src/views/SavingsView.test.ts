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
  { id: 1, nombre: "Principal", banco: "Abanca", tipo: "Cuenta corriente" },
  {
    id: 2,
    nombre: "Remunerada",
    banco: "Trade Republic",
    tipo: "Cuenta remunerada",
  },
];
const history = [
  { fecha: "2026-05-31", cuenta_id: 1, saldo: 2000, aporte: 0, intereses: 0 },
  { fecha: "2026-05-31", cuenta_id: 2, saldo: 3000, aporte: 0, intereses: 5 },
  { fecha: "2026-06-30", cuenta_id: 1, saldo: 2500, aporte: 500, intereses: 0 },
  { fecha: "2026-06-30", cuenta_id: 2, saldo: 3200, aporte: 195, intereses: 5 },
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
      .setValue("2");
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
      fecha: "2026-06-30",
      saldo: 2750,
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
