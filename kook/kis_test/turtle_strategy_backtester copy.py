"""
===================================================================================================
|                                                                                                 |
|               KOSPI/KOSDAQ Momentum Ranking & Volatility Parity Strategy                        |
|                                                                                                 |
===================================================================================================
|
|   **전략 개요:**
|   - 한국 주식(코스피/코스닥) 대상의 모멘텀 기반 포트폴리오 전략.
|   - '평균 모멘텀 점수'로 후보를 만들고, 다중 팩터 점수(이평 기울기/이격도/가격변화/거래량/RSI)로 랭킹 후 매수.
|   - ATR 기반 포지션 사이징과(위험 균등), 손절(고정/트레일링) 및 피라미딩을 지원.
|
|--------------------------------------------------------------------------------------------------
|
|   **실행 가정(체결/주기):**
|   - 체결 시점: 리밸런싱일의 장마감 직전(종가 근처) 체결 가정.
|   - 슬리피지: `slippage_bps`로 매수는 종가*(1+bps), 매도는 종가*(1-bps).
|   - 리밸런싱 주기:
|       - daily: 모든 거래일.
|       - weekly: 해당 주의 첫 거래일(월요일 휴장 시 화요일 등) 1회 실행.
|
|--------------------------------------------------------------------------------------------------
|
|   **전략 플로우(요약):**
|   1) 시장 필터: KOSPI 200MA(선택적으로 50MA) 위에서만 신규 매수 허용.
|   2) 후보 생성: 모멘텀 임계(`momentum_threshold`) 충족(정적 or 상향돌파 `crossing`).
|   3) 점수/랭킹: 팩터별 퍼센트랭크 → 가중합(`score_weights`) → 내림차순 정렬.
|   4) 매수 선정: 빈 슬롯 수만큼 상위부터 채택, ATR로 포지션 수량 산정.
|   5) 관리: 고정 손절(매수가 - ATR*k), 선택적 트레일링 스탑, 선택적 피라미딩.
|
|--------------------------------------------------------------------------------------------------
|
|   **핵심 로직 상세:**
|   - 시장 필터(Market Regime): KOSPI 200MA(필수) & 선택적 50MA 모두 상회 시 상승장으로 간주.
|   - 매수 조건:
|       • static: 당일 Average_Momentum ≥ 임계.
|       • crossing: 전일 < 임계 AND 당일 ≥ 임계.
|   - 매도 조건:
|       • classic_turtle: N일 저가(`exit_low`) 하회 시 청산.
|       • momentum: Average_Momentum < `momentum_sl_threshold` 시 청산.
|   - 포지션 사이징: (총자본 × (리스크/최대보유수)) / ATR.
|
|--------------------------------------------------------------------------------------------------
|
|   **사용 지표(계산 기준: 미래데이터 미사용, 대부분 전일/과거 기반):**
|   - entry_high: 고가.shift(1).rolling(N).max — 전일까지 N일 중 최고가(돌파선).
|   - exit_low: 저가.shift(1).rolling(M).min — 전일까지 M일 중 최저가(청산선).
|   - ATR: talib.ATR(high, low, close, period) — 변동성/포지션 사이징/손절에 사용.
|   - prev_close: 종가.shift(1) — 전일 종가.
|   - 5ma/20ma: 종가.rolling(window).mean.shift(1) — 신호일 기준 전일까지의 이동평균.
|   - 5ma_prev/20ma_prev: 위 이평을 한 번 더 shift(1) — 기울기 계산용.
|   - volume_ma: (거래량*종가).rolling(20).mean.shift(1) — 전일 기준 거래대금 평균(유동성 필터).
|   - volume_ma20/60: 거래량 이동평균의 전일 기준 값(유동성 상대비교용).
|   - RSI(14): talib.RSI — 당일 종가까지 포함(신호 판단은 EOD 체결 가정에 부합).
|   - Momentum_{20..200}: (종가.shift(1) > 종가.shift(1+period)) 여부(1/0).
|   - Average_Momentum: 위 모멘텀 10개 평균(0~1) 및 전일값 Average_Momentum_prev.
|   - KOSPI 200ma/50ma: 지수의 200/50 이동평균(시장 필터).
|
|--------------------------------------------------------------------------------------------------
|
|   **백테스트 기본 설정:**
|   - 대상: KOSPI100, KOSDAQ100
|   - 수수료/세금: 매수 수수료 0.015%, 매도 수수료 0.015% + 세금 0.2%
|   - 리밸런싱: daily/weekly 선택(weekly는 주 첫 거래일 자동 판별)
|
===================================================================================================
"""
# -*- coding: utf-8 -*-

import os
import io
import sys
import pandas as pd
import numpy as np
import talib
import logging
import glob
from tqdm import tqdm
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.ticker import FuncFormatter
import itertools
import copy

# --- 1. 기본 설정 (로깅, UTF-8, 한글 폰트) ---

# Windows 콘솔에서 UTF-8 출력이 깨지는 문제 해결
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 로깅 설정
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, 'turtle_backtester.log')

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file_path, mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def setup_korean_font():
    """Matplotlib에서 한글을 지원하기 위한 폰트 설정"""
    try:
        font_path = fm.findfont(fm.FontProperties(family='Malgun Gothic'))
        plt.rcParams['font.family'] = 'Malgun Gothic'
    except:
        try:
            plt.rcParams['font.family'] = 'AppleGothic'
        except:
            logging.warning("경고: '맑은 고딕' 또는 'AppleGothic' 폰트를 찾을 수 없어 기본 폰트를 사용합니다. 그래프의 한글이 깨질 수 있습니다.")
    plt.rcParams['axes.unicode_minus'] = False


# --- 2. 데이터 로딩 ---

