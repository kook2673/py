# -*- coding: utf-8 -*-
"""
Adaptive Trading Bot - Optimizer

이 스크립트는 주기적으로 (예: 7일에 한 번) 실행되어,
과거 데이터를 기반으로 가장 성과가 좋은 거래 전략과 파라미터를 찾아
'best_strategy.json' 파일로 저장하는 역할을 합니다.
"""
import os
import sys
import json
import itertools
import pandas as pd
import logging
import datetime as dt
import traceback
import ccxt

# --- 의존성 경로 설정 ---
# 이 스크립트가 다른 프로젝트 폴더에서도 실행될 수 있도록 경로를 추가합니다.
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import myBinance
import ende_key
import my_key
import telegram_sender as line_alert

try:
    from strategy_platform import run_backtest, RsiMeanReversion, BollingerBandADXStrategy, MacdADXStrategy, StochasticStrategy
except ImportError:
    print("경고: strategy_platform을 찾을 수 없습니다. 상위 폴더를 경로에 추가합니다.")
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from strategy_platform import run_backtest, RsiMeanReversion, BollingerBandADXStrategy, MacdADXStrategy, StochasticStrategy

# --- 전역 설정 ---
TRAINING_DATA_DAYS = 30     # 최근 30일 데이터로 학습
COIN_CHARGE = 0.001         # 수수료
DEFAULT_LEVERAGE = 10
ACTIVE_COINS = ['BTC/USDT']
BEST_STRATEGY_FILE = os.path.join(os.path.dirname(__file__), "best_strategy.json")

# --- 로깅 설정 ---
def setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"optimizer_{dt.datetime.now().strftime('%Y%m%d')}.log")
    
    logger = logging.getLogger('optimizer')
    logger.setLevel(logging.INFO)
    
    # 핸들러 중복 추가 방지
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        
        # 파일 핸들러
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        # 콘솔 핸들러
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)
        
    return logger

logger = setup_logging()

# --- 최적화 함수 (기존 adaptive_bot.py에서 가져옴) ---
def generate_param_grid():
    """최적화할 파라미터 그리드 생성 (다중 전략)"""
    all_grids = []
    rsi_params = {'rsi_window': [14, 21], 'oversold_threshold': [25, 30], 'overbought_threshold': [70, 75], 'atr_multiplier': [1.5, 2.0]}
    rsi_grid = [(RsiMeanReversion, dict(zip(rsi_params.keys(), p))) for p in itertools.product(*rsi_params.values())]
    all_grids.extend(rsi_grid)

    bb_adx_params = {'window': [20], 'std_dev': [2], 'adx_threshold': [20, 25], 'atr_multiplier': [2.0, 3.0]}
    bb_adx_grid = [(BollingerBandADXStrategy, dict(zip(bb_adx_params.keys(), p))) for p in itertools.product(*bb_adx_params.values())]
    all_grids.extend(bb_adx_grid)

    macd_adx_params = {'fastperiod': [12], 'slowperiod': [26], 'signalperiod': [9], 'adx_threshold': [20, 25], 'atr_multiplier': [2.0, 3.0]}
    macd_adx_grid = [(MacdADXStrategy, dict(zip(macd_adx_params.keys(), p))) for p in itertools.product(*macd_adx_params.values())]
    all_grids.extend(macd_adx_grid)

    stoch_params = {'fastk_period': [14], 'slowk_period': [3], 'slowd_period': [3], 'oversold': [20, 30], 'overbought': [70, 80], 'atr_multiplier': [1.5, 2.0]}
    stoch_grid = [(StochasticStrategy, dict(zip(stoch_params.keys(), p))) for p in itertools.product(*stoch_params.values())]
    all_grids.extend(stoch_grid)
    
    return all_grids

