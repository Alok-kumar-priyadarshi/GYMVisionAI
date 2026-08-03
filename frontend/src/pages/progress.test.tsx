/** The progress page and its charts. */

import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProgressPage from "@/pages/ProgressPage";
import { tokenStore } from "@/services/api/client";
import { errorResponse, renderWithProviders, successResponse } from "@/test/render";

const PROGRESS = {
  currentStreak: 3,
  longestStreak: 7,
  totalWorkouts: 12,
  totalExercises: 60,
  totalMinutes: 340,
  averageWorkoutMinutes: 28.3,
  lastWorkoutDate: "2026-08-01",
};

const STATISTICS = {
  totalWorkouts: 12,
  totalExercises: 60,
  totalMinutes: 340,
  averageWorkoutMinutes: 28.3,
  completedSessions: 40,
  totalReps: 620,
};

function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
}

function session(overrides: Record<string, unknown> = {}) {
  const at = hoursAgo(2);
  return {
    sessionId: "s1",
    exerciseId: "e1",
    status: "Completed",
    totalReps: 12,
    durationSeconds: 300,
    averageAccuracy: 0.92,
    startedAt: at,
    completedAt: at,
    ...overrides,
  };
}

function mockApi(routes: Record<string, () => Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const match = Object.keys(routes).find((path) => url.includes(path));
      if (!match) return Promise.resolve(errorResponse("SYSTEM-001", 500));
      return Promise.resolve(routes[match]());
    }),
  );
}

function withHistory(history: unknown[]) {
  mockApi({
    "/progress/statistics": () => successResponse(STATISTICS),
    "/exercises/history": () => successResponse(history),
    "/progress": () => successResponse(PROGRESS),
  });
}

beforeEach(() => {
  tokenStore.clear();
  vi.restoreAllMocks();
});

describe("the progress page", () => {
  it("charts training once there is history", async () => {
    withHistory([session()]);

    renderWithProviders(<ProgressPage />);

    expect(await screen.findByText("Daily training")).toBeInTheDocument();
    expect(screen.getByText("Repetitions per session")).toBeInTheDocument();
  });

  it("exposes the chart data as a table for screen readers", async () => {
    // The drawing is hidden from assistive technology, so the numbers behind it
    // have to be reachable some other way.
    withHistory([session()]);

    renderWithProviders(<ProgressPage />);

    expect(
      await screen.findByRole("table", { name: /minutes trained each day/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("table", { name: /repetitions in each session/i }),
    ).toBeInTheDocument();
  });

  it("hides the repetition chart when nothing was counted", async () => {
    // A plan of only held exercises records no reps; a flat line at zero says
    // nothing worth the space.
    withHistory([session({ totalReps: 0 })]);

    renderWithProviders(<ProgressPage />);

    expect(await screen.findByText("Daily training")).toBeInTheDocument();
    expect(screen.queryByText("Repetitions per session")).not.toBeInTheDocument();
  });

  it("draws no charts before there is any history", async () => {
    withHistory([]);

    renderWithProviders(<ProgressPage />);

    expect(await screen.findByText(/no sessions yet/i)).toBeInTheDocument();
    expect(screen.queryByText("Daily training")).not.toBeInTheDocument();
  });

  it("still shows the totals when history fails to load", async () => {
    mockApi({
      "/progress/statistics": () => successResponse(STATISTICS),
      "/exercises/history": () => errorResponse("SYSTEM-001", 500),
      "/progress": () => successResponse(PROGRESS),
    });

    renderWithProviders(<ProgressPage />);

    // The streak tiles do not depend on history, so they must survive it.
    expect(await screen.findByText("Current streak")).toBeInTheDocument();
    expect(screen.queryByText("Daily training")).not.toBeInTheDocument();
  });
});
