# -*- coding: utf-8 -*-
'''
1. 기본 종목 ETF 5개 종목에 투자하는 상품
2. 자산여부를 portfolio_config.json에서 가져오게 변경.

관련 포스팅
https://blog.naver.com/zacra/223597500754


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

'''
import KIS_Common as Common
import pandas as pd
import KIS_API_Helper_KR as KisKR
import time
import json
import pprint
import sys
import os
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)
import telegram_sender as telegram
import logging
from datetime import datetime
from portfolio_manager import PortfolioManager 

#계좌 선택.. "VIRTUAL" 는 모의 계좌!
Common.SetChangeMode("REAL") #REAL or VIRTUAL

# 로깅 설정
script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, 'MA_Strategy_KR_Bot_v3.log'), mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

#BOT_NAME = Common.GetNowDist() + "_MyMaStrategy_KR"
BOT_NAME = "MA_Strategy_KR_Bot_v3"

#포트폴리오 이름
PortfolioName = "이동평균자산배분전략_KR"

# 주말 가드: 토(5)/일(6)에는 실행하지 않고 즉시 종료 (텔레그램 전송 없음)
now = datetime.now()
if now.weekday() >= 5:
    msg = f"{PortfolioName}({now.strftime('%Y-%m-%d')})\n주말(토/일)에는 실행하지 않습니다."
    logging.info(msg)
    sys.exit(0)

#마켓이 열렸는지 여부~!
IsMarketOpen = KisKR.IsMarketOpen()

# 장 상태에 따른 로그 메시지
current_date = time.strftime("%Y-%m-%d")
if IsMarketOpen == True:
    logging.info(f"날짜 {current_date} : 장이 열려있습니다.")
    telegram.send(f"{PortfolioName}({current_date})\n장이 열려있습니다.")
else:
    logging.info(f"날짜 {current_date} : 장이 닫혀있습니다.")
    telegram.send(f"{PortfolioName}({current_date})\n장이 닫혀있습니다.")
    # 장이 닫혀있으면 더 이상 로그를 남기지 않고 종료
    sys.exit(0)

#####################################################################################################################################
'''
※ 주문 실행 여부 설정

ENABLE_ORDER_EXECUTION 값을 True로 변경할 경우,  
전략에 따라 매매가 일어납니다.

⚠️ 기본값은 False이며,  
실행 여부는 사용자 본인이 코드를 수정하여 결정해야 합니다.
'''

ENABLE_ORDER_EXECUTION = True  # 주문 실행 여부 설정 (기본값: False)


# portfolio_config.json에서 설정값들을 가져옴
# 스크립트 파일의 디렉토리를 기준으로 portfolio_config.json 파일 경로 설정
config_file_path = os.path.join(script_dir, 'portfolio_config.json')

try:
    with open(config_file_path, 'r', encoding='utf-8') as f:
        portfolio_config = json.load(f)
        bot_config = portfolio_config['bots']['MA_Strategy_KR_Bot_v3']
        
        # 투자 비중 가져오기
        InvestRate = bot_config['allocation_rate']
        logging.info(f"portfolio_config.json에서 가져온 투자 비중: {InvestRate * 100}%")
        
        # FixRate와 DynamicRate 가져오기
        FixRate = bot_config['fix_rate']
        DynamicRate = bot_config['dynamic_rate']
        logging.info(f"FixRate: {FixRate * 100}%, DynamicRate: {DynamicRate * 100}%")
        
        # 투자종목리스트 가져오기
        InvestStockList = bot_config['invest_stock_list']
        logging.info(f"투자종목 수: {len(InvestStockList)}개")
        for stock in InvestStockList:
            logging.info(f"  - {stock['stock_name']} ({stock['stock_code']})")
            
except Exception as e:
    logging.error(f"portfolio_config.json 파일 읽기 실패: {e}")
    logging.error("프로그램을 종료합니다.")
    telegram.send(f"portfolio_config.json 파일 읽기 실패: {e}\n프로그램을 종료합니다.")
    sys.exit(1)


