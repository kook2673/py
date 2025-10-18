import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import ccxt
import time
import datetime as dt
#import pandas as pd
#import pprint

import myBinance
import ende_key  #암복호화키
import my_key    #업비트 시크릿 액세스키
import telegram_sender
import numpy as np
import json
#import talib
import datetime as dt
import gc
import psutil
import warnings

MY_BOT_PATH = "kook"

# 3% 수익 시 포지션 정리를 위한 변수들
POSITION_RESET_THRESHOLD = 3.0  # 3% 달성 시 포지션 정리
position_reset_done = False  # 포지션 정리 완료 여부
current_base_money = 0.0  # 현재 기준점 (포지션 정리 시 업데이트)
position_reset_count = 0  # 포지션 정리 실행 횟수 추적

# ========================= 메모리 관리 유틸리티 =========================
def cleanup_memory():
    """메모리 정리 함수"""
    try:
        # 가비지 컬렉션 강제 실행
        collected = gc.collect()
        
        # 메모리 사용량 확인
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        print(f"메모리 정리 완료: {collected}개 객체 수집, 현재 사용량: {memory_mb:.2f} MB")
        return memory_mb
    except Exception as e:
        print(f"메모리 정리 중 오류: {e}")
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

def calculate_total_position_value(coin_price):
    """포지션 총 가치를 계산하는 함수 (original_enter_price 기준)"""
    total_position_value = 0.0
    for item in dic["item"]:
        # original_enter_price가 없으면 enter_price 사용 (하위 호환성)
        original_price = item.get("original_enter_price", item["enter_price"])
        
        if item["amt"] < 0:  # 숏 포지션
            position_value = (original_price - coin_price) / original_price * abs(item["amt"]) * coin_price
        else:  # 롱 포지션
            position_value = (coin_price - original_price) / original_price * item["amt"] * coin_price
        total_position_value += position_value
    return total_position_value

def close_all_positions(coin_price):
    """모든 포지션을 청산하는 함수"""
    global dic
    
    if len(dic["item"]) == 0:
        return "청산할 포지션이 없습니다."
    
    total_realized_pnl = 0.0
    closed_positions = []
    
    # 모든 포지션 청산
    for item in dic["item"]:
        if item["amt"] < 0:  # 숏 포지션 청산
            revenue_rate = (item["enter_price"] - coin_price) / item["enter_price"]
            charge_dollar = coin_price * abs(item["amt"]) * charge
            my_rate_dollar = (coin_price * abs(item["amt"]) * revenue_rate) - charge_dollar
            
            dic["my_money"] += my_rate_dollar
            dic["today"] += my_rate_dollar
            total_realized_pnl += my_rate_dollar
            closed_positions.append(f"숏 {abs(item['amt']):.3f} @ {item['enter_price']:.2f}")
            
        else:  # 롱 포지션 청산
            revenue_rate = (coin_price - item["enter_price"]) / item["enter_price"]
            charge_dollar = coin_price * abs(item["amt"]) * charge
            my_rate_dollar = (coin_price * abs(item["amt"]) * revenue_rate) - charge_dollar
            
            dic["my_money"] += my_rate_dollar
            dic["today"] += my_rate_dollar
            total_realized_pnl += my_rate_dollar
            closed_positions.append(f"롱 {item['amt']:.3f} @ {item['enter_price']:.2f}")
    
    # 포지션 리스트 초기화
    dic["item"] = []
    
    return f"전체 포지션 청산 완료 | PnL: {total_realized_pnl:,.2f}$ | 청산된 포지션: {len(closed_positions)}개"

def viewlist(msg):
    total_amt = 0
    for item in reversed(dic["item"]):
        revenue_rate = (coin_price - item["enter_price"]) / item["enter_price"] * 100.0
        if item["amt"] < 0:
            revenue_rate = revenue_rate * -1.0
        total_amt += abs(item["amt"])
        msg += "\n"+item["type"]+":"+str(int(item["enter_price"]))+" A:"+str(round(item["amt"], 3))+" 수익:"+str(round(revenue_rate, 1))+"%"
    msg += "\n투자비율 : "+str(round(total_amt/first_amount, 1))+" / "+str(round(current_divisions, 1))
    telegram_sender.SendMessage(msg)

