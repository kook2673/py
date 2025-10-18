'''


$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

백테스팅은 내PC에서 해야 서버 자원을 아끼고 투자 성과 그래프도 확인할 수 있습니다!
이 포스팅을 정독하시고 다양한 기간으로 백테스팅 해보세요!!!
https://blog.naver.com/zacra/223180500307

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$


관련 포스팅

레버리지 ETF 위 아래 변동성 돌파 전략!
https://blog.naver.com/zacra/223128702427

위 포스팅을 꼭 참고하세요!!!

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제공된 전략은 학습 및 테스트 목적으로 구성된 예시 코드이며
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.
   

주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!
   

  
'''

import KIS_Common as Common
import KIS_API_Helper_KR as KisKR
import pandas as pd
import pprint
import numpy as np
import matplotlib.pyplot as plt


#계좌 선택.. "VIRTUAL" 는 모의 계좌!
Common.SetChangeMode("VIRTUAL") #REAL or VIRTUAL

################################################################################################################################################
InvestStockList = [] #테스트할 종목코드를 직접 입력하세요
#InvestStockList = ["306950","412570","243880","243890","225040","225050","225060","196030", "236350","204480","371130"]
################################################################################################################################################



#이렇게 직접 금액을 지정
TotalMoney = 10000000
FirstInvestMoney = TotalMoney

print("테스트하는 총 금액: ", format(round(TotalMoney), ','))




StockDataList = list()

for stock_code in InvestStockList:
    print("..",stock_code,"..")
    stock_data = dict()
    stock_data['stock_code'] = stock_code
    stock_data['stock_name'] = KisKR.GetStockName(stock_code)
    stock_data['try'] = 0
    stock_data['success'] = 0
    stock_data['fail'] = 0
    stock_data['accRev'] = 0

    StockDataList.append(stock_data)

pprint.pprint(StockDataList)



def GetStockName(stock_code, StockDataList):
    result_str = stock_code
    for stock_data in StockDataList:
        if stock_code == stock_data['stock_code']:
            result_str = stock_data['stock_name']
            break

    return result_str
    

stock_df_list = []

for stock_code in InvestStockList:
    df = Common.GetOhlcv("KR", stock_code,10000)
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
    df['prevRSI2'] = df['RSI'].shift(2)

    df['prevHigh'] = df['high'].shift(1)
    df['prevLow'] = df['low'].shift(1)
    df['prevOpen'] = df['open'].shift(1)
    df['value_ma'] = df['value'].rolling(window=10).max().shift(1)

    df.dropna(inplace=True) #데이터 없는건 날린다!

   

    data_dict = {stock_code: df}
    stock_df_list.append(data_dict)
    print("---stock_code---", stock_code , " len ",len(df))
    pprint.pprint(df)





# Combine the OHLCV data into a single DataFrame
combined_df = pd.concat([list(data_dict.values())[0].assign(stock_code=stock_code) for data_dict in stock_df_list for stock_code in data_dict])

# Sort the combined DataFrame by date
combined_df.sort_index(inplace=True)

pprint.pprint(combined_df)
print(" len(combined_df) ", len(combined_df))



IsBuy = False #매수 했는지 여부
BUY_PRICE = 0  #매수한 금액! 

TryCnt = 0      #매매횟수
SuccesCnt = 0   #익절 숫자
FailCnt = 0     #손절 숫자


fee = 0.0015 #수수료+세금+슬리피지를 매수매도마다 0.15%로 세팅!
IsFirstDateSet = False
FirstDateStr = ""


NowInvestCode = ""
InvestMoney = TotalMoney


DivNum = int(len(InvestStockList)/2) 

InvestMoneyCell = InvestMoney / (DivNum + 1)

RemainInvestMoney = InvestMoney




ResultList = list()

TotalMoneyList = list()

NowInvestList = list()