#####################################################################################################################################

#위의 경우 FixRate + DynamicRate = 0.7 즉 70%이니깐 매도신호 시 30%비중은 무조건 팔도록 되어 있다.
#위 두 값이 모두 0이라면 기존처럼 매도신호시 모두 판다!!

# 포트폴리오 매니저 인스턴스 생성
portfolio_manager = PortfolioManager()

#리밸런싱이 가능한지 여부를 판단!
Is_Rebalance_Go = False

#계좌 잔고를 가지고 온다!
Balance = KisKR.GetBalance()

logging.info("--------------내 보유 잔고---------------------")
logging.info(pprint.pformat(Balance))
logging.info("--------------------------------------------")


#####################################################################################################################################
#####################################################################################################################################
#####################################################################################################################################





#####################################################################################################################################
#####################################################################################################################################
#####################################################################################################################################



#기준이 되는 내 총 평가금액에서 투자비중을 곱해서 나온 포트폴리오에 할당된 돈!!
TotalMoney = float(Balance['TotalMoney']) * InvestRate

logging.info(f"총 포트폴리오에 할당된 투자 가능 금액 : {TotalMoney}")


##########################################################


#현재 투자중 상태인 리스트! (모두 파는게 아니라 부분 매도할 경우 매매 기준으로 삼기 위해 이 것이 필요하다.)
StockInvestList = list()

#파일 경로입니다.
invest_file_path = os.path.join(script_dir, BOT_NAME+"_StockInvestList.json")
try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(invest_file_path, 'r') as json_file:
        StockInvestList = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    logging.info("Exception by First")



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

logging.info("--------------내 보유 주식---------------------")
#그리고 현재 이 계좌에서 보유한 주식 리스트를 가지고 옵니다!
MyStockList = KisKR.GetMyStockList()
logging.info(pprint.pformat(MyStockList))
logging.info("--------------------------------------------")
##########################################################



#logging.info("--------------리밸런싱 계산 ---------------------")

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

combined_df = pd.concat([list(data_dict.values())[0].assign(stock_code=stock_code) for data_dict in stock_df_list for stock_code in data_dict])
combined_df.sort_index(inplace=True)
#logging.info(pprint.pformat(combined_df))
#logging.info(f" len(combined_df) {len(combined_df)}")

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
            logging.info(f"{stock_name} {stock_code} 보유중... 매도 조건 체크!!")
            
            if stock_data[str(small_ma)+'ma_before'].values[0] < stock_data[str(big_ma)+'ma_before'].values[0] and stock_data[str(small_ma)+'ma_before2'].values[0] > stock_data[str(small_ma)+'ma_before'].values[0]:
                Is_Rebalance_Go = True
                
                SellRate = FixRate + (stock_data['Average_Momentum'].values[0] * DynamicRate) 
                
                
                
                stock_info['stock_target_rate'] *= SellRate
                stock_info['status'] = 'SELL'
                logging.info(f"{stock_name} {stock_code} 매도조건 만족!!! {stock_info['stock_target_rate']*100}% 비중을 맞춰서 매매해야 함!")
                
                TodayRebalanceList.append(stock_code)
                
    

        if stock_code not in StockInvestList: 
            logging.info(f"{stock_name} {stock_code} 전략의 매수 상태가 아님")
            if stock_data[str(small_ma)+'ma_before'].values[0] > stock_data[str(big_ma)+'ma_before'].values[0] and stock_data[str(small_ma)+'ma_before2'].values[0] < stock_data[str(small_ma)+'ma_before'].values[0]:
                Is_Rebalance_Go = True
                stock_info['status'] = 'BUY'
                logging.info(f"{stock_name} {stock_code} 매수조건 만족!!! {stock_info['stock_target_rate']*100}% 비중을 맞춰서 매매해야 함!")
                
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

    logging.info(f"##### stock_code: {stock_code}")

    
    #매수할 자산 보유할 자산의 비중을 넣어준다!
    stock_target_rate = float(stock_info['stock_target_rate']) 

    #오늘 리밸런싱 대상이 아닌 종목인데 보유비중이 한개도 없다???
    if stock_code not in TodayRebalanceList:
        if stock_amt == 0:
            stock_target_rate *= FixRate #보유하고자 했던 고정비중은 매수하도록 한다!!
            stock_info['status'] = 'BUY_S'
            msg = PortfolioName + " 투자 비중이 없어 "+ stock_name + " " + stock_code+" 종목의 할당 비중의 1/10을 투자하도록 함!"
            logging.info(msg)
            telegram.send(msg)
        
        
    #주식의 총 평가금액을 더해준다
    total_stock_money += stock_eval_totalmoney

    #현재 비중
    stock_now_rate = 0

    #잔고에 있는 경우 즉 이미 매수된 주식의 경우
    if stock_amt > 0:


        stock_now_rate = round((stock_eval_totalmoney / TotalMoney),3)

        logging.info(f"---> NowRate: {round(stock_now_rate * 100.0,2)}%")
        
        if stock_info['status'] != 'NONE':

            if stock_target_rate == 0:
                stock_info['stock_rebalance_amt'] = -stock_amt
                logging.info("!!!!!!!!! SELL")
                
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


        logging.info("---> NowRate: 0%")
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
        # 개별 종목 메시지는 주석 처리하여 중복 방지
        # telegram.send(line_data)
        pass
    strResult += line_data



