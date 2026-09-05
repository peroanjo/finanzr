<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { SupportedLocale } from "../../i18n";
import SettingsInstallationPreferencesPanel from "./SettingsInstallationPreferencesPanel.vue";

const props = defineProps<{
  effectiveLanguage: SupportedLocale;
  effectiveLanguageName: string;
  effectiveLanguageFlag: string;
  preferredLanguage: SupportedLocale | null;
  canManage: boolean;
  canAdminister: boolean;
  languageBusy: boolean;
  languageError: string;
  languageSuccess: string;
  installationLanguage: SupportedLocale;
  supportedLocales: ReadonlyArray<{ code: SupportedLocale; label: string }>;
  installationBusy: boolean;
  installationError: string;
  installationSuccess: string;
}>();

const emit = defineEmits<{
  saveLanguage: [language: SupportedLocale | ""];
  saveInstallationLanguage: [language: SupportedLocale];
}>();

const { t } = useI18n();
const installationLanguageName = computed(() =>
  props.installationLanguage === "en"
    ? t("locales.english")
    : t("locales.spanish"),
);
const personalLanguageOptions = computed(() => [
  {
    code: "" as const,
    flag: "🌐",
    title: t("settings.inheritInstallationLanguage"),
    native: t("settings.automaticLanguage"),
    description: t("settings.inheritLanguageDescription", {
      language: installationLanguageName.value,
    }),
  },
  {
    code: "es-ES" as const,
    flag: "🇪🇸",
    title: t("locales.spanish"),
    native: t("locales.spanish"),
    description: t("settings.spanishLanguageDescription"),
  },
  {
    code: "en" as const,
    flag: "🇬🇧",
    title: t("locales.english"),
    native: "English",
    description: t("settings.englishLanguageDescription"),
  },
]);
</script>

<template>
  <article class="interface-document">
    <header class="interface-document-header">
      <div>
        <p>{{ t("settings.interfaceEyebrow") }}</p>
        <h3>{{ t("settings.interfaceLanguageTitle") }}</h3>
        <span>{{ t("settings.interfaceLanguageIntro") }}</span>
      </div>
      <div class="effective-language" aria-live="polite">
        <span aria-hidden="true">{{ props.effectiveLanguageFlag }}</span>
        <p>
          <small>{{ t("settings.effectiveLanguage") }}</small
          ><strong>{{ props.effectiveLanguageName }}</strong>
        </p>
        <i />
      </div>
    </header>

    <section class="language-preference-panel" aria-labelledby="personal-language-title">
      <header>
        <div>
          <p>{{ t("settings.personalPreference") }}</p>
          <h4 id="personal-language-title">{{ t("settings.chooseLanguage") }}</h4>
        </div>
        <span>
          {{
            props.preferredLanguage
              ? t("settings.personalOverride")
              : t("settings.followingInstallation")
          }}
        </span>
      </header>
      <div class="language-choice-grid" role="radiogroup" :aria-label="t('settings.languageTitle')">
        <button
          v-for="option in personalLanguageOptions"
          :key="option.code || 'automatic'"
          type="button"
          class="language-choice"
          :class="{ selected: (props.preferredLanguage ?? '') === option.code }"
          :aria-checked="(props.preferredLanguage ?? '') === option.code"
          :disabled="props.languageBusy || !props.canManage"
          role="radio"
          @click="emit('saveLanguage', option.code)"
        >
          <span class="language-flag" aria-hidden="true">{{ option.flag }}</span>
          <span class="language-copy"><strong>{{ option.title }}</strong><small>{{ option.native }}</small></span>
          <i class="language-check" aria-hidden="true">✓</i>
          <em>{{ option.description }}</em>
        </button>
      </div>
      <p v-if="props.languageError" class="language-feedback error" role="alert">
        {{ props.languageError }}
      </p>
      <p v-else-if="props.languageSuccess" class="language-feedback success" role="status">
        {{ props.languageSuccess }}
      </p>
      <p v-if="!props.canManage" class="language-feedback muted">
        {{ t("settings.demoLanguageNotice") }}
      </p>
    </section>

    <SettingsInstallationPreferencesPanel
      :mode="'installation'"
      :can-administer="props.canAdminister"
      :supported-locales="props.supportedLocales"
      :installation-language="props.installationLanguage"
      :installation-busy="props.installationBusy"
      :installation-error="props.installationError"
      :installation-success="props.installationSuccess"
      @save-installation-language="emit('saveInstallationLanguage', $event)"
    />
  </article>
</template>

