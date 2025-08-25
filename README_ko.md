# DuruOn — 프라이버시 우선 화장실 응급 모니터링 시스템

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4%2B-red.svg)](https://www.raspberrypi.org/)

**DuruOn** 은 컴퓨터 비전과 포즈 추정을 활용하여 화장실에서의 **낙상** 및 **장시간 무동작(의식 저하 가능)** 상황을 감지하고, 텔레그램을 통해 실시간 알림(텍스트 + 익명화된 골격 이미지)을 전송하는 온디바이스 AI 시스템입니다. 모든 추론은 로컬에서 수행되며 영상은 저장·전송되지 않습니다.

> ⚠️ **프라이버시 주의**: 화장실은 매우 민감한 장소입니다. 반드시 **명시적 동의**를 얻고 관련 법규(개인정보, 영상처리 등)를 준수하십시오.

---
## 🎯 주요 기능
### 핵심 감지
- **실시간 포즈 추정**: MoveNet SinglePose Lightning (TensorFlow Lite)
- **낙상 감지**: 급작스러운 하강 + 수평(또는 낮은) 자세 + 무동작
- **무동작(immobility) 모니터링**: 자세/시간 기반 적응형 임계값
- **PIR 센서 연동**: 사람이 있을 때만 활성 감시
- **LED 상태 표시**: 시스템 / PIR / 경보 상태 시각화
- **텔레그램 알림**: 확인(I'm OK) / 오탐(False) 버튼 포함

### 프라이버시 & 보안
- 온디바이스 추론 (클라우드 전송 없음)
- 비디오 프레임 저장하지 않음 (RAM 내 처리 후 폐기)
- 배경 없는 **스켈레톤(흑색 캔버스)** 이미지만 전송
- 최소한의 메타데이터 전송

### 지능형 적응
- **샤워 인식 모드**: 샤워 시간 동안 임계값 자동 증가 (오탐 감소)
- **자세 기반 움직임 민감도 조정**: 수평/굽힌 자세 vs 직립 구분
- **단계적 알림**: Soft → Hard (중복 스팸 방지 Cooldown)
- **Mock 백엔드**: 하드웨어 없이 개발/테스트 가능

---
## 🛠 요구 하드웨어
| 구성 | 설명 |
|------|------|
| Raspberry Pi 4/5 | 4GB RAM 이상 권장 |
| 카메라 모듈 | Pi Camera v2/v3 또는 USB UVC 카메라 |
| PIR 센서 | HC-SR501 등 (GPIO 24 기본) |
| LED 3개 | 녹(시스템), 청(PIR), 적(알림) |
| 저항 | 각 LED 220~330Ω 직렬 |

### GPIO 기본 매핑 (config 수정 가능)
- Green LED: GPIO18
- Blue LED: GPIO23
- Red LED: GPIO25
- PIR OUT: GPIO24

---
## 📦 설치 (Raspberry Pi OS 64bit)
```bash
# 저장소 가져오기
git clone https://github.com/your-username/duruon.git
cd duruon

# 설치 스크립트 실행 (시스템 의존성 + venv + 모델)
./install.sh

# 텔레그램 환경 변수 설정
sudo nano /opt/bathguard/.env   # TG_BOT_TOKEN, TG_CHAT_ID 입력

# 실행
/opt/bathguard/venv/bin/python -m src.main --config /opt/bathguard/config.yaml
```

### 텔레그램 봇 준비
1. @BotFather 로 새 봇 생성 → 토큰 확보
2. 봇에게 임의 메시지 보내기
3. `https://api.telegram.org/bot<토큰>/getUpdates` 호출하여 `chat.id` 확인
4. `.env` 또는 config에 설정

`.env` 예시:
```bash
TG_BOT_TOKEN=123456:ABC_DEF...
TG_CHAT_ID=987654321 # 수신자 Chat ID
```

---
## ⚙️ 설정 (`config.yaml` 주요 항목)
```yaml
backend:
  type: movenet_tflite         # 또는 mock
  model_path: models/movenet_singlepose_lightning.tflite
  num_threads: 3

camera:
  enabled: true
  index: 0
  width: 640
  height: 480
  fps: 15

risk:
  angle_threshold_deg: 50.0
  drop_threshold: 0.08
  drop_window_s: 1.0
  immobile_window_s: 10.0
  soft_immobility_s: 45.0
  hard_immobility_s: 60.0
  cooldown_s: 600
  movement_tolerance_low_angle: 0.12
  movement_tolerance_high_angle: 0.05
  shower_mode_enabled: true
  shower_start_hour: 6
  shower_end_hour: 22
  shower_duration_multiplier: 4.0

pir_activation:
  enabled: true
  pir_pin: 24
  auto_sleep_timeout: 300.0

led_indicators:
  enabled: true
  green_pin: 18
  blue_pin: 23
  red_pin: 25

telegram:
  type: telegram   # dummy 로 설정하면 테스트용 (알림 출력만)
```

### Mock 모드 빠른 테스트
```bash
cp config.yaml config_mock.yaml
sed -i 's/type: "movenet_tflite"/type: "mock"/' config_mock.yaml
sed -i 's/enabled: true/enabled: false/' config_mock.yaml  # 카메라 비활성화
python -m src.main --config config_mock.yaml
```

---
## 🧪 테스트 / 개발
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # (추가 필요 시 생성)
python -m tests.run_all          # 내장 unittest 실행
```

### 프로젝트 구조
```
src/
  main.py            # 진입점
  activation/        # PIR 제어
  indicators/        # LED 제어
  notify/            # 텔레그램
  pose_backends/     # MoveNet / Mock
  risk/              # 리스크 엔진
  utils/             # 유틸
models/              # TFLite 모델
service/             # systemd 서비스 파일
tests/               # 테스트
```

---
## 🔄 Systemd 서비스 등록
```bash
sudo cp service/bathguard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bathguard
journalctl -u bathguard -f
```

`monitor.sh` 사용:
```bash
./monitor.sh health
./monitor.sh live
./monitor.sh perf
```

---
## 🛡 프라이버시 & 보안 수칙
- 카메라 시야 최소화 (바닥/신체 중심부 제한)
- 네트워크: SSH 키 사용, 불필요 포트 차단
- 주기적 패키지 업데이트 적용
- 토큰/비밀 `.env` 권한 제한 (chmod 600)
- 로그에 민감 정보 미기록

---
## 🚨 문제 해결 (Troubleshooting)
| 문제 | 확인 방법 | 해결 |
|------|-----------|------|
| 카메라 불가 | `ls /dev/video*` | 재부팅 / 케이블 확인 |
| 모델 로드 실패 | 파일 존재 여부 | `models/download_models.sh` 재실행 |
| 텔레그램 미전송 | 네트워크, 토큰 | 새 토큰 발급 / 방화벽 확인 |
| PIR 비동작 | GPIO 권한 | `sudo usermod -a -G gpio $USER` 후 재로그인 |

---
## 📜 라이선스
본 프로젝트는 MIT 라이선스를 따릅니다. `LICENSE` 파일 참고.

---
**면책조항**: 본 시스템은 보조 도구이며, 전문 의료 모니터링을 대체하지 않습니다.
