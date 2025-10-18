# -*- coding: utf-8 -*-
'''

-*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*-
pykrx오류 발생!!
해당 봇의 오류가 발생한다면 아래 포스팅을 참고하여 수정하세요!!!
https://blog.naver.com/zacra/223505969974
-*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*-

-*- 백테스팅 코드가 있는 전략들은 패키지 16번 부터 나오기 시작하니 참고하세요!! -*-


관련 포스팅

국내 상장된 모든 ETF를 동시에 매매!? 에브리씽 에브리웨어 올 앳 원스 ETF전략!
https://blog.naver.com/zacra/223013097411

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



주식/코인 파이썬 매매 FAQ
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
from pykrx import stock

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
📌 투자할 종목 개수는 본인의 선택으로 아래 같은 형식으로 추가하세요!
'''
InvestCnt = 50 #총 50개의 ETF에 분산투자한다!

#해당 봇이 매매하면 안되는 ETF! 즉 다른 전략에서 사용하는 ETF를 넣는다.
OutETFList = []
#OutETFList = ["122630","252670","233740","251340"] #예로 코스닥피레인 전략과 돌린다면 해당 전략의 ETF들을 이런식으로 넣어두면 됨!

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



BOT_NAME = Common.GetNowDist() + "_MyKR_ALL_ETF_Bot"




#시간 정보를 읽는다
time_info = time.gmtime()

#혹시 이 봇을 장 시작하자 마자 돌린다면 20초르 쉬어준다.
#그 이유는 20초는 지나야 오늘의 일봉 정보를 제대로 가져오는데
#tm_hour가 0은 9시, 1은 10시를 뜻한다. 수능 등 10시에 장 시작하는 경우르 대비!
if time_info.tm_hour in [0,1] and time_info.tm_min == 0:
    time.sleep(20.0)
    
print("time_info.tm_mday", time_info.tm_mday)

#포트폴리오 이름
PortfolioName = "게만아 한국 모든 ETF 전략!"




#####################################################################################################################################
#####################################################################################################################################
#####################################################################################################################################
'''
if int(time_info.tm_mday) % 2 == 0:

    print(PortfolioName + "  오늘을 짝수일 이어서 동작하지 않습니다!!")
    line_alert.SendMessage(PortfolioName + "  오늘을 짝수일 이어서 동작하지 않습니다!!")
'''   

if int(time_info.tm_mday) % 2 == 1:

    print(PortfolioName + "  오늘을 홀수일 이어서 동작하지 않습니다!!")
    line_alert.SendMessage(PortfolioName + "  오늘을 홀수일 이어서 동작하지 않습니다!!")
    
