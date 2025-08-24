import os, time, signal, sys, argparse, yaml
import cv2

from .risk.engine import RiskEngine, RiskConfig
from .notify.telegram import TelegramNotifier, DummyNotifier
from .pose_backends.mock_pose import MockBackend, sequence_hard_fall
from .pose_backends.movenet_tflite import MoveNetSinglePose
from .utils.skeleton_draw import render_skeleton_image

def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)

def make_backend(backend_cfg: dict):
    kind = backend_cfg.get("type", "movenet_tflite")
    if kind == "mock":
        return MockBackend(sequence_hard_fall())
    elif kind == "movenet_tflite":
        model_path = backend_cfg.get("model_path", "models/movenet_singlepose_lightning.tflite")
        threads = int(backend_cfg.get("num_threads", 3))
        return MoveNetSinglePose(model_path, num_threads=threads)
    else:
        raise ValueError(f"Unknown backend type: {kind}")

def make_notifier(cfg: dict):
    if cfg.get("type","telegram") == "dummy":
        return DummyNotifier()
    return TelegramNotifier(cfg.get("bot_token"), cfg.get("chat_id"))

def run(config_path: str):
    cfg = load_config(config_path)
    backend = make_backend(cfg.get("backend", {}))
    notifier = make_notifier(cfg.get("telegram", {}))

    camera = cfg.get("camera", {})
    use_camera = camera.get("enabled", True) and cfg.get("backend",{}).get("type","movenet_tflite") != "mock"

    cap = None
    if use_camera:
        cap = cv2.VideoCapture(int(camera.get("index",0)))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  int(camera.get("width",640)))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(camera.get("height",480)))
        cap.set(cv2.CAP_PROP_FPS, int(camera.get("fps",15)))
        fps = cap.get(cv2.CAP_PROP_FPS) or 15
    else:
        fps = 15

    risk_cfg = cfg.get("risk", {})
    risk = RiskEngine(fps=int(fps), cfg=RiskConfig(
        angle_threshold_deg=float(risk_cfg.get("angle_threshold_deg", 50.0)),
        drop_threshold=float(risk_cfg.get("drop_threshold", 0.15)),
        drop_window_s=float(risk_cfg.get("drop_window_s", 1.0)),
        immobile_window_s=float(risk_cfg.get("immobile_window_s", 10.0)),
        immobile_motion_eps=float(risk_cfg.get("immobile_motion_eps", 0.05)),
        soft_immobility_s=float(risk_cfg.get("soft_immobility_s", 30.0)),
        hard_immobility_s=float(risk_cfg.get("hard_immobility_s", 60.0)),
        cooldown_s=float(risk_cfg.get("cooldown_s", 600.0)),
        confirm_grace_s=float(risk_cfg.get("confirm_grace_s", 6.0)),
        # Enhanced shower-aware parameters
        movement_tolerance_low_angle=float(risk_cfg.get("movement_tolerance_low_angle", 0.12)),
        movement_tolerance_high_angle=float(risk_cfg.get("movement_tolerance_high_angle", 0.05)),
        shower_mode_enabled=bool(risk_cfg.get("shower_mode_enabled", True)),
        shower_start_hour=int(risk_cfg.get("shower_start_hour", 6)),
        shower_end_hour=int(risk_cfg.get("shower_end_hour", 22)),
        shower_duration_multiplier=float(risk_cfg.get("shower_duration_multiplier", 4.0)),
        # Enhanced detection parameters  
        angle_change_threshold=float(risk_cfg.get("angle_change_threshold", 30.0)),
        position_change_threshold=float(risk_cfg.get("position_change_threshold", 0.15)),
    ))

    running = True
    def handle_sig(*_):
        nonlocal running
        running = False
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, handle_sig)

    print("🚀 BathGuard starting with corrected angle calculation...")
    frame_count = 0
    last_debug = 0

    while running:
        if use_camera:
            ok, frame = cap.read()
            if not ok:
                notifier.send_text("⚠️ Camera disconnected or no frames. Check device.")
                time.sleep(5); continue
        else:
            frame = None  # mock backend ignores

        pose = backend.infer(frame)
        metrics = risk.update(pose)
        frame_count += 1

        # Debug output every 5 seconds
        now = time.time()
        if now - last_debug >= 5:
            if metrics.get("present"):
                torso_angle = metrics.get('torso_angle', 'N/A')
                vx = metrics.get('debug_vx', 0)
                vy = metrics.get('debug_vy', 0)
                print(f"🔍 DEBUG: frames={frame_count}, torso_angle={torso_angle:.1f}°, vx={vx:.3f}, vy={vy:.3f}")
            else:
                print(f"🔍 DEBUG: frames={frame_count}, no person detected")
            last_debug = now

        if metrics.get("present"):
            event = metrics.get("event")
            if event:
                text = (
                    f"🚨 Bathroom alert ({event})\n"
                    f"torso≈{metrics['torso_angle']:.0f}° drop={metrics['sudden_drop']} immobile={metrics['immobile']}\n"
                    f"{time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                notifier.send_text(text, buttons=[("I'm OK","ACK_OK"),("False","ACK_FALSE")])
                try:
                    img = render_skeleton_image(pose)
                    notifier.send_photo(img, caption="Anonymized pose snapshot")
                except Exception as e:
                    print("skeleton render failed:", e)

        if use_camera:
            time.sleep(max(0, 1.0/fps - 0.001))
        else:
            time.sleep(0.01)  # fast-forward for mocks

    if cap:
        cap.release()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ns = ap.parse_args()
    run(ns.config)