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
import type {
  CryptoPositionSortKey,
  CryptoSortDirection,
} from "../../composables/useCryptoPortfolio";
import type { CryptoPosition } from "../../types/api";

export type CryptoPerformanceRange = "6m" | "1y" | "2y" | "custom";

export interface CryptoPositionsPanelProps {
  positions: CryptoPosition[];
  pricedPositions: number;
  selectedAccountLabel: string;
  baseCurrency: string;
  allocationItems: InvestmentAllocationItem[];
  allocationTotal: number;
  sortedPositions: CryptoPosition[];
  positionSortColumns: Array<{
    key: CryptoPositionSortKey;
    label: string;
  }>;
  positionSortKey: CryptoPositionSortKey;
  positionSortDirection: CryptoSortDirection;
  selectedInstrumentId: string;
  selectedChartOrders: ChartOperation[];
  averagePrice: number | null;
  chartPoints: NormalizedCandlestickChartPoint[];
  chartLoading: boolean;
  chartError: string;
  chartRangeLabel: string;
  ranges: ReadonlyArray<{
    key: CryptoPerformanceRange;
    label: string;
  }>;
  chartRange: CryptoPerformanceRange;
  formatMoney: (value: number) => string;
  formatPercentage: (value: number) => string;
  formatQuantity: (value: number) => string;
  formatSignedMoney: (value: number) => string;
  positionIdentity: (position: CryptoPosition) => string;
  assetTicker: (position: CryptoPosition) => string;
  marketValueSegmentAria: (item: InvestmentAllocationItem) => string;
  positionAriaSort: (
    key: CryptoPositionSortKey,
  ) => "none" | "ascending" | "descending";
  positionSortAria: (key: CryptoPositionSortKey, label: string) => string;
  detailId: (instrumentId: string) => string;
}

const props = defineProps<CryptoPositionsPanelProps>();
const emit = defineEmits<{
  "toggle-position": [instrumentId: string];
  "select-chart-range": [range: CryptoPerformanceRange];
  "retry-chart": [];
  "edit-position": [position: CryptoPosition];
  "add-asset": [];
  sort: [key: CryptoPositionSortKey];
}>();
const { t } = useI18n();

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
  readStorageItem("finanzr-crypto-positions-collapsed") === "true",
);

function toggleCollapsed() {
  collapsed.value = !collapsed.value;
  writeStorageItem(
    "finanzr-crypto-positions-collapsed",
    String(collapsed.value),
  );
}

function togglePosition(instrumentId: string) {
  emit("toggle-position", instrumentId);
}
</script>

