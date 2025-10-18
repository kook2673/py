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

import pandas as pd
import numpy as np

from strategy_platform import run_backtest, RsiMeanReversion, BollingerBandStrategy, MacdStrategy

# --- 설정 변수 ---
script_dir = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(script_dir, 'logs')
RESULTS_CSV = os.path.join(LOGS_DIR, 'WFO_Results.csv')
REALTIME_LOG = os.path.join(LOGS_DIR, 'WFO_Realtime.log')

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
        leverage=10
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
    """최적화할 파라미터 그리드 생성 (optimizer_platform.py와 유사)"""
    # 테스트를 위해 파라미터 조합 수를 줄임
    rsi_params = {'rsi_window': [14, 21], 'oversold_threshold': [25, 30], 'overbought_threshold': [70, 75]}
    rsi_grid = [(RsiMeanReversion, dict(zip(rsi_params.keys(), p))) for p in itertools.product(*rsi_params.values())]
    
    # WFO는 시간이 오래 걸리므로, 우선 RSI 전략 하나만 테스트
    return rsi_grid


def log_realtime(message):
    log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(log_message)
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        with open(REALTIME_LOG, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')
    except Exception: pass


def main():
    log_realtime("🚀 Walk-Forward Optimizer 시작")

    # 1. 데이터 로드 (2025년 1월 ~ 2월)
    try:
        jan_path = os.path.join(DATA_DIR, '2025-01.csv')
        feb_path = os.path.join(DATA_DIR, '2025-02.csv')
        df_jan = pd.read_csv(jan_path, index_col='timestamp', parse_dates=True)
        df_feb = pd.read_csv(feb_path, index_col='timestamp', parse_dates=True)
        full_df = pd.concat([df_jan, df_feb]).sort_index().drop_duplicates()
        log_realtime(f"전체 데이터 로드 완료: {len(full_df):,}개 (기간: {full_df.index[0]} ~ {full_df.index[-1]})")
    except FileNotFoundError:
        log_realtime(f"❌ 데이터 파일을 찾을 수 없습니다. 경로를 확인하세요: {DATA_DIR}")
        return

    # 2. Walk-Forward 파라미터 설정
    total_days = (full_df.index[-1] - full_df.index[0]).days
    train_days = 10  # 10일치 데이터로 훈련
    test_days = 3   # 3일치 데이터로 검증
    step_days = 3   # 3일씩 창문을 이동

    log_realtime(f"WFO 설정: 총 {total_days}일, 훈련 {train_days}일, 검증 {test_days}일, 스텝 {step_days}일")

    # 3. 파라미터 그리드 생성
    param_grid = generate_param_grid()
    log_realtime(f"테스트할 전략/파라미터 조합 수: {len(param_grid)}개")
    
    # 4. 메인 WFO 루프
    all_oos_results = [] # Out-of-Sample(검증) 결과만 저장할 리스트
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
            initial_capital=10000,
            fee=0.001,
            leverage=10
        )
        
        log_realtime(f"  - 🟢 검증(OOS) 결과: Return={oos_result['total_return_pct']:.2f}%, MDD={oos_result['mdd_pct']:.2f}%, Trades={oos_result['num_trades']}")
        
        # OOS 결과 저장
        all_oos_results.append({
            'iteration': iteration,
            'train_start': train_start, 'train_end': train_end,
            'test_start': test_start, 'test_end': test_end,
            'best_strategy': best_strategy,
            'best_params': json.dumps(best_params), # for CSV compatibility
            'oos_return_pct': oos_result['total_return_pct'],
            'oos_mdd_pct': oos_result['mdd_pct'],
            'oos_num_trades': oos_result['num_trades']
        })

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

        # 종합 성과 계산
        total_oos_return = results_df['oos_return_pct'].mean()
        total_oos_mdd = results_df['oos_mdd_pct'].mean()
        total_oos_trades = results_df['oos_num_trades'].sum()

        log_realtime("\n--- WFO 종합 성과 (Out-of-Sample) ---")
        log_realtime(f"  - 총 검증 기간: {len(all_oos_results)}개")
        log_realtime(f"  - 평균 수익률 (per test period): {total_oos_return:.2f}%")
        log_realtime(f"  - 평균 MDD (per test period): {total_oos_mdd:.2f}%")
        log_realtime(f"  - 총 거래 수: {total_oos_trades}회")

if __name__ == '__main__':
    main()
