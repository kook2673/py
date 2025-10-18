#-*-coding:utf-8 -*-
import time
import pandas as pd
import numpy
 
import math
import requests
from datetime import datetime

import base64
import hashlib
import hmac
import json
import httplib2
import uuid

ACCESS_TOKEN = '여러분의 ACCESS_TOKEN'
SECRET_KEY = bytes('여러분의 SECRET_KEY', 'utf-8')


def get_encoded_payload(payload):
    payload['nonce'] = str(uuid.uuid4())

    dumped_json = json.dumps(payload)
    encoded_json = base64.b64encode(bytes(dumped_json, 'utf-8'))
    return encoded_json


def get_signature(encoded_payload):
    signature = hmac.new(SECRET_KEY, encoded_payload, hashlib.sha512)
    return signature.hexdigest()


def get_response(action, payload):
    url = '{}{}'.format('https://api.coinone.co.kr', action)

    encoded_payload = get_encoded_payload(payload)

    headers = {
        'Content-type': 'application/json',
        'X-COINONE-PAYLOAD': encoded_payload,
        'X-COINONE-SIGNATURE': get_signature(encoded_payload),
    }

    http = httplib2.Http()
    response, content = http.request(url, 'POST', headers=headers)

    return content



#RSI지표 수치를 구해준다. 첫번째: 분봉/일봉 정보, 두번째: 기간, 세번째: 기준 날짜
def GetRSI(ohlcv,period,st):
    delta = ohlcv["close"].diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0
    _gain = up.ewm(com=(period - 1), min_periods=period).mean()
    _loss = down.abs().ewm(com=(period - 1), min_periods=period).mean()
    RS = _gain / _loss
    return float(pd.Series(100 - (100 / (1 + RS)), name="RSI").iloc[st])

#이동평균선 수치를 구해준다 첫번째: 분봉/일봉 정보, 두번째: 기간, 세번째: 기준 날짜
def GetMA(ohlcv,period,st):
    close = ohlcv["close"]
    ma = close.rolling(period).mean()
    return float(ma.iloc[st])

#볼린저 밴드를 구해준다 첫번째: 분봉/일봉 정보, 두번째: 기간, 세번째: 기준 날짜
#차트와 다소 오차가 있을 수 있습니다.
def GetBB(ohlcv,period,st,unit=2.0):
    dic_bb = dict()

    ohlcv = ohlcv[::-1]
    ohlcv = ohlcv.shift(st + 1)
    close = ohlcv["close"].iloc[::-1]

    bb_center=numpy.mean(close[len(close)-period:len(close)])
    band1=unit*numpy.std(close[len(close)-period:len(close)])

    dic_bb['ma'] = float(bb_center)
    dic_bb['upper'] = float(bb_center + band1)
    dic_bb['lower'] = float(bb_center - band1)

    return dic_bb


#일목 균형표의 각 데이타를 리턴한다 첫번째: 분봉/일봉 정보, 두번째: 기준 날짜
def GetIC(ohlcv,st):

    high_prices = ohlcv['high']
    close_prices = ohlcv['close']
    low_prices = ohlcv['low']


    nine_period_high =  ohlcv['high'].shift(-2-st).rolling(window=9).max()
    nine_period_low = ohlcv['low'].shift(-2-st).rolling(window=9).min()
    ohlcv['conversion'] = (nine_period_high + nine_period_low) /2
    
    period26_high = high_prices.shift(-2-st).rolling(window=26).max()
    period26_low = low_prices.shift(-2-st).rolling(window=26).min()
    ohlcv['base'] = (period26_high + period26_low) / 2
    
    ohlcv['sunhang_span_a'] = ((ohlcv['conversion'] + ohlcv['base']) / 2).shift(26)
    
    
    period52_high = high_prices.shift(-2-st).rolling(window=52).max()
    period52_low = low_prices.shift(-2-st).rolling(window=52).min()
    ohlcv['sunhang_span_b'] = ((period52_high + period52_low) / 2).shift(26)
    
    
    ohlcv['huhang_span'] = close_prices.shift(-26)


    nine_period_high_real =  ohlcv['high'].rolling(window=9).max()
    nine_period_low_real = ohlcv['low'].rolling(window=9).min()
    ohlcv['conversion'] = (nine_period_high_real + nine_period_low_real) /2
    
    period26_high_real = high_prices.rolling(window=26).max()
    period26_low_real = low_prices.rolling(window=26).min()
    ohlcv['base'] = (period26_high_real + period26_low_real) / 2
    


    
    dic_ic = dict()

    dic_ic['conversion'] = ohlcv['conversion'].iloc[st]
    dic_ic['base'] = ohlcv['base'].iloc[st]
    dic_ic['huhang_span'] = ohlcv['huhang_span'].iloc[-27]
    dic_ic['sunhang_span_a'] = ohlcv['sunhang_span_a'].iloc[-1]
    dic_ic['sunhang_span_b'] = ohlcv['sunhang_span_b'].iloc[-1]


  

    return dic_ic


