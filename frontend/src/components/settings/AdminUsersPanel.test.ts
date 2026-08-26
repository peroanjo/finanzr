import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import AdminUsersPanel from "./AdminUsersPanel.vue";
import { i18n, registerMessages } from "../../i18n";
import { coreMessages } from "../../i18n/coreMessages";

registerMessages(coreMessages);

const rows = [
  {
    id: "admin-1",
    email: "admin@finanzr.local",
    display_name: "Admin",
    role: "admin",
    is_active: true,
    is_self: true,
    date_joined: "2026-01-01T10:00:00Z",
    last_login: "2026-07-31T10:00:00Z",
  },
  {
    id: "user-1",
    email: "user@finanzr.local",
    display_name: "Usuario",
    role: "user",
    is_active: false,
    is_self: false,
    date_joined: "2026-02-01T10:00:00Z",
    last_login: null,
  },
];

describe("AdminUsersPanel", () => {
  it("lists users and opens creation and deletion flows", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => rows,
      })),
    );
    i18n.global.locale.value = "es-ES";
    const wrapper = mount(AdminUsersPanel);
    await flushPromises();

    expect(wrapper.text()).toContain("2 usuarios registrados · 1 con acceso");
    expect(wrapper.text()).toContain("admin@finanzr.local");
    expect(wrapper.text()).toContain("user@finanzr.local");
    expect(wrapper.findAll(".admin-self-label")).toHaveLength(1);

    await wrapper.get(".admin-users-header > button").trigger("click");
    expect(wrapper.get(".admin-create-form").text()).toContain(
      "Crear una cuenta manualmente",
    );
    await wrapper.get(".admin-create-form header > button").trigger("click");
    await wrapper.get(".admin-user-actions .edit").trigger("click");
    expect(wrapper.get(".admin-create-form").text()).toContain(
      "Modificar user@finanzr.local",
    );
    expect(
      (
        wrapper.get('.admin-create-form input[type="email"]')
          .element as HTMLInputElement
      ).value,
    ).toBe("user@finanzr.local");
    expect(wrapper.get(".admin-create-form").text()).toContain(
      "Nueva contraseña (opcional)",
    );
    await wrapper.get(".admin-user-actions .delete").trigger("click");
    expect(wrapper.get(".admin-delete-confirm").text()).toContain(
      "user@finanzr.local",
    );
  });

  it("translates user administration into English", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => rows,
      })),
    );
    i18n.global.locale.value = "en";
    const wrapper = mount(AdminUsersPanel);
    await flushPromises();

    expect(wrapper.text()).toContain("2 registered users · 1 with access");
    expect(wrapper.get(".admin-users-header > button").text()).toBe(
      "+ Create account",
    );
    expect(wrapper.get(".admin-self-label").text()).toBe("Your account");
  });
});
