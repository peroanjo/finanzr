<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { api, json } from "../api/client";
import CurrencyRateChart from "../components/CurrencyRateChart.vue";
import type {
  FetchFxRatesResult,
  FxConvertResult,
  FxRateChartResponse,
  FxRateItem,
  FxRatePayload,
} from "../types/api";

const { t, d, locale } = useI18n();

const rates = ref<FxRateItem[]>([]);
const loading = ref(true);
const error = ref("");
const actionMessage = ref("");
const updatingYahoo = ref(false);
type FxChartRange = "1m" | "6m" | "1y" | "2y" | "custom";
const fxChartRange = ref<FxChartRange>("1y");
const fxChartRanges: FxChartRange[] = ["1m", "6m", "1y", "2y", "custom"];
const fxChart = ref<FxRateChartResponse | null>(null);
const fxChartLoading = ref(false);
const fxChartError = ref("");
let fxChartRequest = 0;
const today = new Date();
const yearAgo = new Date(today);
yearAgo.setFullYear(yearAgo.getFullYear() - 1);
const dateInput = (value: Date) => value.toISOString().slice(0, 10);
const fxCustomStart = ref(dateInput(yearAgo));
const fxCustomEnd = ref(dateInput(today));
const fxDraftStart = ref(fxCustomStart.value);
const fxDraftEnd = ref(fxCustomEnd.value);

// Filters
const selectedPair = ref("all");

// Live Converter State
const calcAmount = ref<number>(100);
const calcFrom = ref("USD");
const calcTo = ref("EUR");
const calcDate = ref(new Date().toISOString().slice(0, 10));
const calcResult = ref<FxConvertResult | null>(null);
const calcLoading = ref(false);
const calcError = ref("");

// Dialog States
const rateDialog = ref<HTMLDialogElement>();
const deleteDialog = ref<HTMLDialogElement>();
const fxCalendarDialog = ref<HTMLDialogElement>();
const dialogMode = ref<"create" | "edit">("create");
const dialogId = ref<string | null>(null);
const formQuoteCurrency = ref("USD");
const formBaseCurrency = ref("EUR");
const formRateDate = ref(new Date().toISOString().slice(0, 10));
const formRate = ref<number | "">("");
const formSource = ref("manual");
const dialogBusy = ref(false);
const dialogError = ref("");

// Rate to Delete
const targetDeleteRate = ref<FxRateItem | null>(null);
const deleteBusy = ref(false);
const deleteError = ref("");

const uniquePairsInfo = computed(() => {
  const map = new Map<string, FxRateItem>();
  const sorted = [...rates.value].sort((a, b) => {
    const byDate = a.rate_date.localeCompare(b.rate_date);
    if (byDate !== 0) return byDate;
    const scopeOrder = { provider: 0, workspace: 1 };
    return (
      scopeOrder[a.scope ?? "provider"] - scopeOrder[b.scope ?? "provider"]
    );
  });
  for (const r of sorted) {
    map.set(`${r.quote_currency}/${r.base_currency}`, r);
  }
  return Array.from(map.values()).sort((a, b) => {
    const pairA = `${a.quote_currency}/${a.base_currency}`;
    const pairB = `${b.quote_currency}/${b.base_currency}`;
    return pairA.localeCompare(pairB);
  });
});

const selectedFxRate = computed(() => {
  if (selectedPair.value === "all") return null;
  return (
    uniquePairsInfo.value.find(
      (item) =>
        `${item.quote_currency}/${item.base_currency}` === selectedPair.value,
    ) || null
  );
});

const latestFxChartPoint = computed(() => fxChart.value?.data.at(-1) ?? null);
const fxCustomRangeValid = computed(() =>
  Boolean(
    fxDraftStart.value &&
    fxDraftEnd.value &&
    Date.parse(fxDraftStart.value) <= Date.parse(fxDraftEnd.value),
  ),
);

function selectCurrencyPair(item: FxRateItem) {
  selectedPair.value = `${item.quote_currency}/${item.base_currency}`;
  calcFrom.value = item.quote_currency;
  calcTo.value = item.base_currency;
  calcDate.value = item.rate_date;
}

function formatDate(isoDate: string) {
  void locale.value;
  const dt = new Date(`${isoDate.slice(0, 10)}T00:00:00`);
  return Number.isNaN(dt.getTime())
    ? isoDate
    : d(dt, { year: "numeric", month: "2-digit", day: "2-digit" });
}

function formatRawNumber(value: number, maxDecimals = 6) {
  return new Intl.NumberFormat(locale.value, {
    minimumFractionDigits: 2,
    maximumFractionDigits: maxDecimals,
  }).format(value);
}

async function loadFxChart() {
  const selection = selectedFxRate.value;
  const request = ++fxChartRequest;
  if (!selection) {
    fxChart.value = null;
    fxChartError.value = "";
    fxChartLoading.value = false;
    return;
  }
  fxChart.value = null;
  fxChartLoading.value = true;
  fxChartError.value = "";
  try {
    const query = new URLSearchParams({
      from: selection.quote_currency,
      to: selection.base_currency,
    });
    if (fxChartRange.value === "custom") {
      query.set("start", fxCustomStart.value);
      query.set("end", fxCustomEnd.value);
    } else {
      query.set("range", fxChartRange.value);
    }
    const result = await api<FxRateChartResponse>(`/fx-rates/chart?${query}`);
    if (request !== fxChartRequest) return;
    fxChart.value = result;
  } catch (reason) {
    if (request !== fxChartRequest) return;
    fxChart.value = null;
    fxChartError.value =
      reason instanceof Error
        ? reason.message
        : t("currencies.chart.unavailable");
  } finally {
    if (request === fxChartRequest) fxChartLoading.value = false;
  }
}

