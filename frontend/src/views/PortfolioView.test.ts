import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { applyLocale, registerMessages } from "../i18n";
import { viewMessagesA } from "../i18n/viewMessagesA";
import PortfolioView from "./PortfolioView.vue";

registerMessages(viewMessagesA);

vi.mock("../api/client", () => ({
  api: vi.fn(),
  json: (method: string, body: unknown) => ({
    method,
    body: JSON.stringify(body),
  }),
}));
vi.mock("../components/AllocationChart.vue", () => ({
  default: {
    props: ["items"],
    template:
      '<div data-testid="allocation-chart">{{ items.map((item) => item.label).join("|") }}</div>',
  },
}));

const apiMock = vi.mocked(api);
const response = {
  total: 5300,
  items: [
    {
      id: "fund:1:AAA",
      nombre: "Fondo global",
      identificador: "AAA",
      clase: "Renta Variable",
      subtipo: "Fondo indexado",
      cuenta: "Cartera Indexada",
      cuenta_id: "fund:1",
      plataforma: "MyInvestor",
      valor: 3000,
      peso: 3000 / 5300,
      origen: "fund",
    },
    {
      id: "stock:1:BBB",
      nombre: "NVIDIA",
      identificador: "BBB",
      clase: "Acciones y ETF",
      subtipo: "Acción o ETF",
      cuenta: "Trade Republic",
      cuenta_id: "stock:1",
      plataforma: "Trade Republic",
      valor: 1500,
      peso: 1500 / 5300,
      origen: "stock",
    },
    {
      id: "crypto:1:BTC",
      nombre: "Bitcoin",
      identificador: "BTC",
      clase: "Crypto",
      subtipo: "Criptomoneda",
      cuenta: "KrakenPro",
      cuenta_id: "crypto:1",
      plataforma: "KrakenPro",
      valor: 800,
      peso: 800 / 5300,
      origen: "crypto",
    },
  ],
};

describe("PortfolioView", () => {
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
      if (path === "/portfolio-analysis") return response;
      throw new Error(`Unexpected path: ${path}`);
    });
  });

  it("shows visualizations and reclassifies by account", async () => {
    const wrapper = mount(PortfolioView);
    await flushPromises();

    expect(wrapper.text()).toContain("Una cartera, cinco formas de leerla");
    expect(wrapper.text()).toContain("5300,00");
    expect(wrapper.findAll(".position-row")).toHaveLength(3);
    expect(wrapper.get('[data-testid="allocation-chart"]').text()).toContain(
      "Renta Variable",
    );
    const firstLegendRow = wrapper.findAll(".allocation-legend > div")[0];
    expect(firstLegendRow.get(".allocation-legend-share").text()).toContain(
      "%",
    );
    expect(firstLegendRow.get(".allocation-legend-value").text()).toContain(
      "€",
    );
    expect(firstLegendRow.get(".allocation-legend-value").text()).not.toContain(
      "%",
    );

    const accountButton = wrapper
      .findAll(".lens-control button")
      .find((button) => button.text().includes("Cuenta"));
    await accountButton!.trigger("click");

    expect(wrapper.get('[data-testid="allocation-chart"]').text()).toContain(
      "Cartera Indexada|Trade Republic|KrakenPro",
    );
  });

  it("combines search and type filters over the list", async () => {
    const wrapper = mount(PortfolioView);
    await flushPromises();

    await wrapper.get("select").setValue("crypto");
    expect(wrapper.findAll(".position-row")).toHaveLength(1);
    expect(wrapper.get(".position-row").text()).toContain("Bitcoin");

    await wrapper.get('input[type="search"]').setValue("ethereum");
    expect(wrapper.findAll(".position-row")).toHaveLength(0);
    expect(wrapper.text()).toContain("No hay posiciones con estos filtros");
  });

  it("renders English text and values", async () => {
    applyLocale("en");
    const wrapper = mount(PortfolioView);
    await flushPromises();

    expect(wrapper.text()).toContain("One portfolio, five ways to read it");
    expect(wrapper.text()).toContain("€5,300.00");
    expect(wrapper.get('input[type="search"]').attributes("aria-label")).toBe(
      "Search the portfolio",
    );
  });
});
