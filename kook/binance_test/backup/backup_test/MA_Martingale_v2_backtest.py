#-*-coding:utf-8 -*-
'''
바이낸스 선물거래 1분봉 MA + 추세 추종 + 물타기 전략 백테스트

=== 전략 구성 ===
1. 기본 MA: 5MA와 20MA 크로스오버
2. 추세 추종: 5가지 추세 지표 조합
3. 양방향 거래: 롱/숏 50:50 분할
4. 물타기 로직: 가격 하락률 기반 + 상승/하락 신호 동시 만족
5. 자산 분할: 1000등분하여 단계별 투자

=== 진입 조건 ===
롱 진입: 5MA > 20MA + 추세 지표 3개 이상 만족
숏 진입: 5MA < 20MA + 추세 지표 3개 이상 만족

=== 물타기 로직 ===
1차 물타기: 진입가 대비 -1% 하락 시 + 상승 신호
2차 물타기: 진입가 대비 -2% 하락 시 + 상승 신호  
3차 물타기: 진입가 대비 -3% 하락 시 + 상승 신호
4차 물타기: 진입가 대비 -4% 하락 시 + 상승 신호

물타기 자본: 각 단계별 누적 총 개수
- 최초 진입: 1개
- 1차 물타기: 2개 (총 3개)
- 2차 물타기: 6개 (총 9개)
- 3차 물타기: 18개 (총 27개)
- 4차 물타기: 54개 (총 81개)

=== 청산 조건 ===
1. 수익 실현: 평균단가 기준 0.3% 이상 수익 + MA 크로스오버 신호
    - 롱: 평균단가 기준 0.3% 이상 + 5MA < 20MA (데드크로스)
    - 숏: 평균단가 기준 0.3% 이상 + 5MA > 20MA (골든크로스)

2. 손절처리: 4차 물타기 완료 후 1배 기준 -1% 하락 시
    - 모든 물타기 기회 소진 후 리스크 관리
    - 초기 진입가 대비 -1% 손실 시 강제 청산

3. 백테스트 종료: 마지막 데이터에서 보유 포지션 강제 청산

=== 추세 지표 (5가지) ===
1. 모멘텀 (5분, 10분)
2. 추세 연속성 (5분 윈도우)
3. 볼린저 밴드 위치
4. RSI (14분)
5. 거래량 증가율

=== 전략 특징 ===
- 체계적인 물타기로 평균단가 낮춤
- 평균단가 기준 수익 실현으로 물타기 효과 극대화
- 수익 실현과 손절처리로 리스크 관리
- 추세 신호와 가격 조건을 동시에 만족해야 물타기 실행
- 최대 4차까지 물타기하여 회복 기회 제공
'''

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
import glob
from datetime import datetime, timedelta

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

def calculate_trend_indicators(df):
    """5가지 추세 지표 계산"""
    
    # 1. 모멘텀 (5분, 10분)
    df['momentum_5'] = df['close'].pct_change(5)
    df['momentum_10'] = df['close'].pct_change(10)
    
    # 2. 추세 연속성 (5분 윈도우)
    df['trend_direction'] = np.where(df['close'] > df['close'].shift(1), 1, -1)
    df['trend_continuity'] = df['trend_direction'].rolling(5).sum()
    
    # 3. 볼린저 밴드 위치
    df['bb_upper'] = df['close'].rolling(20).mean() + 2 * df['close'].rolling(20).std()
    df['bb_lower'] = df['close'].rolling(20).mean() - 2 * df['close'].rolling(20).std()
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # 4. RSI (14분)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 5. 거래량 증가율 (20분 평균 대비)
    df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    
    return df

def check_trend_signals(df, i, position_type):
    """추세 신호 확인 (5개 중 3개 이상 만족)"""
    
    if i < 20:  # 충분한 데이터가 없으면 False
        return False
    
    signals = 0
    total_signals = 5
    
    # 1. 모멘텀 신호
    momentum_5 = df['momentum_5'].iloc[i]
    momentum_10 = df['momentum_10'].iloc[i]
    
    if position_type == 'LONG':
        if momentum_5 > 0 and momentum_10 > 0:
            signals += 1
    else:  # SHORT
        if momentum_5 < 0 and momentum_10 < 0:
            signals += 1
    
    # 2. 추세 연속성 신호
    trend_continuity = df['trend_continuity'].iloc[i]
    
    if position_type == 'LONG':
        if trend_continuity >= 3:  # 3분 이상 연속 상승
            signals += 1
    else:  # SHORT
        if trend_continuity <= -3:  # 3분 이상 연속 하락
            signals += 1
    
    # 3. 볼린저 밴드 위치 신호
    bb_position = df['bb_position'].iloc[i]
    
    if position_type == 'LONG':
        if 0.3 <= bb_position <= 0.8:  # 적정 구간
            signals += 1
    else:  # SHORT
        if 0.2 <= bb_position <= 0.7:  # 적정 구간
            signals += 1
    
    # 4. RSI 신호
    rsi = df['rsi'].iloc[i]
    
    if position_type == 'LONG':
        if 30 <= rsi <= 70:  # 과매도/과매수 구간 제외
            signals += 1
    else:  # SHORT
        if 30 <= rsi <= 70:  # 과매도/과매수 구간 제외
            signals += 1
    
    # 5. 거래량 신호
    volume_ratio = df['volume_ratio'].iloc[i]
    
    if volume_ratio > 1.2:  # 평균 대비 1.2배 이상
        signals += 1
    
    # 5개 중 3개 이상 만족하면 True
    return signals >= 3

