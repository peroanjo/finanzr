<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { api, json } from "../api/client";
import AccountSnapshotChart from "../components/AccountSnapshotChart.vue";
import type {
  AccountChartSeries,
  InvestmentAccount,
  InvestmentSnapshot,
} from "../types/api";

type Range = "6m" | "12m" | "24m" | "all";

const { t, n, d, locale } = useI18n();

const colors = [
  "#5681d8",
  "#8f72d8",
  "#3ddc97",
  "#d88b59",
  "#50a9b7",
  "#d8ae4e",
];
const ranges = computed<Array<{ key: Range; label: string; months?: number }>>(
  () => [
    { key: "6m", label: t("investmentBalances.ranges.sixMonths"), months: 6 },
    { key: "12m", label: t("investmentBalances.ranges.oneYear"), months: 12 },
    { key: "24m", label: t("investmentBalances.ranges.twoYears"), months: 24 },
    { key: "all", label: t("investmentBalances.ranges.all") },
  ],
);

const accounts = ref<InvestmentAccount[]>([]);
const history = ref<InvestmentSnapshot[]>([]);
const loading = ref(true);
const error = ref("");
const range = ref<Range>("12m");
const historyAccount = ref("all");
const accountDialog = ref<HTMLDialogElement>();
const closeDialog = ref<HTMLDialogElement>();
const accountMode = ref<"create" | "edit">("create");
const editingAccountId = ref<string | null>(null);
const accountName = ref("");
const accountPlatform = ref("");
const accountType = ref("Cartera gestionada");
const accountCurrency = ref("EUR");
const accountBusy = ref(false);
const accountError = ref("");
const accountDeleteArmed = ref(false);
const closeMode = ref<"create" | "edit">("create");
const closeOriginal = ref<{ accountId: string; date: string } | null>(null);
const closeAccountId = ref("");
const closeMonth = ref(new Date().toISOString().slice(0, 7));
const closeValue = ref("");
const closeContribution = ref("");
const closePnl = ref("");
const closeBusy = ref(false);
const closeError = ref("");
const closeDeleteArmed = ref(false);

const months = computed(() =>
  [...new Set(history.value.map((item) => item.date.slice(0, 7)))].sort(),
);
const visibleMonths = computed(() => {
  const amount = ranges.value.find((item) => item.key === range.value)?.months;
  return amount ? months.value.slice(-amount) : months.value;
});
const latestMonth = computed(() => months.value.at(-1) ?? "");
function accountTypeLabel(value: string) {
  const labels: Record<string, string> = {
    "Cartera gestionada": t("investmentBalances.accountTypes.managedPortfolio"),
    "Managed portfolio": t("investmentBalances.accountTypes.managedPortfolio"),
    "Plan de pensiones": t("investmentBalances.accountTypes.pensionPlan"),
    "Pension plan": t("investmentBalances.accountTypes.pensionPlan"),
  };
  return labels[value] ?? value;
}
const rows = computed(() =>
  accounts.value.map((account, index) => {
    const snapshots = history.value
      .filter((item) => item.account_id === account.id)
      .sort((a, b) => a.date.localeCompare(b.date));
    const latest = snapshots.at(-1) ?? null;
    const previous = snapshots.at(-2) ?? null;
    const pnlTotal = snapshots.reduce(
      (total, item) => total + item.interest,
      0,
    );
    const contributionTotal = snapshots.reduce(
      (total, item) => total + item.contribution,
      0,
    );
    const base = previous
      ? previous.value + Math.max(latest?.contribution ?? 0, 0)
      : 0;
    return {
      account,
      color: colors[index % colors.length],
      snapshots,
      latest,
      previous,
      value: latest?.value ?? 0,
      contribution: latest?.contribution ?? 0,
      pnl: latest?.interest ?? 0,
      pnlTotal,
      contributionTotal,
      returnRate: base ? (latest?.interest ?? 0) / base : 0,
      upToDate: latest?.date.slice(0, 7) === latestMonth.value,
    };
  }),
);
const totalValue = computed(() =>
  rows.value.reduce((total, item) => total + item.value, 0),
);
const monthContribution = computed(() =>
  rows.value
    .filter((item) => item.latest?.date.slice(0, 7) === latestMonth.value)
    .reduce((total, item) => total + item.contribution, 0),
);
const monthPnl = computed(() =>
  rows.value
    .filter((item) => item.latest?.date.slice(0, 7) === latestMonth.value)
    .reduce((total, item) => total + item.pnl, 0),
);
const previousCapital = computed(() =>
  rows.value.reduce((total, item) => total + (item.previous?.value ?? 0), 0),
);
const monthReturn = computed(() => {
  const base = previousCapital.value + Math.max(monthContribution.value, 0);
  return base ? monthPnl.value / base : 0;
});
const accumulatedPnl = computed(() =>
  history.value.reduce((total, item) => total + item.interest, 0),
);
const pendingAccounts = computed(
  () => rows.value.filter((item) => !item.upToDate).length,
);
const chartLabels = computed(() => visibleMonths.value.map(monthLabel));
const valueSeries = computed<AccountChartSeries[]>(() =>
  rows.value.map((item) => ({
    label: item.account.name,
    color: item.color,
    values: visibleMonths.value.map((month) => valueAt(item.snapshots, month)),
  })),
);
const pnlSeries = computed<AccountChartSeries[]>(() =>
  rows.value.map((item) => ({
    label: item.account.name,
    color: item.color,
    values: visibleMonths.value.map((month) =>
      item.snapshots
        .filter((snapshot) => snapshot.date.startsWith(month))
        .reduce((total, snapshot) => total + snapshot.interest, 0),
    ),
  })),
);
const displayedHistory = computed(() =>
  [...history.value]
    .filter(
      (item) =>
        historyAccount.value === "all" ||
        item.account_id === historyAccount.value,
    )
    .sort((a, b) => b.date.localeCompare(a.date)),
);
const projectedPnl = computed(() => {
  if (closePnl.value !== "") return Number(closePnl.value);
  const account = rows.value.find(
    (item) => item.account.id === closeAccountId.value,
  );
  const closingDate = monthEndDate(closeMonth.value);
  const previous = account?.snapshots
    .filter((item) => item.date < closingDate)
    .at(-1);
  return (
    Number(closeValue.value || 0) -
    (previous?.value ?? 0) -
    Number(closeContribution.value || 0)
  );
});

