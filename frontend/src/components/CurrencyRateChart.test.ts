import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { registerMessages } from "../i18n";
import { currenciesMessages } from "../i18n/currenciesMessages";
import CurrencyRateChart from "./CurrencyRateChart.vue";

vi.mock("chart.js", () => ({
  CategoryScale: {},
  Filler: {},
  LineController: {},
  LineElement: {},
  LinearScale: {},
  PointElement: {},
  Tooltip: {},
  Chart: class {
    static register() {}
    destroy() {}
  },
}));

registerMessages(currenciesMessages);

describe("CurrencyRateChart", () => {
  it("exposes a localized accessible label for the selected pair", () => {
    const wrapper = mount(CurrencyRateChart, {
      props: {
        fromCurrency: "USD",
        toCurrency: "EUR",
        points: [{ fecha: "2026-08-02", rate: 0.92 }],
      },
    });

    expect(wrapper.get("canvas").attributes("aria-label")).toBe(
      "Gráfica del histórico de cambio de USD a EUR",
    );
  });
});
