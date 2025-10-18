'''
1. 균등할당에 코스피100, 코스닥100에 총 200개 종목중에 종목당 50만원씩 책정해서 투자
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

백테스팅은 내PC에서 해야 서버 자원을 아끼고 투자 성과 그래프도 확인할 수 있습니다!
이 포스팅을 정독하시고 다양한 기간으로 백테스팅 해보세요!!!
https://blog.naver.com/zacra/223180500307

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

관련 포스팅
https://blog.naver.com/zacra/223597500754
위 포스팅을 꼭 참고하세요!!!

주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

'''
import KIS_Common as Common
import KIS_API_Helper_KR as KisKR
import pandas as pd
import pprint
import numpy as np
import matplotlib.pyplot as plt
import json
import os
import logging
import requests
from datetime import datetime

#MA_Strategy_FindMa.py에서 최적의 MA 값을 찾는 함수 import
#import MA_Strategy_FindMa as FindMA
# 최적화된 버전 사용 (선택사항)
import MA_Strategy_FindMa_Optimized as FindMA

def get_top_market_cap_stocks(count=100):
    """
    네이버 주식 API에서 코스피와 코스닥 시가총액 상위 종목들을 가져오는 함수
    
    Args:
        count (int): 각 시장에서 가져올 종목 수 (기본값: 100)
        
    Returns:
        list: 종목 코드 리스트
    """
    try:
        stock_codes = []
        
        # 코스피 시가총액 상위 종목 가져오기
        kospi_url = f"https://m.stock.naver.com/api/stocks/marketValue/KOSPI?page=1&pageSize={count}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        logging.info(f"코스피 시가총액 상위 {count}개 종목을 가져오는 중...")
        kospi_response = requests.get(kospi_url, headers=headers)
        kospi_response.raise_for_status()
        kospi_data = kospi_response.json()
        kospi_stocks = kospi_data.get('stocks', [])
        
        for stock in kospi_stocks:
            stock_code = stock.get('itemCode')
            stock_name = stock.get('stockName')
            market_value = stock.get('marketValue', '0')
            
            if stock_code:
                stock_codes.append(stock_code)
                logging.info(f"코스피 종목 추가: {stock_name} ({stock_code}) - 시가총액: {market_value}")
        
        # 코스닥 시가총액 상위 종목 가져오기
        kosdaq_url = f"https://m.stock.naver.com/api/stocks/marketValue/KOSDAQ?page=1&pageSize={count}"
        
        logging.info(f"코스닥 시가총액 상위 {count}개 종목을 가져오는 중...")
        kosdaq_response = requests.get(kosdaq_url, headers=headers)
        kosdaq_response.raise_for_status()
        kosdaq_data = kosdaq_response.json()
        kosdaq_stocks = kosdaq_data.get('stocks', [])
        
        for stock in kosdaq_stocks:
            stock_code = stock.get('itemCode')
            stock_name = stock.get('stockName')
            market_value = stock.get('marketValue', '0')
            
            if stock_code:
                stock_codes.append(stock_code)
                logging.info(f"코스닥 종목 추가: {stock_name} ({stock_code}) - 시가총액: {market_value}")
        
        logging.info(f"총 {len(stock_codes)}개 종목을 가져왔습니다. (코스피: {len(kospi_stocks)}개, 코스닥: {len(kosdaq_stocks)}개)")
        return stock_codes
        
    except Exception as e:
        logging.error(f"네이버 API에서 종목 정보 가져오기 실패: {e}")
        # 실패 시 기본 종목 리스트 반환
        return ["005930", "000660", "373220", "207940", "012450"]

def load_ma_values_from_json(filename="MA_Strategy_Test_v5.json"):
    """
    JSON 파일에서 종목별 이동평균선 값을 로드하는 함수
    
    Args:
        filename (str): JSON 파일명
        
    Returns:
        dict: 종목별 이동평균선 값 딕셔너리
    """
    try:
        # 소스 파일이 있는 폴더 경로 가져오기
        source_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(source_dir, filename)
        
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                ma_values = json.load(f)
                logging.info(f"기존 MA 값 파일을 로드했습니다: {file_path}")
                return ma_values
        else:
            logging.info(f"MA 값 파일이 존재하지 않습니다: {file_path}")
            return {}
    except Exception as e:
        logging.error(f"MA 값 파일 로드 중 오류 발생: {e}")
        return {}

