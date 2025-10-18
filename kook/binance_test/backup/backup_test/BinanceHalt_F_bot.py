#-*-coding:utf-8 -*-
'''

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
 
바이낸스 ccxt 버전
pip3 install --upgrade ccxt==4.2.19
이렇게 버전을 맞춰주세요!

봇은 헤지모드에서 동작합니다. 꼭! 헤지 모드로 바꿔주세요!
https://blog.naver.com/zacra/222662884649

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

해당 컨텐츠는 제가 직접 투자 하기 위해 이 전략을 추가 개선해서 더 좋은 성과를 보여주는 개인 전략이 존재합니다. 

게만아 추가 개선 개인 전략들..
https://blog.naver.com/zacra/223196497504

관심 있으신 분은 위 포스팅을 참고하세요!

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$


관련 포스팅
https://blog.naver.com/zacra/223451342123

최종편 포스팅
https://blog.naver.com/zacra/223455858624

위 포스팅을 꼭 참고하세요!!!

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.

주식/코인 파이썬 매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!

 
'''

import ccxt
import myBinance
import time

import ende_key  #암복호화키
import my_key    #업비트 시크릿 액세스키
import pandas as pd
import pprint
import json

import line_alert





#시간 정보를 읽는다
time_info = time.gmtime()

day_n = time_info.tm_mday



#오늘 로직이 진행되었는지 날짜 저장 관리 하는 파일
DateDateTodayDict = dict()

#파일 경로입니다.
today_file_path = "/var/autobot/BinanceHaltFInvestTodayX.json"
try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(today_file_path, 'r') as json_file:
        DateDateTodayDict = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Init..")
    
    #0으로 초기화!!!!!
    DateDateTodayDict['date'] = 0
    #파일에 저장
    with open(today_file_path, 'w') as outfile:
        json.dump(DateDateTodayDict, outfile)

############################################################
############################################################
#투자 비중 -> 1.0 : 100%  0.5 : 50%   0.1 : 10%
InvestRate = 0.3 #투자 비중은 자금사정에 맞게 수정하세요!
MaxCoinCnt = 6 #투자 코인 개수!!!

#레버리지!! 1배로 기본 셋! 레버리지를 쓰면 음의 복리로 인해 백테스팅과 다른 결과가 나타날 수 있음!
set_leverage = 1
############################################################
############################################################

