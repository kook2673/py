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
import io
import sys

# Windows 콘솔에서 UTF-8 출력이 깨지는 문제 해결
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json
import glob
import itertools
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import copy # Added for deepcopy
import numpy as np # Added for np.where
import pprint # Added for pprint

import pandas as pd

from matplotlib.ticker import FuncFormatter
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from tqdm import tqdm # Added for progress bar

import logging
import logging.handlers

# 경고 메시지 무시
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

# 새로 만든 백테스팅 플랫폼에서 필요 함수/클래스 임포트
from strategy_platform_kr import (
    MovingAverageMomentumStrategy, 
    KospidaqHybridStrategy, 
    SafeAssetRebalancingStrategy, 
    KospiDipBuyingStrategy,
    TurtleStrategy, # 터틀 전략 추가
    run_multi_strategy_backtest
)

# 로깅 설정
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, 'walk_forward_optimizer.log')

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file_path, mode='w', encoding='utf-8'), # 매 실행 시 로그파일 새로 작성
        logging.StreamHandler()
    ]
)

# --- Matplotlib 한글 폰트 설정 ---
def setup_korean_font():
    """한글 폰트를 설정하고 폰트 속성을 반환합니다."""
    try:
        # Windows
        font_path = fm.findfont(fm.FontProperties(family='Malgun Gothic'))
        plt.rcParams['font.family'] = 'Malgun Gothic'
    except:
        # Other OS (e.g., Mac)
        try:
            plt.rcParams['font.family'] = 'AppleGothic'
        except:
            # Font not found, matplotlib will use its default
            logging.warning("경고: '맑은 고딕' 또는 'AppleGothic' 폰트를 찾을 수 없어 기본 폰트를 사용합니다. 그래프의 한글이 깨질 수 있습니다.")
            pass

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

# =============================================================================
# WFO 실행을 위한 전략 및 파라미터 설정
# =============================================================================
STRATEGY_CONFIGS = {
    # 'MA_Momentum': {
    #     'class': MovingAverageMomentumStrategy,
    #     'universe': [], # load_universe_data에서 동적으로 채워짐
    #     'capital_allocation': 0.20,
    #     'params': {
    #         'max_buy_stocks': 30,
    #         'stock_specific_params': {} # load_universe_data에서 동적으로 채워짐
    #     }
    # },
    'Turtle': {
        'class': TurtleStrategy,
        'universe': [], # load_universe_data에서 동적으로 채워짐
        'capital_allocation': 1.0, # 터틀 전략에 100% 집중
        'params': {
            # 기본값 - WFO를 통해 최적화될 값들
            'entry_period': 20, 
            'exit_period': 10,
            'atr_period': 20,
            # 개선 사항에 대한 파라미터 추가
            'risk_per_trade': 0.01, # 1회 거래 시 포트폴리오의 1% 리스크
            'max_positions': 10,    # 최대 동시 보유 종목 수
            'stop_loss_atr_multiplier': 2.0 # 2-ATR 손절
        }
    },
    # 'Kospidaq_Hybrid': {
    #     'class': KospidaqHybridStrategy,
    #     'universe': ['122630', '252670', '233740', '251340'], # KODEX 레버리지, 인버스2X, KOSDAQ150레버리지, 인버스2X
    #     'capital_allocation': 0.20,
    #     'params': { # 이 값들은 WFO를 통해 out-of-sample마다 업데이트됨
    #         '122630': {'small_ma': 5, 'big_ma': 20},
    #         '252670': {'small_ma': 5, 'big_ma': 20},
    #         '233740': {'small_ma': 5, 'big_ma': 20},
    #         '251340': {'small_ma': 5, 'big_ma': 20},
    #     }
    # },
    # 'Safe_Asset': {
    #     'class': SafeAssetRebalancingStrategy,
    #     'universe': ['132030', '148020', '130680', '114260', '138220'], # KOSEF 국고채10년, 단기통안채, 국고채3년, G-FOCUS, KODEX 미국채10년선물
    #     'capital_allocation': 0.20,
    #     'params': {} # SafeAssetRebalancingStrategy는 자체 로직 사용
    # },
    # 'Dip_Buying': {
    #     'class': KospiDipBuyingStrategy,
    #     'universe': ['KOSPI', '122630'], # KOSPI 지수와 KODEX 레버리지 ETF
    #     'capital_allocation': 0.20,
    #     'params': {}
    # }
}


