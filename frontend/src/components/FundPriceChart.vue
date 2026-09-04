<script setup lang="ts">
import {
  CategoryScale,
  Chart,
  Filler,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  ScatterController,
  Tooltip,
} from "chart.js";
import type { ChartConfiguration, ChartDataset } from "chart.js";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { NormalizedLineChartPoint } from "../domain/investments";
import { reportingCurrency } from "../i18n";
import type { FundOrder } from "../types/api";
import {
  groupFundOperationPoints,
  visibleFundOperationPoints,
  type FundOperationMarker,
} from "./fundPriceChart";

Chart.register(
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  ScatterController,
  CategoryScale,
  Filler,
  Tooltip,
);

const props = defineProps<{
  points: NormalizedLineChartPoint[];
  orders: FundOrder[];
  averagePrice: number | null;
}>();
const { locale, t } = useI18n();
const canvas = ref<HTMLCanvasElement>();
const markerPositions = ref<Record<string, { x: number; y: number }>>({});
const chartDimensions = ref({ width: 0, height: 325 });
const activeOperationId = ref<string | null>(null);
const focusedOperationId = ref<string | null>(null);
const hoveredOperationId = ref<string | null>(null);
const hoveredTooltipId = ref<string | null>(null);
const focusedTooltipId = ref<string | null>(null);
const priceTooltip = ref<{
  x: number;
  y: number;
  date: string;
  value: string;
} | null>(null);
let chart: Chart | null = null;
let themeObserver: MutationObserver | null = null;
let closeTimer: ReturnType<typeof setTimeout> | null = null;

const operationMarkers = computed(() =>
  groupFundOperationPoints(
    visibleFundOperationPoints(
      props.orders,
      props.points.map((point) => point.date),
    ),
  ),
);

function syncOperationMarkerPositions(chartInstance: Chart) {
  const next: Record<string, { x: number; y: number }> = {};
  chartInstance.data.datasets.forEach((dataset, datasetIndex) => {
    const meta = chartInstance.getDatasetMeta(datasetIndex);
    meta.data.forEach((element, index) => {
      const point = dataset.data[index] as
        { operationMarkerId?: string } | undefined;
      if (!point?.operationMarkerId) return;
      const { x, y } = element.getProps(["x", "y"], false);
      next[point.operationMarkerId] = { x, y };
    });
  });
  const width = chartInstance.width || canvas.value?.clientWidth || 640;
  const height = chartInstance.height || canvas.value?.clientHeight || 325;
  const currentKeys = Object.keys(markerPositions.value);
  const nextKeys = Object.keys(next);
  const changed =
    currentKeys.length !== nextKeys.length ||
    nextKeys.some((key) => {
      const current = markerPositions.value[key];
      return (
        !current ||
        Math.abs(current.x - next[key].x) > 0.1 ||
        Math.abs(current.y - next[key].y) > 0.1
      );
    });
  if (changed) markerPositions.value = next;
  if (
    chartDimensions.value.width !== width ||
    chartDimensions.value.height !== height
  ) {
    chartDimensions.value = { width, height };
  }
}

const operationPinPlugin = {
  id: "fundOperationPins",
  afterDatasetsDraw(chartInstance: Chart) {
    const { ctx } = chartInstance;
    chartInstance.data.datasets.forEach((dataset, datasetIndex) => {
      const glyph = (dataset as { operationGlyph?: "+" | "−" }).operationGlyph;
      if (!glyph) return;
      const meta = chartInstance.getDatasetMeta(datasetIndex);
      ctx.save();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 1.75;
      ctx.lineCap = "round";
      meta.data.forEach((element) => {
        // Use the marker's current animated position so the glyph and pin move together.
        const { x, y } = element.getProps(["x", "y"], false);
        ctx.beginPath();
        ctx.moveTo(x - 3.25, y);
        ctx.lineTo(x + 3.25, y);
        if (glyph === "+") {
          ctx.moveTo(x, y - 3.25);
          ctx.lineTo(x, y + 3.25);
        }
        ctx.stroke();
      });
      ctx.restore();
    });
    syncOperationMarkerPositions(chartInstance);
  },
};

function priceForOrder(order: FundOrder) {
  return order.base_unit_price ?? order.unit_price;
}

