<script setup lang="ts">
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  Filler,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { reportingCurrency } from "../i18n";
import type { AccountChartSeries } from "../types/api";

Chart.register(
  BarController,
  BarElement,
  CategoryScale,
  Filler,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Tooltip,
);

const props = defineProps<{
  labels: string[];
  series: AccountChartSeries[];
  mode: "balance" | "interest" | "pnl";
  minimumFontSize?: number;
}>();
const { locale, t } = useI18n();
const canvas = ref<HTMLCanvasElement>();
let chart: Chart | null = null;
let themeObserver: MutationObserver | null = null;
function render() {
  chart?.destroy();
  if (!canvas.value || !props.labels.length) return;
  const styles = getComputedStyle(canvas.value);
  const muted = styles.getPropertyValue("--fz-muted").trim() || "#8fa49a";
  const grid =
    styles.getPropertyValue("--fz-chart-grid").trim() ||
    "rgba(143,164,154,.15)";
  const tooltip =
    styles.getPropertyValue("--fz-chart-tooltip").trim() ||
    "rgba(18,27,22,.92)";
  const tooltipText =
    styles.getPropertyValue("--fz-chart-tooltip-text").trim() || "#edf3ef";
  const chartFontSize = props.minimumFontSize ?? 9;
  const balanceMode = props.mode === "balance";
  const pnlMode = props.mode === "pnl";
  const money = new Intl.NumberFormat(locale.value, {
    style: "currency",
    currency: reportingCurrency.value,
    maximumFractionDigits: 2,
  });

  chart = new Chart(canvas.value, {
    type: balanceMode ? "line" : "bar",
    data: {
      labels: props.labels,
      datasets: props.series.map((item) => ({
        label: item.label,
        data: item.values,
        borderColor: item.color,
        backgroundColor: balanceMode ? `${item.color}30` : `${item.color}d8`,
        borderWidth: balanceMode ? 2 : 0,
        borderRadius: 0,
        borderSkipped: false,
        barPercentage: pnlMode ? 0.76 : 0.9,
        categoryPercentage: pnlMode ? 0.7 : 0.8,
        maxBarThickness: pnlMode ? 28 : undefined,
        fill: balanceMode,
        tension: 0.26,
        pointRadius: 0,
        pointHoverRadius: balanceMode ? 4 : 0,
        stack: "savings",
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: muted,
            boxWidth: 8,
            boxHeight: 8,
            padding: 15,
            usePointStyle: true,
            pointStyle: "circle",
            font: { size: chartFontSize, weight: 600 },
          },
        },
        tooltip: {
          backgroundColor: tooltip,
          titleColor: tooltipText,
          bodyColor: tooltipText,
          padding: 12,
          callbacks: {
            label: (context) =>
              ` ${context.dataset.label}: ${money.format(Number(context.parsed.y))}`,
            footer: (contexts) =>
              t("shared.accountSnapshotChart.total", {
                value: money.format(
                  contexts.reduce(
                    (total, context) => total + Number(context.parsed.y),
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
            color: muted,
            maxTicksLimit: 8,
            maxRotation: 0,
            font: { size: chartFontSize, weight: 600 },
          },
        },
        y: {
          stacked: true,
          beginAtZero: true,
          border: { display: false },
          grid: {
            color: (context) =>
              pnlMode && Number(context.tick.value) === 0 ? muted : grid,
            lineWidth: (context) =>
              pnlMode && Number(context.tick.value) === 0 ? 1.25 : 1,
          },
          ticks: {
            color: muted,
            maxTicksLimit: 5,
            callback: (value) => money.format(Number(value)),
            font: { size: chartFontSize, weight: 600 },
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
    props.series,
    props.mode,
    props.minimumFontSize,
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
  <div class="savings-chart">
    <canvas
      ref="canvas"
      role="img"
      :aria-label="
        t(
          mode === 'balance'
            ? 'shared.accountSnapshotChart.balanceAria'
            : mode === 'pnl'
              ? 'shared.accountSnapshotChart.pnlAria'
              : 'shared.accountSnapshotChart.interestAria',
        )
      "
    />
  </div>
</template>

<style scoped>
.savings-chart {
  position: relative;
  width: 100%;
  height: 290px;
}
@media (max-width: 720px) {
  .savings-chart {
    height: 250px;
  }
}
</style>
