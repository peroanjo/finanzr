import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { applyLocale } from "../i18n";
import AssetReturnToggle from "./AssetReturnToggle.vue";

describe("AssetReturnToggle", () => {
  it("switches between percentage and P&L with an accessible pressed state", async () => {
    const wrapper = mount(AssetReturnToggle, {
      props: { modelValue: "percent" },
    });

    expect(
      wrapper
        .get('[aria-label="Mostrar rendimiento porcentual"]')
        .attributes("aria-pressed"),
    ).toBe("true");
    await wrapper
      .get('[aria-label="Mostrar pérdidas y ganancias"]')
      .trigger("click");

    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual(["pnl"]);
  });

  it("translates its label and accessible controls to English", () => {
    applyLocale("en");
    const wrapper = mount(AssetReturnToggle, {
      props: { modelValue: "percent" },
    });

    expect(wrapper.text()).toContain("Return");
    expect(wrapper.get('[role="group"]').attributes("aria-label")).toBe(
      "Return format",
    );
    expect(wrapper.find('[aria-label="Show percentage return"]').exists()).toBe(
      true,
    );
  });
});