#암복호화 클래스 객체를 미리 생성한 키를 받아 생성한다.
simpleEnDecrypt = myBinance.SimpleEnDecrypt(ende_key.ende_key)
#암호화된 액세스키와 시크릿키를 읽어 복호화 한다.
Binance_AccessKey = simpleEnDecrypt.decrypt(my_key.binance_access)
Binance_ScretKey = simpleEnDecrypt.decrypt(my_key.binance_secret)
# binance 객체 생성
binanceX = ccxt.binance(config={
    'apiKey': Binance_AccessKey, 
    'secret': Binance_ScretKey,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'
    }
})

#나의 코인
Coin_Ticker_List = ['BTC/USDT']#, 'ETH/USDT']
print("\n-- START ------------------------------------------------------------------------------------------\n")

# 초기 메모리 정리
initial_memory = cleanup_memory()

#잔고 데이타 가져오기 
balance = binanceX.fetch_balance(params={"type": "future"})
time.sleep(0.1)
print("balance['USDT'] : ", balance['USDT'])
#print("balance['BNB'] : ", balance['BNB'])
#print("Total Money:",float(balance['USDT']['total']))
#print("Remain Money:",float(balance['USDT']['free']))

dic = dict()
info_file_path = os.path.join(os.path.dirname(__file__), "yang_bot.json")
try:
    #이 부분이 파일을 읽어서 딕셔너리에 넣어주는 로직입니다. 
    with open(info_file_path, 'r') as json_file:
        dic = json.load(json_file)
    
    # JSON에서 3% 수익 시 청산 관련 변수들 읽어오기
    current_base_money = dic.get("current_base_money", dic["my_money"])
    position_reset_done = dic.get("position_reset_done", False)
    position_reset_count = dic.get("position_reset_count", 0)
except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")
    dic["yesterday"] = 0
    dic["today"] = 0
    dic["start_money"] = float(balance['USDT']['total'])
    dic["my_money"] = float(balance['USDT']['total'])
    dic["item"] = []    # 진입가
    dic["no"] = 0       # 거래번호
    
    # 3% 수익 시 청산을 위한 초기화
    current_base_money = float(balance['USDT']['total'])
    position_reset_done = False
    position_reset_count = 0
    
    # JSON에 저장할 변수들 추가
    dic["current_base_money"] = current_base_money
    dic["position_reset_done"] = position_reset_done
    dic["position_reset_count"] = position_reset_count
    with open(info_file_path, 'w') as outfile:
        json.dump(dic, outfile, indent=4, ensure_ascii=False)

print("dic[item] : ", len(dic["item"]))

# UTC 현재 시간 + 9시간(한국 시간)
yesterday = dt.datetime.utcnow() + dt.timedelta(hours=9) - dt.timedelta(days=1)
today = dt.datetime.utcnow() + dt.timedelta(hours=9)
# 24시에 수익금 처리
if today.hour == 0 and today.minute == 0:
    dic["today"] = float(balance['USDT']['total'])-dic["my_money"] #실제 오늘의 수익은 편차가 있어서 보정을 해준다.
    dic["my_money"] = float(balance['USDT']['total'])
    dic["yesterday"] = dic["today"]
    dic["today"] = 0
    with open(info_file_path, 'w') as outfile:
        json.dump(dic, outfile, indent=4, ensure_ascii=False)

