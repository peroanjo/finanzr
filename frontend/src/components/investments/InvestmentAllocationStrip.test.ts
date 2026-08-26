import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import InvestmentAllocationStrip from "./InvestmentAllocationStrip.vue";

const item = {
  key: "fund-a",
  label: "Global fund",
  value: 750,
  share: 0.75,
  color: "#3ddc97",
};

const props = {
  items: [item],
  total: 750,
  accountLabel: "All accounts",
  title: "Market value distribution",
  barLabel: "Open fund positions by market value",
  emptyLabel: "No open positions",
  formatValue: (value: number) => `€${value}`,
  formatShare: (value: number) => `${value * 100}%`,
  segmentAria: (allocation: typeof item) =>
    `${allocation.label}: ${allocation.share * 100}%`,
};

describe("InvestmentAllocationStrip", () => {
  it("renders a keyboard-addressable segment with the supplied labels and formatters", () => {
    const wrapper = mount(InvestmentAllocationStrip, { props });

    expect(
      wrapper
        .get('[data-testid="fund-position-allocation"]')
        .attributes("aria-label"),
    ).toBe("Market value distribution · All accounts");
    const segment = wrapper.get(".fund-position-allocation-segment");
    expect(segment.attributes("role")).toBe("img");
    expect(segment.attributes("tabindex")).toBe("0");
    expect(segment.attributes("aria-label")).toBe("Global fund: 75%");
    expect(segment.attributes("style")).toContain("width: 75%");
    expect(wrapper.get(".fund-position-allocation-tooltip").text()).toBe(
      "Global fund€750 · 75%",
    );
  });

  it("renders the empty contract without a focusable segment", () => {
    const wrapper = mount(InvestmentAllocationStrip, {
      props: { ...props, items: [], total: 0 },
    });

    expect(wrapper.get(".fund-position-allocation-empty").text()).toBe(
      "No open positions",
    );
    expect(wrapper.findAll(".fund-position-allocation-segment")).toHaveLength(
      0,
    );
    expect(wrapper.find(".fund-position-allocation-total").exists()).toBe(
      false,
    );
  });
});
