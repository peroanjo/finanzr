<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { api } from "../api/client";
import type { CryptoOrder, FundOrder, StockOrder } from "../types/api";

const props = defineProps<{ kind: "fund" | "stock" | "crypto" }>();
const emit = defineEmits<{ deleted: [] }>();
const { t } = useI18n();
const dialog = ref<HTMLDialogElement>();
const movement = ref<FundOrder | CryptoOrder | StockOrder | null>(null);
const busy = ref(false);
const error = ref("");
const endpoint = computed(() =>
  props.kind === "fund"
    ? "/orders"
    : props.kind === "stock"
      ? "/stock-orders"
      : "/crypto-orders",
);
const assetName = computed(() => {
  if (!movement.value) return "";
  const assetId =
    "symbol" in movement.value ? movement.value.symbol : movement.value.isin;
  return `${assetId} · ${movement.value.asset_name}`;
});
const operationLabel = computed(() => {
  const operation = movement.value?.operation_type;
  const keys: Record<string, string> = {
    buy: "shared.movementEditor.buy",
    sell: "shared.movementEditor.sell",
    transfer_in: "shared.movementEditor.transferIn",
    transfer_out: "shared.movementEditor.transferOut",
  };
  return operation ? (keys[operation] ? t(keys[operation]) : operation) : "";
});

function open(value: FundOrder | CryptoOrder | StockOrder) {
  movement.value = value;
  error.value = "";
  dialog.value?.showModal();
}

function close() {
  if (!busy.value) dialog.value?.close();
}

async function remove() {
  if (!movement.value) return;
  busy.value = true;
  error.value = "";
  try {
    await api(`${endpoint.value}/${encodeURIComponent(movement.value.id)}`, {
      method: "DELETE",
    });
    dialog.value?.close();
    movement.value = null;
    emit("deleted");
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : t("shared.movementDelete.deleteError");
  } finally {
    busy.value = false;
  }
}

defineExpose({ open });
</script>

<template>
  <dialog
    ref="dialog"
    class="movement-delete-dialog"
    aria-labelledby="movement-delete-title"
    @cancel.prevent="close"
  >
    <form @submit.prevent="remove">
      <header>
        <div>
          <p>{{ t("shared.movementDelete.irreversible") }}</p>
          <h2 id="movement-delete-title">
            {{ t("shared.movementDelete.title") }}
          </h2>
        </div>
      </header>
      <div class="movement-delete-summary">
        <strong>{{ operationLabel }}</strong>
        <span>{{ assetName }}</span>
      </div>
      <p>{{ t("shared.movementDelete.warning") }}</p>
      <p v-if="error" class="movement-delete-error" role="alert">{{ error }}</p>
      <footer>
        <button type="button" :disabled="busy" @click="close">
          {{ t("common.cancel") }}
        </button>
        <button class="danger" type="submit" :disabled="busy">
          {{
            busy
              ? t("shared.movementDelete.deleting")
              : t("shared.movementDelete.deleteMovement")
          }}
        </button>
      </footer>
    </form>
  </dialog>
</template>

<style scoped>
.movement-delete-dialog {
  width: min(500px, calc(100vw - 32px));
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 20px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 28px 90px rgba(0, 0, 0, 0.34);
}
.movement-delete-dialog::backdrop {
  background: rgba(6, 11, 8, 0.68);
  backdrop-filter: blur(5px);
}
.movement-delete-dialog form {
  padding: 23px;
}
.movement-delete-dialog header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.movement-delete-dialog header p {
  margin: 0 0 3px;
  color: var(--fz-negative);
  font-size: 10px;
  font-weight: 760;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}
.movement-delete-dialog h2 {
  margin: 0;
  font-size: 18px;
  letter-spacing: -0.03em;
}
.movement-delete-dialog header > button {
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
.movement-delete-summary {
  margin-top: 22px;
  padding: 15px;
  display: grid;
  gap: 4px;
  border-radius: 12px;
  background: var(--fz-surface-soft);
}
.movement-delete-summary strong {
  font-size: 11px;
}
.movement-delete-summary span,
.movement-delete-dialog form > p {
  color: var(--fz-muted);
  font-size: 10px;
}
.movement-delete-dialog form > p {
  margin: 13px 2px 0;
  line-height: 1.5;
}
.movement-delete-dialog .movement-delete-error {
  color: var(--fz-negative);
}
.movement-delete-dialog footer {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
}
.movement-delete-dialog footer button {
  padding: 9px 13px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 710;
  cursor: pointer;
}
.movement-delete-dialog footer .danger {
  border-color: var(--fz-negative);
  background: var(--fz-negative);
  color: #fff;
}
.movement-delete-dialog footer button:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}
</style>
