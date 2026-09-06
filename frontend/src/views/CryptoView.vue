<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { api, json } from "../api/client";
import AssetEditorDialog from "../components/AssetEditorDialog.vue";
import type { AssetReturnMode } from "../components/AssetReturnToggle.vue";
import CryptoPositionsPanel, {
  type CryptoPerformanceRange,
} from "../components/crypto/CryptoPositionsPanel.vue";
import CryptoMovementsPanel from "../components/crypto/CryptoMovementsPanel.vue";
import FundPerformanceChart from "../components/FundPerformanceChart.vue";
import InvestmentAccountBar from "../components/investments/InvestmentAccountBar.vue";
import type { InvestmentAllocationItem } from "../components/investments/InvestmentAllocationStrip.vue";
import InvestmentOverview from "../components/investments/InvestmentOverview.vue";
import type {
  InvestmentAccountBarLabels,
  InvestmentImportConfig,
} from "../components/investments/InvestmentAccountBar.vue";
import type { InvestmentOverviewLabels } from "../components/investments/InvestmentOverview.vue";
import MovementDeleteDialog from "../components/MovementDeleteDialog.vue";
import MovementEditorDialog from "../components/MovementEditorDialog.vue";
import {
  useCryptoPortfolio,
  type CryptoPositionSortKey as PositionSortKey,
} from "../composables/useCryptoPortfolio";
import type {
  MovementDeleteHandle,
  MovementEditorHandle,
} from "../components/movementEditor";
import type {
  AssetEditorHandle,
  EditableAsset,
} from "../components/assetEditor";
import { adaptCryptoChart } from "../domain/investments";
import { reportingCurrency } from "../i18n";
import type {
  CryptoChartResponse,
  CryptoAccount,
  CryptoInstrument,
  CryptoOrder,
  CryptoPosition,
  CryptoPrice,
  InvestmentPerformanceResponse,
  PriceFetchResponse,
  ImporterCatalogItem,
} from "../types/api";
import {
  instrumentById,
  instrumentCurrency,
  instrumentIdentity,
  instrumentName,
  instrumentTicker,
} from "../domain/instruments";

type PerformanceRange = CryptoPerformanceRange;
type CryptoPerformanceMode = "value" | "return";

const CRYPTO_PREFERENCES_STORAGE_KEY = "finanzr:crypto:preferences:v1";

function dateInput(date: Date) {
  return date.toISOString().slice(0, 10);
}

function isIsoDate(value: unknown): value is string {
  const match =
    typeof value === "string" ? /^(\d{4})-(\d{2})-(\d{2})$/.exec(value) : null;
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (year < 1 || year > 9999) return false;
  const candidate = new Date(0);
  candidate.setUTCHours(0, 0, 0, 0);
  candidate.setUTCFullYear(year, month - 1, day);
  return (
    candidate.getUTCFullYear() === year &&
    candidate.getUTCMonth() === month - 1 &&
    candidate.getUTCDate() === day
  );
}

function readStorageItem(key: string) {
  try {
    return globalThis.localStorage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function writeStorageItem(key: string, value: string) {
  try {
    globalThis.localStorage?.setItem(key, value);
  } catch {
    // Storage can be unavailable or read-only in privacy mode.
  }
}

function defaultCryptoCustomRange() {
  const end = new Date();
  const start = new Date(end);
  start.setFullYear(start.getFullYear() - 1);
  return { start: dateInput(start), end: dateInput(end) };
}

function readCryptoPreferences() {
  const fallback = defaultCryptoCustomRange();
  let stored: Record<string, unknown> = {};
  const raw = readStorageItem(CRYPTO_PREFERENCES_STORAGE_KEY);
  if (raw) {
    try {
      const parsed: unknown = JSON.parse(raw);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed))
        stored = parsed as Record<string, unknown>;
    } catch {
      // Corrupt preferences are discarded in favor of safe defaults.
    }
  }
  const storedRange = stored.range;
  const requestedRange: PerformanceRange =
    storedRange === "6m" ||
    storedRange === "1y" ||
    storedRange === "2y" ||
    storedRange === "custom"
      ? storedRange
      : "1y";
  const storedMode = stored.mode;
  const mode: CryptoPerformanceMode =
    storedMode === "return" ? "return" : "value";
  const storedStart = isIsoDate(stored.customStart) ? stored.customStart : null;
  const storedEnd = isIsoDate(stored.customEnd) ? stored.customEnd : null;
  const customRangeValid = Boolean(
    storedStart && storedEnd && storedStart <= storedEnd,
  );
  return {
    range:
      requestedRange === "custom" && !customRangeValid ? "1y" : requestedRange,
    mode,
    customStart: customRangeValid ? storedStart! : fallback.start,
    customEnd: customRangeValid ? storedEnd! : fallback.end,
  };
}

function persistCryptoPreferences(preferences: {
  range?: PerformanceRange;
  mode?: CryptoPerformanceMode;
  customStart?: string;
  customEnd?: string;
}) {
  const current = readCryptoPreferences();
  writeStorageItem(
    CRYPTO_PREFERENCES_STORAGE_KEY,
    JSON.stringify({
      range: preferences.range ?? current.range,
      mode: preferences.mode ?? current.mode,
      customStart: preferences.customStart ?? current.customStart,
      customEnd: preferences.customEnd ?? current.customEnd,
    }),
  );
}