def load_universe_data(data_dir):
    """지정된 디렉토리에서 KOSPI/KOSDAQ/지수 데이터를 로드합니다."""
    universe_dfs = {}
    
    # 코스닥/코스피 100 종목 로드
    kospi100_files = glob.glob(os.path.join(data_dir, "kospi100", "*.csv"))
    kosdaq100_files = glob.glob(os.path.join(data_dir, "kosdaq100", "*.csv"))
    
    if not kospi100_files and not kosdaq100_files:
        logging.error(f"❌ 코스닥/코스피 100 데이터 파일을 찾을 수 없습니다: {os.path.join(data_dir, 'kospi100')}")
        return None, []

    all_files = kospi100_files + kosdaq100_files
    for f in all_files:
        try:
            ticker = os.path.basename(f).split('_')[0]
            df = pd.read_csv(f, index_col='date', parse_dates=True)
            df.columns = [col.lower() for col in df.columns]
            universe_dfs[ticker] = df
        except Exception as e:
            logging.warning(f"⚠️ {f} 파일 로드 중 오류 발생: {e}")


    # KOSPI 지수 데이터 로드 (추세 필터용)
    kospi_search_pattern = os.path.join(data_dir, "etf_index", "KOSPI_*.csv")
    kospi_files = glob.glob(kospi_search_pattern)
    if kospi_files:
        df = pd.read_csv(kospi_files[0], index_col='date', parse_dates=True)
        df.columns = [col.lower() for col in df.columns]
        universe_dfs['KOSPI'] = df
    else:
        logging.error(f"❌ KOSPI 지수 데이터를 찾을 수 없습니다: 패턴({kospi_search_pattern})")
        return None, []

    tickers = [os.path.basename(f).split('_')[0] for f in all_files]
    logging.info(f"✅ 총 {len(tickers)}개 종목 및 KOSPI 지수 데이터 로드 완료.")
    return universe_dfs, tickers


# --- 3. 전략 정의 ---

class PortfolioStrategy:
    """모든 포트폴리오 전략의 기반 클래스"""
    def __init__(self, tickers, params):
        self.tickers = tickers
        self.params = params
        self.universe_with_indicators = {}

    def _add_indicators(self, universe_dfs, tickers):
        raise NotImplementedError("'_add_indicators'를 구현해야 합니다.")

    def generate_signals(self, date, universe_dfs, tickers, current_holdings, strategy_capital, kospi_df):
        # 기본 상태: 현재 보유 종목을 그대로 유지
        target_quantities = {ticker: h['quantity'] for ticker, h in current_holdings.items()}

        # --- 1. 매도 신호 검사 ---
        # 기존 터틀 전략의 청산 조건 (N일 최저가 하회)
        pending_sales_count = 0
        for ticker, holding in current_holdings.items():
            df = universe_dfs.get(ticker)
            if df is not None and date in df.index and pd.notna(df.loc[date, 'exit_low']):
                if df.loc[date, 'close'] < df.loc[date, 'exit_low']:
                    target_quantities[ticker] = 0 # 전량 매도 신호
                    pending_sales_count += 1
        
        # --- 2. 신규 매수 신호 검사 ---
        # 매도 등으로 빈 슬롯이 생겼는지 확인
        effective_holdings_count = len(current_holdings) - pending_sales_count
        available_slots = self.max_positions - effective_holdings_count

        if available_slots > 0:
            # 시장 트렌드 필터
            kospi_above_200ma = False
            if date in kospi_df.index and pd.notna(kospi_df.loc[date, '200ma']):
                kospi_above_200ma = kospi_df.loc[date, 'close'] > kospi_df.loc[date, '200ma']

            if kospi_above_200ma:
                potential_buy_stocks = []
                for ticker in tickers:
                    # 이미 보유하고 있는 종목은 신규 매수 후보에서 제외
                    if ticker in current_holdings:
                        continue

                    df = universe_dfs.get(ticker)
                    if df is not None and date in df.index and pd.notna(df.loc[date, 'Average_Momentum']) and df.loc[date, 'Average_Momentum'] >= 0.8:
                        
                        # 우선순위 점수 계산
                        ma5 = df.loc[date, '5ma']
                        ma5_prev = df.loc[date, '5ma_prev']
                        ma20 = df.loc[date, '20ma']
                        ma20_prev = df.loc[date, '20ma_prev']
                        prev_close = df.loc[date, 'prev_close']
                        prev_close_2 = df['close'].shift(2).loc[date]

                        if all(pd.notna([ma5, ma5_prev, ma20, ma20_prev, prev_close, prev_close_2])):
                            ma5_slope = ma5 - ma5_prev
                            ma20_slope = ma20 - ma20_prev
                            ma_slope_score = (ma5_slope * 0.7 + ma20_slope * 0.3) * 1000
                            price_ma20_ratio = (prev_close / ma20 - 1) * 100 if ma20 > 0 else 0
                            price_change_rate = ((prev_close / prev_close_2 - 1) * 100) * 50 if prev_close_2 > 0 else 0
                            priority_score = ma_slope_score + price_ma20_ratio + price_change_rate
                            
                            potential_buy_stocks.append({
                                'ticker': ticker,
                                'score': priority_score
                            })
                
                if potential_buy_stocks:
                    logging.info(f"[{date.date()}] 매수 후보: {len(potential_buy_stocks)}개, 가능 슬롯: {available_slots}개")
                    
                    # 우선순위 점수가 가장 높은 종목부터 정렬
                    potential_buy_stocks.sort(key=lambda x: x['score'], reverse=True)
                    
                    # 빈 슬롯만큼 최상위 종목 선정
                    selected_stocks_to_buy = potential_buy_stocks[:available_slots]
                    
                    if selected_stocks_to_buy:
                        log_msg = f"[{date.date()}] 최종 매수 선정 ({len(selected_stocks_to_buy)}개): "
                        log_msg += ", ".join([f"{s['ticker']}({s['score']:.2f})" for s in selected_stocks_to_buy])
                        logging.info(log_msg)

                        # 선정된 종목들의 매수 수량 계산 (균등 분할 방식)
                        for stock in selected_stocks_to_buy:
                            ticker = stock['ticker']
                            df = universe_dfs.get(ticker)
                            current_price = df.loc[date, 'close']
                            if current_price > 0:
                                # 균등 분할: 총자본을 최대 보유 종목수로 나눈 금액으로 매수
                                position_size_money = strategy_capital / self.max_positions
                                target_quantities[ticker] = int(position_size_money / current_price)

        return target_quantities


