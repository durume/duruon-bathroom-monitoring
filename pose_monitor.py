#!/usr/bin/env python3
"""
BathGuard Real-time Pose Monitor - FIXED VERSION
Shows live pose detection data in a user-friendly format
"""
import time
import subprocess
import json
import re
from datetime import datetime

class PoseMonitor:
    def __init__(self):
        self.last_data = {}
        
    def parse_log_line(self, line):
        """Parse BathGuard log lines"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Parse ACTIVE logs with pose data
        active_pattern = r'🔍 ACTIVE: frames=(\d+), torso_angle=([\d.]+)°, vx=([-\d.]+), vy=([-\d.]+)'
        match = re.search(active_pattern, line)
        if match:
            return {
                'frames': int(match.group(1)),
                'present': True,
                'torso_angle': float(match.group(2)),
                'vx': float(match.group(3)),
                'vy': float(match.group(4)),
                'sudden_drop': False,  # Would need risk engine data
                'rapid_angle_change': False,
                'angle_change': 0.0,
                'immobile': False,
                'event': None,
                'timestamp': timestamp,
                'state': 'ACTIVE'
            }
        
        # Parse ACTIVE logs with no person
        no_person_pattern = r'🔍 ACTIVE: frames=(\d+), no person detected'
        match = re.search(no_person_pattern, line)
        if match:
            return {
                'frames': int(match.group(1)),
                'present': False,
                'torso_angle': 0.0,
                'vx': 0.0,
                'vy': 0.0,
                'sudden_drop': False,
                'rapid_angle_change': False,
                'angle_change': 0.0,
                'immobile': False,
                'event': None,
                'timestamp': timestamp,
                'state': 'ACTIVE'
            }
        
        # Parse IDLE logs
        idle_pattern = r'💤 IDLE: frames=(\d+), PIR monitoring=(\w+)'
        match = re.search(idle_pattern, line)
        if match:
            return {
                'frames': int(match.group(1)),
                'present': False,
                'torso_angle': 0.0,
                'vx': 0.0,
                'vy': 0.0,
                'sudden_drop': False,
                'rapid_angle_change': False,
                'angle_change': 0.0,
                'immobile': False,
                'event': None,
                'timestamp': timestamp,
                'state': 'IDLE'
            }
            
        return None
        
    def display_status(self, data):
        """Display current pose status"""
        print("\033[2J\033[H", end="")  # Clear screen and move cursor to top
        print("🚿 BathGuard Real-time Pose Monitor - FIXED")
        print("=" * 50)
        print(f"⏰ Last Update: {data['timestamp']}")
        print(f"📊 Frame Count: {data['frames']}")
        print(f"🔋 System State: {data.get('state', 'UNKNOWN')}")
        print()
        
        # Person detection
        if data['present']:
            print("👤 Person Detected: ✅ YES")
            
            print()
            print("📐 Posture Analysis:")
            print(f"   Torso Angle: {data['torso_angle']:.1f}°")
            
            # Posture interpretation
            if data['torso_angle'] <= 30:
                posture = "🔴 HORIZONTAL (Risk Zone)"
            elif data['torso_angle'] <= 45:
                posture = "🟡 LEANING"  
            elif data['torso_angle'] <= 70:
                posture = "🟢 SITTING"
            else:
                posture = "🟢 UPRIGHT"
            print(f"   Posture: {posture}")
            
            print()
            print("🔄 Vector Data:")
            print(f"   VX: {data.get('vx', 0):.3f}")
            print(f"   VY: {data.get('vy', 0):.3f}")
            
        else:
            print("👤 Person Detected: ❌ NO")
            if data.get('state') == 'IDLE':
                print("💤 System in IDLE mode - waiting for PIR activation")
            else:
                print("🔍 System ACTIVE - no person in frame")
            
        print()
        print("🚨 Alert Status:")
        if data.get('event'):
            print(f"   Active Alert: 🚨 {data['event'].upper()}")
        else:
            print("   Active Alert: ✅ NONE")
            
        print()
        print("💡 Controls:")
        print("   Ctrl+C to exit")
        print("   Live updates from BathGuard logs")
        
    def monitor(self):
        """Start monitoring pose detection"""
        print("🚀 Starting BathGuard Pose Monitor - FIXED VERSION...")
        print("📡 Connecting to BathGuard logs...")
        
        try:
            # Use journalctl to follow the logs
            process = subprocess.Popen(
                ['sudo', 'journalctl', '-u', 'bathguard', '-f', '--no-pager'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            for line in process.stdout:
                # Look for ACTIVE or IDLE patterns
                if ("🔍 ACTIVE:" in line) or ("💤 IDLE:" in line):
                    data = self.parse_log_line(line)
                    if data:
                        self.last_data = data
                        self.display_status(data)
                        
        except KeyboardInterrupt:
            print("\n🛑 Monitor stopped by user")
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            if 'process' in locals():
                process.terminate()

if __name__ == "__main__":
    monitor = PoseMonitor()
    monitor.monitor()