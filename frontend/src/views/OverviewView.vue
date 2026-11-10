<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { api } from "../api/client";
import AllocationPie from "../components/AllocationPie.vue";
import LineChart from "../components/LineChart.vue";
import type { LineChartSeries } from "../components/LineChart.vue";
import MonthlyVariationChart from "../components/MonthlyVariationChart.vue";
import NavIcon from "../components/NavIcon.vue";
import type {
  NetWorthPoint,
  RealEstateInvestment,
  Summary,
  SummarySourceKey,
} from "../types/api";

type Period = "6m" | "1y" | "2y" | "all";
type PnlMode = "include" | "exclude";

const { t, n, d, locale } = useI18n();
const summarySourcesUpdatedEvent = "finanzr:summary-sources-updated";

const summary = ref<Summary | null>(null);
const history = ref<NetWorthPoint[]>([]);
const crowdfundingProjects = ref<RealEstateInvestment[]>([]);
const loading = ref(true);
const error = ref("");
const sourceInfoOpen = ref(false);
const period = ref<Period>("2y");
const pnlMode = ref<PnlMode>("include");
const selectedVariationMonth = ref<string | null>(null);

const periods = computed<
  Array<{ key: Period; label: string; points?: number }>
>(() => [
  { key: "6m", label: t("overview.periods.sixMonths"), points: 7 },
  { key: "1y", label: t("overview.periods.oneYear"), points: 13 },
  { key: "2y", label: t("overview.periods.twoYears"), points: 25 },
  { key: "all", label: t("overview.periods.all") },
]);

