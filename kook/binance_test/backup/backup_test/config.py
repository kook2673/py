# -*- coding: utf-8 -*-
"""
스캘핑 최적화 설정 파일
"""

import os

# 스크립트 위치 기준 경로
script_dir = os.path.dirname(os.path.abspath(__file__))

# 파일 경로 설정
PROGRESS_FILE = os.path.join(script_dir, 'logs', 'Scalp_Opt_Progress.json')
RESULTS_CSV = os.path.join(script_dir, 'logs', 'Scalp_Opt_Results.csv')
RESULTS_JSON = os.path.join(script_dir, 'logs', 'Scalp_Opt_Results.json')
REALTIME_LOG = os.path.join(script_dir, 'logs', 'Scalp_Opt_Realtime.log')

# 수익률 양수 결과 파일 경로
PROFITABLE_CSV = os.path.join(script_dir, 'logs', 'Scalp_Opt_Profitable_Results.csv')
PROFITABLE_JSON = os.path.join(script_dir, 'logs', 'Scalp_Opt_Profitable_Results.json')

# 데이터 경로 설정
DATA_DIR = os.path.join(script_dir, 'data', 'BTC_USDT', '1m')
CSV_PATTERN = '2025-03.csv'  # 필요 시 변경

# 파라미터 그리드 설정
FAST_WINDOWS = list(range(3, 21))        # 3~20
SLOW_WINDOWS = list(range(20, 61, 5))    # 20~60 step=5
STOP_LOSSES = [0.0003, 0.0005, 0.0007, 0.0010, 0.0015, 0.0020, 0.0030]
VOL_MULTIPLIERS = [1.0, 1.1, 1.2, 1.3]
MIN_FILTER_COUNTS = list(range(0, 11, 2))
TIMEFRAMES = [1, 3, 5]  # 1분, 3분, 5분

# 백테스트 설정
BACKTEST_CONFIG = {
    'fee': 0.0005,
    'leverage': 10,
    'volume_window': 20,
    'risk_fraction': 1.0
}

# 병렬 처리 설정
MAX_WORKERS_LIMIT = 13  # 최대 워커 수 제한
