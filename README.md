# alarm_clock_cli_btr

Task for Senior Software Engineer role: Build an alarm clock as a Python CLI application.

**Constraints:**

- CLI only
- No web UI
- No React
- No database
- No detailed specification — make reasonable engineering decisions based on the available time

---

# Requirements

The application provides a simple CLI-based alarm clock supporting:

- Set an alarm for a specific time
- Assign an optional label to an alarm
- Set multiple alarms
- List active alarms
- Cancel an alarm
- Trigger an alarm when its scheduled time is reached
- Validate alarm input before accepting it
- Gracefully handle invalid commands and input
- Gracefully shut down the application

## Validation

The following cases are considered before an alarm is accepted or acted upon:

- Invalid time format
- Invalid time values
- Cancellation of an alarm
- Multiple alarms
- Alarm triggering
- Invalid alarm IDs
- Invalid CLI commands

---

# Persistence Decision

The application intentionally does not use database storage.

The specification explicitly prohibits the use of a database, so alarms are stored only in memory for the lifetime of the application.

We will be focused on:

- Correctness
- Concurrency
- Input validation
- Alarm lifecycle management
- Clean CLI interaction
- Maintainable code

All alarms are expected to disappear when the application exits.

Persistence could be introduced in a production version if the requirements change, but for now excluded from this implementation.


# Intended Architecture


                         ┌───────────────────────────────┐
                         │          CLI / INPUT          │
                         │                               │
                         │        Alarm Clock CLI        │
                         │                               │
                         │  set | list | cancel | quit   │
                         └───────────────┬───────────────┘
                                         │
                                         │ commands
                                         ▼
                         ┌───────────────────────────────┐
                         │        ALARM MANAGER          │
                         │                               │
                         │  • Set alarms                 │
                         │  • List alarms                │
                         │  • Cancel alarms              │
                         │  • Manage alarm state         │
                         └───────────────┬───────────────┘
                                         │
                                         ▼
                         ┌───────────────────────────────┐
                         │       IN-MEMORY ALARMS        │
                         │                               │
                         │  • Alarm ID                   │
                         │  • Scheduled time             │
                         │  • Label                      │
                         │  • Active / Triggered state   │
                         │                               │
                         │  Protected by threading.Lock  │
                         └───────────────┬───────────────┘
                                         ▲
                                         │
                              Shared alarm state
                                         │
                         ┌───────────────┴───────────────┐
                         │      BACKGROUND THREAD        │
                         │                               │
                         │  • Read current time          │
                         │  • Check active alarms        │
                         │  • Find matching alarms       │
                         │  • Trigger matching alarms    │
                         │  • Sleep and repeat           │
                         └───────────────┬───────────────┘
                                         │
                                         │ time matches
                                         ▼
                              ┌─────────────────────┐
                              │      🔔 TRIGGER     │
                              │                     │
                              │     Alarm fires     │
                              │    Terminal alert   │
                              └─────────────────────┘


                            Each service has its own thread -> discarded.
                            why?
                            read, comapre, updating in-memory alarm details
                            We dont CPU intensicve work, also we do not more threads than 2. Reason being with more threads we need to maintain co ordinatiobn and synchronization between them.

                            Two threads 1) Main CLI thread and  2) Background handler thread.

                            thread 1 -access-> alarm details 

                            same time

                            thread 2 -access -> alarm details

                            There would be a ambiguity to avoid this race condition we use Threading.Loack.

                            This helps to avoid the case like 
                            Main thread: cancel alarm

                            Background thread:
                            Update alarm. Race condn can be avoided with the threading lock.