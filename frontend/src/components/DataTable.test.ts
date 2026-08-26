import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { applyLocale } from "../i18n";
import DataTable from "./DataTable.vue";

describe("DataTable", () => {
  it("escapes user-controlled content through Vue interpolation", () => {
    const wrapper = mount(DataTable, {
      props: { rows: [{ nombre: "<img src=x onerror=alert(1)>" }] },
    });
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.text()).toContain("<img src=x onerror=alert(1)>");
  });

  it("uses the active locale for its default empty state", () => {
    applyLocale("en");
    const wrapper = mount(DataTable, { props: { rows: [] } });
    expect(wrapper.text()).toContain("There is no data yet.");
  });
});
