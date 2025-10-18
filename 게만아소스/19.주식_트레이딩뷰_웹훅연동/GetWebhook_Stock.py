'''

관련 포스팅

트레이딩뷰 웹훅 알림 받아 주식 자동매매 봇 완성하기 
https://blog.naver.com/zacra/223050088124

위 포스팅을 꼭 참고하세요!!!

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제공된 전략은 학습 및 테스트 목적으로 구성된 예시 코드이며
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.
   

주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!

'''
import line_alert
import json
import sys

import KIS_Common as Common
import KIS_API_Helper_KR as KisKR
import KIS_API_Helper_US as KisUS


#######################################################################
#######################################################################

# https://youtu.be/GmR4-AiJjPE 여기를 참고하세요 트레이딩뷰 웹훅 관련 코드입니다!

#######################################################################
#######################################################################

data = json.loads(sys.argv[1])

print(data)


line_alert.SendMessage("Data GET!: " + str(data) + "\n Logic Start!!")

# account -> 'VIRTUAL' or 'REAL' or .....등의 계좌명
# area -> 'US' or 'KR' 어떤 지역인지
# stock_code -> "SPY" ,"005930" 등의 종목코드
# type -> "limit" 지정가매매, "market" 시장가매매
# side -> "buy"는 매수, "sell"은 매도
# price -> 지정가 매매"limit"의 경우에 진입가격
# amt -> 매수/매도할 수량


#{"account":"VIRTUAL","area":"US","stock_code":"SPY","type":"limit","side":"sell","price":370.0,"amt":1}

Common.SetChangeMode(data['account']) #계좌 세팅!

#한국일 경우!
if data['area'] == "KR":
    print("KR")

    if data['type'] == "market":

        if data['side'] == "buy":
            KisKR.MakeBuyMarketOrder(data['stock_code'],data['amt'])

        elif data['side'] == "sell":
            KisKR.MakeSellMarketOrder(data['stock_code'],data['amt'])

    elif data['type'] == "limit":
        
        if data['side'] == "buy":
            KisKR.MakeBuyLimitOrder(data['stock_code'],data['amt'],data['price'])

        elif data['side'] == "sell":

            KisKR.MakeSellLimitOrder(data['stock_code'],data['amt'],data['price'])


#US 즉 미국일 경우
else:
    print("US")

    if data['type'] == "market":

        #현재가!
        CurrentPrice = KisUS.GetCurrentPrice(data['stock_code'])

        if data['side'] == "buy":

            #현재가보다 위에 매수 주문을 넣음으로써 시장가로 매수
            CurrentPrice *= 1.01
            KisUS.MakeBuyLimitOrder(data['stock_code'],data['amt'],CurrentPrice)


        elif data['side'] == "sell":

            #현재가보다 아래에 매도 주문을 넣음으로써 시장가로 매도
            CurrentPrice *= 0.99
            KisUS.MakeSellLimitOrder(data['stock_code'],data['amt'],CurrentPrice)

    elif data['type'] == "limit":

        if data['side'] == "buy":
            KisUS.MakeBuyLimitOrder(data['stock_code'],data['amt'],data['price'])

        elif data['side'] == "sell":

            KisUS.MakeSellLimitOrder(data['stock_code'],data['amt'],data['price'])



line_alert.SendMessage("Logic Done!!")







