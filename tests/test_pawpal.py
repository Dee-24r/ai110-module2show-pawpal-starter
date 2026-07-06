"""Simple tests for the PawPal+ logic layer.

Run with:  python -m pytest
"""

import datetime

import pytest

from pawpal_system import Frequency, Owner, Pet, Priority, Scheduler, Task


def make_task(description: str = "Morning walk") -> Task:
    """A minimal task for use in tests."""
    return Task(
        description=description,
        date=datetime.date(2026, 7, 4),
        time=datetime.time(8, 0),
        duration=30,
    )


def make_scheduler() -> tuple[Scheduler, Pet]:
    """A scheduler over an owner with a single dog, for convenience."""
    owner = Owner("Funmi", "Engineer")
    pet = Pet("Rex", "dog", "M", 45.0, 18.0)
    owner.add_pet(pet)
    return Scheduler(owner), pet


def test_mark_complete_changes_status():
    """Completing a task flips its status for that day from not-done to done."""
    scheduler, pet = make_scheduler()

    task = make_task()
    scheduler.schedule_task(pet, task)
    day = task.date
    assert task.is_done_on(day) is False  # starts incomplete

    scheduler.mark_as_completed(task.id, day)

    assert task.is_done_on(day) is True  # now marked done


def test_adding_task_increases_pet_task_count():
    """Adding a task to a pet increases that pet's task count by one."""
    pet = Pet("Milo", "cat", "F", 25.0, 4.5)
    assert len(pet.tasks) == 0  # no tasks yet

    pet.add_task(make_task("Evening feeding"))

    assert len(pet.tasks) == 1  # one task after adding


def test_completion_is_per_day():
    """A recurring task done today is still pending on other days (Issue 1)."""
    scheduler, pet = make_scheduler()
    task = Task(
        "Daily walk", datetime.date(2026, 7, 4), datetime.time(8, 0), 30, Frequency.DAILY
    )
    scheduler.schedule_task(pet, task)

    day_one = datetime.date(2026, 7, 4)
    day_two = datetime.date(2026, 7, 5)
    scheduler.mark_as_completed(task.id, day_one)

    assert task.is_done_on(day_one) is True
    assert task.is_done_on(day_two) is False  # completion did not carry over

    scheduler.mark_as_incomplete(task.id, day_one)
    assert task.is_done_on(day_one) is False  # can be un-ticked


def test_free_slot_skips_busy_time():
    """find_free_slot returns the first gap that fits, past busy time (Issue 2)."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    # Busy 07:00–07:30, so a 30-min task can't start at the 07:00 day start.
    scheduler.schedule_task(
        pet, Task("Walk", day, datetime.time(7, 0), 30, Frequency.DAILY)
    )

    slot = scheduler.find_free_slot(day, 30)

    assert slot == datetime.time(7, 30)


def test_suggest_tasks_reflects_pet_attributes():
    """Suggestions derive from a pet's flags, retired pets get none (Issues 3/6)."""
    scheduler, _ = make_scheduler()

    dog = Pet("Rex", "dog", "M", 45.0, 18.0)
    dog_tasks = scheduler.suggest_tasks(dog)
    assert "Daily walk" in [t.description for t in dog_tasks]

    sick_cat = Pet("Milo", "cat", "M", 25.0, 4.5, takes_meds=True, has_illness=True)
    cat_tasks = scheduler.suggest_tasks(sick_cat)
    assert any(t.priority is Priority.HIGH for t in cat_tasks)  # meds/illness are urgent

    dog.retire()
    assert scheduler.suggest_tasks(dog) == []  # nothing for a retired pet


