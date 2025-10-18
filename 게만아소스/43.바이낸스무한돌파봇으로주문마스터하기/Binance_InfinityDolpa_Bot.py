'''

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

바이낸스 ccxt 버전
pip3 install --upgrade ccxt==4.2.19
이렇게 버전을 맞춰주세요!

봇은 헤지모드에서 동작합니다. 꼭! 헤지 모드로 바꿔주세요!
https://blog.naver.com/zacra/222662884649

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

######################################################################
######################################################################
#코인 선물거래는 매우 위험합니다. 성과가 장기간 검증되지 않은 봇은 소액으로 공부하세요!!!!
https://blog.naver.com/zacra/223002929875
######################################################################
######################################################################


관련 포스팅
https://blog.naver.com/zacra/223265819278

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.

주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!


  
'''
import ccxt
import time
import pandas as pd
import pprint
       
import myBinance
import ende_key  #암복호화키
import my_key    #업비트 시크릿 액세스키
import line_alert
import json


#시간 정보를 가져옵니다. 아침 9시의 경우 서버에서는 hour변수가 0이 됩니다.
time_info = time.gmtime()
hour_time = time_info.tm_hour
min_time = time_info.tm_min
print(hour_time, min_time)




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
        'defaultType': 'future'
    }
})



BinanceGapDict = dict()

#파일 경로입니다.
gap_file_path = "/var/autobot/Binance_InfninityDolpa_GapInfoX.json"
try:
    #이 부분이 파일을 읽어서 딕셔너리에 넣어주는 로직입니다. 
    with open(gap_file_path, 'r') as json_file:
        BinanceGapDict = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")




#########################################################################################################
#########################################################################################################
#########################################################################################################
#########################################################################################################

#투자 비중!! 0.2라면 20%를 이 봇에 투자한다는 이야기 입니다.
Invest_Rate = 0.2

#레버리지!! 좀 높은 편인데 잘 조절하세요!!!
set_leverage = 10 

#최소 목표 간격 (단위 %)
min_target_rate_percent = 0.3

#나의 코인 제가 임의로 선정한 코인들입니다! 추천코인이라고 오해하지 말아 주세요!!!
InvestCoinList = ['ATOM/USDT','MATIC/USDT','ADA/USDT','DOT/USDT','SAND/USDT']

#투자할 코인 개수로 할당된 금액을 이 개수로 나눠서 코인별 할당금액이 정해집니다.
#현재는
CoinCnt = len(InvestCoinList) #투자 코인 개수!





