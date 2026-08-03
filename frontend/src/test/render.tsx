/**
 * Test helpers.
 *
 * Renders a component inside the same providers the application uses, so tests
 * exercise real routing, real query behaviour and the real auth context.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactElement, ReactNode } from "react";

import { AuthProvider } from "@/contexts/AuthContext";

/** A client that never retries, so a failing test fails immediately. */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface Options extends Omit<RenderOptions, "wrapper"> {
  route?: string;
  queryClient?: QueryClient;
}

export function renderWithProviders(ui: ReactElement, options: Options = {}) {
  const { route = "/", queryClient = createTestQueryClient(), ...rest } = options;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <AuthProvider>{children}</AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  return { queryClient, ...render(ui, { wrapper: Wrapper, ...rest }) };
}

/** Build a success envelope, matching COMMON-002. */
export function successResponse(data: unknown, status = 200): Response {
  return new Response(
    JSON.stringify({ success: true, message: "ok", data }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

/** Build an error envelope, matching COMMON-001. */
export function errorResponse(code: string, status: number, message = "failed"): Response {
  return new Response(
    JSON.stringify({ success: false, error: { code, message } }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}
