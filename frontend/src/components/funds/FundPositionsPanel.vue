<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import FundPriceChart from "../../components/FundPriceChart.vue";
import type { NormalizedLineChartPoint } from "../../domain/investments/normalized";
import InvestmentAllocationStrip, {
  type InvestmentAllocationItem,
} from "../investments/InvestmentAllocationStrip.vue";
import InvestmentCollapseButton from "../investments/InvestmentCollapseButton.vue";
import type { FundOrder, FundPosition } from "../../types/api";
import type {
  FundPositionAriaSort,
  FundPositionSortKey,
  FundSortDirection,
} from "../../composables/useFundsPortfolio";
import type { PerformanceRange } from "./FundPerformancePanel.vue";

export interface FundPositionsPanelProps {
  positions: FundPosition[];
  pricedPositions: number;
  priceMessage: string;
  selectedAccountLabel: string;
  allocationItems: InvestmentAllocationItem[];
  allocationTotal: number;
  sortedPositions: FundPosition[];
  positionSortColumns: Array<{ key: FundPositionSortKey; label: string }>;
  positionSortKey: FundPositionSortKey;
  positionSortDirection: FundSortDirection;
  selectedFund: string;
  selectedFundPosition: FundPosition | null;
  selectedFundOrders: FundOrder[];
  fundChartPoints: NormalizedLineChartPoint[];
  fundChartLoading: boolean;
  fundChartError: string;
  fundChartRangeLabel: string;
  ranges: ReadonlyArray<{ key: PerformanceRange; label: string }>;
  fundRange: PerformanceRange;
  formatMoney: (value: number) => string;
  formatPercentage: (value: number) => string;
  formatQuantity: (value: number, maximumFractionDigits: number) => string;
  formatSignedMoney: (value: number) => string;
  positionIdentity: (position: FundPosition) => string;
  marketValueSegmentAria: (item: InvestmentAllocationItem) => string;
  positionAriaSort: (key: FundPositionSortKey) => FundPositionAriaSort;
  positionSortAria: (key: FundPositionSortKey, label: string) => string;
  fundDetailId: (instrumentId: string) => string;
}

const props = defineProps<FundPositionsPanelProps>();
const emit = defineEmits<{
  "toggle-fund": [instrumentId: string];
  "select-range": [range: PerformanceRange];
  "retry-chart": [];
  "edit-fund": [position: FundPosition];
  sort: [key: FundPositionSortKey];
}>();
const { t } = useI18n();
const collapsed = ref(
  localStorage.getItem("finanzr-funds-positions-collapsed") === "true",
);

function toggleCollapsed() {
  collapsed.value = !collapsed.value;
  localStorage.setItem(
    "finanzr-funds-positions-collapsed",
    String(collapsed.value),
  );
}

function toggleFund(instrumentId: string) {
  emit("toggle-fund", instrumentId);
}
</script>

