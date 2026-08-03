/**
 * Camera lifecycle.
 *
 * Implements the state machine in `docs/06_camera/33_CAMERA_ARCHITECTURE.md`
 * section 5:
 *
 *     Idle -> PermissionRequested -> Active -> Paused -> Active -> Stopped
 *
 * Only one camera session exists at a time, and the stream is always released:
 * a webcam left running is both a privacy problem and a hardware lock.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export type CameraState =
  | "idle"
  | "requesting"
  | "active"
  | "paused"
  | "stopped"
  | "denied"
  | "unavailable";

const VIDEO_CONSTRAINTS: MediaStreamConstraints = {
  video: {
    width: { ideal: 1280 },
    height: { ideal: 720 },
    facingMode: "user",
    frameRate: { ideal: 30 },
  },
  audio: false,
};

/** A message explaining why the camera is not running, or null when it is. */
export function cameraProblem(state: CameraState): string | null {
  switch (state) {
    case "denied":
      return "GymVision needs camera access to watch your form. Allow it in your browser settings, then try again.";
    case "unavailable":
      return "No camera was found, or this browser does not support camera access.";
    default:
      return null;
  }
}

export function useCamera(videoRef: React.RefObject<HTMLVideoElement | null>) {
  const [state, setState] = useState<CameraState>("idle");
  const streamRef = useRef<MediaStream | null>(null);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    if (videoRef.current) videoRef.current.srcObject = null;
    setState("stopped");
  }, [videoRef]);

  const start = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setState("unavailable");
      return;
    }

    setState("requesting");

    try {
      const stream = await navigator.mediaDevices.getUserMedia(VIDEO_CONSTRAINTS);
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      setState("active");
    } catch (error) {
      const name = (error as DOMException)?.name;
      // A refusal is the user's choice, not a fault; anything else means the
      // device is missing or already in use.
      setState(
        name === "NotAllowedError" || name === "SecurityError"
          ? "denied"
          : "unavailable",
      );
    }
  }, [videoRef]);

  const pause = useCallback(() => {
    streamRef.current?.getVideoTracks().forEach((track) => {
      track.enabled = false;
    });
    setState("paused");
  }, []);

  const resume = useCallback(() => {
    streamRef.current?.getVideoTracks().forEach((track) => {
      track.enabled = true;
    });
    setState("active");
  }, []);

  // Release the camera when the component goes away, however it goes away.
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    };
  }, []);

  return { state, start, stop, pause, resume, isRunning: state === "active" };
}