def init_worker():
    """워커 초기화: 전체 데이터를 메모리에 한 번만 로드"""
    global _SHARED_DF
    try:
        logging.info("📥 워커에서 데이터 로드 중...")
        
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
        logging.info(f"🎉 데이터 로드 완료: 총 {len(_SHARED_DF):,}개 데이터")
        
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
    """WFO의 각 훈련 기간(in-sample)마다 테스트할 파라미터 그리드를 생성합니다."""
    
    # MA_Momentum 전략에 대한 파라미터 그리드 정의
    params = {
        'small_ma': [5, 10, 20],
        'big_ma': [60, 120, 200],
        'max_buy_stocks': [10, 20, 30],
        'momentum_threshold': [0.4, 0.6] 
    }
    
    # small_ma < big_ma 조건을 만족하는 조합만 생성
    grid = []
    for p in itertools.product(*params.values()):
        param_dict = dict(zip(params.keys(), p))
        if param_dict['small_ma'] < param_dict['big_ma']:
            grid.append(param_dict)
            
    return grid


def generate_param_grid_for_turtle():
    """TurtleStrategy를 위한 파라미터 그리드를 생성합니다."""
    param_grid = []
    entry_periods = [20, 55]
    exit_periods = [10, 20]
    atr_periods = [20] # ATR 기간은 우선 20으로 고정
    
    for entry in entry_periods:
        for exit_p in exit_periods:
            if exit_p < entry: # 종료 기간은 진입 기간보다 짧아야 함
                for atr in atr_periods:
                    param_grid.append({
                        'entry_period': entry,
                        'exit_period': exit_p,
                        'atr_period': atr
                    })
    return param_grid

def optimize_turtle_strategy(train_data, turtle_base_config):
    """TurtleStrategy의 최적 파라미터를 찾습니다."""
    logging.info("[In-Sample] Turtle 전략 최적화 시작...")
    param_grid_turtle = generate_param_grid_for_turtle()
    best_in_sample_perf_turtle = -float('inf')
    best_params_turtle = None
    
    # 단일 전략 백테스트를 위한 설정 템플릿 생성
    single_strategy_config = {'Turtle': copy.deepcopy(turtle_base_config)}
    single_strategy_config['Turtle']['capital_allocation'] = 1.0

    for params in param_grid_turtle:
        single_strategy_config['Turtle']['params'] = params
        
        equity_df, _ = run_multi_strategy_backtest(
            universe_dfs=train_data,
            strategy_configs=single_strategy_config,
            initial_capital=100_000_000
        )

        if not equity_df.empty:
            total_return = (equity_df['total_equity'].iloc[-1] / equity_df['total_equity'].iloc[0] - 1) * 100
            if total_return > best_in_sample_perf_turtle:
                best_in_sample_perf_turtle = total_return
                best_params_turtle = params

    logging.info(f"[In-Sample] Turtle 전략 최적 파라미터: {best_params_turtle} (수익률: {best_in_sample_perf_turtle:.2f}%)")
    return best_params_turtle

