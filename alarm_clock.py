"""
alarm_clock.py — Python CLI Alarm Clock
Architecture: main thread (CLI) + one background daemon thread (time monitor)
Shared state protected by threading.Lock
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

class AlarmStatus(Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    TRIGGERED = "TRIGGERED"


@dataclass
class Alarm:
    id: int
    time: str          # "HH:MM"
    label: str
    status: AlarmStatus = AlarmStatus.ACTIVE


# ---------------------------------------------------------------------------
# Alarm Manager — owns shared state and the lock
# ---------------------------------------------------------------------------

class AlarmManager:
    def __init__(self):
        self._alarms: dict[int, Alarm] = {}
        self._next_id = 1
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Mutations — must be called with lock held externally OR
    # the methods themselves acquire it
    # ------------------------------------------------------------------

    def add(self, time_str: str, label: str) -> Alarm:
        with self._lock:
            alarm = Alarm(id=self._next_id, time=time_str, label=label)
            self._alarms[self._next_id] = alarm
            self._next_id += 1
            return alarm

    def cancel(self, alarm_id: int) -> tuple[bool, str]:
        """Returns (success, message)."""
        with self._lock:
            alarm = self._alarms.get(alarm_id)
            if alarm is None:
                return False, f"Active alarm {alarm_id} not found."
            if alarm.status != AlarmStatus.ACTIVE:
                return False, f"Alarm {alarm_id} is already {alarm.status.value.lower()} and cannot be cancelled."
            alarm.status = AlarmStatus.CANCELLED
            return True, f"Alarm {alarm_id} cancelled."

    def list_alarms(self) -> list[Alarm]:
        with self._lock:
            return list(self._alarms.values())

    def get_active_alarms(self) -> list[Alarm]:
        with self._lock:
            return [a for a in self._alarms.values() if a.status == AlarmStatus.ACTIVE]

    def mark_triggered(self, alarm_id: int) -> None:
        with self._lock:
            alarm = self._alarms.get(alarm_id)
            if alarm and alarm.status == AlarmStatus.ACTIVE:
                alarm.status = AlarmStatus.TRIGGERED


# ---------------------------------------------------------------------------
# Background monitor thread
# ---------------------------------------------------------------------------

class AlarmMonitor(threading.Thread):
    """Daemon thread: checks system time every 0.5 s, fires matching alarms."""

    def __init__(self, manager: AlarmManager, clock=None):
        super().__init__(daemon=True)
        self._manager = manager
        self._clock = clock or (lambda: datetime.now().strftime("%H:%M"))
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            current = self._clock()
            for alarm in self._manager.get_active_alarms():
                if alarm.time == current:
                    # Mark triggered before printing to prevent re-fire
                    self._manager.mark_triggered(alarm.id)
                    self._fire(alarm)
            self._stop_event.wait(0.5)

    @staticmethod
    def _fire(alarm: Alarm):
        print(f"\n\a🔔  ALARM {alarm.id}: {alarm.label} ({alarm.time})")
        print("> ", end="", flush=True)   # re-prompt after interruption


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

def parse_time(time_str: str) -> tuple[bool, str]:
    """Returns (valid, message). Message is empty string on success."""
    parts = time_str.split(":")
    if len(parts) != 2:
        return False, "Invalid time format. Use HH:MM (e.g. 14:30)."
    hh, mm = parts
    if not (hh.isdigit() and mm.isdigit()):
        return False, "Invalid time format. Use HH:MM (e.g. 14:30)."
    if not (0 <= int(hh) <= 23):
        return False, f"Invalid hour '{hh}'. Must be 00–23."
    if not (0 <= int(mm) <= 59):
        return False, f"Invalid minute '{mm}'. Must be 00–59."
    # Normalise to zero-padded form
    return True, f"{int(hh):02d}:{int(mm):02d}"


def parse_alarm_id(token: str) -> tuple[bool, int | str]:
    """Returns (valid, int id) or (False, error_message)."""
    if not token.isdigit():
        return False, "ID must be a number."
    return True, int(token)


# ---------------------------------------------------------------------------
# CLI layer
# ---------------------------------------------------------------------------

HELP_TEXT = """\
Commands:
  set HH:MM [label]   — Add an alarm
  list                — List all alarms
  cancel ID           — Cancel an active alarm by ID
  help                — Show this help
  quit / exit         — Shutdown"""


def print_alarm_table(alarms: list[Alarm]):
    if not alarms:
        print("No alarms set.")
        return
    header = f"{'ID':<5} {'Time':<7} {'Label':<20} {'Status'}"
    print("\n" + header)
    print("-" * len(header))
    for a in alarms:
        print(f"{a.id:<5} {a.time:<7} {a.label:<20} {a.status.value}")
    print()


def handle_set(tokens: list[str], manager: AlarmManager):
    if not tokens:
        print("Usage: set HH:MM [label]")
        return
    valid, result = parse_time(tokens[0])
    if not valid:
        print(result)
        return
    normalised_time = result
    label = " ".join(tokens[1:]) if len(tokens) > 1 else "Alarm"
    alarm = manager.add(normalised_time, label)
    print(f"Alarm {alarm.id} set for {alarm.time} — {alarm.label}")


def handle_cancel(tokens: list[str], manager: AlarmManager):
    if not tokens:
        print("Usage: cancel ID")
        return
    valid, result = parse_alarm_id(tokens[0])
    if not valid:
        print(result)
        return
    success, message = manager.cancel(result)
    print(message)


def run_cli(manager: AlarmManager):
    print("\nAlarm Clock")
    print("-----------")
    print(HELP_TEXT)
    print()

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nShutting down. Goodbye!")
            break

        if not raw:
            continue

        parts = raw.split()
        cmd, tokens = parts[0].lower(), parts[1:]

        if cmd in ("quit", "exit"):
            print("Shutting down. Goodbye!")
            break
        elif cmd == "set":
            handle_set(tokens, manager)
        elif cmd == "list":
            print_alarm_table(manager.list_alarms())
        elif cmd == "cancel":
            handle_cancel(tokens, manager)
        elif cmd == "help":
            print(HELP_TEXT)
        else:
            print(f"Unknown command '{cmd}'. Type 'help'.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    manager = AlarmManager()
    monitor = AlarmMonitor(manager)
    monitor.start()
    try:
        run_cli(manager)
    finally:
        monitor.stop()


if __name__ == "__main__":
    main()
