'''
관련 포스팅
https://blog.naver.com/zacra/223750328250
https://blog.naver.com/zacra/223763707914

최종 개선
https://blog.naver.com/zacra/223773295093
https://blog.naver.com/zacra/223816550900


📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제공된 전략은 학습 및 테스트 목적으로 구성된 예시 코드이며
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.
   

주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!
   


'''
# -*- coding: utf-8 -*-
import KIS_Common as Common
import KIS_API_Helper_US as KisUS
import time
import json
import random
import fcntl
import line_alert

from tendo import singleton 
me = singleton.SingleInstance()

#장이 열린지 여부 판단을 위한 계좌 정보로 현재 자동매매중인 계좌명 아무거나 넣으면 됩니다.
Common.SetChangeMode("REAL") #즉 다계좌 매매로 REAL, REAL2, REAL3 여러개를 자동매매 해도 한개만 여기 넣으면 됨!

IsMarketOpen = KisUS.IsMarketOpen()

auto_order_file_path = "/var/autobot/KIS_US_SplitTrader_AutoOrderList.json"
time.sleep(random.random()*0.1)

#자동 주문 리스트 읽기!
AutoOrderList = list()
try:
    with open(auto_order_file_path, 'r') as json_file:
        fcntl.flock(json_file, fcntl.LOCK_EX)  # 파일 락 설정
        AutoOrderList = json.load(json_file)
        
        # RemainingVolume 항목이 없는 데이터 처리
        for AutoSplitData in AutoOrderList:
            if 'RemainingVolume' not in AutoSplitData:
                # 전체 주문량에서 이미 주문한 수량을 빼서 남은 수량 계산
                if AutoSplitData['OrderType'] == "Buy":
                    executed_volume = AutoSplitData['OrderCnt'] * AutoSplitData['SplitBuyVolume']
                else:  # Sell
                    executed_volume = AutoSplitData['OrderCnt'] * AutoSplitData['SplitSellVolume']
                    
                AutoSplitData['RemainingVolume'] = AutoSplitData['OrderVolume'] - executed_volume
                
        fcntl.flock(json_file, fcntl.LOCK_UN)  # 파일 락 해제
except Exception as e:
    print("Exception by First:", e)