def find_optimal_ma_for_ticker(df: pd.DataFrame, short_range: list, long_range: list) -> dict:
    """특정 종목(df)에 대해 최적의 MA 조합을 찾습니다."""
    best_perf = -float('inf')
    best_params = {'small_ma': short_range[0], 'big_ma': long_range[0]}

    # 모든 MA 조합에 대한 백테스트
    for s_ma in short_range:
        for l_ma in long_range:
            if s_ma >= l_ma:
                continue

            # MA 계산
            df['ma_short'] = df['close'].rolling(window=s_ma).mean()
            df['ma_long'] = df['close'].rolling(window=l_ma).mean()
            
            # 간단한 백테스트 로직
            df['position'] = np.where(df['ma_short'] > df['ma_long'], 1, 0)
            df['returns'] = df['close'].pct_change()
            df['strategy_returns'] = df['position'].shift(1) * df['returns']
            
            # 최종 수익률
            cumulative_return = (1 + df['strategy_returns']).cumprod().iloc[-1]
            
            if cumulative_return > best_perf:
                best_perf = cumulative_return
                best_params = {'small_ma': s_ma, 'big_ma': l_ma}
    
    return best_params

def find_optimal_params_for_kospidaq(train_universe: dict) -> dict:
    """Kospidaq_Hybrid 전략의 각 ETF에 대한 최적 MA 조합을 찾습니다."""
    
    tickers = ["122630", "252670", "233740", "251340"]
    short_ma_range = [3, 5, 10, 20]
    long_ma_range = [60, 120]
    
    optimal_params = {}

    for ticker in tickers:
        if ticker in train_universe and not train_universe[ticker].empty:
            df = train_universe[ticker]
            best_ma_pair = find_optimal_ma_for_ticker(df.copy(), short_ma_range, long_ma_range)
            optimal_params[ticker] = best_ma_pair
            
    return optimal_params


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