#MACD의 12,26,9 각 데이타를 리턴한다 첫번째: 분봉/일봉 정보, 두번째: 기준 날짜
def GetMACD(ohlcv,st):
    macd_short, macd_long, macd_signal=12,26,9

    ohlcv["MACD_short"]=ohlcv["close"].ewm(span=macd_short).mean()
    ohlcv["MACD_long"]=ohlcv["close"].ewm(span=macd_long).mean()
    ohlcv["MACD"]=ohlcv["MACD_short"] - ohlcv["MACD_long"]
    ohlcv["MACD_signal"]=ohlcv["MACD"].ewm(span=macd_signal).mean() 

    dic_macd = dict()
    
    dic_macd['macd'] = ohlcv["MACD"].iloc[st]
    dic_macd['macd_siginal'] = ohlcv["MACD_signal"].iloc[st]
    dic_macd['ocl'] = dic_macd['macd'] - dic_macd['macd_siginal']

    return dic_macd


#스토캐스틱 %K %D 값을 구해준다 첫번째: 분봉/일봉 정보, 두번째: 기간, 세번째: 기준 날짜
def GetStoch(ohlcv,period,st):

    dic_stoch = dict()

    ndays_high = ohlcv['high'].rolling(window=period, min_periods=1).max()
    ndays_low = ohlcv['low'].rolling(window=period, min_periods=1).min()
    fast_k = (ohlcv['close'] - ndays_low)/(ndays_high - ndays_low)*100
    slow_d = fast_k.rolling(window=3, min_periods=1).mean()

    dic_stoch['fast_k'] = fast_k.iloc[st]
    dic_stoch['slow_d'] = slow_d.iloc[st]

    return dic_stoch


#해당되는 리스트안에 해당 코인이 있는지 여부를 리턴하는 함수
def CheckCoinInList(CoinList,Ticker):
    InCoinOk = False
    for coinTicker in CoinList:
        if coinTicker == Ticker:
            InCoinOk = True
            break

    return InCoinOk


#원는 개수 만큼의 캔들 정보를 가져옴!! period: 1m, 3m, 5m, 10m, 15m, 30m, 1h, 2h, 4h, 6h, 1d, 1w, 1mon
def GetOhlcv(ticker, period, get_len=200):
    data = []
    if get_len > 200:
        # 시작 시간을 현재 시간으로 설정
        start_timestamp = int(datetime.now().timestamp() * 1000)
        remaining_data = get_len
        
        while True:
            # API에서 데이터 가져오기
            url = f"https://api.coinone.co.kr/public/v2/chart/KRW/{ticker}?interval={period}&timestamp={start_timestamp}"
            headers = {"accept": "application/json"}
            response = requests.get(url, headers=headers)
            new_data = response.json()
            
            # 가져온 데이터를 저장하고 남은 데이터 개수 갱신
            data.extend(new_data['chart'])
            remaining_data -= len(new_data['chart'])
            
            # 마지막 데이터인지 확인하고 루프 종료
            if new_data['is_last'] or remaining_data <= 0:
                break
            
            # 다음 요청을 위한 시작 시간 업데이트
            start_timestamp = new_data['chart'][-1]['timestamp'] - abs((new_data['chart'][-2]['timestamp'] - new_data['chart'][-1]['timestamp']))
            time.sleep(0.2)

    else:
        # get_len이 200 이하인 경우 일반적인 방식으로 데이터 가져오기
        url = f"https://api.coinone.co.kr/public/v2/chart/KRW/{ticker}?interval={period}"
        headers = {"accept": "application/json"}
        response = requests.get(url, headers=headers)
        data = response.json()

    # 데이터를 OHLCV 형식으로 변환
    ohlcv = []
    
    remaining_data = get_len
    st_len = 0
    
    data_chart = None
    if get_len > 200:
        data_chart = data
    else:
        data_chart = data['chart']
        
    for candle in data_chart:
        ohlcv.append([
            candle['timestamp'],
            candle['open'],
            candle['high'],
            candle['low'],
            candle['close'],
            candle['target_volume'],
            candle['quote_volume']
        ])
        st_len += 1
        if get_len <= st_len:
            break

    # DataFrame으로 변환하여 반환
    df = pd.DataFrame(ohlcv, columns=['datetime', 'open', 'high', 'low', 'close', 'volume', 'value'])
    df[[ 'open', 'high', 'low', 'close', 'volume', 'value']] = df[[ 'open', 'high', 'low', 'close', 'volume', 'value']].apply(pd.to_numeric)
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
    df.set_index('datetime', inplace=True)
    df = df.iloc[::-1]
    
    return df

