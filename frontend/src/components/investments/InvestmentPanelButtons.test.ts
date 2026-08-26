import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import InvestmentAddAssetButton from "./InvestmentAddAssetButton.vue";
import InvestmentCollapseButton from "./InvestmentCollapseButton.vue";

describe("shared investment panel buttons", () => {
  it("renders the labelled SVG add asset action", async () => {
    const wrapper = mount(InvestmentAddAssetButton, {
      props: { label: "Añadir activo" },
    });

    expect(wrapper.text()).toBe("Añadir activo");
    expect(wrapper.attributes("aria-label")).toBe("Añadir activo");
    expect(wrapper.get("svg path").attributes("d")).toBe("M10 4v12M4 10h12");

    await wrapper.trigger("click");
    expect(wrapper.emitted("add")).toHaveLength(1);
  });

  it("reflects the expanded state and emits toggle", async () => {
    const wrapper = mount(InvestmentCollapseButton, {
      props: {
        collapsed: false,
        controls: "positions-content",
        label: "Contraer posiciones",
      },
    });

    expect(wrapper.attributes("aria-expanded")).toBe("true");
    expect(wrapper.attributes("aria-controls")).toBe("positions-content");
    expect(wrapper.get("svg").attributes("data-direction")).toBe("up");

    await wrapper.trigger("click");
    expect(wrapper.emitted("toggle")).toHaveLength(1);
  });
});
