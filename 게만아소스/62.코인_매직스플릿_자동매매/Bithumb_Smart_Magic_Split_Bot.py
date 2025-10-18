# -*- coding: utf-8 -*-
'''
빗썸 필수 세팅 설명!! 60번 폴더를 먼저 참고하세요!!
https://blog.naver.com/zacra/223582852975

관련 포스팅
https://blog.naver.com/zacra/223603456956
위 포스팅을 꼭 참고하세요!!!

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.

주식/코인 파이썬 매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!


'''
import myBithumb   #우리가 만든 함수들이 들어있는 모듈
import json
import pprint
import line_alert
import time


import time



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




#시간 정보를 읽는다
time_info = time.gmtime()
#일봉 기준이니깐 날짜정보를 활용!
day_n = time_info.tm_mday



BOT_NAME = "Bithumb_SmartMagicSplitBot"


#내가 가진 잔고 데이터를 다 가져온다.
balances = myBithumb.GetBalances()

TotalMoney = myBithumb.GetTotalMoney(balances) #총 원금
TotalRealMoney = myBithumb.GetTotalRealMoney(balances) #총 평가금액

print("TotalMoeny", TotalMoney)
print("TotalRealMoney", TotalRealMoney)

######################################################
#투자 비중 -> 1.0 : 100%  0.5 : 50%   0.1 : 10%
InvestRate = 0.1 #투자 비중은 자금사정에 맞게 수정하세요!
######################################################


#투자할 종목! 예시.. 2개 종목 투자.
TargetStockList = list()

InvestDataDict = dict()
InvestDataDict['coin_ticker'] = "KRW-SOL" 
InvestDataDict['invest_rate'] = 0.7
TargetStockList.append(InvestDataDict)

InvestDataDict = dict()
InvestDataDict['coin_ticker'] = "KRW-XRP" 
InvestDataDict['invest_rate'] = 0.3
TargetStockList.append(InvestDataDict)


DivNum = 10.0 # 분할 수 설정!!!!! 즉 1차수 매수후 2차수부터 10차수까지 9계좌가 존재

#최소 주문금액 설정!
MinimunBuyMoney = 20000 #적어도 1만원 이상 권장!(최소 매매금액이 5천원인 관계로 1만원 이상은 되어야 반토막 나도 매수된 수량이 매도가 됨!)


#총 투자금 대비 얼마를 투자할지 
# TotalMoney 대신 TotalRealMoney로 바꾸면 평가금 기준으로 투자금을 설정한다!!
######################################################
InvestTotalMoney = TotalMoney * InvestRate
######################################################






#차수 정보가 들어간 데이터 리스트!
InvestInfoDataList = list()

for stock_data in TargetStockList:
    
    coin_ticker = stock_data['coin_ticker']
    
    print("################################################")
    print(coin_ticker)
    
    TotalInvestMoney = InvestTotalMoney * stock_data['invest_rate']
    
    FirstInvestMoney = TotalInvestMoney * 0.4 #1차수에 할당된 투자금 (이 금액이 다 투자되지는 않음 가변적으로 조절)
    RemainInvestMoney = TotalInvestMoney * 0.6 #나머지 차수가 균등하게 쪼개서 투자할 총 금액!
    
    print("1차수 할당 금액 ", FirstInvestMoney)
    print("나머지 차수 할당 금액 ", RemainInvestMoney)
        
    time.sleep(0.2)
    df = myBithumb.GetOhlcv(coin_ticker,'1d')
    #####################################
    prevClose = df['close'].iloc[-2] #전일 종가
    
    ### 이동평균선구하기 ###
    
    Ma5_Before = myBithumb.GetMA(df,5,-3) #전전일 기준
    Ma5 = myBithumb.GetMA(df,5,-2) #전일 기준
    
    Ma20_Before = myBithumb.GetMA(df,20,-3) #전전일 기준
    Ma20 = myBithumb.GetMA(df,20,-2) #전일 기준
    
    Ma60_Before = myBithumb.GetMA(df,60,-3) #전전일 기준
    Ma60 = myBithumb.GetMA(df,60,-2) #전일 기준
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
    print("분할이 기준이 되는 갭의 크기:",percent_gap ,"%")
    
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
    InvestInfoDict['coin_ticker'] = coin_ticker
    InvestInfoDict['split_info_list'] = SplitInfoList
    InvestInfoDataList.append(InvestInfoDict)
    
    
