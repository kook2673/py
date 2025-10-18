# -*- coding: utf-8 -*-
"""
전략 플랫폼용 파라미터 최적화(Optimizer) 스크립트

이 스크립트는 'strategy_platform.py'에 정의된 다양한 전략들을 대상으로
지정된 파라미터 범위에 대한 그리드 탐색(Grid Search)을 수행하여 최적의 조합을 찾습니다.

주요 기능:
- 멀티프로세싱(병렬 처리)을 활용하여 최적화 속도 향상.
- 테스트할 전략(예: RSI, 볼린저 밴드)을 쉽게 선택하고 해당 전략의 파라미터 범위를 지정.
- 진행 상황을 JSON 파일에 저장하여, 스크립트가 중단되더라도 이어서 작업 가능.
- 최종 결과를 CSV 파일로 저장하여 Excel 등에서 쉽게 분석.
"""

import os
import json
import glob
import itertools
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

import pandas as pd

# 새로 만든 백테스팅 플랫폼에서 필요 함수/클래스 임포트
from strategy_platform import run_backtest, RsiMeanReversion, BollingerBandStrategy, MacdStrategy

# --- 설정 변수 ---
# 로그 및 결과 파일 경로
script_dir = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(script_dir, 'logs')
PROGRESS_FILE = os.path.join(LOGS_DIR, 'Opt_Platform_Progress.json')
RESULTS_CSV = os.path.join(LOGS_DIR, 'Opt_Platform_Results.csv')
REALTIME_LOG = os.path.join(LOGS_DIR, 'Opt_Platform_Realtime.log')

# 데이터 경로 (수정됨)
# 경로 수정: binance_test2 폴더 기준으로 상위 폴더의 binance_test 폴더를 바라보도록 변경
DATA_DIR = os.path.abspath(os.path.join(script_dir, '..', 'binance_test', 'data', 'BTC_USDT', '1m'))

# 워커 프로세스 공유 데이터 (메모리에 한 번만 로드하기 위함)
_SHARED_DF = None


def init_worker():
    """워커 초기화: 전체 데이터를 메모리에 한 번만 로드"""
    global _SHARED_DF
    try:
        log_realtime("📥 워커에서 데이터 로드 중...")
        
        # 2025년 1월 ~ 2월 데이터 사용 (테스트를 위해 기간 단축)
        all_files = []
        for month in range(1, 3):
            month_pattern = f'2025-{month:02d}.csv'
            files = glob.glob(os.path.join(DATA_DIR, month_pattern))
            all_files.extend(files)
        
        if not all_files:
            raise RuntimeError(f"데이터 파일을 찾을 수 없습니다: {DATA_DIR}")
        
        dfs = [pd.read_csv(f, index_col='timestamp', parse_dates=True) for f in sorted(all_files)]
        _SHARED_DF = pd.concat(dfs).sort_index().drop_duplicates()
        log_realtime(f"🎉 데이터 로드 완료: 총 {len(_SHARED_DF):,}개 데이터")
        
    except Exception as e:
        _SHARED_DF = None
        raise RuntimeError(f'워커 데이터 로드 실패: {e}')


def run_single_backtest(params_tuple):
    """워커에서 실행될 단일 백테스트 함수"""
    strategy_class, strategy_params = params_tuple
    
    if _SHARED_DF is None:
        raise RuntimeError('공유 데이터프레임이 초기화되지 않았습니다.')

    # 백테스트 실행
    result = run_backtest(
        df_original=_SHARED_DF,
        strategy_class=strategy_class,
        strategy_params=strategy_params,
        trade_type='long_and_short', # 모든 최적화는 롱/숏 양방향으로 진행
        initial_capital=10000,
        fee=0.001,
        leverage=10
    )
    
    # 결과 요약
    # 파라미터를 문자열 키로 변환 (JSON 호환)
    param_key = f"{strategy_class.__name__}_{'_'.join([f'{k}{v}' for k, v in strategy_params.items()])}"
    
    out = {
        'key': param_key,
        'strategy': result['strategy'],
        'total_return_pct': result['total_return_pct'],
        'mdd_pct': result['mdd_pct'],
        'num_trades': result['num_trades'],
        'win_rate_pct': result['win_rate_pct'],
    }
    # 파라미터들을 개별 컬럼으로 추가
    out.update(strategy_params)
    return out


