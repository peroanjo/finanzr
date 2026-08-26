<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { api } from "../api/client";
import AllocationChart from "../components/AllocationChart.vue";
import LineChart from "../components/LineChart.vue";
import type { LineChartSeries } from "../components/LineChart.vue";
import MonthlyVariationChart from "../components/MonthlyVariationChart.vue";
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
const period = ref<Period>("1y");
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
          color: "var(--fz-trade-buy)",
        },
        {
          key: "crowdfunding" as const,
          included: true,
          label: t("overview.allocation.realEstate"),
          value: summary.value.total_real_estate,
          color: "var(--fz-chart-average)",
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
const showsCrowdfundingInsight = computed(() =>
  activeSourceKeys.value.includes("crowdfunding"),
);
const upcomingCrowdfundingProject = computed(() => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const deadline = new Date(today);
  deadline.setMonth(deadline.getMonth() + 3);
  return (
    crowdfundingProjects.value
      .filter((item) => item.estado.toLowerCase().includes("activ"))
      .map((item) => ({
        item,
        maturity: new Date(`${item.fecha_vencimiento.slice(0, 10)}T00:00:00`),
      }))
      .filter(
        ({ item, maturity }) =>
          item.capital_inicial > item.capital_devuelto &&
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
      value: pnlMode.value === "include" ? withPnl : withoutPnl,
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
  monthlyVariationPoints.value.map((item) => item.value),
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
  const magnitude =
    Math.abs(savings) +
    Math.abs(interest) +
    (pnlMode.value === "include" ? Math.abs(pnl) : 0);
  const share = (value: number) =>
    magnitude ? `${(Math.abs(value) / magnitude) * 100}%` : "0%";
  return {
    month: monthName,
    total,
    savings,
    interest,
    pnl,
    savingsShare: share(savings),
    interestShare: share(interest),
    pnlShare: pnlMode.value === "include" ? share(pnl) : "0%",
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
  selectedVariationMonth.value =
    monthlyVariationPoints.value[index]?.fecha ?? null;
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
      <article class="overview-hero">
        <div class="hero-overview-grid">
          <div class="hero-metric-column">
            <p class="metric-label">{{ t("overview.netWorth") }}</p>
            <p class="net-worth">{{ money(summary.net_worth) }}</p>
            <p class="net-worth-source">
              <span aria-hidden="true">i</span>
              {{ netWorthSourceCopy }}
            </p>
            <div class="period-delta" :class="{ negative: periodChange < 0 }">
              <span aria-hidden="true">{{
                periodChange >= 0 ? "↗" : "↘"
              }}</span>
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

          <section
            class="allocation-section"
            aria-labelledby="allocation-title"
          >
            <AllocationChart
              v-if="allocation.some((item) => item.share > 0)"
              :items="allocation"
            />
            <div v-else class="allocation-chart-empty" aria-hidden="true">
              —
            </div>

            <div class="allocation-copy">
              <p class="section-label">{{ t("overview.composition") }}</p>
              <h3 id="allocation-title">
                {{ t("overview.currentDistribution") }}
              </h3>
              <div class="allocation-legend">
                <div v-for="item in allocation" :key="item.label">
                  <span
                    class="legend-dot"
                    :style="{ background: item.color }"
                  />
                  <span>{{ item.label }}</span>
                  <strong>{{ money(item.value) }}</strong>
                  <small>{{ percentage(item.share) }}</small>
                </div>
              </div>
            </div>
          </section>
        </div>
      </article>

      <div class="overview-grid">
        <article class="overview-panel trend-panel">
          <header class="panel-header trend-panel-header">
            <div>
              <p class="section-label">{{ t("overview.trajectory") }}</p>
              <h2>{{ t("overview.netWorthEvolution") }}</h2>
            </div>
            <div class="trend-panel-actions">
              <span class="live-indicator"
                ><i /> {{ t("overview.workspaceData") }}</span
              >
              <div
                class="period-control"
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
            </div>
          </header>

          <div v-if="visibleHistory.length" class="chart-summary">
            <div>
              <small>{{ t("overview.start") }}</small
              ><strong>{{ money(startValue) }}</strong>
            </div>
            <span aria-hidden="true">→</span>
            <div>
              <small>{{ t("overview.current") }}</small
              ><strong>{{ money(currentValue) }}</strong>
            </div>
            <div class="chart-change">
              <small>{{ t("overview.variation") }}</small>
              <strong :class="{ negative: periodChange < 0 }">{{
                percentage(periodChangePercent)
              }}</strong>
            </div>
          </div>
          <div
            v-if="trendSeries.length"
            class="trend-composition"
            role="group"
            :aria-label="t('overview.compositionHistoryAria')"
          >
            <span class="trend-total-key"
              ><i aria-hidden="true" />{{ t("overview.totalNetWorth") }}</span
            >
            <ul>
              <li v-for="item in trendSeries" :key="item.key">
                <i :style="{ background: item.color }" aria-hidden="true" />
                <span>{{ item.label }}</span>
                <strong>{{ money(item.currentValue) }}</strong>
              </li>
            </ul>
          </div>
          <LineChart
            v-if="visibleHistory.length"
            :labels="chartLabels"
            :values="visibleHistory.map((item) => item.total)"
            :series="trendSeries"
            :total-label="t('overview.totalNetWorth')"
            :aria-label="t('overview.compositionHistoryAria')"
          />
          <div v-else class="chart-empty">
            <strong>{{ t("overview.noHistory.title") }}</strong>
            <p>{{ t("overview.noHistory.description") }}</p>
          </div>
        </article>

        <aside class="overview-panel insight-panel">
          <header class="panel-header">
            <div>
              <p class="section-label">{{ t("overview.periodReading") }}</p>
              <h2>{{ t("overview.essentials") }}</h2>
            </div>
          </header>

          <dl class="insight-list">
            <div>
              <dt>{{ t("overview.variation") }}</dt>
              <dd
                :class="{
                  positive: periodChange >= 0,
                  negative: periodChange < 0,
                }"
              >
                {{ signedMoney(periodChange) }}
              </dd>
              <small>{{ periodLabel }}</small>
            </div>
            <div>
              <dt>{{ t("overview.accumulatedInterest") }}</dt>
              <dd>{{ money(summary.total_interest) }}</dd>
              <small>{{ t("overview.recordedHistory") }}</small>
            </div>
            <div class="largest-block-insight">
              <dt>{{ t("overview.largestBlock") }}</dt>
              <dd>{{ biggestAllocation?.label ?? t("common.noData") }}</dd>
              <small v-if="biggestAllocation">{{
                t("overview.ofNetWorth", {
                  share: percentage(biggestAllocation.share),
                })
              }}</small>
            </div>
            <div
              v-if="showsCrowdfundingInsight"
              class="upcoming-project-insight"
            >
              <dt>{{ t("overview.upcomingMaturity") }}</dt>
              <dd :class="{ muted: !upcomingCrowdfundingProject }">
                {{
                  upcomingCrowdfundingProject?.item.nombre ??
                  t("overview.noUpcomingMaturity")
                }}
              </dd>
              <small>
                {{
                  upcomingCrowdfundingProject
                    ? t("overview.maturesOn", {
                        date: upcomingCrowdfundingDate,
                      })
                    : t("overview.nextThreeMonths")
                }}
              </small>
            </div>
          </dl>
        </aside>
      </div>

      <article class="overview-panel monthly-variation-panel">
        <header class="panel-header monthly-variation-header">
          <div>
            <p class="section-label">{{ t("overview.monthly.eyebrow") }}</p>
            <h2>{{ t("overview.monthly.title") }}</h2>
            <p class="monthly-variation-description">
              {{ monthlyDescriptionCopy }}
            </p>
          </div>

          <div class="pnl-mode-control">
            <span>{{ t("overview.monthly.balancePnl") }}</span>
            <div
              class="period-control"
              :aria-label="t('overview.monthly.pnlAria')"
            >
              <button
                type="button"
                :class="{ active: pnlMode === 'include' }"
                :aria-pressed="pnlMode === 'include'"
                @click="pnlMode = 'include'"
              >
                {{ t("overview.monthly.include") }}
              </button>
              <button
                type="button"
                :class="{ active: pnlMode === 'exclude' }"
                :aria-pressed="pnlMode === 'exclude'"
                @click="pnlMode = 'exclude'"
              >
                {{ t("overview.monthly.exclude") }}
              </button>
            </div>
          </div>
        </header>

        <div
          v-if="monthlyVariationPoints.length && selectedMonthlyBreakdown"
          class="monthly-variation-body"
        >
          <section
            class="monthly-breakdown-card"
            aria-labelledby="monthly-breakdown-title"
          >
            <header>
              <strong id="monthly-breakdown-title">{{
                selectedMonthlyBreakdown.month
              }}</strong>
              <span>{{
                pnlMode === "include"
                  ? t("overview.monthly.withPnl")
                  : t("overview.monthly.withoutPnl")
              }}</span>
            </header>

            <div class="monthly-breakdown-total">
              <small>{{ t("overview.monthly.totalVariation") }}</small>
              <strong
                :class="{
                  positive: selectedMonthlyBreakdown.total >= 0,
                  negative: selectedMonthlyBreakdown.total < 0,
                }"
              >
                {{ signedMoney(selectedMonthlyBreakdown.total) }}
              </strong>
            </div>

            <div class="monthly-breakdown-rail" aria-hidden="true">
              <i
                class="savings"
                :style="{ width: selectedMonthlyBreakdown.savingsShare }"
              />
              <i
                class="interest"
                :style="{ width: selectedMonthlyBreakdown.interestShare }"
              />
              <i
                class="pnl"
                :class="{ negative: selectedMonthlyBreakdown.pnl < 0 }"
                :style="{ width: selectedMonthlyBreakdown.pnlShare }"
              />
            </div>

            <dl class="monthly-breakdown-list">
              <div>
                <dt>
                  <i class="savings" />{{
                    t("overview.monthly.savingsAndMovements")
                  }}
                </dt>
                <dd :class="{ negative: selectedMonthlyBreakdown.savings < 0 }">
                  {{ signedMoney(selectedMonthlyBreakdown.savings) }}
                </dd>
              </div>
              <div>
                <dt>
                  <i class="interest" />{{ t("overview.monthly.interest") }}
                </dt>
                <dd
                  :class="{ negative: selectedMonthlyBreakdown.interest < 0 }"
                >
                  {{ signedMoney(selectedMonthlyBreakdown.interest) }}
                </dd>
              </div>
              <div :class="{ excluded: pnlMode === 'exclude' }">
                <dt>
                  <i
                    class="pnl"
                    :class="{ negative: selectedMonthlyBreakdown.pnl < 0 }"
                  />{{ t("overview.monthly.balancePnl") }}
                </dt>
                <dd :class="{ negative: selectedMonthlyBreakdown.pnl < 0 }">
                  {{ signedMoney(selectedMonthlyBreakdown.pnl) }}
                </dd>
                <small v-if="pnlMode === 'exclude'">{{
                  t("overview.monthly.excluded")
                }}</small>
              </div>
            </dl>
          </section>

          <div class="monthly-chart-column">
            <div class="monthly-chart-meta">
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
            </div>
            <MonthlyVariationChart
              :labels="monthlyVariationLabels"
              :values="monthlyVariationValues"
              :label="monthlyVariationLabel"
              :selected-index="selectedVariationIndex"
              @select="selectVariationMonth"
            />
          </div>
        </div>
        <div v-else class="chart-empty monthly-variation-empty">
          <strong>{{ t("overview.monthly.emptyTitle") }}</strong>
          <p>{{ t("overview.monthly.emptyDescription") }}</p>
        </div>
      </article>
    </template>
  </section>
</template>
