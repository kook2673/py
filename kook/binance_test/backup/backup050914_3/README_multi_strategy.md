# 다중 전략 포트폴리오 관리 시스템

## 📋 개요

이 시스템은 10개의 서로 다른 트레이딩 전략을 동시에 실행하고, 성과에 따라 자동으로 자본을 재배분하는 포트폴리오 관리 시스템입니다.

## 🚀 주요 기능

### 1. 다중 전략 실행
- **10개 전략 동시 실행**: 변동성돌파, 모멘텀, 스윙, 브레이크아웃, 스캘핑, RSI, MACD, 볼린저밴드, 이동평균, 스토캐스틱
- **다양한 시간프레임**: 1분, 1시간, 4시간 등 각 전략에 최적화된 시간프레임 사용

### 2. 동적 자본 배분
- **초기 배분**: 10개 전략에 균등 배분 (각 10%)
- **동적 조정**: 성과에 따라 1% ~ 20% 범위에서 자동 조정
- **성과 기반**: 수익률(50%), 승률(30%), 샤프비율(20%) 가중평균으로 배분

### 3. 전략 활성화/비활성화
- **비활성화 조건**: 수익률 -50% 이하 또는 승률 30% 이하
- **재활성화 조건**: 수익률 양수이고 승률 50% 이상
- **자동 리밸런싱**: 주간 단위로 자동 실행

### 4. 실시간 모니터링
- **성과 추적**: 각 전략의 실시간 성과 모니터링
- **리스크 관리**: 최대 낙폭, 샤프 비율 등 리스크 지표 추적
- **자동 조정**: 성과에 따른 자동 자본 재배분

## 📊 지원 전략

| 번호 | 전략명 | 설명 | 시간프레임 | 주요 파라미터 |
|------|--------|------|------------|---------------|
| 1 | 변동성돌파 | ATR 기반 변동성 돌파 전략 | 1h | lookback=20, k=0.5 |
| 2 | 모멘텀 | 가격 모멘텀 추종 전략 | 1h | short=12, long=26 |
| 3 | 스윙 | 스윙 고점/저점 돌파 전략 | 4h | swing_period=5 |
| 4 | 브레이크아웃 | 저항선/지지선 돌파 전략 | 1h | lookback=20 |
| 5 | 스캘핑 | 단기 이동평균 교차 전략 | 1m | short=5, long=20 |
| 6 | RSI | RSI 과매수/과매도 전략 | 1h | period=14, oversold=30, overbought=70 |
| 7 | MACD | MACD 신호선 교차 전략 | 1h | fast=12, slow=26, signal=9 |
| 8 | 볼린저밴드 | 볼린저밴드 이탈 전략 | 1h | period=20, std=2 |
| 9 | 이동평균 | 이동평균 교차 전략 | 1h | short=10, long=30 |
| 10 | 스토캐스틱 | 스토캐스틱 과매수/과매도 전략 | 1h | k=14, d=3, oversold=20, overbought=80 |

## 🛠️ 설치 및 실행

### 1. 필요한 패키지 설치
```bash
pip install pandas numpy matplotlib seaborn
```

### 2. 데이터 준비
- `data/BTCUSDT/1h/BTCUSDT_1h_2024.csv` 파일이 필요합니다.
- 다른 심볼이나 시간프레임을 사용하려면 해당 경로에 데이터 파일을 준비하세요.

### 3. 실행 방법

#### 방법 1: 배치 파일 사용 (Windows)
```bash
run_multi_strategy.bat
```

#### 방법 2: Python 스크립트 직접 실행
```bash
# 기본 실행
python run_multi_strategy.py

# 커스텀 실행
python run_multi_strategy.py --symbol BTCUSDT --timeframe 1h --start 2024-01-01 --end 2024-12-31 --capital 100000

# 전략 정보만 보기
python run_multi_strategy.py --info
```

## 📈 사용 예시

### 기본 백테스트 실행
```bash
python run_multi_strategy.py --start 2024-01-01 --end 2024-12-31 --capital 100000
```

### 커스텀 설정으로 실행
```bash
python run_multi_strategy.py \
  --symbol ETHUSDT \
  --timeframe 4h \
  --start 2024-06-01 \
  --end 2024-12-31 \
  --capital 50000 \
  --rebalance 48
```

## 📊 결과 분석

### 1. 콘솔 출력
- 실시간 진행 상황
- 전략별 성과 요약
- 포트폴리오 전체 성과

### 2. 생성되는 파일
- `logs/multi_strategy_portfolio_YYYYMMDD_HHMMSS.json`: 상세 결과 데이터
- `logs/multi_strategy_performance_YYYYMMDD_HHMMSS.png`: 성과 차트
- `logs/multi_strategy_summary_YYYYMMDD_HHMMSS.json`: 요약 보고서

### 3. 성과 지표
- **총 수익률**: 전체 기간 수익률
- **최대 낙폭(MDD)**: 최대 손실 구간
- **샤프 비율**: 위험 대비 수익률
- **승률**: 수익 거래 비율
- **전략별 배분**: 각 전략의 자본 배분 비율

## ⚙️ 설정 파일

`multi_strategy_config.json` 파일에서 다음 설정을 조정할 수 있습니다:

### 포트폴리오 설정
```json
{
  "portfolio_settings": {
    "initial_capital": 100000,
    "rebalance_frequency_hours": 24,
    "min_allocation_percent": 1.0,
    "max_allocation_percent": 20.0,
    "deactivation_threshold_return": -50.0,
    "deactivation_threshold_winrate": 30.0
  }
}
```

### 전략별 설정
```json
{
  "strategy_settings": {
    "volatility_breakout": {
      "name": "변동성돌파",
      "timeframe": "1h",
      "lookback_period": 20,
      "k_factor": 0.5,
      "enabled": true
    }
  }
}
```

## 🔧 고급 사용법

### 1. 전략 추가
새로운 전략을 추가하려면 `StrategyBase` 클래스를 상속받아 구현하세요:

```python
class MyCustomStrategy(StrategyBase):
    def __init__(self):
        super().__init__("내전략", "1h")
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        # 매매 신호 계산 로직 구현
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        # ... 신호 계산 ...
        return signals
```

### 2. 자본 배분 로직 수정
`_reallocate_capital()` 메서드를 수정하여 자본 배분 로직을 커스터마이징할 수 있습니다.

### 3. 리스크 관리 강화
`risk_management` 설정을 통해 손절매, 익절매 등 리스크 관리 규칙을 추가할 수 있습니다.

## 📝 주의사항

1. **데이터 품질**: 백테스트 결과의 신뢰성을 위해 고품질의 데이터를 사용하세요.
2. **과최적화 주의**: 과도한 파라미터 튜닝은 과최적화를 야기할 수 있습니다.
3. **실매매 전 테스트**: 실제 자금으로 거래하기 전에 충분한 백테스트를 수행하세요.
4. **리스크 관리**: 손실 한도를 설정하고 철저한 리스크 관리를 하세요.

## 🤝 기여하기

버그 리포트, 기능 제안, 코드 기여를 환영합니다!

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

---

**면책 조항**: 이 소프트웨어는 교육 및 연구 목적으로 제공됩니다. 실제 투자 결정에 사용하기 전에 충분한 검토와 테스트를 수행하시기 바랍니다. 투자 손실에 대한 책임은 사용자에게 있습니다.
