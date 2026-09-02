<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { ChartOperation } from "../domain/chartOperationFixes";
import { reportingCurrency } from "../i18n";
import type { MarketCandle } from "../types/api";

const props = withDefaults(
  defineProps<{
    points: MarketCandle[];
    operations: ChartOperation[];
    averagePrice: number | null;
    /** Trade pins are kept explicit so consuming views can document their visual contract. */
    operationMarkerShape?: "pin";
  }>(),
  {
    operationMarkerShape: "pin",
  },
);
const { locale, t } = useI18n();

const width = 1000;
const height = 370;
const bounds = { left: 20, right: 82, top: 18, bottom: 42 };
const plotWidth = width - bounds.left - bounds.right;
const plotHeight = height - bounds.top - bounds.bottom;
const markerGap = 5;
const singlePinWidth = 18;
const groupedPinWidth = 25;
const pinHeight = 16;
const pinBorderWidth = 1.5;
const pinConnectorLength = 7;
const markerHorizontalHalfWidth = groupedPinWidth / 2 + pinBorderWidth;
const markerDomainPadding =
  markerGap + pinConnectorLength + pinHeight + pinBorderWidth;
const hoveredDate = ref<string | null>(null);
const hoveredOperationId = ref<string | null>(null);
const dragStartDate = ref<string | null>(null);
const dragEndDate = ref<string | null>(null);
const pointerStartDate = ref<string | null>(null);
const isDragging = ref(false);
const hasDragged = ref(false);