def find_best_strategy(binanceX, coin_ticker):
    """지난 N일간의 데이터를 바탕으로 최고 성과 전략을 찾음"""
    logger.info(f"=== {coin_ticker} 최적 전략 탐색 시작 (지난 {TRAINING_DATA_DAYS}일 데이터) ===")
    
    limit = TRAINING_DATA_DAYS * 24 * 60
    try:
        ohlcv = binanceX.fetch_ohlcv(coin_ticker, '1m', limit=limit)
        train_df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        train_df['timestamp'] = pd.to_datetime(train_df['timestamp'], unit='ms')
        train_df.set_index('timestamp', inplace=True)
        logger.info(f"데이터 다운로드 성공: {len(train_df)}개 캔들")
    except Exception as e:
        logger.error(f"최적화용 데이터 다운로드 실패: {e}\n{traceback.format_exc()}")
        return None
    
    param_grid = generate_param_grid()
    in_sample_results = []
    
    for i, (strategy_class, params) in enumerate(param_grid, 1):
        try:
            result = run_backtest(
                df_original=train_df.copy(),
                strategy_class=strategy_class,
                strategy_params=params,
                trade_type='long_and_short', initial_capital=10000, fee=COIN_CHARGE, leverage=DEFAULT_LEVERAGE,
                atr_stop_loss_multiplier=params.get('atr_multiplier', 2.0)
            )
            in_sample_results.append(result)
            logger.info(f"  ({i}/{len(param_grid)}) {strategy_class.__name__} | Return={result['total_return_pct']:.2f}%")
        except Exception as e:
            logger.warning(f"  ({i}/{len(param_grid)}) {strategy_class.__name__} 백테스트 중 오류: {e}")

    if not in_sample_results:
        logger.error("모든 전략 백테스트 실패. 최적화 중단.")
        return None
        
    best_result = max(in_sample_results, key=lambda x: x['total_return_pct'])
    
    logger.info("-" * 50)
    logger.info(f"🏆 최적 전략 탐색 완료: {best_result['strategy']}")
    logger.info(f"   - 최적 파라미터: {best_result['params']}")
    logger.info(f"   - 기대 수익률({TRAINING_DATA_DAYS}일): {best_result['total_return_pct']:.2f}%")
    logger.info("-" * 50)
    
    return {
        'name': best_result['strategy'],
        'params': best_result['params'],
        'expected_return_pct': best_result['total_return_pct'],
        'last_update': dt.datetime.now().isoformat()
    }

# --- 메인 실행 로직 ---
def main():
    logger.info("🚀 옵티마이저 스크립트 시작")
    line_alert.SendMessage("🤖[Optimizer] 봇 최적화 시작...")

    try:
        # 바이낸스 연결
        simpleEnDecrypt = myBinance.SimpleEnDecrypt(ende_key.ende_key)
        Binance_AccessKey = simpleEnDecrypt.decrypt(my_key.binance_access)
        Binance_ScretKey = simpleEnDecrypt.decrypt(my_key.binance_secret)
        
        binanceX = ccxt.binance(config={
            'apiKey': Binance_AccessKey, 
            'secret': Binance_ScretKey,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })

        # 최적 전략 탐색
        best_strategy_info = find_best_strategy(binanceX, ACTIVE_COINS[0])
        
        # 결과 파일 저장
        if best_strategy_info:
            with open(BEST_STRATEGY_FILE, 'w', encoding='utf-8') as f:
                json.dump(best_strategy_info, f, indent=4, ensure_ascii=False)
            logger.info(f"✅ 최적화 결과를 '{BEST_STRATEGY_FILE}' 파일에 저장했습니다.")
            
            msg = (f"📈[Optimizer] 새로운 최적 전략 탐색 완료\n"
                   f" - 전략: {best_strategy_info['name']}\n"
                   f" - 파라미터: {best_strategy_info['params']}\n"
                   f" - 기대수익률: {best_strategy_info['expected_return_pct']:.2f}%")
            line_alert.SendMessage(msg)

        else:
            logger.error("❌ 최적 전략을 찾지 못해 파일을 업데이트하지 않았습니다.")
            line_alert.SendMessage("🚨[Optimizer] 최적 전략 탐색에 실패했습니다.")

    except Exception as e:
        logger.critical(f"옵티마이저 실행 중 심각한 오류 발생: {e}\n{traceback.format_exc()}")
        line_alert.SendMessage(f"🚨[Optimizer] 스크립트 실행 중 심각한 오류 발생: {e}")

    logger.info("👋 옵티마이저 스크립트 종료")

if __name__ == "__main__":
    main()
