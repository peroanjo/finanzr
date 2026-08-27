<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { api, json } from "../api/client";
import type { AssetReturnMode } from "../components/AssetReturnToggle.vue";
import FundPerformanceChart from "../components/FundPerformanceChart.vue";
import FundPriceChart from "../components/FundPriceChart.vue";
import InvestmentAccountBar from "../components/investments/InvestmentAccountBar.vue";
import InvestmentAllocationStrip from "../components/investments/InvestmentAllocationStrip.vue";
import type { InvestmentAllocationItem } from "../components/investments/InvestmentAllocationStrip.vue";
import InvestmentOverview from "../components/investments/InvestmentOverview.vue";
import InvestmentMovementActions from "../components/investments/InvestmentMovementActions.vue";
import type {
  InvestmentAccountBarLabels,
  InvestmentImportConfig,
} from "../components/investments/InvestmentAccountBar.vue";
import type { InvestmentOverviewLabels } from "../components/investments/InvestmentOverview.vue";
import { reportingCurrency } from "../i18n";
import MovementDeleteDialog from "../components/MovementDeleteDialog.vue";
import MovementEditorDialog from "../components/MovementEditorDialog.vue";
import type {
  MovementDeleteHandle,
  MovementEditorHandle,
} from "../components/movementEditor";
import type {
  FundAccount,
  FundChartResponse,
  FundInstrument,
  FundOrder,
  FundPerformanceResponse,
  FundPerformancePoint,
  FundPosition,
  FundPrice,
  ImporterCatalogItem,
} from "../types/api";
import {
  adaptFundAccount,
  adaptFundChart,
  adaptFundPerformance,
  adaptFundPosition,
} from "../domain/investments";
import type { NormalizedPosition } from "../domain/investments";

type PerformanceRange = "6m" | "1y" | "2y" | "custom";
type PerformanceMode = "value" | "return";
type PositionSortKey =
  | "fund"
  | "type"
  | "contributed"
  | "shares"
  | "averagePrice"
  | "currentPrice"
  | "value"
  | "pnl"
  | "return";
type SortDirection = "asc" | "desc";

const { t, n, d, locale } = useI18n();

const accounts = ref<FundAccount[]>([]);
const importerCatalog = ref<ImporterCatalogItem[]>([]);
const positions = ref<FundPosition[]>([]);
const orders = ref<FundOrder[]>([]);
const instruments = ref<FundInstrument[]>([]);
const prices = ref<FundPrice[]>([]);
const performance = ref<FundPerformanceResponse | null>(null);
const fundChart = ref<FundChartResponse | null>(null);
const selectedAccount = ref(
  new URLSearchParams(window.location.search).get("account") ?? "all",
);
const selectedFund = ref("");
const range = ref<PerformanceRange>("1y");
const fundRange = ref<PerformanceRange>("1y");
const mode = ref<PerformanceMode>("value");
const loading = ref(true);
const performanceLoading = ref(false);
const fundChartLoading = ref(false);
const error = ref("");
const performanceError = ref("");
const fundChartError = ref("");
let dashboardGeneration = 0;
let performanceRequestGeneration = 0;
let fundChartRequestGeneration = 0;
const accountDialog = ref<HTMLDialogElement>();
const calendarDialog = ref<HTMLDialogElement>();
const fundPriceCalendarDialog = ref<HTMLDialogElement>();
const fundEditDialog = ref<HTMLDialogElement>();
const movementCalendarDialog = ref<HTMLDialogElement>();
const movementEditor = ref<MovementEditorHandle>();
const movementDelete = ref<MovementDeleteHandle>();
const accountDialogMode = ref<"create" | "edit">("create");
const accountName = ref("");
const accountProvider = ref("");
const accountType = ref("");
const accountImporter = ref("");
const accountCurrency = ref("EUR");
const accountBusy = ref(false);
const accountError = ref("");
const accountDeleteArmed = ref(false);
const refreshingPrices = ref(false);
const assetReturnMode = ref<AssetReturnMode>("percent");
const priceMessage = ref("");
const editingFund = ref<FundInstrument | null>(null);
const editFundName = ref("");
const editFundType = ref("");
const editFundSubtype = ref("");
const editFundTicker = ref("");
const editFundPrice = ref("");
const fundEditBusy = ref(false);
const fundEditError = ref("");
const movementFund = ref("all");
const movementType = ref("all");
const movementStart = ref("");
const movementEnd = ref("");
const movementPage = ref(1);
const movementDraftStart = ref("");
const movementDraftEnd = ref("");
const positionsCollapsed = ref(
  localStorage.getItem("finanzr-funds-positions-collapsed") === "true",
);
const movementsCollapsed = ref(
  localStorage.getItem("finanzr-funds-movements-collapsed") === "true",
);
const positionSortKey = ref<PositionSortKey>("value");
const positionSortDirection = ref<SortDirection>("desc");
const fundBaseCurrency = computed(() => reportingCurrency.value);

const today = new Date();
const yearAgo = new Date(today);
yearAgo.setFullYear(yearAgo.getFullYear() - 1);
const dateInput = (date: Date) => date.toISOString().slice(0, 10);
const customStart = ref(dateInput(yearAgo));
const customEnd = ref(dateInput(today));
const draftStart = ref(customStart.value);
const draftEnd = ref(customEnd.value);
const fundCustomStart = ref(customStart.value);
const fundCustomEnd = ref(customEnd.value);
const fundDraftStart = ref(fundCustomStart.value);
const fundDraftEnd = ref(fundCustomEnd.value);

const ranges = computed<Array<{ key: PerformanceRange; label: string }>>(() => [
  { key: "6m", label: t("funds.ranges.sixMonths") },
  { key: "1y", label: t("funds.ranges.oneYear") },
  { key: "2y", label: t("funds.ranges.twoYears") },
  { key: "custom", label: t("funds.ranges.calendar") },
]);
const customRangeValid = computed(() =>
  Boolean(
    draftStart.value &&
    draftEnd.value &&
    Date.parse(draftStart.value) <= Date.parse(draftEnd.value),
  ),
);
const fundCustomRangeValid = computed(() =>
  Boolean(
    fundDraftStart.value &&
    fundDraftEnd.value &&
    Date.parse(fundDraftStart.value) <= Date.parse(fundDraftEnd.value),
  ),
);
const selectedAccountRow = computed(
  () =>
    accounts.value.find((item) => String(item.id) === selectedAccount.value) ??
    null,
);
const compatibleImporters = computed(() =>
  importerCatalog.value.filter((item) => item.target === "fund_orders"),
);
const selectedImporter = computed(
  () =>
    compatibleImporters.value.find(
      (item) => item.slug === selectedAccountRow.value?.importer_slug,
    ) ?? null,
);
const selectedAccountLabel = computed(() =>
  selectedAccount.value === "all"
    ? t("funds.accounts.all")
    : (selectedAccountRow.value?.nombre ?? t("funds.accounts.fallback")),
);
const openPositions = computed(() =>
  [...positions.value]
    .filter((item) => item.participaciones > 0)
    .sort((a, b) => (b.valor_actual ?? 0) - (a.valor_actual ?? 0)),
);
const topPositions = computed(() => openPositions.value.slice(0, 5));
const normalizedAccounts = computed(() => accounts.value.map(adaptFundAccount));
const normalizedPosition = (position: FundPosition): NormalizedPosition =>
  adaptFundPosition(
    position,
    instruments.value.find((item) => item.isin === position.isin),
    { baseCurrency: fundBaseCurrency.value },
  );
const normalizedTopPositions = computed(() =>
  topPositions.value.map(normalizedPosition),
);
const accountBarLabels = computed<InvestmentAccountBarLabels>(() => ({
  portfolioView: t("funds.accounts.portfolioView"),
  accountAria: t("funds.accounts.aria"),
  allAccounts: t("funds.accounts.all"),
  importStatement: t("funds.accounts.importStatement"),
  manage: t("funds.accounts.manage"),
  add: t("funds.accounts.add"),
}));
const overviewLabels = computed<InvestmentOverviewLabels>(() => ({
  assets: {
    section: t("funds.assets.section"),
    title: t("funds.assets.title"),
    asset: t("funds.assets.asset"),
    portfolioValue: t("funds.assets.portfolioValue"),
    contributed: t("funds.assets.contributed"),
    currentPrice: t("funds.assets.currentPrice"),
    averagePrice: t("funds.assets.averagePrice"),
    value: t("funds.assets.value"),
    return: t("funds.assets.return"),
    pnl: t("funds.assets.pnl"),
    pending: t("funds.positions.pending"),
    emptyTitle: t("funds.assets.emptyTitle"),
    emptyDescription: t("funds.assets.emptyDescription"),
  },
  kpis: {
    section: t("funds.kpis.section"),
    title: t("funds.kpis.title"),
    portfolioValue: t("funds.kpis.portfolioValue"),
    openAsset: t("funds.kpis.openAsset"),
    openAssets: t("funds.kpis.openAssets"),
    unrealizedPnl: t("funds.kpis.unrealizedPnl"),
    versusCost: t("funds.kpis.versusCost"),
    realizedPnl: t("funds.kpis.realizedPnl"),
    recordedSales: t("funds.kpis.recordedSales"),
    totalPnl: t("funds.kpis.totalPnl"),
    realizedAndOpen: t("funds.kpis.realizedAndOpen"),
    marketData: t("funds.kpis.marketData"),
    updating: t("funds.kpis.updating"),
    update: t("funds.kpis.update"),
  },
}));
const importConfig = computed<InvestmentImportConfig | null>(() =>
  selectedImporter.value
    ? {
        endpoint: `/account-imports/funds/${selectedAccount.value}`,
        accountsEndpoint: "/fund-accounts",
        accountId: selectedAccount.value,
        accountLabel: selectedAccountLabel.value,
        importerLabel: selectedImporter.value.display_name,
        compatibility: selectedImporter.value.description,
        accept: selectedImporter.value.accepted_extensions.join(","),
        fileHint: selectedImporter.value.formats
          .map((item) => item.label)
          .join(" · "),
      }
    : null,
);
const totalInvested = computed(() =>
  openPositions.value.reduce((total, item) => total + item.total_invertido, 0),
);
const totalValue = computed(() =>
  openPositions.value.reduce(
    (total, item) => total + (item.valor_actual ?? 0),
    0,
  ),
);
const unrealizedPnl = computed(() =>
  openPositions.value.reduce((total, item) => total + (item.pnl ?? 0), 0),
);
const openReturn = computed(() =>
  totalInvested.value ? unrealizedPnl.value / totalInvested.value : 0,
);
const realizedPnl = computed(() => calculateRealizedPnl(orders.value));
const totalPnl = computed(() => unrealizedPnl.value + realizedPnl.value);
const latestUpdate = computed(() => {
  const dates = prices.value
    .map((item) => item.updated)
    .filter(Boolean)
    .sort();
  return dates.length
    ? d(new Date(`${dates.at(-1)}T00:00:00`), "short")
    : t("funds.kpis.neverUpdated");
});
const normalizedPerformance = computed(() =>
  performance.value
    ? adaptFundPerformance(performance.value, {
        baseCurrency: fundBaseCurrency.value,
      })
    : null,
);
const performancePoints = computed<FundPerformancePoint[]>(
  () =>
    normalizedPerformance.value?.data.map((item) => ({
      fecha: item.date,
      valor: item.value,
      invertido: item.invested,
      pnl: item.pnl,
      pnl_pct: item.pnlPercent,
    })) ?? [],
);
const firstPerformance = computed(() => performancePoints.value[0] ?? null);
const lastPerformance = computed(() => performancePoints.value.at(-1) ?? null);
const periodPnl = computed(() => {
  if (!firstPerformance.value || !lastPerformance.value) return 0;
  return lastPerformance.value.pnl - firstPerformance.value.pnl;
});
const periodPnlPercent = computed(() =>
  firstPerformance.value?.valor
    ? periodPnl.value / firstPerformance.value.valor
    : 0,
);
const displayedRange = computed(() => {
  const points = performancePoints.value;
  if (points.length) {
    return `${displayDate(points[0].fecha)} → ${displayDate(points.at(-1)?.fecha ?? points[0].fecha)}`;
  }
  if (range.value === "custom") {
    return `${displayDate(customStart.value)} → ${displayDate(customEnd.value)}`;
  }
  return (
    ranges.value.find((item) => item.key === range.value)?.label ??
    t("funds.ranges.period")
  );
});
const periodLabel = computed(() =>
  range.value === "custom"
    ? t("funds.performance.periodPnl")
    : t("funds.performance.rangePnl", {
        range:
          ranges.value.find((item) => item.key === range.value)?.label ?? "",
      }),
);
const selectedFundPosition = computed(
  () =>
    positions.value.find((item) => item.isin === selectedFund.value) ?? null,
);
const selectedFundOrders = computed(() =>
  orders.value.filter((item) => item.isin === selectedFund.value),
);
const normalizedFundChart = computed(() =>
  fundChart.value
    ? adaptFundChart(fundChart.value, { baseCurrency: fundBaseCurrency.value })
    : null,
);
const fundChartPoints = computed(
  () =>
    normalizedFundChart.value?.data.map((item) => ({
      fecha: item.date,
      precio: item.price,
    })) ?? [],
);
const marketValuePalette = [
  "#3ddc97",
  "#5b8def",
  "#d69b3d",
  "#9b7be8",
  "#e67b78",
];
const otherMarketValueColor = "#78909c";

