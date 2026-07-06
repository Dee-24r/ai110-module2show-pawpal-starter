"""PawPal+ logic layer.

Backend classes for the PawPal+ scheduling app, built CLI-first so the
"brain" is verified before any UI. Responsibilities:

    Task      - a single activity (description, time, frequency, done?).
    Pet       - pet details plus its own list of tasks.
    Owner     - manages multiple pets and exposes all their tasks.
    Scheduler - retrieves, organizes, and manages tasks across all pets.
"""

import datetime
import itertools
from dataclasses import dataclass, field
from enum import Enum

# Auto-incrementing source of unique Task ids (1, 2, 3, ...).
_task_ids = itertools.count(1)


class Frequency(Enum):
    """How often a task repeats.

    ONCE is a one-off (unique) task; DAILY, WEEKLY, and EVERY_N_DAYS recur.
    EVERY_N_DAYS repeats every `Task.interval` days from the task's start date.
    """

    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    EVERY_N_DAYS = "every_n_days"


class Priority(Enum):
    """How urgent a task is; higher value sorts ahead when times tie.

    Used to float critical care (meds, health checks) above nice-to-haves
    when two tasks land at the same time of day.
    """

    LOW = 1
    NORMAL = 2
    HIGH = 3


@dataclass
class Task:
    """A single activity to perform for a pet, e.g. a walk or feeding.

    `date` is the anchor day: for a ONCE task it's the exact day it
    happens; for DAILY it's the start day (recurs every day after); for
    WEEKLY the recurrence lands on this date's weekday.
    """

    description: str
    date: datetime.date
    time: datetime.time
    duration: int  # minutes
    frequency: Frequency = Frequency.ONCE
    priority: Priority = Priority.NORMAL
    # For EVERY_N_DAYS: repeat every `interval` days from `date`.
    interval: int = 1
    # Optional last active day for a recurring task (None = runs forever).
    end_date: datetime.date | None = None
    # Days this task has been ticked off. A recurring task is done on some
    # days but not others, so completion is a set of dates, not one bool.
    completed_on: set[datetime.date] = field(default_factory=set)
    id: int = field(init=False, default_factory=lambda: next(_task_ids))

    def __post_init__(self) -> None:
        if self.interval < 1:
            raise ValueError("interval must be >= 1")

    @property
    def is_recurring(self) -> bool:
        """Whether this task repeats (i.e. is not a one-off)."""
        return self.frequency is not Frequency.ONCE

    def is_done_on(self, day: datetime.date) -> bool:
        """Whether this task was completed on the given day."""
        return day in self.completed_on

    def occurs_on(self, day: datetime.date) -> bool:
        """Whether this task happens on the given calendar day."""
        if day < self.date:
            return False
        if self.end_date is not None and day > self.end_date:
            return False
        if self.frequency is Frequency.ONCE:
            return day == self.date
        if self.frequency is Frequency.DAILY:
            return True
        if self.frequency is Frequency.WEEKLY:
            return day.weekday() == self.date.weekday()
        if self.frequency is Frequency.EVERY_N_DAYS:
            return (day - self.date).days % self.interval == 0
        return False

    def next_occurrence(self, after: datetime.date) -> "Task | None":
        """A fresh copy of this task scheduled for its next occurrence.

        `after` is the day it was just completed; the successor's date is that
        day plus one repeat step, computed with timedelta so month/year
        rollovers are handled correctly (e.g. Jul 31 -> Aug 1). Returns None
        for a one-off task, or when the recurrence has passed its end_date.
        """
        if self.frequency is Frequency.ONCE:
            return None
        if self.frequency is Frequency.DAILY:
            step = datetime.timedelta(days=1)
        elif self.frequency is Frequency.WEEKLY:
            step = datetime.timedelta(weeks=1)
        else:  # EVERY_N_DAYS
            step = datetime.timedelta(days=self.interval)

        next_date = after + step
        if self.end_date is not None and next_date > self.end_date:
            return None
        return Task(
            description=self.description,
            date=next_date,
            time=self.time,
            duration=self.duration,
            frequency=self.frequency,
            priority=self.priority,
            interval=self.interval,
            end_date=self.end_date,
        )

    def overlaps(self, other: "Task") -> bool:
        """Whether this and another task ever collide (same day + time)."""
        return _share_a_day(self, other) and _times_overlap(self, other)


