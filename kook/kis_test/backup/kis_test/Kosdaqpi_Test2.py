'''

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
코드 참고 영상!
https://youtu.be/YdEdM-oC0kc
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$


$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

백테스팅은 내PC에서 해야 서버 자원을 아끼고 투자 성과 그래프도 확인할 수 있습니다!
이 포스팅을 정독하시고 다양한 기간으로 백테스팅 해보세요!!!
https://blog.naver.com/zacra/223180500307

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$




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

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제공된 전략은 학습 및 테스트 목적으로 구성된 예시 코드이며
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.
   

주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!
   

  
'''

# =============================================================================
# 코스피/코스닥 양방향 투자 전략 백테스팅 프로그램
# =============================================================================
# 
# 전략 개요:
# - 코스피 쌍: KODEX 레버리지(122630) + KODEX 200선물인버스2X(252670)
# - 코스닥 쌍: KODEX 코스닥150레버리지(233740) + KODEX 코스닥150선물인버스(251340)
# - 최대 2개 종목 동시 보유, 시장 상황에 따른 동적 비중 조절
# - 상승/하락 모두에서 수익 추구하는 양방향 투자 전략
#
# 주요 특징:
# 1. 코스피 종목: 기술적 지표 기반 매매
# 2. 코스닥 종목: 변동성 돌파 전략
# 3. 모멘텀 기반 비중 조절
# 4. 횡보장 대응 로직
# =============================================================================

# 필요한 라이브러리 임포트
import KIS_Common as Common          # KIS API 공통 모듈
import KIS_API_Helper_KR as KisKR    # KIS 한국 API 헬퍼
import pandas as pd                   # 데이터 처리
import pprint                         # 데이터 출력
import numpy as np                    # 수치 계산
import matplotlib.pyplot as plt       # 차트 생성
from datetime import datetime         # 날짜 처리
import os                             # 파일 시스템
import logging                        # 로깅

# =============================================================================
# 로깅 설정
# =============================================================================
# 로그 디렉토리 및 파일 설정
script_dir = os.path.dirname(os.path.abspath(__file__))  # 현재 스크립트 디렉토리
log_dir = os.path.join(script_dir, "logs")              # 로그 디렉토리
if not os.path.exists(log_dir):
    os.makedirs(log_dir)                                # 로그 디렉토리 생성
log_filename = os.path.join(log_dir, "Kosdaqpi_Test2.log")  # 로그 파일명

# 로깅 설정 (파일 + 콘솔 출력)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, mode='w', encoding='utf-8'),  # 파일 출력
        logging.StreamHandler()                                          # 콘솔 출력
    ]
)

# =============================================================================
# 계좌 설정
# =============================================================================
#계좌 선택.. "VIRTUAL" 는 모의 계좌!
Common.SetChangeMode("VIRTUAL") #REAL or VIRTUAL

# =============================================================================
# 투자 설정
# =============================================================================
##############################################################################
#투자할 종목!
#InvestStockList = [] #테스트할 종목을 아래 예시처럼 직접 판단하여 넣으세요!
# 122630 : KODEX 레버리지 (코스피 상승 추종)
# 252670 : KODEX 200선물인버스2X (코스피 하락 추종)
# 233740 : KODEX 코스닥150레버리지 (코스닥 상승 추종)
# 251340 : KODEX 코스닥150선물인버스 (코스닥 하락 추종)
InvestStockList = ["122630","252670","233740","251340"]
##############################################################################

# =============================================================================
# 투자 파라미터 설정
# =============================================================================
#이렇게 직접 금액을 지정
TotalMoney = 15000000  # 총 투자 금액 (1,500만원)

# 기존 print를 logging.info로 변경 (테스트 금액 출력)
logging.info(f"테스트하는 총 금액: {format(round(TotalMoney), ',')}")

# 수수료 설정 (매수/매도 시 0.15% 수수료 + 세금 + 슬리피지)
fee = 0.0015 

#전략 백테스팅 시작 년도 지정!!!
StartYear = 2017  # 2017년부터 백테스팅 시작

# =============================================================================
# 종목별 성과 추적을 위한 데이터 구조 초기화
# =============================================================================
StockDataList = list()

for stock_code in InvestStockList:
    stock_name = KisKR.GetStockName(stock_code)  # 종목명 조회
    logging.info(f"{stock_name} ({stock_code})")
    
    # 각 종목별 성과 추적용 딕셔너리 생성
    stock_data = dict()
    stock_data['stock_code'] = stock_code      # 종목 코드
    stock_data['stock_name'] = stock_name      # 종목명
    stock_data['try'] = 0                      # 매매 시도 횟수
    stock_data['success'] = 0                  # 성공 횟수
    stock_data['fail'] = 0                     # 실패 횟수
    stock_data['accRev'] = 0                   # 누적 수익률

    StockDataList.append(stock_data)

pprint.pprint(StockDataList)

# =============================================================================
# 유틸리티 함수
# =============================================================================
def GetStockName(stock_code, StockDataList):
    """
    종목 코드로부터 종목명을 반환하는 함수
    
    Args:
        stock_code (str): 종목 코드
        StockDataList (list): 종목 정보 리스트
    
    Returns:
        str: 종목명 (찾지 못하면 종목 코드 반환)
    """
    result_str = stock_code
    for stock_data in StockDataList:
        if stock_code == stock_data['stock_code']:
            result_str = stock_data['stock_name']
            break

    return result_str
    

# =============================================================================
# 데이터 전처리 및 기술적 지표 계산
# =============================================================================
stock_df_list = []  # 각 종목별 데이터프레임을 저장할 리스트

gugan_lenth = 7  # 구간 길이 (고가/저가 계산용)

