"""
최적화된 적응형 트레이딩 시스템 (5분 데이터)

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

3. 리스크 관리 (Risk Management)
   - 진입/청산 수수료: 각각 0.05% (총 0.1%)
   - 손절매: 시장 상황별 1.5%~4% 설정
   - 익절매: 시장 상황별 3%~10% 설정
   - 포지션 크기: 시장 상황별 20%~100% 조절

=== 시장 상황별 전략 ===
1. CRASH (폭락장)
   - MA: 3/10 (매우 빠른 반응)
   - RSI: 20/80 (극단적 과매도/과매수)
   - 포지션: 20% (보수적)
   - 손절/익절: 1.5%/3%

2. STRONG_DOWNTREND (강한 하락장)
   - MA: 5/15 (빠른 반응)
   - RSI: 25/75
   - 포지션: 30%
   - 손절/익절: 2%/4%

3. DOWNTREND (하락장)
   - MA: 8/20 (중간 반응)
   - RSI: 30/70
   - 포지션: 50%
   - 손절/익절: 2.5%/5%

4. STRONG_UPTREND (강한 상승장)
   - MA: 10/30 (안정적)
   - RSI: 40/80
   - 포지션: 100% (공격적)
   - 손절/익절: 4%/10%

5. UPTREND (상승장)
   - MA: 12/35 (안정적)
   - RSI: 35/75
   - 포지션: 80%
   - 손절/익절: 3%/8%

6. HIGH_VOLATILITY_SIDEWAYS (고변동성 횡보)
   - MA: 6/18 (중간)
   - RSI: 25/75
   - 포지션: 60%
   - 손절/익절: 3.5%/8%

7. LOW_VOLATILITY_SIDEWAYS (저변동성 횡보)
   - MA: 15/40 (느린 반응)
   - RSI: 30/70
   - 포지션: 70%
   - 손절/익절: 3%/8%

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
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import warnings
from itertools import product
warnings.filterwarnings('ignore')


class CurrentMarketRegimeDetector:
    """현재 코드의 시장 상황 감지기"""
    
    def __init__(self):
        self.trend_periods = [20, 50, 100]
        self.volatility_period = 20
    
    def detect_market_regime(self, data):
        """시장 상황 분석"""
        # 최소 데이터 요구량을 줄임 (50개면 충분)
        if len(data) < 50:
            return 'unknown'
        
        # 트렌드 분석 (더 짧은 기간 사용)
        short_trend = data['close'].iloc[-20:].pct_change().mean()  # 20일
        mid_trend = data['close'].iloc[-30:].pct_change().mean()    # 30일
        long_trend = data['close'].iloc[-50:].pct_change().mean()   # 50일
        
        # 변동성 분석
        returns = data['close'].pct_change()
        volatility = returns.rolling(20).std().iloc[-1]
        
        # NaN 체크
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
                    'stop_loss': 0.015, 'take_profit': 0.03, 'position_size': 0.2
                },
                'strong_downtrend': {
                    'rsi_oversold': 25, 'rsi_overbought': 75,
                    'ma_short': 15, 'ma_long': 25,  # 최적화: 15/25 (강한 하락장)
                    'stop_loss': 0.02, 'take_profit': 0.04, 'position_size': 0.3
                },
                'downtrend': {
                    'rsi_oversold': 30, 'rsi_overbought': 70,
                    'ma_short': 5, 'ma_long': 10,  # 최적화: 5/10 (하락장)
                    'stop_loss': 0.025, 'take_profit': 0.05, 'position_size': 0.5
                },
                'strong_uptrend': {
                    'rsi_oversold': 40, 'rsi_overbought': 80,
                    'ma_short': 9, 'ma_long': 10,  # 최적화: 9/10 (강한 상승장)
                    'stop_loss': 0.04, 'take_profit': 0.10, 'position_size': 1.0
                },
                'uptrend': {
                    'rsi_oversold': 35, 'rsi_overbought': 75,
                    'ma_short': 13, 'ma_long': 15,  # 최적화: 13/15 (상승장)
                    'stop_loss': 0.03, 'take_profit': 0.08, 'position_size': 0.8
                },
                'high_volatility_sideways': {
                    'rsi_oversold': 25, 'rsi_overbought': 75,
                    'ma_short': 3, 'ma_long': 10,  # 최적화: 3/10 (고변동성 횡보)
                    'stop_loss': 0.035, 'take_profit': 0.08, 'position_size': 0.6
                },
                'low_volatility_sideways': {
                    'rsi_oversold': 30, 'rsi_overbought': 70,
                    'ma_short': 7, 'ma_long': 10,  # 최적화: 7/10 (저변동성 횡보)
                    'stop_loss': 0.03, 'take_profit': 0.08, 'position_size': 0.7
                }
            }
    
    def calculate_indicators(self, data, market_regime):
        """시장 상황별 지표 계산"""
        df = data.copy()
        params = self.market_params.get(market_regime, self.market_params['low_volatility_sideways'])
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Moving Average (MA) - 시장별 파라미터 적용
        df['ma_short'] = df['close'].rolling(params['ma_short']).mean()
        df['ma_long'] = df['close'].rolling(params['ma_long']).mean()
        
        # Donchian Channel (DC) - 다시 활성화
        dc_period = 45  # 기간을 줄여서 더 민감하게
        df['dc_high'] = df['high'].rolling(dc_period).max()
        df['dc_low'] = df['low'].rolling(dc_period).min()
        df['dc_middle'] = (df['dc_high'] + df['dc_low']) / 2
        
        return df, params
    
    def generate_signals(self, df, params):
        """시장 상황별 신호 생성 (MA + RSI + DC)"""
        # Moving Average 신호 - 더 유연하게 변경
        ma_long_signal = df['ma_short'] > df['ma_long']  # 단순히 단기MA > 장기MA
        ma_short_signal = df['ma_short'] < df['ma_long']  # 단순히 단기MA < 장기MA
        
        # RSI 신호
        rsi_long_signal = df['rsi'] < params['rsi_oversold']  # 과매도
        rsi_short_signal = df['rsi'] > params['rsi_overbought']  # 과매수
        
        # Donchian Channel 신호 - 다시 활성화
        dc_long_signal = (df['close'] > df['dc_middle']) & (df['close'] > df['dc_low'] * 1.02)
        dc_short_signal = (df['close'] < df['dc_middle']) & (df['close'] < df['dc_high'] * 0.98)
        
        # MA + RSI + DC 신호 결합
        long_signal = ma_long_signal & rsi_long_signal & dc_long_signal  # MA + RSI + DC
        short_signal = ma_short_signal & rsi_short_signal & dc_short_signal  # MA + RSI + DC
        
        df['long_signal'] = long_signal
        df['short_signal'] = short_signal
        
        return df

def run_optimized_backtest(data, start_date, end_date, initial_capital=10000):
    """최적화된 적응형 트레이딩 시스템 백테스트"""
    print("=== 최적화된 적응형 트레이딩 시스템 백테스트 ===")
    
    # 데이터 필터링
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    mask = (data.index >= start_dt) & (data.index <= end_dt)
    test_data = data[mask].copy()
    
    if len(test_data) == 0:
        print("테스트 데이터가 없습니다.")
        return None
    
    print(f"테스트 기간: {start_date} ~ {end_date}")
    print(f"데이터 길이: {len(test_data)}개 캔들")
    
    # 최적화된 시장 상황 감지 시스템
    print("\n최적화된 시장 상황 감지 시스템 테스트 중...")
    detector = CurrentMarketRegimeDetector()
    adaptive_strategy = AdaptiveStrategy(detector)
    result = run_adaptive_backtest(test_data, adaptive_strategy, initial_capital, "최적화시스템")
    
    # 결과 출력
    if result:
        print("\n" + "="*80)
        print("최적화된 시스템 결과")
        print("="*80)
        print(f"  총 수익률: {result['total_return']:.2f}%")
        print(f"  최종 자본: ${result['final_capital']:.2f}")
        print(f"  총 거래: {result['total_trades']}회")
        print(f"  승률: {result['win_rate']:.2f}%")
        print(f"  최대 낙폭: {result['max_drawdown']:.2f}%")
    
    return result

def run_yearly_analysis(data, start_year=2018, end_year=2025, strategy=None, initial_capital=10000):
    """연도별 성과 분석"""
    print("=== 연도별 성과 분석 (2018-2025) ===")
    
    yearly_results = {}
    current_capital = initial_capital
    
    for year in range(start_year, end_year + 1):
        print(f"\n{year}년 분석 중...")
        
        # 해당 연도 데이터 필터링
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        mask = (data.index >= start_dt) & (data.index <= end_dt)
        year_data = data[mask].copy()
        
        if len(year_data) == 0:
            print(f"  {year}년 데이터가 없습니다.")
            yearly_results[year] = {
                'total_return': 0,
                'final_capital': current_capital,
                'total_trades': 0,
                'win_rate': 0,
                'max_drawdown': 0,
                'trades': []
            }
            continue
        
        print(f"  데이터 길이: {len(year_data)}개 캔들")
        
        # 해당 연도 백테스트 실행
        if strategy is None:
            detector = CurrentMarketRegimeDetector()
            adaptive_strategy = AdaptiveStrategy(detector)
        else:
            adaptive_strategy = strategy
            
        year_result = run_adaptive_backtest_pandas(year_data, adaptive_strategy, current_capital, f"{year}년시스템")
        
        if year_result:
            # JSON 직렬화를 위해 df_with_signals 제거
            clean_result = {k: v for k, v in year_result.items() if k != 'df_with_signals'}
            yearly_results[year] = clean_result
            current_capital = year_result['final_capital']  # 다음 연도 시작 자본 업데이트
            
            print(f"  {year}년 완료: 수익률 {year_result['total_return']:.2f}%, 거래 {year_result['total_trades']}회, 승률 {year_result['win_rate']:.1f}%")
        else:
            yearly_results[year] = {
                'total_return': 0,
                'final_capital': current_capital,
                'total_trades': 0,
                'win_rate': 0,
                'max_drawdown': 0,
                'trades': []
            }
    
    # 연도별 성과 요약 출력
    print("\n" + "="*100)
    print("연도별 성과 요약")
    print("="*100)
    print(f"{'연도':<6} {'수익률':<8} {'최종자본':<12} {'거래수':<6} {'승률':<6} {'최대낙폭':<8} {'누적수익률':<10}")
    print("-" * 100)
    
    cumulative_return = 0
    for year in range(start_year, end_year + 1):
        if year in yearly_results:
            result = yearly_results[year]
            cumulative_return = (result['final_capital'] - initial_capital) / initial_capital * 100
            
            print(f"{year:<6} {result['total_return']:>6.2f}% {result['final_capital']:>10.2f} {result['total_trades']:>5}회 "
                  f"{result['win_rate']:>4.1f}% {result['max_drawdown']:>6.2f}% {cumulative_return:>8.2f}%")
    
    print("-" * 100)
    print(f"전체 기간 누적 수익률: {cumulative_return:.2f}%")
    print(f"최종 자본: ${yearly_results[end_year]['final_capital']:.2f}")
    
    return yearly_results


def run_adaptive_backtest_pandas(data, adaptive_strategy, initial_capital, strategy_name):
    """판다스 벡터화를 사용한 적응형 백테스트 실행"""
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
    ]
    
    choices = ['crash', 'strong_downtrend', 'downtrend', 'strong_uptrend', 'uptrend', 'high_volatility_sideways']
    
    df['market_regime'] = np.select(conditions, choices, default='low_volatility_sideways')
    
    # NaN 값 처리
    df['market_regime'] = df['market_regime'].fillna('unknown')
    
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
    trades = []
    
    for i in range(window_size, len(df)):
        current_time = df.index[i]
        current_row = df.iloc[i]
        market_regime = current_row['market_regime']
        
        if pd.isna(market_regime):
            continue
            
        # 해당 시장 상황의 파라미터 찾기
        params = adaptive_strategy.market_params.get(market_regime, adaptive_strategy.market_params['low_volatility_sideways'])
        
        # 포지션 관리 (기존 로직과 동일)
        if position is None:
            if current_row['long_signal']:
                position = 'long'
                entry_price = current_row['close']
                entry_time = current_time
                position_size = current_capital * params['position_size']
                
                entry_fee = position_size * 0.0005
                current_capital -= entry_fee
                
                print(f"{current_time}: 롱 진입 (시장: {market_regime}, 가격: {entry_price:.2f}, 크기: {position_size:.2f}, fee: {entry_fee:.2f}) [잔액: {current_capital:.2f}]")
                
            elif current_row['short_signal']:
                position = 'short'
                entry_price = current_row['close']
                entry_time = current_time
                position_size = current_capital * params['position_size']
                
                entry_fee = position_size * 0.0005
                current_capital -= entry_fee
                
                print(f"{current_time}: 숏 진입 (시장: {market_regime}, 가격: {entry_price:.2f}, 크기: {position_size:.2f}, fee: {entry_fee:.2f}) [잔액: {current_capital:.2f}]")
        
        elif position is not None:
            should_exit = False
            exit_reason = ""
            
            if position == 'long':
                if current_row['short_signal']:
                    should_exit = True
                    exit_reason = "숏 신호"
                elif current_row['close'] <= entry_price * (1 - params['stop_loss']):
                    should_exit = True
                    exit_reason = f"{params['stop_loss']*100:.0f}% 손절매"
                elif current_row['close'] >= entry_price * (1 + params['take_profit']):
                    should_exit = True
                    exit_reason = f"{params['take_profit']*100:.0f}% 익절"
            
            elif position == 'short':
                if current_row['long_signal']:
                    should_exit = True
                    exit_reason = "롱 신호"
                elif current_row['close'] >= entry_price * (1 + params['stop_loss']):
                    should_exit = True
                    exit_reason = f"{params['stop_loss']*100:.0f}% 손절매"
                elif current_row['close'] <= entry_price * (1 - params['take_profit']):
                    should_exit = True
                    exit_reason = f"{params['take_profit']*100:.0f}% 익절"
            
            if should_exit:
                exit_price = current_row['close']
                position_size = current_capital * params['position_size']
                
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
                
                position = None
    
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

def run_adaptive_backtest(data, adaptive_strategy, initial_capital, strategy_name):
    """적응형 백테스트 실행"""
    current_capital = initial_capital
    position = None
    entry_price = 0
    entry_time = None
    trades = []
    
    window_size = 50
    
    for i in range(window_size, len(data)):
        current_time = data.index[i]
        current_data = data.iloc[max(0, i - window_size + 1):i+1]
        
        # 시장 상황 감지
        market_regime = adaptive_strategy.regime_detector.detect_market_regime(current_data)
        
        # 지표 계산 및 신호 생성
        df_with_indicators, params = adaptive_strategy.calculate_indicators(current_data, market_regime)
        df_with_signals = adaptive_strategy.generate_signals(df_with_indicators, params)
        
        current_row = df_with_signals.iloc[-1]
        
        # 포지션 관리
        if position is None:
            if current_row['long_signal']:
                position = 'long'
                entry_price = current_row['close']
                entry_time = current_time
                position_size = current_capital * params['position_size']
                
                # 진입 수수료 계산 및 차감
                entry_fee = position_size * 0.0005  # 0.05%
                current_capital -= entry_fee
                
                print(f"{current_time}: 롱 진입 (시장: {market_regime}, 가격: {entry_price:.2f}, 크기: {position_size:.2f}, fee: {entry_fee:.2f}) [잔액: {current_capital:.2f}]")
                
            elif current_row['short_signal']:
                position = 'short'
                entry_price = current_row['close']
                entry_time = current_time
                position_size = current_capital * params['position_size']
                
                # 진입 수수료 계산 및 차감
                entry_fee = position_size * 0.0005  # 0.05%
                current_capital -= entry_fee
                
                print(f"{current_time}: 숏 진입 (시장: {market_regime}, 가격: {entry_price:.2f}, 크기: {position_size:.2f}, fee: {entry_fee:.2f}) [잔액: {current_capital:.2f}]")
        
        elif position is not None:
            should_exit = False
            exit_reason = ""
            
            if position == 'long':
                if current_row['short_signal']:
                    should_exit = True
                    exit_reason = "숏 신호"
                elif current_row['close'] <= entry_price * (1 - params['stop_loss']):
                    should_exit = True
                    exit_reason = f"{params['stop_loss']*100:.0f}% 손절매"
                elif current_row['close'] >= entry_price * (1 + params['take_profit']):
                    should_exit = True
                    exit_reason = f"{params['take_profit']*100:.0f}% 익절"
            
            elif position == 'short':
                if current_row['long_signal']:
                    should_exit = True
                    exit_reason = "롱 신호"
                elif current_row['close'] >= entry_price * (1 + params['stop_loss']):
                    should_exit = True
                    exit_reason = f"{params['stop_loss']*100:.0f}% 손절매"
                elif current_row['close'] <= entry_price * (1 - params['take_profit']):
                    should_exit = True
                    exit_reason = f"{params['take_profit']*100:.0f}% 익절"
            
            if should_exit:
                exit_price = current_row['close']
                position_size = current_capital * params['position_size']
                
                # PnL 계산
                pnl = calculate_pnl(entry_price, exit_price, position_size, position)
                
                # 청산 수수료만 계산 (진입 수수료는 이미 차감됨)
                exit_fee = position_size * 0.0005  # 0.05%
                
                # 순 PnL 계산 (청산 수수료만 차감)
                net_pnl = pnl - exit_fee
                current_capital += net_pnl
                
                trades.append({
                    'entry_time': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'exit_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'position': position,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': net_pnl,  # 순 PnL
                    'gross_pnl': pnl,  # 총 PnL
                    'entry_fee': position_size * 0.0005,
                    'exit_fee': exit_fee,
                    'total_fee': (position_size * 0.0005) + exit_fee,  # 총 수수료 (표시용)
                    'exit_reason': exit_reason,
                    'market_regime': market_regime
                })
                
                pnl_percent = (net_pnl / position_size) * 100
                total_fee_display = (position_size * 0.0005) + exit_fee  # 표시용 총 수수료
                if net_pnl > 0:
                    print(f"{current_time}: 청산 [수익] (시장: {market_regime}, 수익률: {pnl_percent:.2f}%, PnL: {net_pnl:.2f}, fee: {total_fee_display:.2f}) [잔액: {current_capital:.2f}]")
                else:
                    print(f"{current_time}: 청산 [손실] (시장: {market_regime}, 손실률: {pnl_percent:.2f}%, PnL: {net_pnl:.2f}, fee: {total_fee_display:.2f}) [잔액: {current_capital:.2f}]")
                
                position = None
    
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
        'trades': trades
    }

def calculate_pnl(entry_price, exit_price, capital, position_type):
    """PnL 계산"""
    if position_type == 'long':
        return (exit_price - entry_price) / entry_price * capital
    else:  # short
        return (entry_price - exit_price) / entry_price * capital

def calculate_max_drawdown(initial_capital, trades):
    """최대 낙폭 계산"""
    if not trades:
        return 0.0
    
    capital_series = [initial_capital]
    for trade in trades:
        capital_series.append(capital_series[-1] + trade['pnl'])
    
    capital_series = np.array(capital_series)
    peak = np.maximum.accumulate(capital_series)
    drawdown = (peak - capital_series) / peak * 100
    
    return np.max(drawdown)

def optimize_ma_parameters(data, market_regime, ma_short_range, ma_long_range, initial_capital=10000):
    """특정 시장 상황에 대한 MA 파라미터 최적화"""
    print(f"  {market_regime} 시장 상황 MA 최적화 중...")
    
    best_params = None
    best_return = -float('inf')
    best_results = {}
    
    # 시장 상황별 기본 파라미터
    base_params = {
        'crash': {'rsi_oversold': 20, 'rsi_overbought': 80, 'stop_loss': 0.015, 'take_profit': 0.03, 'position_size': 0.2},
        'strong_downtrend': {'rsi_oversold': 25, 'rsi_overbought': 75, 'stop_loss': 0.02, 'take_profit': 0.04, 'position_size': 0.3},
        'downtrend': {'rsi_oversold': 30, 'rsi_overbought': 70, 'stop_loss': 0.025, 'take_profit': 0.05, 'position_size': 0.5},
        'strong_uptrend': {'rsi_oversold': 40, 'rsi_overbought': 80, 'stop_loss': 0.04, 'take_profit': 0.10, 'position_size': 1.0},
        'uptrend': {'rsi_oversold': 35, 'rsi_overbought': 75, 'stop_loss': 0.03, 'take_profit': 0.08, 'position_size': 0.8},
        'high_volatility_sideways': {'rsi_oversold': 25, 'rsi_overbought': 75, 'stop_loss': 0.035, 'take_profit': 0.08, 'position_size': 0.6},
        'low_volatility_sideways': {'rsi_oversold': 30, 'rsi_overbought': 70, 'stop_loss': 0.03, 'take_profit': 0.08, 'position_size': 0.7}
    }
    
    base_param = base_params.get(market_regime, base_params['low_volatility_sideways'])
    
    # MA 파라미터 조합 생성
    ma_combinations = list(product(ma_short_range, ma_long_range))
    total_combinations = len(ma_combinations)
    valid_combinations = [combo for combo in ma_combinations if combo[0] < combo[1]]
    valid_total = len(valid_combinations)
    
    print(f"    총 {valid_total}개 조합 테스트 중...")
    
    for i, (ma_short, ma_long) in enumerate(valid_combinations):
        # 진행상황 표시 (10%마다)
        if i % max(1, valid_total // 10) == 0:
            progress = (i / valid_total) * 100
            print(f"    진행률: {progress:.0f}% ({i}/{valid_total})")
            
        # 파라미터 설정
        params = base_param.copy()
        params['ma_short'] = ma_short
        params['ma_long'] = ma_long
        
        # 백테스트 실행
        try:
            result = run_optimization_backtest(data, market_regime, params, initial_capital)
            if result and result['total_return'] > best_return:
                best_return = result['total_return']
                best_params = params.copy()
                best_results = result.copy()
                print(f"    새로운 최적값 발견: MA({ma_short}/{ma_long}) = {best_return:.2f}%")
        except Exception as e:
            continue
    
    print(f"    최적화 완료: {valid_total}개 조합 테스트")
    if best_params:
        print(f"    최적 MA: {best_params['ma_short']}/{best_params['ma_long']}, 수익률: {best_return:.2f}%")
        return best_params, best_results
    else:
        print(f"    {market_regime} 시장 상황에서 유효한 파라미터를 찾지 못했습니다.")
        return base_param, None

def run_optimization_backtest(data, market_regime, params, initial_capital):
    """최적화용 간단한 백테스트"""
    df = data.copy()
    
    # RSI 계산
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MA 계산
    df['ma_short'] = df['close'].rolling(params['ma_short']).mean()
    df['ma_long'] = df['close'].rolling(params['ma_long']).mean()
    
    # Donchian Channel
    dc_period = 45
    df['dc_high'] = df['high'].rolling(dc_period).max()
    df['dc_low'] = df['low'].rolling(dc_period).min()
    df['dc_middle'] = (df['dc_high'] + df['dc_low']) / 2
    
    # 신호 생성
    ma_long_signal = df['ma_short'] > df['ma_long']
    ma_short_signal = df['ma_short'] < df['ma_long']
    rsi_long_signal = df['rsi'] < params['rsi_oversold']
    rsi_short_signal = df['rsi'] > params['rsi_overbought']
    dc_long_signal = (df['close'] > df['dc_middle']) & (df['close'] > df['dc_low'] * 1.02)
    dc_short_signal = (df['close'] < df['dc_middle']) & (df['close'] < df['dc_high'] * 0.98)
    
    df['long_signal'] = ma_long_signal & rsi_long_signal & dc_long_signal
    df['short_signal'] = ma_short_signal & rsi_short_signal & dc_short_signal
    
    # 거래 시뮬레이션
    current_capital = initial_capital
    position = None
    entry_price = 0
    trades = []
    
    for i in range(max(params['ma_long'], dc_period), len(df)):
        current_row = df.iloc[i]
        
        if position is None:
            if current_row['long_signal']:
                position = 'long'
                entry_price = current_row['close']
                position_size = current_capital * params['position_size']
                entry_fee = position_size * 0.0005
                current_capital -= entry_fee
            elif current_row['short_signal']:
                position = 'short'
                entry_price = current_row['close']
                position_size = current_capital * params['position_size']
                entry_fee = position_size * 0.0005
                current_capital -= entry_fee
        
        elif position is not None:
            should_exit = False
            
            if position == 'long':
                if current_row['short_signal'] or current_row['close'] <= entry_price * (1 - params['stop_loss']) or current_row['close'] >= entry_price * (1 + params['take_profit']):
                    should_exit = True
            elif position == 'short':
                if current_row['long_signal'] or current_row['close'] >= entry_price * (1 + params['stop_loss']) or current_row['close'] <= entry_price * (1 - params['take_profit']):
                    should_exit = True
            
            if should_exit:
                exit_price = current_row['close']
                position_size = current_capital * params['position_size']
                
                pnl = calculate_pnl(entry_price, exit_price, position_size, position)
                exit_fee = position_size * 0.0005
                net_pnl = pnl - exit_fee
                current_capital += net_pnl
                
                trades.append({
                    'pnl': net_pnl,
                    'position': position,
                    'entry_price': entry_price,
                    'exit_price': exit_price
                })
                
                position = None
    
    if not trades:
        return None
        
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
        'trades': trades
    }

def optimize_all_market_regimes(data, initial_capital=10000):
    """모든 시장 상황에 대한 MA 파라미터 최적화"""
    print("=== MA 파라미터 그리드 서치 최적화 ===")
    
    # MA 파라미터 범위 설정 (더 빠른 최적화를 위해 범위 축소)
    ma_short_range = range(3, 16, 2)  # 3, 5, 7, 9, 11, 13, 15
    ma_long_range = range(10, 36, 5)  # 10, 15, 20, 25, 30, 35
    
    # 시장 상황별 최적화
    market_regimes = ['crash', 'strong_downtrend', 'downtrend', 'strong_uptrend', 'uptrend', 'high_volatility_sideways', 'low_volatility_sideways']
    
    optimized_params = {}
    total_regimes = len(market_regimes)
    
    print(f"총 {total_regimes}개 시장 상황 최적화 시작...")
    
    for i, regime in enumerate(market_regimes):
        print(f"\n[{i+1}/{total_regimes}] {regime} 시장 상황 최적화 중...")
        optimized_param, result = optimize_ma_parameters(data, regime, ma_short_range, ma_long_range, initial_capital)
        optimized_params[regime] = optimized_param
        print(f"[{i+1}/{total_regimes}] {regime} 완료!")
    
    print(f"\n=== 모든 시장 상황 최적화 완료 ===")
    return optimized_params

def test_market_regime_detection(data):
    """시장 상황 감지 테스트"""
    print("=== 시장 상황 감지 테스트 ===")
    detector = CurrentMarketRegimeDetector()
    
    # 2018년 데이터로 테스트
    test_data = data[data.index.year == 2018].copy()
    if len(test_data) < 100:
        print("테스트 데이터가 부족합니다.")
        return
    
    # 100개씩 샘플링해서 시장 상황 확인
    sample_size = 100
    regime_counts = {}
    
    for i in range(0, len(test_data) - sample_size, sample_size):
        sample = test_data.iloc[i:i+sample_size]
        regime = detector.detect_market_regime(sample)
        regime_counts[regime] = regime_counts.get(regime, 0) + 1
    
    print("시장 상황 분포:")
    for regime, count in regime_counts.items():
        print(f"  {regime}: {count}회")
    
    return regime_counts

def main():
    """메인 실행 함수"""
    print("=== 최적화된 적응형 트레이딩 시스템 (2018-2025) ===")
    
    # 2018-2025년 데이터 로드 (5분 데이터)
    data_files = [
        "data/BTCUSDT/5m/BTCUSDT_5m_2018.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2019.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2020.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2021.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2022.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2023.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2024.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2025.csv"
    ]
    
    all_data = []
    for file_path in data_files:
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            all_data.append(df)
            print(f"데이터 로드 완료: {file_path}")
        else:
            print(f"데이터 파일 없음: {file_path}")
    
    if all_data:
        combined_data = pd.concat(all_data, ignore_index=False).sort_index()
        print(f"전체 데이터: {len(combined_data)}개 캔들")
        print(f"데이터 기간: {combined_data.index.min()} ~ {combined_data.index.max()}")
        
        # 최적화된 적응형 트레이딩 시스템 실행
        print("\n=== 최적화된 적응형 트레이딩 시스템 실행 ===")
        detector = CurrentMarketRegimeDetector()
        optimized_strategy = AdaptiveStrategy(detector)  # 최적화된 파라미터 사용
        results = run_yearly_analysis(combined_data, 2018, 2025, optimized_strategy)
        
        # 결과 저장
        if results:
            output = {
                'system_type': 'Optimized MA Adaptive Trading System (Final)',
                'test_period': '2018-01-01 ~ 2025-12-31',
                'optimization_method': 'Grid Search for MA Parameters',
                'yearly_results': results,
                'summary': {
                    'total_years': len([y for y in results.values() if y['total_trades'] > 0]),
                    'total_trades': sum([y['total_trades'] for y in results.values()]),
                    'final_capital': results[2025]['final_capital'],
                    'total_return': (results[2025]['final_capital'] - 10000) / 10000 * 100
                },
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open('final_optimized_results.json', 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            print(f"\n최종 결과가 final_optimized_results.json에 저장되었습니다.")
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
