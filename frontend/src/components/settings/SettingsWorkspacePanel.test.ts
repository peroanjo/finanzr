import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { i18n } from "../../i18n";
import { useSessionStore } from "../../stores/session";
import type { UserSession } from "../../types/api";
import { api } from "../../api/client";
import SettingsWorkspacePanel from "./SettingsWorkspacePanel.vue";

vi.mock("../../api/client", () => ({
  api: vi.fn(),
  json: (method: string, body: unknown) => ({
    method,
    body: JSON.stringify(body),
  }),
  setWorkspaceContext: vi.fn(),
}));
const mockApi = vi.mocked(api);
const settings = {
  id: "shared-1",
  name: "Synthetic common",
  is_personal: false,
  role: "owner",
  members: [
    {
      id: "member-1",
      name: "Synthetic A",
      email: "a@example.com",
      role: "owner",
      is_self: true,
    },
  ],
  invitations: [],
};
const shareData = {
  resources: [
    {
      kind: "account",
      id: "account-1",
      name: "Synthetic savings",
      workspace_id: "private-1",
    },
  ],
  targets: [{ id: "shared-1", name: "Synthetic common" }],
  outgoing: [
    {
      id: "grant-1",
      name: "Synthetic savings",
      target_name: "Synthetic common",
      access: "read",
    },
  ],
  incoming: [],
};
function render() {
  return mount(SettingsWorkspacePanel, { global: { plugins: [i18n] } });
}

const userSession = (id: string): UserSession => ({
  id: "synthetic-user",
  email: "a@example.com",
  display_name: "Synthetic A",
  role: "user",
  active_workspace_id: id,
  language: "es-ES",
  preferred_language: "es-ES",
  default_language: "es-ES",
  workspaces: [
    {
      id: "private-1",
      name: "Synthetic private",
      slug: "private",
      base_currency: "EUR",
      role: "owner",
      is_shared: false,
    },
    {
      id: "shared-1",
      name: "Synthetic common",
      slug: "shared",
      base_currency: "EUR",
      role: "editor",
      is_shared: true,
    },
  ],
});
beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (
    this: HTMLDialogElement,
  ) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
  });
  const storage = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
  });
  setActivePinia(createPinia());
  i18n.global.locale.value = "es-ES";
  vi.clearAllMocks();
  mockApi.mockImplementation(async (path) =>
    path === "/workspaces/settings"
      ? settings
      : path === "/workspaces/shares"
        ? shareData
        : undefined,
  );
});