#모든 티커 정보 읽어오기
def GetTickers(market="KRW"):

    url = "https://api.coinone.co.kr/public/v2/markets/"+market
    headers = {"accept": "application/json"}

    response = requests.get(url, headers=headers)
    TickerData = response.json()
    
    #pprint.pprint(TickerData)
    
    ticker_list = list()
    for data in TickerData['markets']:
        if data['quote_currency'] == market and data['maintenance_status'] == 0 and data['trade_status'] == 1:
            ticker_list.append(data['target_currency'])
                
    return ticker_list

#잔고를 가져옴
def GetBalances():
    
    BalanceData = json.loads(get_response(action='/v2.1/account/balance/all', payload={'access_token': ACCESS_TOKEN,}).decode('utf-8')) 

    balance_list = list()
    for data in BalanceData['balances']:
        balance_list.append(data)
                
    return balance_list


#거래대금이 많은 순으로 코인 리스트를 얻는다. 첫번째 : Interval기간, 두번째 : 몇개까지 
def GetTopCoinList(interval,top):
    print("--------------GetTopCoinList Start-------------------")
    Tickers = GetTickers()
    time.sleep(0.1)
    dic_coin_money = dict()

    for ticker in Tickers:
        print("--------------------------", ticker)
        try:
            time.sleep(0.1)
            df = GetOhlcv(ticker,interval)
            #volume_money = (df['close'].iloc[-1] * df['volume'].iloc[-1]) + (df['close'].iloc[-2] * df['volume'].iloc[-2])
            volume_money = float(df['value'].iloc[-1]) + float(df['value'].iloc[-2]) #거래대금!
            dic_coin_money[ticker] = volume_money
            print(ticker, dic_coin_money[ticker])
           # time.sleep(0.1)

        except Exception as e:
            print("---:",e)

    dic_sorted_coin_money = sorted(dic_coin_money.items(), key = lambda x : x[1], reverse= True)

    coin_list = list()
    cnt = 0
    for coin_data in dic_sorted_coin_money:
        cnt += 1
        if cnt <= top:
            coin_list.append(coin_data[0])
        else:
            break

    print("--------------GetTopCoinList End-------------------")

    return coin_list


#해당 코인의 현재가를 읽어 온다
def GetCurrentPrice(ticker):
    
    url = "https://api.coinone.co.kr/public/v2/ticker_new/KRW/"+ticker+"?additional_data=false"


    headers = {"accept": "application/json"}

    response = requests.get(url, headers=headers)
    TickerData = response.json()
    
    current_price = 0
    for data in TickerData['tickers']:
        if data['target_currency'].lower() == ticker.lower():
            current_price = data['last']
            break
        
    if current_price == 0:
        current_price = GetOhlcv(ticker,'1d')['close'].iloc[-1]
        
                
    return float(current_price)


#티커에 해당하는 코인의 수익율을 구해서 리턴하는 함수.
def GetRevenueRate(balances,Ticker):
    revenue_rate = 0.0
    for value in balances:
        try:
            realTicker = value['currency']
            if Ticker.lower() == realTicker.lower():
                time.sleep(0.05)
                nowPrice = GetCurrentPrice(realTicker)
                revenue_rate = (float(nowPrice)- float(value['average_price'])) * 100.0 / float(value['average_price'])
                break

        except Exception as e:
            print("---:", e)

    return revenue_rate

#수익금과 수익률을 리턴해주는 함수 (수수료는 생각안함) 
def GetRevenueMoneyAndRate(balances,Ticker):
            
    revenue_data = dict()

    revenue_data['revenue_money'] = 0
    revenue_data['revenue_rate'] = 0

    for value in balances:
        try:
            realTicker = value['currency']
            if Ticker.lower() == realTicker.lower():
                
                nowPrice = GetCurrentPrice(realTicker)
                revenue_data['revenue_money'] = (float(nowPrice) - float(value['average_price'])) * (float(value['available']) + float(value['limit']))
                revenue_data['revenue_rate'] = (float(nowPrice) - float(value['average_price'])) * 100.0 / float(value['average_price'])
                time.sleep(0.06)
                break

        except Exception as e:
            print("---:", e)

    return revenue_data