def generate_param_grid():
    """최적화할 파라미터 그리드 생성"""
    
    # --- 테스트할 전략과 파라미터 범위를 여기에 정의 ---

    # 1. RSI 전략 파라미터
    rsi_params = {
        'rsi_window': [14, 21, 30],
        'oversold_threshold': [20, 25, 30],
        'overbought_threshold': [70, 75, 80]
    }
    rsi_grid = [
        (RsiMeanReversion, dict(zip(rsi_params.keys(), p))) 
        for p in itertools.product(*rsi_params.values())
    ]

    # 2. 볼린저 밴드 전략 파라미터
    bb_params = {
        'window': [20, 30],
        'std_dev': [2.0, 2.5]
    }
    bb_grid = [
        (BollingerBandStrategy, dict(zip(bb_params.keys(), p)))
        for p in itertools.product(*bb_params.values())
    ]

    # 3. MACD 전략 파라미터
    macd_params = {
        'fastperiod': [12, 20],
        'slowperiod': [26, 40],
        'signalperiod': [9, 12]
    }
    macd_grid = [
        (MacdStrategy, dict(zip(macd_params.keys(), p)))
        for p in itertools.product(*macd_params.values())
    ]


    # --- 생성된 그리드를 합쳐서 반환 ---
    # 여기 주석을 풀거나 추가하여 다른 전략도 테스트 가능
    final_grid = rsi_grid + bb_grid + macd_grid
    # final_grid = macd_grid # MACD만 테스트하고 싶을 경우
    
    return final_grid


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception: return {}
    return {}


def save_progress(progress):
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def log_realtime(message):
    log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(log_message)
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        with open(REALTIME_LOG, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')
    except Exception: pass


def main():
    log_realtime("🚀 전략 플랫폼 옵티마이저 시작")
    
    param_grid = generate_param_grid()
    total_jobs = len(param_grid)
    log_realtime(f"총 {total_jobs:,}개의 파라미터 조합 테스트 시작")

    progress = load_progress()
    done_keys = set(progress.get('done_keys', []))

    pending_jobs = []
    for strategy_class, params in param_grid:
        key = f"{strategy_class.__name__}_{'_'.join([f'{k}{v}' for k, v in params.items()])}"
        if key not in done_keys:
            pending_jobs.append((strategy_class, params))

    log_realtime(f"대기 작업: {len(pending_jobs):,}개 (이미 완료: {len(done_keys):,}개)")

    if not pending_jobs:
        log_realtime("✅ 모든 작업이 이미 완료되었습니다.")
        return

    # CPU 코어 수에 맞춰 워커 수 조절
    max_workers = max(1, (multiprocessing.cpu_count() or 2) - 1)
    log_realtime(f"병렬 워커 수: {max_workers}개")

    results = []
    
    with ProcessPoolExecutor(max_workers=max_workers, initializer=init_worker) as executor:
        futures = {executor.submit(run_single_backtest, job): job for job in pending_jobs}
        
        for i, future in enumerate(as_completed(futures), 1):
            try:
                result = future.result()
                results.append(result)
                done_keys.add(result['key'])

                sign = '🟢' if result['total_return_pct'] > 0 else '🔴'
                log_realtime(f"{sign} {i}/{len(pending_jobs)} | {result['key']} => "
                             f"Return={result['total_return_pct']:.2f}%, MDD={result['mdd_pct']:.2f}%")

            except Exception as e:
                log_realtime(f"❌ 오류 발생: {futures[future]} - {e}")

            if i % 5 == 0 or i == len(pending_jobs):
                progress['done_keys'] = list(done_keys)
                save_progress(progress)
                
                # 중간 결과 저장
                if results:
                    pd.DataFrame(results).to_csv(RESULTS_CSV, index=False, encoding='utf-8-sig')

    log_realtime("\n✅ 최적화 완료")
    if results:
        df_results = pd.DataFrame(results)
        df_sorted = df_results.sort_values(by='total_return_pct', ascending=False)
        
        # 최종 결과 저장
        df_sorted.to_csv(RESULTS_CSV, index=False, encoding='utf-8-sig')
        log_realtime(f"💾 최종 결과 저장 완료: {RESULTS_CSV}")

        log_realtime("\n🏆 TOP 10 전략 (수익률 기준):")
        print(df_sorted.head(10).to_string())


if __name__ == '__main__':
    main()
