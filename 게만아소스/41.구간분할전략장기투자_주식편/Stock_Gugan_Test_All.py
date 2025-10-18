#-*-coding:utf-8 -*-
'''
 
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

백테스팅은 내PC에서 해야 서버 자원을 아낄수 있어요
https://blog.naver.com/zacra/223180500307

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$




관련 포스팅

https://blog.naver.com/zacra/223240069613

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
import time

import time
from datetime import datetime



#계좌 선택.. "VIRTUAL" 는 모의 계좌!
Common.SetChangeMode("VIRTUAL") #REAL or VIRTUAL

time_info = time.gmtime()
year_n = time_info.tm_year


####################################

#투자원금
InvestTotalMoney = 10000
#백테스팅 시작일!
StartYear = 2021
#테스트할 종목
InvestStockList = ["TSLA"]

####################################



RealTotalList = list()

df_data = dict() #일봉 데이타를 저장할 구조



for stock_code in InvestStockList:    


    #위 연도만 바꾸면 적절한 개수의 일봉정보를 가져오도록.. 넉넉하게 ㅎ
    data_num = ((year_n - StartYear) + 2) * 365

    df = Common.GetOhlcv("US", stock_code,data_num) 

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
    df['100ma'] = df['close'].rolling(100).mean()
    ########################################



    df.dropna(inplace=True) #데이터 없는건 날린다!
   

    #df = df[:len(df)-150]

    df_data[stock_code] = df




##### for문을 사용해 기간과 분할 수를 조합하여 백테스팅을 해봅니다! ###########

DivNum = 0
target_period = 0

for target_period_st in range(1,7):
    for div_num in range(3,21):



        #time.sleep(0.2)
        ResultList = list()



        for stock_code in InvestStockList:    
            InvestMoney = InvestTotalMoney / len(InvestStockList) #테스트 총 금액을 종목 수로 나눠서 각 할당 투자금을 계산한다!
   


            #print(stock_code, " 종목당 할당 투자금:", InvestMoney)

            ####################
            #구간 분할
            DivNum = div_num 
            ####################
            ###############################
            #고점 저점을 구할 기준이 되는 기간
            target_period = target_period_st * 10  #10을 곱해줬다. 10,20,30,40,50,60 기간을 테스트!!!
            ###############################


            InvestMoneyCell = InvestMoney / DivNum
            RealInvestMoney = 0
            RemainInvestMoney = InvestMoney

            TotalBuyAmt = 0 #매수 수량
            TotalPureMoney = 0 #매수 금액



            #일봉 정보를 가지고 온다!
            #사실 분봉으로 테스트 해보셔도 됩니다. 저는 일봉으로~^^
            df = df_data[stock_code]
            #print(len(df))




            IsBuy = False #매수 했는지 여부
            BuyCnt = 0   #익절 숫자
            SellCnt = 0     #손절 숫자

            fee = 0.0025 #수수료+세금+슬리피지를 매수매도마다 0.25%로 세팅!

            IsFirstDateSet = False
            FirstDateStr = ""
            FirstDateIndex = 0

        

            TotlMoneyList = list()

            AvgPrice = 0

            
            result_step = 1

        #df = df[:len(df)-3000]

        

            for i in range(len(df)):

                date = df.iloc[i].name
                
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



                #종가 기준으로 테스트 하려면 open 을 close로 변경!!
                #NowOpenPrice = df['close'].iloc[i]  
                #PrevOpenPrice = df['close'].iloc[i-1]  
                
                
                NowOpenPrice = df['open'].iloc[i]  
                PrevOpenPrice = df['open'].iloc[i-1]  
                

                
            
                if IsBuy == True:

                    #투자중이면 매일매일 수익률 반영!
                    RealInvestMoney = RealInvestMoney * (1.0 + ((NowOpenPrice - PrevOpenPrice) / PrevOpenPrice))


                    InvestMoney = RealInvestMoney + RemainInvestMoney 
                    InvestMoneyCell = InvestMoney / DivNum

                    Rate = 0
                    RevenueRate = 0
                    
                    if AvgPrice > 0:
                    
                        #진입(매수)가격 대비 변동률
                        Rate = (NowOpenPrice - AvgPrice) / AvgPrice

                        RevenueRate = (Rate - fee)*100.0 #수익률 계산


                    #현재 구간을 구하는 코드
                    high_list = list()
                    low_list = list()
                    for index in range(i-1,i-(target_period+1),-1):
                        high_list.append(df['high'].iloc[index])
                        low_list.append(df['low'].iloc[index])


                    high_price = float(max(high_list))
                    low_price =  float(min(low_list))
                    

                    Gap = (high_price - low_price) / DivNum

                    now_step = DivNum

                    for step in range(1,DivNum+1):

                        if NowOpenPrice < low_price + (Gap * step):
                            now_step = step
                            break
                    #print("-----------------",now_step,"-------------------\n")
                    
                
        

                    #스텝(구간)이 다르다!
                    if result_step != now_step:

                        step_gap = now_step - result_step

                        result_step = now_step

                        if step_gap >= 1: #스텝이 증가!! 매수!!

                            if df['20ma'].iloc[i-1] < df['close'].iloc[i-1]:

                                BuyAmt = float(InvestMoneyCell*abs(step_gap)  /  NowOpenPrice) #매수 가능 수량을 구한다!
                                

                                NowFee = (BuyAmt*NowOpenPrice) * fee


                                #남은 돈이 있다면 매수 한다!!
                                if RemainInvestMoney >= (BuyAmt*NowOpenPrice) + NowFee :

                                    TotalBuyAmt += BuyAmt
                                    TotalPureMoney += (BuyAmt*NowOpenPrice)

                                    RealInvestMoney += (BuyAmt*NowOpenPrice) #실제 들어간 투자금

                                    RemainInvestMoney -= (BuyAmt*NowOpenPrice) #남은 투자금!
                                    RemainInvestMoney -= NowFee

                                    InvestMoney = RealInvestMoney + RemainInvestMoney #실제 잔고는 실제 들어간 투자금 + 남은 투자금!

                                    
                                            
                                    AvgPrice = ((AvgPrice * (TotalBuyAmt-BuyAmt)) + (BuyAmt*NowOpenPrice)) / TotalBuyAmt

                                    InvestMoneyCell = InvestMoney / DivNum
                                    #print(stock_code ," ", df.iloc[i].name, " 구간" ,result_step, ">>>>>>>매수수량:", BuyAmt ,"누적수량:",TotalBuyAmt," 평단: ",round(AvgPrice,2),">>>>>>>> 매수!  \n투자금 수익률: ", round(RevenueRate,2) , "% ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2),"\n")

                                    BuyCnt += 1
                                else:

                                    #print(stock_code ," ", df.iloc[i].name, " 구간" ,result_step, "!!!!!!!!!!해당 수량 매수 금액 부족!!!!!!!!!!!누적수량:",TotalBuyAmt," 평단: ",round(AvgPrice,2)," \n투자금 수익률: ", round(RevenueRate,2) , "% ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2),"\n")

        
                                    InvestMoney = RealInvestMoney + RemainInvestMoney 
                            else:
                                #print(stock_code ," ", df.iloc[i].name, " 구간" ,result_step, "!!!!!!!!!!구간이 증가되 매수해야 하지만 이평선 조건 안맞음!!!!!!!!!!! 누적수량:",TotalBuyAmt," 평단: ",round(AvgPrice,2)," \n투자금 수익률: ", round(RevenueRate,2) , "% ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2),"\n")

                                InvestMoney = RealInvestMoney + RemainInvestMoney 


                        elif step_gap <= -1: #스텝이 감소! 매도!!

                            if (df['5ma'].iloc[i-1] > df['close'].iloc[i-1])  and TotalBuyAmt > 0:

                                SellAmt = float(InvestMoneyCell*abs(step_gap)  /  NowOpenPrice) #매수 가능 수량을 구한다!


                                NowFee = (SellAmt*NowOpenPrice) * fee

                                #남은 수량이 있다면 매도 한다!!
                                if TotalBuyAmt >= abs(SellAmt):

                                    #해당 수량을 감소 시키고! 금액도 감소시킨다!
                                    TotalBuyAmt -= SellAmt
                                    TotalPureMoney -= (SellAmt*NowOpenPrice)
                                    
                                    RealInvestMoney -= (SellAmt*NowOpenPrice) #실제 들어간 투자금
                                    
                                    RemainInvestMoney += (SellAmt*NowOpenPrice) #남은 투자금!
                                    RemainInvestMoney -= NowFee

                                    InvestMoney = RemainInvestMoney + RealInvestMoney
                                    

                                    InvestMoneyCell = InvestMoney / DivNum
                                    #print(stock_code ," ", df.iloc[i].name, " 구간" ,result_step, " >>>>>>>매도수량:", SellAmt ,"누적수량:",TotalBuyAmt," 평단: ",round(AvgPrice,2),">>>>>>>> 매도!  \n투자금 수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2),"\n\n")

                                    SellCnt += 1
                                    
                                else:


                                    InvestMoney = RemainInvestMoney + (RealInvestMoney * (1.0 - fee))  #수수료 및 세금, 슬리피지 반영!

                                    TotalBuyAmt = 0
                                    TotalPureMoney = 0

                                    RealInvestMoney = 0
                                    RemainInvestMoney = InvestMoney
                                    AvgPrice = 0


                                    InvestMoneyCell = InvestMoney / DivNum
                                    #print(stock_code ," ", df.iloc[i].name, " 구간" ,result_step, " >>>>>>>모두 매도!!:", SellAmt ,"누적수량:",TotalBuyAmt," 평단: ",round(AvgPrice,2),">>>>>>>> 매도!  \n투자금 수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2),"\n\n")

                                    SellCnt += 1

                                    InvestMoney = RealInvestMoney + RemainInvestMoney 
                            else:
                                #print(stock_code ," ", df.iloc[i].name, " 구간" ,result_step, "!!!!!!!!!!구간이 감수되 매도해야 하지만 이평선 조건 안맞음!!!!!!!!!!! 누적수량:",TotalBuyAmt," 평단: ",round(AvgPrice,2)," \n투자금 수익률: ", round(RevenueRate,2) , "% ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2),"\n")

                                InvestMoney = RealInvestMoney + RemainInvestMoney 


                        else:
                            InvestMoney = RealInvestMoney + RemainInvestMoney 
                            #print(stock_code ," ", df.iloc[i].name, " 구간" ,result_step, "!!!!!!!!!! 누적수량:",TotalBuyAmt," 평단: ",round(AvgPrice,2)," \n투자금 수익률: ", round(RevenueRate,2) , "% ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2),"\n")



                    else:
                        InvestMoney = RealInvestMoney + RemainInvestMoney 
                        #print(stock_code ," ", df.iloc[i].name, " 구간" ,result_step, "!!!!!!!!!!구간 변동 없음!!!!!!!!!! 누적수량:",TotalBuyAmt," 평단: ",round(AvgPrice,2)," \n투자금 수익률: ", round(RevenueRate,2) , "% ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2),"\n")

                    #print("\n")

                                    

            
                if IsBuy == False and i > 60 and  int(date_object.strftime("%Y")) >= StartYear:

                    if IsFirstDateSet == False:
                        FirstDateStr = df.iloc[i].name
                        FirstDateIndex = i-1
                        IsFirstDateSet = True





                    #첫 매수를 진행한다!!!!
                    InvestMoneyCell = InvestMoney / DivNum


                    
                    #구간을 구하는 코드
                    high_list = list()
                    low_list = list()
                    for index in range(i-1,i-(target_period+1),-1):
                        #print(stock_code ," ", df.iloc[index].name)
                        high_list.append(df['high'].iloc[index])
                        low_list.append(df['low'].iloc[index])


                    high_price = float(max(high_list))
                    low_price =  float(min(low_list))

                    Gap = (high_price - low_price) / DivNum

                    

                    for step in range(1,DivNum+1):
                        if NowOpenPrice < low_price + (Gap * step):
                            result_step = step
                            break

                    #print("-----------------",result_step,"-------------------\n")

                    #if result_step >= 7:
                    BuyAmt = float(InvestMoneyCell /  NowOpenPrice) #매수 가능 수량을 구한다!

                    NowFee = (BuyAmt*NowOpenPrice) * fee

                    TotalBuyAmt += BuyAmt
                    TotalPureMoney += (BuyAmt*NowOpenPrice)

                    RealInvestMoney += (BuyAmt*NowOpenPrice) #실제 들어간 투자금


                    RemainInvestMoney -= (BuyAmt*NowOpenPrice) #남은 투자금!
                    RemainInvestMoney -= NowFee

                    InvestMoney = RealInvestMoney + RemainInvestMoney  #실제 잔고는 실제 들어간 투자금 + 남은 투자금!

                    BuyCnt += 1
                    
                    AvgPrice = NowOpenPrice

                    #print(stock_code ," ", df.iloc[i].name, " 구간" ,result_step, "회차 >>>> 매수수량:", BuyAmt ,"누적수량:",TotalBuyAmt," 평단: ",round(NowOpenPrice,2)," >>>>>>> 매수시작! \n투자금 수익률: 0% ,종목 잔고:",round(RemainInvestMoney,2), "+",round(RealInvestMoney,2), "=",round(InvestMoney,2)  , " 현재가:", round(NowOpenPrice,2),"\n")
                    IsBuy = True #매수했다
                    #print("\n")

                    
                TotlMoneyList.append(InvestMoney)

            #####################################################
            #####################################################
            #####################################################
            #'''
        


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

                #print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                #pprint.pprint(result_df)
                #print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

                resultData['DateStr'] = str(FirstDateStr) + " ~ " + str(result_df.iloc[-1].name)

                resultData['OriMoney'] = result_df['Total_Money'].iloc[FirstDateIndex]
                resultData['FinalMoney'] = result_df['Total_Money'].iloc[-1]
                resultData['OriRevenueHold'] =  (df['open'].iloc[-1]/df['open'].iloc[FirstDateIndex] - 1.0) * 100.0 
                resultData['RevenueRate'] = ((result_df['Cum_Ror'].iloc[-1] -1.0)* 100.0)
                resultData['MDD'] = result_df['MaxDrawdown'].min() * 100.0

                resultData['BuyCnt'] = BuyCnt
                resultData['SellCnt'] = SellCnt

                ResultList.append(resultData)


                #for idx, row in result_df.iterrows():
                #    print(idx, " " , row['Total_Money'], " "  , row['Cum_Ror'])
                    





        #데이터를 보기좋게 프린트 해주는 로직!
        #print("\n\n--------------------")
        
        TotalOri = 0
        TotalFinal = 0
        TotalHoldRevenue = 0
        TotalMDD= 0

        InvestCnt = float(len(ResultList))

        for result in ResultList:

            '''
            print("--->>>",result['DateStr'].replace("00:00:00",""),"<<<---")
            print(result['Ticker'] )
            print("최초 금액: ", str(format(round(result['OriMoney']), ',')) , " 최종 금액: ", str(format(round(result['FinalMoney']), ','))  )
            print("수익률:", round(result['RevenueRate'],2) , "%")
            print("단순 보유 수익률:", round(result['OriRevenueHold'],2) , "%")
            print("MDD:", round(result['MDD'],2) , "%")

            if result['BuyCnt'] > 0:
                print("매수 횟수 :", result['BuyCnt'] )

            if result['SellCnt'] > 0:
                print("매도 횟수 :", result['SellCnt'] )        
            '''

            TotalOri += result['OriMoney']
            TotalFinal += result['FinalMoney']

            TotalHoldRevenue += result['OriRevenueHold']
            TotalMDD += result['MDD']

            #print("\n--------------------\n")

        if TotalOri > 0:
            
            print("####################################")
            print("-- target_period", target_period, " -- DivNum : ", DivNum)
            print("---------- 총 결과 ----------")
            print("최초 금액:", str(format(round(TotalOri), ','))  , " 최종 금액:", str(format(round(TotalFinal), ',')), "\n수익률:", round(((TotalFinal - TotalOri) / TotalOri) * 100,2) ,"% (단순보유수익률:" ,round(TotalHoldRevenue/InvestCnt,2) ,"%) 평균 MDD:",  round(TotalMDD/InvestCnt,2),"%")
            print("------------------------------")
            print("####################################")

            ResultData = dict()

            ResultData['Period'] = target_period
            ResultData['DivNum'] = DivNum
            ResultData['RevenueRate'] = round(((TotalFinal - TotalOri) / TotalOri) * 100,2)
            ResultData['MDD'] = round(TotalMDD/InvestCnt,2)


            RealTotalList.append(ResultData)

        ResultList.clear()



 
        


print("\n\n >>>>>>>>>>>>>최종 결과 종합<<<<<<<<<<<")


df_all = pd.DataFrame(RealTotalList)

df_all = df_all.sort_values(by="RevenueRate",ascending=False)

print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
pprint.pprint(df_all.head(20))
print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>")




