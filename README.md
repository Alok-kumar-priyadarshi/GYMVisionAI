# GymVision AI

A home fitness trainer that watches you through your webcam, counts your
repetitions, checks your form, builds your workouts and answers your questions.

Everything runs on free tiers. No gym equipment is required for any of the 29
supported exercises.

---

## What it does

- **Counts reps through the camera.** MediaPipe Pose runs in your browser and
  sends 33 body landmarks to the backend, where a dedicated detector per
  exercise counts repetitions, tracks holds and checks form. Video never leaves
  your device.
- **Builds your workout.** Deterministic generation from your body profile — no
  AI guesswork, and the same profile always produces the same plan.
- **Plans your meals.** A calorie target from your profile, portioned across
  five meals from a 36-item food library.
- **Coaches you.** An AI assistant explains exercises, reviews your workouts and
  answers fitness questions, grounded in your actual data.
- **Tracks your streak.** Daily streaks, lifetime totals and session history.

---

## Running it locally

You need **Python 3.11+** and **Node 20+**.

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements-dev.txt
cp .env.example .env
```

Open `.env` and set at least these two:

```ini
DATABASE_URL=sqlite+aiosqlite:///./gymvision.db
JWT_SECRET_KEY=<paste the output of the command below>
```

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Then create the database and start the API:

```bash
python -m app.cli bootstrap        # migrate + seed the 29 exercises and 36 foods
python -m app.cli check            # shows what is and is not configured
python -m uvicorn app.main:app --reload
```

The API is now on <http://127.0.0.1:8000>, with interactive docs at
<http://127.0.0.1:8000/docs> and health at `/health`.

> **SQLite is fine for local use.** Production uses PostgreSQL — set
> `DATABASE_URL` to a `postgresql+asyncpg://` URL and run
> `python -m app.cli bootstrap` again. See *Known limitations* below.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open <http://localhost:5173>.

### 3. Sign-in (required to use the app)

Every endpoint needs a signed-in user, and the only sign-in method is Google.
It is free and takes a few minutes:

1. Go to the [Google Cloud Console credentials page](https://console.cloud.google.com/apis/credentials).
2. Create an **OAuth client ID** of type **Web application**.
3. Add `http://localhost:5173` under **Authorised JavaScript origins**.
   This step is not optional. Without it Google renders the button but refuses
   the sign-in, logging `The given origin is not allowed for the given client
   ID` to the browser console. `localhost` and `127.0.0.1` count as different
   origins, and a trailing slash makes it a different origin again.
4. Copy the client ID and secret.

Put the client ID in **both** files, and the secret in the backend only:

```ini
# frontend/.env.local
VITE_GOOGLE_CLIENT_ID=<client id>

# backend/.env
GOOGLE_CLIENT_ID=<client id>
GOOGLE_CLIENT_SECRET=<client secret>
```

Restart both servers. Without this the login page tells you sign-in is not
configured rather than showing a button that cannot work.

If sign-in still fails, expand **Sign-in not working?** on the login page. It
shows the exact origin and client ID the browser is using, which are the two
values Google compares.

### 4. The AI coach (optional)

Get a free key from [Groq](https://console.groq.com/keys) and set
`GROQ_API_KEY` in `backend/.env`. Without it the rest of the app works normally
and the coach reports that it is unavailable.

---

## Running the tests

```bash
cd backend  && .venv/Scripts/python -m pytest      # 1049 tests
cd frontend && npm test                            # 68 tests
```

---

## How it is built

Documentation-first: `docs/`, `contracts/`, `contexts/`, `prompts/` and
`instructions/` are the source of truth, and the code implements them. Start
with [`CLAUDE.md`](CLAUDE.md), then [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for
current state, open decisions and known gaps.

```
backend/
  app/
    domain/           Entities, value objects, repository interfaces
    engines/          Detectors, exercise catalogue, workout, session, nutrition, AI
    application/      Services coordinating the engines
    infrastructure/   PostgreSQL, repositories, Google identity
    api/              FastAPI routers, error handling, health
  configuration/      Exercises, workouts, foods, diet rules, prompts (YAML)
  migrations/         Alembic

frontend/
  src/
    features/camera/  Pose adapter, camera lifecycle, live session
    services/api/     The only place that talks to the backend
    pages/            Route components
```

Dependencies point inward. The domain imports no framework, and a test enforces
that by parsing every module's imports.

**Business logic is deterministic, not AI.** Workout generation, rep counting,
form checks and calorie targets are all plain code. The AI explains and
motivates; it never decides.

---

## Known limitations

Recorded in full in [`PROJECT_STATUS.md`](PROJECT_STATUS.md). The ones that
matter most:

| Limitation | Effect |
|---|---|
| The schema has only been run against SQLite | Verify on PostgreSQL before deploying |
| Live detector state is held in the API process | The frame endpoint is sticky to one server instance |
| Conversation memory is in-process | Chat history is lost on restart |
| Logout does not revoke a token | A token stays valid until it expires |
| Four runtime engines are unbuilt | Blocked on a decision about where exercise thresholds live |
| No diet API contract exists | The diet engine works but is not exposed |

---

## Safety

GymVision gives educational fitness guidance. It is not medical advice, it does
not diagnose anything, and it should not replace a qualified professional. The
calorie and nutrition figures are conventional fitness estimates and have not
been reviewed by a dietitian.
