<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { SummarySourceKey } from "../../types/api";

const props = defineProps<{
  summarySources: SummarySourceKey[];
  summarySourceKeys: SummarySourceKey[];
  scopeLabel: string;
  canManage: boolean;
  busy: boolean;
  error: string;
  success: string;
}>();

const emit = defineEmits<{
  update: [sources: SummarySourceKey[]];
  save: [sources: SummarySourceKey[]];
}>();

const { t } = useI18n();
const selectedAvailableSources = ref<SummarySourceKey[]>([]);
const selectedIncludedSources = ref<SummarySourceKey[]>([]);
const summarySourceRefs = {
  available: {} as Record<string, HTMLButtonElement>,
  included: {} as Record<string, HTMLButtonElement>,
};
const summaryAvailableSources = computed(() =>
  props.summarySourceKeys.filter(
    (key) => !props.summarySources.includes(key),
  ),
);

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
    : props.summarySources;
}

function focusSummarySource(
  side: "available" | "included",
  index: number,
  keyOverride?: SummarySourceKey,
) {
  const key = keyOverride ?? summarySourceSideKeys(side)[index];
  if (!key) return;
  nextTick(() => {
    const referenced = summarySourceRefs[side][key];
    if (referenced) {
      referenced.focus();
      return;
    }
    document
      .querySelector<HTMLElement>(`[data-summary-source="${key}"]`)
      ?.focus();
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
  let nextSources = props.summarySources;
  if (direction === "in") {
    const movingKeys = new Set(moving);
    nextSources = props.summarySourceKeys.filter(
      (key) => props.summarySources.includes(key) || movingKeys.has(key),
    );
    selectedAvailableSources.value = [];
  } else {
    const movingKeys = new Set(moving);
    nextSources = props.summarySources.filter((key) => !movingKeys.has(key));
    selectedIncludedSources.value = [];
  }
  emit("update", nextSources);
  const targetSide = direction === "in" ? "included" : "available";
  const targetKeys =
    targetSide === "available"
      ? props.summarySourceKeys.filter((key) => !nextSources.includes(key))
      : nextSources;
  const targetIndex = targetKeys.findIndex((key) => key === moving[0]);
  if (targetIndex >= 0) focusSummarySource(targetSide, targetIndex, moving[0]);
}

function saveSummarySources() {
  emit("save", [...props.summarySources]);
}
</script>

<template>
  <article class="interface-document summary-sources-document">
    <header class="interface-document-header">
      <div>
        <p>{{ t("settings.summarySources") }}</p>
        <h3>{{ t("settings.summarySources") }}</h3>
        <span>{{ t("settings.summarySourcesDescription") }}</span>
      </div>
      <div class="effective-language summary-source-status" aria-live="polite">
        <span aria-hidden="true">Σ</span>
        <p>
          <small>{{ t("settings.summarySourcesAria") }}</small
          ><strong
            >{{ props.summarySources.length }} /
            {{ props.summarySourceKeys.length }}</strong
          >
        </p>
        <i />
      </div>
    </header>

    <section class="summary-sources-panel" aria-labelledby="summary-sources-title">
      <header>
        <div>
          <p>{{ props.scopeLabel }}</p>
          <h4 id="summary-sources-title">{{ t("settings.summarySources") }}</h4>
        </div>
        <span>{{ props.summarySources.length }}</span>
      </header>
      <p class="document-description">{{ t("settings.summarySourcesHint") }}</p>
      <div class="summary-transfer" :aria-label="t('settings.summarySourcesAria')">
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
              :data-summary-source="key"
              :class="{ selected: selectedAvailableSources.includes(key) }"
              :aria-selected="selectedAvailableSources.includes(key)"
              :disabled="!props.canManage || props.busy"
              :ref="(element) => setSummarySourceRef('available', key, element)"
              @keydown="onSummarySourceKeydown($event, 'available', key)"
              @click="toggleSummarySource('available', key)"
            >
              <span class="summary-source-mark" aria-hidden="true">{{
                key.slice(0, 1).toUpperCase()
              }}</span>
              <span>{{ t(`overview.sources.${key}`) }}</span>
            </button>
            <p v-if="!summaryAvailableSources.length" class="summary-source-empty">
              {{ t("common.noData") }}
            </p>
          </div>
        </section>
        <div class="summary-transfer-rail" aria-hidden="true"><span /><i /><span /></div>
        <div class="summary-transfer-actions">
          <button
            type="button"
            class="summary-transfer-button"
            :aria-label="t('settings.summarySourcesMoveIn')"
            :title="t('settings.summarySourcesMoveIn')"
            :disabled="!selectedAvailableSources.length || !props.canManage || props.busy"
            @click="moveSelectedSummarySources('in')"
          >
            <svg viewBox="0 0 24 24"><path d="M5 12h13m-5-5 5 5-5 5" /></svg>
          </button>
          <button
            type="button"
            class="summary-transfer-button"
            :aria-label="t('settings.summarySourcesMoveOut')"
            :title="t('settings.summarySourcesMoveOut')"
            :disabled="!selectedIncludedSources.length || !props.canManage || props.busy"
            @click="moveSelectedSummarySources('out')"
          >
            <svg viewBox="0 0 24 24"><path d="M19 12H6m5-5-5 5 5 5" /></svg>
          </button>
        </div>
        <section class="summary-source-column included">
          <header>
            <strong>{{ t("settings.summarySourcesIncluded") }}</strong
            ><small>{{ props.summarySources.length }}</small>
          </header>
          <div
            class="summary-source-list"
            role="listbox"
            :aria-label="t('settings.summarySourcesIncludedAria')"
            aria-multiselectable="true"
          >
            <button
              v-for="key in props.summarySources"
              :key="key"
              type="button"
              role="option"
              class="summary-source-option"
              :data-summary-source="key"
              :class="{ selected: selectedIncludedSources.includes(key) }"
              :aria-selected="selectedIncludedSources.includes(key)"
              :disabled="!props.canManage || props.busy"
              :ref="(element) => setSummarySourceRef('included', key, element)"
              @keydown="onSummarySourceKeydown($event, 'included', key)"
              @click="toggleSummarySource('included', key)"
            >
              <span class="summary-source-mark" aria-hidden="true">{{
                key.slice(0, 1).toUpperCase()
              }}</span>
              <span>{{ t(`overview.sources.${key}`) }}</span>
            </button>
            <p v-if="!props.summarySources.length" class="summary-source-empty">
              {{ t("common.noData") }}
            </p>
          </div>
        </section>
      </div>
      <footer class="summary-sources-footer">
        <p v-if="!props.canManage" class="language-feedback muted">
          {{ t("settings.demoLanguageNotice") }}
        </p>
        <p v-if="props.error" class="language-feedback error" role="alert">
          {{ props.error }}
        </p>
        <p v-else-if="props.success" class="language-feedback success" role="status">
          {{ props.success }}
        </p>
        <button
          type="button"
          class="summary-sources-save"
          :disabled="props.busy || !props.canManage"
          @click="saveSummarySources"
        >
          {{ props.busy ? t("common.saving") : t("settings.summarySourcesSave") }}
        </button>
      </footer>
    </section>
  </article>
</template>

<style scoped>
.interface-document {
  min-height: 100%;
  padding: 36px 40px 48px;
  background: linear-gradient(145deg, color-mix(in srgb, var(--fz-accent) 3%, transparent), transparent 38%);
}
.interface-document-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}
.interface-document-header > div:first-child { max-width: 600px; }
.interface-document-header p {
  margin: 0 0 6px;
  color: var(--fz-accent);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.interface-document-header h3 { margin: 0; font-size: 30px; letter-spacing: -0.05em; }
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
.effective-language > span { width: 40px; height: 40px; display: grid; place-items: center; border-radius: 12px; background: var(--fz-surface-soft); font-size: 24px; box-shadow: inset 0 0 0 1px var(--fz-line); }
.effective-language p { margin: 0; display: grid; gap: 2px; }
.effective-language small { color: var(--fz-muted); font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }
.effective-language strong { font-size: 12px; }
.effective-language > i { width: 7px; height: 7px; border-radius: 50%; background: var(--fz-accent); box-shadow: 0 0 0 4px color-mix(in srgb, var(--fz-accent) 12%, transparent); }
.summary-sources-document { background: linear-gradient(145deg, color-mix(in srgb, var(--fz-accent) 5%, transparent), transparent 46%); }
.summary-source-status strong { font-variant-numeric: tabular-nums; }
.summary-sources-panel { margin-top: 32px; padding: 22px; border: 1px solid var(--fz-line); border-radius: 20px; background: var(--fz-surface); box-shadow: var(--fz-shadow); }
.summary-sources-panel > header { display: flex; align-items: end; justify-content: space-between; gap: 18px; margin-bottom: 4px; }
.summary-sources-panel > header p { margin: 0 0 6px; color: var(--fz-accent); font-size: 10px; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; }
.summary-sources-panel > header h4 { margin: 0; font-size: 17px; letter-spacing: -0.025em; }
.summary-sources-panel > header > span { min-width: 30px; padding: 5px 8px; border-radius: 99px; background: var(--fz-accent-soft); color: var(--fz-accent); font-size: 10px; font-weight: 800; text-align: center; }
.document-description { max-width: 630px; margin: 14px 0 0; color: var(--fz-muted); font-size: 12px; line-height: 1.55; }
.summary-transfer { position: relative; margin-top: 22px; display: grid; grid-template-columns: minmax(0, 1fr) 54px minmax(0, 1fr); gap: 14px; align-items: stretch; }
.summary-source-column { min-width: 0; padding: 12px; border: 1px solid var(--fz-line); border-radius: 16px; background: var(--fz-surface-soft); }
.summary-source-column > header { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 2px 3px 10px; color: var(--fz-muted); font-size: 10px; letter-spacing: 0.04em; text-transform: uppercase; }
.summary-source-column > header strong { color: var(--fz-ink); font-size: 10px; font-weight: 800; }
.summary-source-column > header small { min-width: 22px; padding: 3px 6px; border-radius: 99px; background: var(--fz-surface); font-size: 9px; text-align: center; }
.summary-source-column.included { border-color: color-mix(in srgb, var(--fz-accent) 30%, var(--fz-line)); background: color-mix(in srgb, var(--fz-accent) 4%, var(--fz-surface)); }
.summary-source-list { display: grid; gap: 7px; min-height: 222px; padding-top: 2px; }
.summary-source-option { width: 100%; min-height: 43px; padding: 7px 9px; display: flex; align-items: center; gap: 9px; border: 1px solid transparent; border-radius: 10px; background: var(--fz-surface); color: var(--fz-ink); font: inherit; font-size: 11px; font-weight: 680; text-align: left; cursor: pointer; transition: border-color 0.16s ease, background 0.16s ease, transform 0.16s ease; }
.summary-source-option:hover:not(:disabled) { transform: translateX(2px); border-color: color-mix(in srgb, var(--fz-accent) 35%, var(--fz-line)); }
.summary-source-option:focus-visible { outline: 0; border-color: var(--fz-accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 17%, transparent); }
.summary-source-option.selected { border-color: var(--fz-accent); background: var(--fz-accent-soft); box-shadow: inset 3px 0 var(--fz-accent); }
.summary-source-option:disabled { cursor: not-allowed; opacity: 0.62; }
.summary-source-mark { flex: 0 0 auto; width: 25px; height: 25px; display: grid; place-items: center; border-radius: 8px; background: var(--fz-accent-soft); color: var(--fz-accent); font-size: 10px; font-weight: 850; }
.summary-source-empty { align-self: center; margin: 0; padding: 12px; color: var(--fz-muted); font-size: 10px; text-align: center; }
.summary-transfer-rail { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: space-between; padding: 28px 0; }
.summary-transfer-rail:before { content: ""; position: absolute; top: 31px; bottom: 31px; width: 2px; background: var(--fz-accent-soft); }
.summary-transfer-rail span, .summary-transfer-rail i { z-index: 1; width: 8px; height: 8px; border: 2px solid var(--fz-accent); border-radius: 50%; background: var(--fz-surface); }
.summary-transfer-rail i { background: var(--fz-accent); }
.summary-transfer-actions { position: absolute; top: 50%; left: 50%; display: grid; gap: 8px; transform: translate(-50%, -50%); }
.summary-transfer-button { width: 34px; height: 34px; display: grid; place-items: center; border: 1px solid var(--fz-accent); border-radius: 10px; background: var(--fz-accent); color: var(--fz-ink); cursor: pointer; box-shadow: 0 8px 18px color-mix(in srgb, var(--fz-accent) 22%, transparent); transition: transform 0.16s ease, opacity 0.16s ease, background 0.16s ease; }
.summary-transfer-button:first-child { transform: translateY(-47px); }
.summary-transfer-button:last-child { transform: translateY(47px); }
.summary-transfer-button:hover:not(:disabled) { background: var(--fz-accent-soft); transform: translateY(-49px); }
.summary-transfer-button:last-child:hover:not(:disabled) { transform: translateY(49px); }
.summary-transfer-button:focus-visible { outline: 0; box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 24%, transparent); }
.summary-transfer-button:disabled { opacity: 0.38; cursor: not-allowed; box-shadow: none; }
.summary-transfer-button svg { width: 17px; height: 17px; fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.8; }
.summary-sources-footer { margin-top: 18px; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.summary-sources-footer .language-feedback { margin: 0; flex: 1 1 220px; }
.language-feedback { margin: 13px 0 0; padding: 9px 11px; border-radius: 9px; font-size: 11px; font-weight: 680; }
.language-feedback.error { background: color-mix(in srgb, var(--fz-negative) 9%, transparent); color: var(--fz-negative); }
.language-feedback.success { background: var(--fz-accent-soft); color: var(--fz-accent); }
.language-feedback.muted { background: var(--fz-surface-soft); color: var(--fz-muted); }
.summary-sources-save { min-height: 42px; padding: 0 15px; border: 0; border-radius: 11px; background: var(--fz-accent); color: var(--fz-ink); font: inherit; font-size: 11px; font-weight: 800; cursor: pointer; transition: opacity 0.16s ease, transform 0.16s ease; }
.summary-sources-save:hover:not(:disabled) { transform: translateY(-1px); }
.summary-sources-save:focus-visible { outline: 0; box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 25%, transparent); }
.summary-sources-save:disabled { opacity: 0.55; cursor: wait; }
@media (prefers-reduced-motion: reduce) {
  .summary-source-option, .summary-transfer-button, .summary-sources-save { transition: none; }
  .summary-source-option:hover:not(:disabled), .summary-transfer-button:hover:not(:disabled), .summary-transfer-button:last-child:hover:not(:disabled), .summary-sources-save:hover:not(:disabled) { transform: none; }
}
@media (max-width: 900px) {
  .summary-transfer { grid-template-columns: 1fr; gap: 10px; }
  .summary-transfer-rail { display: none; }
  .summary-transfer-actions { position: static; display: flex; justify-content: center; transform: none; order: 2; }
  .summary-transfer-button:first-child, .summary-transfer-button:last-child { transform: none; }
  .summary-transfer-button:first-child svg { transform: rotate(90deg); }
  .summary-transfer-button:last-child svg { transform: rotate(-90deg); }
  .summary-source-column.included { order: 3; }
}
@media (max-width: 720px) {
  .interface-document { padding: 22px 17px 34px; }
  .interface-document-header { display: block; }
  .interface-document-header h3 { font-size: 24px; }
  .effective-language { margin-top: 18px; }
  .summary-sources-panel { margin-top: 20px; padding: 15px; }
  .summary-sources-panel > header { align-items: start; }
  .summary-sources-panel > header h4 { font-size: 15px; }
  .summary-source-list { min-height: 150px; }
  .summary-sources-footer { align-items: stretch; display: grid; }
  .summary-sources-save { width: 100%; }
}
</style>
