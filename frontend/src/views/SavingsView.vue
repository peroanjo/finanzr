<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { api, json } from "../api/client";
import LineChart from "../components/LineChart.vue";
import NavIcon from "../components/NavIcon.vue";
import AccountSnapshotChart from "../components/AccountSnapshotChart.vue";
import type {
  SavingsAccount,
  AccountChartSeries,
  SavingsSnapshot,
} from "../types/api";

type Range = "6m" | "12m" | "24m" | "all";

const { t, n, d, locale } = useI18n();

const colors = [
  "var(--fz-source-savings)",
  "var(--fz-source-manual-investments)",
  "var(--fz-source-stocks)",
  "var(--fz-source-crypto)",
  "var(--fz-source-funds)",
  "var(--fz-source-crowdfunding)",
];
const ranges = computed<Array<{ key: Range; label: string; months?: number }>>(
  () => [
    { key: "6m", label: t("savings.ranges.sixMonths"), months: 6 },
    { key: "12m", label: t("savings.ranges.oneYear"), months: 12 },
    { key: "24m", label: t("savings.ranges.twoYears"), months: 24 },
    { key: "all", label: t("savings.ranges.all") },
  ],
);
const accounts = ref<SavingsAccount[]>([]);
const history = ref<SavingsSnapshot[]>([]);
const loading = ref(true);
const error = ref("");
const range = ref<Range>("12m");
const historyAccount = ref("all");
const expandedAccount = ref<string | null>(null);
const accountDialog = ref<HTMLDialogElement>();
const snapshotDialog = ref<HTMLDialogElement>();
const accountMode = ref<"create" | "edit">("create");
const editingAccountId = ref<string | null>(null);
const accountName = ref("");
const accountBank = ref("");
const accountType = ref("Cuenta corriente");
const accountCurrency = ref("EUR");
const accountBusy = ref(false);
const accountError = ref("");
const accountDeleteArmed = ref(false);
const snapshotMode = ref<"create" | "edit">("create");
const snapshotOriginal = ref<{ accountId: string; date: string } | null>(null);
const snapshotAccountId = ref("");
const snapshotDate = ref(new Date().toISOString().slice(0, 7));
const snapshotBalance = ref("");
const snapshotContribution = ref("");
const snapshotInterest = ref("");
const snapshotBusy = ref(false);
const snapshotError = ref("");
const snapshotDeleteArmed = ref(false);

const allMonths = computed(() =>
  [...new Set(history.value.map((item) => item.date.slice(0, 7)))].sort(),
);
const accountRows = computed(() =>
  accounts.value.map((account, index) => {
    const rows = history.value
      .filter((item) => item.account_id === account.id)
      .sort((a, b) => a.date.localeCompare(b.date));
    const latest = rows.at(-1) ?? null;
    const previous = rows.at(-2) ?? null;
    const totalInterest = rows.reduce(
      (total, item) => total + item.interest,
      0,
    );
    return {
      account,
      color: colors[index % colors.length],
      rows,
      latest,
      balance: latest?.balance ?? 0,
      change: latest && previous ? latest.balance - previous.balance : 0,
      contribution: latest?.contribution ?? 0,
      lastInterest: latest?.interest ?? 0,
      totalInterest,
      periodInterest: rows
        .filter((item) => visibleMonths.value.includes(item.date.slice(0, 7)))
        .reduce((total, item) => total + item.interest, 0),
      remunerated:
        totalInterest > 0 ||
        account.type.toLocaleLowerCase().includes("remunerada") ||
        account.type.toLocaleLowerCase().includes("interest"),
    };
  }),
);
const totalBalance = computed(() =>
  accountRows.value.reduce((total, item) => total + item.balance, 0),
);
const totalInterest = computed(() =>
  history.value.reduce((total, item) => total + item.interest, 0),
);
const remuneratedBalance = computed(() =>
  accountRows.value
    .filter((item) => item.remunerated)
    .reduce((total, item) => total + item.balance, 0),
);
const remuneratedShare = computed(() =>
  totalBalance.value ? remuneratedBalance.value / totalBalance.value : 0,
);

