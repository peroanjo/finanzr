<script setup lang="ts">
import {
  onMounted,
  onBeforeUnmount,
  computed,
  defineAsyncComponent,
  ref,
  watch,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import NavIcon from "./NavIcon.vue";
import WorkspaceVisibilityBadge from "./WorkspaceVisibilityBadge.vue";
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
const sidebarCollapsed = ref(true);
const navigationTooltip = ref<{
  label: string;
  left: number;
  top: number;
} | null>(null);

function hideNavigationTooltip() {
  navigationTooltip.value = null;
}

function showNavigationTooltip(event: Event) {
  if (
    window.innerWidth <= 720 ||
    (!sidebarCollapsed.value && window.innerWidth > 1100)
  ) {
    hideNavigationTooltip();
    return;
  }
  const control =
    event.target instanceof Element
      ? event.target.closest<HTMLElement>(
          ".app-nav a, .sidebar-settings-button, .logout-button",
        )
      : null;
  const label = control?.getAttribute("aria-label");
  if (!control || !label) {
    hideNavigationTooltip();
    return;
  }
  const bounds = control.getBoundingClientRect();
  const sidebarBounds = control
    .closest(".app-sidebar")!
    .getBoundingClientRect();
  navigationTooltip.value = {
    label,
    left: sidebarBounds.right + 10,
    top: Math.max(
      24,
      Math.min(window.innerHeight - 24, bounds.top + bounds.height / 2),
    ),
  };
}

watch(
  [sidebarCollapsed, settingsOpen, locale, () => route.fullPath],
  hideNavigationTooltip,
);
onMounted(() => {
  window.addEventListener("resize", hideNavigationTooltip);
  window.addEventListener("scroll", hideNavigationTooltip, true);
  window.addEventListener("blur", hideNavigationTooltip);
});
onBeforeUnmount(() => {
  window.removeEventListener("resize", hideNavigationTooltip);
  window.removeEventListener("scroll", hideNavigationTooltip, true);
  window.removeEventListener("blur", hideNavigationTooltip);
});
const logoUrl = `${import.meta.env.BASE_URL}finanzr-logo.svg`;
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
function syncWorkspace(event: StorageEvent) {
  if (event.key === "finanzr-workspace-revision" && session.user)
    void session.restore();
}
onMounted(() => window.addEventListener("storage", syncWorkspace));
onBeforeUnmount(() => window.removeEventListener("storage", syncWorkspace));

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
    localStorage.getItem("finanzr-sidebar-collapsed") !== "false";
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
      @pointerover="showNavigationTooltip"
      @pointerleave="hideNavigationTooltip"
      @focusin="showNavigationTooltip"
      @focusout="hideNavigationTooltip"
      @keydown.esc="hideNavigationTooltip"
    >
      <div class="app-sidebar-header">
        <RouterLink class="app-brand" to="/" :aria-label="t('shell.homeLabel')">
          <img
            class="app-brand-mark"
            :src="logoUrl"
            alt=""
            width="30"
            height="30"
          />
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
          :aria-label="overviewLink.label"
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
              :aria-label="link.label"
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
          :aria-label="settingsLink.label"
          :aria-pressed="settingsOpen"
          @click="settingsOpen = true"
        >
          <NavIcon :name="settingsLink.icon" />
          <span>{{ settingsLink.label }}</span>
        </button>

        <button
          class="logout-button"
          type="button"
          :aria-label="t('shell.logOut')"
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
        <div class="app-topbar-actions">
          <div
            class="workspace-picker"
            :class="{
              'workspace-picker-switchable':
                session.user && session.user.workspaces.length > 1,
            }"
          >
            <span class="avatar" aria-hidden="true">{{ initials }}</span>
            <span class="workspace-copy">
              <span class="workspace-title-row">
                <strong :title="activeWorkspace?.name">{{
                  activeWorkspace?.name ?? t("shell.mySpace")
                }}</strong>
              </span>
              <span class="workspace-identity-row">
                <small
                  :title="session.user?.display_name || session.user?.email"
                  >{{
                    session.user?.display_name || session.user?.email
                  }}</small
                >
                <WorkspaceVisibilityBadge
                  v-if="activeWorkspace"
                  :shared="Boolean(activeWorkspace.is_shared)"
                />
              </span>
            </span>
            <svg
              v-if="session.user && session.user.workspaces.length > 1"
              class="workspace-picker-chevron"
              viewBox="0 0 16 16"
              fill="none"
              aria-hidden="true"
            >
              <path d="m4.5 6.25 3.5 3.5 3.5-3.5" />
            </svg>
            <select
              v-if="session.user && session.user.workspaces.length > 1"
              :disabled="session.switchingWorkspace"
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
                {{ item.name }} ·
                {{
                  t(item.is_shared ? "workspace.shared" : "workspace.private")
                }}
              </option>
            </select>
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
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <template v-if="theme === 'light'">
                <circle cx="12" cy="12" r="4" />
                <path
                  d="M12 2v2m0 16v2M2 12h2m16 0h2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"
                />
              </template>
              <path
                v-else
                d="M20.5 13.1A8.5 8.5 0 0 1 10.9 3.5a8.5 8.5 0 1 0 9.6 9.6Z"
              />
            </svg>
          </button>
        </div>
      </header>
      <RouterView
        :key="`${route.fullPath}:${session.user?.active_workspace_id ?? ''}`"
      />
    </main>
    <span
      v-if="navigationTooltip"
      class="app-nav-tooltip"
      aria-hidden="true"
      :style="{
        left: `${navigationTooltip.left}px`,
        top: `${navigationTooltip.top}px`,
      }"
      >{{ navigationTooltip.label }}</span
    >
    <SettingsView v-if="settingsOpen" @close="settingsOpen = false" />
  </div>
</template>
