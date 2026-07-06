import datetime

import streamlit as st

# Bridge to the logic layer: bring the backend classes into the UI.
from pawpal_system import Owner, Pet, Priority, Task, Scheduler, Frequency

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

# --- Session "memory" -----------------------------------------------------
# Streamlit re-runs this file top-to-bottom on every interaction, so any plain
# variable is rebuilt (and emptied) each time. st.session_state is a dict-like
# vault that PERSISTS across reruns. We check whether our objects already exist
# before creating them, so the Owner (and its pets/tasks) survives every click.
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan", occupation="")

if "scheduler" not in st.session_state:
    # The Scheduler is the "brain" and wraps the same persistent Owner.
    st.session_state.scheduler = Scheduler(st.session_state.owner)

# Convenient short handles for use below (these point at the persisted objects).
owner = st.session_state.owner
scheduler = st.session_state.scheduler

st.title("🐾 PawPal+")
st.caption("A pet care planning assistant. Add pets, schedule their care, and see today's plan.")

# --- Owner ----------------------------------------------------------------
st.subheader("👤 Owner")
# Bind the inputs straight back onto the persisted Owner object.
owner.name = st.text_input("Your name", value=owner.name)
owner.occupation = st.text_input("Your occupation", value=owner.occupation)

st.divider()

# --- Add a Pet ------------------------------------------------------------
st.subheader("🐶 Add a Pet")
ANIMAL_TYPES = [
    "dog",
    "cat",
    "rabbit",
    "bird",
    "hamster",
    "fish",
    "reptile",
    "horse",
    "other",
]

with st.form("add_pet_form", clear_on_submit=True):
    p_name = st.text_input("Name", value="")
    p_type = st.selectbox("Type", ANIMAL_TYPES)
    p_gender = st.selectbox("Gender", ["M", "F"])
    c1, c2 = st.columns(2)
    p_height = c1.number_input("Height (cm)", min_value=0.0, value=30.0, step=1.0)
    p_weight = c2.number_input("Weight (kg)", min_value=0.0, value=5.0, step=0.5)
    c3, c4 = st.columns(2)
    p_illness = c3.checkbox("Has illness?")
    p_meds = c4.checkbox("Takes meds?")

    if st.form_submit_button("Add pet"):
        if not p_name.strip():
            st.error("Please give your pet a name.")
        else:
            # >>> Calls the logic layer <<<
            owner.add_pet(
                Pet(
                    name=p_name.strip(),
                    type=p_type,
                    gender=p_gender,
                    height=p_height,
                    weight=p_weight,
                    has_illness=p_illness,
                    takes_meds=p_meds,
                )
            )
            st.success(f"Added {p_name.strip()} the {p_type}!")

# --- Current Pets (with retire) -------------------------------------------
if owner.pets:
    st.write("**Your pets:**")
    for pet in owner.pets:
        badge = " · 💊 meds" if pet.takes_meds else ""
        badge += " · 🤒 illness" if pet.has_illness else ""
        retired = " *(retired)*" if pet.retired else ""
        cols = st.columns([0.75, 0.25])
        cols[0].markdown(
            f"**{pet.name}** — {pet.type.title()} ({pet.gender}), "
            f"{pet.height:g} cm, {pet.weight:g} kg{badge}{retired}"
        )
        # Retire cancels the pet's tasks via Owner.retire_pet in the logic layer.
        if not pet.retired and cols[1].button("Retire", key=f"retire_{id(pet)}"):
            owner.retire_pet(pet)
            st.rerun()
else:
    st.info("No pets yet. Add one above.")

st.divider()

# --- Schedule a Task ------------------------------------------------------
st.subheader("📅 Schedule a Task")
if not owner.pets:
    st.info("Add a pet first, then you can schedule tasks for it.")