function accountTypeLabel(value: string) {
  const labels: Record<string, string> = {
    "Cuenta corriente": t("savings.accountTypes.current"),
    "Current account": t("savings.accountTypes.current"),
    "Cuenta remunerada": t("savings.accountTypes.interestBearing"),
    "Interest-bearing account": t("savings.accountTypes.interestBearing"),
    "Cuenta de ahorro": t("savings.accountTypes.savings"),
    "Savings account": t("savings.accountTypes.savings"),
    Efectivo: t("savings.accountTypes.cash"),
    Cash: t("savings.accountTypes.cash"),
  };
  return labels[value] ?? value;
}
const visibleMonths = computed(() => {
  const months = ranges.value.find((item) => item.key === range.value)?.months;
  const latest = allMonths.value.at(-1);
  if (!months || !latest) return allMonths.value;
  const [year, month] = latest.split("-").map(Number);
  const cutoff = new Date(year, month - months, 1);
  const cutoffMonth = `${cutoff.getFullYear()}-${String(cutoff.getMonth() + 1).padStart(2, "0")}`;
  return allMonths.value.filter((value) => value >= cutoffMonth);
});
const visibleInterest = computed(() =>
  history.value
    .filter((item) => visibleMonths.value.includes(item.date.slice(0, 7)))
    .reduce((total, item) => total + item.interest, 0),
);
const activeRangeLabel = computed(
  () => ranges.value.find((item) => item.key === range.value)?.label ?? "",
);
const latestMonthTotal = computed(() =>
  monthTotal(visibleMonths.value.at(-1) ?? ""),
);
const periodChange = computed(
  () => latestMonthTotal.value - monthTotal(visibleMonths.value[0] ?? ""),
);
const periodChangePercent = computed(() => {
  const start = monthTotal(visibleMonths.value[0] ?? "");
  return start ? periodChange.value / Math.abs(start) : null;
});
const periodDates = computed(() =>
  visibleMonths.value.length
    ? `${monthLabel(visibleMonths.value[0])} – ${monthLabel(visibleMonths.value.at(-1)!)}`
    : "",
);
const balanceSeries = computed(() =>
  accountRows.value.map((row) => ({
    key: row.account.id,
    label: row.account.name,
    color: row.color,
    values: visibleMonths.value.map((month) => balanceAt(row.rows, month)),
  })),
);
const interestSeries = computed<AccountChartSeries[]>(() =>
  accountRows.value
    .filter((row) => row.remunerated)
    .map((row) => ({
      label: row.account.name,
      color: row.color,
      values: visibleMonths.value.map((month) =>
        row.rows
          .filter((item) => item.date.startsWith(month))
          .reduce((total, item) => total + item.interest, 0),
      ),
    })),
);
const chartLabels = computed(() => visibleMonths.value.map(monthLabel));
const displayedHistory = computed(() =>
  [...history.value]
    .filter(
      (item) =>
        historyAccount.value === "all" ||
        item.account_id === historyAccount.value,
    )
    .sort((a, b) => b.date.localeCompare(a.date)),
);

const money = (value: number) => n(value, "currency");
const percentage = (value: number) => n(value, "percent");

function balanceAt(rows: SavingsSnapshot[], month: string) {
  return (
    [...rows].reverse().find((item) => item.date.slice(0, 7) <= month)
      ?.balance ?? 0
  );
}

function monthTotal(month: string) {
  if (!month) return 0;
  return accountRows.value.reduce(
    (total, row) => total + balanceAt(row.rows, month),
    0,
  );
}

function monthLabel(month: string) {
  const [year, value] = month.split("-").map(Number);
  return new Intl.DateTimeFormat(locale.value, {
    month: "short",
    year: "2-digit",
  })
    .format(new Date(year, value - 1, 1))
    .replace(".", "");
}

function displayDate(value: string) {
  const [year, month, day] = value.slice(0, 10).split("-");
  return year && month && day
    ? d(new Date(Number(year), Number(month) - 1, Number(day)), "short")
    : "—";
}