<style scoped>
.interface-document { min-height: 100%; padding: 36px 40px 48px; background: linear-gradient(145deg, color-mix(in srgb, var(--fz-accent) 3%, transparent), transparent 38%); }
.interface-document-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.interface-document-header > div:first-child { max-width: 600px; }
.interface-document-header p { margin: 0 0 6px; color: var(--fz-accent); font-size: 10px; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; }
.interface-document-header h3 { margin: 0; font-size: 30px; letter-spacing: -0.05em; }
.interface-document-header > div:first-child > span { display: block; max-width: 590px; margin-top: 11px; color: var(--fz-muted); font-size: 12px; line-height: 1.6; }
.effective-language { min-width: 178px; padding: 12px 14px; display: grid; grid-template-columns: 40px 1fr 7px; align-items: center; gap: 10px; border: 1px solid color-mix(in srgb, var(--fz-accent) 24%, var(--fz-line)); border-radius: 15px; background: var(--fz-surface); box-shadow: 0 12px 32px rgba(16, 44, 29, 0.07); }
.effective-language > span { width: 40px; height: 40px; display: grid; place-items: center; border-radius: 12px; background: var(--fz-surface-soft); font-size: 24px; box-shadow: inset 0 0 0 1px var(--fz-line); }
.effective-language p { margin: 0; display: grid; gap: 2px; }
.effective-language small { color: var(--fz-muted); font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }
.effective-language strong { font-size: 12px; }
.effective-language > i { width: 7px; height: 7px; border-radius: 50%; background: var(--fz-accent); box-shadow: 0 0 0 4px color-mix(in srgb, var(--fz-accent) 12%, transparent); }
.language-preference-panel { margin-top: 32px; padding: 22px; border: 1px solid var(--fz-line); border-radius: 20px; background: var(--fz-surface); }
.language-preference-panel > header { display: flex; align-items: end; justify-content: space-between; gap: 18px; margin-bottom: 17px; }
.language-preference-panel > header p { margin: 0 0 6px; color: var(--fz-accent); font-size: 10px; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; }
.language-preference-panel h4 { margin: 0; font-size: 16px; letter-spacing: -0.025em; }
.language-preference-panel > header > span { padding: 5px 8px; border-radius: 99px; background: var(--fz-accent-soft); color: var(--fz-accent); font-size: 10px; font-weight: 750; }
.language-choice-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 11px; }
.language-choice { position: relative; min-height: 158px; padding: 16px; display: grid; grid-template-columns: 48px minmax(0, 1fr) 24px; grid-template-rows: auto 1fr; align-items: center; gap: 10px; border: 1px solid var(--fz-line); border-radius: 16px; outline: 0; background: var(--fz-surface-soft); color: var(--fz-ink); text-align: left; cursor: pointer; transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease, background 0.16s ease; }
.language-choice:hover:not(:disabled) { transform: translateY(-2px); border-color: color-mix(in srgb, var(--fz-accent) 32%, var(--fz-line)); box-shadow: 0 12px 28px rgba(13, 42, 26, 0.08); }
.language-choice:focus-visible { box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 18%, transparent); }
.language-choice.selected { border-color: color-mix(in srgb, var(--fz-accent) 58%, var(--fz-line)); background: color-mix(in srgb, var(--fz-accent) 7%, var(--fz-surface)); box-shadow: inset 0 -3px var(--fz-accent), 0 14px 30px rgba(13, 42, 26, 0.08); }
.language-choice:disabled { cursor: not-allowed; opacity: 0.62; }
.language-flag { width: 48px; height: 48px; display: grid; place-items: center; border: 1px solid var(--fz-line); border-radius: 14px; background: var(--fz-surface); font-size: 27px; box-shadow: 0 5px 12px rgba(13, 42, 26, 0.06); }
.language-copy { min-width: 0; display: grid; gap: 3px; }
.language-copy strong { font-size: 12px; line-height: 1.2; }
.language-copy small { overflow: hidden; color: var(--fz-muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.language-check { width: 22px; height: 22px; display: grid; place-items: center; border: 1px solid var(--fz-line); border-radius: 50%; color: transparent; font-size: 11px; font-style: normal; }
.language-choice.selected .language-check { border-color: var(--fz-accent); background: var(--fz-accent); color: #092418; }
.language-choice em { grid-column: 1/-1; align-self: end; margin-top: 8px; color: var(--fz-muted); font-size: 10px; font-style: normal; line-height: 1.5; }
.language-feedback { margin: 13px 0 0; padding: 9px 11px; border-radius: 9px; font-size: 11px; font-weight: 680; }
.language-feedback.error { background: color-mix(in srgb, var(--fz-negative) 9%, transparent); color: var(--fz-negative); }
.language-feedback.success { background: var(--fz-accent-soft); color: var(--fz-accent); }
.language-feedback.muted { background: var(--fz-surface-soft); color: var(--fz-muted); }
@media (prefers-reduced-motion: reduce) { .language-choice { transition: none; } .language-choice:hover:not(:disabled) { transform: none; } }
@media (max-width: 1100px) { .interface-document { padding-inline: 28px; } .language-choice-grid { grid-template-columns: 1fr; } .language-choice { min-height: 108px; } }
@media (max-width: 720px) { .interface-document { padding: 22px 17px 34px; } .interface-document-header { display: block; } .interface-document-header h3 { font-size: 24px; } .effective-language { margin-top: 18px; } .language-preference-panel { margin-top: 20px; padding: 15px; } .language-preference-panel > header { display: block; } .language-preference-panel > header > span { display: inline-block; margin-top: 9px; } }
</style>
