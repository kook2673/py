#-*-coding:utf-8 -*-
'''


$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

백테스팅은 내PC에서 해야 서버 자원을 아끼고 투자 성과 그래프도 확인할 수 있습니다!
이 포스팅을 정독하시고 다양한 기간으로 백테스팅 해보세요!!!
https://blog.naver.com/zacra/223180500307

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$



관련 포스팅
https://blog.naver.com/zacra/223486828128

위 포스팅을 꼭 참고하세요!!!

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제공된 전략은 학습 및 테스트 목적으로 구성된 예시 코드이며
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.
   

주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!
   



'''

import pyupbit
import pandas as pd
import pprint


InvestList = ["KRW-BTC","KRW-ETH","KRW-SOL","KRW-XRP"]

AllRealTotalList = list()



MaxCount = 6000 #맥스 데이터 개수
EnCount = 0     #최근 데이터 삭제! 200으로 세팅하면 200개의 최근 데이터가 사라진다 (즉 과거 시점의 백테스팅 가능)


for coin_ticker in InvestList:

    print("\n----coin_ticker: ", coin_ticker)

    RealTotalList = list()


    #일봉 정보를 가지고 온다!
    df = pyupbit.get_ohlcv(coin_ticker,interval="day",count=MaxCount, period=0.3) #day/minute1/minute3/minute5/minute10/minute15/minute30/minute60/minute240/week/month


    ############# 이동평균선! ###############
    #for ma in range(3,121):
    #    df[str(ma) + 'ma'] = df['close'].rolling(ma).mean()
        
    ma_dfs = []

    # 이동 평균 계산
    for ma in range(3, 121):
        ma_df = df['close'].rolling(ma).mean().rename(str(ma) + 'ma')
        ma_dfs.append(ma_df)

    # 이동 평균 데이터 프레임을 하나로 결합
    ma_df_combined = pd.concat(ma_dfs, axis=1)

    # 원본 데이터 프레임과 결합
    df = pd.concat([df, ma_df_combined], axis=1)
    ########################################

    df.dropna(inplace=True) #데이터 없는건 날린다!
    
    df = df[:len(df)-EnCount]
    
    pprint.pprint(df)

    print("이평선 조합 체크 중....")
    for ma1 in range(3,51):
        for ma2 in range(20,121):
            
            if ma1 < ma2:
            

                InvestMoney = 1000000
                
                IsBuy = False #매수 했는지 여부
                BUY_PRICE = 0  #매수한 가격! 

                TryCnt = 0      #매매횟수
                SuccesCnt = 0   #익절 숫자
                FailCnt = 0     #손절 숫자


                fee = 0.0015 #수수료+슬리피지를 매수매도마다 0.15%로 세팅!

                #df = df[:len(df)-100] #최근 100거래일을 빼고 싶을 때


                TotlMoneyList = list()

                #'''
                #####################################################
                ##########골든 크로스에서 매수~ 데드크로스에서 매도~!##########
                #####################################################
                for i in range(len(df)):


                    NowOpenPrice = df['open'].iloc[i]  
                    PrevOpenPrice = df['open'].iloc[i-1]  
                    
                    
                    
                    if IsBuy == True:

                        #투자중이면 매일매일 수익률 반영!
                        InvestMoney = InvestMoney * (1.0 + ((NowOpenPrice - PrevOpenPrice) / PrevOpenPrice))
                                    
                        
                        if df[str(ma1)+'ma'].iloc[i-2] > df[str(ma2)+'ma'].iloc[i-2] and df[str(ma1)+'ma'].iloc[i-1] < df[str(ma2)+'ma'].iloc[i-1]:  #데드 크로스!


                            #진입(매수)가격 대비 변동률
                            Rate = (NowOpenPrice - BUY_PRICE) / BUY_PRICE

                            RevenueRate = (Rate - fee)*100.0 #수익률 계산

                            InvestMoney = InvestMoney * (1.0 - fee)  #수수료 및 세금, 슬리피지 반영!

                            #print(coin_ticker ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 매도!  수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:", round(InvestMoney,2)  , " ", df['open'].iloc[i])
                            #print("\n\n")


                            TryCnt += 1

                            if RevenueRate > 0: #수익률이 0보다 크다면 익절한 셈이다!
                                SuccesCnt += 1
                            else:
                                FailCnt += 1


                            IsBuy = False #매도했다

                    if IsBuy == False:

                    
                        if i >= 2 and df[str(ma1)+'ma'].iloc[i-2] < df[str(ma2)+'ma'].iloc[i-2] and df[str(ma1)+'ma'].iloc[i-1] > df[str(ma2)+'ma'].iloc[i-1]:  #골든 크로스!

                            BUY_PRICE = NowOpenPrice 

                            InvestMoney = InvestMoney * (1.0 - fee)  #수수료 및 세금, 슬리피지 반영!

                            #print(coin_ticker ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 매수! ,종목 잔고:", round(InvestMoney,2) , " ", df['open'].iloc[i])
                            IsBuy = True #매수했다

                    
                    TotlMoneyList.append(InvestMoney)

                #####################################################
                #####################################################
                #####################################################
                #'''
                



                #결과 정리 및 데이터 만들기!!
                if len(TotlMoneyList) > 0:

                    resultData = dict()

                    
                    resultData['Ticker'] = coin_ticker


                    result_df = pd.DataFrame({ "Total_Money" : TotlMoneyList}, index = df.index)

                    result_df['Ror'] = result_df['Total_Money'].pct_change() + 1
                    result_df['Cum_Ror'] = result_df['Ror'].cumprod()

                    result_df['Highwatermark'] =  result_df['Cum_Ror'].cummax()
                    result_df['Drawdown'] = (result_df['Cum_Ror'] / result_df['Highwatermark']) - 1
                    result_df['MaxDrawdown'] = result_df['Drawdown'].cummin()

                    resultData['DateStr'] = str(result_df.iloc[0].name) + " ~ " + str(result_df.iloc[-1].name)

                    resultData['OriMoney'] = result_df['Total_Money'].iloc[0]
                    resultData['FinalMoney'] = result_df['Total_Money'].iloc[-1]
                    resultData['OriRevenueHold'] =  (df['open'].iloc[-1]/df['open'].iloc[0] - 1.0) * 100.0 
                    resultData['RevenueRate'] = ((result_df['Cum_Ror'].iloc[-1] -1.0)* 100.0)
                    resultData['MDD'] = result_df['MaxDrawdown'].min() * 100.0

                    resultData['TryCnt'] = TryCnt
                    resultData['SuccesCnt'] = SuccesCnt
                    resultData['FailCnt'] = FailCnt

                    
        
                    #'''
                    print("############ 전체기간 ##########")
                                                
                    print("-- ma1", ma1, " -- ma2 : ", ma2)
                    print("---------- 총 결과 ----------")
                    print("최초 금액:", str(format(round(resultData['OriMoney']), ','))  , " 최종 금액:", str(format(round(resultData['FinalMoney']), ',')), "\n수익률:", format(round(((resultData['FinalMoney'] - resultData['OriMoney']) / resultData['OriMoney']) * 100,2),',') ,"% (단순보유수익률:" ,format(round(resultData['OriRevenueHold'],2),',') ,"%) MDD:",  round(resultData['MDD'],2),"%")
                    print("------------------------------")
                    print("####################################")
                    #'''

                    FinalResultData = dict()
                    FinalResultData['day_str'] = resultData['DateStr']
                    FinalResultData['coin_ticker'] = coin_ticker
                    FinalResultData['ma_str'] = str(ma1) + " " + str(ma2) 
                    FinalResultData['RevenueRate'] = round(((resultData['FinalMoney'] - resultData['OriMoney']) / resultData['OriMoney']) * 100,2)
                    FinalResultData['MDD'] = round(resultData['MDD'],2)


                    RealTotalList.append(FinalResultData)
                    
                    TotlMoneyList.clear()
                    
       
    AllRealTotalList.append(RealTotalList)
    
    
    print(coin_ticker, " 체크 끝!!!!!!!")
    print("#####################################################################")
    
    
