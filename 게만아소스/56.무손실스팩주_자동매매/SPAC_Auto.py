# -*- coding: utf-8 -*-
'''

관련 포스팅
https://blog.naver.com/zacra/223548787076

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
  3. 매수할 조건을 명시
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
import json
import pprint
import line_alert


Common.SetChangeMode("VIRTUAL")

    


BOT_NAME = Common.GetNowDist() + "_SPAC_AutoBot"


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

#지정가 주문 상단 공모가 + 몇%까지
#저는 예시로 3%로 설정!!!!
LimitMaxRate = 3

#지정가 주문 하단 공모가 - 몇%까지의 매수를 허용할 것인지
#저는 예시로 -1%로 설정!!!! 뺄쌤이니 양수로 설정.
LimitMinRate = 1

#공시 전 절반의 수량을 파는 기준이 되는 수익률!!!
BeforeTargetRate = 15

#최대 몇개의 스팩주에 분산투자할 것인지
Max_SPAC_Count = 10
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


        
        
#투자하는 스팩주 데이터를 관리할 리스트
InvestSPAC_DataList = list()
#파일 경로입니다.
data_file_path = "/var/autobot/KrStock_" + BOT_NAME + ".json"

try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(data_file_path, 'r') as json_file:
        InvestSPAC_DataList = json.load(json_file)

except Exception as e:
    print("Exception by First")
    
    
            
        
        

#스팩주를 모아놓은 티커 리스트!!
file_path = "/var/autobot/SPAC_TickerList.json"

Spck_Ticker_List = list()

try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(file_path, 'r') as json_file:
        Spck_Ticker_List = json.load(json_file)

except Exception as e:
    print("Exception by First")


print("\n현재 상장된 스팩주 개수: ",len(Spck_Ticker_List))
print(Spck_Ticker_List)




#계좌 잔고를 가지고 온다!
Balance = KisKR.GetBalance()

print("--------------내 보유 잔고---------------------")

pprint.pprint(Balance)

print("--------------------------------------------")

#기준이 되는 내 총 평가금액에서 투자비중을 곱해서 나온 포트폴리오에 할당된 돈!! 
TotalMoney = float(Balance['TotalMoney']) * InvestRate

print("총 포트폴리오에 할당된 투자 가능 금액 : ", TotalMoney)


SPAC_InvestMoney = TotalMoney / Max_SPAC_Count
print("각 스팩주에 할당된 금액 : ", SPAC_InvestMoney)

SPAC_InvestMoney_Cell = SPAC_InvestMoney / 3
print("3분할 한 가격 : ", SPAC_InvestMoney_Cell)


NowSpacCnt = len(InvestSPAC_DataList) #현재 보유 관리중인 스팩주 수!
OrderCnt = 0 #오늘 주문 넣은 카운팅

print("--------------내 보유 주식---------------------")
#그리고 현재 이 계좌에서 보유한 주식 리스트를 가지고 옵니다!
MyStockList = KisKR.GetMyStockList()
#pprint.pprint(MyStockList)
print("--------------------------------------------")
    
#마켓이 열렸는지 여부~!
IsMarketOpen = KisKR.IsMarketOpen()

#혹시 있을지 모르는 중복 제거
Spck_Ticker_List = list(set(Spck_Ticker_List))

for stock_code in Spck_Ticker_List:
    df = Common.GetOhlcv("KR",stock_code, 800) 

    #현재가
    CurrentPrice = KisKR.GetCurrentPrice(stock_code)
    
    #stock_name = stock.get_market_ticker_name(stock_code)
    stock_name = KisKR.GetStockName(stock_code)
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
        #체결된 수량이 있다면 스팩주를 매수했다는 이야기니깐 이를 기록할 필요가 있다!

        #종목 데이터
        SPAC_DataInfo = None

        #저장된 종목 데이터를 찾는다
        for SPACDataInfo in InvestSPAC_DataList:
            if SPACDataInfo['StockCode'] == stock_code:
                SPAC_DataInfo = SPACDataInfo
                break

        #SPAC_DataInfo 이게 없다면 새로 기록!
        if SPAC_DataInfo == None:

            SpacDataDict = dict()
            
            SpacDataDict['StockCode'] = stock_code #종목 코드
            SpacDataDict['StockName'] = stock_name #종목 이름
            SpacDataDict['IsFull'] = False #모두 풀매수 했는지 여부
            SpacDataDict['IsHalfDone'] = False #합병공시 거래정지 전 절반 매도를 했는지 여부
            SpacDataDict['IsStop'] = False #합병공시 거래정지 여부..
            SpacDataDict['IsStopAfter'] = False #합병공시 거래정지 후 다시 거래 재개가 되었는지 여부


            InvestSPAC_DataList.append(SpacDataDict) #데이터를 추가 한다!


            msg = stock_name + "(" +stock_code + ") 투자중!!..."
            print(msg) 
            line_alert.SendMessage(msg) 


            #파일에 저장
            with open(data_file_path, 'w') as outfile:
                json.dump(InvestSPAC_DataList, outfile)
                
                
                
                
                
                
                
    items_to_remove = list()
    IsAlreadyHas = False
    
    #보유중인 스팩주를 처리한다!
    for SpacDataDict in InvestSPAC_DataList:
        
        if SpacDataDict['StockCode'] == stock_code:
            
            
            if stock_amt == 0:
                msg = stock_name + "(" +stock_code + ") 모두 매도되었어요! 투자 종료 처리!!!"
                print(msg) 
                line_alert.SendMessage(msg) 
                
                #모두 매도시 리스트에서 제거하는 로직 추가!
                items_to_remove.append(SpacDataDict)
                
            else:
                
                IsAlreadyHas = True
                print("현재 보유중인 스팩주들!!!")
                
                #전일 거래량이 0이라면..
                if df['volume'].iloc[-2] == 0 and df['open'].iloc[-2] == 0:
                    print("전일 기준 거래중지!.")
                
                    #아직 거래중지 전이 아니라면..
                    if SpacDataDict['IsStop'] == False:
                                
                        msg = stock_name + "(" +stock_code + ") 거래중지가 확인되었어요! 아마 합병공시가 난듯요? 가격이.." + str(CurrentPrice)
                        print(msg) 
                        line_alert.SendMessage(msg) 
                        
                        SpacDataDict['IsStop'] = True
                        
                                        
                        #파일에 저장
                        with open(data_file_path, 'w') as outfile:
                            json.dump(InvestSPAC_DataList, outfile)
                        
                
                else:
                    if SpacDataDict['IsStop'] == True:
                        #전일 거래량이 있다면 거래재개!
                        if SpacDataDict['IsStopAfter'] == False:
                                    
                            msg = stock_name + "(" +stock_code + ") 거래재개가 확인되었어요! 가격이.." + str(CurrentPrice)
                            print(msg) 
                            line_alert.SendMessage(msg) 
                            
                            SpacDataDict['IsStopAfter'] = True
                    
                                                
                            #파일에 저장
                            with open(data_file_path, 'w') as outfile:
                                json.dump(InvestSPAC_DataList, outfile)
                            
                
                
                #아직 풀 매수 상태가 아니라면 추가 주문을 넣는다.
                if SpacDataDict['IsFull'] == False:
                    
                    Target1Price = int(2000 * (1.0 + (float(LimitMaxRate)*0.01)))
                    Target2Price = 2000
                    Target3Price = int(2000 * (1.0 - (float(LimitMinRate)*0.01)))
            
                    InvestRate =  round((stock_avg_price * stock_amt) / SPAC_InvestMoney,2)
                    
                    print("현재 목표비중 대비 달성 비중 : " , InvestRate * 100, "%")
                    
                    
                    if 0.9 <= InvestRate:

                        msg = stock_name + "(" +stock_code + ") 3개의 지정가 주문 모두 체결된 것으로 판단되요!"
                        print(msg) 
                        line_alert.SendMessage(msg) 
                        
                        SpacDataDict['IsFull'] = True
                        #파일에 저장
                        with open(data_file_path, 'w') as outfile:
                            json.dump(InvestSPAC_DataList, outfile)
                                
                    elif 0.5 <= InvestRate:
                        print("2개의 지정가 주문이 체결된 것으로 판단되요!")
                        
                        if IsMarketOpen == True:
                            

                            msg = stock_name + "(" +stock_code + ") 장이 열려서 지정가 주문 1개를 넣어 둡니다!!"
                            print(msg) 
                            line_alert.SendMessage(msg) 
                            
                            
                            #투자금을 현재가로 나눠서 매수 가능한 수량을 정한다.
                            BuyAmt = int(SPAC_InvestMoney_Cell / Target3Price)
                            #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                            if BuyAmt < 1:
                                BuyAmt = 1
                            pprint.pprint(KisKR.MakeBuyLimitOrder(stock_code,BuyAmt,Target3Price))
                                        
                    else:
                        print("1개의 지정가 주문이 체결된 것으로 판단되요! 지정가 주문 2개를 넣어둡니다.")
                        
                        if IsMarketOpen == True:
                            

                            msg = stock_name + "(" +stock_code + ") 장이 열려서 지정가 주문 2개를 넣어 둡니다!!"
                            print(msg) 
                            line_alert.SendMessage(msg) 
                            
                            
                            #투자금을 현재가로 나눠서 매수 가능한 수량을 정한다.
                            BuyAmt = int(SPAC_InvestMoney_Cell / Target2Price)
                            #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                            if BuyAmt < 1:
                                BuyAmt = 1
                            pprint.pprint(KisKR.MakeBuyLimitOrder(stock_code,BuyAmt,Target2Price))
                            
                            
                            #투자금을 현재가로 나눠서 매수 가능한 수량을 정한다.
                            BuyAmt = int(SPAC_InvestMoney_Cell / Target3Price)
                            #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                            if BuyAmt < 1:
                                BuyAmt = 1
                            pprint.pprint(KisKR.MakeBuyLimitOrder(stock_code,BuyAmt,Target3Price))
                    
                   
                   
                   
                   
                #거래 정지 전이라면..    
                if SpacDataDict['IsStop'] == False and SpacDataDict['IsHalfDone'] == False:
                    
                    #수익률이 15%이상이라면 보유 수량 절반을 매도처리 한다!!
                    if stock_revenue_rate >= BeforeTargetRate:
                        
                        if IsMarketOpen == True:
                        
                            SellAmt = int(stock_amt / 2)
                            pprint.pprint(KisKR.MakeSellLimitOrder(stock_code,SellAmt,CurrentPrice*0.99))
                            
                            msg = stock_name + "(" +stock_code + ") 수익이 많이 나서 절반 매도 했어요! 수익률:" + str(stock_revenue_rate)
                            print(msg) 
                            line_alert.SendMessage(msg) 
                            
                            SpacDataDict['IsHalfDone'] = True
                            
                            #파일에 저장
                            with open(data_file_path, 'w') as outfile:
                                json.dump(InvestSPAC_DataList, outfile)
                                
                            
                #공시 후 거래재개 상태라면..
                if SpacDataDict['IsStopAfter'] == True:
                    
                    if IsMarketOpen == True:
                        
                        #전전일 저가보다 전일 저가가 낮았다면
                        if df['low'].iloc[-3] > df['low'].iloc[-2]:
                        
                            if stock_revenue_rate >= 5.0:
                                
                                pprint.pprint(KisKR.MakeSellLimitOrder(stock_code,stock_amt,CurrentPrice*0.99))
                                
                                msg = stock_name + "(" +stock_code + ") 수익이 난 상태라 모두 매도 주문을 넣었어요! 수익률:" + str(stock_revenue_rate) + "\n다음날 모두 매도 되었는지 확인해 봐요!"
                                print(msg) 
                                line_alert.SendMessage(msg) 
                                
                            else:
                                msg = stock_name + "(" +stock_code + ") 전일 저가를 갱신했는데 수익률이 낮은편이에요! 수익률:" + str(stock_revenue_rate) + "\n따라서 자동매도 하지 않았어요! 직접 확인하고 매도하거나 [주식매수청구권]행사를 고려해보세요!"
                                print(msg) 
                                line_alert.SendMessage(msg) 
                                
            break
            
            
    
    if len(items_to_remove) > 0:
            
        #리스트에서 제거
        for item in items_to_remove:
            InvestSPAC_DataList.remove(item)
            
        #파일에 저장
        with open(data_file_path, 'w') as outfile:
            json.dump(InvestSPAC_DataList, outfile)
        
            
        
        
        
        
    if len(InvestSPAC_DataList) < Max_SPAC_Count and IsAlreadyHas == False:
        print("신규 매수할 스팩주인지 체크합니다!")

        if (df['volume'] == 0).any() and (df['open'] == 0).any():
            print(stock_name ,"(",stock_code,") -> 거래정지 이력이 있습니다!! (매매 대상 제외)")
        else:
            if len(df) < 10: #10거래일 미만 제외
                print(stock_name ,"(",stock_code,") -> 상장 된지 얼마 안된 스팩주 (매매 대상 제외)")
            elif len(df) > 500: #500거래일 초과 제외
                print(stock_name ,"(",stock_code,") -> 상장 된지 너무 오래된 스팩주 상폐되도 본전 찾을 여지는 있지만 기분 나쁘니...(매매 대상 제외)")
            else:
                print(stock_name ,"(",stock_code,") -> 매매 대상!")

                
                if df['close'][-1] <= int(2000 * (1.0 + (float(LimitMaxRate+2)*0.01))):
                    print("########################################################################################################")
                    print("$$->",stock_name ,"(",stock_code,") -> 공모가 2000+",LimitMaxRate+2,"% 언더에 가격이 형성된 종목입니다! 현재가,",df['close'][-1])
                    
                    Target1Price = int(2000 * (1.0 + (float(LimitMaxRate)*0.01)))
                    Target2Price = 2000
                    Target3Price = int(2000 * (1.0 - (float(LimitMinRate)*0.01)))
                    
                    if stock_amt == 0:
                        print("아직 체결된 수량이 없는 상태예요")
                        if IsMarketOpen == True:
                            
                            msg = "현재매수개수(NowSpacCnt) : " + str(NowSpacCnt) + " 매수하기 위해 주문 들어간 종목개수(OrderCnt) : " + str(OrderCnt) + " < Max_SPAC_Count(최대 보유할 종목 개수) : " + str(Max_SPAC_Count)
                            print(msg)
                            #line_alert.SendMessage(msg)
                            
                            #현재 보유중인 스팩주와 지금 주문시도하는 수의 합이 맥스값을 넘지 않게!
                            if NowSpacCnt + OrderCnt < Max_SPAC_Count:
                                
                                OrderCnt += 1 #오늘 주문 넣은 카운팅!

                                msg = stock_name + "(" +stock_code + ") 장이 열려서 지정가 주문 3개를 넣어 둡니다!!"
                                print(msg) 
                                line_alert.SendMessage(msg) 
                                
                                #투자금을 현재가로 나눠서 매수 가능한 수량을 정한다.
                                BuyAmt = int(SPAC_InvestMoney_Cell / Target1Price)
                                #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                                if BuyAmt < 1:
                                    BuyAmt = 1
                                pprint.pprint(KisKR.MakeBuyLimitOrder(stock_code,BuyAmt,Target1Price))
                                
                                
                                #투자금을 현재가로 나눠서 매수 가능한 수량을 정한다.
                                BuyAmt = int(SPAC_InvestMoney_Cell / Target2Price)
                                #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                                if BuyAmt < 1:
                                    BuyAmt = 1
                                pprint.pprint(KisKR.MakeBuyLimitOrder(stock_code,BuyAmt,Target2Price))
                                
                                
                                #투자금을 현재가로 나눠서 매수 가능한 수량을 정한다.
                                BuyAmt = int(SPAC_InvestMoney_Cell / Target3Price)
                                #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                                if BuyAmt < 1:
                                    BuyAmt = 1
                                pprint.pprint(KisKR.MakeBuyLimitOrder(stock_code,BuyAmt,Target3Price))
                                
                                
                    
                            
                    print("########################################################################################################")    
                    
                else:
                    print("->",stock_name ,"(",stock_code,") -> 공모가 2000+",LimitMaxRate+2,"% 이상의 가격이라 당장 매수는 힘들겠지만...언젠가... 현재가,",df['close'][-1])
                    
                
                
