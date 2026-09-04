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
import type { FundPosition } from "../types/api";

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);

const props = defineProps<{
  positions: FundPosition[];
  mode: "money" | "percent";
}>();
const { locale, t } = useI18n();
const canvas = ref<HTMLCanvasElement>();
let chart: Chart | null = null;
let themeObserver: MutationObserver | null = null;

function render() {
  chart?.destroy();
  if (!canvas.value || !props.positions.length) return;
  const styles = getComputedStyle(canvas.value);
  const accent = styles.getPropertyValue("--fz-accent").trim() || "#3ddc97";
  const negative = styles.getPropertyValue("--fz-negative").trim() || "#c95151";
  const muted = styles.getPropertyValue("--fz-muted").trim() || "#8fa49a";
  const grid =
    styles.getPropertyValue("--fz-chart-grid").trim() ||
    "rgba(143,164,154,.15)";
  const tooltip =
    styles.getPropertyValue("--fz-chart-tooltip").trim() || "rgba(18,27,22,.9)";
  const tooltipText =
    styles.getPropertyValue("--fz-chart-tooltip-text").trim() || "#edf3ef";
  const sorted = [...props.positions]
    .filter((item) => item.unrealized_pnl != null)
    .sort((a, b) =>
      props.mode === "percent"
        ? (b.return_percent ?? 0) - (a.return_percent ?? 0)
        : (b.unrealized_pnl ?? 0) - (a.unrealized_pnl ?? 0),
    );
  const values = sorted.map((item) =>
    props.mode === "percent"
      ? (item.return_percent ?? 0) * 100
      : (item.unrealized_pnl ?? 0),
  );
  const money = new Intl.NumberFormat(locale.value, {
    style: "currency",
    currency: reportingCurrency.value,
    maximumFractionDigits: 2,
  });
  const percentage = new Intl.NumberFormat(locale.value, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  chart = new Chart(canvas.value, {
    type: "bar",
    data: {
      labels: sorted.map((item) => item.name),
      datasets: [
        {
          data: values,
          backgroundColor: values.map((value) =>
            value >= 0 ? `${accent}d9` : `${negative}d9`,
          ),
          borderRadius: 5,
          borderSkipped: false,
          barThickness: 12,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: "nearest" },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: tooltip,
          titleColor: tooltipText,
          bodyColor: tooltipText,
          padding: 12,
          displayColors: false,
          callbacks: {
            title: (items) => sorted[items[0]?.dataIndex ?? 0]?.name ?? "",
            label: (context) => {
              const item = sorted[context.dataIndex];
              const pnl = item.unrealized_pnl ?? 0;
              const pnlPct = item.return_percent ?? 0;
              return [
                t("shared.fundPnl.pnl", {
                  value: `${pnl >= 0 ? "+" : "−"}${money.format(Math.abs(pnl))}`,
                }),
                t("shared.fundPnl.return", {
                  value: `${pnlPct >= 0 ? "+" : ""}${percentage.format(pnlPct * 100)} %`,
                }),
              ];
            },
          },
        },
      },
      scales: {
        x: {
          border: { display: false },
          grid: { color: grid },
          ticks: {
            color: muted,
            maxTicksLimit: 5,
            callback: (value) =>
              props.mode === "percent"
                ? `${Number(value).toFixed(0)} %`
                : money.format(Number(value)),
            font: { size: 10, weight: 600 },
          },
        },
        y: {
          border: { display: false },
          grid: { display: false },
          ticks: {
            color: muted,
            callback: (_value, index) => {
              const label = sorted[index]?.name ?? "";
              return label.length > 21 ? `${label.slice(0, 20)}…` : label;
            },
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
  () => [props.positions, props.mode, locale.value, reportingCurrency.value],
  render,
  { deep: true },
);
onBeforeUnmount(() => {
  themeObserver?.disconnect();
  chart?.destroy();
});
</script>

<template>
  <div class="fund-pnl-chart">
    <canvas
      ref="canvas"
      role="img"
      :aria-label="t('shared.fundPnl.chartAria')"
    />
  </div>
</template>

<style scoped>
.fund-pnl-chart {
  position: relative;
  width: 100%;
  height: 270px;
}
</style>