const money = (value: number) => n(value, "currency");
const percentage = (value: number) => n(value, "percent");

function valueAt(snapshots: InvestmentSnapshot[], month: string) {
  return (
    [...snapshots].reverse().find((item) => item.date.slice(0, 7) <= month)
      ?.value ?? 0
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

function monthEndDate(monthValue: string) {
  const [year, month] = monthValue.split("-").map(Number);
  return `${year}-${String(month).padStart(2, "0")}-${String(new Date(year, month, 0).getDate()).padStart(2, "0")}`;
}

function displayDate(value: string) {
  const [year, month, day] = value.slice(0, 10).split("-");
  return year && month && day
    ? d(new Date(Number(year), Number(month) - 1, Number(day)), "short")
    : "—";
}

function signedMoney(value: number) {
  return `${value >= 0 ? "+" : "−"}${money(Math.abs(value))}`;
}

function accountNameFor(id: string) {
  return (
    accounts.value.find((item) => item.id === id)?.name ??
    t("investmentBalances.accountFallback", { id })
  );
}

function accountColor(id: string) {
  return rows.value.find((item) => item.account.id === id)?.color ?? colors[0];
}

function openAccountCreate() {
  accountMode.value = "create";
  editingAccountId.value = null;
  accountName.value = "";
  accountPlatform.value = "";
  accountType.value = "Cartera gestionada";
  accountCurrency.value = "EUR";
  accountError.value = "";
  accountDeleteArmed.value = false;
  accountDialog.value?.showModal();
}

function openAccountEdit(account: InvestmentAccount) {
  accountMode.value = "edit";
  editingAccountId.value = account.id;
  accountName.value = account.name;
  accountPlatform.value = account.platform;
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
        ? "/investments/accounts"
        : `/investments/accounts/${editingAccountId.value}`;
    await api(
      path,
      json(editingAccountId.value === null ? "POST" : "PUT", {
        name: accountName.value,
        platform: accountPlatform.value,
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
        : t("investmentBalances.errors.saveAccount");
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
    await api(`/investments/accounts/${editingAccountId.value}`, {
      method: "DELETE",
    });
    accountDialog.value?.close();
    await load();
  } catch (reason) {
    accountError.value =
      reason instanceof Error
        ? reason.message
        : t("investmentBalances.errors.deleteAccount");
  } finally {
    accountBusy.value = false;
  }
}

function openCloseCreate(accountId?: string) {
  closeMode.value = "create";
  closeOriginal.value = null;
  closeAccountId.value = String(accountId ?? accounts.value[0]?.id ?? "");
  closeMonth.value = new Date().toISOString().slice(0, 7);
  const account = rows.value.find(
    (item) => item.account.id === closeAccountId.value,
  );
  closeValue.value = account?.latest
    ? String(account.latest.value_original ?? account.latest.value)
    : "";
  closeContribution.value = "";
  closePnl.value = "";
  closeError.value = "";
  closeDeleteArmed.value = false;
  closeDialog.value?.showModal();
}

function seedCloseFromAccount() {
  if (closeMode.value !== "create") return;
  const account = rows.value.find(
    (item) => item.account.id === closeAccountId.value,
  );
  closeValue.value = account?.latest
    ? String(account.latest.value_original ?? account.latest.value)
    : "";
  closeContribution.value = "";
  closePnl.value = "";
}

function openCloseEdit(item: InvestmentSnapshot) {
  closeMode.value = "edit";
  closeOriginal.value = { accountId: item.account_id, date: item.date };
  closeAccountId.value = item.account_id;
  closeMonth.value = item.date.slice(0, 7);
  closeValue.value = String(item.value_original ?? item.value);
  closeContribution.value = item.contribution_original
    ? String(item.contribution_original)
    : "";
  closePnl.value = String(item.interest_original ?? item.interest);
  closeError.value = "";
  closeDeleteArmed.value = false;
  closeDialog.value?.showModal();
}

async function saveClose() {
  closeBusy.value = true;
  closeError.value = "";
  try {
    const date = monthEndDate(closeMonth.value);
    const accountId = closeAccountId.value;
    const payload: Record<string, number | string> = {
      date,
      account_id: accountId,
      value: Number(closeValue.value),
      contribution: Number(closeContribution.value || 0),
    };
    if (closePnl.value !== "") payload.interest = Number(closePnl.value);
    await api("/investments/history", json("POST", payload));
    if (
      closeOriginal.value &&
      (closeOriginal.value.accountId !== accountId ||
        closeOriginal.value.date !== date)
    ) {
      await api(
        `/investments/history/${closeOriginal.value.accountId}/${closeOriginal.value.date}`,
        { method: "DELETE" },
      );
    }
    closeDialog.value?.close();
    await load();
  } catch (reason) {
    closeError.value =
      reason instanceof Error
        ? reason.message
        : t("investmentBalances.errors.saveClose");
  } finally {
    closeBusy.value = false;
  }
}

async function removeClose() {
  if (!closeDeleteArmed.value) {
    closeDeleteArmed.value = true;
    return;
  }
  if (!closeOriginal.value) return;
  closeBusy.value = true;
  try {
    await api(
      `/investments/history/${closeOriginal.value.accountId}/${closeOriginal.value.date}`,
      { method: "DELETE" },
    );
    closeDialog.value?.close();
    await load();
  } catch (reason) {
    closeError.value =
      reason instanceof Error
        ? reason.message
        : t("investmentBalances.errors.deleteClose");
  } finally {
    closeBusy.value = false;
  }
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    [accounts.value, history.value] = await Promise.all([
      api<InvestmentAccount[]>("/investments/accounts"),
      api<InvestmentSnapshot[]>("/investments/history"),
    ]);
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : t("investmentBalances.errors.load");
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="balances-page">
    <div
      v-if="loading"
      class="balances-loading"
      :aria-label="t('investmentBalances.loading')"
    >
      <div />
      <div />
      <div />
    </div>
    <article v-else-if="error" class="balances-error" role="alert">
      <strong>{{ t("investmentBalances.errors.title") }}</strong>
      <p>{{ error }}</p>
      <button type="button" @click="load">{{ t("common.retry") }}</button>
    </article>

    <template v-else>
      <article class="closing-hero">
        <header>
          <div>
            <p class="eyebrow">{{ t("investmentBalances.hero.eyebrow") }}</p>
            <h2>{{ t("investmentBalances.hero.title") }}</h2>
            <p>{{ t("investmentBalances.hero.description") }}</p>
          </div>
          <div class="hero-actions">
            <button type="button" @click="openAccountCreate">
              ＋ {{ t("investmentBalances.actions.newAccount") }}</button
            ><button class="primary" type="button" @click="openCloseCreate()">
              ＋ {{ t("investmentBalances.actions.registerClose") }}
            </button>
          </div>
        </header>
        <div class="hero-ledger">
          <div class="value-block">
            <span>{{ t("investmentBalances.hero.consolidatedValue") }}</span
            ><strong>{{ money(totalValue) }}</strong
            ><small v-if="latestMonth">{{
              t("investmentBalances.hero.closeOf", {
                month: monthLabel(latestMonth),
              })
            }}</small>
          </div>
          <div
            class="closing-line"
            :aria-label="t('investmentBalances.hero.lastCloseAria')"
          >
            <div>
              <span>{{ t("investmentBalances.contributions") }}</span
              ><strong>{{ signedMoney(monthContribution) }}</strong
              ><i class="contribution" />
            </div>
            <div>
              <span>{{ t("investmentBalances.performance") }}</span
              ><strong
                :class="{ positive: monthPnl >= 0, negative: monthPnl < 0 }"
                >{{ signedMoney(monthPnl) }}</strong
              ><i :class="monthPnl >= 0 ? 'profit' : 'loss'" />
            </div>
            <div>
              <span>{{ t("investmentBalances.return") }}</span
              ><strong
                :class="{
                  positive: monthReturn >= 0,
                  negative: monthReturn < 0,
                }"
                >{{ percentage(monthReturn) }}</strong
              ><i :class="monthReturn >= 0 ? 'profit' : 'loss'" />
            </div>
          </div>
        </div>
        <footer>
          <div>
            <span>{{ t("investmentBalances.hero.accumulatedPnl") }}</span
            ><strong
              :class="{
                positive: accumulatedPnl >= 0,
                negative: accumulatedPnl < 0,
              }"
              >{{ signedMoney(accumulatedPnl) }}</strong
            >
          </div>
          <div>
            <span>{{ t("investmentBalances.platforms") }}</span
            ><strong>{{ accounts.length }}</strong>
          </div>
          <div>
            <span>{{ t("investmentBalances.hero.pendingClose") }}</span
            ><strong :class="{ warning: pendingAccounts }">{{
              pendingAccounts
            }}</strong>
          </div>
          <p>{{ t("investmentBalances.hero.disclaimer") }}</p>
        </footer>
      </article>

      <div class="section-heading">
        <div>
          <p class="eyebrow">{{ t("investmentBalances.accounts.eyebrow") }}</p>
          <h2>{{ t("investmentBalances.accounts.title") }}</h2>
        </div>
        <p>{{ t("investmentBalances.accounts.description") }}</p>
      </div>
      <div class="platform-grid">
        <article
          v-for="item in rows"
          :key="item.account.id"
          class="platform-card"
        >
          <header>
            <span
              class="platform-mark"
              :style="{
                color: item.color,
                background: `color-mix(in srgb, ${item.color} 12%, var(--fz-surface-soft))`,
              }"
              >{{ item.account.name.slice(0, 2).toUpperCase() }}</span
            >
            <div>
              <h3>{{ item.account.name }}</h3>
              <p>
                {{ item.account.platform }} ·
                {{ accountTypeLabel(item.account.type) }}
              </p>
            </div>
            <button
              type="button"
              :aria-label="
                t('investmentBalances.actions.editNamed', {
                  name: item.account.name,
                })
              "
              @click="openAccountEdit(item.account)"
            >
              <svg viewBox="0 0 18 4" aria-hidden="true">
                <circle cx="2" cy="2" r="2" />
                <circle cx="9" cy="2" r="2" />
                <circle cx="16" cy="2" r="2" />
              </svg>
            </button>
          </header>
          <div class="platform-value">
            <span>{{ t("investmentBalances.accounts.latestBalance") }}</span
            ><strong>{{ money(item.value) }}</strong
            ><small>{{
              item.latest
                ? displayDate(item.latest.date)
                : t("investmentBalances.accounts.noCloses")
            }}</small>
          </div>
          <div class="capital-split">
            <span
              :style="{
                width: `${item.value ? Math.min(100, Math.max(0, ((item.value - item.pnlTotal) / item.value) * 100)) : 0}%`,
              }"
            />
            <i />
          </div>
          <div class="platform-kpis">
            <div>
              <span>{{ t("investmentBalances.contribution") }}</span
              ><strong>{{ signedMoney(item.contribution) }}</strong>
            </div>
            <div>
              <span>{{ t("investmentBalances.monthlyPnl") }}</span
              ><strong
                :class="{ positive: item.pnl >= 0, negative: item.pnl < 0 }"
                >{{ signedMoney(item.pnl) }}</strong
              >
            </div>
            <div>
              <span>{{ t("investmentBalances.return") }}</span
              ><strong
                :class="{
                  positive: item.returnRate >= 0,
                  negative: item.returnRate < 0,
                }"
                >{{ percentage(item.returnRate) }}</strong
              >
            </div>
          </div>
          <footer>
            <span :class="item.upToDate ? 'status-current' : 'status-pending'"
              ><i />
              {{
                item.upToDate
                  ? t("investmentBalances.accounts.current")
                  : t("investmentBalances.accounts.pending")
              }}</span
            ><small>{{
              t("investmentBalances.accounts.historicalPnl", {
                pnl: signedMoney(item.pnlTotal),
              })
            }}</small
            ><button type="button" @click="openCloseCreate(item.account.id)">
              {{ t("investmentBalances.actions.registerClose") }}
            </button>
          </footer>
        </article>
      </div>

      <article class="balances-panel value-chart">
        <header>
          <div>
            <p class="eyebrow">
              {{ t("investmentBalances.charts.valueEyebrow") }}
            </p>
            <h2>{{ t("investmentBalances.charts.valueTitle") }}</h2>
          </div>
          <div class="range-control">
            <button
              v-for="item in ranges"
              :key="item.key"
              type="button"
              :class="{ active: range === item.key }"
              @click="range = item.key"
            >
              {{ item.label }}
            </button>
          </div>
        </header>
        <AccountSnapshotChart
          v-if="visibleMonths.length"
          :labels="chartLabels"
          :series="valueSeries"
          mode="balance"
          :minimum-font-size="10"
        />
        <div v-else class="empty-chart">
          {{ t("investmentBalances.charts.noValue") }}
        </div>
      </article>

      <div class="lower-grid">
        <article class="balances-panel">
          <header>
            <div>
              <p class="eyebrow">
                {{ t("investmentBalances.charts.pnlEyebrow") }}
              </p>
              <h2>{{ t("investmentBalances.charts.pnlTitle") }}</h2>
            </div>
            <span class="period-result" :class="{ negative: monthPnl < 0 }">{{
              signedMoney(monthPnl)
            }}</span>
          </header>
          <AccountSnapshotChart
            v-if="visibleMonths.length"
            :labels="chartLabels"
            :series="pnlSeries"
            mode="pnl"
            :minimum-font-size="10"
          />
          <div v-else class="empty-chart">
            {{ t("investmentBalances.charts.noPnl") }}
          </div>
        </article>

        <article class="balances-panel history-panel">
          <header>
            <div>
              <p class="eyebrow">
                {{ t("investmentBalances.history.eyebrow") }}
              </p>
              <h2>
                {{ t("investmentBalances.history.title") }}
                <span>{{ displayedHistory.length }}</span>
              </h2>
            </div>
            <select
              v-model="historyAccount"
              :aria-label="t('investmentBalances.history.filterAria')"
            >
              <option value="all">
                {{ t("investmentBalances.history.allAccounts") }}
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
            <button
              v-for="item in displayedHistory.slice(0, 18)"
              :key="`${item.account_id}:${item.date}`"
              type="button"
              @click="openCloseEdit(item)"
            >
              <i :style="{ background: accountColor(item.account_id) }" />
              <span
                ><strong>{{ accountNameFor(item.account_id) }}</strong
                ><small>{{ displayDate(item.date) }}</small></span
              >
              <span
                ><small>{{ t("investmentBalances.history.balance") }}</small
                ><strong>{{ money(item.value) }}</strong></span
              >
              <span
                ><small>{{ t("investmentBalances.contribution") }}</small
                ><strong>{{
                  item.contribution ? signedMoney(item.contribution) : "—"
                }}</strong></span
              >
              <span
                ><small>{{ t("investmentBalances.pnl") }}</small
                ><strong
                  :class="{
                    positive: item.interest > 0,
                    negative: item.interest < 0,
                  }"
                  >{{
                    item.interest ? signedMoney(item.interest) : "—"
                  }}</strong
                ></span
              >
            </button>
          </div>
        </article>
      </div>
    </template>

    <dialog ref="accountDialog" class="balances-dialog">
      <form @submit.prevent="saveAccount">
        <header>
          <div>
            <p class="eyebrow">
              {{ t("investmentBalances.accountDialog.eyebrow") }}
            </p>
            <h2>
              {{
                accountMode === "create"
                  ? t("investmentBalances.accountDialog.createTitle")
                  : t("investmentBalances.accountDialog.editTitle")
              }}
            </h2>
          </div>
        </header>
        <div class="dialog-fields">
          <label
            ><span>{{ t("common.name") }}</span
            ><input v-model="accountName" required /></label
          ><label
            ><span>{{ t("investmentBalances.platforms") }}</span
            ><input v-model="accountPlatform" /></label
          ><label
            ><span>{{ t("investmentBalances.accountDialog.currency") }}</span
            ><input
              v-model="accountCurrency"
              maxlength="3"
              minlength="3"
              pattern="[A-Za-z]{3}"
              required /></label
          ><label class="wide"
            ><span>{{ t("common.type") }}</span
            ><input
              v-model="accountType"
              :placeholder="
                t('investmentBalances.accountDialog.typePlaceholder')
              "
          /></label>
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
                : t("investmentBalances.actions.deleteAccount")
            }}</button
          ><i /><button type="button" @click="accountDialog?.close()">
            {{ t("common.cancel") }}</button
          ><button class="primary" type="submit">
            {{
              accountBusy
                ? t("common.saving")
                : t("investmentBalances.actions.saveAccount")
            }}
          </button>
        </footer>
      </form>
    </dialog>

    <dialog ref="closeDialog" class="balances-dialog">
      <form @submit.prevent="saveClose">
        <header>
          <div>
            <p class="eyebrow">
              {{ t("investmentBalances.closeDialog.eyebrow") }}
            </p>
            <h2>
              {{
                closeMode === "create"
                  ? t("investmentBalances.closeDialog.createTitle")
                  : t("investmentBalances.closeDialog.editTitle")
              }}
            </h2>
          </div>
        </header>
        <div class="dialog-fields">
          <label
            ><span>{{ t("common.account") }}</span
            ><select
              v-model="closeAccountId"
              required
              @change="seedCloseFromAccount"
            >
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
            ><input v-model="closeMonth" type="month" required /></label
          ><label
            ><span>{{ t("investmentBalances.closeDialog.finalBalance") }}</span
            ><input
              v-model="closeValue"
              type="number"
              step="0.01"
              required /></label
          ><label
            ><span>{{ t("investmentBalances.closeDialog.contribution") }}</span
            ><input
              v-model="closeContribution"
              type="number"
              step="0.01" /></label
          ><label class="wide"
            ><span>{{ t("investmentBalances.closeDialog.explicitPnl") }}</span
            ><input v-model="closePnl" type="number" step="0.01" /><small>{{
              t("investmentBalances.closeDialog.calculationHelp")
            }}</small></label
          >
        </div>
        <div class="calculated-result">
          <span>{{
            closePnl === ""
              ? t("investmentBalances.closeDialog.calculatedPnl")
              : t("investmentBalances.closeDialog.providedPnl")
          }}</span
          ><strong
            :class="{ positive: projectedPnl >= 0, negative: projectedPnl < 0 }"
            >{{ signedMoney(projectedPnl) }}</strong
          >
        </div>
        <p v-if="closeError" class="dialog-error">{{ closeError }}</p>
        <footer>
          <button
            v-if="closeMode === 'edit'"
            class="danger"
            type="button"
            @click="removeClose"
          >
            {{
              closeDeleteArmed
                ? t("common.confirmDeletion")
                : t("investmentBalances.actions.deleteClose")
            }}</button
          ><i /><button type="button" @click="closeDialog?.close()">
            {{ t("common.cancel") }}</button
          ><button class="primary" type="submit">
            {{
              closeBusy
                ? t("common.saving")
                : t("investmentBalances.actions.saveClose")
            }}
          </button>
        </footer>
      </form>
    </dialog>
  </section>
