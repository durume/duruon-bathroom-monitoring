
import numpy as np
import time
from typing import Dict
try:  # pragma: no cover
    import cv2  # type: ignore
    _CV2_AVAILABLE = True
except Exception:
    cv2 = None  # type: ignore
    _CV2_AVAILABLE = False

try:  # pragma: no cover
    from ..shared.pose import PoseResult, COCO17  # type: ignore
except Exception:
    from shared.pose import PoseResult, COCO17  # type: ignore

try:
    import tflite_runtime.interpreter as tflite
except Exception:
    try:
        import tensorflow.lite as tflite  # type: ignore
    except Exception as e:
        tflite = None

class MoveNetSinglePose:
    def __init__(self, model_path: str, num_threads: int = 3):
        if tflite is None:
            raise RuntimeError("No TFLite runtime available. Install tflite-runtime or tensorflow.")
        self.interp = tflite.Interpreter(model_path=model_path, num_threads=max(1, num_threads))
        self.interp.allocate_tensors()
        self.inp = self.interp.get_input_details()[0]
        self.out = self.interp.get_output_details()[0]
        self.h, self.w = self.inp['shape'][1], self.inp['shape'][2]
        self.dtype = self.inp['dtype']

    def _preprocess(self, bgr):
        h0, w0 = bgr.shape[:2]
        scale = min(self.w/w0, self.h/h0)
        nw, nh = int(w0*scale), int(h0*scale)
        resized = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.zeros((self.h, self.w, 3), dtype=np.uint8)
        y1, x1 = (self.h-nh)//2, (self.w-nw)//2
        canvas[y1:y1+nh, x1:x1+nw] = resized
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        x = rgb.astype(np.float32) / 255.0 if self.dtype == np.float32 else rgb.astype(self.dtype)
        return np.expand_dims(x, 0)

    def infer(self, bgr) -> PoseResult:
        if not _CV2_AVAILABLE:
            raise RuntimeError("cv2 not available - cannot run MoveNet inference")
        x = self._preprocess(bgr)
        self.interp.set_tensor(self.inp['index'], x)
        self.interp.invoke()
        y = self.interp.get_tensor(self.out['index'])
        # Accept shapes [1,1,17,3] or [1,17,3]
        if y.ndim == 4 and y.shape[2] == 17 and y.shape[3] == 3:
            kp = {COCO17[i]:(float(y[0,0,i,1]), float(y[0,0,i,0]), float(y[0,0,i,2])) for i in range(17)}
        elif y.ndim == 3 and y.shape[1] == 17 and y.shape[2] == 3:
            kp = {COCO17[i]:(float(y[0,i,1]), float(y[0,i,0]), float(y[0,i,2])) for i in range(17)}
        else:
            kp = {}
        score = float(np.mean([v[2] for v in kp.values()])) if kp else 0.0
        return PoseResult(kp, score, time.time())