i = 0
# Iterate over each date
for date in combined_df.index.unique():
 

    pick_stocks = combined_df.loc[combined_df.index == date].groupby('stock_code')['prevRSI'].max().nlargest(DivNum)
    print("\n\n") 

    i += 1


    today_sell_code = list()



    items_to_remove = list()

    #투자중인 티커!!
    for investData in NowInvestList:
       # pprint.pprint(investData)

        ticker = investData['ticker'] 
        
        if investData['InvestMoney'] > 0:
            stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == ticker)]

            if len(stock_data) == 1:
        

                NowOpenPrice = stock_data['open'].values[0]
                PrevOpenPrice = stock_data['prevOpen'].values[0] 

                #변동성 하향돌파 시가 - (전일고가-전일저가)*0.2
                CutPrice = stock_data['open'].values[0] - ((stock_data['prevHigh'].values[0] - stock_data['prevLow'].values[0]) * 0.2)

                SellPrice = NowOpenPrice

                CutRate = (CutPrice - NowOpenPrice) / NowOpenPrice

                IsSellGo = False
                if CutPrice >= stock_data['low'].values[0] :
                    IsSellGo = True
                    SellPrice = CutPrice


                if investData['DolPaCheck'] == False:
                    investData['DolPaCheck'] = True
                    investData['InvestMoney'] = investData['InvestMoney'] *  (1.0 + ((SellPrice - investData['BuyPrice'] ) / investData['BuyPrice'] ))
                else:
                    investData['InvestMoney'] = investData['InvestMoney'] *  (1.0 + ((SellPrice - PrevOpenPrice ) / PrevOpenPrice))


                if IsSellGo == True:

                    #진입(매수)가격 대비 변동률
                    Rate = (NowOpenPrice - investData['BuyPrice']) / investData['BuyPrice']


                    RevenueRate = (Rate - fee)*100.0 #수익률 계산


                    ReturnMoney = (investData['InvestMoney'] * (1.0 - fee))  #수수료 및 세금, 슬리피지 반영!


                    TryCnt += 1

                    if RevenueRate > 0: #수익률이 0보다 크다면 익절한 셈이다!
                        SuccesCnt += 1
                    else:
                        FailCnt += 1
        
                    #종목별 성과를 기록한다.
                    for stock_data in StockDataList:
                        if ticker == stock_data['stock_code']:
                            stock_data['try'] += 1
                            if RevenueRate > 0:
                                stock_data['success'] += 1
                            else:
                                stock_data['fail'] +=1
                            stock_data['accRev'] += RevenueRate


                    
                    RemainInvestMoney += ReturnMoney
                    investData['InvestMoney'] = 0


                    #pprint.pprint(NowInvestList)

                    NowInvestMoney = 0
                    for iData in NowInvestList:
                        NowInvestMoney += iData['InvestMoney']

                    InvestMoney = RemainInvestMoney + NowInvestMoney

                    print(GetStockName(ticker, StockDataList), "(",ticker, ") ", str(date), " " ,i, " >>>>>>>>>>>>>>>>> 매도! 매수일:",investData['Date']," 매수가:",str(investData['BuyPrice']) ," 매수금:",str(investData['FirstMoney'])," 수익률: ", round(RevenueRate,2) , "%", " ,회수금:", round(ReturnMoney,2)  , " 매도가", SellPrice)
                              

                    items_to_remove.append(investData)

                    today_sell_code.append(ticker)


    #리스트에서 제거
    for item in items_to_remove:
        NowInvestList.remove(item)


    if len(NowInvestList) < int(DivNum):

        for stock_code in pick_stocks.index:

            
            IsAlReadyInvest = False
            for investData in NowInvestList:
                if stock_code == investData['ticker']: 
                    IsAlReadyInvest = True
                    break    

            if stock_code not in today_sell_code and IsAlReadyInvest == False:

                stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)]


  
                #변동성 돌파 시가 + (전일고가-전일저가)*0.3
                DolPaPrice = stock_data['open'].values[0] + ((stock_data['prevHigh'].values[0] - stock_data['prevLow'].values[0]) * 0.3)



                DolPaRate = (DolPaPrice - stock_data['open'].values[0]) / stock_data['open'].values[0] * 100


                if DolPaPrice <= stock_data['high'].values[0]  :

                    IsBuyGo = True

                            
                    if IsBuyGo == True :
                        if IsFirstDateSet == False:
                            FirstDateStr = str(date)
                            IsFirstDateSet = True


                        InvestGoMoney = InvestMoneyCell 
                        
                        #거래대금을 통한 제한!!! ETF의 경우 LP활동시간에는 유동성이 공급되기에 제한을 하지 않았다.
                        '''
                        if InvestGoMoney > stock_data['value_ma'].values[0] / 10:
                            InvestGoMoney = stock_data['value_ma'].values[0] / 10

                        if InvestGoMoney < DolPaPrice*10.0:
                            InvestGoMoney = DolPaPrice*10.0
                        '''

                        if DolPaPrice > 0:

                            BuyAmt = int(InvestGoMoney /  DolPaPrice) #매수 가능 수량을 구한다!

                            NowFee = (BuyAmt*DolPaPrice) * fee

                            #남은 돈이 있다면 매수 한다!!
                            if RemainInvestMoney >= (BuyAmt*DolPaPrice) + NowFee:


                                RealInvestMoney = (BuyAmt*DolPaPrice) #실제 들어간 투자금

                                RemainInvestMoney -= (BuyAmt*DolPaPrice) #남은 투자금!
                                RemainInvestMoney -= NowFee


                                InvestData = dict()

                                InvestData['ticker'] = stock_code
                                InvestData['InvestMoney'] = RealInvestMoney
                                InvestData['FirstMoney'] = RealInvestMoney
                                InvestData['BuyPrice'] = DolPaPrice
                                InvestData['DolPaCheck'] = False
                                InvestData['Date'] = str(date)



                                NowInvestList.append(InvestData)


                                NowInvestMoney = 0
                                for iData in NowInvestList:
                                    NowInvestMoney += iData['InvestMoney']

                                InvestMoney = RemainInvestMoney + NowInvestMoney


                                print(GetStockName(stock_code, StockDataList), "(",stock_code, ") ", str(date), " " ,i, " >>>>>>>>>>>>>>>>> 매수! ,매수금액:", round(RealInvestMoney,2) , " 돌파가격", DolPaPrice, " 시가:", stock_data['open'].values[0])



    
    NowInvestMoney = 0

    for iData in NowInvestList:
        NowInvestMoney += iData['InvestMoney']


    InvestMoneyCell = InvestMoney / (DivNum + 1)

    InvestMoney = RemainInvestMoney + NowInvestMoney

    InvestCoinListStr = ""
    print("\n\n------------------------------------")
    for iData in NowInvestList:
        InvestCoinListStr += GetStockName(iData['ticker'], StockDataList)  + " "
    print("------------------------------------")

    print(">>>>>>>>>>>>", InvestCoinListStr, "---> 투자개수 : ", len(NowInvestList))
    #pprint.pprint(NowInvestList)
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

    resultData['OriMoney'] = FirstInvestMoney
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

    for stock_data in StockDataList:
        print(stock_data['stock_name'] , " (", stock_data['stock_code'],")")
        if stock_data['try'] > 0:
            print("성공:", stock_data['success'] , " 실패:", stock_data['fail']," -> 승률: ", round(stock_data['success']/stock_data['try'] * 100.0,2) ," %")
            print("매매당 평균 수익률:", round(stock_data['accRev']/ stock_data['try'],2) )
        print()

    print("---------- 총 결과 ----------")
    print("최초 금액:", format(int(round(result['OriMoney'],0)), ',') , " 최종 금액:", format(int(round(result['FinalMoney'],0)), ','), " \n수익률:", round(((round(result['FinalMoney'],2) - round(result['OriMoney'],2) ) / round(result['OriMoney'],2) ) * 100,2) ,"% MDD:",  round(result['MDD'],2),"%")
    if result['TryCnt'] > 0:
        print("성공:", result['SuccesCnt'] , " 실패:", result['FailCnt']," -> 승률: ", round(result['SuccesCnt']/result['TryCnt'] * 100.0,2) ," %")

    print("------------------------------")
    print("####################################")