</template>

<style scoped>
.balances-page {
  --balance-blue: #5681d8;
  --capital-violet: #8f72d8;
  width: min(100%, 1440px);
  margin: 0 auto;
  padding: 8px 48px 56px;
}
.eyebrow {
  margin: 0 0 5px;
  color: var(--fz-muted);
  font-size: 8px;
  font-weight: 780;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.closing-hero,
.balances-panel,
.platform-card,
.balances-error {
  border: 1px solid var(--fz-line);
  background: var(--fz-surface);
  box-shadow: var(--fz-shadow);
}
.closing-hero {
  position: relative;
  overflow: hidden;
  padding: 28px;
  border-radius: 24px;
}
.closing-hero::after {
  content: "";
  position: absolute;
  right: -80px;
  top: -180px;
  width: 500px;
  height: 500px;
  border: 1px solid color-mix(in srgb, var(--balance-blue) 17%, transparent);
  border-radius: 50%;
  box-shadow: 0 0 0 64px
    color-mix(in srgb, var(--capital-violet) 3%, transparent);
  pointer-events: none;
}
.closing-hero > header,
.balances-panel > header,
.platform-card > header,
.section-heading,
.balances-dialog header {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.closing-hero h2,
.balances-panel h2,
.section-heading h2,
.balances-dialog h2 {
  margin: 0;
  font-size: 19px;
  letter-spacing: -0.035em;
}
.closing-hero > header p:last-child,
.section-heading > p {
  margin: 5px 0 0;
  color: var(--fz-muted);
  font-size: 9px;
}
.hero-actions {
  display: flex;
  gap: 8px;
}
.hero-actions button {
  padding: 9px 12px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 8px;
}
.hero-actions .primary {
  border-color: var(--balance-blue);
  background: var(--balance-blue);
  color: #fff;
}
.hero-ledger {
  position: relative;
  z-index: 1;
  margin-top: 29px;
  display: grid;
  grid-template-columns: minmax(300px, 0.8fr) minmax(530px, 1.2fr);
  align-items: end;
  gap: 38px;
}
.value-block > span,
.closing-line span,
.closing-hero > footer span,
.platform-value span,
.platform-kpis span {
  color: var(--fz-muted);
  font-size: 8px;
}
.value-block > strong {
  display: block;
  margin-top: 5px;
  font-size: clamp(36px, 4.8vw, 55px);
  line-height: 1;
  letter-spacing: -0.065em;
}
.value-block > small {
  display: block;
  margin-top: 9px;
  color: var(--fz-muted);
  font-size: 8px;
}
.closing-line {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid var(--fz-line);
  border-left: 1px solid var(--fz-line);
}
.closing-line > div {
  position: relative;
  padding: 16px;
  display: grid;
  gap: 6px;
  border-right: 1px solid var(--fz-line);
  border-bottom: 1px solid var(--fz-line);
}
.closing-line strong {
  font-size: 14px;
}
.closing-line i {
  position: absolute;
  right: 0;
  bottom: -1px;
  left: 0;
  height: 3px;
}
.closing-line .contribution {
  background: var(--capital-violet);
}
.closing-line .profit {
  background: var(--fz-positive);
}
.closing-line .loss {
  background: var(--fz-negative);
}
.positive {
  color: var(--fz-positive) !important;
}
.negative {
  color: var(--fz-negative) !important;
}
.warning {
  color: #d89a4c !important;
}
.closing-hero > footer {
  position: relative;
  z-index: 1;
  margin-top: 24px;
  padding-top: 14px;
  display: flex;
  align-items: center;
  gap: 28px;
  border-top: 1px solid var(--fz-line);
}
.closing-hero > footer > div {
  display: grid;
  gap: 3px;
}
.closing-hero > footer strong {
  font-size: 11px;
}
.closing-hero > footer p {
  max-width: 470px;
  margin: 0 0 0 auto;
  color: var(--fz-muted);
  font-size: 7px;
  text-align: right;
}
.section-heading {
  margin: 31px 0 15px;
}
.section-heading > p {
  max-width: 460px;
  text-align: right;
}
.platform-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
.platform-card {
  padding: 21px;
  border-radius: 19px;
}
.platform-card > header {
  align-items: center;
}
.platform-card > header > div {
  min-width: 0;
  flex: 1;
}
.platform-card h3 {
  margin: 0;
  font-size: 13px;
}
.platform-card header p {
  margin: 3px 0 0;
  color: var(--fz-muted);
  font-size: 8px;
}
.platform-mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 12px;
  font-size: 9px;
  font-weight: 820;
}
.platform-card header button {
  width: 30px;
  height: 30px;
  padding: 0;
  display: grid;
  place-items: center;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
}
.platform-card header button svg {
  width: 14px;
  fill: currentColor;
}
.platform-value {
  margin-top: 19px;
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: end;
  gap: 4px 10px;
}
.platform-value > span {
  grid-column: 1/-1;
}
.platform-value strong {
  font-size: 25px;
  letter-spacing: -0.04em;
}
.platform-value small {
  color: var(--fz-muted);
  font-size: 8px;
}
.capital-split {
  height: 5px;
  margin-top: 12px;
  display: flex;
  overflow: hidden;
  border-radius: 99px;
  background: var(--fz-surface-soft);
}
.capital-split span {
  background: var(--capital-violet);
}
.capital-split i {
  flex: 1;
  background: var(--balance-blue);
}
.platform-kpis {
  margin-top: 17px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid var(--fz-line);
  border-left: 1px solid var(--fz-line);
}
.platform-kpis > div {
  padding: 11px;
  display: grid;
  gap: 4px;
  border-right: 1px solid var(--fz-line);
  border-bottom: 1px solid var(--fz-line);
}
.platform-kpis strong {
  font-size: 10px;
}
.platform-card > footer {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 9px;
}
.platform-card footer small {
  flex: 1;
  color: var(--fz-muted);
  font-size: 7px;
}
.platform-card footer button {
  padding: 7px 9px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 7px;
}
.status-current,
.status-pending {
  padding: 5px 7px;
  border-radius: 99px;
  background: color-mix(in srgb, var(--fz-positive) 10%, transparent);
  color: var(--fz-positive);
  font-size: 7px;
  font-weight: 760;
}
.status-pending {
  background: color-mix(in srgb, #d89a4c 12%, transparent);
  color: #d89a4c;
}
.status-current i,
.status-pending i {
  width: 5px;
  height: 5px;
  display: inline-block;
  border-radius: 50%;
  background: currentColor;
}
.balances-panel {
  min-width: 0;
  padding: 24px;
  border-radius: 21px;
}
.value-chart {
  margin-top: 20px;
}
.range-control {
  padding: 4px;
  display: flex;
  border-radius: 11px;
  background: var(--fz-surface-soft);
}
.range-control button {
  padding: 7px 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 8px;
}
.range-control button.active {
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
}
.lower-grid {
  margin-top: 20px;
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(460px, 1.1fr);
  gap: 20px;
}
.period-result {
  padding: 6px 9px;
  border-radius: 99px;
  background: var(--fz-surface-soft);
  color: var(--fz-positive);
  font-size: 8px;
}
.history-panel h2 span {
  color: var(--fz-muted);
  font-size: 9px;
}
.history-panel header select {
  padding: 8px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  font-size: 8px;
}
.history-list {
  max-height: 330px;
  margin-top: 14px;
  overflow: auto;
}
.history-list > button {
  width: 100%;
  min-width: 560px;
  padding: 9px 6px;
  display: grid;
  grid-template-columns: 5px minmax(100px, 1fr) repeat(3, minmax(82px, 0.7fr));
  align-items: center;
  gap: 9px;
  border: 0;
  border-bottom: 1px solid var(--fz-line);
  background: transparent;
  color: var(--fz-ink);
  text-align: left;
}
.history-list > button > i {
  width: 4px;
  height: 27px;
  border-radius: 99px;
}
.history-list span {
  display: grid;
}
.history-list small {
  color: var(--fz-muted);
  font-size: 7px;
}
.history-list strong {
  font-size: 8px;
}
.empty-chart {
  height: 290px;
  display: grid;
  place-content: center;
  color: var(--fz-muted);
  font-size: 9px;
}
.balances-dialog {
  width: min(590px, calc(100vw - 32px));
  padding: 0;
  border: 1px solid var(--fz-line);
  border-radius: 21px;
  background: var(--fz-surface);
  color: var(--fz-ink);
}
.balances-dialog::backdrop {
  background: rgba(5, 10, 8, 0.7);
  backdrop-filter: blur(5px);
}
.balances-dialog form {
  padding: 24px;
}
.balances-dialog header > button {
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
.dialog-fields span,
.dialog-fields small {
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
.calculated-result {
  margin-top: 12px;
  padding: 11px 14px;
  display: flex;
  justify-content: space-between;
  border: 1px solid var(--fz-line);
  border-radius: 11px;
}
.calculated-result span {
  color: var(--fz-muted);
  font-size: 8px;
}
.calculated-result strong {
  font-size: 11px;
}
.dialog-error {
  color: var(--fz-negative);
  font-size: 9px;
}
.balances-dialog footer {
  margin-top: 19px;
  display: flex;
  gap: 9px;
}
.balances-dialog footer i {
  flex: 1;
}
.balances-dialog footer button {
  padding: 9px 12px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
}
.balances-dialog footer .primary {
  border-color: var(--balance-blue);
  background: var(--balance-blue);
  color: #fff;
}
.balances-dialog footer .danger {
  color: var(--fz-negative);
}
.balances-loading {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18px;
}
.balances-loading div {
  min-height: 350px;
  border-radius: 22px;
  background: var(--fz-surface-soft);
}
.balances-loading div:first-child {
  grid-column: 1/-1;
  min-height: 270px;
}
.balances-error {
  padding: 20px;
  border-radius: 18px;
}
.balances-error p {
  color: var(--fz-muted);
}
@media (max-width: 1100px) {
  .hero-ledger,
  .lower-grid {
    grid-template-columns: 1fr;
  }
  .platform-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 720px) {
  .balances-page {
    padding: 4px 18px 32px;
  }
  .closing-hero,
  .balances-panel {
    padding: 19px 17px;
    border-radius: 18px;
  }
  .closing-hero > header,
  .section-heading {
    flex-direction: column;
  }
  .hero-actions {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr;
  }
  .closing-line {
    grid-template-columns: 1fr;
  }
  .closing-hero > footer {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .closing-hero > footer p {
    max-width: none;
    margin: 0;
    text-align: left;
  }
  .section-heading > p {
    text-align: left;
  }
  .platform-kpis {
    grid-template-columns: 1fr;
  }
  .platform-card > footer {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .platform-card footer button {
    width: 100%;
  }
  .dialog-fields {
    grid-template-columns: 1fr;
  }
  .dialog-fields label.wide {
    grid-column: auto;
  }
  .balances-dialog footer {
    flex-wrap: wrap;
  }
  .balances-dialog footer .danger {
    order: 2;
    width: 100%;
  }
}
.eyebrow,
.value-block > span,
.closing-line span,
.closing-hero > footer span,
.platform-value span,
.platform-kpis span,
.value-block > small,
.platform-value small,
.platform-card footer small,
.status-current,
.status-pending,
.dialog-fields small,
.calculated-result span {
  font-size: 10px;
}
.closing-hero > header p:last-child,
.section-heading > p,
.hero-actions button,
.closing-hero > footer p,
.platform-card header p,
.platform-mark,
.platform-card footer button,
.range-control button,
.period-result,
.history-panel h2 span,
.history-panel header select,
.history-list small,
.empty-chart,
.dialog-fields span,
.dialog-error {
  font-size: 11px;
}
.closing-hero h2,
.balances-panel h2,
.section-heading h2,
.balances-dialog h2 {
  font-size: 20px;
}
.closing-line strong {
  font-size: 16px;
}
.platform-card h3 {
  font-size: 15px;
}
.platform-kpis strong {
  font-size: 12px;
}
.history-list strong,
.dialog-fields input,
.dialog-fields select,
.calculated-result strong,
.balances-dialog footer button {
  font-size: 12px;
}
.history-list > button {
  min-width: 620px;
  min-height: 56px;
}
</style>
