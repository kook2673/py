import pandas as pd
import numpy as np
import datetime as dt
import json
import os

# ----------------------------------------------------------------------
# 1. 백테스트 설정
# ----------------------------------------------------------------------

# 백테스트에 사용할 CSV 파일 경로 (사용자 지정 경로)
CSV_PATH = r"C:\work\GitHub\py\kook\binance_test\data\BTCUSDT\1m\BTCUSDT_1m_2021.csv"
Target_Coin_Ticker = 'BTC/USDT'
Target_Coin_Symbol = 'BTCUSDT'

# 초기 자본 및 전략 변수
INITIAL_MONEY = 10000.0   # 시작 잔고 (USDT)
leverage = 10             # 레버리지 10배로 가정
target_revenue_rate = 0.4 # 목표 수익률 0.3%
same_position_enter = -0.5 # 동일 포지션 진입 목표 수익률 1.0%
charge = 0.05             # 편도 수수료 (0.05%)
investment_ratio = 0.5    # 투자비율 50%로 가정
divide = 200              # 분할
FEE_RATE = charge * 0.01  # 수수료율 (0.0005)

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
}

# ❗️ 추가 변수: 기본 1분할 수량을 전역으로 설정하여 execute_order에서 사용
GLOBAL_FIRST_AMOUNT = 0.0 

def calculate_current_pl(current_price, dic_item, total_money):
    """현재 포트폴리오의 미실현 손익(PnL)과 총 가치(Equity)를 계산"""
    total_unrealized_pnl = 0.0
    
    for item in dic_item:
        if item["amt"] < 0:  # 숏 포지션
            pnl = (item["price"] - current_price) * abs(item["amt"])
        else:  # 롱 포지션
            pnl = (current_price - item["price"]) * abs(item["amt"])
            
        total_unrealized_pnl += pnl
        
    return total_unrealized_pnl, total_money + total_unrealized_pnl

