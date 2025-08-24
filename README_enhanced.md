# BathGuard — Privacy-first bathroom emergency monitor (RPi 5 + CV + Telegram)

**Goal**: Detect falls/immobility in a **bathroom** using on-device pose estimation, and send **Telegram** alerts (text + anonymized skeleton image). No video is stored or uploaded.

> ⚠️ Bathrooms are highly sensitive spaces. Deploy only with **explicit consent** and check local laws.

## Features
- On-device inference (MoveNet SinglePose Lightning, TFLite).
- Privacy: only **text** and optional **skeleton-on-black** image are sent.
- **Shower-aware detection**: Smart adaptive thresholds that distinguish between shower activities and emergencies.
- Robust heuristics: sudden drop + horizontal torso + immobility; or long immobility without a drop.
- Telegram alerts with inline **ack** buttons.
- `mock` backend for development (no camera/model needed).

## Enhanced Shower-Aware Detection

BathGuard now includes intelligent detection that adapts to normal shower activities while maintaining emergency detection capabilities:

### Adaptive Thresholds
- **Movement Tolerance**: More lenient when bent down (shampooing, washing) vs. upright positions
- **Time-Based Adjustment**: 4x longer alert thresholds during shower hours (6 AM - 10 PM by default)
- **Tiered Alerts**: Soft alerts (30s) followed by emergency alerts (60s) with shower-time multipliers

### Configuration
The enhanced detection is configured in `config.yaml`:

```yaml
risk:
  angle_threshold_deg: 50          # Trigger point for potential risk
  soft_immobility_s: 30.0          # Soft alert after 30 seconds
  hard_immobility_s: 60.0          # Emergency alert after 60 seconds
  
  # Shower-aware parameters
  movement_tolerance_low_angle: 0.12   # More lenient when bent (shower activities)
  movement_tolerance_high_angle: 0.05  # Stricter when upright
  shower_mode_enabled: true
  shower_start_hour: 6             # Shower hours start
  shower_end_hour: 22              # Shower hours end
  shower_duration_multiplier: 4.0  # 4x longer thresholds during shower hours
```

### How It Works
1. **Normal Hours**: Standard thresholds apply (30s soft, 60s emergency)
2. **Shower Hours** (6 AM - 10 PM): Extended thresholds (120s soft, 240s emergency)
3. **Posture-Adaptive**: Lower movement sensitivity when bending (washing activities)
4. **Multi-Stage Alerts**: Progressive warning system prevents false alarms

This system dramatically reduces false positives during normal shower activities while maintaining rapid emergency detection when needed.

## Quick start (Raspberry Pi OS 64-bit, Pi 5 recommended)
```bash
git clone <this repo> bathguard && cd bathguard
./install.sh
# Put your secrets in /opt/bathguard/.env (TG_BOT_TOKEN, TG_CHAT_ID)
# Edit config.yaml if needed.
/opt/bathguard/venv/bin/python -m src.main --config /opt/bathguard/config.yaml
```

### Telegram setup
Create a bot with **@BotFather** and obtain the **bot token**, then find your **chat_id** (start a chat and call `getUpdates` or use a helper). See the official **Telegram Bot API** documentation. (https://core.telegram.org/bots/api)

### MoveNet model
We use **MoveNet SinglePose Lightning (TFLite)**. If the automatic download script fails (TF Hub URLs sometimes change), open the **TensorFlow Hub MoveNet tutorial** and follow links to the **SinglePose Lightning** TFLite model, save it to `models/movenet_singlepose_lightning.tflite`.
- TF Hub MoveNet overview: https://www.tensorflow.org/hub/tutorials/movenet

## Config
`config.yaml` holds camera, risk thresholds, and backend selection. Use env vars for Telegram secrets.

## Systemd service
```bash
sudo cp service/bathguard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bathguard
journalctl -u bathguard -f
```

## Development without camera/model
```bash
# Use mock backend + dummy notifier
python -m src.main --config config.yaml
# Or run tests:
python -m pytest -q   # if pytest installed
# built-in unittest:
python -m tests.run_all
```

## Safety & Privacy
- Frames never persist to disk; skeleton images are rendered on black (no background).
- Keep the device in a sealed enclosure, angle camera toward floor to minimize exposure.
- Ensure strong physical security; restrict SSH; auto-update.

## License
MIT