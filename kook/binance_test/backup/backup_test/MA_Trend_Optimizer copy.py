#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MA + 추세 하이브리드 전략 최적화 도구 (독립 실행)
- 2024년 1월부터 현재까지 월별 최적화
- 각 월마다 이전 500개 캔들로 MA 계산
- 최적 MA값과 추세 추종 파라미터 도출
"""

import os
import json
import datetime
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional

def load_data_for_optimization(year: int, month: int, data_dir: str, lookback_candles: int = 500, timeframe: str = '4h') -> pd.DataFrame:
    """
    최적화를 위한 데이터 로드
    - MA 계산용 데이터 (과거 500개 캔들)만 수집
    - 백테스트는 별도 파일에서 실행
    """
    print(f"📊 {year}년 {month}월 MA 계산용 데이터 로드 중...")
    
    # MA 계산용 데이터 (과거 500개 캔들)
    print(f"🔧 MA 계산용 과거 데이터 수집 중...")
    
    # 모든 년도 데이터를 순서대로 수집하여 과거 500개 캔들 확보
    all_historical_data = []
    
    # 이전 년도부터 현재 년도까지 순서대로 데이터 수집
    for check_year in range(2023, year + 1):
        year_file = os.path.join(data_dir, f'BTCUSDT_{timeframe}_{check_year}.csv')
        if os.path.exists(year_file):
            year_df = pd.read_csv(year_file)
            year_df['datetime'] = pd.to_datetime(year_df['datetime'])
            year_df.set_index('datetime', inplace=True)
            
            # 현재 월 이전까지만 수집 (MA 계산용)
            if check_year == year:
                # 현재 년도면 현재 월 이전까지만
                current_month_start = datetime.datetime(year, month, 1)
                year_mask = year_df.index < current_month_start
            else:
                # 이전 년도면 전체
                year_mask = year_df.index < datetime.datetime(year, 1, 1)
            
            if year_mask.any():
                year_data = year_df[year_mask]
                all_historical_data.append(year_data)
                print(f"   📊 {check_year}년: {len(year_data)}개 캔들")
    
    if not all_historical_data:
        print(f"❌ 과거 데이터를 찾을 수 없습니다.")
        return None
    
    # 모든 과거 데이터 결합 및 정렬
    combined_historical = pd.concat(all_historical_data).sort_index()
    
    # 과거 500개 캔들만 사용 (MA 계산용)
    if len(combined_historical) > lookback_candles:
        ma_df = combined_historical.tail(lookback_candles)
        print(f"   📊 MA 계산용 데이터 제한: {lookback_candles}개 캔들 (최근)")
    else:
        ma_df = combined_historical
        print(f"   📊 MA 계산용 데이터: {len(ma_df)}개 캔들 (전체)")
    
    print(f"   📊 MA 계산 기간: {ma_df.index[0].strftime('%Y-%m-%d %H:%M')} ~ {ma_df.index[-1].strftime('%Y-%m-%d %H:%M')}")
    
    print(f"✅ MA 계산용 데이터 로드 완료:")
    print(f"   MA 계산용 (과거): {len(ma_df)}개 캔들")
    
    return ma_df

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """기술적 지표 계산"""
    # MA 계산
    for ma in [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]:
        df[f'ma_{ma}'] = df['close'].rolling(ma).mean()
    
    # 모멘텀
    df['momentum_5'] = df['close'].pct_change(5)
    df['momentum_10'] = df['close'].pct_change(10)
    
    # 추세 연속성
    df['trend_direction'] = np.where(df['close'] > df['close'].shift(1), 1, -1)
    df['trend_continuity'] = df['trend_direction'].rolling(5).sum()
    
    # 볼린저 밴드
    df['bb_upper'] = df['close'].rolling(20).mean() + 2 * df['close'].rolling(20).std()
    df['bb_lower'] = df['close'].rolling(20).mean() - 2 * df['close'].rolling(20).std()
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

def backtest_strategy(df: pd.DataFrame, ma1: int, ma2: int, trend_params: Dict, 
                     initial_capital: float = 10000, leverage: int = 5, fee: float = 0.001,
                     strategy_type: str = 'LONG') -> Optional[Dict]:
    """전략 백테스트 (롱/숏 지원, 확장된 추세 파라미터)"""
    # MA 계산
    df[f'ma_{ma1}'] = df['close'].rolling(ma1).mean()
    df[f'ma_{ma2}'] = df['close'].rolling(ma2).mean()
    
    # 지표 계산
    df = calculate_indicators(df)
    df.dropna(inplace=True)
    
    if len(df) < 100:
        return None
    
    # 실제 백테스트 시작 인덱스 (MA 계산용 데이터 제외)
    actual_start_idx = max(ma1, ma2, 20)
    
    # 백테스트 변수
    position = 0  # 0: 없음, 1: 롱, -1: 숏
    entry_price = 0
    entry_time = None
    position_size = 0
    total_capital = initial_capital
    equity_curve = []
    trades = []
    
    # 백테스트 실행
    for i in range(actual_start_idx, len(df)):
        current_price = df['close'].iloc[i]
        current_time = df.index[i]
        
        # MA 신호
        ma1_prev = df[f'ma_{ma1}'].iloc[i-1]
        ma2_prev = df[f'ma_{ma2}'].iloc[i-1]
        ma1_prev2 = df[f'ma_{ma1}'].iloc[i-2]
        ma2_prev2 = df[f'ma_{ma2}'].iloc[i-2]
        close_prev = df['close'].iloc[i-1]
        
        # 확장된 추세 신호
        momentum_period = trend_params.get('momentum_period', 5)
        momentum_signal = df['close'].pct_change(momentum_period).iloc[i]
        momentum_10 = df['momentum_10'].iloc[i]
        trend_continuity = df['trend_continuity'].iloc[i]
        bb_position = df['bb_position'].iloc[i]
        rsi = df['rsi'].iloc[i]
        
        # 볼륨 필터
        volume_filter = True
        if 'volume' in df.columns:
            current_volume = df['volume'].iloc[i]
            avg_volume = df['volume'].rolling(20).mean().iloc[i]
            volume_multiplier = trend_params.get('volume_multiplier', 1.0)
            volume_filter = current_volume > avg_volume * volume_multiplier
        
        # 진입 신호
        if position == 0:
            if strategy_type == 'LONG':
                # 롱 진입 신호 (확장된 조건)
                ma_signal = (close_prev >= ma1_prev and ma1_prev > ma1_prev2 and 
                            close_prev >= ma2_prev and ma2_prev > ma2_prev2)
                
                bb_threshold = trend_params.get('bb_threshold', 0.5)
                trend_signal = (momentum_signal > 0 and momentum_10 > 0 and
                              trend_continuity >= trend_params['trend_continuity_min'] and
                              bb_position > bb_threshold and
                              rsi > trend_params['rsi_oversold'] and
                              rsi < trend_params['rsi_overbought'] and
                              volume_filter)
                
                if ma_signal and trend_signal:
                    position = 1
                    entry_price = current_price
                    entry_time = current_time
                    position_size = (total_capital * leverage) / current_price
                    
            elif strategy_type == 'SHORT':
                # 숏 진입 신호 (확장된 조건)
                ma_signal = (close_prev <= ma1_prev and ma1_prev < ma1_prev2 and 
                            close_prev <= ma2_prev and ma2_prev < ma2_prev2)
                
                bb_threshold = trend_params.get('bb_threshold', 0.5)
                trend_signal = (momentum_signal < 0 and momentum_10 < 0 and
                              trend_continuity <= -trend_params['trend_continuity_min'] and
                              bb_position < (1 - bb_threshold) and
                              rsi > trend_params['rsi_overbought'] and
                              volume_filter)
                
                if ma_signal and trend_signal:
                    position = -1
                    entry_price = current_price
                    entry_time = current_time
                    position_size = (total_capital * leverage) / current_price
        
        # 청산 신호
        elif position == 1:  # 롱 포지션
            # 롱 청산: MA 데드크로스 또는 손절
            if (close_prev < ma1_prev and ma1_prev < ma1_prev2) or \
               (close_prev < ma2_prev and ma2_prev < ma2_prev2) or \
               (current_price <= entry_price * 0.95):  # 5% 손절
                
                exit_price = current_price
                pnl = (exit_price - entry_price) / entry_price * leverage
                total_capital *= (1 + pnl - fee * 2)
                
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'position_size': position_size
                })
                
                position = 0
                entry_price = 0
                entry_time = None
                position_size = 0
                
        elif position == -1:  # 숏 포지션
            # 숏 청산: MA 골든크로스 또는 손절
            if (close_prev > ma1_prev and ma1_prev > ma1_prev2) or \
               (close_prev > ma2_prev and ma2_prev > ma2_prev2) or \
               (current_price >= entry_price * 1.05):  # 5% 손절
                
                exit_price = current_price
                pnl = (entry_price - exit_price) / entry_price * leverage
                total_capital *= (1 + pnl - fee * 2)
                
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'position_size': position_size
                })
                
                position = 0
                entry_price = 0
                entry_time = None
                position_size = 0
        
        # 자산 곡선 기록
        equity_curve.append({
            'time': current_time,
            'equity': total_capital,
            'price': current_price
        })
    
    # 마지막 포지션 청산
    if position != 0:
        exit_price = df['close'].iloc[-1]
        if strategy_type == 'LONG':
            pnl = (exit_price - entry_price) / entry_price * leverage
        else:
            pnl = (entry_price - exit_price) / entry_price * leverage
        
        total_capital *= (1 + pnl - fee)
        trades.append({
            'entry_time': entry_time,
            'exit_time': df.index[-1],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'position_size': position_size
        })
    
    # 결과 계산
    if len(trades) == 0:
        return None
    
    total_return = (total_capital - initial_capital) / initial_capital * 100
    win_trades = len([t for t in trades if t['pnl'] > 0])
    
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
        'final_capital': total_capital,
        'trade_count': len(trades),
        'win_trades': win_trades,
        'mdd': mdd,
        'equity_curve': equity_curve,
        'trades': trades
    }

def optimize_ma_and_trend_together(df: pd.DataFrame, strategy_type: str = 'LONG') -> Optional[Dict]:
    """MA + 추세 파라미터 통합 최적화"""
    print(f"🔍 MA + 추세 파라미터 통합 최적화 중... ({strategy_type})")
    
    best_score = -999999
    best_result = None
    
    # MA 핵심 값들 (확장된 버전)
    ma1_values = [3, 4, 5, 6, 7, 8, 10, 12, 15, 18, 21]  # 11개
    ma2_values = [20, 25, 30, 40, 50, 60, 80, 100, 120, 150, 180, 200]  # 12개
    
    # 추세 파라미터 범위
    trend_ranges = {
        'trend_continuity_min': [2, 3],  # 2개
        'rsi_oversold': [20, 25],   # 2개
        'rsi_overbought': [70, 75, 80],     # 3개
        'momentum_period': [3, 4, 5],            # 3개
        'bb_threshold': [0.3, 0.4],      # 2개
        'volume_multiplier': [1.0, 1.1, 1.2]        # 3개
    }
    
    # 총 조합 수 계산
    ma_combinations = 0
    for ma1 in ma1_values:
        for ma2 in ma2_values:
            if ma1 < ma2:  # MA1 < MA2 조건
                ma_combinations += 1
    
    trend_combinations = (len(trend_ranges['trend_continuity_min']) * 
                         len(trend_ranges['rsi_oversold']) * 
                         len(trend_ranges['rsi_overbought']) * 
                         len(trend_ranges['momentum_period']) * 
                         len(trend_ranges['bb_threshold']) * 
                         len(trend_ranges['volume_multiplier']))
    
    total_combinations = ma_combinations * trend_combinations
    
    print(f"📊 총 {total_combinations}개 조합 테스트 중... (MA + 추세 통합)")
    print(f"   MA 조합: {ma_combinations}개 (MA1: {ma1_values}, MA2: {ma2_values})")
    print(f"   추세 조합: {trend_combinations}개")
    
    current_combination = 0
    successful_combinations = 0
    failed_combinations = 0
    
    for ma1 in ma1_values:
        for ma2 in ma2_values:
            if ma1 >= ma2:  # MA1 < MA2 조건
                continue
                
            for continuity in trend_ranges['trend_continuity_min']:
                for oversold in trend_ranges['rsi_oversold']:
                    for overbought in trend_ranges['rsi_overbought']:
                        if oversold >= overbought:
                            continue
                            
                        for momentum_period in trend_ranges['momentum_period']:
                            for bb_threshold in trend_ranges['bb_threshold']:
                                for volume_mult in trend_ranges['volume_multiplier']:
                                    current_combination += 1
                                    
                                    if current_combination % 1000 == 0:
                                        progress = (current_combination / total_combinations) * 100
                                        print(f"진행률: {progress:.1f}% ({current_combination}/{total_combinations})")
                                    
                                    # 추세 파라미터 구성
                                    if strategy_type == 'SHORT':
                                        # 숏 전략용 파라미터 조정
                                        trend_params = {
                                            'trend_continuity_min': continuity,
                                            'rsi_oversold': overbought,  # 숏 전략용 RSI 과매수
                                            'rsi_overbought': oversold,  # 숏 전략용 RSI 과매도
                                            'momentum_period': momentum_period,
                                            'bb_threshold': bb_threshold,
                                            'volume_multiplier': volume_mult
                                        }
                                    else:
                                        # 롱 전략용 파라미터
                                        trend_params = {
                                            'trend_continuity_min': continuity,
                                            'rsi_oversold': oversold,
                                            'rsi_overbought': overbought,
                                            'momentum_period': momentum_period,
                                            'bb_threshold': bb_threshold,
                                            'volume_multiplier': volume_mult
                                        }
                                    
                                    result = backtest_strategy(df.copy(), ma1, ma2, trend_params, strategy_type=strategy_type)
                                    
                                    if result and result['trade_count'] > 0:
                                        successful_combinations += 1
                                        win_rate = result['win_trades'] / result['trade_count']
                                        # 점수 계산
                                        score = result['total_return'] - result['mdd'] + (win_rate * 15)
                                        
                                        if score > best_score:
                                            best_score = score
                                            best_result = result
                                            best_result['ma1'] = ma1
                                            best_result['ma2'] = ma2
                                            best_result['trend_params'] = trend_params
                                            best_result['score'] = score
                                            
                                            print(f"🎯 새로운 최적 조합 발견!")
                                            print(f"   MA1={ma1}, MA2={ma2}")
                                            print(f"   추세 파라미터: {trend_params}")
                                            print(f"   수익률={result['total_return']:.2f}%, MDD={result['mdd']:.2f}%, 승률={win_rate*100:.1f}%")
                                            print(f"   점수={score:.2f}")
                                    else:
                                        failed_combinations += 1
    
    print(f"📊 최적화 결과 요약:")
    print(f"   성공한 조합: {successful_combinations}개")
    print(f"   실패한 조합: {failed_combinations}개")
    print(f"   총 테스트: {current_combination}개")
    
    if best_result:
        print(f"✅ 최적 MA + 추세 파라미터 선택:")
        print(f"   MA1={best_result['ma1']}, MA2={best_result['ma2']}")
        print(f"   추세 파라미터: {best_result['trend_params']}")
        print(f"   최종 점수: {best_result['score']:.2f}")
    else:
        print(f"❌ 유효한 조합을 찾을 수 없습니다.")
        if strategy_type == 'SHORT':
            print(f"   💡 숏 전략의 경우 진입 조건이 너무 엄격할 수 있습니다.")
    
    return best_result

def optimize_trend_parameters(df: pd.DataFrame, ma1: int, ma2: int) -> Optional[Dict]:
    """추세 파라미터 최적화 (확장된 20-30개 전략)"""
    print(f"🔍 추세 파라미터 최적화 중... (MA1={ma1}, MA2={ma2})")
    
    best_score = -999999
    best_result = None
    
    # 확장된 추세 전략 파라미터 (20-30개 조합)
    # trend_ranges = {
    #     'trend_continuity_min': [2, 3, 4, 5, 6, 7, 8],  # 7개
    #     'rsi_oversold': [20, 25, 30, 35, 40, 45, 50],   # 7개
    #     'rsi_overbought': [70, 75, 80, 85, 90, 95],     # 7개
    #     'momentum_period': [3, 5, 7, 10, 14],            # 5개
    #     'bb_threshold': [0.3, 0.4, 0.5, 0.6, 0.7],      # 5개
    #     'volume_multiplier': [1.0, 1.2, 1.5, 2.0]        # 4개
    # }
    trend_ranges = {
        'trend_continuity_min': [1, 2, 3],  # 2개
        'rsi_oversold': [20, 25],   # 7개
        'rsi_overbought': [70, 75, 80],     # 7개
        'momentum_period': [3, 4, 5],            # 5개
        'bb_threshold': [0.3, 0.4],      # 5개
        'volume_multiplier': [1.0, 1.1, 1.2]        # 4개
    }
    
    total_combinations = (len(trend_ranges['trend_continuity_min']) * 
                         len(trend_ranges['rsi_oversold']) * 
                         len(trend_ranges['rsi_overbought']) * 
                         len(trend_ranges['momentum_period']) * 
                         len(trend_ranges['bb_threshold']) * 
                         len(trend_ranges['volume_multiplier']))
    
    print(f"📊 총 {total_combinations}개 조합 테스트 중...")
    current_combination = 0
    
    for continuity in trend_ranges['trend_continuity_min']:
        for oversold in trend_ranges['rsi_oversold']:
            for overbought in trend_ranges['rsi_overbought']:
                if oversold >= overbought:
                    continue
                    
                for momentum_period in trend_ranges['momentum_period']:
                    for bb_threshold in trend_ranges['bb_threshold']:
                        for volume_mult in trend_ranges['volume_multiplier']:
                            current_combination += 1
                            
                            if current_combination % 100 == 0:
                                progress = (current_combination / total_combinations) * 100
                                print(f"진행률: {progress:.1f}% ({current_combination}/{total_combinations})")
                            
                            trend_params = {
                                'trend_continuity_min': continuity,
                                'rsi_oversold': oversold,
                                'rsi_overbought': overbought,
                                'momentum_period': momentum_period,
                                'bb_threshold': bb_threshold,
                                'volume_multiplier': volume_mult
                            }
                            
                            result = backtest_strategy(df.copy(), ma1, ma2, trend_params)
                            
                            if result and result['trade_count'] > 0:
                                win_rate = result['win_trades'] / result['trade_count']
                                # 다양한 점수 계산 방식
                                score_variations = [
                                    result['total_return'] - result['mdd'] + (win_rate * 10),  # 기본
                                    result['total_return'] * 0.7 - result['mdd'] * 0.3 + (win_rate * 15),  # 수익률 중시
                                    result['total_return'] * 0.5 - result['mdd'] * 0.5 + (win_rate * 20),  # 안정성 중시
                                    result['total_return'] * 0.3 - result['mdd'] * 0.7 + (win_rate * 25)   # 리스크 관리 중시
                                ]
                                
                                # 최고 점수 선택
                                max_score = max(score_variations)
                                
                                if max_score > best_score:
                                    best_score = max_score
                                    best_result = result
                                    best_result['trend_params'] = trend_params
                                    best_result['score'] = max_score
                                    
                                    print(f"🎯 새로운 최적 전략 발견!")
                                    print(f"   연속성={continuity}, RSI과매도={oversold}, RSI과매수={overbought}")
                                    print(f"   모멘텀={momentum_period}, BB임계값={bb_threshold}, 볼륨배수={volume_mult}")
                                    print(f"   수익률={result['total_return']:.2f}%, MDD={result['mdd']:.2f}%, 승률={win_rate*100:.1f}%")
                                    print(f"   점수={max_score:.2f}")
    
    if best_result:
        print(f"✅ 최적 추세 전략 선택:")
        print(f"   파라미터: {best_result['trend_params']}")
        print(f"   최종 점수: {best_result['score']:.2f}")
    
    return best_result

def load_existing_parameters(json_file: str) -> Dict:
    """기존 파라미터 로드"""
    if os.path.exists(json_file):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_parameters(json_file: str, parameters: Dict):
    """파라미터 저장"""
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(parameters, f, ensure_ascii=False, indent=2, default=str)

def main():
    """메인 함수"""
    print("🚀 MA + 추세 하이브리드 전략 최적화 도구 시작!")
    
    # 설정
    start_year = 2024
    start_month = 1
    end_year = datetime.datetime.now().year
    end_month = datetime.datetime.now().month
    lookback_candles = 500
    
    # 차트 타임프레임 선택
    print("\n📊 차트 타임프레임을 선택하세요:")
    print("1. 3분 (단타, 10배 레버리지 권장)")
    print("2. 1시간 (스윙, 7배 레버리지 권장)")
    print("3. 4시간 (중기, 5배 레버리지 권장)")
    print("4. 1일 (장기, 3배 레버리지 권장)")
    
    while True:
        try:
            timeframe_choice = input("선택 (1-4): ").strip()
            if timeframe_choice in ['1', '2', '3', '4']:
                break
            else:
                print("1-4 중에서 선택해주세요.")
        except KeyboardInterrupt:
            print("\n❌ 프로그램이 중단되었습니다.")
            return
    
    # 타임프레임별 설정
    timeframe_configs = {
        '1': {'name': '3m', 'folder': '3m', 'leverage': 10, 'description': '단타 (10배 레버리지)'},
        '2': {'name': '1h', 'folder': '1h', 'leverage': 7, 'description': '스윙 (7배 레버리지)'},
        '3': {'name': '4h', 'folder': '4h', 'leverage': 5, 'description': '중기 (5배 레버리지)'},
        '4': {'name': '1d', 'folder': '1d', 'leverage': 3, 'description': '장기 (3배 레버리지)'}
    }
    
    selected_config = timeframe_configs[timeframe_choice]
    print(f"\n✅ 선택된 타임프레임: {selected_config['description']}")
    
    print(f"📅 최적화 기간: {start_year}년 {start_month}월 ~ {end_year}년 {end_month}월")
    print(f"🔍 각 월마다 이전 {lookback_candles}개 캔들로 MA 계산")
    
    # 파일 경로
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data", "BTCUSDT", selected_config['folder'])
    json_file = os.path.join(script_dir, f"MA_Trend_Optimizer_{selected_config['name']}.json")
    
    if not os.path.exists(data_dir):
        print(f"❌ 데이터 디렉토리를 찾을 수 없습니다: {data_dir}")
        print(f"💡 {selected_config['folder']} 폴더에 BTCUSDT 데이터가 있는지 확인해주세요.")
        return
    
    # 기존 파라미터 로드
    existing_params = load_existing_parameters(json_file)
    
    # 월별 최적화
    for year in range(start_year, end_year + 1):
        for month in range(start_month, end_month + 1):
            if year == datetime.datetime.now().year and month > datetime.datetime.now().month:
                break
            
            print(f"\n{'='*80}")
            print(f"🎯 {year}년 {month}월 최적화 시작")
            print(f"{'='*80}")
            
            # 기존 데이터 확인 (롱/숏 전략이 모두 있으면 건너뛰기)
            month_key = f"{year}_{month:02d}"
            if month_key in existing_params:
                # 롱/숏 전략이 모두 있는지 확인
                if "long_strategy" in existing_params[month_key] and "short_strategy" in existing_params[month_key]:
                    print(f"⏭️  {year}년 {month}월은 이미 롱/숏 전략 모두 최적화 완료. 건너뜁니다.")
                    continue
                else:
                    print(f"🔍 {year}년 {month}월: 일부 전략이 누락됨. 누락된 전략만 추가 최적화합니다.")
                    # 기존 데이터 유지하면서 누락된 전략만 추가
                    if "long_strategy" not in existing_params[month_key]:
                        existing_params[month_key]["long_strategy"] = {}
                    if "short_strategy" not in existing_params[month_key]:
                        existing_params[month_key]["short_strategy"] = {}
                    if "optimization_info" not in existing_params[month_key]:
                        existing_params[month_key]["optimization_info"] = {}
            
            # 데이터 로드 (MA 계산용만)
            ma_df = load_data_for_optimization(year, month, data_dir, lookback_candles, selected_config['name'])
            if ma_df is None:
                print(f"❌ {year}년 {month}월 데이터 로드 실패. 건너뜁니다.")
                continue
            
            # MA 계산용 데이터만 사용
            combined_df = ma_df.copy()
            
            # 1단계: MA + 추세 파라미터 통합 최적화 (롱 전략)
            if month_key not in existing_params or "long_strategy" not in existing_params[month_key] or not existing_params[month_key]["long_strategy"]:
                print(f"\n🔧 1단계: MA + 추세 파라미터 통합 최적화 (롱 전략)")
                long_result = optimize_ma_and_trend_together(combined_df.copy(), strategy_type='LONG')
                
                if not long_result:
                    print(f"❌ 롱 전략 최적화 실패. {year}년 {month}월 건너뜁니다.")
                    continue
                    
                ma_result_long = {
                    'ma1': long_result['ma1'],
                    'ma2': long_result['ma2']
                }
                trend_result_long = {
                    'trend_params': long_result['trend_params']
                }
            else:
                print(f"⏭️  롱 전략은 이미 최적화 완료. 기존 값 사용: MA1={existing_params[month_key]['long_strategy']['ma1']}, MA2={existing_params[month_key]['long_strategy']['ma2']}")
                ma_result_long = {
                    'ma1': existing_params[month_key]['long_strategy']['ma1'],
                    'ma2': existing_params[month_key]['long_strategy']['ma2']
                }
                trend_result_long = {
                    'trend_params': existing_params[month_key]['long_strategy']['trend_params']
                }
            
            # 2단계: MA + 추세 파라미터 통합 최적화 (숏 전략)
            if month_key not in existing_params or "short_strategy" not in existing_params[month_key] or not existing_params[month_key]["short_strategy"]:
                print(f"\n🔧 2단계: MA + 추세 파라미터 통합 최적화 (숏 전략)")
                short_result = optimize_ma_and_trend_together(combined_df.copy(), strategy_type='SHORT')
                
                if not short_result:
                    print(f"⚠️  숏 전략 최적화 실패. 롱 전략만 저장합니다.")
                    ma_result_short = ma_result_long.copy()
                    trend_result_short = trend_result_long.copy()
                else:
                    ma_result_short = {
                        'ma1': short_result['ma1'],
                        'ma2': short_result['ma2']
                    }
                    trend_result_short = {
                        'trend_params': short_result['trend_params']
                    }
            else:
                print(f"⏭️  숏 전략은 이미 최적화 완료. 기존 값 사용: MA1={existing_params[month_key]['short_strategy']['ma1']}, MA2={existing_params[month_key]['short_strategy']['ma2']}")
                ma_result_short = {
                    'ma1': existing_params[month_key]['short_strategy']['ma1'],
                    'ma2': existing_params[month_key]['short_strategy']['ma2']
                }
                trend_result_short = {
                    'trend_params': existing_params[month_key]['short_strategy']['trend_params']
                }
            
            # 결과 저장
            month_key = f"{year}_{month:02d}"
            month_data = {
                "long_strategy": {
                    "ma1": ma_result_long['ma1'],
                    "ma2": ma_result_long['ma2'],
                    "trend_params": trend_result_long['trend_params']
                },
                "short_strategy": {
                    "ma1": ma_result_short['ma1'],
                    "ma2": ma_result_short['ma2'],
                    "trend_params": trend_result_short['trend_params']
                },
                "optimization_info": {
                    "ma_calculation_period": f"{ma_df.index[0].strftime('%Y-%m-%d %H:%M')} ~ {ma_df.index[-1].strftime('%Y-%m-%d %H:%M')}",
                    "lookback_candles": lookback_candles,
                    "ma_calculation_candles": len(ma_df),
                    "optimization_date": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }
            
            existing_params[month_key] = month_data
            
            # 즉시 저장
            save_parameters(json_file, existing_params)
            
            print(f"\n✅ {year}년 {month}월 최적화 완료:")
            print(f"   📊 타임프레임: {selected_config['description']}")
            print(f"   📈 롱 전략:")
            print(f"      MA 파라미터: MA1={ma_result_long['ma1']}, MA2={ma_result_long['ma2']}")
            print(f"      추세 파라미터: {trend_result_long['trend_params']}")
            
            print(f"   📉 숏 전략:")
            print(f"      MA 파라미터: MA1={ma_result_short['ma1']}, MA2={ma_result_short['ma2']}")
            print(f"      추세 파라미터: {trend_result_short['trend_params']}")
            
            print(f"   파라미터가 {json_file}에 저장되었습니다.")
    
    print(f"\n🎉 모든 월 최적화 완료!")
    print(f"📁 결과가 {json_file}에 저장되었습니다.")
    print(f"📊 선택된 타임프레임: {selected_config['description']}")
    print(f"💡 이제 {json_file}의 파라미터를 사용하여 백테스트를 실행할 수 있습니다.")

if __name__ == "__main__":
    main()
