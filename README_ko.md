<div align="center">

# DuruOn — 프라이버시 우선 화장실 응급 모니터링

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4%2B-red.svg)](https://www.raspberrypi.org/)
[![Status](https://img.shields.io/badge/status-active-success.svg)](#)

**낙상 / 장시간 무동작을 즉시 감지**하고 텔레그램으로 알림을 전송하는 초경량 온디바이스 AI 시스템입니다. 비디오는 저장·전송하지 않고 필요 최소 정보(텍스트 + 선택적 골격 이미지)만 전송합니다.

**언어:** 한국어 | [ENGLISH](README.md)

</div>

> ⚠️ **프라이버시 & 동의**  
> 모든 사용자(노출 가능자)의 **명시적 사전 동의**가 필요합니다. 개인정보/영상처리/의료기기 관련 지역 법규를 확인하세요. 본 프로젝트는 **보조 도구**이며 의료기기를 대체하지 않습니다.

---
## 1. 개요

DuruOn은 Raspberry Pi 등 소형 리눅스 보드에서 실행되며:
- 급격 낙상 (드롭 + 낮은 자세 + 짧은 무동작) 신속 감지
- 장기 무동작 Soft → Hard 단계적 에스컬레이션
- 샤워/세안 활동 중 오탐 감소 (시간 & 자세 기반 적응)
- 텔레그램 알림 + 인라인 버튼 (괜찮아요 / 오탐지 / 앱중지)
- 로컬 추론으로 프라이버시 보존

---
## 2. 아키텍처 개요
```
          +------------------+
          |   카메라 (Pi/USB) |
          +---------+--------+
                    v 프레임
             +------+------+
             |  포즈 백엔드 |  (MoveNet 또는 mock)
             +------+------+
                    v 포즈 키포인트
             +------+------+
             |  리스크 엔진 | (낙하 + 각도 + 무동작,
             |  적응/샤워   |  빠른 낙상 경로)
             +--+-------+--+
                | 이벤트
      +---------+---------+
      |                   |
      v                   v
  텔레그램 알림      LED 인디케이터
      |                   ^
      v                   |
 수신자(보호자)  ←  PIR 활성/휴면
```

모듈 구조 (`src/`): `pose_backends/`, `risk/`, `notify/`, `activation/`, `indicators/`, `utils/`.

---
## 3. 주요 기능 요약
| 범주 | 기능 |
|------|------|
| 감지 | 빠른 낙상 경로, Soft/Hard 무동작, 샤워 인식, 자세 기반 적응 |
| 프라이버시 | 온디바이스 추론, 프레임 비저장, 익명 스켈레톤 이미지 |
| 알림 | 텔레그램 인라인 버튼(괜찮아요 / 오탐지 / 앱중지), 반복 재알림, Heartbeat, Cooldown |
| 하드웨어 | PIR 모션 게이팅, 3색(3 LED) 상태 표시 |
| 신뢰성 | 카메라 프리즈 감시, 그레이스풀 종료 |
| 개발/테스트 | Mock 백엔드, 예제 설정(`examples/`), 단위 테스트, 더미 노티파이어 |

---
### 텔레그램 인라인 버튼 상세

| 버튼 | 의미 | 동작 |
|------|------|------|
| 괜찮아요 | I'm OK / 안전 | 알림 종료 및 재알림 중단 |
| 오탐지 | False Alarm | 오탐 기록 (향후 자동 튜닝 활용 예정) |
| 앱중지 | 앱 종료 | 원격 즉시 프로세스 종료 |

라벨 변경: `src/main.py` 에서 `buttons=[("괜찮아요"` 부분 수정.

---
## 4. 빠른 시작 (입문용)
```bash
git clone https://github.com/durume/duruon-bathroom-monitoring.git
cd duruon-bathroom-monitoring
./install.sh                     # /opt/bathguard 구성
sudo nano /opt/bathguard/.env    # TG_BOT_TOKEN / TG_CHAT_ID 입력

# Mock (카메라/센서 없이 논리 확인)
cd /opt/bathguard
venv/bin/python -m src.main --config config.yaml --backend mock

# 실제 실행
venv/bin/python -m src.main --config config.yaml

# 대안 (임포트 문제 회피용 래퍼)
venv/bin/python main_runner.py --config config.yaml
```
Bot 생성: @BotFather → 토큰 → 봇에게 메시지 → `https://api.telegram.org/bot<TOKEN>/getUpdates` → `chat.id` 추출.

---
## 4.1 실행 절차 (Step-by-Step)
운영/테스트에 가장 자주 필요한 명령을 순서대로 정리했습니다.

1. 설치 (코드 복사 + 가상환경 + 모델)
```bash
git clone https://github.com/durume/duruon-bathroom-monitoring.git
cd duruon-bathroom-monitoring
./install.sh
```
2. 텔레그램 자격정보 작성 (`.env`)
```bash
sudo nano /opt/bathguard/.env
```
예시:
```bash
TG_BOT_TOKEN=123456:ABC...
TG_CHAT_ID=999999999
```
3. (선택) 설정 수정
```bash
sudo nano /opt/bathguard/config.yaml
```
4. (선택) 하드웨어 없이 Mock 테스트
```bash
cd /opt/bathguard
venv/bin/python -m src.main --config config.yaml --backend mock --camera.enabled false
```
5. 포그라운드 실행 (튜닝/로그 직관)
```bash
cd /opt/bathguard
venv/bin/python -m src.main --config config.yaml
```
6. systemd 서비스 등록 (부팅 자동 시작)
```bash
sudo cp service/bathguard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bathguard
```
7. 모니터링 / 로그 확인
```bash
cd /opt/bathguard
./monitor.sh health
./monitor.sh live
journalctl -u bathguard -n 50 --no-pager
```
8. 설정 변경 후 재시작
```bash
sudo systemctl restart bathguard
```
9. 중지 / 비활성화
```bash
sudo systemctl stop bathguard
sudo systemctl disable bathguard
```
10. 단위 테스트 실행
```bash
cd /opt/bathguard
venv/bin/python -m tests.run_all
```

선택 안내:
- 실시간 튜닝 필요 → 5번 포그라운드
- 상시 운영 → 6~8번 systemd
- 하드웨어 미보유 → 4번 Mock

서비스 문제 분석:
```bash
systemctl status bathguard --no-pager -l
journalctl -u bathguard -b --no-pager | tail -n 80
```

---
## 5. 설정 개요 (`config.yaml`)
```yaml
backend:
  type: movenet_tflite
  model_path: models/movenet_singlepose_lightning.tflite
  num_threads: 3
camera:
  enabled: true
  index: 0
  width: 640
  height: 480
  fps: 15
risk:
  angle_threshold_deg: 55
  drop_threshold: 0.10
  drop_window_s: 0.9
  immobile_window_s: 10.0
  soft_immobility_s: 30.0
  hard_immobility_s: 90.0
  fast_fall_immobility_s: 12.0
  cooldown_s: 120
  movement_tolerance_low_angle: 0.50
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
alerting:
  repeat_unacked_after_s: 300
  max_repeats: 3
  heartbeat_hour: 9
telegram:
  type: telegram
```
`.env` 예시:
```bash
TG_BOT_TOKEN=123456:ABC...
TG_CHAT_ID=999999999
```

### 파라미터 요약표
| 이름 | 의미 | 값 ↑ (효과) | 값 ↓ (효과) |
|------|------|-------------|-------------|
| angle_threshold_deg | 낮은 자세 판단 기준 각도 | 더 느린 슬라이드 탐지 | 구부릴 때 오탐 감소 |
| drop_threshold | 낙상 감지용 수직 변화 기준 | 민감도 ↑ | 걷기 오탐 ↓ |
| **drop_window_s** | **급락 감지 시간 창** | **긴 히스토리 분석** | **빠른 반응, 적은 맥락** |
| angle_change_threshold | 급락 유발 최소 각도 변화 | 자세 변화 민감 ↑ | 일상 움직임 무시 |
| position_change_threshold | 급락 유발 최소 위치 변화 | 위치 이동 민감 ↑ | 걷기/일상 동작 무시 |
| fast_fall_immobility_s | 빠른 낙상 무동작 확인 창 | 더 빠른 경보 | 짧은 정지 오탐 감소 |
| soft_immobility_s | Soft 알림 지연 | 느린 알림 | 빠른 알림 |
| hard_immobility_s | Hard 에스컬레이션 | 느린 에스컬레이션 | 빠른 에스컬레이션 |
| cooldown_s | 중복 억제 | 중복 ↓ | 반복 ↑ |
| movement_tolerance_low_angle | 누운/구부린 상태 허용 움직임 | 오탐 ↓ | 민감 ↑ |
| movement_tolerance_high_angle | 직립 허용 움직임 | 오탐 ↓ | 민감 ↑ |
| shower_duration_multiplier | 샤워 시간 지연 배수 | 샤워 오탐 ↓ | 샤워 중 빠른 감지 |

### 급락 감지 창 (Drop Detection Window) 설명

**`drop_window_s`**는 급락 감지의 핵심입니다. 시스템이 급작스러운 변화를 감지하기 위해 얼마나 과거를 되돌아볼지 정의합니다:

- **목적**: 현재 자세를 이 시간 창 내 과거 자세들과 비교
- **너무 작음** (< 2.0초): 충분한 자세 샘플을 수집하지 못해 감지 실패 가능
- **너무 큼** (> 5.0초): 과도한 과거 맥락으로 급작스러운 변화가 희석됨
- **권장값**: 대부분 시나리오에서 2.0-4.0초

이 창 내에서 시스템은 **최소 2개의 자세 샘플**이 있어야 급락 감지를 수행합니다. 15 FPS에서 3.0초 창은 ~45프레임을 캡처해야 하지만, 필터링(자세 신뢰도, 키포인트 가용성)으로 개수가 줄어들 수 있습니다.

**감지 로직**:
1. **수직 급락**: 엉덩이 위치가 ≥ `drop_threshold`만큼 하강 (정규화된 화면 좌표)
2. **각도 변화**: 몸통 각도가 ≥ `angle_change_threshold`도 변화
3. **위치 변화**: 엉덩이+어깨 합산 움직임이 ≥ `position_change_threshold`

이 세 조건 중 **하나라도** `drop_window_s` 내에서 발생하면 추가 분석을 위한 "낙상 후보"가 생성됩니다.

---
## 6. 동작 원리 (쉬운 설명)
1. 프레임 → MoveNet 17개 관절 키포인트 산출.  
2. 엉덩이/어깨 평균으로 각도 & 수직 속도 계산.  
3. 급락 + 낮은 자세 → 낙상 후보 → 짧은 무동작 타이머 시작.  
4. 타이머 내 계속 무동작 & 낮은 자세 → 즉시 경보.  
5. 실패 시 장기 무동작(Soft → Hard) 경로로 전환.  
6. 샤워 시간에는 허용 시간 늘리고 모션 허용도 조정.  
7. 미확인 경보는 재알림, Heartbeat로 일일 상태 보고.

---
## 7. 텔레그램 버튼
| 라벨 | 영어 | 동작 |
|------|------|------|
| 괜찮아요 | I'm OK | 경보 확인 & 종료 |
| 오탐 | False Alarm | 오탐 표시 (향후 튜닝 활용) |
| 중지 | Stop | 원격 종료 |

---
## 8. 실행 모드
| 모드 | 명령 | 설명 |
|------|------|------|
| 프로덕션 | `venv/bin/python -m src.main --config config.yaml` | 실제 하드웨어 |
| 래퍼 | `venv/bin/python main_runner.py --config config.yaml` | 임포트 호환 |
| Mock | `venv/bin/python -m src.main --config examples/config_mock.yaml` | 카메라 없음 |
| 테스트 | `python -m tests.run_all` | 유닛 테스트 |

---
## 9. Systemd 서비스
```bash
sudo cp service/bathguard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bathguard
journalctl -u bathguard -f
```

---
## 10. 모니터링 / 로그
```bash
./monitor.sh health
./monitor.sh live
./monitor.sh perf
```
경보 로그: `alerts.log`.

---
## 11. 업데이트 / 유지보수
```bash
git pull
sudo systemctl restart bathguard
```
모델 교체: 같은 경로 TFLite 파일 교체 후 재시작.

---
## 12. 문제 해결
| 문제 | 확인 | 해결 |
|------|------|------|
| 카메라 X | `ls /dev/video*` | 케이블/활성화 확인 |
| 텔레그램 X | 토큰/Chat ID | BotFather 재발급 |
| 오탐 많음 | angle_threshold ↑ | movement_tolerance 조정 |
| 감지 누락 | drop_threshold ↓ | fast_fall_immobility_s ↓ |
| CPU 높음 | fps ↓ threads ↓ | 방열 개선 |

---
## 13. 보안 & 프라이버시 체크리스트
| 항목 | 이유 |
|------|------|
| 물리적 접근 제한 | 카메라 재조준/분해 방지 |
| SSH 키 사용 | 비밀번호 공격 방지 |
| 정기 업데이트 | 보안 패치 적용 |
| 최소 포트 개방 | 공격면 감소 |

---
## 14. 기여 (Contributing)
1. Fork & 브랜치 생성  
2. 테스트 추가/갱신  
3. EN/KO README 동기화 유지  
4. PR 제출 (변경 이유 명확히)  

테스트: `python -m tests.run_all`.

---
## 15. 로드맵 아이디어
- 다국어 i18n 맵 외부화
- 알림 피드백 기반 자동 임계값 조정
- 로컬 웹 대시보드
- 선택적 음성 응답 (“괜찮으세요?”)

---
## 16. 감사
TensorFlow, OpenCV, Raspberry Pi Foundation, Telegram Bot API, 커뮤니티 기여자분들께 감사.

---
## 17. 라이선스 & 면책
MIT License (LICENSE 참조).  
본 시스템은 **전문 의료 모니터링을 대체하지 않으며**, 보조 조기 경보 수단입니다.

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
git clone https://github.com/durume/duruon-bathroom-monitoring.git
cd duruon-bathroom-monitoring

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
