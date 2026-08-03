/** Tests for the camera subsystem: pose adapter, lifecycle and live session. */

import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createRef } from "react";

import {
  POSE_LANDMARK_COUNT,
  toSkeleton,
  type CanonicalHumanSkeleton,
  type PoseProvider,
} from "@/features/camera/poseProvider";
import { cameraProblem, useCamera } from "@/features/camera/useCamera";
import { useLiveSession } from "@/features/camera/useLiveSession";
import { tokenStore } from "@/services/api/client";
import { errorResponse, successResponse } from "@/test/render";

function rawLandmarks(count = POSE_LANDMARK_COUNT, visibility = 0.9) {
  return Array.from({ length: count }, (_, index) => ({
    x: index / 100,
    y: index / 200,
    z: 0.1,
    visibility,
  }));
}

// --- Pose adapter ----------------------------------------------------------

describe("the pose adapter", () => {
  it("produces 33 canonical joints", () => {
    const skeleton = toSkeleton(rawLandmarks(), 1234);

    expect(skeleton).not.toBeNull();
    expect(skeleton!.joints).toHaveLength(POSE_LANDMARK_COUNT);
    expect(skeleton!.timestamp).toBe(1234);
  });

  it("returns nothing when nobody is in frame", () => {
    expect(toSkeleton(undefined, 0)).toBeNull();
    expect(toSkeleton([], 0)).toBeNull();
  });

  it("rejects a truncated landmark set", () => {
    // The backend requires all 33; a partial set would fail validation there.
    expect(toSkeleton(rawLandmarks(20), 0)).toBeNull();
  });

  it("clamps coordinates that fall outside the frame", () => {
    const landmarks = rawLandmarks();
    landmarks[0] = { x: 1.4, y: -0.3, z: 0, visibility: 1.8 };

    const skeleton = toSkeleton(landmarks, 0)!;

    expect(skeleton.joints[0].x).toBe(1);
    expect(skeleton.joints[0].y).toBe(0);
    expect(skeleton.joints[0].visibility).toBe(1);
  });

  it("defaults a missing visibility to zero", () => {
    const landmarks = rawLandmarks().map(({ x, y }) => ({ x, y }));

    expect(toSkeleton(landmarks, 0)!.joints[0].visibility).toBe(0);
  });

  it("averages visibility into a confidence score", () => {
    expect(toSkeleton(rawLandmarks(33, 0.8), 0)!.confidence).toBeCloseTo(0.8, 5);
  });

  it("treats a non-numeric coordinate as unknown rather than guessing", () => {
    const landmarks = rawLandmarks();
    landmarks[5] = { x: NaN, y: Infinity, z: NaN, visibility: NaN };

    const skeleton = toSkeleton(landmarks, 0)!;

    // Zero, not a clamped extreme: an unusable number carries no position, and
    // the joint's zero visibility keeps it out of the overlay anyway.
    expect(skeleton.joints[5]).toEqual({ x: 0, y: 0, z: 0, visibility: 0 });
  });
});

// --- Camera lifecycle ------------------------------------------------------

