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
  featured?: boolean;
}>();
const { locale, t } = useI18n();
const canvas = ref<HTMLCanvasElement>();
const hoverDetail = ref<{
  x: number;
  y: number;
  title: string;
  rows: Array<{ label: string; value: string; color: string }>;
} | null>(null);
let chart: Chart | null = null;
let themeObserver: MutationObserver | null = null;

function render() {
  chart?.destroy();
  hoverDetail.value = null;
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
    (props.featured
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
          backgroundColor: props.featured
            ? gradientFill(totalLine, 0.12)
            : totalLine,
          borderWidth: props.featured ? 2.5 : 3.75,
          fill: props.featured ? "origin" : false,
          tension: 0.24,
          pointRadius: (context) =>
            props.featured && context.dataIndex === props.values.length - 1
              ? 3.5
              : 0,
          pointBackgroundColor: totalLine,
          pointBorderColor: surface,
          pointBorderWidth: 2,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: totalLine,
          pointHoverBorderColor: surface,
          pointHoverBorderWidth: 2,
          stack: "total",
          order: props.featured ? 0 : 20,
        },
        ...(props.series ?? []).map((item) => {
          const color = resolveColor(item.color);
          return {
            label: item.label,
            data: item.values,
            borderColor: color,
            backgroundColor: props.featured
              ? color
              : withAlpha(color, areaOpacity),
            borderWidth: 1.5,
            fill: !props.featured,
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
      layout: {
        padding: {
          left: 0,
          right: props.featured ? 6 : 0,
        },
      },
      animation: {
        duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? 0
          : 350,
      },
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: !props.featured,
          external: props.featured
            ? ({ tooltip: model }) => {
                hoverDetail.value = model.opacity
                  ? {
                      x: model.x,
                      y: model.y,
                      title: model.title?.join(" · ") ?? "",
                      rows: model.dataPoints.map((point) => ({
                        label: point.dataset.label ?? "",
                        value: money.format(Number(point.parsed.y)),
                        color: String(point.dataset.borderColor),
                      })),
                    }
                  : null;
              }
            : undefined,
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
            align: props.featured ? "inner" : "center",
            autoSkip: !props.featured,
            callback: props.featured
              ? function (_value, index) {
                  const last = props.labels.length - 1;
                  const intervals = this.chart.width < 480 ? 2 : 4;
                  const visible = new Set(
                    Array.from({ length: intervals + 1 }, (_, step) =>
                      Math.round((step * last) / intervals),
                    ),
                  );
                  return visible.has(index) ? props.labels[index] : null;
                }
              : undefined,
            maxTicksLimit: 6,
            maxRotation: 0,
            font: { size: 10, weight: 600 },
          },
        },
        y: {
          display: true,
          stacked: !props.featured,
          bounds: props.featured ? "data" : "ticks",
          grace: props.featured ? "8%" : 0,
          beginAtZero: props.featured,
          border: { display: false },
          grid: { color: grid },
          ticks: {
            color: muted,
            maxTicksLimit: 4,
            includeBounds: !props.featured,
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
    props.featured,
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
    <div
      v-if="featured && hoverDetail"
      class="line-chart-hover"
      :style="{
        left: `clamp(0px, ${hoverDetail.x}px, max(0px, calc(100% - 340px)))`,
        top: `clamp(0px, ${hoverDetail.y}px, max(0px, calc(100% - ${44 + hoverDetail.rows.length * 20}px)))`,
      }"
    >
      <strong>{{ hoverDetail.title }}</strong>
      <div
        v-for="row in hoverDetail.rows"
        :key="row.label"
        class="line-chart-hover-row"
      >
        <i :style="{ background: row.color }" aria-hidden="true" />
        <span
          >{{ row.label }}: <b>{{ row.value }}</b></span
        >
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-chart {
  position: relative;
}
.line-chart-hover {
  position: absolute;
  z-index: 4;
  width: min(340px, 100%);
  padding: 12px;
  border-radius: 8px;
  background: var(--fz-tooltip);
  color: var(--fz-tooltip-text);
  box-shadow: 0 6px 24px var(--fz-chart-tooltip-shadow);
  font-size: 12px;
  line-height: 20px;
  pointer-events: none;
}
.line-chart-hover > strong {
  display: block;
  margin-bottom: 4px;
}
.line-chart-hover-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.line-chart-hover-row i {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  border-radius: 2px;
}
.line-chart-hover-row span {
  overflow-wrap: anywhere;
}
.line-chart-hover-row b {
  font-weight: 600;
}
</style>