def test_high_priority_wins_time_ties():
    """When two tasks share a time, the higher-priority one sorts first (Issue 4)."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    scheduler.schedule_task(
        pet, Task("Walk", day, datetime.time(8, 0), 30, Frequency.DAILY)
    )
    scheduler.schedule_task(
        pet, Task("Meds", day, datetime.time(8, 0), 5, Frequency.DAILY, Priority.HIGH)
    )

    ordered = scheduler.tasks_for_day(day)

    assert ordered[0].description == "Meds"  # urgent care floats above the tie


def test_once_task_ignores_daily_that_starts_later():
    """A one-off doesn't conflict with a daily that begins after it (Issue 5)."""
    scheduler, pet = make_scheduler()
    once = Task("Vet visit", datetime.date(2026, 7, 1), datetime.time(8, 0), 30)
    later_daily = Task(
        "Walk", datetime.date(2026, 7, 5), datetime.time(8, 0), 30, Frequency.DAILY
    )
    scheduler.schedule_task(pet, later_daily)

    # The daily hasn't started on July 1, so they never share a day.
    assert scheduler.find_conflicts(once) == []

    # But a daily that started earlier *does* clash on July 1.
    earlier_daily = Task(
        "Feed", datetime.date(2026, 6, 1), datetime.time(8, 0), 30, Frequency.DAILY
    )
    scheduler.schedule_task(pet, earlier_daily)
    assert earlier_daily in scheduler.find_conflicts(once)


def test_every_n_days_recurrence():
    """An EVERY_N_DAYS task lands only on multiples of its interval."""
    task = Task(
        "Flea treatment",
        datetime.date(2026, 7, 4),
        datetime.time(9, 0),
        5,
        Frequency.EVERY_N_DAYS,
        interval=3,
    )
    assert task.occurs_on(datetime.date(2026, 7, 4)) is True   # day 0
    assert task.occurs_on(datetime.date(2026, 7, 5)) is False  # day 1
    assert task.occurs_on(datetime.date(2026, 7, 7)) is True   # day 3
    assert task.occurs_on(datetime.date(2026, 7, 3)) is False  # before start


def test_end_date_stops_recurrence():
    """A recurring task stops occurring after its end_date."""
    task = Task(
        "Med course",
        datetime.date(2026, 7, 4),
        datetime.time(9, 0),
        5,
        Frequency.DAILY,
        end_date=datetime.date(2026, 7, 6),
    )
    assert task.occurs_on(datetime.date(2026, 7, 6)) is True
    assert task.occurs_on(datetime.date(2026, 7, 7)) is False  # past the end date


def test_interval_must_be_positive():
    """An interval below 1 is rejected at construction."""
    with pytest.raises(ValueError):
        Task(
            "Bad",
            datetime.date(2026, 7, 4),
            datetime.time(9, 0),
            5,
            Frequency.EVERY_N_DAYS,
            interval=0,
        )


def test_next_task_returns_soonest_upcoming():
    """next_task skips what's already past and returns the next one due."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    scheduler.schedule_task(pet, Task("Early", day, datetime.time(7, 0), 30, Frequency.DAILY))
    scheduler.schedule_task(pet, Task("Late", day, datetime.time(20, 0), 30, Frequency.DAILY))

    when = datetime.datetime(2026, 7, 4, 8, 0)  # after Early, before Late
    assert scheduler.next_task(when).description == "Late"


def test_next_task_finds_task_beyond_two_weeks():
    """next_task catches a long EVERY_N_DAYS interval, not just the next 14 days."""
    scheduler, pet = make_scheduler()
    start = datetime.date(2026, 7, 4)
    scheduler.schedule_task(
        pet,
        Task("Monthly bath", start, datetime.time(9, 0), 30, Frequency.EVERY_N_DAYS, interval=30),
    )

    # Day after the start: the next bath is ~29 days out (start + 30).
    when = datetime.datetime(2026, 7, 5, 10, 0)
    upcoming = scheduler.next_task(when)

    assert upcoming is not None  # would be None with a 14-day horizon
    assert upcoming.description == "Monthly bath"


def test_overdue_tasks_flags_past_incomplete():
    """overdue_tasks lists today's past-due, not-yet-done tasks and clears on completion."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    meds = Task("Morning meds", day, datetime.time(8, 0), 5, Frequency.DAILY, Priority.HIGH)
    walk = Task("Evening walk", day, datetime.time(20, 0), 30, Frequency.DAILY)
    scheduler.schedule_task(pet, meds)
    scheduler.schedule_task(pet, walk)

    at_noon = datetime.datetime(2026, 7, 4, 12, 0)  # meds overdue, walk still ahead
    assert meds in scheduler.overdue_tasks(at_noon)
    assert walk not in scheduler.overdue_tasks(at_noon)

    scheduler.mark_as_completed(meds.id, day)
    assert meds not in scheduler.overdue_tasks(at_noon)  # ticking it off clears it


