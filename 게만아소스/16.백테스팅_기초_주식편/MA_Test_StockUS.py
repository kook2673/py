'''





$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

백테스팅은 내PC에서 해야 서버 자원을 아끼고 투자 성과 그래프도 확인할 수 있습니다!
이 포스팅을 정독하시고 다양한 기간으로 백테스팅 해보세요!!!
https://blog.naver.com/zacra/223180500307

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$




관련 포스팅

골든크로스 때 매수하면 무조건 수익?? 주식 자동매매 백테스팅으로 시간과 돈 아끼기!
https://blog.naver.com/zacra/223033891384


위 포스팅을 꼭 참고하세요!!!

포스팅과 영상과는 다르게 시가'open'이 아니라 'close' 종가로 기본 세팅을 했습니다.
액면분할등의 종목은 수정주가를 반영해야 되는데 이게 보통 데이터 뽑을 때 종가에만 반영이 되서 
주식의 경우는 종가 기준으로 테스트한다고 디폴트 세팅을 했습니다!!


물론 액면분할 하지 않은 종목이나 테스트 기간에 액면분할 등의 이벤트가 없다면 당연히 시가'open'으로 테스트해도 됩니다!


📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제공된 전략은 학습 및 테스트 목적으로 구성된 예시 코드이며
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.
   

주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!


'''
import KIS_Common as Common

import pandas as pd
import pprint
import matplotlib.pyplot as plt

#계좌 선택.. "VIRTUAL" 는 모의 계좌!
Common.SetChangeMode("VIRTUAL") #REAL or VIRTUAL

##################################################################
InvestStockList = [] #테스트할 종목을 아래 처럼 직접 판단히여 넣으세요!
#InvestStockList = ['AAPL','GOOG','TSLA','MSFT'] #예시 종목
##################################################################


#이렇게 직접 금액을 지정해도 된다!!
TotalMoney = 10000

print("테스트하는 총 금액: $", round(TotalMoney))



ResultList = list()

