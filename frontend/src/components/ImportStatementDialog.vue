<script lang="ts">
export interface ImportStatementDialogHandle {
  open: () => void;
}
</script>

<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import ImportPanel from "./ImportPanel.vue";

defineProps<{
  endpoint: string;
  accountsEndpoint: string;
  accountId: string;
  accountLabel: string;
  importerLabel: string;
  compatibility: string;
  accept?: string;
  fileHint?: string;
}>();

const emit = defineEmits<{ imported: [] }>();
const { t } = useI18n();
const dialog = ref<HTMLDialogElement>();
// The theme lives on .app-shell. Teleporting the dialog inside the shell keeps
// its light/dark tokens and prevents it from inheriting toolbar styles.
const teleportTarget = document.querySelector(".app-shell")
  ? ".app-shell"
  : "body";

function open() {
  dialog.value?.showModal();
}

function close() {
  dialog.value?.close();
}

defineExpose({ open });
</script>

<template>
  <Teleport :to="teleportTarget">
    <dialog
      ref="dialog"
      class="import-statement-dialog"
      aria-labelledby="import-statement-title"
      @cancel.prevent="close"
      @click.self="close"
    >
      <div class="import-dialog-shell">
        <header>
          <div class="import-dialog-heading">
            <span class="import-dialog-mark" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path
                  d="M12 3v12m0-12 4 4m-4-4L8 7M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3"
                />
              </svg>
            </span>
            <div>
              <p>{{ t("shared.importDialog.eyebrow") }}</p>
              <h2 id="import-statement-title">
                {{ t("shared.importDialog.title") }}
              </h2>
            </div>
          </div>
          <button
            type="button"
            class="import-dialog-close"
            :aria-label="t('shared.importDialog.closeAria')"
            @click="close"
          >
            ×
          </button>
        </header>

        <p class="import-dialog-intro">
          {{ t("shared.importDialog.intro") }}
        </p>

        <div class="import-dialog-context">
          <span class="context-icon" aria-hidden="true">{{
            accountLabel.slice(0, 1)
          }}</span>
          <div>
            <small>{{ t("shared.importDialog.destinationAccount") }}</small>
            <strong>{{ accountLabel }}</strong>
          </div>
          <div class="context-importer">
            <small>{{ t("shared.importDialog.activeImporter") }}</small>
            <strong><i />{{ importerLabel }}</strong>
          </div>
        </div>

        <ImportPanel
          compact
          :endpoint="endpoint"
          :accounts-endpoint="accountsEndpoint"
          :account-id="accountId"
          :accept="accept"
          :file-hint="fileHint"
          hide-account-selector
          @imported="emit('imported')"
        />

        <footer>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M12 3 5 6v5c0 4.6 2.9 8.1 7 10 4.1-1.9 7-5.4 7-10V6l-7-3Zm-3 9 2 2 4-4"
            />
          </svg>
          <p>
            <strong>{{ t("shared.importDialog.localProcessing") }}</strong>
            {{ compatibility }}
          </p>
        </footer>
      </div>
    </dialog>
  </Teleport>
</template>

