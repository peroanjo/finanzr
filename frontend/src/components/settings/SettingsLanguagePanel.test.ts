import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SettingsLanguagePanel from "./SettingsLanguagePanel.vue";
import { i18n, registerMessages } from "../../i18n";
import { coreMessages } from "../../i18n/coreMessages";

registerMessages(coreMessages);

describe("SettingsLanguagePanel", () => {
  it("shows the effective language and emits personal language intent", async () => {
    const wrapper = mount(SettingsLanguagePanel, {
      props: {
        effectiveLanguage: "es-ES",
        effectiveLanguageName: "Español",
        effectiveLanguageFlag: "🇪🇸",
        preferredLanguage: "es-ES",
        canManage: true,
        canAdminister: false,
        languageBusy: false,
        languageError: "",
        languageSuccess: "",
        installationLanguage: "es-ES",
        supportedLocales: [{ code: "es-ES", label: "Español" }],
        installationBusy: false,
        installationError: "",
        installationSuccess: "",
      },
      global: { plugins: [i18n] },
    });

    expect(wrapper.get(".effective-language strong").text()).toBe("Español");
    const english = wrapper
      .findAll(".language-choice")
      .find((item) => item.text().includes("English"));
    await english!.trigger("click");
    expect(wrapper.emitted("saveLanguage")?.[0]).toEqual(["en"]);
    expect(wrapper.find(".installation-language-panel").exists()).toBe(false);
  });
});
