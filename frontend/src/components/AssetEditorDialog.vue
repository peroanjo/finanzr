<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { api, json } from "../api/client";
import type {
  CryptoInstrument,
  InstrumentIdentifier,
  StockInstrument,
} from "../types/api";
import {
  instrumentIdentity,
  instrumentTicker,
  primaryIdentifier,
} from "../domain/instruments";
import type { EditableAsset } from "./assetEditor";

const props = defineProps<{
  kind: "stock" | "crypto";
  assets: Array<StockInstrument | CryptoInstrument>;
}>();
const emit = defineEmits<{ saved: [asset: EditableAsset] }>();
const { t } = useI18n();

const dialog = ref<HTMLDialogElement>();
const mode = ref<"create" | "edit">("create");
const assetId = ref("");
const identifierValue = ref("");
const name = ref("");
const ticker = ref("");
const busy = ref(false);
const error = ref("");

const isCrypto = computed(() => props.kind === "crypto");
const identifierLabel = computed(() =>
  isCrypto.value ? t("shared.assetEditor.symbol") : "ISIN",
);
const sectionLabel = computed(() =>
  isCrypto.value
    ? t("shared.assetEditor.cryptoCatalog")
    : t("shared.assetEditor.investmentCatalog"),
);
const title = computed(() =>
  mode.value === "create"
    ? t(
        isCrypto.value
          ? "shared.assetEditor.addCrypto"
          : "shared.assetEditor.addInvestment",
      )
    : t(
        isCrypto.value
          ? "shared.assetEditor.editCrypto"
          : "shared.assetEditor.editInvestment",
      ),
);
const valid = computed(() =>
  Boolean(
    identifierValue.value.trim() && name.value.trim() && ticker.value.trim(),
  ),
);

function idOf(asset: EditableAsset) {
  return asset.id;
}

function identityOf(asset: EditableAsset) {
  return instrumentIdentity(asset);
}

function selectedAsset() {
  return props.assets.find((asset) => idOf(asset) === assetId.value) ?? null;
}

function populate(asset: EditableAsset) {
  assetId.value = idOf(asset);
  identifierValue.value = identityOf(asset);
  name.value = asset.name;
  ticker.value = instrumentTicker(asset);
}

function reset() {
  assetId.value = "";
  identifierValue.value = "";
  name.value = "";
  ticker.value = "";
  error.value = "";
}

function openCreate() {
  mode.value = "create";
  reset();
  dialog.value?.showModal();
}

function openEdit(asset?: EditableAsset | null) {
  const target = asset ?? props.assets[0];
  if (!target) return;
  mode.value = "edit";
  populate(target);
  error.value = "";
  dialog.value?.showModal();
}

function changeEditedAsset() {
  const asset = selectedAsset();
  if (asset) populate(asset);
}

function close() {
  if (!busy.value) dialog.value?.close();
}

async function save() {
  if (!valid.value) return;
  busy.value = true;
  error.value = "";
  const identity = identifierValue.value.trim().toUpperCase();
  const endpoint =
    mode.value === "create"
      ? `/${props.kind === "stock" ? "stocks" : "cryptos"}`
      : `/${props.kind === "stock" ? "stocks" : "cryptos"}/${encodeURIComponent(assetId.value)}`;
  const selected = selectedAsset();
  const scheme = props.kind === "crypto" ? "crypto_symbol" : "isin";
  const identifiers: InstrumentIdentifier[] = selected
    ? (selected.identifiers ?? []).map((item) => ({ ...item }))
    : [];
  // The canonical identifier is immutable during edits. Only creation builds
  // the importer-compatible default-venue primary row.
  if (!selected) {
    identifiers.unshift({
      scheme: scheme as "isin" | "crypto_symbol",
      value: identity,
      venue: "",
      is_primary: true,
    });
  }
  const yahooIdentifier = primaryIdentifier(selected ?? undefined, "yahoo");
  const tickerIndex = yahooIdentifier
    ? identifiers.findIndex(
        (item) =>
          item.scheme === "yahoo" &&
          item.value === yahooIdentifier.value &&
          item.venue === yahooIdentifier.venue &&
          item.is_primary === yahooIdentifier.is_primary,
      )
    : -1;
  const tickerRow = yahooIdentifier
    ? { ...yahooIdentifier, value: ticker.value.trim() }
    : {
        scheme: "yahoo" as const,
        value: ticker.value.trim(),
        venue: "",
        is_primary: true,
      };
  if (tickerIndex >= 0) identifiers[tickerIndex] = tickerRow;
  else identifiers.push(tickerRow);
  const body = {
    name: name.value.trim(),
    quote_currency: selected?.quote_currency ?? "EUR",
    identifiers,
    asset_class: selected?.asset_class ?? null,
    subtype: selected?.subtype ?? null,
    is_active: selected?.is_active ?? true,
  };
  try {
    const saved = await api<EditableAsset>(
      endpoint,
      json(mode.value === "create" ? "POST" : "PUT", body),
    );
    dialog.value?.close();
    emit("saved", saved);
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : t("shared.assetEditor.saveError");
  } finally {
    busy.value = false;
  }
}

defineExpose({ openCreate, openEdit });
</script>

