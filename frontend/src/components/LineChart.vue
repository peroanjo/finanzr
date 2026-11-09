<script setup lang="ts">
import {
  CategoryScale,
  type ScriptableContext,
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
import { reportingCurrency } from "../i18n";

export interface LineChartSeries {
  key: string;
  label: string;
  color: string;
  values: number[];
}

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
  labels: string[];
  values: number[];
  series?: LineChartSeries[];
  totalLabel?: string;
  ariaLabel?: string;
  ambient?: boolean;
}>();
const { locale, t } = useI18n();
const canvas = ref<HTMLCanvasElement>();
let chart: Chart | null = null;
let themeObserver: MutationObserver | null = null;

function render() {
  chart?.destroy();
  if (!canvas.value) return;
  const styles = getComputedStyle(canvas.value);
  const muted = styles.getPropertyValue("--fz-muted").trim() || "#8fa49a";
  const grid =
    styles.getPropertyValue("--fz-chart-grid").trim() ||
    "rgba(143,164,154,.15)";
  const tooltip = styles.getPropertyValue("--fz-tooltip").trim() || "#101e18";
  const tooltipText =
    styles.getPropertyValue("--fz-tooltip-text").trim() || "#edf3ef";
  const ink = styles.getPropertyValue("--fz-ink").trim() || "#152019";
  const totalLine =
    (props.ambient
      ? styles.getPropertyValue("--fz-accent").trim()
      : styles.getPropertyValue("--fz-chart-total-line").trim()) || ink;
  const areaOpacity =
    Number.parseFloat(
      styles.getPropertyValue("--fz-chart-composition-opacity").trim(),
    ) || 0.16;
  const surface = styles.getPropertyValue("--fz-surface").trim() || "#ffffff";
  const resolveColor = (value: string) => {
    const match = value.match(/^var\((--fz-[\w-]+)\)$/);
    return match ? styles.getPropertyValue(match[1]).trim() || value : value;
  };
  const withAlpha = (color: string, alpha: number) => {
    if (/^#[\da-f]{6}$/i.test(color)) {
      return `${color}${Math.round(alpha * 255)
        .toString(16)
        .padStart(2, "0")}`;
    }
    const rgb = color.match(/^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$/i);
    return rgb ? `rgba(${rgb[1]}, ${rgb[2]}, ${rgb[3]}, ${alpha})` : color;
  };
  const gradientFill =
    (color: string, opacity: number) =>
    (context: ScriptableContext<"line">) => {
      const { ctx, chartArea } = context.chart;
      if (!chartArea) return withAlpha(color, 0);
      const gradient = ctx.createLinearGradient(
        0,
        chartArea.top,
        0,
        chartArea.bottom,
      );
      gradient.addColorStop(0, withAlpha(color, opacity));
      gradient.addColorStop(0.65, withAlpha(color, opacity * 0.3));
      gradient.addColorStop(1, withAlpha(color, 0));
      return gradient;
    };
  const money = new Intl.NumberFormat(locale.value, {
    style: "currency",
    currency: reportingCurrency.value,
    maximumFractionDigits: 0,
  });

  chart = new Chart(canvas.value, {
    type: "line",
    data: {
      labels: props.labels,
      datasets: [
        {
          label: props.totalLabel,
          data: props.values,
          borderColor: totalLine,
          backgroundColor: props.ambient
            ? gradientFill(totalLine, 0.22)
            : totalLine,
          borderWidth: props.ambient ? 2.25 : 3.75,
          fill: props.ambient ? "origin" : false,
          tension: 0.24,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: totalLine,
          pointHoverBorderColor: surface,
          pointHoverBorderWidth: 2,
          stack: "total",
          order: props.ambient ? 0 : 20,
        },
        ...(props.series ?? []).map((item) => {
          const color = resolveColor(item.color);
          return {
            label: item.label,
            data: item.values,
            borderColor: color,
            backgroundColor: props.ambient
              ? gradientFill(color, 0.12)
              : withAlpha(color, areaOpacity),
            borderWidth: 1.5,
            fill: true,
            tension: 0.24,
            pointRadius: 0,
            pointHoverRadius: 3,
            pointHoverBackgroundColor: color,
            pointHoverBorderColor: surface,
            pointHoverBorderWidth: 2,
            stack: "composition",
            order: 10,
          };
        }),
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? 0
          : 350,
      },
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: tooltip,
          titleColor: tooltipText,
          bodyColor: tooltipText,
          padding: 12,
          displayColors: true,
          boxWidth: 8,
          boxHeight: 8,
          boxPadding: 5,
          callbacks: {
            label: (context) =>
              `${context.dataset.label}: ${money.format(Number(context.parsed.y))}`,
          },
        },
      },
      scales: {
        x: {
          border: { display: false },
          grid: { display: false },
          ticks: {
            color: muted,
            maxTicksLimit: 6,
            maxRotation: 0,
            font: { size: 10, weight: 600 },
          },
        },
        y: {
          display: !props.ambient,
          stacked: true,
          border: { display: false },
          grid: { color: grid },
          ticks: {
            color: muted,
            maxTicksLimit: 4,
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
    props.series,
    props.totalLabel,
    props.ambient,
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
  <div class="line-chart">
    <canvas
      ref="canvas"
      role="img"
      :aria-label="ariaLabel || t('shared.lineChart.aria')"
    />
  </div>
</template>
