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


######################################################
코드 이해하는데 도움 되는 설명 참고 영상!
https://youtu.be/m_dw24x7VQQ
######################################################




관련 포스팅

섹터 ETF 변동성 돌파 전략 개선하고 자동화 하기 대작전!
https://blog.naver.com/zacra/223110831744

추가 개선되었습니다!
https://blog.naver.com/zacra/223231643956

최종 MDD개선 안내 버전!
https://blog.naver.com/zacra/223370782309

[FINAL] 최종 개선 버전2 안내!!!!
https://blog.naver.com/zacra/223620239264



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
from datetime import datetime

#계좌 선택.. "VIRTUAL" 는 모의 계좌!
Common.SetChangeMode("VIRTUAL") #REAL or VIRTUAL

##############################################################################################################################
InvestStockList = [] #테스트할 종목을 직접 넣으세요!
#InvestStockList = ["091160", "091230", "305720", "305540" , "091170" , "091220" , "102970" , "117460", "091180", "102960"] #예시

##############################################################################################################################


#이렇게 직접 금액을 지정
TotalMoney = 10000000

StartYear = 2013

print("테스트하는 총 금액: ", format(round(TotalMoney), ','))


StockDataList = list()

for stock_code in InvestStockList:
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
    df = Common.GetOhlcv("KR", stock_code,3000) 
    df['value_median'] = df['value'].shift(1).rolling(window=20).median()


    df['prevValue'] = df['value'].shift(1)
    df['prevClose'] = df['close'].shift(1)
    df['prevOpen'] = df['open'].shift(1)

    df['prevHigh'] = df['high'].shift(1)
    df['prevLow'] = df['low'].shift(1)

    df['Disparity'] = df['prevClose'] / df['prevClose'].rolling(window=20).mean() * 100.0

    df['ma_before'] = df['close'].rolling(5).mean().shift(1)
    df['ma_before2'] = df['close'].rolling(5).mean().shift(2)

    df['ma20_before2'] = df['close'].rolling(20).mean().shift(2)
    df['ma20_before'] = df['close'].rolling(20).mean().shift(1)

    df['ma60_before2'] = df['close'].rolling(60).mean().shift(2)
    df['ma60_before'] = df['close'].rolling(60).mean().shift(1)
    
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
FirstDateIndex = 0


NowInvestCode = ""
InvestMoney = TotalMoney

ResultList = list()

TotalMoneyList = list()

IsCutRest = False

i = 0
# Iterate over each date
for date in combined_df.index.unique():
 

    date_format = "%Y-%m-%d %H:%M:%S"
    date_object = None

    try:
        date_object = datetime.strptime(str(date), date_format)
    
    except Exception as e:
        try:
            date_format = "%Y%m%d"
            date_object = datetime.strptime(str(date), date_format)

        except Exception as e2:
            date_format = "%Y-%m-%d"
            date_object = datetime.strptime(str(date), date_format)
            


    pick_stocks = combined_df.loc[combined_df.index == date].groupby('stock_code')['value_median'].max().nlargest(1) #거래대금 중위값 TOP 1




    i += 1
    if IsBuy == True:
        

        #IsBuy가 True라면... 다음날 시가에 매도!
        stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == NowInvestCode)]

        NowOpenPrice = stock_data['open'].values[0]


        InvestMoney = InvestMoney * (1.0 + ((NowOpenPrice - BUY_PRICE) / BUY_PRICE))


        #진입(매수)가격 대비 변동률
        Rate = (NowOpenPrice - BUY_PRICE) / BUY_PRICE

        RevenueRate = (Rate - fee)*100.0 #수익률 계산

        InvestMoney = InvestMoney * (1.0 - fee)  #수수료 및 세금, 슬리피지 반영!

        print(GetStockName(NowInvestCode, StockDataList), "(",NowInvestCode, ") ", str(date), " " ,i, " >>>>>>>>>>>>>>>>> 매도!  수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:", round(InvestMoney,2)  , " 매도가", NowOpenPrice)
        print("\n\n")


        TryCnt += 1

        if RevenueRate > 0: #수익률이 0보다 크다면 익절한 셈이다!
            SuccesCnt += 1
        else:
            FailCnt += 1
            IsCutRest = True

        #종목별 성과를 기록한다.
        for stock_data in StockDataList:
            if NowInvestCode == stock_data['stock_code']:
                stock_data['try'] += 1
                if RevenueRate > 0:
                    stock_data['success'] += 1
                else:
                    stock_data['fail'] +=1
                stock_data['accRev'] += RevenueRate

        IsBuy = False #매도했다




    if IsBuy == False and int(date_object.strftime("%Y")) >= StartYear:


        for stock_code in pick_stocks.index:
            stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)]


            #시가 + 0.8%
            #DolPaPrice = stock_data['open'].values[0] * (1.008)
            #변동성 돌파 시가 + (전일고가-전일저가)*0.4 
            DolPaPrice = stock_data['open'].values[0] + ((stock_data['prevHigh'].values[0] - stock_data['prevLow'].values[0]) * 0.45)

            Disparity = stock_data['Disparity'].values[0]


            # 요일 가져오기 (0: 월요일, 1: 화요일,2 수요일 3 목요일 4 금요일 5 토요일 ..., 6: 일요일)
            weekday = date_object.weekday()


            if DolPaPrice <= stock_data['high'].values[0]  :


                IsBuyGo = True
                
                #목요일 금요일에는 이평선 조건을 더 체크한다!
                if weekday == 3 or weekday == 4 :

                    if stock_data['ma_before2'].values[0] > stock_data['ma_before'].values[0] :
                        IsBuyGo = False

                #나머지 요일에는 이격도를 체크한다!
                else:
                 
                    if Disparity > 110:
                        IsBuyGo = False
                            
                    
                ##### MDD 개선 조건 #####
                if ( (stock_data['prevLow'].values[0] > stock_data['open'].values[0]) or (stock_data['prevOpen'].values[0] > stock_data['prevClose'].values[0]) ) and stock_data['ma60_before'].values[0] > stock_data['prevClose'].values[0] :
                    IsBuyGo = False
                #######################

                        
                if IsBuyGo == True:
                    if IsFirstDateSet == False:
                        FirstDateStr = str(date)
                        FirstDateIndex = i-1
                        IsFirstDateSet = True

                    NowInvestCode = stock_code
                    BUY_PRICE = DolPaPrice 

                    InvestMoney = InvestMoney * (1.0 - fee)  #수수료 및 세금, 슬리피지 반영!
        
                    print(GetStockName(stock_code, StockDataList), "(",stock_code, ") ", str(date), " " ,i, " >>>>>>>>>>>>>>>>> 매수! ,종목 잔고:", round(InvestMoney,2) , " 돌파가격", DolPaPrice, " 시가:", stock_data['open'].values[0])
                    IsBuy = True #매수했다
                    break


        
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

    resultData['OriMoney'] = result_df['Total_Money'].iloc[0]
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
