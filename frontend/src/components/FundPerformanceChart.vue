<script setup lang="ts">
import {
  CategoryScale,
  Chart,
  Filler,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from "chart.js";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { reportingCurrency } from "../i18n";
import type { FundPerformancePoint, StockPerformancePoint } from "../types/api";

Chart.register(
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
  CategoryScale,
  Filler,
  Legend,
);

const props = defineProps<{
  points: Array<FundPerformancePoint | StockPerformancePoint>;
  mode: "value" | "return";
}>();
const { locale, t } = useI18n();
const canvas = ref<HTMLCanvasElement>();
let chart: Chart | null = null;
let themeObserver: MutationObserver | null = null;

const rebasedReturns = computed(() => {
  const first = props.points[0];
  if (!first) return [];
  const base = 1 + first.pnl_pct / 100;
  return props.points.map(
    (point) => ((1 + point.pnl_pct / 100) / base - 1) * 100,
  );
});

function render() {
  chart?.destroy();
  if (!canvas.value || props.points.length < 2) return;
  const styles = getComputedStyle(canvas.value);
  const accent = styles.getPropertyValue("--fz-accent").trim() || "#3ddc97";
  const muted = styles.getPropertyValue("--fz-muted").trim() || "#8fa49a";
  const grid =
    styles.getPropertyValue("--fz-chart-grid").trim() ||
    "rgba(143,164,154,.15)";
  const negative = styles.getPropertyValue("--fz-negative").trim() || "#c95151";
  const tooltip =
    styles.getPropertyValue("--fz-chart-tooltip").trim() || "rgba(18,27,22,.9)";
  const tooltipText =
    styles.getPropertyValue("--fz-chart-tooltip-text").trim() || "#edf3ef";
  const tooltipMuted =
    styles.getPropertyValue("--fz-chart-tooltip-muted").trim() || "#a5b2aa";
  const labels = props.points.map((point) => point.fecha);
  const money = new Intl.NumberFormat(locale.value, {
    style: "currency",
    currency: reportingCurrency.value,
    maximumFractionDigits: 0,
  });
  const dates = new Intl.DateTimeFormat(locale.value, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
  const percentages = new Intl.NumberFormat(locale.value, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const isReturn = props.mode === "return";
  const returnValues = rebasedReturns.value;
  const lastReturn = returnValues.at(-1) ?? 0;
  const lineColor = lastReturn >= 0 ? accent : negative;
  const datasets = isReturn
    ? [
        {
          label: t("shared.fundPerformance.return"),
          data: returnValues,
          borderColor: lineColor,
          backgroundColor: `${lineColor}1f`,
          borderWidth: 2.5,
          fill: true,
          tension: 0.28,
          pointRadius: 0,
          pointHoverRadius: 4,
        },
      ]
    : [
        {
          label: t("shared.fundPerformance.portfolioValue"),
          data: props.points.map((point) => point.valor),
          borderColor: accent,
          backgroundColor: `${accent}20`,
          borderWidth: 2.5,
          fill: true,
          tension: 0.28,
          pointRadius: 0,
          pointHoverRadius: 4,
        },
        {
          label: t("shared.fundPerformance.contributedCapital"),
          data: props.points.map((point) => point.invertido),
          borderColor: muted,
          backgroundColor: "transparent",
          borderWidth: 1.5,
          borderDash: [5, 5],
          fill: false,
          tension: 0,
          pointRadius: 0,
          pointHoverRadius: 3,
        },
      ];

  chart = new Chart(canvas.value, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: {
          display: !isReturn,
          position: "bottom",
          align: "start",
          labels: {
            color: muted,
            boxWidth: 18,
            boxHeight: 2,
            padding: 18,
            font: { size: 10, weight: 600 },
          },
        },
        tooltip: {
          backgroundColor: tooltip,
          titleColor: tooltipText,
          bodyColor: tooltipText,
          borderColor: `${muted}40`,
          borderWidth: 1,
          padding: 12,
          displayColors: !isReturn,
          callbacks: {
            title: (items) => {
              const raw = items[0]?.label;
              return raw ? dates.format(new Date(`${raw}T00:00:00`)) : "";
            },
            label: (context) =>
              isReturn
                ? ` ${t("shared.fundPerformance.returnValue", {
                    value: `${Number(context.parsed.y) >= 0 ? "+" : ""}${percentages.format(Number(context.parsed.y))} %`,
                  })}`
                : ` ${context.dataset.label}: ${money.format(Number(context.parsed.y))}`,
            afterBody: (items) => {
              const index = items[0]?.dataIndex;
              if (index == null) return [];
              const point = props.points[index];
              return [
                t("shared.fundPerformance.pnl", {
                  value: `${point.pnl >= 0 ? "+" : "−"}${money.format(Math.abs(point.pnl))}`,
                }),
              ];
            },
          },
          footerColor: tooltipMuted,
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
            callback: (_value, index) => {
              const [year, month] = labels[index]?.split("-") ?? [];
              if (!year || !month) return "";
              return (
                new Intl.DateTimeFormat(locale.value, { month: "short" })
                  .format(new Date(Number(year), Number(month) - 1, 1))
                  .replace(".", "") + ` '${year.slice(2)}`
              );
            },
            font: { size: 10, weight: 600 },
          },
        },
        y: {
          border: { display: false },
          grid: { color: grid },
          ticks: {
            color: muted,
            maxTicksLimit: 5,
            callback: (value) =>
              isReturn
                ? `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(1)} %`
                : money.format(Number(value)),
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
  () => [props.points, props.mode, locale.value, reportingCurrency.value],
  render,
  { deep: true },
);
onBeforeUnmount(() => {
  themeObserver?.disconnect();
  chart?.destroy();
});
</script>

<template>
  <div class="fund-performance-chart">
    <canvas
      ref="canvas"
      role="img"
      :aria-label="t('shared.fundPerformance.chartAria')"
    />
  </div>
</template>

<style scoped>
.fund-performance-chart {
  position: relative;
  width: 100%;
  height: 330px;
}
@media (max-width: 720px) {
  .fund-performance-chart {
    height: 285px;
  }
}
</style>
