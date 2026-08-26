import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsView from "./SettingsView.vue";
import { useSessionStore } from "../stores/session";
import { i18n, registerMessages } from "../i18n";
import { coreMessages } from "../i18n/coreMessages";

registerMessages(coreMessages);

const storage = new Map<string, string>();
vi.stubGlobal("localStorage", {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
});

const catalog = [
  {
    slug: "kraken_spot",
    display_name: "KrakenPro Spot Trades",
    target: "crypto_orders",
    target_label: "Crypto",
    description: "Importa compras y ventas spot.",
    source_instructions: "Exporta el informe Spot Trades.",
    input_kind: "records",
    accepted_extensions: [".csv"],
    required_fields: ["txid", "pair"],
    formats: [
      {
        extension: ".csv",
        label: "CSV de Spot Trades",
        description: "CSV UTF-8.",
      },
    ],
    fields: [
      {
        name: "txid",
        label: "ID de transacción",
        description: "Identificador único.",
        example: "THVRQM-6JXWD",
        required: true,
        position: null,
      },
      {
        name: "pair",
        label: "Par",
        description: "Par negociado.",
        example: "XBT/EUR",
        required: true,
        position: null,
      },
    ],
    rules: ["Solo se importan pares cotizados en EUR."],
  },
  {
    slug: "trade_republic",
    display_name: "Trade Republic Transactions",
    target: "stock_orders",
    target_label: "Acciones y ETF",
    description: "Importa compras y ventas de acciones.",
    source_instructions: "Exporta el historial de transacciones.",
    input_kind: "records",
    accepted_extensions: [".csv"],
    required_fields: ["transaction_id"],
    formats: [
      {
        extension: ".csv",
        label: "CSV de transacciones",
        description: "CSV UTF-8.",
      },
    ],
    fields: [
      {
        name: "transaction_id",
        label: "ID de transacción",
        description: "Identificador único.",
        example: "7f21c4",
        required: true,
        position: null,
      },
    ],
    rules: ["Se admiten activos STOCK y ETF."],
  },
];

