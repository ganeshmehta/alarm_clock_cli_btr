"""
test_alarm_clock.py — Unit tests for the CLI alarm clock.

Clock injection is used throughout so tests never wait for wall-clock time.
"""

import threading
import time
import unittest

from alarm_clock import (
    Alarm,
    AlarmManager,
    AlarmMonitor,
    AlarmStatus,
    handle_cancel,
    handle_set,
    parse_alarm_id,
    parse_time,
)


# ---------------------------------------------------------------------------
# parse_time
# ---------------------------------------------------------------------------

class TestParseTime(unittest.TestCase):

    def test_valid_time(self):
        ok, result = parse_time("14:30")
        self.assertTrue(ok)
        self.assertEqual(result, "14:30")

    def test_normalises_single_digit(self):
        ok, result = parse_time("9:05")
        self.assertTrue(ok)
        self.assertEqual(result, "09:05")

    def test_invalid_hour(self):
        ok, msg = parse_time("25:00")
        self.assertFalse(ok)
        self.assertIn("hour", msg)

    def test_invalid_minute(self):
        ok, msg = parse_time("12:60")
        self.assertFalse(ok)
        self.assertIn("minute", msg)

    def test_missing_colon(self):
        ok, msg = parse_time("1430")
        self.assertFalse(ok)

    def test_non_numeric(self):
        ok, msg = parse_time("ab:cd")
        self.assertFalse(ok)

    def test_boundary_midnight(self):
        ok, result = parse_time("00:00")
        self.assertTrue(ok)
        self.assertEqual(result, "00:00")

    def test_boundary_end_of_day(self):
        ok, result = parse_time("23:59")
        self.assertTrue(ok)
        self.assertEqual(result, "23:59")


# ---------------------------------------------------------------------------
# parse_alarm_id
# ---------------------------------------------------------------------------

class TestParseAlarmId(unittest.TestCase):

    def test_valid_id(self):
        ok, result = parse_alarm_id("3")
        self.assertTrue(ok)
        self.assertEqual(result, 3)

    def test_alpha_id(self):
        ok, msg = parse_alarm_id("abc")
        self.assertFalse(ok)
        self.assertIn("number", msg)

    def test_float_id(self):
        ok, msg = parse_alarm_id("1.5")
        self.assertFalse(ok)


# ---------------------------------------------------------------------------
# AlarmManager
# ---------------------------------------------------------------------------

class TestAlarmManager(unittest.TestCase):

    def setUp(self):
        self.mgr = AlarmManager()

    # --- add ---

    def test_add_single(self):
        alarm = self.mgr.add("09:00", "Wake up")
        self.assertEqual(alarm.id, 1)
        self.assertEqual(alarm.time, "09:00")
        self.assertEqual(alarm.label, "Wake up")
        self.assertEqual(alarm.status, AlarmStatus.ACTIVE)

    def test_add_multiple_increments_id(self):
        a1 = self.mgr.add("09:00", "First")
        a2 = self.mgr.add("10:00", "Second")
        self.assertEqual(a1.id, 1)
        self.assertEqual(a2.id, 2)

    # --- list ---

    def test_list_empty(self):
        self.assertEqual(self.mgr.list_alarms(), [])

    def test_list_returns_all(self):
        self.mgr.add("09:00", "A")
        self.mgr.add("10:00", "B")
        alarms = self.mgr.list_alarms()
        self.assertEqual(len(alarms), 2)

    # --- cancel ---

    def test_cancel_active(self):
        alarm = self.mgr.add("09:00", "Test")
        ok, msg = self.mgr.cancel(alarm.id)
        self.assertTrue(ok)
        self.assertEqual(alarm.status, AlarmStatus.CANCELLED)

    def test_cancel_nonexistent(self):
        ok, msg = self.mgr.cancel(999)
        self.assertFalse(ok)
        self.assertIn("not found", msg)

    def test_cancel_already_cancelled(self):
        alarm = self.mgr.add("09:00", "Test")
        self.mgr.cancel(alarm.id)
        ok, msg = self.mgr.cancel(alarm.id)
        self.assertFalse(ok)
        self.assertIn("cancelled", msg)

    def test_cancel_triggered_alarm(self):
        alarm = self.mgr.add("09:00", "Test")
        self.mgr.mark_triggered(alarm.id)
        ok, msg = self.mgr.cancel(alarm.id)
        self.assertFalse(ok)

    # --- get_active_alarms ---

    def test_active_alarms_excludes_cancelled(self):
        a1 = self.mgr.add("09:00", "A")
        a2 = self.mgr.add("10:00", "B")
        self.mgr.cancel(a1.id)
        active = self.mgr.get_active_alarms()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].id, a2.id)

    # --- mark_triggered ---

    def test_mark_triggered(self):
        alarm = self.mgr.add("09:00", "Test")
        self.mgr.mark_triggered(alarm.id)
        self.assertEqual(alarm.status, AlarmStatus.TRIGGERED)

    def test_mark_triggered_ignores_cancelled(self):
        alarm = self.mgr.add("09:00", "Test")
        self.mgr.cancel(alarm.id)
        self.mgr.mark_triggered(alarm.id)  # should be a no-op
        self.assertEqual(alarm.status, AlarmStatus.CANCELLED)


# ---------------------------------------------------------------------------
# AlarmMonitor (injected clock)
# ---------------------------------------------------------------------------

