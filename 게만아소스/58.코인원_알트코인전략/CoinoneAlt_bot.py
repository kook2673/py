#-*-coding:utf-8 -*-
'''
 
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

해당 컨텐츠는 제가 직접 투자 하기 위해 이 전략을 추가 개선해서 더 좋은 성과를 보여주는 개인 전략이 존재합니다. 

게만아 추가 개선 개인 전략들..
https://blog.naver.com/zacra/223196497504

관심 있으신 분은 위 포스팅을 참고하세요!

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$



관련 포스팅
https://blog.naver.com/zacra/223570808965

위 포스팅을 꼭 참고하세요!!!

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.

주식/코인 파이썬 매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!


 
'''


import myCoinone
import time

import pandas as pd
import json
import line_alert
import pprint





#시간 정보를 읽는다
time_info = time.gmtime()

day_n = time_info.tm_mday



#오늘 로직이 진행되었는지 날짜 저장 관리 하는 파일
DateDateTodayDict = dict()

#파일 경로입니다.
today_file_path = "/var/autobot/CoinoneHaltInvestToday.json"
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
MaxCoinCnt = 5 #투자 코인 개수!!!


#사용 이동평균선!
long_ma1 = 5
long_ma2 = 50

#최소 매수 금액
minmunMoney = 10000

OutCoinList = ['USDT','BTC','ETH']
    
############################################################
############################################################

