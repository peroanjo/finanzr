<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { api, json } from "../api/client";
import type { AssetReturnMode } from "../components/AssetReturnToggle.vue";
import FundPerformancePanel, {
  type FundPerformancePanelModel,
  type PerformanceMode,
  type PerformanceRange,
} from "../components/funds/FundPerformancePanel.vue";
import FundMovementsPanel from "../components/funds/FundMovementsPanel.vue";
import FundPositionsPanel from "../components/funds/FundPositionsPanel.vue";
import InvestmentAccountBar from "../components/investments/InvestmentAccountBar.vue";
import type { InvestmentAllocationItem } from "../components/investments/InvestmentAllocationStrip.vue";
import InvestmentOverview from "../components/investments/InvestmentOverview.vue";
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
  FundPosition,
  FundPrice,
  ImporterCatalogItem,
  InvestmentPerformanceResponse,
  PriceFetchResponse,
} from "../types/api";
import { adaptFundChart } from "../domain/investments";
import {
  useFundsPortfolio,
  type FundPositionSortKey,
} from "../composables/useFundsPortfolio";
import {
  instrumentById,
  instrumentCurrency,
  instrumentIdentity,
  instrumentName,
  instrumentTicker,
  primaryIdentifier,
} from "../domain/instruments";

const { t, n, d, locale } = useI18n();

const accounts = ref<FundAccount[]>([]);
const importerCatalog = ref<ImporterCatalogItem[]>([]);
const positions = ref<FundPosition[]>([]);
const orders = ref<FundOrder[]>([]);
const instruments = ref<FundInstrument[]>([]);
const prices = ref<FundPrice[]>([]);
const performance = ref<InvestmentPerformanceResponse | null>(null);
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
const editFundPriceCurrency = ref("EUR");
const fundEditBusy = ref(false);
const fundEditError = ref("");
const fundBaseCurrency = computed(() => reportingCurrency.value);

