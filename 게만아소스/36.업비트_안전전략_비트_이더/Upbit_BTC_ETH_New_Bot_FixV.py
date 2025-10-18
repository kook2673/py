#-*-coding:utf-8 -*-
'''
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

해당 컨텐츠는 제가 직접 투자 하기 위해 이 전략을 추가 개선해서 더 좋은 성과를 보여주는 개인 전략이 존재합니다.  

게만아 추가 개선 개인 전략들..
https://blog.naver.com/zacra/223196497504

관심 있으신 분은 위 포스팅을 참고하세요!

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

코드 설명 참고 영상
https://youtu.be/TYj_fq4toAw?si=b3H8B_o8oU3roIWF


관련 포스팅 
https://blog.naver.com/zacra/223319768193

추가 리밸런싱 기능 추가 버전 설명
https://blog.naver.com/zacra/223446583168

최근 마지막 수정 포스팅
https://blog.naver.com/zacra/223805709477

위 포스팅을 꼭 참고하세요!!!

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.

주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!

'''

import myUpbit   #우리가 만든 함수들이 들어있는 모듈
import time
import pyupbit

import ende_key  #암복호화키
import my_key    #업비트 시크릿 액세스키
import pandas as pd
import pprint
import json
import urllib3
import line_alert


#암복호화 클래스 객체를 미리 생성한 키를 받아 생성한다.
simpleEnDecrypt = myUpbit.SimpleEnDecrypt(ende_key.ende_key)

#암호화된 액세스키와 시크릿키를 읽어 복호화 한다.
Upbit_AccessKey = simpleEnDecrypt.decrypt(my_key.upbit_access)
Upbit_ScretKey = simpleEnDecrypt.decrypt(my_key.upbit_secret)

#업비트 객체를 만든다
upbit = pyupbit.Upbit(Upbit_AccessKey, Upbit_ScretKey)



#시간 정보를 읽는다
time_info = time.gmtime()

day_n = time_info.tm_mday

hour_n = time_info.tm_hour
min_n = time_info.tm_min

print("hour_n:", hour_n)
print("min_n:", min_n)

day_str = str(time_info.tm_year) + str(time_info.tm_mon) + str(time_info.tm_mday)



#수익금과 수익률을 리턴해주는 함수 (수수료는 생각안함) myUpbit에 넣으셔서 사용하셔도 됨!
def GetRevenueMoneyAndRate(balances,Ticker):
             
    #내가 가진 잔고 데이터를 다 가져온다.
    balances = upbit.get_balances()
    time.sleep(0.04)

    revenue_data = dict()

    revenue_data['revenue_money'] = 0
    revenue_data['revenue_rate'] = 0

    for value in balances:
        try:
            realTicker = value['unit_currency'] + "-" + value['currency']
            if Ticker == realTicker:
                
                nowPrice = pyupbit.get_current_price(realTicker)
                revenue_data['revenue_money'] = (float(nowPrice) - float(value['avg_buy_price'])) * upbit.get_balance(Ticker)
                revenue_data['revenue_rate'] = (float(nowPrice) - float(value['avg_buy_price'])) * 100.0 / float(value['avg_buy_price'])
                time.sleep(0.06)
                break

        except Exception as e:
            print("---:", e)

    return revenue_data



#봇 상태를 저장할 파일
BotDataDict = dict()

#파일 경로입니다.
botdata_file_path = "/var/autobot/Upbit_Safe_Data.json"
try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(botdata_file_path, 'r') as json_file:
        BotDataDict = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")






#최소 매수 금액
minmunMoney = 5500

#내가 가진 잔고 데이터를 다 가져온다.
balances = upbit.get_balances()

TotalMoeny = myUpbit.GetTotalMoney(balances) #총 원금
TotalRealMoney = myUpbit.GetTotalRealMoney(balances) #총 평가금액

print("TotalMoeny", TotalMoeny)
print("TotalRealMoney", TotalRealMoney)

###############################################################
#투자 비중 -> 1.0 : 100%  0.5 : 50%   0.1 : 10%
InvestRate = 0.7 #투자 비중은 자금사정에 맞게 수정하세요!

#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
Fix_Rebalance_Enable = True #고정비중 리밸런싱 발동!
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

###############################################################

