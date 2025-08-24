"""
LED Status Indicators for DuruOn
Visual feedback for PIR sensor and monitoring status
"""

import time
import threading
from typing import Optional
import logging
import os

# Only import RPi.GPIO if available and not in problematic environment
GPIO_AVAILABLE = False
try:
    # Check if we're on actual Pi hardware and not in a container/test environment
    if os.path.exists('/proc/cpuinfo'):
        with open('/proc/cpuinfo', 'r') as f:
            if 'raspberry' in f.read().lower():
                import RPi.GPIO as GPIO
                GPIO_AVAILABLE = True
except (ImportError, Exception):
    pass

class LEDStatus:
    """LED status indicator system for DuruOn"""
    
    def __init__(self, 
                 green_pin: int = 18,  # System status
                 blue_pin: int = 23,   # PIR activity
                 red_pin: int = 25):   # Alert status
        """
        Initialize LED status system
        
        Args:
            green_pin: GPIO pin for system status LED
            blue_pin: GPIO pin for PIR activity LED  
            red_pin: GPIO pin for alert status LED
        """
        self.green_pin = green_pin
        self.blue_pin = blue_pin
        self.red_pin = red_pin
        
        # LED states
        self.system_status = "starting"  # starting, idle, active, error
        self.pir_status = "clear"        # clear, triggered, monitoring
        self.alert_status = "none"       # none, soft, emergency
        
        # Threading
        self.running = False
        self.led_thread: Optional[threading.Thread] = None
        
        # Timing
        self.last_pir_flash = 0
        self.blink_state = False
        self.blink_counter = 0
        
        # Mock mode state tracking
        self._last_led_states = {}
        self.gpio_working = GPIO_AVAILABLE
        
        self.logger = logging.getLogger('DuruOn.LED')
        
        # Initialize GPIO
        self._setup_gpio()
        
    def _setup_gpio(self):
        """Initialize GPIO for LEDs"""
        if not GPIO_AVAILABLE:
            self.logger.warning("🚨 RPi.GPIO not available - LED indicators running in MOCK mode")
            print("💡 LED Status: Running in MOCK mode - will show LED states in console")
            return
            
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.green_pin, GPIO.OUT)
            GPIO.setup(self.blue_pin, GPIO.OUT)
            GPIO.setup(self.red_pin, GPIO.OUT)
            
            # Start with all LEDs off
            GPIO.output(self.green_pin, GPIO.LOW)
            GPIO.output(self.blue_pin, GPIO.LOW)
            GPIO.output(self.red_pin, GPIO.LOW)
            
            self.logger.info(f"✅ LED indicators initialized: Green={self.green_pin}, Blue={self.blue_pin}, Red={self.red_pin}")
            print(f"💡 LED Status: Hardware mode - Green={self.green_pin}, Blue={self.blue_pin}, Red={self.red_pin}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to setup LED indicators: {e}")
            print(f"⚠️  LED Status: Hardware setup failed, falling back to MOCK mode")
            self.gpio_working = False
            
    def _set_led(self, pin: int, state: bool):
        """Set LED state (with mock support)"""
        if GPIO_AVAILABLE and self.gpio_working:
            try:
                GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
            except Exception as e:
                self.logger.error(f"Error controlling LED {pin}: {e}")
                self.gpio_working = False
        else:
            # Mock mode - only log state changes to reduce spam
            led_name = {self.green_pin: "🟢 GREEN", self.blue_pin: "🔵 BLUE", self.red_pin: "🔴 RED"}.get(pin, f"PIN{pin}")
            if self._last_led_states.get(pin) != state:
                state_str = "ON" if state else "OFF"
                print(f"💡 {led_name} LED: {state_str}")
                self._last_led_states[pin] = state
            
    def start(self):
        """Start LED status system"""
        if self.running:
            return
            
        self.running = True
        self.led_thread = threading.Thread(target=self._led_loop, daemon=True)
        self.led_thread.start()
        
        self.set_system_status("idle")
        self.logger.info("🚀 DuruOn LED status indicators started")
        print("🚀 LED Status: Indicators started")
        
    def stop(self):
        """Stop LED status system"""
        self.running = False
        
        if self.led_thread:
            self.led_thread.join(timeout=2.0)
            
        # Turn off all LEDs and cleanup GPIO
        if GPIO_AVAILABLE and self.gpio_working:
            try:
                GPIO.output(self.green_pin, GPIO.LOW)
                GPIO.output(self.blue_pin, GPIO.LOW)
                GPIO.output(self.red_pin, GPIO.LOW)
                self.logger.info("🔧 GPIO cleanup: All LEDs turned OFF")
                GPIO.cleanup()
                self.logger.info("🧹 GPIO cleanup completed")
            except Exception as e:
                self.logger.error(f"GPIO cleanup error: {e}")
        else:
            print("💡 All LEDs: OFF")
                
        self.logger.info("🛑 DuruOn LED indicators stopped")
        print("🛑 LED Status: Indicators stopped")
        
    def _led_loop(self):
        """Main LED control loop"""
        while self.running:
            try:
                current_time = time.time()
                self.blink_counter += 1
                
                # Update blink state (500ms cycle)
                if self.blink_counter % 5 == 0:
                    self.blink_state = not self.blink_state
                
                # Control Green LED (System Status)
                if self.system_status == "starting":
                    # Fast blink during startup
                    self._set_led(self.green_pin, self.blink_counter % 2 == 0)
                elif self.system_status == "idle":
                    # Slow blink when idle
                    self._set_led(self.green_pin, self.blink_counter % 10 < 2)
                elif self.system_status == "active":
                    # Solid on when active
                    self._set_led(self.green_pin, True)
                elif self.system_status == "error":
                    # Very fast blink on error
                    self._set_led(self.green_pin, self.blink_counter % 1 == 0)
                else:
                    self._set_led(self.green_pin, False)
                
                # Control Blue LED (PIR Status)
                if self.pir_status == "triggered":
                    # Quick flash for PIR trigger (2 second flash only)
                    if current_time - self.last_pir_flash < 2.0:
                        self._set_led(self.blue_pin, self.blink_counter % 2 == 0)
                    else:
                        # After flash, turn off - wait for explicit monitoring status
                        self._set_led(self.blue_pin, False)
                elif self.pir_status == "monitoring":
                    # Solid on during active monitoring
                    self._set_led(self.blue_pin, True)
                else:
                    # Off when clear or idle
                    self._set_led(self.blue_pin, False)
                
                # Control Red LED (Alert Status)
                if self.alert_status == "soft":
                    # Slow blink for soft alert
                    self._set_led(self.red_pin, self.blink_counter % 10 < 5)
                elif self.alert_status == "emergency":
                    # Fast blink for emergency
                    self._set_led(self.red_pin, self.blink_counter % 4 < 2)
                else:
                    # Off when no alert
                    self._set_led(self.red_pin, False)
                
                # Sleep for 100ms (10Hz update rate)
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error in LED control loop: {e}")
                time.sleep(1.0)
    
    def set_system_status(self, status: str):
        """Set system status: starting, idle, active, error"""
        self.system_status = status
        self.logger.info(f"🟢 System status: {status.upper()}")
        
    def set_pir_status(self, status: str):
        """Set PIR status: clear, triggered, monitoring"""
        if status == "triggered":
            self.last_pir_flash = time.time()
        self.pir_status = status
        self.logger.info(f"🔵 PIR status: {status.upper()}")
        
    def set_alert_status(self, status: str):
        """Set alert status: none, soft, emergency"""
        self.alert_status = status
        self.logger.info(f"🔴 Alert status: {status.upper()}")
        
    def flash_pir(self):
        """Quick flash blue LED for PIR trigger"""
        self.set_pir_status("triggered")
        
    def get_status(self) -> dict:
        """Get current LED status"""
        return {
            "system_status": self.system_status,
            "pir_status": self.pir_status,
            "alert_status": self.alert_status,
            "gpio_available": GPIO_AVAILABLE,
            "gpio_working": self.gpio_working,
            "pins": {
                "green": self.green_pin,
                "blue": self.blue_pin,
                "red": self.red_pin
            }
        }