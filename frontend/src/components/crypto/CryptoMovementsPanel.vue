<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import InvestmentCollapseButton from "../investments/InvestmentCollapseButton.vue";
import InvestmentMovementActions from "../investments/InvestmentMovementActions.vue";
import type { CryptoInstrument, CryptoOrder } from "../../types/api";
import { instrumentIdentity, instrumentName } from "../../domain/instruments";

export interface CryptoMovementsPanelProps {
  orders: CryptoOrder[];
  instruments: CryptoInstrument[];
  selectedAccountLabel: string;
  baseCurrency: string;
  formatMoney: (value: number) => string;
  formatQuantity: (value: number) => string;
  displayDate: (value: string) => string;
  basePrice: (order: CryptoOrder) => number;
  baseAmount: (order: CryptoOrder) => number;
  baseFee: (order: CryptoOrder) => number;
}

const props = defineProps<CryptoMovementsPanelProps>();
const emit = defineEmits<{
  add: [];
  edit: [order: CryptoOrder];
  delete: [order: CryptoOrder];
}>();
const { t, n } = useI18n();

const movementSymbol = ref("all");
const movementType = ref("all");
const movementStart = ref("");
const movementEnd = ref("");
const movementDraftStart = ref("");
const movementDraftEnd = ref("");
const movementPage = ref(1);
const movementCalendarDialog = ref<HTMLDialogElement>();
const movementPageSize = 15;

