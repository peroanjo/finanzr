import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AppShell from "./AppShell.vue";
import { i18n, registerMessages } from "../i18n";
import { coreMessages } from "../i18n/coreMessages";

registerMessages(coreMessages);

const storage = new Map<string, string>();
vi.stubGlobal("localStorage", {
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
});

vi.mock("vue-router", () => ({
  useRoute: () => ({
    meta: { titleKey: "navigation.overview" },
    fullPath: "/",
  }),
  useRouter: () => ({ push: vi.fn() }),
}));

const stubs = {
  RouterLink: { template: "<a><slot /></a>" },
  RouterView: { template: "<div />" },
  NavIcon: { template: "<svg />" },
};

describe("AppShell", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    localStorage.setItem("finanzr-theme", "light");
    i18n.global.locale.value = "es-ES";
  });

  it("collapses navigation and preserves the preference", async () => {
    const wrapper = mount(AppShell, { global: { stubs } });
    await flushPromises();

    const toggle = wrapper.get(".sidebar-collapse-button");
    expect(toggle.attributes("aria-expanded")).toBe("true");

    await toggle.trigger("click");

    expect(wrapper.get(".app-shell").classes()).toContain("sidebar-collapsed");
    expect(toggle.attributes("aria-expanded")).toBe("false");
    expect(localStorage.getItem("finanzr-sidebar-collapsed")).toBe("true");
  });

  it("organizes navigation by accounts, investments, and tools", async () => {
    const wrapper = mount(AppShell, { global: { stubs } });
    await flushPromises();

    expect(wrapper.get(".app-nav-primary").text()).toBe("Resumen");
    expect(
      wrapper.findAll(".app-nav-group-label").map((label) => label.text()),
    ).toEqual(["Cuentas", "Inversiones", "Herramientas"]);
    expect(
      wrapper
        .findAll(".app-nav-group")[0]
        .findAll("a")
        .map((link) => link.text()),
    ).toEqual(["Cuentas de ahorro", "Cuentas de inversión"]);
    expect(
      wrapper
        .findAll(".app-nav-group")[1]
        .findAll("a")
        .map((link) => link.text()),
    ).toEqual([
      "Portfolio",
      "Crowdfunding",
      "Fondos",
      "Acciones y ETF",
      "Crypto",
    ]);
    expect(
      wrapper
        .findAll(".app-nav-group")[2]
        .findAll("a")
        .map((link) => link.text()),
    ).toEqual(["Divisas"]);
  });

  it("restores compact mode when the application mounts", async () => {
    localStorage.setItem("finanzr-sidebar-collapsed", "true");
    const wrapper = mount(AppShell, { global: { stubs } });
    await flushPromises();

    expect(wrapper.get(".app-shell").classes()).toContain("sidebar-collapsed");
    expect(wrapper.get(".sidebar-collapse-button").attributes("title")).toBe(
      "Expandir navegación",
    );
  });

  it("updates navigation and the title when switching to English", async () => {
    const wrapper = mount(AppShell, { global: { stubs } });
    i18n.global.locale.value = "en";
    await wrapper.vm.$nextTick();

    expect(wrapper.get(".app-topbar h1").text()).toBe("Overview");
    expect(wrapper.get(".app-nav").text()).toContain("Savings accounts");
    expect(wrapper.get(".app-nav").text()).toContain("Investment accounts");
    expect(wrapper.get(".app-nav").text()).toContain("Crowdfunding");
    expect(wrapper.get(".logout-button").text()).toContain("Sign out");
  });
});
