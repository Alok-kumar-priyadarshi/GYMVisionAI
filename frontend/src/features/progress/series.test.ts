import { describe, expect, it } from "vitest";

import { dailySeries, hasData, sessionSeries } from "@/features/progress/series";
import type { SessionSummary } from "@/types/api";

const NOW = new Date("2026-08-02T18:00:00");

function session(overrides: Partial<SessionSummary> = {}): SessionSummary {
  return {
    sessionId: "s1",
    exerciseId: "e1",
    status: "Completed",
    totalReps: 10,
    durationSeconds: 120,
    averageAccuracy: 0.9,
    startedAt: "2026-08-02T17:00:00",
    completedAt: "2026-08-02T17:02:00",
    ...overrides,
  };
}

describe("dailySeries", () => {
  it("returns one entry per day, oldest first", () => {
    const series = dailySeries([], 7, NOW);

    expect(series).toHaveLength(7);
    expect(series[0].date).toBe("2026-07-27");
    expect(series[6].date).toBe("2026-08-02");
  });

  it("includes days with no training as zeroes", () => {
    // Dropping empty days would make a fortnight off look like a fortnight of
    // daily work, which is the opposite of what the chart is for.
    const series = dailySeries([session()], 7, NOW);

    expect(series.filter((point) => point.sessions === 0)).toHaveLength(6);
    expect(series[6].sessions).toBe(1);
  });

  it("adds up several sessions on the same day", () => {
    const series = dailySeries(
      [session(), session({ sessionId: "s2", totalReps: 5 })],
      7,
      NOW,
    );

    expect(series[6].sessions).toBe(2);
    expect(series[6].reps).toBe(15);
    expect(series[6].minutes).toBe(4);
  });

  it("ignores sessions that were never completed", () => {
    const series = dailySeries(
      [session({ status: "Stopped", completedAt: null })],
      7,
      NOW,
    );

    expect(series.every((point) => point.sessions === 0)).toBe(true);
  });

  it("ignores sessions older than the window", () => {
    const series = dailySeries(
      [session({ completedAt: "2026-01-01T10:00:00" })],
      7,
      NOW,
    );

    expect(series.every((point) => point.sessions === 0)).toBe(true);
  });

  it("keeps days in local time across a month boundary", () => {
    const series = dailySeries([], 3, new Date("2026-03-01T09:00:00"));

    expect(series.map((point) => point.date)).toEqual([
      "2026-02-27",
      "2026-02-28",
      "2026-03-01",
    ]);
  });

  it("survives an unparseable timestamp", () => {
    const series = dailySeries([session({ completedAt: "nonsense" })], 7, NOW);

    expect(series.every((point) => point.sessions === 0)).toBe(true);
  });
});

describe("sessionSeries", () => {
  it("orders oldest first, opposite to the history endpoint", () => {
    // History arrives newest first; a chart reads left to right.
    const points = sessionSeries(
      [
        session({ sessionId: "newest", totalReps: 3 }),
        session({ sessionId: "oldest", totalReps: 1 }),
      ],
      10,
    );

    expect(points.map((point) => point.sessionId)).toEqual(["oldest", "newest"]);
  });

  it("takes the most recent sessions, not the first ones it sees", () => {
    const many = Array.from({ length: 30 }, (_, index) =>
      session({ sessionId: `s${index}`, totalReps: index }),
    );

    const points = sessionSeries(many, 5);

    expect(points).toHaveLength(5);
    expect(points.at(-1)?.sessionId).toBe("s0");
  });

  it("excludes sessions that were never completed", () => {
    const points = sessionSeries(
      [session({ status: "Stopped", completedAt: null }), session()],
      10,
    );

    expect(points).toHaveLength(1);
  });
});

describe("hasData", () => {
  it("is false when nothing was ever counted", () => {
    // A plan of only held exercises records no repetitions, and a flat line at
    // zero says nothing worth the space.
    expect(hasData([{ reps: 0 }, { reps: 0 }])).toBe(false);
  });

  it("is true once anything was counted", () => {
    expect(hasData([{ reps: 0 }, { reps: 4 }])).toBe(true);
  });
});
