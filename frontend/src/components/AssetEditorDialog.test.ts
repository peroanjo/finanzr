import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import AssetEditorDialog from "./AssetEditorDialog.vue";
import type { AssetEditorHandle } from "./assetEditor";
import type { CryptoInstrument, StockInstrument } from "../types/api";

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
      id: "00000000-0000-0000-0000-000000000012",
      kind: "crypto",
      name: "Ethereum",
      quote_currency: "EUR",
      identifiers: [
        {
          scheme: "crypto_symbol",
          value: "ETH",
          venue: "",
          is_primary: true,
        },
        { scheme: "yahoo", value: "ETH-EUR", venue: "", is_primary: true },
      ],
      asset_class: null,
      subtype: null,
      is_active: true,
    } satisfies CryptoInstrument);
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
          name: "Ethereum",
          quote_currency: "EUR",
          identifiers: [
            {
              scheme: "crypto_symbol",
              value: "ETH",
              venue: "",
              is_primary: true,
            },
            { scheme: "yahoo", value: "ETH-EUR", venue: "", is_primary: true },
          ],
          asset_class: null,
          subtype: null,
          is_active: true,
        }),
      }),
    );
  });

  it("allows selecting a stock and editing its ticker", async () => {
    const assets: StockInstrument[] = [
      {
        id: "00000000-0000-0000-0000-000000000010",
        kind: "stock" as const,
        name: "NVIDIA",
        quote_currency: "EUR",
        identifiers: [
          {
            scheme: "isin" as const,
            value: "US67066G1040",
            venue: "",
            is_primary: true,
          },
          {
            scheme: "yahoo" as const,
            value: "NVDA",
            venue: "",
            is_primary: true,
          },
        ],
        asset_class: null,
        subtype: null,
        is_active: true,
      },
      {
        id: "00000000-0000-0000-0000-000000000011",
        kind: "stock" as const,
        name: "Apple",
        quote_currency: "EUR",
        identifiers: [
          {
            scheme: "isin" as const,
            value: "US0378331005",
            venue: "",
            is_primary: false,
          },
          {
            scheme: "yahoo" as const,
            value: "AAPL",
            venue: "NASDAQ",
            is_primary: false,
          },
          {
            scheme: "yahoo" as const,
            value: "AAPL.MC",
            venue: "BME",
            is_primary: true,
          },
        ],
        asset_class: null,
        subtype: null,
        is_active: true,
      },
    ];
    apiMock.mockResolvedValue({
      ...assets[1],
      identifiers: [
        ...assets[1].identifiers.slice(0, 1),
        {
          scheme: "yahoo",
          value: "AAPL",
          venue: "NASDAQ",
          is_primary: false,
        },
        {
          scheme: "yahoo",
          value: "APC.F",
          venue: "BME",
          is_primary: true,
        },
      ],
    } satisfies StockInstrument);
    const wrapper = mount(AssetEditorDialog, {
      props: { kind: "stock", assets },
    });

    (wrapper.vm as unknown as AssetEditorHandle).openEdit(assets[0]);
    await wrapper.vm.$nextTick();
    await wrapper.get("select").setValue(assets[1].id);
    const inputs = wrapper.findAll("input");
    expect((inputs[0].element as HTMLInputElement).value).toBe("Apple");
    await inputs[1].setValue("APC.F");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/stocks/00000000-0000-0000-0000-000000000011",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          name: "Apple",
          quote_currency: "EUR",
          identifiers: [
            {
              scheme: "isin",
              value: "US0378331005",
              venue: "",
              is_primary: false,
            },
            {
              scheme: "yahoo",
              value: "AAPL",
              venue: "NASDAQ",
              is_primary: false,
            },
            {
              scheme: "yahoo",
              value: "APC.F",
              venue: "BME",
              is_primary: true,
            },
          ],
          asset_class: null,
          subtype: null,
          is_active: true,
        }),
      }),
    );
  });

  it("keeps the ordinally selected Yahoo feed and identifier flags on a name-only edit", async () => {
    const asset: StockInstrument = {
      id: "00000000-0000-0000-0000-000000000014",
      kind: "stock",
      name: "Case-sensitive stock",
      quote_currency: "EUR",
      identifiers: [
        {
          scheme: "isin",
          value: "ORDINAL-001",
          venue: "",
          is_primary: false,
        },
        {
          scheme: "yahoo",
          value: "Z.MC",
          venue: "BME",
          is_primary: false,
        },
        {
          scheme: "yahoo",
          value: "a.MC",
          venue: "BME",
          is_primary: false,
        },
      ],
      asset_class: null,
      subtype: null,
      is_active: true,
    };
    apiMock.mockResolvedValue({ ...asset, name: "Renamed stock" });
    const wrapper = mount(AssetEditorDialog, {
      props: { kind: "stock", assets: [asset] },
    });

    (wrapper.vm as unknown as AssetEditorHandle).openEdit(asset);
    await wrapper.vm.$nextTick();
    const inputs = wrapper.findAll("input");
    expect((inputs[1].element as HTMLInputElement).value).toBe("Z.MC");
    await inputs[0].setValue("Renamed stock");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/stocks/00000000-0000-0000-0000-000000000014",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          name: "Renamed stock",
          quote_currency: "EUR",
          identifiers: asset.identifiers,
          asset_class: null,
          subtype: null,
          is_active: true,
        }),
      }),
    );
  });
});
