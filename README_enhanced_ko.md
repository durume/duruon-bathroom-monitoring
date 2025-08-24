# BathGuard — 프라이버시 우선 화장실 응급상황 모니터 (RPi 5 + CV + 텔레그램)

**목표**: 온디바이스 자세 추정을 사용하여 **화장실**에서 낙상/무의식 상태를 감지하고 **텔레그램** 알림(텍스트 + 익명화된 골격 이미지)을 전송합니다. 비디오는 저장되거나 업로드되지 않습니다.

> ⚠️ 화장실은 매우 민감한 공간입니다. **명시적 동의** 하에서만 배포하고 지역 법률을 확인하세요.

## 기능
- 온디바이스 추론 (MoveNet SinglePose Lightning, TFLite).
- 프라이버시: **텍스트**와 선택적 **골격-온-블랙** 이미지만 전송.
- **샤워 인식 감지**: 샤워 활동과 응급상황을 구별하는 스마트 적응형 임계값.
- 강력한 휴리스틱: 급작스러운 낙하 + 수평 몸통 + 무동작; 또는 낙하 없는 장시간 무동작.
- 인라인 **확인** 버튼이 있는 텔레그램 알림.
- 개발용 `mock` 백엔드 (카메라/모델 불필요).

## 향상된 샤워 인식 감지

BathGuard는 이제 응급상황 감지 기능을 유지하면서 일반적인 샤워 활동에 적응하는 지능형 감지를 포함합니다:

### 적응형 임계값
- **움직임 허용도**: 직립 자세와 비교하여 몸을 구부릴 때(샴푸, 세안) 더 관대함
- **시간 기반 조정**: 샤워 시간(기본값: 오전 6시 - 오후 10시) 동안 4배 긴 알림 임계값
- **단계별 알림**: 샤워 시간 배수가 적용된 소프트 알림(30초) 후 응급 알림(60초)

### 설정
향상된 감지는 `config.yaml`에서 설정됩니다:

```yaml
risk:
  angle_threshold_deg: 50          # 잠재적 위험 트리거 포인트
  soft_immobility_s: 30.0          # 30초 후 소프트 알림
  hard_immobility_s: 60.0          # 60초 후 응급 알림
  
  # 샤워 인식 매개변수
  movement_tolerance_low_angle: 0.12   # 구부릴 때 더 관대함 (샤워 활동)
  movement_tolerance_high_angle: 0.05  # 직립할 때 더 엄격함
  shower_mode_enabled: true
  shower_start_hour: 6             # 샤워 시간 시작
  shower_end_hour: 22              # 샤워 시간 종료
  shower_duration_multiplier: 4.0  # 샤워 시간 동안 4배 긴 임계값
```

### 작동 방식
1. **일반 시간**: 표준 임계값 적용 (30초 소프트, 60초 응급)
2. **샤워 시간** (오전 6시 - 오후 10시): 연장된 임계값 (120초 소프트, 240초 응급)
3. **자세 적응형**: 구부릴 때 움직임 감도 낮춤 (세안 활동)
4. **다단계 알림**: 점진적 경고 시스템으로 오알림 방지

이 시스템은 필요할 때 신속한 응급상황 감지를 유지하면서 일반적인 샤워 활동 중 오알림을 극적으로 줄입니다.

## 빠른 시작 (Raspberry Pi OS 64비트, Pi 5 권장)
```bash
git clone <this repo> bathguard && cd bathguard
./install.sh
# /opt/bathguard/.env에 비밀 정보 입력 (TG_BOT_TOKEN, TG_CHAT_ID)
# 필요시 config.yaml 편집
/opt/bathguard/venv/bin/python -m src.main --config /opt/bathguard/config.yaml
```

### 텔레그램 설정
**@BotFather**로 봇을 생성하고 **봇 토큰**을 획득한 후, **chat_id**를 찾으세요 (채팅을 시작하고 `getUpdates`를 호출하거나 헬퍼 사용). 공식 **텔레그램 봇 API** 문서를 참조하세요. (https://core.telegram.org/bots/api)

### MoveNet 모델
**MoveNet SinglePose Lightning (TFLite)**를 사용합니다. 자동 다운로드 스크립트가 실패하면 (TF Hub URL이 가끔 변경됨), **TensorFlow Hub MoveNet 튜토리얼**을 열고 **SinglePose Lightning** TFLite 모델 링크를 따라가서 `models/movenet_singlepose_lightning.tflite`에 저장하세요.
- TF Hub MoveNet 개요: https://www.tensorflow.org/hub/tutorials/movenet

## 설정
`config.yaml`은 카메라, 위험 임계값, 백엔드 선택을 보유합니다. 텔레그램 비밀 정보는 환경 변수를 사용하세요.

## Systemd 서비스
```bash
sudo cp service/bathguard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bathguard
journalctl -u bathguard -f
```

## 카메라/모델 없이 개발
```bash
# 목 백엔드 + 더미 알리미 사용
python -m src.main --config config.yaml
# 또는 테스트 실행:
python -m pytest -q   # pytest가 설치된 경우
# 내장 unittest:
python -m tests.run_all
```

## 안전성 및 프라이버시
- 프레임은 디스크에 저장되지 않음; 골격 이미지는 검은 배경에 렌더링됨 (배경 없음).
- 장치를 밀폐된 인클로저에 보관하고, 노출을 최소화하기 위해 카메라를 바닥 쪽으로 각도 조정.
- 강력한 물리적 보안 확보; SSH 제한; 자동 업데이트.

## 라이선스
MIT