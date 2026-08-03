/**
 * Skeleton overlay.
 *
 * The Overlay Renderer from `docs/06_camera/33_CAMERA_ARCHITECTURE.md`
 * section 6. It draws what the camera subsystem produced and interprets
 * nothing.
 */

import { useEffect, useRef } from "react";

import type { CanonicalHumanSkeleton } from "@/features/camera/poseProvider";

/**
 * MediaPipe's 33-point topology, as index pairs.
 *
 * Declared here rather than imported so the overlay does not depend on the
 * pose library, and so tests can render it without loading a model.
 */
const CONNECTIONS: ReadonlyArray<readonly [number, number]> = [
  // Face
  [0, 2], [0, 5], [2, 7], [5, 8],
  // Torso
  [11, 12], [11, 23], [12, 24], [23, 24],
  // Left arm
  [11, 13], [13, 15], [15, 17], [15, 19], [15, 21],
  // Right arm
  [12, 14], [14, 16], [16, 18], [16, 20], [16, 22],
  // Left leg
  [23, 25], [25, 27], [27, 29], [27, 31],
  // Right leg
  [24, 26], [26, 28], [28, 30], [28, 32],
];

/** Joints below this visibility are not drawn, to avoid inventing limbs. */
const VISIBILITY_THRESHOLD = 0.5;

const JOINT_COLOUR = "#ffffff";
const BONE_COLOUR = "rgba(90, 140, 255, 0.95)";

interface Props {
  skeleton: CanonicalHumanSkeleton | null;
  /** Mirrored to match the mirrored video, so the user's left looks left. */
  mirrored?: boolean;
  className?: string;
}

export function PoseOverlay({ skeleton, mirrored = true, className }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext("2d");
    if (!context) return;

    // Match the canvas buffer to its displayed size, or the drawing stretches.
    const { width, height } = canvas.getBoundingClientRect();
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }

    context.clearRect(0, 0, canvas.width, canvas.height);
    if (!skeleton) return;

    const toX = (x: number) => (mirrored ? 1 - x : x) * canvas.width;
    const toY = (y: number) => y * canvas.height;
    const visible = (index: number) =>
      (skeleton.joints[index]?.visibility ?? 0) >= VISIBILITY_THRESHOLD;

    context.lineWidth = Math.max(2, canvas.width / 260);
    context.strokeStyle = BONE_COLOUR;
    context.lineCap = "round";

    for (const [from, to] of CONNECTIONS) {
      if (!visible(from) || !visible(to)) continue;

      context.beginPath();
      context.moveTo(toX(skeleton.joints[from].x), toY(skeleton.joints[from].y));
      context.lineTo(toX(skeleton.joints[to].x), toY(skeleton.joints[to].y));
      context.stroke();
    }

    context.fillStyle = JOINT_COLOUR;
    const radius = Math.max(3, canvas.width / 320);

    skeleton.joints.forEach((joint, index) => {
      // The face produces eleven points that clutter the view without adding
      // anything a user can act on, so only the body is marked.
      if (index < 11 || joint.visibility < VISIBILITY_THRESHOLD) return;

      context.beginPath();
      context.arc(toX(joint.x), toY(joint.y), radius, 0, Math.PI * 2);
      context.fill();
    });
  }, [skeleton, mirrored]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={className ?? "pointer-events-none absolute inset-0 h-full w-full"}
    />
  );
}
