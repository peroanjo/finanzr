import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import AssetEditorDialog from "./AssetEditorDialog.vue";
import type { AssetEditorHandle } from "./assetEditor";

vi.mock("../api/client", () => ({
  api: vi.fn(),
  json: (method: string, body: unknown) => ({
    method,
    body: JSON.stringify(body),
  }),
}));

const apiMock = vi.mocked(api);

describe("AssetEditorDialog", () => {
  beforeEach(() => {
    HTMLDialogElement.prototype.showModal = vi.fn(function (
      this: HTMLDialogElement,
    ) {
      this.setAttribute("open", "");
    });
    HTMLDialogElement.prototype.close = vi.fn(function (
      this: HTMLDialogElement,
    ) {
      this.removeAttribute("open");
    });
    apiMock.mockReset();
  });

  it("creates a crypto asset with a symbol and ticker", async () => {
    apiMock.mockResolvedValue({
      symbol: "ETH",
      nombre: "Ethereum",
      ticker: "ETH-EUR",
    });
    const wrapper = mount(AssetEditorDialog, {
      props: { kind: "crypto", assets: [] },
    });

    (wrapper.vm as unknown as AssetEditorHandle).openCreate();
    await wrapper.vm.$nextTick();
    const inputs = wrapper.findAll("input");
    await inputs[0].setValue("eth");
    await inputs[1].setValue("Ethereum");
    await inputs[2].setValue("ETH-EUR");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/cryptos",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          nombre: "Ethereum",
          ticker: "ETH-EUR",
          symbol: "ETH",
        }),
      }),
    );
  });

  it("allows selecting a stock and editing its ticker", async () => {
    const assets = [
      { isin: "US67066G1040", nombre: "NVIDIA", ticker: "NVDA" },
      { isin: "US0378331005", nombre: "Apple", ticker: "AAPL" },
    ];
    apiMock.mockResolvedValue({ ...assets[1], ticker: "APC.F" });
    const wrapper = mount(AssetEditorDialog, {
      props: { kind: "stock", assets },
    });

    (wrapper.vm as unknown as AssetEditorHandle).openEdit(assets[0]);
    await wrapper.vm.$nextTick();
    await wrapper.get("select").setValue("US0378331005");
    const inputs = wrapper.findAll("input");
    expect((inputs[0].element as HTMLInputElement).value).toBe("Apple");
    await inputs[1].setValue("APC.F");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/stocks/US0378331005",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ nombre: "Apple", ticker: "APC.F" }),
      }),
    );
  });
});
