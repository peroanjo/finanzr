<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

type Theme = "light" | "dark";

const theme = ref<Theme>("light");
const period = ref("twelveMonths");
const activeNav = ref("overview");
const { locale, t } = useI18n();

const allocation = computed(() => [
  {
    label: t("shared.designPreview.savings"),
    value: 32840,
    share: 32,
    color: "#19a974",
  },
  {
    label: t("shared.designPreview.funds"),
    value: 28490,
    share: 28,
    color: "#5375e2",
  },
  {
    label: t("shared.designPreview.stocks"),
    value: 21710,
    share: 21,
    color: "#ec8c42",
  },
  {
    label: t("navigation.realEstate"),
    value: 13280,
    share: 13,
    color: "#9a6ad6",
  },
  {
    label: t("shared.designPreview.crypto"),
    value: 6120,
    share: 6,
    color: "#e2bd42",
  },
]);

const chartPoints = [22, 28, 25, 34, 37, 43, 41, 49, 54, 62, 68, 72];
const chartPath = computed(() =>
  chartPoints
    .map(
      (value, index) =>
        `${index === 0 ? "M" : "L"} ${index * (560 / 11)} ${110 - value}`,
    )
    .join(" "),
);

const navItems = [
  { key: "overview", icon: "home" },
  { key: "savings", icon: "wallet" },
  { key: "funds", icon: "funds" },
  { key: "stocks", icon: "stocks" },
  { key: "crypto", icon: "crypto" },
  { key: "balances", icon: "trend" },
];
const periods = ["threeMonths", "sixMonths", "twelveMonths", "all"];
const wholeMoney = computed(
  () =>
    new Intl.NumberFormat(locale.value, {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }),
);
const preciseMoney = computed(
  () =>
    new Intl.NumberFormat(locale.value, {
      style: "currency",
      currency: "EUR",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
);
const percentage = computed(
  () =>
    new Intl.NumberFormat(locale.value, {
      style: "percent",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
);
const topDate = computed(() =>
  new Intl.DateTimeFormat(locale.value, {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date(2026, 6, 23)),
);
const shortDate = computed(
  () =>
    new Intl.DateTimeFormat(locale.value, {
      day: "numeric",
      month: "short",
    }).format,
);
const chartMonths = computed(() =>
  [7, 9, 11, 1, 3, 6].map((month, index) => {
    const year = index < 3 ? 2025 : 2026;
    return new Intl.DateTimeFormat(locale.value, { month: "short" })
      .format(new Date(year, month, 1))
      .replace(".", "")
      .toUpperCase();
  }),
);

function toggleTheme() {
  theme.value = theme.value === "light" ? "dark" : "light";
  localStorage.setItem("finanzr-design-theme", theme.value);
}

onMounted(() => {
  const saved = localStorage.getItem("finanzr-design-theme");
  theme.value =
    saved === "light" || saved === "dark"
      ? saved
      : window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
});
</script>

<template>
  <div class="design-preview" :data-theme="theme">
    <aside class="preview-sidebar">
      <a
        class="preview-brand"
        href="#"
        :aria-label="t('shared.designPreview.homeAria')"
        @click.prevent="activeNav = 'overview'"
      >
        <span class="preview-brand-name"
          >finanzr<span class="preview-brand-dot" aria-hidden="true"
            >.</span
          ></span
        >
      </a>

      <nav :aria-label="t('shared.designPreview.navigationAria')">
        <button
          v-for="item in navItems"
          :key="item.key"
          type="button"
          :class="{ active: activeNav === item.key }"
          @click="activeNav = item.key"
        >
          <svg
            class="nav-icon"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
          >
            <template v-if="item.icon === 'home'">
              <path d="M3.5 10.5 12 3.75l8.5 6.75" />
              <path d="M5.5 9.25v10h13v-10M9.5 19.25v-6h5v6" />
            </template>
            <template v-else-if="item.icon === 'wallet'">
              <path
                d="M4 6.5h14.5A1.5 1.5 0 0 1 20 8v10H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h12"
              />
              <path d="M15 11h5v4h-5a2 2 0 0 1 0-4Z" />
            </template>
            <template v-else-if="item.icon === 'trend'">
              <path d="M3 18 9 12l4 4 8-9" />
              <path d="M15 7h6v6" />
            </template>
            <template v-else-if="item.icon === 'funds'">
              <path d="M12 3a9 9 0 1 0 9 9h-9V3Z" />
              <path d="M15 3.5A8.5 8.5 0 0 1 20.5 9H15V3.5Z" />
            </template>
            <template v-else-if="item.icon === 'stocks'">
              <path d="M6 4v16M18 3v18M12 7v10" />
              <path d="M3.5 8h5v7h-5zM9.5 9h5v5h-5zM15.5 6h5v9h-5z" />
            </template>
            <template v-else>
              <path d="M9 5h5.5a3 3 0 0 1 0 6H9m0 0h6a3.5 3.5 0 0 1 0 7H9V5" />
              <path d="M11 2v3m4-3v3m-4 13v4m4-4v4M6 5h3m-3 13h3" />
            </template>
          </svg>
          {{ t(`shared.designPreview.${item.key}`) }}
        </button>
      </nav>

      <div class="sidebar-foot">
        <button class="workspace" type="button">
          <span class="avatar">DN</span>
          <span>
            <strong>Casa Nazo</strong>
            <small>{{ t("shared.designPreview.familyWorkspace") }}</small>
          </span>
          <span aria-hidden="true">⌄</span>
        </button>
        <p>{{ t("shared.designPreview.mockData") }}</p>
      </div>
    </aside>

    <main class="preview-main">
      <header class="preview-topbar">
        <div>
          <p class="context-label">{{ topDate }}</p>
          <h1>{{ t(`shared.designPreview.${activeNav}`) }}</h1>
        </div>

        <div class="top-actions">
          <button
            class="theme-toggle"
            type="button"
            :aria-label="
              t(
                theme === 'light'
                  ? 'shell.enableDarkMode'
                  : 'shell.enableLightMode',
              )
            "
            @click="toggleTheme"
          >
            <span aria-hidden="true">{{ theme === "light" ? "☼" : "☾" }}</span>
            {{ t(theme === "light" ? "shell.light" : "shell.dark") }}
          </button>
          <button class="quick-add" type="button">
            <span aria-hidden="true">＋</span>
            {{ t("shared.designPreview.addMovement") }}
          </button>
        </div>
      </header>

      <section class="snapshot" aria-labelledby="snapshot-title">
        <div class="snapshot-heading">
          <div>
            <p class="section-label">
              {{ t("shared.designPreview.consolidatedPosition") }}
            </p>
            <h2 id="snapshot-title">
              {{ t("shared.designPreview.snapshotTitle") }}
            </h2>
          </div>
          <div
            class="period-control"
            :aria-label="t('shared.designPreview.summaryPeriodAria')"
          >
            <button
              v-for="item in periods"
              :key="item"
              type="button"
              :class="{ active: period === item }"
              @click="period = item"
            >
              {{ t(`shared.designPreview.${item}`) }}
            </button>
          </div>
        </div>

        <div class="net-worth-row">
          <div>
            <p class="metric-label">{{ t("shared.designPreview.netWorth") }}</p>
            <p class="net-worth">{{ preciseMoney.format(102440) }}</p>
          </div>
          <div class="delta">
            <span>↗</span>
            <div>
              <strong>+{{ wholeMoney.format(8320) }}</strong
              ><small>{{
                t("shared.designPreview.inPeriod", {
                  period: t(`shared.designPreview.${period}`).toLowerCase(),
                })
              }}</small>
            </div>
          </div>
        </div>

        <div
          class="allocation-bar"
          :aria-label="t('shared.designPreview.allocationAria')"
        >
          <span
            v-for="item in allocation"
            :key="item.label"
            :style="{ width: `${item.share}%`, background: item.color }"
            :title="`${item.label}: ${item.share}%`"
          />
        </div>
        <div class="allocation-legend">
          <div v-for="item in allocation" :key="item.label">
            <span class="legend-dot" :style="{ background: item.color }" />
            <span>{{ item.label }}</span>
            <strong>{{ wholeMoney.format(item.value) }}</strong>
            <small>{{ item.share }}%</small>
          </div>
        </div>
      </section>

      <div class="dashboard-grid">
        <section class="trend-panel" aria-labelledby="trend-title">
          <header class="panel-header">
            <div>
              <p class="section-label">
                {{ t("shared.designPreview.trajectory") }}
              </p>
              <h2 id="trend-title">
                {{ t("shared.designPreview.netWorthEvolution") }}
              </h2>
            </div>
            <span class="live-indicator"
              ><i /> {{ t("shared.designPreview.upToDate") }}</span
            >
          </header>

          <div class="chart-summary">
            <div>
              <small>{{ t("shared.designPreview.start") }}</small
              ><strong>{{ wholeMoney.format(94120) }}</strong>
            </div>
            <span aria-hidden="true">→</span>
            <div>
              <small>{{ t("shared.designPreview.today") }}</small
              ><strong>{{ wholeMoney.format(102440) }}</strong>
            </div>
            <div class="chart-change">
              <small>{{ t("shared.designPreview.change") }}</small
              ><strong>+{{ percentage.format(0.0884) }}</strong>
            </div>
          </div>

          <div
            class="mock-chart"
            role="img"
            :aria-label="t('shared.designPreview.chartAria')"
          >
            <svg
              viewBox="0 0 560 120"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <defs>
                <linearGradient id="area-light" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stop-color="var(--accent)"
                    stop-opacity=".24"
                  />
                  <stop
                    offset="100%"
                    stop-color="var(--accent)"
                    stop-opacity="0"
                  />
                </linearGradient>
              </defs>
              <path
                :d="`${chartPath} L 560 120 L 0 120 Z`"
                fill="url(#area-light)"
              />
              <path
                :d="chartPath"
                fill="none"
                stroke="var(--accent)"
                stroke-width="3"
                vector-effect="non-scaling-stroke"
              />
            </svg>
            <div class="chart-months">
              <span v-for="month in chartMonths" :key="month">{{ month }}</span>
            </div>
          </div>
        </section>

        <section class="attention-panel" aria-labelledby="attention-title">
          <header class="panel-header">
            <div>
              <p class="section-label">{{ t("shared.designPreview.now") }}</p>
              <h2 id="attention-title">
                {{ t("shared.designPreview.attentionTitle") }}
              </h2>
            </div>
            <span class="count-badge">3</span>
          </header>

          <div class="attention-list">
            <button type="button">
              <span class="attention-icon violet">↻</span>
              <span
                ><strong>{{ t("shared.designPreview.updatePrices") }}</strong
                ><small>{{
                  t("shared.designPreview.staleAssets")
                }}</small></span
              >
              <span aria-hidden="true">→</span>
            </button>
            <button type="button">
              <span class="attention-icon orange">!</span>
              <span
                ><strong>{{
                  t("shared.designPreview.reviewCategorization")
                }}</strong
                ><small>{{
                  t("shared.designPreview.uncategorizedMovement", {
                    amount: preciseMoney.format(86.4),
                  })
                }}</small></span
              >
              <span aria-hidden="true">→</span>
            </button>
            <button type="button">
              <span class="attention-icon blue">⌁</span>
              <span
                ><strong>{{
                  t("shared.designPreview.importOperations")
                }}</strong
                ><small>{{ t("shared.designPreview.lastImport") }}</small></span
              >
              <span aria-hidden="true">→</span>
            </button>
          </div>
        </section>

        <section class="activity-panel" aria-labelledby="activity-title">
          <header class="panel-header">
            <div>
              <p class="section-label">
                {{ t("shared.designPreview.latestChanges") }}
              </p>
              <h2 id="activity-title">
                {{ t("shared.designPreview.recentActivity") }}
              </h2>
            </div>
            <button class="text-button" type="button">
              {{ t("shared.designPreview.viewAll") }}
            </button>
          </header>

          <div class="activity-table">
            <div class="activity-row activity-head">
              <span>{{ t("shared.designPreview.movement") }}</span
              ><span>{{ t("shared.designPreview.account") }}</span
              ><span>{{ t("shared.designPreview.date") }}</span
              ><span>{{ t("shared.designPreview.amount") }}</span>
            </div>
            <div class="activity-row">
              <span
                ><i class="activity-mark green">F</i
                ><strong>{{
                  t("shared.designPreview.indexedFundContribution")
                }}</strong></span
              >
              <span>MyInvestor</span
              ><span>{{ shortDate(new Date(2026, 6, 22)) }}</span
              ><span class="negative">−{{ preciseMoney.format(250) }}</span>
            </div>
            <div class="activity-row">
              <span
                ><i class="activity-mark blue">N</i
                ><strong>{{ t("shared.designPreview.salary") }}</strong></span
              >
              <span>{{ t("shared.designPreview.mainAccount") }}</span
              ><span>{{ shortDate(new Date(2026, 6, 20)) }}</span
              ><span class="positive">+{{ preciseMoney.format(2480) }}</span>
            </div>
            <div class="activity-row">
              <span
                ><i class="activity-mark orange">B</i
                ><strong>{{
                  t("shared.designPreview.btcPurchase")
                }}</strong></span
              >
              <span>Kraken Pro</span
              ><span>{{ shortDate(new Date(2026, 6, 18)) }}</span
              ><span class="negative">−{{ preciseMoney.format(75) }}</span>
            </div>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.design-preview {
  --canvas: #f4f7f5;
  --surface: #ffffff;
  --surface-soft: #edf2ef;
  --accent-wash: #edf8f3;
  --ink: #152019;
  --muted: #68736c;
  --line: #dfe6e1;
  --accent: #148a62;
  --accent-soft: #d8f1e7;
  --sidebar: #19251e;
  --sidebar-ink: #f0f5f1;
  --sidebar-muted: #92a198;
  --panel-shadow: 0 14px 38px rgba(25, 45, 34, 0.06);
  min-height: 100vh;
  background: var(--canvas);
  color: var(--ink);
  display: grid;
  grid-template-columns: 252px minmax(0, 1fr);
  font-family:
    "Manrope Variable", "Manrope", "Inter", ui-sans-serif, system-ui, sans-serif;
  font-weight: 500;
  transition:
    background-color 0.25s ease,
    color 0.25s ease;
}

.design-preview[data-theme="dark"] {
  --canvas: #0d1210;
  --surface: #151c18;
  --surface-soft: #1d2822;
  --accent-wash: #14271e;
  --ink: #edf3ef;
  --muted: #95a39a;
  --line: #2a3730;
  --accent: #4bd2a0;
  --accent-soft: #173b2e;
  --sidebar: #080d0a;
  --sidebar-ink: #f2f7f4;
  --sidebar-muted: #839188;
  --panel-shadow: 0 18px 46px rgba(0, 0, 0, 0.18);
  color-scheme: dark;
}

button,
a {
  -webkit-tap-highlight-color: transparent;
}
button:focus-visible,
a:focus-visible {
  outline: 3px solid #53a9ff;
  outline-offset: 3px;
}

.preview-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: 24px 16px 20px;
  background: var(--sidebar);
  color: var(--sidebar-ink);
  display: flex;
  flex-direction: column;
  border: 0;
}

.preview-brand {
  color: inherit;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 0 10px 32px;
  font-size: 19px;
  font-weight: 760;
  letter-spacing: -0.035em;
}

.preview-brand-dot {
  color: #4bd2a0;
  font-weight: 820;
}

.preview-sidebar nav {
  display: grid;
  gap: 5px;
}
.preview-sidebar nav button {
  width: 100%;
  border: 0;
  padding: 11px 13px;
  background: transparent;
  color: var(--sidebar-muted);
  border-radius: 11px;
  display: grid;
  grid-template-columns: 20px 1fr;
  align-items: center;
  text-align: left;
  font-weight: 620;
  cursor: pointer;
  transition:
    background 0.18s ease,
    color 0.18s ease,
    transform 0.18s ease;
}
.preview-sidebar nav button:hover {
  color: var(--sidebar-ink);
  background: rgba(255, 255, 255, 0.045);
  transform: translateX(2px);
}
.preview-sidebar nav button.active {
  color: #e9fff6;
  background: rgba(75, 210, 160, 0.13);
}
.nav-icon {
  width: 17px;
  height: 17px;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.preview-sidebar nav button.active .nav-icon {
  color: #4bd2a0;
  filter: drop-shadow(0 0 5px rgba(75, 210, 160, 0.2));
}

.sidebar-foot {
  margin-top: auto;
}
.workspace {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.04);
  color: var(--sidebar-ink);
  border-radius: 14px;
  padding: 11px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 10px;
  align-items: center;
  text-align: left;
  cursor: pointer;
}
.workspace .avatar {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  background: #32453a;
  color: #bdf1dc;
  font-size: 11px;
  font-weight: 800;
}
.workspace strong,
.workspace small {
  display: block;
}
.workspace strong {
  font-size: 12px;
  font-weight: 720;
}
.workspace small {
  margin-top: 2px;
  color: var(--sidebar-muted);
  font-size: 10px;
}
.sidebar-foot > p {
  color: #617067;
  font-size: 10px;
  margin: 14px 4px 0;
}

.preview-main {
  min-width: 0;
  padding: 0 48px 56px;
}
.preview-topbar {
  min-height: 108px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  border-bottom: 1px solid var(--line);
}
.context-label,
.section-label {
  margin: 0 0 5px;
  color: var(--muted);
  font-size: 10px;
  line-height: 1.4;
  font-weight: 720;
  letter-spacing: 0.035em;
}
.preview-topbar h1 {
  margin: 0;
  font-size: clamp(30px, 4vw, 40px);
  font-weight: 720;
  letter-spacing: -0.045em;
  line-height: 1.05;
}
.top-actions {
  display: flex;
  gap: 10px;
}
.theme-toggle,
.quick-add {
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink);
  border-radius: 12px;
  padding: 10px 15px;
  font-weight: 680;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(20, 38, 28, 0.04);
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    background 0.18s ease;
}
.theme-toggle {
  display: inline-flex;
  gap: 8px;
  align-items: center;
}
.theme-toggle span {
  width: 21px;
  height: 21px;
  display: grid;
  place-items: center;
  border-radius: 7px;
  background: var(--surface-soft);
}
.theme-toggle:hover,
.quick-add:hover {
  transform: translateY(-1px);
}
.quick-add {
  background: var(--accent);
  color: #f5fffb;
  border-color: var(--accent);
}

.snapshot {
  position: relative;
  overflow: hidden;
  margin-top: 28px;
  padding: 30px;
  border: 1px solid var(--line);
  border-radius: 24px;
  background: linear-gradient(135deg, var(--surface) 55%, var(--accent-wash));
  box-shadow: var(--panel-shadow);
  animation: hero-in 0.46s cubic-bezier(0.2, 0.75, 0.2, 1) both;
}
.snapshot::after {
  content: "";
  position: absolute;
  width: 190px;
  height: 190px;
  top: -118px;
  right: -72px;
  border: 36px solid var(--accent-soft);
  border-radius: 50%;
  opacity: 0.46;
  pointer-events: none;
}
.snapshot-heading,
.panel-header,
.net-worth-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  position: relative;
  z-index: 1;
}
.snapshot h2,
.panel-header h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 720;
  letter-spacing: -0.025em;
}
.period-control {
  display: flex;
  background: var(--surface-soft);
  padding: 4px;
  border-radius: 12px;
}
.period-control button {
  border: 0;
  background: transparent;
  color: var(--muted);
  border-radius: 9px;
  padding: 8px 11px;
  font-size: 11px;
  font-weight: 680;
  cursor: pointer;
}
.period-control button.active {
  background: var(--surface);
  color: var(--ink);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
}
.net-worth-row {
  align-items: flex-end;
  margin: 30px 0 27px;
}
.metric-label {
  margin: 0 0 6px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
}
.net-worth {
  margin: 0;
  font-size: clamp(48px, 7vw, 72px);
  font-weight: 610;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.07em;
  line-height: 0.94;
}
.net-worth span {
  font-size: 0.38em;
  font-weight: 520;
  letter-spacing: -0.035em;
  color: var(--muted);
}
.delta {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 7px;
  color: var(--accent);
}
.delta > span {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  background: var(--accent-soft);
  border-radius: 11px;
}
.delta strong,
.delta small {
  display: block;
}
.delta strong {
  font-size: 14px;
  font-weight: 740;
  font-variant-numeric: tabular-nums;
}
.delta small {
  margin-top: 2px;
  color: var(--muted);
  font-size: 11px;
}
.allocation-bar {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 11px;
  display: flex;
  gap: 4px;
  overflow: hidden;
  border-radius: 999px;
}
.allocation-bar span {
  min-width: 8px;
  transition: filter 0.2s ease;
}
.allocation-bar span:hover {
  filter: brightness(1.15);
}
.allocation-legend {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin-top: 15px;
}
.allocation-legend > div {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 7px;
  align-items: center;
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 3px;
}
.allocation-legend span:not(.legend-dot) {
  font-size: 11px;
  color: var(--muted);
}
.allocation-legend strong {
  grid-column: 2;
  margin-top: 4px;
  font-size: 12px;
  font-weight: 720;
  font-variant-numeric: tabular-nums;
}
.allocation-legend small {
  grid-column: 2;
  margin-top: 2px;
  color: var(--muted);
  font-size: 10px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(300px, 0.85fr);
  gap: 20px;
  padding-top: 20px;
  min-width: 0;
}
.dashboard-grid > section {
  margin: 0;
  padding: 25px;
  max-width: none;
  border: 1px solid var(--line);
  border-radius: 20px;
  background: var(--surface);
  box-shadow: var(--panel-shadow);
  min-width: 0;
}
.panel-header {
  align-items: center;
}
.live-indicator {
  color: var(--muted);
  font-size: 10px;
  font-weight: 650;
  background: var(--surface-soft);
  border-radius: 999px;
  padding: 6px 9px;
}
.live-indicator i {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 5px;
  border-radius: 50%;
  background: var(--accent);
}
.chart-summary {
  display: flex;
  align-items: flex-end;
  gap: 18px;
  margin: 28px 0 8px;
}
.chart-summary div {
  display: grid;
  gap: 3px;
}
.chart-summary small {
  color: var(--muted);
  font-size: 10px;
}
.chart-summary strong {
  font-size: 18px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.035em;
}
.chart-summary > span {
  padding-bottom: 2px;
  color: var(--muted);
}
.chart-summary .chart-change {
  margin-left: auto;
  text-align: right;
}
.chart-change strong {
  color: var(--accent);
}
.mock-chart {
  height: 166px;
  position: relative;
  border-bottom: 1px solid var(--line);
}
.mock-chart::before,
.mock-chart::after {
  content: "";
  position: absolute;
  inset-inline: 0;
  border-top: 1px dashed var(--line);
}
.mock-chart::before {
  top: 35%;
}
.mock-chart::after {
  top: 68%;
}
.mock-chart svg {
  width: 100%;
  height: 145px;
  position: relative;
  z-index: 1;
  overflow: visible;
}
.chart-months {
  display: flex;
  justify-content: space-between;
  color: var(--muted);
  font-size: 9px;
  line-height: 1;
  font-weight: 700;
  letter-spacing: 0.035em;
}

.attention-panel {
  min-width: 0;
}
.count-badge {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--surface-soft);
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
}
.attention-list {
  margin-top: 16px;
}
.attention-list button {
  width: 100%;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 11px;
  border: 0;
  border-top: 1px solid var(--line);
  border-radius: 0;
  background: transparent;
  color: var(--ink);
  padding: 15px 4px;
  text-align: left;
  cursor: pointer;
  transition:
    background 0.18s ease,
    transform 0.18s ease;
}
.attention-list button:hover {
  background: var(--surface-soft);
  transform: translateX(3px);
}
.attention-list button > span:nth-child(2) {
  min-width: 0;
}
.attention-list strong,
.attention-list small {
  display: block;
}
.attention-list strong {
  font-size: 12px;
  font-weight: 720;
}
.attention-list small {
  color: var(--muted);
  font-size: 10px;
  margin-top: 3px;
  line-height: 1.4;
}
.attention-icon {
  width: 31px;
  height: 31px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  font-weight: 800;
}
.attention-icon.violet {
  background: #eee8fa;
  color: #7852b5;
}
.attention-icon.orange {
  background: #faeadc;
  color: #b86827;
}
.attention-icon.blue {
  background: #e2ecfa;
  color: #416eae;
}
[data-theme="dark"] .attention-icon.violet {
  background: #332844;
  color: #c6a7f3;
}
[data-theme="dark"] .attention-icon.orange {
  background: #402d20;
  color: #f1a569;
}
[data-theme="dark"] .attention-icon.blue {
  background: #24354d;
  color: #8bb6ee;
}