for Target_Coin_Ticker in Coin_Ticker_List:
    print("###################################################################################################")
    #거래할 코인 티커와 심볼
    Target_Coin_Symbol = Target_Coin_Ticker.replace("/", "").replace(":USDT", "")
    
    # 메모리 사용량 모니터링
    current_memory = cleanup_memory()
    
    #해당 코인 가격을 가져온다.
    coin_price = myBinance.GetCoinNowPrice(binanceX, Target_Coin_Ticker)
    
    # 3% 수익 시 포지션 정리 체크 (총 자산 기준: 잔고 + 포지션 가치)
    total_position_value = calculate_total_position_value(coin_price)
    total_asset_value = float(balance['USDT']['total']) + abs(total_position_value)
    current_revenue_rate = (total_asset_value - current_base_money) / current_base_money * 100
    
    if not position_reset_done and current_revenue_rate >= POSITION_RESET_THRESHOLD:
        if len(dic["item"]) > 0:  # 포지션이 있을 때만 청산
            position_reset_count += 1  # 카운터 증가
            close_log = close_all_positions(coin_price)
            # 새로운 기준점 설정 (포지션 정리 후 잔고)
            current_base_money = dic['my_money']
            position_reset_done = False  # 다음 3% 달성을 위해 다시 False로 설정
            
            # JSON에 저장
            dic["current_base_money"] = current_base_money
            dic["position_reset_done"] = position_reset_done
            dic["position_reset_count"] = position_reset_count
            msg = f"🎯 +{POSITION_RESET_THRESHOLD}% 달성! ({position_reset_count}번째) {close_log}"
            msg += f"\n💰 새로운 시작 - 잔고: {dic['my_money']:,.2f}$ (기준점: {current_base_money:,.2f}$)"
            msg += f"\n📊 청산 전 총 자산: {total_asset_value:,.2f}$ (잔고: {dic['my_money']:,.2f}$ + 포지션: {total_position_value:,.2f}$)"
            telegram_sender.SendMessage(msg)
            continue  # 포지션 정리 후 다음 코인으로

    # -10% 이상 손실 시 전역 변수 초기화 (총 자산 기준)
    if current_revenue_rate <= -10.0:
        position_reset_done = False
        current_base_money = dic["my_money"]
        position_reset_count = 0
        
        # JSON에 저장
        dic["current_base_money"] = current_base_money
        dic["position_reset_done"] = position_reset_done
        dic["position_reset_count"] = position_reset_count
        
        msg = f"⚠️ -10% 이상 손실로 기준점 초기화 | 현재 수익률: {current_revenue_rate:.2f}% | 새로운 기준점: {current_base_money:,.2f}$"
        msg += f"\n📊 총 자산: {total_asset_value:,.2f}$ (잔고: {dic['my_money']:,.2f}$ + 포지션: {total_position_value:,.2f}$)"
        telegram_sender.SendMessage(msg)

    #변수 셋팅
    leverage = 20 #레버리지 20

    amt_s = 0   #숏 수량 정보
    amt_l = 0   #롱 수량 정보
    #entryPrice_s = 0 #평균 매입 단가. 따라서 물을 타면 변경 된다.
    #entryPrice_l = 0 #평균 매입 단가. 따라서 물을 타면 변경 된다.
    isolated = True #격리모드인지 
    target_revenue_rate = 0.4 #목표 수익율0.32% -> 3.2%정도(레버리지 10배)
    charge = 0.001 #수수료 0.1% (0.001)
    investment_ratio = 1.0 # 투자비율 1이 100%
    same_position_entry_rate = -0.3 # 같은 포지션 추가 진입 비율 -0.5% : 손실 시 같은 방향으로 추가 진입
    divide = 50    # 분할
    #################################################################################################################
    #영상엔 없지만 레버리지를 3으로 셋팅합니다! 
    try:
        print(binanceX.fapiPrivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': leverage}))
    except Exception as e:
        try:
            print(binanceX.fapiprivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': leverage}))
        except Exception as e:
            print("error:", e)
    #################################################################################################################

    #print("==balance : ", balance)
    #숏잔고
    for posi in balance['info']['positions']:
        if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'SHORT':
            #print("==short", posi)
            amt_s = float(posi['positionAmt'])
            # entryPrice가 없으면 현재가를 사용
            #entryPrice_s = float(posi.get('entryPrice', coin_price))
            #leverage = float(posi['leverage'])
            #isolated = posi['isolated']
            break

    #롱잔고
    for posi in balance['info']['positions']:
        if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'LONG':
            #print("==long : ", posi)
            amt_l = float(posi['positionAmt'])
            # entryPrice가 없으면 현재가를 사용
            #entryPrice_l = float(posi.get('entryPrice', coin_price))
            #leverage = float(posi['leverage'])
            #isolated = posi['isolated']
            break
    
    #################################################################################################################
    #교차 모드로 설정
    # if isolated == True:
    #     try:
    #         print(binanceX.fapiprivate_post_margintype({'symbol': Target_Coin_Symbol, 'marginType': 'CROSSED'}))
    #     except Exception as e:
    #         print("Exception:", e)
    #################################################################################################################  
    #################################################################################################################
    #영상엔 없지만 격리모드가 아니라면 격리모드로 처음 포지션 잡기 전에 셋팅해 줍니다,.
    if isolated == False:
       try:
           print(binanceX.fapiPrivate_post_margintype({'symbol': Target_Coin_Symbol, 'marginType': 'ISOLATED'}))
       except Exception as e:
           try:
               print(binanceX.fapiprivate_post_margintype({'symbol': Target_Coin_Symbol, 'marginType': 'ISOLATED'}))
           except Exception as e:
               print("error:", e)
    #################################################################################################################
    #내가 팔아서 아무것도 없을경우 보정해준다.
    if len(dic["item"]) > 0:
        if abs(amt_s) == 0:
            for i in range(len(dic["item"]) - 1, -1, -1):
                if dic["item"][i]["amt"] < 0:
                    del dic["item"][i]
        if abs(amt_l) == 0:
            for i in range(len(dic["item"]) - 1, -1, -1):
                if dic["item"][i]["amt"] > 0:
                    del dic["item"][i]
    
    #캔들 정보 가져온다
    df = myBinance.GetOhlcv(binanceX,Target_Coin_Ticker, '1m')

    #최근 5일선 3개를 가지고 와서 변수에 넣어준다.
    ma5 = [myBinance.GetMA(df, 5, -2), myBinance.GetMA(df, 5, -3), myBinance.GetMA(df, 5, -4)]
    #20일선을 가지고 와서 변수에 넣어준다.
    ma20 = myBinance.GetMA(df, 20, -2)
    
    # 캔들 데이터 처리 후 메모리 정리
    cleanup_dataframes(df)

    #레버리지에 따른 최대 매수 가능 수량
    Max_Amount = round(myBinance.GetAmount(float(balance['USDT']['total']),coin_price,investment_ratio),3) * leverage

    #최대 매수수량의 1%에 해당하는 수량을 구한다.
    one_percent_amount = Max_Amount / divide

    print("one_percent_amount : ", one_percent_amount) 

    #첫 매수 비중을 구한다.. 여기서는 1%!
    first_amount = round((one_percent_amount*1.0)-0.0005, 3)

    #최소 수량 셋팅
    minimun_amount = myBinance.GetMinimumAmount(binanceX, Target_Coin_Ticker)
    if first_amount < minimun_amount:
        first_amount = minimun_amount
    print("first_amount : ", first_amount)

    #print("BNB 최소 구매 갯수 : ", myBinance.GetMinimumAmount(binanceX, "BNB/USDT"))

    # 현재 one_percent_amount에 대한 분할 갯수 계산
    one_percent_divisions = 1 / (one_percent_amount / first_amount)
    # 400분할에 맞춰서 현재 분할 갯수와 비교
    current_divisions = divide / one_percent_divisions
    #print("one_percent_divisions : ", one_percent_divisions)
    #print("current_divisions : ", current_divisions)

    # 한국 시간으로 아침 8시에 해당하는 조건 체크
    if today.hour == 8 and today.minute == 0:
        msg = "\n==========================="
        msg += "\n             바이낸스 양방향봇"
        msg += "\n==========================="
        msg += "\n         "+str(today.month)+"월 "+str(today.day)+"일 수익 결산보고"
        msg += "\n==========================="
        msg += "\n어제 수익 : "+str(round(dic["yesterday"], 2))+" 달러"
        msg += "\n오늘 수익 : "+str(round(dic["today"], 2))+" 달러"
        msg += "\n시작 잔고 : "+str(round(dic["start_money"], 2))+" 달러"
        msg += "\n현재 잔고 : "+str(round(dic["my_money"], 2))+" 달러"
        msg += "\n총 수익금 : "+str(round(dic["my_money"]-dic["start_money"], 2))+" 달러"
        per = (dic["my_money"]-dic["start_money"])/dic["start_money"]*100
        msg += "\n총 수익률 : "+str(round(per, 2))+"%"
        msg += "\n==========================="
        msg += "\n           보유 현황"
        msg += "\n==========================="
        if len(dic["item"]) > 0:
            msg += "\n포지션 : 총 "+ str(len(dic["item"])) + "개"
            viewlist(msg)

    #################################################################################################################    
    #포지션이 없을 경우
    if len(dic['item']) == 0:
        if abs(amt_s) > 0:#값이 있으면 리스트에 추가를 해준다.
            dic['no'] += 1
            dic["item"].append({'no':dic['no'], 'type':'M','enter_price':coin_price,'original_enter_price':coin_price,'amt':round(-(abs(amt_s)), 3)})
            msg = "없는 숏포지션 추가\n현재 가격으로 추가합니다.\n실제 구매하신 가격하고 다를수 있습니다."
            viewlist(msg)
        if abs(amt_l) > 0:#값이 다르면 리스트에 추가를 해준다.
            dic['no'] += 1
            dic["item"].append({'no':dic['no'], 'type':'M','enter_price':coin_price,'original_enter_price':coin_price,'amt':round(amt_l, 3)})
            msg = "없는 롱포지션 추가\n현재 가격으로 추가합니다.\n실제 구매하신 가격하고 다를수 있습니다."
            viewlist(msg)

        #숏포지션 : 5일선이 20일선 위에 있는데 5일선이 하락추세로 꺾였을때 숏 떨어질거야 를 잡는다.
        if ma5[0] > ma20 and ma5[2] < ma5[1] and ma5[1] > ma5[0]:# and rsi14 > 35.0:
            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', first_amount, None, {'positionSide': 'SHORT'})
            buy_price = float(data['average']) #구매가격
            dic['no'] += 1
            dic["item"].append({'no':dic['no'], 'type':'N','enter_price':buy_price,'original_enter_price':buy_price,'amt':round(-first_amount, 3)})
            msg = "\n"+Target_Coin_Symbol+" 숏 포지션 구매11"
            viewlist(msg)
        
        #롱포지션 : 5일선이 20일선 아래에 있는데 5일선이 상승추세로 꺾였을때 롱 오를거야 를 잡는다.
        if ma5[0] < ma20 and ma5[2] > ma5[1] and ma5[1] < ma5[0]:# and rsi14 < 65.0:
            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', first_amount, None, {'positionSide': 'LONG'})
            buy_price = float(data['average']) #구매가격
            dic['no'] += 1
            dic["item"].append({'no':dic['no'], 'type':'N','enter_price':buy_price,'original_enter_price':buy_price,'amt':round(first_amount, 3)})
            msg = "\n"+Target_Coin_Symbol+" 롱 포지션 구매11"
            viewlist(msg)


    #포지션이 있을경우
    else:
        amt_s2 = 0 #숏 총합
        amt_l2 = 0 #롱 총합
        amount_s = first_amount #숏 구매갯수 초기화
        amount_l = first_amount #롱 구매갯수 초기화
    
        max_revenue_index = None  # 수익률이 제일 높은 인덱스를 저장할 변수
        max_revenue = float('-inf')  # 초기 최대 수익률을 음의 무한대로 설정
        for i,item in enumerate(reversed(dic["item"])):
            revenue_rate = (coin_price - item["enter_price"]) / item["enter_price"] * 100.0
            if item["amt"] < 0:
                revenue_rate = revenue_rate * -1.0
                amt_s2 += abs(item["amt"])
            else:
                amt_l2 += abs(item["amt"])

            if revenue_rate > max_revenue:
                max_revenue = revenue_rate
                max_revenue_index = len(dic["item"])-i-1  # 현재 인덱스를 역순으로 계산하여 저장

        if abs(amt_s) > amt_s2 and (abs(amt_s)-amt_s2) >= first_amount:#값이 다르면 리스트에 추가를 해준다.
            dic['no'] += 1
            dic["item"].append({'no':dic['no'],'type':'M','enter_price':coin_price,'original_enter_price':coin_price,'amt':round(-(abs(amt_s)-amt_s2), 3)})
            msg = "없는 숏포지션 추가\n현재 가격으로 추가합니다.\n실제 구매하신 가격하고 다를수 있습니다."
            viewlist(msg)
        if abs(amt_l) > amt_l2 and (abs(amt_l)-amt_l2) >= first_amount:#값이 다르면 리스트에 추가를 해준다.
            dic['no'] += 1
            dic["item"].append({'no':dic['no'],'type':'M','enter_price':coin_price,'original_enter_price':coin_price,'amt':round(amt_l-amt_l2, 3)})
            msg = "없는 롱포지션 추가\n현재 가격으로 추가합니다.\n실제 구매하신 가격하고 다를수 있습니다."
            viewlist(msg)

        # amt = amt_l2 - amt_s2
        # if amt < 0: #숏을 많이 가지고 있다는 얘기
        #     if first_amount*2 < abs(amt):
        #         amount_l = round(abs(amt*2.0)-0.0005, 3)

        # else:#롱을 많이 가지고 있다는 얘기
        #     if first_amount*2 < abs(amt):
        #         amount_s = round(abs(amt*2.0)-0.0005, 3)

        #print("max_revenue_index : ", max_revenue_index)
        #print("max_revenue", max_revenue)
        #print("-target_revenue_rate*2", -target_revenue_rate*2)
        #여기서는 마지막에 있는 포지션이 수익이 나지 않고 멀어졌을경우. 새로운 포지션을 잡는다.
        if max_revenue < same_position_entry_rate:
            #숏포지션 : 5일선이 20일선 위에 있는데 5일선이 하락추세로 꺾였을때 숏 떨어질거야 를 잡는다.
            if ma5[2] < ma5[1] and ma5[1] > ma5[0]:
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', amount_s, None, {'positionSide': 'SHORT'})
                buy_price = float(data['average']) #구매가격
                dic['no'] += 1
                dic["item"].append({'no':dic['no'],'type':'N','enter_price':buy_price,'original_enter_price':buy_price,'amt':round(-amount_s, 3)})
                msg = "\n"+Target_Coin_Symbol+" 숏 포지션 구매22"
                viewlist(msg)
            
            #롱포지션 : 5일선이 20일선 아래에 있는데 5일선이 상승추세로 꺾였을때 롱 오를거야 를 잡는다.
            if ma5[2] > ma5[1] and ma5[1] < ma5[0]:
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', amount_l, None, {'positionSide': 'LONG'})
                buy_price = float(data['average']) #구매가격
                dic['no'] += 1
                dic["item"].append({'no':dic['no'],'type':'N','enter_price':buy_price,'original_enter_price':buy_price,'amt':round(amount_l, 3)})
                msg = "\n"+Target_Coin_Symbol+" 롱 포지션 구매22"
                viewlist(msg)
        
        # 마지막이 숏이고 롱을 사야 하는순간일경우
        elif max_revenue < -target_revenue_rate and dic["item"][max_revenue_index]["amt"] < 0 and ma5[2] > ma5[1] and ma5[1] < ma5[0]:
            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', amount_l, None, {'positionSide': 'LONG'})
            buy_price = float(data['average']) #구매가격
            dic['no'] += 1
            dic["item"].append({'no':dic['no'],'type':'N','enter_price':buy_price,'original_enter_price':buy_price,'amt':round(amount_l, 3)})
            msg = "\n"+Target_Coin_Symbol+" 롱 포지션 구매33"
            viewlist(msg)

        # 마지막이 롱이고 숏을 사야 하는 순간
        elif max_revenue < -target_revenue_rate and dic["item"][max_revenue_index]["amt"] > 0 and ma5[2] < ma5[1] and ma5[1] > ma5[0]:
            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', amount_s, None, {'positionSide': 'SHORT'})
            buy_price = float(data['average']) #구매가격
            dic['no'] += 1
            dic["item"].append({'no':dic['no'],'type':'N','enter_price':buy_price,'original_enter_price':buy_price,'amt':round(-amount_s, 3)})
            msg = "\n"+Target_Coin_Symbol+" 숏 포지션 구매33"
            viewlist(msg)

        else: # 수익이 났는지 확인한다.
            cap = 0.0
            isbuy = None
            msg = ""
            remove = [] #삭제할 인덱스값 저장

            for i,item in enumerate(reversed(dic["item"])):
                if item["amt"] < 0: #숏포지션
                    if ma5[0] < ma20 and ma5[2] > ma5[1] and ma5[1] < ma5[0]:
                        revenue_rate2 = (item["enter_price"] - coin_price) / item["enter_price"] * 100.0
                        if revenue_rate2 >= target_revenue_rate:
                            #숏 포지션 시장가 판매!
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', round(abs(item["amt"]), 3), None, {'positionSide': 'SHORT'})
                            sell_price = float(data['average']) #판매가격
                            charge_dollar = sell_price*abs(item["amt"])*charge #수수료
                            my_rate_dollar = (sell_price*abs(item["amt"])*revenue_rate2*0.01)-charge_dollar#수익률 계산
                            isbuy = "long"

                            remove.append(len(dic["item"])-i-1)
                            tlen = len(dic["item"])
                            if tlen > 1:
                                my_rate_dollar = my_rate_dollar / 2
                                cap += my_rate_dollar

                            dic["today"] += my_rate_dollar
                            msg += "\n"+Target_Coin_Symbol+" 숏 포지션 판매"
                            msg += "\n"+item["type"]+":"+str(round(sell_price, 1))+" 수량:"+str(round(item["amt"], 3))+" 수익:"+str(round(my_rate_dollar, 2))+"$"                          

                else: #롱포지션
                    if ma5[0] > ma20 and ma5[2] < ma5[1] and ma5[1] > ma5[0]:
                        revenue_rate2 = (coin_price - item["enter_price"]) / item["enter_price"] * 100.0
                        if revenue_rate2 >= target_revenue_rate:
                            #롱 포지션 시장가 판매!
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', round(abs(item["amt"]), 3), None, {'positionSide': 'LONG'})
                            sell_price = float(data['average']) #판매가격
                            charge_dollar = sell_price*abs(item["amt"])*charge #수수료
                            my_rate_dollar = (sell_price*abs(item["amt"])*revenue_rate2*0.01)-charge_dollar#수익률 계산
                            isbuy = "short"

                            remove.append(len(dic["item"])-i-1)
                            tlen = len(dic["item"])
                            if tlen > 1:
                                my_rate_dollar = my_rate_dollar / 2
                                cap += my_rate_dollar

                            dic["today"] += my_rate_dollar
                            msg += "\n"+Target_Coin_Symbol+" 롱 포지션 판매"
                            msg += "\n"+item["type"]+":"+str(round(sell_price, 1))+" 수량:"+str(round(item["amt"], 3))+" 수익:"+str(round(my_rate_dollar, 2))+"$"

            if cap > 0.0:
                msg += "\n오늘의수익 : "+str(round(dic["today"], 2))+"$"
                #telegram_sender.SendMessage(msg)           

            # 인덱스를 역순으로 정렬하여 리스트에서 삭제
            #if len(remove) > 1:
            #    telegram_sender.SendMessage(str(remove))
            for index in remove:
                del dic["item"][index]

            #수익이 난 상태면 cap만큼 다른값들을 조정해준다.
            '''
            if len(dic["item"]) > 0 and cap > 0.0:
                total_amt = 0
                for item in dic["item"]:
                    total_amt += abs(item['amt'])
                total_amt *= 1000 #최소단위가 0.001이기 때문에 1000을 곱해줘서 0.001개가 1개가 되도록 해준다.
                
                cap = cap/total_amt#len(dic["item"]) #구해진 cap를 토탈총갯수만큼 분할한다음에
                #print("22 cap : ", cap)
                for item in dic["item"]:
                    item["enter_price"] = round(((item["enter_price"]*abs(item["amt"]))-(cap*item['amt']*1000))/abs(item["amt"]), 2)
            '''
            if len(dic["item"]) > 0 and cap > 0.0:
                cap = cap/len(dic["item"]) #구해진 cap를 토탈총갯수만큼 분할한다음에
                for i, item in enumerate(dic["item"]):
                    if item["amt"] > 0:
                        dic["item"][i]["enter_price"] = round(((item["enter_price"]*abs(item["amt"]))-cap)/abs(item["amt"]), 2)
                        # original_enter_price는 변경하지 않음
                    else:
                        dic["item"][i]["enter_price"] = round(((item["enter_price"]*abs(item["amt"]))+cap)/abs(item["amt"]), 2)
                        # original_enter_price는 변경하지 않음

            if isbuy != None:
                if len(dic["item"])>0:
                    max_revenue_index = None  # 수익률이 제일 높은 인덱스를 저장할 변수
                    max_revenue = float('-inf')  # 초기 최대 수익률을 음의 무한대로 설정
                    for i,item in enumerate(reversed(dic["item"])):
                        revenue_rate = (coin_price - item["enter_price"]) / item["enter_price"] * 100.0
                        if item["amt"] < 0:
                            revenue_rate = revenue_rate * -1.0
                        if revenue_rate > max_revenue:
                            max_revenue = revenue_rate
                            max_revenue_index = len(dic["item"])-i-1  # 현재 인덱스를 역순으로 계산하여 저장

                    target_revenue_rate2 = None
                    if isbuy == "short" and item["amt"] < 0:
                        target_revenue_rate2 = -(target_revenue_rate*3)
                    else:
                        target_revenue_rate2 = -target_revenue_rate
                    if max_revenue >= target_revenue_rate2:
                        isbuy = None
                        viewlist(msg)
                    
                if isbuy == "short":
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', amount_s, None, {'positionSide': 'SHORT'})
                    buy_price = float(data['average']) #구매가격
                    dic['no'] += 1
                    dic["item"].append({'no':dic['no'], 'type':'N','enter_price':buy_price,'original_enter_price':buy_price,'amt':round(-amount_s, 3)})
                    msg += "\n"+Target_Coin_Symbol+" 숏 포지션 구매44"
                    #msg += "\n가격:"+str(round(buy_price, 1))+" 수량:"+str(round(first_amount, 3))
                    #telegram_sender.SendMessage(msg)
                    viewlist(msg)
                
                elif isbuy == "long":
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', amount_l, None, {'positionSide': 'LONG'})
                    buy_price = float(data['average']) #구매가격
                    dic['no'] += 1
                    dic["item"].append({'no':dic['no'], 'type':'N','enter_price':buy_price,'original_enter_price':buy_price,'amt':round(amount_l, 3)})
                    msg += "\n"+Target_Coin_Symbol+" 롱 포지션 구매44"
                    #msg += "\n가격:"+str(round(buy_price, 1))+" 수량:"+str(round(first_amount, 3))
                    #telegram_sender.SendMessage(msg)
                    viewlist(msg)

    print("\n-- END --------------------------------------------------------------------------------------------\n")
    
    # 루프 종료 시 메모리 정리
    cleanup_memory()
    
    # 3% 수익 시 청산 관련 변수들 JSON에 저장
    dic["current_base_money"] = current_base_money
    dic["position_reset_done"] = position_reset_done
    dic["position_reset_count"] = position_reset_count
    
    with open(info_file_path, 'w') as outfile:
        json.dump(dic, outfile, indent=4, ensure_ascii=False)

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

print(f"=== Yang Bot 종료 (최종 메모리: {final_memory:.2f} MB) ===")