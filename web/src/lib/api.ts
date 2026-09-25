// Клиент API. Запросы идут на тот же домен (/api), Next проксирует их в FastAPI.

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public detail: Record<string, unknown> = {},
  ) {
    super(code);
  }
}

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setApiToken(value: string | null) {
  token = value;
}

export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

type Options = {
  method?: string;
  json?: unknown;
  form?: FormData;
};

export async function api<T>(path: string, { method = "GET", json, form }: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = form;
  }

  let response: Response;
  try {
    response = await fetch(`/api${path}`, { method, headers, body, cache: "no-store" });
  } catch {
    throw new ApiError(0, "network");
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data?.detail === "object" && data.detail ? data.detail : {};
    const code = typeof detail.code === "string" ? detail.code : "unknown";
    if (response.status === 401 && path !== "/auth/code" && path !== "/auth/telegram") {
      onUnauthorized?.();
    }
    throw new ApiError(response.status, code, detail);
  }
  return data as T;
}

/** Файл с авторизацией (фото работы): <img> не умеет слать Bearer-токен,
 *  поэтому скачиваем blob и показываем через object URL. */
export async function apiBlob(path: string): Promise<Blob> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { headers, cache: "no-store" });
  } catch {
    throw new ApiError(0, "network");
  }
  if (!response.ok) throw new ApiError(response.status, response.status === 404 ? "file_not_found" : "unknown");
  return response.blob();
}

export function errorCode(error: unknown): string {
  return error instanceof ApiError ? error.code : "unknown";
}
