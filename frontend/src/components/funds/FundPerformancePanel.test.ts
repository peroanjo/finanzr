import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { InvestmentPerformancePoint } from "../../types/api";
import { applyLocale } from "../../i18n";
import FundPerformancePanel, {
  type FundPerformancePanelModel,
} from "./FundPerformancePanel.vue";

vi.mock("../FundPerformanceChart.vue", () => ({
  default: {
    name: "FundPerformanceChart",
    props: ["points", "mode"],
    template:
      '<div data-testid="fund-performance-chart">{{ points.length }}-{{ mode }}</div>',
  },
}));

const points: InvestmentPerformancePoint[] = [
  {
    date: "2026-01-01",
    value: 900,
    invested: 800,
    pnl: 100,
    pnl_percent: 0.125,
  },
  {
    date: "2026-07-01",
    value: 1200,
    invested: 1000,
    pnl: 200,
    pnl_percent: 0.2,
  },
];

const baseModel: FundPerformancePanelModel = {
  accountLabel: "All accounts",
  displayedRange: "01/01/2026 → 01/07/2026",
  range: "1y",
  mode: "value",
  ranges: [
    { key: "6m", label: "6M" },
    { key: "1y", label: "1Y" },
    { key: "2y", label: "2Y" },
    { key: "custom", label: "Calendar" },
  ],
  points,
  lastPerformance: points[1],
  totalValue: 1200,
  totalInvested: 1000,
  realizedPnl: -12,
  periodLabel: "Period P&L",
  periodPnl: -25,
  periodPnlPercent: -0.025,
  loading: false,
  error: "",
  formatters: {
    money: (value) => `money:${value}`,
    percentage: (value) => `percent:${value}`,
    signedMoney: (value) => `signed:${value}`,
  },
};

function modelWith(
  overrides: Partial<FundPerformancePanelModel>,
): FundPerformancePanelModel {
  return { ...baseModel, ...overrides };
}

describe("FundPerformancePanel", () => {
  it("renders KPI values, fallbacks, and sign classes without changing formatting", async () => {
    const wrapper = mount(FundPerformancePanel, {
      props: { model: baseModel },
    });
    const kpis = wrapper.findAll(".fund-period-kpis > div");

    expect(kpis[0].text()).toContain("money:1200");
    expect(kpis[1].text()).toContain("money:1000");
    expect(kpis[2].text()).toContain("signed:200");
    expect(kpis[2].text()).toContain("percent:0.002");
    expect(kpis[3].text()).toContain("signed:-12");
    expect(kpis[4].text()).toContain("signed:-25");
    expect(kpis[2].get("strong").classes()).toContain("positive");
    expect(kpis[3].get("strong").classes()).toContain("negative");
    expect(kpis[4].get("strong").classes()).toContain("negative");

    await wrapper.setProps({
      model: modelWith({
        lastPerformance: null,
        totalValue: 42,
        totalInvested: 21,
        realizedPnl: 0,
        periodPnl: 0,
      }),
    });
    const fallbackKpis = wrapper.findAll(".fund-period-kpis > div");

    expect(fallbackKpis[0].text()).toContain("money:42");
    expect(fallbackKpis[1].text()).toContain("money:21");
    expect(fallbackKpis[2].text()).toContain("signed:0");
    expect(fallbackKpis[2].get("strong").classes()).toContain("positive");
  });

  it("preserves translated controls, ARIA state, chart props, and typed events", async () => {
    const wrapper = mount(FundPerformancePanel, {
      props: { model: baseModel },
    });

    expect(wrapper.get("h2").text()).toBe("Evolución de la cartera");
    expect(wrapper.get('[data-testid="fund-performance-chart"]').text()).toBe(
      "2-value",
    );
    const modeButtons = wrapper.findAll(".fund-mode-control button");
    expect(modeButtons).toHaveLength(2);
    expect(modeButtons[0].attributes("aria-pressed")).toBe("true");
    expect(modeButtons[1].attributes("aria-pressed")).toBe("false");

    await modeButtons[1].trigger("click");
    await wrapper.get(".fund-range-control button:last-child").trigger("click");

    expect(wrapper.emitted("update:mode")).toEqual([["return"]]);
    expect(wrapper.emitted("select-range")).toEqual([["custom"]]);

    applyLocale("en");
    await wrapper.vm.$nextTick();
    expect(wrapper.get("h2").text()).toBe("Portfolio performance");
    expect(wrapper.get(".fund-mode-control").attributes("aria-label")).toBe(
      "Chart mode",
    );
  });

  it("renders loading, error/retry, and insufficient-history states", async () => {
    const loadingWrapper = mount(FundPerformancePanel, {
      props: { model: modelWith({ loading: true }) },
    });
    expect(loadingWrapper.get(".fund-chart-state").text()).toContain(
      "Calculando rendimiento",
    );
    expect(
      loadingWrapper.find('[data-testid="fund-performance-chart"]').exists(),
    ).toBe(false);

    const errorWrapper = mount(FundPerformancePanel, {
      props: { model: modelWith({ error: "Service unavailable" }) },
    });
    expect(errorWrapper.get(".fund-chart-state.error-state").text()).toContain(
      "Service unavailable",
    );
    await errorWrapper.get(".fund-chart-state button").trigger("click");
    expect(errorWrapper.emitted("retry")).toHaveLength(1);

    const emptyWrapper = mount(FundPerformancePanel, {
      props: { model: modelWith({ points: [] }) },
    });
    expect(emptyWrapper.get(".fund-chart-state strong").text()).toContain(
      "Sin histórico suficiente",
    );
    expect(
      emptyWrapper.find('[data-testid="fund-performance-chart"]').exists(),
    ).toBe(false);
  });
});
