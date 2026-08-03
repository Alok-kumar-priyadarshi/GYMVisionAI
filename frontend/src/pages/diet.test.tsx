/** The diet page: generating a plan, reading it back, and opening old ones. */

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DietPage from "@/pages/DietPage";
import { tokenStore } from "@/services/api/client";
import { errorResponse, renderWithProviders, successResponse } from "@/test/render";

const PLAN = {
  dietPlanId: "d1",
  goal: "Weight Loss",
  dietPreference: "Vegetarian",
  estimatedCalories: 1850,
  waterTargetMl: 2600,
  status: "Generated",
  mealCount: 2,
  createdAt: "2026-08-01T08:00:00Z",
  meals: [
    {
      mealId: "m1",
      mealType: "Breakfast",
      displayOrder: 1,
      name: "Breakfast",
      targetCalories: 420,
      items: [
        {
          foodId: "f1",
          slug: "rolled_oats",
          name: "Rolled oats",
          category: "Grain",
          servings: 1.5,
          servingSize: "40 g dry",
          calories: 225,
          proteinG: 8.1,
          carbohydratesG: 40.5,
          fatG: 4.2,
        },
      ],
    },
    {
      mealId: "m2",
      mealType: "Lunch",
      displayOrder: 2,
      name: "Lunch",
      targetCalories: 620,
      items: [
        {
          foodId: "f2",
          slug: "lentils",
          name: "Cooked lentils",
          category: "Legume",
          servings: 2,
          servingSize: "100 g",
          calories: 232,
          proteinG: 18,
          carbohydratesG: 40,
          fatG: 0.8,
        },
      ],
    },
  ],
  totals: { calories: 457, proteinG: 26.1, carbohydratesG: 80.5, fatG: 5 },
};

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

describe("the diet page", () => {
  it("shows the stored plan with its meals and portions", async () => {
    mockApi({
      "/diet/current": () => successResponse(PLAN),
      "/diet/history": () => successResponse([]),
    });

    renderWithProviders(<DietPage />);

    expect(await screen.findByText("Breakfast")).toBeInTheDocument();
    expect(screen.getByText("Rolled oats")).toBeInTheDocument();
    expect(screen.getByText("1.5 × 40 g dry")).toBeInTheDocument();
    expect(screen.getByText("Cooked lentils")).toBeInTheDocument();
  });

  it("reports the daily totals", async () => {
    mockApi({
      "/diet/current": () => successResponse(PLAN),
      "/diet/history": () => successResponse([]),
    });

    renderWithProviders(<DietPage />);

    expect(await screen.findByText("457 kcal")).toBeInTheDocument();
    expect(screen.getByText("26.1 g")).toBeInTheDocument();
    expect(screen.getByText("2.6 L")).toBeInTheDocument();
  });

  it("carries the required safety note", async () => {
    // `23_DIET_PLANNING_ENGINE.md` section 10: the target guides food choice
    // and is not medical advice.
    mockApi({
      "/diet/current": () => successResponse(PLAN),
      "/diet/history": () => successResponse([]),
    });

    renderWithProviders(<DietPage />);

    expect(
      await screen.findByText(/not medical or dietary advice/i),
    ).toBeInTheDocument();
  });

  it("offers to build one when the user has none", async () => {
    mockApi({
      "/diet/current": () => errorResponse("DIET-001", 404),
      "/diet/history": () => successResponse([]),
    });

    renderWithProviders(<DietPage />);

    expect(await screen.findByText(/no diet plan yet/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /build my diet plan/i }),
    ).toBeInTheDocument();
  });

  it("sends the chosen dietary preference", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/diet/generate")) {
        return Promise.resolve(
          successResponse({ ...PLAN, dietPreference: "Vegan" }, 201),
        );
      }
      if (url.includes("/diet/history")) return Promise.resolve(successResponse([]));
      return Promise.resolve(errorResponse("DIET-001", 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<DietPage />);

    await screen.findByText(/no diet plan yet/i);
    await userEvent.click(screen.getByRole("button", { name: "Vegan" }));
    await userEvent.click(
      screen.getByRole("button", { name: /build my diet plan/i }),
    );

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("/diet/generate"),
      );
      expect(call).toBeDefined();
      expect(JSON.parse(String(call![1]?.body))).toEqual({
        dietPreference: "Vegan",
      });
    });
  });

  it("lists earlier plans and opens one", async () => {
    const archived = {
      ...PLAN,
      dietPlanId: "d0",
      status: "Archived",
      createdAt: "2026-07-20T08:00:00Z",
      meals: [{ ...PLAN.meals[0], mealId: "m9", mealType: "Porridge day" }],
    };

    mockApi({
      "/diet/history": () =>
        successResponse([
          {
            dietPlanId: "d0",
            goal: "Weight Loss",
            dietPreference: "Vegetarian",
            estimatedCalories: 1700,
            waterTargetMl: 2500,
            status: "Archived",
            mealCount: 1,
            createdAt: "2026-07-20T08:00:00Z",
          },
        ]),
      "/diet/d0": () => successResponse(archived),
      "/diet/current": () => successResponse(PLAN),
    });

    renderWithProviders(<DietPage />);

    expect(await screen.findByText(/earlier plans/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "View" }));

    // The archived plan replaces the current one in the reading area.
    expect(await screen.findByText("Porridge day")).toBeInTheDocument();
  });

  it("does not list the current plan among the earlier ones", async () => {
    mockApi({
      "/diet/current": () => successResponse(PLAN),
      "/diet/history": () =>
        successResponse([
          {
            dietPlanId: "d1",
            goal: "Weight Loss",
            dietPreference: "Vegetarian",
            estimatedCalories: 1850,
            waterTargetMl: 2600,
            status: "Generated",
            mealCount: 2,
            createdAt: "2026-08-01T08:00:00Z",
          },
        ]),
    });

    renderWithProviders(<DietPage />);

    await screen.findByText("Breakfast");
    // History includes the active plan; showing it twice would be confusing.
    expect(screen.queryByText(/earlier plans/i)).not.toBeInTheDocument();
  });
});
