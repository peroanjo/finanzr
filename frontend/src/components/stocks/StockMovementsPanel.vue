<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import InvestmentCollapseButton from "../investments/InvestmentCollapseButton.vue";
import InvestmentMovementActions from "../investments/InvestmentMovementActions.vue";
import type { StockOrder, StockPosition } from "../../types/api";

export interface StockMovementsPanelProps {
  orders: StockOrder[];
  positions: StockPosition[];
  selectedAccountLabel: string;
  accountKey: string;
  baseCurrency: string;
  formatMoney: (value: number) => string;
  formatQuantity: (value: number) => string;
  displayDate: (value: string) => string;
  positionIdentity: (position: StockPosition) => string;
}

const props = defineProps<StockMovementsPanelProps>();
const emit = defineEmits<{
  add: [];
  edit: [order: StockOrder];
  delete: [order: StockOrder];
}>();
const { t, n, locale } = useI18n();

const movementIsin = ref("all");
const movementType = ref("all");
const movementStart = ref("");
const movementEnd = ref("");
const movementDraftStart = ref("");
const movementDraftEnd = ref("");
const movementPage = ref(1);
const collapsed = ref(
  localStorage.getItem("finanzr-stocks-movements-collapsed") === "true",
);
const movementCalendarDialog = ref<HTMLDialogElement>();
const movementPageSize = 15;

const movementRangeValid = computed(() =>
  Boolean(
    movementDraftStart.value &&
    movementDraftEnd.value &&
    Date.parse(movementDraftStart.value) <= Date.parse(movementDraftEnd.value),
  ),
);
const filteredOrders = computed(() =>
  [...props.orders]
    .filter(
      (order) =>
        movementIsin.value === "all" || order.isin === movementIsin.value,
    )
    .filter(
      (order) =>
        movementType.value === "all" ||
        operationGroup(order) === movementType.value,
    )
    .filter(
      (order) =>
        !movementStart.value || order.trade_date >= movementStart.value,
    )
    .filter(
      (order) => !movementEnd.value || order.trade_date <= movementEnd.value,
    )
    .sort((a, b) => b.trade_date.localeCompare(a.trade_date, locale.value)),
);
const movementPages = computed(() =>
  Math.max(1, Math.ceil(filteredOrders.value.length / movementPageSize)),
);
const displayedOrders = computed(() =>
  filteredOrders.value.slice(
    (movementPage.value - 1) * movementPageSize,
    movementPage.value * movementPageSize,
  ),
);
const movementRangeLabel = computed(() =>
  movementStart.value && movementEnd.value
    ? props.displayDate(movementStart.value) +
      " → " +
      props.displayDate(movementEnd.value)
    : t("stocks.movements.allHistory"),
);

watch([movementIsin, movementType, movementStart, movementEnd], () => {
  movementPage.value = 1;
});
watch(
  () => props.accountKey,
  () => {
    movementIsin.value = "all";
    movementType.value = "all";
    movementStart.value = "";
    movementEnd.value = "";
    movementPage.value = 1;
  },
);
watch(
  () => props.orders,
  (orders) => {
    if (!movementStart.value && orders.length) {
      const dates = orders.map((order) => order.trade_date).sort();
      movementStart.value = dates[0];
      movementEnd.value = dates.at(-1) ?? dates[0];
    }
  },
  { immediate: true },
);

function toggleCollapsed() {
  collapsed.value = !collapsed.value;
  localStorage.setItem(
    "finanzr-stocks-movements-collapsed",
    String(collapsed.value),
  );
}

function operationGroup(order: StockOrder) {
  return order.operation_type === "buy" ? "in" : "out";
}

function operationLabel(order: StockOrder) {
  return order.operation_type === "buy"
    ? t("stocks.movements.buy")
    : t("stocks.movements.sell");
}

function originalMoney(value: number, currency?: string) {
  return n(value, {
    style: "currency",
    currency: currency || "EUR",
    maximumFractionDigits: 2,
  });
}

function hasOriginalCurrency(order: StockOrder) {
  return Boolean(order.currency && order.currency !== props.baseCurrency);
}

function basePrice(order: StockOrder) {
  return order.base_unit_price ?? order.unit_price;
}

function baseAmount(order: StockOrder) {
  return order.base_net_amount ?? order.net_amount;
}

function baseFee(order: StockOrder) {
  return order.base_fee ?? order.fee;
}

function openMovementCalendar() {
  movementDraftStart.value = movementStart.value;
  movementDraftEnd.value = movementEnd.value;
  movementCalendarDialog.value?.showModal();
}

function applyMovementRange() {
  if (!movementRangeValid.value) return;
  movementStart.value = movementDraftStart.value;
  movementEnd.value = movementDraftEnd.value;
  movementCalendarDialog.value?.close();
}

function closeMovementCalendar() {
  movementCalendarDialog.value?.close();
}
</script>