function isPositiveFinite(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

const marketValueAllocationItems = computed(() => {
  const valuedPositions = openPositions.value
    .flatMap((item) => {
      const value = item.valor_actual;
      return isPositiveFinite(value) ? [{ item, value }] : [];
    })
    .sort(
      (left, right) =>
        right.value - left.value ||
        left.item.isin.localeCompare(right.item.isin),
    );
  const total = valuedPositions.reduce((sum, item) => sum + item.value, 0);
  if (!isPositiveFinite(total)) return [];
  const largestPositions = valuedPositions
    .slice(0, 5)
    .map(({ item, value }, index) => ({
      key: item.isin,
      label: item.nombre,
      value,
      share: value / total,
      color: marketValuePalette[index],
    }));
  const otherValue = valuedPositions
    .slice(5)
    .reduce((sum, item) => sum + item.value, 0);
  if (!isPositiveFinite(otherValue)) return largestPositions;
  return [
    ...largestPositions,
    {
      key: "other",
      label: t("funds.positions.other"),
      value: otherValue,
      share: otherValue / total,
      color: otherMarketValueColor,
    },
  ];
});
const marketValueAllocationTotal = computed(() =>
  marketValueAllocationItems.value.reduce((sum, item) => sum + item.value, 0),
);
const fundChartRangeLabel = computed(() => {
  const points = fundChart.value?.data ?? [];
  if (points.length) {
    return `${displayDate(points[0].fecha)} → ${displayDate(points.at(-1)?.fecha ?? points[0].fecha)}`;
  }
  if (fundRange.value === "custom") {
    return `${displayDate(fundCustomStart.value)} → ${displayDate(fundCustomEnd.value)}`;
  }
  return (
    ranges.value.find((item) => item.key === fundRange.value)?.label ??
    t("funds.ranges.period")
  );
});
const latestPriceByIsin = computed(
  () => new Map(prices.value.map((item) => [item.isin, item])),
);
const pricedPositions = computed(
  () =>
    positions.value.filter((item) => latestPriceByIsin.value.has(item.isin))
      .length,
);
const positionSortColumns = computed<
  Array<{ key: PositionSortKey; label: string }>
>(() => [
  { key: "fund", label: t("funds.positions.fund") },
  { key: "type", label: t("funds.positions.type") },
  { key: "contributed", label: t("funds.positions.contributed") },
  { key: "shares", label: t("funds.positions.shares") },
  { key: "averagePrice", label: t("funds.positions.averagePrice") },
  { key: "currentPrice", label: t("funds.positions.currentPrice") },
  { key: "value", label: t("funds.positions.value") },
  { key: "pnl", label: "P&L" },
  { key: "return", label: t("funds.positions.return") },
]);
const sortedPositions = computed(() => {
  const collator = new Intl.Collator(locale.value, {
    numeric: true,
    sensitivity: "base",
  });
  const valueFor = (position: FundPosition): string | number | null => {
    switch (positionSortKey.value) {
      case "fund":
        return position.nombre;
      case "type":
        return `${position.tipo} ${position.subtipo}`.trim();
      case "contributed":
        return position.total_invertido;
      case "shares":
        return position.participaciones;
      case "averagePrice":
        return position.precio_medio;
      case "currentPrice":
        return position.precio_actual;
      case "value":
        return position.valor_actual;
      case "pnl":
        return position.pnl;
      case "return":
        return position.pnl_pct;
    }
  };

  return [...positions.value].sort((left, right) => {
    const leftValue = valueFor(left);
    const rightValue = valueFor(right);
    if (leftValue == null && rightValue == null)
      return collator.compare(left.nombre, right.nombre);
    if (leftValue == null) return 1;
    if (rightValue == null) return -1;

    const comparison =
      typeof leftValue === "string" && typeof rightValue === "string"
        ? collator.compare(leftValue, rightValue)
        : Number(leftValue) - Number(rightValue);
    if (comparison === 0) return collator.compare(left.nombre, right.nombre);
    return positionSortDirection.value === "asc" ? comparison : -comparison;
  });
});
const movementRangeValid = computed(() =>
  Boolean(
    movementDraftStart.value &&
    movementDraftEnd.value &&
    Date.parse(movementDraftStart.value) <= Date.parse(movementDraftEnd.value),
  ),
);
const filteredOrders = computed(() =>
  [...orders.value]
    .filter(
      (item) =>
        movementFund.value === "all" || item.isin === movementFund.value,
    )
    .filter(
      (item) =>
        movementType.value === "all" ||
        operationGroup(item) === movementType.value,
    )
    .filter(
      (item) =>
        !movementStart.value || item.fecha_operacion >= movementStart.value,
    )
    .filter(
      (item) => !movementEnd.value || item.fecha_operacion <= movementEnd.value,
    )
    .sort((a, b) =>
      b.fecha_operacion.localeCompare(a.fecha_operacion, locale.value),
    ),
);
const movementPageSize = 15;
const movementPages = computed(() =>
  Math.max(1, Math.ceil(filteredOrders.value.length / movementPageSize)),
);
const displayedOrders = computed(() =>
  filteredOrders.value.slice(
    (movementPage.value - 1) * movementPageSize,
    movementPage.value * movementPageSize,
  ),
);
const movementRangeLabel = computed(() =>
  movementStart.value && movementEnd.value
    ? `${displayDate(movementStart.value)} → ${displayDate(movementEnd.value)}`
    : t("funds.movements.allHistory"),
);
const movementAssets = computed(() =>
  instruments.value.map((item) => ({
    id: item.isin,
    label: `${item.nombre} · ${item.isin}`,
    currency: item.moneda,
  })),
);

function displayDate(value: string) {
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? "—"
    : d(date, { year: "numeric", month: "2-digit", day: "2-digit" });
}

function money(value: number) {
  return n(value, "currency");
}

function originalMoney(value: number, currency?: string) {
  const code = currency || "EUR";
  return n(value, {
    style: "currency",
    currency: code,
    maximumFractionDigits: 2,
  });
}

function baseAmount(item: FundOrder) {
  return item.importe_base ?? item.importe_neto;
}

function baseUnitPrice(item: FundOrder) {
  return item.precio_base ?? item.precio_neto;
}

function percentage(value: number) {
  return n(value, "percent");
}

function marketValueSegmentAria(item: InvestmentAllocationItem) {
  return t("funds.positions.marketValueSegmentAria", {
    fund: item.label,
    share: percentage(item.share),
  });
}

function quantity(value: number, maximumFractionDigits: number) {
  return n(value, { maximumFractionDigits });
}

function signedMoney(value: number) {
  return `${value >= 0 ? "+" : "−"}${money(Math.abs(value))}`;
}

function operationGroup(item: FundOrder) {
  return ["SUSCRIPCION", "SUSCR.POR TRASPASO I", "Compra"].includes(
    item.tipo_operacion,
  )
    ? "in"
    : "out";
}

function operationLabel(item: FundOrder) {
  return (
    {
      SUSCRIPCION: t("funds.movements.contribution"),
      "SUSCR.POR TRASPASO I": t("funds.movements.transferIn"),
      "REEMB.POR TRASPASO I": t("funds.movements.transferOut"),
      REEMBOLSO: t("funds.movements.redemption"),
      Compra: t("funds.movements.contribution"),
      Venta: t("funds.movements.redemption"),
    }[item.tipo_operacion] ?? item.tipo_operacion
  );
}

function calculateRealizedPnl(items: FundOrder[]) {
  const buyTypes = new Set(["SUSCRIPCION", "SUSCR.POR TRASPASO I"]);
  const sellTypes = new Set(["REEMB.POR TRASPASO I", "REEMBOLSO"]);
  const grouped = new Map<string, FundOrder[]>();
  items.forEach((item) => {
    grouped.set(item.isin, [...(grouped.get(item.isin) ?? []), item]);
  });
  let total = 0;
  grouped.forEach((fundOrders) => {
    let boughtQuantity = 0;
    let buyCost = 0;
    let soldQuantity = 0;
    let saleValue = 0;
    fundOrders.forEach((item) => {
      if (buyTypes.has(item.tipo_operacion)) {
        boughtQuantity += item.titulos;
        buyCost += baseAmount(item);
      } else if (sellTypes.has(item.tipo_operacion)) {
        soldQuantity += item.titulos;
        saleValue += baseAmount(item);
      }
    });
    if (boughtQuantity > 0 && soldQuantity > 0) {
      total += saleValue - (buyCost / boughtQuantity) * soldQuantity;
    }
  });
  return total;
}

function accountQuery() {
  return selectedAccount.value === "all"
    ? ""
    : `?cuenta_id=${encodeURIComponent(selectedAccount.value)}`;
}

function performanceQuery() {
  const account = `cuenta_id=${encodeURIComponent(selectedAccount.value)}`;
  if (range.value === "custom") {
    return `${account}&start=${encodeURIComponent(customStart.value)}&end=${encodeURIComponent(customEnd.value)}`;
  }
  return `${account}&range=${range.value}`;
}

async function loadDashboard(showLoading = true) {
  const generation = ++dashboardGeneration;
  performanceRequestGeneration += 1;
  fundChartRequestGeneration += 1;
  performanceLoading.value = false;
  fundChartLoading.value = false;
  performanceError.value = "";
  fundChartError.value = "";
  if (showLoading) loading.value = true;
  error.value = "";
  try {
    const [nextAccounts, nextImporterCatalog] = await Promise.all([
      api<FundAccount[]>("/fund-accounts"),
      api<ImporterCatalogItem[]>("/importers"),
    ]);
    if (generation !== dashboardGeneration) return;
    accounts.value = nextAccounts;
    importerCatalog.value = nextImporterCatalog;
    if (
      selectedAccount.value !== "all" &&
      !accounts.value.some((item) => String(item.id) === selectedAccount.value)
    ) {
      selectedAccount.value = "all";
      syncAccountUrl();
    }
    const query = accountQuery();
    const [nextPositions, nextOrders, nextInstruments, nextPrices] =
      await Promise.all([
        api<FundPosition[]>(`/fund-analysis${query}`),
        api<FundOrder[]>(`/orders${query}`),
        api<FundInstrument[]>("/funds"),
        api<FundPrice[]>("/fund-prices"),
      ]);
    if (generation !== dashboardGeneration) return;
    positions.value = nextPositions;
    orders.value = nextOrders;
    instruments.value = nextInstruments;
    prices.value = nextPrices;
    const available = positions.value.map((item) => item.isin);
    if (selectedFund.value && !available.includes(selectedFund.value))
      closeFundDetail();
    if (!movementStart.value && orders.value.length) {
      const dates = orders.value.map((item) => item.fecha_operacion).sort();
      movementStart.value = dates[0];
      movementEnd.value = dates.at(-1) ?? dates[0];
    }
  } catch (reason) {
    if (generation !== dashboardGeneration) return;
    error.value =
      reason instanceof Error ? reason.message : t("funds.errors.load");
  } finally {
    if (showLoading && generation === dashboardGeneration)
      loading.value = false;
  }
  if (generation !== dashboardGeneration || error.value) return;
  const chartRequest = selectedFund.value
    ? loadFundChart(generation)
    : Promise.resolve();
  await Promise.all([loadPerformance(generation), chartRequest]);
}

async function loadPerformance(generation = dashboardGeneration) {
  if (generation !== dashboardGeneration) return;
  const requestGeneration = ++performanceRequestGeneration;
  performanceLoading.value = true;
  performanceError.value = "";
  try {
    const nextPerformance = await api<FundPerformanceResponse>(
      `/investment-performance/fund?${performanceQuery()}`,
    );
    if (
      generation !== dashboardGeneration ||
      requestGeneration !== performanceRequestGeneration
    )
      return;
    performance.value = nextPerformance;
  } catch (reason) {
    if (
      generation !== dashboardGeneration ||
      requestGeneration !== performanceRequestGeneration
    )
      return;
    performance.value = null;
    performanceError.value =
      reason instanceof Error ? reason.message : t("funds.errors.performance");
  } finally {
    if (
      generation === dashboardGeneration &&
      requestGeneration === performanceRequestGeneration
    ) {
      performanceLoading.value = false;
    }
  }
}

function fundChartQuery() {
  if (fundRange.value === "custom") {
    return `start=${encodeURIComponent(fundCustomStart.value)}&end=${encodeURIComponent(fundCustomEnd.value)}`;
  }
  const interval = fundRange.value === "2y" ? "1wk" : "1d";
  return `range=${fundRange.value}&interval=${interval}`;
}

async function loadFundChart(generation = dashboardGeneration) {
  if (generation !== dashboardGeneration) return;
  const requestGeneration = ++fundChartRequestGeneration;
  if (!selectedFund.value) {
    fundChart.value = null;
    fundChartLoading.value = false;
    fundChartError.value = "";
    return;
  }
  fundChart.value = null;
  fundChartLoading.value = true;
  fundChartError.value = "";
  try {
    const nextFundChart = await api<FundChartResponse>(
      `/fund-chart/${encodeURIComponent(selectedFund.value)}?${fundChartQuery()}`,
    );
    if (
      generation !== dashboardGeneration ||
      requestGeneration !== fundChartRequestGeneration
    )
      return;
    fundChart.value = nextFundChart;
  } catch (reason) {
    if (
      generation !== dashboardGeneration ||
      requestGeneration !== fundChartRequestGeneration
    )
      return;
    fundChart.value = null;
    fundChartError.value =
      reason instanceof Error ? reason.message : t("funds.errors.chart");
  } finally {
    if (
      generation === dashboardGeneration &&
      requestGeneration === fundChartRequestGeneration
    ) {
      fundChartLoading.value = false;
    }
  }
}

async function selectFund(isin: string) {
  selectedFund.value = isin;
  await loadFundChart();
}

function closeFundDetail() {
  selectedFund.value = "";
  fundChartRequestGeneration += 1;
  fundChart.value = null;
  fundChartLoading.value = false;
  fundChartError.value = "";
}

async function toggleFund(isin: string) {
  if (selectedFund.value === isin) {
    closeFundDetail();
    return;
  }
  await selectFund(isin);
}

function fundDetailId(isin: string) {
  const safeIsin =
    Array.from(isin)
      .map((character) =>
        /[a-z0-9_-]/i.test(character)
          ? character.toLowerCase()
          : `x${character.codePointAt(0)?.toString(16) ?? "0"}x`,
      )
      .join("") || "fund";
  return `fund-price-detail-${safeIsin}`;
}

async function selectFundRange(value: PerformanceRange) {
  if (value === "custom") {
    fundDraftStart.value = fundCustomStart.value;
    fundDraftEnd.value = fundCustomEnd.value;
    fundPriceCalendarDialog.value?.showModal();
    return;
  }
  fundRange.value = value;
  await loadFundChart();
}

function closeFundPriceCalendar() {
  fundPriceCalendarDialog.value?.close();
}

async function applyFundCustomRange() {
  if (!fundCustomRangeValid.value) return;
  fundCustomStart.value = fundDraftStart.value;
  fundCustomEnd.value = fundDraftEnd.value;
  fundRange.value = "custom";
  closeFundPriceCalendar();
  await loadFundChart();
}

function syncAccountUrl() {
  const url = new URL(window.location.href);
  if (selectedAccount.value === "all") url.searchParams.delete("account");
  else url.searchParams.set("account", selectedAccount.value);
  window.history.replaceState(window.history.state, "", url);
}

async function changeAccount(account: string) {
  selectedAccount.value = account;
  movementStart.value = "";
  movementEnd.value = "";
  closeFundDetail();
  syncAccountUrl();
  await loadDashboard(false);
}

async function selectRange(value: PerformanceRange) {
  if (value === "custom") {
    draftStart.value = customStart.value;
    draftEnd.value = customEnd.value;
    calendarDialog.value?.showModal();
    return;
  }
  range.value = value;
  await loadPerformance();
}

function closeCalendar() {
  calendarDialog.value?.close();
}

async function applyCustomRange() {
  if (!customRangeValid.value) return;
  customStart.value = draftStart.value;
  customEnd.value = draftEnd.value;
  range.value = "custom";
  closeCalendar();
  await loadPerformance();
}

function openAccountDialog() {
  accountDialogMode.value = "create";
  accountName.value = "";
  accountProvider.value = "";
  accountType.value = "";
  accountImporter.value = "";
  accountCurrency.value = "EUR";
  accountError.value = "";
  accountDeleteArmed.value = false;
  accountDialog.value?.showModal();
}

function openEditAccountDialog() {
  const account = accounts.value.find(
    (item) => String(item.id) === selectedAccount.value,
  );
  if (!account) return;
  accountDialogMode.value = "edit";
  accountName.value = account.nombre;
  accountProvider.value = account.plataforma;
  accountType.value = account.tipo;
  accountImporter.value = account.importer_slug || "none";
  accountCurrency.value = account.moneda || "EUR";
  accountError.value = "";
  accountDeleteArmed.value = false;
  accountDialog.value?.showModal();
}

function closeAccountDialog() {
  if (!accountBusy.value) accountDialog.value?.close();
}

async function saveAccount() {
  const name = accountName.value.trim();
  const provider = accountProvider.value.trim();
  if (!name || !provider || !accountImporter.value) return;
  accountBusy.value = true;
  accountError.value = "";
  try {
    const target =
      accountDialogMode.value === "edit"
        ? `/fund-accounts/${selectedAccount.value}`
        : "/fund-accounts";
    const saved = await api<FundAccount>(
      target,
      json(accountDialogMode.value === "edit" ? "PUT" : "POST", {
        nombre: name,
        plataforma: provider,
        tipo: accountType.value.trim(),
        importer_slug: accountImporter.value,
        moneda: accountCurrency.value.trim().toUpperCase(),
      }),
    );
    selectedAccount.value = String(saved.id);
    syncAccountUrl();
    accountDialog.value?.close();
    await loadDashboard();
  } catch (reason) {
    accountError.value =
      reason instanceof Error ? reason.message : t("funds.errors.saveAccount");
  } finally {
    accountBusy.value = false;
  }
}

async function deleteAccount() {
  if (!accountDeleteArmed.value) {
    accountDeleteArmed.value = true;
    return;
  }
  accountBusy.value = true;
  accountError.value = "";
  try {
    await api(`/fund-accounts/${selectedAccount.value}`, { method: "DELETE" });
    selectedAccount.value = "all";
    movementStart.value = "";
    movementEnd.value = "";
    syncAccountUrl();
    accountDialog.value?.close();
    await loadDashboard();
  } catch (reason) {
    accountError.value =
      reason instanceof Error
        ? reason.message
        : t("funds.errors.deleteAccount");
  } finally {
    accountBusy.value = false;
  }
}

async function refreshFundPrices() {
  refreshingPrices.value = true;
  priceMessage.value = "";
  try {
    const response = await api<{ results: Array<{ error: string | null }> }>(
      "/fund-prices/fetch",
      { method: "POST" },
    );
    const failures = response.results.filter((item) => item.error).length;
    priceMessage.value = failures
      ? t("funds.prices.updatedWithErrors", {
          updated: response.results.length - failures,
          failed: failures,
        })
      : t("funds.prices.updated", { count: response.results.length });
    await loadDashboard();
  } catch (reason) {
    priceMessage.value =
      reason instanceof Error
        ? reason.message
        : t("funds.errors.refreshPrices");
  } finally {
    refreshingPrices.value = false;
  }
}

function openFundEditor(position: FundPosition) {
  editingFund.value = instruments.value.find(
    (item) => item.isin === position.isin,
  ) ?? {
    isin: position.isin,
    ticker: "",
    nombre: position.nombre,
    tipo: position.tipo,
    subtipo: position.subtipo,
  };
  editFundName.value = editingFund.value.nombre;
  editFundType.value = editingFund.value.tipo;
  editFundSubtype.value = editingFund.value.subtipo;
  editFundTicker.value = editingFund.value.ticker;
  const nativePrice = latestPriceByIsin.value.get(position.isin)?.precio_orig;
  editFundPrice.value = nativePrice == null ? "" : String(nativePrice);
  fundEditError.value = "";
  fundEditDialog.value?.showModal();
}

async function saveFundEditor() {
  if (!editingFund.value || !editFundName.value.trim()) return;
  fundEditBusy.value = true;
  fundEditError.value = "";
  try {
    await api(
      `/funds/${editingFund.value.isin}`,
      json("PUT", {
        nombre: editFundName.value.trim(),
        tipo: editFundType.value.trim(),
        subtipo: editFundSubtype.value.trim(),
        ticker: editFundTicker.value.trim(),
      }),
    );
    if (editFundPrice.value !== "") {
      await api(
        `/fund-prices/${editingFund.value.isin}`,
        json("PUT", {
          precio: Number(editFundPrice.value),
          moneda: editingFund.value.moneda ?? "EUR",
        }),
      );
    }
    fundEditDialog.value?.close();
    await loadDashboard();
  } catch (reason) {
    fundEditError.value =
      reason instanceof Error ? reason.message : t("funds.errors.saveFund");
  } finally {
    fundEditBusy.value = false;
  }
}

function openMovementCalendar() {
  movementDraftStart.value = movementStart.value;
  movementDraftEnd.value = movementEnd.value;
  movementCalendarDialog.value?.showModal();
}

function applyMovementRange() {
  if (!movementRangeValid.value) return;
  movementStart.value = movementDraftStart.value;
  movementEnd.value = movementDraftEnd.value;
  movementCalendarDialog.value?.close();
}

watch([movementFund, movementType, movementStart, movementEnd], () => {
  movementPage.value = 1;
});

function togglePositions() {
  positionsCollapsed.value = !positionsCollapsed.value;
  localStorage.setItem(
    "finanzr-funds-positions-collapsed",
    String(positionsCollapsed.value),
  );
}

function toggleMovements() {
  movementsCollapsed.value = !movementsCollapsed.value;
  localStorage.setItem(
    "finanzr-funds-movements-collapsed",
    String(movementsCollapsed.value),
  );
}

function sortPositions(key: PositionSortKey) {
  if (positionSortKey.value === key) {
    positionSortDirection.value =
      positionSortDirection.value === "asc" ? "desc" : "asc";
    return;
  }
  positionSortKey.value = key;
  positionSortDirection.value = "asc";
}

function positionAriaSort(key: PositionSortKey) {
  if (positionSortKey.value !== key) return "none";
  return positionSortDirection.value === "asc" ? "ascending" : "descending";
}

function positionSortAria(key: PositionSortKey, label: string) {
  const nextDirection =
    positionSortKey.value === key && positionSortDirection.value === "asc"
      ? "funds.positions.sortDescendingAria"
      : "funds.positions.sortAscendingAria";
  return t(nextDirection, { column: label });
}

function askDeleteOrder(order: FundOrder) {
  movementDelete.value?.open(order);
}

function openNewMovement() {
  movementEditor.value?.openCreate();
}

function openEditMovement(order: FundOrder) {
  movementEditor.value?.openEdit(order);
}

onMounted(loadDashboard);
</script>

<template>
  <section class="funds-page" aria-live="polite">
    <div
      v-if="loading"
      class="funds-loading"
      :aria-label="t('funds.loadingAria')"
    >
      <div />
      <div />
    </div>

    <div v-else-if="error" class="overview-error" role="alert">
      <span aria-hidden="true">!</span>
      <div>
        <strong>{{ t("funds.errors.load") }}</strong>
        <p>{{ error }}</p>
      </div>
      <button type="button" @click="loadDashboard()">
        {{ t("funds.actions.retry") }}
      </button>
    </div>

    <template v-else>
      <InvestmentAccountBar
        :accounts="normalizedAccounts"
        :selected-account="selectedAccount"
        :selected-account-label="selectedAccountLabel"
        :labels="accountBarLabels"
        :import-config="importConfig"
        @change-account="changeAccount"
        @open-account-dialog="openAccountDialog"
        @open-account-editor="openEditAccountDialog"
        @imported="loadDashboard"
      />

      <InvestmentOverview
        :top-positions="normalizedTopPositions"
        :open-positions-count="openPositions.length"
        :total-value="totalValue"
        :unrealized-pnl="unrealizedPnl"
        :open-return="openReturn"
        :realized-pnl="realizedPnl"
        :total-pnl="totalPnl"
        :latest-update="latestUpdate"
        :price-message="priceMessage"
        :refreshing-prices="refreshingPrices"
        :currency-label="fundBaseCurrency"
        :asset-return-mode="assetReturnMode"
        :labels="overviewLabels"
        :format-money="money"
        :format-percentage="percentage"
        :format-signed-money="signedMoney"
        @update:asset-return-mode="assetReturnMode = $event"
        @refresh="refreshFundPrices"
      />

      <article class="fund-performance-panel">
        <header class="fund-performance-header">
          <div>
            <p class="section-label">{{ t("funds.performance.section") }}</p>
            <h2>{{ t("funds.performance.title") }}</h2>
            <p class="fund-range-label">
              {{ selectedAccountLabel }} · {{ displayedRange }}
            </p>
          </div>
          <div class="fund-chart-controls">
            <div
              class="fund-mode-control"
              :aria-label="t('funds.performance.chartModeAria')"
            >
              <button
                type="button"
                :class="{ active: mode === 'value' }"
                :aria-pressed="mode === 'value'"
                @click="mode = 'value'"
              >
                {{ t("funds.performance.portfolioValue") }}
              </button>
              <button
                type="button"
                :class="{ active: mode === 'return' }"
                :aria-pressed="mode === 'return'"
                @click="mode = 'return'"
              >
                {{ t("funds.performance.returnPercent") }}
              </button>
            </div>
            <div
              class="fund-range-control"
              :aria-label="t('funds.performance.rangeAria')"
            >
              <button
                v-for="item in ranges"
                :key="item.key"
                type="button"
                :class="{ active: range === item.key }"
                :aria-pressed="range === item.key"
                @click="selectRange(item.key)"
              >
                {{ item.label }}
              </button>
            </div>
          </div>
        </header>

        <div class="fund-period-kpis">
          <div>
            <small>{{ t("funds.performance.closingValue") }}</small>
            <strong>{{ money(lastPerformance?.valor ?? totalValue) }}</strong>
          </div>
          <div>
            <small>{{ t("funds.performance.contributedCapital") }}</small>
            <strong>{{
              money(lastPerformance?.invertido ?? totalInvested)
            }}</strong>
          </div>
          <div>
            <small>{{ t("funds.performance.totalPnl") }}</small>
            <strong
              :class="{
                positive: (lastPerformance?.pnl ?? 0) >= 0,
                negative: (lastPerformance?.pnl ?? 0) < 0,
              }"
            >
              {{ signedMoney(lastPerformance?.pnl ?? 0) }}
            </strong>
            <span>{{ percentage((lastPerformance?.pnl_pct ?? 0) / 100) }}</span>
          </div>
          <div>
            <small>{{ t("funds.performance.realizedPnl") }}</small>
            <strong
              :class="{ positive: realizedPnl >= 0, negative: realizedPnl < 0 }"
            >
              {{ signedMoney(realizedPnl) }}
            </strong>
          </div>
          <div>
            <small>{{ periodLabel }}</small>
            <strong
              :class="{ positive: periodPnl >= 0, negative: periodPnl < 0 }"
            >
              {{ signedMoney(periodPnl) }}
            </strong>
            <span>{{ percentage(periodPnlPercent) }}</span>
          </div>
        </div>

        <div v-if="performanceLoading" class="fund-chart-state">
          {{ t("funds.performance.calculating") }}
        </div>
        <div v-else-if="performanceError" class="fund-chart-state error-state">
          <strong>{{ t("funds.performance.unavailable") }}</strong>
          <p>{{ performanceError }}</p>
          <button type="button" @click="loadPerformance()">
            {{ t("funds.actions.retry") }}
          </button>
        </div>
        <FundPerformanceChart
          v-else-if="performancePoints.length >= 2"
          :points="performancePoints"
          :mode="mode"
        />
        <div v-else class="fund-chart-state">
          <strong>{{ t("funds.performance.insufficientHistory") }}</strong>
          <p>{{ t("funds.performance.insufficientHistoryHint") }}</p>
        </div>
      </article>

      <article
        class="fund-performance-panel positions-panel"
        :class="{ collapsed: positionsCollapsed }"
      >
        <header class="fund-secondary-header">
          <div>
            <p class="section-label">{{ t("funds.positions.section") }}</p>
            <h2>{{ t("funds.positions.title") }}</h2>
            <p class="fund-range-label">
              {{
                t(
                  positions.length === 1
                    ? "funds.positions.pricedOne"
                    : "funds.positions.pricedMany",
                  { priced: pricedPositions, total: positions.length },
                )
              }}
              ·
              {{ priceMessage || t("funds.positions.pricesInEuros") }}
            </p>
          </div>
          <button
            type="button"
            class="fund-collapse-button"
            :class="{ collapsed: positionsCollapsed }"
            :aria-expanded="!positionsCollapsed"
            aria-controls="fund-positions-content"
            :aria-label="
              t(
                positionsCollapsed
                  ? 'funds.positions.expandAria'
                  : 'funds.positions.collapseAria',
              )
            "
            :title="
              t(
                positionsCollapsed
                  ? 'funds.positions.expandAria'
                  : 'funds.positions.collapseAria',
              )
            "
            @click="togglePositions"
          >
            <svg
              :data-direction="positionsCollapsed ? 'down' : 'up'"
              aria-hidden="true"
              viewBox="0 0 20 20"
            >
              <path
                :d="positionsCollapsed ? 'm5 7.5 5 5 5-5' : 'm5 12.5 5-5 5 5'"
              />
            </svg>
          </button>
        </header>
        <div
          v-show="!positionsCollapsed"
          id="fund-positions-content"
          class="fund-positions-content"
        >
          <InvestmentAllocationStrip
            :items="marketValueAllocationItems"
            :total="marketValueAllocationTotal"
            :account-label="selectedAccountLabel"
            :title="t('funds.positions.marketValueDistribution')"
            :bar-label="t('funds.positions.marketValueDistributionBarAria')"
            :empty-label="t('funds.positions.noMarketValueDistribution')"
            :format-value="money"
            :format-share="percentage"
            :segment-aria="marketValueSegmentAria"
          />
          <div class="fund-table-scroll position-table-scroll">
            <table class="fund-table">
              <colgroup>
                <col class="fund-col-name" />
                <col class="fund-col-type" />
                <col class="fund-col-contributed" />
                <col class="fund-col-shares" />
                <col class="fund-col-average" />
                <col class="fund-col-current" />
                <col class="fund-col-value" />
                <col class="fund-col-pnl" />
                <col class="fund-col-return" />
                <col class="fund-col-actions" />
              </colgroup>
              <thead>
                <tr>
                  <th
                    v-for="column in positionSortColumns"
                    :key="column.key"
                    :aria-sort="positionAriaSort(column.key)"
                  >
                    <button
                      type="button"
                      class="fund-sort-button"
                      :data-sort-key="column.key"
                      :aria-label="positionSortAria(column.key, column.label)"
                      @click="sortPositions(column.key)"
                    >
                      <span>{{ column.label }}</span>
                      <span
                        class="fund-sort-indicator"
                        :class="{ active: positionSortKey === column.key }"
                        aria-hidden="true"
                        >{{
                          positionSortKey === column.key
                            ? positionSortDirection === "asc"
                              ? "↑"
                              : "↓"
                            : ""
                        }}</span
                      >
                    </button>
                  </th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <template
                  v-for="position in sortedPositions"
                  :key="position.isin"
                >
                  <tr
                    class="fund-position-row"
                    :class="{ active: selectedFund === position.isin }"
                    @click="toggleFund(position.isin)"
                  >
                    <td>
                      <button
                        type="button"
                        class="fund-position-disclosure"
                        :aria-expanded="selectedFund === position.isin"
                        :aria-controls="fundDetailId(position.isin)"
                        :aria-label="
                          t(
                            selectedFund === position.isin
                              ? 'funds.positions.collapseChartAria'
                              : 'funds.positions.expandChartAria',
                            { asset: position.nombre },
                          )
                        "
                        @click.stop="toggleFund(position.isin)"
                        @keydown.enter.prevent.stop="toggleFund(position.isin)"
                        @keydown.space.prevent.stop="toggleFund(position.isin)"
                      >
                        <span class="fund-position-disclosure-copy">
                          <strong>{{ position.nombre }}</strong
                          ><small>{{ position.isin }}</small>
                        </span>
                        <span
                          class="fund-position-disclosure-icon"
                          :class="{ active: selectedFund === position.isin }"
                          aria-hidden="true"
                          >⌄</span
                        >
                      </button>
                    </td>
                    <td :data-label="t('funds.positions.type')">
                      {{ position.tipo }}<small>{{ position.subtipo }}</small>
                    </td>
                    <td :data-label="t('funds.positions.contributed')">
                      {{ money(position.total_invertido) }}
                    </td>
                    <td :data-label="t('funds.positions.shares')">
                      {{ quantity(position.participaciones, 5) }}
                    </td>
                    <td :data-label="t('funds.positions.averagePrice')">
                      {{ money(position.precio_medio) }}
                    </td>
                    <td :data-label="t('funds.positions.currentPrice')">
                      {{
                        position.precio_actual == null
                          ? t("funds.positions.pending")
                          : money(position.precio_actual)
                      }}
                    </td>
                    <td :data-label="t('funds.positions.value')">
                      {{
                        position.valor_actual == null
                          ? "—"
                          : money(position.valor_actual)
                      }}
                    </td>
                    <td
                      :data-label="'P&L'"
                      :class="{
                        positive: (position.pnl ?? 0) >= 0,
                        negative: (position.pnl ?? 0) < 0,
                      }"
                    >
                      <strong>{{
                        position.pnl == null ? "—" : signedMoney(position.pnl)
                      }}</strong>
                    </td>
                    <td
                      :data-label="t('funds.positions.return')"
                      :class="{
                        positive: (position.pnl_pct ?? 0) >= 0,
                        negative: (position.pnl_pct ?? 0) < 0,
                      }"
                    >
                      <strong>{{
                        position.pnl_pct == null
                          ? "—"
                          : percentage(position.pnl_pct)
                      }}</strong>
                    </td>
                    <td>
                      <button
                        type="button"
                        class="fund-edit-icon-button"
                        :aria-label="t('funds.positions.editAria')"
                        @click.stop="openFundEditor(position)"
                        @keydown.stop
                      >
                        <svg viewBox="0 0 20 20" aria-hidden="true">
                          <path d="M4 16l3.3-.7L16 6.6 13.4 4 4.7 12.7 4 16Z" />
                          <path d="m11.9 5.5 2.6 2.6" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                  <tr
                    v-if="selectedFund === position.isin"
                    class="fund-inline-detail-row"
                  >
                    <td :colspan="positionSortColumns.length + 1">
                      <div
                        :id="fundDetailId(position.isin)"
                        class="fund-inline-price-panel"
                        role="region"
                        :aria-label="
                          t('funds.positions.priceDetailAria', {
                            fund: position.nombre,
                          })
                        "
                      >
                        <div class="fund-inline-chart-toolbar">
                          <div class="fund-chart-legend">
                            <span
                              ><i class="line price" />{{
                                t("funds.priceChart.price")
                              }}</span
                            >
                            <span
                              ><i class="line average" />{{
                                t("funds.priceChart.averagePrice")
                              }}</span
                            >
                            <span
                              ><i class="marker buy" />{{
                                t("funds.priceChart.contributionEntry")
                              }}</span
                            >
                            <span
                              ><i class="marker sell" />{{
                                t("funds.priceChart.redemptionExit")
                              }}</span
                            >
                          </div>
                          <div class="fund-inline-range">
                            <p class="fund-range-label">
                              {{ fundChartRangeLabel }}
                            </p>
                            <div
                              class="fund-range-control"
                              :aria-label="t('funds.priceChart.rangeAria')"
                            >
                              <button
                                v-for="item in ranges"
                                :key="item.key"
                                type="button"
                                :class="{ active: fundRange === item.key }"
                                :aria-pressed="fundRange === item.key"
                                @click="selectFundRange(item.key)"
                              >
                                {{ item.label }}
                              </button>
                            </div>
                          </div>
                        </div>
                        <div v-if="fundChartLoading" class="fund-chart-state">
                          {{ t("funds.priceChart.loading") }}
                        </div>
                        <div
                          v-else-if="fundChartError"
                          class="fund-chart-state error-state"
                        >
                          <strong>{{
                            t("funds.priceChart.unavailable")
                          }}</strong>
                          <p>{{ fundChartError }}</p>
                          <button type="button" @click="loadFundChart()">
                            {{ t("funds.actions.retry") }}
                          </button>
                        </div>
                        <FundPriceChart
                          v-else-if="fundChartPoints.length"
                          :points="fundChartPoints"
                          :orders="selectedFundOrders"
                          :average-price="
                            selectedFundPosition?.precio_medio ?? null
                          "
                        />
                        <div v-else class="fund-chart-state">
                          {{ t("funds.priceChart.noHistory") }}
                        </div>
                      </div>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </div>
      </article>

      <article
        class="fund-performance-panel movements-panel"
        :class="{ collapsed: movementsCollapsed }"
      >
        <header class="fund-secondary-header">
          <div>
            <p class="section-label">{{ t("funds.movements.section") }}</p>
            <h2>{{ t("funds.movements.title") }}</h2>
            <p class="fund-range-label">
              {{
                t(
                  filteredOrders.length === 1
                    ? "funds.movements.operation"
                    : "funds.movements.operations",
                  { count: filteredOrders.length },
                )
              }}
              · {{ movementRangeLabel }}
            </p>
          </div>
          <div class="fund-collapsible-actions">
            <div v-show="!movementsCollapsed" class="movement-filters">
              <button
                type="button"
                class="add-movement"
                @click="openNewMovement"
              >
                <span aria-hidden="true">+</span> {{ t("funds.movements.add") }}
              </button>
              <select
                v-model="movementFund"
                :aria-label="t('funds.movements.filterFundAria')"
              >
                <option value="all">{{ t("funds.movements.allFunds") }}</option>
                <option
                  v-for="position in positions"
                  :key="position.isin"
                  :value="position.isin"
                >
                  {{ position.nombre }}
                </option>
              </select>
              <select
                v-model="movementType"
                :aria-label="t('funds.movements.filterTypeAria')"
              >
                <option value="all">
                  {{ t("funds.movements.allMovements") }}
                </option>
                <option value="in">{{ t("funds.movements.entries") }}</option>
                <option value="out">{{ t("funds.movements.exits") }}</option>
              </select>
              <button type="button" @click="openMovementCalendar">
                {{ movementRangeLabel }}
              </button>
            </div>
            <button
              type="button"
              class="fund-collapse-button"
              :class="{ collapsed: movementsCollapsed }"
              :aria-expanded="!movementsCollapsed"
              aria-controls="fund-movements-content"
              :aria-label="
                t(
                  movementsCollapsed
                    ? 'funds.movements.expandAria'
                    : 'funds.movements.collapseAria',
                )
              "
              :title="
                t(
                  movementsCollapsed
                    ? 'funds.movements.expandAria'
                    : 'funds.movements.collapseAria',
                )
              "
              @click="toggleMovements"
            >
              <svg
                :data-direction="movementsCollapsed ? 'down' : 'up'"
                aria-hidden="true"
                viewBox="0 0 20 20"
              >
                <path
                  :d="movementsCollapsed ? 'm5 7.5 5 5 5-5' : 'm5 12.5 5-5 5 5'"
                />
              </svg>
            </button>
          </div>
        </header>
        <div v-show="!movementsCollapsed" id="fund-movements-content">
          <div class="fund-table-scroll">
            <table class="fund-table movement-table">
              <thead>
                <tr>
                  <th>{{ t("funds.movements.date") }}</th>
                  <th>{{ t("funds.movements.movement") }}</th>
                  <th>{{ t("funds.movements.fund") }}</th>
                  <th>{{ t("funds.movements.account") }}</th>
                  <th>{{ t("funds.movements.shares") }}</th>
                  <th>{{ t("funds.movements.price") }}</th>
                  <th>{{ t("funds.movements.amount") }}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr v-for="order in displayedOrders" :key="order.operacion_id">
                  <td>{{ displayDate(order.fecha_operacion) }}</td>
                  <td>
                    <span
                      class="operation-pill"
                      :class="operationGroup(order)"
                      >{{ operationLabel(order) }}</span
                    >
                  </td>
                  <td>
                    <strong>{{ order.nombre_fondo }}</strong
                    ><small>{{ order.isin }}</small>
                  </td>
                  <td>
                    {{ order.cuenta_nombre ?? selectedAccountLabel
                    }}<small>{{ order.plataforma }}</small>
                  </td>
                  <td>{{ quantity(order.titulos, 6) }}</td>
                  <td>
                    {{ money(baseUnitPrice(order)) }}
                    <small v-if="order.moneda && order.moneda !== 'EUR'">{{
                      originalMoney(order.precio_neto, order.moneda)
                    }}</small>
                  </td>
                  <td>
                    <strong>{{ money(baseAmount(order)) }}</strong>
                    <small v-if="order.moneda && order.moneda !== 'EUR'">{{
                      originalMoney(order.importe_neto, order.moneda)
                    }}</small>
                  </td>
                  <td>
                    <InvestmentMovementActions
                      :edit-label="t('funds.movements.edit')"
                      :delete-label="t('funds.movements.delete')"
                      @edit="openEditMovement(order)"
                      @delete="askDeleteOrder(order)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="!filteredOrders.length" class="fund-empty-compact">
            {{ t("funds.movements.noResults") }}
          </div>
          <nav
            v-else-if="movementPages > 1"
            class="movement-pagination"
            :aria-label="t('funds.movements.paginationAria')"
          >
            <span>{{
              t("funds.movements.page", {
                page: movementPage,
                pages: movementPages,
              })
            }}</span>
            <div>
              <button
                type="button"
                :disabled="movementPage === 1"
                @click="movementPage--"
              >
                {{ t("funds.movements.previous") }}
              </button>
              <button
                type="button"
                :disabled="movementPage === movementPages"
                @click="movementPage++"
              >
                {{ t("funds.movements.next") }}
              </button>
            </div>
          </nav>
        </div>
      </article>

      <MovementEditorDialog
        ref="movementEditor"
        kind="fund"
        :accounts="accounts"
        :assets="movementAssets"
        :selected-account="selectedAccount"
        @saved="loadDashboard"
      />
      <MovementDeleteDialog
        ref="movementDelete"
        kind="fund"
        @deleted="loadDashboard"
      />

      <dialog
        ref="calendarDialog"
        class="fund-dialog"
        aria-labelledby="fund-calendar-title"
        @cancel.prevent="closeCalendar"
      >
        <form @submit.prevent="applyCustomRange">
          <header>
            <div>
              <p class="section-label">
                {{ t("funds.calendar.customPeriod") }}
              </p>
              <h2 id="fund-calendar-title">
                {{ t("funds.calendar.selectDates") }}
              </h2>
            </div>
          </header>
          <div class="fund-calendar-fields">
            <label>
              <span>{{ t("funds.calendar.from") }}</span>
              <input
                v-model="draftStart"
                type="date"
                :max="draftEnd"
                required
              />
            </label>
            <span aria-hidden="true">→</span>
            <label>
              <span>{{ t("funds.calendar.to") }}</span>
              <input
                v-model="draftEnd"
                type="date"
                :min="draftStart"
                required
              />
            </label>
          </div>
          <footer>
            <button type="button" @click="closeCalendar">
              {{ t("funds.actions.cancel") }}
            </button>
            <button class="primary" type="submit" :disabled="!customRangeValid">
              {{ t("funds.calendar.applyPeriod") }}
            </button>
          </footer>
        </form>
      </dialog>

      <dialog
        ref="fundPriceCalendarDialog"
        class="fund-dialog"
        aria-labelledby="fund-price-calendar-title"
        @cancel.prevent="closeFundPriceCalendar"
      >
        <form @submit.prevent="applyFundCustomRange">
          <header>
            <div>
              <p class="section-label">
                {{ t("funds.priceChart.historySection") }}
              </p>
              <h2 id="fund-price-calendar-title">
                {{ t("funds.calendar.selectDates") }}
              </h2>
            </div>
          </header>
          <div class="fund-calendar-fields">
            <label
              ><span>{{ t("funds.calendar.from") }}</span
              ><input
                v-model="fundDraftStart"
                type="date"
                :max="fundDraftEnd"
                required
            /></label>
            <span aria-hidden="true">→</span>
            <label
              ><span>{{ t("funds.calendar.to") }}</span
              ><input
                v-model="fundDraftEnd"
                type="date"
                :min="fundDraftStart"
                required
            /></label>
          </div>
          <footer>
            <button type="button" @click="closeFundPriceCalendar">
              {{ t("funds.actions.cancel") }}
            </button>
            <button
              class="primary"
              type="submit"
              :disabled="!fundCustomRangeValid"
            >
              {{ t("funds.calendar.applyPeriod") }}
            </button>
          </footer>
        </form>
      </dialog>

      <dialog
        ref="movementCalendarDialog"
        class="fund-dialog"
        aria-labelledby="movement-calendar-title"
      >
        <form @submit.prevent="applyMovementRange">
          <header>
            <div>
              <p class="section-label">
                {{ t("funds.movements.filterSection") }}
              </p>
              <h2 id="movement-calendar-title">
                {{ t("funds.calendar.selectDates") }}
              </h2>
            </div>
          </header>
          <div class="fund-calendar-fields">
            <label
              ><span>{{ t("funds.calendar.from") }}</span
              ><input
                v-model="movementDraftStart"
                type="date"
                :max="movementDraftEnd"
                required
            /></label>
            <span aria-hidden="true">→</span>
            <label
              ><span>{{ t("funds.calendar.to") }}</span
              ><input
                v-model="movementDraftEnd"
                type="date"
                :min="movementDraftStart"
                required
            /></label>
          </div>
          <footer>
            <button type="button" @click="movementCalendarDialog?.close()">
              {{ t("funds.actions.cancel") }}
            </button>
            <button
              class="primary"
              type="submit"
              :disabled="!movementRangeValid"
            >
              {{ t("funds.calendar.applyFilter") }}
            </button>
          </footer>
        </form>
      </dialog>

      <dialog
        ref="fundEditDialog"
        class="fund-dialog"
        aria-labelledby="fund-editor-title"
      >
        <form @submit.prevent="saveFundEditor">
          <header>
            <div>
              <p class="section-label">{{ t("funds.editor.marketData") }}</p>
              <h2 id="fund-editor-title">{{ t("funds.editor.title") }}</h2>
            </div>
          </header>
          <div class="fund-account-fields">
            <label
              ><span>{{ t("funds.editor.name") }}</span
              ><input v-model="editFundName" type="text" required
            /></label>
            <label
              ><span>{{ t("funds.editor.yahooTicker") }}</span
              ><input
                v-model="editFundTicker"
                type="text"
                :placeholder="t('funds.editor.tickerPlaceholder')"
            /></label>
            <label
              ><span>{{ t("funds.editor.type") }}</span
              ><input v-model="editFundType" type="text"
            /></label>
            <label
              ><span>{{ t("funds.editor.subtype") }}</span
              ><input v-model="editFundSubtype" type="text"
            /></label>
            <label
              ><span>{{
                t("funds.editor.manualPrice", {
                  currency: editingFund?.moneda ?? "EUR",
                })
              }}</span
              ><input v-model="editFundPrice" type="number" min="0" step="any"
            /></label>
          </div>
          <p v-if="fundEditError" class="fund-dialog-error" role="alert">
            {{ fundEditError }}
          </p>
          <footer>
            <button
              type="button"
              :disabled="fundEditBusy"
              @click="fundEditDialog?.close()"
            >
              {{ t("funds.actions.cancel") }}
            </button>
            <button
              class="primary"
              type="submit"
              :disabled="fundEditBusy || !editFundName.trim()"
            >
              {{
                fundEditBusy
                  ? t("funds.editor.saving")
                  : t("funds.editor.saveChanges")
              }}
            </button>
          </footer>
        </form>
      </dialog>

      <dialog
        ref="accountDialog"
        class="fund-dialog"
        aria-labelledby="fund-account-dialog-title"
        @cancel.prevent="closeAccountDialog"
      >
        <form @submit.prevent="saveAccount">
          <header>
            <div>
              <p class="section-label">{{ t("funds.accounts.section") }}</p>
              <h2 id="fund-account-dialog-title">
                {{
                  accountDialogMode === "edit"
                    ? t("funds.accounts.manageTitle")
                    : t("funds.accounts.addTitle")
                }}
              </h2>
            </div>
          </header>
          <div class="fund-account-fields">
            <label>
              <span>{{ t("funds.accounts.name") }}</span>
              <input
                v-model="accountName"
                type="text"
                :placeholder="t('funds.accounts.namePlaceholder')"
                required
              />
            </label>
            <label>
              <span>{{ t("funds.accounts.platform") }}</span>
              <input
                v-model="accountProvider"
                type="text"
                :placeholder="t('funds.accounts.platformPlaceholder')"
                required
              />
            </label>
            <label>
              <span>{{ t("funds.accounts.currency") }}</span>
              <input
                v-model="accountCurrency"
                maxlength="3"
                minlength="3"
                pattern="[A-Za-z]{3}"
                required
              />
            </label>
            <label>
              <span
                >{{ t("funds.accounts.portfolioType") }}
                <em>{{ t("funds.actions.optional") }}</em></span
              >
              <input
                v-model="accountType"
                type="text"
                :placeholder="t('funds.accounts.typePlaceholder')"
              />
            </label>
            <label>
              <span>{{ t("funds.accounts.importer") }}</span>
              <select v-model="accountImporter" required>
                <option value="" disabled>
                  {{ t("funds.accounts.chooseImporter") }}
                </option>
                <option value="none">
                  {{ t("funds.accounts.noImporter") }}
                </option>
                <option
                  v-for="item in compatibleImporters"
                  :key="item.slug"
                  :value="item.slug"
                >
                  {{ item.display_name }}
                </option>
              </select>
            </label>
          </div>
          <p v-if="accountError" class="fund-dialog-error" role="alert">
            {{ accountError }}
          </p>
          <footer>
            <button
              v-if="accountDialogMode === 'edit'"
              class="danger ghost-danger"
              type="button"
              :disabled="accountBusy"
              @click="deleteAccount"
            >
              {{
                accountDeleteArmed
                  ? t("funds.accounts.confirmDelete")
                  : t("funds.accounts.delete")
              }}
            </button>
            <span class="footer-spacer" />
            <button
              type="button"
              :disabled="accountBusy"
              @click="closeAccountDialog"
            >
              {{ t("funds.actions.cancel") }}
            </button>
            <button
              class="primary"
              type="submit"
              :disabled="
                accountBusy ||
                !accountName.trim() ||
                !accountProvider.trim() ||
                !accountImporter
              "
            >
              {{
                accountBusy
                  ? t("funds.accounts.saving")
                  : accountDialogMode === "edit"
                    ? t("funds.accounts.saveChanges")
                    : t("funds.accounts.create")
              }}
            </button>
          </footer>
        </form>
      </dialog>
    </template>
  </section>
