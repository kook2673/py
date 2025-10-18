#-*-coding:utf-8 -*-
'''
바이낸스 선물거래 MA 최적화 백테스트

=== 최적화 범위 ===
1. 빠른 MA: 3MA ~ 20MA
2. 느린 MA: 21MA ~ 200MA  
3. 시간봉: 1시간봉 ~ 10시간봉
4. 전략: 롱/숏 + 골드크로스/데드크로스 진입 + 빠른MA 꺾임 청산

=== 최적화 목표 ===
- 최고 수익률
- 최저 MDD
- 최고 샤프 비율
- 안정적인 거래 빈도
'''

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
import glob
from datetime import datetime, timedelta
from itertools import product
import warnings
warnings.filterwarnings('ignore')

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
    """Hull Moving Average 마지막 값 계산."""
    n = int(period)
    if n <= 0:
        return None
    half = max(1, n // 2)
    sqrt_n = max(1, int(np.sqrt(n)))
    needed = n + (sqrt_n - 1)
    if len(values) < needed:
        return None
    deltas = []
    for k in range(sqrt_n, 0, -1):
        offset = k - 1
        end_idx = len(values) - offset
        wma_half = _wma_last(values[:end_idx], half)
        wma_full = _wma_last(values[:end_idx], n)
        if wma_half is None or wma_full is None:
            return None
        deltas.append(2 * wma_half - wma_full)
    return _wma_last(deltas, sqrt_n)

def calculate_timeframe_ma(df_1m, timeframe_hours, ma1, ma2):
    """1분봉 데이터를 지정된 시간봉으로 변환하여 MA 계산"""
    
    # 시간봉 리샘플링
    df_tf = df_1m.resample(f'{timeframe_hours}H').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    # MA 계산
    df_tf[f'ma_{ma1}'] = df_tf['close'].rolling(ma1).mean()
    df_tf[f'ma_{ma2}'] = df_tf['close'].rolling(ma2).mean()
    
    return df_tf

def backtest_ma_strategy(df_1m, timeframe_hours, ma1, ma2, initial_capital=10000, leverage=10, fee=0.0005):
    """MA 전략 백테스트"""
    
    # 시간봉 MA 계산
    df_tf = calculate_timeframe_ma(df_1m, timeframe_hours, ma1, ma2)
    
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

    # 시간별 종가 덱
    from collections import deque
    tf_closes = deque([], maxlen=max(ma1, ma2) * 8)
    
    # 초기 덱 채우기
    if len(df_tf) > 0:
        first_time = df_1m.index[0]
        prev_tf = first_time.floor(f'{timeframe_hours}H') - pd.Timedelta(hours=timeframe_hours)
        past = df_tf.loc[:prev_tf]['close'] if prev_tf in df_tf.index else df_tf.iloc[:-1]['close']
        for v in past[-(max(ma1, ma2)*2):].values:
            tf_closes.append(float(v))

    prev_ma1 = None
    prev_ma2 = None

    # 백테스트 실행 (1분 단위)
    for i in range(len(df_1m)):
        current_time = df_1m.index[i]
        current_price = float(df_1m['close'].iloc[i])

        # 새로운 시간봉의 첫 분이면, 직전 분의 종가를 확정 종가로 반영
        if i > 0:
            prev_time = df_1m.index[i-1]
            if current_time.floor(f'{timeframe_hours}H') != prev_time.floor(f'{timeframe_hours}H'):
                tf_closes.append(float(df_1m['close'].iloc[i-1]))

        # 현재 분의 진행 중 시간봉 종가로 임시 종가 대체
        temp_series = list(tf_closes)
        temp_series.append(current_price)

        # MA 계산
        if ma1 <= 20:  # 빠른 MA는 HMA 사용
            ma1_current = _hma_last(temp_series, ma1)
        else:  # 느린 MA는 일반 MA 사용
            ma1_current = np.mean(temp_series[-ma1:]) if len(temp_series) >= ma1 else None
            
        ma2_current = np.mean(temp_series[-ma2:]) if len(temp_series) >= ma2 else None
        
        if ma1_current is None or ma2_current is None:
            # 데이터 부족 시 기록만 진행
            equity_curve.append({
                'time': current_time, 
                'equity': long_capital + short_capital, 
                'price': current_price,
                'long_position': long_position, 
                'short_position': short_position,
                'ma1_tf': None, 
                'ma2_tf': None
            })
            prev_ma1, prev_ma2 = ma1_current if 'ma1_current' in locals() else None, ma2_current if 'ma2_current' in locals() else None
            continue

        # 크로스/꺾임 감지
        golden_cross = (prev_ma1 is not None) and (prev_ma2 is not None) and (ma1_current > ma2_current) and (prev_ma1 <= prev_ma2)
        dead_cross = (prev_ma1 is not None) and (prev_ma2 is not None) and (ma1_current < ma2_current) and (prev_ma1 >= prev_ma2)
        slope = None if prev_ma1 is None else (ma1_current - prev_ma1)
        long_turn_down = (slope is not None) and (slope < 0)
        short_turn_up = (slope is not None) and (slope > 0)

        # 롱 진입
        if long_position == 0 and golden_cross:
            long_position = 1
            long_entry_time = current_time
            long_entry_price = current_price

        # 숏 진입
        if short_position == 0 and dead_cross:
            short_position = 1
            short_entry_time = current_time
            short_entry_price = current_price

        # 롱 청산: 빠른MA 꺾임
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
            long_position = 0
            long_entry_time = None
            long_entry_price = None

        # 숏 청산: 빠른MA 반등
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
            'ma1_tf': ma1_current,
            'ma2_tf': ma2_current
        })

        prev_ma1, prev_ma2 = ma1_current, ma2_current
    
    # 마지막 포지션 강제 청산
    if long_position == 1:
        exit_price = float(df_1m['close'].iloc[-1])
        percent = (exit_price - long_entry_price) / long_entry_price
        gross = percent * leverage * long_capital
        pnl = gross - (2 * fee * leverage * long_capital)
        long_capital += pnl
        trades.append({
            'type': 'LONG', 
            'entry_time': long_entry_time, 
            'entry_price': long_entry_price,
            'exit_time': df_1m.index[-1], 
            'exit_price': exit_price, 
            'return_pct': percent * 100,
            'pnl': pnl, 
            'capital_after': long_capital
        })
        
    if short_position == 1:
        exit_price = float(df_1m['close'].iloc[-1])
        percent = (short_entry_price - exit_price) / short_entry_price
        gross = percent * leverage * short_capital
        pnl = gross - (2 * fee * leverage * short_capital)
        short_capital += pnl
        trades.append({
            'type': 'SHORT', 
            'entry_time': short_entry_time, 
            'entry_price': short_entry_price,
            'exit_time': df_1m.index[-1], 
            'exit_price': exit_price, 
            'return_pct': percent * 100,
            'pnl': pnl, 
            'capital_after': short_capital
        })
    
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
    
    # 샤프 비율 계산 (간단한 버전)
    if len(equity_curve) > 1:
        returns = []
        for i in range(1, len(equity_curve)):
            ret = (equity_curve[i]['equity'] - equity_curve[i-1]['equity']) / equity_curve[i-1]['equity']
            returns.append(ret)
        
        if returns:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe_ratio = avg_return / std_return * np.sqrt(252 * 24 * 60) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
    else:
        sharpe_ratio = 0
    
    return {
        'timeframe_hours': timeframe_hours,
        'ma1': ma1,
        'ma2': ma2,
        'total_return': total_return,
        'final_capital': long_capital + short_capital,
        'initial_capital': initial_capital,
        'trades': trades,
        'equity_curve': equity_curve,
        'mdd': mdd,
        'trade_count': len(trades),
        'sharpe_ratio': sharpe_ratio,
        'win_rate': len([t for t in trades if t['pnl'] > 0]) / len(trades) * 100 if trades else 0
    }

