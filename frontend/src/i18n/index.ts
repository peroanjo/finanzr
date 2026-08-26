import { computed, ref } from "vue";
import { createI18n } from "vue-i18n";
import { api } from "../api/client";
import { coreMessages } from "./coreMessages";

export const SOURCE_LOCALE = "en" as const;
export const DEFAULT_LOCALE = "es-ES" as const;
export const SUPPORTED_LOCALES = [SOURCE_LOCALE, DEFAULT_LOCALE] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];
export const reportingCurrency = ref("EUR");

const STORAGE_KEY = "finanzr-language";
const LOGIN_CHOICE_KEY = "finanzr-login-language-selected";

export const supportedLocales: ReadonlyArray<{
  code: SupportedLocale;
  label: string;
}> = [
  { code: SOURCE_LOCALE, label: coreMessages.en.locales.english },
  { code: DEFAULT_LOCALE, label: coreMessages.en.locales.spanish },
];

export function normalizeLocale(
  value: string | null | undefined,
): SupportedLocale | null {
  if (!value) return null;
  const normalized = value.toLowerCase();
  if (normalized === "es" || normalized.startsWith("es-")) return "es-ES";
  if (normalized === "en" || normalized.startsWith("en-")) return "en";
  return null;
}

function initialLocale(): SupportedLocale {
  const stored = normalizeLocale(globalThis.localStorage?.getItem(STORAGE_KEY));
  if (stored) return stored;
  const browserLocales = globalThis.navigator?.languages ?? [
    globalThis.navigator?.language,
  ];
  return (
    browserLocales
      .map(normalizeLocale)
      .find((item): item is SupportedLocale => Boolean(item)) ?? DEFAULT_LOCALE
  );
}

export const i18n = createI18n({
  legacy: false,
  locale: initialLocale(),
  fallbackLocale: SOURCE_LOCALE,
  missingWarn: import.meta.env.DEV,
  fallbackWarn: import.meta.env.DEV,
  messages: { en: {}, "es-ES": {} },
  numberFormats: {
    en: {
      currency: { style: "currency", currency: "EUR" },
      currencyPrecise: {
        style: "currency",
        currency: "EUR",
        minimumFractionDigits: 2,
        maximumFractionDigits: 4,
      },
      percent: { style: "percent", maximumFractionDigits: 2 },
      quantity: { maximumFractionDigits: 8 },
    },
    "es-ES": {
      currency: { style: "currency", currency: "EUR" },
      currencyPrecise: {
        style: "currency",
        currency: "EUR",
        minimumFractionDigits: 2,
        maximumFractionDigits: 4,
      },
      percent: { style: "percent", maximumFractionDigits: 2 },
      quantity: { maximumFractionDigits: 8 },
    },
  },
  datetimeFormats: {
    en: {
      short: { day: "2-digit", month: "short", year: "numeric" },
      monthYear: { month: "short", year: "2-digit" },
      long: { day: "numeric", month: "long", year: "numeric" },
    },
    "es-ES": {
      short: { day: "2-digit", month: "short", year: "numeric" },
      monthYear: { month: "short", year: "2-digit" },
      long: { day: "numeric", month: "long", year: "numeric" },
    },
  },
});

export type MessageCatalog = Record<SupportedLocale, Record<string, unknown>>;

export function registerMessages(catalog: MessageCatalog) {
  for (const locale of SUPPORTED_LOCALES) {
    i18n.global.mergeLocaleMessage(locale, catalog[locale]);
  }
}

function applyDocumentLanguage(locale: SupportedLocale) {
  if (globalThis.document) document.documentElement.lang = locale;
}

export function applyLocale(locale: SupportedLocale, persistLocally = true) {
  i18n.global.locale.value = locale;
  if (persistLocally) globalThis.localStorage?.setItem(STORAGE_KEY, locale);
  applyDocumentLanguage(locale);
}

export function applyReportingCurrency(value: string | null | undefined) {
  const normalized = String(value || "EUR")
    .trim()
    .toUpperCase();
  reportingCurrency.value = /^[A-Z]{3}$/.test(normalized) ? normalized : "EUR";
  for (const locale of SUPPORTED_LOCALES) {
    i18n.global.mergeNumberFormat(locale, {
      currency: { style: "currency", currency: reportingCurrency.value },
      currencyPrecise: {
        style: "currency",
        currency: reportingCurrency.value,
        minimumFractionDigits: 2,
        maximumFractionDigits: 4,
      },
    });
  }
}

applyDocumentLanguage(i18n.global.locale.value);

export function useLocalePreference() {
  const locale = computed<SupportedLocale>({
    get: () => i18n.global.locale.value,
    set: (value) => applyLocale(value),
  });

  function setLocale(value: SupportedLocale) {
    applyLocale(value);
  }

  function selectLoginLocale(value: SupportedLocale) {
    setLocale(value);
    globalThis.sessionStorage?.setItem(LOGIN_CHOICE_KEY, "true");
  }

  function hasLoginLocaleChoice() {
    return globalThis.sessionStorage?.getItem(LOGIN_CHOICE_KEY) === "true";
  }

  function clearLoginLocaleChoice() {
    globalThis.sessionStorage?.removeItem(LOGIN_CHOICE_KEY);
  }

  async function loadInstallationLocale() {
    if (globalThis.localStorage?.getItem(STORAGE_KEY)) return;
    try {
      const preferences = await api<{ default_language: SupportedLocale }>(
        "/installation/preferences",
      );
      if (globalThis.localStorage?.getItem(STORAGE_KEY)) return;
      applyLocale(preferences.default_language, false);
    } catch {
      // Browser detection remains the fallback when the installation is unavailable.
    }
  }

  return {
    locale,
    supportedLocales,
    setLocale,
    selectLoginLocale,
    hasLoginLocaleChoice,
    clearLoginLocaleChoice,
    loadInstallationLocale,
  };
}
