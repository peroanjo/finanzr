import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import MonthlyVariationChart from "./MonthlyVariationChart.vue";

vi.mock("chart.js", () => ({
  Chart: class {
    static register() {}
    width = 300;
    scales = { x: { getValueForPixel: (x: number) => Math.floor(x / 100) } };
    update() {}
    destroy() {}
  },
  BarController: {},
  BarElement: {},
  CategoryScale: {},
  LinearScale: {},
  Tooltip: {},
}));

const props = {
  labels: ["oct 26", "nov 26", "dic 26"],
  values: [-250, 0, 1500],
  label: "Monthly change",
  range: { min: -250, max: 1800 },
  selectedIndex: 0,
  selectedMonth: "octubre de 2026",
};

describe("MonthlyVariationChart", () => {
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