def test_sort_by_time_orders_by_time():
    """sort_by_time returns tasks in ascending time order, however they arrived."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    for hour in (18, 7, 9):  # added out of order
        scheduler.schedule_task(pet, Task(f"T{hour}", day, datetime.time(hour, 0), 15))

    times = [t.time for t in scheduler.sort_by_time()]

    assert times == [datetime.time(7, 0), datetime.time(9, 0), datetime.time(18, 0)]


def test_filter_by_pet_name():
    """filter_tasks(pet_name=...) returns only that pet's tasks."""
    owner = Owner("Funmi", "Engineer")
    rex = Pet("Rex", "dog", "M", 45.0, 18.0)
    milo = Pet("Milo", "cat", "M", 25.0, 4.5)
    owner.add_pet(rex)
    owner.add_pet(milo)
    scheduler = Scheduler(owner)
    day = datetime.date(2026, 7, 4)
    scheduler.schedule_task(rex, Task("Walk", day, datetime.time(8, 0), 30))
    scheduler.schedule_task(milo, Task("Feed", day, datetime.time(8, 0), 10))

    rex_tasks = scheduler.filter_tasks(pet_name="Rex")

    assert [t.description for t in rex_tasks] == ["Walk"]


def test_filter_by_completion_is_per_day():
    """filter_tasks(completed=...) is evaluated per day."""
    scheduler, pet = make_scheduler()
    task = Task("Walk", datetime.date(2026, 7, 4), datetime.time(8, 0), 30, Frequency.DAILY)
    scheduler.schedule_task(pet, task)
    day_one = datetime.date(2026, 7, 4)
    day_two = datetime.date(2026, 7, 5)
    scheduler.mark_as_completed(task.id, day_one)

    assert task in scheduler.filter_tasks(completed=True, day=day_one)
    assert task not in scheduler.filter_tasks(completed=False, day=day_one)
    # Not done on day two, so the flags flip.
    assert task in scheduler.filter_tasks(completed=False, day=day_two)
    assert task not in scheduler.filter_tasks(completed=True, day=day_two)


def test_filter_combined():
    """Combining filters returns only tasks matching both."""
    owner = Owner("Funmi", "Engineer")
    rex = Pet("Rex", "dog", "M", 45.0, 18.0)
    milo = Pet("Milo", "cat", "M", 25.0, 4.5)
    owner.add_pet(rex)
    owner.add_pet(milo)
    scheduler = Scheduler(owner)
    day = datetime.date(2026, 7, 4)
    # One-off tasks here so completion doesn't spawn a successor (keeps this a
    # pure filter test; recurrence roll-over is covered separately below).
    done = Task("Walk", day, datetime.time(8, 0), 30)
    pending = Task("Play", day, datetime.time(9, 0), 20)
    scheduler.schedule_task(rex, done)
    scheduler.schedule_task(rex, pending)
    scheduler.schedule_task(milo, Task("Feed", day, datetime.time(9, 0), 10))
    scheduler.mark_as_completed(done.id, day)

    result = scheduler.filter_tasks(pet_name="Rex", completed=False, day=day)

    assert [t.description for t in result] == ["Play"]


