# -*- coding: utf-8 -*-
"""
Walk-Forward 최적화(WFO) 스크립트

이 스크립트는 백테스팅의 과적합을 방지하고 전략의 실전 성능을 보다 현실적으로
검증하기 위해 Walk-Forward 최적화 기법을 구현합니다.

과정:
1. 전체 데이터를 여러 개의 Window로 분할합니다.
2. 각 Window는 훈련(In-Sample) 기간과 검증(Out-of-Sample) 기간으로 나뉩니다.
3. 훈련 기간 데이터로 파라미터를 최적화하여 '최적의 파라미터'를 찾습니다.
4. 이 '최적의 파라미터'를 바로 다음의 검증 기간(미래 데이터로 가정)에 적용하여
   단일 백테스트를 실행하고, 그 성과(Out-of-Sample Performance)를 기록합니다.
5. Window를 한 칸씩 이동하며 위 과정을 전체 데이터 기간에 대해 반복합니다.
6. 최종적으로 모든 검증 기간의 성과를 하나로 합쳐, 전략의 장기적인 안정성과
   현실적인 기대 수익률을 평가합니다.
"""

import os
import json
import itertools
from datetime import datetime
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import mplfinance as mpf

from strategy_platform import run_backtest, RsiMeanReversion, BollingerBandStrategy, MacdStrategy, StochasticStrategy, BollingerBandADXStrategy, MacdADXStrategy

# --- 설정 변수 ---
script_dir = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(script_dir, 'logs')
RESULTS_CSV = os.path.join(LOGS_DIR, 'WFO_Results.csv')
REALTIME_LOG = os.path.join(LOGS_DIR, 'WFO_Realtime.log')
LOSING_TRADES_LOG = os.path.join(LOGS_DIR, 'WFO_Losing_Trades.log')
GRAPH_FILE = os.path.join(LOGS_DIR, 'WFO_Chart.png') # 그래프 저장 경로 추가

# 데이터 경로 (optimizer_platform.py와 동일)
DATA_DIR = os.path.abspath(os.path.join(script_dir, '..', 'binance_test', 'data', 'BTC_USDT', '1m'))

# 워커 프로세스 공유 데이터
_SHARED_DF_POOL = {}

def init_worker(process_id, df_split):
    """워커 초기화: 각 워커는 담당할 데이터 조각(split)만 메모리에 올림"""
    global _SHARED_DF_POOL
    _SHARED_DF_POOL[process_id] = df_split
    # print(f"Worker {os.getpid()} initialized with data split of size {len(df_split)}")


def run_single_backtest_wfo(params_tuple):
    """WFO용 단일 백테스트 워커 함수"""
    process_id, strategy_class, strategy_params = params_tuple
    df = _SHARED_DF_POOL.get(process_id)

    if df is None:
        raise RuntimeError(f'Worker {os.getpid()} has no data for process {process_id}')

    result = run_backtest(
        df_original=df,
        strategy_class=strategy_class,
        strategy_params=strategy_params,
        trade_type='long_and_short',
        initial_capital=10000,
        fee=0.001,
        leverage=10,
        atr_stop_loss_multiplier=strategy_params.get('atr_multiplier', 2.0) # 파라미터에서 ATR 배수 가져오기
    )
    
    # 파라미터와 주요 결과만 반환
    return {
        'strategy': result['strategy'],
        'params': result['params'],
        'total_return_pct': result['total_return_pct'],
        'mdd_pct': result['mdd_pct'],
        'num_trades': result['num_trades'],
    }


def generate_param_grid():
    """최적화할 파라미터 그리드 생성 (다중 전략)"""
    all_grids = []

    # 1. RSI 전략 파라미터
    rsi_params = {
        'rsi_window': [14, 21],
        'oversold_threshold': [25, 30],
        'overbought_threshold': [70, 75],
        'atr_multiplier': [1.5, 2.0]
    }
    rsi_grid = [(RsiMeanReversion, dict(zip(rsi_params.keys(), p))) for p in itertools.product(*rsi_params.values())]
    all_grids.extend(rsi_grid)

    # 2. 볼린저 밴드 (ADX 필터) 전략 파라미터
    bb_adx_params = {
        'window': [20],
        'std_dev': [2],
        'adx_threshold': [20, 25],
        'atr_multiplier': [2.0, 3.0]
    }
    bb_adx_grid = [(BollingerBandADXStrategy, dict(zip(bb_adx_params.keys(), p))) for p in itertools.product(*bb_adx_params.values())]
    all_grids.extend(bb_adx_grid)

    # 3. MACD (ADX 필터) 전략 파라미터
    macd_adx_params = {
        'fastperiod': [12],
        'slowperiod': [26],
        'signalperiod': [9],
        'adx_threshold': [20, 25],
        'atr_multiplier': [2.0, 3.0]
    }
    macd_adx_grid = [(MacdADXStrategy, dict(zip(macd_adx_params.keys(), p))) for p in itertools.product(*macd_adx_params.values())]
    all_grids.extend(macd_adx_grid)
    
    # 4. 스토캐스틱 전략 파라미터
    stoch_params = {
        'fastk_period': [14],
        'slowk_period': [3],
        'slowd_period': [3],
        'oversold': [20, 30],
        'overbought': [70, 80],
        'atr_multiplier': [1.5, 2.0]
    }
    stoch_grid = [(StochasticStrategy, dict(zip(stoch_params.keys(), p))) for p in itertools.product(*stoch_params.values())]
    all_grids.extend(stoch_grid)
    
    return all_grids


