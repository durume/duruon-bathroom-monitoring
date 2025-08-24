
import unittest
from src.risk.engine import RiskEngine, RiskConfig
from src.pose_backends.mock_pose import sequence_hard_fall, sequence_soft_immobility

def run_seq(seq, fps=15):
    eng = RiskEngine(fps=fps, cfg=RiskConfig(soft_immobility_s=2.0, cooldown_s=1.0))  # shorten for test
    events = []
    for pose in seq:
        m = eng.update(pose)
        if m.get("event"):
            events.append(m["event"])
    return events

class TestRiskEngine(unittest.TestCase):
    def test_hard_fall_detects_once(self):
        events = run_seq(sequence_hard_fall(fps=15), fps=15)
        self.assertIn("hard_fall", events)
        self.assertEqual(events.count("hard_fall"), 1)

    def test_soft_immobility_triggers(self):
        events = run_seq(sequence_soft_immobility(fps=15, still_s=3.0), fps=15)
        self.assertIn("soft_immobility", events)

if __name__ == '__main__':
    unittest.main()
