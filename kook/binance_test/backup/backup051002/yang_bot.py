import pandas as pd
import numpy as np
import datetime as dt
import json
import os
import logging

# ----------------------------------------------------------------------
# 1. 백테스트 설정
# ----------------------------------------------------------------------

# 백테스트에 사용할 CSV 파일 경로 (사용자 지정 경로)
CSV_PATH = r"C:\work\GitHub\py\kook\binance_test\data\BTCUSDT\1m\BTCUSDT_1m_2021.csv"
TARGET_COIN_TICKER = 'BTC/USDT'
TARGET_COIN_SYMBOL = 'BTCUSDT'

# ----------------------------------------------------------------------
# 로깅 설정
# ----------------------------------------------------------------------
class ColoredFormatter(logging.Formatter):
    """컬러 포맷터 클래스"""
    
    # ANSI 컬러 코드
    COLORS = {
        'DEBUG': '\033[36m',    # 청록색
        'INFO': '\033[37m',     # 흰색
        'WARNING': '\033[33m',  # 노란색
        'ERROR': '\033[31m',    # 빨간색
        'CRITICAL': '\033[35m', # 자주색
        'RESET': '\033[0m'      # 리셋
    }
    
    # 거래 관련 컬러
    TRADE_COLORS = {
        'LONG_ENTRY': '\033[97m',    # 흰색
        'SHORT_ENTRY': '\033[97m',   # 흰색
        'LONG_CLOSE': '\033[32m',    # 녹색
        'SHORT_CLOSE': '\033[31m',   # 빨간색
        'PROFIT': '\033[92m',        # 밝은 녹색
        'LOSS': '\033[91m',          # 밝은 빨간색
        'RESET': '\033[0m'           # 리셋
    }
    
    # 거래 관련 이모지
    TRADE_EMOJIS = {
        'LONG_ENTRY': '⚪',         # 롱 진입 (흰색)
        'SHORT_ENTRY': '⚪',        # 숏 진입 (흰색)
        'PROFIT_CLOSE': '🟢',       # 수익 청산
        'LOSS_CLOSE': '🔴',         # 손실 청산
        'PROFIT': '💰',             # 수익 달성
        'RESET': ''                 # 리셋
    }
    
    def format(self, record):
        # 기본 컬러 적용
        color = self.COLORS.get(record.levelname, self.COLORS['INFO'])
        record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        
        # 거래 관련 메시지에 특별한 컬러 및 이모지 적용
        message = record.getMessage()
        if '롱 진입' in message:
            emoji = self.TRADE_EMOJIS['LONG_ENTRY']
            message = f"{emoji} {self.TRADE_COLORS['LONG_ENTRY']}{message}{self.TRADE_COLORS['RESET']}"
        elif '숏 진입' in message:
            emoji = self.TRADE_EMOJIS['SHORT_ENTRY']
            message = f"{emoji} {self.TRADE_COLORS['SHORT_ENTRY']}{message}{self.TRADE_COLORS['RESET']}"
        elif '롱 청산' in message or '숏 청산' in message:
            # PnL 값에 따라 수익/손실 판단
            if 'PnL' in message:
                # PnL 값 추출 (예: "PnL 0.51$" 또는 "PnL -1.23$")
                import re
                pnl_match = re.search(r'PnL\s+([+-]?\d+\.?\d*)\$', message)
                if pnl_match:
                    pnl_value = float(pnl_match.group(1))
                    if pnl_value >= 0:
                        # 수익 청산
                        emoji = self.TRADE_EMOJIS['PROFIT_CLOSE']
                        color = self.TRADE_COLORS['PROFIT']
                    else:
                        # 손실 청산
                        emoji = self.TRADE_EMOJIS['LOSS_CLOSE']
                        color = self.TRADE_COLORS['LOSS']
                    message = f"{emoji} {color}{message}{self.TRADE_COLORS['RESET']}"
                else:
                    # PnL 정보가 없으면 기본 컬러
                    if '롱 청산' in message:
                        message = f"{self.TRADE_COLORS['LONG_CLOSE']}{message}{self.TRADE_COLORS['RESET']}"
                    else:
                        message = f"{self.TRADE_COLORS['SHORT_CLOSE']}{message}{self.TRADE_COLORS['RESET']}"
            else:
                # PnL 정보가 없으면 기본 컬러
                if '롱 청산' in message:
                    message = f"{self.TRADE_COLORS['LONG_CLOSE']}{message}{self.TRADE_COLORS['RESET']}"
                else:
                    message = f"{self.TRADE_COLORS['SHORT_CLOSE']}{message}{self.TRADE_COLORS['RESET']}"
        elif '달성!' in message:
            emoji = self.TRADE_EMOJIS['PROFIT']
            message = f"{emoji} {self.TRADE_COLORS['PROFIT']}{message}{self.TRADE_COLORS['RESET']}"
        elif '백테스트 결과' in message:
            emoji = self.TRADE_EMOJIS['PROFIT']
            message = f"{emoji} {self.TRADE_COLORS['PROFIT']}{message}{self.TRADE_COLORS['RESET']}"
        
        record.msg = message
        return super().format(record)

