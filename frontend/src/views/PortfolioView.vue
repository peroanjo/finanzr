<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { api, json } from "../api/client";
import AllocationChart from "../components/AllocationChart.vue";
import type {
  PortfolioAnalysisItem,
  PortfolioAnalysisResponse,
} from "../types/api";

type Grouping = "asset" | "class" | "subtype" | "account" | "platform";
type Sort = "value" | "name" | "weight";

const { t, n, locale } = useI18n();

interface GroupedExposure {
  label: string;
  value: number;
  share: number;
  count: number;
  color: string;
}

interface ManualForm {
  nombre: string;
  tipo_renta: string;
  subtipo: string;
  plataforma: string;
  efectivo: string;
}

const palette = [
  "#3ddc97",
  "#587bd8",
  "#c78359",
  "#9876d8",
  "#50a9b7",
  "#d8ae4e",
  "#d66f78",
  "#739b6a",
  "#b86e9c",
  "#748b99",
  "#8b9560",
  "#b4774e",
];
const groupings = computed<
  Array<{ key: Grouping; label: string; hint: string }>
>(() => [
  {
    key: "asset",
    label: t("portfolio.groupings.asset.label"),
    hint: t("portfolio.groupings.asset.hint"),
  },
  {
    key: "class",
    label: t("portfolio.groupings.class.label"),
    hint: t("portfolio.groupings.class.hint"),
  },
  {
    key: "subtype",
    label: t("portfolio.groupings.subtype.label"),
    hint: t("portfolio.groupings.subtype.hint"),
  },
  {
    key: "account",
    label: t("portfolio.groupings.account.label"),
    hint: t("portfolio.groupings.account.hint"),
  },
  {
    key: "platform",
    label: t("portfolio.groupings.platform.label"),
    hint: t("portfolio.groupings.platform.hint"),
  },
]);
const sourceLabels = computed<Record<PortfolioAnalysisItem["origen"], string>>(
  () => ({
    fund: t("portfolio.sources.fund"),
    stock: t("portfolio.sources.stock"),
    crypto: t("portfolio.sources.crypto"),
    real_estate: t("portfolio.sources.realEstate"),
    manual: t("portfolio.sources.manual"),
  }),
);
const sourceMarks: Record<PortfolioAnalysisItem["origen"], string> = {
  fund: "◔",
  stock: "⌁",
  crypto: "₿",
  real_estate: "⌂",
  manual: "◇",
};

const portfolio = ref<PortfolioAnalysisResponse | null>(null);
const loading = ref(true);
const error = ref("");
const grouping = ref<Grouping>("class");
const search = ref("");
const sourceFilter = ref("all");
const classFilter = ref("all");
const accountFilter = ref("all");
const platformFilter = ref("all");
const sort = ref<Sort>("value");
const manualDialog = ref<HTMLDialogElement>();
const manualMode = ref<"create" | "edit">("create");
const manualId = ref<number | null>(null);
const manualBusy = ref(false);
const manualError = ref("");
const manualDeleteArmed = ref(false);
const manualForm = ref<ManualForm>({
  nombre: "",
  tipo_renta: "",
  subtipo: "",
  plataforma: "",
  efectivo: "",
});

