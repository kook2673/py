# -*- coding: utf-8 -*-
"""
스캘핑 최적화 워커 프로세스 관련 함수들
"""

import os
import glob
import pandas as pd
from config import DATA_DIR, CSV_PATTERN, BACKTEST_CONFIG
from Scalp_1m_5MA20MA_Backtest import backtest

# 워커 프로세스가 공유할 데이터프레임 (각 워커에서 1회만 로드)
_SHARED_DF = None


def _init_worker(data_dir: str = None, csv_pattern: str = None):
    """워커 프로세스 초기화 - 데이터 로드"""
    global _SHARED_DF
    
    # 기본값 사용
    if data_dir is None:
        data_dir = DATA_DIR
    if csv_pattern is None:
        csv_pattern = CSV_PATTERN
    
    try:
        files = glob.glob(os.path.join(data_dir, csv_pattern))
        dfs = []
        for f in sorted(files):
            df = pd.read_csv(f, index_col='timestamp', parse_dates=True)
            dfs.append(df)
        _SHARED_DF = pd.concat(dfs).sort_index().drop_duplicates()
    except Exception as e:
        _SHARED_DF = None
        raise RuntimeError(f'워커 데이터 로드 실패: {e}')


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
        fee=BACKTEST_CONFIG['fee'],
        leverage=BACKTEST_CONFIG['leverage'],
        volume_window=BACKTEST_CONFIG['volume_window'],
        volume_multiplier=vm,
        min_pass_filters=mfc,
        risk_fraction=BACKTEST_CONFIG['risk_fraction'],
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


def get_worker_initializer():
    """워커 초기화 함수 반환"""
    return _init_worker


def get_single_runner():
    """단일 실행 함수 반환"""
    return _run_single