function selectFxChartRange(value: FxChartRange) {
  if (value !== "custom") {
    fxChartRange.value = value;
    return;
  }
  fxDraftStart.value = fxCustomStart.value;
  fxDraftEnd.value = fxCustomEnd.value;
  fxCalendarDialog.value?.showModal();
}

function closeFxCalendar() {
  fxCalendarDialog.value?.close();
}

function applyFxCustomRange() {
  if (!fxCustomRangeValid.value) return;
  fxCustomStart.value = fxDraftStart.value;
  fxCustomEnd.value = fxDraftEnd.value;
  const alreadyCustom = fxChartRange.value === "custom";
  fxChartRange.value = "custom";
  fxCalendarDialog.value?.close();
  if (alreadyCustom) void loadFxChart();
}

function inverseRate(rate: number) {
  return rate > 0 ? 1 / rate : 0;
}

async function loadRates() {
  loading.value = true;
  error.value = "";
  try {
    rates.value = await api<FxRateItem[]>("/fx-rates");
    const pairs = uniquePairsInfo.value.map(
      (item) => `${item.quote_currency}/${item.base_currency}`,
    );
    if (!pairs.includes(selectedPair.value)) {
      const firstPair = uniquePairsInfo.value[0];
      if (firstPair) selectCurrencyPair(firstPair);
      else selectedPair.value = "all";
    }
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : t("currencies.errors.load");
  } finally {
    loading.value = false;
  }
}

async function runLiveConversion() {
  if (
    !calcAmount.value ||
    calcAmount.value <= 0 ||
    !calcFrom.value ||
    !calcTo.value
  )
    return;
  calcLoading.value = true;
  calcError.value = "";
  try {
    const query = `amount=${encodeURIComponent(calcAmount.value)}&from=${encodeURIComponent(calcFrom.value)}&to=${encodeURIComponent(calcTo.value)}&date=${encodeURIComponent(calcDate.value)}`;
    calcResult.value = await api<FxConvertResult>(`/fx-rates/convert?${query}`);
  } catch (reason) {
    calcResult.value = null;
    calcError.value =
      reason instanceof Error
        ? reason.message
        : t("currencies.converter.error");
  } finally {
    calcLoading.value = false;
  }
}

async function fetchFromYahoo() {
  updatingYahoo.value = true;
  actionMessage.value = "";
  try {
    const result = await api<FetchFxRatesResult>("/fx-rates/fetch", {
      method: "POST",
    });
    actionMessage.value = t("currencies.notifications.updatedYahoo", {
      count: result.updated_count,
    });
    await loadRates();
    await runLiveConversion();
  } catch (reason) {
    actionMessage.value =
      reason instanceof Error
        ? reason.message
        : t("currencies.errors.updateYahoo");
  } finally {
    updatingYahoo.value = false;
  }
}

function openCreateDialog() {
  dialogMode.value = "create";
  dialogId.value = null;
  formQuoteCurrency.value = "USD";
  formBaseCurrency.value = "EUR";
  formRateDate.value = new Date().toISOString().slice(0, 10);
  formRate.value = "";
  formSource.value = "manual";
  dialogError.value = "";
  rateDialog.value?.showModal();
}

function openEditDialog(item: FxRateItem) {
  dialogMode.value = "edit";
  dialogId.value = item.id;
  formQuoteCurrency.value = item.quote_currency;
  formBaseCurrency.value = item.base_currency;
  formRateDate.value = item.rate_date;
  formRate.value = item.rate;
  formSource.value = item.source || "manual";
  dialogError.value = "";
  rateDialog.value?.showModal();
}

function closeRateDialog() {
  if (!dialogBusy.value) rateDialog.value?.close();
}

async function saveRate() {
  if (
    !formQuoteCurrency.value ||
    !formBaseCurrency.value ||
    !formRateDate.value ||
    !formRate.value
  )
    return;
  dialogBusy.value = true;
  dialogError.value = "";
  try {
    const payloadData: FxRatePayload = {
      quote_currency: formQuoteCurrency.value.trim().toUpperCase(),
      base_currency: formBaseCurrency.value.trim().toUpperCase(),
      rate_date: formRateDate.value,
      rate: Number(formRate.value),
      source: formSource.value.trim(),
    };
    if (dialogMode.value === "edit" && dialogId.value) {
      await api(`/fx-rates/${dialogId.value}`, json("PUT", payloadData));
    } else {
      await api("/fx-rates", json("POST", payloadData));
    }
    rateDialog.value?.close();
    actionMessage.value = t("currencies.notifications.saveSuccess");
    await loadRates();
    await runLiveConversion();
  } catch (reason) {
    dialogError.value =
      reason instanceof Error ? reason.message : t("currencies.errors.save");
  } finally {
    dialogBusy.value = false;
  }
}

function openDeleteDialog(item: FxRateItem) {
  targetDeleteRate.value = item;
  deleteError.value = "";
  deleteDialog.value?.showModal();
}

function closeDeleteDialog() {
  if (!deleteBusy.value) {
    deleteError.value = "";
    deleteDialog.value?.close();
    targetDeleteRate.value = null;
  }
}

async function confirmDeleteRate() {
  if (!targetDeleteRate.value) return;
  deleteBusy.value = true;
  deleteError.value = "";
  try {
    await api(`/fx-rates/${targetDeleteRate.value.id}?scope=pair`, {
      method: "DELETE",
    });
    deleteDialog.value?.close();
    targetDeleteRate.value = null;
    actionMessage.value = t("currencies.notifications.deleteSuccess");
    await loadRates();
    await runLiveConversion();
  } catch (reason) {
    deleteError.value =
      reason instanceof Error ? reason.message : t("currencies.errors.delete");
  } finally {
    deleteBusy.value = false;
  }
}

