import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LoginView from "./LoginView.vue";
import { i18n, registerMessages } from "../i18n";
import { coreMessages } from "../i18n/coreMessages";

registerMessages(coreMessages);

const storage = new Map<string, string>();
const sessionStorageValues = new Map<string, string>();
vi.stubGlobal("localStorage", {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
});
vi.stubGlobal("sessionStorage", {
  clear: () => sessionStorageValues.clear(),
  getItem: (key: string) => sessionStorageValues.get(key) ?? null,
  setItem: (key: string, value: string) => sessionStorageValues.set(key, value),
  removeItem: (key: string) => sessionStorageValues.delete(key),
});

const login = vi.fn();
const updateLanguage = vi.fn();
const push = vi.fn();

vi.mock("../stores/session", () => ({
  useSessionStore: () => ({ login, updateLanguage }),
}));
vi.mock("vue-router", () => ({
  useRouter: () => ({ push }),
}));

describe("LoginView", () => {
  beforeEach(() => {
    login.mockReset();
    updateLanguage.mockReset();
    push.mockReset();
    sessionStorage.clear();
    localStorage.setItem("finanzr-language", "es-ES");
    i18n.global.locale.value = "es-ES";
  });

  it("signs in and navigates to the overview", async () => {
    login.mockResolvedValue(undefined);
    const wrapper = mount(LoginView);

    await wrapper.get('input[type="email"]').setValue("persona@example.com");
    await wrapper.get('input[type="password"]').setValue("contraseña-segura");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(login).toHaveBeenCalledWith(
      "persona@example.com",
      "contraseña-segura",
    );
    expect(push).toHaveBeenCalledWith("/");
  });

  it("shows authentication errors without leaving the landing page", async () => {
    login.mockRejectedValue(new Error("Credenciales incorrectas"));
    const wrapper = mount(LoginView);

    await wrapper.get('input[type="email"]').setValue("persona@example.com");
    await wrapper.get('input[type="password"]').setValue("incorrecta");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toContain(
      "Credenciales incorrectas",
    );
    expect(push).not.toHaveBeenCalled();
  });

  it("allows choosing English before signing in", async () => {
    login.mockResolvedValue(undefined);
    updateLanguage.mockResolvedValue(undefined);
    const wrapper = mount(LoginView);

    await wrapper.get(".login-language-picker select").setValue("en");
    await flushPromises();

    expect(wrapper.get(".login-panel h2").text()).toBe("Enter your space");
    expect(wrapper.get(".login-submit").text()).toContain("Sign in to Finanzr");
    expect(localStorage.getItem("finanzr-language")).toBe("en");

    await wrapper.get('input[type="email"]').setValue("persona@example.com");
    await wrapper.get('input[type="password"]').setValue("contraseña-segura");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(updateLanguage).toHaveBeenCalledWith("en");
  });
});
