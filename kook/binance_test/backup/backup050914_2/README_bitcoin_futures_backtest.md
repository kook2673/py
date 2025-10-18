# 비트코인 선물 백테스트 시스템

## 🚀 개요

이 시스템은 비트코인 선물 거래를 위한 5가지 주요 전략의 백테스트를 제공합니다. 각 전략은 구체적인 진입/청산 규칙과 함께 상세한 성과 분석을 제공합니다.

## 📊 지원 전략

### 1. 변동성 돌파 전략 (Volatility Breakout)
- **개요**: ATR 기반 변동성 돌파를 활용한 전략
- **진입 조건**: 전일 고가/저가 + ATR * k 돌파 + 거래량 확인
- **청산 조건**: ATR 기반 손절/익절 (2:1 비율)
- **시간프레임**: 1시간봉
- **레버리지**: 10배

### 2. 모멘텀 전략 (Momentum Strategy)
- **개요**: 이동평균 크로스오버와 모멘텀 지표를 조합한 전략
- **진입 조건**: 5MA > 20MA + 모멘텀 확인 + RSI 필터
- **청산 조건**: 모멘텀 약화 + ATR 기반 손절/익절
- **시간프레임**: 1시간봉
- **레버리지**: 10배

### 3. 스윙 트레이딩 (Swing Trading)
- **개요**: 중기 추세를 추종하는 전략
- **진입 조건**: 200MA 위/아래 + 10MA vs 50MA + RSI 필터
- **청산 조건**: 추세 반전 + ATR 기반 손절/익절
- **시간프레임**: 4시간봉
- **레버리지**: 5배

### 4. 브레이크아웃 전략 (Breakout Strategy)
- **개요**: 지지/저항선 돌파를 활용한 전략
- **진입 조건**: 20일 고가/저가 돌파 + 거래량/변동성 확인
- **청산 조건**: 가짜 돌파 필터링 + ATR 기반 손절/익절
- **시간프레임**: 1시간봉
- **레버리지**: 10배

### 5. 스캘핑 전략 (Scalping Strategy)
- **개요**: 매우 짧은 시간 내에 작은 가격 변동을 이용한 전략
- **진입 조건**: RSI/BB/스토캐스틱 반전 + 거래량/변동성 확인
- **청산 조건**: 빠른 수익 실현 (0.5%) + 타이트한 손절 (0.3%)
- **시간프레임**: 1분봉
- **레버리지**: 20배

## 🛠️ 설치 및 설정

### 필수 라이브러리
```bash
pip install pandas numpy matplotlib seaborn
```

### 데이터 구조
```
data/
└── BTC_USDT/
    ├── 1m/          # 1분봉 데이터
    ├── 5m/          # 5분봉 데이터
    ├── 15m/         # 15분봉 데이터
    ├── 1h/          # 1시간봉 데이터
    ├── 4h/          # 4시간봉 데이터
    └── 1d/          # 1일봉 데이터
```

각 데이터 파일은 다음 형식을 따라야 합니다:
- 파일명: `YYYY-MM.csv` (예: `2024-01.csv`)
- 컬럼: `timestamp, open, high, low, close, volume`

## 🚀 사용법

### 1. 개별 전략 실행

#### 변동성 돌파 전략
```bash
python volatility_breakout_backtest.py
```

#### 모멘텀 전략
```bash
python momentum_strategy_backtest.py
```

#### 스윙 트레이딩
```bash
python swing_trading_backtest.py
```

#### 브레이크아웃 전략
```bash
python breakout_strategy_backtest.py
```

#### 스캘핑 전략
```bash
python scalping_strategy_backtest.py
```

### 2. 모든 전략 실행 및 비교

```bash
# 기본 실행 (2024년 전체)
python run_all_strategies.py

# 사용자 정의 기간
python run_all_strategies.py --start 2024-01-01 --end 2024-12-31 --capital 10000

# 특정 전략만 실행
python run_all_strategies.py --strategies volatility momentum swing
```

### 3. 통합 백테스트 시스템

