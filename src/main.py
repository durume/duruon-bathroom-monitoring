import os, time, signal, sys, argparse, yaml
os.environ.setdefault("PYTHONUNBUFFERED","1")  # ensure unbuffered if service missed flag
try:
    import cv2
    CV2_AVAILABLE = True
except Exception as e:  # OpenCV optional
    CV2_AVAILABLE = False
    cv2 = None  # type: ignore
    print(f"⚠️ OpenCV unavailable ({e}); running without camera support")

from .risk.engine import RiskEngine, RiskConfig
from .notify.telegram import TelegramNotifier, DummyNotifier
from .pose_backends.mock_pose import MockBackend, sequence_hard_fall
from .pose_backends.movenet_tflite import MoveNetSinglePose
from .utils.skeleton_draw import render_skeleton_image

# Import LED status indicators first to initialize GPIO
LED_AVAILABLE = False
try:
    from .indicators.led_status import LEDStatus
    LED_AVAILABLE = True
except ImportError:
    print("⚠️  LED status module not found - running without LED indicators")

# Import PIR activation system after LED system
PIR_AVAILABLE = False
try:
    from .activation.pir_activation import PIRActivation
    PIR_AVAILABLE = True
except ImportError:
    print("⚠️  PIR activation module not found - running without PIR sensor")

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
    # Explicit dummy choice
    if cfg.get("type","telegram") == "dummy":
        return DummyNotifier()

    # Prefer config values
    token = cfg.get("bot_token")
    chat_id = cfg.get("chat_id")

    # Environment fallback (systemd EnvironmentFile or exported vars)
    if not token:
        token = (
            os.getenv("TG_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
        )
    if not chat_id:
        chat_id = (
            os.getenv("TG_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID")
        )

    # If still missing, try to parse local .env (when running manually) without extra deps
    if (not token or not chat_id) and os.path.exists('.env'):
        try:
            with open('.env','r') as f:
                for line in f:
                    if '=' not in line or line.strip().startswith('#'):
                        continue
                    k,v = line.strip().split('=',1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if not token and k in ("TG_BOT_TOKEN","TELEGRAM_BOT_TOKEN","BOT_TOKEN"):
                        token = v
                    if not chat_id and k in ("TG_CHAT_ID","TELEGRAM_CHAT_ID","CHAT_ID"):
                        chat_id = v
        except Exception as e:
            print(f"⚠️ Could not parse .env for Telegram creds: {e}")

    if not token or not chat_id:
        print("⚠️ Telegram credentials not found (config/env/.env) – using DummyNotifier")
        return DummyNotifier()

    try:
        return TelegramNotifier(token, chat_id)
    except Exception as e:
        print(f"⚠️ Failed to initialize TelegramNotifier ({e}); falling back to DummyNotifier")
        return DummyNotifier()

def run(config_path: str):
    cfg = load_config(config_path)
    backend = make_backend(cfg.get("backend", {}))
    notifier = make_notifier(cfg.get("telegram", {}))

    camera = cfg.get("camera", {})
    use_camera = camera.get("enabled", True) and cfg.get("backend",{}).get("type","movenet_tflite") != "mock"

    cap = None
    # Camera operational parameters & retry settings
    camera_index = int(camera.get("index",0))
    cam_width    = int(camera.get("width",640))
    cam_height   = int(camera.get("height",480))
    cam_req_fps  = int(camera.get("fps",15))
    retry_interval_s = float(camera.get("retry_interval_s", 5.0))
    error_notify_interval_s = float(camera.get("error_notify_interval_s", 60.0))
    reopen_verbose = bool(camera.get("reopen_verbose", True))
    last_camera_retry = 0.0
    last_camera_error_notify = 0.0
    fps = 15

    def _open_camera():
        nonlocal cap, fps
        if not (use_camera and CV2_AVAILABLE):
            return False
        try:
            c = cv2.VideoCapture(camera_index)
            c.set(cv2.CAP_PROP_FRAME_WIDTH,  cam_width)
            c.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_height)
            c.set(cv2.CAP_PROP_FPS, cam_req_fps)
            if not c.isOpened():
                c.release()
                return False
            cap = c
            fps_val = c.get(cv2.CAP_PROP_FPS) or cam_req_fps
            fps = fps_val if fps_val else 15
            if reopen_verbose:
                print(f"📷 Camera opened (index={camera_index}, {cam_width}x{cam_height} @ {fps:.1f}fps)")
            return True
        except Exception as e:
            if reopen_verbose:
                print(f"⚠️ Camera open exception: {e}")
            return False

    # Initial open attempt
    if use_camera and CV2_AVAILABLE:
        if not _open_camera():
            print("⚠️ Initial camera open failed; will retry in background")
    else:
        if use_camera and not CV2_AVAILABLE:
            print("⚠️ Camera requested but OpenCV not installed; continuing in mock/no-camera mode")

    # PID file lock (prevent multiple instances)
    pid_file = cfg.get("pid_file", "duruon.pid")
    try:
        if os.path.exists(pid_file):
            with open(pid_file, 'r') as pf:
                existing = pf.read().strip()
            if existing.isdigit() and os.path.exists(f"/proc/{existing}"):
                print(f"❌ Another DuruOn instance running (PID {existing}). Exiting.")
                return
            else:
                print("⚠️ Stale PID file found; overwriting")
        with open(pid_file, 'w') as pf:
            pf.write(str(os.getpid()))
    except Exception as e:
        print(f"⚠️ Could not create PID file: {e}")

    risk_cfg = cfg.get("risk", {})
    risk = RiskEngine(fps=int(fps), cfg=RiskConfig(
        angle_threshold_deg=float(risk_cfg.get("angle_threshold_deg", 50.0)),
        drop_threshold=float(risk_cfg.get("drop_threshold", 0.15)),
        drop_window_s=float(risk_cfg.get("drop_window_s", 1.0)),
        immobile_window_s=float(risk_cfg.get("immobile_window_s", 10.0)),
        immobile_motion_eps=float(risk_cfg.get("immobile_motion_eps", 0.05)),
        soft_immobility_s=float(risk_cfg.get("soft_immobility_s", 30.0)),
        hard_immobility_s=float(risk_cfg.get("hard_immobility_s", 60.0)),
    fast_fall_immobility_s=float(risk_cfg.get("fast_fall_immobility_s", 12.0)),
        cooldown_s=float(risk_cfg.get("cooldown_s", 600.0)),
        confirm_grace_s=float(risk_cfg.get("confirm_grace_s", 6.0)),
        movement_tolerance_low_angle=float(risk_cfg.get("movement_tolerance_low_angle", 0.12)),
        movement_tolerance_high_angle=float(risk_cfg.get("movement_tolerance_high_angle", 0.05)),
        shower_mode_enabled=bool(risk_cfg.get("shower_mode_enabled", True)),
        shower_start_hour=int(risk_cfg.get("shower_start_hour", 6)),
        shower_end_hour=int(risk_cfg.get("shower_end_hour", 22)),
        shower_duration_multiplier=float(risk_cfg.get("shower_duration_multiplier", 4.0)),
        angle_change_threshold=float(risk_cfg.get("angle_change_threshold", 30.0)),
        position_change_threshold=float(risk_cfg.get("position_change_threshold", 0.15)),
    min_kp_confidence=float(risk_cfg.get("min_kp_confidence", 0.10)),
    ))

    led_system = None
    if LED_AVAILABLE:
        led_cfg = cfg.get("led_indicators", {})
        if led_cfg.get("enabled", True):
            led_system = LEDStatus(
                green_pin=int(led_cfg.get("green_pin", 18)),
                blue_pin=int(led_cfg.get("blue_pin", 23)),
                red_pin=int(led_cfg.get("red_pin", 25))
            )
            led_system.start()
            led_system.set_system_status("starting")
            print("✅ LED status indicators enabled")
            time.sleep(0.5)
        else:
            print("⚠️  LED indicators disabled in config")
    else:
        print("⚠️  LED indicators not available")

    pir_system = None
    if PIR_AVAILABLE:
        pir_cfg = cfg.get("pir_activation", {})
        if pir_cfg.get("enabled", True):
            try:
                time.sleep(0.5)
                pir_system = PIRActivation(
                    pir_pin=int(pir_cfg.get("pir_pin", 24)),
                    debounce_time=float(pir_cfg.get("debounce_time", 2.0)),
                    activation_grace_period=float(pir_cfg.get("activation_grace_period", 10.0)),
                    auto_sleep_timeout=float(pir_cfg.get("auto_sleep_timeout", 300.0))
                )
                print("✅ PIR activation system enabled")
            except Exception as e:
                print(f"⚠️  PIR activation failed: {e} - running in continuous mode")
                pir_system = None
        else:
            print("⚠️  PIR activation disabled in config")
    else:
        print("⚠️  PIR activation not available - running in continuous mode")

    # Alert / heartbeat configuration
    alert_cfg = cfg.get("alerting", {})
    heartbeat_cfg = alert_cfg.get("heartbeat", {}) if isinstance(alert_cfg.get("heartbeat"), dict) else {}
    heartbeat_enabled = bool(heartbeat_cfg.get("enabled", False))
    heartbeat_interval = float(heartbeat_cfg.get("interval_s", 86400.0))
    last_heartbeat = time.time()
    start_time = last_heartbeat
    event_count = 0

    monitoring_active = pir_system is None
    frame_count = 0
    last_debug = 0
    # Throttle repetitive presence combination logs
    last_presence_combo = None  # ('present','pir_motion') tuple
    last_presence_log_time = 0.0
    presence_log_interval = 10.0  # seconds
    first_presence_cycle = True

    # Logging frequency (lower debug frequency)
    logging_cfg = cfg.get("logging", {}) if isinstance(cfg.get("logging"), dict) else {}
    active_debug_interval = float(logging_cfg.get("active_debug_interval_s", 30.0))  # was 5
    idle_debug_interval = float(logging_cfg.get("idle_debug_interval_s", 120.0))     # was 30
    # Presence log debounce settings
    presence_min_persist_s = float(logging_cfg.get("presence_min_persist_s", 2.0))
    min_log_gap_s = float(logging_cfg.get("presence_min_log_gap_s", 1.5))
    last_presence_log_real = 0.0
    pending_combo = None
    pending_combo_since = 0.0

    # Debug frame capture configuration
    debug_cfg = cfg.get("debug", {}) if isinstance(cfg.get("debug"), dict) else {}
    debug_save_frames = bool(debug_cfg.get("save_frames", False)) and CV2_AVAILABLE and use_camera
    debug_frame_dir = debug_cfg.get("frame_dir", "debug_frames")
    debug_save_interval = float(debug_cfg.get("save_interval_s", 10.0))
    debug_save_on_state_change = bool(debug_cfg.get("save_on_state_change", True))
    debug_max_frames = int(debug_cfg.get("max_frames", 200))
    debug_brightness_warn_interval = float(debug_cfg.get("brightness_warn_interval_s", 60.0))
    risk_verbose = bool(debug_cfg.get("risk_verbose", False))
    risk_verbose_interval = float(debug_cfg.get("risk_verbose_interval_s", 5.0))
    risk_snapshot_interval = float(debug_cfg.get("risk_snapshot_every_s", 0.0))  # 0 = disabled
    keypoint_dump = bool(debug_cfg.get("keypoint_dump", True))
    keypoint_dump_top_n = int(debug_cfg.get("keypoint_dump_top_n", 6))  # show weakest N keypoints
    risk_verbose_compact = bool(debug_cfg.get("risk_verbose_compact", True))
    last_debug_frame_save = 0.0
    last_brightness_warn = 0.0
    saved_frame_count = 0
    last_saved_state_combo = None
    last_risk_verbose = 0.0
    last_risk_snapshot = 0.0
    if debug_save_frames:
        try:
            os.makedirs(debug_frame_dir, exist_ok=True)
            print(f"🧪 Debug frame saving enabled -> {debug_frame_dir}/ (interval={debug_save_interval}s, on_state_change={debug_save_on_state_change})")
        except Exception as e:
            print(f"⚠️ Could not create debug frame directory {debug_frame_dir}: {e}")
            debug_save_frames = False

    def on_pir_activate():
        nonlocal monitoring_active
        monitoring_active = True
        print("🟢 PIR ACTIVATED - Starting pose detection and risk monitoring")
        if led_system:
            led_system.set_pir_status("triggered")
            led_system.set_system_status("active")

    def on_pir_deactivate():
        nonlocal monitoring_active
        monitoring_active = False
        print("💤 PIR DEACTIVATED - Stopping monitoring, returning to idle")
        if led_system:
            led_system.set_pir_status("clear")
            led_system.set_system_status("idle")

    if pir_system:
        pir_system.set_activation_callback(on_pir_activate)
        pir_system.set_deactivation_callback(on_pir_deactivate)
        pir_system.start()

    running = True
    def handle_sig(*_):
        nonlocal running
        running = False
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, handle_sig)

    # Startup summary (include git revision if available)
    backend_type = cfg.get("backend", {}).get("type", "unknown")
    notifier_type = type(notifier).__name__
    camera_status = (
        f"enabled idx={camera_index} {cam_width}x{cam_height}@{cam_req_fps}fps" if (use_camera and CV2_AVAILABLE) else (
            "requested-but-missing-OpenCV" if use_camera and not CV2_AVAILABLE else "disabled")
    )
    pir_status = "enabled" if pir_system else "disabled"
    led_status = "enabled" if LED_AVAILABLE else "disabled"
    git_rev = None
    try:
        import subprocess
        git_rev = subprocess.check_output(["git","rev-parse","--short","HEAD"], stderr=subprocess.DEVNULL, timeout=1).decode().strip()
    except Exception:
        git_rev = os.getenv("GIT_REV") or "unknown"
    print(f"🚀 DuruOn starting (rev={git_rev})...")
    print(f"ℹ️  Backend={backend_type} | Camera={camera_status} | PIR={pir_status} | LED={led_status} | Notifier={notifier_type}")
    if heartbeat_enabled:
        print(f"🫀 Heartbeat enabled every {heartbeat_interval/60:.1f} min")
    sys.stdout.flush()
    if pir_system:
        print("💤 System in IDLE mode - waiting for PIR motion detection")
        if led_system:
            led_system.set_system_status("idle")
    else:
        print("🔍 System in CONTINUOUS monitoring mode")
        if led_system:
            led_system.set_system_status("active")

    try:
        while running:
            current_time = time.time()
            if use_camera and CV2_AVAILABLE:
                # Ensure camera open / retry
                if (cap is None or not cap.isOpened()):
                    now = time.time()
                    if now - last_camera_retry >= retry_interval_s:
                        last_camera_retry = now
                        opened = _open_camera()
                        if not opened and reopen_verbose:
                            print(f"⏳ Camera reopen attempt failed; next in {retry_interval_s:.1f}s")
                    frame = None
                    # If camera not yet available, idle briefly
                    if cap is None or not cap.isOpened():
                        time.sleep(0.2)
                        continue
                ok, frame = cap.read()
                if not ok:
                    # Release and schedule retry
                    if reopen_verbose:
                        print("⚠️ Camera frame read failed; releasing and scheduling reopen")
                    try:
                        cap.release()
                    except Exception:
                        pass
                    cap = None
                    now = time.time()
                    if monitoring_active and (now - last_camera_error_notify) >= error_notify_interval_s:
                        notifier.send_text("⚠️ Camera disconnected or no frames. Will keep retrying.")
                        last_camera_error_notify = now
                    if led_system:
                        led_system.set_system_status("error")
                    time.sleep(0.5)
                    continue
            else:
                frame = None

            if monitoring_active:
                # Optional brightness / debug frame saving BEFORE inference
                if use_camera and CV2_AVAILABLE and frame is not None:
                    try:
                        mean_val = float(frame.mean())
                        now_bt = time.time()
                        if mean_val < 30 and (now_bt - last_brightness_warn) >= debug_brightness_warn_interval:
                            level = "extremely dark" if mean_val < 10 else "dark"
                            print(f"🌑 LOW LIGHT: mean_pixel={mean_val:.1f} ({level}) -> detection quality may drop")
                            last_brightness_warn = now_bt
                        # Save diagnostic frame if enabled
                        if debug_save_frames:
                            combo_state = (last_presence_combo or (False, False))
                            save_reason = None
                            if (time.time() - last_debug_frame_save) >= debug_save_interval:
                                save_reason = "interval"
                            if debug_save_on_state_change and combo_state != last_saved_state_combo:
                                save_reason = (save_reason + "+state" if save_reason else "state_change")
                            if save_reason and saved_frame_count < debug_max_frames:
                                ts_name = time.strftime('%Y%m%d_%H%M%S')
                                fname = os.path.join(debug_frame_dir, f"frame_{ts_name}_{save_reason}_{saved_frame_count:04d}.jpg")
                                try:
                                    cv2.imwrite(fname, frame)
                                    print(f"🖼️ Saved debug frame ({save_reason}) -> {fname}")
                                    last_debug_frame_save = time.time()
                                    last_saved_state_combo = combo_state
                                    saved_frame_count += 1
                                except Exception as e:
                                    print(f"⚠️ Failed saving debug frame: {e}")
                                if saved_frame_count >= debug_max_frames:
                                    print("🧪 Reached debug_max_frames limit; disabling further saves")
                                    debug_save_frames = False
                    except Exception as e:
                        pass
                try:
                    pose = backend.infer(frame)
                except Exception as e:
                    print(f"⚠️ backend.infer error: {e}; skipping frame")
                    time.sleep(0.05)
                    continue
                metrics = risk.update(pose)
                frame_count += 1
                present = metrics.get("present")
                pir_motion = pir_system._read_pir() if pir_system else False

                # Risk debug instrumentation
                if risk_verbose:
                    now_rv = time.time()
                    if (now_rv - last_risk_verbose) >= risk_verbose_interval:
                        # Optional keypoint dump when absent or low score
                        kp_extra = ""
                        if keypoint_dump:
                            try:
                                # Sort by confidence ascending
                                kps = sorted(pose.keypoints.items(), key=lambda kv: kv[1][2])
                                weakest = kps[:keypoint_dump_top_n]
                                weakest_str = ",".join([f"{n}:{v[2]:.2f}" for n,v in weakest])
                                # Show hips/shoulders explicitly if missing
                                req = []
                                for rq in ("left_hip","right_hip","left_shoulder","right_shoulder"):
                                    if rq in pose.keypoints:
                                        req.append(f"{rq}:{pose.keypoints[rq][2]:.2f}")
                                kp_extra = f" | kp[{len(pose.keypoints)}] mean={pose.score:.2f} weak={weakest_str} req={' '.join(req)}"
                            except Exception:
                                pass
                        if risk_verbose_compact:
                            # Compact form (avoid terminal wrapping)
                            print(
                                "🧪 RISK DBG: pres=%s evt=%s ang=%.0f° drop=%s imm=%s sc=%.2f%s" % (
                                    metrics.get('present'), metrics.get('event'), metrics.get('torso_angle', -1.0),
                                    metrics.get('sudden_drop'), metrics.get('immobile'), pose.score, kp_extra
                                )
                            )
                        else:
                            print(
                                "🧪 RISK DBG: present=%s event=%s angle=%.1f sudden_drop=%s dy=%.3f angleΔ=%.1f totalAngleΔ=%.1f motion_eps=%.3f immobile=%s softT=%.1fs hardT=%.1fs vx=%.3f vy=%.3f score=%.2f%s" % (
                                    metrics.get('present'), metrics.get('event'), metrics.get('torso_angle', -1.0),
                                    metrics.get('sudden_drop'), metrics.get('vertical_dy', 0.0), metrics.get('angle_change',0.0), metrics.get('angle_change_total',0.0),
                                    metrics.get('adaptive_motion_eps',0.0), metrics.get('immobile'),
                                    metrics.get('adaptive_soft_threshold',0.0), metrics.get('adaptive_hard_threshold',0.0),
                                    metrics.get('debug_vx',0.0), metrics.get('debug_vy',0.0), pose.score, kp_extra
                                )
                            )
                        last_risk_verbose = now_rv
                    # Optional periodic anonymized snapshot even without event to verify pose skeleton
                    if risk_snapshot_interval > 0 and metrics.get('present'):
                        now_rs = time.time()
                        if (now_rs - last_risk_snapshot) >= risk_snapshot_interval:
                            try:
                                img_dbg = render_skeleton_image(pose)
                                notifier.send_photo(img_dbg, caption="🧪 Debug pose snapshot")
                                last_risk_snapshot = now_rs
                            except Exception as e:
                                print(f"⚠️ Debug snapshot failed: {e}")
                if pir_system:
                    combo = (bool(present), bool(pir_motion))  # (present, pir_motion)
                    now_ts = time.time()
                    periodic = (now_ts - last_presence_log_time) >= presence_log_interval
                    suppress = first_presence_cycle and combo == (False, False)
                    # Debounce logic: wait for stability before accepting new combo
                    if combo != last_presence_combo:
                        if pending_combo != combo:
                            pending_combo = combo
                            pending_combo_since = now_ts
                        stable = (now_ts - pending_combo_since) >= presence_min_persist_s
                        # Dual detection considered important -> bypass stability delay
                        if combo == (True, True):
                            stable = True
                        if stable:
                            # Enforce minimum gap between any presence logs
                            if (now_ts - last_presence_log_real) >= min_log_gap_s:
                                if combo == (True, True):
                                    print("✅ DUAL DETECTION: Camera + PIR both detect presence (timer reset)")
                                elif combo == (True, False):
                                    print("📷 CAMERA ONLY: person detected; PIR clear (countdown continues)")
                                elif combo == (False, True):
                                    print("📡 PIR ONLY: motion detected; no person in camera (countdown continues)")
                                elif not suppress:
                                    print("👻 BOTH CLEAR: no person & PIR clear (idle countdown)")
                                last_presence_combo = combo
                                last_presence_log_real = now_ts
                                last_presence_log_time = now_ts
                                if combo == (True, True):
                                    pir_system.update_motion()
                                    if led_system:
                                        led_system.set_pir_status("monitoring")
                    elif periodic and (now_ts - last_presence_log_real) >= min_log_gap_s:
                        # Periodic heartbeat of presence state
                        if last_presence_combo == (True, True):
                            print("✅ DUAL DETECTION: (periodic)")
                        elif last_presence_combo == (True, False):
                            print("📷 CAMERA ONLY: (periodic) still person detected")
                        elif last_presence_combo == (False, True):
                            print("📡 PIR ONLY: (periodic) still motion only")
                        elif not suppress:
                            print("👻 BOTH CLEAR: (periodic) still idle")
                        last_presence_log_time = now_ts
                        last_presence_log_real = now_ts
                    first_presence_cycle = False
                if current_time - last_debug >= active_debug_interval:
                    present = metrics.get("present")
                    event = metrics.get("event") 
                    if present:
                        torso_angle = metrics.get('torso_angle', 'N/A')
                        vx = metrics.get('debug_vx', 0)
                        vy = metrics.get('debug_vy', 0)
                        print(f"🔍 ACTIVE: frames={frame_count}, present={present}, event={event}, torso_angle={torso_angle:.1f}°, vx={vx:.3f}, vy={vy:.3f}")
                    else:
                        print(f"🔍 ACTIVE: frames={frame_count}, present={present}, event={event}, no person detected")
                    if pir_system:
                        time_since_motion = current_time - pir_system.last_motion_time if pir_system.last_motion_time else 0
                        print(f"📡 PIR DEBUG: monitoring={pir_system.is_monitoring}, last_motion={time_since_motion:.1f}s ago, timeout={pir_system.auto_sleep_timeout}s")
                        if time_since_motion > pir_system.auto_sleep_timeout:
                            print("⚠️  PIR SHOULD DEACTIVATE BUT HASN'T!")
                    last_debug = current_time
                if metrics.get("present"):
                    event = metrics.get("event")
                    if event:
                        event_count += 1
                        if led_system:
                            if "hard" in event or "fall" in event:
                                led_system.set_alert_status("emergency")
                            else:
                                led_system.set_alert_status("soft")
                        text = (
                            f"🚨 DuruOn alert ({event})\n"
                            f"torso≈{metrics['torso_angle']:.0f}° drop={metrics['sudden_drop']} immobile={metrics['immobile']}\n"
                            f"{time.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        notifier.send_text(text, buttons=[("I'm OK","ACK_OK"),("False","ACK_FALSE")])
                        try:
                            img = render_skeleton_image(pose)
                            notifier.send_photo(img, caption="Anonymized pose snapshot")
                        except Exception as e:
                            print("skeleton render failed:", e)
                    else:
                        if led_system:
                            led_system.set_alert_status("none")
                else:
                    frame_count += 1
                    if current_time - last_debug >= idle_debug_interval:
                        pir_status = pir_system.get_status() if pir_system else {"is_monitoring": False}
                        print(f"💤 IDLE: frames={frame_count}, PIR monitoring={pir_status.get('is_monitoring', False)}")
                        last_debug = current_time
                # Periodic heartbeat (outside of event branch to ensure regularity)
                if heartbeat_enabled:
                    if (current_time - last_heartbeat) >= heartbeat_interval:
                        uptime_s = int(current_time - start_time)
                        hb_text = (
                            f"✅ DuruOn heartbeat\n"
                            f"uptime={uptime_s//3600}h{(uptime_s%3600)//60}m frames={frame_count} events={event_count} present={metrics.get('present')}\n"
                            f"camera={'ok' if (cap and cap.isOpened()) else 'down'} pir={'on' if (pir_system and pir_system.is_monitoring) else 'idle'}"
                        )
                        notifier.send_text(hb_text)
                        last_heartbeat = current_time
            if use_camera and CV2_AVAILABLE:
                sleep_time = max(0, 1.0/fps - 0.001)
                if not monitoring_active:
                    sleep_time *= 5
                time.sleep(sleep_time)
            else:
                time.sleep(0.1 if monitoring_active else 1.0)
    except KeyboardInterrupt:
        print("🛑 Keyboard interrupt received")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        if led_system:
            led_system.set_system_status("error")
        raise
    finally:
        print("🛑 Shutting down DuruOn...")
        if pir_system:
            pir_system.stop()
        if led_system:
            led_system.stop()
        if cap:
            cap.release()
            print("📷 Camera released")
        # Clean PID file
        try:
            if os.path.exists(pid_file):
                os.remove(pid_file)
        except Exception:
            pass
        uptime_total = int(time.time() - start_time)
        print(f"✅ DuruOn shutdown complete (uptime={uptime_total//3600}h{(uptime_total%3600)//60}m events={event_count})")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ns = ap.parse_args()
    run(ns.config)