<style scoped>
.import-statement-dialog {
  width: min(650px, calc(100vw - 32px));
  max-height: min(760px, calc(100dvh - 32px));
  padding: 0;
  overflow: auto;
  border: 1px solid
    color-mix(in srgb, var(--fz-accent, #3ddc97) 24%, var(--fz-line, #d8e0dc));
  border-radius: 26px;
  background: var(--fz-surface, #fff);
  color: var(--fz-ink, #15221b);
  color-scheme: inherit;
  box-shadow: 0 34px 110px rgba(0, 0, 0, 0.38);
}
.import-statement-dialog::backdrop {
  background: color-mix(in srgb, #07100c 70%, transparent);
  backdrop-filter: blur(9px) saturate(0.85);
}
.import-dialog-shell {
  position: relative;
  padding: 28px;
  overflow: hidden;
}
.import-dialog-shell::before {
  position: absolute;
  inset: 0 0 auto;
  height: 150px;
  background:
    radial-gradient(
      circle at 15% 0,
      color-mix(in srgb, var(--fz-accent) 22%, transparent),
      transparent 55%
    ),
    linear-gradient(
      100deg,
      color-mix(in srgb, var(--fz-accent) 7%, transparent),
      transparent 70%
    );
  content: "";
  pointer-events: none;
}
header,
.import-dialog-intro,
.import-dialog-context,
:deep(.import-compact),
footer {
  position: relative;
}
header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}
.import-dialog-heading {
  display: flex;
  align-items: center;
  gap: 14px;
}
.import-dialog-mark {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border: 1px solid color-mix(in srgb, var(--fz-accent) 38%, transparent);
  border-radius: 15px;
  background: color-mix(in srgb, var(--fz-accent) 13%, var(--fz-surface));
  color: var(--fz-accent);
  box-shadow: inset 0 1px rgba(255, 255, 255, 0.12);
}
.import-dialog-mark svg {
  width: 22px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}
.import-dialog-heading p {
  margin: 0 0 3px;
  color: var(--fz-accent);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}
.import-dialog-heading h2 {
  margin: 0;
  font-size: 26px;
  letter-spacing: -0.045em;
}
.import-dialog-close {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border: 1px solid var(--fz-line);
  border-radius: 12px;
  background: color-mix(in srgb, var(--fz-surface-soft) 86%, transparent);
  color: var(--fz-muted);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
}
.import-dialog-close:hover {
  border-color: var(--fz-accent);
  color: var(--fz-ink);
}
.import-dialog-intro {
  max-width: 560px;
  margin: 22px 0 18px;
  color: var(--fz-muted);
  font-size: 13px;
  line-height: 1.6;
}
.import-dialog-context {
  min-height: 68px;
  padding: 11px 13px;
  display: flex;
  align-items: center;
  gap: 11px;
  border: 1px solid var(--fz-line);
  border-radius: 17px;
  background: color-mix(in srgb, var(--fz-surface-soft) 80%, transparent);
}
.context-icon {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: var(--fz-accent);
  color: #f4fff9;
  font-size: 13px;
  font-weight: 850;
}
.import-dialog-context div {
  display: grid;
  gap: 2px;
}
.import-dialog-context small {
  color: var(--fz-muted);
  font-size: 10px;
}
.import-dialog-context strong {
  font-size: 13px;
}
.context-importer {
  margin-left: auto;
  padding-left: 18px;
  border-left: 1px solid var(--fz-line);
  text-align: right;
}
.context-importer small {
  color: var(--fz-muted);
  font-size: 10px;
}
.context-importer strong {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 7px;
  font-size: 11px;
}
.context-importer i {
  width: 6px;
  height: 6px;
  display: inline-block;
  border-radius: 50%;
  background: var(--fz-accent);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--fz-accent) 11%, transparent);
}
:deep(.import-compact) {
  margin: 16px 0 0;
  padding: 0;
  display: grid;
  gap: 14px;
  border: 0;
  border-radius: 0;
  background: transparent;
}
:deep(.import-control) {
  display: grid;
  gap: 7px;
}
:deep(.import-control > span) {
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 700;
}
:deep(.import-control select) {
  width: 100%;
  min-height: 46px;
  padding: 0 13px;
  border: 1px solid var(--fz-line);
  border-radius: 13px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  font: inherit;
  font-size: 12px;
  font-weight: 650;
}
:deep(.import-file) {
  position: relative;
  min-height: 112px;
  padding: 18px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 13px;
  border: 1px dashed color-mix(in srgb, var(--fz-muted) 48%, var(--fz-line));
  border-radius: 18px;
  background: color-mix(in srgb, var(--fz-surface-soft) 65%, transparent);
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background 0.18s ease,
    transform 0.18s ease;
}
:deep(.import-file:hover) {
  border-color: var(--fz-accent);
  background: color-mix(in srgb, var(--fz-accent) 6%, var(--fz-surface-soft));
  transform: translateY(-1px);
}
:deep(.import-file.selected) {
  border-style: solid;
  border-color: color-mix(in srgb, var(--fz-accent) 45%, var(--fz-line));
}
:deep(.import-file input) {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
:deep(.import-file-icon) {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 13px;
  background: color-mix(in srgb, var(--fz-accent) 12%, var(--fz-surface));
  color: var(--fz-accent);
}
:deep(.import-file-icon svg) {
  width: 20px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}
:deep(.import-file-copy) {
  min-width: 0;
  display: grid;
  gap: 4px;
}
:deep(.import-file-copy strong) {
  overflow: hidden;
  color: var(--fz-ink);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
:deep(.import-file-copy small) {
  color: var(--fz-muted);
  font-size: 10px;
  line-height: 1.45;
}
:deep(.import-file-action) {
  color: var(--fz-accent);
  font-size: 11px;
  font-weight: 750;
}
:deep(.import-submit) {
  min-height: 46px;
  padding: 0 17px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 0;
  border-radius: 13px;
  background: var(--fz-accent);
  color: #f4fff9;
  font: inherit;
  font-size: 12px;
  font-weight: 780;
  cursor: pointer;
  box-shadow: 0 10px 26px color-mix(in srgb, var(--fz-accent) 22%, transparent);
}
:deep(.import-submit:disabled) {
  opacity: 0.45;
  cursor: not-allowed;
  box-shadow: none;
}
:deep(.import-message) {
  margin: -2px 0 0;
  font-size: 11px;
  font-weight: 650;
}
:deep(.import-message.success) {
  color: var(--fz-positive);
}
:deep(.import-message.error) {
  color: var(--fz-negative);
}
footer {
  margin-top: 18px;
  padding-top: 16px;
  display: flex;
  align-items: center;
  gap: 9px;
  border-top: 1px solid var(--fz-line);
  color: var(--fz-muted);
}
footer svg {
  width: 18px;
  flex: 0 0 auto;
  fill: none;
  stroke: var(--fz-accent);
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.7;
}
footer p {
  margin: 0;
  font-size: 10px;
  line-height: 1.5;
}
footer strong {
  color: var(--fz-ink);
}

@media (max-width: 560px) {
  .import-dialog-shell {
    padding: 21px 18px;
  }
  .import-dialog-heading h2 {
    font-size: 23px;
  }
  .context-importer {
    padding-left: 10px;
  }
  :deep(.import-file) {
    grid-template-columns: auto minmax(0, 1fr);
  }
  :deep(.import-file-action) {
    grid-column: 2;
  }
}

@media (prefers-reduced-motion: reduce) {
  :deep(.import-file) {
    transition: none;
  }
}
</style>
