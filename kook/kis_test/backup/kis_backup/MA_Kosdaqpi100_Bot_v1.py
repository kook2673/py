# -*- coding: utf-8 -*-
"""
=============================================================================
이동평균선 기반 주식 투자 전략 봇 v4.0
=============================================================================

📊 [전략 개요]
- 코스피100, 코스닥100 종목 중 선별된 종목에 투자하는 이동평균선 기반 전략
- 모멘텀 지표와 이동평균선 교차를 활용한 매수/매도 신호 생성
- 최대 30개 종목에 분산 투자하여 리스크 관리

📈 [주요 기능]
1. 자산 정보를 portfolio_config.json에서 동적으로 로딩
2. 코스피100, 코스닥100 총 200개 종목 중 최대 30개 선별 투자
3. Average_Momentum 지표를 활용한 종목 필터링 (0.4 이하 시 제외)
4. 우선순위 점수 기반 종목 선별:
   - 이동평균선 기울기 (가중치: 1000) - 5일, 20일 이동평균의 기울기
   - 가격 대비 이동평균선 위치 (가중치: 100) - 현재 가격이 20일 이동평균 대비 위치
   - 최근 가격 변동성 (가중치: 50) - 전일 대비 가격 변화율

🔄 [매매 신호]
- 매수: 단기 이동평균 > 장기 이동평균 교차 + 평균모멘텀 = 1.0
- 매도: 단기 이동평균 < 장기 이동평균 교차 시 부분 매도

⚠️ [실행 조건 및 주의사항]
- 본 코드는 수동 실행 방식으로, 사용자가 직접 실행해야 함
- 자동 반복 실행을 위해서는 별도 스케줄러 구성 필요
- 실제 매매는 ENABLE_ORDER_EXECUTION = True 설정 시에만 실행됨

🛠️ [설정 방법]
1. ENABLE_ORDER_EXECUTION 값을 True로 변경
2. portfolio_config.json에서 투자 비중 및 종목 설정
3. 제외할 종목 리스트 설정 (선택사항)
4. 서버 환경에서 스케줄러 등록

📚 [관련 자료]
- 전략 상세 설명: https://blog.naver.com/zacra/223597500754

=============================================================================
"""
# =============================================================================
# 필수 라이브러리 임포트
# =============================================================================
import KIS_Common as Common                 # KIS API 공통 모듈
import pandas as pd                         # 데이터 분석 및 처리
import KIS_API_Helper_KR as KisKR          # 한국투자증권 API 헬퍼
import time                                 # 시간 처리
import json                                 # JSON 파일 처리
import pprint                              # 예쁜 출력 포맷
import sys                                 # 시스템 관련 기능
import os                                  # 운영체제 인터페이스
import logging                             # 로깅 기능
from datetime import datetime              # 날짜/시간 처리

# 상위 디렉토리(kook)를 모듈 경로에 추가한 뒤 텔레그램 모듈 임포트
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)
import telegram_sender as telegram         # 텔레그램 메시지 전송

from portfolio_manager import PortfolioManager    # 포트폴리오 관리 모듈

# =============================================================================
# 기본 설정
# =============================================================================
# 계좌 모드 설정 - "REAL": 실제 계좌, "VIRTUAL": 모의 계좌
Common.SetChangeMode("REAL")

# =============================================================================
# 로깅 시스템 설정
# =============================================================================
# 스크립트 디렉토리 경로 설정
script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)  # logs 디렉토리가 없으면 생성

# 로깅 설정: 파일과 콘솔 양쪽에 로그 출력
logging.basicConfig(
    level=logging.INFO,                   # INFO 레벨 이상의 로그만 출력
    format='%(asctime)s - %(levelname)s - %(message)s',  # 로그 포맷
    handlers=[
        # 파일 핸들러: 로그를 파일에 저장 (UTF-8 인코딩, 추가 모드)
        logging.FileHandler(os.path.join(logs_dir, 'MA_Kosdaqpi100_Bot_v1.log'), mode='a', encoding='utf-8'),
        # 스트림 핸들러: 로그를 콘솔에 출력
        logging.StreamHandler()
    ]
)

# 봇 기본 정보
BOT_NAME = "MA_Kosdaqpi100_Bot_v1"                        # 봇 이름
PortfolioName = "코스피,코스닥100 이동평균자산배분전략_KR"    # 포트폴리오 이름

# 주말 가드: 토(5)/일(6)에는 실행하지 않고 즉시 종료 (텔레그램 전송 없음)
now = datetime.now()
if now.weekday() >= 5:
    msg = f"{PortfolioName}({now.strftime('%Y-%m-%d')})\n주말(토/일)에는 실행하지 않습니다."
    logging.info(msg)
    sys.exit(0)

