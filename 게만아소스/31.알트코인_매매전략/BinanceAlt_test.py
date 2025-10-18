#-*-coding:utf-8 -*-
'''

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

백테스팅은 내PC에서 해야 서버 자원을 아끼고 투자 성과 그래프도 확인할 수 있습니다!
이 포스팅을 정독하시고 다양한 기간으로 백테스팅 해보세요!!!
https://blog.naver.com/zacra/223180500307

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$



$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

해당 컨텐츠는 제가 직접 투자 하기 위해 이 전략을 추가 개선해서 더 좋은 성과를 보여주는 개인 전략이 존재합니다. 

게만아 추가 개선 개인 전략들..
https://blog.naver.com/zacra/223196497504

관심 있으신 분은 위 포스팅을 참고하세요!

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$



코드 이해하는데 도움 되는 설명 참고 영상!
https://youtu.be/IViI5gofQf4?si=Fnqm4_OmVfLnHCWD



관련 포스팅

https://blog.naver.com/zacra/223375538360

위 포스팅을 꼭 참고하세요!!!

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.

주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!

'''

import pandas as pd
import pprint

import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime



InvestTotalMoney = 100000 

combined_df = pd.read_csv('./BinanceDataAll.csv', index_col=0)

pprint.pprint(combined_df)

IsBuy = False #매수 했는지 여부
BUY_PRICE = 0  #매수한 금액! 

TryCnt = 0      #매매횟수
SuccesCnt = 0   #익절 숫자
FailCnt = 0     #손절 숫자


fee = 0.0015 #수수료+세금+슬리피지를 매수매도마다 0.15%로 세팅!
IsFirstDateSet = False
FirstDateStr = ""
FirstDateIndex = 0

ReadyCoinList = list()

NowInvestList = list()


InvestMoney = InvestTotalMoney


DivNum = 30



InvestMoneyCell = InvestMoney / (DivNum +1)

RemainInvestMoney = InvestMoney


ResultList = list()

