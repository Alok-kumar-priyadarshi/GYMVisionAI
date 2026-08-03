/** Page-level tests: loading, error, empty and populated states. */

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ExercisesPage from "@/pages/ExercisesPage";
import ProfilePage from "@/pages/ProfilePage";
import CoachPage from "@/pages/CoachPage";
import { tokenStore } from "@/services/api/client";
import { errorResponse, renderWithProviders, successResponse } from "@/test/render";

const EXERCISES = [
  {
    exerciseId: "push_ups",
    name: "Push-ups",
    category: "Upper Body",
    difficulty: "Intermediate",
    exerciseType: "Repetition",
    detectorAvailable: true,
  },
  {
    exerciseId: "plank",
    name: "Plank",
    category: "Core",
    difficulty: "Beginner",
    exerciseType: "Duration",
    detectorAvailable: true,
  },
];

/** Route requests to scripted responses, so no test depends on call order. */
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

beforeEach(() => {
  tokenStore.clear();
  vi.restoreAllMocks();
});

describe("the exercise library", () => {
  it("lists every exercise", async () => {
    mockApi({ "/exercises": () => successResponse(EXERCISES) });

    renderWithProviders(<ExercisesPage />);

    expect(await screen.findByText("Push-ups")).toBeInTheDocument();
    expect(screen.getByText("Plank")).toBeInTheDocument();
  });

  it("filters by search term", async () => {
    mockApi({ "/exercises": () => successResponse(EXERCISES) });
    const user = userEvent.setup();

    renderWithProviders(<ExercisesPage />);
    await screen.findByText("Push-ups");

    await user.type(screen.getByLabelText(/search/i), "plank");

    expect(screen.queryByText("Push-ups")).not.toBeInTheDocument();
    expect(screen.getByText("Plank")).toBeInTheDocument();
  });

  it("filters by category", async () => {
    mockApi({ "/exercises": () => successResponse(EXERCISES) });
    const user = userEvent.setup();

    renderWithProviders(<ExercisesPage />);
    await screen.findByText("Push-ups");

    await user.click(screen.getByRole("button", { name: "Core" }));

    expect(screen.queryByText("Push-ups")).not.toBeInTheDocument();
    expect(screen.getByText("Plank")).toBeInTheDocument();
  });

  it("explains when nothing matches", async () => {
    mockApi({ "/exercises": () => successResponse(EXERCISES) });
    const user = userEvent.setup();

    renderWithProviders(<ExercisesPage />);
    await screen.findByText("Push-ups");

    await user.type(screen.getByLabelText(/search/i), "deadlift");

    expect(screen.getByText(/no exercises match/i)).toBeInTheDocument();
  });
});

describe("the profile form", () => {
  it("shows an empty form when no profile exists", async () => {
    mockApi({ "/users/profile": () => errorResponse("USER-002", 404) });

    renderWithProviders(<ProfilePage />);

    expect(
      await screen.findByRole("button", { name: /create profile/i }),
    ).toBeInTheDocument();
  });

  it("rejects an implausible age before calling the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue(errorResponse("USER-002", 404));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderWithProviders(<ProfilePage />);
    await screen.findByRole("button", { name: /create profile/i });

    await user.type(screen.getByLabelText(/^age$/i), "5");
    await user.type(screen.getByLabelText(/height/i), "170");
    await user.type(screen.getByLabelText(/weight/i), "70");
    await user.click(screen.getByRole("button", { name: /create profile/i }));

    expect(await screen.findByText(/between 13 and 100/i)).toBeInTheDocument();
    // Only the initial GET happened; nothing was submitted.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("saves a valid profile", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(errorResponse("USER-002", 404))
      .mockResolvedValue(
        successResponse({
          id: "p1",
          age: 30,
          gender: "Male",
          heightCm: 178,
          weightKg: 78,
          fitnessGoal: "General Fitness",
          fitnessLevel: "Beginner",
          problemAreas: [],
          workoutDurationMinutes: 30,
          bodyType: null,
          bmi: 24.6,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderWithProviders(<ProfilePage />);
    await screen.findByRole("button", { name: /create profile/i });

    await user.type(screen.getByLabelText(/^age$/i), "30");
    await user.type(screen.getByLabelText(/height/i), "178");
    await user.type(screen.getByLabelText(/weight/i), "78");
    await user.click(screen.getByRole("button", { name: /create profile/i }));

    expect(await screen.findByRole("status")).toHaveTextContent(/profile saved/i);
  });
});

describe("the coach", () => {
  it("shows the user's message and the reply", async () => {
    mockApi({
      "/ai/chat": () =>
        successResponse({
          conversationId: "c1",
          response: "Keep your core braced throughout the movement.",
          createdAt: "2026-08-02T10:00:00Z",
        }),
    });
    const user = userEvent.setup();

    renderWithProviders(<CoachPage />);

    await user.type(screen.getByLabelText(/message/i), "How do I do push-ups?");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(screen.getByText("How do I do push-ups?")).toBeInTheDocument();
    expect(
      await screen.findByText(/keep your core braced/i),
    ).toBeInTheDocument();
  });

  it("reports when the coach is unavailable", async () => {
    mockApi({
      "/ai/chat": () =>
        errorResponse("AI-001", 503, "The AI assistant is temporarily unavailable."),
    });
    const user = userEvent.setup();

    renderWithProviders(<CoachPage />);

    await user.type(screen.getByLabelText(/message/i), "Hello");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable/i);
  });

  it("will not send an empty message", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<CoachPage />);

    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
    await waitFor(() => expect(fetchMock).not.toHaveBeenCalled());
  });
});