# =============================================================================
# 매매 실행 설정
# =============================================================================
"""
⚠️ 주요 안전 설정

ENABLE_ORDER_EXECUTION 값을 True로 변경할 경우, 실제 매매가 실행됩니다.
- 기본값: False (매매 비활성화)
- 실제 매매를 원할 경우 사용자가 직접 True로 변경해야 함
- 변경 전 반드시 포트폴리오 설정을 확인하세요!
"""
ENABLE_ORDER_EXECUTION = True  # 주문 실행 여부 설정

# =============================================================================
# 설정 파일 및 기본 변수
# =============================================================================
# 설정 파일 경로 설정
config_file_path = os.path.join(script_dir, 'portfolio_config.json')

# 포트폴리오 매니저 인스턴스 생성
portfolio_manager = PortfolioManager()

# =============================================================================
# 시장 및 계좌 정보 조회
# =============================================================================
# 리밸런싱 실행 여부 플래그
Is_Rebalance_Go = False

# 한국 주식 시장 개장 여부 확인
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

# 현재 계좌 잔고 정보 조회
Balance = KisKR.GetBalance()

# =============================================================================
# 전역 변수 선언
# =============================================================================
# 현재 투자중인 종목 코드 리스트 (부분 매도 시 기준이 됨)
StockInvestList = None

# 포트폴리오 관련 리스트들
MyPortfolioList = list()        # 내 포트폴리오 종목 정보
MyStockList = list()            # 현재 보유 주식 리스트
TodayRebalanceList = list()     # 오늘 리밸런싱 대상 종목 리스트
potential_buy_stocks = list()   # 매수 후보 종목 리스트

# 투자 금액 관련 변수
TotalMoney = 0                  # 포트폴리오에 할당된 총 투자 금액

