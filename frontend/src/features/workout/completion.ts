/**
 * Which of a workout's exercises the user has already done.
 *
 * A workout plan is a repeatable template, not a one-off checklist: the same
 * plan is worked through again tomorrow. So "completed" is scoped to the
 * current day, and is derived from recorded sessions rather than held in the
 * page. Deriving it means the marks survive a refresh, appear on any device,
 * and can never disagree with what Progress reports.
 */

import type { SessionSummary } from "@/types/api";

/** `SessionStatus.COMPLETED` in `app/domain/value_objects/enums.py`. */
const COMPLETED = "Completed";

/**
 * Compare calendar days in the viewer's own timezone.
 *
 * Sessions are stored in UTC. Comparing the UTC dates would move the boundary
 * away from the user's midnight, so a late evening workout could show as
 * belonging to tomorrow.
 */
function isSameLocalDay(left: Date, right: Date): boolean {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  );
}

/**
 * Identifiers of the exercises finished today.
 *
 * Abandoned sessions do not count: only a session the backend marked
 * `Completed` means the work was actually done.
 */
export function exercisesCompletedToday(
  sessions: readonly SessionSummary[],
  now: Date = new Date(),
): ReadonlySet<string> {
  const finished = new Set<string>();

  for (const session of sessions) {
    if (session.status !== COMPLETED) continue;

    // `completedAt` is when the effort ended, which is the honest timestamp for
    // a session that ran across midnight. It is nullable in the contract, so
    // the start time is the fallback.
    const when = new Date(session.completedAt ?? session.startedAt);
    if (Number.isNaN(when.getTime())) continue;

    if (isSameLocalDay(when, now)) finished.add(session.exerciseId);
  }

  return finished;
}
