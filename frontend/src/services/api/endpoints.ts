/**
 * Typed wrappers for every backend endpoint.
 *
 * One function per documented contract. Components never build a URL, so a
 * route change is a change in this file alone.
 */

import { request, requestPaged, type Paged } from "@/services/api/client";
import type {
  DietPlan,
  DietPlanSummary,
  DietPreference,
  AccessTokenResult,
  BodyProfile,
  ChatReply,
  Dashboard,
  ExerciseDetail,
  ExerciseExplanation,
  ExerciseSession,
  ExerciseSummary,
  FrameResult,
  Landmark,
  LoginResult,
  ProfileInput,
  Progress,
  SessionSummary,
  Statistics,
  User,
  WorkoutDetail,
  WorkoutReview,
  WorkoutSummary,
} from "@/types/api";

export const authApi = {
  /** POST /auth/google — exchange a Google ID token for application tokens. */
  loginWithGoogle: (idToken: string) =>
    request<LoginResult>("/auth/google", {
      method: "POST",
      body: { idToken },
      anonymous: true,
    }),

  /** POST /auth/refresh — renew an access token. */
  refresh: (refreshToken: string) =>
    request<AccessTokenResult>("/auth/refresh", {
      method: "POST",
      body: { refreshToken },
      anonymous: true,
    }),

  /** GET /auth/me — the signed-in user. */
  me: () => request<User>("/auth/me"),

  /** POST /auth/logout — acknowledge sign-out. */
  logout: () => request<null>("/auth/logout", { method: "POST", body: {} }),
};

export const dietApi = {
  /** POST /diet/generate — build and store a plan. Deterministic, never AI. */
  generate: (dietPreference?: DietPreference) =>
    request<DietPlan>("/diet/generate", {
      method: "POST",
      body: dietPreference ? { dietPreference } : {},
    }),

  /** GET /diet/current — the active plan, or a 404 if none exists yet. */
  current: () => request<DietPlan>("/diet/current"),

  /** GET /diet/history — the user's plans, newest first. */
  history: (page = 1, limit = 20): Promise<Paged<DietPlanSummary[]>> =>
    requestPaged<DietPlanSummary[]>("/diet/history", {
      query: { page, limit },
    }),

  /** GET /diet/{id} — one plan in full, including archived ones. */
  detail: (dietPlanId: string) =>
    request<DietPlan>(`/diet/${dietPlanId}`),
};

export const usersApi = {
  /** GET /users/profile — the body profile, or a 404 if not created. */
  profile: () => request<BodyProfile>("/users/profile"),

  /** PUT /users/profile — create or replace the body profile. */
  saveProfile: (input: ProfileInput) =>
    request<BodyProfile>("/users/profile", { method: "PUT", body: input }),
};

/**
 * Largest page the session history endpoint accepts.
 *
 * `contracts/exercises/` caps `limit` at 100, and asking for more is rejected
 * as a validation error rather than clamped. Declared here so callers cannot
 * guess a number the backend will refuse.
 */
export const MAX_SESSION_HISTORY = 100;

export const exercisesApi = {
  /** GET /exercises — the supported library. */
  list: () => request<ExerciseSummary[]>("/exercises"),

  /** GET /exercises/{slug} — full metadata for one exercise. */
  detail: (slug: string) => request<ExerciseDetail>(`/exercises/${slug}`),

  /** GET /exercises/history — past sessions, newest first. */
  history: (limit = 20) =>
    request<SessionSummary[]>("/exercises/history", { query: { limit } }),

  /** POST /exercises/start — open a live session. */
  start: (exerciseId: string, workoutId?: string) =>
    request<ExerciseSession>("/exercises/start", {
      method: "POST",
      body: { exerciseId, workoutId: workoutId ?? null },
    }),

  /** POST /exercises/frame — analyse one camera frame. */
  frame: (sessionId: string, landmarks: Landmark[], signal?: AbortSignal) =>
    request<FrameResult>("/exercises/frame", {
      method: "POST",
      body: { sessionId, landmarks },
      signal,
    }),

  /** POST /exercises/end — close a session. */
  end: (sessionId: string) =>
    request<SessionSummary>("/exercises/end", {
      method: "POST",
      body: { sessionId },
    }),

  /** GET /exercises/sessions/{id} — one session. */
  session: (sessionId: string) =>
    request<SessionSummary>(`/exercises/sessions/${sessionId}`),
};

export const workoutsApi = {
  /** POST /workouts/generate — generate and persist a plan. */
  generate: () =>
    request<WorkoutSummary>("/workouts/generate", { method: "POST", body: {} }),

  /** GET /workouts/current — the newest unarchived plan. */
  current: () => request<WorkoutDetail>("/workouts/current"),

  /** GET /workouts/history — the user's plans, paginated. */
  history: (page = 1, limit = 10): Promise<Paged<WorkoutSummary[]>> =>
    requestPaged<WorkoutSummary[]>("/workouts/history", {
      query: { page, limit },
    }),

  /** GET /workouts/{id} — one plan with its exercises. */
  detail: (workoutId: string) =>
    request<WorkoutDetail>(`/workouts/${workoutId}`),

  /** DELETE /workouts/{id} — remove a plan. */
  remove: (workoutId: string) =>
    request<null>(`/workouts/${workoutId}`, { method: "DELETE" }),
};

export const progressApi = {
  /** GET /progress — streaks and lifetime totals. */
  progress: () => request<Progress>("/progress"),

  /** GET /progress/dashboard — everything the dashboard shows. */
  dashboard: () => request<Dashboard>("/progress/dashboard"),

  /** GET /progress/statistics — aggregated training statistics. */
  statistics: () => request<Statistics>("/progress/statistics"),
};

export const aiApi = {
  /** POST /ai/chat — send a message to the assistant. */
  chat: (conversationId: string, message: string) =>
    request<ChatReply>("/ai/chat", {
      method: "POST",
      body: { conversationId, message },
    }),

  /** POST /ai/explain — explain one exercise. */
  explain: (exerciseId: string) =>
    request<ExerciseExplanation>("/ai/explain", {
      method: "POST",
      body: { exerciseId },
    }),

  /** POST /ai/review — review a completed workout. */
  review: (workoutId: string) =>
    request<WorkoutReview>("/ai/review", {
      method: "POST",
      body: { workoutId },
    }),
};
