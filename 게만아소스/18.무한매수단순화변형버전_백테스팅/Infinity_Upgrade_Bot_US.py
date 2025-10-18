'''

관련 포스팅

무한매수법 변형 단순화하고 백테스팅으로 개선해서 연복리 30%넘어가게  MDD는 절반으로 줄여보기!
https://blog.naver.com/zacra/223042245494

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
import KIS_API_Helper_US as KisUS
import json
import pprint
import line_alert

Common.SetChangeMode("VIRTUAL")

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
#투자할 종목!
TargetStockList = [] #투자할 종목을 아래 처럼 직접 판단히여 넣으세요!
#TargetStockList = ['TQQQ','SOXL'] #예시 종목
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




BOT_NAME = Common.GetNowDist() + "_InfinityUpgradeBot"

#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#
############# 해당 전략으로 매수한 종목 데이터 리스트 ####################
InfinityUpgradeDataList = list()
#파일 경로입니다.
bot_file_path = "/var/autobot/UsStock_" + BOT_NAME + ".json"

try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(bot_file_path, 'r') as json_file:
        InfinityUpgradeDataList = json.load(json_file)

except Exception as e:
    print("Exception by First")
################################################################
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#


#계좌 잔고를 가지고 온다!
Balance = KisUS.GetBalance()



print("--------------내 보유 잔고---------------------")

pprint.pprint(Balance)

print("--------------------------------------------")


#기준이 되는 내 총 평가금액에서 투자비중을 곱해서 나온 포트폴리오에 할당된 돈!!
TotalMoney = float(Balance['TotalMoney']) * InvestRate

#각 종목당 투자할 금액! 리스트의 종목 개수로 나눈다!
StockMoney = TotalMoney / len(TargetStockList)
print("TotalMoney:", str(format(round(TotalMoney), ',')))
print("StockMoney:", str(format(round(StockMoney), ',')))





print("--------------내 보유 주식---------------------")
#그리고 현재 이 계좌에서 보유한 주식 리스트를 가지고 옵니다!
MyStockList = KisUS.GetMyStockList()
pprint.pprint(MyStockList)
print("--------------------------------------------")
    

if ENABLE_ORDER_EXECUTION == True:


    #마켓이 열렸는지 여부~!
    IsMarketOpen = KisUS.IsMarketOpen()

    #장이 열렸을 때!
    if IsMarketOpen == True:


        #투자할 종목을 순회한다!
        for stock_code in TargetStockList:

            #주식(ETF) 정보~
            stock_name = ""
            stock_amt = 0 #수량
            stock_avg_price = 0 #평단
            stock_eval_totalmoney = 0 #총평가금액!
            stock_revenue_rate = 0 #종목 수익률
            stock_revenue_money = 0 #종목 수익금


            #매수된 상태라면 정보를 넣어준다!!!
            for my_stock in MyStockList:
                if my_stock['StockCode'] == stock_code:
                    stock_name = my_stock['StockName']
                    stock_amt = int(my_stock['StockAmt'])
                    stock_avg_price = float(my_stock['StockAvgPrice'])
                    stock_eval_totalmoney = float(my_stock['StockNowMoney'])
                    stock_revenue_rate = float(my_stock['StockRevenueRate'])
                    stock_revenue_money = float(my_stock['StockRevenueMoney'])

                    break
                    

            #현재가
            CurrentPrice = KisUS.GetCurrentPrice(stock_code)

                
            #종목 데이터
            PickStockInfo = None

            #저장된 종목 데이터를 찾는다
            for StockInfo in InfinityUpgradeDataList:
                if StockInfo['StockCode'] == stock_code:
                    PickStockInfo = StockInfo
                    break

            #PickStockInfo 이게 없다면 매수되지 않은 처음 상태이거나 이전에 손으로 매수한 종목인데 해당 봇으로 돌리고자 할 때!
            if PickStockInfo == None:
                #잔고가 없다 즉 처음이다!!!
                if stock_amt == 0:

                    InfinityDataDict = dict()
                    
                    InfinityDataDict['StockCode'] = stock_code #종목 코드
                    InfinityDataDict['MaxRound'] = 40 #맥스 회차!
                    InfinityDataDict['Round'] = 0    #현재 회차
                    InfinityDataDict['IsReady'] = 'Y' #하루에 한번 체크하고 매수등의 처리를 하기 위한 플래그

                    InfinityUpgradeDataList.append(InfinityDataDict) #데이터를 추가 한다!


                    msg = stock_code + " 개선무한매수봇 첫 시작!!!!"
                    print(msg) 
                    line_alert.SendMessage(msg) 
                    
                #데이터가 없는데 잔고가 있다? 이미 이 봇으로 트레이딩 하기전에 매수된 종목!
                else:
                    print("Exist")

                    InfinityDataDict = dict()
                    
                    InfinityDataDict['StockCode'] = stock_code #종목 코드
                    InfinityDataDict['MaxRound'] = 40 #맥스 회차!
                    
                    #분할된 투자금!
                    StMoney = StockMoney / InfinityDataDict['MaxRound']
                    InfinityDataDict['Round'] = int(stock_eval_totalmoney / StMoney)    #현재 회차 - 매수된 금액을 분할된 단위 금액으로 나누면 회차가 나온다!
                    InfinityDataDict['IsReady'] = 'Y' #하루에 한번 체크하고 매수등의 처리를 하기 위한 플래그


                    InfinityUpgradeDataList.append(InfinityDataDict) #데이터를 추가 한다!


                    msg = stock_code + " 기존에 매수한 종목을 개선무한매수봇으로 변경해서 트레이딩 첫 시작!!!! " + str(InfinityDataDict['Round']) + "회차로 세팅 완료!"
                    print(msg) 
                    line_alert.SendMessage(msg) 

                #파일에 저장
                with open(bot_file_path, 'w') as outfile:
                    json.dump(InfinityUpgradeDataList, outfile)
                    

            #이제 데이터(InfinityUpgradeDataList)는 확실히 있을 테니 본격적으로 트레이딩을 합니다!
            for StockInfo in InfinityUpgradeDataList:

                if StockInfo['StockCode'] == stock_code:
                    

                    #매수는 장이 열렸을 때 1번만 해야 되니깐! 안의 로직을 다 수행하면 N으로 바꿔준다! 
                    if StockInfo['IsReady'] == 'Y' :


                        #캔들 데이터를 읽는다
                        df = Common.GetOhlcv("US",stock_code, 1000)

                        #5일 이평선
                        Ma5_before2 = Common.GetMA(df,5,-3)
                        Ma5_before = Common.GetMA(df,5,-2)
                        Ma5 = Common.GetMA(df,5,-1)

                        print("MA5 ", Ma5_before, "-> ",Ma5)

                        #200일 이평선
                        Ma200_before2 = Common.GetMA(df,200,-3)
                        Ma200_before = Common.GetMA(df,200,-2)
                        Ma200 = Common.GetMA(df,200,-1)

                        print("MA200 ",Ma200)

                        
                        #RSI14
                        Rsi14= Common.GetRSI(df,14,-2)
                        
                        #107일 이평선
                        Ma107_before = Common.GetMA(df,107,-2)
                        
                        Ma100_before = Common.GetMA(df,100,-2)
                        Ma60_before = Common.GetMA(df,60,-2)
                        Ma20_before = Common.GetMA(df,20,-2)
                        
                        #3일 이평선
                        Ma3_before2 = Common.GetMA(df,3,-3)
                        Ma3_before = Common.GetMA(df,3,-2)
                        
                    

                        #1회차 이상 매수된 상황이라면 익절 조건을 체크해서 익절 처리 해야 한다!
                        if StockInfo['Round'] > 0 :
                            


                            #목표 수익률을 구한다! 
                            TargetRate = 10.0  / 100.0

                            FinalRate = TargetRate 

                            #수익화할 가격을 구한다!
                            RevenuePrice = stock_avg_price * (1.0 + FinalRate) 
                            
                            if CurrentPrice >= RevenuePrice or StockInfo['Round'] >= StockInfo['MaxRound']:

                                #목표한 수익가격보다 현재가가 높다면 익절처리할 순간이다!
                                if CurrentPrice >= RevenuePrice:
                                    
            
                                    #현재가보다 아래에 매도 주문을 넣음으로써 시장가로 매도효과!
                                    pprint.pprint(KisUS.MakeSellLimitOrder(stock_code,stock_amt,CurrentPrice*0.99))


                                    msg = stock_code + " 개선무한매수봇 모두 팔아서 수익확정!!!!  [" + str(stock_revenue_money) + "] 수익 조으다! (현재 [" + str(StockInfo['Round']) + "] 라운드까지 진행되었고 모든 수량 매도 처리! )"
                                    print(msg) 
                                    line_alert.SendMessage(msg) 

                                    #전량 매도 모두 초기화! 
                                    StockInfo['Round'] = 0


                                    #파일에 저장
                                    with open(bot_file_path, 'w') as outfile:
                                        json.dump(InfinityUpgradeDataList, outfile)
                                        
                                        
                                else:
                                    
                                    
                                    if StockInfo['Round'] >= StockInfo['MaxRound']: #쿼터 손절 들어간다!
                                        
                                        StockInfo['Round'] -= int(StockInfo['Round']/4.0)
                                        CutAmt = int(stock_amt / 4.0)

                                        pprint.pprint(KisUS.MakeSellLimitOrder(stock_code,CutAmt,CurrentPrice*0.99))


                                        msg = stock_code + " 개선무한매수봇 쿼터 손절!!!!  [" + str(stock_revenue_money/4.0) + "] 손익 확정! (현재 [" + str(StockInfo['Round']) + "] 라운드로 셋!)"
                                        print(msg) 
                                        line_alert.SendMessage(msg) 


                                        #파일에 저장
                                        with open(bot_file_path, 'w') as outfile:
                                            json.dump(InfinityUpgradeDataList, outfile)
                                            
                                            
                            else:
                                


                                if StockInfo['Round'] < StockInfo['MaxRound']:
                                    
                                    #개선본을 사용한다면 이 부분 주석처리 해야 해요!
                                    IsBuyGo = False
                                    
                                    ##########################################################################################
                                    ##########################################################################################
                                    ############### 블로그 내용 수정 예정이지만 매수는 100일선 아래에서 3일선이 증가될때로 변경 되었습니다 ################
                                    ##########################################################################################
                                    ##########################################################################################
                        
                                    if Ma100_before > df['close'].iloc[-2]: #어제 종가가 100일선보다 작은 하락장!

                                        if Ma3_before2 < Ma3_before: #전일까지 3일선이 증가했다면 그때만 매수!!
                                            IsBuyGo = True

                                    else: #200일선 위에 있는 상승장엔 기존 처럼 매일 매수!
                                        
                                        IsBuyGo = True
                                    #여기까지 주석처리요!!!!!!!!
                                                    

                                    ############# GMA 개선본!! 시작 #############
                                    ''' #개선본 사용시 위 부분은 주석처리!!!
                                    IsBuyGo = False
                                    if Ma107_before > df['close'].iloc[-2]: #현재가가 107일선보다 작은 하락장!

                                        if Ma3_before2 < Ma3_before: #전일까지 3일선이 증가했다면 그때만 매수!!
                                            IsBuyGo = True

                                    else: #107일선 위에 있는 상승장엔 기존 처럼 매일 매수!
                                        
                                        IsBuyGo = True
                                    '''
                                    ############# GMA 개선본!! 끝 #############
                        
                        
                                    ############# GMA 개선본!! 시작 #############
                                    '''
                                    if Rsi14 >= 80: # 개선된 점 GMA #RSI 80이상의 과매도 구간에선 회차 매수 안함!!
                                        IsBuyGo = False

                                    '''
                                    ############# GMA 개선본!! 끝 #############
                        
                        
                                    #200일선 위에 있다가 아래로 종가가 떨어지면...
                                    if (Ma200_before2 < df['close'].iloc[-3] and Ma200_before > df['close'].iloc[-2]) :
                                    

                                        #현재가보다 아래에 매도 주문을 넣음으로써 시장가로 매도효과!
                                        pprint.pprint(KisUS.MakeSellLimitOrder(stock_code,stock_amt,CurrentPrice*0.99))


                                        msg = stock_code + " 개선무한매수봇 하락장 진입!!!!!  [" + str(stock_revenue_money) + "] 손익 확정!! (현재 [" + str(StockInfo['Round']) + "] 라운드까지 진행되었고 모든 수량 매도 처리! )"
                                        print(msg) 
                                        line_alert.SendMessage(msg) 

                                        #전량 매도 모두 초기화! 
                                        StockInfo['Round'] = 0


                                        #파일에 저장
                                        with open(bot_file_path, 'w') as outfile:
                                            json.dump(InfinityUpgradeDataList, outfile)
                                            
                                        IsBuyGo = False
                                            
                        

                                    #한 회차 매수 한다!!
                                    if IsBuyGo == True:

                                        StockInfo['Round'] += 1 #라운드 증가!

                        
                                        #분할된 투자금!
                                        StMoney = StockMoney / StockInfo['MaxRound']


                                        BuyAmt = int(StMoney / CurrentPrice)
                                        
                                        #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                                        if BuyAmt < 1:
                                            BuyAmt = 1

                                        #시장가 주문을 넣는다!
                                        #현재가보다 위에 매수 주문을 넣음으로써 시장가로 매수!
                                        pprint.pprint(KisUS.MakeBuyLimitOrder(stock_code,BuyAmt,CurrentPrice*1.01))


                                        msg = stock_code + " 개선무한매수봇 " + str(StockInfo['Round']) + "회차 매수 완료!"
                                        print(msg) 
                                        line_alert.SendMessage(msg) 

        
                        
                        
                        if StockInfo['Round'] == 0 and Ma5_before < df['close'].iloc[-2] : #전일 종가가 5일선 위에 있을 때만 
                            
                            if Ma200_before > df['close'].iloc[-2]: #200일선 아래에 있을 땐 40분할
                                StockInfo['MaxRound'] = 40
                                
                            else: # 200일선 위에 있을 땐 30분할
                                StockInfo['MaxRound'] = 30 
                                
                                ############# GMA 개선본!! 시작 #############
                                '''
                                StockInfo['MaxRound'] = 55

                                
                                if Ma100_before <= df['close'].iloc[-2]:
                                    StockInfo['MaxRound'] -= 15


                                if Ma60_before <= df['close'].iloc[-2]:
                                    StockInfo['MaxRound'] -= 8


                                if Ma20_before <= df['close'].iloc[-2]:
                                    StockInfo['MaxRound'] -= 7     
                                '''    
                                ############# GMA 개선본!! 끝 #############
                    
                            
                            StockInfo['Round'] += 1 #라운드 증가!

            
                            #분할된 투자금!
                            StMoney = StockMoney / StockInfo['MaxRound']


                            BuyAmt = int(StMoney / CurrentPrice)
                            
                            #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                            if BuyAmt < 1:
                                BuyAmt = 1

                            #시장가 주문을 넣는다!
                            #현재가보다 위에 매수 주문을 넣음으로써 시장가로 매수!
                            pprint.pprint(KisUS.MakeBuyLimitOrder(stock_code,BuyAmt,CurrentPrice*1.01))


                            msg = stock_code + " 개선무한매수봇 " + str(StockInfo['Round']) + "회차 매수 완료!"
                            print(msg) 
                            line_alert.SendMessage(msg) 
                                    
                                    
                                    
                                
                        #위 로직 완료하면 N으로 바꿔서 오늘 매수는 안되게 처리!
                        StockInfo['IsReady'] = 'N' 

                        #파일에 저장
                        with open(bot_file_path, 'w') as outfile:
                            json.dump(InfinityUpgradeDataList, outfile) 
                            
                    break

    else:

            
        #장이 끝나고 다음날 다시 매수시도 할수 있게 Y로 바꿔줍니당!
        for StockInfo in InfinityUpgradeDataList:
            StockInfo['IsReady'] = 'Y'


        #파일에 저장
        with open(bot_file_path, 'w') as outfile:
            json.dump(InfinityUpgradeDataList, outfile)
            
            
    pprint.pprint(InfinityUpgradeDataList)

    
else:
    print("코드 맨 첫 부분에 ENABLE_ORDER_EXECUTION 값을 True로 변경해야 매수매도가 진행됩니다!")