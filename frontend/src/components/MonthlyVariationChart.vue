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
import ChartHoverDetail, { type ChartHoverData } from "./ChartHoverDetail.vue";

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);

export interface MonthlyVariationSeries {
  key: "savings" | "interest" | "pnl";
  label: string;
  values: number[];
}

const props = defineProps<{
  labels: string[];
  values: number[];
  series: MonthlyVariationSeries[];
  label: string;
  selectedIndex: number;
  selectedMonth: string;
}>();
const emit = defineEmits<{ select: [index: number] }>();
const { locale, t } = useI18n();
const canvas = ref<HTMLCanvasElement>();
const hoverDetail = ref<ChartHoverData | null>(null);
let chart: Chart<"bar", number[], string> | null = null;
let themeObserver: MutationObserver | null = null;
let selectionAccent = "";
let zeroLineColor = "";
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
const axisRange = computed(() => {
  let min = 0;
  let max = 0;
  // Chart.js stacks gains and losses on opposite sides of zero.
  for (const index of props.labels.keys()) {
    let losses = 0;
    let gains = 0;
    for (const { values } of props.series) {
      const value = values[index];
      if (value < 0) losses += value;
      else gains += value;
    }
    min = Math.min(min, losses);
    max = Math.max(max, gains);
  }
  return { min, max: min === max ? 1 : max };
});
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
  hoverDetail.value = null;
  if (!canvas.value) return;

  const styles = getComputedStyle(canvas.value);
  const colors = {
    savings: styles.getPropertyValue("--monthly-savings").trim() || "#148a62",
    interest: styles.getPropertyValue("--monthly-interest").trim() || "#d08a32",
    pnl: styles.getPropertyValue("--monthly-pnl").trim() || "#8870c5",
  };
  selectionAccent = colors.savings;
  const muted = styles.getPropertyValue("--fz-muted").trim() || "#8fa49a";
  zeroLineColor = muted;
  const grid =
    styles.getPropertyValue("--fz-chart-grid").trim() ||
    "rgba(143,164,154,.15)";
  const money = new Intl.NumberFormat(locale.value, {
    style: "currency",
    currency: reportingCurrency.value,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });

  const config: ChartConfiguration<"bar", number[], string> = {
    type: "bar",
    data: {
      labels: props.labels,
      datasets: props.series.map(({ key, label, values }) => ({
        label,
        data: values,
        backgroundColor: values.map((_value, index) =>
          index === props.selectedIndex ? colors[key] : `${colors[key]}a6`,
        ),
        hoverBackgroundColor: colors[key],
        borderRadius: 4,
        borderSkipped: "middle",
        maxBarThickness: 44,
      })),
    },
    plugins: [
      {
        id: "monthlyChartGuides",
        beforeDatasetsDraw({ chartArea, ctx, scales }) {
          if (scales.y.ticks.some(({ value }) => value === 0)) return;
          const y = scales.y.getPixelForValue(0);
          ctx.save();
          ctx.strokeStyle = zeroLineColor;
          ctx.beginPath();
          ctx.moveTo(chartArea.left, y);
          ctx.lineTo(chartArea.right, y);
          ctx.stroke();
          ctx.restore();
        },
        afterDatasetsDraw({ chartArea, ctx, scales }) {
          if (
            props.series.some(({ values }) => values[props.selectedIndex] !== 0)
          )
            return;
          const x = scales.x.getPixelForValue(props.selectedIndex);
          const y = Math.max(
            chartArea.top + 3,
            Math.min(chartArea.bottom - 3, scales.y.getPixelForValue(0)),
          );
          ctx.save();
          ctx.fillStyle = selectionAccent;
          ctx.beginPath();
          ctx.arc(x, y, 2.5, 0, 2 * Math.PI);
          ctx.fill();
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
          enabled: false,
          filter: (context) =>
            context.dataIndex !== props.selectedIndex && context.parsed.y !== 0,
          external: ({ tooltip }) => {
            hoverDetail.value =
              tooltip.opacity && tooltip.dataPoints.length
                ? {
                    x: tooltip.x,
                    y: tooltip.y,
                    title: tooltip.title.join(" · "),
                    rows: tooltip.dataPoints.map((point) => ({
                      label: point.dataset.label ?? "",
                      value: signedAmount(Number(point.parsed.y)),
                      color: String(point.dataset.hoverBackgroundColor),
                    })),
                  }
                : null;
          },
        },
      },
      scales: {
        x: {
          stacked: true,
          border: { display: false },
          grid: { display: false },
          ticks: {
            color: ({ tick }) =>
              tick.value === props.selectedIndex ? selectionAccent : muted,
            maxTicksLimit: 10,
            maxRotation: 0,
            font: { size: 10, weight: 600 },
          },
        },
        y: {
          stacked: true,
          bounds: "ticks",
          min: axisRange.value.min,
          max: axisRange.value.max,
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
            autoSkip: false,
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
    props.series,
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
    <ChartHoverDetail
      v-if="hoverDetail"
      :detail="hoverDetail"
      aria-hidden="true"
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
