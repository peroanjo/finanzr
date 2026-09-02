<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { api, json } from "../api/client";
import type {
  CryptoAccount,
  CryptoOrder,
  FundAccount,
  FundOrder,
  StockAccount,
  StockOrder,
} from "../types/api";
import {
  movementAssetIdentifier,
  type MovementAssetOption,
  type MovementKind,
} from "./movementEditor";

const props = defineProps<{
  kind: MovementKind;
  accounts: Array<FundAccount | CryptoAccount | StockAccount>;
  assets: MovementAssetOption[];
  selectedAccount: string;
}>();
const emit = defineEmits<{ saved: [] }>();
const { t } = useI18n();

const dialog = ref<HTMLDialogElement>();
const mode = ref<"create" | "edit">("create");
const movementId = ref("");
const originalAccountId = ref("");
const accountId = ref("");
const assetId = ref("");
const operationType = ref("");
const tradeDate = ref("");
const settlementDate = ref("");
const quantity = ref("");
const unitPrice = ref("");
const netAmount = ref("");
const fee = ref("0");
const currency = ref("EUR");
const saveback = ref(false);
const busy = ref(false);
const error = ref("");
const today = new Date().toISOString().slice(0, 10);

const operations = computed(() =>
  props.kind === "fund"
    ? [
        {
          value: "SUSCRIPCION",
          label: t("shared.movementEditor.contribution"),
        },
        {
          value: "SUSCR.POR TRASPASO I",
          label: t("shared.movementEditor.transferIn"),
        },
        {
          value: "REEMB.POR TRASPASO I",
          label: t("shared.movementEditor.transferOut"),
        },
        { value: "REEMBOLSO", label: t("shared.movementEditor.redemption") },
      ]
    : [
        { value: "Compra", label: t("shared.movementEditor.buy") },
        { value: "Venta", label: t("shared.movementEditor.sell") },
      ],
);
const valid = computed(() =>
  Boolean(
    accountId.value &&
    assetId.value &&
    operationType.value &&
    tradeDate.value &&
    Number(quantity.value) > 0 &&
    Number(unitPrice.value) >= 0 &&
    Number(netAmount.value) >= 0 &&
    (props.kind === "fund" || Number(fee.value) >= 0),
  ),
);
const endpoint = computed(() =>
  props.kind === "fund"
    ? "/orders"
    : props.kind === "stock"
      ? "/stock-orders"
      : "/crypto-orders",
);
const assetLabel = computed(() =>
  props.kind === "fund"
    ? t("shared.movementEditor.fund")
    : props.kind === "stock"
      ? t("shared.movementEditor.stock")
      : t("shared.movementEditor.crypto"),
);
const selectedProvider = computed(
  () =>
    props.accounts.find((account) => String(account.id) === accountId.value)
      ?.platform ?? "",
);
const selectedAccountCurrency = computed(
  () =>
    props.accounts.find((account) => String(account.id) === accountId.value)
      ?.currency ?? "EUR",
);
const canUseSaveback = computed(
  () =>
    props.kind === "stock" &&
    selectedProvider.value.toLowerCase().includes("trade republic"),
);

function reset() {
  movementId.value = "";
  originalAccountId.value = "";
  accountId.value =
    props.selectedAccount === "all"
      ? String(props.accounts[0]?.id ?? "")
      : props.selectedAccount;
  assetId.value = props.assets[0]?.id ?? "";
  operationType.value = operations.value[0]?.value ?? "";
  tradeDate.value = today;
  settlementDate.value = "";
  quantity.value = "";
  unitPrice.value = "";
  netAmount.value = "";
  fee.value = "0";
  currency.value = props.assets[0]?.currency || selectedAccountCurrency.value;
  saveback.value = false;
  error.value = "";
}

function openCreate() {
  mode.value = "create";
  reset();
  dialog.value?.showModal();
}