def test_completing_daily_task_spawns_next_day():
    """Completing a DAILY task auto-creates the next day's instance."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    walk = Task("Walk", day, datetime.time(8, 0), 30, Frequency.DAILY)
    scheduler.schedule_task(pet, walk)

    spawned = scheduler.mark_as_completed(walk.id, day)

    assert spawned is not None
    assert spawned.description == "Walk"
    assert spawned.date == day + datetime.timedelta(days=1)  # today + 1 day
    assert spawned.frequency is Frequency.DAILY
    assert spawned.is_done_on(spawned.date) is False  # fresh, not done
    # No duplicate: exactly one "Walk" occurs the next day.
    tomorrow = scheduler.tasks_for_day(day + datetime.timedelta(days=1))
    assert [t.id for t in tomorrow] == [spawned.id]


def test_completing_weekly_task_spawns_next_week():
    """Completing a WEEKLY task advances the date by one week."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    grooming = Task("Grooming", day, datetime.time(10, 0), 60, Frequency.WEEKLY)
    scheduler.schedule_task(pet, grooming)

    spawned = scheduler.mark_as_completed(grooming.id, day)

    assert spawned is not None
    assert spawned.date == day + datetime.timedelta(weeks=1)
    assert spawned.frequency is Frequency.WEEKLY


def test_completing_once_task_spawns_nothing():
    """A one-off task doesn't create a successor."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    once = Task("Vet visit", day, datetime.time(9, 0), 30)  # ONCE by default

    scheduler.schedule_task(pet, once)
    spawned = scheduler.mark_as_completed(once.id, day)

    assert spawned is None
    assert len(pet.tasks) == 1


def test_recurrence_stops_at_end_date():
    """No successor is spawned once the recurrence reaches its end_date."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    last = Task("Med", day, datetime.time(9, 0), 5, Frequency.DAILY, end_date=day)

    scheduler.schedule_task(pet, last)
    spawned = scheduler.mark_as_completed(last.id, day)

    assert spawned is None
    assert len(pet.tasks) == 1


def test_completing_twice_does_not_duplicate_successor():
    """Re-completing the same task doesn't spawn a second successor."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    walk = Task("Walk", day, datetime.time(8, 0), 30, Frequency.DAILY)
    scheduler.schedule_task(pet, walk)

    first = scheduler.mark_as_completed(walk.id, day)
    second = scheduler.mark_as_completed(walk.id, day)

    assert first is not None
    assert second is None  # successor already exists
    assert sum(t.description == "Walk" for t in pet.tasks) == 2  # original + one


def test_conflict_warning_reports_overlap_across_pets():
    """conflict_warning names the clashing task (even for a different pet)."""
    owner = Owner("Funmi", "Engineer")
    rex = Pet("Rex", "dog", "M", 45.0, 18.0)
    milo = Pet("Milo", "cat", "M", 25.0, 4.5)
    owner.add_pet(rex)
    owner.add_pet(milo)
    scheduler = Scheduler(owner)
    day = datetime.date(2026, 7, 4)
    scheduler.schedule_task(rex, Task("Vet visit", day, datetime.time(15, 0), 30))
    play = Task("Play date", day, datetime.time(15, 0), 30)  # same time, other pet

    warning = scheduler.conflict_warning(play)

    assert warning is not None
    assert "Vet visit" in warning  # names the clashing task
    assert "Rex" in warning        # and its pet, across pets


def test_conflict_warning_is_none_when_clear():
    """No overlap -> no warning (returns None, never raises)."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    scheduler.schedule_task(pet, Task("Walk", day, datetime.time(8, 0), 30))
    later = Task("Feed", day, datetime.time(9, 0), 15)  # after the walk ends

    assert scheduler.conflict_warning(later) is None


