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
