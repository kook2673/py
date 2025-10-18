# -*- coding: utf-8 -*-
'''

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

해당 컨텐츠는 제가 직접 투자 하기 위해 이 전략을 추가 개선해서 더 좋은 성과를 보여주는 개인 전략이 존재합니다. 


게만아 추가 개선 개인 전략들..
https://blog.naver.com/zacra/223196497504


관심 있으신 분은 위 포스팅을 참고하세요!

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$





관련 포스팅

https://blog.naver.com/zacra/223597500754
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
import pandas as pd
import KIS_API_Helper_KR as KisKR
import time
import json
import pprint


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

InvestStockList = list() #투자할 종목을 직접 판단하여 아래 예시처럼 넣으세요!
#InvestStockList.append({"stock_code":"133690", "small_ma":5 , "big_ma":34, "invest_rate":0.4}) #TIGER 미국나스닥100
#InvestStockList.append({"stock_code":"069500", "small_ma":3 , "big_ma":103, "invest_rate":0.2}) #KODEX 200
#InvestStockList.append({"stock_code":"148070", "small_ma":8 , "big_ma":71, "invest_rate":0.1}) #KOSEF 국고채10년
#InvestStockList.append({"stock_code":"305080", "small_ma":20 , "big_ma":61, "invest_rate":0.1}) #TIGER 미국채10년선물
#InvestStockList.append({"stock_code":"132030", "small_ma":15 , "big_ma":89, "invest_rate":0.2}) #KODEX 골드선물(H)
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



FixRate = 0.1 #각 자산별 할당 금액의 10%를 고정비중으로 투자함!
DynamicRate = 0.6 #각 자산별 할당 금액의 60%의 투자 비중은 모멘텀에 의해 정해짐!
#위의 경우 FixRate + DynamicRate = 0.7 즉 70%이니깐 매도신호 시 30%비중은 무조건 팔도록 되어 있다.
#위 두 값이 모두 0이라면 기존처럼 매도신호시 모두 판다!!



BOT_NAME = Common.GetNowDist() + "_MyMaStrategy_KR"

#포트폴리오 이름
PortfolioName = "이동평균자산배분전략_KR"



#리밸런싱이 가능한지 여부를 판단!
Is_Rebalance_Go = False
#마켓이 열렸는지 여부~!
IsMarketOpen = KisKR.IsMarketOpen()



#계좌 잔고를 가지고 온다!
Balance = KisKR.GetBalance()


print("--------------내 보유 잔고---------------------")

pprint.pprint(Balance)

print("--------------------------------------------")


#####################################################################################################################################
#####################################################################################################################################
#####################################################################################################################################





#####################################################################################################################################
#####################################################################################################################################
#####################################################################################################################################



#기준이 되는 내 총 평가금액에서 투자비중을 곱해서 나온 포트폴리오에 할당된 돈!!
TotalMoney = float(Balance['TotalMoney']) * InvestRate

print("총 포트폴리오에 할당된 투자 가능 금액 : ", TotalMoney)


##########################################################


#현재 투자중 상태인 리스트! (모두 파는게 아니라 부분 매도할 경우 매매 기준으로 삼기 위해 이 것이 필요하다.)
StockInvestList = list()

#파일 경로입니다.
invest_file_path = "/var/autobot/"+BOT_NAME+"_StockInvestList.json"
try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(invest_file_path, 'r') as json_file:
        StockInvestList = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")



#투자 주식 리스트
MyPortfolioList = list()



for stock_info in InvestStockList:

    asset = dict()
    asset['stock_code'] = stock_info['stock_code']         #종목코드
    asset['stock_name'] = KisKR.GetStockName(stock_info['stock_code'])
    asset['small_ma'] = stock_info['small_ma']  
    asset['big_ma'] = stock_info['big_ma']  
    asset['stock_target_rate'] = stock_info['invest_rate']      #비중..
    asset['stock_rebalance_amt'] = 0  #리밸런싱 수량
    asset['status'] = 'NONE'
    MyPortfolioList.append(asset)





##########################################################

print("--------------내 보유 주식---------------------")
#그리고 현재 이 계좌에서 보유한 주식 리스트를 가지고 옵니다!
MyStockList = KisKR.GetMyStockList()
pprint.pprint(MyStockList)
print("--------------------------------------------")
##########################################################



print("--------------리밸런싱 계산 ---------------------")




stock_df_list = []

for stock_info in InvestStockList:
    
    stock_code = stock_info['stock_code']
    
    #################################################################
    #################################################################
    df = Common.GetOhlcv("KR", stock_code,300) 
    #################################################################
    #################################################################


    df['prevClose'] = df['close'].shift(1)

    
    ############# 이동평균선! ###############
    ma_dfs = []

    # 이동 평균 계산
    for ma in range(3, 201):
        ma_df = df['close'].rolling(ma).mean().rename(str(ma) + 'ma_before').shift(1)
        ma_dfs.append(ma_df)
        
        ma_df = df['close'].rolling(ma).mean().rename(str(ma) + 'ma_before2').shift(2)
        ma_dfs.append(ma_df)
    # 이동 평균 데이터 프레임을 하나로 결합
    ma_df_combined = pd.concat(ma_dfs, axis=1)

    # 원본 데이터 프레임과 결합
    df = pd.concat([df, ma_df_combined], axis=1)

    ########################################

    #200거래일 평균 모멘텀
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


    stock_df_list.append(data_dict)
        
    print("---stock_code---", stock_code , " len ",len(df))
    
    pprint.pprint(df)




combined_df = pd.concat([list(data_dict.values())[0].assign(stock_code=stock_code) for data_dict in stock_df_list for stock_code in data_dict])
combined_df.sort_index(inplace=True)
pprint.pprint(combined_df)
print(" len(combined_df) ", len(combined_df))



date = combined_df.iloc[-1].name



TodayRebalanceList = list()


#리밸런싱 수량을 확정한다!
for stock_info in MyPortfolioList:

    stock_code = stock_info['stock_code']
    stock_name = stock_info['stock_name']


    stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)] 

    
    if len(stock_data) == 1:
        
        
        stock_amt = 0 #수량

        #내가 보유한 주식 리스트에서 매수된 잔고 정보를 가져온다
        for my_stock in MyStockList:
            if my_stock['StockCode'] == stock_code:
                stock_amt = int(my_stock['StockAmt'])
                break
            
            
        NowClosePrice = stock_data['close'].values[0]
        
        

        ma1 = stock_info['small_ma']
        ma2 = stock_info['big_ma']
        
                
        small_ma = int(ma1)
        big_ma = int(ma2)


        #이평선에 의해 매도처리 해야 된다!!! 
        if stock_code in StockInvestList and stock_amt > 0:
            print(stock_name , " " , stock_code, " 보유중... 매도 조건 체크!!")
            
            if stock_data[str(small_ma)+'ma_before'].values[0] < stock_data[str(big_ma)+'ma_before'].values[0] and stock_data[str(small_ma)+'ma_before2'].values[0] > stock_data[str(small_ma)+'ma_before'].values[0]:
                Is_Rebalance_Go = True
                
                SellRate = FixRate + (stock_data['Average_Momentum'].values[0] * DynamicRate) 
                
                
                
                stock_info['stock_target_rate'] *= SellRate
                stock_info['status'] = 'SELL'
                print(stock_name , " " , stock_code, " 매도조건 만족!!!", stock_info['stock_target_rate']*100, "% 비중을 맞춰서 매매해야 함!")
                
                TodayRebalanceList.append(stock_code)
                
    

        if stock_code not in StockInvestList: 
            print(stock_name , " " , stock_code, " 전략의 매수 상태가 아님")
            if stock_data[str(small_ma)+'ma_before'].values[0] > stock_data[str(big_ma)+'ma_before'].values[0] and stock_data[str(small_ma)+'ma_before2'].values[0] < stock_data[str(small_ma)+'ma_before'].values[0]:
                Is_Rebalance_Go = True
                stock_info['status'] = 'BUY'
                print(stock_name , " " , stock_code, " 매수조건 만족!!!", stock_info['stock_target_rate']*100, "% 비중을 맞춰서 매매해야 함!")
                
                TodayRebalanceList.append(stock_code)
            




strResult = "-- 현재 포트폴리오 상황 --\n"

#매수된 자산의 총합!
total_stock_money = 0

#현재 평가금액 기준으로 각 자산이 몇 주씩 매수해야 되는지 계산한다 (포트폴리오 비중에 따라) 이게 바로 리밸런싱 목표치가 됩니다.
for stock_info in MyPortfolioList:

    #내주식 코드
    stock_code = stock_info['stock_code']


    #현재가!
    CurrentPrice = KisKR.GetCurrentPrice(stock_code)


    
    stock_name = stock_info['stock_name']
    stock_amt = 0 #수량
    stock_avg_price = 0 #평단
    stock_eval_totalmoney = 0 #총평가금액!
    stock_revenue_rate = 0 #종목 수익률
    stock_revenue_money = 0 #종목 수익금

 

    #내가 보유한 주식 리스트에서 매수된 잔고 정보를 가져온다
    for my_stock in MyStockList:
        if my_stock['StockCode'] == stock_code:
            stock_name = my_stock['StockName']
            stock_amt = int(my_stock['StockAmt'])
            stock_avg_price = float(my_stock['StockAvgPrice'])
            stock_eval_totalmoney = float(my_stock['StockNowMoney'])
            stock_revenue_rate = float(my_stock['StockRevenueRate'])
            stock_revenue_money = float(my_stock['StockRevenueMoney'])

            break

    print("##### stock_code: ", stock_code)

    
    #매수할 자산 보유할 자산의 비중을 넣어준다!
    stock_target_rate = float(stock_info['stock_target_rate']) 

    #오늘 리밸런싱 대상이 아닌 종목인데 보유비중이 한개도 없다???
    if stock_code not in TodayRebalanceList:
        if stock_amt == 0:
            stock_target_rate *= FixRate #보유하고자 했던 고정비중은 매수하도록 한다!!
            stock_info['status'] = 'BUY_S'
            msg = PortfolioName + " 투자 비중이 없어 "+ stock_name + " " + stock_code+" 종목의 할당 비중의 1/10을 투자하도록 함!"
            print(msg)
            line_alert.SendMessage(msg)
        
        
    #주식의 총 평가금액을 더해준다
    total_stock_money += stock_eval_totalmoney

    #현재 비중
    stock_now_rate = 0

    #잔고에 있는 경우 즉 이미 매수된 주식의 경우
    if stock_amt > 0:


        stock_now_rate = round((stock_eval_totalmoney / TotalMoney),3)

        print("---> NowRate:", round(stock_now_rate * 100.0,2), "%")
        
        if stock_info['status'] != 'NONE':

            if stock_target_rate == 0:
                stock_info['stock_rebalance_amt'] = -stock_amt
                print("!!!!!!!!! SELL")
                
            else:
                #목표한 비중이 다르다면!!
                if stock_now_rate != stock_target_rate:


                    #갭을 구한다!!!
                    GapRate = stock_target_rate - stock_now_rate


                    #그래서 그 갭만큼의 금액을 구한다
                    GapMoney = TotalMoney * abs(GapRate) 
                    #현재가로 나눠서 몇주를 매매해야 되는지 계산한다
                    GapAmt = GapMoney / CurrentPrice


                    #수량이 1보다 커야 리밸러싱을 할 수 있다!! 즉 그 전에는 리밸런싱 불가 
                    if GapAmt >= 1.0:

                        GapAmt = int(GapAmt)

                        #갭이 음수라면! 비중이 더 많으니 팔아야 되는 상황!!! 
                        if GapRate < 0:
                            print("this!!!")
                            
                            stock_info['stock_rebalance_amt'] = -GapAmt

                        #갭이 양수라면 비중이 더 적으니 사야되는 상황!
                        else:  
                            stock_info['stock_rebalance_amt'] = GapAmt




    #잔고에 없는 경우
    else:


        print("---> NowRate: 0%")
        if stock_target_rate > 0:
            
            if stock_info['status'] == 'BUY' or stock_info['status'] == 'BUY_S':
                
                #비중대로 매수할 총 금액을 계산한다 
                BuyMoney = TotalMoney * stock_target_rate


                #매수할 수량을 계산한다!
                BuyAmt = int(BuyMoney / CurrentPrice)

                if BuyAmt <= 0:
                    BuyAmt = 1

                stock_info['stock_rebalance_amt'] = BuyAmt


    
        
        
        
    #라인 메시지랑 로그를 만들기 위한 문자열 
    line_data =  (">> " + stock_name + " " + stock_code + " << \n비중: " + str(round(stock_now_rate * 100.0,2)) + "/" + str(round(stock_target_rate * 100.0,2)) 
    + "% \n수익: $" + str(stock_revenue_money) + "("+ str(round(stock_revenue_rate,2)) 
    + "%) \n총평가금액: $" + str(round(stock_eval_totalmoney,2)) 
    + "\n현재보유수량: " + str(stock_amt) 
    + "\n리밸런싱수량: " + str(stock_info['stock_rebalance_amt']) + "\n----------------------\n")


    if Is_Rebalance_Go == True:
        line_alert.SendMessage(line_data)
    strResult += line_data



##########################################################

print("--------------리밸런싱 해야 되는 수량-------------")

data_str = "\n" + PortfolioName + "\n" +  strResult + "\n포트폴리오할당금액: $" + str(round(TotalMoney,2)) + "\n매수한자산총액: $" + str(round(total_stock_money,2))

#결과를 출력해 줍니다!
print(data_str)
#영상엔 없지만 리밸런싱이 가능할때만 내게 메시지를 보내자!
#if Is_Rebalance_Go == True:
#    line_alert.SendMessage(data_str)
    
#만약 위의 한번에 보내는 라인메시지가 짤린다면 아래 주석을 해제하여 개별로 보내면 됩니다
if Is_Rebalance_Go == True:
    line_alert.SendMessage("\n포트폴리오할당금액: $" + str(round(TotalMoney,2)) + "\n매수한자산총액: $" + str(round(total_stock_money,2)))




print("--------------------------------------------")

if Is_Rebalance_Go == True:
    if IsMarketOpen == False:
        msg = PortfolioName + " 매매할 종목이 있어 리밸런싱 수행 해야 하지만 지금은 장이 열려있지 않아요!"
        print(msg)
        line_alert.SendMessage(msg)
        

#'''
#리밸런싱이 가능한 상태여야 하고 매수 매도는 장이 열려있어야지만 가능하다!!!
if Is_Rebalance_Go == True and IsMarketOpen == True:
    
    if ENABLE_ORDER_EXECUTION == True:

        line_alert.SendMessage(PortfolioName + " 리밸런싱 시작!!")

        print("------------------리밸런싱 시작  ---------------------")


        #이제 목표치에 맞게 포트폴리오를 조정하면 되는데
        #매도를 해야 돈이 생겨 매수를 할 수 있을 테니
        #먼저 매도를 하고
        #그 다음에 매수를 해서 포트폴리오를 조정합니다!

        print("--------------매도 (리밸런싱 수량이 마이너스인거)---------------------")

        for stock_info in MyPortfolioList:

            #내주식 코드
            stock_code = stock_info['stock_code']
            rebalance_amt = stock_info['stock_rebalance_amt']

            #리밸런싱 수량이 마이너스인 것을 찾아 매도 한다!
            if rebalance_amt < 0:
                        
                #현재가!
                CurrentPrice = KisKR.GetCurrentPrice(stock_code)
                

                #현재가보다 아래에 매도 주문을 넣음으로써 시장가로 매도
                CurrentPrice *= 0.99
                pprint.pprint(KisKR.MakeSellLimitOrder(stock_code,abs(rebalance_amt),CurrentPrice))

        



        print("--------------------------------------------")


        #3초 정도 쉬어준다
        time.sleep(3.0)

                


        print("--------------매수 ---------------------")

        for stock_info in MyPortfolioList:

            #내주식 코드
            stock_code = stock_info['stock_code']
            rebalance_amt = stock_info['stock_rebalance_amt']

            #리밸런싱 수량이 플러스인 것을 찾아 매수 한다!
            if rebalance_amt > 0:
                        
                #현재가!
                CurrentPrice = KisKR.GetCurrentPrice(stock_code)



                #현재가보다 위에 매수 주문을 넣음으로써 시장가로 매수
                CurrentPrice *= 1.01
                data = KisKR.MakeBuyLimitOrder(stock_code,rebalance_amt,CurrentPrice)
                
                print(data)
                line_alert.SendMessage(PortfolioName + " " + stock_code + " " + str(data))
                


    


        print("--------------------------------------------")
        for stock_info in MyPortfolioList:
            stock_code = stock_info['stock_code']
            stock_name = stock_info['stock_name']


            if stock_info['status'] == 'BUY':
            
                StockInvestList.append(stock_code)

                line_alert.SendMessage(PortfolioName + " " + stock_name + " " + stock_code + " 전략 보유 처리!")
                
            if stock_info['status'] == 'SELL':
            
                StockInvestList.remove(stock_code)
                    
                line_alert.SendMessage(PortfolioName + " " + stock_name + " " + stock_code + " 전략 미보유 처리!")
                
        #파일에 저장
        with open(invest_file_path, 'w') as outfile:
            json.dump(StockInvestList, outfile)
                

        line_alert.SendMessage(PortfolioName + "  리밸런싱 완료!!")
        print("------------------리밸런싱 끝---------------------")

    else:
        print("코드 맨 첫 부분에 ENABLE_ORDER_EXECUTION 값을 True로 변경해야 매수매도가 진행됩니다!")