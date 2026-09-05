<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { useI18n } from "vue-i18n";
import { api, json } from "../api/client";
import type { ImporterCatalogItem, SummarySourceKey } from "../types/api";
import NavIcon from "../components/NavIcon.vue";
import AdminUsersPanel from "../components/settings/AdminUsersPanel.vue";
import SettingsAccountPanel from "../components/settings/SettingsAccountPanel.vue";
import SettingsImporterDocument from "../components/settings/SettingsImporterDocument.vue";
import SettingsInstallationPreferencesPanel from "../components/settings/SettingsInstallationPreferencesPanel.vue";
import SettingsLanguagePanel from "../components/settings/SettingsLanguagePanel.vue";
import SettingsSummarySourcesPanel from "../components/settings/SettingsSummarySourcesPanel.vue";
import { useSessionStore } from "../stores/session";
import { useLocalePreference } from "../i18n";

const emit = defineEmits<{ close: [] }>();
const session = useSessionStore();
const { t } = useI18n();
const { locale, supportedLocales } = useLocalePreference();
const activeSection = ref<
  "importers" | "sections" | "interface" | "account" | "administration"
>("importers");
const activeProductSection = ref<"summary" | "crowdfunding">("summary");
const importers = ref<ImporterCatalogItem[]>([]);
const selectedSlug = ref("");
const loading = ref(true);
const error = ref("");
const closeButton = ref<HTMLButtonElement>();
const selectedImporter = computed(
  () =>
    importers.value.find((item) => item.slug === selectedSlug.value) ??
    importers.value[0] ??
    null,
);
const importerGroups = computed(() => {
  const preferredOrder = ["fund_orders", "stock_orders", "crypto_orders"];
  const grouped = new Map<string, ImporterCatalogItem[]>();
  for (const importer of importers.value) {
    const group = grouped.get(importer.target_label) ?? [];
    group.push(importer);
    grouped.set(importer.target_label, group);
  }
  return [...grouped.entries()]
    .map(([label, items]) => ({ label, items, target: items[0]?.target ?? "" }))
    .sort((left, right) => {
      const leftIndex = preferredOrder.indexOf(left.target);
      const rightIndex = preferredOrder.indexOf(right.target);
      if (leftIndex === -1 && rightIndex === -1)
        return left.label.localeCompare(right.label);
      if (leftIndex === -1) return 1;
      if (rightIndex === -1) return -1;
      return leftIndex - rightIndex;
    });
});
const activeImporterLabel = computed(() =>
  importers.value.length === 1
    ? t("settings.importerActive")
    : t("settings.importersActive", { count: importers.value.length }),
);
const canManageAccount = computed(() =>
  Boolean(session.user && session.user.role !== "demo"),
);
const canAdminister = computed(() => session.user?.role === "admin");
const accountRoleLabel = computed(() =>
  session.user?.role === "admin"
    ? t("settings.administrator")
    : t("settings.user"),
);
const identityBusy = ref(false);
const identityError = ref("");
const identitySuccess = ref("");
const passwordBusy = ref(false);
const passwordError = ref("");
const passwordSuccess = ref("");
const languageBusy = ref(false);
const languageError = ref("");
const languageSuccess = ref("");
const installationLanguageBusy = ref(false);
const installationLanguageError = ref("");
const installationLanguageSuccess = ref("");
const crowdfundingTaxBusy = ref(false);
const crowdfundingTaxError = ref("");
const crowdfundingTaxSuccess = ref("");
const summarySources = ref<SummarySourceKey[]>([]);
const summarySourcesBusy = ref(false);
const summarySourcesError = ref("");
const summarySourcesSuccess = ref("");
const summarySourceKeys: SummarySourceKey[] = [
  "savings",
  "manual_investments",
  "funds",
  "stocks",
  "crypto",
  "crowdfunding",
  "manual_assets",
];
const summaryScopeLabel = computed(() =>
  session.user?.summary_sources_scope === "personal"
    ? t("settings.summarySourcesScopePersonal")
    : t("settings.summarySourcesScopeInstallation"),
);
let previousBodyOverflow = "";