const periodLabel = computed(
  () => periods.value.find((item) => item.key === period.value)?.label ?? "",
);
const visibleHistory = computed(() => {
  const points = periods.value.find(
    (item) => item.key === period.value,
  )?.points;
  return points ? history.value.slice(-points) : history.value;
});
const chartLabels = computed(() =>
  visibleHistory.value.map((item) => {
    const [year, month] = item.fecha.split("-").map(Number);
    return new Intl.DateTimeFormat(locale.value, {
      month: "short",
      year: "2-digit",
    })
      .format(new Date(year, month - 1, 1))
      .replace(".", "");
  }),
);
const startValue = computed(
  () => visibleHistory.value[0]?.total ?? summary.value?.net_worth ?? 0,
);
const currentValue = computed(
  () => visibleHistory.value.at(-1)?.total ?? summary.value?.net_worth ?? 0,
);
const periodChange = computed(() => {
  if (visibleHistory.value.length > 1)
    return currentValue.value - startValue.value;
  return summary.value?.net_worth_change ?? 0;
});
const periodChangePercent = computed(() =>
  startValue.value ? periodChange.value / Math.abs(startValue.value) : 0,
);
const allocation = computed(() => {
  if (!summary.value) return [];
  const items = summary.value.source_breakdown?.length
    ? summary.value.source_breakdown.map((item) => ({
        ...item,
        label: t(`overview.sources.${item.key}`),
        color: sourceColor(item.key),
      }))
    : [
        {
          key: "savings" as const,
          included: true,
          label: t("overview.allocation.savings"),
          value: summary.value.total_savings,
          color: "var(--fz-accent)",
        },
        {
          key: "manual_investments" as const,
          included: true,
          label: t("overview.allocation.investments"),
          value: summary.value.total_investments,
          color: sourceColor("manual_investments"),
        },
        {
          key: "crowdfunding" as const,
          included: true,
          label: t("overview.allocation.realEstate"),
          value: summary.value.total_real_estate,
          color: sourceColor("crowdfunding"),
        },
      ];
  const visibleItems = items.filter((item) => item.included);
  const total = visibleItems.reduce(
    (sum, item) => sum + Math.max(item.value, 0),
    0,
  );
  return visibleItems.map((item) => ({
    ...item,
    share: total > 0 ? Math.max(item.value, 0) / total : 0,
  }));
});
const activeSourceKeys = computed<SummarySourceKey[]>(() => {
  const breakdown = summary.value?.source_breakdown;
  if (breakdown?.length)
    return breakdown.filter((item) => item.included).map((item) => item.key);
  return (
    summary.value?.summary_sources ?? [
      "savings",
      "manual_investments",
      "crowdfunding",
    ]
  );
});
const netWorthSourceCopy = computed(() => {
  const keys = activeSourceKeys.value;
  if (keys.length === 0) return t("overview.netWorthSourceEmpty");
  const legacy = ["savings", "manual_investments", "crowdfunding"];
  if (
    keys.length === legacy.length &&
    keys.every((key, index) => key === legacy[index])
  ) {
    return t("overview.netWorthSource");
  }
  const labels = keys.map((key) => t(`overview.sources.${key}`)).join(", ");
  return t("overview.netWorthSourceDynamic", { sources: labels });
});
const monthlyDescriptionCopy = computed(() =>
  t("overview.monthly.descriptionDynamic", {
    sources: activeSourceKeys.value
      .map((key) => t(`overview.sources.${key}`))
      .join(", "),
    period: periodLabel.value,
  }),
);
function sourceColor(key: SummarySourceKey) {
  const colors: Record<SummarySourceKey, string> = {
    savings: "var(--fz-source-savings)",
    manual_investments: "var(--fz-source-manual-investments)",
    funds: "var(--fz-source-funds)",
    stocks: "var(--fz-source-stocks)",
    crypto: "var(--fz-source-crypto)",
    crowdfunding: "var(--fz-source-crowdfunding)",
    manual_assets: "var(--fz-source-manual-assets)",
  };
  return colors[key];
}
function historicalSourceValue(point: NetWorthPoint, key: SummarySourceKey) {
  const explicitValue = point.source_totals?.[key];
  if (explicitValue !== undefined) return explicitValue;
  if (key === "savings") return point.ahorro;
  if (key === "manual_investments") return point.balances;
  if (key === "crowdfunding") return point.inversiones - point.balances;
  return 0;
}
const trendSeries = computed<Array<LineChartSeries & { currentValue: number }>>(
  () =>
    activeSourceKeys.value
      .map((key) => {
        const values = visibleHistory.value.map((point) =>
          historicalSourceValue(point, key),
        );
        return {
          key,
          label: t(`overview.sources.${key}`),
          color: sourceColor(key),
          values,
          currentValue: values.at(-1) ?? 0,
        };
      })
      .filter((item) => item.values.some((value) => value !== 0)),
);
const biggestAllocation = computed(
  () => [...allocation.value].sort((a, b) => b.share - a.share)[0],
);
const includesCrowdfunding = computed(() =>
  activeSourceKeys.value.includes("crowdfunding"),
);
const upcomingCrowdfundingProject = computed(() => {
  if (!includesCrowdfunding.value) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const deadline = new Date(today);
  deadline.setMonth(deadline.getMonth() + 3);
  return (
    crowdfundingProjects.value
      .filter((item) => item.status === "active")
      .filter((item) => item.maturity_date !== null)
      .map((item) => ({
        item,
        maturity: new Date(`${item.maturity_date!.slice(0, 10)}T00:00:00`),
      }))
      .filter(
        ({ item, maturity }) =>
          item.initial_capital > item.returned_capital &&
          Number.isFinite(maturity.getTime()) &&
          maturity >= today &&
          maturity <= deadline,
      )
      .sort((a, b) => a.maturity.getTime() - b.maturity.getTime())[0] ?? null
  );
});
const upcomingCrowdfundingDate = computed(() =>
  upcomingCrowdfundingProject.value
    ? d(upcomingCrowdfundingProject.value.maturity, "short")
    : "",
);
const monthlyVariationPoints = computed(() =>
  visibleHistory.value.slice(1).map((current, index) => {
    const previous = visibleHistory.value[index];
    const savingsChange = current.ahorro - previous.ahorro;
    const withPnl = current.total - previous.total;
    const withoutPnl = savingsChange + current.inv_aportes;
    return {
      fecha: current.fecha,
      withPnl,
      withoutPnl,
    };
  }),
);
const monthlyVariationLabels = computed(() =>
  monthlyVariationPoints.value.map((item) => {
    const [year, month] = item.fecha.split("-").map(Number);
    return new Intl.DateTimeFormat(locale.value, {
      month: "short",
      year: "2-digit",
    })
      .format(new Date(year, month - 1, 1))
      .replace(".", "");
  }),
);
const monthlyVariationValues = computed(() =>
  monthlyVariationPoints.value.map((item) =>
    pnlMode.value === "include" ? item.withPnl : item.withoutPnl,
  ),
);
const monthlyVariationRange = computed(() =>
  monthlyVariationPoints.value.reduce(
    (range, point) => ({
      min: Math.min(range.min, point.withPnl, point.withoutPnl),
      max: Math.max(range.max, point.withPnl, point.withoutPnl),
    }),
    { min: 0, max: 0 },
  ),
);
const selectedVariationIndex = computed(() => {
  const index = monthlyVariationPoints.value.findIndex(
    (item) => item.fecha === selectedVariationMonth.value,
  );
  return index >= 0
    ? index
    : Math.max(0, monthlyVariationPoints.value.length - 1);
});
const positiveMonths = computed(
  () => monthlyVariationValues.value.filter((value) => value > 0).length,
);
const periodPnlImpact = computed(() =>
  monthlyVariationPoints.value.reduce(
    (total, item) => total + item.withPnl - item.withoutPnl,
    0,
  ),
);
const monthlyVariationLabel = computed(() =>
  pnlMode.value === "include"
    ? t("overview.monthly.chartLabelInclude")
    : t("overview.monthly.chartLabelExclude"),
);
const selectedMonthlyBreakdown = computed(() => {
  const selected = monthlyVariationPoints.value[selectedVariationIndex.value];
  const currentIndex = history.value.findIndex(
    (item) => item.fecha === selected?.fecha,
  );
  const current = history.value[currentIndex];
  const previous = history.value[currentIndex - 1];
  if (!current || !previous) return null;
  const [year, month] = current.fecha.split("-").map(Number);
  const monthName = new Intl.DateTimeFormat(locale.value, {
    month: "long",
    year: "numeric",
  }).format(new Date(year, month - 1, 1));
  const interest = current.ahorro_intereses;
  const savingsChange = current.ahorro - previous.ahorro;
  const withoutPnl = savingsChange + current.inv_aportes;
  const savings = withoutPnl - interest;
  const pnl = current.total - previous.total - withoutPnl;
  const withPnl = withoutPnl + pnl;
  const total = pnlMode.value === "include" ? withPnl : withoutPnl;
  return {
    month: monthName,
    total,
    savings,
    interest,
    pnl,
  };
});

