import unittest

from roastpilot.core.simulator import RoastSimulator


class RoastSimulatorTests(unittest.TestCase):
    def test_burner_drives_positive_ror(self):
        sim = RoastSimulator()
        ror = 0.0
        for _ in range(50):
            ror = sim.step(100.0, 25.0, 3.0)
        self.assertGreater(ror, 0.0)
        self.assertLess(ror, sim.gain * 100.0)

    def test_zero_burner_at_ambient_settles_to_neutral(self):
        sim = RoastSimulator()
        sim.ror_c_per_min = 10.0
        ror = 10.0
        for _ in range(100):
            ror = sim.step(0.0, 25.0, 3.0)
        self.assertAlmostEqual(ror, 0.0, places=3)

    def test_hot_bean_drives_negative_ror_at_zero_burner(self):
        sim = RoastSimulator()
        ror = sim.step(0.0, 200.0, 3.0)
        self.assertLess(ror, 0.0)

    def test_reset(self):
        sim = RoastSimulator()
        sim.step(100.0, 25.0, 3.0)
        sim.reset()
        self.assertEqual(sim.ror_c_per_min, 0.0)


if __name__ == "__main__":
    unittest.main()