#해당 코인의 보유 수량을 얻어온다!
def GetCoinAmount(balances,Ticker,type="ALL"):
    CoinAmount = 0.0
    for value in balances:
        realTicker = value['currency']
        if Ticker.lower() == realTicker.lower():
            CoinAmount = float(value['available']) 
            if type == "ALL":
                CoinAmount += float(value['limit'])
            break
    return CoinAmount

#티커에 해당하는 코인의 총 매수금액을 리턴하는 함수
def GetCoinNowMoney(balances,Ticker):
    CoinMoney = 0.0
    for value in balances:
        realTicker = value['currency']
        if Ticker.lower() == realTicker.lower():
            CoinMoney = float(value['average_price']) * (float(value['available']) + float(value['limit']))
            break
    return CoinMoney

#티커에 해당하는 코인의 현재 평가 금액을 리턴하는 함수
def GetCoinNowRealMoney(balances,Ticker):
    CoinMoney = 0.0
    for value in balances:
        realTicker = value['currency']
        if Ticker.lower() == realTicker.lower():
            time.sleep(0.1)
            nowPrice = GetCurrentPrice(realTicker)
            CoinMoney = float(nowPrice) * (float(value['available']) + float(value['limit']))
            break
    return CoinMoney

#티커에 해당하는 코인이 매수된 상태면 참을 리턴하는함수
def IsHasCoin(balances,Ticker):
    HasCoin = False
    for value in balances:
        realTicker = value['currency']
        if Ticker.lower() == realTicker.lower() and (float(value['available']) + float(value['limit'])) > 0:
            HasCoin = True
    return HasCoin

#내가 매수한 (가지고 있는) 코인 개수를 리턴하는 함수
def GetHasCoinCnt(balances):
    CoinCnt = 0
    for value in balances:
        if (float(value['available']) + float(value['limit'])) > 0 and float(value['average_price']) != 0:
            CoinCnt += 1
    return CoinCnt


#티커에 해당하는 코인의 평균 매입단가를 리턴한다.
def GetAvgBuyPrice(balances, Ticker):
    avg_buy_price = 0
    for value in balances:
        realTicker = value['currency']
        if Ticker.lower() == realTicker.lower():
            time.sleep(0.1)
            avg_buy_price = float(value['average_price'])
    return avg_buy_price

#총 원금을 구한다!
def GetTotalMoney(balances):
    total = 0.0
    for value in balances:
        try:
            ticker = value['currency']
            if ticker.upper() == "KRW": #원화일 때는 평균 매입 단가가 0이므로 구분해서 총 평가금액을 구한다.
                total += (float(value['available']) + float(value['limit']))
            else:
                avg_buy_price = float(value['average_price'])
                if avg_buy_price != 0 and (float(value['available']) != 0 or float(value['limit']) != 0):
                    total += (avg_buy_price * (float(value['available']) + float(value['limit'])))
        except Exception as e:
            print("")
    return total

#총 평가금액을 구한다!
def GetTotalRealMoney(balances):
    total = 0.0
    for value in balances:

        try:
            ticker = value['currency']
            if ticker.upper() == "KRW": #원화일 때는 평균 매입 단가가 0이므로 구분해서 총 평가금액을 구한다.
                total += (float(value['available']) + float(value['limit']))
            else:
            
                avg_buy_price = float(value['average_price'])
                if avg_buy_price != 0 and (float(value['available']) != 0 or float(value['limit']) != 0): #드랍받은 코인(평균매입단가가 0이다) 제외 하고 현재가격으로 평가금액을 구한다,.
                   
                    time.sleep(0.1)
                    nowPrice = GetCurrentPrice(ticker)
                    total += (float(nowPrice) * (float(value['available']) + float(value['limit'])))
        except Exception as e:
            print("")


    return total

#거래대금 폭발 여부 첫번째: 캔들 정보, 두번째: 이전 5개의 평균 거래량보다 몇 배 이상 큰지
#이전 캔들이 그 이전 캔들 5개의 평균 거래금액보다 몇 배이상 크면 거래량 폭발로 인지하고 True를 리턴해줍니다
#현재 캔들[-1]은 막 시작했으므로 이전 캔들[-2]을 보는게 맞다!
def IsVolumePung(ohlcv,st):

    Result = False
    try:
        avg_volume = (float(ohlcv['volume'].iloc[-3]) + float(ohlcv['volume'].iloc[-4]) + float(ohlcv['volume'].iloc[-5]) + float(ohlcv['volume'].iloc[-6]) + float(ohlcv['volume'].iloc[-7])) / 5.0
        if avg_volume * st < float(ohlcv['volume'].iloc[-2]):
            Result = True
    except Exception as e:
        print("IsVolumePung ---:", e)

    
    return Result