describe("SettingsView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    useSessionStore().user = {
      id: "user-1",
      email: "admin@finanzr.local",
      display_name: "Admin",
      role: "admin",
      language: "es-ES",
      preferred_language: "es-ES",
      default_language: "es-ES",
      active_workspace_id: "workspace-1",
      workspaces: [
        {
          id: "workspace-1",
          name: "Personal",
          slug: "personal",
          base_currency: "EUR",
          role: "owner",
        },
      ],
    };
    localStorage.setItem("finanzr-language", "es-ES");
    i18n.global.locale.value = "es-ES";
  });

  it("shows the published contract for each importer", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => catalog,
    }));
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(SettingsView, {
      attachTo: document.body,
    });
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/importers",
      expect.any(Object),
    );
    expect(wrapper.get(".settings-primary button").text()).toContain(
      "Importadores",
    );
    expect(wrapper.findAll(".importer-group")).toHaveLength(2);
    expect(
      wrapper.findAll(".importer-group > header h3").map((item) => item.text()),
    ).toEqual(["Acciones y ETF", "Crypto"]);
    expect(wrapper.findAll(".importer-group > button")).toHaveLength(2);
    expect(wrapper.get(".importer-count").text()).toBe(
      "2 importadores activos",
    );
    expect(wrapper.find(".settings-primary footer").exists()).toBe(false);
    expect(wrapper.text()).toContain("KrakenPro Spot Trades");
    expect(wrapper.text()).toContain("CSV de Spot Trades");
    expect(wrapper.text()).toContain("ID de transacción");
    expect(wrapper.text()).toContain("Solo se importan pares cotizados en EUR");
    expect(wrapper.get(".fields-section header").text()).toContain(
      "2 campos · 2 obligatorios",
    );

    await wrapper.findAll(".importer-group > button")[0].trigger("click");
    expect(wrapper.get(".document-header h3").text()).toBe(
      "Trade Republic Transactions",
    );
    expect(wrapper.text()).toContain("Se admiten activos STOCK y ETF");

    await wrapper.get(".settings-modal-header button").trigger("click");
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("shows Account to admins and users, but not to Demo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => catalog,
      })),
    );

    const wrapper = mount(SettingsView);
    await flushPromises();
    expect(
      wrapper.findAll(".settings-primary > button").map((item) => item.text()),
    ).toEqual(
      expect.arrayContaining([
        expect.stringContaining("Importadores"),
        expect.stringContaining("Secciones"),
        expect.stringContaining("Interfaz"),
        expect.stringContaining("Cuenta"),
        expect.stringContaining("Administración"),
      ]),
    );

    const accountButton = wrapper
      .findAll(".settings-primary > button")
      .find((item) => item.text().includes("Cuenta"));
    await accountButton!.trigger("click");
    expect(wrapper.get(".account-document h3").text()).toBe("Tu cuenta");
    expect(wrapper.get(".account-document-header > span").text()).toBe(
      "Administrador",
    );
    expect(
      (wrapper.get('input[autocomplete="name"]').element as HTMLInputElement)
        .value,
    ).toBe("Admin");
    expect(
      (wrapper.get('input[type="email"]').element as HTMLInputElement).value,
    ).toBe("admin@finanzr.local");

    wrapper.unmount();
    const session = useSessionStore();
    session.user = { ...session.user!, role: "user" };
    const userWrapper = mount(SettingsView);
    await flushPromises();
    expect(userWrapper.text()).toContain("Correo y contraseña");
    expect(userWrapper.text()).not.toContain("Usuarios y accesos");
    userWrapper.unmount();

    session.user = { ...session.user!, role: "demo" };
    const demoWrapper = mount(SettingsView);
    await flushPromises();
    expect(demoWrapper.findAll(".settings-primary > button")).toHaveLength(3);
    expect(demoWrapper.text()).toContain("Interfaz");
    expect(demoWrapper.text()).toContain("Secciones");
    expect(demoWrapper.text()).not.toContain("Correo y contraseña");
  });

  it("shows Language inside Interface with flags and visual selection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => catalog,
      })),
    );
    const session = useSessionStore();
    const updateLanguage = vi
      .spyOn(session, "updateLanguage")
      .mockImplementation(async (language) => {
        session.user = {
          ...session.user!,
          language: language === "en" ? "en" : "es-ES",
          preferred_language: language,
        };
        i18n.global.locale.value = session.user.language;
        return session.user;
      });

    const wrapper = mount(SettingsView);
    await flushPromises();
    const interfaceButton = wrapper
      .findAll(".settings-primary > button")
      .find((item) => item.text().includes("Interfaz"));
    await interfaceButton!.trigger("click");

    expect(wrapper.get(".settings-secondary .active strong").text()).toBe(
      "Idioma",
    );
    expect(
      wrapper.findAll(".language-flag").map((item) => item.text()),
    ).toEqual(["🌐", "🇪🇸", "🇬🇧"]);
    expect(wrapper.get(".language-choice.selected").text()).toContain(
      "Español",
    );

    const english = wrapper
      .findAll(".language-choice")
      .find((item) => item.text().includes("English"));
    await english!.trigger("click");
    await flushPromises();

    expect(updateLanguage).toHaveBeenCalledWith("en");
    expect(wrapper.get(".effective-language strong").text()).toBe("English");
  });

  it("configures personal-income tax through Sections -> Crowdfunding -> Withholding tax", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (
        url.includes("/installation/preferences") &&
        init?.method === "PATCH"
      ) {
        const body = JSON.parse(String(init.body));
        return {
          ok: true,
          status: 200,
          json: async () => ({
            default_language: "es-ES",
            default_crowdfunding_tax_rate: body.default_crowdfunding_tax_rate,
            language: "es-ES",
          }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => catalog,
      };
    });
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(SettingsView);
    await flushPromises();

    const sectionsButton = wrapper
      .findAll(".settings-primary > button")
      .find((item) => item.text().includes("Secciones"));
    expect(sectionsButton).toBeDefined();
    await sectionsButton!.trigger("click");

    const crowdfundingButton = wrapper
      .findAll(".settings-secondary > button")
      .find((item) => item.text().includes("Crowdfunding"));
    await crowdfundingButton!.trigger("click");
    expect(wrapper.get(".settings-secondary .active strong").text()).toBe(
      "Crowdfunding",
    );

    // 3. Inspect the personal-income-tax document
    expect(wrapper.get(".interface-document-header h3").text()).toBe(
      "Retención IRPF",
    );
    expect(wrapper.get(".interface-document-header p").text()).toBe(
      "Crowdfunding",
    );
    expect(wrapper.get(".effective-language strong").text()).toBe("19 %");

    // 4. Update the withholding rate and submit
    const taxInput = wrapper.get<HTMLInputElement>(".tax-rate-field input");
    await taxInput.setValue("21.5");
    const taxForm = wrapper
      .findAll("form")
      .find((item) => item.text().includes("Retención IRPF"));
    await taxForm!.trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain(
      "Tipo de retención por defecto actualizado",
    );
    expect(useSessionStore().user?.default_crowdfunding_tax_rate).toBe(21.5);
  });

  it("supports listbox keyboard navigation and preserves focus after transfer", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => catalog,
      })),
    );
    const wrapper = mount(SettingsView, {
      attachTo: document.body,
    });
    await flushPromises();
    const sectionsButton = wrapper
      .findAll(".settings-primary > button")
      .find((item) => item.text().includes("Secciones"));
    await sectionsButton!.trigger("click");
    expect(wrapper.get(".settings-secondary .active strong").text()).toBe(
      "Resumen",
    );
    expect(wrapper.get(".settings-secondary .active small").text()).toBe(
      "Fuentes del resumen",
    );
    const available = wrapper
      .findAll('[role="listbox"]')[0]
      .findAll('[role="option"]');
    expect(available.length).toBeGreaterThan(3);

    await available[0].trigger("focus");
    await available[0].trigger("keydown", { key: "ArrowDown" });
    await flushPromises();
    expect(document.activeElement).toBe(available[1].element);
    await available[1].trigger("keydown", { key: "End" });
    await flushPromises();
    expect(document.activeElement).toBe(available.at(-1)!.element);
    await available.at(-1)!.trigger("keydown", { key: "Home" });
    await flushPromises();
    expect(document.activeElement).toBe(available[0].element);

    await available[0].trigger("click");
    const include = wrapper.find(
      '[aria-label="Incluir fuentes seleccionadas"]',
    );
    expect(include.attributes("disabled")).toBeUndefined();
    await include.trigger("click");
    await flushPromises();
    const included = wrapper
      .findAll('[role="listbox"]')[1]
      .findAll('[role="option"]');
    const moved = included.find((item) => item.text().includes("Fondos"));
    expect(document.activeElement).toBe(moved!.element);
    expect(wrapper.findAll("svg")).not.toHaveLength(0);
    wrapper.unmount();
  });
});
