'''
-*- 백테스팅 코드가 있는 전략들은 패키지 16번 부터 나오기 시작하니 참고하세요!! -*-

관련 포스팅

#################################################################
불행히도 현재 수수료가 무료가 아니기 때문에 이 전략은 유효하지 않습니다!!! ㅠ.ㅜ 
참고만 하세요!!!
#################################################################

바이낸스 비트코인 현물 수수료 무료! 이평무한매수봇으로 수익내자!
https://blog.naver.com/zacra/222981499437

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

import json
import line_alert

#크론탭에 1분 혹은 5분마다 돌게 세팅합니다!

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
        'defaultType': 'spot'
    }
})


#선물 마켓에서 거래중인 모든 코인을 가져옵니다.
Tickers = binanceX.fetch_tickers()

Invest_Rate = 1.0

#########################-트레일링스탑 적용-#######################
TraillingStopRate = 0.01 #1%기준으로 트레일링 스탑!
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#


#나의 코인
LovelyCoinList = ['BTC/USDT']

CoinCnt = len(LovelyCoinList)




#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#
############# 해당 전략으로 매수한 종목 데이터 리스트 ####################
InfinityMaDataList = list()
#파일 경로입니다.
bot_file_path = "/var/autobot/BinanceSpotMAInfinityFinalhourV2.json"

try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(bot_file_path, 'r') as json_file:
        InfinityMaDataList = json.load(json_file)

except Exception as e:
    print("Exception by First")
################################################################
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#

#시간 정보를 읽는다
time_info = time.gmtime()
print("time_info.tm_mday: " , time_info.tm_mday)
min = time_info.tm_min




#잔고 데이타 가져오기 
balance = binanceX.fetch_balance(params={"type": "spot"})


CoinMoney = 0


for ticker in LovelyCoinList:

    try: 

        Target_Coin_Ticker = ticker

        Target_Coin_Symbol = ticker.replace("/", "").replace(":USDT", "")

        
        #해당 코인 가격을 가져온다.
        coin_price = myBinance.GetCoinNowPrice(binanceX, Target_Coin_Ticker)
        
        #해당 코인 보유 수량
        coin_amt = float(balance[ticker.split('/')[0]]['total'])

        CoinMoney = coin_amt * coin_price


        #해당 코인에 할당된 금액에 따른 최대 매수수량을 구해본다!
        Max_Amt = float(binanceX.amount_to_precision(Target_Coin_Ticker, myBinance.GetAmount((float(balance['USDT']['total']) + CoinMoney),coin_price,Invest_Rate ))) / float(CoinCnt)


        print("coin_amt ", coin_amt)
        print("CoinMoney ", CoinMoney)


        Buy_Amt = Max_Amt / 50.0 #50분할!

        print("Max_Amt ", Max_Amt)
        print("Buy_Amt ", Buy_Amt)

        
            
        #종목 데이터
        PickCoinInfo = None

        #저장된 종목 데이터를 찾는다
        for CoinInfo in InfinityMaDataList:
            if CoinInfo['Ticker'] == Target_Coin_Ticker:
                PickCoinInfo = CoinInfo
                break



        if PickCoinInfo == None:
        
            #잔고가 없다 즉 처음이다!!!
            if coin_amt < Buy_Amt:

                InfinityDataDict = dict()
                
                InfinityDataDict['Ticker'] = Target_Coin_Ticker #종목 코드

                InfinityDataDict['Date'] = time_info.tm_hour

                InfinityDataDict['Round'] = 0    #현재 회차
                InfinityDataDict['IsCheck'] = 'Y' #하루에 한번 체크하고 매수등의 처리를 하기 위한 플래그

                InfinityDataDict['S_WaterAmt'] = 0 #물탄 수량!
                InfinityDataDict['S_WaterLossMoney'] = 0 #물탄 수량을 팔때 손해본 금액

                InfinityDataDict['TrallingPrice'] = 0 #트레일링 추적할 가격
                InfinityDataDict['IsTralling'] = 'N' #트레일링 시작 여부

                InfinityDataDict['TotalBuyMoney'] = 0 #총매수금액 - 이걸 나중에 수량으로 나눠야 평단을 알 수 있다!


                InfinityMaDataList.append(InfinityDataDict) #데이터를 추가 한다!


                msg = Target_Coin_Ticker + " 바이낸스 수수료 무료 스팟 비트코인 무한매수 첫 시작!!!!"
                print(msg) 
                line_alert.SendMessage(msg) 


                #파일에 저장
                with open(bot_file_path, 'w') as outfile:
                    json.dump(InfinityMaDataList, outfile)
                        
        



        #이제 데이터(InfinityMaDataList)는 확실히 있을 테니 본격적으로 트레이딩을 합니다!
        for CoinInfo in InfinityMaDataList:

            if CoinInfo['Ticker'] == Target_Coin_Ticker:

                print(" CoinInfo['Round']: ", CoinInfo['Round'])

                #1회차 이상 매수된 상황이라면 익절 조건을 체크해서 익절 처리 해야 한다!
                if CoinInfo['Round'] > 0 :
                    coin_revenue_money = CoinMoney - CoinInfo['TotalBuyMoney']
                    print(">>> coin_revenue_money : ", coin_revenue_money)
                    print(">>> CoinInfo['TotalBuyMoney']: ", CoinInfo['TotalBuyMoney'])

                    #$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#
                    #########################-트레일링스탑 적용-#######################
                    #트레일링 스탑이 시작되었다면 이전에 저장된 값 대비 트레일링 스탑 비중만큼 떨어졌다면 스탑!
                    #아니라면 고점 갱신해줍니다!!
                    if CoinInfo['IsTralling'] == 'Y':

                        #스탑할 가격을 구합니다.
                        StopPrice = CoinInfo['TrallingPrice'] * (1.0 - TraillingStopRate)

                        #스탑할 가격보다 작아졌다면
                        if coin_price <= StopPrice:

                            
                            #남은 수량을 매도 
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', coin_amt)
                            
                            msg = "이평무한매수봇 모두 팔아서 수익확정!!!!  [" + str(coin_revenue_money) + "] 수익 조으다! (현재 [" + str(CoinInfo['Round']) + "] 라운드까지 진행되었고 모든 수량 매도 처리! )"
                            print(Target_Coin_Ticker + " " + msg) 
                            line_alert.SendMessage(Target_Coin_Ticker + " " + msg) 

                            #전량 매도 모두 초기화! 
                            CoinInfo['TrallingPrice'] = 0
                            CoinInfo['IsTralling'] = 'N' 
                            CoinInfo['Round'] = 0
                            CoinInfo['IsCheck'] = 'N' #익절한 날은 매수 안하고 즐기자!
                            CoinInfo['S_WaterAmt'] = 0 #물탄 수량 초기화 
                            CoinInfo['S_WaterLossMoney'] = 0 #물탄 수량을 팔때 손해본 금액 초기화!
                            CoinInfo['TotalBuyMoney'] = 0

                            #파일에 저장
                            with open(bot_file_path, 'w') as outfile:
                                json.dump(InfinityMaDataList, outfile)

                        #현재가가 이전에 저장된 가격보다 높아졌다면 고점 갱신!!!
                        if CoinInfo['TrallingPrice'] < coin_price:

                            CoinInfo['TrallingPrice'] = coin_price

                            #파일에 저장
                            with open(bot_file_path, 'w') as outfile:
                                json.dump(InfinityMaDataList, outfile)

                    #트레일링 스탑 아직 시작 안됨!
                    else:

                        #목표 수익률을 구한다! 
                        '''
                        1회 :  10% + 1%
                        10회  8.5% + 1%
                        20회  7%
                        30회  5.5%
                        40회 : 4%
                        '''
                        TargetRate = (10.0 - CoinInfo['Round']*0.15) / 100.0

                        #현재총평가금액은 물타기 손실금액을 반영한게 아니다.
                        #손실액이 현재 평가금액 대비 비중이 얼마인지 체크한다. 
                        PlusRate = CoinInfo['S_WaterLossMoney'] / CoinMoney

                        #그래서 목표수익률이랑 손실액을 커버하기 위한 수익률을 더해준다! + 트레일링 스탑 기준도 더해서 수익 확보!
                        FinalRate = TargetRate + PlusRate + TraillingStopRate

                        print("TargetRate:", TargetRate , "+ PlusRate:" ,PlusRate , "  -> FinalRate:" , FinalRate)
                        #수익화할 가격을 구한다!
                        RevenuePrice = (CoinInfo['TotalBuyMoney']/coin_amt) * (1.0 + FinalRate) 
                        
                        print("CurrentPrice:", coin_price, " >=  RevenuePrice:", RevenuePrice)

                        #목표한 수익가격보다 현재가가 높다면 익절처리할 순간이다!
                        if coin_price >= RevenuePrice:
                            
                            #그런데 현재 수량이 1회차보다 작거나 같다면 그냥 모두 판다!
                            if coin_amt <= Buy_Amt:
                                    

                                
                                #남은 수량을 매도 
                                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', coin_amt)
                                    

                                msg = "이평무한매수봇 모두 팔아서 수익확정!!!!  [" + str(coin_revenue_money) + "] 수익 조으다! (현재 [" + str(CoinInfo['Round']) + "] 라운드까지 진행되었고 모든 수량 매도 처리! )"
                                print(Target_Coin_Ticker + " " + msg) 
                                line_alert.SendMessage(Target_Coin_Ticker + " " + msg) 

                                #전량 매도 모두 초기화! 
                                CoinInfo['TrallingPrice'] = 0
                                CoinInfo['IsTralling'] = 'N' 
                                CoinInfo['Round'] = 0
                                CoinInfo['IsCheck'] = 'N' #익절한 날은 매수 안하고 즐기자!
                                CoinInfo['S_WaterAmt'] = 0 #물탄 수량 초기화 
                                CoinInfo['S_WaterLossMoney'] = 0 #물탄 수량을 팔때 손해본 금액 초기화!
                                CoinInfo['TotalBuyMoney'] = 0

                                #파일에 저장
                                with open(bot_file_path, 'w') as outfile:
                                    json.dump(InfinityMaDataList, outfile)

                                
                            else:

                                #절반은 바로 팔고 절반은 트레일링 스탑으로 처리한다!!!
                                HalfAmt = coin_amt * 0.5
                         
                                #남은 수량을 매도 
                                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', HalfAmt)

                                CoinInfo['TotalBuyMoney'] -= (float(data['price'])*float(data['amount'])) #매도한 금액을 빼준다!
                                

                                msg = "이평무한매수봇 절반 팔아서 수익확정!!!!  [" + str(coin_revenue_money*0.5) + "] 수익 조으다! (현재 [" + str(CoinInfo['Round']) + "] 라운드까지 진행되었고 절반 익절 후 트레일링 스탑 시작!!)"
                                print(Target_Coin_Ticker + " " + msg) 
                                line_alert.SendMessage(Target_Coin_Ticker + " " + msg) 

                                CoinInfo['TrallingPrice'] = coin_price
                                CoinInfo['IsTralling'] = 'Y' #트레일링 스탑 시작!

                                #파일에 저장
                                with open(bot_file_path, 'w') as outfile:
                                    json.dump(InfinityMaDataList, outfile)



                #매수는 장이 열렸을 때 1번만 해야 되니깐! 안의 로직을 다 수행하면 N으로 바꿔준다! 그리고 트레일링 스탑이 진행중이라면 추가매수하지 않는다!
                if CoinInfo['IsCheck'] == 'Y' and CoinInfo['IsTralling'] =='N':

                    msg = "이평무한매수봇 오늘 로직 시작!!"
                    print(Target_Coin_Ticker + " " + msg) 
                    line_alert.SendMessage(Target_Coin_Ticker + " " + msg) 



                    df= myBinance.GetOhlcv(binanceX,Target_Coin_Ticker, '1h')


                    #5일 이평선
                    Ma5_before3 = myBinance.GetMA(df,5,-4)
                    Ma5_before = myBinance.GetMA(df,5,-3)
                    Ma5 = myBinance.GetMA(df,5,-2)

                    print("MA5",Ma5_before3, "->", Ma5_before, "-> ",Ma5)

                    #20일 이평선
                    Ma20_before = myBinance.GetMA(df,20,-3)
                    Ma20 = myBinance.GetMA(df,20,-2)

                    print("MA20", Ma20_before, "-> ",Ma20)

                    #양봉 캔들인지 여부
                    IsUpCandle = False

                    #시가보다 종가가 크다면 양봉이다
                    if df['open'].iloc[-2] <= df['close'].iloc[-2]:
                        IsUpCandle = True

                    print("IsUpCandle : ", IsUpCandle)




                            
                    #40회를 넘었다면! 풀매수 상태이다!
                    if CoinInfo['Round'] >= 40:
                        #그런데 애시당초 후반부는 5일선이 증가추세일때만 매매 하므로 5일선이 하락으로 바뀌었다면 이때 손절처리를 한다
                        if Ma5_before > Ma5:
                            #절반을 손절처리 한다

                            HalfAmt = coin_amt * 0.5

                            #남은 수량을 매도 
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', HalfAmt)

                            CoinInfo['Round'] = 21 #라운드는 절반을 팔았으니깐 21회로 초기화

                            coin_revenue_money = CoinMoney - CoinInfo['TotalBuyMoney']


                            CoinInfo['TotalBuyMoney'] -= (float(data['price'])*float(data['amount'])) #매도한 금액을 빼준다!
                            



                            #단 현재 수익금이 마이너스 즉 손실 상태라면 손실 금액을 저장해 둔다!
                            if coin_revenue_money < 0:
                                #손실 금액에서 매도수량/보유수량 즉 예로 10개보유 하고 현재 -100달러인데 5개를 파는 거라면 실제 확정 손실금은 -100 * (5/10)이 니깐~
                                LossMoney = abs(coin_revenue_money) * (float(HalfAmt) / float(coin_amt))
                                CoinInfo['S_WaterLossMoney'] += LossMoney

                                msg = "40회가 소진되어 절반 손절합니다! 약 [" + str(LossMoney) + "] 확정손실이 나서 기록했으며 누적 손실은 [" + str(CoinInfo['S_WaterLossMoney']) + "] 입니다"
                                print(Target_Coin_Ticker + " " + msg) 
                                line_alert.SendMessage(Target_Coin_Ticker + " " + msg) 

                            #이 경우는 이득 본 경우다! 목표 %에 못 도달했지만 수익권이긴 한 상태.
                            else:

                                #이득본 금액도 계산해보자
                                RevenuMoney = abs(coin_revenue_money) * (float(HalfAmt) / float(coin_amt))

                                #혹시나 저장된 손실본 금액이 있다면 줄여 준다! (빠른 탈출을 위해)
                                if CoinInfo['S_WaterLossMoney'] > 0:
                                    CoinInfo['S_WaterLossMoney'] -= RevenuMoney #저 데이터는 손실금을 저장하는 곳이니 빼준다

                                    #수익금을 뺐더니 손실금이 음수라면 0으로 처리해 준다!
                                    if CoinInfo['S_WaterLossMoney'] < 0:
                                        CoinInfo['S_WaterLossMoney'] = 0


                                msg = "40회가 소진되어 절반 매도합니다! 약 [" + str(RevenuMoney) + "] 확정 수익이 났네요!"
                                print(Target_Coin_Ticker + " " + msg) 
                                line_alert.SendMessage(Target_Coin_Ticker + " " + msg) 


               

                    IsBuyGo = False #매수 하는지!

                    #라운드에 따라 매수 조건이 다르다!
                    if CoinInfo['Round'] <= 10-1:

                        #여기는 무조건 매수
                        IsBuyGo = True

                    elif CoinInfo['Round'] <= 20-1:

                        #현재가가 5일선 위에 있을 때만 매수
                        if Ma5 < coin_price:
                            IsBuyGo = True

                    elif CoinInfo['Round'] <= 30-1:

                        #현재가가 5일선 위에 있고 이전 봉이 양봉일 때만 매수
                        if Ma5 < coin_price and IsUpCandle == True:
                            IsBuyGo = True

                    elif CoinInfo['Round'] <= 40-1:

                        #현재가가 5일선 위에 있고 이전 봉이 양봉일때 그리고 5일선, 20일선 둘다 증가추세에 있을 때만 매수
                        if Ma5 < coin_price and IsUpCandle == True and Ma5_before < Ma5 and Ma20_before < Ma20:
                            IsBuyGo = True



                    #한 회차 매수 한다!!
                    if IsBuyGo == True:

                        CoinInfo['Round'] += 1 #라운드 증가!

                        data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', Buy_Amt)
                        pprint.pprint(data)

                        CoinInfo['TotalBuyMoney'] += (float(data['price'])*float(data['amount']))

                        msg = "이평무한매수봇 " + str(CoinInfo['Round']) + "회차 매수 완료!"
                        print(Target_Coin_Ticker + " " + msg) 
                        line_alert.SendMessage(Target_Coin_Ticker + " " + msg) 




                    #위 로직 완료하면 N으로 바꿔서 오늘 매수는 안되게 처리!
                    CoinInfo['IsCheck'] = 'N'
                    CoinInfo['Date'] = time_info.tm_hour

                    #파일에 저장
                    with open(bot_file_path, 'w') as outfile:
                        json.dump(InfinityMaDataList, outfile)
                        
                    pprint.pprint(InfinityMaDataList)
                    
                    
                    ####################################################################################
                    ################## 위 정규 매수 로직과는 별개로 특별 물타기 로직을 체크하고 제어한다! #############

                    #이평선이 꺾여서 특별히 물탄 경우 수량이 0이 아닐꺼고 즉 여기는  물을 탄 상태이다!
                    if CoinInfo['S_WaterAmt'] != 0:

                        #그렇다면 하루가 지났다는 이야기니깐 해당 수량 만큼 무조건 매도 한다!

                        #현재가보다 아래에 매도 주문을 넣음으로써 시장가로 매도효과!
                        
                        data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', CoinInfo['S_WaterAmt'])

                        coin_revenue_money = CoinMoney - CoinInfo['TotalBuyMoney']


                        CoinInfo['TotalBuyMoney'] -= (float(data['price'])*float(data['amount'])) #매도한 금액을 빼준다!
                        


                        #단 현재 수익금이 마이너스 즉 손실 상태라면 손실 금액을 저장해 둔다!
                        if coin_revenue_money < 0:
                            #손실 금액에서 매도수량/보유수량 즉 예로 10개보유 하고 현재 -100달러인데 3개를 파는 거라면 실제 확정 손실금은 -100 * (3/10)이 니깐~
                            LossMoney = abs(coin_revenue_money) * (float(CoinInfo['S_WaterAmt']) / float(coin_amt))
                            CoinInfo['S_WaterLossMoney'] += LossMoney

                            msg = "평단을 확 낮추기 위한 이평무한매수봇 물탄지 하루가 지나 그 수량만큼 매도합니다! 약 [" + str(LossMoney) + "] 확정손실이 나서 기록했으며 누적 손실은 [" + str(CoinInfo['S_WaterLossMoney']) + "] 입니다"
                            print(Target_Coin_Ticker + " " + msg) 
                            line_alert.SendMessage(Target_Coin_Ticker + " " + msg) 

                        #이 경우는 이득 본 경우다!
                        else:

                            #이득본 금액도 계산해보자
                            RevenuMoney = abs(coin_revenue_money) * (float(CoinInfo['S_WaterAmt']) / float(coin_amt))

                            #혹시나 저장된 손실본 금액이 있다면 줄여 준다! (빠른 탈출을 위해)
                            if CoinInfo['S_WaterLossMoney'] > 0:
                                CoinInfo['S_WaterLossMoney'] -= RevenuMoney #저 데이터는 손실금을 저장하는 곳이니 빼준다

                                #수익금을 뺐더니 손실금이 음수라면 0으로 처리해 준다!
                                if CoinInfo['S_WaterLossMoney'] < 0:
                                    CoinInfo['S_WaterLossMoney'] = 0


                            msg = "평단을 확 낮추기 위한 이평무한매수봇 물탄지 하루가 지나 그 수량만큼 매도합니다! 약 [" + str(RevenuMoney) + "] 확정 수익이 났네요!"
                            print(Target_Coin_Ticker + " " + msg) 
                            line_alert.SendMessage(Target_Coin_Ticker + " " + msg) 

                        CoinInfo['S_WaterAmt'] = 0 #팔았으니 0으로 초기화!

                        
                    #평단 낮추기위한 물타기 미진행!
                    else:
                        # 20선밑에 5일선이 있는데 5일선이 위로 꺾여을 때
                        if Ma5 < Ma20 and Ma5_before3 > Ma5_before and Ma5_before < Ma5:

                            '''

                            매수할 회차 = 현재 회차 / 4 + 1

                            '''
                            #즉 10분할 남은 수량을 회차비중별로 차등 물을 탄다
                            #만약 현재 4회차 진입에 이 상황을 만났다면 2분할을 물을 타주고
                            #만약 현재 38회차 진입에 이 상황을 만났다면 10분할로 물을 타줘서
                            #평단을 확확 내려 줍니다!

                            BuyRound = int(CoinInfo['Round']/4) + 1 #물탈 회수

                            WaterBuyAmt = Buy_Amt * BuyRound
                            
             
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', WaterBuyAmt)
                            pprint.pprint(data)


                            CoinInfo['S_WaterAmt'] = data['amount']

                            CoinInfo['TotalBuyMoney'] += (float(data['price'])*float(data['amount'])) 
                            


                            msg = "이평선이 위로 꺾였어요! 평단을 확 낮추기 위한 이평무한매수봇 물을 탑니다!! [" + str(BuyRound) + "] 회차 만큼의 수량을 추가 했어요!"
                            print(Target_Coin_Ticker + " " + msg) 
                            line_alert.SendMessage(Target_Coin_Ticker + " " + msg) 

                    #########################################################################################
                    #########################################################################################
                    #파일에 저장
                    with open(bot_file_path, 'w') as outfile:
                        json.dump(InfinityMaDataList, outfile)
                        

                    msg = "이평무한매수봇 오늘 로직 끝!!"
                    print(Target_Coin_Ticker + " " + msg) 
                    line_alert.SendMessage(Target_Coin_Ticker + " " + msg) 
                    
                break




    except Exception as e:
        print("error:", e)






#저장된 날자값이랑 다르다면 날이 바뀐거다!! Y로 바꿔서 매매가능하게 플래그 변경
for CoinInfo in InfinityMaDataList:
    if CoinInfo['Date'] != time_info.tm_hour:
        CoinInfo['IsCheck'] = 'Y'
    

#파일에 저장
with open(bot_file_path, 'w') as outfile:
    json.dump(InfinityMaDataList, outfile)
    


#이 밑에 부분은 옵션으로 없어도 됩니다.
#그냥 내 총 잔고를 매 시간마다 혹은 0.5% 증가 되었다면 알림을 받는 로직입니다.

MoneyDict = dict()

#파일 경로입니다.
money_file_path = "/var/autobot/BinanceSpotMoney.json"
try:
    #이 부분이 파일을 읽어서 딕셔너리에 넣어주는 로직입니다. 
    with open(money_file_path, 'r') as json_file:
        MoneyDict = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")


#현재 평가금액을 구합니다.
TotalRealMoney =  float(balance['total']['USDT']) + float(CoinMoney)

print("TotalRealMoney ", TotalRealMoney)



if MoneyDict.get('TotalRealMoney') == None:
    MoneyDict['TotalRealMoney'] = TotalRealMoney

    with open(money_file_path, 'w') as outfile:
        json.dump(MoneyDict, outfile)   

    line_alert.SendMessage("!!!!!!!!!!!!!! First !!!!!! " + str(MoneyDict['TotalRealMoney']))


print("$$$$$$$$ MoneyDict['TotalRealMoney']", MoneyDict['TotalRealMoney'])
print("$$$$$$$$ MoneyDict['TotalRealMoney'] * 1.005", MoneyDict['TotalRealMoney'] * 1.005)
print("$$$$$$$$ TotalRealMoney", TotalRealMoney)



#이전에 저장된 가격에서 0.5%이상 증가되었다면!!
if MoneyDict['TotalRealMoney'] * 1.005 <= TotalRealMoney :


    #그리고 저장!!!
    MoneyDict['TotalRealMoney'] = TotalRealMoney

    with open(money_file_path, 'w') as outfile:
        json.dump(MoneyDict, outfile)   

    line_alert.SendMessage("$$$$$$$$!!!!!!!!!!!!!! 0.05% UPUP!!!!!!  USDT:" + str(TotalRealMoney))


else:
    if min == 0:
        line_alert.SendMessage("$$$$$$$$!!!!!!!!!!!!!!!!!!  USDT:" + str(TotalRealMoney))




