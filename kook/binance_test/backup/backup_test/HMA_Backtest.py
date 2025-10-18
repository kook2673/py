#-*-coding:utf-8 -*-
'''
바이낸스 선물거래 MA + 추세 하이브리드 전략 백테스트 (JSON MA 값 사용)
2023년 1월~12월까지 월간별로 JSON에서 MA 값을 읽어서 백테스트 실행

=== 전략 구성 ===
1. MA 신호: 골든크로스/데드크로스 기반 이동평균 전략
2. 추세 필터: 모멘텀 + 연속성 + 볼린저밴드 + RSI 조합
3. 거래량 필터: 평균 거래량 대비 20% 이상 높을 때만 진입

=== 추세 전략 상세 ===
- 모멘텀 (5일, 10일): 현재가 - N일 전 가격으로 추세 강도 측정
- 추세 연속성: 연속 상승/하락 일수로 추세 지속성 확인
- 볼린저 밴드: 가격 위치(0~1)로 과매수/과매도 구간 판단
- RSI (14일): 상대강도지수로 과매수/과매도 상태 확인

=== 진입 조건 ===
롱 진입: MA 골든크로스 + 상승 추세 + 거래량 증가
- MA1, MA2 모두 상승 중
- 모멘텀 5일, 10일 양수
- 추세 연속성 3일 이상
- 볼린저 밴드 상단(>0.5)
- RSI 중립선 이상(>50)
- 거래량 20일 평균 대비 20% 이상

=== 청산 조건 ===
롱 청산: MA 데드크로스 또는 추세 전환
- MA1 또는 MA2 하락 전환
- 모멘텀 전환 또는 추세 연속성 중단
- RSI 과매수(>80)

=== 설정값 ===
- 레버리지: 5배
- 초기 자본: 10,000 USDT
- 수수료: 0.1% (진입/청산 각각)
- 롱 포지션만: 안전하고 단순한 구조

=== 백테스트 결과 ===
- 월간별 성과 분석
- 전체 기간 수익률 및 MDD
- 전략별 승률 및 거래 통계
- 그래프 시각화 및 JSON 저장
'''

import pandas as pd
import json
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import os
import glob

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

def calculate_hma(df, period):
    """Hull Moving Average 계산"""
    # WMA(Weighted Moving Average) 계산
    def wma(data, period):
        weights = np.arange(1, period + 1)
        return np.average(data, weights=weights)
    
    # HMA 계산
    half_period = int(period / 2)
    sqrt_period = int(np.sqrt(period))
    
    # 1단계: half_period 기간의 WMA
    wma1 = df['close'].rolling(half_period).apply(lambda x: wma(x, half_period))
    
    # 2단계: period 기간의 WMA
    wma2 = df['close'].rolling(period).apply(lambda x: wma(x, period))
    
    # 3단계: 2*WMA1 - WMA2
    raw_hma = 2 * wma1 - wma2
    
    # 4단계: sqrt_period 기간의 WMA
    hma = raw_hma.rolling(sqrt_period).apply(lambda x: wma(x, sqrt_period))
    
    return hma

def calculate_ma(df, period):
    """Simple Moving Average 계산"""
    return df['close'].rolling(period).mean()