##########################################################

logging.info("--------------리밸런싱 해야 되는 수량-------------")

data_str = "\n" + PortfolioName + "\n" +  strResult + "\n포트폴리오할당금액: $" + str(round(TotalMoney,2)) + "\n매수한자산총액: $" + str(round(total_stock_money,2))

#결과를 출력해 줍니다!
logging.info(data_str)
#영상엔 없지만 리밸런싱이 가능할때만 내게 메시지를 보내자!
#if Is_Rebalance_Go == True:
#    line_alert.SendMessage(data_str)
    
#만약 위의 한번에 보내는 라인메시지가 짤린다면 아래 주석을 해제하여 개별로 보내면 됩니다
if Is_Rebalance_Go == True:
    # 포트폴리오 요약 메시지는 주석 처리하여 중복 방지
    # telegram.send("\n포트폴리오할당금액: $" + str(round(TotalMoney,2)) + "\n매수한자산총액: $" + str(round(total_stock_money,2)))
    pass




logging.info("--------------------------------------------")

if Is_Rebalance_Go == True:
    if IsMarketOpen == False:
        msg = PortfolioName + " 매매할 종목이 있어 리밸런싱 수행 해야 하지만 지금은 장이 열려있지 않아요!"
        logging.info(msg)
        telegram.send(msg)
        