def calculate_martingale_size(entry_count):
    """물타기 크기 계산 (누적 총 개수)"""
    if entry_count == 1:
        return 1  # 최초 진입
    elif entry_count == 2:
        return 2  # 1차 물타기: 총 3개
    elif entry_count == 3:
        return 6  # 2차 물타기: 총 9개
    elif entry_count == 4:
        return 18  # 3차 물타기: 총 27개
    elif entry_count == 5:
        return 54  # 4차 물타기: 총 81개
    else:
        return 0  # 물타기 없음

def check_martingale_condition(entry_price, current_price, position_type, entry_count):
    """물타기 조건 확인 (가격 기반 + 상승 신호)"""
    
    if position_type == 'LONG':
        # 롱 포지션: 가격이 하락할 때 물타기
        if entry_count == 1:  # 1차 물타기: -1%
            return current_price <= entry_price * 0.99
        elif entry_count == 2:  # 2차 물타기: -2%
            return current_price <= entry_price * 0.98
        elif entry_count == 3:  # 3차 물타기: -3%
            return current_price <= entry_price * 0.97
        elif entry_count == 4:  # 4차 물타기: -4%
            return current_price <= entry_price * 0.96
    else:  # SHORT
        # 숏 포지션: 가격이 상승할 때 물타기
        if entry_count == 1:  # 1차 물타기: +1%
            return current_price >= entry_price * 1.01
        elif entry_count == 2:  # 2차 물타기: +2%
            return current_price >= entry_price * 1.02
        elif entry_count == 3:  # 3차 물타기: +3%
            return current_price >= entry_price * 1.03
        elif entry_count == 4:  # 4차 물타기: +4%
            return current_price >= entry_price * 1.04
    
    return False

