# -*- coding: utf-8 -*-
'''
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
import myUpbit   #우리가 만든 함수들이 들어있는 모듈
import pyupbit
import json
import pprint
import line_alert

import ende_key  #암복호화키
import my_key    #업비트 시크릿 액세스키

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



#수익금과 수익률을 리턴해주는 함수 (수수료는 생각안함) myUpbit에 넣으셔서 사용하셔도 됨!
def GetRevenueMoneyAndRate(balances,Ticker):
             
    #내가 가진 잔고 데이터를 다 가져온다.
    balances = upbit.get_balances()
    time.sleep(0.04)

    revenue_data = dict()

    revenue_data['revenue_money'] = 0
    revenue_data['revenue_rate'] = 0

    for value in balances:
        try:
            realTicker = value['unit_currency'] + "-" + value['currency']
            if Ticker == realTicker:
                
                nowPrice = pyupbit.get_current_price(realTicker)
                revenue_data['revenue_money'] = (float(nowPrice) - float(value['avg_buy_price'])) * upbit.get_balance(Ticker)
                revenue_data['revenue_rate'] = (float(nowPrice) - float(value['avg_buy_price'])) * 100.0 / float(value['avg_buy_price'])
                time.sleep(0.06)
                break

        except Exception as e:
            print("---:", e)

    return revenue_data





#암복호화 클래스 객체를 미리 생성한 키를 받아 생성한다.
simpleEnDecrypt = myUpbit.SimpleEnDecrypt(ende_key.ende_key)

#암호화된 액세스키와 시크릿키를 읽어 복호화 한다.
Upbit_AccessKey = simpleEnDecrypt.decrypt(my_key.upbit_access)
Upbit_ScretKey = simpleEnDecrypt.decrypt(my_key.upbit_secret)

#업비트 객체를 만든다
upbit = pyupbit.Upbit(Upbit_AccessKey, Upbit_ScretKey)


#시간 정보를 읽는다
time_info = time.gmtime()
#일봉 기준이니깐 날짜정보를 활용!
day_n = time_info.tm_mday



#내가 가진 잔고 데이터를 다 가져온다.
balances = upbit.get_balances()


TotalMoney = myUpbit.GetTotalMoney(balances) #총 원금
TotalRealMoney = myUpbit.GetTotalRealMoney(balances) #총 평가금액

print("TotalMoeny", TotalMoney)
print("TotalRealMoney", TotalRealMoney)



BOT_NAME = "Upbit_MagicSplitBot"


#투자할 종목! 예시.. 2개 종목 투자.
TargetStockList = ['KRW-SOL','KRW-XRP']

#한차수 최소 주문금액 설정! 2만원으로 세팅 예!
MinimunBuyMoney = 20000 #적어도 1만원 이상 권장!(최소 매매금액이 5천원인 관계로 1만원 이상은 되어야 반토막 나도 매수된 수량이 매도가 됨!)



#차수 정보가 들어간 데이터 리스트!
InvestInfoDataList = list()

for coin_ticker in TargetStockList:
    
    InvestInfoDict = dict()
    InvestInfoDict['coin_ticker'] = coin_ticker
    
    SplitInfoList = list()
    
    if coin_ticker == 'KRW-SOL':

        #####################
        '''
        아래 설정할 invest_money 값이 아무리 작아도 매수시 MinimunBuyMoney 이 값으로 자동 보정됩니다!!!
        따라서 최소 MinimunBuyMoney 이상의 값으로 세팅하세요!
        '''
        #####################
        #1차수 설정!!!
        SplitItem = {"number":1, "target_rate":10.0 , "trigger_rate":None , "invest_money":50000}  #차수, 목표수익률, 매수기준 손실률 (1차수는 이 정보가 필요 없다),투자금액
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":2, "target_rate":2.0 , "trigger_rate":-3.0 , "invest_money":30000} 
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":3, "target_rate":3.0 , "trigger_rate":-4.0 , "invest_money":30000} 
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":4, "target_rate":3.0 , "trigger_rate":-5.0 , "invest_money":30000} 
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":5, "target_rate":3.0 , "trigger_rate":-5.0 , "invest_money":30000} 
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":6, "target_rate":4.0 , "trigger_rate":-6.0 , "invest_money":30000} 
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":7, "target_rate":4.0 , "trigger_rate":-6.0 , "invest_money":30000} 
        SplitInfoList.append(SplitItem)   
        SplitItem = {"number":8, "target_rate":4.0 , "trigger_rate":-6.0 , "invest_money":30000} 
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":9, "target_rate":5.0 , "trigger_rate":-7.0 , "invest_money":30000} 
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":10, "target_rate":5.0 , "trigger_rate":-7.0 , "invest_money":30000} 
        SplitInfoList.append(SplitItem)
         
    elif coin_ticker == 'KRW-XRP':

        #1차수 설정!!!
        SplitItem = {"number":1, "target_rate":10.0 , "trigger_rate":None , "invest_money":40000}  #차수, 목표수익률, 매수기준 손실률 (1차수는 이 정보가 필요 없다),투자금액
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":2, "target_rate":2.0 , "trigger_rate":-3.0 , "invest_money":20000} 
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":3, "target_rate":3.0 , "trigger_rate":-4.0 , "invest_money":20000} 
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":4, "target_rate":3.0 , "trigger_rate":-5.0 , "invest_money":20000} 
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":5, "target_rate":3.0 , "trigger_rate":-5.0 , "invest_money":20000} 
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":6, "target_rate":4.0 , "trigger_rate":-6.0 , "invest_money":20000} 
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":7, "target_rate":4.0 , "trigger_rate":-6.0 , "invest_money":20000} 
        SplitInfoList.append(SplitItem)   
        SplitItem = {"number":8, "target_rate":4.0 , "trigger_rate":-6.0 , "invest_money":20000} 
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":9, "target_rate":5.0 , "trigger_rate":-7.0 , "invest_money":20000} 
        SplitInfoList.append(SplitItem)
        SplitItem = {"number":10, "target_rate":5.0 , "trigger_rate":-7.0 , "invest_money":20000} 
        SplitInfoList.append(SplitItem)
      
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
    CurrentPrice = pyupbit.get_current_price(coin_ticker)


        
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


        msg = BOT_NAME + " " + coin_ticker + " 매직스플릿 투자 준비 완료!!!!!"
        print(msg) 
        line_alert.SendMessage(msg) 


        #파일에 저장
        with open(bot_file_path, 'w') as outfile:
            json.dump(MagicNumberDataList, outfile)


    #이제 데이터(MagicNumberDataList)는 확실히 있을 테니 본격적으로 트레이딩을 합니다!
    for MagicDataInfo in MagicNumberDataList:
        

        if MagicDataInfo['coin_ticker'] == coin_ticker:
            
        
            
            #1차수가 매수되지 않은 상태인지를 체크해서 1차수를 일단 매수한다!!
            for MagicData in MagicDataInfo['MagicDataList']:
                if MagicData['Number'] == 1: #1차수를 찾아서!
                    if MagicData['IsBuy'] == False and MagicDataInfo['Date'] != day_n: #매수하지 않은 상태라면 매수를 진행한다!
                        
                        #새로 시작하는 거니깐 누적 실현손익 0으로 초기화!
                        MagicDataInfo['RealizedPNL'] = 0
                        
                        #1차수를 봇이 매수 안했는데 잔고에 수량이 있다면?
                        if myUpbit.IsHasCoin(balances,coin_ticker) == True:
                            
                            
                            MagicData['IsBuy'] = True
                            MagicData['EntryPrice'] = myUpbit.GetAvgBuyPrice(balances,coin_ticker)
                            MagicData['EntryAmt'] = upbit.get_balance(coin_ticker)

            

                            msg = BOT_NAME + " " + coin_ticker + " 매직스플릿 1차 투자를 하려고 했는데 잔고가 있어서 이를 1차투자로 가정하게 세팅했습니다!"
                            print(msg) 
                            line_alert.SendMessage(msg)
                            
                        else:
                
                            #1차수에 해당하는 정보 데이터를 읽는다.
                            PickSplitMeta = GetSplitMetaInfo(InvestInfo['split_info_list'],1)

                            #매수전 수량
                            coin_amt = upbit.get_balance(coin_ticker)

                            BuyMoney = PickSplitMeta['invest_money']

                            if BuyMoney < MinimunBuyMoney: #최소 금액 보정!!
                                BuyMoney = MinimunBuyMoney


                            #시장가 매수를 한다.
                            balances = myUpbit.BuyCoinMarket(upbit,coin_ticker,BuyMoney)
                            

                            
                            MagicData['IsBuy'] = True
                            MagicData['EntryPrice'] = CurrentPrice #현재가로 진입했다고 가정합니다!
                            MagicData['EntryAmt'] = abs(upbit.get_balance(coin_ticker) - coin_amt) #진입 수량!
                            
    

                            msg = BOT_NAME + " " + coin_ticker + " 매직스플릿 1차 투자 완료!"
                            print(msg) 
                            line_alert.SendMessage(msg)
                            
                        #파일에 저장
                        with open(bot_file_path, 'w') as outfile:
                            json.dump(MagicNumberDataList, outfile)
                        
                else:
                    if myUpbit.IsHasCoin(balances,coin_ticker) == False: #잔고가 없다면 2차이후의 차수 매매는 없는거니깐 초기화!
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
                    
                    
                    #현재 수익률이 목표 수익률보다 높다면
                    if CurrentRate >= PickSplitMeta['target_rate'] and myUpbit.IsHasCoin(balances,coin_ticker) == True:
                        
                        SellAmt = MagicData['EntryAmt']
                        

                        #보유 수량
                        coin_amt = upbit.get_balance(coin_ticker)


                        IsOver = False
                        #만약 매도할 수량이 수동 매도등에 의해서 보유 수량보다 크다면 보유수량으로 정정해준다!
                        if SellAmt > coin_amt:
                            SellAmt = coin_amt
                            IsOver = True
                    
                        
                        #모든 주문 취소하고
                        myUpbit.CancelCoinOrder(upbit,coin_ticker)
                        time.sleep(0.2)
                        
                        if MagicData['Number'] == 1:
                            SellAmt = coin_amt
                            

                        #시장가로 매도!
                        balances = myUpbit.SellCoinMarket(upbit,coin_ticker,SellAmt)

                        MagicData['IsBuy'] = False
                                    
                        #수익금과 수익률을 구한다!
                        revenue_data = GetRevenueMoneyAndRate(balances,coin_ticker)
                        MagicDataInfo['RealizedPNL'] += (revenue_data['revenue_money'] * SellAmt/coin_amt)
                        
                        
                        
                        msg = BOT_NAME + " " + coin_ticker + " 매직스플릿 "+str(MagicData['Number'])+"차 수익 매도 완료! 차수 목표수익률" + str(PickSplitMeta['target_rate']) +"% 만족" 
                        
                        if IsOver == True:
                            msg = BOT_NAME + " " + coin_ticker + " 매직스플릿 "+str(MagicData['Number'])+"차 수익 매도 완료! 차수 목표수익률" + str(PickSplitMeta['target_rate']) +"% 만족 매도할 수량이 보유 수량보다 많은 상태라 모두 매도함!" 
                            
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
                    
                    #이전차수 정보를 읽어온다.
                    PrevMagicData = GetSplitDataInfo(MagicDataInfo['MagicDataList'],MagicData['Number'] - 1)
                    
                    if PrevMagicData is not None and PrevMagicData.get('IsBuy', False) == True:

                        
                        #이전 차수 수익률을 구한다!
                        prevRate = (CurrentPrice - PrevMagicData['EntryPrice']) / PrevMagicData['EntryPrice'] * 100.0
                            
                            
                        print(coin_ticker, " ", MagicData['Number'], "차 진입을 위한 ",MagicData['Number']-1,"차 수익률 ", round(prevRate,2) , "% 트리거 수익률", PickSplitMeta['trigger_rate'], "%")

                        #현재 손실률이 트리거 손실률보다 낮다면
                        if prevRate <= PickSplitMeta['trigger_rate']:
                            

                            #매수전 수량
                            coin_amt = upbit.get_balance(coin_ticker)

                            BuyMoney = PickSplitMeta['invest_money']

                            if BuyMoney < MinimunBuyMoney: #최소 금액 보정!!
                                BuyMoney = MinimunBuyMoney

                            #시장가 매수를 한다.
                            balances = myUpbit.BuyCoinMarket(upbit,coin_ticker,BuyMoney)
                            

                            
                            MagicData['IsBuy'] = True
                            MagicData['EntryPrice'] = CurrentPrice #현재가로 진입했다고 가정합니다!
                            MagicData['EntryAmt'] = abs(upbit.get_balance(coin_ticker) - coin_amt) #진입 수량!

                            #파일에 저장
                            with open(bot_file_path, 'w') as outfile:
                                json.dump(MagicNumberDataList, outfile)
                                
                                
                            msg = BOT_NAME + " " + coin_ticker + " 매직스플릿 "+str(MagicData['Number'])+"차 수익 매수 완료! 이전 차수 손실률" + str(PickSplitMeta['trigger_rate']) +"% 만족" 
                            print(msg) 
                            line_alert.SendMessage(msg)
                            
               

#파일에 저장
with open(bot_file_path, 'w') as outfile:
    json.dump(MagicNumberDataList, outfile)
        
    

for MagicDataInfo in MagicNumberDataList:
    print(MagicDataInfo['coin_ticker'], "누적 실현 손익:", MagicDataInfo['RealizedPNL'])
    
    
#pprint.pprint(MagicNumberDataList)