for stock_code in InvestStockList:

    print("\n----stock_code: ", stock_code)


    InvestMoney = TotalMoney / len(InvestStockList) #테스트 총 금액을 종목 수로 나눠서 각 할당 투자금을 계산한다!

    print(stock_code, " 종목당 할당 투자금:", InvestMoney)


    #일봉 정보를 가지고 온다!
    df = Common.GetOhlcv("US",stock_code, 310) #310이 얼추 1년...  500, 1000등의 숫자를 넣어 테스트 해보자!

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

    
    ############# 이동평균선! ###############
    df['3ma'] = df['close'].rolling(3).mean()
    df['5ma'] = df['close'].rolling(5).mean()
    df['10ma'] = df['close'].rolling(10).mean()
    df['20ma'] = df['close'].rolling(20).mean()
    df['60ma'] = df['close'].rolling(60).mean()
    ########################################

    df.dropna(inplace=True) #데이터 없는건 날린다!
    pprint.pprint(df)


    IsBuy = False #매수 했는지 여부
    BUY_PRICE = 0  #매수한 금액! 

    TryCnt = 0      #매매횟수
    SuccesCnt = 0   #익절 숫자
    FailCnt = 0     #손절 숫자


    fee = 0.0015 #수수료+세금+슬리피지를 매수매도마다 0.15%로 세팅!


    TotlMoneyList = list()

    #'''
    #####################################################
    ##########골든 크로스에서 매수~ 데드크로스에서 매도~!##########
    #####################################################
    for i in range(len(df)):


        NowOpenPrice = df['close'].iloc[i]    #원래 시가 'open'이었지만 종가'close'로 변경해놨어요 이유는 맨 윗부분의 글을 참고하세요!
        PrevOpenPrice = df['close'].iloc[i-1]  #원래 시가 'open'이었지만 종가'close'로 변경해놨어요 이유는 맨 윗부분의 글을 참고하세요!
        
        
        
        if IsBuy == True:

            #투자중이면 매일매일 수익률 반영!
            InvestMoney = InvestMoney * (1.0 + ((NowOpenPrice - PrevOpenPrice) / PrevOpenPrice))
                        
            
            if df['5ma'].iloc[i-2] > df['20ma'].iloc[i-2] and df['5ma'].iloc[i-1] < df['20ma'].iloc[i-1]:  #데드 크로스!


                #진입(매수)가격 대비 변동률
                Rate = (NowOpenPrice - BUY_PRICE) / BUY_PRICE

                RevenueRate = (Rate - fee)*100.0 #수익률 계산

                InvestMoney = InvestMoney * (1.0 - fee)  #수수료 및 세금, 슬리피지 반영!

                print(stock_code ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 매도!  수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:", round(InvestMoney,2)  , " ", df['open'].iloc[i])
                print("\n\n")


                TryCnt += 1

                if RevenueRate > 0: #수익률이 0보다 크다면 익절한 셈이다!
                    SuccesCnt += 1
                else:
                    FailCnt += 1


                IsBuy = False #매도했다

        if IsBuy == False:

        
            if i >= 2 and df['5ma'].iloc[i-2] < df['20ma'].iloc[i-2] and df['5ma'].iloc[i-1] > df['20ma'].iloc[i-1]:  #골든 크로스!

                BUY_PRICE = NowOpenPrice 

                InvestMoney = InvestMoney * (1.0 - fee)  #수수료 및 세금, 슬리피지 반영!

                print(stock_code ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 매수! ,종목 잔고:", round(InvestMoney,2) , " ", df['open'].iloc[i])
                IsBuy = True #매수했다

        
        TotlMoneyList.append(InvestMoney)

    #####################################################
    #####################################################
    #####################################################
    #'''
    
    '''
    #####################################################
    ##########골든 크로스에서 매수~ 10% 위 익절  3% 아래 손절룰!##########
    #####################################################
    
    TakeProfit = 0.10   #익절 목표
    StopLossProfit = 0.03  #손절 목표

    for i in range(len(df)):
        
        NowOpenPrice = df['close'].iloc[i]     #원래 시가 'open'이었지만 종가'close'로 변경해놨어요 이유는 맨 윗부분의 글을 참고하세요!
        PrevOpenPrice = df['close'].iloc[i-1]   #원래 시가 'open'이었지만 종가'close'로 변경해놨어요 이유는 맨 윗부분의 글을 참고하세요!

        if IsBuy == True:

            #투자중이면 매일매일 수익률 반영!
            InvestMoney = InvestMoney * (1.0 + ((NowOpenPrice - PrevOpenPrice) / PrevOpenPrice))

            #진입(매수)가격 대비 변동률
            Rate = (NowOpenPrice - BUY_PRICE) / BUY_PRICE

            TakePrice = BUY_PRICE * (1.0 + TakeProfit) #익절가격
            StopPrice = BUY_PRICE * (1.0 - StopLossProfit) #손절가격
            

            #손절가 도달! 손절 처리!
            if NowOpenPrice <= StopPrice: 

                RevenueRate = (Rate - fee)*100.0 #수익률 계산

                InvestMoney = InvestMoney * (1.0 - fee) #수수료 및 세금, 슬리피지 반영!

                print(stock_code ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 매도!  수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:", round(InvestMoney,2) , " ", df['open'].iloc[i])
                print("\n\n")


                TryCnt += 1
                FailCnt += 1

                IsBuy = False #매도했다

            else:

                #수익가 도달! 익절 처리!!
                if NowOpenPrice >= TakePrice: 

                    RevenueRate = (Rate - fee)*100.0 #수익률 계산

                    InvestMoney = InvestMoney * (1.0 - fee) #수수료 및 세금, 슬리피지 반영!

                    print(stock_code ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 매도!  수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:", round(InvestMoney,2)  , " ", df['open'].iloc[i])
                    print("\n\n")


                    TryCnt += 1
                    SuccesCnt += 1

                    IsBuy = False #매도했다

        



        if IsBuy == False:

            #골든 크로스!
            if i >= 2 and df['5ma'].iloc[i-2] < df['20ma'].iloc[i-2] and df['5ma'].iloc[i-1] > df['20ma'].iloc[i-1]: 

                BUY_PRICE = NowOpenPrice #매수가격 지정!

                InvestMoney = InvestMoney * (1.0 - fee) #수수료 및 세금, 슬리피지 반영!

                print(stock_code ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 매수! ,종목 잔고:", round(InvestMoney,2) )

                IsBuy = True #매수했다!!


        TotlMoneyList.append(InvestMoney)
    
    #####################################################
    #####################################################
    #####################################################
    '''



    #결과 정리 및 데이터 만들기!!
    if len(TotlMoneyList) > 0:

        resultData = dict()

        
        resultData['Ticker'] = stock_code


        result_df = pd.DataFrame({ "Total_Money" : TotlMoneyList}, index = df.index)

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

        resultData['TryCnt'] = TryCnt
        resultData['SuccesCnt'] = SuccesCnt
        resultData['FailCnt'] = FailCnt

        
        ResultList.append(resultData)

        result_df.index = pd.to_datetime(result_df.index)

        # Create a figure with subplots for the two charts
        fig, axs = plt.subplots(2, 1, figsize=(10, 10))

        # Plot the return chart
        axs[0].plot(result_df['Cum_Ror'] * 100, label='Strategy')
        axs[0].set_ylabel('Cumulative Return (%)')
        axs[0].set_title(stock_code + ' Return Comparison Chart')
        axs[0].legend()

        # Plot the MDD and DD chart on the same graph
        axs[1].plot(result_df.index, result_df['MaxDrawdown'] * 100, label='MDD')
        axs[1].plot(result_df.index, result_df['Drawdown'] * 100, label='Drawdown')
        axs[1].set_ylabel('Drawdown (%)')
        axs[1].set_title(stock_code + ' Drawdown Comparison Chart')
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

    print("--->>>",result['DateStr'].replace("00:00:00",""),"<<<---")
    print(result['Ticker'] )
    print("최초 금액: $", round(result['OriMoney'],2) , " 최종 금액: $", round(result['FinalMoney'],2))
    print("수익률:", round(result['RevenueRate'],2) , "%")
    print("단순 보유 수익률:", round(result['OriRevenueHold'],2) , "%")
    print("MDD:", round(result['MDD'],2) , "%")

    if result['TryCnt'] > 0:
        print("성공:", result['SuccesCnt'] , " 실패:", result['FailCnt']," -> 승률: ", round(result['SuccesCnt']/result['TryCnt'] * 100.0,2) ," %")

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