const {
  openPositions,
  normalizedTopPositions,
  totalInvested,
  totalValue,
  unrealizedPnl,
  openReturn,
  realizedPnl,
  totalPnl,
  selectedFundPosition,
  selectedFundOrders,
  latestPriceByInstrumentId,
  pricedPositions,
  positionSortKey,
  positionSortDirection,
  sortedPositions,
  sortPositions,
  positionAriaSort,
} = useFundsPortfolio({
  positions,
  orders,
  instruments,
  prices,
  selectedFund,
  locale,
});

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
    : (selectedAccountRow.value?.name ?? t("funds.accounts.fallback")),
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
const latestUpdate = computed(() => {
  const dates = prices.value
    .map((item) => item.quoted_at.slice(0, 10))
    .filter(Boolean)
    .sort();
  return dates.length
    ? d(new Date(`${dates.at(-1)}T00:00:00`), "short")
    : t("funds.kpis.neverUpdated");
});
const performancePoints = computed(() => performance.value?.data ?? []);
const firstPerformance = computed(() => performancePoints.value[0] ?? null);
const lastPerformance = computed(() => performancePoints.value.at(-1) ?? null);
const periodPnl = computed(() => {
  if (!firstPerformance.value || !lastPerformance.value) return 0;
  return lastPerformance.value.pnl - firstPerformance.value.pnl;
});
const periodPnlPercent = computed(() =>
  firstPerformance.value?.value
    ? periodPnl.value / firstPerformance.value.value
    : 0,
);
const displayedRange = computed(() => {
  const points = performancePoints.value;
  if (points.length) {
    return `${displayDate(points[0].date)} → ${displayDate(points.at(-1)?.date ?? points[0].date)}`;
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
const performancePanelModel = computed<FundPerformancePanelModel>(() => ({
  accountLabel: selectedAccountLabel.value,
  displayedRange: displayedRange.value,
  range: range.value,
  mode: mode.value,
  ranges: ranges.value,
  points: performancePoints.value,
  lastPerformance: lastPerformance.value,
  totalValue: totalValue.value,
  totalInvested: totalInvested.value,
  realizedPnl: realizedPnl.value,
  periodLabel: periodLabel.value,
  periodPnl: periodPnl.value,
  periodPnlPercent: periodPnlPercent.value,
  loading: performanceLoading.value,
  error: performanceError.value,
  formatters: { money, percentage, signedMoney },
}));
const fundChartPoints = computed(() =>
  fundChart.value ? adaptFundChart(fundChart.value) : [],
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
      const value = item.current_value;
      return isPositiveFinite(value) ? [{ item, value }] : [];
    })
    .sort(
      (left, right) =>
        right.value - left.value ||
        positionIdentity(left.item).localeCompare(positionIdentity(right.item)),
    );
  const total = valuedPositions.reduce((sum, item) => sum + item.value, 0);
  if (!isPositiveFinite(total)) return [];
  const largestPositions = valuedPositions
    .slice(0, 5)
    .map(({ item, value }, index) => ({
      key: item.instrument_id,
      label: item.name,
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
    return `${displayDate(points[0].date)} → ${displayDate(points.at(-1)?.date ?? points[0].date)}`;
  }
  if (fundRange.value === "custom") {
    return `${displayDate(fundCustomStart.value)} → ${displayDate(fundCustomEnd.value)}`;
  }
  return (
    ranges.value.find((item) => item.key === fundRange.value)?.label ??
    t("funds.ranges.period")
  );
});
const positionSortColumns = computed<
  Array<{ key: FundPositionSortKey; label: string }>
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
const movementAssets = computed(() =>
  instruments.value.map((item) => ({
    id: instrumentIdentity(item),
    label: instrumentName(item) + " · " + instrumentIdentity(item),
    currency: instrumentCurrency(item),
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

function accountQuery() {
  return selectedAccount.value === "all"
    ? ""
    : `?account_id=${encodeURIComponent(selectedAccount.value)}`;
}

function performanceQuery() {
  const account = `account_id=${encodeURIComponent(selectedAccount.value)}`;
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
    const available = positions.value.map((item) => item.instrument_id);
    if (selectedFund.value && !available.includes(selectedFund.value))
      closeFundDetail();
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
    const nextPerformance = await api<InvestmentPerformanceResponse>(
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
  const instrumentId = selectedFund.value;
  if (!instrumentId) {
    fundChart.value = null;
    fundChartLoading.value = false;
    fundChartError.value = t("funds.errors.chart");
    return;
  }
  fundChart.value = null;
  fundChartLoading.value = true;
  fundChartError.value = "";
  try {
    const nextFundChart = await api<FundChartResponse>(
      `/fund-chart/${encodeURIComponent(instrumentId)}?${fundChartQuery()}`,
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

async function selectFund(instrumentId: string) {
  selectedFund.value = instrumentId;
  await loadFundChart();
}

function closeFundDetail() {
  selectedFund.value = "";
  fundChartRequestGeneration += 1;
  fundChart.value = null;
  fundChartLoading.value = false;
  fundChartError.value = "";
}

async function toggleFund(instrumentId: string) {
  if (selectedFund.value === instrumentId) {
    closeFundDetail();
    return;
  }
  await selectFund(instrumentId);
}

function fundDetailId(instrumentId: string) {
  const safeIsin =
    Array.from(instrumentId)
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
  accountName.value = account.name;
  accountProvider.value = account.platform;
  accountType.value = account.type;
  accountImporter.value = account.importer_slug || "none";
  accountCurrency.value = account.currency || "EUR";
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
        name,
        platform: provider,
        type: accountType.value.trim(),
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
    const response = await api<PriceFetchResponse>("/fund-prices/fetch", {
      method: "POST",
    });
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
  editingFund.value =
    instrumentById(instruments.value, position.instrument_id) ?? null;
  if (!editingFund.value) return;
  editFundName.value = editingFund.value.name;
  editFundType.value = editingFund.value.asset_class ?? "";
  editFundSubtype.value = editingFund.value.subtype ?? "";
  editFundTicker.value = instrumentTicker(editingFund.value);
  const nativePrice = latestPriceByInstrumentId.value.get(editingFund.value.id);
  editFundPrice.value = nativePrice == null ? "" : String(nativePrice.close);
  editFundPriceCurrency.value =
    nativePrice?.currency ?? editingFund.value.quote_currency;
  fundEditError.value = "";
  fundEditDialog.value?.showModal();
}

function positionIdentity(position: FundPosition) {
  return instrumentIdentity(
    instrumentById(instruments.value, position.instrument_id),
  );
}

async function saveFundEditor() {
  if (!editingFund.value || !editFundName.value.trim()) return;
  fundEditBusy.value = true;
  fundEditError.value = "";
  try {
    const identifiers = (editingFund.value.identifiers ?? []).map((item) => ({
      ...item,
    }));
    const yahooIdentifier = primaryIdentifier(editingFund.value, "yahoo");
    const tickerIndex = yahooIdentifier
      ? identifiers.findIndex(
          (item) =>
            item.scheme === "yahoo" &&
            item.value === yahooIdentifier.value &&
            item.venue === yahooIdentifier.venue &&
            item.is_primary === yahooIdentifier.is_primary,
        )
      : -1;
    const tickerRow = yahooIdentifier
      ? {
          ...yahooIdentifier,
          value: editFundTicker.value.trim(),
        }
      : {
          scheme: "yahoo" as const,
          value: editFundTicker.value.trim(),
          venue: "",
          is_primary: true,
        };
    if (tickerIndex >= 0) identifiers[tickerIndex] = tickerRow;
    else identifiers.push(tickerRow);
    await api(
      "/funds/" + editingFund.value.id,
      json("PUT", {
        name: editFundName.value.trim(),
        quote_currency: editingFund.value.quote_currency,
        identifiers,
        asset_class: editFundType.value.trim() || null,
        subtype: editFundSubtype.value.trim() || null,
      }),
    );
    if (editFundPrice.value !== "") {
      await api(
        "/fund-prices/" + editingFund.value.id,
        json("PUT", {
          close: Number(editFundPrice.value),
          currency: editFundPriceCurrency.value,
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

function positionSortAria(key: FundPositionSortKey, label: string) {
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
        :accounts="accounts"
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

      <FundPerformancePanel
        :model="performancePanelModel"
        @update:mode="mode = $event"
        @select-range="selectRange"
        @retry="loadPerformance()"
      />

      <FundPositionsPanel
        :positions="positions"
        :priced-positions="pricedPositions"
        :price-message="priceMessage"
        :selected-account-label="selectedAccountLabel"
        :allocation-items="marketValueAllocationItems"
        :allocation-total="marketValueAllocationTotal"
        :sorted-positions="sortedPositions"
        :position-sort-columns="positionSortColumns"
        :position-sort-key="positionSortKey"
        :position-sort-direction="positionSortDirection"
        :selected-fund="selectedFund"
        :selected-fund-position="selectedFundPosition"
        :selected-fund-orders="selectedFundOrders"
        :fund-chart-points="fundChartPoints"
        :fund-chart-loading="fundChartLoading"
        :fund-chart-error="fundChartError"
        :fund-chart-range-label="fundChartRangeLabel"
        :ranges="ranges"
        :fund-range="fundRange"
        :format-money="money"
        :format-percentage="percentage"
        :format-quantity="quantity"
        :format-signed-money="signedMoney"
        :position-identity="positionIdentity"
        :market-value-segment-aria="marketValueSegmentAria"
        :position-aria-sort="positionAriaSort"
        :position-sort-aria="positionSortAria"
        :fund-detail-id="fundDetailId"
        @toggle-fund="toggleFund"
        @select-range="selectFundRange"
        @retry-chart="loadFundChart()"
        @edit-fund="openFundEditor"
        @sort="sortPositions"
      />
    </template>
    <FundMovementsPanel
      v-show="!loading && !error"
      :orders="orders"
      :positions="positions"
      :selected-account-label="selectedAccountLabel"
      :account-key="selectedAccount"
      :format-money="money"
      :format-quantity="quantity"
      :display-date="displayDate"
      :position-identity="positionIdentity"
      @add="openNewMovement"
      @edit="openEditMovement"
      @delete="askDeleteOrder"
    />
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

    <template v-if="!loading && !error">
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
                  currency:
                    editFundPriceCurrency ||
                    editingFund?.quote_currency ||
                    "EUR",
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
.fund-account-fields em {
  font-size: 10px;
}
.fund-account-actions select,
.fund-account-actions button,
.fund-account-actions summary,
:deep(.import-compact select),
:deep(.import-compact input),
:deep(.import-compact button),
.fund-asset-head,
.fund-action-button,
.fund-live,
.fund-calendar-fields label span,
.fund-account-fields label span,
.fund-dialog-error {
  font-size: 11px;
}
.fund-panel-header h2 {
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
.fund-calendar-fields input,
.fund-account-fields input,
.fund-account-fields select,
.fund-dialog footer button {
  font-size: 12px;
}
</style>
