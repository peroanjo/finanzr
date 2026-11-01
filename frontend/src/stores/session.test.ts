import { flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { expect, it, vi } from "vitest";
import type { UserSession } from "../types/api";

it("keeps the displayed workspace and request context aligned after a late preferences response", async () => {
  vi.resetModules();
  const storage = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
  });
  setActivePinia(createPinia());
  const user = (active: string): UserSession => ({
    id: "synthetic-user",
    email: "synthetic@example.com",
    display_name: "Synthetic",
    role: "user",
    active_workspace_id: active,
    workspaces: ["private", "shared"].map((id) => ({
      id,
      name: id,
      slug: id,
      base_currency: "EUR",
      role: "owner",
    })),
    language: "en",
    preferred_language: "en",
    default_language: "en",
  });
  let finishPreferences!: (value: Response) => void;
  const fetchMock = vi.fn((url: string) => {
    if (url === "/api/auth/csrf")
      return Promise.resolve(
        new Response(JSON.stringify({ csrfToken: "synthetic-csrf" }), {
          status: 200,
        }),
      );
    if (url === "/api/auth/preferences")
      return new Promise<Response>((resolve) => {
        finishPreferences = resolve;
      });
    return Promise.resolve(
      new Response(
        JSON.stringify(url === "/api/workspaces/current" ? user("shared") : []),
        { status: 200 },
      ),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  const { useSessionStore } = await import("./session");
  const { api } = await import("../api/client");
  const session = useSessionStore();
  session.applySession(user("private"));
  const pending = session.updateSummarySources(["savings"]);
  const assertion = expect(pending).rejects.toMatchObject({
    name: "WorkspaceContextChangedError",
  });
  await flushPromises();
  await session.selectWorkspace("shared");
  finishPreferences(
    new Response(JSON.stringify(user("private")), { status: 200 }),
  );
  await assertion;
  expect(session.user?.active_workspace_id).toBe("shared");
  await api("/savings/accounts");
  const [, request] = vi.mocked(fetch).mock.calls.at(-1)!;
  expect(new Headers(request?.headers).get("X-Workspace-ID")).toBe("shared");
});
