<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import NavIcon from "./NavIcon.vue";
import { useSessionStore } from "../stores/session";
import { buildLabel } from "../buildInfo";
import { useLocalePreference } from "../i18n";

type Theme = "light" | "dark";

const SettingsView = defineAsyncComponent(
  () => import("../views/SettingsView.vue"),
);

const session = useSessionStore();
const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const { locale } = useLocalePreference();
const theme = ref<Theme>("light");
const settingsOpen = ref(false);
const sidebarCollapsed = ref(false);
const overviewLink = computed(() => ({
  to: "/",
  label: t("navigation.overview"),
  icon: "home",
}));
const navigationGroups = computed(() => [
  {
    key: "accounts",
    label: t("shell.navigationGroups.accounts"),
    links: [
      { to: "/ahorro", label: t("navigation.savings"), icon: "wallet" },
      {
        to: "/inversiones",
        label: t("navigation.investmentBalances"),
        icon: "trend",
      },
    ],
  },
  {
    key: "investments",
    label: t("shell.navigationGroups.investments"),
    links: [
      { to: "/portfolio", label: t("navigation.portfolio"), icon: "briefcase" },
      {
        to: "/inmobiliario",
        label: t("navigation.realEstate"),
        icon: "building",
      },
      { to: "/fondos", label: t("navigation.funds"), icon: "funds" },
      { to: "/acciones", label: t("navigation.stocks"), icon: "stocks" },
      { to: "/crypto", label: t("navigation.crypto"), icon: "crypto" },
    ],
  },
  {
    key: "tools",
    label: t("shell.navigationGroups.tools"),
    links: [
      { to: "/divisas", label: t("navigation.currencies"), icon: "currency" },
    ],
  },
]);
const settingsLink = computed(() => ({
  label: t("navigation.settings"),
  icon: "settings",
}));
const pageTitle = computed(() => {
  const titleKey = route.meta.titleKey;
  return typeof titleKey === "string" ? t(titleKey) : "Finanzr";
});
const dateLabel = computed(() =>
  new Intl.DateTimeFormat(locale.value, {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date()),
);
const initials = computed(() => {
  const source =
    session.user?.display_name ||
    session.user?.email ||
    t("shell.userFallback");
  return source
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
});
const activeWorkspace = computed(
  () =>
    session.user?.workspaces.find(
      (item) => item.id === session.user?.active_workspace_id,
    ) ?? session.user?.workspaces[0],
);

watch(
  pageTitle,
  (title) => {
    document.title = `${title} · Finanzr`;
  },
  { immediate: true },
);

function toggleTheme() {
  theme.value = theme.value === "light" ? "dark" : "light";
  localStorage.setItem("finanzr-theme", theme.value);
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
  localStorage.setItem(
    "finanzr-sidebar-collapsed",
    String(sidebarCollapsed.value),
  );
}

async function logout() {
  await session.logout();
  await router.push("/login");
}

onMounted(() => {
  const saved = localStorage.getItem("finanzr-theme");
  theme.value =
    saved === "light" || saved === "dark"
      ? saved
      : window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
  sidebarCollapsed.value =
    localStorage.getItem("finanzr-sidebar-collapsed") === "true";
});
</script>

<template>
  <div
    class="app-shell"
    :class="{ 'sidebar-collapsed': sidebarCollapsed }"
    :data-theme="theme"
  >
    <aside
      class="app-sidebar"
      :inert="settingsOpen"
      :aria-hidden="settingsOpen ? 'true' : undefined"
    >
      <div class="app-sidebar-header">
        <RouterLink class="app-brand" to="/" :aria-label="t('shell.homeLabel')">
          <span class="app-brand-name"
            >finanzr<span class="app-brand-dot" aria-hidden="true"
              >.</span
            ></span
          >
        </RouterLink>
        <button
          class="sidebar-collapse-button"
          type="button"
          :title="
            sidebarCollapsed
              ? t('shell.expandNavigation')
              : t('shell.collapseNavigation')
          "
          :aria-label="
            sidebarCollapsed
              ? t('shell.expandNavigationAria')
              : t('shell.collapseNavigationAria')
          "
          :aria-expanded="!sidebarCollapsed"
          @click="toggleSidebar"
        >
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <path d="m12.5 5-5 5 5 5" />
          </svg>
        </button>
      </div>

      <nav class="app-nav" :aria-label="t('shell.mainSections')">
        <RouterLink
          class="app-nav-primary"
          :to="overviewLink.to"
          exact-active-class="active"
          :title="overviewLink.label"
        >
          <NavIcon :name="overviewLink.icon" />
          <span>{{ overviewLink.label }}</span>
        </RouterLink>
        <section
          v-for="group in navigationGroups"
          :key="group.key"
          class="app-nav-group"
          :aria-labelledby="`nav-group-${group.key}`"
        >
          <p :id="`nav-group-${group.key}`" class="app-nav-group-label">
            {{ group.label }}
          </p>
          <div class="app-nav-links">
            <RouterLink
              v-for="link in group.links"
              :key="link.to"
              :to="link.to"
              exact-active-class="active"
              :title="link.label"
            >
              <NavIcon :name="link.icon" />
              <span>{{ link.label }}</span>
            </RouterLink>
          </div>
        </section>
      </nav>

      <div class="app-sidebar-footer">
        <button
          class="app-nav-button sidebar-settings-button"
          type="button"
          :class="{ active: settingsOpen }"
          :title="settingsLink.label"
          :aria-pressed="settingsOpen"
          @click="settingsOpen = true"
        >
          <NavIcon :name="settingsLink.icon" />
          <span>{{ settingsLink.label }}</span>
        </button>

        <label
          v-if="session.user && session.user.workspaces.length > 1"
          class="workspace-picker"
        >
          <span class="avatar">{{ initials }}</span>
          <span class="workspace-copy">
            <small>{{ t("shell.activeSpace") }}</small>
            <select
              :value="session.user.active_workspace_id ?? ''"
              :aria-label="t('shell.activeWorkspace')"
              @change="
                session.selectWorkspace(
                  ($event.target as HTMLSelectElement).value,
                )
              "
            >
              <option
                v-for="item in session.user.workspaces"
                :key="item.id"
                :value="item.id"
              >
                {{ item.name }}
              </option>
            </select>
          </span>
        </label>
        <div v-else class="workspace-picker">
          <span class="avatar">{{ initials }}</span>
          <span class="workspace-copy">
            <strong>{{ activeWorkspace?.name ?? t("shell.mySpace") }}</strong>
            <small>{{
              session.user?.display_name || session.user?.email
            }}</small>
          </span>
        </div>
        <button
          class="logout-button"
          type="button"
          :title="t('shell.logOut')"
          @click="logout"
        >
          <span aria-hidden="true">↗</span><span>{{ t("shell.logOut") }}</span>
        </button>
        <p class="app-build-info" :title="t('shell.deployedVersion')">
          <span>{{ t("shell.version") }}</span> {{ buildLabel }}
        </p>
      </div>
    </aside>

    <main
      class="app-main"
      :inert="settingsOpen"
      :aria-hidden="settingsOpen ? 'true' : undefined"
    >
      <header class="app-topbar">
        <div>
          <p>{{ dateLabel }}</p>
          <h1>{{ pageTitle }}</h1>
        </div>
        <button
          class="app-theme-toggle"
          type="button"
          :aria-label="
            theme === 'light'
              ? t('shell.enableDarkMode')
              : t('shell.enableLightMode')
          "
          @click="toggleTheme"
        >
          <span aria-hidden="true">{{ theme === "light" ? "☼" : "☾" }}</span>
          {{ theme === "light" ? t("shell.light") : t("shell.dark") }}
        </button>
      </header>
      <RouterView
        :key="`${route.fullPath}:${session.user?.active_workspace_id ?? ''}`"
      />
    </main>
    <SettingsView v-if="settingsOpen" @close="settingsOpen = false" />
  </div>
</template>