@dataclass
class Pet:
    """A pet belonging to an owner; owns its own list of tasks."""

    name: str
    type: str
    gender: str
    height: float
    weight: float
    has_illness: bool = False
    takes_meds: bool = False
    retired: bool = False
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Attach a task to this pet."""
        self.tasks.append(task)

    def remove_task(self, task_id: int) -> None:
        """Remove one of this pet's tasks by id."""
        self.tasks = [t for t in self.tasks if t.id != task_id]

    def get_task(self, task_id: int) -> Task | None:
        """Look up one of this pet's tasks by id."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def retire(self) -> None:
        """Mark this pet as retired (task cleanup is done by Owner.retire_pet)."""
        self.retired = True


class Owner:
    """The app user; manages pets and exposes all of their tasks."""

    def __init__(self, name: str, occupation: str) -> None:
        """Create an owner with no pets yet."""
        self.name = name
        self.occupation = occupation
        self.pets: list[Pet] = []

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        self.pets.append(pet)

    def retire_pet(self, pet: Pet) -> None:
        """Retire a pet and drop its scheduled tasks so it stops reminding."""
        pet.retire()
        pet.tasks.clear()

    def all_tasks(self) -> list[Task]:
        """Every task across every pet, flattened into one list."""
        return [task for pet in self.pets for task in pet.tasks]

    def pet_of(self, task_id: int) -> Pet | None:
        """Which pet owns a given task (handy for display)."""
        for pet in self.pets:
            if pet.get_task(task_id) is not None:
                return pet
        return None


class Scheduler:
    """The brain: retrieves, organizes, and manages tasks across all pets.

    It operates on a single Owner rather than storing tasks itself, so the
    Owner's pets remain the single source of truth.
    """

    def __init__(self, owner: Owner) -> None:
        """Create a scheduler that operates over the given owner's pets."""
        self.owner = owner

    def all_tasks(self) -> list[Task]:
        """All tasks across the owner's pets (delegates to the Owner)."""
        return self.owner.all_tasks()

    def schedule_task(self, pet: Pet, task: Task) -> list[Task]:
        """Attach a task to a pet, returning any conflicting tasks.

        The task is added regardless; the returned list lets the caller warn
        the user ("this overlaps with Rex's walk - schedule anyway?"). An
        empty list means no conflict. Conflicts are checked across ALL pets,
        since the owner is one person who can't be in two places at once.
        """
        conflicts = self.find_conflicts(task)
        pet.add_task(task)
        return conflicts

    def find_conflicts(self, task: Task) -> list[Task]:
        """Existing tasks (any pet) that overlap the given task in day + time."""
        return [
            other
            for other in self.all_tasks()
            if other.id != task.id and task.overlaps(other)
        ]

    def conflict_warning(self, task: Task) -> str | None:
        """A human-readable warning if `task` clashes, else None.

        Lightweight and non-fatal: it never raises and never blocks scheduling,
        it just reports. Conflicts are checked across ALL pets (the owner can't
        be in two places at once), naming each clashing task, its time, and pet.
        """
        conflicts = self.find_conflicts(task)
        if not conflicts:
            return None
        clashes = ", ".join(
            f"{c.description} at {c.time:%H:%M}"
            + (f" ({p.name})" if (p := self.owner.pet_of(c.id)) is not None else "")
            for c in conflicts
        )
        return (
            f"Conflict: '{task.description}' at {task.time:%H:%M} "
            f"overlaps with {clashes}."
        )

    def tasks_for_day(self, day: datetime.date) -> list[Task]:
        """All tasks occurring on the given day.

        Ordered chronologically so it reads like a timeline; ties at the same
        time break by priority (HIGH first) so critical care isn't buried.
        """
        due = [t for t in self.all_tasks() if t.occurs_on(day)]
        return sorted(due, key=lambda t: (t.time, -t.priority.value))

    def sort_by_time(self, tasks: list[Task] | None = None) -> list[Task]:
        """Return tasks ordered by time of day (earliest first).

        Defaults to every task across all pets. `datetime.time` objects compare
        directly, so the key lambda (`lambda t: t.time`) needs no parsing.
        Runs in O(n log n) via Python's stable Timsort.
        """
        tasks = self.all_tasks() if tasks is None else tasks
        return sorted(tasks, key=lambda t: t.time)

    def filter_tasks(
        self,
        pet_name: str | None = None,
        completed: bool | None = None,
        day: datetime.date | None = None,
    ) -> list[Task]:
        """Tasks filtered by owning pet and/or completion status.

        Each filter is optional; omitting one skips that check. Completion is
        per-day, so `completed` is evaluated against `day` (default: today).
        """
        day = day or datetime.date.today()
        tasks = self.all_tasks()
        if pet_name is not None:
            tasks = [
                t
                for t in tasks
                if (p := self.owner.pet_of(t.id)) is not None and p.name == pet_name
            ]
        if completed is not None:
            tasks = [t for t in tasks if t.is_done_on(day) == completed]
        return tasks

    def find_free_slot(
        self,
        day: datetime.date,
        duration: int,
        day_start: datetime.time = datetime.time(7, 0),
        day_end: datetime.time = datetime.time(22, 0),
    ) -> datetime.time | None:
        """First start time on `day` where a `duration`-minute task fits.

        Sweeps that day's existing tasks in order and returns the earliest gap
        (within the owner's waking window) big enough to hold the new task, or
        None if the day is too full.
        """
        cursor = _to_minutes(day_start)
        end = _to_minutes(day_end)
        busy = sorted(
            (_to_minutes(t.time), _to_minutes(t.time) + t.duration)
            for t in self.tasks_for_day(day)
        )
        for busy_start, busy_end in busy:
            if busy_start - cursor >= duration:
                return _from_minutes(cursor)
            cursor = max(cursor, busy_end)
        if end - cursor >= duration:
            return _from_minutes(cursor)
        return None

    def suggest_tasks(
        self, pet: Pet, start: datetime.date | None = None
    ) -> list[Task]:
        """Propose a starter care routine derived from a pet's attributes.

        Turns the pet's flags into concrete daily tasks (a retired pet needs
        none, a dog needs a walk, meds/illness raise a HIGH-priority reminder)
        so the owner isn't hand-authoring every routine task. Returns unsaved
        Tasks; the caller decides which to schedule.
        """
        if pet.retired:
            return []

        day = start or datetime.date.today()
        suggestions = [
            Task("Morning feeding", day, datetime.time(8, 0), 15, Frequency.DAILY),
        ]
        if pet.type == "dog":
            suggestions.append(
                Task("Daily walk", day, datetime.time(7, 30), 30, Frequency.DAILY)
            )
        if pet.takes_meds:
            suggestions.append(
                Task(
                    "Give medication",
                    day,
                    datetime.time(9, 0),
                    5,
                    Frequency.DAILY,
                    Priority.HIGH,
                )
            )
        if pet.has_illness:
            suggestions.append(
                Task(
                    "Health check-in",
                    day,
                    datetime.time(19, 0),
                    10,
                    Frequency.DAILY,
                    Priority.HIGH,
                )
            )
        return suggestions

    def tasks_for_today(self) -> list[Task]:
        """All tasks occurring today, sorted by time."""
        return self.tasks_for_day(datetime.date.today())

    def get_task(self, task_id: int) -> Task | None:
        """Look up a single task by id across all pets."""
        for task in self.all_tasks():
            if task.id == task_id:
                return task
        return None

    def mark_as_completed(
        self, task_id: int, day: datetime.date | None = None
    ) -> Task | None:
        """Mark a task done for a day (default today); roll recurring ones over.

        Completing a DAILY/WEEKLY/EVERY_N_DAYS task auto-creates its next
        occurrence (via Task.next_occurrence) and caps the finished instance at
        `day` so the schedule still shows exactly one instance per calendar day.
        Returns the newly spawned successor task, or None if nothing was spawned
        (one-off task, ended recurrence, or a successor already exists).
        """
        day = day or datetime.date.today()
        task = self.get_task(task_id)
        if task is None:
            return None
        task.completed_on.add(day)
        if not task.is_recurring:
            return None

        upcoming = task.next_occurrence(day)
        if upcoming is None:
            return None
        pet = self.owner.pet_of(task.id)
        if pet is None:
            return None
        # Idempotent: don't spawn a duplicate if the successor already exists
        # (e.g. the same task gets completed twice, or toggled in the UI).
        if any(
            t.description == upcoming.description and t.date == upcoming.date
            for t in pet.tasks
        ):
            return None
        task.end_date = day  # the finished instance stops recurring here
        pet.add_task(upcoming)
        return upcoming

    def mark_as_incomplete(
        self, task_id: int, day: datetime.date | None = None
    ) -> None:
        """Un-complete a task (by id) for a given day (defaults to today)."""
        task = self.get_task(task_id)
        if task is not None:
            task.completed_on.discard(day or datetime.date.today())

    def remove_task(self, task_id: int) -> None:
        """Remove a task (by id) from whichever pet owns it."""
        for pet in self.owner.pets:
            pet.remove_task(task_id)

    def next_task(self, when: datetime.datetime | None = None) -> Task | None:
        """The soonest not-yet-done task at or after `when` (defaults to now).

        Scans forward day by day (up to a year, so even a long EVERY_N_DAYS
        interval is caught) and returns the first upcoming task, so the owner
        always knows what's next.
        """
        when = when or datetime.datetime.now()
        for offset in range(_LOOKAHEAD_DAYS):
            day = when.date() + datetime.timedelta(days=offset)
            for task in self.tasks_for_day(day):  # already time-sorted
                if task.is_done_on(day):
                    continue
                if offset == 0 and _to_minutes(task.time) <= _to_minutes(when.time()):
                    continue  # already past today
                return task
        return None

    def overdue_tasks(self, when: datetime.datetime | None = None) -> list[Task]:
        """Today's tasks whose start time has passed and aren't done yet.

        Lets the caller nudge the owner about missed care; HIGH-priority
        items in this list (e.g. medication) are the ones worth shouting about.
        Returned in schedule order (time, then priority).
        """
        when = when or datetime.datetime.now()
        today = when.date()
        now_minutes = _to_minutes(when.time())
        return [
            task
            for task in self.tasks_for_day(today)
            if _to_minutes(task.time) < now_minutes and not task.is_done_on(today)
        ]

    def daily_load(self, day: datetime.date) -> dict[str, int]:
        """Total scheduled minutes per pet for `day` (a quick workload view).

        Aggregates each occurring task's duration into a {pet name: minutes}
        dict in one linear pass, so an owner sees "Rex: 45 min" at a glance.
        """
        load: dict[str, int] = {}
        for task in self.tasks_for_day(day):
            pet = self.owner.pet_of(task.id)
            name = pet.name if pet else "unassigned"
            load[name] = load.get(name, 0) + task.duration
        return load

    def conflicts_on(self, day: datetime.date) -> list[tuple[Task, Task]]:
        """All pairs of tasks whose times overlap on `day`.

        A sweep line: walk the day's tasks in start-time order keeping only the
        ones still "open" (not yet ended); every open task overlaps the one
        arriving. O(n log n) instead of comparing all n*n pairs.
        """
        ordered = sorted(self.tasks_for_day(day), key=lambda t: _to_minutes(t.time))
        clashes: list[tuple[Task, Task]] = []
        active: list[Task] = []
        for task in ordered:
            start = _to_minutes(task.time)
            active = [t for t in active if _to_minutes(t.time) + t.duration > start]
            clashes.extend((other, task) for other in active)
            active.append(task)
        return clashes