function amountForOrder(order: FundOrder) {
  return order.base_net_amount ?? order.net_amount;
}

function operationLabel(order: FundOrder) {
  const operation = order.provider_operation_type || order.operation_type;
  return (
    (
      {
        buy: t("shared.movementEditor.contribution"),
        SUSCRIPCION: t("shared.movementEditor.contribution"),
        transfer_in: t("shared.movementEditor.transferIn"),
        "SUSCR.POR TRASPASO I": t("shared.movementEditor.transferIn"),
        transfer_out: t("shared.movementEditor.transferOut"),
        "REEMB.POR TRASPASO I": t("shared.movementEditor.transferOut"),
        sell: t("shared.movementEditor.redemption"),
        REEMBOLSO: t("shared.movementEditor.redemption"),
        Compra: t("shared.movementEditor.buy"),
        Venta: t("shared.movementEditor.sell"),
      } as Record<string, string>
    )[operation] ?? operation
  );
}

function operationAccount(order: FundOrder) {
  const labels = [order.account_name, order.platform]
    .filter((value): value is string => Boolean(value?.trim()))
    .filter((value, index, values) => values.indexOf(value) === index);
  return labels.join(" · ") || t("shared.candlestick.investmentAccount");
}

function operationAccounts(marker: FundOperationMarker) {
  const labels = marker.sourceOrders
    .map((order) => operationAccount(order))
    .filter((value, index, values) => values.indexOf(value) === index);
  return labels.join(" · ") || t("shared.candlestick.investmentAccount");
}

function operationHeading(marker: FundOperationMarker) {
  const labels = marker.sourceOrders
    .map((order) => operationLabel(order))
    .filter((value, index, values) => values.indexOf(value) === index);
  const label =
    labels.length === 1
      ? labels[0]
      : t(
          marker.buy
            ? "shared.fundPrice.buyOrEntry"
            : "shared.fundPrice.sellOrExit",
        );
  return marker.operationCount > 1
    ? `${label} ×${marker.operationCount}`
    : label;
}

function dateForOrder(order: FundOrder) {
  return new Date(`${order.trade_date.slice(0, 10)}T00:00:00`);
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.max(minimum, Math.min(maximum, value));
}

function fallbackMarkerPosition(marker: FundOperationMarker) {
  const width = chartDimensions.value.width || canvas.value?.clientWidth || 640;
  const height =
    chartDimensions.value.height || canvas.value?.clientHeight || 325;
  const pointIndex = props.points.findIndex((point) => point.date === marker.x);
  const x =
    props.points.length > 1
      ? 30 +
        (Math.max(pointIndex, 0) / (props.points.length - 1)) *
          Math.max(width - 70, 100)
      : width / 2;
  const values = [
    ...props.points.map((point) => point.price),
    ...(props.averagePrice != null ? [props.averagePrice] : []),
    ...operationMarkers.value.map((item) => item.y),
  ];
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = Math.max(maximum - minimum, 1);
  const y = 22 + ((maximum - marker.y) / span) * Math.max(height - 52, 120);
  return { x, y };
}

function markerPosition(marker: FundOperationMarker) {
  return markerPositions.value[marker.id] ?? fallbackMarkerPosition(marker);
}