<template>
  <article
    class="fund-performance-panel positions-panel crypto-positions-panel"
    :class="{ collapsed }"
  >
    <header class="fund-secondary-header">
      <div>
        <p class="section-label">{{ t("crypto.positions.section") }}</p>
        <h2>{{ t("crypto.positions.title") }}</h2>
        <p class="fund-range-label">
          {{
            t(
              props.positions.length === 1
                ? "crypto.positions.pricedOne"
                : "crypto.positions.pricedMany",
              { priced: props.pricedPositions, total: props.positions.length },
            )
          }}
          ·
          {{
            t("crypto.positions.pricesInCurrency", {
              currency: props.baseCurrency,
            })
          }}
        </p>
      </div>
      <div class="fund-collapsible-actions">
        <InvestmentAddAssetButton
          :label="t('crypto.assets.add')"
          @add="emit('add-asset')"
        />
        <InvestmentCollapseButton
          :collapsed="collapsed"
          controls="crypto-positions-content"
          :label="
            t(
              collapsed
                ? 'crypto.positions.expandAria'
                : 'crypto.positions.collapseAria',
            )
          "
          @toggle="toggleCollapsed"
        />
      </div>
    </header>
    <div
      v-show="!collapsed"
      id="crypto-positions-content"
      class="fund-positions-content"
    >
      <InvestmentAllocationStrip
        :items="props.allocationItems"
        :total="props.allocationTotal"
        :account-label="props.selectedAccountLabel"
        :title="t('crypto.positions.marketValueDistribution')"
        :bar-label="t('crypto.positions.marketValueDistributionBarAria')"
        :empty-label="t('crypto.positions.noMarketValueDistribution')"
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
                          ? 'crypto.positions.collapseChartAria'
                          : 'crypto.positions.expandChartAria',
                        { asset: position.name },
                      )
                    "
                    @click.stop="togglePosition(position.instrument_id)"
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
                      ? t("crypto.positions.pending")
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
                  <strong>{{
                    position.unrealized_pnl == null
                      ? "—"
                      : props.formatSignedMoney(position.unrealized_pnl)
                  }}</strong>
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
                    :aria-label="t('crypto.positions.editAria')"
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
                      t('crypto.positions.priceDetailAria', {
                        asset: position.name,
                      })
                    "
                  >
                    <div class="fund-inline-chart-toolbar">
                      <div class="fund-chart-legend">
                        <span
                          >▌ {{ t("crypto.chart.bullishCandle") }} /
                          {{ t("crypto.chart.bearishCandle") }}</span
                        ><span>╍ {{ t("crypto.chart.averagePrice") }}</span
                        ><span>+ {{ t("crypto.movements.buy") }}</span
                        ><span>− {{ t("crypto.movements.sell") }}</span>
                      </div>
                      <div class="fund-inline-range">
                        <p class="fund-range-label">
                          {{ props.chartRangeLabel }}
                        </p>
                        <div
                          class="fund-range-control"
                          :aria-label="t('crypto.chart.rangeAria')"
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
                    <div v-if="props.chartLoading" class="fund-chart-state">
                      {{ t("crypto.chart.loading") }}
                    </div>
                    <div
                      v-else-if="props.chartError"
                      class="fund-chart-state error-state"
                    >
                      <strong>{{ t("crypto.chart.unavailable") }}</strong>
                      <p>{{ props.chartError }}</p>
                      <button type="button" @click="emit('retry-chart')">
                        {{ t("crypto.actions.retry") }}
                      </button>
                    </div>
                    <CryptoCandlestickChart
                      v-else-if="props.chartPoints.length"
                      :points="props.chartPoints"
                      :operations="props.selectedChartOrders"
                      :average-price="props.averagePrice"
                      operation-marker-shape="pin"
                    />
                    <div v-else class="fund-chart-state">
                      {{ t("crypto.chart.noData") }}
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
      <div v-if="!props.sortedPositions.length" class="fund-empty-compact">
        {{ t("crypto.assets.noOpenPositionsHint") }}
      </div>
    </div>
  </article>
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
.fund-sort-button {
  width: 100%;
  padding: 3px 0;
  display: flex;
  justify-content: flex-end;
  gap: 3px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}
.fund-table th:first-child .fund-sort-button,
.fund-table th:nth-child(2) .fund-sort-button {
  justify-content: flex-start;
}
.fund-sort-button:focus-visible {
  outline: 2px solid var(--fz-accent);
  outline-offset: 2px;
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
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--fz-ink);
  text-align: left;
  cursor: pointer;
}
.fund-position-disclosure-copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}
.fund-position-disclosure-copy strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fund-position-disclosure-copy small,
.fund-table td small {
  display: block;
  color: var(--fz-muted);
  font-size: 9px;
}
.fund-edit-icon-button {
  border: 0;
  background: transparent;
  color: var(--fz-muted);
  cursor: pointer;
}
.fund-edit-icon-button:hover {
  color: var(--fz-accent);
}
.fund-inline-detail-row td {
  padding: 12px 10px 16px;
  text-align: left;
  white-space: normal;
  border-bottom: 0;
}
.fund-inline-price-panel {
  padding: 17px 19px 19px;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 17px;
  background: var(--fz-surface);
}
.fund-inline-chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.fund-inline-range {
  display: grid;
  justify-items: end;
  gap: 7px;
}
.fund-inline-range .fund-range-label {
  margin: 0;
}
.fund-chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-chart-state,
.fund-empty-compact {
  min-height: 180px;
  display: grid;
  place-content: center;
  gap: 5px;
  color: var(--fz-muted);
  font-size: 10px;
  text-align: center;
}
.fund-chart-state strong {
  color: var(--fz-ink);
  font-size: 12px;
}
.fund-chart-state p {
  margin: 0;
}
.fund-chart-state button {
  width: fit-content;
  margin: 4px auto 0;
  padding: 7px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.positive {
  color: var(--fz-positive);
}
.negative {
  color: var(--fz-negative);
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
}
@media (max-width: 720px) {
  .fund-performance-panel {
    padding: 19px 17px;
    border-radius: 18px;
  }
  .fund-inline-range {
    justify-items: start;
  }
  .fund-collapsible-actions {
    width: 100%;
    flex-wrap: wrap;
  }
  .fund-inline-range .fund-range-control {
    width: 100%;
  }
}
</style>