def calculate_atr(df, period=14):
    """Average True Range 계산 (변동성 측정)"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()

def calculate_volatility_ratio(df, period=20):
    """변동성 비율 계산 (현재 변동성 / 과거 평균 변동성)"""
    atr = calculate_atr(df, period)
    atr_ma = atr.rolling(period).mean()
    return atr / atr_ma

def calculate_moving_averages(df, ma1, ma2):
    """하이브리드 이동평균선 계산 (HMA + MA)"""
    # HMA 계산
    df[f'{ma1}hma'] = calculate_hma(df, ma1)
    df[f'{ma2}hma'] = calculate_hma(df, ma2)
    
    # MA 계산
    df[f'{ma1}ma'] = calculate_ma(df, ma1)
    df[f'{ma2}ma'] = calculate_ma(df, ma2)
    
    # 변동성 지표 계산
    df['volatility_ratio'] = calculate_volatility_ratio(df, 20)
    
    return df

def calculate_trend_indicators(df):
    """
    추세 지표 계산
    
    === 계산되는 지표들 ===
    1. 모멘텀 (5일, 10일): 가격 변화의 강도와 방향
    2. 추세 강도: 가격 변화율의 표준편차로 변동성 측정
    3. 추세 연속성: 연속 상승/하락 일수로 추세 지속성 확인
    4. 볼린저 밴드: 가격의 상대적 위치 (0=하단, 1=상단)
    5. RSI: 상대강도지수로 과매수/과매도 상태 판단
    
    === 각 지표의 의미 ===
    - 모멘텀 > 0: 상승 추세, < 0: 하락 추세
    - 추세 연속성: 양수=상승 연속, 음수=하락 연속
    - 볼린저 밴드: 0.5 이상=상단, 0.5 이하=하단
    - RSI: 50 이상=상승, 50 이하=하락, 80 이상=과매수, 20 이하=과매도
    """
    # 1. 가격 모멘텀 (현재가 - N일 전 가격)
    # 모멘텀 > 0: 상승 추세, < 0: 하락 추세
    df['momentum_5'] = df['close'] - df['close'].shift(5)   # 5일 모멘텀
    df['momentum_10'] = df['close'] - df['close'].shift(10) # 10일 모멘텀
    
    # 2. 추세 강도 (가격 변화율의 표준편차)
    # 변동성이 클수록 값이 커짐 (추세 전환 가능성)
    df['price_change'] = df['close'].pct_change()
    df['trend_strength'] = df['price_change'].rolling(20).std()
    
    # 3. 추세 방향 (연속 상승/하락 일수)
    # 양수: 상승 연속, 음수: 하락 연속, 절댓값이 클수록 강한 추세
    df['trend_direction'] = np.where(df['close'] > df['close'].shift(1), 1, -1)
    df['trend_continuity'] = df['trend_direction'].rolling(5).sum()
    
    # 4. 볼린저 밴드 기반 추세
    # 20일 이동평균 ± 2표준편차
    # 0.5 이상: 상단 (상승 추세), 0.5 이하: 하단 (하락 추세)
    df['bb_upper'] = df['close'].rolling(20).mean() + 2 * df['close'].rolling(20).std()
    df['bb_lower'] = df['close'].rolling(20).mean() - 2 * df['close'].rolling(20).std()
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # 5. RSI 기반 추세 (14일)
    # 50 이상: 상승 추세, 50 이하: 하락 추세
    # 80 이상: 과매수, 20 이하: 과매도
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

def backtest_trend_strategy(df, initial_capital=10000, leverage=3, fee=0.001):
    """추세 기반 전략 백테스트 (롱 포지션만)"""
    # 추세 지표 계산
    df = calculate_trend_indicators(df)
    df.dropna(inplace=True)
    
    # 백테스트 변수 초기화 (롱 포지션만)
    position = 0  # 0: 없음, 1: 롱 보유
    entry_price = 0
    entry_time = None
    position_size = 0
    
    total_capital = initial_capital
    equity_curve = []
    trades = []
    
    for i in range(20, len(df)):
        current_price = df['close'].iloc[i]
        current_time = df.index[i]
        
        # 추세 신호 생성
        momentum_5 = df['momentum_5'].iloc[i]
        momentum_10 = df['momentum_10'].iloc[i]
        trend_continuity = df['trend_continuity'].iloc[i]
        bb_position = df['bb_position'].iloc[i]
        trend_strength = df['trend_strength'].iloc[i]
        rsi = df['rsi'].iloc[i]
        
        # 롱 진입: 강한 상승 추세
        if (position == 0 and 
            momentum_5 > 0 and momentum_10 > 0 and  # 모멘텀 양수
            trend_continuity >= 3 and               # 연속 상승
            bb_position > 0.5 and                   # 볼린저 밴드 상단
            rsi > 50):                              # RSI 중립선 이상
        
            position = 1
            entry_price = current_price
            entry_time = current_time
            position_size = (total_capital * leverage) / current_price
        
        # 롱 포지션 청산 신호
        elif position == 1:
            if (momentum_5 < 0 or momentum_10 < 0 or  # 모멘텀 전환
                trend_continuity <= 0 or               # 추세 전환
                rsi > 80):                            # RSI 과매수
        
                # 수익률 계산
                pnl = (current_price - entry_price) / entry_price * leverage
                pnl_amount = total_capital * pnl
                total_fee = (entry_price + current_price) * position_size * fee
                net_pnl = pnl_amount - total_fee
                
                # 자본 업데이트
                total_capital += net_pnl
                
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'pnl': net_pnl,
                    'strategy_type': 'TREND',
                    'position_type': 'LONG'
                })
                
                position = 0
                entry_price = 0
                entry_time = None
                position_size = 0
        
        # 자산 곡선 기록
        if position != 0:
            current_equity = total_capital + (position * (current_price - entry_price) / entry_price * leverage * total_capital)
            equity_curve.append({
                'time': current_time,
                'equity': current_equity,
                'price': current_price
            })
    
    # 마지막 포지션 강제 청산
    if position == 1:
        final_price = df['close'].iloc[-1]
        pnl = (final_price - entry_price) / entry_price * leverage
        pnl_amount = total_capital * pnl
        total_fee = (entry_price + final_price) * position_size * fee
        net_pnl = pnl_amount - total_fee
        total_capital += net_pnl
        
        trades.append({
            'entry_time': entry_time,
            'exit_time': df.index[-1],
            'entry_price': entry_price,
            'exit_price': final_price,
            'pnl': net_pnl,
            'strategy_type': 'TREND',
            'position_type': 'LONG'
        })
    
    # 결과 계산
    if not equity_curve:
        total_return = 0
        final_equity = initial_capital
    else:
        final_equity = total_capital
        total_return = (final_equity - initial_capital) / initial_capital * 100
    
    # MDD 계산
    if not equity_curve:
        mdd = 0
    else:
        equity_values = [e['equity'] for e in equity_curve]
        peak = equity_values[0]
        mdd = 0
        
        for equity in equity_values:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak * 100
            if drawdown > mdd:
                mdd = drawdown
    
    return {
        'total_return': total_return,
        'final_equity': final_equity,
        'initial_capital': initial_capital,
        'equity_curve': equity_curve,
        'trades': trades,
        'mdd': mdd,
        'trade_count': len(trades),
        'win_trades': len([t for t in trades if t['pnl'] > 0]),
        'strategy_type': 'TREND_ONLY'
    }

def backtest_hybrid_strategy(df, ma1, ma2, initial_capital=10000, leverage=3, fee=0.001, use_trend=False, trend_params=None):
    """MA + 추세 하이브리드 전략 백테스트 (MA만 사용, 롱 포지션만)"""
    # MA 이동평균선 계산
    df = calculate_moving_averages(df, ma1, ma2)
    
    # 추세 지표도 계산 (하이브리드 모드일 때)
    if use_trend:
        df = calculate_trend_indicators(df)
    
    df.dropna(inplace=True)
    
    # 백테스트 변수 초기화 (롱 포지션만)
    position = 0  # 0: 없음, 1: 롱 보유
    entry_price = 0
    entry_time = None
    position_size = 0
    
    total_capital = initial_capital
    equity_curve = []
    trades = []

    for i in range(2, len(df)):
        current_price = df['close'].iloc[i]
        current_time = df.index[i]
        
        # MA만 사용 (HMA 제거)
        ma1_current = df[f'{ma1}ma'].iloc[i]
        ma1_prev = df[f'{ma1}ma'].iloc[i-1]
        ma1_prev2 = df[f'{ma1}ma'].iloc[i-2]
        
        ma2_current = df[f'{ma2}ma'].iloc[i]
        ma2_prev = df[f'{ma2}ma'].iloc[i-1]
        ma2_prev2 = df[f'{ma2}ma'].iloc[i-2]
        
        close_prev = df['close'].iloc[i-1]
        
        # 추세 신호 (하이브리드 모드일 때)
        trend_signal = 0
        if use_trend and i >= 20:
            momentum_5 = df['momentum_5'].iloc[i]
            momentum_10 = df['momentum_10'].iloc[i]
            trend_continuity = df['trend_continuity'].iloc[i]
            bb_position = df['bb_position'].iloc[i]
            rsi = df['rsi'].iloc[i]
            
            # JSON에서 가져온 추세 파라미터 사용
            if trend_params:
                trend_continuity_min = trend_params.get('trend_continuity_min', 2)
                rsi_oversold = trend_params.get('rsi_oversold', 50)
                rsi_overbought = trend_params.get('rsi_overbought', 80)
                momentum_period = trend_params.get('momentum_period', 5)
            else:
                # 기본값 (fallback)
                trend_continuity_min = 2
                rsi_oversold = 50
                rsi_overbought = 80
                momentum_period = 5
            
            # 추세 신호 생성 (JSON 파라미터 기반)
            if (momentum_5 > 0 and momentum_10 > 0 and  # 모멘텀 양수
                trend_continuity >= trend_continuity_min and  # JSON에서 가져온 연속 상승 기준
                bb_position > 0.3 and                     # 볼린저 밴드 0.3 이상
                rsi > rsi_oversold and                    # JSON에서 가져온 RSI 과매도 기준
                rsi < rsi_overbought):                    # JSON에서 가져온 RSI 과매수 기준
                trend_signal = 1  # 상승 추세
        
        # 롱 진입 신호 (MA + 추세 조합)
        if position == 0:
            volume_filter = False
            if i >= 20:
                current_volume = df['volume'].iloc[i]
                avg_volume = df['volume'].rolling(20).mean().iloc[i]
                volume_filter = current_volume > avg_volume * 1.2
            
            # MA 신호
            ma_signal = (close_prev >= ma1_prev and ma1_prev2 <= ma1_prev and 
                        close_prev >= ma2_prev and ma2_prev2 <= ma2_prev)
            
            # 추세 신호와 조합 - 추세 전략 우선
            if use_trend:
                # 추세 전략이 활성화되면 더 유연한 진입 조건
                if trend_signal == 1:
                    # 추세 신호가 있으면 MA 조건 완화 또는 추세만으로 진입
                    entry_condition = ((close_prev >= ma1_prev or close_prev >= ma2_prev) or 
                                     (trend_continuity >= 3 and momentum_5 > 0 and momentum_10 > 0)) and (i < 20 or volume_filter)
                else:
                    # 추세 신호가 없으면 기존 MA 조건
                    entry_condition = ma_signal and (i < 20 or volume_filter)
            else:
                entry_condition = ma_signal and (i < 20 or volume_filter)
            
            if entry_condition:
                position = 1
                entry_price = current_price
                entry_time = current_time
                position_size = (total_capital * leverage) / current_price
                
                # 전략 타입 결정 (진입 시점에 결정)
                if use_trend and trend_signal == 1:
                    strategy_type = 'TREND'
                else:
                    strategy_type = 'MA'
        
        # 롱 포지션 청산 신호
        elif position == 1:
            if (close_prev < ma1_prev and ma1_prev2 > ma1_prev) or (close_prev < ma2_prev and ma2_prev2 > ma2_prev):
                pnl = (current_price - entry_price) / entry_price * leverage
                pnl_amount = total_capital * pnl
                total_fee = (entry_price + current_price) * position_size * fee
                net_pnl = pnl_amount - total_fee
                
                total_capital += net_pnl
                
                equity_curve.append({
                    'time': current_time,
                    'equity': total_capital,
                    'price': current_price,
                    'pnl_display': f"롱진입: {entry_price:.0f} | 청산: {current_price:.0f} | 실현: {pnl*100:.2f}% | 수익: {net_pnl:.0f} | {strategy_type}"
                })
                
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'pnl': net_pnl,
                    'pnl_pct': pnl * 100,
                    'strategy_type': strategy_type,
                    'volatility_ratio': 1.0,  # MA 사용 시 고정값
                    'position_type': 'LONG'
                })
                
                position = 0
                entry_price = 0
                entry_time = None
                position_size = 0
        
        # 진입 시 자산 곡선 기록
        if position == 1 and current_time == entry_time:
            equity_curve.append({
                'time': current_time,
                'equity': total_capital,
                'price': current_price,
                'pnl_display': f"롱진입: {entry_price:.0f} | 미실현: 0.00% | MA"
            })
    
    # 마지막 포지션 강제 청산
    if position == 1:
        final_price = df['close'].iloc[-1]
        pnl = (final_price - entry_price) / entry_price * leverage
        pnl_amount = total_capital * pnl
        total_fee = (entry_price + final_price) * position_size * fee
        net_pnl = pnl_amount - total_fee
        total_capital += net_pnl
        
        trades.append({
            'entry_time': entry_time,
            'exit_time': df.index[-1],
            'entry_price': entry_price,
            'exit_price': final_price,
            'pnl': net_pnl,
            'pnl_pct': pnl * 100,
            'strategy_type': 'MA',
            'volatility_ratio': 1.0,  # MA 사용 시 고정값
            'position_type': 'LONG'
        })
    
    # 결과 계산
    if not equity_curve:
        total_return = 0
        final_equity = initial_capital
    else:
        final_equity = total_capital
        total_return = (final_equity - initial_capital) / initial_capital * 100
    
    # MDD 계산
    if not equity_curve:
        mdd = 0
    else:
        equity_values = [e['equity'] for e in equity_curve]
        peak = equity_values[0]
        mdd = 0
        
        for equity in equity_values:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak * 100
            if drawdown > mdd:
                mdd = drawdown
    
    return {
        'total_return': total_return,
        'final_equity': final_equity,
        'initial_capital': initial_capital,
        'equity_curve': equity_curve,
        'trades': trades,
        'mdd': mdd,
        'trade_count': len(trades),
        'win_trades': len([t for t in trades if t['pnl'] > 0]),
        'ma1': ma1,
        'ma2': ma2,
        'strategy_mode': 'MA_ONLY'
    }

def backtest_strategy(df, ma1, ma2, initial_capital=10000, leverage=3, fee=0.001):
    """HMA 더블 이동평균 전략 백테스트 (롱 포지션만)"""
    # HMA 이동평균선 계산
    df = calculate_moving_averages(df, ma1, ma2)
    df.dropna(inplace=True)
    
    # 백테스트 변수 초기화 (롱 포지션만)
    position = 0  # 0: 없음, 1: 롱 보유
    entry_price = 0
    entry_time = None
    position_size = 0
    
    total_capital = initial_capital
    equity_curve = []
    trades = []
    strategy_type = "Unknown"
    
    for i in range(2, len(df)):
        current_price = df['close'].iloc[i]
        current_time = df.index[i]
        
        # 변동성 기반 이동평균선 선택
        volatility_ratio = df['volatility_ratio'].iloc[i] if 'volatility_ratio' in df.columns else 1.0
        volatility_threshold = 1.2
        
        # 변동성이 높을 때는 HMA, 낮을 때는 MA 사용
        if volatility_ratio > volatility_threshold:
            ma1_current = df[f'{ma1}hma'].iloc[i]
            ma1_prev = df[f'{ma1}hma'].iloc[i-1]
            ma1_prev2 = df[f'{ma1}hma'].iloc[i-2]
            
            ma2_current = df[f'{ma2}hma'].iloc[i]
            ma2_prev = df[f'{ma2}hma'].iloc[i-1]
            ma2_prev2 = df[f'{ma2}hma'].iloc[i-2]
            
            strategy_type = "HMA"
        else:
            ma1_current = df[f'{ma1}ma'].iloc[i]
            ma1_prev = df[f'{ma1}ma'].iloc[i-1]
            ma1_prev2 = df[f'{ma1}ma'].iloc[i-2]
            
            ma2_current = df[f'{ma2}ma'].iloc[i]
            ma2_prev = df[f'{ma2}ma'].iloc[i-1]
            ma2_prev2 = df[f'{ma2}ma'].iloc[i-2]
            
            strategy_type = "MA"
        
        close_prev = df['close'].iloc[i-1]
        
        # 롱 진입 신호 확인
        if position == 0:
            # 거래량 필터: 현재 거래량이 20기간 평균 거래량보다 20% 이상 높을 때만 진입
            volume_filter = False
            if i >= 20:
                current_volume = df['volume'].iloc[i]
                avg_volume = df['volume'].rolling(20).mean().iloc[i]
                volume_filter = current_volume > avg_volume * 1.2
            
            # 롱 진입: 골든 크로스 (단기 이동평균이 장기 이동평균을 상향 돌파하고 둘 다 상승중)
            if (close_prev >= ma1_prev and ma1_prev2 <= ma1_prev and 
                close_prev >= ma2_prev and ma2_prev2 <= ma2_prev and
                (i < 20 or volume_filter)):
                
                position = 1  # 롱 포지션
                entry_price = current_price
                entry_time = current_time
                position_size = (total_capital * leverage) / current_price
                
        # 롱 포지션 청산 신호 확인
        elif position == 1:
            # 롱 포지션 청산: 데드 크로스 (단기 이동평균이 장기 이동평균을 하향 돌파)
            if (close_prev < ma1_prev and ma1_prev2 > ma1_prev) or (close_prev < ma2_prev and ma2_prev2 > ma2_prev):
                
                # 롱 포지션 수익률 계산
                pnl = (current_price - entry_price) / entry_price * leverage
                pnl_amount = total_capital * pnl
                
                # 수수료 차감
                total_fee = (entry_price + current_price) * position_size * fee
                net_pnl = pnl_amount - total_fee
                
                # 자본 업데이트
                total_capital += net_pnl
                
                # 청산 직후 equity_curve에 추가
                equity_curve.append({
                    'time': current_time,
                    'equity': total_capital,
                    'price': current_price,
                    'pnl_display': f"롱진입: {entry_price:.0f} | 청산: {current_price:.0f} | 실현: {pnl*100:.2f}% | 수익: {net_pnl:.0f} | {strategy_type}"
                })
                
                # 거래 기록
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'pnl': net_pnl,
                    'pnl_pct': pnl * 100,
                    'strategy_type': strategy_type,
                    'volatility_ratio': round(volatility_ratio, 3),
                    'position_type': 'LONG'
                })
                
                position = 0
                entry_price = 0
                entry_time = None
                position_size = 0
        
        # 롱 진입 시 자산 곡선 기록
        if position == 1 and current_time == entry_time:
            equity_curve.append({
                'time': current_time,
                'equity': total_capital,
                'price': current_price,
                'pnl_display': f"롱진입: {entry_price:.0f} | 미실현: 0.00% | {strategy_type}"
            })
    
    # 마지막 포지션이 열려있다면 강제 청산
    if position == 1:
        final_price = df['close'].iloc[-1]
        pnl = (final_price - entry_price) / entry_price * leverage
        pnl_amount = total_capital * pnl
        total_fee = (entry_price + final_price) * position_size * fee
        net_pnl = pnl_amount - total_fee
        total_capital += net_pnl
        
        trades.append({
            'entry_time': entry_time,
            'exit_time': df.index[-1],
            'entry_price': entry_price,
            'exit_price': final_price,
            'pnl': net_pnl,
            'pnl_pct': pnl * 100,
            'strategy_type': strategy_type,
            'volatility_ratio': round(df['volatility_ratio'].iloc[-1], 3) if 'volatility_ratio' in df.columns else 0,
            'position_type': 'LONG'
        })
    
    # 결과 계산
    if not equity_curve:
        total_return = 0
        final_equity = initial_capital
    else:
        final_equity = total_capital
        total_return = (final_equity - initial_capital) / initial_capital * 100
    
    # MDD 계산
    if not equity_curve:
        mdd = 0
    else:
        equity_values = [e['equity'] for e in equity_curve]
        peak = equity_values[0]
        mdd = 0
        
        for equity in equity_values:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak * 100
            if drawdown > mdd:
                mdd = drawdown
    
    return {
        'total_return': total_return,
        'final_equity': final_equity,
        'initial_capital': initial_capital,
        'equity_curve': equity_curve,
        'trades': trades,
        'mdd': mdd,
        'trade_count': len(trades),
        'win_trades': len([t for t in trades if t['pnl'] > 0]),
        'ma1': ma1,
        'ma2': ma2
    }



def plot_backtest_results(df, backtest_result, ticker):
    """백테스트 결과를 그래프로 표시 (원본 HMA_Backtest.py 형식)"""
    if not backtest_result or not backtest_result['equity_curve']:
        return None
    
    # 데이터 준비
    equity_curve = backtest_result['equity_curve']
    times = [e['time'] for e in equity_curve]
    equity_values = [e['equity'] for e in equity_curve]
    prices = [e['price'] for e in equity_curve]
    pnl_displays = [e.get('pnl_display', '') for e in equity_curve]
    
    # 거래 신호 표시
    trades = backtest_result['trades']
    buy_times = []
    buy_prices = []
    sell_times = []
    sell_prices = []
    
    for trade in trades:
        buy_times.append(trade['entry_time'])
        buy_prices.append(trade['entry_price'])
        sell_times.append(trade['exit_time'])
        sell_prices.append(trade['exit_price'])
    
    # 그래프 생성
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(20, 12))
    
    # 첫 번째 그래프: 비트코인 가격과 매매 신호
    # 4시간 가격 차트 (더 선명하게)
    if not df.empty:
        # equity_curve의 시간 범위에 맞는 데이터만 필터링
        start_time = min(times)
        end_time = max(times)
        chart_data = df[(df.index >= start_time) & (df.index <= end_time)]
        
        if not chart_data.empty:
            # 4시간 가격 차트 (더 선명하게)
            ax1.plot(chart_data.index, chart_data['close'], 
                    label='BTC/USDT 4H', linewidth=1.5, color='lightblue', alpha=0.9)
    
    # equity_curve의 가격 데이터 (더 진하게)
    ax1.plot(times, prices, label='거래 가격', linewidth=1.5, color='darkblue', alpha=0.9)
    
    # 매수 신호 (녹색 화살표만 - 글자 제거)
    if buy_times:
        ax1.scatter(buy_times, buy_prices, color='lime', marker='^', s=200, label='매수', zorder=10, alpha=1.0, edgecolors='darkgreen', linewidth=2)
    
    # 매도 신호 (빨간 화살표만 - 글자 제거)
    if sell_times:
        ax1.scatter(sell_times, sell_prices, color='red', marker='v', s=200, label='매도', zorder=10, alpha=1.0, edgecolors='darkred', linewidth=2)
    
    ax1.set_ylabel('가격 (USDT)', fontsize=12)
    ax1.set_title(f'{ticker} - 4시간 가격 차트 및 매매 신호', fontsize=14)
    ax1.legend()
    ax1.grid(True, alpha=0.4)
    
    # 두 번째 그래프: 자산 곡선과 MDD
    ax2.plot(times, equity_values, label='자산 곡선', linewidth=3, color='darkgreen', alpha=0.9)
    
    # 초기 자본선 (첫 번째 자산 값 기준)
    initial_capital = equity_values[0] if equity_values else 10000
    ax2.axhline(y=initial_capital, color='red', linestyle='--', alpha=0.8, label=f'초기 자본: {initial_capital:.0f}', linewidth=2)
    
    # MDD 표시
    if backtest_result['mdd'] > 0:
        peak_value = max(equity_values)
        ax2.axhline(y=peak_value, color='orange', linestyle=':', alpha=0.8, label=f'피크: {peak_value:.0f}', linewidth=2)
    
    # 수익률 표시 제거 (진입가, 청산가 정보 없이)
    
    ax2.set_ylabel('자산 (USDT)', fontsize=12)
    ax2.set_title(f'자산 곡선 (수익률: {backtest_result["total_return"]:.2f}%, MDD: {backtest_result["mdd"]:.2f}%)', fontsize=14)
    ax2.legend()
    ax2.grid(True, alpha=0.4)
    
    # x축 날짜 포맷 설정
    for ax in [ax1, ax2]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    
    # logs 폴더에 그래프 이미지 저장
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    image_filename = f'Monthly_Backtest_Graph_{ticker.replace("/", "_")}_{timestamp}.png'
    image_filepath = os.path.join(logs_dir, image_filename)
    
    plt.savefig(image_filepath, dpi=300, bbox_inches='tight')
    print(f"백테스트 결과 그래프가 {image_filepath}에 저장되었습니다.")
    
    #plt.show()
    
    return fig

def load_optimized_parameters(json_file_path):
    """MA_Trend_Backtest_v2.json에서 최적화된 파라미터 로드"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✅ 최적화 파라미터 로드 완료: {os.path.basename(json_file_path)}")
        
        # 2024년부터 현재까지의 월별 파라미터만 필터링
        monthly_parameters = {}
        for key, value in data.items():
            if key.startswith('2024_') or key.startswith('2025_'):
                monthly_parameters[key] = value
        
        print(f"📊 총 {len(monthly_parameters)}개월의 파라미터가 로드되었습니다.")
        print(f"📅 백테스트 기간: 2024년 1월 ~ 현재")
        
        return monthly_parameters
    except Exception as e:
        print(f"❌ 파라미터 로드 실패: {e}")
        print(f"📁 파일 경로: {json_file_path}")
        return None

