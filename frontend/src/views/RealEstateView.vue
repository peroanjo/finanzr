<script setup lang="ts">
import {
  computed,
  defineComponent,
  h,
  onMounted,
  ref,
  type PropType,
} from "vue";
import { useI18n } from "vue-i18n";
import { api, json } from "../api/client";
import type { RealEstateInvestment } from "../types/api";
import { useSessionStore } from "../stores/session";

const { t, n, d } = useI18n();
const session = useSessionStore();

const defaultTaxRate = computed(
  () => session.user?.default_crowdfunding_tax_rate ?? 19,
);
const DAY = 86_400_000;
const investments = ref<RealEstateInvestment[]>([]);
const loading = ref(true);
const error = ref("");
const editor = ref<HTMLDialogElement>();
const editorMode = ref<"create" | "edit">("create");
const editingId = ref<string | null>(null);
const busy = ref(false);
const editorError = ref("");
const deleteArmed = ref(false);

interface InvestmentForm {
  name: string;
  platform: string;
  status: RealEstateInvestment["status"];
  initial_capital: string;
  new_capital: string;
  expected_profit: string;
  expected_irr_percent: string;
  expected_term_months: string;
  start_date: string;
  maturity_date: string;
  tax_rate: string;
  movements: EstateMovementForm[];
  origin: string;
}

interface EstateMovementForm {
  id?: string;
  flow_type: "capital_return" | "profit";
  effective_date: string;
  amount: string;
  note: string;
}

const emptyForm = (): InvestmentForm => ({
  name: "",
  platform: "",
  status: "active",
  initial_capital: "",
  new_capital: "",
  expected_profit: "",
  expected_irr_percent: "",
  expected_term_months: "",
  start_date: new Date().toISOString().slice(0, 10),
  maturity_date: "",
  tax_rate: "",
  movements: [],
  origin: "",
});
const form = ref<InvestmentForm>(emptyForm());

const activeInvestments = computed(() =>
  investments.value.filter(
    (item) => item.status === "active" && liveCapital(item) > 0,
  ),
);
const completedInvestments = computed(() =>
  investments.value.filter(isCompleted),
);
const activeProjectCards = computed(() =>
  investments.value.filter((item) => !isCompleted(item)),
);
const totalInitial = computed(() => sumBy((item) => item.initial_capital));
const totalNewCapital = computed(() => sumBy((item) => item.new_capital));
const totalReturned = computed(() => sumBy((item) => item.returned_capital));
const totalLive = computed(() => sumBy(liveCapital));
const totalProfitNet = computed(() =>
  investments.value.reduce((total, item) => total + realizedNet(item), 0),
);
const totalExpectedGross = computed(() => sumBy(estimatedProfit));
const totalExpectedNet = computed(() =>
  investments.value.reduce((total, item) => total + expectedNet(item), 0),
);
const weightedIrr = computed(() => {
  const weight = activeInvestments.value.reduce(
    (total, item) => total + liveCapital(item),
    0,
  );
  if (!weight) return 0;
  return (
    activeInvestments.value.reduce(
      (total, item) => total + item.expected_irr_percent * liveCapital(item),
      0,
    ) / weight
  );
});
const returnedShare = computed(() =>
  totalInitial.value
    ? Math.min(100, (totalReturned.value / totalInitial.value) * 100)
    : 0,
);
const liveShare = computed(() => Math.max(0, 100 - returnedShare.value));
const nextMaturities = computed(() =>
  [...activeInvestments.value]
    .filter((item) => item.maturity_date)
    .sort((a, b) =>
      (a.maturity_date ?? "").localeCompare(b.maturity_date ?? ""),
    )
    .slice(0, 4),
);

function sumBy(pick: (item: RealEstateInvestment) => number) {
  return investments.value.reduce(
    (total, item) => total + (pick(item) || 0),
    0,
  );
}

function liveCapital(item: RealEstateInvestment) {
  return Math.max(
    0,
    (item.initial_capital || 0) - (item.returned_capital || 0),
  );
}

function estimatedProfit(item: RealEstateInvestment) {
  if (item.expected_profit !== null && item.expected_profit !== undefined) {
    return item.expected_profit;
  }
  return (
    (((liveCapital(item) * (item.expected_irr_percent || 0)) / 100) *
      (item.expected_term_months || 0)) /
    12
  );
}

function itemTaxRate(item: RealEstateInvestment) {
  return item.tax_rate ?? defaultTaxRate.value;
}

function itemRetention(item: RealEstateInvestment) {
  return itemTaxRate(item) / 100;
}

function projectNet(item: RealEstateInvestment, gross: number) {
  if (gross <= 0) return gross;
  return gross * (1 - itemRetention(item));
}

function realizedNet(item: RealEstateInvestment) {
  return (
    item.net_realized_profit ?? projectNet(item, item.realized_profit || 0)
  );
}

function expectedNet(item: RealEstateInvestment) {
  return item.net_expected_profit ?? projectNet(item, estimatedProfit(item));
}

function displayDate(value: string | null) {
  if (!value) return t("realEstate.noDate");
  const [year, month, day] = value.slice(0, 10).split("-");
  return year && month && day
    ? d(new Date(Number(year), Number(month) - 1, Number(day)), "short")
    : t("realEstate.noDate");
}

function signedMoney(value: number) {
  return `${value >= 0 ? "+" : "−"}${money(Math.abs(value))}`;
}

function percent(value: number, maximumFractionDigits = 1) {
  return n(value / 100, {
    style: "percent",
    maximumFractionDigits,
  });
}

