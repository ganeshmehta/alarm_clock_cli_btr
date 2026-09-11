# Skill: Python CLI Alarm Clock Interview Task

## Purpose

Guide the design, implementation, review, and explanation of a small Python CLI alarm-clock application for a senior software-engineering take-home/interview task with a short implementation window.

The skill emphasizes:
- Requirement refinement before coding
- Constraint-driven design
- Clean CLI behavior
- Multiple alarms
- Validation and error handling
- Simple, justified concurrency
- Thread-safe in-memory state
- Clear architectural trade-offs
- Interview-ready explanation of design decisions

## Task Constraints

The application is intentionally constrained:

- CLI only
- No web UI
- No React
- No database
- Limited implementation time (approximately 30 minutes)
- The specification is intentionally open-ended
- The candidate should use AI before coding to refine requirements, architecture, implementation, and edge cases

Do not introduce unnecessary infrastructure or dependencies.

## Recommended MVP Requirements

Implement the smallest complete alarm-clock system that demonstrates engineering judgment.

### Core functionality

1. Set an alarm
   - Input format: `set HH:MM [label]`
   - Example: `set 14:30 Meeting`

2. Support multiple alarms
   - Each alarm receives a unique numeric ID.

3. List alarms
   - Show ID, time, label, and status.

4. Cancel an alarm
   - Input format: `cancel ID`

5. Trigger alarms
   - Continuously monitor the current system time.
   - When an active alarm matches the current time, trigger it.
   - Mark it as triggered so it does not fire repeatedly.

6. Help and shutdown
   - `help`
   - `quit` / `exit`

### Validation

At minimum validate:

- Time format
- Valid hour/minute ranges
- Alarm ID format
- Command syntax
- Alarm existence
- Cancellation of only active alarms
- Clearly defined behavior for alarms scheduled in the past/current minute

Invalid input should produce a useful message rather than crashing the application.

## Persistence Decision

Do not add a database.

The task explicitly prohibits databases. Therefore alarms should live only in memory for the lifetime of the application.

This is a deliberate constraint-driven decision, not an omission.

A good interview explanation:

> Persistence is intentionally excluded because the specification explicitly prohibits a database. Given the limited implementation time, I prioritized correctness, validation, concurrency, thread safety, and a clean CLI experience.

## Architecture

The preferred architecture is:

```text
                    +-------------------------+
                    |       CLI / INPUT       |
                    |                         |
                    | set | list | cancel     |
                    | help | quit             |
                    +------------+------------+
                                 |
                                 v
                    +-------------------------+
                    |     ALARM MANAGER       |
                    |                         |
                    | - Set alarms            |
                    | - List alarms           |
                    | - Cancel alarms         |
                    | - Manage alarm state    |
                    +------------+------------+
                                 |
                                 v
                    +-------------------------+
                    |    IN-MEMORY ALARMS     |
                    |                         |
                    | Alarm objects stored    |
                    | in memory               |
                    |                         |
                    | Protected by Lock       |
                    +------------+------------+
                                 |
                                 v
                    +-------------------------+
                    |   BACKGROUND CHECKER    |
                    |                         |
                    | Separate daemon thread  |
                    |                         |
                    | - Check current time    |
                    | - Match active alarms   |
                    | - Trigger alarm         |
                    +------------+------------+
                                 |
                                 | time matches
                                 v
                    +-------------------------+
                    |       ALARM FIRED       |
                    |                         |
                    | Terminal message/bell   |
                    +-------------------------+
```

## Concurrency Model

Use two threads:

### Main thread

Responsible for:

- Reading CLI input
- Parsing commands
- Setting alarms
- Listing alarms
- Cancelling alarms
- Handling shutdown

### Background daemon thread

Responsible for:

- Reading the system clock
- Checking active alarms
- Triggering matching alarms
- Marking alarms as triggered
- Sleeping briefly before checking again

