#-*-coding:utf-8 -*-
'''

관련 포스팅

업비트 자동매매 연복리 60%이상의 괴물 전략! - 구간 분할 장기 투자 전략!
https://blog.naver.com/zacra/223052327452

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

import line_alert



#암복호화 클래스 객체를 미리 생성한 키를 받아 생성한다.
simpleEnDecrypt = myUpbit.SimpleEnDecrypt(ende_key.ende_key)

#암호화된 액세스키와 시크릿키를 읽어 복호화 한다.
Upbit_AccessKey = simpleEnDecrypt.decrypt(my_key.upbit_access)
Upbit_ScretKey = simpleEnDecrypt.decrypt(my_key.upbit_secret)

#업비트 객체를 만든다
upbit = pyupbit.Upbit(Upbit_AccessKey, Upbit_ScretKey)





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





#최소 매수 금액
minmunMoney = 5500

#내가 가진 잔고 데이터를 다 가져온다.
balances = upbit.get_balances()

TotalMoeny = myUpbit.GetTotalMoney(balances) #총 원금
TotalRealMoney = myUpbit.GetTotalRealMoney(balances) #총 평가금액

print("TotalMoeny", TotalMoeny)
print("TotalRealMoney", TotalRealMoney)
#투자 비중 -> 1.0 : 100%  0.5 : 50%   0.1 : 10%
InvestRate = 1.0 #투자 비중은 자금사정에 맞게 수정하세요! 검증할때는 소액으로 하는게 옳아요!

##########################################################################
InvestTotalMoney = TotalRealMoney * InvestRate #총 평가금액을 투자 원금으로 한다!!!!!
##########################################################################



#현재 구간 정보를 저장
GuganCoinInfoDict = dict()

#파일 경로입니다.
gugan_file_path = "/var/autobot/UpbitGuganStatus.json"
try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(gugan_file_path, 'r') as json_file:
        GuganCoinInfoDict = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")



#투자가 시작되었는지 여부
GuganStartCoinInfoDict = dict()

#파일 경로입니다.
startflag_file_path = "/var/autobot/UpbitGuganStargFlag.json"
try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(startflag_file_path, 'r') as json_file:
        GuganStartCoinInfoDict = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")




######################################## 1. 균등 분할 투자 ###########################################################
#InvestCoinList = ["KRW-BTC","KRW-ETH",'KRW-ADA','KRW-DOT','KRW-POL']
##########################################################################################################


######################################## 2. 차등 분할 투자 ###################################################
#'''
InvestCoinList = list()

InvestDataDict = dict()
InvestDataDict['ticker'] = "KRW-BTC"
InvestDataDict['rate'] = 0.4
InvestCoinList.append(InvestDataDict)

InvestDataDict = dict()
InvestDataDict['ticker'] = "KRW-ETH"
InvestDataDict['rate'] = 0.3
InvestCoinList.append(InvestDataDict)


InvestDataDict = dict()
InvestDataDict['ticker'] = "KRW-ADA"
InvestDataDict['rate'] = 0.1
InvestCoinList.append(InvestDataDict)


InvestDataDict = dict()
InvestDataDict['ticker'] = "KRW-DOT"
InvestDataDict['rate'] = 0.1
InvestCoinList.append(InvestDataDict)


InvestDataDict = dict()
InvestDataDict['ticker'] = "KRW-POL"
InvestDataDict['rate'] = 0.1
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

    InvestMoney = InvestTotalMoney * coin_data['rate'] #설정된 투자금에 맞게 투자!