<template>
  <article
    class="fund-performance-panel positions-panel"
    :class="{ collapsed }"
  >
    <header class="fund-secondary-header">
      <div>
        <p class="section-label">{{ t("funds.positions.section") }}</p>
        <h2>{{ t("funds.positions.title") }}</h2>
        <p class="fund-range-label">
          {{
            t(
              props.positions.length === 1
                ? "funds.positions.pricedOne"
                : "funds.positions.pricedMany",
              { priced: props.pricedPositions, total: props.positions.length },
            )
          }}
          ·
          {{ props.priceMessage || t("funds.positions.pricesInEuros") }}
        </p>
      </div>
      <InvestmentCollapseButton
        :collapsed="collapsed"
        controls="fund-positions-content"
        :label="
          t(
            collapsed
              ? 'funds.positions.expandAria'
              : 'funds.positions.collapseAria',
          )
        "
        @toggle="toggleCollapsed"
      />
    </header>
    <div
      v-show="!collapsed"
      id="fund-positions-content"
      class="fund-positions-content"
    >
      <InvestmentAllocationStrip
        :items="props.allocationItems"
        :total="props.allocationTotal"
        :account-label="props.selectedAccountLabel"
        :title="t('funds.positions.marketValueDistribution')"
        :bar-label="t('funds.positions.marketValueDistributionBarAria')"
        :empty-label="t('funds.positions.noMarketValueDistribution')"
        :format-value="props.formatMoney"
        :format-share="props.formatPercentage"
        :segment-aria="props.marketValueSegmentAria"
      />
      <div class="fund-table-scroll position-table-scroll">
        <table class="fund-table">
          <colgroup>
            <col class="fund-col-name" />
            <col class="fund-col-type" />
            <col class="fund-col-contributed" />
            <col class="fund-col-shares" />
            <col class="fund-col-average" />
            <col class="fund-col-current" />
            <col class="fund-col-value" />
            <col class="fund-col-pnl" />
            <col class="fund-col-return" />
            <col class="fund-col-actions" />
          </colgroup>
          <thead>
            <tr>
              <th
                v-for="column in props.positionSortColumns"
                :key="column.key"
                :aria-sort="props.positionAriaSort(column.key)"
              >
                <button
                  type="button"
                  class="fund-sort-button"
                  :data-sort-key="column.key"
                  :aria-label="props.positionSortAria(column.key, column.label)"
                  @click="emit('sort', column.key)"
                >
                  <span>{{ column.label }}</span>
                  <span
                    class="fund-sort-indicator"
                    :class="{ active: props.positionSortKey === column.key }"
                    aria-hidden="true"
                    >{{
                      props.positionSortKey === column.key
                        ? props.positionSortDirection === "asc"
                          ? "↑"
                          : "↓"
                        : ""
                    }}</span
                  >
                </button>
              </th>
              <th />
            </tr>
          </thead>
          <tbody>
            <template
              v-for="position in props.sortedPositions"
              :key="position.instrument_id"
            >
              <tr
                class="fund-position-row"
                :class="{
                  active: props.selectedFund === position.instrument_id,
                }"
                @click="toggleFund(position.instrument_id)"
              >
                <td>
                  <button
                    type="button"
                    class="fund-position-disclosure"
                    :aria-expanded="
                      props.selectedFund === position.instrument_id
                    "
                    :aria-controls="props.fundDetailId(position.instrument_id)"
                    :aria-label="
                      t(
                        props.selectedFund === position.instrument_id
                          ? 'funds.positions.collapseChartAria'
                          : 'funds.positions.expandChartAria',
                        { asset: position.name },
                      )
                    "
                    @click.stop="toggleFund(position.instrument_id)"
                    @keydown.enter.prevent.stop="
                      toggleFund(position.instrument_id)
                    "
                    @keydown.space.prevent.stop="
                      toggleFund(position.instrument_id)
                    "
                  >
                    <span class="fund-position-disclosure-copy">
                      <strong>{{ position.name }}</strong>
                      <small>{{ props.positionIdentity(position) }}</small>
                    </span>
                    <span
                      class="fund-position-disclosure-icon"
                      :class="{
                        active: props.selectedFund === position.instrument_id,
                      }"
                      aria-hidden="true"
                      >⌄</span
                    >
                  </button>
                </td>
                <td :data-label="t('funds.positions.type')">
                  {{ position.asset_class
                  }}<small>{{ position.subtype }}</small>
                </td>
                <td :data-label="t('funds.positions.contributed')">
                  {{ props.formatMoney(position.cost) }}
                </td>
                <td :data-label="t('funds.positions.shares')">
                  {{ props.formatQuantity(position.quantity, 5) }}
                </td>
                <td :data-label="t('funds.positions.averagePrice')">
                  {{ props.formatMoney(position.average_price) }}
                </td>
                <td :data-label="t('funds.positions.currentPrice')">
                  {{
                    position.current_price == null
                      ? t("funds.positions.pending")
                      : props.formatMoney(position.current_price)
                  }}
                </td>
                <td :data-label="t('funds.positions.value')">
                  {{
                    position.current_value == null
                      ? "—"
                      : props.formatMoney(position.current_value)
                  }}
                </td>
                <td
                  :data-label="'P&L'"
                  :class="{
                    positive: (position.unrealized_pnl ?? 0) >= 0,
                    negative: (position.unrealized_pnl ?? 0) < 0,
                  }"
                >
                  <strong
                    >{ position.unrealized_pnl == null ? "—" :
                    props.formatSignedMoney(position.unrealized_pnl) }}</strong
                  >
                </td>
                <td
                  :data-label="t('funds.positions.return')"
                  :class="{
                    positive: (position.return_percent ?? 0) >= 0,
                    negative: (position.return_percent ?? 0) < 0,
                  }"
                >
                  <strong
                    >{ position.return_percent == null ? "—" :
                    props.formatPercentage(position.return_percent) }}</strong
                  >
                </td>
                <td>
                  <button
                    type="button"
                    class="fund-edit-icon-button"
                    :aria-label="t('funds.positions.editAria')"
                    @click.stop="emit('edit-fund', position)"
                    @keydown.stop
                  >
                    <svg viewBox="0 0 20 20" aria-hidden="true">
                      <path d="M4 16l3.3-.7L16 6.6 13.4 4 4.7 12.7 4 16Z" />
                      <path d="m11.9 5.5 2.6 2.6" />
                    </svg>
                  </button>
                </td>
              </tr>
              <tr
                v-if="props.selectedFund === position.instrument_id"
                class="fund-inline-detail-row"
              >
                <td :colspan="props.positionSortColumns.length + 1">
                  <div
                    :id="props.fundDetailId(position.instrument_id)"
                    class="fund-inline-price-panel"
                    role="region"
                    :aria-label="
                      t('funds.positions.priceDetailAria', {
                        fund: position.name,
                      })
                    "
                  >
                    <div class="fund-inline-chart-toolbar">
                      <div class="fund-chart-legend">
                        <span
                          ><i class="line price" />{{
                            t("funds.priceChart.price")
                          }}</span
                        >
                        <span
                          ><i class="line average" />{{
                            t("funds.priceChart.averagePrice")
                          }}</span
                        >
                        <span
                          ><i class="marker buy" />{{
                            t("funds.priceChart.contributionEntry")
                          }}</span
                        >
                        <span
                          ><i class="marker sell" />{{
                            t("funds.priceChart.redemptionExit")
                          }}</span
                        >
                      </div>
                      <div class="fund-inline-range">
                        <p class="fund-range-label">
                          {{ props.fundChartRangeLabel }}
                        </p>
                        <div
                          class="fund-range-control"
                          :aria-label="t('funds.priceChart.rangeAria')"
                        >
                          <button
                            v-for="item in props.ranges"
                            :key="item.key"
                            type="button"
                            :class="{ active: props.fundRange === item.key }"
                            :aria-pressed="props.fundRange === item.key"
                            @click="emit('select-range', item.key)"
                          >
                            {{ item.label }}
                          </button>
                        </div>
                      </div>
                    </div>
                    <div v-if="props.fundChartLoading" class="fund-chart-state">
                      {{ t("funds.priceChart.loading") }}
                    </div>
                    <div
                      v-else-if="props.fundChartError"
                      class="fund-chart-state error-state"
                    >
                      <strong>{{ t("funds.priceChart.unavailable") }}</strong>
                      <p>{{ props.fundChartError }}</p>
                      <button type="button" @click="emit('retry-chart')">
                        {{ t("funds.actions.retry") }}
                      </button>
                    </div>
                    <FundPriceChart
                      v-else-if="props.fundChartPoints.length"
                      :points="props.fundChartPoints"
                      :orders="props.selectedFundOrders"
                      :average-price="
                        props.selectedFundPosition?.average_price ?? null
                      "
                    />
                    <div v-else class="fund-chart-state">
                      {{ t("funds.priceChart.noHistory") }}
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>
  </article>