const money = computed(
  () =>
    new Intl.NumberFormat(locale.value, {
      style: "currency",
      currency: reportingCurrency.value,
      maximumFractionDigits: 0,
    }),
);
const preciseMoney = computed(
  () =>
    new Intl.NumberFormat(locale.value, {
      style: "currency",
      currency: reportingCurrency.value,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
);
const quantity = computed(
  () =>
    new Intl.NumberFormat(locale.value, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 8,
    }),
);
const shortDate = computed(
  () =>
    new Intl.DateTimeFormat(locale.value, { day: "2-digit", month: "short" }),
);
const longDate = computed(
  () =>
    new Intl.DateTimeFormat(locale.value, {
      day: "numeric",
      month: "short",
      year: "numeric",
    }),
);
const fullDate = computed(
  () =>
    new Intl.DateTimeFormat(locale.value, {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }),
);
function operationAssetId(operation: ChartOperation) {
  return "symbol" in operation ? operation.symbol : operation.isin;
}
function operationAccount(operation: ChartOperation) {
  return (
    operation.account_name ||
    operation.platform ||
    t("shared.candlestick.investmentAccount")
  );
}
function truncateLabel(value: string, length = 24) {
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}
const percentage = computed(
  () =>
    new Intl.NumberFormat(locale.value, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
);

const timestamps = computed(() =>
  props.points.map((point) => Date.parse(`${point.fecha}T00:00:00Z`)),
);
const domain = computed(() => {
  const values = props.points.flatMap((point) => [point.low, point.high]);
  if (props.averagePrice && props.averagePrice > 0)
    values.push(props.averagePrice);
  props.operations.forEach((operation) => {
    const timestamp = Date.parse(
      `${operation.trade_date.slice(0, 10)}T00:00:00Z`,
    );
    const first = timestamps.value[0] ?? 0;
    const last = timestamps.value.at(-1) ?? 0;
    if (operation.unit_price > 0 && timestamp >= first && timestamp <= last) {
      values.push(operation.unit_price);
    }
  });
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = Math.max(maximum - minimum, maximum * 0.025, 1);
  // Reserve outer padding so local trade pins at the chart extremes remain fully visible.
  const paddingFraction = markerDomainPadding / plotHeight;
  const valuePadding =
    (span * paddingFraction) / Math.max(1 - paddingFraction * 2, 0.1);
  return { minimum: minimum - valuePadding, maximum: maximum + valuePadding };
});
const timeDomain = computed(() => ({
  minimum: timestamps.value[0] ?? 0,
  maximum: timestamps.value.at(-1) ?? 1,
}));
const candleWidth = computed(() =>
  Math.max(
    2,
    Math.min(13, (plotWidth / Math.max(props.points.length, 1)) * 0.62),
  ),
);

function xFor(timestamp: number) {
  const span = Math.max(timeDomain.value.maximum - timeDomain.value.minimum, 1);
  return (
    bounds.left + ((timestamp - timeDomain.value.minimum) / span) * plotWidth
  );
}

function yFor(value: number) {
  const span = Math.max(domain.value.maximum - domain.value.minimum, 1);
  return bounds.top + ((domain.value.maximum - value) / span) * plotHeight;
}

const candles = computed(() =>
  props.points.map((point, index) => {
    const x = xFor(timestamps.value[index]);
    const openY = yFor(point.open);
    const closeY = yFor(point.close);
    return {
      ...point,
      x,
      timestamp: timestamps.value[index],
      highY: yFor(point.high),
      lowY: yFor(point.low),
      bodyY: Math.min(openY, closeY),
      bodyHeight: Math.max(Math.abs(closeY - openY), 1.5),
      closeY,
      rising: point.close >= point.open,
    };
  }),
);
function clampMarkerY(value: number) {
  const strokeHalf = pinBorderWidth / 2;
  const topExtent = pinHeight / 2 + strokeHalf;
  const bottomExtent = pinHeight / 2 + strokeHalf;
  return Math.max(
    bounds.top + topExtent,
    Math.min(height - bounds.bottom - bottomExtent, value),
  );
}

function markerPosition(
  timestamp: number,
  x: number,
  buy: boolean,
  price: number,
) {
  const associatedCandle = candles.value.reduce((closest, candidate) => {
    if (
      !closest ||
      Math.abs(candidate.timestamp - timestamp) <
        Math.abs(closest.timestamp - timestamp)
    ) {
      return candidate;
    }
    return closest;
  }, candles.value[0]);
  const footprintLeft = x - markerHorizontalHalfWidth;
  const footprintRight = x + markerHorizontalHalfWidth;
  const candleHalfWidth = candleWidth.value / 2 + 0.7;
  const localCandles = candles.value.filter(
    (candle) =>
      candle.x + candleHalfWidth >= footprintLeft &&
      candle.x - candleHalfWidth <= footprintRight,
  );
  if (associatedCandle && !localCandles.includes(associatedCandle))
    localCandles.push(associatedCandle);
  if (!localCandles.length) {
    return {
      y: clampMarkerY(yFor(price)),
      candleLowY: null,
      candleHighY: null,
    };
  }
  // SVG Y grows downwards: the lowest local price is the largest Y coordinate.
  const localLowY = Math.max(...localCandles.map((candle) => candle.lowY));
  const localHighY = Math.min(...localCandles.map((candle) => candle.highY));
  const y = buy
    ? localLowY + markerGap + pinConnectorLength + pinHeight / 2
    : localHighY - markerGap - pinConnectorLength - pinHeight / 2;
  return {
    y: clampMarkerY(y),
    candleLowY: localLowY,
    candleHighY: localHighY,
  };
}
const hoveredCandle = computed(
  () =>
    candles.value.find((candle) => candle.fecha === hoveredDate.value) ?? null,
);
const selectedRange = computed(() => {
  if (!dragStartDate.value || !dragEndDate.value) return null;
  const startCandidate = candles.value.find(
    (candle) => candle.fecha === dragStartDate.value,
  );
  const endCandidate = candles.value.find(
    (candle) => candle.fecha === dragEndDate.value,
  );
  if (!startCandidate || !endCandidate) return null;
  const [start, end] =
    startCandidate.x <= endCandidate.x
      ? [startCandidate, endCandidate]
      : [endCandidate, startCandidate];
  const change = start.close
    ? ((end.close - start.close) / start.close) * 100
    : 0;
  const direction = change > 0 ? "up" : change < 0 ? "down" : "flat";
  const label = t(
    direction === "up"
      ? "shared.candlestick.rise"
      : direction === "down"
        ? "shared.candlestick.fall"
        : "shared.candlestick.unchanged",
  );
  const formattedChange = `${change > 0 ? "+" : change < 0 ? "−" : ""}${percentage.value.format(Math.abs(change))} %`;
  return {
    start,
    end,
    direction,
    label,
    formattedChange,
    dates: `${fullDate.value.format(new Date(`${start.fecha}T00:00:00Z`))} → ${fullDate.value.format(new Date(`${end.fecha}T00:00:00Z`))}`,
    x: start.x,
    width: Math.max(end.x - start.x, candleWidth.value),
  };
});
const tooltip = computed(() => {
  if (isDragging.value || selectedRange.value || hoveredOperationId.value)
    return null;
  const candle = hoveredCandle.value;
  if (!candle) return null;
  const tooltipWidth = 156;
  const tooltipHeight = 56;
  const x =
    candle.x > bounds.left + plotWidth * 0.72
      ? candle.x - tooltipWidth - 12
      : candle.x + 12;
  const y = Math.max(
    bounds.top + 4,
    Math.min(
      candle.closeY - tooltipHeight / 2,
      bounds.top + plotHeight - tooltipHeight - 4,
    ),
  );
  return { candle, x, y, width: tooltipWidth, height: tooltipHeight };
});
const yTicks = computed(() =>
  Array.from({ length: 5 }, (_, index) => {
    const value =
      domain.value.maximum -
      ((domain.value.maximum - domain.value.minimum) / 4) * index;
    return { value, y: yFor(value) };
  }),
);
const xTicks = computed(() => {
  if (!props.points.length) return [];
  const count = Math.min(6, props.points.length);
  return Array.from({ length: count }, (_, index) => {
    const pointIndex = Math.round(
      (index * (props.points.length - 1)) / Math.max(count - 1, 1),
    );
    const point = props.points[pointIndex];
    return {
      fecha: point.fecha,
      x: xFor(timestamps.value[pointIndex]),
      label: shortDate.value
        .format(new Date(`${point.fecha}T00:00:00Z`))
        .replace(".", ""),
    };
  });
});
const operationMarkers = computed(() => {
  const visible = props.operations.flatMap((operation) => {
    const timestamp = Date.parse(
      `${operation.trade_date.slice(0, 10)}T00:00:00Z`,
    );
    if (
      !operation.unit_price ||
      timestamp < timeDomain.value.minimum ||
      timestamp > timeDomain.value.maximum
    )
      return [];
    return [{ operation, timestamp }];
  });
  const groups = new Map<string, typeof visible>();
  visible.forEach((item) => {
    const buy = item.operation.operation_type === "buy";
    const key = `${item.operation.trade_date.slice(0, 10)}:${buy ? "buy" : "sell"}`;
    const group = groups.get(key) ?? [];
    group.push(item);
    groups.set(key, group);
  });
  return Array.from(groups.values()).map((group) => {
    const { operation: firstOperation, timestamp } = group[0];
    const buy = firstOperation.operation_type === "buy";
    const operationCount = group.length;
    const titles = group.reduce(
      (total, item) => total + item.operation.quantity,
      0,
    );
    const weightedPrice = group.reduce(
      (total, item) =>
        total + item.operation.unit_price * item.operation.quantity,
      0,
    );
    const sameAccount = group.every(
      (item) => item.operation.account_name === firstOperation.account_name,
    );
    const sameAdjustment = group.every(
      (item) =>
        item.operation.chartAdjustment?.id ===
        firstOperation.chartAdjustment?.id,
    );
    const operation = {
      ...firstOperation,
      id: group.map((item) => item.operation.id).join(":"),
      quantity: titles,
      net_amount: group.reduce(
        (total, item) => total + item.operation.net_amount,
        0,
      ),
      fee: group.reduce((total, item) => total + item.operation.fee, 0),
      unit_price:
        titles > 0 ? weightedPrice / titles : firstOperation.unit_price,
      account_name: sameAccount ? firstOperation.account_name : "",
      chartAdjustment: sameAdjustment
        ? firstOperation.chartAdjustment
        : undefined,
    };
    const baseX = xFor(timestamp);
    const x = Math.max(
      bounds.left + markerHorizontalHalfWidth,
      Math.min(width - bounds.right - markerHorizontalHalfWidth, baseX),
    );
    const position = markerPosition(timestamp, x, buy, operation.unit_price);
    const { y } = position;
    return {
      ...operation,
      buy,
      operationCount,
      sourceOperations: group.map((item) => item.operation),
      width: operationCount > 1 ? groupedPinWidth : singlePinWidth,
      x,
      y,
      candleLowY: position.candleLowY,
      candleHighY: position.candleHighY,
      connectorCandleY: buy ? position.candleLowY : position.candleHighY,
      connectorPinY: buy ? y - pinHeight / 2 : y + pinHeight / 2,
      timestamp,
    };
  });
});
const operationTooltip = computed(() => {
  const marker = operationMarkers.value.find(
    (operation) => operation.id === hoveredOperationId.value,
  );
  if (!marker) return null;
  const grouped = marker.operationCount > 1;
  const columnCount = grouped
    ? Math.min(2, Math.ceil(marker.operationCount / 5))
    : 1;
  const rowsPerColumn = Math.ceil(marker.operationCount / columnCount);
  const hasRowAdjustment = marker.sourceOperations.some(
    (operation) => operation.chartAdjustment,
  );
  const rowHeight = hasRowAdjustment ? 50 : 42;
  const columnWidth = 285;
  const tooltipWidth = grouped ? columnWidth * columnCount : 260;
  const tooltipHeight = grouped
    ? 50 + rowsPerColumn * rowHeight + 8
    : marker.chartAdjustment
      ? 111
      : 92;
  const preferredX =
    marker.x > bounds.left + plotWidth * 0.68
      ? marker.x - tooltipWidth - 14
      : marker.x + 14;
  const x = Math.max(
    bounds.left + 4,
    Math.min(width - bounds.right - tooltipWidth - 4, preferredX),
  );
  const y = Math.max(
    bounds.top + 4,
    Math.min(
      marker.y - tooltipHeight / 2,
      bounds.top + plotHeight - tooltipHeight - 4,
    ),
  );
  const rows = marker.sourceOperations.map((operation, index) => {
    const column = Math.floor(index / rowsPerColumn);
    const row = index % rowsPerColumn;
    return {
      operation,
      x: x + column * columnWidth,
      y: y + 50 + row * rowHeight,
      width: columnWidth,
      account: truncateLabel(operationAccount(operation), 25),
    };
  });
  const account = operationAccount(marker);
  return {
    marker,
    grouped,
    rows,
    x,
    y,
    width: tooltipWidth,
    height: tooltipHeight,
    account: truncateLabel(account),
  };
});
const averageY = computed(() =>
  props.averagePrice && props.averagePrice > 0
    ? yFor(props.averagePrice)
    : null,
);

function nearestCandle(event: PointerEvent) {
  const svg = event.currentTarget as SVGSVGElement;
  const rect = svg.getBoundingClientRect();
  if (!rect.width || !candles.value.length) return null;
  const pointerX = ((event.clientX - rect.left) / rect.width) * width;
  if (pointerX < bounds.left || pointerX > width - bounds.right) {
    return null;
  }
  return candles.value.reduce((candidate, candle) =>
    Math.abs(candle.x - pointerX) < Math.abs(candidate.x - pointerX)
      ? candle
      : candidate,
  );
}

function handlePointerDown(event: PointerEvent) {
  if (event.button !== 0) return;
  const nearest = nearestCandle(event);
  if (!nearest) return;
  const svg = event.currentTarget as SVGSVGElement;
  svg.setPointerCapture?.(event.pointerId);
  pointerStartDate.value = nearest.fecha;
  hasDragged.value = false;
  hoveredDate.value = null;
  isDragging.value = true;
}

function showOperation(operationId: string) {
  hoveredOperationId.value = operationId;
  hoveredDate.value = null;
}

function hideOperation() {
  hoveredOperationId.value = null;
}

function handlePointerMove(event: PointerEvent) {
  const nearest = nearestCandle(event);
  if (isDragging.value) {
    if (nearest && pointerStartDate.value) {
      if (nearest.fecha !== pointerStartDate.value) hasDragged.value = true;
      if (hasDragged.value) {
        dragStartDate.value = pointerStartDate.value;
        dragEndDate.value = nearest.fecha;
      }
    }
    return;
  }
  hoveredDate.value = nearest?.fecha ?? null;
}

function finishSelection(event: PointerEvent) {
  if (!isDragging.value) return;
  const nearest = nearestCandle(event);
  if (hasDragged.value && nearest && pointerStartDate.value) {
    dragStartDate.value = pointerStartDate.value;
    dragEndDate.value = nearest.fecha;
  } else {
    dragStartDate.value = null;
    dragEndDate.value = null;
  }
  const svg = event.currentTarget as SVGSVGElement;
  if (svg.hasPointerCapture?.(event.pointerId))
    svg.releasePointerCapture(event.pointerId);
  isDragging.value = false;
  pointerStartDate.value = null;
  hasDragged.value = false;
  hoveredDate.value = nearest?.fecha ?? null;
}

function handlePointerLeave(event: PointerEvent) {
  hoveredDate.value = null;
  hoveredOperationId.value = null;
  finishSelection(event);
}
</script>

<template>
  <div class="candlestick-scroll">
    <div v-if="points.length" class="candlestick-stage">
      <div
        v-if="selectedRange"
        class="range-summary"
        :class="`is-${selectedRange.direction}`"
        role="status"
        aria-live="polite"
        :aria-label="`${selectedRange.dates}. ${selectedRange.label} ${selectedRange.formattedChange}`"
      >
        <span class="range-summary-dates">{{ selectedRange.dates }}</span>
        <strong
          >{{ selectedRange.label }} {{ selectedRange.formattedChange }}</strong
        >
      </div>
      <svg
        class="candlestick-chart"
        :viewBox="`0 0 ${width} ${height}`"
        role="img"
        :aria-label="t('shared.candlestick.chartAria')"
        @pointerdown.prevent="handlePointerDown"
        @pointermove="handlePointerMove"
        @pointerup="finishSelection"
        @pointercancel="finishSelection"
        @pointerleave="handlePointerLeave"
      >
        <g class="chart-grid">
          <template v-for="tick in yTicks" :key="tick.value">
            <line
              :x1="bounds.left"
              :x2="width - bounds.right"
              :y1="tick.y"
              :y2="tick.y"
            />
            <text :x="width - bounds.right + 10" :y="tick.y + 4">
              {{ money.format(tick.value) }}
            </text>
          </template>
        </g>

        <g class="chart-dates">
          <template v-for="tick in xTicks" :key="tick.fecha">
            <line
              :x1="tick.x"
              :x2="tick.x"
              :y1="height - bounds.bottom"
              :y2="height - bounds.bottom + 5"
            />
            <text :x="tick.x" :y="height - 16">{{ tick.label }}</text>
          </template>
        </g>

        <g
          v-if="selectedRange"
          class="range-selection"
          :class="`is-${selectedRange.direction}`"
        >
          <rect
            :x="selectedRange.x"
            :y="bounds.top"
            :width="selectedRange.width"
            :height="plotHeight"
          />
          <line
            :x1="selectedRange.start.x"
            :x2="selectedRange.start.x"
            :y1="bounds.top"
            :y2="height - bounds.bottom"
          />
          <line
            :x1="selectedRange.end.x"
            :x2="selectedRange.end.x"
            :y1="bounds.top"
            :y2="height - bounds.bottom"
          />
        </g>

        <g class="candles">
          <g
            v-for="candle in candles"
            :key="candle.fecha"
            :class="{ rising: candle.rising, falling: !candle.rising }"
          >
            <line
              :x1="candle.x"
              :x2="candle.x"
              :y1="candle.highY"
              :y2="candle.lowY"
            />
            <rect
              :x="candle.x - candleWidth / 2"
              :y="candle.bodyY"
              :width="candleWidth"
              :height="candle.bodyHeight"
              rx=".7"
            />
          </g>
        </g>

        <g v-if="averageY !== null" class="average-price">
          <line
            :x1="bounds.left"
            :x2="width - bounds.right"
            :y1="averageY"
            :y2="averageY"
          />
          <text :x="width - bounds.right - 6" :y="averageY - 7">
            {{
              t("shared.candlestick.averagePrice", {
                value: money.format(averagePrice ?? 0),
              })
            }}
          </text>
        </g>

        <g class="operation-markers">
          <g
            v-for="marker in operationMarkers"
            :key="marker.id"
            class="operation-marker"
            :class="{
              buy: marker.buy,
              sell: !marker.buy,
              active: hoveredOperationId === marker.id,
            }"
            :data-marker-shape="operationMarkerShape"
            :data-direction="marker.buy ? 'buy' : 'sell'"
            :data-operation-count="marker.operationCount"
            :data-marker-y="marker.y"
            :data-candle-low-y="marker.candleLowY ?? undefined"
            :data-candle-high-y="marker.candleHighY ?? undefined"
            :data-connector-candle-y="marker.connectorCandleY ?? undefined"
            :data-connector-pin-y="marker.connectorPinY"
            :data-operation-id="marker.id"
            :data-adjustment="marker.chartAdjustment?.id"
            @pointerdown.stop
            @pointermove.stop
            @pointerenter="showOperation(marker.id)"
            @pointerleave="hideOperation"
          >
            <circle
              class="operation-hit"
              :cx="marker.x"
              :cy="marker.y"
              r="14"
            />
            <line
              v-if="marker.connectorCandleY !== null"
              class="operation-pin-connector"
              :x1="marker.x"
              :x2="marker.x"
              :y1="marker.connectorCandleY"
              :y2="marker.connectorPinY"
            />
            <g class="operation-pin-body" aria-hidden="true">
              <rect
                :x="marker.x - marker.width / 2"
                :y="marker.y - pinHeight / 2"
                :width="marker.width"
                :height="pinHeight"
                rx="5"
              />
              <text
                v-if="marker.operationCount > 1"
                class="operation-pin-count"
                :x="marker.x"
                :y="marker.y"
              >
                {{ `${marker.buy ? "+" : "−"}${marker.operationCount}` }}
              </text>
              <line
                v-else
                class="operation-pin-glyph"
                :x1="marker.x - 3.25"
                :x2="marker.x + 3.25"
                :y1="marker.y"
                :y2="marker.y"
              />
              <line
                v-if="marker.buy && marker.operationCount === 1"
                class="operation-pin-glyph"
                :x1="marker.x"
                :x2="marker.x"
                :y1="marker.y - 3.25"
                :y2="marker.y + 3.25"
              />
            </g>
          </g>
        </g>

        <g v-if="operationTooltip" class="operation-tooltip" aria-hidden="true">
          <line
            class="operation-tooltip-leader"
            :x1="operationTooltip.marker.x"
            :x2="
              operationTooltip.marker.x > operationTooltip.x
                ? operationTooltip.x + operationTooltip.width
                : operationTooltip.x
            "
            :y1="operationTooltip.marker.y"
            :y2="operationTooltip.marker.y"
          />
          <g class="tooltip-card-group">
            <rect
              class="tooltip-card"
              :x="operationTooltip.x"
              :y="operationTooltip.y"
              :width="operationTooltip.width"
              :height="operationTooltip.height"
              rx="11"
            />
            <rect
              class="tooltip-accent"
              :class="{
                rising: operationTooltip.marker.buy,
                falling: !operationTooltip.marker.buy,
              }"
              :x="operationTooltip.x"
              :y="operationTooltip.y + 11"
              width="3"
              :height="operationTooltip.height - 22"
              rx="1.5"
            />
            <text
              class="operation-tooltip-title"
              :x="operationTooltip.x + 15"
              :y="operationTooltip.y + 21"
            >
              {{
                `${t(operationTooltip.marker.buy ? "shared.candlestick.buy" : "shared.candlestick.sell")}${operationTooltip.grouped ? ` ×${operationTooltip.marker.operationCount}` : ` · ${operationTooltip.account}`}`
              }}
            </text>
            <text
              class="operation-tooltip-date"
              :x="operationTooltip.x + 15"
              :y="operationTooltip.y + 38"
            >
              {{ longDate.format(new Date(operationTooltip.marker.timestamp)) }}
            </text>
            <template v-if="operationTooltip.grouped">
              <g
                v-for="row in operationTooltip.rows"
                :key="row.operation.id"
                class="operation-tooltip-row"
              >
                <line
                  class="operation-tooltip-divider"
                  :x1="row.x + 12"
                  :x2="row.x + row.width - 12"
                  :y1="row.y"
                  :y2="row.y"
                />
                <circle
                  class="operation-tooltip-dot"
                  :class="{
                    buy: operationTooltip.marker.buy,
                    sell: !operationTooltip.marker.buy,
                  }"
                  :cx="row.x + 17"
                  :cy="row.y + 14"
                  r="3"
                />
                <text
                  class="operation-tooltip-row-account"
                  :x="row.x + 26"
                  :y="row.y + 17"
                >
                  {{ row.account }}
                </text>
                <text
                  class="operation-tooltip-row-total"
                  :x="row.x + row.width - 13"
                  :y="row.y + 17"
                >
                  {{
                    t("shared.candlestick.total", {
                      value: preciseMoney.format(row.operation.net_amount),
                    })
                  }}
                </text>
                <text
                  class="operation-tooltip-row-detail"
                  :x="row.x + 26"
                  :y="row.y + 34"
                >
                  {{
                    `${quantity.format(row.operation.quantity)} ${operationAssetId(row.operation)} · ${money.format(row.operation.unit_price)} / ${t("shared.candlestick.unit")} · ${t("shared.candlestick.fee", { value: preciseMoney.format(row.operation.fee) })}`
                  }}
                </text>
                <text
                  v-if="row.operation.chartAdjustment"
                  class="operation-tooltip-row-adjustment"
                  :x="row.x + 26"
                  :y="row.y + 47"
                >
                  {{
                    t("shared.candlestick.chartAdjustment", {
                      label: row.operation.chartAdjustment.label,
                    })
                  }}
                </text>
              </g>
            </template>
            <template v-else>
              <text
                class="operation-tooltip-value"
                :x="operationTooltip.x + 15"
                :y="operationTooltip.y + 60"
              >
                {{
                  `${quantity.format(operationTooltip.marker.quantity)} ${operationAssetId(operationTooltip.marker)} · ${money.format(operationTooltip.marker.unit_price)} / ${t("shared.candlestick.unit")}`
                }}
              </text>
              <text
                class="operation-tooltip-meta"
                :x="operationTooltip.x + 15"
                :y="operationTooltip.y + 79"
              >
                {{
                  t("shared.candlestick.totalAndFee", {
                    total: preciseMoney.format(
                      operationTooltip.marker.net_amount,
                    ),
                    fee: preciseMoney.format(operationTooltip.marker.fee),
                  })
                }}
              </text>
              <text
                v-if="operationTooltip.marker.chartAdjustment"
                class="operation-tooltip-adjustment"
                :x="operationTooltip.x + 15"
                :y="operationTooltip.y + 98"
              >
                {{
                  t("shared.candlestick.chartAdjustment", {
                    label: operationTooltip.marker.chartAdjustment.label,
                  })
                }}
              </text>
            </template>
          </g>
        </g>

        <g v-if="tooltip" class="chart-tooltip" aria-hidden="true">
          <line
            class="tooltip-guide"
            :x1="tooltip.candle.x"
            :x2="tooltip.candle.x"
            :y1="bounds.top"
            :y2="height - bounds.bottom"
          />
          <g class="tooltip-card-group">
            <rect
              class="tooltip-card"
              :x="tooltip.x"
              :y="tooltip.y"
              :width="tooltip.width"
              :height="tooltip.height"
              rx="10"
            />
            <rect
              class="tooltip-accent"
              :class="{
                rising: tooltip.candle.rising,
                falling: !tooltip.candle.rising,
              }"
              :x="tooltip.x"
              :y="tooltip.y + 9"
              width="3"
              :height="tooltip.height - 18"
              rx="1.5"
            />
            <text class="tooltip-date" :x="tooltip.x + 14" :y="tooltip.y + 21">
              {{
                longDate.format(new Date(`${tooltip.candle.fecha}T00:00:00Z`))
              }}
            </text>
            <text class="tooltip-value" :x="tooltip.x + 14" :y="tooltip.y + 43">
              {{
                t("shared.candlestick.close", {
                  value: money.format(tooltip.candle.close),
                })
              }}
            </text>
          </g>
        </g>
      </svg>
    </div>
  </div>