def main():
    """
    메인 실행 함수
    
    주요 기능:
    1. 설정 파일 로딩 및 검증
    2. 투자 종목 필터링
    3. 포트폴리오 데이터 생성
    4. 리밸런싱 로직 실행
    5. 매매 주문 실행 (설정에 따라)
    """
    # 전역 변수 선언
    global StockInvestList, MyPortfolioList, MyStockList, TodayRebalanceList, potential_buy_stocks, TotalMoney, Is_Rebalance_Go
    
    # =========================================================================
    # 1. 설정 파일 로딩 및 검증
    # =========================================================================
    try:
        # portfolio_config.json 파일 읽기
        with open(config_file_path, 'r', encoding='utf-8') as f:
            portfolio_config = json.load(f)
            bot_config = portfolio_config['bots']['MA_Kosdaqpi100_Bot_v1']
            
        # 일별, 월별, 연별 판매수익 초기화
        initialize_period_profits()
        
        # 투자 비중 설정 로딩
        InvestRate = bot_config['allocation_rate']
        logging.info(f"📊 투자 비중: {InvestRate * 100:.1f}%")
        
        # 매도 비중 설정 로딩
        FixRate = bot_config['fix_rate']        # 고정 보유 비중
        DynamicRate = bot_config['dynamic_rate'] # 동적 보유 비중 (모멘텀 기반)
        logging.info(f"📊 FixRate: {FixRate * 100:.1f}%, DynamicRate: {DynamicRate * 100:.1f}%")
        
        # 투자 대상 종목 리스트 로딩
        InvestStockList = bot_config['invest_stock_list']
        
        # 제외할 종목 리스트 로딩 및 처리
        exclude_stock_list = bot_config.get('exclude_stock_list', [])
        exclude_stock_codes = []
        for exclude_stock in exclude_stock_list:
            stock_code = list(exclude_stock.keys())[0]
            exclude_stock_codes.append(stock_code)
        logging.info(f"🚫 제외할 종목 목록: {exclude_stock_codes}")
            
    except Exception as e:
        error_msg = f"portfolio_config.json 파일 읽기 실패: {e}"
        logging.error(error_msg)
        telegram.send(f"{error_msg}\n프로그램을 종료합니다.")
        sys.exit(1)
    
    # =========================================================================
    # 2. 투자 종목 필터링
    # =========================================================================
    logging.info("🔍 투자 종목 필터링 시작")
    
    # 필터링된 투자 종목 리스트 생성
    filtered_invest_stock_list = []
    
    for stock in InvestStockList:
        stock_code = stock['stock_code']
        stock_name = stock['stock_name']
        
        # 제외 종목 리스트에 포함된 종목 필터링
        if stock_code in exclude_stock_codes:
            logging.info(f"❌ 제외 리스트: {stock_name} ({stock_code})")
            continue
        
        # 이동평균선 설정이 누락된 종목 필터링
        if stock.get('small_ma') is None or stock.get('big_ma') is None:
            logging.info(f"❌ 이동평균선 미설정: {stock_name} ({stock_code})")
            continue
            
        # 필터링을 통과한 종목만 추가
        filtered_invest_stock_list.append(stock)
    
    # 필터링된 종목 리스트로 업데이트
    InvestStockList = filtered_invest_stock_list
    logging.info(f"✅ 필터링 후 투자 대상 종목: {len(InvestStockList)}개")
    
    # 투자 대상 종목 상세 로깅
    #for stock in InvestStockList:
    #    logging.info(f"   📈 {stock['stock_name']} ({stock['stock_code']}) - "
    #                f"단기MA: {stock['small_ma']}, 장기MA: {stock['big_ma']}")
    
    # 매수 가능한 최대 종목 수 설정
    MAX_BUY_STOCKS = bot_config.get('max_buy_stocks', 30)
    logging.info(f"🎯 매수 가능한 최대 종목 수: {MAX_BUY_STOCKS}개")


    
    # =========================================================================
    # 3. 계좌 정보 및 투자 금액 계산
    # =========================================================================
    """
    매도 비중 설정 설명:
    - FixRate + DynamicRate = 전체 매도 비중
    - 예: FixRate(0.3) + DynamicRate(0.4) = 0.7 → 매도 신호 시 70% 매도, 30% 보유
    - 두 값이 모두 0이면 매도 신호 시 100% 매도
    """
    
    logging.info("=" * 50)
    logging.info("💰 계좌 잔고 정보")
    logging.info("=" * 50)
    logging.info(pprint.pformat(Balance))
    logging.info("=" * 50)

    # 포트폴리오에 할당된 총 투자 가능 금액 계산
    TotalMoney = float(Balance['TotalMoney']) * InvestRate
    logging.info(f"💵 총 평가금액: {float(Balance['TotalMoney']):,.0f}원")
    logging.info(f"💵 포트폴리오 할당금액: {TotalMoney:,.0f}원 (투자비중: {InvestRate*100:.1f}%)")

    # =========================================================================
    # 4. 투자 종목 상태 파일 로딩
    # =========================================================================
    # 현재 투자중인 종목 리스트를 저장하는 JSON 파일 경로
    invest_file_path = os.path.join(script_dir, BOT_NAME + "_StockInvestList.json")
    
    try:
        # 기존 투자 종목 리스트 로딩
        with open(invest_file_path, 'r') as json_file:
            StockInvestList = json.load(json_file)
        logging.info(f"📂 기존 투자 종목 리스트 로딩 완료: {len(StockInvestList)}개 종목")
        
    except FileNotFoundError:
        # 최초 실행 시 파일이 없는 경우 빈 리스트로 초기화
        StockInvestList = []
        logging.info("📂 투자 종목 리스트 파일이 없어 새로 생성합니다.")
    except Exception as e:
        logging.error(f"📂 투자 종목 리스트 로딩 중 오류: {e}")
        StockInvestList = []

    # =========================================================================
    # 5. 포트폴리오 데이터 구조 생성
    # =========================================================================
    logging.info("🏗️ 포트폴리오 데이터 구조 생성 시작")
    
    # 각 투자 대상 종목에 대한 포트폴리오 정보 생성
    for stock_info in InvestStockList:
        asset = {
            'stock_code': stock_info['stock_code'],                    # 종목 코드
            'stock_name': KisKR.GetStockName(stock_info['stock_code']), # 종목명 (API 조회)
            'small_ma': stock_info['small_ma'],                        # 단기 이동평균선 기간
            'big_ma': stock_info['big_ma'],                           # 장기 이동평균선 기간
            'stock_target_rate': stock_info['invest_rate'],           # 목표 투자 비중
            'stock_rebalance_amt': 0,                                 # 리밸런싱 수량 (계산 예정)
            'status': 'NONE'                                          # 매매 상태 (NONE/BUY/SELL)
        }
        MyPortfolioList.append(asset)
    
    logging.info(f"✅ 포트폴리오 데이터 생성 완료: {len(MyPortfolioList)}개 종목")

    # =========================================================================
    # 6. 현재 보유 주식 정보 조회
    # =========================================================================
    logging.info("=" * 50)
    logging.info("📈 현재 보유 주식 정보 조회")
    logging.info("=" * 50)
    
    # KIS API를 통한 보유 주식 리스트 조회
    MyStockList = KisKR.GetMyStockList()
    logging.info(f"📊 보유 주식 종목 수: {len(MyStockList)}개")
    
    # 보유 주식 상세 정보 로깅
    for stock in MyStockList:
        if int(stock.get('StockAmt', 0)) > 0:  # 보유 수량이 있는 종목만
            logging.info(f"   🏛️ {stock.get('StockName', 'N/A')} ({stock.get('StockCode', 'N/A')}) "
                        f"- {stock.get('StockAmt', 0)}주, 평균단가: {stock.get('StockAvgPrice', 0)}원")
    
    logging.info("=" * 50)
    
    # 보유 종목 동기화: 실제 지갑 보유 종목 기준으로 StockInvestList 정합성 맞추기 (투자 대상/제외 리스트 반영)
    try:
        invest_stock_codes = [
            s['stock_code'] for s in InvestStockList if s.get('stock_code') not in exclude_stock_codes
        ]
        actual_holdings_codes = []
        for s in MyStockList:
            try:
                if int(s.get('StockAmt', 0)) > 0 and s.get('StockCode') in invest_stock_codes:
                    actual_holdings_codes.append(s.get('StockCode'))
            except Exception:
                continue
        # 중복 제거 및 정렬로 안정화
        actual_holdings_codes = sorted(list(set(actual_holdings_codes)))
        loaded_codes = sorted(list(set(StockInvestList))) if isinstance(StockInvestList, list) else []
        if actual_holdings_codes != loaded_codes:
            logging.info(
                f"보유 종목 동기화: 파일({len(loaded_codes)}개) → 실제 보유({len(actual_holdings_codes)}개)로 업데이트")
            StockInvestList = actual_holdings_codes
            try:
                with open(invest_file_path, 'w') as outfile:
                    json.dump(StockInvestList, outfile)
            except Exception as e:
                logging.error(f"보유 종목 동기화 저장 실패: {e}")
    except Exception as e:
        logging.error(f"보유 종목 동기화 중 오류: {e}")
    # =========================================================================
    # 7. 기술적 분석 데이터 생성
    # =========================================================================
    logging.info("=" * 50)
    logging.info("📊 기술적 분석 데이터 생성 및 분석 시작")
    logging.info("=" * 50)

    # 각 종목별 기술적 분석 데이터를 저장할 리스트
    stock_df_list = []

    # 각 투자 대상 종목에 대해 기술적 분석 수행
    for stock_info in InvestStockList:
        stock_code = stock_info['stock_code']
        stock_name = stock_info['stock_name']
        
        #logging.info(f"📈 {stock_name}({stock_code}) 데이터 분석 중...")
        
        # =====================================================================
        # 7-1. OHLCV 데이터 조회 (최근 300거래일)
        # =====================================================================
        df = Common.GetOhlcv("KR", stock_code, 300)
        
        # 전일 종가 추가 (모멘텀 계산용)
        df['prevClose'] = df['close'].shift(1)

        # =====================================================================
        # 7-2. 이동평균선 계산 (3일~200일)
        # =====================================================================
        ma_dfs = []
        
        # 3일부터 200일까지의 모든 이동평균선 계산
        for ma_period in range(3, 201):
            # 전일 이동평균선 (1일 지연)
            ma_before = df['close'].rolling(ma_period).mean().rename(f'{ma_period}ma_before').shift(1)
            ma_dfs.append(ma_before)
            
            # 전전일 이동평균선 (2일 지연) - 기울기 계산용
            ma_before2 = df['close'].rolling(ma_period).mean().rename(f'{ma_period}ma_before2').shift(2)
            ma_dfs.append(ma_before2)
        
        # 모든 이동평균선 데이터를 하나로 결합
        ma_df_combined = pd.concat(ma_dfs, axis=1)
        df = pd.concat([df, ma_df_combined], axis=1)

        # =====================================================================
        # 7-3. 평균 모멘텀 지표 계산 (200거래일 기준)
        # =====================================================================
        # 20일 간격으로 10개 구간 설정 (20, 40, 60, ..., 200일)
        momentum_periods = [i * 20 for i in range(1, 11)]
        
        # 각 구간별 모멘텀 계산 (현재가 > 과거가 = 1, 아니면 0)
        for period in momentum_periods:
            column_name = f'Momentum_{period}'
            df[column_name] = (df['prevClose'] > df['close'].shift(period)).astype(int)

        # 평균 모멘텀 계산 (10개 구간의 평균)
        momentum_columns = [f'Momentum_{period}' for period in momentum_periods]
        df['Average_Momentum'] = df[momentum_columns].sum(axis=1) / len(momentum_periods)
        
        # 모멘텀 필터링: 0.4 이하는 0으로 처리 (약한 모멘텀 제거)
        df['Average_Momentum'] = df['Average_Momentum'].apply(lambda x: 0 if x <= 0.4 else x)

        # =====================================================================
        # 7-4. 데이터 정리 및 저장
        # =====================================================================
        # 결측값 제거
        df.dropna(inplace=True)
        
        # 종목 코드와 함께 데이터 저장
        data_dict = {stock_code: df}
        stock_df_list.append(data_dict)

    # =========================================================================
    # 8. 전체 데이터 통합 및 최신 거래일 추출
    # =========================================================================
    # 모든 종목의 데이터를 하나의 DataFrame으로 통합
    combined_df = pd.concat([
        list(data_dict.values())[0].assign(stock_code=stock_code) 
        for data_dict in stock_df_list 
        for stock_code in data_dict
    ])
    combined_df.sort_index(inplace=True)
    
    logging.info(f"📊 전체 데이터 통합 완료: {len(combined_df)} 행")
    
    # 최신 거래일 추출 (리밸런싱 기준일)
    latest_date = combined_df.iloc[-1].name
    logging.info(f"📅 분석 기준일: {latest_date}")

    # =========================================================================
    # 9. 리밸런싱 대상 종목 리스트 초기화
    # =========================================================================
    TodayRebalanceList = []        # 오늘 리밸런싱할 종목 리스트
    potential_buy_stocks = []      # 매수 후보 종목 리스트

    #리밸런싱 수량을 확정한다!
    for stock_info in MyPortfolioList:
        stock_code = stock_info['stock_code']
        stock_name = stock_info['stock_name']

        stock_data = combined_df[(combined_df.index == latest_date) & (combined_df['stock_code'] == stock_code)] 

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
                    # 평균모먼텀이 1인 종목만 필터링
                    if stock_data['Average_Momentum'].values[0] == 1.0:
                        # 기울기 관련 요소들 계산
                        # 1. 이동평균선 기울기 (5일, 20일 이동평균의 기울기)
                        ma5_slope = stock_data['5ma_before'].values[0] - stock_data['5ma_before2'].values[0]
                        ma20_slope = stock_data['20ma_before'].values[0] - stock_data['20ma_before2'].values[0]
                        ma_slope_score = (ma5_slope * 0.7 + ma20_slope * 0.3) * 1000  # 가중치: 1000
                        
                        # 2. 가격 대비 이동평균선 위치 (현재 가격이 20일 이동평균보다 얼마나 위에 있는지)
                        price_ma20_ratio = (stock_data['close'].values[0] / stock_data['20ma_before'].values[0] - 1) * 100  # 가중치: 100
                        
                        # 3. 최근 가격 변동성 (전일 대비 가격 변화율)
                        price_change_rate = ((stock_data['close'].values[0] / stock_data['prevClose'].values[0] - 1) * 100) * 50  # 가중치: 50
                        
                        # 우선순위 점수 계산
                        priority_score = ma_slope_score + price_ma20_ratio + price_change_rate
                        
                        logging.info(f"{stock_name} {stock_code} - 평균모먼텀: {stock_data['Average_Momentum'].values[0]}, 우선순위점수: {priority_score:.2f}")
                        logging.info(f"  - 이동평균기울기점수: {ma_slope_score:.2f}, 가격대비MA20위치: {price_ma20_ratio:.2f}, 가격변동성: {price_change_rate:.2f}")
                        
                        # 매수 조건을 만족하는 종목을 임시 리스트에 추가
                        potential_buy_stocks.append({
                            'stock_code': stock_code,
                            'stock_name': stock_name,
                            'stock_info': stock_info,
                            'target_rate': stock_info['stock_target_rate'],
                            'priority_score': priority_score
                        })

    # =========================================================================
    # 10. 매수 후보 종목 선별 및 제한 적용
    # =========================================================================
    # 매수 조건을 만족하는 종목들을 우선순위 점수에 따라 정렬 (기울기가 높은 순)
    potential_buy_stocks.sort(key=lambda x: x['priority_score'], reverse=True)
    
    # 현재 보유 중인 종목 수 확인 (실제 지갑 보유 기준, 투자 대상/제외 리스트 반영)
    current_holdings = 0
    try:
        invest_stock_codes = [
            s['stock_code'] for s in InvestStockList if s.get('stock_code') not in exclude_stock_codes
        ]
        current_holdings = sum(
            1 for s in MyStockList
            if int(s.get('StockAmt', 0)) > 0 and s.get('StockCode') in invest_stock_codes
        )
    except Exception as e:
        logging.error(f"보유 종목 수 계산 중 오류: {e}")
        current_holdings = len(StockInvestList)
    # 음수일 경우 파이썬 슬라이싱 특성 때문에 제한이 무력화되므로 0으로 클램프
    available_slots = max(0, MAX_BUY_STOCKS - current_holdings)
    
    logging.info(f"매수 조건을 만족하는 종목 수: {len(potential_buy_stocks)}개")
    logging.info(f"현재 보유 종목 수: {current_holdings}/{MAX_BUY_STOCKS}")
    logging.info(f"매수 가능한 종목 수: {available_slots}개")
    
    # 매수 가능한 종목 수만큼만 선택 (0이면 신규 매수 없음)
    selected_buy_stocks = potential_buy_stocks[:available_slots]
    if available_slots == 0 and len(potential_buy_stocks) > 0:
        logging.info("보유 종목이 최대치라 신규 매수 종목을 선택하지 않습니다.")
    
    # 선택된 종목들의 투자비율을 MAX_BUY_STOCKS 기준으로 재조정
    if selected_buy_stocks:
        # MAX_BUY_STOCKS 기준으로 균등 분배
        adjusted_rate = 1.0 / MAX_BUY_STOCKS
        
        logging.info(f"선택된 종목들의 투자비율을 {adjusted_rate*100:.2f}%로 재조정 (MAX_BUY_STOCKS: {MAX_BUY_STOCKS}개 기준)")
        
        # 선택된 종목들을 MyPortfolioList에 추가하고 투자비율 조정
        for selected_stock in selected_buy_stocks:
            stock_code = selected_stock['stock_code']
            stock_name = selected_stock['stock_name']
            stock_info = selected_stock['stock_info']
            priority_score = selected_stock['priority_score']
            
            # 투자비율을 30개 기준으로 재조정
            stock_info['stock_target_rate'] = adjusted_rate
            
            Is_Rebalance_Go = True
            stock_info['status'] = 'BUY'
            logging.info(f"{stock_name} {stock_code} 매수조건 만족!!! 우선순위점수: {priority_score:.2f}, {stock_info['stock_target_rate']*100:.2f}% 비중으로 매매 (보유종목: {current_holdings}/{MAX_BUY_STOCKS})")
            
            TodayRebalanceList.append(stock_code)
    
    # 매수 제한으로 인해 선택되지 않은 종목들 로그
    if len(potential_buy_stocks) > available_slots:
        logging.info(f"매수 제한으로 인해 {len(potential_buy_stocks) - available_slots}개 종목이 제외됨:")
        for excluded_stock in potential_buy_stocks[available_slots:]:
            logging.info(f"  - {excluded_stock['stock_name']} ({excluded_stock['stock_code']}) - 우선순위점수: {excluded_stock['priority_score']:.2f}, 투자비중: {excluded_stock['target_rate']*100}%")




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
                if FixRate == 0:
                    stock_info['status'] = 'NONE'  # FixRate가 0이면 매수하지 않음
                    #msg = PortfolioName + " 투자 비중이 없어 "+ stock_name + " " + stock_code+" 종목을 매수하지 않습니다. (FixRate: 0)"
                else:
                    stock_info['status'] = 'BUY_S'  # FixRate가 0이 아니면 매수
                    msg = PortfolioName + " 투자 비중이 없어 "+ stock_name + " " + stock_code+" 종목의 할당 비중의 " + str(FixRate*100) + "%를 투자하도록 함!"
                    logging.info(msg)
                #telegram.send(msg)
            
            
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
                    
                    # 최소 매수 수량 체크 (1주 이상이어야 매수)
                    #if BuyAmt >= 1:
                    #    stock_info['stock_rebalance_amt'] = BuyAmt
                    #    logging.info(f"{stock_name} {stock_code} 매수 수량: {BuyAmt}주 (투자금액: ${BuyMoney:.2f}, 현재가: ${CurrentPrice:.2f})")
                    #else:
                    #    stock_info['stock_rebalance_amt'] = 0
                    #    logging.info(f"{stock_name} {stock_code} 매수 취소: 투자금액이 부족함 (필요금액: ${BuyMoney:.2f}, 현재가: ${CurrentPrice:.2f})")

            
        # 비중이 있는 종목만 로그/메시지 생성
        if (stock_now_rate > 0) or (stock_target_rate > 0):
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


    # 매매 실행 여부 확인
    if ENABLE_ORDER_EXECUTION:
        logging.info("매매 실행 모드로 실행 중...")
        
        # 매매 실행 전 상태 로깅 (실제 지갑 보유 기준)
        try:
            invest_stock_codes = [
                s['stock_code'] for s in InvestStockList if s.get('stock_code') not in exclude_stock_codes
            ]
            current_holdings_pre = sum(
                1 for s in MyStockList
                if int(s.get('StockAmt', 0)) > 0 and s.get('StockCode') in invest_stock_codes
            )
        except Exception:
            current_holdings_pre = len(StockInvestList)
        logging.info(f"현재 보유 종목 수: {current_holdings_pre}개")
        logging.info(f"매매 대상 종목 수: {len(TodayRebalanceList)}개")
        
        # 매매 실행
        if Is_Rebalance_Go and IsMarketOpen:
            logging.info("매매 실행 시작")
            
            # 매도 실행
            sell_count = 0
            for stock_info in MyPortfolioList:
                stock_code = stock_info['stock_code']
                rebalance_amt = stock_info['stock_rebalance_amt']
                
                if rebalance_amt < 0:
                    CurrentPrice = KisKR.GetCurrentPrice(stock_code)
                    CurrentPrice *= 0.99
                    data = KisKR.MakeSellLimitOrder(stock_code, abs(rebalance_amt), CurrentPrice)
                    logging.info(f"매도 주문: {stock_code} - {data}")
                    sell_count += 1
            
            logging.info(f"매도 주문 완료: {sell_count}개 종목")
            
            # 3초 대기
            time.sleep(3.0)
            
            # 매수 실행
            buy_count = 0
            total_investment_used = 0  # 금번 매수 세션의 신규 투자금 추적 (로그용)
            # 기존 보유 평가금액을 포함하여 예산 체크를 하기 위한 현재 사용 예산
            budget_used = total_stock_money
            buy_stocks = [stock_info for stock_info in MyPortfolioList if stock_info['stock_rebalance_amt'] > 0]
            buy_stocks.sort(key=lambda x: x['stock_target_rate'], reverse=True)
            
            for stock_info in buy_stocks:
                stock_code = stock_info['stock_code']
                rebalance_amt = stock_info['stock_rebalance_amt']
                
                if rebalance_amt > 0:
                    CurrentPrice = KisKR.GetCurrentPrice(stock_code)
                    CurrentPrice *= 1.01
                    
                    # 이 종목의 투자금액 계산
                    investment_amount = rebalance_amt * CurrentPrice
                    
                    # 총 투자금 제한 체크 (기보유 평가금액 + 신규 매수 누적 기준)
                    if budget_used + investment_amount > TotalMoney:
                        # 투자금 초과 시 수량 조정
                        remaining_money = TotalMoney - budget_used
                        if remaining_money > 0:
                            adjusted_quantity = int(remaining_money / CurrentPrice)
                            if adjusted_quantity >= 1:
                                rebalance_amt = adjusted_quantity
                                investment_amount = rebalance_amt * CurrentPrice
                                logging.info(f"{stock_code} 투자금 초과로 수량 조정: {rebalance_amt}주 (투자금: {investment_amount:,.0f}원)")
                            else:
                                logging.info(f"{stock_code} 투자금 부족으로 매수 취소")
                                continue
                        else:
                            logging.info(f"{stock_code} 투자금 한도 초과로 매수 취소")
                            continue
                    
                    data = KisKR.MakeBuyLimitOrder(stock_code, rebalance_amt, CurrentPrice)
                    logging.info(f"매수 주문: {stock_code} - {data}")
                    buy_count += 1
                    total_investment_used += investment_amount
                    budget_used += investment_amount
            
            logging.info(f"매수 주문 완료: {buy_count}개 종목")
            
            # 보유 종목 리스트 업데이트
            for stock_info in MyPortfolioList:
                stock_code = stock_info['stock_code']
                if stock_info['status'] == 'BUY':
                    if stock_code not in StockInvestList:
                        StockInvestList.append(stock_code)
                elif stock_info['status'] == 'SELL':
                    if stock_code in StockInvestList:
                        StockInvestList.remove(stock_code)
            
            # 파일에 저장
            with open(invest_file_path, 'w') as outfile:
                json.dump(StockInvestList, outfile)
            
            logging.info("매매 실행 완료")
        else:
            logging.info("매매 조건이 충족되지 않아 매매를 실행하지 않습니다.")
            if not Is_Rebalance_Go:
                logging.info("리밸런싱 대상이 없습니다.")
            if not IsMarketOpen:
                logging.info("장이 열려있지 않습니다.")
    else:
        logging.info("매매 실행이 비활성화되어 있습니다.")
        


