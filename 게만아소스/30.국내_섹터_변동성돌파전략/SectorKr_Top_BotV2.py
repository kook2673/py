#-*-coding:utf-8 -*-
'''


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
https://blog.naver.com/zacra/223620239264

위 포스팅을 꼭 참고하세요!!!


📌 [코드 제공 목적]

이 코드는 클래스101 게만아 <파이썬 자동매매 봇 만들기> 강의의 보조 자료로 제공되며,  
강의 수강생의 **학습 및 실습을 위한 참고용 예시 코드**입니다.  
**투자 권유, 종목 추천, 자문 또는 일임을 위한 목적은 전혀 없습니다.**

📌 [기술 구현 관련 안내]

- 본 코드는 **증권사에서 공식적으로 제공한 API** 및  
  **공식 개발자 가이드 문서**에 따라 구현되었습니다.
- 해당 API는 일반 투자자 누구나 이용 가능한 서비스이며,  
  본 코드는 그것을 구현한 예시를 활용해 전략을 구현해보는 학습 목적으로 활용한 것입니다.

📌 [전략 실행 조건]

- 본 코드는 자동 반복 실행되지 않으며, 사용자가 직접 실행해야 1회 동작합니다.
- 반복 실행을 원할 경우, 사용자가 별도로 서버 및 스케줄러 구성을 해야 합니다.


- 본 코드에는 증권사 제공 API를 활용한 매매 기능이 포함되어 있으나,  
  **사용자가 명시적으로 설정을 변경하지 않는 한 실행되지 않습니다.**
  

- 전략 실행을 위해서는 다음의 과정을 **사용자가 직접** 수행해야 합니다:

  1. `ENABLE_ORDER_EXECUTION` 값을 `True`로 변경  
  2. `InvestRate` 비중을 설정 (기본값: 0)  
  3. 매수할 종목을 명시 (기본값: 빈 리스트)  
  4. AWS 또는 개인 서버 구축 및 `crontab` 또는 스케줄러 등록

- 제공자는 서버 구축, 설정, 실행 대행 등을 전혀 하지 않습니다.

📌 [법적 책임 고지]

- 제공되는 코드는 기술 학습 및 테스트 목적의 예시 코드입니다.  
- **백테스트 결과는 과거 데이터 기반이며, 미래 수익을 보장하지 않습니다.**

- 본 코드의 사용, 수정, 실행에 따른 모든 결과와 책임은 사용자에게 있으며,  
  **제공자는 법적·금전적 책임을 일절 지지 않습니다.**

📌 [저작권 안내]

- 이 코드는 저작권법 및 부정경쟁방지법의 보호를 받습니다.  
- 무단 복제, 공유, 재판매, 배포 시 민·형사상 책임이 따를 수 있습니다.

📌 [학습 권장 사항]

- 본 예시 코드는 전략 구현을 이해하기 위한 템플릿입니다.  
- 이를 바탕으로 자신만의 전략을 개발해보시길 권장드립니다 :)



주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!


'''

import KIS_Common as Common
import KIS_API_Helper_KR as KisKR
import time
import pprint
import pandas as pd
import json
from datetime import datetime

import line_alert



#계좌 선택.. "VIRTUAL" 는 모의 계좌!
Common.SetChangeMode("VIRTUAL") #REAL or VIRTUAL


#####################################################################################################################################
'''
※ 주문 실행 여부 설정

ENABLE_ORDER_EXECUTION 값을 True로 변경할 경우,  
전략에 따라 매매가 일어납니다.

⚠️ 기본값은 False이며,  
실행 여부는 사용자 본인이 코드를 수정하여 결정해야 합니다.
'''

ENABLE_ORDER_EXECUTION = False  # 주문 실행 여부 설정 (기본값: False)

'''
📌 본 전략은 시스템을 구현하는 예시 코드이며,  
실제 투자 및 주문 실행은 사용자 본인의 의사와 책임 하에 수행됩니다.
'''
#####################################################################################################################################

'''
📌 투자할 종목은 본인의 선택으로 리스트 형식으로 직접 입력하세요!
'''
InvestStockList = [] # #아래 예시처럼 직접 종목을 채우세요
#InvestStockList = ["091160", "091230", "305720", "305540" , "091170" , "091220" , "102970" , "117460", "091180", "102960"]