.activity-panel {
  grid-column: 1 / -1;
}
.text-button {
  border: 0;
  background: transparent;
  color: var(--accent);
  padding: 5px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}
.activity-table {
  margin-top: 18px;
}
.activity-row {
  display: grid;
  grid-template-columns: minmax(260px, 1.5fr) 1fr 100px 120px;
  gap: 18px;
  align-items: center;
  min-height: 53px;
  border-top: 1px solid var(--line);
  font-size: 11px;
  transition: background 0.18s ease;
}
.activity-row:not(.activity-head):hover {
  background: var(--surface-soft);
}
.activity-row > span:first-child {
  display: flex;
  align-items: center;
  gap: 10px;
}
.activity-row > span:last-child {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}
.activity-head {
  min-height: 32px;
  color: var(--muted);
  font-size: 9px;
  line-height: 1;
  font-weight: 720;
  letter-spacing: 0.045em;
}
.activity-mark {
  width: 26px;
  height: 26px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border-radius: 8px;
  font-style: normal;
  font-size: 10px;
}
.activity-mark.green {
  background: var(--accent-soft);
  color: var(--accent);
}
.activity-mark.blue {
  background: #e2ecfa;
  color: #416eae;
}
.activity-mark.orange {
  background: #faeadc;
  color: #b86827;
}
[data-theme="dark"] .activity-mark.blue {
  background: #24354d;
  color: #8bb6ee;
}
[data-theme="dark"] .activity-mark.orange {
  background: #402d20;
  color: #f1a569;
}
.positive {
  color: var(--accent);
}
.negative {
  color: var(--ink);
}

