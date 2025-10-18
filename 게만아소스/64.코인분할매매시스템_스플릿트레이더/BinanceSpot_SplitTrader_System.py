'''

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

바이낸스 ccxt 버전
pip3 install --upgrade ccxt==4.2.19
이렇게 버전을 맞춰주세요!

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


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
import ccxt
import myBinance
import ende_key  #암복호화키
import my_key   
import time
import random
import json
import line_alert
import fcntl

#from tendo import singleton 
#me = singleton.SingleInstance()



DIST = "바이낸스현물"



#암복호화 클래스 객체를 미리 생성한 키를 받아 생성한다.
simpleEnDecrypt = myBinance.SimpleEnDecrypt(ende_key.ende_key)


#암호화된 액세스키와 시크릿키를 읽어 복호화 한다.
Binance_AccessKey = simpleEnDecrypt.decrypt(my_key.binance_access)
Binance_ScretKey = simpleEnDecrypt.decrypt(my_key.binance_secret)


# binance 객체 생성
binanceX = ccxt.binance(config={
    'apiKey': Binance_AccessKey, 
    'secret': Binance_ScretKey,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'spot'
    }
})




#최소 금액 
minimumMoney = 5.0 #5USDT


auto_order_file_path = "/var/autobot/BinanceSpot_SplitTrader_AutoOrderList.json"
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


items_to_remove = list()


#저장된 분할 매매 데이터를 순회한다 
for AutoSplitData in AutoOrderList:
    
    #매도를 먼저 한다!!
    if AutoSplitData['OrderType'] == "Sell":
            
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
                
            nowPrice = myBinance.GetCoinNowPrice(binanceX, AutoSplitData['Ticker'])

            balance = binanceX.fetch_balance(params={"type": "spot"})
            time.sleep(0.1)

        

            SellVolume = AutoSplitData['SplitSellVolume']
            AllVolume = float(balance[AutoSplitData['Ticker'].split('/')[0]]['total'])

            if AllVolume * nowPrice < minimumMoney:

                msg = DIST + " " + AutoSplitData['Ticker'] + " 현재 보유 수량이 최소 주문 금액보다 적어서 매도 주문을 취소합니다."
                print(msg)
                line_alert.SendMessage(msg)

                if IsLastOrder == False:
                    items_to_remove.append(AutoSplitData)

            else:
                #마지막 주문이라면 매도했을 때 남은 금액이 5 USDT 이하라면 자투리로 판단 모두 매도한다.   
                if IsLastOrder == True:

                    if 'LastSellAll' in AutoSplitData and AutoSplitData['LastSellAll'] == True:
                        SellVolume = AllVolume
                    else:
                        #남은 수량과 매도 수량의 차이를 구한다.
                        GapVolume = abs(AllVolume - SellVolume)
                    
                        #마지막 주문이라면 매도했을 때 남은 금액이 5 USDT 이하라면 자투리로 판단 모두 매도한다.   
                        if GapVolume * nowPrice <= minimumMoney:
                            SellVolume = AllVolume



                #매도!
                data = binanceX.create_order(AutoSplitData['Ticker'], 'market', 'sell', AutoSplitData['SplitSellVolume'])
                print(data)
                time.sleep(0.2)
                


                msg = DIST + " " + AutoSplitData['Ticker'] + " " + str(AutoSplitData['OrderVolume']) + "개 (" + str(nowPrice*AutoSplitData['OrderVolume']) +")원어치 " + str(AutoSplitData['SplitCount']) + "분할 매도 중입니다.\n"
                msg += str(AutoSplitData['OrderCnt']) + "번째 매도 수량: " + str(AutoSplitData['SplitSellVolume']) + "개 (" + str(nowPrice*AutoSplitData['SplitSellVolume']) +")원어치 매도 주문 완료!"

                if IsLastOrder == True:
                    msg += " 마지막 매도까지 모두 완료!"
                    
                print(msg)
                line_alert.SendMessage(msg)




#저장된 분할 매매 데이터를 순회한다 
for AutoSplitData in AutoOrderList:
    
    #매수를 후에 한다!
    if AutoSplitData['OrderType'] == "Buy":
            
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
                
            nowPrice = myBinance.GetCoinNowPrice(binanceX, AutoSplitData['Ticker'])

            balance = binanceX.fetch_balance(params={"type": "spot"})
            time.sleep(0.1)
            
            

            usdt = float(balance['USDT']['free'])

            if AutoSplitData['SplitBuyVolume'] * nowPrice > usdt:
                AutoSplitData['SplitBuyVolume'] = (usdt * 0.99) / nowPrice #수수료 및 슬리피지 고려



            if AutoSplitData['SplitBuyVolume'] * nowPrice < minimumMoney:
                msg = DIST + " " + AutoSplitData['Ticker'] + " 현재 보유 USDT가 최소 주문 금액보다 적어서 매수 주문을 취소합니다."
                print(msg)
                line_alert.SendMessage(msg)

                if IsLastOrder == False:
                    items_to_remove.append(AutoSplitData)
            else:


                data = binanceX.create_order(AutoSplitData['Ticker'], 'market', 'buy', AutoSplitData['SplitBuyVolume'])
                print(data)
                time.sleep(0.2)

                msg = DIST + " " + AutoSplitData['Ticker'] + " " + str(AutoSplitData['OrderVolume']) + "개 (" + str(nowPrice*AutoSplitData['OrderVolume']) +")원어치 " + str(AutoSplitData['SplitCount']) + "분할 매수 중입니다.\n"
                msg += str(AutoSplitData['OrderCnt']) + "번째 매수 수량: " + str(AutoSplitData['SplitBuyVolume']) + "개  (" + str(nowPrice*AutoSplitData['SplitBuyVolume']) +")원어치 매수 주문 완료!"
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
