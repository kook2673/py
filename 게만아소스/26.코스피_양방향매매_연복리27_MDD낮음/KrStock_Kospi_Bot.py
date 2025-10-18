#-*-coding:utf-8 -*-
'''

관련 포스팅

연복리 26%의 MDD 10~16의 강력한 코스피 지수 양방향 매매 전략!
https://blog.naver.com/zacra/223085637779

위 포스팅을 꼭 참고하세요!!!



📌 [코드 제공 목적]

이 코드는 클래스101 게만아 <파이썬 자동매매 봇 만들기> 강의의 보조 자료로 제공되며,  
강의 수강생의 **학습 및 실습을 위한 참고용 예시 코드**입니다.  
**투자 권유, 종목 추천, 자문 또는 일임을 위한 목적은 전혀 없습니다.**

📌 [기술 구현 관련 안내]

- 본 코드는 **증권사에서 공식적으로 제공한 API** 및  
  **공식 개발자 가이드 문서**에 따라 구현되었습니다.
- 해당 API는 일반 투자자 누구나 이용 가능한 서비스이며,  
  본 코드는 그것을 구현한 예시를 활용해 전략을 구현해보는 학습 목적으로 활용한 것입니다.

📌 [전략 실행 조건]

- 본 코드는 자동 반복 실행되지 않으며, 사용자가 직접 실행해야 1회 동작합니다.
- 반복 실행을 원할 경우, 사용자가 별도로 서버 및 스케줄러 구성을 해야 합니다.


- 본 코드에는 증권사 제공 API를 활용한 매매 기능이 포함되어 있으나,  
  **사용자가 명시적으로 설정을 변경하지 않는 한 실행되지 않습니다.**
  

- 전략 실행을 위해서는 다음의 과정을 **사용자가 직접** 수행해야 합니다:

  1. `ENABLE_ORDER_EXECUTION` 값을 `True`로 변경  
  2. `InvestRate` 비중을 설정 (기본값: 0)  
  3. 매수할 종목을 명시 (기본값: 빈 리스트)  
  4. AWS 또는 개인 서버 구축 및 `crontab` 또는 스케줄러 등록

- 제공자는 서버 구축, 설정, 실행 대행 등을 전혀 하지 않습니다.

📌 [법적 책임 고지]

- 제공되는 코드는 기술 학습 및 테스트 목적의 예시 코드입니다.  
- **백테스트 결과는 과거 데이터 기반이며, 미래 수익을 보장하지 않습니다.**

- 본 코드의 사용, 수정, 실행에 따른 모든 결과와 책임은 사용자에게 있으며,  
  **제공자는 법적·금전적 책임을 일절 지지 않습니다.**

📌 [저작권 안내]

- 이 코드는 저작권법 및 부정경쟁방지법의 보호를 받습니다.  
- 무단 복제, 공유, 재판매, 배포 시 민·형사상 책임이 따를 수 있습니다.

📌 [학습 권장 사항]

- 본 예시 코드는 전략 구현을 이해하기 위한 템플릿입니다.  
- 이를 바탕으로 자신만의 전략을 개발해보시길 권장드립니다 :)



주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!


'''

import KIS_Common as Common
import KIS_API_Helper_KR as KisKR
import time
import json
import pprint

import line_alert



#계좌 선택.. "VIRTUAL" 는 모의 계좌!
Common.SetChangeMode("VIRTUAL") #REAL or VIRTUAL



#####################################################################################################################################
'''
※ 주문 실행 여부 설정

ENABLE_ORDER_EXECUTION 값을 True로 변경할 경우,  
전략에 따라 매매가 일어납니다.

⚠️ 기본값은 False이며,  
실행 여부는 사용자 본인이 코드를 수정하여 결정해야 합니다.
'''

ENABLE_ORDER_EXECUTION = False  # 주문 실행 여부 설정 (기본값: False)

'''
📌 본 전략은 시스템을 구현하는 예시 코드이며,  
실제 투자 및 주문 실행은 사용자 본인의 의사와 책임 하에 수행됩니다.
'''
#####################################################################################################################################

'''
📌 투자할 종목은 본인의 선택으로 리스트 형식으로 직접 입력하세요!
'''
InverseStockCode = '' #직접 종목을 넣으세요!
#InverseStockCode = '252670' #인버스

InvestStockList = list()

InvestDataDict = dict()
InvestDataDict['ticker'] = "" # 직접 종목을 넣으세요
#InvestDataDict['ticker'] = "122630" # 레버리지
InvestDataDict['rate'] = 0.7
InvestStockList.append(InvestDataDict)


InvestDataDict = dict()
InvestDataDict['ticker'] = ""  # 직접 종목을 넣으세요
#InvestDataDict['ticker'] = "252670"  # 인버스
InvestDataDict['rate'] = 0.3
InvestStockList.append(InvestDataDict)

#####################################################################################################################################

