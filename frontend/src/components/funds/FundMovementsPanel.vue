<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import InvestmentCollapseButton from "../investments/InvestmentCollapseButton.vue";
import InvestmentMovementActions from "../investments/InvestmentMovementActions.vue";
import type { FundOrder, FundPosition } from "../../types/api";

export interface FundMovementsPanelProps {
  orders: FundOrder[];
  positions: FundPosition[];
  selectedAccountLabel: string;
  accountKey: string;
  formatMoney: (value: number) => string;
  formatQuantity: (value: number, maximumFractionDigits: number) => string;
  displayDate: (value: string) => string;
  positionIdentity: (position: FundPosition) => string;
}

const props = defineProps<FundMovementsPanelProps>();
const emit = defineEmits<{
  add: [];
  edit: [order: FundOrder];
  delete: [order: FundOrder];
}>();
const { t, n, locale } = useI18n();

const movementFund = ref("all");
const movementType = ref("all");
const movementStart = ref("");
const movementEnd = ref("");
const movementPage = ref(1);
const movementDraftStart = ref("");
const movementDraftEnd = ref("");
const collapsed = ref(
  localStorage.getItem("finanzr-funds-movements-collapsed") === "true",
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
      (item) =>
        movementFund.value === "all" || item.isin === movementFund.value,
    )
    .filter(
      (item) =>
        movementType.value === "all" ||
        operationGroup(item) === movementType.value,
    )
    .filter(
      (item) => !movementStart.value || item.trade_date >= movementStart.value,
    )
    .filter(
      (item) => !movementEnd.value || item.trade_date <= movementEnd.value,
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
    ? `${props.displayDate(movementStart.value)} → ${props.displayDate(movementEnd.value)}`
    : t("funds.movements.allHistory"),
);

watch([movementFund, movementType, movementStart, movementEnd], () => {
  movementPage.value = 1;
});
watch(
  () => props.accountKey,
  () => {
    movementStart.value = "";
    movementEnd.value = "";
    movementPage.value = 1;
  },
);
watch(
  () => props.orders,
  (orders) => {
    if (!movementStart.value && orders.length) {
      const dates = orders.map((item) => item.trade_date).sort();
      movementStart.value = dates[0];
      movementEnd.value = dates.at(-1) ?? dates[0];
    }
  },
  { immediate: true },
);

function toggleCollapsed() {
  collapsed.value = !collapsed.value;
  localStorage.setItem(
    "finanzr-funds-movements-collapsed",
    String(collapsed.value),
  );
}

function operationGroup(item: FundOrder) {
  return ["buy", "transfer_in"].includes(item.operation_type) ? "in" : "out";
}

function operationLabel(item: FundOrder) {
  const operation = item.provider_operation_type || item.operation_type;
  return (
    {
      buy: t("funds.movements.contribution"),
      SUSCRIPCION: t("funds.movements.contribution"),
      transfer_in: t("funds.movements.transferIn"),
      "SUSCR.POR TRASPASO I": t("funds.movements.transferIn"),
      transfer_out: t("funds.movements.transferOut"),
      "REEMB.POR TRASPASO I": t("funds.movements.transferOut"),
      sell: t("funds.movements.redemption"),
      REEMBOLSO: t("funds.movements.redemption"),
      Compra: t("funds.movements.contribution"),
      Venta: t("funds.movements.redemption"),
    }[operation] ?? operation
  );
}

function originalMoney(value: number, currency?: string) {
  return n(value, {
    style: "currency",
    currency: currency || "EUR",
    maximumFractionDigits: 2,
  });
}

function baseUnitPrice(item: FundOrder) {
  return item.base_unit_price ?? item.unit_price;
}