const sessionDefaultLanguage = computed(
  () =>
    (
      session.user as typeof session.user & {
        default_language?: "es-ES" | "en";
      }
    )?.default_language,
);
const sessionDefaultCrowdfundingTaxRate = computed(
  () =>
    (
      session.user as typeof session.user & {
        default_crowdfunding_tax_rate?: number;
      }
    )?.default_crowdfunding_tax_rate,
);
const effectiveLanguage = computed(
  () => session.user?.language ?? locale.value,
);
const effectiveLanguageName = computed(() =>
  effectiveLanguage.value === "en"
    ? t("locales.english")
    : t("locales.spanish"),
);
const effectiveLanguageFlag = computed(() =>
  effectiveLanguage.value === "en" ? "🇬🇧" : "🇪🇸",
);

watch(importers, (items) => {
  if (!items.some((item) => item.slug === selectedSlug.value)) {
    selectedSlug.value = items[0]?.slug ?? "";
  }
});
watch(
  () => [session.user?.active_workspace_id, session.user?.summary_sources],
  () => {
    const next = (session.user?.summary_sources ??
      session.user?.default_summary_sources ?? [
        "savings",
        "manual_investments",
        "crowdfunding",
      ]) as SummarySourceKey[];
    summarySources.value = summarySourceKeys.filter((key) =>
      next.includes(key),
    );
  },
  { deep: true, immediate: true },
);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    importers.value = await api<ImporterCatalogItem[]>("/importers");
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : t("settings.catalogLoadError");
  } finally {
    loading.value = false;
  }
}

async function saveIdentity(payload: {
  displayName: string;
  email: string;
  password: string;
}) {
  identityError.value = "";
  identitySuccess.value = "";
  identityBusy.value = true;
  try {
    await session.updateAccount(
      payload.displayName,
      payload.email,
      payload.password,
    );
    identitySuccess.value = t("settings.profileUpdated");
  } catch (reason) {
    identityError.value =
      reason instanceof Error
        ? reason.message
        : t("settings.profileUpdateError");
  } finally {
    identityBusy.value = false;
  }
}

async function savePassword(payload: {
  currentPassword: string;
  newPassword: string;
  confirmation: string;
}) {
  passwordError.value = "";
  passwordSuccess.value = "";
  if (payload.newPassword !== payload.confirmation) {
    passwordError.value = t("settings.passwordMismatch");
    return;
  }
  passwordBusy.value = true;
  try {
    await session.changePassword(
      payload.currentPassword,
      payload.newPassword,
      payload.confirmation,
    );
    passwordSuccess.value = t("settings.passwordUpdated");
  } catch (reason) {
    passwordError.value =
      reason instanceof Error
        ? reason.message
        : t("settings.passwordUpdateError");
  } finally {
    passwordBusy.value = false;
  }
}

async function saveInstallationLanguage(language: "es-ES" | "en") {
  installationLanguageError.value = "";
  installationLanguageSuccess.value = "";
  installationLanguageBusy.value = true;
  try {
    const result = await api<{
      default_language: "es-ES" | "en";
      language: "es-ES" | "en";
    }>(
      "/installation/preferences",
      json("PATCH", { default_language: language }),
    );
    if (session.user) {
      Object.assign(session.user, {
        default_language: result.default_language,
      });
      if (session.user.preferred_language === null) {
        session.user.language = result.language;
        locale.value = result.language;
      }
    }
    installationLanguageSuccess.value = t("settings.installationLanguageSaved");
  } catch (reason) {
    installationLanguageError.value =
      reason instanceof Error
        ? reason.message
        : t("settings.installationLanguageError");
  } finally {
    installationLanguageBusy.value = false;
  }
}

