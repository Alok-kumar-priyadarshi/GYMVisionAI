/**
 * One exercise, with an optional AI explanation.
 *
 * The explanation is requested on demand rather than on load: it costs a model
 * call, and most visits only need the documented steps.
 */

import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  Badge,
  Button,
  Card,
  ErrorState,
  LoadingState,
  PageHeader,
  Spinner,
} from "@/components/ui";
import { useExercise, useExerciseExplanation } from "@/hooks/queries";

export default function ExerciseDetailPage() {
  const { slug = "" } = useParams();
  const { data, isPending, isError, refetch } = useExercise(slug);
  const [wantsExplanation, setWantsExplanation] = useState(false);
  const explanation = useExerciseExplanation(slug, wantsExplanation);

  if (isPending) return <LoadingState label="Loading exercise" />;
  if (isError || !data) {
    return (
      <ErrorState
        title="Exercise not found"
        message="This exercise is not part of the supported library."
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <>
      <Link
        to="/exercises"
        className="mb-4 inline-block text-sm text-brand-700 hover:underline"
      >
        ← All exercises
      </Link>

      <PageHeader title={data.name} subtitle={data.primaryMuscles.join(" · ")} />

      <div className="mb-6 flex flex-wrap gap-2">
        <Badge tone="brand">{data.category}</Badge>
        <Badge>{data.difficulty}</Badge>
        <Badge>{data.movementType}</Badge>
        <Badge tone={data.exerciseType === "Duration" ? "warning" : "neutral"}>
          {data.exerciseType === "Duration" ? "Timed hold" : "Counted reps"}
        </Badge>
        {data.detectorAvailable && <Badge tone="positive">Camera tracking</Badge>}
      </div>

      {data.detectorAvailable && (
        <Link to={`/exercises/${slug}/live`} className="mb-6 inline-block">
          <Button>Start with camera</Button>
        </Link>
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
            How to perform it
          </h2>
          <ol className="mt-3 space-y-3">
            {data.instructions.map((step, index) => (
              <li key={step} className="flex gap-3 text-sm text-ink">
                <span
                  aria-hidden="true"
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700"
                >
                  {index + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
        </Card>

        <div className="space-y-5">
          <Card>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
              Muscles
            </h2>
            <dl className="mt-3 space-y-2 text-sm">
              <div>
                <dt className="text-ink-muted">Primary</dt>
                <dd className="text-ink">{data.primaryMuscles.join(", ")}</dd>
              </div>
              {data.secondaryMuscles.length > 0 && (
                <div>
                  <dt className="text-ink-muted">Secondary</dt>
                  <dd className="text-ink">{data.secondaryMuscles.join(", ")}</dd>
                </div>
              )}
              <div>
                <dt className="text-ink-muted">Equipment</dt>
                <dd className="text-ink">
                  {data.equipment.includes("none")
                    ? "None needed"
                    : data.equipment.join(", ").replace(/_/g, " ")}
                </dd>
              </div>
            </dl>
          </Card>

          <Card>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
              Ask the coach
            </h2>

            {!wantsExplanation ? (
              <>
                <p className="mt-2 text-sm text-ink-muted">
                  Get a coaching explanation of technique, mistakes and breathing.
                </p>
                <Button
                  variant="secondary"
                  fullWidth
                  className="mt-4"
                  onClick={() => setWantsExplanation(true)}
                >
                  Explain this exercise
                </Button>
              </>
            ) : explanation.isPending ? (
              <p className="mt-3 flex items-center gap-2 text-sm text-ink-muted">
                <Spinner size="sm" /> Writing your explanation…
              </p>
            ) : explanation.isError ? (
              <p role="alert" className="mt-3 text-sm text-danger">
                The coach is unavailable right now. The steps above still apply.
              </p>
            ) : (
              <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-ink">
                {explanation.data?.explanation}
              </p>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