function swapConverterCurrencies() {
  const temp = calcFrom.value;
  calcFrom.value = calcTo.value;
  calcTo.value = temp;
  void runLiveConversion();
}

watch([calcAmount, calcFrom, calcTo, calcDate], () => {
  void runLiveConversion();
});

watch([selectedPair, fxChartRange], () => {
  void loadFxChart();
});

onMounted(async () => {
  await loadRates();
  await runLiveConversion();
});
</script>

<template>
  <section class="crypto-page currencies-page" aria-live="polite">
    <div
      v-if="loading"
      class="crypto-loading"
      :aria-label="t('currencies.loadingAria')"
    >
      <div />
      <div />
      <div />
    </div>

    <div v-else-if="error" class="overview-error" role="alert">
      <span aria-hidden="true">!</span>
      <div>
        <strong>{{ t("currencies.errors.loadTitle") }}</strong>
        <p>{{ error }}</p>
      </div>
      <button type="button" @click="loadRates">
        {{ t("currencies.actions.retry") }}
      </button>
    </div>

    <template v-else>
      <div class="crypto-top-grid">
        <article class="crypto-panel assets-panel currency-list-panel">
          <header class="crypto-panel-header">
            <div>
              <p class="section-label">
                {{ t("currencies.rates.listSection") }}
              </p>
              <h2>{{ t("currencies.rates.listTitle") }}</h2>
            </div>
            <div class="asset-header-actions">
              <button
                type="button"
                :disabled="!selectedFxRate"
                @click="selectedFxRate && openEditDialog(selectedFxRate)"
              >
                {{ t("currencies.rates.edit") }}
              </button>
              <button
                type="button"
                :disabled="
                  !selectedFxRate || selectedFxRate.scope === 'provider'
                "
                @click="selectedFxRate && openDeleteDialog(selectedFxRate)"
                style="color: var(--fz-danger)"
              >
                {{ t("currencies.rates.delete") }}
              </button>
              <button class="primary" type="button" @click="openCreateDialog">
                <span aria-hidden="true">+</span>
                {{ t("currencies.rates.add") }}
              </button>
              <button
                type="button"
                :disabled="updatingYahoo"
                @click="fetchFromYahoo"
                style="margin-left: 8px"
              >
                <span aria-hidden="true">↻</span>
                {{
                  updatingYahoo
                    ? t("currencies.rates.updating")
                    : t("currencies.rates.updateYahoo")
                }}
              </button>
            </div>
          </header>

          <div v-if="uniquePairsInfo.length" class="asset-table">
            <div class="asset-table-head" aria-hidden="true">
              <span>{{ t("currencies.rates.pair") }}</span
              ><span>{{ t("currencies.rates.rate") }}</span
              ><span>{{ t("currencies.rates.inverse") }}</span>
            </div>
            <button
              v-for="item in uniquePairsInfo"
              :key="`${item.quote_currency}/${item.base_currency}`"
              type="button"
              class="asset-row"
              :class="{
                active:
                  selectedPair ===
                  `${item.quote_currency}/${item.base_currency}`,
              }"
              @click="selectCurrencyPair(item)"
            >
              <span class="asset-identity">
                <i aria-hidden="true">⇄</i>
                <span>
                  <strong
                    >{{ item.quote_currency }} /
                    {{ item.base_currency }}</strong
                  >
                  <small>{{ formatDate(item.rate_date) }}</small>
                </span>
              </span>
              <span class="asset-cell">
                <strong>{{ formatRawNumber(item.rate, 6) }}</strong>
                <small>{{ t("currencies.rates.direct") }}</small>
              </span>
              <span class="asset-cell">
                <strong>{{
                  formatRawNumber(inverseRate(item.rate), 6)
                }}</strong>
                <small>{{ t("currencies.rates.inverseLabel") }}</small>
              </span>
            </button>
          </div>
          <div v-else class="crypto-empty">
            <strong>{{ t("currencies.rates.noRates") }}</strong>
            <p>{{ t("currencies.rates.noRatesHint") }}</p>
          </div>
        </article>

        <article class="crypto-panel converter-panel">
          <header class="crypto-panel-header">
            <div>
              <p class="section-label">
                {{ t("currencies.converter.section") }}
              </p>
              <h2>{{ t("currencies.converter.title") }}</h2>
            </div>
            <span class="crypto-live"
              ><i /> {{ t("currencies.converter.live") }}</span
            >
          </header>

          <form class="fx-converter" @submit.prevent="runLiveConversion">
            <div class="fx-converter-body">
              <div class="fx-input-group">
                <label class="fx-label">{{
                  t("currencies.converter.amount")
                }}</label>
                <div class="fx-input-row">
                  <input
                    v-model.number="calcAmount"
                    type="number"
                    step="any"
                    min="0"
                    required
                    class="fx-amount"
                  />
                  <input
                    v-model="calcFrom"
                    class="fx-currency"
                    maxlength="3"
                    minlength="3"
                    pattern="[A-Za-z]{3}"
                    required
                  />
                </div>
              </div>

              <div class="fx-divider">
                <button
                  type="button"
                  class="fx-swap"
                  :title="t('currencies.converter.swapCurrencies')"
                  :aria-label="t('currencies.converter.swapCurrencies')"
                  @click="swapConverterCurrencies"
                >
                  <svg
                    viewBox="0 0 24 24"
                    width="20"
                    height="20"
                    stroke="currentColor"
                    stroke-width="2"
                    fill="none"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <path
                      d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"
                    />
                  </svg>
                </button>
                <div class="fx-rate-hint" v-if="calcResult">
                  1 {{ calcResult.from_currency }} =
                  {{ formatRawNumber(calcResult.rate, 6) }}
                  {{ calcResult.to_currency }}
                </div>
              </div>

              <div class="fx-input-group is-result">
                <label class="fx-label">{{
                  t("currencies.converter.result")
                }}</label>
                <div class="fx-input-row">
                  <div v-if="calcLoading" class="fx-amount is-loading">...</div>
                  <div v-else-if="calcError" class="fx-amount is-error">!</div>
                  <div v-else class="fx-amount result-amount">
                    {{
                      calcResult
                        ? formatRawNumber(calcResult.converted_amount)
                        : "0.00"
                    }}
                  </div>
                  <input
                    v-model="calcTo"
                    class="fx-currency"
                    maxlength="3"
                    minlength="3"
                    pattern="[A-Za-z]{3}"
                    required
                  />
                </div>
              </div>
            </div>

            <div class="fx-converter-footer">
              <label class="fx-date-picker">
                <span>{{ t("currencies.converter.date") }}</span>
                <input v-model="calcDate" type="date" required />
              </label>
              <div class="fx-source-info" v-if="calcResult">
                <span
                  class="source-tag"
                  :class="calcResult.source === 'manual' ? 'manual' : 'yahoo'"
                  >{{
                    calcResult.source === "manual"
                      ? t("currencies.rates.sourceManual")
                      : t("currencies.rates.sourceYahoo")
                  }}</span
                >
              </div>
            </div>
          </form>
        </article>
      </div>

      <article v-if="selectedFxRate" class="crypto-panel fx-chart-panel">
        <header class="fx-chart-header">
          <div>
            <p class="section-label">{{ t("currencies.chart.section") }}</p>
            <h2>
              {{ t("currencies.chart.title") }} ·
              {{ selectedFxRate.quote_currency }}/{{
                selectedFxRate.base_currency
              }}
            </h2>
            <p class="fx-chart-subtitle">
              {{
                t("currencies.chart.subtitle", {
                  from: selectedFxRate.quote_currency,
                  to: selectedFxRate.base_currency,
                })
              }}
            </p>
          </div>
          <div class="fx-chart-controls">
            <div v-if="latestFxChartPoint" class="fx-chart-latest">
              <span>{{ t("currencies.chart.latest") }}</span>
              <strong
                >{{ formatRawNumber(latestFxChartPoint.rate, 6) }}
                {{ selectedFxRate.base_currency }}</strong
              >
              <small>{{
                t("currencies.chart.latestDate", {
                  date: formatDate(latestFxChartPoint.fecha),
                })
              }}</small>
            </div>
            <div
              class="fx-range-control"
              :aria-label="t('currencies.chart.rangeAria')"
            >
              <button
                v-for="rangeOption in fxChartRanges"
                :key="rangeOption"
                type="button"
                :class="{ active: fxChartRange === rangeOption }"
                :aria-pressed="fxChartRange === rangeOption"
                :aria-label="
                  rangeOption === 'custom'
                    ? t('currencies.chart.customPeriod')
                    : undefined
                "
                :title="
                  rangeOption === 'custom'
                    ? t('currencies.chart.customPeriod')
                    : undefined
                "
                @click="selectFxChartRange(rangeOption)"
              >
                {{
                  rangeOption === "custom"
                    ? t("currencies.chart.rangeCustom")
                    : t(`currencies.chart.range${rangeOption}`)
                }}
              </button>
            </div>
          </div>
        </header>
        <div v-if="fxChartLoading" class="fx-chart-state">
          {{ t("currencies.chart.loading") }}
        </div>
        <div
          v-else-if="fxChartError"
          class="fx-chart-state error-state"
          role="alert"
        >
          <strong>{{ t("currencies.chart.unavailable") }}</strong>
          <p>{{ fxChartError }}</p>
          <button type="button" @click="loadFxChart">
            {{ t("currencies.actions.retry") }}
          </button>
        </div>
        <CurrencyRateChart
          v-else-if="fxChart?.data.length"
          :points="fxChart.data"
          :from-currency="fxChart.from_currency"
          :to-currency="fxChart.to_currency"
        />
        <div v-else class="fx-chart-state">
          {{ t("currencies.chart.empty") }}
        </div>
      </article>
    </template>

    <dialog
      ref="fxCalendarDialog"
      class="currency-dialog fx-calendar-dialog"
      aria-labelledby="fx-calendar-title"
      @cancel.prevent="closeFxCalendar"
    >
      <form @submit.prevent="applyFxCustomRange">
        <header class="currency-dialog-header">
          <div>
            <p class="section-label">
              {{ t("currencies.chart.customPeriod") }}
            </p>
            <h2 id="fx-calendar-title">
              {{ t("currencies.chart.selectDates") }}
            </h2>
          </div>
        </header>
        <div class="fx-calendar-fields">
          <label>
            <span>{{ t("currencies.chart.fromDate") }}</span>
            <input
              v-model="fxDraftStart"
              type="date"
              :max="fxDraftEnd"
              required
            />
          </label>
          <span aria-hidden="true">→</span>
          <label>
            <span>{{ t("currencies.chart.toDate") }}</span>
            <input
              v-model="fxDraftEnd"
              type="date"
              :min="fxDraftStart"
              required
            />
          </label>
        </div>
        <footer class="currency-dialog-actions">
          <button type="button" @click="closeFxCalendar">
            {{ t("currencies.chart.cancel") }}
          </button>
          <button class="primary" type="submit" :disabled="!fxCustomRangeValid">
            {{ t("currencies.chart.applyPeriod") }}
          </button>
        </footer>
      </form>
    </dialog>

    <!-- Create / Edit Dialog -->
    <dialog ref="rateDialog" class="currency-dialog">
      <form @submit.prevent="saveRate">
        <header class="currency-dialog-header">
          <div>
            <p class="section-label">{{ t("currencies.rates.section") }}</p>
            <h2>
              {{
                dialogMode === "edit"
                  ? t("currencies.dialog.editTitle")
                  : t("currencies.dialog.addTitle")
              }}
            </h2>
          </div>
        </header>

        <div class="currency-dialog-fields">
          <label>
            <span>{{ t("currencies.dialog.quoteCurrency") }}</span>
            <input
              v-model="formQuoteCurrency"
              class="currency-code-input"
              maxlength="3"
              minlength="3"
              pattern="[A-Za-z]{3}"
              required
            />
          </label>
          <label>
            <span>{{ t("currencies.dialog.baseCurrency") }}</span>
            <input
              v-model="formBaseCurrency"
              class="currency-code-input"
              maxlength="3"
              minlength="3"
              pattern="[A-Za-z]{3}"
              required
            />
          </label>
          <label>
            <span>{{ t("currencies.dialog.rate") }}</span>
            <input
              v-model.number="formRate"
              type="number"
              step="any"
              min="0.000000000001"
              required
            />
          </label>
          <label>
            <span>{{ t("currencies.dialog.date") }}</span>
            <input v-model="formRateDate" type="date" required />
          </label>
        </div>

        <p v-if="dialogError" class="dialog-error">{{ dialogError }}</p>

        <footer class="currency-dialog-actions">
          <button type="button" @click="closeRateDialog">
            {{ t("currencies.dialog.cancel") }}
          </button>
          <button class="primary" type="submit" :disabled="dialogBusy">
            {{
              dialogBusy
                ? t("currencies.dialog.saving")
                : t("currencies.dialog.save")
            }}
          </button>
        </footer>
      </form>
    </dialog>

    <!-- Delete Confirm Dialog -->
    <dialog ref="deleteDialog" class="currency-dialog currency-delete-dialog">
      <form @submit.prevent="confirmDeleteRate">
        <header class="currency-dialog-header">
          <div>
            <p class="section-label">{{ t("currencies.rates.section") }}</p>
            <h2>{{ t("currencies.deleteDialog.title") }}</h2>
          </div>
        </header>

        <div v-if="targetDeleteRate" class="delete-dialog-body">
          <div class="delete-rate-card">
            <i aria-hidden="true">⇄</i>
            <div>
              <strong
                >{{ targetDeleteRate.quote_currency }} /
                {{ targetDeleteRate.base_currency }}</strong
              >
              <small>{{ formatDate(targetDeleteRate.rate_date) }}</small>
            </div>
            <b>{{ formatRawNumber(targetDeleteRate.rate, 6) }}</b>
          </div>
          <p class="delete-hint">
            {{
              t("currencies.deleteDialog.confirmText", {
                pair: `${targetDeleteRate.quote_currency}/${targetDeleteRate.base_currency}`,
                date: formatDate(targetDeleteRate.rate_date),
              })
            }}
          </p>
        </div>

        <p v-if="deleteError" class="dialog-error" role="alert">
          {{ deleteError }}
        </p>

        <footer class="currency-dialog-actions">
          <button type="button" @click="closeDeleteDialog">
            {{ t("currencies.deleteDialog.cancel") }}
          </button>
          <button class="danger" type="submit" :disabled="deleteBusy">
            {{
              deleteBusy
                ? t("currencies.deleteDialog.deleting")
                : t("currencies.deleteDialog.delete")
            }}
          </button>
        </footer>
      </form>
    </dialog>
  </section>