print("\n\n\n>>>>>>>>>>>>>>>>>>>최종결과<<<<<<<<<<<<<<<<<<<<<<<<<")
for ResultList in AllRealTotalList:
    
    df_all = pd.DataFrame(ResultList)
    
    print("#####################################################################")
    print("#####################################################################\n")
    Ticker = df_all['coin_ticker'].iloc[-1]
    print("대상 종목 : ", Ticker)
    print("테스트 기간: ", df_all['day_str'].iloc[-1],"\n")
    
    df_all = df_all.drop('day_str', axis=1)
    df_all = df_all.drop('coin_ticker', axis=1)
    
    df_all['RevenueRate_rank'] = df_all['RevenueRate'].rank(ascending=True)
    df_all['MDD_rank'] = df_all['MDD'].rank(ascending=True)
    df_all['Score'] = df_all['RevenueRate_rank'] + df_all['MDD_rank']

    df_all = df_all.sort_values(by="RevenueRate_rank",ascending=False)
    print(">>>>>>>>>> ",Ticker," 수익률 TOP10 >>>>>>>>>>>>>>>>")
    pprint.pprint(df_all.head(10))
    
    df_all = df_all.sort_values(by="MDD_rank",ascending=False)
    print("\n>>>>>>>>>> ",Ticker," MDD TOP10 >>>>>>>>>>>>>>>>")
    pprint.pprint(df_all.head(10))
    
    df_all = df_all.sort_values(by="Score",ascending=False)
    print("\n>>>>>>>>>> ",Ticker," (수익률랭크+MDD랭크)랭킹 TOP10 >>>>>>>>>>>>>>>>")
    pprint.pprint(df_all.head(10))
    
    print("#####################################################################")
    print("#####################################################################\n\n")
    

print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