#####################################################################################################################################

'''
📌 투자 비중 설정!
기본은 0으로 설정되어 있어요.
본인의 투자 비중을 설정하세요! 

전략에서 활용할 주문이 
시장가 주문이라면 0 ~ 0.75 
지정가 주문이라면 0 ~ 0.98
사이의 값으로 설정하세요! (0.1 = 10% 0.5 = 50%)
'''
InvestRate = 0 #총 평가금액에서 해당 봇에게 할당할 총 금액비율 0.1 = 10%  0.5 = 50%
#####################################################################################################################################




BOT_NAME = Common.GetNowDist() + "_MySecterTop_Bot"


#포트폴리오 이름
PortfolioName = "게만아 섹터 ETF 매매 전략!"


#시간 정보를 읽는다
time_info = time.gmtime()

day_str = str(time_info.tm_mon) + "-" + str(time_info.tm_mday)

print(day_str)



###################################################################
###################################################################
SectorStragegyData = dict()
#파일 경로입니다.
data_file_path = "/var/autobot/KrStock_" + BOT_NAME + ".json"

try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(data_file_path, 'r') as json_file:
        SectorStragegyData = json.load(json_file)

except Exception as e:
    print("Init....")

    SectorStragegyData['StockCode'] = "" #대상 종목 코드
    SectorStragegyData['StockName'] = "" #종목 이름
    SectorStragegyData['Date'] = "00" #오늘날짜
    SectorStragegyData['Status'] = "REST" #상태 READY(돌파를체크해야하는 준비상태), INVESTING(돌파해서 투자중), REST(조건불만족,투자안함,돌파체크안함) 
    SectorStragegyData['TargetPrice'] = 0 #돌파가격
    SectorStragegyData['BuyAmt'] = 0 #매수수량

    #파일에 저장
    with open(data_file_path, 'w') as outfile:
        json.dump(SectorStragegyData, outfile)

###################################################################
###################################################################




#####################################################################################################################################

#계좌 잔고를 가지고 온다!
Balance = KisKR.GetBalance()
#####################################################################################################################################

'''-------통합 증거금 사용자는 아래 코드도 사용할 수 있습니다! -----------'''
#통합증거금 계좌 사용자 분들중 만약 미국계좌랑 통합해서 총자산을 계산 하고 포트폴리오 비중에도 반영하고 싶으시다면 아래 코드를 사용하시면 되고 나머지는 동일합니다!!!
#Balance = Common.GetBalanceKrwTotal()

'''-----------------------------------------------------------'''
#####################################################################################################################################


print("--------------내 보유 잔고---------------------")

pprint.pprint(Balance)

print("--------------------------------------------")


##########################################################

print("--------------내 보유 주식---------------------")
#그리고 현재 이 계좌에서 보유한 주식 리스트를 가지고 옵니다!
MyStockList = KisKR.GetMyStockList()
pprint.pprint(MyStockList)
print("--------------------------------------------")
##########################################################



#기준이 되는 내 총 평가금액에서 투자비중을 곱해서 나온 포트폴리오에 할당된 돈!!
TotalMoney = float(Balance['TotalMoney']) * InvestRate

print("전략에 투자하는 총 금액: ", format(round(TotalMoney), ','))

InvestMoney = TotalMoney




