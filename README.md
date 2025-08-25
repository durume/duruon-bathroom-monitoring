# DuruOn — Privacy-first bathroom emergency monitoring system

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4%2B-red.svg)](https://www.raspberrypi.org/)

**DuruOn** is an AI-powered bathroom emergency detection system that monitors for falls and immobility using computer vision and pose estimation. It provides real-time alerts via Telegram while maintaining complete privacy through on-device processing.

[🇰🇷 한국어 문서](README_ko.md)

> ⚠️ **Privacy Notice**: Bathrooms are highly sensitive spaces. Deploy only with **explicit consent** and check local privacy laws and regulations.

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