<template>
  <dialog
    ref="dialog"
    class="asset-editor-dialog"
    aria-labelledby="asset-editor-title"
    @cancel.prevent="close"
  >
    <form @submit.prevent="save">
      <header>
        <div>
          <p>{{ sectionLabel }}</p>
          <h2 id="asset-editor-title">{{ title }}</h2>
        </div>
      </header>

      <div class="asset-editor-fields">
        <label>
          <span>{{ identifierLabel }}</span>
          <select
            v-if="mode === 'edit'"
            v-model="assetId"
            :aria-label="
              t('shared.assetEditor.selectAria', {
                identifier: identifierLabel,
              })
            "
            @change="changeEditedAsset"
          >
            <option
              v-for="asset in assets"
              :key="idOf(asset)"
              :value="idOf(asset)"
            >
              {{ asset.name }} · {{ identityOf(asset) }}
            </option>
          </select>
          <input
            v-else
            v-model="identifierValue"
            type="text"
            :placeholder="
              t(
                isCrypto
                  ? 'shared.assetEditor.cryptoIdentifierExample'
                  : 'shared.assetEditor.investmentIdentifierExample',
              )
            "
            autocomplete="off"
            required
          />
          <small v-if="mode === 'edit'">{{
            t("shared.assetEditor.immutableIdentifier")
          }}</small>
        </label>
        <label>
          <span>{{ t("shared.assetEditor.name") }}</span>
          <input
            v-model="name"
            type="text"
            :placeholder="
              t(
                isCrypto
                  ? 'shared.assetEditor.cryptoNameExample'
                  : 'shared.assetEditor.investmentNameExample',
              )
            "
            required
          />
        </label>
        <label class="ticker-field">
          <span>{{ t("shared.assetEditor.yahooTicker") }}</span>
          <input
            v-model="ticker"
            type="text"
            :placeholder="
              t(
                isCrypto
                  ? 'shared.assetEditor.cryptoTickerExample'
                  : 'shared.assetEditor.investmentTickerExample',
              )
            "
            autocomplete="off"
            required
          />
          <small>{{ t("shared.assetEditor.tickerHelp") }}</small>
        </label>
      </div>

      <p v-if="error" class="asset-editor-error" role="alert">{{ error }}</p>
      <footer>
        <button type="button" :disabled="busy" @click="close">
          {{ t("common.cancel") }}
        </button>
        <button class="primary" type="submit" :disabled="busy || !valid">
          {{
            busy
              ? t("common.saving")
              : mode === "create"
                ? t("shared.assetEditor.addAsset")
                : t("shared.assetEditor.saveChanges")
          }}
        </button>
      </footer>
    </form>
  </dialog>
</template>

<style scoped>
.asset-editor-dialog {
  width: min(560px, calc(100vw - 32px));
  padding: 0;
  border: 1px solid var(--fz-line);
  border-radius: 20px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 28px 80px rgba(0, 0, 0, 0.24);
}
.asset-editor-dialog::backdrop {
  background: rgba(6, 11, 8, 0.68);
  backdrop-filter: blur(5px);
}
.asset-editor-dialog form {
  padding: 24px;
}
.asset-editor-dialog header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.asset-editor-dialog header p {
  margin: 0 0 4px;
  color: var(--fz-accent);
  font-size: 10px;
  font-weight: 780;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.asset-editor-dialog h2 {
  margin: 0;
  font-size: 21px;
  letter-spacing: -0.035em;
}
.asset-editor-dialog header button {
  width: 34px;
  height: 34px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  cursor: pointer;
}
.asset-editor-fields {
  margin-top: 22px;
  padding: 18px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  border: 1px solid var(--fz-line);
  border-radius: 15px;
  background: var(--fz-surface-soft);
}
.asset-editor-fields label {
  min-width: 0;
  display: grid;
  gap: 7px;
}
.asset-editor-fields .ticker-field {
  grid-column: 1 / -1;
}
.asset-editor-fields span {
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 710;
}
.asset-editor-fields input,
.asset-editor-fields select {
  width: 100%;
  min-width: 0;
  padding: 11px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font: inherit;
  font-size: 12px;
  font-weight: 690;
}
.asset-editor-fields input:focus,
.asset-editor-fields select:focus {
  border-color: var(--fz-accent);
  outline: 3px solid color-mix(in srgb, var(--fz-accent) 14%, transparent);
}
.asset-editor-fields small {
  color: var(--fz-muted);
  font-size: 10px;
  line-height: 1.45;
}
.asset-editor-error {
  margin: 14px 2px 0;
  color: var(--fz-negative);
  font-size: 11px;
}
.asset-editor-dialog footer {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
}
.asset-editor-dialog footer button {
  padding: 10px 14px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: transparent;
  color: var(--fz-muted);
  font-weight: 710;
  cursor: pointer;
}
.asset-editor-dialog footer .primary {
  border-color: var(--fz-accent);
  background: var(--fz-accent);
  color: #fff;
}
.asset-editor-dialog button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
@media (max-width: 560px) {
  .asset-editor-fields {
    grid-template-columns: 1fr;
  }
  .asset-editor-fields .ticker-field {
    grid-column: auto;
  }
}
</style>