TotalMoneyList = list()
combined_df.index = pd.DatetimeIndex(combined_df.index).strftime('%Y-%m-%d %H:%M:%S')
i = 0
# Iterate over each date
for date in combined_df.index.unique():
    

    i += 1


    #비트나 이더를 기준으로 마켓타이밍으로 테스팅을 할때 아래 코드로 당일 비트와 이더 데이터를 가져올 수 있음
    #btc_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == 'BTC/USDT:USDT')]

    #eth_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == 'ETH/USDT:USDT')]



    pick_coins_top = combined_df.loc[combined_df.index == date].groupby('ticker')['prevValue'].max().nlargest(60).nsmallest((int(DivNum))) #거래대금 상위 30개 중 하위 20개

    pick_coins_top_change = combined_df.loc[combined_df.index == date].groupby('ticker')['prevChange'].max().nlargest(60).nsmallest((int(DivNum))) #등락률 상위 30개 중 하위 20개



    items_to_remove = list()

    #투자중인 티커!!
    for investData in NowInvestList:
       # pprint.pprint(investData)

        ticker = investData['ticker'] 
        
        if investData['InvestMoney'] > 0:
            stock_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == ticker)]

            if len(stock_data) == 1:


                #if IsTOP10In == True:
                NowOpenPrice = stock_data['open'].values[0] 
                PrevOpenPrice = stock_data['prevOpen'].values[0] 

                investData['InvestMoney'] = investData['InvestMoney'] *  (1.0 + ((NowOpenPrice - PrevOpenPrice) / PrevOpenPrice))

              

                #진입(매수)가격 대비 변동률
                Rate = (NowOpenPrice - investData['BuyPrice']) / investData['BuyPrice']


                RevenueRate = (Rate - fee)*100.0 #수익률 계산



                IsSell = False

                #매도 조건!!!!
                if stock_data['ma5_before2'].values[0] > stock_data['ma5_before'].values[0] and stock_data['prevRSI'].values[0] <= 55: 
                    IsSell = True


                if IsSell == True:

                    ReturnMoney = (investData['InvestMoney'] * (1.0 - fee))  #수수료 및 세금, 슬리피지 반영!


                    TryCnt += 1

                    if RevenueRate > 0: #수익률이 0보다 크다면 익절한 셈이다!
                        SuccesCnt += 1
                    else:
                        FailCnt += 1
                
                    
                    RemainInvestMoney += ReturnMoney
                    investData['InvestMoney'] = 0


                    #pprint.pprint(NowInvestList)

                    NowInvestMoney = 0
                    for iData in NowInvestList:
                        NowInvestMoney += iData['InvestMoney']

                    InvestMoney = RemainInvestMoney + NowInvestMoney


                    print("(",ticker, ") ", str(date), " " ,i, " >>>>>>>>>>>>>>>>> 매도!  수익률: ", round(RevenueRate,2) , "%",  " 매도가", NowOpenPrice, " 매수날짜:",str(investData['Date']))
                    print("\n\n")                

                    items_to_remove.append(investData)
            
    #리스트에서 제거
    for item in items_to_remove:
        NowInvestList.remove(item)


    for ticker in pick_coins_top.index:

        if ticker in ['BTC/USDT:USDT','ETH/USDT:USDT']: 
            continue

        
        IsAlReadyInvest = False
        for investData in NowInvestList:
            if ticker == investData['ticker']: 
                IsAlReadyInvest = True
                break

        IsTOPInChange = False
        for ticker_t in pick_coins_top_change.index:
            if ticker_t == ticker:
                coin_top_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == ticker_t)]
                if len(coin_top_data) == 1:
                    IsTOPInChange = True
                    break




        stock_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == ticker)]
        if len(stock_data) == 1 and IsAlReadyInvest == False and IsTOPInChange == True: #and len(btc_data) == 1 and len(eth_data) == 1:

            NowOpenPrice = stock_data['open'].values[0] 
            BuyPrice = NowOpenPrice

            IsBuyGo = False

            #매수 조건!!!!
            if stock_data['ma5_rsi_before'].values[0] < stock_data['prevRSI'].values[0] and stock_data['prevChange'].values[0] > 0 and stock_data['ma5_before'].values[0] < stock_data['prevClose'].values[0] and stock_data['ma10_before'].values[0] < stock_data['prevClose'].values[0] and stock_data['ma20_before'].values[0] < stock_data['prevClose'].values[0]:
                IsBuyGo = True


            
            if IsBuyGo == True:

                if len(NowInvestList) < int(DivNum):

                    if IsFirstDateSet == False:
                        FirstDateStr = str(date)
                        FirstDateIndex = i-1
                        IsFirstDateSet = True

                    

                    InvestGoMoney = InvestMoneyCell 
                    
                    #거래대금을 통한 제한!!!
                    #'''
                    if InvestGoMoney > stock_data['value_ma'].values[0] / 2000:
                        InvestGoMoney = stock_data['value_ma'].values[0] / 2000

                    if InvestGoMoney < 10:
                        InvestGoMoney = 10
                    #'''



                    BuyAmt = float(InvestGoMoney /  BuyPrice) #매수 가능 수량을 구한다!

                    NowFee = (BuyAmt*BuyPrice) * fee

                    #남은 돈이 있다면 매수 한다!!
                    if RemainInvestMoney >= (BuyAmt*BuyPrice) + NowFee:


                        RealInvestMoney = (BuyAmt*BuyPrice) #실제 들어간 투자금

                        RemainInvestMoney -= (BuyAmt*BuyPrice) #남은 투자금!
                        RemainInvestMoney -= NowFee


                        InvestData = dict()

                        InvestData['ticker'] = ticker
                        InvestData['InvestMoney'] = RealInvestMoney
                        InvestData['BuyPrice'] = BuyPrice
                        InvestData['Date'] = str(date)

                        NowInvestList.append(InvestData)


                        NowInvestMoney = 0
                        for iData in NowInvestList:
                            NowInvestMoney += iData['InvestMoney']

                        InvestMoney = RemainInvestMoney + NowInvestMoney


                        print("(",ticker, ") ", str(date), " " ,i, " >>>>>>>>>>>>>>>>> 매수!  매수가:", BuyPrice)



    NowInvestMoney = 0


    for iData in NowInvestList:
        NowInvestMoney += iData['InvestMoney']

    InvestMoney = RemainInvestMoney + NowInvestMoney


    InvestMoneyCell = InvestMoney / (DivNum +1)

    InvestCoinListStr = ""

    for iData in NowInvestList:
        InvestCoinListStr += iData['ticker'] + " "


    print("\n\n>>>>>>>>>>>>", InvestCoinListStr, "---> 투자개수 : ", len(NowInvestList))
    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>--))", str(date), " 잔고:",str(InvestMoney) , "=" , str(RemainInvestMoney) , "+" , str(NowInvestMoney), "\n\n" )
    
    TotalMoneyList.append(InvestMoney)

    #####################################################
    #####################################################
    #####################################################
    #'''
    
   

