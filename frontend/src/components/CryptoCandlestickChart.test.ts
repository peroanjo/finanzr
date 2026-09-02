import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { applyLocale, applyReportingCurrency } from "../i18n";
import CryptoCandlestickChart from "./CryptoCandlestickChart.vue";

const points = [
  {
    fecha: "2026-07-09",
    precio: 69000,
    open: 68000,
    high: 70000,
    low: 67000,
    close: 69000,
  },
  {
    fecha: "2026-07-10",
    precio: 71000,
    open: 69000,
    high: 72000,
    low: 68500,
    close: 71000,
  },
];
const operations = [
  {
    id: "btc-buy",
    fecha_operacion: "2026-07-10",
    titulos: 0.001,
    importe_neto: 71.25,
    cuenta_id: "00000000-0000-0000-0000-000000000001",
    cuenta_nombre: "KrakenPro",
    plataforma: "KrakenPro",
    tipo_operacion: "Compra",
    symbol: "BTC",
    nombre_activo: "Bitcoin",
    precio_compra: 71000,
    comision: 0.25,
  },
];

describe("CryptoCandlestickChart", () => {
  beforeEach(() => applyReportingCurrency("EUR"));

  it("shows the nearest candle close in a themed tooltip", async () => {
    const wrapper = mount(CryptoCandlestickChart, {
      props: { points, operations: [], averagePrice: 70000 },
    });
    const svg = wrapper.get("svg").element;
    vi.spyOn(svg, "getBoundingClientRect").mockReturnValue({
      left: 0,
      top: 0,
      width: 1000,
      height: 370,
      right: 1000,
      bottom: 370,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    await wrapper
      .get("svg")
      .trigger("pointermove", { clientX: 900, clientY: 160 });

    const tooltipText = wrapper
      .get(".chart-tooltip")
      .text()
      .replaceAll("\u00a0", " ");
    expect(tooltipText).toContain("10 jul 2026");
    expect(tooltipText).toContain("Cierre 71.000 €");

    await wrapper.get("svg").trigger("pointerleave");
    expect(wrapper.find(".chart-tooltip").exists()).toBe(false);
  });

  it("shows the selected dates and price change while dragging a period", async () => {
    const wrapper = mount(CryptoCandlestickChart, {
      props: { points, operations: [], averagePrice: 70000 },
    });
    const svg = wrapper.get("svg").element;
    vi.spyOn(svg, "getBoundingClientRect").mockReturnValue({
      left: 0,
      top: 0,
      width: 1000,
      height: 370,
      right: 1000,
      bottom: 370,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    await wrapper.get("svg").trigger("pointerdown", {
      button: 0,
      pointerId: 1,
      clientX: 20,
      clientY: 160,
    });
    await wrapper.get("svg").trigger("pointermove", {
      pointerId: 1,
      clientX: 900,
      clientY: 160,
    });
    await wrapper.get("svg").trigger("pointerup", {
      pointerId: 1,
      clientX: 900,
      clientY: 160,
    });

    const summary = wrapper
      .get(".range-summary")
      .text()
      .replaceAll("\u00a0", " ");
    expect(summary).toContain("09/07/2026 → 10/07/2026");
    expect(summary).toContain("Subida +2,90 %");
    expect(wrapper.find(".range-selection").exists()).toBe(true);

    await wrapper.get("svg").trigger("pointerdown", {
      button: 0,
      pointerId: 2,
      clientX: 900,
      clientY: 160,
    });
    await wrapper.get("svg").trigger("pointerup", {
      pointerId: 2,
      clientX: 900,
      clientY: 160,
    });

    expect(wrapper.find(".range-selection").exists()).toBe(false);
    expect(wrapper.find(".range-summary").exists()).toBe(false);
    expect(
      wrapper.get(".chart-tooltip").text().replaceAll("\u00a0", " "),
    ).toContain("Cierre 71.000 €");
  });

  it("reacts to GBP and USD reporting currencies", async () => {
    applyLocale("es-ES", false);
    applyReportingCurrency("GBP");
    const wrapper = mount(CryptoCandlestickChart, {
      props: { points, operations: [], averagePrice: 70000 },
    });
    const svg = wrapper.get("svg").element;
    vi.spyOn(svg, "getBoundingClientRect").mockReturnValue({
      left: 0,
      top: 0,
      width: 1000,
      height: 370,
      right: 1000,
      bottom: 370,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    await wrapper
      .get("svg")
      .trigger("pointermove", { clientX: 900, clientY: 160 });
    expect(wrapper.get(".chart-tooltip").text()).toContain(
      new Intl.NumberFormat("es-ES", {
        style: "currency",
        currency: "GBP",
        maximumFractionDigits: 0,
      }).format(71000),
    );

    applyReportingCurrency("USD");
    await wrapper.vm.$nextTick();
    expect(wrapper.get(".chart-tooltip").text()).toContain(
      new Intl.NumberFormat("es-ES", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      }).format(71000),
    );
  });

  it("shows the operation details when hovering a buy or sell marker", async () => {
    const wrapper = mount(CryptoCandlestickChart, {
      props: { points, operations, averagePrice: 70000 },
    });

    await wrapper.get(".operation-marker").trigger("pointerenter");

    const detail = wrapper
      .get(".operation-tooltip")
      .text()
      .replaceAll("\u00a0", " ");
    expect(detail).toContain("Compra · KrakenPro");
    expect(detail).toContain("10 jul 2026");
    expect(detail).toContain("0,001 BTC · 71.000 € / ud.");
    expect(detail).toContain("Total 71,25 € · Comisión 0,25 €");
    expect(wrapper.find(".chart-tooltip").exists()).toBe(false);

    await wrapper.get(".operation-marker").trigger("pointerleave");
    expect(wrapper.find(".operation-tooltip").exists()).toBe(false);
  });

  it("renders compact trade pins in local candle lanes", () => {
    const sellOperation = {
      ...operations[0],
      id: "btc-sell",
      fecha_operacion: "2026-07-09",
      tipo_operacion: "Venta",
      precio_compra: 69000,
    };
    const earlyBuyOperation = {
      ...operations[0],
      id: "btc-buy-early",
      fecha_operacion: "2026-07-09",
      precio_compra: 69000,
    };
    const wrapper = mount(CryptoCandlestickChart, {
      props: {
        points,
        operations: [operations[0], sellOperation, earlyBuyOperation],
        averagePrice: 70000,
        operationMarkerShape: "pin",
      },
    });

    const buyMarker = wrapper.get('[data-operation-id="btc-buy"]');
    const earlyBuyMarker = wrapper.get('[data-operation-id="btc-buy-early"]');
    const sellMarker = wrapper.get('[data-operation-id="btc-sell"]');
    expect(wrapper.findAll(".operation-pin-body")).toHaveLength(3);
    expect(wrapper.findAll(".operation-pin-connector")).toHaveLength(3);
    expect(wrapper.find(".operation-arrow").exists()).toBe(false);
    expect(buyMarker.attributes("data-marker-shape")).toBe("pin");
    expect(sellMarker.attributes("data-marker-shape")).toBe("pin");
    expect(buyMarker.attributes("data-direction")).toBe("buy");
    expect(sellMarker.attributes("data-direction")).toBe("sell");
    expect(buyMarker.findAll(".operation-pin-glyph")).toHaveLength(2);
    expect(sellMarker.findAll(".operation-pin-glyph")).toHaveLength(1);
    expect(buyMarker.get(".operation-pin-body rect").attributes("width")).toBe(
      "18",
    );
    expect(buyMarker.get(".operation-pin-body rect").attributes("height")).toBe(
      "16",
    );

    const candleLowYs = wrapper
      .findAll(".candles g line")
      .map((line) => Number(line.attributes("y2")));
    const candleHighYs = wrapper
      .findAll(".candles g line")
      .map((line) => Number(line.attributes("y1")));
    expect(Number(earlyBuyMarker.attributes("data-candle-low-y"))).toBe(
      candleLowYs[0],
    );
    expect(Number(buyMarker.attributes("data-candle-low-y"))).toBe(
      candleLowYs[1],
    );
    expect(Number(sellMarker.attributes("data-candle-high-y"))).toBe(
      candleHighYs[0],
    );
    expect(Number(earlyBuyMarker.attributes("data-marker-y"))).not.toBe(
      Number(buyMarker.attributes("data-marker-y")),
    );
    expect(
      Number(buyMarker.attributes("data-connector-pin-y")) -
        Number(buyMarker.attributes("data-connector-candle-y")),
    ).toBe(12);
    expect(
      Number(sellMarker.attributes("data-connector-candle-y")) -
        Number(sellMarker.attributes("data-connector-pin-y")),
    ).toBe(12);
    expect(
      Number(buyMarker.attributes("data-marker-y")) - candleLowYs[1],
    ).toBeCloseTo(20, 5);
    expect(
      candleHighYs[0] - Number(sellMarker.attributes("data-marker-y")),
    ).toBeCloseTo(20, 5);
  });

  it("groups same-day operations into a single count pin", async () => {
    const secondBuy = {
      ...operations[0],
      id: "btc-buy-second",
      titulos: 0.002,
      importe_neto: 142.5,
      comision: 0.5,
    };
    const wrapper = mount(CryptoCandlestickChart, {
      props: {
        points,
        operations: [operations[0], secondBuy],
        averagePrice: 70000,
      },
    });

    const marker = wrapper.get(".operation-marker");
    expect(wrapper.findAll(".operation-marker")).toHaveLength(1);
    expect(marker.attributes("data-operation-count")).toBe("2");
    expect(marker.get(".operation-pin-body rect").attributes("width")).toBe(
      "25",
    );
    expect(marker.get(".operation-pin-count").text()).toBe("+2");

    await marker.trigger("pointerenter");
    const tooltip = wrapper.get(".operation-tooltip");
    const detail = tooltip.text().replaceAll("\u00a0", " ");
    expect(detail).toContain("Compra ×2");
    expect(tooltip.findAll(".operation-tooltip-row")).toHaveLength(2);
    expect(
      tooltip
        .findAll(".operation-tooltip-row-account")
        .map((row) => row.text()),
    ).toEqual(["KrakenPro", "KrakenPro"]);
    expect(detail).toContain("0,001 BTC");
    expect(detail).toContain("Total 71,25 €");
    expect(detail).toContain("Comisión 0,25 €");
    expect(detail).toContain("0,002 BTC");
    expect(detail).toContain("Total 142,50 €");
    expect(detail).toContain("Comisión 0,50 €");
  });

  it("identifies a historical operation adjusted only for the chart", async () => {
    const adjustedOperation = {
      id: "byd-pre-split",
      fecha_operacion: "2025-02-03",
      titulos: 3,
      importe_neto: 34.07,
      cuenta_id: "00000000-0000-0000-0000-000000000001",
      cuenta_nombre: "Trade Republic",
      plataforma: "Trade Republic",
      tipo_operacion: "Compra",
      isin: "CNE100000296",
      nombre_activo: "BYD",
      precio_compra: 34.07 / 3,
      comision: 0,
      es_saveback: false,
      chartAdjustment: {
        id: "byd-pre-june-10-2025-split-3-to-1",
        label: "Split BYD 3:1",
      },
    };
    const bydPoints = [
      {
        fecha: "2025-02-03",
        precio: 11.2,
        open: 11,
        high: 11.5,
        low: 10.9,
        close: 11.2,
      },
      {
        fecha: "2025-02-04",
        precio: 11.4,
        open: 11.2,
        high: 11.6,
        low: 11.1,
        close: 11.4,
      },
    ];
    const wrapper = mount(CryptoCandlestickChart, {
      props: {
        points: bydPoints,
        operations: [adjustedOperation],
        averagePrice: null,
      },
    });

    await wrapper.get(".operation-marker").trigger("pointerenter");

    const detail = wrapper
      .get(".operation-tooltip")
      .text()
      .replaceAll("\u00a0", " ");
    expect(detail).toContain("3 CNE100000296 · 11 € / ud.");
    expect(detail).toContain("Ajuste gráfico · Split BYD 3:1");
  });

  it("translates chart details and regional formats to English", async () => {
    applyLocale("en");
    const wrapper = mount(CryptoCandlestickChart, {
      props: { points, operations, averagePrice: 70000 },
    });

    await wrapper.get(".operation-marker").trigger("pointerenter");
    const detail = wrapper
      .get(".operation-tooltip")
      .text()
      .replaceAll("\u00a0", " ");
    expect(detail).toContain("Buy · KrakenPro");
    expect(detail).toContain("Jul 10, 2026");
    expect(detail).toContain("0.001 BTC · €71,000 / unit");
    expect(detail).toContain("Total €71.25 · Fee €0.25");
  });
});