const cryptoPreferences = readCryptoPreferences();

const { t, n, d, locale } = useI18n();

const positions = ref<CryptoPosition[]>([]);
const orders = ref<CryptoOrder[]>([]);
const instruments = ref<CryptoInstrument[]>([]);
const prices = ref<CryptoPrice[]>([]);
const accounts = ref<CryptoAccount[]>([]);
const importerCatalog = ref<ImporterCatalogItem[]>([]);
const performance = ref<InvestmentPerformanceResponse | null>(null);
const chart = ref<CryptoChartResponse | null>(null);
const selectedAccount = ref(
  new URLSearchParams(window.location.search).get("account") ?? "all",
);
const selectedInstrumentId = ref("");
const range = ref<PerformanceRange>(cryptoPreferences.range);
const chartRange = ref<PerformanceRange>("1y");
const mode = ref<CryptoPerformanceMode>(cryptoPreferences.mode);
const loading = ref(true);
const performanceLoading = ref(false);
const chartLoading = ref(false);
const refreshingPrices = ref(false);
const error = ref("");
const performanceError = ref("");
const chartError = ref("");
const priceMessage = ref("");
const calendarDialog = ref<HTMLDialogElement>();
const accountDialog = ref<HTMLDialogElement>();
const assetEditor = ref<AssetEditorHandle>();
const movementEditor = ref<MovementEditorHandle>();
const movementDelete = ref<MovementDeleteHandle>();
const movementPanel = ref<{
  resetForAccount: (resetType?: boolean) => void;
  resetPage: () => void;
  initializeMovementRange: () => void;
}>();
const accountDialogMode = ref<"create" | "edit">("create");
const accountName = ref("");
const accountProvider = ref("");
const accountImporter = ref("");
const accountCurrency = ref("EUR");
const assetReturnMode = ref<AssetReturnMode>("percent");
const accountBusy = ref(false);
const accountError = ref("");
const accountDeleteArmed = ref(false);
const chartCalendarDialog = ref<HTMLDialogElement>();
let dashboardGeneration = 0;
let performanceRequestGeneration = 0;
let chartRequestGeneration = 0;
let assetSaveGeneration = 0;

const customStart = ref(cryptoPreferences.customStart);
const customEnd = ref(cryptoPreferences.customEnd);
const draftStart = ref(customStart.value);
const draftEnd = ref(customEnd.value);
const chartCustomStart = ref(customStart.value);
const chartCustomEnd = ref(customEnd.value);
const chartDraftStart = ref(chartCustomStart.value);
const chartDraftEnd = ref(chartCustomEnd.value);

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
} = useCryptoPortfolio({
  positions,
  orders,
  instruments,
  selectedInstrumentId,
  locale,
});