if ENABLE_ORDER_EXECUTION == True:

    #마켓이 열렸는지 여부~!
    IsMarketOpen = KisKR.IsMarketOpen()

    IsLP_OK = True
    #정각 9시 5분 전에는 LP유동성 공급자가 없으니 매매를 피하고 싶다면..
    if time_info.tm_hour == 0: #9시인데
        if time_info.tm_min <= 5: #5분보다 적은 값이면
            IsLP_OK = False
            

    if IsMarketOpen == True and IsLP_OK == True: #9시 5분 지나서 매매하려면 이 코드
    #if IsMarketOpen == True : #9시정각에 매매하고 싶다면 이 코드

        #혹시 이 봇을 장 시작하자 마자 돌린다면 20초르 쉬어준다.
        #그 이유는 20초는 지나야 오늘의 일봉 정보를 제대로 가져오는데
        #tm_hour가 0은 9시, 1은 10시를 뜻한다. 수능 등 10시에 장 시작하는 경우르 대비!
        if time_info.tm_hour in [0,1] and time_info.tm_min == 0:
            time.sleep(20.0)
            

        print("Market Is Open!!!!!!!!!!!")
        #영상엔 없지만 리밸런싱이 가능할때만 내게 메시지를 보내자!


        #날짜가 다르다면 날이 바뀐거다 매매할 섹터를 찾고 처리하자!
        if day_str != SectorStragegyData['Date']:
            
                
            line_alert.SendMessage(PortfolioName + "  장이 열려서 매매 가능!!")

            #데이터를 조합한다.
            stock_df_list = []

            for stock_code in InvestStockList:
                df = Common.GetOhlcv("KR", stock_code,100)

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

            date = combined_df.iloc[-1].name

            #최근 20일 거래대금 중간값이 큰 종목을 구한다.
            pick_stocks = combined_df.loc[combined_df.index == date].groupby('stock_code')['value_median'].max().nlargest(1)



            #1개이기 때문에 for문을 돌 필요는 없지만 확장을 위해.
            for stock_code in pick_stocks.index:
                stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)]




                DolPaRate = 0.45
                if stock_code == "091160":
                    DolPaRate = 1.0
                elif stock_code == "091230":
                    DolPaRate = 1.0
                elif stock_code == "305720":
                    DolPaRate = 1.0
                elif stock_code == "305540":
                    DolPaRate = 0.9
                elif stock_code == "091170":
                    DolPaRate = 0.9
                elif stock_code == "091220":
                    DolPaRate = 0.1 
                elif stock_code == "102970":
                    DolPaRate = 0.6
                elif stock_code == "117460":
                    DolPaRate = 0.7
                elif stock_code == "091180":
                    DolPaRate = 1.0
                elif stock_code == "102960":
                    DolPaRate = 1.0
                    
                #변동성 돌파 시가 + (전일고가-전일저가)*0.45
                DolPaPrice = stock_data['open'].values[0] + ((stock_data['prevHigh'].values[0] - stock_data['prevLow'].values[0]) * DolPaRate)
                
                Disparity = stock_data['Disparity'].values[0]


                # 일봉 정보 가지고 오는 모듈이 달라지면 에러가 나므로 예외처리
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
                        

                # 요일 가져오기 (0: 월요일, 1: 화요일,2 수요일 3 목요일 4 금요일 5 토요일 ..., 6: 일요일)
                weekday = date_object.weekday()
                print("--weekday--", weekday, time_info.tm_wday)

                #가장 최근 데이터의 날짜의 요일과 봇이 실행되는 요일은 같아야 한다.
                #이게 다르다면 아직 최근 데이터의 날자가 갱신 안되었단 이야기인데 이는 9시 정각이나..(20초 딜레이가 필요) 수능등으로 장 오픈시간이 지연되었을때 다를 수 있다. 그때는 매매하면 안된다
                if weekday == time_info.tm_wday:



                    SectorStragegyData['Date'] = day_str #오늘 맨처음 할일 (종목 선정 및 돌파가격 설정, 상태 설정)을 끝냈으니 날짜를 넣어 다음날 다시 실행되게 한다.

                    #파일에 저장
                    with open(data_file_path, 'w') as outfile:
                        json.dump(SectorStragegyData, outfile)
                        

                    #만약 투자중이라면 전일 돌파매수를 한거니 지금 매도하면 된다!
                    if SectorStragegyData['Status'] == "INVESTING": #투자중 상태인데 날짜가 바뀌었다면 

        
                        stock_amt = 0 #수량
                        stock_avg_price = 0 #평단
                        stock_eval_totalmoney = 0 #총평가금액!
                        stock_revenue_rate = 0 #종목 수익률
                        stock_revenue_money = 0 #종목 수익금

                    
                        
                        #내가 보유한 주식 리스트에서 매수된 잔고 정보를 가져온다
                        for my_stock in MyStockList:
                            if my_stock['StockCode'] == SectorStragegyData['StockCode']:
                                stock_name = my_stock['StockName']
                                stock_amt = int(my_stock['StockAmt'])
                                stock_avg_price = float(my_stock['StockAvgPrice'])
                                stock_eval_totalmoney = float(my_stock['StockNowMoney'])
                                stock_revenue_rate = float(my_stock['StockRevenueRate'])
                                stock_revenue_money = float(my_stock['StockRevenueMoney'])

                                break
                            
                        if stock_amt > 0:

                            pprint.pprint(KisKR.MakeSellMarketOrder(SectorStragegyData['StockCode'],stock_amt))
                            
                            SectorStragegyData['Status'] = "REST" 

                            msg = stock_name + " 모두 매도!!! " + str(stock_revenue_money) + " 수익 확정!! 수익률:" + str(stock_revenue_rate) + "%"
                            print(msg)
                            line_alert.SendMessage(msg)
                            
                        else:
                            
                            SectorStragegyData['Status'] = "REST" 
                            
                            msg = stock_name + " 매도해야 되는데 매수한 수량이 없어요! 매수가 실패한 듯 보여요!"
                            print(msg)
                            line_alert.SendMessage(msg)
                

                    IsBuyReady = True
                    
                    #목요일/금요일은 5일 이평선이 감소중이라면 매매 안한다!
                    if weekday == 3 or weekday == 4:
                        if stock_data['ma_before2'].values[0] > stock_data['ma_before'].values[0]:
                            IsBuyReady = False
                    else:
                        #그밖의 요일은 20일선 이격도가 110 넘어가면 매매 안한다.
                        if Disparity > 110:
                            IsBuyReady = False

                        
                    ##### MDD 개선 조건 #####
                    if ( (stock_data['prevLow'].values[0] > stock_data['open'].values[0]) or (stock_data['prevOpen'].values[0] > stock_data['prevClose'].values[0]) ) and stock_data['ma60_before'].values[0] > stock_data['prevClose'].values[0] :
                        IsBuyReady = False
                    #######################
                    

                    SectorStragegyData['StockCode'] = stock_code #대상 종목 코드
                    SectorStragegyData['StockName'] = KisKR.GetStockName(stock_code)


                    if IsBuyReady == True:
                        print("IS Ready!!!")
                        SectorStragegyData['TargetPrice'] = DolPaPrice #돌파가격
                        SectorStragegyData['Status'] = "READY"


                        msg = SectorStragegyData['StockName'] + "  조건을 만족하여 오늘 돌파하면 매수합니다!!!"
                        print(msg)
                        line_alert.SendMessage(msg)
                    else:
                        print("No Ready")
                        SectorStragegyData['Status'] = "REST" #상태 READY(돌파를체크해야하는 준비상태), INVESTING_TRY(돌파해서 주문 들어감), INVESTING(돌파해서 투자중), REST(조건불만족,투자안함,돌파체크안함) 


                        msg = SectorStragegyData['StockName'] + "  조건을 불만족하여 오늘 돌파매수는 쉽니다!!!"
                        print(msg)
                        line_alert.SendMessage(msg)




                    #파일에 저장
                    with open(data_file_path, 'w') as outfile:
                        json.dump(SectorStragegyData, outfile)
                else:
                    
                    #정시나 30분에는 메시지를 보내주자! 뭔가 이상상황...
                    if time_info.tm_min == 0 or time_info.tm_min == 30:
                        msg = "요일이 다르게 나왔어요! 좀 더 기다려봐요!"
                        print(msg)
                        line_alert.SendMessage(msg)
                    

        else: #날짜가 같다면 오늘 할 일이 정해진 상태다!!!
            #현재가!
            CurrentPrice = KisKR.GetCurrentPrice(SectorStragegyData['StockCode'])        
            
            
            
            #시장가매수가 진행 되었다
            if SectorStragegyData['Status'] == "INVESTING_TRY":
                
                MyStockList = KisKR.GetMyStockList()

                stock_amt = 0 #수량

                
                #내가 보유한 주식 리스트에서 매수된 잔고 정보를 가져온다
                for my_stock in MyStockList:
                    if my_stock['StockCode'] == SectorStragegyData['StockCode']:
                        stock_amt = int(my_stock['StockAmt'])
                        break
                    
                #실제로 매수가 되었다면 투자중 상태로 변경!!!
                if stock_amt > 0:
                    SectorStragegyData['Status'] = "INVESTING"


                    msg = SectorStragegyData['StockName'] + "  조건을 만족하여 매수가 된 상태에요!!! (일부 지정가 주문은 체결이 안되었을 수도 있어요!)"
                    print(msg)
                    line_alert.SendMessage(msg)


                    
                #아니라면 알림으로 알려준다!!
                else:

            
                    msg = SectorStragegyData['StockName'] + "  조건을 만족하여 시장가 / 지정가 매수 시도 했는데 1주도 매수되지 않았어요! 시장가 주문 조차 실패되었다는 이야기인데 다시 1/5만큼 시장가 주문을 넣어볼게요! "
                    print(msg)
                    line_alert.SendMessage(msg)
                    

                    #이렇게 시장가로 매수! 
                    returnData = KisKR.MakeBuyMarketOrder(SectorStragegyData['StockCode'],SectorStragegyData['BuyAmt'],True)

                    print(str(returnData))
                    line_alert.SendMessage(str(returnData))

                    

                #파일에 저장
                with open(data_file_path, 'w') as outfile:
                    json.dump(SectorStragegyData, outfile)


                
            #상태를 체크해서 READY라면 돌파시 매수한다!

            if SectorStragegyData['Status'] == "READY":
                print("돌파 체크중...")
            

                #돌파가격보다 현재가가 높다? 돌파한거다 매수한다!
                if CurrentPrice >= SectorStragegyData['TargetPrice']:


                    #매수할 수량을 계산한다! - 5분할 합니다!!
                    BuyAmt = int(InvestMoney / CurrentPrice)


                    #최소 5주는 살 수 있도록!
                    if BuyAmt < 5:
                        BuyAmt = 5


                

                    SliceAmt = BuyAmt / 5


                    SectorStragegyData['BuyAmt'] = SliceAmt # 1/5수량을 저장해둠
                    

                    msg = SectorStragegyData['StockName'] + "  조건을 만족하여 지정가 / 시장가로 매수 시도 합니다!!! "
                    print(msg)
                    line_alert.SendMessage(msg)
        
                    KisKR.MakeBuyLimitOrder(SectorStragegyData['StockCode'],SliceAmt,CurrentPrice*(1.0 - 0.001)) #20%는 0.1%아래 
                    
                    KisKR.MakeBuyLimitOrder(SectorStragegyData['StockCode'],SliceAmt,CurrentPrice) #20%는 현재가로 지정가 주문!

                    KisKR.MakeBuyLimitOrder(SectorStragegyData['StockCode'],SliceAmt,SectorStragegyData['TargetPrice']) #20%는 돌파가격으로 지정가 주문!
            
                    KisKR.MakeBuyMarketOrder(SectorStragegyData['StockCode'],SliceAmt*2,True) #40%만! 시장가로 주문!
        

                        
                    SectorStragegyData['Status'] = "INVESTING_TRY" #상태 READY(돌파를체크해야하는 준비상태), INVESTING_TRY(돌파해서 주문 들어감), INVESTING(돌파해서 투자중), REST(조건불만족,투자안함,돌파체크안함) 

        

                    #파일에 저장
                    with open(data_file_path, 'w') as outfile:
                        json.dump(SectorStragegyData, outfile)

                    msg = SectorStragegyData['StockName'] + "  조건을 만족하여 지정가 / 시장가로 매수!!! 투자 시작!! "
                    print(msg)
                    line_alert.SendMessage(msg)
                else:
                    print("아직 돌파 안함..")
                    
        


    else:
        print("Market Is Close!!!!!!!!!!!")

        #line_alert.SendMessage(PortfolioName + "  장이 열려있지 않아요!")


    print("----현재 데이터 상태----")
    pprint.pprint(SectorStragegyData)

else:
    print("코드 맨 첫 부분에 ENABLE_ORDER_EXECUTION 값을 True로 변경해야 매수매도가 진행됩니다!")