</template>

<style scoped>
.funds-page {
  width: min(100%, 1440px);
  margin: 0 auto;
  padding: 8px 48px 56px;
}
.fund-account-actions select,
.fund-account-actions button,
.fund-account-actions summary {
  min-height: 34px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  font-size: 11px;
  font-weight: 710;
}
.fund-account-actions select {
  min-width: 174px;
  padding: 8px 30px 8px 11px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
}
.fund-account-actions button,
.fund-account-actions summary {
  padding: 8px 11px;
  background: transparent;
  color: var(--fz-muted);
  cursor: pointer;
}
.fund-account-actions button:hover,
.fund-account-actions summary:hover {
  border-color: var(--fz-accent);
  color: var(--fz-ink);
}
.fund-account-actions details {
  position: relative;
}
.fund-account-actions summary {
  display: grid;
  place-items: center;
  list-style: none;
}
.fund-account-actions summary::-webkit-details-marker {
  display: none;
}
.fund-import-popover {
  position: absolute;
  z-index: 5;
  top: calc(100% + 9px);
  right: 0;
  width: min(370px, 80vw);
  padding: 12px;
  border: 1px solid var(--fz-line);
  border-radius: 14px;
  background: var(--fz-surface);
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.16);
}
.fund-import-popover p {
  margin: 5px 0 0;
  color: var(--fz-muted);
  font-size: 10px;
}
:deep(.import-compact) {
  margin: 0;
  padding: 0;
  display: grid;
  gap: 9px;
  border: 0;
  background: transparent;
}
:deep(.import-compact h2) {
  display: none;
}
:deep(.import-compact select),
:deep(.import-compact input) {
  min-width: 0;
  width: 100%;
  padding: 9px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  font-size: 11px;
}
:deep(.import-compact button) {
  padding: 9px 11px;
  border: 0;
  border-radius: 9px;
  background: var(--fz-accent);
  color: #f4fff9;
  font-size: 11px;
  font-weight: 720;
}
:deep(.import-compact p) {
  min-height: 12px;
  margin: 0;
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-panel-header h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 750;
  letter-spacing: -0.03em;
}
.fund-asset-head {
  padding: 0 8px 8px;
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-kpi strong {
  overflow: hidden;
  font-size: 14px;
  font-weight: 760;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.04em;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fund-kpi.primary strong {
  font-size: 25px;
}
.fund-utility strong {
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}
.fund-performance-panel {
  margin-top: 18px;
  padding: 24px;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 22px;
  background: var(--fz-surface);
  box-shadow: var(--fz-shadow);
}
.fund-secondary-header,
.fund-price-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.fund-secondary-header h2,
.fund-price-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 750;
  letter-spacing: -0.03em;
}
.fund-empty-compact {
  min-height: 180px;
  display: grid;
  place-items: center;
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-price-header {
  align-items: center;
}
.fund-price-controls {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}
.fund-price-controls label {
  display: grid;
  gap: 5px;
}
.fund-price-controls label span {
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 700;
}
.fund-price-controls select,
.movement-filters select,
.movement-filters button {
  min-height: 36px;
  padding: 8px 28px 8px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  font-size: 11px;
  font-weight: 680;
}
.fund-price-controls select {
  max-width: 260px;
}
.fund-chart-legend {
  margin: 16px 0 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 650;
}
.fund-chart-legend span {
  display: flex;
  align-items: center;
  gap: 6px;
}
.fund-chart-legend i {
  display: inline-block;
}
.fund-chart-legend .line {
  width: 18px;
  height: 2px;
  border-radius: 2px;
  background: var(--fz-accent);
}
.fund-chart-legend .average {
  background: transparent;
  border-top: 2px dashed var(--fz-chart-average);
}
.fund-chart-legend .marker {
  width: 18px;
  height: 16px;
  display: grid;
  place-items: center;
  border: 1.5px solid var(--fz-surface);
  border-radius: 5px;
  background: var(--fz-trade-buy);
  color: #fff;
  font-style: normal;
  font-weight: 780;
  line-height: 1;
  box-shadow: 0 1px 3px var(--fz-chart-tooltip-shadow);
}
.fund-chart-legend .marker::before {
  content: "+";
}
.fund-chart-legend .marker.buy {
  border-color: var(--fz-trade-buy-outline);
}
.fund-chart-legend .sell {
  border-color: var(--fz-trade-sell-outline);
  background: var(--fz-trade-sell);
}
.fund-chart-legend .sell::before {
  content: "−";
}
.positions-panel,
.movements-panel {
  padding-bottom: 18px;
}
.positions-panel.collapsed,
.movements-panel.collapsed {
  padding-bottom: 24px;
}
.fund-collapsible-actions {
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  gap: 10px;
}
.fund-collapse-button {
  width: 36px;
  height: 36px;
  padding: 0;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  cursor: pointer;
}
.fund-collapse-button:hover {
  border-color: var(--fz-accent);
  color: var(--fz-ink);
}
.fund-collapse-button:focus-visible {
  outline: 2px solid var(--fz-accent);
  outline-offset: 2px;
}
.fund-collapse-button svg {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}
.fund-table-scroll {
  margin-top: 17px;
  overflow-x: auto;
}
.fund-positions-content {
  margin-top: 17px;
}
.position-table-scroll {
  --fund-inline-width: 100%;
  margin-top: 0;
  overflow-x: visible;
}
.fund-table {
  width: 100%;
  min-width: 0;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 10px;
}
.fund-col-name {
  width: 21%;
}
.fund-col-type {
  width: 11%;
}
.fund-col-contributed {
  width: 10%;
}
.fund-col-shares {
  width: 9%;
}
.fund-col-average,
.fund-col-current,
.fund-col-value {
  width: 10%;
}
.fund-col-pnl {
  width: 8%;
}
.fund-col-return {
  width: 6%;
}
.fund-col-actions {
  width: 5%;
}
.fund-table th {
  padding: 8px 5px;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 700;
  text-align: right;
  line-height: 1.2;
  white-space: normal;
  border-bottom: 1px solid var(--fz-line);
}
.fund-table th:first-child,
.fund-table th:nth-child(2),
.fund-table td:first-child,
.fund-table td:nth-child(2) {
  text-align: left;
}
.position-table-scroll .fund-table th:first-child,
.position-table-scroll .fund-table .fund-position-row > td:first-child {
  padding-left: 12px;
}
.fund-sort-button {
  width: 100%;
  padding: 3px 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: inherit;
  line-height: inherit;
  white-space: normal;
  cursor: pointer;
}
.fund-table th:first-child .fund-sort-button,
.fund-table th:nth-child(2) .fund-sort-button {
  justify-content: flex-start;
}
.fund-sort-button:hover {
  color: var(--fz-ink);
}
.fund-sort-button:focus-visible {
  outline: 2px solid var(--fz-accent);
  outline-offset: 3px;
  border-radius: 3px;
}
.fund-sort-indicator {
  width: 7px;
  flex: 0 0 7px;
  color: transparent;
  font-size: 11px;
  line-height: 1;
  text-align: center;
}
.fund-sort-indicator.active {
  color: var(--fz-accent);
}
.fund-table td {
  min-width: 0;
  padding: 11px 5px;
  overflow: hidden;
  text-align: right;
  text-overflow: ellipsis;
  font-variant-numeric: tabular-nums;
  border-bottom: 1px solid var(--fz-line);
  white-space: nowrap;
}
.fund-position-row {
  cursor: pointer;
  outline: none;
  transition:
    background-color 0.14s ease,
    box-shadow 0.14s ease;
}
.fund-position-row:hover,
.fund-position-row.active {
  background: color-mix(in srgb, var(--fz-accent) 7%, transparent);
}
.fund-position-row.active {
  box-shadow: inset 3px 0 var(--fz-accent);
}
.fund-inline-detail-row td {
  position: static;
  width: var(--fund-inline-width, 100%);
  max-width: var(--fund-inline-width, 100%);
  padding: 12px 10px 16px;
  text-align: left;
  white-space: normal;
  border-bottom: 0;
  background: transparent;
}
.fund-inline-price-panel {
  position: relative;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  padding: 18px 20px 20px;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 18px;
  background: var(--fz-surface);
}
.fund-inline-chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px 18px;
  flex-wrap: wrap;
}
.fund-inline-price-panel .fund-chart-legend {
  width: fit-content;
  max-width: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
}
.fund-inline-range {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-left: auto;
}
.fund-inline-range .fund-range-label {
  margin: 0;
  white-space: nowrap;
}
.fund-inline-price-panel .fund-chart-state {
  min-height: 250px;
  margin-top: 14px;
  border: 0;
  background: transparent;
}
.fund-inline-price-panel :deep(.fund-price-chart) {
  height: 325px;
  margin-top: 14px;
}
.fund-inline-price-panel .fund-range-control {
  max-width: 100%;
  flex-wrap: wrap;
}
.fund-table tbody tr:last-child td {
  border-bottom: 0;
}
.fund-table td strong,
.fund-table td small {
  display: block;
}
.fund-table td small {
  margin-top: 3px;
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-table td button {
  padding: 6px 8px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 11px;
  cursor: pointer;
}
.fund-table td button:hover {
  border-color: var(--fz-accent);
  color: var(--fz-ink);
}
.fund-table td .fund-edit-icon-button {
  width: 30px;
  height: 30px;
  padding: 0;
  display: inline-grid;
  place-items: center;
  border-radius: 9px;
  background: color-mix(in srgb, var(--fz-surface-soft) 72%, transparent);
}
.fund-edit-icon-button svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.fund-table td .fund-edit-icon-button:hover {
  background: color-mix(in srgb, var(--fz-accent) 9%, var(--fz-surface));
  color: var(--fz-accent);
}
.fund-edit-icon-button:focus-visible {
  outline: 2px solid var(--fz-accent);
  outline-offset: 2px;
}
.fund-table td .fund-position-disclosure {
  width: 100%;
  min-width: 0;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--fz-ink);
  font: inherit;
  text-align: left;
}
.fund-position-disclosure:focus-visible {
  outline: 2px solid var(--fz-accent);
  outline-offset: 3px;
}
.fund-position-disclosure-copy {
  min-width: 0;
}
.fund-position-disclosure-copy strong,
.fund-position-disclosure-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fund-position-disclosure-icon {
  flex: 0 0 auto;
  color: var(--fz-muted);
  font-size: 15px;
  line-height: 1;
  transform: translateY(-2px);
  transition:
    color 0.14s ease,
    transform 0.14s ease;
}
.fund-position-disclosure:hover .fund-position-disclosure-icon,
.fund-position-disclosure-icon.active {
  color: var(--fz-accent);
}
.fund-position-disclosure-icon.active {
  transform: rotate(180deg) translateY(2px);
}
.movement-filters {
  display: flex;
  align-items: center;
  gap: 8px;
}
.movement-filters button {
  padding-right: 10px;
  cursor: pointer;
}
.movement-filters .add-movement {
  border-color: var(--fz-accent);
  background: var(--fz-accent);
  color: #f4fff9;
}
.movement-filters .add-movement span {
  margin-right: 3px;
  font-size: 12px;
}
.movement-table th:nth-child(3),
.movement-table th:nth-child(4),
.movement-table td:nth-child(3),
.movement-table td:nth-child(4) {
  text-align: left;
}
.operation-pill {
  display: inline-flex;
  padding: 5px 7px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 730;
}
.operation-pill.in {
  background: color-mix(in srgb, var(--fz-accent) 13%, transparent);
  color: var(--fz-accent);
}
.operation-pill.out {
  background: color-mix(in srgb, var(--fz-negative) 10%, transparent);
  color: var(--fz-negative);
}
.fund-table td .delete-order {
  color: var(--fz-negative);
}
.movement-row-actions {
  display: inline-flex;
  gap: 5px;
}
.movement-pagination {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 680;
}
.movement-pagination div {
  display: flex;
  gap: 7px;
}
.movement-pagination button {
  padding: 7px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}
.movement-pagination button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.fund-performance-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}
.fund-performance-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 750;
  letter-spacing: -0.035em;
}
.fund-range-label {
  margin: 7px 0 0;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
.fund-chart-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}
.fund-mode-control,
.fund-range-control {
  display: flex;
  padding: 4px;
  border-radius: 12px;
  background: var(--fz-surface-soft);
}
.fund-mode-control button,
.fund-range-control button {
  padding: 7px 10px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 720;
  white-space: nowrap;
  cursor: pointer;
}
.fund-mode-control button.active,
.fund-range-control button.active {
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
}
.fund-period-kpis {
  margin: 20px 0 14px;
  padding: 14px 0;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  border-block: 1px solid var(--fz-line);
}
.fund-period-kpis > div {
  min-width: 0;
  padding: 0 16px;
  display: grid;
  gap: 3px;
  border-left: 1px solid var(--fz-line);
}
.fund-period-kpis > div:first-child {
  padding-left: 0;
  border-left: 0;
}
.fund-period-kpis small,
.fund-period-kpis span {
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-period-kpis strong {
  overflow: hidden;
  font-size: 14px;
  font-weight: 740;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fund-chart-state {
  min-height: 330px;
  display: grid;
  place-content: center;
  text-align: center;
  color: var(--fz-muted);
  font-size: 11px;
}
.fund-chart-state strong {
  color: var(--fz-ink);
  font-size: 13px;
}
.fund-chart-state p {
  margin: 5px 0 12px;
}
.fund-chart-state button {
  justify-self: center;
  padding: 8px 11px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}
.fund-dialog {
  width: min(520px, calc(100vw - 32px));
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 20px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 28px 90px rgba(0, 0, 0, 0.34);
}
.fund-dialog::backdrop {
  background: rgba(6, 11, 8, 0.68);
  backdrop-filter: blur(5px);
}
.fund-dialog form {
  padding: 23px;
}
.fund-dialog header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.fund-dialog h2 {
  margin: 0;
  font-size: 18px;
}
.fund-dialog header > button {
  width: 31px;
  height: 31px;
  display: grid;
  place-items: center;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  font-size: 18px;
  cursor: pointer;
}
.fund-calendar-fields,
.fund-account-fields {
  margin-top: 23px;
  padding: 18px;
  display: grid;
  gap: 12px;
  border-radius: 14px;
  background: var(--fz-surface-soft);
}
.fund-calendar-fields {
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: end;
}
.fund-account-fields {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.fund-account-fields label:last-child {
  grid-column: 1 / -1;
}
.fund-calendar-fields label,
.fund-account-fields label {
  display: grid;
  gap: 7px;
}
.fund-calendar-fields label span,
.fund-account-fields label span {
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 690;
}
.fund-account-fields em {
  font-size: 10px;
  font-style: normal;
  font-weight: 550;
}
.fund-calendar-fields > span {
  padding-bottom: 9px;
  color: var(--fz-muted);
}
.fund-calendar-fields input,
.fund-account-fields input,
.fund-account-fields select {
  min-width: 0;
  width: 100%;
  padding: 10px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font-size: 10px;
}
.fund-dialog footer {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
}
.fund-dialog footer .footer-spacer {
  flex: 1;
}
.fund-dialog footer button {
  padding: 9px 13px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 710;
  cursor: pointer;
}
.fund-dialog footer .primary {
  border-color: var(--fz-accent);
  background: var(--fz-accent);
  color: #f4fff9;
}
.fund-dialog footer .danger {
  border-color: color-mix(in srgb, var(--fz-negative) 55%, var(--fz-line));
  background: var(--fz-negative);
  color: #fff;
}
.fund-dialog footer .ghost-danger {
  background: transparent;
  color: var(--fz-negative);
}
.confirm-dialog > form > p {
  margin: 22px 0 0;
  color: var(--fz-muted);
  font-size: 10px;
  line-height: 1.6;
}
.fund-dialog footer button:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}
.fund-dialog-error {
  margin: 12px 2px 0;
  color: var(--fz-negative);
  font-size: 11px;
}
.funds-loading {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.funds-loading div {
  min-height: 120px;
  border-radius: 17px;
  background: linear-gradient(
    90deg,
    var(--fz-surface-soft),
    var(--fz-surface),
    var(--fz-surface-soft)
  );
  background-size: 220% 100%;
  animation: skeleton 1.4s ease-in-out infinite;
}
.funds-loading div:last-child {
  min-height: 520px;
  grid-column: 1 / -1;
}

@media (max-width: 1050px) {
  .fund-top-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .fund-kpi-panel {
    order: -1;
  }
  .fund-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .fund-performance-header {
    align-items: stretch;
    flex-direction: column;
  }
  .fund-chart-controls {
    justify-content: space-between;
  }
  .fund-price-header {
    align-items: stretch;
    flex-direction: column;
  }
  .fund-price-controls {
    justify-content: space-between;
  }
  .fund-secondary-header {
    align-items: stretch;
  }
  .movements-panel .fund-secondary-header {
    flex-direction: column;
  }
  .fund-collapsible-actions {
    width: 100%;
  }
  .fund-collapsible-actions .movement-filters {
    flex: 1;
  }
}
@media (max-width: 720px) {
  .funds-page {
    padding: 4px 18px 32px;
  }
  .fund-account-bar {
    align-items: stretch;
    flex-direction: column;
  }
  .fund-account-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .fund-account-actions label {
    grid-column: 1 / -1;
  }
  .fund-account-actions select {
    width: 100%;
    min-width: 0;
  }
  .fund-assets-panel,
  .fund-kpi-panel {
    padding: 19px 17px;
    border-radius: 18px;
  }
  .fund-kpi-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .fund-performance-panel {
    padding: 19px 17px;
    border-radius: 18px;
  }
  .fund-chart-controls {
    align-items: stretch;
    flex-direction: column;
  }
  .fund-mode-control,
  .fund-range-control {
    overflow-x: auto;
  }
  .fund-mode-control button,
  .fund-range-control button {
    flex: 1;
  }
  .fund-period-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px 0;
  }
  .fund-period-kpis > div {
    min-height: 42px;
  }
  .fund-period-kpis > div:nth-child(odd) {
    padding-left: 0;
    border-left: 0;
  }
  .fund-price-controls,
  .movement-filters {
    align-items: stretch;
    flex-direction: column;
  }
  .fund-collapsible-actions {
    align-items: flex-start;
  }
  .fund-price-controls select,
  .movement-filters select,
  .movement-filters button {
    width: 100%;
    max-width: none;
  }
  .fund-price-controls .fund-range-control {
    width: 100%;
    overflow-x: auto;
  }
  .position-table-scroll {
    --fund-inline-width: 100%;
  }
  .position-table-scroll .fund-table,
  .position-table-scroll .fund-table tbody {
    display: block;
  }
  .position-table-scroll .fund-table colgroup,
  .position-table-scroll .fund-table thead {
    display: none;
  }
  .position-table-scroll .fund-table tbody {
    display: grid;
    gap: 10px;
  }
  .position-table-scroll .fund-position-row {
    position: relative;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 3px 12px;
    padding: 11px 10px;
    border: 1px solid var(--fz-line);
    border-radius: 14px;
    background: color-mix(in srgb, var(--fz-surface-soft) 42%, transparent);
  }
  .position-table-scroll .fund-position-row.active {
    border-color: color-mix(in srgb, var(--fz-accent) 32%, var(--fz-line));
    box-shadow: inset 3px 0 var(--fz-accent);
  }
  .position-table-scroll .fund-table .fund-position-row > td {
    min-width: 0;
    padding: 7px 6px;
    display: grid;
    gap: 3px;
    border: 0;
    text-align: left;
    white-space: normal;
  }
  .position-table-scroll .fund-table .fund-position-row > td:first-child {
    grid-column: 1 / -1;
    padding-left: 12px;
    padding-right: 40px;
  }
  .position-table-scroll
    .fund-table
    .fund-position-row
    > td:not(:first-child):not(:last-child)::before {
    content: attr(data-label);
    color: var(--fz-muted);
    font-size: 10px;
    font-weight: 680;
  }
  .position-table-scroll .fund-table .fund-position-row > td:last-child {
    position: absolute;
    top: 10px;
    right: 10px;
    padding: 0;
  }
  .position-table-scroll .fund-inline-detail-row {
    display: block;
  }
  .position-table-scroll .fund-table .fund-inline-detail-row td {
    width: 100%;
    display: block;
    padding: 0;
    overflow: visible;
    border: 0;
  }
  .fund-inline-price-panel {
    padding: 16px 14px 15px;
    border-radius: 16px;
  }
  .fund-inline-chart-toolbar {
    align-items: stretch;
  }
  .fund-inline-range {
    width: 100%;
    justify-content: space-between;
    margin-left: 0;
  }
  .fund-inline-range .fund-range-control {
    overflow: visible;
    flex-wrap: wrap;
  }
  .fund-calendar-fields,
  .fund-account-fields {
    grid-template-columns: minmax(0, 1fr);
  }
  .fund-account-fields label:last-child {
    grid-column: auto;
  }
  .fund-calendar-fields > span {
    display: none;
  }
  .funds-loading {
    grid-template-columns: minmax(0, 1fr);
  }
  .funds-loading div:last-child {
    grid-column: auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  .fund-position-row,
  .fund-position-disclosure-icon {
    transition: none;
  }
}

/* Type hierarchy shared with the rest of the dashboard. */
.section-label {
  font-size: 10px;
}
.fund-account-copy small,
.fund-import-popover p,
:deep(.import-compact p),
.fund-asset-head,
.fund-asset-cell small,
.fund-asset-id small,
.fund-kpi small,
.fund-kpi span,
.fund-utility small,
.fund-utility span,
.fund-price-controls label span,
.fund-chart-legend,
.fund-table td small,
.operation-pill,
.movement-pagination,
.fund-period-kpis small,
.fund-period-kpis span,
.fund-account-fields em {
  font-size: 10px;
}
.fund-account-actions select,
.fund-account-actions button,
.fund-account-actions summary,
:deep(.import-compact select),
:deep(.import-compact input),
:deep(.import-compact button),
.fund-price-controls select,
.movement-filters select,
.movement-filters button,
.fund-asset-head,
.fund-action-button,
.fund-live,
.fund-table,
.fund-table td button,
.movement-pagination button,
.fund-range-label,
.fund-mode-control button,
.fund-range-control button,
.fund-chart-state button,
.fund-calendar-fields label span,
.fund-account-fields label span,
.fund-dialog-error {
  font-size: 11px;
}
.fund-secondary-header h2,
.fund-price-header h2,
.fund-panel-header h2 {
  font-size: 20px;
}
.fund-performance-header h2 {
  font-size: 20px;
}
.fund-asset-cell strong,
.fund-utility strong {
  font-size: 11px;
}
.fund-kpi strong {
  font-size: 16px;
}
.fund-kpi.primary strong {
  font-size: 27px;
}
.fund-period-kpis strong {
  font-size: 16px;
}
.fund-table th {
  font-size: 10px;
}
.fund-table td {
  padding-block: 14px;
}
.position-table-scroll .fund-table {
  font-size: 10px;
}
.position-table-scroll .fund-table th {
  font-size: 10px;
}
.position-table-scroll .fund-table td {
  padding-block: 10px;
}
.position-table-scroll .fund-table td small {
  font-size: 10px;
}
.fund-calendar-fields input,
.fund-account-fields input,
.fund-account-fields select,
.fund-dialog footer button {
  font-size: 12px;
}
</style>