The system clock itself is not a thread. The background thread reads the current time using `datetime.now()`.

## Why One Background Thread?

Do not create one thread per alarm.

An alarm is simply scheduled state. A single lightweight monitoring loop can check all active alarms.

One thread per alarm would add:

- Thread-management overhead
- More lifecycle complexity
- More synchronization points
- More complicated shutdown behavior
- No meaningful benefit for a small number of lightweight alarms

The design principle is:

> Use concurrency based on responsibility rather than creating concurrency per data item.

## Why Not Multiple Worker Threads?

Multiple workers are unnecessary because:

- Checking alarms is lightweight
- There is no significant CPU-heavy workload
- There is no meaningful blocking workload requiring a worker pool
- More threads would add coordination complexity

Concurrency should solve a real problem rather than exist for its own sake.

## Why Not a Separate Process?

A separate process is unnecessary because the application does not require:

- CPU-heavy computation
- Process isolation
- Independent failure boundaries
- Separate memory spaces

Processes would also make shared alarm state more complicated because the main and monitoring components would need inter-process communication or another state-sharing mechanism.

A thread is the simpler fit.

## Shared State and Thread Safety

The main thread and background thread both access the alarm collection.

Therefore protect shared mutable state with `threading.Lock`.

Example race:

```text
Main thread                  Background thread
-----------                  -----------------
cancel alarm 1               check alarm 1
                             sees it as active
                             triggers alarm
```

A lock ensures that state transitions are synchronized.

Keep critical sections small where practical.

## Alarm Lifecycle

Represent alarm state explicitly:

```text
CREATED
   |
   v
ACTIVE
 /   v     v
CANCELLED   TRIGGERED
```

Use explicit states rather than treating every inactive alarm as triggered.

Recommended states:

- `ACTIVE`
- `CANCELLED`
- `TRIGGERED`

This prevents a common bug where a cancelled alarm is displayed as `TRIGGERED`.

## Suggested Data Model

A simple dataclass is sufficient:

```python
@dataclass
class Alarm:
    id: int
    time: str
    label: str
    status: AlarmStatus = AlarmStatus.ACTIVE
```

An enum can represent status:

```python
class AlarmStatus(Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    TRIGGERED = "TRIGGERED"
```

This is clearer than a single boolean such as `active`.

## Time Checking

A straightforward implementation can:

1. Read `datetime.now()`
2. Convert it to `HH:MM`
3. Check active alarms
4. Trigger matching alarms
5. Mark them as triggered
6. Sleep briefly
7. Repeat

For example, checking every 0.5 seconds is simple and responsive while still avoiding unnecessary busy looping.

To prevent duplicate triggering within the same minute, either:

- Track the last processed minute, or
- Mark the alarm as `TRIGGERED` immediately after firing

The latter is essential even if minute-level deduplication is also used.

## Recommended Input Examples

```text
Alarm Clock
-----------

Commands:
  set HH:MM [label]
  list
  cancel ID
  help
  quit

> set 14:30 Team meeting
Alarm 1 set for 14:30 - Team meeting

> set 14:30 Call
Alarm 2 set for 14:30 - Call

> list

ID   Time    Label              Status
---------------------------------------------
1    14:30   Team meeting       ACTIVE
2    14:30   Call               ACTIVE

> cancel 2
Alarm 2 cancelled.

> list

ID   Time    Label              Status
---------------------------------------------
1    14:30   Team meeting       ACTIVE
2    14:30   Call               CANCELLED
```

When the time is reached:

```text
ALARM 1: Team meeting (14:30)
```

Optionally emit the terminal bell using `\a`.

## Error Handling

The CLI should remain running after invalid input.

Examples:

```text
> set 25:99
Invalid time. Please use HH:MM format.

> cancel abc
ID must be a number.

> cancel 999
Active alarm 999 not found.

> something
Unknown command. Type 'help'.
```

Avoid uncaught exceptions for expected user mistakes.