```bash
# 변동성 돌파 전략
python bitcoin_futures_backtest_system.py --strategy volatility --period 1h --start 2024-01-01 --end 2024-12-31

# 모멘텀 전략
python bitcoin_futures_backtest_system.py --strategy momentum --period 1h --start 2024-01-01 --end 2024-12-31

# 스윙 트레이딩
python bitcoin_futures_backtest_system.py --strategy swing --period 4h --start 2024-01-01 --end 2024-12-31

# 브레이크아웃 전략
python bitcoin_futures_backtest_system.py --strategy breakout --period 1h --start 2024-01-01 --end 2024-12-31

# 스캘핑 전략
python bitcoin_futures_backtest_system.py --strategy scalping --period 1m --start 2024-01-01 --end 2024-12-31
```

## 📈 결과 분석

### 출력 파일
각 전략 실행 후 다음 파일들이 생성됩니다:

1. **JSON 결과 파일**: `{strategy}_backtest_{timestamp}.json`
   - 상세한 거래 내역
   - 성과 지표
   - 자산 곡선 데이터

2. **시각화 파일**: `{strategy}_backtest_{timestamp}.png`
   - 가격 차트 + 거래 신호
   - 기술적 지표
   - 자산 곡선
   - MDD 현황

3. **비교 차트**: `strategy_comparison_{timestamp}.png`
   - 전략별 성과 비교
   - 수익률, MDD, 승률, 거래 수 비교

4. **요약 보고서**: `strategy_summary_{timestamp}.csv`
   - 전략별 핵심 지표 요약

### 주요 성과 지표

- **총 수익률**: 백테스트 기간 동안의 총 수익률
- **최대 MDD**: 최대 낙폭 (Maximum Drawdown)
- **승률**: 수익 거래 비율
- **평균 수익/손실**: 수익/손실 거래의 평균 수익률
- **총 거래 수**: 백테스트 기간 동안의 총 거래 횟수
- **평균 보유 시간**: 포지션의 평균 보유 시간

## ⚙️ 설정 옵션

### 백테스트 파라미터
- `initial_capital`: 초기 자본 (기본값: 10,000 USDT)
- `leverage`: 레버리지 (전략별 다름)
- `fee`: 수수료 (기본값: 0.1%)

### 전략별 파라미터
각 전략은 고유한 파라미터를 가지고 있으며, 코드 내에서 조정 가능합니다:

- **변동성 돌파**: ATR 배수, 거래량 임계값
- **모멘텀**: 이동평균 기간, RSI 임계값
- **스윙 트레이딩**: 추세 확인 기간, ADX 임계값
- **브레이크아웃**: 돌파 강도, 가짜 돌파 필터
- **스캘핑**: 반전 신호 임계값, 빠른 청산 조건

## 🔧 커스터마이징

### 새로운 전략 추가
1. 새로운 전략 클래스 생성
2. `run_all_strategies.py`에 전략 추가
3. `bitcoin_futures_backtest_system.py`에 전략 로직 추가

### 파라미터 최적화
각 전략의 파라미터를 조정하여 성과를 개선할 수 있습니다:

```python
# 예: 변동성 돌파 전략의 ATR 배수 조정
df['breakout_upper'] = df['high'].shift(1) + df['atr'].shift(1) * 1.5  # 1.0 → 1.5
```

## 📊 성과 분석 예시

### 전략별 특징
- **변동성 돌파**: 높은 수익률, 높은 MDD
- **모멘텀**: 안정적인 수익, 중간 MDD
- **스윙 트레이딩**: 낮은 MDD, 중간 수익률
- **브레이크아웃**: 높은 승률, 중간 수익률
- **스캘핑**: 높은 거래 빈도, 낮은 수익률

### 리스크 관리
- 각 전략은 ATR 기반 동적 포지션 사이징 사용
- 연속 손실 시 포지션 크기 감소
- 최대 손실 제한 설정
- 시간 기반 강제 청산

## ⚠️ 주의사항

1. **백테스트 한계**: 과거 데이터 기반 결과는 미래 성과를 보장하지 않음
2. **거래 비용**: 실제 거래 시 슬리피지와 수수료 고려 필요
3. **데이터 품질**: 백테스트 결과는 입력 데이터의 품질에 의존
4. **시장 변화**: 시장 구조 변화로 인한 전략 성과 변동 가능

## 📞 지원

문제가 발생하거나 개선 사항이 있으면 이슈를 등록해 주세요.

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.
