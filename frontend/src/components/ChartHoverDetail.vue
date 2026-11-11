<script setup lang="ts">
export interface ChartHoverData {
  x: number;
  y: number;
  title: string;
  rows: Array<{ label: string; value: string; color: string }>;
}

defineProps<{ detail: ChartHoverData }>();
</script>

<template>
  <div
    class="chart-hover-detail"
    :style="{
      left: `clamp(0px, ${detail.x}px, max(0px, calc(100% - 340px)))`,
      top: `clamp(0px, ${detail.y}px, max(0px, calc(100% - ${44 + detail.rows.length * 20}px)))`,
    }"
  >
    <strong>{{ detail.title }}</strong>
    <div
      v-for="row in detail.rows"
      :key="row.label"
      class="chart-hover-detail-row"
    >
      <i :style="{ background: row.color }" aria-hidden="true" />
      <span
        >{{ row.label }}: <b>{{ row.value }}</b></span
      >
    </div>
  </div>
</template>

<style scoped>
.chart-hover-detail {
  position: absolute;
  z-index: 4;
  width: min(340px, 100%);
  padding: 12px;
  border-radius: 8px;
  background: var(--fz-tooltip);
  color: var(--fz-tooltip-text);
  box-shadow: 0 6px 24px var(--fz-chart-tooltip-shadow);
  font-size: 12px;
  line-height: 20px;
  pointer-events: none;
}
.chart-hover-detail > strong {
  display: block;
  margin-bottom: 4px;
}
.chart-hover-detail-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.chart-hover-detail-row i {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  border-radius: 2px;
}
.chart-hover-detail-row span {
  overflow-wrap: anywhere;
}
.chart-hover-detail-row b {
  font-weight: 600;
}
</style>
