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
import line_alert
import numpy as np
import json
#import talib
import datetime as dt

MY_BOT_PATH = "kook"

def viewlist(msg):
    total_amt = 0
    for item in reversed(dic["item"]):
        revenue_rate = (coin_price - item["price"]) / item["price"] * 100.0
        if item["amt"] < 0:
            revenue_rate = revenue_rate * -1.0
        total_amt += abs(item["amt"])
        msg += "\n"+item["type"]+":"+str(int(item["price"]))+" A:"+str(round(item["amt"], 3))+" 수익:"+str(round(revenue_rate, 1))+"%"
    msg += "\n투자비율 : "+str(round(total_amt/first_amount, 1))+" / "+str(round(current_divisions, 1))
    line_alert.SendMessage(msg)

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

line_alert.SendMessage("test")

#나의 코인
Coin_Ticker_List = ['BTC/USDT']#, 'ETH/USDT']
print("\n-- START ------------------------------------------------------------------------------------------\n")
#잔고 데이타 가져오기 
balance = binanceX.fetch_balance(params={"type": "future"})
time.sleep(0.1)
print("balance['USDT'] : ", balance['USDT'])
#print("balance['BNB'] : ", balance['BNB'])
#print("Total Money:",float(balance['USDT']['total']))
#print("Remain Money:",float(balance['USDT']['free']))

dic = dict()
info_file_path = "/var/autobot/"+MY_BOT_PATH+"/binance_yang_bot7.json"
try:
    #이 부분이 파일을 읽어서 딕셔너리에 넣어주는 로직입니다. 
    with open(info_file_path, 'r') as json_file:
        dic = json.load(json_file)
except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")
    dic["yesterday"] = 0
    dic["today"] = 0
    dic["start_money"] = float(balance['USDT']['total'])
    dic["my_money"] = float(balance['USDT']['total'])
    dic["item"] = []    # 진입가
    dic["event"] = []   # 이벤트발생(하락or상승)
    dic["no"] = 0       # 거래번호
    with open(info_file_path, 'w') as outfile:
        json.dump(dic, outfile)

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
        json.dump(dic, outfile)

