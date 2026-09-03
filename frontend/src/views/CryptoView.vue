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
import {
  adaptCryptoAccount,
  adaptCryptoChart,
  adaptCryptoPerformance,
} from "../domain/investments";
import type { NormalizedPerformancePoint } from "../domain/investments";
import { reportingCurrency } from "../i18n";
import type {
  CryptoChartResponse,
  CryptoAccount,
  CryptoInstrument,
  CryptoOrder,
  CryptoPosition,
  CryptoPrice,
  CryptoPerformanceResponse,
  PriceFetchResponse,
  ImporterCatalogItem,
  MarketCandle,
} from "../types/api";
import {
  instrumentByIdentity,
  instrumentCurrency,
  instrumentIdentity,
  instrumentName,
  instrumentTicker,
} from "../domain/instruments";

type PerformanceRange = "6m" | "1y" | "2y" | "custom";
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
const performance = ref<CryptoPerformanceResponse | null>(null);
const chart = ref<CryptoChartResponse | null>(null);
const selectedAccount = ref(
  new URLSearchParams(window.location.search).get("account") ?? "all",
);
const selectedSymbol = ref("");
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
const movementCalendarDialog = ref<HTMLDialogElement>();
const accountDialog = ref<HTMLDialogElement>();
const assetEditor = ref<AssetEditorHandle>();
const movementEditor = ref<MovementEditorHandle>();
const movementDelete = ref<MovementDeleteHandle>();
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
const positionsCollapsed = ref(
  readStorageItem("finanzr-crypto-positions-collapsed") === "true",
);
const movementsCollapsed = ref(
  readStorageItem("finanzr-crypto-movements-collapsed") === "true",
);
const movementType = ref("all");
const movementPage = ref(1);
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
const movementSymbol = ref("all");
const movementStart = ref("");
const movementEnd = ref("");
const movementDraftStart = ref("");
const movementDraftEnd = ref("");

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
  selectedSymbol,
  baseCurrency: reportingCurrency,
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
const movementRangeValid = computed(() =>
  Boolean(
    movementDraftStart.value &&
    movementDraftEnd.value &&
    Date.parse(movementDraftStart.value) <= Date.parse(movementDraftEnd.value),
  ),
);

