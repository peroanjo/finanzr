<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import CryptoCandlestickChart from "../CryptoCandlestickChart.vue";
import InvestmentAllocationStrip, {
  type InvestmentAllocationItem,
} from "../investments/InvestmentAllocationStrip.vue";
import InvestmentAddAssetButton from "../investments/InvestmentAddAssetButton.vue";
import InvestmentCollapseButton from "../investments/InvestmentCollapseButton.vue";
import type { ChartOperation } from "../../domain/chartOperations";
import type { NormalizedCandlestickChartPoint } from "../../domain/investments";
import type { CandleIntervalSelection } from "../../domain/investments/marketChartInterval";
import type {
  StockPositionSortKey,
  StockSortDirection,
} from "../../composables/useStocksPortfolio";
import type { StockPosition as StockPositionData } from "../../types/api";

export type StockPerformanceRange = "6m" | "1y" | "2y" | "custom";

export interface StockPositionsPanelProps {
  positions: StockPositionData[];
  pricedPositions: number;
  selectedAccountLabel: string;
  baseCurrency: string;
  allocationItems: InvestmentAllocationItem[];
  allocationTotal: number;
  sortedPositions: StockPositionData[];
  positionSortColumns: Array<{
    key: StockPositionSortKey;
    label: string;
  }>;
  positionSortKey: StockPositionSortKey;
  positionSortDirection: StockSortDirection;
  selectedInstrumentId: string;
  selectedChartOrders: ChartOperation[];
  averagePrice: number | null;
  chartPoints: NormalizedCandlestickChartPoint[];
  chartLoading: boolean;
  chartError: string;
  chartRangeLabel: string;
  ranges: ReadonlyArray<{
    key: StockPerformanceRange;
    label: string;
  }>;
  chartRange: StockPerformanceRange;
  candleInterval: CandleIntervalSelection;
  candleIntervals: ReadonlyArray<{
    key: CandleIntervalSelection;
    label: string;
    disabled?: boolean;
  }>;
  formatMoney: (value: number) => string;
  formatPercentage: (value: number) => string;
  formatQuantity: (value: number) => string;
  formatSignedMoney: (value: number) => string;
  positionIdentity: (position: StockPositionData) => string;
  assetTicker: (position: StockPositionData) => string;
  marketValueSegmentAria: (item: InvestmentAllocationItem) => string;
  positionAriaSort: (
    key: StockPositionSortKey,
  ) => "none" | "ascending" | "descending";
  positionSortAria: (key: StockPositionSortKey, label: string) => string;
  detailId: (instrumentId: string) => string;
}

const props = defineProps<StockPositionsPanelProps>();
const emit = defineEmits<{
  "toggle-position": [instrumentId: string];
  "select-chart-range": [range: StockPerformanceRange];
  "select-candle-interval": [interval: CandleIntervalSelection];
  "retry-chart": [];
  "edit-position": [position: StockPositionData];
  "add-asset": [];
  sort: [key: StockPositionSortKey];
}>();
const { t } = useI18n();
const collapsed = ref(
  localStorage.getItem("finanzr-stocks-positions-collapsed") === "true",
);

function toggleCollapsed() {
  collapsed.value = !collapsed.value;
  localStorage.setItem(
    "finanzr-stocks-positions-collapsed",
    String(collapsed.value),
  );
}

function togglePosition(instrumentId: string) {
  emit("toggle-position", instrumentId);
}

function selectCandleInterval(event: Event) {
  emit(
    "select-candle-interval",
    (event.target as HTMLSelectElement).value as CandleIntervalSelection,
  );
}
</script>

