import { describe, expect, it } from "vitest";
import SettingsLanguagePanel from "./SettingsLanguagePanel.vue";
import { mountWithTestI18n } from "./testI18n";

describe("SettingsLanguagePanel", () => {
  it("shows the effective language and emits personal language intent", async () => {
    const wrapper = mountWithTestI18n(SettingsLanguagePanel, {
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