# 
#장이 열린 상황에서만!
if IsMarketOpen == True:
    print("장이 열린 상황")

    items_to_remove = list()

    #저장된 분할 매매 데이터를 순회한다 
    for AutoSplitData in AutoOrderList:
        
        #매도를 먼저 한다!
        if AutoSplitData['OrderType'] == "Sell":
            print(AutoSplitData)

            #계좌 세팅!
            Common.SetChangeMode(AutoSplitData['AccountType'])

            DIST = Common.GetNowDist()


            #시간 카운트를 증가시킨다.
            AutoSplitData['TimeCnt'] += 1
            #시간 카운트가 시간 텀보다 크거나 같으면 주문을 처리한다.
            if AutoSplitData['TimeCnt'] >= AutoSplitData['TimeTerm']:
                AutoSplitData['TimeCnt'] = 0
                AutoSplitData['OrderCnt'] += 1

                IsLastOrder = False
                if AutoSplitData['OrderCnt'] >= AutoSplitData['SplitCount']:
                    IsLastOrder = True
                    items_to_remove.append(AutoSplitData)
                    
                msg = DIST + " " + AutoSplitData['stock_code'] + " " +  str(AutoSplitData['OrderVolume']) + "개 매도 중.." + str(AutoSplitData['RemainingVolume']) + "개 남음"
                print(msg)
                line_alert.SendMessage(msg)
                
                if AutoSplitData['RemainingVolume'] < 1:
                    
                    msg = DIST + " " + AutoSplitData['stock_code'] + " " +  str(AutoSplitData['OrderVolume']) + "개의 모든 매도 주문이 완료가 되어 분할 매도 종료합니다!"
                    print(msg)
                    line_alert.SendMessage(msg)
                    
                    if IsLastOrder == False:
                        items_to_remove.append(AutoSplitData)
                        
                else:

                    nowPrice = KisUS.GetCurrentPrice(AutoSplitData['stock_code'])

                    SellVolume = AutoSplitData['SplitSellVolume']
                    
                    if IsLastOrder == True:
                        SellVolume = AutoSplitData['RemainingVolume']

                    MyStockList = KisUS.GetMyStockList()

                    # 보유 주식 수량을 가져옵니다.
                    stock_amt = 0
                    for my_stock in MyStockList:
                        if my_stock['StockCode'] == AutoSplitData['stock_code']:
                            stock_amt = int(my_stock['StockAmt'])
                            
                    IsAllSell = False
                    if SellVolume > stock_amt:
                        SellVolume = stock_amt
                        IsAllSell = True
                        
                        if IsLastOrder == False:
                            items_to_remove.append(AutoSplitData)


                    #마지막 주문이고 LastSellAll이 True라면 모두 매도한다.  
                    if IsLastOrder == True:
                        if 'LastSellAll' in AutoSplitData and AutoSplitData['LastSellAll'] == True:
                            SellVolume = stock_amt
                            
                    if SellVolume >= 1:

                        # 매도!
                        data = KisUS.MakeSellLimitOrder(AutoSplitData['stock_code'],SellVolume,nowPrice*0.99)
                        print(data)
                        time.sleep(0.2)
                        
                        
                        AutoSplitData['RemainingVolume'] = AutoSplitData['RemainingVolume'] - SellVolume

                        msg = DIST + " " + AutoSplitData['stock_code'] + " " +  str(AutoSplitData['OrderVolume']) + "개 (" + str(nowPrice*AutoSplitData['OrderVolume']) +")원어치 " + str(AutoSplitData['SplitCount']) + "분할 매도 중입니다.\n"
                        msg += str(AutoSplitData['OrderCnt']) + "번째 매도 수량: " + str(SellVolume) + "개 (" + str(nowPrice*SellVolume) +")원어치 매도 주문 완료!"
                        msg += " 남은 수량: " + str(AutoSplitData['RemainingVolume'])
                        if IsAllSell == True:
                            msg += " (남은 분할 수가 있지만 수량 부족으로 모두 매도 완료!)"

                        if IsLastOrder == True:
                            msg += " 마지막 매도까지 모두 완료!"
                        print(msg)
                        line_alert.SendMessage(msg)



    #저장된 분할 매매 데이터를 순회한다 
    for AutoSplitData in AutoOrderList:
        
        #매수를 후에 한다!
        if AutoSplitData['OrderType'] == "Buy":
            print(AutoSplitData)

            #계좌 세팅!
            Common.SetChangeMode(AutoSplitData['AccountType'])

            DIST = Common.GetNowDist()


            #시간 카운트를 증가시킨다.
            AutoSplitData['TimeCnt'] += 1
            #시간 카운트가 시간 텀보다 크거나 같으면 주문을 처리한다.
            if AutoSplitData['TimeCnt'] >= AutoSplitData['TimeTerm']:
                AutoSplitData['TimeCnt'] = 0
                AutoSplitData['OrderCnt'] += 1

                IsLastOrder = False
                if AutoSplitData['OrderCnt'] >= AutoSplitData['SplitCount']:
                    IsLastOrder = True
                    items_to_remove.append(AutoSplitData)
                    
                    
                    
                msg = DIST + " " + AutoSplitData['stock_code'] + " " +  str(AutoSplitData['OrderVolume']) + "개 매수 중.." + str(AutoSplitData['RemainingVolume']) + "개 남음"
                print(msg)
                line_alert.SendMessage(msg)
                    
                if AutoSplitData['RemainingVolume'] < 1:
                    
                    msg = DIST + " " + AutoSplitData['stock_code'] + " " +  str(AutoSplitData['OrderVolume']) + "개의 모든 매수 주문이 완료가 되어 분할 매수 종료합니다!"
                    print(msg)
                    line_alert.SendMessage(msg)
                    
                    if IsLastOrder == False:
                        items_to_remove.append(AutoSplitData)   
                        
                else:

                        
                    nowPrice = KisUS.GetCurrentPrice(AutoSplitData['stock_code'])

        
                    #계좌 잔고를 가지고 온다!
                    Balance = KisUS.GetBalance()

                    RemainMoney = float(Balance['RemainMoney'])

                    msg = DIST + " " + AutoSplitData['stock_code'] + " " +  str(AutoSplitData['OrderVolume']) + "개 매수 중.." + str(AutoSplitData['RemainingVolume']) + "개 남음"
                    msg += " 남은 잔고: " + str(RemainMoney)
                    print(msg)
                    line_alert.SendMessage(msg)

                    if AutoSplitData['SplitBuyVolume'] * nowPrice > RemainMoney:
                        
                        msg = DIST + " " + AutoSplitData['stock_code'] + " " +  str(AutoSplitData['OrderVolume']) + "개 매수 중.." + str(AutoSplitData['RemainingVolume']) + "개 남음"
                        msg += " 남은 현금 부족으로 매수 수량을 줄입니다."
                        print(msg)
                        line_alert.SendMessage(msg)    
                        
              
                        AutoSplitData['SplitBuyVolume'] = int((RemainMoney * 0.98) / nowPrice) #수수료 및 슬리피지 시장가 고려

                    
                    BuyVolume = AutoSplitData['SplitBuyVolume']
                    if IsLastOrder == True:
                        BuyVolume = AutoSplitData['RemainingVolume']

                    
                    if BuyVolume >= 1:

                        #첫번째 매수!
                        data = KisUS.MakeBuyLimitOrder(AutoSplitData['stock_code'],BuyVolume,nowPrice*1.01) 
                        print(data)
                        time.sleep(0.2)
                        
                        
                        AutoSplitData['RemainingVolume'] = AutoSplitData['RemainingVolume'] - BuyVolume

                        msg = DIST + " " + AutoSplitData['stock_code'] + " " + str(AutoSplitData['OrderVolume']) + "주 현재가 기준 약(" + str(nowPrice*AutoSplitData['OrderVolume']) +")원어치 " + str(AutoSplitData['SplitCount']) + "분할 매수 중입니다.\n"
                        msg += str(AutoSplitData['OrderCnt']) + "번째 : " + str(BuyVolume) + "주 매수 주문 완료!"
                        msg += " 남은 수량: " + str(AutoSplitData['RemainingVolume'])
                        if IsLastOrder == True:
                            msg += " 마지막 매수까지 모두 완료!"
                            
                        print(msg)
                        line_alert.SendMessage(msg)
           

    #리스트에서 제거
    for item in items_to_remove:
        try:
            AutoOrderList.remove(item)
        except Exception as e:
            print(e)


    time.sleep(random.random()*0.1)
    #파일에 저장
    with open(auto_order_file_path, 'w') as outfile:
        fcntl.flock(outfile, fcntl.LOCK_EX)
        json.dump(AutoOrderList, outfile)
        fcntl.flock(outfile, fcntl.LOCK_UN)
