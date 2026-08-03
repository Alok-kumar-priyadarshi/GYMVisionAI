/**
 * Turning session history into something a chart can draw.
 *
 * The progress endpoints report totals, not a time series, so the shape of
 * someone's training over time has to be derived from their sessions. These are
 * pure functions with the date passed in, so the behaviour around month ends
 * and daylight-saving changes can actually be tested.
 */

import type { SessionSummary } from "@/types/api";

/** `SessionStatus.COMPLETED` in `app/domain/value_objects/enums.py`. */
const COMPLETED = "Completed";

export interface DayPoint {
  /** Local calendar day, as `YYYY-MM-DD`. */
  date: string;
  /** Short label for the axis. */
  label: string;
  sessions: number;
  reps: number;
  minutes: number;
}

export interface SessionPoint {
  sessionId: string;
  /** Position in time, oldest first. */
  label: string;
  reps: number;
  minutes: number;
}

function startOfLocalDay(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function isoDay(value: Date): string {
  // Built from local parts rather than `toISOString`, which would convert to
  // UTC and shift the day for anyone east or west of Greenwich.
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${value.getFullYear()}-${month}-${day}`;
}

/** When a session's effort should be attributed to. */
function endedAt(session: SessionSummary): Date {
  return new Date(session.completedAt ?? session.startedAt);
}

function isUsable(session: SessionSummary): boolean {
  if (session.status !== COMPLETED) return false;
  return !Number.isNaN(endedAt(session).getTime());
}

/**
 * One entry per day for the last `days` days, oldest first.
 *
 * Days with no training are included as zeroes. Omitting them would draw a
 * chart where a fortnight off looks identical to a fortnight of daily work,
 * which is the opposite of what a progress chart is for.
 */
export function dailySeries(
  sessions: readonly SessionSummary[],
  days: number,
  now: Date = new Date(),
): DayPoint[] {
  const today = startOfLocalDay(now);
  const points = new Map<string, DayPoint>();

  for (let offset = days - 1; offset >= 0; offset -= 1) {
    const date = new Date(today);
    date.setDate(today.getDate() - offset);
    points.set(isoDay(date), {
      date: isoDay(date),
      label: date.toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
      }),
      sessions: 0,
      reps: 0,
      minutes: 0,
    });
  }

  for (const session of sessions) {
    if (!isUsable(session)) continue;

    const point = points.get(isoDay(endedAt(session)));
    // Older than the window, or in the future on a badly set clock.
    if (!point) continue;

    point.sessions += 1;
    point.reps += session.totalReps;
    point.minutes += session.durationSeconds / 60;
  }

  return [...points.values()].map((point) => ({
    ...point,
    minutes: Math.round(point.minutes * 10) / 10,
  }));
}

/**
 * The most recent `limit` completed sessions, oldest first.
 *
 * Ordered for reading left to right, which is the opposite of the order the
 * history endpoint returns.
 */
export function sessionSeries(
  sessions: readonly SessionSummary[],
  limit: number,
): SessionPoint[] {
  return sessions
    .filter(isUsable)
    .slice(0, limit)
    .reverse()
    .map((session, index) => ({
      sessionId: session.sessionId,
      label: `Session ${index + 1}`,
      reps: session.totalReps,
      minutes: Math.round((session.durationSeconds / 60) * 10) / 10,
    }));
}

/** Whether a series has anything worth drawing. */
export function hasData(points: readonly { reps: number }[]): boolean {
  return points.some((point) => point.reps > 0);
}