if DateDateTodayDict['date'] != day_n:
    



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


    #잔고 데이타 가져오기 
    balance = binanceX.fetch_balance(params={"type": "future"})
    time.sleep(0.1)
    
    
    InvestCoinMoney = (float(balance['USDT']['total']) * InvestRate) / (MaxCoinCnt) #코인당 투자금! 총 평가금 기준!!


    #해당 전략이 매매하면 안되는 코인리스트.. (다른전략이 투자하는 코인이거나 상폐 예정인 코인들을 여기에 추가!!!)
    OutCoinList = ['BTC/USDT:USDT','ETH/USDT:USDT']


    #투자한 코인을 저장할 리스트!!
    AltInvestList = list()

    #파일 경로입니다.
    invest_file_path = "/var/autobot/BinanceHaltFInvestListX.json"
    try:
        #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
        with open(invest_file_path, 'r') as json_file:
            AltInvestList = json.load(json_file)

    except Exception as e:
        #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
        print("Exception by First")



    #코인을 얼마 기간동안 보유하고 있는지를 관리할 파일!
    CoinHasCountDict = dict()

    #파일 경로입니다.
    CoinHasCount_file_path = "/var/autobot/BinanceHaltFHasCoinCountX.json"
    try:
        #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
        with open(CoinHasCount_file_path, 'r') as json_file:
            CoinHasCountDict = json.load(json_file)

    except Exception as e:
        #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
        print("..")



    tickers_prev = binanceX.fetch_tickers()

    Tickers = list()

    for ticker, coin_Data in tickers_prev.items():
        if "/USDT" in ticker and "-" not in ticker:
            print(ticker ,"added")
            Tickers.append(ticker)
            
            
    stock_df_list = []

    for ticker in Tickers:

        try:

   
            print("----->", ticker ,"<-----")
            df = myBinance.GetOhlcv(binanceX,ticker, '1d')

            df['value'] = df['close'] * df['volume']
            
            period = 14

            delta = df["close"].diff()
            up, down = delta.copy(), delta.copy()
            up[up < 0] = 0
            down[down > 0] = 0
            _gain = up.ewm(com=(period - 1), min_periods=period).mean()
            _loss = down.abs().ewm(com=(period - 1), min_periods=period).mean()
            RS = _gain / _loss

            df['RSI'] = pd.Series(100 - (100 / (1 + RS)), name="RSI")

            df['prevRSI'] = df['RSI'].shift(1)
            df['ma5_rsi_before'] = df['RSI'].rolling(5).mean().shift(1)


            df['prevValue'] = df['value'].shift(1)
            df['prevClose'] = df['close'].shift(1)
            df['prevClose2'] = df['close'].shift(2)

            df['prevChange'] = (df['prevClose'] - df['prevClose2']) / df['prevClose2']

            df['value_ma'] = df['value'].rolling(window=10).mean().shift(1)

            df['ma5_before'] = df['close'].rolling(5).mean().shift(1)
            df['ma5_before2'] = df['close'].rolling(5).mean().shift(2)

            df['ma10_before'] = df['close'].rolling(10).mean().shift(1)

            df['ma20_before'] = df['close'].rolling(20).mean().shift(1)

            df['ma60_before'] = df['close'].rolling(60).mean().shift(1)
            df['ma60_before2'] = df['close'].rolling(60).mean().shift(2)
            

            df['ma120_before'] = df['close'].rolling(120).mean().shift(1)
            df['ma120_before2'] = df['close'].rolling(120).mean().shift(2)


            df['prevCloseW'] = df['close'].shift(7)
            df['prevChangeW'] = (df['prevClose'] - df['prevCloseW']) / df['prevCloseW']
                
            df.dropna(inplace=True) #데이터 없는건 날린다!

        

            data_dict = {ticker: df}
            stock_df_list.append(data_dict)

            time.sleep(0.2)

        except Exception as e:
            print("Exception ", e)


    # Combine the OHLCV data into a single DataFrame
    combined_df = pd.concat([list(data_dict.values())[0].assign(ticker=ticker) for data_dict in stock_df_list for ticker in data_dict])

    # Sort the combined DataFrame by date
    combined_df.sort_index(inplace=True)


    pprint.pprint(combined_df)
    print(" len(combined_df) ", len(combined_df))


    combined_df.index = pd.DatetimeIndex(combined_df.index).strftime('%Y-%m-%d %H:%M:%S')

    #가장 최근 날짜를 구해서 가져옴 
    date = combined_df.iloc[-1].name


    btc_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == 'BTC/USDT:USDT')]

    pick_coins_top = combined_df.loc[combined_df.index == date].groupby('ticker')['value_ma'].max().nlargest(20)

    
    ###################################################
    #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 시작<--
    pick_coins_top_change = combined_df.loc[combined_df.index == date].groupby('ticker')['prevChangeW'].max().nlargest(MaxCoinCnt)
    #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 끝 <--
    ###################################################
    
    ###################################################
    #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 시작!<--
    '''
    dic_coin_change = dict()

    for ticker in pick_coins_top.index:
        try:
            
                
            if ticker in ['BTC/USDT:USDT','ETH/USDT:USDT']: 
                continue

            coin_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == ticker)]
            if len(coin_data) == 1:
                    
                dic_coin_change[ticker] = coin_data['prevChangeW'].values[0]

        except Exception as e:
            print("---:",e)

    dic_sorted_coin_change = sorted(dic_coin_change.items(), key = lambda x : x[1], reverse= True)

    pick_coins_top_change = list()
    cnt = 0
    for coin_data in dic_sorted_coin_change:
        cnt += 1
        if cnt <= MaxCoinCnt:
            pick_coins_top_change.append(coin_data[0])
        else:
            break
    '''
    #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 끝 <--
    ###################################################

    TodayRemoveList = list()

    items_to_remove = list()

    #투자중 코인!
    for coin_ticker in AltInvestList:
        
        Target_Coin_Ticker = coin_ticker
        Target_Coin_Symbol = coin_ticker.replace("/", "").replace(":USDT", "")


        amt_b = 0
        entryPrice_b = 0 
        unrealizedProfit_b = 0

        #롱잔고
        for posi in balance['info']['positions']:
            if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'LONG':
                print(posi)
                amt_b = float(posi['positionAmt'])
                entryPrice_b = float(posi['entryPrice'])
                unrealizedProfit_b = float(posi['unrealizedProfit'])
                break


        


        #잔고가 있는 경우.
        if abs(amt_b) > 0: 

            coin_price = myBinance.GetCoinNowPrice(binanceX, Target_Coin_Ticker)
            
            revenue_rate_b = (coin_price - entryPrice_b) / entryPrice_b * 100.0
            
            msg = coin_ticker + "현재 수익률 : 약 " + str(round(revenue_rate_b,2)) + "% 수익금 : 약" + str(format(round(unrealizedProfit_b), ',')) + "USDT"
            print(msg)
            line_alert.SendMessage(msg)


            #혹시 값이 없다면 0으로 넣어준다!
            if CoinHasCountDict.get(coin_ticker) == None:

                CoinHasCountDict[coin_ticker] = 0
                #파일에 저장
                with open(CoinHasCount_file_path, 'w') as outfile:
                    json.dump(CoinHasCountDict, outfile)
                    
                    
            #보유 날자를 증가시켜준다!!!
            CoinHasCountDict[coin_ticker] += 1
            #파일에 저장
            with open(CoinHasCount_file_path, 'w') as outfile:
                json.dump(CoinHasCountDict, outfile)
                
                

            stock_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == coin_ticker)]


            if len(stock_data) == 1 and len(btc_data) == 1:

                IsSell = False



                #매도 조건!!!! 7일 이상 보유중이라면 리밸런싱 대상이 될 수 있다!
                if CoinHasCountDict[coin_ticker] >= 7:
                    
                    IsTopIn = False
                    ###################################################
                    #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 시작<--
                    #'''
                    for ticker_t in pick_coins_top.index:
                        
                        if ticker_t == coin_ticker:
                            for ticker_t2 in pick_coins_top_change.index:
                            
                                if ticker_t2 == ticker_t:
                                    coin_top_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == ticker_t2)]
                                    if len(coin_top_data) == 1:
                                        IsTopIn = True
                                        break
                    #'''
                    #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 끝 <--
                    ###################################################
                    
                    ###################################################
                    #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 시작!<--
                    '''
                    if coin_ticker in pick_coins_top_change:
                        IsTopIn = True
                    '''
                    #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 끝 <--
                    ###################################################
                    if IsTopIn == False:
                        IsSell = True
                        
                #비트코인이 120일선 아래로 떨어지면 매도한다!
                if btc_data['ma120_before'].values[0]  >  btc_data['prevClose'].values[0]:
                     IsSell = True



                if IsSell == True:


                    TodayRemoveList.append(Target_Coin_Ticker)
                    params = {
                        'positionSide': 'LONG'
                    }
                    print(binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', abs(amt_b), None, params))
                    
                                    
                    msg = coin_ticker + " 바이낸스 할트 투자 봇 : 조건을 불만족하여 모두 포지션 정리했어요!!"
                    print(msg)
                    line_alert.SendMessage(msg)

                    items_to_remove.append(coin_ticker)


                    #보유 날자를 초기화
                    CoinHasCountDict[coin_ticker] = 0
                    #파일에 저장
                    with open(CoinHasCount_file_path, 'w') as outfile:
                        json.dump(CoinHasCountDict, outfile)
                
        #잔고가 없는 경우
        else:
            #투자중으로 나와 있는데 잔고가 없다? 있을 수 없지만 수동으로 매도한 경우..
            items_to_remove.append(coin_ticker)


    #리스트에서 제거
    for item in items_to_remove:
        AltInvestList.remove(item)


    #파일에 저장
    with open(invest_file_path, 'w') as outfile:
        json.dump(AltInvestList, outfile)


    ###################################################
    #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 시작<--
    for ticker in pick_coins_top.index:
    #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 끝 <--
    ###################################################

    ###################################################
    #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 시작!<--
    #for ticker in pick_coins_top_change:
    #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 끝 <--
    ###################################################
    
        
        Target_Coin_Ticker = ticker
        Target_Coin_Symbol = ticker.replace("/", "").replace(":USDT", "")


        coin_price = myBinance.GetCoinNowPrice(binanceX, Target_Coin_Ticker)
        
        
        if ticker in OutCoinList: #제외할 코인!
            continue
        
        
        CheckMsg = ticker
        print("---거래대금 상위 OK..." ,ticker)
        CheckMsg += " 거래대금 조건 만족! "
        
        IsAlReadyInvest = False
        for coin_ticker in AltInvestList:
            if ticker == coin_ticker: 
                IsAlReadyInvest = True
                break

            

        ###################################################
        #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 시작<--
        #'''
        IsTOPInChange = False
        for ticker_t in pick_coins_top_change.index:

            if ticker_t == ticker:
                coin_top_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == ticker_t)]
                if len(coin_top_data) == 1:
                    IsTOPInChange = True
                    break
        #'''
        #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 끝 <--
        ################################################### 

            
        ###################################################
        #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 시작!<--
        #IsTOPInChange = True
        #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 끝 <--
        ###################################################
        



        stock_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == ticker)]

       
        #이미 투자중이 아니면서 조건 만족한 코인들
        if len(stock_data) == 1 and IsAlReadyInvest == False and IsTOPInChange == True: 

            print("--- 등락률 상위 OK..." ,ticker)

            CheckMsg += " 등락률 상위 조건 만족! "

            IsBuyGo = False

            #매수 조건 체크!
            if (btc_data['ma60_before2'].values[0]  <  btc_data['ma60_before'].values[0] or btc_data['ma60_before'].values[0]  <  btc_data['prevClose'].values[0])  and (btc_data['ma120_before2'].values[0]  <  btc_data['ma120_before'].values[0] or btc_data['ma120_before'].values[0]  <  btc_data['prevClose'].values[0]) and stock_data['prevChangeW'].values[0] > 0:

                CheckMsg += " 추가 조건 만족! 모든 코인이 투자된 것이 아니라면 롱포지션!! "
                IsBuyGo = True



            #조건 만족하고 모든 코인이 투자된 것이 아니라면 
            if IsBuyGo == True and len(AltInvestList) < int(MaxCoinCnt) and Target_Coin_Ticker not in TodayRemoveList:


                coin_price = myBinance.GetCoinNowPrice(binanceX, Target_Coin_Ticker)
                
                #최소 주문 수량을 가져온다 
                minimun_amount = myBinance.GetMinimumAmount(binanceX,Target_Coin_Ticker)
                    

                amt_b = 0
                entryPrice_b = 0 
                leverage = 0
                isolated = True #격리모드인지 


                #롱잔고
                for posi in balance['info']['positions']:
                    if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'LONG':
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

                if abs(amt_b) == 0:
                    
                        
                    Rate = 1.0

                    BuyMoney = InvestCoinMoney * Rate

                    #투자금 제한!
                    if BuyMoney > stock_data['value_ma'].values[0] / 2000:
                        BuyMoney = stock_data['value_ma'].values[0] / 2000

                    if BuyMoney < 10:
                        BuyMoney = 10

                    
                    Buy_Amt = float(binanceX.amount_to_precision(Target_Coin_Ticker, myBinance.GetAmount(BuyMoney,coin_price,1.0)))  * set_leverage 

                

                    #잔고 데이타 가져오기 
                    balance = binanceX.fetch_balance(params={"type": "future"})
                    time.sleep(0.1)
                    
                    
                    #USDT 잔고를 가져온다
                    usdt = float(balance['USDT']['free'])
                    print("# Remain USDT :", usdt)
                    time.sleep(0.04)
                                
                    if BuyMoney > usdt:
                        BuyMoney = usdt
                        
                    Buy_Amt = float(binanceX.amount_to_precision(Target_Coin_Ticker, myBinance.GetAmount(BuyMoney,coin_price,1.0)))  * set_leverage 
                    
                    
                    if Buy_Amt < minimun_amount:
                        Buy_Amt = minimun_amount
                        
    
                    try:
                        
                        params = {
                            'positionSide': 'LONG'
                        }
                        data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', Buy_Amt, None, params)
                        

                        #보유 날자를 초기화
                        CoinHasCountDict[ticker] = 0
                        #파일에 저장
                        with open(CoinHasCount_file_path, 'w') as outfile:
                            json.dump(CoinHasCountDict, outfile)
                        
                    except Exception as e:
                        print("error:", e)

                        msg = ticker + " 바이낸스 할트 투자 봇 : 포지션 잡기 실패! " + str(e)
                        print(msg)
                        line_alert.SendMessage(msg)


                    msg = ticker + " 바이낸스 할트  투자 봇 : 조건 만족 하여 롱 포지션!!"
                    print(msg)
                    line_alert.SendMessage(msg)

                    AltInvestList.append(ticker)

                    #파일에 저장
                    with open(invest_file_path, 'w') as outfile:
                        json.dump(AltInvestList, outfile)



        print(CheckMsg)
        line_alert.SendMessage(CheckMsg)


    #체크 날짜가 다르다면 맨 처음이거나 날이 바뀐것이다!!
    DateDateTodayDict['date'] = day_n
    #파일에 저장
    with open(today_file_path, 'w') as outfile:
        json.dump(DateDateTodayDict, outfile)


    msg = " 바이낸스 할트 투자 봇 : 오늘 로직 끝!!"
    print(msg)
    line_alert.SendMessage(msg)




else:
    print("오늘은 이미 바이낸스 할트 봇 로직이 끝났어요!!")

