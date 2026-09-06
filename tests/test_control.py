import unittest

from roastpilot.core.control import ControlPolicy, GasEnvelope


class GasEnvelopeTests(unittest.TestCase):
    def test_clamp(self):
        envelope = GasEnvelope(10, 80)
        self.assertEqual(envelope.clamp(5), 10)
        self.assertEqual(envelope.clamp(50), 50)
        self.assertEqual(envelope.clamp(90), 80)


class ControlPolicyTests(unittest.TestCase):
    def test_phase_by_elapsed_time(self):
        policy = ControlPolicy()
        self.assertEqual(policy.phase(0, 300, 510), "drying")
        self.assertEqual(policy.phase(299, 300, 510), "drying")
        self.assertEqual(policy.phase(300, 300, 510), "maillard")
        self.assertEqual(policy.phase(509, 300, 510), "maillard")
        self.assertEqual(policy.phase(510, 300, 510), "development")

    def test_clamp_to_envelope(self):
        policy = ControlPolicy(drying=GasEnvelope(30, 100))
        self.assertEqual(policy.clamp_to_envelope(150, "drying"), 100)
        self.assertEqual(policy.clamp_to_envelope(10, "drying"), 30)

    def test_gain_scale_ramps_down_near_fc(self):
        policy = ControlPolicy(fc_gain_scale=0.5, fc_gain_ramp_s=30)
        self.assertEqual(policy.gain_scale(400, 510), 1.0)
        self.assertEqual(policy.gain_scale(480, 510), 1.0)  # ramp start
        self.assertEqual(policy.gain_scale(495, 510), 0.75)  # halfway
        self.assertEqual(policy.gain_scale(510, 510), 0.5)  # at FC
        self.assertEqual(policy.gain_scale(600, 510), 0.5)  # after FC

    def test_gain_scale_disabled(self):
        policy = ControlPolicy(fc_gain_scale=1.0, fc_gain_ramp_s=30)
        self.assertEqual(policy.gain_scale(600, 510), 1.0)


if __name__ == "__main__":
    unittest.main()