def backtest_martingale_strategy(df, ma1=5, ma2=20, initial_capital=10000, leverage=7, fee=0.001):
    """MA + 추세 + 물타기 전략 백테스트"""
    
    # 추세 지표 계산
    df = calculate_trend_indicators(df)
    
    # MA 계산
    df[f'ma_{ma1}'] = df['close'].rolling(ma1).mean()
    df[f'ma_{ma2}'] = df['close'].rolling(ma2).mean()
    
    # 전략 변수
    long_position = 0  # 0: 없음, 1: 보유
    short_position = 0  # 0: 없음, 1: 보유
    
    long_entries = []  # 롱 진입 내역
    short_entries = []  # 숏 진입 내역
    
    capital = initial_capital
    long_capital = capital * 0.5  # 롱 전용 자본
    short_capital = capital * 0.5  # 숏 전용 자본
    
    trades = []
    equity_curve = []
    
    # 백테스트 실행
    for i in range(max(ma1, ma2), len(df)):
        current_time = df.index[i]
        current_price = df['close'].iloc[i]
        
        # MA 신호
        ma1_current = df[f'ma_{ma1}'].iloc[i]
        ma2_current = df[f'ma_{ma2}'].iloc[i]
        ma1_prev = df[f'ma_{ma1}'].iloc[i-1]
        ma2_prev = df[f'ma_{ma2}'].iloc[i-1]
        
        # 롱 진입 신호
        if long_position == 0:
            ma_signal = ma1_current > ma2_current and ma1_prev <= ma2_prev  # 골든크로스
            trend_signal = check_trend_signals(df, i, 'LONG')
            
            if ma_signal and trend_signal:
                # 롱 진입
                long_position = 1
                entry_info = {
                    'time': current_time,
                    'price': current_price,
                    'size': 1,  # 초기 진입 크기
                    'capital': long_capital * 0.001  # 1000등분 중 1
                }
                long_entries.append(entry_info)
                
                print(f"🟢 롱 진입: {current_time} | 가격: {current_price:.0f} | 크기: 1")
        
        # 숏 진입 신호
        if short_position == 0:
            ma_signal = ma1_current < ma2_current and ma1_prev >= ma2_prev  # 데드크로스
            trend_signal = check_trend_signals(df, i, 'SHORT')
            
            if ma_signal and trend_signal:
                # 숏 진입
                short_position = 1
                entry_info = {
                    'time': current_time,
                    'price': current_price,
                    'size': 1,  # 초기 진입 크기
                    'capital': short_capital * 0.001  # 1000등분 중 1
                }
                short_entries.append(entry_info)
                
                print(f"🔴 숏 진입: {current_time} | 가격: {current_price:.0f} | 크기: 1")
        
        # 롱 포지션 물타기 및 청산
        if long_position == 1 and long_entries:
            latest_entry = long_entries[-1]
            entry_price = latest_entry['price']
            entry_count = len(long_entries)
            
            # 물타기 조건 확인 (가격 기반 + 상승 신호)
            if entry_count == 1 and check_martingale_condition(entry_price, current_price, 'LONG', 1):
                # 1차 물타기: -1% 하락 시 + 상승 신호 확인
                if check_trend_signals(df, i, 'LONG'):
                    martingale_size = calculate_martingale_size(2)
                    if martingale_size > 0:
                        entry_info = {
                            'time': current_time,
                            'price': current_price,
                            'size': martingale_size,
                            'capital': long_capital * 0.001 * martingale_size
                        }
                        long_entries.append(entry_info)
                        print(f"🟢 롱 1차 물타기: {current_time} | 가격: {current_price:.0f} | 크기: {martingale_size}개 | 하락률: {((current_price-entry_price)/entry_price*100):.2f}% | 총 {len(long_entries)}개")
            
            elif entry_count == 2 and check_martingale_condition(entry_price, current_price, 'LONG', 2):
                # 2차 물타기: -2% 하락 시 + 상승 신호 확인
                if check_trend_signals(df, i, 'LONG'):
                    martingale_size = calculate_martingale_size(3)
                    if martingale_size > 0:
                        entry_info = {
                            'time': current_time,
                            'price': current_price,
                            'size': martingale_size,
                            'capital': long_capital * 0.001 * martingale_size
                        }
                        long_entries.append(entry_info)
                        print(f"🟢 롱 2차 물타기: {current_time} | 가격: {current_price:.0f} | 크기: {martingale_size}개 | 하락률: {((current_price-entry_price)/entry_price*100):.2f}% | 총 {len(long_entries)}개")
            
            elif entry_count == 3 and check_martingale_condition(entry_price, current_price, 'LONG', 3):
                # 3차 물타기: -3% 하락 시 + 상승 신호 확인
                if check_trend_signals(df, i, 'LONG'):
                    martingale_size = calculate_martingale_size(4)
                    if martingale_size > 0:
                        entry_info = {
                            'time': current_time,
                            'price': current_price,
                            'size': martingale_size,
                            'capital': long_capital * 0.001 * martingale_size
                        }
                        long_entries.append(entry_info)
                        print(f"🟢 롱 3차 물타기: {current_time} | 가격: {current_price:.0f} | 크기: {martingale_size}개 | 하락률: {((current_price-entry_price)/entry_price*100):.2f}% | 총 {len(long_entries)}개")
            
            elif entry_count == 4 and check_martingale_condition(entry_price, current_price, 'LONG', 4):
                # 4차 물타기: -4% 하락 시 + 상승 신호 확인
                if check_trend_signals(df, i, 'LONG'):
                    martingale_size = calculate_martingale_size(5)
                    if martingale_size > 0:
                        entry_info = {
                            'time': current_time,
                            'price': current_price,
                            'size': martingale_size,
                            'capital': long_capital * 0.001 * martingale_size
                        }
                        long_entries.append(entry_info)
                        print(f"🟢 롱 4차 물타기: {current_time} | 가격: {current_price:.0f} | 크기: {martingale_size}개 | 하락률: {((current_price-entry_price)/entry_price*100):.2f}% | 총 {len(long_entries)}개")

            # 4차 물타기 후 손절 조건 확인
            if entry_count == 5:  # 4차 물타기까지 완료된 상태
                initial_entry_price = long_entries[0]['price']  # 초기 진입가
                current_return_1x = (current_price - initial_entry_price) / initial_entry_price * 100  # 1배 기준 수익률
                
                # 손절 조건: 4차 물타기 후 -1% 하락 시
                if current_return_1x <= -1.0:
                    # 모든 롱 포지션 손절 청산
                    total_pnl = 0
                    total_invested = 0
                    
                    for entry in long_entries:
                        pnl = (current_price - entry['price']) / entry['price'] * leverage * (1 - fee)
                        invested = entry['capital']
                        total_pnl += pnl * invested
                        total_invested += invested
                    
                    # 손실률 계산
                    if total_invested > 0:
                        total_return = total_pnl / total_invested
                        long_capital *= (1 + total_return)
                        
                        trades.append({
                            'type': 'LONG_STOPLOSS',  # 손절 표시
                            'entry_times': [e['time'] for e in long_entries],
                            'entry_prices': [e['price'] for e in long_entries],
                            'exit_time': current_time,
                            'exit_price': current_price,
                            'sizes': [e['size'] for e in long_entries],
                            'total_return': total_return * 100,
                            'pnl': total_pnl,
                            'return_1x': current_return_1x
                        })
                        
                        print(f"🟢 롱 손절: {current_time} | 가격: {current_price:.0f} | 1배기준손실률: {current_return_1x:.2f}% | 총손실률: {total_return*100:.2f}% | 물타기횟수: {len(long_entries)}회")
                    
                    # 포지션 초기화
                    long_position = 0
                    long_entries = []

            # 청산 조건: 평균단가 기준 0.3% 이상 수익 + MA 크로스오버 신호
            # 평균단가 기준 수익률 계산
            if long_entries:  # 리스트가 비어있지 않을 때만 실행
                # 평균단가 계산
                total_invested = sum(entry['capital'] for entry in long_entries)
                weighted_avg_price = sum(entry['price'] * entry['capital'] for entry in long_entries) / total_invested
                current_return_avg = (current_price - weighted_avg_price) / weighted_avg_price * 100  # 평균단가 기준 수익률
                
                # 1배 기준 수익률도 계산 (로깅용)
                initial_entry_price = long_entries[0]['price']
                current_return_1x = (current_price - initial_entry_price) / initial_entry_price * 100
                
                if current_return_avg >= 0.3 and ma1_current < ma2_current and ma1_prev >= ma2_prev:  # 0.3% 이상 + 데드크로스
                    # 모든 롱 포지션 청산
                    total_pnl = 0
                    total_invested = 0
                    
                    for entry in long_entries:
                        pnl = (current_price - entry['price']) / entry['price'] * leverage * (1 - fee)
                        invested = entry['capital']
                        total_pnl += pnl * invested
                        total_invested += invested
                    
                    # 수익률 계산
                    if total_invested > 0:
                        total_return = total_pnl / total_invested
                        long_capital *= (1 + total_return)
                        
                        trades.append({
                            'type': 'LONG',
                            'entry_times': [e['time'] for e in long_entries],
                            'entry_prices': [e['price'] for e in long_entries],
                            'exit_time': current_time,
                            'exit_price': current_price,
                            'sizes': [e['size'] for e in long_entries],
                            'total_return': total_return * 100,
                            'pnl': total_pnl,
                            'return_avg': current_return_avg,  # 평균단가 기준 수익률로 변경
                            'avg_price': weighted_avg_price  # 평균단가 추가
                        })
                        
                        print(f"🟢 롱 청산: {current_time} | 가격: {current_price:.0f} | 평균단가기준수익률: {current_return_avg:.2f}% | 총수익률: {total_return*100:.2f}% | 물타기횟수: {len(long_entries)}회")
                    
                    # 포지션 초기화
                    long_position = 0
                    long_entries = []
        
        # 숏 포지션 물타기 및 청산
        if short_position == 1 and short_entries:
            latest_entry = short_entries[-1]
            entry_price = latest_entry['price']
            entry_count = len(short_entries)
            
            # 물타기 조건 확인 (가격 기반 + 하락 신호)
            if entry_count == 1 and check_martingale_condition(entry_price, current_price, 'SHORT', 1):
                # 1차 물타기: +1% 상승 시 + 하락 신호 확인
                if check_trend_signals(df, i, 'SHORT'):
                    martingale_size = calculate_martingale_size(2)
                    if martingale_size > 0:
                        entry_info = {
                            'time': current_time,
                            'price': current_price,
                            'size': martingale_size,
                            'capital': short_capital * 0.001 * martingale_size
                        }
                        short_entries.append(entry_info)
                        print(f"🔴 숏 1차 물타기: {current_time} | 가격: {current_price:.0f} | 크기: {martingale_size}개 | 상승률: {((current_price-entry_price)/entry_price*100):.2f}% | 총 {len(short_entries)}개")
            
            elif entry_count == 2 and check_martingale_condition(entry_price, current_price, 'SHORT', 2):
                # 2차 물타기: +2% 상승 시 + 하락 신호 확인
                if check_trend_signals(df, i, 'SHORT'):
                    martingale_size = calculate_martingale_size(3)
                    if martingale_size > 0:
                        entry_info = {
                            'time': current_time,
                            'price': current_price,
                            'size': martingale_size,
                            'capital': short_capital * 0.001 * martingale_size
                        }
                        short_entries.append(entry_info)
                        print(f"🔴 숏 2차 물타기: {current_time} | 가격: {current_price:.0f} | 크기: {martingale_size}개 | 상승률: {((current_price-entry_price)/entry_price*100):.2f}% | 총 {len(short_entries)}개")
            
            elif entry_count == 3 and check_martingale_condition(entry_price, current_price, 'SHORT', 3):
                # 3차 물타기: +3% 상승 시 + 하락 신호 확인
                if check_trend_signals(df, i, 'SHORT'):
                    martingale_size = calculate_martingale_size(4)
                    if martingale_size > 0:
                        entry_info = {
                            'time': current_time,
                            'price': current_price,
                            'size': martingale_size,
                            'capital': short_capital * 0.001 * martingale_size
                        }
                        short_entries.append(entry_info)
                        print(f"🔴 숏 3차 물타기: {current_time} | 가격: {current_price:.0f} | 크기: {martingale_size}개 | 상승률: {((current_price-entry_price)/entry_price*100):.2f}% | 총 {len(short_entries)}개")
            
            elif entry_count == 4 and check_martingale_condition(entry_price, current_price, 'SHORT', 4):
                # 4차 물타기: +4% 상승 시 + 하락 신호 확인
                if check_trend_signals(df, i, 'SHORT'):
                    martingale_size = calculate_martingale_size(5)
                    if martingale_size > 0:
                        entry_info = {
                            'time': current_time,
                            'price': current_price,
                            'size': martingale_size,
                            'capital': short_capital * 0.001 * martingale_size
                        }
                        short_entries.append(entry_info)
                        print(f"🔴 숏 4차 물타기: {current_time} | 가격: {current_price:.0f} | 크기: {martingale_size}개 | 상승률: {((current_price-entry_price)/entry_price*100):.2f}% | 총 {len(short_entries)}개")

            # 4차 물타기 후 손절 조건 확인
            if entry_count == 5:  # 4차 물타기까지 완료된 상태
                initial_entry_price = short_entries[0]['price']  # 초기 진입가
                current_return_1x = (initial_entry_price - current_price) / initial_entry_price * 100  # 1배 기준 수익률
                
                # 손절 조건: 4차 물타기 후 -1% 하락 시
                if current_return_1x <= -1.0:
                    # 모든 숏 포지션 손절 청산
                    total_pnl = 0
                    total_invested = 0
                    
                    for entry in short_entries:
                        pnl = (entry['price'] - current_price) / entry['price'] * leverage * (1 - fee)
                        invested = entry['capital']
                        total_pnl += pnl * invested
                        total_invested += invested
                    
                    # 손실률 계산
                    if total_invested > 0:
                        total_return = total_pnl / total_invested
                        short_capital *= (1 + total_return)
                        
                        trades.append({
                            'type': 'SHORT_STOPLOSS',  # 손절 표시
                            'entry_times': [e['time'] for e in short_entries],
                            'entry_prices': [e['price'] for e in short_entries],
                            'exit_time': current_time,
                            'exit_price': current_price,
                            'sizes': [e['size'] for e in short_entries],
                            'total_return': total_return * 100,
                            'pnl': total_pnl,
                            'return_1x': current_return_1x
                        })
                        
                        print(f"🔴 숏 손절: {current_time} | 가격: {current_price:.0f} | 1배기준손실률: {current_return_1x:.2f}% | 총손실률: {total_return*100:.2f}% | 물타기횟수: {len(short_entries)}회")
                    
                    # 포지션 초기화
                    short_position = 0
                    short_entries = []
            
            # 청산 조건: 평균단가 기준 0.3% 이상 수익 + MA 크로스오버 신호
            # 평균단가 기준 수익률 계산
            if short_entries:  # 리스트가 비어있지 않을 때만 실행
                # 평균단가 계산
                total_invested = sum(entry['capital'] for entry in short_entries)
                weighted_avg_price = sum(entry['price'] * entry['capital'] for entry in short_entries) / total_invested
                current_return_avg = (weighted_avg_price - current_price) / weighted_avg_price * 100  # 평균단가 기준 수익률
                
                # 1배 기준 수익률도 계산 (로깅용)
                initial_entry_price = short_entries[0]['price']
                current_return_1x = (initial_entry_price - current_price) / initial_entry_price * 100
                
                if current_return_avg >= 0.3 and ma1_current > ma2_current and ma1_prev <= ma2_prev:  # 0.3% 이상 + 골든크로스
                    # 모든 숏 포지션 청산
                    total_pnl = 0
                    total_invested = 0
                    
                    for entry in short_entries:
                        pnl = (entry['price'] - current_price) / entry['price'] * leverage * (1 - fee)
                        invested = entry['capital']
                        total_pnl += pnl * invested
                        total_invested += invested
                    
                    # 수익률 계산
                    if total_invested > 0:
                        total_return = total_pnl / total_invested
                        short_capital *= (1 + total_return)
                        
                        trades.append({
                            'type': 'SHORT',
                            'entry_times': [e['time'] for e in short_entries],
                            'entry_prices': [e['price'] for e in short_entries],
                            'exit_time': current_time,
                            'exit_price': current_price,
                            'sizes': [e['size'] for e in short_entries],
                            'total_return': total_return * 100,
                            'pnl': total_pnl,
                            'return_1x': current_return_1x  # 1배 기준 수익률 추가
                        })
                        
                        print(f"🔴 숏 청산: {current_time} | 가격: {current_price:.0f} | 1배기준수익률: {current_return_1x:.2f}% | 총수익률: {total_return*100:.2f}% | 물타기횟수: {len(short_entries)}회")
                    
                    # 포지션 초기화
                    short_position = 0
                    short_entries = []
        
        # 자산 곡선 기록
        total_equity = long_capital + short_capital
        equity_curve.append({
            'time': current_time,
            'equity': total_equity,
            'long_capital': long_capital,
            'short_capital': short_capital,
            'price': current_price,
            'long_position': long_position,
            'short_position': short_position
        })
    
    # 마지막 포지션 청산
    if long_position == 1 and long_entries:
        exit_price = df['close'].iloc[-1]
        total_pnl = 0
        total_invested = 0
        
        for entry in long_entries:
            pnl = (exit_price - entry['price']) / entry['price'] * leverage * (1 - fee)
            invested = entry['capital']
            total_pnl += pnl * invested
            total_invested += invested
        
        if total_invested > 0:
            total_return = total_pnl / total_invested
            long_capital *= (1 + total_return)
            
            # 1배 기준 수익률 계산
            initial_entry_price = long_entries[0]['price']
            final_return_1x = (exit_price - initial_entry_price) / initial_entry_price * 100
            
            # 평균단가 기준 수익률 계산
            total_invested = sum(entry['capital'] for entry in long_entries)
            weighted_avg_price = sum(entry['price'] * entry['capital'] for entry in long_entries) / total_invested
            final_return_avg = (exit_price - weighted_avg_price) / weighted_avg_price * 100
            
            trades.append({
                'type': 'LONG',
                'entry_times': [e['time'] for e in long_entries],
                'entry_prices': [e['price'] for e in long_entries],
                'exit_time': df.index[-1],
                'exit_price': exit_price,
                'sizes': [e['size'] for e in long_entries],
                'total_return': total_return * 100,
                'pnl': total_pnl,
                'return_avg': final_return_avg,  # 평균단가 기준 수익률로 변경
                'avg_price': weighted_avg_price  # 평균단가 추가
            })
    
    if short_position == 1 and short_entries:
        exit_price = df['close'].iloc[-1]
        total_pnl = 0
        total_invested = 0
        
        for entry in short_entries:
            pnl = (entry['price'] - exit_price) / entry['price'] * leverage * (1 - fee)
            invested = entry['capital']
            total_pnl += pnl * invested
            total_invested += invested
        
        if total_invested > 0:
            total_return = total_pnl / total_invested
            short_capital *= (1 + total_return)
            
            # 1배 기준 수익률 계산
            initial_entry_price = short_entries[0]['price']
            final_return_1x = (initial_entry_price - exit_price) / initial_entry_price * 100
            
            # 평균단가 기준 수익률 계산
            total_invested = sum(entry['capital'] for entry in short_entries)
            weighted_avg_price = sum(entry['price'] * entry['capital'] for entry in short_entries) / total_invested
            final_return_avg = (weighted_avg_price - exit_price) / weighted_avg_price * 100
            
            trades.append({
                'type': 'SHORT',
                'entry_times': [e['time'] for e in short_entries],
                'entry_prices': [e['price'] for e in short_entries],
                'exit_time': df.index[-1],
                'exit_price': exit_price,
                'sizes': [e['size'] for e in short_entries],
                'total_return': total_return * 100,
                'pnl': total_pnl,
                'return_avg': final_return_avg,  # 평균단가 기준 수익률로 변경
                'avg_price': weighted_avg_price  # 평균단가 추가
            })
    
    # 결과 계산
    final_capital = long_capital + short_capital
    total_return = (final_capital - initial_capital) / initial_capital * 100
    
    # MDD 계산
    peak = initial_capital
    mdd = 0
    for point in equity_curve:
        if point['equity'] > peak:
            peak = point['equity']
        drawdown = (peak - point['equity']) / peak * 100
        if drawdown > mdd:
            mdd = drawdown
    
    return {
        'total_return': total_return,
        'final_capital': final_capital,
        'long_capital': long_capital,
        'short_capital': short_capital,
        'trades': trades,
        'equity_curve': equity_curve,
        'mdd': mdd,
        'trade_count': len(trades)
    }