async function saveCrowdfundingTax(rate: number) {
  crowdfundingTaxError.value = "";
  crowdfundingTaxSuccess.value = "";
  crowdfundingTaxBusy.value = true;
  try {
    const result = await api<{
      default_crowdfunding_tax_rate: number;
      default_language: "es-ES" | "en";
      language: "es-ES" | "en";
    }>(
      "/installation/preferences",
      json("PATCH", {
        default_crowdfunding_tax_rate: Number(rate),
      }),
    );
    if (session.user) {
      session.user.default_crowdfunding_tax_rate =
        result.default_crowdfunding_tax_rate;
    }
    crowdfundingTaxSuccess.value = t("settings.crowdfundingTaxSaved");
  } catch (reason) {
    crowdfundingTaxError.value =
      reason instanceof Error
        ? reason.message
        : t("settings.crowdfundingTaxError");
  } finally {
    crowdfundingTaxBusy.value = false;
  }
}

async function saveLanguage(value: "es-ES" | "en" | "") {
  if (languageBusy.value || !canManageAccount.value) return;
  languageBusy.value = true;
  languageError.value = "";
  languageSuccess.value = "";
  try {
    await session.updateLanguage(value || null);
    languageSuccess.value = t("settings.languageSaved");
  } catch (reason) {
    languageError.value =
      reason instanceof Error ? reason.message : t("settings.languageError");
  } finally {
    languageBusy.value = false;
  }
}

async function saveSummarySources(nextSources = summarySources.value) {
  if (summarySourcesBusy.value || !canManageAccount.value) return;
  summarySourcesBusy.value = true;
  summarySourcesError.value = "";
  summarySourcesSuccess.value = "";
  try {
    await session.updateSummarySources(nextSources);
    summarySourcesSuccess.value = t("settings.summarySourcesSaved");
  } catch (reason) {
    summarySourcesError.value =
      reason instanceof Error
        ? reason.message
        : t("settings.summarySourcesError");
  } finally {
    summarySourcesBusy.value = false;
  }
}

function updateSummarySources(nextSources: SummarySourceKey[]) {
  summarySources.value = nextSources;
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") emit("close");
}

onMounted(async () => {
  previousBodyOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  window.addEventListener("keydown", onKeydown);
  await Promise.all([load(), nextTick()]);
  closeButton.value?.focus();
});
onBeforeUnmount(() => {
  document.body.style.overflow = previousBodyOverflow;
  window.removeEventListener("keydown", onKeydown);
});
</script>