# 포트폴리오 보유 종목 정보를 업데이트하는 함수
def update_portfolio_holdings():
    """현재 보유 종목 정보를 portfolio_config.json에 업데이트합니다."""
    try:
        # portfolio_config.json 파일 읽기
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_file_path = os.path.join(script_dir, "portfolio_config.json")
        
        with open(config_file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            bot_config = config_data['bots']['MA_Kosdaqpi100_Bot_v1']
            InvestStockList = bot_config['invest_stock_list']
            # 제외 리스트 적용을 위해 로드
            exclude_stock_list = bot_config.get('exclude_stock_list', [])
            exclude_stock_codes = [list(item.keys())[0] for item in exclude_stock_list]
        
        # 현재 보유 주식 정보 가져오기
        MyStockList = KisKR.GetMyStockList()
        
        # 투자 대상 종목 코드 리스트 생성 (제외 리스트 적용)
        invest_stock_codes = [
            stock['stock_code'] for stock in InvestStockList
            if stock.get('stock_code') not in exclude_stock_codes
        ]
        
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
        initial_allocation = config_data['bots']['MA_Kosdaqpi100_Bot_v1']['initial_allocation']
        realized_total_profit = config_data['bots']['MA_Kosdaqpi100_Bot_v1'].get('total_sold_profit', 0)
        current_allocation = initial_allocation + cumulative_profit + realized_total_profit
        
        # 현금 잔고 계산 (현재 분배금 - 보유 주식 평가금액)
        cash_balance = current_allocation - total_holding_value
        
        # portfolio_config.json 업데이트
        config_data['bots']['MA_Kosdaqpi100_Bot_v1']['current_allocation'] = current_allocation
        config_data['bots']['MA_Kosdaqpi100_Bot_v1']['holdings'] = holdings
        config_data['bots']['MA_Kosdaqpi100_Bot_v1']['total_holding_value'] = total_holding_value
        config_data['bots']['MA_Kosdaqpi100_Bot_v1']['cash_balance'] = cash_balance
        # 판매 누적 수익은 판매 시점에만 갱신되며 여기서 리셋하지 않습니다.
        config_data['bots']['MA_Kosdaqpi100_Bot_v1']['total_sold_profit'] = realized_total_profit
        
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
        bot_config = config_data['bots']['MA_Kosdaqpi100_Bot_v1']
        
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
        bot_config = config_data['bots']['MA_Kosdaqpi100_Bot_v1']
        
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

# 수익 계산 및 업데이트 함수
def calculate_and_update_profit():
    """현재 수익을 계산하고 포트폴리오 매니저에 업데이트합니다."""
    try:
        # portfolio_config.json에서 InvestRate 로딩
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_file_path = os.path.join(script_dir, "portfolio_config.json")
        
        with open(config_file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            bot_config = config_data['bots']['MA_Kosdaqpi100_Bot_v1']
            InvestRate = bot_config['allocation_rate']
            # 투자 대상 종목 리스트 + 제외 리스트 로딩 (함수 스코프 내에서 사용)
            InvestStockList = bot_config['invest_stock_list']
            exclude_stock_list = bot_config.get('exclude_stock_list', [])
            exclude_stock_codes = [list(item.keys())[0] for item in exclude_stock_list]
        
        # 현재 보유 주식 정보 가져오기
        MyStockList = KisKR.GetMyStockList()
        
        total_profit = 0
        total_investment = 0
        initial_investment = portfolio_manager.get_initial_investment() * InvestRate
        
        # 투자 대상 종목 코드 리스트 생성 (제외 리스트 적용)
        invest_stock_codes = [
            stock['stock_code'] for stock in InvestStockList
            if stock.get('stock_code') not in exclude_stock_codes
        ]
        
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
        portfolio_manager.update_bot_profit("MA_Kosdaqpi100_Bot_v1", total_profit, profit_rate)
        
        # 로그 출력
        logging.info("=== MA_Kosdaqpi100_Bot_v1 수익 현황 ===")
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
        
        bot_config = config_data['bots']['MA_Kosdaqpi100_Bot_v1']
        initial_allocation = bot_config['initial_allocation']
        current_allocation = bot_config['current_allocation']
        total_sold_profit = bot_config['total_sold_profit']
        # 투자 대상 종목 리스트 + 제외 리스트 로딩 (함수 스코프 내에서 사용)
        InvestStockList = bot_config['invest_stock_list']
        exclude_stock_list = bot_config.get('exclude_stock_list', [])
        exclude_stock_codes = [list(item.keys())[0] for item in exclude_stock_list]
    except Exception as e:
        logging.error(f"portfolio_config.json 읽기 중 오류: {e}")
        initial_allocation = 0
        current_allocation = 0
        total_sold_profit = 0
        InvestStockList = []
    
    # 현재 보유 주식 정보 가져오기
    MyStockList = KisKR.GetMyStockList()
    
    # 투자 대상 종목 코드 리스트 생성 (제외 리스트 적용)
    invest_stock_codes = [
        stock['stock_code'] for stock in InvestStockList
        if stock.get('stock_code') not in exclude_stock_codes
    ]
    
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
                status_emoji = "❌"  # 빨간색 그래프 올라가는 아이콘으로 변경
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
    lock_file = os.path.join(script_dir, "MA_Kosdaqpi100_Bot_v1.lock")
    
    try:
        # 이미 실행 중인지 확인
        if os.path.exists(lock_file):
            logging.info("이미 실행 중인 봇이 있습니다. 종료합니다.")
            telegram.send("MA_Kosdaqpi100_Bot_v1 : 이미 실행 중인 봇이 있습니다. 종료합니다.")
            sys.exit(0)
        
        # 락 파일 생성
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        
        logging.info("MA_Kosdaqpi100_Bot_v1 시작")
        logging.info("=" * 37)
        telegram.send("MA_Kosdaqpi100_Bot_v1 시작")
        
        main()

        # 봇 실행 완료 후 수익 계산 및 업데이트
        if ENABLE_ORDER_EXECUTION:
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
        
        logging.info("MA_Kosdaqpi100_Bot_v1 정상 종료")
        logging.info("=" * 37)
        telegram.send("MA_Kosdaqpi100_Bot_v1 정상 종료")
        
    except Exception as e:
        error_msg = f"MA_Kosdaqpi100_Bot_v1 실행 중 오류 발생: {e}"
        logging.error(error_msg)
        telegram.send(f"오류: {error_msg}")
        sys.exit(1)
    finally:
        # 락 파일 제거
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logging.info("락 파일 제거 완료")
        except Exception as e:
            logging.error(f"락 파일 제거 실패: {e}")