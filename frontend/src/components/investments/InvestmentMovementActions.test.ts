import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import InvestmentMovementActions from "./InvestmentMovementActions.vue";

describe("InvestmentMovementActions", () => {
  it("renders accessible SVG actions and emits edit and delete", async () => {
    const wrapper = mount(InvestmentMovementActions, {
      props: {
        editLabel: "Editar movimiento",
        deleteLabel: "Eliminar movimiento",
      },
    });

    const edit = wrapper.get('[aria-label="Editar movimiento"]');
    const remove = wrapper.get('[aria-label="Eliminar movimiento"]');

    expect(wrapper.text()).toBe("");
    expect(edit.find("svg").exists()).toBe(true);
    expect(remove.find("svg").exists()).toBe(true);
    expect(remove.classes()).toContain("delete-order");

    await edit.trigger("click");
    await remove.trigger("click");

    expect(wrapper.emitted("edit")).toHaveLength(1);
    expect(wrapper.emitted("delete")).toHaveLength(1);
  });
});