const money = computed(
  () =>
    new Intl.NumberFormat(locale.value, {
      style: "currency",
      currency: reportingCurrency.value,
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    }),
);
const totalMoney = computed(
  () =>
    new Intl.NumberFormat(locale.value, {
      style: "currency",
      currency: reportingCurrency.value,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
);
const quantities = computed(
  () => new Intl.NumberFormat(locale.value, { maximumFractionDigits: 6 }),
);
const dates = computed(
  () => new Intl.DateTimeFormat(locale.value, { dateStyle: "medium" }),
);

const priceTooltipStyle = computed(() => {
  if (!priceTooltip.value) return {};
  const width = 156;
  const height = 56;
  const chartWidth =
    chartDimensions.value.width || canvas.value?.clientWidth || 640;
  const chartHeight =
    chartDimensions.value.height || canvas.value?.clientHeight || 325;
  const preferredX =
    priceTooltip.value.x > chartWidth * 0.72
      ? priceTooltip.value.x - width - 12
      : priceTooltip.value.x + 12;
  const x = clamp(preferredX, 4, Math.max(4, chartWidth - width - 4));
  const y = clamp(
    priceTooltip.value.y - height / 2,
    4,
    Math.max(4, chartHeight - height - 4),
  );
  return {
    left: `${x}px`,
    top: `${y}px`,
    width: `${width}px`,
    height: `${height}px`,
  };
});

const priceTooltipGuideStyle = computed(() => ({
  left: `${priceTooltip.value?.x ?? 0}px`,
  top: "4px",
  height: `${Math.max((chartDimensions.value.height || canvas.value?.clientHeight || 325) - 8, 1)}px`,
}));

const operationTooltip = computed(() => {
  const marker = operationMarkers.value.find(
    (item) => item.id === activeOperationId.value,
  );
  if (!marker) return null;
  const grouped = marker.operationCount > 1;
  const chartWidth =
    chartDimensions.value.width || canvas.value?.clientWidth || 640;
  const chartHeight =
    chartDimensions.value.height || canvas.value?.clientHeight || 325;
  const availableWidth = Math.max(chartWidth - 12, 1);
  const columnCount =
    grouped && availableWidth >= 545
      ? Math.min(2, Math.ceil(marker.operationCount / 5))
      : 1;
  const rowsPerColumn = Math.ceil(marker.operationCount / columnCount);
  const columnWidth = 265;
  const width = Math.min(columnWidth * columnCount, availableWidth);
  const rowHeight = 44;
  const preferredHeight = grouped ? 53 + rowsPerColumn * rowHeight + 8 : 108;
  // Keep the card inside the chart on narrow/mobile layouts. Long grouped
  // details remain available through the keyboard-scrollable rows pane.
  const height = Math.min(preferredHeight, Math.max(chartHeight - 8, 1));
  const position = markerPosition(marker);
  const x = clamp(
    position.x > chartWidth * 0.68 ? position.x - width - 14 : position.x + 14,
    4,
    Math.max(4, chartWidth - width - 4),
  );
  const y = clamp(
    position.y - height / 2,
    4,
    Math.max(4, chartHeight - height - 4),
  );
  const rows = marker.sourceOrders.map((order, index) => ({
    order,
    type: operationLabel(order),
    account: operationAccount(order),
    date: dates.value.format(dateForOrder(order)),
    units: t("shared.fundPrice.units", {
      count: quantities.value.format(order.quantity),
    }),
    price: money.value.format(priceForOrder(order)),
    amount: totalMoney.value.format(amountForOrder(order)),
    column: Math.floor(index / rowsPerColumn),
    row: index % rowsPerColumn,
  }));
  return {
    marker,
    grouped,
    title: grouped
      ? operationHeading(marker)
      : `${operationHeading(marker)} · ${operationAccounts(marker)}`,
    date: dates.value.format(dateForOrder(marker.order)),
    units: t("shared.fundPrice.units", {
      count: quantities.value.format(marker.order.quantity),
    }),
    price: money.value.format(priceForOrder(marker.order)),
    amount: totalMoney.value.format(amountForOrder(marker.order)),
    rows,
    x,
    y,
    width,
    height,
    account: operationAccount(marker.order),
    columnCount,
    columnWidth: width / columnCount,
    rowHeight,
    rowsMaxHeight: Math.max(height - 64, 48),
  };
});

function operationAriaLabel(marker: FundOperationMarker) {
  const order = marker.order;
  return `${operationHeading(marker)} · ${operationAccounts(marker)} · ${dates.value.format(dateForOrder(order))}. ${t("shared.fundPrice.units", { count: quantities.value.format(order.quantity) })}. ${t("shared.fundPrice.priceValue", { value: money.value.format(priceForOrder(order)) })}. ${t("shared.fundPrice.amount", { value: totalMoney.value.format(amountForOrder(order)) })}`;
}

function markerButtonStyle(marker: FundOperationMarker) {
  const position = markerPosition(marker);
  return {
    left: `${position.x}px`,
    top: `${position.y}px`,
  };
}

function clearChartTooltip() {
  priceTooltip.value = null;
  if (!chart) return;
  chart.setActiveElements([]);
  chart.tooltip?.setActiveElements([], { x: 0, y: 0 });
  chart.update("none");
}

function cancelClose() {
  if (closeTimer !== null) {
    clearTimeout(closeTimer);
    closeTimer = null;
  }
}

function closeIfOutside(operationId: string) {
  closeTimer = null;
  if (activeOperationId.value !== operationId) return;
  if (
    focusedOperationId.value === operationId ||
    focusedTooltipId.value === operationId ||
    hoveredOperationId.value === operationId ||
    hoveredTooltipId.value === operationId
  )
    return;
  activeOperationId.value = null;
}

function scheduleClose(operationId: string) {
  cancelClose();
  closeTimer = setTimeout(() => closeIfOutside(operationId), 120);
}

function showOperation(operationId: string) {
  activeOperationId.value = operationId;
  clearChartTooltip();
  cancelClose();
}

function enterOperation(operationId: string) {
  hoveredOperationId.value = operationId;
  showOperation(operationId);
}

function leaveOperation(operationId: string) {
  hoveredOperationId.value = null;
  scheduleClose(operationId);
}

function focusOperation(operationId: string) {
  focusedOperationId.value = operationId;
  showOperation(operationId);
}

function blurOperation(operationId: string) {
  if (focusedOperationId.value === operationId) focusedOperationId.value = null;
  scheduleClose(operationId);
}

function enterTooltip(operationId: string) {
  hoveredTooltipId.value = operationId;
  showOperation(operationId);
}

function leaveTooltip(operationId: string) {
  hoveredTooltipId.value = null;
  scheduleClose(operationId);
}

function focusTooltip(operationId: string) {
  focusedTooltipId.value = operationId;
  showOperation(operationId);
}

function blurTooltip(operationId: string) {
  if (focusedTooltipId.value === operationId) focusedTooltipId.value = null;
  scheduleClose(operationId);
}

function closeOperation(operationId: string, event: Event) {
  cancelClose();
  if (focusedOperationId.value === operationId) focusedOperationId.value = null;
  if (activeOperationId.value === operationId) activeOperationId.value = null;
  hoveredOperationId.value = null;
  hoveredTooltipId.value = null;
  focusedTooltipId.value = null;
  const target = event.currentTarget as HTMLElement | null;
  target?.blur();
}

function closeActiveOperation(event: Event) {
  cancelClose();
  activeOperationId.value = null;
  focusedOperationId.value = null;
  hoveredOperationId.value = null;
  hoveredTooltipId.value = null;
  focusedTooltipId.value = null;
  const target = event.currentTarget as HTMLElement | null;
  target?.blur();
}

function render() {
  const previousActiveId = activeOperationId.value;
  priceTooltip.value = null;
  markerPositions.value = {};
  chart?.destroy();
  if (
    previousActiveId &&
    !operationMarkers.value.some((marker) => marker.id === previousActiveId)
  ) {
    activeOperationId.value = null;
    focusedOperationId.value = null;
    hoveredOperationId.value = null;
    hoveredTooltipId.value = null;
    focusedTooltipId.value = null;
  }
  if (!canvas.value || props.points.length < 2) return;
  const styles = getComputedStyle(canvas.value);
  const accent = styles.getPropertyValue("--fz-accent").trim() || "#3ddc97";
  const surface = styles.getPropertyValue("--fz-surface").trim() || "#fff";
  const tradeBuy =
    styles.getPropertyValue("--fz-trade-buy").trim() || "#3b6ff5";
  const tradeSell =
    styles.getPropertyValue("--fz-trade-sell").trim() || "#d97706";
  const tradeBuyOutline =
    styles.getPropertyValue("--fz-trade-buy-outline").trim() || surface;
  const tradeSellOutline =
    styles.getPropertyValue("--fz-trade-sell-outline").trim() || surface;
  const average =
    styles.getPropertyValue("--fz-chart-average").trim() || "#7d8790";
  const muted = styles.getPropertyValue("--fz-muted").trim() || "#8fa49a";
  const grid =
    styles.getPropertyValue("--fz-chart-grid").trim() ||
    "rgba(143,164,154,.15)";
  const labels = props.points.map((point) => point.date);
  const priceFormatter = new Intl.NumberFormat(locale.value, {
    style: "currency",
    currency: reportingCurrency.value,
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  });
  const operationPoints = groupFundOperationPoints(
    visibleFundOperationPoints(props.orders, labels),
  );
  const buyPoints = operationPoints.filter(({ buy }) => buy);
  const sellPoints = operationPoints.filter(({ buy }) => !buy);
  const chartPoint = (point: FundOperationMarker) => ({
    x: point.x,
    y: point.y,
    order: point.order,
    operationMarkerId: point.id,
  });
  type FundChartPoint = {
    x: string;
    y: number;
    order: FundOrder;
    operationMarkerId?: string;
  };
  type FundChartDataset = ChartDataset<
    "line" | "scatter",
    (number | FundChartPoint)[]
  > & {
    operationGlyph?: "+" | "−";
  };
  const datasets: FundChartDataset[] = [
    {
      label: t("shared.fundPrice.price"),
      data: props.points.map((point) => point.price),
      borderColor: accent,
      backgroundColor: `${accent}18`,
      borderWidth: 2.4,
      fill: true,
      tension: 0.22,
      pointRadius: 0,
      pointHoverRadius: 8,
      pointHoverBackgroundColor: accent,
      pointHoverBorderColor: surface,
      pointHoverBorderWidth: 1.5,
    },
  ];
  if (props.averagePrice != null) {
    const averagePrice = props.averagePrice;
    datasets.push({
      label: t("shared.fundPrice.averagePrice"),
      data: props.points.map(() => averagePrice),
      borderColor: average,
      borderWidth: 1.5,
      borderDash: [5, 5],
      fill: false,
      tension: 0,
      pointRadius: 0,
      pointHoverRadius: 0,
    });
  }
  datasets.push(
    {
      label: t("shared.fundPrice.buyOrEntry"),
      type: "scatter",
      data: buyPoints.map(chartPoint),
      backgroundColor: tradeBuy,
      borderColor: tradeBuyOutline,
      borderWidth: 1.75,
      pointStyle: "rectRounded",
      pointRadius: 8,
      pointHoverRadius: 9.5,
      operationGlyph: "+",
    },
    {
      label: t("shared.fundPrice.sellOrExit"),
      type: "scatter",
      data: sellPoints.map(chartPoint),
      backgroundColor: tradeSell,
      borderColor: tradeSellOutline,
      borderWidth: 1.75,
      pointStyle: "rectRounded",
      pointRadius: 8,
      pointHoverRadius: 9.5,
      operationGlyph: "−",
    },
  );

  const chartConfiguration: ChartConfiguration<
    "line" | "scatter",
    (number | FundChartPoint)[],
    string
  > = {
    type: "line",
    data: { labels, datasets },
    plugins: [operationPinPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: "nearest" },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: false,
          external: ({ tooltip: chartTooltip }) => {
            if (chartTooltip.opacity === 0) {
              priceTooltip.value = null;
              return;
            }
            const point = chartTooltip.dataPoints?.find(
              (item) => item.datasetIndex === 0,
            );
            if (
              !point ||
              chartTooltip.caretX == null ||
              chartTooltip.caretY == null
            ) {
              priceTooltip.value = null;
              return;
            }
            const date = labels[point.dataIndex];
            if (!date) {
              priceTooltip.value = null;
              return;
            }
            priceTooltip.value = {
              x: chartTooltip.caretX,
              y: chartTooltip.caretY,
              date: dates.value.format(new Date(`${date}T00:00:00`)),
              value: priceFormatter.format(Number(point.parsed.y)),
            };
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
            padding: 10,
            font: { size: 10, weight: 600 },
          },
        },
        y: {
          border: { display: false },
          grid: { color: grid },
          ticks: {
            color: muted,
            maxTicksLimit: 5,
            padding: 8,
            callback: (value) => priceFormatter.format(Number(value)),
            font: { size: 10, weight: 600 },
          },
        },
      },
    },
  };
  chart = new Chart(canvas.value, chartConfiguration) as unknown as Chart;
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
    props.points,
    props.orders,
    props.averagePrice,
    locale.value,
    reportingCurrency.value,
  ],
  render,
  { deep: true },
);
onBeforeUnmount(() => {
  themeObserver?.disconnect();
  cancelClose();
  chart?.destroy();
});
</script>

