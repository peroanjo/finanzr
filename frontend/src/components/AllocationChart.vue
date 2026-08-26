<script setup lang="ts">
import { ArcElement, Chart, DoughnutController, Tooltip } from "chart.js";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { reportingCurrency } from "../i18n";

export interface AllocationChartItem {
  label: string;
  value: number;
  color: string;
}

Chart.register(DoughnutController, ArcElement, Tooltip);

const props = defineProps<{ items: AllocationChartItem[] }>();
const { locale, t } = useI18n();
const canvas = ref<HTMLCanvasElement>();
const visibleItems = computed(() =>
  props.items.filter((item) => item.value > 0),
);
const total = computed(() =>
  visibleItems.value.reduce((sum, item) => sum + item.value, 0),
);
let chart: Chart<"doughnut"> | null = null;
let themeObserver: MutationObserver | null = null;

function render() {
  chart?.destroy();
  if (!canvas.value || !visibleItems.value.length) return;

  const styles = getComputedStyle(canvas.value);
  const surface = styles.getPropertyValue("--fz-surface").trim() || "#ffffff";
  const tooltip = styles.getPropertyValue("--fz-tooltip").trim() || "#101e18";
  const tooltipText =
    styles.getPropertyValue("--fz-tooltip-text").trim() || "#edf3ef";
  const resolveColor = (value: string) => {
    const match = value.match(/^var\((--fz-[\w-]+)\)$/);
    return match ? styles.getPropertyValue(match[1]).trim() || value : value;
  };
  const money = new Intl.NumberFormat(locale.value, {
    style: "currency",
    currency: reportingCurrency.value,
    maximumFractionDigits: 0,
  });
  const percentage = new Intl.NumberFormat(locale.value, {
    style: "percent",
    maximumFractionDigits: 1,
  });

  chart = new Chart(canvas.value, {
    type: "doughnut",
    data: {
      labels: visibleItems.value.map((item) => item.label),
      datasets: [
        {
          data: visibleItems.value.map((item) => item.value),
          backgroundColor: visibleItems.value.map((item) =>
            resolveColor(item.color),
          ),
          borderColor: surface,
          borderWidth: 4,
          hoverBorderColor: surface,
          hoverBorderWidth: 4,
          hoverOffset: 5,
          spacing: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "64%",
      animation: { duration: 500 },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: tooltip,
          titleColor: tooltipText,
          bodyColor: tooltipText,
          padding: 12,
          displayColors: false,
          callbacks: {
            label: (context) => {
              const value = Number(context.parsed);
              const share = total.value > 0 ? value / total.value : 0;
              return `${money.format(value)} · ${percentage.format(share)}`;
            },
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
watch(() => [props.items, locale.value, reportingCurrency.value], render, {
  deep: true,
});
onBeforeUnmount(() => {
  themeObserver?.disconnect();
  chart?.destroy();
});
</script>

<template>
  <div class="allocation-chart">
    <canvas
      ref="canvas"
      role="img"
      :aria-label="
        t('shared.allocationChart.aria', { count: visibleItems.length })
      "
    />
  </div>
</template>

<style scoped>
.allocation-chart {
  position: relative;
  width: 174px;
  height: 174px;
}

@media (max-width: 720px) {
  .allocation-chart {
    width: 148px;
    height: 148px;
  }
}
</style>
