'''


관련 포스팅
https://blog.naver.com/zacra/223744333599
https://blog.naver.com/zacra/223763707914

최종 개선
https://blog.naver.com/zacra/223773295093

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.

주식/코인 파이썬 매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!


'''
# -*- coding: utf-8 -*-
import pyupbit
import myUpbit
import time
import random
import json
import line_alert
import fcntl

import ende_key  #암복호화키
import my_key    #업비트 시크릿 액세스키

DIST = "업비트"

simpleEnDecrypt = myUpbit.SimpleEnDecrypt(ende_key.ende_key)

#암호화된 액세스키와 시크릿키를 읽어 복호화 한다.
Upbit_AccessKey = simpleEnDecrypt.decrypt(my_key.upbit_access)
Upbit_ScretKey = simpleEnDecrypt.decrypt(my_key.upbit_secret)

#업비트 객체를 만든다
upbit = pyupbit.Upbit(Upbit_AccessKey, Upbit_ScretKey)

#최소 금액 
minimumMoney = 5000


auto_order_file_path = "/var/autobot/Upbit_SplitTrader_AutoOrderList.json"
time.sleep(random.random()*0.1)

#자동 주문 리스트 읽기!
AutoOrderList = list()
try:
    with open(auto_order_file_path, 'r') as json_file:
        fcntl.flock(json_file, fcntl.LOCK_EX)  # 파일 락 설정
        AutoOrderList = json.load(json_file)
        fcntl.flock(json_file, fcntl.LOCK_UN)  # 파일 락 해제
except Exception as e:
    print("Exception by First")



# 분할 매수 주문 함수
def MakeSplitBuyOrder(ticker, order_money, split_count=1, time_term=0, Exclusive=False):
    global AutoOrderList  # 전역 변수임을 명시적으로 선언
    global upbit
    global DIST
    
    if Exclusive == True:
        for AutoSplitData in AutoOrderList:
            if AutoSplitData['OrderType'] == "Buy":
                if AutoSplitData['Ticker'] == ticker:
                    msg = DIST + " " + ticker + " 독점 분할 매수 주문이 실행 중이라 현재 진행 중인 분할 매수가 끝날 때 까지 추가 분할 매수 주문은 처리하지 않습니다."
                    print(msg)
                    line_alert.SendMessage(msg)
                    return
    

    SplitBuyMoney = order_money / float(split_count)

    if SplitBuyMoney < minimumMoney:
        SplitBuyMoney = minimumMoney

    #첫번째 매수!
    upbit.buy_market_order(ticker, SplitBuyMoney)
    time.sleep(0.2)

    msg = DIST + " " + ticker + " " + str(order_money) + "를 " + str(split_count) + "분할 매수 중입니다.\n"
    msg += "첫번째 매수 금액: " + str(SplitBuyMoney) + " 매수 주문 완료!"
    print(msg)
    line_alert.SendMessage(msg)

    #분할 매수수가 1개 이상인 경우 데이터를 추가해서 이후 분할 매수 주문을 처리할 수 있도록 해준다.
    if split_count > 1:

        AutoSplitData = dict()
        AutoSplitData['OrderType'] = "Buy"
        AutoSplitData['Ticker'] = ticker
        AutoSplitData['OrderMoney'] = order_money
        AutoSplitData['SplitBuyMoney'] = SplitBuyMoney
        AutoSplitData['SplitCount'] = split_count
        AutoSplitData['TimeTerm'] = time_term
        AutoSplitData['TimeCnt'] = 0
        AutoSplitData['OrderCnt'] = 1

        #!!!! 데이터를 리스트에 추가하고 저장하기!!!!
        AutoOrderList.append(AutoSplitData)
        with open(auto_order_file_path, 'w') as outfile:
            fcntl.flock(outfile, fcntl.LOCK_EX)
            json.dump(AutoOrderList, outfile)
            fcntl.flock(outfile, fcntl.LOCK_UN)

# 분할 매도 주문 함수
def MakeSplitSellOrder(ticker, order_volume, split_count=1, time_term=0, last_sell_all=False, Exclusive=False):
    global AutoOrderList  # 전역 변수임을 명시적으로 선언
    global upbit
    global DIST

    if Exclusive == True:
        for AutoSplitData in AutoOrderList:
            if AutoSplitData['OrderType'] == "Sell":
                if AutoSplitData['Ticker'] == ticker:
                    msg = DIST + " " + ticker + " 독점 분할 매도 주문이 실행 중이라 현재 진행중인 분할 매도가 끝날 때 까지 추가 분할 매도 주문은 처리하지 않습니다."
                    print(msg)
                    line_alert.SendMessage(msg)
                    return
    
    nowPrice = pyupbit.get_current_price(ticker)
    time.sleep(0.2)

    SplitSellVolume = order_volume / float(split_count)

    #분할해서 매도할 수량이 최소 주문 금액보다 적다면 최소 주문 금액을 보정해서 (10%) 최소 주문 금액은 매도 되도록 세팅힌다.
    if SplitSellVolume * nowPrice < minimumMoney:
        SplitSellVolume = (minimumMoney*1.1) / nowPrice


    #첫번째 매도!
    upbit.sell_market_order(ticker, SplitSellVolume)
    


    msg = DIST + " " + ticker + " " + str(order_volume) + "개 (" + str(nowPrice*order_volume) +")원어치 " + str(split_count) + "분할 매도 중입니다.\n"
    msg += "첫번째 매도 수량: " + str(SplitSellVolume) + "개 (" + str(nowPrice*SplitSellVolume) +")원어치 매도 주문 완료!"
    print(msg)
    line_alert.SendMessage(msg)

    if split_count > 1:
        AutoSplitData = dict()
        AutoSplitData['OrderType'] = "Sell"
        AutoSplitData['Ticker'] = ticker
        AutoSplitData['OrderVolume'] = order_volume
        AutoSplitData['SplitSellVolume'] = SplitSellVolume
        AutoSplitData['SplitCount'] = split_count
        AutoSplitData['TimeTerm'] = time_term
        AutoSplitData['TimeCnt'] = 0
        AutoSplitData['OrderCnt'] = 1
        AutoSplitData['LastSellAll'] = last_sell_all


        #!!!! 데이터를 리스트에 추가하고 저장하기!!!!
        AutoOrderList.append(AutoSplitData)
        with open(auto_order_file_path, 'w') as outfile:
            fcntl.flock(outfile, fcntl.LOCK_EX)
            json.dump(AutoOrderList, outfile)
            fcntl.flock(outfile, fcntl.LOCK_UN)

