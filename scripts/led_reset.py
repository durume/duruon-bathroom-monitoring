#!/usr/bin/env python3
"""Force-turn off DuruOn LEDs if a previous run crashed or was killed.
Safely attempts GPIO cleanup only if RPi.GPIO available.
"""
import os, sys
try:
    import RPi.GPIO as GPIO  # type: ignore
except Exception:
    print("RPi.GPIO not available; nothing to reset.")
    sys.exit(0)

GREEN=int(os.environ.get('DURUON_GREEN_PIN',18))
BLUE=int(os.environ.get('DURUON_BLUE_PIN',23))
RED=int(os.environ.get('DURUON_RED_PIN',25))

GPIO.setmode(GPIO.BCM)
for pin in (GREEN,BLUE,RED):
    try:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
    except Exception as e:
        print(f"Pin {pin} reset error: {e}")

GPIO.cleanup()
print(f"LEDs off & GPIO cleaned (pins {GREEN},{BLUE},{RED}).")
