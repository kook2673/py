# -*- coding: utf-8 -*-
"""
1분/3분/5분 스캘핑(일반화 MA) 최적화 스크립트
- 빠른/느린 MA 기간, 손절 비율, 거래량 배수, 필터 최소 통과 개수, 타임프레임(1/3/5분)을 그리드 탐색
- 병렬 처리 지원 (멀티프로세스)
- 진행상태를 JSON에 저장하여, 중단 후 재실행 시 이어서 진행
- 개별 전략 결과를 로깅하고, 최종 종합 결과 CSV/JSON으로 저장

사용법:
  python Scalp_1m_5MA20MA_Optimizer.py
"""

import os
import json
import glob
from datetime import datetime
import itertools
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

import numpy as np
import pandas as pd

from Scalp_1m_5MA20MA_Backtest import backtest

# 로그 파일 경로 (스크립트 위치 기준)
script_dir = os.path.dirname(os.path.abspath(__file__))
PROGRESS_FILE = os.path.join(script_dir, 'logs', 'Scalp_Opt_Progress.json')
RESULTS_CSV = os.path.join(script_dir, 'logs', 'Scalp_Opt_Results.csv')
RESULTS_JSON = os.path.join(script_dir, 'logs', 'Scalp_Opt_Results.json')
REALTIME_LOG = os.path.join(script_dir, 'logs', 'Scalp_Opt_Realtime.log')

# 워커 프로세스가 공유할 데이터프레임 (각 워커에서 1회만 로드)
_SHARED_DF = None


def _init_worker(data_dir: str, csv_pattern: str):
    global _SHARED_DF
    try:
        files = glob.glob(os.path.join(data_dir, csv_pattern))
        dfs = []
        for f in sorted(files):
            df = pd.read_csv(f, index_col='timestamp', parse_dates=True)
            dfs.append(df)
        _SHARED_DF = pd.concat(dfs).sort_index().drop_duplicates()
    except Exception as e:
        _SHARED_DF = None