'''
📌 투자 비중 설정!
기본은 0으로 설정되어 있어요.
본인의 투자 비중을 설정하세요! 

전략에서 활용할 주문이 
시장가 주문이라면 0 ~ 0.75 
지정가 주문이라면 0 ~ 0.98
사이의 값으로 설정하세요! (0.1 = 10% 0.5 = 50%)
'''
InvestRate = 0 #총 평가금액에서 해당 봇에게 할당할 총 금액비율 0.1 = 10%  0.5 = 50%
#####################################################################################################################################





BOT_NAME = Common.GetNowDist() + "_MyKospi_ETF_Bot"


#포트폴리오 이름
PortfolioName = "게만아 코스피 지수 양방향 매매 전략!"


#시간 정보를 읽는다
time_info = time.gmtime()


print("time_info.tm_mon", time_info.tm_mon)





#####################################################################################################################################

#계좌 잔고를 가지고 온다!
Balance = KisKR.GetBalance()


print("--------------내 보유 잔고---------------------")

pprint.pprint(Balance)

print("--------------------------------------------")


##########################################################

print("--------------내 보유 주식---------------------")
#그리고 현재 이 계좌에서 보유한 주식 리스트를 가지고 옵니다!
MyStockList = KisKR.GetMyStockList()
pprint.pprint(MyStockList)
print("--------------------------------------------")
##########################################################




#기준이 되는 내 총 평가금액에서 투자비중을 곱해서 나온 포트폴리오에 할당된 돈!!
TotalMoney = float(Balance['TotalMoney']) * InvestRate

print("전략에 투자하는 총 금액: ", format(round(TotalMoney), ','))