<template>
  <div class="fund-price-chart">
    <canvas
      ref="canvas"
      role="img"
      :aria-label="t('shared.fundPrice.chartAria')"
    />
    <span
      v-if="priceTooltip"
      class="price-tooltip-guide"
      :style="priceTooltipGuideStyle"
      aria-hidden="true"
    />
    <div
      v-if="priceTooltip"
      class="operation-tooltip price-tooltip"
      :style="priceTooltipStyle"
      aria-hidden="true"
    >
      <span class="operation-tooltip-accent price" aria-hidden="true" />
      <span class="operation-tooltip-date">{{ priceTooltip.date }}</span>
      <strong class="operation-tooltip-value">{{ priceTooltip.value }}</strong>
    </div>
    <button
      v-for="marker in operationMarkers"
      :key="marker.id"
      type="button"
      class="operation-marker"
      :class="{
        buy: marker.buy,
        sell: !marker.buy,
        active: activeOperationId === marker.id,
      }"
      :style="markerButtonStyle(marker)"
      :data-operation-id="marker.id"
      :data-direction="marker.buy ? 'buy' : 'sell'"
      :data-operation-count="marker.operationCount"
      :aria-label="operationAriaLabel(marker)"
      @pointerdown.stop
      @click.stop="showOperation(marker.id)"
      @pointerenter="enterOperation(marker.id)"
      @pointerleave="leaveOperation(marker.id)"
      @focus="focusOperation(marker.id)"
      @blur="blurOperation(marker.id)"
      @keydown.esc.prevent.stop="closeOperation(marker.id, $event)"
    />
    <div
      v-if="operationTooltip"
      class="operation-tooltip"
      role="status"
      aria-live="polite"
      :style="{
        left: `${operationTooltip.x}px`,
        top: `${operationTooltip.y}px`,
        width: `${operationTooltip.width}px`,
        height: `${operationTooltip.height}px`,
      }"
      @pointerenter="enterTooltip(operationTooltip.marker.id)"
      @pointerleave="leaveTooltip(operationTooltip.marker.id)"
      @focusin="focusTooltip(operationTooltip.marker.id)"
      @focusout="blurTooltip(operationTooltip.marker.id)"
      @keydown.esc.prevent.stop="closeActiveOperation($event)"
    >
      <span
        class="operation-tooltip-accent"
        :class="{
          buy: operationTooltip.marker.buy,
          sell: !operationTooltip.marker.buy,
        }"
        aria-hidden="true"
      />
      <strong class="operation-tooltip-title">{{
        operationTooltip.title
      }}</strong>
      <span class="operation-tooltip-date">{{ operationTooltip.date }}</span>
      <template v-if="operationTooltip.grouped">
        <div
          class="operation-tooltip-rows"
          tabindex="0"
          role="list"
          :aria-label="operationTooltip.title"
          :style="{
            maxHeight: `${operationTooltip.rowsMaxHeight}px`,
            gridTemplateColumns: `repeat(${operationTooltip.columnCount}, minmax(0, 1fr))`,
          }"
        >
          <div
            v-for="row in operationTooltip.rows"
            :key="row.order.id"
            class="operation-tooltip-row"
            role="listitem"
            :style="{ gridColumn: row.column + 1, gridRow: row.row + 1 }"
          >
            <span class="operation-tooltip-row-type">{{ row.type }}</span>
            <span class="operation-tooltip-row-account">{{ row.account }}</span>
            <strong class="operation-tooltip-row-total">{{
              t("shared.candlestick.total", { value: row.amount })
            }}</strong>
            <span class="operation-tooltip-row-detail">{{
              `${row.date} · ${row.units} · ${row.price} / ${t("shared.candlestick.unit")}`
            }}</span>
          </div>
        </div>
      </template>
      <template v-else>
        <span class="operation-tooltip-value">{{
          `${operationTooltip.units} · ${operationTooltip.price} / ${t("shared.candlestick.unit")}`
        }}</span>
        <strong class="operation-tooltip-total">{{
          t("shared.candlestick.total", { value: operationTooltip.amount })
        }}</strong>
      </template>
    </div>
  </div>