def calculate_max_revenue(current_price, dic_item):
    """현재 포트폴리오에서 가장 수익률이 좋은 포지션의 수익률을 반환"""
    max_revenue = float('-inf')
    max_revenue_index = -1
    
    for i, item in enumerate(reversed(dic_item)):
        # 숏 포지션 수익률: (진입가 - 현재가) / 진입가 * 100
        if item["amt"] < 0:
            revenue_rate = (item["price"] - current_price) / item["price"] * 100.0
        # 롱 포지션 수익률: (현재가 - 진입가) / 진입가 * 100
        else:
            revenue_rate = (current_price - item["price"]) / item["price"] * 100.0
        
        if revenue_rate > max_revenue:
            max_revenue = revenue_rate
            max_revenue_index = len(dic_item) - 1 - i
            
    return max_revenue, max_revenue_index

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
            
            dic['no'] += 1
            dic["item"].append({'no': dic['no'], 'type': log_prefix, 'price': current_price, 'amt': round(-amount, 3)})
            log_msg = f"숏 진입 ({log_prefix}): {split_count} 분할"
            
    # 롱 (BUY) 주문
    elif side == 'buy' and positionSide == 'LONG':
        if amount > 0:
            # 진입 시 수수료 차감
            fee = current_price * amount * FEE_RATE
            dic["my_money"] -= fee
            dic["today"] -= fee

            dic['no'] += 1
            dic["item"].append({'no': dic['no'], 'type': log_prefix, 'price': current_price, 'amt': round(amount, 3)})
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
                    revenue_rate = (item["price"] - current_price) / item["price"] * 100.0
                    charge_dollar = current_price * amt_closed_in_this_step * FEE_RATE 
                    my_rate_dollar = (current_price * amt_closed_in_this_step * revenue_rate * 0.01) - charge_dollar
                    
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
                    revenue_rate = (current_price - item["price"]) / item["price"] * 100.0
                    charge_dollar = current_price * amt_closed_in_this_step * FEE_RATE
                    my_rate_dollar = (current_price * amt_closed_in_this_step * revenue_rate * 0.01) - charge_dollar
                    
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
    
    # -----------------------------------------------------------
    # 2. 기술 지표 및 변수 설정 (현재 캔들 기준)
    # -----------------------------------------------------------
    
    ma5 = [df['MA_5'].shift(1).loc[current_candle.name], df['MA_5'].shift(2).loc[current_candle.name], df['MA_5'].shift(3).loc[current_candle.name]]
    ma20 = df['MA_20'].shift(1).loc[current_candle.name] 

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
                current_revenue_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100
                _, equity = calculate_current_pl(coin_price, dic["item"], dic["my_money"])
                print(f"[{current_candle.name.strftime('%Y-%m-%d %H:%M')}] {log} (롱: 0.0, 숏: {total_split:.1f} / {current_divisions:.1f} 분할) | 잔고: {dic['my_money']:,.2f}$ ({current_revenue_rate:.2f}%) | 포지션포함: {equity:,.2f}$")


        # 롱 진입 조건
        if ma5[0] < ma20 and ma5[2] > ma5[1] and ma5[1] < ma5[0]:
            log = execute_order('buy', first_amount, coin_price, 'LONG', 'N')
            if log: 
                # 초기 진입 시: 총 분할 수는 새로 들어간 분할 수와 동일
                total_split = round(first_amount / GLOBAL_FIRST_AMOUNT, 1)

                # ❗️ 잔고 및 수익률 추가 (롱: total_split, 숏: 0.0)
                current_revenue_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100
                _, equity = calculate_current_pl(coin_price, dic["item"], dic["my_money"])
                print(f"[{current_candle.name.strftime('%Y-%m-%d %H:%M')}] {log} (롱: {total_split:.1f}, 숏: 0.0 / {current_divisions:.1f} 분할) | 잔고: {dic['my_money']:,.2f}$ ({current_revenue_rate:.2f}%) | 포지션포함: {equity:,.2f}$")

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
        #     amount_l = round(abs(amt_l2 - amt_s2) * 0.5, 3)
        # elif amt_l2 - amt_s2 > 0 and first_amount * 2 < abs(amt_l2 - amt_s2):
        #     amount_s = first_amount*2#round(abs(amt_l2 - amt_s2) * 0.5, 3)


        # D. 물타기 / 추가 진입
        new_entry_made = False
        
        if max_revenue < same_position_enter: # -0.9% 손실일 경우 (강력 물타기)
            if ma5[2] < ma5[1] and ma5[1] > ma5[0]:
                log = execute_order('sell', amount_s, coin_price, 'SHORT', 'N')
                new_entry_made = True
            
            if ma5[2] > ma5[1] and ma5[1] < ma5[0]:
                log = execute_order('buy', amount_l, coin_price, 'LONG', 'N')
                new_entry_made = True
        
        elif (max_revenue < -target_revenue_rate and 
              dic["item"][max_revenue_index]["amt"] < 0 and 
              ma5[2] > ma5[1] and ma5[1] < ma5[0]):
            log = execute_order('buy', amount_l, coin_price, 'LONG', 'N')
            new_entry_made = True

        elif (max_revenue < -target_revenue_rate and 
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
            current_revenue_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100
            _, equity = calculate_current_pl(coin_price, dic["item"], dic["my_money"])
            print(f"[{current_candle.name.strftime('%Y-%m-%d %H:%M')}] {log} (롱: {new_long_split:.1f}, 숏: {new_short_split:.1f} / {current_divisions:.1f} 분할) | 잔고: {dic['my_money']:,.2f}$ ({current_revenue_rate:.2f}%) | 포지션포함: {equity:,.2f}$")
            
            
        # E. 익절 (청산)
        else: 
            cap = 0.0
            profit_side = None # 👈 추가: 수익이 발생한 포지션 종류 (예: 'LONG', 'SHORT')
            
            for i in range(len(dic["item"]) - 1, -1, -1):
                item = dic["item"][i]
                
                if item["amt"] < 0: # 숏 포지션 익절
                    if ma5[0] < ma20 and ma5[2] > ma5[1] and ma5[1] < ma5[0]: 
                        revenue_rate2 = (item["price"] - coin_price) / item["price"] * 100.0
                        if revenue_rate2 >= target_revenue_rate:
                            log = execute_order('buy', abs(item["amt"]), coin_price, 'SHORT') 
                            if log: 
                                # ❗️ 잔고 및 수익률 추가
                                current_revenue_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100
                                _, equity = calculate_current_pl(coin_price, dic["item"], dic["my_money"])
                                print(f"[{current_candle.name.strftime('%Y-%m-%d %H:%M')}] {log} | 잔고: {dic['my_money']:,.2f}$ ({current_revenue_rate:.2f}%) | 포지션포함: {equity:,.2f}$")


                            charge_dollar = coin_price * abs(item["amt"]) * FEE_RATE
                            my_rate_dollar = (coin_price * abs(item["amt"]) * revenue_rate2 * 0.01) - charge_dollar
                            
                            tlen = len(dic["item"])
                            if tlen > 1:
                                my_rate_dollar = my_rate_dollar / 2
                                cap += my_rate_dollar
                                profit_side = 'SHORT' # 👈 수정: 숏 포지션에서 수익 발생 기록
                            
                else: # 롱 포지션 익절
                    if ma5[0] > ma20 and ma5[2] < ma5[1] and ma5[1] > ma5[0]: 
                        revenue_rate2 = (coin_price - item["price"]) / item["price"] * 100.0
                        if revenue_rate2 >= target_revenue_rate:
                            log = execute_order('sell', abs(item["amt"]), coin_price, 'LONG')
                            if log: 
                                # ❗️ 잔고 및 수익률 추가
                                current_revenue_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100
                                _, equity = calculate_current_pl(coin_price, dic["item"], dic["my_money"])
                                print(f"[{current_candle.name.strftime('%Y-%m-%d %H:%M')}] {log} | 잔고: {dic['my_money']:,.2f}$ ({current_revenue_rate:.2f}%) | 포지션포함: {equity:,.2f}$")

                            charge_dollar = coin_price * abs(item["amt"]) * FEE_RATE
                            my_rate_dollar = (coin_price * abs(item["amt"]) * revenue_rate2 * 0.01) - charge_dollar
                            
                            tlen = len(dic["item"])
                            if tlen > 1:
                                my_rate_dollar = my_rate_dollar / 2
                                cap += my_rate_dollar
                                profit_side = 'LONG' # 👈 수정: 롱 포지션에서 수익 발생 기록

            # F. 수익금(cap)을 사용한 평단가 조정
            if len(dic["item"]) > 0 and cap > 0.0:
                # 조정 대상 인덱스를 미리 수집합니다.
                target_indices = []
                if profit_side == 'SHORT':
                    # 숏 익절 -> 롱 포지션(amt > 0) 조정
                    target_indices = [i for i, item in enumerate(dic["item"]) if item["amt"] > 0]
                elif profit_side == 'LONG':
                    # 롱 익절 -> 숏 포지션(amt < 0) 조정
                    target_indices = [i for i, item in enumerate(dic["item"]) if item["amt"] < 0]

                if len(target_indices) > 0:
                    cap_per_item = cap / len(target_indices)
                    
                    for i in target_indices:
                        item = dic["item"][i]
                        
                        if item["amt"] > 0: # 롱 포지션 평단가 하향 조정
                            # 새로운 평단가 = ((기존 평단가 * 수량) - 수익금) / 수량
                            new_price = ((item["price"] * abs(item["amt"])) - cap_per_item) / abs(item["amt"])
                            dic["item"][i]["price"] = round(new_price, 2)
                            
                        elif item["amt"] < 0: # 숏 포지션 평단가 상향 조정 (진입 가격이 올라가야 수익을 내기 쉬워짐)
                            # 새로운 평단가 = ((기존 평단가 * 수량) + 수익금) / 수량
                            new_price = ((item["price"] * abs(item["amt"])) + cap_per_item) / abs(item["amt"])
                            dic["item"][i]["price"] = round(new_price, 2)
    
def main_backtest():
    """백테스트 메인 함수"""
    
    global GLOBAL_FIRST_AMOUNT
    
    # 1. 데이터 로드 및 전처리
    print(f"[{CSV_PATH}] 파일을 로드 중입니다...")
    
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
    
    print(f"데이터 로드 완료. 총 {len(df)}개 캔들 테스트 시작.")

    # 2. 거래량 계산 (초기값 설정)
    
    total_money = dic["start_money"] 
    Max_Amount = round(total_money / df['close'].iloc[0] * investment_ratio, 3) * leverage
    one_percent_amount = Max_Amount / divide
    first_amount = round((one_percent_amount * 1.0), 3)
    
    # 전역 변수에 기본 1분할 수량 설정
    GLOBAL_FIRST_AMOUNT = first_amount 
    
    current_divisions = divide / (one_percent_amount / first_amount)

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
        
        # 자산 가치 기록
        unrealized_pnl, equity = calculate_current_pl(coin_price, dic["item"], dic["my_money"])
        equity_list.append(equity)
    
    # 4. 결과 출력
    print("\n" + "="*50)
    print("                 ✨ 백테스트 결과 ✨")
    print("="*50)
    
    # 최종 자산 가치 계산
    final_pnl, final_equity = calculate_current_pl(df['close'].iloc[-1], dic["item"], dic["my_money"])
    
    print(f"시작일: {df.index[0]}")
    print(f"종료일: {df.index[-1]}")
    print(f"시작 잔고: {INITIAL_MONEY:,.2f} USDT")
    print(f"최종 청산 잔고: {final_equity:,.2f} USDT")
    
    total_revenue = final_equity - INITIAL_MONEY
    total_revenue_rate = (total_revenue / INITIAL_MONEY) * 100
    
    print(f"총 수익금: {total_revenue:,.2f} USDT")
    print(f"총 수익률: {total_revenue_rate:.2f}%")
    print("="*50)

if __name__ == "__main__":
    main_backtest()