/**
 * HTTP client wrapper.
 *
 * - Adds the Bearer access token from the auth store on every request.
 * - On 401 (token expired), tries POST /auth/refresh once via the HttpOnly cookie.
 * - On refresh success, retries the original request transparently.
 * - On refresh failure, clears the auth store and lets the caller see the 401.
 *
 * Cookies are sent automatically by `credentials: "include"` — refresh token
 * lives in an HttpOnly cookie, never touched by JS.
 */

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "/api/v1").replace(/\/$/, "");

export type ApiError = {
  status: number;
  code: string;
  message: string;
  detail?: unknown;
};

let _accessTokenGetter: () => string | null = () => null;
let _accessTokenSetter: (t: string | null) => void = () => {};
let _onAuthLost: () => void = () => {};

export function configureClient(opts: {
  getAccessToken: () => string | null;
  setAccessToken: (t: string | null) => void;
  onAuthLost: () => void;
}): void {
  _accessTokenGetter = opts.getAccessToken;
  _accessTokenSetter = opts.setAccessToken;
  _onAuthLost = opts.onAuthLost;
}

let _refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (_refreshInFlight) return _refreshInFlight;
  _refreshInFlight = (async () => {
    try {
      const r = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!r.ok) return null;
      const body = (await r.json()) as { access_token: string };
      _accessTokenSetter(body.access_token);
      return body.access_token;
    } catch {
      return null;
    } finally {
      _refreshInFlight = null;
    }
  })();
  return _refreshInFlight;
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  /** Skip the auth header (e.g. for /auth/login) */
  anonymous?: boolean;
  /** Return raw Response instead of JSON-parsing */
  raw?: boolean;
};

export async function api<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;

  const buildInit = (token: string | null): RequestInit => {
    const headers: Record<string, string> = {
      Accept: "application/json",
      ...opts.headers,
    };
    if (opts.body !== undefined && !(opts.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }
    if (token && !opts.anonymous) {
      headers.Authorization = `Bearer ${token}`;
    }
    return {
      method: opts.method ?? "GET",
      headers,
      credentials: "include",
      body:
        opts.body === undefined
          ? undefined
          : opts.body instanceof FormData
            ? opts.body
            : JSON.stringify(opts.body),
    };
  };

  let response = await fetch(url, buildInit(_accessTokenGetter()));

  if (response.status === 401 && !opts.anonymous && !path.startsWith("/auth/")) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      response = await fetch(url, buildInit(newToken));
    } else {
      _onAuthLost();
    }
  }

  if (opts.raw) return response as unknown as T;

  if (!response.ok) {
    let body: { error?: string; message?: string; detail?: unknown } | null = null;
    try {
      body = (await response.json()) as typeof body;
    } catch {
      // ignore non-JSON
    }
    const err: ApiError = {
      status: response.status,
      code: body?.error ?? `http_${response.status}`,
      message: body?.message ?? response.statusText,
      detail: body?.detail,
    };
    throw err;
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const apiBaseUrl = API_BASE;
