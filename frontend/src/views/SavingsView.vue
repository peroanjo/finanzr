<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { api, json } from "../api/client";
import AccountSnapshotChart from "../components/AccountSnapshotChart.vue";
import type {
  SavingsAccount,
  AccountChartSeries,
  SavingsSnapshot,
} from "../types/api";

type Range = "6m" | "12m" | "24m" | "all";

const { t, n, d, locale } = useI18n();

const colors = [
  "#3ddc97",
  "#5681d8",
  "#c78359",
  "#9775d7",
  "#50a9b7",
  "#d8ae4e",
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
const accountDialog = ref<HTMLDialogElement>();
const snapshotDialog = ref<HTMLDialogElement>();
const accountMode = ref<"create" | "edit">("create");
const editingAccountId = ref<number | null>(null);
const accountName = ref("");
const accountBank = ref("");
const accountType = ref("Cuenta corriente");
const accountCurrency = ref("EUR");
const accountBusy = ref(false);
const accountError = ref("");
const accountDeleteArmed = ref(false);
const snapshotMode = ref<"create" | "edit">("create");
const snapshotOriginal = ref<{ accountId: number; date: string } | null>(null);
const snapshotAccountId = ref("");
const snapshotDate = ref(new Date().toISOString().slice(0, 7));
const snapshotBalance = ref("");
const snapshotContribution = ref("");
const snapshotInterest = ref("");
const snapshotBusy = ref(false);
const snapshotError = ref("");
const snapshotDeleteArmed = ref(false);

const allMonths = computed(() =>
  [...new Set(history.value.map((item) => item.fecha.slice(0, 7)))].sort(),
);
const accountRows = computed(() =>
  accounts.value.map((account, index) => {
    const rows = history.value
      .filter((item) => item.cuenta_id === account.id)
      .sort((a, b) => a.fecha.localeCompare(b.fecha));
    const latest = rows.at(-1) ?? null;
    const previous = rows.at(-2) ?? null;
    const totalInterest = rows.reduce(
      (total, item) => total + item.intereses,
      0,
    );
    const twelveMonthCutoff = allMonths.value.slice(-12);
    const lastTwelveInterest = rows
      .filter((item) => twelveMonthCutoff.includes(item.fecha.slice(0, 7)))
      .reduce((total, item) => total + item.intereses, 0);
    return {
      account,
      color: colors[index % colors.length],
      rows,
      latest,
      balance: latest?.saldo ?? 0,
      change: latest && previous ? latest.saldo - previous.saldo : 0,
      contribution: latest?.aporte ?? 0,
      lastInterest: latest?.intereses ?? 0,
      totalInterest,
      lastTwelveInterest,
      remunerated:
        totalInterest > 0 ||
        account.tipo.toLocaleLowerCase().includes("remunerada") ||
        account.tipo.toLocaleLowerCase().includes("interest"),
    };
  }),
);
const totalBalance = computed(() =>
  accountRows.value.reduce((total, item) => total + item.balance, 0),
);
const totalInterest = computed(() =>
  history.value.reduce((total, item) => total + item.intereses, 0),
);
const lastTwelveInterest = computed(() => {
  const cutoff = allMonths.value.slice(-12);
  return history.value
    .filter((item) => cutoff.includes(item.fecha.slice(0, 7)))
    .reduce((total, item) => total + item.intereses, 0);
});
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
  return months ? allMonths.value.slice(-months) : allMonths.value;
});
const visibleInterest = computed(() =>
  history.value
    .filter((item) => visibleMonths.value.includes(item.fecha.slice(0, 7)))
    .reduce((total, item) => total + item.intereses, 0),
);
const activeRangeLabel = computed(
  () => ranges.value.find((item) => item.key === range.value)?.label ?? "",
);
const latestMonthTotal = computed(() =>
  monthTotal(visibleMonths.value.at(-1) ?? ""),
);
const previousMonthTotal = computed(() =>
  monthTotal(visibleMonths.value.at(-2) ?? ""),
);
const monthlyChange = computed(
  () => latestMonthTotal.value - previousMonthTotal.value,
);
const balanceSeries = computed<AccountChartSeries[]>(() =>
  accountRows.value.map((row) => ({
    label: row.account.nombre,
    color: row.color,
    values: visibleMonths.value.map((month) => balanceAt(row.rows, month)),
  })),
);
const interestSeries = computed<AccountChartSeries[]>(() =>
  accountRows.value
    .filter((row) => row.remunerated)
    .map((row) => ({
      label: row.account.nombre,
      color: row.color,
      values: visibleMonths.value.map((month) =>
        row.rows
          .filter((item) => item.fecha.startsWith(month))
          .reduce((total, item) => total + item.intereses, 0),
      ),
    })),
);
const chartLabels = computed(() => visibleMonths.value.map(monthLabel));
const displayedHistory = computed(() =>
  [...history.value]
    .filter(
      (item) =>
        historyAccount.value === "all" ||
        String(item.cuenta_id) === historyAccount.value,
    )
    .sort((a, b) => b.fecha.localeCompare(a.fecha)),
);