def optimize_ma_parameters(df_1m, initial_capital=10000, leverage=10, fee=0.0005):
    """MA 파라미터 최적화"""
    
    print("🔍 MA 파라미터 최적화 시작...")
    print("=" * 80)
    
    # 최적화 범위 설정
    fast_mas = list(range(13, 21))  # 3MA ~ 20MA
    slow_mas = list(range(41, 101))  # 21MA ~ 200MA
    timeframes = list(range(4, 5))  # 1시간봉 ~ 10시간봉
    
    print(f"📊 최적화 범위:")
    print(f"  빠른 MA: {fast_mas[0]} ~ {fast_mas[-1]} ({len(fast_mas)}개)")
    print(f"  느린 MA: {slow_mas[0]} ~ {slow_mas[-1]} ({len(slow_mas)}개)")
    print(f"  시간봉: {timeframes[0]}시간 ~ {timeframes[-1]}시간 ({len(timeframes)}개)")
    print(f"  총 조합 수: {len(fast_mas) * len(slow_mas) * len(timeframes):,}개")
    
    # 결과 저장용 리스트
    all_results = []
    total_combinations = len(fast_mas) * len(slow_mas) * len(timeframes)
    current_combination = 0
    
    # 모든 조합 테스트
    for ma1, ma2, tf in product(fast_mas, slow_mas, timeframes):
        current_combination += 1
        
        if current_combination % 100 == 0:
            progress = (current_combination / total_combinations) * 100
            print(f"🔄 진행률: {progress:.1f}% ({current_combination:,}/{total_combinations:,})")
        
        try:
            result = backtest_ma_strategy(df_1m, tf, ma1, ma2, initial_capital, leverage, fee)
            if result:
                all_results.append(result)
                
                # 각 전략 완료 시 수익률 표시
                return_color = "🟢" if result['total_return'] > 0 else "🔴"
                print(f"{return_color} {tf}시간봉 {ma1}MA + {ma2}MA: {result['total_return']:+.2f}% | MDD: {result['mdd']:.2f}% | 거래: {result['trade_count']}회")
                
        except Exception as e:
            print(f"❌ 오류 발생: MA1={ma1}, MA2={ma2}, TF={tf}시간 - {e}")
            continue
    
    print(f"\n✅ 최적화 완료! 총 {len(all_results)}개 조합 테스트 완료")
    
    return all_results