const money = (value: number) => n(value, "currency");

function projectProgress(item: RealEstateInvestment) {
  if (isCompleted(item)) return 100;
  if (!item.start_date || !item.maturity_date) return 0;
  const start = Date.parse(`${item.start_date.slice(0, 10)}T00:00:00`);
  const end = Date.parse(`${item.maturity_date.slice(0, 10)}T00:00:00`);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start)
    return 0;
  return Math.min(
    100,
    Math.max(0, ((Date.now() - start) / (end - start)) * 100),
  );
}

function daysToMaturity(item: RealEstateInvestment) {
  if (!item.maturity_date) return null;
  const maturity = Date.parse(`${item.maturity_date.slice(0, 10)}T00:00:00`);
  return Number.isFinite(maturity)
    ? Math.ceil((maturity - Date.now()) / DAY)
    : null;
}

function maturityCopy(item: RealEstateInvestment) {
  if (isCompleted(item)) return t("realEstate.maturity.completed");
  const days = daysToMaturity(item);
  if (days === null) return t("realEstate.maturity.undefined");
  if (days < 0)
    return t("realEstate.maturity.expired", { count: Math.abs(days) });
  if (days === 0) return t("realEstate.maturity.today");
  return t("realEstate.maturity.remaining", { count: days });
}

function statusLabel(item: RealEstateInvestment) {
  const status = statusClass(item);
  return t(`realEstate.status.${status}`);
}

function statusClass(item: RealEstateInvestment) {
  if (isCompleted(item)) return "complete";
  if (item.status === "defaulted") return "risk";
  if (item.status === "cancelled") return "cancelled";
  return "active";
}

function isCompleted(item: RealEstateInvestment) {
  return item.status === "completed" || liveCapital(item) === 0;
}

