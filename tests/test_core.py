import unittest

import numpy as np

from roastpilot.core.bt_filter import RateOfRiseFilter
from roastpilot.core.pid import PIDController
from roastpilot.core.ror_engine import target_at
from roastpilot.core.target_ror import generate_target_ror, parse_mmss


class TargetRoRTests(unittest.TestCase):
    def test_profile_integrates_to_each_temperature_change(self):
        target = generate_target_ror(300, 150, 510, 196, 660, 210, charge_temp_c=25)
        self.assertAlmostEqual(target.ror_c_per_min[0] > target.ror_c_per_min[-1], True)
        self.assertAlmostEqual(target_at(target, 0), target.ror_c_per_min[0])
        self.assertIsNone(target_at(target, -1))

    def test_time_parser_and_validation(self):
        self.assertEqual(parse_mmss("08:45"), 525)
        with self.assertRaises(ValueError): parse_mmss("8:60")
        with self.assertRaises(ValueError): generate_target_ror(500, 150, 400, 196, 660, 210)

    def test_high_charge_profile_has_a_falling_turn_phase(self):
        target = generate_target_ror(
            300, 150, 510, 196, 660, 210,
            charge_temp_c=200, turn_time_s=90, turn_temp_c=90,
        )
        self.assertEqual(len(target.milestones), 5)
        self.assertAlmostEqual(target.bt_c[0], 90.0)
        self.assertAlmostEqual(target.bt_c[-1], 210.0)
        self.assertGreater(target.ror_c_per_min[0], 0)
        self.assertIsNotNone(target_at(target, 90))
        self.assertIsNone(target_at(target, 89.9))

    def test_target_ror_has_no_phase_boundary_steps(self):
        target = generate_target_ror(
            300, 150, 510, 196, 660, 210,
            charge_temp_c=200, turn_time_s=90, turn_temp_c=90,
        )
        for milestone in target.milestones[1:-1]:
            index = int(abs(target.time_s - milestone.time_s).argmin())
            if index == 0:
                continue
            # A high-charge turn may recover sharply, but the spline must not
            # create the 5–15 °C/min vertical steps of the former phase joins.
            self.assertLess(abs(target.ror_c_per_min[index + 1] - target.ror_c_per_min[index - 1]), 3.0)

    def test_target_ror_is_the_derivative_of_target_bt(self):
        target = generate_target_ror(
            300, 150, 510, 196, 660, 210,
            charge_temp_c=200, turn_time_s=90, turn_temp_c=90,
        )
        numerical_ror = np.gradient(target.bt_c, target.time_s / 60.0)
        mask = np.ones(len(target.time_s), dtype=bool)
        for milestone in target.milestones:
            index = int(abs(target.time_s - milestone.time_s).argmin())
            mask[max(0, index - 2):index + 3] = False
        np.testing.assert_allclose(
            target.ror_c_per_min[mask], numerical_ror[mask], atol=0.15,
        )


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
