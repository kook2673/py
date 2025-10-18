#-*-coding:utf-8 -*-
'''

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

바이낸스 ccxt 버전
pip3 install --upgrade ccxt==4.2.19
이렇게 버전을 맞춰주세요!

봇은 헤지모드에서 동작합니다. 꼭! 헤지 모드로 바꿔주세요!
https://blog.naver.com/zacra/222662884649

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

백테스팅은 내PC에서 해야 서버 자원을 아끼고 투자 성과 그래프도 확인할 수 있습니다!
이 포스팅을 정독하시고 다양한 기간으로 백테스팅 해보세요!!!
https://blog.naver.com/zacra/223180500307

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$



관련 포스팅
https://blog.naver.com/zacra/223270069010


위 포스팅을 꼭 참고하세요!!!

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

import datetime
import matplotlib.pyplot as plt


#분봉/일봉 캔들 정보를 가져온다 시작점을 정의하는 함수로 변경!
def GetOhlcv2(binance, Ticker, period, year=2020, month=1, day=1, hour=0, minute=0):
    date_start = datetime.datetime(year, month, day, hour, minute)
    date_start_ms = int(date_start.timestamp() * 1000)

    final_list = []

    # OHLCV 데이터를 최대 한도(1000)만큼의 청크로 가져옵니다.
    while True:
        # OHLCV 데이터를 가져옵니다.
        ohlcv_data = binance.fetch_ohlcv(Ticker, period, since=date_start_ms)

        # 데이터가 없으면 루프를 중단합니다.
        if not ohlcv_data:
            break

        # 가져온 데이터를 최종 리스트에 추가합니다.
        final_list.extend(ohlcv_data)

        # 다음 가져오기를 위해 시작 날짜를 업데이트합니다.
        date_start = datetime.datetime.utcfromtimestamp(ohlcv_data[-1][0] / 1000)
        date_start_ms = ohlcv_data[-1][0] + (ohlcv_data[1][0] - ohlcv_data[0][0])

        print("Get Data...",str(date_start_ms))
        # 요청 간의 짧은 시간 대기를 위해 sleep을 포함합니다.
        time.sleep(0.2)

    # 최종 리스트를 DataFrame으로 변환합니다.
    df = pd.DataFrame(final_list, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
    df.set_index('datetime', inplace=True)
    
    return df



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


balance = binanceX.fetch_balance(params={"type": "future"})
time.sleep(0.1)



#테스트할 코인 리스트
InvestCoinList = ['MEME/USDT','ORDI/USDT','AAVE/USDT','GAS/USDT','CAKE/USDT']

InvestTotalMoney = 1000



fee = 0.0005 #수수료+슬리피지를 포지션 잡을때 마다 0.05%로 세팅!

#기준 간격 몇 개의 캔들로 정할지..
target_period = 3

#돌파 기준 몇 개의 캔들로 정할지..
dolpa_period = 2

#익손절 설정 변수
GetRate = 3.0
CutRate = 1.5



ResultList = list()

for coin_ticker in InvestCoinList:


    print("\n----coin_ticker: ", coin_ticker)

    #해당 코인 가격을 가져온다.
    coin_price = myBinance.GetCoinNowPrice(binanceX, coin_ticker)

    InvestMoney = InvestTotalMoney / len(InvestCoinList) #테스트 총 금액을 종목 수로 나눠서 각 할당 투자금을 계산한다!

    print(coin_ticker, " 종목당 할당 투자금:", InvestMoney)

    #LongInvestMoney = InvestMoney

    #롱과 숏 절반씩!
    LongInvestMoney = InvestMoney / 2.0  #롱
    ShortInvestMoney = InvestMoney / 2.0 #숏


    #일봉 정보를 가지고 온다!
    #df = myBinance.GetOhlcv(binanceX,coin_ticker, '5m') #1m/3m/5m/15m/30m/1h/4h/1d
    df = GetOhlcv2(binanceX,coin_ticker, '5m' ,2023, 11, 1, 0, 0) #1m/3m/5m/15m/30m/1h/4h/1d

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
    df['rsi_ma'] = df['rsi'].rolling(20).mean()
 
    
    ############# 이동평균선! ###############
    df['3ma'] = df['close'].rolling(3).mean()
    df['5ma'] = df['close'].rolling(5).mean()
    df['10ma'] = df['close'].rolling(10).mean()
    df['20ma'] = df['close'].rolling(20).mean()

    ########################################

    



    df.dropna(inplace=True) #데이터 없는건 날린다!
    pprint.pprint(df)


    IsBuy = False #롱 포지션 여부
    BUY_PRICE = 0  #매수한 가격! 
    IsDolpaLong = False


    LongTryCnt = 0      #매매횟수
    LongSuccesCnt = 0   #익절 숫자
    LongFailCnt = 0     #손절 숫자


    IsSell = False #숏 포지션 여부
    SELL_PRICE = 0  #매수한 가격! 
    IsDolpaShort = False

    ShortTryCnt = 0      #매매횟수
    ShortSuccesCnt = 0   #익절 숫자
    ShortFailCnt = 0     #손절 숫자


    #df = df[:len(df)-100] #최근 100거래일을 빼고 싶을 때




    TotalMoneyList = list()

  
    TakeProfit = 0
    StopLossProfit = 0


    GapRateL = 0
    GapRateS = 0



    LongStopPrice = 0
    ShortStopPrice = 0



    for i in range(len(df)):
        

        IsCutShort = False
        IsCutLong = False


        NowOpenPrice = df['open'].iloc[i]  
        PrevOpenPrice = df['open'].iloc[i-1]  

        IsCloseLongNow = False
        
        if IsBuy == True:

            TakeProfit = GapRateL*GetRate
            StopLossProfit = GapRateL*CutRate

            TakePrice = BUY_PRICE * (1.0 + TakeProfit) #익절가격
            LongStopPrice = BUY_PRICE * (1.0 - StopLossProfit) 

 
            
            CUT_PRICE = NowOpenPrice


            #진입(매수)가격 대비 변동률
            Rate = (CUT_PRICE - BUY_PRICE) / BUY_PRICE

            IsCut = False
            IsGet = False


            if LongStopPrice >= df['low'].iloc[i]:
                CUT_PRICE = LongStopPrice
                IsCut = True

            if TakePrice <= df['high'].iloc[i]:
                CUT_PRICE = TakePrice
                IsGet = True

    
            

            #진입(매수)가격 대비 변동률
            Rate = (CUT_PRICE - BUY_PRICE) / BUY_PRICE


            if IsDolpaLong == True:
                IsDolpaLong = False
                LongInvestMoney = LongInvestMoney * (1.0 + (((CUT_PRICE - BUY_PRICE) / BUY_PRICE) ))

            else:
                LongInvestMoney = LongInvestMoney * (1.0 + (((CUT_PRICE - PrevOpenPrice) / PrevOpenPrice) ))


            if IsCut == True:

                RevenueRate = (Rate - fee)*100.0 #수익률 계산

                LongInvestMoney = LongInvestMoney * (1.0 - fee) #수수료 및 세금, 슬리피지 반영!

                print(coin_ticker ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 롱 포지션 종료!  수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:", round(LongInvestMoney + ShortInvestMoney,2) , " CUT_PRICE:", CUT_PRICE, " NowOpenPrice", df['open'].iloc[i])


                LongTryCnt += 1
                LongFailCnt += 1

                IsBuy = False 
                IsCutLong = True
                IsCloseLongNow = True
            else:

                if IsGet == True:

                    RevenueRate = (Rate - fee)*100.0 #수익률 계산

                    LongInvestMoney = LongInvestMoney * (1.0 - fee) #수수료 및 세금, 슬리피지 반영!

                    print(coin_ticker ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 롱 포지션 종료!  수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:", round(LongInvestMoney + ShortInvestMoney,2) , " CUT_PRICE:", CUT_PRICE, " NowOpenPrice", df['open'].iloc[i])


                    LongTryCnt += 1
                    LongSuccesCnt += 1

                    IsBuy = False 
                    IsCloseLongNow = True


        

        if IsBuy == False and IsSell == False and IsCloseLongNow == False:


            if i >= max(target_period,dolpa_period): 


                ################################################
                #기준 간격 설정!! target_period개 만큼의 캔들로 계산..
                high_list = list()
                low_list = list()

                for index in range(i-1,i-(target_period+1),-1):
                    high_list.append(df['high'].iloc[index])
                    low_list.append(df['low'].iloc[index])

                high_price = float(max(high_list))
                low_price =  float(min(low_list))


                GapRateL = ((high_price / low_price) - 1.0) 

                ################################################


                ################################################
                #돌파 캔들을 체크해 돌파 가격 설정!!! dolpa_period개 만큼의 캔들로 계산

                high_list = list()
                for index in range(i-1,i-(dolpa_period+1),-1):
                    high_list.append(df['high'].iloc[index])


                high_price = float(max(high_list))
                ################################################




                TargetPrice = high_price



                if  ((df['high'].iloc[i] >= TargetPrice and TargetPrice > NowOpenPrice) or TargetPrice < NowOpenPrice) and ((df['rsi_ma'].iloc[i-2] < df['rsi_ma'].iloc[i-1]) and  df['rsi_ma'].iloc[i] < df['rsi'].iloc[i-1]) :


                    if GapRateL > 0.003:

                        if GapRateL > 0.01:
                            GapRateL = 0.01

                        if TargetPrice < NowOpenPrice:
    
                            BUY_PRICE = NowOpenPrice #매수가격 지정!
                            IsDolpaLong = False
                        else:
    
                            BUY_PRICE = TargetPrice #매수가격 지정!
                            IsDolpaLong = True

                        LongInvestMoney = LongInvestMoney * (1.0 - fee) #수수료 및 세금, 슬리피지 반영!

                        print(coin_ticker ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 롱 포지션 시작! ,종목 잔고:", round(LongInvestMoney + ShortInvestMoney,2), " TargetPrice", TargetPrice, " NowOpenPrice: ", NowOpenPrice  )

                        IsBuy = True 





        #'''
        ######################################################################################
        ######################################################################################
        #################################################################
        
        IsCloseShortNow = False
        
        if IsSell == True:

            TakeProfit = GapRateS*GetRate
            StopLossProfit = GapRateS*CutRate

            TakePrice = SELL_PRICE * (1.0 - TakeProfit) #익절가격
            ShortStopPrice = SELL_PRICE * (1.0 + StopLossProfit) 


            CUT_PRICE = NowOpenPrice

            #진입(매수)가격 대비 변동률
            Rate = (SELL_PRICE - CUT_PRICE) / SELL_PRICE

            IsCut = False
            IsGet = False

            if TakePrice >= df['low'].iloc[i]:
                CUT_PRICE = TakePrice
                IsGet = True


            if ShortStopPrice <= df['high'].iloc[i]:
                CUT_PRICE = ShortStopPrice
                IsCut = True



            #진입(매수)가격 대비 변동률
            Rate = (SELL_PRICE - CUT_PRICE) / SELL_PRICE


            if IsDolpaShort == True:
                IsDolpaShort = False
                #투자중이면 매일매일 수익률 반영!
                ShortInvestMoney = ShortInvestMoney * (1.0 + (((SELL_PRICE - CUT_PRICE) / SELL_PRICE)))

            else:
                #투자중이면 매일매일 수익률 반영!
                ShortInvestMoney = ShortInvestMoney * (1.0 + (((PrevOpenPrice - CUT_PRICE) / PrevOpenPrice)))




            if IsCut == True: 
                RevenueRate = (Rate - fee)*100.0 #수익률 계산

                ShortInvestMoney = ShortInvestMoney * (1.0 - fee) #수수료 및 세금, 슬리피지 반영!

                print(coin_ticker ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 숏 포지션 종료!  수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:", round(LongInvestMoney + ShortInvestMoney,2) , " CUT_PRICE:", CUT_PRICE, " NowOpenPrice", df['open'].iloc[i])


                ShortTryCnt += 1
                ShortFailCnt += 1

                IsSell = False 
                IsCutShort = True
                IsCloseShortNow = True

                
            else:
                if IsGet == True:
                    RevenueRate = (Rate - fee)*100.0 #수익률 계산

                    ShortInvestMoney = ShortInvestMoney * (1.0 - fee) #수수료 및 세금, 슬리피지 반영!

                    print(coin_ticker ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 숏 포지션 종료!  수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:", round(LongInvestMoney + ShortInvestMoney,2)  , " CUT_PRICE:", CUT_PRICE, " NowOpenPrice", df['open'].iloc[i])


                    ShortTryCnt += 1
                    ShortSuccesCnt += 1

                    IsSell = False 
                    IsCloseShortNow = True



        if IsSell == False and IsBuy == False and IsCloseShortNow == False:

            if i >= max(target_period,dolpa_period) :

                ################################################
                #기준 간격 설정!! target_period개 만큼의 캔들로 계산..
                high_list = list()
                low_list = list()

                for index in range(i-1,i-(target_period+1),-1):
                    high_list.append(df['high'].iloc[index])
                    low_list.append(df['low'].iloc[index])

                high_price = float(max(high_list))
                low_price =  float(min(low_list))


                GapRateS = ((high_price / low_price) - 1.0) 
                ################################################


                ################################################
                #돌파 캔들을 체크해 돌파 가격 설정!!! dolpa_period개 만큼의 캔들로 계산
                low_list = list()
                for index in range(i-1,i-(dolpa_period+1),-1):
                    low_list.append(df['low'].iloc[index])

                low_price =  float(min(low_list))
                ################################################



                TargetPrice = low_price

                if   ((df['low'].iloc[i] <= TargetPrice and TargetPrice < NowOpenPrice) or TargetPrice > NowOpenPrice) and df['rsi_ma'].iloc[i-2] > df['rsi_ma'].iloc[i-1] and  df['rsi_ma'].iloc[i] > df['rsi'].iloc[i-1]:
                    
                    
                    if GapRateS > 0.003:

                        if GapRateS > 0.01:
                            GapRateS = 0.01


                        if TargetPrice > NowOpenPrice:
    
                            SELL_PRICE = NowOpenPrice #매수가격 지정!
                            IsDolpaShort = False
                        else:

                            SELL_PRICE = TargetPrice #매수가격 지정!
                            IsDolpaShort = True


                        ShortInvestMoney = ShortInvestMoney * (1.0 - fee) #수수료 및 세금, 슬리피지 반영!

                        print(coin_ticker ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 숏 포지션 시작! ,종목 잔고:", round(LongInvestMoney + ShortInvestMoney,2) , " TargetPrice", TargetPrice, " NowOpenPrice: ", NowOpenPrice )

                        IsSell = True 


        #'''
        #################################################################
        ######################################################################################
        ######################################################################################


        TotalMoneyList.append(LongInvestMoney + ShortInvestMoney)
    
    #####################################################
    #####################################################
    #####################################################
    #'''



    #결과 정리 및 데이터 만들기!!
    if len(TotalMoneyList) > 0:

        resultData = dict()

        
        resultData['Ticker'] = coin_ticker


        result_df = pd.DataFrame({ "Total_Money" : TotalMoneyList}, index = df.index)

        result_df['Ror'] = result_df['Total_Money'].pct_change() + 1
        result_df['Cum_Ror'] = result_df['Ror'].cumprod()

        result_df['Highwatermark'] =  result_df['Cum_Ror'].cummax()
        result_df['Drawdown'] = (result_df['Cum_Ror'] / result_df['Highwatermark']) - 1
        result_df['MaxDrawdown'] = result_df['Drawdown'].cummin()

        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        pprint.pprint(result_df)
        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

        resultData['DateStr'] = str(result_df.iloc[0].name) + " ~ " + str(result_df.iloc[-1].name)

        resultData['OriMoney'] = result_df['Total_Money'].iloc[0]
        resultData['FinalMoney'] = result_df['Total_Money'].iloc[-1]
        resultData['OriRevenueHold'] =  (df['open'].iloc[-1]/df['open'].iloc[0] - 1.0) * 100.0 
        resultData['RevenueRate'] = ((result_df['Cum_Ror'].iloc[-1] -1.0)* 100.0)
        resultData['MDD'] = result_df['MaxDrawdown'].min() * 100.0

        resultData['LongTryCnt'] = LongTryCnt
        resultData['LongSuccesCnt'] = LongSuccesCnt
        resultData['LongFailCnt'] = LongFailCnt

        resultData['ShortTryCnt'] = ShortTryCnt
        resultData['ShortSuccesCnt'] = ShortSuccesCnt
        resultData['ShortFailCnt'] = ShortFailCnt


        ResultList.append(resultData)

        result_df.index = pd.to_datetime(result_df.index)


        # Create a figure with subplots for the two charts
        fig, axs = plt.subplots(2, 1, figsize=(10, 10))

        # Plot the return chart
        axs[0].plot(result_df['Cum_Ror'] * 100, label='Strategy')
        axs[0].set_ylabel('Cumulative Return (%)')
        axs[0].set_title(coin_ticker + ' Return Comparison Chart')
        axs[0].legend()

        # Plot the MDD and DD chart on the same graph
        axs[1].plot(result_df.index, result_df['MaxDrawdown'] * 100, label='MDD')
        axs[1].plot(result_df.index, result_df['Drawdown'] * 100, label='Drawdown')
        axs[1].set_ylabel('Drawdown (%)')
        axs[1].set_title(coin_ticker + ' Drawdown Comparison Chart')
        axs[1].legend()

        # Show the plot
        plt.tight_layout()
        plt.show()
            

        for idx, row in result_df.iterrows():
            print(idx, " " , row['Total_Money'], " "  , row['Cum_Ror'])
            



#데이터를 보기좋게 프린트 해주는 로직!
print("\n\n--------------------")
TotalOri = 0
TotalFinal = 0
TotalHoldRevenue = 0
TotalMDD= 0

InvestCnt = float(len(ResultList))

for result in ResultList:

    print("--->>>",result['DateStr'],"<<<---")
    print(result['Ticker'] )
    print("최초 금액: ", round(result['OriMoney'],2) , " 최종 금액: ", round(result['FinalMoney'],2))
    print("수익률:", round(result['RevenueRate'],2) , "%")
    print("단순 보유 수익률:", round(result['OriRevenueHold'],2) , "%")
    print("MDD:", round(result['MDD'],2) , "%")

    if result['LongTryCnt'] > 0:
        print("롱 성공:", result['LongSuccesCnt'] , " 실패:", result['LongFailCnt']," -> 승률: ", round(result['LongSuccesCnt']/result['LongTryCnt'] * 100.0,2) ," %")


    if result['ShortTryCnt'] > 0:
        print("숏 성공:", result['ShortSuccesCnt'] , " 실패:", result['ShortFailCnt']," -> 승률: ", round(result['ShortSuccesCnt']/result['ShortTryCnt'] * 100.0,2) ," %")


    TotalOri += result['OriMoney']
    TotalFinal += result['FinalMoney']

    TotalHoldRevenue += result['OriRevenueHold']
    TotalMDD += result['MDD']

    print("\n--------------------\n")

if TotalOri > 0:
    print("####################################")
    print("---------- 총 결과 ----------")
    print("최초 금액:", TotalOri , " 최종 금액:", TotalFinal, "\n수익률:", round(((TotalFinal - TotalOri) / TotalOri) * 100,2) ,"% (단순보유수익률:" ,round(TotalHoldRevenue/InvestCnt,2) ,"%) 평균 MDD:",  round(TotalMDD/InvestCnt,2),"%")
    print("------------------------------")
    print("####################################")






