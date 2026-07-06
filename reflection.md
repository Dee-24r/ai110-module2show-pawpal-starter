# PawPal+ Project Reflection

## 1. System Design

What does my app do?
- Users can add a pet, and select the characterisistics and actions particular to their pet.
- Put in their work/life schedule
- Schedule a walk, schedule feeding
- See today's tasks
- Reschedule or cancel a task!
- Tick off completed tasks
- View pet info and dashboard

OBJECTS

- Owner
  - Name
  - Occupation
  - Number of pets, maybe?
  - 

- Pet
  - Type (dog, cat, horse, giraffe)?
  - gender
  - Height, weight
  - has illness?
  - Takes meds?
  - Retire

- Activity/Task
  - Duration
  - Recurring or not?/Frequency
  - Time(s) of occurence
  - Remove
  - Schedule (with set frequency)

- Scheduler
  - Schedule an extra task
  - Mark as completed
  - Remove a task

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

My initial UML design has 4 clas]ses - Pet, Owner, Activities and Schedule.

The schedule can add an activity to the schedule, mark one as completed, and remove one.
The Pet can retire!
The Owner can add a pet!

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

Yes, I changed design before I started implementing.

Now activities have the scheduling method.
and scheduler schedules recurring activities.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?


The scheduler considers time of day, duration, priority, recurrence pattern, and a "waking window" (7am–10pm) for free-slot suggestions. Conflicts are checked across all pets because the owner is one person. The time is the primary ordering key and the priority is the tie-breaker — when two tasks share a time, HIGH-priority care (like meds) sorts first. This matters because we shouldn't misplace medication reminders.



**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

(This paragraph is for the phase where we were to consider if we could make a function's code perform better or be easier to read/understand. We worked on the 'add an activity' function). There was no specific performance tradeoffs. the only tradeoff was in the code. It would be cleaner but it would run twice (once in conflict_warning, once in schedule_task).


Reflections for entire project:

The main tradeoff is taht we warn but don't block. schedule_task saves the task even when it conflicts, and returns the clashes for the UI to warn about, rather than refusing the save. That's reasonable because a busy owner sometimes intentionally double-books. A smaller code tradeoff: conflict_warning and schedule_task both call find_conflicts, so the overlap check runs twice — I accepted the minor duplication for cleaner, single-responsibility methods.
---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

I used AI to write and edit the code, find out edge-cases and logic-breaks, create tests, and refactor some parts of the code.

Prompts that were most helpful was prompts that asked AI what could go wrong, what was currently wrong with the code or what edge-cases to test.

This helps because AI can find out its own bugs, errors and ignorance, but it is almost impossible for AI to make zero-mistakes when first creating the code.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

Something I rejected from AI was it's suggestion to create a pciture for th UML diagram. I realised it was a wrong idea because it mentioned that the image was too long and not wide. It is helpful that the AI shares feedback after performing tasks.
---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

We wrote 53 tests covering sorting (chronological + priority tie-break), recurrence (occurs_on per frequency, month/year rollover in next_occurrence), conflict detection (overlap boundaries, cross-pet), per-day completion, and filtering. These matter because they're the core scheduling guarantees — if sorting or recurrence is wrong, every view is wrong.

b. Confidence

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

Confident enough, maybe about 4/5. We're pretty sure the logic works really well, but not everything in the User Interface and Command Line Interface are tested properly like input validation (zero-duration tasks or very long intervals).
---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?
I'm satisfied with the building part!

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

Maybe make it a standard GUI.

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

I learned that AI is really powerful but is not capable of going through an entire design and build loop on its own. I.e, AI will tell you it found errors, poor logic, and poor edge-case handling in the code it built, simply because it is incapable of making it right all at once. Therefore, AI can do a lot and is smart on its own but it needs guidance (someone like a pilot) to lead it in all its steps. 

Also, as the programmer, it's helpful to have a checklist to go through while building with AI because the first reason we build with AI is because we can't get things right all at once as well.


Reflect on AI Strategy: Specifically describe your experience with your AI coding assistant:
Which AI coding assistant features were most effective for building your scheduler?
Give one example of an AI suggestion you rejected or modified to keep your system design clean.
How did using separate chat sessions for different phases help you stay organized?
Summarize what you learned about being the "lead architect" when collaborating with powerful AI tools.