for stock_code in InvestStockList:
    # KIS API를 통해 OHLCV 데이터 수집 (최근 2200일)
    df = Common.GetOhlcv("KR", stock_code,2200)

    # =============================================================================
    # RSI (Relative Strength Index) 계산
    # =============================================================================
    period = 14  # RSI 계산 기간

    # 가격 변화량 계산
    delta = df["close"].diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0] = 0      # 상승분만 추출
    down[down > 0] = 0  # 하락분만 추출 (절댓값)
    
    # 지수이동평균으로 평균 상승/하락 계산
    _gain = up.ewm(com=(period - 1), min_periods=period).mean()
    _loss = down.abs().ewm(com=(period - 1), min_periods=period).mean()
    RS = _gain / _loss  # 상대강도 계산

    # RSI 계산 (0-100 범위)
    df['RSI'] = pd.Series(100 - (100 / (1 + RS)), name="RSI")

    # 이전 RSI 값들 (매매 조건에서 사용)
    df['prevRSI'] = df['RSI'].shift(1)   # 1일 전 RSI
    df['prevRSI2'] = df['RSI'].shift(2)  # 2일 전 RSI
    
    # =============================================================================
    # 고가/저가 구간 계산 (추가 필터링용)
    # =============================================================================
    df['high_'+str(gugan_lenth)+'_max'] = df['high'].rolling(window=gugan_lenth).max().shift(1)
    df['low_'+str(gugan_lenth)+'_min'] = df['low'].rolling(window=gugan_lenth).min().shift(1)
    
    

    # =============================================================================
    # 이전 데이터 계산 (매매 조건에서 사용)
    # =============================================================================
    # 이전 거래량 데이터
    df['prevVolume'] = df['volume'].shift(1)   # 1일 전 거래량
    df['prevVolume2'] = df['volume'].shift(2)  # 2일 전 거래량
    df['prevVolume3'] = df['volume'].shift(3)  # 3일 전 거래량

    # 이전 가격 데이터
    df['prevClose'] = df['close'].shift(1)     # 1일 전 종가
    df['prevOpen'] = df['open'].shift(1)       # 1일 전 시가

    # 이전 고가/저가 데이터
    df['prevHigh'] = df['high'].shift(1)       # 1일 전 고가
    df['prevHigh2'] = df['high'].shift(2)      # 2일 전 고가
    df['prevLow'] = df['low'].shift(1)         # 1일 전 저가
    df['prevLow2'] = df['low'].shift(2)        # 2일 전 저가

    # =============================================================================
    # 이격도 계산 (가격과 이동평균의 괴리율)
    # =============================================================================
    # 20일 이격도 (현재가 / 20일 이동평균 * 100)
    df['Disparity20'] = df['prevClose'] / df['prevClose'].rolling(window=20).mean() * 100.0
    
    # 11일 이격도 (현재가 / 11일 이동평균 * 100)
    df['Disparity11'] = df['prevClose'] / df['prevClose'].rolling(window=11).mean() * 100.0


    # =============================================================================
    # 이동평균 계산 (매매 조건에서 사용)
    # =============================================================================
    # 단기 이동평균
    df['ma3_before'] = df['close'].rolling(3).mean().shift(1)   # 3일 이동평균
    df['ma6_before'] = df['close'].rolling(6).mean().shift(1)   # 6일 이동평균
    df['ma19_before'] = df['close'].rolling(19).mean().shift(1) # 19일 이동평균

    # 중기 이동평균
    df['ma10_before'] = df['close'].rolling(10).mean().shift(1) # 10일 이동평균
    df['ma20_before'] = df['close'].rolling(20).mean().shift(1) # 20일 이동평균
    df['ma20_before2'] = df['close'].rolling(20).mean().shift(2) # 2일 전 20일 이동평균

    # 장기 이동평균
    df['ma60_before'] = df['close'].rolling(60).mean().shift(1) # 60일 이동평균
    df['ma60_before2'] = df['close'].rolling(60).mean().shift(2) # 2일 전 60일 이동평균
    df['ma120_before'] = df['close'].rolling(120).mean().shift(1) # 120일 이동평균

    # =============================================================================
    # 변화율 이동평균 (횡보장 판단용)
    # =============================================================================
    # 20일 변화율 이동평균
    df['prevChangeMa'] = df['change'].shift(1).rolling(window=20).mean()
    
    # 10일 변화율 이동평균 (단기 횡보장 판단)
    df['prevChangeMa_S'] = df['change'].shift(1).rolling(window=10).mean()

    # =============================================================================
    # 모멘텀 스코어 계산 (10일마다 총 100일 평균모멘텀스코어)
    # =============================================================================
    specific_days = list()

    # 10일, 20일, 30일... 100일 전 가격과 비교
    for i in range(1,11):
        st = i * 10
        specific_days.append(st)

    # 각 기간별 모멘텀 계산 (현재가 > 과거가격이면 1, 아니면 0)
    for day in specific_days:
        column_name = f'Momentum_{day}'
        df[column_name] = (df['prevClose'] > df['close'].shift(day)).astype(int)
        
    # 평균 모멘텀 스코어 (0-1 범위, 높을수록 상승 모멘텀)
    df['Average_Momentum'] = df[[f'Momentum_{day}' for day in specific_days]].sum(axis=1) / 10


    # =============================================================================
    # 단기 모멘텀 스코어 계산 (3일마다 총 30일)
    # =============================================================================
    # Define the list of specific trading days to compare
    specific_days = list()

    # 3일, 6일, 9일... 30일 전 가격과 비교
    for i in range(1,11):
        st = i * 3
        specific_days.append(st)

    # Iterate over the specific trading days and compare the current market price with the corresponding closing prices
    for day in specific_days:
        # Create a column name for each specific trading day
        column_name = f'Momentum_{day}'
        
        # Compare current market price with the closing price of the specific trading day
        df[column_name] = (df['prevClose'] > df['close'].shift(day)).astype(int)

    # Calculate the average momentum score (단기 모멘텀)
    df['Average_Momentum3'] = df[[f'Momentum_{day}' for day in specific_days]].sum(axis=1) / 10

    # =============================================================================
    # 데이터 정리 및 저장
    # =============================================================================
    df.dropna(inplace=True) #데이터 없는건 날린다!

    # 종목별 데이터를 딕셔너리로 저장
    data_dict = {stock_code: df}
    stock_df_list.append(data_dict)
    print("---stock_code---", stock_code , " len ",len(df))
    pprint.pprint(df)





# =============================================================================
# 데이터 결합 및 정렬
# =============================================================================
# Combine the OHLCV data into a single DataFrame
# 모든 종목의 데이터를 하나의 데이터프레임으로 결합
combined_df = pd.concat([list(data_dict.values())[0].assign(stock_code=stock_code) for data_dict in stock_df_list for stock_code in data_dict])

# Sort the combined DataFrame by date
# 날짜순으로 정렬
combined_df.sort_index(inplace=True)

pprint.pprint(combined_df)
print(" len(combined_df) ", len(combined_df))

# =============================================================================
# 백테스팅 변수 초기화
# =============================================================================
# 매매 상태 변수
IsBuy = False #매수 했는지 여부
BUY_PRICE = 0  #매수한 금액! 

# 성과 추적 변수
TryCnt = 0      #매매횟수
SuccesCnt = 0   #익절 숫자
FailCnt = 0     #손절 숫자

# 날짜 추적 변수
IsFirstDateSet = False
FirstDateStr = ""
FirstDateIndex = 0

# 투자 관리 변수
NowInvestCode = ""
InvestMoney = TotalMoney
DivNum = len(InvestStockList)  # 투자 종목 수
MaxInvestCount = 2  # 최대 투자 종목 수 (2개로 제한)
RemainInvestMoney = InvestMoney # 남은 투자금

# 결과 저장 리스트
ResultList = list()      # 최종 결과 저장
TotalMoneyList = list()  # 일별 총 자산 변화
NowInvestList = list()   # 현재 투자중인 종목들

# 손절 관리 변수
IsCut = False   # 손절 발생 여부
IsCutCnt = 0    # 연속 손절 횟수


