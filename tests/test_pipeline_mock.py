import unittest
from src.pose_backends.mock_pose import MockBackend, sequence_hard_fall
from src.risk.engine import RiskEngine, RiskConfig
from src.notify.telegram import DummyNotifier
from src.utils.skeleton_draw import render_skeleton_image

class TestPipelineMock(unittest.TestCase):
    def test_pipeline_with_mock_backend(self):
        backend = MockBackend(sequence_hard_fall(fps=15))
        notifier = DummyNotifier()
        risk = RiskEngine(
            fps=15,
            cfg=RiskConfig(
                soft_immobility_s=2,
                hard_immobility_s=3,
                immobile_window_s=1.0,
                cooldown_s=1,
                movement_tolerance_low_angle=0.2,
                movement_tolerance_high_angle=0.05,
                shower_mode_enabled=False,
                shower_duration_multiplier=1.0,
            ),
        )

        saw_event = False
        img = None
        for _ in range(15*7):
            pose = backend.infer(None)
            m = risk.update(pose)
            if m.get("event"):
                saw_event = True
                notifier.send_text("alert")
                # Exercise skeleton rendering (ensures cv2 + drawing path works)
                img = render_skeleton_image(pose)
                break

        if img is not None:
            self.assertIsInstance(img, (bytes, bytearray))

        self.assertTrue(saw_event)
        self.assertTrue(any(k == "text" for k,_ in notifier.messages))

if __name__ == '__main__':
    unittest.main()