def save_ma_values_to_json(ma_values, filename="MA_Strategy_Test_v5.json"):
    """
    종목별 이동평균선 값을 JSON 파일에 저장하는 함수
    
    Args:
        ma_values (dict): 종목별 이동평균선 값 딕셔너리
        filename (str): JSON 파일명
    """
    try:
        # 소스 파일이 있는 폴더 경로 가져오기
        source_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(source_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(ma_values, f, ensure_ascii=False, indent=4)
        logging.info(f"MA 값 파일을 저장했습니다: {file_path}")
    except Exception as e:
        logging.error(f"MA 값 파일 저장 중 오류 발생: {e}")

def get_or_create_ma_values(stock_codes, test_area="KR", filename="MA_Strategy_Test_v5.json"):
    """
    종목별 이동평균선 값을 가져오거나 새로 생성하는 함수
    
    Args:
        stock_codes (list): 종목 코드 리스트
        test_area (str): 테스트 영역 ("KR" 또는 "US")
        filename (str): JSON 파일명
        
    Returns:
        dict: 종목별 이동평균선 값 딕셔너리
    """
    # 기존 파일에서 로드
    ma_values = load_ma_values_from_json(filename)
    
    # 새로운 종목들 확인 (small_ma 값이 없는 종목들)
    new_stocks = []
    for stock_code in stock_codes:
        if stock_code not in ma_values or 'small_ma' not in ma_values[stock_code]:
            new_stocks.append(stock_code)
    
    # 새로운 종목이 있으면 최적 MA 값 찾기
    if new_stocks:
        logging.info(f"새로운 종목 {len(new_stocks)}개에 대해 최적 MA 값을 찾습니다...")
        
        for stock_code in new_stocks:
            logging.info(f"{stock_code} 종목의 최적 MA 값을 찾는 중...")
            
            # 최적의 MA 값 찾기
            optimal_result = FindMA.FindOptimalMA(
                stock_code=stock_code,
                test_area=test_area,
                get_count=700,
                cut_count=0,
                fee=0.0025,
                total_money=1000000
            )
            
            if optimal_result is not None:
                ma_values[stock_code] = {
                    "small_ma": optimal_result['small_ma'],
                    "big_ma": optimal_result['big_ma'],
                    "revenue_rate": optimal_result['revenue_rate'],
                    "mdd": optimal_result['mdd'],
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                logging.info(f"{stock_code}: small_ma={optimal_result['small_ma']}, big_ma={optimal_result['big_ma']}, 수익률={optimal_result['revenue_rate']}%, MDD={optimal_result['mdd']}%")
            else:
                logging.warning(f"{stock_code} 종목의 최적 MA 값을 찾을 수 없습니다.")
        
        # 업데이트된 값 저장
        save_ma_values_to_json(ma_values, filename)
    else:
        logging.info("모든 종목의 MA 값이 JSON 파일에 존재합니다. 기존 값을 사용합니다.")
    
    return ma_values

#로깅 설정
def setup_logging():
    """
    로깅 설정을 초기화하는 함수
    """
    #소스 파일이 있는 폴더 경로 가져오기
    source_dir = os.path.dirname(os.path.abspath(__file__))
    
    #logs 폴더가 없으면 생성
    logs_dir = os.path.join(source_dir, 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    #charts 폴더가 없으면 생성
    charts_dir = os.path.join(source_dir, 'charts')
    if not os.path.exists(charts_dir):
        os.makedirs(charts_dir)
    
    #로깅 설정
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(logs_dir, f"MA_Strategy_Test_v5_{timestamp}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return timestamp, source_dir

#차트 저장 함수
def save_charts(df, stock_code, timestamp, source_dir, strategy_name="MA_Strategy_v5"):
    """
    차트를 저장하는 함수
    
    Args:
        df (DataFrame): 차트 데이터
        stock_code (str): 종목 코드
        timestamp (str): 타임스탬프
        source_dir (str): 소스 폴더 경로
        strategy_name (str): 전략 이름
    """
    try:
        #가격 차트
        plt.figure(figsize=(15, 10))
        
        #서브플롯 설정
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 12))
        
        #가격 차트
        ax1.plot(df.index, df['close'], label='Close Price', color='blue')
        ax1.set_title(f'{stock_code} - Price Chart')
        ax1.set_ylabel('Price')
        ax1.legend()
        ax1.grid(True)
        
        #거래량 차트
        ax2.bar(df.index, df['volume'], color='green', alpha=0.7)
        ax2.set_title(f'{stock_code} - Volume Chart')
        ax2.set_ylabel('Volume')
        ax2.grid(True)
        
        #이동평균선 차트
        if 'small_ma' in df.columns and 'big_ma' in df.columns:
            ax3.plot(df.index, df['close'], label='Close Price', color='blue')
            ax3.plot(df.index, df['small_ma'], label='Small MA', color='red')
            ax3.plot(df.index, df['big_ma'], label='Big MA', color='orange')
            ax3.set_title(f'{stock_code} - Moving Average Chart')
            ax3.set_ylabel('Price')
            ax3.legend()
            ax3.grid(True)
        
        plt.tight_layout()
        
        #차트 저장
        chart_filename = os.path.join(source_dir, 'charts', f"{strategy_name}_{stock_code}_{timestamp}.png")
        plt.savefig(chart_filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        logging.info(f"차트가 저장되었습니다: {chart_filename}")
        
    except Exception as e:
        logging.error(f"차트 저장 중 오류 발생: {e}")

#결과 저장 함수
def save_results(results, timestamp, source_dir, strategy_name="MA_Strategy_v5"):
    """
    결과를 JSON 파일로 저장하는 함수
    
    Args:
        results (dict): 결과 데이터
        timestamp (str): 타임스탬프
        source_dir (str): 소스 폴더 경로
        strategy_name (str): 전략 이름
    """
    try:
        results_filename = os.path.join(source_dir, 'logs', f"{strategy_name}_results_{timestamp}.json")
        with open(results_filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        logging.info(f"결과가 저장되었습니다: {results_filename}")
        
    except Exception as e:
        logging.error(f"결과 저장 중 오류 발생: {e}")

#최적의 MA 값을 찾아서 InvestStockList를 생성하는 함수 (JSON 파일 사용)
def CreateOptimalInvestStockList(stock_codes, test_area="KR", invest_rates=None, use_json=True):
    """
    주어진 종목 코드들에 대해 최적의 MA 값을 찾아서 InvestStockList를 생성하는 함수
    
    Args:
        stock_codes (list): 종목 코드 리스트
        test_area (str): 테스트 영역 ("KR" 또는 "US")
        invest_rates (list): 투자 비율 리스트 (None이면 균등 분배)
        use_json (bool): JSON 파일 사용 여부
        
    Returns:
        list: 최적의 MA 값이 설정된 InvestStockList
    """
    if invest_rates is None:
        #균등 분배
        invest_rates = [1.0 / len(stock_codes)] * len(stock_codes)
    
    invest_stock_list = []
    
    if use_json:
        # JSON 파일에서 MA 값 가져오기
        ma_values = get_or_create_ma_values(stock_codes, test_area)
        
        for i, stock_code in enumerate(stock_codes):
            if stock_code in ma_values:
                ma_data = ma_values[stock_code]
                invest_stock_list.append({
                    "stock_code": stock_code,
                    "small_ma": ma_data['small_ma'],
                    "big_ma": ma_data['big_ma'],
                    "invest_rate": invest_rates[i]
                })
                logging.info(f"{stock_code}: small_ma={ma_data['small_ma']}, big_ma={ma_data['big_ma']}, invest_rate={invest_rates[i]} (JSON에서 로드)")
            else:
                logging.warning(f"{stock_code} 종목의 MA 값이 JSON 파일에 없습니다.")
    else:
        # 기존 방식: 실시간으로 최적 MA 값 찾기
        for i, stock_code in enumerate(stock_codes):
            logging.info(f"{stock_code} 종목의 최적 MA 값을 찾는 중...")
            
            #최적의 MA 값 찾기
            optimal_result = FindMA.FindOptimalMA(
                stock_code=stock_code,
                test_area=test_area,
                get_count=700,
                cut_count=0,
                fee=0.0025,
                total_money=1000000
            )
            
            if optimal_result is not None:
                invest_stock_list.append({
                    "stock_code": stock_code,
                    "small_ma": optimal_result['small_ma'],
                    "big_ma": optimal_result['big_ma'],
                    "invest_rate": invest_rates[i]
                })
                logging.info(f"{stock_code}: small_ma={optimal_result['small_ma']}, big_ma={optimal_result['big_ma']}, invest_rate={invest_rates[i]}")
            else:
                logging.warning(f"{stock_code} 종목의 최적 MA 값을 찾을 수 없습니다.")
    
    return invest_stock_list

#토큰 만료 시 자동 재발급받는 함수
def RefreshTokenIfNeeded():
    """
    토큰이 만료되었는지 확인하고 필요시 재발급받는 함수
    """
    try:
        #간단한 API 호출로 토큰 유효성 테스트
        test_result = KisKR.GetCurrentPrice("069500")  # KODEX 200으로 테스트
        if test_result is None or test_result == "EGW00123":
            logging.info("토큰이 만료되었습니다. 새로운 토큰을 발급받습니다...")
            Common.RefreshTokenIfExpired(Common.GetNowDist())
            return True
        return False
    except Exception as e:
        error_msg = str(e)
        if "EGW00123" in error_msg or "기간이 만료된 token" in error_msg:
            logging.info("토큰이 만료되었습니다. 새로운 토큰을 발급받습니다...")
            Common.RefreshTokenIfExpired(Common.GetNowDist())
            return True
        return False

#로깅 설정 초기화
timestamp, source_dir = setup_logging()
logging.info("MA_Strategy_Test_v5 시작")

Common.SetChangeMode("VIRTUAL") 

##################################################################

###############################################################################################################################################################
#테스트할 종목을 직접 판단하여 아래 예시처럼 넣으세요!
InvestStockList = list()

#기존 수동 설정 방식 (주석 처리)
#InvestStockList.append({"stock_code":"QQQ", "small_ma":3 , "big_ma":132, "invest_rate":0.5}) 
#InvestStockList.append({"stock_code":"TLT", "small_ma":13 , "big_ma":53, "invest_rate":0.25}) 
#InvestStockList.append({"stock_code":"GLD", "small_ma":17 , "big_ma":78, "invest_rate":0.25}) 

#InvestStockList.append({"stock_code":"133690", "small_ma":5 , "big_ma":34, "invest_rate":0.4}) #TIGER 미국나스닥100
#InvestStockList.append({"stock_code":"069500", "small_ma":3 , "big_ma":103, "invest_rate":0.2}) #KODEX 200
#InvestStockList.append({"stock_code":"148070", "small_ma":8 , "big_ma":71, "invest_rate":0.1}) #KOSEF 국고채10년
#InvestStockList.append({"stock_code":"305080", "small_ma":20 , "big_ma":61, "invest_rate":0.1}) #TIGER 미국채10년선물
#InvestStockList.append({"stock_code":"132030", "small_ma":15 , "big_ma":89, "invest_rate":0.2}) #KODEX 골드선물(H)

#자동으로 최적의 MA 값을 찾아서 설정 (TestArea 정의 후에 실행)
#stock_codes = ["133690","069500","148070","305080","132030"]  # 테스트를 위해 하나의 종목만 사용

# 시가총액 상위 종목 수 설정
TOP_STOCK_COUNT = 100  # 시가총액 상위 100개 종목 사용
# 최대 종목수 제한 제거 - 남은 금액이 50만원 이상일 때만 투자

# 시가총액 상위 종목들을 자동으로 가져오기
logging.info(f"네이버 API에서 시가총액 상위 {TOP_STOCK_COUNT}개 종목들을 가져오는 중...")
stock_codes = get_top_market_cap_stocks(count=TOP_STOCK_COUNT)

# 투자 비율을 단순화 (각 종목이 독립적으로 투자되므로 50만원 고정 투자)
invest_rates = [500000] * len(stock_codes)  # 모든 종목에 대해 50만원 고정 투자

#TestArea가 정의된 후에 실행되도록 주석 처리
#InvestStockList = CreateOptimalInvestStockList(stock_codes, TestArea, invest_rates)
###############################################################################################################################################################


#####################################################
TestArea = "KR" #한국이라면 KR 미국이라면 US로 변경하세요 ^^

#################################################################
FixRate = 0.0 #각 자산별 할당 금액의 10%를 고정비중으로 투자함!
DynamicRate = 0.0 #각 자산별 할당 금액의 60%의 투자 비중은 모멘텀에 의해 정해짐!
#위의 경우 FixRate + DynamicRate = 0.7 즉 70%이니깐 매도신호 시 30%비중은 무조건 팔도록 되어 있다.
#위 두 값이 모두 0이라면 기존처럼 매도신호시 모두 판다!!


GetCount = 700  #얼마큼의 데이터를 가져올 것인지
CutCount = 0     #최근 데이터 삭제! 200으로 세팅하면 200개의 최근 데이터가 사라진다

  
TotalMoney = 10000000 #한국 계좌의 경우 시작 투자금 1000만원으로 가정!

TaxAdd = False #양도세 반영 여부! 
MoneyForTaxCalc = 0 #양도세 계산을 위한 손익을 저장할 변수 - 미국만 해당
FreeTax = 2100 #환율을 1200원으로 퉁쳐서 $2100 가 면세 기준! - 미국만 해당


if TestArea == "US": #미국의 경우는
    TotalMoney = 10000 #시작 투자금 $10000로 가정!
    TaxAdd = True #미국의 경우 양도세 반영!!!

#TestArea가 정의된 후에 최적의 MA 값을 찾아서 InvestStockList 생성
logging.info("JSON 파일에서 MA 값을 로드하거나 새로 생성하는 중...")
InvestStockList = CreateOptimalInvestStockList(stock_codes, TestArea, invest_rates, use_json=True)

FirstInvestMoney = TotalMoney

fee = 0.0025 #수수료를 매수매도마다 0.25%로 세팅!

print("테스트하는 총 금액: ", format(round(TotalMoney), ','))


#################################################################

    
RebalanceSt = "%Y%m" 


StockDataList = list()

for stock_info in InvestStockList:
    logging.info(f"종목 정보: {stock_info}")
    stock_data = dict()
    stock_data['stock_code'] = stock_info['stock_code']
    
    if TestArea == "KR":
        stock_data['stock_name'] = KisKR.GetStockName(stock_info['stock_code'])
    else:
        stock_data['stock_name'] = stock_info['stock_code']
        
    stock_data['invest_rate'] = stock_info['invest_rate']
    stock_data['InvestDayCnt'] = 0
    StockDataList.append(stock_data)

logging.info(f"종목 데이터 리스트: {StockDataList}")


def IncreaseInvestDayCnt(stock_code, StockDataList):
    for stock_data in StockDataList:
        if stock_code == stock_data['stock_code']:
            stock_data['InvestDayCnt'] += 1
            break


def GetDefaultInvestRate(stock_code, StockDataList):
    # 각 종목이 독립적으로 투자되므로 50만원 고정 투자
    return 500000  # 50만원 고정 투자


#사실 미국에선 사용하지 않지만 한국에선 사용
def GetStockName(stock_code, StockDataList):
    result_str = stock_code
    for stock_data in StockDataList:
        if stock_code == stock_data['stock_code']:
            result_str = stock_data['stock_name']
            break

    return result_str

NowInvestList = list() #투자중인 항목의 리스트
AvailableStockList = list() #구매 가능한 종목 리스트 (Average_Momentum = 1인 종목들)

# 현재 투자 중인 종목 수를 추적하는 변수 (최대 종목수 제한 제거)
CurrentInvestCount = 0

stock_df_list = []

for stock_info in InvestStockList:
    
    stock_code = stock_info['stock_code']
    #################################################################
    #################################################################
    #토큰 만료 시 자동 재발급받는 로직 추가
    try:
        df = Common.GetOhlcv(TestArea, stock_code, GetCount) 
        if df is None:
            logging.warning(f"데이터 조회 실패 ({stock_code}). 토큰을 재발급받습니다...")
            Common.RefreshTokenIfExpired(Common.GetNowDist())
            df = Common.GetOhlcv(TestArea, stock_code, GetCount)
    except Exception as e:
        error_msg = str(e)
        if "EGW00123" in error_msg or "기간이 만료된 token" in error_msg:
            logging.warning(f"토큰 만료 오류 발생 ({stock_code}). 토큰을 재발급받습니다...")
            Common.RefreshTokenIfExpired(Common.GetNowDist())
            df = Common.GetOhlcv(TestArea, stock_code, GetCount)
        else:
            logging.error(f"데이터 조회 중 오류 발생 ({stock_code}): {e}")
            continue
    #################################################################
    #################################################################

    if df is None:
        logging.error(f"데이터를 가져올 수 없습니다 ({stock_code}). 다음 종목으로 넘어갑니다.")
        continue

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

    df = df[:len(df)- CutCount]
    data_dict = {stock_code: df}


    stock_df_list.append(data_dict)
    
    #차트 저장
    try:
        #이동평균선 추가
        df_chart = df.copy()
        df_chart['small_ma'] = df_chart['close'].rolling(stock_info['small_ma']).mean()
        df_chart['big_ma'] = df_chart['close'].rolling(stock_info['big_ma']).mean()
        
        #save_charts(df_chart, stock_code, timestamp, source_dir, "MA_Strategy_v5")
    except Exception as e:
        logging.error(f"차트 저장 중 오류 발생 ({stock_code}): {e}")
        
    logging.info(f"종목 코드: {stock_code}, 데이터 길이: {len(df)}")

    #모든 항목의 데이터를 만들어 놓는다!
    InvestData = dict()

    InvestData['stock_code'] = stock_code
    InvestData['InvestMoney'] = 0
    InvestData['InvestRate'] = stock_info['invest_rate']
    InvestData['small_ma'] = stock_info['small_ma']
    InvestData['big_ma'] =  stock_info['big_ma']
    InvestData['RebalanceAmt'] = 0
    InvestData['EntryMonth'] = 0
    InvestData['AvgPrice'] = 0
    InvestData['TotAmt'] = 0
    InvestData['Investing'] = False
    InvestData['IsRebalanceGo'] = False


    NowInvestList.append(InvestData)



combined_df = pd.concat([list(data_dict.values())[0].assign(stock_code=stock_code) for data_dict in stock_df_list for stock_code in data_dict])
combined_df.sort_index(inplace=True)
pprint.pprint(combined_df)
print(" len(combined_df) ", len(combined_df))



IsFirstDateSet = False
FirstDateStr = ""


NowInvestCode = ""
InvestMoney = TotalMoney
RemainInvestMoney = InvestMoney



ResultList = list()

TotalMoneyList = list()


i = 0
# Iterate over each date
for date in combined_df.index.unique():
 

    #날짜 정보를 획득
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
            

    i += 1


    IsRebalnceDayforTax = False


    # 현재 날짜에서 Average_Momentum = 1인 종목들을 찾아서 AvailableStockList에 추가
    AvailableStockList.clear()
    for stock_code in stock_codes:
        stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)]
        if len(stock_data) == 1:
            # if stock_data['Average_Momentum'].values[0] == 1.0:  # Average_Momentum 조건 주석처리
            AvailableStockList.append(stock_code)
    
    # 현재 투자 중인 종목 수 계산
    CurrentInvestCount = sum(1 for investData in NowInvestList if investData['Investing'] == True)
    
    #투자중인 종목을 순회하며 처리!
    for investData in NowInvestList:

        stock_code = investData['stock_code'] 
        
    

        stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)] 


        if len(stock_data) == 1:
    
            #################################################################################################################
            #매일매일의 등락률을 반영한다!
            NowClosePrice = 0
            PrevClosePrice = 0

            NowClosePrice = stock_data['close'].values[0]
            PrevClosePrice = stock_data['prevClose'].values[0] 


            if investData['InvestMoney'] > 0:
                investData['InvestMoney'] = investData['InvestMoney'] *  (1.0 + ((NowClosePrice - PrevClosePrice ) / PrevClosePrice))
                IncreaseInvestDayCnt(stock_code, StockDataList)
            #################################################################################################################



            ma1 = investData['small_ma']
            ma2 = investData['big_ma']
            
                
            small_ma = int(ma1)
            big_ma = int(ma2)
            
            

            IsReblanceDay = False
            
            if investData['EntryMonth'] != date_object.strftime(RebalanceSt):
                investData['EntryMonth'] = date_object.strftime(RebalanceSt)

                IsRebalnceDayforTax = True #미국 양도세 관련..



            

            #이평선에 의해 매도처리 해야 된다!!! 
            if investData['Investing'] == True and stock_data[str(small_ma)+'ma_before'].values[0] < stock_data[str(big_ma)+'ma_before'].values[0] and stock_data[str(small_ma)+'ma_before2'].values[0] > stock_data[str(small_ma)+'ma_before'].values[0]:
                IsReblanceDay = True
                
                SellRate = FixRate + (stock_data['Average_Momentum'].values[0] * DynamicRate) 
                
                investData['InvestRate'] = GetDefaultInvestRate(stock_code, StockDataList) * SellRate
                
            

            if investData['Investing'] == False and stock_data[str(small_ma)+'ma_before'].values[0] > stock_data[str(big_ma)+'ma_before'].values[0] and stock_data[str(small_ma)+'ma_before2'].values[0] < stock_data[str(small_ma)+'ma_before'].values[0]:
                # Average_Momentum = 1이고 남은 금액이 50만원 이상일 때만 매수
                # if stock_data['Average_Momentum'].values[0] == 1.0 and RemainInvestMoney >= 500000:  # Average_Momentum 조건 주석처리
                if RemainInvestMoney >= 500000:  # 남은 금액만 체크
                    IsReblanceDay = True
                    investData['InvestRate'] = GetDefaultInvestRate(stock_code, StockDataList)
                    logging.info(f"새로운 종목 매수 시도: {stock_code} (남은금액: {RemainInvestMoney:,.0f}원)")
                    
                
            if IsReblanceDay == True: 
                
                
                investData['IsRebalanceGo'] = True
                investData['RebalanceAmt'] = 0

    
    if IsRebalnceDayforTax == True:

        if TaxAdd == True:
            #리밸런싱 하는 날이 1월 이라면 양도세를 반영하고 초기화 시켜준다!
            if int(date_object.strftime("%m")) == 1:
                MoneyForTaxCalc -= FreeTax
                
                print("지난 한해 동안 $", MoneyForTaxCalc," 손익확정을 했어요!")
                
                
                #공제후에도 남은 수익에 대해선 양도세22를 계산해 감산하자!!
                if MoneyForTaxCalc > 0:
                    OMG_Tax = MoneyForTaxCalc * 0.22
                    RemainInvestMoney -= OMG_Tax #남은 투자금에서 감산!!!
                    print(str(date), "--양도세 $",OMG_Tax , "차감 되었어요 ㅠ.ㅜ")
                else:
                    print(str(date), "--양도세 없어요! 불행인지 다행인지...^^")
                    
                    
                MoneyForTaxCalc = 0 #새해가 되었으니 초기화!!
                
            

    #################################################################################################################
    ##################### 리밸런싱 할때 투자 비중을 맞춰주는 작업 #############################



    NowInvestMoney = 0

    for iData in NowInvestList:
        NowInvestMoney += iData['InvestMoney']

    
    InvestMoney = RemainInvestMoney + NowInvestMoney


    #리밸런싱 수량을 확정한다!
    for investData in NowInvestList:

        if investData['IsRebalanceGo'] == True:

            stock_code = investData['stock_code']

            stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)] 

            
            if len(stock_data) == 1:
                

                NowClosePrice = stock_data['close'].values[0]


                # 각 종목의 목표 투자 금액을 50만원으로 설정
                GapInvest = investData['InvestRate'] - investData['InvestMoney'] #목표 금액(50만원)에서 현재 평가금액을 빼서 갭을 구한다!
                investData['RebalanceAmt'] += int(GapInvest / NowClosePrice)




    #실제 매도!!
    for investData in NowInvestList:


        if investData['IsRebalanceGo'] == True:


            stock_code = investData['stock_code']
            
            stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)] 

            if len(stock_data) == 1:

                NowClosePrice = stock_data['close'].values[0]

                if investData['RebalanceAmt'] < 0:


                    SellAmt = abs(investData['RebalanceAmt'])

                    RealSellMoney = SellAmt * NowClosePrice


                    RevenueRate = (NowClosePrice - investData['AvgPrice']) / investData['AvgPrice'] #손익률을 구한다!

                    #팔아야할 금액이 현재 투자금보다 크다면!!! 모두 판다! 혹은 실제 팔아야할 계산된 금액이 투자금보다 크다면 모두 판다!!
                    if RealSellMoney > investData['InvestMoney']:
                        RealSellMoney = investData['InvestMoney']

                        ReturnMoney = RealSellMoney

                        investData['InvestMoney'] = 0

                        RemainInvestMoney += (ReturnMoney * (1.0 - fee))

                        investData['IsRebalanceGo'] = False

                        investData['AvgPrice'] = 0
                        investData['TotAmt'] = 0
                        
                        #모두 팔때는 매도 금액 x 수익률이 손익금
                        if TaxAdd == True:
                            MoneyForTaxCalc += RealSellMoney * RevenueRate
                        
                        print(investData['stock_code'], str(date), " " ,i, " >>>>>>>>>>>>>>>>> 모두 매도!(리밸런싱) 매도금액:", round(RealSellMoney,2) ,  " 매도가:",NowClosePrice)
                        CurrentInvestCount -= 1  # 실제 매도 시 투자 종목 수 감소
                        
                        
                    else:

                        if SellAmt > 0 :

                            ReturnMoney = RealSellMoney

                            investData['InvestMoney'] -= RealSellMoney

                            RemainInvestMoney += (ReturnMoney * (1.0 - fee))

                            investData['IsRebalanceGo'] = False
                            
                            investData['TotAmt'] -= SellAmt
                            
                            #일부 팔때는 (매도금액 x 매도수량) - (평균매입단가 x 매도수량)
                            if TaxAdd == True:
                                MoneyForTaxCalc += (RealSellMoney - (investData['AvgPrice']*SellAmt))
                                
                            print(investData['stock_code'], str(date), " " ,i, " >>>>>>>>>>>>>>>>> 일부 매도!(리밸런싱) 매도금액:", round(RealSellMoney,2) ,  " 매도가:",NowClosePrice)
                            CurrentInvestCount -= 1  # 일부 매도 시에도 투자 종목 수 감소

                    
                    investData['Investing'] = False

                    investData['EntryMonth'] = date_object.strftime(RebalanceSt)
                    investData['IsRebalanceGo'] = False
                    
                    # 매도 후 새로운 종목 구매 시도 (남은 금액이 50만원 이상일 때만)
                    if RemainInvestMoney >= 500000 and len(AvailableStockList) > 0:
                        # 아직 투자하지 않은 종목 중에서 Average_Momentum = 1인 종목 찾기
                        for available_stock in AvailableStockList:
                            # 이미 투자 중인 종목인지 확인
                            is_already_investing = any(inv['stock_code'] == available_stock and inv['Investing'] == True for inv in NowInvestList)
                            
                            if not is_already_investing:
                                # 새로운 종목 구매
                                for new_invest in NowInvestList:
                                    if new_invest['stock_code'] == available_stock:
                                        new_invest['IsRebalanceGo'] = True
                                        new_invest['RebalanceAmt'] = 0
                                        new_invest['InvestRate'] = GetDefaultInvestRate(available_stock, StockDataList)
                                        logging.info(f"매도 후 새로운 종목 구매 시도: {available_stock} (남은금액: {RemainInvestMoney:,.0f}원)")
                                        break
                            break

            

    #실제 매수!!
    for investData in NowInvestList:


        if investData['IsRebalanceGo'] == True:


            stock_code = investData['stock_code']
            
            stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)] 

            if len(stock_data) == 1:

                NowClosePrice = stock_data['close'].values[0]

                if investData['RebalanceAmt'] > 0:


                    if IsFirstDateSet == False:
                        FirstDateStr = str(date)
                        IsFirstDateSet = True


                    BuyAmt = investData['RebalanceAmt']


                    NowFee = (BuyAmt*NowClosePrice) * fee

                    # 구매하려는 종목이 50만원 이상일 때 최소 1주를 구매하되, 남은 돈 내에서 구매
                    if BuyAmt * NowClosePrice >= 500000:
                        # 최소 1주는 구매하되, 남은 돈 내에서 구매
                        min_buy_amount = max(1, BuyAmt)
                        
                        # 남은 돈으로 구매 가능한 최대 수량 계산
                        max_affordable_amount = int((RemainInvestMoney - NowFee) / NowClosePrice)
                        
                        # 최소 1주와 구매 가능한 수량 중 작은 값으로 설정
                        BuyAmt = min(min_buy_amount, max_affordable_amount)
                        NowFee = (BuyAmt*NowClosePrice) * fee
                    else:
                        # 50만원 미만인 경우 기존 로직 사용
                        #매수해야 되는데 남은돈이 부족하다면 수량을 하나씩 감소시켜 만족할 때 매수한다!!
                        while RemainInvestMoney < (BuyAmt*NowClosePrice) + NowFee:
                            if RemainInvestMoney > NowClosePrice:
                                BuyAmt -= 1
                                NowFee = (BuyAmt*NowClosePrice) * fee
                            else:
                                break
                    
                    if BuyAmt > 0 and RemainInvestMoney > NowClosePrice:
                        RealBuyMoney = BuyAmt * NowClosePrice

                        investData['InvestMoney'] += RealBuyMoney

                        RemainInvestMoney -= (BuyAmt*NowClosePrice) #남은 투자금!
                        RemainInvestMoney -= NowFee

                        print('GOGO!!!')
                        if investData['TotAmt'] == 0:
                            investData['AvgPrice'] = NowClosePrice
                            investData['TotAmt'] = BuyAmt
                            

                        else:

                            investData['TotAmt'] += BuyAmt
                            investData['AvgPrice'] = ((investData['AvgPrice'] * (investData['TotAmt']-BuyAmt)) + (BuyAmt*NowClosePrice)) / investData['TotAmt']

                        print(investData['stock_code'], str(date), " " ,i, " >>>>>>>>>>>>>>>>> 매수!(리밸런싱) 매수금액:", round(RealBuyMoney,2) ,  " 매수가:",NowClosePrice)
                        investData['Investing'] = True
                        CurrentInvestCount += 1  # 실제 매수 시 투자 종목 수 증가
                        
                        # 매도 후 새로운 종목 구매인 경우 로그 추가
                        if investData['stock_code'] in AvailableStockList:
                            logging.info(f"매도 후 새로운 종목 매수 완료: {investData['stock_code']} (매수금액: {RealBuyMoney:,.0f}원)")
            

                    investData['EntryMonth'] = date_object.strftime(RebalanceSt)
                    investData['IsRebalanceGo'] = False


    #혹시나 위에서 처리되지 않은 게 있다면...            
    for investData in NowInvestList:


        if investData['IsRebalanceGo'] == True:

            investData['EntryMonth'] = date_object.strftime(RebalanceSt)
            investData['IsRebalanceGo'] = False



    
    NowInvestMoney = 0

    for iData in NowInvestList:
        NowInvestMoney += iData['InvestMoney']

    
    InvestMoney = RemainInvestMoney + NowInvestMoney



    InvestCoinListStr = ""
    print("\n\n------------------------------------\n")
    for iData in NowInvestList:
        InvestCoinListStr += (">>>" + GetStockName(iData['stock_code'], StockDataList)  + "-> 목표투자비중:" + str(iData['InvestRate']*100) + "%-> 실제투자비중:" + str(iData['InvestMoney']/InvestMoney*100)  +"%\n -->실제투자금:" + str(format(int(round(iData['InvestMoney'],0)), ',')) +"\n\n")
    print("------------------------------------")

    print(InvestCoinListStr, "---> 투자대상 : ", len(NowInvestList))
    #pprint.pprint(NowInvestList)
    print(">>>>>>>>>>>>--))", str(date), " 잔고:",format(int(round(InvestMoney,0)), ',') , "=" , format(int(round(RemainInvestMoney,0)), ',') , "+" , format(int(round(NowInvestMoney,0)), ','), "\n\n" )
    print("MoneyForTaxCalc : ", MoneyForTaxCalc)

    TotalMoneyList.append(InvestMoney)

    #####################################################
    #####################################################
    #####################################################
    #'''
    
   