def test_daily_load_sums_minutes_per_pet():
    """daily_load totals each pet's scheduled minutes for the day."""
    owner = Owner("Funmi", "Engineer")
    rex = Pet("Rex", "dog", "M", 45.0, 18.0)
    milo = Pet("Milo", "cat", "M", 25.0, 4.5)
    owner.add_pet(rex)
    owner.add_pet(milo)
    scheduler = Scheduler(owner)
    day = datetime.date(2026, 7, 4)

    scheduler.schedule_task(rex, Task("Walk", day, datetime.time(7, 0), 30, Frequency.DAILY))
    scheduler.schedule_task(rex, Task("Feed", day, datetime.time(8, 0), 15, Frequency.DAILY))
    scheduler.schedule_task(milo, Task("Feed", day, datetime.time(8, 0), 10, Frequency.DAILY))

    load = scheduler.daily_load(day)
    assert load["Rex"] == 45  # 30 + 15
    assert load["Milo"] == 10


def test_conflicts_on_finds_overlapping_pairs():
    """conflicts_on reports overlapping pairs but not merely touching ones."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    scheduler.schedule_task(pet, Task("A", day, datetime.time(8, 0), 60, Frequency.DAILY))
    scheduler.schedule_task(pet, Task("B", day, datetime.time(8, 30), 15, Frequency.DAILY))
    scheduler.schedule_task(pet, Task("C", day, datetime.time(9, 0), 30, Frequency.DAILY))

    pairs = {frozenset((a.description, b.description)) for a, b in scheduler.conflicts_on(day)}

    assert frozenset(("A", "B")) in pairs      # 08:30 starts inside A (08:00–09:00)
    assert frozenset(("A", "C")) not in pairs  # C starts at 09:00, exactly when A ends


# ==========================================================================
# Three headline requirements: sorting, recurrence, conflict detection
# ==========================================================================

def test_sorting_correctness_returns_chronological_order():
    """Sorting Correctness: a day's tasks come back earliest-time-first."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    # Scheduled deliberately out of order (evening, dawn, midday, morning).
    scheduler.schedule_task(pet, Task("Evening walk", day, datetime.time(20, 0), 30))
    scheduler.schedule_task(pet, Task("Dawn feed", day, datetime.time(6, 30), 15))
    scheduler.schedule_task(pet, Task("Midday play", day, datetime.time(13, 0), 20))
    scheduler.schedule_task(pet, Task("Morning meds", day, datetime.time(9, 0), 5))

    ordered = scheduler.tasks_for_day(day)

    times = [t.time for t in ordered]
    assert times == sorted(times)  # non-decreasing: a real timeline
    assert [t.description for t in ordered] == [
        "Dawn feed", "Morning meds", "Midday play", "Evening walk"
    ]