<template>
  <article
    class="fund-performance-panel movements-panel"
    :class="{ collapsed }"
  >
    <header class="fund-secondary-header">
      <div>
        <p class="section-label">{{ t("stocks.movements.section") }}</p>
        <h2>{{ t("stocks.movements.title") }}</h2>
        <p class="fund-range-label">
          {{
            t(
              filteredOrders.length === 1
                ? "stocks.movements.operation"
                : "stocks.movements.operations",
              { count: filteredOrders.length },
            )
          }}
          · {{ movementRangeLabel }}
        </p>
      </div>
      <div class="fund-collapsible-actions">
        <div v-show="!collapsed" class="movement-filters">
          <button type="button" class="add-movement" @click="emit('add')">
            + {{ t("stocks.movements.add") }}
          </button>
          <select
            v-model="movementIsin"
            :aria-label="t('stocks.movements.assetFilterAria')"
          >
            <option value="all">{{ t("stocks.movements.allAssets") }}</option>
            <option
              v-for="position in props.positions"
              :key="position.instrument_id"
              :value="props.positionIdentity(position)"
            >
              {{ position.name }}
            </option>
          </select>
          <select
            v-model="movementType"
            :aria-label="t('stocks.movements.filterTypeAria')"
          >
            <option value="all">
              {{ t("stocks.movements.allMovements") }}
            </option>
            <option value="in">{{ t("stocks.movements.entries") }}</option>
            <option value="out">{{ t("stocks.movements.exits") }}</option>
          </select>
          <button
            type="button"
            :aria-label="t('stocks.movements.dateFilterAria')"
            @click="openMovementCalendar"
          >
            {{ movementRangeLabel }}
          </button>
        </div>
        <InvestmentCollapseButton
          :collapsed="collapsed"
          controls="stock-movements-content"
          :label="
            t(
              collapsed
                ? 'stocks.movements.expandAria'
                : 'stocks.movements.collapseAria',
            )
          "
          @toggle="toggleCollapsed"
        />
      </div>
    </header>
    <div v-show="!collapsed" id="stock-movements-content">
      <div class="fund-table-scroll">
        <table class="fund-table movement-table">
          <thead>
            <tr>
              <th>{{ t("stocks.movements.date") }}</th>
              <th>{{ t("stocks.movements.movement") }}</th>
              <th>{{ t("stocks.movements.asset") }}</th>
              <th>{{ t("stocks.movements.account") }}</th>
              <th>{{ t("stocks.movements.quantity") }}</th>
              <th>{{ t("stocks.movements.price") }}</th>
              <th>{{ t("stocks.movements.amount") }}</th>
              <th>{{ t("stocks.movements.fee") }}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="order in displayedOrders" :key="order.id">
              <td>{{ props.displayDate(order.trade_date) }}</td>
              <td>
                <span class="operation-pill" :class="operationGroup(order)">
                  {{ operationLabel(order)
                  }}<small v-if="order.is_saveback">{{
                    t("stocks.movements.cashback")
                  }}</small>
                </span>
              </td>
              <td>
                <strong>{{ order.asset_name }}</strong
                ><small>{{ order.isin }}</small>
              </td>
              <td>
                {{ order.account_name ?? props.selectedAccountLabel
                }}<small>{{ order.platform }}</small>
              </td>
              <td>{{ props.formatQuantity(order.quantity) }}</td>
              <td>
                {{ props.formatMoney(basePrice(order)) }}
                <small v-if="hasOriginalCurrency(order)">{{
                  t("stocks.movements.originalValue", {
                    value: originalMoney(order.unit_price, order.currency),
                  })
                }}</small>
              </td>
              <td>
                <strong>{{ props.formatMoney(baseAmount(order)) }}</strong
                ><small v-if="hasOriginalCurrency(order)">{{
                  t("stocks.movements.originalValue", {
                    value: originalMoney(order.net_amount, order.currency),
                  })
                }}</small>
              </td>
              <td>
                {{ props.formatMoney(baseFee(order)) }}
                <small v-if="hasOriginalCurrency(order)">{{
                  t("stocks.movements.originalFee", {
                    value: originalMoney(order.fee, order.currency),
                  })
                }}</small>
              </td>
              <td>
                <InvestmentMovementActions
                  :edit-label="
                    t('stocks.movements.editAria', {
                      asset: order.asset_name,
                    })
                  "
                  :delete-label="
                    t('stocks.movements.deleteAria', {
                      asset: order.asset_name,
                    })
                  "
                  @edit="emit('edit', order)"
                  @delete="emit('delete', order)"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!filteredOrders.length" class="fund-empty-compact">
        {{ t("stocks.movements.noResults") }}
      </div>
      <nav
        v-else-if="movementPages > 1"
        class="movement-pagination"
        :aria-label="t('stocks.movements.paginationAria')"
      >
        <span>{{
          t("stocks.movements.page", {
            page: movementPage,
            pages: movementPages,
          })
        }}</span>
        <div>
          <button
            type="button"
            :disabled="movementPage === 1"
            @click="movementPage--"
          >
            {{ t("stocks.movements.previous") }}
          </button>
          <button
            type="button"
            :disabled="movementPage === movementPages"
            @click="movementPage++"
          >
            {{ t("stocks.movements.next") }}
          </button>
        </div>
      </nav>
    </div>
  </article>

  <dialog
    ref="movementCalendarDialog"
    class="stock-dialog stock-movement-dialog"
    aria-labelledby="stocks-movement-calendar-title"
  >
    <form @submit.prevent="applyMovementRange">
      <header>
        <h2 id="stocks-movement-calendar-title">
          {{ t("stocks.calendar.selectDates") }}
        </h2>
      </header>
      <div class="stock-calendar-fields">
        <label
          ><span>{{ t("stocks.calendar.from") }}</span
          ><input
            v-model="movementDraftStart"
            type="date"
            :max="movementDraftEnd"
            required /></label
        ><label
          ><span>{{ t("stocks.calendar.to") }}</span
          ><input
            v-model="movementDraftEnd"
            type="date"
            :min="movementDraftStart"
            required
        /></label>
      </div>
      <footer>
        <button type="button" @click="closeMovementCalendar">
          {{ t("stocks.calendar.cancel") }}
        </button>
        <button class="primary" type="submit" :disabled="!movementRangeValid">
          {{ t("stocks.calendar.applyFilter") }}
        </button>
      </footer>
    </form>
  </dialog>
