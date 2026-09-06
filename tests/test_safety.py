import unittest

from roastpilot.safety import BurnerGuard, Watchdog, clamp_output


class ClampTests(unittest.TestCase):
    def test_clamp_bounds(self):
        self.assertEqual(clamp_output(-1), 0.0)
        self.assertEqual(clamp_output(50), 50.0)
        self.assertEqual(clamp_output(101), 100.0)


class BurnerGuardTests(unittest.TestCase):
    def test_clamps_absolute_limits(self):
        guard = BurnerGuard(max_slew_per_s=1000.0)
        self.assertEqual(guard.update(-10, 0.0), 0.0)
        self.assertEqual(guard.update(150, 1.0), 100.0)

    def test_limits_slew_rate(self):
        guard = BurnerGuard(max_slew_per_s=10.0)
        self.assertEqual(guard.update(100.0, 0.0), 100.0)
        # From 100 toward 0, the max step is 10 %/s * 1 s = 10 %.
        self.assertEqual(guard.update(0.0, 1.0), 90.0)

    def test_failsafe_on_stale_input(self):
        guard = BurnerGuard(stale_timeout_s=2.0)
        self.assertEqual(guard.update(80.0, 0.0), 80.0)
        self.assertEqual(guard.update(80.0, 10.0), 0.0)

    def test_emergency_stop_latches_to_zero(self):
        guard = BurnerGuard()
        guard.update(70.0, 0.0)
        guard.emergency_stop()
        self.assertTrue(guard.tripped)
        self.assertEqual(guard.update(70.0, 1.0), 0.0)
        guard.reset()
        self.assertFalse(guard.tripped)
        self.assertEqual(guard.update(70.0, 2.0), 70.0)

    def test_rejects_backwards_time(self):
        guard = BurnerGuard()
        guard.update(50.0, 2.0)
        with self.assertRaises(ValueError):
            guard.update(50.0, 1.0)


class WatchdogTests(unittest.TestCase):
    def test_expired_until_fed(self):
        watchdog = Watchdog(5.0)
        self.assertTrue(watchdog.is_expired(0.0))

    def test_expires_after_timeout(self):
        watchdog = Watchdog(5.0)
        watchdog.feed(0.0)
        self.assertFalse(watchdog.is_expired(4.9))
        self.assertTrue(watchdog.is_expired(5.1))

    def test_reset(self):
        watchdog = Watchdog(5.0)
        watchdog.feed(0.0)
        watchdog.reset()
        self.assertTrue(watchdog.is_expired(1.0))


if __name__ == "__main__":
    unittest.main()