</template>

<style scoped>
.fund-price-chart {
  position: relative;
  width: 100%;
  height: 325px;
}
.fund-price-chart canvas {
  position: relative;
  z-index: 1;
}
.price-tooltip-guide {
  position: absolute;
  z-index: 2;
  width: 1px;
  background: color-mix(in srgb, var(--fz-muted) 42%, transparent);
  border-left: 1px dashed color-mix(in srgb, var(--fz-muted) 42%, transparent);
  transform: translateX(-0.5px);
  pointer-events: none;
}
.operation-marker {
  position: absolute;
  z-index: 3;
  width: 30px;
  height: 30px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  transform: translate(-50%, -50%);
  cursor: help;
}
.operation-marker:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: 2px;
}
.operation-marker.buy {
  color: var(--fz-trade-buy-outline, #3b6ff5);
}
.operation-marker.sell {
  color: var(--fz-trade-sell-outline, #d97706);
}
.operation-tooltip {
  position: absolute;
  z-index: 4;
  display: grid;
  grid-template-columns: 1fr;
  gap: 4px;
  min-width: 0;
  min-height: 0;
  padding: 13px 15px 12px 17px;
  overflow: hidden;
  color: var(--fz-chart-tooltip-text);
  background: var(--fz-chart-operation-tooltip, var(--fz-chart-tooltip));
  border: 1px solid var(--fz-chart-tooltip-border);
  border-radius: 11px;
  box-shadow: 0 8px 18px var(--fz-chart-tooltip-shadow);
  backdrop-filter: blur(10px) saturate(120%);
  pointer-events: auto;
}
.price-tooltip {
  background: var(--fz-chart-tooltip);
  pointer-events: none;
}
.operation-tooltip-accent {
  position: absolute;
  top: 11px;
  bottom: 11px;
  left: 0;
  width: 3px;
  border-radius: 0 2px 2px 0;
}
.operation-tooltip-accent.buy {
  background: var(--fz-trade-buy-outline, #3b6ff5);
}
.operation-tooltip-accent.sell {
  background: var(--fz-trade-sell-outline, #d97706);
}
.operation-tooltip-accent.price {
  background: var(--fz-accent);
}
.operation-tooltip-title {
  color: var(--fz-chart-tooltip-text);
  font-size: 11px;
  font-weight: 780;
  line-height: 1.25;
}
.operation-tooltip-date {
  color: var(--fz-chart-tooltip-muted);
  font-size: 10px;
  font-weight: 620;
  line-height: 1.25;
  font-variant-numeric: tabular-nums;
}
.operation-tooltip-value,
.operation-tooltip-total {
  color: var(--fz-chart-tooltip-text);
  font-size: 11px;
  font-weight: 720;
  line-height: 1.35;
  font-variant-numeric: tabular-nums;
}
.operation-tooltip-total {
  margin-top: 2px;
}
.operation-tooltip-rows {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 12px;
  min-height: 0;
  overflow-y: auto;
  margin-top: 3px;
  scrollbar-width: thin;
}
.operation-tooltip-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 2px 8px;
  min-width: 0;
  padding: 7px 0 4px;
  border-top: 1px solid
    color-mix(in srgb, var(--fz-chart-tooltip-border) 72%, transparent);
}
.operation-tooltip-row-type {
  grid-column: 1 / -1;
  color: var(--fz-chart-tooltip-muted);
  font-size: 10px;
  font-weight: 700;
}
.operation-tooltip-row-account,
.operation-tooltip-row-total {
  min-width: 0;
  overflow: hidden;
  color: var(--fz-chart-tooltip-text);
  font-size: 10px;
  font-weight: 760;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.operation-tooltip-row-total {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.operation-tooltip-row-detail {
  grid-column: 1 / -1;
  color: var(--fz-chart-tooltip-muted);
  font-size: 10px;
  font-weight: 620;
  line-height: 1.35;
  font-variant-numeric: tabular-nums;
}
@media (max-width: 540px) {
  .operation-tooltip-rows {
    grid-template-columns: 1fr;
  }
}
@media (prefers-reduced-motion: reduce) {
  .operation-marker {
    transition: none;
  }
}
</style>
