# 스켈핑 최적화 도구

1배 기준 0.3~0.5% 수익률을 목표로 하는 스켈핑 전략 최적화 도구입니다.

## 🎯 주요 기능

### 1. 스켈핑 전략 최적화
- **목표 수익률**: 0.3~0.5% (1배 레버리지 기준)
- **분할매매**: 3단계 분할매도/분할매수 시스템
- **리스크 관리**: 0.1% 손절, 2% 일일 최대 손실
- **파라미터 최적화**: 그리드 서치를 통한 최적 파라미터 탐색

### 2. 기술적 지표 조합
- **볼린저밴드**: 밴드 터치 신호
- **RSI**: 과매수/과매도 신호
- **MACD**: 크로스오버 신호
- **거래량**: 급증 신호

### 3. 분할매매 시스템
- **3단계 분할**: 40%, 40%, 20% 비율
- **개별 익절/손절**: 각 분할 주문별 독립 관리
- **수익률 극대화**: 작은 수익이라도 확실하게 확보

### 4. 실시간 모니터링
- **실시간 가격 추적**: 1분 간격 가격 업데이트
- **자동 신호 생성**: 기술적 지표 기반 자동 신호
- **자동 매매 실행**: 신호 발생시 자동 포지션 진입
- **리스크 관리**: 실시간 손절/익절 관리

## 📁 파일 구조

```
kook/binance_test/
├── scalping_optimizer.py      # 메인 최적화 도구
├── scalping_monitor.py        # 실시간 모니터링
├── run_scalping_optimizer.py  # 실행 스크립트
├── run_scalping.bat          # Windows 배치 파일
├── README_scalping.md        # 사용법 설명
└── logs/                     # 로그 파일
    ├── scalping_optimizer.log
    └── scalping_monitor.log
```

## 🚀 사용법

### 1. Windows에서 실행
```bash
# 배치 파일 실행
run_scalping.bat

# 또는 직접 실행
python run_scalping_optimizer.py backtest
python run_scalping_optimizer.py monitor
python run_scalping_optimizer.py quick
```

### 2. 백테스트 실행
```python
from scalping_optimizer import ScalpingOptimizer, ScalpingParams

# 최적화 도구 생성
optimizer = ScalpingOptimizer(initial_balance=10000)

# 데이터 로드
df = optimizer.load_data("data/BTCUSDT/5m/BTCUSDT_5m_2024.csv")

# 파라미터 최적화
optimal_params = optimizer.optimize_parameters(df)

# 백테스트 실행
results = optimizer.execute_split_scalping(df, optimal_params)

# 결과 출력
print(f"총 수익률: {results['total_return']:.2f}%")
print(f"승률: {results['win_rate']:.1f}%")
```

### 3. 실시간 모니터링
```python
from scalping_monitor import ScalpingMonitor

# 모니터 생성
monitor = ScalpingMonitor(initial_balance=10000)

# 모니터링 시작
monitor.start_monitoring(symbol="BTCUSDT", interval=60)

# 상태 확인
monitor.print_status()

# 모니터링 중지
monitor.stop_monitoring()
```

## ⚙️ 파라미터 설정

### 기본 파라미터
```python
params = ScalpingParams(
    target_profit=0.003,      # 0.3% 목표 수익
    max_profit=0.005,         # 0.5% 최대 수익
    stop_loss=0.001,          # 0.1% 손절
    position_size=0.1,        # 10% 포지션 크기
    split_ratio=[0.4, 0.4, 0.2],  # 분할 비율
    max_daily_trades=50,      # 일일 최대 거래 수
    max_daily_loss=0.02,      # 2% 일일 최대 손실
    cooldown_minutes=5        # 거래 간 쿨다운
)
```

### 최적화 범위
- **목표 수익**: 0.2%~0.6%
- **최대 수익**: 0.4%~0.8%
- **손절**: 0.05%~0.2%
- **포지션 크기**: 5%~20%

