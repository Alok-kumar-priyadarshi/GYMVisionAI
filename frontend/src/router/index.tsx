/**
 * Application routes.
 *
 * `instructions/03_FRONTEND_RULES.md` section 7 requires every route to be
 * documented and to use protected routes where necessary. Every route except
 * sign-in requires a session.
 *
 * Pages are lazily loaded, per section 11.
 */

import { Suspense, lazy } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { LoadingState } from "@/components/ui";
import { useAuth } from "@/contexts/AuthContext";

const LoginPage = lazy(() => import("@/pages/LoginPage"));
const WorkoutPage = lazy(() => import("@/pages/WorkoutPage"));
const DietPage = lazy(() => import("@/pages/DietPage"));
const ExercisesPage = lazy(() => import("@/pages/ExercisesPage"));
const ExerciseDetailPage = lazy(() => import("@/pages/ExerciseDetailPage"));
const LiveSessionPage = lazy(() => import("@/pages/LiveSessionPage"));
const ProgressPage = lazy(() => import("@/pages/ProgressPage"));
const CoachPage = lazy(() => import("@/pages/CoachPage"));
const ProfilePage = lazy(() => import("@/pages/ProfilePage"));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage"));

/** Blocks a route until a session exists. */
function ProtectedRoute() {
  const { isAuthenticated, isRestoring } = useAuth();

  // Waiting for the stored session to be verified. Redirecting here would
  // bounce a signed-in user to the login screen on every refresh.
  if (isRestoring) return <LoadingState label="Restoring your session" />;

  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}

/** Keeps a signed-in user away from the login screen. */
function PublicOnlyRoute() {
  const { isAuthenticated, isRestoring } = useAuth();

  if (isRestoring) return <LoadingState label="Restoring your session" />;

  return isAuthenticated ? <Navigate to="/" replace /> : <Outlet />;
}

export function AppRoutes() {
  return (
    <Suspense fallback={<LoadingState />}>
      <Routes>
        <Route element={<PublicOnlyRoute />}>
          <Route path="/login" element={<LoginPage />} />
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            {/* Workout is the landing page: the dashboard summarised other
                pages without being any of them, so it was removed. */}
            <Route index element={<Navigate to="/workout" replace />} />
            <Route path="workout" element={<WorkoutPage />} />
            <Route path="exercises" element={<ExercisesPage />} />
            <Route path="exercises/:slug" element={<ExerciseDetailPage />} />
            <Route path="exercises/:slug/live" element={<LiveSessionPage />} />
            <Route path="diet" element={<DietPage />} />
            <Route path="progress" element={<ProgressPage />} />
            <Route path="coach" element={<CoachPage />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}