#결과 정리 및 데이터 만들기!!
if len(TotalMoneyList) > 0:

    print("TotalMoneyList -> ", len(TotalMoneyList))


    resultData = dict()

    # Create the result DataFrame with matching shapes
    result_df = pd.DataFrame({"Total_Money": TotalMoneyList}, index=combined_df.index.unique())

    result_df['Ror'] = np.nan_to_num(result_df['Total_Money'].pct_change()) + 1
    result_df['Cum_Ror'] = result_df['Ror'].cumprod()
    result_df['Highwatermark'] = result_df['Cum_Ror'].cummax()
    result_df['Drawdown'] = (result_df['Cum_Ror'] / result_df['Highwatermark']) - 1
    result_df['MaxDrawdown'] = result_df['Drawdown'].cummin()

    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    pprint.pprint(result_df)
    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

    resultData['DateStr'] = str(FirstDateStr) + " ~ " + str(result_df.iloc[-1].name)

    resultData['OriMoney'] = FirstInvestMoney
    resultData['FinalMoney'] = result_df['Total_Money'].iloc[-1]
    resultData['RevenueRate'] = ((result_df['Cum_Ror'].iloc[-1] -1.0)* 100.0)

    resultData['MDD'] = result_df['MaxDrawdown'].min() * 100.0


    ResultList.append(resultData)

    result_df.index = pd.to_datetime(result_df.index)


    # Create a figure with subplots for the two charts
    fig, axs = plt.subplots(2, 1, figsize=(10, 10))

    # Plot the return chart
    axs[0].plot(result_df['Cum_Ror'] * 100, label='Strategy')
    axs[0].set_ylabel('Cumulative Return (%)')
    axs[0].set_title('Return Comparison Chart')
    axs[0].legend()

    # Plot the MDD and DD chart on the same graph
    axs[1].plot(result_df.index, result_df['MaxDrawdown'] * 100, label='MDD')
    axs[1].plot(result_df.index, result_df['Drawdown'] * 100, label='Drawdown')
    axs[1].set_ylabel('Drawdown (%)')
    axs[1].set_title('Drawdown Comparison Chart')
    axs[1].legend()

    # Show the plot
    plt.tight_layout()
    
    #차트 저장
    try:
        chart_filename = os.path.join(source_dir, 'charts', f"MA_Strategy_v5_results_{timestamp}.png")
        plt.savefig(chart_filename, dpi=300, bbox_inches='tight')
        logging.info(f"결과 차트가 저장되었습니다: {chart_filename}")
    except Exception as e:
        logging.error(f"결과 차트 저장 중 오류 발생: {e}")
    
    plt.show()
        

    


    for idx, row in result_df.iterrows():
        print(idx, " " , row['Total_Money'], " "  , row['Cum_Ror'])
        



