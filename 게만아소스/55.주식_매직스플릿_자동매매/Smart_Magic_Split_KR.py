# -*- coding: utf-8 -*-
'''
관련 포스팅
https://blog.naver.com/zacra/223534417235

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
  3. 매수할 종목을 명시 
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
import json
import pprint
import line_alert
import time


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
📌 투자할 종목은 본인의 선택으로 직접 입력하세요!
'''
#투자할 종목! 예시.. 2개 종목 투자.
TargetStockList = list()

InvestDataDict = dict()
InvestDataDict['stock_code'] = "458730" 
InvestDataDict['invest_rate'] = 0.6
TargetStockList.append(InvestDataDict)

InvestDataDict = dict()
InvestDataDict['stock_code'] = "329750" 
InvestDataDict['invest_rate'] = 0.4
TargetStockList.append(InvestDataDict)


DivNum = 10.0 # 분할 수 설정!!!!! 즉 1차수 매수후 2차수부터 10차수까지 9계좌가 존재

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



#시간 정보를 읽는다
time_info = time.gmtime()


#정보리스트와 차수를 받아서 차수 정보(익절기준,진입기준)을 리턴한다!
def GetSplitMetaInfo(DataList, number):
    
    PickSplitMeta = None
    for infoData in DataList:
        if number == infoData["number"]:
            PickSplitMeta =  infoData
            break
            
    return PickSplitMeta

#파일로 저장관리되는 데이터를 읽어온다(진입가,진입수량)
def GetSplitDataInfo(DataList, number):
    
    PickSplitData = None
    for saveData in DataList:
        if number == saveData["Number"]:
            PickSplitData =  saveData
            break
            
    return PickSplitData



BOT_NAME = Common.GetNowDist() + "_SmartMagicSplitBot"

#계좌 잔고를 가지고 온다!
Balance = KisKR.GetBalance()


print("--------------내 보유 잔고---------------------")

pprint.pprint(Balance)

print("--------------------------------------------")
####################################

#기준이 되는 내 총 평가금액에서 투자비중을 곱해서 나온 포트폴리오에 할당된 돈!! 
TotalMoney = float(Balance['TotalMoney']) * InvestRate

print("총 포트폴리오에 할당된 투자 가능 금액 : ", TotalMoney)