if ENABLE_ORDER_EXECUTION == True:

    #마켓이 열렸는지 여부~!
    IsMarketOpen = KisKR.IsMarketOpen()

    if IsMarketOpen == True:
        print("Market Is Open!!!!!!!!!!!")

        #혹시 이 봇을 장 시작하자 마자 돌린다면 20초르 쉬어준다.
        #그 이유는 20초는 지나야 오늘의 일봉 정보를 제대로 가져오는데
        #tm_hour가 0은 9시, 1은 10시를 뜻한다. 수능 등 10시에 장 시작하는 경우르 대비!
        if time_info.tm_hour in [0,1] and time_info.tm_min == 0:
            time.sleep(20.0)
            
        line_alert.SendMessage(PortfolioName + "  장이 열려서 매매 가능!!")



        for stock_data in InvestStockList:

            stock_code = stock_data['ticker']

            InvestMoney = TotalMoney * stock_data['rate']

            #일봉 정보를 가지고 온다!
            df_day = Common.GetOhlcv("KR",stock_code)

            #인버스를 위한 3, 6, 19선으로 투자
            Ma3 = Common.GetMA(df_day,3,-2)   #전일 종가 기준 3일 이동평균선
            Ma6 = Common.GetMA(df_day,6,-2)   #전일 종가 기준 6일 이동평균선
            Ma19 = Common.GetMA(df_day,19,-2)   #전일 종가 기준 19일 이동평균선

            Ma60_before = Common.GetMA(df_day,60,-3) # 전전일 종가 기준 60일 이동평균선
            Ma60 = Common.GetMA(df_day,60,-2) # 전일 종가 기준 60일 이동평균선

            PrevClose = df_day['close'].iloc[-2] #전일 종가!

            Disparity11 = (PrevClose/Common.GetMA(df_day,11,-2))*100.0 #전일 종가 기준 11선 이격도
            Disparity20 = (PrevClose/Common.GetMA(df_day,20,-2))*100.0 #전일 종가 기준 20선 이격도


            Rsi_before = Common.GetRSI(df_day,14,-3) 
            Rsi = Common.GetRSI(df_day,14,-2) 


            stock_name = ""
            stock_amt = 0 #수량
            stock_avg_price = 0 #평단
            stock_eval_totalmoney = 0 #총평가금액!
            stock_revenue_rate = 0 #종목 수익률
            stock_revenue_money = 0 #종목 수익금

        
            
            #내가 보유한 주식 리스트에서 매수된 잔고 정보를 가져온다
            for my_stock in MyStockList:
                if my_stock['StockCode'] == stock_code:
                    stock_name = my_stock['StockName']
                    stock_amt = int(my_stock['StockAmt'])
                    stock_avg_price = float(my_stock['StockAvgPrice'])
                    stock_eval_totalmoney = float(my_stock['StockNowMoney'])
                    stock_revenue_rate = float(my_stock['StockRevenueRate'])
                    stock_revenue_money = float(my_stock['StockRevenueMoney'])

                    break

            #잔고에 없는 경우 
            if stock_amt == 0:
                stock_name = KisKR.GetStockName(stock_code)


            print("----stock_code: ", stock_code, " ", stock_name)

            print("종목당 할당 투자금:", InvestMoney)


            print("Ma3: ", Ma3)
            print("Ma6: ", Ma6)
            print("Ma19: ", Ma19)
            print("Ma60: ", Ma60)
            print("PrevClose: ", PrevClose)
            print("Disparity11: ", Disparity11)
            print("Disparity20: ", Disparity20)

            #잔고가 있다 즉 매수된 상태다!
            if stock_amt > 0:


                IsSellGo = False
                


                if InverseStockCode == stock_code: #인버스
        
                    if Disparity11 > 105:
                        #
                        if  PrevClose < Ma3: 
                            IsSellGo = True

                    else:
                        #
                        if PrevClose < Ma6 and PrevClose < Ma19 : 
                            IsSellGo = True

                else:

                    total_volume = (df_day['volume'].iloc[-4] + df_day['volume'].iloc[-3] + df_day['volume'].iloc[-2]) / 3.0

                    if (df_day['low'].iloc[-3] < df_day['low'].iloc[-2] or df_day['volume'].iloc[-2] < total_volume) and (Disparity20 < 98 or Disparity20 > 105):
                        print("hold..")
                    else:
                        IsSellGo = True


                if IsSellGo == True:
    
                    #이렇게 시장가로 매도 해도 큰 무리는 없어 보인다!       
                    pprint.pprint(KisKR.MakeSellMarketOrder(stock_code,stock_amt))


                    #나중에 투자금이 커지면 시장가 매도시 큰 슬리피지가 있을수 있으므로 아래의 코드로 지정가 주문을 날려도 된다 
                    '''
                    CurrentPrice = KisKR.GetCurrentPrice(stock_code)
                    CurrentPrice *= 0.99 #현재가의 1%아래의 가격으로 지정가 매도.. (그럼 1%아래 가격보다 큰 가격의 호가들은 모두 체결되기에 제한있는 시장가 매도 효과)
                    pprint.pprint(KisKR.MakeSellLimitOrder(stock_code,stock_amt,CurrentPrice))
                    '''
                    


                    msg = stock_name + "  조건을 불만족해 모두 매도!!!" + str(stock_revenue_money) + " 수익 확정!! 수익률:" + str(stock_revenue_rate) + "%"
                    print(msg)
                    line_alert.SendMessage(msg)

                else:

                    msg = stock_name + "  투자중..!!!" + str(stock_revenue_money) + " 수익 중!! 수익률:" + str(stock_revenue_rate) + "%"
                    print(msg)
                    line_alert.SendMessage(msg)
                        
            #잔고가 없는 경우
            else:


                IsBuyGo = False



                if InverseStockCode == stock_code:

                    if PrevClose > Ma3 and PrevClose > Ma6  and PrevClose > Ma19 and Rsi < 70 and Rsi_before < Rsi:
                        if PrevClose > Ma60 and Ma60_before < Ma60  and Ma3 > Ma6 > Ma19 :
                            IsBuyGo = True

                else:

                    if df_day['low'].iloc[-3] < df_day['low'].iloc[-2] and Rsi < 80 and (Disparity20 < 98 or Disparity20 > 106) :
                        IsBuyGo = True
                

                if IsBuyGo == True:



                    #현재가!
                    CurrentPrice = KisKR.GetCurrentPrice(stock_code)


                    #매수할 수량을 계산한다!
                    BuyAmt = int(InvestMoney / CurrentPrice)

                    #최소 1주는 살 수 있도록!
                    if BuyAmt <= 0:
                        BuyAmt = 1


            
                    #이렇게 시장가로 매수 해도 큰 무리는 없어 보인다!  
                    pprint.pprint(KisKR.MakeBuyMarketOrder(stock_code,BuyAmt))

                    #나중에 투자금이 커지면 시장가 매수시 큰 슬리피지가 있을수 있으므로 아래의 코드로 지정가 주문을 날려도 된다 
                    '''
                    CurrentPrice = KisKR.GetCurrentPrice(stock_code)
                    CurrentPrice *= 1.01 #현재가의 1%위의 가격으로 지정가 매수.. (그럼 1% 위 가격보다 작은 가격의 호가들은 모두 체결되기에 제한있는 시장가 매수 효과)
                    pprint.pprint(KisKR.MakeBuyLimitOrder(stock_code,BuyAmt,CurrentPrice))
                    '''


    

                    msg = stock_name + "  조건을 만족하여 매수!!! 투자 시작!! "
                    print(msg)
                    line_alert.SendMessage(msg)
                else:

                    msg = stock_name + "  조건 불만족!!! 투자 안함."
                    print(msg)
                    line_alert.SendMessage(msg)

    else:
        print("Market Is Close!!!!!!!!!!!")
        #영상엔 없지만 리밸런싱이 가능할때만 내게 메시지를 보내자!

        line_alert.SendMessage(PortfolioName + "  장이 열려있지 않아요!")

else:
    print("코드 맨 첫 부분에 ENABLE_ORDER_EXECUTION 값을 True로 변경해야 매수매도가 진행됩니다!")