#결과 정리 및 데이터 만들기!!
if len(TotalMoneyList) > 0:

    print("TotalMoneyList -> ", len(TotalMoneyList))


    resultData = dict()

    # Create the result DataFrame with matching shapes
    result_df = pd.DataFrame({"Total_Money": TotalMoneyList}, index=combined_df.index.unique())

    result_df['Ror'] = np.nan_to_num(result_df['Total_Money'].pct_change()) + 1
    result_df['Cum_Ror'] = result_df['Ror'].cumprod()
    result_df['Highwatermark'] = result_df['Cum_Ror'].cummax()
    result_df['Drawdown'] = (result_df['Cum_Ror'] / result_df['Highwatermark']) - 1
    result_df['MaxDrawdown'] = result_df['Drawdown'].cummin()

    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    pprint.pprint(result_df)
    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

    resultData['DateStr'] = str(FirstDateStr) + " ~ " + str(result_df.iloc[-1].name)

    resultData['OriMoney'] = InvestTotalMoney
    resultData['FinalMoney'] = result_df['Total_Money'].iloc[-1]
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
    axs[0].set_title('Return Comparison Chart')
    axs[0].legend()

    # Plot the MDD and DD chart on the same graph
    axs[1].plot(result_df.index, result_df['MaxDrawdown'] * 100, label='MDD')
    axs[1].plot(result_df.index, result_df['Drawdown'] * 100, label='Drawdown')
    axs[1].set_ylabel('Drawdown (%)')
    axs[1].set_title('Drawdown Comparison Chart')
    axs[1].legend()

    # Show the plot
    plt.tight_layout()
    plt.show()
        

    


    for idx, row in result_df.iterrows():
        print(idx, " " , row['Total_Money'], " "  , row['Cum_Ror'])
        



#데이터를 보기좋게 프린트 해주는 로직!
print("\n\n--------------------")


for result in ResultList:

    print("--->>>",result['DateStr'].replace("00:00:00",""),"<<<---")


    print("---------- 총 결과 ----------")
    print("최초 금액:", format(int(round(result['OriMoney'],0)), ',') , " 최종 금액:", format(int(round(result['FinalMoney'],0)), ','), " \n수익률:", round(((round(result['FinalMoney'],2) - round(result['OriMoney'],2) ) / round(result['OriMoney'],2) ) * 100,2) ,"% MDD:",  round(result['MDD'],2),"%")
    if result['TryCnt'] > 0:
        print("성공:", result['SuccesCnt'] , " 실패:", result['FailCnt']," -> 승률: ", round(result['SuccesCnt']/result['TryCnt'] * 100.0,2) ," %")

    print("------------------------------")
    print("####################################")



