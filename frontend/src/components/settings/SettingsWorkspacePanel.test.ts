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
  it("shares an original resource into the workspace being configured", async () => {
    const data = structuredClone(shareData);
    mockApi.mockImplementation(async (path, init) => {
      if (path === "/workspaces/settings") return settings;
      if (path === "/workspaces/shares" && init?.method === "POST") {
        const shared = {
          id: "new-grant",
          kind: "account",
          resource_id: "account-1",
          name: "Synthetic savings",
          target_id: "shared-1",
          target_name: "Synthetic common",
          access: "edit",
        };
        data.incoming = [shared] as unknown as typeof data.incoming;
        data.outgoing = [shared];
        return shared;
      }
      return structuredClone(data);
    });
    const wrapper = render();
    await flushPromises();
    expect(wrapper.text()).toContain("Synthetic A");
    expect(wrapper.text()).toContain("Compartir cuentas y activos");
    await wrapper.get(".sharing-controls select").setValue("edit");
    await wrapper
      .get('.sharing-add[aria-label="Compartir Synthetic savings"]')
      .trigger("click");
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
    expect(wrapper.findAll(".sharing-add")).toHaveLength(0);
    expect(wrapper.get(".sharing-included-row").text()).toContain(
      "Synthetic savings",
    );
    wrapper.unmount();
  });

  it("shares all available resources without duplicating existing grants", async () => {
    const data = {
      ...structuredClone(shareData),
      resources: [
        ...shareData.resources,
        {
          kind: "manual_asset",
          id: "asset-2",
          name: "Synthetic asset",
          workspace_id: "private-1",
        },
      ],
      incoming: [] as Array<{
        id: string;
        kind: string;
        resource_id: string;
        name: string;
        target_id: string;
        target_name: string;
        access: string;
      }>,
      outgoing: [] as Array<{
        id: string;
        kind: string;
        resource_id: string;
        name: string;
        target_id: string;
        target_name: string;
        access: string;
      }>,
    };
    mockApi.mockImplementation(async (path, init) => {
      if (path === "/workspaces/settings") return settings;
      if (init?.method === "POST") {
        const request = JSON.parse(init.body as string);
        const grant = {
          id: request.resource_id,
          kind: request.kind,
          resource_id: request.resource_id,
          name: "Synthetic resource",
          target_id: "shared-1",
          target_name: "Synthetic common",
          access: request.access,
        };
        data.incoming.push(grant);
        data.outgoing.push(grant);
        return grant;
      }
      return structuredClone(data);
    });
    const wrapper = render();
    await flushPromises();
    await wrapper.get(".share-all").trigger("click");
    await flushPromises();
    expect(
      mockApi.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(2);
    expect(wrapper.findAll(".sharing-included-row")).toHaveLength(2);
    expect(wrapper.get('[role="status"].sharing-status').text()).toContain(
      "2 de 2",
    );
    expect(wrapper.get(".share-all").attributes("disabled")).toBeDefined();
    wrapper.unmount();
  });

  it("refreshes partial batch successes when a later resource cannot be shared", async () => {
    const data = {
      ...structuredClone(shareData),
      resources: [
        ...shareData.resources,
        {
          kind: "manual_asset",
          id: "asset-2",
          name: "Synthetic incompatible currency",
          workspace_id: "private-1",
        },
      ],
      incoming: [] as Array<Record<string, string>>,
    };
    mockApi.mockImplementation(async (path, init) => {
      if (path === "/workspaces/settings") return settings;
      if (init?.method === "POST") {
        const request = JSON.parse(init.body as string);
        if (request.resource_id === "asset-2")
          throw new Error("Synthetic currency mismatch");
        const grant = {
          id: "grant-1",
          kind: "account",
          resource_id: "account-1",
          name: "Synthetic savings",
          target_id: "shared-1",
          target_name: "Synthetic common",
          access: "read",
        };
        data.incoming.push(grant);
        return grant;
      }
      return structuredClone(data);
    });
    const wrapper = render();
    await flushPromises();
    await wrapper.get(".share-all").trigger("click");
    await flushPromises();
    expect(wrapper.get('.sharing-error[role="alert"]').text()).toContain(
      "Synthetic currency mismatch",
    );
    expect(wrapper.get(".sharing-status").text()).toContain("1 de 2");
    expect(wrapper.findAll(".sharing-add")).toHaveLength(1);
    expect(wrapper.findAll(".sharing-included-row")).toHaveLength(1);
    wrapper.unmount();
  });

  it("returns a revoked resource to the available column without deleting the original", async () => {
    const share = {
      id: "grant-1",
      kind: "account",
      resource_id: "account-1",
      name: "Synthetic savings",
      target_id: "shared-1",
      target_name: "Synthetic common",
      access: "read",
    };
    const data = {
      ...structuredClone(shareData),
      incoming: [share],
      outgoing: [share],
    };
    mockApi.mockImplementation(async (path, init) => {
      if (path === "/workspaces/settings") return settings;
      if (init?.method === "DELETE") {
        data.incoming = [];
        data.outgoing = [];
        return undefined;
      }
      return structuredClone(data);
    });
    const wrapper = render();
    await flushPromises();
    await wrapper.get(".sharing-remove").trigger("click");
    await flushPromises();
    expect(mockApi).toHaveBeenCalledWith("/workspaces/shares/grant-1", {
      method: "DELETE",
    });
    expect(wrapper.findAll(".sharing-included-row")).toHaveLength(0);
    expect(wrapper.get(".sharing-add").text()).toContain("Synthetic savings");
    expect(wrapper.get(".sharing-status").text()).toContain(
      "Se conserva el original",
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
      useSessionStore().user = userSession("shared-1");
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
      expect(
        wrapper.get(".workspace-selection-face .workspace-visibility").text(),
      ).toBe(label);
      expect(
        wrapper
          .get(".workspace-selection-face .workspace-visibility")
          .classes(),
      ).toContain(className);
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
