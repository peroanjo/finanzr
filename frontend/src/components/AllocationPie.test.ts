import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AllocationPie from "./AllocationPie.vue";

const items = [
  {
    key: "savings",
    label: "Savings",
    value: 750,
    share: 0.75,
    color: "#28aa88",
  },
  { key: "funds", label: "Funds", value: 250, share: 0.25, color: "#6699dd" },
];

describe("AllocationPie", () => {
  it("links legend selection to the highlighted slice", async () => {
    const wrapper = mount(AllocationPie, { props: { items } });
    expect(wrapper.findAll(".allocation-pie-slice")).toHaveLength(2);
    expect(wrapper.findAll("button")[0].attributes("aria-pressed")).toBe(
      "true",
    );
    await wrapper.findAll("button")[1].trigger("focus");
    expect(wrapper.findAll("button")[1].attributes("aria-pressed")).toBe(
      "true",
    );
    expect(wrapper.findAll(".allocation-pie-slice")[1].classes()).toContain(
      "active",
    );
    await wrapper.setProps({ items: [items[0]] });
    expect(wrapper.get("button").attributes("aria-pressed")).toBe("true");
  });

  it("draws a full circle for a single positive category", () => {
    const wrapper = mount(AllocationPie, {
      props: { items: [{ ...items[0], share: 1 }] },
    });
    const path = wrapper.get("path").attributes("d") ?? "";
    expect(path.match(/A 94 94/g)).toHaveLength(2);
    expect(path).not.toContain("NaN");
  });

  it("keeps zero and negative amounts in the legend without drawing misleading slices", () => {
    const wrapper = mount(AllocationPie, {
      props: {
        items: [
          { ...items[0], value: 0, share: 0 },
          { ...items[1], value: -250, share: 0 },
        ],
      },
    });
    expect(wrapper.find("svg").exists()).toBe(false);
    expect(wrapper.findAll("button")).toHaveLength(2);
    expect(
      wrapper
        .findAll("button")
        .every((button) => button.attributes("disabled") !== undefined),
    ).toBe(true);
    expect(wrapper.text()).toContain("-250");
  });
});