class TurtleStrategy(PortfolioStrategy):
    """개선된 터틀 트레이딩 전략"""
    def __init__(self, tickers, params):
        super().__init__(tickers, params)
        self.entry_period = params.get('entry_period', 20)
        self.exit_period = params.get('exit_period', 10)
        self.atr_period = params.get('atr_period', 20)
        self.risk_per_trade = params.get('risk_per_trade', 0.01)
        self.max_positions = params.get('max_positions', 10)
        self.stop_loss_atr_multiplier = params.get('stop_loss_atr_multiplier', 2.0)
        
        # 시나리오 테스트를 위한 파라미터 추가
        self.strategy_mode = params.get('strategy_mode', 'momentum') # 'momentum' or 'classic_turtle'
        self.test_type = params.get('test_type', 'static') # 'static' or 'crossing'
        self.momentum_threshold = params.get('momentum_threshold', 0.9)
        self.momentum_sl_threshold = params.get('momentum_sl_threshold', 0.4) # 손절매 모멘텀 추가
        self.min_volume_threshold = params.get('min_volume_threshold', 500_000_000) # 최소 거래대금 (예: 5억)

        # 시장 필터 강화
        self.use_market_filter = params.get('use_market_filter', True)
        self.use_dual_ma_filter = params.get('use_dual_ma_filter', False)
        self.market_filter_short_ma = params.get('market_filter_short_ma', 50)

        # 동적 손절매
        self.use_trailing_stop = params.get('use_trailing_stop', False)
        self.trailing_stop_atr_multiplier = params.get('trailing_stop_atr_multiplier', 3.0)

        # 우선순위 점수 가중치 (팩터 모델)
        self.score_weights = params.get('score_weights', {
            'ma_slope': 0.3,
            'price_ma': 0.2,
            'price_change': 0.2,
            'volume': 0.15,
            'rsi': 0.15
        })

        # 피라미딩(추가 매수) 설정
        self.use_pyramiding = params.get('use_pyramiding', False)
        self.pyramid_unit_atr = params.get('pyramid_unit_atr', 0.5)  # n * ATR 상승 시 한 유닛 추가
        self.max_units_per_position = params.get('max_units_per_position', 4)

        # 슬리피지 설정
        self.slippage_bps = params.get('slippage_bps', 0.0)  # bps 단위 슬리피지

        logging.info(f"TurtleStrategy Initialized: Mode={self.strategy_mode}, MaxPositions={self.max_positions}, TestType={self.test_type}, MomentumThreshold={self.momentum_threshold}, MomentumSL={self.momentum_sl_threshold}")
        logging.info(f"Execution Settings: SlippageBps={self.slippage_bps}")

    def _add_indicators(self, universe_dfs, tickers):
        logging.info("Adding indicators to all dataframes...")
        kospi_df = universe_dfs['KOSPI']
        kospi_df['200ma'] = kospi_df['close'].rolling(window=200).mean()
        kospi_df['50ma'] = kospi_df['close'].rolling(window=self.market_filter_short_ma).mean() # 단기 이평선 추가

        for ticker in tqdm(tickers, desc="Calculating Indicators"):
            df = universe_dfs.get(ticker)
            if df is None:
                continue

            df['entry_high'] = df['high'].shift(1).rolling(self.entry_period).max()
            df['exit_low'] = df['low'].shift(1).rolling(self.exit_period).min()
            # ATR 제거 - 균등 분할 방식 사용

            # --- MA_Kosdaqpi100_Bot_v1.py 로직 기반 신규 지표 추가 ---
            df['prev_close'] = df['close'].shift(1)

            # 이동평균선 (신호일 기준 전일 종가까지의 데이터로 계산되도록 shift(1))
            df['5ma'] = df['close'].rolling(window=5).mean().shift(1)
            df['20ma'] = df['close'].rolling(window=20).mean().shift(1)
            df['5ma_prev'] = df['5ma'].shift(1)      # 2일 전 MA (기울기 계산용)
            df['20ma_prev'] = df['20ma'].shift(1)    # 2일 전 MA (기울기 계산용)

            # 거래대금 이동평균 (유동성 필터용, 전일 기준)
            df['volume_ma'] = (df['volume'] * df['close']).rolling(window=20).mean().shift(1)

            # 팩터 모델용 지표
            df['volume_ma20'] = df['volume'].rolling(window=20).mean().shift(1)
            df['volume_ma60'] = df['volume'].rolling(window=60).mean().shift(1)
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)

            # 평균 모멘텀 (신호일 기준 전일 종가까지의 데이터로 계산)
            momentum_periods = [i * 20 for i in range(1, 11)]  # 20, 40, ..., 200
            for period in momentum_periods:
                # (어제 종가 > 1+period일 전 종가) 이면 1, 아니면 0
                df[f'Momentum_{period}'] = (df['close'].shift(1) > df['close'].shift(1 + period)).astype(int)

            momentum_columns = [f'Momentum_{period}' for period in momentum_periods]
            df['Average_Momentum'] = df[momentum_columns].sum(axis=1) / len(momentum_periods)
            df['Average_Momentum_prev'] = df['Average_Momentum'].shift(1)
            # --- 신규 지표 추가 완료 ---

        return universe_dfs
    def generate_signals(self, date, universe_dfs, tickers, current_holdings, strategy_capital, kospi_df):
        # 기본 상태: 현재 보유 종목을 그대로 유지
        target_quantities = {ticker: h['quantity'] for ticker, h in current_holdings.items()}

        # --- 1. 매도 신호 검사 ---
        pending_sales_count = 0
        for ticker in current_holdings:
            df = universe_dfs.get(ticker)
            if df is not None and date in df.index:
                # 1. 'classic_turtle' 모드: 추세 이탈 매도 (N-day low)
                if self.strategy_mode == 'classic_turtle':
                    if pd.notna(df.loc[date, 'exit_low']) and df.loc[date, 'close'] < df.loc[date, 'exit_low']:
                        target_quantities[ticker] = 0  # 전량 매도
                        pending_sales_count += 1
                        logging.info(f"[{date.date()}] 🐢 터틀 청산: {ticker}, N일 저가 하회")
                        continue

                # 2. 'momentum' 모드: 모멘텀 붕괴 손절
                elif self.strategy_mode == 'momentum':
                    if 'Average_Momentum' in df.columns and df.loc[date, 'Average_Momentum'] < self.momentum_sl_threshold:
                        target_quantities[ticker] = 0 # 전량 매도
                        pending_sales_count += 1
                        logging.info(f"[{date.date()}] 📉 모멘텀 청산: {ticker}, 모멘텀 점수 {df.loc[date, 'Average_Momentum']:.2f} < {self.momentum_sl_threshold}")
                        continue

        # --- 2. 신규 매수 신호 검사 ---
        # 매도 등으로 빈 슬롯이 생겼는지 확인
        effective_holdings_count = len(current_holdings) - pending_sales_count
        available_slots = self.max_positions - effective_holdings_count

        if available_slots > 0:
            # 시장 트렌드 필터
            kospi_above_200ma = False
            if date in kospi_df.index and pd.notna(kospi_df.loc[date, '200ma']):
                kospi_above_200ma = kospi_df.loc[date, 'close'] > kospi_df.loc[date, '200ma']
            
            # 듀얼 MA 필터 적용
            if self.use_dual_ma_filter:
                kospi_above_50ma = False
                if date in kospi_df.index and pd.notna(kospi_df.loc[date, '50ma']):
                    kospi_above_50ma = kospi_df.loc[date, 'close'] > kospi_df.loc[date, '50ma']
                
                is_bull_market = kospi_above_200ma and kospi_above_50ma
            else:
                is_bull_market = kospi_above_200ma

            # 시장 필터 사용 안 함 옵션 처리
            if not self.use_market_filter:
                is_bull_market = True

            if is_bull_market:
                potential_buy_stocks_data = []
                
                # 'momentum' 모드 로직
                if self.strategy_mode == 'momentum':
                    for ticker in tickers:
                        # 이미 보유하고 있는 종목은 신규 매수 후보에서 제외
                        if ticker in current_holdings:
                            continue

                        df = universe_dfs.get(ticker)

                        # 거래대금 필터
                        if df is None or date not in df.index or 'volume_ma' not in df.columns or df.loc[date, 'volume_ma'] < self.min_volume_threshold:
                            continue
                        
                        is_candidate = False
                        if self.test_type == 'static':
                            if pd.notna(df.loc[date, 'Average_Momentum']) and df.loc[date, 'Average_Momentum'] >= self.momentum_threshold:
                                is_candidate = True
                        elif self.test_type == 'crossing':
                            if pd.notna(df.loc[date, 'Average_Momentum']) and pd.notna(df.loc[date, 'Average_Momentum_prev']) and df.loc[date, 'Average_Momentum_prev'] < self.momentum_threshold and df.loc[date, 'Average_Momentum'] >= self.momentum_threshold:
                                is_candidate = True

                        if is_candidate:
                            # 우선순위 점수 계산에 필요한 팩터 값들 추출
                            ma5 = df.loc[date, '5ma']
                            ma5_prev = df.loc[date, '5ma_prev']
                            ma20 = df.loc[date, '20ma']
                            ma20_prev = df.loc[date, '20ma_prev']
                            prev_close = df.loc[date, 'prev_close']
                            prev_close_2 = df['close'].shift(2).loc[date]
                            volume_ma20 = df.loc[date, 'volume_ma20']
                            volume_ma60 = df.loc[date, 'volume_ma60']
                            rsi = df.loc[date, 'rsi']

                            if all(pd.notna([ma5, ma5_prev, ma20, ma20_prev, prev_close, prev_close_2, volume_ma20, volume_ma60, rsi])):
                                ma_slope = ((ma5 - ma5_prev) * 0.7 + (ma20 - ma20_prev) * 0.3)
                                price_ma_ratio = (prev_close / ma20 - 1)
                                price_change = (prev_close / prev_close_2 - 1)
                                volume_ratio = (volume_ma20 / volume_ma60) if volume_ma60 > 0 else 1.0
                                
                                potential_buy_stocks_data.append({
                                    'ticker': ticker,
                                    'ma_slope': ma_slope,
                                    'price_ma': price_ma_ratio,
                                    'price_change': price_change,
                                    'volume': volume_ratio,
                                    'rsi': rsi
                                })

                # 'classic_turtle' 모드 로직 (단순 진입이므로 팩터 점수 계산 없음)
                elif self.strategy_mode == 'classic_turtle':
                    for ticker in tickers:
                        if ticker in current_holdings:
                            continue
                        df = universe_dfs.get(ticker)

                        # 거래대금 필터
                        if df is None or date not in df.index or 'volume_ma' not in df.columns or df.loc[date, 'volume_ma'] < self.min_volume_threshold:
                            continue
                            
                        if pd.notna(df.loc[date, 'entry_high']) and pd.notna(df.loc[date, 'close']):
                            if df.loc[date, 'close'] > df.loc[date, 'entry_high']:
                                potential_buy_stocks_data.append({'ticker': ticker, 'final_score': 0})

                potential_buy_stocks = []
                if potential_buy_stocks_data:
                    # --- 순위 기반 다중 팩터 점수 계산 ---
                    if self.strategy_mode == 'momentum':
                        scores_df = pd.DataFrame(potential_buy_stocks_data)
                        
                        # 각 팩터별 순위 계산 (높을수록 좋음)
                        scores_df['ma_slope_rank'] = scores_df['ma_slope'].rank(pct=True)
                        scores_df['price_ma_rank'] = scores_df['price_ma'].rank(pct=True)
                        scores_df['price_change_rank'] = scores_df['price_change'].rank(pct=True)
                        scores_df['volume_rank'] = scores_df['volume'].rank(pct=True)
                        scores_df['rsi_rank'] = scores_df['rsi'].rank(pct=True)

                        # 가중치 적용하여 최종 점수 계산
                        weights = self.score_weights
                        scores_df['final_score'] = (
                            scores_df['ma_slope_rank'] * weights.get('ma_slope', 0) +
                            scores_df['price_ma_rank'] * weights.get('price_ma', 0) +
                            scores_df['price_change_rank'] * weights.get('price_change', 0) +
                            scores_df['volume_rank'] * weights.get('volume', 0) +
                            scores_df['rsi_rank'] * weights.get('rsi', 0)
                        )
                        
                        scores_df = scores_df.sort_values(by='final_score', ascending=False)
                        
                        # potential_buy_stocks 리스트 형식으로 변환
                        for _, row in scores_df.iterrows():
                            potential_buy_stocks.append({'ticker': row['ticker'], 'score': row['final_score']})

                    elif self.strategy_mode == 'classic_turtle':
                        # 터틀 모드는 별도 점수 없이 후보군 전체를 사용
                        potential_buy_stocks = [{'ticker': d['ticker'], 'score': 0} for d in potential_buy_stocks_data]

                if potential_buy_stocks:
                    logging.info(f"[{date.date()}] 매수 후보: {len(potential_buy_stocks)}개, 가능 슬롯: {available_slots}개")
                    
                    # 'momentum' 모드일 때만 점수가 의미 있음 (정렬은 이미 위에서 완료)
                    # if self.strategy_mode == 'momentum':
                    #     potential_buy_stocks.sort(key=lambda x: x['score'], reverse=True)
                    
                    # 빈 슬롯만큼 최상위 종목 선정
                    selected_stocks_to_buy = potential_buy_stocks[:available_slots]
                    
                    if selected_stocks_to_buy:
                        log_msg = f"[{date.date()}] 최종 매수 선정 ({len(selected_stocks_to_buy)}개): "
                        log_msg += ", ".join([f"{s['ticker']}({s['score']:.2f})" for s in selected_stocks_to_buy]) if self.strategy_mode == 'momentum' else ", ".join([s['ticker'] for s in selected_stocks_to_buy])
                        logging.info(log_msg)

                        # 선정된 종목들의 매수 수량 계산 (균등 분할 방식)
                        for stock in selected_stocks_to_buy:
                            ticker = stock['ticker']
                            df = universe_dfs.get(ticker)
                            current_price = df.loc[date, 'close']
                            if current_price > 0:
                                # 균등 분할: 총자본을 최대 보유 종목수로 나눈 금액으로 매수
                                position_size_money = strategy_capital / self.max_positions
                                target_quantities[ticker] = int(position_size_money / current_price)

                # --- 피라미딩: 보유 종목 추가 매수 신호 (고정 비율 방식) ---
                if self.use_pyramiding:
                    for ticker, holding in current_holdings.items():
                        df = universe_dfs.get(ticker)
                        if df is None or date not in df.index:
                            continue
                        price = df.loc[date, 'close']
                        if pd.isna(price) or price <= 0:
                            continue
                        units_count = holding.get('units_count', 1)
                        last_add_price = holding.get('last_add_price', holding.get('avg_price', price))
                        if units_count >= self.max_units_per_position:
                            continue
                        # 고정 비율 피라미딩: 5% 상승 시마다 추가 매수
                        price_increase_pct = (price - last_add_price) / last_add_price if last_add_price > 0 else 0
                        pyramid_threshold = 0.05  # 5% 상승 시 추가 매수
                        steps = int(price_increase_pct / pyramid_threshold)
                        if steps >= 1:
                            add_units = min(steps, self.max_units_per_position - units_count)
                            # 균등 분할 방식으로 수량 계산
                            position_size_money = strategy_capital / self.max_positions
                            add_qty = int(position_size_money / price) * add_units
                            # 목표 수량 상향
                            current_qty = target_quantities.get(ticker, holding['quantity'])
                            target_quantities[ticker] = current_qty + max(add_qty, 0)

        return target_quantities