else:
    with st.form("add_task_form", clear_on_submit=True):
        # Select by index and look the pet up in owner.pets, so we mutate the
        # SAME persisted object (Streamlit doesn't preserve object identity for
        # object-valued selectbox options).
        pet_index = st.selectbox(
            "For which pet?",
            options=range(len(owner.pets)),
            format_func=lambda i: f"{owner.pets[i].name} ({owner.pets[i].type})",
        )
        pet = owner.pets[pet_index]
        description = st.text_input("What needs doing?", value="Morning walk")
        c1, c2 = st.columns(2)
        t_date = c1.date_input("Date", value=datetime.date.today())
        t_time = c2.time_input("Time", value=datetime.time(8, 0))
        c3, c4 = st.columns(2)
        t_duration = c3.number_input("Duration (min)", min_value=1, max_value=480, value=30)
        t_freq = c4.selectbox(
            "Frequency",
            options=list(Frequency),
            format_func=lambda f: f.value.replace("_", " ").title(),
        )
        # Only used when frequency is "Every N Days"; ignored otherwise.
        t_interval = st.number_input(
            "Repeat every N days (for 'Every N Days')",
            min_value=1,
            max_value=365,
            value=2,
        )

        if st.form_submit_button("Schedule task"):
            if not description.strip():
                st.error("Please describe the task.")
            else:
                task = Task(
                    description=description.strip(),
                    date=t_date,
                    time=t_time,
                    duration=int(t_duration),
                    frequency=t_freq,
                    interval=int(t_interval),
                )
                # >>> logic layer: detect clashes across ALL pets <<<
                conflicts = scheduler.find_conflicts(task)
                scheduler.schedule_task(pet, task)  # saved regardless (non-blocking)
                st.success(
                    f"✅ Scheduled '{task.description}' for {pet.name} "
                    f"at {task.time:%H:%M}."
                )
                if conflicts:
                    # A pet owner is one person who can't be two places at once,
                    # so we WARN (amber, not a red error) instead of refusing the
                    # save — and we make it actionable: name each clash and offer
                    # the next open slot so the fix is one glance away.
                    detail = "\n".join(
                        f"- **{c.description}** at {c.time:%H:%M}"
                        + (f" ({cp.name})" if (cp := owner.pet_of(c.id)) else "")
                        for c in conflicts
                    )
                    slot = scheduler.find_free_slot(t_date, task.duration)
                    tip = (
                        f"\n\n💡 Next free slot on {t_date:%b %d}: "
                        f"**{slot:%H:%M}** — edit the task to move it there."
                        if slot
                        else "\n\n💡 That day is fully booked in your waking hours."
                    )
                    st.warning(
                        f"⚠️ **Heads up — this overlaps another task.**\n\n"
                        f"'{task.description}' at {task.time:%H:%M} clashes with:\n"
                        f"{detail}{tip}\n\n"
                        "_Saved anyway — just make sure you can manage both, "
                        "or reschedule one._"
                    )

st.divider()

# --- Today's Schedule -----------------------------------------------------
st.subheader("📋 Today's Schedule")
today = datetime.date.today()
today_tasks = scheduler.tasks_for_today()  # >>> logic layer: retrieves + sorts <<<

if not today_tasks:
    st.info("Nothing scheduled today. Go relax with your pets! 🐾")
