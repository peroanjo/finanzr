<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { api, json } from "../api/client";
import AssetEditorDialog from "../components/AssetEditorDialog.vue";
import type { AssetReturnMode } from "../components/AssetReturnToggle.vue";
import CryptoCandlestickChart from "../components/CryptoCandlestickChart.vue";
import FundPerformanceChart from "../components/FundPerformanceChart.vue";
import InvestmentAccountBar from "../components/investments/InvestmentAccountBar.vue";
import InvestmentAllocationStrip from "../components/investments/InvestmentAllocationStrip.vue";
import type { InvestmentAllocationItem } from "../components/investments/InvestmentAllocationStrip.vue";
import InvestmentAddAssetButton from "../components/investments/InvestmentAddAssetButton.vue";
import InvestmentCollapseButton from "../components/investments/InvestmentCollapseButton.vue";
import InvestmentOverview from "../components/investments/InvestmentOverview.vue";
import InvestmentMovementActions from "../components/investments/InvestmentMovementActions.vue";
import type {
  InvestmentAccountBarLabels,
  InvestmentImportConfig,
} from "../components/investments/InvestmentAccountBar.vue";
import type { InvestmentOverviewLabels } from "../components/investments/InvestmentOverview.vue";
import MovementDeleteDialog from "../components/MovementDeleteDialog.vue";
import MovementEditorDialog from "../components/MovementEditorDialog.vue";
import type {
  MovementDeleteHandle,
  MovementEditorHandle,
} from "../components/movementEditor";
import type {
  AssetEditorHandle,
  EditableAsset,
} from "../components/assetEditor";
import {
  adaptStockAccount,
  adaptStockChart,
  adaptStockPerformance,
} from "../domain/investments";
import type { NormalizedPerformancePoint } from "../domain/investments";
import {
  useStocksPortfolio,
  type StockPositionSortKey as SortKey,
} from "../composables/useStocksPortfolio";
import { reportingCurrency } from "../i18n";
import type {
  ImporterCatalogItem,
  StockAccount,
  StockChartResponse,
  StockInstrument,
  StockOrder,
  StockPerformanceResponse,
  StockPosition,
  StockPrice,
  PriceFetchResponse,
} from "../types/api";
import {
  instrumentById,
  instrumentCurrency,
  instrumentIdentity,
  instrumentName,
  instrumentTicker,
} from "../domain/instruments";

type Range = "6m" | "1y" | "2y" | "custom";
const { t, n, d, locale } = useI18n();
const accounts = ref<StockAccount[]>([]);
const importerCatalog = ref<ImporterCatalogItem[]>([]);
const positions = ref<StockPosition[]>([]);
const orders = ref<StockOrder[]>([]);
const instruments = ref<StockInstrument[]>([]);
const prices = ref<StockPrice[]>([]);
const performance = ref<StockPerformanceResponse | null>(null);
const chart = ref<StockChartResponse | null>(null);
const selectedAccount = ref(
  new URLSearchParams(window.location.search).get("account") ?? "all",
);
const selectedInstrumentId = ref("");
const range = ref<Range>("1y");
const chartRange = ref<Range>("1y");
const mode = ref<"value" | "return">("value");
const loading = ref(true);
const performanceLoading = ref(false);
const chartLoading = ref(false);
const refreshingPrices = ref(false);
const error = ref("");
const performanceError = ref("");
const chartError = ref("");
const priceMessage = ref("");
const assetReturnMode = ref<AssetReturnMode>("percent");
const cashbackAsBenefit = ref(
  localStorage.getItem("finanzr_ignore_savebacks") !== "false",
);
const positionsCollapsed = ref(
  localStorage.getItem("finanzr-stocks-positions-collapsed") === "true",
);
const movementsCollapsed = ref(
  localStorage.getItem("finanzr-stocks-movements-collapsed") === "true",
);
const movementIsin = ref("all");
const movementType = ref("all");
const movementStart = ref("");
const movementEnd = ref("");
const movementDraftStart = ref("");
const movementDraftEnd = ref("");
const movementPage = ref(1);
const accountDialog = ref<HTMLDialogElement>();
const calendarDialog = ref<HTMLDialogElement>();
const chartCalendarDialog = ref<HTMLDialogElement>();
const movementCalendarDialog = ref<HTMLDialogElement>();
const accountDialogMode = ref<"create" | "edit">("create");
const accountName = ref("");
const accountProvider = ref("");
const accountImporter = ref("");
const accountCurrency = ref("EUR");
const accountBusy = ref(false);
const accountError = ref("");
const accountDeleteArmed = ref(false);
const assetEditor = ref<AssetEditorHandle>();
const movementEditor = ref<MovementEditorHandle>();
const movementDelete = ref<MovementDeleteHandle>();
const today = new Date();
const dateInput = (date: Date) => date.toISOString().slice(0, 10);
const yearAgo = new Date(today);
yearAgo.setFullYear(yearAgo.getFullYear() - 1);
const customStart = ref(dateInput(yearAgo));
const customEnd = ref(dateInput(today));
const draftStart = ref(customStart.value);
const draftEnd = ref(customEnd.value);
const chartCustomStart = ref(customStart.value);
const chartCustomEnd = ref(customEnd.value);
const chartDraftStart = ref(chartCustomStart.value);
const chartDraftEnd = ref(chartCustomEnd.value);
let dashboardGeneration = 0;
let performanceRequestGeneration = 0;
let chartRequestGeneration = 0;
let assetSaveGeneration = 0;

