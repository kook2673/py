'''
-*- 백테스팅 코드가 있는 전략들은 패키지 16번 부터 나오기 시작하니 참고하세요!! -*-

관련 포스팅

주식 양방향 매매 최종본! 바로 이거다! 이평무한매수전략(수익 인증)을 헷지(헤지) 모드로 접근하기!
https://blog.naver.com/zacra/223005881442

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
import json
import pprint
import line_alert
import time

Common.SetChangeMode("VIRTUAL")


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
📌 투자할 종목은 본인의 선택으로 아래 같은 형식으로 추가하세요!
'''
#투자할 종목! KODEX 레버리지 
TargetStockList = ['']
#TargetStockList = ['122630'] #예시

InverseShortCode = dict()
InverseShortCode[''] = '' # [롱] = 숏
#InverseShortCode['122630'] = '252670' #예시..


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

#########################-트레일링스탑 적용-#######################
TraillingStopRate = 0.01 #1%기준으로 트레일링 스탑!


#시간 정보를 읽는다
time_info = time.gmtime()

#혹시 이 봇을 장 시작하자 마자 돌린다면 20초르 쉬어준다.
#그 이유는 20초는 지나야 오늘의 일봉 정보를 제대로 가져오는데
#tm_hour가 0은 9시, 1은 10시를 뜻한다. 수능 등 10시에 장 시작하는 경우르 대비!
if time_info.tm_hour in [0,1] and time_info.tm_min == 0:
    time.sleep(20.0)
    

BOT_NAME = Common.GetNowDist() + "_InfinityHedgeBot"


#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#
############# 해당 전략으로 매수한 종목 데이터 리스트 ####################
InfinityMaDataList = list()
#파일 경로입니다.
bot_file_path = "/var/autobot/KrStock_" + BOT_NAME + ".json"

try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(bot_file_path, 'r') as json_file:
        InfinityMaDataList = json.load(json_file)

except Exception as e:
    print("Exception by First")
################################################################
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#


#계좌 잔고를 가지고 온다!
Balance = KisKR.GetBalance()
#####################################################################################################################################




print("--------------내 보유 잔고---------------------")

pprint.pprint(Balance)

print("--------------------------------------------")

#기준이 되는 내 총 평가금액에서 투자비중을 곱해서 나온 포트폴리오에 할당된 돈!!
TotalMoney = float(Balance['TotalMoney']) * InvestRate

#각 종목당 투자할 금액! 리스트의 종목 개수로 나눈다!
StockMoney = TotalMoney / len(TargetStockList)
print("TotalMoney:", str(format(round(TotalMoney), ',')))
print("StockMoney:", str(format(round(StockMoney), ',')))

#분할된 투자금!
StMoney = StockMoney / 60.0

print("StMoney:", str(format(round(StMoney), ',')))





print("--------------내 보유 주식---------------------")
#그리고 현재 이 계좌에서 보유한 주식 리스트를 가지고 옵니다!
MyStockList = KisKR.GetMyStockList()
pprint.pprint(MyStockList)
print("--------------------------------------------")
    

