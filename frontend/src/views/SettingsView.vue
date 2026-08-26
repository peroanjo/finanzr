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
const accountDisplayName = ref("");
const accountEmail = ref("");
const identityPassword = ref("");
const identityBusy = ref(false);
const identityError = ref("");
const identitySuccess = ref("");
const currentPassword = ref("");
const newPassword = ref("");
const passwordConfirmation = ref("");
const passwordBusy = ref(false);
const passwordError = ref("");
const passwordSuccess = ref("");
const languageBusy = ref(false);
const languageError = ref("");
const languageSuccess = ref("");
const installationLanguage = ref<"es-ES" | "en">("es-ES");
const installationLanguageBusy = ref(false);
const installationLanguageError = ref("");
const installationLanguageSuccess = ref("");
const defaultCrowdfundingTaxRate = ref(19);
const crowdfundingTaxBusy = ref(false);
const crowdfundingTaxError = ref("");
const crowdfundingTaxSuccess = ref("");
const summarySources = ref<SummarySourceKey[]>([]);
const selectedAvailableSources = ref<SummarySourceKey[]>([]);
const selectedIncludedSources = ref<SummarySourceKey[]>([]);
const summarySourceRefs = {
  available: {} as Record<string, HTMLButtonElement>,
  included: {} as Record<string, HTMLButtonElement>,
};
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
const summaryAvailableSources = computed(() =>
  summarySourceKeys.filter((key) => !summarySources.value.includes(key)),
);
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
const installationLanguageName = computed(() =>
  installationLanguage.value === "en"
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

watch(importers, (items) => {
  if (!items.some((item) => item.slug === selectedSlug.value)) {
    selectedSlug.value = items[0]?.slug ?? "";
  }
});
watch(
  () => session.user?.email,
  (email) => {
    accountEmail.value = email ?? "";
  },
  { immediate: true },
);
watch(
  () => session.user?.display_name,
  (name) => {
    accountDisplayName.value = name ?? "";
  },
  { immediate: true },
);
watch(
  sessionDefaultLanguage,
  (language) => {
    installationLanguage.value = language === "en" ? "en" : "es-ES";
  },
  { immediate: true },
);
watch(
  sessionDefaultCrowdfundingTaxRate,
  (rate) => {
    if (rate !== undefined && rate !== null) {
      defaultCrowdfundingTaxRate.value = rate;
    }
  },
  { immediate: true },
);
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
    selectedAvailableSources.value = [];
    selectedIncludedSources.value = [];
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

async function saveIdentity() {
  identityError.value = "";
  identitySuccess.value = "";
  identityBusy.value = true;
  try {
    await session.updateAccount(
      accountDisplayName.value,
      accountEmail.value,
      identityPassword.value,
    );
    identityPassword.value = "";
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

async function savePassword() {
  passwordError.value = "";
  passwordSuccess.value = "";
  if (newPassword.value !== passwordConfirmation.value) {
    passwordError.value = t("settings.passwordMismatch");
    return;
  }
  passwordBusy.value = true;
  try {
    await session.changePassword(
      currentPassword.value,
      newPassword.value,
      passwordConfirmation.value,
    );
    currentPassword.value = "";
    newPassword.value = "";
    passwordConfirmation.value = "";
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

async function saveInstallationLanguage() {
  installationLanguageError.value = "";
  installationLanguageSuccess.value = "";
  installationLanguageBusy.value = true;
  try {
    const result = await api<{
      default_language: "es-ES" | "en";
      language: "es-ES" | "en";
    }>(
      "/installation/preferences",
      json("PATCH", { default_language: installationLanguage.value }),
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

async function saveCrowdfundingTax() {
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
        default_crowdfunding_tax_rate: Number(defaultCrowdfundingTaxRate.value),
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

function toggleSummarySource(
  side: "available" | "included",
  key: SummarySourceKey,
) {
  const target =
    side === "available" ? selectedAvailableSources : selectedIncludedSources;
  target.value = target.value.includes(key)
    ? target.value.filter((item) => item !== key)
    : [...target.value, key];
}

function setSummarySourceRef(
  side: "available" | "included",
  key: SummarySourceKey,
  element: unknown,
) {
  if (element && typeof (element as { focus?: unknown }).focus === "function") {
    summarySourceRefs[side][key] = element as HTMLButtonElement;
  } else delete summarySourceRefs[side][key];
}

function summarySourceSideKeys(side: "available" | "included") {
  return side === "available"
    ? summaryAvailableSources.value
    : summarySources.value;
}

function focusSummarySource(side: "available" | "included", index: number) {
  const key = summarySourceSideKeys(side)[index];
  if (!key) return;
  nextTick(() => {
    const referenced = summarySourceRefs[side][key];
    if (referenced) {
      referenced.focus();
      return;
    }
    const selector =
      side === "available"
        ? ".summary-source-column:not(.included) .summary-source-option"
        : ".summary-source-column.included .summary-source-option";
    (
      document.querySelectorAll(selector)[index] as HTMLElement | undefined
    )?.focus();
  });
}

function onSummarySourceKeydown(
  event: KeyboardEvent,
  side: "available" | "included",
  key: SummarySourceKey,
) {
  const keys = summarySourceSideKeys(side);
  const index = keys.indexOf(key);
  if (index < 0) return;
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    toggleSummarySource(side, key);
    return;
  }
  const nextIndex =
    event.key === "ArrowDown"
      ? Math.min(keys.length - 1, index + 1)
      : event.key === "ArrowUp"
        ? Math.max(0, index - 1)
        : event.key === "Home"
          ? 0
          : event.key === "End"
            ? keys.length - 1
            : -1;
  if (nextIndex >= 0) {
    event.preventDefault();
    focusSummarySource(side, nextIndex);
  }
}

function moveSelectedSummarySources(direction: "in" | "out") {
  const moving =
    direction === "in"
      ? [...selectedAvailableSources.value]
      : [...selectedIncludedSources.value];
  if (direction === "in") {
    const movingKeys = new Set(moving);
    summarySources.value = summarySourceKeys.filter(
      (key) => summarySources.value.includes(key) || movingKeys.has(key),
    );
    selectedAvailableSources.value = [];
  } else {
    const movingKeys = new Set(moving);
    summarySources.value = summarySources.value.filter(
      (key) => !movingKeys.has(key),
    );
    selectedIncludedSources.value = [];
  }
  const targetSide = direction === "in" ? "included" : "available";
  const targetKeys = summarySourceSideKeys(targetSide);
  const targetIndex = targetKeys.findIndex((key) => key === moving[0]);
  if (targetIndex >= 0) focusSummarySource(targetSide, targetIndex);
}

async function saveSummarySources() {
  if (summarySourcesBusy.value || !canManageAccount.value) return;
  summarySourcesBusy.value = true;
  summarySourcesError.value = "";
  summarySourcesSuccess.value = "";
  try {
    await session.updateSummarySources(summarySources.value);
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
          <article
            v-if="
              activeSection === 'sections' && activeProductSection === 'summary'
            "
            class="interface-document summary-sources-document"
          >
            <header class="interface-document-header">
              <div>
                <p>{{ t("settings.summarySources") }}</p>
                <h3>{{ t("settings.summarySources") }}</h3>
                <span>{{ t("settings.summarySourcesDescription") }}</span>
              </div>
              <div
                class="effective-language summary-source-status"
                aria-live="polite"
              >
                <span aria-hidden="true">Σ</span>
                <p>
                  <small>{{ t("settings.summarySourcesAria") }}</small
                  ><strong
                    >{{ summarySources.length }} /
                    {{ summarySourceKeys.length }}</strong
                  >
                </p>
                <i />
              </div>
            </header>

            <section
              class="summary-sources-panel"
              :aria-labelledby="'summary-sources-title'"
            >
              <header>
                <div>
                  <p>{{ summaryScopeLabel }}</p>
                  <h4 id="summary-sources-title">
                    {{ t("settings.summarySources") }}
                  </h4>
                </div>
                <span>{{ summarySources.length }}</span>
              </header>
              <p class="document-description">
                {{ t("settings.summarySourcesHint") }}
              </p>
              <div
                class="summary-transfer"
                :aria-label="t('settings.summarySourcesAria')"
              >
                <section class="summary-source-column">
                  <header>
                    <strong>{{ t("settings.summarySourcesAvailable") }}</strong
                    ><small>{{ summaryAvailableSources.length }}</small>
                  </header>
                  <div
                    class="summary-source-list"
                    role="listbox"
                    :aria-label="t('settings.summarySourcesAvailableAria')"
                    aria-multiselectable="true"
                  >
                    <button
                      v-for="key in summaryAvailableSources"
                      :key="key"
                      type="button"
                      role="option"
                      class="summary-source-option"
                      :class="{
                        selected: selectedAvailableSources.includes(key),
                      }"
                      :aria-selected="selectedAvailableSources.includes(key)"
                      @keydown="
                        onSummarySourceKeydown($event, 'available', key)
                      "
                      :ref="
                        (element) =>
                          setSummarySourceRef('available', key, element)
                      "
                      :disabled="!canManageAccount || summarySourcesBusy"
                      @click="toggleSummarySource('available', key)"
                    >
                      <span class="summary-source-mark" aria-hidden="true">{{
                        key.slice(0, 1).toUpperCase()
                      }}</span>
                      <span>{{ t(`overview.sources.${key}`) }}</span>
                    </button>
                    <p
                      v-if="!summaryAvailableSources.length"
                      class="summary-source-empty"
                    >
                      {{ t("common.noData") }}
                    </p>
                  </div>
                </section>
                <div class="summary-transfer-rail" aria-hidden="true">
                  <span /><i /><span />
                </div>
                <div class="summary-transfer-actions">
                  <button
                    type="button"
                    class="summary-transfer-button"
                    :aria-label="t('settings.summarySourcesMoveIn')"
                    :title="t('settings.summarySourcesMoveIn')"
                    :disabled="
                      !selectedAvailableSources.length ||
                      !canManageAccount ||
                      summarySourcesBusy
                    "
                    @click="moveSelectedSummarySources('in')"
                  >
                    <svg viewBox="0 0 24 24">
                      <path d="M5 12h13m-5-5 5 5-5 5" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    class="summary-transfer-button"
                    :aria-label="t('settings.summarySourcesMoveOut')"
                    :title="t('settings.summarySourcesMoveOut')"
                    :disabled="
                      !selectedIncludedSources.length ||
                      !canManageAccount ||
                      summarySourcesBusy
                    "
                    @click="moveSelectedSummarySources('out')"
                  >
                    <svg viewBox="0 0 24 24">
                      <path d="M19 12H6m5-5-5 5 5 5" />
                    </svg>
                  </button>
                </div>
                <section class="summary-source-column included">
                  <header>
                    <strong>{{ t("settings.summarySourcesIncluded") }}</strong
                    ><small>{{ summarySources.length }}</small>
                  </header>
                  <div
                    class="summary-source-list"
                    role="listbox"
                    :aria-label="t('settings.summarySourcesIncludedAria')"
                    aria-multiselectable="true"
                  >
                    <button
                      v-for="key in summarySources"
                      :key="key"
                      type="button"
                      role="option"
                      class="summary-source-option"
                      :class="{
                        selected: selectedIncludedSources.includes(key),
                      }"
                      :aria-selected="selectedIncludedSources.includes(key)"
                      @keydown="onSummarySourceKeydown($event, 'included', key)"
                      :ref="
                        (element) =>
                          setSummarySourceRef('included', key, element)
                      "
                      :disabled="!canManageAccount || summarySourcesBusy"
                      @click="toggleSummarySource('included', key)"
                    >
                      <span class="summary-source-mark" aria-hidden="true">{{
                        key.slice(0, 1).toUpperCase()
                      }}</span>
                      <span>{{ t(`overview.sources.${key}`) }}</span>
                    </button>
                    <p
                      v-if="!summarySources.length"
                      class="summary-source-empty"
                    >
                      {{ t("common.noData") }}
                    </p>
                  </div>
                </section>
              </div>
              <footer class="summary-sources-footer">
                <p v-if="!canManageAccount" class="language-feedback muted">
                  {{ t("settings.demoLanguageNotice") }}
                </p>
                <p
                  v-if="summarySourcesError"
                  class="language-feedback error"
                  role="alert"
                >
                  {{ summarySourcesError }}
                </p>
                <p
                  v-else-if="summarySourcesSuccess"
                  class="language-feedback success"
                  role="status"
                >
                  {{ summarySourcesSuccess }}
                </p>
                <button
                  type="button"
                  class="summary-sources-save"
                  :disabled="summarySourcesBusy || !canManageAccount"
                  @click="saveSummarySources"
                >
                  {{
                    summarySourcesBusy
                      ? t("common.saving")
                      : t("settings.summarySourcesSave")
                  }}
                </button>
              </footer>
            </section>
          </article>
          <article
            v-else-if="activeSection === 'interface'"
            class="interface-document"
          >
            <header class="interface-document-header">
              <div>
                <p>{{ t("settings.interfaceEyebrow") }}</p>
                <h3>{{ t("settings.interfaceLanguageTitle") }}</h3>
                <span>{{ t("settings.interfaceLanguageIntro") }}</span>
              </div>
              <div class="effective-language" aria-live="polite">
                <span aria-hidden="true">{{ effectiveLanguageFlag }}</span>
                <p>
                  <small>{{ t("settings.effectiveLanguage") }}</small
                  ><strong>{{ effectiveLanguageName }}</strong>
                </p>
                <i />
              </div>
            </header>

            <section
              class="language-preference-panel"
              :aria-labelledby="'personal-language-title'"
            >
              <header>
                <div>
                  <p>{{ t("settings.personalPreference") }}</p>
                  <h4 id="personal-language-title">
                    {{ t("settings.chooseLanguage") }}
                  </h4>
                </div>
                <span>{{
                  session.user?.preferred_language
                    ? t("settings.personalOverride")
                    : t("settings.followingInstallation")
                }}</span>
              </header>
              <div
                class="language-choice-grid"
                role="radiogroup"
                :aria-label="t('settings.languageTitle')"
              >
                <button
                  v-for="option in personalLanguageOptions"
                  :key="option.code || 'automatic'"
                  type="button"
                  class="language-choice"
                  :class="{
                    selected:
                      (session.user?.preferred_language ?? '') === option.code,
                  }"
                  :aria-checked="
                    (session.user?.preferred_language ?? '') === option.code
                  "
                  :disabled="languageBusy || !canManageAccount"
                  role="radio"
                  @click="saveLanguage(option.code)"
                >
                  <span class="language-flag" aria-hidden="true">{{
                    option.flag
                  }}</span>
                  <span class="language-copy"
                    ><strong>{{ option.title }}</strong
                    ><small>{{ option.native }}</small></span
                  >
                  <i class="language-check" aria-hidden="true">✓</i>
                  <em>{{ option.description }}</em>
                </button>
              </div>
              <p
                v-if="languageError"
                class="language-feedback error"
                role="alert"
              >
                {{ languageError }}
              </p>
              <p
                v-else-if="languageSuccess"
                class="language-feedback success"
                role="status"
              >
                {{ languageSuccess }}
              </p>
              <p v-if="!canManageAccount" class="language-feedback muted">
                {{ t("settings.demoLanguageNotice") }}
              </p>
            </section>

            <form
              v-if="canAdminister"
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
                  v-for="option in supportedLocales"
                  :key="option.code"
                  :class="{ selected: installationLanguage === option.code }"
                >
                  <input
                    v-model="installationLanguage"
                    type="radio"
                    name="installation-language"
                    :value="option.code"
                  />
                  <span aria-hidden="true">{{
                    option.code === "en" ? "🇬🇧" : "🇪🇸"
                  }}</span>
                  <strong>{{ option.label }}</strong>
                </label>
                <button type="submit" :disabled="installationLanguageBusy">
                  {{
                    installationLanguageBusy
                      ? t("common.saving")
                      : t("settings.saveInstallationLanguage")
                  }}
                </button>
              </div>
              <p
                v-if="installationLanguageError"
                class="language-feedback error"
                role="alert"
              >
                {{ installationLanguageError }}
              </p>
              <p
                v-else-if="installationLanguageSuccess"
                class="language-feedback success"
                role="status"
              >
                {{ installationLanguageSuccess }}
              </p>
            </form>
          </article>

          <article
            v-else-if="
              activeSection === 'sections' &&
              activeProductSection === 'crowdfunding'
            "
            class="interface-document"
          >
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
                  ><strong>{{ defaultCrowdfundingTaxRate }} %</strong>
                </p>
                <i aria-hidden="true" />
              </div>
            </header>

            <form
              class="language-preference-panel"
              @submit.prevent="saveCrowdfundingTax"
            >
              <header>
                <div>
                  <p>{{ t("settings.crowdfunding") }}</p>
                  <h4>{{ t("settings.crowdfundingTaxTitle") }}</h4>
                </div>
                <span>{{ t("settings.installationPreference") }}</span>
              </header>
              <p class="document-description">
                {{ t("settings.crowdfundingTaxHelp") }}
              </p>

              <div class="withholding-form-row">
                <label class="tax-rate-field">
                  <span>{{ t("settings.defaultCrowdfundingTaxRate") }}</span>
                  <div class="tax-rate-input-wrap">
                    <input
                      v-model.number="defaultCrowdfundingTaxRate"
                      type="number"
                      min="0"
                      max="100"
                      step="0.1"
                      :disabled="!canAdminister || crowdfundingTaxBusy"
                      required
                    />
                    <strong>%</strong>
                  </div>
                </label>
                <button
                  v-if="canAdminister"
                  type="submit"
                  :disabled="crowdfundingTaxBusy"
                >
                  {{
                    crowdfundingTaxBusy
                      ? t("common.saving")
                      : t("settings.saveCrowdfundingTax")
                  }}
                </button>
              </div>

              <p v-if="!canAdminister" class="language-feedback muted">
                {{ t("settings.adminsOnlyWithholdingNotice") }}
              </p>
              <p
                v-if="crowdfundingTaxError"
                class="language-feedback error"
                role="alert"
              >
                {{ crowdfundingTaxError }}
              </p>
              <p
                v-else-if="crowdfundingTaxSuccess"
                class="language-feedback success"
                role="status"
              >
                {{ crowdfundingTaxSuccess }}
              </p>
            </form>
          </article>
          <div
            v-else-if="activeSection === 'administration'"
            class="administration-document"
          >
            <AdminUsersPanel />
          </div>
          <article
            v-else-if="activeSection === 'account'"
            class="account-document"
          >
            <header class="account-document-header">
              <div>
                <p>{{ t("settings.identityAndAccess") }}</p>
                <h3>{{ t("settings.yourAccount") }}</h3>
              </div>
              <span>{{ accountRoleLabel }}</span>
            </header>
            <p class="account-intro">{{ t("settings.accountIntro") }}</p>

            <div class="account-form-grid">
              <form class="account-form-card" @submit.prevent="saveIdentity">
                <header>
                  <span aria-hidden="true">@</span>
                  <div>
                    <p>{{ t("settings.identification") }}</p>
                    <h4>{{ t("settings.profileAndEmail") }}</h4>
                  </div>
                </header>
                <p>{{ t("settings.identityHelp") }}</p>
                <label>
                  <span>{{ t("settings.displayName") }}</span>
                  <input
                    v-model.trim="accountDisplayName"
                    type="text"
                    autocomplete="name"
                    maxlength="120"
                  />
                </label>
                <label>
                  <span>{{ t("settings.email") }}</span>
                  <input
                    v-model.trim="accountEmail"
                    type="email"
                    autocomplete="email"
                    required
                  />
                </label>
                <label>
                  <span>{{ t("settings.currentPassword") }}</span>
                  <input
                    v-model="identityPassword"
                    type="password"
                    autocomplete="current-password"
                    required
                  />
                </label>
                <p
                  v-if="identityError"
                  class="account-form-message error"
                  role="alert"
                >
                  {{ identityError }}
                </p>
                <p
                  v-else-if="identitySuccess"
                  class="account-form-message success"
                  role="status"
                >
                  {{ identitySuccess }}
                </p>
                <button type="submit" :disabled="identityBusy">
                  {{
                    identityBusy
                      ? t("common.saving")
                      : t("settings.saveProfile")
                  }}
                </button>
              </form>

              <form class="account-form-card" @submit.prevent="savePassword">
                <header>
                  <span aria-hidden="true">••</span>
                  <div>
                    <p>{{ t("settings.security") }}</p>
                    <h4>{{ t("settings.password") }}</h4>
                  </div>
                </header>
                <p>{{ t("settings.passwordHelp") }}</p>
                <label>
                  <span>{{ t("settings.currentPassword") }}</span>
                  <input
                    v-model="currentPassword"
                    type="password"
                    autocomplete="current-password"
                    required
                  />
                </label>
                <label>
                  <span>{{ t("settings.newPassword") }}</span>
                  <input
                    v-model="newPassword"
                    type="password"
                    autocomplete="new-password"
                    minlength="12"
                    required
                  />
                </label>
                <label>
                  <span>{{ t("settings.repeatNewPassword") }}</span>
                  <input
                    v-model="passwordConfirmation"
                    type="password"
                    autocomplete="new-password"
                    minlength="12"
                    required
                  />
                </label>
                <p
                  v-if="passwordError"
                  class="account-form-message error"
                  role="alert"
                >
                  {{ passwordError }}
                </p>
                <p
                  v-else-if="passwordSuccess"
                  class="account-form-message success"
                  role="status"
                >
                  {{ passwordSuccess }}
                </p>
                <button type="submit" :disabled="passwordBusy">
                  {{
                    passwordBusy
                      ? t("settings.updating")
                      : t("settings.changePassword")
                  }}
                </button>
              </form>
            </div>
          </article>
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
          <article v-else-if="selectedImporter" class="importer-document">
            <header class="document-header">
              <div>
                <p>
                  {{
                    t("settings.importContract", {
                      target: selectedImporter.target_label,
                    })
                  }}
                </p>
                <h3>{{ selectedImporter.display_name }}</h3>
                <span><i /> {{ t("common.configured") }}</span>
              </div>
              <code>{{ selectedImporter.slug }}</code>
            </header>

            <p class="document-description">
              {{ selectedImporter.description }}
            </p>
            <div class="source-note">
              <span aria-hidden="true">↓</span>
              <p>
                <strong>{{ t("settings.howToGetIt") }}</strong
                >{{ selectedImporter.source_instructions }}
              </p>
            </div>

            <section class="document-section">
              <header>
                <div>
                  <p>01</p>
                  <h4>{{ t("settings.supportedFormats") }}</h4>
                </div>
                <span>{{ selectedImporter.formats.length }}</span>
              </header>
              <div class="format-grid">
                <div
                  v-for="format in selectedImporter.formats"
                  :key="format.extension"
                >
                  <span>{{
                    format.extension.replace(".", "").toUpperCase()
                  }}</span>
                  <p>
                    <strong>{{ format.label }}</strong
                    ><small>{{ format.description }}</small>
                  </p>
                </div>
              </div>
            </section>

            <section class="document-section fields-section">
              <header>
                <div>
                  <p>02</p>
                  <h4>{{ t("settings.expectedStructure") }}</h4>
                </div>
                <span>{{
                  t("settings.fieldsSummary", {
                    fields: selectedImporter.fields.length,
                    required: selectedImporter.required_fields.length,
                  })
                }}</span>
              </header>
              <div class="field-table">
                <div class="field-head">
                  <span>{{ t("settings.field") }}</span
                  ><span>{{ t("settings.expectedContent") }}</span
                  ><span>{{ t("settings.example") }}</span>
                </div>
                <div
                  v-for="field in selectedImporter.fields"
                  :key="field.name"
                  class="field-row"
                >
                  <div>
                    <b v-if="field.position">{{
                      String(field.position).padStart(2, "0")
                    }}</b>
                    <span
                      ><strong>{{ field.label }}</strong
                      ><code>{{ field.name }}</code></span
                    >
                  </div>
                  <p>
                    {{ field.description }}
                    <em>{{
                      field.required
                        ? t("common.required")
                        : t("common.optional")
                    }}</em>
                  </p>
                  <code>{{ field.example }}</code>
                </div>
              </div>
            </section>

            <section class="document-section rules-section">
              <header>
                <div>
                  <p>03</p>
                  <h4>{{ t("settings.importerRules") }}</h4>
                </div>
              </header>
              <ul>
                <li v-for="rule in selectedImporter.rules" :key="rule">
                  {{ rule }}
                </li>
              </ul>
            </section>
          </article>
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
.importer-document {
  padding: 29px 34px 42px;
}
.document-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 22px;
}
.document-header p {
  margin: 0 0 6px;
  color: var(--fz-muted);
  font-size: 7px;
  font-weight: 760;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.document-header h3 {
  display: inline;
  margin: 0;
  font-size: 25px;
  letter-spacing: -0.045em;
}
.document-header > div > span {
  margin-left: 10px;
  padding: 5px 8px;
  border-radius: 99px;
  background: color-mix(in srgb, var(--fz-accent) 9%, transparent);
  color: var(--fz-accent);
  font-size: 6px;
  font-weight: 780;
  vertical-align: 4px;
}
.document-header > div > span i {
  width: 5px;
  height: 5px;
  display: inline-block;
  margin-right: 4px;
  border-radius: 50%;
  background: currentColor;
}
.document-header > code {
  padding: 6px 8px;
  border-radius: 7px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  font-size: 7px;
}
.document-description {
  max-width: 720px;
  margin: 13px 0 0;
  font-size: 10px;
  line-height: 1.6;
}
.source-note {
  margin-top: 16px;
  padding: 12px 14px;
  display: flex;
  gap: 10px;
  border-left: 3px solid var(--fz-accent);
  background: color-mix(in srgb, var(--fz-accent) 5%, transparent);
}
.source-note > span {
  color: var(--fz-accent);
  font-size: 15px;
}
.source-note p {
  margin: 0;
  display: grid;
  gap: 3px;
  color: var(--fz-muted);
  font-size: 8px;
  line-height: 1.5;
}
.source-note strong {
  color: var(--fz-ink);
  font-size: 7px;
  text-transform: uppercase;
}
.document-section {
  margin-top: 27px;
}
.document-section > header {
  margin-bottom: 11px;
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 18px;
}
.document-section > header > div {
  display: flex;
  align-items: center;
  gap: 9px;
}
.document-section > header p {
  margin: 0;
  color: var(--fz-accent);
  font:
    750 8px ui-monospace,
    monospace;
}
.document-section h4 {
  margin: 0;
  font-size: 12px;
}
.document-section > header > span {
  color: var(--fz-muted);
  font-size: 7px;
}
.format-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.format-grid > div {
  padding: 11px;
  display: flex;
  align-items: flex-start;
  gap: 9px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
}
.format-grid > div > span {
  padding: 4px 6px;
  border-radius: 6px;
  background: var(--fz-surface);
  color: var(--fz-accent);
  font-size: 6px;
  font-weight: 820;
}
.format-grid p {
  margin: 0;
  display: grid;
  gap: 3px;
}
.format-grid strong {
  font-size: 8px;
}
.format-grid small {
  color: var(--fz-muted);
  font-size: 7px;
  line-height: 1.4;
}
.field-table {
  overflow-x: auto;
  border-top: 1px solid var(--fz-line);
}
.field-head,
.field-row {
  min-width: 700px;
  display: grid;
  grid-template-columns: minmax(190px, 0.8fr) minmax(280px, 1.25fr) minmax(
      135px,
      0.6fr
    );
  gap: 12px;
  align-items: center;
}
.field-head {
  padding: 8px;
  color: var(--fz-muted);
  font-size: 6px;
  text-transform: uppercase;
}
.field-row {
  min-height: 55px;
  padding: 8px;
  border-top: 1px solid var(--fz-line);
}
.field-row > div {
  display: flex;
  align-items: center;
  gap: 7px;
}
.field-row b {
  width: 20px;
  color: var(--fz-muted);
  font-size: 6px;
}
.field-row > div span {
  display: grid;
  gap: 2px;
}
.field-row strong {
  font-size: 8px;
}
.field-row code {
  color: var(--fz-muted);
  font:
    600 7px ui-monospace,
    SFMono-Regular,
    Menlo,
    monospace;
}
.field-row > p {
  margin: 0;
  color: var(--fz-muted);
  font-size: 7px;
  line-height: 1.45;
}
.field-row em {
  margin-left: 4px;
  color: var(--fz-accent);
  font-size: 6px;
  font-style: normal;
  font-weight: 760;
  text-transform: uppercase;
}
.field-row > code {
  padding: 6px 7px;
  border-radius: 6px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  font-size: 7px;
}
.rules-section ul {
  margin: 0;
  padding: 13px 17px 13px 31px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  font-size: 8px;
  line-height: 1.7;
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
  .importer-document {
    padding-inline: 24px;
  }
  .format-grid {
    grid-template-columns: 1fr;
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
  .importer-document {
    padding: 22px 17px 34px;
  }
  .document-header {
    display: block;
  }
  .document-header > code {
    display: inline-block;
    margin-top: 10px;
  }
  .document-header h3 {
    font-size: 21px;
  }
  .field-head,
  .field-row {
    min-width: 650px;
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
.account-document {
  padding: 34px 38px 48px;
}
.account-document-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.account-document-header p {
  margin: 0 0 6px;
  color: var(--fz-muted);
  font-size: 7px;
  font-weight: 760;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.account-document-header h3 {
  margin: 0;
  font-size: 27px;
  letter-spacing: -0.045em;
}
.account-document-header > span {
  padding: 6px 9px;
  border: 1px solid color-mix(in srgb, var(--fz-accent) 24%, var(--fz-line));
  border-radius: 99px;
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
  font-size: 7px;
  font-weight: 780;
}
.account-intro {
  max-width: 650px;
  margin: 12px 0 0;
  color: var(--fz-muted);
  font-size: 9px;
  line-height: 1.6;
}
.account-form-grid {
  margin-top: 27px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  align-items: start;
}
.account-form-card {
  min-width: 0;
  padding: 19px;
  display: grid;
  gap: 13px;
  border: 1px solid var(--fz-line);
  border-radius: 16px;
  background: var(--fz-surface-soft);
}
.account-form-card > header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 13px;
  border-bottom: 1px solid var(--fz-line);
}
.account-form-card > header > span {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
  font-size: 10px;
  font-weight: 820;
}
.account-form-card > header div {
  display: grid;
  gap: 2px;
}
.account-form-card > header p {
  margin: 0;
  color: var(--fz-accent);
  font-size: 6px;
  font-weight: 780;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.account-form-card h4 {
  margin: 0;
  font-size: 13px;
  letter-spacing: -0.025em;
}
.account-form-card > p {
  min-height: 29px;
  margin: 0;
  color: var(--fz-muted);
  font-size: 8px;
  line-height: 1.55;
}
.account-form-card label {
  display: grid;
  gap: 6px;
}
.account-form-card label > span {
  color: var(--fz-muted);
  font-size: 7px;
  font-weight: 700;
}
.account-form-card input {
  width: 100%;
  height: 39px;
  padding: 0 11px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  outline: 0;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font: 600 9px inherit;
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease;
}
.account-form-card input:focus {
  border-color: color-mix(in srgb, var(--fz-accent) 58%, var(--fz-line));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 10%, transparent);
}
.account-form-card > button {
  justify-self: start;
  min-width: 130px;
  margin-top: 2px;
  padding: 10px 13px;
  border: 0;
  border-radius: 10px;
  background: var(--fz-accent);
  color: #092418;
  font-size: 8px;
  font-weight: 780;
  cursor: pointer;
}
.account-form-card > button:disabled {
  opacity: 0.55;
  cursor: wait;
}
.account-form-message {
  min-height: 0 !important;
  padding: 8px 10px;
  border-radius: 8px;
  font-weight: 680;
}
.account-form-message.error {
  background: color-mix(in srgb, var(--fz-negative) 9%, transparent);
  color: var(--fz-negative);
}
.account-form-message.success {
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
}
.account-form-card input {
  font-family: inherit;
  font-size: 9px;
  font-weight: 600;
}
@media (max-width: 1060px) {
  .account-form-grid {
    grid-template-columns: 1fr;
  }
  .account-document {
    padding-inline: 28px;
  }
}
@media (max-width: 720px) {
  .settings-primary {
    display: flex;
    gap: 5px;
    overflow-x: auto;
  }
  .settings-primary > button {
    min-width: 170px;
    margin: 0;
  }
  .account-access-state {
    display: none;
  }
  .account-document {
    padding: 22px 17px 34px;
  }
  .account-document-header h3 {
    font-size: 22px;
  }
  .account-form-grid {
    margin-top: 20px;
  }
  .account-form-card {
    padding: 16px;
  }
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
.document-header p,
.document-header > div > span,
.document-header > code,
.source-note strong,
.document-section > header p,
.document-section > header > span,
.format-grid > div > span,
.format-grid small,
.field-head,
.field-row b,
.field-row code,
.field-row em,
.field-row > code,
.importer-group > header h3,
.importer-group > header span,
.importer-group > button > span,
.importer-group > button small,
.importer-count,
.account-access-state,
.account-document-header p,
.account-document-header > span,
.account-form-card > header p {
  font-size: 10px;
}
.settings-primary > button strong,
.settings-secondary > button strong,
.source-note p,
.format-grid strong,
.field-row strong,
.field-row > p,
.rules-section ul,
.settings-error p,
.importer-group > button strong,
.account-form-card > p,
.account-form-card label > span,
.account-form-card > button,
.account-form-message {
  font-size: 11px;
}
.settings-primary footer > span {
  font-size: 11px;
}
.settings-modal-header h2 {
  font-size: 22px;
}
.document-header h3 {
  font-size: 28px;
}
.document-description,
.account-intro {
  font-size: 12px;
}
.document-section h4 {
  font-size: 15px;
}
.field-row {
  min-height: 64px;
}
.field-head,
.field-row {
  min-width: 780px;
  grid-template-columns: minmax(210px, 0.8fr) minmax(330px, 1.25fr) minmax(
      160px,
      0.6fr
    );
}
.account-document-header h3 {
  font-size: 29px;
}
.account-form-card h4 {
  font-size: 15px;
}
.account-form-card input {
  height: 43px;
  font-size: 12px;
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
  .document-header h3 {
    font-size: 23px;
  }
  .account-document-header h3 {
    font-size: 24px;
  }
  .field-head,
  .field-row {
    min-width: 720px;
  }
}
.administration-document {
  min-height: 100%;
}
.interface-document {
  min-height: 100%;
  padding: 36px 40px 48px;
  background: linear-gradient(
    145deg,
    color-mix(in srgb, var(--fz-accent) 3%, transparent),
    transparent 38%
  );
}
.interface-document-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}
.interface-document-header > div:first-child {
  max-width: 600px;
}
.interface-document-header p,
.language-preference-panel > header p,
.installation-language-copy p {
  margin: 0 0 6px;
  color: var(--fz-accent);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.interface-document-header h3 {
  margin: 0;
  font-size: 30px;
  letter-spacing: -0.05em;
}
.interface-document-header > div:first-child > span {
  display: block;
  max-width: 590px;
  margin-top: 11px;
  color: var(--fz-muted);
  font-size: 12px;
  line-height: 1.6;
}
.effective-language {
  min-width: 178px;
  padding: 12px 14px;
  display: grid;
  grid-template-columns: 40px 1fr 7px;
  align-items: center;
  gap: 10px;
  border: 1px solid color-mix(in srgb, var(--fz-accent) 24%, var(--fz-line));
  border-radius: 15px;
  background: var(--fz-surface);
  box-shadow: 0 12px 32px rgba(16, 44, 29, 0.07);
}
.effective-language > span {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: var(--fz-surface-soft);
  font-size: 24px;
  box-shadow: inset 0 0 0 1px var(--fz-line);
}
.effective-language p {
  margin: 0;
  display: grid;
  gap: 2px;
}
.effective-language small {
  color: var(--fz-muted);
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.effective-language strong {
  font-size: 12px;
}
.effective-language > i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--fz-accent);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--fz-accent) 12%, transparent);
}
.language-preference-panel {
  margin-top: 32px;
  padding: 22px;
  border: 1px solid var(--fz-line);
  border-radius: 20px;
  background: var(--fz-surface);
}
.language-preference-panel > header {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 17px;
}
.language-preference-panel h4,
.installation-language-copy h4 {
  margin: 0;
  font-size: 16px;
  letter-spacing: -0.025em;
}
.language-preference-panel > header > span {
  padding: 5px 8px;
  border-radius: 99px;
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
  font-size: 10px;
  font-weight: 750;
}
.language-choice-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 11px;
}
.language-choice {
  position: relative;
  min-height: 158px;
  padding: 16px;
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) 24px;
  grid-template-rows: auto 1fr;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--fz-line);
  border-radius: 16px;
  outline: 0;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  text-align: left;
  cursor: pointer;
  transition:
    transform 0.16s ease,
    border-color 0.16s ease,
    box-shadow 0.16s ease,
    background 0.16s ease;
}
.language-choice:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--fz-accent) 32%, var(--fz-line));
  box-shadow: 0 12px 28px rgba(13, 42, 26, 0.08);
}
.language-choice:focus-visible {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 18%, transparent);
}
.language-choice.selected {
  border-color: color-mix(in srgb, var(--fz-accent) 58%, var(--fz-line));
  background: color-mix(in srgb, var(--fz-accent) 7%, var(--fz-surface));
  box-shadow:
    inset 0 -3px var(--fz-accent),
    0 14px 30px rgba(13, 42, 26, 0.08);
}
.language-choice:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}
.language-flag {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border: 1px solid var(--fz-line);
  border-radius: 14px;
  background: var(--fz-surface);
  font-size: 27px;
  box-shadow: 0 5px 12px rgba(13, 42, 26, 0.06);
}
.language-copy {
  min-width: 0;
  display: grid;
  gap: 3px;
}
.language-copy strong {
  font-size: 12px;
  line-height: 1.2;
}
.language-copy small {
  overflow: hidden;
  color: var(--fz-muted);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.language-check {
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border: 1px solid var(--fz-line);
  border-radius: 50%;
  color: transparent;
  font-size: 11px;
  font-style: normal;
}
.language-choice.selected .language-check {
  border-color: var(--fz-accent);
  background: var(--fz-accent);
  color: #092418;
}
.language-choice em {
  grid-column: 1/-1;
  align-self: end;
  margin-top: 8px;
  color: var(--fz-muted);
  font-size: 10px;
  font-style: normal;
  line-height: 1.5;
}
.language-feedback {
  margin: 13px 0 0;
  padding: 9px 11px;
  border-radius: 9px;
  font-size: 11px;
  font-weight: 680;
}
.language-feedback.error {
  background: color-mix(in srgb, var(--fz-negative) 9%, transparent);
  color: var(--fz-negative);
}
.language-feedback.success {
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
}
.language-feedback.muted {
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
}
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
.installation-language-copy {
  display: flex;
  align-items: center;
  gap: 12px;
}
.installation-language-copy > span {
  width: 39px;
  height: 39px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
  font-size: 18px;
}
.installation-language-copy small {
  display: block;
  max-width: 500px;
  margin-top: 4px;
  color: var(--fz-muted);
  font-size: 10px;
  line-height: 1.45;
}
.installation-language-actions {
  display: flex;
  align-items: center;
  gap: 7px;
}
.installation-language-actions label {
  height: 42px;
  padding: 0 10px;
  display: flex;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface);
  cursor: pointer;
}
.installation-language-actions > button {
  height: 42px;
  padding: 0 13px;
  border: 0;
  border-radius: 10px;
  background: var(--fz-accent);
  color: #092418;
  font-size: 10px;
  font-weight: 800;
  cursor: pointer;
}
.installation-language-actions > button:disabled {
  opacity: 0.55;
  cursor: wait;
}
.installation-language-panel > .language-feedback {
  grid-column: 1/-1;
  margin: 0;
}
.withholding-form-row {
  margin-top: 20px;
  display: flex;
  align-items: flex-end;
  gap: 14px;
  flex-wrap: wrap;
}
.withholding-form-row label {
  display: grid;
  gap: 6px;
}
.withholding-form-row label > span {
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 700;
}
.tax-rate-input-wrap {
  height: 44px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--fz-line);
  border-radius: 12px;
  background: var(--fz-surface-soft);
  transition: border-color 0.15s ease;
}
.tax-rate-input-wrap:focus-within {
  border-color: var(--fz-accent);
}
.tax-rate-input-wrap input {
  width: 80px;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--fz-ink);
  font: inherit;
  font-size: 14px;
  font-weight: 750;
  text-align: right;
}
.tax-rate-input-wrap strong {
  color: var(--fz-muted);
  font-size: 12px;
}
.withholding-form-row button {
  height: 44px;
  padding: 0 18px;
  border: 0;
  border-radius: 12px;
  background: var(--fz-accent);
  color: #092418;
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
  transition: opacity 0.15s ease;
}
.withholding-form-row button:disabled {
  opacity: 0.55;
  cursor: wait;
}
.summary-sources-document {
  background: linear-gradient(
    145deg,
    color-mix(in srgb, var(--fz-accent) 5%, transparent),
    transparent 46%
  );
}
.summary-source-status strong {
  font-variant-numeric: tabular-nums;
}
.summary-sources-panel {
  margin-top: 32px;
  padding: 22px;
  border: 1px solid var(--fz-line);
  border-radius: 20px;
  background: var(--fz-surface);
  box-shadow: var(--fz-shadow);
}
.summary-sources-panel > header {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 4px;
}
.summary-sources-panel > header p {
  margin: 0 0 6px;
  color: var(--fz-accent);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.summary-sources-panel > header h4 {
  margin: 0;
  font-size: 17px;
  letter-spacing: -0.025em;
}
.summary-sources-panel > header > span {
  min-width: 30px;
  padding: 5px 8px;
  border-radius: 99px;
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
  font-size: 10px;
  font-weight: 800;
  text-align: center;
}
.summary-sources-panel > .document-description {
  max-width: 630px;
  margin: 14px 0 0;
  color: var(--fz-muted);
  line-height: 1.55;
}
.summary-transfer {
  position: relative;
  margin-top: 22px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 54px minmax(0, 1fr);
  gap: 14px;
  align-items: stretch;
}
.summary-source-column {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--fz-line);
  border-radius: 16px;
  background: var(--fz-surface-soft);
}
.summary-source-column > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 2px 3px 10px;
  color: var(--fz-muted);
  font-size: 10px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.summary-source-column > header strong {
  color: var(--fz-ink);
  font-size: 10px;
  font-weight: 800;
}
.summary-source-column > header small {
  min-width: 22px;
  padding: 3px 6px;
  border-radius: 99px;
  background: var(--fz-surface);
  font-size: 9px;
  text-align: center;
}
.summary-source-column.included {
  border-color: color-mix(in srgb, var(--fz-accent) 30%, var(--fz-line));
  background: color-mix(in srgb, var(--fz-accent) 4%, var(--fz-surface));
}
.summary-source-list {
  display: grid;
  gap: 7px;
  min-height: 222px;
  padding-top: 2px;
}
.summary-source-option {
  width: 100%;
  min-height: 43px;
  padding: 7px 9px;
  display: flex;
  align-items: center;
  gap: 9px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font: inherit;
  font-size: 11px;
  font-weight: 680;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    transform 0.16s ease;
}
.summary-source-option:hover:not(:disabled) {
  transform: translateX(2px);
  border-color: color-mix(in srgb, var(--fz-accent) 35%, var(--fz-line));
}
.summary-source-option:focus-visible {
  outline: 0;
  border-color: var(--fz-accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 17%, transparent);
}
.summary-source-option.selected {
  border-color: var(--fz-accent);
  background: var(--fz-accent-soft);
  box-shadow: inset 3px 0 var(--fz-accent);
}
.summary-source-option:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}
.summary-source-mark {
  flex: 0 0 auto;
  width: 25px;
  height: 25px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
  font-size: 10px;
  font-weight: 850;
}
.summary-source-empty {
  align-self: center;
  margin: 0;
  padding: 12px;
  color: var(--fz-muted);
  font-size: 10px;
  text-align: center;
}
.summary-transfer-rail {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  padding: 28px 0;
}
.summary-transfer-rail:before {
  content: "";
  position: absolute;
  top: 31px;
  bottom: 31px;
  width: 2px;
  background: var(--fz-accent-soft);
}
.summary-transfer-rail span {
  z-index: 1;
  width: 8px;
  height: 8px;
  border: 2px solid var(--fz-accent);
  border-radius: 50%;
  background: var(--fz-surface);
}
.summary-transfer-rail i {
  z-index: 1;
  width: 8px;
  height: 8px;
  border: 2px solid var(--fz-accent);
  border-radius: 50%;
  background: var(--fz-accent);
}
.summary-transfer-actions {
  position: absolute;
  top: 50%;
  left: 50%;
  display: grid;
  gap: 8px;
  transform: translate(-50%, -50%);
}
.summary-transfer-button {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 1px solid var(--fz-accent);
  border-radius: 10px;
  background: var(--fz-accent);
  color: var(--fz-ink);
  cursor: pointer;
  box-shadow: 0 8px 18px color-mix(in srgb, var(--fz-accent) 22%, transparent);
  transition:
    transform 0.16s ease,
    opacity 0.16s ease,
    background 0.16s ease;
}
.summary-transfer-button:first-child {
  transform: translateY(-47px);
}
.summary-transfer-button:last-child {
  transform: translateY(47px);
}
.summary-transfer-button:hover:not(:disabled) {
  background: var(--fz-accent-soft);
  transform: translateY(-49px);
}
.summary-transfer-button:last-child:hover:not(:disabled) {
  transform: translateY(49px);
}
.summary-transfer-button:focus-visible {
  outline: 0;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 24%, transparent);
}
.summary-transfer-button:disabled {
  opacity: 0.38;
  cursor: not-allowed;
  box-shadow: none;
}
.summary-transfer-button svg {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}
.summary-sources-footer {
  margin-top: 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.summary-sources-footer .language-feedback {
  margin: 0;
  flex: 1 1 220px;
}
.summary-sources-save {
  min-height: 42px;
  padding: 0 15px;
  border: 0;
  border-radius: 11px;
  background: var(--fz-accent);
  color: var(--fz-ink);
  font: inherit;
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}
.summary-sources-save:hover:not(:disabled) {
  transform: translateY(-1px);
}
.summary-sources-save:focus-visible {
  outline: 0;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 25%, transparent);
}
.summary-sources-save:disabled {
  opacity: 0.55;
  cursor: wait;
}
@media (prefers-reduced-motion: reduce) {
  .summary-source-option,
  .summary-transfer-button,
  .summary-sources-save {
    transition: none;
  }
  .summary-source-option:hover:not(:disabled),
  .summary-transfer-button:hover:not(:disabled),
  .summary-transfer-button:last-child:hover:not(:disabled),
  .summary-sources-save:hover:not(:disabled) {
    transform: none;
  }
}
@media (max-width: 900px) {
  .summary-transfer {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  .summary-transfer-rail {
    display: none;
  }
  .summary-transfer-actions {
    position: static;
    display: flex;
    justify-content: center;
    transform: none;
    order: 2;
  }
  .summary-transfer-button:first-child,
  .summary-transfer-button:last-child {
    transform: none;
  }
  .summary-transfer-button:first-child svg {
    transform: rotate(90deg);
  }
  .summary-transfer-button:last-child svg {
    transform: rotate(-90deg);
  }
  .summary-source-column.included {
    order: 3;
  }
}
@media (max-width: 720px) {
  .summary-sources-panel {
    margin-top: 20px;
    padding: 15px;
  }
  .summary-sources-panel > header {
    align-items: start;
  }
  .summary-sources-panel > header h4 {
    font-size: 15px;
  }
  .summary-source-list {
    min-height: 150px;
  }
  .summary-sources-footer {
    align-items: stretch;
    display: grid;
  }
  .summary-sources-save {
    width: 100%;
  }
}
@media (prefers-reduced-motion: reduce) {
  .language-choice {
    transition: none;
  }
  .language-choice:hover:not(:disabled) {
    transform: none;
  }
}
@media (max-width: 1100px) {
  .interface-document {
    padding-inline: 28px;
  }
  .language-choice-grid {
    grid-template-columns: 1fr;
  }
  .language-choice {
    min-height: 108px;
  }
  .installation-language-panel {
    grid-template-columns: 1fr;
  }
  .installation-language-actions {
    justify-content: flex-start;
  }
}
@media (max-width: 720px) {
  .interface-document {
    padding: 22px 17px 34px;
  }
  .interface-document-header {
    display: block;
  }
  .interface-document-header h3 {
    font-size: 24px;
  }
  .effective-language {
    margin-top: 18px;
  }
  .language-preference-panel {
    margin-top: 20px;
    padding: 15px;
  }
  .language-preference-panel > header {
    display: block;
  }
  .language-preference-panel > header > span {
    display: inline-block;
    margin-top: 9px;
  }
  .language-choice {
    min-height: 120px;
  }
  .installation-language-panel {
    padding: 15px;
  }
  .installation-language-actions {
    flex-wrap: wrap;
  }
  .installation-language-actions > button {
    width: 100%;
  }
}
</style>