</template>

<style scoped>
.candlestick-scroll {
  width: 100%;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--fz-line) transparent;
}
.candlestick-stage {
  position: relative;
  min-width: 720px;
}
.candlestick-chart {
  width: 100%;
  display: block;
  color: var(--fz-muted);
  cursor: crosshair;
  user-select: none;
  touch-action: pan-y;
}
.chart-grid line {
  stroke: var(--fz-chart-grid);
  stroke-width: 1;
  vector-effect: non-scaling-stroke;
}
.chart-grid text,
.chart-dates text {
  fill: var(--fz-muted);
  font-size: 10px;
  font-weight: 620;
  font-variant-numeric: tabular-nums;
}
.chart-dates line {
  stroke: var(--fz-line);
  vector-effect: non-scaling-stroke;
}
.chart-dates text {
  text-anchor: middle;
}
.range-selection {
  pointer-events: none;
}
.range-selection rect {
  fill: color-mix(in srgb, var(--fz-accent) 9%, transparent);
}
.range-selection line {
  stroke: var(--fz-accent);
  stroke-width: 1.25;
  stroke-dasharray: 4 4;
  vector-effect: non-scaling-stroke;
}
.range-selection.is-down rect {
  fill: color-mix(in srgb, var(--fz-negative) 8%, transparent);
}
.range-selection.is-down line {
  stroke: var(--fz-negative);
}
.range-selection.is-flat rect {
  fill: color-mix(in srgb, var(--fz-muted) 8%, transparent);
}
.range-selection.is-flat line {
  stroke: var(--fz-muted);
}
.range-summary {
  position: absolute;
  z-index: 2;
  top: 12px;
  left: 50%;
  display: grid;
  grid-template-columns: auto auto;
  align-items: center;
  gap: 12px;
  padding: 8px 11px 8px 12px;
  color: var(--fz-chart-tooltip-text);
  background: var(--fz-chart-tooltip);
  border: 1px solid var(--fz-chart-tooltip-border);
  border-radius: 10px;
  box-shadow: 0 8px 18px var(--fz-chart-tooltip-shadow);
  backdrop-filter: blur(10px) saturate(120%);
  transform: translateX(-50%);
  pointer-events: none;
  white-space: nowrap;
}
.range-summary::before {
  content: "";
  width: 3px;
  align-self: stretch;
  grid-row: 1;
  background: var(--fz-accent);
  border-radius: 999px;
}
.range-summary-dates {
  grid-column: 2;
  color: var(--fz-chart-tooltip-muted);
  font-size: 10px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
.range-summary strong {
  grid-column: 3;
  color: var(--fz-accent);
  font-size: 12px;
  font-weight: 780;
  font-variant-numeric: tabular-nums;
}
.range-summary.is-down::before {
  background: var(--fz-negative);
}
.range-summary.is-down strong {
  color: var(--fz-negative);
}
.range-summary.is-flat::before {
  background: var(--fz-muted);
}
.range-summary.is-flat strong {
  color: var(--fz-chart-tooltip-muted);
}
.candles line {
  stroke-width: 1.25;
  vector-effect: non-scaling-stroke;
}
.candles rect {
  stroke-width: 0.7;
  vector-effect: non-scaling-stroke;
}
.candles .rising line,
.candles .rising rect {
  fill: var(--fz-chart-up, #3e9b78);
  stroke: var(--fz-chart-up, #3e9b78);
}
.candles .falling line,
.candles .falling rect {
  fill: var(--fz-chart-down, #c96f6b);
  stroke: var(--fz-chart-down, #c96f6b);
}
.average-price line {
  stroke: var(--fz-chart-average, #7d8790);
  stroke-width: 1.5;
  stroke-dasharray: 5 5;
  vector-effect: non-scaling-stroke;
}
.average-price text {
  fill: var(--fz-chart-average, #7d8790);
  font-size: 10px;
  font-weight: 740;
  text-anchor: end;
}
.operation-marker {
  cursor: help;
}
.operation-pin-connector {
  stroke: color-mix(in srgb, currentColor 58%, transparent);
  stroke-width: 1;
  stroke-dasharray: 2 2;
  pointer-events: none;
  vector-effect: non-scaling-stroke;
}
.operation-pin-body {
  transform-box: fill-box;
  transform-origin: center;
  transition:
    transform 140ms ease,
    filter 140ms ease;
}
.operation-pin-body rect {
  stroke: var(--fz-surface);
  stroke-width: 1.5;
  vector-effect: non-scaling-stroke;
}
.operation-pin-glyph {
  stroke: #fff;
  stroke-width: 1.75;
  stroke-linecap: round;
  pointer-events: none;
  vector-effect: non-scaling-stroke;
}
.operation-pin-count {
  fill: #fff;
  font-size: 9px;
  font-weight: 800;
  text-anchor: middle;
  dominant-baseline: central;
  pointer-events: none;
}
.operation-marker.buy {
  color: var(--fz-trade-buy-connector, #3b6ff5);
}
.operation-marker.sell {
  color: var(--fz-trade-sell-connector, #d97706);
}
.operation-marker.buy .operation-pin-body rect {
  fill: var(--fz-trade-buy, #3b6ff5);
  stroke: var(--fz-trade-buy-outline, var(--fz-surface));
}
.operation-marker.sell .operation-pin-body rect {
  fill: var(--fz-trade-sell, #d97706);
  stroke: var(--fz-trade-sell-outline, var(--fz-surface));
}
.operation-marker.active .operation-pin-body {
  transform: scale(1.12);
  filter: drop-shadow(0 3px 5px var(--fz-chart-tooltip-shadow));
}
.operation-hit {
  fill: transparent;
  stroke: none;
}
@media (prefers-reduced-motion: reduce) {
  .operation-pin-body {
    transition: none;
  }
}
.operation-tooltip {
  pointer-events: none;
}
.operation-tooltip .tooltip-card {
  fill: var(--fz-chart-operation-tooltip, var(--fz-chart-tooltip));
}
.operation-tooltip-leader {
  stroke: color-mix(in srgb, var(--fz-muted) 48%, transparent);
  stroke-width: 1;
  stroke-dasharray: 3 3;
  vector-effect: non-scaling-stroke;
}
.operation-tooltip-title {
  fill: var(--fz-chart-tooltip-text);
  font-size: 11px;
  font-weight: 780;
}
.operation-tooltip-date,
.operation-tooltip-meta {
  fill: var(--fz-chart-tooltip-muted);
  font-size: 10px;
  font-weight: 620;
}
.operation-tooltip-value {
  fill: var(--fz-chart-tooltip-text);
  font-size: 11px;
  font-weight: 720;
  font-variant-numeric: tabular-nums;
}
.operation-tooltip-meta {
  font-variant-numeric: tabular-nums;
}
.operation-tooltip-adjustment {
  fill: var(--fz-accent);
  font-size: 10px;
  font-weight: 720;
}
.operation-tooltip .tooltip-accent.rising {
  fill: var(--fz-trade-buy-outline);
}
.operation-tooltip .tooltip-accent.falling {
  fill: var(--fz-trade-sell-outline);
}
.operation-tooltip-divider {
  stroke: color-mix(in srgb, var(--fz-chart-tooltip-border) 72%, transparent);
  stroke-width: 1;
  vector-effect: non-scaling-stroke;
}
.operation-tooltip-dot.buy {
  fill: var(--fz-trade-buy-outline);
}
.operation-tooltip-dot.sell {
  fill: var(--fz-trade-sell-outline);
}
.operation-tooltip-row-account,
.operation-tooltip-row-total {
  fill: var(--fz-chart-tooltip-text);
  font-size: 10px;
  font-weight: 760;
}
.operation-tooltip-row-total {
  text-anchor: end;
  font-variant-numeric: tabular-nums;
}
.operation-tooltip-row-detail {
  fill: var(--fz-chart-tooltip-muted);
  font-size: 9px;
  font-weight: 620;
  font-variant-numeric: tabular-nums;
}
.operation-tooltip-row-adjustment {
  fill: var(--fz-accent);
  font-size: 8px;
  font-weight: 700;
}
.chart-tooltip {
  pointer-events: none;
}
.tooltip-guide {
  stroke: color-mix(in srgb, var(--fz-muted) 42%, transparent);
  stroke-width: 1;
  stroke-dasharray: 3 4;
  vector-effect: non-scaling-stroke;
}
.tooltip-card-group {
  filter: drop-shadow(0 8px 14px var(--fz-chart-tooltip-shadow));
}
.tooltip-card {
  fill: var(--fz-chart-tooltip);
  stroke: var(--fz-chart-tooltip-border);
  stroke-width: 1;
  vector-effect: non-scaling-stroke;
}
.tooltip-accent.rising {
  fill: #25b982;
}
.tooltip-accent.falling {
  fill: #dc6b67;
}
.tooltip-date {
  fill: var(--fz-chart-tooltip-muted);
  font-size: 10px;
  font-weight: 620;
}
.tooltip-value {
  fill: var(--fz-chart-tooltip-text);
  font-size: 12px;
  font-weight: 750;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}
</style>
