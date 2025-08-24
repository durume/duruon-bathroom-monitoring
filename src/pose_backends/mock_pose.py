
import time, itertools
from typing import Iterator, Dict, Tuple, List
from ..shared.pose import PoseResult, COCO17

def _make_empty_kp() -> Dict[str, Tuple[float,float,float]]:
    return {name:(0.0,0.0,0.0) for name in COCO17}

def sequence_hard_fall(fps: int = 15) -> Iterator[PoseResult]:
    # 1s standing, 0.5s drop, 5s flat & immobile
    now = time.time()
    # Standing (hips y=0.5, shoulders y=0.3)
    for i in range(fps):
        kp = _make_empty_kp()
        kp["left_hip"] = (0.5, 0.50, 0.9); kp["right_hip"] = (0.5, 0.50, 0.9)
        kp["left_shoulder"] = (0.5, 0.30, 0.9); kp["right_shoulder"] = (0.5, 0.30, 0.9)
        yield PoseResult(kp, 0.9, now + i/fps)
    # Sudden drop to y~0.85 with torso horizontal
    for i in range(int(0.5*fps)):
        kp = _make_empty_kp()
        y = 0.50 + (0.35 * (i+1)/(0.5*fps))
        kp["left_hip"] = (0.5, y, 0.9); kp["right_hip"] = (0.5, y, 0.9)
        kp["left_shoulder"] = (0.8, y, 0.9); kp["right_shoulder"] = (0.2, y, 0.9)  # horizontal
        yield PoseResult(kp, 0.9, now + 1.0 + i/fps)
    # Immobile on floor
    for i in range(5*fps):
        kp = _make_empty_kp()
        y = 0.85
        kp["left_hip"] = (0.5, y, 0.9); kp["right_hip"] = (0.5, y, 0.9)
        kp["left_shoulder"] = (0.8, y, 0.9); kp["right_shoulder"] = (0.2, y, 0.9)
        yield PoseResult(kp, 0.9, now + 1.5 + i/fps)

def sequence_soft_immobility(fps: int = 15, still_s: float = 125.0) -> Iterator[PoseResult]:
    now = time.time()
    # slowly sit/lie (no sudden drop), then stay immobile long enough
    # transition 5s to lower height
    for i in range(5*fps):
        frac = (i+1)/(5*fps)
        hipy = 0.5 + 0.3*frac
        kp = _make_empty_kp()
        kp["left_hip"] = (0.5, hipy, 0.9); kp["right_hip"] = (0.5, hipy, 0.9)
        kp["left_shoulder"] = (0.52, hipy-0.18, 0.9); kp["right_shoulder"] = (0.48, hipy-0.18, 0.9)
        yield PoseResult(kp, 0.9, now + i/fps)
    # immobile period
    for i in range(int(still_s*fps)):
        hipy = 0.8
        kp = _make_empty_kp()
        kp["left_hip"] = (0.5, hipy, 0.9); kp["right_hip"] = (0.5, hipy, 0.9)
        kp["left_shoulder"] = (0.52, hipy-0.18, 0.9); kp["right_shoulder"] = (0.48, hipy-0.18, 0.9)
        yield PoseResult(kp, 0.9, now + 5.0 + i/fps)

class MockBackend:
    def __init__(self, seq: Iterator[PoseResult]):
        self.seq = seq
    def infer(self, _frame=None) -> PoseResult:
        try:
            return next(self.seq)
        except StopIteration:
            # repeat last known pose
            return PoseResult({}, 0.0, time.time())
