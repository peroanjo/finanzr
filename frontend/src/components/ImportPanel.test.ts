import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import ImportPanel from "./ImportPanel.vue";

vi.mock("../api/client", () => ({ api: vi.fn() }));

const apiMock = vi.mocked(api);

describe("ImportPanel", () => {
  beforeEach(() => {
    apiMock.mockReset();
    apiMock.mockResolvedValue({ imported: 2, skipped: 1 });
  });

  it("uses the fixed destination without rendering or loading a second account selector", async () => {
    const wrapper = mount(ImportPanel, {
      props: {
        endpoint: "/crypto-orders/upload-kraken-pro",
        accountsEndpoint: "/crypto-accounts",
        accountId: "7",
        hideAccountSelector: true,
        compact: true,
      },
    });

    expect(wrapper.find('[aria-label="Cuenta de destino"]').exists()).toBe(
      false,
    );
    expect(apiMock).not.toHaveBeenCalledWith("/crypto-accounts");

    const file = new File(["txid,pair"], "trades.csv", { type: "text/csv" });
    const input = wrapper.get('input[type="file"]');
    Object.defineProperty(input.element, "files", { value: [file] });
    await input.trigger("change");
    await wrapper.get("form").trigger("submit");

    expect(apiMock).toHaveBeenCalledTimes(1);
    const [endpoint, options] = apiMock.mock.calls[0];
    expect(endpoint).toBe("/crypto-orders/upload-kraken-pro");
    expect((options?.body as FormData).get("cuenta_id")).toBe("7");
  });
});