def analyze_optimization_results(all_results):
    """최적화 결과 분석"""
    
    if not all_results:
        print("❌ 분석할 결과가 없습니다.")
        return
    
    print(f"\n📊 최적화 결과 분석")
    print("=" * 80)
    
    # 데이터프레임으로 변환
    df_results = pd.DataFrame(all_results)
    
    # 1. 수익률 기준 상위 10개
    print(f"\n🏆 수익률 기준 상위 10개:")
    top_return = df_results.nlargest(10, 'total_return')[['timeframe_hours', 'ma1', 'ma2', 'total_return', 'mdd', 'sharpe_ratio', 'trade_count', 'win_rate']]
    print(top_return.to_string(index=False))
    
    # 2. 샤프 비율 기준 상위 10개
    print(f"\n📈 샤프 비율 기준 상위 10개:")
    top_sharpe = df_results.nlargest(10, 'sharpe_ratio')[['timeframe_hours', 'ma1', 'ma2', 'total_return', 'mdd', 'sharpe_ratio', 'trade_count', 'win_rate']]
    print(top_sharpe.to_string(index=False))
    
    # 3. MDD 기준 상위 10개 (낮은 순)
    print(f"\n🛡️ MDD 기준 상위 10개 (낮은 순):")
    top_mdd = df_results.nsmallest(10, 'mdd')[['timeframe_hours', 'ma1', 'ma2', 'total_return', 'mdd', 'sharpe_ratio', 'trade_count', 'win_rate']]
    print(top_mdd.to_string(index=False))
    
    # 4. 통계 요약
    print(f"\n📋 전체 결과 통계:")
    print(f"  평균 수익률: {df_results['total_return'].mean():.2f}%")
    print(f"  중앙값 수익률: {df_results['total_return'].median():.2f}%")
    print(f"  최고 수익률: {df_results['total_return'].max():.2f}%")
    print(f"  최저 수익률: {df_results['total_return'].min():.2f}%")
    print(f"  평균 MDD: {df_results['mdd'].mean():.2f}%")
    print(f"  평균 샤프 비율: {df_results['sharpe_ratio'].mean():.2f}")
    print(f"  평균 거래 수: {df_results['trade_count'].mean():.1f}회")
    print(f"  평균 승률: {df_results['win_rate'].mean():.1f}%")
    
    # 5. 수익률이 양수인 전략 수
    profitable_strategies = df_results[df_results['total_return'] > 0]
    print(f"\n💰 수익률이 양수인 전략: {len(profitable_strategies)}개 ({len(profitable_strategies)/len(df_results)*100:.1f}%)")
    
    return df_results

