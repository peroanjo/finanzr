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

const seriesOrder = ["savings", "interest", "pnl"] as const;
export interface MonthlyVariationSeries {
  key: string;
  label: string;
  values: number[];
  color?: string;
}

type AxisRange = { min: number; max: number };
type AnimatedSeries = {
  series: MonthlyVariationSeries;
  amount: number;
  fromAmount: number;
  toAmount: number;
  average: number;
};
const transitionDuration = 340;

const props = defineProps<{
  labels: string[];
  values: number[];
  series: MonthlyVariationSeries[];
  label: string;
  selectedIndex: number;
  selectedMonth: string;
  showTooltip?: boolean;
}>();
const emit = defineEmits<{
  select: [index: number];
  preview: [index: number | null];
}>();
const { locale, t } = useI18n();
const canvas = ref<HTMLCanvasElement>();
let chart: Chart<"bar", number[], string> | null = null;
let themeObserver: MutationObserver | null = null;
let selectionAccent = "";
let zeroLineColor = "";
let averageStyle = { line: "", ink: "", font: "" };
let animationFrame: number | null = null;
let seriesTransition: {
  tracks: AnimatedSeries[];
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
      signDisplay: "negative",
    }),
);
function mean(values: number[]) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}
const monthlyAverage = computed(() =>
  props.values.length ? mean(props.values) : null,
);
function averageLabel(value: number) {
  return t("shared.monthlyVariationChart.average", {
    amount: currency.value.format(value),
  });
}

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

function stopSeriesTransition() {
  if (animationFrame !== null) window.cancelAnimationFrame(animationFrame);
  animationFrame = null;
  seriesTransition = null;
}

function animatedValues({ series, amount }: AnimatedSeries) {
  return amount === 1
    ? series.values
    : series.values.map((value) => value * amount);
}

function animateSeries(previousSeries: MonthlyVariationSeries[]) {
  const instance = chart;
  const previous = seriesTransition;
  stopSeriesTransition();
  if (
    !instance ||
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  ) {
    render();
    return;
  }

  const keys = new Set([
    ...seriesOrder,
    ...previousSeries.map(({ key }) => key),
    ...(previous?.tracks.map(({ series }) => series.key) ?? []),
    ...props.series.map(({ key }) => key),
  ]);
  const tracks = [...keys].flatMap((key): AnimatedSeries[] => {
    const before = previousSeries.find((item) => item.key === key);
    const after = props.series.find((item) => item.key === key);
    const running = previous?.tracks.find(({ series }) => series.key === key);
    const series = after ?? running?.series ?? before;
    const fromAmount = running?.amount ?? (before ? 1 : 0);
    const toAmount = after ? 1 : 0;
    if (!series || (!fromAmount && !toAmount)) return [];
    return [
      {
        series,
        amount: fromAmount,
        fromAmount,
        toAmount,
        average: mean(series.values),
      },
    ];
  });
  if (
    tracks.every(
      ({ fromAmount, toAmount, series }) =>
        fromAmount === toAmount || series.values.every((value) => value === 0),
    )
  ) {
    render();
    return;
  }

  const fromRange =
    previous?.range ?? stackedRange(previousSeries, props.labels.length);
  const toRange = axisRange.value;
  const transition = { tracks, range: fromRange };
  seriesTransition = transition;
  render();

  const started = performance.now();
  const drawFrame = (now: number) => {
    const time = Math.max(0, (now - started) / transitionDuration);
    if (time >= 1) {
      stopSeriesTransition();
      render();
      return;
    }
    const progress = time * time * (3 - 2 * time);
    // Make room for growing stacks before tightening either end of the axis.
    const expand = 1 - (1 - progress) ** 2;
    const contract = progress ** 2;
    transition.range = {
      min:
        fromRange.min +
        (toRange.min - fromRange.min) *
          (toRange.min < fromRange.min ? expand : contract),
      max:
        fromRange.max +
        (toRange.max - fromRange.max) *
          (toRange.max > fromRange.max ? expand : contract),
    };
    for (const [index, track] of tracks.entries()) {
      track.amount =
        track.fromAmount + (track.toAmount - track.fromAmount) * progress;
      instance.data.datasets[index].data = animatedValues(track);
    }
    const y = instance.options.scales?.y;
    if (y) {
      y.min = transition.range.min;
      y.max = transition.range.max;
    }
    instance.update("none");
    animationFrame = window.requestAnimationFrame(drawFrame);
  };
  animationFrame = window.requestAnimationFrame(drawFrame);
}
function signedAmount(value: number) {
  return `${value >= 0 ? "+" : "−"}${currency.value.format(Math.abs(value))}`;
}

function selectMonth(index: number) {
  emit("preview", null);
  const next = Math.max(0, Math.min(index, props.values.length - 1));
  if (props.values.length && next !== props.selectedIndex) emit("select", next);
}

function monthAtPointer(event: PointerEvent, plotOnly = false) {
  if (!chart || !canvas.value) return;
  const bounds = canvas.value.getBoundingClientRect();
  if (!bounds.width) return;
  const x = ((event.clientX - bounds.left) * chart.width) / bounds.width;
  if (plotOnly) {
    const y = ((event.clientY - bounds.top) * chart.height) / bounds.height;
    const { left, right, top, bottom } = chart.chartArea;
    if (x < left || x > right || y < top || y > bottom) return;
  }
  return chart.scales.x.getValueForPixel(x);
}

