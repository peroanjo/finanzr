<script setup lang="ts">
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { SupportedLocale } from "../../i18n";

const props = defineProps<{
  mode: "installation" | "crowdfunding";
  canAdminister: boolean;
  supportedLocales?: ReadonlyArray<{ code: SupportedLocale; label: string }>;
  installationLanguage?: SupportedLocale;
  installationBusy?: boolean;
  installationError?: string;
  installationSuccess?: string;
  defaultCrowdfundingTaxRate?: number;
  crowdfundingBusy?: boolean;
  crowdfundingError?: string;
  crowdfundingSuccess?: string;
}>();

const emit = defineEmits<{
  saveInstallationLanguage: [language: SupportedLocale];
  saveCrowdfundingTax: [rate: number];
}>();

const { t } = useI18n();
const installationLanguage = ref<SupportedLocale>(
  props.installationLanguage ?? "es-ES",
);
const crowdfundingTaxRate = ref(props.defaultCrowdfundingTaxRate ?? 19);

watch(
  () => props.installationLanguage,
  (language) => {
    installationLanguage.value = language ?? "es-ES";
  },
);
watch(
  () => props.defaultCrowdfundingTaxRate,
  (rate) => {
    if (rate !== undefined && rate !== null) crowdfundingTaxRate.value = rate;
  },
);

function saveInstallationLanguage() {
  emit("saveInstallationLanguage", installationLanguage.value);
}

function saveCrowdfundingTax() {
  emit("saveCrowdfundingTax", Number(crowdfundingTaxRate.value));
}
</script>

<template>
  <form
    v-if="props.mode === 'installation' && props.canAdminister"
    class="installation-language-panel"
    @submit.prevent="saveInstallationLanguage"
  >
    <div class="installation-language-copy">
      <span aria-hidden="true">⌂</span>
      <div>
        <p>{{ t("settings.installationPreference") }}</p>
        <h4>{{ t("settings.installationLanguageTitle") }}</h4>
        <small>{{ t("settings.installationLanguageHelp") }}</small>
      </div>
    </div>
    <div class="installation-language-actions">
      <label
        v-for="option in props.supportedLocales"
        :key="option.code"
        :class="{ selected: installationLanguage === option.code }"
      >
        <input
          v-model="installationLanguage"
          type="radio"
          name="installation-language"
          :value="option.code"
        />
        <span aria-hidden="true">{{ option.code === "en" ? "🇬🇧" : "🇪🇸" }}</span>
        <strong>{{ option.label }}</strong>
      </label>
      <button type="submit" :disabled="props.installationBusy">
        {{
          props.installationBusy
            ? t("common.saving")
            : t("settings.saveInstallationLanguage")
        }}
      </button>
    </div>
    <p v-if="props.installationError" class="language-feedback error" role="alert">
      {{ props.installationError }}
    </p>
    <p v-else-if="props.installationSuccess" class="language-feedback success" role="status">
      {{ props.installationSuccess }}
    </p>
  </form>

  <article v-else-if="props.mode === 'crowdfunding'" class="interface-document">
    <header class="interface-document-header">
      <div>
        <p>{{ t("settings.crowdfunding") }}</p>
        <h3>{{ t("settings.crowdfundingTaxTitle") }}</h3>
        <span>{{ t("settings.crowdfundingTaxIntro") }}</span>
      </div>
      <div class="effective-language" aria-live="polite">
        <span aria-hidden="true">%</span>
        <p>
          <small>{{ t("settings.defaultRateBadge") }}</small
          ><strong>{{ crowdfundingTaxRate }} %</strong>
        </p>
        <i aria-hidden="true" />
      </div>
    </header>

    <form class="language-preference-panel" @submit.prevent="saveCrowdfundingTax">
      <header>
        <div>
          <p>{{ t("settings.crowdfunding") }}</p>
          <h4>{{ t("settings.crowdfundingTaxTitle") }}</h4>
        </div>
        <span>{{ t("settings.installationPreference") }}</span>
      </header>
      <p class="document-description">{{ t("settings.crowdfundingTaxHelp") }}</p>
      <div class="withholding-form-row">
        <label class="tax-rate-field">
          <span>{{ t("settings.defaultCrowdfundingTaxRate") }}</span>
          <div class="tax-rate-input-wrap">
            <input
              v-model.number="crowdfundingTaxRate"
              type="number"
              min="0"
              max="100"
              step="0.1"
              :disabled="!props.canAdminister || props.crowdfundingBusy"
              required
            />
            <strong>%</strong>
          </div>
        </label>
        <button
          v-if="props.canAdminister"
          type="submit"
          :disabled="props.crowdfundingBusy"
        >
          {{
            props.crowdfundingBusy
              ? t("common.saving")
              : t("settings.saveCrowdfundingTax")
          }}
        </button>
      </div>
      <p v-if="!props.canAdminister" class="language-feedback muted">
        {{ t("settings.adminsOnlyWithholdingNotice") }}
      </p>
      <p v-if="props.crowdfundingError" class="language-feedback error" role="alert">
        {{ props.crowdfundingError }}
      </p>
      <p v-else-if="props.crowdfundingSuccess" class="language-feedback success" role="status">
        {{ props.crowdfundingSuccess }}
      </p>
    </form>
  </article>