def plot_wfo_results(results_data, title='Walk-Forward Optimization Results'):
    """WFO 및 멀티-전략 백테스트 결과를 시각화"""
    
    setup_korean_font()
    plt.rcParams['axes.unicode_minus'] = False

    plt.figure(figsize=(15, 8))

    for name, curve in results_data.items():
        if curve.empty:
            continue
        
        equity_curve = curve.iloc[:, 0] if isinstance(curve, pd.DataFrame) else curve
        
        if equity_curve.empty or equity_curve.iloc[0] == 0:
            ret, mdd = 0.0, 0.0
        else:
            ret = (equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100
            rolling_max = equity_curve.cummax()
            drawdown = equity_curve / rolling_max - 1
            mdd = drawdown.min() * 100

        label = f"{name} (Return: {ret:.2f}%, MDD: {mdd:.2f}%)"
        linewidth = 2.5 if name == 'Total Portfolio' else 1.5
        linestyle = '-' if name == 'Total Portfolio' else '--'
        
        plt.plot(equity_curve.index, equity_curve, label=label, linewidth=linewidth, linestyle=linestyle)

    plt.title(title, fontsize=16)
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Equity', fontsize=12)
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.legend()
    plt.yscale('log')
    
    formatter = FuncFormatter(lambda y, _: f'{int(y):,}')
    plt.gca().yaxis.set_major_formatter(formatter)
    
    plt.tight_layout()
    
    img_path = os.path.join(LOGS_DIR, 'WFO_Multi_Strategy_Results_KR.png')
    plt.savefig(img_path)
    logging.info(f"📊 결과 그래프 저장 완료: {img_path}")


def load_universe_data(data_dir, limit=None):
    """데이터 디렉토리에서 필요한 모든 종목 데이터를 로드하고 유니버스 매핑"""
    universe_dfs = {}
    
    # 코스닥/코스피 100 종목 로드
    kospi100_files = glob.glob(os.path.join(data_dir, "kospi100", "*.csv"))
    kosdaq100_files = glob.glob(os.path.join(data_dir, "kosdaq100", "*.csv"))
    
    if not kospi100_files and not kosdaq100_files:
        logging.warning(f"❌ 코스닥/코스피 100 데이터 파일을 찾을 수 없습니다: {os.path.join(data_dir, 'kospi100')}")

    for f in kospi100_files:
        ticker = os.path.basename(f).split('_')[0]
        df = pd.read_csv(f, index_col='date', parse_dates=True)
        df.columns = [col.lower() for col in df.columns]
        universe_dfs[ticker] = df

    for f in kosdaq100_files:
        ticker = os.path.basename(f).split('_')[0]
        df = pd.read_csv(f, index_col='date', parse_dates=True)
        df.columns = [col.lower() for col in df.columns]
        universe_dfs[ticker] = df

    # 추가로 필요한 ETF 및 지수 데이터 로드
    other_assets = ["122630", "252670", "233740", "251340", "132030", "114800", "130680", "KOSPI", "139260", "148070", "305080"]
    for asset in other_assets:
        search_pattern = os.path.join(data_dir, "etf_index", f"{asset}_*.csv")
        found_files = glob.glob(search_pattern)
        
        if found_files:
            file_path = found_files[0]
            ticker = os.path.basename(file_path).split('_')[0]
            df = pd.read_csv(file_path, index_col='date', parse_dates=True)
            df.columns = [col.lower() for col in df.columns]
            universe_dfs[ticker] = df
        else:
            logging.warning(f"❌ {asset} 데이터 파일을 찾을 수 없습니다: 패턴({search_pattern})")

    # 동적으로 유니버스 할당
    ma_momentum_universe = [os.path.basename(f).split('_')[0] for f in kospi100_files + kosdaq100_files]
    
    # stock_list.json에서 최적 파라미터 로드
    stock_list_path = os.path.join(script_dir, '..', 'kis', 'stock_list.json')
    stock_specific_params = {}
    try:
        with open(stock_list_path, 'r', encoding='utf-8') as f:
            stock_data = json.load(f)
            # JSON 파일 최상위의 'stocks' 키에 접근
            stock_details_dict = stock_data.get('stocks', {})
            # .items()로 종목코드와 상세정보를 순회
            for ticker, details in stock_details_dict.items():
                # 'small_ma', 'big_ma' 키를 직접 사용
                ma_short = details.get('small_ma')
                ma_long = details.get('big_ma')
                if ticker and ma_short and ma_long:
                    stock_specific_params[ticker] = {'small_ma': ma_short, 'big_ma': ma_long}
    except FileNotFoundError:
        logging.warning(f"❌ stock_list.json 파일을 찾을 수 없습니다: {stock_list_path}")
    except json.JSONDecodeError:
        logging.warning(f"❌ stock_list.json 파일 파싱 오류: {stock_list_path}")

    return universe_dfs, ma_momentum_universe, stock_specific_params


def main():
    logging.info("🚀 한국 주식 포트폴리오 WFO 시작")
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    # 전체 기간 설정 (원래대로 복원)
    total_start_date = '2018-01-01'
    total_end_date = datetime.now().strftime('%Y-%m-%d')

    # 날짜를 Timestamp 객체로 변환
    total_start_date = pd.to_datetime(total_start_date)
    total_end_date = pd.to_datetime(total_end_date)
    
    # WFO 파라미터 (원래대로 복원)
    in_sample_years = 2
    out_of_sample_months = 3
    step_months = 3

    # 전체 기간 데이터 로드
    all_stock_data, ma_momentum_universe, stock_specific_params = load_universe_data(os.path.join(script_dir, 'data'))
    
    # 5개 전략에 대한 설정 (MA_Momentum 추가, 자금 20%씩 분배)
    STRATEGY_CONFIGS = {
        # 'MA_Momentum': {
        #     'class': MovingAverageMomentumStrategy,
        #     'universe': ma_momentum_universe,
        #     'params': {
        #         'max_buy_stocks': 30,
        #         'stock_specific_params': stock_specific_params
        #     },
        #     'capital_allocation': 0.20
        # },
        'Turtle': {
            'class': TurtleStrategy,
            'universe': ma_momentum_universe,
            'params': {},
            'capital_allocation': 0.20
        },
        # 'Kospidaq_Hybrid': {
        #     'class': KospidaqHybridStrategy,
        #     'universe': ['122630', '252670', '233740', '251340'],
        #     'params': {},
        #     'capital_allocation': 0.20
        # },
        # 'Safe_Asset': {
        #     'class': SafeAssetRebalancingStrategy,
        #     'universe': ['139260', '148070', '305080', '132030'],
        #     'params': {},
        #     'capital_allocation': 0.20
        # },
        # 'Dip_Buying': {
        #     'class': KospiDipBuyingStrategy,
        #     'universe': ['122630', 'KOSPI'],
        #     'params': {},
        #     'capital_allocation': 0.20
        # }
    }

    # WFO 루프
    current_date = total_start_date
    all_oos_equity_curves = []
    all_oos_strategy_curves = {}
    
    # 첫 OOS 기간의 초기 자본은 설정된 initial_capital로 시작합니다.
    last_equity = 100_000_000 # 초기 자본 설정
    
    # 각 전략의 초기 자본을 할당 비율에 따라 계산합니다.
    total_allocation = sum(config['capital_allocation'] for config in STRATEGY_CONFIGS.values() if config['capital_allocation'] > 0)
    last_strategy_equity = {
        name: last_equity * (config['capital_allocation'] / total_allocation)
        for name, config in STRATEGY_CONFIGS.items() if config['capital_allocation'] > 0
    }

    while current_date + pd.DateOffset(years=in_sample_years) + pd.DateOffset(months=out_of_sample_months) <= total_end_date:

        train_start_date = current_date
        train_end_date = train_start_date + pd.DateOffset(years=in_sample_years)
        oos_start_date = train_end_date
        oos_end_date = oos_start_date + pd.DateOffset(months=out_of_sample_months)

        if oos_end_date > total_end_date:
            oos_end_date = total_end_date

        logging.info("-" * 80)
        logging.info(f" WFO ?ъ씠?? {train_start_date.date()} ~ {oos_end_date.date()} ".center(80, "#"))
        logging.info(f" In-Sample: {train_start_date.date()} ~ {train_end_date.date()} | Out-of-Sample: {oos_start_date.date()} ~ {oos_end_date.date()} ".center(80, " "))
        logging.info("-" * 80)

        train_data = {ticker: data.loc[train_start_date:train_end_date] for ticker, data in all_stock_data.items()}

        best_params_turtle = optimize_turtle_strategy(train_data, STRATEGY_CONFIGS['Turtle'])
        # optimal_params_kospidaq = find_optimal_params_for_kospidaq(train_data) # 鍮꾪솢?깊솕???꾨왂

        oos_config = copy.deepcopy(STRATEGY_CONFIGS)
        if best_params_turtle:
            oos_config['Turtle']['params'] = best_params_turtle
        # oos_config['Kospidaq_Hybrid']['params'] = optimal_params_kospidaq # 鍮꾪솢?깊솕???꾨왂

        logging.info("-" * 80)
        logging.info(f" OOS 諛깊뀒?ㅽ듃: {oos_start_date.date()} ~ {oos_end_date.date()} ".center(80, "="))

        oos_data = {ticker: data.loc[oos_start_date:oos_end_date] for ticker, data in all_stock_data.items()}

        # --------------------------------------------------------------------------------
        # 3. Out-of-Sample(OOS) 기간으로 백테스트 실행
        # --------------------------------------------------------------------------------
        logging.info(f"\n{'='*21} OOS 백테스트: {oos_start_date.date()} ~ {oos_end_date.date()} {'='*22}")
        
        oos_equity_df, oos_strategy_equity_curves = run_multi_strategy_backtest(
            universe_dfs=oos_data,
            strategy_configs=oos_config,
            initial_capital=last_equity, # 이전 기간의 최종 자산을 초기 자본으로 사용
            strategy_initial_capitals=last_strategy_equity # 이전 기간의 전략별 최종 자산을 초기 자본으로 사용
        )

        if not oos_equity_df.empty:
            # 전체 자산 곡선 리스트에 이번 OOS 기간의 결과를 추가합니다.
            # 첫번째 oos_equity_df는 초기자본 행을 포함하고, 그 이후부터는 중복을 피하기 위해 첫 행을 제외합니다.
            if not all_oos_equity_curves:
                all_oos_equity_curves.append(oos_equity_df)
            else:
                all_oos_equity_curves.append(oos_equity_df.iloc[1:])
            
            # 다음 루프를 위해 최종 자산을 업데이트합니다.
            last_equity = oos_equity_df['total_equity'].iloc[-1]

            # 전략별 자산 곡선도 동일한 방식으로 처리합니다.
            for name, curve in oos_strategy_equity_curves.items():
                if name not in all_oos_strategy_curves:
                    all_oos_strategy_curves[name] = []
                
                if not all_oos_strategy_curves[name]:
                     all_oos_strategy_curves[name].append(curve)
                else:
                    all_oos_strategy_curves[name].append(curve.iloc[1:])
                
                # 다음 루프를 위해 전략별 최종 자산을 업데이트합니다.
                if not curve.empty:
                    last_strategy_equity[name] = curve.iloc[-1]

        current_date += pd.DateOffset(months=step_months)

    if not all_oos_equity_curves:
        logging.warning("WFO를 실행할 수 있는 충분한 데이터 기간이 없습니다.")
        return

    # 각 OOS 기간의 자산 곡선을 하나로 합칩니다.
    compounded_equity = pd.concat(all_oos_equity_curves)

    # 개별 전략 자산 곡선도 하나로 합칩니다.
    final_strategy_results = {}
    for name, curves in all_oos_strategy_curves.items():
        if curves:
            final_strategy_results[name] = pd.concat(curves)

    # --- 최종 결과 출력 ---
    logging.info("\n" + "="*50)
    logging.info("✅ 최종 WFO 백테스트 완료!")

    # 최종 성과 계산
    if compounded_equity.empty:
        total_return = 0.0
        mdd = 0.0
    else:
        equity_curve = compounded_equity.iloc[:, 0] if isinstance(compounded_equity, pd.DataFrame) else compounded_equity
        if equity_curve.empty or not np.isfinite(equity_curve.iloc[0]) or equity_curve.iloc[0] == 0:
            total_return = 0.0
            mdd = 0.0
        else:
            start_val = equity_curve.iloc[0]
            end_val = equity_curve.iloc[-1]
            total_return = (end_val / start_val - 1) * 100
            rolling_max = equity_curve.cummax()
            drawdown = equity_curve / rolling_max - 1
            mdd = drawdown.min() * 100

    logging.info(f"[종합 포트폴리오] 총 수익률: {total_return:.2f}%, MDD: {mdd:.2f}%")
    
    # 그래프를 위한 데이터 준비
    results_data = {'Total Portfolio': compounded_equity}
    
    for name, curve in final_strategy_results.items():
        results_data[name] = curve # 그래프용 데이터 추가
        if curve.empty or curve.iloc[0] == 0:
            ret, mdd_val = 0.0, 0.0
        else:
            ret = (curve.iloc[-1] / curve.iloc[0] - 1) * 100
            rolling_max = curve.cummax()
            drawdown = curve / rolling_max - 1
            mdd_val = drawdown.min() * 100
        
        if pd.isna(ret): ret = 0.0
        if pd.isna(mdd_val): mdd_val = 0.0
        logging.info(f"  [{name}] 총 수익률: {ret:.2f}%, MDD: {mdd_val:.2f}%")

    # 최종 그래프 시각화
    plot_wfo_results(results_data, title='Walk-Forward Optimization Results (KR Stocks)')


if __name__ == '__main__':
    # 멀티프로세싱 시작 방식 설정 (Windows 호환)
    multiprocessing.set_start_method('spawn', force=True)
    main()
