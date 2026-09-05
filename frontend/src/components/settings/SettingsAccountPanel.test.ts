import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SettingsAccountPanel from "./SettingsAccountPanel.vue";
import { i18n, registerMessages } from "../../i18n";
import { coreMessages } from "../../i18n/coreMessages";

registerMessages(coreMessages);

describe("SettingsAccountPanel", () => {
  it("keeps identity and password drafts local and emits typed save intents", async () => {
    const wrapper = mount(SettingsAccountPanel, {
      props: {
        initialDisplayName: "Synthetic User",
        initialEmail: "synthetic@example.test",
        roleLabel: "User",
        identityBusy: false,
        identityError: "",
        identitySuccess: "",
        passwordBusy: false,
        passwordError: "",
        passwordSuccess: "",
      },
      global: { plugins: [i18n] },
    });

    await wrapper.get('input[autocomplete="name"]').setValue("Updated User");
    await wrapper.get('input[type="email"]').setValue("updated@example.test");
    await wrapper
      .get('.account-form-card input[autocomplete="current-password"]')
      .setValue("current-secret");
    await wrapper.findAll("form")[0].trigger("submit");
    expect(wrapper.emitted("saveIdentity")?.[0]).toEqual([
      {
        displayName: "Updated User",
        email: "updated@example.test",
        password: "current-secret",
      },
    ]);

    const passwordInputs = wrapper.findAll(
      '.account-form-card input[autocomplete="current-password"]',
    );
    await passwordInputs[1].setValue("old-secret");
    await wrapper.get('input[autocomplete="new-password"]').setValue("new-secret-123");
    await wrapper
      .findAll('input[autocomplete="new-password"]')[1]
      .setValue("new-secret-123");
    await wrapper.findAll("form")[1].trigger("submit");
    expect(wrapper.emitted("savePassword")?.[0]).toEqual([
      {
        currentPassword: "old-secret",
        newPassword: "new-secret-123",
        confirmation: "new-secret-123",
      },
    ]);
  });

  it("clears password drafts after successful saves", async () => {
    const wrapper = mount(SettingsAccountPanel, {
      props: {
        initialDisplayName: "Synthetic User",
        initialEmail: "synthetic@example.test",
        roleLabel: "User",
        identityBusy: false,
        identityError: "",
        identitySuccess: "",
        passwordBusy: false,
        passwordError: "",
        passwordSuccess: "",
      },
      global: { plugins: [i18n] },
    });

    await wrapper.get('input[autocomplete="name"]').setValue("Updated User");
    await wrapper.get('.account-form-card input[autocomplete="current-password"]').setValue("secret");
    await wrapper.setProps({ identitySuccess: "Saved" });
    expect(
      (wrapper.get('.account-form-card input[type="password"]').element as HTMLInputElement)
        .value,
    ).toBe("");
  });
});
