/**
 * The current workout.
 *
 * Shows the generated plan and lets the user request an AI review of it.
 */

import { useState } from "react";
import { Link } from "react-router-dom";

import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui";
import { exercisesCompletedToday } from "@/features/workout/completion";
import { WorkoutTabs } from "@/features/workout/WorkoutTabs";
import { buildTabs } from "@/features/workout/tabs";
import {
  useCurrentWorkout,
  useExerciseHistory,
  useGenerateWorkout,
  useWorkout,
  useWorkoutHistory,
  useWorkoutReview,
} from "@/hooks/queries";
import { ApiError } from "@/services/api/client";
import { MAX_SESSION_HISTORY } from "@/services/api/endpoints";
import type { WorkoutExercise } from "@/types/api";

/**
 * Enough history to cover a full day of work, since only today's sessions can
 * tick an exercise off. The default page of 20 could be filled by yesterday.
 */
const HISTORY_DEPTH = MAX_SESSION_HISTORY;

function prescription(exercise: WorkoutExercise): string {
  const effort =
    exercise.holdSeconds > 0
      ? `${exercise.holdSeconds}s hold`
      : `${exercise.repetitions} reps`;
  return `${exercise.sets} × ${effort}`;
}

/** The completed mark. Never the only signal — a "Done" badge sits beside it. */
function CheckIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-5 w-5"
    >
      <path
        fillRule="evenodd"
        d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0l-3.5-3.5a1 1 0 1 1 1.4-1.4l2.8 2.8 6.8-6.8a1 1 0 0 1 1.4 0Z"
        clipRule="evenodd"
      />
    </svg>
  );
}

