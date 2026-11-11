import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import MonthlyVariationChart, {
  type MonthlyVariationSeries,
} from "./MonthlyVariationChart.vue";
import type { ChartConfiguration } from "chart.js";

const { recordOptions, recordPnl } = vi.hoisted(() => ({
  recordOptions: vi.fn(),
  recordPnl: vi.fn(),
}));

vi.mock("chart.js", () => ({
  Chart: class {
    static register() {}
    width = 300;
    height = 200;
    chartArea = { left: 20, right: 300, top: 10, bottom: 180 };
    scales = { x: { getValueForPixel: (x: number) => Math.floor(x / 100) } };
    data: ChartConfiguration<"bar">["data"];
    options: ChartConfiguration<"bar">["options"];
    constructor(_canvas: HTMLCanvasElement, config: ChartConfiguration<"bar">) {
      this.data = config.data;
      this.options = config.options;
      recordOptions(this.options);
    }
    update() {
      recordOptions(this.options);
      recordPnl(this.data.datasets.find(({ label }) => label === "P&L")?.data);
    }
    destroy() {}
  },
  BarController: {},
  BarElement: {},
  CategoryScale: {},
  LinearScale: {},
}));

const props = {
  labels: ["oct 26", "nov 26", "dic 26"],
  values: [-250, 0, 1500],
  label: "Monthly change",
  series: [
    { key: "savings", label: "Savings", values: [200, 100, 1200] },
    { key: "interest", label: "Interest", values: [15, 20, 40] },
    { key: "pnl", label: "P&L", values: [-465, -120, 260] },
  ] satisfies MonthlyVariationSeries[],
  selectedIndex: 0,
  selectedMonth: "octubre de 2026",
};

describe("MonthlyVariationChart", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("previews the hovered month without selecting it and clears the preview outside the plot", async () => {
    const wrapper = mount(MonthlyVariationChart, { props });
    const canvas = wrapper.get("canvas");
    vi.spyOn(canvas.element, "getBoundingClientRect").mockReturnValue(
      new DOMRect(0, 0, 300, 200),
    );
    for (const [clientX, clientY] of [
      [125, 65],
      [245, 80],
      [245, 190],
    ]) {
      canvas.element.dispatchEvent(
        Object.assign(
          new MouseEvent("pointermove", { bubbles: true, clientX, clientY }),
          { pointerType: "mouse" },
        ),
      );
    }
    expect(wrapper.emitted("preview")).toEqual([[1], [2], [null]]);
    expect(wrapper.emitted("select")).toBeUndefined();
    await canvas.trigger("pointerleave");
    expect(wrapper.emitted("preview")?.at(-1)).toEqual([null]);
    wrapper.unmount();
  });

  it("fits the axis to the visible positive and negative stacks", async () => {
    vi.stubGlobal("matchMedia", () => ({ matches: true }));
    const wrapper = mount(MonthlyVariationChart, { props });
    expect(recordOptions).toHaveBeenLastCalledWith(
      expect.objectContaining({
        scales: expect.objectContaining({
          y: expect.objectContaining({ stacked: true, min: -465, max: 1500 }),
        }),
      }),
    );
    await wrapper.setProps({
      series: props.series.slice(0, 2),
      values: [215, 120, 1240],
    });
    expect(recordOptions).toHaveBeenLastCalledWith(
      expect.objectContaining({
        scales: expect.objectContaining({
          y: expect.objectContaining({ stacked: true, min: 0, max: 1240 }),
        }),
      }),
    );
    expect(recordPnl).toHaveBeenLastCalledWith(undefined);
    wrapper.unmount();
  });

  it("retracts signed P&L values and reverses from the current frame", async () => {
    let frame: FrameRequestCallback | undefined;
    vi.stubGlobal("matchMedia", () => ({ matches: false }));
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      frame = callback;
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", () => {
      frame = undefined;
    });
    const now = vi.spyOn(performance, "now").mockReturnValue(1000);
    const wrapper = mount(MonthlyVariationChart, { props });

    const excluded = {
      series: props.series.slice(0, 2),
      values: [215, 120, 1240],
    };
    await wrapper.setProps(excluded);
    expect(recordPnl).toHaveBeenLastCalledWith([-465, -120, 260]);
    frame?.(1170);
    expect(recordPnl).toHaveBeenLastCalledWith([-232.5, -60, 130]);

    now.mockReturnValue(1170);
    await wrapper.setProps({ series: props.series, values: props.values });
    expect(recordPnl).toHaveBeenLastCalledWith([-232.5, -60, 130]);
    frame?.(1510);
    expect(recordPnl).toHaveBeenLastCalledWith([-465, -120, 260]);

    now.mockReturnValue(1510);
    await wrapper.setProps(excluded);
    frame?.(1850);
    expect(recordPnl).toHaveBeenLastCalledWith(undefined);
    wrapper.unmount();
  });
  it("announces the selected month and signed amount and supports arrow and end keys", async () => {
    const wrapper = mount(MonthlyVariationChart, { props });
    const chart = wrapper.get('[role="slider"]');
    expect(chart.attributes("aria-valuetext")).toMatch(/octubre de 2026.*−250/);

    await chart.trigger("keydown", { key: "ArrowLeft" });
    expect(wrapper.emitted("select")).toBeUndefined();
    await chart.trigger("keydown", { key: "ArrowRight" });
    await chart.trigger("keydown", { key: "End" });
    expect(wrapper.emitted("select")).toEqual([[1], [2]]);
    wrapper.unmount();
  });

  it("selects on a touch tap or horizontal drag and ignores vertical swipes", async () => {
    const wrapper = mount(MonthlyVariationChart, { props });
    const canvas = wrapper.get("canvas");
    vi.spyOn(canvas.element, "getBoundingClientRect").mockReturnValue(
      new DOMRect(0, 0, 300, 200),
    );
    async function touch(type: string, clientX: number, clientY: number) {
      canvas.element.dispatchEvent(
        Object.assign(
          new MouseEvent(type, { bubbles: true, clientX, clientY }),
          {
            pointerId: 1,
            pointerType: "touch",
            isPrimary: true,
          },
        ),
      );
      await nextTick();
    }

    await touch("pointerdown", 120, 20);
    await touch("pointermove", 124, 70);
    await touch("pointerup", 124, 70);
    expect(wrapper.emitted("select")).toBeUndefined();

    await touch("pointerdown", 120, 20);
    await touch("pointerup", 120, 20);
    expect(wrapper.emitted("select")).toEqual([[1]]);

    await touch("pointerdown", 25, 20);
    await touch("pointermove", 230, 23);
    expect(wrapper.emitted("select")?.at(-1)).toEqual([2]);
    wrapper.unmount();
  });
});