function baseAmount(item: FundOrder) {
  return item.base_net_amount ?? item.net_amount;
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
  <div class="fund-performance-panel movement-panel-host">
    <article
      class="fund-performance-panel movements-panel"
      :class="{ collapsed }"
    >
      <header class="fund-secondary-header">
        <div>
          <p class="section-label">{{ t("funds.movements.section") }}</p>
          <h2>{{ t("funds.movements.title") }}</h2>
          <p class="fund-range-label">
            {{
              t(
                filteredOrders.length === 1
                  ? "funds.movements.operation"
                  : "funds.movements.operations",
                { count: filteredOrders.length },
              )
            }}
            · {{ movementRangeLabel }}
          </p>
        </div>
        <div class="fund-collapsible-actions">
          <div v-show="!collapsed" class="movement-filters">
            <button type="button" class="add-movement" @click="emit('add')">
              <span aria-hidden="true">+</span> {{ t("funds.movements.add") }}
            </button>
            <select
              v-model="movementFund"
              :aria-label="t('funds.movements.filterFundAria')"
            >
              <option value="all">{{ t("funds.movements.allFunds") }}</option>
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
              :aria-label="t('funds.movements.filterTypeAria')"
            >
              <option value="all">
                {{ t("funds.movements.allMovements") }}
              </option>
              <option value="in">{{ t("funds.movements.entries") }}</option>
              <option value="out">{{ t("funds.movements.exits") }}</option>
            </select>
            <button type="button" @click="openMovementCalendar">
              {{ movementRangeLabel }}
            </button>
          </div>
          <InvestmentCollapseButton
            :collapsed="collapsed"
            controls="fund-movements-content"
            :label="
              t(
                collapsed
                  ? 'funds.movements.expandAria'
                  : 'funds.movements.collapseAria',
              )
            "
            @toggle="toggleCollapsed"
          />
        </div>
      </header>
      <div v-show="!collapsed" id="fund-movements-content">
        <div class="fund-table-scroll">
          <table class="fund-table movement-table">
            <thead>
              <tr>
                <th>{{ t("funds.movements.date") }}</th>
                <th>{{ t("funds.movements.movement") }}</th>
                <th>{{ t("funds.movements.fund") }}</th>
                <th>{{ t("funds.movements.account") }}</th>
                <th>{{ t("funds.movements.shares") }}</th>
                <th>{{ t("funds.movements.price") }}</th>
                <th>{{ t("funds.movements.amount") }}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              <tr v-for="order in displayedOrders" :key="order.id">
                <td>{{ props.displayDate(order.trade_date) }}</td>
                <td>
                  <span class="operation-pill" :class="operationGroup(order)">
                    {{ operationLabel(order) }}
                  </span>
                </td>
                <td>
                  <strong>{{ order.asset_name }}</strong>
                  <small>{{ order.isin }}</small>
                </td>
                <td>
                  {{ order.account_name ?? props.selectedAccountLabel }}
                  <small>{{ order.platform }}</small>
                </td>
                <td>{{ props.formatQuantity(order.quantity, 6) }}</td>
                <td>
                  {{ props.formatMoney(baseUnitPrice(order)) }}
                  <small v-if="order.currency && order.currency !== 'EUR'">
                    {{ originalMoney(order.unit_price, order.currency) }}
                  </small>
                </td>
                <td>
                  <strong>{{ props.formatMoney(baseAmount(order)) }}</strong>
                  <small v-if="order.currency && order.currency !== 'EUR'">
                    {{ originalMoney(order.net_amount, order.currency) }}
                  </small>
                </td>
                <td>
                  <InvestmentMovementActions
                    :edit-label="t('funds.movements.edit')"
                    :delete-label="t('funds.movements.delete')"
                    @edit="emit('edit', order)"
                    @delete="emit('delete', order)"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!filteredOrders.length" class="fund-empty-compact">
          {{ t("funds.movements.noResults") }}
        </div>
        <nav
          v-else-if="movementPages > 1"
          class="movement-pagination"
          :aria-label="t('funds.movements.paginationAria')"
        >
          <span>{{
            t("funds.movements.page", {
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
              {{ t("funds.movements.previous") }}
            </button>
            <button
              type="button"
              :disabled="movementPage === movementPages"
              @click="movementPage++"
            >
              {{ t("funds.movements.next") }}
            </button>
          </div>
        </nav>
      </div>
    </article>

    <dialog
      ref="movementCalendarDialog"
      class="fund-dialog"
      aria-labelledby="movement-calendar-title"
      @cancel.prevent="closeMovementCalendar"
    >
      <form @submit.prevent="applyMovementRange">
        <header>
          <div>
            <p class="section-label">
              {{ t("funds.movements.filterSection") }}
            </p>
            <h2 id="movement-calendar-title">
              {{ t("funds.calendar.selectDates") }}
            </h2>
          </div>
        </header>
        <div class="movement-calendar-fields">
          <label
            ><span>{{ t("funds.calendar.from") }}</span
            ><input
              v-model="movementDraftStart"
              type="date"
              :max="movementDraftEnd"
              required
          /></label>
          <span aria-hidden="true">→</span>
          <label
            ><span>{{ t("funds.calendar.to") }}</span
            ><input
              v-model="movementDraftEnd"
              type="date"
              :min="movementDraftStart"
              required
          /></label>
        </div>
        <footer>
          <button type="button" @click="closeMovementCalendar">
            {{ t("funds.actions.cancel") }}
          </button>
          <button class="primary" type="submit" :disabled="!movementRangeValid">
            {{ t("funds.calendar.applyFilter") }}
          </button>
        </footer>
      </form>
    </dialog>
  </div>
</template>

<style scoped>
.movement-panel-host {
  display: contents;
}
.fund-performance-panel {
  margin-top: 18px;
  padding: 24px;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 22px;
  background: var(--fz-surface);
  box-shadow: var(--fz-shadow);
}
.movements-panel {
  padding-bottom: 18px;
}
.movements-panel.collapsed {
  padding-bottom: 24px;
}
.fund-secondary-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.fund-secondary-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 750;
  letter-spacing: -0.03em;
}
.section-label {
  font-size: 10px;
}
.fund-range-label {
  margin: 7px 0 0;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
.fund-collapsible-actions {
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  gap: 10px;
}
.movement-filters {
  display: flex;
  align-items: center;
  gap: 8px;
}
.movement-filters select,
.movement-filters button {
  min-height: 36px;
  padding: 8px 28px 8px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  font-size: 11px;
  font-weight: 680;
}
.movement-filters button {
  padding-right: 10px;
  cursor: pointer;
}
.movement-filters .add-movement {
  border-color: var(--fz-accent);
  background: var(--fz-accent);
  color: #f4fff9;
}
.movement-filters .add-movement span {
  margin-right: 3px;
  font-size: 12px;
}
.fund-table-scroll {
  margin-top: 17px;
  overflow-x: auto;
}
.fund-table {
  width: 100%;
  min-width: 0;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 10px;
}
.fund-table th {
  padding: 8px 5px;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 700;
  text-align: right;
  line-height: 1.2;
  white-space: normal;
  border-bottom: 1px solid var(--fz-line);
}
.fund-table th:first-child,
.fund-table th:nth-child(2),
.fund-table td:first-child,
.fund-table td:nth-child(2),
.movement-table th:nth-child(3),
.movement-table th:nth-child(4),
.movement-table td:nth-child(3),
.movement-table td:nth-child(4) {
  text-align: left;
}
.fund-table td {
  min-width: 0;
  padding: 14px 5px;
  overflow: hidden;
  text-align: right;
  text-overflow: ellipsis;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  border-bottom: 1px solid var(--fz-line);
  white-space: nowrap;
}
.fund-table tbody tr:last-child td {
  border-bottom: 0;
}
.fund-table td strong,
.fund-table td small {
  display: block;
}
.fund-table td small {
  margin-top: 3px;
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-table td button {
  padding: 6px 8px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 11px;
  cursor: pointer;
}
.fund-table td button:hover {
  border-color: var(--fz-accent);
  color: var(--fz-ink);
}
.operation-pill {
  display: inline-flex;
  padding: 5px 7px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 730;
}
.operation-pill.in {
  background: color-mix(in srgb, var(--fz-accent) 13%, transparent);
  color: var(--fz-accent);
}
.operation-pill.out {
  background: color-mix(in srgb, var(--fz-negative) 10%, transparent);
  color: var(--fz-negative);
}
.movement-row-actions {
  display: inline-flex;
  gap: 5px;
}
.movement-pagination {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 680;
}
.movement-pagination div {
  display: flex;
  gap: 7px;
}
.movement-pagination button {
  padding: 7px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}
.movement-pagination button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.fund-empty-compact {
  min-height: 180px;
  display: grid;
  place-items: center;
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-dialog {
  width: min(520px, calc(100vw - 32px));
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 20px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 28px 90px rgba(0, 0, 0, 0.34);
}
.fund-dialog::backdrop {
  background: rgba(6, 11, 8, 0.68);
  backdrop-filter: blur(5px);
}
.fund-dialog form {
  padding: 23px;
}
.fund-dialog header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.fund-dialog h2 {
  margin: 0;
  font-size: 18px;
}
.movement-calendar-fields {
  margin-top: 23px;
  padding: 18px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: end;
  gap: 12px;
  border-radius: 14px;
  background: var(--fz-surface-soft);
}
.movement-calendar-fields label {
  display: grid;
  gap: 7px;
}
.movement-calendar-fields label span {
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 690;
}
.movement-calendar-fields > span {
  padding-bottom: 9px;
  color: var(--fz-muted);
}
.movement-calendar-fields input {
  min-width: 0;
  width: 100%;
  padding: 10px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font-size: 12px;
}
.fund-dialog footer {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
}
.fund-dialog footer button {
  padding: 9px 13px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 12px;
  font-weight: 710;
  cursor: pointer;
}
.fund-dialog footer .primary {
  border-color: var(--fz-accent);
  background: var(--fz-accent);
  color: #f4fff9;
}
.fund-dialog footer button:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}
@media (max-width: 1050px) {
  .fund-secondary-header {
    align-items: stretch;
  }
  .movements-panel .fund-secondary-header {
    flex-direction: column;
  }
  .fund-collapsible-actions {
    width: 100%;
  }
  .fund-collapsible-actions .movement-filters {
    flex: 1;
  }
}
@media (max-width: 720px) {
  .fund-performance-panel {
    padding: 19px 17px;
    border-radius: 18px;
  }
  .movement-filters {
    align-items: stretch;
    flex-direction: column;
  }
  .fund-collapsible-actions {
    align-items: flex-start;
  }
  .movement-filters select,
  .movement-filters button {
    width: 100%;
    max-width: none;
  }
  .movement-calendar-fields {
    grid-template-columns: minmax(0, 1fr);
  }
  .movement-calendar-fields > span {
    display: none;
  }
}
</style>
