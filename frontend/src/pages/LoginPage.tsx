/**
 * Sign-in page.
 *
 * `docs/09_security/47_SECURITY_ARCHITECTURE.md` section 5 makes Google OAuth
 * the only authentication method in Version 1.
 *
 * Google Identity Services is loaded from Google's script, which needs a client
 * ID. Without `VITE_GOOGLE_CLIENT_ID` the page says so plainly rather than
 * rendering a button that cannot work.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { Button, Card, Spinner } from "@/components/ui";
import { optional } from "@/config/env";
import { useAuth } from "@/contexts/AuthContext";
import { ApiError, NetworkError, TimeoutError } from "@/services/api/client";

const GOOGLE_CLIENT_ID = optional(import.meta.env.VITE_GOOGLE_CLIENT_ID);
const GOOGLE_SCRIPT_SRC = "https://accounts.google.com/gsi/client";

interface GoogleCredentialResponse {
  credential: string;
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: GoogleCredentialResponse) => void;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: Record<string, unknown>,
          ) => void;
        };
      };
    };
  }
}

/** How long to wait for Google's library before giving up. */
const SCRIPT_TIMEOUT_MS = 10_000;

/** Shared across mounts, so StrictMode's double effect loads the script once. */
let scriptPromise: Promise<void> | null = null;

/** True once Google's library has finished initialising itself. */
function googleIsReady(): boolean {
  return Boolean(window.google?.accounts?.id);
}

/**
 * Load Google Identity Services.
 *
 * Resolving on the presence of a `<script>` tag is not enough: the tag exists
 * the moment it is appended, long before `window.google` is defined. Under
 * StrictMode the effect runs twice, and the second run would otherwise resolve
 * instantly against a still-loading script and render no button at all.
 */
function loadGoogleScript(): Promise<void> {
  if (googleIsReady()) return Promise.resolve();
  if (scriptPromise) return scriptPromise;

  scriptPromise = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${GOOGLE_SCRIPT_SRC}"]`,
    );
    const script = existing ?? document.createElement("script");

    const fail = () => {
      // Allow a later attempt to retry rather than reusing a failed promise.
      scriptPromise = null;
      reject(new Error("Google Identity Services failed to load"));
    };

    script.addEventListener("load", () => resolve(), { once: true });
    script.addEventListener("error", fail, { once: true });

    if (!existing) {
      script.src = GOOGLE_SCRIPT_SRC;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }

    // A blocked request can hang without firing either event.
    setTimeout(() => {
      if (!googleIsReady()) fail();
    }, SCRIPT_TIMEOUT_MS);
  });

  return scriptPromise;
}

export default function LoginPage() {
  const { signIn } = useAuth();
  const buttonRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSigningIn, setSigningIn] = useState(false);
  const [scriptFailed, setScriptFailed] = useState(false);
  const [buttonReady, setButtonReady] = useState(false);

  const handleCredential = useCallback(
    async (response: GoogleCredentialResponse) => {
      setSigningIn(true);
      setError(null);

      try {
        // The client aborts the request on its own deadline. Racing a timer
        // here instead would report a failure while leaving the exchange
        // running, and signing the user in once it finally answered.
        await signIn(response.credential);
      } catch (cause) {
        if (
          cause instanceof NetworkError ||
          cause instanceof TimeoutError ||
          cause instanceof ApiError
        ) {
          setError(cause.message);
        } else {
          setError(
            "Sign-in did not complete. Check that the backend is running, then try again.",
          );
        }
        setSigningIn(false);
      }
    },
    [signIn],
  );

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;

    let cancelled = false;

    loadGoogleScript()
      .then(() => {
        if (cancelled) return;

        // Never fall through silently: a blank card with no explanation is the
        // worst possible outcome here.
        if (!googleIsReady() || !buttonRef.current) {
          setScriptFailed(true);
          return;
        }

        window.google!.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (response) => void handleCredential(response),
        });
        window.google!.accounts.id.renderButton(buttonRef.current, {
          theme: "outline",
          size: "large",
          width: 280,
        });
        setButtonReady(true);
      })
      .catch(() => {
        if (!cancelled) setScriptFailed(true);
      });

    return () => {
      cancelled = true;
    };
  }, [handleCredential]);

  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-semibold tracking-tight text-ink">
            GymVision AI
          </h1>
          <p className="mt-2 text-sm text-ink-muted">
            Your camera-guided home trainer. Sign in to pick up where you left
            off.
          </p>
        </div>

        <Card>
          {!GOOGLE_CLIENT_ID ? (
            <div role="alert" className="text-center">
              <p className="text-sm font-medium text-ink">Sign-in unavailable</p>
              <p className="mt-2 text-sm text-ink-muted">
                Google sign-in is not configured for this deployment. Set{" "}
                <code className="rounded bg-surface-muted px-1 py-0.5 text-xs">
                  VITE_GOOGLE_CLIENT_ID
                </code>{" "}
                and reload.
              </p>
            </div>
          ) : scriptFailed ? (
            <div role="alert" className="text-center">
              <p className="text-sm font-medium text-ink">
                Google sign-in could not load
              </p>
              <p className="mt-2 text-sm text-ink-muted">
                Check your connection, then reload the page.
              </p>
              <Button
                variant="secondary"
                className="mt-4"
                onClick={() => window.location.reload()}
              >
                Reload
              </Button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-4">
              <p className="text-sm text-ink-muted">
                Continue with your Google account
              </p>
              {/* Google renders its own button into this element. */}
              <div ref={buttonRef} />
              {!buttonReady && !isSigningIn && (
                <p className="flex items-center gap-2 text-sm text-ink-muted">
                  <Spinner size="sm" /> Loading Google sign-in…
                </p>
              )}
              {isSigningIn && (
                <p className="flex items-center gap-2 text-sm text-ink-muted">
                  <Spinner size="sm" /> Signing you in…
                </p>
              )}
            </div>
          )}

          {error && (
            <p role="alert" className="mt-4 text-center text-sm text-danger">
              {error}
            </p>
          )}
        </Card>

        <p className="mt-6 text-center text-xs text-ink-muted">
          GymVision gives educational fitness guidance. It is not medical advice.
        </p>
      </div>



    </main>
  );
}
