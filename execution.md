# Python CLI Alarm Clock

A minimal, interview-quality Python alarm clock — CLI only, no database, standard library only.

## Usage

```bash
python alarm_clock.py
```

### Commands

| Command | Description |
|---|---|
| `set HH:MM [label]` | Set an alarm |
| `list` | List all alarms |
| `cancel ID` | Cancel an active alarm by ID |
| `help` | Show commands |
| `quit` / `exit` | Shutdown cleanly |

### Example session

```
Alarm Clock
-----------

> set 14:30 Team meeting
Alarm 1 set for 14:30 — Team meeting

> set 14:30 Call
Alarm 2 set for 14:30 — Call

> list

ID    Time    Label                Status
-----------------------------------------
1     14:30   Team meeting         ACTIVE
2     14:30   Call                 ACTIVE

> cancel 2
Alarm 2 cancelled.

🔔  ALARM 1: Team meeting (14:30)
```

## Running tests

```bash
python -m pytest test_alarm_clock.py -v
# or
python -m unittest test_alarm_clock -v
```

## Architecture

```
CLI (main thread)  ──→  AlarmManager  ←──  AlarmMonitor (daemon thread)
                         (threading.Lock)
```

Two threads only:

- **Main thread** — reads input, parses commands, mutates alarm state.
- **Background daemon thread** — reads `datetime.now()` every 0.5 s, fires alarms whose time matches the current minute, marks them `TRIGGERED`.

## Design decisions

### One background thread, not one per alarm

An alarm is scheduled state, not a unit of work. A single monitoring loop checks all active alarms; per-alarm threads would add lifecycle overhead and synchronisation complexity for no benefit.

### No database

The specification explicitly prohibits one. In-memory state is correct for the given constraints. Persistence could be added later with a simple JSON file if requirements change.

### Explicit alarm status enum

`ACTIVE / CANCELLED / TRIGGERED` rather than a boolean. This prevents the common bug where a cancelled alarm shows up as `TRIGGERED`, and makes state transitions auditable.

### threading.Lock over queue / asyncio

The workload is lightweight I/O. A lock over a plain dict is sufficient and easy to reason about. A queue or asyncio event loop would be disproportionate.

### Daemon thread

The monitor thread is a daemon so it does not prevent the process from exiting when the main thread finishes.