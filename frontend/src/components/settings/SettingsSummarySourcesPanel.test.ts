import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SettingsSummarySourcesPanel from "./SettingsSummarySourcesPanel.vue";
import { i18n, registerMessages } from "../../i18n";
import { coreMessages } from "../../i18n/coreMessages";

registerMessages(coreMessages);

const sourceKeys = [
  "savings",
  "manual_investments",
  "funds",
  "stocks",
  "crypto",
  "crowdfunding",
  "manual_assets",
] as const;

describe("SettingsSummarySourcesPanel", () => {
  it("transfers selected sources and emits the explicit save intent", async () => {
    const wrapper = mount(SettingsSummarySourcesPanel, {
      props: {
        summarySources: ["savings", "crowdfunding"],
        summarySourceKeys: [...sourceKeys],
        scopeLabel: "Installation",
        canManage: true,
        busy: false,
        error: "",
        success: "",
      },
      global: { plugins: [i18n] },
    });

    const available = wrapper.findAll('[role="option"]')[0];
    await available.trigger("click");
    await wrapper
      .find('[aria-label="Incluir fuentes seleccionadas"]')
      .trigger("click");
    expect(wrapper.emitted("update")?.[0]).toEqual([
      ["savings", "manual_investments", "crowdfunding"],
    ]);

    await wrapper.get(".summary-sources-save").trigger("click");
    expect(wrapper.emitted("save")?.[0]).toEqual([
      ["savings", "crowdfunding"],
    ]);
    await flushPromises();
  });

  it("keeps listbox navigation and save controls accessible", async () => {
    const wrapper = mount(SettingsSummarySourcesPanel, {
      props: {
        summarySources: ["savings"],
        summarySourceKeys: [...sourceKeys],
        scopeLabel: "Installation",
        canManage: true,
        busy: false,
        error: "",
        success: "",
      },
      attachTo: document.body,
      global: { plugins: [i18n] },
    });

    const available = wrapper.findAll('[role="listbox"]')[0].findAll('[role="option"]');
    await available[0].trigger("focus");
    await available[0].trigger("keydown", { key: "End" });
    await flushPromises();
    expect(document.activeElement).toBe(available.at(-1)!.element);
    expect(wrapper.get(".summary-sources-save").attributes("disabled")).toBeUndefined();
    wrapper.unmount();
  });
});