</template>

<style scoped>
.fund-performance-panel {
  margin-top: 18px;
  padding: 24px;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 22px;
  background: var(--fz-surface);
  box-shadow: var(--fz-shadow);
}
.positions-panel {
  padding-bottom: 18px;
}
.positions-panel.collapsed {
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
.fund-positions-content {
  margin-top: 17px;
}
.fund-table-scroll {
  margin-top: 17px;
  overflow-x: auto;
}
.position-table-scroll {
  --fund-inline-width: 100%;
  margin-top: 0;
  overflow-x: visible;
}
.fund-table {
  width: 100%;
  min-width: 0;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 10px;
}
.fund-col-name {
  width: 21%;
}
.fund-col-type {
  width: 11%;
}
.fund-col-contributed {
  width: 10%;
}
.fund-col-shares {
  width: 9%;
}
.fund-col-average,
.fund-col-current,
.fund-col-value {
  width: 10%;
}
.fund-col-pnl {
  width: 8%;
}
.fund-col-return {
  width: 6%;
}
.fund-col-actions {
  width: 5%;
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
.fund-table td:nth-child(2) {
  text-align: left;
}
.position-table-scroll .fund-table th:first-child,
.position-table-scroll .fund-table .fund-position-row > td:first-child {
  padding-left: 12px;
}
.fund-sort-button {
  width: 100%;
  padding: 3px 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: inherit;
  line-height: inherit;
  white-space: normal;
  cursor: pointer;
}
.fund-table th:first-child .fund-sort-button,
.fund-table th:nth-child(2) .fund-sort-button {
  justify-content: flex-start;
}
.fund-sort-button:hover {
  color: var(--fz-ink);
}
.fund-sort-button:focus-visible {
  outline: 2px solid var(--fz-accent);
  outline-offset: 3px;
  border-radius: 3px;
}
.fund-sort-indicator {
  width: 7px;
  flex: 0 0 7px;
  color: transparent;
  font-size: 11px;
  line-height: 1;
  text-align: center;
}
.fund-sort-indicator.active {
  color: var(--fz-accent);
}
.fund-table td {
  min-width: 0;
  padding: 10px 5px;
  overflow: hidden;
  text-align: right;
  text-overflow: ellipsis;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  border-bottom: 1px solid var(--fz-line);
  white-space: nowrap;
}
.fund-position-row {
  cursor: pointer;
  outline: none;
  transition:
    background-color 0.14s ease,
    box-shadow 0.14s ease;
}
.fund-position-row:hover,
.fund-position-row.active {
  background: color-mix(in srgb, var(--fz-accent) 7%, transparent);
}
.fund-position-row.active {
  box-shadow: inset 3px 0 var(--fz-accent);
}
.fund-inline-detail-row td {
  position: static;
  width: var(--fund-inline-width, 100%);
  max-width: var(--fund-inline-width, 100%);
  padding: 12px 10px 16px;
  text-align: left;
  white-space: normal;
  border-bottom: 0;
  background: transparent;
}
.fund-inline-price-panel {
  position: relative;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  padding: 18px 20px 20px;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 18px;
  background: var(--fz-surface);
}
.fund-inline-chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px 18px;
  flex-wrap: wrap;
}
.fund-chart-legend {
  width: fit-content;
  max-width: 100%;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  border: 0;
  background: transparent;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 650;
}
.fund-chart-legend span {
  display: flex;
  align-items: center;
  gap: 6px;
}
.fund-chart-legend i {
  display: inline-block;
}
.fund-chart-legend .line {
  width: 18px;
  height: 2px;
  border-radius: 2px;
  background: var(--fz-accent);
}
.fund-chart-legend .average {
  background: transparent;
  border-top: 2px dashed var(--fz-chart-average);
}
.fund-chart-legend .marker {
  width: 18px;
  height: 16px;
  display: grid;
  place-items: center;
  border: 1.5px solid var(--fz-surface);
  border-radius: 5px;
  background: var(--fz-trade-buy);
  color: #fff;
  font-style: normal;
  font-weight: 780;
  line-height: 1;
  box-shadow: 0 1px 3px var(--fz-chart-tooltip-shadow);
}
.fund-chart-legend .marker::before {
  content: "+";
}
.fund-chart-legend .marker.buy {
  border-color: var(--fz-trade-buy-outline);
}
.fund-chart-legend .sell {
  border-color: var(--fz-trade-sell-outline);
  background: var(--fz-trade-sell);
}
.fund-chart-legend .sell::before {
  content: "−";
}
.fund-inline-range {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-left: auto;
}
.fund-inline-range .fund-range-label {
  margin: 0;
  white-space: nowrap;
}
.fund-range-control {
  display: flex;
  padding: 4px;
  border-radius: 12px;
  background: var(--fz-surface-soft);
}
.fund-range-control button {
  padding: 7px 10px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 720;
  white-space: nowrap;
  cursor: pointer;
}
.fund-range-control button.active {
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
}
.fund-inline-price-panel .fund-range-control {
  max-width: 100%;
  flex-wrap: wrap;
}
.fund-inline-price-panel .fund-chart-state {
  min-height: 250px;
  margin-top: 14px;
  border: 0;
  background: transparent;
}
.fund-inline-price-panel :deep(.fund-price-chart) {
  height: 325px;
  margin-top: 14px;
}
.fund-chart-state {
  min-height: 330px;
  display: grid;
  place-content: center;
  text-align: center;
  color: var(--fz-muted);
  font-size: 11px;
}
.fund-chart-state strong {
  color: var(--fz-ink);
  font-size: 13px;
}
.fund-chart-state p {
  margin: 5px 0 12px;
}
.fund-chart-state button {
  justify-self: center;
  padding: 8px 11px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
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
.fund-table td .fund-edit-icon-button {
  width: 30px;
  height: 30px;
  padding: 0;
  display: inline-grid;
  place-items: center;
  border-radius: 9px;
  background: color-mix(in srgb, var(--fz-surface-soft) 72%, transparent);
}
.fund-edit-icon-button svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.fund-table td .fund-edit-icon-button:hover {
  background: color-mix(in srgb, var(--fz-accent) 9%, var(--fz-surface));
  color: var(--fz-accent);
}
.fund-edit-icon-button:focus-visible {
  outline: 2px solid var(--fz-accent);
  outline-offset: 2px;
}
.fund-table td .fund-position-disclosure {
  width: 100%;
  min-width: 0;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--fz-ink);
  font: inherit;
  text-align: left;
}
.fund-position-disclosure:focus-visible {
  outline: 2px solid var(--fz-accent);
  outline-offset: 3px;
}
.fund-position-disclosure-copy {
  min-width: 0;
}
.fund-position-disclosure-copy strong,
.fund-position-disclosure-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fund-position-disclosure-icon {
  flex: 0 0 auto;
  color: var(--fz-muted);
  font-size: 15px;
  line-height: 1;
  transform: translateY(-2px);
  transition:
    color 0.14s ease,
    transform 0.14s ease;
}
.fund-position-disclosure:hover .fund-position-disclosure-icon,
.fund-position-disclosure-icon.active {
  color: var(--fz-accent);
}
.fund-position-disclosure-icon.active {
  transform: rotate(180deg) translateY(2px);
}
@media (max-width: 1050px) {
  .fund-secondary-header {
    align-items: stretch;
  }
}
@media (max-width: 720px) {
  .fund-performance-panel {
    padding: 19px 17px;
    border-radius: 18px;
  }
  .position-table-scroll {
    --fund-inline-width: 100%;
  }
  .position-table-scroll .fund-table,
  .position-table-scroll .fund-table tbody {
    display: block;
  }
  .position-table-scroll .fund-table colgroup,
  .position-table-scroll .fund-table thead {
    display: none;
  }
  .position-table-scroll .fund-table tbody {
    display: grid;
    gap: 10px;
  }
  .position-table-scroll .fund-position-row {
    position: relative;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 3px 12px;
    padding: 11px 10px;
    border: 1px solid var(--fz-line);
    border-radius: 14px;
    background: color-mix(in srgb, var(--fz-surface-soft) 42%, transparent);
  }
  .position-table-scroll .fund-position-row.active {
    border-color: color-mix(in srgb, var(--fz-accent) 32%, var(--fz-line));
    box-shadow: inset 3px 0 var(--fz-accent);
  }
  .position-table-scroll .fund-table .fund-position-row > td {
    min-width: 0;
    padding: 7px 6px;
    display: grid;
    gap: 3px;
    border: 0;
    text-align: left;
    white-space: normal;
  }
  .position-table-scroll .fund-table .fund-position-row > td:first-child {
    grid-column: 1 / -1;
    padding-left: 12px;
    padding-right: 40px;
  }
  .position-table-scroll
    .fund-table
    .fund-position-row
    > td:not(:first-child):not(:last-child)::before {
    content: attr(data-label);
    color: var(--fz-muted);
    font-size: 10px;
    font-weight: 680;
  }
  .position-table-scroll .fund-table .fund-position-row > td:last-child {
    position: absolute;
    top: 10px;
    right: 10px;
    padding: 0;
  }
  .position-table-scroll .fund-inline-detail-row {
    display: block;
  }
  .position-table-scroll .fund-table .fund-inline-detail-row td {
    width: 100%;
    display: block;
    padding: 0;
    overflow: visible;
    border: 0;
  }
  .fund-inline-price-panel {
    padding: 16px 14px 15px;
    border-radius: 16px;
  }
  .fund-inline-chart-toolbar {
    align-items: stretch;
  }
  .fund-inline-range {
    width: 100%;
    justify-content: space-between;
    margin-left: 0;
  }
  .fund-inline-range .fund-range-control {
    overflow: visible;
    flex-wrap: wrap;
  }
}
@media (prefers-reduced-motion: reduce) {
  .fund-position-row,
  .fund-position-disclosure-icon {
    transition: none;
  }
}
</style>
