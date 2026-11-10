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
  it("shows details only while a segment is hovered", async () => {
    const wrapper = mount(AllocationPie, { props: { items } });
    expect(wrapper.find(".allocation-pie-center").exists()).toBe(false);
    expect(wrapper.find(".allocation-pie-slice.active").exists()).toBe(false);
    const slice = wrapper.findAll(".allocation-pie-slice")[1];
    await slice.trigger("mouseenter");
    expect(wrapper.get(".allocation-pie-center").text()).toContain("Funds");
    expect(wrapper.get(".allocation-pie-center").text()).toContain("250,00");
    expect(wrapper.get(".allocation-pie-center").text()).toContain("25");
    expect(slice.classes()).toContain("active");
    await slice.trigger("mouseleave");
    expect(wrapper.find(".allocation-pie-center").exists()).toBe(false);
    expect(wrapper.find(".allocation-pie-slice.active").exists()).toBe(false);
  });

  it("supports legend focus and clears details on blur or removed categories", async () => {
    const wrapper = mount(AllocationPie, { props: { items } });
    const button = wrapper.findAll("button")[1];
    await button.trigger("focus");
    expect(button.attributes("aria-pressed")).toBe("true");
    await button.trigger("blur");
    expect(wrapper.find(".allocation-pie-center").exists()).toBe(false);
    await button.trigger("mouseenter");
    await button.trigger("mouseleave");
    expect(wrapper.find(".allocation-pie-slice.active").exists()).toBe(false);
    await button.trigger("focus");
    await wrapper.setProps({ items: [items[0]] });
    expect(wrapper.find(".allocation-pie-center").exists()).toBe(false);
    expect(wrapper.get("button").attributes("aria-pressed")).toBe("false");
  });

  it("draws both boundaries of a full ring for a single positive category", () => {
    const wrapper = mount(AllocationPie, {
      props: { items: [{ ...items[0], share: 1 }] },
    });
    const path = wrapper.get("path").attributes("d") ?? "";
    expect(path.match(/A 94 94/g)).toHaveLength(2);
    expect(path.match(/A 62 62/g)).toHaveLength(2);
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
