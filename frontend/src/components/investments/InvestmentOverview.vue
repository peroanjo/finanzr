<script setup lang="ts">
import { computed } from "vue";
import AssetReturnToggle from "../AssetReturnToggle.vue";
import type { AssetReturnMode } from "../AssetReturnToggle.vue";
import type { NormalizedPosition } from "../../domain/investments";

type Formatter = (value: number) => string;

export interface InvestmentOverviewLabels {
  assets: {
    section: string;
    title: string;
    asset: string;
    portfolioValue: string;
    contributed: string;
    currentPrice: string;
    averagePrice: string;
    value: string;
    return: string;
    pnl: string;
    pending: string;
    emptyTitle: string;
    emptyDescription: string;
  };
  kpis: {
    section: string;
    title: string;
    portfolioValue: string;
    openAsset: string;
    openAssets: string;
    unrealizedPnl: string;
    versusCost: string;
    realizedPnl: string;
    recordedSales: string;
    totalPnl: string;
    realizedAndOpen: string;
    marketData: string;
    updating: string;
    update: string;
  };
}

const emit = defineEmits<{
  "update:assetReturnMode": [value: AssetReturnMode];
  refresh: [];
}>();

const props = defineProps<{
  topPositions: NormalizedPosition[];
  openPositionsCount: number;
  totalValue: number;
  unrealizedPnl: number;
  openReturn: number;
  realizedPnl: number;
  totalPnl: number;
  latestUpdate: string;
  priceMessage: string;
  refreshingPrices: boolean;
  currencyLabel: string;
  assetReturnMode: AssetReturnMode;
  labels: InvestmentOverviewLabels;
  formatMoney: Formatter;
  formatPercentage: Formatter;
  formatSignedMoney: Formatter;
}>();

const assetReturnMode = computed({
  get: () => props.assetReturnMode,
  set: (value: AssetReturnMode) => emit("update:assetReturnMode", value),
});

function positionReturn(position: NormalizedPosition) {
  const metadataValue = position.metadata.returnPercent;
  return typeof metadataValue === "number"
    ? metadataValue
    : position.cost
      ? (position.unrealizedPnl ?? 0) / position.cost
      : 0;
}
</script>

