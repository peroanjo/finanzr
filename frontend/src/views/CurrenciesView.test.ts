import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { applyLocale, registerMessages } from "../i18n";
import { currenciesMessages } from "../i18n/currenciesMessages";
import type { FxRateChartResponse } from "../types/api";
import CurrenciesView from "./CurrenciesView.vue";

registerMessages(currenciesMessages);

vi.mock("../api/client", () => ({
  api: vi.fn(),
  json: (method: string, body: unknown) => ({
    method,
    body: JSON.stringify(body),
  }),
}));
vi.mock("../components/CurrencyRateChart.vue", () => ({
  default: {
    name: "CurrencyRateChart",
    props: ["points", "fromCurrency", "toCurrency"],
    template:
      '<div data-testid="fx-chart" :data-from="fromCurrency" :data-to="toCurrency">{{ points.length }}</div>',
  },
}));

const apiMock = vi.mocked(api);
const rates = [
  {
    id: "rate-usd",
    quote_currency: "USD",
    base_currency: "EUR",
    rate_date: "2026-08-01",
    rate: 0.92,
    source: "yahoo",
  },
  {
    id: "rate-gbp",
    quote_currency: "GBP",
    base_currency: "EUR",
    rate_date: "2026-08-02",
    rate: 1.16,
    source: "yahoo",
  },
];

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

