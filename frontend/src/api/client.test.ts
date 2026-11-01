import { beforeEach, describe, expect, it, vi } from "vitest";

describe("API client localization", () => {
  const storage = new Map<string, string>();

  beforeEach(() => {
    vi.resetModules();
    storage.clear();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      clear: () => storage.clear(),
    });
    document.documentElement.lang = "";
    vi.stubGlobal("fetch", vi.fn());
  });

  it("uses the English source message when no locale has been established", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 500 }));
    const { api } = await import("./client");

    await expect(
      api("/example", { method: "POST", body: "{}" }),
    ).rejects.toThrow("A secure session could not be started");
  });

  it("uses the Spanish translation for the bootstrap error", async () => {
    localStorage.setItem("finanzr-language", "es-ES");
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 500 }));
    const { api } = await import("./client");

    await expect(
      api("/example", { method: "POST", body: "{}" }),
    ).rejects.toThrow("No se pudo iniciar una sesión segura");
  });

  it("preserves the selected locale in the Accept-Language header", async () => {
    localStorage.setItem("finanzr-language", "es-ES");
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrfToken: "token" }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
      );
    const { api } = await import("./client");

    await api("/example", { method: "POST", body: "{}" });

    const [, request] = vi.mocked(fetch).mock.calls[1];
    expect(new Headers(request?.headers).get("Accept-Language")).toBe("es-ES");
  });
});

describe("workspace request isolation", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal("fetch", vi.fn());
  });

  it("pins financial requests to the workspace where they started", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );
    const { api, setWorkspaceContext } = await import("./client");
    setWorkspaceContext("synthetic-private");
    await api("/savings/accounts");
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(new Headers(init?.headers).get("X-Workspace-ID")).toBe(
      "synthetic-private",
    );
  });

  it("discards a late response after switching workspaces", async () => {
    let resolveResponse!: (value: Response) => void;
    vi.mocked(fetch).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveResponse = resolve;
        }),
    );
    const { api, setWorkspaceContext } = await import("./client");
    setWorkspaceContext("synthetic-private");
    const pending = api("/savings/accounts");
    const rejected = expect(pending).rejects.toThrow();
    const signal = vi.mocked(fetch).mock.calls[0][1]?.signal;
    setWorkspaceContext("synthetic-shared");
    expect(signal?.aborted).toBe(true);
    resolveResponse(
      new Response(JSON.stringify([{ name: "Private data" }]), { status: 200 }),
    );
    await rejected;
  });
});

describe("workspace-bound session responses", () => {
  it.each([
    "/auth/preferences",
    "/auth/account",
    "/auth/me",
    "/workspaces/current",
  ])("rejects stale %s responses", async (path) => {
    vi.resetModules();
    let finish!: (value: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            finish = resolve;
          }),
      ),
    );
    const { api, setWorkspaceContext } = await import("./client");
    setWorkspaceContext("synthetic-private");
    const pending = api(path);
    const assertion = expect(pending).rejects.toMatchObject({
      name: "WorkspaceContextChangedError",
    });
    setWorkspaceContext("synthetic-shared");
    finish(
      new Response(
        JSON.stringify({ active_workspace_id: "synthetic-private" }),
        { status: 200 },
      ),
    );
    await assertion;
  });
});