describe("the camera lifecycle", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  function videoRef() {
    const ref = createRef<HTMLVideoElement>();
    const element = document.createElement("video");
    element.play = vi.fn().mockResolvedValue(undefined);
    (ref as { current: HTMLVideoElement }).current = element;
    return ref;
  }

  function mockStream() {
    const track = { stop: vi.fn(), enabled: true };
    return {
      stream: {
        getTracks: () => [track],
        getVideoTracks: () => [track],
      } as unknown as MediaStream,
      track,
    };
  }

  it("starts idle", () => {
    const { result } = renderHook(() => useCamera(videoRef()));

    expect(result.current.state).toBe("idle");
  });

  it("becomes active once permission is granted", async () => {
    const { stream } = mockStream();
    vi.stubGlobal("navigator", {
      mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(stream) },
    });

    const { result } = renderHook(() => useCamera(videoRef()));
    await act(async () => {
      await result.current.start();
    });

    expect(result.current.state).toBe("active");
    expect(result.current.isRunning).toBe(true);
  });

  it("reports a refusal separately from a missing camera", async () => {
    vi.stubGlobal("navigator", {
      mediaDevices: {
        getUserMedia: vi
          .fn()
          .mockRejectedValue(
            Object.assign(new Error("no"), { name: "NotAllowedError" }),
          ),
      },
    });

    const { result } = renderHook(() => useCamera(videoRef()));
    await act(async () => {
      await result.current.start();
    });

    expect(result.current.state).toBe("denied");
    expect(cameraProblem("denied")).toMatch(/camera access/i);
  });

  it("reports an unavailable device", async () => {
    vi.stubGlobal("navigator", {
      mediaDevices: {
        getUserMedia: vi
          .fn()
          .mockRejectedValue(
            Object.assign(new Error("no"), { name: "NotFoundError" }),
          ),
      },
    });

    const { result } = renderHook(() => useCamera(videoRef()));
    await act(async () => {
      await result.current.start();
    });

    expect(result.current.state).toBe("unavailable");
  });

  it("reports a browser without camera support", async () => {
    vi.stubGlobal("navigator", {});

    const { result } = renderHook(() => useCamera(videoRef()));
    await act(async () => {
      await result.current.start();
    });

    expect(result.current.state).toBe("unavailable");
  });

  it("stops every track when stopped", async () => {
    const { stream, track } = mockStream();
    vi.stubGlobal("navigator", {
      mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(stream) },
    });

    const { result } = renderHook(() => useCamera(videoRef()));
    await act(async () => {
      await result.current.start();
    });
    act(() => result.current.stop());

    expect(track.stop).toHaveBeenCalled();
    expect(result.current.state).toBe("stopped");
  });

  it("releases the camera when the component unmounts", async () => {
    const { stream, track } = mockStream();
    vi.stubGlobal("navigator", {
      mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(stream) },
    });

    const { result, unmount } = renderHook(() => useCamera(videoRef()));
    await act(async () => {
      await result.current.start();
    });
    unmount();

    // A webcam left running is a privacy problem, not just a leak.
    expect(track.stop).toHaveBeenCalled();
  });

  it("pauses without releasing the device", async () => {
    const { stream, track } = mockStream();
    vi.stubGlobal("navigator", {
      mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(stream) },
    });

    const { result } = renderHook(() => useCamera(videoRef()));
    await act(async () => {
      await result.current.start();
    });

    act(() => result.current.pause());
    expect(result.current.state).toBe("paused");
    expect(track.enabled).toBe(false);
    expect(track.stop).not.toHaveBeenCalled();

    act(() => result.current.resume());
    expect(result.current.state).toBe("active");
    expect(track.enabled).toBe(true);
  });
});

// --- Live session ----------------------------------------------------------