const ranges = computed<Array<{ key: PerformanceRange; label: string }>>(() => [
  { key: "6m", label: t("crypto.ranges.sixMonths") },
  { key: "1y", label: t("crypto.ranges.oneYear") },
  { key: "2y", label: t("crypto.ranges.twoYears") },
  { key: "custom", label: t("crypto.ranges.calendar") },
]);
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
const performancePoints = computed(() => performance.value?.data ?? []);
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
    ? t("crypto.performance.periodPnl")
    : t("crypto.performance.rangePnl", {
        range:
          ranges.value.find((item) => item.key === range.value)?.label ?? "",
      }),
);
const latestUpdate = computed(() => {
  const dates = prices.value
    .map((item) => item.quoted_at.slice(0, 10))
    .filter(Boolean)
    .sort();
  return dates.length
    ? d(new Date(`${dates.at(-1)}T00:00:00`), "short")
    : t("crypto.kpis.neverUpdated");
});
const selectedAccountLabel = computed(() =>
  selectedAccount.value === "all"
    ? t("crypto.accounts.all")
    : (accounts.value.find((item) => String(item.id) === selectedAccount.value)
        ?.name ?? t("crypto.accounts.fallback")),
);
const selectedAccountRow = computed(
  () =>
    accounts.value.find((item) => String(item.id) === selectedAccount.value) ??
    null,
);
const compatibleImporters = computed(() =>
  importerCatalog.value.filter((item) => item.target === "crypto_orders"),
);
const selectedImporter = computed(
  () =>
    compatibleImporters.value.find(
      (item) => item.slug === selectedAccountRow.value?.importer_slug,
    ) ?? null,
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
    t("crypto.ranges.period")
  );
});
const chartRangeLabel = computed(() => {
  const points = chart.value?.data ?? [];
  if (points.length)
    return `${displayDate(points[0].date)} → ${displayDate(points.at(-1)?.date ?? points[0].date)}`;
  if (chartRange.value === "custom")
    return `${displayDate(chartCustomStart.value)} → ${displayDate(chartCustomEnd.value)}`;
  return (
    ranges.value.find((item) => item.key === chartRange.value)?.label ??
    t("crypto.ranges.period")
  );
});
const chartPoints = computed(() =>
  chart.value ? adaptCryptoChart(chart.value) : [],
);
const allocationItems = computed<InvestmentAllocationItem[]>(() => {
  const valued = openPositions.value.flatMap((position) =>
    typeof position.current_value === "number" && position.current_value > 0
      ? [{ position, value: position.current_value }]
      : [],
  );
  const total = valued.reduce((sum, item) => sum + item.value, 0);
  if (!(total > 0)) return [];
  const colors = ["#7967f2", "#55cbef", "#f7931a", "#b18cff", "#56d6a0"];
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
          label: t("crypto.positions.other"),
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
const positionSortColumns = computed(() => [
  { key: "asset" as PositionSortKey, label: t("crypto.positions.asset") },
  { key: "ticker" as PositionSortKey, label: t("crypto.positions.symbol") },
  { key: "cost" as PositionSortKey, label: t("crypto.positions.contributed") },
  { key: "quantity" as PositionSortKey, label: t("crypto.positions.quantity") },
  {
    key: "averagePrice" as PositionSortKey,
    label: t("crypto.positions.averagePrice"),
  },
  {
    key: "currentPrice" as PositionSortKey,
    label: t("crypto.positions.currentPrice"),
  },
  { key: "value" as PositionSortKey, label: t("crypto.positions.value") },
  { key: "pnl" as PositionSortKey, label: t("crypto.positions.pnl") },
  { key: "return" as PositionSortKey, label: t("crypto.positions.return") },
]);
const movementAssets = computed(() =>
  instruments.value.map((item) => ({
    id: instrumentIdentity(item),
    label: instrumentIdentity(item) + " · " + instrumentName(item),
    currency: instrumentCurrency(item),
  })),
);
const accountBarLabels = computed<InvestmentAccountBarLabels>(() => ({
  portfolioView: t("crypto.accounts.portfolioView"),
  accountAria: t("crypto.accounts.aria"),
  allAccounts: t("crypto.accounts.all"),
  importStatement: t("crypto.accounts.importStatement"),
  manage: t("crypto.accounts.manage"),
  add: t("crypto.accounts.add"),
}));
const overviewLabels = computed<InvestmentOverviewLabels>(() => ({
  assets: {
    section: t("crypto.assets.section"),
    title: t("crypto.assets.title"),
    asset: t("crypto.assets.asset"),
    portfolioValue: t("crypto.assets.portfolioValue"),
    contributed: t("crypto.assets.contributed"),
    currentPrice: t("crypto.assets.currentPrice"),
    averagePrice: t("crypto.assets.averagePrice"),
    value: t("crypto.assets.value"),
    return: t("crypto.assets.return"),
    pnl: t("crypto.positions.pnl"),
    pending: t("crypto.positions.pending"),
    emptyTitle: t("crypto.assets.noOpenPositions"),
    emptyDescription: t("crypto.assets.noOpenPositionsHint"),
  },
  kpis: {
    section: t("crypto.kpis.section"),
    title: t("crypto.kpis.title"),
    portfolioValue: t("crypto.kpis.portfolioValue"),
    openAsset: t("crypto.kpis.openAsset"),
    openAssets: t("crypto.kpis.openAssets"),
    unrealizedPnl: t("crypto.kpis.unrealizedPnl"),
    versusCost: t("crypto.kpis.versusCost"),
    realizedPnl: t("crypto.kpis.realizedPnl"),
    recordedSales: t("crypto.kpis.recordedSales"),
    totalPnl: t("crypto.kpis.totalPnl"),
    realizedAndOpen: t("crypto.kpis.realizedPlusOpen"),
    marketData: t("crypto.kpis.marketData"),
    updating: t("crypto.kpis.updating"),
    update: t("crypto.kpis.update"),
  },
}));
const importConfig = computed<InvestmentImportConfig | null>(() =>
  selectedImporter.value
    ? {
        endpoint: `/account-imports/crypto/${selectedAccount.value}`,
        accountsEndpoint: "/crypto-accounts",
        accountId: selectedAccount.value,
        accountLabel: selectedAccountLabel.value,
        importerLabel: selectedImporter.value.display_name,
        compatibility: importerDescription(selectedImporter.value),
        accept: selectedImporter.value.accepted_extensions.join(","),
        fileHint: selectedImporter.value.formats
          .map((item) => item.label)
          .join(" · "),
      }
    : null,
);

function displayDate(value: string) {
  void locale.value;
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

function signedMoney(value: number) {
  return `${value >= 0 ? "+" : "−"}${money(Math.abs(value))}`;
}

function accountQuery() {
  return selectedAccount.value === "all"
    ? ""
    : `?account_id=${encodeURIComponent(selectedAccount.value)}`;
}

function performanceQuery() {
  const params = new URLSearchParams({ account_id: selectedAccount.value });
  if (range.value === "custom") {
    params.set("start", customStart.value);
    params.set("end", customEnd.value);
  } else params.set("range", range.value);
  return params.toString();
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
      api<CryptoAccount[]>("/crypto-accounts"),
      api<ImporterCatalogItem[]>("/importers"),
    ]);
    if (generation !== dashboardGeneration) return;
    accounts.value = nextAccounts;
    importerCatalog.value = nextImporters;
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
        api<CryptoPosition[]>(`/crypto-analysis${query}`),
        api<CryptoOrder[]>(`/crypto-orders${query}`),
        api<CryptoInstrument[]>("/cryptos"),
        api<CryptoPrice[]>("/crypto-prices"),
      ]);
    if (generation !== dashboardGeneration) return;
    positions.value = nextPositions;
    orders.value = nextOrders;
    instruments.value = nextInstruments;
    prices.value = nextPrices;
    movementPanel.value?.initializeMovementRange();
    const available = openPositions.value.map(
      (position) => position.instrument_id,
    );
    if (!available.includes(selectedInstrumentId.value))
      selectedInstrumentId.value = "";
  } catch (reason) {
    if (generation !== dashboardGeneration) return;
    error.value =
      reason instanceof Error ? reason.message : t("crypto.errors.load");
  } finally {
    if (showLoading && generation === dashboardGeneration)
      loading.value = false;
  }
  if (generation === dashboardGeneration && !error.value) {
    await loadPerformance(generation);
    if (loadSelectedChart && selectedInstrumentId.value)
      await loadChart(generation);
  }
}

