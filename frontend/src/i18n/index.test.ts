import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  applyLocale,
  applyReportingCurrency,
  DEFAULT_LOCALE,
  i18n,
  normalizeLocale,
  reportingCurrency,
  SOURCE_LOCALE,
  supportedLocales,
} from "./index";

describe("i18n", () => {
  const storage = new Map<string, string>();

  beforeEach(() => {
    storage.clear();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      clear: () => storage.clear(),
    });
    applyReportingCurrency("EUR");
  });

  it("normaliza únicamente los idiomas compatibles", () => {
    expect(normalizeLocale("es-MX")).toBe("es-ES");
    expect(normalizeLocale("en-GB")).toBe("en");
    expect(normalizeLocale("fr")).toBeNull();
  });

  it("aplica y conserva el idioma elegido", () => {
    applyLocale("en");

    expect(i18n.global.locale.value).toBe("en");
    expect(document.documentElement.lang).toBe("en");
    expect(localStorage.getItem("finanzr-language")).toBe("en");
  });

  it("usa inglés como fuente y fallback sin cambiar el predeterminado español", () => {
    expect(SOURCE_LOCALE).toBe("en");
    expect(DEFAULT_LOCALE).toBe("es-ES");
    expect(i18n.global.fallbackLocale.value).toBe("en");
    expect(supportedLocales).toEqual([
      { code: "en", label: "English" },
      { code: "es-ES", label: "Español" },
    ]);
  });

  it("resuelve desde el catálogo fuente inglés una clave ausente en español", () => {
    const warning = vi
      .spyOn(console, "warn")
      .mockImplementation(() => undefined);
    i18n.global.mergeLocaleMessage("en", {
      sourceContractTest: { englishOnly: "English source value" },
    });
    applyLocale("es-ES", false);

    expect(i18n.global.t("sourceContractTest.englishOnly")).toBe(
      "English source value",
    );
    warning.mockRestore();
  });

  it.each(["EUR", "USD", "GBP"])(
    "formatea importes con la moneda base %s",
    (currency) => {
      applyLocale("es-ES", false);
      applyReportingCurrency(currency);

      expect(reportingCurrency.value).toBe(currency);
      expect(i18n.global.n(1234.5, "currency")).toBe(
        new Intl.NumberFormat("es-ES", { style: "currency", currency }).format(
          1234.5,
        ),
      );
    },
  );

  it("vuelve a EUR si la sesión entrega una moneda inválida", () => {
    applyReportingCurrency("invalid");

    expect(reportingCurrency.value).toBe("EUR");
  });
});
