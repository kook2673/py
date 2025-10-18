#-*-coding:utf-8 -*-
'''
바이낸스 선물거래 1시간 MA + 1분 체크 + 롱 전용 전략 백테스트

=== 전략 구성 ===
1. 기본 MA: 1시간봉 기준 5MA와 20MA 크로스오버
2. 진입: 골드크로스 (5MA > 20MA) 시점에 롱 진입
3. 청산: 5MA가 꺾이는 순간 (기울기 변화) 즉시 청산
4. 1분 단위로 체크하여 MA 교차 지점 감지

=== 진입 조건 ===
롱 진입: 1시간봉 기준 5MA > 20MA (골드크로스)

=== 청산 조건 ===
1. 5MA 꺾임: 5MA 기울기가 음수로 변하는 순간
2. 백테스트 종료: 마지막 데이터에서 보유 포지션 강제 청산

=== 전략 특징 ===
- 1시간봉 기준으로 MA 계산하여 빠른 반응
- 1분 단위로 체크하여 정확한 진입/청산 타이밍 포착
- 롱 전용으로 단순화된 전략
- 5MA 기울기 변화로 추세 전환 감지
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

# HMA 계산 유틸리티
def _wma_last(values, period):
    if period <= 0 or values is None or len(values) < period:
        return None
    weights = np.arange(1, period + 1, dtype=float)
    window = np.array(values[-period:], dtype=float)
    return np.dot(window, weights) / weights.sum()

def _hma_last(values, period):
    """Hull Moving Average 마지막 값 계산.
    HMA(n) = WMA( 2*WMA(price, n/2) - WMA(price, n), sqrt(n) )
    """
    n = int(period)
    if n <= 0:
        return None
    half = max(1, n // 2)
    sqrt_n = max(1, int(np.sqrt(n)))
    # delta 시계열의 마지막 sqrt_n개를 만들어 WMA 수행
    needed = n + (sqrt_n - 1)
    if len(values) < needed:
        return None
    deltas = []
    for k in range(sqrt_n, 0, -1):
        # k: sqrt_n..1 (과거→현재 순서를 만들기 위함)
        offset = k - 1
        end_idx = len(values) - offset
        wma_half = _wma_last(values[:end_idx], half)
        wma_full = _wma_last(values[:end_idx], n)
        if wma_half is None or wma_full is None:
            return None
        deltas.append(2 * wma_half - wma_full)
    # deltas는 과거→현재 순서, 마지막 sqrt_n개로 WMA
    return _wma_last(deltas, sqrt_n)

def calculate_4h_ma(df_1m, ma1=5, ma2=20):
    """1분봉 데이터를 4시간봉으로 변환하여 MA 계산"""
    
    # 1분봉을 4시간봉으로 리샘플링
    df_4h = df_1m.resample('4H').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    # 4시간봉 기준 MA 계산
    df_4h[f'ma_{ma1}'] = df_4h['close'].rolling(ma1).mean()
    df_4h[f'ma_{ma2}'] = df_4h['close'].rolling(ma2).mean()
    
    # 5MA 기울기 계산 (4시간봉 기준)
    df_4h[f'ma_{ma1}_slope'] = df_4h[f'ma_{ma1}'].diff()
    
    return df_4h

def check_ma_crossover(df_4h, i, ma1=5, ma2=20):
    """MA 크로스오버 확인 (골드크로스/데드크로스)"""
    if i < 1:
        return None
    
    ma1_current = df_1h[f'ma_{ma1}'].iloc[i]
    ma2_current = df_1h[f'ma_{ma2}'].iloc[i]
    ma1_prev = df_1h[f'ma_{ma1}'].iloc[i-1]
    ma2_prev = df_1h[f'ma_{ma2}'].iloc[i-1]
    
    # 골드크로스: 5MA가 20MA를 위로 교차
    if ma1_current > ma2_current and ma1_prev <= ma2_prev:
        return 'GOLDEN_CROSS'
    
    # 데드크로스: 5MA가 20MA를 아래로 교차
    elif ma1_current < ma2_current and ma1_prev >= ma2_prev:
        return 'DEAD_CROSS'
    
    return None

def check_ma5_slope_change(df_4h, i, ma1=5):
    """5MA 기울기 변화 확인 (꺾임 감지)"""
    if i < 2:
        return False
    
    slope_current = df_1h[f'ma_{ma1}_slope'].iloc[i]
    slope_prev = df_1h[f'ma_{ma1}_slope'].iloc[i-1]
    
    # 기울기가 양수에서 음수로 변하는 순간 (꺾임)
    if slope_prev > 0 and slope_current < 0:
        return True
    
    return False

def backtest_4h_ma_strategy(df_1m, ma1=5, ma2=20, initial_capital=10000, leverage=10, fee=0.0005):
    """4시간 5HMA/20MA + 분단위 즉시 평가 + 롱/숏 동시 운용 백테스트
    - 자본을 2등분하여 롱/숏 각각 독립 운용
    - 매 분 현재가를 포함한 '진행 중인 4시간봉' 의사 종가로 4시간 MA를 재계산
    - 진입: 골든/데드 크로스가 분 단위로 발생하면 즉시
    - 청산: 5MA 기울기 반전(꺾임)이 분 단위로 발생하면 즉시
    - 룩어헤드 없음: 해당 분까지의 정보만 사용
    """
    
    # 4시간봉 MA 계산 (초기 참조용, 진행 중에는 HMA로 대체 계산)
    df_4h = calculate_4h_ma(df_1m, ma1, ma2)
    # 룩어헤드 방지: 신호는 전시간(마감 완료된 바) 기준으로만 사용
    df_4h['ma1_prev'] = df_4h[f'ma_{ma1}'].shift(1)
    df_4h['ma2_prev'] = df_4h[f'ma_{ma2}'].shift(1)
    df_4h['golden_cross'] = (df_4h[f'ma_{ma1}'] > df_4h[f'ma_{ma2}']) & (df_4h['ma1_prev'] <= df_4h['ma2_prev'])
    # 5MA 꺾임(기울기 양->음) 감지: 전시간 마감 기준
    df_4h['slope'] = df_4h[f'ma_{ma1}'].diff()
    df_4h['slope_prev'] = df_4h['slope'].shift(1)
    df_4h['ma5_turn_down'] = (df_4h['slope_prev'] > 0) & (df_4h['slope'] <= 0)
    
    # 롱/숏 독립 자본
    long_capital = initial_capital * 0.5
    short_capital = initial_capital * 0.5

    # 포지션 상태
    long_position = 0
    short_position = 0
    long_entry_time = None
    long_entry_price = None
    short_entry_time = None
    short_entry_price = None

    trades = []
    equity_curve = []

    # 시간 경계 추적 및 시간별 종가 덱(마지막 40개 버퍼)
    from collections import deque
    hourly_closes = deque([], maxlen=max(ma1, ma2) * 8)
    
    # 초기 덱: 첫 분의 전시간까지의 확정된 4시간 종가 채우기
    if len(df_4h) > 0:
        first_time = df_1m.index[0]
        prev_4h = first_time.floor('4H') - pd.Timedelta(hours=4)
        past = df_4h.loc[:prev_4h]['close'] if prev_4h in df_4h.index else df_4h.iloc[:-1]['close']
        for v in past[-(max(ma1, ma2)*2):].values:
            hourly_closes.append(float(v))

    prev_ma1 = None
    prev_ma2 = None

    # 백테스트 실행 (1분 단위)
    for i in range(len(df_1m)):
        current_time = df_1m.index[i]
        current_price = float(df_1m['close'].iloc[i])

        # 새로운 4시간의 첫 분이면, 직전 분(이전 4시간)의 종가를 확정 4시간 종가로 반영
        if i > 0:
            prev_time = df_1m.index[i-1]
            if current_time.floor('4H') != prev_time.floor('4H'):
                hourly_closes.append(float(df_1m['close'].iloc[i-1]))

        # 현재 분의 진행 중 4시간봉 종가로 임시 4시간 닫기값 대체
        temp_series = list(hourly_closes)
        temp_series.append(current_price)

        # HMA 계산 가능할 때만 진행 (5HMA, 20MA)
        hma1 = _hma_last(temp_series, ma1)
        ma2_current = np.mean(temp_series[-ma2:]) if len(temp_series) >= ma2 else None
        if hma1 is not None and ma2_current is not None:
            ma1_current = hma1
        else:
            # 데이터 부족 시 기록만 진행
            equity_curve.append({'time': current_time, 'equity': long_capital + short_capital, 'price': current_price,
                                 'long_position': long_position, 'short_position': short_position,
                                 'ma1_4h': None, 'ma2_4h': None})
            prev_ma1, prev_ma2 = ma1_current if 'ma1_current' in locals() else None, ma2_current if 'ma2_current' in locals() else None
            continue

        # 크로스/꺾임 감지 (분 단위, 진행봉 포함)
        golden_cross = (prev_ma1 is not None) and (prev_ma2 is not None) and (ma1_current > ma2_current) and (prev_ma1 <= prev_ma2)
        dead_cross = (prev_ma1 is not None) and (prev_ma2 is not None) and (ma1_current < ma2_current) and (prev_ma1 >= prev_ma2)
        slope = None if prev_ma1 is None else (ma1_current - prev_ma1)
        slope_prev = None  # 한 분 전 기울기는 필요 시 prev-previous로 확장 가능
        long_turn_down = (slope is not None) and (slope < 0)
        short_turn_up = (slope is not None) and (slope > 0)

        # 롱 진입
        if long_position == 0 and golden_cross:
            long_position = 1
            long_entry_time = current_time
            long_entry_price = current_price
            print(f"🟢 롱 진입: {current_time} | 가격: {current_price:.0f} | MA5:{ma1_current:.2f} > MA20:{ma2_current:.2f}")

        # 숏 진입
        if short_position == 0 and dead_cross:
            short_position = 1
            short_entry_time = current_time
            short_entry_price = current_price
            print(f"🔴 숏 진입: {current_time} | 가격: {current_price:.0f} | MA5:{ma1_current:.2f} < MA20:{ma2_current:.2f}")

        # 롱 청산: 5HMA 꺾임(기울기<0)
        if long_position == 1 and long_turn_down:
            exit_price = current_price
            percent = (exit_price - long_entry_price) / long_entry_price
            gross = percent * leverage * long_capital
            pnl = gross - (2 * fee * leverage * long_capital)
            long_capital += pnl
            trades.append({
                'type': 'LONG',
                'entry_time': long_entry_time,
                'entry_price': long_entry_price,
                'exit_time': current_time,
                'exit_price': exit_price,
                'return_pct': percent * 100,
                'pnl': pnl,
                'capital_after': long_capital,
            })
            print(f"🟡 롱 청산(5MA 꺾임): {current_time} | 손익: {pnl:.2f} USDT | 자본L: {long_capital:,.2f}")
            long_position = 0
            long_entry_time = None
            long_entry_price = None

        # 숏 청산: 5HMA 반등(기울기>0)
        if short_position == 1 and short_turn_up:
            exit_price = current_price
            percent = (short_entry_price - exit_price) / short_entry_price
            gross = percent * leverage * short_capital
            pnl = gross - (2 * fee * leverage * short_capital)
            short_capital += pnl
            trades.append({
                'type': 'SHORT',
                'entry_time': short_entry_time,
                'entry_price': short_entry_price,
                'exit_time': current_time,
                'exit_price': exit_price,
                'return_pct': percent * 100,
                'pnl': pnl,
                'capital_after': short_capital,
            })
            print(f"🟣 숏 청산(5MA 반등): {current_time} | 손익: {pnl:.2f} USDT | 자본S: {short_capital:,.2f}")
            short_position = 0
            short_entry_time = None
            short_entry_price = None

        # 자산 곡선 기록
        equity_curve.append({
            'time': current_time,
            'equity': long_capital + short_capital,
            'price': current_price,
            'long_position': long_position,
            'short_position': short_position,
            'ma1_4h': ma1_current,
            'ma2_4h': ma2_current
        })

        prev_ma1, prev_ma2 = ma1_current, ma2_current
    
    # 마지막 포지션 청산
    # 마지막 포지션 강제 청산
    if long_position == 1:
        exit_price = float(df_1m['close'].iloc[-1])
        percent = (exit_price - long_entry_price) / long_entry_price
        gross = percent * leverage * long_capital
        pnl = gross - (2 * fee * leverage * long_capital)
        long_capital += pnl
        trades.append({'type': 'LONG', 'entry_time': long_entry_time, 'entry_price': long_entry_price,
                       'exit_time': df_1m.index[-1], 'exit_price': exit_price, 'return_pct': percent * 100,
                       'pnl': pnl, 'capital_after': long_capital})
    if short_position == 1:
        exit_price = float(df_1m['close'].iloc[-1])
        percent = (short_entry_price - exit_price) / short_entry_price
        gross = percent * leverage * short_capital
        pnl = gross - (2 * fee * leverage * short_capital)
        short_capital += pnl
        trades.append({'type': 'SHORT', 'entry_time': short_entry_time, 'entry_price': short_entry_price,
                       'exit_time': df_1m.index[-1], 'exit_price': exit_price, 'return_pct': percent * 100,
                       'pnl': pnl, 'capital_after': short_capital})
    
    # 결과 계산
    total_return = ((long_capital + short_capital) - initial_capital) / initial_capital * 100
    
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
        'final_capital': long_capital + short_capital,
        'initial_capital': initial_capital,
        'trades': trades,
        'equity_curve': equity_curve,
        'mdd': mdd,
        'trade_count': len(trades),
        'df_4h': df_4h
    }

def main():
    """메인 함수"""
    
    print("🚀 4시간 MA + 1분 체크 + 롱 전용 전략 백테스트 시작! (2025년 3월)")
    print("=" * 60)
    
    # 스크립트 디렉토리
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1분봉 데이터 로드
    data_dir = os.path.join(script_dir, 'data', 'BTC_USDT', '1m')
    
    # 2025년 3월 1분봉 파일 찾기
    csv_pattern = '2025-03.csv'
    csv_files = glob.glob(os.path.join(data_dir, csv_pattern))
    
    if not csv_files:
        print(f"❌ {csv_pattern} 패턴의 파일을 찾을 수 없습니다.")
        print(f"📁 데이터 디렉토리: {data_dir}")
        return
    
    print(f"📊 발견된 1분봉 파일 수: {len(csv_files)}개")
    print(f"📅 기간: 2025년 3월")
    
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
    initial_capital = 10000  # 초기 자본
    leverage = 10  # 레버리지
    fee = 0.0005  # 수수료 0.05%
    
    # 두 가지 MA 조합 테스트
    ma_combinations = [
        (8, 21, "8HMA + 21MA"),
        (13, 34, "13HMA + 34MA")
    ]
    
    all_results = []
    
    for ma1, ma2, strategy_name in ma_combinations:
        print(f"\n{'='*60}")
        print(f"🔄 {strategy_name} 전략 백테스트 시작!")
        print(f"{'='*60}")
        
        print(f"\n📊 백테스트 설정:")
        print(f"MA 설정: 4시간봉 기준 {ma1}HMA + {ma2}MA")
        print(f"체크 주기: 1분 단위")
        print(f"초기 자본: {initial_capital:,} USDT")
        print(f"레버리지: {leverage}배")
        print(f"수수료: {fee*100:.1f}%")
        print(f"전략: 롱/숏 + 골드크로스/데드크로스 진입 + 5HMA 꺾임 청산")
        
        # 백테스트 실행
        print(f"\n🔄 백테스트 실행 중...")
        result = backtest_4h_ma_strategy(df_1m, ma1, ma2, initial_capital, leverage, fee)
        
        if result:
            result['strategy_name'] = strategy_name
            result['ma1'] = ma1
            result['ma2'] = ma2
            all_results.append(result)
            
            print(f"\n✅ {strategy_name} 백테스트 완료!")
            print(f"📈 전체 수익률: {result['total_return']:.2f}%")
            print(f"💰 최종 자본: {result['final_capital']:,.2f} USDT")
            print(f"🔄 총 거래 수: {result['trade_count']}회")
            print(f"📉 최대 MDD: {result['mdd']:.2f}%")
            
            # 거래 내역 요약
            if result['trades']:
                print(f"\n📋 거래 내역 요약:")
                
                # 수익 거래 분석
                profitable_trades = [t for t in result['trades'] if t.get('pnl', 0) > 0]
                if profitable_trades:
                    avg_profit = sum(t['pnl'] for t in profitable_trades) / len(profitable_trades)
                    print(f"수익 거래 평균: {avg_profit:.2f} USDT")
                
                # 손실 거래 분석
                loss_trades = [t for t in result['trades'] if t.get('pnl', 0) < 0]
                if loss_trades:
                    avg_loss = sum(t['pnl'] for t in loss_trades) / len(loss_trades)
                    print(f"손실 거래 평균: {avg_loss:.2f} USDT")
                
                # 승률 계산
                win_rate = len(profitable_trades) / len(result['trades']) * 100
                print(f"승률: {win_rate:.1f}%")
        else:
            print(f"❌ {strategy_name} 백테스트 실패")
    
    # 결과 비교 및 저장
    if all_results:
        print(f"\n{'='*60}")
        print(f"📊 전략 비교 결과")
        print(f"{'='*60}")
        
        for result in all_results:
            print(f"\n{result['strategy_name']}:")
            print(f"  📈 수익률: {result['total_return']:.2f}%")
            print(f"  💰 최종자본: {result['final_capital']:,.2f} USDT")
            print(f"  🔄 거래수: {result['trade_count']}회")
            print(f"  📉 MDD: {result['mdd']:.2f}%")
        
        # 최고 성과 전략 찾기
        best_strategy = max(all_results, key=lambda x: x['total_return'])
        print(f"\n🏆 최고 성과 전략: {best_strategy['strategy_name']}")
        print(f"   수익률: {best_strategy['total_return']:.2f}%")
        
        # 결과 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_filename = f"MA_4h_1m_Comparison_{timestamp}.json"
        result_path = os.path.join(script_dir, 'logs', result_filename)
        
        # 로그 디렉토리 생성
        os.makedirs(os.path.dirname(result_path), exist_ok=True)
        
        # 결과 데이터 구성
        result_data = {
            'comparison_date': timestamp,
            'strategies': []
        }
        
        for result in all_results:
            strategy_data = {
                'strategy_name': result['strategy_name'],
                'parameters': {
                    'ma1': result['ma1'],
                    'ma2': result['ma2'],
                    'initial_capital': initial_capital,
                    'leverage': leverage,
                    'fee': fee
                },
                'performance': {
                    'total_return': result['total_return'],
                    'final_capital': result['final_capital'],
                    'initial_capital': result['initial_capital'],
                    'trade_count': result['trade_count'],
                    'mdd': result['mdd']
                },
                'trades': result['trades'],
                'equity_curve': result['equity_curve']
            }
            result_data['strategies'].append(strategy_data)
        
        # JSON 파일로 저장
        import json
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 비교 결과가 {result_path}에 저장되었습니다.")
        
        # 그래프 생성
        print(f"\n📊 그래프 생성 중...")
        try:
            create_comparison_graph(all_results, df_1m, result_path.replace('.json', '.png'))
            print(f"✅ 비교 그래프가 {result_path.replace('.json', '.png')}에 저장되었습니다.")
        except Exception as e:
            print(f"❌ 그래프 생성 실패: {e}")
    
    else:
        print("❌ 모든 백테스트 실패")

def create_comparison_graph(all_results, df_1m, graph_path):
    """전략 비교 그래프 생성"""
    
    # 3개 서브플롯 생성
    fig, axes = plt.subplots(3, 1, figsize=(20, 15))
    
    # 1. 가격 차트 + 거래 내역
    ax1 = axes[0]
    ax1.plot(df_1m.index, df_1m['close'], 'k-', linewidth=0.5, alpha=0.8, label='BTC 1M')
    
    # 각 전략별 거래 내역 표시
    colors = ['red', 'blue']
    markers = ['^', 's']
    
    for i, result in enumerate(all_results):
        color = colors[i % len(colors)]
        marker = markers[i % len(markers)]
        
        for trade in result['trades']:
            if trade['type'] == 'LONG':
                ax1.scatter(trade['entry_time'], trade['entry_price'], 
                           color=color, marker=marker, s=80, alpha=0.8, zorder=5,
                           label=f"{result['strategy_name']} 진입" if trade == result['trades'][0] else "")
                ax1.scatter(trade['exit_time'], trade['exit_price'], 
                           color=color, marker='v', s=80, alpha=0.8, zorder=5)
            elif trade['type'] == 'SHORT':
                ax1.scatter(trade['entry_time'], trade['entry_price'], 
                           color=color, marker=marker, s=80, alpha=0.8, zorder=5,
                           label=f"{result['strategy_name']} 진입" if trade == result['trades'][0] else "")
                ax1.scatter(trade['exit_time'], trade['exit_price'], 
                           color=color, marker='v', s=80, alpha=0.8, zorder=5)
    
    ax1.set_title('BTC 1분봉 + 전략별 거래내역 비교', fontsize=14, fontweight='bold')
    ax1.set_ylabel('가격 (USDT)', fontsize=12)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. 자산 곡선 비교
    ax2 = axes[1]
    
    for i, result in enumerate(all_results):
        color = colors[i % len(colors)]
        times = [point['time'] for point in result['equity_curve']]
        equities = [point['equity'] for point in result['equity_curve']]
        
        ax2.plot(times, equities, color=color, linewidth=2, 
                label=f"{result['strategy_name']} (수익률: {result['total_return']:.2f}%)", alpha=0.9)
    
    ax2.axhline(y=10000, color='black', linestyle='--', alpha=0.7, label='초기 자본')
    ax2.set_title('전략별 자산 곡선 비교', fontsize=14, fontweight='bold')
    ax2.set_ylabel('자산 (USDT)', fontsize=12)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. 성과 지표 비교
    ax3 = axes[2]
    
    strategy_names = [result['strategy_name'] for result in all_results]
    returns = [result['total_return'] for result in all_results]
    mdd_values = [result['mdd'] for result in all_results]
    trade_counts = [result['trade_count'] for result in all_results]
    
    x = np.arange(len(strategy_names))
    width = 0.25
    
    # 수익률 바
    bars1 = ax3.bar(x - width, returns, width, label='수익률 (%)', color='green', alpha=0.7)
    # MDD 바
    bars2 = ax3.bar(x, mdd_values, width, label='MDD (%)', color='red', alpha=0.7)
    # 거래수 바
    bars3 = ax3.bar(x + width, trade_counts, width, label='거래수', color='blue', alpha=0.7)
    
    # 값 표시
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height + (0.1 if height > 0 else -0.1),
                    f'{height:.1f}', ha='center', va='bottom' if height > 0 else 'top')
    
    ax3.set_title('전략별 성과 지표 비교', fontsize=14, fontweight='bold')
    ax3.set_ylabel('수치', fontsize=12)
    ax3.set_xlabel('전략', fontsize=12)
    ax3.set_xticks(x)
    ax3.set_xticklabels(strategy_names)
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.axhline(y=0, color='black', linestyle='-', alpha=0.5)
    
    # x축 날짜 포맷 (첫 번째 차트만)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=7))
    ax1.tick_params(axis='x', rotation=45)
    
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=7))
    ax2.tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.savefig(graph_path, dpi=300, bbox_inches='tight')
    plt.close()

def create_performance_graph(result, df_1m, ma1, ma2, graph_path):
    """개별 전략 성과 그래프 생성"""
    
    # 4개 서브플롯 생성
    fig, axes = plt.subplots(4, 1, figsize=(20, 16))
    
    # 1. 비트코인 1분봉 + 4시간 MA
    ax1 = axes[0]
    
    # 가격 데이터
    ax1.plot(df_1m.index, df_1m['close'], 'k-', linewidth=0.5, alpha=0.8, label='BTC 1M')
    
    # 4시간봉 MA 선들 (1분봉 시간축에 맞춰 플롯)
    if 'df_4h' in result:
        df_4h = result['df_4h']
        # 4시간봉 시간을 1분봉 시간축에 맞춰 플롯
        for i, timestamp in enumerate(df_4h.index):
            if i < len(df_4h):
                ma1_val = df_4h[f'ma_{ma1}'].iloc[i]
                ma2_val = df_4h[f'ma_{ma2}'].iloc[i]
                # 4시간봉 시작부터 다음 4시간봉 시작까지 같은 값으로 플롯
                if i + 1 < len(df_4h):
                    next_timestamp = df_4h.index[i + 1]
                else:
                    next_timestamp = df_1m.index[-1]
                
                # 해당 구간에 MA 값 플롯
                mask = (df_1m.index >= timestamp) & (df_1m.index < next_timestamp)
                if mask.any():
                    ax1.plot(df_1m.index[mask], [ma1_val] * mask.sum(), 'r-', linewidth=1, alpha=0.7)
                    ax1.plot(df_1m.index[mask], [ma2_val] * mask.sum(), 'b-', linewidth=1, alpha=0.7)
    
    # 거래 내역 화살표 표시
    for trade in result['trades']:
        if trade['type'] in ('LONG', 'LONG_FINAL'):
            # 진입 지점 (녹색 화살표 위)
            ax1.scatter(trade['entry_time'], trade['entry_price'], color='green', marker='^', s=100, alpha=0.8, zorder=5)
            # 청산 지점 (빨간색 화살표 아래)
            ax1.scatter(trade['exit_time'], trade['exit_price'], color='red', marker='v', s=100, alpha=0.8, zorder=5)
    
    ax1.set_title('BTC 1분봉 + 4시간 MA 이동평균선 + 거래내역', fontsize=14, fontweight='bold')
    ax1.set_ylabel('가격 (USDT)', fontsize=12)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. 거래별 수익률
    ax2 = axes[1]
    
    if result['trades']:
        trade_times = [trade['exit_time'] for trade in result['trades']]
        trade_returns = [trade['return_pct'] for trade in result['trades']]
        
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
        
        ax3.plot(times, equities, 'b-', linewidth=1.5, label='자산', alpha=0.9)
        ax3.axhline(y=10000, color='black', linestyle='--', alpha=0.7, label='초기 자본')
        
        ax3.set_title('자산 곡선', fontsize=14, fontweight='bold')
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