def log_realtime(message):
    log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(log_message)
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        with open(REALTIME_LOG, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')
    except Exception: pass


def plot_wfo_results(full_df, combined_equity, all_trades, suffix=""):
    """WFO 전체 결과 그래프를 생성하고 저장"""
    if suffix:
        GRAPH_FILE = os.path.join(LOGS_DIR, f'WFO_Chart{suffix}.png')
    else:
        GRAPH_FILE = os.path.join(LOGS_DIR, 'WFO_Chart.png')

    log_realtime(f"📊 최종 결과 그래프 생성 중... ({GRAPH_FILE})")

    # 1. 진입/청산 포인트 만들기
    buy_signals = []
    sell_signals = []
    for trade in all_trades:
        if trade['type'] == 'long':
            buy_signals.append((trade['entry_time'], trade['entry_price'] * 0.99)) # 화살표 위치 조정
        elif trade['type'] == 'short':
            sell_signals.append((trade['entry_time'], trade['entry_price'] * 1.01))

    # mplfinance에 맞는 형식으로 변환
    buy_markers = [np.nan] * len(full_df)
    sell_markers = [np.nan] * len(full_df)
    
    for time, price in buy_signals:
        if time in full_df.index:
            idx = full_df.index.get_loc(time)
            buy_markers[idx] = price
            
    for time, price in sell_signals:
        if time in full_df.index:
            idx = full_df.index.get_loc(time)
            sell_markers[idx] = price

    # 2. 그래프 그리기
    fig, axes = plt.subplots(2, 1, figsize=(20, 12), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
    ax1 = axes[0]
    ax2 = axes[1]
    
    # 추가 플롯 설정 (매수/매도 마커)
    ap = [
        mpf.make_addplot(buy_markers, type='scatter', marker='^', color='g', markersize=100, ax=ax1),
        mpf.make_addplot(sell_markers, type='scatter', marker='v', color='r', markersize=100, ax=ax1)
    ]

    # 차트 1: 캔들차트 + 진입 포인트
    mpf.plot(full_df, type='candle', ax=ax1, style='yahoo', volume=False,
             ylabel='Price (USDT)', addplot=ap)
    ax1.set_title('Walk-Forward Optimization - BTC/USDT Price and Trades')
    ax1.legend(['Buy', 'Sell'])
    
    # 차트 2: 자산 변화 곡선
    ax2.plot(combined_equity.index, combined_equity['equity'], color='blue')
    ax2.set_title('Equity Curve')
    ax2.set_ylabel('Equity (USDT)')
    ax2.grid(True)
    
    plt.tight_layout()
    try:
        fig.savefig(GRAPH_FILE)
        log_realtime(f"💾 그래프 저장 완료: {GRAPH_FILE}")
    except Exception as e:
        log_realtime(f"❌ 그래프 저장 실패: {e}")
    plt.close(fig)


def main(run_id=None):
    # 결과 파일을 위한 접미사 설정
    suffix = f"_{run_id}" if run_id else ""
    RESULTS_CSV = os.path.join(LOGS_DIR, f'WFO_Results{suffix}.csv')
    REALTIME_LOG = os.path.join(LOGS_DIR, f'WFO_Realtime{suffix}.log')
    LOSING_TRADES_LOG = os.path.join(LOGS_DIR, f'WFO_Losing_Trades{suffix}.log')
    EQUITY_CURVE_CSV = os.path.join(LOGS_DIR, f'WFO_Equity{suffix}.csv')
    
    log_realtime("="*80)
    log_realtime(f"🚀 Walk-Forward Optimizer 시작 (Run ID: {run_id or 'default'})")

    # 이전 손실 거래 로그 파일 삭제
    if os.path.exists(LOSING_TRADES_LOG):
        os.remove(LOSING_TRADES_LOG)

    # 1. 데이터 로드 (2025년 1월 ~ 2월)
    try:
        jan_path = os.path.join(DATA_DIR, '2025-01.csv')
        data_frames = []
        
        for month in range(1, 8): # 1월부터 7월까지
            file_path = os.path.join(DATA_DIR, f'2025-{month:02d}.csv')
            try:
                df_month = pd.read_csv(file_path, index_col='timestamp', parse_dates=True)
                data_frames.append(df_month)
            except FileNotFoundError:
                log_realtime(f"경고: {file_path} 파일을 찾을 수 없어 건너뜁니다.")

        if not data_frames:
            raise FileNotFoundError("로드할 데이터 파일이 하나도 없습니다.")
            
        full_df = pd.concat(data_frames).sort_index().drop_duplicates()
        log_realtime(f"전체 데이터 로드 완료: {len(full_df):,}개 (기간: {full_df.index[0]} ~ {full_df.index[-1]})")
    except FileNotFoundError as e:
        log_realtime(f"❌ 데이터 로딩 실패: {e}. 경로를 확인하세요: {DATA_DIR}")
        return

    # 2. Walk-Forward 파라미터 설정
    total_days = (full_df.index[-1] - full_df.index[0]).days
    train_days = 30  # 10일치 데이터로 훈련
    test_days = 3   # 3일치 데이터로 검증
    step_days = 3   # 3일씩 창문을 이동

    log_realtime(f"WFO 설정: 총 {total_days}일, 훈련 {train_days}일, 검증 {test_days}일, 스텝 {step_days}일")

    # 3. 파라미터 그리드 생성
    param_grid = generate_param_grid()
    log_realtime(f"테스트할 전략/파라미터 조합 수: {len(param_grid)}개")
    
    # 4. 메인 WFO 루프
    all_oos_results = [] # Out-of-Sample(검증) 결과만 저장할 리스트
    all_equity_curves = [] # 자산 변화 곡선을 저장할 리스트
    all_oos_trades = [] # 전체 거래 내역을 저장할 리스트
    initial_wfo_capital = 10000.0  # WFO 전체 기간의 초기 자본
    current_capital = initial_wfo_capital  # 각 OOS 기간의 시작 자본 (연속적으로 업데이트)
    start_date = full_df.index[0]
    iteration = 1

    max_workers = max(1, (multiprocessing.cpu_count() or 2) - 1)

    while True:
        train_start = start_date
        train_end = train_start + pd.Timedelta(days=train_days)
        test_start = train_end
        test_end = test_start + pd.Timedelta(days=test_days)

        if test_end > full_df.index[-1]:
            break

        log_realtime("-" * 80)
        log_realtime(f"WFO Iteration #{iteration}")
        log_realtime(f"  - 훈련(In-Sample) 기간: {train_start} ~ {train_end}")
        log_realtime(f"  - 검증(Out-of-Sample) 기간: {test_start} ~ {test_end}")

        # 데이터 분할
        train_df = full_df.loc[train_start:train_end]

        # In-Sample 최적화 (병렬 처리)
        in_sample_results = []
        process_id = os.getpid() # 이 루프의 고유 ID

        with ProcessPoolExecutor(max_workers=max_workers, initializer=init_worker, initargs=(process_id, train_df)) as executor:
            jobs = [(process_id, strategy, params) for strategy, params in param_grid]
            futures = {executor.submit(run_single_backtest_wfo, job): job for job in jobs}

            for future in as_completed(futures):
                try:
                    in_sample_results.append(future.result())
                except Exception as e:
                    log_realtime(f"  - 훈련 중 오류: {e}")
        
        if not in_sample_results:
            log_realtime("  - 훈련 결과가 없습니다. 다음 Iteration으로 넘어갑니다.")
            start_date += pd.Timedelta(days=step_days)
            iteration += 1
            continue

        # 훈련 기간의 최고 성과 파라미터 찾기
        best_in_sample = max(in_sample_results, key=lambda x: x['total_return_pct'])
        best_strategy = best_in_sample['strategy']
        best_params = best_in_sample['params']
        log_realtime(f"  - 훈련 최고 성과: {best_strategy} | {best_params} | Return={best_in_sample['total_return_pct']:.2f}%")

        # Out-of-Sample 검증 (단일 실행)
        test_df = full_df.loc[test_start:test_end]
        oos_result = run_backtest(
            df_original=test_df,
            strategy_class=eval(best_strategy), # 클래스 이름으로 실제 클래스 객체 찾기
            strategy_params=best_params,
            trade_type='long_and_short',
            initial_capital=current_capital, # 이전 OOS의 최종 자본을 초기 자본으로 사용
            fee=0.001,
            leverage=10,
            atr_stop_loss_multiplier=best_params.get('atr_multiplier', 2.0) # 최고 파라미터의 ATR 배수 적용
        )
        
        log_realtime(f"  - 🟢 검증(OOS) 결과: Return={oos_result['total_return_pct']:.2f}%, MDD={oos_result['mdd_pct']:.2f}%, Trades={oos_result['num_trades']}")
        
        # 자산 변화 곡선 저장
        all_equity_curves.append(oos_result['equity_curve'])
        all_oos_trades.extend(oos_result.get('trades', [])) # 모든 거래 내역 추가

        # 손실 거래 기록
        losing_trades = [t for t in oos_result.get('trades', []) if t.get('pnl', 0) < 0]
        if losing_trades:
            try:
                with open(LOSING_TRADES_LOG, 'a', encoding='utf-8') as f:
                    f.write(f"--- Iteration #{iteration} ({test_start} ~ {test_end}) ---\n")
                    for trade in losing_trades:
                        pnl_pct = trade.get('pnl_pct', 0)
                        log_line = (
                            f"  - Type: {trade.get('type')}, "
                            f"Entry: {trade.get('entry_time')}, "
                            f"Exit: {trade.get('exit_time')}, "
                            f"PnL %: {pnl_pct:.2f}%\n"
                        )
                        f.write(log_line)
            except Exception as e:
                log_realtime(f"  - 손실 거래 로그 기록 중 오류: {e}")

        # OOS 결과 저장
        all_oos_results.append({
            'iteration': iteration,
            'train_start': train_start, 'train_end': train_end,
            'test_start': test_start, 'test_end': test_end,
            'best_strategy': best_strategy,
            'best_params': json.dumps(best_params), # for CSV compatibility
            'oos_initial_capital': oos_result['initial_capital'],
            'oos_final_capital': oos_result['final_capital'],
            'oos_return_pct': oos_result['total_return_pct'],
            'oos_mdd_pct': oos_result['mdd_pct'],
            'oos_num_trades': oos_result['num_trades']
        })

        # 다음 OOS를 위해 자본금 업데이트
        current_capital = oos_result['final_capital']

        # 다음 Window로 이동
        start_date += pd.Timedelta(days=step_days)
        iteration += 1

    # 5. 최종 결과 종합 및 저장
    log_realtime("-" * 80)
    log_realtime("✅ Walk-Forward 최적화 완료")
    
    if all_oos_results:
        results_df = pd.DataFrame(all_oos_results)
        results_df.to_csv(RESULTS_CSV, index=False, encoding='utf-8-sig')
        log_realtime(f"💾 최종 결과 저장 완료: {RESULTS_CSV}")

        # 전체 기간의 자산 변화 곡선 저장
        if all_equity_curves:
            combined_equity_series = pd.concat(all_equity_curves).sort_index()
            # 중복된 인덱스(날짜)가 있을 경우 평균값 사용
            combined_equity_series = combined_equity_series.groupby(combined_equity_series.index).mean()
            # Series를 'equity' 열을 가진 DataFrame으로 변환
            combined_equity = combined_equity_series.to_frame(name='equity')
            
            combined_equity.to_csv(EQUITY_CURVE_CSV) # header는 DataFrame의 열 이름을 따름
            log_realtime(f"💾 자산 변화 데이터 저장 완료: {EQUITY_CURVE_CSV}")

            # 그래프 생성 및 저장
            plot_wfo_results(full_df, combined_equity, all_oos_trades, suffix)

        # 종합 성과 계산
        final_capital = results_df['oos_final_capital'].iloc[-1] if not results_df.empty else initial_wfo_capital
        total_oos_return_pct = ((final_capital / initial_wfo_capital) - 1) * 100 if initial_wfo_capital > 0 else 0
        
        total_oos_mdd = results_df['oos_mdd_pct'].mean()
        total_oos_trades = results_df['oos_num_trades'].sum()

        log_realtime("\n--- WFO 종합 성과 (Out-of-Sample) ---")
        log_realtime(f"  - 총 검증 기간: {len(all_oos_results)}개")
        log_realtime(f"  - 초기 자본: ${initial_wfo_capital:,.2f}")
        log_realtime(f"  - 최종 자본: ${final_capital:,.2f}")
        log_realtime(f"  - 총 수익률: {total_oos_return_pct:.2f}%")
        log_realtime(f"  - 평균 MDD (per test period): {total_oos_mdd:.2f}%")
        log_realtime(f"  - 총 거래 수: {total_oos_trades}회")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Walk-Forward Optimizer Script")
    parser.add_argument('--run_id', type=str, help='A unique ID for the run to save result files separately.')
    args = parser.parse_args()
    main(run_id=args.run_id)