function selectAtPointer(event: PointerEvent) {
  const index = monthAtPointer(event);
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

function movePointer(event: PointerEvent) {
  if (!activePointer) {
    if (event.pointerType === "mouse") {
      emit("preview", monthAtPointer(event, true) ?? null);
    }
    return;
  }
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

function drawMonthlyAverage({ chartArea, ctx, scales }: Chart<"bar">) {
  const average = monthlyAverage.value;
  if (average === null) return;

  const { left, right, top, bottom } = chartArea;
  // Keep the line aligned with the amounts currently drawn during the transition.
  const value =
    seriesTransition?.tracks.reduce(
      (total, track) => total + track.average * (track.amount - track.toAmount),
      average,
    ) ?? average;
  const pixel = scales.y.getPixelForValue(value);
  if (pixel < top - 1 || pixel > bottom + 1) return;
  const y = Math.max(top + 1, Math.min(bottom - 1, pixel));

  ctx.save();
  ctx.strokeStyle = averageStyle.line;
  ctx.lineWidth = 1.2;
  ctx.lineCap = "round";
  ctx.setLineDash([2, 4]);
  ctx.beginPath();
  ctx.moveTo(left, y);
  ctx.lineTo(right, y);
  ctx.stroke();

  const label = averageLabel(value);
  ctx.font = averageStyle.font;
  const labelWidth = Math.min(ctx.measureText(label).width, right - left - 28);
  if (labelWidth > 0) {
    const legendY = top - 14;
    const swatchEnd = right - labelWidth - 8;
    ctx.beginPath();
    ctx.moveTo(swatchEnd - 18, legendY);
    ctx.lineTo(swatchEnd, legendY);
    ctx.stroke();
    ctx.fillStyle = averageStyle.ink;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.fillText(label, right, legendY, labelWidth);
  }
  ctx.restore();
}

function render() {
  if (!canvas.value) return;

  const transition = seriesTransition;
  const series =
    transition?.tracks.map((track) => ({
      ...track.series,
      values: animatedValues(track),
    })) ?? props.series;
  const range = transition?.range ?? axisRange.value;

  const styles = getComputedStyle(canvas.value);
  averageStyle = {
    line: styles.getPropertyValue("--fz-chart-average").trim() || "#7d8790",
    ink: styles.getPropertyValue("--fz-ink").trim() || "#152019",
    font: `600 11px ${styles.fontFamily || "sans-serif"}`,
  };
  const colors: Record<string, string> = {
    savings: styles.getPropertyValue("--monthly-savings").trim() || "#148a62",
    interest: styles.getPropertyValue("--monthly-interest").trim() || "#d08a32",
    pnl: styles.getPropertyValue("--monthly-pnl").trim() || "#8870c5",
  };
  const negativeColors: Partial<typeof colors> = {
    savings:
      styles.getPropertyValue("--monthly-savings-negative").trim() || "#5479bd",
    pnl: styles.getPropertyValue("--monthly-pnl-negative").trim() || "#c95151",
  };
  const colorFor = (key: string, value: number) =>
    (value < 0 ? negativeColors[key] : undefined) ??
    colors[key] ??
    colors.interest;
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
      datasets: series.map(({ key, label, values, color }, index) => {
        const amounts = transition?.tracks[index].series.values ?? values;
        const seriesColor = color ? styles.getPropertyValue(color).trim() : "";
        const swatches = amounts.map(
          (value) => seriesColor || colorFor(key, value),
        );
        return {
          label,
          data: values,
          backgroundColor: swatches.map((color, index) =>
            index === props.selectedIndex ? color : `${color}a6`,
          ),
          hoverBackgroundColor: swatches,
          borderRadius: 4,
          borderSkipped: "start",
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
        afterDatasetsDraw(instance) {
          drawMonthlyAverage(instance);
          const { chartArea, ctx, data, scales } = instance;
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
      layout: { padding: { top: 18 } },
      events: ["mousemove", "mouseout"],
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: props.showTooltip ?? false,
          backgroundColor: styles.getPropertyValue("--fz-chart-tooltip").trim(),
          titleColor: styles.getPropertyValue("--fz-chart-tooltip-text").trim(),
          bodyColor: styles.getPropertyValue("--fz-chart-tooltip-text").trim(),
          callbacks: {
            label: ({ dataset, parsed }) =>
              `${dataset.label}: ${currency.value.format(parsed.y ?? 0)}`,
            footer: (items) =>
              t("shared.accountSnapshotChart.total", {
                value: currency.value.format(
                  items.reduce(
                    (total, item) => total + (item.parsed.y ?? 0),
                    0,
                  ),
                ),
              }),
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
              const movingRange = seriesTransition?.range;
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
  () => [props.labels, props.series, props.values] as const,
  ([labels, series], [previousLabels, previousSeries]) => {
    const visibilityChanged =
      series.length !== previousSeries.length ||
      series.some(
        ({ key }) => !previousSeries.some((item) => item.key === key),
      );
    if (labels === previousLabels && visibilityChanged) {
      animateSeries(previousSeries);
    } else {
      stopSeriesTransition();
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
  stopSeriesTransition();
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
    :aria-description="
      monthlyAverage === null ? undefined : averageLabel(monthlyAverage)
    "
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
      @pointermove="movePointer"
      @pointerleave="emit('preview', null)"
      @pointerup="finishScrub"
      @pointercancel="cancelScrub"
      @lostpointercapture="cancelScrub"
    />
  </div>
</template>

<style scoped>
.monthly-variation-chart canvas {
  max-width: 100%;
  max-height: 100%;
  cursor: crosshair;
  touch-action: pan-y pinch-zoom;
}
.monthly-variation-chart:focus-visible {
  outline: 3px solid var(--fz-accent);
  outline-offset: 4px;
}
</style>
