import unittest

import numpy as np

from roastpilot.core.bt_filter import RateOfRiseFilter
from roastpilot.core.pid import PIDController
from roastpilot.core.ror_engine import target_at
from roastpilot.core.target_bt import generate_target_bt
from roastpilot.core.target_ror import generate_target_ror, ror_from_bt
from roastpilot.core.timeutil import parse_mmss


class TargetRoRTests(unittest.TestCase):
    def test_bt_passes_through_milestones(self):
        target = generate_target_ror(90, 300, 150, 510, 196, 660, 210)
        self.assertEqual(len(target.milestones), 4)
        self.assertAlmostEqual(target.bt_c[0], 90.0)
        self.assertAlmostEqual(target.bt_c[-1], 210.0)
        for milestone in target.milestones:
            index = int(abs(target.time_s - milestone.time_s).argmin())
            self.assertAlmostEqual(target.bt_c[index], milestone.temp_c, places=6)

    def test_uniform_one_second_sampling(self):
        target = generate_target_ror(90, 300, 150, 510, 196, 660, 210)
        steps = np.diff(target.time_s)
        self.assertTrue(np.all(steps[:-1] == 1.0))
        self.assertAlmostEqual(target.time_s[-1], 660.0)

    def test_ror_is_generated_from_bt_stream(self):
        target = generate_target_ror(90, 300, 150, 510, 196, 660, 210)
        estimator = RateOfRiseFilter(window_s=30)
        values = [estimator.add(float(t), float(bt)) for t, bt in zip(target.time_s, target.bt_c)]
        first = next(value for value in values if value is not None)
        expected = np.array([first if value is None else value for value in values], dtype=float)
        np.testing.assert_allclose(target.ror_c_per_min, expected)

    def test_bt_is_strictly_increasing(self):
        target = generate_target_ror(90, 300, 150, 510, 196, 660, 210)
        self.assertTrue(np.all(np.diff(target.bt_c) > 0))

    def test_time_parser_and_validation(self):
        self.assertEqual(parse_mmss("08:45"), 525)
        with self.assertRaises(ValueError):
            parse_mmss("8:60")
        with self.assertRaises(ValueError):
            generate_target_ror(150, 300, 150, 510, 196, 660, 210)  # start == DE temp
        with self.assertRaises(ValueError):
            generate_target_ror(90, 400, 150, 300, 196, 660, 210)  # DE after FC time

    def test_target_at_bounds(self):
        target = generate_target_ror(90, 300, 150, 510, 196, 660, 210)
        self.assertAlmostEqual(target_at(target, 0), target.ror_c_per_min[0])
        self.assertIsNone(target_at(target, -1))
        self.assertIsNone(target_at(target, 661))

    def test_target_bt_and_ror_are_separable(self):
        profile = generate_target_bt(90, 300, 150, 510, 196, 660, 210)
        self.assertEqual(len(profile.bt_c), len(profile.time_s))
        ror = ror_from_bt(profile, window_s=30)
        self.assertEqual(len(ror), len(profile.bt_c))
        combined = generate_target_ror(90, 300, 150, 510, 196, 660, 210)
        np.testing.assert_allclose(ror, combined.ror_c_per_min)
        np.testing.assert_allclose(profile.bt_c, combined.bt_c)

    def test_all_fit_methods_pass_through_milestones(self):
        for method in ("pchip", "cubic", "akima", "linear"):
            target = generate_target_ror(90, 300, 150, 510, 196, 660, 210, method=method)
            for milestone in target.milestones:
                index = int(abs(target.time_s - milestone.time_s).argmin())
                self.assertAlmostEqual(target.bt_c[index], milestone.temp_c, places=6)

    def test_decline_method_decreasing_ror_passes_milestones(self):
        target = generate_target_ror(90, 300, 180, 510, 222, 660, 237, method="decline")
        for milestone in target.milestones:
            index = int(abs(target.time_s - milestone.time_s).argmin())
            self.assertAlmostEqual(target.bt_c[index], milestone.temp_c, places=6)
        raw = np.gradient(target.bt_c, target.time_s / 60.0)
        self.assertTrue(np.all(np.diff(raw) <= 1e-6))

    def test_decline_method_rejects_non_declining_profile(self):
        with self.assertRaises(ValueError):
            generate_target_ror(90, 300, 150, 510, 196, 660, 210, method="decline")

    def test_unknown_fit_method_raises(self):
        with self.assertRaises(ValueError):
            generate_target_ror(90, 300, 150, 510, 196, 660, 210, method="nope")


class ControlTests(unittest.TestCase):
    def test_filter_recovers_a_linear_rate(self):
        estimate = RateOfRiseFilter(window_s=30)
        value = None
        for second in range(0, 31, 5):
            value = estimate.add(second, 100 + second / 6)
        self.assertAlmostEqual(value, 10.0, places=6)

    def test_pid_stays_bounded(self):
        pid = PIDController(kp=20, ki=1)
        self.assertEqual(pid.update(100, 0, 1), 100)
        self.assertEqual(pid.update(0, 100, 1), 0)


if __name__ == "__main__":
    unittest.main()
