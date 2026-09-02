import { mount } from "@vue/test-utils";
import { applyLocale, applyReportingCurrency } from "../i18n";
import FundPriceChart from "./FundPriceChart.vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FundOrder } from "../types/api";
import {
  groupFundOperationPoints,
  visibleFundOperationPoints,
} from "./fundPriceChart";

type ChartPoint = number | { y: number };
type ChartDataset = { data: ChartPoint[] };
type ChartTooltipContext = {
  tooltip: {
    opacity: number;
    caretX?: number;
    caretY?: number;
    dataPoints?: Array<{
      datasetIndex: number;
      dataIndex: number;
      parsed: { y: number };
    }>;
  };
};
type ChartConfig = {
  data: { datasets: ChartDataset[] };
  options?: {
    plugins?: {
      tooltip?: { external?: (context: ChartTooltipContext) => void };
    };
  };
  plugins?: Array<{ afterDatasetsDraw?: (chart: ChartLike) => void }>;
};
type ChartMeta = {
  data: Array<{
    getProps: (
      keys: string[],
      useFinalPosition: boolean,
    ) => { x: number; y: number };
  }>;
};
type ChartLike = {
  data: ChartConfig["data"];
  getDatasetMeta: (index: number) => ChartMeta;
};

const chartState = vi.hoisted(() => ({
  last: null as ChartLike | null,
  config: null as ChartConfig | null,
  calls: [] as boolean[],
  width: 600,
}));

vi.mock("chart.js", () => ({
  CategoryScale: {},
  Filler: {},
  LineController: {},
  LineElement: {},
  LinearScale: {},
  PointElement: {},
  ScatterController: {},
  Tooltip: {},
  Chart: class MockChart {
    static register() {}
    data: ChartConfig["data"];
    metas: ChartMeta[] = [];
    width = chartState.width;
    height = 325;
    ctx = {
      save: vi.fn(),
      restore: vi.fn(),
      beginPath: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      stroke: vi.fn(),
    };
    tooltip = { setActiveElements: vi.fn() };
    constructor(_canvas: HTMLCanvasElement, config: ChartConfig) {
      this.data = config.data;
      chartState.last = this;
      chartState.config = config;
      chartState.calls = [];
      config.plugins?.forEach((plugin) => plugin.afterDatasetsDraw?.(this));
    }
    destroy() {}
    setActiveElements() {}
    update() {}
    getDatasetMeta(index: number): ChartMeta {
      if (this.metas[index]) return this.metas[index];
      this.metas[index] = {
        data: (this.data.datasets[index]?.data ?? []).map(
          (point, pointIndex) => ({
            getProps: vi.fn((_keys: string[], useFinalPosition: boolean) => {
              expect(useFinalPosition).toBe(false);
              chartState.calls.push(useFinalPosition);
              return {
                x: 90 + pointIndex * 180,
                y: typeof point === "number" ? point : point.y,
              };
            }),
          }),
        ),
      };
      return this.metas[index];
    }
  },
}));

import { sharedMessages } from "../i18n/sharedMessages";
import { registerMessages } from "../i18n";

registerMessages(sharedMessages);

afterEach(() => {
  chartState.width = 600;
});

function order(id: string, date: string): FundOrder {
  return {
    id,
    fecha_operacion: date,
    fecha_liquidacion: date,
    tipo_operacion: "SUSCRIPCION",
    isin: "TEST",
    nombre_fondo: "Fondo de prueba",
    titulos: 1,
    precio_neto: 100,
    importe_neto: 100,
    cuenta_id: "00000000-0000-0000-0000-000000000001",
  };
}

const points = [
  { fecha: "2026-07-10", precio: 98 },
  { fecha: "2026-07-11", precio: 101 },
];

describe("visibleFundOperationPoints", () => {
  beforeEach(() => {
    applyLocale("es-ES", false);
    applyReportingCurrency("EUR");
  });
  it("excludes operations outside the chart instead of grouping them at its edges", () => {
    const points = visibleFundOperationPoints(
      [
        order("before", "2026-01-01"),
        order("inside", "2026-07-11"),
        order("after", "2026-12-31"),
      ],
      ["2026-07-10", "2026-07-12"],
    );

    expect(points).toHaveLength(1);
    expect(points[0].order.id).toBe("inside");
    expect(points[0].x).toBe("2026-07-10");
  });

  it("groups same-day entries and exits independently with weighted details", () => {
    const first = order("first", "2026-07-11");
    const second = {
      ...order("second", "2026-07-11"),
      titulos: 3,
      precio_neto: 120,
      importe_neto: 360,
    };
    const redemption = {
      ...order("redemption", "2026-07-11"),
      tipo_operacion: "REEMBOLSO",
      titulos: 2,
      precio_neto: 130,
      importe_neto: 260,
    };

    const markers = groupFundOperationPoints(
      visibleFundOperationPoints(
        [first, second, redemption],
        ["2026-07-11", "2026-07-12"],
      ),
    );

    expect(markers).toHaveLength(2);
    expect(markers.find((marker) => marker.buy)?.operationCount).toBe(2);
    expect(markers.find((marker) => marker.buy)?.order.titulos).toBe(4);
    expect(markers.find((marker) => marker.buy)?.order.precio_neto).toBe(115);
    expect(
      markers.find((marker) => !marker.buy)?.sourceOrders[0].tipo_operacion,
    ).toBe("REEMBOLSO");
  });

  it("keeps real operation dates separate when weekly labels share one candle", () => {
    const first = order("weekly-first", "2026-07-07");
    const second = {
      ...order("weekly-second", "2026-07-10"),
      precio_neto: 110,
    };
    const points = visibleFundOperationPoints(
      [first, second],
      ["2026-07-07", "2026-07-14"],
    );

    const markers = groupFundOperationPoints(points);

    expect(points.map((point) => point.x)).toEqual([
      "2026-07-07",
      "2026-07-07",
    ]);
    expect(markers).toHaveLength(2);
    expect(markers.map((marker) => marker.order.fecha_operacion)).toEqual([
      "2026-07-07",
      "2026-07-10",
    ]);
    expect(markers.every((marker) => marker.operationCount === 1)).toBe(true);
  });
});