# --- 4. 백테스팅 엔진 ---

def run_backtest(universe_dfs, tickers, strategy_class, strategy_params, initial_capital, start_date, end_date):
    """단일 전략 백테스트 실행"""
    
    # 공통 거래일 계산
    all_dates = pd.to_datetime(list(universe_dfs.values())[0].index)
    backtest_dates = all_dates[(all_dates >= pd.to_datetime(start_date)) & (all_dates <= pd.to_datetime(end_date))]
    
    # 리밸런싱 주기 설정
    rebalance_period = strategy_params.get('rebalance_period', 'daily')
    rebalance_dates = pd.Index([])
    if rebalance_period == 'daily':
        rebalance_dates = backtest_dates
    else:
        df_dates = pd.DataFrame(index=backtest_dates)
        if rebalance_period == 'weekly':
            df_dates['key'] = df_dates.index.strftime('%Y-%W')
            rebalance_dates = df_dates.groupby('key').head(1).index
        elif rebalance_period == 'monthly':
            df_dates['key'] = df_dates.index.strftime('%Y-%m')
            rebalance_dates = df_dates.groupby('key').head(1).index

    # 전략 인스턴스 생성 및 지표 계산
    strategy = strategy_class(tickers, strategy_params)
    universe_dfs = strategy._add_indicators(universe_dfs, tickers)
    
    # 상태 초기화
    cash = initial_capital
    equity_curve = pd.Series(index=backtest_dates, dtype=np.float64)
    portfolio = {}
    trades_pnl = [] # 거래별 손익 기록

    # 백테스팅 루프
    for date in tqdm(backtest_dates, desc=f"Turtle Strategy Backtest ({rebalance_period})"):
        # --- 손절매 및 동적 손절매 업데이트 (매일) ---
        for ticker, holding in list(portfolio.items()):
            df = universe_dfs.get(ticker)
            if df is None or date not in df.index:
                continue

            # 1. 일일 최고가 기준으로 포지션 최고가 업데이트
            current_high = df.loc[date, 'high']
            if pd.notna(current_high):
                holding['highest_price_since_buy'] = max(holding.get('highest_price_since_buy', 0), current_high)

            # 2. 동적 손절매 가격 계산 및 업데이트 (고정 비율 방식)
            if strategy.use_trailing_stop:
                # 고가 대비 10% 하락 시 손절 (트레일링 스탑)
                trailing_stop_price = holding['highest_price_since_buy'] * 0.9
                
                # 손절가는 상승만 가능 (기존 손절가보다 낮아지면 안 됨)
                holding['stop_loss_price'] = max(holding.get('stop_loss_price', 0), trailing_stop_price)

            # 3. 손절매 실행
            stop_loss_price = holding.get('stop_loss_price', 0)
            avg_price = holding.get('avg_price', 0)
            
            if stop_loss_price > 0 and avg_price > 0:
                if df.loc[date, 'low'] < stop_loss_price:
                    sell_qty = holding['quantity']
                    sell_price = stop_loss_price
                    
                    # 수익/손실 계산
                    pnl = (sell_price - avg_price) * sell_qty
                    pnl_pct = (sell_price / avg_price - 1) * 100 if avg_price > 0 else 0
                    icon = "🟢" if pnl >= 0 else "🔴"
                    
                    sell_value = sell_qty * sell_price
                    cash += sell_value * (1 - 0.00015 - 0.002) # 수수료/세금
                    logging.info(f"[{date.date()}] {icon} 손절매(TS): {ticker}, 가격: {sell_price:,.0f}, 수량: {sell_qty}주, 수익: {pnl:,.0f}원 ({pnl_pct:.2f}%)")
                    del portfolio[ticker]
                    trades_pnl.append(pnl) # 손절매 PnL 기록

        # 현재 포트폴리오 가치 계산
        portfolio_value = 0
        for ticker, holding in portfolio.items():
            df = universe_dfs.get(ticker)
            if df is not None and date in df.index:
                portfolio_value += holding['quantity'] * df.loc[date, 'close']
        
        # 일별 자산 기록
        current_equity = cash + portfolio_value
        equity_curve.loc[date] = current_equity

        # 리밸런싱일에만 신호 생성 및 거래 실행
        if date in rebalance_dates:
            target_quantities = strategy.generate_signals(
                date,
                universe_dfs,
                tickers,
                portfolio,
                current_equity, # 현재 총 자산 기준
                universe_dfs['KOSPI']
            )

            # 현재 보유량
            current_holdings = {ticker: h['quantity'] for ticker, h in portfolio.items()}

            # 매도/비중 축소
            for ticker, current_qty in list(current_holdings.items()):
                target_qty = target_quantities.get(ticker, 0)
                if current_qty > target_qty:
                    sell_qty = current_qty - target_qty
                    df = universe_dfs.get(ticker)
                    if df is not None and date in df.index:
                        price = df.loc[date, 'close']
                        # 매도 체결가에 슬리피지 적용 (매도는 불리하게 낮게 체결)
                        if strategy.slippage_bps and strategy.slippage_bps != 0:
                            price = price * (1 - (strategy.slippage_bps / 10000.0))
                        avg_price = portfolio[ticker]['avg_price']

                        # 수익/손실 계산
                        pnl = (price - avg_price) * sell_qty
                        pnl_pct = (price / avg_price - 1) * 100 if avg_price > 0 else 0
                        icon = "🟢" if pnl >= 0 else "🔴"
                        log_text = "청산" if target_qty == 0 else "비중축소"
                        
                        sell_value = sell_qty * price
                        cash += sell_value * (1 - 0.00015 - 0.002)
                        portfolio[ticker]['quantity'] -= sell_qty
                        if portfolio[ticker]['quantity'] <= 0:
                            del portfolio[ticker]
                        logging.info(f"[{date.date()}] {icon} 매도({log_text}): {ticker}, 가격: {price:,.0f}, 수량: {sell_qty}주, 수익: {pnl:,.0f}원 ({pnl_pct:.2f}%)")
                        trades_pnl.append(pnl) # 매도 PnL 기록

            # 매수/비중 확대
            for ticker, target_qty in target_quantities.items():
                current_qty = current_holdings.get(ticker, 0)
                if target_qty > current_qty:
                    buy_qty = target_qty - current_qty
                    df = universe_dfs.get(ticker)
                    if df is not None and date in df.index:
                        price = df.loc[date, 'close']
                        # 매수 체결가에 슬리피지 적용 (매수는 불리하게 높게 체결)
                        if strategy.slippage_bps and strategy.slippage_bps != 0:
                            price = price * (1 + (strategy.slippage_bps / 10000.0))
                        buy_value = buy_qty * price
                        
                        if cash >= buy_value * (1 + 0.00015):
                            cash -= buy_value * (1 + 0.00015)
                            # 고정 비율 손절 (매수가 대비 10% 하락 시 손절)
                            stop_loss_price = price * 0.9
                            
                            if ticker in portfolio: # 비중 확대
                                old_qty = portfolio[ticker]['quantity']
                                old_avg_price = portfolio[ticker]['avg_price']
                                new_avg_price = ((old_avg_price * old_qty) + (price * buy_qty)) / (old_qty + buy_qty)
                                portfolio[ticker]['quantity'] += buy_qty
                                portfolio[ticker]['avg_price'] = new_avg_price
                                portfolio[ticker]['stop_loss_price'] = stop_loss_price
                                # 피라미딩 유닛 관리
                                if strategy.use_pyramiding:
                                    portfolio[ticker]['units_count'] = portfolio[ticker].get('units_count', 1) + 1
                                    portfolio[ticker]['last_add_price'] = price
                            else: # 신규 진입
                                portfolio[ticker] = {
                                    'quantity': buy_qty,
                                    'avg_price': price,
                                    'stop_loss_price': stop_loss_price,
                                    'highest_price_since_buy': price,
                                }
                                if strategy.use_pyramiding:
                                    portfolio[ticker]['units_count'] = 1
                                    portfolio[ticker]['last_add_price'] = price
                            logging.info(f"[{date.date()}] 매수(진입/확대): {ticker}, 가격: {price:,.0f}, 수량: {buy_qty}주, 손절가: {stop_loss_price:,.0f}")
                        
    return equity_curve, trades_pnl

