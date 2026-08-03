/**
 * Authentication state.
 *
 * `instructions/03_FRONTEND_RULES.md` section 5 limits global state to
 * authentication, theme, session and configuration. This provider owns exactly
 * the session; everything else is server state held by React Query.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ApiError, tokenStore } from "@/services/api/client";
import { authApi } from "@/services/api/endpoints";
import type { User } from "@/types/api";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  /** True until the stored session has been checked on first load. */
  isRestoring: boolean;
  signIn: (googleIdToken: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isRestoring, setRestoring] = useState(true);
  const queryClient = useQueryClient();

  // Restore the session on load: a stored token is only trustworthy if the
  // backend still accepts it, so it is verified rather than assumed.
  useEffect(() => {
    let cancelled = false;

    async function restore() {
      if (!tokenStore.access()) {
        if (!cancelled) setRestoring(false);
        return;
      }

      try {
        const current = await authApi.me();
        if (!cancelled) setUser(current);
      } catch (error) {
        if (error instanceof ApiError && error.isAuthError) {
          tokenStore.clear();
        }
      } finally {
        if (!cancelled) setRestoring(false);
      }
    }

    void restore();
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(
    async (googleIdToken: string) => {
      const result = await authApi.loginWithGoogle(googleIdToken);
      tokenStore.save(result.accessToken, result.refreshToken);
      setUser(result.user);
    },
    [],
  );

  const signOut = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Signing out locally must succeed even if the call fails.
    }
    tokenStore.clear();
    setUser(null);
    // Drop every cached response so the next user starts clean.
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo<AuthState>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isRestoring,
      signIn,
      signOut,
    }),
    [user, isRestoring, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Read the authentication state. */
export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used inside an AuthProvider");
  }
  return context;
}