def _to_minutes(t: datetime.time) -> int:
    """Minutes since midnight for a time-of-day."""
    return t.hour * 60 + t.minute


def _from_minutes(m: int) -> datetime.time:
    """Turn minutes-since-midnight back into a time-of-day."""
    return datetime.time(m // 60, m % 60)


def _times_overlap(a: Task, b: Task) -> bool:
    """Whether two tasks' time-of-day intervals overlap."""
    a_start = _to_minutes(a.time)
    b_start = _to_minutes(b.time)
    return a_start < b_start + b.duration and b_start < a_start + a.duration


# How far ahead _share_a_day looks for a day two recurrences both land on.
# A year covers the repeat cycle of any realistic daily/weekly/every-n mix.
_CONFLICT_SCAN_DAYS = 366

# How far ahead next_task looks; a year guarantees it catches the next
# occurrence of any single task, including a yearly-ish EVERY_N_DAYS interval.
_LOOKAHEAD_DAYS = 366


def _share_a_day(a: Task, b: Task) -> bool:
    """Whether two tasks can ever fall on the same calendar day.

    Anchored to each task's start (and end) date so recurrences that haven't
    begun, or have already finished, don't create phantom conflicts.

    - A one-off only happens on its own date, so it shares a day with the
      other task exactly when the other also occurs that date.
    - Two recurring tasks share a day if, scanning forward from the later
      start date, they both land on the same day within the cycle window.
    """
    if a.frequency is Frequency.ONCE:
        return b.occurs_on(a.date)
    if b.frequency is Frequency.ONCE:
        return a.occurs_on(b.date)
    start = max(a.date, b.date)
    return any(
        a.occurs_on(day) and b.occurs_on(day)
        for day in (start + datetime.timedelta(days=n) for n in range(_CONFLICT_SCAN_DAYS))
    )
