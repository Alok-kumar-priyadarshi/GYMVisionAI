# GymVision AI — Frontend

React client for the GymVision AI home trainer.

## Running it

```bash
npm install
cp .env.example .env.local     # fill in VITE_GOOGLE_CLIENT_ID
npm run dev                    # http://localhost:5173
```

The dev server proxies `/api` to `http://127.0.0.1:8000`, so run the backend
alongside it:

```bash
cd ../backend
.venv/Scripts/python -m uvicorn app.main:app --reload
```

| Script | Purpose |
|--------|---------|
| `npm run dev` | Dev server with hot reload |
| `npm run build` | Type-check and build for production |
| `npm test` | Run the test suite |
| `npm run typecheck` | Type-check only |
| `npm run lint` | Lint |

## Structure

Follows `docs/05_frontend/30_FRONTEND_ARCHITECTURE.md`.

```
src/
  components/ui/     Reusable presentational components
  components/layout/ Application shell
  contexts/          Global state (session only)
  hooks/             React Query hooks
  pages/             Route components
  router/            Routes and route guards
  services/api/      The only place that talks to the backend
  types/             API contract types
  test/              Test helpers
```

The dependency direction is one way: pages use hooks, hooks use services,
services use the client. A component never calls `fetch`, per
`instructions/03_FRONTEND_RULES.md` section 6.

## State

Per `docs/05_frontend/32_FRONTEND_STATE_ARCHITECTURE.md`:

- **Server state** — React Query. Never duplicated into Context.
- **Global state** — the session, and nothing else.
- **Local state** — `useState` inside the component that owns it.

## Decisions worth reviewing

### TypeScript rather than JavaScript

The stated stack says JavaScript, but `30_FRONTEND_ARCHITECTURE.md` section 4
specifies `App.tsx` and `index.ts`. Documentation wins, per `CLAUDE.md`
section 16, and it satisfies the type-safety requirement for frontend pages.

### Tokens are stored in `localStorage`

The auth contracts return tokens in the response body for the client to hold,
so they are stored in `localStorage`. That is readable by any script on the
origin. The stronger option is httpOnly cookies, which would require changing
`contracts/auth/01_GOOGLE_LOGIN.md` to set them server-side. Worth revisiting
before launch.

### react-router carries one advisory

`npm audit` reports a high-severity advisory against react-router 7.12–8.2:
**RSC Mode CSRF Bypass**. It applies to React Router's RSC mode, which this app
does not use — routing is client-side with no server actions. Downgrading to
7.11 exposes fourteen worse advisories, and no 8.x is published. The current
version is the safest available; re-check when 8.x ships.

## Not yet built

**The live camera session.** `docs/06_camera/33_CAMERA_ARCHITECTURE.md` and
`34_POSE_PROVIDER_ADAPTER.md` describe capturing frames, running MediaPipe Pose
in the browser and posting landmarks to `POST /api/v1/exercises/frame`. The
backend endpoint, the detectors and the API client are all ready; the browser
capture and pose overlay are not written.

This is the product's flagship feature and deserves its own pass.
