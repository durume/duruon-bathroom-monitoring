
from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import time

# COCO-17 keypoint names in MoveNet order
COCO17 = [
    "nose","left_eye","right_eye","left_ear","right_ear",
    "left_shoulder","right_shoulder","left_elbow","right_elbow",
    "left_wrist","right_wrist","left_hip","right_hip",
    "left_knee","right_knee","left_ankle","right_ankle"
]

SKELETON_EDGES = [
    ("left_shoulder","right_shoulder"),("left_hip","right_hip"),
    ("left_shoulder","left_elbow"),("left_elbow","left_wrist"),
    ("right_shoulder","right_elbow"),("right_elbow","right_wrist"),
    ("left_hip","left_knee"),("left_knee","left_ankle"),
    ("right_hip","right_knee"),("right_knee","right_ankle"),
    ("left_shoulder","left_hip"),("right_shoulder","right_hip")
]

@dataclass
class PoseResult:
    keypoints: Dict[str, Tuple[float, float, float]]  # name -> (x, y, score) normalized [0,1]
    score: float                                      # mean visibility of visible keypoints
    ts: float                                         # timestamp (seconds)
    def now_like(self) -> "PoseResult":
        return PoseResult(self.keypoints, self.score, time.time())