# =============================================================================
# 메인 백테스팅 루프 시작
# =============================================================================
i = 0
# Iterate over each date
# 각 날짜별로 백테스팅 실행
for date in combined_df.index.unique():
 
    #날짜 정보를 획득
    # 다양한 날짜 형식에 대응
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

    # =============================================================================
    # 현재 날짜의 종목별 데이터 추출
    # =============================================================================
    # 해당 날짜의 모든 종목 중 종가가 높은 순으로 DivNum개 선택
    all_stocks = combined_df.loc[combined_df.index == date].groupby('stock_code')['close'].max().nlargest(DivNum)
    
    # =============================================================================
    # 횡보장 판단 로직
    # =============================================================================
    #횡보장을 정의하기 위한 로직!!
    # https://blog.naver.com/zacra/223225906361 이 포스팅을 정독하세요!!!
    
    # 현재 날짜의 각 종목 데이터 추출
    Kosdaq_Long_Data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == "233740")]  # 코스닥 레버리지
    Kosdaq_Short_Data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == "251340")] # 코스닥 인버스
    Kospi_Long_Data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == "122630")]  # 코스피 레버리지
    Kospi_Short_Data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == "252670")] # 코스피 인버스
    
    # 횡보장 판단: 모든 종목이 같은 방향으로 움직이면 횡보장으로 판단
    IsNoWay = False
    if len(Kosdaq_Long_Data) == 1 and len(Kosdaq_Short_Data) == 1 and len(Kospi_Long_Data) == 1 and len(Kospi_Short_Data) == 1:
        # 코스피 쌍이나 코스닥 쌍이 모두 같은 방향(상승 또는 하락)으로 움직이면 횡보장
        if  (Kospi_Long_Data['prevChangeMa_S'].values[0] > 0 and Kospi_Short_Data['prevChangeMa_S'].values[0] > 0) or (Kospi_Long_Data['prevChangeMa_S'].values[0] < 0 and Kospi_Short_Data['prevChangeMa_S'].values[0] < 0)  or (Kosdaq_Long_Data['prevChangeMa_S'].values[0] > 0 and Kosdaq_Short_Data['prevChangeMa_S'].values[0] > 0) or (Kosdaq_Long_Data['prevChangeMa_S'].values[0] < 0 and Kosdaq_Short_Data['prevChangeMa_S'].values[0] < 0) :
            IsNoWay = True
    #######################################################################################################################################



    # =============================================================================
    # 매도 로직 시작
    # =============================================================================
    i += 1

    # 오늘 매도된 종목들을 추적
    today_sell_code = list()

    # 매도 후 제거할 투자 데이터 리스트
    items_to_remove = list()

    # 코스닥 매도 관련 변수
    Kosdaq_sell_cnt = 0              # 코스닥 매도 발생 횟수
    Kosdaq_sell_money_furture = 0    # 코스닥 매도로 인한 미래 투자금

    # =============================================================================
    # 현재 투자중인 종목들의 매도 조건 체크
    # =============================================================================
    #투자중인 종목들!!
    for investData in NowInvestList:

        stock_code = investData['stock_code'] 
        
        if investData['InvestMoney'] > 0:
            stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)]

            if len(stock_data) == 1:
                
                # =============================================================================
                # 코스닥 종목 매도 전략 (변동성 돌파 전략의 손절)
                # =============================================================================
                ####!!!!코스닥 전략!!!####
                #조건 만족시 매도 한다!
                if stock_code in ["233740","251340"]:
                    
                    # =============================================================================
                    # 현재 가격 정보 추출
                    # =============================================================================
                    NowOpenPrice = stock_data['open'].values[0]      # 현재 시가
                    PrevOpenPrice = stock_data['prevOpen'].values[0] # 전일 시가
                    PrevClosePrice = stock_data['prevClose'].values[0] # 전일 종가

                    # =============================================================================
                    # 손절 비율 설정 (종목별로 다름)
                    # =============================================================================
                    CutRate = 0.4

                    # KODEX 코스닥150선물인버스 (인버스 종목)
                    if stock_code == "251340":
                        CutRate = 0.4  # 고정 0.4

                    # KODEX 코스닥150레버리지 (레버리지 종목)
                    else:
                        # 60일 이동평균 기준으로 손절 비율 조정
                        if PrevClosePrice > stock_data['ma60_before'].values[0]:
                            CutRate = 0.4  # 상승장에서는 0.4
                        else:
                            CutRate = 0.3  # 하락장에서는 0.3 (더 보수적)



                    # =============================================================================
                    # 손절 가격 계산 및 매도 조건 체크
                    # =============================================================================
                    #목표컷 매도가! 시가 - (전일고가 - 전일저가) x CutRate 
                    # 변동성 돌파 전략의 반대: 하향 돌파 시 손절
                    CutPrice = stock_data['open'].values[0] - ((stock_data['prevHigh'].values[0] - stock_data['prevLow'].values[0]) * CutRate)

                    # 기본 매도가격은 현재 시가
                    SellPrice = NowOpenPrice

                    # 매도 실행 여부
                    IsSellGo = False

                    # =============================================================================
                    # 하향 돌파 확인 및 매도 실행
                    # =============================================================================
                    #하향 돌파했다면 매도 고고!!
                    # 손절가가 현재 저가보다 높으면 하향 돌파 발생
                    if CutPrice >= stock_data['low'].values[0] :
                        IsSellGo = True
                        SellPrice = CutPrice  # 손절가로 매도


                    # =============================================================================
                    # 투자금 반영 및 수익률 계산
                    # =============================================================================
                    #매일 매일 투자금 반영!
                    # 첫 번째 매도인지 여부에 따라 투자금 계산 방식이 다름
                    if investData['DolPaCheck'] == False:
                        # 첫 번째 매도: 매수가 대비 수익률로 투자금 조정
                        investData['DolPaCheck'] = True
                        investData['InvestMoney'] = investData['InvestMoney'] *  (1.0 + ((SellPrice - investData['BuyPrice'] ) / investData['BuyPrice'] ))
                    else:
                        # 두 번째 이후 매도: 전일 시가 대비 수익률로 투자금 조정
                        investData['InvestMoney'] = investData['InvestMoney'] *  (1.0 + ((SellPrice - PrevOpenPrice ) / PrevOpenPrice))

                    # =============================================================================
                    # 수익률 계산
                    # =============================================================================
                    #진입(매수)가격 대비 변동률 (수수료 포함)
                    Rate = (SellPrice* (1.0 - fee) - investData['BuyPrice']) / investData['BuyPrice']

                    # 최종 수익률 계산 (수수료 제외)
                    RevenueRate = (Rate - fee)*100.0 #수익률 계산

                    # =============================================================================
                    # 코스닥 매도 실행 및 결과 처리
                    # =============================================================================
                    if IsSellGo == True :

                        Kosdaq_sell_cnt += 1 #코스닥 돌파 매도가 일어난 날!
                        
                        # =============================================================================
                        # 손절 관리 로직
                        # =============================================================================
                        if RevenueRate < 0:
                            IsCut = True      # 손절 발생
                            IsCutCnt += 1     # 연속 손절 횟수 증가
                        else:
                            IsCut = False     # 익절 발생
                            IsCutCnt -= 1     # 연속 손절 횟수 감소
                            if IsCutCnt < 0:
                                IsCutCnt = 0   # 음수가 되지 않도록 보정

                        # =============================================================================
                        # 회수 금액 계산
                        # =============================================================================
                        ReturnMoney = (investData['InvestMoney'] * (1.0 - fee))  #수수료 및 세금, 슬리피지 반영!

                        # 시가가 손절가보다 높으면 미래 투자금에 추가
                        if NowOpenPrice > CutPrice:
                            Kosdaq_sell_money_furture += ReturnMoney

                        # =============================================================================
                        # 성과 통계 업데이트
                        # =============================================================================
                        TryCnt += 1

                        if RevenueRate > 0: #수익률이 0보다 크다면 익절한 셈이다!
                            SuccesCnt += 1
                        else:
                            FailCnt += 1
            
                        #종목별 성과를 기록한다.
                        for stock_data in StockDataList:
                            if stock_code == stock_data['stock_code']:
                                stock_data['try'] += 1
                                if RevenueRate > 0:
                                    stock_data['success'] += 1
                                else:
                                    stock_data['fail'] +=1
                                stock_data['accRev'] += RevenueRate


                        
                        RemainInvestMoney += ReturnMoney
                        investData['InvestMoney'] = 0


                        NowInvestMoney = 0
                        for iData in NowInvestList:
                            NowInvestMoney += iData['InvestMoney']

                        InvestMoney = RemainInvestMoney + NowInvestMoney

                        logging.info(f"{str(date)} {GetStockName(stock_code, StockDataList)} ({stock_code}) {i} >>\n 매도! 매수일:{investData['Date']}, 매수가:{investData['BuyPrice']} , 매수금:{investData['FirstMoney']}, 수익률: {round(RevenueRate,2)} %, 회수금:{round(ReturnMoney,2)}  , 매도가:{SellPrice * (1.0 - fee)}")
                                
                        items_to_remove.append(investData)

                        today_sell_code.append(stock_code)

                # =============================================================================
                # 코스피 종목 매도 전략 (기술적 지표 기반)
                # =============================================================================
                ####!!!!코스피 전략!!!####
                #조건 만족시 매도 한다!
                else:
                    
                    # =============================================================================
                    # 현재 가격 정보 추출
                    # =============================================================================
                    NowOpenPrice = stock_data['open'].values[0]      # 현재 시가
                    PrevOpenPrice = stock_data['prevOpen'].values[0] # 전일 시가
                    PrevClosePrice = stock_data['prevClose'].values[0] # 전일 종가

                    # 기본 매도가격은 현재 시가
                    SellPrice = NowOpenPrice

                    # 매도 실행 여부
                    IsSellGo = False

                    # =============================================================================
                    # 투자금 반영 및 수익률 계산
                    # =============================================================================
                    #매일 매일 투자금 반영!
                    if investData['DolPaCheck'] == False:
                        investData['DolPaCheck'] = True
                        investData['InvestMoney'] = investData['InvestMoney'] *  (1.0 + ((SellPrice - investData['BuyPrice'] ) / investData['BuyPrice'] ))
                    else:
                        investData['InvestMoney'] = investData['InvestMoney'] *  (1.0 + ((SellPrice - PrevOpenPrice ) / PrevOpenPrice))

                    #진입(매수)가격 대비 변동률
                    Rate = (SellPrice* (1.0 - fee) - investData['BuyPrice']) / investData['BuyPrice']

                    RevenueRate = (Rate - fee)*100.0 #수익률 계산
                    
                    # =============================================================================
                    # 코스피 종목별 매도 조건
                    # =============================================================================
                    # KODEX 200선물인버스2X (코스피 하락 추종)
                    if stock_code == "252670":
                        
                        # 11일 이격도가 105% 이상일 때 (과매수 구간)
                        if stock_data['Disparity11'].values[0] > 105:
                            # 3일 이동평균 하향 돌파 시 매도
                            if  PrevClosePrice < stock_data['ma3_before'].values[0]: 
                                IsSellGo = True

                        else:
                            # 일반적인 경우: 6일, 19일 이동평균 모두 하향 돌파 시 매도
                            if PrevClosePrice < stock_data['ma6_before'].values[0] and PrevClosePrice < stock_data['ma19_before'].values[0] : 
                                IsSellGo = True

                    # KODEX 레버리지 (코스피 상승 추종)
                    else:
                        # 평균 거래량 계산 (최근 3일)
                        total_volume = (stock_data['prevVolume'].values[0]+ stock_data['prevVolume2'].values[0] +stock_data['prevVolume3'].values[0]) / 3.0

                        # 20일 이격도
                        Disparity = stock_data['Disparity20'].values[0] 

                        # 매도 조건: 
                        # 1. 저가가 상승하거나 거래량이 평균보다 낮고
                        # 2. 이격도가 98% 미만이거나 105% 초과일 때
                        # → 홀딩 (매도하지 않음)
                        if (stock_data['prevLow2'].values[0] < stock_data['prevLow'].values[0] or stock_data['prevVolume'].values[0] < total_volume) and (Disparity < 98 or Disparity > 105):
                            logging.info("hold..")
                        else:
                            # 그 외의 경우 매도
                            IsSellGo = True
                    

             
             

                    # =============================================================================
                    # 코스피 매도 실행 및 결과 처리
                    # =============================================================================
                    #조건 만족 했다면 매도 고고!
                    if IsSellGo == True :

                        # =============================================================================
                        # 회수 금액 계산
                        # =============================================================================
                        ReturnMoney = (investData['InvestMoney'] * (1.0 - fee))  #수수료 및 세금, 슬리피지 반영!

                        # =============================================================================
                        # 성과 통계 업데이트
                        # =============================================================================
                        TryCnt += 1

                        if RevenueRate > 0: #수익률이 0보다 크다면 익절한 셈이다!
                            SuccesCnt += 1
                        else:
                            FailCnt += 1
            
                        #종목별 성과를 기록한다.
                        for stock_data in StockDataList:
                            if stock_code == stock_data['stock_code']:
                                stock_data['try'] += 1
                                if RevenueRate > 0:
                                    stock_data['success'] += 1
                                else:
                                    stock_data['fail'] +=1
                                stock_data['accRev'] += RevenueRate


                        
                        RemainInvestMoney += ReturnMoney
                        investData['InvestMoney'] = 0


                        #pprint.pprint(NowInvestList)

                        NowInvestMoney = 0
                        for iData in NowInvestList:
                            NowInvestMoney += iData['InvestMoney']

                        InvestMoney = RemainInvestMoney + NowInvestMoney

                        logging.info(f"{str(date)} {GetStockName(stock_code, StockDataList)} ({stock_code}) {i} >>\n 매도! 매수일:{investData['Date']}, 매수가:{investData['BuyPrice']} , 매수금:{investData['FirstMoney']}, 수익률: {round(RevenueRate,2)} %, 회수금:{round(ReturnMoney,2)}  , 매도가:{SellPrice * (1.0 - fee)}")
                                
                        items_to_remove.append(investData)

                        today_sell_code.append(stock_code)


    # =============================================================================
    # 매도 완료 후 투자 리스트 정리
    # =============================================================================
    #리스트에서 제거
    for item in items_to_remove:
        NowInvestList.remove(item)

    # =============================================================================
    # 코스피 종목 매수 로직
    # =============================================================================
    #최대 2개 종목만 투자 가능함! 코스피 매수 조건 체크!
    #즉 코스피 먼저 매수 여부를 판단하여 매수한다!
    if len(NowInvestList) < MaxInvestCount and int(date_object.strftime("%Y")) >= StartYear:

        if IsFirstDateSet == False:
            FirstDateStr = str(date)
            FirstDateIndex = i-1
            IsFirstDateSet = True


        for stock_code in all_stocks.index:

            IsAlReadyInvest = False
            for investData in NowInvestList:
                if stock_code == investData['stock_code']: 
                    IsAlReadyInvest = True
                    break    
            
            if stock_code not in today_sell_code and IsAlReadyInvest == False:

                # =============================================================================
                # 현재 종목 데이터 추출
                # =============================================================================
                stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)]
                
                # =============================================================================
                # 코스피 종목 매수 전략 (기술적 지표 기반)
                # =============================================================================
                ####!!!!코스피 전략!!!####
                if stock_code in ["122630","252670"]:
                    
                    # =============================================================================
                    # 기본 변수 설정
                    # =============================================================================
                    PrevClosePrice = stock_data['prevClose'].values[0]  # 전일 종가
                    DolPaPrice = stock_data['open'].values[0]          # 매수 가격 (시가)
                    IsBuyGo = False                                    # 매수 실행 여부
                    
                    # =============================================================================
                    # KODEX 200선물인버스2X 매수 조건 (코스피 하락 추종)
                    # =============================================================================
                    # KODEX 200선물인버스2X
                    if stock_code == "252670":
                        # 기본 조건: 모든 단기 이동평균 상향 돌파 + RSI 조건
                        if PrevClosePrice > stock_data['ma3_before'].values[0]  and PrevClosePrice > stock_data['ma6_before'].values[0]  and PrevClosePrice > stock_data['ma19_before'].values[0] and stock_data['prevRSI'].values[0] < 70 and stock_data['prevRSI2'].values[0] < stock_data['prevRSI'].values[0]:
                            # 추가 조건: 거래량 증가 + 저가 상승 + 장기 이동평균 상향 + 단기 이동평균 정렬
                            if (stock_data['prevVolume2'].values[0] < stock_data['prevVolume'].values[0]) and (stock_data['prevLow2'].values[0] < stock_data['prevLow'].values[0]) and PrevClosePrice > stock_data['ma60_before'].values[0] and stock_data['ma60_before2'].values[0] < stock_data['ma60_before'].values[0]  and stock_data['ma3_before'].values[0]  > stock_data['ma6_before'].values[0]  > stock_data['ma19_before'].values[0]  :
                                IsBuyGo = True

                    # =============================================================================
                    # KODEX 레버리지 매수 조건 (코스피 상승 추종)
                    # =============================================================================
                    # KODEX 레버리지
                    else:
                        Disparity = stock_data['Disparity20'].values[0] 
                        
                        # 매수 조건: 저가 상승 + 이격도 조건 + RSI 조건
                        if (stock_data['prevLow2'].values[0] < stock_data['prevLow'].values[0]) and (Disparity < 98 or Disparity > 106) and stock_data['prevRSI'].values[0] < 80 :
                            IsBuyGo = True

        
                    #조건을 만족했다면 매수 고고!
                    if IsBuyGo == True :



                        Rate = 1.0


                        # =============================================================================
                        # 새로운 투자 비율 시스템 적용
                        # =============================================================================
                        #InvestGoMoney = (InvestMoney / len(InvestStockList)) * Rate
                        InvestGoMoney = 0

                        # 현재 투자중인 종목 수 계산
                        current_invest_count = len(NowInvestList)
                        
                        # 새로운 투자 비율 시스템
                        if IsNoWay == True:
                            # 횡보장인 경우: 균등 분배
                            InvestGoMoney = ((RemainInvestMoney - Kosdaq_sell_money_furture) / len(InvestStockList))
                        else:
                            # 새로운 투자 비율 로직
                            if current_invest_count == 0:
                                # 첫 번째 종목: 100% 투자
                                InvestGoMoney = (RemainInvestMoney - Kosdaq_sell_money_furture)
                            elif current_invest_count == 1:
                                # 두 번째 종목: 기존 종목 매도 후 50:50 분배
                                # 기존 투자금의 절반을 매도하고 새로운 종목에 투자
                                existing_invest = NowInvestList[0]['InvestMoney']
                                sell_amount = existing_invest * 0.5  # 기존 투자금의 절반 매도
                                
                                # 기존 투자금 조정
                                NowInvestList[0]['InvestMoney'] = existing_invest * 0.5
                                RemainInvestMoney += sell_amount * (1.0 - fee)  # 수수료 차감 후 현금 추가
                                
                                new_total = (RemainInvestMoney - Kosdaq_sell_money_furture)
                                InvestGoMoney = new_total * 0.5  # 새로운 종목에 50% 투자
                                
                                logging.info(f"기존 투자금 절반 매도: {GetStockName(NowInvestList[0]['stock_code'], StockDataList)} -> {round(sell_amount,2)}")
                                
                            else:
                                # 2개 이상인 경우: 더 이상 투자하지 않음
                                InvestGoMoney = 0
                    
                   
            


                        if InvestGoMoney > 0:


                            BuyAmt = int(InvestGoMoney /  DolPaPrice) #매수 가능 수량을 구한다!

                            NowFee = (BuyAmt*DolPaPrice) * fee



                            #매수해야 되는데 남은돈이 부족하다면 수량을 하나씩 감소시켜 만족할 때 매수한다!!
                            while (RemainInvestMoney - Kosdaq_sell_money_furture)  < (BuyAmt*DolPaPrice) + NowFee:
                                if (RemainInvestMoney - Kosdaq_sell_money_furture)  > DolPaPrice:
                                    BuyAmt -= 1
                                    NowFee = (BuyAmt*DolPaPrice) * fee
                                else:
                                    break
                            
                            if BuyAmt > 0:



                                RealInvestMoney = (BuyAmt*DolPaPrice) #실제 들어간 투자금

                                RemainInvestMoney -= (BuyAmt*DolPaPrice) #남은 투자금!
                                RemainInvestMoney -= NowFee


                                InvestData = dict()

                                InvestData['stock_code'] = stock_code
                                InvestData['InvestMoney'] = RealInvestMoney
                                InvestData['FirstMoney'] = RealInvestMoney
                                InvestData['BuyPrice'] = DolPaPrice
                                InvestData['DolPaCheck'] = False
                                InvestData['Date'] = str(date)



                                NowInvestList.append(InvestData)


                                NowInvestMoney = 0
                                for iData in NowInvestList:
                                    NowInvestMoney += iData['InvestMoney']

                                InvestMoney = RemainInvestMoney + NowInvestMoney


                                logging.info(f"{str(date)} {GetStockName(stock_code, StockDataList)} ({stock_code}) {i} >>\n 매수! ,매수금액:{round(RealInvestMoney,2)} , 돌파가격:{DolPaPrice}, 시가:{stock_data['open'].values[0]}")

             
             

    # =============================================================================
    # 코스닥 종목 매수 로직 (변동성 돌파 전략)
    # =============================================================================
    #최대 2개 종목만 투자 가능함! 코스닥 매수 조건 체크!
    if len(NowInvestList) < MaxInvestCount and int(date_object.strftime("%Y")) >= StartYear:

        for stock_code in all_stocks.index:

            # =============================================================================
            # 이미 투자중인 종목인지 확인
            # =============================================================================
            IsAlReadyInvest = False
            for investData in NowInvestList:
                if stock_code == investData['stock_code']: 
                    IsAlReadyInvest = True
                    break    
            
            # =============================================================================
            # 매수 조건 체크 (오늘 매도되지 않았고, 현재 투자중이 아닌 종목)
            # =============================================================================
            if stock_code not in today_sell_code and IsAlReadyInvest == False:

                #코스닥 매도가 일어났는데 현재 또 코스피에 보유중인 종목이 있다면 코스닥 매도는 장중 매도니깐 이때는 매도하지 않음!
                #if Kosdaq_sell_cnt == 1 and len(NowInvestList) == 1:
                #    continue

                # =============================================================================
                # 현재 종목 데이터 추출
                # =============================================================================
                stock_data = combined_df[(combined_df.index == date) & (combined_df['stock_code'] == stock_code)]
                
                # =============================================================================
                # 코스닥 종목 매수 전략 (변동성 돌파 전략)
                # =============================================================================
                ####!!!!코스닥 전략!!!####
                if stock_code in ["233740","251340"]:
                    

                    # =============================================================================
                    # 기본 변수 설정
                    # =============================================================================
                    PrevClosePrice = stock_data['prevClose'].values[0]  # 전일 종가

                    # 기본 돌파 비율 설정
                    DolpaRate = 0.4

                    # =============================================================================
                    # 종목별 돌파 비율 설정
                    # =============================================================================
                    #KODEX 코스닥150선물인버스 (인버스 종목)
                    if stock_code == "251340":
                        DolpaRate = 0.4  # 고정 0.4

                    #KODEX 코스닥150레버리지 (레버리지 종목)
                    else: 
                        # 60일 이동평균 기준으로 돌파 비율 조정
                        if PrevClosePrice > stock_data['ma60_before'].values[0]:
                            DolpaRate = 0.3  # 상승장에서는 0.3 (더 보수적)
                        else:
                            DolpaRate = 0.4  # 하락장에서는 0.4

                    # =============================================================================
                    # 갭 상승/하락을 이용한 돌파값 조절
                    # =============================================================================
                    ##########################################################################
                    #갭 상승 하락을 이용한 돌파값 조절!
                    # https://blog.naver.com/zacra/223277173514 이 포스팅을 체크!!!!
                    ##########################################################################
                    
                    # 갭 크기 계산 (시가와 전일 종가의 차이율)
                    Gap = ((abs(stock_data['open'].values[0] - PrevClosePrice) / PrevClosePrice)) * 100.0

                    # 갭에 따른 조절 비율 계산
                    GapSt = (Gap*0.025)

                    # 조절 비율 범위 제한
                    if GapSt > 1.0:
                        GapSt = 1.0
                    if GapSt < 0:
                        GapSt = 0.1

                    # 갭 상승 시 (시가 > 전일 종가): 돌파 비율 증가
                    if PrevClosePrice > stock_data['open'].values[0] and Gap >= 3.0:
                        DolpaRate *= (1.0 + GapSt)

                    # 갭 하락 시 (시가 < 전일 종가): 돌파 비율 감소
                    if PrevClosePrice < stock_data['open'].values[0] and Gap >= 3.0:
                        DolpaRate *= (1.0 - GapSt)


                    # =============================================================================
                    # 변동성 돌파 가격 계산
                    # =============================================================================
                    #변동성 돌파 시가 + (전일고가-전일저가)*DolpaRate
                    DolPaPrice = stock_data['open'].values[0] + ((stock_data['prevHigh'].values[0] - stock_data['prevLow'].values[0]) * DolpaRate)

                    # 매수 실행 여부
                    IsBuyGo = False

                    # 돌파 비율 계산 (백분율)
                    DolPaRate = (DolPaPrice - stock_data['open'].values[0]) / stock_data['open'].values[0] * 100

                    # =============================================================================
                    # 돌파 확인 및 매수 조건 체크
                    # =============================================================================
                    #돌파 했다면 매수 고???
                    # 돌파가가 현재 고가보다 낮으면 돌파 발생
                    if DolPaPrice <= stock_data['high'].values[0]  :

                        IsBuyGo = True

                        # =============================================================================
                        # 추가 필터링 로직 (매수 조건 만족 시에도 추가 검증)
                        # =============================================================================
                        #추가 필터를 거쳐 아래 조건을 만족하면 매수하지 않는다!

                        # =============================================================================
                        # 종목별 추가 필터
                        # =============================================================================
                        #KODEX 코스닥150선물인버스 (인버스 종목)
                        if stock_code == "251340":
                            # 전일 종가가 20일 이동평균 이하면 매수하지 않음
                            if stock_data['prevClose'].values[0] <= stock_data['ma20_before'].values[0]:
                                IsBuyGo = False 
        
                        #KODEX 코스닥150레버리지 (레버리지 종목)
                        else: 
                            # 전일 저가가 시가보다 높고, 전일 종가가 10일 이동평균 이하면 매수하지 않음
                            if stock_data['prevLow'].values[0] > stock_data['open'].values[0] and stock_data['prevClose'].values[0] < stock_data['ma10_before'].values[0]:
                                IsBuyGo = False 

                        # =============================================================================
                        # 추가 개선 로직 (이동평균 정렬 및 가격 구간 필터)
                        # =============================================================================
                        # 추가 개선 로직 https://blog.naver.com/zacra/223326173552 이 포스팅 참고!!!!
                        
                        # 이동평균 정렬 확인 (상승 추세)
                        IsJung = False    
                        if stock_data['ma10_before'].values[0] > stock_data['ma20_before'].values[0] > stock_data['ma60_before'].values[0] > stock_data['ma120_before'].values[0]:
                            IsJung = True
                            
                        # 이동평균이 정렬되지 않은 경우 추가 필터 적용
                        if IsJung == False:
                            # 최근 구간의 고가/저가 계산
                            high_price = stock_data['high_'+str(gugan_lenth)+'_max'].values[0] 
                            low_price =  stock_data['low_'+str(gugan_lenth)+'_min'].values[0] 
                            
                            # 구간을 4등분하여 상위 25% 구간 계산
                            Gap = (high_price - low_price) / 4
                            
                            # 상위 25% 구간의 최대 가격
                            MaximunPrice = low_price + Gap * 3.0
                            
                            # 시가가 상위 25% 구간을 넘으면 매수하지 않음 (과매수 구간)
                            if stock_data['open'].values[0] > MaximunPrice:
                                IsBuyGo = False
            
                        
                            
                            
                    # =============================================================================
                    # 코스닥 매수 실행 및 투자 비중 결정
                    # =============================================================================
                    if IsBuyGo == True :
     
                        # =============================================================================
                        # 기본 투자 비율 설정
                        # =============================================================================
                        Rate = 1.0

                        # =============================================================================
                        # 모멘텀 스코어를 통한 비중 조절!
                        # =============================================================================
                        #모멘텀 스코어를 통한 비중 조절!
                        if len(Kosdaq_Long_Data) == 1 and len(Kosdaq_Short_Data) == 1:
                        
                            # 모멘텀 스코어 비교 (레버리지 vs 인버스)
                            IsLongStrong = False
                            
                            if Kosdaq_Long_Data['Average_Momentum'].values[0] > Kosdaq_Short_Data['Average_Momentum'].values[0]:
                                IsLongStrong = True
                                
                            # 변화율 이동평균 비교
                            IsLongStrong2 = False
                            
                            if Kosdaq_Long_Data['prevChangeMa'].values[0] > Kosdaq_Short_Data['prevChangeMa'].values[0]:
                                IsLongStrong2 = True
                                
                            # =============================================================================
                            # 모멘텀 기반 비중 조절 로직
                            # =============================================================================
                            # 레버리지가 강할 때
                            if IsLongStrong == True and IsLongStrong2 == True:
                                
                                if stock_code == "233740":  # 레버리지 종목
                                    Rate = 1.3  # 비중 증가
                                else:  # 인버스 종목
                                    Rate = 0.7  # 비중 감소
                                    
                            # 인버스가 강할 때
                            elif IsLongStrong == False and IsLongStrong2 == False:
                                    
                                if stock_code == "233740":  # 레버리지 종목
                                    Rate = 0.7  # 비중 감소
                                else:  # 인버스 종목
                                    Rate = 1.3  # 비중 증가
                                    
                        # =============================================================================
                        # 투자 금액 계산
                        # =============================================================================
                        #InvestGoMoney = (InvestMoney / len(InvestStockList)) * Rate
                        InvestGoMoney = 0
                        
                        # =============================================================================
                        # 시스템 손절 관련 투자 비율 조절
                        # =============================================================================
                        #############################################################
                        #시스템 손절(?) 관련
                        # https://blog.naver.com/zacra/223225906361 이 포스팅 체크!!!
                        #############################################################
                        AdjustRate = 1.0

                        # 연속 손절이 2회 이상 발생한 경우
                        if IsCut == True and IsCutCnt >= 2:
                            
                            # 전일 하락장이고 고가가 상승한 경우
                            if stock_data['prevOpen'].values[0] > stock_data['prevClose'].values[0] and stock_data['prevHigh2'].values[0] > stock_data['prevHigh'].values[0]:
                                
                                # 연속 손절이 4회 이상이면 더 보수적으로 조절
                                if IsCutCnt >= 4:
                                    AdjustRate = stock_data['Average_Momentum3'].values[0] * 0.5
                                    
                                else:
                                    AdjustRate =  stock_data['Average_Momentum3'].values[0]

                        # =============================================================================
                        # 새로운 투자 비율 시스템 적용 (코스닥 종목)
                        # =============================================================================
                        # 횡보장인 경우
                        if IsNoWay == True:
                            InvestGoMoney = ((RemainInvestMoney - Kosdaq_sell_money_furture) / len(InvestStockList)) * AdjustRate
                        else:
                            # 현재 투자중인 종목 수 계산
                            current_invest_count = len(NowInvestList)
                            
                            # 새로운 투자 비율 로직
                            if current_invest_count == 0:
                                # 첫 번째 종목: 100% 투자
                                InvestGoMoney = (RemainInvestMoney - Kosdaq_sell_money_furture) * AdjustRate
                            elif current_invest_count == 1:
                                # 두 번째 종목: 기존 종목 매도 후 50:50 분배
                                existing_invest = NowInvestList[0]['InvestMoney']
                                sell_amount = existing_invest * 0.5  # 기존 투자금의 절반 매도
                                
                                # 기존 투자금 조정
                                NowInvestList[0]['InvestMoney'] = existing_invest * 0.5
                                RemainInvestMoney += sell_amount * (1.0 - fee)  # 수수료 차감 후 현금 추가
                                
                                new_total = (RemainInvestMoney - Kosdaq_sell_money_furture)
                                InvestGoMoney = new_total * 0.5 * AdjustRate  # 새로운 종목에 50% 투자
                                
                                logging.info(f"기존 투자금 절반 매도: {GetStockName(NowInvestList[0]['stock_code'], StockDataList)} -> {round(sell_amount,2)}")
                                
                            else:
                                # 2개 이상인 경우: 더 이상 투자하지 않음
                                InvestGoMoney = 0
                    
                   
                        # =============================================================================
                        # 매수 실행 및 투자 데이터 생성
                        # =============================================================================
                        if InvestGoMoney > 0 and AdjustRate > 0:

                            # =============================================================================
                            # 매수 수량 계산
                            # =============================================================================
                            BuyAmt = int(InvestGoMoney /  DolPaPrice) #매수 가능 수량을 구한다!

                            NowFee = (BuyAmt*DolPaPrice) * fee

                            # =============================================================================
                            # 자금 부족 시 수량 조정
                            # =============================================================================
                            #매수해야 되는데 남은돈이 부족하다면 수량을 하나씩 감소시켜 만족할 때 매수한다!!
                            while (RemainInvestMoney - Kosdaq_sell_money_furture)  < (BuyAmt*DolPaPrice) + NowFee:
                                if (RemainInvestMoney - Kosdaq_sell_money_furture)  > DolPaPrice:
                                    BuyAmt -= 1
                                    NowFee = (BuyAmt*DolPaPrice) * fee
                                else:
                                    break
                            
                            # =============================================================================
                            # 매수 실행 및 투자 데이터 생성
                            # =============================================================================
                            if BuyAmt > 0:

                                # 실제 투자 금액 계산
                                RealInvestMoney = (BuyAmt*DolPaPrice) #실제 들어간 투자금

                                # 남은 투자금 차감
                                RemainInvestMoney -= (BuyAmt*DolPaPrice) #남은 투자금!
                                RemainInvestMoney -= NowFee

                                # =============================================================================
                                # 투자 데이터 생성
                                # =============================================================================
                                InvestData = dict()

                                InvestData['stock_code'] = stock_code      # 종목 코드
                                InvestData['InvestMoney'] = RealInvestMoney # 현재 투자 금액
                                InvestData['FirstMoney'] = RealInvestMoney  # 최초 투자 금액
                                InvestData['BuyPrice'] = DolPaPrice        # 매수 가격
                                InvestData['DolPaCheck'] = False           # 첫 매도 여부
                                InvestData['Date'] = str(date)             # 매수 날짜

                                # 투자 리스트에 추가
                                NowInvestList.append(InvestData)

                                # =============================================================================
                                # 총 투자 금액 업데이트
                                # =============================================================================
                                NowInvestMoney = 0
                                for iData in NowInvestList:
                                    NowInvestMoney += iData['InvestMoney']

                                InvestMoney = RemainInvestMoney + NowInvestMoney

                                # 매수 로그 출력
                                logging.info(f"{str(date)} {GetStockName(stock_code, StockDataList)} ({stock_code}) {i} >>\n 매수! ,매수금액:{round(RealInvestMoney,2)} , 돌파가격:{DolPaPrice}, 시가:{stock_data['open'].values[0]}")

        

       


    
    # =============================================================================
    # 일별 포트폴리오 상태 업데이트
    # =============================================================================
    # 현재 투자중인 종목들의 총 투자금 계산
    NowInvestMoney = 0

    for iData in NowInvestList:
        NowInvestMoney += iData['InvestMoney']

    # 총 자산 계산 (현금 + 투자금)
    InvestMoney = RemainInvestMoney + NowInvestMoney

    # =============================================================================
    # 투자 현황 로그 출력
    # =============================================================================
    InvestCoinListStr = ""
    #print("\n\n------------------------------------")
    for iData in NowInvestList:
        InvestCoinListStr += GetStockName(iData['stock_code'], StockDataList)  + " "

   # print("------------------------------------\n\n")

    # 투자 현황 로그 출력
    logging.info(f"{InvestCoinListStr} ---> 투자개수 : {len(NowInvestList)}")
    pprint.pprint(NowInvestList)
    logging.info(f"잔고:{str(InvestMoney)} = {str(RemainInvestMoney)} + {str(NowInvestMoney)}\n" )
    
    # 일별 총 자산 변화 기록
    TotalMoneyList.append(InvestMoney)

    #####################################################
    #####################################################
    #####################################################
    #'''
    
   


