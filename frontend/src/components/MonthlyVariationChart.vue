<script setup lang="ts">
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  LinearScale,
  Tooltip,
  type ChartConfiguration,
} from "chart.js";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { reportingCurrency } from "../i18n";

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);

const props = defineProps<{
  labels: string[];
  values: number[];
  label: string;
  range: { min: number; max: number };
  selectedIndex: number;
  selectedMonth: string;
}>();
const emit = defineEmits<{ select: [index: number] }>();
const { locale, t } = useI18n();
const canvas = ref<HTMLCanvasElement>();
let chart: Chart<"bar", number[], string> | null = null;
let themeObserver: MutationObserver | null = null;
let selectionTint = "";
let activePointer: {
  id: number;
  x: number;
  y: number;
  scrubbing: boolean;
} | null = null;

const currency = computed(
  () =>
    new Intl.NumberFormat(locale.value, {
      style: "currency",
      currency: reportingCurrency.value,
    }),
);
function signedAmount(value: number) {
  return `${value >= 0 ? "+" : "−"}${currency.value.format(Math.abs(value))}`;
}

function selectMonth(index: number) {
  const next = Math.max(0, Math.min(index, props.values.length - 1));
  if (props.values.length && next !== props.selectedIndex) emit("select", next);
}

function selectAtPointer(event: PointerEvent) {
  if (!chart || !canvas.value) return;
  const bounds = canvas.value.getBoundingClientRect();
  if (!bounds.width) return;
  const x = ((event.clientX - bounds.left) * chart.width) / bounds.width;
  const index = chart.scales.x.getValueForPixel(x);
  if (index !== undefined) selectMonth(index);
}

function startScrub(event: PointerEvent) {
  if (!event.isPrimary || event.button !== 0 || activePointer) return;
  activePointer = {
    id: event.pointerId,
    x: event.clientX,
    y: event.clientY,
    scrubbing: event.pointerType !== "touch",
  };
  canvas.value?.setPointerCapture?.(event.pointerId);
  if (activePointer.scrubbing) selectAtPointer(event);
}

function moveScrub(event: PointerEvent) {
  if (activePointer?.id !== event.pointerId) return;
  if (!activePointer.scrubbing) {
    const distanceX = Math.abs(event.clientX - activePointer.x);
    const distanceY = Math.abs(event.clientY - activePointer.y);
    if (distanceX < 6 || distanceX <= distanceY) return;
    activePointer.scrubbing = true;
  }
  selectAtPointer(event);
}

function finishScrub(event: PointerEvent) {
  if (activePointer?.id !== event.pointerId) return;
  const distance = Math.hypot(
    event.clientX - activePointer.x,
    event.clientY - activePointer.y,
  );
  if (activePointer.scrubbing || distance < 6) selectAtPointer(event);
  activePointer = null;
}

function cancelScrub(event: PointerEvent) {
  if (activePointer?.id === event.pointerId) activePointer = null;
}

function render() {
  if (!canvas.value) return;

  const styles = getComputedStyle(canvas.value);
  const accent = styles.getPropertyValue("--fz-accent").trim() || "#3ddc97";
  const negative = styles.getPropertyValue("--fz-negative").trim() || "#c95151";
  const muted = styles.getPropertyValue("--fz-muted").trim() || "#8fa49a";
  const grid =
    styles.getPropertyValue("--fz-chart-grid").trim() ||
    "rgba(143,164,154,.15)";
  selectionTint = grid;
  const tooltip = styles.getPropertyValue("--fz-tooltip").trim() || "#101e18";
  const tooltipText =
    styles.getPropertyValue("--fz-tooltip-text").trim() || "#edf3ef";
  const money = new Intl.NumberFormat(locale.value, {
    style: "currency",
    currency: reportingCurrency.value,
    maximumFractionDigits: props.range.max - props.range.min < 10 ? 2 : 0,
  });

  const config: ChartConfiguration<"bar", number[], string> = {
    type: "bar",
    data: {
      labels: props.labels,
      datasets: [
        {
          label: props.label,
          data: props.values,
          backgroundColor: props.values.map((value, index) => {
            const color = value >= 0 ? accent : negative;
            return `${color}${index === props.selectedIndex ? "f2" : "80"}`;
          }),
          hoverBackgroundColor: props.values.map((value) =>
            value >= 0 ? accent : negative,
          ),
          borderColor: props.values.map((value) =>
            value >= 0 ? accent : negative,
          ),
          borderWidth: props.values.map((_value, index) =>
            index === props.selectedIndex ? 1.5 : 0,
          ),
          borderRadius: 6,
          borderSkipped: false,
          maxBarThickness: 44,
        },
      ],
    },
    plugins: [
      {
        id: "monthlySelectionGuide",
        beforeDatasetsDraw(instance) {
          const { chartArea, ctx } = instance;
          const x = instance.scales.x.getPixelForValue(props.selectedIndex);
          const halfWidth = Math.min(
            30,
            chartArea.width / props.labels.length / 2,
          );
          const left = Math.max(chartArea.left, x - halfWidth);
          const right = Math.min(chartArea.right, x + halfWidth);
          ctx.save();
          ctx.fillStyle = selectionTint;
          ctx.fillRect(left, chartArea.top, right - left, chartArea.height);
          ctx.restore();
        },
      },
    ],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      events: ["mousemove", "mouseout"],
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: tooltip,
          titleColor: tooltipText,
          bodyColor: tooltipText,
          padding: 12,
          displayColors: false,
          callbacks: {
            label: (context) => signedAmount(Number(context.parsed.y)),
          },
        },
      },
      scales: {
        x: {
          border: { display: false },
          grid: { display: false },
          ticks: {
            color: muted,
            maxTicksLimit: 10,
            maxRotation: 0,
            font: { size: 10, weight: 600 },
          },
        },
        y: {
          beginAtZero: true,
          suggestedMin: props.range.min,
          suggestedMax: props.range.max,
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
  };
  if (chart) {
    chart.data = config.data;
    chart.options = config.options ?? {};
    chart.update("none");
  } else {
    chart = new Chart(canvas.value, config);
  }
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
    props.range,
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
  <div
    class="monthly-variation-chart"
    role="slider"
    tabindex="0"
    :aria-label="t('shared.monthlyVariationChart.chartAria', { label })"
    :aria-valuemin="1"
    :aria-valuemax="labels.length"
    :aria-valuenow="selectedIndex + 1"
    :aria-valuetext="`${selectedMonth} · ${signedAmount(values[selectedIndex])}`"
    @keydown.left.prevent="selectMonth(selectedIndex - 1)"
    @keydown.down.prevent="selectMonth(selectedIndex - 1)"
    @keydown.right.prevent="selectMonth(selectedIndex + 1)"
    @keydown.up.prevent="selectMonth(selectedIndex + 1)"
    @keydown.home.prevent="selectMonth(0)"
    @keydown.end.prevent="selectMonth(labels.length - 1)"
  >
    <canvas
      ref="canvas"
      aria-hidden="true"
      @pointerdown="startScrub"
      @pointermove="moveScrub"
      @pointerup="finishScrub"
      @pointercancel="cancelScrub"
      @lostpointercapture="cancelScrub"
    />
  </div>
</template>

<style scoped>
.monthly-variation-chart canvas {
  cursor: crosshair;
  touch-action: pan-y pinch-zoom;
}
.monthly-variation-chart:focus-visible {
  outline: 3px solid var(--fz-accent);
  outline-offset: 4px;
}
</style>