for Target_Coin_Ticker in Coin_Ticker_List:
    print("###################################################################################################")
    #거래할 코인 티커와 심볼
    Target_Coin_Symbol = Target_Coin_Ticker.replace("/", "").replace(":USDT", "")

    #변수 셋팅
    leverage = 40 #레버리지 10

    amt_s = 0   #숏 수량 정보
    amt_l = 0   #롱 수량 정보
    entryPrice_s = 0 #평균 매입 단가. 따라서 물을 타면 변경 된다.
    entryPrice_l = 0 #평균 매입 단가. 따라서 물을 타면 변경 된다.
    isolated = True #격리모드인지 
    target_revenue_rate = 0.3 #목표 수익율0.32% -> 3.2%정도(레버리지 10배)
    charge = 0.08 #수수료 살때 0.04%, 팔때 0.04%
    investment_ratio = 1 # 투자비율 1이 100%
    water_rate = -0.3 # 물타는 비율 0.3% -> 0.9%(레버리지 3배) : 마지막 수량에 대한 물타기
    divide = 400    # 분할
    #water_rate_add = -0.2 #0.2%씩 증가
    #revenue_rate_s = 0
    #revenue_rate_l = 0

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

    #숏잔고
    for posi in balance['info']['positions']:
        if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'SHORT':
            #print("==short", posi)
            amt_s = float(posi['positionAmt'])
            entryPrice_s= float(posi['entryPrice'])
            leverage = float(posi['leverage'])
            isolated = posi['isolated']
            break

    #롱잔고
    for posi in balance['info']['positions']:
        if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'LONG':
            #print("==long : ", posi)
            amt_l = float(posi['positionAmt'])
            entryPrice_l = float(posi['entryPrice'])
            leverage = float(posi['leverage'])
            isolated = posi['isolated']
            break
    
    #################################################################################################################
    #교차 모드로 설정
    if isolated == True:
        try:
            print(binanceX.fapiprivate_post_margintype({'symbol': Target_Coin_Symbol, 'marginType': 'CROSSED'}))
        except Exception as e:
            print("Exception:", e)
    #################################################################################################################  
    #################################################################################################################
    #영상엔 없지만 격리모드가 아니라면 격리모드로 처음 포지션 잡기 전에 셋팅해 줍니다,.
    #if isolated == False:
    #    try:
    #        print(binanceX.fapiPrivate_post_margintype({'symbol': Target_Coin_Symbol, 'marginType': 'ISOLATED'}))
    #    except Exception as e:
    #        try:
    #            print(binanceX.fapiprivate_post_margintype({'symbol': Target_Coin_Symbol, 'marginType': 'ISOLATED'}))
    #        except Exception as e:
    #            print("error:", e)
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
    
    '''
    time.sleep(0.1)
    df_1d = myBinance.GetOhlcv(binanceX,Target_Coin_Ticker, '1d')
    ma50 = [myBinance.GetMA(df_1d, 50, -1), myBinance.GetMA(df_1d, 50, -2)]
    '''
    df_1h = myBinance.GetOhlcv(binanceX,Target_Coin_Ticker, '1h')
    time.sleep(0.1)   
    #캔들 정보 가져온다
    df = myBinance.GetOhlcv(binanceX,Target_Coin_Ticker, '1m')

    #최근 5일선 3개를 가지고 와서 변수에 넣어준다.
    ma5 = [myBinance.GetMA(df, 5, -2), myBinance.GetMA(df, 5, -3), myBinance.GetMA(df, 5, -4)]
    #20일선을 가지고 와서 변수에 넣어준다.
    ma20 = myBinance.GetMA(df, 20, -2)
    #RSI14 정보를 가지고 온다.
    #rsi14 = myBinance.GetRSI(df, 14, -1)

    # 변동성 체크.
    #df['Log_Return'] = np.log(df['close'] / df['close'].shift(1))
    #df['volatility'] = round((df['Log_Return'].rolling(window=20).std()*np.sqrt(20))*100, 2)

    '''
    # HMA를 계산할 다양한 윈도우 크기 정의
    hma_windows = [5, 10, 20, 60, 200]
    # 각 윈도우 크기에 대해 HMA 계산 및 DataFrame에 추가
    for window in hma_windows:
        hma_values = hma(df_1d['close'].values, window)
        df_1d[f"hma_{window}"] = hma_values
        #print(df_1d["hma_"+str(window)])
    '''

    #해당 코인 가격을 가져온다.
    coin_price = myBinance.GetCoinNowPrice(binanceX, Target_Coin_Ticker)

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
        msg += "\n             바이낸스 양방향봇7"
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

    '''
    if today.minute == 3: #한시간마다 체크한다.
        msg2 = "BNB코인 구매 실행"
        time.sleep(0.05)
        # 수수료에 대해서 BNB코인이 별로 없으면 구매를 한다.
        #BNB의 현재 가격을 가져와야 한다. 매번 체크하지 않고 1시간마다 체크한다.
        bnb_amt = float(balance['BNB']['total']) #bnb_amt갯수를 가져온다.
        print("BNB : ", bnb_amt)
        bnb_price = float(myBinance.GetCoinNowPrice(binanceX, "BNB/USDT"))
        fee_cost = coin_price*first_amount*charge*0.01  # 수수료 가격
        # 수수료 가격의 50배와 20배를 계산
        fee_cost_max = fee_cost*30
        fee_cost_min = fee_cost*10
        time.sleep(0.05)

        # 필요한 USDT를 계산 (110% 여유 포함)
        amount_to_transfer = (fee_cost_max - bnb_amt * bnb_price) / bnb_price * 1.10
        amount_to_transfer = round(amount_to_transfer, 2)  # 소수점 2자리로 반올림
        print("Amount to transfer (USDT):", amount_to_transfer)

        # BNB 잔액이 부족할 경우 구매
        if bnb_amt * bnb_price < fee_cost_min:
            msg2 += "\n잔액부족으로 진입"
            # 선물 계정에서 현물 계정으로 USDT 전송
            try:
                transfer_response = binanceX.sapi_post_asset_convert_transfer({
                    'fromAsset': 'USDT',
                    'toAsset': 'BNB',
                    'amount': amount_to_transfer,
                    'type': 2  # 1: from spot to futures, 2: from futures to spot
                })
                print(f"Transfer response: {transfer_response}")
                msg2 += f"\nTransfer response: {transfer_response}"

                # 바이낸스 인스턴스 생성
                binanceBNB = ccxt.binance({
                    'apiKey': Binance_AccessKey, 
                    'secret': Binance_ScretKey,
                    'enableRateLimit': True,
                })
                
                # 현물 계정 잔고 업데이트 (전송 후 약간의 대기 시간 필요)
                time.sleep(5)
                balance = binanceBNB.fetch_balance()
                usdt_balance = float(balance['total']['USDT'])
                print("USDT balance after transfer:", usdt_balance)
                msg2 += f"\nUSDT balance after transfer: {usdt_balance}"

                # USDT 잔액이 충분한지 확인
                required_usdt = amount_to_transfer * bnb_price
                if usdt_balance < required_usdt:
                    print(f"Insufficient USDT balance. Required: {required_usdt}, Available: {usdt_balance}")
                else:
                    # BNB 구매 명령 실행
                    amount_to_buy = round((fee_cost_max - bnb_amt * bnb_price) / bnb_price, 3)
                    print("Amount to buy (BNB):", amount_to_buy)
                    msg2 += "\nBNB 구매 명령 실행 : "+str(amount_to_buy)
                    minimun_amount = 0.01
                    if amount_to_buy < minimun_amount:  # 최소 구매갯수가 0.01개이다.
                        amount_to_buy = minimun_amount
                    try:
                        data = binanceBNB.create_order("BNBUSDT", 'market', 'buy', amount_to_buy)
                        buy_price = float(data['average'])  # 구매 가격
                        msg2 = f"BNB 코인을 구매했습니다.\n가격: {buy_price} 수량: {amount_to_buy}"
                        print(msg)  # 메시지를 출력 (또는 다른 방법으로 알림)
                    except ccxt.BaseError as e:
                        msg2 = f"An error occurred during purchase: {e}"
                        print(msg)
            except ccxt.BaseError as e:
                print(f"An error occurred during transfer: {e}")
                msg2 += "\nAn error occurred during transfer"

        line_alert.SendMessage(msg2)
    '''

    #################################################################################################################    
    #포지션이 없을 경우
    if len(dic['item']) == 0:
        if abs(amt_s) > 0:#값이 있으면 리스트에 추가를 해준다.
            dic['no'] += 1
            dic["item"].append({'no':dic['no'], 'type':'M','price':coin_price,'amt':round(-(abs(amt_s)), 3)})
            msg = "없는 숏포지션 추가\n현재 가격으로 추가합니다.\n실제 구매하신 가격하고 다를수 있습니다."
            viewlist(msg)
        if abs(amt_l) > 0:#값이 다르면 리스트에 추가를 해준다.
            dic['no'] += 1
            dic["item"].append({'no':dic['no'], 'type':'M','price':coin_price,'amt':round(amt_l, 3)})
            msg = "없는 롱포지션 추가\n현재 가격으로 추가합니다.\n실제 구매하신 가격하고 다를수 있습니다."
            viewlist(msg)

        #숏포지션 : 5일선이 20일선 위에 있는데 5일선이 하락추세로 꺾였을때 숏 떨어질거야 를 잡는다.
        if ma5[0] > ma20 and ma5[2] < ma5[1] and ma5[1] > ma5[0]:# and rsi14 > 35.0:
            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', first_amount, None, {'positionSide': 'SHORT'})
            buy_price = float(data['average']) #구매가격
            dic['no'] += 1
            dic["item"].append({'no':dic['no'], 'type':'N','price':buy_price,'amt':round(-first_amount, 3)})
            msg = "\n"+Target_Coin_Symbol+" 숏 포지션 구매11"
            viewlist(msg)
        
        #롱포지션 : 5일선이 20일선 아래에 있는데 5일선이 상승추세로 꺾였을때 롱 오를거야 를 잡는다.
        if ma5[0] < ma20 and ma5[2] > ma5[1] and ma5[1] < ma5[0]:# and rsi14 < 65.0:
            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', first_amount, None, {'positionSide': 'LONG'})
            buy_price = float(data['average']) #구매가격
            dic['no'] += 1
            dic["item"].append({'no':dic['no'], 'type':'N','price':buy_price,'amt':round(first_amount, 3)})
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
            revenue_rate = (coin_price - item["price"]) / item["price"] * 100.0
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
            dic["item"].append({'no':dic['no'],'type':'M','price':coin_price,'amt':round(-(abs(amt_s)-amt_s2), 3)})
            msg = "없는 숏포지션 추가\n현재 가격으로 추가합니다.\n실제 구매하신 가격하고 다를수 있습니다."
            viewlist(msg)
        if abs(amt_l) > amt_l2 and (abs(amt_l)-amt_l2) >= first_amount:#값이 다르면 리스트에 추가를 해준다.
            dic['no'] += 1
            dic["item"].append({'no':dic['no'],'type':'M','price':coin_price,'amt':round(amt_l-amt_l2, 3)})
            msg = "없는 롱포지션 추가\n현재 가격으로 추가합니다.\n실제 구매하신 가격하고 다를수 있습니다."
            viewlist(msg)

        amt = amt_l2 - amt_s2
        if amt < 0: #숏을 많이 가지고 있다는 얘기
            if first_amount*2 < abs(amt):
                amount_l = round(abs(amt*2.0)-0.0005, 3)

        else:#롱을 많이 가지고 있다는 얘기
            if first_amount*2 < abs(amt):
                amount_s = round(abs(amt*2.0)-0.0005, 3)

        #이벤트 정리
        for i in range(len(dic["event"]) - 1, -1, -1):
            delidx = i
            for item in dic["item"]:
                if item["type"] == "E":
                    if dic["event"][i]["time"] == item["time"]:
                        delidx = -1
        
            if delidx > -1 and dic["event"][i]["time"] != (today.day*100)+today.hour:
                del dic["event"][i]

        bEvent = False
        for event in dic["event"]:
            #해당 시간대에 이벤트가 있는지 체크.
            if event["type"] == "E" and event["time"] == (today.day*100)+today.hour:
                bEvent = True
        
        # 이벤트가 있는지 체크 시간별 체크를 해야 하는데 
        if bEvent == False and today.minute > 0: # 정시에 할경우 문제가 생기는거 같다.
            per = (df_1h["close"].iloc[-1]/df_1h["open"].iloc[-2])-1
            #print("per : ", per)
            if abs(per) >= 0.013: #2시간봉 기준으로 1.3%이상일경우 해당 방향으로 이벤트를 추가한다.
                amount = round(((amt_l2+amt_s2)/2)-0.0005, 3)
                if amount < first_amount*10:
                    amount = first_amount*10
                    
                if per > 0: #롱을 구매한다.
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', amount, None, {'positionSide': 'LONG'})
                    buy_price = float(data['average']) #구매가격
                    dic['no'] += 1
                    dic["item"].append({'no':dic['no'],'type':'E','price':buy_price,'amt':round(amount, 3),'time':(today.day*100)+today.hour})
                    dic["event"].append({'no':dic['no'],'type':'E','price':buy_price,'amt':round(amount, 3),'time':(today.day*100)+today.hour})
                    msg = "\n"+Target_Coin_Symbol+" 롱 포지션 이벤트구매"
                    viewlist(msg)

                else: #숏을 구매한다.
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', amount, None, {'positionSide': 'SHORT'})
                    buy_price = float(data['average']) #구매가격
                    dic['no'] += 1
                    dic["item"].append({'no':dic['no'],'type':'E','price':buy_price,'amt':round(-amount, 3),'time':(today.day*100)+today.hour})
                    dic["event"].append({'no':dic['no'],'type':'E','price':buy_price,'amt':round(-amount, 3),'time':(today.day*100)+today.hour})
                    msg = "\n"+Target_Coin_Symbol+" 숏 포지션 이벤트구매"
                    viewlist(msg)

        #print("max_revenue_index : ", max_revenue_index)
        #print("max_revenue", max_revenue)
        #print("-target_revenue_rate*2", -target_revenue_rate*2)
        #여기서는 마지막에 있는 포지션이 수익이 나지 않고 멀어졌을경우. 새로운 포지션을 잡는다.
        if max_revenue < -(target_revenue_rate*3):
            #숏포지션 : 5일선이 20일선 위에 있는데 5일선이 하락추세로 꺾였을때 숏 떨어질거야 를 잡는다.
            if ma5[2] < ma5[1] and ma5[1] > ma5[0]:
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', amount_s, None, {'positionSide': 'SHORT'})
                buy_price = float(data['average']) #구매가격
                dic['no'] += 1
                dic["item"].append({'no':dic['no'],'type':'N','price':buy_price,'amt':round(-amount_s, 3)})
                msg = "\n"+Target_Coin_Symbol+" 숏 포지션 구매22"
                viewlist(msg)
            
            #롱포지션 : 5일선이 20일선 아래에 있는데 5일선이 상승추세로 꺾였을때 롱 오를거야 를 잡는다.
            if ma5[2] > ma5[1] and ma5[1] < ma5[0]:
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', amount_l, None, {'positionSide': 'LONG'})
                buy_price = float(data['average']) #구매가격
                dic['no'] += 1
                dic["item"].append({'no':dic['no'],'type':'N','price':buy_price,'amt':round(amount_l, 3)})
                msg = "\n"+Target_Coin_Symbol+" 롱 포지션 구매22"
                viewlist(msg)
        
        # 마지막이 숏이고 롱을 사야 하는순간일경우
        elif max_revenue < -target_revenue_rate and dic["item"][max_revenue_index]["amt"] < 0 and ma5[2] > ma5[1] and ma5[1] < ma5[0]:
            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', amount_l, None, {'positionSide': 'LONG'})
            buy_price = float(data['average']) #구매가격
            dic['no'] += 1
            dic["item"].append({'no':dic['no'],'type':'N','price':buy_price,'amt':round(amount_l, 3)})
            msg = "\n"+Target_Coin_Symbol+" 롱 포지션 구매33"
            viewlist(msg)

        # 마지막이 롱이고 숏을 사야 하는 순간
        elif max_revenue < -target_revenue_rate and dic["item"][max_revenue_index]["amt"] > 0 and ma5[2] < ma5[1] and ma5[1] > ma5[0]:
            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', amount_s, None, {'positionSide': 'SHORT'})
            buy_price = float(data['average']) #구매가격
            dic['no'] += 1
            dic["item"].append({'no':dic['no'],'type':'N','price':buy_price,'amt':round(-amount_s, 3)})
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
                        revenue_rate2 = (item["price"] - coin_price) / item["price"] * 100.0
                        if revenue_rate2 >= target_revenue_rate:
                            #숏 포지션 시장가 판매!
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', round(abs(item["amt"]), 3), None, {'positionSide': 'SHORT'})
                            sell_price = float(data['average']) #판매가격
                            charge_dollar = sell_price*abs(item["amt"])*charge*0.01 #수수료
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
                        revenue_rate2 = (coin_price - item["price"]) / item["price"] * 100.0
                        if revenue_rate2 >= target_revenue_rate:
                            #롱 포지션 시장가 판매!
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', round(abs(item["amt"]), 3), None, {'positionSide': 'LONG'})
                            sell_price = float(data['average']) #판매가격
                            charge_dollar = sell_price*abs(item["amt"])*charge*0.01 #수수료
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
                #line_alert.SendMessage(msg)           

            # 인덱스를 역순으로 정렬하여 리스트에서 삭제
            #if len(remove) > 1:
            #    line_alert.SendMessage(str(remove))
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
                    item["price"] = round(((item["price"]*abs(item["amt"]))-(cap*item['amt']*1000))/abs(item["amt"]), 2)
            '''
            if len(dic["item"]) > 0 and cap > 0.0:
                cap = cap/len(dic["item"]) #구해진 cap를 토탈총갯수만큼 분할한다음에
                for i, item in enumerate(dic["item"]):
                    if item["amt"] > 0:
                        dic["item"][i]["price"] = round(((item["price"]*abs(item["amt"]))-cap)/abs(item["amt"]), 2)
                    else:
                        dic["item"][i]["price"] = round(((item["price"]*abs(item["amt"]))+cap)/abs(item["amt"]), 2)

            if isbuy != None:
                if len(dic["item"])>0:
                    max_revenue_index = None  # 수익률이 제일 높은 인덱스를 저장할 변수
                    max_revenue = float('-inf')  # 초기 최대 수익률을 음의 무한대로 설정
                    for i,item in enumerate(reversed(dic["item"])):
                        revenue_rate = (coin_price - item["price"]) / item["price"] * 100.0
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
                    dic["item"].append({'no':dic['no'], 'type':'N','price':buy_price,'amt':round(-amount_s, 3)})
                    msg += "\n"+Target_Coin_Symbol+" 숏 포지션 구매44"
                    #msg += "\n가격:"+str(round(buy_price, 1))+" 수량:"+str(round(first_amount, 3))
                    #line_alert.SendMessage(msg)
                    viewlist(msg)
                
                elif isbuy == "long":
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', amount_l, None, {'positionSide': 'LONG'})
                    buy_price = float(data['average']) #구매가격
                    dic['no'] += 1
                    dic["item"].append({'no':dic['no'], 'type':'N','price':buy_price,'amt':round(amount_l, 3)})
                    msg += "\n"+Target_Coin_Symbol+" 롱 포지션 구매44"
                    #msg += "\n가격:"+str(round(buy_price, 1))+" 수량:"+str(round(first_amount, 3))
                    #line_alert.SendMessage(msg)
                    viewlist(msg)

    print("\n-- END --------------------------------------------------------------------------------------------\n")
    with open(info_file_path, 'w') as outfile:
        json.dump(dic, outfile)