function monthEndDate(monthValue: string) {
  const [year, month] = monthValue.split("-").map(Number);
  const day = new Date(year, month, 0).getDate();
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function signedMoney(value: number) {
  return `${value >= 0 ? "+" : "−"}${money(Math.abs(value))}`;
}

function accountNameFor(id: string) {
  return (
    accounts.value.find((item) => item.id === id)?.name ??
    t("savings.accountFallback", { id })
  );
}

function accountColor(id: string) {
  return (
    accountRows.value.find((item) => item.account.id === id)?.color ?? colors[0]
  );
}

function openAccountCreate() {
  accountMode.value = "create";
  editingAccountId.value = null;
  accountName.value = "";
  accountBank.value = "";
  accountType.value = "Cuenta corriente";
  accountCurrency.value = "EUR";
  accountError.value = "";
  accountDeleteArmed.value = false;
  accountDialog.value?.showModal();
}

function openAccountEdit(account: SavingsAccount) {
  accountMode.value = "edit";
  editingAccountId.value = account.id;
  accountName.value = account.name;
  accountBank.value = account.bank;
  accountType.value = account.type;
  accountCurrency.value = account.currency || "EUR";
  accountError.value = "";
  accountDeleteArmed.value = false;
  accountDialog.value?.showModal();
}

async function saveAccount() {
  accountBusy.value = true;
  accountError.value = "";
  try {
    const path =
      editingAccountId.value === null
        ? "/savings/accounts"
        : `/savings/accounts/${editingAccountId.value}`;
    const method = editingAccountId.value === null ? "POST" : "PUT";
    await api(
      path,
      json(method, {
        name: accountName.value,
        bank: accountBank.value,
        type: accountType.value,
        currency: accountCurrency.value.trim().toUpperCase(),
      }),
    );
    accountDialog.value?.close();
    await load();
  } catch (reason) {
    accountError.value =
      reason instanceof Error
        ? reason.message
        : t("savings.errors.saveAccount");
  } finally {
    accountBusy.value = false;
  }
}

async function removeAccount() {
  if (!accountDeleteArmed.value) {
    accountDeleteArmed.value = true;
    return;
  }
  if (editingAccountId.value === null) return;
  accountBusy.value = true;
  try {
    await api(`/savings/accounts/${editingAccountId.value}`, {
      method: "DELETE",
    });
    accountDialog.value?.close();
    await load();
  } catch (reason) {
    accountError.value =
      reason instanceof Error
        ? reason.message
        : t("savings.errors.deleteAccount");
  } finally {
    accountBusy.value = false;
  }
}

function openSnapshotCreate(accountId?: string) {
  snapshotMode.value = "create";
  snapshotOriginal.value = null;
  snapshotAccountId.value = String(accountId ?? accounts.value[0]?.id ?? "");
  snapshotDate.value = new Date().toISOString().slice(0, 7);
  const selected = accountRows.value.find(
    (item) => item.account.id === snapshotAccountId.value,
  );
  snapshotBalance.value = selected?.latest
    ? String(selected.latest.balance_original ?? selected.latest.balance)
    : "";
  snapshotContribution.value = "";
  snapshotInterest.value = "";
  snapshotError.value = "";
  snapshotDeleteArmed.value = false;
  snapshotDialog.value?.showModal();
}

function openSnapshotEdit(item: SavingsSnapshot) {
  snapshotMode.value = "edit";
  snapshotOriginal.value = { accountId: item.account_id, date: item.date };
  snapshotAccountId.value = item.account_id;
  snapshotDate.value = item.date.slice(0, 7);
  snapshotBalance.value = String(item.balance_original ?? item.balance);
  snapshotContribution.value = item.contribution_original
    ? String(item.contribution_original)
    : "";
  snapshotInterest.value = item.interest_original
    ? String(item.interest_original)
    : "";
  snapshotError.value = "";
  snapshotDeleteArmed.value = false;
  snapshotDialog.value?.showModal();
}

async function saveSnapshot() {
  snapshotBusy.value = true;
  snapshotError.value = "";
  try {
    const newDate = monthEndDate(snapshotDate.value);
    const newAccountId = snapshotAccountId.value;
    await api(
      "/savings/history",
      json("POST", {
        date: newDate,
        account_id: newAccountId,
        balance: Number(snapshotBalance.value),
        contribution: Number(snapshotContribution.value || 0),
        interest: Number(snapshotInterest.value || 0),
      }),
    );
    if (
      snapshotOriginal.value &&
      (snapshotOriginal.value.accountId !== newAccountId ||
        snapshotOriginal.value.date !== newDate)
    ) {
      await api(
        `/savings/history/${snapshotOriginal.value.accountId}/${snapshotOriginal.value.date}`,
        { method: "DELETE" },
      );
    }
    snapshotDialog.value?.close();
    await load();
  } catch (reason) {
    snapshotError.value =
      reason instanceof Error
        ? reason.message
        : t("savings.errors.saveSnapshot");
  } finally {
    snapshotBusy.value = false;
  }
}

async function removeSnapshot() {
  if (!snapshotDeleteArmed.value) {
    snapshotDeleteArmed.value = true;
    return;
  }
  if (!snapshotOriginal.value) return;
  snapshotBusy.value = true;
  try {
    await api(
      `/savings/history/${snapshotOriginal.value.accountId}/${snapshotOriginal.value.date}`,
      { method: "DELETE" },
    );
    snapshotDialog.value?.close();
    await load();
  } catch (reason) {
    snapshotError.value =
      reason instanceof Error
        ? reason.message
        : t("savings.errors.deleteSnapshot");
  } finally {
    snapshotBusy.value = false;
  }
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    [accounts.value, history.value] = await Promise.all([
      api<SavingsAccount[]>("/savings/accounts"),
      api<SavingsSnapshot[]>("/savings/history"),
    ]);
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : t("savings.errors.load");
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="savings-page">
    <div
      v-if="loading"
      class="savings-loading"
      :aria-label="t('savings.loading')"
    >
      <div />
      <div />
      <div />
    </div>
    <article v-else-if="error" class="savings-error" role="alert">
      <strong>{{ t("savings.errors.title") }}</strong>
      <p>{{ error }}</p>
      <button type="button" @click="load">{{ t("common.retry") }}</button>
    </article>

    <template v-else>
      <header class="savings-heading">
        <h1>{{ t("savings.redesign.title") }}</h1>
        <div class="hero-actions">
          <button type="button" @click="openAccountCreate">
            ＋ {{ t("savings.actions.newAccount") }}
          </button>
          <button
            class="primary"
            type="button"
            :disabled="!accounts.length"
            @click="openSnapshotCreate()"
          >
            ＋ {{ t("savings.redesign.recordBalance") }}
          </button>
        </div>
      </header>
      <div class="liquidity-grid">
        <article class="liquidity-hero" aria-labelledby="savings-total-title">
          <header>
            <h2 id="savings-total-title">
              {{ t("savings.redesign.recordedBalance") }}
            </h2>
            <div
              class="range-control"
              role="group"
              :aria-label="t('overview.periodAria')"
            >
              <button
                v-for="item in ranges"
                :key="item.key"
                type="button"
                :class="{ active: range === item.key }"
                :aria-pressed="range === item.key"
                @click="range = item.key"
              >
                {{ item.label }}
              </button>
            </div>
          </header>
          <div class="cash-total">
            <strong>{{ money(totalBalance) }}</strong>
            <div class="savings-delta" :class="{ negative: periodChange < 0 }">
              <template v-if="visibleMonths.length > 1">
                <strong
                  >{{ signedMoney(periodChange)
                  }}<template v-if="periodChangePercent !== null">
                    · {{ percentage(periodChangePercent) }}</template
                  ></strong
                >
                <small>{{ periodDates }}</small>
              </template>
              <small v-else>{{ t("savings.redesign.needHistory") }}</small>
            </div>
          </div>
          <div class="savings-trend">
            <LineChart
              v-if="visibleMonths.length"
              :labels="chartLabels"
              :values="visibleMonths.map(monthTotal)"
              :series="balanceSeries"
              featured
              :total-label="t('savings.redesign.recordedBalance')"
              :aria-label="t('savings.charts.balanceTitle')"
            />
            <p v-else class="empty-chart">
              {{ t("savings.redesign.noHistory") }}
            </p>
          </div>
          <div class="liquidity-legend">
            <span
              ><i class="total-marker" />{{
                t("savings.redesign.recordedBalance")
              }}</span
            >
            <span v-for="item in accountRows" :key="item.account.id"
              ><i :style="{ background: item.color }" />{{
                item.account.name
              }}</span
            >
          </div>
        </article>
        <section
          class="savings-essentials"
          aria-labelledby="savings-essentials-title"
        >
          <h2 id="savings-essentials-title">{{ t("overview.essentials") }}</h2>
          <dl class="insight-grid savings-kpis">
            <div class="insight-card">
              <dt>
                <NavIcon name="wallet" class="insight-icon" />
                <span>{{ t("savings.hero.interestBearingBalance") }}</span>
              </dt>
              <dd class="insight-value">{{ money(remuneratedBalance) }}</dd>
              <dd class="insight-detail">
                {{
                  t("savings.hero.ofCash", {
                    share: percentage(remuneratedShare),
                  })
                }}
              </dd>
            </div>
            <div class="insight-card interest-insight">
              <dt>
                <NavIcon name="trend" class="insight-icon" />
                <span>{{ t("savings.redesign.periodInterest") }}</span>
              </dt>
              <dd class="insight-value">{{ signedMoney(visibleInterest) }}</dd>
              <dd class="insight-detail">
                {{ periodDates || activeRangeLabel }} ·
                {{
                  t("savings.hero.sinceStart", { total: money(totalInterest) })
                }}
              </dd>
            </div>
            <div class="insight-card accounts-insight">
              <dt>
                <NavIcon name="building" class="insight-icon" />
                <span>{{ t("savings.hero.activeAccounts") }}</span>
              </dt>
              <dd class="insight-value">{{ accounts.length }}</dd>
              <dd class="insight-detail">
                {{
                  t("savings.hero.earningInterest", {
                    count: accountRows.filter((item) => item.remunerated)
                      .length,
                  })
                }}
              </dd>
            </div>
          </dl>
        </section>
      </div>

      <div class="accounts-heading">
        <h2>{{ t("savings.redesign.yourAccounts") }}</h2>
        <p>{{ t("savings.redesign.balanceNote") }}</p>
      </div>
      <div class="account-grid">
        <div v-if="!accountRows.length" class="savings-panel empty-accounts">
          <h3>{{ t("savings.redesign.noAccounts") }}</h3>
          <p>{{ t("savings.redesign.createFirst") }}</p>
          <button type="button" @click="openAccountCreate">
            ＋ {{ t("savings.actions.newAccount") }}
          </button>
        </div>
        <article
          v-for="item in accountRows"
          :key="item.account.id"
          class="cash-account"
        >
          <div class="account-row">
            <button
              class="account-identity"
              type="button"
              :aria-expanded="expandedAccount === item.account.id"
              :aria-controls="`account-detail-${item.account.id}`"
              @click="
                expandedAccount =
                  expandedAccount === item.account.id ? null : item.account.id
              "
            >
              <span class="bank-mark" :style="{ color: item.color }">{{
                item.account.name.slice(0, 2).toUpperCase()
              }}</span>
              <span
                ><strong>{{ item.account.name }}</strong
                ><small>{{
                  [item.account.bank, accountTypeLabel(item.account.type)]
                    .filter(Boolean)
                    .join(" · ")
                }}</small></span
              >
              <span aria-hidden="true">{{
                expandedAccount === item.account.id ? "⌃" : "⌄"
              }}</span>
            </button>
            <div class="account-balance">
              <span>{{ t("savings.accounts.currentBalance") }}</span>
              <strong>{{ item.latest ? money(item.balance) : "—" }}</strong>
              <div class="account-rail" aria-hidden="true">
                <i
                  :style="{
                    width: `${totalBalance > 0 ? Math.max(0, Math.min(100, (item.balance / totalBalance) * 100)) : 0}%`,
                    background: item.color,
                  }"
                />
              </div>
            </div>
            <div class="account-period-interest">
              <small>{{ t("savings.redesign.periodInterest") }}</small
              ><strong>{{ money(item.periodInterest) }}</strong>
            </div>
            <div class="account-updated">
              <small>{{ t("savings.redesign.lastRecord") }}</small
              ><span>{{
                item.latest ? displayDate(item.latest.date) : t("common.noData")
              }}</span>
            </div>
            <button
              class="update-balance"
              type="button"
              @click="openSnapshotCreate(item.account.id)"
            >
              {{ t("savings.actions.updateBalance") }}
            </button>
            <button
              class="edit-account"
              type="button"
              :aria-label="
                t('savings.actions.editNamed', { name: item.account.name })
              "
              @click="openAccountEdit(item.account)"
            >
              ⋯
            </button>
          </div>
          <div
            v-if="expandedAccount === item.account.id"
            :id="`account-detail-${item.account.id}`"
            class="account-detail"
          >
            <div class="account-detail-heading">
              <h3>{{ t("savings.charts.balanceTitle") }}</h3>
              <span>{{ activeRangeLabel }}</span>
            </div>
            <div class="account-detail-chart">
              <LineChart
                v-if="item.rows.length"
                :labels="chartLabels"
                :values="
                  visibleMonths.map((month) => balanceAt(item.rows, month))
                "
                :total-label="item.account.name"
                :aria-label="t('savings.charts.balanceTitle')"
              />
              <p v-else>{{ t("savings.redesign.noHistory") }}</p>
            </div>
            <div class="account-detail-history">
              <button
                v-for="entry in [...item.rows].reverse()"
                :key="entry.date"
                type="button"
                @click="openSnapshotEdit(entry)"
              >
                <span>{{ displayDate(entry.date) }}</span>
                <span
                  >{{ t("savings.history.balance") }}
                  <strong>{{ money(entry.balance) }}</strong></span
                >
                <span
                  >{{ t("savings.redesign.contribution") }}
                  <strong>{{ money(entry.contribution) }}</strong></span
                >
                <span
                  >{{ t("savings.history.interest") }}
                  <strong>{{ money(entry.interest) }}</strong></span
                >
              </button>
            </div>
          </div>
        </article>
      </div>

      <div class="lower-grid">
        <article class="savings-panel interest-panel">
          <header>
            <div>
              <p class="section-label">
                {{ t("savings.charts.interestEyebrow") }}
              </p>
              <h2>{{ t("savings.charts.interestTitle") }}</h2>
            </div>
            <span>{{ money(visibleInterest) }} · {{ activeRangeLabel }}</span>
          </header>
          <AccountSnapshotChart
            v-if="interestSeries.length"
            :labels="chartLabels"
            :series="interestSeries"
            mode="interest"
            :minimum-font-size="10"
          />
          <div v-else class="empty-chart">
            {{ t("savings.charts.noInterest") }}
          </div>
        </article>

        <article class="savings-panel history-panel">
          <header>
            <div>
              <p class="section-label">{{ t("savings.history.eyebrow") }}</p>
              <h2>
                {{ t("savings.history.title") }}
                <span>{{ displayedHistory.length }}</span>
              </h2>
            </div>
            <select
              v-model="historyAccount"
              :aria-label="t('savings.history.filterAria')"
            >
              <option value="all">
                {{ t("savings.history.allAccounts") }}
              </option>
              <option
                v-for="item in accounts"
                :key="item.id"
                :value="String(item.id)"
              >
                {{ item.name }}
              </option>
            </select>
          </header>
          <div class="history-list">
            <p v-if="!displayedHistory.length" class="empty-chart">
              {{ t("savings.redesign.noHistory") }}
            </p>
            <button
              v-for="item in displayedHistory"
              :key="`${item.account_id}:${item.date}`"
              type="button"
              @click="openSnapshotEdit(item)"
            >
              <i :style="{ background: accountColor(item.account_id) }" />
              <span
                ><strong>{{ accountNameFor(item.account_id) }}</strong
                ><small>{{ displayDate(item.date) }}</small></span
              >
              <span
                ><small>{{ t("savings.history.balance") }}</small
                ><strong>{{ money(item.balance) }}</strong></span
              >
              <span
                ><small>{{ t("savings.redesign.contribution") }}</small
                ><strong
                  :class="{
                    positive: item.contribution > 0,
                    negative: item.contribution < 0,
                  }"
                  >{{
                    item.contribution ? signedMoney(item.contribution) : "—"
                  }}</strong
                ></span
              >
              <span
                ><small>{{ t("savings.history.interest") }}</small
                ><strong :class="{ positive: item.interest > 0 }">{{
                  item.interest ? money(item.interest) : "—"
                }}</strong></span
              >
            </button>
          </div>
        </article>
      </div>
    </template>

    <dialog ref="accountDialog" class="savings-dialog">
      <form @submit.prevent="saveAccount">
        <header>
          <div>
            <p class="section-label">
              {{ t("savings.accountDialog.eyebrow") }}
            </p>
            <h2>
              {{
                accountMode === "create"
                  ? t("savings.accountDialog.createTitle")
                  : t("savings.accountDialog.editTitle")
              }}
            </h2>
          </div>
        </header>
        <div class="dialog-fields">
          <label
            ><span>{{ t("common.name") }}</span
            ><input v-model="accountName" required /></label
          ><label
            ><span>{{ t("savings.accountDialog.bank") }}</span
            ><input v-model="accountBank" /></label
          ><label
            ><span>{{ t("savings.accountDialog.currency") }}</span
            ><input
              v-model="accountCurrency"
              maxlength="3"
              minlength="3"
              pattern="[A-Za-z]{3}"
              required /></label
          ><label class="wide"
            ><span>{{ t("common.type") }}</span
            ><select v-model="accountType">
              <option value="Cuenta corriente">
                {{ t("savings.accountTypes.current") }}
              </option>
              <option value="Cuenta remunerada">
                {{ t("savings.accountTypes.interestBearing") }}
              </option>
              <option value="Cuenta de ahorro">
                {{ t("savings.accountTypes.savings") }}
              </option>
              <option value="Efectivo">
                {{ t("savings.accountTypes.cash") }}
              </option>
            </select></label
          >
        </div>
        <p v-if="accountError" class="dialog-error">{{ accountError }}</p>
        <footer>
          <button
            v-if="accountMode === 'edit'"
            class="danger"
            type="button"
            @click="removeAccount"
          >
            {{
              accountDeleteArmed
                ? t("common.confirmDeletion")
                : t("savings.actions.deleteAccount")
            }}</button
          ><i /><button type="button" @click="accountDialog?.close()">
            {{ t("common.cancel") }}</button
          ><button class="primary" type="submit">
            {{
              accountBusy
                ? t("common.saving")
                : t("savings.actions.saveAccount")
            }}
          </button>
        </footer>
      </form>
    </dialog>

    <dialog ref="snapshotDialog" class="savings-dialog">
      <form @submit.prevent="saveSnapshot">
        <header>
          <div>
            <p class="section-label">
              {{ t("savings.snapshotDialog.eyebrow") }}
            </p>
            <h2>
              {{
                snapshotMode === "create"
                  ? t("savings.snapshotDialog.createTitle")
                  : t("savings.snapshotDialog.editTitle")
              }}
            </h2>
          </div>
        </header>
        <div class="dialog-fields">
          <label
            ><span>{{ t("common.account") }}</span
            ><select v-model="snapshotAccountId" required>
              <option
                v-for="item in accounts"
                :key="item.id"
                :value="String(item.id)"
              >
                {{ item.name }}
              </option>
            </select></label
          ><label
            ><span>{{ t("common.month") }}</span
            ><input v-model="snapshotDate" type="month" required /></label
          ><label
            ><span>{{ t("savings.snapshotDialog.closingBalance") }}</span
            ><input
              v-model="snapshotBalance"
              type="number"
              step="0.01"
              required /></label
          ><label
            ><span>{{ t("savings.snapshotDialog.contribution") }}</span
            ><input
              v-model="snapshotContribution"
              type="number"
              step="0.01" /></label
          ><label class="wide"
            ><span>{{ t("savings.snapshotDialog.interest") }}</span
            ><input
              v-model="snapshotInterest"
              type="number"
              min="0"
              step="0.01"
          /></label>
        </div>
        <p v-if="snapshotError" class="dialog-error">{{ snapshotError }}</p>
        <footer>
          <button
            v-if="snapshotMode === 'edit'"
            class="danger"
            type="button"
            @click="removeSnapshot"
          >
            {{
              snapshotDeleteArmed
                ? t("common.confirmDeletion")
                : t("savings.actions.deleteSnapshot")
            }}</button
          ><i /><button type="button" @click="snapshotDialog?.close()">
            {{ t("common.cancel") }}</button
          ><button class="primary" type="submit">
            {{
              snapshotBusy
                ? t("common.saving")
                : t("savings.actions.saveSnapshot")
            }}
          </button>
        </footer>
      </form>
    </dialog>
  </section>