#시장가 매수한다. 2초뒤 잔고 데이타 리스트를 리턴한다.
def BuyCoinMarket(Ticker,Money):
    time.sleep(0.05)

    print(get_response(action='/v2.1/order', payload={
        'access_token': ACCESS_TOKEN,
        'quote_currency': 'KRW',
        'target_currency': Ticker,
        'type': 'MARKET',
        'side': 'BUY',
        'amount': Money
    }))

    time.sleep(2.0)
    #내가 가진 잔고 데이터를 다 가져온다.
    balances = GetBalances()
    return balances

#시장가 매도한다. 2초뒤 잔고 데이타 리스트를 리턴한다.
def SellCoinMarket(Ticker,Volume):
    time.sleep(0.05)
    print(get_response(action='/v2.1/order', payload={
        'access_token': ACCESS_TOKEN,
        'quote_currency': 'KRW',
        'target_currency': Ticker,
        'type': 'MARKET',
        'side': 'SELL',
        'qty': Volume
    }))

    time.sleep(2.0)
    #내가 가진 잔고 데이터를 다 가져온다.
    balances = GetBalances()
    return balances


#넘겨받은 가격과 수량으로 지정가 매수한다.
def BuyCoinLimit(Ticker,Price,Volume,ReturnData=False):
    time.sleep(0.05)
    
    resp_data = get_response(action='/v2.1/order', payload={
        'access_token': ACCESS_TOKEN,
        'quote_currency': 'KRW',
        'target_currency': Ticker,
        'type': 'LIMIT',
        'side': 'BUY',
        'qty': Volume,
        'price': change_price(Price),
        'post_only': True
    })
    
    if ReturnData == True:
        print(resp_data)
        resp_data_str = resp_data.decode('utf-8')
        resp_data_json = json.loads(resp_data_str)
        return resp_data_json['order_id']
    else:
        print(resp_data)


#넘겨받은 가격과 수량으로 지정가 매도한다.
def SellCoinLimit(Ticker,Price,Volume,ReturnData=False):
    time.sleep(0.05)
    
    resp_data = get_response(action='/v2.1/order', payload={
        'access_token': ACCESS_TOKEN,
        'quote_currency': 'KRW',
        'target_currency': Ticker,
        'type': 'LIMIT',
        'side': 'SELL',
        'qty': Volume,
        'price': change_price(Price),
        'post_only': True
    })
    
    if ReturnData == True:
        print(resp_data)
        resp_data_str = resp_data.decode('utf-8')
        resp_data_json = json.loads(resp_data_str)
        return resp_data_json['order_id']
    else:
        print(resp_data)



#현재 라이브중인 미체결 주문 리스트 얻기
def GetActiveOrders(Ticker):
    
    OrderData = json.loads(get_response(action='/v2.1/order/active_orders', payload={'access_token': ACCESS_TOKEN,'quote_currency': 'KRW','target_currency': Ticker}).decode('utf-8')) 
                
    return OrderData['active_orders']


#해당 코인에 걸어진 매수매도주문 모두를 취소한다.
def CancelCoinOrder(Ticker):
    
    orders_data = GetActiveOrders(Ticker)
    if len(orders_data) > 0:
        for order in orders_data:
            time.sleep(0.1)
            print(get_response(action='/v2.1/order/cancel', payload={
                'access_token': ACCESS_TOKEN,
                'order_id': order['order_id'],
                'quote_currency': 'KRW',
                'target_currency': Ticker,
            }))
            
#주문 ID로 해당 주문 하나를 취소한다.
def CancelOrderById(order_id, Ticker):
    time.sleep(0.1)
    print(get_response(action='/v2.1/order/cancel', payload={
        'access_token': ACCESS_TOKEN,
        'order_id': order_id,
        'quote_currency': 'KRW',
        'target_currency': Ticker,
    }))



#틱사이즈 보정!! 
def change_price(price, method="floor"):

    url = "https://api.coinone.co.kr/public/v2/range_units"
    headers = {"accept": "application/json"}
    response = requests.get(url, headers=headers)
    Hoga_data = response.json()


    func = math.floor 
    if method == "floor":
        func = math.floor
    elif method == "round":
        func = round 
    else:
        func = math.ceil 
        
    tick_size = price
    for data in Hoga_data['range_price_units']:
        if data['range_min'] <= price < data['next_range_min']:
            tick_size = func(price / data['price_unit']) / (1/data['price_unit'])
            break
        
    return tick_size


            