function openEdit(movement: FundOrder | CryptoOrder | StockOrder) {
  mode.value = "edit";
  movementId.value = movement.operacion_id;
  originalAccountId.value = String(movement.cuenta_id);
  accountId.value = String(movement.cuenta_id);
  assetId.value = "isin" in movement ? movement.isin : movement.symbol;
  operationType.value = movement.tipo_operacion;
  tradeDate.value = movement.fecha_operacion.slice(0, 10);
  settlementDate.value =
    "fecha_liquidacion" in movement
      ? movement.fecha_liquidacion.slice(0, 10)
      : "";
  quantity.value = String(movement.titulos);
  unitPrice.value = String(
    "precio_neto" in movement ? movement.precio_neto : movement.precio_compra,
  );
  netAmount.value = String(movement.importe_neto);
  fee.value = String("comision" in movement ? movement.comision : 0);
  currency.value = movement.moneda || selectedAccountCurrency.value;
  saveback.value = "es_saveback" in movement ? movement.es_saveback : false;
  error.value = "";
  dialog.value?.showModal();
}

function close() {
  if (!busy.value) dialog.value?.close();
}

async function save() {
  if (!valid.value) return;
  busy.value = true;
  error.value = "";
  const payload: Record<string, string | number> = {
    account_id: accountId.value,
    fecha_operacion: tradeDate.value,
    tipo_operacion: operationType.value,
    titulos: Number(quantity.value),
    importe_neto: Number(netAmount.value),
    divisa: currency.value.trim().toUpperCase(),
    ...movementAssetIdentifier(props.kind, assetId.value),
  };
  if (props.kind === "fund") {
    payload.fecha_liquidacion = settlementDate.value;
    payload.precio_neto = Number(unitPrice.value);
  } else {
    payload.precio_compra = Number(unitPrice.value);
    payload.comision = Number(fee.value);
    if (props.kind === "stock")
      payload.es_saveback = canUseSaveback.value && saveback.value ? 1 : 0;
  }
  if (mode.value === "edit")
    payload.original_account_id = originalAccountId.value;
  try {
    const target =
      mode.value === "edit"
        ? `${endpoint.value}/${encodeURIComponent(movementId.value)}`
        : endpoint.value;
    await api(target, json(mode.value === "edit" ? "PUT" : "POST", payload));
    dialog.value?.close();
    emit("saved");
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : t("shared.movementEditor.saveError");
  } finally {
    busy.value = false;
  }
}

defineExpose({ openCreate, openEdit });
</script>

<template>
  <dialog
    ref="dialog"
    class="movement-editor-dialog"
    aria-labelledby="movement-editor-title"
    @cancel.prevent="close"
  >
    <form @submit.prevent="save">
      <header>
        <div>
          <p>{{ t("shared.movementEditor.manualMovement") }}</p>
          <h2 id="movement-editor-title">
            {{
              t(
                mode === "edit"
                  ? "shared.movementEditor.editTitle"
                  : "shared.movementEditor.addTitle",
              )
            }}
          </h2>
        </div>
      </header>

      <div class="movement-editor-fields">
        <label>
          <span>{{ t("shared.movementEditor.account") }}</span>
          <select v-model="accountId" required>
            <option
              v-for="account in accounts"
              :key="account.id"
              :value="String(account.id)"
            >
              {{ account.name }} · {{ account.platform }}
            </option>
          </select>
        </label>
        <label>
          <span>{{ assetLabel }}</span>
          <select v-model="assetId" required>
            <option v-for="asset in assets" :key="asset.id" :value="asset.id">
              {{ asset.label }}
            </option>
          </select>
        </label>
        <label>
          <span>{{ t("shared.movementEditor.type") }}</span>
          <select v-model="operationType" required>
            <option
              v-for="operation in operations"
              :key="operation.value"
              :value="operation.value"
            >
              {{ operation.label }}
            </option>
          </select>
        </label>
        <label>
          <span>{{ t("shared.movementEditor.tradeDate") }}</span>
          <input v-model="tradeDate" type="date" required />
        </label>
        <label v-if="kind === 'fund'">
          <span
            >{{ t("shared.movementEditor.settlementDate") }}
            <em>{{ t("common.optional") }}</em></span
          >
          <input v-model="settlementDate" type="date" :min="tradeDate" />
        </label>
        <label>
          <span>{{
            t(
              kind === "fund"
                ? "shared.movementEditor.units"
                : "shared.movementEditor.quantity",
            )
          }}</span>
          <input v-model="quantity" type="number" min="0" step="any" required />
        </label>
        <label>
          <span>{{ t("shared.movementEditor.unitPrice") }}</span>
          <input
            v-model="unitPrice"
            type="number"
            min="0"
            step="any"
            required
          />
        </label>
        <label>
          <span>{{ t("shared.movementEditor.netAmount") }}</span>
          <input
            v-model="netAmount"
            type="number"
            min="0"
            step="any"
            required
          />
        </label>
        <label>
          <span>{{ t("shared.movementEditor.currency") }}</span>
          <input
            v-model="currency"
            type="text"
            maxlength="3"
            minlength="3"
            pattern="[A-Za-z]{3}"
            required
          />
        </label>
        <label v-if="kind !== 'fund'">
          <span>{{ t("shared.movementEditor.fee") }}</span>
          <input v-model="fee" type="number" min="0" step="any" required />
        </label>
        <label v-if="canUseSaveback" class="saveback-field">
          <span>{{ t("shared.movementEditor.saveback") }}</span>
          <input v-model="saveback" type="checkbox" />
        </label>
      </div>

      <p class="movement-editor-note">
        {{ t("shared.movementEditor.note") }}
      </p>
      <p v-if="error" class="movement-editor-error" role="alert">{{ error }}</p>
      <footer>
        <button type="button" :disabled="busy" @click="close">
          {{ t("common.cancel") }}
        </button>
        <button class="primary" type="submit" :disabled="busy || !valid">
          {{
            busy ? t("common.saving") : t("shared.movementEditor.saveMovement")
          }}
        </button>
      </footer>
    </form>
  </dialog>
