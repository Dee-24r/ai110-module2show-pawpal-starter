"""Demo / testing ground for the PawPal+ logic layer.

Run with: python main.py

Builds an owner with a couple of pets and a few tasks, then prints today's
schedule to the terminal so we can eyeball that the backend works before
touching the Streamlit UI.
"""

import datetime

from pawpal_system import Frequency, Owner, Pet, Scheduler, Task


def print_todays_schedule(scheduler: Scheduler) -> None:
    """Pretty-print everything on today's schedule."""
    today = datetime.date.today()
    tasks = scheduler.tasks_for_day(today)

    print(f"\n===== Today's Schedule ({today:%A, %B %d, %Y}) =====")
    if not tasks:
        print("  Nothing scheduled today. Go relax with your pets!")
        return

    for task in tasks:
        pet = scheduler.owner.pet_of(task.id)
        pet_label = pet.type if pet else "unknown pet"
        status = "[x]" if task.completed else "[ ]"
        print(
            f"  {status} {task.time:%H:%M}  {task.description} "
            f"({pet_label}, {task.duration} min, {task.frequency.value})"
        )
    print("=" * 47)


def main() -> None:
    # 1. Create an owner and at least two pets.
    owner = Owner(name="Funmi", occupation="Software Engineer")

    rex = Pet(type="dog", gender="M", height=45.0, weight=18.0)
    milo = Pet(type="cat", gender="M", height=25.0, weight=4.5, takes_meds=True)
    owner.add_pet(rex)
    owner.add_pet(milo)

    # 2. Wire up the scheduler (the brain) over this owner.
    scheduler = Scheduler(owner)

    # 3. Add at least three tasks with different times.
    today = datetime.date.today()

    morning_walk = Task(
        description="Morning walk",
        date=today,
        time=datetime.time(7, 30),
        duration=30,
        frequency=Frequency.DAILY,
    )
    give_meds = Task(
        description="Give allergy meds",
        date=today,
        time=datetime.time(9, 0),
        duration=5,
        frequency=Frequency.DAILY,
    )
    evening_feed = Task(
        description="Evening feeding",
        date=today,
        time=datetime.time(18, 0),
        duration=15,
        frequency=Frequency.DAILY,
    )

    # Schedule them; schedule_task returns any conflicting tasks.
    for pet, task in [(rex, morning_walk), (milo, give_meds), (milo, evening_feed)]:
        conflicts = scheduler.schedule_task(pet, task)
        if conflicts:
            clashing = ", ".join(c.description for c in conflicts)
            print(f"WARNING: '{task.description}' overlaps with: {clashing}")

    # 4. Print today's schedule.
    print_todays_schedule(scheduler)

    # Bonus: tick one off and show the schedule updating.
    scheduler.mark_as_completed(morning_walk.id)
    print("\n...marked 'Morning walk' as completed...")
    print_todays_schedule(scheduler)


if __name__ == "__main__":
    main()
