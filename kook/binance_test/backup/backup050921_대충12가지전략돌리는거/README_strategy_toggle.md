# MA 적응형 전략 시스템 - 전략 선택 기능

이제 원하는 전략만 선택해서 백테스트를 실행할 수 있습니다!

## 🎯 사용 방법

### 1. 사용 가능한 전략 목록 확인
```bash
python ma_adaptive_12.py --list-strategies
```

### 2. 설정 파일로 전략 선택 (추천)
`strategy_config.json` 파일을 수정하여 원하는 전략을 활성화/비활성화할 수 있습니다.

```json
{
  "enabled_strategies": [
    "momentum_long",
    "momentum_short"
  ]
}
```

### 3. 명령행으로 전략 선택
```bash
# 2개 전략만 테스트
python ma_adaptive_12.py --strategies momentum_long momentum_short --year 2023

# 3개 전략 테스트
python ma_adaptive_12.py --strategies macd_long macd_short trend_long --year 2023

# 연속 백테스트 (설정 파일 사용)
python ma_adaptive_12.py --start-year 2020 --end-year 2023
```

## 📋 사용 가능한 전략 목록

| 전략명 | 설명 |
|--------|------|
| `momentum_long` | 모멘텀 롱 전략 |
| `momentum_short` | 모멘텀 숏 전략 |
| `scalping_long` | 스캘핑 롱 전략 |
| `scalping_short` | 스캘핑 숏 전략 |
| `macd_long` | MACD 롱 전략 |
| `macd_short` | MACD 숏 전략 |
| `moving_average_long` | 이동평균 롱 전략 |
| `moving_average_short` | 이동평균 숏 전략 |
| `trend_long` | 트렌드 롱 전략 |
| `trend_short` | 트렌드 숏 전략 |
| `bb_long` | 볼린저밴드 롱 전략 |
| `bb_short` | 볼린저밴드 숏 전략 |

## 🔧 설정 파일 예시

### 2개 전략만 테스트 (모멘텀 전략)
```json
{
  "enabled_strategies": [
    "momentum_long",
    "momentum_short"
  ]
}
```

### 4개 전략 테스트 (MACD + 트렌드)
```json
{
  "enabled_strategies": [
    "macd_long",
    "macd_short",
    "trend_long",
    "trend_short"
  ]
}
```

### 모든 전략 테스트
```json
{
  "enabled_strategies": [
    "momentum_long",
    "momentum_short",
    "scalping_long",
    "scalping_short",
    "macd_long",
    "macd_short",
    "moving_average_long",
    "moving_average_short",
    "trend_long",
    "trend_short",
    "bb_long",
    "bb_short"
  ]
}
```

## 💡 팁

1. **설정 파일 사용**: 자주 사용하는 전략 조합은 설정 파일에 저장해두세요
2. **명령행 사용**: 한 번만 테스트할 때는 명령행 인자를 사용하세요
3. **전략 조합**: 롱/숏 전략을 함께 사용하면 더 안정적인 결과를 얻을 수 있습니다
4. **자본 배분**: 선택한 전략 수에 따라 자본이 자동으로 균등 배분됩니다

## 🚀 예시 명령어

```bash
# 1. 사용 가능한 전략 확인
python ma_adaptive_12.py --list-strategies

# 2. 2개 전략만 테스트 (2023년)
python ma_adaptive_12.py --strategies momentum_long momentum_short --year 2023

# 3. 수익성 개선된 설정으로 테스트
python ma_adaptive_12.py --config profitable_strategy_config.json --year 2023

# 4. 공격적 전략으로 테스트
python ma_adaptive_12.py --config aggressive_strategy_config.json --year 2023

# 5. 연속 백테스트 (2020-2023년)
python ma_adaptive_12.py --start-year 2020 --end-year 2023

# 6. 다른 설정 파일 사용
python ma_adaptive_12.py --config my_strategies.json --year 2023
```

## 💰 수익성 개선 사항

### ✅ 개선된 설정:
- **수수료**: 0.06% → 0.04% (33% 감소)
- **레버리지**: 5배 → 2배 (안전성 증가)
- **손절라인**: 15% → 8% (완화)
- **익절라인**: 12% 추가 (수익 확정)
- **진입 조건**: 완화 (더 많은 거래 기회)
- **진입 확률**: 1.5배 증가

### 📊 추천 전략 조합:
1. **수익성 개선**: `profitable_strategy_config.json` (4개 전략)
2. **공격적**: `aggressive_strategy_config.json` (6개 전략)
3. **안전적**: `strategy_config.json` (2개 전략)