</template>

<style scoped>
.installation-language-panel {
  margin-top: 16px;
  padding: 18px 20px;
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto;
  align-items: center;
  gap: 16px;
  border: 1px dashed color-mix(in srgb, var(--fz-accent) 32%, var(--fz-line));
  border-radius: 17px;
  background: color-mix(in srgb, var(--fz-accent) 3%, var(--fz-surface));
}
.installation-language-copy { display: flex; align-items: center; gap: 12px; }
.installation-language-copy > span { width: 39px; height: 39px; display: grid; place-items: center; border-radius: 11px; background: var(--fz-accent-soft); color: var(--fz-accent); font-size: 18px; }
.installation-language-copy p { margin: 0 0 6px; color: var(--fz-accent); font-size: 10px; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; }
.installation-language-copy h4 { margin: 0; font-size: 16px; letter-spacing: -0.025em; }
.installation-language-copy small { display: block; max-width: 500px; margin-top: 4px; color: var(--fz-muted); font-size: 10px; line-height: 1.45; }
.installation-language-actions { display: flex; align-items: center; gap: 7px; }
.installation-language-actions label { height: 42px; padding: 0 10px; display: flex; align-items: center; gap: 7px; border: 1px solid var(--fz-line); border-radius: 10px; background: var(--fz-surface); cursor: pointer; }
.installation-language-actions > button { height: 42px; padding: 0 13px; border: 0; border-radius: 10px; background: var(--fz-accent); color: #092418; font-size: 10px; font-weight: 800; cursor: pointer; }
.installation-language-actions > button:disabled { opacity: 0.55; cursor: wait; }
.installation-language-panel > .language-feedback { grid-column: 1/-1; margin: 0; }
.language-feedback { margin: 13px 0 0; padding: 9px 11px; border-radius: 9px; font-size: 11px; font-weight: 680; }
.language-feedback.error { background: color-mix(in srgb, var(--fz-negative) 9%, transparent); color: var(--fz-negative); }
.language-feedback.success { background: var(--fz-accent-soft); color: var(--fz-accent); }
.language-feedback.muted { background: var(--fz-surface-soft); color: var(--fz-muted); }
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
.document-description { max-width: 590px; margin: 11px 0 0; color: var(--fz-muted); font-size: 12px; line-height: 1.6; }
.withholding-form-row { margin-top: 20px; display: flex; align-items: flex-end; gap: 14px; flex-wrap: wrap; }
.withholding-form-row label { display: grid; gap: 6px; }
.withholding-form-row label > span { color: var(--fz-muted); font-size: 11px; font-weight: 700; }
.tax-rate-input-wrap { height: 44px; padding: 0 12px; display: flex; align-items: center; gap: 8px; border: 1px solid var(--fz-line); border-radius: 12px; background: var(--fz-surface-soft); transition: border-color 0.15s ease; }
.tax-rate-input-wrap:focus-within { border-color: var(--fz-accent); }
.tax-rate-input-wrap input { width: 80px; border: 0; outline: 0; background: transparent; color: var(--fz-ink); font: inherit; font-size: 14px; font-weight: 750; text-align: right; }
.tax-rate-input-wrap strong { color: var(--fz-muted); font-size: 12px; }
.withholding-form-row button { height: 44px; padding: 0 18px; border: 0; border-radius: 12px; background: var(--fz-accent); color: #092418; font-size: 11px; font-weight: 800; cursor: pointer; transition: opacity 0.15s ease; }
.withholding-form-row button:disabled { opacity: 0.55; cursor: wait; }
@media (max-width: 1100px) {
  .interface-document { padding-inline: 28px; }
  .installation-language-panel { grid-template-columns: 1fr; }
  .installation-language-actions { justify-content: flex-start; }
}
@media (max-width: 720px) {
  .interface-document { padding: 22px 17px 34px; }
  .interface-document-header { display: block; }
  .interface-document-header h3 { font-size: 24px; }
  .effective-language { margin-top: 18px; }
  .language-preference-panel { margin-top: 20px; padding: 15px; }
  .language-preference-panel > header { display: block; }
  .language-preference-panel > header > span { display: inline-block; margin-top: 9px; }
  .installation-language-panel { padding: 15px; }
  .installation-language-actions { flex-wrap: wrap; }
  .installation-language-actions > button { width: 100%; }
}
</style>
