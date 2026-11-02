import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import WorkspaceSharingBoard from "./WorkspaceSharingBoard.vue";
import type { WorkspaceShares } from "./workspaceSharing";
const data: WorkspaceShares = {
  resources: [
    {
      id: "available",
      kind: "account",
      name: "Synthetic savings",
      workspace_id: "private",
    },
    {
      id: "already",
      kind: "manual_asset",
      name: "Synthetic shared asset",
      workspace_id: "private",
    },
    {
      id: "native",
      kind: "account",
      name: "Synthetic common account",
      workspace_id: "common",
    },
  ],
  native: [
    {
      id: "native",
      kind: "account",
      name: "Synthetic common account",
      workspace_id: "common",
    },
  ],
  targets: [{ id: "common", name: "Synthetic common" }],
  incoming: [
    {
      id: "mine",
      kind: "manual_asset",
      resource_id: "already",
      name: "Synthetic shared asset",
      target_id: "common",
      target_name: "Synthetic common",
      access: "read",
    },
    {
      id: "other",
      kind: "real_estate",
      resource_id: "other-asset",
      name: "Synthetic other member property",
      target_id: "common",
      target_name: "Synthetic common",
      access: "edit",
    },
  ],
  outgoing: [
    {
      id: "mine",
      kind: "manual_asset",
      resource_id: "already",
      name: "Synthetic shared asset",
      target_id: "common",
      target_name: "Synthetic common",
      access: "read",
    },
  ],
};
function render(overrides = {}) {
  return mount(WorkspaceSharingBoard, {
    props: {
      data,
      workspaceId: "common",
      workspaceName: "Synthetic common",
      busy: false,
      error: "",
      status: "",
      ...overrides,
    },
  });
}
describe("WorkspaceSharingBoard", () => {
  it("separates available resources from original and incoming workspace resources", () => {
    const wrapper = render();
    expect(wrapper.findAll(".sharing-add")).toHaveLength(1);
    expect(wrapper.get(".sharing-add").text()).toContain("Synthetic savings");
    expect(wrapper.findAll(".sharing-included-row")).toHaveLength(3);
    expect(wrapper.findAll(".sharing-remove")).toHaveLength(1);
    expect(wrapper.text()).toContain("Compartido por otro miembro");
    expect(wrapper.text()).toContain("De este espacio");
  });
  it("shares all unshared resources even when the search hides them", async () => {
    const wrapper = render();
    await wrapper.get('input[type="search"]').setValue("other member");
    expect(wrapper.findAll(".sharing-add")).toHaveLength(0);
    await wrapper.get(".share-all").trigger("click");
    expect(wrapper.emitted("share")?.[0]).toEqual([
      [data.resources[0]],
      "read",
    ]);
  });
  it("revokes only your own grant and allows permission updates", async () => {
    const wrapper = render();
    await wrapper.get(".sharing-remove").trigger("click");
    expect(wrapper.emitted("revoke")?.[0]).toEqual([data.incoming[0]]);
    await wrapper.get(".sharing-included-row select").setValue("edit");
    expect(wrapper.emitted("permission")?.[0]).toEqual([
      data.incoming[0],
      "edit",
    ]);
  });
  it("disables sharing in an ineligible space or during a pending operation", () => {
    for (const wrapper of [
      render({ data: { ...data, targets: [] } }),
      render({ busy: true }),
    ]) {
      expect(wrapper.get(".share-all").attributes("disabled")).toBeDefined();
      expect(wrapper.get(".sharing-add").attributes("disabled")).toBeDefined();
      expect(
        wrapper.get(".sharing-controls select").attributes("disabled"),
      ).toBeDefined();
    }
  });
  it("keeps keyboard focus on a transferred resource after it changes columns", async () => {
    const wrapper = mount(WorkspaceSharingBoard, {
      attachTo: document.body,
      props: {
        data,
        workspaceId: "common",
        workspaceName: "Synthetic common",
        busy: false,
        error: "",
        status: "",
      },
    });
    const add = wrapper.get(".sharing-add");
    (add.element as HTMLButtonElement).focus();
    await add.trigger("click");
    await wrapper.setProps({ busy: true });
    const share = {
      id: "added",
      kind: "account",
      resource_id: "available",
      name: "Synthetic savings",
      target_id: "common",
      target_name: "Synthetic common",
      access: "read",
    };
    await wrapper.setProps({
      data: {
        ...data,
        incoming: [...data.incoming, share],
        outgoing: [...data.outgoing, share],
      },
      busy: false,
    });
    await flushPromises();
    expect(document.activeElement).toBe(
      wrapper.get('[aria-label="Dejar de compartir Synthetic savings"]')
        .element,
    );
    wrapper.unmount();
  });
});