def main():
    """메인 함수"""
    
    print("🚀 1분봉 MA + 추세 + 물타기 전략 백테스트 시작!")
    print("=" * 60)
    
    # 스크립트 디렉토리
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1분봉 데이터 로드
    data_dir = os.path.join(script_dir, 'data', 'BTC_USDT', '1m')
    
    # 2024년 1월 1분봉 파일만 찾기
    csv_pattern = '2024-01.csv'
    csv_files = glob.glob(os.path.join(data_dir, csv_pattern))
    
    if not csv_files:
        print(f"❌ {csv_pattern} 패턴의 파일을 찾을 수 없습니다.")
        print(f"📁 데이터 디렉토리: {data_dir}")
        return
    
    print(f"📊 발견된 1분봉 파일 수: {len(csv_files)}개")
    
    # 모든 CSV 파일을 하나로 합치기
    all_data = []
    for csv_file in sorted(csv_files):
        try:
            df = pd.read_csv(csv_file, index_col='timestamp', parse_dates=True)
            all_data.append(df)
            print(f"✅ {os.path.basename(csv_file)} 로드 완료: {len(df)}개 캔들")
        except Exception as e:
            print(f"❌ {csv_file} 로드 실패: {e}")
    
    if not all_data:
        print("데이터를 가져올 수 없습니다.")
        return
    
    # 모든 데이터 합치기
    df_1m = pd.concat(all_data, ignore_index=False)
    df_1m = df_1m.sort_index()  # 시간순 정렬
    df_1m = df_1m.drop_duplicates()  # 중복 제거
    
    print(f"✅ 전체 데이터 로드 완료: {len(df_1m)}개 캔들")
    print(f"기간: {df_1m.index[0]} ~ {df_1m.index[-1]}")
    
    # 백테스트 설정
    ma1 = 5   # 빠른 MA
    ma2 = 20  # 느린 MA
    initial_capital = 10000  # 초기 자본
    leverage = 7  # 레버리지
    fee = 0.001  # 수수료 0.1%
    
    print(f"\n📊 백테스트 설정:")
    print(f"MA 설정: {ma1}MA + {ma2}MA")
    print(f"초기 자본: {initial_capital:,} USDT")
    print(f"레버리지: {leverage}배")
    print(f"수수료: {fee*100:.1f}%")
    print(f"전략: 롱/숏 50:50 + 물타기 (가격 기반: -1%/-2%/-3%/-4% + 상승신호)")
    print(f"추세 지표: 5가지 (모멘텀, 연속성, BB, RSI, 거래량)")
    
    # 백테스트 실행
    print(f"\n🔄 백테스트 실행 중...")
    result = backtest_martingale_strategy(df_1m, ma1, ma2, initial_capital, leverage, fee)
    
    if result:
        print(f"\n✅ 백테스트 완료!")
        print("=" * 60)
        print(f"📈 전체 수익률: {result['total_return']:.2f}%")
        print(f"💰 최종 자본: {result['final_capital']:,.2f} USDT")
        print(f"📊 롱 자본: {result['long_capital']:,.2f} USDT")
        print(f"📉 숏 자본: {result['short_capital']:,.2f} USDT")
        print(f"🔄 총 거래 수: {result['trade_count']}회")
        print(f"📉 최대 MDD: {result['mdd']:.2f}%")
        
        # 거래 내역 요약
        if result['trades']:
            print(f"\n📋 거래 내역 요약:")
            long_trades = [t for t in result['trades'] if t['type'] == 'LONG']
            short_trades = [t for t in result['trades'] if t['type'] == 'SHORT']
            
            print(f"롱 거래: {len(long_trades)}회")
            print(f"숏 거래: {len(short_trades)}회")
            
            # 수익 거래 분석
            profitable_trades = [t for t in result['trades'] if t['total_return'] > 0]
            if profitable_trades:
                avg_profit = sum(t['total_return'] for t in profitable_trades) / len(profitable_trades)
                print(f"수익 거래 평균: {avg_profit:.2f}%")
            
            # 손실 거래 분석
            loss_trades = [t for t in result['trades'] if t['total_return'] < 0]
            if loss_trades:
                avg_loss = sum(t['total_return'] for t in loss_trades) / len(loss_trades)
                print(f"손실 거래 평균: {avg_loss:.2f}%")
            
            # 승률 계산
            win_rate = len(profitable_trades) / len(result['trades']) * 100
            print(f"승률: {win_rate:.1f}%")
        
        # 결과 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_filename = f"MA_Trend_1m_Martingale_Result_BTC_USDT_{timestamp}.json"
        result_path = os.path.join(script_dir, 'logs', result_filename)
        
        # 로그 디렉토리 생성
        os.makedirs(os.path.dirname(result_path), exist_ok=True)
        
        # 결과 데이터 구성
        result_data = {
            'strategy': 'MA_Trend_1m_Martingale',
            'parameters': {
                'ma1': ma1,
                'ma2': ma2,
                'initial_capital': initial_capital,
                'leverage': leverage
            },
            'performance': {
                'total_return': result['total_return'],
                'final_capital': result['final_capital'],
                'long_capital': result['long_capital'],
                'short_capital': result['short_capital'],
                'trade_count': result['trade_count'],
                'mdd': result['mdd']
            },
            'trades': result['trades'],
            'equity_curve': result['equity_curve']
        }
        
        # JSON 파일로 저장
        import json
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 결과가 {result_path}에 저장되었습니다.")
        
        # 그래프 생성
        print(f"\n📊 그래프 생성 중...")
        try:
            create_performance_graph(result, df_1m, ma1, ma2, result_path.replace('.json', '.png'))
            print(f"✅ 그래프가 {result_path.replace('.json', '.png')}에 저장되었습니다.")
        except Exception as e:
            print(f"❌ 그래프 생성 실패: {e}")
    
    else:
        print("❌ 백테스트 실패")