const money = (value: number) => n(value, "currency");
const percentage = (value: number) => n(value, "percent");

function balanceAt(rows: SavingsSnapshot[], month: string) {
  return (
    [...rows].reverse().find((item) => item.fecha.slice(0, 7) <= month)
      ?.saldo ?? 0
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

function accountNameFor(id: number) {
  return (
    accounts.value.find((item) => item.id === id)?.nombre ??
    t("savings.accountFallback", { id })
  );
}

function accountColor(id: number) {
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
  accountName.value = account.nombre;
  accountBank.value = account.banco;
  accountType.value = account.tipo;
  accountCurrency.value = account.moneda || "EUR";
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
        nombre: accountName.value,
        banco: accountBank.value,
        tipo: accountType.value,
        moneda: accountCurrency.value.trim().toUpperCase(),
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

function openSnapshotCreate(accountId?: number) {
  snapshotMode.value = "create";
  snapshotOriginal.value = null;
  snapshotAccountId.value = String(accountId ?? accounts.value[0]?.id ?? "");
  snapshotDate.value = new Date().toISOString().slice(0, 7);
  const selected = accountRows.value.find(
    (item) => item.account.id === Number(snapshotAccountId.value),
  );
  snapshotBalance.value = selected?.latest
    ? String(selected.latest.saldo_original ?? selected.latest.saldo)
    : "";
  snapshotContribution.value = "";
  snapshotInterest.value = "";
  snapshotError.value = "";
  snapshotDeleteArmed.value = false;
  snapshotDialog.value?.showModal();
}

function openSnapshotEdit(item: SavingsSnapshot) {
  snapshotMode.value = "edit";
  snapshotOriginal.value = { accountId: item.cuenta_id, date: item.fecha };
  snapshotAccountId.value = String(item.cuenta_id);
  snapshotDate.value = item.fecha.slice(0, 7);
  snapshotBalance.value = String(item.saldo_original ?? item.saldo);
  snapshotContribution.value = item.aporte_original
    ? String(item.aporte_original)
    : "";
  snapshotInterest.value = item.intereses_original
    ? String(item.intereses_original)
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
    const newAccountId = Number(snapshotAccountId.value);
    await api(
      "/savings/history",
      json("POST", {
        fecha: newDate,
        cuenta_id: newAccountId,
        saldo: Number(snapshotBalance.value),
        aporte: Number(snapshotContribution.value || 0),
        intereses: Number(snapshotInterest.value || 0),
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
      <article class="liquidity-hero">
        <header>
          <div>
            <p class="section-label">{{ t("savings.hero.eyebrow") }}</p>
            <h2>{{ t("savings.hero.title") }}</h2>
            <p>{{ t("savings.hero.description") }}</p>
          </div>
          <div class="hero-actions">
            <button type="button" @click="openAccountCreate">
              ＋ {{ t("savings.actions.newAccount") }}</button
            ><button
              class="primary"
              type="button"
              @click="openSnapshotCreate()"
            >
              ＋ {{ t("savings.actions.monthlySnapshot") }}
            </button>
          </div>
        </header>
        <div class="hero-grid">
          <div class="cash-total">
            <span>{{ t("savings.hero.availableNow") }}</span
            ><strong>{{ money(totalBalance) }}</strong
            ><small :class="{ negative: monthlyChange < 0 }">{{
              t("savings.hero.vsPrevious", {
                change: signedMoney(monthlyChange),
              })
            }}</small>
          </div>
          <div class="savings-kpis">
            <div>
              <span>{{ t("savings.hero.interestBearingBalance") }}</span
              ><strong>{{ money(remuneratedBalance) }}</strong
              ><small>{{
                t("savings.hero.ofCash", {
                  share: percentage(remuneratedShare),
                })
              }}</small>
            </div>
            <div>
              <span>{{ t("savings.hero.interestTwelveMonths") }}</span
              ><strong class="positive">{{
                signedMoney(lastTwelveInterest)
              }}</strong
              ><small>{{
                t("savings.hero.sinceStart", { total: money(totalInterest) })
              }}</small>
            </div>
            <div>
              <span>{{ t("savings.hero.activeAccounts") }}</span
              ><strong>{{ accounts.length }}</strong
              ><small>{{
                t("savings.hero.earningInterest", {
                  count: accountRows.filter((item) => item.remunerated).length,
                })
              }}</small>
            </div>
          </div>
        </div>
        <div
          class="liquidity-line"
          :aria-label="t('savings.cashDistributionAria')"
        >
          <i
            v-for="item in accountRows"
            :key="item.account.id"
            :style="{
              width: `${totalBalance ? (item.balance / totalBalance) * 100 : 0}%`,
              background: item.color,
            }"
            :title="`${item.account.nombre}: ${money(item.balance)}`"
          />
        </div>
        <div class="liquidity-legend">
          <span v-for="item in accountRows" :key="item.account.id"
            ><i :style="{ background: item.color }" />{{ item.account.nombre }}
            <strong>{{
              percentage(totalBalance ? item.balance / totalBalance : 0)
            }}</strong></span
          >
        </div>
      </article>

      <div class="accounts-heading">
        <div>
          <p class="section-label">{{ t("savings.accounts.eyebrow") }}</p>
          <h2>{{ t("savings.accounts.title") }}</h2>
        </div>
        <p>{{ t("savings.accounts.description") }}</p>
      </div>
      <div class="account-grid">
        <article
          v-for="item in accountRows"
          :key="item.account.id"
          class="cash-account"
          :class="{ remunerated: item.remunerated }"
        >
          <header>
            <span
              class="bank-mark"
              :style="{
                color: item.color,
                background: `color-mix(in srgb, ${item.color} 12%, var(--fz-surface-soft))`,
              }"
              >{{ item.account.nombre.slice(0, 2).toUpperCase() }}</span
            >
            <div>
              <h3>{{ item.account.nombre }}</h3>
              <p>
                {{ item.account.banco }} ·
                {{ accountTypeLabel(item.account.tipo) }}
              </p>
            </div>
            <button
              type="button"
              :aria-label="
                t('savings.actions.editNamed', { name: item.account.nombre })
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
          <div class="account-balance">
            <span>{{ t("savings.accounts.currentBalance") }}</span
            ><strong>{{ money(item.balance) }}</strong
            ><small>{{
              t("savings.hero.ofCash", {
                share: percentage(
                  totalBalance ? item.balance / totalBalance : 0,
                ),
              })
            }}</small>
          </div>
          <div class="account-rail">
            <i
              :style="{
                width: `${totalBalance ? (item.balance / totalBalance) * 100 : 0}%`,
                background: item.color,
              }"
            />
          </div>
          <div class="account-kpis">
            <div>
              <span>{{ t("savings.accounts.latestChange") }}</span
              ><strong
                :class="{
                  positive: item.change > 0,
                  negative: item.change < 0,
                }"
                >{{ signedMoney(item.change) }}</strong
              >
            </div>
            <div>
              <span>{{ t("savings.accounts.latestInterest") }}</span
              ><strong :class="{ positive: item.lastInterest > 0 }">{{
                money(item.lastInterest)
              }}</strong>
            </div>
            <div>
              <span>{{ t("savings.accounts.interestTwelveMonths") }}</span
              ><strong :class="{ positive: item.lastTwelveInterest > 0 }">{{
                money(item.lastTwelveInterest)
              }}</strong>
            </div>
          </div>
          <footer>
            <span v-if="item.remunerated" class="yield-badge"
              ><i /> {{ t("savings.accounts.interestBearing") }}</span
            ><span v-else class="cash-badge">{{
              t("savings.accounts.cash")
            }}</span
            ><small>{{
              t("savings.accounts.updated", {
                date: displayDate(item.latest?.fecha ?? ""),
              })
            }}</small
            ><button type="button" @click="openSnapshotCreate(item.account.id)">
              {{ t("savings.actions.updateBalance") }}
            </button>
          </footer>
        </article>
      </div>

      <article class="savings-panel balance-panel">
        <header>
          <div>
            <p class="section-label">
              {{ t("savings.charts.balanceEyebrow") }}
            </p>
            <h2>{{ t("savings.charts.balanceTitle") }}</h2>
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
          :labels="chartLabels"
          :series="balanceSeries"
          mode="balance"
          :minimum-font-size="10"
        />
      </article>

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
                {{ item.nombre }}
              </option>
            </select>
          </header>
          <div class="history-list">
            <button
              v-for="item in displayedHistory.slice(0, 18)"
              :key="`${item.cuenta_id}:${item.fecha}`"
              type="button"
              @click="openSnapshotEdit(item)"
            >
              <i :style="{ background: accountColor(item.cuenta_id) }" />
              <span
                ><strong>{{ accountNameFor(item.cuenta_id) }}</strong
                ><small>{{ displayDate(item.fecha) }}</small></span
              >
              <span
                ><small>{{ t("savings.history.balance") }}</small
                ><strong>{{ money(item.saldo) }}</strong></span
              >
              <span
                ><small>{{ t("savings.history.variation") }}</small
                ><strong
                  :class="{
                    positive: item.aporte > 0,
                    negative: item.aporte < 0,
                  }"
                  >{{ item.aporte ? signedMoney(item.aporte) : "—" }}</strong
                ></span
              >
              <span
                ><small>{{ t("savings.history.interest") }}</small
                ><strong :class="{ positive: item.intereses > 0 }">{{
                  item.intereses ? money(item.intereses) : "—"
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
                {{ item.nombre }}
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
  --cash-blue: #5681d8;
  --cash-cyan: #50a9b7;
  width: min(100%, 1440px);
  margin: 0 auto;
  padding: 8px 48px 56px;
}
.section-label {
  margin: 0 0 5px;
  color: var(--fz-muted);
  font-size: 8px;
  font-weight: 780;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.liquidity-hero,
.savings-panel,
.cash-account,
.savings-error {
  border: 1px solid var(--fz-line);
  background: var(--fz-surface);
  box-shadow: var(--fz-shadow);
}
.liquidity-hero {
  position: relative;
  overflow: hidden;
  padding: 28px;
  border-radius: 24px;
}
.liquidity-hero::after {
  content: "";
  position: absolute;
  right: -110px;
  bottom: -260px;
  width: 570px;
  height: 570px;
  border: 1px solid color-mix(in srgb, var(--cash-cyan) 18%, transparent);
  border-radius: 50%;
  box-shadow:
    0 0 0 70px color-mix(in srgb, var(--cash-cyan) 3%, transparent),
    0 0 0 140px color-mix(in srgb, var(--cash-blue) 2%, transparent);
  pointer-events: none;
}
.liquidity-hero > header,
.savings-panel > header,
.cash-account > header,
.accounts-heading,
.savings-dialog header {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.liquidity-hero h2,
.savings-panel h2,
.accounts-heading h2,
.savings-dialog h2 {
  margin: 0;
  font-size: 19px;
  letter-spacing: -0.035em;
}
.liquidity-hero > header p:last-child,
.accounts-heading > p {
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
  border-color: var(--cash-blue);
  background: var(--cash-blue);
  color: #fff;
}
.hero-grid {
  position: relative;
  z-index: 1;
  margin-top: 28px;
  display: grid;
  grid-template-columns: minmax(300px, 0.9fr) minmax(560px, 1.4fr);
  gap: 35px;
}
.cash-total > span,
.savings-kpis span,
.account-balance span,
.account-kpis span {
  color: var(--fz-muted);
  font-size: 8px;
}
.cash-total > strong {
  display: block;
  margin-top: 5px;
  font-size: clamp(35px, 4.8vw, 54px);
  line-height: 1;
  letter-spacing: -0.065em;
}
.cash-total > small {
  display: block;
  margin-top: 10px;
  color: var(--fz-positive);
  font-size: 9px;
}
.negative {
  color: var(--fz-negative) !important;
}
.positive {
  color: var(--fz-positive) !important;
}
.savings-kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-top: 1px solid var(--fz-line);
  border-left: 1px solid var(--fz-line);
}
.savings-kpis > div {
  padding: 16px;
  display: grid;
  gap: 5px;
  border-right: 1px solid var(--fz-line);
  border-bottom: 1px solid var(--fz-line);
  background: color-mix(in srgb, var(--fz-surface-soft) 45%, transparent);
}
.savings-kpis strong {
  font-size: 15px;
}
.savings-kpis small {
  color: var(--fz-muted);
  font-size: 7px;
}
.liquidity-line {
  position: relative;
  z-index: 1;
  height: 9px;
  margin-top: 26px;
  display: flex;
  overflow: hidden;
  border-radius: 99px;
  background: var(--fz-surface-soft);
}
.liquidity-line i {
  min-width: 2px;
  height: 100%;
}
.liquidity-legend {
  position: relative;
  z-index: 1;
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
}
.liquidity-legend span {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--fz-muted);
  font-size: 7px;
}
.liquidity-legend i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.liquidity-legend strong {
  color: var(--fz-ink);
}
.accounts-heading {
  margin: 31px 0 15px;
}
.accounts-heading > p {
  max-width: 430px;
  text-align: right;
}
.account-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
.cash-account {
  padding: 21px;
  border-radius: 19px;
}
.cash-account > header {
  align-items: center;
}
.cash-account > header > div {
  min-width: 0;
  flex: 1;
}
.cash-account h3 {
  margin: 0;
  font-size: 13px;
}
.cash-account header p {
  margin: 3px 0 0;
  color: var(--fz-muted);
  font-size: 8px;
}
.bank-mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 12px;
  font-size: 9px;
  font-weight: 820;
}
.cash-account header button {
  width: 30px;
  height: 30px;
  padding: 0;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
}
.account-balance {
  margin-top: 19px;
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: end;
  gap: 4px 10px;
}
.account-balance > span {
  grid-column: 1/-1;
}
.account-balance strong {
  font-size: 25px;
  letter-spacing: -0.04em;
}
.account-balance small {
  color: var(--fz-muted);
  font-size: 8px;
}
.account-rail {
  height: 4px;
  margin-top: 12px;
  overflow: hidden;
  border-radius: 99px;
  background: var(--fz-surface-soft);
}
.account-rail i {
  height: 100%;
  display: block;
  min-width: 2px;
}
.account-kpis {
  margin-top: 17px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid var(--fz-line);
  border-left: 1px solid var(--fz-line);
}
.account-kpis > div {
  padding: 11px;
  display: grid;
  gap: 4px;
  border-right: 1px solid var(--fz-line);
  border-bottom: 1px solid var(--fz-line);
}
.account-kpis strong {
  font-size: 10px;
}
.cash-account > footer {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 9px;
}
.cash-account footer small {
  flex: 1;
  color: var(--fz-muted);
  font-size: 7px;
}
.cash-account footer button {
  padding: 7px 9px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 7px;
}
.yield-badge,
.cash-badge {
  padding: 5px 7px;
  border-radius: 99px;
  background: color-mix(in srgb, var(--fz-accent) 10%, transparent);
  color: var(--fz-positive);
  font-size: 7px;
  font-weight: 760;
}
.yield-badge i {
  width: 5px;
  height: 5px;
  display: inline-block;
  border-radius: 50%;
  background: var(--fz-accent);
}
.cash-badge {
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
}
.savings-panel {
  min-width: 0;
  padding: 24px;
  border-radius: 21px;
}
.balance-panel {
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
  grid-template-columns: minmax(0, 0.9fr) minmax(440px, 1.1fr);
  gap: 20px;
}
.interest-panel > header > span {
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
.savings-loading {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18px;
}
.savings-loading div {
  min-height: 350px;
  border-radius: 22px;
  background: var(--fz-surface-soft);
}
.savings-loading div:first-child {
  grid-column: 1/-1;
  min-height: 270px;
}
.savings-error {
  padding: 20px;
  border-radius: 18px;
}
.savings-error p {
  color: var(--fz-muted);
}
@media (max-width: 1100px) {
  .hero-grid,
  .lower-grid {
    grid-template-columns: 1fr;
  }
  .account-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 720px) {
  .savings-page {
    padding: 4px 18px 32px;
  }
  .liquidity-hero,
  .savings-panel {
    padding: 19px 17px;
    border-radius: 18px;
  }
  .liquidity-hero > header,
  .accounts-heading {
    flex-direction: column;
  }
  .hero-actions {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr;
  }
  .savings-kpis {
    grid-template-columns: 1fr;
  }
  .accounts-heading > p {
    text-align: left;
  }
  .account-kpis {
    grid-template-columns: 1fr;
  }
  .cash-account > footer {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .cash-account footer button {
    width: 100%;
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
  .savings-dialog footer .danger {
    order: 2;
    width: 100%;
  }
}
.cash-account header button {
  display: grid;
  place-items: center;
}
.cash-account header button svg {
  width: 14px;
  fill: currentColor;
}
/* Savings: type scale with 10 px as the readable minimum. */
.savings-page {
  --savings-type-min: 10px;
  --savings-type-caption: 11px;
  --savings-type-body: 12px;
}
.section-label {
  margin-bottom: 6px;
  font-size: var(--savings-type-caption);
}
.liquidity-hero h2,
.savings-panel h2,
.accounts-heading h2,
.savings-dialog h2 {
  font-size: 20px;
  line-height: 1.2;
}
.liquidity-hero > header p:last-child,
.accounts-heading > p {
  margin-top: 7px;
  font-size: var(--savings-type-caption);
  line-height: 1.55;
}
.hero-actions button {
  padding: 10px 13px;
  font-size: var(--savings-type-caption);
  font-weight: 680;
}
.cash-total > span,
.savings-kpis span,
.account-balance span,
.account-kpis span {
  font-size: var(--savings-type-caption);
  font-weight: 620;
}
.cash-total > small {
  margin-top: 11px;
  font-size: var(--savings-type-caption);
}
.savings-kpis > div {
  padding: 18px;
  gap: 6px;
}
.savings-kpis strong {
  font-size: 17px;
}
.savings-kpis small {
  font-size: var(--savings-type-min);
  line-height: 1.45;
}
.liquidity-legend {
  margin-top: 12px;
  gap: 9px 20px;
}
.liquidity-legend span {
  font-size: var(--savings-type-min);
}
.cash-account {
  padding: 23px;
}
.cash-account h3 {
  font-size: 15px;
}
.cash-account header p {
  margin-top: 4px;
  font-size: var(--savings-type-caption);
}
.bank-mark {
  width: 40px;
  height: 40px;
  font-size: var(--savings-type-min);
}
.account-balance {
  margin-top: 21px;
}
.account-balance strong {
  font-size: 27px;
}
.account-balance small {
  font-size: var(--savings-type-min);
}
.account-kpis > div {
  min-height: 62px;
  padding: 12px;
  gap: 5px;
}
.account-kpis strong {
  font-size: var(--savings-type-body);
}
.cash-account > footer {
  margin-top: 16px;
  gap: 10px;
}
.cash-account footer small {
  font-size: var(--savings-type-min);
}
.cash-account footer button {
  padding: 8px 10px;
  font-size: var(--savings-type-caption);
}
.yield-badge,
.cash-badge {
  font-size: var(--savings-type-min);
}
.savings-panel {
  padding: 26px;
}
.range-control button {
  padding: 8px 11px;
  font-size: var(--savings-type-caption);
  font-weight: 680;
}
.lower-grid {
  grid-template-columns: minmax(0, 0.9fr) minmax(470px, 1.1fr);
}
.interest-panel > header > span {
  font-size: var(--savings-type-min);
}
.history-panel h2 span {
  font-size: var(--savings-type-min);
}
.history-panel header select {
  font-size: var(--savings-type-caption);
}
.history-list > button {
  min-width: 620px;
  padding: 11px 8px;
  grid-template-columns: 5px minmax(130px, 1fr) repeat(3, minmax(94px, 0.7fr));
  gap: 10px;
}
.history-list small {
  font-size: var(--savings-type-min);
  line-height: 1.35;
}
.history-list strong {
  font-size: var(--savings-type-caption);
}
.empty-chart {
  font-size: var(--savings-type-caption);
}
.savings-dialog {
  width: min(620px, calc(100vw - 32px));
}
.dialog-fields span {
  font-size: var(--savings-type-caption);
  font-weight: 650;
}
.dialog-fields input,
.dialog-fields select {
  font-size: var(--savings-type-body);
}
.dialog-error {
  font-size: var(--savings-type-caption);
}
.savings-dialog footer button {
  font-size: var(--savings-type-caption);
  font-weight: 650;
}
.savings-error {
  font-size: var(--savings-type-body);
}
@media (max-width: 1100px) {
  .lower-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 720px) {
  .liquidity-hero,
  .savings-panel {
    padding: 19px 17px;
  }
  .cash-account {
    padding: 20px 18px;
  }
}
</style>
