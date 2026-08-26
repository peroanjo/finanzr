<script setup lang="ts">
import {
  CategoryScale,
  Chart,
  Filler,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from "chart.js";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { FxRateChartPoint } from "../types/api";

Chart.register(
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
  CategoryScale,
  Filler,
);

const props = defineProps<{
  points: FxRateChartPoint[];
  fromCurrency: string;
  toCurrency: string;
}>();

const { locale, t } = useI18n();
const canvas = ref<HTMLCanvasElement>();
let chart: Chart | null = null;
let themeObserver: MutationObserver | null = null;

function dateLabel(value: string) {
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat(locale.value, {
        day: "2-digit",
        month: "short",
        year: "numeric",
      }).format(parsed);
}

function formatRate(value: number) {
  return new Intl.NumberFormat(locale.value, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  }).format(value);
}

function render() {
  chart?.destroy();
  if (!canvas.value || !props.points.length) return;
  const styles = getComputedStyle(canvas.value);
  const accent = styles.getPropertyValue("--fz-accent").trim() || "#3ddc97";
  const muted = styles.getPropertyValue("--fz-muted").trim() || "#8fa49a";
  const grid =
    styles.getPropertyValue("--fz-chart-grid").trim() ||
    "rgba(143,164,154,.15)";
  const tooltip =
    styles.getPropertyValue("--fz-chart-tooltip").trim() || "#101e18";
  const tooltipText =
    styles.getPropertyValue("--fz-chart-tooltip-text").trim() || "#edf3ef";
  const labels = props.points.map((point) => point.fecha);

  chart = new Chart(canvas.value, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: `${props.fromCurrency}/${props.toCurrency}`,
          data: props.points.map((point) => point.rate),
          borderColor: accent,
          backgroundColor: `${accent}1c`,
          borderWidth: 2.4,
          fill: true,
          tension: 0.2,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: accent,
          pointHoverBorderColor: tooltip,
          pointHoverBorderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
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
            title: (items) => dateLabel(items[0]?.label ?? ""),
            label: (context) =>
              t("currencies.chart.rateValue", {
                from: props.fromCurrency,
                rate: formatRate(Number(context.parsed.y)),
                to: props.toCurrency,
              }),
          },
        },
      },
      scales: {
        x: {
          border: { display: false },
          grid: { display: false },
          ticks: {
            color: muted,
            maxTicksLimit: 7,
            maxRotation: 0,
            font: { size: 10, weight: 600 },
          },
        },
        y: {
          border: { display: false },
          grid: { color: grid },
          ticks: {
            color: muted,
            maxTicksLimit: 5,
            callback: (value) => formatRate(Number(value)),
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
  () => [props.points, props.fromCurrency, props.toCurrency, locale.value],
  render,
  { deep: true },
);
onBeforeUnmount(() => {
  themeObserver?.disconnect();
  chart?.destroy();
});
</script>

<template>
  <div class="currency-rate-chart">
    <canvas
      ref="canvas"
      role="img"
      :aria-label="
        t('currencies.chart.aria', { from: fromCurrency, to: toCurrency })
      "
    />
  </div>
</template>

<style scoped>
.currency-rate-chart {
  position: relative;
  width: 100%;
  height: 320px;
}

@media (max-width: 768px) {
  .currency-rate-chart {
    height: 260px;
  }
}
</style>