</template>

<style scoped>
.crypto-page {
  width: min(100%, 1440px);
  margin: 0 auto;
  padding: 8px 48px 56px;
}
.currencies-page {
  --currency-accent: #3e82d8;
  --fz-accent: var(--currency-accent);
  --fz-accent-soft: color-mix(
    in srgb,
    var(--currency-accent) 12%,
    var(--fz-surface)
  );
}
:global(.app-shell[data-theme="dark"]) .currencies-page {
  --currency-accent: #74a9f5;
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
.converter-panel,
.assets-panel {
  padding: 24px;
}
.converter-panel {
  display: flex;
  flex-direction: column;
}
.currency-list-panel {
  min-height: 330px;
}
@media (min-width: 1181px) {
  .currency-list-panel {
    min-height: 430px;
  }
}
.fx-chart-panel {
  margin-top: 20px;
  padding: 24px;
}
.fx-chart-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
}
.fx-chart-header h2 {
  margin: 0;
  color: var(--fz-ink);
  font-size: 20px;
  font-weight: 730;
  letter-spacing: -0.03em;
}
.fx-chart-subtitle {
  margin: 5px 0 0;
  color: var(--fz-muted);
  font-size: 11px;
  line-height: 1.45;
}
.fx-chart-controls {
  display: flex;
  align-items: flex-end;
  gap: 14px;
}
.fx-chart-latest {
  display: grid;
  gap: 2px;
  min-width: max-content;
  text-align: right;
}
.fx-chart-latest span,
.fx-chart-latest small {
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 650;
}
.fx-chart-latest strong {
  color: var(--fz-ink);
  font-size: 15px;
  font-weight: 760;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.025em;
}
.fx-range-control {
  display: inline-flex;
  padding: 3px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
}
.fx-range-control button {
  min-width: 33px;
  padding: 6px 7px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 760;
  cursor: pointer;
}
.fx-range-control button:hover {
  color: var(--fz-ink);
}
.fx-range-control button.active {
  background: var(--fz-surface);
  box-shadow: 0 1px 3px color-mix(in srgb, var(--fz-ink) 13%, transparent);
  color: var(--fz-accent);
}
.fx-range-control button:focus-visible,
.fx-chart-state button:focus-visible {
  outline: 2px solid var(--fz-accent);
  outline-offset: 2px;
}
.fx-chart-state {
  min-height: 320px;
  display: grid;
  place-content: center;
  gap: 8px;
  color: var(--fz-muted);
  font-size: 12px;
  text-align: center;
}
.fx-chart-state.error-state strong {
  color: var(--fz-ink);
}
.fx-chart-state.error-state p {
  max-width: 440px;
  margin: 0;
}
.fx-chart-state button {
  justify-self: center;
  padding: 7px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-ink);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}
