<script setup lang="ts">
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  LinearScale,
  Tooltip,
} from "chart.js";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { reportingCurrency } from "../i18n";

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);

const props = defineProps<{
  labels: string[];
  values: number[];
  label: string;
  selectedIndex?: number;
}>();
const emit = defineEmits<{ select: [index: number] }>();
const { locale, t } = useI18n();
const canvas = ref<HTMLCanvasElement>();
let chart: Chart | null = null;
let themeObserver: MutationObserver | null = null;

function render() {
  chart?.destroy();
  if (!canvas.value) return;

  const styles = getComputedStyle(canvas.value);
  const accent = styles.getPropertyValue("--fz-accent").trim() || "#3ddc97";
  const negative = styles.getPropertyValue("--fz-negative").trim() || "#c95151";
  const muted = styles.getPropertyValue("--fz-muted").trim() || "#8fa49a";
  const grid =
    styles.getPropertyValue("--fz-chart-grid").trim() ||
    "rgba(143,164,154,.15)";
  const tooltip = styles.getPropertyValue("--fz-tooltip").trim() || "#101e18";
  const tooltipText =
    styles.getPropertyValue("--fz-tooltip-text").trim() || "#edf3ef";
  const money = new Intl.NumberFormat(locale.value, {
    style: "currency",
    currency: reportingCurrency.value,
    maximumFractionDigits: 0,
  });
  const hasSelection =
    props.selectedIndex !== undefined && props.selectedIndex >= 0;

  chart = new Chart(canvas.value, {
    type: "bar",
    data: {
      labels: props.labels,
      datasets: [
        {
          label: props.label,
          data: props.values,
          backgroundColor: props.values.map((value, index) => {
            const color = value >= 0 ? accent : negative;
            if (!hasSelection) return `${color}cc`;
            return `${color}${index === props.selectedIndex ? "f2" : "70"}`;
          }),
          hoverBackgroundColor: props.values.map((value) =>
            value >= 0 ? accent : negative,
          ),
          borderColor: props.values.map((value) =>
            value >= 0 ? accent : negative,
          ),
          borderWidth: props.values.map((_value, index) =>
            index === props.selectedIndex ? 2 : 1,
          ),
          borderRadius: 5,
          borderSkipped: false,
          maxBarThickness: 44,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: "index" },
      onClick: (_event, elements) => {
        const index = elements[0]?.index;
        if (index !== undefined) emit("select", index);
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: tooltip,
          titleColor: tooltipText,
          bodyColor: tooltipText,
          padding: 12,
          displayColors: false,
          callbacks: {
            label: (context) => {
              const value = Number(context.parsed.y);
              return `${value >= 0 ? "+" : "−"}${money.format(Math.abs(value))}`;
            },
          },
        },
      },
      scales: {
        x: {
          border: { display: false },
          grid: { display: false },
          ticks: {
            color: muted,
            maxTicksLimit: 12,
            maxRotation: 0,
            font: { size: 10, weight: 600 },
          },
        },
        y: {
          border: { display: false },
          grid: {
            color: (context) =>
              Number(context.tick.value) === 0 ? muted : grid,
            lineWidth: (context) =>
              Number(context.tick.value) === 0 ? 1.4 : 1,
          },
          ticks: {
            color: muted,
            maxTicksLimit: 5,
            callback: (value) => money.format(Number(value)),
            font: { size: 10, weight: 600 },
          },
        },
      },
    },
  });
}

onMounted(() => {
  render();
  const shell = canvas.value?.closest(".app-shell");
  if (shell) {
    themeObserver = new MutationObserver(render);
    themeObserver.observe(shell, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
  }
});
watch(
  () => [
    props.labels,
    props.values,
    props.label,
    props.selectedIndex,
    locale.value,
    reportingCurrency.value,
  ],
  render,
  { deep: true },
);
onBeforeUnmount(() => {
  themeObserver?.disconnect();
  chart?.destroy();
});
</script>

<template>
  <div class="monthly-variation-chart">
    <canvas
      ref="canvas"
      role="img"
      :aria-label="t('shared.monthlyVariationChart.chartAria', { label })"
    />
    <div
      class="month-selectors"
      :aria-label="t('shared.monthlyVariationChart.selectMonthAria')"
    >
      <button
        v-for="(item, index) in labels"
        :key="`${item}:${index}`"
        type="button"
        :aria-pressed="selectedIndex === index"
        @click="emit('select', index)"
      >
        {{ item }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.monthly-variation-chart canvas {
  cursor: pointer;
}
.month-selectors {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