const items = computed(() => portfolio.value?.items ?? []);
const sourceOptions = computed(() => [
  ...new Set(items.value.map((item) => item.origen)),
]);
const classOptions = computed(() =>
  [...new Set(items.value.map((item) => item.clase))].sort(),
);
const accountOptions = computed(() =>
  [...new Set(items.value.map((item) => item.cuenta))].sort(),
);
const platformOptions = computed(() =>
  [...new Set(items.value.map((item) => item.plataforma))].sort(),
);
const hasFilters = computed(() =>
  Boolean(
    search.value ||
    sourceFilter.value !== "all" ||
    classFilter.value !== "all" ||
    accountFilter.value !== "all" ||
    platformFilter.value !== "all",
  ),
);
const filteredItems = computed(() => {
  const query = search.value.trim().toLocaleLowerCase(locale.value);
  const filtered = items.value.filter(
    (item) =>
      (!query ||
        [
          item.nombre,
          item.identificador,
          item.clase,
          item.subtipo,
          item.cuenta,
          item.plataforma,
        ].some((value) =>
          value.toLocaleLowerCase(locale.value).includes(query),
        )) &&
      (sourceFilter.value === "all" || item.origen === sourceFilter.value) &&
      (classFilter.value === "all" || item.clase === classFilter.value) &&
      (accountFilter.value === "all" || item.cuenta === accountFilter.value) &&
      (platformFilter.value === "all" ||
        item.plataforma === platformFilter.value),
  );
  return [...filtered].sort((a, b) => {
    if (sort.value === "name")
      return a.nombre.localeCompare(b.nombre, locale.value);
    if (sort.value === "weight") return b.peso - a.peso;
    return b.valor - a.valor;
  });
});
const filteredTotal = computed(() =>
  filteredItems.value.reduce((total, item) => total + item.valor, 0),
);
const classesCount = computed(
  () => new Set(filteredItems.value.map((item) => item.clase)).size,
);
function classificationLabel(value: string) {
  const keyByValue: Record<string, string> = {
    Fondos: "funds",
    "Acciones y ETF": "stocks",
    Crypto: "crypto",
    Inmobiliario: "realEstate",
    Otros: "other",
    "Fondo de inversión": "investmentFund",
    "Acción o ETF": "stockOrEtf",
    "Posición manual": "manualPosition",
  };
  const key = keyByValue[value];
  return key ? t(`portfolio.classifications.${key}`) : value;
}
const accountsCount = computed(
  () => new Set(filteredItems.value.map((item) => item.cuenta_id)).size,
);
const topPosition = computed(
  () => [...filteredItems.value].sort((a, b) => b.valor - a.valor)[0],
);
const topThreeShare = computed(() => {
  if (!filteredTotal.value) return 0;
  return (
    [...filteredItems.value]
      .sort((a, b) => b.valor - a.valor)
      .slice(0, 3)
      .reduce((total, item) => total + item.valor, 0) / filteredTotal.value
  );
});
const groupingLabel = computed(
  () =>
    groupings.value.find((item) => item.key === grouping.value)?.label ??
    t("portfolio.groupings.class.label"),
);
const groupedExposures = computed<GroupedExposure[]>(() => {
  const grouped = new Map<string, { value: number; count: number }>();
  filteredItems.value.forEach((item) => {
    const label = groupValue(item, grouping.value);
    const current = grouped.get(label) ?? { value: 0, count: 0 };
    grouped.set(label, {
      value: current.value + item.valor,
      count: current.count + 1,
    });
  });
  return [...grouped.entries()]
    .map(([label, value], index) => ({
      label,
      value: value.value,
      count: value.count,
      share: filteredTotal.value ? value.value / filteredTotal.value : 0,
      color: palette[index % palette.length],
    }))
    .sort((a, b) => b.value - a.value)
    .map((item, index) => ({
      ...item,
      color: palette[index % palette.length],
    }));
});
const chartExposures = computed<GroupedExposure[]>(() => {
  if (groupedExposures.value.length <= 9) return groupedExposures.value;
  const visible = groupedExposures.value.slice(0, 8);
  const rest = groupedExposures.value.slice(8);
  const value = rest.reduce((total, item) => total + item.value, 0);
  return [
    ...visible,
    {
      label: t("portfolio.other"),
      value,
      share: filteredTotal.value ? value / filteredTotal.value : 0,
      count: rest.reduce((total, item) => total + item.count, 0),
      color: palette[8],
    },
  ];
});
const allocationItems = computed(() =>
  chartExposures.value.map((item) => ({
    label: item.label,
    value: item.value,
    color: item.color,
  })),
);
const topExposures = computed(() => groupedExposures.value.slice(0, 7));

const money = (value: number) => n(value, "currency");
const percentage = (value: number) => n(value, "percent");

function groupValue(item: PortfolioAnalysisItem, dimension: Grouping) {
  return (
    {
      asset: item.nombre,
      class: item.clase,
      subtype: item.subtipo,
      account: item.cuenta,
      platform: item.plataforma,
    }[dimension] || t("portfolio.unclassified")
  );
}

function shareOfFiltered(item: PortfolioAnalysisItem) {
  return filteredTotal.value ? item.valor / filteredTotal.value : 0;
}

function clearFilters() {
  search.value = "";
  sourceFilter.value = "all";
  classFilter.value = "all";
  accountFilter.value = "all";
  platformFilter.value = "all";
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    portfolio.value = await api<PortfolioAnalysisResponse>(
      "/portfolio-analysis",
    );
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : t("portfolio.errors.load");
  } finally {
    loading.value = false;
  }
}

function openManualCreate() {
  manualMode.value = "create";
  manualId.value = null;
  manualForm.value = {
    nombre: "",
    tipo_renta: "",
    subtipo: "",
    plataforma: "",
    efectivo: "",
  };
  manualError.value = "";
  manualDeleteArmed.value = false;
  manualDialog.value?.showModal();
}

function openManualEdit(item: PortfolioAnalysisItem) {
  if (item.origen !== "manual") return;
  manualMode.value = "edit";
  manualId.value = Number(item.id.split(":")[1]);
  manualForm.value = {
    nombre: item.nombre,
    tipo_renta: item.clase,
    subtipo: item.subtipo,
    plataforma: item.plataforma === "Manual" ? "" : item.plataforma,
    efectivo: String(item.valor),
  };
  manualError.value = "";
  manualDeleteArmed.value = false;
  manualDialog.value?.showModal();
}

async function saveManual() {
  manualBusy.value = true;
  manualError.value = "";
  const payload = {
    ...manualForm.value,
    efectivo: Number(manualForm.value.efectivo),
  };
  try {
    const path =
      manualId.value === null ? "/portfolio" : `/portfolio/${manualId.value}`;
    const method = manualId.value === null ? "POST" : "PUT";
    await api(path, json(method, payload));
    manualDialog.value?.close();
    await load();
  } catch (reason) {
    manualError.value =
      reason instanceof Error
        ? reason.message
        : t("portfolio.errors.savePosition");
  } finally {
    manualBusy.value = false;
  }
}

