#-*-coding:utf-8 -*-
'''

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
코드 참고 영상!
https://youtu.be/YdEdM-oC0kc
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$


$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

해당 컨텐츠는 제가 직접 투자 하기 위해 이 전략을 추가 개선해서 더 좋은 성과를 보여주는 개인 전략이 존재합니다. 

게만아 추가 개선 개인 전략들..
https://blog.naver.com/zacra/223196497504

관심 있으신 분은 위 포스팅을 참고하세요!

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$



관련 포스팅

코스닥 코스피 양방향으로 투자하는 전략! 초전도체 LK99에 버금가는 발견!!
https://blog.naver.com/zacra/223177598281

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
import os
import logging
import sys
from datetime import datetime

import sys
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)
import telegram_sender as telegram
from portfolio_manager import portfolio_manager
# from KIS_KR_SplitTrader import MakeSplitBuyOrder, MakeSplitSellOrder

# 로깅 설정
script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, 'Kosdaqpi_Bot.log'), mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

#계좌 선택.. "VIRTUAL" 는 모의 계좌!
Common.SetChangeMode("REAL") #REAL or VIRTUAL

#####################################################################################################################################
'''
※ 주문 실행 여부 설정

ENABLE_ORDER_EXECUTION 값을 True로 변경할 경우,  
전략에 따라 매매가 일어납니다.

