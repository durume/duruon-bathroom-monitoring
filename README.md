<div align="center">

# DuruOn — Privacy‑First Bathroom Emergency Monitoring

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4%2B-red.svg)](https://www.raspberrypi.org/)
[![Status](https://img.shields.io/badge/status-active-success.svg)](#)

**AI fall & immobility detection designed for the most privacy‑sensitive room.** All inference happens locally; only concise Telegram alerts (text + optional anonymised skeleton on black) are sent.

**Language:** EN | [🇰🇷 한국어](README_ko.md)

</div>

> ⚠️ **PRIVACY & CONSENT**  
> Deploy only with explicit, informed consent of every person who may appear. Check your local regulations (privacy, CCTV / video processing, medical device rules). This project is **assistive**, not a medical device.

---
## 1. What Is DuruOn?

DuruOn is a lightweight Python application for a Raspberry Pi (or any Linux SBC) that:
- Detects rapid **falls** (sudden drop + low posture + short immobility)
- Detects prolonged **immobility** (soft → hard escalation)
- Sends **Telegram alerts** with inline acknowledgment buttons ("I'm OK", "False", "Stop")
- Minimises false positives during **shower / normal grooming** via time & posture adaptive thresholds
- Preserves privacy (no raw frames stored, no cloud inference)

---
## 2. High‑Level Architecture

```
          +-----------------------------+
          |        Camera (Pi / USB)    |
          +---------------+-------------+
                          v frames
                 +--------+---------+
                 |  Pose Backend    |  (MoveNet TFLite OR mock)
                 +--------+---------+
                          v pose (keypoints)
                 +--------+---------+
                 |  Risk Engine     |  (drop + angle + immobility logic,
                 |  adaptive/shower |   fast fall path, cooldown)
                 +----+------+------+
                      | events
        +-------------+-------------+
        |                           |
        v                           v
  Telegram Notifier         LED Indicators (status)
        |                           ^
        v alerts                   PIR activation (wake/sleep)
   Caregiver / User <---- heartbeat & repeats ----+
```

Core modules live under `src/`:
- `pose_backends/` – TFLite MoveNet SinglePose Lightning or `mock` generator
- `risk/engine.py` – stateful detection pipeline
- `notify/telegram.py` – message + callback handling
- `activation/pir_activation.py` – motion gating (optional)
- `indicators/led_status.py` – tri‑LED hardware feedback
- `utils/skeleton_draw.py` – anonymised skeleton JPEG rendering

---
## 3. Feature Summary

| Category | Features |
|----------|----------|
| Detection | Fast fall pathway (`fast_fall_immobility_s`), tiered immobility (soft → hard), posture & shower aware adaptive thresholds |
| Privacy | On‑device inference, no frame storage, skeletal abstraction only |
| Alerts | Telegram inline buttons (OK / False / Stop), repeat reminders, cooldown, daily heartbeat |
| Hardware | PIR motion gating, RGB (3 mono) LED status set (Green system, Blue active, Red alert) |
| Reliability | Camera freeze watchdog (internal), graceful shutdown, configurable cooldown |
| Dev/Test | Mock backend sequence, examples configs in `examples/`, unit tests, dummy notifier |

---
## 4. Quick Start (Beginner Friendly)

```bash
# 1. Clone
git clone https://github.com/your-username/duruon.git
cd duruon

# 2. Install (creates /opt/bathguard, virtualenv, downloads model)
./install.sh

# 3. Set Telegram secrets
sudo nano /opt/bathguard/.env   # Add TG_BOT_TOKEN & TG_CHAT_ID

# 4. (Optional) Test without hardware
cd /opt/bathguard
venv/bin/python -m src.main --config config.yaml --backend mock

# 5. Run with camera
venv/bin/python -m src.main --config config.yaml

# Alternative simpler entry (adds import fallback)
venv/bin/python main_runner.py --config config.yaml
```

> If you do not yet have a bot: use @BotFather → create bot → copy token → send a message to the bot → open `https://api.telegram.org/bot<TOKEN>/getUpdates` → extract `chat.id`.

---
## 4.1 How to Run (Step‑by‑Step)
Essential execution workflow (manual run, then service operation):

1. Install (copies into `/opt/bathguard`, creates venv, downloads model)
```bash
git clone https://github.com/your-username/duruon.git
cd duruon
./install.sh
```
2. Add Telegram credentials
```bash
sudo nano /opt/bathguard/.env
```
Example:
```bash
TG_BOT_TOKEN=123456:ABC...
TG_CHAT_ID=999999999
```
3. (Optional) Edit config
```bash
sudo nano /opt/bathguard/config.yaml
```
4. (Optional) Dry run without hardware
```bash
cd /opt/bathguard
venv/bin/python -m src.main --config config.yaml --backend mock --camera.enabled false
```
5. Foreground live run (interactive tuning)
```bash
cd /opt/bathguard
venv/bin/python -m src.main --config config.yaml
```
6. Install as systemd service (auto start)
```bash
sudo cp service/bathguard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bathguard
```
7. Monitor & logs
```bash
cd /opt/bathguard
./monitor.sh health
./monitor.sh live
journalctl -u bathguard -n 50 --no-pager
```
8. Apply config changes
```bash
sudo systemctl restart bathguard
```
9. Stop / disable
```bash
sudo systemctl stop bathguard
sudo systemctl disable bathguard
```
10. Run unit tests
```bash
cd /opt/bathguard
venv/bin/python -m tests.run_all
```

Decision helper:
- Need quick experimentation? → Step 5 foreground.
- Want resilience & auto boot? → Steps 6–8 systemd.
- No hardware yet? → Step 4 mock.

If the service fails, inspect:
```bash
systemctl status bathguard --no-pager -l
journalctl -u bathguard -b --no-pager | tail -n 80
```

---
## 5. Configuration Overview

Main file: `config.yaml`. Example fragments below (see comments):

```yaml
backend:
  type: movenet_tflite          # movenet_tflite | mock
  model_path: models/movenet_singlepose_lightning.tflite
  num_threads: 3                # Reduce if CPU constrained

camera:
  enabled: true
  index: 0
  width: 640
  height: 480
  fps: 15                       # Higher FPS -> faster detection, more CPU

risk:
  angle_threshold_deg: 55       # Lower angle (closer to horizontal) triggers risk consideration
  drop_threshold: 0.10          # Normalised vertical displacement for sudden drop
  drop_window_s: 0.9            # Time window for drop calc
  immobile_window_s: 10.0       # Rolling motion average window
  soft_immobility_s: 30.0       # Soft alert after this (if no fast fall path triggered)
  hard_immobility_s: 90.0       # Escalated alert after this
  fast_fall_immobility_s: 12.0  # Fast confirmation time when drop+low angle
  cooldown_s: 120               # Suppress repeat alerts
  movement_tolerance_low_angle: 0.50  # Allowed motion if lying/bent
  movement_tolerance_high_angle: 0.05 # Allowed motion upright
  shower_mode_enabled: true
  shower_start_hour: 6
  shower_end_hour: 22
  shower_duration_multiplier: 4.0  # Multiplies soft/hard times in shower hours

pir_activation:
  enabled: true
  pir_pin: 24
  auto_sleep_timeout: 300.0     # (Optional) Return to idle after inactivity

led_indicators:
  enabled: true
  green_pin: 18
  blue_pin: 23
  red_pin: 25

alerting:
  repeat_unacked_after_s: 300   # Reminder interval
  max_repeats: 3                # Limit reminders
  heartbeat_hour: 9             # Daily heartbeat (set -1 to disable)

telegram:
  type: telegram                # telegram | dummy
```

Environment (`.env`):
```bash
TG_BOT_TOKEN=123456:ABC...
TG_CHAT_ID=999999999
```

### Parameter Cheat Sheet
| Name | Purpose | Tune Up (>) | Tune Down (<) |
|------|---------|-------------|---------------|
| angle_threshold_deg | Angle below which posture considered low | Detect slower slides | Reduce false alarms while bending |
| drop_threshold | Min vertical delta for fall | More sensitivity | Fewer false drops |
| fast_fall_immobility_s | Window to confirm fast fall | Faster alerts | Safer against brief pauses |
| soft_immobility_s | Soft stage delay | Later soft alerts | Earlier soft alerts |
| hard_immobility_s | Hard escalation delay | Later escalation | Earlier escalation |
| cooldown_s | Alert spam reduction | Fewer duplicates | Get repeat alerts sooner |
| movement_tolerance_low_angle | Lying allowed motion | More lenient | Stricter |
| movement_tolerance_high_angle | Upright allowed motion | Fewer false immobility | Reduce misses |
| shower_duration_multiplier | Extends thresholds during shower hours | Fewer shower false alerts | Faster detection while showering |

---
## 6. How Detection Works (Beginner Explanation)

1. Every frame → MoveNet outputs 17 keypoints (x, y, confidence).  
2. Risk engine computes torso angle & vertical velocity (hip/shoulder averages).  
3. A **fall candidate** triggers if: sudden vertical drop + angle below threshold OR combined posture/position change.  
4. If candidate → start short immobility timer (`fast_fall_immobility_s`). If still immobile and posture low → immediate alert.  
5. Otherwise track general immobility: motion average < tolerance (adaptive by angle & shower time).  
6. Soft alert (caregivers can pre‑empt) → escalate to hard if still unacknowledged or ongoing.  
7. Repeat reminders until acknowledged or max reached. Heartbeat confirms system liveness daily.

---
## 7. Telegram Buttons

| Label (KR) | English | Action |
|------------|---------|--------|
| 괜찮아요 | I'm OK | Acknowledge + clear alert |
| 오탐 | False Alarm | Mark false → adaptive tuning input (future) |
| 중지 | Stop | Graceful remote shutdown |

To switch to English labels, edit button tuples in `src/main.py` (search for `buttons=[(`).

---
## 8. Running Modes

| Mode | Command | Purpose |
|------|---------|---------|
| Production | `venv/bin/python -m src.main --config config.yaml` | Full hardware run |
| Runner Wrapper | `venv/bin/python main_runner.py --config config.yaml` | Import‑safe entry |
| Mock fast test | `venv/bin/python -m src.main --config examples/config_mock.yaml` | Dev without camera |
| Unit tests | `python -m tests.run_all` | Validate logic |

---
## 9. Service Installation (systemd)
```bash
sudo cp service/bathguard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bathguard
journalctl -u bathguard -f
```

Restart after config change: `sudo systemctl restart bathguard`.

---
## 10. Monitoring & Logs
```bash
./monitor.sh health     # Basic health summary
./monitor.sh live       # Tail recent application log output
./monitor.sh perf       # (If implemented) Performance snapshot
```
Alerts written to `alerts.log` (rotated by size in code logic if enabled).

---
## 11. Updating / Maintenance
```bash
git pull
sudo systemctl restart bathguard
```
To upgrade Python deps: `source /opt/bathguard/venv/bin/activate && pip install -U -r requirements.txt`.

Model update: replace `models/movenet_singlepose_lightning.tflite` (same filename) then restart.

---
## 12. Troubleshooting

| Issue | Check | Fix |
|-------|-------|-----|
| Camera not opening | `ls /dev/video*`, `vcgencmd get_camera` | Cable seating / enable in raspi-config |
| Telegram no messages | Token / chat id, network | Recreate bot / verify `.env` permissions |
| Frequent false alerts | Increase `angle_threshold_deg`, raise `drop_threshold`, extend `soft_immobility_s` | — |
| Missed slow falls | Lower `angle_threshold_deg`, reduce `drop_threshold`, decrease `fast_fall_immobility_s` | — |
| High CPU | Lower `fps`, reduce `num_threads` | Heatsink / active cooling |
| PIR never triggers | GPIO wiring & correct pin, 5V vs 3.3V logic | Adjust sensitivity knobs on module |

---
## 13. Security & Privacy Checklist
| Item | Why |
|------|-----|
| Restrict physical access | Prevent tampering / lens re‑aim |
| Use SSH keys only | Avoid password brute force |
| Keep system updated | Patch CVEs |
| Minimal network exposure | No unnecessary ports open |
| Principle of least privilege | Limit service user rights |

---
## 14. Contributing
1. Fork & branch (`feat/<topic>`).  
2. Add/update tests.  
3. Keep README sections bilingual parity (EN + KO).  
4. Submit PR with clear description & screenshots (if UI).  

Run tests: `python -m tests.run_all`.

---
## 15. Roadmap Ideas
- Configurable multi‑language i18n map
- Automatic threshold tuning using confirmed false / true events
- Web dashboard (local only)
- Optional on‑device audio prompt (“Are you OK?”)

---
## 16. Acknowledgments
TensorFlow (MoveNet), OpenCV, Raspberry Pi Foundation, Telegram Bot API, and open‑source contributors.

---
## 17. License & Disclaimer
MIT License (see `LICENSE`).  
This project **does not replace** professional medical monitoring; it is an **assistive early warning tool**.

## 🎯 Features

### Core Functionality
- **Real-time pose detection** using MoveNet SinglePose Lightning (TensorFlow Lite)
- **Fall detection (fast + tiered)**: sudden drop + short immobility fast-path, plus longer immobility escalation
- **Immobility monitoring** with adaptive thresholds (posture & shower-aware)
- **PIR sensor integration** for motion-activated monitoring
- **LED status indicators** for visual system feedback
- **Telegram alerts** with interactive acknowledgment buttons (localized KR/EN)

### Privacy & Security
- **On-device inference** - no data leaves the device
- **No video storage** - frames processed in memory only
- **Anonymous skeleton images** - sent on black background without video feed
- **Secure notifications** - only text alerts and skeleton data transmitted

### Smart Detection
- **Fast fall pathway** - sudden drop + low angle + short immobility (configurable `fast_fall_immobility_s`)
- **Tiered escalation** - soft immobility → hard immobility fallback
- **Shower-aware thresholds** - extended durations & leniency during configured hours  
- **Adaptive motion detection** - posture-based movement tolerance
- **Cooldown periods** - prevents alert spam
- **Repeat reminders & STOP button** - configurable follow‑ups until acknowledged
- **Heartbeat messages** - optional daily alive notification

## 🛠 Hardware Requirements

### Core Components
- **Raspberry Pi 4/5** (4GB+ RAM recommended)
- **Camera module** - Pi Camera v2/v3 or compatible USB camera
- **PIR motion sensor** - HC-SR501 or similar
- **Status LEDs** - 3x standard LEDs (Green, Blue, Red)
- **MicroSD card** - 32GB+ Class 10

### Wiring Diagram

```
Raspberry Pi GPIO Layout:
                3V3  (1) (2)  5V    
               GPIO2 (3) (4)  5V    
               GPIO3 (5) (6)  GND   
               GPIO4 (7) (8)  GPIO14
                 GND (9) (10) GPIO15
              GPIO17 (11) (12) GPIO18 ← Green LED (+)
              GPIO27 (13) (14) GND   ← LED Ground
              GPIO22 (15) (16) GPIO23 ← Blue LED (+)
                3V3 (17) (18) GPIO24 ← PIR Signal
              GPIO10 (19) (20) GND   
               GPIO9 (21) (22) GPIO25 ← Red LED (+)
              GPIO11 (23) (24) GPIO8 
                 GND (25) (26) GPIO7 
```

### Component Connections
```
PIR Sensor (HC-SR501):
├── VCC → Pi 5V (Pin 2)
├── GND → Pi GND (Pin 6)
└── OUT → GPIO24 (Pin 18)

LED Status Indicators:
├── Green LED → GPIO18 (Pin 12) + 330Ω resistor → GND
├── Blue LED  → GPIO23 (Pin 16) + 330Ω resistor → GND  
└── Red LED   → GPIO25 (Pin 22) + 330Ω resistor → GND

Camera:
└── Pi Camera connector or USB port
```

## 🚀 Installation

### Quick Start
```bash
# Clone the repository
git clone https://github.com/your-username/duruon.git
cd duruon

# Run installation script
./install.sh

# Configure Telegram credentials
sudo nano /opt/bathguard/.env

# Start the system
/opt/bathguard/venv/bin/python -m src.main --config /opt/bathguard/config.yaml
```

## ⚙️ Configuration

### Environment Variables (`/opt/bathguard/.env`)
```bash
# Telegram Bot Configuration
TG_BOT_TOKEN=your_bot_token_here
TG_CHAT_ID=your_chat_id_here  # Chat ID of the chat receiver
```

### Main Configuration (`config.yaml`)
```yaml
# AI Backend Configuration
backend:
  type: "movenet_tflite"
  model_path: "models/movenet_singlepose_lightning.tflite"
  num_threads: 3

# Camera Settings
camera:
  enabled: true
  index: 0
  width: 640
  height: 480
  fps: 15

# Risk Detection Parameters (excerpt)
risk:
  angle_threshold_deg: 55           # Horizontal / low‑posture risk threshold
  drop_threshold: 0.10              # Normalized vertical drop (hip/shoulder avg)
  drop_window_s: 0.9                # Time window to evaluate sudden drop
  immobile_window_s: 10.0           # Averaging window for motion
  soft_immobility_s: 30.0           # Soft alert delay (no fall detected)
  hard_immobility_s: 90.0           # Long fallback escalation
  fast_fall_immobility_s: 12.0      # Fast path confirmation after detected drop
  cooldown_s: 120                   # Seconds to suppress duplicate alerts
  movement_tolerance_low_angle: 0.50  # Motion tolerance when near-horizontal
  movement_tolerance_high_angle: 0.05 # Upright stricter tolerance
  shower_mode_enabled: true
  shower_start_hour: 6
  shower_end_hour: 22
  shower_duration_multiplier: 4.0   # Multiplies immobility thresholds during shower hours

# Hardware Configuration  
pir_activation:
  enabled: true
  pir_pin: 24

led_indicators:
  enabled: true
  green_pin: 18
  blue_pin: 23
  red_pin: 25
```

### Telegram Button Meanings
Buttons appear with each alert and reminders (localized in Korean by default):

| Korean Label | English Meaning        | Action / Purpose                                 |
|--------------|------------------------|--------------------------------------------------|
| 괜찮아요       | I'm OK / Safe           | Acknowledge; dismisses alert, counts as resolved |
| 오탐          | False Alarm             | Marks alert as false positive (adaptive tuning)  |
| 중지          | Stop (optional)         | Stops the application process remotely           |

To switch labels back to English, edit button texts in `src/main.py` (search for `buttons=[("괜찮아요"`). Future improvement: externalize i18n map.

## 🔧 Development

### Setting up Development Environment
```bash
git clone https://github.com/your-username/duruon.git
cd duruon
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
python -m pytest tests/

# Run in mock mode (no hardware required)
python -m src.main --config config_mock.yaml
```

### Project Structure
```
duruon/
├── src/                      # Main application source
│   ├── main.py              # Application entry point (alerts, repeat, heartbeat, i18n KR)
│   ├── activation/          # PIR sensor system
│   ├── indicators/          # LED status system
│   ├── notify/              # Telegram notifications & callback handling
│   ├── pose_backends/       # AI pose detection (TFLite / mock)
│   ├── risk/                # RiskEngine (fast fall + tiered immobility logic)
│   └── utils/               # Utility functions (skeleton rendering, etc.)
├── tests/                 # Test suite
├── models/                # AI models
├── service/               # System service files
└── config.yaml           # Configuration
```

## 🤝 Contributing

We welcome contributions! Please:

1. **Fork** the repository
2. **Create** a feature branch
3. **Add tests** for new functionality
4. **Follow** code style guidelines
5. **Submit** a Pull Request

### Development Guidelines
- **Security first**: Never log sensitive data
- **Privacy by design**: Minimize data collection
- **Hardware compatibility**: Test on real Raspberry Pi
- **Error handling**: Graceful degradation

## 📊 Monitoring

### System Health Check
```bash
# Check system status
/opt/bathguard/monitor.sh health

# View live logs  
/opt/bathguard/monitor.sh live

# Test hardware
sudo python3 /tmp/wiring_test.py
```

### Service Management
```bash
# Install as system service
sudo cp service/bathguard.service /etc/systemd/system/
sudo systemctl enable --now bathguard

# Monitor service
journalctl -u bathguard -f
```

## 🔒 Security & Privacy

### Privacy Protection
- **On-device processing** - no cloud dependencies
- **Minimal data transmission** - only anonymous skeleton data
- **No video storage** - frames processed in memory only
- **Secure communications** - encrypted Telegram Bot API

### Deployment Security
- **Physical security** - secure device mounting
- **Network security** - firewall and SSH keys
- **Regular updates** - security patches
- **Access control** - principle of least privilege

## 🚨 Troubleshooting

### Common Issues

**Camera not detected:**
```bash
ls /dev/video*
python3 -c "import cv2; print(cv2.VideoCapture(0).isOpened())"
```

**GPIO permissions:**
```bash
sudo usermod -a -G gpio $USER
```

**Model loading:**
```bash
cd models && ./download_models.sh
```

## 📜 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **TensorFlow** team for MoveNet pose estimation
- **Raspberry Pi Foundation** for the hardware platform
- **Telegram** for the Bot API
- **OpenCV** community for computer vision tools

---

**⚠️ Disclaimer**: This system assists with emergency detection but should not replace professional medical monitoring or emergency services.