/**
 * The live exercise session.
 *
 * Drives the loop described in `docs/06_camera/33_CAMERA_ARCHITECTURE.md`
 * section 4: video frame -> MediaPipe -> 33 landmarks -> backend detector.
 *
 * The browser counts nothing. Repetitions, stages and form feedback all come
 * back from the backend, because the detector engine is the single place that
 * analyses movement.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { exercisesApi } from "@/services/api/endpoints";
import { ApiError } from "@/services/api/client";
import type { FrameResult } from "@/types/api";

import {
  MediaPipePoseProvider,
  PoseModelError,
  type CanonicalHumanSkeleton,
  type PoseProvider,
} from "@/features/camera/poseProvider";

/**
 * How often landmarks are sent to the backend.
 *
 * The camera runs at about 30fps and pose detection runs on every frame so the
 * overlay stays smooth, but posting 30 times a second is unnecessary: a
 * repetition takes roughly one to three seconds, so 12 samples a second gives
 * the detector plenty of transitions to see while cutting the request rate by
 * more than half.
 */
const UPLOAD_INTERVAL_MS = 80;

/** Confidence below which a frame is treated as "nobody is properly in shot". */
const TRACKING_THRESHOLD = 0.5;

export type SessionPhase =
  | "preparing"
  | "loading-model"
  | "ready"
  | "running"
  | "finished"
  | "failed";

export interface LiveSessionState {
  phase: SessionPhase;
  sessionId: string | null;
  reps: number;
  stage: string | null;
  feedback: string[];
  metrics: Record<string, unknown>;
  /** True when the user is not clearly visible to the camera. */
  trackingLost: boolean;
  error: string | null;
  elapsedSeconds: number;
}

interface Options {
  exerciseSlug: string;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  /** Injectable for tests, which have no GPU and no camera. */
  provider?: PoseProvider;
  onSkeleton?: (skeleton: CanonicalHumanSkeleton | null) => void;
}

export function useLiveSession({
  exerciseSlug,
  videoRef,
  provider,
  onSkeleton,
}: Options) {
  const [state, setState] = useState<LiveSessionState>({
    phase: "preparing",
    sessionId: null,
    reps: 0,
    stage: null,
    feedback: [],
    metrics: {},
    trackingLost: false,
    error: null,
    elapsedSeconds: 0,
  });

  const providerRef = useRef<PoseProvider>(provider ?? new MediaPipePoseProvider());
  const sessionIdRef = useRef<string | null>(null);
  const frameRef = useRef<number | null>(null);
  const lastUploadRef = useRef(0);
  const startedAtRef = useRef(0);
  // Guards against overlapping uploads: a slow response must never be applied
  // after a newer one, which would make the rep count jump backwards.
  const inFlightRef = useRef(false);
  const runningRef = useRef(false);

  const patch = useCallback((changes: Partial<LiveSessionState>) => {
    setState((current) => ({ ...current, ...changes }));
  }, []);

  /** Load the pose model and open a backend session. */
  const prepare = useCallback(async () => {
    patch({ phase: "loading-model", error: null });

    try {
      await providerRef.current.initialise();
    } catch (error) {
      patch({
        phase: "failed",
        error:
          error instanceof PoseModelError
            ? error.message
            : "We could not start pose tracking.",
      });
      return;
    }

    try {
      const session = await exercisesApi.start(exerciseSlug);
      sessionIdRef.current = session.sessionId;
      patch({ phase: "ready", sessionId: session.sessionId });
    } catch (error) {
      patch({
        phase: "failed",
        error:
          error instanceof ApiError
            ? error.message
            : "We could not start this exercise session.",
      });
    }
  }, [exerciseSlug, patch]);

  /** Send one frame's landmarks and apply the detector's answer. */
  const upload = useCallback(
    async (skeleton: CanonicalHumanSkeleton) => {
      const sessionId = sessionIdRef.current;
      if (!sessionId || inFlightRef.current) return;

      inFlightRef.current = true;
      try {
        const result: FrameResult = await exercisesApi.frame(
          sessionId,
          skeleton.joints,
        );
        // A late response after the user stopped must not revive the UI.
        if (!runningRef.current) return;

        patch({
          reps: result.reps,
          stage: result.stage,
          feedback: result.feedback,
          metrics: result.metrics,
        });
      } catch (error) {
        // A dropped frame is not worth interrupting the workout for; only a
        // session that no longer exists is fatal.
        if (error instanceof ApiError && error.status === 404) {
          runningRef.current = false;
          patch({ phase: "failed", error: "This session is no longer active." });
        }
      } finally {
        inFlightRef.current = false;
      }
    },
    [patch],
  );

  /** The per-frame loop: detect locally, upload on a slower cadence. */
  const tick = useCallback(() => {
    if (!runningRef.current) return;

    const video = videoRef.current;
    const now = performance.now();

    if (video) {
      const skeleton = providerRef.current.detect(video, now);
      onSkeleton?.(skeleton);

      const lost = !skeleton || skeleton.confidence < TRACKING_THRESHOLD;
      setState((current) =>
        current.trackingLost === lost ? current : { ...current, trackingLost: lost },
      );

      if (skeleton && !lost && now - lastUploadRef.current >= UPLOAD_INTERVAL_MS) {
        lastUploadRef.current = now;
        void upload(skeleton);
      }
    }

    setState((current) => {
      const elapsed = Math.floor((now - startedAtRef.current) / 1000);
      return current.elapsedSeconds === elapsed
        ? current
        : { ...current, elapsedSeconds: elapsed };
    });

    frameRef.current = requestAnimationFrame(tick);
  }, [onSkeleton, upload, videoRef]);

  const start = useCallback(() => {
    if (!sessionIdRef.current) return;

    runningRef.current = true;
    startedAtRef.current = performance.now();
    lastUploadRef.current = 0;
    patch({ phase: "running" });
    frameRef.current = requestAnimationFrame(tick);
  }, [patch, tick]);

  /** Close the session and return its recorded totals. */
  const finish = useCallback(async () => {
    runningRef.current = false;
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    frameRef.current = null;

    const sessionId = sessionIdRef.current;
    if (!sessionId) {
      patch({ phase: "finished" });
      return null;
    }

    try {
      const summary = await exercisesApi.end(sessionId);
      patch({ phase: "finished", reps: summary.totalReps });
      return summary;
    } catch {
      // The workout still happened even if the closing call failed.
      patch({ phase: "finished" });
      return null;
    }
  }, [patch]);

  // Always release the model and stop the loop, however the page is left.
  useEffect(() => {
    const poseProvider = providerRef.current;
    return () => {
      runningRef.current = false;
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
      poseProvider.close();
    };
  }, []);

  return { state, prepare, start, finish };
}
