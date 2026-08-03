/**
 * Building the workout tab list.
 *
 * Kept apart from the component so it can be tested directly, and so the module
 * holding the component exports only components.
 */

import type { WorkoutSummary } from "@/types/api";

export interface WorkoutTab {
  workoutId: string;
  label: string;
  /** Shown under the label, to tell plans with the same name apart. */
  detail: string;
  isCurrent: boolean;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
  });
}

/**
 * Build the tab list from the current plan and the user's history.
 *
 * The current plan is pinned first and removed from the rest, so it never
 * appears twice — history includes it.
 */
export function buildTabs(
  current: WorkoutSummary | null,
  history: readonly WorkoutSummary[],
): WorkoutTab[] {
  const tabs: WorkoutTab[] = [];

  if (current) {
    tabs.push({
      workoutId: current.workoutId,
      label: current.name,
      detail: "Current",
      isCurrent: true,
    });
  }

  // Guarded rather than trusted: the page is worth showing even if the history
  // request returned something unexpected.
  for (const plan of Array.isArray(history) ? history : []) {
    if (current && plan.workoutId === current.workoutId) continue;
    tabs.push({
      workoutId: plan.workoutId,
      label: plan.name,
      detail: formatDate(plan.createdAt),
      isCurrent: false,
    });
  }

  return tabs;
}
