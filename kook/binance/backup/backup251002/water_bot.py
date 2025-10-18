'''
########################################################################################################################
#   Live Water Bot for Binance Futures (By kook) - 라이브 물타기 트레이딩 봇
#
#   === 개요 ===
#   이 봇은 볼린저밴드(BB) + RSI 전략을 기반으로 한 물타기 시스템으로,
#   실시간으로 롱/숏 양방향 거래를 수행합니다.
#
#   === 핵심 규칙 ===
#   1. **자본 분산 (32분할)**
#      - 총 자본을 32분할로 나누어 관리
#      - 롱 포지션: 최대 16분할 (1+1+2+4+8)
#      - 숏 포지션: 최대 16분할 (1+1+2+4+8)
#      - 각 분할당 자본: division_capital = capital / 32
#
#   2. **진입 조건 (BB + RSI 전략)**
#      - 롱 진입: 하단 볼린저밴드 터치 + RSI 과매도 (close <= bb_lower AND rsi < 30)
#      - 숏 진입: 상단 볼린저밴드 터치 + RSI 과매수 (close >= bb_upper AND rsi > 70)
#      - 각각 1분할로 진입
#
#   3. **물타기 로직 (1,1,2,4,8 분할)**
#      - 롱 물타기: 가격 5% 하락 시 추가 매수
#      - 숏 물타기: 가격 5% 상승 시 추가 매수
#      - 물타기 분할: [1, 1, 2, 4, 8] 순서로 진행
#      - 최대 5단계까지 물타기 가능
#
#   4. **수익 실현 규칙**
#      A. 물타기 안했을 때 (진입 1만):
#         - 0.3% 수익 시 → 50% 매도
#         - 나머지 50% → 트레일링 스탑
#
#      B. 물타기 했을 때 (진입 + 물타기):
#         - 0.1% 수익 시 → 가진 것의 50% 매도
#         - 0.3% 수익 시 → 가진 것의 50% 매도 (나머지 50%의 50%)
#         - 나머지 25% → 트레일링 스탑
#
#   5. **손절매 조건**
#      - 롱: 5단계 물타기 후 25% 하락 시 손절
#      - 숏: 5단계 물타기 후 25% 상승 시 손절
#
#   === 실행 주기 ===
#   - crontab: "* * * * *" (1분마다 실행)
#   - 실시간 데이터 수집: 3분봉 데이터
#
#   === 설정 파일 (water_bot.json) ===
#   - initial_capital: 초기 자본
#   - trading_fee: 거래 수수료 (0.0005 = 0.05%)
#   - leverage: 레버리지 배수 (기본 1배)
#   - enable_long_short: 롱/숏 양방향 거래 활성화
#   - slides: 물타기 분할 설정 [1, 1, 2, 4, 8]
#   - profit_targets: 수익 실현 목표 설정
#   - stop_loss: 손절매 임계값 설정
#   - technical_indicators: BB + RSI 파라미터
#
#   === 의존성 ===
#   - myBinance.py: 바이낸스 API 연동
#   - telegram_sender.py: 텔레그램 알림
#   - water_bot.json: 설정 파일
#
########################################################################################################################
'''

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import ccxt
import pandas as pd
import numpy as np
import json
import datetime as dt
import logging
import traceback
import time
import gc
import psutil
import warnings
import myBinance
import ende_key
import my_key
import telegram_sender as line_alert
import subprocess
from pathlib import Path
import talib
from typing import Dict, List, Tuple, Optional, Any

# ========================= 전역 설정 변수 =========================
DEFAULT_LEVERAGE = 5  # 물타기용 레버리지 (1배)
INVESTMENT_RATIO = 0.5  # 투자 비율 (자산의 50%)
COIN_CHARGE = 0.0005  # 수수료 (0.05%)
ACTIVE_COINS = ['BTC/USDT']

# 물타기용 32분할 자본 관리 (롱/숏 양방향)
DIVISION_CAPITAL_RATIO = 1/24#32  # 각 분할당 자본 비율 (3.125%)
MARTINGALE_MULTIPLIERS = [1, 1, 2, 4, 8]  # 물타기 분할 배수
MAX_MARTINGALE_LEVEL = 5  # 최대 물타기 단계

# 물타기용 파라미터
WATER_BOT_PARAMS = {
    'rsi_period': 14,
    'rsi_oversold': 30,
    'rsi_overbought': 70,
    'bb_period': 20,
    'bb_std': 2.0,
    'ma_period': 20,
    'ema_short': 5,
    'ema_long': 20,
    'martingale_trigger_pct': 0.05,  # 5% 하락/상승 시 물타기
    'profit_target_1': 0.002,  # 0.2% 수익 시 첫 번째 매도 (물타기 했을 때)
    'profit_target_2': 0.004,  # 0.4% 수익 시 두 번째 매도
    'trailing_stop_activation': 0.04,  # 4% 이상 수익 시 트레일링 스탑 활성화
    'trailing_stop_multiplier': 0.5,  # 추가 수익의 50%
    'trailing_stop_min_ratio': 0.10,  # 최소 스탑 비율 10%
    'trailing_stop_reduction_rate': 0.05,  # 1% 증가당 5% 감소
    'stop_loss_4': 0.85,  # 4단계 15% 하락 시 손절
    'stop_loss_5': 0.75   # 5단계 25% 하락 시 손절
}

# ========================= 로깅 설정 =========================
def setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    today = dt.datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"water_bot_{today}.log")
    trade_log_file = os.path.join(log_dir, "water_bot_trades.log")
    
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

