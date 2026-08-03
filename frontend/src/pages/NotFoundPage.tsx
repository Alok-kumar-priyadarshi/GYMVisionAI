/** Route fallback. */

import { Link } from "react-router-dom";

import { Button } from "@/components/ui";

export default function NotFoundPage() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="text-sm font-medium uppercase tracking-wide text-ink-muted">
        404
      </p>
      <h1 className="text-2xl font-semibold text-ink">Page not found</h1>
      <p className="max-w-sm text-sm text-ink-muted">
        That page does not exist. It may have moved, or the link may be wrong.
      </p>
      <Link to="/">
        <Button>Back to my workout</Button>
      </Link>
    </main>
  );
}