## Testing Strategy

Test at least:

### Input validation

- Valid `HH:MM`
- Invalid hour
- Invalid minute
- Invalid syntax
- Invalid alarm ID

### Alarm management

- Create one alarm
- Create multiple alarms
- List alarms
- Cancel an active alarm
- Attempt to cancel a nonexistent alarm
- Attempt to cancel an already terminal alarm

### Triggering

- Alarm triggers at the expected time
- Triggered alarm does not fire repeatedly
- Multiple alarms at the same time all trigger
- Cancelled alarm does not trigger

### Shutdown

- `quit` exits cleanly
- `Ctrl+C` exits cleanly
- Background monitoring thread does not keep the process alive

For production-quality testing, inject the clock/time source so tests do not have to wait for real wall-clock time.

## Design Trade-offs

### Included

- Core alarm management
- Multiple alarms
- Validation
- Cancellation
- Triggering
- Thread-safe shared state
- Graceful shutdown
- Clean CLI

### Intentionally excluded

- Database persistence
- Web UI
- React
- Recurring alarms
- Snooze
- External notifications
- Distributed architecture
- Authentication
- Message queues

These are outside the stated requirements and/or unnecessary for the time constraint.

## Senior-Level Design Principles to Explain

The implementation should demonstrate judgment rather than complexity.

Key principles:

1. Start from requirements and constraints.
2. Build the smallest complete solution.
3. Add concurrency only where it provides a clear benefit.
4. Avoid architecture that is disproportionate to the workload.
5. Protect shared mutable state.
6. Make state transitions explicit.
7. Handle expected user errors gracefully.
8. Explain why features were intentionally omitted.
9. Keep the code easy to understand and modify.
10. Prefer standard-library solutions for a small standalone task.

## AI-Assisted Development Talking Points

The interviewer expects AI to be used before coding.

Explain AI usage as assistance in:

- Refining ambiguous requirements
- Identifying edge cases
- Comparing concurrency approaches
- Reviewing the architecture
- Checking validation behavior
- Reviewing implementation quality
- Identifying race conditions
- Improving the testing strategy

Do not present AI as the decision-maker.

A strong explanation is:

> I used AI to challenge the requirements and compare implementation options, especially around concurrency, validation, and edge cases. I then selected the final design based on the task constraints and the actual workload.

## Interview Explanation

A concise architecture explanation:

> The application has two threads. The main thread handles CLI interaction, while a single background daemon thread monitors the system time and checks all active alarms. Both threads share an in-memory alarm collection protected by a lock.
>
> I deliberately avoided one thread per alarm because an alarm is just scheduled state and one monitoring thread is sufficient. I also avoided multiple workers and a separate process because there is no CPU-heavy workload or need for process isolation.
>
> Persistence is intentionally excluded because the specification prohibits a database. This lets the implementation focus on correctness, validation, thread safety, and a clean CLI experience.

## Future Improvements

If requirements expand, possible additions include:

- Recurring alarms
- Snooze
- Persistent storage when permitted
- Better terminal notification mechanisms
- Unit tests with an injectable clock
- Modular separation into CLI, service, and model modules
- Configuration
- Structured logging

Do not add these merely to make the interview solution appear more sophisticated.

## Implementation Review Checklist

Before submitting, verify:

- [ ] CLI works without a web interface
- [ ] No database is used
- [ ] Multiple alarms work
- [ ] Alarm IDs are unique
- [ ] Time input is validated
- [ ] Alarm status distinguishes active/cancelled/triggered
- [ ] Cancelled alarms cannot trigger
- [ ] Triggered alarms cannot trigger again
- [ ] Same-time alarms can all trigger
- [ ] Shared state is protected by a lock
- [ ] Background thread is daemonized
- [ ] Shutdown is clean
- [ ] Invalid commands do not crash the app
- [ ] README explains design decisions
- [ ] Architecture decisions can be defended verbally
