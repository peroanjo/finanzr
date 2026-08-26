<script setup lang="ts">
export interface InvestmentAllocationItem {
  key: string;
  label: string;
  value: number;
  share: number;
  color: string;
}

defineProps<{
  items: InvestmentAllocationItem[];
  total: number;
  accountLabel: string;
  title: string;
  barLabel: string;
  emptyLabel: string;
  formatValue: (value: number) => string;
  formatShare: (value: number) => string;
  segmentAria: (item: InvestmentAllocationItem) => string;
}>();
</script>

<template>
  <div
    class="fund-position-allocation investment-allocation-strip"
    data-testid="fund-position-allocation"
    role="group"
    :aria-label="`${title} · ${accountLabel}`"
  >
    <div class="fund-position-allocation-header">
      <div>
        <strong>{{ title }}</strong>
        <span>{{ accountLabel }}</span>
      </div>
      <strong v-if="items.length" class="fund-position-allocation-total">{{
        formatValue(total)
      }}</strong>
    </div>
    <div
      v-if="items.length"
      class="fund-position-allocation-bar"
      role="group"
      :aria-label="barLabel"
    >
      <span
        v-for="item in items"
        :key="item.key"
        class="fund-position-allocation-segment"
        :style="{ width: `${item.share * 100}%`, background: item.color }"
        role="img"
        tabindex="0"
        :aria-label="segmentAria(item)"
      >
        <span class="fund-position-allocation-tooltip" role="tooltip">
          <strong>{{ item.label }}</strong>
          <span
            >{{ formatValue(item.value) }} · {{ formatShare(item.share) }}</span
          >
        </span>
      </span>
    </div>
    <p v-else class="fund-position-allocation-empty">{{ emptyLabel }}</p>
  </div>
</template>

<style scoped>
.investment-allocation-strip {
  margin-bottom: 18px;
  padding: 13px 14px 14px;
  border: 1px solid var(--fz-line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--fz-surface-soft) 38%, transparent);
}
.fund-position-allocation-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}
.fund-position-allocation-header > div {
  min-width: 0;
  display: grid;
  gap: 3px;
}
.fund-position-allocation-header strong {
  font-size: 10px;
  font-weight: 760;
}
.fund-position-allocation-header span {
  overflow: hidden;
  color: var(--fz-muted);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fund-position-allocation-total {
  flex: 0 0 auto;
  color: var(--fz-muted);
  font-variant-numeric: tabular-nums;
}
.fund-position-allocation-bar {
  height: 12px;
  display: flex;
  margin-top: 11px;
  overflow: visible;
  border-radius: 999px;
  background: var(--fz-line);
}
.fund-position-allocation-segment {
  position: relative;
  height: 100%;
  display: block;
  flex: 0 0 auto;
  padding: 0;
  border: 0;
  color: inherit;
  cursor: default;
  outline: 1px solid color-mix(in srgb, var(--fz-surface) 60%, transparent);
  outline-offset: -1px;
}
.fund-position-allocation-segment:hover,
.fund-position-allocation-segment:focus-visible {
  z-index: 2;
  filter: brightness(1.08) saturate(1.05);
}
.fund-position-allocation-segment:focus-visible {
  outline: 2px solid var(--fz-ink);
  outline-offset: 2px;
}
.fund-position-allocation-segment:first-child {
  border-radius: 999px 0 0 999px;
}
.fund-position-allocation-segment:last-child {
  border-radius: 0 999px 999px 0;
}
.fund-position-allocation-segment:only-child {
  border-radius: 999px;
}
.fund-position-allocation-tooltip {
  position: absolute;
  bottom: calc(100% + 9px);
  left: 50%;
  width: max-content;
  max-width: min(240px, calc(100vw - 32px));
  display: grid;
  gap: 4px;
  padding: 9px 11px;
  border-radius: 8px;
  color: var(--fz-tooltip-text);
  background: var(--fz-tooltip);
  box-shadow: 0 8px 18px var(--fz-chart-tooltip-shadow);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  line-height: 1.25;
  text-align: left;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  visibility: hidden;
  transform: translate(-50%, 3px);
  transition:
    opacity 0.12s ease,
    transform 0.12s ease,
    visibility 0.12s ease;
}
.fund-position-allocation-tooltip strong {
  overflow: hidden;
  max-width: 218px;
  font-size: 10px;
  text-overflow: ellipsis;
}
.fund-position-allocation-tooltip > span {
  opacity: 0.78;
}
.fund-position-allocation-segment:hover .fund-position-allocation-tooltip,
.fund-position-allocation-segment:focus-visible
  .fund-position-allocation-tooltip {
  opacity: 1;
  visibility: visible;
  transform: translate(-50%, 0);
}
.fund-position-allocation-segment:first-child
  .fund-position-allocation-tooltip {
  left: 0;
  transform: translate(0, 3px);
}
.fund-position-allocation-segment:first-child:hover
  .fund-position-allocation-tooltip,
.fund-position-allocation-segment:first-child:focus-visible
  .fund-position-allocation-tooltip {
  transform: translate(0, 0);
}
.fund-position-allocation-segment:last-child .fund-position-allocation-tooltip {
  right: 0;
  left: auto;
  transform: translate(0, 3px);
}
.fund-position-allocation-segment:last-child:hover
  .fund-position-allocation-tooltip,
.fund-position-allocation-segment:last-child:focus-visible
  .fund-position-allocation-tooltip {
  transform: translate(0, 0);
}
.fund-position-allocation-empty {
  margin: 10px 0 0;
  color: var(--fz-muted);
  font-size: 10px;
}

@media (prefers-reduced-motion: reduce) {
  .fund-position-allocation-tooltip {
    transition: none;
  }
}
</style>