/** How far through the plan the user is today. */
function DailyProgress({ done, total }: { done: number; total: number }) {
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;
  // `total` guards the empty case, which would otherwise read as complete.
  const allDone = total > 0 && done === total;

  return (
    <div className="mb-6">
      <div className="mb-2 flex items-center justify-between text-sm">
        <span
          className={allDone ? "font-medium text-positive" : "text-ink-muted"}
        >
          {allDone
            ? "Workout complete for today"
            : `${done} of ${total} done today`}
        </span>
        {done > 0 && !allDone && (
          <span className="text-ink-muted">{percent}%</span>
        )}
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={done}
        aria-label="Exercises completed today"
        className="h-1.5 overflow-hidden rounded-full bg-surface-muted"
      >
        <div
          className="h-full rounded-full bg-positive transition-[width] duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

export default function WorkoutPage() {
  const { data, isPending, isError, error, refetch } = useCurrentWorkout();
  const history = useExerciseHistory(HISTORY_DEPTH);
  const generate = useGenerateWorkout();
  const review = useWorkoutReview();
  const [reviewRequested, setReviewRequested] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  // Null means "whatever is current", so a newly generated plan is followed
  // automatically instead of the view being pinned to a stale identifier.
  const [viewing, setViewing] = useState<string | null>(null);
  const workoutHistory = useWorkoutHistory(1);
  const selected = useWorkout(viewing);

  /**
   * Generation is deterministic, so an unchanged profile returns the plan the
   * user already has. Saying so is the difference between a button that looks
   * broken and one whose outcome is understood.
   */
  function regenerate() {
    setNotice(null);
    generate.mutate(undefined, {
      onSuccess: (plan) => {
        // Return to the current plan, which is the one that just changed.
        setViewing(null);
        setNotice(
          plan.unchanged
            ? "That is already the plan for your profile. Change your goal, fitness level or available time in your profile to get a different one."
            : "New workout generated.",
        );
      },
    });
  }

  // The plan renders without waiting on history: an unmarked exercise for a
  // moment is far better than holding the whole page back.
  const completed = exercisesCompletedToday(history.data ?? []);

  if (isPending) return <LoadingState label="Loading your workout" />;

  // A 404 is the documented answer for "no workout yet", not a failure.
  const hasNoWorkout = error instanceof ApiError && error.status === 404;

  if (hasNoWorkout) {
    return (
      <>
        <PageHeader title="Workout" />
        <EmptyState
          title="No workout yet"
          message="Generate a plan built from your profile. It uses only exercises you can do at home."
          action={
            <Button loading={generate.isPending} onClick={regenerate}>
              Generate my workout
            </Button>
          }
        />
        {generate.isError && (
          <p role="alert" className="mt-3 text-center text-sm text-danger">
            {generate.error instanceof ApiError
              ? generate.error.message
              : "We could not generate a workout."}
          </p>
        )}
      </>
    );
  }

  if (isError || !data) {
    return (
      <ErrorState
        message="We could not load your workout."
        onRetry={() => void refetch()}
      />
    );
  }

  const tabs = buildTabs(data, workoutHistory.data?.data ?? []);
  // While an older plan loads, keep showing the current one rather than
  // blanking the page.
  const shown = viewing && selected.data ? selected.data : data;
  const isPast = shown.workoutId !== data.workoutId;

  return (
    <>
      <PageHeader
        title={shown.name}
        subtitle={`${shown.exerciseCount} exercises · about ${shown.estimatedDurationMinutes} minutes`}
        action={
          <Button
            variant="secondary"
            loading={generate.isPending}
            onClick={regenerate}
          >
            Generate a new one
          </Button>
        }
      />

      <WorkoutTabs
        tabs={tabs}
        selectedId={shown.workoutId}
        onSelect={(id) => setViewing(id === data.workoutId ? null : id)}
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <Badge tone="brand">{shown.difficulty}</Badge>
        <Badge>{shown.goal}</Badge>
        {isPast && <Badge tone="warning">Earlier plan</Badge>}
      </div>

      {generate.isError ? (
        <p role="alert" className="mb-4 text-sm text-danger">
          {generate.error instanceof ApiError
            ? generate.error.message
            : "We could not generate a workout."}
        </p>
      ) : notice ? (
        <p role="status" className="mb-4 text-sm text-ink-muted">
          {notice}
        </p>
      ) : null}

      <div
        role="tabpanel"
        id={`workout-panel-${shown.workoutId}`}
        aria-labelledby={`workout-tab-${shown.workoutId}`}
        tabIndex={-1}
      >
        {/* Counted against the plan, not against `completed`: an exercise done
            outside this workout must not push the bar past full. */}
        <DailyProgress
          done={
            shown.exercises.filter((item) => completed.has(item.exerciseId))
              .length
          }
          total={shown.exercises.length}
        />

        <ol className="space-y-3">
          {shown.exercises.map((exercise) => {
            const isDone = completed.has(exercise.exerciseId);

            return (
              <li key={exercise.exerciseId}>
                {/* The completed state is carried by the check and the badge.
                  Tinting the card itself would mean overriding Card's own
                  background, and `cx` is a plain join with no conflict
                  resolution, so which class won would depend on the order
                  Tailwind happened to emit them in. */}
                <Card>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-3">
                      <span
                        aria-hidden="true"
                        className={
                          isDone
                            ? "flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-positive text-white"
                            : "flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-50 text-sm font-semibold text-brand-700"
                        }
                      >
                        {isDone ? <CheckIcon /> : exercise.displayOrder}
                      </span>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p
                            className={
                              isDone
                                ? "truncate font-medium text-ink-muted"
                                : "truncate font-medium text-ink"
                            }
                          >
                            {exercise.name}
                          </p>
                          {isDone && <Badge tone="positive">Done</Badge>}
                        </div>
                        <p className="text-sm text-ink-muted">
                          {prescription(exercise)} · {exercise.restSeconds}s
                          rest
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Link
                        to={`/exercises/${exercise.slug}`}
                        className="text-sm font-medium text-brand-700 hover:underline"
                      >
                        How to do it
                      </Link>
                      <Link to={`/exercises/${exercise.slug}/live`}>
                        {/* Repeating a finished exercise stays available, but is
                          worded so it does not read as work still outstanding. */}
                        <Button variant={isDone ? "ghost" : "secondary"}>
                          {isDone ? "Do it again" : "Start"}
                        </Button>
                      </Link>
                    </div>
                  </div>
                </Card>
              </li>
            );
          })}
        </ol>
      </div>

      <section aria-label="Coach review" className="mt-8">
        <Card>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
            Coach review
          </h2>

          {!reviewRequested ? (
            <>
              <p className="mt-2 text-sm text-ink-muted">
                Ask the coach to review this workout and your recorded sessions.
              </p>
              <Button
                variant="secondary"
                className="mt-4"
                onClick={() => {
                  setReviewRequested(true);
                  review.mutate(shown.workoutId);
                }}
              >
                Review my workout
              </Button>
            </>
          ) : review.isPending ? (
            <LoadingState label="Reviewing your workout" />
          ) : review.isError ? (
            <p role="alert" className="mt-3 text-sm text-danger">
              The coach is unavailable right now. Please try again later.
            </p>
          ) : review.data ? (
            <div className="mt-3 space-y-4 text-sm">
              <p className="leading-relaxed text-ink">{review.data.summary}</p>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-positive">
                    Strengths
                  </h3>
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-ink">
                    {review.data.strengths.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-warning">
                    To work on
                  </h3>
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-ink">
                    {review.data.improvements.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              </div>

              <p className="rounded-lg bg-brand-50 p-3 leading-relaxed text-brand-700">
                {review.data.motivation}
              </p>
            </div>
          ) : null}
        </Card>
      </section>
    </>
  );
}
