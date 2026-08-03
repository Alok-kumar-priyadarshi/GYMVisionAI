/**
 * Tests for the sign-in page.
 *
 * The regression that motivated these: under StrictMode the effect runs twice,
 * and a script loader that resolved on the presence of a `<script>` tag would
 * resolve the second time before Google's library had defined `window.google`.
 * The button was then never rendered, and nothing said why.
 */

import { StrictMode } from "react";
import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const SCRIPT_SRC = "https://accounts.google.com/gsi/client";

interface FakeGoogle {
  initialize: ReturnType<typeof vi.fn>;
  renderButton: ReturnType<typeof vi.fn>;
}

/**
 * Load the page and the render helper from one fresh module graph.
 *
 * The page caches its script promise at module scope, which is right in a
 * browser but would leak between tests. Resetting modules gives each test a
 * clean cache, and both imports must come from the same graph or the page's
 * `AuthContext` would not be the one the provider supplies.
 */
async function freshPage() {
  vi.resetModules();
  const [page, helpers] = await Promise.all([
    import("@/pages/LoginPage"),
    import("@/test/render"),
  ]);
  return { LoginPage: page.default, render: helpers.renderWithProviders };
}

function installGoogle(): FakeGoogle {
  const api: FakeGoogle = {
    initialize: vi.fn(),
    renderButton: vi.fn((parent: HTMLElement) => {
      parent.appendChild(document.createElement("iframe"));
    }),
  };
  (window as unknown as { google: unknown }).google = { accounts: { id: api } };
  return api;
}

function currentGoogle(): FakeGoogle {
  return (window as unknown as { google: { accounts: { id: FakeGoogle } } }).google
    .accounts.id;
}

/**
 * Behave like the real script: appending the tag does not define
 * `window.google`. That only happens when the load event fires.
 */
function serveScript({ succeed = true, defineGoogle = true } = {}) {
  const append = document.head.appendChild.bind(document.head);

  vi.spyOn(document.head, "appendChild").mockImplementation((node) => {
    const element = node as HTMLScriptElement;
    if (element.tagName === "SCRIPT" && element.src?.includes("gsi/client")) {
      setTimeout(() => {
        if (succeed) {
          if (defineGoogle) installGoogle();
          element.dispatchEvent(new Event("load"));
        } else {
          element.dispatchEvent(new Event("error"));
        }
      }, 0);
    }
    return append(node);
  });
}

beforeEach(() => {
  vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com");
  delete (window as unknown as { google?: unknown }).google;
  document
    .querySelectorAll(`script[src="${SCRIPT_SRC}"]`)
    .forEach((node) => node.remove());
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("the sign-in page", () => {
  it("renders the Google button once the library has loaded", async () => {
    serveScript();
    const { LoginPage, render } = await freshPage();

    const { container } = render(<LoginPage />);

    await waitFor(() =>
      expect(container.querySelector("iframe")).toBeInTheDocument(),
    );
  });

  it("still renders the button when the effect runs twice", async () => {
    // The StrictMode case that produced a blank card with no explanation.
    serveScript();
    const { LoginPage, render } = await freshPage();

    const { container } = render(
      <StrictMode>
        <LoginPage />
      </StrictMode>,
    );

    await waitFor(() =>
      expect(container.querySelector("iframe")).toBeInTheDocument(),
    );
  });

  it("loads the script only once across both mounts", async () => {
    serveScript();
    const { LoginPage, render } = await freshPage();

    render(
      <StrictMode>
        <LoginPage />
      </StrictMode>,
    );

    await waitFor(() =>
      expect(
        document.querySelectorAll(`script[src="${SCRIPT_SRC}"]`),
      ).toHaveLength(1),
    );
  });

  it("shows a loading hint until the button appears", async () => {
    serveScript();
    const { LoginPage, render } = await freshPage();

    render(<LoginPage />);

    expect(screen.getByText(/loading google sign-in/i)).toBeInTheDocument();
  });

  it("explains itself when the script cannot load", async () => {
    serveScript({ succeed: false });
    const { LoginPage, render } = await freshPage();

    render(<LoginPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not load/i);
    expect(screen.getByRole("button", { name: /reload/i })).toBeInTheDocument();
  });

  it("explains itself when the script loads but defines nothing", async () => {
    // A blocker or extension can serve an empty script successfully.
    serveScript({ defineGoogle: false });
    const { LoginPage, render } = await freshPage();

    render(<LoginPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not load/i);
  });

  it("initialises Google with the configured client id", async () => {
    serveScript();
    const { LoginPage, render } = await freshPage();

    render(<LoginPage />);

    await waitFor(() =>
      expect(currentGoogle().initialize).toHaveBeenCalledWith(
        expect.objectContaining({
          client_id: "test-client.apps.googleusercontent.com",
        }),
      ),
    );
  });

  it("says so plainly when no client id is configured", async () => {
    vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "");
    const { LoginPage, render } = await freshPage();

    render(<LoginPage />);

    expect(screen.getByText(/sign-in unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/VITE_GOOGLE_CLIENT_ID/)).toBeInTheDocument();
  });
});

describe("sign-in troubleshooting", () => {
  it("shows the origin and client id Google must be told about", async () => {
    // Google reports the origin mismatch only to the console. The page repeats
    // both values so the fix does not require opening devtools.
    serveScript();
    const { LoginPage, render } = await freshPage();

    render(<LoginPage />);

    expect(screen.getByText(/sign-in not working/i)).toBeInTheDocument();
    expect(screen.getByText(window.location.origin)).toBeInTheDocument();
    expect(
      screen.getByText("test-client.apps.googleusercontent.com"),
    ).toBeInTheDocument();
  });

  it("is not shown when no client id is configured", async () => {
    vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "");
    const { LoginPage, render } = await freshPage();

    render(<LoginPage />);

    expect(screen.queryByText(/sign-in not working/i)).not.toBeInTheDocument();
  });
});
