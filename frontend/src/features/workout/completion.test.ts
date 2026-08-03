import { describe, expect, it } from "vitest";

import { exercisesCompletedToday } from "@/features/workout/completion";
import type { SessionSummary } from "@/types/api";

const NOW = new Date("2026-08-02T18:00:00");

function session(overrides: Partial<SessionSummary> = {}): SessionSummary {
  return {
    sessionId: "session-1",
    exerciseId: "exercise-1",
    status: "Completed",
    totalReps: 12,
    durationSeconds: 60,
    averageAccuracy: 0.9,
    startedAt: "2026-08-02T17:00:00",
    completedAt: "2026-08-02T17:01:00",
    ...overrides,
  };
}

describe("exercisesCompletedToday", () => {
  it("marks an exercise finished today", () => {
    const done = exercisesCompletedToday([session()], NOW);

    expect(done.has("exercise-1")).toBe(true);
  });

  it("ignores a session that was never completed", () => {
    // Starting an exercise and walking away is not doing it.
    const done = exercisesCompletedToday(
      [session({ status: "Stopped", completedAt: null })],
      NOW,
    );

    expect(done.size).toBe(0);
  });

  it("ignores a session from an earlier day", () => {
    // The plan is repeatable, so yesterday's work must not tick off today.
    const done = exercisesCompletedToday(
      [
        session({
          startedAt: "2026-08-01T17:00:00",
          completedAt: "2026-08-01T17:01:00",
        }),
      ],
      NOW,
    );

    expect(done.size).toBe(0);
  });

  it("counts a session by when it ended, not when it began", () => {
    // Started before midnight, finished after: it belongs to the new day.
    const done = exercisesCompletedToday(
      [
        session({
          startedAt: "2026-08-01T23:58:00",
          completedAt: "2026-08-02T00:03:00",
        }),
      ],
      NOW,
    );

    expect(done.has("exercise-1")).toBe(true);
  });

  it("falls back to the start time when the end time is absent", () => {
    const done = exercisesCompletedToday(
      [session({ completedAt: null })],
      NOW,
    );

    expect(done.has("exercise-1")).toBe(true);
  });

  it("collapses repeated sessions of one exercise into a single mark", () => {
    const done = exercisesCompletedToday(
      [session(), session({ sessionId: "session-2" })],
      NOW,
    );

    expect(done.size).toBe(1);
  });

  it("survives an unparseable timestamp", () => {
    const done = exercisesCompletedToday(
      [session({ completedAt: "not a date" })],
      NOW,
    );

    expect(done.size).toBe(0);
  });

  it("returns nothing for an empty history", () => {
    expect(exercisesCompletedToday([], NOW).size).toBe(0);
  });
});