##########################################################################
InvestTotalMoney = TotalMoeny * InvestRate #총 투자원금+ 남은 원화 기준으로 투자!!!!
##########################################################################

print("InvestTotalMoney", InvestTotalMoney)


######################################## 1. 균등 분할 투자 ###########################################################
#InvestCoinList = ["KRW-BTC","KRW-ETH"]
##########################################################################################################


######################################## 2. 차등 분할 투자 ###################################################
#'''
InvestCoinList = list()


############################# FixV ####################################
InvestDataDict = dict()
InvestDataDict['ticker'] = "KRW-BTC"
InvestDataDict['rate'] = 0.4     #전략에 의해 사고파는 비중 40%
InvestDataDict['fix_rate'] = 0.1 #고정 비중 10% 할당!
InvestCoinList.append(InvestDataDict)

InvestDataDict = dict()
InvestDataDict['ticker'] = "KRW-ETH"
InvestDataDict['rate'] = 0.4      #전략에 의해 사고파는 비중 40%
InvestDataDict['fix_rate'] = 0.1  #고정 비중 10% 할당!
InvestCoinList.append(InvestDataDict)




#'''
##########################################################################################################


######################################## 1. 균등 분할 투자 ###########################################################
'''
for coin_ticker in InvestCoinList:    
    InvestMoney = InvestTotalMoney / len(InvestCoinList) #테스트 총 금액을 종목 수로 나눠서 각 할당 투자금을 계산한다!
'''
##########################################################################################################