## 📊 성과 지표

### 기본 지표
- **총 수익률**: 전체 기간 수익률
- **승률**: 수익 거래 비율
- **수익 팩터**: 총 수익 / 총 손실
- **최대 낙폭**: 최대 손실 구간

### 분할매매 지표
- **분할 거래 수**: 분할 주문 실행 횟수
- **평균 분할 수익**: 분할 주문 평균 수익률
- **분할별 성과**: 각 분할 단계별 성과

### 일일 지표
- **일일 승률**: 수익 일수 비율
- **연속 수익/손실**: 최대 연속 일수
- **일일 거래 수**: 하루 평균 거래 횟수

## 🛡️ 리스크 관리

### 1. 포지션 관리
- **1배 레버리지**: 원금 대비 1배만 거래
- **포지션 크기 제한**: 자본의 10% 이하
- **분할매매**: 리스크 분산

### 2. 손실 제한
- **개별 손절**: 0.1% 손실시 즉시 청산
- **일일 손실 한도**: 2% 손실시 거래 중단
- **거래 수 한도**: 일일 50회 제한

### 3. 수익 관리
- **목표 수익**: 0.3% 달성시 익절
- **최대 수익**: 0.5% 초과시 익절
- **분할 익절**: 각 분할별 독립 익절

## 📈 사용 시나리오

### 1. 백테스트 시나리오
```bash
# 1. 빠른 테스트 (10분)
python run_scalping_optimizer.py quick

# 2. 전체 백테스트 (30분)
python run_scalping_optimizer.py backtest

# 3. 결과 확인
# - scalping_optimizer_results.png (차트)
# - scalping_optimizer_results.json (데이터)
```

### 2. 실시간 모니터링 시나리오
```bash
# 1. 모니터링 시작
python run_scalping_optimizer.py monitor

# 2. 실시간 상태 확인
# - 30초마다 상태 출력
# - Ctrl+C로 중지

# 3. 결과 저장
# - scalping_monitor_results.json
```

## 🔧 커스터마이징

### 1. 전략 수정
```python
# scalping_optimizer.py의 generate_scalping_signals 함수 수정
def generate_scalping_signals(self, df, params):
    # 여기에 자신만의 신호 로직 추가
    pass
```

### 2. 파라미터 조정
```python
# run_scalping_optimizer.py의 파라미터 수정
params = ScalpingParams(
    target_profit=0.004,  # 0.4%로 변경
    max_profit=0.006,     # 0.6%로 변경
    # ... 기타 파라미터
)
```

### 3. 지표 추가
```python
# calculate_indicators 함수에 새로운 지표 추가
def calculate_indicators(self, df):
    # 새로운 지표 계산
    df['new_indicator'] = talib.NEW_INDICATOR(df['close'])
    return df
```

## ⚠️ 주의사항

### 1. 데이터 요구사항
- **최소 데이터**: 1000개 캔들 이상
- **시간 간격**: 1분봉 또는 5분봉
- **필수 컬럼**: open, high, low, close, volume

### 2. 리스크 경고
- **과거 성과**: 미래 수익을 보장하지 않음
- **시장 리스크**: 급격한 가격 변동시 손실 가능
- **시스템 리스크**: 기술적 오류 가능성

### 3. 사용 권장사항
- **소액 테스트**: 처음에는 소액으로 테스트
- **지속적 모니터링**: 실시간 상태 확인
- **백테스트 검증**: 충분한 백테스트 후 실전 적용

## 📞 지원

문제가 발생하거나 개선 사항이 있으면 로그 파일을 확인하세요:
- `logs/scalping_optimizer.log`
- `logs/scalping_monitor.log`

## 📝 라이선스

이 도구는 교육 및 연구 목적으로 제작되었습니다. 실제 거래에 사용할 때는 충분한 테스트와 검증을 거쳐 사용하시기 바랍니다.
