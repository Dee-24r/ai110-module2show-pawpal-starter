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

    ONCE is a one-off (unique) task; DAILY and WEEKLY are recurring.
    """

    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"


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
    completed: bool = False
    id: int = field(init=False, default_factory=lambda: next(_task_ids))

    @property
    def is_recurring(self) -> bool:
        """Whether this task repeats (i.e. is not a one-off)."""
        return self.frequency is not Frequency.ONCE

    def occurs_on(self, day: datetime.date) -> bool:
        """Whether this task happens on the given calendar day."""
        if day < self.date:
            return False
        if self.frequency is Frequency.ONCE:
            return day == self.date
        if self.frequency is Frequency.DAILY:
            return True
        if self.frequency is Frequency.WEEKLY:
            return day.weekday() == self.date.weekday()
        return False

    def overlaps(self, other: "Task") -> bool:
        """Whether this and another task ever collide (same day + time)."""
        return _share_a_day(self, other) and _times_overlap(self, other)


@dataclass
class Pet:
    """A pet belonging to an owner; owns its own list of tasks."""

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

    def tasks_for_day(self, day: datetime.date) -> list[Task]:
        """All tasks occurring on the given day, sorted by time."""
        due = [t for t in self.all_tasks() if t.occurs_on(day)]
        return sorted(due, key=lambda t: t.time)

    def tasks_for_today(self) -> list[Task]:
        """All tasks occurring today, sorted by time."""
        return self.tasks_for_day(datetime.date.today())

    def get_task(self, task_id: int) -> Task | None:
        """Look up a single task by id across all pets."""
        for task in self.all_tasks():
            if task.id == task_id:
                return task
        return None

    def mark_as_completed(self, task_id: int) -> None:
        """Mark a task (by id) as done."""
        task = self.get_task(task_id)
        if task is not None:
            task.completed = True

    def remove_task(self, task_id: int) -> None:
        """Remove a task (by id) from whichever pet owns it."""
        for pet in self.owner.pets:
            pet.remove_task(task_id)


def _times_overlap(a: Task, b: Task) -> bool:
    """Whether two tasks' time-of-day intervals overlap."""
    a_start = a.time.hour * 60 + a.time.minute
    b_start = b.time.hour * 60 + b.time.minute
    a_end = a_start + a.duration
    b_end = b_start + b.duration
    return a_start < b_end and b_start < a_end


def _share_a_day(a: Task, b: Task) -> bool:
    """Whether two tasks can ever fall on the same calendar day.

    Simplified: DAILY is treated as ongoing (ignores start-date boundaries).
    """
    if a.frequency is Frequency.DAILY or b.frequency is Frequency.DAILY:
        return True
    if a.frequency is Frequency.WEEKLY or b.frequency is Frequency.WEEKLY:
        # weekly-vs-weekly or weekly-vs-once: collide only on the same weekday
        return a.date.weekday() == b.date.weekday()
    # both ONCE
    return a.date == b.date
