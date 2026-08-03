import { describe, expect, it } from "vitest";

import { buildTabs } from "@/features/workout/tabs";
import type { WorkoutSummary } from "@/types/api";

function plan(overrides: Partial<WorkoutSummary> = {}): WorkoutSummary {
  return {
    workoutId: "w1",
    name: "Full Body Balance",
    difficulty: "Beginner",
    goal: "General Fitness",
    estimatedDurationMinutes: 19,
    exerciseCount: 7,
    createdAt: "2026-08-03T10:00:00Z",
    ...overrides,
  };
}

describe("buildTabs", () => {
  it("puts the current plan first and labels it", () => {
    const tabs = buildTabs(plan(), [plan({ workoutId: "w0" })]);

    expect(tabs[0].workoutId).toBe("w1");
    expect(tabs[0].detail).toBe("Current");
    expect(tabs[0].isCurrent).toBe(true);
  });

  it("does not list the current plan twice", () => {
    // History includes the current plan, so it has to be filtered out.
    const tabs = buildTabs(plan(), [plan(), plan({ workoutId: "w0" })]);

    expect(tabs.map((tab) => tab.workoutId)).toEqual(["w1", "w0"]);
  });

  it("dates earlier plans so identical names can be told apart", () => {
    // Regenerating an unchanged profile produces the same name every time.
    const tabs = buildTabs(
      plan(),
      [plan({ workoutId: "w0", createdAt: "2026-07-30T10:00:00Z" })],
    );

    expect(tabs[1].detail).not.toBe("Current");
    expect(tabs[1].detail).toMatch(/\d/);
  });

  it("returns a single tab when there is no history", () => {
    expect(buildTabs(plan(), [])).toHaveLength(1);
  });

  it("returns nothing when there is no plan at all", () => {
    expect(buildTabs(null, [])).toEqual([]);
  });

  it("survives a history payload that is not a list", () => {
    // The page is worth showing even if that request answered unexpectedly.
    const tabs = buildTabs(plan(), undefined as never);

    expect(tabs).toHaveLength(1);
  });
});
