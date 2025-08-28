
from typing import Tuple
import numpy as np
try:  # pragma: no cover
    from ..shared.pose import PoseResult, SKELETON_EDGES  # type: ignore
except Exception:
    from shared.pose import PoseResult, SKELETON_EDGES  # type: ignore

# Optional cv2 import (fallback will raise if used without cv2)
try:  # pragma: no cover - simple import guard
    import cv2  # type: ignore
    _CV2_AVAILABLE = True
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore
    _CV2_AVAILABLE = False

def render_skeleton_image(pose: PoseResult, out_size: Tuple[int,int]=(480,480)) -> bytes:
    if not _CV2_AVAILABLE:
        raise RuntimeError("cv2 not available - cannot render skeleton image")
    w, h = out_size
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    def to_px(p): return (int(p[0]*w), int(p[1]*h))
    # draw lines
    for a,b in SKELETON_EDGES:
        pa = pose.keypoints.get(a); pb = pose.keypoints.get(b)
        if pa and pb and pa[2] > 0.2 and pb[2] > 0.2:
            cv2.line(canvas, to_px(pa), to_px(pb), (255,255,255), 2)
    # draw joints
    for name,p in pose.keypoints.items():
        if p[2] > 0.2:
            cv2.circle(canvas, to_px(p), 3, (255,255,255), -1)
    _, buf = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return bytes(buf)
