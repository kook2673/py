#-*-coding:utf-8 -*-
'''


!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

바이낸스 ccxt 버전
pip3 install --upgrade ccxt==4.2.19
이렇게 버전을 맞춰주세요!

봇은 헤지모드에서 동작합니다. 꼭! 헤지 모드로 바꿔주세요!
https://blog.naver.com/zacra/222662884649

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

관련 포스팅 
https://blog.naver.com/zacra/223449598379


위 포스팅을 꼭 참고하세요!!!

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.

주식/코인 파이썬 매매 FAQ
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
import my_key    #바이낸스 시크릿 액세스키

import line_alert #라인 메세지를 보내기 위함!
import json


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




#시간 정보를 읽는다
time_info = time.gmtime()

day_n = time_info.tm_mday

hour_n = time_info.tm_hour
min_n = time_info.tm_min

print("hour_n:", hour_n)
print("min_n:", min_n)

day_str = str(time_info.tm_year) + str(time_info.tm_mon) + str(time_info.tm_mday)





#봇 상태를 저장할 파일
BotDataDict = dict()

#파일 경로입니다.
botdata_file_path = "/var/autobot/BinanceF_Data.json"
try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(botdata_file_path, 'r') as json_file:
        BotDataDict = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")


 
###################################################
#레버리지!! 1배로 기본 셋! 레버리지를 쓰면 음의 복리로 인해 백테스팅과 다른 결과가 나타날 수 있음!
set_leverage = 1


#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
Fix_Rebalance_Enable = True #고정비중 리밸런싱 발동!
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

#투자 비중 -> 1.0 : 100%  0.5 : 50%   0.1 : 10%
InvestRate = 0.7 #투자 비중은 자금사정에 맞게 수정하세요!
###################################################


balance = binanceX.fetch_balance(params={"type": "future"})
time.sleep(0.1)
#pprint.pprint(balance)



TotalMoney = float(balance['USDT']['total']) #총 원금
print("TotalMoney", TotalMoney)


##########################################################################
InvestTotalMoney = TotalMoney * InvestRate
##########################################################################

print("InvestTotalMoney", InvestTotalMoney)



######################################## 1. 균등 분할 투자 ###########################################################
#InvestCoinList = ["BTC/USDT","ETH/USDT"]
##########################################################################################################


######################################## 2. 차등 분할 투자 ###################################################
#'''
InvestCoinList = list()

InvestDataDict = dict()
InvestDataDict['ticker'] = "BTC/USDT"
InvestDataDict['rate'] = 0.4     #전략에 의해 사고파는 비중 40%
InvestDataDict['fix_rate'] = 0.1 #고정 비중 10% 할당!
InvestCoinList.append(InvestDataDict)

InvestDataDict = dict()
InvestDataDict['ticker'] = "ETH/USDT"
InvestDataDict['rate'] = 0.4      #전략에 의해 사고파는 비중 40%
InvestDataDict['fix_rate'] = 0.1  #고정 비중 10% 할당!
InvestCoinList.append(InvestDataDict)


#'''
##########################################################################################################

CoinCnt = len(InvestCoinList)



######################################## 1. 균등 분할 투자 ###########################################################
'''
for coin_ticker in InvestCoinList:    
    InvestMoney = InvestTotalMoney / len(InvestCoinList) #테스트 총 금액을 종목 수로 나눠서 각 할당 투자금을 계산한다!
'''
##########################################################################################################