def main():
    """메인 함수"""
    print("바이낸스 선물거래 MA + 추세 하이브리드 전략 백테스트 시작!")
    print("MA_Trend_Backtest_v2.json에서 최적화된 파라미터를 읽어와서 2024년부터 현재까지 백테스트를 실행합니다.")
    print("전략: MA + 추세 (안정적인 MA 신호 + 추세 필터)")
    
    # MA + 추세 하이브리드 전략으로 고정
    selected_strategy = 'HYBRID'
    print(f"\n✅ 사용 전략: {selected_strategy}")
    
    # MA_Trend_Backtest_v2.json 파일에서 최적화된 파라미터 로드
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_file_path = os.path.join(script_dir, "MA_Trend_Backtest_v2.json")
    
    if not os.path.exists(json_file_path):
        print(f"❌ MA_Trend_Backtest_v2.json 파일을 찾을 수 없습니다.")
        print(f"📁 파일 경로: {json_file_path}")
        return
    
    print(f"✅ 파라미터 파일 발견: {os.path.basename(json_file_path)}")
    
    # 최적화된 파라미터 로드
    monthly_parameters = load_optimized_parameters(json_file_path)
    if not monthly_parameters:
        print("파라미터를 로드할 수 없습니다.")
        return
    
    # 백테스트 설정
    ticker = 'BTC/USDT'
    initial_capital = 10000  # 기본값
    leverage = 5  # 기본값
    
    print(f"\n{ticker} 로컬 CSV 데이터 로드 중...")
    
    # 2024년부터 현재까지의 CSV 파일들 로드
    data_dir = os.path.join(script_dir, 'data', 'BTCUSDT', '4h')
    
    # 2024년부터 2025년까지의 CSV 파일들 찾기
    csv_files = []
    for year in [2024, 2025]:
        csv_pattern = f'BTCUSDT_4h_{year}.csv'
        year_files = glob.glob(os.path.join(data_dir, csv_pattern))
        csv_files.extend(year_files)
    
    if not csv_files:
        print(f"❌ CSV 파일을 찾을 수 없습니다.")
        print(f"📁 데이터 디렉토리: {data_dir}")
        print("먼저 필요한 데이터를 다운로드하세요.")
        return
    
    # 모든 CSV 파일을 하나로 합치기
    all_data = []
    for csv_file in sorted(csv_files):
        try:
            df = pd.read_csv(csv_file, index_col='datetime', parse_dates=True)
            all_data.append(df)
            print(f"✅ {os.path.basename(csv_file)} 로드 완료: {len(df)}개 캔들")
        except Exception as e:
            print(f"❌ {csv_file} 로드 실패: {e}")
    
    if not all_data:
        print("데이터를 가져올 수 없습니다.")
        return
    
    # 모든 데이터 합치기
    df_4h = pd.concat(all_data, ignore_index=False)
    df_4h = df_4h.sort_index()  # 시간순 정렬
    
    print(f"✅ 전체 데이터 로드 완료: {len(df_4h)}개 캔들")
    print(f"기간: {df_4h.index[0]} ~ {df_4h.index[-1]}")
    
    # 월간별 백테스트 결과 저장
    monthly_backtest_results = []
    
    # 각 월별로 백테스트 진행 (연속성 유지)
    current_capital = initial_capital  # 첫 달은 10000으로 시작
    for month_key, params in monthly_parameters.items():
        year, month = month_key.split('_')
        year = int(year)
        month = int(month)
        
        # 해당 월의 데이터 추출
        month_start_date = datetime.datetime(year, month, 1)
        if month == 12:
            month_end_date = datetime.datetime(year + 1, 1, 1) - datetime.timedelta(seconds=1)
        else:
            month_end_date = datetime.datetime(year, month + 1, 1) - datetime.timedelta(seconds=1)
        
        month_df = df_4h[(df_4h.index >= month_start_date) & (df_4h.index <= month_end_date)]
        
        if len(month_df) < 10:  # 최소 10개 캔들 이상
            print(f"⚠️ {year}년 {month:02d}월 데이터가 부족하여 건너뜁니다. ({len(month_df)}개 캔들)")
            continue
        
        ma1 = params['ma1']
        ma2 = params['ma2']
        trend_params = params.get('trend_params', {})
        
        print(f"\n{'='*60}")
        print(f"진행률: {len(monthly_backtest_results)+1}/{len(monthly_parameters)} 월")
        print(f"기간: {year}년 {month:02d}월")
        print(f"MA 값: MA1={ma1}, MA2={ma2}")
        print(f"추세 파라미터: {trend_params}")
        print(f"현재 자본: {current_capital:.2f} USDT")
        print(f"전략: {selected_strategy} (MA + 추세)")
        
        # MA + 추세 하이브리드 전략 실행 (JSON 파라미터 사용)
        backtest_result = backtest_hybrid_strategy(month_df.copy(), ma1, ma2, current_capital, leverage, use_trend=True, trend_params=trend_params)
        
        if backtest_result:
            # 월간 결과를 전체 형식에 맞게 변환
            monthly_result = {
                'month_start': month_start_date,
                'month_end': month_end_date,
                'ma1': ma1 if 'ma1' in backtest_result else 'N/A',
                'ma2': ma2 if 'ma2' in backtest_result else 'N/A',
                'total_return': backtest_result['total_return'],
                'final_equity': backtest_result['final_equity'],
                'mdd': backtest_result['mdd'],
                'trade_count': backtest_result['trade_count'],
                'win_trades': backtest_result['win_trades'],
                'equity_curve': backtest_result['equity_curve'],
                'trades': backtest_result['trades'],
                'strategy_mode': backtest_result.get('strategy_mode', selected_strategy)
            }
            
            monthly_backtest_results.append(monthly_result)
            
            # 월간 결과 출력
            print(f"월간 백테스트 결과:")
            print(f"  수익률: {backtest_result['total_return']:.2f}%")
            print(f"  MDD: {backtest_result['mdd']:.2f}%")
            print(f"  거래 횟수: {backtest_result['trade_count']}")
            if backtest_result['trade_count'] > 0:
                win_rate = backtest_result['win_trades'] / backtest_result['trade_count'] * 100
                print(f"  승률: {win_rate:.1f}%")
            
            # 다음 달 초기 자본으로 업데이트
            current_capital = backtest_result['final_equity']
            print(f"  다음 달 초기 자본: {current_capital:.2f} USDT")
        else:
            print("백테스트 실패")
    
    # 최종 결과 정리 및 저장
    print(f"\n{'='*60}")
    print("월간 백테스트 완료!")
    
    if monthly_backtest_results:
        # 전체 성과 계산
        total_months = len(monthly_backtest_results)
        profitable_months = len([r for r in monthly_backtest_results if r['total_return'] > 0])
        total_return = sum([r['total_return'] for r in monthly_backtest_results])
        avg_return = total_return / total_months
        max_mdd = max([r['mdd'] for r in monthly_backtest_results])
        
        print(f"\n=== 전체 성과 요약 ===")
        print(f"사용 전략: {selected_strategy} (MA + 추세)")
        print(f"총 개월: {total_months}개월")
        print(f"수익 개월: {profitable_months}개월 ({profitable_months/total_months*100:.1f}%)")
        print(f"총 수익률: {total_return:.2f}%")
        print(f"평균 월간 수익률: {avg_return:.2f}%")
        print(f"최대 MDD: {max_mdd:.2f}%")
        
        # 월간별 MA 파라미터 변화 요약
        print(f"\n=== 월간별 MA 파라미터 변화 ===")
        for i, result in enumerate(monthly_backtest_results):
            print(f"{result['month_start'].strftime('%Y-%m')}: MA1={result['ma1']}, MA2={result['ma2']}, "
                  f"수익률={result['total_return']:.2f}%")
    
    # 최종 결과를 파일로 저장
    final_results = {
        'ticker': ticker,
        'backtest_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'selected_strategy': selected_strategy,
        'strategy_description': 'MA + 추세 하이브리드 전략 (JSON 파라미터 사용)',
        'initial_capital': initial_capital,
        'leverage': leverage,
        'backtest_period': {
            'start_date': '2024-01-01',
            'end_date': datetime.datetime.now().strftime('%Y-%m-%d'),
            'total_months': len(monthly_parameters)
        }
    }
    
    # 전체 성과 요약 추가
    if monthly_backtest_results:
        # 전체 성과 계산
        total_months = len(monthly_backtest_results)
        profitable_months = len([r for r in monthly_backtest_results if r['total_return'] > 0])
        total_return = sum([r['total_return'] for r in monthly_backtest_results])
        avg_return = total_return / total_months
        max_mdd = max([r['mdd'] for r in monthly_backtest_results])
        
        # 전체 거래 통계
        total_trades = sum([r['trade_count'] for r in monthly_backtest_results])
        total_win_trades = sum([r['win_trades'] for r in monthly_backtest_results])
        win_rate = (total_win_trades / total_trades * 100) if total_trades > 0 else 0
        
        # 최종 자본 계산
        final_capital = monthly_backtest_results[-1]['final_equity'] if monthly_backtest_results else initial_capital
        
        # 전략별 통계 계산을 위한 임시 변수
        ma_trades_count = 0
        trend_trades_count = 0
        ma_win_count = 0
        trend_win_count = 0
        long_trades_count = 0
        long_win_count = 0
        
        # 월간 결과에서 전략별 통계 수집
        for result in monthly_backtest_results:
            if result and 'trades' in result:
                for trade in result['trades']:
                    # 전략별 통계
                    if trade.get('strategy_type') == 'MA':
                        ma_trades_count += 1
                        if trade['pnl'] > 0:
                            ma_win_count += 1
                    elif trade.get('strategy_type') == 'TREND':
                        trend_trades_count += 1
                        if trade['pnl'] > 0:
                            trend_win_count += 1
                    
                    # 포지션별 통계 (롱만)
                    if trade.get('position_type') == 'LONG':
                        long_trades_count += 1
                        if trade['pnl'] > 0:
                            long_win_count += 1
        
        ma_win_rate = (ma_win_count / ma_trades_count * 100) if ma_trades_count > 0 else 0
        trend_win_rate = (trend_win_count / trend_trades_count * 100) if trend_trades_count > 0 else 0
        long_win_rate = (long_win_count / long_trades_count * 100) if long_trades_count > 0 else 0
        
        final_results['overall_summary'] = {
            'total_return': round(total_return, 2),
            'final_capital': round(final_capital, 2),
            'profit_multiplier': round(final_capital / initial_capital, 2),
            'total_months': total_months,
            'profitable_months': profitable_months,
            'profitable_month_rate': round(profitable_months / total_months * 100, 1),
            'avg_monthly_return': round(avg_return, 2),
            'max_mdd': round(max_mdd, 2),
            'total_trades': total_trades,
            'total_win_trades': total_win_trades,
            'win_rate': round(win_rate, 1),
            'strategy_breakdown': {
                'ma_trades': ma_trades_count,
                'ma_win_rate': round(ma_win_rate, 1),
                'trend_trades': trend_trades_count,
                'trend_win_rate': round(trend_win_rate, 1)
            },
            'position_breakdown': {
                'long_trades': long_trades_count,
                'long_win_rate': round(long_win_rate, 1)
            }
        }
    
    final_results['monthly_backtest_results'] = monthly_backtest_results
    
    filename = f'HMA_Backtest_Result_{ticker.replace("/", "_")}_{selected_strategy}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    # logs 폴더에 저장
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    filepath = os.path.join(logs_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n최종 결과가 {filepath}에 저장되었습니다.")
    
    # 전체 기간 그래프 생성
    if monthly_backtest_results:
        print("\n전체 기간 백테스트 결과 그래프 생성 중...")
        
        # 전체 기간 데이터 준비
        all_equity_curve = []
        all_trades = []
        
        # 모든 월의 데이터를 하나로 합치기
        for result in monthly_backtest_results:
            if result and result['equity_curve']:
                all_equity_curve.extend(result['equity_curve'])
                all_trades.extend(result['trades'])
        
        if all_equity_curve:
            # 전체 백테스트 결과 생성
            total_equity_values = [e['equity'] for e in all_equity_curve]
            total_return = (total_equity_values[-1] - initial_capital) / initial_capital * 100
            
            # 전체 MDD 계산
            peak = total_equity_values[0]
            total_mdd = 0
            for equity in total_equity_values:
                if equity > peak:
                    peak = equity
                drawdown = (peak - equity) / peak * 100
                if drawdown > total_mdd:
                    total_mdd = drawdown
            
            # 전체 백테스트 결과
            total_backtest_result = {
                'total_return': total_return,
                'mdd': total_mdd,
                'equity_curve': all_equity_curve,
                'trades': all_trades
            }
            
            # 전체 기간 그래프 생성
            fig = plot_backtest_results(df_4h, total_backtest_result, ticker)
            if fig:
                plt.close(fig)  # 메모리 절약을 위해 그래프 닫기

if __name__ == "__main__":
    main()
