# DuruOn — Privacy-first bathroom emergency monitoring system

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4%2B-red.svg)](https://www.raspberrypi.org/)

**DuruOn** is an AI-powered bathroom emergency detection system that monitors for falls and immobility using computer vision and pose estimation. It provides real-time alerts via Telegram while maintaining complete privacy through on-device processing.

> ⚠️ **Privacy Notice**: Bathrooms are highly sensitive spaces. Deploy only with **explicit consent** and check local privacy laws and regulations.

## 🎯 Features

### Core Functionality
- **Real-time pose detection** using MoveNet SinglePose Lightning (TensorFlow Lite)
- **Fall detection** via sudden drop + horizontal posture analysis
- **Immobility monitoring** with adaptive thresholds based on body position
- **PIR sensor integration** for motion-activated monitoring
- **LED status indicators** for visual system feedback
- **Telegram alerts** with interactive acknowledgment buttons

### Privacy & Security
- **On-device inference** - no data leaves the device
- **No video storage** - frames processed in memory only
- **Anonymous skeleton images** - sent on black background without video feed
- **Secure notifications** - only text alerts and skeleton data transmitted

### Smart Detection
- **Shower-aware thresholds** - different sensitivity during shower hours  
- **Adaptive motion detection** - stricter monitoring for horizontal positions
- **Cooldown periods** - prevents alert spam
- **Multi-stage alerts** - soft warnings before emergency alerts

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
TG_CHAT_ID=your_chat_id_here
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

# Risk Detection Parameters
risk:
  angle_threshold_deg: 50.0
  hard_immobility_s: 60.0
  cooldown_s: 600

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
├── src/                    # Main application source
│   ├── main.py            # Application entry point
│   ├── activation/        # PIR sensor system
│   ├── indicators/        # LED status system
│   ├── notify/            # Telegram notifications
│   ├── pose_backends/     # AI pose detection
│   ├── risk/              # Emergency detection logic
│   └── utils/             # Utility functions
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