describe("SettingsWorkspacePanel", () => {
  it("shows members, original-resource sharing and explicit permissions", async () => {
    const wrapper = render();
    await flushPromises();
    expect(wrapper.text()).toContain("Synthetic A");
    expect(wrapper.text()).toContain("Compartir cuentas y activos");
    expect(wrapper.text()).toContain("registro original sin copiarlo");
    const form = wrapper
      .findAll("form")
      .find((item) => item.text().includes("Cuenta o activo"))!;
    const selects = form.findAll("select");
    await selects[0].setValue("account:account-1");
    await selects[1].setValue("shared-1");
    await selects[2].setValue("edit");
    await form.trigger("submit");
    await flushPromises();
    expect(mockApi).toHaveBeenCalledWith(
      "/workspaces/shares",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          kind: "account",
          resource_id: "account-1",
          target_id: "shared-1",
          access: "edit",
        }),
      }),
    );
    wrapper.unmount();
  });
  it("creates email-bound invitations and displays the private acceptance code", async () => {
    mockApi.mockImplementation(async (path) =>
      path === "/workspaces/settings"
        ? settings
        : path === "/workspaces/shares"
          ? shareData
          : { token: "synthetic-invitation-code" },
    );
    const wrapper = render();
    await flushPromises();
    const form = wrapper
      .findAll("form")
      .find((item) => item.text().includes("Invitar por correo"))!;
    await form.get("input").setValue("b@example.com");
    await form.trigger("submit");
    await flushPromises();
    expect(wrapper.get(".invitation-code").text()).toBe(
      "synthetic-invitation-code",
    );
    expect(wrapper.text()).toContain("solo puede aceptarlo ese correo");
    wrapper.unmount();
  });
  it("hides invitation and member management for personal spaces", async () => {
    mockApi.mockImplementation(async (path) =>
      path === "/workspaces/settings"
        ? { ...settings, is_personal: true }
        : shareData,
    );
    const wrapper = render();
    await flushPromises();
    expect(wrapper.find('input[type="email"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain("Archivar espacio");
    expect(wrapper.text()).toContain("Crear espacio");
    wrapper.unmount();
  });
  it("reports failures without displaying data from a failed load", async () => {
    mockApi.mockRejectedValue(new Error("Synthetic permissions failure"));
    const wrapper = render();
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe(
      "Synthetic permissions failure",
    );
    expect(wrapper.text()).not.toContain("Synthetic savings");
    wrapper.unmount();
  });
  it.each([
    { personal: true, members: 1, label: "Privado", className: "private" },
    { personal: false, members: 1, label: "Privado", className: "private" },
    { personal: false, members: 2, label: "Compartido", className: "shared" },
  ])(
    "labels visibility by actual members: $members / personal=$personal",
    async ({ personal, members, label, className }) => {
      mockApi.mockImplementation(async (path) =>
        path === "/workspaces/settings"
          ? {
              ...settings,
              is_personal: personal,
              members: Array.from({ length: members }, (_, index) => ({
                ...settings.members[0],
                id: `member-${index}`,
                is_self: index === 0,
              })),
              invitations: [
                { id: "pending", email: "pending@example.com", role: "viewer" },
              ],
            }
          : shareData,
      );
      const wrapper = render();
      await flushPromises();
      const badge = wrapper.get(".workspace-heading .workspace-visibility");
      expect(badge.text()).toBe(label);
      expect(badge.classes()).toContain(className);
      wrapper.unmount();
    },
  );
  it("selects the workspace being configured and reloads its settings", async () => {
    const session = useSessionStore();
    session.user = userSession("private-1");
    let active = "private-1";
    mockApi.mockImplementation(async (path) => {
      if (path === "/workspaces/current") {
        active = "shared-1";
        return userSession(active);
      }
      return path === "/workspaces/settings"
        ? { ...settings, id: active }
        : shareData;
    });
    const wrapper = render();
    await flushPromises();
    const selector = wrapper.get(".workspace-selection select");
    expect(selector.text()).toContain("Synthetic private · Privado");
    expect(selector.text()).toContain("Synthetic common · Compartido");
    await selector.setValue("shared-1");
    await flushPromises();
    expect(mockApi).toHaveBeenCalledWith(
      "/workspaces/current",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ workspace_id: "shared-1" }),
      }),
    );
    expect(session.user?.active_workspace_id).toBe("shared-1");
    expect((selector.element as HTMLSelectElement).value).toBe("shared-1");
    wrapper.unmount();
  });

  it("opens a focused creation dialog and only creates after submission", async () => {
    mockApi.mockImplementation(async (path) =>
      path === "/workspaces"
        ? userSession("shared-1")
        : path === "/workspaces/settings"
          ? settings
          : shareData,
    );
    const wrapper = mount(SettingsWorkspacePanel, {
      attachTo: document.body,
      global: { plugins: [i18n] },
    });
    await flushPromises();
    expect(wrapper.get("dialog").attributes("open")).toBeUndefined();
    await wrapper.get(".workspace-actions button:first-child").trigger("click");
    await flushPromises();
    expect(wrapper.get("dialog").attributes("open")).toBeDefined();
    expect(wrapper.get("dialog h3").text()).toBe("Crear espacio");
    expect(document.activeElement).toBe(wrapper.get("dialog input").element);
    expect(mockApi).not.toHaveBeenCalledWith("/workspaces", expect.anything());
    await wrapper.get("dialog input").setValue("  Synthetic household  ");
    await wrapper.get("dialog form").trigger("submit");
    await flushPromises();
    expect(mockApi).toHaveBeenCalledWith(
      "/workspaces",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ name: "Synthetic household" }),
      }),
    );
    expect(wrapper.get("dialog").attributes("open")).toBeUndefined();
    wrapper.unmount();
  });

  it("keeps failed invitation codes in the joining dialog and supports retry", async () => {
    let attempts = 0;
    mockApi.mockImplementation(async (path) => {
      if (path === "/workspaces/invitations/accept") {
        if (++attempts === 1) throw new Error("Synthetic invalid code");
        return userSession("shared-1");
      }
      return path === "/workspaces/settings" ? settings : shareData;
    });
    const wrapper = render();
    await flushPromises();
    await wrapper.get(".workspace-actions button:last-child").trigger("click");
    expect(wrapper.get("dialog h3").text()).toBe("Unirse a espacio");
    await wrapper.get("dialog input").setValue("  synthetic-code  ");
    await wrapper.get("dialog form").trigger("submit");
    await flushPromises();
    expect(wrapper.get('dialog [role="alert"]').text()).toBe(
      "Synthetic invalid code",
    );
    expect(wrapper.get("dialog").attributes("open")).toBeDefined();
    expect(
      (wrapper.get("dialog input").element as HTMLInputElement).value,
    ).toContain("synthetic-code");
    await wrapper.get("dialog form").trigger("submit");
    await flushPromises();
    expect(mockApi).toHaveBeenCalledWith(
      "/workspaces/invitations/accept",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ token: "synthetic-code" }),
      }),
    );
    expect(wrapper.get("dialog").attributes("open")).toBeUndefined();
    wrapper.unmount();
  });

  it("cancels without a request and contains Escape within the nested dialog", async () => {
    const wrapper = render();
    await flushPromises();
    await wrapper.get(".workspace-actions button:first-child").trigger("click");
    await wrapper.get("dialog input").setValue("Synthetic discarded name");
    const windowKeydown = vi.fn();
    window.addEventListener("keydown", windowKeydown);
    await wrapper.get("dialog").trigger("keydown", { key: "Escape" });
    expect(windowKeydown).not.toHaveBeenCalled();
    await wrapper.get("dialog").trigger("cancel");
    expect(wrapper.get("dialog").attributes("open")).toBeUndefined();
    expect(mockApi).not.toHaveBeenCalledWith("/workspaces", expect.anything());
    await wrapper.get(".workspace-actions button:last-child").trigger("click");
    expect(
      (wrapper.get("dialog input").element as HTMLInputElement).value,
    ).toBe("");
    window.removeEventListener("keydown", windowKeydown);
    wrapper.unmount();
  });
});
