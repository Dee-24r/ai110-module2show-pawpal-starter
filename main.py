"""Demo / testing ground for the PawPal+ logic layer.

Run with: python main.py

Builds an owner with a couple of pets, lets the scheduler derive their care
routine from their attributes, then prints the schedule so we can eyeball that
the backend works before touching the Streamlit UI. Along the way it shows off
the scheduler's smarter logic: attribute-driven suggestions, priority ordering,
free-slot rescheduling, and per-day completion.
"""

import datetime

from pawpal_system import Frequency, Owner, Pet, Priority, Scheduler, Task


def print_schedule(scheduler: Scheduler, day: datetime.date, heading: str) -> None:
    """Pretty-print everything on `day`'s schedule."""
    tasks = scheduler.tasks_for_day(day)

    print(f"\n===== {heading} ({day:%A, %B %d}) =====")
    if not tasks:
        print("  Nothing scheduled. Go relax with your pets!")
        print("=" * 52)
        return

    for task in tasks:
        pet = scheduler.owner.pet_of(task.id)
        pet_label = pet.name if pet else "unknown pet"
        status = "[x]" if task.is_done_on(day) else "[ ]"
        flag = " (!)" if task.priority is Priority.HIGH else ""
        print(
            f"  {status} {task.time:%H:%M}  {task.description}{flag} "
            f"({pet_label}, {task.duration} min, {task.frequency.value})"
        )
    print("=" * 52)


def main() -> None:
    # 1. Create an owner and at least two pets.
    owner = Owner(name="Funmi", occupation="Software Engineer")

    rex = Pet(name="Rex", type="dog", gender="M", height=45.0, weight=18.0)
    milo = Pet(
        name="Milo", type="cat", gender="M", height=25.0, weight=4.5, takes_meds=True
    )
    owner.add_pet(rex)
    owner.add_pet(milo)

    # 2. Wire up the scheduler (the brain) over this owner.
    scheduler = Scheduler(owner)
    today = datetime.date.today()

    # 3. Let the scheduler derive each pet's routine from its attributes,
    #    instead of hand-authoring every task. Milo's meds task comes straight
    #    from `takes_meds=True`; Rex gets a dog's daily walk.
    for pet in owner.pets:
        for task in scheduler.suggest_tasks(pet, start=today):
            scheduler.schedule_task(pet, task)
        print(f"Auto-added {len(pet.tasks)} suggested task(s) for {pet.name}.")

    # 4. Add a one-off task that clashes with the routine. Rather than just
    #    warning, the scheduler proposes the next free slot and we take it.
    grooming = Task(
        description="Grooming",
        date=today,
        time=datetime.time(8, 0),  # collides with the 08:00 feedings
        duration=45,
        frequency=Frequency.ONCE,
    )
    conflicts = scheduler.find_conflicts(grooming)
    if conflicts:
        clashing = ", ".join(c.description for c in conflicts)
        slot = scheduler.find_free_slot(today, grooming.duration)
        print(
            f"\n'{grooming.description}' at {grooming.time:%H:%M} clashes with "
            f"{clashing}."
        )
        if slot is not None:
            print(f"  -> Free slot found: {slot:%H:%M}. Rescheduling there.")
            grooming.time = slot
    scheduler.schedule_task(rex, grooming)

    # 4b. An interval-based routine: deep-clean Milo's litter every 3 days.
    scheduler.schedule_task(
        milo,
        Task(
            "Litter deep-clean",
            today,
            datetime.time(17, 0),
            20,
            Frequency.EVERY_N_DAYS,
            interval=3,
        ),
    )

    # 4c. Lightweight conflict check: two tasks at the SAME time (different
    #     pets). The scheduler warns instead of crashing, and we schedule anyway.
    vet_visit = Task("Vet visit", today, datetime.time(15, 0), 30, Frequency.ONCE)
    play_date = Task("Play date", today, datetime.time(15, 0), 30, Frequency.ONCE)
    scheduler.schedule_task(rex, vet_visit)  # first one goes in clean
    warning = scheduler.conflict_warning(play_date)  # second lands at 15:00 too
    print(f"\n{warning}" if warning else "\nNo conflict for the play date.")
    scheduler.schedule_task(milo, play_date)  # non-fatal: added despite the clash

    # 5. Print today's schedule (note meds float above ties, marked "(!)").
    print_schedule(scheduler, today, "Today's Schedule")

    # 6. Tick off a recurring task for today, and show completion is per-day:
    #    it reads done today but is still pending tomorrow.
    walk = next((t for t in rex.tasks if t.description == "Daily walk"), None)
    if walk is not None:
        spawned = scheduler.mark_as_completed(walk.id)  # today only
        print("\n...marked Rex's 'Daily walk' as done for today...")
        if spawned is not None:
            print(f"   auto-created the next one for {spawned.date:%A, %b %d}.")
        print_schedule(scheduler, today, "Today's Schedule")

        tomorrow = today + datetime.timedelta(days=1)
        print_schedule(
            scheduler, tomorrow, "Tomorrow (completion rolled the daily task forward)"
        )

    # 7. Planner insights an owner actually cares about.
    print("\n----- Planner insights -----")
    upcoming = scheduler.next_task()
    if upcoming is not None:
        pet = scheduler.owner.pet_of(upcoming.id)
        who = pet.name if pet else "?"
        print(f"  Next up: {upcoming.time:%H:%M} {upcoming.description} ({who})")
    for name, minutes in scheduler.daily_load(today).items():
        print(f"  {name}'s workload today: {minutes} min")
    clashes = scheduler.conflicts_on(today)
    if clashes:
        for first, second in clashes:
            print(f"  Clash: {first.description} overlaps {second.description}")
    else:
        print("  No time clashes today.")
    for task in scheduler.overdue_tasks():
        mark = " (!)" if task.priority is Priority.HIGH else ""
        print(f"  OVERDUE{mark}: {task.time:%H:%M} {task.description}")
    print("-" * 28)

    # 8. Add tasks OUT OF ORDER, then sort + filter them back into shape.
    for description, hour, minute in [
        ("Evening cuddle", 21, 0),
        ("Sunrise stretch", 6, 15),
        ("Midday play", 13, 30),
    ]:
        scheduler.schedule_task(
            rex,
            Task(description, today, datetime.time(hour, minute), 10, Frequency.DAILY),
        )

    print("\n----- Rex's tasks, sorted by time (added out of order) -----")
    for task in scheduler.sort_by_time(scheduler.filter_tasks(pet_name="Rex")):
        status = "[x]" if task.is_done_on(today) else "[ ]"
        print(f"  {status} {task.time:%H:%M}  {task.description}")

    print("\n----- Still incomplete today (any pet), earliest first -----")
    for task in scheduler.sort_by_time(scheduler.filter_tasks(completed=False, day=today)):
        pet = scheduler.owner.pet_of(task.id)
        who = pet.name if pet else "?"
        print(f"  {task.time:%H:%M}  {task.description} ({who})")


if __name__ == "__main__":
    main()