else:
    # >>> logic layer: quick planner insights <<<
    next_up = scheduler.next_task()
    load = scheduler.daily_load(today)
    clashes = scheduler.conflicts_on(today)

    m1, m2 = st.columns(2)
    m1.metric("Tasks today", len(today_tasks))
    m2.metric("Busy minutes", sum(load.values()))
    if next_up is not None:
        st.caption(f"⏭️ Next up: **{next_up.time:%H:%M}** — {next_up.description}")
    if load:
        st.caption("🐾 " + " · ".join(f"{name}: {mins} min" for name, mins in load.items()))

    # A little positive reinforcement once the whole day is ticked off.
    if all(t.is_done_on(today) for t in today_tasks):
        st.success("🎉 Everything for today is done — go relax with your pets!")

    overdue = scheduler.overdue_tasks()
    high_overdue = [t for t in overdue if t.priority is Priority.HIGH]
    if high_overdue:
        names = ", ".join(t.description for t in high_overdue)
        st.error(f"⏰ Overdue & urgent: {names} — do these first!")
    elif overdue:
        names = ", ".join(t.description for t in overdue)
        st.info(f"⏰ Overdue: {names}")

    if clashes:
        lines = "\n".join(f"- {a.description} ↔ {b.description}" for a, b in clashes)
        st.warning(f"⚠️ {len(clashes)} time clash(es) today:\n{lines}")

    for task in today_tasks:
        task_pet = owner.pet_of(task.id)
        pet_label = task_pet.name if task_pet else "?"
        # Completion is per-day, so ask whether it's done *today*.
        done_today = task.is_done_on(today)
        cols = st.columns([0.08, 0.62, 0.15, 0.15])

        # Checkbox toggles today's completion through the logic layer.
        checked = cols[0].checkbox(
            "done",
            value=done_today,
            key=f"done_{task.id}",
            label_visibility="collapsed",
        )
        if checked and not done_today:
            scheduler.mark_as_completed(task.id)  # defaults to today
        elif not checked and done_today:
            scheduler.mark_as_incomplete(task.id)

        flag = " ‼️" if task.priority is Priority.HIGH else ""
        label = (
            f"**{task.time:%H:%M}** — {task.description}{flag} "
            f"({pet_label} · {task.duration} min · {task.frequency.value})"
        )
        cols[1].markdown(f"~~{label}~~" if done_today else label)

        if cols[3].button("Remove", key=f"rm_{task.id}"):
            scheduler.remove_task(task.id)  # >>> logic layer <<<
            st.rerun()

st.divider()

# --- Browse Tasks (sorted + filtered) -------------------------------------
# A read-only, professional overview for ANY date, showing off the Scheduler's
# filtering and sorting. (Today's Schedule above stays interactive; this is the
# "at a glance" table view.)
st.subheader("🔎 Browse Tasks")
if not scheduler.all_tasks():
    st.info("No tasks scheduled yet. Add some above to see them here.")
else:
    fc1, fc2, fc3 = st.columns(3)
    pet_choice = fc1.selectbox(
        "Pet", ["All pets"] + [p.name for p in owner.pets], key="browse_pet"
    )
    status_choice = fc2.selectbox("Status", ["All", "Pending", "Done"], key="browse_status")
    view_date = fc3.date_input("On date", value=today, key="browse_date")

    # Translate the UI choices into logic-layer filter arguments.
    pet_name = None if pet_choice == "All pets" else pet_choice
    completed = {"All": None, "Pending": False, "Done": True}[status_choice]

    # >>> logic layer: filter by pet + completion, keep that day's occurrences,
    #     then sort chronologically <<<
    filtered = scheduler.filter_tasks(pet_name=pet_name, completed=completed, day=view_date)
    day_view = scheduler.sort_by_time([t for t in filtered if t.occurs_on(view_date)])

    if not day_view:
        st.info(f"No matching tasks on {view_date:%A, %b %d}.")
    else:
        rows = [
            {
                "Time": f"{t.time:%H:%M}",
                "Task": t.description,
                "Pet": (owner.pet_of(t.id).name if owner.pet_of(t.id) else "—"),
                "Duration": f"{t.duration} min",
                "Priority": t.priority.name.title(),
                "Repeats": t.frequency.value.replace("_", " ").title(),
                "Status": "✅ Done" if t.is_done_on(view_date) else "⬜ Pending",
            }
            for t in day_view
        ]
        st.table(rows)
        st.caption(
            f"Showing {len(rows)} task(s) on {view_date:%A, %b %d} — "
            "sorted by time of day."
        )

        # >>> logic layer: flag overlapping pairs on the viewed day <<<
        day_clashes = scheduler.conflicts_on(view_date)
        if day_clashes:
            lines = "\n".join(
                f"- **{a.description}** ({a.time:%H:%M}) ↔ "
                f"**{b.description}** ({b.time:%H:%M})"
                for a, b in day_clashes
            )
            st.warning(f"⚠️ {len(day_clashes)} time clash(es) on this day:\n{lines}")
        else:
            st.success("✅ No scheduling conflicts on this day.")