def _run_single(params):
    """워커에서 실행될 단일 조합 실행 함수.
    params: (fast_w, slow_w, sl, vm, mfc, tfm)
    """
    global _SHARED_DF
    fast_w, slow_w, sl, vm, mfc, tfm = params

    key = f'f{fast_w}_s{slow_w}_sl{sl}_vm{vm}_mfc{mfc}_tfm{tfm}'

    if _SHARED_DF is None:
        raise RuntimeError('Shared DF not initialized in worker')

    result = backtest(
        _SHARED_DF,
        stop_loss_pct=sl,
        fee=0.0005,
        leverage=10,
        volume_window=20,
        volume_multiplier=vm,
        min_pass_filters=mfc,
        risk_fraction=1.0,
        fast_ma_window=fast_w,
        slow_ma_window=slow_w,
        timeframe_minutes=tfm,
    )

    out = {
        'key': key,
        'fast_ma': fast_w,
        'slow_ma': slow_w,
        'stop_loss_pct': sl,
        'volume_multiplier': vm,
        'min_pass_filters': mfc,
        'timeframe_minutes': tfm,
        'total_return': result['total_return'],
        'mdd': result['mdd'],
        'final_capital': result['final_capital'],
        'trades': len([t for t in result['trades'] if t['type'] != 'LONG_ENTRY'])
    }
    return out


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_progress(progress: dict):
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    # 백업 저장
    try:
        if os.path.exists(PROGRESS_FILE):
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            os.replace(PROGRESS_FILE, PROGRESS_FILE + f'.bak')
    except Exception:
        pass
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def log_realtime(message: str):
    """실시간 진행상황을 파일과 콘솔에 동시 출력"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}] {message}"
    
    # 콘솔 출력
    print(log_message)
    
    # 파일에 저장
    try:
        os.makedirs(os.path.dirname(REALTIME_LOG), exist_ok=True)
        with open(REALTIME_LOG, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')
    except Exception as e:
        print(f"⚠️ 실시간 로그 저장 실패: {e}")


def generate_param_grid():
    # 조정 가능: 범위를 넓히면 시간이 급증
    fast_windows = list(range(3, 21))        # 5~20
    slow_windows = list(range(20, 61, 5))    # 20~60 step=5
    # 손절 비율을 더 촘촘하게: 0.03%~0.30% 근처 구간 포함
    stop_losses = [0.0003, 0.0005, 0.0007, 0.0010, 0.0015, 0.0020, 0.0030]
    vol_multipliers = [1.0, 1.1, 1.2, 1.3]
    min_filter_counts = list(range(0, 11, 2))
    timeframes = [1, 3, 5]  # 1분, 3분, 5분 탐색

    # fast < slow 조합만 사용
    combos = [(f, s) for f in fast_windows for s in slow_windows if f < s]

    # (f, s, sl, vm, mfc, tfm) 튜플 목록 반환
    grid = [
        (f, s, sl, vm, mfc, tfm)
        for (f, s), sl, vm, mfc, tfm in itertools.product(
            combos, stop_losses, vol_multipliers, min_filter_counts, timeframes
        )
    ]
    return grid


def main():
    log_realtime('🚀 스캘핑 최적화 시작 (병렬, 재개 지원)')
    log_realtime('=' * 60)

    # 데이터 경로 (워커 초기화용)
    data_dir = os.path.join(script_dir, 'data', 'BTC_USDT', '1m')
    csv_pattern = '2025-03.csv'  # 필요 시 변경

    # 파라미터 그리드
    grid = generate_param_grid()
    total = len(grid)
    log_realtime(f'총 조합 수: {total:,}개')

    # 진행상태 불러오기
    progress = load_progress()
    done_set = set(progress.get('done_keys', []))

    # 미완료 조합만 필터링
    pending = []
    for f, s, sl, vm, mfc, tfm in grid:
        key = f'f{f}_s{s}_sl{sl}_vm{vm}_mfc{mfc}_tfm{tfm}'
        if key not in done_set:
            pending.append((f, s, sl, vm, mfc, tfm))
    log_realtime(f'대기 작업: {len(pending):,}개 (이미 완료: {len(done_set):,}개)')

    if not pending:
        log_realtime('✅ 진행할 작업이 없습니다. (모두 완료)')
        return

    # 워커 수 결정 (5600X 6코어 12스레드에 최적화)
    max_workers = max(1, min((multiprocessing.cpu_count() or 2) - 1, 12))
    log_realtime(f'병렬 워커 수: {max_workers}개')

    results = []

    # 워커 초기화(데이터 1회 로드)
    with ProcessPoolExecutor(max_workers=max_workers, initializer=_init_worker, initargs=(data_dir, csv_pattern)) as ex:
        futures = {ex.submit(_run_single, p): p for p in pending}
        for i, fut in enumerate(as_completed(futures), start=1):
            params = futures[fut]
            try:
                out = fut.result()
                results.append(out)
                done_set.add(out['key'])

                # 진행중 출력
                sign = '🟢' if out['total_return'] > 0 else '🔴'
                log_realtime(f"{sign} {i}/{len(pending)} | tf={out['timeframe_minutes']}m, f={out['fast_ma']}, s={out['slow_ma']}, sl={out['stop_loss_pct']*100:.2f}%, vm={out['volume_multiplier']:.2f}, mfc={out['min_pass_filters']:02d} => ret={out['total_return']:+.2f}% MDD={out['mdd']:.2f}%")

            except Exception as e:
                # 오류난 조합도 키 기록해 중복 시도 방지 (원치 않으면 제외)
                f, s, sl, vm, mfc, tfm = params
                key = f'f{f}_s{s}_sl{sl}_vm{vm}_mfc{mfc}_tfm{tfm}'
                log_realtime(f'❌ 오류: {key} - {e}')
                done_set.add(key)

            # 체크포인트 저장(증분)
            progress['done_keys'] = list(done_set)
            progress['last_time'] = datetime.now().isoformat()
            progress['total'] = total
            save_progress(progress)

            # 중간 결과 저장
            try:
                os.makedirs(os.path.dirname(RESULTS_CSV), exist_ok=True)
                pd.DataFrame(results).to_csv(RESULTS_CSV, index=False, encoding='utf-8-sig')
                with open(RESULTS_JSON, 'w', encoding='utf-8') as f:
                    json.dump({'results': results}, f, ensure_ascii=False, indent=2)
            except Exception as e:
                log_realtime(f'⚠️ 중간결과 저장 실패: {e}')

    # 최종 요약
    if results:
        df_r = pd.DataFrame(results)
        best_by_return = df_r.loc[df_r['total_return'].idxmax()]
        best_by_mdd = df_r.loc[df_r['mdd'].idxmin()]
        log_realtime('\n✅ 최적화 완료')
        log_realtime('=' * 60)
        log_realtime('수익률 최고 전략:')
        log_realtime(str(best_by_return))
        log_realtime('\nMDD 최소 전략:')
        log_realtime(str(best_by_mdd))
        # 최종 저장(덮어쓰기)
        df_r.to_csv(RESULTS_CSV, index=False, encoding='utf-8-sig')
        with open(RESULTS_JSON, 'w', encoding='utf-8') as f:
            json.dump({'results': results, 'summary': {
                'best_by_return': best_by_return.to_dict(),
                'best_by_mdd': best_by_mdd.to_dict(),
            }}, f, ensure_ascii=False, indent=2)
    else:
        log_realtime('❌ 결과 없음')


if __name__ == '__main__':
    main()
