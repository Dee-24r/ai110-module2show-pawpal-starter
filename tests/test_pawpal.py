"""Simple tests for the PawPal+ logic layer.

Run with:  python -m pytest
"""

import datetime

from pawpal_system import Owner, Pet, Scheduler, Task


def make_task(description: str = "Morning walk") -> Task:
    """A minimal task for use in tests."""
    return Task(
        description=description,
        date=datetime.date(2026, 7, 4),
        time=datetime.time(8, 0),
        duration=30,
    )


def test_mark_complete_changes_status():
    """Completing a task flips its status from not-done to done."""
    owner = Owner("Funmi", "Engineer")
    pet = Pet("dog", "M", 45.0, 18.0)
    owner.add_pet(pet)
    scheduler = Scheduler(owner)

    task = make_task()
    scheduler.schedule_task(pet, task)
    assert task.completed is False  # starts incomplete

    scheduler.mark_as_completed(task.id)

    assert task.completed is True  # now marked done


def test_adding_task_increases_pet_task_count():
    """Adding a task to a pet increases that pet's task count by one."""
    pet = Pet("cat", "F", 25.0, 4.5)
    assert len(pet.tasks) == 0  # no tasks yet

    pet.add_task(make_task("Evening feeding"))

    assert len(pet.tasks) == 1  # one task after adding