else:


    #마켓이 열렸는지 여부~!
    IsMarketOpen = KisKR.IsMarketOpen()

    if IsMarketOpen == True:
        print("Market Is Open!!!!!!!!!!!")
        #영상엔 없지만 리밸런싱이 가능할때만 내게 메시지를 보내자!
    
        line_alert.SendMessage(PortfolioName + "  장이 열려서 포트폴리오 리밸런싱 가능!!")
    else:
        print("Market Is Close!!!!!!!!!!!")
        #영상엔 없지만 리밸런싱이 가능할때만 내게 메시지를 보내자!

        line_alert.SendMessage(PortfolioName + "  장이 닫혀서 포트폴리오 리밸런싱 불가능!!")





    #####################################################################################################################################
    #####################################################################################################################################
    #####################################################################################################################################



    #####################################################################################################################################

    #계좌 잔고를 가지고 온다!
    Balance = KisKR.GetBalance()
    #####################################################################################################################################



    print("--------------내 보유 잔고---------------------")

    pprint.pprint(Balance)

    print("--------------------------------------------")


    #기준이 되는 내 총 평가금액에서 투자비중을 곱해서 나온 포트폴리오에 할당된 돈!!
    TotalMoney = float(Balance['TotalMoney']) * InvestRate

    print("총 포트폴리오에 할당된 투자 가능 금액 : ", format(round(TotalMoney), ','))



    ##########################################################

    #투자 주식 리스트
    MyPortfolioList = list()


    StockCodeList = stock.get_etf_ticker_list(Common.GetNowDateStr("KR","NONE"))

    print("len(StockCodeList):",len(StockCodeList))


    for stock_code in StockCodeList:

        #이 로직에 의해 OutETFList 제외!
        if stock_code in OutETFList:
            continue
        
        asset = dict()
        asset['stock_code'] = stock_code          #종목코드
        asset['stock_type'] = "SECTOR"
        asset['stock_target_rate'] = 100/InvestCnt   
        asset['stock_rebalance_amt'] = 0     #리밸런싱 해야하는 수량

        MyPortfolioList.append(asset)



    ##########################################################

    print("--------------내 보유 주식---------------------")
    #그리고 현재 이 계좌에서 보유한 주식 리스트를 가지고 옵니다!
    MyStockList = KisKR.GetMyStockList()
    pprint.pprint(MyStockList)
    print("--------------------------------------------")
    ##########################################################


    line_alert.SendMessage(PortfolioName +" 모멘텀 스코어 구하기 시작!!!!")


    #모든 자산의 모멘텀 스코어 구하기! 
    for stock_info in MyPortfolioList:
        stock_code = stock_info['stock_code']
        try:

            
            stock_type = stock_info['stock_type']
            
            #모멘텀 스코어 초기화
            stock_info['stock_momentum_score_day'] = 0
            stock_info['stock_momentum_score_5day'] = 0
            stock_info['stock_momentum_score_1month'] = 0
            stock_info['stock_momentum_score_fast'] = 0
            stock_info['stock_momentum_score'] = 0

            df = Common.GetOhlcv("KR",stock_code)

            Now_Price = Common.GetCloseData(df,-1) #현재가
            Before_Price = Common.GetCloseData(df,-3) #3일전 종가
            Week_Price = Common.GetCloseData(df,-5) #5일전 
            
            One_Price = Common.GetCloseData(df,-20) #한달 전
            Three_Price = Common.GetCloseData(df,-60) #3달전
            Six_Price = Common.GetCloseData(df,-120) #6달전
            Twelve_Price = Common.GetCloseData(df,-240) #1년전

            Now_MA5 = Now_Price
            Now_MA20 = Now_Price

            try:
                Now_MA5 = Common.GetMA(df,5,-1)  
            except Exception as e:
                print("Exception by First")

            try:
                Now_MA20 = Common.GetMA(df,20,-1) 
            except Exception as e:
                print("Exception by First")


            print(stock_code, Now_Price, One_Price, Three_Price, Six_Price, Twelve_Price)

        
            stock_info['stock_momentum_score_day'] = ((Now_Price - Before_Price) / Before_Price)

            stock_info['stock_momentum_score_5day'] = ((Now_Price - Week_Price) / Week_Price)

            stock_info['stock_momentum_score_1month'] = ((Now_Price - One_Price) / One_Price)

            stock_info['stock_momentum_score_fast'] = (((Now_Price - One_Price) / One_Price) + ((Now_Price - Three_Price) / Three_Price) + ((Now_Price - Six_Price) / Six_Price)) / 3.0

            # 12*1개월 수익률, 4*3개월 수익률, 2*6개월 수익률, 1*12개월 수익률의 합!!
            MomentumScore = (((Now_Price - One_Price) / One_Price) * 12.0) + (((Now_Price - Three_Price) / Three_Price) * 4.0) + (((Now_Price - Six_Price) / Six_Price) * 2.0) + (((Now_Price - Twelve_Price) / Twelve_Price) * 1.0)

            stock_info['stock_momentum_score'] = MomentumScore

            

            if Now_MA5 < Now_Price:
                stock_info['ma5_up'] = True
            else:
                stock_info['ma5_up'] = False


            if Now_MA20 < Now_Price:
                stock_info['ma20_up'] = True
            else:
                stock_info['ma20_up'] = False



            print(KisKR.GetStockName(stock_code) , stock_code," -> MomentumScore: ",MomentumScore)


            Avg_Period = 10.0 #10개월의 평균 모멘텀을 구한다

            #이건 평균 모멘텀을 구하기에 상장된지 얼마 안된 ETF이다.
            if len(df) < Avg_Period * 20:

                #10개 이하면 즉 상장된지 10일도 안지났다? 절대모멘텀은 0.7로 가정하고 비중 조절!!!
                if len(df) < (Avg_Period+1):
                    stock_info['stock_target_rate'] *= 0.70
                    print("#>> 10개이하라 70%만 투자!!")

                else:
                    #남은 데이터를 Avg_Period(10)분할 해서 모멘텀을 구한다
                    Up_Count = 0
                    
                    CellVal = int(len(df)/Avg_Period)

                    Start_Num = -CellVal

                    for i in range(1,int(Avg_Period)+1):
                        CheckPrice = Common.GetCloseData(df,Start_Num)

                        if Now_Price >= CheckPrice:
                            Up_Count += 1.0

                        Start_Num -= CellVal

                    avg_momentum_score = Up_Count/Avg_Period

                    print("#>> 10등분 평균 모멘텀 ", avg_momentum_score)

                    stock_info['stock_target_rate'] *= (0.2 + avg_momentum_score*0.8)

            else:

                #20일이 1달! 10개월 모멘텀
                Up_Count = 0
                Start_Num = -20
                for i in range(1,int(Avg_Period)+1):
                    
                    CheckPrice = Common.GetCloseData(df,Start_Num)
                    print(CheckPrice, "  <<-  df[-", Start_Num,"]")

                    if Now_Price >= CheckPrice:
                        print("UP!")
                        Up_Count += 1.0


                    Start_Num -= 20

                avg_momentum_score = Up_Count/Avg_Period

                print("10개월 평균 모멘텀 ", avg_momentum_score)

                stock_info['stock_target_rate'] *= (0.2 + avg_momentum_score*0.8)


            print("1차 최종 비중: ", stock_info['stock_target_rate'])


        except Exception as e:
            print("Exception,",e)
            line_alert.SendMessage(PortfolioName + " " + str(stock_code) + " 해당 종목 예외 발생 !!!" + str(e))
        
        
    line_alert.SendMessage(PortfolioName +" 모멘텀 스코어 모두 구함!!!!")


    FinalSelectedList = list()

    #1일기준 모멘텀 TOP 10개 추가!!!
    Stockdata = sorted(MyPortfolioList, key=lambda stock_info: (stock_info['stock_momentum_score_day']), reverse= True)
    pprint.pprint(Stockdata)


    for i in range(0,10):
        FinalSelectedList.append(Stockdata[i]['stock_code'])
        




    #5일기준 모멘텀 TOP 10개 추가!!!
    Stockdata = sorted(MyPortfolioList, key=lambda stock_info: (stock_info['stock_momentum_score_5day']), reverse= True)
    pprint.pprint(Stockdata)


    TCnt = 10
    i = 0
    for data in Stockdata:
        
        if i < TCnt:
            
            AlreadyHas = False
            for stock_code in FinalSelectedList:
                if stock_code == data['stock_code']:
                    AlreadyHas = True
                    break
                
            if AlreadyHas == False:
                FinalSelectedList.append(data['stock_code'])
                i += 1
                


    #1달 기준 모멘텀 TOP 10개 추가!!!
    Stockdata = sorted(MyPortfolioList, key=lambda stock_info: (stock_info['stock_momentum_score_1month']), reverse= True)
    pprint.pprint(Stockdata)

    TCnt = 10
    i = 0
    for data in Stockdata:
        
        if i < TCnt:
            
            AlreadyHas = False
            for stock_code in FinalSelectedList:
                if stock_code == data['stock_code']:
                    AlreadyHas = True
                    break
                
            if AlreadyHas == False:
                FinalSelectedList.append(data['stock_code'])
                i += 1
                
        
    
    #1,3,6개월 모멘텀 TOP 10개 추가!!!
    Stockdata = sorted(MyPortfolioList, key=lambda stock_info: (stock_info['stock_momentum_score_fast']), reverse= True)
    pprint.pprint(Stockdata)

    TCnt = 10
    i = 0
    for data in Stockdata:
        
        if i < TCnt:
            
            AlreadyHas = False
            for stock_code in FinalSelectedList:
                if stock_code == data['stock_code']:
                    AlreadyHas = True
                    break
                
            if AlreadyHas == False:
                FinalSelectedList.append(data['stock_code'])
                i += 1


    # 12*1개월 수익률, 4*3개월 수익률, 2*6개월 수익률, 1*12개월 수익률의 합인 가중 모멘텀 TOP 10개 추가!
    Stockdata = sorted(MyPortfolioList, key=lambda stock_info: (stock_info['stock_momentum_score']), reverse= True)
    pprint.pprint(Stockdata)

    TCnt = 10
    i = 0
    for data in Stockdata:
        
        if i < TCnt:
            
            AlreadyHas = False
            for stock_code in FinalSelectedList:
                if stock_code == data['stock_code']:
                    AlreadyHas = True
                    break
                
            if AlreadyHas == False:
                FinalSelectedList.append(data['stock_code'])
                i += 1




    line_alert.SendMessage(PortfolioName +" 투자할 종목 정렬 그리고 선택 완료!!!")



    RemainRate = 0


    print("---------- 최종 선택 리스트 -------------")
    for stock_info in MyPortfolioList:
        stock_code = stock_info['stock_code']

        try:


            
            MomentumScore = stock_info['stock_momentum_score']
            Stock_Name = KisKR.GetStockName(stock_code)

            msg = ""
            print(Stock_Name , stock_code," -> MomentumScore: ",MomentumScore)
            
            if Common.CheckStockCodeInList(FinalSelectedList,stock_code) == True:

                msg = "\n>>>>>>>>>>>>>>" + Stock_Name 

                #20일선 & 5일선 이하라면 절반 감소
                if stock_info['ma5_up'] == False and stock_info['ma20_up'] == False:
                    stock_info['stock_target_rate'] *= 0.5
                    msg += "\n->20일선 & 5일선 밑이라 비중 절반 감소!"

                    
                msg += "\n->" + Stock_Name + " 의 최종 투자비중:" + str(stock_info['stock_target_rate'])
                msg += "\n----------------------------------"


                
                print(msg)
            else:
                stock_info['stock_target_rate'] = 0
                msg = Stock_Name +"> . <  TOP50에 못들어 감.... 투자비중:" + str(stock_info['stock_target_rate'])
                            

            #line_alert.SendMessage(msg)
            print("                                            ")



        except Exception as e:
            print("Exception,",e)
            line_alert.SendMessage(PortfolioName + " " + str(stock_code) + " 해당 종목 예외 발생 !!!" + str(e))
        


    line_alert.SendMessage(PortfolioName +" 투자 비중 최종 완료!!!")



    TotalRate = 0
    for stock_info in MyPortfolioList:

        #내주식 코드
        stock_code = stock_info['stock_code']
        TotalRate += stock_info['stock_target_rate']


    RemainRate = 100.0 - TotalRate

    print(">>>>>>>>>>$$>>>>>>>>>>>>>>>>>> TotalRate", TotalRate , "%")
    print(">>>>>>>>>>$$>>>>>>>>>>>>>>>>>> RemainRate", RemainRate , "%")


    if IsMarketOpen == True and RemainRate > 0:

        print(RemainRate, "% 가 남아서 일단 현금 보유!")
        
        line_alert.SendMessage(PortfolioName + " (" + str(RemainRate) + ") 비중은  일단 현금 보유!")


    print("-----------------Final Top50-------------------------")
    print("-----------------Final Top50-------------------------")
    print("-----------------Final Top50-------------------------")
    print("-----------------Final Top50-------------------------")
    for stock_code in FinalSelectedList:
        print(stock_code + " " + KisKR.GetStockName(stock_code))
    print("-----------------Final Top50-------------------------")
    print("-----------------Final Top50-------------------------")
    print("-----------------Final Top50-------------------------")
    print("-----------------Final Top50-------------------------")


    print("---------- 최종 선택 비중... -------------")
    print("---------- 최종 선택 비중... -------------")
    print("---------- 최종 선택 비중... -------------")
    for stock_info in MyPortfolioList:
        if stock_info['stock_target_rate'] > 0:
            stock_code = stock_info['stock_code']
            Stock_Name = KisKR.GetStockName(stock_code)
            print(Stock_Name , stock_code," -> 비중 : ",stock_info['stock_target_rate'])
            
    print("---------- 최종 선택 비중... -------------")
    print("---------- 최종 선택 비중... -------------")
    print("---------- 최종 선택 비중... -------------")




    line_alert.SendMessage(PortfolioName +" 리밸런싱 수량 계산!!!")




    print("--------------리밸런싱 수량 계산 ---------------------")

    strResult = "-- 현재 포트폴리오 상황 --\n"

    #매수된 자산의 총합!
    total_stock_money = 0

    #현재 평가금액 기준으로 각 자산이 몇 주씩 매수해야 되는지 계산한다 (포트폴리오 비중에 따라) 이게 바로 리밸런싱 목표치가 됩니다.
    for stock_info in MyPortfolioList:

        #내주식 코드
        stock_code = stock_info['stock_code']



        stock_target_rate = float(stock_info['stock_target_rate']) / 100.0

        #현재가!
        CurrentPrice = KisKR.GetCurrentPrice(stock_code)

        

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


        print("#####" , KisKR.GetStockName(stock_code) ," stock_code: ", stock_code)
        print("---> TargetRate:", round(stock_target_rate * 100.0,2) , "%")

        #주식의 총 평가금액을 더해준다
        total_stock_money += stock_eval_totalmoney

        #현재 비중
        stock_now_rate = 0

        #잔고에 있는 경우 즉 이미 매수된 주식의 경우
        if stock_amt > 0:


            stock_now_rate = round((stock_eval_totalmoney / TotalMoney),3)

            print("---> NowRate:", round(stock_now_rate * 100.0,2), "%")

            #최종 선택된 자산리스트에 포함되어 있다면 비중대로 보유해야 한다! 리밸린싱!
            if Common.CheckStockCodeInList(FinalSelectedList,stock_code) == True:


                #목표한 비중가 다르다면!!
                if stock_now_rate != stock_target_rate:


                    #갭을 구한다!!!
                    GapRate = stock_target_rate - stock_now_rate


                    #그래서 그 갭만큼의 금액을 구한다
                    GapMoney = TotalMoney * abs(GapRate) 
                    #현재가로 나눠서 몇주를 매매해야 되는지 계산한다
                    GapAmt = GapMoney / CurrentPrice

                    #수량이 1보다 커야 리밸러싱을 할 수 있다!! 즉 그 전에는 리밸런싱 불가 
                    if GapAmt >= 1.0:

                        GapAmt = int(GapAmt)

                        #갭이 음수라면! 비중이 더 많으니 팔아야 되는 상황!!!
                        if GapRate < 0:

                            #팔아야 되는 상황에서는 현재 주식수량에서 매도할 수량을 뺀 값이 1주는 남아 있어야 한다
                            #그래야 포트폴리오 상에서 아예 사라지는 걸 막는다!
                            if stock_amt - GapAmt >= 1:
                                stock_info['stock_rebalance_amt'] = -GapAmt

                        #갭이 양수라면 비중이 더 적으니 사야되는 상황!
                        else:  
                            stock_info['stock_rebalance_amt'] = GapAmt

            #선택된 자산이 아니라면 전 수량 다 팔아야 한다
            else:
                stock_info['stock_rebalance_amt'] = -stock_amt


        #잔고에 없는 경우
        else:
            #최종 선택된 자산리스트에 포함되어 있다면 비중대로 매수해야 한다!
            if Common.CheckStockCodeInList(FinalSelectedList,stock_code) == True:

                print("---> NowRate: 0%")

                #잔고가 없다면 첫 매수다! 비중대로 매수할 총 금액을 계산한다 
                BuyMoney = TotalMoney * stock_target_rate


                #매수할 수량을 계산한다!
                BuyAmt = int(BuyMoney / CurrentPrice)

                #비중이 들어간건 일단 무조건 1주를 사주자..
                if BuyAmt <= 0 and stock_target_rate > 0:
                    BuyAmt = 1

                stock_info['stock_rebalance_amt'] = BuyAmt
                
                
            
            
            
            
        #라인 메시지랑 로그를 만들기 위한 문자열 
        line_data =  (">> " + KisKR.GetStockName(stock_code) + "(" + stock_code + ") << \n비중: " + str(round(stock_now_rate * 100.0,2)) + "/" + str(round(stock_target_rate * 100.0,2)) 
        + "% \n수익: " + str(format(round(stock_revenue_money), ',')) + "("+ str(round(stock_revenue_rate,2)) 
        + "%) \n총평가금액: " + str(format(round(stock_eval_totalmoney), ',')) 
        + "\n리밸런싱수량: " + str(stock_info['stock_rebalance_amt']) + "\n----------------------\n")

        #만약 아래 한번에 보내는 라인메시지가 짤린다면 아래 주석을 해제하여 개별로 보내면 됩니다
        if stock_info['stock_rebalance_amt'] != 0:
            line_alert.SendMessage(line_data)
        strResult += line_data



    ##########################################################

    print("--------------리밸런싱 해야 되는 수량-------------")

    data_str = "\n" + PortfolioName + "\n" +  strResult + "\n포트폴리오할당금액: " + str(format(round(TotalMoney), ',')) + "\n매수한자산총액: " + str(format(round(total_stock_money), ',') )

    #결과를 출력해 줍니다!
    print(data_str)

    #영상엔 없지만 리밸런싱이 가능할때만 내게 메시지를 보내자!
    #if Is_Rebalance_Go == True:
    #    line_alert.SendMessage(data_str)
        
    #만약 위의 한번에 보내는 라인메시지가 짤린다면 아래 주석을 해제하여 개별로 보내면 됩니다

    line_alert.SendMessage("\n포트폴리오할당금액: " + str(format(round(TotalMoney), ',')) + "\n매수한자산총액: " + str(format(round(total_stock_money), ',') ))




    print("--------------------------------------------")

    ##########################################################


    #리밸런싱이 가능한 상태여야 하고 매수 매도는 장이 열려있어야지만 가능하다!!!
    if IsMarketOpen == True:

        if ENABLE_ORDER_EXECUTION == True:

            line_alert.SendMessage(PortfolioName + "  리밸런싱 시작!!")

            print("------------------리밸런싱 시작  ---------------------")



            #이제 목표치에 맞게 포트폴리오를 조정하면 되는데
            #매도를 해야 돈이 생겨 매수를 할 수 있을 테니
            #먼저 매도를 하고
            #그 다음에 매수를 해서 포트폴리오를 조정합니다!

            print("--------------매도 (리밸런싱 수량이 마이너스인거)---------------------")

            for stock_info in MyPortfolioList:

                #내주식 코드
                stock_code = stock_info['stock_code']
                rebalance_amt = stock_info['stock_rebalance_amt']

                #리밸런싱 수량이 마이너스인 것을 찾아 매도 한다!
                if rebalance_amt < 0:
                                
                    #이렇게 시장가로 매도 해도 큰 무리는 없어 보인다!       
                    pprint.pprint(KisKR.MakeSellMarketOrder(stock_code,abs(rebalance_amt)))


                    #나중에 투자금이 커지면 시장가 매도시 큰 슬리피지가 있을수 있으므로 아래의 코드로 지정가 주문을 날려도 된다 
                    '''
                    CurrentPrice = KisKR.GetCurrentPrice(stock_code)
                    CurrentPrice *= 0.99 #현재가의 1%아래의 가격으로 지정가 매도.. (그럼 1%아래 가격보다 큰 가격의 호가들은 모두 체결되기에 제한있는 시장가 매도 효과)
                    pprint.pprint(KisKR.MakeSellLimitOrder(stock_code,abs(rebalance_amt),CurrentPrice))
                    '''
                    




            print("--------------------------------------------")


            #3초 정도 쉬어준다
            time.sleep(3.0)



            print("--------------매수 ---------------------")

            for stock_info in MyPortfolioList:

                #내주식 코드
                stock_code = stock_info['stock_code']
                rebalance_amt = stock_info['stock_rebalance_amt']

                #리밸런싱 수량이 플러스인 것을 찾아 매수 한다!
                if rebalance_amt > 0:


                    #이렇게 시장가로 매수 해도 큰 무리는 없어 보인다!  
                    pprint.pprint(KisKR.MakeBuyMarketOrder(stock_code,rebalance_amt))

                    #나중에 투자금이 커지면 시장가 매수시 큰 슬리피지가 있을수 있으므로 아래의 코드로 지정가 주문을 날려도 된다 
                    '''
                    CurrentPrice = KisKR.GetCurrentPrice(stock_code)
                    CurrentPrice *= 1.01 #현재가의 1%위의 가격으로 지정가 매수.. (그럼 1% 위 가격보다 작은 가격의 호가들은 모두 체결되기에 제한있는 시장가 매수 효과)
                    pprint.pprint(KisKR.MakeBuyLimitOrder(stock_code,abs(rebalance_amt),CurrentPrice))
                    '''


                
            line_alert.SendMessage(PortfolioName + "  리밸런싱 완료!!")
            print("------------------리밸런싱 끝---------------------")
        else:
            print("코드 맨 첫 부분에 ENABLE_ORDER_EXECUTION 값을 True로 변경해야 매수매도가 진행됩니다!")