const ranges = computed(() => [
  { key: "6m" as Range, label: t("stocks.ranges.sixMonths") },
  { key: "1y" as Range, label: t("stocks.ranges.oneYear") },
  { key: "2y" as Range, label: t("stocks.ranges.twoYears") },
  { key: "custom" as Range, label: t("stocks.ranges.calendar") },
]);
const baseCurrency = computed(() => reportingCurrency.value);
const stockBaseCurrency = computed(() => baseCurrency.value);
const {
  openPositions,
  normalizedTopPositions,
  totalValue,
  totalCost,
  unrealizedPnl,
  realizedPnl,
  totalPnl,
  openReturn,
  pricedPositions,
  selectedChartOrders,
  averagePrice,
  positionSortKey,
  positionSortDirection,
  sortedPositions,
  baseAmount,
  basePrice,
  baseFee,
  sortPositions,
  ariaSort,
} = useStocksPortfolio({
  positions,
  orders,
  instruments,
  selectedInstrumentId,
  baseCurrency,
  locale,
});
const selectedAccountRow = computed(
  () =>
    accounts.value.find(
      (account) => String(account.id) === selectedAccount.value,
    ) ?? null,
);
const selectedAccountLabel = computed(() =>
  selectedAccount.value === "all"
    ? t("stocks.accounts.all")
    : (selectedAccountRow.value?.name ?? t("stocks.accounts.fallback")),
);
const compatibleImporters = computed(() =>
  importerCatalog.value.filter((item) => item.target === "stock_orders"),
);
const selectedImporter = computed(
  () =>
    compatibleImporters.value.find(
      (item) => item.slug === selectedAccountRow.value?.importer_slug,
    ) ?? null,
);
const isTradeRepublic = computed(
  () =>
    selectedAccountRow.value?.platform
      .toLowerCase()
      .includes("trade republic") ?? false,
);
const normalizedAccounts = computed(() =>
  accounts.value.map(adaptStockAccount),
);
const normalizedPerformance = computed(() =>
  performance.value
    ? adaptStockPerformance(performance.value, {
        baseCurrency: baseCurrency.value,
      })
    : null,
);
const performancePoints = computed<NormalizedPerformancePoint[]>(
  () => normalizedPerformance.value?.data ?? [],
);
const firstPerformance = computed(() => performancePoints.value[0] ?? null);
const lastPerformance = computed(() => performancePoints.value.at(-1) ?? null);
const periodPnl = computed(() =>
  firstPerformance.value && lastPerformance.value
    ? lastPerformance.value.pnl - firstPerformance.value.pnl
    : 0,
);
const periodPnlPercent = computed(() =>
  firstPerformance.value?.value
    ? periodPnl.value / firstPerformance.value.value
    : 0,
);
const periodLabel = computed(() =>
  range.value === "custom"
    ? t("stocks.performance.periodPnl")
    : t("stocks.performance.rangePnl", {
        range:
          ranges.value.find((item) => item.key === range.value)?.label ?? "",
      }),
);
const displayedRange = computed(() =>
  performancePoints.value.length
    ? `${displayDate(performancePoints.value[0].date)} → ${displayDate(performancePoints.value.at(-1)?.date ?? "")}`
    : range.value === "custom"
      ? `${displayDate(customStart.value)} → ${displayDate(customEnd.value)}`
      : (ranges.value.find((item) => item.key === range.value)?.label ??
        t("stocks.ranges.period")),
);
const chartRangeLabel = computed(() =>
  chart.value?.data.length
    ? `${displayDate(chart.value.data[0].date)} → ${displayDate(chart.value.data.at(-1)?.date ?? "")}`
    : chartRange.value === "custom"
      ? `${displayDate(chartCustomStart.value)} → ${displayDate(chartCustomEnd.value)}`
      : (ranges.value.find((item) => item.key === chartRange.value)?.label ??
        t("stocks.ranges.period")),
);
const normalizedChart = computed(() =>
  chart.value
    ? adaptStockChart(chart.value, { baseCurrency: baseCurrency.value })
    : null,
);
const chartPoints = computed(() => normalizedChart.value?.data ?? []);
const operationAssets = computed(() =>
  instruments.value.map((instrument) => ({
    id: instrumentIdentity(instrument),
    label: instrumentName(instrument) + " · " + instrumentIdentity(instrument),
    currency: instrumentCurrency(instrument),
  })),
);
const filteredOrders = computed(() =>
  [...orders.value]
    .filter(
      (order) =>
        movementIsin.value === "all" || order.isin === movementIsin.value,
    )
    .filter(
      (order) =>
        movementType.value === "all" ||
        operationGroup(order) === movementType.value,
    )
    .filter(
      (order) =>
        !movementStart.value || order.trade_date >= movementStart.value,
    )
    .filter(
      (order) => !movementEnd.value || order.trade_date <= movementEnd.value,
    )
    .sort((a, b) => b.trade_date.localeCompare(a.trade_date, locale.value)),
);
const movementPages = computed(() =>
  Math.max(1, Math.ceil(filteredOrders.value.length / 15)),
);
const displayedOrders = computed(() =>
  filteredOrders.value.slice(
    (movementPage.value - 1) * 15,
    movementPage.value * 15,
  ),
);
const movementRangeLabel = computed(() =>
  movementStart.value && movementEnd.value
    ? `${displayDate(movementStart.value)} → ${displayDate(movementEnd.value)}`
    : t("stocks.movements.allHistory"),
);
const customRangeValid = computed(() =>
  Boolean(
    draftStart.value &&
    draftEnd.value &&
    Date.parse(draftStart.value) <= Date.parse(draftEnd.value),
  ),
);
const chartCustomRangeValid = computed(() =>
  Boolean(
    chartDraftStart.value &&
    chartDraftEnd.value &&
    Date.parse(chartDraftStart.value) <= Date.parse(chartDraftEnd.value),
  ),
);
const movementRangeValid = computed(() =>
  Boolean(
    movementDraftStart.value &&
    movementDraftEnd.value &&
    Date.parse(movementDraftStart.value) <= Date.parse(movementDraftEnd.value),
  ),
);
const positionSortColumns = computed(() => [
  { key: "asset" as SortKey, label: t("stocks.positions.asset") },
  { key: "ticker" as SortKey, label: t("stocks.positions.ticker") },
  { key: "cost" as SortKey, label: t("stocks.positions.contributed") },
  { key: "quantity" as SortKey, label: t("stocks.positions.shares") },
  { key: "averagePrice" as SortKey, label: t("stocks.positions.averagePrice") },
  { key: "currentPrice" as SortKey, label: t("stocks.positions.currentPrice") },
  { key: "value" as SortKey, label: t("stocks.positions.value") },
  { key: "pnl" as SortKey, label: t("stocks.positions.pnl") },
  { key: "return" as SortKey, label: t("stocks.positions.return") },
]);
const allocationItems = computed<InvestmentAllocationItem[]>(() => {
  const valued = openPositions.value.flatMap((position) =>
    typeof position.current_value === "number" && position.current_value > 0
      ? [{ position, value: position.current_value }]
      : [],
  );
  const total = valued.reduce((sum, item) => sum + item.value, 0);
  if (!(total > 0)) return [];
  const colors = ["#3ddc97", "#5b8def", "#d69b3d", "#9b7be8", "#e67b78"];
  const items = valued.slice(0, 5).map(({ position, value }, index) => ({
    key: position.instrument_id,
    label: position.name,
    value,
    share: value / total,
    color: colors[index],
  }));
  const other = valued.slice(5).reduce((sum, item) => sum + item.value, 0);
  return other > 0
    ? [
        ...items,
        {
          key: "other",
          label: t("stocks.positions.other"),
          value: other,
          share: other / total,
          color: "#78909c",
        },
      ]
    : items;
});
const allocationTotal = computed(() =>
  allocationItems.value.reduce((sum, item) => sum + item.value, 0),
);
const latestUpdate = computed(() => {
  const dates = prices.value
    .map((price) => price.quoted_at.slice(0, 10))
    .filter(Boolean)
    .sort();
  return dates.length
    ? d(new Date(`${dates.at(-1)}T00:00:00`), "short")
    : t("stocks.prices.neverUpdated");
});
const accountBarLabels = computed<InvestmentAccountBarLabels>(() => ({
  portfolioView: t("stocks.accounts.portfolioView"),
  accountAria: t("stocks.accounts.selectAria"),
  allAccounts: t("stocks.accounts.all"),
  importStatement: t("stocks.accounts.importStatement"),
  manage: t("stocks.accounts.manage"),
  add: t("stocks.accounts.add"),
}));
const overviewLabels = computed<InvestmentOverviewLabels>(() => ({
  assets: {
    section: t("stocks.assets.section"),
    title: t("stocks.assets.title"),
    asset: t("stocks.assets.asset"),
    portfolioValue: t("stocks.assets.portfolioValue"),
    contributed: t("stocks.assets.contributed"),
    currentPrice: t("stocks.assets.currentPrice"),
    averagePrice: t("stocks.assets.averagePrice"),
    value: t("stocks.assets.value"),
    return: t("stocks.assets.return"),
    pnl: t("stocks.assets.pnl"),
    pending: t("stocks.positions.pending"),
    emptyTitle: t("stocks.assets.emptyTitle"),
    emptyDescription: t("stocks.assets.emptyDescription"),
  },
  kpis: {
    section: t("stocks.kpis.section"),
    title: t("stocks.kpis.title"),
    portfolioValue: t("stocks.kpis.portfolioValue"),
    openAsset: t("stocks.assets.openAsset"),
    openAssets: t("stocks.assets.openAssets"),
    unrealizedPnl: t("stocks.kpis.unrealizedPnl"),
    versusCost: t("stocks.kpis.versusCost"),
    realizedPnl: t("stocks.kpis.realizedPnl"),
    recordedSales: t("stocks.kpis.recordedSales"),
    totalPnl: t("stocks.kpis.totalPnl"),
    realizedAndOpen: t("stocks.kpis.realizedAndOpen"),
    marketData: t("stocks.kpis.marketData"),
    updating: t("stocks.kpis.updating"),
    update: t("stocks.kpis.update"),
  },
}));
const importConfig = computed<InvestmentImportConfig | null>(() =>
  selectedImporter.value
    ? {
        endpoint: `/account-imports/stocks/${selectedAccount.value}`,
        accountsEndpoint: "/stock-accounts",
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
  return n(value, {
    style: "currency",
    currency: currency || "EUR",
    maximumFractionDigits: 2,
  });
}
function percentage(value: number) {
  return n(value, "percent");
}
function quantity(value: number) {
  return n(value, { maximumFractionDigits: 8 });
}
function signedMoney(value: number) {
  return `${value >= 0 ? "+" : "−"}${money(Math.abs(value))}`;
}
function hasOriginalCurrency(order: StockOrder) {
  return Boolean(order.currency && order.currency !== stockBaseCurrency.value);
}
function isBuy(order: StockOrder) {
  return order.operation_type === "buy";
}
function operationGroup(order: StockOrder) {
  return isBuy(order) ? "in" : "out";
}
function operationLabel(order: StockOrder) {
  return isBuy(order) ? t("stocks.movements.buy") : t("stocks.movements.sell");
}
function positionReturn(position: StockPosition) {
  return position.cost ? (position.unrealized_pnl ?? 0) / position.cost : 0;
}
function assetTicker(position: StockPosition) {
  const instrument = instrumentById(instruments.value, position.instrument_id);
  return instrumentTicker(instrument) || instrumentIdentity(instrument);
}
function positionIdentity(position: StockPosition) {
  return instrumentIdentity(
    instrumentById(instruments.value, position.instrument_id),
  );
}
function segmentAria(item: InvestmentAllocationItem) {
  return t("stocks.positions.marketValueSegmentAria", {
    asset: item.label,
    share: percentage(item.share),
  });
}
function detailId(isin: string) {
  return `stock-price-detail-${
    Array.from(isin)
      .map((character) =>
        /[a-z0-9_-]/i.test(character)
          ? character.toLowerCase()
          : `x${character.codePointAt(0)?.toString(16) ?? "0"}x`,
      )
      .join("") || "stock"
  }`;
}
function sortAria(key: SortKey, label: string) {
  return t(
    positionSortKey.value === key && positionSortDirection.value === "asc"
      ? "stocks.positions.sortDescendingAria"
      : "stocks.positions.sortAscendingAria",
    { column: label },
  );
}
function syncAccountUrl() {
  const url = new URL(window.location.href);
  if (selectedAccount.value === "all") url.searchParams.delete("account");
  else url.searchParams.set("account", selectedAccount.value);
  window.history.replaceState(window.history.state, "", url);
}
function accountQuery() {
  const params = new URLSearchParams();
  if (selectedAccount.value !== "all")
    params.set("account_id", selectedAccount.value);
  if (cashbackAsBenefit.value) params.set("ignore_savebacks", "true");
  const query = params.toString();
  return query ? `?${query}` : "";
}
function performanceQuery() {
  const params = new URLSearchParams({ account_id: selectedAccount.value });
  if (range.value === "custom") {
    params.set("start", customStart.value);
    params.set("end", customEnd.value);
  } else params.set("range", range.value);
  if (cashbackAsBenefit.value) params.set("ignore_savebacks", "true");
  return params.toString();
}
function chartQuery() {
  if (chartRange.value === "custom") {
    const days =
      Math.abs(
        Date.parse(chartCustomEnd.value) - Date.parse(chartCustomStart.value),
      ) / 86_400_000;
    const interval = days > 1500 ? "1mo" : days > 400 ? "1wk" : "1d";
    return `start=${encodeURIComponent(chartCustomStart.value)}&end=${encodeURIComponent(chartCustomEnd.value)}&interval=${interval}`;
  }
  return `range=${chartRange.value}&interval=${chartRange.value === "2y" ? "1wk" : "1d"}`;
}
function initializeMovementRange() {
  if (!orders.value.length || movementStart.value) return;
  const dates = orders.value.map((order) => order.trade_date).sort();
  movementStart.value = dates[0];
  movementEnd.value = dates.at(-1) ?? dates[0];
}
async function loadDashboard(showLoading = true, loadSelectedChart = true) {
  const generation = ++dashboardGeneration;
  performanceRequestGeneration += 1;
  chartRequestGeneration += 1;
  performance.value = null;
  chart.value = null;
  performanceError.value = "";
  chartError.value = "";
  if (showLoading) loading.value = true;
  error.value = "";
  try {
    const [nextAccounts, nextImporters] = await Promise.all([
      api<StockAccount[]>("/stock-accounts"),
      api<ImporterCatalogItem[]>("/importers"),
    ]);
    if (generation !== dashboardGeneration) return;
    accounts.value = nextAccounts;
    importerCatalog.value = nextImporters;
    if (
      selectedAccount.value !== "all" &&
      !accounts.value.some(
        (account) => String(account.id) === selectedAccount.value,
      )
    ) {
      selectedAccount.value = "all";
      syncAccountUrl();
    }
    const query = accountQuery();
    const [nextPositions, nextOrders, nextInstruments, nextPrices] =
      await Promise.all([
        api<StockPosition[]>(`/stock-analysis${query}`),
        api<StockOrder[]>(
          selectedAccount.value === "all"
            ? "/stock-orders"
            : `/stock-orders?account_id=${selectedAccount.value}`,
        ),
        api<StockInstrument[]>("/stocks"),
        api<StockPrice[]>("/stock-prices"),
      ]);
    if (generation !== dashboardGeneration) return;
    positions.value = nextPositions;
    orders.value = nextOrders;
    instruments.value = nextInstruments;
    prices.value = nextPrices;
    initializeMovementRange();
    const available = openPositions.value.map(
      (position) => position.instrument_id,
    );
    if (!available.includes(selectedInstrumentId.value))
      selectedInstrumentId.value = "";
  } catch (reason) {
    if (generation !== dashboardGeneration) return;
    error.value =
      reason instanceof Error ? reason.message : t("stocks.errors.load");
  } finally {
    if (showLoading && generation === dashboardGeneration)
      loading.value = false;
  }
  if (generation === dashboardGeneration && !error.value) {
    await loadPerformance(generation);
    if (
      loadSelectedChart &&
      generation === dashboardGeneration &&
      selectedInstrumentId.value
    )
      await loadChart(generation);
  }
}
async function loadPerformance(generation = dashboardGeneration) {
  if (generation !== dashboardGeneration) return;
  const request = ++performanceRequestGeneration;
  performanceLoading.value = true;
  performanceError.value = "";
  try {
    const result = await api<StockPerformanceResponse>(
      `/investment-performance/stock?${performanceQuery()}`,
    );
    if (
      generation !== dashboardGeneration ||
      request !== performanceRequestGeneration
    )
      return;
    performance.value = result;
  } catch (reason) {
    if (
      generation !== dashboardGeneration ||
      request !== performanceRequestGeneration
    )
      return;
    performance.value = null;
    performanceError.value =
      reason instanceof Error ? reason.message : t("stocks.errors.performance");
  } finally {
    if (
      generation === dashboardGeneration &&
      request === performanceRequestGeneration
    )
      performanceLoading.value = false;
  }
}
async function loadChart(generation = dashboardGeneration) {
  if (generation !== dashboardGeneration || !selectedInstrumentId.value) return;
  const request = ++chartRequestGeneration;
  const instrumentId = selectedInstrumentId.value;
  if (!instrumentId) {
    chart.value = null;
    chartLoading.value = false;
    chartError.value = t("stocks.errors.chart");
    return;
  }
  chartLoading.value = true;
  chartError.value = "";
  try {
    const result = await api<StockChartResponse>(
      `/stock-chart/${encodeURIComponent(instrumentId)}?${chartQuery()}`,
    );
    if (
      generation !== dashboardGeneration ||
      request !== chartRequestGeneration
    )
      return;
    chart.value = result;
  } catch (reason) {
    if (
      generation !== dashboardGeneration ||
      request !== chartRequestGeneration
    )
      return;
    chart.value = null;
    chartError.value =
      reason instanceof Error ? reason.message : t("stocks.errors.chart");
  } finally {
    if (
      generation === dashboardGeneration &&
      request === chartRequestGeneration
    )
      chartLoading.value = false;
  }
}
function closePosition() {
  selectedInstrumentId.value = "";
  chartRequestGeneration += 1;
  chart.value = null;
  chartLoading.value = false;
  chartError.value = "";
}
async function togglePosition(instrumentId: string) {
  if (selectedInstrumentId.value === instrumentId) {
    closePosition();
    return;
  }
  selectedInstrumentId.value = instrumentId;
  await loadChart();
}
async function selectRange(value: Range) {
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
async function selectChartRange(value: Range) {
  if (value === "custom") {
    chartDraftStart.value = chartCustomStart.value;
    chartDraftEnd.value = chartCustomEnd.value;
    chartCalendarDialog.value?.showModal();
    return;
  }
  chartRange.value = value;
  await loadChart();
}
function closeChartCalendar() {
  chartCalendarDialog.value?.close();
}
async function applyChartCustomRange() {
  if (!chartCustomRangeValid.value) return;
  chartCustomStart.value = chartDraftStart.value;
  chartCustomEnd.value = chartDraftEnd.value;
  chartRange.value = "custom";
  closeChartCalendar();
  await loadChart();
}
async function changeAccount(account: string) {
  selectedAccount.value = account;
  movementIsin.value = "all";
  movementType.value = "all";
  movementStart.value = "";
  movementEnd.value = "";
  movementPage.value = 1;
  closePosition();
  syncAccountUrl();
  await loadDashboard(false);
}
function openAccountDialog() {
  accountDialogMode.value = "create";
  accountName.value = "";
  accountProvider.value = "";
  accountImporter.value = "";
  accountCurrency.value = "EUR";
  accountError.value = "";
  accountDeleteArmed.value = false;
  accountDialog.value?.showModal();
}
function openEditAccountDialog() {
  if (!selectedAccountRow.value) return;
  accountDialogMode.value = "edit";
  accountName.value = selectedAccountRow.value.name;
  accountProvider.value = selectedAccountRow.value.platform;
  accountImporter.value = selectedAccountRow.value.importer_slug || "none";
  accountCurrency.value = selectedAccountRow.value.currency || "EUR";
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
        ? `/stock-accounts/${selectedAccount.value}`
        : "/stock-accounts";
    const saved = await api<StockAccount>(
      target,
      json(accountDialogMode.value === "edit" ? "PUT" : "POST", {
        name,
        platform: provider,
        importer_slug: accountImporter.value,
        currency: accountCurrency.value.trim().toUpperCase(),
      }),
    );
    selectedAccount.value = String(saved.id);
    syncAccountUrl();
    accountDialog.value?.close();
    await loadDashboard();
  } catch (reason) {
    accountError.value =
      reason instanceof Error ? reason.message : t("stocks.errors.saveAccount");
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
  try {
    await api(`/stock-accounts/${selectedAccount.value}`, { method: "DELETE" });
    selectedAccount.value = "all";
    syncAccountUrl();
    accountDialog.value?.close();
    await loadDashboard();
  } catch (reason) {
    accountError.value =
      reason instanceof Error
        ? reason.message
        : t("stocks.errors.deleteAccount");
  } finally {
    accountBusy.value = false;
  }
}
async function refreshPrices() {
  refreshingPrices.value = true;
  try {
    const result = await api<PriceFetchResponse>("/stock-prices/fetch", {
      method: "POST",
    });
    const failed = result.results.filter((item) => item.error).length;
    priceMessage.value = failed
      ? t("stocks.prices.failed", failed)
      : t("stocks.prices.refreshed");
    await loadDashboard();
  } catch (reason) {
    priceMessage.value =
      reason instanceof Error ? reason.message : t("stocks.errors.refresh");
  } finally {
    refreshingPrices.value = false;
  }
}
async function toggleCashback() {
  localStorage.setItem(
    "finanzr_ignore_savebacks",
    String(cashbackAsBenefit.value),
  );
  await loadDashboard(false);
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
function togglePositions() {
  positionsCollapsed.value = !positionsCollapsed.value;
  localStorage.setItem(
    "finanzr-stocks-positions-collapsed",
    String(positionsCollapsed.value),
  );
}
function toggleMovements() {
  movementsCollapsed.value = !movementsCollapsed.value;
  localStorage.setItem(
    "finanzr-stocks-movements-collapsed",
    String(movementsCollapsed.value),
  );
}
function openNewMovement() {
  movementEditor.value?.openCreate();
}
function openEditMovement(order: StockOrder) {
  movementEditor.value?.openEdit(order);
}
function askDeleteOrder(order: StockOrder) {
  movementDelete.value?.open(order);
}
async function handleAssetSaved(asset: EditableAsset) {
  const generation = ++assetSaveGeneration;
  const targetInstrumentId = asset.id;
  if (targetInstrumentId) selectedInstrumentId.value = targetInstrumentId;
  await loadDashboard(true, false);
  if (generation !== assetSaveGeneration || !targetInstrumentId) return;
  selectedInstrumentId.value = targetInstrumentId;
  await loadChart();
}
watch([movementIsin, movementType, movementStart, movementEnd], () => {
  movementPage.value = 1;
});
onMounted(loadDashboard);
</script>

<template>
  <section class="stocks-page" aria-live="polite">
    <div
      v-if="loading"
      class="stocks-loading"
      role="status"
      :aria-label="t('stocks.loadingAria')"
    >
      <div />
      <div />
    </div>
    <div v-else-if="error" class="overview-error" role="alert">
      <span aria-hidden="true">!</span>
      <div>
        <strong>{{ t("stocks.errors.title") }}</strong>
        <p>{{ error }}</p>
      </div>
      <button type="button" @click="loadDashboard()">
        {{ t("stocks.retry") }}
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
        :currency-label="baseCurrency"
        :asset-return-mode="assetReturnMode"
        :labels="overviewLabels"
        :format-money="money"
        :format-percentage="percentage"
        :format-signed-money="signedMoney"
        @update:asset-return-mode="assetReturnMode = $event"
        @refresh="refreshPrices"
      />

      <article class="fund-performance-panel stock-performance-panel">
        <header class="fund-performance-header">
          <div>
            <p class="section-label">{{ t("stocks.performance.section") }}</p>
            <h2>{{ t("stocks.performance.title") }}</h2>
            <p class="fund-range-label">
              {{ selectedAccountLabel }} · {{ displayedRange }}
            </p>
          </div>
          <div class="stock-performance-controls">
            <div
              class="fund-mode-control"
              :aria-label="t('stocks.performance.chartModeAria')"
            >
              <button
                type="button"
                :class="{ active: mode === 'value' }"
                :aria-pressed="mode === 'value'"
                @click="mode = 'value'"
              >
                {{ t("stocks.performance.portfolioValue") }}</button
              ><button
                type="button"
                :class="{ active: mode === 'return' }"
                :aria-pressed="mode === 'return'"
                @click="mode = 'return'"
              >
                {{ t("stocks.performance.returnPercent") }}
              </button>
            </div>
            <div
              class="fund-range-control"
              :aria-label="t('stocks.performance.rangeAria')"
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
        <div class="stock-performance-meta">
          <div>
            <small>{{ t("stocks.performance.closingValue") }}</small
            ><strong>{{ money(lastPerformance?.value ?? totalValue) }}</strong>
          </div>
          <div>
            <small>{{ t("stocks.performance.contributedCapital") }}</small
            ><strong>{{
              money(lastPerformance?.invested ?? totalCost)
            }}</strong>
          </div>
          <div>
            <small>{{ t("stocks.performance.totalPnl") }}</small
            ><strong
              :class="{
                positive: (lastPerformance?.pnl ?? 0) >= 0,
                negative: (lastPerformance?.pnl ?? 0) < 0,
              }"
              >{{ signedMoney(lastPerformance?.pnl ?? 0) }}</strong
            ><span>{{
              percentage((lastPerformance?.pnlPercent ?? 0) / 100)
            }}</span>
          </div>
          <div>
            <small>{{ t("stocks.performance.realizedPnl") }}</small
            ><strong
              :class="{ positive: realizedPnl >= 0, negative: realizedPnl < 0 }"
              >{{ signedMoney(realizedPnl) }}</strong
            >
          </div>
          <div>
            <small>{{ periodLabel }}</small
            ><strong
              :class="{ positive: periodPnl >= 0, negative: periodPnl < 0 }"
              >{{ signedMoney(periodPnl) }}</strong
            ><span>{{ percentage(periodPnlPercent) }}</span>
          </div>
        </div>
        <label v-if="isTradeRepublic" class="cashback-control"
          ><span
            ><strong>{{ t("stocks.cashback.title") }}</strong
            ><small>{{ t("stocks.cashback.description") }}</small></span
          ><input
            v-model="cashbackAsBenefit"
            type="checkbox"
            @change="toggleCashback"
        /></label>
        <div v-if="performanceLoading" class="fund-chart-state">
          {{ t("stocks.performance.calculating") }}
        </div>
        <div v-else-if="performanceError" class="fund-chart-state error-state">
          <strong>{{ t("stocks.performance.unavailable") }}</strong>
          <p>{{ performanceError }}</p>
          <button type="button" @click="loadPerformance()">
            {{ t("stocks.retry") }}
          </button>
        </div>
        <FundPerformanceChart
          v-else-if="performancePoints.length >= 2"
          :points="performancePoints"
          :mode="mode"
        />
        <div v-else class="fund-chart-state">
          <strong>{{ t("stocks.performance.insufficientHistory") }}</strong>
          <p>{{ t("stocks.performance.insufficientHistoryHint") }}</p>
        </div>
      </article>

      <article
        class="fund-performance-panel positions-panel"
        :class="{ collapsed: positionsCollapsed }"
      >
        <header class="fund-secondary-header">
          <div>
            <p class="section-label">{{ t("stocks.positions.section") }}</p>
            <h2>{{ t("stocks.positions.title") }}</h2>
            <p class="fund-range-label">
              {{
                t(
                  positions.length === 1
                    ? "stocks.positions.pricedOne"
                    : "stocks.positions.pricedMany",
                  { priced: pricedPositions, total: positions.length },
                )
              }}
              ·
              {{
                t("stocks.positions.pricesInCurrency", {
                  currency: stockBaseCurrency,
                })
              }}
            </p>
          </div>
          <div class="stock-secondary-actions">
            <InvestmentAddAssetButton
              class="stock-add-asset-button"
              :label="t('stocks.assets.add')"
              @add="assetEditor?.openCreate()"
            />
            <InvestmentCollapseButton
              :collapsed="positionsCollapsed"
              controls="stock-positions-content"
              :label="
                t(
                  positionsCollapsed
                    ? 'stocks.positions.expandAria'
                    : 'stocks.positions.collapseAria',
                )
              "
              @toggle="togglePositions"
            />
          </div>
        </header>
        <div
          v-show="!positionsCollapsed"
          id="stock-positions-content"
          class="fund-positions-content"
        >
          <InvestmentAllocationStrip
            :items="allocationItems"
            :total="allocationTotal"
            :account-label="selectedAccountLabel"
            :title="t('stocks.positions.marketValueDistribution')"
            :bar-label="t('stocks.positions.marketValueDistributionBarAria')"
            :empty-label="t('stocks.positions.noMarketValueDistribution')"
            :format-value="money"
            :format-share="percentage"
            :segment-aria="segmentAria"
          />
          <div class="fund-table-scroll position-table-scroll">
            <table class="fund-table position-table">
              <thead>
                <tr>
                  <th
                    v-for="column in positionSortColumns"
                    :key="column.key"
                    :aria-sort="ariaSort(column.key)"
                  >
                    <button
                      type="button"
                      class="fund-sort-button"
                      :aria-label="sortAria(column.key, column.label)"
                      @click="sortPositions(column.key)"
                    >
                      {{ column.label }}
                      <span>{{
                        positionSortKey === column.key
                          ? positionSortDirection === "asc"
                            ? "↑"
                            : "↓"
                          : ""
                      }}</span>
                    </button>
                  </th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <template
                  v-for="position in sortedPositions"
                  :key="position.instrument_id"
                  ><tr
                    class="fund-position-row"
                    :class="{
                      active: selectedInstrumentId === position.instrument_id,
                    }"
                    @click="togglePosition(position.instrument_id)"
                  >
                    <td>
                      <button
                        type="button"
                        class="fund-position-disclosure"
                        :aria-expanded="
                          selectedInstrumentId === position.instrument_id
                        "
                        :aria-controls="detailId(position.instrument_id)"
                        :aria-label="
                          t(
                            selectedInstrumentId === position.instrument_id
                              ? 'stocks.positions.collapseChartAria'
                              : 'stocks.positions.expandChartAria',
                            { asset: position.name },
                          )
                        "
                        @click.stop="togglePosition(position.instrument_id)"
                        @keydown.enter.prevent.stop="
                          togglePosition(position.instrument_id)
                        "
                        @keydown.space.prevent.stop="
                          togglePosition(position.instrument_id)
                        "
                      >
                        <span class="fund-position-disclosure-copy"
                          ><strong>{{ position.name }}</strong
                          ><small>{{ positionIdentity(position) }}</small></span
                        ><span aria-hidden="true">⌄</span>
                      </button>
                    </td>
                    <td>{{ assetTicker(position) }}</td>
                    <td>{{ money(position.cost) }}</td>
                    <td>{{ quantity(position.quantity) }}</td>
                    <td>
                      {{
                        money(
                          position.quantity
                            ? position.cost / position.quantity
                            : 0,
                        )
                      }}
                    </td>
                    <td>
                      {{
                        position.current_price == null
                          ? t("stocks.positions.pending")
                          : money(position.current_price)
                      }}
                    </td>
                    <td>
                      {{
                        position.current_value == null
                          ? "—"
                          : money(position.current_value)
                      }}
                    </td>
                    <td
                      :class="{
                        positive: (position.unrealized_pnl ?? 0) >= 0,
                        negative: (position.unrealized_pnl ?? 0) < 0,
                      }"
                    >
                      <strong>{{
                        position.unrealized_pnl == null
                          ? "—"
                          : signedMoney(position.unrealized_pnl)
                      }}</strong>
                    </td>
                    <td
                      :class="{
                        positive: positionReturn(position) >= 0,
                        negative: positionReturn(position) < 0,
                      }"
                    >
                      <strong>{{
                        percentage(positionReturn(position))
                      }}</strong>
                    </td>
                    <td>
                      <button
                        type="button"
                        class="fund-edit-icon-button"
                        :aria-label="t('stocks.positions.editAria')"
                        @click.stop="
                          assetEditor?.openEdit(
                            instrumentById(instruments, position.instrument_id),
                          )
                        "
                      >
                        ✎
                      </button>
                    </td>
                  </tr>
                  <tr
                    v-if="selectedInstrumentId === position.instrument_id"
                    class="fund-inline-detail-row"
                  >
                    <td :colspan="positionSortColumns.length + 1">
                      <div
                        :id="detailId(position.instrument_id)"
                        class="fund-inline-price-panel"
                        role="region"
                        :aria-label="
                          t('stocks.positions.priceDetailAria', {
                            asset: position.name,
                          })
                        "
                      >
                        <div class="fund-inline-chart-toolbar">
                          <div class="fund-chart-legend">
                            <span
                              >▌ {{ t("stocks.chart.risingCandle") }} /
                              {{ t("stocks.chart.fallingCandle") }}</span
                            ><span>╍ {{ t("stocks.chart.averagePrice") }}</span
                            ><span>+ {{ t("stocks.movements.buy") }}</span
                            ><span>− {{ t("stocks.movements.sell") }}</span>
                          </div>
                          <div class="fund-inline-range">
                            <p class="fund-range-label">
                              {{ chartRangeLabel }}
                            </p>
                            <div
                              class="fund-range-control"
                              :aria-label="t('stocks.chart.rangeAria')"
                            >
                              <button
                                v-for="item in ranges"
                                :key="item.key"
                                type="button"
                                :class="{ active: chartRange === item.key }"
                                :aria-pressed="chartRange === item.key"
                                @click="selectChartRange(item.key)"
                              >
                                {{ item.label }}
                              </button>
                            </div>
                          </div>
                        </div>
                        <div v-if="chartLoading" class="fund-chart-state">
                          {{ t("stocks.chart.loading") }}
                        </div>
                        <div
                          v-else-if="chartError"
                          class="fund-chart-state error-state"
                        >
                          <strong>{{ t("stocks.chart.unavailable") }}</strong>
                          <p>{{ chartError }}</p>
                          <button type="button" @click="loadChart()">
                            {{ t("stocks.retry") }}
                          </button>
                        </div>
                        <CryptoCandlestickChart
                          v-else-if="chartPoints.length"
                          :points="chartPoints"
                          :operations="selectedChartOrders"
                          :average-price="averagePrice"
                          operation-marker-shape="pin"
                        />
                        <div v-else class="fund-chart-state">
                          {{ t("stocks.chart.empty") }}
                        </div>
                      </div>
                    </td>
                  </tr></template
                >
              </tbody>
            </table>
          </div>
          <div v-if="!sortedPositions.length" class="fund-empty-compact">
            {{ t("stocks.assets.emptyDescription") }}
          </div>
        </div>
      </article>

      <article
        class="fund-performance-panel movements-panel"
        :class="{ collapsed: movementsCollapsed }"
      >
        <header class="fund-secondary-header">
          <div>
            <p class="section-label">{{ t("stocks.movements.section") }}</p>
            <h2>{{ t("stocks.movements.title") }}</h2>
            <p class="fund-range-label">
              {{
                t(
                  filteredOrders.length === 1
                    ? "stocks.movements.operation"
                    : "stocks.movements.operations",
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
                + {{ t("stocks.movements.add") }}</button
              ><select
                v-model="movementIsin"
                :aria-label="t('stocks.movements.assetFilterAria')"
              >
                <option value="all">
                  {{ t("stocks.movements.allAssets") }}
                </option>
                <option
                  v-for="position in positions"
                  :key="position.instrument_id"
                  :value="positionIdentity(position)"
                >
                  {{ position.name }}
                </option></select
              ><select
                v-model="movementType"
                :aria-label="t('stocks.movements.filterTypeAria')"
              >
                <option value="all">
                  {{ t("stocks.movements.allMovements") }}
                </option>
                <option value="in">{{ t("stocks.movements.entries") }}</option>
                <option value="out">
                  {{ t("stocks.movements.exits") }}
                </option></select
              ><button
                type="button"
                :aria-label="t('stocks.movements.dateFilterAria')"
                @click="openMovementCalendar"
              >
                {{ movementRangeLabel }}
              </button>
            </div>
            <InvestmentCollapseButton
              :collapsed="movementsCollapsed"
              controls="stock-movements-content"
              :label="
                t(
                  movementsCollapsed
                    ? 'stocks.movements.expandAria'
                    : 'stocks.movements.collapseAria',
                )
              "
              @toggle="toggleMovements"
            />
          </div>
        </header>
        <div v-show="!movementsCollapsed" id="stock-movements-content">
          <div class="fund-table-scroll">
            <table class="fund-table movement-table">
              <thead>
                <tr>
                  <th>{{ t("stocks.movements.date") }}</th>
                  <th>{{ t("stocks.movements.movement") }}</th>
                  <th>{{ t("stocks.movements.asset") }}</th>
                  <th>{{ t("stocks.movements.account") }}</th>
                  <th>{{ t("stocks.movements.quantity") }}</th>
                  <th>{{ t("stocks.movements.price") }}</th>
                  <th>{{ t("stocks.movements.amount") }}</th>
                  <th>{{ t("stocks.movements.fee") }}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr v-for="order in displayedOrders" :key="order.id">
                  <td>{{ displayDate(order.trade_date) }}</td>
                  <td>
                    <span class="operation-pill" :class="operationGroup(order)"
                      >{{ operationLabel(order)
                      }}<small v-if="order.is_saveback">{{
                        t("stocks.movements.cashback")
                      }}</small></span
                    >
                  </td>
                  <td>
                    <strong>{{ order.asset_name }}</strong
                    ><small>{{ order.isin }}</small>
                  </td>
                  <td>
                    {{ order.account_name ?? selectedAccountLabel
                    }}<small>{{ order.platform }}</small>
                  </td>
                  <td>{{ quantity(order.quantity) }}</td>
                  <td>
                    {{ money(basePrice(order))
                    }}<small v-if="hasOriginalCurrency(order)">{{
                      t("stocks.movements.originalValue", {
                        value: originalMoney(order.unit_price, order.currency),
                      })
                    }}</small>
                  </td>
                  <td>
                    <strong>{{ money(baseAmount(order)) }}</strong
                    ><small v-if="hasOriginalCurrency(order)">{{
                      t("stocks.movements.originalValue", {
                        value: originalMoney(order.net_amount, order.currency),
                      })
                    }}</small>
                  </td>
                  <td>
                    {{ money(baseFee(order)) }}
                    <small v-if="hasOriginalCurrency(order)">{{
                      t("stocks.movements.originalFee", {
                        value: originalMoney(order.fee, order.currency),
                      })
                    }}</small>
                  </td>
                  <td>
                    <InvestmentMovementActions
                      :edit-label="
                        t('stocks.movements.editAria', {
                          asset: order.asset_name,
                        })
                      "
                      :delete-label="
                        t('stocks.movements.deleteAria', {
                          asset: order.asset_name,
                        })
                      "
                      @edit="openEditMovement(order)"
                      @delete="askDeleteOrder(order)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="!filteredOrders.length" class="fund-empty-compact">
            {{ t("stocks.movements.noResults") }}
          </div>
          <nav
            v-else-if="movementPages > 1"
            class="movement-pagination"
            :aria-label="t('stocks.movements.paginationAria')"
          >
            <span>{{
              t("stocks.movements.page", {
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
                {{ t("stocks.movements.previous") }}</button
              ><button
                type="button"
                :disabled="movementPage === movementPages"
                @click="movementPage++"
              >
                {{ t("stocks.movements.next") }}
              </button>
            </div>
          </nav>
        </div>
      </article>

      <MovementEditorDialog
        ref="movementEditor"
        kind="stock"
        :accounts="accounts"
        :assets="operationAssets"
        :selected-account="selectedAccount"
        @saved="loadDashboard"
      />
      <MovementDeleteDialog
        ref="movementDelete"
        kind="stock"
        @deleted="loadDashboard"
      />
      <AssetEditorDialog
        ref="assetEditor"
        kind="stock"
        :assets="instruments"
        @saved="handleAssetSaved"
      />
      <dialog
        ref="calendarDialog"
        class="stock-dialog"
        aria-labelledby="stocks-performance-calendar-title"
        @cancel.prevent="closeCalendar"
      >
        <form @submit.prevent="applyCustomRange">
          <header>
            <h2 id="stocks-performance-calendar-title">
              {{ t("stocks.calendar.selectDates") }}
            </h2>
          </header>
          <div class="stock-calendar-fields">
            <label
              ><span>{{ t("stocks.calendar.from") }}</span
              ><input
                v-model="draftStart"
                type="date"
                :max="draftEnd"
                required /></label
            ><label
              ><span>{{ t("stocks.calendar.to") }}</span
              ><input v-model="draftEnd" type="date" :min="draftStart" required
            /></label>
          </div>
          <footer>
            <button type="button" @click="closeCalendar">
              {{ t("stocks.calendar.cancel") }}</button
            ><button
              class="primary"
              type="submit"
              :disabled="!customRangeValid"
            >
              {{ t("stocks.calendar.applyPeriod") }}
            </button>
          </footer>
        </form>
      </dialog>
      <dialog
        ref="chartCalendarDialog"
        class="stock-dialog"
        aria-labelledby="stocks-candle-calendar-title"
        @cancel.prevent="closeChartCalendar"
      >
        <form @submit.prevent="applyChartCustomRange">
          <header>
            <h2 id="stocks-candle-calendar-title">
              {{ t("stocks.calendar.selectDates") }}
            </h2>
          </header>
          <div class="stock-calendar-fields">
            <label
              ><span>{{ t("stocks.calendar.from") }}</span
              ><input
                v-model="chartDraftStart"
                type="date"
                :max="chartDraftEnd"
                required /></label
            ><label
              ><span>{{ t("stocks.calendar.to") }}</span
              ><input
                v-model="chartDraftEnd"
                type="date"
                :min="chartDraftStart"
                required
            /></label>
          </div>
          <footer>
            <button type="button" @click="closeChartCalendar">
              {{ t("stocks.calendar.cancel") }}</button
            ><button
              class="primary"
              type="submit"
              :disabled="!chartCustomRangeValid"
            >
              {{ t("stocks.calendar.applyPeriod") }}
            </button>
          </footer>
        </form>
      </dialog>
      <dialog
        ref="movementCalendarDialog"
        class="stock-dialog"
        aria-labelledby="stocks-movement-calendar-title"
      >
        <form @submit.prevent="applyMovementRange">
          <header>
            <h2 id="stocks-movement-calendar-title">
              {{ t("stocks.calendar.selectDates") }}
            </h2>
          </header>
          <div class="stock-calendar-fields">
            <label
              ><span>{{ t("stocks.calendar.from") }}</span
              ><input
                v-model="movementDraftStart"
                type="date"
                :max="movementDraftEnd"
                required /></label
            ><label
              ><span>{{ t("stocks.calendar.to") }}</span
              ><input
                v-model="movementDraftEnd"
                type="date"
                :min="movementDraftStart"
                required
            /></label>
          </div>
          <footer>
            <button type="button" @click="movementCalendarDialog?.close()">
              {{ t("stocks.calendar.cancel") }}</button
            ><button
              class="primary"
              type="submit"
              :disabled="!movementRangeValid"
            >
              {{ t("stocks.calendar.applyFilter") }}
            </button>
          </footer>
        </form>
      </dialog>
      <dialog
        ref="accountDialog"
        class="stock-dialog"
        aria-labelledby="stocks-account-dialog-title"
      >
        <form @submit.prevent="saveAccount">
          <header>
            <h2 id="stocks-account-dialog-title">
              {{
                accountDialogMode === "edit"
                  ? t("stocks.accounts.manageTitle")
                  : t("stocks.accounts.addTitle")
              }}
            </h2>
          </header>
          <div class="stock-calendar-fields account-fields">
            <label
              ><span>{{ t("stocks.accounts.name") }}</span
              ><input v-model="accountName" required /></label
            ><label
              ><span>{{ t("stocks.accounts.platform") }}</span
              ><input v-model="accountProvider" required /></label
            ><label
              ><span>{{ t("stocks.accounts.currency") }}</span
              ><input
                v-model="accountCurrency"
                maxlength="3"
                minlength="3"
                pattern="[A-Za-z]{3}"
                required /></label
            ><label
              ><span>{{ t("stocks.accounts.importer") }}</span
              ><select v-model="accountImporter" required>
                <option value="" disabled>
                  {{ t("stocks.accounts.chooseImporter") }}
                </option>
                <option value="none">
                  {{ t("stocks.accounts.noImporter") }}
                </option>
                <option
                  v-for="item in compatibleImporters"
                  :key="item.slug"
                  :value="item.slug"
                >
                  {{ item.display_name }}
                </option>
              </select></label
            >
          </div>
          <p v-if="accountError" class="dialog-error" role="alert">
            {{ accountError }}
          </p>
          <footer>
            <button
              v-if="accountDialogMode === 'edit'"
              class="danger"
              type="button"
              @click="deleteAccount"
            >
              {{
                accountDeleteArmed
                  ? t("stocks.accounts.confirmDelete")
                  : t("stocks.accounts.delete")
              }}</button
            ><span /><button type="button" @click="closeAccountDialog">
              {{ t("stocks.accounts.cancel") }}</button
            ><button
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
                  ? t("stocks.accounts.saving")
                  : t("stocks.accounts.save")
              }}
            </button>
          </footer>
        </form>
      </dialog>
    </template>
  </section>
</template>

<style scoped>
.stocks-page {
  width: min(100%, 1440px);
  margin: 0 auto;
  padding: 8px 48px 56px;
}
.stocks-loading {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}
.stocks-loading div {
  min-height: 320px;
  border-radius: 22px;
  background: var(--fz-surface-soft);
}
.stock-performance-panel,
.positions-panel,
.movements-panel {
  margin-top: 20px;
  padding: 24px;
  border: 1px solid var(--fz-line);
  border-radius: 22px;
  background: var(--fz-surface);
  box-shadow: var(--fz-shadow);
}
.fund-performance-header,
.fund-secondary-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
}
.fund-performance-header h2,
.fund-secondary-header h2 {
  margin: 0;
  font-size: 20px;
}
.fund-range-label {
  margin: 7px 0 0;
  color: var(--fz-muted);
  font-size: 11px;
}
.stock-performance-controls,
.fund-collapsible-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.fund-mode-control,
.fund-range-control {
  display: flex;
  gap: 3px;
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
  cursor: pointer;
}
.fund-mode-control button.active,
.fund-range-control button.active {
  background: var(--fz-surface);
  color: var(--fz-ink);
}
.stock-performance-meta {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  margin: 21px 0 14px;
  border-top: 1px solid var(--fz-line);
  border-left: 1px solid var(--fz-line);
}
.stock-performance-meta > div {
  padding: 13px;
  border-right: 1px solid var(--fz-line);
  border-bottom: 1px solid var(--fz-line);
}
.stock-performance-meta small,
.stock-performance-meta span {
  display: block;
  color: var(--fz-muted);
  font-size: 10px;
}
.stock-performance-meta strong {
  display: block;
  margin-top: 4px;
  font-size: 15px;
}
.cashback-control {
  margin-bottom: 15px;
  padding: 11px;
  display: flex;
  justify-content: space-between;
  border: 1px solid color-mix(in srgb, var(--fz-accent) 25%, var(--fz-line));
  border-radius: 12px;
  background: color-mix(in srgb, var(--fz-accent) 6%, transparent);
}
.cashback-control span {
  display: grid;
  gap: 3px;
}
.cashback-control strong {
  font-size: 11px;
}
.cashback-control small {
  color: var(--fz-muted);
  font-size: 10px;
}
.cashback-control input {
  accent-color: var(--fz-accent);
}
.stock-secondary-actions {
  display: flex;
  align-items: center;
  gap: 7px;
}
.stock-secondary-actions
  > button:not(.fund-collapse-button):not(.stock-add-asset-button) {
  min-height: 32px;
  padding: 7px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
  cursor: pointer;
}
.fund-positions-content {
  margin-top: 17px;
}
.fund-table-scroll {
  overflow-x: auto;
}
.fund-table {
  width: 100%;
  min-width: 980px;
  margin-top: 18px;
  border-collapse: collapse;
  font-size: 11px;
}
.position-table-scroll .fund-table {
  margin-top: 0;
}
.fund-table th {
  padding: 0 10px 9px;
  color: var(--fz-muted);
  text-align: right;
}
.fund-table th:first-child {
  text-align: left;
}
.fund-table td {
  padding: 11px 10px;
  border-top: 1px solid var(--fz-line);
  text-align: right;
  vertical-align: middle;
  font-variant-numeric: tabular-nums;
}
.fund-table td:first-child {
  text-align: left;
}
.fund-table td small {
  display: block;
  margin-top: 3px;
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-sort-button {
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}
.fund-position-disclosure {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--fz-ink);
  text-align: left;
  cursor: pointer;
}
.fund-position-disclosure-copy {
  display: grid;
  min-width: 0;
}
.fund-position-disclosure-copy strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fund-edit-icon-button {
  border: 1px solid var(--fz-line);
  border-radius: 7px;
  background: transparent;
  color: var(--fz-muted);
  cursor: pointer;
}
.fund-inline-detail-row td {
  padding: 0;
  background: var(--fz-surface-soft);
}
.fund-inline-price-panel {
  padding: 17px;
}
.fund-inline-chart-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 15px;
  margin-bottom: 10px;
}
.fund-chart-legend {
  display: flex;
  gap: 10px;
  color: var(--fz-muted);
  font-size: 10px;
}
.fund-inline-range {
  display: grid;
  justify-items: end;
}
.fund-chart-state,
.fund-empty-compact {
  min-height: 180px;
  display: grid;
  place-content: center;
  gap: 5px;
  text-align: center;
  color: var(--fz-muted);
  font-size: 11px;
}
.fund-chart-state strong {
  color: var(--fz-ink);
}
.movement-filters {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}
.movement-filters select,
.movement-filters button {
  min-height: 34px;
  padding: 7px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  font-size: 11px;
}
.movement-filters .add-movement {
  background: var(--fz-accent);
  color: #fff;
}
.operation-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 7px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--fz-accent) 12%, transparent);
  color: var(--fz-accent);
  white-space: nowrap;
}
.operation-pill.out {
  background: color-mix(in srgb, var(--fz-negative) 12%, transparent);
  color: var(--fz-negative);
}
.operation-pill small {
  display: inline;
  margin-left: 0;
}
.movement-row-actions {
  display: flex;
  justify-content: flex-end;
  gap: 5px;
}
.movement-row-actions button {
  padding: 5px 7px;
  border: 1px solid var(--fz-line);
  border-radius: 7px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 10px;
}
.delete-order {
  color: var(--fz-negative) !important;
}
.movement-pagination {
  display: flex;
  justify-content: space-between;
  margin-top: 15px;
  color: var(--fz-muted);
  font-size: 11px;
}
.movement-pagination button {
  padding: 7px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
}
.stock-dialog {
  width: min(540px, calc(100vw - 32px));
  padding: 0;
  border: 1px solid var(--fz-line);
  border-radius: 20px;
  background: var(--fz-surface);
  color: var(--fz-ink);
}
.stock-dialog form {
  padding: 23px;
}
.stock-dialog header {
  display: flex;
  justify-content: space-between;
}
.stock-dialog h2 {
  margin: 0;
}
.stock-calendar-fields {
  margin-top: 20px;
  padding: 18px;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  background: var(--fz-surface-soft);
  border-radius: 14px;
}
.stock-calendar-fields label {
  display: grid;
  gap: 7px;
}
.stock-calendar-fields span {
  color: var(--fz-muted);
  font-size: 10px;
}
.stock-calendar-fields input,
.stock-calendar-fields select {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface);
  color: var(--fz-ink);
}
.stock-dialog footer {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
}
.stock-dialog footer > span {
  flex: 1;
}
.stock-dialog footer button {
  padding: 9px 13px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: transparent;
  color: var(--fz-muted);
}
.stock-dialog footer .primary {
  background: var(--fz-accent);
  color: #fff;
}
.stock-dialog footer .danger {
  color: var(--fz-negative);
}
.positive {
  color: var(--fz-positive);
}
.negative {
  color: var(--fz-negative);
}
@media (max-width: 1050px) {
  .stocks-page {
    padding-inline: 28px;
  }
  .fund-performance-header,
  .fund-secondary-header {
    align-items: stretch;
    flex-direction: column;
  }
  .stock-performance-meta {
    grid-template-columns: repeat(3, 1fr);
  }
  .fund-inline-chart-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .fund-inline-range {
    justify-items: start;
  }
}
@media (max-width: 720px) {
  .stocks-page {
    padding: 4px 18px 32px;
  }
  .stock-performance-panel,
  .positions-panel,
  .movements-panel {
    padding: 19px 17px;
  }
  .stock-performance-meta {
    grid-template-columns: repeat(2, 1fr);
  }
  .stock-performance-controls,
  .fund-collapsible-actions {
    flex-wrap: wrap;
  }
  .fund-inline-range {
    justify-items: start;
  }
  .movement-filters > * {
    width: 100%;
  }
  .stock-calendar-fields {
    grid-template-columns: 1fr;
  }
  .account-fields {
    grid-template-columns: 1fr;
  }
}
@media (prefers-reduced-motion: reduce) {
  * {
    scroll-behavior: auto !important;
    transition: none !important;
  }
}
</style>
