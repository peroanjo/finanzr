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

type AxisRange = { min: number; max: number };
const pnlTransitionDuration = 340;

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
let pnlFrame: number | null = null;
let pnlTransition: {
  series: MonthlyVariationSeries;
  amount: number;
  range: AxisRange;
} | null = null;
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
function stackedRange(series: MonthlyVariationSeries[], monthCount: number) {
  let min = 0;
  let max = 0;
  // Chart.js stacks gains and losses on opposite sides of zero.
  for (let index = 0; index < monthCount; index++) {
    let losses = 0;
    let gains = 0;
    for (const { values } of series) {
      const value = values[index];
      if (value < 0) losses += value;
      else gains += value;
    }
    min = Math.min(min, losses);
    max = Math.max(max, gains);
  }
  return { min, max: min === max ? 1 : max };
}
const axisRange = computed(() =>
  stackedRange(props.series, props.labels.length),
);

function stopPnlTransition() {
  if (pnlFrame !== null) window.cancelAnimationFrame(pnlFrame);
  pnlFrame = null;
  pnlTransition = null;
}

function animatePnl(
  series: MonthlyVariationSeries,
  previousRange: AxisRange,
  include: boolean,
) {
  const instance = chart;
  const previous = pnlTransition;
  stopPnlTransition();
  if (
    !instance ||
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ||
    series.values.every((value) => value === 0)
  ) {
    render();
    return;
  }

  const fromAmount = previous?.amount ?? (include ? 0 : 1);
  const toAmount = include ? 1 : 0;
  const fromRange = previous?.range ?? previousRange;
  const toRange = axisRange.value;
  const transition = { series, amount: fromAmount, range: fromRange };
  pnlTransition = transition;
  render();

  const started = performance.now();
  const drawFrame = (now: number) => {
    const time = Math.max(0, (now - started) / pnlTransitionDuration);
    if (time >= 1) {
      stopPnlTransition();
      render();
      return;
    }
    const progress = time * time * (3 - 2 * time);
    // Expand the axis ahead of the growing bars and tighten it as they retract.
    const axisProgress = include ? 1 - (1 - time) ** 3 : time ** 3;
    transition.amount = fromAmount + (toAmount - fromAmount) * progress;
    transition.range = {
      min: fromRange.min + (toRange.min - fromRange.min) * axisProgress,
      max: fromRange.max + (toRange.max - fromRange.max) * axisProgress,
    };
    const dataset = instance.data.datasets[instance.data.datasets.length - 1];
    dataset.data = series.values.map((value) => value * transition.amount);
    const y = instance.options.scales?.y;
    if (y) {
      y.min = transition.range.min;
      y.max = transition.range.max;
    }
    instance.update("none");
    pnlFrame = window.requestAnimationFrame(drawFrame);
  };
  pnlFrame = window.requestAnimationFrame(drawFrame);
}
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

  const transition = pnlTransition;
  const series = transition
    ? [
        ...props.series.filter((item) => item.key !== "pnl"),
        {
          ...transition.series,
          values: transition.series.values.map(
            (value) => value * transition.amount,
          ),
        },
      ]
    : props.series;
  const range = transition?.range ?? axisRange.value;

  const styles = getComputedStyle(canvas.value);
  const colors = {
    savings: styles.getPropertyValue("--monthly-savings").trim() || "#148a62",
    interest: styles.getPropertyValue("--monthly-interest").trim() || "#d08a32",
    pnl: styles.getPropertyValue("--monthly-pnl").trim() || "#8870c5",
  };
  const negativeColors: Partial<typeof colors> = {
    savings:
      styles.getPropertyValue("--monthly-savings-negative").trim() || "#5479bd",
    pnl: styles.getPropertyValue("--monthly-pnl-negative").trim() || "#c95151",
  };
  const colorFor = (key: MonthlyVariationSeries["key"], value: number) =>
    value < 0 ? (negativeColors[key] ?? colors[key]) : colors[key];
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
      datasets: series.map(({ key, label, values }) => {
        const amounts =
          key === "pnl" && transition ? transition.series.values : values;
        const swatches = amounts.map((value) => colorFor(key, value));
        return {
          label,
          data: values,
          backgroundColor: swatches.map((color, index) =>
            index === props.selectedIndex ? color : `${color}a6`,
          ),
          hoverBackgroundColor: swatches,
          borderRadius: 4,
          borderSkipped: "middle",
          maxBarThickness: 44,
        };
      }),
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
        afterDatasetsDraw({ chartArea, ctx, data, scales }) {
          if (data.datasets.some(({ data }) => data[props.selectedIndex] !== 0))
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
            !pnlTransition &&
            context.dataIndex !== props.selectedIndex &&
            context.parsed.y !== 0,
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
                      color: colorFor(
                        series[point.datasetIndex].key,
                        Number(point.parsed.y),
                      ),
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
          min: range.min,
          max: range.max,
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
            callback: (value) => {
              const amount = Number(value);
              const movingRange = pnlTransition?.range;
              // Keep interim labels from shifting as fractional digits change.
              return money.format(
                movingRange && movingRange.max - movingRange.min >= 100
                  ? Math.round(amount)
                  : amount,
              );
            },
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
  () => [props.labels, props.series] as const,
  ([labels, series], [previousLabels, previousSeries]) => {
    const pnl = series.find((item) => item.key === "pnl");
    const previousPnl = previousSeries.find((item) => item.key === "pnl");
    const changedPnl = pnl ?? previousPnl;
    if (
      labels === previousLabels &&
      changedPnl &&
      Boolean(pnl) !== Boolean(previousPnl)
    ) {
      animatePnl(
        changedPnl,
        stackedRange(previousSeries, labels.length),
        Boolean(pnl),
      );
    } else {
      stopPnlTransition();
      render();
    }
  },
  { deep: true },
);
watch(
  () => [props.selectedIndex, locale.value, reportingCurrency.value],
  render,
);
onBeforeUnmount(() => {
  stopPnlTransition();
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