const ProjectCard = defineComponent({
  name: "ProjectCard",
  props: {
    item: { type: Object as PropType<RealEstateInvestment>, required: true },
  },
  setup(props) {
    return () => {
      const item = props.item;
      const progress = projectProgress(item);
      return h("article", { class: "project-card" }, [
        h("header", [
          h("div", { class: "project-identity" }, [
            h("span", item.name.slice(0, 2).toUpperCase()),
            h("div", [
              h("h3", item.name),
              h("p", item.platform || t("realEstate.projects.noPlatform")),
            ]),
          ]),
          h("div", { class: "project-actions" }, [
            h(
              "span",
              { class: ["status", statusClass(item)] },
              statusLabel(item),
            ),
            h(
              "button",
              {
                type: "button",
                "aria-label": t("realEstate.actions.editNamed", {
                  name: item.name,
                }),
                onClick: () => openEdit(item),
              },
              [
                h("svg", { viewBox: "0 0 18 4", "aria-hidden": "true" }, [
                  h("circle", { cx: "2", cy: "2", r: "2" }),
                  h("circle", { cx: "9", cy: "2", r: "2" }),
                  h("circle", { cx: "16", cy: "2", r: "2" }),
                ]),
              ],
            ),
          ]),
        ]),
        h("div", { class: "project-value" }, [
          h("span", t("realEstate.liveCapital")),
          h("strong", money(liveCapital(item))),
          h(
            "small",
            t("realEstate.projects.ofInitial", {
              amount: money(item.initial_capital),
            }),
          ),
        ]),
        h("div", { class: "project-progress" }, [
          h("div", [
            h("span", displayDate(item.start_date)),
            h("span", maturityCopy(item)),
            h("span", displayDate(item.maturity_date)),
          ]),
          h(
            "div",
            {
              class: "progress-track",
              role: "progressbar",
              "aria-label": t("realEstate.projects.progressAria", {
                name: item.name,
              }),
              "aria-valuemin": "0",
              "aria-valuemax": "100",
              "aria-valuenow": String(Math.round(progress)),
            },
            [h("i", { style: { width: `${progress}%` } })],
          ),
        ]),
        h("div", { class: "project-kpis" }, [
          h("div", [
            h("span", t("realEstate.contributedCapital")),
            h("strong", money(item.new_capital)),
          ]),
          h("div", [
            h("span", t("realEstate.returnedCapital")),
            h(
              "strong",
              { class: { positive: item.returned_capital > 0 } },
              money(item.returned_capital),
            ),
          ]),
          h("div", [
            h("span", t("realEstate.netProfit")),
            h(
              "strong",
              { class: { positive: realizedNet(item) > 0 } },
              money(realizedNet(item)),
            ),
            h(
              "small",
              t("realEstate.grossAmount", {
                amount: money(item.realized_profit),
              }),
            ),
          ]),
          h("div", [
            h("span", t("realEstate.expectedNet")),
            h("strong", { class: "clay" }, money(expectedNet(item))),
            h(
              "small",
              t("realEstate.grossAmount", {
                amount: money(estimatedProfit(item)),
              }),
            ),
          ]),
          h("div", [
            h("span", t("realEstate.annualIrr")),
            h("strong", percent(item.expected_irr_percent, 2)),
          ]),
          h("div", [
            h("span", t("realEstate.term")),
            h(
              "strong",
              item.expected_term_months
                ? t("realEstate.monthCount", {
                    count: item.expected_term_months,
                  })
                : "—",
            ),
          ]),
        ]),
        item.origin
          ? h("footer", [
              h("span", t("realEstate.capitalOrigin")),
              h("p", item.origin),
            ])
          : null,
      ]);
    };
  },
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    investments.value = await api<RealEstateInvestment[]>("/real-estate");
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : t("realEstate.errors.load");
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editorMode.value = "create";
  editingId.value = null;
  form.value = emptyForm();
  editorError.value = "";
  deleteArmed.value = false;
  editor.value?.showModal();
}

function openEdit(item: RealEstateInvestment) {
  editorMode.value = "edit";
  editingId.value = item.id;
  form.value = {
    name: item.name,
    platform: item.platform,
    status: item.status,
    initial_capital: String(item.initial_capital ?? ""),
    new_capital: String(item.new_capital ?? ""),
    expected_profit:
      item.expected_profit === null ? "" : String(item.expected_profit),
    expected_irr_percent: item.expected_irr_percent
      ? String(item.expected_irr_percent)
      : "",
    expected_term_months: item.expected_term_months
      ? String(item.expected_term_months)
      : "",
    start_date: item.start_date,
    maturity_date: item.maturity_date ?? "",
    tax_rate:
      item.tax_rate !== null && item.tax_rate !== undefined
        ? String(item.tax_rate)
        : "",
    movements:
      item.movements?.map((movement) => ({
        id: movement.id,
        flow_type: movement.flow_type,
        effective_date: movement.effective_date ?? "",
        amount: String(movement.amount),
        note: movement.note,
      })) ?? [],
    origin: item.origin,
  };
  editorError.value = "";
  deleteArmed.value = false;
  editor.value?.showModal();
}

function numberValue(value: string) {
  return value === "" ? 0 : Number(value);
}

function addMovement(flow_type: EstateMovementForm["flow_type"]) {
  form.value.movements.push({
    flow_type,
    effective_date: new Date().toISOString().slice(0, 10),
    amount: "",
    note: "",
  });
}

function removeMovement(index: number) {
  form.value.movements.splice(index, 1);
}

async function save() {
  busy.value = true;
  editorError.value = "";
  const payload = {
    name: form.value.name,
    platform: form.value.platform,
    status: form.value.status,
    initial_capital: numberValue(form.value.initial_capital),
    new_capital:
      form.value.new_capital === ""
        ? numberValue(form.value.initial_capital)
        : numberValue(form.value.new_capital),
    expected_profit:
      form.value.expected_profit === ""
        ? null
        : numberValue(form.value.expected_profit),
    expected_irr_percent: numberValue(form.value.expected_irr_percent),
    expected_term_months: numberValue(form.value.expected_term_months),
    start_date: form.value.start_date,
    maturity_date: form.value.maturity_date || null,
    tax_rate:
      form.value.tax_rate === "" ? null : numberValue(form.value.tax_rate),
    movements: form.value.movements.map((movement) => ({
      id: movement.id,
      flow_type: movement.flow_type,
      effective_date: movement.effective_date || null,
      amount: numberValue(movement.amount),
      note: movement.note,
    })),
    origin: form.value.origin,
  };
  try {
    const path =
      editingId.value === null
        ? "/real-estate"
        : `/real-estate/${editingId.value}`;
    const method = editingId.value === null ? "POST" : "PUT";
    await api(path, json(method, payload));
    editor.value?.close();
    await load();
  } catch (reason) {
    editorError.value =
      reason instanceof Error ? reason.message : t("realEstate.errors.save");
  } finally {
    busy.value = false;
  }
}

async function remove() {
  if (!deleteArmed.value) {
    deleteArmed.value = true;
    return;
  }
  if (editingId.value === null) return;
  busy.value = true;
  editorError.value = "";
  try {
    await api(`/real-estate/${editingId.value}`, { method: "DELETE" });
    editor.value?.close();
    await load();
  } catch (reason) {
    editorError.value =
      reason instanceof Error ? reason.message : t("realEstate.errors.delete");
  } finally {
    busy.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="estate-page">
    <p v-if="error" class="estate-error" role="alert">{{ error }}</p>

    <div
      v-if="loading"
      class="estate-loading"
      :aria-label="t('realEstate.loading')"
    >
      <div />
      <div />
      <div />
    </div>

    <template v-else>
      <article class="estate-hero">
        <header class="hero-header">
          <div class="hero-heading">
            <span class="building-mark" aria-hidden="true">
              <svg viewBox="0 0 48 48" fill="none">
                <path d="M10 41V13L26 7v34M26 17h12v24M6 41h36" />
                <path d="M16 17h4m-4 7h4m-4 7h4m16-7h-4m4 7h-4" />
              </svg>
            </span>
            <div>
              <p class="eyebrow">{{ t("realEstate.hero.eyebrow") }}</p>
              <h2>{{ t("realEstate.hero.title") }}</h2>
              <p>
                {{
                  t("realEstate.hero.activeProjects", {
                    count: activeInvestments.length,
                  })
                }}
                ·
                {{
                  t("realEstate.hero.completedProjects", {
                    count: completedInvestments.length,
                  })
                }}
              </p>
            </div>
          </div>
          <button class="add-project" type="button" @click="openCreate">
            <span>＋</span> {{ t("realEstate.actions.newInvestment") }}
          </button>
        </header>

        <div class="hero-body">
          <div class="live-capital">
            <span>{{ t("realEstate.liveCapital") }}</span>
            <strong>{{ money(totalLive) }}</strong>
            <p>
              {{
                t("realEstate.hero.returnedToCash", {
                  amount: money(totalReturned),
                })
              }}
            </p>
            <div
              class="capital-rail"
              :aria-label="t('realEstate.hero.capitalDistributionAria')"
            >
              <i :style="{ width: `${liveShare}%` }" />
              <i class="returned" :style="{ width: `${returnedShare}%` }" />
            </div>
            <div class="rail-labels">
              <span
                ><i />
                {{
                  t("realEstate.hero.inProjects", { share: percent(liveShare) })
                }}</span
              >
              <span
                ><i />
                {{
                  t("realEstate.hero.returned", {
                    share: percent(returnedShare),
                  })
                }}</span
              >
            </div>
          </div>

          <div class="general-kpis">
            <div>
              <span>{{ t("realEstate.contributedCapital") }}</span>
              <strong>{{ money(totalNewCapital) }}</strong>
              <small>{{ t("realEstate.hero.newMoney") }}</small>
            </div>
            <div>
              <span>{{ t("realEstate.hero.collectedProfit") }}</span>
              <strong class="positive">{{
                signedMoney(totalProfitNet)
              }}</strong>
              <small>{{ t("realEstate.hero.netAfterRetention") }}</small>
            </div>
            <div>
              <span>{{ t("realEstate.hero.expectedProfit") }}</span>
              <strong class="clay">{{ signedMoney(totalExpectedNet) }}</strong>
              <small>{{
                t("realEstate.hero.estimatedGross", {
                  amount: money(totalExpectedGross),
                })
              }}</small>
            </div>
            <div>
              <span>{{ t("realEstate.hero.weightedIrr") }}</span>
              <strong>{{ percent(weightedIrr, 2) }}</strong>
              <small>{{ t("realEstate.hero.onLiveCapital") }}</small>
            </div>
          </div>
        </div>
      </article>

      <article v-if="nextMaturities.length" class="maturity-strip">
        <header>
          <p class="eyebrow">{{ t("realEstate.maturities.eyebrow") }}</p>
          <h2>{{ t("realEstate.maturities.title") }}</h2>
        </header>
        <div class="maturity-list">
          <div v-for="(maturity, index) in nextMaturities" :key="maturity.id">
            <span class="maturity-index">{{
              String(index + 1).padStart(2, "0")
            }}</span>
            <span>
              <strong>{{ maturity.name }}</strong>
              <small>{{ maturity.platform }}</small>
            </span>
            <span>
              <strong>{{ displayDate(maturity.maturity_date) }}</strong>
              <small>{{ maturityCopy(maturity) }}</small>
            </span>
            <strong>{{ money(liveCapital(maturity)) }}</strong>
          </div>
        </div>
      </article>

      <header class="projects-heading">
        <div>
          <p class="eyebrow">{{ t("realEstate.projects.eyebrow") }}</p>
          <h2>{{ t("realEstate.projects.title") }}</h2>
        </div>
        <p>{{ t("realEstate.projects.description") }}</p>
      </header>

      <div
        v-if="activeProjectCards.length"
        class="project-grid project-grid--active"
      >
        <ProjectCard
          v-for="project in activeProjectCards"
          :key="project.id"
          :item="project"
        />
      </div>

      <article
        v-else-if="completedInvestments.length"
        class="active-projects-empty"
      >
        <p>{{ t("realEstate.projects.activeEmpty") }}</p>
      </article>

      <article v-else class="empty-estate">
        <span aria-hidden="true">⌂</span>
        <h2>{{ t("realEstate.empty.title") }}</h2>
        <p>{{ t("realEstate.empty.description") }}</p>
        <button type="button" @click="openCreate">
          {{ t("realEstate.actions.addInvestment") }}
        </button>
      </article>

      <details v-if="completedInvestments.length" class="completed-projects">
        <summary>
          <span>{{ t("realEstate.projects.completedTitle") }}</span>
          <small>{{
            t("realEstate.projects.completedCount", {
              count: completedInvestments.length,
            })
          }}</small>
        </summary>
        <div class="project-grid project-grid--completed">
          <ProjectCard
            v-for="project in completedInvestments"
            :key="project.id"
            :item="project"
          />
        </div>
      </details>
    </template>

    <dialog ref="editor" class="estate-dialog">
      <form @submit.prevent="save">
        <header>
          <div>
            <p class="eyebrow">{{ t("realEstate.editor.eyebrow") }}</p>
            <h2>
              {{
                editorMode === "create"
                  ? t("realEstate.editor.createTitle")
                  : t("realEstate.editor.editTitle")
              }}
            </h2>
          </div>
        </header>

        <div class="form-grid">
          <label class="wide"
            ><span>{{ t("realEstate.editor.projectName") }}</span
            ><input v-model="form.name" required
          /></label>
          <label
            ><span>{{ t("realEstate.editor.platform") }}</span
            ><input
              v-model="form.platform"
              required
              :placeholder="t('realEstate.editor.platformPlaceholder')"
          /></label>
          <label
            ><span>{{ t("realEstate.editor.status") }}</span
            ><select v-model="form.status">
              <option value="active">
                {{ t("realEstate.status.active") }}
              </option>
              <option value="completed">
                {{ t("realEstate.status.complete") }}
              </option>
              <option value="defaulted">
                {{ t("realEstate.status.risk") }}
              </option>
              <option value="cancelled">
                {{ t("realEstate.status.cancelled") }}
              </option>
            </select></label
          >
          <label
            ><span>{{ t("realEstate.editor.initialCapital") }}</span
            ><input
              v-model="form.initial_capital"
              type="number"
              min="0"
              step="0.01"
              required
          /></label>
          <label
            ><span>{{ t("realEstate.editor.newCapital") }}</span
            ><input
              v-model="form.new_capital"
              type="number"
              min="0"
              step="0.01"
              :placeholder="t('realEstate.editor.newCapitalPlaceholder')"
          /></label>
          <label
            ><span>{{ t("realEstate.editor.grossProfitEstimated") }}</span
            ><input
              v-model="form.expected_profit"
              type="number"
              min="0"
              step="0.01"
              :placeholder="t('realEstate.editor.estimatedPlaceholder')"
          /></label>
          <label
            ><span>{{ t("realEstate.editor.annualIrr") }}</span
            ><input
              v-model="form.expected_irr_percent"
              type="number"
              step="0.01"
          /></label>
          <label
            ><span>{{ t("realEstate.editor.termMonths") }}</span
            ><input
              v-model="form.expected_term_months"
              type="number"
              min="0"
              step="1"
          /></label>
          <label
            ><span>{{ t("realEstate.editor.startDate") }}</span
            ><input v-model="form.start_date" type="date" required
          /></label>
          <label
            ><span>{{ t("realEstate.editor.maturityDate") }}</span
            ><input v-model="form.maturity_date" type="date"
          /></label>
          <label
            ><span>{{ t("realEstate.editor.taxRate") }}</span
            ><input
              v-model="form.tax_rate"
              type="number"
              min="0"
              max="100"
              step="0.1"
              :placeholder="
                t('realEstate.editor.taxRatePlaceholder', {
                  rate: defaultTaxRate,
                })
              "
          /></label>
          <label class="wide"
            ><span>{{ t("realEstate.capitalOrigin") }}</span
            ><input
              v-model="form.origin"
              :placeholder="t('realEstate.editor.originPlaceholder')"
          /></label>
        </div>

        <section class="movement-editor">
          <header>
            <div>
              <strong>{{ t("realEstate.movements.title") }}</strong>
              <small>{{ t("realEstate.movements.description") }}</small>
            </div>
            <span>
              <button type="button" @click="addMovement('capital_return')">
                ＋ {{ t("realEstate.movements.capitalReturn") }}
              </button>
              <button type="button" @click="addMovement('profit')">
                ＋ {{ t("realEstate.movements.profit") }}
              </button>
            </span>
          </header>
          <div v-if="form.movements.length" class="movement-list">
            <div
              v-for="(movement, index) in form.movements"
              :key="movement.id ?? index"
              class="movement-row"
            >
              <label>
                <span>{{ t("common.type") }}</span>
                <select v-model="movement.flow_type">
                  <option value="capital_return">
                    {{ t("realEstate.movements.capitalReturn") }}
                  </option>
                  <option value="profit">
                    {{ t("realEstate.movements.profit") }}
                  </option>
                </select>
              </label>
              <label
                ><span>{{ t("realEstate.movements.date") }}</span
                ><input v-model="movement.effective_date" type="date" required
              /></label>
              <label
                ><span>{{ t("realEstate.movements.grossAmount") }}</span
                ><input
                  v-model="movement.amount"
                  type="number"
                  min="0"
                  step="0.01"
                  required
              /></label>
              <label class="movement-note"
                ><span>{{ t("realEstate.movements.note") }}</span
                ><input
                  v-model="movement.note"
                  :placeholder="t('realEstate.movements.notePlaceholder')"
              /></label>
              <button
                class="remove-movement"
                type="button"
                :aria-label="t('realEstate.movements.remove')"
                @click="removeMovement(index)"
              >
                ×
              </button>
            </div>
          </div>
          <p v-else>{{ t("realEstate.movements.empty") }}</p>
        </section>

        <p v-if="editorError" class="dialog-error" role="alert">
          {{ editorError }}
        </p>
        <footer>
          <button
            v-if="editorMode === 'edit'"
            class="danger"
            type="button"
            :disabled="busy"
            @click="remove"
          >
            {{
              deleteArmed
                ? t("common.confirmDeletion")
                : t("realEstate.actions.deleteProject")
            }}
          </button>
          <i />
          <button type="button" :disabled="busy" @click="editor?.close()">
            {{ t("common.cancel") }}
          </button>
          <button class="primary" type="submit" :disabled="busy">
            {{
              busy ? t("common.saving") : t("realEstate.actions.saveInvestment")
            }}
          </button>
        </footer>
      </form>
    </dialog>
  </section>
</template>

<style scoped>
.estate-page {
  --estate-clay: #c78359;
  --estate-sage: #6e9b7c;
  --estate-stone: #8e8378;
  width: min(100%, 1440px);
  margin: 0 auto;
  padding: 8px 48px 56px;
}
.estate-error {
  padding: 14px 18px;
  border: 1px solid color-mix(in srgb, var(--fz-negative) 35%, var(--fz-line));
  border-radius: 14px;
  background: color-mix(in srgb, var(--fz-negative) 7%, var(--fz-surface));
  color: var(--fz-negative);
}
.estate-hero,
.maturity-strip,
:deep(.project-card),
.empty-estate {
  border: 1px solid var(--fz-line);
  background: var(--fz-surface);
  box-shadow: var(--fz-shadow);
}
.estate-hero {
  position: relative;
  overflow: hidden;
  padding: 28px;
  border-radius: 24px;
}
.estate-hero::after {
  content: "";
  position: absolute;
  right: -92px;
  bottom: -160px;
  width: 420px;
  height: 420px;
  border: 1px solid color-mix(in srgb, var(--estate-clay) 22%, transparent);
  border-radius: 50%;
  box-shadow:
    0 0 0 54px color-mix(in srgb, var(--estate-clay) 4%, transparent),
    0 0 0 108px color-mix(in srgb, var(--estate-clay) 3%, transparent);
  pointer-events: none;
}
.hero-header,
.hero-heading,
:deep(.project-card > header),
:deep(.project-identity),
:deep(.project-actions),
.projects-heading {
  display: flex;
  align-items: center;
}
.hero-header {
  position: relative;
  z-index: 1;
  justify-content: space-between;
  gap: 20px;
}
.hero-heading {
  gap: 14px;
}
.building-mark {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 15px;
  background: color-mix(
    in srgb,
    var(--estate-clay) 14%,
    var(--fz-surface-soft)
  );
  color: var(--estate-clay);
}
.building-mark svg {
  width: 29px;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.eyebrow {
  margin: 0 0 4px;
  color: var(--fz-muted);
  font-size: 8px;
  font-weight: 780;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.hero-heading h2,
.projects-heading h2,
.maturity-strip h2,
.empty-estate h2 {
  margin: 0;
  color: var(--fz-ink);
  font-size: 19px;
  letter-spacing: -0.035em;
}
.hero-heading > div > p:last-child,
.projects-heading > p {
  margin: 4px 0 0;
  color: var(--fz-muted);
  font-size: 9px;
}
.add-project {
  padding: 10px 14px;
  border: 1px solid color-mix(in srgb, var(--estate-clay) 42%, var(--fz-line));
  border-radius: 11px;
  background: color-mix(in srgb, var(--estate-clay) 10%, var(--fz-surface));
  color: var(--fz-ink);
  font-size: 9px;
  font-weight: 760;
  cursor: pointer;
}
.add-project span {
  margin-right: 5px;
  color: var(--estate-clay);
  font-size: 13px;
}
.hero-body {
  position: relative;
  z-index: 1;
  margin-top: 28px;
  display: grid;
  grid-template-columns: minmax(260px, 0.9fr) minmax(500px, 1.35fr);
  gap: 36px;
}
.live-capital > span,
:deep(.project-value > span),
:deep(.project-kpis span),
.general-kpis span {
  color: var(--fz-muted);
  font-size: 8px;
}
.live-capital > strong {
  display: block;
  margin-top: 5px;
  font-size: clamp(32px, 4vw, 48px);
  line-height: 1;
  letter-spacing: -0.06em;
}
.live-capital > p {
  margin: 8px 0 18px;
  color: var(--fz-muted);
  font-size: 9px;
}
.capital-rail {
  height: 7px;
  display: flex;
  overflow: hidden;
  border-radius: 99px;
  background: var(--fz-surface-soft);
}
.capital-rail i {
  height: 100%;
  background: var(--estate-clay);
}
.capital-rail .returned {
  background: var(--estate-sage);
}
.rail-labels {
  margin-top: 9px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--fz-muted);
  font-size: 8px;
}
.rail-labels span {
  display: flex;
  align-items: center;
  gap: 6px;
}
.rail-labels i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--estate-clay);
}
.rail-labels span:last-child i {
  background: var(--estate-sage);
}
.general-kpis {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border-top: 1px solid var(--fz-line);
  border-left: 1px solid var(--fz-line);
}
.general-kpis > div {
  min-width: 0;
  padding: 15px 17px;
  display: grid;
  gap: 4px;
  border-right: 1px solid var(--fz-line);
  border-bottom: 1px solid var(--fz-line);
  background: color-mix(in srgb, var(--fz-surface-soft) 45%, transparent);
}
.general-kpis strong,
:deep(.project-kpis strong) {
  font-size: 15px;
  font-variant-numeric: tabular-nums;
}
.general-kpis small,
:deep(.project-kpis small) {
  color: var(--fz-muted);
  font-size: 7px;
}
.positive,
:deep(.project-card .positive) {
  color: var(--fz-positive);
}
.clay,
:deep(.project-card .clay) {
  color: var(--estate-clay);
}
.maturity-strip {
  margin-top: 20px;
  padding: 22px 24px;
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr);
  gap: 22px;
  border-radius: 19px;
}
.maturity-strip h2 {
  font-size: 15px;
}
.maturity-list {
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 22px;
}
.maturity-list > div {
  min-width: 0;
  padding: 8px 0;
  display: grid;
  grid-template-columns: 25px minmax(90px, 1fr) minmax(100px, 0.8fr) auto;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid var(--fz-line);
}
.maturity-list > div:nth-last-child(-n + 2) {
  border-bottom: 0;
}
.maturity-list span:not(.maturity-index) {
  min-width: 0;
  display: grid;
}
.maturity-list strong {
  overflow: hidden;
  color: var(--fz-ink);
  font-size: 9px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.maturity-list small {
  color: var(--fz-muted);
  font-size: 7px;
}
.maturity-index {
  color: var(--estate-clay);
  font-size: 8px;
  font-weight: 800;
}
.projects-heading {
  margin: 31px 0 15px;
  justify-content: space-between;
  gap: 20px;
}
.projects-heading > p {
  max-width: 340px;
  text-align: right;
}
.project-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
.active-projects-empty {
  padding: 14px 16px;
  border: 1px dashed color-mix(in srgb, var(--estate-sage) 32%, var(--fz-line));
  border-radius: 14px;
  background: color-mix(in srgb, var(--estate-sage) 5%, var(--fz-surface));
}
.active-projects-empty p {
  margin: 0;
  color: var(--fz-muted);
  font-size: 11px;
}
.completed-projects {
  margin-top: 22px;
  border-top: 1px solid var(--fz-line);
}
.completed-projects summary {
  padding: 14px 2px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--fz-muted);
  cursor: pointer;
  font-size: 11px;
  font-weight: 730;
  list-style: none;
}
.completed-projects summary::-webkit-details-marker {
  display: none;
}
.completed-projects summary::before {
  width: 7px;
  height: 7px;
  margin-right: 2px;
  border-right: 1px solid currentColor;
  border-bottom: 1px solid currentColor;
  content: "";
  transform: rotate(-45deg);
  transition: transform 0.18s ease;
}
.completed-projects[open] summary::before {
  transform: rotate(45deg);
}
.completed-projects summary span {
  margin-right: auto;
}
.completed-projects summary small {
  padding: 4px 7px;
  border-radius: 99px;
  background: var(--fz-surface-soft);
  color: var(--estate-sage);
  font-size: 10px;
  font-weight: 760;
}
.project-grid--completed {
  padding: 2px 0 4px;
}
:deep(.project-card) {
  min-width: 0;
  padding: 22px;
  border-radius: 20px;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease;
}
:deep(.project-card:hover) {
  border-color: color-mix(in srgb, var(--estate-clay) 30%, var(--fz-line));
  transform: translateY(-2px);
}
:deep(.project-card > header) {
  justify-content: space-between;
  gap: 14px;
}
:deep(.project-identity) {
  min-width: 0;
  gap: 10px;
}
:deep(.project-identity > span) {
  width: 37px;
  height: 37px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 12px;
  background: color-mix(
    in srgb,
    var(--estate-clay) 13%,
    var(--fz-surface-soft)
  );
  color: var(--estate-clay);
  font-size: 9px;
  font-weight: 820;
}
:deep(.project-identity > div) {
  min-width: 0;
}
:deep(.project-identity h3) {
  margin: 0;
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
:deep(.project-identity p) {
  margin: 3px 0 0;
  color: var(--fz-muted);
  font-size: 8px;
}
:deep(.project-actions) {
  gap: 7px;
}
:deep(.project-actions button) {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
  cursor: pointer;
}
:deep(.project-actions button svg) {
  width: 14px;
  height: auto;
  overflow: visible;
  fill: currentColor;
}
:deep(.status) {
  padding: 5px 8px;
  border-radius: 99px;
  font-size: 7px;
  font-weight: 780;
}
:deep(.status.active) {
  background: color-mix(in srgb, var(--estate-sage) 15%, transparent);
  color: var(--estate-sage);
}
:deep(.status.complete) {
  background: color-mix(in srgb, var(--fz-accent) 12%, transparent);
  color: var(--fz-positive);
}
:deep(.status.risk) {
  background: color-mix(in srgb, var(--fz-negative) 12%, transparent);
  color: var(--fz-negative);
}
:deep(.status.cancelled) {
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
}
:deep(.project-value) {
  margin-top: 22px;
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: end;
  gap: 4px 12px;
}
:deep(.project-value > span) {
  grid-column: 1 / -1;
}
:deep(.project-value strong) {
  font-size: 25px;
  letter-spacing: -0.045em;
}
:deep(.project-value small) {
  color: var(--fz-muted);
  font-size: 8px;
}
:deep(.project-progress) {
  margin-top: 17px;
}
:deep(.project-progress > div:first-child) {
  margin-bottom: 7px;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 8px;
  color: var(--fz-muted);
  font-size: 7px;
}
:deep(.project-progress > div:first-child span:nth-child(2)) {
  color: var(--estate-clay);
  text-align: center;
}
:deep(.project-progress > div:first-child span:last-child) {
  text-align: right;
}
:deep(.progress-track) {
  height: 4px;
  overflow: hidden;
  border-radius: 99px;
  background: var(--fz-surface-soft);
}
:deep(.progress-track i) {
  height: 100%;
  display: block;
  border-radius: inherit;
  background: var(--estate-clay);
}
:deep(.project-kpis) {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-top: 1px solid var(--fz-line);
  border-left: 1px solid var(--fz-line);
}
:deep(.project-kpis > div) {
  min-width: 0;
  padding: 12px;
  display: grid;
  gap: 4px;
  border-right: 1px solid var(--fz-line);
  border-bottom: 1px solid var(--fz-line);
}
:deep(.project-kpis strong) {
  overflow: hidden;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
:deep(.project-card > footer) {
  margin-top: 15px;
  padding: 11px 13px;
  border-radius: 11px;
  background: color-mix(in srgb, var(--estate-clay) 6%, var(--fz-surface-soft));
}
:deep(.project-card > footer span) {
  color: var(--estate-clay);
  font-size: 7px;
  font-weight: 760;
}
:deep(.project-card > footer p) {
  margin: 4px 0 0;
  color: var(--fz-muted);
  font-size: 8px;
  line-height: 1.45;
}
.empty-estate {
  min-height: 340px;
  padding: 32px;
  display: grid;
  place-content: center;
  justify-items: center;
  border-radius: 20px;
  text-align: center;
}
.empty-estate > span {
  color: var(--estate-clay);
  font-size: 38px;
}
.empty-estate p {
  max-width: 380px;
  color: var(--fz-muted);
}
.empty-estate button {
  padding: 10px 14px;
  border: 0;
  border-radius: 10px;
  background: var(--estate-clay);
  color: #fff;
}
.estate-dialog {
  width: min(760px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  padding: 0;
  border: 1px solid var(--fz-line);
  border-radius: 22px;
  background: var(--fz-surface);
  color: var(--fz-ink);
}
.estate-dialog::backdrop {
  background: rgba(5, 10, 8, 0.7);
  backdrop-filter: blur(5px);
}
.estate-dialog form {
  padding: 25px;
}
.estate-dialog form > header {
  display: flex;
  justify-content: space-between;
}
.estate-dialog h2 {
  margin: 0;
  font-size: 20px;
}
.estate-dialog form > header button {
  width: 32px;
  height: 32px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
}
.form-grid {
  margin-top: 21px;
  padding: 18px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 13px;
  border-radius: 15px;
  background: var(--fz-surface-soft);
}
.form-grid label {
  min-width: 0;
  display: grid;
  gap: 6px;
}
.form-grid label.wide {
  grid-column: span 2;
}
.form-grid span {
  color: var(--fz-muted);
  font-size: 8px;
}
.form-grid input,
.form-grid select {
  width: 100%;
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
.estate-dialog form > footer {
  margin-top: 20px;
  display: flex;
  align-items: center;
  gap: 9px;
}
.estate-dialog form > footer i {
  flex: 1;
}
.estate-dialog form > footer button {
  padding: 9px 13px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 9px;
}
.estate-dialog form > footer .primary {
  border-color: var(--estate-clay);
  background: var(--estate-clay);
  color: #fff;
}
.estate-dialog form > footer .danger {
  color: var(--fz-negative);
}
.movement-editor {
  margin-top: 16px;
  padding: 17px;
  border-radius: 14px;
  background: var(--fz-surface-soft);
}
.movement-editor > header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}
.movement-editor > header div {
  display: grid;
  gap: 4px;
}
.movement-editor > header small,
.movement-editor > p {
  color: var(--fz-muted);
  font-size: 10px;
}
.movement-editor > header > span {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 7px;
}
.movement-editor button {
  padding: 8px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface);
  color: var(--fz-muted);
}
.movement-list {
  margin-top: 14px;
  display: grid;
  gap: 9px;
}
.movement-row {
  display: grid;
  grid-template-columns: 1fr 125px 110px minmax(150px, 1.25fr) 32px;
  align-items: end;
  gap: 8px;
}
.movement-row label {
  display: grid;
  gap: 6px;
}
.movement-row label > span {
  color: var(--fz-muted);
  font-size: 10px;
}
.movement-row input,
.movement-row select {
  min-width: 0;
  padding: 9px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font: inherit;
  font-size: 11px;
}
.movement-row .remove-movement {
  width: 32px;
  height: 34px;
  padding: 0;
  color: var(--fz-negative);
}
.estate-loading {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
.estate-loading div {
  min-height: 370px;
  border-radius: 22px;
  background: var(--fz-surface-soft);
}
.estate-loading div:first-child {
  grid-column: 1 / -1;
  min-height: 270px;
}
@media (max-width: 1100px) {
  .hero-body {
    grid-template-columns: 1fr;
  }
  .maturity-strip {
    grid-template-columns: 1fr;
  }
  .project-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 720px) {
  .estate-page {
    padding: 4px 18px 32px;
  }
  .estate-hero {
    padding: 20px 17px;
    border-radius: 19px;
  }
  .hero-header {
    align-items: flex-start;
    flex-direction: column;
  }
  .add-project {
    width: 100%;
  }
  .hero-body {
    margin-top: 22px;
    gap: 25px;
  }
  .general-kpis {
    grid-template-columns: 1fr;
  }
  .maturity-strip {
    padding: 18px 17px;
  }
  .maturity-list {
    grid-template-columns: 1fr;
  }
  .maturity-list > div:nth-last-child(-n + 2) {
    border-bottom: 1px solid var(--fz-line);
  }
  .maturity-list > div:last-child {
    border-bottom: 0;
  }
  .projects-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .projects-heading > p {
    text-align: left;
  }
  :deep(.project-card) {
    padding: 18px 16px;
  }
  :deep(.project-kpis) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
  .form-grid label.wide {
    grid-column: auto;
  }
  .movement-editor > header {
    flex-direction: column;
  }
  .movement-editor > header > span {
    justify-content: flex-start;
  }
  .movement-row {
    grid-template-columns: 1fr 1fr;
  }
  .movement-note {
    grid-column: 1 / -1;
  }
  .estate-dialog form > footer {
    flex-wrap: wrap;
  }
  .estate-dialog form > footer .danger {
    order: 2;
    width: 100%;
  }
}
@media (prefers-reduced-motion: reduce) {
  :deep(.project-card),
  .completed-projects summary::before {
    transition: none;
  }
}

/* Readable type scale: 10 px is the floor for secondary information. */
.eyebrow,
.live-capital > span,
:deep(.project-value > span),
:deep(.project-kpis span),
.general-kpis span,
.general-kpis small,
:deep(.project-kpis small),
.rail-labels,
.maturity-list small,
.maturity-index,
:deep(.status),
:deep(.project-value small),
:deep(.project-progress > div:first-child),
:deep(.project-card > footer span) {
  font-size: 10px;
}
.hero-heading > div > p:last-child,
.projects-heading > p,
.add-project,
.live-capital > p,
.maturity-list strong,
:deep(.project-identity p),
:deep(.project-card > footer p),
.form-grid span,
.dialog-error,
.estate-dialog form > footer button {
  font-size: 11px;
}
.hero-heading h2,
.projects-heading h2,
.empty-estate h2 {
  font-size: 20px;
}
.maturity-strip h2 {
  font-size: 18px;
}
.general-kpis strong {
  font-size: 17px;
}
:deep(.project-identity > span) {
  font-size: 11px;
}
:deep(.project-identity h3) {
  font-size: 15px;
}
:deep(.project-kpis strong) {
  font-size: 13px;
}
.form-grid input,
.form-grid select {
  font-size: 12px;
}
</style>
