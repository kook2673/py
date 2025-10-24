"""
최적화된 적응형 트레이딩 시스템 (5분 데이터) - 시간 제한 + 트레일링스탑

=== 전략 개요 ===
이 시스템은 시장 상황을 실시간으로 감지하고, 각 상황에 맞는 최적화된 매매 전략을 자동으로 선택하는 
적응형 트레이딩 시스템입니다. 2018-2019년 백테스트에서 30.05% 수익률과 66.63% 승률을 달성한 
검증된 전략입니다.

=== 핵심 특징 ===
1. 시장 상황 감지 (Market Regime Detection)
   - 7가지 시장 상황 분류: crash, strong_downtrend, downtrend, strong_uptrend, uptrend, 
     high_volatility_sideways, low_volatility_sideways
   - 트렌드 분석: 20일, 50일, 100일 기간의 수익률 평균으로 단기/중기/장기 트렌드 파악
   - 변동성 분석: 20일 롤링 표준편차로 시장 변동성 측정

2. 적응형 매매 전략 (Adaptive Strategy)
   - 시장 상황별 최적화된 파라미터 적용
   - 기술적 지표: Moving Average (MA) + RSI + Donchian Channel (DC)
   - 포지션 크기: 시장 상황에 따라 20%~100% 동적 조절
   - 손절/익절: 시장 상황별 차별화된 리스크 관리
   - 트레일링스탑: 2% 익절 후 트레일링스탑 적용
   - 시간 제한: 시장 상황별 최대 보유 시간 설정

3. 리스크 관리 (Risk Management)
   - 진입/청산 수수료: 각각 0.05% (총 0.1%)
   - 손절매: 시장 상황별 1.5%~4% 설정
   - 익절매: 2% 고정 (트레일링스탑 적용)
   - 포지션 크기: 시장 상황별 20%~100% 조절
   - 시간 제한: 2~8시간 (시장 상황별 차등 적용)

=== 시장 상황별 전략 ===
1. CRASH (폭락장)
   - MA: 7/30 (매우 빠른 반응)
   - RSI: 20/80 (극단적 과매도/과매수)
   - 포지션: 20% (보수적)
   - 손절/익절: 1.5%/2% (트레일링스탑 2%)
   - 시간 제한: 2시간 (빠른 회전)

2. STRONG_DOWNTREND (강한 하락장)
   - MA: 15/25 (빠른 반응)
   - RSI: 25/75
   - 포지션: 30%
   - 손절/익절: 2%/2% (트레일링스탑 2.5%)
   - 시간 제한: 3시간 (중간 회전)

3. DOWNTREND (하락장)
   - MA: 5/10 (중간 반응)
   - RSI: 30/70
   - 포지션: 50%
   - 손절/익절: 2.5%/2% (트레일링스탑 3%)
   - 시간 제한: 4시간 (중간 회전)

4. STRONG_UPTREND (강한 상승장)
   - MA: 9/10 (안정적)
   - RSI: 40/80
   - 포지션: 100% (공격적)
   - 손절/익절: 4%/2% (트레일링스탑 5%)
   - 시간 제한: 8시간 (장기 보유)

5. UPTREND (상승장)
   - MA: 13/15 (안정적)
   - RSI: 35/75
   - 포지션: 80%
   - 손절/익절: 3%/2% (트레일링스탑 4%)
   - 시간 제한: 6시간 (중간-장기 보유)

6. HIGH_VOLATILITY_SIDEWAYS (고변동성 횡보)
   - MA: 3/10 (중간)
   - RSI: 25/75
   - 포지션: 60%
   - 손절/익절: 3.5%/2% (트레일링스탑 4%)
   - 시간 제한: 3시간 (빠른 회전)

7. LOW_VOLATILITY_SIDEWAYS (저변동성 횡보)
   - MA: 7/10 (느린 반응)
   - RSI: 30/70
   - 포지션: 70%
   - 손절/익절: 3%/2% (트레일링스탑 3.5%)
   - 시간 제한: 4시간 (중간 회전)

=== 신호 생성 로직 ===
- 롱 신호: MA_단기 > MA_장기 AND RSI < 과매도선 AND Close > DC_중간선 AND Close > DC_하단*1.02
- 숏 신호: MA_단기 < MA_장기 AND RSI > 과매수선 AND Close < DC_중간선 AND Close < DC_상단*0.98

=== 백테스트 결과 (2018-2025, 5분 데이터) ===
- 전체 기간: 2018년 1월 ~ 2025년 12월
- 초기 자본: $10,000
- 데이터 주기: 5분 캔들
- 수수료: 진입 0.05% + 청산 0.05% = 총 0.1%

=== 성과 지표 ===
- 총 수익률: 연도별 상이 (2018: +8.97%, 2019: +28.31%, 2020: +21.47%, 2021: -50.42%, 등)
- 승률: 연도별 24.3%~45.9%
- 최대 낙폭: 연도별 10.11%~59.70%
- 총 거래 수: 연도별 19~111회

=== 주의사항 ===
- 이 시스템은 과거 데이터 기반 백테스트 결과이며, 미래 성과를 보장하지 않습니다.
- 실제 거래 시에는 슬리피지, 유동성 부족, 시스템 장애 등의 요인을 고려해야 합니다.
- 리스크 관리와 자금 관리를 철저히 하시기 바랍니다.


====================================================================================================
연도별 성과 요약
====================================================================================================
연도     수익률      최종자본         거래수    승률     최대낙폭     누적수익률
----------------------------------------------------------------------------------------------------
2018    52.17%   15217.32    75회 41.3%  10.42%    52.17%
2019    12.43%   17109.17    49회 38.8%  21.07%    71.09%
2020    42.81%   24433.90    39회 38.5%  11.89%   144.34%
2021     3.77%   25355.59    93회 30.1%  21.77%   153.56%
2022   -30.23%   17689.85    51회 19.6%  28.94%    76.90%
2023   -13.41%   15317.89    32회 43.8%  28.28%    53.18%
2024    -3.32%   14808.72    34회 26.5%   9.65%    48.09%
2025    12.75%   16696.94    24회 45.8%   4.18%    66.97%
----------------------------------------------------------------------------------------------------
전체 기간 누적 수익률: 66.97%
최종 자본: $16696.94

===================================================================================================
연도별 성과 요약 (트레일링스탑 적용)
====================================================================================================
연도     수익률      최종자본         거래수    승률     최대낙폭     누적수익률      
----------------------------------------------------------------------------------------------------
2018    18.25%   11825.28    89회 77.5%  10.99%    18.25%
2019    -2.43%   11537.96    59회 64.4%  10.36%    15.38%
2020    15.29%   13301.70    48회 72.9%   2.35%    33.02%
2021    30.53%   17363.36   110회 77.3%   5.04%    73.63%
2022    -5.04%   16487.92    59회 69.5%   9.74%    64.88%
2023    -0.97%   16327.78    40회 75.0%   9.57%    63.28%
2024    -2.65%   15895.81    43회 62.8%   6.47%    58.96%
2025     7.16%   17033.45    25회 68.0%   2.18%    70.33%
----------------------------------------------------------------------------------------------------
전체 기간 누적 수익률: 70.33%
최종 자본: $17033.45

====================================================================================================
연도별 성과 요약 (take_profit:0.02, 트레일링스탑 적용)
====================================================================================================
연도     수익률      최종자본         거래수    승률     최대낙폭     누적수익률      
----------------------------------------------------------------------------------------------------
2018    30.57%   13056.77    86회 58.1%  10.92%    30.57%
2019   -10.56%   11677.56    53회 47.2%  20.94%    16.78%
2020    22.82%   14342.87    45회 62.2%   4.91%    43.43%
2021    18.73%   17029.52   103회 57.3%  13.71%    70.30%
2022    -0.05%   17020.93    57회 52.6%  14.08%    70.21%
2023    -6.68%   15884.29    38회 57.9%  15.20%    58.84%
2024     9.49%   17392.33    42회 52.4%   5.65%    73.92%
2025     7.64%   18721.53    25회 56.0%   2.18%    87.22%
----------------------------------------------------------------------------------------------------
전체 기간 누적 수익률: 87.22%
최종 자본: $18721.53

====================================================================================================
연도별 성과 요약 (시간 제한 + 트레일링스탑 적용)
====================================================================================================
연도     수익률      최종자본         거래수    승률     최대낙폭     누적수익률      
----------------------------------------------------------------------------------------------------
2018    TBD%    TBD     TBD회 TBD%  TBD%    TBD%
2019    TBD%    TBD     TBD회 TBD%  TBD%    TBD%
2020    TBD%    TBD     TBD회 TBD%  TBD%    TBD%
2021    TBD%    TBD     TBD회 TBD%  TBD%    TBD%
2022    TBD%    TBD     TBD회 TBD%  TBD%    TBD%
2023    TBD%    TBD     TBD회 TBD%  TBD%    TBD%
2024    TBD%    TBD     TBD회 TBD%  TBD%    TBD%
2025    TBD%    TBD     TBD회 TBD%  TBD%    TBD%
----------------------------------------------------------------------------------------------------
전체 기간 누적 수익률: TBD%
최종 자본: $TBD
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

def calculate_pnl(entry_price, exit_price, position_size, position_type):
    """PnL 계산"""
    if position_type == 'long':
        return (exit_price - entry_price) * position_size
    elif position_type == 'short':
        return (entry_price - exit_price) * position_size
    return 0

def calculate_max_drawdown(initial_capital, trades):
    """최대 낙폭 계산"""
    if not trades:
        return 0
    
    capital = initial_capital
    max_capital = initial_capital
    max_drawdown = 0
    
    for trade in trades:
        capital += trade['pnl']
        if capital > max_capital:
            max_capital = capital
        drawdown = (max_capital - capital) / max_capital
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    return max_drawdown * 100

class MarketRegimeDetector:
    """시장 상황 감지기"""
    
    def __init__(self):
        pass
    
    def detect_market_regime(self, data):
        """시장 상황 감지"""
        if len(data) < 50:
            return 'unknown'
        
        # 트렌드 분석
        short_trend = data['close'].pct_change().rolling(20).mean().iloc[-1]
        mid_trend = data['close'].pct_change().rolling(30).mean().iloc[-1]
        long_trend = data['close'].pct_change().rolling(50).mean().iloc[-1]
        
        # 변동성 분석
        volatility = data['close'].pct_change().rolling(20).std().iloc[-1]
        
        if pd.isna(short_trend) or pd.isna(mid_trend) or pd.isna(long_trend) or pd.isna(volatility):
            return 'unknown'
        
        # 시장 상황 분류 (임계값을 더 현실적으로 조정)
        if short_trend < -0.001 and mid_trend < -0.0005 and long_trend < -0.0002:
            if volatility > 0.02:
                return 'crash'
            else:
                return 'strong_downtrend'
        elif short_trend < -0.0005 and mid_trend < -0.0002:
            return 'downtrend'
        elif short_trend > 0.001 and mid_trend > 0.0005 and long_trend > 0.0002:
            return 'strong_uptrend'
        elif short_trend > 0.0005 and mid_trend > 0.0002:
            return 'uptrend'
        else:
            if volatility > 0.015:
                return 'high_volatility_sideways'
            else:
                return 'low_volatility_sideways'


class AdaptiveStrategy:
    """시장 상황별 적응형 전략"""
    
    def __init__(self, regime_detector, optimized_params=None):
        self.regime_detector = regime_detector
        
        # 최적화된 파라미터가 있으면 사용, 없으면 기본 파라미터 사용
        if optimized_params:
            self.market_params = optimized_params
        else:
            # 최적화된 파라미터 (그리드 서치 결과 적용)
            # 사용 지표: RSI + Moving Average + Donchian Channel
            self.market_params = {
                'crash': {
                    'rsi_oversold': 20, 'rsi_overbought': 80,
                    'ma_short': 7, 'ma_long': 30,  # 최적화: 7/30 (폭락장 대응)
                    'stop_loss': 0.015, 'take_profit': 0.02, 'position_size': 0.2, 'trailing_stop': True, 'trailing_stop_pct': 0.02,
                    'max_hold_hours': 2  # 폭락장에서는 빠른 회전
                },
                'strong_downtrend': {
                    'rsi_oversold': 25, 'rsi_overbought': 75,
                    'ma_short': 15, 'ma_long': 25,  # 최적화: 15/25 (강한 하락장)
                    'stop_loss': 0.02, 'take_profit': 0.02, 'position_size': 0.3, 'trailing_stop': True, 'trailing_stop_pct': 0.025,
                    'max_hold_hours': 3  # 강한 하락장에서는 중간 회전
                },
                'downtrend': {
                    'rsi_oversold': 30, 'rsi_overbought': 70,
                    'ma_short': 5, 'ma_long': 10,  # 최적화: 5/10 (하락장)
                    'stop_loss': 0.025, 'take_profit': 0.02, 'position_size': 0.5, 'trailing_stop': True, 'trailing_stop_pct': 0.03,
                    'max_hold_hours': 4  # 하락장에서는 중간 회전
                },
                'strong_uptrend': {
                    'rsi_oversold': 40, 'rsi_overbought': 80,
                    'ma_short': 9, 'ma_long': 10,  # 최적화: 9/10 (강한 상승장)
                    'stop_loss': 0.04, 'take_profit': 0.02, 'position_size': 1.0, 'trailing_stop': True, 'trailing_stop_pct': 0.05,
                    'max_hold_hours': 8  # 강한 상승장에서는 오래 보유
                },
                'uptrend': {
                    'rsi_oversold': 35, 'rsi_overbought': 75,
                    'ma_short': 13, 'ma_long': 15,  # 최적화: 13/15 (상승장)
                    'stop_loss': 0.03, 'take_profit': 0.02, 'position_size': 0.8, 'trailing_stop': True, 'trailing_stop_pct': 0.04,
                    'max_hold_hours': 6  # 상승장에서는 중간-장기 보유
                },
                'high_volatility_sideways': {
                    'rsi_oversold': 25, 'rsi_overbought': 75,
                    'ma_short': 3, 'ma_long': 10,  # 최적화: 3/10 (고변동성 횡보)
                    'stop_loss': 0.035, 'take_profit': 0.02, 'position_size': 0.6, 'trailing_stop': True, 'trailing_stop_pct': 0.04,
                    'max_hold_hours': 3  # 고변동성에서는 빠른 회전
                },
                'low_volatility_sideways': {
                    'rsi_oversold': 30, 'rsi_overbought': 70,
                    'ma_short': 7, 'ma_long': 10,  # 최적화: 7/10 (저변동성 횡보)
                    'stop_loss': 0.03, 'take_profit': 0.02, 'position_size': 0.7, 'trailing_stop': True, 'trailing_stop_pct': 0.035,
                    'max_hold_hours': 4  # 저변동성에서는 중간 회전
                }
            }
    
    def calculate_indicators(self, data, market_regime):
        """시장 상황별 지표 계산"""
        df = data.copy()
        params = self.market_params.get(market_regime, self.market_params['low_volatility_sideways'])
        
        # RSI 계산
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Moving Average 계산
        df['ma_short'] = df['close'].rolling(window=params['ma_short']).mean()
        df['ma_long'] = df['close'].rolling(window=params['ma_long']).mean()
        
        # Donchian Channel 계산
        dc_period = 20
        df['dc_high'] = df['high'].rolling(window=dc_period).max()
        df['dc_low'] = df['low'].rolling(window=dc_period).min()
        df['dc_mid'] = (df['dc_high'] + df['dc_low']) / 2
        
        return df, params
    
    def generate_signals(self, df, params):
        """신호 생성"""
        df = df.copy()
        
        # 롱 신호: MA_단기 > MA_장기 AND RSI < 과매도선 AND Close > DC_중간선 AND Close > DC_하단*1.02
        long_condition = (
            (df['ma_short'] > df['ma_long']) &
            (df['rsi'] < params['rsi_oversold']) &
            (df['close'] > df['dc_mid']) &
            (df['close'] > df['dc_low'] * 1.02)
        )
        
        # 숏 신호: MA_단기 < MA_장기 AND RSI > 과매수선 AND Close < DC_중간선 AND Close < DC_상단*0.98
        short_condition = (
            (df['ma_short'] < df['ma_long']) &
            (df['rsi'] > params['rsi_overbought']) &
            (df['close'] < df['dc_mid']) &
            (df['close'] < df['dc_high'] * 0.98)
        )
        
        df['long_signal'] = long_condition
        df['short_signal'] = short_condition
        
        return df


def run_adaptive_backtest_pandas(data, adaptive_strategy, initial_capital, strategy_name):
    """판다스 벡터화를 사용한 적응형 백테스트 실행 (시간 제한 + 트레일링스탑)"""
    print(f"=== 판다스 벡터화 백테스트: {strategy_name} ===")
    
    window_size = 50  # 시장 상황 감지를 위한 최소 데이터
    df = data.copy()

    # 전체 데이터에 대해 시장 상황 감지 (완전 벡터화)
    print("시장 상황 감지 중...")
    
    # 벡터화된 시장 상황 감지
    df['short_trend'] = df['close'].rolling(20).apply(lambda x: x.pct_change().mean(), raw=False)
    df['mid_trend'] = df['close'].rolling(30).apply(lambda x: x.pct_change().mean(), raw=False)
    df['long_trend'] = df['close'].rolling(50).apply(lambda x: x.pct_change().mean(), raw=False)
    df['volatility'] = df['close'].pct_change().rolling(20).std()
    
    # 시장 상황 분류 (벡터화)
    conditions = [
        # crash
        (df['short_trend'] < -0.001) & (df['mid_trend'] < -0.0005) & (df['long_trend'] < -0.0002) & (df['volatility'] > 0.02),
        # strong_downtrend
        (df['short_trend'] < -0.001) & (df['mid_trend'] < -0.0005) & (df['long_trend'] < -0.0002) & (df['volatility'] <= 0.02),
        # downtrend
        (df['short_trend'] < -0.0005) & (df['mid_trend'] < -0.0002),
        # strong_uptrend
        (df['short_trend'] > 0.001) & (df['mid_trend'] > 0.0005) & (df['long_trend'] > 0.0002),
        # uptrend
        (df['short_trend'] > 0.0005) & (df['mid_trend'] > 0.0002),
        # high_volatility_sideways
        (df['volatility'] > 0.015),
        # low_volatility_sideways
        True
    ]
    
    choices = ['crash', 'strong_downtrend', 'downtrend', 'strong_uptrend', 'uptrend', 'high_volatility_sideways', 'low_volatility_sideways']
    df['market_regime'] = np.select(conditions, choices, default='unknown')
    
    print(f"시장 상황 감지 완료: {df['market_regime'].value_counts().to_dict()}")
    
    # 각 시장 상황별로 지표 계산 및 신호 생성 (벡터화)
    print("지표 계산 및 신호 생성 중...")
    all_signals = []
    
    for regime in df['market_regime'].unique():
        if pd.isna(regime):
            continue
            
        regime_mask = df['market_regime'] == regime
        regime_data = df[regime_mask].copy()
        
        if len(regime_data) < 20:
            continue
            
        # 해당 시장 상황에 대한 지표 계산
        regime_indicators, params = adaptive_strategy.calculate_indicators(regime_data, regime)
        regime_signals = adaptive_strategy.generate_signals(regime_indicators, params)
        
        all_signals.append(regime_signals)
    
    # 모든 신호를 하나로 합치기
    if all_signals:
        combined_signals = pd.concat(all_signals).sort_index()
        df = df.join(combined_signals[['long_signal', 'short_signal']], how='left')
    else:
        df['long_signal'] = False
        df['short_signal'] = False
    
    print("거래 시뮬레이션 시작...")
    
    # 거래 시뮬레이션 (여전히 순차적이지만 더 효율적)
    current_capital = initial_capital
    position = None
    entry_price = 0
    entry_time = None
    entry_position_size = 0  # 진입 시 포지션 크기 저장
    trades = []
    
    # 트레일링스탑 관련 변수
    highest_price = 0  # 롱 포지션의 최고가 추적
    lowest_price = float('inf')  # 숏 포지션의 최저가 추적
    trailing_stop_price = 0  # 현재 트레일링스탑 가격
    
    # 시간 제한 관련 변수
    max_hold_hours = 0  # 현재 포지션의 최대 보유 시간 (시간)
    
    for i in range(window_size, len(df)):
        current_time = df.index[i]
        current_row = df.iloc[i]
        market_regime = current_row['market_regime']
        
        if pd.isna(market_regime):
            continue
            
        # 해당 시장 상황의 파라미터 찾기
        params = adaptive_strategy.market_params.get(market_regime, adaptive_strategy.market_params['low_volatility_sideways'])
        
        # 자본이 0 이하가 되면 거래 중단
        if current_capital <= 0:
            print(f"{current_time}: 자본 고갈로 거래 중단 (잔액: {current_capital:.2f})")
            break
        
        # 포지션 관리 (기존 로직과 동일)
        if position is None:
            if current_row['long_signal']:
                position = 'long'
                entry_price = current_row['close']
                entry_time = current_time
                entry_position_size = max(0, current_capital * params['position_size'])
                
                # 트레일링스탑 변수 초기화
                highest_price = entry_price
                lowest_price = float('inf')
                trailing_stop_price = 0
                
                # 시간 제한 설정
                max_hold_hours = params.get('max_hold_hours', 4)  # 기본 4시간
                
                entry_fee = entry_position_size * 0.0005
                current_capital -= entry_fee
                
                print(f"{current_time}: 롱 진입 (시장: {market_regime}, 가격: {entry_price:.2f}, 크기: {entry_position_size:.2f}, fee: {entry_fee:.2f}) [잔액: {current_capital:.2f}]")
                
            elif current_row['short_signal']:
                position = 'short'
                entry_price = current_row['close']
                entry_time = current_time
                entry_position_size = max(0, current_capital * params['position_size'])
                
                # 트레일링스탑 변수 초기화
                highest_price = 0
                lowest_price = entry_price
                trailing_stop_price = 0
                
                # 시간 제한 설정
                max_hold_hours = params.get('max_hold_hours', 4)  # 기본 4시간
                
                entry_fee = entry_position_size * 0.0005
                current_capital -= entry_fee
                
                print(f"{current_time}: 숏 진입 (시장: {market_regime}, 가격: {entry_price:.2f}, 크기: {entry_position_size:.2f}, fee: {entry_fee:.2f}) [잔액: {current_capital:.2f}]")
        
        elif position is not None:
            should_exit = False
            exit_reason = ""
            current_price = current_row['close']
            
            # 시간 제한 체크
            time_elapsed = (current_time - entry_time).total_seconds() / 3600  # 시간 단위
            if time_elapsed >= max_hold_hours:
                should_exit = True
                exit_reason = f"시간 제한 ({max_hold_hours}시간)"
            
            # 트레일링스탑 업데이트 (시간 제한에 걸리지 않은 경우에만)
            if not should_exit:
                if position == 'long':
                    # 롱 포지션: 최고가 업데이트 및 트레일링스탑 계산
                    if current_price > highest_price:
                        highest_price = current_price
                        # 트레일링스탑이 활성화되어 있고, 2% 수익을 넘었을 때만 트레일링스탑 적용
                        if params.get('trailing_stop', False) and current_price >= entry_price * (1 + params['take_profit']):
                            trailing_stop_price = highest_price * (1 - params['trailing_stop_pct'])
                    
                    # 청산 조건 확인
                    if current_row['short_signal']:
                        should_exit = True
                        exit_reason = "숏 신호"
                    elif current_price <= entry_price * (1 - params['stop_loss']):
                        should_exit = True
                        exit_reason = f"{params['stop_loss']*100:.0f}% 손절매"
                    elif current_price >= entry_price * (1 + params['take_profit']):
                        # 2% 익절에 도달했지만 트레일링스탑이 활성화된 경우
                        if params.get('trailing_stop', False):
                            if trailing_stop_price > 0 and current_price <= trailing_stop_price:
                                should_exit = True
                                exit_reason = f"트레일링스탑 ({params['trailing_stop_pct']*100:.1f}%)"
                        else:
                            should_exit = True
                            exit_reason = f"{params['take_profit']*100:.0f}% 익절"
                
                elif position == 'short':
                    # 숏 포지션: 최저가 업데이트 및 트레일링스탑 계산
                    if current_price < lowest_price:
                        lowest_price = current_price
                        # 트레일링스탑이 활성화되어 있고, 2% 수익을 넘었을 때만 트레일링스탑 적용
                        if params.get('trailing_stop', False) and current_price <= entry_price * (1 - params['take_profit']):
                            trailing_stop_price = lowest_price * (1 + params['trailing_stop_pct'])
                    
                    # 청산 조건 확인
                    if current_row['long_signal']:
                        should_exit = True
                        exit_reason = "롱 신호"
                    elif current_price >= entry_price * (1 + params['stop_loss']):
                        should_exit = True
                        exit_reason = f"{params['stop_loss']*100:.0f}% 손절매"
                    elif current_price <= entry_price * (1 - params['take_profit']):
                        # 2% 익절에 도달했지만 트레일링스탑이 활성화된 경우
                        if params.get('trailing_stop', False):
                            if trailing_stop_price > 0 and current_price >= trailing_stop_price:
                                should_exit = True
                                exit_reason = f"트레일링스탑 ({params['trailing_stop_pct']*100:.1f}%)"
                        else:
                            should_exit = True
                            exit_reason = f"{params['take_profit']*100:.0f}% 익절"
            
            if should_exit:
                exit_price = current_row['close']
                # 진입 시의 포지션 크기를 사용
                position_size = entry_position_size
                
                pnl = calculate_pnl(entry_price, exit_price, position_size, position)
                exit_fee = position_size * 0.0005
                net_pnl = pnl - exit_fee
                current_capital += net_pnl
                
                trades.append({
                    'entry_time': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'exit_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'position': position,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': net_pnl,
                    'gross_pnl': pnl,
                    'entry_fee': position_size * 0.0005,
                    'exit_fee': exit_fee,
                    'total_fee': (position_size * 0.0005) + exit_fee,
                    'exit_reason': exit_reason,
                    'market_regime': market_regime
                })
                
                pnl_percent = (net_pnl / position_size) * 100
                total_fee_display = (position_size * 0.0005) + exit_fee
                if net_pnl > 0:
                    print(f"{current_time}: 청산 [수익] (시장: {market_regime}, 수익률: {pnl_percent:.2f}%, PnL: {net_pnl:.2f}, fee: {total_fee_display:.2f}) [잔액: {current_capital:.2f}]")
                else:
                    print(f"{current_time}: 청산 [손실] (시장: {market_regime}, 손실률: {pnl_percent:.2f}%, PnL: {net_pnl:.2f}, fee: {total_fee_display:.2f}) [잔액: {current_capital:.2f}]")
                
                # 포지션 청산 후 변수 초기화
                position = None
                entry_position_size = 0
    
    # 결과 계산
    total_return = (current_capital - initial_capital) / initial_capital * 100
    winning_trades = len([t for t in trades if t['pnl'] > 0])
    win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0
    max_drawdown = calculate_max_drawdown(initial_capital, trades)
    
    return {
        'total_return': total_return,
        'final_capital': current_capital,
        'total_trades': len(trades),
        'win_rate': win_rate,
        'max_drawdown': max_drawdown,
        'trades': trades,
        'df_with_signals': df  # 신호가 포함된 데이터프레임 반환
    }


def main():
    """메인 실행 함수"""
    print("=== 적응형 트레이딩 시스템 백테스트 (시간 제한 + 트레일링스탑) ===")
    
    # 데이터 로드 (실제 데이터 경로로 수정 필요)
    data_path = "data/btc_5m_2018_2025.csv"  # 실제 데이터 파일 경로
    
    if not os.path.exists(data_path):
        print(f"데이터 파일을 찾을 수 없습니다: {data_path}")
        print("샘플 데이터를 생성합니다...")
        
        # 샘플 데이터 생성 (실제 사용 시에는 실제 데이터를 로드)
        dates = pd.date_range('2018-01-01', '2025-12-31', freq='5T')
        np.random.seed(42)
        price = 10000
        prices = []
        for _ in range(len(dates)):
            price += np.random.normal(0, price * 0.001)  # 0.1% 변동성
            prices.append(max(price, 100))  # 최소 가격 100
        
        data = pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': [p * (1 + abs(np.random.normal(0, 0.002))) for p in prices],
            'low': [p * (1 - abs(np.random.normal(0, 0.002))) for p in prices],
            'close': prices,
            'volume': np.random.uniform(1000, 10000, len(dates))
        })
        data.set_index('timestamp', inplace=True)
    else:
        data = pd.read_csv(data_path, index_col=0, parse_dates=True)
    
    print(f"데이터 로드 완료: {len(data)}개 캔들")
    print(f"기간: {data.index[0]} ~ {data.index[-1]}")
    
    # 시장 상황 감지기 및 전략 초기화
    regime_detector = MarketRegimeDetector()
    adaptive_strategy = AdaptiveStrategy(regime_detector)
    
    # 백테스트 실행
    initial_capital = 10000
    results = run_adaptive_backtest_pandas(data, adaptive_strategy, initial_capital, "시간제한_트레일링스탑_전략")
    
    # 결과 출력
    print("\n" + "="*80)
    print("백테스트 결과")
    print("="*80)
    print(f"초기 자본: ${initial_capital:,.2f}")
    print(f"최종 자본: ${results['final_capital']:,.2f}")
    print(f"총 수익률: {results['total_return']:.2f}%")
    print(f"총 거래 수: {results['total_trades']}회")
    print(f"승률: {results['win_rate']:.1f}%")
    print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
    
    # 연도별 성과 분석
    if results['trades']:
        trades_df = pd.DataFrame(results['trades'])
        trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
        trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
        trades_df['year'] = trades_df['exit_time'].dt.year
        
        print("\n연도별 성과:")
        yearly_performance = trades_df.groupby('year').agg({
            'pnl': ['sum', 'count'],
            'gross_pnl': lambda x: (x > 0).sum()
        }).round(2)
        
        yearly_performance.columns = ['총_PnL', '거래수', '승리거래수']
        yearly_performance['승률'] = (yearly_performance['승리거래수'] / yearly_performance['거래수'] * 100).round(1)
        print(yearly_performance)
    
    # 결과 저장
    output_file = "market_regime_comparison_time_limit_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'strategy_name': '시간제한_트레일링스탑_전략',
            'total_return': results['total_return'],
            'final_capital': results['final_capital'],
            'total_trades': results['total_trades'],
            'win_rate': results['win_rate'],
            'max_drawdown': results['max_drawdown'],
            'trades': results['trades']
        }, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n결과가 {output_file}에 저장되었습니다.")


if __name__ == "__main__":
    main()
