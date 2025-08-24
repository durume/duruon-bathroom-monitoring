"""
PIR Sensor Activation System for DuruOn - Fixed GPIO sharing
"""

import time
import threading
from typing import Callable, Optional
import logging
import os

# Only import RPi.GPIO if we're actually on a Pi and not in a container/test environment
GPIO_AVAILABLE = False
try:
    # Check if we're on actual Pi hardware
    if os.path.exists('/proc/cpuinfo'):
        with open('/proc/cpuinfo', 'r') as f:
            if 'raspberry' in f.read().lower():
                import RPi.GPIO as GPIO
                GPIO_AVAILABLE = True
except (ImportError, Exception):
    pass

class PIRActivation:
    """PIR sensor activation system for DuruOn"""
    
    def __init__(self, 
                 pir_pin: int = 24,
                 debounce_time: float = 2.0,
                 activation_grace_period: float = 10.0,
                 auto_sleep_timeout: float = 300.0):
        """
        Initialize PIR activation system
        
        Args:
            pir_pin: GPIO pin number for PIR sensor (BCM numbering)
            debounce_time: Minimum time between PIR triggers (seconds)
            activation_grace_period: Delay before full monitoring starts (seconds) 
            auto_sleep_timeout: Time to sleep after no motion (seconds)
        """
        self.pir_pin = pir_pin
        self.debounce_time = debounce_time
        self.activation_grace_period = activation_grace_period
        self.auto_sleep_timeout = auto_sleep_timeout
        
        # State tracking
        self.is_monitoring = False
        self.last_motion_time = 0
        self.last_trigger_time = 0
        self.grace_period_active = False
        self.gpio_initialized = False
        
        # Enhanced tracking for logging
        self.pir_trigger_count = 0
        self.last_pir_state = False
        self.last_status_log = 0
        
        # Mock mode simulation
        self.mock_motion_counter = 0
        
        # Callbacks
        self.activation_callback: Optional[Callable] = None
        self.deactivation_callback: Optional[Callable] = None
        
        # Threading
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        self.logger = logging.getLogger('DuruOn.PIR')
        
        # Initialize GPIO
        self._setup_gpio()
        
    def _setup_gpio(self):
        """Initialize GPIO for PIR sensor - share GPIO with LED system"""
        if not GPIO_AVAILABLE:
            self.logger.warning("🚨 RPi.GPIO not available - PIR sensor running in MOCK mode")
            self.logger.info("📋 Mock mode will simulate motion detection for testing")
            return
            
        try:
            # Try to set GPIO mode, but don't fail if already set
            try:
                GPIO.setmode(GPIO.BCM)
            except:
                # GPIO mode already set by LED system, continue
                pass
                
            GPIO.setup(self.pir_pin, GPIO.IN)
            self.gpio_initialized = True
            self.logger.info(f"✅ PIR sensor initialized on GPIO {self.pir_pin} - HARDWARE mode")
            
            # Test initial PIR state
            initial_state = GPIO.input(self.pir_pin)
            self.logger.info(f"📡 Initial PIR state: {'HIGH (motion)' if initial_state else 'LOW (no motion)'}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to setup PIR sensor: {e}")
            self.logger.info("🔄 Falling back to MOCK mode")
            self.gpio_initialized = False
            
    def _read_pir(self) -> bool:
        """Read PIR sensor state"""
        if not GPIO_AVAILABLE or not self.gpio_initialized:
            # Mock PIR for testing - simulate motion every ~8-12 seconds
            self.mock_motion_counter += 1
            
            # Simulate motion detection pattern
            if self.mock_motion_counter >= 40:  # ~8 seconds at 5Hz polling
                if self.mock_motion_counter <= 45:  # Motion for ~1 second
                    return True
                elif self.mock_motion_counter >= 60:  # Reset after 12 seconds
                    self.mock_motion_counter = 0
            return False
            
        try:
            current_state = GPIO.input(self.pir_pin) == GPIO.HIGH
            
            # Log PIR state changes
            if current_state != self.last_pir_state:
                if current_state:
                    self.pir_trigger_count += 1
                    self.logger.info(f"🔴 PIR TRIGGER #{self.pir_trigger_count} - Motion detected on GPIO {self.pir_pin}")
                else:
                    self.logger.info(f"🔵 PIR CLEAR - Motion ended on GPIO {self.pir_pin}")
                self.last_pir_state = current_state
            
            return current_state
            
        except Exception as e:
            self.logger.error(f"Error reading PIR sensor: {e}")
            return False
            
    def set_activation_callback(self, callback: Callable):
        """Set callback function to call when monitoring should start"""
        self.activation_callback = callback
        
    def set_deactivation_callback(self, callback: Callable):
        """Set callback function to call when monitoring should stop"""
        self.deactivation_callback = callback
        
    def start(self):
        """Start the PIR monitoring system"""
        if self.running:
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        mode = "HARDWARE" if (GPIO_AVAILABLE and self.gpio_initialized) else "MOCK"
        self.logger.info(f"🚀 PIR activation system started in {mode} mode - DuruOn in IDLE state")
        
        # Log detailed configuration
        self.logger.info(f"⚙️  PIR Configuration: pin={self.pir_pin}, debounce={self.debounce_time}s, "
                        f"grace={self.activation_grace_period}s, timeout={self.auto_sleep_timeout}s")
        
    def stop(self):
        """Stop the PIR monitoring system"""
        self.running = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
            
        # Don't cleanup GPIO - let LED system handle it
        self.logger.info("🛑 PIR activation system stopped")
        
    def _monitor_loop(self):
        """Main PIR monitoring loop"""
        while self.running:
            try:
                current_time = time.time()
                
                # Read PIR sensor
                motion_detected = self._read_pir()
                
                if motion_detected:
                    self.last_motion_time = current_time
                    
                    # Check if we should activate (with debouncing)
                    if (not self.is_monitoring and 
                        current_time - self.last_trigger_time >= self.debounce_time):
                        
                        self._activate_monitoring()
                        self.last_trigger_time = current_time
                        
                # Check for auto-sleep timeout
                elif (self.is_monitoring and 
                      current_time - self.last_motion_time > self.auto_sleep_timeout):
                    self._deactivate_monitoring()
                
                # Enhanced status logging every 60 seconds
                if current_time - self.last_status_log >= 60:
                    self._log_status()
                    self.last_status_log = current_time
                    
                # Sleep for sensor polling rate
                time.sleep(0.2)  # 5Hz polling rate
                
            except Exception as e:
                self.logger.error(f"Error in PIR monitor loop: {e}")
                time.sleep(1.0)
    
    def _log_status(self):
        """Log detailed PIR system status"""
        mode = "HARDWARE" if (GPIO_AVAILABLE and self.gpio_initialized) else "MOCK"
        status = "MONITORING" if self.is_monitoring else "IDLE"
        
        time_since_motion = time.time() - self.last_motion_time if self.last_motion_time else 0
        auto_sleep_in = max(0, self.auto_sleep_timeout - time_since_motion) if self.last_motion_time else 0
        
        self.logger.info(f"📊 PIR Status: {mode} mode, {status}, "
                        f"triggers={self.pir_trigger_count}, "
                        f"last_motion={time_since_motion:.0f}s ago, "
                        f"auto_sleep_in={auto_sleep_in:.0f}s")
                
    def _activate_monitoring(self):
        """Activate full DuruOn monitoring"""
        if self.is_monitoring:
            return
            
        mode_indicator = "🔴" if (GPIO_AVAILABLE and self.gpio_initialized) else "🟠"
        self.logger.info(f"{mode_indicator} PIR MOTION DETECTED - Activating DuruOn monitoring")
        
        # Grace period
        if self.activation_grace_period > 0:
            self.logger.info(f"⏱️  Grace period: {self.activation_grace_period:.0f}s before full monitoring")
            self.grace_period_active = True
            
            # Start grace period in separate thread
            grace_thread = threading.Thread(
                target=self._grace_period_timer, 
                daemon=True
            )
            grace_thread.start()
        else:
            self._start_full_monitoring()
            
    def _grace_period_timer(self):
        """Handle grace period before starting full monitoring"""
        time.sleep(self.activation_grace_period)
        if self.running and self.grace_period_active:
            self._start_full_monitoring()
            
    def _start_full_monitoring(self):
        """Start full monitoring after grace period"""
        self.is_monitoring = True
        self.grace_period_active = False
        
        self.logger.info("🟢 FULL MONITORING ACTIVE - Pose detection and risk analysis started")
        
        # Call activation callback
        if self.activation_callback:
            try:
                self.activation_callback()
            except Exception as e:
                self.logger.error(f"Error in activation callback: {e}")
                
    def _deactivate_monitoring(self):
        """Deactivate monitoring and return to idle"""
        if not self.is_monitoring:
            return
            
        self.is_monitoring = False
        self.grace_period_active = False
        
        timeout_minutes = self.auto_sleep_timeout / 60
        self.logger.info(f"💤 AUTO-SLEEP - No motion for {timeout_minutes:.1f} minutes, returning to IDLE mode")
        
        # Call deactivation callback
        if self.deactivation_callback:
            try:
                self.deactivation_callback()
            except Exception as e:
                self.logger.error(f"Error in deactivation callback: {e}")
                
    def update_motion(self):
        """Update motion timestamp (call this when person detected via pose)"""
        self.last_motion_time = time.time()
        
    def force_activate(self):
        """Manually activate monitoring (for testing)"""
        self.logger.info("🔧 MANUAL ACTIVATION")
        self._activate_monitoring()
        
    def force_deactivate(self):
        """Manually deactivate monitoring (for testing)"""
        self.logger.info("🔧 MANUAL DEACTIVATION")
        self._deactivate_monitoring()
        
    def get_status(self) -> dict:
        """Get current PIR system status"""
        current_time = time.time()
        
        return {
            "is_monitoring": self.is_monitoring,
            "grace_period_active": self.grace_period_active,
            "last_motion_ago": current_time - self.last_motion_time if self.last_motion_time else None,
            "auto_sleep_in": max(0, self.auto_sleep_timeout - (current_time - self.last_motion_time)) if self.last_motion_time else 0,
            "pir_pin": self.pir_pin,
            "gpio_available": GPIO_AVAILABLE,
            "gpio_initialized": self.gpio_initialized,
            "mode": "HARDWARE" if (GPIO_AVAILABLE and self.gpio_initialized) else "MOCK",
            "trigger_count": self.pir_trigger_count
        }