.fx-chart-state button:hover {
  border-color: var(--fz-accent);
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
  font-size: 11px;
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
  font-size: 14px;
}
.asset-table {
  margin-top: 19px;
  overflow-x: auto;
  scrollbar-width: thin;
}
.asset-table-head,
.asset-row {
  min-width: 100%;
  display: grid;
  grid-template-columns: minmax(108px, 1.2fr) minmax(80px, 1fr) minmax(
      80px,
      1fr
    );
  gap: 8px;
  align-items: center;
}
.asset-table-head {
  padding: 0 8px 8px;
  color: var(--fz-muted);
  font-size: 11px;
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
  background: color-mix(in srgb, var(--fz-accent) 14%, var(--fz-surface));
  color: var(--fz-accent);
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
  font-size: 12px;
  font-weight: 760;
}
.asset-identity small {
  overflow: hidden;
  margin-top: 2px;
  color: var(--fz-muted);
  font-size: 10px;
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
  font-size: 10px;
}
.asset-cell strong {
  overflow: hidden;
  font-size: 11px;
  font-weight: 710;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.crypto-panel-header,
.movements-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.crypto-panel h2,
.movements-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 730;
  letter-spacing: -0.03em;
}
.section-label {
  margin: 0 0 5px;
  color: var(--fz-muted);
  font-size: 10px;
  line-height: 1.4;
  font-weight: 720;
  letter-spacing: 0.035em;
}
.crypto-live {
  padding: 6px 9px;
  border-radius: 999px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  font-size: 11px;
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
  font-size: 11px;
}
.crypto-kpi-grid strong {
  font-size: 16px;
  font-weight: 740;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.025em;
  color: var(--fz-ink);
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
  font-size: 27px;
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
.crypto-actions {
  display: flex;
  align-items: center;
  gap: 7px;
}
.crypto-actions > button {
  padding: 8px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 690;
  cursor: pointer;
}
.crypto-actions > button:hover {
  border-color: var(--fz-accent);
  color: var(--fz-ink);
}
.crypto-actions > button:disabled {
  opacity: 0.55;
  cursor: wait;
}

.movements-panel {
  margin-top: 20px;
  padding: 24px;
  overflow: hidden;
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
  font-size: 11px;
  vertical-align: 2px;
}
.movement-filters {
  display: flex;
  align-items: stretch;
  gap: 9px;
}
.movement-filters .add-movement {
  min-height: 49px;
  padding: 8px 13px;
  border: 1px solid var(--fz-accent);
  border-radius: 12px;
  background: var(--fz-accent);
  color: #f4fff9;
  font-size: 11px;
  font-weight: 720;
  white-space: nowrap;
  cursor: pointer;
}
.movement-filters .add-movement span {
  margin-right: 3px;
  font-size: 12px;
}
.movement-symbol-filter {
  min-height: 49px;
  display: grid;
  align-content: center;
  gap: 2px;
  border: 1px solid var(--fz-line);
  border-radius: 12px;
  background: var(--fz-surface-soft);
  min-width: 190px;
  padding: 7px 11px;
}
.movement-symbol-filter > span {
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 680;
}
.movement-symbol-filter select {
  width: 100%;
  padding: 0 22px 0 0;
  border: 0;
  background-color: transparent;
  color: var(--fz-ink);
  font-size: 12px;
  font-weight: 720;
  cursor: pointer;
}
.movement-symbol-filter:hover {
  border-color: color-mix(in srgb, var(--fz-accent) 70%, var(--fz-line));
}
.search-filter {
  min-height: 49px;
  display: flex;
  align-items: center;
  border: 1px solid var(--fz-line);
  border-radius: 12px;
  background: var(--fz-surface-soft);
  padding: 7px 11px;
}
.search-filter input {
  width: 100%;
  border: 0;
  background-color: transparent;
  color: var(--fz-ink);
  font-size: 12px;
  font-weight: 500;
  outline: none;
}
.search-filter input::placeholder {
  color: var(--fz-muted);
}
.search-filter:focus-within {
  border-color: var(--fz-accent);
}

.movement-table {
  margin-top: 20px;
}
.movement-table-head,
.movement-row {
  display: grid;
  grid-template-columns: 120px 2fr 1fr 1.5fr 1.5fr 100px;
  gap: 10px;
  align-items: center;
}
.movement-table-head {
  padding: 0 12px 9px;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 710;
}
.movement-table-head span:nth-child(n + 4) {
  text-align: right;
}
.movement-row {
  min-height: 70px;
  padding: 10px 12px;
  border-top: 1px solid var(--fz-line);
  transition: background 0.16s ease;
}
.movement-row:hover {
  background: var(--fz-surface-soft);
}
.movement-row time {
  color: var(--fz-muted);
  font-size: 11px;
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
.movement-kind.is-neutral > i {
  color: #f7931a;
}
.movement-kind > span {
  display: grid;
  gap: 2px;
}
.movement-kind strong {
  overflow: hidden;
  color: var(--fz-ink);
  font-size: 12px;
  font-weight: 720;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.movement-kind small {
  color: var(--fz-muted);
  font-size: 10px;
}
.movement-number {
  color: var(--fz-ink);
  font-size: 11px;
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
  font-size: 11px;
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
.movement-row-actions .delete:hover {
  border-color: var(--fz-negative);
  color: var(--fz-negative);
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

.crypto-empty {
  min-height: 190px;
  display: grid;
  place-content: center;
  text-align: center;
  color: var(--fz-muted);
  font-size: 11px;
}
.crypto-empty strong {
  color: var(--fz-ink);
  font-size: 13px;
}
.crypto-empty p {
  margin: 5px 0 12px;
}

@keyframes skeleton {
  0% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0 50%;
  }
}

/* Converter: a compact transfer between two amounts, using the same
   data-card language as the saved-rates panel. */
.fx-converter {
  min-height: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 19px;
}

.fx-converter-body {
  min-height: 0;
  flex: 1;
  display: grid;
  grid-template-rows: minmax(100px, 1fr) 34px minmax(100px, 1fr);
  gap: 6px;
}

.fx-input-group {
  min-width: 0;
  padding: 16px 15px;
  display: grid;
  align-content: center;
  border: 1px solid var(--fz-line);
  border-radius: 12px;
  background: var(--fz-surface-soft);
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease,
    background 0.16s ease;
}

.fx-input-group:focus-within {
  border-color: var(--fz-accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 13%, transparent);
  background: var(--fz-surface);
}

.fx-input-group.is-result {
  background: linear-gradient(
    135deg,
    var(--fz-accent-wash),
    color-mix(in srgb, var(--fz-accent) 5%, var(--fz-surface))
  );
  border-color: color-mix(in srgb, var(--fz-accent) 26%, var(--fz-line));
}

.fx-label {
  display: block;
  margin-bottom: 7px;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 720;
  letter-spacing: 0.035em;
}

.fx-input-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.fx-amount {
  min-width: 0;
  width: 100%;
  padding: 0;
  flex: 1;
  border: none;
  background: transparent;
  color: var(--fz-ink);
  font-size: 25px;
  font-weight: 740;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.045em;
  line-height: 1.15;
  outline: none;
}

.fx-amount.result-amount {
  color: var(--fz-ink);
}

.fx-amount.is-loading,
.fx-amount.is-error {
  color: var(--fz-muted);
}

.fx-currency {
  width: 54px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--fz-ink);
  font-size: 14px;
  font-weight: 780;
  letter-spacing: 0.025em;
  outline: none;
  text-transform: uppercase;
  text-align: right;
}

.fx-currency:focus {
  color: var(--fz-accent);
}

.fx-divider {
  min-height: 34px;
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  align-items: center;
  gap: 9px;
  padding: 0 5px;
}

.fx-swap {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface);
  cursor: pointer;
  color: var(--fz-muted);
  transition:
    border-color 0.16s ease,
    color 0.16s ease,
    transform 0.2s ease;
}

.fx-swap:hover {
  color: var(--fz-accent);
  border-color: var(--fz-accent);
  transform: rotate(180deg);
}

.fx-rate-hint {
  min-width: 0;
  overflow: hidden;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 690;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fx-converter-footer {
  flex: 0 0 auto;
  min-height: 42px;
  padding-top: 9px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  border-top: 1px solid var(--fz-line);
}

.fx-date-picker {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  padding: 0;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 680;
}

.fx-date-picker input {
  min-width: 0;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--fz-ink);
  outline: none;
  font-family: inherit;
  font-size: 11px;
  font-weight: 720;
  cursor: pointer;
}

.fx-source-info {
  display: flex;
  align-items: center;
}

.source-tag {
  display: inline-block;
  padding: 4px 7px;
  border-radius: 999px;
  font-size: 9px;
  font-weight: 760;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.source-tag.manual {
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
}
.source-tag.yahoo {
  background: color-mix(in srgb, var(--fz-accent) 15%, transparent);
  color: var(--fz-accent);
}
.positive {
  color: var(--fz-accent);
}
.action-msg {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--fz-accent);
  margin-top: 0.2rem;
}
.currency-dialog {
  width: min(540px, calc(100vw - 32px));
  margin: auto;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--fz-line);
  border-radius: 20px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 28px 80px rgba(15, 31, 22, 0.22);
}
.currency-dialog::backdrop {
  background: rgba(6, 11, 8, 0.68);
  backdrop-filter: blur(5px);
}
.currency-dialog form {
  padding: 0;
}
.currency-dialog-header {
  min-height: 88px;
  padding: 22px 24px 18px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  border-bottom: 1px solid var(--fz-line);
  background: linear-gradient(
    110deg,
    color-mix(in srgb, var(--fz-accent) 7%, transparent),
    transparent 58%
  );
}
.currency-dialog-header .section-label {
  margin: 0 0 5px;
  color: var(--fz-accent);
  font-size: 10px;
  font-weight: 760;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}
.currency-dialog-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 740;
  letter-spacing: -0.035em;
}
.currency-dialog-header button {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  padding: 0;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface);
  color: var(--fz-muted);
  font-size: 19px;
  line-height: 1;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    color 0.16s ease,
    background 0.16s ease;
}
.currency-dialog-header button:hover {
  border-color: var(--fz-accent);
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
}
.currency-dialog-fields {
  margin: 20px 24px 0;
  padding: 16px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  border: 1px solid var(--fz-line);
  border-radius: 14px;
  background: var(--fz-surface-soft);
}
.currency-dialog-fields label {
  min-width: 0;
  display: grid;
  gap: 7px;
}
.currency-dialog-fields label > span {
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 680;
}
.currency-dialog-fields input {
  width: 100%;
  min-width: 0;
  height: 42px;
  padding: 0 11px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font-size: 12px;
  font-weight: 690;
  outline: none;
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease;
}
.currency-dialog-fields input:focus {
  border-color: var(--fz-accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 13%, transparent);
}
.currency-dialog-fields .currency-code-input {
  font-size: 14px;
  font-weight: 780;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.fx-calendar-fields {
  margin: 20px 24px 0;
  padding: 16px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: end;
  gap: 12px;
  border: 1px solid var(--fz-line);
  border-radius: 14px;
  background: var(--fz-surface-soft);
}
.fx-calendar-fields label {
  min-width: 0;
  display: grid;
  gap: 7px;
}
.fx-calendar-fields label span {
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 680;
}
.fx-calendar-fields > span {
  padding-bottom: 12px;
  color: var(--fz-muted);
}
.fx-calendar-fields input {
  width: 100%;
  min-width: 0;
  height: 42px;
  padding: 0 11px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font-family: inherit;
  font-size: 12px;
  font-weight: 690;
  outline: none;
}
.fx-calendar-fields input:focus {
  border-color: var(--fz-accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 13%, transparent);
}
.fx-calendar-dialog .currency-dialog-actions button:disabled {
  cursor: not-allowed;
}
.currency-dialog-actions {
  margin-top: 20px;
  padding: 16px 24px 20px;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  border-top: 1px solid var(--fz-line);
}
.currency-dialog-actions button {
  min-height: 38px;
  padding: 8px 13px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 11px;
  font-weight: 720;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    color 0.16s ease,
    background 0.16s ease;
}
.currency-dialog-actions button:hover:not(:disabled) {
  border-color: var(--fz-accent);
  color: var(--fz-ink);
}
.currency-dialog-actions .primary {
  border-color: var(--fz-accent);
  background: var(--fz-accent);
  color: #f4fff9;
}
.currency-dialog-actions .danger {
  border-color: color-mix(in srgb, var(--fz-negative) 45%, var(--fz-line));
  background: color-mix(in srgb, var(--fz-negative) 8%, transparent);
  color: var(--fz-negative);
}
.currency-dialog-actions .danger:hover:not(:disabled) {
  border-color: var(--fz-negative);
  background: var(--fz-negative);
  color: #fff;
}
.currency-dialog-actions button:disabled {
  cursor: wait;
  opacity: 0.58;
}
.dialog-error {
  margin: 14px 24px 0;
  padding: 10px 11px;
  border: 1px solid color-mix(in srgb, var(--fz-negative) 24%, var(--fz-line));
  border-radius: 10px;
  background: color-mix(in srgb, var(--fz-negative) 7%, transparent);
  color: var(--fz-negative);
  font-size: 11px;
  line-height: 1.4;
}
.currency-delete-dialog .currency-dialog-header {
  background: linear-gradient(
    110deg,
    color-mix(in srgb, var(--fz-negative) 8%, transparent),
    transparent 58%
  );
}
.currency-delete-dialog .currency-dialog-header .section-label {
  color: var(--fz-negative);
}
.delete-dialog-body {
  padding: 22px 24px 0;
}
.delete-rate-card {
  padding: 13px;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--fz-line);
  border-radius: 13px;
  background: var(--fz-surface-soft);
}
.delete-rate-card > i {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: color-mix(in srgb, var(--fz-negative) 11%, transparent);
  color: var(--fz-negative);
  font-size: 13px;
  font-style: normal;
  font-weight: 820;
}
.delete-rate-card > div {
  min-width: 0;
  display: grid;
  gap: 2px;
}
.delete-rate-card strong {
  overflow: hidden;
  font-size: 13px;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.delete-rate-card small {
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 650;
}
.delete-rate-card b {
  color: var(--fz-ink);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.delete-hint {
  margin: 14px 0 0;
  padding: 0;
  color: var(--fz-muted);
  font-size: 12px;
  line-height: 1.55;
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
}

@media (max-width: 768px) {
  .crypto-page {
    padding: 4px 18px 32px;
  }
  .converter-panel,
  .kpi-panel,
  .movements-panel {
    padding: 19px 17px;
    border-radius: 18px;
  }
  .fx-chart-panel {
    padding: 19px 17px;
    border-radius: 18px;
  }
  .fx-chart-header {
    display: grid;
    gap: 14px;
  }
  .fx-chart-controls {
    align-items: center;
    justify-content: space-between;
  }
  .fx-chart-state {
    min-height: 260px;
  }
  .fx-divider {
    margin: 1px 0;
  }
  .movement-filters {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }
  .movement-symbol-filter,
  .search-filter,
  .movement-filters .add-movement {
    width: 100%;
    min-width: 0;
  }

  .movement-table-head {
    display: none;
  }
  .movement-row {
    grid-template-columns: 1fr;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 15px 4px;
    align-items: flex-start;
  }
  .movement-row time {
    width: 100%;
    padding-bottom: 7px;
    border-bottom: 1px dashed var(--fz-line);
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
    width: 100%;
    justify-content: flex-start;
    margin-top: 10px;
  }
  .currency-dialog-header {
    min-height: 80px;
    padding: 19px 18px 16px;
  }
  .currency-dialog-fields {
    margin: 16px 18px 0;
    padding: 13px;
    grid-template-columns: 1fr;
  }
  .fx-calendar-fields {
    margin: 16px 18px 0;
    padding: 13px;
    grid-template-columns: 1fr;
  }
  .fx-calendar-fields > span {
    display: none;
  }
  .currency-dialog-actions {
    margin-top: 16px;
    padding: 14px 18px 18px;
  }
  .delete-dialog-body {
    padding: 18px 18px 0;
  }
  .dialog-error {
    margin-inline: 18px;
  }
}
</style>
