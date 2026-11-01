import { apiMessages } from "../i18n/apiMessages";

let csrfToken = "";
let workspaceId: string | null = null;
let workspaceGeneration = 0;
const pending = new Set<AbortController>();
function contextChanged() {
  const error = new Error(clientMessage("workspaceChanged"));
  error.name = "WorkspaceContextChangedError";
  return error;
}

export function setWorkspaceContext(id: string | null) {
  if (id === workspaceId) return;
  workspaceId = id;
  workspaceGeneration += 1;
  for (const controller of pending) controller.abort();
  pending.clear();
}

type ApiClientMessageKey = keyof typeof apiMessages.en.apiClient;

function preferredLanguage() {
  return (
    globalThis.localStorage?.getItem("finanzr-language") ??
    globalThis.document?.documentElement.lang
  );
}

function clientMessage(key: ApiClientMessageKey): string {
  const locale = preferredLanguage()?.toLowerCase().startsWith("es")
    ? "es-ES"
    : "en";
  return apiMessages[locale].apiClient[key];
}

async function csrf(): Promise<string> {
  if (csrfToken) return csrfToken;
  const response = await fetch("/api/auth/csrf", {
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error(clientMessage("secureSessionError"));
  csrfToken = (await response.json()).csrfToken;
  return csrfToken;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const generation = workspaceGeneration;
  const context = workspaceId;
  const scoped = !["/auth/csrf", "/auth/login", "/auth/logout"].includes(path);
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (scoped && context && path !== "/auth/me")
    headers.set("X-Workspace-ID", context);
  const language = preferredLanguage();
  if (language) headers.set("Accept-Language", language);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method))
    headers.set("X-CSRFToken", await csrf());
  if (scoped && generation !== workspaceGeneration) throw contextChanged();
  const controller = new AbortController();
  if (scoped) pending.add(controller);
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers,
      credentials: "same-origin",
      signal: init.signal ?? controller.signal,
    });
  } finally {
    pending.delete(controller);
  }
  if (scoped && generation !== workspaceGeneration) throw contextChanged();
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      body.message ??
        body.error ??
        body.detail ??
        `HTTP error ${response.status}`,
    );
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json();
  if (scoped && generation !== workspaceGeneration) throw contextChanged();
  if (typeof data.csrfToken === "string") csrfToken = data.csrfToken;
  return data;
}

export const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});
