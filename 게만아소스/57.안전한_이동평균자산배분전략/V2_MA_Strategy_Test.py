'''

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

해당 컨텐츠는 제가 직접 투자 하기 위해 이 전략을 추가 개선해서 더 좋은 성과를 보여주는 개인 전략이 존재합니다. 


게만아 추가 개선 개인 전략들..
https://blog.naver.com/zacra/223196497504


관심 있으신 분은 위 포스팅을 참고하세요!

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

 



$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

백테스팅은 내PC에서 해야 서버 자원을 아끼고 투자 성과 그래프도 확인할 수 있습니다!
이 포스팅을 정독하시고 다양한 기간으로 백테스팅 해보세요!!!
https://blog.naver.com/zacra/223180500307

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$




관련 포스팅
https://blog.naver.com/zacra/223597500754
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
import json

from datetime import datetime


Common.SetChangeMode("VIRTUAL") 

##################################################################

###############################################################################################################################################################
#테스트할 종목을 직접 판단하여 아래 예시처럼 넣으세요!
InvestStockList = list()

#InvestStockList.append({"stock_code":"QQQ", "small_ma":3 , "big_ma":132, "invest_rate":0.5}) 
#InvestStockList.append({"stock_code":"TLT", "small_ma":13 , "big_ma":53, "invest_rate":0.25}) 
#InvestStockList.append({"stock_code":"GLD", "small_ma":17 , "big_ma":78, "invest_rate":0.25}) 

#InvestStockList.append({"stock_code":"133690", "small_ma":5 , "big_ma":34, "invest_rate":0.4}) #TIGER 미국나스닥100
#InvestStockList.append({"stock_code":"069500", "small_ma":3 , "big_ma":103, "invest_rate":0.2}) #KODEX 200
#InvestStockList.append({"stock_code":"148070", "small_ma":8 , "big_ma":71, "invest_rate":0.1}) #KOSEF 국고채10년
#InvestStockList.append({"stock_code":"305080", "small_ma":20 , "big_ma":61, "invest_rate":0.1}) #TIGER 미국채10년선물
#InvestStockList.append({"stock_code":"132030", "small_ma":15 , "big_ma":89, "invest_rate":0.2}) #KODEX 골드선물(H)
###############################################################################################################################################################


#####################################################
TestArea = "US" #한국이라면 KR 미국이라면 US로 변경하세요 ^^
#####################################################

#################################################################
FixRate = 0.1 #각 자산별 할당 금액의 10%를 고정비중으로 투자함!
DynamicRate = 0.6 #각 자산별 할당 금액의 60%의 투자 비중은 모멘텀에 의해 정해짐!
#위의 경우 FixRate + DynamicRate = 0.7 즉 70%이니깐 매도신호 시 30%비중은 무조건 팔도록 되어 있다.
#위 두 값이 모두 0이라면 기존처럼 매도신호시 모두 판다!!


GetCount = 700  #얼마큼의 데이터를 가져올 것인지
CutCount = 0     #최근 데이터 삭제! 200으로 세팅하면 200개의 최근 데이터가 사라진다

  
TotalMoney = 10000000 #한국 계좌의 경우 시작 투자금 1000만원으로 가정!

TaxAdd = False #양도세 반영 여부! 
MoneyForTaxCalc = 0 #양도세 계산을 위한 손익을 저장할 변수 - 미국만 해당
FreeTax = 2100 #환율을 1200원으로 퉁쳐서 $2100 가 면세 기준! - 미국만 해당


if TestArea == "US": #미국의 경우는
    TotalMoney = 10000 #시작 투자금 $10000로 가정!
    TaxAdd = True #미국의 경우 양도세 반영!!!


FirstInvestMoney = TotalMoney

fee = 0.0025 #수수료를 매수매도마다 0.25%로 세팅!

print("테스트하는 총 금액: ", format(round(TotalMoney), ','))






#################################################################


    
RebalanceSt = "%Y%m" 
    


StockDataList = list()

for stock_info in InvestStockList:
    print("..",stock_info,"..")
    stock_data = dict()
    stock_data['stock_code'] = stock_info['stock_code']
    
    if TestArea == "KR":
        stock_data['stock_name'] = KisKR.GetStockName(stock_info['stock_code'])
    else:
        stock_data['stock_name'] = stock_info['stock_code']
        
    stock_data['invest_rate'] = stock_info['invest_rate']
    stock_data['InvestDayCnt'] = 0
    StockDataList.append(stock_data)

pprint.pprint(StockDataList)


def IncreaseInvestDayCnt(stock_code, StockDataList):
    for stock_data in StockDataList:
        if stock_code == stock_data['stock_code']:
            stock_data['InvestDayCnt'] += 1
            break


def GetDefaultInvestRate(stock_code, StockDataList):
    invest_rate = 0
    for stock_data in StockDataList:
        if stock_code == stock_data['stock_code']:
            invest_rate = stock_data['invest_rate']
            break

    return invest_rate


#사실 미국에선 사용하지 않지만 한국에선 사용
def GetStockName(stock_code, StockDataList):
    result_str = stock_code
    for stock_data in StockDataList:
        if stock_code == stock_data['stock_code']:
            result_str = stock_data['stock_name']
            break

    return result_str

NowInvestList = list() #투자중인 항목의 리스트



stock_df_list = []

for stock_info in InvestStockList:
    
    stock_code = stock_info['stock_code']
    #################################################################
    #################################################################
    df = Common.GetOhlcv(TestArea, stock_code, GetCount) 
    #################################################################
    #################################################################


    df['prevClose'] = df['close'].shift(1)
 
    
    ############# 이동평균선! ###############
    ma_dfs = []

    # 이동 평균 계산
    for ma in range(3, 201):
        ma_df = df['close'].rolling(ma).mean().rename(str(ma) + 'ma_before').shift(1)
        ma_dfs.append(ma_df)
        
        ma_df = df['close'].rolling(ma).mean().rename(str(ma) + 'ma_before2').shift(2)
        ma_dfs.append(ma_df)
    # 이동 평균 데이터 프레임을 하나로 결합
    ma_df_combined = pd.concat(ma_dfs, axis=1)

    # 원본 데이터 프레임과 결합
    df = pd.concat([df, ma_df_combined], axis=1)

    ########################################

    #200거래일 평균 모멘텀
    specific_days = list()

    for i in range(1,11):
        st = i * 20
        specific_days.append(st)

    for day in specific_days:
        column_name = f'Momentum_{day}'
        df[column_name] = (df['prevClose'] > df['close'].shift(day)).astype(int)

    df['Average_Momentum'] = df[[f'Momentum_{day}' for day in specific_days]].sum(axis=1) / 10


    df.dropna(inplace=True) #데이터 없는건 날린다!

    df = df[:len(df)- CutCount]
    data_dict = {stock_code: df}


    stock_df_list.append(data_dict)
        
    print("---stock_code---", stock_code , " len ",len(df))
    
    pprint.pprint(df)

    #모든 항목의 데이터를 만들어 놓는다!
    InvestData = dict()

    InvestData['stock_code'] = stock_code
    InvestData['InvestMoney'] = 0
    InvestData['InvestRate'] = stock_info['invest_rate']
    InvestData['small_ma'] = stock_info['small_ma']
    InvestData['big_ma'] =  stock_info['big_ma']
    InvestData['RebalanceAmt'] = 0
    InvestData['EntryMonth'] = 0
    InvestData['AvgPrice'] = 0
    InvestData['TotAmt'] = 0
    InvestData['Investing'] = False
    InvestData['IsRebalanceGo'] = False


    NowInvestList.append(InvestData)



combined_df = pd.concat([list(data_dict.values())[0].assign(stock_code=stock_code) for data_dict in stock_df_list for stock_code in data_dict])
combined_df.sort_index(inplace=True)
pprint.pprint(combined_df)
print(" len(combined_df) ", len(combined_df))



IsFirstDateSet = False
FirstDateStr = ""


NowInvestCode = ""
InvestMoney = TotalMoney
RemainInvestMoney = InvestMoney



ResultList = list()

TotalMoneyList = list()


i = 0
# Iterate over each date
for date in combined_df.index.unique():
 

    #날짜 정보를 획득
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
            

    i += 1


    IsRebalnceDayforTax = False


    #투자중인 종목을 순회하며 처리!
    for investData in NowInvestList:

        stock_code = investData['stock_code'] 
        
    

        stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)] 


        if len(stock_data) == 1:
    
            #################################################################################################################
            #매일매일의 등락률을 반영한다!
            NowClosePrice = 0
            PrevClosePrice = 0

            NowClosePrice = stock_data['close'].values[0]
            PrevClosePrice = stock_data['prevClose'].values[0] 


            if investData['InvestMoney'] > 0:
                investData['InvestMoney'] = investData['InvestMoney'] *  (1.0 + ((NowClosePrice - PrevClosePrice ) / PrevClosePrice))
                IncreaseInvestDayCnt(stock_code, StockDataList)
            #################################################################################################################



            ma1 = investData['small_ma']
            ma2 = investData['big_ma']
            
                
            small_ma = int(ma1)
            big_ma = int(ma2)
            
            

            IsReblanceDay = False
            
            if investData['EntryMonth'] != date_object.strftime(RebalanceSt):
                investData['EntryMonth'] = date_object.strftime(RebalanceSt)

                IsRebalnceDayforTax = True #미국 양도세 관련..



            

            #이평선에 의해 매도처리 해야 된다!!! 
            if investData['Investing'] == True and stock_data[str(small_ma)+'ma_before'].values[0] < stock_data[str(big_ma)+'ma_before'].values[0] and stock_data[str(small_ma)+'ma_before2'].values[0] > stock_data[str(small_ma)+'ma_before'].values[0]:
                IsReblanceDay = True
                
                SellRate = FixRate + (stock_data['Average_Momentum'].values[0] * DynamicRate) 
                
                investData['InvestRate'] = GetDefaultInvestRate(stock_code, StockDataList) * SellRate
                
            

            if investData['Investing'] == False and stock_data[str(small_ma)+'ma_before'].values[0] > stock_data[str(big_ma)+'ma_before'].values[0] and stock_data[str(small_ma)+'ma_before2'].values[0] < stock_data[str(small_ma)+'ma_before'].values[0]:
                IsReblanceDay = True
                investData['InvestRate'] = GetDefaultInvestRate(stock_code, StockDataList)
                    
                
            if IsReblanceDay == True: 
                
                
                investData['IsRebalanceGo'] = True
                investData['RebalanceAmt'] = 0

    
    if IsRebalnceDayforTax == True:

        if TaxAdd == True:
            #리밸런싱 하는 날이 1월 이라면 양도세를 반영하고 초기화 시켜준다!
            if int(date_object.strftime("%m")) == 1:
                MoneyForTaxCalc -= FreeTax
                
                print("지난 한해 동안 $", MoneyForTaxCalc," 손익확정을 했어요!")
                
                
                #공제후에도 남은 수익에 대해선 양도세22를 계산해 감산하자!!
                if MoneyForTaxCalc > 0:
                    OMG_Tax = MoneyForTaxCalc * 0.22
                    RemainInvestMoney -= OMG_Tax #남은 투자금에서 감산!!!
                    print(str(date), "--양도세 $",OMG_Tax , "차감 되었어요 ㅠ.ㅜ")
                else:
                    print(str(date), "--양도세 없어요! 불행인지 다행인지...^^")
                    
                    
                MoneyForTaxCalc = 0 #새해가 되었으니 초기화!!
                
            

    #################################################################################################################
    ##################### 리밸런싱 할때 투자 비중을 맞춰주는 작업 #############################



    NowInvestMoney = 0

    for iData in NowInvestList:
        NowInvestMoney += iData['InvestMoney']

    
    InvestMoney = RemainInvestMoney + NowInvestMoney


    #리밸런싱 수량을 확정한다!
    for investData in NowInvestList:

        if investData['IsRebalanceGo'] == True:

            stock_code = investData['stock_code']

            stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)] 

            
            if len(stock_data) == 1:
                

                NowClosePrice = stock_data['close'].values[0]


                GapInvest = (InvestMoney * investData['InvestRate']) - investData['InvestMoney'] #목표 금액에서 현재 평가금액을 빼서 갭을 구한다!
                investData['RebalanceAmt'] += int(GapInvest / NowClosePrice)




    #실제 매도!!
    for investData in NowInvestList:


        if investData['IsRebalanceGo'] == True:


            stock_code = investData['stock_code']
            
            stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)] 

            if len(stock_data) == 1:

                NowClosePrice = stock_data['close'].values[0]

                if investData['RebalanceAmt'] < 0:


                    SellAmt = abs(investData['RebalanceAmt'])

                    RealSellMoney = SellAmt * NowClosePrice


                    RevenueRate = (NowClosePrice - investData['AvgPrice']) / investData['AvgPrice'] #손익률을 구한다!

                    #팔아야할 금액이 현재 투자금보다 크다면!!! 모두 판다! 혹은 실제 팔아야할 계산된 금액이 투자금보다 크다면 모두 판다!!
                    if RealSellMoney > investData['InvestMoney']:
                        RealSellMoney = investData['InvestMoney']

                        ReturnMoney = RealSellMoney

                        investData['InvestMoney'] = 0

                        RemainInvestMoney += (ReturnMoney * (1.0 - fee))

                        investData['IsRebalanceGo'] = False

                        investData['AvgPrice'] = 0
                        investData['TotAmt'] = 0
                        
                        #모두 팔때는 매도 금액 x 수익률이 손익금
                        if TaxAdd == True:
                            MoneyForTaxCalc += RealSellMoney * RevenueRate
                        
                        print(investData['stock_code'], str(date), " " ,i, " >>>>>>>>>>>>>>>>> 모두 매도!(리밸런싱) 매도금액:", round(RealSellMoney,2) ,  " 매도가:",NowClosePrice)
                        
                        
                    else:

                        if SellAmt > 0 :

                            ReturnMoney = RealSellMoney

                            investData['InvestMoney'] -= RealSellMoney

                            RemainInvestMoney += (ReturnMoney * (1.0 - fee))

                            investData['IsRebalanceGo'] = False
                            
                            investData['TotAmt'] -= SellAmt
                            
                            #일부 팔때는 (매도금액 x 매도수량) - (평균매입단가 x 매도수량)
                            if TaxAdd == True:
                                MoneyForTaxCalc += (RealSellMoney - (investData['AvgPrice']*SellAmt))
                                
                            print(investData['stock_code'], str(date), " " ,i, " >>>>>>>>>>>>>>>>> 일부 매도!(리밸런싱) 매도금액:", round(RealSellMoney,2) ,  " 매도가:",NowClosePrice)

                    
                    investData['Investing'] = False

                    investData['EntryMonth'] = date_object.strftime(RebalanceSt)
                    investData['IsRebalanceGo'] = False

            

    #실제 매수!!
    for investData in NowInvestList:


        if investData['IsRebalanceGo'] == True:


            stock_code = investData['stock_code']
            
            stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)] 

            if len(stock_data) == 1:

                NowClosePrice = stock_data['close'].values[0]

                if investData['RebalanceAmt'] > 0:


                    if IsFirstDateSet == False:
                        FirstDateStr = str(date)
                        IsFirstDateSet = True


                    BuyAmt = investData['RebalanceAmt']


                    NowFee = (BuyAmt*NowClosePrice) * fee

                    #매수해야 되는데 남은돈이 부족하다면 수량을 하나씩 감소시켜 만족할 때 매수한다!!
                    while RemainInvestMoney < (BuyAmt*NowClosePrice) + NowFee:
                        if RemainInvestMoney > NowClosePrice:
                            BuyAmt -= 1
                            NowFee = (BuyAmt*NowClosePrice) * fee
                        else:
                            break
                    
                    if BuyAmt > 0 and RemainInvestMoney > NowClosePrice:
                        RealBuyMoney = BuyAmt * NowClosePrice

                        investData['InvestMoney'] += RealBuyMoney

                        RemainInvestMoney -= (BuyAmt*NowClosePrice) #남은 투자금!
                        RemainInvestMoney -= NowFee

                        print('GOGO!!!')
                        if investData['TotAmt'] == 0:
                            investData['AvgPrice'] = NowClosePrice
                            investData['TotAmt'] = BuyAmt
                            

                        else:

                            investData['TotAmt'] += BuyAmt
                            investData['AvgPrice'] = ((investData['AvgPrice'] * (investData['TotAmt']-BuyAmt)) + (BuyAmt*NowClosePrice)) / investData['TotAmt']

                        print(investData['stock_code'], str(date), " " ,i, " >>>>>>>>>>>>>>>>> 매수!(리밸런싱) 매수금액:", round(RealBuyMoney,2) ,  " 매수가:",NowClosePrice)
                        investData['Investing'] = True
            

                    investData['EntryMonth'] = date_object.strftime(RebalanceSt)
                    investData['IsRebalanceGo'] = False


    #혹시나 위에서 처리되지 않은 게 있다면...            
    for investData in NowInvestList:


        if investData['IsRebalanceGo'] == True:

            investData['EntryMonth'] = date_object.strftime(RebalanceSt)
            investData['IsRebalanceGo'] = False



    
    NowInvestMoney = 0

    for iData in NowInvestList:
        NowInvestMoney += iData['InvestMoney']

    
    InvestMoney = RemainInvestMoney + NowInvestMoney



    InvestCoinListStr = ""
    print("\n\n------------------------------------\n")
    for iData in NowInvestList:
        InvestCoinListStr += (">>>" + GetStockName(iData['stock_code'], StockDataList)  + "-> 목표투자비중:" + str(iData['InvestRate']*100) + "%-> 실제투자비중:" + str(iData['InvestMoney']/InvestMoney*100)  +"%\n -->실제투자금:" + str(format(int(round(iData['InvestMoney'],0)), ',')) +"\n\n")
    print("------------------------------------")

    print(InvestCoinListStr, "---> 투자대상 : ", len(NowInvestList))
    #pprint.pprint(NowInvestList)
    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>--))", str(date), " 잔고:",str(InvestMoney) , "=" , str(RemainInvestMoney) , "+" , str(NowInvestMoney), "\n\n" )
    print("MoneyForTaxCalc : ", MoneyForTaxCalc)

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
        print(stock_data['stock_name'] , " (", stock_data['stock_code'],") 투자일수: ",stock_data['InvestDayCnt'])

    print("---------- 총 결과 ----------")
    print("최초 금액:", format(int(round(result['OriMoney'],0)), ',') , " 최종 금액:", format(int(round(result['FinalMoney'],0)), ','), " \n수익률:", round(((round(result['FinalMoney'],2) - round(result['OriMoney'],2) ) / round(result['OriMoney'],2) ) * 100,2) ,"% MDD:",  round(result['MDD'],2),"%")

    print("------------------------------")
    print("####################################")