</template>

<style scoped>
.fund-performance-panel {
  margin-top: 20px;
  padding: 24px;
  border: 1px solid var(--fz-line);
  border-radius: 22px;
  background: var(--fz-surface);
  box-shadow: var(--fz-shadow);
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
}
.fund-range-label {
  margin: 7px 0 0;
  color: var(--fz-muted);
  font-size: 11px;
}
.fund-collapsible-actions {
  display: flex;
  align-items: center;
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
  text-align: right;
}
.fund-table th:first-child {
  text-align: left;
}
.fund-table td {
  padding: 11px 10px;
  border-top: 1px solid var(--fz-line);
  text-align: right;
  vertical-align: middle;
  font-variant-numeric: tabular-nums;
}
.fund-table td:first-child {
  text-align: left;
}
.fund-table td small {
  display: block;
  margin-top: 3px;
  color: var(--fz-muted);
  font-size: 10px;
}
.operation-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 7px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--fz-accent) 12%, transparent);
  color: var(--fz-accent);
  white-space: nowrap;
}
.operation-pill.out {
  background: color-mix(in srgb, var(--fz-negative) 12%, transparent);
  color: var(--fz-negative);
}
.operation-pill small {
  display: inline;
  margin-left: 0;
}
.movement-row-actions {
  display: flex;
  justify-content: flex-end;
  gap: 5px;
}
.movement-row-actions button {
  padding: 5px 7px;
  border: 1px solid var(--fz-line);
  border-radius: 7px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 10px;
}
.delete-order {
  color: var(--fz-negative) !important;
}
.movement-pagination {
  display: flex;
  justify-content: space-between;
  margin-top: 15px;
  color: var(--fz-muted);
  font-size: 11px;
}
.movement-pagination button {
  padding: 7px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
}
.fund-empty-compact {
  min-height: 180px;
  display: grid;
  place-content: center;
  gap: 5px;
  text-align: center;
  color: var(--fz-muted);
  font-size: 11px;
}
.stock-movement-dialog {
  width: min(540px, calc(100vw - 32px));
  padding: 0;
  border: 1px solid var(--fz-line);
  border-radius: 20px;
  background: var(--fz-surface);
  color: var(--fz-ink);
}
.stock-movement-dialog form {
  padding: 23px;
}
.stock-movement-dialog header {
  display: flex;
  justify-content: space-between;
}
.stock-movement-dialog h2 {
  margin: 0;
}
.stock-calendar-fields {
  margin-top: 20px;
  padding: 18px;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  background: var(--fz-surface-soft);
  border-radius: 14px;
}
.stock-calendar-fields label {
  display: grid;
  gap: 7px;
}
.stock-calendar-fields span {
  color: var(--fz-muted);
  font-size: 10px;
}
.stock-calendar-fields input {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface);
  color: var(--fz-ink);
}
.stock-movement-dialog footer {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
}
.stock-movement-dialog footer button {
  padding: 9px 13px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: transparent;
  color: var(--fz-muted);
}
.stock-movement-dialog footer .primary {
  background: var(--fz-accent);
  color: #fff;
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
  }
  .fund-collapsible-actions {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .movement-filters {
    flex-direction: column;
  }
  .movement-filters > * {
    width: 100%;
  }
  .stock-calendar-fields {
    grid-template-columns: 1fr;
  }
}
</style>
