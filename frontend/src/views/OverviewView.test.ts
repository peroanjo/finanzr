import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { applyLocale, registerMessages } from "../i18n";
import { viewMessagesA } from "../i18n/viewMessagesA";

registerMessages(viewMessagesA);

const { fetchMock } = vi.hoisted(() => ({ fetchMock: vi.fn() }));
vi.stubGlobal("fetch", fetchMock);
const chartStubs = {
  AllocationChart: {
    props: ["items"],
    template: '<div data-testid="allocation-chart">{{ items.length }}</div>',
  },
  LineChart: {
    name: "LineChart",
    props: ["labels", "values", "series", "totalLabel", "ariaLabel"],
    template:
      '<div data-testid="line-chart" :data-series="series?.length ?? 0">{{ values.length }}</div>',
  },
  MonthlyVariationChart: {
    name: "MonthlyVariationChart",
    props: ["labels", "values", "label", "selectedIndex"],
    emits: ["select"],
    template:
      '<button data-testid="monthly-variation-chart" @click="$emit(\'select\', 0)">{{ values.join(",") }}</button>',
  },
};

const history = Array.from({ length: 30 }, (_, index) => {
  const date = new Date(2025, index, 1);
  return {
    fecha: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`,
    ahorro: 600 + index * 60,
    ahorro_intereses: 10,
    balances: 400 + index * 40,
    balance_aportes: 30,
    inversiones: 400 + index * 40,
    total: 1000 + index * 100,
    inv_aportes: 30,
  };
});

describe("OverviewView", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockImplementation(async (path: string) => {
      let data;
      if (path === "/api/summary")
        data = {
          total_savings: 1800,
          total_investments: 700,
          total_real_estate: 200,
          net_worth: 2700,
          net_worth_change: 200,
          total_interest: 45,
        };
      else if (path === "/api/net-worth-history") data = history;
      else if (path === "/api/real-estate") data = [];
      else throw new Error(`Unexpected path: ${path}`);
      return {
        ok: true,
        status: 200,
        json: async () => data,
      };
    });
  });

  it("renders live API totals and recalculates the selected period", async () => {
    const { default: OverviewView } = await import("./OverviewView.vue");
    const wrapper = mount(OverviewView, { global: { stubs: chartStubs } });
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith("/api/summary", expect.any(Object));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/net-worth-history",
      expect.any(Object),
    );
    expect(wrapper.text()).toContain("2700,00");
    expect(wrapper.text()).toContain("Ahorro");
    expect(wrapper.get(".net-worth-source").text()).toContain(
      "Calculado con cuentas de ahorro manuales, balances manuales y crowdfunding",
    );
    expect(wrapper.text()).not.toContain("Al excluir P&L se sustituyen");
    expect(wrapper.text()).not.toContain("Tu patrimonio, sin ruido.");
    expect(wrapper.text()).not.toContain("Posición consolidada");
    expect(wrapper.find(".overview-hero .period-control").exists()).toBe(false);
    expect(wrapper.findAll(".trend-panel .period-control button")).toHaveLength(
      4,
    );
    expect(
      wrapper
        .findAll(".trend-panel .period-control button")
        .map((button) => button.text()),
    ).toEqual(["6 meses", "1 año", "2 años", "Todo"]);
    expect(wrapper.get('[data-testid="allocation-chart"]').text()).toBe("3");
    expect(wrapper.get('[data-testid="line-chart"]').text()).toBe("13");
    expect(
      wrapper.get('[data-testid="line-chart"]').attributes("data-series"),
    ).toBe("2");
    expect(
      wrapper.findAll(".trend-composition li").map((item) => item.text()),
    ).toEqual([
      expect.stringContaining("Cuentas de ahorro"),
      expect.stringContaining("Balances de inversión manual"),
    ]);
    expect(
      wrapper.get('[data-testid="monthly-variation-chart"]').text().split(","),
    ).toHaveLength(12);
    expect(
      wrapper.get('[data-testid="monthly-variation-chart"]').text(),
    ).toContain("100");
    expect(wrapper.text()).toContain("+1200,00");
    expect(wrapper.get(".largest-block-insight dd").text()).toBe("Ahorro");
    expect(wrapper.get(".largest-block-insight small").text()).toContain(
      "del patrimonio",
    );
    expect(wrapper.get(".upcoming-project-insight dd").text()).toBe("Ninguno");
    expect(wrapper.get(".upcoming-project-insight small").text()).toBe(
      "Próximos 3 meses",
    );
    expect(wrapper.find(".monthly-insight-copy").exists()).toBe(false);
    expect(wrapper.get("#monthly-breakdown-title").text()).toBe(
      "junio de 2027",
    );
    expect(
      wrapper
        .getComponent({ name: "MonthlyVariationChart" })
        .props("selectedIndex"),
    ).toBe(11);
    expect(
      wrapper
        .get(".monthly-breakdown-total strong")
        .text()
        .replaceAll("\u00a0", " "),
    ).toBe("+100,00 €");
    expect(
      wrapper
        .findAll(".monthly-breakdown-list dd")
        .map((item) => item.text().replaceAll("\u00a0", " ")),
    ).toEqual(["+80,00 €", "+10,00 €", "+10,00 €"]);

    await wrapper
      .get('[data-testid="monthly-variation-chart"]')
      .trigger("click");
    expect(wrapper.get("#monthly-breakdown-title").text()).toBe(
      "julio de 2026",
    );
    expect(
      wrapper
        .getComponent({ name: "MonthlyVariationChart" })
        .props("selectedIndex"),
    ).toBe(0);

    const excludePnl = wrapper
      .findAll("button")
      .find((button) => button.text() === "Excluir");
    expect(excludePnl).toBeDefined();
    await excludePnl!.trigger("click");
    expect(
      wrapper.get('[data-testid="monthly-variation-chart"]').text(),
    ).toContain("90");
    expect(excludePnl!.attributes("aria-pressed")).toBe("true");
    expect(
      wrapper
        .get(".monthly-breakdown-total strong")
        .text()
        .replaceAll("\u00a0", " "),
    ).toBe("+90,00 €");
    expect(
      wrapper.get(".monthly-breakdown-list > div.excluded small").text(),
    ).toBe("Excluido");

    const sixMonths = wrapper
      .findAll("button")
      .find((button) => button.text() === "6 meses");
    expect(sixMonths).toBeDefined();
    await sixMonths!.trigger("click");

    expect(wrapper.get('[data-testid="line-chart"]').text()).toBe("7");
    expect(
      wrapper.get('[data-testid="monthly-variation-chart"]').text().split(","),
    ).toHaveLength(6);
    expect(wrapper.text()).toContain("+600,00");

    const twoYears = wrapper
      .findAll("button")
      .find((button) => button.text() === "2 años");
    expect(twoYears).toBeDefined();
    await twoYears!.trigger("click");

    expect(wrapper.get('[data-testid="line-chart"]').text()).toBe("25");
    expect(
      wrapper.get('[data-testid="monthly-variation-chart"]').text().split(","),
    ).toHaveLength(24);
    expect(wrapper.text()).toContain("+2400,00");
    wrapper.unmount();
  });

  it("includes real-estate transfers without presenting them as separate gains", async () => {
    const propertyHistory = [
      {
        fecha: "2025-08",
        ahorro: 10234.64,
        ahorro_intereses: 9.91,
        balances: 34687.51,
        balance_aportes: 2850,
        inversiones: 34687.51,
        total: 44922.15,
        inv_aportes: 2850,
      },
      {
        fecha: "2025-09",
        ahorro: 10055.55,
        ahorro_intereses: 9.06,
        balances: 32221.64,
        balance_aportes: -2673,
        inversiones: 35221.64,
        total: 45277.19,
        inv_aportes: 327,
      },
    ];
    fetchMock.mockImplementation(async (path: string) => ({
      ok: true,
      status: 200,
      json: async () =>
        path === "/api/net-worth-history"
          ? propertyHistory
          : path === "/api/real-estate"
            ? []
            : {
                total_savings: 10055.55,
                total_investments: 32221.64,
                total_real_estate: 3000,
                net_worth: 45277.19,
                net_worth_change: 355.04,
                total_interest: 18.97,
              },
    }));

    const { default: OverviewView } = await import("./OverviewView.vue");
    const wrapper = mount(OverviewView, { global: { stubs: chartStubs } });
    await flushPromises();

    expect(
      wrapper
        .getComponent({ name: "MonthlyVariationChart" })
        .props("values")[0],
    ).toBeCloseTo(355.04, 2);
    expect(
      wrapper
        .get(".monthly-breakdown-total strong")
        .text()
        .replaceAll("\u00a0", " "),
    ).toBe("+355,04 €");
    expect(wrapper.text()).toContain("Ahorro y movimientos netos");
    expect(wrapper.text()).not.toContain("Aportación inmobiliaria");

    const excludePnl = wrapper
      .findAll("button")
      .find((button) => button.text() === "Excluir");
    await excludePnl!.trigger("click");

    expect(
      wrapper
        .getComponent({ name: "MonthlyVariationChart" })
        .props("values")[0],
    ).toBeCloseTo(147.91, 2);
    expect(
      wrapper
        .get(".monthly-breakdown-total strong")
        .text()
        .replaceAll("\u00a0", " "),
    ).toBe("+147,91 €");
    wrapper.unmount();
  });

  it("refreshes after source preferences change and describes the dynamic composition", async () => {
    let refreshCount = 0;
    fetchMock.mockImplementation(async (path: string) => {
      if (path === "/api/summary") {
        refreshCount += 1;
        return {
          ok: true,
          status: 200,
          json: async () => ({
            total_savings: 0,
            total_investments: 0,
            total_real_estate: 0,
            net_worth: refreshCount,
            net_worth_change: 0,
            total_interest: 0,
            summary_sources: ["stocks"],
            source_breakdown: [
              { key: "stocks", value: refreshCount, included: true },
            ],
          }),
        };
      }
      if (path === "/api/real-estate") {
        return { ok: true, status: 200, json: async () => [] };
      }
      return { ok: true, status: 200, json: async () => history };
    });
    const { default: OverviewView } = await import("./OverviewView.vue");
    const wrapper = mount(OverviewView, { global: { stubs: chartStubs } });
    await flushPromises();
    expect(wrapper.get(".net-worth-source").text()).toContain(
      "Calculado con Acciones y ETF",
    );
    expect(refreshCount).toBe(1);

    window.dispatchEvent(new CustomEvent("finanzr:summary-sources-updated"));
    await flushPromises();
    expect(refreshCount).toBe(2);
    expect(wrapper.text()).toContain("2,00");
    wrapper.unmount();
  });

  it("shows the historical composition supplied for each source", async () => {
    fetchMock.mockImplementation(async (path: string) => ({
      ok: true,
      status: 200,
      json: async () =>
        path === "/api/net-worth-history"
          ? [
              {
                ...history[0],
                total: 1000,
                source_totals: { savings: 450, stocks: 350, crypto: 200 },
              },
              {
                ...history[1],
                total: 1200,
                source_totals: { savings: 500, stocks: 420, crypto: 280 },
              },
            ]
          : path === "/api/real-estate"
            ? []
            : {
                total_savings: 500,
                total_investments: 700,
                total_real_estate: 0,
                net_worth: 1200,
                net_worth_change: 200,
                total_interest: 10,
                summary_sources: ["savings", "stocks", "crypto"],
                source_breakdown: [
                  { key: "savings", value: 500, included: true },
                  { key: "stocks", value: 420, included: true },
                  { key: "crypto", value: 280, included: true },
                ],
              },
    }));

    const { default: OverviewView } = await import("./OverviewView.vue");
    const wrapper = mount(OverviewView, { global: { stubs: chartStubs } });
    await flushPromises();

    const chart = wrapper.getComponent({ name: "LineChart" });
    expect(chart.props("totalLabel")).toBe("Patrimonio total");
    expect(chart.props("series")).toEqual([
      expect.objectContaining({
        key: "savings",
        values: [450, 500],
        currentValue: 500,
      }),
      expect.objectContaining({
        key: "stocks",
        values: [350, 420],
        currentValue: 420,
      }),
      expect.objectContaining({
        key: "crypto",
        values: [200, 280],
        currentValue: 280,
      }),
    ]);
    expect(wrapper.findAll(".trend-composition li")).toHaveLength(3);
    wrapper.unmount();
  });

  it("highlights the next active crowdfunding project maturing within three months", async () => {
    const maturity = new Date();
    maturity.setMonth(maturity.getMonth() + 2);
    const maturityDate = [
      maturity.getFullYear(),
      String(maturity.getMonth() + 1).padStart(2, "0"),
      String(maturity.getDate()).padStart(2, "0"),
    ].join("-");
    fetchMock.mockImplementation(async (path: string) => ({
      ok: true,
      status: 200,
      json: async () =>
        path === "/api/net-worth-history"
          ? history
          : path === "/api/real-estate"
            ? [
                {
                  id: 1,
                  nombre: "Madrid Norte",
                  plataforma: "Urbanitae",
                  estado: "Activo",
                  capital_inicial: 1000,
                  capital_nuevo: 1000,
                  capital_devuelto: 0,
                  beneficio_obtenido: 0,
                  beneficio_estimado: 100,
                  tir: 10,
                  meses: 12,
                  fecha_inicio: "2025-01-01",
                  fecha_vencimiento: maturityDate,
                  fecha_devolucion: "",
                  movimientos: [],
                  origen: "",
                  moneda: "EUR",
                },
              ]
            : {
                total_savings: 1800,
                total_investments: 700,
                total_real_estate: 1000,
                net_worth: 3500,
                net_worth_change: 200,
                total_interest: 45,
              },
    }));

    const { default: OverviewView } = await import("./OverviewView.vue");
    const wrapper = mount(OverviewView, { global: { stubs: chartStubs } });
    await flushPromises();

    expect(wrapper.get(".upcoming-project-insight dd").text()).toBe(
      "Madrid Norte",
    );
    expect(wrapper.get(".upcoming-project-insight small").text()).toContain(
      "Finaliza el",
    );
    wrapper.unmount();
  });

  it("renders English text and formats", async () => {
    applyLocale("en");
    const { default: OverviewView } = await import("./OverviewView.vue");
    const wrapper = mount(OverviewView, { global: { stubs: chartStubs } });
    await flushPromises();

    expect(wrapper.text()).toContain("Net worth");
    expect(wrapper.text()).toContain("€2,700.00");
    expect(
      wrapper
        .findAll(".trend-panel .period-control button")
        .map((button) => button.text()),
    ).toEqual(["6 months", "1 year", "2 years", "All"]);
    wrapper.unmount();
  });
});
