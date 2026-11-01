import { defineStore } from "pinia";
import { api, json, setWorkspaceContext } from "../api/client";
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
    switchingWorkspace: false,
  }),
  actions: {
    applySession(user: UserSession) {
      this.user = user;
      setWorkspaceContext(user.active_workspace_id);
      applyLocale(user.language);
      applyWorkspaceCurrency(user);
    },
    async restore() {
      try {
        this.applySession(await api<UserSession>("/auth/me"));
      } catch (reason) {
        if (
          reason instanceof Error &&
          ["WorkspaceContextChangedError", "AbortError"].includes(reason.name)
        )
          return;
        this.user = null;
        setWorkspaceContext(null);
      } finally {
        this.loading = false;
      }
    },
    async login(email: string, password: string) {
      this.user = await api<UserSession>(
        "/auth/login",
        json("POST", { email, password }),
      );
      this.applySession(this.user);
    },
    async logout() {
      await api("/auth/logout", { method: "POST" });
      this.user = null;
      setWorkspaceContext(null);
      applyReportingCurrency("EUR");
    },
    async selectWorkspace(workspace_id: string) {
      if (this.switchingWorkspace) return;
      this.switchingWorkspace = true;
      try {
        this.applySession(
          await api<UserSession>(
            "/workspaces/current",
            json("PUT", { workspace_id }),
          ),
        );
        localStorage.setItem("finanzr-workspace-revision", String(Date.now()));
      } finally {
        this.switchingWorkspace = false;
      }
    },
    async updateAccount(
      display_name: string,
      email: string,
      current_password: string,
    ) {
      this.applySession(
        await api<UserSession>(
          "/auth/account",
          json("PATCH", { display_name, email, current_password }),
        ),
      );
    },
    async updateLanguage(language: "es-ES" | "en" | null) {
      this.applySession(
        await api<UserSession>(
          "/auth/preferences",
          json("PATCH", { language }),
        ),
      );
      return this.user;
    },
    async updateSummarySources(
      summary_sources: UserSession["summary_sources"],
    ) {
      this.applySession(
        await api<UserSession>(
          "/auth/preferences",
          json("PATCH", { summary_sources }),
        ),
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