</template>

<style scoped>
.movement-editor-dialog {
  width: min(680px, calc(100vw - 32px));
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 20px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 28px 90px rgba(0, 0, 0, 0.34);
}
.movement-editor-dialog::backdrop {
  background: rgba(6, 11, 8, 0.68);
  backdrop-filter: blur(5px);
}
.movement-editor-dialog form {
  padding: 23px;
}
.movement-editor-dialog header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.movement-editor-dialog header p {
  margin: 0 0 3px;
  color: var(--fz-accent);
  font-size: 10px;
  font-weight: 760;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}
.movement-editor-dialog h2 {
  margin: 0;
  font-size: 18px;
  letter-spacing: -0.03em;
}
.movement-editor-dialog header > button {
  width: 31px;
  height: 31px;
  display: grid;
  place-items: center;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  font-size: 18px;
  cursor: pointer;
}
.movement-editor-fields {
  margin-top: 22px;
  padding: 18px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  border-radius: 14px;
  background: var(--fz-surface-soft);
}
.movement-editor-fields label {
  min-width: 0;
  display: grid;
  gap: 7px;
}
.movement-editor-fields span {
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 690;
}
.movement-editor-fields em {
  font-size: 10px;
  font-style: normal;
  font-weight: 550;
}
.movement-editor-fields input,
.movement-editor-fields select {
  min-width: 0;
  width: 100%;
  padding: 10px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font-size: 12px;
}
.movement-editor-fields .saveback-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface);
}
.movement-editor-fields .saveback-field input {
  width: 18px;
  height: 18px;
}
.movement-editor-note {
  margin: 13px 2px 0;
  color: var(--fz-muted);
  font-size: 10px;
  line-height: 1.5;
}
.movement-editor-error {
  margin: 10px 2px 0;
  color: var(--fz-negative);
  font-size: 11px;
}
.movement-editor-dialog footer {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
}
.movement-editor-dialog footer button {
  padding: 9px 13px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 710;
  cursor: pointer;
}
.movement-editor-dialog footer .primary {
  border-color: var(--fz-accent);
  background: var(--fz-accent);
  color: #f4fff9;
}
.movement-editor-dialog footer button:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

@media (max-width: 620px) {
  .movement-editor-dialog form {
    padding: 19px;
  }
  .movement-editor-fields {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