<template>
  <article
    class="fund-performance-panel positions-panel"
    :class="{ collapsed }"
  >
    <header class="fund-secondary-header">
      <div>
        <p class="section-label">{{ t("stocks.positions.section") }}</p>
        <h2>{{ t("stocks.positions.title") }}</h2>
        <p class="fund-range-label">
          {{
            t(
              props.positions.length === 1
                ? "stocks.positions.pricedOne"
                : "stocks.positions.pricedMany",
              { priced: props.pricedPositions, total: props.positions.length },
            )
          }}
          ·
          {{
            t("stocks.positions.pricesInCurrency", {
              currency: props.baseCurrency,
            })
          }}
        </p>
      </div>
      <div class="stock-secondary-actions">
        <InvestmentAddAssetButton
          class="stock-add-asset-button"
          :label="t('stocks.assets.add')"
          @add="emit('add-asset')"
        />
        <InvestmentCollapseButton
          :collapsed="collapsed"
          controls="stock-positions-content"
          :label="
            t(
              collapsed
                ? 'stocks.positions.expandAria'
                : 'stocks.positions.collapseAria',
            )
          "
          @toggle="toggleCollapsed"
        />
      </div>
    </header>
    <div
      v-show="!collapsed"
      id="stock-positions-content"
      class="fund-positions-content"
    >
      <InvestmentAllocationStrip
        :items="props.allocationItems"
        :total="props.allocationTotal"
        :account-label="props.selectedAccountLabel"
        :title="t('stocks.positions.marketValueDistribution')"
        :bar-label="t('stocks.positions.marketValueDistributionBarAria')"
        :empty-label="t('stocks.positions.noMarketValueDistribution')"
        :format-value="props.formatMoney"
        :format-share="props.formatPercentage"
        :segment-aria="props.marketValueSegmentAria"
      />
      <div class="fund-table-scroll position-table-scroll">
        <table class="fund-table position-table">
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
                  :aria-label="props.positionSortAria(column.key, column.label)"
                  @click="emit('sort', column.key)"
                >
                  {{ column.label }}
                  <span>{{
                    props.positionSortKey === column.key
                      ? props.positionSortDirection === "asc"
                        ? "↑"
                        : "↓"
                      : ""
                  }}</span>
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
                  active: props.selectedInstrumentId === position.instrument_id,
                }"
                @click="togglePosition(position.instrument_id)"
              >
                <td>
                  <button
                    type="button"
                    class="fund-position-disclosure"
                    :aria-expanded="
                      props.selectedInstrumentId === position.instrument_id
                    "
                    :aria-controls="props.detailId(position.instrument_id)"
                    :aria-label="
                      t(
                        props.selectedInstrumentId === position.instrument_id
                          ? 'stocks.positions.collapseChartAria'
                          : 'stocks.positions.expandChartAria',
                        { asset: position.name },
                      )
                    "
                    @click.stop="togglePosition(position.instrument_id)"
                    @keydown.enter.prevent.stop="
                      togglePosition(position.instrument_id)
                    "
                    @keydown.space.prevent.stop="
                      togglePosition(position.instrument_id)
                    "
                  >
                    <span class="fund-position-disclosure-copy"
                      ><strong>{{ position.name }}</strong
                      ><small>{{
                        props.positionIdentity(position)
                      }}</small></span
                    ><span aria-hidden="true">⌄</span>
                  </button>
                </td>
                <td>{{ props.assetTicker(position) }}</td>
                <td>{{ props.formatMoney(position.cost) }}</td>
                <td>{{ props.formatQuantity(position.quantity) }}</td>
                <td>
                  {{
                    props.formatMoney(
                      position.quantity ? position.cost / position.quantity : 0,
                    )
                  }}
                </td>
                <td>
                  {{
                    position.current_price == null
                      ? t("stocks.positions.pending")
                      : props.formatMoney(position.current_price)
                  }}
                </td>
                <td>
                  {{
                    position.current_value == null
                      ? "—"
                      : props.formatMoney(position.current_value)
                  }}
                </td>
                <td
                  :class="{
                    positive: (position.unrealized_pnl ?? 0) >= 0,
                    negative: (position.unrealized_pnl ?? 0) < 0,
                  }"
                >
                  <strong>
                    {{
                      position.unrealized_pnl == null
                        ? "—"
                        : props.formatSignedMoney(position.unrealized_pnl)
                    }}
                  </strong>
                </td>
                <td
                  :class="{
                    positive:
                      position.cost === 0 ||
                      (position.unrealized_pnl ?? 0) / position.cost >= 0,
                    negative:
                      position.cost !== 0 &&
                      (position.unrealized_pnl ?? 0) / position.cost < 0,
                  }"
                >
                  <strong>{{
                    props.formatPercentage(
                      position.cost
                        ? (position.unrealized_pnl ?? 0) / position.cost
                        : 0,
                    )
                  }}</strong>
                </td>
                <td>
                  <button
                    type="button"
                    class="fund-edit-icon-button"
                    :aria-label="t('stocks.positions.editAria')"
                    @click.stop="emit('edit-position', position)"
                  >
                    ✎
                  </button>
                </td>
              </tr>
              <tr
                v-if="props.selectedInstrumentId === position.instrument_id"
                class="fund-inline-detail-row"
              >
                <td :colspan="props.positionSortColumns.length + 1">
                  <div
                    :id="props.detailId(position.instrument_id)"
                    class="fund-inline-price-panel"
                    role="region"
                    :aria-label="
                      t('stocks.positions.priceDetailAria', {
                        asset: position.name,
                      })
                    "
                  >
                    <div class="fund-inline-chart-toolbar">
                      <div class="fund-chart-legend">
                        <span
                          >▌ {{ t("stocks.chart.risingCandle") }} /
                          {{ t("stocks.chart.fallingCandle") }}</span
                        ><span>╍ {{ t("stocks.chart.averagePrice") }}</span
                        ><span>+ {{ t("stocks.movements.buy") }}</span
                        ><span>− {{ t("stocks.movements.sell") }}</span>
                      </div>
                      <div class="fund-inline-range">
                        <p class="fund-range-label">
                          {{ props.chartRangeLabel }}
                        </p>
                        <div class="fund-chart-controls">
                          <label class="candle-interval-control">
                            <span>{{ t("stocks.chart.candleInterval") }}</span>
                            <select
                              :value="props.candleInterval"
                              :aria-label="t('stocks.chart.candleIntervalAria')"
                              @change="selectCandleInterval"
                            >
                              <option
                                v-for="item in props.candleIntervals"
                                :key="item.key"
                                :value="item.key"
                                :disabled="item.disabled"
                              >
                                {{ item.label }}
                              </option>
                            </select>
                          </label>
                          <div
                            class="fund-range-control"
                            :aria-label="t('stocks.chart.rangeAria')"
                          >
                            <button
                              v-for="item in props.ranges"
                              :key="item.key"
                              type="button"
                              :class="{ active: props.chartRange === item.key }"
                              :aria-pressed="props.chartRange === item.key"
                              @click="emit('select-chart-range', item.key)"
                            >
                              {{ item.label }}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div v-if="props.chartLoading" class="fund-chart-state">
                      {{ t("stocks.chart.loading") }}
                    </div>
                    <div
                      v-else-if="props.chartError"
                      class="fund-chart-state error-state"
                    >
                      <strong>{{ t("stocks.chart.unavailable") }}</strong>
                      <p>{{ props.chartError }}</p>
                      <button type="button" @click="emit('retry-chart')">
                        {{ t("stocks.retry") }}
                      </button>
                    </div>
                    <CryptoCandlestickChart
                      v-else-if="props.chartPoints.length"
                      :points="props.chartPoints"
                      :operations="props.selectedChartOrders"
                      :average-price="props.averagePrice"
                      :density-mode="
                        props.candleInterval === 'auto' ? 'auto' : 'manual'
                      "
                      operation-marker-shape="pin"
                    />
                    <div v-else class="fund-chart-state">
                      {{ t("stocks.chart.empty") }}
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
      <div v-if="!props.sortedPositions.length" class="fund-empty-compact">
        {{ t("stocks.assets.emptyDescription") }}
      </div>
    </div>
  </article>
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
.positions-panel {
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
}
.fund-range-label {
  margin: 7px 0 0;
  color: var(--fz-muted);
  font-size: 11px;
}
.stock-secondary-actions {
  display: flex;
  align-items: center;
  gap: 7px;
}
.fund-positions-content {
  margin-top: 17px;
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
.position-table-scroll .fund-table {
  margin-top: 0;
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
.fund-sort-button {
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}
.fund-position-row {
  cursor: pointer;
  transition: background 0.14s ease;
}
@media (prefers-reduced-motion: reduce) {
  .fund-position-row {
    transition: none;
  }
}
.fund-position-row:hover,
.fund-position-row.active {
  background: color-mix(in srgb, var(--fz-accent) 7%, transparent);
}
.fund-position-row.active {
  box-shadow: inset 3px 0 var(--fz-accent);
}
.fund-position-disclosure {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--fz-ink);
  text-align: left;
  cursor: pointer;
}
.fund-position-disclosure-copy {
  display: grid;
  min-width: 0;
}
.fund-position-disclosure-copy strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fund-edit-icon-button {
  border: 1px solid var(--fz-line);
  border-radius: 7px;
  background: transparent;
  color: var(--fz-muted);
  cursor: pointer;
}
.fund-inline-detail-row td {
  padding: 0;
  background: var(--fz-surface-soft);
}
.fund-inline-price-panel {
  padding: 17px;
}
.fund-inline-chart-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 15px;
  margin-bottom: 10px;
}
.fund-chart-legend {
  display: flex;
  gap: 10px;
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-inline-range {
  display: grid;
  justify-items: end;
  gap: 7px;
}
.fund-inline-range .fund-range-label {
  margin: 0;
}
.fund-chart-controls {
  display: flex;
  align-items: stretch;
  justify-content: flex-end;
  gap: 7px;
}
.candle-interval-control {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 4px 4px 4px 9px;
  border-radius: 12px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 700;
}
.candle-interval-control select {
  min-width: 84px;
  padding: 7px 25px 7px 9px;
  border: 0;
  border-radius: 9px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font: inherit;
  cursor: pointer;
}
.fund-range-control {
  display: flex;
  gap: 3px;
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
  cursor: pointer;
}
.fund-range-control button.active {
  background: var(--fz-surface);
  color: var(--fz-ink);
}
.fund-chart-state,
.fund-empty-compact {
  min-height: 180px;
  display: grid;
  place-content: center;
  gap: 5px;
  text-align: center;
  color: var(--fz-muted);
  font-size: 11px;
}
.fund-chart-state strong {
  color: var(--fz-ink);
}
.positive {
  color: var(--fz-positive);
}
.negative {
  color: var(--fz-negative);
}
@media (max-width: 1280px) {
  .fund-inline-chart-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .fund-inline-range {
    justify-items: start;
  }
  .fund-chart-controls {
    justify-content: flex-start;
  }
}
@media (max-width: 1050px) {
  .fund-secondary-header {
    align-items: stretch;
    flex-direction: column;
  }
  .fund-inline-chart-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .fund-inline-range {
    justify-items: start;
  }
  .fund-chart-controls {
    justify-content: flex-start;
  }
}
@media (max-width: 720px) {
  .fund-performance-panel {
    padding: 19px 17px;
  }
  .stock-secondary-actions {
    flex-wrap: wrap;
  }
  .fund-inline-range {
    justify-items: start;
  }
  .fund-chart-controls {
    width: 100%;
    flex-wrap: wrap;
  }
  .fund-inline-range .fund-range-control button {
    flex: 1;
  }
}
</style>
