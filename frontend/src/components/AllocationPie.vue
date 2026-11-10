<script setup lang="ts">
import { computed, ref } from "vue";
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
      };
    });
});
</script>

<template>
  <div class="allocation-pie">
    <div v-if="slices.length" class="allocation-pie-stage">
      <svg
        viewBox="22 22 196 196"
        aria-hidden="true"
        class="allocation-pie-disc"
      >
        <g
          v-for="slice in slices"
          :key="slice.key"
          class="allocation-pie-slice"
          :class="{ active: active?.key === slice.key }"
          :style="{ '--slice-color': slice.color }"
          @mouseenter="selected = slice.key"
          @click="selected = slice.key"
        >
          <path :d="slice.path" />
        </g>
      </svg>
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
  display: grid;
  gap: 22px;
  margin-top: 24px;
  container-type: inline-size;
}
.allocation-pie-stage {
  width: 148px;
  margin: 0 auto;
}
.allocation-pie-disc {
  display: block;
  width: 100%;
}
.allocation-pie-slice {
  cursor: pointer;
  opacity: 0.85;
  transition: opacity 160ms ease;
}
.allocation-pie-slice.active {
  opacity: 1;
}
.allocation-pie-slice path {
  fill: color-mix(in srgb, var(--slice-color) 72%, var(--fz-muted));
  stroke: var(--fz-surface);
  stroke-width: 2;
  stroke-linejoin: round;
}
.allocation-pie-legend {
  display: grid;
  min-width: 0;
}
.allocation-pie-legend button {
  display: grid;
  grid-template-columns: 6px minmax(0, 1fr) auto 52px;
  align-items: baseline;
  gap: 10px;
  width: 100%;
  min-height: 44px;
  padding: 12px 0;
  border: 0;
  border-bottom: 1px solid var(--fz-line);
  border-radius: 0;
  background: transparent;
  color: var(--fz-ink);
  text-align: left;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}
.allocation-pie-legend button:last-child {
  border-bottom: 0;
}
.allocation-pie-legend button:focus-visible {
  outline-offset: 3px;
  border-radius: 3px;
}
.allocation-pie-legend button:disabled {
  cursor: default;
  opacity: 1;
}
.allocation-pie-dot {
  width: 5px;
  height: 5px;
  align-self: center;
  border-radius: 50%;
  background: color-mix(in srgb, var(--slice-color) 72%, var(--fz-muted));
}
.allocation-pie-name {
  overflow-wrap: anywhere;
  line-height: 1.5;
}
.allocation-pie-legend strong {
  font-size: 12px;
  font-weight: 550;
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.allocation-pie-legend small {
  color: var(--fz-muted);
  text-align: right;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.allocation-pie-empty {
  margin: 0;
  padding: 16px 0;
  color: var(--fz-muted);
  text-align: center;
}
@container (max-width: 320px) {
  .allocation-pie-legend button {
    grid-template-columns: 6px minmax(0, 1fr) auto;
    gap: 3px 9px;
  }
  .allocation-pie-dot {
    grid-row: 1 / 3;
  }
  .allocation-pie-name {
    grid-column: 2;
    grid-row: 1 / 3;
  }
  .allocation-pie-legend strong {
    grid-column: 3;
  }
  .allocation-pie-legend small {
    grid-column: 3;
  }
}
@container (max-width: 240px) {
  .allocation-pie-dot {
    grid-row: 1;
  }
  .allocation-pie-name {
    grid-column: 2 / -1;
    grid-row: 1;
  }
  .allocation-pie-legend strong {
    grid-column: 2;
    grid-row: 2;
    text-align: left;
  }
  .allocation-pie-legend small {
    grid-column: 3;
    grid-row: 2;
  }
}
@media (min-width: 721px) and (max-width: 1100px) {
  .allocation-pie {
    grid-template-columns: 148px minmax(0, 1fr);
    align-items: center;
    gap: 32px;
  }
}
@media (min-width: 1101px) {
  .allocation-pie {
    display: flex;
    flex-direction: column;
    flex: 1;
    gap: 18px;
    margin-top: 16px;
  }
  .allocation-pie-stage {
    display: grid;
    place-items: center;
    flex: 1;
    width: 100%;
    min-height: 148px;
  }
  .allocation-pie-disc {
    width: clamp(148px, 14vw, 188px);
    max-width: 100%;
  }
  .allocation-pie-legend {
    margin-top: auto;
  }
}
@media (prefers-reduced-motion: reduce) {
  .allocation-pie-slice {
    transition: none;
  }
}
</style>
