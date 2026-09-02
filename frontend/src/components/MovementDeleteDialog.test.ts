import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import type { FundOrder } from "../types/api";
import MovementDeleteDialog from "./MovementDeleteDialog.vue";

vi.mock("../api/client", () => ({ api: vi.fn() }));

const apiMock = vi.mocked(api);

describe("MovementDeleteDialog", () => {
  beforeEach(() => {
    apiMock.mockReset();
    apiMock.mockResolvedValue({ ok: true });
    HTMLDialogElement.prototype.showModal = vi.fn();
    HTMLDialogElement.prototype.close = vi.fn();
  });

  it("scopes deletion by the movement account UUID", async () => {
    const wrapper = mount(MovementDeleteDialog, { props: { kind: "fund" } });
    const movement = {
      operacion_id: "provider/id",
      cuenta_id: "12345678-1234-5678-1234-567812345678",
      nombre_fondo: "Synthetic fund",
      tipo_operacion: "SUSCRIPCION",
    } as FundOrder;
    (wrapper.vm as unknown as { open(value: FundOrder): void }).open(movement);

    await wrapper.get("form").trigger("submit");

    expect(apiMock).toHaveBeenCalledWith(
      "/orders/provider%2Fid?account_id=12345678-1234-5678-1234-567812345678",
      { method: "DELETE" },
    );
  });
});
