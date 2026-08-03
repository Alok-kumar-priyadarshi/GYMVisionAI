/**
 * Pose Provider Adapter.
 *
 * Implements `docs/06_camera/34_POSE_PROVIDER_ADAPTER.md`: it receives MediaPipe
 * landmarks, validates them, normalises coordinates and produces a
 * `CanonicalHumanSkeleton`.
 *
 * It calculates no angles, validates no form and counts no repetitions —
 * section 3 assigns all of that to the detector engine on the backend.
 *
 * MediaPipe lives behind the `PoseProvider` interface so a different pose
 * library, or a fake in tests, can replace it without touching the camera
 * lifecycle or the UI.
 */

import { configured } from "@/config/env";
import type { Landmark } from "@/types/api";

/** Number of landmarks MediaPipe Pose produces, and the backend requires. */
export const POSE_LANDMARK_COUNT = 33;

/**
 * Where the MediaPipe runtime is loaded from.
 *
 * Served from this origin, copied out of the installed package by
 * `scripts/sync-mediapipe.mjs`. The runtime's JavaScript and its WASM binary
 * are built together and must be the same version, so a version-pinned CDN URL
 * silently breaks the moment npm resolves a different package version.
 */
const WASM_ROOT = configured(
  import.meta.env.VITE_MEDIAPIPE_WASM_URL,
  "/mediapipe/wasm",
);
/**
 * The pose model itself, about 6 MB.
 *
 * Too large to ship in the repository, so it is fetched once and cached by the
 * browser. Set `VITE_POSE_MODEL_URL` to a self-hosted copy for offline use.
 */
const MODEL_URL = configured(
  import.meta.env.VITE_POSE_MODEL_URL,
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
);

/** One frame's worth of body position, in the shape the rest of the app uses. */
export interface CanonicalHumanSkeleton {
  /** The 33 joints, in MediaPipe's canonical order. */
  joints: Landmark[];
  /** Mean visibility across all joints, 0 to 1. */
  confidence: number;
  /** When the frame was captured, in milliseconds since page load. */
  timestamp: number;
}

/** Produces skeletons from video frames. */
export interface PoseProvider {
  /** Load the model. Safe to call more than once. */
  initialise(): Promise<void>;
  /** Detect a pose in one video frame, or return null if nobody is visible. */
  detect(video: HTMLVideoElement, timestamp: number): CanonicalHumanSkeleton | null;
  /** Release the model and its resources. */
  close(): void;
}

/** Raised when the pose model cannot be loaded. */
export class PoseModelError extends Error {
  constructor() {
    super(
      "We could not load the pose model. Check your connection and try again.",
    );
    this.name = "PoseModelError";
  }
}

interface RawLandmark {
  x: number;
  y: number;
  z?: number;
  visibility?: number;
}

/**
 * Convert MediaPipe output into the canonical skeleton.
 *
 * Exported for testing: this is the whole of the adapter's logic, and it should
 * be verifiable without a camera or a GPU.
 */
export function toSkeleton(
  landmarks: RawLandmark[] | undefined,
  timestamp: number,
): CanonicalHumanSkeleton | null {
  // A frame with nobody in it, or a truncated result, is not an error. The
  // caller simply has nothing to send.
  if (!landmarks || landmarks.length < POSE_LANDMARK_COUNT) return null;

  const joints: Landmark[] = landmarks
    .slice(0, POSE_LANDMARK_COUNT)
    .map((landmark) => ({
      // Normalised coordinates are already 0 to 1, but a joint tracked just
      // outside the frame can exceed that, and the backend expects the
      // documented range.
      x: clamp01(landmark.x),
      y: clamp01(landmark.y),
      z: Number.isFinite(landmark.z) ? (landmark.z as number) : 0,
      visibility: clamp01(landmark.visibility ?? 0),
    }));

  const confidence =
    joints.reduce((total, joint) => total + joint.visibility, 0) / joints.length;

  return { joints, confidence, timestamp };
}

function clamp01(value: number | undefined): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value as number));
}

/** Pose detection backed by MediaPipe Tasks Vision. */
export class MediaPipePoseProvider implements PoseProvider {
  private landmarker: {
    detectForVideo: (
      video: HTMLVideoElement,
      timestamp: number,
    ) => { landmarks?: RawLandmark[][] };
    close: () => void;
  } | null = null;

  private loading: Promise<void> | null = null;

  async initialise(): Promise<void> {
    if (this.landmarker) return;
    // Concurrent callers share one load rather than fetching the model twice.
    if (this.loading) return this.loading;

    this.loading = (async () => {
      try {
        const { FilesetResolver, PoseLandmarker } = await import(
          "@mediapipe/tasks-vision"
        );
        const fileset = await FilesetResolver.forVisionTasks(WASM_ROOT);

        this.landmarker = await PoseLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
          runningMode: "VIDEO",
          numPoses: 1,
        });
      } catch {
        this.loading = null;
        throw new PoseModelError();
      }
    })();

    return this.loading;
  }

  detect(
    video: HTMLVideoElement,
    timestamp: number,
  ): CanonicalHumanSkeleton | null {
    if (!this.landmarker || video.readyState < 2) return null;

    const result = this.landmarker.detectForVideo(video, timestamp);
    return toSkeleton(result.landmarks?.[0], timestamp);
  }

  close(): void {
    this.landmarker?.close();
    this.landmarker = null;
    this.loading = null;
  }
}
