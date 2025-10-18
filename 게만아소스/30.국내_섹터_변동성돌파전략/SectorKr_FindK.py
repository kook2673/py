'''
 
관련 포스팅
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

import pandas as pd
import pprint
from datetime import datetime


Common.SetChangeMode("VIRTUAL")

#####################################################################
#테스트할 종목 넣기!!
stock_code = "" 
#stock_code = "091160"  #예시
#####################################################################

GetCount = 3000  #얼마큼의 데이터를 가져올 것인지 
CutCount = 0     #최근 데이터 삭제! 200으로 세팅하면 200개의 최근 데이터가 사라진다

fee = 0.0015 #수수료+세금+슬리피지를 매수매도마다 0.15%로 기본 세팅!

TotalMoney = 1000000 #한국 계좌의 경우 시작 투자금 100만원으로 가정!


RealTotalList = list() #최종 결과가 저장될 리스트


print("\n----stock_code: ", stock_code)

#일봉 캔들 정보를 가지고 온다!
df = Common.GetOhlcv("KR",stock_code, GetCount) 

df['5ma'] = df['close'].rolling(5).mean()
df['60ma'] = df['close'].rolling(60).mean()

df['prevClose'] = df['close'].shift(1)
df['Disparity'] = df['prevClose'] / df['prevClose'].rolling(window=20).mean() * 100.0


df['prevClose'] = df['close'].shift(1)


df.dropna(inplace=True) #데이터 없는건 날린다!

df = df[:len(df)-CutCount] #최신 데이터 몇 개를 날리는 부분 CutCount값이 0이라면 최근 데이터까지!
pprint.pprint(df)



print("테스트하는 총 금액: ", round(TotalMoney))


print("K값 체크 중....")
for K_buy in range(1,11): #0.1~1.0

    K_buy_v = round(K_buy *0.1,2)
                  
    IsBuy = False #매수 했는지 여부
    IsDolpa = False #돌파 했는지!
    BUY_PRICE = 0  #매수한 금액! 

    TryCnt = 0      #매매횟수
    SuccesCnt = 0   #익절 숫자
    FailCnt = 0     #손절 숫자

    InvestMoney = TotalMoney #초기 투자금 설정
    TotalMoneyList = list() #투자금 이력 리스트

    #'''

    #####################################################
    for i in range(len(df)):

        date = df.index[i]

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
                
                
                
        NowOpenPrice = df['open'].iloc[i]    
        PrevOpenPrice = df['open'].iloc[i-1] 
        
        PrevClosePrice = df['close'].iloc[i-1] 
        
        
        #매수 상태!
        if IsBuy == True:
            

            
            SellPrice = NowOpenPrice
        
            InvestMoney = InvestMoney * (1.0 + ((SellPrice - BUY_PRICE) / BUY_PRICE))


            #진입(매수)가격 대비 변동률
            Rate = (NowOpenPrice - BUY_PRICE) / BUY_PRICE

            RevenueRate = (Rate - fee)*100.0 #수익률 계산

            InvestMoney = InvestMoney * (1.0 - fee)  #수수료 및 세금, 슬리피지 반영!

            #print(stock_code ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 매도!  수익률: ", round(RevenueRate,2) , "%", " ,종목 잔고:", round(InvestMoney,2)  , " ", df['open'].iloc[i])
            #print("\n\n")

            TryCnt += 1 #매매 횟수

            if RevenueRate > 0: #수익률이 0보다 크다면 익절한 셈이다!
                SuccesCnt += 1 #성공
            else:
                FailCnt += 1 #실패


            IsBuy = False #매도했다

        #아직 매수전 상태
        if IsBuy == False:
            
            if i >= 2:
                
                DolPaPrice = NowOpenPrice + ((df['high'].iloc[i-1] - df['low'].iloc[i-1]) * K_buy_v)

                if DolPaPrice <= df['high'].iloc[i] and NowOpenPrice <= DolPaPrice:
                    IsBuyGo = True
                    
                    weekday = date_object.weekday()
                    
                    #목요일 금요일에는 이평선 조건을 더 체크한다!
                    if weekday == 3 or weekday == 4 :

                        if df['5ma'].iloc[i-2] > df['5ma'].iloc[i-1]  :
                            IsBuyGo = False

                    #나머지 요일에는 이격도를 체크한다!
                    else:
                    
                        if df['Disparity'].iloc[i] > 110:
                            IsBuyGo = False
                                
                        
                    ##### MDD 개선 조건 #####
                    if ( (df['low'].iloc[i-1] > NowOpenPrice) or (df['open'].iloc[i-1] > df['close'].iloc[i-1]) ) and df['60ma'].iloc[i-1] > df['close'].iloc[i-1] :
                        IsBuyGo = False
                    #######################
            
                    
                        
                    if IsBuyGo == True:

                        BUY_PRICE = DolPaPrice  #매수가격은 돌파가격!

                        InvestMoney = InvestMoney * (1.0 - fee)  #수수료 및 세금, 슬리피지 반영!

                        #print(stock_code ," ", df.iloc[i].name, " " ,i, " >>>>>>>>>>>>>>>>> 매수! ,종목 잔고:", round(InvestMoney,2) , " ", df['open'].iloc[i])
                        IsBuy = True #매수했다
                        IsDolpa = True

        
        TotalMoneyList.append(InvestMoney)  #투자금 변경이력을 리스트에 저장!

    #####################################################
    #####################################################
    #####################################################
    #'''
    


    #결과 정리 및 데이터 만들기!!
    if len(TotalMoneyList) > 0:

        resultData = dict()

        
        resultData['Ticker'] = stock_code

        #이동평균 매매 전략 성과 구하기
        result_df = pd.DataFrame({ "Total_Money" : TotalMoneyList}, index = df.index)

        result_df['Ror'] = result_df['Total_Money'].pct_change() + 1
        result_df['Cum_Ror'] = result_df['Ror'].cumprod()

        result_df['Highwatermark'] =  result_df['Cum_Ror'].cummax()
        result_df['Drawdown'] = (result_df['Cum_Ror'] / result_df['Highwatermark']) - 1
        result_df['MaxDrawdown'] = result_df['Drawdown'].cummin()

        resultData['DateStr'] = str(result_df.iloc[0].name) + " ~ " + str(result_df.iloc[-1].name)

        resultData['OriMoney'] = TotalMoney
        resultData['FinalMoney'] = result_df['Total_Money'].iloc[-1]
        resultData['RevenueRate'] = ((result_df['Cum_Ror'].iloc[-1] -1.0)* 100.0)
        resultData['MDD'] = result_df['MaxDrawdown'].min() * 100.0

        resultData['TryCnt'] = TryCnt
        resultData['SuccesCnt'] = SuccesCnt
        resultData['FailCnt'] = FailCnt

        

        #'''
        #각 결과 로그 뿌려주기..
        print("############ ",resultData['DateStr']," ##########")
                                    
        print("-- K_buy", K_buy_v)
        print("---------- 총 결과 ----------")
        print("최초 금액:", str(format(round(resultData['OriMoney']), ','))  , " 최종 금액:", str(format(round(resultData['FinalMoney']), ',')), "\n수익률:", format(round(((resultData['FinalMoney'] - resultData['OriMoney']) / resultData['OriMoney']) * 100,2),',') ,"% MDD:",  round(resultData['MDD'],2),"%")
        print("------------------------------")
        print("####################################")
        #'''


        #조합 결과 데이터 만들기!
        FinalResultData = dict()
        FinalResultData['day_str'] = resultData['DateStr']
        FinalResultData['stock_ticker'] = stock_code
        FinalResultData['K_str'] = str(K_buy_v) 
        FinalResultData['RevenueRate'] = round(((resultData['FinalMoney'] - resultData['OriMoney']) / resultData['OriMoney']) * 100,2)
        FinalResultData['MDD'] = round(resultData['MDD'],2)


        RealTotalList.append(FinalResultData)
        
        TotalMoneyList.clear()
        


print(stock_code, " 체크 끝!!!!!!!")
print("#####################################################################")



df_all = pd.DataFrame(RealTotalList)

#결과 보여주기 프린트문!!
print("#####################################################################")
print("#####################################################################\n")
Ticker = df_all['stock_ticker'].iloc[-1]
print("대상 종목 : ", Ticker)
print("테스트 기간: ", df_all['day_str'].iloc[-1],"\n")

df_all = df_all.drop('day_str', axis=1)
df_all = df_all.drop('stock_ticker', axis=1)

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









