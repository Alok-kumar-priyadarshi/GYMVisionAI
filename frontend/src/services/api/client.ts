/**
 * The HTTP client.
 *
 * `instructions/03_FRONTEND_RULES.md` section 6 routes every backend call
 * through this layer, and forbids components from calling `fetch` directly.
 *
 * The client owns three concerns no component should repeat: attaching the
 * access token, unwrapping the response envelope, and refreshing an expired
 * token once before giving up.
 */

import { configured } from "@/config/env";
import type { ErrorEnvelope, Pagination, SuccessEnvelope } from "@/types/api";

const API_BASE = configured(import.meta.env.VITE_API_BASE_URL, "/api/v1");

/**
 * How long any single request may take before it is aborted.
 *
 * A request with no deadline does not merely hang: `Promise.race` against a
 * timer leaves the original request running, so a call the user was already
 * told had failed can still succeed minutes later and apply its result. Signing
 * in was the visible case — the page reported a failure and then logged the
 * user in several minutes afterwards. Aborting the request itself is what makes
 * a timeout final.
 */
const REQUEST_TIMEOUT_MS = 20_000;

const ACCESS_TOKEN_KEY = "gymvision.accessToken";
const REFRESH_TOKEN_KEY = "gymvision.refreshToken";

/** An error carrying the backend's documented error code. */
export class ApiError extends Error {
  // Declared as fields rather than constructor parameter properties, which the
  // project's `erasableSyntaxOnly` setting disallows.
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }

  /** Whether the request failed because the session is no longer valid. */
  get isAuthError(): boolean {
    return this.code.startsWith("AUTH-");
  }
}

/** Raised when the backend cannot be reached at all. */
export class NetworkError extends Error {
  constructor() {
    super("We could not reach GymVision. Check your connection and try again.");
    this.name = "NetworkError";
  }
}

/** Raised when the backend accepted the request but did not answer in time. */
export class TimeoutError extends Error {
  constructor() {
    super("The server took too long to respond. Please try again.");
    this.name = "TimeoutError";
  }
}

/**
 * Token storage.
 *
 * `localStorage` is readable by any script on the origin, which is a real
 * trade-off. The alternative documented by the security architecture is
 * httpOnly cookies, which the token contracts do not use: they return tokens in
 * the response body for the client to hold. This is recorded in the frontend
 * README as a decision to revisit.
 */
export const tokenStore = {
  access: (): string | null => localStorage.getItem(ACCESS_TOKEN_KEY),
  refresh: (): string | null => localStorage.getItem(REFRESH_TOKEN_KEY),
  save(accessToken: string, refreshToken?: string): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    if (refreshToken) localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },
  clear(): void {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** Skip the Authorization header, for the public login endpoints. */
  anonymous?: boolean;
  query?: Record<string, string | number | undefined>;
  signal?: AbortSignal;
}

/** A response plus its pagination block, when the endpoint returns one. */
export interface Paged<T> {
  data: T;
  pagination?: Pagination;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = `${API_BASE}${path}`;
  if (!query) return url;

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) params.set(key, String(value));
  }
  const search = params.toString();
  return search ? `${url}?${search}` : url;
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const token = tokenStore.access();
  if (!options.anonymous && token) {
    headers.Authorization = `Bearer ${token}`;
  }

  // A caller's own signal still wins; the deadline is added on top of it.
  const deadline = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const signal = options.signal
    ? AbortSignal.any([options.signal, deadline])
    : deadline;

  try {
    return await fetch(buildUrl(path, options.query), {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal,
    });
  } catch {
    // Distinguish "took too long" from "could not connect": they point the user
    // at completely different problems.
    if (deadline.aborted) throw new TimeoutError();
    // A thrown fetch means the network failed, not that the API rejected us.
    throw new NetworkError();
  }
}

/** Exchange the refresh token for a new access token. Returns success. */
async function refreshSession(): Promise<boolean> {
  const refreshToken = tokenStore.refresh();
  if (!refreshToken) return false;

  const response = await send("/auth/refresh", {
    method: "POST",
    body: { refreshToken },
    anonymous: true,
  });

  if (!response.ok) {
    tokenStore.clear();
    return false;
  }

  // Parsed defensively: a non-JSON body here threw a raw SyntaxError out of the
  // request, past every typed error the callers handle.
  try {
    const payload = (await response.json()) as SuccessEnvelope<{
      accessToken: string;
    }>;
    if (!payload?.data?.accessToken) return false;
    tokenStore.save(payload.data.accessToken);
    return true;
  } catch {
    return false;
  }
}

async function unwrap<T>(response: Response): Promise<Paged<T>> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    // Not a JSON body at all, so this did not come from the API: the dev
    // server proxy answered because the backend was restarting or unreachable,
    // or something in front of it returned an HTML error page. Reporting the
    // generic "something went wrong" here hid that distinction completely and
    // made a stopped backend indistinguishable from a rejected request.
    throw new ApiError(
      "SYSTEM-001",
      `The server returned an unexpected response (${response.status}). ` +
        "It may be starting up or unreachable — check the backend is running.",
      response.status,
    );
  }

  if (!response.ok) {
    const failure = payload as ErrorEnvelope;
    const error = failure?.error;
    throw new ApiError(
      error?.code ?? "SYSTEM-001",
      error?.message ?? "Something went wrong. Please try again.",
      response.status,
    );
  }

  const success = payload as SuccessEnvelope<T>;
  return { data: success.data, pagination: success.pagination };
}

/**
 * Perform an API request.
 *
 * A 401 triggers exactly one refresh attempt, then the original request is
 * retried. Retrying more than once would loop when the refresh token itself has
 * expired.
 */
export async function requestPaged<T>(
  path: string,
  options: RequestOptions = {},
): Promise<Paged<T>> {
  let response = await send(path, options);

  if (response.status === 401 && !options.anonymous) {
    const refreshed = await refreshSession();
    if (refreshed) {
      response = await send(path, options);
    }
  }

  return unwrap<T>(response);
}

/** Perform an API request and return only its payload. */
export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { data } = await requestPaged<T>(path, options);
  return data;
}
