# 📈 Kiwoom OpenAPI Python 모듈

이 폴더는 **키움증권 OpenAPI(REST) 기반 자동매매/데이터 수집/백테스트**를 위한 파이썬 코드와 공용 라이브러리를 모아둔 공간입니다.

---

## 📁 폴더 구조 및 주요 파일 설명

```
py/kiwoom/
├── .env                  # 키움 API 키/시크릿/토큰/환경 설정 파일 (반드시 여기에 위치)
├── kiwoom_openapi.py     # 공용 키움 OpenAPI REST 클라이언스(토큰 자동 관리, 테마/계좌/주식 등)
├── turtle/               # 터틀 트레이딩, 전략, 테마전략 등 자동매매/백테스트 코드
├── discount/             # 할인/특가 관련 자동화 코드 (예: 이벤트, 알림 등)
├── futures/              # 선물/옵션 관련 자동매매 코드
├── ...                  # 기타 확장 모듈
```

---

## 🗂️ 주요 파일/폴더 상세 설명

### 1. `.env`
- **API 키, 시크릿, 토큰, 환경설정**을 저장하는 파일
- 예시:
  ```
  KIWOOM_APP_KEY=발급받은_APP_KEY
  KIWOOM_SECRET_KEY=발급받은_SECRET_KEY
  KIWOOM_MOCK=true  # 모의투자면 true, 실전이면 false
  KIWOOM_ACCESS_TOKEN=자동발급된_토큰값
  ```
- 모든 파이썬 코드에서 이 파일을 읽어 키/토큰을 공유함

### 2. `kiwoom_openapi.py`
- **키움 OpenAPI REST 공용 클라이언트 클래스**
- 주요 기능:
  - 토큰 자동 발급 및 .env 저장/관리
  - 테마 그룹/구성종목(ka90001/ka90002) API
  - 계좌/주식/잔고 등 다양한 REST API 지원
- 예시 사용법:
  ```python
  from kiwoom_openapi import KiwoomOpenAPI
  api = KiwoomOpenAPI()
  theme_groups = api.get_theme_groups()
  ```
- 모든 하위 모듈에서 import하여 공용으로 사용

### 3. `turtle/`
- **터틀 트레이딩 전략, 테마 전략, 백테스트, 실전 자동매매** 등 다양한 전략 코드 모음
- 예시: `main.py`, `theme_turtle_strategy.py`, `kiwoom_theme_api_sample.py` 등
- 대부분 `kiwoom_openapi.py`를 import하여 API를 사용

### 4. `discount/`
- **이벤트, 할인, 특가 관련 자동화/알림** 코드 모음
- 예시: `kiwoom_openapi.py`(이전 버전, 현재는 상위 폴더로 통합됨)

### 5. `futures/`
- **선물/옵션 자동매매, 데이터 수집** 관련 코드
- 예시: `main.py`, `config.py` 등

---

## 🚀 사용법 요약

1. `.env` 파일에 키/시크릿/환경을 입력
2. `kiwoom_openapi.py`를 import하여 공용 API 사용
3. 토큰이 없으면 자동으로 발급 및 저장됨
4. 모든 전략/자동매매/데이터 수집 코드에서 동일한 방식으로 API 사용 가능

---

## 🔗 참고
- 키움 OpenAPI 공식 문서 및 개발자센터
- 각 폴더별 README/주석 참고

---

**문의/확장/기여는 언제든 환영합니다!** 