/** Tests for the API client: envelopes, errors, auth headers and refresh. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  NetworkError,
  request,
  requestPaged,
  tokenStore,
} from "@/services/api/client";
import { errorResponse, successResponse } from "@/test/render";

describe("the API client", () => {
  beforeEach(() => {
    tokenStore.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    tokenStore.clear();
  });

  it("unwraps the data field from a success envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(successResponse({ name: "Push-ups" })),
    );

    await expect(request("/exercises/push_ups")).resolves.toEqual({
      name: "Push-ups",
    });
  });

  it("returns pagination when the endpoint supplies it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: true,
            message: "ok",
            data: [],
            pagination: { page: 1, limit: 10, total: 30, pages: 3 },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    const result = await requestPaged("/workouts/history");

    expect(result.pagination?.pages).toBe(3);
  });

  it("raises the backend's documented error code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        errorResponse("EXERCISE-001", 404, "Exercise not found."),
      ),
    );

    await expect(request("/exercises/nope")).rejects.toMatchObject({
      code: "EXERCISE-001",
      status: 404,
      message: "Exercise not found.",
    });
  });

  it("attaches the access token when one is stored", async () => {
    tokenStore.save("stored-token");
    const fetchMock = vi.fn().mockResolvedValue(successResponse({}));
    vi.stubGlobal("fetch", fetchMock);

    await request("/auth/me");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer stored-token");
  });

  it("omits the token for anonymous requests", async () => {
    tokenStore.save("stored-token");
    const fetchMock = vi.fn().mockResolvedValue(successResponse({}));
    vi.stubGlobal("fetch", fetchMock);

    await request("/auth/google", { anonymous: true, method: "POST", body: {} });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.Authorization).toBeUndefined();
  });

  it("refreshes an expired token once and retries the request", async () => {
    tokenStore.save("expired-token", "refresh-token");

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(errorResponse("AUTH-003", 401))
      .mockResolvedValueOnce(successResponse({ accessToken: "fresh-token" }))
      .mockResolvedValueOnce(successResponse({ name: "Alice" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/auth/me")).resolves.toEqual({ name: "Alice" });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(tokenStore.access()).toBe("fresh-token");
  });

  it("gives up and clears the session when the refresh token is rejected", async () => {
    tokenStore.save("expired-token", "stale-refresh");

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(errorResponse("AUTH-003", 401))
      .mockResolvedValueOnce(errorResponse("AUTH-002", 401));
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/auth/me")).rejects.toBeInstanceOf(ApiError);

    // Two calls only: the original and the refresh. No retry loop.
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(tokenStore.access()).toBeNull();
  });

  it("does not attempt a refresh without a refresh token", async () => {
    tokenStore.save("expired-token");
    const fetchMock = vi.fn().mockResolvedValue(errorResponse("AUTH-003", 401));
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/auth/me")).rejects.toBeInstanceOf(ApiError);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("reports a network failure separately from an API error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await expect(request("/auth/me")).rejects.toBeInstanceOf(NetworkError);
  });

  it("survives a response that is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>502</html>", { status: 502 })),
    );

    await expect(request("/auth/me")).rejects.toMatchObject({
      code: "SYSTEM-001",
    });
  });

  it("builds a query string from the supplied parameters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(successResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await request("/workouts/history", { query: { page: 2, limit: 10 } });

    expect(fetchMock.mock.calls[0][0]).toContain("page=2&limit=10");
  });

  it("omits undefined query parameters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(successResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await request("/exercises/start", { query: { workoutId: undefined } });

    expect(fetchMock.mock.calls[0][0]).not.toContain("workoutId");
  });

  it("recognises an authentication failure", () => {
    expect(new ApiError("AUTH-002", "bad", 401).isAuthError).toBe(true);
    expect(new ApiError("EXERCISE-001", "gone", 404).isAuthError).toBe(false);
  });

  it("says the server is unreachable when the response is not JSON", async () => {
    // A stopped or restarting backend makes the dev proxy answer with HTML.
    // Reporting a generic "something went wrong" made that indistinguishable
    // from a rejected request, which is the one case a user can act on.
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response("<!doctype html><title>proxy error</title>", {
            status: 500,
            headers: { "Content-Type": "text/html" },
          }),
        ),
      ),
    );

    await expect(request("/auth/me")).rejects.toThrow(
      /unexpected response \(500\)/i,
    );
  });

  it("keeps the backend's own message for a real API error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          errorResponse("AUTH-004", 401, "Google authentication failed."),
        ),
      ),
    );

    await expect(request("/auth/google")).rejects.toMatchObject({
      code: "AUTH-004",
      message: "Google authentication failed.",
    });
  });
});