if ENABLE_ORDER_EXECUTION == True:

    #마켓이 열렸는지 여부~!
    IsMarketOpen = KisKR.IsMarketOpen()

    #장이 열렸을 때!
    if IsMarketOpen == True:


        #투자할 종목을 순회한다!
        for stock_code in TargetStockList:


            #주식(ETF) 정보~
            stock_name = ""
            stock_amt = 0 #수량
            stock_avg_price = 0 #평단
            stock_eval_totalmoney = 0 #총평가금액!
            stock_revenue_rate = 0 #종목 수익률
            stock_revenue_money = 0 #종목 수익금


            #매수된 상태라면 정보를 넣어준다!!!
            for my_stock in MyStockList:
                if my_stock['StockCode'] == stock_code:
                    stock_name = my_stock['StockName']
                    stock_amt = int(my_stock['StockAmt'])
                    stock_avg_price = float(my_stock['StockAvgPrice'])
                    stock_eval_totalmoney = float(my_stock['StockNowMoney'])
                    stock_revenue_rate = float(my_stock['StockRevenueRate'])
                    stock_revenue_money = float(my_stock['StockRevenueMoney'])

                    break
                    
            if stock_amt > 0:
                #수수료 및 세금을 생각해서 손실금의 10% 증가 수익금의 10%감소 보정을 한다
                if stock_revenue_money < 0:
                    stock_revenue_money *= 1.1
                else:
                    stock_revenue_money *= 0.9
                
                
            #현재가
            CurrentPrice = KisKR.GetCurrentPrice(stock_code)


            ##########################################################                
            #인버스(숏)에 해당하는 종목 코드
            ShortCode = InverseShortCode[stock_code]
            
            #주식(ETF) 정보~
            Short_stock_amt = 0 #수량
            Short_stock_revenue_money = 0 #종목 수익금


            #매수된 상태라면 정보를 넣어준다!!!
            for my_stock in MyStockList:
                if my_stock['StockCode'] == ShortCode:
                    Short_stock_amt = int(my_stock['StockAmt'])
                    Short_stock_revenue_money = float(my_stock['StockRevenueMoney'])
                    break
                
            if Short_stock_amt > 0:
                #수수료 및 세금을 생각해서 손실금의 10% 증가 수익금의 10%감소 보정을 한다
                if Short_stock_revenue_money < 0:
                    Short_stock_revenue_money *= 1.1
                else:
                    Short_stock_revenue_money *= 0.9
                

            #현재가
            Short_CurrentPrice = KisKR.GetCurrentPrice(ShortCode)
            
            
            
            ##########################################################    
                

                
            #종목 데이터
            PickStockInfo = None

            #저장된 종목 데이터를 찾는다
            for StockInfo in InfinityMaDataList:
                if StockInfo['StockCode'] == stock_code:
                    PickStockInfo = StockInfo
                    break

            #PickStockInfo 이게 없다면 매수되지 않은 처음 상태이거나 이전에 손으로 매수한 종목인데 해당 봇으로 돌리고자 할 때!
            if PickStockInfo == None:
                #잔고가 없다 즉 처음이다!!!
                if stock_amt == 0:

                    InfinityDataDict = dict()
                    
                    InfinityDataDict['StockCode'] = stock_code #종목 코드
                    InfinityDataDict['Round'] = 0    #현재 회차
                    InfinityDataDict['IsReady'] = 'Y' #하루에 한번 체크하고 매수등의 처리를 하기 위한 플래그

                    InfinityDataDict['S_WaterAmt'] = 0 #물탄 수량!
                    InfinityDataDict['S_WaterLossMoney'] = 0 #물탄 수량을 팔때 손해본 금액
                    
                    InfinityDataDict['Inverse_S_WaterAmt'] = 0 #롱 물탈때 같이 탄 수량!

                    InfinityDataDict['TrallingPrice'] = 0 #트레일링 추적할 가격
                    InfinityDataDict['IsTralling'] = 'N' #트레일링 시작 여부

                    InfinityMaDataList.append(InfinityDataDict) #데이터를 추가 한다!


                    msg = KisKR.GetStockName(stock_code) + "("+ stock_code  + ")  이평무한매수봇 첫 시작!!!!"
                    print(msg) 
                    line_alert.SendMessage(msg) 
                    
                #데이터가 없는데 잔고가 있다? 이미 이 봇으로 트레이딩 하기전에 매수된 종목!
                else:
                    print("Exist")

                    InfinityDataDict = dict()
                    
                    InfinityDataDict['StockCode'] = stock_code #종목 코드
                    InfinityDataDict['Round'] = int(stock_eval_totalmoney / StMoney)    #현재 회차 - 매수된 금액을 50분할된 단위 금액으로 나누면 회차가 나온다!
                    InfinityDataDict['IsReady'] = 'Y' #하루에 한번 체크하고 매수등의 처리를 하기 위한 플래그

                    InfinityDataDict['S_WaterAmt'] = 0 #물탄 수량!
                    InfinityDataDict['S_WaterLossMoney'] = 0 #물탄 수량을 팔때 손해본 금액

                    
                    InfinityDataDict['Inverse_S_WaterAmt'] = 0 #롱 물탈때 같이 탄 수량!

                    
                    InfinityDataDict['TrallingPrice'] = 0 #트레일링 추적할 가격
                    InfinityDataDict['IsTralling'] = 'N' #트레일링 시작 여부

                    InfinityMaDataList.append(InfinityDataDict) #데이터를 추가 한다!


                    msg = KisKR.GetStockName(stock_code) + "("+ stock_code  + ")  기존에 매수한 종목을 이평무한매수봇으로 변경해서 트레이딩 첫 시작!!!! " + str(InfinityDataDict['Round']) + "회차로 세팅 완료!"
                    print(msg) 
                    line_alert.SendMessage(msg) 

                #파일에 저장
                with open(bot_file_path, 'w') as outfile:
                    json.dump(InfinityMaDataList, outfile)
                    




            #이제 데이터(InfinityMaDataList)는 확실히 있을 테니 본격적으로 트레이딩을 합니다!
            for StockInfo in InfinityMaDataList:

                if StockInfo['StockCode'] == stock_code:

                    #1회차 이상 매수된 상황이라면 익절 조건을 체크해서 익절 처리 해야 한다!
                    if StockInfo['Round'] > 0 and stock_amt >= 1:


                        #$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#
                        #########################-트레일링스탑 적용-#######################
                        #트레일링 스탑이 시작되었다면 이전에 저장된 값 대비 트레일링 스탑 비중만큼 떨어졌다면 스탑!
                        #아니라면 고점 갱신해줍니다!!
                        if StockInfo['IsTralling'] == 'Y':

                            #스탑할 가격을 구합니다.
                            StopPrice = StockInfo['TrallingPrice'] * (1.0 - TraillingStopRate)

                            #스탑할 가격보다 작아졌다면
                            if CurrentPrice <= StopPrice:

                                #현재가보다 아래에 매도 주문을 넣음으로써 시장가로 매도효과!
                                pprint.pprint(KisKR.MakeSellMarketOrder(stock_code,stock_amt))


                                msg = KisKR.GetStockName(stock_code) + "("+ stock_code  + ")  이평무한매수봇 모두 팔아서 수익확정!!!!  [" + str(stock_revenue_money) + "] 수익 조으다! (현재 [" + str(StockInfo['Round']) + "] 라운드까지 진행되었고 모든 수량 매도 처리! )"
                                print(msg) 
                                line_alert.SendMessage(msg) 

                                #전량 매도 모두 초기화! 
                                StockInfo['TrallingPrice'] = 0
                                StockInfo['IsTralling'] = 'N' 
                                StockInfo['Round'] = 0
                                StockInfo['IsReady'] = 'N' #익절한 날은 매수 안하고 즐기자!
                                StockInfo['S_WaterAmt'] = 0 #물탄 수량 초기화 
                                StockInfo['S_WaterLossMoney'] = 0 #물탄 수량을 팔때 손해본 금액 초기화!
                                StockInfo['Inverse_S_WaterAmt'] = 0



                            #현재가가 이전에 저장된 가격보다 높아졌다면 고점 갱신!!!
                            if StockInfo['TrallingPrice'] < CurrentPrice:

                                StockInfo['TrallingPrice'] = CurrentPrice

                            #파일에 저장
                            with open(bot_file_path, 'w') as outfile:
                                json.dump(InfinityMaDataList, outfile)

                        #트레일링 스탑 아직 시작 안됨!
                        else:

                            #목표 수익률을 구한다! 한국은 3배 레버는 없으니깐 목표수익을 낮춰준다 
                            '''
                            1회 :  5%
                            10회  4.5%
                            20회  4%
                            30회  3.5%
                            40회 : 3%
                            '''
                            TargetRate = (5.0 - StockInfo['Round']*0.05) / 100.0

                            #현재총평가금액은 물타기 손실금액을 반영한게 아니다.
                            #손실액이 현재 평가금액 대비 비중이 얼마인지 체크한다. 
                            PlusRate = StockInfo['S_WaterLossMoney'] / stock_eval_totalmoney
                            
                            #숏 손익/ 롱 평가금 대비 비중을 구한다. 
                            ShortRate = (Short_stock_revenue_money / stock_eval_totalmoney) * -1
                            

                            #그래서 목표수익률이랑 손실액을 커버하기 위한 수익률을 더해준다! + 트레일링 스탑 기준도 더해서 수익 확보!
                            FinalRate = TargetRate + PlusRate + TraillingStopRate + ShortRate

                            print("TargetRate:", TargetRate , "+ PlusRate:" ,PlusRate , "+ TraillingStopRate:", TraillingStopRate, "+ ShortRate:", ShortRate,"  -> FinalRate:" , FinalRate)
                            print("목표 수익률 : ", round(FinalRate*100.0,2) ,"% 현재 ",KisKR.GetStockName(stock_code)," 수익률 : " ,  stock_revenue_rate, "%")
                            #수익화할 가격을 구한다!
                            RevenuePrice = stock_avg_price * (1.0 + FinalRate) 

                            print("목표 가격 : ", round(RevenuePrice,2) ," 현재 가격 : ", round(CurrentPrice,2))
                            #목표한 수익가격보다 현재가가 높다면 익절처리할 순간이다!
                            if CurrentPrice >= RevenuePrice and (stock_revenue_money + Short_stock_revenue_money) > 0:

                                if Short_stock_amt >= 1:
                                    #현재가보다 아래에 매도 주문을 넣음으로써 시장가로 매도효과!
                                    pprint.pprint(KisKR.MakeSellMarketOrder(ShortCode,Short_stock_amt))

                                    msg = KisKR.GetStockName(ShortCode) + "("+ ShortCode  + ")  이평무한매수봇 숏 모두 정리!!!!  [" + str(Short_stock_revenue_money) + "] 손익 확정! )"
                                    print(msg) 
                                    line_alert.SendMessage(msg) 


                                if stock_amt == 1:
                                    
                                    #현재가보다 아래에 매도 주문을 넣음으로써 시장가로 매도효과!
                                    pprint.pprint(KisKR.MakeSellMarketOrder(stock_code,stock_amt))


                                    msg = KisKR.GetStockName(stock_code) + "("+ stock_code  + ")  이평무한매수봇 모두 팔아서 수익확정!!!!  [" + str(stock_revenue_money) + "] 수익 조으다! (현재 [" + str(StockInfo['Round']) + "] 라운드까지 진행되었고 모든 수량 매도 처리! )"
                                    print(msg) 
                                    line_alert.SendMessage(msg) 

                                    #전량 매도 모두 초기화! 
                                    StockInfo['TrallingPrice'] = 0
                                    StockInfo['IsTralling'] = 'N' 
                                    StockInfo['Round'] = 0
                                    StockInfo['IsReady'] = 'N' #익절한 날은 매수 안하고 즐기자!
                                    StockInfo['S_WaterAmt'] = 0 #물탄 수량 초기화 
                                    StockInfo['S_WaterLossMoney'] = 0 #물탄 수량을 팔때 손해본 금액 초기화!
                                    StockInfo['Inverse_S_WaterAmt'] = 0
                                        
                                else:
                                    
                                    #절반은 바로 팔고 절반은 트레일링 스탑으로 처리한다!!!
                                    HalfAmt = int(stock_amt * 0.5)

                                    #절반만 팝니다!!!!!
                                    pprint.pprint(KisKR.MakeSellMarketOrder(stock_code,HalfAmt))


                                    msg = KisKR.GetStockName(stock_code) + "("+ stock_code  + ")  이평무한매수봇 절반 팔아서 수익확정!!!!  [" + str(stock_revenue_money*0.5) + "] 수익 조으다! (현재 [" + str(StockInfo['Round']) + "] 라운드까지 진행되었고 절반 익절 후 트레일링 스탑 시작!!)"
                                    print(msg) 
                                    line_alert.SendMessage(msg) 

                                    StockInfo['TrallingPrice'] = CurrentPrice
                                    StockInfo['IsTralling'] = 'Y' #트레일링 스탑 시작!

                                #파일에 저장
                                with open(bot_file_path, 'w') as outfile:
                                    json.dump(InfinityMaDataList, outfile)



                    #매수는 장이 열렸을 때 1번만 해야 되니깐! 안의 로직을 다 수행하면 N으로 바꿔준다! 그리고 트레일링 스탑이 진행중이라면 추가매수하지 않는다!
                    if StockInfo['IsReady'] == 'Y' and StockInfo['IsTralling'] =='N':



                        #50분할된 투자금이 현재가격보다 작다면..투자금이 너무 작다!
                        if CurrentPrice > StMoney:

                            msg = KisKR.GetStockName(stock_code) + "("+ stock_code  + ")  현재 60분할된 투자금보다 현재가가 높아서 전략을 제대로 수행 못해요! 투자비중이나 자금을 늘리세요!"
                            print(msg)   
                            line_alert.SendMessage(msg) 



                        #캔들 데이터를 읽는다
                        df = Common.GetOhlcv("KR",stock_code, 50)

                        #5일 이평선
                        Ma5_before3 = Common.GetMA(df,5,-4)
                        Ma5_before = Common.GetMA(df,5,-3)
                        Ma5 = Common.GetMA(df,5,-2)

                        print("MA5",Ma5_before3, "->", Ma5_before, "-> ",Ma5)

                        #20일 이평선
                        Ma20_before = Common.GetMA(df,20,-3)
                        Ma20 = Common.GetMA(df,20,-2)

                        print("MA20", Ma20_before, "-> ",Ma20)

                        #양봉 캔들인지 여부
                        IsUpCandle = False

                        #시가보다 종가가 크다면 양봉이다
                        if df['open'].iloc[-2] <= df['close'].iloc[-2]:
                            IsUpCandle = True

                        print("IsUpCandle : ", IsUpCandle)




                                
                        #40회를 넘었다면! 풀매수 상태이다!
                        if StockInfo['Round'] >= 40:
                            #그런데 애시당초 후반부는 5일선이 증가추세일때만 매매 하므로 5일선이 하락으로 바뀌었다면 이때 손절처리를 한다
                            if Ma5_before > Ma5:
                                #절반을 손절처리 한다
    
                                #절반은 바로 팔고 절반은 트레일링 스탑으로 처리한다!!!
                                HalfAmt = int(stock_amt * 0.5)

                                #절반만 팝니다!!!!!
                                pprint.pprint(KisKR.MakeSellMarketOrder(stock_code,HalfAmt))

                                StockInfo['Round'] = 21 #라운드는 절반을 팔았으니깐 21회로 초기화

                                #단 현재 수익금이 마이너스 즉 손실 상태라면 손실 금액을 저장해 둔다!
                                if stock_revenue_money < 0:
                                    #손실 금액에서 매도수량/보유수량 즉 예로 10개보유 하고 현재 -100달러인데 5개를 파는 거라면 실제 확정 손실금은 -100 * (5/10)이 니깐~
                                    LossMoney = abs(stock_revenue_money) * (float(HalfAmt) / float(stock_amt))
                                    StockInfo['S_WaterLossMoney'] += LossMoney

                                    msg = KisKR.GetStockName(stock_code) + "("+ stock_code  + ")  40회가 소진되어 절반 손절합니다! 약 [" + str(LossMoney) + "] 확정손실이 나서 기록했으며 누적 손실은 [" + str(StockInfo['S_WaterLossMoney']) + "] 입니다"
                                    print(msg) 
                                    line_alert.SendMessage(msg) 

                                #이 경우는 이득 본 경우다! 목표 %에 못 도달했지만 수익권이긴 한 상태.
                                else:

                                    #이득본 금액도 계산해보자
                                    RevenuMoney = abs(stock_revenue_money) * (float(HalfAmt) / float(stock_amt))

                                    #혹시나 저장된 손실본 금액이 있다면 줄여 준다! (빠른 탈출을 위해)
                                    if StockInfo['S_WaterLossMoney'] > 0:
                                        StockInfo['S_WaterLossMoney'] -= RevenuMoney #저 데이터는 손실금을 저장하는 곳이니 빼준다



                                    msg = KisKR.GetStockName(stock_code) + "("+ stock_code  + ")  40회가 소진되어 절반 매도합니다! 약 [" + str(RevenuMoney) + "] 확정 수익이 났네요!"
                                    print(msg) 
                                    line_alert.SendMessage(msg) 


                        '''
                        
                        1~10회:

                        무조건 삽니다

                        11~20회 :

                        5일선 위에 있을 때만!

                        21~30회 :

                        5일선 위에 있고 이전봉이 양봉일때만

                        30~40회 :

                        5일선 위에 있고 이전봉이 양봉이고 
                        5일선 증가, 20일선이 증가했다!

                        '''

                        IsBuyGo = False #매수 하는지!

                        #라운드에 따라 매수 조건이 다르다!
                        if StockInfo['Round'] <= 10-1:

                            #여기는 무조건 매수
                            IsBuyGo = True

                        elif StockInfo['Round'] <= 20-1:

                            #현재가가 5일선 위에 있을 때만 매수
                            if Ma5 < CurrentPrice:
                                IsBuyGo = True

                        elif StockInfo['Round'] <= 30-1:

                            #현재가가 5일선 위에 있고 이전 봉이 양봉일 때만 매수
                            if Ma5 < CurrentPrice and IsUpCandle == True:
                                IsBuyGo = True

                        elif StockInfo['Round'] <= 40-1:

                            #현재가가 5일선 위에 있고 이전 봉이 양봉일때 그리고 5일선, 20일선 둘다 증가추세에 있을 때만 매수
                            if Ma5 < CurrentPrice and IsUpCandle == True and Ma5_before < Ma5 and Ma20_before < Ma20:
                                IsBuyGo = True



                        #한 회차 매수 한다!!
                        if IsBuyGo == True:

                            StockInfo['Round'] += 1 #라운드 증가!

                            BuyAmt = int(StMoney / CurrentPrice)
                            
                            #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                            if BuyAmt < 1:
                                BuyAmt = 1

                            #시장가 주문을 넣는다!
                            #현재가보다 위에 매수 주문을 넣음으로써 시장가로 매수!
                            pprint.pprint(KisKR.MakeBuyMarketOrder(stock_code,BuyAmt))


                            msg = KisKR.GetStockName(stock_code) + "("+ stock_code  + ")  이평무한매수봇 " + str(StockInfo['Round']) + "회차 매수 완료!"
                            print(msg) 
                            line_alert.SendMessage(msg) 



                        #위 로직 완료하면 N으로 바꿔서 오늘 매수는 안되게 처리!
                        StockInfo['IsReady'] = 'N' 

                        #파일에 저장
                        with open(bot_file_path, 'w') as outfile:
                            json.dump(InfinityMaDataList, outfile)
                            


                        ####################################################################################
                        ################## 위 정규 매수 로직과는 별개로 특별 물타기 로직을 체크하고 제어한다! #############

                        #이평선이 꺾여서 특별히 물탄 경우 수량이 0이 아닐꺼고 즉 여기는  물을 탄 상태이다!
                        if StockInfo['S_WaterAmt'] != 0:

                            #그렇다면 하루가 지났다는 이야기니깐 해당 수량 만큼 무조건 매도 한다!

                            #현재가보다 아래에 매도 주문을 넣음으로써 시장가로 매도효과!
                            pprint.pprint(KisKR.MakeSellMarketOrder(stock_code,StockInfo['S_WaterAmt']))

                            #단 현재 수익금이 마이너스 즉 손실 상태라면 손실 금액을 저장해 둔다!
                            if stock_revenue_money < 0:
                                #손실 금액에서 매도수량/보유수량 즉 예로 10개보유 하고 현재 -100달러인데 3개를 파는 거라면 실제 확정 손실금은 -100 * (3/10)이 니깐~
                                LossMoney = abs(stock_revenue_money) * (float(StockInfo['S_WaterAmt']) / float(stock_amt))
                                StockInfo['S_WaterLossMoney'] += LossMoney

                                msg = KisKR.GetStockName(stock_code) + "("+ stock_code  + ")  평단을 확 낮추기 위한 이평무한매수봇 물탄지 하루가 지나 그 수량만큼 매도합니다! 약 [" + str(LossMoney) + "] 확정손실이 나서 기록했으며 누적 손실은 [" + str(StockInfo['S_WaterLossMoney']) + "] 입니다"
                                print(msg) 
                                line_alert.SendMessage(msg) 

                            #이 경우는 이득 본 경우다!
                            else:

                                #이득본 금액도 계산해보자
                                RevenuMoney = abs(stock_revenue_money) * (float(StockInfo['S_WaterAmt']) / float(stock_amt))

                                #혹시나 저장된 손실본 금액이 있다면 줄여 준다! (빠른 탈출을 위해)
                                if StockInfo['S_WaterLossMoney'] > 0:
                                    StockInfo['S_WaterLossMoney'] -= RevenuMoney #저 데이터는 손실금을 저장하는 곳이니 빼준다



                                msg = KisKR.GetStockName(stock_code) + "("+ stock_code  + ")  평단을 확 낮추기 위한 이평무한매수봇 물탄지 하루가 지나 그 수량만큼 매도합니다! 약 [" + str(RevenuMoney) + "] 확정 수익이 났네요! 누적 손실은 [" + str(StockInfo['S_WaterLossMoney']) + "] 입니다"
                                print(msg) 
                                line_alert.SendMessage(msg) 

                            StockInfo['S_WaterAmt'] = 0 #팔았으니 0으로 초기화!
                            
                            
                            
                            ###########################################################################################
                            
                            #현재가보다 아래에 매도 주문을 넣음으로써 시장가로 매도효과!
                            pprint.pprint(KisKR.MakeSellMarketOrder(ShortCode,StockInfo['Inverse_S_WaterAmt']))

                            #단 현재 수익금이 마이너스 즉 손실 상태라면 손실 금액을 저장해 둔다!
                            if Short_stock_revenue_money < 0:
                                #손실 금액에서 매도수량/보유수량 즉 예로 10개보유 하고 현재 -100달러인데 3개를 파는 거라면 실제 확정 손실금은 -100 * (3/10)이 니깐~
                                LossMoney = abs(Short_stock_revenue_money) * (float(StockInfo['Inverse_S_WaterAmt']) / float(Short_stock_amt))
                                StockInfo['S_WaterLossMoney'] += LossMoney

                                msg = KisKR.GetStockName(ShortCode) + "("+ ShortCode  + ")  평단을 확 낮추기 위한 이평무한매수봇 물탄지 하루가 지나 인버스(숏) 수량만큼 매도합니다! 약 [" + str(LossMoney) + "] 확정손실이 나서 기록했으며 누적 손실은 [" + str(StockInfo['S_WaterLossMoney']) + "] 입니다"
                                print(msg) 
                                line_alert.SendMessage(msg) 

                            #이 경우는 이득 본 경우다!
                            else:

                                #이득본 금액도 계산해보자
                                RevenuMoney = abs(Short_stock_revenue_money) * (float(StockInfo['Inverse_S_WaterAmt']) / float(Short_stock_amt))

                                #혹시나 저장된 손실본 금액이 있다면 줄여 준다! (빠른 탈출을 위해)
                                if StockInfo['S_WaterLossMoney'] > 0:
                                    StockInfo['S_WaterLossMoney'] -= RevenuMoney #저 데이터는 손실금을 저장하는 곳이니 빼준다



                                msg = KisKR.GetStockName(ShortCode) + "("+ ShortCode  + ")  평단을 확 낮추기 위한 이평무한매수봇 물탄지 하루가 지나 인버스(숏) 수량만큼 매도합니다! 약 [" + str(RevenuMoney) + "] 확정 수익이 났네요! 누적 손실은 [" + str(StockInfo['S_WaterLossMoney']) + "] 입니다"
                                print(msg) 
                                line_alert.SendMessage(msg) 

                            StockInfo['Inverse_S_WaterAmt'] = 0 #팔았으니 0으로 초기화!
                            
                            
                            
                            ###########################################################################################

                            
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

                                BuyRound = int(StockInfo['Round']/4) + 1 #물탈 회수

                                BuyAmt = int((StMoney * BuyRound) / CurrentPrice) #물탈 수량을 구한다!
                                
                                if BuyAmt < 1:
                                    BuyAmt = 1


                                StockInfo['S_WaterAmt'] = BuyAmt

                                #시장가 주문을 넣는다!
                                pprint.pprint(KisKR.MakeBuyMarketOrder(stock_code,BuyAmt))

                                msg = KisKR.GetStockName(stock_code) + "("+ stock_code  + ")  이평선이 위로 꺾였어요! 평단을 확 낮추기 위한 이평무한매수봇 물을 탑니다!! [" + str(BuyRound) + "] 회차 만큼의 수량을 추가 했어요!"
                                print(msg) 
                                line_alert.SendMessage(msg) 



                                ###########################################################################################
                                ShortBuyAmt = int((StMoney * BuyRound) / Short_CurrentPrice) #물탈 수량을 구한다!
                                
                                if ShortBuyAmt < 1:
                                    ShortBuyAmt = 1


                                StockInfo['Inverse_S_WaterAmt'] = ShortBuyAmt

                                #시장가 주문을 넣는다!
                                pprint.pprint(KisKR.MakeBuyMarketOrder(ShortCode,ShortBuyAmt))


                                msg = stock_code + " 같은 물량기준으로 숏도 매수!!!"
                                print(msg) 
                                line_alert.SendMessage(msg) 
                                ###########################################################################################
                                
                                
                                
                        #########################################################################################
                        #########################################################################################

                        #파일에 저장
                        with open(bot_file_path, 'w') as outfile:
                            json.dump(InfinityMaDataList, outfile)
                            
                                

                    break


    else:

            
        #장이 끝나고 다음날 다시 매수시도 할수 있게 Y로 바꿔줍니당!
        for StockInfo in InfinityMaDataList:
            StockInfo['IsReady'] = 'Y' 


        #파일에 저장
        with open(bot_file_path, 'w') as outfile:
            json.dump(InfinityMaDataList, outfile)
            
            

            
    pprint.pprint(InfinityMaDataList)

else:
    print("코드 맨 첫 부분에 ENABLE_ORDER_EXECUTION 값을 True로 변경해야 매수매도가 진행됩니다!")
