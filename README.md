# SupplyRisk

Open-source dependency risk scoring platform. This README is written for a
team where not everyone is deeply familiar with the stack — follow it in
order.

## What's already built (the shared foundation)

- Docker setup that runs Postgres + Redis + the backend together, identically
  on everyone's laptop
- The core database schema (packages, score_history, contributors,
  advisories, dependency_edges, watchlists)
- A minimal FastAPI backend that proves the whole stack is wired correctly
- Alembic migrations (the tool that creates/updates real tables from the
  schema)

## Part 1 — One-time setup (whoever is setting up the base project)

### 1. Install prerequisites
- **Git** — https://git-scm.com/downloads
- **Docker Desktop** — https://www.docker.com/products/docker-desktop
  (includes Docker Compose). Install it, open it once, make sure it says
  "Docker is running" before continuing.
- **VS Code** (or any editor) — https://code.visualstudio.com

You do NOT need to install Python, Postgres, or Redis on your own machine —
Docker handles all of that inside containers. This is deliberate: it means
every teammate has an identical environment with zero manual setup.

### 2. Create the GitHub repo
1. Go to github.com, click **New repository**.
2. Name it `supplyrisk`, keep it **Private** (final year project, keep it
   private until you're ready to show it publicly), do NOT initialize with a
   README (you already have one).
3. Create it.

### 3. Push this starter project to it
Open a terminal in this project folder and run:
```bash
git init
git add .
git commit -m "Initial project setup: Docker, schema, FastAPI skeleton"
git branch -M main
git remote add origin https://github.com/<your-username>/supplyrisk.git
git push -u origin main
```

### 4. Protect the main branch
On GitHub: **Settings → Branches → Add branch protection rule** → branch
name pattern `main` → check **"Require a pull request before merging"** →
Save. This means nobody (including you) can push straight to `main` — every
change goes through a reviewed Pull Request. This one setting prevents most
group-project disasters.

### 5. Create your real `.env` file
```bash
cp .env.example .env
```
Leave the values as they are for now — they're already correct for the
Docker setup. Never commit `.env` (it's already in `.gitignore`).

### 6. Start everything
```bash
docker-compose up --build
```
First run takes a few minutes (downloading images, installing Python
packages). You'll see logs from three services: `supplyrisk_db`,
`supplyrisk_redis`, `supplyrisk_backend`.

### 7. Verify it's actually working
Open a browser:
- http://localhost:8000/health → should show `{"status":"ok"}`
- http://localhost:8000/health/db → should show
  `{"status":"ok","database":"connected"}`
- http://localhost:8000/docs → FastAPI's automatic interactive API docs —
  bookmark this, you'll use it constantly

If `/health/db` fails, wait 10 seconds and refresh — Postgres can take a
moment to finish starting on the very first run.

### 8. Create the actual database tables
The schema (models.py) exists in code, but the tables don't exist in
Postgres yet — Alembic creates them. In a **new terminal** (leave
`docker-compose up` running in the first one):
```bash
docker exec -it supplyrisk_backend alembic revision --autogenerate -m "initial schema"
docker exec -it supplyrisk_backend alembic upgrade head
```
The first command generates a migration file by comparing your models to the
(currently empty) database. The second actually creates the tables.

Verify it worked:
```bash
docker exec -it supplyrisk_db psql -U supplyrisk -d supplyrisk -c "\dt"
```
You should see all 6 tables listed (packages, score_history, contributors,
advisories, dependency_edges, watchlists).

### 9. Commit the migration file
Alembic just generated a new file under `backend/alembic/versions/`. Commit
it:
```bash
git add backend/alembic/versions/
git commit -m "Add initial schema migration"
git push
```
This migration file is what lets every teammate build the exact same tables
on their own machine automatically — nobody manually creates tables by hand.

**Base setup is done at this point.** Everything below is for your
teammates.

## Part 2 — Adding teammates

### On GitHub
**Settings → Collaborators → Add people** → add each teammate by username or
email.

### What each teammate does (send them this)
```bash
git clone https://github.com/<your-username>/supplyrisk.git
cd supplyrisk
cp .env.example .env
docker-compose up --build
docker exec -it supplyrisk_backend alembic upgrade head
```
That last command applies the migration you already committed — it builds
their tables to match yours automatically. They should then be able to hit
http://localhost:8000/docs and see the same thing you see.

### Daily workflow for everyone, going forward
```bash
git checkout main
git pull                                  # get latest changes
git checkout -b feature/whatever-you-are-building
# ... do work ...
git add .
git commit -m "clear description of what changed"
git push -u origin feature/whatever-you-are-building
```
Then open a Pull Request on GitHub, get at least one teammate to review and
approve, then merge. Never work directly on `main`.

## Part 3 — Who builds what next

| Person | Owns | Builds on top of |
|---|---|---|
| **A** | Scoring engine + DB schema evolution (bus factor, churn, advisory-gap formulas; partitioning `score_history`; the recursive-CTE dependency-tree query) | `models.py`, Postgres |
| **B** | Crawlers + ingestion pipeline (GitHub/npm/PyPI APIs, Celery scheduled jobs, Redis caching) | `config.py` (add `GITHUB_TOKEN`), new `app/crawlers/` folder |
| **C** | Backend API + auth + deployment (real endpoints beyond the placeholder ones, JWT auth, Render/Railway/Supabase deployment) | `main.py`, new `app/routers/` folder |
| **D** | Browser extension + dashboard (React dashboard hitting this API, Manifest V3 extension) | New top-level `frontend/` and `extension/` folders — doesn't touch backend code |

Whoever does this base setup naturally has the deepest early understanding
of the schema — that's usually a good fit for **Person A (scoring engine)**
or **Person C (backend/API)**, since you'll already be comfortable in this
codebase. Pick based on who's more interested in "the math/logic" (→ A) vs.
"building endpoints and shipping it live" (→ C).

## Quick troubleshooting
- **Port already in use (5432 or 8000):** something else on your machine is
  using that port. Either stop it, or change the left-hand number in
  `docker-compose.yml`'s `ports:` section (e.g. `"5433:5432"`).
- **`.env` not found error:** you skipped step 5 — run `cp .env.example .env`.
- **Changes to Python code not showing up:** the backend runs with
  `--reload`, so it should auto-restart — if not, `docker-compose restart backend`.
- **Totally stuck / want a clean slate:** `docker-compose down -v` (this
  deletes the database data too — only use it if you're okay losing local
  test data).