watch(
  monthlyVariationPoints,
  (points) => {
    if (!points.some((item) => item.fecha === selectedVariationMonth.value)) {
      selectedVariationMonth.value = points.at(-1)?.fecha ?? null;
    }
  },
  { immediate: true },
);

const money = (value: number) => n(value, "currency");
const percentage = (value: number) => n(value, "percent");
const signedMoney = (value: number) =>
  `${value >= 0 ? "+" : "−"}${money(Math.abs(value))}`;
function selectVariationMonth(index: number) {
  const month = monthlyVariationPoints.value[index];
  if (month) selectedVariationMonth.value = month.fecha;
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    [summary.value, history.value, crowdfundingProjects.value] =
      await Promise.all([
        api<Summary>("/summary"),
        api<NetWorthPoint[]>("/net-worth-history"),
        api<RealEstateInvestment[]>("/real-estate").catch(() => []),
      ]);
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : t("overview.errors.load");
  } finally {
    loading.value = false;
  }
}

function refreshAfterSummarySourcesChange() {
  void load();
}

onMounted(() => {
  window.addEventListener(
    summarySourcesUpdatedEvent,
    refreshAfterSummarySourcesChange,
  );
  void load();
});
onBeforeUnmount(() => {
  window.removeEventListener(
    summarySourcesUpdatedEvent,
    refreshAfterSummarySourcesChange,
  );
});
</script>