<template>
  <div class="settings-overlay" @mousedown.self="emit('close')">
    <section
      class="settings-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
    >
      <header class="settings-modal-header">
        <div>
          <p>Finanzr</p>
          <h2 id="settings-title">{{ t("settings.title") }}</h2>
        </div>
        <button
          ref="closeButton"
          type="button"
          :aria-label="t('settings.closeAria')"
          @click="emit('close')"
        >
          ×
        </button>
      </header>

      <div class="settings-layout">
        <nav class="settings-primary" :aria-label="t('settings.areasAria')">
          <p>{{ t("settings.sections") }}</p>
          <button
            type="button"
            :class="{ active: activeSection === 'importers' }"
            :aria-current="activeSection === 'importers' ? 'page' : undefined"
            @click="activeSection = 'importers'"
          >
            <span><NavIcon name="import" /></span>
            <strong>{{ t("settings.importers") }}</strong>
            <small>{{ t("settings.inputFormats") }}</small>
          </button>
          <button
            type="button"
            :class="{ active: activeSection === 'sections' }"
            :aria-current="activeSection === 'sections' ? 'page' : undefined"
            @click="activeSection = 'sections'"
          >
            <span><NavIcon name="trend" /></span>
            <strong>{{ t("settings.sections") }}</strong>
            <small>{{ t("settings.sectionsDescription") }}</small>
          </button>
          <button
            type="button"
            :class="{ active: activeSection === 'interface' }"
            :aria-current="activeSection === 'interface' ? 'page' : undefined"
            @click="activeSection = 'interface'"
          >
            <span><NavIcon name="interface" /></span>
            <strong>{{ t("settings.interface") }}</strong>
            <small>{{ t("settings.interfaceDescription") }}</small>
          </button>
          <button
            v-if="canManageAccount"
            type="button"
            :class="{ active: activeSection === 'account' }"
            :aria-current="activeSection === 'account' ? 'page' : undefined"
            @click="activeSection = 'account'"
          >
            <span><NavIcon name="user" /></span>
            <strong>{{ t("settings.account") }}</strong>
            <small>{{ t("settings.emailAndPassword") }}</small>
          </button>
          <button
            v-if="canAdminister"
            type="button"
            :class="{ active: activeSection === 'administration' }"
            :aria-current="
              activeSection === 'administration' ? 'page' : undefined
            "
            @click="activeSection = 'administration'"
          >
            <span><NavIcon name="admin" /></span>
            <strong>{{ t("settings.administration") }}</strong>
            <small>{{ t("settings.usersAndAccess") }}</small>
          </button>
        </nav>

        <nav
          v-if="activeSection === 'importers'"
          class="settings-secondary"
          :aria-label="t('settings.configuredImportersAria')"
        >
          <header>
            <p>{{ t("settings.importers") }}</p>
          </header>
          <div v-if="loading" class="importer-nav-loading"><i /><i /><i /></div>
          <div v-else class="importer-groups">
            <section
              v-for="group in importerGroups"
              :key="group.label"
              class="importer-group"
            >
              <header>
                <h3>{{ group.label }}</h3>
                <span>{{ group.items.length }}</span>
              </header>
              <button
                v-for="item in group.items"
                :key="item.slug"
                type="button"
                :class="{ active: selectedImporter?.slug === item.slug }"
                :aria-pressed="selectedImporter?.slug === item.slug"
                @click="selectedSlug = item.slug"
              >
                <span>{{ item.target_label.slice(0, 2).toUpperCase() }}</span>
                <p>
                  <strong>{{ item.display_name }}</strong
                  ><small>{{ item.target_label }}</small>
                </p>
                <i aria-hidden="true">›</i>
              </button>
            </section>
          </div>
          <footer class="importer-count"><i />{{ activeImporterLabel }}</footer>
        </nav>
        <nav
          v-else-if="activeSection === 'sections'"
          class="settings-secondary account-secondary"
          :aria-label="t('settings.sectionsOptionsAria')"
        >
          <header>
            <p>{{ t("settings.sections") }}</p>
          </header>
          <button
            type="button"
            :class="{ active: activeProductSection === 'summary' }"
            :aria-current="
              activeProductSection === 'summary' ? 'page' : undefined
            "
            @click="activeProductSection = 'summary'"
          >
            <span><NavIcon name="trend" /></span>
            <p>
              <strong>{{ t("settings.overviewSection") }}</strong
              ><small>{{ t("settings.summarySources") }}</small>
            </p>
            <i aria-hidden="true">›</i>
          </button>
          <button
            type="button"
            :class="{ active: activeProductSection === 'crowdfunding' }"
            :aria-current="
              activeProductSection === 'crowdfunding' ? 'page' : undefined
            "
            @click="activeProductSection = 'crowdfunding'"
          >
            <span><NavIcon name="building" /></span>
            <p>
              <strong>{{ t("settings.crowdfunding") }}</strong
              ><small>{{ t("settings.crowdfundingTaxTitle") }}</small>
            </p>
            <i aria-hidden="true">›</i>
          </button>
          <footer class="account-access-state">
            <i />{{
              activeProductSection === "summary"
                ? summaryScopeLabel
                : t("settings.installationPreference")
            }}
          </footer>
        </nav>
        <nav
          v-else-if="activeSection === 'interface'"
          class="settings-secondary account-secondary"
          :aria-label="t('settings.interfaceOptionsAria')"
        >
          <header>
            <p>{{ t("settings.interface") }}</p>
          </header>
          <button class="active" type="button" aria-current="page">
            <span aria-hidden="true">文</span>
            <p>
              <strong>{{ t("settings.languageCategory") }}</strong
              ><small>{{ t("settings.regionalPreference") }}</small>
            </p>
            <i aria-hidden="true">›</i>
          </button>
          <footer class="account-access-state">
            <i />{{ t("settings.interfacePersonal") }}
          </footer>
        </nav>
        <nav
          v-else-if="activeSection === 'account'"
          class="settings-secondary account-secondary"
          :aria-label="t('settings.accountOptionsAria')"
        >
          <header>
            <p>{{ t("settings.account") }}</p>
          </header>
          <button class="active" type="button" aria-current="page">
            <span>SE</span>
            <p>
              <strong>{{ t("settings.securityAndAccess") }}</strong
              ><small>{{ t("settings.personalCredentials") }}</small>
            </p>
            <i aria-hidden="true">›</i>
          </button>
          <footer class="account-access-state">
            <i />{{ t("settings.protectedSession") }}
          </footer>
        </nav>
        <nav
          v-else
          class="settings-secondary account-secondary"
          :aria-label="t('settings.administrationOptionsAria')"
        >
          <header>
            <p>{{ t("settings.administration") }}</p>
          </header>
          <button class="active" type="button" aria-current="page">
            <span>US</span>
            <p>
              <strong>{{ t("settings.users") }}</strong
              ><small>{{ t("settings.accountsAndAccess") }}</small>
            </p>
            <i aria-hidden="true">›</i>
          </button>
          <footer class="account-access-state">
            <i />{{ t("settings.adminsOnly") }}
          </footer>
        </nav>

        <main class="settings-content">
          <SettingsSummarySourcesPanel
            v-if="
              activeSection === 'sections' && activeProductSection === 'summary'
            "
            :summary-sources="summarySources"
            :summary-source-keys="summarySourceKeys"
            :scope-label="summaryScopeLabel"
            :can-manage="canManageAccount"
            :busy="summarySourcesBusy"
            :error="summarySourcesError"
            :success="summarySourcesSuccess"
            @update="updateSummarySources"
            @save="saveSummarySources"
          />
          <SettingsLanguagePanel
            v-else-if="activeSection === 'interface'"
            :effective-language="effectiveLanguage"
            :effective-language-name="effectiveLanguageName"
            :effective-language-flag="effectiveLanguageFlag"
            :preferred-language="session.user?.preferred_language ?? null"
            :can-manage="canManageAccount"
            :can-administer="canAdminister"
            :language-busy="languageBusy"
            :language-error="languageError"
            :language-success="languageSuccess"
            :installation-language="sessionDefaultLanguage"
            :supported-locales="supportedLocales"
            :installation-busy="installationLanguageBusy"
            :installation-error="installationLanguageError"
            :installation-success="installationLanguageSuccess"
            @save-language="saveLanguage"
            @save-installation-language="saveInstallationLanguage"
          />
          <SettingsInstallationPreferencesPanel
            v-else-if="
              activeSection === 'sections' &&
              activeProductSection === 'crowdfunding'
            "
            mode="crowdfunding"
            :can-administer="canAdminister"
            :default-crowdfunding-tax-rate="sessionDefaultCrowdfundingTaxRate ?? 19"
            :crowdfunding-busy="crowdfundingTaxBusy"
            :crowdfunding-error="crowdfundingTaxError"
            :crowdfunding-success="crowdfundingTaxSuccess"
            @save-crowdfunding-tax="saveCrowdfundingTax"
          />
          <div
            v-else-if="activeSection === 'administration'"
            class="administration-document"
          >
            <AdminUsersPanel />
          </div>
          <SettingsAccountPanel
            v-else-if="activeSection === 'account'"
            :initial-display-name="session.user?.display_name ?? ''"
            :initial-email="session.user?.email ?? ''"
            :role-label="accountRoleLabel"
            :identity-busy="identityBusy"
            :identity-error="identityError"
            :identity-success="identitySuccess"
            :password-busy="passwordBusy"
            :password-error="passwordError"
            :password-success="passwordSuccess"
            @save-identity="saveIdentity"
            @save-password="savePassword"
          />
          <div
            v-else-if="loading"
            class="content-loading"
            :aria-label="t('settings.loadingImportersAria')"
          >
            <i /><i /><i />
          </div>
          <article v-else-if="error" class="settings-error" role="alert">
            <div>
              <strong>{{ t("settings.catalogLoadError") }}</strong>
              <p>{{ error }}</p>
            </div>
            <button type="button" @click="load">{{ t("common.retry") }}</button>
          </article>
          <SettingsImporterDocument
            v-else-if="selectedImporter"
            :selected-importer="selectedImporter"
          />
        </main>
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings-overlay {
  position: fixed;
  z-index: 100;
  inset: 0;
  padding: 24px;
  display: grid;
  place-items: center;
  background: rgba(5, 10, 7, 0.48);
  backdrop-filter: blur(10px) saturate(0.82);
  animation: overlay-in 0.18s ease-out;
}
.settings-modal {
  width: min(1320px, calc(100vw - 48px));
  height: min(820px, calc(100vh - 48px));
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 24px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 32px 90px rgba(3, 10, 6, 0.28);
  animation: modal-in 0.22s ease-out;
}
.settings-modal-header {
  height: 70px;
  padding: 0 20px 0 25px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--fz-line);
}
.settings-modal-header p {
  margin: 0 0 2px;
  color: var(--fz-accent);
  font-size: 7px;
  font-weight: 800;
  letter-spacing: 0.15em;
  text-transform: uppercase;
}
.settings-modal-header h2 {
  margin: 0;
  font-size: 20px;
  letter-spacing: -0.04em;
}
.settings-modal-header button {
  width: 38px;
  height: 38px;
  border: 1px solid var(--fz-line);
  border-radius: 11px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  font-size: 21px;
  cursor: pointer;
}
.settings-layout {
  height: calc(100% - 70px);
  display: grid;
  grid-template-columns: 190px 260px minmax(0, 1fr);
}
.settings-primary,
.settings-secondary {
  min-height: 0;
  border-right: 1px solid var(--fz-line);
  background: color-mix(in srgb, var(--fz-surface-soft) 62%, var(--fz-surface));
}
.settings-primary {
  padding: 22px 14px;
  display: flex;
  flex-direction: column;
}
.settings-primary > p,
.settings-secondary > header p {
  margin: 0;
  color: var(--fz-muted);
  font-size: 7px;
  font-weight: 760;
  letter-spacing: 0.11em;
  text-transform: uppercase;
}
.settings-primary > p {
  padding: 0 9px 12px;
}
.settings-primary > button {
  width: 100%;
  padding: 11px;
  display: grid;
  grid-template-columns: 32px 1fr;
  gap: 1px 9px;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  color: var(--fz-muted);
  text-align: left;
  cursor: pointer;
}
.settings-primary > button.active {
  border-color: color-mix(in srgb, var(--fz-accent) 20%, var(--fz-line));
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 8px 24px rgba(25, 45, 34, 0.06);
}
.settings-primary > button > span {
  grid-row: 1/3;
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
}
.settings-primary > button strong {
  font-size: 9px;
}
.settings-primary > button small {
  color: var(--fz-muted);
  font-size: 7px;
}
.settings-primary footer {
  margin-top: auto;
  padding: 13px 9px 2px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid var(--fz-line);
}
.settings-primary footer > span {
  color: var(--fz-accent);
  font:
    700 8px ui-monospace,
    monospace;
}
.settings-primary footer p {
  margin: 0;
  display: grid;
  color: var(--fz-muted);
  font-size: 7px;
}
.settings-primary footer strong {
  color: var(--fz-ink);
}
.settings-secondary {
  padding: 22px 12px;
}
.settings-secondary > header {
  padding: 0 9px 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.settings-secondary > header span {
  padding: 3px 6px;
  border-radius: 99px;
  background: var(--fz-surface);
  color: var(--fz-muted);
  font-size: 7px;
}
.settings-secondary > button {
  width: 100%;
  padding: 10px 9px;
  display: grid;
  grid-template-columns: 31px minmax(0, 1fr) 12px;
  align-items: center;
  gap: 9px;
  border: 0;
  border-radius: 11px;
  background: transparent;
  color: var(--fz-muted);
  text-align: left;
  cursor: pointer;
}
.settings-secondary > button + button {
  margin-top: 3px;
}
.settings-secondary > button:hover {
  background: color-mix(in srgb, var(--fz-surface) 68%, transparent);
}
.settings-secondary > button.active {
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow:
    inset 3px 0 var(--fz-accent),
    0 6px 18px rgba(25, 45, 34, 0.05);
}
.settings-secondary > button > span {
  width: 31px;
  height: 31px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
  font-size: 7px;
  font-weight: 820;
}
.settings-secondary > button p {
  min-width: 0;
  margin: 0;
  display: grid;
  gap: 2px;
}
.settings-secondary > button strong,
.settings-secondary > button small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.settings-secondary > button strong {
  font-size: 8px;
}
.settings-secondary > button small {
  color: var(--fz-muted);
  font-size: 7px;
}
.settings-secondary > button > i {
  font-style: normal;
  font-size: 15px;
}
.settings-content {
  min-width: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
}
.settings-error {
  margin: 30px;
  padding: 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid var(--fz-line);
  border-radius: 14px;
}
.settings-error p {
  margin: 4px 0 0;
  color: var(--fz-muted);
  font-size: 8px;
}
.settings-error button {
  padding: 8px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-ink);
}
.importer-nav-loading {
  display: grid;
  gap: 7px;
}
.importer-nav-loading i {
  height: 50px;
  border-radius: 10px;
  background: var(--fz-surface);
}
.content-loading {
  padding: 30px;
  display: grid;
  gap: 14px;
}
.content-loading i {
  height: 85px;
  border-radius: 13px;
  background: var(--fz-surface-soft);
}
.content-loading i:nth-child(2) {
  height: 190px;
}
.content-loading i:nth-child(3) {
  height: 280px;
}
@keyframes overlay-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
@keyframes modal-in {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.99);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  .settings-overlay,
  .settings-modal {
    animation: none;
  }
}
@media (max-width: 980px) {
  .settings-layout {
    grid-template-columns: 150px 220px minmax(0, 1fr);
  }
  .settings-primary {
    padding-inline: 9px;
  }
}
@media (max-width: 720px) {
  .settings-overlay {
    padding: 10px;
  }
  .settings-modal {
    width: calc(100vw - 20px);
    height: calc(100vh - 20px);
    border-radius: 17px;
  }
  .settings-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto minmax(0, 1fr);
  }
  .settings-primary,
  .settings-secondary {
    border-right: 0;
    border-bottom: 1px solid var(--fz-line);
  }
  .settings-primary {
    padding: 10px;
    display: block;
  }
  .settings-primary > p,
  .settings-primary footer {
    display: none;
  }
  .settings-primary > button {
    max-width: 180px;
  }
  .settings-secondary {
    padding: 9px;
    overflow-x: auto;
    display: flex;
    gap: 5px;
  }
  .settings-secondary > header {
    display: none;
  }
  .settings-secondary > button {
    min-width: 190px;
    margin: 0 !important;
  }
}
.settings-secondary {
  display: flex;
  flex-direction: column;
}
.importer-groups {
  min-height: 0;
  overflow-y: auto;
}
.importer-group + .importer-group {
  margin-top: 17px;
}
.importer-group > header {
  padding: 0 9px 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.importer-group > header h3 {
  margin: 0;
  color: var(--fz-muted);
  font-size: 7px;
  font-weight: 760;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.importer-group > header span {
  color: var(--fz-muted);
  font-size: 6px;
}
.importer-group > button {
  width: 100%;
  padding: 10px 9px;
  display: grid;
  grid-template-columns: 31px minmax(0, 1fr) 12px;
  align-items: center;
  gap: 9px;
  border: 0;
  border-radius: 11px;
  background: transparent;
  color: var(--fz-muted);
  text-align: left;
  cursor: pointer;
}
.importer-group > button + button {
  margin-top: 3px;
}
.importer-group > button:hover {
  background: color-mix(in srgb, var(--fz-surface) 68%, transparent);
}
.importer-group > button.active {
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow:
    inset 3px 0 var(--fz-accent),
    0 6px 18px rgba(25, 45, 34, 0.05);
}
.importer-group > button > span {
  width: 31px;
  height: 31px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
  font-size: 7px;
  font-weight: 820;
}
.importer-group > button p {
  min-width: 0;
  margin: 0;
  display: grid;
  gap: 2px;
}
.importer-group > button strong,
.importer-group > button small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.importer-group > button strong {
  font-size: 8px;
}
.importer-group > button small {
  color: var(--fz-muted);
  font-size: 7px;
}
.importer-group > button > i {
  font-style: normal;
  font-size: 15px;
}
.importer-count {
  margin-top: auto;
  padding: 13px 9px 2px;
  display: flex;
  align-items: center;
  gap: 7px;
  border-top: 1px solid var(--fz-line);
  color: var(--fz-muted);
  font-size: 7px;
}
.importer-count i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--fz-accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 12%, transparent);
}
@media (max-width: 720px) {
  .settings-secondary {
    display: block;
    overflow-x: auto;
  }
  .settings-secondary > header,
  .importer-count {
    display: none;
  }
  .importer-groups {
    display: flex;
    gap: 13px;
    overflow: visible;
  }
  .importer-group {
    min-width: max-content;
  }
  .importer-group + .importer-group {
    margin-top: 0;
  }
  .importer-group > header {
    padding-bottom: 4px;
  }
  .importer-group > button {
    min-width: 190px;
  }
}
.settings-primary > button + button {
  margin-top: 5px;
}
.account-access-state {
  margin-top: auto;
  padding: 13px 9px 2px;
  display: flex;
  align-items: center;
  gap: 7px;
  border-top: 1px solid var(--fz-line);
  color: var(--fz-muted);
  font-size: 7px;
}
.account-access-state i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--fz-accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 12%, transparent);
}
/* Settings type scale: dense data without dropping below 10 px. */
.settings-layout {
  grid-template-columns: 220px 290px minmax(0, 1fr);
}
.settings-modal-header p,
.settings-primary > p,
.settings-secondary > header p,
.settings-primary > button small,
.settings-primary footer p,
.settings-secondary > header span,
.settings-secondary > button > span,
.settings-secondary > button small,
.importer-group > header h3,
.importer-group > header span,
.importer-group > button > span,
.importer-group > button small,
.importer-count,
.account-access-state {
  font-size: 10px;
}
.settings-primary > button strong,
.settings-secondary > button strong,
.settings-error p,
.importer-group > button strong {
  font-size: 11px;
}
.settings-primary footer > span {
  font-size: 11px;
}
.settings-modal-header h2 {
  font-size: 22px;
}
@media (max-width: 1100px) {
  .settings-layout {
    grid-template-columns: 190px 250px minmax(0, 1fr);
  }
}
@media (max-width: 720px) {
  .settings-layout {
    grid-template-columns: 1fr;
  }
  .settings-primary > button {
    min-width: 185px;
  }
  .settings-secondary > button,
  .importer-group > button {
    min-width: 210px;
  }
}
.administration-document {
  min-height: 100%;
}
</style>
