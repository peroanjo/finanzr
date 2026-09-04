<script setup lang="ts">
import { useI18n } from "vue-i18n";
import FundPerformanceChart from "../FundPerformanceChart.vue";
import type { InvestmentPerformancePoint } from "../../types/api";

export type PerformanceRange = "6m" | "1y" | "2y" | "custom";
export type PerformanceMode = "value" | "return";

export interface FundPerformancePanelRange {
  key: PerformanceRange;
  label: string;
}

export interface FundPerformancePanelModel {
  accountLabel: string;
  displayedRange: string;
  range: PerformanceRange;
  mode: PerformanceMode;
  ranges: readonly FundPerformancePanelRange[];
  points: InvestmentPerformancePoint[];
  lastPerformance: InvestmentPerformancePoint | null;
  totalValue: number;
  totalInvested: number;
  realizedPnl: number;
  periodLabel: string;
  periodPnl: number;
  periodPnlPercent: number;
  loading: boolean;
  error: string;
  formatters: {
    money(value: number): string;
    percentage(value: number): string;
    signedMoney(value: number): string;
  };
}

defineProps<{
  model: FundPerformancePanelModel;
}>();

const emit = defineEmits<{
  "update:mode": [mode: PerformanceMode];
  "select-range": [range: PerformanceRange];
  retry: [];
}>();

const { t } = useI18n();
</script>

<template>
  <article class="fund-performance-panel">
    <header class="fund-performance-header">
      <div>
        <p class="section-label">{{ t("funds.performance.section") }}</p>
        <h2>{{ t("funds.performance.title") }}</h2>
        <p class="fund-range-label">
          {{ model.accountLabel }} · {{ model.displayedRange }}
        </p>
      </div>
      <div class="fund-chart-controls">
        <div
          class="fund-mode-control"
          :aria-label="t('funds.performance.chartModeAria')"
        >
          <button
            type="button"
            :class="{ active: model.mode === 'value' }"
            :aria-pressed="model.mode === 'value'"
            @click="emit('update:mode', 'value')"
          >
            {{ t("funds.performance.portfolioValue") }}
          </button>
          <button
            type="button"
            :class="{ active: model.mode === 'return' }"
            :aria-pressed="model.mode === 'return'"
            @click="emit('update:mode', 'return')"
          >
            {{ t("funds.performance.returnPercent") }}
          </button>
        </div>
        <div
          class="fund-range-control"
          :aria-label="t('funds.performance.rangeAria')"
        >
          <button
            v-for="item in model.ranges"
            :key="item.key"
            type="button"
            :class="{ active: model.range === item.key }"
            :aria-pressed="model.range === item.key"
            @click="emit('select-range', item.key)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>
    </header>

    <div class="fund-period-kpis">
      <div>
        <small>{{ t("funds.performance.closingValue") }}</small>
        <strong>{{
          model.formatters.money(
            model.lastPerformance?.value ?? model.totalValue,
          )
        }}</strong>
      </div>
      <div>
        <small>{{ t("funds.performance.contributedCapital") }}</small>
        <strong>{{
          model.formatters.money(
            model.lastPerformance?.invested ?? model.totalInvested,
          )
        }}</strong>
      </div>
      <div>
        <small>{{ t("funds.performance.totalPnl") }}</small>
        <strong
          :class="{
            positive: (model.lastPerformance?.pnl ?? 0) >= 0,
            negative: (model.lastPerformance?.pnl ?? 0) < 0,
          }"
        >
          {{ model.formatters.signedMoney(model.lastPerformance?.pnl ?? 0) }}
        </strong>
        <span>
          {{
            model.formatters.percentage(
              (model.lastPerformance?.pnl_percent ?? 0) / 100,
            )
          }}
        </span>
      </div>
      <div>
        <small>{{ t("funds.performance.realizedPnl") }}</small>
        <strong
          :class="{
            positive: model.realizedPnl >= 0,
            negative: model.realizedPnl < 0,
          }"
        >
          {{ model.formatters.signedMoney(model.realizedPnl) }}
        </strong>
      </div>
      <div>
        <small>{{ model.periodLabel }}</small>
        <strong
          :class="{
            positive: model.periodPnl >= 0,
            negative: model.periodPnl < 0,
          }"
        >
          {{ model.formatters.signedMoney(model.periodPnl) }}
        </strong>
        <span>{{ model.formatters.percentage(model.periodPnlPercent) }}</span>
      </div>
    </div>

    <div v-if="model.loading" class="fund-chart-state">
      {{ t("funds.performance.calculating") }}
    </div>
    <div v-else-if="model.error" class="fund-chart-state error-state">
      <strong>{{ t("funds.performance.unavailable") }}</strong>
      <p>{{ model.error }}</p>
      <button type="button" @click="emit('retry')">
        {{ t("funds.actions.retry") }}
      </button>
    </div>
    <FundPerformanceChart
      v-else-if="model.points.length >= 2"
      :points="model.points"
      :mode="model.mode"
    />
    <div v-else class="fund-chart-state">
      <strong>{{ t("funds.performance.insufficientHistory") }}</strong>
      <p>{{ t("funds.performance.insufficientHistoryHint") }}</p>
    </div>
  </article>
</template>

<style scoped>
.section-label {
  font-size: 10px;
}
.fund-performance-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}
.fund-performance-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 750;
  letter-spacing: -0.035em;
}
.fund-range-label {
  margin: 7px 0 0;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
.fund-chart-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}
.fund-mode-control,
.fund-range-control {
  display: flex;
  padding: 4px;
  border-radius: 12px;
  background: var(--fz-surface-soft);
}
.fund-mode-control button,
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
.fund-mode-control button.active,
.fund-range-control button.active {
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
}
.fund-period-kpis {
  margin: 20px 0 14px;
  padding: 14px 0;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  border-block: 1px solid var(--fz-line);
}
.fund-period-kpis > div {
  min-width: 0;
  padding: 0 16px;
  display: grid;
  gap: 3px;
  border-left: 1px solid var(--fz-line);
}
.fund-period-kpis > div:first-child {
  padding-left: 0;
  border-left: 0;
}
.fund-period-kpis small,
.fund-period-kpis span {
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-period-kpis strong {
  overflow: hidden;
  font-size: 14px;
  font-weight: 740;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
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

@media (max-width: 1050px) {
  .fund-performance-header {
    align-items: stretch;
    flex-direction: column;
  }
  .fund-chart-controls {
    justify-content: space-between;
  }
}
@media (max-width: 720px) {
  .fund-chart-controls {
    align-items: stretch;
    flex-direction: column;
  }
  .fund-mode-control,
  .fund-range-control {
    overflow-x: auto;
  }
  .fund-mode-control button,
  .fund-range-control button {
    flex: 1;
  }
  .fund-period-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px 0;
  }
  .fund-period-kpis > div {
    min-height: 42px;
  }
  .fund-period-kpis > div:nth-child(odd) {
    padding-left: 0;
    border-left: 0;
  }
}

/* Preserve the compact typography used by the parent dashboard view. */
.fund-performance-header h2 {
  font-size: 20px;
}
.fund-period-kpis strong {
  font-size: 16px;
}
</style>
