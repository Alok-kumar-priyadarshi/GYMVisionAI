/** The workout page, and the completed marks it derives from session history. */

import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import WorkoutPage from "@/pages/WorkoutPage";
import { tokenStore } from "@/services/api/client";
import { errorResponse, renderWithProviders, successResponse } from "@/test/render";

const WORKOUT = {
  workoutId: "w1",
  name: "Full Body Balance",
  difficulty: "Beginner",
  goal: "General Fitness",
  estimatedDurationMinutes: 19,
  exerciseCount: 3,
  createdAt: "2026-08-01T10:00:00Z",
  exercises: [
    {
      exerciseId: "ex-jumping-jacks",
      slug: "jumping_jacks",
      name: "Jumping Jacks",
      displayOrder: 1,
      sets: 2,
      repetitions: 12,
      holdSeconds: 0,
      restSeconds: 45,
    },
    {
      exerciseId: "ex-squats",
      slug: "bodyweight_squats",
      name: "Bodyweight Squats",
      displayOrder: 2,
      sets: 2,
      repetitions: 12,
      holdSeconds: 0,
      restSeconds: 45,
    },
    {
      exerciseId: "ex-plank",
      slug: "plank",
      name: "Plank",
      displayOrder: 3,
      sets: 2,
      repetitions: 0,
      holdSeconds: 20,
      restSeconds: 45,
    },
  ],
};

/** Timestamps are relative so the tests do not depend on the calendar. */
function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
}