#'''
#리밸런싱이 가능한 상태여야 하고 매수 매도는 장이 열려있어야지만 가능하다!!!
if Is_Rebalance_Go == True and IsMarketOpen == True:
    
    if ENABLE_ORDER_EXECUTION == True:

        # 리밸런싱 시작 메시지는 주석 처리하여 중복 방지
        # telegram.send(PortfolioName + " 리밸런싱 시작!!")

        logging.info("------------------리밸런싱 시작  ---------------------")


        #이제 목표치에 맞게 포트폴리오를 조정하면 되는데
        #매도를 해야 돈이 생겨 매수를 할 수 있을 테니
        #먼저 매도를 하고
        #그 다음에 매수를 해서 포트폴리오를 조정합니다!

        logging.info("--------------매도 (리밸런싱 수량이 마이너스인거)---------------------")

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
                logging.info(pprint.pformat(KisKR.MakeSellLimitOrder(stock_code,abs(rebalance_amt),CurrentPrice)))

        



        logging.info("--------------------------------------------")


        #3초 정도 쉬어준다
        time.sleep(3.0)

                


        logging.info("--------------매수 ---------------------")

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
                
                logging.info(data)
                # 매수 주문 메시지는 주석 처리하여 중복 방지
                # telegram.send(PortfolioName + " " + stock_code + " " + str(data))
                


    


        logging.info("--------------------------------------------")
        for stock_info in MyPortfolioList:
            stock_code = stock_info['stock_code']
            stock_name = stock_info['stock_name']


            if stock_info['status'] == 'BUY':
            
                StockInvestList.append(stock_code)

                # 전략 보유 처리 메시지는 주석 처리하여 중복 방지
                # telegram.send(PortfolioName + " " + stock_name + " " + stock_code + " 전략 보유 처리!")
                
            if stock_info['status'] == 'SELL':
            
                StockInvestList.remove(stock_code)
                    
                # 전략 미보유 처리 메시지는 주석 처리하여 중복 방지
                # telegram.send(PortfolioName + " " + stock_name + " " + stock_code + " 전략 미보유 처리!")
                
        #파일에 저장
        with open(invest_file_path, 'w') as outfile:
            json.dump(StockInvestList, outfile)
                

        # 리밸런싱 완료 메시지는 주석 처리하여 중복 방지
        # telegram.send(PortfolioName + "  리밸런싱 완료!!")
        logging.info("------------------리밸런싱 끝---------------------")

    else:
        logging.info("코드 맨 첫 부분에 ENABLE_ORDER_EXECUTION 값을 True로 변경해야 매수매도가 진행됩니다!")