def create_performance_graph(result, df, ma1, ma2, graph_path):
    """성과 그래프 생성"""
    
    # 4개 서브플롯 생성
    fig, axes = plt.subplots(4, 1, figsize=(20, 16))
    
    # 1. 비트코인 1분봉 + MA
    ax1 = axes[0]
    
    # 가격 데이터
    ax1.plot(df.index, df['close'], 'k-', linewidth=0.5, alpha=0.8, label='BTC 1M')
    
    # MA 선들
    ax1.plot(df.index, df[f'ma_{ma1}'], 'r-', linewidth=1, alpha=0.7, label=f'{ma1}MA')
    ax1.plot(df.index, df[f'ma_{ma2}'], 'b-', linewidth=1, alpha=0.7, label=f'{ma2}MA')
    
    # 거래 내역 화살표 표시
    for trade in result['trades']:
        if trade['type'] == 'LONG':
            # 진입 지점들 (녹색 화살표 위)
            for entry_time, entry_price in zip(trade['entry_times'], trade['entry_prices']):
                ax1.scatter(entry_time, entry_price, color='green', marker='^', s=50, alpha=0.8, zorder=5)
            # 청산 지점 (빨간색 화살표 아래)
            ax1.scatter(trade['exit_time'], trade['exit_price'], color='red', marker='v', s=100, alpha=0.8, zorder=5)
        else:  # SHORT
            # 진입 지점들 (빨간색 화살표 아래)
            for entry_time, entry_price in zip(trade['entry_times'], trade['entry_prices']):
                ax1.scatter(entry_time, entry_price, color='red', marker='v', s=50, alpha=0.8, zorder=5)
            # 청산 지점 (녹색 화살표 위)
            ax1.scatter(trade['exit_time'], trade['exit_price'], color='green', marker='^', s=100, alpha=0.8, zorder=5)
    
    ax1.set_title('BTC 1분봉 + MA 이동평균선 + 거래내역', fontsize=14, fontweight='bold')
    ax1.set_ylabel('가격 (USDT)', fontsize=12)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. 거래별 수익률
    ax2 = axes[1]
    
    if result['trades']:
        trade_times = [trade['exit_time'] for trade in result['trades']]
        trade_returns = [trade['total_return'] for trade in result['trades']]
        
        colors = ['green' if ret > 0 else 'red' for ret in trade_returns]
        bars = ax2.bar(range(len(trade_times)), trade_returns, color=colors, alpha=0.7)
        
        # 수익률 값 표시
        for i, (bar, ret) in enumerate(zip(bars, trade_returns)):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + (0.1 if height > 0 else -0.1),
                    f'{ret:.1f}%', ha='center', va='bottom' if height > 0 else 'top')
        
        ax2.set_title('거래별 수익률', fontsize=14, fontweight='bold')
        ax2.set_ylabel('수익률 (%)', fontsize=12)
        ax2.set_xlabel('거래 순서', fontsize=12)
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax2.grid(True, alpha=0.3)
    
    # 3. 자산 곡선
    ax3 = axes[2]
    
    if result['equity_curve']:
        times = [point['time'] for point in result['equity_curve']]
        equities = [point['equity'] for point in result['equity_curve']]
        long_capitals = [point['long_capital'] for point in result['equity_curve']]
        short_capitals = [point['short_capital'] for point in result['equity_curve']]
        
        ax3.plot(times, equities, 'b-', linewidth=2, label='합산 자산', alpha=0.8)
        ax3.plot(times, long_capitals, 'g-', linewidth=1, label='롱 자산', alpha=0.6)
        ax3.plot(times, short_capitals, 'r-', linewidth=1, label='숏 자산', alpha=0.6)
        ax3.axhline(y=10000, color='black', linestyle='--', alpha=0.7, label='초기 자본')
        
        ax3.set_title('자산 곡선 (롱/숏/합산)', fontsize=14, fontweight='bold')
        ax3.set_ylabel('자산 (USDT)', fontsize=12)
        ax3.legend()
        ax3.grid(True, alpha=0.3)
    
    # 4. MDD 현황
    ax4 = axes[3]
    
    if result['equity_curve']:
        # MDD 계산 및 플롯
        peak = 10000
        mdd_values = []
        mdd_times = []
        
        for point in result['equity_curve']:
            if point['equity'] > peak:
                peak = point['equity']
            drawdown = (peak - point['equity']) / peak * 100
            mdd_values.append(drawdown)
            mdd_times.append(point['time'])
        
        ax4.fill_between(mdd_times, mdd_values, 0, alpha=0.3, color='red', label='MDD')
        ax4.plot(mdd_times, mdd_values, 'r-', linewidth=1, alpha=0.8)
        
        # 최대 MDD 지점 표시
        max_mdd_idx = np.argmax(mdd_values)
        max_mdd = mdd_values[max_mdd_idx]
        max_mdd_time = mdd_times[max_mdd_idx]
        
        ax4.scatter(max_mdd_time, max_mdd, color='darkred', s=100, zorder=5, 
                   label=f'최대 MDD: {max_mdd:.2f}%')
        ax4.text(max_mdd_time, max_mdd + 0.5, f'{max_mdd:.2f}%', 
                 ha='center', va='bottom', fontweight='bold')
        
        ax4.set_title('MDD (Maximum Drawdown) 현황', fontsize=14, fontweight='bold')
        ax4.set_ylabel('MDD (%)', fontsize=12)
        ax4.set_xlabel('시간', fontsize=12)
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        ax4.invert_yaxis()  # MDD는 위에서 아래로 표시
    
    # x축 날짜 포맷
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=7))
        ax.tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.savefig(graph_path, dpi=300, bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    main()