function completedSession(exerciseId: string, at = new Date().toISOString()) {
  return {
    sessionId: `s-${exerciseId}`,
    exerciseId,
    status: "Completed",
    totalReps: 12,
    durationSeconds: 60,
    averageAccuracy: 0.9,
    startedAt: at,
    completedAt: at,
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

/** The list item for one exercise, so assertions cannot match a sibling row. */
function row(name: string): HTMLElement {
  return screen.getByText(name).closest("li") as HTMLElement;
}

beforeEach(() => {
  tokenStore.clear();
  vi.restoreAllMocks();
});

describe("the workout page", () => {
  it("marks an exercise completed today", async () => {
    mockApi({
      "/workouts/current": () => successResponse(WORKOUT),
      "/exercises/history": () =>
        successResponse([completedSession("ex-jumping-jacks")]),
    });

    renderWithProviders(<WorkoutPage />);

    await screen.findByText("Jumping Jacks");

    const done = within(row("Jumping Jacks"));
    expect(done.getByText("Done")).toBeInTheDocument();
    expect(done.getByRole("button", { name: /do it again/i })).toBeInTheDocument();

    // An exercise not yet done keeps its ordinary call to action.
    const pending = within(row("Plank"));
    expect(pending.queryByText("Done")).not.toBeInTheDocument();
    expect(pending.getByRole("button", { name: "Start" })).toBeInTheDocument();
  });

  it("counts progress across the plan", async () => {
    mockApi({
      "/workouts/current": () => successResponse(WORKOUT),
      "/exercises/history": () =>
        successResponse([
          completedSession("ex-jumping-jacks"),
          completedSession("ex-squats"),
        ]),
    });

    renderWithProviders(<WorkoutPage />);

    expect(await screen.findByText("2 of 3 done today")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2");
  });

  it("announces a finished workout", async () => {
    mockApi({
      "/workouts/current": () => successResponse(WORKOUT),
      "/exercises/history": () =>
        successResponse(
          WORKOUT.exercises.map((item) => completedSession(item.exerciseId)),
        ),
    });

    renderWithProviders(<WorkoutPage />);

    expect(
      await screen.findByText("Workout complete for today"),
    ).toBeInTheDocument();
  });

  it("does not carry yesterday's work into today", async () => {
    mockApi({
      "/workouts/current": () => successResponse(WORKOUT),
      "/exercises/history": () =>
        successResponse([completedSession("ex-jumping-jacks", hoursAgo(30))]),
    });

    renderWithProviders(<WorkoutPage />);

    expect(await screen.findByText("0 of 3 done today")).toBeInTheDocument();
    expect(screen.queryByText("Done")).not.toBeInTheDocument();
  });

  it("ignores an exercise done outside this plan", async () => {
    mockApi({
      "/workouts/current": () => successResponse(WORKOUT),
      "/exercises/history": () =>
        successResponse([
          completedSession("ex-jumping-jacks"),
          completedSession("ex-not-in-this-plan"),
        ]),
    });

    renderWithProviders(<WorkoutPage />);

    // Counting the raw history would read "2 of 3" and overfill the bar.
    expect(await screen.findByText("1 of 3 done today")).toBeInTheDocument();
  });

  it("still shows the plan when history cannot be loaded", async () => {
    mockApi({
      "/workouts/current": () => successResponse(WORKOUT),
      "/exercises/history": () => errorResponse("SYSTEM-001", 500),
    });

    renderWithProviders(<WorkoutPage />);

    // The workout is the point of the page; marks are an enhancement.
    expect(await screen.findByText("Jumping Jacks")).toBeInTheDocument();
    expect(screen.getByText("0 of 3 done today")).toBeInTheDocument();
  });

  it("requests no more history than the endpoint allows", async () => {
    // The endpoint caps `limit` at 100 and rejects anything larger as a
    // validation error rather than clamping it. Asking for 200 on the progress
    // page made its session list and both charts fail silently.
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/exercises/history")) {
        const limit = Number(new URL(url, "http://x").searchParams.get("limit"));
        expect(limit).toBeLessThanOrEqual(100);
        return Promise.resolve(successResponse([]));
      }
      if (url.includes("/workouts/history")) {
        return Promise.resolve(successResponse([]));
      }
      return Promise.resolve(successResponse(WORKOUT));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<WorkoutPage />);

    await screen.findByText("Jumping Jacks");
  });

  it("explains that an unchanged profile yields the same plan", async () => {
    // Generation is deterministic, so regenerating without changing the profile
    // returns the existing plan. Saying nothing made the button look broken.
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/workouts/generate")) {
        return Promise.resolve(successResponse({ ...WORKOUT, unchanged: true }));
      }
      if (url.includes("/exercises/history")) {
        return Promise.resolve(successResponse([]));
      }
      return Promise.resolve(successResponse(WORKOUT));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<WorkoutPage />);
    await screen.findByText("Jumping Jacks");

    await userEvent.click(
      screen.getByRole("button", { name: /generate a new one/i }),
    );

    expect(
      await screen.findByText(/already the plan for your profile/i),
    ).toBeInTheDocument();
  });

  it("reports a generation failure instead of doing nothing visible", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/workouts/generate")) {
        return Promise.resolve(
          errorResponse("WORKOUT-002", 500, "Workout generation failed."),
        );
      }
      if (url.includes("/exercises/history")) {
        return Promise.resolve(successResponse([]));
      }
      return Promise.resolve(successResponse(WORKOUT));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<WorkoutPage />);
    await screen.findByText("Jumping Jacks");

    await userEvent.click(
      screen.getByRole("button", { name: /generate a new one/i }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /workout generation failed/i,
    );
  });

  it("offers to generate a plan when there is none", async () => {
    mockApi({
      "/workouts/current": () => errorResponse("WORKOUT-001", 404),
      "/exercises/history": () => successResponse([]),
    });

    renderWithProviders(<WorkoutPage />);

    expect(await screen.findByText(/no workout yet/i)).toBeInTheDocument();
  });

  it("shows the new plan after generating a different one", async () => {
    // The plan on screen must follow the one just generated, or a profile
    // change looks as though it had no effect at all.
    const REPLACEMENT = {
      ...WORKOUT,
      workoutId: "w2",
      name: "Fat Burn Circuit",
      exercises: [{ ...WORKOUT.exercises[0], name: "Burpees" }],
    };
    let generated = false;

    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/workouts/generate")) {
          generated = true;
          return Promise.resolve(successResponse(REPLACEMENT));
        }
        if (url.includes("/exercises/history")) {
          return Promise.resolve(successResponse([]));
        }
        if (url.includes("/workouts/history")) {
          return Promise.resolve(successResponse([]));
        }
        return Promise.resolve(
          successResponse(generated ? REPLACEMENT : WORKOUT),
        );
      }),
    );

    renderWithProviders(<WorkoutPage />);
    await screen.findByText("Full Body Balance");

    await userEvent.click(
      screen.getByRole("button", { name: /generate a new one/i }),
    );

    expect(await screen.findByText("Fat Burn Circuit")).toBeInTheDocument();
    expect(screen.getByText("Burpees")).toBeInTheDocument();
    expect(screen.queryByText("Full Body Balance")).not.toBeInTheDocument();
  });

  const EARLIER = [
    {
      workoutId: "w1",
      name: "Full Body Balance",
      difficulty: "Beginner",
      goal: "General Fitness",
      estimatedDurationMinutes: 19,
      exerciseCount: 3,
      createdAt: "2026-08-03T10:00:00Z",
    },
    {
      workoutId: "w0",
      name: "Fat Burn Circuit",
      difficulty: "Beginner",
      goal: "Weight Loss",
      estimatedDurationMinutes: 22,
      exerciseCount: 1,
      createdAt: "2026-07-30T10:00:00Z",
    },
  ];

  const OLD_PLAN = {
    ...EARLIER[1],
    exercises: [{ ...WORKOUT.exercises[0], name: "Burpees" }],
  };

  function withTabs() {
    mockApi({
      "/workouts/current": () => successResponse(WORKOUT),
      "/workouts/history": () => successResponse(EARLIER),
      "/workouts/w0": () => successResponse(OLD_PLAN),
      "/exercises/history": () => successResponse([]),
    });
  }

  it("offers a tab for each workout, current first", async () => {
    withTabs();

    renderWithProviders(<WorkoutPage />);

    const tabs = await screen.findAllByRole("tab");
    expect(tabs).toHaveLength(2);
    expect(tabs[0]).toHaveTextContent("Full Body Balance");
    expect(tabs[0]).toHaveTextContent("Current");
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
    expect(tabs[1]).toHaveTextContent("Fat Burn Circuit");
  });

  it("opens an earlier plan when its tab is chosen", async () => {
    withTabs();

    renderWithProviders(<WorkoutPage />);
    await screen.findAllByRole("tab");

    await userEvent.click(screen.getByRole("tab", { name: /fat burn circuit/i }));

    expect(await screen.findByText("Burpees")).toBeInTheDocument();
    // Marked so an old plan is not mistaken for the one to train today.
    expect(screen.getByText("Earlier plan")).toBeInTheDocument();
  });

  it("moves between tabs with the arrow keys", async () => {
    // Tabs are expected to be operable from the keyboard, not only by pointer.
    withTabs();

    renderWithProviders(<WorkoutPage />);
    const tabs = await screen.findAllByRole("tab");

    tabs[0].focus();
    await userEvent.keyboard("{ArrowRight}");

    expect(
      screen.getByRole("tab", { name: /fat burn circuit/i }),
    ).toHaveAttribute("aria-selected", "true");
  });

  it("shows no tab strip when there is only one plan", async () => {
    mockApi({
      "/workouts/current": () => successResponse(WORKOUT),
      "/workouts/history": () => successResponse([EARLIER[0]]),
      "/exercises/history": () => successResponse([]),
    });

    renderWithProviders(<WorkoutPage />);
    await screen.findByText("Jumping Jacks");

    // One plan is not a choice.
    expect(screen.queryAllByRole("tab")).toHaveLength(0);
  });

  it("returns to the current plan after generating", async () => {
    mockApi({
      "/workouts/generate": () => successResponse(WORKOUT),
      "/workouts/current": () => successResponse(WORKOUT),
      "/workouts/history": () => successResponse(EARLIER),
      "/workouts/w0": () => successResponse(OLD_PLAN),
      "/exercises/history": () => successResponse([]),
    });

    renderWithProviders(<WorkoutPage />);
    await screen.findAllByRole("tab");

    await userEvent.click(screen.getByRole("tab", { name: /fat burn circuit/i }));
    await screen.findByText("Burpees");

    await userEvent.click(
      screen.getByRole("button", { name: /generate a new one/i }),
    );

    // The plan that just changed is the current one, so that is what to show.
    expect(await screen.findByText("Jumping Jacks")).toBeInTheDocument();
    expect(screen.queryByText("Earlier plan")).not.toBeInTheDocument();
  });
});
