import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { i18n } from "../../i18n";
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

beforeEach(() => {
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
    expect(wrapper.text()).toContain("Crear espacio compartido");
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
});