# --- 5. 성과 분석 및 시각화 ---

def calculate_performance(equity_curve):
    """수익률 곡선을 바탕으로 주요 성과 지표를 계산합니다."""
    if equity_curve.empty or equity_curve.iloc[0] == 0:
        return 0.0, 0.0
    
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100
    rolling_max = equity_curve.cummax()
    drawdown = equity_curve / rolling_max - 1
    mdd = drawdown.min() * 100
    
    return total_return, mdd


def calculate_detailed_performance(equity_curve, trades, num_years):
    """상세 성과 지표 계산"""
    if equity_curve.empty or not trades:
        return {
            "Total Return": 0,
            "CAGR": 0,
            "MDD": 0,
            "Sharpe Ratio": 0,
            "Win Rate": 0,
            "Profit Factor": 0,
            "Total Trades": 0
        }

    # 1. 총 수익률
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100

    # 2. 연평균 복리 수익률 (CAGR)
    cagr = ((equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (1 / num_years) - 1) * 100 if num_years > 0 else 0

    # 3. 최대 낙폭 (MDD)
    roll_max = equity_curve.cummax()
    daily_drawdown = equity_curve / roll_max - 1.0
    mdd = daily_drawdown.cummin().iloc[-1] * 100

    # 4. 샤프 지수 (Sharpe Ratio)
    daily_returns = equity_curve.pct_change().dropna()
    sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() != 0 else 0

    # 5. 거래 기반 지표
    total_trades = len(trades)
    winning_trades = [t for t in trades if t > 0]
    losing_trades = [t for t in trades if t < 0]
    
    win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
    
    total_profit = sum(winning_trades)
    total_loss = abs(sum(losing_trades))
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

    return {
        "Total Return": total_return,
        "CAGR": cagr,
        "MDD": mdd,
        "Sharpe Ratio": sharpe_ratio,
        "Win Rate": win_rate,
        "Profit Factor": profit_factor,
        "Total Trades": total_trades
    }


def plot_results(equity_curve, title):
    """백테스트 결과를 그래프로 시각화하고 저장합니다."""
    setup_korean_font()
    total_return, mdd = calculate_performance(equity_curve)

    plt.figure(figsize=(15, 8))
    plt.plot(equity_curve.index, equity_curve, label=f"Turtle Strategy (Return: {total_return:.2f}%, MDD: {mdd:.2f}%)")
    plt.title(title, fontsize=16)
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Equity', fontsize=12)
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.legend(fontsize=12)
    plt.yscale('log')
    formatter = FuncFormatter(lambda y, _: f'{int(y):,}')
    plt.gca().yaxis.set_major_formatter(formatter)
    plt.tight_layout()
    
    img_path = os.path.join(log_dir, 'turtle_backtester_results.png')
    plt.savefig(img_path)
    logging.info(f"📊 결과 그래프 저장 완료: {img_path}")
    # plt.show() # 로컬 실행 시 활성화


# --- 6. 메인 실행 블록 ---

if __name__ == "__main__":
    # 백테스트 파라미터 설정
    START_DATE = '2018-01-01'
    END_DATE = '2025-09-01'
    INITIAL_CAPITAL = 100_000_000
    DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
    
    # --- 7. 최적화 모드 설정 ---
    OPTIMIZATION_MODE = False # True로 설정 시 최적화 실행, False 시 단일 백테스트 실행

    # 데이터 로드 (공통)
    universe_dfs, tickers = load_universe_data(DATA_DIR)

    if OPTIMIZATION_MODE:
        logging.info("="*80)
        logging.info("⚙️ 전략 파라미터 최적화를 시작합니다.")
        logging.info("="*80)

        # === 최적화할 파라미터 그리드 설정 ===
        # 1. 모멘텀 전략 테스트용 (리밸런싱 주기 제거 - 빈 슬롯 있을 때만 매수)
        param_grid = {
            'strategy_mode': ['momentum'],
            'momentum_threshold': [0.6, 0.65, 0.7, 0.75],
            'momentum_sl_threshold': [0.35, 0.4, 0.45, 0.5],
            'max_positions': [10, 15, 20],
            'min_volume_threshold': [500_000_000],
            'use_dual_ma_filter': [False],
            'rebalance_period': ['daily'],
            'use_trailing_stop': [False],
            'use_pyramiding': [False],
            'max_units_per_position': [4],
            'score_weights_set': [0],
            'slippage_bps': [0.0]
        }

        # # 2. 정통 터틀 전략 테스트용 (위 모멘텀 테스트 시 주석 처리)
        # param_grid = {
        #     'strategy_mode': ['classic_turtle'],
        #     'entry_period': [20, 55],
        #     'exit_period': [10, 20],
        #     'max_positions': [20, 30]
        # }
        
        keys, values = zip(*param_grid.items())
        param_combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
        
        results = []
        base_params = {
            'entry_period': 55, 'exit_period': 20,
            'test_type': 'crossing', 'momentum_threshold': 0.9, 'momentum_sl_threshold': 0.4,
            'min_volume_threshold': 500_000_000, 'use_dual_ma_filter': False, 'market_filter_short_ma': 50,
            'rebalance_period': 'daily', 'use_trailing_stop': False,
            'use_pyramiding': False, 'max_units_per_position': 4,
            'score_weights': {'ma_slope': 0.3, 'price_ma': 0.2, 'price_change': 0.2, 'volume': 0.15, 'rsi': 0.15},
            'slippage_bps': 0.0
        }

        weight_presets = {
            0: {'ma_slope': 0.3, 'price_ma': 0.2, 'price_change': 0.2, 'volume': 0.15, 'rsi': 0.15},
            1: {'ma_slope': 0.2, 'price_ma': 0.25, 'price_change': 0.25, 'volume': 0.15, 'rsi': 0.15}
        }

        for i, params_to_test in enumerate(param_combinations):
            test_params = base_params.copy()
            test_params.update(params_to_test)

            # 가중치 프리셋 적용
            if 'score_weights_set' in test_params:
                preset_key = test_params['score_weights_set']
                test_params['score_weights'] = weight_presets.get(preset_key, base_params['score_weights'])
                del test_params['score_weights_set']

            logging.info(f"\n--- [{i+1}/{len(param_combinations)}] Optimizing with: {params_to_test} ---")
            
            # 각 테스트는 독립적인 데이터 객체를 사용 (안전성)
            universe_dfs_copy = copy.deepcopy(universe_dfs)

            equity_curve, trades = run_backtest(
                universe_dfs_copy, tickers, TurtleStrategy, test_params,
                INITIAL_CAPITAL, START_DATE, END_DATE
            )

            if equity_curve is not None and not equity_curve.empty:
                num_years = (pd.to_datetime(END_DATE) - pd.to_datetime(START_DATE)).days / 365.25
                performance = calculate_detailed_performance(equity_curve, trades, num_years)
                
                result_row = params_to_test.copy()
                result_row['CAGR'] = performance['CAGR']
                result_row['MDD'] = performance['MDD']
                result_row['Sharpe'] = performance['Sharpe Ratio']
                results.append(result_row)
        
        if results:
            results_df = pd.DataFrame(results).sort_values(by='CAGR', ascending=False)
            logging.info("\n" + "="*80)
            logging.info("🏆 최적화 결과 요약 (CAGR 순 정렬)")
            logging.info("="*80)
            logging.info("\n" + results_df.to_string())
            logging.info("="*80)

    else:
        # --- 36번 베스트 파라미터 (CAGR 25.71%) ---
        best_params = {
            'entry_period': 55,
            'exit_period': 20,
            'max_positions': 15,  # 36번: 15
            'strategy_mode': 'momentum', 
            'test_type': 'crossing', 
            'momentum_threshold': 0.65,  # 36번: 0.65
            'momentum_sl_threshold': 0.5,  # 36번: 0.5
            'min_volume_threshold': 500_000_000,
            'use_market_filter': True,
            'use_dual_ma_filter': False,  # 36번: False
            'rebalance_period': 'daily',  # 36번: daily
            'use_trailing_stop': False,
            'score_weights': {'ma_slope': 0.3, 'price_ma': 0.2, 'price_change': 0.2, 'volume': 0.15, 'rsi': 0.15},  # 36번: score_weights_set 0
            'use_pyramiding': False,      # 가지고 있는 자본보다 많이 사용해서 False처리함.
            'max_units_per_position': 4,  # 가지고 있는 자본보다 많이 사용해서 False처리함.
            'slippage_bps': 0.0
        }

        if universe_dfs:
            logging.info("="*80)
            log_title = "🐢 터틀 전략 (정통)" if best_params['strategy_mode'] == 'classic_turtle' else "📈 터틀 전략 (모멘텀 0.9 상향돌파)"
            logging.info(log_title)
            logging.info(f"백테스트 기간: {START_DATE} ~ {END_DATE}")
            logging.info(f"초기 자본금: {INITIAL_CAPITAL:,.0f}원")
            logging.info(f"최대 보유 종목 수: {best_params['max_positions']}개")
            logging.info("="*80)

            equity_curve, trades = run_backtest(
                universe_dfs,
                tickers,
                TurtleStrategy,
                best_params,
                INITIAL_CAPITAL,
                START_DATE,
                END_DATE
            )

            if equity_curve is not None and not equity_curve.empty:
                num_years = (pd.to_datetime(END_DATE) - pd.to_datetime(START_DATE)).days / 365.25
                performance = calculate_detailed_performance(equity_curve, trades, num_years)
                
                logging.info("="*50)
                logging.info("✅ 백테스트 완료! 최종 성적 요약:")
                logging.info(f"테스트 기간: {START_DATE} ~ {END_DATE}")
                logging.info("="*50)
                logging.info(f"총 수익률 (Total Return) : {performance['Total Return']:.2f}%")
                logging.info(f"연평균 복리 수익률 (CAGR): {performance['CAGR']:.2f}%")
                logging.info(f"최대 낙폭 (MDD)         : {performance['MDD']:.2f}%")
                logging.info(f"샤프 지수 (Sharpe Ratio)  : {performance['Sharpe Ratio']:.2f}")
                logging.info(f"승률 (Win Rate)         : {performance['Win Rate']:.2f}%")
                logging.info(f"수익/손실 비율 (P/F)    : {performance['Profit Factor']:.2f}")
                logging.info(f"총 거래 횟수            : {performance['Total Trades']}회")
                logging.info("="*50)
                
                plot_title = "Final Turtle Strategy (Classic)" if best_params['strategy_mode'] == 'classic_turtle' else "Final Turtle Strategy (Momentum 0.9 Crossing)"
                plot_results(equity_curve, plot_title)
            else:
                logging.error("❌ 백테스트 실행에 실패했거나 결과 데이터가 없습니다.")
        else:
            logging.error("❌ 데이터를 로드할 수 없어 백테스트를 종료합니다.")