async function removeManual() {
  if (!manualDeleteArmed.value) {
    manualDeleteArmed.value = true;
    return;
  }
  if (manualId.value === null) return;
  manualBusy.value = true;
  manualError.value = "";
  try {
    await api(`/portfolio/${manualId.value}`, { method: "DELETE" });
    manualDialog.value?.close();
    await load();
  } catch (reason) {
    manualError.value =
      reason instanceof Error
        ? reason.message
        : t("portfolio.errors.deletePosition");
  } finally {
    manualBusy.value = false;
  }
}

watch([sourceFilter, classFilter, accountFilter, platformFilter], () => {
  if (
    sourceFilter.value !== "all" &&
    !sourceOptions.value.includes(
      sourceFilter.value as PortfolioAnalysisItem["origen"],
    )
  ) {
    sourceFilter.value = "all";
  }
});
onMounted(load);
</script>

<template>
  <section class="portfolio-page">
    <div
      v-if="loading"
      class="portfolio-loading"
      :aria-label="t('portfolio.loading')"
    >
      <div />
      <div />
      <div />
    </div>

    <article v-else-if="error" class="portfolio-error" role="alert">
      <span>!</span>
      <div>
        <strong>{{ t("portfolio.errors.title") }}</strong>
        <p>{{ error }}</p>
      </div>
      <button type="button" @click="load">{{ t("common.retry") }}</button>
    </article>

    <template v-else-if="portfolio">
      <article class="portfolio-hero">
        <header>
          <div>
            <p class="section-label">{{ t("portfolio.hero.eyebrow") }}</p>
            <h2>{{ t("portfolio.hero.title") }}</h2>
            <p>{{ t("portfolio.hero.description") }}</p>
          </div>
          <button class="manual-action" type="button" @click="openManualCreate">
            <span>＋</span> {{ t("portfolio.actions.manualPosition") }}
          </button>
        </header>

        <div class="hero-grid">
          <div class="portfolio-total">
            <span>{{
              hasFilters
                ? t("portfolio.hero.filteredValue")
                : t("portfolio.hero.portfolioValue")
            }}</span>
            <strong>{{ money(filteredTotal) }}</strong>
            <small v-if="hasFilters">{{
              t("portfolio.hero.ofConsolidated", {
                total: money(portfolio.total),
              })
            }}</small>
            <small v-else>{{
              t("portfolio.hero.positionsWithValue", {
                count: filteredItems.length,
              })
            }}</small>
          </div>
          <div class="portfolio-kpis">
            <div>
              <span>{{ t("portfolio.hero.largestPosition") }}</span>
              <strong>{{ topPosition?.nombre ?? "—" }}</strong>
              <small>{{
                topPosition ? percentage(shareOfFiltered(topPosition)) : "—"
              }}</small>
            </div>
            <div>
              <span>{{ t("portfolio.hero.topThreeConcentration") }}</span>
              <strong>{{ percentage(topThreeShare) }}</strong>
              <small>{{
                topThreeShare > 0.5
                  ? t("portfolio.hero.relevantWeight")
                  : t("portfolio.hero.broadDistribution")
              }}</small>
            </div>
            <div>
              <span>{{ t("portfolio.hero.assetTypes") }}</span>
              <strong>{{ classesCount }}</strong>
              <small>{{ t("portfolio.hero.classesRepresented") }}</small>
            </div>
            <div>
              <span>{{ t("portfolio.hero.accounts") }}</span>
              <strong>{{ accountsCount }}</strong>
              <small>{{ t("portfolio.hero.custodySources") }}</small>
            </div>
          </div>
        </div>

        <div
          class="composition-band"
          :aria-label="t('portfolio.compositionAria')"
        >
          <i
            v-for="item in chartExposures"
            :key="item.label"
            :style="{ width: `${item.share * 100}%`, background: item.color }"
            :title="`${item.label}: ${percentage(item.share)}`"
          />
        </div>

        <div class="lens-control" :aria-label="t('portfolio.classifyAria')">
          <span>{{ t("portfolio.classifyBy") }}</span>
          <button
            v-for="item in groupings"
            :key="item.key"
            type="button"
            :class="{ active: grouping === item.key }"
            :aria-pressed="grouping === item.key"
            @click="grouping = item.key"
          >
            <strong>{{ item.label }}</strong>
            <small>{{ item.hint }}</small>
          </button>
        </div>
      </article>

      <div class="visual-grid">
        <article class="visual-panel allocation-panel">
          <header>
            <div>
              <p class="section-label">{{ t("portfolio.composition") }}</p>
              <h2>
                {{
                  t("portfolio.byGrouping", {
                    grouping: groupingLabel.toLocaleLowerCase(locale),
                  })
                }}
              </h2>
            </div>
            <span>{{
              t("portfolio.groups", { count: groupedExposures.length })
            }}</span>
          </header>
          <div class="allocation-body">
            <div class="donut-wrap">
              <AllocationChart
                v-if="allocationItems.length"
                :items="allocationItems"
              />
              <div class="donut-center">
                <strong>{{ money(filteredTotal) }}</strong>
                <span>{{ t("portfolio.visibleTotal") }}</span>
              </div>
            </div>
            <div class="allocation-legend">
              <div v-for="item in chartExposures" :key="item.label">
                <i :style="{ background: item.color }" />
                <span class="allocation-legend-copy">
                  <strong class="allocation-legend-label">{{
                    item.label
                  }}</strong>
                  <small>{{
                    t("portfolio.positionCount", { count: item.count })
                  }}</small>
                </span>
                <strong class="allocation-legend-share">{{
                  percentage(item.share)
                }}</strong>
                <strong class="allocation-legend-value">{{
                  money(item.value)
                }}</strong>
              </div>
            </div>
          </div>
        </article>

        <article class="visual-panel exposure-panel">
          <header>
            <div>
              <p class="section-label">{{ t("portfolio.concentration") }}</p>
              <h2>{{ t("portfolio.topExposures") }}</h2>
            </div>
            <span>{{
              t("portfolio.topCount", { count: topExposures.length })
            }}</span>
          </header>
          <div class="exposure-list">
            <div v-for="(item, index) in topExposures" :key="item.label">
              <span class="rank">{{ String(index + 1).padStart(2, "0") }}</span>
              <span class="exposure-copy"
                ><strong>{{ item.label }}</strong
                ><small>{{ money(item.value) }}</small></span
              >
              <span class="exposure-track"
                ><i
                  :style="{
                    width: `${item.share * 100}%`,
                    background: item.color,
                  }"
              /></span>
              <strong>{{ percentage(item.share) }}</strong>
            </div>
          </div>
        </article>
      </div>

      <article class="positions-panel">
        <header>
          <div>
            <p class="section-label">{{ t("portfolio.inventory.eyebrow") }}</p>
            <h2>
              {{ t("portfolio.inventory.title") }}
              <span>{{ filteredItems.length }}</span>
            </h2>
          </div>
          <button
            v-if="hasFilters"
            class="clear-filters"
            type="button"
            @click="clearFilters"
          >
            {{ t("portfolio.actions.clearFilters") }}
          </button>
        </header>

        <div class="filter-bar">
          <label class="search-filter">
            <span aria-hidden="true">⌕</span>
            <input
              v-model="search"
              type="search"
              :placeholder="t('portfolio.filters.searchPlaceholder')"
              :aria-label="t('portfolio.filters.searchAria')"
            />
          </label>
          <label
            ><span>{{ t("portfolio.filters.source") }}</span
            ><select
              v-model="sourceFilter"
              :aria-label="t('portfolio.filters.sourceAria')"
            >
              <option value="all">{{ t("common.allMasculine") }}</option>
              <option
                v-for="source in sourceOptions"
                :key="source"
                :value="source"
              >
                {{ sourceLabels[source] }}
              </option>
            </select></label
          >
          <label
            ><span>{{ t("common.type") }}</span
            ><select
              v-model="classFilter"
              :aria-label="t('portfolio.filters.typeAria')"
            >
              <option value="all">{{ t("common.allMasculine") }}</option>
              <option v-for="item in classOptions" :key="item">
                {{ item }}
              </option>
            </select></label
          >
          <label
            ><span>{{ t("common.account") }}</span
            ><select
              v-model="accountFilter"
              :aria-label="t('portfolio.filters.accountAria')"
            >
              <option value="all">{{ t("common.allFeminine") }}</option>
              <option v-for="item in accountOptions" :key="item">
                {{ item }}
              </option>
            </select></label
          >
          <label
            ><span>{{ t("portfolio.platform") }}</span
            ><select
              v-model="platformFilter"
              :aria-label="t('portfolio.filters.platformAria')"
            >
              <option value="all">{{ t("common.allFeminine") }}</option>
              <option v-for="item in platformOptions" :key="item">
                {{ item }}
              </option>
            </select></label
          >
          <label
            ><span>{{ t("portfolio.filters.order") }}</span
            ><select
              v-model="sort"
              :aria-label="t('portfolio.filters.orderAria')"
            >
              <option value="value">
                {{ t("portfolio.filters.highestValue") }}
              </option>
              <option value="weight">
                {{ t("portfolio.filters.highestWeight") }}
              </option>
              <option value="name">{{ t("portfolio.filters.nameAsc") }}</option>
            </select></label
          >
        </div>

        <div class="position-table">
          <div class="position-head">
            <span>{{ t("portfolio.asset") }}</span
            ><span>{{ t("portfolio.typeSubtype") }}</span
            ><span>{{ t("common.account") }}</span
            ><span>{{ t("portfolio.platform") }}</span
            ><span>{{ t("portfolio.value") }}</span
            ><span>{{ t("portfolio.weight") }}</span
            ><span />
          </div>
          <div
            v-for="item in filteredItems"
            :key="item.id"
            class="position-row"
          >
            <span class="position-asset">
              <i :class="item.origen">{{ sourceMarks[item.origen] }}</i>
              <span
                ><strong>{{ item.nombre }}</strong
                ><small>{{
                  item.identificador || sourceLabels[item.origen]
                }}</small></span
              >
            </span>
            <span class="classification"
              ><strong>{{ classificationLabel(item.clase) }}</strong
              ><small>{{ classificationLabel(item.subtipo) }}</small></span
            >
            <span class="account-cell"
              ><strong>{{ item.cuenta }}</strong
              ><small>{{ sourceLabels[item.origen] }}</small></span
            >
            <span>{{ item.plataforma }}</span>
            <strong class="numeric">{{ money(item.valor) }}</strong>
            <span class="weight-cell"
              ><strong>{{ percentage(shareOfFiltered(item)) }}</strong
              ><i><b :style="{ width: `${shareOfFiltered(item) * 100}%` }" /></i
            ></span>
            <button
              v-if="item.origen === 'manual'"
              type="button"
              @click="openManualEdit(item)"
            >
              {{ t("common.edit") }}
            </button>
            <span v-else class="automatic">{{ t("portfolio.automatic") }}</span>
          </div>
          <div v-if="!filteredItems.length" class="empty-positions">
            <strong>{{ t("portfolio.empty.title") }}</strong>
            <button type="button" @click="clearFilters">
              {{ t("portfolio.empty.showAll") }}
            </button>
          </div>
        </div>
      </article>
    </template>

    <dialog ref="manualDialog" class="manual-dialog">
      <form @submit.prevent="saveManual">
        <header>
          <div>
            <p class="section-label">
              {{ t("portfolio.manualDialog.eyebrow") }}
            </p>
            <h2>
              {{
                manualMode === "create"
                  ? t("portfolio.manualDialog.createTitle")
                  : t("portfolio.manualDialog.editTitle")
              }}
            </h2>
          </div>
        </header>
        <div class="manual-fields">
          <label class="wide"
            ><span>{{ t("common.name") }}</span
            ><input v-model="manualForm.nombre" required
          /></label>
          <label
            ><span>{{ t("portfolio.manualDialog.assetType") }}</span
            ><input
              v-model="manualForm.tipo_renta"
              required
              :placeholder="t('portfolio.manualDialog.assetTypePlaceholder')"
          /></label>
          <label
            ><span>{{ t("portfolio.manualDialog.subtype") }}</span
            ><input
              v-model="manualForm.subtipo"
              :placeholder="t('portfolio.manualDialog.subtypePlaceholder')"
          /></label>
          <label
            ><span>{{ t("portfolio.manualDialog.platform") }}</span
            ><input v-model="manualForm.plataforma"
          /></label>
          <label
            ><span>{{ t("portfolio.manualDialog.currentValue") }}</span
            ><input
              v-model="manualForm.efectivo"
              type="number"
              min="0"
              step="0.01"
              required
          /></label>
        </div>
        <p v-if="manualError" class="dialog-error" role="alert">
          {{ manualError }}
        </p>
        <footer>
          <button
            v-if="manualMode === 'edit'"
            class="danger"
            type="button"
            :disabled="manualBusy"
            @click="removeManual"
          >
            {{
              manualDeleteArmed
                ? t("common.confirmDeletion")
                : t("common.delete")
            }}
          </button>
          <i />
          <button
            type="button"
            :disabled="manualBusy"
            @click="manualDialog?.close()"
          >
            {{ t("common.cancel") }}
          </button>
          <button class="primary" type="submit" :disabled="manualBusy">
            {{
              manualBusy
                ? t("common.saving")
                : t("portfolio.actions.savePosition")
            }}
          </button>
        </footer>
      </form>
    </dialog>
  </section>
