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
const gradientId = useId();
const selected = ref<string | null>(null);
const active = computed(() =>
  props.items.find((item) => item.key === selected.value && item.share > 0),
);
const slices = computed(() => {
  let angle = -Math.PI / 2;
  return props.items
    .filter((item) => item.share > 0)
    .map((item) => {
      const start = angle;
      const sweep = item.share * Math.PI * 2;
      angle += sweep;
      const point = (radius: number, a: number) =>
        `${120 + radius * Math.cos(a)} ${120 + radius * Math.sin(a)}`;
      const middle = start + sweep / 2;
      // Split both boundaries into two arcs to support a complete ring.
      const path = `M ${point(94, start)} A 94 94 0 0 1 ${point(94, middle)} A 94 94 0 0 1 ${point(94, angle)} L ${point(62, angle)} A 62 62 0 0 0 ${point(62, middle)} A 62 62 0 0 0 ${point(62, start)} Z`;
      return {
        ...item,
        path,
        offset: `translate(${Math.cos(middle) * 4}px, ${Math.sin(middle) * 4}px)`,
      };
    });
});
</script>

<template>
  <div class="allocation-pie">
    <div v-if="slices.length" class="allocation-pie-stage">
      <div class="allocation-pie-ring">
        <svg
          viewBox="16 16 208 208"
          aria-hidden="true"
          class="allocation-pie-disc"
        >
          <defs>
            <radialGradient
              v-for="(slice, index) in slices"
              :id="`${gradientId}-satin-${index}`"
              :key="slice.key"
              gradientUnits="userSpaceOnUse"
              cx="120"
              cy="120"
              r="94"
              :style="{ '--slice-color': slice.color }"
              class="allocation-pie-satin"
            >
              <stop offset="0" class="satin-inner" />
              <stop offset="66%" class="satin-inner" />
              <stop offset="84%" class="satin-body" />
              <stop offset="100%" class="satin-outer" />
            </radialGradient>
            <linearGradient
              :id="`${gradientId}-light`"
              gradientUnits="userSpaceOnUse"
              x1="26"
              y1="26"
              x2="214"
              y2="214"
            >
              <stop offset="0" stop-color="white" stop-opacity=".20" />
              <stop offset=".5" stop-color="white" stop-opacity="0" />
              <stop offset="1" stop-color="black" stop-opacity=".10" />
            </linearGradient>
          </defs>
          <g
            v-for="(slice, index) in slices"
            :key="slice.key"
            class="allocation-pie-slice"
            :class="{ active: active?.key === slice.key }"
            :style="{
              '--slice-color': slice.color,
              '--slice-offset': slice.offset,
            }"
            @mouseenter="selected = slice.key"
            @mouseleave="selected = null"
          >
            <path class="allocation-pie-hit" :d="slice.path" />
            <g class="allocation-pie-shape">
              <path
                class="allocation-pie-base"
                :d="slice.path"
                :fill="`url(#${gradientId}-satin-${index})`"
              />
              <path :d="slice.path" :fill="`url(#${gradientId}-light)`" />
            </g>
          </g>
        </svg>
        <div v-if="active" class="allocation-pie-center" aria-hidden="true">
          <strong>{{ n(active.value, "currency") }}</strong>
          <span>{{ active.label }}</span>
          <small>{{ n(active.share, "percent") }}</small>
        </div>
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
        @mouseleave="selected = null"
        @focus="selected = item.key"
        @blur="selected = null"
        @keydown.esc="selected = null"
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
  width: 100%;
  margin: 0 auto;
  display: grid;
  place-items: center;
}
.allocation-pie-ring {
  position: relative;
  width: 208px;
  max-width: 100%;
}
.allocation-pie-disc {
  display: block;
  width: 100%;
}
.allocation-pie-slice {
  cursor: pointer;
}
.allocation-pie-hit {
  fill: transparent;
}
.allocation-pie-satin {
  --slice-base: color-mix(in srgb, var(--slice-color) 85%, var(--fz-muted));
}
.satin-inner {
  stop-color: color-mix(in srgb, var(--slice-base) 74%, black);
}
.satin-body {
  stop-color: var(--slice-base);
}
.satin-outer {
  stop-color: color-mix(in srgb, var(--slice-base) 84%, white);
}
.allocation-pie-shape {
  pointer-events: none;
  filter: brightness(1);
  transition:
    transform 180ms ease,
    filter 180ms ease;
}
.allocation-pie-base {
  stroke: var(--fz-surface);
  stroke-width: 1.5;
  stroke-linejoin: round;
}
.allocation-pie-slice.active .allocation-pie-shape {
  transform: var(--slice-offset);
  filter: brightness(1.06);
}
.allocation-pie-center {
  position: absolute;
  inset: 23%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  text-align: center;
  pointer-events: none;
  color: var(--fz-ink);
}
.allocation-pie-center strong {
  font-size: 16px;
  line-height: 1.2;
  letter-spacing: -0.04em;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.allocation-pie-center span {
  font-size: 10px;
  line-height: 1.35;
  color: var(--fz-muted);
  overflow-wrap: anywhere;
}
.allocation-pie-center small {
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
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
  background: color-mix(in srgb, var(--slice-color) 85%, var(--fz-muted));
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
    grid-template-columns: 208px minmax(0, 1fr);
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
    min-height: 208px;
  }
  .allocation-pie-ring {
    width: clamp(208px, 17vw, 232px);
    max-width: 100%;
  }
  .allocation-pie-legend {
    margin-top: auto;
  }
}
@media (prefers-reduced-motion: reduce) {
  .allocation-pie-shape {
    transition: none;
  }
}
</style>
