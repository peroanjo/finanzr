import { createRouter, createWebHistory } from "vue-router";
import { useSessionStore } from "./stores/session";
import AppShell from "./components/AppShell.vue";

export const router = createRouter({
  history: createWebHistory("/app/"),
  routes: [
    {
      path: "/login",
      component: () => import("./views/LoginView.vue"),
      meta: { public: true },
    },
    ...(import.meta.env.DEV
      ? [
          {
            path: "/design-preview",
            component: () => import("./views/DesignPreviewView.vue"),
            meta: { public: true },
          },
        ]
      : []),
    {
      path: "/",
      component: AppShell,
      children: [
        {
          path: "",
          component: () => import("./views/OverviewView.vue"),
          meta: { titleKey: "navigation.overview" },
        },
        {
          path: "ahorro",
          component: () => import("./views/SavingsView.vue"),
          meta: { titleKey: "navigation.savings" },
        },
        {
          path: "portfolio",
          component: () => import("./views/PortfolioView.vue"),
          meta: { titleKey: "navigation.portfolio" },
        },
        {
          path: "inmobiliario",
          component: () => import("./views/RealEstateView.vue"),
          meta: { titleKey: "navigation.realEstate" },
        },
        {
          path: "fondos",
          component: () => import("./views/FundsView.vue"),
          meta: { titleKey: "navigation.funds" },
        },
        {
          path: "acciones",
          component: () => import("./views/StocksView.vue"),
          meta: { titleKey: "navigation.stocks" },
        },
        {
          path: "crypto",
          component: () => import("./views/CryptoView.vue"),
          meta: { titleKey: "navigation.crypto" },
        },
        {
          path: "divisas",
          component: () => import("./views/CurrenciesView.vue"),
          meta: { titleKey: "navigation.currencies" },
        },
        {
          path: "inversiones",
          component: () => import("./views/InvestmentBalancesView.vue"),
          meta: { titleKey: "navigation.investmentBalances" },
        },
        { path: "configuracion", redirect: "/" },
      ],
    },
  ],
});
router.beforeEach(async (to) => {
  const session = useSessionStore();
  if (session.loading) await session.restore();
  if (!to.meta.public && !session.user) return "/login";
  if (to.path === "/login" && session.user) return "/";
});
