
# Benchmark MoveNet on a folder of images or from camera; optional.
# Usage: python -m scripts.bench_pose --model models/movenet_singlepose_lightning.tflite --camera 0
import argparse, time, cv2, numpy as np
from src.pose_backends.movenet_tflite import MoveNetSinglePose

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--camera", type=int, default=None)
    args = ap.parse_args()

    backend = MoveNetSinglePose(args.model, num_threads=3)
    if args.camera is not None:
        cap = cv2.VideoCapture(args.camera)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
        cap.set(cv2.CAP_PROP_FPS, 15)
        start = time.time(); n=0
        while n < 200:
            ok, frame = cap.read()
            if not ok: break
            backend.infer(frame)
            n+=1
        dur = time.time()-start
        print(f"{n} frames in {dur:.2f}s => {n/dur:.1f} FPS")
    else:
        print("Provide --camera to bench live camera.")
