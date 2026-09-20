# Scoring Engine — Phase 1, independent work

Everything in this folder (plus `tests/test_scoring.py` and
`scripts/seed_fake_data.py`) can be built, run, and fully trusted **without
waiting on B, C, or D**. This README says exactly what's independent, what
isn't, and what to double check once B's real data shows up.

## What's 100% independent (no teammate needed)

| File                    | Depends on                                  |
| ----------------------- | ------------------------------------------- |
| `config.py`             | Nothing                                     |
| `signals.py`            | Nothing — pure functions, plain data in/out |
| `formula.py`            | Nothing — pure calculation, no DB           |
| `tests/test_scoring.py` | Nothing — hand-written synthetic data       |

You can write, run, and pass all of these today, in Week 1–2, with zero
teammates having done anything yet.

## What needs the database (but NOT B's real crawlers)

| File                        | Depends on                                                                                                         |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `write_score.py`            | A running Postgres with the `score_history` table (already exists from Initial Setup — Alembic already created it) |
| `scripts/seed_fake_data.py` | Same — just your own local Docker Postgres, running your own made-up test packages                                 |

This is the key point: your local Postgres already has the real
`score_history`, `packages`, `contributors`, and `advisories` tables (from
the Alembic migration you already ran). You don't need B's _code_ to have
rows in those tables — `seed_fake_data.py` puts believable fake rows in
yourself, so you can run the entire pipeline (fake stats → `compute_score`
→ `write_score_history` → real row in Postgres) completely solo.

## What genuinely has to wait for B (Week 3–4)

Nothing in _this_ folder waits on B. What waits on B is the step _after_
this: writing the query that turns B's real `contributors` / `advisories`
rows into a `PackageRawStats` object. That's a small, separate piece
(a handful of SQL queries or ORM calls) you'll add once B's real seed
dataset lands — the formula and signal logic you build now don't change at
all when that happens.

## How to run everything today

```bash
# 1. Run the unit tests (no DB needed)
docker exec -it supplyrisk_backend pytest tests/test_scoring.py -v

# 2. Seed fake data + run the real pipeline end-to-end against your local DB
docker exec -it supplyrisk_backend python scripts/seed_fake_data.py
```

## Before you trust this against the real schema

`write_score.py` and `seed_fake_data.py` both **guess** at exact column
names (`package_id`, `score`, `breakdown`, `computed_at` on `score_history`;
`name`, `registry` on `packages`). Open `backend/app/models.py`, check the
real column names, and adjust both files if anything doesn't match —
they're written so that's a one-place, few-line fix, not a rewrite.

## Once B's real data exists (Week 3)

1. Write a small function (new file, e.g. `build_stats.py`) that queries
   the real `contributors` / `advisories` tables for one package and builds
   a `PackageRawStats` object from real rows — this replaces
   `build_healthy_stats()` / `build_abandoned_stats()` from the seed script.
2. Everything downstream (`compute_score`, `write_score_history`) is
   already done and already tested — nothing there needs to change.