describe("CurrenciesView", () => {
  beforeEach(() => {
    applyLocale("es-ES");
    HTMLDialogElement.prototype.showModal = vi.fn();
    HTMLDialogElement.prototype.close = vi.fn();
    apiMock.mockImplementation(async (path) => {
      if (path === "/fx-rates") return rates;
      if (path.startsWith("/fx-rates/chart?")) {
        const query = new URLSearchParams(path.split("?")[1]);
        const from = query.get("from")!;
        const to = query.get("to")!;
        return {
          from_currency: from,
          to_currency: to,
          range: query.get("range"),
          data: [{ fecha: "2026-08-02", rate: from === "GBP" ? 1.16 : 0.92 }],
        };
      }
      if (path.startsWith("/fx-rates/convert?")) {
        return {
          from_currency: "GBP",
          to_currency: "EUR",
          original_amount: 100,
          converted_amount: 116,
          rate: 1.16,
          rate_date: "2026-08-02",
          source: "yahoo",
        };
      }
      throw new Error(`Unexpected path: ${path}`);
    });
  });

  it("loads the first pair chart and refetches it when a currency row is selected", async () => {
    const wrapper = mount(CurrenciesView);
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/fx-rates/chart?from=GBP&to=EUR&range=1y",
    );
    expect(
      wrapper.get('[data-testid="fx-chart"]').attributes("data-from"),
    ).toBe("GBP");

    const usdRow = wrapper
      .findAll(".asset-row")
      .find((row) => row.text().includes("USD / EUR"));
    expect(usdRow).toBeDefined();
    await usdRow!.trigger("click");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/fx-rates/chart?from=USD&to=EUR&range=1y",
    );
    expect(
      wrapper.get('[data-testid="fx-chart"]').attributes("data-from"),
    ).toBe("USD");

    await wrapper.get(".fx-swap").trigger("click");
    await flushPromises();

    expect(
      wrapper.get('[data-testid="fx-chart"]').attributes("data-from"),
    ).toBe("USD");
    expect(wrapper.get('[data-testid="fx-chart"]').attributes("data-to")).toBe(
      "EUR",
    );
  });

  it("does not expose a previous pair while chart requests resolve out of order", async () => {
    const gbpChart = deferred<FxRateChartResponse>();
    const usdChart = deferred<FxRateChartResponse>();
    apiMock.mockImplementation(async (path) => {
      if (path === "/fx-rates") return rates;
      if (path === "/fx-rates/chart?from=GBP&to=EUR&range=1y")
        return gbpChart.promise;
      if (path === "/fx-rates/chart?from=USD&to=EUR&range=1y")
        return usdChart.promise;
      if (path.startsWith("/fx-rates/convert?")) {
        return {
          from_currency: "GBP",
          to_currency: "EUR",
          original_amount: 100,
          converted_amount: 116,
          rate: 1.16,
          rate_date: "2026-08-02",
          source: "yahoo",
        };
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    const wrapper = mount(CurrenciesView);
    await flushPromises();
    const usdRow = wrapper
      .findAll(".asset-row")
      .find((row) => row.text().includes("USD / EUR"));
    await usdRow!.trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="fx-chart"]').exists()).toBe(false);
    expect(wrapper.find(".fx-chart-latest").exists()).toBe(false);

    gbpChart.resolve({
      from_currency: "GBP",
      to_currency: "EUR",
      range: "1y",
      data: [{ fecha: "2026-08-02", rate: 1.16 }],
    });
    await flushPromises();

    expect(wrapper.find('[data-testid="fx-chart"]').exists()).toBe(false);
    expect(wrapper.find(".fx-chart-latest").exists()).toBe(false);

    usdChart.resolve({
      from_currency: "USD",
      to_currency: "EUR",
      range: "1y",
      data: [{ fecha: "2026-08-02", rate: 0.92 }],
    });
    await flushPromises();

    expect(
      wrapper.get('[data-testid="fx-chart"]').attributes("data-from"),
    ).toBe("USD");
    expect(wrapper.get(".fx-chart-latest").text()).toContain("0,92");
  });

  it("applies a custom date range to the selected currency chart", async () => {
    const wrapper = mount(CurrenciesView);
    await flushPromises();

    await wrapper
      .get('button[aria-label="Periodo personalizado"]')
      .trigger("click");
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalled();
    expect(
      wrapper.get('button[aria-label="Periodo personalizado"]').text(),
    ).toBe("Calendario");

    const calendar = wrapper.get('dialog[aria-labelledby="fx-calendar-title"]');
    const inputs = calendar.findAll('input[type="date"]');
    await inputs[0].setValue("2025-01-15");
    await inputs[1].setValue("2025-05-20");
    await calendar.get("form").trigger("submit");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/fx-rates/chart?from=GBP&to=EUR&start=2025-01-15&end=2025-05-20",
    );
    expect(
      calendar.get('button[type="submit"]').attributes("disabled"),
    ).toBeUndefined();
  });

  it("prefers a workspace override over a provider rate for the same date", async () => {
    apiMock.mockImplementation(async (path) => {
      if (path === "/fx-rates") {
        return [
          { ...rates[0], scope: "provider" },
          {
            ...rates[0],
            id: "override-usd",
            rate: 0.95,
            source: "manual",
            scope: "workspace",
          },
        ];
      }
      if (path.startsWith("/fx-rates/chart?")) {
        return {
          from_currency: "USD",
          to_currency: "EUR",
          range: "1y",
          data: [],
        };
      }
      if (path.startsWith("/fx-rates/convert?")) {
        return {
          from_currency: "USD",
          to_currency: "EUR",
          original_amount: 100,
          converted_amount: 95,
          rate: 0.95,
          rate_date: "2026-08-01",
          source: "manual",
        };
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    const wrapper = mount(CurrenciesView);
    await flushPromises();

    expect(wrapper.findAll(".asset-row")).toHaveLength(1);
    expect(wrapper.get(".asset-row").text()).toContain("0,95");
    const deleteButton = wrapper
      .findAll(".asset-header-actions button")
      .find((button) => button.text().includes("Eliminar"));
    expect(deleteButton?.attributes("disabled")).toBeUndefined();
  });

  it("localizes the rate list and converter controls in English", async () => {
    const wrapper = mount(CurrenciesView);
    await flushPromises();
    applyLocale("en");
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain("Exchange rates");
    expect(wrapper.text()).toContain("Currency Pair");
    expect(wrapper.text()).toContain("Direct Rate");
    expect(wrapper.text()).toContain("Inverse Rate");
    expect(wrapper.text()).toContain("Direct");
    expect(wrapper.text()).toContain("Inverse");
    expect(wrapper.text()).toContain("Live");
    expect(wrapper.get(".fx-swap").attributes("title")).toBe("Swap currencies");
  });
});
