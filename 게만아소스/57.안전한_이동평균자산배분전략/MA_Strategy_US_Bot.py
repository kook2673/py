# -*- coding: utf-8 -*-
'''


$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

해당 컨텐츠는 제가 직접 투자 하기 위해 이 전략을 추가 개선해서 더 좋은 성과를 보여주는 개인 전략이 존재합니다. 

해당 전략 추가 개선한 버전 안내
https://blog.naver.com/zacra/223577385295

게만아 추가 개선 개인 전략들..
https://blog.naver.com/zacra/223196497504


관심 있으신 분은 위 포스팅을 참고하세요!

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$




관련 포스팅
https://blog.naver.com/zacra/223559959653

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
import KIS_API_Helper_US as KisUS

import pprint

import line_alert


#계좌 선택.. "VIRTUAL" 는 모의 계좌!
Common.SetChangeMode("VIRTUAL") #REAL or VIRTUAL


#포트폴리오 이름
PortfolioName = "이동평균자산배분전략_US"


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

InvestStockList = list() #투자할 종목을 직접 판단하여 아래 예시처럼 넣으세요!
#InvestStockList.append({"stock_code":"QQQ", "small_ma":3 , "big_ma":132, "invest_rate":0.5}) 
#InvestStockList.append({"stock_code":"TLT", "small_ma":13 , "big_ma":53, "invest_rate":0.25}) 
#InvestStockList.append({"stock_code":"GLD", "small_ma":17 , "big_ma":78, "invest_rate":0.25}) 
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





#마켓이 열렸는지 여부~!
IsMarketOpen = KisUS.IsMarketOpen()


#계좌 잔고를 가지고 온다!
Balance = KisUS.GetBalance()


print("--------------내 보유 잔고---------------------")

pprint.pprint(Balance)



#기준이 되는 내 총 평가금액에서 투자비중을 곱해서 나온 포트폴리오에 할당된 돈!!
TotalMoney = float(Balance['TotalMoney']) * InvestRate

print("총 포트폴리오에 할당된 투자 가능 금액 : ", TotalMoney)


##########################################################



##########################################################

print("--------------내 보유 주식---------------------")
#그리고 현재 이 계좌에서 보유한 주식 리스트를 가지고 옵니다!
MyStockList = KisUS.GetMyStockList()
#pprint.pprint(MyStockList)
print("--------------------------------------------")
##########################################################



if ENABLE_ORDER_EXECUTION == True:
    
    
    for stock_info in InvestStockList:
        
        stock_code = stock_info['stock_code']
        
        small_ma = stock_info['small_ma']
        big_ma = stock_info['big_ma']
        
        stock_target_rate = stock_info['invest_rate']
        


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


        
        
        df = Common.GetOhlcv("US", stock_code,250)

        df['prevOpen'] = df['open'].shift(1)
        df['prevClose'] = df['close'].shift(1)
        
        ############# 이동평균선! ###############

        df[str(small_ma) + 'ma'] = df['close'].rolling(small_ma).mean()
        df[str(big_ma)+ 'ma'] = df['close'].rolling(big_ma).mean()
            
        ########################################

        df.dropna(inplace=True) #데이터 없는건 날린다!
        
        
        print("---stock_code---", stock_code , " len ",len(df))
        #pprint.pprint(df)
        
        #보유중이 아니다
        if stock_amt == 0:
            
            msg = stock_name + "("+stock_code + ") 현재 매수하지 않고 현금 보유 상태! 목표할당비중:" + str(stock_target_rate*100) + "%"
            print(msg) 
            
            if df[str(small_ma) + 'ma'].iloc[-2] > df[str(big_ma) + 'ma'].iloc[-2] and df[str(small_ma) + 'ma'].iloc[-3] < df[str(small_ma) + 'ma'].iloc[-2]:
                print("비중 만큼 매수!!")
                if IsMarketOpen == True:
                    
                    msg = stock_name + "("+stock_code + ") 상승추세가 확인되었는데 보유수량이 없어 비중만큼 매수!!!!"
                    print(msg) 
                    line_alert.SendMessage(msg)
                                        
                    BuyMoney = TotalMoney * stock_target_rate

                    CurrentPrice = KisUS.GetCurrentPrice(stock_code)
                    #매수할 수량을 계산한다!
                    BuyAmt = int(BuyMoney / CurrentPrice)
                    
                    CurrentPrice *= 1.01 #현재가의 1%위의 가격으로 지정가 매수.. (그럼 1% 위 가격보다 작은 가격의 호가들은 모두 체결되기에 제한있는 시장가 매수 효과)
                    pprint.pprint(KisUS.MakeBuyLimitOrder(stock_code,BuyAmt,CurrentPrice))
                    
                    
                    
                    
        #보유중이다
        else:
            
            
            msg = stock_name + "("+stock_code + ") 현재 매수하여 보유 상태! 목표할당비중:" + str(stock_target_rate*100) + "%"
            print(msg) 
            
            if df[str(small_ma) + 'ma'].iloc[-2] < df[str(big_ma) + 'ma'].iloc[-2] and df[str(small_ma) + 'ma'].iloc[-3] > df[str(small_ma) + 'ma'].iloc[-2]:
                print("보유 수량 만큼 매도!!")
                if IsMarketOpen == True:
                    
                    msg = stock_name + "("+stock_code + ") 하락세가 확인되었는데 보유수량이 있어 매도!!!!"
                    print(msg) 
                    line_alert.SendMessage(msg)


                    CurrentPrice = KisUS.GetCurrentPrice(stock_code)
                    CurrentPrice *= 0.99 #현재가의 1%아래의 가격으로 지정가 매도.. (그럼 1%아래 가격보다 큰 가격의 호가들은 모두 체결되기에 제한있는 시장가 매도 효과)
                    pprint.pprint(KisUS.MakeSellLimitOrder(stock_code,abs(stock_amt),CurrentPrice))
                    
                    
else:
    print("코드 맨 첫 부분에 ENABLE_ORDER_EXECUTION 값을 True로 변경해야 매수매도가 진행됩니다!")