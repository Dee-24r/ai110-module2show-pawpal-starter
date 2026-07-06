# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:

```
===== Today's Schedule (Saturday, July 04, 2026) =====
  [ ] 07:30  Morning walk (dog, 30 min, daily)
  [ ] 09:00  Give allergy meds (cat, 5 min, daily)
  [ ] 18:00  Evening feeding (cat, 15 min, daily)
===============================================

...marked 'Morning walk' as completed...

===== Today's Schedule (Saturday, July 04, 2026) =====
  [x] 07:30  Morning walk (dog, 30 min, daily)
  [ ] 09:00  Give allergy meds (cat, 5 min, daily)
  [ ] 18:00  Evening feeding (cat, 15 min, daily)
===============================================
```

```
# e.g.:
# Daily plan for Biscuit (Golden Retriever):
#   08:00 — Morning walk (30 min) [priority: high]
#   09:00 — Feeding (10 min) [priority: high]
#   ...
```

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
# Paste your pytest output here
```

## 📐 Smarter Scheduling

All scheduling logic lives in the `Scheduler` "brain" and the `Task` data class in
[`pawpal_system.py`](pawpal_system.py); the Streamlit UI (`app.py`) and CLI demo
(`main.py`) only call into them. The four core behaviors:

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| **Sorting** | `Scheduler.sort_by_time()`, `Scheduler.tasks_for_day()` | Orders tasks by time of day. |
| **Filtering** | `Scheduler.filter_tasks(pet_name=, completed=, day=)` | Filter by pet and/or completion status. |
| **Conflict detection** | `Scheduler.conflict_warning()`, `find_conflicts()`, `conflicts_on()` | Detects overlapping time slots across pets. |
| **Recurring tasks** | `Task.occurs_on()`, `Task.next_occurrence()`, `Scheduler.mark_as_completed()` | Daily / weekly / every-N-days repetition. |

### Sorting behavior
- **`Scheduler.sort_by_time(tasks=None)`** — returns a task list ordered earliest-first.
  `datetime.time` objects compare directly, so the key is simply `lambda t: t.time`
  (no `"HH:MM"` string parsing needed). O(n log n) via Python's stable sort.
- **`Scheduler.tasks_for_day(day)`** — a day's tasks as a timeline, sorted by
  `(time, -priority)` so that when two tasks share a time, the higher-`Priority`
  one (e.g. medication) sorts first.

### Filtering behavior
- **`Scheduler.filter_tasks(pet_name=None, completed=None, day=None)`** — each filter
  is optional; omit one to skip that check. Because completion is tracked per-day,
  the `completed` flag is evaluated with `Task.is_done_on(day)` (default: today).
  Composes with sorting, e.g. `sort_by_time(filter_tasks(pet_name="Rex"))`.

### Conflict detection logic
- **`Scheduler.conflict_warning(task)`** — the lightweight, non-crashing front door:
  returns a human-readable warning string, or `None` if the task is clear. Never
  raises and never blocks scheduling.
- **`Scheduler.find_conflicts(task)`** — the list of existing tasks that overlap,
  checked across **all** pets (the owner can't be in two places at once).
- **`Scheduler.conflicts_on(day)`** — audits a whole day for every overlapping pair
  using a sweep line (sort by start, keep only still-"open" tasks): O(n log n)
  instead of comparing all n² pairs.
- Underlying checks: `Task.overlaps()` → `_times_overlap()` (interval math on
  start + duration) and `_share_a_day()` (do the two ever land on the same date).
- **`Scheduler.find_free_slot(day, duration)`** — on a conflict, proposes the next
  open gap in the owner's waking window via an interval sweep.

### Recurring task logic
- **`Frequency`** enum: `ONCE`, `DAILY`, `WEEKLY`, `EVERY_N_DAYS` (with `Task.interval`
  and an optional `Task.end_date`).
- **`Task.occurs_on(day)`** — whether a recurring task lands on a given date;
  `EVERY_N_DAYS` uses modular arithmetic `(day - start).days % interval == 0`, and
  the check respects `date`/`end_date` bounds.
- **`Task.next_occurrence(after)`** — builds the next instance using
  `datetime.timedelta` (days=1 / weeks=1 / days=interval) so month/year rollovers
  are correct.
- **`Scheduler.mark_as_completed(id, day)`** — completing a recurring task
  auto-spawns its next occurrence and caps the finished one (`end_date`) so the
  schedule shows exactly one instance per day; idempotent so it never duplicates.

### Bonus owner-facing helpers
| Feature | Method(s) |
|---------|-----------|
| Priority ordering | `Priority` enum + tie-break in `tasks_for_day()` |
| Attribute-driven task suggestions | `Scheduler.suggest_tasks(pet)` |
| Per-day completion / undo | `Task.completed_on`, `Task.is_done_on()`, `mark_as_incomplete()` |
| "Next up" / overdue / workload | `Scheduler.next_task()`, `overdue_tasks()`, `daily_load()` |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
