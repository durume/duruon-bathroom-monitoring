from collections import deque
from dataclasses import dataclass
from typing import Optional, Dict, Any
import math, time
from datetime import datetime
try:  # pragma: no cover
    from ..shared.pose import PoseResult  # type: ignore
except Exception:  # allow running without package context
    from shared.pose import PoseResult  # type: ignore

@dataclass
class RiskConfig:
    angle_threshold_deg: float = 50.0
    drop_threshold: float = 0.25
    drop_window_s: float = 0.7
    immobile_window_s: float = 10.0
    immobile_motion_eps: float = 0.05
    soft_immobility_s: float = 30.0
    hard_immobility_s: float = 90.0  # fallback long immobility escalation
    fast_fall_immobility_s: float = 12.0  # NEW: required immobility after a detected fall candidate
    cooldown_s: float = 600.0
    confirm_grace_s: float = 6.0
    # Enhanced shower-aware parameters
    movement_tolerance_low_angle: float = 0.12
    movement_tolerance_high_angle: float = 0.05
    shower_mode_enabled: bool = True
    shower_start_hour: int = 6
    shower_end_hour: int = 22
    shower_duration_multiplier: float = 4.0
    # Original enhanced detection parameters
    angle_change_threshold: float = 30.0
    position_change_threshold: float = 0.15
    # Keypoint confidence gating (was hardcoded 0.1)
    min_kp_confidence: float = 0.10