const normalizedAccounts = computed(() =>
  accounts.value.map(adaptCryptoAccount),
);
const normalizedPerformance = computed(() =>
  performance.value
    ? adaptCryptoPerformance(performance.value, {
        baseCurrency: reportingCurrency.value,
      })
    : null,
);
const performancePoints = computed<NormalizedPerformancePoint[]>(
  () => normalizedPerformance.value?.data ?? [],
);
const performanceChartPoints = computed(() =>
  performancePoints.value.map((point) => ({
    fecha: point.date,
    valor: point.value,
    invertido: point.invested,
    pnl: point.pnl,
    pnl_pct: point.pnlPercent,
  })),
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
const normalizedChart = computed(() =>
  chart.value
    ? adaptCryptoChart(chart.value, { baseCurrency: reportingCurrency.value })
    : null,
);
const chartPoints = computed<MarketCandle[]>(
  () =>
    normalizedChart.value?.data.map((point) => ({
      fecha: point.date,
      precio: point.close,
      open: point.open,
      high: point.high,
      low: point.low,
      close: point.close,
      moneda_base: reportingCurrency.value,
    })) ?? [],
);
const allocationItems = computed<InvestmentAllocationItem[]>(() => {
  const valued = openPositions.value.flatMap((position) =>
    typeof position.valor_actual === "number" && position.valor_actual > 0
      ? [{ position, value: position.valor_actual }]
      : [],
  );
  const total = valued.reduce((sum, item) => sum + item.value, 0);
  if (!(total > 0)) return [];
  const colors = ["#7967f2", "#55cbef", "#f7931a", "#b18cff", "#56d6a0"];
  const items = valued.slice(0, 5).map(({ position, value }, index) => ({
    key: position.symbol,
    label: position.nombre,
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
const movementSymbols = computed(() => {
  const names = new Map(
    instruments.value.map((item) => [
      instrumentIdentity(item),
      instrumentName(item),
    ]),
  );
  orders.value.forEach((item) => {
    names.set(
      item.symbol,
      item.asset_name || names.get(item.symbol) || item.symbol,
    );
  });
  return [...names.entries()]
    .filter(([symbol]) => orders.value.some((item) => item.symbol === symbol))
    .map(([symbol, name]) => ({ symbol, name }))
    .sort((a, b) => a.symbol.localeCompare(b.symbol));
});
const filteredMovements = computed(() =>
  [...orders.value]
    .filter(
      (item) =>
        movementSymbol.value === "all" || item.symbol === movementSymbol.value,
    )
    .filter(
      (item) =>
        movementType.value === "all" ||
        operationGroup(item) === movementType.value,
    )
    .filter(
      (item) =>
        !movementStart.value ||
        item.trade_date.slice(0, 10) >= movementStart.value,
    )
    .filter(
      (item) =>
        !movementEnd.value || item.trade_date.slice(0, 10) <= movementEnd.value,
    )
    .sort(
      (a, b) =>
        b.trade_date.localeCompare(a.trade_date) ||
        String(b.id).localeCompare(String(a.id)),
    ),
);
const movementPages = computed(() =>
  Math.max(1, Math.ceil(filteredMovements.value.length / 15)),
);
const displayedMovements = computed(() =>
  filteredMovements.value.slice(
    (movementPage.value - 1) * 15,
    movementPage.value * 15,
  ),
);
const movementRangeLabel = computed(() =>
  movementStart.value && movementEnd.value
    ? `${displayDate(movementStart.value)} → ${displayDate(movementEnd.value)}`
    : t("crypto.movements.allDates"),
);
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

function positionReturn(position: CryptoPosition) {
  return position.coste_total ? (position.pnl ?? 0) / position.coste_total : 0;
}

function signedMoney(value: number) {
  return `${value >= 0 ? "+" : "−"}${money(Math.abs(value))}`;
}

function initializeMovementRange() {
  if (!orders.value.length || (movementStart.value && movementEnd.value))
    return;
  const dates = orders.value.map((item) => item.trade_date.slice(0, 10)).sort();
  movementStart.value = dates[0];
  movementEnd.value = dates.at(-1) ?? dates[0];
  movementDraftStart.value = movementStart.value;
  movementDraftEnd.value = movementEnd.value;
}

function resetMovementFiltersForAccount() {
  movementSymbol.value = "all";
  movementStart.value = "";
  movementEnd.value = "";
  movementDraftStart.value = "";
  movementDraftEnd.value = "";
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
  movementPage.value = 1;
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
    initializeMovementRange();
    const available = openPositions.value.map((position) => position.symbol);
    if (!available.includes(selectedSymbol.value)) selectedSymbol.value = "";
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
    if (loadSelectedChart && selectedSymbol.value) await loadChart(generation);
  }
}

async function loadPerformance(generation = dashboardGeneration) {
  if (generation !== dashboardGeneration) return;
  const request = ++performanceRequestGeneration;
  performanceLoading.value = true;
  performanceError.value = "";
  try {
    const result = await api<CryptoPerformanceResponse>(
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
  resetMovementFiltersForAccount();
  movementType.value = "all";
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
    resetMovementFiltersForAccount();
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
    resetMovementFiltersForAccount();
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
  if (generation !== dashboardGeneration || !selectedSymbol.value) return;
  const request = ++chartRequestGeneration;
  const instrumentId = instrumentByIdentity(
    instruments.value,
    selectedSymbol.value,
  )?.id;
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
  selectedSymbol.value = "";
  chartRequestGeneration += 1;
  chart.value = null;
  chartLoading.value = false;
  chartError.value = "";
}

async function togglePosition(symbol: string) {
  if (selectedSymbol.value === symbol) {
    closePosition();
    return;
  }
  selectedSymbol.value = symbol;
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

function openMovementCalendar() {
  movementDraftStart.value = movementStart.value;
  movementDraftEnd.value = movementEnd.value;
  movementCalendarDialog.value?.showModal();
}

function closeMovementCalendar() {
  movementCalendarDialog.value?.close();
}

function applyMovementRange() {
  if (!movementRangeValid.value) return;
  movementStart.value = movementDraftStart.value;
  movementEnd.value = movementDraftEnd.value;
  closeMovementCalendar();
}

function operationGroup(order: CryptoOrder) {
  return movementTone(order) === "is-buy" ? "in" : "out";
}

function hasOriginalCurrency(order: CryptoOrder) {
  return Boolean(order.currency && order.currency !== reportingCurrency.value);
}

function assetTicker(position: CryptoPosition) {
  return (
    instrumentTicker(
      instrumentByIdentity(instruments.value, position.symbol),
    ) || position.symbol
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

function togglePositions() {
  positionsCollapsed.value = !positionsCollapsed.value;
  writeStorageItem(
    "finanzr-crypto-positions-collapsed",
    String(positionsCollapsed.value),
  );
}

function toggleMovements() {
  movementsCollapsed.value = !movementsCollapsed.value;
  writeStorageItem(
    "finanzr-crypto-movements-collapsed",
    String(movementsCollapsed.value),
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

function movementTone(order: CryptoOrder) {
  if (order.operation_type === "buy") return "is-buy";
  if (order.operation_type === "sell") return "is-sell";
  return "is-neutral";
}

function movementLabel(order: CryptoOrder) {
  if (order.operation_type === "buy") return t("crypto.movements.buy");
  if (order.operation_type === "sell") return t("crypto.movements.sell");
  return order.provider_operation_type || order.operation_type;
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
  const symbol = instrumentIdentity(asset);
  if (symbol) selectedSymbol.value = symbol;
  await loadDashboard(true, false);
  if (generation !== assetSaveGeneration || !symbol) return;
  selectedSymbol.value = symbol;
  await loadChart();
}

watch([movementSymbol, movementType, movementStart, movementEnd], () => {
  movementPage.value = 1;
});
watch(movementPages, (pages) => {
  if (movementPage.value > pages) movementPage.value = pages;
});
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
              percentage((lastPerformance?.pnlPercent ?? 0) / 100)
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
          v-else-if="performanceChartPoints.length >= 2"
          :points="performanceChartPoints"
          :mode="mode"
        />
        <div v-else class="fund-chart-state">
          <strong>{{ t("crypto.performance.insufficientHistory") }}</strong>
          <p>{{ t("crypto.performance.insufficientHistoryHint") }}</p>
        </div>
      </article>

      <article
        class="fund-performance-panel positions-panel crypto-positions-panel"
        :class="{ collapsed: positionsCollapsed }"
      >
        <header class="fund-secondary-header">
          <div>
            <p class="section-label">{{ t("crypto.positions.section") }}</p>
            <h2>{{ t("crypto.positions.title") }}</h2>
            <p class="fund-range-label">
              {{
                t(
                  positions.length === 1
                    ? "crypto.positions.pricedOne"
                    : "crypto.positions.pricedMany",
                  { priced: pricedPositions, total: positions.length },
                )
              }}
              ·
              {{
                t("crypto.positions.pricesInCurrency", {
                  currency: reportingCurrency,
                })
              }}
            </p>
          </div>
          <div class="fund-collapsible-actions">
            <InvestmentAddAssetButton
              :label="t('crypto.assets.add')"
              @add="assetEditor?.openCreate()"
            />
            <InvestmentCollapseButton
              :collapsed="positionsCollapsed"
              controls="crypto-positions-content"
              :label="
                t(
                  positionsCollapsed
                    ? 'crypto.positions.expandAria'
                    : 'crypto.positions.collapseAria',
                )
              "
              @toggle="togglePositions"
            />
          </div>
        </header>
        <div
          v-show="!positionsCollapsed"
          id="crypto-positions-content"
          class="fund-positions-content"
        >
          <InvestmentAllocationStrip
            :items="allocationItems"
            :total="allocationTotal"
            :account-label="selectedAccountLabel"
            :title="t('crypto.positions.marketValueDistribution')"
            :bar-label="t('crypto.positions.marketValueDistributionBarAria')"
            :empty-label="t('crypto.positions.noMarketValueDistribution')"
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
                  :key="position.symbol"
                  ><tr
                    class="fund-position-row"
                    :class="{ active: selectedSymbol === position.symbol }"
                    @click="togglePosition(position.symbol)"
                  >
                    <td>
                      <button
                        type="button"
                        class="fund-position-disclosure"
                        :aria-expanded="selectedSymbol === position.symbol"
                        :aria-controls="detailId(position.symbol)"
                        :aria-label="
                          t(
                            selectedSymbol === position.symbol
                              ? 'crypto.positions.collapseChartAria'
                              : 'crypto.positions.expandChartAria',
                            { asset: position.nombre },
                          )
                        "
                        @click.stop="togglePosition(position.symbol)"
                      >
                        <span class="fund-position-disclosure-copy"
                          ><strong>{{ position.nombre }}</strong
                          ><small>{{ position.symbol }}</small></span
                        ><span aria-hidden="true">⌄</span>
                      </button>
                    </td>
                    <td>{{ assetTicker(position) }}</td>
                    <td>{{ money(position.coste_total) }}</td>
                    <td>{{ n(position.titulos, "quantity") }}</td>
                    <td>
                      {{
                        money(
                          position.titulos
                            ? position.coste_total / position.titulos
                            : 0,
                        )
                      }}
                    </td>
                    <td>
                      {{
                        position.precio_actual == null
                          ? t("crypto.positions.pending")
                          : money(position.precio_actual)
                      }}
                    </td>
                    <td>
                      {{
                        position.valor_actual == null
                          ? "—"
                          : money(position.valor_actual)
                      }}
                    </td>
                    <td
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
                        :aria-label="t('crypto.positions.editAria')"
                        @click.stop="
                          assetEditor?.openEdit(
                            instrumentByIdentity(instruments, position.symbol),
                          )
                        "
                      >
                        ✎
                      </button>
                    </td>
                  </tr>
                  <tr
                    v-if="selectedSymbol === position.symbol"
                    class="fund-inline-detail-row"
                  >
                    <td :colspan="positionSortColumns.length + 1">
                      <div
                        :id="detailId(position.symbol)"
                        class="fund-inline-price-panel"
                        role="region"
                        :aria-label="
                          t('crypto.positions.priceDetailAria', {
                            asset: position.nombre,
                          })
                        "
                      >
                        <div class="fund-inline-chart-toolbar">
                          <div class="fund-chart-legend">
                            <span
                              >▌ {{ t("crypto.chart.bullishCandle") }} /
                              {{ t("crypto.chart.bearishCandle") }}</span
                            ><span>╍ {{ t("crypto.chart.averagePrice") }}</span
                            ><span>+ {{ t("crypto.movements.buy") }}</span
                            ><span>− {{ t("crypto.movements.sell") }}</span>
                          </div>
                          <div class="fund-inline-range">
                            <p class="fund-range-label">
                              {{ chartRangeLabel }}
                            </p>
                            <div
                              class="fund-range-control"
                              :aria-label="t('crypto.chart.rangeAria')"
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
                          {{ t("crypto.chart.loading") }}
                        </div>
                        <div
                          v-else-if="chartError"
                          class="fund-chart-state error-state"
                        >
                          <strong>{{ t("crypto.chart.unavailable") }}</strong>
                          <p>{{ chartError }}</p>
                          <button type="button" @click="loadChart()">
                            {{ t("crypto.actions.retry") }}
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
                          {{ t("crypto.chart.noData") }}
                        </div>
                      </div>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
          <div v-if="!sortedPositions.length" class="fund-empty-compact">
            {{ t("crypto.assets.noOpenPositionsHint") }}
          </div>
        </div>
      </article>

      <article
        class="fund-performance-panel movements-panel"
        :class="{ collapsed: movementsCollapsed }"
      >
        <header class="fund-secondary-header">
          <div>
            <p class="section-label">{{ t("crypto.movements.section") }}</p>
            <h2>{{ t("crypto.movements.title") }}</h2>
            <p class="fund-range-label">
              {{
                t(
                  filteredMovements.length === 1
                    ? "crypto.movements.operation"
                    : "crypto.movements.operations",
                  { count: filteredMovements.length },
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
                + {{ t("crypto.movements.add") }}</button
              ><select
                v-model="movementSymbol"
                :aria-label="t('crypto.movements.currencyFilterAria')"
              >
                <option value="all">
                  {{ t("crypto.movements.allCurrencies") }}
                </option>
                <option
                  v-for="item in movementSymbols"
                  :key="item.symbol"
                  :value="item.symbol"
                >
                  {{ item.symbol }} · {{ item.name }}
                </option></select
              ><select
                v-model="movementType"
                :aria-label="t('crypto.movements.filterTypeAria')"
              >
                <option value="all">
                  {{ t("crypto.movements.allMovements") }}
                </option>
                <option value="in">{{ t("crypto.movements.entries") }}</option>
                <option value="out">
                  {{ t("crypto.movements.exits") }}
                </option></select
              ><button
                type="button"
                :aria-label="t('crypto.movements.dateFilterAria')"
                @click="openMovementCalendar"
              >
                {{ movementRangeLabel }}
              </button>
            </div>
            <InvestmentCollapseButton
              :collapsed="movementsCollapsed"
              controls="crypto-movements-content"
              :label="
                t(
                  movementsCollapsed
                    ? 'crypto.movements.expandAria'
                    : 'crypto.movements.collapseAria',
                )
              "
              @toggle="toggleMovements"
            />
          </div>
        </header>
        <div v-show="!movementsCollapsed" id="crypto-movements-content">
          <div class="fund-table-scroll">
            <table class="fund-table movement-table">
              <thead>
                <tr>
                  <th>{{ t("crypto.movements.date") }}</th>
                  <th>{{ t("crypto.movements.movement") }}</th>
                  <th>{{ t("crypto.movements.asset") }}</th>
                  <th>{{ t("crypto.movements.account") }}</th>
                  <th>{{ t("crypto.movements.quantity") }}</th>
                  <th>{{ t("crypto.movements.price") }}</th>
                  <th>{{ t("crypto.movements.amount") }}</th>
                  <th>{{ t("crypto.movements.fee") }}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in displayedMovements"
                  :key="item.id"
                  :data-testid="`movement-${item.id}`"
                >
                  <td>{{ displayDate(item.trade_date) }}</td>
                  <td>
                    <span
                      class="operation-pill"
                      :class="operationGroup(item)"
                      >{{ movementLabel(item) }}</span
                    >
                  </td>
                  <td>
                    <strong>{{ item.asset_name }}</strong
                    ><small>{{ item.symbol }}</small>
                  </td>
                  <td>
                    {{ item.account_name || selectedAccountLabel
                    }}<small>{{
                      item.platform || t("crypto.accounts.cryptoFallback")
                    }}</small>
                  </td>
                  <td>{{ n(item.quantity, "quantity") }}</td>
                  <td>
                    {{ money(basePrice(item))
                    }}<small v-if="hasOriginalCurrency(item)">{{
                      originalMoney(item.unit_price, item.currency)
                    }}</small>
                  </td>
                  <td>
                    <strong>{{ money(baseAmount(item)) }}</strong
                    ><small v-if="hasOriginalCurrency(item)">{{
                      originalMoney(item.net_amount, item.currency)
                    }}</small>
                  </td>
                  <td>
                    {{ money(baseFee(item))
                    }}<small v-if="hasOriginalCurrency(item)">{{
                      originalMoney(item.fee, item.currency)
                    }}</small>
                  </td>
                  <td>
                    <InvestmentMovementActions
                      :edit-label="t('crypto.movements.edit')"
                      :delete-label="t('crypto.movements.delete')"
                      @edit="openEditMovement(item)"
                      @delete="askDeleteMovement(item)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="!filteredMovements.length" class="fund-empty-compact">
            {{ t("crypto.movements.noResults") }}
          </div>
          <nav
            v-else-if="movementPages > 1"
            class="movement-pagination"
            :aria-label="t('crypto.movements.paginationAria')"
          >
            <span>{{
              t("crypto.movements.page", {
                page: movementPage,
                pages: movementPages,
              })
            }}</span>
            <div>
              <button
                type="button"
                :disabled="movementPage === 1"
                @click="movementPage -= 1"
              >
                {{ t("crypto.movements.previous") }}</button
              ><button
                type="button"
                :disabled="movementPage === movementPages"
                @click="movementPage += 1"
              >
                {{ t("crypto.movements.next") }}
              </button>
            </div>
          </nav>
        </div>
      </article>

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
        ref="movementCalendarDialog"
        class="calendar-dialog movement-calendar-dialog"
        aria-labelledby="movement-calendar-title"
        @cancel.prevent="closeMovementCalendar"
      >
        <form @submit.prevent="applyMovementRange">
          <header>
            <div>
              <p class="section-label">
                {{ t("crypto.movements.filterSection") }}
              </p>
              <h2 id="movement-calendar-title">
                {{ t("crypto.calendar.selectDates") }}
              </h2>
            </div>
          </header>
          <div class="calendar-fields">
            <label>
              <span>{{ t("crypto.calendar.from") }}</span>
              <input
                v-model="movementDraftStart"
                type="date"
                :max="movementDraftEnd"
                required
              />
            </label>
            <span aria-hidden="true">→</span>
            <label>
              <span>{{ t("crypto.calendar.to") }}</span>
              <input
                v-model="movementDraftEnd"
                type="date"
                :min="movementDraftStart"
                required
              />
            </label>
          </div>
          <footer class="calendar-dialog-actions">
            <button type="button" @click="closeMovementCalendar">
              {{ t("crypto.actions.cancel") }}
            </button>
            <button
              class="primary"
              type="submit"
              :disabled="!movementRangeValid"
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
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.crypto-account-bar {
  margin-bottom: 16px;
  padding: 11px 12px 11px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border: 1px solid var(--fz-line);
  border-radius: 16px;
  background:
    radial-gradient(
      circle at 88% -70%,
      color-mix(in srgb, var(--crypto-signal) 15%, transparent),
      transparent 34%
    ),
    linear-gradient(
      105deg,
      color-mix(in srgb, var(--crypto-accent) 11%, transparent),
      transparent 46%
    ),
    var(--fz-surface);
  box-shadow: 0 10px 26px
    color-mix(in srgb, var(--fz-chart-tooltip-shadow) 34%, transparent);
}
.account-scope-copy,
.account-scope-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.account-scope-mark {
  width: 31px;
  height: 31px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: linear-gradient(
    145deg,
    var(--crypto-accent),
    var(--crypto-accent-deep)
  );
  color: #fff;
  box-shadow: 0 5px 12px
    color-mix(in srgb, var(--crypto-accent) 24%, transparent);
  font-size: 11px;
  font-weight: 820;
  text-transform: uppercase;
}
.account-scope-copy div {
  display: grid;
  gap: 1px;
}
.account-scope-copy small {
  color: var(--fz-muted);
  font-size: 8px;
  font-weight: 680;
}
.account-scope-copy strong {
  font-size: 11px;
  font-weight: 750;
}
.account-scope-actions select,
.account-scope-actions button,
.account-scope-actions summary {
  min-height: 34px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  font-size: 9px;
  font-weight: 710;
}
.account-scope-actions select {
  min-width: 160px;
  padding: 8px 30px 8px 11px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
}
.account-scope-actions button,
.account-scope-actions summary {
  padding: 8px 11px;
  background: transparent;
  color: var(--fz-muted);
  cursor: pointer;
}
.account-scope-actions button:hover,
.account-scope-actions summary:hover {
  border-color: var(--fz-accent);
  color: var(--fz-ink);
}
.account-scope-actions details {
  position: relative;
}
.account-scope-actions summary {
  display: grid;
  place-items: center;
  list-style: none;
}
.account-scope-actions summary::-webkit-details-marker {
  display: none;
}
.account-scope-actions button span {
  margin-right: 3px;
  color: var(--fz-accent);
  font-size: 13px;
}
.crypto-top-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(340px, 0.72fr);
  gap: 20px;
}
.crypto-panel {
  min-width: 0;
  border: 1px solid var(--fz-line);
  border-radius: 22px;
  background: var(--fz-surface);
  box-shadow: var(--fz-shadow);
}
.assets-panel,
.kpi-panel {
  padding: 24px;
}
.crypto-panel-header,
.chart-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.asset-header-actions {
  display: flex;
  align-items: center;
  gap: 7px;
}
.asset-header-actions button {
  min-height: 32px;
  padding: 7px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 8px;
  font-weight: 720;
  cursor: pointer;
}
.asset-header-actions button:hover:not(:disabled) {
  border-color: var(--fz-accent);
  color: var(--fz-ink);
}
.asset-header-actions button.primary {
  border-color: color-mix(in srgb, var(--fz-accent) 55%, var(--fz-line));
  background: color-mix(in srgb, var(--fz-accent) 9%, transparent);
  color: var(--fz-ink);
}
.asset-header-actions button.primary span {
  margin-right: 3px;
  color: var(--fz-accent);
  font-size: 12px;
}
.asset-header-actions button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.crypto-panel h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 730;
  letter-spacing: -0.03em;
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
.asset-table {
  margin-top: 19px;
  overflow-x: auto;
  scrollbar-width: thin;
}
.asset-table-head,
.asset-row {
  min-width: 500px;
  display: grid;
  grid-template-columns:
    minmax(108px, 1.2fr) repeat(4, minmax(68px, 0.76fr))
    minmax(82px, 0.82fr);
  gap: 8px;
  align-items: center;
}
.asset-table-head {
  padding: 0 8px 8px;
  color: var(--fz-muted);
  font-size: 8px;
  font-weight: 710;
}
.asset-table-head span:not(:first-child) {
  text-align: right;
}
.asset-row {
  width: 100%;
  padding: 11px 8px;
  border: 0;
  border-top: 1px solid var(--fz-line);
  background: transparent;
  color: var(--fz-ink);
  text-align: left;
  cursor: pointer;
  transition:
    background 0.16s ease,
    transform 0.16s ease;
}
.asset-row:hover {
  background: var(--fz-surface-soft);
}
.asset-row.active {
  background: color-mix(in srgb, var(--fz-accent) 8%, transparent);
  box-shadow: inset 3px 0 var(--fz-accent);
}
.asset-identity {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.asset-identity > i {
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: color-mix(in srgb, var(--crypto-amber) 17%, var(--fz-surface));
  color: var(--crypto-amber);
  font-size: 12px;
  font-style: normal;
  font-weight: 820;
}
.asset-identity strong,
.asset-identity small,
.asset-cell strong,
.asset-cell small {
  display: block;
}
.asset-identity strong {
  font-size: 11px;
  font-weight: 760;
}
.asset-identity small {
  overflow: hidden;
  margin-top: 2px;
  color: var(--fz-muted);
  font-size: 8px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.asset-cell {
  min-width: 0;
  text-align: right;
}
.asset-cell small {
  display: none;
  color: var(--fz-muted);
  font-size: 8px;
}
.asset-cell strong {
  overflow: hidden;
  font-size: 9px;
  font-weight: 710;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.asset-contributed strong {
  color: var(--fz-accent);
}
.crypto-live {
  padding: 6px 9px;
  border-radius: 999px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  font-size: 9px;
  font-weight: 720;
}
.crypto-live i {
  width: 6px;
  height: 6px;
  display: inline-block;
  margin-right: 5px;
  border-radius: 50%;
  background: var(--fz-accent);
}
.crypto-kpi-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 18px;
  border-top: 1px solid var(--fz-line);
  border-left: 1px solid var(--fz-line);
}
.crypto-kpi-grid > div {
  min-width: 0;
  padding: 14px;
  display: grid;
  gap: 4px;
  border-right: 1px solid var(--fz-line);
  border-bottom: 1px solid var(--fz-line);
}
.crypto-kpi-grid small,
.crypto-kpi-grid span,
.crypto-utility small,
.crypto-utility span {
  color: var(--fz-muted);
  font-size: 8px;
}
.crypto-kpi-grid strong {
  font-size: 14px;
  font-weight: 740;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.025em;
}
.crypto-kpi-grid .primary-kpi {
  grid-column: 1 / -1;
  padding-block: 17px;
  background: linear-gradient(
    120deg,
    color-mix(in srgb, var(--fz-accent) 9%, transparent),
    transparent
  );
}
.crypto-kpi-grid .primary-kpi strong {
  font-size: 25px;
  letter-spacing: -0.045em;
}
.crypto-utility {
  position: relative;
  margin-top: 17px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.crypto-utility > div:first-child {
  display: grid;
  gap: 2px;
}
.crypto-utility > div:first-child strong {
  font-size: 10px;
}
.crypto-actions {
  display: flex;
  align-items: center;
  gap: 7px;
}
.crypto-actions > button,
.crypto-actions summary,
.chart-error button {
  padding: 8px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 9px;
  font-weight: 690;
  cursor: pointer;
}
.crypto-actions > button:hover,
.crypto-actions summary:hover {
  border-color: var(--fz-accent);
  color: var(--fz-ink);
}
.crypto-actions > button:disabled {
  opacity: 0.55;
  cursor: wait;
}
.crypto-actions details {
  position: relative;
}
.crypto-actions summary {
  list-style: none;
}
.crypto-actions summary::-webkit-details-marker {
  display: none;
}
.crypto-import-popover {
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
:deep(.import-compact) {
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 9px;
  border: 0;
  border-radius: 0;
  background: transparent;
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
  font-size: 9px;
}
:deep(.import-compact button) {
  padding: 9px 11px;
  border: 0;
  border-radius: 9px;
  background: var(--fz-accent);
  color: #f4fff9;
  font-size: 9px;
  font-weight: 720;
}
:deep(.import-compact p) {
  min-height: 12px;
  margin: 0;
  color: var(--fz-muted);
  font-size: 8px;
}
.kraken-pro-note {
  margin: 1px 0 0;
  color: var(--fz-muted);
  font-size: 8px;
  line-height: 1.45;
}
.chart-panel {
  margin-top: 20px;
  padding: 24px;
  overflow: hidden;
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
.fund-collapsible-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
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
  font-size: 10px;
  font-weight: 700;
  text-align: right;
  border-bottom: 1px solid var(--fz-line);
}
.fund-table th:first-child,
.fund-table td:first-child,
.fund-table th:nth-child(2),
.fund-table td:nth-child(2) {
  text-align: left;
}
.fund-table td {
  padding: 11px 10px;
  border-bottom: 1px solid var(--fz-line);
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.fund-sort-button {
  width: 100%;
  padding: 3px 0;
  display: flex;
  justify-content: flex-end;
  gap: 3px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}
.fund-table th:first-child .fund-sort-button,
.fund-table th:nth-child(2) .fund-sort-button {
  justify-content: flex-start;
}
.fund-sort-button:focus-visible {
  outline: 2px solid var(--fz-accent);
  outline-offset: 2px;
}
.fund-position-row {
  cursor: pointer;
  transition: background 0.14s ease;
}
.fund-position-row:hover,
.fund-position-row.active {
  background: color-mix(in srgb, var(--fz-accent) 7%, transparent);
}
.fund-position-row.active {
  box-shadow: inset 3px 0 var(--fz-accent);
}
.fund-position-disclosure {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--fz-ink);
  text-align: left;
  cursor: pointer;
}
.fund-position-disclosure-copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}
.fund-position-disclosure-copy strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fund-position-disclosure-copy small,
.fund-table td small {
  display: block;
  color: var(--fz-muted);
  font-size: 9px;
}
.fund-edit-icon-button {
  border: 0;
  background: transparent;
  color: var(--fz-muted);
  cursor: pointer;
}
.fund-edit-icon-button:hover {
  color: var(--fz-accent);
}
.fund-inline-detail-row td {
  padding: 12px 10px 16px;
  text-align: left;
  white-space: normal;
  border-bottom: 0;
}
.fund-inline-price-panel {
  padding: 17px 19px 19px;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 17px;
  background: var(--fz-surface);
}
.fund-inline-chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.fund-inline-range {
  display: grid;
  justify-items: end;
  gap: 7px;
}
.fund-inline-range .fund-range-label {
  margin: 0;
}
.fund-chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: var(--fz-muted);
  font-size: 10px;
}
.movement-pagination {
  margin-top: 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  color: var(--fz-muted);
  font-size: 11px;
}
.movement-pagination button {
  padding: 7px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.movement-pagination button:disabled {
  opacity: 0.4;
  cursor: default;
}
.movements-panel {
  margin-top: 20px;
  padding: 24px;
  overflow: hidden;
}
.movements-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
}
.movements-header h2 span {
  display: inline-grid;
  min-width: 22px;
  min-height: 22px;
  margin-left: 5px;
  place-items: center;
  border-radius: 999px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  font-size: 9px;
  vertical-align: 2px;
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
  white-space: nowrap;
  cursor: pointer;
}
.movement-filters .add-movement span {
  margin-right: 3px;
  font-size: 12px;
}
.movement-symbol-filter,
.movement-date-filter {
  min-height: 49px;
  display: grid;
  align-content: center;
  gap: 2px;
  border: 1px solid var(--fz-line);
  border-radius: 12px;
  background: var(--fz-surface-soft);
}
.movement-symbol-filter {
  min-width: 190px;
  padding: 7px 11px;
}
.movement-symbol-filter > span,
.movement-date-filter > span {
  color: var(--fz-muted);
  font-size: 8px;
  font-weight: 680;
}
.movement-symbol-filter select {
  width: 100%;
  padding: 0 22px 0 0;
  border: 0;
  background-color: transparent;
  color: var(--fz-ink);
  font-size: 10px;
  font-weight: 720;
  cursor: pointer;
}
.movement-date-filter {
  position: relative;
  min-width: 210px;
  padding: 7px 35px 7px 11px;
  color: var(--fz-ink);
  text-align: left;
  cursor: pointer;
}
.movement-date-filter strong {
  font-size: 10px;
  font-weight: 720;
  font-variant-numeric: tabular-nums;
}
.movement-date-filter i {
  position: absolute;
  top: 50%;
  right: 12px;
  color: var(--fz-muted);
  font-size: 13px;
  font-style: normal;
  transform: translateY(-50%);
}
.movement-symbol-filter:hover,
.movement-date-filter:hover {
  border-color: color-mix(in srgb, var(--fz-accent) 70%, var(--fz-line));
}
.movement-table {
  margin-top: 20px;
}
.movement-table-head,
.movement-row {
  display: grid;
  grid-template-columns:
    78px minmax(130px, 1.15fr) minmax(100px, 0.8fr)
    minmax(100px, 0.9fr) repeat(3, minmax(74px, 0.7fr)) 105px;
  gap: 10px;
  align-items: center;
}
.movement-table-head {
  padding: 0 12px 9px;
  color: var(--fz-muted);
  font-size: 8px;
  font-weight: 710;
}
.movement-table-head span:nth-child(n + 4) {
  text-align: right;
}
.movement-row {
  min-height: 64px;
  padding: 10px 12px;
  border-top: 1px solid var(--fz-line);
  transition: background 0.16s ease;
}
.movement-row:hover {
  background: var(--fz-surface-soft);
}
.movement-row time {
  color: var(--fz-muted);
  font-size: 9px;
  font-weight: 680;
  font-variant-numeric: tabular-nums;
}
.movement-kind,
.movement-account {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 9px;
}
.movement-kind > i {
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: color-mix(in srgb, currentColor 11%, transparent);
  font-size: 13px;
  font-style: normal;
  font-weight: 820;
}
.movement-kind > span,
.movement-account {
  display: grid;
  gap: 2px;
}
.movement-kind strong,
.movement-account strong {
  overflow: hidden;
  color: var(--fz-ink);
  font-size: 10px;
  font-weight: 720;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.movement-kind small,
.movement-account small,
.movement-number small {
  color: var(--fz-muted);
  font-size: 8px;
  font-weight: 570;
}
.movement-number {
  color: var(--fz-ink);
  font-size: 9px;
  font-weight: 690;
  font-variant-numeric: tabular-nums;
  text-align: right;
  white-space: nowrap;
}
.movement-number small {
  display: none;
}
.movement-number.muted {
  color: var(--fz-muted);
}
.movement-row-actions {
  display: flex;
  justify-content: flex-end;
  gap: 5px;
}
.movement-row-actions button {
  padding: 6px 8px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 8px;
  font-weight: 690;
  cursor: pointer;
}
.movement-row-actions button:hover {
  border-color: var(--fz-accent);
  color: var(--fz-ink);
}
.movement-row-actions .delete {
  color: var(--fz-negative);
}
.movement-kind.is-buy,
.movement-number.is-buy {
  color: var(--fz-positive);
}
.movement-kind.is-sell,
.movement-number.is-sell {
  color: var(--fz-negative);
}
.movement-kind.is-neutral,
.movement-number.is-neutral {
  color: var(--crypto-amber);
}
.movements-empty {
  min-height: 180px;
}
.chart-panel-header {
  align-items: flex-end;
}
.chart-asset-identity {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.chart-asset-mark {
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--crypto-amber) 22%, var(--fz-line));
  border-radius: 11px;
  background: color-mix(in srgb, var(--crypto-amber) 13%, var(--fz-surface));
  color: var(--crypto-amber);
  font-size: 13px;
  font-weight: 820;
}
.chart-asset-selector {
  display: grid;
  gap: 1px;
}
.chart-asset-selector > span {
  color: var(--fz-muted);
  font-size: 8px;
  font-weight: 680;
}
.chart-asset-selector select {
  max-width: 250px;
  padding: 1px 24px 1px 0;
  border: 0;
  background-color: transparent;
  color: var(--fz-ink);
  font-size: 17px;
  font-weight: 760;
  letter-spacing: -0.035em;
  cursor: pointer;
}
.chart-asset-selector select:focus-visible {
  border-radius: 5px;
}
.displayed-range {
  margin: 9px 0 0;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 680;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.01em;
}
.chart-range-control {
  display: flex;
  padding: 4px;
  border-radius: 12px;
  background: var(--fz-surface-soft);
}
.chart-range-control button {
  padding: 7px 10px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 9px;
  font-weight: 720;
  cursor: pointer;
}
.chart-range-control button.active {
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
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
.calendar-dialog header > button {
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
.chart-toolbar {
  min-height: 44px;
  margin: 17px 0 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}
.chart-variation {
  margin-left: auto;
  display: grid;
  gap: 2px;
  text-align: right;
}
.chart-variation small,
.chart-variation span {
  color: var(--fz-muted);
  font-size: 9px;
}
.chart-variation strong {
  font-size: 22px;
  letter-spacing: -0.04em;
}
.chart-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  gap: 10px 16px;
}
.chart-legend span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--fz-muted);
  font-size: 10px;
  line-height: 1;
  font-weight: 620;
  white-space: nowrap;
}
.chart-legend .legend-label {
  padding-right: 14px;
  border-right: 1px solid var(--fz-line);
  color: color-mix(in srgb, var(--fz-muted) 78%, transparent);
  font-size: 8px;
  font-weight: 760;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}
.chart-legend i {
  position: relative;
  flex: 0 0 auto;
  font-style: normal;
}
.chart-legend .up,
.chart-legend .down {
  width: 7px;
  height: 11px;
  border-radius: 1px;
}
.chart-legend .up {
  background: var(--fz-chart-up);
}
.chart-legend .down {
  background: var(--fz-chart-down);
}
.chart-legend .up::before,
.chart-legend .down::before {
  content: "";
  position: absolute;
  top: -3px;
  bottom: -3px;
  left: 3px;
  width: 1px;
  background: inherit;
}
.chart-legend .average {
  width: 18px;
  height: 0;
  border-top: 2px dashed var(--fz-chart-average);
}
.chart-legend .trade-pin {
  width: 18px;
  height: 16px;
  display: grid;
  place-items: center;
  border: 1.5px solid var(--fz-surface);
  border-radius: 5px;
  color: #fff;
  font-size: 11px;
  font-style: normal;
  font-weight: 780;
  line-height: 1;
  box-shadow: 0 1px 3px var(--fz-chart-tooltip-shadow);
}
.chart-legend .trade-pin.buy {
  border-color: var(--fz-trade-buy-outline);
  background: var(--fz-trade-buy);
}
.chart-legend .trade-pin.sell {
  border-color: var(--fz-trade-sell-outline);
  background: var(--fz-trade-sell);
}
.chart-loading,
.chart-error,
.crypto-empty {
  min-height: 190px;
  display: grid;
  place-content: center;
  text-align: center;
  color: var(--fz-muted);
  font-size: 11px;
}
.chart-loading {
  min-height: 360px;
}
.chart-error {
  min-height: 330px;
}
.chart-error strong,
.crypto-empty strong {
  color: var(--fz-ink);
  font-size: 13px;
}
.chart-error p,
.crypto-empty p {
  margin: 5px 0 12px;
}
.chart-error button {
  justify-self: center;
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
  .crypto-top-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .kpi-panel {
    order: -1;
  }
  .crypto-kpi-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .crypto-kpi-grid .primary-kpi {
    grid-column: auto;
  }
  .crypto-kpi-grid .primary-kpi strong {
    font-size: 18px;
  }
  .stock-performance-meta {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .crypto-page {
    padding: 4px 18px 32px;
  }
  .crypto-account-bar {
    align-items: stretch;
    flex-direction: column;
  }
  .account-scope-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .account-scope-actions label {
    grid-column: 1 / -1;
  }
  .account-scope-actions select {
    width: 100%;
    min-width: 0;
  }
  .assets-panel,
  .kpi-panel,
  .chart-panel,
  .movements-panel {
    padding: 19px 17px;
    border-radius: 18px;
  }
  .crypto-panel-header {
    display: block;
  }
  .asset-header-actions {
    margin-top: 14px;
  }
  .chart-panel-header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: end;
  }
  .asset-table {
    padding-bottom: 4px;
  }
  .crypto-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .crypto-kpi-grid .primary-kpi {
    grid-column: 1 / -1;
  }
  .crypto-utility {
    align-items: flex-start;
  }
  .crypto-actions {
    align-items: flex-end;
    flex-direction: column;
  }
  .chart-toolbar {
    align-items: stretch;
    flex-direction: column-reverse;
  }
  .chart-range-control {
    overflow-x: auto;
  }
  .chart-range-control button {
    flex: 1;
    white-space: nowrap;
  }
  .calendar-fields {
    grid-template-columns: minmax(0, 1fr);
  }
  .movements-header {
    align-items: stretch;
    flex-direction: column;
    gap: 15px;
  }
  .movement-filters {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }
  .movement-symbol-filter,
  .movement-date-filter,
  .movement-filters .add-movement {
    width: 100%;
    min-width: 0;
  }
  .movement-table-head {
    display: none;
  }
  .movement-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px 18px;
    padding: 15px 4px;
  }
  .movement-row time {
    grid-column: 1 / -1;
    padding-bottom: 7px;
    border-bottom: 1px dashed var(--fz-line);
  }
  .movement-kind,
  .movement-account {
    min-height: 34px;
  }
  .movement-number {
    display: grid;
    gap: 3px;
    text-align: left;
  }
  .movement-number small {
    display: block;
  }
  .movement-row-actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }
  .account-fields {
    grid-template-columns: minmax(0, 1fr);
  }
  .calendar-fields > span {
    display: none;
  }
  .chart-variation {
    align-self: flex-end;
  }
  .chart-legend {
    justify-content: flex-start;
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
  .fund-performance-header,
  .fund-secondary-header {
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
  .fund-collapsible-actions {
    width: 100%;
    flex-wrap: wrap;
  }
  .fund-collapsible-actions .movement-filters {
    width: 100%;
    order: 2;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }
  .fund-collapsible-actions .movement-filters select,
  .fund-collapsible-actions .movement-filters button {
    width: 100%;
    min-width: 0;
  }
  .fund-inline-chart-toolbar {
    align-items: stretch;
  }
  .fund-inline-range {
    justify-items: start;
  }
  .fund-inline-range .fund-range-control {
    width: 100%;
  }
}

/* Type hierarchy shared with Stocks and Funds. */
.section-label {
  font-size: 10px;
}
.account-scope-copy small,
.asset-identity small,
.asset-cell small,
.crypto-kpi-grid small,
.crypto-kpi-grid span,
.crypto-utility small,
.crypto-utility span,
:deep(.import-compact p),
.kraken-pro-note,
.movement-symbol-filter > span,
.movement-date-filter > span,
.movement-kind small,
.movement-account small,
.movement-number small,
.chart-asset-selector > span,
.chart-legend .legend-label {
  font-size: 10px;
}
.account-scope-actions select,
.account-scope-actions button,
.account-scope-actions summary,
.asset-header-actions button,
.asset-table-head,
.asset-cell strong,
.crypto-live,
.crypto-actions > button,
.crypto-actions summary,
.chart-error button,
:deep(.import-compact select),
:deep(.import-compact input),
:deep(.import-compact button),
.movements-header h2 span,
.movement-filters .add-movement,
.movement-table-head,
.movement-row time,
.movement-number,
.movement-row-actions button,
.chart-range-control button,
.calendar-fields label span,
.account-fields span,
.account-dialog-note,
.account-dialog-error,
.chart-variation small,
.chart-variation span {
  font-size: 11px;
}
.crypto-panel h2 {
  font-size: 20px;
}
.asset-identity strong,
.movement-kind strong,
.movement-account strong {
  font-size: 12px;
}
.crypto-kpi-grid strong {
  font-size: 16px;
}
.crypto-kpi-grid .primary-kpi strong {
  font-size: 27px;
}
.chart-asset-selector select {
  font-size: 19px;
}
.movement-row {
  min-height: 70px;
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
