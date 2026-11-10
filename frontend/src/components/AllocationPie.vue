<script setup lang="ts">
import { computed, ref, useId } from "vue";
import { useI18n } from "vue-i18n";

type AllocationItem = {
  key: string;
  label: string;
  value: number;
  share: number;
  color: string;
};
const props = defineProps<{ items: AllocationItem[] }>();
const { t, n } = useI18n();
const id = useId();
const selected = ref<string | null>(null);
const active = computed(
  () =>
    props.items.find((item) => item.key === selected.value && item.share > 0) ??
    [...props.items].sort((a, b) => b.share - a.share)[0],
);
const slices = computed(() => {
  let angle = -Math.PI / 2;
  return props.items
    .filter((item) => item.share > 0)
    .map((item) => {
      const start = angle;
      const sweep = item.share * Math.PI * 2;
      angle += sweep;
      const point = (a: number) =>
        `${120 + 94 * Math.cos(a)} ${120 + 94 * Math.sin(a)}`;
      const middle = start + sweep / 2;
      // Two arcs also cover a single category occupying the entire circle.
      const path = `M 120 120 L ${point(start)} A 94 94 0 0 1 ${point(middle)} A 94 94 0 0 1 ${point(angle)} Z`;
      return {
        ...item,
        path,
        offset: `translate(${Math.cos(middle) * 5}px, ${Math.sin(middle) * 5}px)`,
      };
    });
});
</script>

<template>
  <div class="allocation-pie">
    <div v-if="slices.length" class="allocation-pie-stage">
      <svg viewBox="0 0 240 240" aria-hidden="true" class="allocation-pie-disc">
        <defs>
          <linearGradient :id="`${id}-light`" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="white" stop-opacity=".28" />
            <stop offset=".48" stop-color="white" stop-opacity="0" />
            <stop offset="1" stop-color="black" stop-opacity=".22" />
          </linearGradient>
        </defs>
        <g
          v-for="slice in slices"
          :key="slice.key"
          class="allocation-pie-slice"
          :class="{ active: active?.key === slice.key }"
          :style="{
            '--slice-offset': slice.offset,
            '--slice-color': slice.color,
          }"
          @mouseenter="selected = slice.key"
          @click="selected = slice.key"
        >
          <path :d="slice.path" :fill="slice.color" />
          <path :d="slice.path" :fill="`url(#${id}-light)`" />
        </g>
      </svg>
      <div v-if="active" class="allocation-pie-caption" aria-hidden="true">
        <span :style="{ background: active.color }" />
        <strong>{{ n(active.share, "percent") }}</strong>
        <small>{{ active.label }}</small>
      </div>
    </div>
    <p v-else class="allocation-pie-empty">{{ t("common.noData") }}</p>
    <div class="allocation-pie-legend">
      <button
        v-for="item in items"
        :key="item.key"
        type="button"
        :aria-pressed="active?.key === item.key"
        :disabled="item.share <= 0"
        :style="{ '--slice-color': item.color }"
        @mouseenter="selected = item.key"
        @focus="selected = item.key"
        @click="selected = item.key"
      >
        <span class="allocation-pie-dot" aria-hidden="true" />
        <span class="allocation-pie-name">{{ item.label }}</span>
        <strong>{{ n(item.value, "currency") }}</strong>
        <small>{{ n(item.share, "percent") }}</small>
      </button>
    </div>
  </div>
</template>

<style scoped>
.allocation-pie {
  min-width: 0;
}
.allocation-pie-stage {
  position: relative;
  width: 100%;
  max-width: 320px;
  margin: 8px auto 14px;
  padding-bottom: 18px;
}
.allocation-pie-disc {
  display: block;
  width: 214px;
  max-width: 100%;
  margin: 0 auto;
  overflow: visible;
  filter: drop-shadow(
      0 5px 0 color-mix(in srgb, var(--fz-ink) 18%, var(--fz-surface))
    )
    drop-shadow(0 10px 10px color-mix(in srgb, var(--fz-ink) 12%, transparent));
}
.allocation-pie-slice {
  cursor: pointer;
  transition:
    transform 220ms ease,
    opacity 220ms ease;
  opacity: 0.78;
}
.allocation-pie-slice.active {
  transform: var(--slice-offset);
  opacity: 1;
}
.allocation-pie-slice path {
  stroke: var(--fz-surface);
  stroke-width: 2.5;
  stroke-linejoin: round;
}
.allocation-pie-slice path + path {
  stroke: none;
  pointer-events: none;
}
.allocation-pie-caption {
  position: absolute;
  bottom: 0;
  right: 0;
  display: grid;
  grid-template-columns: 6px auto;
  align-items: center;
  gap: 2px 8px;
  max-width: 72%;
  padding: 9px 12px;
  border: 1px solid var(--fz-line);
  border-radius: 12px;
  background: var(--fz-surface);
  box-shadow: 0 4px 16px color-mix(in srgb, var(--fz-ink) 6%, transparent);
}
.allocation-pie-caption > span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.allocation-pie-caption strong {
  font-size: 22px;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.04em;
}
.allocation-pie-caption small {
  grid-column: 2;
  color: var(--fz-muted);
  font-size: 10px;
  overflow-wrap: anywhere;
}
.allocation-pie-legend {
  display: grid;
  gap: 3px;
}
.allocation-pie-legend button {
  display: grid;
  grid-template-columns: 7px minmax(0, 1fr) auto;
  align-items: center;
  gap: 2px 9px;
  width: 100%;
  min-height: 44px;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: var(--fz-ink);
  text-align: left;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}
.allocation-pie-legend button[aria-pressed="true"] {
  background: color-mix(in srgb, var(--slice-color) 8%, var(--fz-surface));
  border-color: color-mix(in srgb, var(--slice-color) 20%, var(--fz-surface));
}
.allocation-pie-legend button:disabled {
  cursor: default;
  opacity: 1;
}
.allocation-pie-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--slice-color);
}
.allocation-pie-name {
  grid-column: 2;
  grid-row: 1 / 3;
  overflow-wrap: anywhere;
}
.allocation-pie-legend strong {
  font-size: 12px;
  font-weight: 650;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.allocation-pie-legend small {
  grid-column: 3;
  color: var(--fz-muted);
  text-align: right;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}
.allocation-pie-empty {
  padding: 24px 0;
  color: var(--fz-muted);
  text-align: center;
}
@media (min-width: 721px) and (max-width: 1100px) {
  .allocation-pie {
    display: grid;
    grid-template-columns: minmax(180px, 0.8fr) minmax(0, 1fr);
    align-items: center;
    gap: 24px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .allocation-pie-slice {
    transition: none;
  }
}
</style>