######################################## 2. 차등 분할 투자 ###################################################
#'''
for coin_data in InvestCoinList:

    coin_ticker = coin_data['ticker']
    print("\n----coin_ticker: ", coin_ticker)


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
        

        StrategyBuyDict = dict()

        #파일 경로입니다.
        strategybuy_file_path = "/var/autobot/UpbitNewStrategyBuy.json"
        try:
            #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
            with open(strategybuy_file_path, 'r') as json_file:
                StrategyBuyDict = json.load(json_file)

            #여기까지 탔다면 기존에 저 파일에 저장된 내용이 있다는 것! 그것을 읽어와서 세팅한다!
            BotDataDict[coin_ticker+"_HAS"] = StrategyBuyDict[coin_ticker]

        except Exception as e:

            if myUpbit.IsHasCoin(balances,coin_ticker) == True: 

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

    
    #코인별 할당된 모든 금액을 투자하는 올인 전략이니만큼 수수료를 감안하여 투자금 설정!
    InvestMoneyCell = InvestMoney * 0.995
    print("InvestMoneyCell: ", InvestMoneyCell)


    df_day = pyupbit.get_ohlcv(coin_ticker,interval="day")
    time.sleep(0.1)
    ############# 이동평균선! ###############
    for ma in range(3,80):
        df_day[str(ma) + 'ma'] = df_day['close'].rolling(ma).mean()
    ########################################
    
    
    df_day['value_ma'] = df_day['value'].rolling(window=10).mean()


    Ma3_before = df_day['3ma'].iloc[-3] 
    Ma3 = df_day['3ma'].iloc[-2]  


    Ma5_before = df_day['5ma'].iloc[-3] 


    Ma5 = df_day['5ma'].iloc[-2]   

    Ma6_before = df_day['6ma'].iloc[-3] 
    Ma6 = df_day['6ma'].iloc[-2]   

    Ma10_before = df_day['10ma'].iloc[-3]   
    Ma10 = df_day['10ma'].iloc[-2]   
    
    Ma19_before = df_day['19ma'].iloc[-3] 
    Ma19 = df_day['19ma'].iloc[-2] 
    Ma20 = df_day['20ma'].iloc[-2] 

    Ma_Last = Ma19
    


    Ma50_before = df_day['50ma'].iloc[-3] 
    Ma50 = df_day['50ma'].iloc[-2]

    Ma60 = df_day['60ma'].iloc[-2]

    
    Ma70 = df_day['70ma'].iloc[-2]
    
    Rsi_before = myUpbit.GetRSI(df_day,14,-3) 
    Rsi = myUpbit.GetRSI(df_day,14,-2) 


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
    NowCurrentPrice = pyupbit.get_current_price(coin_ticker)



    #잔고가 있는 경우.
    #if myUpbit.IsHasCoin(balances,coin_ticker) == True: 
    ############################# FixV ####################################
    if BotDataDict[coin_ticker+"_HAS"] == True and myUpbit.IsHasCoin(balances,coin_ticker) == True:
        print("전략으로 매수한 경우!")

        #수익금과 수익률을 구한다!
        revenue_data = GetRevenueMoneyAndRate(balances,coin_ticker)



        IsSellGo = False


    
        IsDolpaCut = False

        #이더리움의 경우
        if coin_ticker == 'KRW-ETH':

            #RSI지표가 70이상인 과매수 구간에서 단기 이평선을 아래로 뚫으면 돌파매도 처리!!
            CutPrice = Ma6
            
            if df_day['rsi'].iloc[-2] >= 70 and NowCurrentPrice <= CutPrice and df_day['open'].iloc[-1] > CutPrice :
                IsSellGo = True
                IsDolpaCut = True

        if BotDataDict[coin_ticker+"_DATE_CHECK"] != day_n:

            msg = coin_ticker + "현재 수익률 : 약 " + str(round(revenue_data['revenue_rate'],2)) + "% 수익금 : 약" + str(format(round(revenue_data['revenue_money']), ',')) + "원"
            print(msg)
            line_alert.SendMessage(msg)


            time.sleep(1.0)
                
            #이더리움의 경우
            if coin_ticker == 'KRW-ETH':
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



        #도지 캔들 패턴 체크
        prev_high_low_gap = abs(df_day['high'].iloc[-3] - df_day['low'].iloc[-3])
        prev_open_close_gap = abs(df_day['open'].iloc[-3] - df_day['close'].iloc[-3])

        #윗꼬리와 아래꼬리 길이 계산
        upper_tail = df_day['high'].iloc[-2] - max(df_day['open'].iloc[-2], df_day['close'].iloc[-2])
        lower_tail = min(df_day['open'].iloc[-2], df_day['close'].iloc[-2]) - df_day['low'].iloc[-2]


        #시가와 종가의 갭이 고가와 저가의 갭의 40% 이하면서 윗꼬리가 더 길 경우..
        if (prev_high_low_gap > 0 and (prev_open_close_gap / prev_high_low_gap) <= 0.4) and upper_tail > lower_tail:
                
            #저전저가보다 이전종가가 낮으면서 수익률이 0보다 작다면..
            if df_day['low'].iloc[-3] > df_day['close'].iloc[-2] and revenue_data['revenue_rate'] < 0:
                IsSellGo = True

        #저장된 매수날짜와 오늘 날짜가 같다면.. 오늘 돌파 매수던 시가 매수던 매수가 된 상황이니깐 오늘은 매도 하면 안된다.
        if BotDataDict[coin_ticker+"_BUY_DATE"] == day_str:
            IsSellGo = False


        if IsSellGo == True:

            ############################# FixV ####################################
            #매도 하되 고정 비율 만큼은 남기도록 매도한다
            AllAmt = upbit.get_balance(coin_ticker) #현재 수량
            
            SellAmt = AllAmt * (1.0 - (coin_data['fix_rate']/(coin_data['rate']+coin_data['fix_rate'])))

            balances = myUpbit.SellCoinMarket(upbit,coin_ticker,SellAmt)

            if IsDolpaCut == True:
                msg = coin_ticker + " 업비트 안전 전략 봇 : 조건을 하향 돌파 불만족하여 매도처리 했어요!! 현재 수익률 : 약 " + str(round(revenue_data['revenue_rate'],2)) + "% 수익금 : 약" + str(format(round(revenue_data['revenue_money']), ',')) + "원"
                print(msg)
                line_alert.SendMessage(msg)
            else:
                            
                msg = coin_ticker + " 업비트 안전 전략 봇 : 조건을 불만족하여 매도처리 했어요!! 현재 수익률 : 약 " + str(round(revenue_data['revenue_rate'],2)) + "% 수익금 : 약" + str(format(round(revenue_data['revenue_money']), ',')) + "원"
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
        
        if coin_ticker == 'KRW-ETH':
            
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



        IsAdditionalCondition = False
        
        if coin_ticker == 'KRW-ETH':
            if (df_day['5ma'].iloc[-3] <= df_day['5ma'].iloc[-2] and df_day['5ma'].iloc[-2] <= PrevClose) and (df_day['24ma'].iloc[-3] <= df_day['24ma'].iloc[-2] and df_day['24ma'].iloc[-2] <= PrevClose):
                IsAdditionalCondition = True
                    


        else:
            if (df_day['3ma'].iloc[-3] <= df_day['3ma'].iloc[-2] and df_day['3ma'].iloc[-2] <= PrevClose) and (df_day['33ma'].iloc[-3] <= df_day['33ma'].iloc[-2] and df_day['33ma'].iloc[-2] <= PrevClose):
                IsAdditionalCondition = True
                
                
        #도지 캔들 패턴 체크
        prev_high_low_gap = abs(df_day['high'].iloc[-2] - df_day['low'].iloc[-2])
        prev_open_close_gap = abs(df_day['open'].iloc[-2] - df_day['close'].iloc[-2])



        #시가와 종가의 갭이 고가와 저가의 갭의 10% 이하라면 도지 캔들로 판단
        if (prev_high_low_gap > 0 and (prev_open_close_gap / prev_high_low_gap) <= 0.1) :
            IsMaDone = False


        #저장된 매도날짜와 오늘 날짜가 같다면.. 매도가 된 상황이니깐 오늘은 매수 하면 안된다.
        if BotDataDict[coin_ticker+"_SELL_DATE"] == day_str:
            IsMaDone = False



        if IsMaDone == True and IsAdditionalCondition == True :

            Rate = 1.0

            ########################################################################################################
            ''' 이 부분을 주석처리 하면 감산 로직이 제거 됩니다 
            if Ma50_before > Ma50 or Ma50 > df_day['close'].iloc[-2]:
                Rate *= 0.5
            '''
            ########################################################################################################


            BuyGoMoney = InvestMoneyCell * Rate

            #투자금 거래대금 10일 평균의 1/2000수준으로 제한!
            if BuyGoMoney >= df_day['value_ma'].iloc[-2] / 2000:
                BuyGoMoney = df_day['value_ma'].iloc[-2] / 2000

            BuyMoney = BuyGoMoney 


                
            ########################################################################################
            #현재 투자 평가금을 구한다!
            NowMoney = myUpbit.GetCoinNowRealMoney(balances,coin_ticker)
            
            #해당 코인에 할당된 금액!!!
            TargetTotalMoney = InvestTotalMoney * (coin_data['rate'] + coin_data['fix_rate'])

            
            #투자로 정해진 금액보다 살금액 + 현재 투자금이 더 크다면?
            if TargetTotalMoney < (BuyMoney + NowMoney):
                BuyMoney = TargetTotalMoney - NowMoney #살 금액을 정해진 금액에서 현재 투자금의 차액으로 정해준다!!!           

            #투자로 정해진 금액보다 살금액 + 현재 투자금이 더 작다면?? 비중이 모자라다 채워주자! 그 갭만큼!!
            elif TargetTotalMoney > (BuyMoney + NowMoney):
                BuyMoney += (TargetTotalMoney - (BuyMoney + NowMoney))



            #######################################################################################
            
            #원화 잔고를 가져온다
            won = float(upbit.get_balance("KRW"))
            print("# Remain Won :", won)
            time.sleep(0.004)
            
            #
            if BuyMoney > won:
                BuyMoney = won * 0.99 #수수료 및 슬리피지 고려
                
            
            if BuyMoney >= minmunMoney:

                balances = myUpbit.BuyCoinMarket(upbit,coin_ticker,BuyMoney)

                
    
                ############################# FixV ####################################
                BotDataDict[coin_ticker+"_HAS"] = True

                #매수했다면 매수 날짜를 기록한다.
                BotDataDict[coin_ticker+"_BUY_DATE"] = day_str
                #파일에 저장
                with open(botdata_file_path, 'w') as outfile:
                    json.dump(BotDataDict, outfile)

                    
                    
                    
                msg = coin_ticker + " 업비트 안전 전략 봇 :  조건 만족 하여 매수!! " + str(BuyMoney) + "원어치 매수!"

                print(msg)
                line_alert.SendMessage(msg)

        else:
            #매일 아침 9시 정각에..
            if hour_n == 0 and min_n == 0:
                msg = coin_ticker + " 업비트 안전 전략 봇 :  조건 만족하지 않아 현금 보유 합니다!"
                print(msg)
                line_alert.SendMessage(msg)
            


    ############################# FixV ####################################
    if coin_data['fix_rate'] > 0:

        #내가 가진 잔고 데이터를 다 가져온다.
        balances = upbit.get_balances()

        RealMoney = myUpbit.GetCoinNowRealMoney(balances,coin_ticker)
        
        #잔고가 없다면 고정 비중만큼 매수한다!
        if myUpbit.IsHasCoin(balances,coin_ticker) == False: 
            
            #고정 비중 만큼 매수한다!!!!
            InvestMoneyCell = InvestFixMoney * 0.995

            Rate = 1.0
            BuyGoMoney = InvestMoneyCell * Rate

            #투자금 거래대금 10일 평균의 1/2000수준으로 제한!
            if BuyGoMoney >= df_day['value_ma'].iloc[-2] / 2000:
                BuyGoMoney = df_day['value_ma'].iloc[-2] / 2000

            BuyMoney = BuyGoMoney 

            #원화 잔고를 가져온다
            won = float(upbit.get_balance("KRW"))
            print("# Remain Won :", won)
            time.sleep(0.004)
            
            #
            if BuyMoney > won:
                BuyMoney = won * 0.99 #수수료 및 슬리피지 고려

            balances = myUpbit.BuyCoinMarket(upbit,coin_ticker,BuyMoney)


            msg = coin_ticker + " 업비트 안전 전략 봇 :  고정비중이 없어 투자!!"
            print(msg)
            line_alert.SendMessage(msg)
            
        else:
                    
            if Fix_Rebalance_Enable == True and BotDataDict[coin_ticker+"_HAS"] == False:
                print("고정 비중 투자 잔고가 있는 경우.. 리밸런싱이 필요하다면 리밸런싱!!")

                TargetTotalMoney = InvestTotalMoney * 0.995

                #현재 코인의 총 매수금액
                NowCoinTotalMoney = myUpbit.GetCoinNowRealMoney(balances,coin_ticker)
                
                print(NowCoinTotalMoney, " / ", TargetTotalMoney)

                Rate = NowCoinTotalMoney / TargetTotalMoney
                print("--------------> coin_ticker rate : ", Rate, coin_data['fix_rate'] )

                #코인 목표 비중과 현재 비중이 다르다.
                if Rate != coin_data['fix_rate']:

                    #갭을 구한다!!!
                    GapRate = coin_data['fix_rate'] - Rate
                    print("--------------> coin_ticker Gaprate : ", GapRate)


                    GapMoney = TargetTotalMoney * abs(GapRate)

                    #갭이 음수면 코인 비중보다 수익이 나서 더 많은 비중을 차지하고 있는 경우
                    if GapRate < 0:
                        
                        #고정비중의 1/10이상의 갭이 있을때 리밸런싱이 진행!!
                        if GapMoney >= minmunMoney and abs(GapRate) >= (coin_data['fix_rate'] / 10.0): 
                            
                            #그 갭만큼 수량을 구해서 
                            GapAmt = GapMoney / pyupbit.get_current_price(coin_ticker)

                            #시장가 매도를 한다.
                            balances = myUpbit.SellCoinMarket(upbit,coin_ticker,GapAmt)

                            
                            line_alert.SendMessage(coin_ticker + " 업비트 안전 전략 봇 : 리밸런싱 진행!!!! 일부 매도!" )
                            print("--------------> SELL ",coin_ticker,"!!!!")



                    #갭이 양수면 비트코인 비중이 적으니 추매할 필요가 있는 경우
                    else:

                        #고정비중의 1/10이상의 갭이 있을때 리밸런싱이 진행!!
                        if GapMoney >=  minmunMoney and abs(GapRate) >= (coin_data['fix_rate'] / 10.0):

                            balances = myUpbit.BuyCoinMarket(upbit,coin_ticker,GapMoney)
                            
                            line_alert.SendMessage(coin_ticker + " 업비트 안전 전략 봇 : 리밸런싱 진행!!! 일부 매수!" )
                            print("--------------> BUY ",coin_ticker,"!!!!")
                    

                    