def test_recurrence_logic_daily_complete_creates_following_day():
    """Recurrence Logic: completing a daily task spawns one for the next day."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    feeding = Task("Morning feeding", day, datetime.time(8, 0), 15, Frequency.DAILY)
    scheduler.schedule_task(pet, feeding)

    spawned = scheduler.mark_as_completed(feeding.id, day)
    tomorrow = day + datetime.timedelta(days=1)

    assert spawned is not None                       # a successor was created
    assert spawned.date == tomorrow                  # for the following day
    assert spawned.description == "Morning feeding"  # same activity
    assert spawned.frequency is Frequency.DAILY      # still recurring
    assert spawned.is_done_on(tomorrow) is False     # fresh, not pre-completed
    # It actually shows up on tomorrow's schedule.
    assert spawned in scheduler.tasks_for_day(tomorrow)


def test_conflict_detection_flags_duplicate_times():
    """Conflict Detection: scheduling a task at an occupied time is flagged."""
    scheduler, pet = make_scheduler()
    day = datetime.date(2026, 7, 4)
    scheduler.schedule_task(pet, Task("Vet visit", day, datetime.time(15, 0), 30))

    clash = Task("Grooming", day, datetime.time(15, 0), 30)  # exact same time slot
    conflicts = scheduler.schedule_task(pet, clash)

    assert len(conflicts) == 1                     # the clash is reported...
    assert conflicts[0].description == "Vet visit"  # ...and names the occupant
    # And it surfaces through the human-readable warning too.
    assert scheduler.conflict_warning(clash) is not None


# ==========================================================================
# Edge cases: Task.occurs_on across every frequency
# (Scheduler tests above lean on EVERY_N_DAYS + end_date; these fill the gaps)
# ==========================================================================

MONDAY = datetime.date(2026, 7, 6)  # a known Monday, for weekday-based tests
NINE_AM = datetime.time(9, 0)


def bare_task(freq: Frequency = Frequency.ONCE, *, date=MONDAY, time=NINE_AM,
              duration: int = 30, **kw) -> Task:
    """A Task with defaults; override only what the test cares about."""
    return Task("t", date, time, duration, freq, **kw)


def test_occurs_on_once_only_its_own_day():
    t = bare_task(Frequency.ONCE)
    assert t.occurs_on(MONDAY) is True
    assert t.occurs_on(MONDAY + datetime.timedelta(days=1)) is False
    assert t.occurs_on(MONDAY - datetime.timedelta(days=1)) is False  # before start


def test_occurs_on_daily_every_day_from_start():
    t = bare_task(Frequency.DAILY)
    assert t.occurs_on(MONDAY) is True                                 # start day
    assert t.occurs_on(MONDAY + datetime.timedelta(days=1)) is True
    assert t.occurs_on(MONDAY + datetime.timedelta(days=365)) is True
    assert t.occurs_on(MONDAY - datetime.timedelta(days=1)) is False   # before start


def test_occurs_on_weekly_matches_weekday_only():
    t = bare_task(Frequency.WEEKLY)  # anchored on MONDAY
    assert t.occurs_on(MONDAY) is True
    assert t.occurs_on(MONDAY + datetime.timedelta(weeks=1)) is True   # next Monday
    assert t.occurs_on(MONDAY + datetime.timedelta(days=1)) is False   # a Tuesday
    assert t.occurs_on(MONDAY - datetime.timedelta(weeks=1)) is False  # prior Mon, pre-start


def test_occurs_on_end_date_is_inclusive():
    end = MONDAY + datetime.timedelta(days=2)
    t = bare_task(Frequency.DAILY, end_date=end)
    assert t.occurs_on(end) is True                                    # last active day counts
    assert t.occurs_on(end + datetime.timedelta(days=1)) is False      # day after end


# ==========================================================================
# Edge cases: Task.next_occurrence (untested directly before — only via
# mark_as_completed). Its docstring promises correct month/year rollover.
# ==========================================================================

def test_next_occurrence_once_returns_none():
    assert bare_task(Frequency.ONCE).next_occurrence(MONDAY) is None


def test_next_occurrence_daily_advances_one_day():
    nxt = bare_task(Frequency.DAILY).next_occurrence(MONDAY)
    assert nxt is not None
    assert nxt.date == MONDAY + datetime.timedelta(days=1)


def test_next_occurrence_weekly_advances_one_week():
    nxt = bare_task(Frequency.WEEKLY).next_occurrence(MONDAY)
    assert nxt.date == MONDAY + datetime.timedelta(weeks=1)


def test_next_occurrence_every_n_days_uses_interval():
    nxt = bare_task(Frequency.EVERY_N_DAYS, interval=10).next_occurrence(MONDAY)
    assert nxt.date == MONDAY + datetime.timedelta(days=10)


def test_next_occurrence_handles_month_rollover():
    """Docstring's headline promise: Jul 31 + 1 day -> Aug 1, not 'Jul 32'."""
    jul31 = datetime.date(2026, 7, 31)
    nxt = bare_task(Frequency.DAILY).next_occurrence(jul31)
    assert nxt.date == datetime.date(2026, 8, 1)


