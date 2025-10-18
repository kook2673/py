'''

백테스팅은
https://blog.naver.com/zacra/223180500307
위 포스팅을 참고하여 (기간 조절 방법 포함) 내 PC에서 하시는 것을 권장합니다. (그래야 투자 성과 그래프도 나옵니다!)


관련 포스팅

미국 핵심위성 + 섹터모멘텀 전략 검증하고 개선하기
https://blog.naver.com/zacra/223135937564

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
import pandas as pd
import pprint
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

#계좌 선택.. "VIRTUAL" 는 모의 계좌!
Common.SetChangeMode("VIRTUAL") #REAL or VIRTUAL


#당연한 이야기지만 VOO등으로 변경해서 테스팅도 가능합니다.
Snp500ETF = "SPY"
##################################################################################################
InvestStockList = [] #아래 같은 예시로 테스트할 종목을 추가하셔요
#InvestStockList = [Snp500ETF,"XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLU","XLV","XLY","XLRE"]
##################################################################################################


#이렇게 직접 금액을 지정
TotalMoney = 10000
FirstInvestMoney = TotalMoney

print("테스트하는 총 금액: ", format(round(TotalMoney), ','))



StockDataList = list()

for stock_code in InvestStockList:
    print("..",stock_code,"..")
    stock_data = dict()
    stock_data['stock_code'] = stock_code
    stock_data['stock_name'] = stock_code#KisKR.GetStockName(stock_code)
    stock_data['try'] = 0
    stock_data['success'] = 0
    stock_data['fail'] = 0
    stock_data['accRev'] = 0

    StockDataList.append(stock_data)

pprint.pprint(StockDataList)


#사실 미국에선 사용하지 않지만 한국에선 유용하니깐 그냥 내비두장~
def GetStockName(stock_code, StockDataList):
    result_str = stock_code
    for stock_data in StockDataList:
        if stock_code == stock_data['stock_code']:
            result_str = stock_data['stock_name']
            break

    return result_str
    
    
#################################################################
#전략 백테스팅 시작 년도 지정!!!
StartYear = 2020
#StartYear = 2000
#################################################################

stock_df_list = []
stock_df_list_withSPY = []

for stock_code in InvestStockList:
    
    #################################################################
    #################################################################
    df = Common.GetOhlcv("US", stock_code,1622) #최근 3년여의 데이터
    #df = Common.GetOhlcv("US", stock_code,10000) #전체 기간 넉넉히 1만개 데이터!
    #################################################################
    #################################################################


    df['prevClose'] = df['close'].shift(1)


    df['prev1MonthPrice'] = df['close'].shift(20) 
    df['prev3MonthPrice'] = df['close'].shift(60)  
    df['prev6MonthPrice']  = df['close'].shift(120)  
    df['prev12MonthPrice']  = df['close'].shift(240)

    #모멘텀 스코어!! 이게 마이너스라면 투자 비중을 50% 감삼한다 (섹터만~)
    df['MomenTumScore'] =  (((df['prevClose'] - df['prev1MonthPrice']) / df['prev1MonthPrice']) * 12.0) + (((df['prevClose'] - df['prev3MonthPrice']) / df['prev3MonthPrice']) * 4.0) + (((df['prevClose'] - df['prev6MonthPrice']) / df['prev6MonthPrice']) * 2.0) + (((df['prevClose'] - df['prev12MonthPrice']) / df['prev12MonthPrice']) * 1.0)


    #20거래일(즉 약 1달) 총 10개의 데이터로 10개월 평균 모멘텀을 구한다!
    specific_days = list()

    for i in range(1,11):
        st = i * 20
        specific_days.append(st)

    for day in specific_days:

        column_name = f'Momentum_{day}'
        
        df[column_name] = (df['prevClose'] > df['close'].shift(day)).astype(int)

    df['Average_Momentum'] = df[[f'Momentum_{day}' for day in specific_days]].sum(axis=1) / 10


    df.dropna(inplace=True) #데이터 없는건 날린다!

   

    data_dict = {stock_code: df}

    #SPY랑 나머지 섹터ETF들 구분해서 다른 리스트에 저장
    if stock_code == Snp500ETF:
        stock_df_list_withSPY.append(data_dict)
    else:
        stock_df_list.append(data_dict)
        
    print("---stock_code---", stock_code , " len ",len(df))
    pprint.pprint(df)




#섹터ETF들의 통합 데이터
combined_df = pd.concat([list(data_dict.values())[0].assign(stock_code=stock_code) for data_dict in stock_df_list for stock_code in data_dict])
combined_df.sort_index(inplace=True)
pprint.pprint(combined_df)
print(" len(combined_df) ", len(combined_df))

#SPY 데이터는 따로 관리
combined_withSPY_df = pd.concat([list(data_dict.values())[0].assign(stock_code=stock_code) for data_dict in stock_df_list_withSPY for stock_code in data_dict])
combined_withSPY_df.sort_index(inplace=True)
pprint.pprint(combined_withSPY_df)
print(" len(combined_df) ", len(combined_withSPY_df))





IsBuy = False #매수 했는지 여부
BUY_PRICE = 0  #매수한 금액! 

TryCnt = 0      #매매횟수
SuccesCnt = 0   #익절 숫자
FailCnt = 0     #손절 숫자


fee = 0.0025 #수수료+세금+슬리피지를 매수매도마다 0.25%로 세팅!
IsFirstDateSet = False
FirstDateStr = ""


NowInvestCode = ""
InvestMoney = TotalMoney


##################################################################################################
##################################################################################################
TopCnt = 5 #최대 5개 섹터!

DivNum = TopCnt

#0.2 : 0.8로 SPY 20% : 섹터모멘텀 80% 비중으로 세팅되어 있다
SpyRate = 0.2
SectorRate = 0.8

InvestSpy = (InvestMoney * SpyRate ) * (1.0 - fee)     #0.2 
InvestMoneyCell = (InvestMoney * SectorRate  / (DivNum + 0)) * (1.0 - fee) #0.8 
##################################################################################################
##################################################################################################
RemainInvestMoney = InvestMoney



ResultList = list() #백테스팅 데이터 들어갈 리스트

TotalMoneyList = list() #투자금 데이터가 들어갈 리스트

NowInvestList = list() #투자중인 항목의 리스트

IsSPY_Buy = False


i = 0
# Iterate over each date
for date in combined_df.index.unique():
 
    
    #날짜 정보를 획득
    date_format = "%Y-%m-%d %H:%M:%S"
    date_object = None

    #데이터를 어디서 가져오느냐에 따라서(한투인지 야후인지) 날자 타잎이 다르기에 처리!
    try:
        date_object = datetime.strptime(str(date), date_format)
    
    except Exception as e:
        try:
            date_format = "%Y%m%d"
            date_object = datetime.strptime(str(date), date_format)

        except Exception as e2:
            date_format = "%Y-%m-%d"
            date_object = datetime.strptime(str(date), date_format)
            
            

    ##########################################################################################################################
    ##########################################################################################################################
    #섹터 모멘텀 TOP을 구하는데 평균 모멘텀을 사용하도록 세팅되어 있다. 얼마든지 변형 가능!!!
    pick_stocks = combined_df.loc[combined_df.index == date].groupby('stock_code')['Average_Momentum'].max().nlargest(TopCnt) #상위 n개!
    ##########################################################################################################################
    ##########################################################################################################################

    i += 1



    items_to_remove = list()

    #투자중인 종목을 순회하며 처리!
    for investData in NowInvestList:
       # pprint.pprint(investData)

        stock_code = investData['stock_code'] 
        
        if investData['InvestMoney'] > 0:

            stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)] #섹터 ETF
            stock_spy_data = combined_withSPY_df[(combined_withSPY_df.index == date) & (combined_withSPY_df['stock_code'] == stock_code)] #SPY ETF
            

            if len(stock_data) == 1 or len(stock_spy_data) == 1:
        
                #################################################################################################################
                #매일매일의 등락률을 반영한다!
                NowClosePrice = 0
                PrevClosePrice = 0

                if len(stock_data) == 1:

                    NowClosePrice = stock_data['close'].values[0]
                    PrevClosePrice = stock_data['prevClose'].values[0] 

                else:

                    NowClosePrice = stock_spy_data['close'].values[0]
                    PrevClosePrice = stock_spy_data['prevClose'].values[0] 

                investData['InvestMoney'] = investData['InvestMoney'] *  (1.0 + ((NowClosePrice - PrevClosePrice ) / PrevClosePrice))
                #################################################################################################################


                #################################################################################################################
                #지정한 TOP순위에서 벗어났는지 여부를 결정!!!!
                IsTOPIn = False
                for stock_code_t in pick_stocks.index:
                    if stock_code_t == stock_code:
                        coin_top_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code_t)]
                        if len(coin_top_data) == 1:
                            IsTOPIn = True
                            break
                #################################################################################################################

                IsReblanceDay = False
                #################################################################################################################
                #이 부분이 월별 리밸런싱을 가능하게 하는 부분~ 요 코드블럭을 주석처리하면 매일매일 체크해 TOP에 맞는 종목으로 리밸런싱하게 된다
                if investData['EntryMonth'] != date_object.strftime("%Y%m"):
                    investData['EntryMonth'] = date_object.strftime("%Y%m")
                    IsReblanceDay = True

                #월이 변동없다면 탑에 속한다고 친다!-월별 리밸런싱을 위해!
                else:
                    IsTOPIn = True
                #################################################################################################################
               

                
                #섹터ETF가 TOP에 못들어 갔다고 최종 결정되면 매도 진행!!!!
                if IsTOPIn == False and investData['stock_code'] != Snp500ETF:


                    #진입(매수)가격 대비 변동률
                    Rate = (NowClosePrice - investData['BuyPrice']) / investData['BuyPrice']


                    RevenueRate = (Rate - fee)*100.0 #수익률 계산


                    ReturnMoney = (investData['InvestMoney'] * (1.0 - fee))  #수수료 및 세금, 슬리피지 반영!


                    TryCnt += 1

                    if RevenueRate > 0: #수익률이 0보다 크다면 익절한 셈이다!
                        SuccesCnt += 1
                    else:
                        FailCnt += 1
        
                    #종목별 성과를 기록한다.
                    for stock_data in StockDataList:
                        if stock_code == stock_data['stock_code']:
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

                    print(GetStockName(stock_code, StockDataList), "(",stock_code, ") ", str(date), " " ,i, " >>>>>>>>>>>>>>>>> 매도! 매수일:",investData['Date']," 매수가:",str(investData['BuyPrice']) ," 매수금:",str(investData['FirstMoney'])," 수익률: ", round(RevenueRate,2) , "%", " ,회수금:", round(ReturnMoney,2)  , " 매도가", NowClosePrice)
                              

                    items_to_remove.append(investData) #투자중 리스트에서 제거해야한다

                else:

                    if IsReblanceDay == True: #리밸런싱 날이라면 여기는 SPY 그리고 이미 투자중인 섹터ETF가 있다
  
                        investData['IsRebalanceGo'] = True
                         


                    
                #'''
                
    #실제로 여기서 제거
    for item in items_to_remove:
        NowInvestList.remove(item)
        
        
    

    #################################################################################################################
    ##################### 리밸런싱 할때 투자 비중을 맞춰주는 작업 #############################
    # 테스팅 결과 성과가 안좋아서 제외  ###
    # 하지만 추가적으로 SPY 만 리밸런싱 진행 - 이유는 섹터는 순위가 바뀌면 자동적으로 늘어난 투자금에 맞게 투자가 되지만
    # 한번 매수하고 아무것도 안하는 SPY의 경우 계좌에 투자금이 새로 들어온다던가에 대응이 안되니깐 SPY만 매월 비중에 맞게 리밸런싱!!!
    #'''
    #월초여서 이미 투자중인 항목의 리밸런싱이 필요한 경우 진행! 먼저 매도부터!
    for investData in NowInvestList:

        if investData['IsRebalanceGo'] == True:
            
            if investData['stock_code'] == Snp500ETF:
                

                stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == investData['stock_code'])] 

                if len(stock_data) == 1:

                    InvestSpyForReblanceTargetMoney = (InvestMoney * SpyRate ) * (1.0 - fee)     #0.2 
                    InvestMoneyCellForReblanceTargetMoney  = (InvestMoney * SectorRate  / (DivNum + 0)) * (1.0 - fee) #0.8 

                    GapInvest = 0
                    if investData['stock_code'] == Snp500ETF:

                        GapInvest = InvestSpyForReblanceTargetMoney - investData['InvestMoney'] #목표 금액에서 현재 평가금액을 빼서 갭을 구한다


                    else:

                        GapInvest = InvestMoneyCellForReblanceTargetMoney - investData['InvestMoney'] #목표 금액에서 현재 평가금액을 빼서 갭을 구한다!


                    if GapInvest < 0:
                        GapInvest = abs(GapInvest)

                        NowClosePrice = stock_data['close'].values[0]

                        SellAmt = int(GapInvest / NowClosePrice)

                        if SellAmt > 0:

                            RealSellMoney = SellAmt * NowClosePrice

                            ReturnMoney = (RealSellMoney * (1.0 - fee))  #수수료 및 세금, 슬리피지 반영!

                            investData['InvestMoney'] -= RealSellMoney

                            RemainInvestMoney += ReturnMoney

                            investData['IsRebalanceGo'] = False
                            

                            print(investData['stock_code'], str(date), " " ,i, " >>>>>>>>>>>>>>>>> 일부 매도!(리밸런싱) ,매도금액:", round(RealSellMoney,2) ,  " 매도가:",NowClosePrice)
                            
    #월초여서 이미 투자중인 항목의 리밸런싱이 필요한 경우 진행! 매수!
    for investData in NowInvestList:

        if investData['IsRebalanceGo'] == True: #리밸런싱 마지막 매수단계이니깐
            investData['IsRebalanceGo'] = False #리밸런싱은 무조건 종료!
            
            if investData['stock_code'] == Snp500ETF:


                stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == investData['stock_code'])] 

                if len(stock_data) == 1:

                    InvestSpyForReblanceTargetMoney = (InvestMoney * SpyRate ) * (1.0 - fee)     #0.2 
                    InvestMoneyCellForReblanceTargetMoney  = (InvestMoney * SectorRate  / (DivNum + 0)) * (1.0 - fee) #0.8 

                    GapInvest = 0
                    if investData['stock_code'] == Snp500ETF:

                        GapInvest = InvestSpyForReblanceTargetMoney - investData['InvestMoney'] #목표 금액에서 현재 평가금액을 빼서 갭을 구한다


                    else:

                        GapInvest = InvestMoneyCellForReblanceTargetMoney - investData['InvestMoney'] #목표 금액에서 현재 평가금액을 빼서 갭을 구한다!


                    if GapInvest > 0:
                        GapInvest = abs(GapInvest)

                        NowClosePrice = stock_data['close'].values[0]

                        BuyAmt = int(GapInvest / NowClosePrice)

                        if BuyAmt > 0:

                            RealBuyMoney = BuyAmt * NowClosePrice

                            investData['InvestMoney'] += RealBuyMoney



                            OutMoney = (RealBuyMoney * (1.0 + fee))  #수수료 및 세금, 슬리피지 반영!

                            RemainInvestMoney -= OutMoney


                            print(investData['stock_code'], str(date), " " ,i, " >>>>>>>>>>>>>>>>> 일부 매수!(리밸런싱) ,매수금액:", round(RealBuyMoney,2) ,  " 매수가:",NowClosePrice)
    #'''
    #################################################################################################################
    #################################################################################################################
    
    
    


    #################################################################################################################
    #SPY ETF를 매수하는 로직으로 처음에 매수한뒤 유지한다
    spy_data = combined_withSPY_df[(combined_withSPY_df.index == date) & (combined_withSPY_df['stock_code'] == Snp500ETF)]
    if len(spy_data) == 1:

        
        NowClosePrice = spy_data['close'].values[0]

        #아직 첫 매수 전이라면..
        if IsSPY_Buy == False:
            
            IsAlReadyInvest = False
            for investData in NowInvestList:
                if Snp500ETF == investData['stock_code']: 
                    IsAlReadyInvest = True
                    break    



            if IsAlReadyInvest == False:
                    
                IsBuyGo = True
                        
                if IsBuyGo == True and int(date_object.strftime("%Y")) >= StartYear:
                    if IsFirstDateSet == False:
                        FirstDateStr = str(date)
                        IsFirstDateSet = True


                    InvestGoMoney = InvestSpy 
                    
            
                    if NowClosePrice > 0:

                        IsSPY_Buy = True


                        BuyAmt = int(InvestGoMoney/  NowClosePrice) #매수 가능 수량을 구한다!

                        NowFee = (BuyAmt*NowClosePrice) * fee


                        #남은 돈이 있다면 매수 한다!!
                        #혹시 남은돈이 모자르면 1주씩 줄여서 매수 가능한 수량을 구한다.
                        while RemainInvestMoney < (BuyAmt*NowClosePrice) + NowFee:
                            if RemainInvestMoney > NowClosePrice:
                                BuyAmt -= 1
                                NowFee = (BuyAmt*NowClosePrice) * fee
                            else:
                                break


                        RealInvestMoney = (BuyAmt*NowClosePrice) #실제 들어간 투자금

                        RemainInvestMoney -= (BuyAmt*NowClosePrice) #남은 투자금!
                        RemainInvestMoney -= NowFee

                        #관리한 투자 데이터!
                        InvestData = dict()

                        InvestData['stock_code'] = Snp500ETF
                        InvestData['InvestMoney'] = RealInvestMoney
                        InvestData['FirstMoney'] = RealInvestMoney
                        InvestData['BuyPrice'] = NowClosePrice
                        InvestData['EntryMonth'] = date_object.strftime("%Y%m")
                        InvestData['IsRebalanceGo'] = False
                        InvestData['Date'] = str(date)



                        NowInvestList.append(InvestData)


                        NowInvestMoney = 0
                        for iData in NowInvestList:
                            NowInvestMoney += iData['InvestMoney']

                        InvestMoney = RemainInvestMoney + NowInvestMoney


                        print(GetStockName(Snp500ETF, StockDataList), "(",Snp500ETF, ") ", str(date), " " ,i, " >>>>>>>>>>>>>>>>> 매수! ,매수금액:", round(RealInvestMoney,2) ,  " 매수가:",NowClosePrice)
        
       
        
    #################################################################################################################   


    #섹터 투자할 금액 설정!
    if TopCnt - len(NowInvestList) + 1 > 0:
        InvestMoneyCell = (RemainInvestMoney / (TopCnt - len(NowInvestList) +1 )) * (1.0 - fee)


    #아직 목표한 개수를 채우지 못했다면 안으로 매수 시도!!! 1을 빼주는 이유는 SPY가 있기 때문에
    if len(NowInvestList)-1 < TopCnt:


        for stock_code in pick_stocks.index:

            if stock_code == Snp500ETF: #SPY는 저기에 없을 테지만 
                continue

            print("-PICK_CODE-" , stock_code)

            
            IsAlReadyInvest = False
            for investData in NowInvestList:
                if stock_code == investData['stock_code']: 
                    IsAlReadyInvest = True
                    break    


            

            if IsAlReadyInvest == False:


                stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)]
                NowClosePrice = stock_data['close'].values[0]



                IsBuyGo = True

                #매수하되 지정한 년도부터 매수한다!!
                if IsBuyGo == True  and len(NowInvestList) -1 < TopCnt and int(date_object.strftime("%Y")) >= StartYear:
                    
                    if IsFirstDateSet == False:
                        FirstDateStr = str(date)
                        IsFirstDateSet = True



                    InvestGoMoney = InvestMoneyCell 
                    
                    #거래대금을 통한 제한!!! ETF의 경우 LP활동시간에는 유동성이 공급되기에 제한을 하지 않았다. 더군다나 미국인데 ㅎ
                    '''
                    if InvestGoMoney > stock_data['value_ma'].values[0] / 100:
                        InvestGoMoney = stock_data['value_ma'].values[0] / 100

                    if InvestGoMoney < DolPaPrice*10.0:
                        InvestGoMoney = DolPaPrice*10.0
                    '''



                    if NowClosePrice > 0:

                        #모멘텀 스코어가 음수라면 비중을 절반으로 줄여준다!!!
                        if stock_data['MomenTumScore'].values[0] < 0:
                            InvestGoMoney *= 0.5
                        

                        BuyAmt = int(InvestGoMoney /  NowClosePrice) #매수 가능 수량을 구한다!

                        NowFee = (BuyAmt*NowClosePrice) * fee

                        #매수해야 되는데 남은돈이 부족하다면 수량을 하나씩 감소시켜 만족할 때 매수한다!!
                        while RemainInvestMoney < (BuyAmt*NowClosePrice) + NowFee:
                            if RemainInvestMoney > NowClosePrice:
                                BuyAmt -= 1
                                NowFee = (BuyAmt*NowClosePrice) * fee
                            else:
                                break
                        


                        RealInvestMoney = (BuyAmt*NowClosePrice) #실제 들어간 투자금

                        RemainInvestMoney -= (BuyAmt*NowClosePrice) #남은 투자금!
                        RemainInvestMoney -= NowFee


                        InvestData = dict()

                        InvestData['stock_code'] = stock_code
                        InvestData['InvestMoney'] = RealInvestMoney
                        InvestData['FirstMoney'] = RealInvestMoney
                        InvestData['BuyPrice'] = NowClosePrice
                        InvestData['EntryMonth'] = date_object.strftime("%Y%m")
                        InvestData['IsRebalanceGo'] = False
                        InvestData['Date'] = str(date)



                        NowInvestList.append(InvestData)


                        NowInvestMoney = 0
                        for iData in NowInvestList:
                            NowInvestMoney += iData['InvestMoney']

                        InvestMoney = RemainInvestMoney + NowInvestMoney


                        print(GetStockName(stock_code, StockDataList), "(",stock_code, ") ", str(date), " " ,i, " >>>>>>>>>>>>>>>>> 매수! ,매수금액:", round(RealInvestMoney,2) ,  " 매수가:",NowClosePrice)



    
    NowInvestMoney = 0

    for iData in NowInvestList:
        NowInvestMoney += iData['InvestMoney']



    
    InvestMoney = RemainInvestMoney + NowInvestMoney

    if TopCnt - len(NowInvestList) + 1 > 0:
        InvestMoneyCell = (RemainInvestMoney / (TopCnt - len(NowInvestList) +1 )) * (1.0 - fee)


    InvestCoinListStr = ""
    print("\n\n------------------------------------")
    for iData in NowInvestList:
        InvestCoinListStr += GetStockName(iData['stock_code'], StockDataList)  + " "
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