describe("the live session", () => {
  beforeEach(() => {
    tokenStore.clear();
    vi.restoreAllMocks();
  });

  function fakeProvider(skeleton: CanonicalHumanSkeleton | null): PoseProvider {
    return {
      initialise: vi.fn().mockResolvedValue(undefined),
      detect: vi.fn().mockReturnValue(skeleton),
      close: vi.fn(),
    };
  }

  const SKELETON: CanonicalHumanSkeleton = {
    joints: rawLandmarks().map((l) => ({ ...l, z: 0 })),
    confidence: 0.9,
    timestamp: 0,
  };

  function videoRef() {
    const ref = createRef<HTMLVideoElement>();
    (ref as { current: HTMLVideoElement }).current =
      document.createElement("video");
    return ref;
  }

  it("loads the model and opens a session", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        successResponse({
          sessionId: "ses-1",
          workoutId: null,
          exerciseId: "push_ups",
          exerciseName: "Push-ups",
          status: "running",
          startedAt: "2026-08-02T10:00:00Z",
        }),
      ),
    );
    const provider = fakeProvider(SKELETON);

    const { result } = renderHook(() =>
      useLiveSession({ exerciseSlug: "push_ups", videoRef: videoRef(), provider }),
    );

    await act(async () => {
      await result.current.prepare();
    });

    expect(provider.initialise).toHaveBeenCalled();
    expect(result.current.state.phase).toBe("ready");
    expect(result.current.state.sessionId).toBe("ses-1");
  });

  it("fails cleanly when the model will not load", async () => {
    const provider = fakeProvider(null);
    provider.initialise = vi.fn().mockRejectedValue(new Error("no gpu"));

    const { result } = renderHook(() =>
      useLiveSession({ exerciseSlug: "push_ups", videoRef: videoRef(), provider }),
    );

    await act(async () => {
      await result.current.prepare();
    });

    expect(result.current.state.phase).toBe("failed");
    expect(result.current.state.error).toBeTruthy();
  });

  it("fails cleanly when the backend refuses a second session", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          errorResponse("EXERCISE-003", 409, "Exercise session already active."),
        ),
    );

    const { result } = renderHook(() =>
      useLiveSession({
        exerciseSlug: "push_ups",
        videoRef: videoRef(),
        provider: fakeProvider(SKELETON),
      }),
    );

    await act(async () => {
      await result.current.prepare();
    });

    expect(result.current.state.phase).toBe("failed");
    expect(result.current.state.error).toMatch(/already active/i);
  });

  it("shows the repetition count the backend returned", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        successResponse({
          sessionId: "ses-1",
          workoutId: null,
          exerciseId: "push_ups",
          exerciseName: "Push-ups",
          status: "running",
          startedAt: "2026-08-02T10:00:00Z",
        }),
      )
      .mockResolvedValue(
        successResponse({
          sessionId: "ses-1",
          exerciseId: "push_ups",
          reps: 4,
          stage: "down",
          feedback: ["Good form"],
          metrics: { elbow_angle: 88 },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useLiveSession({
        exerciseSlug: "push_ups",
        videoRef: videoRef(),
        provider: fakeProvider(SKELETON),
      }),
    );

    await act(async () => {
      await result.current.prepare();
    });
    act(() => result.current.start());

    // The browser counts nothing: the number comes back from the detector.
    await waitFor(() => expect(result.current.state.reps).toBe(4));
    expect(result.current.state.stage).toBe("down");
    expect(result.current.state.feedback).toEqual(["Good form"]);
  });

  it("warns when the user is not properly in frame", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        successResponse({
          sessionId: "ses-1",
          workoutId: null,
          exerciseId: "push_ups",
          exerciseName: "Push-ups",
          status: "running",
          startedAt: "2026-08-02T10:00:00Z",
        }),
      ),
    );

    const { result } = renderHook(() =>
      useLiveSession({
        exerciseSlug: "push_ups",
        videoRef: videoRef(),
        provider: fakeProvider({ ...SKELETON, confidence: 0.2 }),
      }),
    );

    await act(async () => {
      await result.current.prepare();
    });
    act(() => result.current.start());

    await waitFor(() => expect(result.current.state.trackingLost).toBe(true));
  });

  it("does not upload a frame with nobody in it", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      successResponse({
        sessionId: "ses-1",
        workoutId: null,
        exerciseId: "push_ups",
        exerciseName: "Push-ups",
        status: "running",
        startedAt: "2026-08-02T10:00:00Z",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useLiveSession({
        exerciseSlug: "push_ups",
        videoRef: videoRef(),
        provider: fakeProvider(null),
      }),
    );

    await act(async () => {
      await result.current.prepare();
    });
    act(() => result.current.start());
    await new Promise((resolve) => setTimeout(resolve, 120));

    // Only the session-start call; no frames were posted.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("closes the session and reports the recorded total", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        successResponse({
          sessionId: "ses-1",
          workoutId: null,
          exerciseId: "push_ups",
          exerciseName: "Push-ups",
          status: "running",
          startedAt: "2026-08-02T10:00:00Z",
        }),
      )
      .mockResolvedValueOnce(
        successResponse({
          sessionId: "ses-1",
          exerciseId: "push_ups",
          status: "Completed",
          totalReps: 12,
          durationSeconds: 95,
          averageAccuracy: 0.93,
          startedAt: "2026-08-02T10:00:00Z",
          completedAt: "2026-08-02T10:01:35Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useLiveSession({
        exerciseSlug: "push_ups",
        videoRef: videoRef(),
        provider: fakeProvider(SKELETON),
      }),
    );

    await act(async () => {
      await result.current.prepare();
    });

    let summary: unknown;
    await act(async () => {
      summary = await result.current.finish();
    });

    expect(result.current.state.phase).toBe("finished");
    expect((summary as { totalReps: number }).totalReps).toBe(12);
  });

  it("still finishes when the closing call fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        successResponse({
          sessionId: "ses-1",
          workoutId: null,
          exerciseId: "push_ups",
          exerciseName: "Push-ups",
          status: "running",
          startedAt: "2026-08-02T10:00:00Z",
        }),
      )
      .mockResolvedValue(errorResponse("SYSTEM-001", 500));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useLiveSession({
        exerciseSlug: "push_ups",
        videoRef: videoRef(),
        provider: fakeProvider(SKELETON),
      }),
    );

    await act(async () => {
      await result.current.prepare();
    });
    await act(async () => {
      await result.current.finish();
    });

    // The workout happened even if the server did not hear about it.
    expect(result.current.state.phase).toBe("finished");
  });

  it("releases the pose model on unmount", async () => {
    const provider = fakeProvider(SKELETON);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(successResponse({})));

    const { unmount } = renderHook(() =>
      useLiveSession({ exerciseSlug: "push_ups", videoRef: videoRef(), provider }),
    );
    unmount();

    expect(provider.close).toHaveBeenCalled();
  });
});