#데이터를 보기좋게 프린트 해주는 로직!
print("\n\n--------------------")


for result in ResultList:

    print("--->>>",result['DateStr'].replace("00:00:00",""),"<<<---")

    for stock_data in StockDataList:
        print(stock_data['stock_name'] , " (", stock_data['stock_code'],") 투자일수: ",stock_data['InvestDayCnt'])

    print("---------- 총 결과 ----------")
    print("최초 금액:", format(int(round(result['OriMoney'],0)), ',') , " 최종 금액:", format(int(round(result['FinalMoney'],0)), ','), " \n수익률:", round(((round(result['FinalMoney'],2) - round(result['OriMoney'],2) ) / round(result['OriMoney'],2) ) * 100,2) ,"% MDD:",  round(result['MDD'],2),"%")

    print("------------------------------")
    print("####################################")
    
    #결과 저장
    try:
        results_data = {
            'strategy_name': 'MA_Strategy_v5',
            'timestamp': timestamp,
            'test_area': TestArea,
            'total_money': TotalMoney,
            'results': ResultList,
            'stock_data': StockDataList,
            'final_result': {
                'initial_money': result['OriMoney'],
                'final_money': result['FinalMoney'],
                'revenue_rate': round(((round(result['FinalMoney'],2) - round(result['OriMoney'],2) ) / round(result['OriMoney'],2) ) * 100,2),
                'mdd': round(result['MDD'],2),
                'date_range': result['DateStr']
            }
        }
        
        save_results(results_data, timestamp, source_dir, "MA_Strategy_v5")
        logging.info("백테스팅 완료 및 결과 저장 완료")
        
    except Exception as e:
        logging.error(f"결과 저장 중 오류 발생: {e}")
