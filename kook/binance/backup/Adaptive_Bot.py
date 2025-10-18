'''
########################################################################################################################
#   Adaptive Trading Bot for Binance Futures (By kook)
#
#   === 개요 ===
#   이 봇은 정적(static)인 단일 전략에 의존하는 대신, 주기적으로 시장 상황을 학습하여
#   가장 성공적인 거래 전략을 스스로 선택하고 적용하는 '적응형(Adaptive)' 트레이딩 봇입니다.
#   Walk-Forward Optimization(WFO) 개념을 라이브 트레이딩에 접목하여, 변화하는 시장에 능동적으로 대응하는 것을 목표로 합니다.
#
#   === 핵심 작동 원리 ===
#   1.  **주기적인 최적화 (Optimization)**:
#       - `OPTIMIZATION_PERIOD_DAYS`(기본 7일)마다 한 번씩, `TRAINING_DATA_DAYS`(기본 30일) 분량의 과거 1분봉 데이터를 수집합니다.
#       - 수집된 데이터로 사전에 정의된 여러 클래식 전략들을 모두 백테스트합니다.
#
#   2.  **최고 성과 전략 선택 (Strategy Selection)**:
#       - 백테스트 결과(수익률 기준)가 가장 좋았던 '최고의 전략'과 해당 전략의 '최적 파라미터'를 선정합니다.
#       - 선택 가능한 전략 후보군은 다음과 같습니다:
#         - `RsiMeanReversion`: RSI 지표를 활용한 과매도/과매수 기반의 역추세 전략
#         - `StochasticStrategy`: 스토캐스틱 오실레이터를 이용한 역추세 전략
#         - `BollingerBandADXStrategy`: ADX로 추세 강도를 필터링하여 볼린저 밴드 이탈을 노리는 전략
#         - `MacdADXStrategy`: ADX로 추세 강도를 필터링하여 MACD 교차를 활용하는 추세추종 전략
#
#   3.  **라이브 거래 적용 (Live Trading)**:
#       - 선정된 '최고의 전략'을 다음 최적화 주기가 돌아올 때까지 실시간 거래에 사용합니다.
#       - 모든 거래는 시장 변동성에 따라 자동으로 손절 라인을 조절하는 'ATR 기반 동적 손절매'가 적용되어 리스크를 관리합니다.
#
#   4.  **상태 저장 및 관리**:
#       - 현재 활성화된 전략, 포지션 정보 등 모든 상태는 `Adaptive_Bot.json` 파일에 저장되어, 봇이 재시작되어도 연속성을 가집니다.
#
#   === 기대 효과 ===
#   - 상승장, 하락장, 횡보장 등 각기 다른 시장 상황에 더 유리한 전략을 자동으로 채택하여 장기적인 수익 곡선의 안정성을 높입니다.
#   - 과거 데이터에 과적합(overfitting)될 위험이 있는 단일 ML 모델의 한계를 극복합니다.
#
#   === 의존성 ===
#   - 이 봇은 `strategy_platform.py`에 정의된 백테스팅 및 전략 클래스에 의존합니다.
#     경로가 올바르게 설정되어 있는지 확인해야 합니다.
#
########################################################################################################################
'''

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
import ccxt
import time
import datetime as dt
import logging
import traceback
import myBinance
import ende_key
import my_key
import telegram_sender as line_alert
import numpy as np
import json
import itertools
import pandas as pd

# 백테스팅 플랫폼 및 전략 임포트
# (경로가 올바른지 확인 필요)
try:
    from strategy_platform import run_backtest, RsiMeanReversion, BollingerBandADXStrategy, MacdADXStrategy, StochasticStrategy
except ImportError:
    print("경고: strategy_platform을 찾을 수 없습니다. 상위 폴더를 경로에 추가합니다.")
    # 이 경로 추가는 VSCode 등의 환경에서 직접 실행 시 필요할 수 있음
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from strategy_platform import run_backtest, RsiMeanReversion, BollingerBandADXStrategy, MacdADXStrategy, StochasticStrategy

