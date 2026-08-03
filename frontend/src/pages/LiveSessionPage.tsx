/**
 * Live exercise session.
 *
 * The camera screen: permission, video, skeleton overlay, and the live counts
 * the backend detector returns.
 */

import { useCallback, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  Badge,
  Button,
  Card,
  ErrorState,
  LoadingState,
} from "@/components/ui";
import { PoseOverlay } from "@/features/camera/PoseOverlay";
import type { CanonicalHumanSkeleton } from "@/features/camera/poseProvider";
import { cameraProblem, useCamera } from "@/features/camera/useCamera";
import { useLiveSession } from "@/features/camera/useLiveSession";
import { useExercise, useSessionRecorded } from "@/hooks/queries";
import type { SessionSummary } from "@/types/api";

function formatClock(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export default function LiveSessionPage() {
  const { slug = "" } = useParams();
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [skeleton, setSkeleton] = useState<CanonicalHumanSkeleton | null>(null);
  const [summary, setSummary] = useState<SessionSummary | null>(null);

  const exercise = useExercise(slug);
  const camera = useCamera(videoRef);
  const sessionRecorded = useSessionRecorded();

  const handleSkeleton = useCallback((next: CanonicalHumanSkeleton | null) => {
    setSkeleton(next);
  }, []);

  const session = useLiveSession({
    exerciseSlug: slug,
    videoRef,
    onSkeleton: handleSkeleton,
  });

  const isHold = exercise.data?.exerciseType === "Duration";

  /** Ask for the camera, load the model, open the session, then begin. */
  async function begin() {
    await camera.start();
    await session.prepare();
  }

  async function stop() {
    const result = await session.finish();
    camera.stop();
    setSkeleton(null);
    setSummary(result);
    // Only a session the backend actually closed changes what those pages show.
    if (result) sessionRecorded();
  }

  if (exercise.isPending) return <LoadingState label="Loading exercise" />;
  if (exercise.isError || !exercise.data) {
    return (
      <ErrorState
        title="Exercise not found"
        message="This exercise is not part of the supported library."
      />
    );
  }

  // --- Finished ------------------------------------------------------------

  if (session.state.phase === "finished") {
    return (
      <div className="mx-auto max-w-md text-center">
        <h1 className="text-2xl font-semibold text-ink">Session complete</h1>
        <p className="mt-1 text-sm text-ink-muted">{exercise.data.name}</p>

        <Card className="mt-6">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-ink-muted">
                {isHold ? "Held" : "Reps"}
              </p>
              <p className="mt-1 text-4xl font-semibold tabular-nums text-ink">
                {summary?.totalReps ?? session.state.reps}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-ink-muted">
                Duration
              </p>
              <p className="mt-1 text-4xl font-semibold tabular-nums text-ink">
                {formatClock(
                  summary?.durationSeconds ?? session.state.elapsedSeconds,
                )}
              </p>
            </div>
          </div>
        </Card>

        <div className="mt-6 flex flex-col gap-3">
          <Button onClick={() => navigate("/workout")}>Back to workout</Button>
          <Button variant="secondary" onClick={() => window.location.reload()}>
            Go again
          </Button>
        </div>
      </div>
    );
  }

  // --- Failed --------------------------------------------------------------

  if (session.state.phase === "failed") {
    return (
      <ErrorState
        title="We could not start the session"
        message={session.state.error ?? undefined}
        onRetry={() => void begin()}
      />
    );
  }

  const problem = cameraProblem(camera.state);
  const isLive = session.state.phase === "running";

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <Link
            to={`/exercises/${slug}`}
            className="text-sm text-brand-700 hover:underline"
          >
            ← {exercise.data.name}
          </Link>
          <p className="text-xs text-ink-muted">
            {isHold ? "Hold the position" : "Counted by the camera"}
          </p>
        </div>
        {isLive && (
          <span
            className="flex items-center gap-2 text-sm font-medium text-danger"
            role="status"
          >
            <span
              aria-hidden="true"
              className="h-2.5 w-2.5 animate-pulse rounded-full bg-danger"
            />
            Recording
          </span>
        )}
      </div>

      <div className="relative overflow-hidden rounded-card bg-black">
        {/* Mirrored so moving right on screen matches moving right in life. */}
        <video
          ref={videoRef}
          playsInline
          muted
          className="aspect-video w-full -scale-x-100 object-cover"
        />
        <PoseOverlay skeleton={skeleton} />

        {camera.state === "idle" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-black/70 p-6 text-center">
            <p className="max-w-sm text-sm text-white/90">
              GymVision uses your camera to count reps and check your form. Video
              stays on your device — only body positions are sent.
            </p>
            <Button onClick={() => void begin()}>Turn on the camera</Button>
          </div>
        )}

        {(camera.state === "requesting" ||
          session.state.phase === "loading-model") && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/70">
            <p className="text-sm text-white/90">
              {camera.state === "requesting"
                ? "Waiting for camera permission…"
                : "Loading pose tracking…"}
            </p>
          </div>
        )}

        {problem && (
          <div
            role="alert"
            className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-black/80 p-6 text-center"
          >
            <p className="max-w-sm text-sm text-white/90">{problem}</p>
            <Button variant="secondary" onClick={() => void begin()}>
              Try again
            </Button>
          </div>
        )}

        {isLive && session.state.trackingLost && (
          <p
            role="status"
            className="absolute inset-x-0 bottom-0 bg-warning/90 px-4 py-2 text-center text-sm font-medium text-white"
          >
            Step back so your whole body is in frame.
          </p>
        )}
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        <Card className="text-center">
          <p className="text-xs uppercase tracking-wide text-ink-muted">
            {isHold ? "Holding" : "Reps"}
          </p>
          <p
            aria-live="polite"
            className="mt-1 text-4xl font-semibold tabular-nums text-ink"
          >
            {session.state.reps}
          </p>
        </Card>
        <Card className="text-center">
          <p className="text-xs uppercase tracking-wide text-ink-muted">Time</p>
          <p className="mt-1 text-4xl font-semibold tabular-nums text-ink">
            {formatClock(session.state.elapsedSeconds)}
          </p>
        </Card>
        <Card className="text-center">
          <p className="text-xs uppercase tracking-wide text-ink-muted">Stage</p>
          <p className="mt-2 text-lg font-medium capitalize text-ink">
            {session.state.stage?.replace(/_/g, " ") ?? "—"}
          </p>
        </Card>
      </div>

      {session.state.feedback.length > 0 && (
        <div aria-live="polite" className="mt-4 flex flex-wrap gap-2">
          {session.state.feedback.map((note) => (
            <Badge key={note} tone="brand">
              {note}
            </Badge>
          ))}
        </div>
      )}

      <div className="mt-6 flex justify-center gap-3">
        {session.state.phase === "ready" && (
          <Button onClick={session.start}>Start {exercise.data.name}</Button>
        )}
        {isLive && (
          <Button variant="danger" onClick={() => void stop()}>
            Finish session
          </Button>
        )}
      </div>
    </div>
  );
}
