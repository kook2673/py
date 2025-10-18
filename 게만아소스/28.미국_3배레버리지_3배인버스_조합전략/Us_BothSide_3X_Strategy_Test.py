'''

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

백테스팅은 내PC에서 해야 서버 자원을 아끼고 투자 성과 그래프도 확인할 수 있습니다!
이 포스팅을 정독하시고 다양한 기간으로 백테스팅 해보세요!!!
https://blog.naver.com/zacra/223180500307

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$


관련 포스팅

미국 주식 양방향 매매 최종판 (TQQQ / SQQQ, SOXL / SOXS) - 하락장에서도 안정적 수익내기
https://blog.naver.com/zacra/223097613599

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
import matplotlib.pyplot as plt
import time
import FinanceDataReader as fdr

#계좌 선택.. "VIRTUAL" 는 모의 계좌!
Common.SetChangeMode("VIRTUAL") #REAL or VIRTUAL



#이렇게 직접 금액을 지정해도 된다!!
TotalMoney = 10000000

fee = 0.0035 #수수료+세금+슬리피지 세팅!


print("테스트하는 총 금액: $", round(TotalMoney))

########################################################################
########################################################################
'''
아래 코드를  통해 투자 비중을 조절해 보세요.
지금은 7:3 비중으로 투자한다고 가정한 설정이겠죠?

만약 인버스만 투자한 결과를 보고 싶다면 레버리지의 비중을 0으로 만들거나 잠시 삭제하고(주석처리) 테스트하시면 됩니다!
'''
########################################################################
########################################################################

InvestStockList = list()

#테스트할 종목을 아래와 같은 예로 구성하세요~!
#'''
InvestDataDict = dict()
InvestDataDict['ticker'] = "TQQQ" 
InvestDataDict['rate'] = 0.35
InvestStockList.append(InvestDataDict)

InvestDataDict = dict()
InvestDataDict['ticker'] = "SOXL" 
InvestDataDict['rate'] = 0.35
InvestStockList.append(InvestDataDict)
#'''

#테스트할 종목을 아래와 같은 예로 구성하세요~!
#'''
InvestDataDict = dict()
InvestDataDict['ticker'] = "SQQQ" 
InvestDataDict['rate'] = 0.15
InvestStockList.append(InvestDataDict)

InvestDataDict = dict()
InvestDataDict['ticker'] = "SOXS" 
InvestDataDict['rate'] = 0.15
InvestStockList.append(InvestDataDict)
#'''

ResultList = list()
AvgPrice = 0


TotalResultDict= dict()