#'''
##########################################################################################################

    print(coin_ticker, " 종목당 할당 투자금:", InvestMoney)

    DivNum = 10 #구간은 10분할로!!!

    target_period = 60 #60일 기간의 값의 변동으로 구간을 삼는다!
    
    ## 20, 20 으로 바꾸는 등으로 변경하면 더 성과가 좋아집니다!!

    #원화 잔고를 가져온다
    won = float(upbit.get_balance("KRW"))
    print("# Remain Won :", won)
    time.sleep(0.004)
    
    #분할된 가격!
    InvestMoneyCell = InvestMoney / DivNum
    print("InvestMoneyCell", InvestMoneyCell)



    df_day = pyupbit.get_ohlcv(coin_ticker,interval="day")
    time.sleep(0.04)

    Ma5 = myUpbit.GetMA(df_day,5,-2)   #전일 종가 기준 5일 이동평균선
    Ma20 = myUpbit.GetMA(df_day,20,-2) #전일 종가 기준 20일 이동평균선



    #현재가를 구하다
    NowOpenPrice = pyupbit.get_current_price(coin_ticker)


    #최고가와 최저가를 구해서
    high_list = list()
    low_list = list()

    for index in range(2,(target_period+2)):
        high_list.append(df_day['high'].iloc[-index])
        low_list.append(df_day['low'].iloc[-index])

    high_price = float(max(high_list))
    low_price =  float(min(low_list))

    Gap = (high_price - low_price) / DivNum

    #현재 구간을 구한다!!!
    now_step = DivNum #추가된 부분!!
    
    for step in range(1,DivNum+1):
        if NowOpenPrice < low_price + (Gap * step):
            now_step = step
            break

    print("-----------------",now_step,"-------------------\n")

    #딕셔너리에 구간 값이 없는 즉 봇 처음 실행하는 시점이라면 현재 구간을 저장해 둔다!!!
    if GuganCoinInfoDict.get(coin_ticker) == None:
        GuganCoinInfoDict[coin_ticker] = now_step
        #파일에 저장합니다
        with open(gugan_file_path, 'w') as outfile:
            json.dump(GuganCoinInfoDict, outfile)


    if GuganStartCoinInfoDict.get(coin_ticker) == None:
        if myUpbit.IsHasCoin(balances,coin_ticker) == True:
            GuganStartCoinInfoDict[coin_ticker] = True
        else:
            GuganStartCoinInfoDict[coin_ticker] = False
        #파일에 저장합니다
        with open(startflag_file_path, 'w') as outfile:
            json.dump(GuganStartCoinInfoDict, outfile)



    #잔고가 있거나 이 전략으로 스타트된 경우!!
    if myUpbit.IsHasCoin(balances,coin_ticker) == True or GuganStartCoinInfoDict[coin_ticker] == True: 
        print("잔고가 있는 경우!")
        
        NowRealCoinMoney = 0

        if myUpbit.IsHasCoin(balances,coin_ticker) == True :
            NowRealCoinMoney = myUpbit.GetCoinNowRealMoney(balances,coin_ticker)
            

        RemainMoney = InvestMoney - NowRealCoinMoney

        AllAmt = 0
        if myUpbit.IsHasCoin(balances,coin_ticker) == True :
            AllAmt = upbit.get_balance(coin_ticker) #현재 수량
            
            
        print("현재 수량 :", AllAmt)
        print("현재 평가금 :", NowRealCoinMoney, "남은 현금:", RemainMoney ," 10분할금 : ", InvestMoneyCell)


        #스텝(구간)이 다르다!
        if GuganCoinInfoDict[coin_ticker] != now_step:
            print("")

            step_gap = now_step - GuganCoinInfoDict[coin_ticker] #구간 갮을 구함!


            GuganCoinInfoDict[coin_ticker] = now_step
            #파일에 저장합니다
            with open(gugan_file_path, 'w') as outfile:
                json.dump(GuganCoinInfoDict, outfile)


            if step_gap >= 1: #스텝이 증가!! 매수!!

                if Ma20 < df_day['close'].iloc[-2]:

                    #남은 현금이 있을 때만 
                    if RemainMoney >= InvestMoneyCell*abs(step_gap) and won >= minmunMoney:

                        #10분할된 금액에 스텝 증가분을 곲해서 매수한다!
                        balances = myUpbit.BuyCoinMarket(upbit,coin_ticker,InvestMoneyCell*abs(step_gap))

                        msg = coin_ticker + " 구간이 증가되었어요! 그래서 매수했어요! ^^ " + " 현재 " + str(GuganCoinInfoDict[coin_ticker]) + "구간"
                        print(msg)
                        line_alert.SendMessage(msg)
                    else:
                        msg = coin_ticker + " 구간이 증가되어 매수해야되지만 그만한 할당 현금이 없어 하지 않았어요! ^^" + " 현재 " + str(GuganCoinInfoDict[coin_ticker]) + "구간"
                        print(msg)
                        line_alert.SendMessage(msg)
                else:
                    msg = coin_ticker + " 구간이 증가되어 매수해야되지만 이평선 조건을 만족하지 않아 하지 않았어요! ^^" + " 현재 " + str(GuganCoinInfoDict[coin_ticker]) + "구간"
                    print(msg)
                    line_alert.SendMessage(msg)


            elif step_gap <= -1: #스텝이 감소! 매도!!
                
                if myUpbit.IsHasCoin(balances,coin_ticker) == True:

                    if Ma5 > df_day['close'].iloc[-2]:

                        SellAmt = float(InvestMoneyCell*abs(step_gap) / NowOpenPrice) #매도 가능 수량을 구한다!


                        if AllAmt >= SellAmt:

                            
                            balances = myUpbit.SellCoinMarket(upbit,coin_ticker,SellAmt)
                                            
                            msg = coin_ticker + " 구간이 감소되었어요! 그래서 매도했어요! ^^" + " 현재 " + str(GuganCoinInfoDict[coin_ticker]) + "구간"
                            print(msg)
                            line_alert.SendMessage(msg)

                        else:


                            balances = myUpbit.SellCoinMarket(upbit,coin_ticker,AllAmt)
                                            
                            msg = coin_ticker + " 구간이 감소되어 모두 매도처리 했어요!!" + " 현재 " + str(GuganCoinInfoDict[coin_ticker]) + "구간"
                            print(msg)
                            line_alert.SendMessage(msg)

                    else:
                        msg = coin_ticker + " 구간이 감소되어 매도해야되지만 이평선 조건을 만족하지 않아 하지 않았어요! ^^" + " 현재 " + str(GuganCoinInfoDict[coin_ticker]) + "구간"
                        print(msg)
                        line_alert.SendMessage(msg)
                else:

                    msg = coin_ticker + " 구간이 감소되어 매도해야되지만 보유 잔고가 없어요! ^^" + " 현재 " + str(GuganCoinInfoDict[coin_ticker]) + "구간"
                    print(msg)
                    line_alert.SendMessage(msg)
            


        revenue_data = 0
        
        if myUpbit.IsHasCoin(balances,coin_ticker) == True:
            #수익금과 수익률을 구한다!
            revenue_data = GetRevenueMoneyAndRate(balances,coin_ticker)

            
            msg = coin_ticker + "현재 수익률 : 약 " + str(round(revenue_data['revenue_rate'],2)) + "% 수익금 : 약" + str(format(round(revenue_data['revenue_money']), ',')) + "원" + " 현재 " + str(GuganCoinInfoDict[coin_ticker]) + "구간"
            print(msg)
            line_alert.SendMessage(msg)

        else:
            msg = coin_ticker + "현재 " + str(GuganCoinInfoDict[coin_ticker]) + "구간"
            print(msg)
            line_alert.SendMessage(msg)



    else:
        print("잔고없음")

        GuganCoinInfoDict[coin_ticker] = now_step
        #파일에 저장합니다
        with open(gugan_file_path, 'w') as outfile:
            json.dump(GuganCoinInfoDict, outfile)


        #10분할된 금액만큼 매수한다!!
        balances = myUpbit.BuyCoinMarket(upbit,coin_ticker,InvestMoneyCell)

        msg = coin_ticker + "장기 구간 분할 투자 봇 작동 개시!! : " + "현재 " + str(GuganCoinInfoDict[coin_ticker]) + "구간"
        print(msg)
        line_alert.SendMessage(msg)
        
        GuganStartCoinInfoDict[coin_ticker] = True
        #파일에 저장합니다
        with open(startflag_file_path, 'w') as outfile:
            json.dump(GuganStartCoinInfoDict, outfile)
















