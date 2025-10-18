'''

관련 포스팅

주식 양방향 매매 이평무한매수 전략의 성과를 예측하다? 코인 양방향 매매로.. (수익 공개!)
https://blog.naver.com/zacra/222993971891

위 포스팅을 꼭 참고하세요!!! 

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.

주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!


'''
import ccxt
import time
import pandas as pd
import pprint
       
import myBinance
import ende_key  #암복호화키
import my_key    #업비트 시크릿 액세스키

import line_alert #라인 메세지를 보내기 위함!

import json

BOT_NAME = "INFINITY_BOTH_SIDE"

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


#선물 마켓에서 거래중인 모든 코인을 가져옵니다.
#Tickers = binanceX.fetch_tickers()

Tickers = ['BTC/USDT']
#총 원금대비 설정 비율 
#아래처럼 0.2 로 셋팅하면 20%가 해당 전략에 할당된다는 이야기!
Invest_Rate = 0.25


#테스트를 위해 비트코인만 일단 체크해봅니다. 
#LovelyCoinList = ['BTC/USDT']

#매매 대상 코인 개수 
CoinCnt = len(Tickers) #len(LovelyCoinList)





#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#
############# 해당 전략으로 매수할 종목 데이터 리스트 ####################
InfinityMaDataList = list()
#파일 경로입니다.
bot_file_path = "/var/autobot/Coin_" + BOT_NAME + ".json"

try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(bot_file_path, 'r') as json_file:
        InfinityMaDataList = json.load(json_file)

except Exception as e:
    print("Exception by First")
################################################################
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#







###################################################
#설정할 레버리지!
set_leverage = 20

#타임프레임!
now_time_frame = 15 #1,3,5,15,30

balance = binanceX.fetch_balance(params={"type": "future"})
time.sleep(0.1)

#pprint.pprint(balance)

MoneyDict = dict()

#파일 경로입니다.
money_file_path = "/var/autobot/Coin_" + BOT_NAME + "_Money.json"
try:
    #이 부분이 파일을 읽어서 딕셔너리에 넣어주는 로직입니다. 
    with open(money_file_path, 'r') as json_file:
        MoneyDict = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")


#현재 평가금액을 구합니다.
TotalRealMoney =  float(balance['total']['USDT'])

print("TotalRealMoney ", TotalRealMoney)



if MoneyDict.get('TotalRealMoney') == None:
    MoneyDict['TotalRealMoney'] = TotalRealMoney

    with open(money_file_path, 'w') as outfile:
        json.dump(MoneyDict, outfile)   

    line_alert.SendMessage("!!!!!!!!!!!!!! First !!!!!! " + str(MoneyDict['TotalRealMoney']))



print("$$$$$$$$ MoneyDict['TotalRealMoney']", MoneyDict['TotalRealMoney'])


print("$$$$$$$$ TotalRealMoney", TotalRealMoney)


#시간 정보를 가져옵니다. 아침 9시의 경우 서버에서는 hour변수가 0이 됩니다.
time_info = time.gmtime()
hour = time_info.tm_hour
min = time_info.tm_min
print("TIME" , hour, ":" ,min)



#이전에 저장된 가격에서 3%이상 증가되었다면!!
if MoneyDict['TotalRealMoney'] * 1.005 <= TotalRealMoney :

    #그리고 저장!!!
    MoneyDict['TotalRealMoney'] = TotalRealMoney

    with open(money_file_path, 'w') as outfile:
        json.dump(MoneyDict, outfile)   

    line_alert.SendMessage("$$$$$$$$!!!!!!!!!!!!!! 0.5% UPUP!!!!!!  USDT:" + str(balance['total']['USDT']))

else:
    
        
    if min == 0:
        line_alert.SendMessage("$$$$$$$$!!!!!!!!!!!!!!NOW STATUS !!!!!!  USDT:" + str(balance['total']['USDT']))
        




