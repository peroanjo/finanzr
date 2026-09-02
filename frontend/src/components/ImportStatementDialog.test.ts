import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ImportStatementDialog from "./ImportStatementDialog.vue";
import type { ImportStatementDialogHandle } from "./ImportStatementDialog.vue";

vi.mock("./ImportPanel.vue", () => ({
  default: {
    emits: ["imported"],
    template:
      '<button data-testid="complete-import" @click="$emit(\'imported\')">Completar</button>',
  },
}));

const props = {
  endpoint: "/stock-orders/upload-tr",
  accountsEndpoint: "/stock-accounts",
  accountId: "11111111-1111-4111-8111-111111111111",
  accountLabel: "Trade Republic",
  importerLabel: "Trade Republic Transactions",
  compatibility: "Compatible con CSV de Trade Republic.",
  accept: ".csv",
  fileHint: "CSV exportado desde la plataforma",
};

describe("ImportStatementDialog", () => {
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
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("opens as a modal, shows account context and closes from its header", async () => {
    const wrapper = mount(ImportStatementDialog, { props });
    (wrapper.vm as unknown as ImportStatementDialogHandle).open();

    const dialog = document.body.querySelector<HTMLDialogElement>(
      ".import-statement-dialog",
    );
    expect(dialog?.hasAttribute("open")).toBe(true);
    expect(dialog?.textContent).toContain("Trade Republic");
    expect(dialog?.textContent).toContain("Cuenta de destino");
    expect(dialog?.textContent).not.toContain("Importar en");
    expect(dialog?.textContent).toContain("Importador activo");
    expect(dialog?.textContent).toContain("Trade Republic Transactions");
    expect(dialog?.textContent).toContain("Procesamiento local y privado");

    document.body
      .querySelector<HTMLButtonElement>(".import-dialog-close")
      ?.click();
    expect(dialog?.hasAttribute("open")).toBe(false);
    wrapper.unmount();
  });

  it("forwards a completed import to the current portfolio view", async () => {
    const wrapper = mount(ImportStatementDialog, { props });
    document.body
      .querySelector<HTMLButtonElement>('[data-testid="complete-import"]')
      ?.click();

    expect(wrapper.emitted("imported")).toHaveLength(1);
    wrapper.unmount();
  });

  it("renders inside the themed application shell when it is available", () => {
    const shell = document.createElement("div");
    shell.className = "app-shell";
    shell.dataset.theme = "dark";
    document.body.append(shell);

    const wrapper = mount(ImportStatementDialog, { props });

    expect(shell.querySelector(".import-statement-dialog")).not.toBeNull();
    wrapper.unmount();
  });
});
