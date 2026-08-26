import { defineStore } from "pinia";
import { api, json } from "../api/client";
import type { UserSession } from "../types/api";
import { applyLocale, applyReportingCurrency } from "../i18n";

function applyWorkspaceCurrency(user: UserSession) {
  const active = user.workspaces.find(
    (item) => item.id === user.active_workspace_id,
  );
  applyReportingCurrency(active?.base_currency);
}

export const useSessionStore = defineStore("session", {
  state: () => ({
    user: null as UserSession | null,
    loading: true,
    summaryRevision: 0,
  }),
  actions: {
    async restore() {
      try {
        this.user = await api<UserSession>("/auth/me");
        applyLocale(this.user.language);
        applyWorkspaceCurrency(this.user);
      } catch {
        this.user = null;
      } finally {
        this.loading = false;
      }
    },
    async login(email: string, password: string) {
      this.user = await api<UserSession>(
        "/auth/login",
        json("POST", { email, password }),
      );
      applyLocale(this.user.language);
      applyWorkspaceCurrency(this.user);
    },
    async logout() {
      await api("/auth/logout", { method: "POST" });
      this.user = null;
      applyReportingCurrency("EUR");
    },
    async selectWorkspace(workspace_id: string) {
      this.user = await api<UserSession>(
        "/workspaces/current",
        json("PUT", { workspace_id }),
      );
      applyWorkspaceCurrency(this.user);
    },
    async updateAccount(
      display_name: string,
      email: string,
      current_password: string,
    ) {
      this.user = await api<UserSession>(
        "/auth/account",
        json("PATCH", { display_name, email, current_password }),
      );
    },
    async updateLanguage(language: "es-ES" | "en" | null) {
      this.user = await api<UserSession>(
        "/auth/preferences",
        json("PATCH", { language }),
      );
      applyLocale(this.user.language);
      return this.user;
    },
    async updateSummarySources(
      summary_sources: UserSession["summary_sources"],
    ) {
      this.user = await api<UserSession>(
        "/auth/preferences",
        json("PATCH", { summary_sources }),
      );
      this.summaryRevision += 1;
      window.dispatchEvent(new CustomEvent("finanzr:summary-sources-updated"));
      return this.user;
    },
    async changePassword(
      current_password: string,
      password: string,
      password_confirmation: string,
    ) {
      await api(
        "/auth/password",
        json("POST", {
          current_password,
          password,
          password_confirmation,
        }),
      );
    },
  },
});