for ticker in InvestCoinList:

    try: 

        if "/USDT" in ticker:
            Target_Coin_Ticker = ticker


            print("Target_Coin_Ticker:", Target_Coin_Ticker)
            time.sleep(0.5)

            Target_Coin_Symbol = ticker.replace("/", "").replace(":USDT", "")


            #해당 코인 가격을 가져온다.
            coin_price = myBinance.GetCoinNowPrice(binanceX, Target_Coin_Ticker)


            #잔고 데이타 가져오기 
            balance = binanceX.fetch_balance(params={"type": "future"})
            time.sleep(0.1)

            print(balance['USDT'])
            print("Total Money:",float(balance['USDT']['total']))
            print("Remain Money:",float(balance['USDT']['free']))

            #최소 주문 수량을 가져온다 
            minimun_amount = myBinance.GetMinimumAmount(binanceX,Target_Coin_Ticker)

            
            
            #해당 코인에 할당된 금액에 따른 최대 매수수량을 구해본다!
            Max_Amt = float(binanceX.amount_to_precision(Target_Coin_Ticker, myBinance.GetAmount(float(balance['USDT']['total']),coin_price,Invest_Rate / float(CoinCnt))))  * set_leverage 
 
            print("Max_Amt:", Max_Amt)
            
            
            Buy_Amt = Max_Amt / 4 #4분할.. 롱2 : 숏2:
            
            Buy_Amt = float(binanceX.amount_to_precision(Target_Coin_Ticker,Buy_Amt)) #보정!!!

            if minimun_amount > Buy_Amt:
                Buy_Amt = minimun_amount


            


            amt_s = 0 
            amt_b = 0
            entryPrice_s = 0 #평균 매입 단가. 따라서 물을 타면 변경 된다.
            entryPrice_b = 0 #평균 매입 단가. 따라서 물을 타면 변경 된다.
            leverage = 0


            isolated = True #격리모드인지 



            print("------")
            #숏잔고
            for posi in balance['info']['positions']:
                if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'SHORT':
                    print(posi)
                    amt_s = float(posi['positionAmt'])
                    entryPrice_s= float(posi['entryPrice'])
                    leverage = float(posi['leverage'])
                    isolated = posi['isolated']
                    break


            #롱잔고
            for posi in balance['info']['positions']:
                if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'LONG':
                    print(posi)
                    amt_b = float(posi['positionAmt'])
                    entryPrice_b = float(posi['entryPrice'])
                    leverage = float(posi['leverage'])
                    isolated = posi['isolated']
                    break






            #################################################################################################################
            #레버리지 셋팅
            if leverage != set_leverage:
                    
                try:
                    print(binanceX.fapiPrivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': set_leverage}))
                except Exception as e:
                    try:
                        print(binanceX.fapiprivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': set_leverage}))
                    except Exception as e:
                        print("Exception..Done")

            #################################################################################################################





            #################################################################################################################
            #격리 모드로 설정
            if isolated == False:
                try:
                    print(binanceX.fapiPrivate_post_margintype({'symbol': Target_Coin_Symbol, 'marginType': 'ISOLATED'}))
                except Exception as e:
                    try:
                        print(binanceX.fapiprivate_post_margintype({'symbol': Target_Coin_Symbol, 'marginType': 'ISOLATED'}))
                    except Exception as e:
                        print("Exception..Done")


            '''
            #현재 코인에 걸려진 주문 프린트..
            orders = binanceX.fetch_orders(Target_Coin_Ticker)

            for order in orders:
                if order['status'] == "open":
                    print(order['id'],order['type']," ",order['info']['positionSide']," ", order['info']['status'] )
            '''

            #########################################################################################
            #########################################################################################
            #########################################################################################
            # 5분봉 기준이기 때문에 5분마다 체크하게 합니다!!!
            
            #5분마다 체크가 필요!
            if min_time % 5 == 0 :
                
                #5분봉을 구한다!
                df = myBinance.GetOhlcv(binanceX,Target_Coin_Ticker, '5m')

                ########## RSI 지표 구하는 로직! ##########
                period = 14

                delta = df["close"].diff()
                up, down = delta.copy(), delta.copy()
                up[up < 0] = 0
                down[down > 0] = 0
                _gain = up.ewm(com=(period - 1), min_periods=period).mean()
                _loss = down.abs().ewm(com=(period - 1), min_periods=period).mean()
                RS = _gain / _loss

                df['rsi'] = pd.Series(100 - (100 / (1 + RS)), name="RSI")
                ########################################
                df['rsi_ma'] = df['rsi'].rolling(20).mean() #RSI의 20일 평균!


                #기준 간격을 구합니다. 이전 캔들 3개의 고가중 가장 높은 값과 이전 캔들 3개의 저가중 가장 낮은 값의 차이입니다!
                gap_rate = ((max(df['high'].iloc[-4],df['high'].iloc[-3],df['high'].iloc[-2]) / min(df['low'].iloc[-4],df['low'].iloc[-3],df['low'].iloc[-2])) - 1.0) 

                if gap_rate > 0.01:
                    gap_rate = 0.01

                gap_rate_percent = gap_rate * 100


                #최소 기준 간격을 넘으면 일단 포지션 잡을 수 있는 요건 충족!!!
                if gap_rate_percent >= min_target_rate_percent:
                    
                    print("간격은 충분하다!!")



                    #롱 포지션이 없다면....
                    if abs(amt_b) == 0:


                        # 기존 미리 걸어둔 주문을 취소 한다!
                        orders = binanceX.fetch_orders(Target_Coin_Ticker)

                        for order in orders:
                            if order['status'] == "open" and order['info']['positionSide'] == "LONG" :
                                try:

                                    binanceX.cancel_order(order['id'],Target_Coin_Ticker)

                                    msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 분 봉이 바뀌었으니 이전 주문 혹은 남아있는 롱 주문을 취소 합니다!!!! " + str(order['type']) + "주문 취소!"
                                    print(msg)
                                    #line_alert.SendMessage(msg)
                                
                                    time.sleep(0.1)

                                except Exception as e:
                                    print("error:", e)


                        #롱 돌파 기준!! 이전 캔들 2개의 고가중 큰 것이 기준!!
                        TargetPrice = max(df['high'].iloc[-3],df['high'].iloc[-2])
                    
                        #현재 돌파를 했다! 그리고 RSI평균이 증가추세면서 RSI평균보다 현재 RSI가 높은 상황이라면 롱 포지션!!!
                        if coin_price >= TargetPrice and df['rsi_ma'].iloc[-3] < df['rsi_ma'].iloc[-2] and  df['rsi_ma'].iloc[-2] < df['rsi'].iloc[-2]  :
                            print("이미 이전 2캔들의 고가를 돌파한 상황")


                            #현재 기준 간격 및 롱의 스탑로스를 올리기 위한 데이터를 초기화 한다!!
                            BinanceGapDict[Target_Coin_Ticker+"_LONG"] = gap_rate
                            BinanceGapDict[Target_Coin_Ticker+"_LONG_UU_CNT"] = 0
                            with open(gap_file_path, 'w') as outfile:
                                json.dump(BinanceGapDict, outfile)  

                            
                            
                            
                            #롱 시장가 주문! 2분할을 잡고 1분할은 지정가 익절 1분할은 트레일링 스탑으로 마무리!
                            params = {
                                'positionSide': 'LONG'
                            }
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', Buy_Amt * 2.0, None, params)
                            
                            
                            
                            
                            
                            #익절 가격을 정한다!! 기준 간격에 1.2를 곱해서 익절! 
                            target_price = binanceX.price_to_precision(Target_Coin_Ticker,data['price'] * (1.0 + gap_rate*1.2))
                            
                            
                            
                            #1분할 지정가 익절 주문을 넣는다
                            params = {
                                'positionSide': 'LONG'
                            }
                            limit_order_result = binanceX.create_order(Target_Coin_Ticker, 'limit', 'sell', data['amount']*0.5, target_price, params)
                                              
                                              
                                                    

                            #트레일링 스탑은 기준 간격의 절반으로 설정한다!!
                            trailling_stop_rate = round((gap_rate*50),1)

                            #0.2보다는 크게 설정!
                            if trailling_stop_rate < 0.2:
                                trailling_stop_rate = 0.2
                                
                            #2보다는 작게 설정!
                            if trailling_stop_rate > 2.0:
                                trailling_stop_rate = 2.0 

                            #1분할 트레일링 스탑 주문을 넣는다!!
                            params = {
                                'positionSide': 'LONG',
                                'activationPrice': target_price,
                                'callbackRate': trailling_stop_rate
                            }

                            trailling_order_result = binanceX.create_order(Target_Coin_Ticker, 'TRAILING_STOP_MARKET', 'sell', data['amount']*0.5, target_price, params)
                            
                            
                            
                            
                            
                            
                            
                            
                            
                            #스탑로스 가격구하기. 기준 간격에 0.75를 곱했다.
                            stop_price = binanceX.price_to_precision(Target_Coin_Ticker,data['price'] * (1.0 - gap_rate*0.75))
                            
                            
                            params = {
                                'positionSide': 'LONG',
                                'stopPrice': stop_price,
                                'closePosition' : True
                            }

                            #스탑 로스 주문을 걸어 놓는다.
                            stoploss_order_result = binanceX.create_order(Target_Coin_Ticker,'STOP_MARKET',"sell",data['amount'],stop_price,params)


                            msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 이전 캔들 2개의 고가를 모두 돌파한 상태여서 롱 포지션 잡고 익절,물타기,스탑로스 주문 모두 겁니다!!!"
                            print(msg)
                            line_alert.SendMessage(msg)





                            
                        else:
                            print("아직 롱 기준의 돌파를 하지 않았다!!!")

                            #RSI평균이 증가추세면서 RSI평균보다 현재 RSI가 높은 상황이라면 롱 포지션을 잡을 수 있으니깐 스탑 주문을 걸어놓는다 (미래에 걸릴 주문!)
                            if df['rsi_ma'].iloc[-3] < df['rsi_ma'].iloc[-2] and df['rsi_ma'].iloc[-2] < df['rsi'].iloc[-2]:


                                #현재 기준 간격 및 롱의 스탑로스를 올리기 위한 데이터를 초기화 한다!!
                                BinanceGapDict[Target_Coin_Ticker+"_LONG"] = gap_rate
                                BinanceGapDict[Target_Coin_Ticker+"_LONG_UU_CNT"] = 0
                                with open(gap_file_path, 'w') as outfile:
                                    json.dump(BinanceGapDict, outfile)  



                                #미래에 돌파하면 자동으로 포지션을 잡도록 스탑 주문을 걸어놓는다.2분할만큼
                                open_price = binanceX.price_to_precision(Target_Coin_Ticker,TargetPrice)
                                
                                params = {
                                    'positionSide': 'LONG',
                                    'stopPrice': open_price,
                                    'quantity': Buy_Amt*2.0,
                                    'closePosition' : False
                                }

                                stop_order_result = binanceX.create_order(Target_Coin_Ticker,'STOP_MARKET',"buy",Buy_Amt*2.0,open_price,params)

                                msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 이전 캔들 2개의 고가를 모두 돌파하는 가격에 미리 롱 주문을 걸어둡니다!!"
                                print(msg)
                                line_alert.SendMessage(msg)






                    #숏포지션이 없는 경우!
                    if abs(amt_s) == 0:


                        # 기존 미리 걸어둔 주문을 취소 한다!
                        orders = binanceX.fetch_orders(Target_Coin_Ticker)

                        for order in orders:
                            if order['status'] == "open" and order['info']['positionSide'] == "SHORT" :
                                try:

                                    binanceX.cancel_order(order['id'],Target_Coin_Ticker)

                                    msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 분봉이 바뀌었으니 이전 주문 혹은 남아있는 숏 주문을 취소 합니다!!!! " + str(order['type']) + "주문 취소!"
                                    print(msg)
                                    #line_alert.SendMessage(msg)
                                    
                                    time.sleep(0.1)

                                except Exception as e:
                                    print("error:", e)


                        #숏 돌파 기준!! 이전 캔들 2개의 저가중 작은 것이 기준!!
                        TargetPrice = min(df['low'].iloc[-3],df['low'].iloc[-2])
                    
                    
                        #현재 돌파를 했다! 그리고 RSI평균이 감소추세면서 RSI평균보다 현재 RSI가 낮은 상황이라면 숏 포지션!!!
                        if coin_price <= TargetPrice and df['rsi_ma'].iloc[-3] > df['rsi_ma'].iloc[-2] and df['rsi_ma'].iloc[-2] > df['rsi'].iloc[-2] :
                            print("이미 이전 2캔들의 저가를 하향 돌파한 상황")
                            
                            #현재 기준 간격 및 숏의 스탑로스를 내리기 위한 데이터를 초기화 한다!!
                            BinanceGapDict[Target_Coin_Ticker+"_SHORT"] = gap_rate
                            BinanceGapDict[Target_Coin_Ticker+"_SHORT_UU_CNT"] = 0
                            with open(gap_file_path, 'w') as outfile:
                                json.dump(BinanceGapDict, outfile)  




                            #숏 시장가 주문! 2분할을 잡고 1분할은 지정가 익절 1분할은 트레일링 스탑으로 마무리!
                            params = {
                                'positionSide': 'SHORT'
                            }
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', Buy_Amt * 2.0, None, params)
                            
                            
                            
                            
                            
                            
                            
                            #익절 가격을 정한다!! 기준 간격에 1.2를 곱해서 익절! 
                            target_price = binanceX.price_to_precision(Target_Coin_Ticker,data['price'] * (1.0 - gap_rate*1.2))
                            
                            
                            #1분할 지정가 익절 주문을 넣는다
                            params = {
                                'positionSide': 'SHORT'
                            }
                            limit_order_result = binanceX.create_order(Target_Coin_Ticker, 'limit', 'buy', data['amount']*0.5, target_price, params)
                                                    

                            #트레일링 스탑은 기준 간격의 절반으로 설정한다!!
                            trailling_stop_rate = round((gap_rate*50),1)

                            #0.2보다는 크게 설정!
                            if trailling_stop_rate < 0.2:
                                trailling_stop_rate = 0.2
                                
                            #2보다는 작게 설정!
                            if trailling_stop_rate > 2.0:
                                trailling_stop_rate = 2.0 

                                
                            #1분할 트레일링 스탑 주문을 넣는다!!
                            params = {
                                'positionSide': 'SHORT',
                                'activationPrice': target_price,
                                'callbackRate': trailling_stop_rate
                            }

                            trailling_order_result = binanceX.create_order(Target_Coin_Ticker, 'TRAILING_STOP_MARKET', 'buy', data['amount']*0.5, target_price, params)
                            
                            
                            
                            
                            
                            
                            
                            
                            #스탑로스 가격! 기준 간격에 0.75를 곱했다.
                            stop_price = binanceX.price_to_precision(Target_Coin_Ticker,data['price'] * (1.0 + gap_rate*0.75))
                            
                            params = {
                                'positionSide': 'SHORT',
                                'stopPrice': stop_price,
                                'closePosition' : True
                            }

                            #스탑 로스 주문을 걸어 놓는다.
                            stoploss_order_result = binanceX.create_order(Target_Coin_Ticker,'STOP_MARKET',"buy",data['amount'],stop_price,params)


                            msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 이전 캔들 2개의 저가를 모두 하향 돌파한 상태여서 숏 포지션 잡고 익절,물타기,스탑로스 주문 모두 겁니다!!!"
                            print(msg)
                            line_alert.SendMessage(msg)
                                    


                        else:
                            print("아직 숏 기준의 돌파를 하지 않았다!!!")
        
                            # RSI평균이 감소추세면서 RSI평균보다 현재 RSI가 낮은 상황이라면 숏 포지션을 잡을 수 있다!
                            if df['rsi_ma'].iloc[-3] > df['rsi_ma'].iloc[-2] and df['rsi_ma'].iloc[-2] > df['rsi'].iloc[-2]:

                                #현재 기준 간격 및 숏의 스탑로스를 내리기 위한 데이터를 초기화 한다!!
                                BinanceGapDict[Target_Coin_Ticker+"_SHORT"] = gap_rate
                                BinanceGapDict[Target_Coin_Ticker+"_SHORT_UU_CNT"] = 0
                                with open(gap_file_path, 'w') as outfile:
                                    json.dump(BinanceGapDict, outfile)  



                                #미래에 돌파하면 자동으로 포지션을 잡도록 스탑 주문을 걸어놓는다. 2분할만큼
                                open_price = binanceX.price_to_precision(Target_Coin_Ticker,TargetPrice)
                                
                                params = {
                                    'positionSide': 'SHORT',
                                    'stopPrice': open_price,
                                    'quantity': Buy_Amt*2.0,
                                    'closePosition' : False
                                }

                                stop_order_result = binanceX.create_order(Target_Coin_Ticker,'STOP_MARKET',"sell",Buy_Amt*2.0,open_price,params)


                                msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 이전 캔들 2개의 저가를 모두 하향 돌파하는 가격에 미리 숏 주문을 걸어둡니다!!"
                                print(msg)
                                line_alert.SendMessage(msg)
                                

                else:
                    print("간격이 충분하지 않음")
            else:

                #롱 포지션이 있는 경우 
                if abs(amt_b) != 0:
                    

                    orderBinances = binanceX.fetch_orders(Target_Coin_Ticker)

                    Is_Go_Order = False
                    for order_binance in orderBinances:
                        if order_binance['status'] == 'open' and order_binance['info']['positionSide'] == "LONG":
                            Is_Go_Order = True

                            break
                        

                    #걸려있는 주문이 없다면 미리 걸어둔 스탑 주문이 걸린거다! 익절 손절 주문을 걸어두자!
                    if Is_Go_Order == False:
                        print("주문이 걸려있지 않다!")

                        #저장해둔 기준 간격을 읽어 온다!
                        gap_rate = BinanceGapDict[Target_Coin_Ticker+"_LONG"]

                        #익절 가격
                        target_price = binanceX.price_to_precision(Target_Coin_Ticker,entryPrice_b * (1.0 + gap_rate*1.2))
                        
                        
                        #지정가 익절 주문
                        params = {
                            'positionSide': 'LONG'
                        }
                        limit_order_result = binanceX.create_order(Target_Coin_Ticker, 'limit', 'sell', abs(amt_b)*0.5, target_price, params)




                        trailling_stop_rate = round((gap_rate*50),1)

                        if trailling_stop_rate < 0.2:
                            trailling_stop_rate = 0.2

                        if trailling_stop_rate > 2:
                            trailling_stop_rate = 2
                            
                        #트레일링 스탑 주문           
                        params = {
                            'positionSide': 'LONG',
                            'activationPrice': target_price,
                            'callbackRate': trailling_stop_rate
                        }

                        trailling_order_result = binanceX.create_order(Target_Coin_Ticker, 'TRAILING_STOP_MARKET', 'sell', abs(amt_b)*0.5, target_price, params)
                        
                        
 
                        
                        #스탑로스 가격!
                        stop_price = binanceX.price_to_precision(Target_Coin_Ticker,entryPrice_b* (1.0 - gap_rate*0.75))
                        
                        params = {
                            'positionSide': 'LONG',
                            'stopPrice': stop_price,
                            'closePosition' : True
                        }

                        #스탑 로스 주문을 걸어 놓는다.
                        stoploss_order_result = binanceX.create_order(Target_Coin_Ticker,'STOP_MARKET',"sell",abs(amt_b),stop_price,params)



                        msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 미리 걸어둔 롱 주문이 체결되었어요!! 익절/물타기/손절 주문을 걸어둡니다!!"
                        print(msg)
                        line_alert.SendMessage(msg)




                #숏 포지션이 있는 경우
                if abs(amt_s) != 0:
                    
                        
                
                    orderBinances = binanceX.fetch_orders(Target_Coin_Ticker)

                    Is_Go_Order = False

                    for order_binance in orderBinances:

                        if order_binance['status'] == 'open' and order_binance['info']['positionSide'] == "SHORT":
                            Is_Go_Order = True
    
                            break



                    #걸려있는 주문이 없다면 미리 걸어둔 스탑 주문이 걸린거다! 익절 손절 주문을 걸어두자!
                    if Is_Go_Order == False:
                        print("주문이 걸려있지 않다!")
                        
                        gap_rate = BinanceGapDict[Target_Coin_Ticker+"_SHORT"]


                        #익절 가격
                        target_price = binanceX.price_to_precision(Target_Coin_Ticker,entryPrice_s * (1.0 - gap_rate*1.2))
                        
                        
                        #지정가 익절 주문
                        params = {
                            'positionSide': 'SHORT'
                        }
                        limit_order_result = binanceX.create_order(Target_Coin_Ticker, 'limit', 'buy', abs(amt_s)*0.5, target_price, params)


                        trailling_stop_rate = round((gap_rate*50),1)

                        if trailling_stop_rate < 0.2:
                            trailling_stop_rate = 0.2
                            
                            
                        if trailling_stop_rate > 2:
                            trailling_stop_rate = 2
                                        
                                        
                        #트레일링 스탑 주문..
                        params = {
                            'positionSide': 'SHORT',
                            'activationPrice': target_price,
                            'callbackRate': trailling_stop_rate
                        }

                        trailling_order_result = binanceX.create_order(Target_Coin_Ticker, 'TRAILING_STOP_MARKET', 'buy', abs(amt_s)*0.5, target_price, params)
                        
                        
                        
                        
                        #스탑로스 가격!
                        stop_price = binanceX.price_to_precision(Target_Coin_Ticker,entryPrice_s* (1.0 + gap_rate*0.75))
                        
                        params = {
                            'positionSide': 'SHORT',
                            'stopPrice': stop_price,
                            'closePosition' : True
                        }

                        #스탑 로스 주문을 걸어 놓는다.
                        stoploss_order_result = binanceX.create_order(Target_Coin_Ticker,'STOP_MARKET',"buy",abs(amt_s),stop_price,params)




                        msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 미리 걸어둔 숏 주문이 체결되었어요!! 익절/물타기/손절 주문을 걸어둡니다!!"
                        print(msg)
                        line_alert.SendMessage(msg)


        
        
        
        
            #롱 포지션이 있는 경우
            if abs(amt_b) != 0:
                print("투자중..")


                revenue_rate_b = (coin_price - entryPrice_b) / entryPrice_b * 100.0

                print(Target_Coin_Ticker, " revenue_rate_b : ", revenue_rate_b)


                #그럴일은 없겠지만 현재 수익률이 기준간격보다 더 떨어졌다면 스탑로스가 걸려야 되는데 만약 안걸렸다면.. 강제 손절!!
                if revenue_rate_b < BinanceGapDict[Target_Coin_Ticker+"_LONG"]*-100:

                    params = {
                        'positionSide': 'LONG'
                    }
                    print(binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', abs(amt_b), None, params))


                    msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 방어로직 강제 손절!"
                    print(msg)
                    line_alert.SendMessage(msg)


                else:


                    time.sleep(0.1)
                    
                    #1분봉을 읽어 온다.
                    df = myBinance.GetOhlcv(binanceX,Target_Coin_Ticker, '1m')


                    adjust_rate = 1.0
                    #이전봉이 음봉이거나 수익률이 0.2%이상(레버 곱하기 전)이라면..UU_CNT를 증가시켜 준다!!!
                    if df['close'].iloc[-2] < df['open'].iloc[-2]  or revenue_rate_b > 0.2:
                        
                        BinanceGapDict[Target_Coin_Ticker+"_LONG_UU_CNT"] += 0.2 #0.2씩 증가시키게 했는데 잘 조절하세용!

                        with open(gap_file_path, 'w') as outfile:
                            json.dump(BinanceGapDict, outfile)  

                        #증가된 UU_CNT를 통해 adjust_rate를 줄여준다..
                        adjust_rate -= (float(BinanceGapDict[Target_Coin_Ticker+"_LONG_UU_CNT"])*0.1)

                    if adjust_rate < 0.2:
                        adjust_rate = 0.2


                    print("adjust_rate: ", adjust_rate)

                    #줄어든 adjust_rate를 곱해서 스탑로스 가격 위로 땡기는 작업을 한다!!!
                    stop_price = binanceX.price_to_precision(Target_Coin_Ticker,coin_price* (1.0 - (BinanceGapDict[Target_Coin_Ticker+"_LONG"]*0.75*adjust_rate)))

                    #이거랑 별개로 현재 수익률이  기준간격 절반보다 크다면 스탑로스를 본전으로 땡겨 준다.. (즉 스탑로스가 걸리면 수수료만 날리는 구조.. 원금 확보)
                    if float(stop_price) < entryPrice_b and revenue_rate_b > BinanceGapDict[Target_Coin_Ticker+"_LONG"]*50.0:
                        stop_price = entryPrice_b

                    
                    #주문 정보를 읽어온다.
                    orders = binanceX.fetch_orders(Target_Coin_Ticker)
                    

                    for order in orders:

                        if order['status'] == "open" and order['type'] == 'stop_market' and order['info']['positionSide'] == "LONG":
                            
                            NowTriggerPrice = float(order['triggerPrice']) 

                            print("-------->",NowTriggerPrice,"<",stop_price,"CHECK!!")


                            #만약 계산된 스탑로스 가격이 현재의 스탑로스보다 크다면 기존 스탑로스 주문을 취소하고 새로 걸어준다!!!!
                            if NowTriggerPrice < float(stop_price):

                                try:

                                    binanceX.cancel_order(order['id'],Target_Coin_Ticker)
                                    time.sleep(0.1)

                                except Exception as e:
                                    print("error:", e)


                                params = {
                                    'positionSide': 'LONG',
                                    'stopPrice': stop_price,
                                    'closePosition' : True
                                }

                                #스탑 로스 주문을 걸어 놓는다.
                                stoploss_order_result = binanceX.create_order(Target_Coin_Ticker,'STOP_MARKET',"sell",abs(amt_b),stop_price,params)


                                msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 롱 스탑로스를 위로 올립니다.."
                                print(msg)
                                #line_alert.SendMessage(msg)

                            break
                        
                        
                    time.sleep(0.2)
                    
                    
                    
                    #만약 민감한 스탑로스 주문이... 발견되지 않는다면 걸어줍니다!!
                    #익절 주문도 만약에 없다면 걸어줘요!
                    orders = binanceX.fetch_orders(Target_Coin_Ticker)
                    

                    IsStopLossOk = False
                    IsGetOrderOk = False

                    for order in orders:

                        if order['status'] == "open" and order['type'] == 'stop_market' and order['info']['positionSide'] == "LONG":
                            IsStopLossOk = True
                            break
                        if order['status'] == "open" and (order['type'] == 'trailing_stop_market' or order['type'] == 'limit')  and order['info']['positionSide'] == "LONG":
                            IsGetOrderOk = True
                            


                    if IsStopLossOk == False:

                        params = {
                            'positionSide': 'LONG',
                            'stopPrice': stop_price,
                            'closePosition' : True
                        }

                        #스탑 로스 주문을 걸어 놓는다.
                        stoploss_order_result = binanceX.create_order(Target_Coin_Ticker,'STOP_MARKET',"sell",abs(amt_b),stop_price,params)


                        msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 롱 스탑로스가 없어서 만들었어요!"
                        print(msg)
                    
                    if IsGetOrderOk == False:

                    

                        #저장해둔 기준 간격을 읽어 온다!
                        gap_rate = BinanceGapDict[Target_Coin_Ticker+"_LONG"]

                        #익절 가격
                        target_price = binanceX.price_to_precision(Target_Coin_Ticker,entryPrice_b * (1.0 + gap_rate*1.2))
                        
                        
                        #지정가 익절 주문
                        params = {
                            'positionSide': 'LONG'
                        }
                        limit_order_result = binanceX.create_order(Target_Coin_Ticker, 'limit', 'sell', abs(amt_b)*0.5, target_price, params)




                        trailling_stop_rate = round((gap_rate*50),1)

                        if trailling_stop_rate < 0.2:
                            trailling_stop_rate = 0.2

                        if trailling_stop_rate > 2:
                            trailling_stop_rate = 2
                            
                        #트레일링 스탑 주문           
                        params = {
                            'positionSide': 'LONG',
                            'activationPrice': target_price,
                            'callbackRate': trailling_stop_rate
                        }

                        trailling_order_result = binanceX.create_order(Target_Coin_Ticker, 'TRAILING_STOP_MARKET', 'sell', abs(amt_b)*0.5, target_price, params)


                        msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 롱 익절 주문이 없어서 만들었어요"
                        print(msg)



                            

            #숏 포지션이 있는 경우
            if abs(amt_s) != 0:
                print("투자중..")



                #숏 수익율을 구한다!
                revenue_rate_s = (entryPrice_s - coin_price) / entryPrice_s * 100.0

                print(Target_Coin_Ticker, "revenue_rate_s : ", revenue_rate_s)


                #그럴일은 없겠지만 현재 수익률이 기준간격보다 더 떨어졌다면 스탑로스가 걸려야 되는데 만약 안걸렸다면.. 강제 손절!!
                if revenue_rate_s < BinanceGapDict[Target_Coin_Ticker+"_SHORT"]*-100:

                    params = {
                        'positionSide': 'SHORT'
                    }
                    print(binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', abs(amt_s), None, params))


                    msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 방어로직 강제 손절!"
                    print(msg)
                    line_alert.SendMessage(msg)
                    
                else:

                    time.sleep(0.1)
                    df = myBinance.GetOhlcv(binanceX,Target_Coin_Ticker, '1m')

                    adjust_rate = 1.0
                    
                    #이전봉이 양봉이거나 수익률이 0.2%이상(레버 곱하기 전)이라면..UU_CNT를 증가시켜 준다!!!
                    if df['close'].iloc[-2] > df['open'].iloc[-2] or revenue_rate_s > 0.2:
         
                        BinanceGapDict[Target_Coin_Ticker+"_SHORT_UU_CNT"] += 0.2 #0.2씩 증가시키게 했는데 잘 조절하세용!

                        with open(gap_file_path, 'w') as outfile:
                            json.dump(BinanceGapDict, outfile)  

                        #증가된 UU_CNT를 통해 adjust_rate를 줄여준다..
                        adjust_rate -= (float(BinanceGapDict[Target_Coin_Ticker+"_SHORT_UU_CNT"])*0.1)

                    if adjust_rate < 0.2:
                        adjust_rate = 0.2


                    print("adjust_rate: ", adjust_rate)


                    #줄어든 adjust_rate를 곱해서 스탑로스 가격 아래로 땡기는 작업을 한다!!!
                    stop_price = binanceX.price_to_precision(Target_Coin_Ticker,coin_price* (1.0 + (BinanceGapDict[Target_Coin_Ticker+"_SHORT"]*0.75*adjust_rate)))


                    #이거랑 별개로 현재 수익률이 기준간격 절반보다 크다면 스탑로스를 본전으로 땡겨 준다.. (즉 스탑로스가 걸리면 수수료만 날리는 구조.. 원금 확보)
                    if float(stop_price) > entryPrice_s and revenue_rate_s > BinanceGapDict[Target_Coin_Ticker+"_SHORT"] * 50:
                        stop_price = entryPrice_s


                    #주문 정보를 읽어온다.
                    orders = binanceX.fetch_orders(Target_Coin_Ticker)

                    for order in orders:

                        if order['status'] == "open" and order['type'] == 'stop_market' and order['info']['positionSide'] == "SHORT":
    
                            NowTriggerPrice = float(order['triggerPrice']) 

                            
                            print("-------->",NowTriggerPrice,">",stop_price,"CHECK!!")
                            
                            
                            #만약 계산된 스탑로스 가격이 현재의 스탑로스보다 작다면 기존 스탑로스 주문을 취소하고 새로 걸어준다!!!!
                            if NowTriggerPrice > float(stop_price):

                                try:

                                    binanceX.cancel_order(order['id'],Target_Coin_Ticker)

                                    time.sleep(0.1)

                                except Exception as e:
                                    print("error:", e)


                                params = {
                                    'positionSide': 'SHORT',
                                    'stopPrice': stop_price,
                                    'closePosition' : True
                                }

                                #스탑 로스 주문을 걸어 놓는다.
                                stoploss_order_result = binanceX.create_order(Target_Coin_Ticker,'STOP_MARKET',"buy",abs(amt_s),stop_price,params)


                                msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 숏 스탑로스를 아래로 내립니다.."
                                print(msg)
                                #line_alert.SendMessage(msg)
                                


                            break

                    time.sleep(0.2)
                    
                    
                    #만약 민감한 스탑로스 주문이... 발견되지 않는다면 걸어줍니다!!
                    #익절 주문도 만약에 없다면 걸어줘요!
                    orders = binanceX.fetch_orders(Target_Coin_Ticker)
                    

                    IsStopLossOk = False
                    IsGetOrderOk = False

                    for order in orders:

                        if order['status'] == "open" and order['type'] == 'stop_market' and order['info']['positionSide'] == "SHORT":
                            IsStopLossOk = True
                            
                        if order['status'] == "open" and (order['type'] == 'trailing_stop_market' or order['type'] == 'limit')  and order['info']['positionSide'] == "SHORT":
                            IsGetOrderOk = True
                            

                        
                    if IsStopLossOk == False:

                        params = {
                            'positionSide': 'SHORT',
                            'stopPrice': stop_price,
                            'closePosition' : True
                        }

                        #스탑 로스 주문을 걸어 놓는다.
                        stoploss_order_result = binanceX.create_order(Target_Coin_Ticker,'STOP_MARKET',"buy",abs(amt_s),stop_price,params)


                        msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 숏 스탑로스가 없어서 만들었어요"
                        print(msg)

                    if IsGetOrderOk == False:

                    

                        gap_rate = BinanceGapDict[Target_Coin_Ticker+"_SHORT"]


                        #익절 가격
                        target_price = binanceX.price_to_precision(Target_Coin_Ticker,entryPrice_s * (1.0 - gap_rate*1.2))
                        
                        
                        #지정가 익절 주문
                        params = {
                            'positionSide': 'SHORT'
                        }
                        limit_order_result = binanceX.create_order(Target_Coin_Ticker, 'limit', 'buy', abs(amt_s)*0.5, target_price, params)


                        trailling_stop_rate = round((gap_rate*50),1)

                        if trailling_stop_rate < 0.2:
                            trailling_stop_rate = 0.2
                            
                            
                        if trailling_stop_rate > 2:
                            trailling_stop_rate = 2
                                        
                                        
                        #트레일링 스탑 주문..
                        params = {
                            'positionSide': 'SHORT',
                            'activationPrice': target_price,
                            'callbackRate': trailling_stop_rate
                        }

                        trailling_order_result = binanceX.create_order(Target_Coin_Ticker, 'TRAILING_STOP_MARKET', 'buy', abs(amt_s)*0.5, target_price, params)
                        
                        
                        

                        msg = Target_Coin_Ticker + " 바이낸스 무한 돌파 전략 봇 : 숏 익절 주문이 없어서 만들었어요"
                        print(msg)

    except Exception as e:
        print("error:", e)




#이 밑에 부분은 옵션으로 없어도 됩니다.
#그냥 내 총 잔고를 매 시간마다 혹은 0.5% 증가 되었다면 알림을 받는 로직입니다.

#잔고 데이타 가져오기 
balance = binanceX.fetch_balance(params={"type": "future"})
time.sleep(0.1)


MoneyDict = dict()

#파일 경로입니다.
money_file_path = "/var/autobot/BinanceFurtureMoneyX.json"
try:
    #이 부분이 파일을 읽어서 딕셔너리에 넣어주는 로직입니다. 
    with open(money_file_path, 'r') as json_file:
        MoneyDict = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")


#현재 평가금액을 구합니다.
TotalRealMoney =  float(balance['total']['USDT']) 

print("TotalRealMoney ", TotalRealMoney)



if MoneyDict.get('TotalRealMoney') == None:
    MoneyDict['TotalRealMoney'] = TotalRealMoney

    with open(money_file_path, 'w') as outfile:
        json.dump(MoneyDict, outfile)   

    line_alert.SendMessage("!!!!!!!!!!!!!! First !!!!!! " + str(MoneyDict['TotalRealMoney']))


print("$$$$$$$$ MoneyDict['TotalRealMoney']", MoneyDict['TotalRealMoney'])
print("$$$$$$$$ MoneyDict['TotalRealMoney'] * 1.005", MoneyDict['TotalRealMoney'] * 1.005)
print("$$$$$$$$ TotalRealMoney", TotalRealMoney)



#이전에 저장된 가격에서 0.5%이상 증가되었다면!!
if MoneyDict['TotalRealMoney'] * 1.005 <= TotalRealMoney :


    #그리고 저장!!!
    MoneyDict['TotalRealMoney'] = TotalRealMoney

    with open(money_file_path, 'w') as outfile:
        json.dump(MoneyDict, outfile)   

    line_alert.SendMessage("$$$$$$$$!!!!!!!!!!!!!! 0.05% UPUP!!!!!!  USDT:" + str(TotalRealMoney))


else:
    if min_time == 0:
        line_alert.SendMessage("$$$$$$$$!!!!!!!!!!!!!!!!!!  USDT:" + str(TotalRealMoney))