<template>
  <section class="overview-page" aria-live="polite">
    <div
      v-if="loading"
      class="overview-loading"
      :aria-label="t('overview.loading')"
    >
      <div class="skeleton skeleton-hero" />
      <div class="skeleton-grid">
        <div class="skeleton" />
        <div class="skeleton" />
      </div>
    </div>

    <div v-else-if="error" class="overview-error" role="alert">
      <span aria-hidden="true">!</span>
      <div>
        <strong>{{ t("overview.errors.title") }}</strong>
        <p>{{ error }}</p>
      </div>
      <button type="button" @click="load">{{ t("common.retry") }}</button>
    </div>

    <template v-else-if="summary">
      <article
        class="overview-hero trend-panel"
        aria-labelledby="net-worth-title"
      >
        <header class="panel-header">
          <div class="net-worth-heading">
            <h2 id="net-worth-title" class="metric-label">
              {{ t("overview.netWorth") }}
            </h2>
            <span
              class="net-worth-info"
              @mouseenter="sourceInfoOpen = true"
              @mouseleave="sourceInfoOpen = false"
              @keydown.esc.stop="sourceInfoOpen = false"
            >
              <button
                type="button"
                class="net-worth-info-button"
                :aria-label="t('overview.netWorthInfo')"
                aria-describedby="net-worth-source-info"
                @focus="sourceInfoOpen = true"
                @blur="sourceInfoOpen = false"
                @click="sourceInfoOpen = true"
              >
                <span aria-hidden="true">i</span>
              </button>
              <span
                v-show="sourceInfoOpen"
                id="net-worth-source-info"
                class="net-worth-info-tooltip"
                role="tooltip"
                >{{ netWorthSourceCopy }}</span
              >
            </span>
          </div>
          <div
            class="period-control"
            role="group"
            :aria-label="t('overview.periodAria')"
          >
            <button
              v-for="item in periods"
              :key="item.key"
              type="button"
              :class="{ active: period === item.key }"
              :aria-pressed="period === item.key"
              @click="period = item.key"
            >
              {{ item.label }}
            </button>
          </div>
        </header>
        <div class="hero-metric-column">
          <p class="net-worth">{{ money(summary.net_worth) }}</p>
          <div class="period-delta" :class="{ negative: periodChange < 0 }">
            <span aria-hidden="true">{{ periodChange >= 0 ? "↗" : "↘" }}</span>
            <div>
              <strong>{{ signedMoney(periodChange) }}</strong>
              <small>{{
                t("overview.changeInPeriod", {
                  change: percentage(periodChangePercent),
                  period: periodLabel.toLocaleLowerCase(locale),
                })
              }}</small>
            </div>
          </div>
        </div>
        <div class="hero-chart" :aria-label="t('overview.netWorthEvolution')">
          <LineChart
            v-if="visibleHistory.length"
            :labels="chartLabels"
            featured
            :values="visibleHistory.map((item) => item.total)"
            :series="trendSeries"
            :total-label="t('overview.totalNetWorth')"
            :aria-label="t('overview.compositionHistoryAria')"
          />
          <div v-else class="chart-empty">
            <strong>{{ t("overview.noHistory.title") }}</strong>
            <p>{{ t("overview.noHistory.description") }}</p>
          </div>
        </div>
        <ul v-if="visibleHistory.length" class="hero-legend">
          <li class="hero-legend-total">
            <span aria-hidden="true" />{{ t("overview.totalNetWorth") }}
          </li>
          <li v-for="series in trendSeries" :key="series.key">
            <span :style="{ background: series.color }" aria-hidden="true" />
            {{ series.label }}
          </li>
        </ul>
      </article>

      <div class="overview-grid">
        <section
          class="overview-panel allocation-section"
          aria-labelledby="allocation-title"
        >
          <div class="allocation-copy">
            <h2 id="allocation-title">
              {{ t("overview.currentDistribution") }}
            </h2>
            <AllocationPie :items="allocation" />
          </div>
        </section>
      </div>

      <section class="overview-essentials" aria-labelledby="essentials-title">
        <h2 id="essentials-title">{{ t("overview.essentials") }}</h2>
        <dl class="insight-grid">
          <div class="insight-card">
            <dt>
              <NavIcon name="trend" class="insight-icon" />
              <span>{{ t("overview.variation") }}</span>
            </dt>
            <dd
              class="insight-value"
              :class="{
                positive: periodChange >= 0,
                negative: periodChange < 0,
              }"
            >
              {{ signedMoney(periodChange) }}
            </dd>
            <dd class="insight-detail">
              <small>{{ periodLabel }}</small>
            </dd>
          </div>
          <div class="insight-card interest-insight">
            <dt>
              <NavIcon name="wallet" class="insight-icon" />
              <span>{{ t("overview.accumulatedInterest") }}</span>
            </dt>
            <dd class="insight-value">{{ money(summary.total_interest) }}</dd>
            <dd class="insight-detail">
              <small>{{ t("overview.recordedHistory") }}</small>
            </dd>
          </div>
          <div class="insight-card largest-block-insight">
            <dt>
              <NavIcon name="funds" class="insight-icon" />
              <span>{{ t("overview.largestBlock") }}</span>
            </dt>
            <dd class="insight-value">
              {{ biggestAllocation?.label ?? t("common.noData") }}
            </dd>
            <dd v-if="biggestAllocation" class="insight-detail">
              <small>{{
                t("overview.ofNetWorth", {
                  share: percentage(biggestAllocation.share),
                })
              }}</small>
            </dd>
          </div>
          <div class="insight-card upcoming-project-insight">
            <dt>
              <NavIcon name="building" class="insight-icon" />
              <span>{{ t("overview.upcomingMaturity") }}</span>
            </dt>
            <dd
              class="insight-value"
              :class="{ muted: !upcomingCrowdfundingProject }"
            >
              {{
                upcomingCrowdfundingProject?.item.name ??
                t(
                  includesCrowdfunding
                    ? "overview.noUpcomingMaturity"
                    : "common.noData",
                )
              }}
            </dd>
            <dd class="insight-detail">
              <small>
                {{
                  upcomingCrowdfundingProject
                    ? t("overview.maturesOn", {
                        date: upcomingCrowdfundingDate,
                      })
                    : t(
                        includesCrowdfunding
                          ? "overview.nextThreeMonths"
                          : "overview.crowdfundingExcluded",
                      )
                }}
              </small>
            </dd>
          </div>
        </dl>
      </section>

      <article
        class="overview-panel monthly-variation-panel"
        aria-labelledby="monthly-variation-title"
      >
        <header class="panel-header monthly-variation-header">
          <h2 id="monthly-variation-title">
            {{ t("overview.monthly.title") }}
          </h2>
          <p class="monthly-variation-description">
            <span class="monthly-variation-sources">{{
              monthlyDescriptionCopy
            }}</span>
            <span class="monthly-variation-period">{{ periodLabel }}</span>
          </p>

          <div
            v-if="selectedMonthlyBreakdown"
            class="monthly-pnl-control"
            role="group"
            :aria-label="t('overview.monthly.pnlAria')"
          >
            <button
              type="button"
              :aria-pressed="pnlMode === 'include'"
              @click="pnlMode = 'include'"
            >
              {{ t("overview.monthly.withPnl") }}
            </button>
            <button
              type="button"
              :aria-pressed="pnlMode === 'exclude'"
              @click="pnlMode = 'exclude'"
            >
              {{ t("overview.monthly.withoutPnl") }}
            </button>
          </div>
        </header>

        <template v-if="selectedMonthlyBreakdown">
          <div class="monthly-breakdown-total">
            <div class="monthly-month-navigation">
              <h3 id="monthly-breakdown-title">
                {{ selectedMonthlyBreakdown.month }}
              </h3>
              <div class="monthly-month-buttons">
                <button
                  type="button"
                  :aria-label="t('overview.monthly.previousMonth')"
                  :disabled="selectedVariationIndex === 0"
                  @click="selectVariationMonth(selectedVariationIndex - 1)"
                >
                  <i class="monthly-month-arrow previous" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  :aria-label="t('overview.monthly.nextMonth')"
                  :disabled="
                    selectedVariationIndex === monthlyVariationPoints.length - 1
                  "
                  @click="selectVariationMonth(selectedVariationIndex + 1)"
                >
                  <i class="monthly-month-arrow" aria-hidden="true" />
                </button>
              </div>
            </div>
            <strong
              :class="{
                positive: selectedMonthlyBreakdown.total >= 0,
                negative: selectedMonthlyBreakdown.total < 0,
              }"
            >
              {{ signedMoney(selectedMonthlyBreakdown.total) }}
            </strong>
          </div>

          <MonthlyVariationChart
            :labels="monthlyVariationLabels"
            :values="monthlyVariationValues"
            :label="monthlyVariationLabel"
            :range="monthlyVariationRange"
            :selected-index="selectedVariationIndex"
            :selected-month="selectedMonthlyBreakdown.month"
            @select="selectVariationMonth"
          />

          <dl class="monthly-breakdown-list">
            <div>
              <dt>{{ t("overview.monthly.savingsAndMovements") }}</dt>
              <dd :class="{ negative: selectedMonthlyBreakdown.savings < 0 }">
                {{ signedMoney(selectedMonthlyBreakdown.savings) }}
              </dd>
            </div>
            <div>
              <dt>{{ t("overview.monthly.interest") }}</dt>
              <dd :class="{ negative: selectedMonthlyBreakdown.interest < 0 }">
                {{ signedMoney(selectedMonthlyBreakdown.interest) }}
              </dd>
            </div>
            <div :class="{ excluded: pnlMode === 'exclude' }">
              <dt>{{ t("overview.monthly.balancePnl") }}</dt>
              <dd>
                <span
                  :class="{
                    negative:
                      pnlMode === 'include' && selectedMonthlyBreakdown.pnl < 0,
                  }"
                >
                  {{ signedMoney(selectedMonthlyBreakdown.pnl) }}
                </span>
                <small v-if="pnlMode === 'exclude'">{{
                  t("overview.monthly.excluded")
                }}</small>
              </dd>
            </div>
          </dl>

          <footer class="monthly-chart-meta">
            <span>{{
              t("overview.monthly.positiveMonths", {
                positive: positiveMonths,
                count: monthlyVariationPoints.length,
              })
            }}</span>
            <span>
              {{ t("overview.monthly.pnlEffect") }}
              <strong
                :class="{
                  positive: periodPnlImpact >= 0,
                  negative: periodPnlImpact < 0,
                }"
              >
                {{ signedMoney(periodPnlImpact) }}
              </strong>
            </span>
          </footer>
        </template>
        <div v-else class="chart-empty monthly-variation-empty">
          <strong>{{ t("overview.monthly.emptyTitle") }}</strong>
          <p>{{ t("overview.monthly.emptyDescription") }}</p>
        </div>
      </article>
    </template>
  </section>
</template>