for stock_data in InvestStockList:

    stock_code = stock_data['ticker']

    print("\n----stock_code: ", stock_code)

    stock_name = stock_code

    InvestMoney = TotalMoney * stock_data['rate']
    

    print(stock_name, " 종목당 할당 투자금:", InvestMoney)



    DivNum = 40.0


    InvestMoneyCell = InvestMoney / DivNum
    RealInvestMoney = 0
    RemainInvestMoney = InvestMoney

    BuyCnt = 0 #회차
    TotalBuyAmt = 0 #매수 수량
    TotalPureMoney = 0 #매수 금액


    #일봉 정보를 가지고 온다!
    df = Common.GetOhlcv("US",stock_code, 3500) 

    print(len(df))

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
    df['50ma'] = df['close'].rolling(50).mean()
    df['60ma'] = df['close'].rolling(60).mean()
    df['100ma'] = df['close'].rolling(100).mean()
    df['200ma'] = df['close'].rolling(200).mean()
    df['210ma'] = df['close'].rolling(210).mean()
    ########################################

    df.dropna(inplace=True) #데이터 없는건 날린다!
    pprint.pprint(df)
    
    #df = df[:len(df)-100]


    IsBuy = False #매수 했는지 여부
    SuccesCnt = 0   #익절 숫자
    FailCnt = 0     #손절 숫자


    IsNoCash = False


    IsFirstDateSet = False
    FirstDateStr = ""
    FirstDateIndex = 0
   

    TotalMoneyList = list()
    AvgPrice = 0



    for i in range(len(df)):

        #종가 기준으로 테스트 하려면 open 을 close로 변경!!
        #NowOpenPrice = df['close'].iloc[i]  
        #PrevOpenPrice = df['close'].iloc[i-1]  
        
        
        NowOpenPrice = df['open'].iloc[i]  
        PrevOpenPrice = df['open'].iloc[i-1]  
        PrevClosePrice = df['close'].iloc[i-1]
        
        
            
        #매수된 상태라면..
        if IsBuy == True:

            #투자중이면 매일매일 수익률 반영!
            RealInvestMoney = RealInvestMoney * (1.0 + ((NowOpenPrice - PrevOpenPrice) / PrevOpenPrice))



            TargetRate = 10.0 / 100.0 #목표수익률 10%!!!
            

            TakePrice = AvgPrice * (1.0 + TargetRate) #익절가격


            #진입(매수)가격 대비 변동률
            Rate = (NowOpenPrice - AvgPrice) / AvgPrice

            RevenueRate = (Rate - fee)*100.0 #수익률 계산
        
            #TQQQ, SOXL의 경우
            if stock_code == 'TQQQ' or stock_code == 'SOXL':

                #목표 수익을 달성했거나 회차가 다 찼거나.. 남은 현금이 없을 때..
                if (TakePrice <= NowOpenPrice) or BuyCnt >= DivNum or IsNoCash == True:

                            
                    Disparity = (PrevClosePrice/df['5ma'].iloc[i-1])*100.0
                    
                    st_disparity = 102
                    
                    if stock_code == 'TQQQ':
                        st_disparity = 103

                    #목표수익률을 달성했다면 바로 익절! 정리!!
                    if TakePrice <= NowOpenPrice and Disparity > st_disparity :


                        InvestMoney = RemainInvestMoney + (RealInvestMoney * (1.0 - fee))  #수수료 및 세금, 슬리피지 반영!

                        print(stock_code ," ", df.iloc[i].name, " " ,BuyCnt, " >>>>>>>>매도! 누적수량:",TotalBuyAmt,">>>>>>>> 매도! \n투자금 수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2) , " 이전종가:",round(PrevClosePrice,2),"\n\n")
                        print("\n\n")

                        BuyCnt = 0

                        TotalBuyAmt = 0
                        TotalPureMoney = 0

                        RealInvestMoney = 0
                        RemainInvestMoney = InvestMoney
                        AvgPrice = 0



                        SuccesCnt += 1
                        IsBuy = False #매도했다


                    #그게 아니라면 돈이 없거나 40회 다 찬거다.. 1/4 쿼터 손절!!!
                    else:
                        
                        Test_div = 8.0
                        
                        if df['20ma'].iloc[i-2] > df['20ma'].iloc[i-1] and df['60ma'].iloc[i-2] > df['60ma'].iloc[i-1]:
                            Test_div = 6.0
                        
                        BuyCnt = BuyCnt - int(BuyCnt / Test_div)

                        CutAmt = int(TotalBuyAmt / Test_div)


                        NowFee = (CutAmt*NowOpenPrice) * fee

                        #해당 수량을 감소 시키고! 금액도 감소시킨다!
                        TotalBuyAmt -= CutAmt
                        TotalPureMoney -= (CutAmt*NowOpenPrice)
                        
                        RealInvestMoney -= (CutAmt*NowOpenPrice) #실제 들어간 투자금
                        
                        RemainInvestMoney += (CutAmt*NowOpenPrice) #남은 투자금!
                        RemainInvestMoney -= NowFee

                        InvestMoney = RemainInvestMoney + RealInvestMoney

                        #AvgPrice = TotalPureMoney / TotalBuyAmt
                        
                        InvestMoneyCell = InvestMoney / DivNum
                        print(stock_code ," ", df.iloc[i].name, " " ,BuyCnt, " >>>>>>>매도수량:", CutAmt ,"누적수량:",TotalBuyAmt," 평단: ",round(AvgPrice,2),">>>>>>>> 쿼터손절!  \n투자금 수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2), " 이전종가:",round(PrevClosePrice,2),"\n\n")

                        FailCnt +=1
                        IsNoCash = False
                    
                    
                

                else:
                    #아직 회차가 다 안찼다면! 매일 매수를 진행한다!
                    if BuyCnt < DivNum:


                        
                        ###################### 개선된 점 #######################
                        #########################################################
                        IsBuyGo = False
                        
                        if df['100ma'].iloc[i-1] > df['close'].iloc[i-1]: # 개선된 점 GMA  

                            if df['3ma'].iloc[i-2] < df['3ma'].iloc[i-1]: # 개선된 점 GMA  
                                IsBuyGo = True

                        else: #200일선 위에 있는 상승장엔 기존 처럼 매일 매수!
      
                            IsBuyGo = True
                        
                        
                            
                        #########################################################
                        #########################################################


                        if df['rsi'].iloc[i-1] >= 80: # 개선된 점 GMA #RSI 80이상의 과매도 구간에선 회차 매수 안함!!
                            IsBuyGo = False



                        ###################### 개선된 점 #######################
                        #########################################################
                        
                        Disparity = (PrevClosePrice/df['5ma'].iloc[i-1])*100.0
                        
                        st_disparity = 97
                        
                        if stock_code == 'SOXL':
                            st_disparity = 108
                            
                        
                        #200일선 위에 있다가 아래로 종가가 떨어지면... 다음날 시가로 모두 매도!!!
                        if (df['200ma'].iloc[i-2] < df['close'].iloc[i-2]  and df['200ma'].iloc[i-1] > df['close'].iloc[i-1]) and Disparity < st_disparity:
                        

                            InvestMoney = RemainInvestMoney + (RealInvestMoney * (1.0 - fee))  #수수료 및 세금, 슬리피지 반영!

                            print("-----> !!!CUT!!!!", stock_code ," ", df.iloc[i].name, " " ,BuyCnt, " >>>>>>>>매도! 누적수량:",TotalBuyAmt,">>>>>>>> 매도! \n투자금 수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2), " 이전종가:",round(PrevClosePrice,2),"\n\n")
                            print("\n\n")

                            BuyCnt = 0

                            TotalBuyAmt = 0
                            TotalPureMoney = 0

                            RealInvestMoney = 0
                            RemainInvestMoney = InvestMoney
                            AvgPrice = 0



                            FailCnt +=1
                            IsBuy = False #매도했다
                            
                            
                            
                            IsBuyGo = False
                        #########################################################
                        #########################################################
                        
                        
                        
                        if IsBuyGo == True:


                            BuyAmt = float(int(InvestMoneyCell /  NowOpenPrice)) #매수 가능 수량을 구한다!

                            NowFee = (BuyAmt*NowOpenPrice) * fee

                            #남은 돈이 있다면 매수 한다!!
                            if RemainInvestMoney >= (BuyAmt*NowOpenPrice) + NowFee:

                                TotalBuyAmt += BuyAmt
                                TotalPureMoney += (BuyAmt*NowOpenPrice)

                                RealInvestMoney += (BuyAmt*NowOpenPrice) #실제 들어간 투자금

                                RemainInvestMoney -= (BuyAmt*NowOpenPrice) #남은 투자금!
                                RemainInvestMoney -= NowFee

                                InvestMoney = RealInvestMoney + RemainInvestMoney #실제 잔고는 실제 들어간 투자금 + 남은 투자금!

                                BuyCnt += 1



                                AvgPrice = ((AvgPrice * (TotalBuyAmt-BuyAmt)) + (BuyAmt*NowOpenPrice)) / TotalBuyAmt
                                
                                print(stock_code ," ", df.iloc[i].name, " " ,BuyCnt, "회차 >>>>>>>매수수량:", BuyAmt ,"누적수량:",TotalBuyAmt," 평단: ",round(AvgPrice,2),">>>>>>>> 매수!  \n투자금 수익률: ", round(RevenueRate,2) , "% ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2), " 이전종가:",round(PrevClosePrice,2),"\n")

                            #남은 돈이 없다? 손절이 필요하다!
                            else:
                                InvestMoney = RemainInvestMoney + RealInvestMoney
                                print(stock_code ," ", df.iloc[i].name, " " ,BuyCnt, "회차 >>>>>> 누적수량:",TotalBuyAmt," 평단: ",round(AvgPrice,2)," >>>>>>>>> 현금 소진상태..  \n투자금 수익률: ", round(RevenueRate,2) , "% ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2), " 이전종가:",round(PrevClosePrice,2),"\n")
                                IsNoCash = True

                        else:
                            InvestMoney = RealInvestMoney + RemainInvestMoney 
                            
            # SQQQ, SOXL의 인버스의 경우
            else:

                IsSellGo = False
                
                Disparity = (PrevClosePrice/df['5ma'].iloc[i-1])*100.0

                if  (Disparity > 102 or Disparity < 98):

                    IsSellGo = True
                    
                if IsSellGo == True:

                    InvestMoney = RemainInvestMoney + (RealInvestMoney * (1.0 - fee))  #수수료 및 세금, 슬리피지 반영!

                    print("-----> !!!CUT!!!!", stock_code ," ", df.iloc[i].name, " " ,BuyCnt, " >>>>>>>>매도! 누적수량:",TotalBuyAmt,">>>>>>>> 매도! \n투자금 수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2), " 이전종가:",round(PrevClosePrice,2),"\n\n")
                    print("\n\n")

                    BuyCnt = 0

                    TotalBuyAmt = 0
                    TotalPureMoney = 0

                    RealInvestMoney = 0
                    RemainInvestMoney = InvestMoney
                    AvgPrice = 0


                    if RevenueRate > 0:
                        SuccesCnt += 1
                    else:
                        FailCnt +=1
                    IsBuy = False #매도했다
                    
                    
            
                                     
        #첫 매수가 진행이 안되었다!
        if IsBuy == False and i > 1:

            if IsFirstDateSet == False:
                FirstDateStr = df.iloc[i].name
                FirstDateIndex = i-1
                IsFirstDateSet = True
                
            if stock_code == 'TQQQ' or stock_code == 'SOXL':
                ###################### 개선된 점 #######################
                #########################################################
                
                    
                if df['5ma'].iloc[i-1] < df['close'].iloc[i-1]: #전일 종가 5일선 위에 있을 때만 
                #########################################################
                #########################################################
                    

                    ###################### 개선된 점 #######################
                    #########################################################
                    if df['200ma'].iloc[i-1] > df['close'].iloc[i-1]: #200일선 아래에 있을 땐 40분할
                        DivNum = 35
                    else: # 개선된 점 GMA  # 200일선 위에 있을 땐 이평선에 따라 분할 차등!
                        
                        st_num = 55
                        
                        if stock_code == 'TQQQ':
                            st_num = 54
                            
                                
                        DivNum = st_num

                        
                        if df['100ma'].iloc[i-1] <= df['close'].iloc[i-1]:
                            DivNum -= 15


                        if df['60ma'].iloc[i-1] <= df['close'].iloc[i-1]:
                            DivNum -= 8


                        if df['20ma'].iloc[i-1] <= df['close'].iloc[i-1]:
                            DivNum -= 7    
                            
                            
                        if DivNum == st_num:
                            DivNum = 35    
                    #########################################################
                    #########################################################
                    
                    


                    #첫 매수를 진행한다!!!!
                    InvestMoneyCell = InvestMoney / DivNum


                    BuyAmt = float(int(InvestMoneyCell /  NowOpenPrice)) #매수 가능 수량을 구한다!

                    NowFee = (BuyAmt*NowOpenPrice) * fee

                    TotalBuyAmt += BuyAmt
                    TotalPureMoney += (BuyAmt*NowOpenPrice)

                    RealInvestMoney += (BuyAmt*NowOpenPrice) #실제 들어간 투자금


                    RemainInvestMoney -= (BuyAmt*NowOpenPrice) #남은 투자금!
                    RemainInvestMoney -= NowFee

                    InvestMoney = RealInvestMoney + RemainInvestMoney  #실제 잔고는 실제 들어간 투자금 + 남은 투자금!

                    BuyCnt += 1
                    
                    AvgPrice = NowOpenPrice

                    print(stock_code ," ", df.iloc[i].name, " " ,BuyCnt, "회차 >>>> 매수수량:", BuyAmt ,"누적수량:",TotalBuyAmt," 평단: ",round(NowOpenPrice,2)," >>>>>>> 매수시작! \n투자금 수익률: 0% ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2), " 이전종가:",round(PrevClosePrice,2),"\n")
                    IsBuy = True #매수했다

                
            else:
                


                IsBuyGo = False

                
                

                Disparity = (PrevClosePrice/df['5ma'].iloc[i-1])*100.0

                if df['20ma'].iloc[i-1] > df['close'].iloc[i-1]:

                    if (df['low'].iloc[i-2] < df['low'].iloc[i-1]) and df['open'].iloc[i-1] < df['close'].iloc[i-1] :

                        if stock_code == 'SOXS':
                            if df['volume'].iloc[i-2] < df['volume'].iloc[i-1] and df['open'].iloc[i-2] > df['close'].iloc[i-2] and Disparity < 102:
                                IsBuyGo = True
                        else:
                            if df['open'].iloc[i-2] > df['close'].iloc[i-2] and Disparity < 103:
                                IsBuyGo = True

                                

                if stock_code == 'SOXS':
                    if  min(df['open'].iloc[i-3],df['close'].iloc[i-3]) < min(df['open'].iloc[i-2],df['close'].iloc[i-2]) < min(df['open'].iloc[i-1],df['close'].iloc[i-1]) and df['open'].iloc[i-1] < df['close'].iloc[i-1] and Disparity < 102:
                        IsBuyGo = True



                                
                if IsBuyGo == True:
                    

                    #첫 매수를 진행한다!!!!
                    InvestMoneyCell = InvestMoney * (1.0 - fee)


                    BuyAmt = float(int(InvestMoneyCell /  NowOpenPrice)) #매수 가능 수량을 구한다!

                    NowFee = (BuyAmt*NowOpenPrice) * fee

                    TotalBuyAmt += BuyAmt
                    TotalPureMoney += (BuyAmt*NowOpenPrice)

                    RealInvestMoney += (BuyAmt*NowOpenPrice) #실제 들어간 투자금


                    RemainInvestMoney -= (BuyAmt*NowOpenPrice) #남은 투자금!
                    RemainInvestMoney -= NowFee

                    InvestMoney = RealInvestMoney + RemainInvestMoney  #실제 잔고는 실제 들어간 투자금 + 남은 투자금!

                    BuyCnt += 1
                    
                    AvgPrice = NowOpenPrice

                    print(stock_code ," ", df.iloc[i].name, " " ,BuyCnt, "회차 >>>> 매수수량:", BuyAmt ,"누적수량:",TotalBuyAmt," 평단: ",round(NowOpenPrice,2)," >>>>>>> 매수시작! \n투자금 수익률: 0% ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2), " 이전종가:",round(PrevClosePrice,2),"\n")

                    IsBuy = True #매수했다

            
        TotalMoneyList.append(InvestMoney)

    #####################################################
    #####################################################
    #####################################################
    #'''
  


    #결과 정리 및 데이터 만들기!!
    if len(TotalMoneyList) > 0:

        TotalResultDict[stock_code] = TotalMoneyList

        resultData = dict()

        
        resultData['Ticker'] = stock_code


        result_df = pd.DataFrame({ "Total_Money" : TotalMoneyList}, index = df.index)

        result_df['Ror'] = result_df['Total_Money'].pct_change() + 1
        result_df['Cum_Ror'] = result_df['Ror'].cumprod()

        result_df['Highwatermark'] =  result_df['Cum_Ror'].cummax()
        result_df['Drawdown'] = (result_df['Cum_Ror'] / result_df['Highwatermark']) - 1
        result_df['MaxDrawdown'] = result_df['Drawdown'].cummin()

        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        pprint.pprint(result_df)
        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

        resultData['DateStr'] = str(FirstDateStr) + " ~ " + str(result_df.iloc[-1].name)

        resultData['OriMoney'] = result_df['Total_Money'].iloc[FirstDateIndex]
        resultData['FinalMoney'] = result_df['Total_Money'].iloc[-1]
        resultData['OriRevenueHold'] =  (df['open'].iloc[-1]/df['open'].iloc[FirstDateIndex] - 1.0) * 100.0 
        resultData['RevenueRate'] = ((result_df['Cum_Ror'].iloc[-1] -1.0)* 100.0)
        resultData['MDD'] = result_df['MaxDrawdown'].min() * 100.0

        resultData['SuccesCnt'] = SuccesCnt
        resultData['FailCnt'] = FailCnt

        
        ResultList.append(resultData)



        for idx, row in result_df.iterrows():
            print(idx, " " , row['Total_Money'], " "  , row['Cum_Ror'])
            



#데이터를 보기좋게 프린트 해주는 로직!
print("\n\n--------------------")

TotalHoldRevenue = 0


InvestCnt = float(len(ResultList))

for result in ResultList:

    print("--->>>",result['DateStr'].replace("00:00:00",""),"<<<---")
    print(result['Ticker'] )
    print("최초 금액: ", format(round(result['OriMoney'],2),',') , " 최종 금액: ", format(round(result['FinalMoney'],2),','))
    print("수익률:", round(result['RevenueRate'],2) , "%")
    print("단순 보유 수익률:", round(result['OriRevenueHold'],2) , "%")
    print("MDD:", round(result['MDD'],2) , "%")

    if result['SuccesCnt'] > 0:
        print("성공 횟수 :", result['SuccesCnt'] )

    if result['FailCnt'] > 0:
        print("손절 횟수 :", result['FailCnt'] )        


    TotalHoldRevenue += result['OriRevenueHold']


    print("\n--------------------\n")


if len(ResultList) > 0:
    print("####################################")
    

    # 딕셔너리의 리스트들의 길이를 가져옴
    length = len(list(TotalResultDict.values())[0])

    # 종합 리스트 초기화
    FinalTotalMoneyList = [0] * length

    # 딕셔너리에서 리스트를 가져와 합산
    for my_list in TotalResultDict.values():
        # 리스트의 각 요소를 합산
        for i, value in enumerate(my_list):
            FinalTotalMoneyList[i] += value


    result_df = pd.DataFrame({ "Total_Money" : FinalTotalMoneyList}, index = df.index)

    result_df['Ror'] = result_df['Total_Money'].pct_change() + 1
    result_df['Cum_Ror'] = result_df['Ror'].cumprod()

    result_df['Highwatermark'] =  result_df['Cum_Ror'].cummax()
    result_df['Drawdown'] = (result_df['Cum_Ror'] / result_df['Highwatermark']) - 1
    result_df['MaxDrawdown'] = result_df['Drawdown'].cummin()


    #'''
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
        
    #'''

    

    TotalOri = result_df['Total_Money'].iloc[1]
    TotalFinal = result_df['Total_Money'].iloc[-1]

    TotalMDD = result_df['MaxDrawdown'].min() * 100.0 #MDD를 종합적으로 계산!


    print("---------- 총 결과 ----------")
    print("최초 금액:", format(int(round(TotalOri,0)), ',') , " 최종 금액:",  format(int(round(TotalFinal,0)), ',') , "\n수익률:", round(((TotalFinal - TotalOri) / TotalOri) * 100,2) ,"% (단순보유수익률:" ,round(TotalHoldRevenue/InvestCnt,2) ,"%) 평균 MDD:",  round(TotalMDD,2),"%")
    print("------------------------------")
    print("####################################")