@media (max-width: 1050px) {
  .design-preview {
    grid-template-columns: 88px minmax(0, 1fr);
  }
  .preview-sidebar {
    padding-inline: 12px;
  }
  .preview-brand {
    justify-content: center;
    padding-inline: 0;
  }
  .preview-brand > span:last-child,
  .preview-sidebar nav button:not(.active),
  .preview-sidebar nav button.active {
    font-size: 0;
  }
  .preview-sidebar nav button {
    grid-template-columns: 1fr;
    justify-items: center;
    text-align: center;
  }
  .workspace > span:not(.avatar),
  .workspace + p {
    display: none;
  }
  .workspace {
    display: flex;
    justify-content: center;
  }
  .dashboard-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .activity-panel {
    grid-column: auto;
  }
}

@media (max-width: 720px) {
  .design-preview {
    display: block;
  }
  .preview-sidebar {
    position: static;
    height: auto;
    padding: 13px 16px;
    flex-direction: row;
    align-items: center;
    gap: 12px;
    overflow: hidden;
  }
  .preview-brand {
    padding: 0;
  }
  .preview-brand > span:last-child {
    display: none;
  }
  .preview-sidebar nav {
    display: flex;
    overflow-x: auto;
  }
  .preview-sidebar nav button,
  .preview-sidebar nav button:not(.active),
  .preview-sidebar nav button.active {
    width: auto;
    min-width: max-content;
    display: block;
    font-size: 11px;
    padding: 8px 10px;
  }
  .nav-icon,
  .sidebar-foot {
    display: none;
  }
  .preview-main {
    padding: 0 18px 32px;
  }
  .preview-topbar {
    min-height: 92px;
  }
  .context-label,
  .quick-add {
    display: none;
  }
  .theme-toggle {
    padding: 9px;
    font-size: 0;
  }
  .theme-toggle span {
    font-size: 18px;
  }
  .snapshot {
    padding: 24px 20px;
    border-radius: 20px;
  }
  .snapshot-heading {
    display: block;
  }
  .period-control {
    width: 100%;
    margin-top: 20px;
    overflow-x: auto;
  }
  .period-control button {
    flex: 1;
    white-space: nowrap;
  }
  .net-worth-row {
    display: block;
  }
  .delta {
    margin-top: 16px;
  }
  .allocation-legend {
    grid-template-columns: repeat(2, 1fr);
    row-gap: 13px;
  }
  .dashboard-grid > section {
    padding: 18px;
  }
  .chart-summary {
    gap: 10px;
  }
  .chart-summary .chart-change {
    display: none;
  }
  .activity-panel {
    overflow: hidden;
  }
  .activity-table {
    width: 100%;
    overflow-x: auto;
  }
  .activity-row {
    min-width: 650px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .design-preview,
  .preview-sidebar nav button,
  .allocation-bar span,
  .snapshot {
    transition: none;
    animation: none;
  }
}

@keyframes hero-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