if DateDateTodayDict['date'] != day_n:
    


    print("15초 정도 쉽니다!")
    time.sleep(15.0) #안전전략등 다른 봇과 돌릴 경우.



    #내가 가진 잔고 데이터를 다 가져온다.
    balances = myCoinone.GetBalances()

    TotalMoney = myCoinone.GetTotalMoney(balances) #총 원금
    TotalRealMoney = myCoinone.GetTotalRealMoney(balances) #총 평가금액

    print("TotalMoney", TotalMoney)
    print("TotalRealMoney", TotalRealMoney)
    
    
    
    ##########################################################################
    InvestTotalMoney = TotalMoney * InvestRate #총 투자원금+ 남은 원화 기준으로 투자!!!!
    ##########################################################################

    print("InvestTotalMoney", InvestTotalMoney)

    InvestCoinMoney = InvestTotalMoney / (MaxCoinCnt) #코인당 투자금!
    

    
    Tickers = myCoinone.GetTickers()
            

    #투자한 코인을 저장할 리스트!!
    AltInvestList = list()

    #파일 경로입니다.
    invest_file_path = "/var/autobot/CoinoneHaltInvestList.json"
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
    CoinHasCount_file_path = "/var/autobot/CoinoneHaltHasCoinCount.json"
    try:
        #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
        with open(CoinHasCount_file_path, 'r') as json_file:
            CoinHasCountDict = json.load(json_file)

    except Exception as e:
        #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
        print("..")



            
    stock_df_list = []

    for ticker in Tickers:

        try:

   
            print("----->", ticker ,"<-----")
            df = myCoinone.GetOhlcv(ticker,'1d',700)

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
            df['prevOpen'] = df['open'].shift(1)
            
            df['prevClose'] = df['close'].shift(1)
            df['prevClose2'] = df['close'].shift(2)

            df['prevChange'] = (df['prevClose'] - df['prevClose2']) / df['prevClose2']

            df['value_ma'] = df['value'].rolling(window=10).mean().shift(1)


            df['prevCloseW'] = df['close'].shift(7)
            df['prevChangeW'] = (df['prevClose'] - df['prevCloseW']) / df['prevCloseW']
                
                

            #이렇게 3일선 부터 200일선을 자동으로 만들 수 있다!
            '''
            for ma in range(3,201):
                df['ma'+str(ma)+'_before'] = df['close'].rolling(ma).mean().shift(1)
                df['ma'+str(ma)+'_before2'] = df['close'].rolling(ma).mean().shift(2)
            '''
            ma_dfs = []

            # 이동 평균 계산
            for ma in range(3, 201):
                ma_df = df['close'].rolling(ma).mean().rename('ma'+str(ma)+'_before').shift(1)
                ma_dfs.append(ma_df)
                
                ma_df = df['close'].rolling(ma).mean().rename('ma'+str(ma)+'_before2').shift(2)
                ma_dfs.append(ma_df)
            # 이동 평균 데이터 프레임을 하나로 결합
            ma_df_combined = pd.concat(ma_dfs, axis=1)

            # 원본 데이터 프레임과 결합
            df = pd.concat([df, ma_df_combined], axis=1)

            
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


    btc_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == 'BTC')]

    pick_coins_top = combined_df.loc[combined_df.index == date].groupby('ticker')['value_ma'].max().nlargest(20)


    ###################################################
    #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 시작<--
    #pick_coins_top_change = combined_df.loc[combined_df.index == date].groupby('ticker')['prevChangeW'].max().nlargest(MaxCoinCnt)
    #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 끝 <--
    ###################################################
    
    ###################################################
    #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 시작!<--
    #'''
    dic_coin_change = dict()

    for ticker in pick_coins_top.index:
        try:
            
                
            if ticker in OutCoinList: 
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
    #'''
    #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 끝 <--

    TodayRemoveList = list()

    items_to_remove = list()

    #투자중 코인!
    for coin_ticker in AltInvestList:
        


        #잔고가 있는 경우.
        if myCoinone.IsHasCoin(balances,coin_ticker) == True and myCoinone.GetCoinNowRealMoney(balances,coin_ticker) >= minmunMoney: 
            print("")

            #수익금과 수익률을 구한다!
            revenue_data = myCoinone.GetRevenueMoneyAndRate(balances,coin_ticker)

            msg = coin_ticker + "현재 수익률 : 약 " + str(round(revenue_data['revenue_rate'],2)) + "% 수익금 : 약" + str(format(round(revenue_data['revenue_money']), ',')) + "원"
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
                if CoinHasCountDict[coin_ticker] >= 5:
                    
                    IsTopIn = False
                    ###################################################
                    #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 시작<--
                    '''
                    for ticker_t in pick_coins_top.index:
                        
                        if ticker_t == ticker:
                            for ticker_t2 in pick_coins_top_change.index:
                            
                                if ticker_t2 == ticker_t:
                                    coin_top_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == ticker_t2)]
                                    if len(coin_top_data) == 1:
                                        IsTopIn = True
                                        break
                    '''
                    #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 끝 <--
                    ###################################################
                    
                    ###################################################
                    #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 시작!<--
                    #'''
                    if coin_ticker in pick_coins_top_change:
                        IsTopIn = True
                    #'''
                    #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 끝 <--
                    ###################################################
                    if IsTopIn == False:
                        IsSell = True
                        
                    

                if btc_data['ma120_before'].values[0]  >  btc_data['prevClose'].values[0]:
                    IsSell = True
                    
                     
   
                if ((stock_data['ma'+str(long_ma1)+'_before2'].values[0]  >  stock_data['ma'+str(long_ma1)+'_before'].values[0] and stock_data['ma'+str(long_ma1)+'_before'].values[0]  >  stock_data['prevClose'].values[0]) or (stock_data['ma'+str(long_ma2)+'_before2'].values[0]  >  stock_data['ma'+str(long_ma2)+'_before'].values[0] and stock_data['ma'+str(long_ma2)+'_before'].values[0]  >  stock_data['prevClose'].values[0])) :
                    IsSell = True



                if IsSell == True:

                    TodayRemoveList.append(coin_ticker)
                    
                    
                    AllAmt = myCoinone.GetCoinAmount(balances,coin_ticker)  #현재 수량

                    balances =  myCoinone.SellCoinMarket(coin_ticker,AllAmt) 
                                    
                    msg = coin_ticker + " 코인원 알트 투자 봇 : 조건을 불만족하여 모두 매도처리 했어요!!"
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
    #for ticker in pick_coins_top.index:
    #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 끝 <--
    ###################################################

    ###################################################
    #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 시작!<--
    for ticker in pick_coins_top_change:
    #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 끝 <--
    ###################################################

        if ticker in OutCoinList: #제외할 코인!
            continue
        
        
        CheckMsg = ticker
        
        CheckMsg += " 거래대금 & 등락률 상위 조건 만족! "
        
        IsAlReadyInvest = False
        for coin_ticker in AltInvestList:
            if ticker == coin_ticker: 
                IsAlReadyInvest = True
                break


        ###################################################
        #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 시작<--
        '''
        IsTOPInChange = False
        for ticker_t in pick_coins_top_change.index:

            if ticker_t == ticker:
                coin_top_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == ticker_t)]
                if len(coin_top_data) == 1:
                    IsTOPInChange = True
                    break
        '''
        #--> A) 거래대금 TOP 과 수익률 TOP 교집합 조합 버전 끝 <--
        ################################################### 

            
        ###################################################
        #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 시작!<--
        IsTOPInChange = True
        #--> B) 거래대금 TOP 중에서 수익률 높은거 뽑는 버전 끝 <--
        ###################################################
        



        stock_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == ticker)]

       
        #이미 투자중이 아니면서 조건 만족한 코인들
        if len(stock_data) == 1 and IsAlReadyInvest == False and IsTOPInChange == True: 

            print("--- 등락률 상위 OK..." ,ticker)


            IsBuyGo = False

            #매수 조건 체크!
            if (btc_data['ma60_before2'].values[0]  <  btc_data['ma60_before'].values[0] or btc_data['ma60_before'].values[0]  <  btc_data['prevClose'].values[0])  and (btc_data['ma120_before2'].values[0]  <  btc_data['ma120_before'].values[0] or btc_data['ma120_before'].values[0]  <  btc_data['prevClose'].values[0]) and stock_data['prevChangeW'].values[0] > 0:

                CheckMsg += " 비트코인 조건 만족! "
                #거래대금 10억 이상
                if stock_data['prevValue'].values[0] > 1000000000:  


                    CheckMsg += " 거래대금 조건 만족 "
                        
                    if stock_data['prevClose'].values[0] > stock_data['prevOpen'].values[0] and ((stock_data['ma'+str(long_ma1)+'_before2'].values[0]  <=  stock_data['ma'+str(long_ma1)+'_before'].values[0] and stock_data['ma'+str(long_ma1)+'_before'].values[0]  <=  stock_data['prevClose'].values[0]) and (stock_data['ma'+str(long_ma2)+'_before2'].values[0]  <=  stock_data['ma'+str(long_ma2)+'_before'].values[0] and stock_data['ma'+str(long_ma2)+'_before'].values[0]  <=  stock_data['prevClose'].values[0])) :
            
                        CheckMsg += " 추가 조건 만족! 모든 코인이 투자된 것이 아니라면 매수!! "
                        IsBuyGo = True



            #조건 만족하고 모든 코인이 투자된 것이 아니라면 
            if IsBuyGo == True and len(AltInvestList) < int(MaxCoinCnt) and ticker not in TodayRemoveList:


                if myCoinone.IsHasCoin(balances,ticker) == False or myCoinone.GetCoinNowRealMoney(balances,ticker) < minmunMoney: 

                    Rate = 1.0
                    BuyMoney = InvestCoinMoney * Rate

                    #투자금 제한!
                    if BuyMoney > stock_data['value_ma'].values[0] / 2000:
                        BuyMoney = stock_data['value_ma'].values[0] / 2000

                    if BuyMoney < minmunMoney:
                        BuyMoney = minmunMoney



                    #원화 잔고를 가져온다
                    won = float(myCoinone.GetCoinAmount(balances,"KRW"))
                    print("# Remain Won :", won)
                    time.sleep(0.04)
                    
                    #
                    if BuyMoney > won:
                        BuyMoney = won * 0.99 #슬리피지 및 수수료 고려

                    balances = myCoinone.BuyCoinMarket(ticker,BuyMoney)

                    msg = ticker + " 코인원 알트 투자 봇 : 조건 만족 하여 매수!!"
                    print(msg)
                    line_alert.SendMessage(msg)



                    
                    AltInvestList.append(ticker)

                    #파일에 저장
                    with open(invest_file_path, 'w') as outfile:
                        json.dump(AltInvestList, outfile)



                    CoinHasCountDict[ticker] = 0
                    #파일에 저장
                    with open(CoinHasCount_file_path, 'w') as outfile:
                        json.dump(CoinHasCountDict, outfile)
                        

        print(CheckMsg)
        line_alert.SendMessage(CheckMsg)

    #체크 날짜가 다르다면 맨 처음이거나 날이 바뀐것이다!!
    DateDateTodayDict['date'] = day_n
    #파일에 저장
    with open(today_file_path, 'w') as outfile:
        json.dump(DateDateTodayDict, outfile)


    msg = " 코인원 알트 투자 봇 : 오늘 로직 끝!!"
    print(msg)
    line_alert.SendMessage(msg)



else:
    print("오늘은 이미 코인원 알트 투자 봇 로직이 끝났어요!!")