#모든 선물 거래가능한 코인을 가져온다.
for ticker in Tickers:

    try: 

        if "/USDT" in ticker:
            Target_Coin_Ticker = ticker


            Target_Coin_Symbol = ticker.replace("/", "").replace(":USDT", "")


            amt_s = 0 
            amt_b = 0
            entryPrice_s = 0 #평균 매입 단가. 따라서 물을 타면 변경 된다.
            entryPrice_b = 0 #평균 매입 단가. 따라서 물을 타면 변경 된다.


            isolated = False #격리모드인지 

                            

            print("------")
            #숏잔고
            for posi in balance['info']['positions']:
                if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'SHORT':
                    print(posi)
                    amt_s = float(posi['positionAmt'])
                    entryPrice_s= float(posi['entryPrice'])
                    leverage = float(posi['leverage'])
                    isolated = posi['isolated']
                    break


            #롱잔고
            for posi in balance['info']['positions']:
                if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'LONG':
                    print(posi)
                    amt_b = float(posi['positionAmt'])
                    entryPrice_b = float(posi['entryPrice'])
                    leverage = float(posi['leverage'])
                    isolated = posi['isolated']
                    break



      

      


                
            #종목 데이터
            PickCoinInfo = None

            #저장된 종목 데이터를 찾는다
            for CoinInfo in InfinityMaDataList:
                if CoinInfo['Ticker'] == Target_Coin_Ticker:
                    PickCoinInfo = CoinInfo
                    break



            if PickCoinInfo == None:
            
                #잔고가 없다 즉 처음이다!!!
                if abs(amt_b) == 0 and abs(amt_s) == 0:

                    InfinityDataDict = dict()
                    
                    InfinityDataDict['Ticker'] = Target_Coin_Ticker #종목 코드

                    InfinityDataDict['Long_Round'] = 0    #현재 회차

                    InfinityDataDict['Long_WaterAmt'] = 0 #물탄 수량!
                    InfinityDataDict['Long_WaterLossMoney'] = 0 #물탄 수량을 팔때 손해본 금액


                    InfinityDataDict['Short_Round'] = 0    #현재 회차

                    InfinityDataDict['Short_WaterAmt'] = 0 #물탄 수량!
                    InfinityDataDict['Short_WaterLossMoney'] = 0 #물탄 수량을 팔때 손해본 금액


                    InfinityDataDict['IsReady'] = 'Y'


                    InfinityMaDataList.append(InfinityDataDict) #데이터를 추가 한다!


                    msg = Target_Coin_Ticker + " 바이낸스 양방향 이평무한매수양방향봇 첫 시작!!!!"
                    print(msg) 
                    line_alert.SendMessage(msg) 


                    #파일에 저장
                    with open(bot_file_path, 'w') as outfile:
                        json.dump(InfinityMaDataList, outfile)
                        

        
            time.sleep(0.2)
            print("Target_Coin_Ticker" , Target_Coin_Ticker)

            

            time.sleep(0.05)
            #최소 주문 수량을 가져온다 
            minimun_amount = myBinance.GetMinimumAmount(binanceX,Target_Coin_Ticker)

            print("--- Target_Coin_Ticker:", Target_Coin_Ticker ," minimun_amount : ", minimun_amount)




            print(balance['USDT'])
            print("Total Money:",float(balance['USDT']['total']))
            print("Remain Money:",float(balance['USDT']['free']))


            leverage = 0  #레버리지

            #해당 코인 가격을 가져온다.
            coin_price = myBinance.GetCoinNowPrice(binanceX, Target_Coin_Ticker)



            #해당 코인에 할당된 금액에 따른 최대 매수수량을 구해본다!
            Max_Amt = float(binanceX.amount_to_precision(Target_Coin_Ticker, myBinance.GetAmount(float(balance['USDT']['total']),coin_price,Invest_Rate / CoinCnt)))  * set_leverage 

            print("Max_Amt:", Max_Amt)

                                        
            Buy_Amt = Max_Amt / 100.0

            Buy_Amt = float(binanceX.amount_to_precision(Target_Coin_Ticker,Buy_Amt))


            #최소 주문 수량보다 작다면 이렇게 셋팅!
            if Buy_Amt < minimun_amount:
                Buy_Amt = minimun_amount


            #보정된 미실현 손익이 해당 값보다 커야 이득으로 보고 포지션 종료!
            mininumSumProfit = (coin_price * (Buy_Amt/float(set_leverage))) * 0.5

            print("mininumSumProfit ", mininumSumProfit)



            #################################################################################################################
            #레버리지 셋팅
            if leverage != set_leverage:
                    
                try:
                    print(binanceX.fapiPrivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': set_leverage}))
                except Exception as e:
                    print("Exception:", e)

            #################################################################################################################


            #################################################################################################################
            #교차 모드로 설정
            if isolated == True:
                try:
                    print(binanceX.fapiPrivate_post_margintype({'symbol': Target_Coin_Symbol, 'marginType': 'CROSSED'}))
                except Exception as e:
                    print("Exception:", e)
            #################################################################################################################  





            #이제 데이터(InfinityMaDataList)는 확실히 있을 테니 본격적으로 트레이딩을 합니다!
            for CoinInfo in InfinityMaDataList:

                if CoinInfo['Ticker'] == Target_Coin_Ticker :

                    

                        
                    Avg_Period = 10.0 
                    

                    #현재는 15분 마다..
                    if min % now_time_frame == 0 or CoinInfo.get("IsUpCandle") == None:

                        df = myBinance.GetOhlcv(binanceX,Target_Coin_Ticker, str(now_time_frame) + 'm')



                        Now_Price = df['close'].iloc[-1]

                        CoinInfo['Now_Price'] = float(Now_Price)

                        #5일 이평선
                        CoinInfo['Ma5_before3'] = myBinance.GetMA(df,5,-4)
                        CoinInfo['Ma5_before'] = myBinance.GetMA(df,5,-3)
                        CoinInfo['Ma5'] = myBinance.GetMA(df,5,-2)

                        print("MA5",CoinInfo['Ma5_before3'], "->", CoinInfo['Ma5_before'], "-> ",CoinInfo['Ma5'])

                        #20일 이평선
                        CoinInfo['Ma20_before'] = myBinance.GetMA(df,20,-3)
                        CoinInfo['Ma20'] = myBinance.GetMA(df,20,-2)

                        print("MA20", CoinInfo['Ma20_before'], "-> ",CoinInfo['Ma20'])
                        

                        #양봉 캔들인지 여부
                        CoinInfo['IsUpCandle'] = 0

                        #시가보다 종가가 크다면 양봉이다
                        if df['open'].iloc[-2] <= df['close'].iloc[-2]:
                            CoinInfo['IsUpCandle'] = 1

                        print("IsUpCandle : ", CoinInfo['IsUpCandle'])
                        
                    




                        Up_Count = 0
                        Start_Num = -20
                        for i in range(1,int(Avg_Period)+1):
                            
                            CheckPrice = df['close'].iloc[Start_Num] 
                            print(CheckPrice, "  <<-  df[-", Start_Num,"]")

                            if Now_Price >= CheckPrice:
                                print("UP!")
                                Up_Count += 1.0


                            Start_Num -= 20

                        avg_month_momentum_score = Up_Count/Avg_Period

                        print("200기간 평균 모멘텀 ", avg_month_momentum_score)




                        Up_Count = 0
                        Start_Num = -10
                        for i in range(1,int(Avg_Period)+1):
                            
                            CheckPrice = df['close'].iloc[Start_Num] 
                            print(CheckPrice, "  <<-  df[-", Start_Num,"]")

                            if Now_Price >= CheckPrice:
                                print("UP!")
                                Up_Count += 1.0


                            Start_Num -= 10

                        avg_10day_momentum_score = Up_Count/Avg_Period

                        print("100기간 평균 모멘텀 ", avg_10day_momentum_score)



                        Up_Count = 0
                        Start_Num = -2
                        for i in range(1,int(Avg_Period)+1):
                            
                            CheckPrice = df['close'].iloc[Start_Num] 
                            print(CheckPrice, "  <<-  df[-", Start_Num,"]")

                            if Now_Price >= CheckPrice:
                                print("UP!")
                                Up_Count += 1.0


                            Start_Num -= 1

                        avg_day_momentum_score = Up_Count/Avg_Period

                        print("10기간 평균 모멘텀 ", avg_day_momentum_score)


                        long_momentum_score = (avg_month_momentum_score * 0.3) + (avg_10day_momentum_score * 0.2) + (avg_day_momentum_score * 0.3)
                        short_momentum_score = 0.8 - long_momentum_score


                        #절대 비중을 더해준다.
                        long_momentum_score += 0.1
                        short_momentum_score += 0.1

                        #결국 롱 스코어와 숏 스코어를 더하면 1.0이 나온다.

                        print("롱 모멘텀 스코어:", long_momentum_score , "숏 모멘텀 스코어:", short_momentum_score)
                        
                                
                        CoinInfo['long_momentum_score'] = long_momentum_score
                        CoinInfo['short_momentum_score'] = short_momentum_score
                        
                        
                        

                        CoinInfo['IsReady'] = 'Y'

                        #파일에 저장
                        with open(bot_file_path, 'w') as outfile:
                            json.dump(InfinityMaDataList, outfile)

                        line_alert.SendMessage("롱모멘텀:" + str(long_momentum_score) + " 숏모멘텀:" + str(short_momentum_score))

                    pprint.pprint(CoinInfo)



                        


                    ############ 매도 파트.... ##############
                    unrealizedProfit_s = 0 #미 실현 손익.
                    unrealizedProfit_s_f = 0
                    unrealizedProfit_b = 0 #미 실현 손익.
                    unrealizedProfit_b_f = 0

                    print("------")
                    #숏잔고
                    for posi in balance['info']['positions']:
                        if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'SHORT':

                            unrealizedProfit_s = posi['unrealizedProfit']
                            break


                    #롱 잔고
                    for posi in balance['info']['positions']:
                        if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'LONG':

                            unrealizedProfit_b = posi['unrealizedProfit']
                            break


                    #해당 코인 가격을 가져온다.
                    coin_price = myBinance.GetCoinNowPrice(binanceX, Target_Coin_Ticker)

                    TotalRevenue = 0



                    if abs(amt_b) > 0:
                            

                            
                        unrealizedProfit_b_f = float(unrealizedProfit_b) * 0.70
                        if float(unrealizedProfit_b) < 0:
                            unrealizedProfit_b_f = float(unrealizedProfit_b) * 1.3

                        TotalRevenue += (float(unrealizedProfit_b_f) - float(CoinInfo['Long_WaterLossMoney'])) 


                    if abs(amt_s) > 0:
                    


                        unrealizedProfit_s_f = float(unrealizedProfit_s) * 0.70
                        if float(unrealizedProfit_s) < 0:
                            unrealizedProfit_s_f = float(unrealizedProfit_s) * 1.3


                        TotalRevenue += (float(unrealizedProfit_s_f) - float(CoinInfo['Short_WaterLossMoney'])) 


                    print("mininumSumProfit:", mininumSumProfit," ---- TotalRevenue:", TotalRevenue)
                    if min % 15 == 0:
                        line_alert.SendMessage("현재손익:" + str(TotalRevenue) + " 목표수익:" + str(mininumSumProfit))


                    


                    #수익화 포지션 종료! 
                    # 보정한 미실현 손익이  목표 수익률보다 크다면 종료!
                    if mininumSumProfit < TotalRevenue:


                        
                        binanceX.cancel_all_orders(Target_Coin_Ticker)
                        time.sleep(0.1)

                        if abs(amt_b) > 0:

                            params = {
                                'positionSide': 'LONG'
                            }
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', abs(amt_b), None, params)
                            
                            #print(binanceX.create_market_sell_order(Target_Coin_Ticker, abs(amt_b), params))
                            

                        if abs(amt_s) > 0:

                            params = {
                                'positionSide': 'SHORT'
                            }
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', abs(amt_s), None, params)
                            
                            #print(binanceX.create_market_buy_order(Target_Coin_Ticker, abs(amt_s), params))


                        msg = Target_Coin_Ticker + " 이평무한매수양방향봇 모두 팔아서 손익확정!!!!  [" + str(TotalRevenue) + "] 손익 조으다!"
                        print(msg) 
                        line_alert.SendMessage(msg) 



                        CoinInfo['Long_Round'] = 0    #현재 회차

                        CoinInfo['Long_WaterAmt'] = 0 #물탄 수량!
                        CoinInfo['Long_WaterLossMoney'] = 0 #물탄 수량을 팔때 손해본 금액


                        CoinInfo['Short_Round'] = 0    #현재 회차

                        CoinInfo['Short_WaterAmt'] = 0 #물탄 수량!
                        CoinInfo['Short_WaterLossMoney'] = 0 #물탄 수량을 팔때 손해본 금액


                        CoinInfo['IsReady'] = 'N'


                            
                        #파일에 저장
                        with open(bot_file_path, 'w') as outfile:
                            json.dump(InfinityMaDataList, outfile)


                  
                    else:







                        #매수는 타임 프레임마다!!
                        if CoinInfo['IsReady'] == 'Y':


                            #롱과 숏에 할당된 투자 수량
                            Long_Max_Amt = Max_Amt * CoinInfo['long_momentum_score']
                            Short_Max_Amt = Max_Amt * CoinInfo['short_momentum_score']
        
                            print("Long_Max_Amt:", Long_Max_Amt)
                            print("Short_Max_Amt:", Short_Max_Amt)

                            #50분할하여 1회차 투자 금액 확정!
                            Long_Amt = Long_Max_Amt / 50.0
                            Short_Amt= Short_Max_Amt / 50.0
                            print("Long_Amt:", Long_Amt)
                            print("Short_Amt:", Short_Amt)

                            if abs(amt_b) > 0:
                                CoinInfo['Long_Round'] = abs(amt_b) / Long_Amt


                            if abs(amt_s) > 0:
                                CoinInfo['Short_Round'] = abs(amt_s) / Short_Amt




                            #5일선 밑에 있는 하락세다!!!
                            if CoinInfo['Ma5'] > CoinInfo['Now_Price'] and CoinInfo['Long_Round'] >= 1.0 and abs(amt_b) > 0:

                                Is_Cut_Ok = True
                                if CoinInfo['long_momentum_score'] > CoinInfo['short_momentum_score']:
                                    if CoinInfo['Long_Round'] < 5.0:
                                        Is_Cut_Ok = False


                                if Is_Cut_Ok == True:
                                        
                                    SellAmt = Long_Amt

                                    if SellAmt < minimun_amount:
                                        SellAmt = minimun_amount


                                    params = {
                                        'positionSide': 'LONG'
                                    }
                                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', SellAmt, None, params)

                                    CoinInfo['Long_Round'] -= 1.0


                                    #단 현재 수익금이 마이너스 즉 손실 상태라면 손실 금액을 저장해 둔다!
                                    if unrealizedProfit_b_f < 0:
                                        #손실 금액에서 매도수량/보유수량 즉 예로 10개보유 하고 현재 -100달러인데 5개를 파는 거라면 실제 확정 손실금은 -100 * (5/10)이 니깐~
                                        LossMoney = abs(unrealizedProfit_b_f) * (float(SellAmt) / float(abs(amt_b)))
                                        CoinInfo['Long_WaterLossMoney'] += LossMoney

                                        msg = Target_Coin_Ticker + " 5일선 밑에 있어서 롱 1회차 손절합니다!  약 [" + str(LossMoney) + "] 확정손실이 나서 기록했으며 롱 누적 손실은 [" + str(CoinInfo['Long_WaterLossMoney']) + "] 입니다"
                                        print(msg) 
                                        line_alert.SendMessage(msg) 

                                    #이 경우는 이득 본 경우다! 목표 %에 못 도달했지만 수익권이긴 한 상태.
                                    else:

                                        #이득본 금액도 계산해보자
                                        RevenuMoney = abs(unrealizedProfit_b_f) * (float(SellAmt) / float(abs(amt_b)))

                                        #혹시나 저장된 손실본 금액이 있다면 줄여 준다! (빠른 탈출을 위해)
                                        if CoinInfo['Long_WaterLossMoney'] > 0:
                                            CoinInfo['Long_WaterLossMoney'] -= RevenuMoney #저 데이터는 손실금을 저장하는 곳이니 빼준다

                                            #수익금을 뺐더니 손실금이 음수라면 0으로 처리해 준다!
                                            #if CoinInfo['Long_WaterLossMoney'] < 0:
                                            #   CoinInfo['Long_WaterLossMoney'] = 0


                                        msg = Target_Coin_Ticker + " 5일선 밑에 있어서 롱 1회차 정리합니다!  약 [" + str(RevenuMoney) + "] 확정 수익이 났네요!"
                                        print(msg)  
                                        line_alert.SendMessage(msg) 

    
                            #5일선 위에 있는 상승세다!!!
                            if CoinInfo['Ma5'] < CoinInfo['Now_Price'] and CoinInfo['Short_Round'] >= 1.0 and abs(amt_s) > 0:
                

                                Is_Cut_Ok = True
                                if CoinInfo['long_momentum_score'] < CoinInfo['short_momentum_score']:
                                    if CoinInfo['Short_Round'] < 5.0:
                                        Is_Cut_Ok = False


                                if Is_Cut_Ok == True:


                                    SellAmt = Short_Amt

                                    if SellAmt < minimun_amount:
                                        SellAmt = minimun_amount



                                    params = {
                                        'positionSide': 'SHORT'
                                    }
                                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', SellAmt, None, params)
                                    #print(binanceX.create_market_buy_order(Target_Coin_Ticker, HalfAmt, params))
                                    

                                    CoinInfo['Short_Round'] -= 1.0

                                    #단 현재 수익금이 마이너스 즉 손실 상태라면 손실 금액을 저장해 둔다!
                                    if unrealizedProfit_s_f < 0:
                                        #손실 금액에서 매도수량/보유수량 즉 예로 10개보유 하고 현재 -100달러인데 5개를 파는 거라면 실제 확정 손실금은 -100 * (5/10)이 니깐~
                                        LossMoney = abs(unrealizedProfit_s_f) * (float(SellAmt) / float(abs(amt_s)))
                                        CoinInfo['Short_WaterLossMoney'] += LossMoney

                                        msg = Target_Coin_Ticker + " 5일선 위에 있어서 숏 1회차 손절합니다! 약 [" + str(LossMoney) + "] 확정손실이 나서 기록했으며 숏 누적 손실은 [" + str(CoinInfo['Short_WaterLossMoney']) + "] 입니다"
                                        print(msg) 
                                        line_alert.SendMessage(msg) 

                                    #이 경우는 이득 본 경우다! 목표 %에 못 도달했지만 수익권이긴 한 상태.
                                    else:

                                        #이득본 금액도 계산해보자
                                        RevenuMoney = abs(unrealizedProfit_s_f) * (float(SellAmt) / float(abs(amt_s)))

                                        #혹시나 저장된 손실본 금액이 있다면 줄여 준다! (빠른 탈출을 위해)
                                        if CoinInfo['Short_WaterLossMoney'] > 0:
                                            CoinInfo['Short_WaterLossMoney'] -= RevenuMoney #저 데이터는 손실금을 저장하는 곳이니 빼준다

                                            #수익금을 뺐더니 손실금이 음수라면 0으로 처리해 준다!
                                            #if CoinInfo['Short_WaterLossMoney'] < 0:
                                            #   CoinInfo['Short_WaterLossMoney'] = 0


                                        msg = Target_Coin_Ticker + " 5일선 위에 있어서 숏 1회차 정리합니다! 약 [" + str(RevenuMoney) + "] 확정 수익이 났네요!"
                                        print(msg) 
                                        line_alert.SendMessage(msg) 








                            if CoinInfo['Long_Round'] >= 40:

                                if CoinInfo['Ma5_before'] > CoinInfo['Ma5']:


                                    #절반을 손절처리 한다
                                    HalfAmt = abs(amt_b) * 0.5


                                    params = {
                                        'positionSide': 'LONG'
                                    }
                                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', HalfAmt, None, params)
                                    #print(binanceX.create_market_sell_order(Target_Coin_Ticker, HalfAmt, params))
                                    

                                    CoinInfo['Long_Round'] = 21 #라운드는 절반을 팔았으니깐 21회로 초기화

                                    #단 현재 수익금이 마이너스 즉 손실 상태라면 손실 금액을 저장해 둔다!
                                    if unrealizedProfit_b_f < 0:
                                        #손실 금액에서 매도수량/보유수량 즉 예로 10개보유 하고 현재 -100달러인데 5개를 파는 거라면 실제 확정 손실금은 -100 * (5/10)이 니깐~
                                        LossMoney = abs(unrealizedProfit_b_f) * (float(HalfAmt) / float(abs(amt_b)))
                                        CoinInfo['Long_WaterLossMoney'] += LossMoney

                                        msg = Target_Coin_Ticker + "롱 40회가 소진되어 절반 손절합니다! 약 [" + str(LossMoney) + "] 확정손실이 나서 기록했으며 롱 누적 손실은 [" + str(CoinInfo['Long_WaterLossMoney']) + "] 입니다"
                                        print(msg) 
                                        line_alert.SendMessage(msg) 

                                    #이 경우는 이득 본 경우다! 목표 %에 못 도달했지만 수익권이긴 한 상태.
                                    else:

                                        #이득본 금액도 계산해보자
                                        RevenuMoney = abs(unrealizedProfit_b_f) * (float(HalfAmt) / float(abs(amt_b)))

                                        #혹시나 저장된 손실본 금액이 있다면 줄여 준다! (빠른 탈출을 위해)
                                        if CoinInfo['Long_WaterLossMoney'] > 0:
                                            CoinInfo['Long_WaterLossMoney'] -= RevenuMoney #저 데이터는 손실금을 저장하는 곳이니 빼준다

                                            #수익금을 뺐더니 손실금이 음수라면 0으로 처리해 준다!
                                            #if CoinInfo['Long_WaterLossMoney'] < 0:
                                            #   CoinInfo['Long_WaterLossMoney'] = 0


                                        msg = Target_Coin_Ticker + "롱 40회가 소진되어 절반 매도합니다! 약 [" + str(RevenuMoney) + "] 확정 수익이 났네요!"
                                        print(msg) 
                                        line_alert.SendMessage(msg) 


                            if CoinInfo['Short_Round'] >= 40:

                                if CoinInfo['Ma5_before'] < CoinInfo['Ma5']:


                                    #절반을 손절처리 한다
                                    HalfAmt = abs(amt_s) * 0.5


                                    params = {
                                        'positionSide': 'SHORT'
                                    }
                                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', HalfAmt, None, params)
                                    #print(binanceX.create_market_buy_order(Target_Coin_Ticker, HalfAmt, params))
                                    

                                    CoinInfo['Short_Round'] = 21 #라운드는 절반을 팔았으니깐 21회로 초기화

                                    #단 현재 수익금이 마이너스 즉 손실 상태라면 손실 금액을 저장해 둔다!
                                    if unrealizedProfit_s_f < 0:
                                        #손실 금액에서 매도수량/보유수량 즉 예로 10개보유 하고 현재 -100달러인데 5개를 파는 거라면 실제 확정 손실금은 -100 * (5/10)이 니깐~
                                        LossMoney = abs(unrealizedProfit_s_f) * (float(HalfAmt) / float(abs(amt_s)))
                                        CoinInfo['Short_WaterLossMoney'] += LossMoney

                                        msg = Target_Coin_Ticker + "롱 40회가 소진되어 절반 손절합니다! 약 [" + str(LossMoney) + "] 확정손실이 나서 기록했으며 숏 누적 손실은 [" + str(CoinInfo['Short_WaterLossMoney']) + "] 입니다"
                                        print(msg) 
                                        line_alert.SendMessage(msg) 

                                    #이 경우는 이득 본 경우다! 목표 %에 못 도달했지만 수익권이긴 한 상태.
                                    else:

                                        #이득본 금액도 계산해보자
                                        RevenuMoney = abs(unrealizedProfit_s_f) * (float(HalfAmt) / float(abs(amt_s)))

                                        #혹시나 저장된 손실본 금액이 있다면 줄여 준다! (빠른 탈출을 위해)
                                        if CoinInfo['Short_WaterLossMoney'] > 0:
                                            CoinInfo['Short_WaterLossMoney'] -= RevenuMoney #저 데이터는 손실금을 저장하는 곳이니 빼준다

                                            #수익금을 뺐더니 손실금이 음수라면 0으로 처리해 준다!
                                            #if CoinInfo['Short_WaterLossMoney'] < 0:
                                            #   CoinInfo['Short_WaterLossMoney'] = 0


                                        msg = Target_Coin_Ticker + "롱 40회가 소진되어 절반 매도합니다! 약 [" + str(RevenuMoney) + "] 확정 수익이 났네요!"
                                        print(msg) 
                                        line_alert.SendMessage(msg) 





                            IsLongBuyGo = False #매수 하는지!

                            #라운드에 따라 매수 조건이 다르다!
                            if CoinInfo['Long_Round'] <= 5-1:

                                #롱 모멘텀이 우세하다면! 기존대로!
                                if CoinInfo['long_momentum_score'] > CoinInfo['short_momentum_score']:

                                    #여기는 무조건 매수
                                    IsLongBuyGo = True
                                
                                else:
                                    #현재가가 5일선 위에 있을 때만 매수
                                    if CoinInfo['Ma5'] < CoinInfo['Now_Price']:
                                        IsLongBuyGo = True

                            elif CoinInfo['Long_Round'] <= 20-1:


                                #롱 모멘텀이 우세하다면! 기존대로!
                                if CoinInfo['long_momentum_score'] > CoinInfo['short_momentum_score']:
                                    #현재가가 5일선 위에 있을 때만 매수
                                    if CoinInfo['Ma5'] < CoinInfo['Now_Price']:
                                        IsLongBuyGo = True
                                else:
                                    #현재가가 5일선 / 20일선 위에 있고 이전 봉이 양봉일 때만 매수
                                    if CoinInfo['Ma20'] < CoinInfo['Now_Price'] and CoinInfo['Ma5'] < CoinInfo['Now_Price'] and CoinInfo['IsUpCandle'] == 1:
                                        IsLongBuyGo = True                   

                            elif CoinInfo['Long_Round'] <= 30-1:


                                #롱 모멘텀이 우세하다면! 기존대로!
                                if CoinInfo['long_momentum_score'] > CoinInfo['short_momentum_score']:

                                    #현재가가 5일선 위에 있고 이전 봉이 양봉일 때만 매수
                                    if CoinInfo['Ma20'] < CoinInfo['Now_Price'] and CoinInfo['Ma5'] < CoinInfo['Now_Price'] and CoinInfo['IsUpCandle'] == 1:
                                        IsLongBuyGo = True
                                else:

                                    #현재가가 5/20일선 위에 있고 이전 봉이 양봉일때 그리고 5일선, 20일선 둘다 증가추세에 있을 때만 매수
                                    if CoinInfo['Ma20'] < CoinInfo['Now_Price'] and CoinInfo['Ma5'] < CoinInfo['Now_Price'] and CoinInfo['IsUpCandle'] == 1 and CoinInfo['Ma5_before'] < CoinInfo['Ma5'] and CoinInfo['Ma20_before'] < CoinInfo['Ma20']:
                                        IsLongBuyGo = True

                            elif CoinInfo['Long_Round'] <= 40-1:

                                #현재가가 5/20일선 위에 있고 이전 봉이 양봉일때 그리고 5일선, 20일선 둘다 증가추세에 있을 때만 매수
                                if CoinInfo['Ma20'] < CoinInfo['Now_Price'] and CoinInfo['Ma5'] < CoinInfo['Now_Price'] and CoinInfo['IsUpCandle'] == 1 and CoinInfo['Ma5_before'] < CoinInfo['Ma5'] and CoinInfo['Ma20_before'] < CoinInfo['Ma20']:
                                    IsLongBuyGo = True





                            #숏일 경우
                            IsShortBuyGo = False #매수 하는지!

                            #라운드에 따라 매수 조건이 다르다!
                            if CoinInfo['Short_Round'] <= 5-1:
                                #숏 모멘텀이 우세하다면! 기존대로!
                                if CoinInfo['long_momentum_score'] < CoinInfo['short_momentum_score']:

                                    #여기는 무조건 매수
                                    IsShortBuyGo = True

                                else:
                                    #현재가가 5일선 아래에 있을 때만 매수
                                    if CoinInfo['Ma5'] > CoinInfo['Now_Price']:
                                        IsShortBuyGo = True

                            elif CoinInfo['Short_Round'] <= 20-1:
                                #숏 모멘텀이 우세하다면! 기존대로!
                                if CoinInfo['long_momentum_score'] < CoinInfo['short_momentum_score']:

                                    #현재가가 5일선 아래에 있을 때만 매수
                                    if CoinInfo['Ma5'] > CoinInfo['Now_Price']:
                                        IsShortBuyGo = True

                                else:

                                    #현재가가 5/20일선 아래에 있고 이전 봉이 음봉 때만 매수
                                    if CoinInfo['Ma20'] > CoinInfo['Now_Price'] and CoinInfo['Ma5'] > CoinInfo['Now_Price'] and CoinInfo['IsUpCandle'] == 0:
                                        IsShortBuyGo = True

                            elif CoinInfo['Short_Round'] <= 30-1:
                                #숏 모멘텀이 우세하다면! 기존대로!
                                if CoinInfo['long_momentum_score'] < CoinInfo['short_momentum_score']:

                                    #현재가가 5/20일선 아래에 있고 이전 봉이 음봉 때만 매수
                                    if CoinInfo['Ma20'] > CoinInfo['Now_Price'] and CoinInfo['Ma5'] > CoinInfo['Now_Price'] and CoinInfo['IsUpCandle'] == 0:
                                        IsShortBuyGo = True

                                else:

                                    #현재가가 5/20일선 아래에 있고 이전 봉이 음봉 때 그리고 5일선, 20일선 둘다 감소 추세에 있을 때만 매수
                                    if CoinInfo['Ma20'] > CoinInfo['Now_Price'] and CoinInfo['Ma5'] > CoinInfo['Now_Price'] and CoinInfo['IsUpCandle'] == 0 and CoinInfo['Ma5_before'] > CoinInfo['Ma5'] and CoinInfo['Ma20_before'] > CoinInfo['Ma20']:
                                        IsShortBuyGo = True

                            elif CoinInfo['Short_Round'] <= 40-1:

                                #현재가가 5/20일선 아래에 있고 이전 봉이 음봉 때 그리고 5일선, 20일선 둘다 감소 추세에 있을 때만 매수
                                if CoinInfo['Ma20'] > CoinInfo['Now_Price'] and CoinInfo['Ma5'] > CoinInfo['Now_Price'] and CoinInfo['IsUpCandle'] == 0 and CoinInfo['Ma5_before'] > CoinInfo['Ma5'] and CoinInfo['Ma20_before'] > CoinInfo['Ma20']:
                                    IsShortBuyGo = True






                            #한 회차 매수 한다!!
                            if IsLongBuyGo == True:

                                BuyAmt = Long_Amt
                                #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                                if Long_Amt < minimun_amount:
                                    BuyAmt = minimun_amount

                                    CoinInfo['Long_Round'] += (float(Long_Amt)/float(minimun_amount))
                                else:
                                    CoinInfo['Long_Round'] += 1 #라운드 증가!


                                params = {
                                    'positionSide': 'LONG'
                                }
                                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', BuyAmt, None, params)
                                #print(binanceX.create_market_buy_order(Target_Coin_Ticker, BuyAmt, params))
                                

                                msg = Target_Coin_Ticker + " 롱 이평무한매수양방향봇 " + str(CoinInfo['Long_Round']) + "회차 매수 완료!"
                                print(msg) 
                                line_alert.SendMessage(msg) 



                            #한 회차 매수 한다!!
                            if IsShortBuyGo == True:

                                BuyAmt = Short_Amt
                                #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                                if Short_Amt < minimun_amount:
                                    BuyAmt = minimun_amount

                                    CoinInfo['Short_Round'] += (float(Short_Amt)/float(minimun_amount))
                                else:
                                    CoinInfo['Short_Round'] += 1 #라운드 증가!


                                params = {
                                    'positionSide': 'SHORT'
                                }
                                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', BuyAmt, None, params)
                                #print(binanceX.create_market_sell_order(Target_Coin_Ticker, BuyAmt, params))
                                

                                msg = Target_Coin_Ticker + " 숏 이평무한매수양방향봇 " + str(CoinInfo['Short_Round']) + "회차 매수 완료!"
                                print(msg) 
                                line_alert.SendMessage(msg) 




                            ####################################################################################
                            ################## 위 정규 매수 로직과는 별개로 특별 물타기 로직을 체크하고 제어한다! #############

                            #이평선이 꺾여서 특별히 물탄 경우 수량이 0이 아닐꺼고 즉 여기는  물을 탄 상태이다!
                            if CoinInfo['Long_WaterAmt'] != 0:
                                if abs(amt_b) > 0:
                                    if abs(amt_b) < CoinInfo['Long_WaterAmt']:
                                        CoinInfo['Long_WaterAmt'] = abs(amt_b)
                                        
        
                                    params = {
                                        'positionSide': 'LONG'
                                    }
                                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', CoinInfo['Long_WaterAmt'], None, params)
                                    #print(binanceX.create_market_sell_order(Target_Coin_Ticker, CoinInfo['Long_WaterAmt'], params))
                                    


                                    #단 현재 수익금이 마이너스 즉 손실 상태라면 손실 금액을 저장해 둔다!
                                    if unrealizedProfit_b_f < 0:
                                        #손실 금액에서 매도수량/보유수량 즉 예로 10개보유 하고 현재 -100달러인데 5개를 파는 거라면 실제 확정 손실금은 -100 * (5/10)이 니깐~
                                        LossMoney = abs(unrealizedProfit_b_f) * (CoinInfo['Long_WaterAmt'] / float(abs(amt_b)))
                                        CoinInfo['Long_WaterLossMoney'] += LossMoney

                                        msg = Target_Coin_Ticker + "롱 평단을 확 낮추기 위한 이평무한매수양방향봇 물탔는데 익절구간이라 그 수량만큼 매도합니다 약 [" + str(LossMoney) + "] 확정손실이 나서 기록했으며 누적 손실은 [" + str(CoinInfo['Long_WaterLossMoney']) + "] 입니다"
                                        print(msg) 
                                        line_alert.SendMessage(msg) 

                                    #이 경우는 이득 본 경우다! 목표 %에 못 도달했지만 수익권이긴 한 상태.
                                    else:

                                        #이득본 금액도 계산해보자
                                        RevenuMoney = abs(unrealizedProfit_b_f) * (CoinInfo['Long_WaterAmt'] / float(abs(amt_b)))

                                        #혹시나 저장된 손실본 금액이 있다면 줄여 준다! (빠른 탈출을 위해)
                                        if CoinInfo['Long_WaterLossMoney'] > 0:
                                            CoinInfo['Long_WaterLossMoney'] -= RevenuMoney #저 데이터는 손실금을 저장하는 곳이니 빼준다

                                            #수익금을 뺐더니 손실금이 음수라면 0으로 처리해 준다!
                                            if CoinInfo['Long_WaterLossMoney'] < 0:
                                                CoinInfo['Long_WaterLossMoney'] = 0


                                        msg = Target_Coin_Ticker + "롱 평단을 확 낮추기 위한 이평무한매수양방향봇 물탔는데 익절구간이라 그 수량만큼 매도합니다! 약 [" + str(RevenuMoney) + "] 확정 수익이 났네요!"
                                        print(msg) 
                                        line_alert.SendMessage(msg) 


                                    CoinInfo['Long_WaterAmt'] = 0 #팔았으니 0으로 초기화!



                            #이평선이 꺾여서 특별히 물탄 경우 수량이 0이 아닐꺼고 즉 여기는  물을 탄 상태이다!
                            if CoinInfo['Short_WaterAmt'] != 0:
                                if abs(amt_s) > 0:
                                    if abs(amt_s) < CoinInfo['Short_WaterAmt']:
                                        CoinInfo['Short_WaterAmt'] = abs(amt_s)

                                    params = {
                                        'positionSide': 'SHORT'
                                    }
                                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', CoinInfo['Short_WaterAmt'], None, params)
                                    #print(binanceX.create_market_buy_order(Target_Coin_Ticker, CoinInfo['Short_WaterAmt'], params))
                                    


                                    #단 현재 수익금이 마이너스 즉 손실 상태라면 손실 금액을 저장해 둔다!
                                    if unrealizedProfit_s_f < 0:
                                        #손실 금액에서 매도수량/보유수량 즉 예로 10개보유 하고 현재 -100달러인데 5개를 파는 거라면 실제 확정 손실금은 -100 * (5/10)이 니깐~
                                        LossMoney = abs(unrealizedProfit_s_f) * (CoinInfo['Short_WaterAmt'] / float(abs(amt_s)))
                                        CoinInfo['Short_WaterLossMoney'] += LossMoney

                                        msg = Target_Coin_Ticker + "숏 평단을 확 낮추기 위한 이평무한매수양방향봇 물탔는데 익절구간이라 그 수량만큼 매도합니다 약 [" + str(LossMoney) + "] 확정손실이 나서 기록했으며 누적 손실은 [" + str(CoinInfo['Short_WaterLossMoney']) + "] 입니다"
                                        print(msg) 
                                        line_alert.SendMessage(msg) 

                                    #이 경우는 이득 본 경우다! 목표 %에 못 도달했지만 수익권이긴 한 상태.
                                    else:

                                        #이득본 금액도 계산해보자
                                        RevenuMoney = abs(unrealizedProfit_s_f) * (CoinInfo['Short_WaterAmt'] / float(abs(amt_s)))

                                        #혹시나 저장된 손실본 금액이 있다면 줄여 준다! (빠른 탈출을 위해)
                                        if CoinInfo['Short_WaterLossMoney'] > 0:
                                            CoinInfo['Short_WaterLossMoney'] -= RevenuMoney #저 데이터는 손실금을 저장하는 곳이니 빼준다

                                            #수익금을 뺐더니 손실금이 음수라면 0으로 처리해 준다!
                                            #if CoinInfo['Short_WaterLossMoney'] < 0:
                                            #    CoinInfo['Short_WaterLossMoney'] = 0


                                        msg = Target_Coin_Ticker + "숏 평단을 확 낮추기 위한 이평무한매수양방향봇 물탔는데 익절구간이라 그 수량만큼 매도합니다! 약 [" + str(RevenuMoney) + "] 확정 수익이 났네요!"
                                        print(msg) 
                                        line_alert.SendMessage(msg) 


                                    CoinInfo['Short_WaterAmt'] = 0 #팔았으니 0으로 초기화!
        


                            
                            if CoinInfo['Ma5'] < CoinInfo['Ma20'] and CoinInfo['Ma5_before3'] > CoinInfo['Ma5_before'] and CoinInfo['Ma5_before'] < CoinInfo['Ma5'] and CoinInfo['Long_Round'] > 1 and CoinInfo['Long_WaterAmt'] == 0:


                                BuyRound = int(CoinInfo['Long_Round']/4) + 1 #물탈 회수

                                BuyAmt = (Max_Amt/50.0) * float(BuyRound)
                                #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                                if BuyAmt < minimun_amount:
                                    BuyAmt = minimun_amount

                                params = {
                                    'positionSide': 'LONG'
                                }
                                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', BuyAmt, None, params)
                                
                                #data = binanceX.create_market_buy_order(Target_Coin_Ticker, BuyAmt, params)


                                CoinInfo['Long_WaterAmt'] = float(data['amount'])
                                

                                msg = Target_Coin_Ticker + "  이평선이 위로 꺾였어요! 평단을 확 낮추기 위한 이평무한매수양방향봇 물을 탑니다!! 롱 [" + str(BuyRound) + "] 회차 만큼의 수량을 추가 했어요!"
                                print(msg) 
                                line_alert.SendMessage(msg) 


                            if CoinInfo['Ma5'] > CoinInfo['Ma20'] and CoinInfo['Ma5_before3'] < CoinInfo['Ma5_before'] and CoinInfo['Ma5_before'] > CoinInfo['Ma5'] and CoinInfo['Short_Round'] > 1 and CoinInfo['Short_WaterAmt'] == 0:


                                BuyRound = int(CoinInfo['Short_Round']/4) + 1 #물탈 회수

                                BuyAmt = (Max_Amt/50.0) * float(BuyRound)
                                #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                                if BuyAmt < minimun_amount:
                                    BuyAmt = minimun_amount

                                params = {
                                    'positionSide': 'SHORT'
                                }
                                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', BuyAmt, None, params)
                                
                                #data = binanceX.create_market_sell_order(Target_Coin_Ticker, BuyAmt, params)
                                


                                CoinInfo['Short_WaterAmt'] = float(data['amount'])


                                msg = Target_Coin_Ticker + "  이평선이 아래로 꺾였어요! 평단을 확 낮추기 위한 이평무한매수양방향봇 물을 탑니다!! 숏 [" + str(BuyRound) + "] 회차 만큼의 수량을 추가 했어요!"
                                print(msg) 
                                line_alert.SendMessage(msg) 
                            
                        #########################################################################################


                        #위 로직 완료하면 N으로 바꾸고 다음 타임 프레임 기다림!
                        CoinInfo['IsReady'] = 'N' 

                        #파일에 저장
                        with open(bot_file_path, 'w') as outfile:
                            json.dump(InfinityMaDataList, outfile)
                        
                            




    except Exception as e:
        print("Exception:", e)








