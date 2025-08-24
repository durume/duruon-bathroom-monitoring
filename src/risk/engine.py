from collections import deque
from dataclasses import dataclass
from typing import Optional, Dict, Any
import math, time
from datetime import datetime
from ..shared.pose import PoseResult

@dataclass
class RiskConfig:
    angle_threshold_deg: float = 50.0
    drop_threshold: float = 0.25
    drop_window_s: float = 0.7
    immobile_window_s: float = 10.0
    immobile_motion_eps: float = 0.05
    soft_immobility_s: float = 30.0
    hard_immobility_s: float = 60.0
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

class RiskEngine:
    def __init__(self, fps: int = 15, cfg: RiskConfig = None):
        self.fps = max(1, int(fps))
        self.cfg = cfg or RiskConfig()
        self.hist = deque(maxlen=int(max(5, self.cfg.hard_immobility_s)+5)*self.fps)
        self.last_alert_ts = 0.0
        self.soft_timer_start: Optional[float] = None
        self.pending_fall_ts: Optional[float] = None

    def _mid(self, a: str, b: str, kp: Dict[str, tuple]):
        pa, pb = kp.get(a), kp.get(b)
        if not pa or not pb or pa[2] < 0.1 or pb[2] < 0.1: return None
        return ((pa[0]+pb[0])/2.0, (pa[1]+pb[1])/2.0)

    def _is_shower_time(self) -> bool:
        """Check if current time is within shower hours"""
        if not self.cfg.shower_mode_enabled:
            return False
        current_hour = datetime.now().hour
        return self.cfg.shower_start_hour <= current_hour <= self.cfg.shower_end_hour

    def _get_adaptive_thresholds(self, angle_deg: float, is_shower_time: bool) -> Dict[str, float]:
        """Get adaptive thresholds based on posture and time"""
        # Base thresholds
        immobile_window = self.cfg.immobile_window_s
        soft_immobility = self.cfg.soft_immobility_s
        hard_immobility = self.cfg.hard_immobility_s
        
        # Adaptive movement tolerance based on angle
        if angle_deg <= self.cfg.angle_threshold_deg:
            # Person is bent/low - use more lenient movement tolerance
            motion_eps = self.cfg.movement_tolerance_low_angle
        else:
            # Person is upright - use stricter movement tolerance
            motion_eps = self.cfg.movement_tolerance_high_angle
        
        # Apply shower time multiplier
        if is_shower_time:
            multiplier = self.cfg.shower_duration_multiplier
            immobile_window *= multiplier
            soft_immobility *= multiplier
            hard_immobility *= multiplier
            
        return {
            'immobile_window': immobile_window,
            'soft_immobility': soft_immobility,
            'hard_immobility': hard_immobility,
            'motion_eps': motion_eps
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

        # Get adaptive thresholds
        is_shower_time = self._is_shower_time()
        thresholds = self._get_adaptive_thresholds(angle_deg, is_shower_time)

        # Enhanced sudden drop detection
        window = [(t,h,s,m,a) for (t,h,s,m,a) in self.hist if h and s and t >= ts - self.cfg.drop_window_s]
        sudden_drop = False
        rapid_angle_change = False
        large_position_change = False
        
        if len(window) >= 2:
            # FIXED: Original vertical drop detection - access y coordinate correctly
            dy = mh[1] - window[0][1][1]  # window[0][1] is mh tuple, so [1] is y-coord
            sudden_drop = dy >= self.cfg.drop_threshold
            
            # Rapid angle change detection
            angle_start = window[0][4]
            angle_change_total = abs(angle_deg - angle_start)
            rapid_angle_change = angle_change_total >= self.cfg.angle_change_threshold
            
            # FIXED: Enhanced position change detection
            hip_start = window[0][1]     # mh tuple from start
            shoulder_start = window[0][2] # ms tuple from start
            total_position_change = (math.hypot(mh[0]-hip_start[0], mh[1]-hip_start[1]) + 
                                   math.hypot(ms[0]-shoulder_start[0], ms[1]-shoulder_start[1]))
            large_position_change = total_position_change >= self.cfg.position_change_threshold

        # Combine drop detection methods
        sudden_drop = sudden_drop or rapid_angle_change or large_position_change

        # Adaptive immobility detection
        motions = [m for (t,_,_,m,_) in self.hist if t >= ts - thresholds['immobile_window']]
        immobile = (sum(motions)/max(1,len(motions))) < thresholds['motion_eps'] if motions else False

        # FIXED: Risk candidate detection - LOW angles are dangerous (horizontal), not high angles
        if sudden_drop and angle_deg <= self.cfg.angle_threshold_deg:
            self.pending_fall_ts = ts
        if self.pending_fall_ts and ts - self.pending_fall_ts > self.cfg.confirm_grace_s:
            self.pending_fall_ts = None

        event = None
        now = ts
        
        # Hard fall: detected drop + low angle (horizontal) + sustained immobility
        if self.pending_fall_ts and immobile:
            # Start immobility timer for drop scenario if not already started
            if self.soft_timer_start is None:
                self.soft_timer_start = now
            else:
                time_immobile = now - self.soft_timer_start
                
                # Require same immobility duration as regular alerts
                if time_immobile >= thresholds['hard_immobility']:
                    if now - self.last_alert_ts >= self.cfg.cooldown_s:
                        event = "hard_fall"
                        self.last_alert_ts = now
                    self.pending_fall_ts = None
                    self.soft_timer_start = None
        else:
            # Tiered immobility detection with adaptive thresholds - LOW angles are risky
            if angle_deg <= self.cfg.angle_threshold_deg and immobile:
                if self.soft_timer_start is None:
                    self.soft_timer_start = now
                else:
                    time_immobile = now - self.soft_timer_start
                    
                    # Soft alert after adaptive threshold
                    if (time_immobile >= thresholds['soft_immobility'] and 
                        time_immobile < thresholds['hard_immobility']):
                        if now - self.last_alert_ts >= self.cfg.cooldown_s:
                            event = "soft_immobility"
                            self.last_alert_ts = now
                    
                    # Hard alert after longer adaptive threshold
                    elif time_immobile >= thresholds['hard_immobility']:
                        if now - self.last_alert_ts >= self.cfg.cooldown_s:
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
            # Debug info
            "rapid_angle_change": rapid_angle_change if len(window) >= 2 else False,
            "angle_change": angle_change,
            # Shower-aware debug info
            "is_shower_time": is_shower_time,
            "adaptive_motion_eps": thresholds['motion_eps'],
            "adaptive_soft_threshold": thresholds['soft_immobility'],
            "adaptive_hard_threshold": thresholds['hard_immobility'],
            # Debug angle calculation
            "debug_vx": vx,
            "debug_vy": vy
        }
    
    def _get_adaptive_thresholds(self, angle_deg, is_shower_time):
        """Calculate adaptive thresholds based on pose angle and shower mode"""
        # Use adaptive movement tolerance based on angle
        if angle_deg <= self.cfg.angle_threshold_deg:  # Horizontal/risky position
            motion_tolerance = self.cfg.movement_tolerance_low_angle
        else:  # Upright position
            motion_tolerance = self.cfg.movement_tolerance_high_angle
            
        # Apply shower time multiplier if enabled
        multiplier = self.cfg.shower_duration_multiplier if (is_shower_time and self.cfg.shower_mode_enabled) else 1.0
        
        return {
            'motion_eps': motion_tolerance,
            'immobile_window': self.cfg.immobile_window_s,
            'soft_immobility': self.cfg.soft_immobility_s * multiplier,
            'hard_immobility': self.cfg.hard_immobility_s * multiplier
        }
    
    def _is_shower_time(self):
        """Check if current time is within shower hours"""
        if not self.cfg.shower_mode_enabled:
            return False
            
        from datetime import datetime
        current_hour = datetime.now().hour
        return self.cfg.shower_start_hour <= current_hour <= self.cfg.shower_end_hour