⚠️ 기본값은 False이며,  
실행 여부는 사용자 본인이 코드를 수정하여 결정해야 합니다.
'''

ENABLE_ORDER_EXECUTION = True  # 주문 실행 여부 설정 (기본값: False)

'''
📌 본 전략은 시스템을 구현하는 예시 코드이며,  
실제 투자 및 주문 실행은 사용자 본인의 의사와 책임 하에 수행됩니다.
'''
#####################################################################################################################################

'''
📌 투자할 종목은 본인의 선택으로 리스트 형식으로 직접 입력하세요!
'''
#실제 투자 종목!!!
# 122630 : KODEX 레버리지
# 252670 : KODEX 200선물인버스2X
# 233740 : KODEX 코스닥150레버리지
# 251340 : KODEX 코스닥150선물인버스
InvestStockList = ["122630","252670","233740","251340"]

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
# 포트폴리오 매니저에서 설정 가져오기
InvestRate = portfolio_manager.get_bot_allocation("Kosdaqpi_Bot")  # 설정 파일에서 할당 비율 가져오기
#####################################################################################################################################

BOT_NAME = Common.GetNowDist() + "autonam_Kospidaq_Bot"

#포트폴리오 이름
PortfolioName = "코스피닥 매매 전략!"

#시간 정보를 읽는다
time_info = time.gmtime()

day_n = time_info.tm_mday
day_str = str(time_info.tm_mon) + "-" + str(time_info.tm_mday)

logging.info(f"날짜: {day_str}")

# 주말 가드: 토(5)/일(6)에는 실행하지 않고 즉시 종료
now = datetime.now()
if now.weekday() >= 5:
    msg = f"{PortfolioName}({now.strftime('%Y-%m-%d')})\n주말(토/일)에는 실행하지 않습니다."
    logging.info(msg)
    sys.exit(0)

###################################################################
###################################################################
#리스트에서 데이터를 리턴!
def GetKospidaqStrategyData(stock_code,KospidaqStrategyList):
    ResultData = None
    for KospidaqStrategyData in KospidaqStrategyList:
        if KospidaqStrategyData['StockCode'] == stock_code:
            ResultData = KospidaqStrategyData
            break
    return ResultData

#투자개수
def GetKospidaqInvestCnt(KospidaqStrategyList):
    
    MyStockList = KisKR.GetMyStockList()

    InvestCnt = 0
        
    for KospidaqStrategyData in KospidaqStrategyList:
        stock_code = KospidaqStrategyData['StockCode']
        
        stock_amt = 0
        #내가 보유한 주식 리스트에서 매수된 잔고 정보를 가져온다
        for my_stock in MyStockList:
            if my_stock['StockCode'] == stock_code:
                stock_amt = int(my_stock['StockAmt'])
                break
            
        if stock_amt > 0:
            InvestCnt += 1
                  
    return InvestCnt

# 거래 기록을 저장하는 함수들
def save_trade_history(trade_type, stock_code, stock_name, quantity, unit_price, amount, fee=0):
    """거래 내역을 Kosdaqpi_Bot_history.json 파일에 저장합니다."""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        history_file_path = os.path.join(script_dir, "Kosdaqpi_Bot_history.json")
        
        # 기존 거래 내역 읽기
        trade_history = []
        if os.path.exists(history_file_path):
            try:
                with open(history_file_path, 'r', encoding='utf-8') as f:
                    trade_history = json.load(f)
            except Exception as e:
                logging.error(f"거래 내역 파일 읽기 오류: {e}")
                trade_history = []
        
        # 새로운 거래 내역 추가
        current_time = datetime.now()
        trade_record = {
            "일자": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "구분": trade_type,  # "구매" 또는 "판매"
            "코드": stock_code,
            "네임": stock_name,
            "수량": quantity,
            "단가": unit_price,
            "금액": amount,
            "수수료": fee
        }
        
        trade_history.append(trade_record)
        
        # 파일에 저장
        with open(history_file_path, 'w', encoding='utf-8') as f:
            json.dump(trade_history, f, ensure_ascii=False, indent=4)
        
        logging.info(f"거래 내역 저장 완료: {trade_type} - {stock_name}({stock_code}) {quantity}주 @ {unit_price:,.0f}원")
        
    except Exception as e:
        logging.error(f"거래 내역 저장 중 오류: {e}")

def save_buy_history(stock_code, stock_name, quantity, unit_price, amount, fee=0):
    """매수 내역을 저장합니다."""
    save_trade_history("구매", stock_code, stock_name, quantity, unit_price, amount, fee)

def save_sell_history(stock_code, stock_name, quantity, unit_price, amount, fee=0):
    """매도 내역을 저장합니다."""
    save_trade_history("판매", stock_code, stock_name, quantity, unit_price, amount, fee)

def calculate_profit_from_history():
    """거래 내역을 기반으로 수익률을 계산합니다."""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        history_file_path = os.path.join(script_dir, "Kosdaqpi_Bot_history.json")
        
        if not os.path.exists(history_file_path):
            logging.warning("거래 내역 파일이 존재하지 않습니다.")
            return 0, 0, 0, 0
        
        with open(history_file_path, 'r', encoding='utf-8') as f:
            trade_history = json.load(f)
        
        # 종목별 매수/매도 내역 정리
        stock_summary = {}
        
        for trade in trade_history:
            stock_code = trade['코드']
            stock_name = trade['네임']
            trade_type = trade['구분']
            quantity = trade['수량']
            unit_price = trade['단가']
            amount = trade['금액']
            
            if stock_code not in stock_summary:
                stock_summary[stock_code] = {
                    'name': stock_name,
                    'buy_quantity': 0,
                    'buy_amount': 0,
                    'sell_quantity': 0,
                    'sell_amount': 0,
                    'avg_buy_price': 0
                }
            
            if trade_type == "구매":
                stock_summary[stock_code]['buy_quantity'] += quantity
                stock_summary[stock_code]['buy_amount'] += amount
            elif trade_type == "판매":
                stock_summary[stock_code]['sell_quantity'] += quantity
                stock_summary[stock_code]['sell_amount'] += amount
        
        # 수익률 계산
        total_profit = 0
        total_investment = 0
        total_realized_profit = 0
        
        for stock_code, summary in stock_summary.items():
            if summary['buy_quantity'] > 0:
                # 평균 매수가 계산
                avg_buy_price = summary['buy_amount'] / summary['buy_quantity']
                summary['avg_buy_price'] = avg_buy_price
                
                # 현재 보유 수량
                current_quantity = summary['buy_quantity'] - summary['sell_quantity']
                
                if current_quantity > 0:
                    # 현재가 가져오기 (실제로는 API 호출 필요)
                    try:
                        current_price = KisKR.GetCurrentPrice(stock_code)
                        current_value = current_quantity * current_price
                        unrealized_profit = current_value - (current_quantity * avg_buy_price)
                        total_profit += unrealized_profit
                        total_investment += current_value
                    except Exception as e:
                        logging.warning(f"현재가 조회 실패 ({stock_code}): {e}")
                        # 현재가를 가져올 수 없는 경우 평균 매수가로 계산
                        total_investment += current_quantity * avg_buy_price
                
                # 실현 손익 계산
                if summary['sell_quantity'] > 0:
                    realized_profit = summary['sell_amount'] - (summary['sell_quantity'] * avg_buy_price)
                    total_realized_profit += realized_profit
        
        # 전체 수익률 계산
        profit_rate = 0
        if total_investment > 0:
            profit_rate = (total_profit / total_investment) * 100
        
        logging.info(f"거래 내역 기반 수익 계산 완료:")
        logging.info(f"총 투자금액: {total_investment:,.0f}원")
        logging.info(f"총 평가손익: {total_profit:,.0f}원")
        logging.info(f"총 실현손익: {total_realized_profit:,.0f}원")
        logging.info(f"수익률: {profit_rate:.2f}%")
        
        return total_profit, profit_rate, total_investment, total_realized_profit
        
    except Exception as e:
        logging.error(f"거래 내역 기반 수익 계산 중 오류: {e}")
        return 0, 0, 0, 0

def get_trade_history_summary():
    """거래 내역 요약 정보를 반환합니다."""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        history_file_path = os.path.join(script_dir, "Kosdaqpi_Bot_history.json")
        
        if not os.path.exists(history_file_path):
            return "거래 내역이 없습니다."
        
        with open(history_file_path, 'r', encoding='utf-8') as f:
            trade_history = json.load(f)
        
        if not trade_history:
            return "거래 내역이 없습니다."
        
        # 거래 통계 계산
        total_trades = len(trade_history)
        buy_trades = len([t for t in trade_history if t['구분'] == '구매'])
        sell_trades = len([t for t in trade_history if t['구분'] == '판매'])
        
        # 종목별 거래 요약
        stock_summary = {}
        for trade in trade_history:
            stock_code = trade['코드']
            stock_name = trade['네임']
            trade_type = trade['구분']
            quantity = trade['수량']
            amount = trade['금액']
            
            if stock_code not in stock_summary:
                stock_summary[stock_code] = {
                    'name': stock_name,
                    'total_buy_quantity': 0,
                    'total_buy_amount': 0,
                    'total_sell_quantity': 0,
                    'total_sell_amount': 0
                }
            
            if trade_type == '구매':
                stock_summary[stock_code]['total_buy_quantity'] += quantity
                stock_summary[stock_code]['total_buy_amount'] += amount
            else:
                stock_summary[stock_code]['total_sell_quantity'] += quantity
                stock_summary[stock_code]['total_sell_amount'] += amount
        
        # 요약 메시지 생성
        summary = f"📊 Kosdaqpi_Bot 거래 내역 요약\n"
        summary += f"총 거래 건수: {total_trades}건 (매수: {buy_trades}건, 매도: {sell_trades}건)\n\n"
        
        summary += "종목별 거래 현황:\n"
        for stock_code, data in stock_summary.items():
            summary += f"• {data['name']} ({stock_code})\n"
            summary += f"  - 매수: {data['total_buy_quantity']}주 ({data['total_buy_amount']:,.0f}원)\n"
            summary += f"  - 매도: {data['total_sell_quantity']}주 ({data['total_sell_amount']:,.0f}원)\n"
            summary += f"  - 보유: {data['total_buy_quantity'] - data['total_sell_quantity']}주\n\n"
        
        return summary
        
    except Exception as e:
        logging.error(f"거래 내역 요약 생성 중 오류: {e}")
        return f"거래 내역 요약 생성 중 오류가 발생했습니다: {e}"

# 판매 시 누적 수익을 업데이트하는 함수
def update_cumulative_profit_on_sale(stock_code, stock_amt, current_price, avg_price):
    """주식 판매 시 누적 수익을 업데이트합니다."""
    try:
        # 판매 수익 계산
        sale_profit = (current_price - avg_price) * stock_amt
        
        # 전역 변수에 누적 수익 추가
        global cumulative_profit
        if 'cumulative_profit' not in globals():
            cumulative_profit = 0
        cumulative_profit += sale_profit
        
        logging.info(f"누적 수익 업데이트: {stock_code} - 판매 수익: {sale_profit:,.0f}원, 누적: {cumulative_profit:,.0f}원")
        
    except Exception as e:
        logging.error(f"누적 수익 업데이트 중 오류: {e}")

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
        bot_config = config_data['bots']['Kosdaqpi_Bot']
        
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


#####################################################################################################################################

#계좌 잔고를 가지고 온다!
Balance = KisKR.GetBalance()
#####################################################################################################################################

'''-------통합 증거금 사용자는 아래 코드도 사용할 수 있습니다! -----------'''
#통합증거금 계좌 사용자 분들중 만약 미국계좌랑 통합해서 총자산을 계산 하고 포트폴리오 비중에도 반영하고 싶으시다면 아래 코드를 사용하시면 되고 나머지는 동일합니다!!!
#Balance = Common.GetBalanceKrwTotal()

'''-----------------------------------------------------------'''
#####################################################################################################################################


logging.info("--------------내 보유 잔고---------------------")

logging.info(f"잔고 정보: {Balance}")

logging.info("--------------------------------------------")


##########################################################

logging.info("--------------내 보유 주식---------------------")
#그리고 현재 이 계좌에서 보유한 주식 리스트를 가지고 옵니다!
MyStockList = KisKR.GetMyStockList()
logging.info(f"보유 주식 정보: {MyStockList}")
logging.info("--------------------------------------------")
##########################################################





NowInvestMoney = 0

for stock_code in InvestStockList:
    stock_name = ""
    stock_amt = 0 #수량
    stock_avg_price = 0 #평단

    #내가 보유한 주식 리스트에서 매수된 잔고 정보를 가져온다
    for my_stock in MyStockList:
        if my_stock['StockCode'] == stock_code:
            stock_name = my_stock['StockName']
            stock_amt = int(my_stock['StockAmt'])
            stock_avg_price = float(my_stock['StockAvgPrice'])

            
            NowInvestMoney += (stock_amt*stock_avg_price)
            break



###################################################################
###################################################################
KospidaqStrategyList = list()
#파일 경로입니다.
script_dir = os.path.dirname(os.path.abspath(__file__))
data_file_path = os.path.join(script_dir, "Kosdaqpi_Bot_Stock.json")

try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(data_file_path, 'r') as json_file:
        KospidaqStrategyList = json.load(json_file)

except Exception as e:
    logging.info("Init....")

    for stock_code in InvestStockList:
        KospidaqStrategyData = dict()
        KospidaqStrategyData['StockCode'] = stock_code #대상 종목 코드
        KospidaqStrategyData['StockName'] = KisKR.GetStockName(stock_code) #종목 이름
        KospidaqStrategyData['Status'] = "REST" #상태 READY(돌파를체크해야하는 준비상태), INVESTING(돌파해서 투자중), INVESTING_TRY(매수 주문 들어감) REST(조건불만족,투자안함,돌파체크안함) 
        KospidaqStrategyData['DayStatus'] = "NONE" #오늘 매수(BUY)하는 날인지 매도(SELL)하는 날인지 대상이 아닌지 (NONE) 체크
        KospidaqStrategyData['TargetPrice'] = 0 #돌파가격
        KospidaqStrategyData['TryBuyCnt'] = 0 #매수시도하고자 하는 수량!

        KospidaqStrategyList.append(KospidaqStrategyData)

    #파일에 저장
    with open(data_file_path, 'w') as outfile:
        json.dump(KospidaqStrategyList, outfile, indent=4, sort_keys=True, ensure_ascii=False)


###################################################################
###################################################################
DateData = dict()
#파일 경로입니다.
date_file_path = os.path.join(script_dir, "Kosdaqpi_Bot_Date.json")

try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(date_file_path, 'r') as json_file:
        DateData = json.load(json_file)

except Exception as e:
    logging.info("Init....")

    DateData['Date'] = "00" #오늘날짜

    #파일에 저장
    with open(date_file_path, 'w') as outfile:
        json.dump(DateData, outfile, indent=4, sort_keys=True, ensure_ascii=False)

###################################################################
###################################################################



###################################################################

#오늘 코스피 시가매매 로직이 진행되었는지 날짜 저장 관리 하는 파일
DateSiGaLogicDoneDict = dict()

#파일 경로입니다.
siga_logic_file_path = os.path.join(script_dir, "Kosdaqpi_Bot_TodaySigaLogicDoneDate.json")
try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(siga_logic_file_path, 'r') as json_file:
        DateSiGaLogicDoneDict = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    logging.info("Exception by First")

###################################################################

# 포트폴리오 매니저에서 최초 투자금액과 할당 비율 가져오기
try:
    # portfolio_config.json에서 allocation_rate 가져오기
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(script_dir, "portfolio_config.json")
    
    with open(config_file_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    allocation_rate = config_data['bots']['Kosdaqpi_Bot']['allocation_rate']
    
    # 계좌 잔고에 할당 비율을 적용하여 총 투자금액 계산
    TotalMoney = float(Balance['TotalMoney']) * allocation_rate

    logging.info(f"계좌 총액: {format(float(Balance['TotalMoney']), ',')}원")
    logging.info(f"할당 비율: {allocation_rate * 100}%")
    logging.info(f"전략에 투자하는 총 금액: {format(round(TotalMoney), ',')}")

    InvestMoney = TotalMoney
    RemainInvestMoney = TotalMoney - NowInvestMoney

    logging.info(f"현재 남은 금액! (투자금 제외): {format(round(RemainInvestMoney), ',')}")
except Exception as e:
    logging.error(f"포트폴리오 설정 가져오기 실패: {e}")
    # 기본값 설정
    TotalMoney = float(Balance['TotalMoney']) * InvestRate  # InvestRate 변수 사용
    InvestMoney = TotalMoney
    RemainInvestMoney = TotalMoney - NowInvestMoney




DivNum = len(InvestStockList)

if ENABLE_ORDER_EXECUTION == True:

    #마켓이 열렸는지 여부~!
    IsMarketOpen = KisKR.IsMarketOpen()
    
    # 현재 날짜 정보 가져오기
    current_date = time.strftime("%Y-%m-%d")
    
    # 장 상태에 따른 로그 메시지
    if IsMarketOpen == True:
        logging.info(f"날짜 {current_date} : 장이 열려있습니다.")
        telegram.send(f"{PortfolioName}({current_date})\n장이 열려있습니다.")
    else:
        logging.info(f"날짜 {current_date} : 장이 닫혀있습니다.")
        telegram.send(f"{PortfolioName}({current_date})\n장이 닫혀있습니다.")
        # 장이 닫혀있으면 더 이상 로그를 남기지 않고 종료
        sys.exit(0)

    IsLP_OK = True
    #정각 9시 5분 전에는 LP유동성 공급자가 없으니 매매를 피하고자.
    if time_info.tm_hour == 0: #9시인데
        if time_info.tm_min < 6: #6분보다 적은 값이면 --> 6분부터 LP가 활동한다고 하자!
            IsLP_OK = False
            
    #장이 열렸고 LP가 활동할때 매수!!!
    if IsMarketOpen == True and IsLP_OK == True: 


        #혹시 이 봇을 장 시작하자 마자 돌린다면 20초르 쉬어준다.
        #그 이유는 20초는 지나야 오늘의 일봉 정보를 제대로 가져오는데
        #tm_hour가 0은 9시, 1은 10시를 뜻한다. 수능 등 10시에 장 시작하는 경우르 대비!
        if time_info.tm_hour in [0,1] and time_info.tm_min in [0,1]:
            time.sleep(20.0)
            

        logging.info("Market Is Open!!!!!!!!!!!")
        #영상엔 없지만 리밸런싱이 가능할때만 내게 메시지를 보내자!



        #데이터를 조합한다.
        stock_df_list = []
        
                
        gugan_lenth = 7


        for stock_code in InvestStockList:
            df = Common.GetOhlcv("KR", stock_code,200)

            period = 14

            delta = df["close"].diff()
            up, down = delta.copy(), delta.copy()
            up[up < 0] = 0
            down[down > 0] = 0
            _gain = up.ewm(com=(period - 1), min_periods=period).mean()
            _loss = down.abs().ewm(com=(period - 1), min_periods=period).mean()
            RS = _gain / _loss

            df['RSI'] = pd.Series(100 - (100 / (1 + RS)), name="RSI")

            df['prevRSI'] = df['RSI'].shift(1)
            df['prevRSI2'] = df['RSI'].shift(2)
            
            df['high_'+str(gugan_lenth)+'_max'] = df['high'].rolling(window=gugan_lenth).max().shift(1)
            df['low_'+str(gugan_lenth)+'_min'] = df['low'].rolling(window=gugan_lenth).min().shift(1)


            df['prevVolume'] = df['volume'].shift(1)
            df['prevVolume2'] = df['volume'].shift(2)
            df['prevVolume3'] = df['volume'].shift(3)

            df['prevClose'] = df['close'].shift(1)
            df['prevOpen'] = df['open'].shift(1)

            df['prevHigh'] = df['high'].shift(1)
            df['prevHigh2'] = df['high'].shift(2)

            df['prevLow'] = df['low'].shift(1)
            df['prevLow2'] = df['low'].shift(2)

            df['Disparity20'] = df['prevClose'] / df['prevClose'].rolling(window=20).mean() * 100.0
            
            df['Disparity11'] = df['prevClose'] / df['prevClose'].rolling(window=11).mean() * 100.0


            df['ma3_before'] = df['close'].rolling(3).mean().shift(1)
            df['ma6_before'] = df['close'].rolling(6).mean().shift(1)
            df['ma19_before'] = df['close'].rolling(19).mean().shift(1)


            df['ma10_before'] = df['close'].rolling(10).mean().shift(1)

            df['ma20_before'] = df['close'].rolling(20).mean().shift(1)
            df['ma20_before2'] = df['close'].rolling(20).mean().shift(2)
            df['ma60_before'] = df['close'].rolling(60).mean().shift(1)
            df['ma60_before2'] = df['close'].rolling(60).mean().shift(2)

            df['ma120_before'] = df['close'].rolling(120).mean().shift(1)



            df['prevChangeMa'] = df['change'].shift(1).rolling(window=20).mean()
            

            df['prevChangeMa_S'] = df['change'].shift(1).rolling(window=10).mean()
            

            #10일마다 총 100일 평균모멘텀스코어
            specific_days = list()

            for i in range(1,11):
                st = i * 10
                specific_days.append(st)

            for day in specific_days:
                column_name = f'Momentum_{day}'
                df[column_name] = (df['prevClose'] > df['close'].shift(day)).astype(int)
                
            df['Average_Momentum'] = df[[f'Momentum_{day}' for day in specific_days]].sum(axis=1) / 10



            # Define the list of specific trading days to compare
            specific_days = list()

            for i in range(1,11):
                st = i * 3
                specific_days.append(st)



            # Iterate over the specific trading days and compare the current market price with the corresponding closing prices
            for day in specific_days:
                # Create a column name for each specific trading day
                column_name = f'Momentum_{day}'
                
                # Compare current market price with the closing price of the specific trading day
                df[column_name] = (df['prevClose'] > df['close'].shift(day)).astype(int)

            # Calculate the average momentum score
            df['Average_Momentum3'] = df[[f'Momentum_{day}' for day in specific_days]].sum(axis=1) / 10



            df.dropna(inplace=True) #데이터 없는건 날린다!


            data_dict = {stock_code: df}
            stock_df_list.append(data_dict)
            logging.info(f"---stock_code--- {stock_code} len {len(df)}")
            pprint.pprint(df)
            
            


            #시가매매 체크한 기록이 없는 맨 처음이라면 
            if DateSiGaLogicDoneDict.get(stock_code) == None:

                #0으로 초기화!!!!!
                DateSiGaLogicDoneDict[stock_code] = 0
                #파일에 저장
                with open(siga_logic_file_path, 'w') as outfile:
                    json.dump(DateSiGaLogicDoneDict, outfile, indent=4, sort_keys=True, ensure_ascii=False)

            #시가매매 체크한 기록이 없는 맨 처음이라면 
            if DateSiGaLogicDoneDict.get('InvestCnt') == None:
                DateSiGaLogicDoneDict['InvestCnt'] =  GetKospidaqInvestCnt(KospidaqStrategyList) #일단 투자중 개수 저장!
                #파일에 저장
                with open(siga_logic_file_path, 'w') as outfile:
                    json.dump(DateSiGaLogicDoneDict, outfile, indent=4, sort_keys=True, ensure_ascii=False)
                    
                    
            if DateSiGaLogicDoneDict.get('IsCut') == None:
                DateSiGaLogicDoneDict['IsCut'] =  False
                DateSiGaLogicDoneDict['IsCutCnt'] =  0
                #파일에 저장
                with open(siga_logic_file_path, 'w') as outfile:
                    json.dump(DateSiGaLogicDoneDict, outfile, indent=4, sort_keys=True, ensure_ascii=False)



        # Combine the OHLCV data into a single DataFrame
        combined_df = pd.concat([list(data_dict.values())[0].assign(stock_code=stock_code) for data_dict in stock_df_list for stock_code in data_dict])

        # Sort the combined DataFrame by date
        combined_df.sort_index(inplace=True)

        pprint.pprint(combined_df)
        logging.info(f"len(combined_df): {len(combined_df)}")


        date = combined_df.iloc[-1].name

        all_stocks = combined_df.loc[combined_df.index == date].groupby('stock_code')['close'].max().nlargest(DivNum)
        

        #######################################################################################################################################
        # 횡보장을 정의하기 위한 로직!!
        # https://blog.naver.com/zacra/223225906361 이 포스팅을 정독하세요!!!
        Kosdaq_Long_Data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == "233740")]
        Kosdaq_Short_Data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == "251340")]
        Kospi_Long_Data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == "122630")]
        Kospi_Short_Data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == "252670")]
        
        
        IsNoWay = False
        if  (Kospi_Long_Data['prevChangeMa_S'].values[0] > 0 and Kospi_Short_Data['prevChangeMa_S'].values[0] > 0) or (Kospi_Long_Data['prevChangeMa_S'].values[0] < 0 and Kospi_Short_Data['prevChangeMa_S'].values[0] < 0)  or (Kosdaq_Long_Data['prevChangeMa_S'].values[0] > 0 and Kosdaq_Short_Data['prevChangeMa_S'].values[0] > 0) or (Kosdaq_Long_Data['prevChangeMa_S'].values[0] < 0 and Kosdaq_Short_Data['prevChangeMa_S'].values[0] < 0) :
            IsNoWay = True
        #######################################################################################################################################
       

        #날짜가 다르다면 날이 바뀐거다
        if day_str != DateData['Date']:
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
            logging.info(f"--weekday-- {weekday} {time_info.tm_wday}")





            #가장 최근 데이터의 날짜의 요일과 봇이 실행되는 요일은 같아야 한다.
            #이게 다르다면 아직 최근 데이터의 날자가 갱신 안되었단 이야기인데 이는 9시 정각이나..(20초 딜레이가 필요) 수능등으로 장 오픈시간이 지연되었을때 다를 수 있다. 그때는 매매하면 안된다
            if weekday == time_info.tm_wday:
                
                DateSiGaLogicDoneDict['InvestCnt'] = GetKospidaqInvestCnt(KospidaqStrategyList) #일단 투자중 개수 저장!
                #파일에 저장
                with open(siga_logic_file_path, 'w') as outfile:
                    json.dump(DateSiGaLogicDoneDict, outfile, indent=4, sort_keys=True, ensure_ascii=False)
                    
                    

                DateData['Date'] = day_str #오늘 맨처음 할일 (종목 선정 및 돌파가격 설정, 상태 설정)을 끝냈으니 날짜를 넣어 다음날 다시 실행되게 한다.
                with open(date_file_path, 'w') as outfile:
                    json.dump(DateData, outfile, indent=4, sort_keys=True, ensure_ascii=False)

                #기본적으로 날이 바뀌었기 때문에 데이 조건(BUY_DAY,SELL_DAY)를 모두 초기화 한다!
                for KospidaqStrategyData in KospidaqStrategyList:
                    KospidaqStrategyData['DayStatus'] = "NONE"

                    #그리고 투자중 상태는 SELL_DAY로 바꿔준다!!
                    if KospidaqStrategyData['Status'] == "INVESTING":
                        KospidaqStrategyData['DayStatus'] = "SELL_DAY"

                        msg = KospidaqStrategyData['StockName'] + "  투자중 상태에요! 조건을 만족하면 매도로 트레이딩 종료 합니다.!!"
                        logging.info(msg)
                        #telegram.send(msg)


            
                for stock_code in  all_stocks.index:
                    stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)]

                    #해당 정보를 읽는다.
                    KospidaqStrategyData = GetKospidaqStrategyData(stock_code,KospidaqStrategyList)

                    #만약 정보가 없다면 새로 추가된 종목이니 새로 저장한다!!!
                    if KospidaqStrategyData == None:

                        KospidaqStrategyData = dict()
                        KospidaqStrategyData['StockCode'] = stock_code #대상 종목 코드
                        KospidaqStrategyData['StockName'] = KisKR.GetStockName(stock_code) #종목 이름
                        KospidaqStrategyData['Status'] = "REST" #상태 READY(돌파를체크해야하는 준비상태), INVESTING(돌파해서 투자중), REST(조건불만족,투자안함,돌파체크안함) 
                        KospidaqStrategyData['DayStatus'] = "NONE" #오늘 매수하는 날인지 매도하는 날인지 체크
                        KospidaqStrategyData['TargetPrice'] = 0 #돌파가격
                        KospidaqStrategyData['TryBuyCnt'] = 0 #매수시도하고자 하는 수량!

                        KospidaqStrategyList.append(KospidaqStrategyData)

                    #코스닥 전략...돌파 매매..
                    if stock_code in ["233740","251340"]:
                        
                            
                        PrevClosePrice = stock_data['prevClose'].values[0] 
                        
                        DolpaRate = 0.4

                        # KODEX 코스닥150선물인버스
                        if stock_code == "251340":

                            DolpaRate = 0.4

                        #KODEX 코스닥150레버리지
                        else: 

                            if PrevClosePrice > stock_data['ma60_before'].values[0]:
                                DolpaRate = 0.3
                            else:
                                DolpaRate = 0.4


                        ##########################################################################
                        #갭 상승 하락을 이용한 돌파값 조절!
                        # https://blog.naver.com/zacra/223277173514 이 포스팅을 체크!!!!
                        ##########################################################################
                        Gap = ((abs(stock_data['open'].values[0] - PrevClosePrice) / PrevClosePrice)) * 100.0

                        GapSt = (Gap*0.025)

                        if GapSt > 1.0:
                            GapSt = 1.0
                        if GapSt < 0:
                            GapSt = 0.1

                        if PrevClosePrice > stock_data['open'].values[0] and Gap >= 3.0:
                            DolpaRate *= (1.0 + GapSt)

                        if PrevClosePrice < stock_data['open'].values[0] and Gap >= 3.0:
                            DolpaRate *= (1.0 - GapSt)

            
                        DolPaPrice = stock_data['open'].values[0] + ((stock_data['prevHigh'].values[0] - stock_data['prevLow'].values[0]) * DolpaRate)


                        #어제 무슨 이유에서건 매수 실패했다면 일단 REST로!
                        if KospidaqStrategyData['Status'] == "INVESTING_TRY":
                            KospidaqStrategyData['Status'] = "REST"
                            KospidaqStrategyData['DayStatus'] = "NONE"

                        #어제 무슨 이유에서건 매도 실패했다면 투자중 상태로 변경!
                        if KospidaqStrategyData['Status'] == "SELL_DONE_CHECK":
                            KospidaqStrategyData['Status'] = "INVESTING"
                            KospidaqStrategyData['DayStatus'] = "SELL_DAY"



                        
                        if KospidaqStrategyData['Status'] != "INVESTING": #투자 상태가 아니라면 조건을 체크하여 매수시도할 수 있다!
                            
                            IsBuyReady = True #일단 무조건 True 만약 필터하고자 하면 False로 하고 조건만족시 True로 바꾸면 된다.
                            

                            KospidaqStrategyData['StockCode'] = stock_code #대상 종목 코드
                            KospidaqStrategyData['StockName'] = KisKR.GetStockName(stock_code)


                            if stock_code == "251340":
                                if stock_data['prevClose'].values[0] <= stock_data['ma20_before'].values[0]:
                                    IsBuyReady = False 
            

                            else: #레버리지

                                if stock_data['prevLow'].values[0] > stock_data['open'].values[0] and stock_data['prevClose'].values[0] < stock_data['ma10_before'].values[0]:
                                    IsBuyReady = False 
                                    
                            # 추가 개선 로직 https://blog.naver.com/zacra/223326173552 이 포스팅 참고!!!!
                            IsJung = False    
                            if stock_data['ma10_before'].values[0] > stock_data['ma20_before'].values[0] > stock_data['ma60_before'].values[0] > stock_data['ma120_before'].values[0]:
                                IsJung = True
                                
                            if IsJung == False:
                                
                                        
                                high_price = stock_data['high_'+str(gugan_lenth)+'_max'].values[0] 
                                low_price =  stock_data['low_'+str(gugan_lenth)+'_min'].values[0] 
                                
                                Gap = (high_price - low_price) / 4
                                
                                
                                MaximunPrice = low_price + Gap * 3.0
                                
                                
                                if stock_data['open'].values[0] > MaximunPrice:
                                    IsBuyReady = False
            

                            #기본 필터 통과!! 돌파가격을 정하고 READY상태로 변경
                            if IsBuyReady == True:
                                logging.info("IS Ready!!!")
                                KospidaqStrategyData['TargetPrice'] = DolPaPrice #돌파가격

                                KospidaqStrategyData['Status'] = "READY"
                                KospidaqStrategyData['DayStatus'] = "BUY_DAY"


                                msg = KospidaqStrategyData['StockName'] + " 돌파하면 매수합니다!!!"
                                logging.info(msg)
                                #telegram.send(msg)

                            #기본 필터 통과 실패 매수 안함! 
                            else:
                                logging.info("No Ready")
                
                                KospidaqStrategyData['Status'] = "REST"
                                KospidaqStrategyData['DayStatus'] = "NONE"

                                msg = KospidaqStrategyData['StockName'] + "  조건을 불만족하여 오늘 돌파매수는 쉽니다!!!"
                                logging.info(msg)
                                #telegram.send(msg)
                            
                    #코스피 전략.... 시가 매매
                    else:
                        

                        #어제 무슨 이유에서건 매수 실패했다면 일단 REST로!
                        if KospidaqStrategyData['Status'] == "INVESTING_TRY":
                            KospidaqStrategyData['Status'] = "REST"
                            KospidaqStrategyData['DayStatus'] = "NONE"

                        #어제 무슨 이유에서건 매도 실패했다면 투자중 상태로 변경!
                        if KospidaqStrategyData['Status'] == "SELL_DONE_CHECK":
                            KospidaqStrategyData['Status'] = "INVESTING"
                            KospidaqStrategyData['DayStatus'] = "SELL_DAY"

                        

                        if KospidaqStrategyData['Status'] != "INVESTING": #투자 상태가 아니라면 조건을 체크하여 매수시도할 수 있다!
                            KospidaqStrategyData['StockCode'] = stock_code #대상 종목 코드
                            KospidaqStrategyData['StockName'] = KisKR.GetStockName(stock_code)

                            KospidaqStrategyData['Status'] = "READY"
                            KospidaqStrategyData['DayStatus'] = "BUY_DAY"

                            msg = KospidaqStrategyData['StockName'] + " 조건을 만족했다면 매수합니다!!!"
                            logging.info(msg)
                            #telegram.send(msg)




                    #파일에 저장
                    with open(data_file_path, 'w') as outfile:
                        json.dump(KospidaqStrategyList, outfile, indent=4, sort_keys=True, ensure_ascii=False)
            else:

                if time_info.tm_min == 0 or time_info.tm_min == 30:
                    msg = "요일이 다르게 나왔어요! 좀 더 기다려봐요!"
                    logging.info(msg)
                    try:
                        telegram.send(msg)
                    except Exception as e:
                        logging.error(f"텔레그램 전송 실패: {e}")
                    

        if day_str == DateData['Date']: #오늘 할일을 한다!

            ### 매도 파트 ###
            for KospidaqStrategyData in KospidaqStrategyList:
                pprint.pprint(KospidaqStrategyData)

                stock_code = KospidaqStrategyData['StockCode']
                
                stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)]

                if len(stock_data) == 1:
                    
                    NowOpenPrice = stock_data['open'].values[0]
                    PrevOpenPrice = stock_data['prevOpen'].values[0] 
                    PrevClosePrice = stock_data['prevClose'].values[0] 


                    #현재가!
                    CurrentPrice = KisKR.GetCurrentPrice(stock_code)        
                    


                    IsSellAlready = False   
                    #해당 ETF가 매도하는 날 상태이다!
                    if KospidaqStrategyData['DayStatus'] == "SELL_DAY":

                        #제대로 매도되었는지 확인!
                        if KospidaqStrategyData['Status'] == "SELL_DONE_CHECK":
                            stock_amt = 0 #수량

                            
                            #내가 보유한 주식 리스트에서 매수된 잔고 정보를 가져온다
                            for my_stock in MyStockList:
                                if my_stock['StockCode'] == stock_code:
                                    stock_amt = int(my_stock['StockAmt'])
                                    break

                            logging.info(f"stock_amt: {stock_amt}")

                            if stock_amt == 0:
                                KospidaqStrategyData['Status'] = "REST" 
                                KospidaqStrategyData['DayStatus'] = "NONE"

                                msg = KospidaqStrategyData['StockName']  + " 모두 매도된 것이 확인 되었습니다!"
                                logging.info(msg)
                                telegram.send(msg)
                                                
                                #파일에 저장
                                with open(data_file_path, 'w') as outfile:
                                    json.dump(KospidaqStrategyList, outfile, indent=4, sort_keys=True, ensure_ascii=False)

                            else:

                                KisKR.CancelAllOrders(KospidaqStrategyData['StockCode'],"ALL")

                                # 시장가 매도로 변경
                                data = KisKR.MakeSellMarketOrder(KospidaqStrategyData['StockCode'],stock_amt)
                                # 분할매도로 변경 (1분할, 1분 간격)
                                #data = MakeSplitSellOrder(KospidaqStrategyData['StockCode'], stock_amt, split_count=1, time_term=1)

                                # 매도 거래 기록 저장 (재시도 시에도)
                                try:
                                    save_sell_history(
                                        stock_code=stock_code,
                                        stock_name=stock_name,
                                        quantity=stock_amt,
                                        unit_price=CurrentPrice,
                                        amount=stock_amt * CurrentPrice,
                                        fee=0
                                    )
                                except Exception as e:
                                    logging.error(f"매도 재시도 거래 기록 저장 실패: {e}")

                                # 매도 시 누적 수익 업데이트 (재시도 시에도)
                                update_cumulative_profit_on_sale(stock_code, stock_amt, CurrentPrice, stock_avg_price)
                                
                                msg = KospidaqStrategyData['StockName']  + " 모두 매도한 줄 알았는데 실패했나봐요 다시 시도합니다.\n" + str(data)
                                logging.info(msg)
                                telegram.send(msg)


                        #만약 투자중이라면 조건을 체크!
                        if KospidaqStrategyData['Status'] == "INVESTING": #투자중 상태


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
                                
                            #코스닥 전략...돌파 매매..
                            if stock_code in ["233740","251340"]:
                                
                                        
                                if stock_amt > 0:
                                    

                                    CutRate = 0.4

                                    if stock_code == "251340":
                                        CutRate = 0.4

                                    else:

                                        if PrevClosePrice > stock_data['ma60_before'].values[0]:
                                            CutRate = 0.4
                                        else:
                                            CutRate = 0.3


                                    
                                    CutPrice = stock_data['open'].values[0] - ((stock_data['prevHigh'].values[0] - stock_data['prevLow'].values[0]) * CutRate)
                                    
                                    

                                    CurrentPrice = KisKR.GetCurrentPrice(stock_code)  

                                    if CurrentPrice <= CutPrice or stock_data['low'].values[0] <= CutPrice :
                                        
                                        
                                        
                                        # 시장가 매도로 변경
                                        order_result = KisKR.MakeSellMarketOrder(stock_code,stock_amt)
                                        pprint.pprint(order_result)
                                         # 분할매도로 변경 (1분할, 1분 간격)
                                        #pprint.pprint(MakeSplitSellOrder(stock_code, stock_amt, split_count=1, time_term=1))
                                        
                                        # 매도 거래 기록 저장
                                        try:
                                            save_sell_history(
                                                stock_code=stock_code,
                                                stock_name=stock_name,
                                                quantity=stock_amt,
                                                unit_price=CurrentPrice,
                                                amount=stock_amt * CurrentPrice,
                                                fee=0
                                            )
                                        except Exception as e:
                                            logging.error(f"매도 거래 기록 저장 실패: {e}")
                                        
                                        KospidaqStrategyData['Status'] = "SELL_DONE_CHECK" 

                                        # 매도 시 누적 수익 업데이트
                                        update_cumulative_profit_on_sale(stock_code, stock_amt, CurrentPrice, stock_avg_price)
                                        
                                        msg = KospidaqStrategyData['StockName']  + " 모두 시장가 매도!!! " + str(stock_revenue_money) + " 수익 확정!! 수익률:" + str(stock_revenue_rate) + "%"
                                        logging.info(msg)
                                        telegram.send(msg)

                                        if stock_revenue_rate < 0:
            
                                            DateSiGaLogicDoneDict['IsCut'] = True
                                            DateSiGaLogicDoneDict['IsCutCnt'] += 1
                                            #파일에 저장
                                            with open(siga_logic_file_path, 'w') as outfile:
                                                json.dump(DateSiGaLogicDoneDict, outfile, indent=4, sort_keys=True, ensure_ascii=False)


                                        else:
                
                                            DateSiGaLogicDoneDict['IsCut'] =  False
                                            DateSiGaLogicDoneDict['IsCutCnt'] -= 1
                                            if DateSiGaLogicDoneDict['IsCutCnt'] < 0:
                                                DateSiGaLogicDoneDict['IsCutCnt'] = 0

                                            #파일에 저장
                                            with open(siga_logic_file_path, 'w') as outfile:
                                                json.dump(DateSiGaLogicDoneDict, outfile, indent=4, sort_keys=True, ensure_ascii=False)



                                        IsSellAlready = True
                                        
                                        


                                    
                                else:
                                    KospidaqStrategyData['Status'] = "REST" 
                                    KospidaqStrategyData['DayStatus'] = "NONE"


                                    msg = KospidaqStrategyData['StockName']  + " 매수했다고 기록되었는데 물량이 없네요? 암튼 초기화 했어요 다음날 다시 전략 시작합니다!"
                                    logging.info(msg)
                                    telegram.send(msg)
                            #코스피
                            else:
                                
                                if stock_amt > 0:
                                    
                                    IsSellGo = False

                                    if stock_code == "252670":
                                        
                                        if stock_data['Disparity11'].values[0] > 105:
                                            #
                                            if  PrevClosePrice < stock_data['ma3_before'].values[0]: 
                                                IsSellGo = True

                                        else:
                                            #
                                            if PrevClosePrice < stock_data['ma6_before'].values[0] and PrevClosePrice < stock_data['ma19_before'].values[0] : 
                                                IsSellGo = True

                                    else:
                                        logging.info("")
                                        
                            
                                        total_volume = (stock_data['prevVolume'].values[0]+ stock_data['prevVolume2'].values[0] +stock_data['prevVolume3'].values[0]) / 3.0

                                        Disparity = stock_data['Disparity20'].values[0] 

                                        if (stock_data['prevLow2'].values[0] < stock_data['prevLow'].values[0] or stock_data['prevVolume'].values[0] < total_volume) and (Disparity < 98 or Disparity > 105):
                                            logging.info("hold..")
                                        else:
                                            IsSellGo = True

                        
                                    if IsSellGo == True:
                                        
                                        
                                        DateSiGaLogicDoneDict['InvestCnt'] -= 1 #코스피 시가 매도 걸렸을 때만 투자중 카운트를 감소!
                                        #파일에 저장
                                        with open(siga_logic_file_path, 'w') as outfile:
                                            json.dump(DateSiGaLogicDoneDict, outfile, indent=4, sort_keys=True, ensure_ascii=False)
                                            
                    
                                        # 시장가 매도로 변경
                                        order_result = KisKR.MakeSellMarketOrder(stock_code,stock_amt)
                                        pprint.pprint(order_result)
                                        # 분할매도로 변경 (1분할, 1분 간격)
                                        #pprint.pprint(MakeSplitSellOrder(stock_code, stock_amt, split_count=1, time_term=1))
                                        
                                        # 매도 거래 기록 저장
                                        try:
                                            save_sell_history(
                                                stock_code=stock_code,
                                                stock_name=stock_name,
                                                quantity=stock_amt,
                                                unit_price=CurrentPrice,
                                                amount=stock_amt * CurrentPrice,
                                                fee=0
                                            )
                                        except Exception as e:
                                            logging.error(f"매도 거래 기록 저장 실패: {e}")
                                        
                                        KospidaqStrategyData['Status'] = "SELL_DONE_CHECK" 

                                        # 매도 시 누적 수익 업데이트
                                        update_cumulative_profit_on_sale(stock_code, stock_amt, CurrentPrice, stock_avg_price)
                                        
                                        msg = KospidaqStrategyData['StockName']  + " 분할매도 시작!!! " + str(stock_revenue_money) + " 수익 확정!! 수익률:" + str(stock_revenue_rate) + "%"
                                        logging.info(msg)
                                        telegram.send(msg)

                                        IsSellAlready = True
                                        


                                        ############## 팔렸다면 남은 금액 갱신 #######################
                                        time.sleep(5.0)
                                        MyStockList = KisKR.GetMyStockList()
                                        NowInvestMoney = 0

                                        for stock_code in InvestStockList:
                                            stock_name = ""
                                            stock_amt = 0 #수량
                                            stock_avg_price = 0 #평단

                                            #내가 보유한 주식 리스트에서 매수된 잔고 정보를 가져온다
                                            for my_stock in MyStockList:
                                                if my_stock['StockCode'] == stock_code:
                                                    stock_name = my_stock['StockName']
                                                    stock_amt = int(my_stock['StockAmt'])
                                                    stock_avg_price = float(my_stock['StockAvgPrice'])

                                                    
                                                    NowInvestMoney += (stock_amt*stock_avg_price)
                                                    break

                                        RemainInvestMoney = TotalMoney - NowInvestMoney
                                        ###########################################################

                                    
                                else:
                                    KospidaqStrategyData['Status'] = "REST" 
                                    KospidaqStrategyData['DayStatus'] = "NONE"


                                    msg = KospidaqStrategyData['StockName']  + " 매수했다고 기록되었는데 물량이 없네요? 암튼 초기화 했어요 다음날 다시 전략 시작합니다!"
                                    logging.info(msg)
                                    telegram.send(msg)


            ### 매수 파트 ###
            for KospidaqStrategyData in KospidaqStrategyList:
                pprint.pprint(KospidaqStrategyData)

                stock_code = KospidaqStrategyData['StockCode']
                
                stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)]

                if len(stock_data) == 1:
                    
                    NowOpenPrice = stock_data['open'].values[0]
                    PrevOpenPrice = stock_data['prevOpen'].values[0] 
                    PrevClosePrice = stock_data['prevClose'].values[0] 


                    #현재가!
                    CurrentPrice = KisKR.GetCurrentPrice(stock_code)        
                    
                
                    #해당 ETF가 매수하는 날 상태이다!
                    if KospidaqStrategyData['DayStatus'] == "BUY_DAY":              
                        
                        #매수 시도가 진행 되었다. 매수 완료 되었는지 체크
                        if KospidaqStrategyData['Status'] == "INVESTING_TRY":
                            
                            MyStockList = KisKR.GetMyStockList()

                            stock_amt = 0 #수량

                            
                            #내가 보유한 주식 리스트에서 매수된 잔고 정보를 가져온다
                            for my_stock in MyStockList:
                                if my_stock['StockCode'] == KospidaqStrategyData['StockCode']:
                                    stock_amt = int(my_stock['StockAmt'])
                                    break
                                
                            #실제로 1주라도 매수가 되었다면 투자중 상태로 변경!!!
                            if stock_amt > 0:
                                KospidaqStrategyData['Status'] = "INVESTING"
                                KospidaqStrategyData['DayStatus'] = "NONE"
                                
                                msg = KospidaqStrategyData['StockName'] + " 투자중이에요!!"
                                logging.info(msg)
                                telegram.send(msg)

                            #아니라면 알림으로 알려준다!!
                            else:
                        
                                msg = KospidaqStrategyData['StockName'] + "  조건을 만족하여 매수 시도했는데 아직 1주도 매수되지 않았어요! 감산해서 매수시도 합니다! "
                                logging.info(msg)
                                telegram.send(msg)

                                if KospidaqStrategyData.get('TryBuyCnt') == None:
                                    KospidaqStrategyData['TryBuyCnt'] = 1


                                KospidaqStrategyData['TryBuyCnt'] = int(KospidaqStrategyData['TryBuyCnt'] * 0.7)

                                if KospidaqStrategyData['TryBuyCnt'] > 1:
                                    # 시장가 매수로 변경
                                    returnData = KisKR.MakeBuyMarketOrder(KospidaqStrategyData['StockCode'],KospidaqStrategyData['TryBuyCnt'],True) #30%감소된 수량으로 매수 시도!!
                                    # 분할매수로 변경 (1분할, 1분 간격)
                                    #returnData = MakeSplitBuyOrder(KospidaqStrategyData['StockCode'], KospidaqStrategyData['TryBuyCnt'], split_count=1, time_term=1)
                                    
                                    # 매수 재시도 거래 기록 저장
                                    try:
                                        save_buy_history(
                                            stock_code=KospidaqStrategyData['StockCode'],
                                            stock_name=KospidaqStrategyData['StockName'],
                                            quantity=KospidaqStrategyData['TryBuyCnt'],
                                            unit_price=CurrentPrice,
                                            amount=KospidaqStrategyData['TryBuyCnt'] * CurrentPrice,
                                            fee=0
                                        )
                                    except Exception as e:
                                        logging.error(f"매수 재시도 거래 기록 저장 실패: {e}")

                                    msg = KospidaqStrategyData['StockName'] + "  시장가매수 시도!!! " + str(returnData)
                                    logging.info(msg)
                                    telegram.send(msg)

                                else:

                                    KospidaqStrategyData['Status'] = "REST"
                                    KospidaqStrategyData['DayStatus'] = "NONE"
                                    

                                    msg = KospidaqStrategyData['StockName'] + "  매수 실패!!! "
                                    logging.info(msg)
                                    telegram.send(msg)


                                
                            
                            
                        #상태를 체크해서 READY라면 돌파시 매수한다!
                        if KospidaqStrategyData['Status'] == "READY" and DateSiGaLogicDoneDict['InvestCnt'] < 2:
                            
                            
                            
                            logging.info("돌파 체크중...")
                            
                            
                            #코스닥 전략...돌파 매매..
                            if stock_code in ["233740","251340"]:
                                

                        
                                DolpaRate = 0.4

                                # KODEX 코스닥150선물인버스
                                if stock_code == "251340":

                                    DolpaRate = 0.4

                                #KODEX 코스닥150레버리지
                                else: 

                                    if PrevClosePrice > stock_data['ma60_before'].values[0]:
                                        DolpaRate = 0.3
                                    else:
                                        DolpaRate = 0.4


                    
                                ##########################################################################
                                #갭 상승 하락을 이용한 돌파값 조절!
                                # https://blog.naver.com/zacra/223277173514 이 포스팅을 체크!!!!
                                ##########################################################################
                                Gap = ((abs(stock_data['open'].values[0] - PrevClosePrice) / PrevClosePrice)) * 100.0

                                GapSt = (Gap*0.025)

                                if GapSt > 1.0:
                                    GapSt = 1.0
                                if GapSt < 0:
                                    GapSt = 0.1

                                if PrevClosePrice > stock_data['open'].values[0] and Gap >= 3.0:
                                    DolpaRate *= (1.0 + GapSt)

                                if PrevClosePrice < stock_data['open'].values[0] and Gap >= 3.0:
                                    DolpaRate *= (1.0 - GapSt)


                    
                                DolPaPrice = stock_data['open'].values[0] + ((stock_data['prevHigh'].values[0] - stock_data['prevLow'].values[0]) * DolpaRate)

                                KospidaqStrategyData['TargetPrice'] = DolPaPrice


                                #돌파가격보다 현재가가 높다? 돌파한거다 매수한다!
                                if CurrentPrice >= KospidaqStrategyData['TargetPrice'] or stock_data['high'].values[0] >= KospidaqStrategyData['TargetPrice']  :

                                    Rate = 1.0
                                    if len(Kosdaq_Long_Data) == 1 and len(Kosdaq_Short_Data) == 1:
                                    
                                        IsLongStrong = False
                                        
                                        if Kosdaq_Long_Data['Average_Momentum'].values[0] > Kosdaq_Short_Data['Average_Momentum'].values[0]:
                                            IsLongStrong = True
                                            
                                        IsLongStrong2 = False
                                        
                                        if Kosdaq_Long_Data['prevChangeMa'].values[0] > Kosdaq_Short_Data['prevChangeMa'].values[0]:
                                            IsLongStrong2 = True
                                            
                                            
                                        if IsLongStrong == True and IsLongStrong2 == True:
                                            
                                            if stock_code == "233740":
                                                Rate = 1.3
                                            else:
                                                Rate = 0.7
                                                
                                        elif IsLongStrong == False and IsLongStrong2 == False:
                                                
                                            if stock_code == "233740":
                                                Rate = 0.7
                                            else:
                                                Rate = 1.3
                                                

                                    #############################################################
                                    #시스템 손절(?) 관련
                                    # https://blog.naver.com/zacra/223225906361 이 포스팅 체크!!!
                                    #############################################################
                                                
                                    AdjustRate = 1.0

                                    if DateSiGaLogicDoneDict['IsCut'] == True and DateSiGaLogicDoneDict['IsCutCnt'] >= 2:
                                        
                                        if stock_data['prevOpen'].values[0] > stock_data['prevClose'].values[0] and stock_data['prevHigh2'].values[0] > stock_data['prevHigh'].values[0]:

                                            AdjustRate = stock_data['Average_Momentum3'].values[0] 

                                            if DateSiGaLogicDoneDict['IsCutCnt'] >= 4:
                                                AdjustRate = stock_data['Average_Momentum3'].values[0] * 0.5


                                        
                            
                                    InvestMoneyCell = 0

                                    if IsNoWay == True:
                                        
                                        InvestMoneyCell = InvestMoney * 0.25 * Rate * AdjustRate
                                        

                                    else:                                         
                                    
                                        InvestMoneyCell = InvestMoney * 0.5 * Rate * AdjustRate
                                        
                                        #if DateSiGaLogicDoneDict['InvestCnt']  >= 1:
                                        #    InvestMoneyCell = RemainInvestMoney * Rate * AdjustRate

                                    
                                    if Rate > 0 and AdjustRate > 0:
                                        
                                        #할당된 투자금이 남은돈보다 많다면 남은 돈만큼으로 세팅!
                                        if RemainInvestMoney < InvestMoneyCell:
                                            InvestMoneyCell = RemainInvestMoney



                                            
                                        BuyAmt = int(InvestMoneyCell / CurrentPrice)
                                        

                                        #최소 2주는 살 수 있도록!
                                        if BuyAmt < 2:
                                            BuyAmt = 2

                                        KospidaqStrategyData['TryBuyCnt'] = BuyAmt #매수할 수량을..저장!

                                        ######## 시장가 지정가 나눠서 고고 ##########    
                                        #SliceAmt = int(BuyAmt / 2)

                                        #절반은 시장가로 바로고!
                                        #KisKR.MakeBuyMarketOrder(KospidaqStrategyData['StockCode'],SliceAmt,True) 
                                        
                                        #절반은 돌파가격 지정가로!
                                        #KisKR.MakeBuyLimitOrder(KospidaqStrategyData['StockCode'],SliceAmt,KospidaqStrategyData['TargetPrice'])

                                        
                                        ######## 시장가 1번에 고고 ##########
                                        #시장가로 바로고!
                                        order_result = KisKR.MakeBuyMarketOrder(KospidaqStrategyData['StockCode'],BuyAmt,True) 
                                        
                                        # 매수 거래 기록 저장
                                        try:
                                            save_buy_history(
                                                stock_code=KospidaqStrategyData['StockCode'],
                                                stock_name=KospidaqStrategyData['StockName'],
                                                quantity=BuyAmt,
                                                unit_price=CurrentPrice,
                                                amount=BuyAmt * CurrentPrice,
                                                fee=0
                                            )
                                        except Exception as e:
                                            logging.error(f"매수 거래 기록 저장 실패: {e}")
                                    
                                    
                                        DateSiGaLogicDoneDict['InvestCnt'] += 1
                                        #파일에 저장
                                        with open(siga_logic_file_path, 'w') as outfile:
                                            json.dump(DateSiGaLogicDoneDict, outfile, indent=4, sort_keys=True, ensure_ascii=False)
                                            
                                        RemainInvestMoney -= InvestMoneyCell
                                        
                                        KospidaqStrategyData['Status'] = "INVESTING_TRY"

                            


                                        msg = KospidaqStrategyData['StockName'] + "  조건을 만족하여 매수!!! 투자 시작!! "
                                        logging.info(msg)
                                        telegram.send(msg)
                                    else:


                                        msg = KospidaqStrategyData['StockName'] + "  돌파했지만 추세가 안좋아 매수 안함! "
                                        logging.info(msg)
                                        telegram.send(msg)
                    
                                else:
                                    logging.info("아직 돌파 안함..")
                                
                                
                            #코스피 전략...시가 매매
                            else:
                                logging.info("")
                                
                                                    
                                                    
                                #체크 날짜가 다르다면 맨 처음이거나 날이 바뀐것이다!!
                                if DateSiGaLogicDoneDict[stock_code] != day_n:
                                            
                                    IsBuyGo = False
                                    if stock_code == "252670":

                                        #이거변경
                                        if PrevClosePrice > stock_data['ma3_before'].values[0]  and PrevClosePrice > stock_data['ma6_before'].values[0]  and PrevClosePrice > stock_data['ma19_before'].values[0] and stock_data['prevRSI'].values[0] < 70 and stock_data['prevRSI2'].values[0] < stock_data['prevRSI'].values[0]:
                                            if (stock_data['prevVolume2'].values[0] < stock_data['prevVolume'].values[0]) and (stock_data['prevLow2'].values[0] < stock_data['prevLow'].values[0]) and PrevClosePrice > stock_data['ma60_before'].values[0] and stock_data['ma60_before2'].values[0] < stock_data['ma60_before'].values[0]  and stock_data['ma3_before'].values[0]  > stock_data['ma6_before'].values[0]  > stock_data['ma19_before'].values[0]  :
                                                IsBuyGo = True

                                    else:

                                        Disparity = stock_data['Disparity20'].values[0] 
                                        
                                        if (stock_data['prevLow2'].values[0] < stock_data['prevLow'].values[0]) and (Disparity < 98 or Disparity > 106) and stock_data['prevRSI'].values[0] < 80 :
                                            IsBuyGo = True
                        
                                        
                                    if IsBuyGo == True:
                                        
                        
                        
                                        Rate = 1.0
                                        
                                        

                                        InvestMoneyCell = 0


                                        if IsNoWay == True:
                                            
                                            InvestMoneyCell = InvestMoney * 0.25 * Rate

                                        else:
                                            

                                            InvestMoneyCell = InvestMoney * 0.5 * Rate

                                            #if DateSiGaLogicDoneDict['InvestCnt']  >= 1:
                                            #    InvestMoneyCell = RemainInvestMoney * Rate * AdjustRate


                                        #할당된 투자금이 남은돈보다 많다면 남은 돈만큼으로 세팅!
                                        if RemainInvestMoney < InvestMoneyCell:
                                            InvestMoneyCell = RemainInvestMoney

                                            
                                        BuyAmt = int(InvestMoneyCell / CurrentPrice)
                                        
                                        

                                        #최소 2주는 살 수 있도록!
                                        if BuyAmt < 2:
                                            BuyAmt = 2

                                        KospidaqStrategyData['TryBuyCnt'] = BuyAmt #매수할 수량을..저장!
                                        ######## 분할매수로 변경 ##########    
                                        #SliceAmt = int(BuyAmt / 2)

                                        #절반은 시장가로 바로고!
                                        #KisKR.MakeBuyMarketOrder(KospidaqStrategyData['StockCode'],SliceAmt,True) 
                                        
                                        #절반은 돌파가격 지정가로!
                                        #KisKR.MakeBuyLimitOrder(KospidaqStrategyData['StockCode'],SliceAmt,CurrentPrice)

                                        
                                        ######## 시장가 매수로 변경 ##########
                                        #시장가로 바로고!
                                        order_result = KisKR.MakeBuyMarketOrder(KospidaqStrategyData['StockCode'],BuyAmt,True)
                                        
                                        # 매수 거래 기록 저장
                                        try:
                                            save_buy_history(
                                                stock_code=KospidaqStrategyData['StockCode'],
                                                stock_name=KospidaqStrategyData['StockName'],
                                                quantity=BuyAmt,
                                                unit_price=CurrentPrice,
                                                amount=BuyAmt * CurrentPrice,
                                                fee=0
                                            )
                                        except Exception as e:
                                            logging.error(f"매수 거래 기록 저장 실패: {e}")

                                        ######## 분할매수로 변경 ##########
                                        #분할매수로 실행 (1분할, 1분 간격)
                                        #MakeSplitBuyOrder(KospidaqStrategyData['StockCode'], BuyAmt, split_count=1, time_term=1)  
                                        
                                            
                                        DateSiGaLogicDoneDict['InvestCnt'] += 1
                                        #파일에 저장
                                        with open(siga_logic_file_path, 'w') as outfile:
                                            json.dump(DateSiGaLogicDoneDict, outfile, indent=4, sort_keys=True, ensure_ascii=False)
                                            
                                        
                                        
                                        RemainInvestMoney -= InvestMoneyCell
                                        
                                        KospidaqStrategyData['Status'] = "INVESTING_TRY" 
                            


                                        msg = KospidaqStrategyData['StockName'] + "  조건을 만족하여 매수!!! 투자 시작!! "
                                        logging.info(msg)
                                        telegram.send(msg)



                                    msg = KospidaqStrategyData['StockName'] + " 오늘 매수여부 체크 완료!"
                                    logging.info(msg)
                                    #telegram.send(msg)


                                    #시가 매수 로직 안으로 들어왔다면 날자를 바꿔준다!!
                                    DateSiGaLogicDoneDict[stock_code] = day_n
                                    #파일에 저장
                                    with open(siga_logic_file_path, 'w') as outfile:
                                        json.dump(DateSiGaLogicDoneDict, outfile, indent=4, sort_keys=True, ensure_ascii=False)

            #파일에 저장
            with open(data_file_path, 'w') as outfile:
                json.dump(KospidaqStrategyList, outfile, indent=4, sort_keys=True, ensure_ascii=False)
    else:
        logging.info("Market Is Close!!!!!!!!!!!")


    pprint.pprint(DateData)
    pprint.pprint(KospidaqStrategyList)


else:
    logging.info("코드 맨 첫 부분에 ENABLE_ORDER_EXECUTION 값을 True로 변경해야 매수매도가 진행됩니다!")

# 종목 상태 요약 메시지 생성 함수
def create_status_summary_message(KospidaqStrategyList, current_date):
    """모든 종목의 상태를 요약한 텔레그램 메시지를 생성합니다."""
    status_messages = []
    
    for strategy_data in KospidaqStrategyList:
        stock_name = strategy_data['StockName']
        stock_code = strategy_data['StockCode']
        status = strategy_data['Status']
        
        # 상태 설명 매핑
        status_descriptions = {
            "READY": "돌파를 체크해야 하는 준비상태",
            "INVESTING": "돌파해서 투자중",
            "INVESTING_TRY": "매수 주문 들어감",
            "SELL_DONE_CHECK": "매도 완료 체크",
            "REST": "조건불만족, 투자안함, 돌파체크안함"
        }
        
        status_desc = status_descriptions.get(status, "알 수 없는 상태")
        status_messages.append(f"{stock_name}:{status}\n({status_desc})")
    
    # 전체 메시지 조합
    summary_message = f"{PortfolioName}({current_date})\n\n종목별 상태:\n" + "\n".join(status_messages)
    
    return summary_message

# 수익 계산 및 업데이트
def calculate_and_update_profit():
    """현재 수익을 계산하고 포트폴리오 매니저에 업데이트합니다."""
    try:
        # 현재 보유 주식 정보 가져오기
        MyStockList = KisKR.GetMyStockList()
        
        # 장이 닫혀있거나 데이터가 없는 경우 처리
        if not MyStockList:
            logging.warning("보유 주식 정보를 가져올 수 없습니다. 장이 닫혀있을 수 있습니다.")
            # 기존 수익 정보를 유지하거나 기본값 반환
            return 0, 0, 0
        
        total_profit = 0
        total_investment = 0
        processed_stocks = 0
        
        for stock in MyStockList:
            if stock['StockCode'] in InvestStockList:  # 투자 대상 종목만 계산
                try:
                    stock_profit = float(stock['StockRevenueMoney'])
                    stock_investment = float(stock['StockNowMoney'])
                    
                    total_profit += stock_profit
                    total_investment += stock_investment
                    processed_stocks += 1
                    
                    logging.info(f"종목 처리: {stock['StockName']} - 수익: {stock_profit}, 투자금: {stock_investment}")
                except (ValueError, KeyError) as e:
                    logging.error(f"주식 데이터 처리 중 오류: {e}")
                    continue
        
        # 처리된 종목이 없는 경우
        if processed_stocks == 0:
            logging.warning("처리할 수 있는 투자 종목이 없습니다.")
            return 0, 0, 0
        
        # 초기 투자금액 가져오기
        initial_investment = portfolio_manager.get_initial_investment() * InvestRate
        
        # 수익률 계산
        profit_rate = (total_profit / initial_investment * 100) if initial_investment > 0 else 0
        
        # 포트폴리오 매니저에 업데이트
        portfolio_manager.update_bot_profit("Kosdaqpi_Bot", total_profit, profit_rate)
        
        # 로그 출력
        logging.info("=== Kosdaqpi_Bot 수익 현황 ===")
        logging.info(f"총 투자금액: {initial_investment:,.0f}원")
        logging.info(f"총 평가금액: {total_investment:,.0f}원")
        logging.info(f"총 수익금: {total_profit:,.0f}원")
        logging.info(f"수익률: {profit_rate:.2f}%")
        logging.info(f"처리된 종목 수: {processed_stocks}개")
        
        return total_profit, profit_rate, total_investment
        
    except Exception as e:
        logging.error(f"수익 계산 중 오류 발생: {e}")
        return 0, 0, 0

# 보유 종목 정보를 portfolio_config.json에 업데이트하는 함수
def update_portfolio_holdings():
    """현재 보유 종목 정보를 portfolio_config.json에 업데이트합니다."""
    try:
        # 현재 보유 주식 정보 가져오기
        MyStockList = KisKR.GetMyStockList()
        
        if not MyStockList:
            logging.warning("보유 주식 정보를 가져올 수 없습니다.")
            return
        
        # portfolio_config.json 파일 읽기
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_file_path = os.path.join(script_dir, "portfolio_config.json")
        
        with open(config_file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # Kosdaqpi_Bot의 보유 종목 정보 업데이트
        holdings = []
        total_holding_value = 0
        cumulative_profit = 0
        
        for stock in MyStockList:
            if stock['StockCode'] in InvestStockList:  # 투자 대상 종목만 처리
                try:
                    stock_code = stock['StockCode']
                    stock_name = stock['StockName']
                    stock_amt = int(stock['StockAmt'])
                    stock_avg_price = float(stock['StockAvgPrice'])
                    stock_now_price = float(stock['StockNowPrice'])
                    stock_revenue_money = float(stock['StockRevenueMoney'])
                    stock_revenue_rate = float(stock['StockRevenueRate'])
                    
                    # 현재 평가금액 계산
                    current_value = stock_amt * stock_now_price
                    
                    # 보유 종목 정보 생성
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
                    total_holding_value += current_value
                    cumulative_profit += stock_revenue_money
                    
                    logging.info(f"종목 정보 업데이트: {stock_name} - 수량: {stock_amt}, 수익률: {stock_revenue_rate:.2f}%")
                    
                except (ValueError, KeyError) as e:
                    logging.error(f"종목 데이터 처리 중 오류: {e}")
                    continue
        
        # 현재 분배금 계산 (초기 분배금 + 평가 손익 + 실현 손익 누적)
        initial_allocation = config_data['bots']['Kosdaqpi_Bot']['initial_allocation']
        realized_total_profit = config_data['bots']['Kosdaqpi_Bot'].get('total_sold_profit', 0)
        current_allocation = initial_allocation + cumulative_profit + realized_total_profit
        
        # 현금 잔고 계산 (현재 분배금 - 보유 주식 평가금액)
        cash_balance = current_allocation - total_holding_value
        
        # portfolio_config.json 업데이트
        config_data['bots']['Kosdaqpi_Bot']['current_allocation'] = current_allocation
        config_data['bots']['Kosdaqpi_Bot']['holdings'] = holdings
        config_data['bots']['Kosdaqpi_Bot']['total_holding_value'] = total_holding_value
        config_data['bots']['Kosdaqpi_Bot']['cash_balance'] = cash_balance
        # 판매 누적 수익은 판매 시점에만 갱신되며 여기서 리셋하지 않습니다.
        config_data['bots']['Kosdaqpi_Bot']['total_sold_profit'] = realized_total_profit
        
        # 파일에 저장
        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        
        logging.info("포트폴리오 보유 종목 정보가 성공적으로 업데이트되었습니다.")
        logging.info(f"총 보유 가치: {total_holding_value:,.0f}원")
        logging.info(f"누적 수익: {cumulative_profit:,.0f}원")
        logging.info(f"현금 잔고: {cash_balance:,.0f}원")
        
    except Exception as e:
        logging.error(f"포트폴리오 보유 종목 정보 업데이트 중 오류: {e}")

# 수익 정보 메시지 생성 함수
def create_profit_summary_message(total_profit, profit_rate, total_investment, current_date):
    """수익 요약 메시지를 생성합니다."""
    # portfolio_config.json에서 봇 정보 읽기
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_file_path = os.path.join(script_dir, "portfolio_config.json")
        
        with open(config_file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        initial_allocation = config_data['bots']['Kosdaqpi_Bot']['initial_allocation']
        current_allocation = config_data['bots']['Kosdaqpi_Bot']['current_allocation']
        total_sold_profit = config_data['bots']['Kosdaqpi_Bot']['total_sold_profit']
    except Exception as e:
        logging.error(f"portfolio_config.json 읽기 중 오류: {e}")
        initial_allocation = 0
        current_allocation = 0
        total_sold_profit = 0
    
    # 현재 보유 주식 정보 가져오기
    MyStockList = KisKR.GetMyStockList()
    
    # 투자 대상 종목 코드 리스트 생성 (InvestStockList는 이미 문자열 리스트)
    invest_stock_codes = InvestStockList
    
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
                status_emoji = "✅"
            elif stock_revenue_money < 0:
                loss_stocks += 1
                status_emoji = "❌"
            else:
                neutral_stocks += 1
                status_emoji = "➖"
            
            # 총금액 계산
            total_amount = stock_amt * stock_now_price
            
            # 수익/손실 기호 결정
            profit_sign = "+" if stock_revenue_money >= 0 else ""
            rate_sign = "+" if stock_revenue_rate >= 0 else ""
            
            message += f"{status_emoji} {stock_name} ({stock_amt}주)\n"
            message += f"   {total_amount:,.0f}원({profit_sign}{stock_revenue_money:,.0f}원:{rate_sign}{stock_revenue_rate:.2f}%)\n"
    
    # 전체 요약 정보
    message += "=" * 34 + "\n"
    message += f"💰 초기 분배금: {initial_allocation:,.0f}원\n"
    message += f"💰 현재 분배금: {current_allocation:,.0f}원\n"
    message += f"💰 총 투자금액: {total_investment:,.0f}원\n"
    message += f"📈 현재 수익금: {total_profit:,.0f}원({profit_rate:+.2f}%)\n"
    message += f"📊 누적 판매 수익금: {total_sold_profit:,.0f}원\n"
    message += f"📊 종목별 현황: 수익 {profit_stocks}개, 손실 {loss_stocks}개, 손익없음 {neutral_stocks}개\n"
    
    return message

# 봇 실행 시작 시 기간별 수익 초기화
if ENABLE_ORDER_EXECUTION == True:
    try:
        # 일별, 월별, 연별 판매수익 초기화
        initialize_period_profits()
        
        # 수익 계산 및 결과 받기
        total_profit, profit_rate, total_investment = calculate_and_update_profit()
        
        # 거래 내역 기반 수익 계산
        history_profit, history_profit_rate, history_investment, history_realized_profit = calculate_profit_from_history()
        
        # 보유 종목 정보를 portfolio_config.json에 업데이트
        update_portfolio_holdings()
        
        # 현재 날짜 정보 가져오기
        current_date = time.strftime("%Y-%m-%d")
        
        # 상태 요약 메시지와 수익 정보 메시지 생성
        status_summary = create_status_summary_message(KospidaqStrategyList, current_date)
        profit_summary = create_profit_summary_message(total_profit, profit_rate, total_investment, current_date)
        
        # 거래 내역 기반 수익 정보 추가
        if history_investment > 0:
            history_message = f"\n📊 거래 내역 기반 수익 현황:\n"
            history_message += f"💰 총 투자금액: {history_investment:,.0f}원\n"
            history_message += f"📈 평가손익: {history_profit:,.0f}원 ({history_profit_rate:+.2f}%)\n"
            history_message += f"💰 실현손익: {history_realized_profit:,.0f}원\n"
            profit_summary += history_message
        
        # 거래 내역 요약 추가
        trade_summary = get_trade_history_summary()
        if trade_summary and "거래 내역이 없습니다" not in trade_summary:
            profit_summary += f"\n{trade_summary}"
        
        # 두 메시지를 하나로 합쳐서 텔레그램 전송
        combined_message = status_summary + "\n\n" + profit_summary
        telegram.send(combined_message)
        logging.info("상태 요약 메시지와 수익 정보를 하나의 메시지로 합쳐서 텔레그램으로 전송했습니다.")
        logging.info(f"거래 내역 기반 수익 계산 완료: 투자금 {history_investment:,.0f}원, 수익률 {history_profit_rate:.2f}%")

    except Exception as e:
        error_msg = f"수익 계산 중 오류: {e}"
        logging.error(error_msg)
        # 오류가 발생해도 봇은 정상 종료로 처리

# 메인 실행 부분 추가
if __name__ == "__main__":
    try:
        logging.info("Kosdaqpi_Bot 시작")
        logging.info("=" * 37)
        
        # 여기에 봇의 메인 로직이 실행됩니다
        # 위의 코드에서 이미 실행되므로 추가 실행은 필요 없음
        
        logging.info("=" * 37)
        logging.info("Kosdaqpi_Bot 정상 종료")
        
    except Exception as e:
        error_msg = f"Kosdaqpi_Bot 실행 중 오류 발생: {e}"
        logging.error(error_msg)
        telegram.send(f"❌ {error_msg}")
        # 오류가 발생해도 종료 코드 0으로 처리 (스케줄러에서 정상 종료로 인식)
        sys.exit(0)