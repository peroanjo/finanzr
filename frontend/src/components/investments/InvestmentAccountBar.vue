<script setup lang="ts">
import { ref } from "vue";
import ImportStatementDialog from "../ImportStatementDialog.vue";
import type { ImportStatementDialogHandle } from "../ImportStatementDialog.vue";

export interface InvestmentAccountBarLabels {
  portfolioView: string;
  accountAria: string;
  allAccounts: string;
  importStatement: string;
  manage: string;
  add: string;
}

export interface InvestmentImportConfig {
  endpoint: string;
  accountsEndpoint: string;
  accountId: string;
  accountLabel: string;
  importerLabel: string;
  compatibility: string;
  accept: string;
  fileHint: string;
}

defineProps<{
  accounts: Array<{ id: string; name: string }>;
  selectedAccount: string;
  selectedAccountLabel: string;
  labels: InvestmentAccountBarLabels;
  importConfig: InvestmentImportConfig | null;
}>();

const emit = defineEmits<{
  "change-account": [value: string];
  "open-account-dialog": [];
  "open-account-editor": [];
  imported: [];
}>();

const importDialog = ref<ImportStatementDialogHandle>();

function changeAccount(event: Event) {
  emit("change-account", (event.target as HTMLSelectElement).value);
}
</script>

<template>
  <div class="fund-account-bar investment-account-bar">
    <div class="fund-account-copy">
      <span class="fund-account-mark" aria-hidden="true">{{
        selectedAccountLabel.slice(0, 1)
      }}</span>
      <div>
        <small>{{ labels.portfolioView }}</small>
        <strong>{{ selectedAccountLabel }}</strong>
      </div>
    </div>
    <div class="fund-account-actions scope-actions">
      <label>
        <span class="sr-only">{{ labels.accountAria }}</span>
        <select
          :value="selectedAccount"
          :aria-label="labels.accountAria"
          @change="changeAccount"
        >
          <option value="all">{{ labels.allAccounts }}</option>
          <option
            v-for="account in accounts"
            :key="account.id"
            :value="account.id"
          >
            {{ account.name }}
          </option>
        </select>
      </label>
      <button v-if="importConfig" type="button" @click="importDialog?.open()">
        {{ labels.importStatement }}
      </button>
      <ImportStatementDialog
        v-if="importConfig"
        ref="importDialog"
        :endpoint="importConfig.endpoint"
        :accounts-endpoint="importConfig.accountsEndpoint"
        :account-id="importConfig.accountId"
        :account-label="importConfig.accountLabel"
        :importer-label="importConfig.importerLabel"
        :compatibility="importConfig.compatibility"
        :accept="importConfig.accept"
        :file-hint="importConfig.fileHint"
        @imported="emit('imported')"
      />
      <button
        v-if="selectedAccount !== 'all'"
        type="button"
        @click="emit('open-account-editor')"
      >
        {{ labels.manage }}
      </button>
      <button type="button" @click="emit('open-account-dialog')">
        <span aria-hidden="true">+</span> {{ labels.add }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.investment-account-bar {
  margin-bottom: 18px;
  padding: 11px 12px 11px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border: 1px solid var(--fz-line);
  border-radius: 16px;
  background:
    linear-gradient(
      105deg,
      color-mix(in srgb, var(--fz-accent) 7%, transparent),
      transparent 42%
    ),
    var(--fz-surface);
  box-shadow: 0 10px 26px
    color-mix(in srgb, var(--fz-chart-tooltip-shadow) 34%, transparent);
}
.fund-account-copy,
.fund-account-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.fund-account-mark {
  width: 31px;
  height: 31px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: var(--fz-accent);
  color: #f4fff9;
  font-size: 11px;
  font-weight: 820;
}
.fund-account-copy div {
  display: grid;
  gap: 1px;
}
.fund-account-copy small {
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 680;
}
.fund-account-copy strong {
  font-size: 11px;
  font-weight: 750;
}
.fund-account-actions select,
.fund-account-actions button {
  min-height: 34px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  font-size: 11px;
  font-weight: 710;
}
.fund-account-actions select {
  min-width: 174px;
  padding: 8px 30px 8px 11px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
}
.fund-account-actions button {
  padding: 8px 11px;
  background: transparent;
  color: var(--fz-muted);
  cursor: pointer;
}
.fund-account-actions button:hover {
  border-color: var(--fz-accent);
  color: var(--fz-ink);
}
.fund-account-actions button span {
  margin-right: 3px;
  color: var(--fz-accent);
  font-size: 13px;
}
:deep(.import-compact) {
  margin: 0;
  padding: 0;
  display: grid;
  gap: 9px;
  border: 0;
  background: transparent;
}
:deep(.import-compact h2) {
  display: none;
}
:deep(.import-compact select),
:deep(.import-compact input) {
  min-width: 0;
  width: 100%;
  padding: 9px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  font-size: 11px;
}
:deep(.import-compact button) {
  padding: 9px 11px;
  border: 0;
  border-radius: 9px;
  background: var(--fz-accent);
  color: #f4fff9;
  font-size: 11px;
  font-weight: 720;
}
:deep(.import-compact p) {
  min-height: 12px;
  margin: 0;
  color: var(--fz-muted);
  font-size: 10px;
}

@media (max-width: 720px) {
  .investment-account-bar {
    align-items: stretch;
    flex-direction: column;
  }
  .fund-account-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .fund-account-actions label {
    grid-column: 1 / -1;
  }
  .fund-account-actions select {
    width: 100%;
    min-width: 0;
  }
}
</style>