# =============================================================================
# 백테스팅 결과 분석 및 정리
# =============================================================================
#결과 정리 및 데이터 만들기!!
if len(TotalMoneyList) > 0:

    logging.info(f"TotalMoneyList -> {len(TotalMoneyList)}")

    # =============================================================================
    # 결과 데이터 구조 생성
    # =============================================================================
    resultData = dict()

    # Create the result DataFrame with matching shapes
    # 일별 총 자산 변화를 데이터프레임으로 변환
    result_df = pd.DataFrame({"Total_Money": TotalMoneyList}, index=combined_df.index.unique())

    # =============================================================================
    # 성과 지표 계산
    # =============================================================================
    result_df['Ror'] = np.nan_to_num(result_df['Total_Money'].pct_change()) + 1        # 일별 수익률
    result_df['Cum_Ror'] = result_df['Ror'].cumprod()                                   # 누적 수익률
    result_df['Highwatermark'] = result_df['Cum_Ror'].cummax()                          # 최고점
    result_df['Drawdown'] = (result_df['Cum_Ror'] / result_df['Highwatermark']) - 1    # 드로우다운
    result_df['MaxDrawdown'] = result_df['Drawdown'].cummin()                           # 최대 드로우다운

    logging.info(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    pprint.pprint(result_df)
    logging.info(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

    # =============================================================================
    # 최종 결과 데이터 정리
    # =============================================================================
    resultData['DateStr'] = str(FirstDateStr) + " ~ " + str(result_df.iloc[-1].name)    # 백테스팅 기간

    resultData['OriMoney'] = result_df['Total_Money'].iloc[0]                           # 초기 자산
    resultData['FinalMoney'] = result_df['Total_Money'].iloc[-1]                        # 최종 자산
    resultData['RevenueRate'] = ((result_df['Cum_Ror'].iloc[-1] -1.0)* 100.0)          # 총 수익률

    resultData['MDD'] = result_df['MaxDrawdown'].min() * 100.0                          # 최대 드로우다운

    resultData['TryCnt'] = TryCnt                                                        # 총 매매 횟수
    resultData['SuccesCnt'] = SuccesCnt                                                  # 성공 횟수
    resultData['FailCnt'] = FailCnt                                                      # 실패 횟수

    
    ResultList.append(resultData)
    
    
    result_df.index = pd.to_datetime(result_df.index)

    #'''
    # charts 폴더 생성
    charts_dir = os.path.join(script_dir, "charts")
    if not os.path.exists(charts_dir):
        os.makedirs(charts_dir)
    
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

    # Save the plot to charts folder (덮어쓰기)
    plt.tight_layout()
    chart_filename = os.path.join(charts_dir, "Kosdaqpi_Test2.png")
    plt.savefig(chart_filename, dpi=300, bbox_inches='tight')
    logging.info(f"차트가 저장되었습니다: {chart_filename}")
    plt.show()
        
    #'''
    
    


    for idx, row in result_df.iterrows():
        logging.info(f"{idx}  {row['Total_Money']}  {row['Cum_Ror']}")
        



#데이터를 보기좋게 프린트 해주는 로직!
logging.info("\n\n--------------------")


for result in ResultList:

    logging.info(f"--->>> {result['DateStr'].replace('00:00:00','')} <<<---")

    for stock_data in StockDataList:
        logging.info(f"{stock_data['stock_name']} ({stock_data['stock_code']})")
        if stock_data['try'] > 0:
            logging.info(f"성공: {stock_data['success']} 실패: {stock_data['fail']}, -> 승률: {round(stock_data['success']/stock_data['try'] * 100.0,2)} %")
            logging.info(f"매매당 평균 수익률: {round(stock_data['accRev']/ stock_data['try'],2)}")
        logging.info("")

    logging.info("---------- 총 결과 ----------")
    logging.info(f"최초 금액: {format(int(round(TotalMoney,0)), ',')} 최종 금액: {format(int(round(result['FinalMoney'],0)), ',')} \n수익률: {round(((round(result['FinalMoney'],2) - round(TotalMoney,2) ) / round(TotalMoney,2) ) * 100,2)}% MDD: {round(result['MDD'],2)}%")
    if result['TryCnt'] > 0:
        logging.info(f"성공: {result['SuccesCnt']} 실패: {result['FailCnt']}, -> 승률: {round(result['SuccesCnt']/result['TryCnt'] * 100.0,2)} %")

    logging.info("------------------------------")
    logging.info("####################################")