if ENABLE_ORDER_EXECUTION == True:


    #혹시 이 봇을 장 시작하자 마자 돌린다면 20초르 쉬어준다.
    #그 이유는 20초는 지나야 오늘의 일봉 정보를 제대로 가져오는데
    #tm_hour가 0은 9시, 1은 10시를 뜻한다. 수능 등 10시에 장 시작하는 경우르 대비!
    if time_info.tm_hour in [0,1] and time_info.tm_min in [0,1]:
        time.sleep(20.0)
        
        
            
    #차수 정보가 들어간 데이터 리스트!
    InvestInfoDataList = list()

    for stock_data in TargetStockList:
        
        stock_code = stock_data['stock_code']
        
        print("################################################")
        print(KisKR.GetStockName(stock_code), " ", stock_code)
        
        TotalInvestMoney = TotalMoney * stock_data['invest_rate']
        
        FirstInvestMoney = TotalInvestMoney * 0.4 #1차수에 할당된 투자금 (이 금액이 다 투자되지는 않음 가변적으로 조절)
        RemainInvestMoney = TotalInvestMoney * 0.6 #나머지 차수가 균등하게 쪼개서 투자할 총 금액!
        
        print("1차수 할당 금액 ", FirstInvestMoney)
        print("나머지 차수 할당 금액 ", RemainInvestMoney)
            
        

        df = Common.GetOhlcv("KR",stock_code, 200)  ### 일봉정보를 가져온다 200개!

        #####################################
        prevClose = df['close'].iloc[-2] #전일 종가
        
        ### 이동평균선구하기 ###
        
        Ma5_Before = Common.GetMA(df,5,-3) #전전일 기준
        Ma5 = Common.GetMA(df,5,-2) #전일 기준
        
        Ma20_Before = Common.GetMA(df,20,-3) #전전일 기준
        Ma20 = Common.GetMA(df,20,-2) #전일 기준
        
        Ma60_Before = Common.GetMA(df,60,-3) #전전일 기준
        Ma60 = Common.GetMA(df,60,-2) #전일 기준
        #####################################
        
        
        min_price = df['close'].min()
        max_price = df['close'].max()
        
        gap = max_price - min_price
        step_gap = gap / DivNum

        percent_gap = round((gap / min_price) * 100,2)
        
        print("최근 200개 캔들 최저가 ", min_price)
        print("최근 200개 캔들 최고가 ", max_price)
        
        print("최고 최저가 차이  ", gap)
        print("각 간격 사이의 갭 ", step_gap)
        print("분할의 기준이 되는 갭의 크기:",percent_gap ,"%")
        
        target_rate = round(percent_gap / DivNum,2)
        trigger_rate = -round((percent_gap / DivNum),2)

        print("각 차수의 목표 수익률: ",target_rate ,"%")
        print("각 차수의 진입 기준이 되는 이전 차수 손실률:",trigger_rate ,"%")
        

        #현재 구간을 구할 수 있다.
        now_step = DivNum

        for step in range(1,int(DivNum)+1):

            if prevClose < min_price + (step_gap * step):
                now_step = step
                break
        print("현재 구간 ",now_step)
        




        SplitInfoList = list()
        
        for i in range(int(DivNum)):
            number = i+1
            
            #1차수라면
            if number == 1:
                
                FinalInvestRate = 0
                
                #이동평균선에 의해 최대 60%!!
                if prevClose >= Ma5:
                    FinalInvestRate += 10
                if prevClose >= Ma20:
                    FinalInvestRate += 10  
                if prevClose >= Ma60:
                    FinalInvestRate += 10
                    
                if Ma5 >= Ma5_Before:
                    FinalInvestRate += 10
                if Ma20 >= Ma20_Before:
                    FinalInvestRate += 10
                if Ma60 >= Ma60_Before:
                    FinalInvestRate += 10
                    
                print("- 1차수 진입 이동평균선에 의한 비율 ", FinalInvestRate , "%")
                    
                #현재 분할 위치에 따라 최대 40%
                
                print("- 1차수 진입 현재 구간에 의한 비율 ", ((int(DivNum)+1)-now_step) * (40.0/DivNum) , "%")
                FinalInvestRate += (((int(DivNum)+1)-now_step) * (40.0/DivNum))
                
                
                FinalFirstMoney = FirstInvestMoney * (FinalInvestRate/100.0)
                print("- 1차수 진입 금액 ", FinalFirstMoney , " 할당 금액 대비 투자 비중:" , FinalInvestRate, "%")
                
                SplitInfoList.append({"number":1, "target_rate":target_rate * 2.0 , "trigger_rate":None , "invest_money":round(FinalFirstMoney)}) #차수, 목표수익률, 매수기준 손실률 (1차수는 이 정보가 필요 없다),투자금액
                
            #그밖의 차수
            else:
                SplitInfoList.append({"number":number, "target_rate":target_rate , "trigger_rate":trigger_rate , "invest_money":round(RemainInvestMoney / (DivNum-1))}) #차수, 목표수익률, 매수기준 손실률 ,투자금액
            


        InvestInfoDict = dict()
        InvestInfoDict['stock_code'] = stock_code
        InvestInfoDict['split_info_list'] = SplitInfoList
        InvestInfoDataList.append(InvestInfoDict)
        
        
    pprint.pprint(InvestInfoDataList)


    #'''
    #$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#
    ############# 매수후 진입시점, 수익률 등을 저장 관리할 파일 ####################
    MagicNumberDataList = list()
    #파일 경로입니다.
    bot_file_path = "/var/autobot/KrStock_" + BOT_NAME + ".json"

    try:
        #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
        with open(bot_file_path, 'r') as json_file:
            MagicNumberDataList = json.load(json_file)

    except Exception as e:
        print("Exception by First")
    ################################################################
    #$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#
    #$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#
    #'''


    print("--------------내 보유 주식---------------------")
    #그리고 현재 이 계좌에서 보유한 주식 리스트를 가지고 옵니다!
    MyStockList = KisKR.GetMyStockList()
    #pprint.pprint(MyStockList)
    print("--------------------------------------------")
        

    #마켓이 열렸는지 여부~!
    IsMarketOpen = KisKR.IsMarketOpen()

    IsLP_OK = True
    #정각 9시 5분 전에는 LP유동성 공급자가 없으니 매매를 피하고자.
    if time_info.tm_hour == 0: #9시인데
        if time_info.tm_min < 6: #6분보다 적은 값이면 --> 6분부터 LP가 활동한다고 하자!
            IsLP_OK = False
            

    #장이 열렸고 LP가 활동할때 매수!!!
    if IsMarketOpen == True and IsLP_OK == True: 


        #투자할 종목을 순회한다!
        for InvestInfo in InvestInfoDataList:
            
            stock_code = InvestInfo['stock_code'] #종목 코드
            
            #종목 정보~
            stock_name = KisKR.GetStockName(stock_code)
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
            CurrentPrice = KisKR.GetCurrentPrice(stock_code)


                
            #종목 데이터
            PickMagicDataInfo = None

            #저장된 종목 데이터를 찾는다
            for MagicDataInfo in MagicNumberDataList:
                if MagicDataInfo['StockCode'] == stock_code:
                    PickMagicDataInfo = MagicDataInfo
                    break

            #PickMagicDataInfo 이게 없다면 매수되지 않은 처음 상태이거나 이전에 손으로 매수한 종목인데 해당 봇으로 돌리고자 할 때!
            if PickMagicDataInfo == None:

                MagicNumberDataDict = dict()
                
                MagicNumberDataDict['StockCode'] = stock_code #종목 코드
                MagicNumberDataDict['StockName'] = stock_name #종목 이름
                MagicNumberDataDict['IsReady'] = True #오늘 장에서 매수 가능한지 플래그!

            
                MagicDataList = list()
                
                #사전에 정의된 데이터!
                for i in range(len(InvestInfo['split_info_list'])):
                    MagicDataDict = dict()
                    MagicDataDict['Number'] = i+1 # 차수
                    MagicDataDict['EntryPrice'] = 0 #진입가격
                    MagicDataDict['EntryAmt'] = 0   #진입수량
                    MagicDataDict['IsBuy'] = False   #매수 상태인지 여부
                    
                    MagicDataList.append(MagicDataDict)

                MagicNumberDataDict['MagicDataList'] = MagicDataList
                MagicNumberDataDict['RealizedPNL'] = 0 #종목의 누적 실현손익


                MagicNumberDataList.append(MagicNumberDataDict) #데이터를 추가 한다!


                msg = stock_code + " 스마트스플릿 투자 준비 완료!!!!!"
                print(msg) 
                line_alert.SendMessage(msg) 


                #파일에 저장
                with open(bot_file_path, 'w') as outfile:
                    json.dump(MagicNumberDataList, outfile)


            #이제 데이터(MagicNumberDataList)는 확실히 있을 테니 본격적으로 트레이딩을 합니다!
            for MagicDataInfo in MagicNumberDataList:
                

                if MagicDataInfo['StockCode'] == stock_code:
                    
                    
                    
                    
                    df = Common.GetOhlcv("KR",stock_code, 200)  ### 일봉정보를 가져온다 200개!

                    #####################################
                    prevOpen = df['open'].iloc[-2] #전일 시가
                    prevClose = df['close'].iloc[-2] #전일 종가
                    
                    ### 이동평균선구하기 ###
                    
                    Ma5_Before = Common.GetMA(df,5,-3) #전전일 기준
                    Ma5 = Common.GetMA(df,5,-2) #전일 기준

                    #1차수가 매수되지 않은 상태인지를 체크해서 1차수를 일단 매수한다!!
                    for MagicData in MagicDataInfo['MagicDataList']:
                        if MagicData['Number'] == 1: #1차수를 찾아서!
                            
                            if MagicData['IsBuy'] == False and MagicDataInfo['IsReady'] == True: #매수하지 않은 상태라면 매수를 진행한다!
                                
                                #전일 양봉이면서 5일선 위에 있거나 5일선이 증가중인 상승추세가 보일 때 매수!
                                if prevOpen < prevClose and (prevClose >= Ma5 or Ma5_Before <= Ma5):
                                    
                                    #새로 시작하는 거니깐 누적 실현손익 0으로 초기화!
                                    MagicDataInfo['RealizedPNL'] = 0
                                    
                                    #1차수를 봇이 매수 안했는데 잔고에 수량이 있다면?
                                    if stock_amt > 0:
                                        
                                        
                                        MagicData['IsBuy'] = True
                                        MagicData['EntryPrice'] = stock_avg_price #현재가로 진입했다고 가정합니다!
                                        MagicData['EntryAmt'] = stock_amt



                                        msg = stock_name + "("+stock_code + ") 스마트스플릿 1차 투자를 하려고 했는데 잔고가 있어서 이를 1차투자로 가정하게 세팅했습니다!"
                                        print(msg) 
                                        line_alert.SendMessage(msg)
                                        
                                    else:
                            
                                        #1차수에 해당하는 정보 데이터를 읽는다.
                                        PickSplitMeta = GetSplitMetaInfo(InvestInfo['split_info_list'],1)
                                        
                                        #투자금을 현재가로 나눠서 매수 가능한 수량을 정한다.
                                        BuyAmt = int(PickSplitMeta['invest_money'] / CurrentPrice)
                                        
                                        #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                                        if BuyAmt < 1:
                                            BuyAmt = 1
                                            
                                        pprint.pprint(KisKR.MakeBuyLimitOrder(stock_code,BuyAmt,CurrentPrice*1.01))
                                        
                                        MagicData['IsBuy'] = True
                                        MagicData['EntryPrice'] = CurrentPrice #현재가로 진입했다고 가정합니다!
                                        MagicData['EntryAmt'] = BuyAmt



                                        msg = stock_code + " 스마트스플릿 1차 투자 완료!"
                                        print(msg) 
                                        line_alert.SendMessage(msg)
                                        
                        
                                        #매매가 일어났으니 보유수량등을 리프레시 한다!
                                        MyStockList = KisKR.GetMyStockList()
                                        #매수된 상태라면 정보를 넣어준다!!!
                                        for my_stock in MyStockList:
                                            if my_stock['StockCode'] == stock_code:
                                                stock_amt = int(my_stock['StockAmt'])
                                                stock_avg_price = float(my_stock['StockAvgPrice'])
                                                stock_eval_totalmoney = float(my_stock['StockNowMoney'])
                                                stock_revenue_rate = float(my_stock['StockRevenueRate'])
                                                stock_revenue_money = float(my_stock['StockRevenueMoney'])
                                                break
                                    #파일에 저장
                                    with open(bot_file_path, 'w') as outfile:
                                        json.dump(MagicNumberDataList, outfile)   
                                
                        else:
            
                            if stock_amt == 0: #잔고가 0이라면 차수 매매는 없는거니깐 초기화!
                                MagicData['IsBuy'] = False
                                MagicData['EntryAmt'] = 0
                                MagicData['EntryPrice'] = 0   

                                #파일에 저장
                                with open(bot_file_path, 'w') as outfile:
                                    json.dump(MagicNumberDataList, outfile)
                
                
                    
                    
                    
                    #매수된 차수가 있다면 수익률을 체크해서 매도하고, 매수 안된 차수도 체크해서 매수한다.
                    for MagicData in MagicDataInfo['MagicDataList']:
                        
                    
                        #해당 차수의 정보를 읽어온다.
                        PickSplitMeta = GetSplitMetaInfo(InvestInfo['split_info_list'],MagicData['Number'])
                            
                        #매수된 차수이다.
                        if MagicData['IsBuy'] == True:
                            
                            #현재 수익률을 구한다!
                            CurrentRate = (CurrentPrice - MagicData['EntryPrice']) / MagicData['EntryPrice'] * 100.0
                            
                            print(stock_name,"(",stock_code, ") ",  MagicData['Number'], "차 수익률 ", round(CurrentRate,2) , "% 목표수익률", PickSplitMeta['target_rate'], "%")
                            
                            
                            #현재 수익률이 목표 수익률보다 높다면
                            if CurrentRate >= PickSplitMeta['target_rate'] and stock_amt > 0 :#and (stock_revenue_money + MagicDataInfo['RealizedPNL']) > 0 :
                                
                                SellAmt = MagicData['EntryAmt']
                                
                                IsOver = False
                                #만약 매도할 수량이 수동 매도등에 의해서 보유 수량보다 크다면 보유수량으로 정정해준다!
                                if SellAmt > stock_amt:
                                    SellAmt = stock_amt
                                    IsOver = True
                            
                                
                                pprint.pprint(KisKR.MakeSellLimitOrder(stock_code,SellAmt,CurrentPrice*0.99))
                                
                                
                                MagicData['IsBuy'] = False
                                MagicDataInfo['RealizedPNL'] += (stock_revenue_money * SellAmt/stock_amt)
                                
                                
                                
                                msg = stock_name + "("+stock_code + ") 스마트스플릿 "+str(MagicData['Number'])+"차 수익 매도 완료! 차수 목표수익률" + str(PickSplitMeta['target_rate']) +"% 만족" 
                                
                                if IsOver == True:
                                    msg = stock_name + "("+stock_code + ") 스마트스플릿 "+str(MagicData['Number'])+"차 수익 매도 완료! 차수 목표수익률" + str(PickSplitMeta['target_rate']) +"% 만족 매도할 수량이 보유 수량보다 많은 상태라 모두 매도함!" 
                                    
                                print(msg) 
                                line_alert.SendMessage(msg)
                                

                                #1차수 매도라면 레디값을 False로 바꿔서 오늘 1차 매수가 없도록 한다!
                                if MagicData['Number'] == 1:
                                    MagicDataInfo['IsReady'] = False

                                #파일에 저장
                                with open(bot_file_path, 'w') as outfile:
                                    json.dump(MagicNumberDataList, outfile)
                                    
                                    
                                    
                                #매매가 일어났으니 보유수량등을 리프레시 한다!
                                MyStockList = KisKR.GetMyStockList()
                                #매수된 상태라면 정보를 넣어준다!!!
                                for my_stock in MyStockList:
                                    if my_stock['StockCode'] == stock_code:
                                        stock_amt = int(my_stock['StockAmt'])
                                        stock_avg_price = float(my_stock['StockAvgPrice'])
                                        stock_eval_totalmoney = float(my_stock['StockNowMoney'])
                                        stock_revenue_rate = float(my_stock['StockRevenueRate'])
                                        stock_revenue_money = float(my_stock['StockRevenueMoney'])
                                        break
                                    
                                    
                                    
                            
                        #매수아직 안한 차수!
                        else:
                            
                            if MagicData['Number'] > 1:
                                
                                #이전차수 정보를 읽어온다.
                                PrevMagicData = GetSplitDataInfo(MagicDataInfo['MagicDataList'],MagicData['Number'] - 1)
                                
                                if PrevMagicData is not None and PrevMagicData.get('IsBuy', False) == True:
                                        
                                    #이전 차수 수익률을 구한다!
                                    prevRate = (CurrentPrice - PrevMagicData['EntryPrice']) / PrevMagicData['EntryPrice'] * 100.0
                                        
                                        
                                    print(stock_name,"(",stock_code, ") ", MagicData['Number'], "차 진입을 위한 ",MagicData['Number']-1,"차 수익률 ", round(prevRate,2) , "% 트리거 수익률", PickSplitMeta['trigger_rate'], "%")



                                    AdditionlCondition = True
                                    
                                    if MagicData['Number'] % 2 == 1: #홀수 차수일 경우
                                        
                                        if prevOpen < prevClose and (prevClose >= Ma5 or Ma5_Before <= Ma5):
                                            AdditionlCondition = True
                                        else:
                                            AdditionlCondition = False
                                            
                                        
                                    else: #짝수 차수일 경우
                                        AdditionlCondition = True
                                        
                                    

                                    #현재 손실률이 트리거 손실률보다 낮다면
                                    if prevRate <= PickSplitMeta['trigger_rate'] and AdditionlCondition == True:
                                        

                                        #투자금을 현재가로 나눠서 매수 가능한 수량을 정한다.
                                        BuyAmt = int(PickSplitMeta['invest_money'] / CurrentPrice)
                                        
                                        #1주보다 적다면 투자금이나 투자비중이 작은 상황인데 일단 1주는 매수하게끔 처리 하자!
                                        if BuyAmt < 1:
                                            BuyAmt = 1

                                        
                                        #매수주문 들어감!
                                        pprint.pprint(KisKR.MakeBuyLimitOrder(stock_code,BuyAmt,CurrentPrice*1.01))
                                        
                                        MagicData['IsBuy'] = True
                                        MagicData['EntryPrice'] = CurrentPrice #현재가로 진입했다고 가정합니다!
                                        MagicData['EntryAmt'] = BuyAmt

                                        #파일에 저장
                                        with open(bot_file_path, 'w') as outfile:
                                            json.dump(MagicNumberDataList, outfile)
                                            
                                            
                                        msg = stock_name + "("+stock_code + ") 스마트스플릿 "+str(MagicData['Number'])+"차 매수 완료! 이전 차수 손실률" + str(PickSplitMeta['trigger_rate']) +"% 만족" 
                                        print(msg) 
                                        line_alert.SendMessage(msg)
                                        
                                        
                                        
                                        
                                        #매매가 일어났으니 보유수량등을 리프레시 한다!
                                        MyStockList = KisKR.GetMyStockList()
                                        #매수된 상태라면 정보를 넣어준다!!!
                                        for my_stock in MyStockList:
                                            if my_stock['StockCode'] == stock_code:
                                                stock_amt = int(my_stock['StockAmt'])
                                                stock_avg_price = float(my_stock['StockAvgPrice'])
                                                stock_eval_totalmoney = float(my_stock['StockNowMoney'])
                                                stock_revenue_rate = float(my_stock['StockRevenueRate'])
                                                stock_revenue_money = float(my_stock['StockRevenueMoney'])
                                                break
                        
                        
                        

                    #'''
                    IsFullBuy = True #풀매수 상태!
                    
                    for MagicData in MagicDataInfo['MagicDataList']:
                        #한 차수라도 매수되지 않은 차수가 있다면 풀 매수 상태는 아니다!!!
                        if MagicData['IsBuy'] == False:
                            IsFullBuy = False
                            break
                            
                    #풀매수 상태라면
                    if IsFullBuy == True:
                        
                    
                        #마지막 차수 정보를 얻어온다.
                        LastSplitMeta = GetSplitMetaInfo(InvestInfo['split_info_list'],int(DivNum))
                        LastMagicData = GetSplitDataInfo(MagicDataInfo['MagicDataList'],int(DivNum))
                    
                        #마지막 차수의 손익률
                        LastRate = (CurrentPrice - LastMagicData['EntryPrice']) / LastMagicData['EntryPrice'] * 100.0
                        
                        #그런데 마지막 차수 마저 갭 간격 비율 만큼 추가 하락을 했다!!!
                        if LastRate <= LastSplitMeta['trigger_rate']:
                    
                            msg = stock_name + "("+stock_code + ") 스마트스플릿 풀매수 상태인데 더 하락하여 2차수 손절 및 초기화!" 
                            print(msg) 
                            line_alert.SendMessage(msg)
                            
                            SecondMagicData = GetSplitDataInfo(MagicDataInfo['MagicDataList'],2)
                            

                            SellAmt = SecondMagicData['EntryAmt']
                            
                            IsOver = False
                            #만약 매도할 수량이 수동 매도등에 의해서 보유 수량보다 크다면 보유수량으로 정정해준다!
                            if SellAmt > stock_amt:
                                SellAmt = stock_amt
                                IsOver = True
                        
                            
                            pprint.pprint(KisKR.MakeSellLimitOrder(stock_code,SellAmt,CurrentPrice*0.99))
                            
                            
                            SecondMagicData['IsBuy'] = False
                            MagicDataInfo['RealizedPNL'] += (stock_revenue_money * SellAmt/stock_amt)
                            
                            
                            msg = stock_name + "("+stock_code + ") 스마트스플릿 풀매수 상태여서 2차 수량 손절 완료! " + str(SellAmt) + "주 매도!"
                            
                            if IsOver == True:
                                msg = stock_name + "("+stock_code + ") 스마트스플릿 풀매수 상태여인데 1차수 매도할 수량이 보유 수량보다 많은 상태라 모두 매도함!" + str(SellAmt) + "주 매도!"
                                
                            print(msg) 
                            line_alert.SendMessage(msg)
                            
                            
                        
                            for i in range(int(DivNum)):
                                
                                Number = i + 1
                                
                                if Number >= 2: 
                                    data = MagicDataInfo['MagicDataList'][i]
            
                                    if Number == int(DivNum):
                                        data['IsBuy'] = False
                                        data['EntryAmt'] = 0
                                        data['EntryPrice'] = 0
                                        
                                        msg = stock_name + "("+stock_code + ") 스마트스플릿 " + str(Number) + "차수 비워둠!\n 10차수를 새로 매수할 수 있음!" 
                                        print(msg) 
                                        line_alert.SendMessage(msg)
                            
                                    else:
                                        data['IsBuy'] = MagicDataInfo['MagicDataList'][i + 1]['IsBuy']
                                        data['EntryAmt'] = MagicDataInfo['MagicDataList'][i + 1]['EntryAmt']
                                        data['EntryPrice'] = MagicDataInfo['MagicDataList'][i + 1]['EntryPrice']
                                        
                                        msg = stock_name + "("+stock_code + ") 스마트스플릿 " + str(Number + 1) + "차수 데이터를 " +  str(Number) + "차수로 옮김!"
                                        print(msg) 
                                        line_alert.SendMessage(msg)


                            #파일에 저장
                            with open(bot_file_path, 'w') as outfile:
                                json.dump(MagicNumberDataList, outfile)
                                
                                    
                    #'''                                   
                                                            

    else:
        #장이 끝나고 1차수 매매 가능하게 True로 변경
        for StockInfo in MagicNumberDataList:
            StockInfo['IsReady'] = True


        #파일에 저장
        with open(bot_file_path, 'w') as outfile:
            json.dump(MagicNumberDataList, outfile)
            
        


    for MagicDataInfo in MagicNumberDataList:
        print(MagicDataInfo['StockName'],"(",MagicDataInfo['StockCode'] ,") 누적 실현 손익:", MagicDataInfo['RealizedPNL'])
        
else:
    print("코드 맨 첫 부분에 ENABLE_ORDER_EXECUTION 값을 True로 변경해야 매수매도가 진행됩니다!")