describe("FundPriceChart operation bubble", () => {
  it("uses the shared card treatment for the price hover tooltip", async () => {
    const wrapper = mount(FundPriceChart, {
      props: { points, orders: [], averagePrice: 99 },
    });
    const external = chartState.config?.options?.plugins?.tooltip?.external;
    if (!external) throw new Error("Chart tooltip callback was not registered");

    external({
      tooltip: {
        opacity: 1,
        caretX: 300,
        caretY: 120,
        dataPoints: [{ datasetIndex: 0, dataIndex: 1, parsed: { y: 101 } }],
      },
    });
    await wrapper.vm.$nextTick();

    const tooltip = wrapper.get(".price-tooltip");
    expect(tooltip.text().replaceAll("\u00a0", " ")).toContain("101,00 €");
    expect(tooltip.find(".operation-tooltip-accent.price").exists()).toBe(true);
    expect(wrapper.find(".price-tooltip-guide").exists()).toBe(true);

    external({ tooltip: { opacity: 0 } });
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".price-tooltip").exists()).toBe(false);
  });

  it("shows localized fund movement details and hides the generic tooltip on hover", async () => {
    const fundOrder = {
      ...order("fund-buy", "2026-07-11"),
      titulos: 1.5,
      precio_neto: 100,
      importe_neto: 150,
      cuenta_nombre: "Indexa",
      plataforma: "MyInvestor",
    };
    const wrapper = mount(FundPriceChart, {
      props: { points, orders: [fundOrder], averagePrice: 99 },
    });

    await wrapper.get(".operation-marker").trigger("pointerenter");
    const detail = wrapper
      .get(".operation-tooltip")
      .text()
      .replaceAll("\u00a0", " ");
    expect(detail).toContain("Aportación · Indexa · MyInvestor");
    expect(detail).toContain("11 jul 2026");
    expect(detail).toContain("1,5 participaciones · 100,00 € / ud.");
    expect(detail).toContain("Total 150,00 €");
    expect(wrapper.get(".operation-marker").attributes("aria-label")).toContain(
      "Aportación",
    );

    await wrapper.get(".operation-marker").trigger("pointerleave");
    await new Promise((resolve) => setTimeout(resolve, 130));
    expect(wrapper.find(".operation-tooltip").exists()).toBe(false);
  });

  it("keeps the operation bubble in bounds and translates currency to English", async () => {
    applyLocale("en", false);
    applyReportingCurrency("USD");
    const wrapper = mount(FundPriceChart, {
      props: {
        points,
        orders: [
          {
            ...order("fund-sell", "2026-07-11"),
            tipo_operacion: "REEMBOLSO",
            importe_neto: 100,
          },
        ],
        averagePrice: null,
      },
    });

    await wrapper.get(".operation-marker").trigger("focus");
    const tooltip = wrapper.get(".operation-tooltip");
    const detail = tooltip.text().replaceAll("\u00a0", " ");
    expect(detail).toContain("Redemption · Investment account");
    expect(detail).toContain("Jul 11, 2026");
    expect(detail).toContain("$100.00");
    expect(
      Number.parseFloat(
        tooltip.element.getAttribute("style")?.match(/left: ([\d.]+)px/)?.[1] ??
          "-1",
      ),
    ).toBeGreaterThanOrEqual(4);
    expect(
      Number.parseFloat(
        tooltip.element.getAttribute("style")?.match(/top: ([\d.]+)px/)?.[1] ??
          "-1",
      ),
    ).toBeGreaterThanOrEqual(4);
  });

  it("uses a directional localized heading for mixed movement types", async () => {
    const wrapper = mount(FundPriceChart, {
      props: {
        points,
        orders: [
          order("mixed-contribution", "2026-07-11"),
          {
            ...order("mixed-transfer", "2026-07-11"),
            tipo_operacion: "SUSCR.POR TRASPASO I",
          },
        ],
        averagePrice: null,
      },
    });

    await wrapper.get(".operation-marker").trigger("pointerenter");
    const detail = wrapper
      .get(".operation-tooltip")
      .text()
      .replaceAll("\u00a0", " ");
    expect(detail).toContain("Compra / entrada ×2");
    expect(detail).toContain("Aportación");
    expect(detail).toContain("Traspaso de entrada");
    expect(detail.match(/11 jul 2026/g)).toHaveLength(3);

    applyLocale("en", false);
    await wrapper.vm.$nextTick();
    await wrapper.get(".operation-marker").trigger("pointerenter");
    const english = wrapper
      .get(".operation-tooltip")
      .text()
      .replaceAll("\u00a0", " ");
    expect(english).toContain("Buy / transfer in ×2");
    expect(english).toContain("Contribution");
    expect(english).toContain("Transfer in");
  });

  it("keeps seven grouped operations scrollable within a mobile-height card", async () => {
    chartState.width = 280;
    const orders = Array.from({ length: 7 }, (_, index) =>
      order(`grouped-${index}`, "2026-07-11"),
    );
    const wrapper = mount(FundPriceChart, {
      props: { points, orders, averagePrice: null },
    });

    await wrapper.get(".operation-marker").trigger("pointerenter");
    const tooltip = wrapper.get(".operation-tooltip");
    const rows = tooltip.get(".operation-tooltip-rows");
    const style = tooltip.attributes("style") ?? "";
    const rowsStyle = rows.attributes("style") ?? "";
    expect(
      Number.parseFloat(style.match(/height: ([\d.]+)px/)?.[1] ?? "999"),
    ).toBeLessThanOrEqual(317);
    expect(
      Number.parseFloat(rowsStyle.match(/max-height: ([\d.]+)px/)?.[1] ?? "0"),
    ).toBeLessThanOrEqual(253);
    expect(rows.attributes("tabindex")).toBe("0");
    expect(rows.findAll('[role="listitem"]')).toHaveLength(7);

    (wrapper.get(".operation-marker").element as HTMLElement).focus();
    await wrapper.vm.$nextTick();
    (rows.element as HTMLElement).focus();
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".operation-tooltip").exists()).toBe(true);
    await rows.trigger("keydown", { key: "Escape", code: "Escape" });
    expect(wrapper.find(".operation-tooltip").exists()).toBe(false);
    expect(document.activeElement).not.toBe(rows.element);
  });

  it("removes focus on Escape and reopens from the button click", async () => {
    const host = document.createElement("div");
    host.className = "app-shell";
    document.body.appendChild(host);
    const wrapper = mount(FundPriceChart, {
      props: {
        points,
        orders: [order("keyboard", "2026-07-11")],
        averagePrice: null,
      },
      attachTo: host,
    });
    const marker = wrapper.get(".operation-marker");

    (marker.element as HTMLElement).focus();
    await wrapper.vm.$nextTick();
    expect(document.activeElement).toBe(marker.element);
    expect(wrapper.find(".operation-tooltip").exists()).toBe(true);
    await marker.trigger("keydown", { key: "Escape", code: "Escape" });
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".operation-tooltip").exists()).toBe(false);
    expect(document.activeElement).not.toBe(marker.element);

    await marker.trigger("click");
    expect(wrapper.find(".operation-tooltip").exists()).toBe(true);
    wrapper.unmount();
    host.remove();
  });

  it("keeps the active bubble open and updates it during locale, currency and theme renders", async () => {
    const host = document.createElement("div");
    host.className = "app-shell";
    document.body.appendChild(host);
    const wrapper = mount(FundPriceChart, {
      props: {
        points,
        orders: [order("live-locale", "2026-07-11")],
        averagePrice: null,
      },
      attachTo: host,
    });
    await wrapper.get(".operation-marker").trigger("pointerenter");
    expect(wrapper.get(".operation-tooltip").text()).toContain("Aportación");

    applyLocale("en", false);
    applyReportingCurrency("USD");
    host.setAttribute("data-theme", "dark");
    await wrapper.vm.$nextTick();
    await new Promise((resolve) => setTimeout(resolve, 0));
    await wrapper.vm.$nextTick();

    const updated = wrapper
      .get(".operation-tooltip")
      .text()
      .replaceAll("\u00a0", " ");
    expect(updated).toContain("Contribution");
    expect(updated).toContain("$100.00");
    wrapper.unmount();
    host.remove();
  });

  it("tracks animated marker coordinates for the pin glyph", () => {
    mount(FundPriceChart, {
      props: {
        points,
        orders: [order("animated", "2026-07-11")],
        averagePrice: null,
      },
    });
    expect(chartState.calls.length).toBeGreaterThan(0);
    expect(
      chartState.calls.every((useFinalPosition) => useFinalPosition === false),
    ).toBe(true);
  });
});