pprint.pprint(InvestInfoDataList)

#'''
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#
############# 매수후 진입시점, 수익률 등을 저장 관리할 파일 ####################
MagicNumberDataList = list()
#파일 경로입니다.
bot_file_path = "/var/autobot/" + BOT_NAME + ".json"

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


#투자할 종목을 순회한다!
for InvestInfo in InvestInfoDataList:
    
    coin_ticker = InvestInfo['coin_ticker'] #종목 코드
    

    #현재가
    CurrentPrice =  myBithumb.GetCurrentPrice(coin_ticker)


        
    #종목 데이터
    PickMagicDataInfo = None

    #저장된 종목 데이터를 찾는다
    for MagicDataInfo in MagicNumberDataList:
        if MagicDataInfo['coin_ticker'] == coin_ticker:
            PickMagicDataInfo = MagicDataInfo
            break

    #PickMagicDataInfo 이게 없다면 매수되지 않은 처음 상태이거나 이전에 손으로 매수한 종목인데 해당 봇으로 돌리고자 할 때!
    if PickMagicDataInfo == None:

        MagicNumberDataDict = dict()
        
        MagicNumberDataDict['coin_ticker'] = coin_ticker #종목 코드
        MagicNumberDataDict['Date'] = 0 

        
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


        msg = BOT_NAME + " " + coin_ticker + " 스마트스플릿 투자 준비 완료!!!!!"
        print(msg) 
        line_alert.SendMessage(msg) 


        #파일에 저장
        with open(bot_file_path, 'w') as outfile:
            json.dump(MagicNumberDataList, outfile)


    #이제 데이터(MagicNumberDataList)는 확실히 있을 테니 본격적으로 트레이딩을 합니다!
    for MagicDataInfo in MagicNumberDataList:
        

        if MagicDataInfo['coin_ticker'] == coin_ticker:
            
            time.sleep(0.3)
            df = myBithumb.GetOhlcv(coin_ticker,'1d')

            #####################################
            prevOpen = df['open'].iloc[-2] #전일 시가
            prevClose = df['close'].iloc[-2] #전일 종가
            
            ### 이동평균선구하기 ###
            
            Ma5_Before = myBithumb.GetMA(df,5,-3) #전전일 기준
            Ma5 = myBithumb.GetMA(df,5,-2) #전일 기준

            
            
            #1차수가 매수되지 않은 상태인지를 체크해서 1차수를 일단 매수한다!!
            for MagicData in MagicDataInfo['MagicDataList']:
                if MagicData['Number'] == 1: #1차수를 찾아서!

                    if MagicData['IsBuy'] == False and MagicDataInfo['Date'] != day_n: #매수하지 않은 상태라면 매수를 진행한다!
                        

                        #전일 양봉이면서 5일선 위에 있거나 5일선이 증가중인 상승추세가 보일 때 매수!
                        if prevOpen < prevClose and (prevClose >= Ma5 or Ma5_Before <= Ma5):
                                
                            #새로 시작하는 거니깐 누적 실현손익 0으로 초기화!
                            MagicDataInfo['RealizedPNL'] = 0
                            
                            #1차수를 봇이 매수 안했는데 잔고에 수량이 있다면?
                            if myBithumb.IsHasCoin(balances,coin_ticker) == True and myBithumb.GetCoinNowRealMoney(balances,coin_ticker) >= 5000:
                                
                                
                                MagicData['IsBuy'] = True
                                MagicData['EntryPrice'] = myBithumb.GetAvgBuyPrice(balances,coin_ticker)
                                MagicData['EntryAmt'] = myBithumb.GetCoinAmount(balances,coin_ticker) 


                                msg = BOT_NAME + " " + coin_ticker + " 스마트스플릿 1차 투자를 하려고 했는데 잔고가 있어서 이를 1차투자로 가정하게 세팅했습니다!"
                                print(msg) 
                                line_alert.SendMessage(msg)
                                
                            else:
                    
                                #1차수에 해당하는 정보 데이터를 읽는다.
                                PickSplitMeta = GetSplitMetaInfo(InvestInfo['split_info_list'],1)
                                
                                #매수전 수량
                                coin_amt = myBithumb.GetCoinAmount(balances,coin_ticker) 

                                BuyMoney = PickSplitMeta['invest_money']

                                if BuyMoney < MinimunBuyMoney: #최소 금액 보정!!
                                    BuyMoney = MinimunBuyMoney

                                #시장가 매수를 한다.
                                balances = myBithumb.BuyCoinMarket(coin_ticker,BuyMoney)
                                    
                                MagicData['IsBuy'] = True
                                MagicData['EntryPrice'] = CurrentPrice #현재가로 진입했다고 가정합니다!
                                MagicData['EntryAmt'] = abs(myBithumb.GetCoinAmount(balances,coin_ticker)  - coin_amt) #진입 수량!


                                msg = BOT_NAME + " " + coin_ticker + " 스마트스플릿 1차 투자 완료!"
                                print(msg) 
                                line_alert.SendMessage(msg)
                                
                            #파일에 저장
                            with open(bot_file_path, 'w') as outfile:
                                json.dump(MagicNumberDataList, outfile)

                else:
                    if myBithumb.IsHasCoin(balances,coin_ticker) == False or myBithumb.GetCoinNowRealMoney(balances,coin_ticker) < 5000: #잔고가 0이라면 2차이후의 차수 매매는 없는거니깐 초기화!
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
                    
                    print(coin_ticker, " ", MagicData['Number'], "차 수익률 ", round(CurrentRate,2) , "% 목표수익률", PickSplitMeta['target_rate'], "%")
                    
                    #수익금과 수익률을 구한다!
                    revenue_data = myBithumb.GetRevenueMoneyAndRate(balances,coin_ticker)


                    #현재 수익률이 목표 수익률보다 높다면
                    if CurrentRate >= PickSplitMeta['target_rate'] and myBithumb.IsHasCoin(balances,coin_ticker) == True and myBithumb.GetCoinNowRealMoney(balances,coin_ticker) >= 5000 : #and (revenue_data['revenue_money'] + MagicDataInfo['RealizedPNL']) > 0 :
                        
                        SellAmt = MagicData['EntryAmt']
                        

                        #보유 수량
                        coin_amt = myBithumb.GetCoinAmount(balances,coin_ticker) 


                        IsOver = False
                        #만약 매도할 수량이 수동 매도등에 의해서 보유 수량보다 크다면 보유수량으로 정정해준다!
                        if SellAmt > coin_amt:
                            SellAmt = coin_amt
                            IsOver = True
                    
                        
                        #모든 주문 취소하고
                        myBithumb.CancelCoinOrder(coin_ticker)
                        time.sleep(0.2)

                        if MagicData['Number'] == 1:
                            SellAmt = coin_amt
                            


                        #시장가로 매도!
                        balances = myBithumb.SellCoinMarket(coin_ticker,SellAmt)

                        MagicData['IsBuy'] = False

                        MagicDataInfo['RealizedPNL'] += (revenue_data['revenue_money'] * SellAmt/coin_amt)
                        
                        
                        
                        msg = BOT_NAME + " " + coin_ticker +  " 스마트스플릿 "+str(MagicData['Number'])+"차 수익 매도 완료! 차수 목표수익률" + str(PickSplitMeta['target_rate']) +"% 만족" 
                        
                        if IsOver == True:
                            msg = BOT_NAME + " " + coin_ticker + " 스마트스플릿 "+str(MagicData['Number'])+"차 수익 매도 완료! 차수 목표수익률" + str(PickSplitMeta['target_rate']) +"% 만족 매도할 수량이 보유 수량보다 많은 상태라 모두 매도함!" 
                            
                        print(msg) 
                        line_alert.SendMessage(msg)
                        
                        #1차수 매도라면 오늘 날짜를 넣어서 오늘 1차 매수가 없도록 한다!
                        if MagicData['Number'] == 1:
                            MagicDataInfo['Date'] = day_n

                        #파일에 저장
                        with open(bot_file_path, 'w') as outfile:
                            json.dump(MagicNumberDataList, outfile)
                            
                            
                    
                #매수아직 안한 차수!
                else:
                    
                    if MagicData['Number'] > 1:
                        #이전차수 정보를 읽어온다.
                        PrevMagicData = GetSplitDataInfo(MagicDataInfo['MagicDataList'],MagicData['Number'] - 1)
                        
                        if PrevMagicData is not None and PrevMagicData.get('IsBuy', False) == True:

                            
                            #이전 차수 수익률을 구한다!
                            prevRate = (CurrentPrice - PrevMagicData['EntryPrice']) / PrevMagicData['EntryPrice'] * 100.0
                                
                                
                            print(coin_ticker, " ", MagicData['Number'], "차 진입을 위한 ",MagicData['Number']-1,"차 수익률 ", round(prevRate,2) , "% 트리거 수익률", PickSplitMeta['trigger_rate'], "%")



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
                                

                                #매수전 수량
                                coin_amt = myBithumb.GetCoinAmount(balances,coin_ticker) 

                                BuyMoney = PickSplitMeta['invest_money']

                                if BuyMoney < MinimunBuyMoney: #최소 금액 보정!!
                                    BuyMoney = MinimunBuyMoney

                                #시장가 매수를 한다.
                                balances = myBithumb.BuyCoinMarket(coin_ticker,BuyMoney)

                                
                                MagicData['IsBuy'] = True
                                MagicData['EntryPrice'] = CurrentPrice #현재가로 진입했다고 가정합니다!
                                MagicData['EntryAmt'] = abs(myBithumb.GetCoinAmount(balances,coin_ticker)  - coin_amt) #진입 수량!

                                #파일에 저장
                                with open(bot_file_path, 'w') as outfile:
                                    json.dump(MagicNumberDataList, outfile)
                                    
                                    
                                msg = BOT_NAME + " " + coin_ticker + " 스마트스플릿 "+str(MagicData['Number'])+"차 매수 완료! 이전 차수 손실률" + str(PickSplitMeta['trigger_rate']) +"% 만족" 
                                print(msg) 
                                line_alert.SendMessage(msg)
                                


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
            
                    msg = BOT_NAME + " " + coin_ticker + "스마트스플릿 풀매수 상태인데 더 하락하여 2차수 손절 및 초기화!" 
                    print(msg) 
                    line_alert.SendMessage(msg)
                    
                    SecondMagicData = GetSplitDataInfo(MagicDataInfo['MagicDataList'],2)
                    

                    SellAmt = SecondMagicData['EntryAmt']

                    #보유 수량
                    coin_amt = myBithumb.GetCoinAmount(balances,coin_ticker) 

                    IsOver = False
                    #만약 매도할 수량이 수동 매도등에 의해서 보유 수량보다 크다면 보유수량으로 정정해준다!
                    if SellAmt > coin_amt:
                        SellAmt = coin_amt
                        IsOver = True
                

                    #시장가로 매도!
                    balances = myBithumb.SellCoinMarket(coin_ticker,SellAmt)
                    
                    SecondMagicData['IsBuy'] = False
                    #수익금과 수익률을 구한다!
                    revenue_data = myBithumb.GetRevenueMoneyAndRate(balances,coin_ticker)
                    MagicDataInfo['RealizedPNL'] += (revenue_data['revenue_money'] * SellAmt/coin_amt)
                    
                    
                    msg = BOT_NAME + " " + coin_ticker + " 스마트스플릿 풀매수 상태여서 2차 수량 손절 완료! "
                    
                    if IsOver == True:
                        msg = BOT_NAME + " " + coin_ticker + " 스마트스플릿 풀매수 상태여인데 1차수 매도할 수량이 보유 수량보다 많은 상태라 모두 매도함!"
                        
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
                                
                                msg = BOT_NAME + " " + coin_ticker + " 스마트스플릿 " + str(Number) + "차수 비워둠!\n 10차수를 새로 매수할 수 있음!" 
                                print(msg) 
                                line_alert.SendMessage(msg)
                    
                            else:
                                data['IsBuy'] = MagicDataInfo['MagicDataList'][i + 1]['IsBuy']
                                data['EntryAmt'] = MagicDataInfo['MagicDataList'][i + 1]['EntryAmt']
                                data['EntryPrice'] = MagicDataInfo['MagicDataList'][i + 1]['EntryPrice']
                                
                                msg = BOT_NAME + " " + coin_ticker + " 스마트스플릿 " + str(Number + 1) + "차수 데이터를 " +  str(Number) + "차수로 옮김!"
                                print(msg) 
                                line_alert.SendMessage(msg)


                    #파일에 저장
                    with open(bot_file_path, 'w') as outfile:
                        json.dump(MagicNumberDataList, outfile)
                        
                            
            #'''                   
            
                    


for MagicDataInfo in MagicNumberDataList:
    print(MagicDataInfo['coin_ticker'], "누적 실현 손익:", MagicDataInfo['RealizedPNL'])
    
    
#pprint.pprint(MagicNumberDataList)