async function loadPerformance(generation = dashboardGeneration) {
  if (generation !== dashboardGeneration) return;
  const request = ++performanceRequestGeneration;
  performanceLoading.value = true;
  performanceError.value = "";
  try {
    const result = await api<InvestmentPerformanceResponse>(
      `/investment-performance/crypto?${performanceQuery()}`,
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
      reason instanceof Error ? reason.message : t("crypto.errors.performance");
  } finally {
    if (
      generation === dashboardGeneration &&
      request === performanceRequestGeneration
    )
      performanceLoading.value = false;
  }
}

function syncAccountUrl() {
  const url = new URL(window.location.href);
  if (selectedAccount.value === "all") url.searchParams.delete("account");
  else url.searchParams.set("account", selectedAccount.value);
  window.history.replaceState(window.history.state, "", url);
}

async function changeAccount(account: string) {
  selectedAccount.value = account;
  movementPanel.value?.resetForAccount(true);
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
  const account = accounts.value.find(
    (item) => String(item.id) === selectedAccount.value,
  );
  if (!account) return;
  accountDialogMode.value = "edit";
  accountName.value = account.name;
  accountProvider.value = account.platform;
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
        ? `/crypto-accounts/${selectedAccount.value}`
        : "/crypto-accounts";
    const saved = await api<CryptoAccount>(
      target,
      json(accountDialogMode.value === "edit" ? "PUT" : "POST", {
        name,
        platform: provider,
        importer_slug: accountImporter.value,
        currency: accountCurrency.value.trim().toUpperCase(),
      }),
    );
    selectedAccount.value = String(saved.id);
    movementPanel.value?.resetForAccount(false);
    syncAccountUrl();
    accountDialog.value?.close();
    await loadDashboard();
  } catch (reason) {
    accountError.value =
      reason instanceof Error ? reason.message : t("crypto.errors.saveAccount");
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
    await api(`/crypto-accounts/${selectedAccount.value}`, {
      method: "DELETE",
    });
    selectedAccount.value = "all";
    movementPanel.value?.resetForAccount(false);
    syncAccountUrl();
    accountDialog.value?.close();
    await loadDashboard();
  } catch (reason) {
    accountError.value =
      reason instanceof Error
        ? reason.message
        : t("crypto.errors.deleteAccount");
  } finally {
    accountBusy.value = false;
  }
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

async function loadChart(generation = dashboardGeneration) {
  if (generation !== dashboardGeneration || !selectedInstrumentId.value) return;
  const request = ++chartRequestGeneration;
  const instrumentId = selectedInstrumentId.value;
  if (!instrumentId) {
    chart.value = null;
    chartLoading.value = false;
    chartError.value = t("crypto.errors.chart");
    return;
  }
  chartLoading.value = true;
  chartError.value = "";
  try {
    const result = await api<CryptoChartResponse>(
      `/crypto-chart/${encodeURIComponent(instrumentId)}?${chartQuery()}`,
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
      reason instanceof Error ? reason.message : t("crypto.errors.chart");
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

async function selectRange(value: PerformanceRange) {
  if (value === "custom") {
    draftStart.value = customStart.value;
    draftEnd.value = customEnd.value;
    calendarDialog.value?.showModal();
    return;
  }
  range.value = value;
  persistCryptoPreferences({ range: value });
  await loadPerformance();
}

function selectPerformanceMode(value: CryptoPerformanceMode) {
  mode.value = value;
  persistCryptoPreferences({ mode: value });
}

function closeCalendar() {
  calendarDialog.value?.close();
}

async function applyCustomRange() {
  if (!customRangeValid.value) return;
  customStart.value = draftStart.value;
  customEnd.value = draftEnd.value;
  range.value = "custom";
  persistCryptoPreferences({
    range: "custom",
    customStart: customStart.value,
    customEnd: customEnd.value,
  });
  closeCalendar();
  await loadPerformance();
}

async function selectChartRange(value: PerformanceRange) {
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

function assetTicker(position: CryptoPosition) {
  const instrument = instrumentById(instruments.value, position.instrument_id);
  return instrumentTicker(instrument) || instrumentIdentity(instrument);
}

function positionIdentity(position: CryptoPosition) {
  return instrumentIdentity(
    instrumentById(instruments.value, position.instrument_id),
  );
}

function segmentAria(item: InvestmentAllocationItem) {
  return t("crypto.positions.marketValueSegmentAria", {
    asset: item.label,
    share: percentage(item.share),
  });
}

function detailId(symbol: string) {
  const safe =
    Array.from(symbol)
      .map((character) =>
        /[a-z0-9_-]/i.test(character)
          ? character.toLowerCase()
          : `x${character.codePointAt(0)?.toString(16) ?? "0"}x`,
      )
      .join("") || "crypto";
  return `crypto-price-detail-${safe}`;
}

function sortAria(key: PositionSortKey, label: string) {
  return t(
    positionSortKey.value === key && positionSortDirection.value === "asc"
      ? "crypto.positions.sortDescendingAria"
      : "crypto.positions.sortAscendingAria",
    { column: label },
  );
}

function openNewMovement() {
  movementEditor.value?.openCreate();
}

function openEditMovement(order: CryptoOrder) {
  movementEditor.value?.openEdit(order);
}

function askDeleteMovement(order: CryptoOrder) {
  movementDelete.value?.open(order);
}

function importerDescription(importer: ImporterCatalogItem) {
  return importer.slug === "kraken_spot"
    ? t("crypto.importers.krakenSpotDescription")
    : importer.description;
}

async function refreshPrices() {
  refreshingPrices.value = true;
  priceMessage.value = "";
  try {
    const result = await api<PriceFetchResponse>("/crypto-prices/fetch", {
      method: "POST",
    });
    const failures = result.results.filter((item) => item.error).length;
    priceMessage.value = failures
      ? t(
          failures === 1
            ? "crypto.prices.failedOne"
            : "crypto.prices.failedMany",
          {
            count: failures,
          },
        )
      : t("crypto.prices.updated");
    await loadDashboard();
  } catch (reason) {
    priceMessage.value =
      reason instanceof Error
        ? reason.message
        : t("crypto.errors.refreshPrices");
  } finally {
    refreshingPrices.value = false;
  }
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

onMounted(loadDashboard);
</script>

<template>
  <section class="crypto-page" aria-live="polite">
    <div
      v-if="loading"
      class="crypto-loading"
      :aria-label="t('crypto.loadingAria')"
    >
      <div />
      <div />
      <div />
    </div>

    <div v-else-if="error" class="overview-error" role="alert">
      <span aria-hidden="true">!</span>
      <div>
        <strong>{{ t("crypto.errors.loadTitle") }}</strong>
        <p>{{ error }}</p>
      </div>
      <button type="button" @click="loadDashboard()">
        {{ t("crypto.actions.retry") }}
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
        :currency-label="reportingCurrency"
        :asset-return-mode="assetReturnMode"
        :labels="overviewLabels"
        :format-money="money"
        :format-percentage="percentage"
        :format-signed-money="signedMoney"
        @update:asset-return-mode="assetReturnMode = $event"
        @refresh="refreshPrices"
      />

      <article class="fund-performance-panel crypto-performance-panel">
        <header class="fund-performance-header">
          <div>
            <p class="section-label">{{ t("crypto.performance.section") }}</p>
            <h2>{{ t("crypto.performance.title") }}</h2>
            <p class="fund-range-label">
              {{ selectedAccountLabel }} · {{ displayedRange }}
            </p>
          </div>
          <div class="stock-performance-controls">
            <div
              class="fund-mode-control"
              :aria-label="t('crypto.performance.chartModeAria')"
            >
              <button
                type="button"
                :class="{ active: mode === 'value' }"
                :aria-pressed="mode === 'value'"
                @click="selectPerformanceMode('value')"
              >
                {{ t("crypto.performance.portfolioValue") }}
              </button>
              <button
                type="button"
                :class="{ active: mode === 'return' }"
                :aria-pressed="mode === 'return'"
                @click="selectPerformanceMode('return')"
              >
                {{ t("crypto.performance.returnPercent") }}
              </button>
            </div>
            <div
              class="fund-range-control"
              :aria-label="t('crypto.performance.rangeAria')"
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
            <small>{{ t("crypto.performance.closingValue") }}</small
            ><strong>{{ money(lastPerformance?.value ?? totalValue) }}</strong>
          </div>
          <div>
            <small>{{ t("crypto.performance.contributedCapital") }}</small
            ><strong>{{
              money(lastPerformance?.invested ?? totalCost)
            }}</strong>
          </div>
          <div>
            <small>{{ t("crypto.performance.totalPnl") }}</small
            ><strong
              :class="{
                positive: (lastPerformance?.pnl ?? 0) >= 0,
                negative: (lastPerformance?.pnl ?? 0) < 0,
              }"
              >{{ signedMoney(lastPerformance?.pnl ?? 0) }}</strong
            ><span>{{
              percentage((lastPerformance?.pnl_percent ?? 0) / 100)
            }}</span>
          </div>
          <div>
            <small>{{ t("crypto.performance.realizedPnl") }}</small
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
        <div v-if="performanceLoading" class="fund-chart-state">
          {{ t("crypto.performance.calculating") }}
        </div>
        <div v-else-if="performanceError" class="fund-chart-state error-state">
          <strong>{{ t("crypto.performance.unavailable") }}</strong>
          <p>{{ performanceError }}</p>
          <button type="button" @click="loadPerformance()">
            {{ t("crypto.actions.retry") }}
          </button>
        </div>
        <FundPerformanceChart
          v-else-if="performancePoints.length >= 2"
          :points="performancePoints"
          :mode="mode"
        />
        <div v-else class="fund-chart-state">
          <strong>{{ t("crypto.performance.insufficientHistory") }}</strong>
          <p>{{ t("crypto.performance.insufficientHistoryHint") }}</p>
        </div>
      </article>

      <CryptoPositionsPanel
        :positions="positions"
        :priced-positions="pricedPositions"
        :selected-account-label="selectedAccountLabel"
        :base-currency="reportingCurrency"
        :allocation-items="allocationItems"
        :allocation-total="allocationTotal"
        :sorted-positions="sortedPositions"
        :position-sort-columns="positionSortColumns"
        :position-sort-key="positionSortKey"
        :position-sort-direction="positionSortDirection"
        :selected-instrument-id="selectedInstrumentId"
        :selected-chart-orders="selectedChartOrders"
        :average-price="averagePrice"
        :chart-points="chartPoints"
        :chart-loading="chartLoading"
        :chart-error="chartError"
        :chart-range-label="chartRangeLabel"
        :ranges="ranges"
        :chart-range="chartRange"
        :format-money="money"
        :format-percentage="percentage"
        :format-quantity="(value) => n(value, 'quantity')"
        :format-signed-money="signedMoney"
        :position-identity="positionIdentity"
        :asset-ticker="assetTicker"
        :market-value-segment-aria="segmentAria"
        :position-aria-sort="ariaSort"
        :position-sort-aria="sortAria"
        :detail-id="detailId"
        @toggle-position="togglePosition"
        @select-chart-range="selectChartRange"
        @retry-chart="loadChart"
        @edit-position="
          (position) =>
            assetEditor?.openEdit(
              instrumentById(instruments, position.instrument_id),
            )
        "
        @add-asset="assetEditor?.openCreate()"
        @sort="sortPositions"
      />

      <MovementEditorDialog
        ref="movementEditor"
        kind="crypto"
        :accounts="accounts"
        :assets="movementAssets"
        :selected-account="selectedAccount"
        @saved="loadDashboard"
      />
      <AssetEditorDialog
        ref="assetEditor"
        kind="crypto"
        :assets="instruments"
        @saved="handleAssetSaved"
      />
      <MovementDeleteDialog
        ref="movementDelete"
        kind="crypto"
        @deleted="loadDashboard"
      />

      <dialog
        ref="calendarDialog"
        class="calendar-dialog"
        aria-labelledby="calendar-dialog-title"
      >
        <form @submit.prevent="applyCustomRange">
          <header>
            <div>
              <p class="section-label">
                {{ t("crypto.calendar.customPeriod") }}
              </p>
              <h2 id="calendar-dialog-title">
                {{ t("crypto.calendar.selectDates") }}
              </h2>
            </div>
          </header>
          <div class="calendar-fields">
            <label>
              <span>{{ t("crypto.calendar.from") }}</span>
              <input
                v-model="draftStart"
                type="date"
                :max="draftEnd"
                required
              />
            </label>
            <span aria-hidden="true">→</span>
            <label>
              <span>{{ t("crypto.calendar.to") }}</span>
              <input
                v-model="draftEnd"
                type="date"
                :min="draftStart"
                required
              />
            </label>
          </div>
          <footer class="calendar-dialog-actions">
            <button type="button" @click="closeCalendar">
              {{ t("crypto.actions.cancel") }}
            </button>
            <button class="primary" type="submit" :disabled="!customRangeValid">
              {{ t("crypto.calendar.applyPeriod") }}
            </button>
          </footer>
        </form>
      </dialog>

      <dialog
        ref="chartCalendarDialog"
        class="calendar-dialog"
        aria-labelledby="chart-calendar-dialog-title"
      >
        <form @submit.prevent="applyChartCustomRange">
          <header>
            <div>
              <p class="section-label">
                {{ t("crypto.calendar.customPeriod") }}
              </p>
              <h2 id="chart-calendar-dialog-title">
                {{ t("crypto.calendar.selectDates") }}
              </h2>
            </div>
          </header>
          <div class="calendar-fields">
            <label
              ><span>{{ t("crypto.calendar.from") }}</span
              ><input
                v-model="chartDraftStart"
                type="date"
                :max="chartDraftEnd"
                required /></label
            ><span aria-hidden="true">→</span
            ><label
              ><span>{{ t("crypto.calendar.to") }}</span
              ><input
                v-model="chartDraftEnd"
                type="date"
                :min="chartDraftStart"
                required
            /></label>
          </div>
          <footer class="calendar-dialog-actions">
            <button type="button" @click="closeChartCalendar">
              {{ t("crypto.actions.cancel") }}</button
            ><button
              class="primary"
              type="submit"
              :disabled="!chartCustomRangeValid"
            >
              {{ t("crypto.calendar.applyPeriod") }}
            </button>
          </footer>
        </form>
      </dialog>

      <dialog
        ref="accountDialog"
        class="calendar-dialog account-dialog"
        aria-labelledby="account-dialog-title"
        @cancel.prevent="closeAccountDialog"
      >
        <form @submit.prevent="saveAccount">
          <header>
            <div>
              <p class="section-label">{{ t("crypto.accounts.section") }}</p>
              <h2 id="account-dialog-title">
                {{
                  accountDialogMode === "edit"
                    ? t("crypto.accounts.manageTitle")
                    : t("crypto.accounts.addTitle")
                }}
              </h2>
            </div>
          </header>
          <div class="account-fields">
            <label>
              <span>{{ t("crypto.accounts.name") }}</span>
              <input
                v-model="accountName"
                type="text"
                :placeholder="t('crypto.accounts.namePlaceholder')"
                required
              />
            </label>
            <label>
              <span>{{ t("crypto.accounts.exchange") }}</span>
              <input
                v-model="accountProvider"
                type="text"
                :placeholder="t('crypto.accounts.exchangePlaceholder')"
                required
              />
            </label>
            <label>
              <span>{{ t("crypto.accounts.currency") }}</span>
              <input
                v-model="accountCurrency"
                maxlength="3"
                minlength="3"
                pattern="[A-Za-z]{3}"
                required
              />
            </label>
            <label class="importer-field">
              <span>{{ t("crypto.accounts.importer") }}</span>
              <select v-model="accountImporter" required>
                <option value="" disabled>
                  {{ t("crypto.accounts.chooseImporter") }}
                </option>
                <option value="none">
                  {{ t("crypto.accounts.noImporter") }}
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
          <p class="account-dialog-note">
            {{ t("crypto.accounts.importerNote") }}
          </p>
          <p v-if="accountError" class="account-dialog-error" role="alert">
            {{ accountError }}
          </p>
          <footer class="calendar-dialog-actions">
            <button
              v-if="accountDialogMode === 'edit'"
              class="danger ghost-danger"
              type="button"
              :disabled="accountBusy"
              @click="deleteAccount"
            >
              {{
                accountDeleteArmed
                  ? t("crypto.accounts.confirmDelete")
                  : t("crypto.accounts.delete")
              }}
            </button>
            <span class="footer-spacer" />
            <button
              type="button"
              :disabled="accountBusy"
              @click="closeAccountDialog"
            >
              {{ t("crypto.actions.cancel") }}
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
                  ? t("crypto.accounts.saving")
                  : accountDialogMode === "edit"
                    ? t("crypto.accounts.saveChanges")
                    : t("crypto.accounts.create")
              }}
            </button>
          </footer>
        </form>
      </dialog>
    </template>
    <CryptoMovementsPanel
      v-show="!loading && !error"
      ref="movementPanel"
      :orders="orders"
      :instruments="instruments"
      :selected-account-label="selectedAccountLabel"
      :base-currency="reportingCurrency"
      :format-money="money"
      :format-quantity="(value) => n(value, 'quantity')"
      :display-date="displayDate"
      :base-price="basePrice"
      :base-amount="baseAmount"
      :base-fee="baseFee"
      @add="openNewMovement"
      @edit="openEditMovement"
      @delete="askDeleteMovement"
    />
  </section>
</template>

<style scoped>
.crypto-page {
  --crypto-accent: #7967f2;
  --crypto-accent-deep: #5543c7;
  --crypto-signal: #55cbef;
  --crypto-amber: #f7931a;
  --fz-accent: var(--crypto-accent);
  --fz-accent-soft: color-mix(
    in srgb,
    var(--crypto-accent) 12%,
    var(--fz-surface)
  );
  width: min(100%, 1440px);
  margin: 0 auto;
  padding: 8px 48px 56px;
}
.calendar-fields input {
  padding: 8px 28px 8px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  font-size: 11px;
  font-weight: 720;
}
.fund-performance-panel {
  margin-top: 20px;
  padding: 24px;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 22px;
  background: var(--fz-surface);
  box-shadow: var(--fz-shadow);
}
.fund-performance-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
}
.fund-performance-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 750;
  letter-spacing: -0.03em;
}
.fund-range-label {
  margin: 7px 0 0;
  color: var(--fz-muted);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.stock-performance-controls {
  display: grid;
  justify-items: end;
  gap: 9px;
}
.fund-mode-control,
.fund-range-control {
  display: flex;
  padding: 4px;
  border-radius: 11px;
  background: var(--fz-surface-soft);
}
.fund-mode-control button,
.fund-range-control button {
  padding: 7px 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 700;
  cursor: pointer;
}
.fund-mode-control button.active,
.fund-range-control button.active {
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
}
.stock-performance-meta {
  margin: 19px 0 4px;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  border-top: 1px solid var(--fz-line);
  border-left: 1px solid var(--fz-line);
}
.stock-performance-meta > div {
  min-width: 0;
  padding: 12px 13px;
  display: grid;
  gap: 4px;
  border-right: 1px solid var(--fz-line);
  border-bottom: 1px solid var(--fz-line);
}
.stock-performance-meta small,
.stock-performance-meta span {
  color: var(--fz-muted);
  font-size: 10px;
}
.stock-performance-meta strong {
  overflow: hidden;
  font-size: 14px;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fund-chart-state {
  min-height: 180px;
  display: grid;
  place-content: center;
  gap: 5px;
  color: var(--fz-muted);
  font-size: 10px;
  text-align: center;
}
.fund-chart-state strong {
  color: var(--fz-ink);
  font-size: 12px;
}
.fund-chart-state p {
  margin: 0;
}
.fund-chart-state button {
  width: fit-content;
  margin: 4px auto 0;
  padding: 7px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.calendar-dialog {
  width: min(520px, calc(100vw - 32px));
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 20px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 28px 90px rgba(0, 0, 0, 0.34);
}
.calendar-dialog::backdrop {
  background: rgba(6, 11, 8, 0.68);
  backdrop-filter: blur(5px);
}
.calendar-dialog form {
  padding: 23px;
}
.calendar-dialog header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.calendar-dialog h2 {
  font-size: 18px;
}
.calendar-fields {
  margin-top: 23px;
  padding: 18px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: end;
  gap: 12px;
  border-radius: 14px;
  background: var(--fz-surface-soft);
}
.calendar-fields label {
  display: grid;
  gap: 7px;
}
.calendar-fields label span {
  color: var(--fz-muted);
  font-size: 9px;
  font-weight: 690;
}
.calendar-fields > span {
  padding-bottom: 9px;
  color: var(--fz-muted);
}
.calendar-fields input {
  width: 100%;
  min-width: 0;
  padding-right: 10px;
}
.account-fields {
  margin-top: 23px;
  padding: 18px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  border-radius: 14px;
  background: var(--fz-surface-soft);
}
.account-fields label {
  display: grid;
  gap: 7px;
}
.account-fields span {
  color: var(--fz-muted);
  font-size: 9px;
  font-weight: 690;
}
.account-fields input,
.account-fields select {
  min-width: 0;
  width: 100%;
  padding: 10px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font-size: 10px;
}
.account-fields input::placeholder {
  color: color-mix(in srgb, var(--fz-muted) 68%, transparent);
}
.account-dialog-note {
  margin: 14px 2px 0;
  color: var(--fz-muted);
  font-size: 9px;
  line-height: 1.55;
}
.account-dialog-error {
  margin: 10px 2px 0;
  color: var(--fz-negative);
  font-size: 9px;
  font-weight: 680;
}
.calendar-dialog-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
}
.calendar-dialog-actions .footer-spacer {
  flex: 1;
}
.calendar-dialog-actions button {
  padding: 9px 13px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 710;
  cursor: pointer;
}
.calendar-dialog-actions .primary {
  border-color: var(--fz-accent);
  background: var(--fz-accent);
  color: #f4fff9;
}
.calendar-dialog-actions .danger {
  border-color: color-mix(in srgb, var(--fz-negative) 55%, var(--fz-line));
  color: var(--fz-negative);
}
.calendar-dialog-actions .ghost-danger {
  background: transparent;
}
.calendar-dialog-actions button:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}
.crypto-loading {
  display: grid;
  grid-template-columns: 1.35fr 0.72fr;
  gap: 20px;
}
.crypto-loading div {
  min-height: 330px;
  border-radius: 22px;
  background: linear-gradient(
    90deg,
    var(--fz-surface-soft),
    var(--fz-surface),
    var(--fz-surface-soft)
  );
  background-size: 220% 100%;
  animation: skeleton 1.4s ease-in-out infinite;
}
.crypto-loading div:last-child {
  min-height: 430px;
  grid-column: 1 / -1;
}

@media (max-width: 1180px) {
  .stock-performance-meta {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .crypto-page {
    padding: 4px 18px 32px;
  }
  .calendar-fields {
    grid-template-columns: minmax(0, 1fr);
  }
  .account-fields {
    grid-template-columns: minmax(0, 1fr);
  }
  .calendar-fields > span {
    display: none;
  }
  .crypto-loading {
    grid-template-columns: 1fr;
  }
  .crypto-loading div:last-child {
    grid-column: auto;
  }
  .fund-performance-panel {
    padding: 19px 17px;
    border-radius: 18px;
  }
  .fund-performance-header {
    display: grid;
    justify-content: stretch;
    gap: 14px;
  }
  .stock-performance-controls {
    justify-items: stretch;
    overflow-x: auto;
  }
  .fund-mode-control,
  .fund-range-control {
    width: max-content;
    max-width: 100%;
    overflow-x: auto;
  }
  .stock-performance-meta {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

/* Type hierarchy shared with Stocks and Funds. */
.section-label {
  font-size: 10px;
}
.calendar-fields label span,
.account-fields span,
.account-dialog-note,
.account-dialog-error {
  font-size: 11px;
}
.account-fields input,
.account-fields select,
.calendar-dialog-actions button {
  font-size: 12px;
}

@media (prefers-reduced-motion: reduce) {
  .crypto-page *,
  .crypto-page *::before,
  .crypto-page *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