class TestAlarmMonitor(unittest.TestCase):

    def _make_monitor(self, clock_fn):
        mgr = AlarmManager()
        monitor = AlarmMonitor(mgr, clock=clock_fn)
        return mgr, monitor

    def test_fires_matching_alarm(self):
        fired = []
        original_fire = AlarmMonitor._fire.__func__ if hasattr(AlarmMonitor._fire, '__func__') else AlarmMonitor._fire

        mgr, monitor = self._make_monitor(clock_fn=lambda: "09:00")
        alarm = mgr.add("09:00", "Test")

        # Patch _fire to capture instead of printing
        monitor._fire = lambda a: fired.append(a.id)

        monitor.start()
        time.sleep(0.2)
        monitor.stop()
        monitor.join(timeout=1)

        self.assertIn(alarm.id, fired)
        self.assertEqual(alarm.status, AlarmStatus.TRIGGERED)

    def test_does_not_fire_cancelled_alarm(self):
        fired = []

        mgr, monitor = self._make_monitor(clock_fn=lambda: "09:00")
        alarm = mgr.add("09:00", "Test")
        mgr.cancel(alarm.id)

        monitor._fire = lambda a: fired.append(a.id)

        monitor.start()
        time.sleep(0.2)
        monitor.stop()
        monitor.join(timeout=1)

        self.assertNotIn(alarm.id, fired)

    def test_does_not_fire_twice(self):
        fired = []

        mgr, monitor = self._make_monitor(clock_fn=lambda: "09:00")
        alarm = mgr.add("09:00", "Once only")
        monitor._fire = lambda a: fired.append(a.id)

        monitor.start()
        time.sleep(0.8)   # enough for multiple check cycles
        monitor.stop()
        monitor.join(timeout=1)

        self.assertEqual(fired.count(alarm.id), 1)

    def test_fires_multiple_alarms_at_same_time(self):
        fired = []

        mgr, monitor = self._make_monitor(clock_fn=lambda: "09:00")
        a1 = mgr.add("09:00", "First")
        a2 = mgr.add("09:00", "Second")
        monitor._fire = lambda a: fired.append(a.id)

        monitor.start()
        time.sleep(0.2)
        monitor.stop()
        monitor.join(timeout=1)

        self.assertIn(a1.id, fired)
        self.assertIn(a2.id, fired)

    def test_does_not_fire_wrong_time(self):
        fired = []

        mgr, monitor = self._make_monitor(clock_fn=lambda: "10:00")
        alarm = mgr.add("09:00", "Morning")
        monitor._fire = lambda a: fired.append(a.id)

        monitor.start()
        time.sleep(0.2)
        monitor.stop()
        monitor.join(timeout=1)

        self.assertNotIn(alarm.id, fired)

    def test_monitor_is_daemon(self):
        mgr, monitor = self._make_monitor(clock_fn=lambda: "00:00")
        self.assertTrue(monitor.daemon)

    def test_stop_terminates_thread(self):
        mgr, monitor = self._make_monitor(clock_fn=lambda: "00:00")
        monitor.start()
        monitor.stop()
        monitor.join(timeout=1)
        self.assertFalse(monitor.is_alive())


# ---------------------------------------------------------------------------
# CLI command handlers (lightweight integration)
# ---------------------------------------------------------------------------

class TestHandleSet(unittest.TestCase):

    def setUp(self):
        self.mgr = AlarmManager()

    def test_set_valid(self):
        handle_set(["09:00", "Stand-up"], self.mgr)
        alarms = self.mgr.list_alarms()
        self.assertEqual(len(alarms), 1)
        self.assertEqual(alarms[0].time, "09:00")
        self.assertEqual(alarms[0].label, "Stand-up")

    def test_set_default_label(self):
        handle_set(["09:00"], self.mgr)
        self.assertEqual(self.mgr.list_alarms()[0].label, "Alarm")

    def test_set_invalid_time_does_not_add(self):
        handle_set(["99:00"], self.mgr)
        self.assertEqual(self.mgr.list_alarms(), [])

    def test_set_multiword_label(self):
        handle_set(["09:00", "Team", "meeting"], self.mgr)
        self.assertEqual(self.mgr.list_alarms()[0].label, "Team meeting")


class TestHandleCancel(unittest.TestCase):

    def setUp(self):
        self.mgr = AlarmManager()
        self.mgr.add("09:00", "Test")

    def test_cancel_valid(self):
        handle_cancel(["1"], self.mgr)
        self.assertEqual(self.mgr.list_alarms()[0].status, AlarmStatus.CANCELLED)

    def test_cancel_nonexistent(self):
        # Should print error but not crash
        handle_cancel(["999"], self.mgr)

    def test_cancel_non_numeric(self):
        handle_cancel(["abc"], self.mgr)

    def test_cancel_no_args(self):
        handle_cancel([], self.mgr)


# ---------------------------------------------------------------------------
# Thread safety smoke test
# ---------------------------------------------------------------------------

class TestThreadSafety(unittest.TestCase):

    def test_concurrent_adds_produce_unique_ids(self):
        mgr = AlarmManager()
        results = []
        lock = threading.Lock()

        def add_alarm(t):
            alarm = mgr.add(t, "Concurrent")
            with lock:
                results.append(alarm.id)

        threads = [threading.Thread(target=add_alarm, args=("09:00",)) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 50)
        self.assertEqual(len(set(results)), 50)   # all IDs unique


if __name__ == "__main__":
    unittest.main(verbosity=2)