function readStorageItem(key: string) {
  try {
    return globalThis.localStorage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function writeStorageItem(key: string, value: string) {
  try {
    globalThis.localStorage?.setItem(key, value);
  } catch {
    // Storage can be unavailable or read-only in privacy mode.
  }
}

const collapsed = ref(
  readStorageItem("finanzr-crypto-movements-collapsed") === "true",
);

const movementSymbols = computed(() => {
  const names = new Map(
    props.instruments.map((item) => [
      instrumentIdentity(item),
      instrumentName(item),
    ]),
  );
  props.orders.forEach((item) => {
    names.set(
      item.symbol,
      item.asset_name || names.get(item.symbol) || item.symbol,
    );
  });
  return [...names.entries()]
    .filter(([symbol]) => props.orders.some((item) => item.symbol === symbol))
    .map(([symbol, name]) => ({ symbol, name }))
    .sort((a, b) => a.symbol.localeCompare(b.symbol));
});

const movementRangeValid = computed(() =>
  Boolean(
    movementDraftStart.value &&
      movementDraftEnd.value &&
      Date.parse(movementDraftStart.value) <= Date.parse(movementDraftEnd.value),
  ),
);
const filteredMovements = computed(() =>
  [...props.orders]
    .filter(
      (item) =>
        movementSymbol.value === "all" || item.symbol === movementSymbol.value,
    )
    .filter(
      (item) =>
        movementType.value === "all" ||
        operationGroup(item) === movementType.value,
    )
    .filter(
      (item) =>
        !movementStart.value ||
        item.trade_date.slice(0, 10) >= movementStart.value,
    )
    .filter(
      (item) =>
        !movementEnd.value || item.trade_date.slice(0, 10) <= movementEnd.value,
    )
    .sort(
      (a, b) =>
        b.trade_date.localeCompare(a.trade_date) ||
        String(b.id).localeCompare(String(a.id)),
    ),
);
const movementPages = computed(() =>
  Math.max(1, Math.ceil(filteredMovements.value.length / movementPageSize)),
);
const displayedMovements = computed(() =>
  filteredMovements.value.slice(
    (movementPage.value - 1) * movementPageSize,
    movementPage.value * movementPageSize,
  ),
);
const movementRangeLabel = computed(() =>
  movementStart.value && movementEnd.value
    ? props.displayDate(movementStart.value) +
      " → " +
      props.displayDate(movementEnd.value)
    : t("crypto.movements.allDates"),
);

watch([movementSymbol, movementType, movementStart, movementEnd], () => {
  movementPage.value = 1;
});
watch(movementPages, (pages) => {
  if (movementPage.value > pages) movementPage.value = pages;
});
function initializeMovementRange() {
  if (!props.orders.length || (movementStart.value && movementEnd.value)) return;
  const dates = props.orders
    .map((item) => item.trade_date.slice(0, 10))
    .sort();
  movementStart.value = dates[0];
  movementEnd.value = dates.at(-1) ?? dates[0];
  movementDraftStart.value = movementStart.value;
  movementDraftEnd.value = movementEnd.value;
}
watch(
  () => props.orders,
  () => {
    movementPage.value = 1;
    initializeMovementRange();
  },
  { immediate: true },
);

function resetForAccount(resetType = true) {
  movementSymbol.value = "all";
  movementStart.value = "";
  movementEnd.value = "";
  movementDraftStart.value = "";
  movementDraftEnd.value = "";
  movementPage.value = 1;
  if (resetType) movementType.value = "all";
}

function resetPage() {
  movementPage.value = 1;
}

defineExpose({ resetForAccount, resetPage, initializeMovementRange });

function toggleCollapsed() {
  collapsed.value = !collapsed.value;
  writeStorageItem(
    "finanzr-crypto-movements-collapsed",
    String(collapsed.value),
  );
}

function operationGroup(order: CryptoOrder) {
  return order.operation_type === "buy" ? "in" : "out";
}

function movementLabel(order: CryptoOrder) {
  if (order.operation_type === "buy") return t("crypto.movements.buy");
  if (order.operation_type === "sell") return t("crypto.movements.sell");
  return order.provider_operation_type || order.operation_type;
}

function originalMoney(value: number, currency?: string) {
  return n(value, {
    style: "currency",
    currency: currency || "EUR",
    maximumFractionDigits: 2,
  });
}

function hasOriginalCurrency(order: CryptoOrder) {
  return Boolean(order.currency && order.currency !== props.baseCurrency);
}

function openMovementCalendar() {
  movementDraftStart.value = movementStart.value;
  movementDraftEnd.value = movementEnd.value;
  movementCalendarDialog.value?.showModal();
}

function closeMovementCalendar() {
  movementCalendarDialog.value?.close();
}

function applyMovementRange() {
  if (!movementRangeValid.value) return;
  movementStart.value = movementDraftStart.value;
  movementEnd.value = movementDraftEnd.value;
  closeMovementCalendar();
}
</script>

<template>
  <article class="fund-performance-panel movements-panel" :class="{ collapsed }">
    <header class="fund-secondary-header">
      <div>
        <p class="section-label">{{ t("crypto.movements.section") }}</p>
        <h2>{{ t("crypto.movements.title") }}</h2>
        <p class="fund-range-label">
          {{
            t(
              filteredMovements.length === 1
                ? "crypto.movements.operation"
                : "crypto.movements.operations",
              { count: filteredMovements.length },
            )
          }}
          · {{ movementRangeLabel }}
        </p>
      </div>
      <div class="fund-collapsible-actions">
        <div v-show="!collapsed" class="movement-filters">
          <button type="button" class="add-movement" @click="emit('add')">
            + {{ t("crypto.movements.add") }}
          </button>
          <select
            v-model="movementSymbol"
            :aria-label="t('crypto.movements.currencyFilterAria')"
          >
            <option value="all">
              {{ t("crypto.movements.allCurrencies") }}
            </option>
            <option
              v-for="item in movementSymbols"
              :key="item.symbol"
              :value="item.symbol"
            >
              {{ item.symbol }} · {{ item.name }}
            </option>
          </select>
          <select
            v-model="movementType"
            :aria-label="t('crypto.movements.filterTypeAria')"
          >
            <option value="all">
              {{ t("crypto.movements.allMovements") }}
            </option>
            <option value="in">{{ t("crypto.movements.entries") }}</option>
            <option value="out">{{ t("crypto.movements.exits") }}</option>
          </select>
          <button
            type="button"
            :aria-label="t('crypto.movements.dateFilterAria')"
            @click="openMovementCalendar"
          >
            {{ movementRangeLabel }}
          </button>
        </div>
        <InvestmentCollapseButton
          :collapsed="collapsed"
          controls="crypto-movements-content"
          :label="
            t(
              collapsed
                ? 'crypto.movements.expandAria'
                : 'crypto.movements.collapseAria',
            )
          "
          @toggle="toggleCollapsed"
        />
      </div>
    </header>
    <div v-show="!collapsed" id="crypto-movements-content">
      <div class="fund-table-scroll">
        <table class="fund-table movement-table">
          <thead>
            <tr>
              <th>{{ t("crypto.movements.date") }}</th>
              <th>{{ t("crypto.movements.movement") }}</th>
              <th>{{ t("crypto.movements.asset") }}</th>
              <th>{{ t("crypto.movements.account") }}</th>
              <th>{{ t("crypto.movements.quantity") }}</th>
              <th>{{ t("crypto.movements.price") }}</th>
              <th>{{ t("crypto.movements.amount") }}</th>
              <th>{{ t("crypto.movements.fee") }}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in displayedMovements"
              :key="item.id"
              :data-testid="'movement-' + item.id"
            >
              <td>{{ props.displayDate(item.trade_date) }}</td>
              <td>
                <span class="operation-pill" :class="operationGroup(item)">
                  {{ movementLabel(item) }}</span
                >
              </td>
              <td>
                <strong>{{ item.asset_name }}</strong
                ><small>{{ item.symbol }}</small>
              </td>
              <td>
                {{ item.account_name || props.selectedAccountLabel
                }}<small>{{
                  item.platform || t("crypto.accounts.cryptoFallback")
                }}</small>
              </td>
              <td>{{ props.formatQuantity(item.quantity) }}</td>
              <td>
                {{ props.formatMoney(props.basePrice(item))
                }}<small v-if="hasOriginalCurrency(item)">{{
                  originalMoney(item.unit_price, item.currency)
                }}</small>
              </td>
              <td>
                <strong>{{ props.formatMoney(props.baseAmount(item)) }}</strong
                ><small v-if="hasOriginalCurrency(item)">{{
                  originalMoney(item.net_amount, item.currency)
                }}</small>
              </td>
              <td>
                {{ props.formatMoney(props.baseFee(item))
                }}<small v-if="hasOriginalCurrency(item)">{{
                  originalMoney(item.fee, item.currency)
                }}</small>
              </td>
              <td>
                <InvestmentMovementActions
                  :edit-label="t('crypto.movements.edit')"
                  :delete-label="t('crypto.movements.delete')"
                  @edit="emit('edit', item)"
                  @delete="emit('delete', item)"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!filteredMovements.length" class="fund-empty-compact">
        {{ t("crypto.movements.noResults") }}
      </div>
      <nav
        v-else-if="movementPages > 1"
        class="movement-pagination"
        :aria-label="t('crypto.movements.paginationAria')"
      >
        <span>{{
          t("crypto.movements.page", {
            page: movementPage,
            pages: movementPages,
          })
        }}</span>
        <div>
          <button
            type="button"
            :disabled="movementPage === 1"
            @click="movementPage -= 1"
          >
            {{ t("crypto.movements.previous") }}
          </button>
          <button
            type="button"
            :disabled="movementPage === movementPages"
            @click="movementPage += 1"
          >
            {{ t("crypto.movements.next") }}
          </button>
        </div>
      </nav>
    </div>
  </article>

  <dialog
    ref="movementCalendarDialog"
    class="calendar-dialog movement-calendar-dialog"
    aria-labelledby="movement-calendar-title"
    @cancel.prevent="closeMovementCalendar"
  >
    <form @submit.prevent="applyMovementRange">
      <header>
        <div>
          <p class="section-label">
            {{ t("crypto.movements.filterSection") }}
          </p>
          <h2 id="movement-calendar-title">
            {{ t("crypto.calendar.selectDates") }}
          </h2>
        </div>
      </header>
      <div class="calendar-fields">
        <label>
          <span>{{ t("crypto.calendar.from") }}</span>
          <input
            v-model="movementDraftStart"
            type="date"
            :max="movementDraftEnd"
            required
          />
        </label>
        <span aria-hidden="true">→</span>
        <label>
          <span>{{ t("crypto.calendar.to") }}</span>
          <input
            v-model="movementDraftEnd"
            type="date"
            :min="movementDraftStart"
            required
          />
        </label>
      </div>
      <footer class="calendar-dialog-actions">
        <button type="button" @click="closeMovementCalendar">
          {{ t("crypto.actions.cancel") }}
        </button>
        <button
          class="primary"
          type="submit"
          :disabled="!movementRangeValid"
        >
          {{ t("crypto.calendar.applyPeriod") }}
        </button>
      </footer>
    </form>
  </dialog>
</template>

<style scoped>
.fund-performance-panel {
  margin-top: 20px;
  padding: 24px;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 22px;
  background: var(--fz-surface);
  box-shadow: var(--fz-shadow);
}
.movements-panel {
  margin-top: 20px;
  padding: 24px;
  overflow: hidden;
}
.fund-secondary-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
}
.fund-secondary-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 750;
  letter-spacing: -0.03em;
}
.fund-range-label {
  margin: 7px 0 0;
  color: var(--fz-muted);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.fund-collapsible-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
.movement-filters {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}
.movement-filters select,
.movement-filters button {
  min-height: 34px;
  padding: 7px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  font-size: 11px;
}
.movement-filters .add-movement {
  background: var(--fz-accent);
  color: #fff;
  white-space: nowrap;
  cursor: pointer;
}
.fund-table-scroll {
  overflow-x: auto;
}
.fund-table {
  width: 100%;
  min-width: 980px;
  margin-top: 18px;
  border-collapse: collapse;
  font-size: 11px;
}
.fund-table th {
  padding: 0 10px 9px;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 700;
  text-align: right;
  border-bottom: 1px solid var(--fz-line);
}
.fund-table th:first-child,
.fund-table td:first-child,
.fund-table th:nth-child(2),
.fund-table td:nth-child(2) {
  text-align: left;
}
.fund-table td {
  padding: 11px 10px;
  border-bottom: 1px solid var(--fz-line);
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.fund-table td small {
  display: block;
  color: var(--fz-muted);
  font-size: 9px;
}
.movement-row-actions {
  display: flex;
  justify-content: flex-end;
  gap: 5px;
}
.movement-row-actions button {
  padding: 6px 8px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 690;
  cursor: pointer;
}
.movement-row-actions button:hover {
  border-color: var(--fz-accent);
  color: var(--fz-ink);
}
.movement-row-actions .delete {
  color: var(--fz-negative);
}
.movement-pagination {
  margin-top: 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  color: var(--fz-muted);
  font-size: 11px;
}
.movement-pagination button {
  padding: 7px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.movement-pagination button:disabled {
  opacity: 0.4;
  cursor: default;
}
.fund-empty-compact {
  min-height: 180px;
  display: grid;
  place-content: center;
  gap: 5px;
  color: var(--fz-muted);
  font-size: 10px;
  text-align: center;
}
.calendar-dialog {
  width: min(520px, calc(100vw - 32px));
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 20px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 28px 90px rgba(0, 0, 0, 0.34);
}
.calendar-dialog::backdrop {
  background: rgba(6, 11, 8, 0.68);
  backdrop-filter: blur(5px);
}
.calendar-dialog form {
  padding: 23px;
}
.calendar-dialog header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.calendar-dialog h2 {
  font-size: 18px;
}
.calendar-fields {
  margin-top: 23px;
  padding: 18px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: end;
  gap: 12px;
  border-radius: 14px;
  background: var(--fz-surface-soft);
}
.calendar-fields label {
  display: grid;
  gap: 7px;
}
.calendar-fields label span {
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 690;
}
.calendar-fields > span {
  padding-bottom: 9px;
  color: var(--fz-muted);
}
.calendar-fields input {
  width: 100%;
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  font-size: 11px;
  font-weight: 720;
}
.calendar-dialog-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
}
.calendar-dialog-actions button {
  padding: 9px 13px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 12px;
  font-weight: 710;
  cursor: pointer;
}
.calendar-dialog-actions .primary {
  border-color: var(--fz-accent);
  background: var(--fz-accent);
  color: #f4fff9;
}
.calendar-dialog-actions button:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}
@media (max-width: 1050px) {
  .fund-secondary-header {
    align-items: stretch;
    flex-direction: column;
  }
}
@media (max-width: 720px) {
  .fund-performance-panel {
    padding: 19px 17px;
    border-radius: 18px;
  }
  .fund-secondary-header {
    display: grid;
    justify-content: stretch;
    gap: 14px;
  }
  .fund-collapsible-actions {
    width: 100%;
    flex-wrap: wrap;
  }
  .fund-collapsible-actions .movement-filters {
    width: 100%;
    order: 2;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }
  .fund-collapsible-actions .movement-filters select,
  .fund-collapsible-actions .movement-filters button {
    width: 100%;
    min-width: 0;
  }
  .calendar-fields {
    grid-template-columns: minmax(0, 1fr);
  }
  .calendar-fields > span {
    display: none;
  }
}
</style>