<template>
  <div class="fund-top-grid investment-overview">
    <article class="fund-assets-panel">
      <header class="fund-panel-header">
        <div>
          <p class="section-label">{{ labels.assets.section }}</p>
          <h2>{{ labels.assets.title }}</h2>
        </div>
      </header>

      <div v-if="topPositions.length" class="fund-asset-table">
        <div class="fund-asset-head" aria-hidden="true">
          <span>{{ labels.assets.asset }}</span>
          <span>{{ labels.assets.portfolioValue }}</span>
          <span>{{ labels.assets.contributed }}</span>
          <span>{{ labels.assets.currentPrice }}</span>
          <span>{{ labels.assets.averagePrice }}</span>
          <AssetReturnToggle v-model="assetReturnMode" />
        </div>
        <div
          v-for="item in topPositions"
          :key="item.assetKey"
          class="fund-asset-row asset-row"
        >
          <span class="fund-asset-id">
            <i>{{ item.name.slice(0, 1) }}</i>
            <span
              ><strong>{{ item.name }}</strong
              ><small>{{ item.displayIdentifier }}</small></span
            >
          </span>
          <span class="fund-asset-cell">
            <small>{{ labels.assets.value }}</small>
            <strong>{{
              item.currentValue == null
                ? labels.assets.pending
                : formatMoney(item.currentValue)
            }}</strong>
          </span>
          <span class="fund-asset-cell fund-asset-contributed">
            <small>{{ labels.assets.contributed }}</small>
            <strong>{{ formatMoney(item.cost) }}</strong>
          </span>
          <span class="fund-asset-cell">
            <small>{{ labels.assets.currentPrice }}</small>
            <strong>{{
              item.currentPrice == null
                ? labels.assets.pending
                : formatMoney(item.currentPrice)
            }}</strong>
          </span>
          <span class="fund-asset-cell">
            <small>{{ labels.assets.averagePrice }}</small>
            <strong>{{
              formatMoney(item.quantity ? item.cost / item.quantity : 0)
            }}</strong>
          </span>
          <span
            class="fund-asset-cell fund-asset-return asset-return-value"
            :class="{
              positive: (item.unrealizedPnl ?? 0) >= 0,
              negative: (item.unrealizedPnl ?? 0) < 0,
            }"
          >
            <small>{{
              assetReturnMode === "percent"
                ? labels.assets.return
                : labels.assets.pnl
            }}</small>
            <strong>{{
              item.unrealizedPnl == null
                ? "—"
                : assetReturnMode === "percent"
                  ? formatPercentage(positionReturn(item))
                  : formatSignedMoney(item.unrealizedPnl)
            }}</strong>
          </span>
        </div>
      </div>
      <div v-else class="fund-empty-compact">
        <strong>{{ labels.assets.emptyTitle }}</strong>
        <p>{{ labels.assets.emptyDescription }}</p>
      </div>
    </article>

    <aside class="fund-kpi-panel">
      <header class="fund-panel-header">
        <div>
          <p class="section-label">{{ labels.kpis.section }}</p>
          <h2>{{ labels.kpis.title }}</h2>
        </div>
        <span class="fund-live"><i /> {{ currencyLabel }}</span>
      </header>

      <div class="fund-kpi-grid">
        <article class="fund-kpi primary">
          <small>{{ labels.kpis.portfolioValue }}</small>
          <strong>{{ formatMoney(totalValue) }}</strong>
          <span>{{
            (openPositionsCount === 1
              ? labels.kpis.openAsset
              : labels.kpis.openAssets
            ).replace("{count}", String(openPositionsCount))
          }}</span>
        </article>
        <article class="fund-kpi">
          <small>{{ labels.kpis.unrealizedPnl }}</small>
          <strong
            :class="{
              positive: unrealizedPnl >= 0,
              negative: unrealizedPnl < 0,
            }"
            >{{ formatSignedMoney(unrealizedPnl) }}</strong
          >
          <span>{{
            labels.kpis.versusCost.replace(
              "{return}",
              formatPercentage(openReturn),
            )
          }}</span>
        </article>
        <article class="fund-kpi">
          <small>{{ labels.kpis.realizedPnl }}</small>
          <strong
            :class="{ positive: realizedPnl >= 0, negative: realizedPnl < 0 }"
            >{{ formatSignedMoney(realizedPnl) }}</strong
          >
          <span>{{ labels.kpis.recordedSales }}</span>
        </article>
        <article class="fund-kpi">
          <small>{{ labels.kpis.totalPnl }}</small>
          <strong
            :class="{ positive: totalPnl >= 0, negative: totalPnl < 0 }"
            >{{ formatSignedMoney(totalPnl) }}</strong
          >
          <span>{{ labels.kpis.realizedAndOpen }}</span>
        </article>
      </div>

      <div class="fund-utility">
        <div>
          <small>{{ labels.kpis.marketData }}</small>
          <strong>{{ latestUpdate }}</strong>
          <span v-if="priceMessage">{{ priceMessage }}</span>
        </div>
        <button
          class="fund-action-button"
          type="button"
          :disabled="refreshingPrices"
          @click="emit('refresh')"
        >
          {{ refreshingPrices ? labels.kpis.updating : labels.kpis.update }}
        </button>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.section-label {
  font-size: 10px;
}
.investment-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(340px, 0.72fr);
  gap: 20px;
}
.fund-assets-panel,
.fund-kpi-panel {
  min-width: 0;
  padding: 24px;
  border: 1px solid var(--fz-line);
  border-radius: 22px;
  background: var(--fz-surface);
  box-shadow: var(--fz-shadow);
}
.fund-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.fund-panel-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 750;
  letter-spacing: -0.03em;
}
.fund-asset-table {
  margin-top: 19px;
  overflow-x: auto;
}
.fund-asset-head,
.fund-asset-row {
  min-width: 680px;
  display: grid;
  grid-template-columns: minmax(145px, 1.2fr) repeat(5, minmax(82px, 0.76fr));
  gap: 8px;
  align-items: center;
}
.fund-asset-head {
  padding: 0 8px 8px;
  color: var(--fz-muted);
  font-size: 11px;
}
.fund-asset-head span:not(:first-child) {
  text-align: right;
}
.fund-asset-row {
  width: 100%;
  padding: 11px 8px;
  border: 0;
  border-top: 1px solid var(--fz-line);
  background: transparent;
  color: var(--fz-ink);
  cursor: default;
}
.fund-asset-row > span:not(:first-child) {
  text-align: right;
}
.fund-asset-cell small,
.fund-asset-cell strong,
.fund-asset-id strong,
.fund-asset-id small {
  display: block;
}
.fund-asset-cell small,
.fund-asset-id small {
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-asset-cell strong {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.fund-asset-id {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  text-align: left !important;
}
.fund-asset-id > i {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 10px;
  background: color-mix(in srgb, var(--fz-accent) 13%, var(--fz-surface));
  color: var(--fz-accent);
  font-size: 12px;
  font-style: normal;
  font-weight: 820;
}
.fund-asset-id > span {
  min-width: 0;
}
.fund-asset-id strong {
  font-size: 11px;
  font-weight: 760;
}
.fund-asset-id strong,
.fund-asset-id small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fund-asset-contributed strong {
  color: var(--fz-accent);
}
.fund-asset-return strong {
  font-variant-numeric: tabular-nums;
}
.fund-kpi-panel .fund-panel-header .fund-live {
  padding: 6px 9px;
  border-radius: 999px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  font-size: 11px;
}
.fund-live i {
  width: 6px;
  height: 6px;
  display: inline-block;
  margin-right: 5px;
  border-radius: 50%;
  background: var(--fz-accent);
}
.fund-kpi-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 18px;
  border-top: 1px solid var(--fz-line);
  border-left: 1px solid var(--fz-line);
}
.fund-kpi {
  min-width: 0;
  padding: 14px;
  display: grid;
  gap: 5px;
  border-right: 1px solid var(--fz-line);
  border-bottom: 1px solid var(--fz-line);
  background: color-mix(in srgb, var(--fz-surface-soft) 35%, transparent);
}
.fund-kpi.primary {
  background: linear-gradient(
    120deg,
    color-mix(in srgb, var(--fz-accent) 9%, transparent),
    transparent
  );
  grid-column: 1 / -1;
}
.fund-kpi small,
.fund-kpi span {
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-kpi strong {
  overflow: hidden;
  font-size: 16px;
  font-weight: 760;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.04em;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fund-kpi.primary strong {
  font-size: 27px;
}
.fund-utility {
  margin-top: 17px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.fund-utility > div {
  min-width: 0;
  display: grid;
  gap: 2px;
}
.fund-utility small,
.fund-utility span {
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-utility strong {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.fund-utility span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fund-utility .fund-action-button {
  white-space: nowrap;
}
.fund-action-button {
  padding: 9px 12px;
  border: 1px solid color-mix(in srgb, var(--fz-accent) 45%, var(--fz-line));
  border-radius: 10px;
  background: color-mix(in srgb, var(--fz-accent) 9%, transparent);
  color: var(--fz-ink);
  font-size: 11px;
  font-weight: 720;
  cursor: pointer;
}
.fund-action-button:disabled {
  opacity: 0.55;
  cursor: wait;
}
.fund-empty-compact {
  min-height: 180px;
  display: grid;
  place-items: center;
  color: var(--fz-muted);
  font-size: 10px;
}

@media (max-width: 1050px) {
  .investment-overview {
    grid-template-columns: minmax(0, 1fr);
  }
  .fund-kpi-panel {
    order: -1;
  }
  .fund-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .fund-assets-panel,
  .fund-kpi-panel {
    padding: 19px 17px;
    border-radius: 18px;
  }
  .fund-kpi-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
