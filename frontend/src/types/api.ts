/**
 * Types mirroring the backend API contracts.
 *
 * Field names are camelCase because `contracts/common/02_RESPONSE_FORMAT.md`
 * section 12 requires it. These types are the frontend's copy of the contract:
 * if the backend changes shape, this file changes with it.
 */

/** Envelope returned by every successful request. */
export interface SuccessEnvelope<T> {
  success: true;
  message: string;
  data: T;
  pagination?: Pagination;
}

/** Envelope returned by every failed request. */
export interface ErrorEnvelope {
  success: false;
  error: { code: string; message: string };
}

export interface Pagination {
  page: number;
  limit: number;
  total: number;
  pages: number;
}

// --- Authentication --------------------------------------------------------

export interface User {
  id: string;
  name: string;
  email: string;
  picture: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface LoginResult {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  user: User;
}

export interface AccessTokenResult {
  accessToken: string;
  expiresIn: number;
}

// --- Users -----------------------------------------------------------------

export type FitnessGoal = "Weight Loss" | "Muscle Gain" | "General Fitness";
export type FitnessLevel = "Beginner" | "Intermediate" | "Advanced";
export type Gender = "Male" | "Female" | "Other" | "Prefer not to say";

export interface BodyProfile {
  id: string;
  age: number;
  gender: Gender;
  heightCm: number;
  weightKg: number;
  fitnessGoal: FitnessGoal;
  fitnessLevel: FitnessLevel;
  problemAreas: string[];
  workoutDurationMinutes: number;
  bodyType: string | null;
  bmi: number;
}

export interface ProfileInput {
  age: number;
  gender: Gender;
  heightCm: number;
  weightKg: number;
  fitnessGoal: FitnessGoal;
  fitnessLevel: FitnessLevel;
  problemAreas: string[];
  workoutDurationMinutes: number;
}

// --- Exercises -------------------------------------------------------------

export type ExerciseType = "Repetition" | "Duration";

export interface ExerciseSummary {
  exerciseId: string;
  name: string;
  category: string;
  difficulty: string;
  exerciseType: ExerciseType;
  detectorAvailable: boolean;
}

export interface ExerciseDetail extends ExerciseSummary {
  equipment: string[];
  primaryMuscles: string[];
  secondaryMuscles: string[];
  instructions: string[];
  movementType: string;
}

export interface ExerciseSession {
  sessionId: string;
  workoutId: string | null;
  exerciseId: string;
  exerciseName: string;
  status: string;
  startedAt: string;
}

export interface SessionSummary {
  sessionId: string;
  exerciseId: string;
  status: string;
  totalReps: number;
  durationSeconds: number;
  averageAccuracy: number | null;
  startedAt: string;
  completedAt: string | null;
}

/** One MediaPipe pose landmark, as the frame endpoint expects it. */
export interface Landmark {
  x: number;
  y: number;
  z: number;
  visibility: number;
}

export interface FrameResult {
  sessionId: string;
  exerciseId: string;
  reps: number;
  stage: string | null;
  feedback: string[];
  metrics: Record<string, unknown>;
}

// --- Workouts --------------------------------------------------------------

export interface WorkoutSummary {
  /** True when generation returned the plan the user already had. */
  unchanged?: boolean;
  workoutId: string;
  name: string;
  difficulty: string;
  goal: string;
  estimatedDurationMinutes: number;
  exerciseCount: number;
  createdAt: string;
}

export interface WorkoutExercise {
  exerciseId: string;
  slug: string;
  name: string;
  displayOrder: number;
  sets: number;
  repetitions: number;
  holdSeconds: number;
  restSeconds: number;
}

export interface WorkoutDetail extends WorkoutSummary {
  exercises: WorkoutExercise[];
}

// --- Progress --------------------------------------------------------------

export interface Progress {
  currentStreak: number;
  longestStreak: number;
  totalWorkouts: number;
  totalExercises: number;
  totalMinutes: number;
  averageWorkoutMinutes: number;
  lastWorkoutDate: string | null;
}

export interface Dashboard {
  user: User;
  progress: Progress;
  currentWorkout: WorkoutSummary | null;
  hasProfile: boolean;
}

export interface Statistics {
  totalWorkouts: number;
  totalExercises: number;
  totalMinutes: number;
  averageWorkoutMinutes: number;
  completedSessions: number;
  totalReps: number;
}

// --- AI --------------------------------------------------------------------

export interface ChatReply {
  conversationId: string;
  response: string;
  createdAt: string;
}

export interface ExerciseExplanation {
  exerciseId: string;
  title: string;
  explanation: string;
}

export interface WorkoutReview {
  workoutId: string;
  summary: string;
  strengths: string[];
  improvements: string[];
  motivation: string;
}

// --- Diet ------------------------------------------------------------------

/** One food and how much of it to eat. Nutrition is for the portion as served. */
export interface MealItem {
  foodId: string;
  slug: string;
  name: string;
  category: string;
  servings: number;
  servingSize: string;
  calories: number;
  proteinG: number;
  carbohydratesG: number;
  fatG: number;
}

export interface Meal {
  mealId: string;
  mealType: string;
  displayOrder: number;
  name: string;
  targetCalories: number;
  items: MealItem[];
}

export interface DietTotals {
  calories: number;
  proteinG: number;
  carbohydratesG: number;
  fatG: number;
}

/** A stored plan without its meals, as the history list returns it. */
export interface DietPlanSummary {
  dietPlanId: string;
  goal: string;
  dietPreference: string;
  estimatedCalories: number;
  waterTargetMl: number;
  status: string;
  mealCount: number;
  createdAt: string;
}

export interface DietPlan extends DietPlanSummary {
  meals: Meal[];
  totals: DietTotals;
}

/** The dietary preferences the food catalog supports. */
export type DietPreference = "Vegan" | "Vegetarian" | "Non Vegetarian";