def test_next_occurrence_handles_year_rollover():
    dec31 = datetime.date(2026, 12, 31)
    nxt = bare_task(Frequency.DAILY).next_occurrence(dec31)
    assert nxt.date == datetime.date(2027, 1, 1)


def test_next_occurrence_none_past_end_date():
    t = bare_task(Frequency.DAILY, end_date=MONDAY)  # ends on the completion day
    assert t.next_occurrence(MONDAY) is None


def test_next_occurrence_is_fresh_copy_new_id_no_completions():
    original = bare_task(Frequency.DAILY, priority=Priority.HIGH, duration=45)
    original.completed_on.add(MONDAY)
    nxt = original.next_occurrence(MONDAY)

    # Attributes carried forward...
    assert nxt.description == original.description
    assert nxt.priority is Priority.HIGH
    assert nxt.duration == 45
    assert nxt.frequency is Frequency.DAILY
    # ...but it's a genuinely new, un-ticked instance.
    assert nxt.id != original.id
    assert nxt.completed_on == set()


def test_next_occurrence_preserves_interval_and_end_date():
    end = MONDAY + datetime.timedelta(days=100)
    t = bare_task(Frequency.EVERY_N_DAYS, interval=5, end_date=end)
    nxt = t.next_occurrence(MONDAY)
    assert nxt.interval == 5
    assert nxt.end_date == end


# ==========================================================================
# Edge cases: frequency semantics via Task.is_recurring
# ==========================================================================

@pytest.mark.parametrize(
    "freq, recurring",
    [
        (Frequency.ONCE, False),
        (Frequency.DAILY, True),
        (Frequency.WEEKLY, True),
        (Frequency.EVERY_N_DAYS, True),
    ],
)
def test_is_recurring_matches_frequency(freq, recurring):
    assert bare_task(freq).is_recurring is recurring


# ==========================================================================
# Edge cases: Task.overlaps (direct — boundary, symmetry, cross-day)
# ==========================================================================

def test_overlaps_same_day_and_time():
    a = bare_task(time=datetime.time(9, 0), duration=30)
    b = bare_task(time=datetime.time(9, 15), duration=30)
    assert a.overlaps(b) is True


def test_overlaps_touching_boundary_does_not_count():
    """A ends exactly when B begins -> no collision (half-open intervals)."""
    a = bare_task(time=datetime.time(9, 0), duration=30)   # 09:00-09:30
    b = bare_task(time=datetime.time(9, 30), duration=30)  # 09:30-10:00
    assert a.overlaps(b) is False


def test_overlaps_same_day_disjoint_times():
    a = bare_task(time=datetime.time(9, 0), duration=30)
    b = bare_task(time=datetime.time(11, 0), duration=30)
    assert a.overlaps(b) is False


def test_overlaps_same_time_different_days():
    a = bare_task(date=MONDAY, time=NINE_AM, duration=30)
    b = bare_task(date=MONDAY + datetime.timedelta(days=1), time=NINE_AM, duration=30)
    assert a.overlaps(b) is False


def test_overlaps_is_symmetric():
    a = bare_task(time=datetime.time(9, 0), duration=30)
    b = bare_task(time=datetime.time(9, 15), duration=30)
    assert a.overlaps(b) == b.overlaps(a)


def test_overlaps_recurring_tasks_share_a_future_day():
    """Two dailies at the same time collide even though neither is a one-off."""
    a = bare_task(Frequency.DAILY, time=NINE_AM)
    b = bare_task(Frequency.DAILY, time=NINE_AM, date=MONDAY + datetime.timedelta(days=3))
    assert a.overlaps(b) is True


def test_overlaps_once_vs_daily_that_starts_later():
    once = bare_task(Frequency.ONCE, date=MONDAY, time=NINE_AM)
    later_daily = bare_task(
        Frequency.DAILY, date=MONDAY + datetime.timedelta(days=1), time=NINE_AM
    )
    assert once.overlaps(later_daily) is False  # daily hasn't begun on the one-off's day
