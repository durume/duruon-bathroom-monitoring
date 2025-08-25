import os, time, signal, sys, argparse, yaml
import cv2

# Support running as 'python src/main.py' by repairing sys.path and using absolute imports if relative fail
try:
    from .risk.engine import RiskEngine, RiskConfig  # type: ignore
    from .notify.telegram import TelegramNotifier, DummyNotifier  # type: ignore
    from .pose_backends.mock_pose import MockBackend, sequence_hard_fall  # type: ignore
    from .pose_backends.movenet_tflite import MoveNetSinglePose  # type: ignore
    from .utils.skeleton_draw import render_skeleton_image  # type: ignore
except ImportError:  # pragma: no cover
    pkg_root = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(pkg_root)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    # Retry with absolute-style imports
    from risk.engine import RiskEngine, RiskConfig
    from notify.telegram import TelegramNotifier, DummyNotifier
    from pose_backends.mock_pose import MockBackend, sequence_hard_fall
    from pose_backends.movenet_tflite import MoveNetSinglePose
    from utils.skeleton_draw import render_skeleton_image

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
    if cfg.get("type","telegram") == "dummy":
        return DummyNotifier()
    return TelegramNotifier(cfg.get("bot_token"), cfg.get("chat_id"))

def run(config_path: str):
    print("🔧 DEBUG: Starting run function")
    cfg = load_config(config_path)
    print("🔧 DEBUG: Config loaded")
    backend = make_backend(cfg.get("backend", {}))
    print("🔧 DEBUG: Backend created")
    notifier = make_notifier(cfg.get("telegram", {}))
    print("🔧 DEBUG: Notifier created")

    camera = cfg.get("camera", {})
    use_camera = camera.get("enabled", True) and cfg.get("backend",{}).get("type","movenet_tflite") != "mock"

    # Initialize camera
    cap = None
    if use_camera:
        cap = cv2.VideoCapture(int(camera.get("index",0)))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  int(camera.get("width",640)))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(camera.get("height",480)))
        cap.set(cv2.CAP_PROP_FPS, int(camera.get("fps",15)))
        fps = cap.get(cv2.CAP_PROP_FPS) or 15
    else:
        fps = 15

    # Initialize risk engine
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

    # Initialize LED status indicators FIRST to set up GPIO
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
            # Give LED system time to initialize GPIO
            time.sleep(0.5)
        else:
            print("⚠️  LED indicators disabled in config")
    else:
        print("⚠️  LED indicators not available")

    # Initialize PIR activation system AFTER LED system
    pir_system = None
    if PIR_AVAILABLE:
        pir_cfg = cfg.get("pir_activation", {})
        if pir_cfg.get("enabled", True):
            try:
                # Add a small delay to ensure LED GPIO is properly initialized
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

    # System state
    monitoring_active = pir_system is None  # Start active if no PIR, idle if PIR enabled
    frame_count = 0
    last_debug = 0
    last_callback_check = 0.0
    callback_interval = float(cfg.get('telegram', {}).get('callback_poll_interval_s', 3.0))
    last_frame_hash = None
    last_frame_hash_time = time.time()
    freeze_alert_sent = False
    frame_freeze_seconds = float(cfg.get('camera', {}).get('freeze_alert_s', 30.0))
    
    # Simple alert log (append-only). Avoid logging raw PII; only structural info.
    alert_log_path = cfg.get('logging', {}).get('alert_log', 'alerts.log')
    alert_cfg = cfg.get('alerting', {})
    repeat_after = float(alert_cfg.get('repeat_unacked_after_s', 0))
    max_repeats = int(alert_cfg.get('max_repeats', 0))
    include_stop = bool(alert_cfg.get('stop_button', True))
    heartbeat_cfg = alert_cfg.get('heartbeat', {})
    heartbeat_enabled = bool(heartbeat_cfg.get('enabled', False))
    heartbeat_interval = float(heartbeat_cfg.get('interval_s', 86400))
    next_heartbeat = time.time() + heartbeat_interval if heartbeat_enabled else None
    log_rotate_kb = int(alert_cfg.get('log_rotate_kb', 0))
    log_keep = int(alert_cfg.get('log_keep', 3))
    adaptive_soft_mult = float(alert_cfg.get('adaptive_soft_multiplier', 1.0))
    adaptive_hard_mult = float(alert_cfg.get('adaptive_hard_multiplier', 1.0))
    # Adaptive tuning state
    base_soft_threshold = risk.cfg.soft_immobility_s
    base_hard_threshold = risk.cfg.hard_immobility_s
    soft_scale = 1.0
    hard_scale = 1.0
    last_adapt_event_count = 0
    adapt_interval_events = 5  # evaluate every N resolved alerts (ack or false)
    min_scale, max_scale = 0.5, 2.5
    
    active_alert = None  # dict with keys: first_ts, last_sent_ts, repeats, event, metrics
    false_positive_count = 0
    ack_ok_count = 0
    def log_alert(event_type: str, metrics: dict):
        try:
            with open(alert_log_path, 'a') as lf:
                lf.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')},event={event_type},angle={metrics.get('torso_angle')},immobile={metrics.get('immobile')},drop={metrics.get('sudden_drop')}\n")
            # Rotate if needed
            if log_rotate_kb > 0 and os.path.getsize(alert_log_path) > log_rotate_kb * 1024:
                for i in range(log_keep-1, 0, -1):
                    old = f"{alert_log_path}.{i}"
                    older = f"{alert_log_path}.{i+1}"
                    if os.path.exists(old):
                        if i+1 > log_keep-1 and os.path.exists(older):
                            try: os.remove(older)
                            except Exception: pass
                        os.rename(old, older)
                os.rename(alert_log_path, f"{alert_log_path}.1")
        except Exception:
            pass
    
    # PIR callbacks with LED integration
    def on_pir_activate():
        nonlocal monitoring_active
        monitoring_active = True
        print("🟢 PIR ACTIVATED - Starting pose detection and risk monitoring")
        if led_system:
            led_system.set_pir_status("triggered")  # Flash blue LED
            # Set monitoring status after brief delay to show person detected  
            led_system.set_system_status("active")
        
    def on_pir_deactivate():
        nonlocal monitoring_active
        monitoring_active = False
        print("💤 PIR DEACTIVATED - Stopping monitoring, returning to idle")
        if led_system:
            led_system.set_pir_status("clear")
            led_system.set_system_status("idle")

    # Setup PIR callbacks
    if pir_system:
        pir_system.set_activation_callback(on_pir_activate)
        pir_system.set_deactivation_callback(on_pir_deactivate)
        pir_system.start()

    # Signal handling
    running = True
    def handle_sig(*_):
        nonlocal running
        running = False
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, handle_sig)

    print("🚀 DuruOn starting with PIR activation and LED indicators...")
    if pir_system:
        print("💤 System in IDLE mode - waiting for PIR motion detection")
        if led_system:
            led_system.set_system_status("idle")
    else:
        print("🔍 System in CONTINUOUS monitoring mode")
        if led_system:
            led_system.set_system_status("active")

    # Main monitoring loop
    try:
        while running:
            current_time = time.time()

            # Always read camera frame (minimal processing when idle)
            if use_camera:
                ok, frame = cap.read()
                if not ok:
                    if monitoring_active:  # Only send notifications when active
                        notifier.send_text("⚠️ Camera disconnected or no frames. Check device.")
                    if led_system:
                        led_system.set_system_status("error")
                    time.sleep(5)
                    continue
            else:
                frame = None  # mock backend ignores

            # Process frame based on monitoring state
            if monitoring_active:
                # ACTIVE: Full pose detection and risk analysis
                # Safe inference wrapper
                try:
                    pose = backend.infer(frame)
                except Exception as inf_err:
                    print(f"⚠️ Inference error: {inf_err}")
                    time.sleep(0.2)
                    continue
                metrics = risk.update(pose)
                frame_count += 1
                
                # Camera freeze watchdog (hash every ~1s)
                if use_camera and frame_count % int(max(1, fps)) == 0:
                    try:
                        frame_hash = hash(frame.tobytes()[:5000])  # partial hash for speed
                        if frame_hash == last_frame_hash:
                            if (time.time() - last_frame_hash_time) > frame_freeze_seconds and not freeze_alert_sent:
                                notifier.send_text("⚠️ Camera feed appears frozen. Check lens or connection.")
                                freeze_alert_sent = True
                        else:
                            last_frame_hash = frame_hash
                            last_frame_hash_time = time.time()
                            freeze_alert_sent = False
                    except Exception:
                        pass

                # FIXED: Update PIR system only when BOTH camera detects person AND PIR detects motion
                present = metrics.get("present")
                pir_motion = pir_system._read_pir() if pir_system else False
                
                if pir_system and present and pir_motion:
                    print(f"✅ DUAL DETECTION: Camera + PIR both detect presence, resetting PIR timer")
                    pir_system.update_motion()
                    # Set blue LED to monitoring when person is actually detected
                    if led_system:
                        led_system.set_pir_status("monitoring")
                elif pir_system and present:
                    # EMERGENCY OVERRIDE: If camera detects person, keep PIR active even without PIR motion
                    print(f"🚨 EMERGENCY OVERRIDE: Camera detects person, keeping PIR active for safety")
                    pir_system.update_motion()  # Reset PIR timer to prevent deactivation
                elif pir_system:
                    if present and not pir_motion:
                        print(f"📷 CAMERA ONLY: Camera detects person but PIR clear - allowing PIR countdown")
                    elif not present and pir_motion:
                        print(f"📡 PIR ONLY: PIR detects motion but no person in camera - allowing PIR countdown") 
                    else:
                        print(f"👻 BOTH CLEAR: No camera detection and PIR clear - PIR timer counting down")

                # Debug output every 1 second when active
                if current_time - last_debug >= 1:
                    present = metrics.get("present")
                    event = metrics.get("event") 
                    if present:
                        torso_angle = metrics.get('torso_angle', 'N/A')
                        vx = metrics.get('debug_vx', 0)
                        vy = metrics.get('debug_vy', 0)
                        immobile = metrics.get('immobile', False)
                        adaptive_motion_eps = metrics.get('adaptive_motion_eps', 'N/A')
                        total_movement = (vx**2 + vy**2)**0.5
                        angle_low = torso_angle <= 50.0 if torso_angle != 'N/A' else False
                        print(f"🔍 ACTIVE: frames={frame_count}, present={present}, event={event}, torso_angle={torso_angle:.1f}°, vx={vx:.3f}, vy={vy:.3f}")
                        print(f"  🐛 DEBUG: immobile={immobile}, total_movement={total_movement:.3f}, threshold={adaptive_motion_eps}, angle_low={angle_low}")
                        
                        # Show alert conditions
                        if angle_low and immobile and not event:
                            print(f"  ⚠️  SHOULD ALERT: Low angle + immobile but no event! Check risk engine timer logic.")
                    else:
                        print(f"🔍 ACTIVE: frames={frame_count}, present={present}, event={event}, no person detected")
                    
                    # PIR status debug
                    if pir_system:
                        time_since_motion = current_time - pir_system.last_motion_time if pir_system.last_motion_time else 0
                        print(f"📡 PIR DEBUG: monitoring={pir_system.is_monitoring}, last_motion={time_since_motion:.1f}s ago, timeout={pir_system.auto_sleep_timeout}s")
                        if time_since_motion > pir_system.auto_sleep_timeout:
                            print("⚠️  PIR SHOULD DEACTIVATE BUT HASN'T!")
                    
                    last_debug = current_time

                # Handle emergency events with LED indicators
                if metrics.get("present"):
                    event = metrics.get("event")
                    if event:
                        # Update LED status for alerts
                        if led_system:
                            if "hard" in event or "fall" in event:
                                led_system.set_alert_status("emergency")
                            else:
                                led_system.set_alert_status("soft")
                        
                        # Original English template kept for reference:
                        # f"🚨 DuruOn alert ({event})\n" f"torso≈{metrics['torso_angle']:.0f}° drop={metrics['sudden_drop']} immobile={metrics['immobile']}\n"
                        # Korean localized alert text
                        text = (
                            f"🚨 DuruOn 경보 ({event})\n"
                            f"몸각도≈{metrics['torso_angle']:.0f}° 쓰러짐={metrics['sudden_drop']} 무동작={metrics['immobile']}\n"
                            f"{time.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        # Localized button labels (Korean)
                        buttons=[("괜찮아요","ACK_OK"),("오탐","ACK_FALSE")]
                        if include_stop:
                            buttons.append(("중지","STOP_APP"))
                        notifier.send_text(text, buttons=buttons)
                        log_alert(event, metrics)
                        active_alert = {
                            'first_ts': time.time(),
                            'last_sent_ts': time.time(),
                            'repeats': 0,
                            'event': event,
                            'metrics': metrics,
                        }
                        try:
                            img = render_skeleton_image(pose)
                            notifier.send_photo(img, caption="Anonymized pose snapshot")
                        except Exception as e:
                            print("skeleton render failed:", e)
                    else:
                        # Clear alert status if no event
                        if led_system:
                            led_system.set_alert_status("none")

            else:
                # IDLE: Minimal processing, just waiting for PIR
                frame_count += 1
                
                # Minimal debug output when idle
                if current_time - last_debug >= 30:  # Every 30 seconds when idle
                    pir_status = pir_system.get_status() if pir_system else {"is_monitoring": False}
                    print(f"💤 IDLE: frames={frame_count}, PIR monitoring={pir_status.get('is_monitoring', False)}")
                    last_debug = current_time

            # Telegram callback polling (ack buttons)
            if current_time - last_callback_check >= callback_interval:
                last_callback_check = current_time
                try:
                    cb = notifier.check_callbacks() if hasattr(notifier, 'check_callbacks') else None
                    if cb == 'ACK_OK':
                        if led_system:
                            led_system.set_alert_status('none')
                        print("✅ Alert acknowledged by user (OK)")
                        ack_ok_count += 1
                        active_alert = None
                    elif cb == 'ACK_FALSE':
                        if led_system:
                            led_system.set_alert_status('none')
                        print("🟡 Alert marked as false alarm by user")
                        false_positive_count += 1
                        active_alert = None
                    elif cb == 'STOP_APP':
                        print("🛑 STOP command received via Telegram")
                        running = False
                except Exception as e:
                    print(f"⚠️ Callback polling error: {e}")

            # Alert repeat logic
            if active_alert and repeat_after > 0 and max_repeats > 0:
                if (current_time - active_alert['last_sent_ts'] >= repeat_after and
                        active_alert['repeats'] < max_repeats):
                    # Resend reminder
                    metrics = active_alert['metrics']
                    # Korean localized reminder
                    reminder = (
                        f"⏰ 재알림: ({active_alert['event']}) 아직 확인되지 않았습니다\n"
                        f"각도≈{metrics['torso_angle']:.0f}° 무동작={metrics['immobile']} 낙하={metrics['sudden_drop']}\n"
                        f"{time.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    buttons=[("괜찮아요","ACK_OK"),("오탐","ACK_FALSE")]
                    if include_stop: buttons.append(("중지","STOP_APP"))
                    notifier.send_text(reminder, buttons=buttons)
                    log_alert(active_alert['event']+"_repeat", metrics)
                    active_alert['last_sent_ts'] = current_time
                    active_alert['repeats'] += 1
                    if active_alert['repeats'] >= max_repeats:
                        # Stop repeating further, keep state until ack or new event
                        pass

            # Heartbeat
            if heartbeat_enabled and next_heartbeat and current_time >= next_heartbeat:
                notifier.send_text(f"💓 상태 점검: 시스템 정상 동작 중. 확인={ack_ok_count} 오탐={false_positive_count}")
                next_heartbeat = current_time + heartbeat_interval

            # Adaptive threshold tuning (lightweight heuristic)
            total_events = ack_ok_count + false_positive_count
            if adaptive_soft_mult > 0 and adaptive_hard_mult > 0 and total_events - last_adapt_event_count >= adapt_interval_events and not active_alert:
                fp_ratio = false_positive_count / total_events if total_events else 0
                adjust = False
                if fp_ratio > 0.4:  # too many false alarms -> relax (increase durations)
                    soft_scale *= 1.10
                    hard_scale *= 1.05
                    adjust = True
                    reason = f"High false positive ratio {fp_ratio:.2f}" 
                elif fp_ratio < 0.05 and ack_ok_count - last_adapt_event_count >= adapt_interval_events:  # very few false alarms -> tighten slightly
                    soft_scale *= 0.95
                    hard_scale *= 0.97
                    adjust = True
                    reason = f"Low false positive ratio {fp_ratio:.2f}" 
                # Clamp scales
                soft_scale = max(min_scale, min(max_scale, soft_scale))
                hard_scale = max(min_scale, min(max_scale, hard_scale))
                if adjust:
                    risk.cfg.soft_immobility_s = base_soft_threshold * soft_scale * adaptive_soft_mult
                    risk.cfg.hard_immobility_s = base_hard_threshold * hard_scale * adaptive_hard_mult
                    print(f"🛠️ Adaptive tuning: soft={risk.cfg.soft_immobility_s:.1f}s hard={risk.cfg.hard_immobility_s:.1f}s (scales {soft_scale:.2f}/{hard_scale:.2f}) due to {reason}")
                last_adapt_event_count = total_events

            # Frame rate control
            if use_camera:
                sleep_time = max(0, 1.0/fps - 0.001)
                if not monitoring_active:
                    sleep_time *= 5  # Sleep longer when idle to save CPU
                time.sleep(sleep_time)
            else:
                time.sleep(0.1 if monitoring_active else 1.0)  # Slower when idle

    except KeyboardInterrupt:
        print("🛑 Keyboard interrupt received")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        if led_system:
            led_system.set_system_status("error")
        raise
    finally:
        print("🛑 Shutting down DuruOn...")
        
        # Stop PIR system first
        if pir_system:
            pir_system.stop()
        
        # Stop LED system last (handles GPIO cleanup)
        if led_system:
            led_system.stop()
            
        # Release camera
        if cap:
            cap.release()
            print("📷 Camera released")
            
        print("✅ DuruOn shutdown complete")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ns = ap.parse_args()
    run(ns.config)