class RiskEngine:
    def __init__(self, fps: int = 15, cfg: RiskConfig = None):
        self.fps = max(1, int(fps))
        self.cfg = cfg or RiskConfig()
        # History stores tuples: (timestamp, mid_hip, mid_shoulder, motion_scalar, torso_angle)
        self.hist = deque(maxlen=int(max(5, self.cfg.hard_immobility_s) + 5) * self.fps)
        self.last_alert_ts = 0.0
        self.soft_timer_start = None  # immobility timer start
        # Fall candidate tracking
        self.pending_fall_ts = None
        self.pending_fall_type = None

    def _mid(self, a: str, b: str, kp: Dict[str, tuple]):
        pa, pb = kp.get(a), kp.get(b)
        thr = getattr(self.cfg, 'min_kp_confidence', 0.1)
        if not pa or not pb or pa[2] < thr or pb[2] < thr:
            return None
        return ((pa[0]+pb[0])/2.0, (pa[1]+pb[1])/2.0)

    # --- Helper methods (unified versions) ---
    def _is_shower_time(self) -> bool:
        if not self.cfg.shower_mode_enabled:
            return False
        hour = datetime.now().hour
        return self.cfg.shower_start_hour <= hour <= self.cfg.shower_end_hour

    def _get_adaptive_thresholds(self, angle_deg: float, is_shower_time: bool) -> Dict[str, float]:
        """Return dict with motion_eps, immobile_window, soft_immobility, hard_immobility.
        Consolidated logic (removed duplicate definitions)."""
        motion_eps = (self.cfg.movement_tolerance_low_angle
                      if angle_deg <= self.cfg.angle_threshold_deg else
                      self.cfg.movement_tolerance_high_angle)
        immobile_window = self.cfg.immobile_window_s
        soft_imm = self.cfg.soft_immobility_s
        hard_imm = self.cfg.hard_immobility_s
        if is_shower_time:
            mult = self.cfg.shower_duration_multiplier
            immobile_window *= mult
            soft_imm *= mult
            hard_imm *= mult
        return {
            'motion_eps': motion_eps,
            'immobile_window': immobile_window,
            'soft_immobility': soft_imm,
            'hard_immobility': hard_imm,
        }

    def update(self, pose: PoseResult) -> Dict[str, Any]:
        ts = pose.ts
        kp = pose.keypoints
        mh = self._mid("left_hip","right_hip", kp)
        ms = self._mid("left_shoulder","right_shoulder", kp)
        if not mh or not ms:
            self.hist.append((ts, None, None, 0.0, None))
            self.soft_timer_start = None
            self.pending_fall_ts = None
            return {"present": False, "event": None}

        # CORRECTED: Proper angle calculation for torso uprightness
        # Vector from hip to shoulder (torso direction)
        vx, vy = (ms[0]-mh[0], ms[1]-mh[1])
        
        # FINAL FIX: Correct angle calculation
        # In image coordinates: Y increases downward
        # When upright: vy < 0 (shoulders above hips)
        # When horizontal: vy ≈ 0 (shoulders level with hips)
        
        if abs(vx) < 0.001 and abs(vy) < 0.001:
            # Hip and shoulder at same level - horizontal position
            angle_deg = 0.0
        else:
            # Calculate angle from vertical axis (upright = 90°, horizontal = 0°)
            # atan2(abs(vx), abs(vy)) gives angle from vertical
            angle_rad = math.atan2(abs(vx), abs(vy))  
            angle_deg = math.degrees(angle_rad)
            
            # When person is upright: vx small, vy large (negative) -> angle near 0° from vertical = 90° from horizontal
            # When person is horizontal: vx large, vy small -> angle near 90° from vertical = 0° from horizontal
            angle_deg = 90.0 - angle_deg  # Convert to "upright angle"
            angle_deg = max(0.0, min(90.0, angle_deg))  # Clamp to valid range

        # Enhanced motion detection
        motion = 0.0
        angle_change = 0.0
        if self.hist:
            _, pmh, pms, _, prev_angle = self.hist[-1]
            if pmh and pms and prev_angle is not None:
                motion = math.hypot(mh[0]-pmh[0], mh[1]-pmh[1]) + math.hypot(ms[0]-pms[0], ms[1]-pms[1])
                angle_change = abs(angle_deg - prev_angle)

        self.hist.append((ts, mh, ms, motion, angle_deg))

        # Get adaptive thresholds (unified)
        is_shower_time = self._is_shower_time()
        thresholds = self._get_adaptive_thresholds(angle_deg, is_shower_time)

        # Enhanced sudden drop detection
        window = [(t,h,s,m,a) for (t,h,s,m,a) in self.hist if h and s and t >= ts - self.cfg.drop_window_s]
        sudden_drop = False
        rapid_angle_change = False
        large_position_change = False
        
        dy = 0.0
        angle_change_total = 0.0
        if len(window) >= 2:
            # FIXED: Original vertical drop detection - access y coordinate correctly
            dy = mh[1] - window[0][1][1]
            sudden_drop = dy >= self.cfg.drop_threshold
            # Rapid angle change detection
            angle_start = window[0][4]
            angle_change_total = abs(angle_deg - angle_start)
            rapid_angle_change = angle_change_total >= self.cfg.angle_change_threshold
            # Enhanced position change detection
            hip_start = window[0][1]
            shoulder_start = window[0][2]
            total_position_change = (math.hypot(mh[0]-hip_start[0], mh[1]-hip_start[1]) + 
                                     math.hypot(ms[0]-shoulder_start[0], ms[1]-shoulder_start[1]))
            large_position_change = total_position_change >= self.cfg.position_change_threshold

        # Combine drop detection methods
        sudden_drop = sudden_drop or rapid_angle_change or large_position_change

        # Adaptive immobility detection
        motions = [m for (t,_,_,m,_) in self.hist if t >= ts - thresholds['immobile_window']]
        immobile = (sum(motions)/max(1,len(motions))) < thresholds['motion_eps'] if motions else False

        # FIXED: Risk candidate detection - LOW angles are dangerous (horizontal), not high angles
        # Broaden fall candidate logic: allow rapid orientation or large displacement even if not yet fully horizontal
        if sudden_drop and (angle_deg <= self.cfg.angle_threshold_deg or rapid_angle_change):
            self.pending_fall_ts = ts
            self.pending_fall_type = 'drop'
        if self.pending_fall_ts and ts - self.pending_fall_ts > self.cfg.confirm_grace_s:
            # If within grace we have not accumulated enough immobility, downgrade to plain immobility tracking
            if self.pending_fall_type == 'drop' and self.soft_timer_start is None:
                # fall candidate expired; treat as regular immobility path
                pass
            self.pending_fall_ts = None
            self.pending_fall_type = None

        event = None
        now = ts
        
        # Hard fall: detected drop + low angle (horizontal) + sustained immobility
        if self.pending_fall_ts and immobile:
            # Start immobility timer for drop scenario if not already started
            if self.soft_timer_start is None:
                self.soft_timer_start = now
            else:
                time_immobile = now - self.soft_timer_start
                fast_needed = getattr(self.cfg, 'fast_fall_immobility_s', None)
                if fast_needed is None:
                    fast_needed = thresholds['hard_immobility']  # fallback
                # Allow very short thresholds for unit tests (they customize hard/soft)
                effective_needed = min(fast_needed, thresholds['hard_immobility'])
                if time_immobile >= effective_needed:
                    if now - self.last_alert_ts >= self.cfg.cooldown_s:
                        event = "hard_fall"
                        self.last_alert_ts = now
                    self.pending_fall_ts = None
                    self.pending_fall_type = None
                    self.soft_timer_start = None
        else:
            # Tiered immobility detection.
            # LOW angle (horizontal) immobility -> potential fall progression.
            # HIGH angle (upright) prolonged immobility can still warrant a soft check (e.g., faint while seated upright) so allow soft tier.
            horizontal_risky = angle_deg <= self.cfg.angle_threshold_deg
            if immobile and (horizontal_risky or self.soft_timer_start is not None or self.soft_timer_start is None):
                # Start timer for any immobility; escalation differs by angle.
                if self.soft_timer_start is None:
                    self.soft_timer_start = now
                else:
                    time_immobile = now - self.soft_timer_start
                    # Soft immobility: any immobility exceeding soft threshold; if horizontal_risky escalate later.
                    if (time_immobile >= thresholds['soft_immobility'] and 
                        time_immobile < thresholds['hard_immobility'] and event is None):
                        if now - self.last_alert_ts >= self.cfg.cooldown_s:
                            event = "soft_immobility"
                            self.last_alert_ts = now
                    # Hard immobility: only escalate to hard if horizontal OR very prolonged (2x hard threshold) while upright.
                    if time_immobile >= thresholds['hard_immobility']:
                        # Fallback escalation after prolonged immobility
                        escalate = horizontal_risky or time_immobile >= (thresholds['hard_immobility'] * 2)
                        if escalate and now - self.last_alert_ts >= self.cfg.cooldown_s:
                            event = "hard_immobility"
                            self.last_alert_ts = now
                            self.soft_timer_start = None
            else:
                self.soft_timer_start = None

        return {
            "present": True,
            "torso_angle": angle_deg,
            "sudden_drop": sudden_drop,
            "immobile": immobile,
            "event": event,
            "rapid_angle_change": rapid_angle_change if len(window) >= 2 else False,
            "angle_change": angle_change,
            "angle_change_total": angle_change_total,
            "vertical_dy": dy,
            "is_shower_time": is_shower_time,
            "adaptive_motion_eps": thresholds['motion_eps'],
            "adaptive_soft_threshold": thresholds['soft_immobility'],
            "adaptive_hard_threshold": thresholds['hard_immobility'],
            "debug_vx": vx,
            "debug_vy": vy
        }
    
    # (Removed duplicate helper definitions below)