# ========================= 전역 설정 변수 =========================
DEFAULT_LEVERAGE = 10
INVESTMENT_RATIO = 0.9  # 투자 비율을 90%로 상향
ASSET_SPLIT = 1
ACTIVE_COINS = ['BTC/USDT']
COIN_CHARGE = 0.001 # 수수료 설정

# WFO 설정
OPTIMIZATION_PERIOD_DAYS = 7  # 7일마다 최적화 실행
TRAINING_DATA_DAYS = 30     # 최근 30일 데이터로 학습

# ========================= 로깅 시스템 설정 =========================
def setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    today = dt.datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"Adaptive_Bot_{today}.log")
    trade_log_file = os.path.join(log_dir, "Adaptive_Bot_list.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    trade_logger = logging.getLogger('trade_logger')
    trade_logger.setLevel(logging.INFO)
    trade_logger.handlers = []
    trade_logger.propagate = False
    trade_logger.addHandler(logging.FileHandler(trade_log_file, encoding='utf-8'))
    
    logging.getLogger('ccxt').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return logging.getLogger(__name__), trade_logger

logger, trade_logger = setup_logging()

# ========================= 로깅 유틸리티 =========================
def log_trade_action(action_type, coin_ticker, position_side, price, quantity, reason="", profit=0, profit_rate=0):
    try:
        trade_record = {
            "timestamp": dt.datetime.now().isoformat(), "action": action_type, "coin": coin_ticker,
            "position": position_side, "price": round(price, 2), "quantity": round(quantity, 3),
            "reason": reason, "profit_usdt": round(profit, 2) if profit != 0 else 0,
            "profit_rate": round(profit_rate, 2) if profit_rate != 0 else 0
        }
        trade_logger.info(json.dumps(trade_record, ensure_ascii=False))
    except Exception as e:
        logger.error(f"거래 기록 로깅 실패: {e}")

def log_error(error_msg, error_detail=None):
    logger.error(f"오류: {error_msg}")
    if error_detail:
        logger.error(f"상세: {error_detail}")

# ========================= WFO 관련 함수 =========================
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
        log_error(f"최적화용 데이터 다운로드 실패: {e}", traceback.format_exc())
        return None, None

    param_grid = generate_param_grid()
    in_sample_results = []
    
    for strategy_class, params in param_grid:
        try:
            result = run_backtest(
                df_original=train_df.copy(),
                strategy_class=strategy_class,
                strategy_params=params,
                trade_type='long_and_short', initial_capital=10000, fee=COIN_CHARGE, leverage=DEFAULT_LEVERAGE,
                atr_stop_loss_multiplier=params.get('atr_multiplier', 2.0)
            )
            in_sample_results.append(result)
        except Exception as e:
            logger.warning(f"{strategy_class.__name__} 백테스트 중 오류: {e}")

    if not in_sample_results:
        logger.error("모든 전략 백테스트 실패. 최적화 중단.")
        return None, None
        
    best_result = max(in_sample_results, key=lambda x: x['total_return_pct'])
    best_strategy_name = best_result['strategy']
    best_params = best_result['params']
    
    logger.info(f"🏆 최적 전략 탐색 완료: {best_strategy_name}")
    logger.info(f"   - 최적 파라미터: {best_params}")
    logger.info(f"   - 기대 수익률({TRAINING_DATA_DAYS}일): {best_result['total_return_pct']:.2f}%")
    
    return best_strategy_name, best_params

# ========================= 메인 실행 코드 =========================
if __name__ == "__main__":
    simpleEnDecrypt = myBinance.SimpleEnDecrypt(ende_key.ende_key)
    Binance_AccessKey = simpleEnDecrypt.decrypt(my_key.binance_access)
    Binance_ScretKey = simpleEnDecrypt.decrypt(my_key.binance_secret)
    
    binanceX = ccxt.binance(config={
        'apiKey': Binance_AccessKey, 
        'secret': Binance_ScretKey,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })

    info_file_path = os.path.join(os.path.dirname(__file__), "Adaptive_Bot.json")
    try:
        with open(info_file_path, 'r', encoding='utf-8') as f:
            dic = json.load(f)
    except FileNotFoundError:
        logger.info("설정 파일이 없어 새로 생성합니다.")
        balance = binanceX.fetch_balance(params={"type": "future"})['USDT']['total']
        dic = {
            "start_money": balance, "my_money": balance,
            "coins": {
                "BTC/USDT": {
                    "long": {"position": 0, "entry_price": 0, "position_size": 0},
                    "short": {"position": 0, "entry_price": 0, "position_size": 0}
                }
            },
            "strategy_info": {"name": None, "params": {}, "last_update": None}
        }

    # --- 전략 최적화 로직 ---
    strategy_info = dic.get('strategy_info', {})
    last_update_str = strategy_info.get('last_update')
    needs_optimization = True
    if last_update_str:
        last_update_time = dt.datetime.fromisoformat(last_update_str)
        if dt.datetime.now() - last_update_time < dt.timedelta(days=OPTIMIZATION_PERIOD_DAYS):
            needs_optimization = False
            logger.info("기존 최적화 전략을 계속 사용합니다.")

    if needs_optimization:
        logger.info("최적화 주기 도래. 새로운 전략 탐색을 시작합니다.")
        line_alert.SendMessage("🤖 봇 최적화 시작...")
        best_strategy_name, best_params = find_best_strategy(binanceX, ACTIVE_COINS[0])
        if best_strategy_name and best_params:
            strategy_info = {
                'name': best_strategy_name,
                'params': best_params,
                'last_update': dt.datetime.now().isoformat()
            }
            dic['strategy_info'] = strategy_info
            line_alert.SendMessage(f"📈 새로운 최적 전략: {best_strategy_name}")
            with open(info_file_path, 'w', encoding='utf-8') as f:
                json.dump(dic, f, indent=4)
    
    active_strategy_name = strategy_info.get('name')
    active_params = strategy_info.get('params')
    
    if not active_strategy_name:
        logger.error("활성화된 전략이 없습니다. 프로그램을 종료합니다.")
        sys.exit(1)

    for Target_Coin_Ticker in ACTIVE_COINS:
        logger.info(f"=== {Target_Coin_Ticker} | 활성 전략: {active_strategy_name} ===")
        
        Target_Coin_Symbol = Target_Coin_Ticker.replace("/", "")
        binanceX.fapiPrivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': DEFAULT_LEVERAGE})

        df = myBinance.GetOhlcv(binanceX, Target_Coin_Ticker, '1m', 200)
        coin_price = df['close'].iloc[-1]
        
        long_data = dic['coins'][Target_Coin_Ticker]['long']
        short_data = dic['coins'][Target_Coin_Ticker]['short']
        long_position = long_data['position']
        short_position = short_data['position']

        try:
            strategy_class = eval(active_strategy_name)
            strategy = strategy_class(df, active_params)
            signals = strategy.generate_signals()
            action = signals.iloc[-1]
            reason = f"{active_strategy_name}({active_params.get('atr_multiplier', 'N/A')}x ATR)"
            logger.info(f"신호: {action} | 사유: {reason}")
        except Exception as e:
            log_error(f"신호 생성 오류: {e}", traceback.format_exc())
            action = 'hold'

        position_size = round((dic['my_money'] * INVESTMENT_RATIO * DEFAULT_LEVERAGE) / coin_price, 3)
        minimum_amount = myBinance.GetMinimumAmount(binanceX, Target_Coin_Ticker)
        if position_size < minimum_amount:
            position_size = minimum_amount
            logger.info(f"최소 주문 수량 적용: {position_size}")

        # --- 주문 실행 로직 ---
        if action == 'buy':
            if short_position == 1:
                logger.info("포지션 전환: 숏 포지션 청산")
                try:
                    # 현재 보유 수량으로 전량 청산
                    close_qty = short_data.get('position_size', 0)
                    if close_qty > 0:
                        data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', close_qty, None, {'positionSide': 'SHORT'})
                        exit_price = float(data.get('average', coin_price))
                        
                        # 수익 계산
                        profit = (short_data['entry_price'] - exit_price) * close_qty
                        profit_rate = (short_data['entry_price'] - exit_price) / short_data['entry_price'] * 100.0
                        
                        log_trade_action('SELL_SHORT', Target_Coin_Ticker, 'short', exit_price, close_qty, "포지션 전환", profit, profit_rate)
                        
                        # 포지션 정보 초기화
                        short_data['position'] = 0
                        short_data['entry_price'] = 0
                        short_data['position_size'] = 0
                except Exception as e:
                    log_error(f"숏 포지션 청산 실패: {e}", traceback.format_exc())
            if long_position == 0:
                logger.info("신규 진입: 롱 포지션 주문")
                try:
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', position_size, None, {'positionSide': 'LONG'})
                    entry_price = float(data.get('average', coin_price))
                    
                    # 포지션 정보 업데이트
                    long_data['position'] = 1
                    long_data['entry_price'] = entry_price
                    long_data['position_size'] = position_size
                    
                    log_trade_action('BUY_LONG', Target_Coin_Ticker, 'long', entry_price, position_size, reason)
                    line_alert.SendMessage(f"📈 롱 포지션 진입\n- 코인: {Target_Coin_Ticker}\n- 가격: {entry_price:.2f}\n- 수량: {position_size}")

                except Exception as e:
                    log_error(f"롱 포지션 진입 실패: {e}", traceback.format_exc())
        
        elif action == 'sell':
            if long_position == 1:
                logger.info("포지션 전환: 롱 포지션 청산")
                try:
                    close_qty = long_data.get('position_size', 0)
                    if close_qty > 0:
                        data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', close_qty, None, {'positionSide': 'LONG'})
                        exit_price = float(data.get('average', coin_price))
                        
                        # 수익 계산
                        profit = (exit_price - long_data['entry_price']) * close_qty
                        profit_rate = (exit_price - long_data['entry_price']) / long_data['entry_price'] * 100.0
                        
                        log_trade_action('SELL_LONG', Target_Coin_Ticker, 'long', exit_price, close_qty, "포지션 전환", profit, profit_rate)
                        
                        # 포지션 정보 초기화
                        long_data['position'] = 0
                        long_data['entry_price'] = 0
                        long_data['position_size'] = 0
                except Exception as e:
                    log_error(f"롱 포지션 청산 실패: {e}", traceback.format_exc())

            if short_position == 0:
                logger.info("신규 진입: 숏 포지션 주문")
                try:
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', position_size, None, {'positionSide': 'SHORT'})
                    entry_price = float(data.get('average', coin_price))

                    # 포지션 정보 업데이트
                    short_data['position'] = 1
                    short_data['entry_price'] = entry_price
                    short_data['position_size'] = position_size
                    
                    log_trade_action('BUY_SHORT', Target_Coin_Ticker, 'short', entry_price, position_size, reason)
                    line_alert.SendMessage(f"📉 숏 포지션 진입\n- 코인: {Target_Coin_Ticker}\n- 가격: {entry_price:.2f}\n- 수량: {position_size}")

                except Exception as e:
                    log_error(f"숏 포지션 진입 실패: {e}", traceback.format_exc())
        
        # 포지션 정보 파일에 저장
        with open(info_file_path, 'w', encoding='utf-8') as f:
            json.dump(dic, f, indent=4)

    logger.info("=== Adaptive Trading Bot 종료 ===")
