import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NormalizedCandlestickChartPoint } from "../domain/investments";
import { applyLocale, applyReportingCurrency } from "../i18n";
import type { CryptoOrder, StockOrder } from "../types/api";
import CryptoCandlestickChart from "./CryptoCandlestickChart.vue";

const points: NormalizedCandlestickChartPoint[] = [
  {
    date: "2026-07-09",
    open: 68000,
    high: 70000,
    low: 67000,
    close: 69000,
  },
  {
    date: "2026-07-10",
    open: 69000,
    high: 72000,
    low: 68500,
    close: 71000,
  },
];
const operations: CryptoOrder[] = [
  {
    id: "btc-buy",
    trade_date: "2026-07-10",
    settlement_date: null,
    quantity: 0.001,
    net_amount: 71.25,
    fee: 0.25,
    account_id: "00000000-0000-0000-0000-000000000001",
    account_name: "KrakenPro",
    platform: "KrakenPro",
    operation_type: "buy",
    cash_flow_type: "none",
    symbol: "BTC",
    asset_name: "Bitcoin",
    unit_price: 71000,
    currency: "EUR",
    base_currency: "EUR",
    base_unit_price: 71000,
    base_net_amount: 71.25,
    base_fee: 0.25,
    fx_rate_to_base: 1,
    fx_rate_date: "2026-07-10",
    fx_source: "identity",
    market: "",
    provider_operation_type: "Compra",
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
      trade_date: "2026-07-09",
      operation_type: "sell" as const,
      cash_flow_type: "none" as const,
      provider_operation_type: "Venta",
      unit_price: 69000,
      base_unit_price: 69000,
    };
    const earlyBuyOperation = {
      ...operations[0],
      id: "btc-buy-early",
      trade_date: "2026-07-09",
      unit_price: 69000,
      base_unit_price: 69000,
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
      quantity: 0.002,
      net_amount: 142.5,
      fee: 0.5,
      base_net_amount: 142.5,
      base_fee: 0.5,
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
      trade_date: "2025-02-03",
      settlement_date: null,
      quantity: 3,
      net_amount: 34.07,
      fee: 0,
      account_id: "00000000-0000-0000-0000-000000000001",
      account_name: "Trade Republic",
      platform: "Trade Republic",
      operation_type: "buy",
      cash_flow_type: "none",
      isin: "CNE100000296",
      asset_name: "BYD",
      unit_price: 34.07 / 3,
      currency: "EUR",
      base_currency: "EUR",
      base_unit_price: 34.07 / 3,
      base_net_amount: 34.07,
      base_fee: 0,
      fx_rate_to_base: 1,
      fx_rate_date: "2025-02-03",
      fx_source: "identity",
      market: "",
      provider_operation_type: "Compra",
      is_saveback: false,
      chartAdjustment: {
        id: "byd-pre-june-10-2025-split-3-to-1",
        label: "Split BYD 3:1",
      },
    } as StockOrder & {
      chartAdjustment: { id: string; label: string };
    };
    const bydPoints: NormalizedCandlestickChartPoint[] = [
      {
        date: "2025-02-03",
        open: 11,
        high: 11.5,
        low: 10.9,
        close: 11.2,
      },
      {
        date: "2025-02-04",
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