</template>

<style scoped>
.portfolio-page {
  --portfolio-blue: #587bd8;
  --portfolio-clay: #c78359;
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
.portfolio-hero,
.visual-panel,
.positions-panel,
.portfolio-error {
  border: 1px solid var(--fz-line);
  border-radius: 22px;
  background: var(--fz-surface);
  box-shadow: var(--fz-shadow);
}
.portfolio-hero {
  position: relative;
  overflow: hidden;
  padding: 28px;
}
.portfolio-hero::after {
  content: "";
  position: absolute;
  top: -210px;
  right: -90px;
  width: 520px;
  height: 520px;
  border: 1px solid color-mix(in srgb, var(--portfolio-blue) 18%, transparent);
  border-radius: 50%;
  box-shadow:
    0 0 0 65px color-mix(in srgb, var(--portfolio-blue) 3%, transparent),
    0 0 0 130px color-mix(in srgb, var(--portfolio-blue) 2%, transparent);
  pointer-events: none;
}
.portfolio-hero > header,
.visual-panel > header,
.positions-panel > header,
.manual-dialog header {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.portfolio-hero h2,
.visual-panel h2,
.positions-panel h2,
.manual-dialog h2 {
  margin: 0;
  color: var(--fz-ink);
  font-size: 19px;
  letter-spacing: -0.035em;
}
.portfolio-hero > header p:last-child {
  margin: 5px 0 0;
  color: var(--fz-muted);
  font-size: 9px;
}
.manual-action {
  padding: 10px 14px;
  border: 1px solid
    color-mix(in srgb, var(--portfolio-blue) 40%, var(--fz-line));
  border-radius: 11px;
  background: color-mix(in srgb, var(--portfolio-blue) 9%, var(--fz-surface));
  color: var(--fz-ink);
  font-size: 9px;
  font-weight: 760;
}
.manual-action span {
  margin-right: 4px;
  color: var(--portfolio-blue);
  font-size: 13px;
}
.hero-grid {
  position: relative;
  z-index: 1;
  margin-top: 27px;
  display: grid;
  grid-template-columns: minmax(280px, 0.85fr) minmax(560px, 1.45fr);
  gap: 34px;
}
.portfolio-total > span,
.portfolio-kpis span {
  color: var(--fz-muted);
  font-size: 8px;
}
.portfolio-total > strong {
  display: block;
  margin-top: 5px;
  font-size: clamp(34px, 4.6vw, 53px);
  line-height: 1;
  letter-spacing: -0.065em;
}
.portfolio-total > small {
  display: block;
  margin-top: 9px;
  color: var(--fz-muted);
  font-size: 9px;
}
.portfolio-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-top: 1px solid var(--fz-line);
  border-left: 1px solid var(--fz-line);
}
.portfolio-kpis > div {
  min-width: 0;
  padding: 15px;
  display: grid;
  align-content: center;
  gap: 5px;
  border-right: 1px solid var(--fz-line);
  border-bottom: 1px solid var(--fz-line);
  background: color-mix(in srgb, var(--fz-surface-soft) 45%, transparent);
}
.portfolio-kpis strong {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.portfolio-kpis small {
  color: var(--fz-muted);
  font-size: 7px;
}
.composition-band {
  position: relative;
  z-index: 1;
  height: 8px;
  margin-top: 25px;
  display: flex;
  overflow: hidden;
  border-radius: 99px;
  background: var(--fz-surface-soft);
}
.composition-band i {
  min-width: 2px;
  height: 100%;
  transition: width 0.25s ease;
}
.lens-control {
  position: relative;
  z-index: 1;
  margin-top: 18px;
  display: grid;
  grid-template-columns: 100px repeat(5, minmax(0, 1fr));
  align-items: stretch;
  border: 1px solid var(--fz-line);
  border-radius: 14px;
  background: var(--fz-surface-soft);
}
.lens-control > span {
  padding: 12px;
  display: grid;
  place-items: center start;
  color: var(--fz-muted);
  font-size: 8px;
  font-weight: 730;
}
.lens-control button {
  padding: 10px 12px;
  display: grid;
  gap: 2px;
  border: 0;
  border-left: 1px solid var(--fz-line);
  background: transparent;
  color: var(--fz-muted);
  text-align: left;
  cursor: pointer;
}
.lens-control button strong {
  color: inherit;
  font-size: 9px;
}
.lens-control button small {
  font-size: 7px;
}
.lens-control button.active {
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: inset 0 -3px var(--portfolio-blue);
}
.visual-grid {
  margin-top: 20px;
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(380px, 0.92fr);
  gap: 20px;
}
.visual-panel {
  min-width: 0;
  padding: 24px;
}
.visual-panel > header > span {
  padding: 6px 9px;
  border-radius: 99px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  font-size: 8px;
}
.allocation-body {
  margin-top: 18px;
  display: grid;
  grid-template-columns: 205px minmax(0, 1fr);
  align-items: center;
  gap: 25px;
}
.donut-wrap {
  position: relative;
  min-height: 200px;
  display: grid;
  place-items: center;
}
.donut-wrap :deep(.allocation-chart) {
  width: 200px;
  height: 200px;
}
.donut-center {
  position: absolute;
  width: 104px;
  display: grid;
  text-align: center;
  pointer-events: none;
}
.donut-center strong {
  font-size: 13px;
  letter-spacing: -0.025em;
}
.donut-center span {
  margin-top: 3px;
  color: var(--fz-muted);
  font-size: 7px;
}
.allocation-legend {
  min-width: 0;
}
.allocation-legend > div {
  min-width: 0;
  padding: 8px 0;
  display: grid;
  grid-template-columns: 7px minmax(135px, 1fr) minmax(56px, auto) minmax(
      105px,
      auto
    );
  align-items: center;
  gap: 14px;
  border-bottom: 1px solid var(--fz-line);
}
.allocation-legend > div:last-child {
  border-bottom: 0;
}
.allocation-legend i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.allocation-legend-copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}
.allocation-legend strong {
  overflow: hidden;
  font-size: 8px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.allocation-panel .allocation-legend .allocation-legend-label {
  grid-column: auto;
  grid-row: auto;
}
.allocation-panel .allocation-legend .allocation-legend-share,
.allocation-panel .allocation-legend .allocation-legend-value {
  grid-column: auto;
  grid-row: auto;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.allocation-panel .allocation-legend .allocation-legend-share {
  color: var(--fz-muted);
  font-weight: 660;
}
.allocation-legend small {
  color: var(--fz-muted);
  font-size: 7px;
}
.exposure-list {
  margin-top: 18px;
}
.exposure-list > div {
  padding: 9px 0;
  display: grid;
  grid-template-columns: 24px minmax(100px, 0.8fr) minmax(100px, 1.2fr) 44px;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid var(--fz-line);
}
.exposure-list > div:last-child {
  border-bottom: 0;
}
.rank {
  color: var(--portfolio-clay);
  font-size: 7px;
  font-weight: 800;
}
.exposure-copy {
  min-width: 0;
  display: grid;
}
.exposure-copy strong {
  overflow: hidden;
  font-size: 9px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.exposure-copy small {
  color: var(--fz-muted);
  font-size: 7px;
}
.exposure-track {
  height: 5px;
  overflow: hidden;
  border-radius: 99px;
  background: var(--fz-surface-soft);
}
.exposure-track i {
  height: 100%;
  display: block;
  min-width: 2px;
  border-radius: inherit;
}
.exposure-list > div > strong {
  font-size: 8px;
  text-align: right;
}
.positions-panel {
  margin-top: 20px;
  padding: 24px;
}
.positions-panel h2 span {
  color: var(--fz-muted);
  font-size: 9px;
}
.clear-filters {
  padding: 8px 10px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 8px;
}
.filter-bar {
  margin-top: 18px;
  display: grid;
  grid-template-columns: minmax(180px, 1.35fr) repeat(5, minmax(105px, 0.7fr));
  gap: 8px;
}
.filter-bar label {
  min-width: 0;
  padding: 7px 9px;
  display: grid;
  gap: 3px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
}
.filter-bar label > span {
  color: var(--fz-muted);
  font-size: 7px;
}
.filter-bar select,
.filter-bar input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--fz-ink);
  font: inherit;
  font-size: 8px;
}
.search-filter {
  grid-template-columns: 18px 1fr;
  align-items: center;
}
.search-filter > span {
  grid-row: 1;
  color: var(--portfolio-blue) !important;
  font-size: 15px !important;
}
.search-filter input {
  grid-column: 2;
  grid-row: 1;
}
.position-table {
  margin-top: 18px;
  overflow-x: auto;
}
.position-head,
.position-row {
  min-width: 910px;
  display: grid;
  grid-template-columns:
    minmax(170px, 1.25fr) minmax(125px, 0.9fr) minmax(115px, 0.8fr)
    minmax(100px, 0.72fr) minmax(90px, 0.62fr) minmax(90px, 0.62fr) 62px;
  align-items: center;
  gap: 10px;
}
.position-head {
  padding: 0 10px 9px;
  color: var(--fz-muted);
  font-size: 7px;
}
.position-head span:nth-last-child(-n + 3) {
  text-align: right;
}
.position-row {
  min-height: 64px;
  padding: 10px;
  border-top: 1px solid var(--fz-line);
  color: var(--fz-muted);
  font-size: 8px;
}
.position-asset {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 9px;
}
.position-asset > i {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 10px;
  background: color-mix(
    in srgb,
    var(--portfolio-blue) 11%,
    var(--fz-surface-soft)
  );
  color: var(--portfolio-blue);
  font-style: normal;
  font-weight: 800;
}
.position-asset > i.crypto {
  color: #d8ae4e;
  background: color-mix(in srgb, #d8ae4e 12%, var(--fz-surface-soft));
}
.position-asset > i.real_estate {
  color: var(--portfolio-clay);
  background: color-mix(
    in srgb,
    var(--portfolio-clay) 12%,
    var(--fz-surface-soft)
  );
}
.position-asset > i.fund {
  color: var(--fz-accent);
  background: color-mix(in srgb, var(--fz-accent) 10%, var(--fz-surface-soft));
}
.position-asset > span,
.classification,
.account-cell {
  min-width: 0;
  display: grid;
}
.position-row strong {
  overflow: hidden;
  color: var(--fz-ink);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.position-row small {
  overflow: hidden;
  color: var(--fz-muted);
  font-size: 7px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.numeric {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.weight-cell {
  display: grid;
  justify-items: end;
  gap: 5px;
}
.weight-cell > i {
  width: 56px;
  height: 3px;
  overflow: hidden;
  border-radius: 99px;
  background: var(--fz-surface-soft);
}
.weight-cell b {
  height: 100%;
  display: block;
  min-width: 1px;
  background: var(--portfolio-blue);
}
.position-row > button {
  padding: 6px 8px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 7px;
}
.automatic {
  color: var(--fz-muted);
  font-size: 7px;
  text-align: right;
}
.empty-positions {
  min-height: 180px;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 10px;
  color: var(--fz-muted);
  font-size: 9px;
}
.empty-positions button {
  border: 0;
  background: transparent;
  color: var(--portfolio-blue);
}
.manual-dialog {
  width: min(620px, calc(100vw - 32px));
  padding: 0;
  border: 1px solid var(--fz-line);
  border-radius: 21px;
  background: var(--fz-surface);
  color: var(--fz-ink);
}
.manual-dialog::backdrop {
  background: rgba(5, 10, 8, 0.7);
  backdrop-filter: blur(5px);
}
.manual-dialog form {
  padding: 24px;
}
.manual-dialog header > button {
  width: 31px;
  height: 31px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
}
.manual-fields {
  margin-top: 20px;
  padding: 17px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  border-radius: 14px;
  background: var(--fz-surface-soft);
}
.manual-fields label {
  min-width: 0;
  display: grid;
  gap: 6px;
}
.manual-fields label.wide {
  grid-column: 1 / -1;
}
.manual-fields span {
  color: var(--fz-muted);
  font-size: 8px;
}
.manual-fields input {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font: inherit;
  font-size: 9px;
}
.manual-dialog footer {
  margin-top: 19px;
  display: flex;
  gap: 9px;
}
.manual-dialog footer i {
  flex: 1;
}
.manual-dialog footer button {
  padding: 9px 12px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: transparent;
  color: var(--fz-muted);
}
.manual-dialog footer .primary {
  border-color: var(--portfolio-blue);
  background: var(--portfolio-blue);
  color: #fff;
}
.manual-dialog footer .danger {
  color: var(--fz-negative);
}
.dialog-error {
  color: var(--fz-negative);
  font-size: 9px;
}
.portfolio-error {
  padding: 18px;
  display: flex;
  align-items: center;
  gap: 13px;
}
.portfolio-error > span {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: color-mix(in srgb, var(--fz-negative) 12%, transparent);
  color: var(--fz-negative);
}
.portfolio-error div {
  flex: 1;
}
.portfolio-error p {
  margin: 3px 0 0;
  color: var(--fz-muted);
}
.portfolio-loading {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}
.portfolio-loading div {
  min-height: 350px;
  border-radius: 22px;
  background: var(--fz-surface-soft);
}
.portfolio-loading div:first-child {
  grid-column: 1 / -1;
  min-height: 300px;
}
@media (max-width: 1180px) {
  .hero-grid {
    grid-template-columns: 1fr;
  }
  .portfolio-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .visual-grid {
    grid-template-columns: 1fr;
  }
  .filter-bar {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .search-filter {
    grid-column: span 2;
  }
}
@media (max-width: 720px) {
  .portfolio-page {
    padding: 4px 18px 32px;
  }
  .portfolio-hero,
  .visual-panel,
  .positions-panel {
    padding: 19px 17px;
    border-radius: 18px;
  }
  .portfolio-hero > header {
    flex-direction: column;
  }
  .manual-action {
    width: 100%;
  }
  .portfolio-kpis {
    grid-template-columns: 1fr;
  }
  .lens-control {
    grid-template-columns: repeat(2, 1fr);
    overflow: hidden;
  }
  .lens-control > span {
    grid-column: 1 / -1;
  }
  .lens-control button {
    border-top: 1px solid var(--fz-line);
  }
  .allocation-body {
    grid-template-columns: 1fr;
  }
  .filter-bar {
    grid-template-columns: 1fr;
  }
  .search-filter {
    grid-column: auto;
  }
  .positions-panel > header {
    align-items: flex-start;
    flex-direction: column;
  }
  .manual-fields {
    grid-template-columns: 1fr;
  }
  .manual-fields label.wide {
    grid-column: auto;
  }
}
@media (max-width: 520px) {
  .allocation-legend > div {
    grid-template-columns: 7px minmax(0, 1fr) auto;
    gap: 5px 11px;
  }
  .allocation-legend-copy {
    grid-column: 2;
    grid-row: 1 / 3;
  }
  .allocation-panel .allocation-legend .allocation-legend-share {
    grid-column: 3;
    grid-row: 1;
  }
  .allocation-panel .allocation-legend .allocation-legend-value {
    grid-column: 3;
    grid-row: 2;
  }
}
@media (prefers-reduced-motion: reduce) {
  .composition-band i {
    transition: none;
  }
}

/* Readable type scale: 10 px is the floor for secondary information. */
.section-label,
.portfolio-total > span,
.portfolio-kpis span,
.portfolio-kpis small,
.lens-control > span,
.lens-control button small,
.visual-panel > header > span,
.donut-center span,
.allocation-legend small,
.rank,
.exposure-copy small,
.position-row small,
.automatic {
  font-size: 10px;
}
.portfolio-hero > header p:last-child,
.portfolio-total > small,
.manual-action,
.lens-control button strong,
.allocation-legend strong,
.exposure-list > div > strong,
.positions-panel h2 span,
.clear-filters,
.filter-bar label > span,
.position-head,
.position-row > button,
.manual-fields span,
.dialog-error {
  font-size: 11px;
}
.portfolio-hero h2,
.visual-panel h2,
.positions-panel h2,
.manual-dialog h2 {
  font-size: 20px;
}
.portfolio-kpis strong,
.donut-center strong,
.exposure-copy strong {
  font-size: 12px;
}
.filter-bar select,
.filter-bar input,
.position-row,
.manual-fields input,
.manual-dialog footer button,
.empty-positions {
  font-size: 12px;
}
.position-row {
  min-height: 70px;
}
.position-head,
.position-row {
  min-width: 980px;
}
</style>