</template>

<style scoped>
.savings-page {
  width: min(100%, 1440px);
  margin: 0 auto;
  padding: 8px 48px 56px;
  --cash-blue: var(--fz-accent);
  container: savings / inline-size;
  font-size: 13px;
}
.savings-heading,
.accounts-heading,
.liquidity-hero > header,
.savings-panel > header,
.account-detail-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.savings-heading {
  margin-bottom: 20px;
}
h1,
h2,
h3,
p {
  margin: 0;
}
h1 {
  font-size: 22px;
  letter-spacing: -0.04em;
}
h2 {
  font-size: 18px;
  letter-spacing: -0.03em;
}
h3 {
  font-size: 14px;
}
button {
  cursor: pointer;
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
.hero-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.hero-actions button,
.update-balance,
.edit-account,
.empty-accounts button {
  min-height: 40px;
  padding: 9px 13px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font-size: 12px;
  font-weight: 650;
}
.hero-actions .primary,
.empty-accounts button {
  background: var(--fz-accent);
  border-color: var(--fz-accent);
  color: var(--fz-canvas);
}
.liquidity-hero,
.savings-panel,
.cash-account,
.savings-error {
  background: var(--fz-surface);
  border: 1px solid var(--fz-line);
  border-radius: 20px;
}
.liquidity-grid {
  display: grid;
  gap: 20px;
}
.liquidity-hero {
  min-width: 0;
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background:
    radial-gradient(
      ellipse at 95% 0%,
      color-mix(in srgb, var(--fz-accent) 12%, transparent),
      transparent 60%
    ),
    var(--fz-surface);
  box-shadow: var(--fz-shadow);
}
.liquidity-hero h2 {
  color: var(--fz-muted);
  font-size: 15px;
  font-weight: 600;
}
.range-control {
  display: flex;
  padding: 3px;
  gap: 2px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
}
.range-control button {
  min-height: 32px;
  padding: 6px 10px;
  font-size: 12px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--fz-muted);
}
.range-control button.active {
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 2px 6px #00000008;
}
.cash-total {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}
.cash-total > strong {
  font-size: clamp(32px, 3.4vw, 52px);
  font-weight: 600;
  letter-spacing: -0.045em;
  line-height: 1.1;
}
.savings-delta {
  display: grid;
  gap: 5px;
  color: var(--fz-accent);
}
.savings-delta strong {
  font-size: 15px;
}
.savings-delta small {
  color: var(--fz-muted);
  font-size: 12px;
}
.negative {
  color: var(--fz-negative);
}
.positive {
  color: var(--fz-positive);
}
.savings-trend {
  height: 236px;
  padding-top: 16px;
  border-top: 1px solid var(--fz-line);
  min-width: 0;
}
.savings-trend :deep(.line-chart),
.account-detail-chart :deep(.line-chart) {
  height: 100%;
}
.liquidity-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 20px;
  color: var(--fz-muted);
  font-size: 11px;
}
.liquidity-legend span {
  display: flex;
  align-items: center;
  gap: 7px;
}
.liquidity-legend i {
  width: 12px;
  height: 3px;
  border-radius: 2px;
}
.liquidity-legend .total-marker {
  background: var(--fz-accent);
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.accounts-heading {
  margin: 30px 0 14px;
}
.accounts-heading p {
  color: var(--fz-muted);
  font-size: 12px;
}
.account-grid {
  display: grid;
  gap: 10px;
}
.cash-account {
  min-width: 0;
  border-radius: 14px;
  overflow: hidden;
}
.account-row {
  display: grid;
  grid-template-columns:
    minmax(160px, 1.5fr) minmax(130px, 1fr) minmax(105px, 0.8fr)
    minmax(100px, 0.8fr) auto 40px;
  gap: 18px;
  align-items: center;
  padding: 20px;
}
.account-identity {
  display: flex;
  gap: 12px;
  align-items: center;
  min-width: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--fz-ink);
  text-align: left;
}
.account-identity > span:nth-child(2) {
  min-width: 0;
  flex: 1;
}
.account-identity strong {
  font-size: 14px;
  overflow-wrap: anywhere;
}
.account-identity small {
  display: block;
  margin-top: 4px;
  color: var(--fz-muted);
  font-size: 11px;
  overflow-wrap: anywhere;
}
.bank-mark {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
  font-size: 12px;
  font-weight: 700;
}
.account-balance,
.account-period-interest,
.account-updated {
  display: grid;
  gap: 5px;
  min-width: 0;
}
.account-balance > span,
.account-period-interest small,
.account-updated small {
  color: var(--fz-muted);
  font-size: 11px;
}
.account-balance strong {
  font-size: 19px;
  font-weight: 650;
  letter-spacing: -0.03em;
}
.account-row strong,
.cash-total,
.savings-kpis strong {
  font-variant-numeric: tabular-nums;
}
.account-rail {
  height: 3px;
  background: var(--fz-surface-soft);
  border-radius: 9px;
  overflow: hidden;
}
.account-rail i {
  display: block;
  height: 100%;
}
.edit-account {
  padding: 6px;
  font-size: 20px;
}
.update-balance:hover,
.edit-account:hover,
.hero-actions button:not(.primary):hover {
  background: var(--fz-surface-soft);
}
.account-detail {
  padding: 20px;
  border-top: 1px solid var(--fz-line);
  background: color-mix(in srgb, var(--fz-surface-soft) 40%, var(--fz-surface));
}
.account-detail-heading span {
  color: var(--fz-muted);
  font-size: 12px;
}
.account-detail-chart {
  height: 190px;
  margin: 16px 0;
}
.account-detail-history {
  max-height: 250px;
  overflow: auto;
}
.account-detail-history button {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  width: 100%;
  padding: 12px 0;
  text-align: left;
  color: var(--fz-muted);
  background: transparent;
  border: 0;
  border-top: 1px solid var(--fz-line);
  font-size: 12px;
}
.account-detail-history strong {
  display: block;
  margin-top: 3px;
  color: var(--fz-ink);
}
.savings-essentials {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.savings-essentials h2 {
  font-weight: 650;
  letter-spacing: -0.035em;
}
.savings-kpis {
  grid-template-columns: minmax(0, 1fr);
  gap: 10px;
  flex: 1;
}
.savings-kpis .insight-card {
  padding: 14px 16px;
}
.savings-kpis .insight-value {
  margin-top: 7px;
}
.savings-kpis .insight-detail {
  overflow-wrap: anywhere;
}
.savings-kpis .accounts-insight {
  --insight-accent: var(--fz-source-stocks);
}
@container savings (560px <= width < 760px) {
  .savings-kpis {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@container savings (width >= 760px) {
  .liquidity-grid {
    grid-template-columns: minmax(0, 1fr) minmax(240px, 28%);
  }
  .savings-trend {
    flex: 1 0 236px;
  }
}
.lower-grid {
  display: grid;
  gap: 20px;
  margin-top: 24px;
}
.savings-panel {
  padding: 24px;
  min-width: 0;
}
.section-label {
  margin-bottom: 6px;
  color: var(--fz-muted);
  font-size: 11px;
}
.interest-panel > header > span,
.history-panel h2 span {
  color: var(--fz-muted);
  font-size: 12px;
}
.history-panel select {
  padding: 9px;
  max-width: 100%;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
}
.history-list {
  max-height: 400px;
  overflow: auto;
  margin-top: 18px;
}
.history-list > button {
  display: grid;
  grid-template-columns: 4px minmax(110px, 1.5fr) repeat(3, minmax(90px, 1fr));
  gap: 16px;
  align-items: center;
  width: 100%;
  min-width: 550px;
  padding: 13px 4px;
  border: 0;
  border-bottom: 1px solid var(--fz-line);
  background: transparent;
  color: var(--fz-ink);
  text-align: left;
}
.history-list > button:hover,
.account-detail-history button:hover {
  background: var(--fz-surface-soft);
}
.history-list i {
  height: 28px;
  border-radius: 3px;
}
.history-list span {
  display: grid;
  gap: 4px;
}
.history-list small {
  font-size: 11px;
  color: var(--fz-muted);
}
.history-list strong {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.empty-chart {
  min-height: 160px;
  display: grid;
  place-content: center;
  color: var(--fz-muted);
  font-size: 13px;
}
.empty-accounts {
  display: grid;
  justify-items: start;
  gap: 14px;
}
.empty-accounts p {
  color: var(--fz-muted);
}
.savings-loading {
  display: grid;
  gap: 18px;
}
.savings-loading > div {
  height: 100px;
  border-radius: 20px;
  background: var(--fz-surface-soft);
}
.savings-loading > div:first-child {
  height: 370px;
}
.savings-error {
  padding: 24px;
}
.savings-dialog {
  width: min(590px, calc(100vw - 32px));
  padding: 0;
  border: 1px solid var(--fz-line);
  border-radius: 21px;
  background: var(--fz-surface);
  color: var(--fz-ink);
}
.savings-dialog::backdrop {
  background: rgba(5, 10, 8, 0.7);
  backdrop-filter: blur(5px);
}
.savings-dialog form {
  padding: 24px;
}
.savings-dialog header > button {
  width: 31px;
  height: 31px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
}
.dialog-fields {
  margin-top: 20px;
  padding: 17px;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  border-radius: 14px;
  background: var(--fz-surface-soft);
}
.dialog-fields label {
  display: grid;
  gap: 6px;
}
.dialog-fields label.wide {
  grid-column: 1/-1;
}
.dialog-fields span {
  color: var(--fz-muted);
  font-size: 8px;
}
.dialog-fields input,
.dialog-fields select {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font: inherit;
  font-size: 9px;
}
.dialog-error {
  color: var(--fz-negative);
  font-size: 9px;
}
.savings-dialog footer {
  margin-top: 19px;
  display: flex;
  gap: 9px;
}
.savings-dialog footer i {
  flex: 1;
}
.savings-dialog footer button {
  padding: 9px 12px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
}
.savings-dialog footer .primary {
  border-color: var(--cash-blue);
  background: var(--cash-blue);
  color: #fff;
}
.savings-dialog footer .danger {
  color: var(--fz-negative);
}
.dialog-fields span,
.dialog-fields input,
.dialog-fields select,
.dialog-error {
  font-size: 13px;
}
.savings-dialog footer .primary {
  color: var(--fz-canvas);
}
@media (max-width: 1200px) {
  .savings-page {
    padding-inline: 24px;
  }
  .account-row {
    grid-template-columns:
      minmax(150px, 1.5fr) minmax(120px, 1fr) minmax(95px, 0.8fr)
      auto 36px;
    gap: 12px;
  }
  .account-updated {
    grid-column: 1;
    grid-row: 2;
  }
}
@media (max-width: 720px) {
  .savings-page {
    padding: 8px 16px 32px;
  }
  .savings-heading {
    align-items: flex-start;
  }
  .hero-actions {
    width: 100%;
  }
  .hero-actions button {
    flex: 1;
    min-height: 44px;
  }
  .liquidity-hero,
  .savings-panel {
    padding: 20px 16px;
  }
  .savings-trend {
    height: 210px;
  }
  .account-row {
    grid-template-columns: minmax(0, 1fr) auto 36px;
    padding: 16px;
    gap: 14px 10px;
  }
  .account-identity {
    grid-column: 1 / 3;
  }
  .edit-account {
    grid-column: 3;
    grid-row: 1;
  }
  .account-balance {
    grid-column: 1 / 4;
    grid-row: 2;
  }
  .account-balance strong {
    font-size: 26px;
  }
  .account-period-interest {
    grid-column: 1;
    grid-row: 3;
  }
  .account-updated {
    grid-column: 2 / 4;
    grid-row: 3;
  }
  .update-balance {
    grid-column: 1 / 4;
    min-height: 44px;
  }
  .account-detail {
    padding: 16px;
  }
  .account-detail-history button {
    grid-template-columns: 1fr 1fr;
  }
  .dialog-fields {
    grid-template-columns: 1fr;
  }
  .dialog-fields label.wide {
    grid-column: auto;
  }
  .savings-dialog footer {
    flex-wrap: wrap;
  }
}
</style>