def create_optimization_heatmap(df_results, save_path):
    """최적화 결과 히트맵 생성"""
    
    print(f"\n📊 히트맵 생성 중...")
    
    # 시간봉별로 그룹화하여 히트맵 생성
    timeframes = sorted(df_results['timeframe_hours'].unique())
    
    fig, axes = plt.subplots(2, 2, figsize=(24, 20))
    fig.suptitle('MA 최적화 결과 히트맵', fontsize=20, fontweight='bold')
    
    # 1. 수익률 히트맵 (가장 중요한 지표)
    ax1 = axes[0, 0]
    pivot_return = df_results.pivot_table(values='total_return', index='ma1', columns='ma2', aggfunc='mean')
    im1 = ax1.imshow(pivot_return.values, cmap='RdYlGn', aspect='auto', vmin=-20, vmax=20)
    ax1.set_title('평균 수익률 (%)', fontsize=16, fontweight='bold')
    ax1.set_xlabel('느린 MA', fontsize=14)
    ax1.set_ylabel('빠른 MA', fontsize=14)
    ax1.set_xticks(range(len(pivot_return.columns)))
    ax1.set_xticklabels(pivot_return.columns[::10], rotation=45)
    ax1.set_yticks(range(len(pivot_return.index)))
    ax1.set_yticklabels(pivot_return.index)
    plt.colorbar(im1, ax=ax1, label='수익률 (%)')
    
    # 2. 샤프 비율 히트맵
    ax2 = axes[0, 1]
    pivot_sharpe = df_results.pivot_table(values='sharpe_ratio', index='ma1', columns='ma2', aggfunc='mean')
    im2 = ax2.imshow(pivot_sharpe.values, cmap='viridis', aspect='auto')
    ax2.set_title('평균 샤프 비율', fontsize=16, fontweight='bold')
    ax2.set_xlabel('느린 MA', fontsize=14)
    ax2.set_ylabel('빠른 MA', fontsize=14)
    ax2.set_xticks(range(len(pivot_sharpe.columns)))
    ax2.set_xticklabels(pivot_sharpe.columns[::10], rotation=45)
    ax2.set_yticks(range(len(pivot_sharpe.index)))
    ax2.set_yticklabels(pivot_sharpe.index)
    plt.colorbar(im2, ax=ax2, label='샤프 비율')
    
    # 3. MDD 히트맵
    ax3 = axes[1, 0]
    pivot_mdd = df_results.pivot_table(values='mdd', index='ma1', columns='ma2', aggfunc='mean')
    im3 = ax3.imshow(pivot_mdd.values, cmap='Reds', aspect='auto')
    ax3.set_title('평균 MDD (%)', fontsize=16, fontweight='bold')
    ax3.set_xlabel('느린 MA', fontsize=14)
    ax3.set_ylabel('빠른 MA', fontsize=14)
    ax3.set_xticks(range(len(pivot_mdd.columns)))
    ax3.set_xticklabels(pivot_mdd.columns[::10], rotation=45)
    ax3.set_yticks(range(len(pivot_mdd.index)))
    ax3.set_yticklabels(pivot_mdd.index)
    plt.colorbar(im3, ax=ax3, label='MDD (%)')
    
    # 4. 거래 수 히트맵
    ax4 = axes[1, 1]
    pivot_trades = df_results.pivot_table(values='trade_count', index='ma1', columns='ma2', aggfunc='mean')
    im4 = ax4.imshow(pivot_trades.values, cmap='Blues', aspect='auto')
    ax4.set_title('평균 거래 수', fontsize=16, fontweight='bold')
    ax4.set_xlabel('느린 MA', fontsize=14)
    ax4.set_ylabel('빠른 MA', fontsize=14)
    ax4.set_xticks(range(len(pivot_trades.columns)))
    ax4.set_xticklabels(pivot_trades.columns[::10], rotation=45)
    ax4.set_yticks(range(len(pivot_trades.index)))
    ax4.set_yticklabels(pivot_trades.index)
    plt.colorbar(im4, ax=ax4, label='거래 수')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ 히트맵이 {save_path}에 저장되었습니다.")

def main():
    """메인 함수"""
    
    print("🚀 MA 최적화 백테스트 시작!")
    print("=" * 80)
    
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
    
    print(f"\n📊 백테스트 설정:")
    print(f"초기 자본: {initial_capital:,} USDT")
    print(f"레버리지: {leverage}배")
    print(f"수수료: {fee*100:.1f}%")
    
    # MA 최적화 실행
    print(f"\n🔄 MA 최적화 실행 중...")
    all_results = optimize_ma_parameters(df_1m, initial_capital, leverage, fee)
    
    if all_results:
        # 결과 분석
        df_results = analyze_optimization_results(all_results)
        
        # 결과 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_filename = f"MA_Optimization_Results_{timestamp}.csv"
        result_path = os.path.join(script_dir, 'logs', result_filename)
        
        # 로그 디렉토리 생성
        os.makedirs(os.path.dirname(result_path), exist_ok=True)
        
        # CSV 파일로 저장
        df_results.to_csv(result_path, index=False, encoding='utf-8-sig')
        print(f"\n💾 최적화 결과가 {result_path}에 저장되었습니다.")
        
        # 히트맵 생성
        heatmap_path = result_path.replace('.csv', '_heatmap.png')
        create_optimization_heatmap(df_results, heatmap_path)
        
        # 최고 전략 상세 분석
        best_strategy = df_results.loc[df_results['total_return'].idxmax()]
        print(f"\n🏆 최고 성과 전략 상세:")
        print(f"  시간봉: {best_strategy['timeframe_hours']}시간")
        print(f"  빠른 MA: {best_strategy['ma1']}")
        print(f"  느린 MA: {best_strategy['ma2']}")
        print(f"  수익률: {best_strategy['total_return']:.2f}%")
        print(f"  MDD: {best_strategy['mdd']:.2f}%")
        print(f"  샤프 비율: {best_strategy['sharpe_ratio']:.2f}")
        print(f"  거래 수: {best_strategy['trade_count']}회")
        print(f"  승률: {best_strategy['win_rate']:.1f}%")
        
    else:
        print("❌ 최적화 실패")

if __name__ == "__main__":
    main()
