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
                # >>> logic layer: build the clash message (or None) <<<
                warning = scheduler.conflict_warning(task)
                scheduler.schedule_task(pet, task)
                st.success(f"Scheduled '{task.description}' for {pet.name}.")
                if warning:
                    # >>> logic layer: propose the next open slot <<<
                    slot = scheduler.find_free_slot(t_date, task.duration)
                    tip = f" Next free slot: **{slot:%H:%M}**." if slot else ""
                    st.warning(f"⚠️ {warning}{tip}")

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