# ========================= 기술적 지표 계산 =========================
def calculate_technical_indicators(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """기술적 지표 계산 (BB + RSI 전략용)"""
    data = df.copy()
    
    # RSI 계산
    rsi_period = params.get('rsi_period', 14)
    data['rsi'] = talib.RSI(data['close'], timeperiod=rsi_period)
    
    # 볼린저밴드 계산
    bb_period = params.get('bb_period', 20)
    bb_std = params.get('bb_std', 2.0)
    data['bb_upper'], data['bb_middle'], data['bb_lower'] = talib.BBANDS(
        data['close'], timeperiod=bb_period, nbdevup=bb_std, nbdevdn=bb_std, matype=0
    )
    
    # 이동평균
    ma_period = params.get('ma_period', 20)
    data['ma_20'] = talib.SMA(data['close'], timeperiod=ma_period)
    
    # 지수이동평균
    ema_short = params.get('ema_short', 5)
    ema_long = params.get('ema_long', 20)
    data['ema_5'] = talib.EMA(data['close'], timeperiod=ema_short)
    data['ema_20'] = talib.EMA(data['close'], timeperiod=ema_long)
    
    # ATR (손절가 설정용)
    data['atr'] = talib.ATR(data['high'], data['low'], data['close'], timeperiod=14)
    
    return data

def generate_water_bot_signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """물타기 봇 신호 생성 (BB + RSI 전략)"""
    data = df.copy()
    
    # 진입 신호 생성
    data['long_entry'] = 0
    data['short_entry'] = 0
    
    # 롱 진입 조건: 하단 볼린저밴드 터치 + RSI 과매도
    long_condition = (data['close'] <= data['bb_lower']) & (data['rsi'] < params.get('rsi_oversold', 30))
    data.loc[long_condition, 'long_entry'] = 1
    
    # 숏 진입 조건: 상단 볼린저밴드 터치 + RSI 과매수
    short_condition = (data['close'] >= data['bb_upper']) & (data['rsi'] > params.get('rsi_overbought', 70))
    data.loc[short_condition, 'short_entry'] = 1
    
    return data

# ========================= 물타기 포지션 관리 =========================
def calculate_division_capital(capital: float) -> float:
    """32분할 자본 계산"""
    return capital * DIVISION_CAPITAL_RATIO

def calculate_base_quantity(division_capital: float, coin_price: float, leverage: int = 1) -> float:
    """32등분의 1개 분할에 대한 기본 구매 수량 계산 (소수점 3자리)"""
    # 레버리지 적용된 구매 금액
    leveraged_amount = division_capital * leverage
    # 기본 구매 수량 (소수점 3자리까지)
    base_quantity = round(leveraged_amount / coin_price, 3)
    return base_quantity

def calculate_martingale_size(division_capital: float, level: int) -> float:
    """물타기 단계별 포지션 크기 계산"""
    if level >= len(MARTINGALE_MULTIPLIERS):
        return 0
    return division_capital * MARTINGALE_MULTIPLIERS[level]

def calculate_martingale_quantity(base_quantity: float, level: int) -> float:
    """물타기 단계별 실제 구매 수량 계산"""
    if level >= len(MARTINGALE_MULTIPLIERS):
        return 0
    # 기본 수량에 물타기 배수 곱하기
    quantity = round(base_quantity * MARTINGALE_MULTIPLIERS[level], 3)
    return quantity

def should_trigger_martingale(current_price: float, entry_price: float, direction: str, trigger_pct: float) -> bool:
    """물타기 트리거 조건 확인"""
    if direction == 'long':
        return current_price <= entry_price * (1 - trigger_pct)
    elif direction == 'short':
        return current_price >= entry_price * (1 + trigger_pct)
    return False

def calculate_profit_rate(current_price: float, avg_price: float, direction: str) -> float:
    """수익률 계산"""
    if direction == 'long':
        return (current_price - avg_price) / avg_price
    elif direction == 'short':
        return (avg_price - current_price) / avg_price
    return 0

# ========================= 메모리 관리 유틸리티 =========================
def cleanup_memory():
    """메모리 정리 함수"""
    try:
        # 가비지 컬렉션 강제 실행
        collected = gc.collect()
        
        # 메모리 사용량 확인
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        logger.info(f"메모리 정리 완료: {collected}개 객체 수집, 현재 사용량: {memory_mb:.2f} MB")
        return memory_mb
    except Exception as e:
        logger.warning(f"메모리 정리 중 오류: {e}")
        return 0

def cleanup_dataframes(*dataframes):
    """데이터프레임들 명시적 삭제"""
    for df in dataframes:
        if df is not None:
            try:
                del df
            except:
                pass

def cleanup_variables(**kwargs):
    """변수들 명시적 삭제"""
    for var_name, var_value in kwargs.items():
        if var_value is not None:
            try:
                del var_value
            except:
                pass

# ========================= 로깅 유틸리티 =========================
def log_trade_action(action_type, coin_ticker, position_side, price, quantity, reason="", profit=0, profit_rate=0):
    try:
        # 수익/손실에 따른 색상 버튼 생성
        if profit > 0:
            profit_emoji = "🟢"
        elif profit < 0:
            profit_emoji = "🔴"
        else:
            profit_emoji = "⚪"
        
        # 거래 로그 메시지 생성
        trade_msg = f"{profit_emoji} {action_type} | {coin_ticker} | {position_side.upper()} | {price:.2f} | {quantity:.4f} | {reason}"
        if profit != 0:
            trade_msg += f" | P/L: {profit:.2f} ({profit_rate:.2f}%)"
        
        trade_logger.info(trade_msg)
        logger.info(trade_msg)
        
    except Exception as e:
        logger.error(f"거래 로그 기록 실패: {e}")

def log_error(message, error_detail=None):
    """에러 로깅"""
    logger.error(message)
    if error_detail:
        logger.error(f"상세: {error_detail}")

# ========================= 물타기 거래 함수들 =========================
def execute_long_martingale(binanceX, Target_Coin_Ticker, coin_price, long_data, base_quantity, water_bot_config, dic, line_alert, logger):
    """롱 포지션 물타기 로직 실행"""
    entry_price = long_data.get('entry_price', 0)
    avg_price = long_data.get('avg_price', entry_price)
    long_slide_level = long_data.get('slide_level', 0)
    
    # 물타기 트리거 확인
    if should_trigger_martingale(coin_price, entry_price, 'long', water_bot_config['martingale_trigger_pct']):
        if long_slide_level < MAX_MARTINGALE_LEVEL:
            # 물타기 실행 - 기본 수량에 물타기 배수 곱하기
            martingale_quantity = calculate_martingale_quantity(base_quantity, long_slide_level)
            if martingale_quantity > 0:
                try:
                    # 현재가보다 약간 높은 가격으로 limit 주문
                    limit_price = coin_price * 1.001  # 0.1% 높은 가격
                    data = binanceX.create_order(Target_Coin_Ticker, 'limit', 'buy', martingale_quantity, limit_price, {'positionSide': 'LONG'})
                    buy_price = float(data.get('average', limit_price))
                    
                    # 평균 단가 업데이트
                    total_cost = long_data.get('total_cost', 0) + (buy_price * martingale_quantity)
                    total_size = long_data.get('position_size', 0) + martingale_quantity
                    new_avg_price = total_cost / total_size
                    
                    # 포지션 정보 업데이트
                    long_data['position_size'] = total_size
                    long_data['total_cost'] = total_cost
                    long_data['avg_price'] = new_avg_price
                    long_data['slide_level'] = long_slide_level + 1
                    
                    logger.info(f"롱 물타기 {long_slide_level + 1}단계 실행: {martingale_quantity:.3f} @ {buy_price:.2f}")
                    line_alert.SendMessage(f"💧📈 롱 물타기 {long_slide_level + 1}단계\n- 코인: {Target_Coin_Ticker}\n- 가격: {buy_price:.2f}\n- 수량: {martingale_quantity:.3f}\n- 평균단가: {new_avg_price:.2f}")
                    
                    # 물타기 후 미리 주문 걸어두기
                    long_data['position_side'] = 'LONG'
                    place_pre_orders(binanceX, Target_Coin_Ticker, coin_price, long_data, water_bot_config, logger)
                    
                except Exception as e:
                    logger.error(f"롱 물타기 실행 실패: {e}")

def execute_short_martingale(binanceX, Target_Coin_Ticker, coin_price, short_data, base_quantity, water_bot_config, dic, line_alert, logger):
    """숏 포지션 물타기 로직 실행"""
    entry_price = short_data.get('entry_price', 0)
    avg_price = short_data.get('avg_price', entry_price)
    short_slide_level = short_data.get('slide_level', 0)
    
    # 물타기 트리거 확인 (숏은 가격 상승 시)
    if should_trigger_martingale(coin_price, entry_price, 'short', water_bot_config['martingale_trigger_pct']):
        if short_slide_level < MAX_MARTINGALE_LEVEL:
            # 물타기 실행 - 기본 수량에 물타기 배수 곱하기
            martingale_quantity = calculate_martingale_quantity(base_quantity, short_slide_level)
            if martingale_quantity > 0:
                try:
                    # 현재가보다 약간 낮은 가격으로 limit 주문
                    limit_price = coin_price * 0.999  # 0.1% 낮은 가격
                    data = binanceX.create_order(Target_Coin_Ticker, 'limit', 'sell', martingale_quantity, limit_price, {'positionSide': 'SHORT'})
                    sell_price = float(data.get('average', limit_price))
                    
                    # 평균 단가 업데이트
                    total_cost = short_data.get('total_cost', 0) + (sell_price * martingale_quantity)
                    total_size = short_data.get('position_size', 0) + martingale_quantity
                    new_avg_price = total_cost / total_size
                    
                    # 포지션 정보 업데이트
                    short_data['position_size'] = total_size
                    short_data['total_cost'] = total_cost
                    short_data['avg_price'] = new_avg_price
                    short_data['slide_level'] = short_slide_level + 1
                    
                    logger.info(f"숏 물타기 {short_slide_level + 1}단계 실행: {martingale_quantity:.3f} @ {sell_price:.2f}")
                    line_alert.SendMessage(f"💧📉 숏 물타기 {short_slide_level + 1}단계\n- 코인: {Target_Coin_Ticker}\n- 가격: {sell_price:.2f}\n- 수량: {martingale_quantity:.3f}\n- 평균단가: {new_avg_price:.2f}")
                    
                    # 물타기 후 미리 주문 걸어두기
                    short_data['position_side'] = 'SHORT'
                    place_pre_orders(binanceX, Target_Coin_Ticker, coin_price, short_data, water_bot_config, logger)
                    
                except Exception as e:
                    logger.error(f"숏 물타기 실행 실패: {e}")

def check_pre_orders_executed(binanceX, Target_Coin_Ticker, position_data, water_bot_config, logger):
    """미리 걸어둔 주문이 체결되었는지 확인하고 포지션 업데이트"""
    position_side = position_data.get('position_side', 'LONG')
    position_size = position_data.get('position_size', 0)
    avg_price = position_data.get('avg_price', 0)
    
    if position_size <= 0:
        return False
    
    try:
        # 현재 포지션 크기 확인
        positions = binanceX.fetch_positions([Target_Coin_Ticker])
        current_position_size = 0
        
        for pos in positions:
            if pos['symbol'] == Target_Coin_Ticker.replace('/', '') and pos['side'] == 'long':
                current_position_size = float(pos['contracts'])
                break
        
        # 포지션 크기가 줄어들었다면 주문이 체결된 것
        if current_position_size < position_size:
            reduction = position_size - current_position_size
            reduction_ratio = reduction / position_size
            
            # 50% 매도가 체결되었는지 확인
            if 0.4 <= reduction_ratio <= 0.6:  # 50% ± 10% 허용
                position_data['partial_sell_done'] = True
                position_data['position_size'] = current_position_size
                logger.info(f"{position_side} 50% 매도 주문 체결: {reduction:.6f} 감소")
                return True
            
            # 25% 매도가 체결되었는지 확인 (두 번째 매도)
            elif 0.2 <= reduction_ratio <= 0.3:  # 25% ± 5% 허용
                position_data['second_partial_sell_done'] = True
                position_data['position_size'] = current_position_size
                logger.info(f"{position_side} 25% 매도 주문 체결: {reduction:.6f} 감소")
                return True
                
    except Exception as e:
        logger.error(f"미리 주문 체결 확인 실패: {e}")
    
    return False

def execute_long_profit_taking(binanceX, Target_Coin_Ticker, coin_price, long_data, water_bot_config, dic, line_alert, logger):
    """롱 포지션 수익 실현 로직"""
    avg_price = long_data.get('avg_price', 0)
    long_slide_level = long_data.get('slide_level', 0)
    profit_rate = calculate_profit_rate(coin_price, avg_price, 'long')
    
    # 미리 걸어둔 주문 체결 확인 (물타기 여부 관계없이)
    check_pre_orders_executed(binanceX, Target_Coin_Ticker, long_data, water_bot_config, logger)
    
    # 물타기 안했을 때 (1분할만) - 미리 주문으로 처리되므로 여기서는 트레일링 스탑만 체크
    if long_slide_level == 0:
        if profit_rate >= water_bot_config['trailing_stop_activation']:  # 0.4% 수익
            if not long_data.get('trailing_stop_triggered', False):
                # 트레일링 스탑 활성화
                long_data['trailing_stop_triggered'] = True
                long_data['highest_price'] = coin_price
                
                logger.info(f"롱 트레일링 스탑 활성화: {coin_price:.2f}")
                line_alert.SendMessage(f"🎯📈 롱 트레일링 스탑 활성화\n- 코인: {Target_Coin_Ticker}\n- 가격: {coin_price:.2f}")
    
    # 물타기 했을 때 - 미리 주문으로 처리되므로 여기서는 트레일링 스탑만 체크
    else:
        if profit_rate >= water_bot_config['trailing_stop_activation']:  # 0.4% 수익
            if not long_data.get('trailing_stop_triggered', False):
                # 트레일링 스탑 활성화
                long_data['trailing_stop_triggered'] = True
                long_data['highest_price'] = coin_price
                
                logger.info(f"롱 물타기 트레일링 스탑 활성화: {coin_price:.2f}")
                line_alert.SendMessage(f"🎯📈 롱 물타기 트레일링 스탑 활성화\n- 코인: {Target_Coin_Ticker}\n- 가격: {coin_price:.2f}")
            

def execute_short_profit_taking(binanceX, Target_Coin_Ticker, coin_price, short_data, water_bot_config, dic, line_alert, logger):
    """숏 포지션 수익 실현 로직"""
    avg_price = short_data.get('avg_price', 0)
    short_slide_level = short_data.get('slide_level', 0)
    profit_rate = calculate_profit_rate(coin_price, avg_price, 'short')
    
    # 미리 걸어둔 주문 체결 확인 (물타기 여부 관계없이)
    check_pre_orders_executed(binanceX, Target_Coin_Ticker, short_data, water_bot_config, logger)
    
    # 물타기 안했을 때 (1분할만) - 미리 주문으로 처리되므로 여기서는 트레일링 스탑만 체크
    if short_slide_level == 0:
        if profit_rate >= water_bot_config['trailing_stop_activation']:  # 0.4% 수익
            if not short_data.get('trailing_stop_triggered', False):
                # 트레일링 스탑 활성화
                short_data['trailing_stop_triggered'] = True
                short_data['lowest_price'] = coin_price
                
                logger.info(f"숏 트레일링 스탑 활성화: {coin_price:.2f}")
                line_alert.SendMessage(f"🎯📉 숏 트레일링 스탑 활성화\n- 코인: {Target_Coin_Ticker}\n- 가격: {coin_price:.2f}")
    
    # 물타기 했을 때 - 미리 주문으로 처리되므로 여기서는 트레일링 스탑만 체크
    else:
        if profit_rate >= water_bot_config['trailing_stop_activation']:  # 0.4% 수익
            if not short_data.get('trailing_stop_triggered', False):
                # 트레일링 스탑 활성화
                short_data['trailing_stop_triggered'] = True
                short_data['lowest_price'] = coin_price
                
                logger.info(f"숏 물타기 트레일링 스탑 활성화: {coin_price:.2f}")
                line_alert.SendMessage(f"🎯📉 숏 물타기 트레일링 스탑 활성화\n- 코인: {Target_Coin_Ticker}\n- 가격: {coin_price:.2f}")
        

def cancel_existing_orders(binanceX, Target_Coin_Ticker, position_side, logger):
    """기존 미리 걸어둔 주문 취소"""
    try:
        orders = binanceX.fetch_orders(Target_Coin_Ticker)
        
        for order in orders:
            if (order['status'] == "open" and 
                order['info']['positionSide'] == position_side and
                order['side'] == 'sell'):  # 매도 주문만 취소
                try:
                    binanceX.cancel_order(order['id'], Target_Coin_Ticker)
                    logger.info(f"{Target_Coin_Ticker} {position_side} 매도 주문 취소: {order['id']}")
                    time.sleep(0.1)
                except Exception as e:
                    logger.error(f"주문 취소 실패: {e}")
                    
    except Exception as e:
        logger.error(f"주문 조회 실패: {e}")

def place_pre_orders(binanceX, Target_Coin_Ticker, coin_price, position_data, water_bot_config, logger):
    """물타기 후 미리 지정가 주문 걸어두기"""
    position_side = position_data.get('position_side', 'LONG')
    position_size = position_data.get('position_size', 0)
    avg_price = position_data.get('avg_price', 0)
    slide_level = position_data.get('slide_level', 0)
    
    # 포지션이 있을 때만 미리 주문 걸기
    if position_size <= 0:
        return
    
    # 최소 주문 수량 확인
    minimum_amount = myBinance.GetMinimumAmount(binanceX, Target_Coin_Ticker)
    
    # 기존 주문 취소
    cancel_existing_orders(binanceX, Target_Coin_Ticker, position_side, logger)
    
    try:
        if position_side == 'LONG':
            # 롱 포지션: 0.2%에서 50% 매도, 0.4%에서 25% 매도
            target_price_1 = avg_price * (1 + water_bot_config['profit_target_1'])  # 0.2%
            target_price_2 = avg_price * (1 + water_bot_config['profit_target_2'])  # 0.4%
            
            # 첫 번째 50% 매도 주문
            sell_qty_1 = position_size * 0.5
            if sell_qty_1 >= minimum_amount:
                try:
                    binanceX.create_order(
                        Target_Coin_Ticker, 'limit', 'sell', 
                        sell_qty_1, target_price_1, 
                        {'positionSide': 'LONG'}
                    )
                    logger.info(f"롱 50% 매도 주문 등록: {sell_qty_1:.6f} @ {target_price_1:.2f}")
                except Exception as e:
                    logger.error(f"롱 50% 매도 주문 실패: {e}")
            
            # 두 번째 25% 매도 주문 (남은 것의 50%)
            sell_qty_2 = position_size * 0.25
            if sell_qty_2 >= minimum_amount:
                try:
                    binanceX.create_order(
                        Target_Coin_Ticker, 'limit', 'sell', 
                        sell_qty_2, target_price_2, 
                        {'positionSide': 'LONG'}
                    )
                    logger.info(f"롱 25% 매도 주문 등록: {sell_qty_2:.6f} @ {target_price_2:.2f}")
                except Exception as e:
                    logger.error(f"롱 25% 매도 주문 실패: {e}")
        
        elif position_side == 'SHORT':
            # 숏 포지션: 0.2%에서 50% 매도, 0.4%에서 25% 매도
            target_price_1 = avg_price * (1 - water_bot_config['profit_target_1'])  # 0.2%
            target_price_2 = avg_price * (1 - water_bot_config['profit_target_2'])  # 0.4%
            
            # 첫 번째 50% 매도 주문 (숏은 buy로 청산)
            buy_qty_1 = position_size * 0.5
            if buy_qty_1 >= minimum_amount:
                try:
                    binanceX.create_order(
                        Target_Coin_Ticker, 'limit', 'buy', 
                        buy_qty_1, target_price_1, 
                        {'positionSide': 'SHORT'}
                    )
                    logger.info(f"숏 50% 매도 주문 등록: {buy_qty_1:.6f} @ {target_price_1:.2f}")
                except Exception as e:
                    logger.error(f"숏 50% 매도 주문 실패: {e}")
            
            # 두 번째 25% 매도 주문 (남은 것의 50%)
            buy_qty_2 = position_size * 0.25
            if buy_qty_2 >= minimum_amount:
                try:
                    binanceX.create_order(
                        Target_Coin_Ticker, 'limit', 'buy', 
                        buy_qty_2, target_price_2, 
                        {'positionSide': 'SHORT'}
                    )
                    logger.info(f"숏 25% 매도 주문 등록: {buy_qty_2:.6f} @ {target_price_2:.2f}")
                except Exception as e:
                    logger.error(f"숏 25% 매도 주문 실패: {e}")
                    
    except Exception as e:
        logger.error(f"미리 주문 걸기 실패: {e}")

def execute_trailing_stop(binanceX, Target_Coin_Ticker, coin_price, long_data, short_data, water_bot_config, dic, line_alert, logger):
    """트레일링 스탑 실행 로직"""
    # 롱 포지션 트레일링 스탑
    if long_data.get('trailing_stop_triggered', False) and long_data.get('position', 0) > 0:
        avg_price = long_data.get('avg_price', 0)
        current_profit_pct = (coin_price - avg_price) / avg_price
        
        # 최고가 업데이트
        if current_profit_pct >= 0.003 and coin_price > long_data.get('highest_price', coin_price):
            long_data['highest_price'] = coin_price
        
        # 동적 트레일링 스탑 계산 (수익률이 커질수록 스탑 비율 감소)
        activation_threshold = water_bot_config['trailing_stop_activation']  # 4%
        min_ratio = water_bot_config['trailing_stop_min_ratio']  # 10%
        reduction_rate = water_bot_config['trailing_stop_reduction_rate']  # 5%
        
        if current_profit_pct >= activation_threshold:
            # 4% 이상일 때만 트레일링 스탑 적용
            additional_profit = current_profit_pct - activation_threshold  # 4% 초과 수익
            
            # 수익률이 커질수록 스탑 비율 감소
            # 4%+1% = 50%, 4%+2% = 45%, 4%+3% = 40%, 4%+4% = 35%, 4%+5% = 30%, ..., 최소 10%
            stop_ratio = max(min_ratio, 0.5 - (additional_profit * reduction_rate))
            
            # 실제 스탑 가격 계산 (진입가 기준으로 stop_ratio만큼 하락)
            # 4% + additional_profit * stop_ratio = 4% + 0.5% * 50% = 4.25%
            stop_profit_pct = activation_threshold + (additional_profit * stop_ratio)
            stop_price = avg_price * (1 + stop_profit_pct)
            
            if coin_price <= stop_price:
                # 롱 포지션 전체 청산
                try:
                    sell_qty = long_data['position_size']
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', sell_qty, None, {'positionSide': 'LONG'})
                    sell_price = float(data.get('average', coin_price))
                    
                    profit = (sell_price - avg_price) * sell_qty * (1 - (COIN_CHARGE * 2))
                    
                    # 자금 업데이트
                    dic['my_money'] += profit
                    total_profit_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100.0
                    
                    logger.info(f"롱 트레일링 스탑 실행: {sell_qty} @ {sell_price:.2f}, 수익: {profit:.2f} USDT, 스탑비율: {stop_ratio:.1%}")
                    line_alert.SendMessage(f"🎯📈 롱 트레일링 스탑 실행\n- 코인: {Target_Coin_Ticker}\n- 가격: {sell_price:.2f}\n- 수익: {profit:.2f} USDT\n- 스탑비율: {stop_ratio:.1%}\n- 총손익률: {total_profit_rate:.2f}%")
                    
                    # 포지션 초기화
                    long_data.update({
                        'position': 0, 'entry_price': 0, 'position_size': 0, 'stop_loss_price': 0,
                        'slide_level': 0, 'total_cost': 0, 'avg_price': 0,
                        'partial_sell_done': False, 'second_partial_sell_done': False,
                        'trailing_stop_triggered': False, 'highest_price': 0
                    })
                    
                except Exception as e:
                    logger.error(f"롱 트레일링 스탑 실행 실패: {e}")
    
    # 숏 포지션 트레일링 스탑
    if short_data.get('trailing_stop_triggered', False) and short_data.get('position', 0) > 0:
        avg_price = short_data.get('avg_price', 0)
        current_profit_pct = (avg_price - coin_price) / avg_price
        
        # 최저가 업데이트
        if current_profit_pct >= 0.003 and coin_price < short_data.get('lowest_price', coin_price):
            short_data['lowest_price'] = coin_price
        
        # 동적 트레일링 스탑 계산 (수익률이 커질수록 스탑 비율 감소)
        activation_threshold = water_bot_config['trailing_stop_activation']  # 4%
        min_ratio = water_bot_config['trailing_stop_min_ratio']  # 10%
        reduction_rate = water_bot_config['trailing_stop_reduction_rate']  # 5%
        
        if current_profit_pct >= activation_threshold:
            # 4% 이상일 때만 트레일링 스탑 적용
            additional_profit = current_profit_pct - activation_threshold  # 4% 초과 수익
            
            # 수익률이 커질수록 스탑 비율 감소
            # 4%+1% = 50%, 4%+2% = 45%, 4%+3% = 40%, 4%+4% = 35%, 4%+5% = 30%, ..., 최소 10%
            stop_ratio = max(min_ratio, 0.5 - (additional_profit * reduction_rate))
            
            # 실제 스탑 가격 계산 (진입가 기준으로 stop_ratio만큼 상승)
            # 4% + additional_profit * stop_ratio = 4% + 0.5% * 50% = 4.25%
            stop_profit_pct = activation_threshold + (additional_profit * stop_ratio)
            stop_price = avg_price * (1 - stop_profit_pct)
            
            if coin_price >= stop_price:
                # 숏 포지션 전체 청산
                try:
                    buy_qty = short_data['position_size']
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', buy_qty, None, {'positionSide': 'SHORT'})
                    buy_price = float(data.get('average', coin_price))
                    
                    profit = (avg_price - buy_price) * buy_qty * (1 - (COIN_CHARGE * 2))
                    
                    # 자금 업데이트
                    dic['my_money'] += profit
                    total_profit_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100.0
                    
                    logger.info(f"숏 트레일링 스탑 실행: {buy_qty} @ {buy_price:.2f}, 수익: {profit:.2f} USDT, 스탑비율: {stop_ratio:.1%}")
                    line_alert.SendMessage(f"🎯📉 숏 트레일링 스탑 실행\n- 코인: {Target_Coin_Ticker}\n- 가격: {buy_price:.2f}\n- 수익: {profit:.2f} USDT\n- 스탑비율: {stop_ratio:.1%}\n- 총손익률: {total_profit_rate:.2f}%")
                    
                    # 포지션 초기화
                    short_data.update({
                        'position': 0, 'entry_price': 0, 'position_size': 0, 'stop_loss_price': 0,
                        'slide_level': 0, 'total_cost': 0, 'avg_price': 0,
                        'partial_sell_done': False, 'second_partial_sell_done': False,
                        'trailing_stop_triggered': False, 'lowest_price': 0
                    })
                    
                except Exception as e:
                    logger.error(f"숏 트레일링 스탑 실행 실패: {e}")

def execute_long_stop_loss(binanceX, Target_Coin_Ticker, coin_price, long_data, dic, line_alert, logger):
    """롱 포지션 손절매 로직"""
    avg_price = long_data.get('avg_price', 0)
    long_slide_level = long_data.get('slide_level', 0)
    profit_rate = calculate_profit_rate(coin_price, avg_price, 'long')
    
    # 손절매 체크
    if long_slide_level >= 4 and profit_rate <= -0.15:  # 4단계 이상에서 15% 손실
        try:
            close_qty = long_data['position_size']
            if close_qty > 0:
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', close_qty, None, {'positionSide': 'LONG'})
                sell_price = float(data.get('average', coin_price))
                
                loss = (avg_price - sell_price) * close_qty * (1 - (COIN_CHARGE * 2))
                
                # 자금 업데이트
                dic['my_money'] += loss
                total_profit_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100.0
                
                # 포지션 초기화
                long_data['position'] = 0
                long_data['entry_price'] = 0
                long_data['position_size'] = 0
                long_data['slide_level'] = 0
                long_data['total_cost'] = 0
                long_data['avg_price'] = 0
                long_data['partial_sell_done'] = False
                long_data['second_partial_sell_done'] = False
                
                logger.info(f"롱 손절매: {close_qty} @ {sell_price:.2f}, 손실: {loss:.2f} USDT")
                line_alert.SendMessage(f"🛑📈 롱 손절매\n- 코인: {Target_Coin_Ticker}\n- 가격: {sell_price:.2f}\n- 손실: {loss:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")
                
        except Exception as e:
            logger.error(f"롱 손절매 실패: {e}")
    
    elif long_slide_level >= 5 and profit_rate <= -0.25:  # 5단계에서 25% 손실
        try:
            close_qty = long_data['position_size']
            if close_qty > 0:
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', close_qty, None, {'positionSide': 'LONG'})
                sell_price = float(data.get('average', coin_price))
                
                loss = (avg_price - sell_price) * close_qty * (1 - (COIN_CHARGE * 2))
                
                # 자금 업데이트
                dic['my_money'] += loss
                total_profit_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100.0
                
                # 포지션 초기화
                long_data['position'] = 0
                long_data['entry_price'] = 0
                long_data['position_size'] = 0
                long_data['slide_level'] = 0
                long_data['total_cost'] = 0
                long_data['avg_price'] = 0
                long_data['partial_sell_done'] = False
                long_data['second_partial_sell_done'] = False
                
                logger.info(f"롱 최종 손절매: {close_qty} @ {sell_price:.2f}, 손실: {loss:.2f} USDT")
                line_alert.SendMessage(f"🛑📈 롱 최종 손절매\n- 코인: {Target_Coin_Ticker}\n- 가격: {sell_price:.2f}\n- 손실: {loss:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")

        except Exception as e:
            logger.error(f"롱 최종 손절매 실패: {e}")

def execute_short_stop_loss(binanceX, Target_Coin_Ticker, coin_price, short_data, dic, line_alert, logger):
    """숏 포지션 손절매 로직"""
    avg_price = short_data.get('avg_price', 0)
    short_slide_level = short_data.get('slide_level', 0)
    profit_rate = calculate_profit_rate(coin_price, avg_price, 'short')
    
    # 손절매 체크 (숏)
    if short_slide_level >= 4 and profit_rate <= -0.15:  # 4단계 이상에서 15% 손실
        try:
            close_qty = short_data['position_size']
            if close_qty > 0:
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', close_qty, None, {'positionSide': 'SHORT'})
                buy_price = float(data.get('average', coin_price))
                
                loss = (buy_price - avg_price) * close_qty * (1 - (COIN_CHARGE * 2))
                
                # 자금 업데이트
                dic['my_money'] += loss
                total_profit_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100.0
                
                # 포지션 초기화
                short_data['position'] = 0
                short_data['entry_price'] = 0
                short_data['position_size'] = 0
                short_data['slide_level'] = 0
                short_data['total_cost'] = 0
                short_data['avg_price'] = 0
                short_data['partial_sell_done'] = False
                short_data['second_partial_sell_done'] = False
                
                logger.info(f"숏 손절매: {close_qty} @ {buy_price:.2f}, 손실: {loss:.2f} USDT")
                line_alert.SendMessage(f"🛑📉 숏 손절매\n- 코인: {Target_Coin_Ticker}\n- 가격: {buy_price:.2f}\n- 손실: {loss:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")
                
        except Exception as e:
            logger.error(f"숏 손절매 실패: {e}")
    
    elif short_slide_level >= 5 and profit_rate <= -0.25:  # 5단계에서 25% 손실
        try:
            close_qty = short_data['position_size']
            if close_qty > 0:
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', close_qty, None, {'positionSide': 'SHORT'})
                buy_price = float(data.get('average', coin_price))
                
                loss = (buy_price - avg_price) * close_qty * (1 - (COIN_CHARGE * 2))
                
                # 자금 업데이트
                dic['my_money'] += loss
                total_profit_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100.0
                
                # 포지션 초기화
                short_data['position'] = 0
                short_data['entry_price'] = 0
                short_data['position_size'] = 0
                short_data['slide_level'] = 0
                short_data['total_cost'] = 0
                short_data['avg_price'] = 0
                short_data['partial_sell_done'] = False
                short_data['second_partial_sell_done'] = False
                
                logger.info(f"숏 최종 손절매: {close_qty} @ {buy_price:.2f}, 손실: {loss:.2f} USDT")
                line_alert.SendMessage(f"🛑📉 숏 최종 손절매\n- 코인: {Target_Coin_Ticker}\n- 가격: {buy_price:.2f}\n- 손실: {loss:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")

        except Exception as e:
            logger.error(f"숏 최종 손절매 실패: {e}")

def execute_long_entry(binanceX, Target_Coin_Ticker, coin_price, long_data, base_quantity, water_bot_config, line_alert, logger):
    """롱 신규 진입 로직"""
    try:
        # 1분할로 진입 - 기본 수량 사용 (limit 주문으로 수수료 절약)
        if base_quantity > 0:
            # 현재가보다 약간 높은 가격으로 limit 주문
            limit_price = coin_price * 1.001  # 0.1% 높은 가격
            data = binanceX.create_order(Target_Coin_Ticker, 'limit', 'buy', base_quantity, limit_price, {'positionSide': 'LONG'})
            buy_price = float(data.get('average', limit_price))
            
            # 포지션 정보 설정
            long_data['position'] = 1
            long_data['entry_price'] = buy_price
            long_data['position_size'] = base_quantity
            long_data['slide_level'] = 0
            long_data['total_cost'] = buy_price * base_quantity
            long_data['avg_price'] = buy_price
            long_data['partial_sell_done'] = False
            long_data['second_partial_sell_done'] = False
            
            logger.info(f"롱 신규 진입: {base_quantity:.3f} @ {buy_price:.2f}")
            line_alert.SendMessage(f"🚀📈 롱 신규 진입\n- 코인: {Target_Coin_Ticker}\n- 가격: {buy_price:.2f}\n- 수량: {base_quantity:.3f}\n- 신호: BB하단터치 + RSI과매도")
            
            # 신규 진입 시에도 미리 주문 걸어두기 (물타기 안했을 때)
            long_data['position_side'] = 'LONG'
            place_pre_orders(binanceX, Target_Coin_Ticker, coin_price, long_data, water_bot_config, logger)
            
    except Exception as e:
        logger.error(f"롱 신규 진입 실패: {e}")

def execute_short_entry(binanceX, Target_Coin_Ticker, coin_price, short_data, base_quantity, water_bot_config, line_alert, logger):
    """숏 신규 진입 로직"""
    try:
        # 1분할로 진입 - 기본 수량 사용 (limit 주문으로 수수료 절약)
        if base_quantity > 0:
            # 현재가보다 약간 낮은 가격으로 limit 주문
            limit_price = coin_price * 0.999  # 0.1% 낮은 가격
            data = binanceX.create_order(Target_Coin_Ticker, 'limit', 'sell', base_quantity, limit_price, {'positionSide': 'SHORT'})
            sell_price = float(data.get('average', limit_price))
            
            # 포지션 정보 설정
            short_data['position'] = 1
            short_data['entry_price'] = sell_price
            short_data['position_size'] = base_quantity
            short_data['slide_level'] = 0
            short_data['total_cost'] = sell_price * base_quantity
            short_data['avg_price'] = sell_price
            short_data['partial_sell_done'] = False
            short_data['second_partial_sell_done'] = False
            
            logger.info(f"숏 신규 진입: {base_quantity:.3f} @ {sell_price:.2f}")
            line_alert.SendMessage(f"🚀📉 숏 신규 진입\n- 코인: {Target_Coin_Ticker}\n- 가격: {sell_price:.2f}\n- 수량: {base_quantity:.3f}\n- 신호: BB상단터치 + RSI과매수")
            
            # 신규 진입 시에도 미리 주문 걸어두기 (물타기 안했을 때)
            short_data['position_side'] = 'SHORT'
            place_pre_orders(binanceX, Target_Coin_Ticker, coin_price, short_data, water_bot_config, logger)
            
    except Exception as e:
        logger.error(f"숏 신규 진입 실패: {e}")

# ========================= 메인 실행 코드 =========================
if __name__ == "__main__":
    logger.info("=== Live Water Bot 시작 ===")
    
    # 바이낸스 API 설정
    simpleEnDecrypt = myBinance.SimpleEnDecrypt(ende_key.ende_key)
    Binance_AccessKey = simpleEnDecrypt.decrypt(my_key.binance_access)
    Binance_ScretKey = simpleEnDecrypt.decrypt(my_key.binance_secret)
    
    binanceX = ccxt.binance(config={
        'apiKey': Binance_AccessKey, 
        'secret': Binance_ScretKey,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True,
        }
    })

    # 봇 시작 시 서버 시간과 동기화
    logger.info("서버 시간과 동기화를 시도합니다...")
    try:
        binanceX.load_time_difference()
        original_offset = binanceX.options.get('timeDifference', 0)
        safety_margin = -1000
        final_offset = original_offset + safety_margin
        binanceX.options['timeDifference'] = final_offset
        logger.info(f"서버 시간 동기화 완료: 오프셋 {final_offset}ms")
    except Exception as e:
        logger.critical(f"시간 동기화 실패: {e}")
        sys.exit(1)

    # 설정파일 json로드
    info_file_path = os.path.join(os.path.dirname(__file__), "water_bot.json")
    try:
        with open(info_file_path, 'r', encoding='utf-8') as f:
            dic = json.load(f)
        
        # 매 실행 시 실제 잔고를 가져와서 my_money 업데이트
        try:
            current_balance = binanceX.fetch_balance(params={"type": "future"})['USDT']['total']
            old_money = dic['my_money']
            dic['my_money'] = current_balance
            logger.info(f"잔고 업데이트: {old_money:.2f} USDT → {current_balance:.2f} USDT")
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"잔고 조회 실패, 기존 값 유지: {e}")
            
    except FileNotFoundError:
        logger.info("설정 파일이 없어 새로 생성합니다.")
        balance = binanceX.fetch_balance(params={"type": "future"})['USDT']['total']
        time.sleep(0.1)
        dic = {
            "start_money": balance, "my_money": balance,
            "coins": {
                "BTC/USDT": {
                    "long": {
                        "position": 0, "entry_price": 0, "position_size": 0, "stop_loss_price": 0,
                        "slide_level": 0, "total_cost": 0, "avg_price": 0,
                        "partial_sell_done": False, "second_partial_sell_done": False
                    },
                    "short": {
                        "position": 0, "entry_price": 0, "position_size": 0, "stop_loss_price": 0,
                        "slide_level": 0, "total_cost": 0, "avg_price": 0,
                        "partial_sell_done": False, "second_partial_sell_done": False
                    }
                }
            },
            "water_bot_config": WATER_BOT_PARAMS,
            "position_tracking": {
                "current_ratio": 0.01,  # 현재 포지션 비율
                "consecutive_losses": 0,  # 연속 손실 횟수
                "consecutive_wins": 0     # 연속 승리 횟수
            }
        }

    # --- 물타기 봇 설정 ---
    water_bot_config = dic.get('water_bot_config', WATER_BOT_PARAMS)
    
    for Target_Coin_Ticker in ACTIVE_COINS:
        logger.info(f"=== {Target_Coin_Ticker} | 물타기 봇 시작 ===")
        
        Target_Coin_Symbol = Target_Coin_Ticker.replace("/", "")

        # 레버리지 설정
        try:
            leverage_result = binanceX.fapiPrivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': DEFAULT_LEVERAGE})
            logger.info(f"{Target_Coin_Symbol} 레버리지 설정 성공: {DEFAULT_LEVERAGE}배")
        except Exception as e:
            try:
                leverage_result = binanceX.fapiprivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': DEFAULT_LEVERAGE})
                logger.info(f"{Target_Coin_Symbol} 레버리지 설정 성공 (대체): {DEFAULT_LEVERAGE}배")
            except Exception as e2:
                error_msg = f"{Target_Coin_Symbol} 레버리지 설정 실패: {e2}"
                log_error(error_msg)
                continue

        # 데이터 수집 (최근 200개 캔들, 3분봉)
        df = myBinance.GetOhlcv(binanceX, Target_Coin_Ticker, '3m', 200)
        coin_price = df['close'].iloc[-1]
        
        logger.info(f"현재 {Target_Coin_Ticker} 가격: {coin_price:.2f} USDT")
        
        # 메모리 사용량 모니터링
        initial_memory = cleanup_memory()
        
        # 기술적 지표 계산 및 신호 생성
        try:
            # 기술적 지표 계산
            df_with_indicators = calculate_technical_indicators(df, water_bot_config)
            
            # 물타기 봇 신호 생성
            df_with_signals = generate_water_bot_signals(df_with_indicators, water_bot_config)
            
            # 최신 신호 확인
            latest_long_signal = df_with_signals['long_entry'].iloc[-1]
            latest_short_signal = df_with_signals['short_entry'].iloc[-1]
            
            logger.info(f"롱 신호: {latest_long_signal}, 숏 신호: {latest_short_signal}")
                
        except Exception as e:
            logger.error(f"기술적 지표 계산 실패: {e}")
            continue
        
        # 물타기 봇 거래 로직
        try:
            # 현재 포지션 정보 가져오기
            long_data = dic['coins'][Target_Coin_Ticker]['long']
            short_data = dic['coins'][Target_Coin_Ticker]['short']
            long_position = long_data['position']
            short_position = short_data['position']
            long_slide_level = long_data.get('slide_level', 0)
            short_slide_level = short_data.get('slide_level', 0)
            
            # 16분할 자본 계산
            division_capital = calculate_division_capital(dic['my_money']*INVESTMENT_RATIO)
            
            logger.info(f"현재 포지션 - 롱: {long_position}, 숏: {short_position}")
            logger.info(f"물타기 단계 - 롱: {long_slide_level}, 숏: {short_slide_level}")
            logger.info(f"분할 자본: {division_capital:.2f} USDT")
            
        except Exception as e:
            log_error(f"포지션 정보 조회 실패: {e}", traceback.format_exc())
            continue

        # ATR 기반 손절 체크
        try:
            current_atr = df_with_indicators['atr'].iloc[-1]
            logger.info(f"현재 ATR: {current_atr:.4f}")
        except:
            current_atr = None

        # --- 물타기 봇 거래 로직 ---
        logger.info("물타기 거래 로직 실행 중...")
        
        # 현재 포지션 상태 확인
        logger.info(f"현재 포지션 상태 - 롱: {long_position}, 숏: {short_position}")
        logger.info(f"물타기 단계 - 롱: {long_slide_level}, 숏: {short_slide_level}")
        
        # 최소 주문 수량 확인
        minimum_amount = myBinance.GetMinimumAmount(binanceX, Target_Coin_Ticker)
        
        # 기본 수량 계산 (32분할의 1개 분할) - 한 번만 계산
        base_quantity = calculate_base_quantity(division_capital, coin_price, DEFAULT_LEVERAGE)
        
        # 최소 주문 수량보다 작으면 최소 수량으로 조정
        if base_quantity < minimum_amount:
            base_quantity = minimum_amount
            logger.info(f"최소 주문 수량 적용: {base_quantity:.3f}")
        
        logger.info(f"기본 수량 (32분할 1개): {base_quantity:.3f}")
        
        # 1. 롱 포지션 물타기 로직
        if long_position == 1:
            # 물타기 실행
            execute_long_martingale(binanceX, Target_Coin_Ticker, coin_price, long_data, base_quantity, water_bot_config, dic, line_alert, logger)
            
            # 수익 실현 로직
            execute_long_profit_taking(binanceX, Target_Coin_Ticker, coin_price, long_data, water_bot_config, dic, line_alert, logger)
            
            # 손절매 체크
            execute_long_stop_loss(binanceX, Target_Coin_Ticker, coin_price, long_data, dic, line_alert, logger)
        
        # 2. 숏 포지션 물타기 로직
        if short_position == 1:
            # 물타기 실행
            execute_short_martingale(binanceX, Target_Coin_Ticker, coin_price, short_data, base_quantity, water_bot_config, dic, line_alert, logger)
            
            # 수익 실현 로직
            execute_short_profit_taking(binanceX, Target_Coin_Ticker, coin_price, short_data, water_bot_config, dic, line_alert, logger)
            
            # 손절매 체크
            execute_short_stop_loss(binanceX, Target_Coin_Ticker, coin_price, short_data, dic, line_alert, logger)

        # 3. 트레일링 스탑 실행 (독립적으로 실행)
        execute_trailing_stop(binanceX, Target_Coin_Ticker, coin_price, long_data, short_data, water_bot_config, dic, line_alert, logger)

        # 4. 신규 진입 로직 (BB + RSI 신호 기반) - 롱/숏 독립적으로 진입 가능
        # 롱 신호가 있고 롱 포지션이 없을 때 롱 진입
        if latest_long_signal == 1 and long_position == 0:
            execute_long_entry(binanceX, Target_Coin_Ticker, coin_price, long_data, base_quantity, water_bot_config, line_alert, logger)
        
        # 숏 신호가 있고 숏 포지션이 없을 때 숏 진입
        if latest_short_signal == 1 and short_position == 0:
            execute_short_entry(binanceX, Target_Coin_Ticker, coin_price, short_data, base_quantity, water_bot_config, line_alert, logger)

    # 설정 파일 저장
    try:
        with open(info_file_path, 'w', encoding='utf-8') as f:
            json.dump(dic, f, indent=2, ensure_ascii=False)
        logger.info("설정 파일 저장 완료")
    except Exception as e:
        logger.error(f"설정 파일 저장 실패: {e}")

    # 최종 메모리 정리
    final_memory = cleanup_memory()
    
    # API 연결 정리
    try:
        if 'binanceX' in locals():
            del binanceX
    except:
        pass
    
    # 전역 변수들 정리
    cleanup_variables(
        dic=dic,
        simpleEnDecrypt=simpleEnDecrypt
    )
    
    # 최종 가비지 컬렉션
    gc.collect()
    
    logger.info(f"=== Live Water Bot 종료 (최종 메모리: {final_memory:.2f} MB) ===")
