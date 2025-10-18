
#-*-coding:utf-8 -*-
'''

관련 포스팅 
https://blog.naver.com/zacra/223508324003

위 포스팅을 꼭 참고하세요!!!

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.

주식/코인 파이썬 매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!



##############################################################
코인원 앱 -> 하단 더보기 -> 이벤트 코드 -> 등록하기 -> ZABOBSTUDIO 
##############################################################


'''
import myCoinone
import pprint


print("모든 코인 티커 가져오기 ")
tickers = myCoinone.GetTickers()
print(tickers)
print("###################################################################")
print("###################################################################")
print("###################################################################\n\n")

print("잔고 가져오기 ")
balances = myCoinone.GetBalances()

won = myCoinone.GetCoinAmount(balances,"KRW")

print(">>>>" , won ," <<<")


pprint.pprint(balances)
print("###################################################################")
print("###################################################################")
print("###################################################################\n\n")

print("금액 확인 ")
print("GetTotalMoney: ",myCoinone.GetTotalMoney(balances))
print("GetTotalRealMoney: ",myCoinone.GetTotalRealMoney(balances))
print("GetHasCoinCnt ", myCoinone.GetHasCoinCnt(balances))

print("###################################################################")
print("###################################################################")
print("###################################################################\n\n")

print("보유 중인 코인 데이터 체크!")
for ticker in tickers:
    if myCoinone.IsHasCoin(balances,ticker):
        print("has coin!", ticker)
        print("GetAvgBuyPrice: ",myCoinone.GetAvgBuyPrice(balances,ticker))
        print("GetCurrentPrice: ",myCoinone.GetCurrentPrice(ticker))

        print("GetCoinNowMoney ", myCoinone.GetCoinNowMoney(balances,ticker))
        print("GetCoinNowRealMoney ", myCoinone.GetCoinNowRealMoney(balances,ticker))
        print("GetRevenueRate: ",myCoinone.GetRevenueRate(balances,ticker))

        pprint.pprint(myCoinone.GetRevenueMoneyAndRate(balances,ticker))
        print("\n")
        

#'''
print("###################################################################")
print("###################################################################")
print("###################################################################")
print("일봉 정보 가져오기 예시")
df = myCoinone.GetOhlcv("BTC",'1d',1000)
pprint.pprint(df)
print("###################################################################")
print("###################################################################")
print("###################################################################\n\n")
#'''

'''       
print("시장가 주문 예시") 
balances = myCoinone.BuyCoinMarket("ETH",10000)

amount = myCoinone.GetCoinAmount(balances,"ETH")
print("amount ", amount)

balances = myCoinone.SellCoinMarket("ETH",amount/2.0)
'''

'''
print("지정가 주문 예시") 
amount = myCoinone.GetCoinAmount(balances,"ETH")
print("amount ", amount)

target_price =float(myCoinone.GetCurrentPrice("ETH")) * 0.95
myCoinone.BuyCoinLimit("ETH",target_price,amount)

time.sleep(0.2)
target_price =float(myCoinone.GetCurrentPrice("ETH")) * 1.05
myCoinone.SellCoinLimit("ETH",target_price,amount)
'''

'''
print("주문 정보 예시") 
pprint.pprint(myCoinone.GetActiveOrders("ETH"))
print("---------------\n")
pprint.pprint(myCoinone.CancelCoinOrder("ETH"))
print("---------------\n")
pprint.pprint(myCoinone.GetActiveOrders("ETH"))

'''
