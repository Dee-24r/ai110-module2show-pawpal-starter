"""PawPal+ logic layer.

Backend classes for the PawPal+ scheduling app. Structure follows
diagrams/uml.mmd: an Owner owns many Pets and has one Schedule; the
Schedule contains many Activities; each Activity is for one Pet.
"""

from dataclasses import dataclass, field


@dataclass
class Pet:
    """A pet belonging to an owner."""

    type: str
    gender: str
    height: float
    weight: float
    has_illness: bool = False
    takes_meds: bool = False
    retired: bool = False

    def retire(self) -> None:
        """Mark this pet as retired (no longer gets new activities)."""
        pass


@dataclass
class Activity:
    """A task to perform for a pet, e.g. a walk or feeding."""

    pet: Pet
    duration: int
    recurring: bool = False
    frequency: str = ""
    times: list[str] = field(default_factory=list)
    completed: bool = False


class Schedule:
    """Holds and manages all activities for an owner."""

    def __init__(self) -> None:
        self.tasks: list[Activity] = []

    def schedule_task(self, task: Activity) -> None:
        """Add an activity to the schedule."""
        pass

    def mark_as_completed(self, task: Activity) -> None:
        """Mark an activity as done."""
        pass

    def remove_task(self, task: Activity) -> None:
        """Remove an activity from the schedule."""
        pass


class Owner:
    """The app user; owns pets and has a schedule."""

    def __init__(self, name: str, occupation: str) -> None:
        self.name = name
        self.occupation = occupation
        self.pets: list[Pet] = []
        self.schedule = Schedule()

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        pass