def setup_logging():
    """로그 설정 함수"""
    # 로그 디렉토리 생성
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 현재 날짜와 시간으로 로그 파일명 생성
    current_datetime = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{log_dir}/yang_bot_{current_datetime}.log"
    
    # 로거 생성
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 파일 핸들러 (컬러 없음)
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_formatter = logging.Formatter('%(asctime)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # 콘솔 핸들러 (컬러 있음)
    console_handler = logging.StreamHandler()
    console_formatter = ColoredFormatter('%(asctime)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # 핸들러 추가
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 로거 초기화
logger = setup_logging()

# ----------------------------------------------------------------------
# 2. 계좌 및 거래 설정
# ----------------------------------------------------------------------
INITIAL_MONEY = 10000.0   # 시작 잔고 (USDT)
LEVERAGE = 10             # 레버리지 10배로 가정
FEE_RATE = 0.0005        # 편도 수수료율 (0.05%)

# ----------------------------------------------------------------------
# 3. 전략 변수 설정
# ----------------------------------------------------------------------
INVESTMENT_RATIO = 1.0    # 투자비율 50%로 가정
DIVIDE = 100              # 분할
# 목표 수익률: 개별 포지션 청산 기준 (0.4% -> 0.004)
TARGET_REVENUE_RATE = 0.004
DIFFERENT_POSITION_ADD_ENTRY_RATE = -0.003
# 동일 포지션 추가 진입 기준 손실률: 이 손실률 도달 시 물타기 조건 확인 (-0.5% -> -0.005)
SAME_POSITION_ADD_ENTRY_RATE = -0.01


# ----------------------------------------------------------------------
# 2. 백테스트 유틸리티 함수 (실제 API 호출 대신 가상 포트폴리오 관리)
# ----------------------------------------------------------------------

# (실제 API 호출 대신) 가상 포트폴리오 관리
dic = {
    "yesterday": 0,
    "today": 0,
    "start_money": INITIAL_MONEY,
    "my_money": INITIAL_MONEY,
    "item": [],    # 진입 포지션 리스트
    "no": 0,       # 거래번호
    "total_fees": 0.0, # 누적 수수료
}

# ❗️ 추가 변수: 기본 1분할 수량을 전역으로 설정하여 execute_order에서 사용
GLOBAL_FIRST_AMOUNT = 0.0

# ❗️ 추가 변수: +5% 달성 시 포지션 정리를 위한 변수
POSITION_RESET_THRESHOLD = 3.0  # 3% 달성 시 포지션 정리
position_reset_done = False  # 포지션 정리 완료 여부
current_base_money = INITIAL_MONEY  # 현재 기준점 (포지션 정리 시 업데이트)
position_reset_count = 0  # 포지션 정리 실행 횟수 추적

# ❗️ 추가 변수: 최대 포지션 수량 추적
max_long_position = 0.0  # 최대 롱 포지션 수량
max_short_position = 0.0  # 최대 숏 포지션 수량
max_total_position = 0.0  # 최대 총 포지션 수량 

def calculate_current_pl(current_price, dic_item, total_money):
    """현재 포트폴리오의 미실현 손익(PnL)과 총 가치(Equity)를 계산"""
    total_unrealized_pnl = 0.0
    
    for item in dic_item:
        # original_enter_price가 있으면 사용, 없으면 enter_price 사용 (하위 호환성)
        enter_price = item.get("original_enter_price", item["enter_price"])
        
        if item["amt"] < 0:  # 숏 포지션
            pnl = (enter_price - current_price) * abs(item["amt"])
        else:  # 롱 포지션
            pnl = (current_price - enter_price) * abs(item["amt"])
            
        total_unrealized_pnl += pnl
        
    return total_unrealized_pnl, total_money + total_unrealized_pnl

def update_max_positions():
    """현재 포지션 수량을 계산하고 최대값을 업데이트"""
    global max_long_position, max_short_position, max_total_position
    
    current_long = sum(item["amt"] for item in dic["item"] if item["amt"] > 0)
    current_short = sum(abs(item["amt"]) for item in dic["item"] if item["amt"] < 0)
    current_total = current_long + current_short
    
    # 최대값 업데이트
    if current_long > max_long_position:
        max_long_position = current_long
    if current_short > max_short_position:
        max_short_position = current_short
    if current_total > max_total_position:
        max_total_position = current_total

def calculate_max_revenue(current_price, dic_item):
    """현재 포트폴리오에서 가장 수익률이 좋은 포지션의 수익률을 반환"""
    max_revenue = float('-inf')
    max_revenue_index = -1
    
    for i, item in enumerate(reversed(dic_item)):
        # original_enter_price가 있으면 사용, 없으면 enter_price 사용 (하위 호환성)
        enter_price = item.get("original_enter_price", item["enter_price"])
        
        # 숏 포지션 수익률: (진입가 - 현재가) / 진입가
        if item["amt"] < 0:
            revenue_rate = (enter_price - current_price) / enter_price
        # 롱 포지션 수익률: (현재가 - 진입가) / 진입가
        else:
            revenue_rate = (current_price - enter_price) / enter_price
        
        if revenue_rate > max_revenue:
            max_revenue = revenue_rate
            max_revenue_index = len(dic_item) - 1 - i
            
    return max_revenue, max_revenue_index

def close_all_positions(current_price):
    """모든 포지션을 청산하는 함수"""
    global dic
    
    if len(dic["item"]) == 0:
        return "청산할 포지션이 없습니다."
    
    total_realized_pnl = 0.0
    closed_positions = []
    
    # 모든 포지션 청산
    for item in dic["item"]:
        # original_enter_price가 있으면 사용, 없으면 enter_price 사용 (하위 호환성)
        enter_price = item.get("original_enter_price", item["enter_price"])
        
        if item["amt"] < 0:  # 숏 포지션 청산
            revenue_rate = (enter_price - current_price) / enter_price
            charge_dollar = current_price * abs(item["amt"]) * FEE_RATE
            my_rate_dollar = (current_price * abs(item["amt"]) * revenue_rate) - charge_dollar
            
            dic["my_money"] += my_rate_dollar
            dic["today"] += my_rate_dollar
            total_realized_pnl += my_rate_dollar
            closed_positions.append(f"숏 {abs(item['amt']):.3f} @ {enter_price:.2f}")
            
        else:  # 롱 포지션 청산
            revenue_rate = (current_price - enter_price) / enter_price
            charge_dollar = current_price * abs(item["amt"]) * FEE_RATE
            my_rate_dollar = (current_price * abs(item["amt"]) * revenue_rate) - charge_dollar
            
            dic["my_money"] += my_rate_dollar
            dic["today"] += my_rate_dollar
            total_realized_pnl += my_rate_dollar
            closed_positions.append(f"롱 {item['amt']:.3f} @ {enter_price:.2f}")
    
    # 포지션 리스트 초기화
    dic["item"] = []
    
    return f"전체 포지션 청산 완료 | PnL: {total_realized_pnl:,.2f}$ | 청산된 포지션: {len(closed_positions)}개"

def execute_order(side, amount, current_price, positionSide, log_prefix=""):
    """가상 주문 실행 및 dic["item"] 업데이트"""
    global GLOBAL_FIRST_AMOUNT
    global dic
    
    split_count = 0.0
    if amount > 0 and GLOBAL_FIRST_AMOUNT > 1e-6:
        split_count = round(amount / GLOBAL_FIRST_AMOUNT, 1) 
        
    log_msg = ""
    
    # 숏 (SELL) 주문
    if side == 'sell' and positionSide == 'SHORT':
        if amount > 0:
            # 진입 시 수수료 차감
            fee = current_price * amount * FEE_RATE
            dic["my_money"] -= fee
            dic["today"] -= fee
            dic["total_fees"] += fee
            
            dic['no'] += 1
            dic["item"].append({'no': dic['no'], 'type': log_prefix, 'enter_price': current_price, 'original_enter_price': current_price, 'amt': round(-amount, 3)})
            log_msg = f"숏 진입 ({log_prefix}): {split_count} 분할"
            
    # 롱 (BUY) 주문
    elif side == 'buy' and positionSide == 'LONG':
        if amount > 0:
            # 진입 시 수수료 차감
            fee = current_price * amount * FEE_RATE
            dic["my_money"] -= fee
            dic["today"] -= fee
            dic["total_fees"] += fee

            dic['no'] += 1
            dic["item"].append({'no': dic['no'], 'type': log_prefix, 'enter_price': current_price, 'original_enter_price': current_price, 'amt': round(amount, 3)})
            log_msg = f"롱 진입 ({log_prefix}): {split_count} 분할"
            
    # 청산 주문 (PnL 계산 및 반영)
    elif (side == 'buy' and positionSide == 'SHORT') or (side == 'sell' and positionSide == 'LONG'):
        
        amt_to_close = amount
        is_short_close = (positionSide == 'SHORT')
        
        remove_indices = []
        realized_pnl_total = 0.0

        for i in range(len(dic["item"]) - 1, -1, -1):
            item = dic["item"][i]
            
            # 숏 포지션 청산 (BUY to CLOSE SHORT)
            if is_short_close and item["amt"] < 0: 
                
                amt_held = abs(item["amt"])
                amt_closed_in_this_step = min(amt_to_close, amt_held)
                
                if amt_closed_in_this_step > 1e-6:
                    # original_enter_price가 있으면 사용, 없으면 enter_price 사용 (하위 호환성)
                    enter_price = item.get("original_enter_price", item["enter_price"])
                    revenue_rate = (enter_price - current_price) / enter_price
                    charge_dollar = current_price * amt_closed_in_this_step * FEE_RATE 
                    dic["total_fees"] += charge_dollar # 청산 수수료 누적
                    my_rate_dollar = (current_price * amt_closed_in_this_step * revenue_rate) - charge_dollar
                    
                    dic["my_money"] += my_rate_dollar
                    dic["today"] += my_rate_dollar
                    realized_pnl_total += my_rate_dollar
                    
                    amt_to_close -= amt_closed_in_this_step
                    
                    if amt_to_close < 1e-6: 
                        dic["item"][i]["amt"] = round(item["amt"] + amt_closed_in_this_step, 3) 
                        if abs(dic["item"][i]["amt"]) < 1e-6:
                            remove_indices.append(i)
                        break
                    else: 
                        remove_indices.append(i)

            # 롱 포지션 청산 (SELL to CLOSE LONG)
            elif not is_short_close and item["amt"] > 0: 

                amt_held = item["amt"]
                amt_closed_in_this_step = min(amt_to_close, amt_held)
                
                if amt_closed_in_this_step > 1e-6:
                    # original_enter_price가 있으면 사용, 없으면 enter_price 사용 (하위 호환성)
                    enter_price = item.get("original_enter_price", item["enter_price"])
                    revenue_rate = (current_price - enter_price) / enter_price
                    charge_dollar = current_price * amt_closed_in_this_step * FEE_RATE
                    dic["total_fees"] += charge_dollar # 청산 수수료 누적
                    my_rate_dollar = (current_price * amt_closed_in_this_step * revenue_rate) - charge_dollar
                    
                    dic["my_money"] += my_rate_dollar
                    dic["today"] += my_rate_dollar
                    realized_pnl_total += my_rate_dollar

                    amt_to_close -= amt_closed_in_this_step
                    
                    if amt_to_close < 1e-6: 
                        dic["item"][i]["amt"] = round(item["amt"] - amt_closed_in_this_step, 3) 
                        if abs(dic["item"][i]["amt"]) < 1e-6:
                            remove_indices.append(i)
                        break
                    else: 
                        remove_indices.append(i)
        
        # 청산된 포지션 제거
        for i in sorted(remove_indices, reverse=True):
            del dic["item"][i]
            
        position_type = "숏" if is_short_close else "롱"
        log_msg = f"{position_type} 청산: PnL {realized_pnl_total:,.2f}$"
    
    return log_msg

def backtest_trading_logic(current_candle, df, first_amount, one_percent_amount, current_divisions, coin_price):
    """
    원본 스크립트의 핵심 거래 로직을 Pandas DataFrame을 사용하여 실행
    """
    global dic
    global GLOBAL_FIRST_AMOUNT
    global position_reset_done
    global current_base_money
    
    # -----------------------------------------------------------
    # 2. 기술 지표 및 변수 설정 (현재 캔들 기준)
    # -----------------------------------------------------------
    
    ma5 = [df['MA_5'].shift(1).loc[current_candle.name], df['MA_5'].shift(2).loc[current_candle.name], df['MA_5'].shift(3).loc[current_candle.name]]
    ma20 = df['MA_20'].shift(1).loc[current_candle.name]
    
    # -----------------------------------------------------------
    # 3. +1% 달성 시 포지션 정리 체크 (잔고 기준)
    # -----------------------------------------------------------
    current_revenue_rate = (dic['my_money'] - current_base_money) / current_base_money * 100
    
    if not position_reset_done and current_revenue_rate >= POSITION_RESET_THRESHOLD:
        if len(dic["item"]) > 0:  # 포지션이 있을 때만 청산
            global position_reset_count
            position_reset_count += 1  # 카운터 증가
            close_log = close_all_positions(coin_price)
            # 새로운 기준점 설정 (포지션 정리 후 잔고)
            current_base_money = dic['my_money']
            position_reset_done = False  # 다음 3% 달성을 위해 다시 False로 설정
            logger.info(f"[{current_candle.name.strftime('%Y-%m-%d %H:%M')}] 🎯 잔고 +{POSITION_RESET_THRESHOLD}% 달성! ({position_reset_count}번째) {close_log}")
            logger.info(f"[{current_candle.name.strftime('%Y-%m-%d %H:%M')}] 💰 새로운 시작 - 잔고: {dic['my_money']:,.2f}$ (기준점: {current_base_money:,.2f}$)")
            return  # 포지션 정리 후 다음 캔들로 

    # -----------------------------------------------------------
    # 5. 포지션이 없을 경우: 초기 진입
    # -----------------------------------------------------------
    if len(dic['item']) == 0:
        
        # 숏 진입 조건
        if ma5[0] > ma20 and ma5[2] < ma5[1] and ma5[1] > ma5[0]:
            log = execute_order('sell', first_amount, coin_price, 'SHORT', 'N')
            if log: 
                # 초기 진입 시: 총 분할 수는 새로 들어간 분할 수와 동일
                total_split = round(first_amount / GLOBAL_FIRST_AMOUNT, 1)
                
                # ❗️ 잔고 및 수익률 추가 (롱: 0.0, 숏: total_split)
                current_revenue_rate = (dic['my_money'] - current_base_money) / current_base_money * 100
                _, equity = calculate_current_pl(coin_price, dic["item"], dic["my_money"])
                position_value = equity - dic['my_money']  # 포지션 가치 (미실현 손익)
                logger.info(f"[{current_candle.name.strftime('%Y-%m-%d %H:%M')}] {log} (롱: 0.0, 숏: {total_split:.1f} / {current_divisions:.1f} 분할) | 잔고: {dic['my_money']:,.2f}$ ({current_revenue_rate:.2f}%) | 포지션포함: {equity:,.2f}$ ({position_value:+,.2f})")


        # 롱 진입 조건
        if ma5[0] < ma20 and ma5[2] > ma5[1] and ma5[1] < ma5[0]:
            log = execute_order('buy', first_amount, coin_price, 'LONG', 'N')
            if log: 
                # 초기 진입 시: 총 분할 수는 새로 들어간 분할 수와 동일
                total_split = round(first_amount / GLOBAL_FIRST_AMOUNT, 1)

                # ❗️ 잔고 및 수익률 추가 (롱: total_split, 숏: 0.0)
                current_revenue_rate = (dic['my_money'] - current_base_money) / current_base_money * 100
                _, equity = calculate_current_pl(coin_price, dic["item"], dic["my_money"])
                position_value = equity - dic['my_money']  # 포지션 가치 (미실현 손익)
                logger.info(f"[{current_candle.name.strftime('%Y-%m-%d %H:%M')}] {log} (롱: {total_split:.1f}, 숏: 0.0 / {current_divisions:.1f} 분할) | 잔고: {dic['my_money']:,.2f}$ ({current_revenue_rate:.2f}%) | 포지션포함: {equity:,.2f}$ ({position_value:+,.2f})")

    # -----------------------------------------------------------
    # 6. 포지션이 있을 경우: 물타기 및 익절
    # -----------------------------------------------------------
    else:
        amt_s2 = 0 
        amt_l2 = 0 
        amount_s = first_amount 
        amount_l = first_amount 
        
        max_revenue, max_revenue_index = calculate_max_revenue(coin_price, dic["item"])
        
        for item in dic["item"]:
            if item["amt"] < 0:
                amt_s2 += abs(item["amt"])
            else:
                amt_l2 += abs(item["amt"])
        
        # ❗️ 롱/숏 분할 수 계산
        if GLOBAL_FIRST_AMOUNT > 1e-6:
            long_split = round(amt_l2 / GLOBAL_FIRST_AMOUNT, 1)
            short_split = round(amt_s2 / GLOBAL_FIRST_AMOUNT, 1)
        else:
            long_split = 0.0
            short_split = 0.0
            
        # C. 포지션 불균형 해소 시 수량 증가 (0.5배)
        # if amt_l2 - amt_s2 < 0 and first_amount * 2 < abs(amt_l2 - amt_s2):
        #     amount_l = round(abs(amt_l2 - amt_s2) * 0.3, 3)
        # elif amt_l2 - amt_s2 > 0 and first_amount * 2 < abs(amt_l2 - amt_s2):
        #     amount_s = round(abs(amt_l2 - amt_s2) * 0.3, 3)


        # D. 물타기 / 추가 진입
        new_entry_made = False
        
        if max_revenue < SAME_POSITION_ADD_ENTRY_RATE: # -0.9% 손실일 경우 (강력 물타기)
            if ma5[2] < ma5[1] and ma5[1] > ma5[0]:
                log = execute_order('sell', amount_s, coin_price, 'SHORT', 'N')
                new_entry_made = True
            
            if ma5[2] > ma5[1] and ma5[1] < ma5[0]:
                log = execute_order('buy', amount_l, coin_price, 'LONG', 'N')
                new_entry_made = True
        
        elif (max_revenue < DIFFERENT_POSITION_ADD_ENTRY_RATE and 
              dic["item"][max_revenue_index]["amt"] < 0 and 
              ma5[2] > ma5[1] and ma5[1] < ma5[0]):
            log = execute_order('buy', amount_l, coin_price, 'LONG', 'N')
            new_entry_made = True

        elif (max_revenue < DIFFERENT_POSITION_ADD_ENTRY_RATE and 
              dic["item"][max_revenue_index]["amt"] > 0 and 
              ma5[2] < ma5[1] and ma5[1] > ma5[0]):
            log = execute_order('sell', amount_s, coin_price, 'SHORT', 'N')
            new_entry_made = True
        
        # ❗️ 물타기/추가 진입 후 로그 출력
        if new_entry_made:
            # 포지션이 변경되었으므로, 롱/숏 분할 수 다시 계산
            new_amt_s2 = sum(abs(item["amt"]) for item in dic["item"] if item["amt"] < 0)
            new_amt_l2 = sum(item["amt"] for item in dic["item"] if item["amt"] > 0)
            
            new_long_split = round(new_amt_l2 / GLOBAL_FIRST_AMOUNT, 1)
            new_short_split = round(new_amt_s2 / GLOBAL_FIRST_AMOUNT, 1)

            # ❗️ 잔고 및 수익률 추가
            current_revenue_rate = (dic['my_money'] - current_base_money) / current_base_money * 100
            _, equity = calculate_current_pl(coin_price, dic["item"], dic["my_money"])
            position_value = equity - dic['my_money']  # 포지션 가치 (미실현 손익)
            logger.info(f"[{current_candle.name.strftime('%Y-%m-%d %H:%M')}] {log} (롱: {new_long_split:.1f}, 숏: {new_short_split:.1f} / {current_divisions:.1f} 분할) | 잔고: {dic['my_money']:,.2f}$ ({current_revenue_rate:.2f}%) | 포지션포함: {equity:,.2f}$ ({position_value:+,.2f})")
            
            
        # E. 익절 (청산)
        else: 
            cap = 0.0
            profit_side = None # 👈 추가: 수익이 발생한 포지션 종류 (예: 'LONG', 'SHORT')
            
            item_indices_to_process = list(range(len(dic["item"]) - 1, -1, -1))

            for i in item_indices_to_process:
                # 항목이 루프 중에 삭제될 수 있으므로 유효한 인덱스인지 확인
                if i >= len(dic["item"]):
                    continue
                
                item = dic["item"][i]
                
                if item["amt"] < 0: # 숏 포지션 익절
                    if ma5[0] < ma20 and ma5[2] > ma5[1] and ma5[1] < ma5[0]: 
                        # 판매조건 확인은 enter_price (평단가) 사용
                        revenue_rate2 = (item["enter_price"] - coin_price) / item["enter_price"]
                        if revenue_rate2 >= TARGET_REVENUE_RATE:
                            
                            # 익절로 얻게 될 예상 수익금 (수수료 차감 전)
                            my_rate_dollar_preview = (coin_price * abs(item["amt"]) * revenue_rate2)
                            
                            log = execute_order('buy', abs(item["amt"]), coin_price, 'SHORT') 
                            if log: 
                                current_revenue_rate = (dic['my_money'] - current_base_money) / current_base_money * 100
                                _, equity = calculate_current_pl(coin_price, dic["item"], dic["my_money"])
                                position_value = equity - dic['my_money']
                                logger.info(f"[{current_candle.name.strftime('%Y-%m-%d %H:%M')}] {log} | 잔고: {dic['my_money']:,.2f}$ ({current_revenue_rate:.2f}%) | 포지션포함: {equity:,.2f}$ ({position_value:+,.2f})")

                            tlen = len(dic["item"])
                            if tlen > 0: # 👈 수정: 1이 아닌 0으로 변경 (청산 후 포지션이 남아있다면)
                                my_rate_dollar = my_rate_dollar_preview  # 전체 수익금
                                # 수익의 50%만 물타기에 사용, 나머지 50%는 실제 수익으로 유지
                                cap += my_rate_dollar * 0.5
                                profit_side = 'SHORT'
                            
                else: # 롱 포지션 익절
                    if ma5[0] > ma20 and ma5[2] < ma5[1] and ma5[1] > ma5[0]: 
                        # 판매조건 확인은 enter_price (평단가) 사용
                        revenue_rate2 = (coin_price - item["enter_price"]) / item["enter_price"]
                        if revenue_rate2 >= TARGET_REVENUE_RATE:
                            
                            # 익절로 얻게 될 예상 수익금 (수수료 차감 전)
                            my_rate_dollar_preview = (coin_price * abs(item["amt"]) * revenue_rate2)

                            log = execute_order('sell', abs(item["amt"]), coin_price, 'LONG')
                            if log: 
                                current_revenue_rate = (dic['my_money'] - current_base_money) / current_base_money * 100
                                _, equity = calculate_current_pl(coin_price, dic["item"], dic["my_money"])
                                position_value = equity - dic['my_money']
                                logger.info(f"[{current_candle.name.strftime('%Y-%m-%d %H:%M')}] {log} | 잔고: {dic['my_money']:,.2f}$ ({current_revenue_rate:.2f}%) | 포지션포함: {equity:,.2f}$ ({position_value:+,.2f})")

                            tlen = len(dic["item"])
                            if tlen > 0: # 👈 수정: 1이 아닌 0으로 변경 (청산 후 포지션이 남아있다면)
                                my_rate_dollar = my_rate_dollar_preview  # 전체 수익금
                                # 수익의 50%만 물타기에 사용, 나머지 50%는 실제 수익으로 유지
                                cap += my_rate_dollar * 0.5
                                profit_side = 'LONG'

            # F. 수익금(cap)을 사용한 평단가 조정 (전체 포지션에 물타기)
            if len(dic["item"]) > 0 and cap > 0.0:
                cap_per_item = cap / len(dic["item"])  # 전체 포지션 수로 나누기
                
                for i, item in enumerate(dic["item"]):
                    if item["amt"] > 0: # 롱 포지션 평단가 하향 조정
                        new_price = ((item["enter_price"] * abs(item["amt"])) - cap_per_item) / abs(item["amt"])
                        dic["item"][i]["enter_price"] = round(new_price, 2)
                        
                    elif item["amt"] < 0: # 숏 포지션 평단가 상향 조정
                        new_price = ((item["enter_price"] * abs(item["amt"])) + cap_per_item) / abs(item["amt"])
                        dic["item"][i]["enter_price"] = round(new_price, 2)
    
def main_backtest():
    """백테스트 메인 함수"""
    
    global GLOBAL_FIRST_AMOUNT
    global position_reset_done
    global current_base_money
    
    # 포지션 정리 상태 및 기준점 초기화
    position_reset_done = False
    current_base_money = INITIAL_MONEY
    
    # 1. 데이터 로드 및 전처리
    logger.info(f"[{CSV_PATH}] 파일을 로드 중입니다...")
    
    df = pd.read_csv(
        CSV_PATH, 
        header=0, 
        index_col='timestamp', 
        parse_dates=True
    ) 
    
    df.index.name = 'Date'
    
    df = df[['open', 'high', 'low', 'close']].copy()
    
    df['MA_5'] = df['close'].rolling(window=5).mean()
    df['MA_20'] = df['close'].rolling(window=20).mean()
    
    df = df.dropna(subset=['MA_20'])
    
    logger.info(f"데이터 로드 완료. 총 {len(df)}개 캔들 테스트 시작.")

    # 2. 거래량 계산 (초기값 설정)
    
    total_money = dic["start_money"] 
    Max_Amount = round(total_money / df['close'].iloc[0] * INVESTMENT_RATIO, 3) * LEVERAGE
    one_percent_amount = Max_Amount / DIVIDE
    first_amount = round((one_percent_amount * 1.0), 3)
    
    # 전역 변수에 기본 1분할 수량 설정
    GLOBAL_FIRST_AMOUNT = first_amount 
    
    current_divisions = DIVIDE / (one_percent_amount / first_amount)

    # 3. 메인 백테스트 루프
    
    equity_list = []

    for index, current_candle in df.iterrows():
        coin_price = current_candle['close']
        
        backtest_trading_logic(
            current_candle, 
            df, 
            first_amount, 
            one_percent_amount, 
            current_divisions, 
            coin_price
        )
        
        # 최대 포지션 수량 업데이트
        update_max_positions()
        
        # 자산 가치 기록
        unrealized_pnl, equity = calculate_current_pl(coin_price, dic["item"], dic["my_money"])
        equity_list.append(equity)
    
    # 4. 결과 출력
    logger.info("\n" + "="*50)
    logger.info("                 ✨ 백테스트 결과 ✨")
    logger.info("="*50)
    
    # 최종 자산 가치 계산
    final_pnl, final_equity = calculate_current_pl(df['close'].iloc[-1], dic["item"], dic["my_money"])
    
    logger.info(f"시작일: {df.index[0]}")
    logger.info(f"종료일: {df.index[-1]}")
    logger.info(f"시작 잔고: {INITIAL_MONEY:,.2f} USDT")
    logger.info(f"최종 보유 현금: {dic['my_money']:,.2f} USDT")
    logger.info(f"누적 거래 수수료: {dic['total_fees']:,.2f} USDT")
    logger.info(f"미실현 손익 (평가손익): {final_pnl:,.2f} USDT")
    logger.info(f"보유 포지션 수: {len(dic['item'])}개")
    logger.info(f"포지션 정리 실행 횟수: {position_reset_count}회")
    logger.info("-" * 50)
    logger.info("📊 최대 포지션 수량 정보:")
    logger.info(f"  최대 롱 포지션: {max_long_position:.3f} BTC")
    logger.info(f"  최대 숏 포지션: {max_short_position:.3f} BTC")
    logger.info(f"  최대 총 포지션: {max_total_position:.3f} BTC")
    logger.info(f"  현재 분할 수량: {GLOBAL_FIRST_AMOUNT:.3f} BTC")
    logger.info(f"  최대 분할 수: {max_total_position / GLOBAL_FIRST_AMOUNT:.1f}개 (현재 설정: {DIVIDE}개)")
    logger.info("-" * 50)
    logger.info(f"최종 자산 (Equity): {final_equity:,.2f} USDT")
    
    total_revenue = final_equity - INITIAL_MONEY
    total_revenue_rate = (total_revenue / INITIAL_MONEY) * 100
    
    logger.info(f"총 수익금: {total_revenue:,.2f} USDT")
    logger.info(f"총 수익률: {total_revenue_rate:.2f}%")
    logger.info("="*50)

if __name__ == "__main__":
    main_backtest()