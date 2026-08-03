/**
 * Progress and training history.
 */

import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  StatTile,
} from "@/components/ui";
import { DailyActivityChart, RepTrendChart } from "@/features/progress/Charts";
import {
  dailySeries,
  hasData,
  sessionSeries,
} from "@/features/progress/series";
import { useExerciseHistory, useProgress, useStatistics } from "@/hooks/queries";
import { MAX_SESSION_HISTORY } from "@/services/api/endpoints";

const CHART_DAYS = 30;

/**
 * Enough history to fill the charts; the default page of 20 would not.
 *
 * Capped at what the endpoint accepts. Asking for more is a validation error,
 * not a clamp — requesting 200 here made this page's session list and both
 * charts fail while the totals above them still rendered.
 */
const HISTORY_DEPTH = MAX_SESSION_HISTORY;

/** Sessions plotted on the repetition trend. More becomes unreadable. */
const TREND_SESSIONS = 15;

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder ? `${minutes}m ${remainder}s` : `${minutes}m`;
}

export default function ProgressPage() {
  const progress = useProgress();
  const statistics = useStatistics();
  const history = useExerciseHistory(HISTORY_DEPTH);

  if (progress.isPending || statistics.isPending) {
    return <LoadingState label="Loading your progress" />;
  }

  if (progress.isError || statistics.isError) {
    return (
      <ErrorState
        message="We could not load your progress."
        onRetry={() => {
          void progress.refetch();
          void statistics.refetch();
        }}
      />
    );
  }

  return (
    <>
      <PageHeader
        title="Progress"
        subtitle={
          progress.data.lastWorkoutDate
            ? `Last trained on ${formatDate(progress.data.lastWorkoutDate)}`
            : "Your training history will appear here."
        }
      />

      <section aria-label="Streaks" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label="Current streak" value={progress.data.currentStreak} hint="days" />
        <StatTile label="Best streak" value={progress.data.longestStreak} hint="days" />
        <StatTile label="Workouts" value={progress.data.totalWorkouts} />
        <StatTile
          label="Average session"
          value={progress.data.averageWorkoutMinutes}
          hint="minutes"
        />
      </section>

      <section aria-label="Totals" className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-muted">
          All time
        </h2>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatTile label="Minutes trained" value={progress.data.totalMinutes} />
          <StatTile label="Exercises" value={progress.data.totalExercises} />
          <StatTile
            label="Tracked sessions"
            value={statistics.data.completedSessions}
          />
          <StatTile label="Reps counted" value={statistics.data.totalReps} />
        </div>
      </section>

      {history.data && history.data.length > 0 && (
        <section aria-label="Training over time" className="mt-8 space-y-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
            Over time
          </h2>

          <Card>
            <DailyActivityChart
              points={dailySeries(history.data, CHART_DAYS)}
            />
          </Card>

          {/* Repetitions are meaningless for a plan of only held exercises, so
              the chart appears only once something has actually been counted. */}
          {hasData(sessionSeries(history.data, TREND_SESSIONS)) && (
            <Card>
              <RepTrendChart
                points={sessionSeries(history.data, TREND_SESSIONS)}
              />
            </Card>
          )}
        </section>
      )}

      <section aria-label="Recent sessions" className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-muted">
          Recent sessions
        </h2>

        {history.isPending ? (
          <LoadingState label="Loading sessions" />
        ) : history.isError ? (
          <ErrorState
            message="We could not load your sessions."
            onRetry={() => void history.refetch()}
          />
        ) : history.data.length === 0 ? (
          <EmptyState
            title="No sessions yet"
            message="Start an exercise from your workout and your results will show up here."
          />
        ) : (
          <ul className="space-y-2">
            {history.data.map((session) => (
              <li key={session.sessionId}>
                <Card className="flex flex-wrap items-center justify-between gap-3 py-4">
                  <div>
                    <p className="text-sm font-medium text-ink">
                      {formatDate(session.startedAt)}
                    </p>
                    <p className="text-xs text-ink-muted">
                      {session.totalReps} reps ·{" "}
                      {formatDuration(session.durationSeconds)}
                    </p>
                  </div>
                  <Badge
                    tone={session.status === "Completed" ? "positive" : "neutral"}
                  >
                    {session.status}
                  </Badge>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
