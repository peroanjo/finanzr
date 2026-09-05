import { config, mount, type ComponentMountingOptions } from "@vue/test-utils";
import type { Component } from "vue";
import { createI18n } from "vue-i18n";
import { coreMessages } from "../../i18n/coreMessages";

export function createTestI18n() {
  return createI18n({
    legacy: false,
    globalInjection: true,
    missingWarn: false,
    fallbackWarn: false,
    locale: "es-ES",
    fallbackLocale: "en",
    messages: {
      en: coreMessages.en,
      "es-ES": coreMessages["es-ES"],
    },
  });
}

export function mountWithTestI18n<T extends Component>(
  component: T,
  options: ComponentMountingOptions<T> = {},
) {
  const previousPlugins = config.global.plugins;
  config.global.plugins = [];
  try {
    return mount(component, {
      ...options,
      global: {
        ...options.global,
        plugins: [[createTestI18n(), { globalInstall: false }]],
      },
    });
  } finally {
    config.global.plugins = previousPlugins;
  }
}
