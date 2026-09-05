import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SettingsInstallationPreferencesPanel from "./SettingsInstallationPreferencesPanel.vue";
import { i18n, registerMessages } from "../../i18n";
import { coreMessages } from "../../i18n/coreMessages";

registerMessages(coreMessages);

const locales = [
  { code: "es-ES" as const, label: "Español" },
  { code: "en" as const, label: "English" },
];

describe("SettingsInstallationPreferencesPanel", () => {
  it("emits installation language changes from the local draft", async () => {
    const wrapper = mount(SettingsInstallationPreferencesPanel, {
      props: {
        mode: "installation",
        canAdminister: true,
        supportedLocales: locales,
        installationLanguage: "es-ES",
        installationBusy: false,
        installationError: "",
        installationSuccess: "",
      },
      global: { plugins: [i18n] },
    });

    await wrapper.find('input[value="en"]').setValue();
    await wrapper.get("form").trigger("submit");
    expect(wrapper.emitted("saveInstallationLanguage")?.[0]).toEqual(["en"]);
  });

  it("emits crowdfunding tax updates and gates the editor for non-admins", async () => {
    const wrapper = mount(SettingsInstallationPreferencesPanel, {
      props: {
        mode: "crowdfunding",
        canAdminister: true,
        defaultCrowdfundingTaxRate: 19,
        crowdfundingBusy: false,
        crowdfundingError: "",
        crowdfundingSuccess: "",
      },
      global: { plugins: [i18n] },
    });

    await wrapper.get(".tax-rate-field input").setValue("21.5");
    await wrapper.get("form").trigger("submit");
    expect(wrapper.emitted("saveCrowdfundingTax")?.[0]).toEqual([21.5]);

    await wrapper.setProps({ canAdminister: false });
    expect(wrapper.get(".tax-rate-field input").attributes("disabled")).toBe("");
    expect(wrapper.find(".withholding-form-row button").exists()).toBe(false);
  });
});