# 포트폴리오 보유 종목 정보를 업데이트하는 함수
def update_portfolio_holdings():
    """현재 보유 종목 정보를 portfolio_config.json에 업데이트합니다."""
    try:
        # portfolio_config.json 파일 읽기
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_file_path = os.path.join(script_dir, "portfolio_config.json")
        
        with open(config_file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 현재 보유 주식 정보 가져오기
        MyStockList = KisKR.GetMyStockList()
        
        # 투자 대상 종목 코드 리스트 생성
        invest_stock_codes = [stock['stock_code'] for stock in InvestStockList]
        
        holdings = []
        total_holding_value = 0
        cumulative_profit = 0
        
        for stock in MyStockList:
            if stock['StockCode'] in invest_stock_codes:
                stock_name = stock['StockName']
                stock_code = stock['StockCode']
                stock_amt = int(stock['StockAmt'])
                stock_avg_price = float(stock['StockAvgPrice'])
                stock_now_price = float(stock['StockNowPrice'])
                stock_revenue_money = float(stock['StockRevenueMoney'])
                stock_revenue_rate = float(stock['StockRevenueRate'])
                
                # 현재 가치 계산
                current_value = stock_amt * stock_now_price
                total_holding_value += current_value
                cumulative_profit += stock_revenue_money
                
                # 보유 종목 정보 추가
                holding_info = {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "purchase_price": stock_avg_price,
                    "current_price": stock_now_price,
                    "quantity": stock_amt,
                    "profit_rate": stock_revenue_rate,
                    "current_value": current_value,
                    "profit_loss": stock_revenue_money
                }
                holdings.append(holding_info)
        
        # 현재 분배금 계산 (초기 분배금 + 평가 손익 + 실현 손익 누적)
        initial_allocation = config_data['bots']['MA_Strategy_KR_Bot_v3']['initial_allocation']
        realized_total_profit = config_data['bots']['MA_Strategy_KR_Bot_v3'].get('total_sold_profit', 0)
        current_allocation = initial_allocation + cumulative_profit + realized_total_profit
        
        # 현금 잔고 계산 (현재 분배금 - 보유 주식 평가금액)
        cash_balance = current_allocation - total_holding_value
        
        # portfolio_config.json 업데이트
        config_data['bots']['MA_Strategy_KR_Bot_v3']['current_allocation'] = current_allocation
        config_data['bots']['MA_Strategy_KR_Bot_v3']['holdings'] = holdings
        config_data['bots']['MA_Strategy_KR_Bot_v3']['total_holding_value'] = total_holding_value
        config_data['bots']['MA_Strategy_KR_Bot_v3']['cash_balance'] = cash_balance
        # 판매 누적 수익은 판매 시점에만 갱신되며 여기서 리셋하지 않습니다.
        config_data['bots']['MA_Strategy_KR_Bot_v3']['total_sold_profit'] = realized_total_profit
        
        # 파일에 저장
        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        
        logging.info("포트폴리오 보유 종목 정보가 성공적으로 업데이트되었습니다.")
        logging.info(f"총 보유 가치: {total_holding_value:,.0f}원")
        logging.info(f"누적 수익: {cumulative_profit:,.0f}원")
        logging.info(f"현금 잔고: {cash_balance:,.0f}원")
        
    except Exception as e:
        logging.error(f"포트폴리오 보유 종목 정보 업데이트 중 오류: {e}")

# 판매 시 누적 수익을 업데이트하는 함수
def update_sold_profits_on_sale(sold_stock_code, sold_quantity, sold_price, purchase_price):
    """주식 판매 시 4군데 수익 변수를 업데이트합니다."""
    try:
        # portfolio_config.json 파일 읽기
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_file_path = os.path.join(script_dir, "portfolio_config.json")
        
        with open(config_file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 판매 수익 계산
        sale_profit = (sold_price - purchase_price) * sold_quantity
        
        # 봇 설정에서 수익 변수들 업데이트
        bot_config = config_data['bots']['MA_Strategy_KR_Bot_v3']
        
        # 일별 판매수익 업데이트
        bot_config['daily_sold_profit'] = bot_config.get('daily_sold_profit', 0) + sale_profit
        
        # 월별 판매수익 업데이트
        bot_config['monthly_sold_profit'] = bot_config.get('monthly_sold_profit', 0) + sale_profit
        
        # 연별 판매수익 업데이트
        bot_config['yearly_sold_profit'] = bot_config.get('yearly_sold_profit', 0) + sale_profit
        
        # 총 판매수익 업데이트 (초기화되지 않음)
        bot_config['total_sold_profit'] = bot_config.get('total_sold_profit', 0) + sale_profit
        
        # 파일에 저장
        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        
        logging.info(f"판매수익 업데이트 완료: {sold_stock_code} - 판매 수익: {sale_profit:,.0f}원")
        logging.info(f"일별: {bot_config['daily_sold_profit']:,}원, 월별: {bot_config['monthly_sold_profit']:,}원, "
                    f"연별: {bot_config['yearly_sold_profit']:,}원, 총: {bot_config['total_sold_profit']:,}원")
        
    except Exception as e:
        logging.error(f"판매수익 업데이트 중 오류: {e}")

def initialize_period_profits():
    """일별, 월별, 연별 판매수익 초기화"""
    try:
        # portfolio_config.json 파일 읽기
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_file_path = os.path.join(script_dir, "portfolio_config.json")
        
        with open(config_file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        current_time = datetime.now()
        current_date = current_time.strftime("%Y-%m-%d")
        current_month = current_time.strftime("%Y-%m")
        current_year = current_time.strftime("%Y")
        
        # 봇 설정에서 마지막 초기화 정보 확인
        bot_config = config_data['bots']['MA_Strategy_KR_Bot_v3']
        
        last_daily = bot_config.get('last_daily_reset', '')
        last_monthly = bot_config.get('last_monthly_reset', '')
        last_yearly = bot_config.get('last_yearly_reset', '')
        
        # 일별 초기화 (매일)
        if last_daily != current_date:
            bot_config['daily_sold_profit'] = 0
            bot_config['last_daily_reset'] = current_date
            logging.info(f"[{current_date}] 일별 판매수익 초기화 완료")
            
        # 월별 초기화 (매월)
        if last_monthly != current_month:
            bot_config['monthly_sold_profit'] = 0
            bot_config['last_monthly_reset'] = current_month
            logging.info(f"[{current_month}] 월별 판매수익 초기화 완료")
            
        # 연별 초기화 (매년)
        if last_yearly != current_year:
            bot_config['yearly_sold_profit'] = 0
            bot_config['last_yearly_reset'] = current_year
            logging.info(f"[{current_year}] 연별 판매수익 초기화 완료")
            
        # 설정 저장
        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
            
    except Exception as e:
        logging.error(f"기간별 수익 초기화 중 오류: {e}")

def calculate_and_update_profit():
    """현재 수익을 계산하고 포트폴리오 매니저에 업데이트합니다."""
    try:
        # 현재 보유 주식 정보 가져오기
        MyStockList = KisKR.GetMyStockList()
        
        total_profit = 0
        total_investment = 0
        initial_investment = portfolio_manager.get_initial_investment() * InvestRate
        
        # 투자 대상 종목 코드 리스트 생성
        invest_stock_codes = [stock['stock_code'] for stock in InvestStockList]
        
        for stock in MyStockList:
            if stock['StockCode'] in invest_stock_codes:  # 투자 대상 종목만 계산
                try:
                    stock_profit = float(stock['StockRevenueMoney'])
                    stock_investment = float(stock['StockNowMoney'])
                    
                    total_profit += stock_profit
                    total_investment += stock_investment
                except (ValueError, KeyError) as e:
                    logging.error(f"주식 데이터 처리 중 오류: {e}")
                    continue
        
        # 수익률 계산
        profit_rate = (total_profit / initial_investment * 100) if initial_investment > 0 else 0
        
        # 포트폴리오 매니저에 업데이트
        portfolio_manager.update_bot_profit("MA_Strategy_KR_Bot_v3", total_profit, profit_rate)
        
        # 로그 출력
        logging.info("=== MA_Strategy_KR_Bot_v3 수익 현황 ===")
        logging.info(f"총 투자금액: {initial_investment:,.0f}원")
        logging.info(f"총 평가금액: {total_investment:,.0f}원")
        logging.info(f"총 수익금: {total_profit:,.0f}원")
        logging.info(f"수익률: {profit_rate:.2f}%")
        
        return total_profit, profit_rate, total_investment
        
    except Exception as e:
        logging.error(f"수익 계산 중 오류 발생: {e}")
        return 0, 0, 0

# 수익 정보 메시지 생성 함수
def create_profit_summary_message(total_profit, profit_rate, total_investment, current_date):
    """수익 요약 메시지를 생성합니다."""
    # portfolio_config.json에서 봇 정보 읽기
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_file_path = os.path.join(script_dir, "portfolio_config.json")
        
        with open(config_file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        initial_allocation = config_data['bots']['MA_Strategy_KR_Bot_v3']['initial_allocation']
        current_allocation = config_data['bots']['MA_Strategy_KR_Bot_v3']['current_allocation']
        total_sold_profit = config_data['bots']['MA_Strategy_KR_Bot_v3']['total_sold_profit']
    except Exception as e:
        logging.error(f"portfolio_config.json 읽기 중 오류: {e}")
        initial_allocation = 0
        current_allocation = 0
        total_sold_profit = 0
    
    # 현재 보유 주식 정보 가져오기
    MyStockList = KisKR.GetMyStockList()
    
    # 투자 대상 종목 코드 리스트 생성
    invest_stock_codes = [stock['stock_code'] for stock in InvestStockList]
    
    # 이모지 문자를 완전히 제거하고 안전한 문자로 대체
    message = f"📊 {PortfolioName}\n상세 수익 현황 ({current_date})\n"
    message += "=" * 34 + "\n"
    
    # 종목별 상세 정보 추가
    profit_stocks = 0
    loss_stocks = 0
    neutral_stocks = 0
    
    for stock in MyStockList:
        if stock['StockCode'] in invest_stock_codes:
            stock_name = stock['StockName']
            stock_code = stock['StockCode']
            stock_amt = int(stock['StockAmt'])
            stock_avg_price = float(stock['StockAvgPrice'])
            stock_now_price = float(stock['StockNowPrice'])
            stock_revenue_money = float(stock['StockRevenueMoney'])
            stock_revenue_rate = float(stock['StockRevenueRate'])
            
            # 수익/손실 상태 카운트
            if stock_revenue_money > 0:
                profit_stocks += 1
                status_emoji = "✅"  # V체크 아이콘으로 변경
            elif stock_revenue_money < 0:
                loss_stocks += 1
                status_emoji = "❌"  # X버튼 아이콘으로 변경
            else:
                neutral_stocks += 1
                status_emoji = "➖"
            
            # 총금액 계산
            total_amount = stock_amt * stock_now_price
            
            # 수익/손실 기호 결정
            profit_sign = "+" if stock_revenue_money >= 0 else ""
            rate_sign = "+" if stock_revenue_rate >= 0 else ""
            
            message += f"{status_emoji} {stock_name}({stock_amt}주)\n"
            message += f"   {total_amount:,.0f}원({profit_sign}{stock_revenue_money:,.0f}원:{rate_sign}{stock_revenue_rate:.2f}%)\n"
    
    # 전체 요약 정보
    message += "=" * 34 + "\n"
    message += f"💰 초기 분배금: {initial_allocation:,.0f}원\n"
    message += f"💰 현재 분배금: {current_allocation:,.0f}원\n"
    message += f"💰 총 투자금액: {total_investment:,.0f}원\n"
    message += f"📈 현재 수익금: {total_profit:,.0f}원({profit_rate:+.2f}%)\n"
    message += f"📊 누적 판매 수익금: {total_sold_profit:,.0f}원\n"
    message += f"📊 종목별 현황: 수익 {profit_stocks}개, 손실 {loss_stocks}개, 손익없음 {neutral_stocks}개\n"
    
    # 마지막 결과 메시지 삭제
    # if total_profit > 0:
    #     message += "[결과] 전체 수익 발생"
    # elif total_profit < 0:
    #     message += "[결과] 전체 손실 발생"
    # else:
    #     message += "[결과] 전체 손익 없음"
    
    return message

# 메인 실행 부분 추가
if __name__ == "__main__":
    # 중복 실행 방지를 위한 플래그
    import os
    lock_file = os.path.join(script_dir, "MA_Strategy_KR_Bot_v3.lock")
    
    try:
        # 이미 실행 중인지 확인
        if os.path.exists(lock_file):
            logging.info("이미 실행 중인 봇이 있습니다. 종료합니다.")
            telegram.send("MA_Strategy_KR_Bot_v3 : 이미 실행 중인 봇이 있습니다. 종료합니다.")
            sys.exit(0)
        
        # 락 파일 생성
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        
        logging.info("MA_Strategy_KR_Bot_v3 시작")
        logging.info("=" * 37)
        telegram.send("MA_Strategy_KR_Bot_v3 시작")
        
        # 봇 실행 시작 시 기간별 수익 초기화
        if ENABLE_ORDER_EXECUTION:
            # 일별, 월별, 연별 판매수익 초기화
            initialize_period_profits()
            
            logging.info("수익 계산 및 업데이트 시작")
            total_profit, profit_rate, total_investment = calculate_and_update_profit()
            
            # 보유 종목 정보를 portfolio_config.json에 업데이트
            update_portfolio_holdings()
            
            # 텔레그램으로 수익 정보 전송 (한 번만 전송)
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            profit_message = create_profit_summary_message(total_profit, profit_rate, total_investment, current_date)
            
            # 수익 메시지 전송 시도
            telegram.send(profit_message)
            logging.info("수익 정보 텔레그램 전송 완료")
            
            logging.info(f"수익 계산 완료 - 총 수익: {total_profit:,.0f}원, 수익률: {profit_rate:.2f}%")
            logging.info("수익 계산 및 업데이트 완료")
        
        logging.info("MA_Strategy_KR_Bot_v3 정상 종료")
        logging.info("=" * 37)
        
    except Exception as e:
        error_msg = f"MA_Strategy_KR_Bot_v3 실행 중 오류 발생: {e}"
        logging.error(error_msg)
        telegram.send(f"오류: {error_msg}")
        sys.exit(1)
    finally:
        # 락 파일 제거
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except:
            pass