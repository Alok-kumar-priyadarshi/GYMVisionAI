/**
 * React Query hooks.
 *
 * `docs/05_frontend/32_FRONTEND_STATE_ARCHITECTURE.md` section 5 makes React
 * Query the owner of all server state and forbids duplicating it in Context.
 *
 * Query keys are declared once so an invalidation can never miss a cache entry
 * through a typo.
 */

import { useCallback } from "react";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { ApiError } from "@/services/api/client";
import {
  aiApi,
  dietApi,
  exercisesApi,
  progressApi,
  usersApi,
  workoutsApi,
} from "@/services/api/endpoints";
import type { DietPreference, ProfileInput } from "@/types/api";

export const queryKeys = {
  profile: ["profile"] as const,
  exercises: ["exercises"] as const,
  exercise: (slug: string) => ["exercises", slug] as const,
  exerciseHistory: (limit: number) => ["exercises", "history", limit] as const,
  currentWorkout: ["workouts", "current"] as const,
  workoutHistory: (page: number) => ["workouts", "history", page] as const,
  workout: (id: string) => ["workouts", id] as const,
  dashboard: ["progress", "dashboard"] as const,
  progress: ["progress"] as const,
  statistics: ["progress", "statistics"] as const,
  explanation: (slug: string) => ["ai", "explain", slug] as const,
  currentDiet: ["diet", "current"] as const,
  dietHistory: (page: number) => ["diet", "history", page] as const,
  dietPlan: (id: string) => ["diet", id] as const,
};

/** Treat a documented "not found" as an empty result rather than an error. */
function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

export function useProgress() {
  return useQuery({ queryKey: queryKeys.progress, queryFn: progressApi.progress });
}

export function useStatistics() {
  return useQuery({
    queryKey: queryKeys.statistics,
    queryFn: progressApi.statistics,
  });
}

export function useExercises() {
  return useQuery({
    queryKey: queryKeys.exercises,
    queryFn: exercisesApi.list,
    // The library is seeded from configuration and changes only on deploy.
    staleTime: 60 * 60 * 1000,
  });
}

export function useExercise(slug: string) {
  return useQuery({
    queryKey: queryKeys.exercise(slug),
    queryFn: () => exercisesApi.detail(slug),
    staleTime: 60 * 60 * 1000,
    enabled: Boolean(slug),
  });
}

export function useExerciseHistory(limit = 20) {
  return useQuery({
    queryKey: queryKeys.exerciseHistory(limit),
    queryFn: () => exercisesApi.history(limit),
  });
}

/**
 * Refresh everything a finished exercise session changes.
 *
 * The session is recorded by the backend, so the caches holding the old view
 * of it have to be dropped: the workout page derives its completed marks from
 * history, and both progress views count the session.
 *
 * Prefixes are invalidated rather than exact keys, so every cached page size
 * is covered without listing them.
 */
export function useSessionRecorded() {
  const queryClient = useQueryClient();

  return useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["exercises", "history"] });
    void queryClient.invalidateQueries({ queryKey: queryKeys.progress });
  }, [queryClient]);
}

export function useProfile(
  options?: Partial<UseQueryOptions<Awaited<ReturnType<typeof usersApi.profile>>>>,
) {
  return useQuery({
    queryKey: queryKeys.profile,
    queryFn: usersApi.profile,
    retry: (failureCount, error) => !isNotFound(error) && failureCount < 2,
    ...options,
  });
}

export function useSaveProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: ProfileInput) => usersApi.saveProfile(input),
    onSuccess: (saved) => {
      // The response is the saved profile, so the cache is seeded directly.
      // Invalidating instead would refetch, and a user creating their first
      // profile would see the page flip back to a loading state.
      queryClient.setQueryData(queryKeys.profile, saved);
      // `/progress/dashboard` still reports whether a profile exists.
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
  });
}

export function useCurrentWorkout() {
  return useQuery({
    queryKey: queryKeys.currentWorkout,
    queryFn: workoutsApi.current,
    retry: (failureCount, error) => !isNotFound(error) && failureCount < 2,
  });
}

export function useWorkoutHistory(page: number) {
  return useQuery({
    queryKey: queryKeys.workoutHistory(page),
    queryFn: () => workoutsApi.history(page),
  });
}

export function useWorkout(workoutId: string | null) {
  return useQuery({
    queryKey: queryKeys.workout(workoutId ?? ""),
    queryFn: () => workoutsApi.detail(workoutId!),
    enabled: Boolean(workoutId),
    // A past plan is fixed, so it is worth keeping for the session.
    staleTime: Infinity,
  });
}

export function useGenerateWorkout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: workoutsApi.generate,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workouts"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
  });
}

export function useDeleteWorkout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (workoutId: string) => workoutsApi.remove(workoutId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workouts"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
  });
}

export function useCurrentDiet() {
  return useQuery({
    queryKey: queryKeys.currentDiet,
    queryFn: dietApi.current,
    // A 404 means "no plan yet", which is a normal state to be in.
    retry: (failureCount, error) => !isNotFound(error) && failureCount < 2,
  });
}

export function useDietHistory(page: number) {
  return useQuery({
    queryKey: queryKeys.dietHistory(page),
    queryFn: () => dietApi.history(page),
  });
}

export function useDietPlan(dietPlanId: string | null) {
  return useQuery({
    queryKey: queryKeys.dietPlan(dietPlanId ?? ""),
    queryFn: () => dietApi.detail(dietPlanId!),
    enabled: Boolean(dietPlanId),
    // An archived plan never changes, so it is worth keeping for the session.
    staleTime: Infinity,
  });
}

export function useGenerateDiet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (dietPreference?: DietPreference) =>
      dietApi.generate(dietPreference),
    onSuccess: (plan) => {
      // The response is the new plan, so the cache is seeded rather than
      // invalidated: refetching would flash a loading state over a page that
      // already has its answer.
      queryClient.setQueryData(queryKeys.currentDiet, plan);
      // History gained an entry and the previous plan became archived.
      void queryClient.invalidateQueries({ queryKey: ["diet", "history"] });
    },
  });
}

export function useExerciseExplanation(slug: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.explanation(slug),
    queryFn: () => aiApi.explain(slug),
    enabled: enabled && Boolean(slug),
    // Explanations cost a model call, so they are kept for the session.
    staleTime: Infinity,
    retry: false,
  });
}

export function useChat() {
  return useMutation({
    mutationFn: ({
      conversationId,
      message,
    }: {
      conversationId: string;
      message: string;
    }) => aiApi.chat(conversationId, message),
  });
}

export function useWorkoutReview() {
  return useMutation({
    mutationFn: (workoutId: string) => aiApi.review(workoutId),
  });
}