######################################## 2. 차등 분할 투자 ###################################################
#'''
for coin_data in InvestCoinList:
    
    
    try:
        
        

        coin_ticker = coin_data['ticker']
        print("\n----coin_ticker: ", coin_ticker)

        Target_Coin_Ticker = coin_ticker

        Target_Coin_Symbol = coin_ticker.replace("/", "").replace(":USDT","")
        
        
        amt_s = 0 
        amt_b = 0
        entryPrice_s = 0 #평균 매입 단가. 
        entryPrice_b = 0 #평균 매입 단가. 
        leverage = 0


        isolated = True #격리모드인지 



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

        #################################################################################################################

        if set_leverage != leverage:
            try:
                print(binanceX.fapiPrivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': set_leverage}))
            except Exception as e:
                try:
                    print(binanceX.fapiprivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': set_leverage}))
                except Exception as e:
                    print("Exception Done OK..")


        #################################################################################################################



        #################################################################################################################
        #영상엔 없지만         
        #교차모드로 셋팅합니다! isolated == True로 격리모드라면 CROSSED 로 교차모드로 바꿔주면 됩니다.
        #################################################################################################################
        if isolated == True:
            try:
                print(binanceX.fapiPrivate_post_margintype({'symbol': Target_Coin_Symbol, 'marginType': 'CROSSED'}))
            except Exception as e:
                try:
                    print(binanceX.fapiprivate_post_margintype({'symbol': Target_Coin_Symbol, 'marginType': 'CROSSED'}))
                except Exception as e:
                    print("Exception Done OK..")
        ########################################################################################
        

        #최소 주문 수량을 가져온다 
        minimun_amount = myBinance.GetMinimumAmount(binanceX,Target_Coin_Ticker)




        #해당 코인의 저장된 매수날짜가 없다면 디폴트 값으로 ""으로 세팅한다!
        if BotDataDict.get(coin_ticker+"_BUY_DATE") == None:
            BotDataDict[coin_ticker+"_BUY_DATE"] = ""

            #파일에 저장
            with open(botdata_file_path, 'w') as outfile:
                json.dump(BotDataDict, outfile)


        #해당 코인의 저장된 매도날짜가 없다면 디폴트 값으로 ""으로 세팅한다!
        if BotDataDict.get(coin_ticker+"_SELL_DATE") == None:
            BotDataDict[coin_ticker+"_SELL_DATE"] = ""

            #파일에 저장
            with open(botdata_file_path, 'w') as outfile:
                json.dump(BotDataDict, outfile)




        #체크한 기록이 없는 처음이라면 
        if BotDataDict.get(coin_ticker+"_DATE_CHECK") == None:

            #0으로 초기화!!!!!
            BotDataDict[coin_ticker+"_DATE_CHECK"] = 0
            #파일에 저장
            with open(botdata_file_path, 'w') as outfile:
                json.dump(BotDataDict, outfile)



        ############################# FixV ####################################
        #체크한 기록이 없는 처음이라면 
        if BotDataDict.get(coin_ticker+"_HAS") == None:
            
            if abs(amt_b) > 0: 

                #보유하고 있다면 일단 전략에 의해 매수했다고 가정하자!
                BotDataDict[coin_ticker+"_HAS"] = True
                
            else:
                
                BotDataDict[coin_ticker+"_HAS"] = False
                
            #파일에 저장
            with open(botdata_file_path, 'w') as outfile:
                json.dump(BotDataDict, outfile)





        InvestMoney = InvestTotalMoney * coin_data['rate'] #설정된 투자금에 맞게 투자!
        ############################# FixV ####################################
        InvestFixMoney = InvestTotalMoney * coin_data['fix_rate'] #설정된 투자금에 맞게 투자!
        
    #'''
    ##########################################################################################################

        print(coin_ticker, " 종목당 할당 투자금:", InvestMoney)
        print(coin_ticker, " 종목당 고정 투자금:", InvestFixMoney)
        print(coin_ticker, " 종목당 투자금:", InvestMoney + InvestFixMoney)
        
        #코인별 할당된 모든 금액을 투자하는 올인 전략이니만큼 수수료를 감안하여 투자금 설정!
        InvestMoneyCell = InvestMoney * 0.995


        df_day = myBinance.GetOhlcv(binanceX,coin_ticker, '1d')
        time.sleep(0.1)
        df_day['value'] = df_day['close'] * df_day['volume']
        
        df_day['value_ma'] = df_day['value'].rolling(window=10).mean()


        Ma3_before = myBinance.GetMA(df_day,3,-3) 
        Ma3 = myBinance.GetMA(df_day,3,-2)  


        Ma5_before = myBinance.GetMA(df_day,5,-3) 


        Ma5 = myBinance.GetMA(df_day,5,-2)   

        Ma6_before = myBinance.GetMA(df_day,6,-3) 
        Ma6 = myBinance.GetMA(df_day,6,-2)   

        Ma10_before = myBinance.GetMA(df_day,10,-3)   
        Ma10 = myBinance.GetMA(df_day,10,-2)   
        
        Ma19_before = myBinance.GetMA(df_day,19,-3) 
        Ma19 = myBinance.GetMA(df_day,19,-2) 
        Ma20 = myBinance.GetMA(df_day,20,-2) 

        Ma_Last = Ma19
        


        Ma50_before = myBinance.GetMA(df_day,50,-3) 
        Ma50 = myBinance.GetMA(df_day,50,-2)

        Ma60 = myBinance.GetMA(df_day,60,-2)

        
        Ma70 = myBinance.GetMA(df_day,70,-2)
        
        Rsi_before = myBinance.GetRSI(df_day,14,-3) 
        Rsi = myBinance.GetRSI(df_day,14,-2) 


        ########## RSI 지표 구하는 로직! ##########
        period = 14

        delta = df_day["close"].diff()
        up, down = delta.copy(), delta.copy()
        up[up < 0] = 0
        down[down > 0] = 0
        _gain = up.ewm(com=(period - 1), min_periods=period).mean()
        _loss = down.abs().ewm(com=(period - 1), min_periods=period).mean()
        RS = _gain / _loss

        df_day['rsi'] = pd.Series(100 - (100 / (1 + RS)), name="RSI")
        ########################################

        df_day['rsi_ma'] = df_day['rsi'].rolling(10).mean()
        
        RsiMa_before  = df_day['rsi_ma'].iloc[-3]
        RsiMa  = df_day['rsi_ma'].iloc[-2]


        PrevClose = df_day['close'].iloc[-2]

        #현재가를 구하다
        NowCurrentPrice = myBinance.GetCoinNowPrice(binanceX, Target_Coin_Ticker)



        #잔고가 있는 경우.
        #if abs(amt_b) != 0: 
        ############################# FixV ####################################
        if BotDataDict[coin_ticker+"_HAS"] == True and abs(amt_b) != 0:
            print("전략으로 매수한 경우!")

            revenue_rate_b = (NowCurrentPrice - entryPrice_b) / entryPrice_b * 100.0


            unrealizedProfit_b = 0 #미 실현 손익.

            #롱 잔고
            for posi in balance['info']['positions']:
                if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'LONG':

                    unrealizedProfit_b = float(posi['unrealizedProfit'])
                    break



            IsSellGo = False


        
            IsDolpaCut = False

            #이더리움의 경우
            if coin_ticker == 'ETH/USDT':

                #RSI지표가 70이상인 과매수 구간에서 단기 이평선을 아래로 뚫으면 돌파매도 처리!!
                CutPrice = Ma6
                
                if df_day['rsi'].iloc[-2] >= 70 and NowCurrentPrice <= CutPrice and df_day['open'].iloc[-1] > CutPrice :
                    IsSellGo = True
                    IsDolpaCut = True

            if BotDataDict[coin_ticker+"_DATE_CHECK"] != day_n:

                msg = coin_ticker + "현재 수익률 : 약 " + str(round(revenue_rate_b * set_leverage,2)) + "% 수익금 : 약" + str(format(round(unrealizedProfit_b), ',')) + "USDT"
                print(msg)
                line_alert.SendMessage(msg)


                time.sleep(1.0)
                    
                #이더리움의 경우
                if coin_ticker == 'ETH/USDT':
                    #50일선 위에 있는 상승장
                    if PrevClose > Ma50:

                        #6일선, 10일선 둘다 밑으로 내려가면 매도!!
                        if Ma6 > PrevClose and Ma10 > PrevClose:

                            IsSellGo = True

                    #50일선 아래에 있는 하락장
                    else:
                        
                        # 5일선 밑으로 내려가거나 전일 캔들 기준 고가도 하락하고 저가도 하락했다면 매도!
                        if Ma6 > PrevClose or (df_day['high'].iloc[-3] > df_day['high'].iloc[-2] and df_day['low'].iloc[-3] > df_day['low'].iloc[-2]) :
                            IsSellGo = True

                #비트코인의 경우
                else:
                    #전일 캔들 기준 고가도 하락하고 저가도 하락했거나 2연속 음봉이거나 수익률이 0보다 작아지면 매도!!
                    if ((df_day['high'].iloc[-3] > df_day['high'].iloc[-2] and df_day['low'].iloc[-3] > df_day['low'].iloc[-2]) or (df_day['open'].iloc[-2] > df_day['close'].iloc[-2] and df_day['open'].iloc[-3] > df_day['close'].iloc[-3])  ) :
                        IsSellGo = True


                    if RsiMa_before < RsiMa and Ma3_before < Ma3:
                        IsSellGo = False


                BotDataDict[coin_ticker+"_DATE_CHECK"] = day_n
                #파일에 저장
                with open(botdata_file_path, 'w') as outfile:
                    json.dump(BotDataDict, outfile)

            #저장된 매수날짜와 오늘 날짜가 같다면.. 오늘 돌파 매수던 시가 매수던 매수가 된 상황이니깐 오늘은 매도 하면 안된다.
            if BotDataDict[coin_ticker+"_BUY_DATE"] == day_str:
                IsSellGo = False


            if IsSellGo == True:

                ############################# FixV ####################################
                #매도 하되 고정 비율 만큼은 남기도록 매도한다
                NowMoney = myBinance.GetCoinRealMoney(balance,Target_Coin_Ticker,"LONG")
                print("NowMoney ", NowMoney)
                TargetTotalMoney = InvestTotalMoney * coin_data['fix_rate']
                
                SellMoney = 0
                if NowMoney > TargetTotalMoney:
                    SellMoney = NowMoney - TargetTotalMoney #살 금액을 정해진 금액에서 현재 투자금의 차액으로 정해준다!!!      
                
                print("SellMoney: ", SellMoney)
                SellAmt = float(binanceX.amount_to_precision(Target_Coin_Ticker, myBinance.GetAmount(SellMoney,NowCurrentPrice,1.0))) * set_leverage 
                print("SellAmt: ", SellAmt)


                if SellMoney == 0:
                    print("고정비중보다 현재 적은 상황이니 매도(롱포지션 종료)하지 않고 처리만 해준다!")
                
                else:

                    if SellAmt >= minimun_amount:
                        #롱 포지션 종료!!
                        params = {
                            'positionSide': 'LONG'
                        }
                        print(binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', float(binanceX.amount_to_precision(Target_Coin_Ticker,SellAmt)), None, params))
                        

                if IsDolpaCut == True:
                    msg = coin_ticker + " 바이낸스 안전 전략 봇 : 조건을 하향 돌파 불만족하여 매도처리 했어요!! 현재 수익률 : 약 " + str(round(revenue_rate_b * set_leverage,2)) + "% 수익금 : 약" + str(format(round(unrealizedProfit_b), ',')) + "USDT"
                    print(msg)
                    line_alert.SendMessage(msg)
                else:
                                
                    msg = coin_ticker + " 바이낸스 안전 전략 봇 : 조건을 불만족하여 매도처리 했어요!! 현재 수익률 : 약 " + str(round(revenue_rate_b * set_leverage,2)) + "% 수익금 : 약" + str(format(round(unrealizedProfit_b), ',')) + "USDT"
                    print(msg)
                    line_alert.SendMessage(msg)


                ############################# FixV ####################################
                BotDataDict[coin_ticker+"_HAS"] = False
                
                #매도했다면 매도 날짜를 기록한다.
                BotDataDict[coin_ticker+"_SELL_DATE"] = day_str
                #파일에 저장
                with open(botdata_file_path, 'w') as outfile:
                    json.dump(BotDataDict, outfile)
                


        else:
            print("아직 투자하지 않음")

            #이평선 조건을 만족하는지
            IsMaDone = False


            #3개의 이평선 중 가장 높은 값을 구한다!
            DolPaSt = max(Ma6,Ma10,Ma_Last)
            
            if coin_ticker == 'ETH/USDT':
                
                #가장 높은 이평선의 값이 가장 긴 기간의 이평선일때
                #그 전일 이평선 값을 현재가가 넘었다면 돌파 매수를 한다!!!
                if DolPaSt == Ma_Last and NowCurrentPrice >= DolPaSt:
                
                    #단 RSI지표가 증가! RSI 10일 평균지표도 증가할 때 돌파매수!
                    if Rsi_before < Rsi and RsiMa_before < RsiMa:
                        IsMaDone = True
                        

                #그 밖의 경우
                else:
                    #5,10,20선 위에 있고 RSI지표가 증가! RSI 10일 평균지표도 증가한다면 매수!
                    if PrevClose > Ma6 and PrevClose > Ma10 and PrevClose > Ma_Last and Rsi_before < Rsi  and RsiMa_before < RsiMa:
                        IsMaDone = True


                if IsMaDone == False:

                    print("변돌 체크!")

                    DolpaRate = 0.7

                    if Ma_Last < PrevClose:
                        DolpaRate = 0.6

                    if Ma6_before < Ma6 and Ma10_before < Ma10 and  Ma19_before < Ma19 and Ma19 < Ma10 < Ma6:
                        DolpaRate = 0.5


                    DolPaSt = df_day['open'].iloc[-1] + (( df_day['high'].iloc[-2] - df_day['low'].iloc[-2]) * DolpaRate)

                    if NowCurrentPrice >= DolPaSt and RsiMa_before < RsiMa and Ma6_before < Ma6:

                        IsMaDone = True



            #비트코인일 때       
            else:
                

                #가장 높은 이평선의 값이 가장 긴 기간의 이평선일때
                #그 전일 이평선 값을 현재가가 넘었다면 돌파 매수를 한다!!!
                if DolPaSt == Ma_Last and NowCurrentPrice >= DolPaSt:

                    #비트코인은 추가 조건 체크 없이 그냥 돌파했으면 매수!
                    IsMaDone = True
                        
                else:
                    #2연속 양봉이면서 고가도 증가되는데 5일선이 증가되고 있으면서 10일선,70일선 위에 있을 때 비트 매수!
                    if df_day['open'].iloc[-2] < df_day['close'].iloc[-2] and df_day['open'].iloc[-3] < df_day['close'].iloc[-3] and df_day['close'].iloc[-3] < df_day['close'].iloc[-2]  and df_day['high'].iloc[-3] < df_day['high'].iloc[-2] and Ma3_before < Ma3 and Ma20 < df_day['close'].iloc[-2] and Ma70 < df_day['close'].iloc[-2] :
                            
                        IsMaDone = True
                        

                if IsMaDone == False:
                    print("변돌 체크!")

                    DolpaRate = 0.7

                    DolPaSt = df_day['open'].iloc[-1] + ( ( max(df_day['high'].iloc[-3],df_day['high'].iloc[-2]) - min(df_day['low'].iloc[-3],df_day['low'].iloc[-2]) ) * DolpaRate)

                    if NowCurrentPrice >= DolPaSt and RsiMa_before < RsiMa and df_day['low'].iloc[-3] < df_day['low'].iloc[-2] and Ma10 < PrevClose and Ma19 < Ma10 < Ma3:
                        IsMaDone = True


            #저장된 매도날짜와 오늘 날짜가 같다면.. 매도가 된 상황이니깐 오늘은 매수 하면 안된다.
            if BotDataDict[coin_ticker+"_SELL_DATE"] == day_str:
                IsMaDone = False




            if IsMaDone == True :

                Rate = 1.0

                #50일선이 감소중이거나 50일선 밑에 있다면 투자비중 절반으로 줄여줌!
                if Ma50_before > Ma50 or Ma50 > df_day['close'].iloc[-2]:
                    Rate *= 0.5

                BuyGoMoney = InvestMoneyCell * Rate

                #투자금 거래대금 10일 평균의 1/2000수준으로 제한!
                if BuyGoMoney >= df_day['value_ma'].iloc[-2] / 2000:
                    BuyGoMoney = df_day['value_ma'].iloc[-2] / 2000

                BuyMoney = BuyGoMoney 

    
                ##########################################################
                #현재 투자 평가금을 구한다!
                NowMoney = myBinance.GetCoinRealMoney(balance,Target_Coin_Ticker,"LONG")
                
                #해당 코인에 할당된 금액!!!
                TargetTotalMoney = InvestTotalMoney * (coin_data['rate'] + coin_data['fix_rate'])
                # TargetTotalMoney 이걸 넘기면 안된다!!!
                
                #투자로 정해진 금액보다 살금액 + 현재 투자금이 더 크다면?
                if TargetTotalMoney < (BuyMoney + NowMoney):
                    BuyMoney = TargetTotalMoney - NowMoney #살 금액을 정해진 금액에서 현재 투자금의 차액으로 정해준다!!!           

                #투자로 정해진 금액보다 살금액 + 현재 투자금이 더 작다면?? 비중이 모자라다 채워주자! 그 갭만큼!!
                elif TargetTotalMoney > (BuyMoney + NowMoney):
                    BuyMoney += (TargetTotalMoney - (BuyMoney + NowMoney))
                

                #######################################################################################
                
                Buy_Amt = float(binanceX.amount_to_precision(Target_Coin_Ticker, myBinance.GetAmount(BuyMoney,NowCurrentPrice,1.0))) * set_leverage 


                if minimun_amount > Buy_Amt:
                    Buy_Amt = minimun_amount
                    
                    
                #롱 포지션을 잡습니다.
                params = {
                    'positionSide': 'LONG'
                }
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', Buy_Amt, None, params)
                


                ############################# FixV ####################################
                BotDataDict[coin_ticker+"_HAS"] = True

                #매수했다면 매수 날짜를 기록한다.
                BotDataDict[coin_ticker+"_BUY_DATE"] = day_str
                #파일에 저장
                with open(botdata_file_path, 'w') as outfile:
                    json.dump(BotDataDict, outfile)


                    
                    
                msg = coin_ticker + " 바이낸스 안전 전략 봇 :  조건 만족 하여 매수!! "

                print(msg)
                line_alert.SendMessage(msg)

            else:
                #매일 아침 9시 정각에..
                if hour_n == 0 and min_n == 0:
                    msg = coin_ticker + " 바이낸스 안전 전략 봇 :  조건 만족하지 않아 현금 보유 합니다!"
                    print(msg)
                    line_alert.SendMessage(msg)
                


        ############################# FixV ####################################
        if coin_data['fix_rate'] > 0:

            balance = binanceX.fetch_balance(params={"type": "future"})
            time.sleep(0.1)


            amt_b = 0
            entryPrice_b = 0 #평균 매입 단가. 

            #롱잔고
            for posi in balance['info']['positions']:
                if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'LONG':
                    print(posi)
                    amt_b = float(posi['positionAmt'])
                    entryPrice_b = float(posi['entryPrice'])

                    break


            
            #잔고가 없다면 고정 비중만큼 매수한다!
            if abs(amt_b) == 0: 
                
                #고정 비중 만큼 매수한다!!!!
                InvestMoneyCell = InvestFixMoney * 0.995

                Rate = 1.0
                BuyGoMoney = InvestMoneyCell * Rate

                #투자금 거래대금 10일 평균의 1/2000수준으로 제한!
                if BuyGoMoney >= df_day['value_ma'].iloc[-2] / 2000:
                    BuyGoMoney = df_day['value_ma'].iloc[-2] / 2000

                BuyMoney = BuyGoMoney 

        
                Buy_Amt = float(binanceX.amount_to_precision(Target_Coin_Ticker, myBinance.GetAmount(BuyMoney,NowCurrentPrice,1.0))) * set_leverage 


                if minimun_amount > Buy_Amt:
                    Buy_Amt = minimun_amount
                    
                    
                #롱 포지션을 잡습니다.
                params = {
                    'positionSide': 'LONG'
                }
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', Buy_Amt, None, params)
                

                msg = coin_ticker + " 바이낸스 안전 전략 봇 :  고정비중이 없어 투자!!"
                print(msg)
                line_alert.SendMessage(msg)
                
            else:
                        
                if Fix_Rebalance_Enable == True and BotDataDict[coin_ticker+"_HAS"] == False:
                    print("고정 비중 투자 잔고가 있는 경우.. 리밸런싱이 필요하다면 리밸런싱!!")

                    TargetTotalMoney = InvestTotalMoney * 0.995

                    #현재 코인의 총 매수금액
                    NowCoinTotalMoney = myBinance.GetCoinRealMoney(balance,Target_Coin_Ticker,"LONG")
                    
                    print(NowCoinTotalMoney, " / ", TargetTotalMoney)

                    Rate = NowCoinTotalMoney / TargetTotalMoney
                    print("--------------> coin_ticker rate : ", Rate, coin_data['fix_rate'] )

                    #코인 목표 비중과 현재 비중이 다르다.
                    if Rate != coin_data['fix_rate']:

                        #갭을 구한다!!!
                        GapRate = coin_data['fix_rate'] - Rate
                        print("--------------> coin_ticker Gaprate : ", GapRate)


                        GapMoney = TargetTotalMoney * abs(GapRate)
                        
                        GapAmt = float(binanceX.amount_to_precision(Target_Coin_Ticker, myBinance.GetAmount(GapMoney,NowCurrentPrice,1.0))) * set_leverage 


                        #갭이 음수면 코인 비중보다 수익이 나서 더 많은 비중을 차지하고 있는 경우
                        if GapRate < 0:
                            
                            #고정비중의 1/10이상의 갭이 있을때 리밸런싱이 진행!!
                            if GapAmt >= minimun_amount and abs(GapRate) >= (coin_data['fix_rate'] / 10.0): 
    

                                #롱 포지션 종료!!
                                params = {
                                    'positionSide': 'LONG'
                                }
                                print(binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', GapAmt, None, params))
                                

                                
                                line_alert.SendMessage(coin_ticker + " 바이낸스 안전 전략 봇 : 리밸런싱 진행!!!! 일부 매도!" )
                                print("--------------> SELL ",coin_ticker,"!!!!")



                        #갭이 양수면 비트코인 비중이 적으니 추매할 필요가 있는 경우
                        else:

                            #고정비중의 1/10이상의 갭이 있을때 리밸런싱이 진행!!
                            if GapAmt >= minimun_amount and abs(GapRate) >= (coin_data['fix_rate'] / 10.0):

                                #롱 포지션 진입!!
                                params = {
                                    'positionSide': 'LONG'
                                }
                                print(binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', GapAmt, None, params))
                                
                                
                                line_alert.SendMessage(coin_ticker + " 바이낸스 안전 전략 봇 : 리밸런싱 진행!!! 일부 매수!" )
                                print("--------------> BUY ",coin_ticker,"!!!!")
                        

    except Exception as e:
        print("check, ", e)
        
