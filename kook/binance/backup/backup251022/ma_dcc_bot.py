"""
통합 전략 바이낸스 봇 (15분봉)

=== 사용된 기술적 지표 및 전략 ===

1. 이동평균선 (Moving Average)
   - SMA Short: 단기 이동평균선 (3, 6, 9, 12, 15)
   - SMA Long: 장기 이동평균선 (20, 30, 40, 50)
   - 역할: 추세 방향 판단
   - 신호: 단기선이 장기선을 상향돌파 → 롱 신호, 하향돌파 → 숏 신호

2. 던키안 채널 (Donchian Channel)
   - DCC Period: 25 (고정)
   - DCC High: 25기간 최고가
   - DCC Low: 25기간 최저가
   - DCC Middle: (최고가 + 최저가) / 2
   - 역할: 변동성과 돌파 신호 판단
   - 롱 조건: 현재가 > DCC Middle & 현재가 > DCC Low * 1.02
   - 숏 조건: 현재가 < DCC Middle & 현재가 < DCC High * 0.98

3. RSI (Relative Strength Index)
   - 기간: 14 (고정)
   - 계산: RSI = 100 - (100 / (1 + RS))
   - RS = 평균 상승폭 / 평균 하락폭
   - 역할: 과매수/과매도 구간 판단
   - 롱 조건: RSI < 70 (과매수 아님)
   - 숏 조건: RSI > 30 (과매도 아님)
   - 청산 조건: 롱 RSI > 80, 숏 RSI < 20

4. 통합 전략 특징
   - 롱/숏 동시 진입 방지: 충돌 신호 시 우선순위 적용
   - 볼륨 필터 제거: 2025년 시장 특성 고려
   - 수수료 고려: 진입/청산 시 각각 0.05% 수수료 적용
   - 레버리지: 20배 (선물 거래 기준)

5. 실시간 거래 방식
   - 데이터: 15분봉 실시간 데이터
   - 신호 생성: 이동평균 + 던키안 채널 + RSI
   - 포지션 관리: 단일 포지션 유지 (롱 또는 숏)

6. 리스크 관리
   - 최대 낙폭(MDD) 추적
   - 승률 계산
   - 거래 빈도 모니터링
   - 롱/숏 거래 비율 분석

=== 파라미터 최적화 범위 ===
- SMA Short: 3, 6, 9, 12, 15 (5개)
- SMA Long: 20, 30, 40, 50 (4개)  
- DCC Period: 25 (고정)
- 총 조합: 5 × 4 × 1 = 20개

=== 전략 로직 ===
1. 진입 조건 (모두 만족해야 함):
   - 이동평균선 크로스오버
   - 던키안 채널 조건
   - RSI 과매수/과매도 아님

2. 청산 조건 (하나라도 만족하면):
   - 반대 신호 발생
   - RSI 극값 도달 (80/20)

3. 동시 진입 방지:
   - 롱/숏 신호 동시 발생 시 충돌 처리
   - 우선순위에 따른 신호 선택
"""

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import ccxt
import time
import datetime as dt
import pandas as pd
import numpy as np
import json
import talib
import gc
import psutil
import warnings
import logging
from itertools import product

import myBinance
import ende_key  #암복호화키
import my_key    #업비트 시크릿 액세스키
import telegram_sender

# ========================= 로깅 설정 =========================
script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, "..", "logs")
os.makedirs(logs_dir, exist_ok=True)

log_file = os.path.join(logs_dir, f"ml_bot_{dt.datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========================= 전략 설정 =========================
SMA_SHORT = 3    # 단기 이동평균
SMA_LONG = 40    # 장기 이동평균
DCC_PERIOD = 25  # 던키안 채널 기간
RSI_PERIOD = 14  # RSI 기간
RSI_OVERBOUGHT = 70  # RSI 과매수 기준
RSI_OVERSOLD = 30    # RSI 과매도 기준
RSI_EXTREME_HIGH = 80  # RSI 극값 상한
RSI_EXTREME_LOW = 20   # RSI 극값 하한

# ========================= 최적화 함수 =========================
def optimize_ma_parameters(binanceX, symbol, days_back=365):
    """1년치 데이터로 최적 MA 파라미터 찾기"""
    logger.info(f"🔍 {days_back}일치 데이터로 MA 파라미터 최적화 시작...")
    
    try:
        # 1년치 데이터 가져오기 (10분봉으로 직접 가져오기)
        end_time = dt.datetime.now()
        start_time = end_time - dt.timedelta(days=days_back)
        
        # 15분봉 데이터 직접 가져오기
        df = myBinance.GetOhlcv(binanceX, symbol, '15m')
        
        if len(df) < 100:
            logger.warning("데이터가 부족합니다. 기본값 사용.")
            return SMA_SHORT, SMA_LONG
        
        logger.info(f"📊 최적화용 데이터: {len(df)}개 캔들 (15분봉)")
        
        best_score = -999999
        best_params = None
        
        # MA 파라미터 범위
        ma_short_range = [3, 6, 9, 12]
        ma_long_range = [20, 30, 40]
        
        total_combinations = len(ma_short_range) * len(ma_long_range)
        logger.info(f"총 {total_combinations}개 조합 테스트 중...")
        
        for ma_short, ma_long in product(ma_short_range, ma_long_range):
            if ma_short >= ma_long:
                continue
                
            try:
                # 지표 계산
                test_df = calculate_indicators_with_params(df, ma_short, ma_long, DCC_PERIOD)
                test_df = generate_signals(test_df)
                
                # 백테스트 실행
                result = run_backtest_simple(test_df)
                
                # 점수 계산 (수익률 - 최대낙폭)
                score = result['total_return'] - result['max_drawdown']
                
                if score > best_score:
                    best_score = score
                    best_params = (ma_short, ma_long)
                    logger.info(f"새로운 최고 점수: {score:.2f} (MA: {ma_short}/{ma_long}, 수익률: {result['total_return']:.2f}%, MDD: {result['max_drawdown']:.2f}%)")
                    
            except Exception as e:
                continue
        
        if best_params:
            logger.info(f"✅ 최적 파라미터: MA_SHORT={best_params[0]}, MA_LONG={best_params[1]}")
            return best_params[0], best_params[1]
        else:
            logger.warning("최적화 실패. 기본값 사용.")
            return SMA_SHORT, SMA_LONG
            
    except Exception as e:
        logger.error(f"최적화 중 오류: {e}")
        return SMA_SHORT, SMA_LONG

def calculate_indicators_with_params(df, ma_short, ma_long, dcc_period):
    """파라미터를 받아서 지표 계산"""
    df = df.copy()
    
    # 이동평균선
    df['sma_short'] = talib.SMA(df['close'], timeperiod=ma_short)
    df['sma_long'] = talib.SMA(df['close'], timeperiod=ma_long)
    
    # 던키안 채널
    df['dcc_high'] = df['high'].rolling(dcc_period).max()
    df['dcc_low'] = df['low'].rolling(dcc_period).min()
    df['dcc_middle'] = (df['dcc_high'] + df['dcc_low']) / 2
    
    # RSI
    df['rsi'] = talib.RSI(df['close'], timeperiod=RSI_PERIOD)
    
    return df

def run_backtest_simple(df):
    """간단한 백테스트 실행"""
    df = df.dropna()
    
    if len(df) == 0:
        return {'total_return': 0.0, 'max_drawdown': 0.0}
    
    position = None
    entry_price = 0
    trades = []
    capital = 10000
    
    for i, (timestamp, row) in enumerate(df.iterrows()):
        # 진입 신호
        if position is None:
            if row['long_signal']:
                position = 'long'
                entry_price = row['close']
            elif row['short_signal']:
                position = 'short'
                entry_price = row['close']
        
        # 청산 신호
        elif position == 'long':
            if row['short_signal'] or row['rsi'] > 80:
                exit_price = row['close']
                pnl = calculate_pnl_simple(entry_price, exit_price, capital, 'long')
                capital += pnl
                trades.append({'type': 'long', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl})
                position = None
                
        elif position == 'short':
            if row['long_signal'] or row['rsi'] < 20:
                exit_price = row['close']
                pnl = calculate_pnl_simple(entry_price, exit_price, capital, 'short')
                capital += pnl
                trades.append({'type': 'short', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl})
                position = None
    
    # 결과 계산
    if len(trades) > 0:
        total_return = (capital - 10000) / 10000 * 100
        max_drawdown = calculate_max_drawdown_simple(trades)
    else:
        total_return = 0.0
        max_drawdown = 0.0
    
    return {
        'total_return': total_return,
        'max_drawdown': max_drawdown
    }

def calculate_pnl_simple(entry_price, exit_price, capital, position_type):
    """간단한 PnL 계산"""
    fee_rate = 0.001  # 0.1% 수수료
    
    if position_type == 'long':
        entry_with_fee = entry_price * (1 + fee_rate)
        exit_with_fee = exit_price * (1 - fee_rate)
        amount = capital / entry_with_fee
        pnl = (exit_with_fee - entry_with_fee) * amount
    else:  # short
        entry_with_fee = entry_price * (1 - fee_rate)
        exit_with_fee = exit_price * (1 + fee_rate)
        amount = capital / entry_with_fee
        pnl = (entry_with_fee - exit_with_fee) * amount
    
    return pnl

def calculate_max_drawdown_simple(trades):
    """최대 낙폭 계산"""
    if not trades:
        return 0.0
    
    capital_series = [10000]
    for trade in trades:
        capital_series.append(capital_series[-1] + trade['pnl'])
    
    capital_series = np.array(capital_series)
    peak = np.maximum.accumulate(capital_series)
    drawdown = (peak - capital_series) / peak * 100
    
    return np.max(drawdown)

# ========================= 메모리 관리 유틸리티 =========================
def cleanup_memory():
    """메모리 정리 함수"""
    try:
        collected = gc.collect()
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        logger.info(f"메모리 정리 완료: {collected}개 객체 수집, 현재 사용량: {memory_mb:.2f} MB")
        return memory_mb
    except Exception as e:
        logger.error(f"메모리 정리 중 오류: {e}")
        return 0

def cleanup_dataframes(*dataframes):
    """데이터프레임들 명시적 삭제"""
    for df in dataframes:
        if df is not None:
            try:
                del df
            except:
                pass

# ========================= 기술적 지표 계산 함수 =========================
def calculate_indicators(df: pd.DataFrame, ma_short=None, ma_long=None, dcc_period=None) -> pd.DataFrame:
    """통합 전략용 기술적 지표 계산"""
    df = df.copy()
    
    # 파라미터 설정 (기본값 사용)
    ma_short = ma_short or SMA_SHORT
    ma_long = ma_long or SMA_LONG
    dcc_period = dcc_period or DCC_PERIOD
        
    # 이동평균선
    df['sma_short'] = talib.SMA(df['close'], timeperiod=ma_short)
    df['sma_long'] = talib.SMA(df['close'], timeperiod=ma_long)
    
    # 던키안 채널
    df['dcc_high'] = df['high'].rolling(dcc_period).max()
    df['dcc_low'] = df['low'].rolling(dcc_period).min()
    df['dcc_middle'] = (df['dcc_high'] + df['dcc_low']) / 2
    
    # RSI
    df['rsi'] = talib.RSI(df['close'], timeperiod=RSI_PERIOD)
        
    return df

def generate_signals(df: pd.DataFrame, params=None) -> pd.DataFrame:
    """통합 전략 신호 생성"""
    # 파라미터 설정
    rsi_overbought = params.get('rsi_overbought', RSI_OVERBOUGHT) if params else RSI_OVERBOUGHT
    rsi_oversold = params.get('rsi_oversold', RSI_OVERSOLD) if params else RSI_OVERSOLD
    
    # 롱 신호
    long_ma_signal = (df['sma_short'] > df['sma_long']) & (df['sma_short'].shift(1) <= df['sma_long'].shift(1))
    long_dcc_signal = (df['close'] > df['dcc_middle']) & (df['close'] > df['dcc_low'] * 1.02)
    long_rsi_signal = df['rsi'] < rsi_overbought
    
    # 숏 신호
    short_ma_signal = (df['sma_short'] < df['sma_long']) & (df['sma_short'].shift(1) >= df['sma_long'].shift(1))
    short_dcc_signal = (df['close'] < df['dcc_middle']) & (df['close'] < df['dcc_high'] * 0.98)
    short_rsi_signal = df['rsi'] > rsi_oversold
    
    # 최종 신호
    long_signal = long_ma_signal & long_dcc_signal & long_rsi_signal
    short_signal = short_ma_signal & short_dcc_signal & short_rsi_signal
    
    # 동시 진입 방지
    conflict_mask = long_signal & short_signal
    long_signal = long_signal & ~conflict_mask
    short_signal = short_signal & ~conflict_mask
    
    df['long_signal'] = long_signal
    df['short_signal'] = short_signal
    df['conflict_count'] = conflict_mask.sum()
    
    return df

def viewlist(msg, amt_s=0, amt_l=0, entryPrice_s=0, entryPrice_l=0):
    # 숏 포지션 정보
    if abs(amt_s) > 0 and entryPrice_s > 0:
        revenue_rate_s = (entryPrice_s - coin_price) / entryPrice_s * 100.0
        msg += f"\n[숏] 진입가: {entryPrice_s:.2f}, 수량: {abs(amt_s):.3f}, 수익률: {revenue_rate_s:.2f}%"
    
    # 롱 포지션 정보
    if abs(amt_l) > 0 and entryPrice_l > 0:
        revenue_rate_l = (coin_price - entryPrice_l) / entryPrice_l * 100.0
        msg += f"\n[롱] 진입가: {entryPrice_l:.2f}, 수량: {amt_l:.3f}, 수익률: {revenue_rate_l:.2f}%"
    
    telegram_sender.SendMessage(msg)

# ========================= 메인 로직 시작 =========================
logger.info("=" * 80)
logger.info("MA DCC Bot - 바이낸스 양방향 전략 (시작)")
logger.info("=" * 80)

#암복호화 클래스 객체를 미리 생성한 키를 받아 생성한다.
simpleEnDecrypt = myBinance.SimpleEnDecrypt(ende_key.ende_key)
#암호화된 액세스키와 시크릿키를 읽어 복호화 한다.
Binance_AccessKey = simpleEnDecrypt.decrypt(my_key.binance_access)
Binance_ScretKey = simpleEnDecrypt.decrypt(my_key.binance_secret)
# binance 객체 생성
binanceX = ccxt.binance(config={
    'apiKey': Binance_AccessKey, 
    'secret': Binance_ScretKey,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
        'adjustForTimeDifference': True,
    }
})

# 봇 시작 시 서버 시간과 동기화
logger.info("서버 시간과 동기화를 시도합니다...")
try:
    binanceX.load_time_difference()
    original_offset = binanceX.options.get('timeDifference', 0)
    safety_margin = -1000  # 1초 여유를 두어 타임스탬프 오류 방지
    final_offset = original_offset + safety_margin
    binanceX.options['timeDifference'] = final_offset
    logger.info(f"서버 시간 동기화 완료: 오프셋 {final_offset}ms")
except Exception as e:
    logger.critical(f"시간 동기화 실패: {e}")
    sys.exit(1)

#나의 코인
Coin_Ticker_List = ['BTC/USDT']
logger.info("\n-- START ------------------------------------------------------------------------------------------\n")

# 초기 메모리 정리
initial_memory = cleanup_memory()

dic = dict()
info_file_path = os.path.join(os.path.dirname(__file__), "ma_dcc_bot.json")

#잔고 데이타 가져오기 
balance = binanceX.fetch_balance(params={"type": "future"})
time.sleep(0.1)

# JSON 파일 존재 여부 확인
json_exists = os.path.exists(info_file_path)
optimization_needed = False

try:
    if json_exists:
        with open(info_file_path, 'r') as json_file:
            dic = json.load(json_file)
        
        # MA 파라미터가 없거나 기본값인 경우 최적화 필요
        if "params" not in dic or "ma_short" not in dic.get("params", {}) or "ma_long" not in dic.get("params", {}):
            optimization_needed = True
            logger.info("MA 파라미터가 없습니다. 최적화가 필요합니다.")
        # 6개월마다 재최적화 체크
        elif "optimization_date" in dic:
            last_optimization = dt.datetime.fromisoformat(dic["optimization_date"])
            days_since_optimization = (dt.datetime.now() - last_optimization).days
            if days_since_optimization >= 180:  # 6개월 = 180일
                optimization_needed = True
                logger.info(f"6개월 경과로 재최적화 필요 (마지막 최적화: {days_since_optimization}일 전)")
    else:
        optimization_needed = True
        logger.info("JSON 파일이 없습니다. 초기 설정 및 최적화가 필요합니다.")
        
    # 기본값 설정
    if "yesterday" not in dic:
        dic["yesterday"] = 0
    if "today" not in dic:
        dic["today"] = 0
    if "start_money" not in dic:
        dic["start_money"] = float(balance['USDT']['total'])
    if "my_money" not in dic:
        dic["my_money"] = float(balance['USDT']['total'])
    if "long_position" not in dic:
        dic["long_position"] = {"entry_price": 0, "amount": 0}
    if "short_position" not in dic:
        dic["short_position"] = {"entry_price": 0, "amount": 0}
    
    # 기본 파라미터 설정
    if "params" not in dic:
        dic["params"] = {
            'ma_short': SMA_SHORT,
            'ma_long': SMA_LONG,
            'dcc_period': DCC_PERIOD,
            'rsi_period': RSI_PERIOD,
            'rsi_overbought': RSI_OVERBOUGHT,
            'rsi_oversold': RSI_OVERSOLD,
            'rsi_extreme_high': RSI_EXTREME_HIGH,
            'rsi_extreme_low': RSI_EXTREME_LOW
        }
        
except Exception as e:
    logger.info("Exception by First")
    optimization_needed = True
    dic["yesterday"] = 0
    dic["today"] = 0
    dic["start_money"] = float(balance['USDT']['total'])
    dic["my_money"] = float(balance['USDT']['total'])
    dic["long_position"] = {
        "entry_price": 0,
        "amount": 0
    }
    dic["short_position"] = {
        "entry_price": 0,
        "amount": 0
    }
    dic["params"] = {
        'ma_short': SMA_SHORT,
        'ma_long': SMA_LONG,
        'dcc_period': DCC_PERIOD,
        'rsi_period': RSI_PERIOD,
        'rsi_overbought': RSI_OVERBOUGHT,
        'rsi_oversold': RSI_OVERSOLD,
        'rsi_extreme_high': RSI_EXTREME_HIGH,
        'rsi_extreme_low': RSI_EXTREME_LOW
    }

logger.info(f"balance['USDT'] : {balance['USDT']}")

logger.info(f"포지션 정보는 바이낸스 API에서 직접 가져옵니다")

# ========================= 최적화 실행 =========================
if optimization_needed:
    logger.info("🚀 MA 파라미터 최적화를 시작합니다...")
    try:
        # 최적 MA 파라미터 찾기
        optimal_ma_short, optimal_ma_long = optimize_ma_parameters(binanceX, Coin_Ticker_List[0])
        
        # params에 최적 파라미터 저장
        dic["params"]["ma_short"] = optimal_ma_short
        dic["params"]["ma_long"] = optimal_ma_long
        dic["params"]["dcc_period"] = DCC_PERIOD
        dic["optimization_date"] = dt.datetime.now().isoformat()
        
        # JSON 파일 저장
        with open(info_file_path, 'w') as outfile:
            json.dump(dic, outfile, indent=4, ensure_ascii=False)
        
        logger.info(f"✅ 최적화 완료! MA_SHORT={optimal_ma_short}, MA_LONG={optimal_ma_long}")
        
        # 최적화 유형에 따른 메시지
        if "optimization_date" in dic:
            telegram_sender.SendMessage(f"🔄 MA 파라미터 재최적화 완료\nMA_SHORT: {optimal_ma_short}\nMA_LONG: {optimal_ma_long}\nDCC_PERIOD: {DCC_PERIOD}")
        else:
            telegram_sender.SendMessage(f"🤖 MA 파라미터 최적화 완료\nMA_SHORT: {optimal_ma_short}\nMA_LONG: {optimal_ma_long}\nDCC_PERIOD: {DCC_PERIOD}")
        
    except Exception as e:
        logger.error(f"최적화 실패: {e}")
        telegram_sender.SendMessage(f"⚠️ MA 파라미터 최적화 실패: {e}")
        # 기본값 사용 (params에만 저장)
        dic["params"]["ma_short"] = SMA_SHORT
        dic["params"]["ma_long"] = SMA_LONG
        dic["params"]["dcc_period"] = DCC_PERIOD
else:
    # 기존 파라미터 사용 (params에서만 가져오기)
    optimal_ma_short = dic.get("params", {}).get("ma_short", SMA_SHORT)
    optimal_ma_long = dic.get("params", {}).get("ma_long", SMA_LONG)
    logger.info(f"기존 파라미터 사용: MA_SHORT={optimal_ma_short}, MA_LONG={optimal_ma_long}")

# UTC 현재 시간 + 9시간(한국 시간)
yesterday = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9) - dt.timedelta(days=1)
today = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)

# 24시에 수익금 처리
if today.hour == 0 and today.minute == 0:
    dic["today"] = float(balance['USDT']['total'])-dic["my_money"]
    dic["my_money"] = float(balance['USDT']['total'])
    dic["yesterday"] = dic["today"]
    dic["today"] = 0
    with open(info_file_path, 'w') as outfile:
        json.dump(dic, outfile, indent=4, ensure_ascii=False)

for Target_Coin_Ticker in Coin_Ticker_List:
    logger.info("###################################################################################################")
    Target_Coin_Symbol = Target_Coin_Ticker.replace("/", "").replace(":USDT", "")
    
    current_memory = cleanup_memory()
    
    coin_price = myBinance.GetCoinNowPrice(binanceX, Target_Coin_Ticker)
    

    #변수 셋팅
    leverage = 5
    amt_s = 0
    amt_l = 0
    isolated = True
    
    # 백테스트와 동일한 청산 파라미터
    charge = 0.001  # 수수료율 (Maker + Taker)
    investment_ratio = 0.5  # 투자 비율
    divide = 100  # 분할 수 (1%)
    
    # 레버리지 설정
    try:
        logger.info(binanceX.fapiPrivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': leverage}))
    except Exception as e:
        try:
            logger.info(binanceX.fapiprivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': leverage}))
        except Exception as e:
            logger.error(f"error: {e}")

    # 숏잔고
    entryPrice_s = 0
    for posi in balance['info']['positions']:
        if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'SHORT':
            logger.info(f"📊 숏 포지션: {posi}")
            amt_s = float(posi['positionAmt'])
            entryPrice_s = float(posi.get('entryPrice', 0))
            
            # entryPrice가 0이면 notional과 unrealizedProfit으로 계산
            if entryPrice_s == 0 and abs(amt_s) > 0:
                notional = float(posi.get('notional', 0))
                unrealized_profit = float(posi.get('unrealizedProfit', 0))
                if notional > 0:
                    # 진입가격 = (현재 포지션 가치 - 미실현 손익) / 포지션 수량
                    entryPrice_s = (notional - unrealized_profit) / abs(amt_s)
                    logger.info(f"📊 숏 진입가 계산: notional={notional:.2f}, unrealized={unrealized_profit:.2f}, amt={abs(amt_s):.6f}")
            
            if abs(amt_s) > 0:
                logger.info(f"📊 숏 포지션: {amt_s}, 진입가: {entryPrice_s:.2f}")
            break

    # 롱잔고
    entryPrice_l = 0
    for posi in balance['info']['positions']:
        if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'LONG':
            logger.info(f"📊 롱 포지션: {posi}")
            amt_l = float(posi['positionAmt'])
            entryPrice_l = float(posi.get('entryPrice', 0))
            
            # entryPrice가 0이면 notional과 unrealizedProfit으로 계산
            if entryPrice_l == 0 and abs(amt_l) > 0:
                notional = float(posi.get('notional', 0))
                unrealized_profit = float(posi.get('unrealizedProfit', 0))
                if notional > 0:
                    # 진입가격 = (현재 포지션 가치 - 미실현 손익) / 포지션 수량
                    entryPrice_l = (notional - unrealized_profit) / abs(amt_l)
                    logger.info(f"📊 롱 진입가 계산: notional={notional:.2f}, unrealized={unrealized_profit:.2f}, amt={abs(amt_l):.6f}")
            
            if abs(amt_l) > 0:
                logger.info(f"📊 롱 포지션: {amt_l}, 진입가: {entryPrice_l:.2f}")
            break

    logger.info(f"entryPrice_s : {entryPrice_s}")
    logger.info(f"entryPrice_l : {entryPrice_l}")
    
    # 격리모드 설정
    if isolated == False:
       try:
           logger.info(binanceX.fapiPrivate_post_margintype({'symbol': Target_Coin_Symbol, 'marginType': 'ISOLATED'}))
       except Exception as e:
           try:
               logger.info(binanceX.fapiprivate_post_margintype({'symbol': Target_Coin_Symbol, 'marginType': 'ISOLATED'}))
           except Exception as e:
               logger.error(f"error: {e}")
    
    # 포지션 정보는 바이낸스 API에서 직접 가져오므로 보정 불필요
    
    # 캔들 정보 가져오기 (15분봉)
    df = myBinance.GetOhlcv(binanceX, Target_Coin_Ticker, '15m')

    # 통합 전략 지표 계산 (최적화된 파라미터 사용)
    df_with_indicators = calculate_indicators(df, optimal_ma_short, optimal_ma_long, DCC_PERIOD)
    df_with_signals = generate_signals(df_with_indicators, dic.get("params", {}))
    
    # 현재 신호 상태
    current_row = df_with_signals.iloc[-1] if len(df_with_signals) > 0 else None

    # ========================= 신호 확인 =========================
    if current_row is not None:
        logger.info(f"📊 현재 신호: 롱={current_row['long_signal']}, 숏={current_row['short_signal']}, RSI={current_row['rsi']:.1f}")
    else:
        logger.warning("신호 데이터를 가져올 수 없습니다.")
    
    # 레버리지에 따른 최대 매수 가능 수량
    Max_Amount = round(myBinance.GetAmount(float(balance['USDT']['total']),coin_price,investment_ratio),3) * leverage
    one_percent_amount = Max_Amount / divide
    logger.info(f"one_percent_amount : {one_percent_amount}") 

    first_amount = round((one_percent_amount*1.0)-0.0005, 3)
    minimun_amount = myBinance.GetMinimumAmount(binanceX, Target_Coin_Ticker)
    if first_amount < minimun_amount:
        first_amount = minimun_amount
    logger.info(f"first_amount : {first_amount}")

    one_percent_divisions = 1 / (one_percent_amount / first_amount)
    current_divisions = divide / one_percent_divisions

    # 아침 8시 보고
    if today.hour == 8 and today.minute == 0:
        msg = "\n==========================="
        msg += "\n         MA DCC Bot (양방향 전략)"
        msg += "\n==========================="
        msg += "\n         "+str(today.month)+"월 "+str(today.day)+"일 수익 결산보고"
        msg += "\n==========================="
        msg += "\n어제 수익 : "+str(round(dic["yesterday"], 2))+" 달러"
        msg += "\n오늘 수익 : "+str(round(dic["today"], 2))+" 달러"
        msg += "\n시작 잔고 : "+str(round(dic["start_money"], 2))+" 달러"
        msg += "\n현재 잔고 : "+str(round(dic["my_money"], 2))+" 달러"
        msg += "\n총 수익금 : "+str(round(dic["my_money"]-dic["start_money"], 2))+" 달러"
        per = (dic["my_money"]-dic["start_money"])/dic["start_money"]*100
        msg += "\n총 수익률 : "+str(round(per, 2))+"%"
        msg += "\n==========================="
        params = dic.get("params", {})
        msg += f"\n📊 현재 파라미터: MA_SHORT={optimal_ma_short}, MA_LONG={optimal_ma_long}, DCC={DCC_PERIOD}"
        msg += f"\n📊 RSI 파라미터: 과매수={params.get('rsi_overbought', RSI_OVERBOUGHT)}, 과매도={params.get('rsi_oversold', RSI_OVERSOLD)}, 극값={params.get('rsi_extreme_high', RSI_EXTREME_HIGH)}/{params.get('rsi_extreme_low', RSI_EXTREME_LOW)}"
        if "optimization_date" in dic:
            opt_date = dt.datetime.fromisoformat(dic["optimization_date"])
            days_since = (dt.datetime.now() - opt_date).days
            next_optimization = opt_date + dt.timedelta(days=180)
            msg += f"\n🔄 최적화 일시: {opt_date.strftime('%Y-%m-%d %H:%M')} ({days_since}일 전)"
            msg += f"\n📅 다음 최적화: {next_optimization.strftime('%Y-%m-%d')}"
        else:
            msg += f"\n📋 기본 파라미터 사용"
        msg += "\n==========================="
        # 포지션 정보 표시
        has_position = abs(amt_s) > 0 or abs(amt_l) > 0
        if has_position:
            msg += f"\n포지션: "
        if abs(amt_s) > 0:
            msg += f"숏 {abs(amt_s):.3f} "
        if abs(amt_l) > 0:
            msg += f"롱 {amt_l:.3f}"
        viewlist(msg, amt_s, amt_l, entryPrice_s, entryPrice_l)

   
    # 현재 포지션 확인 (바이낸스 API 기준)
    has_short = abs(amt_s) > 0
    has_long = abs(amt_l) > 0
    
    # ==================== 포지션 소실 감지 및 청산 처리 ====================
    # JSON에는 포지션이 있지만 실제로는 포지션이 없는 경우 (수동 청산 등)
    
    # 숏 포지션 소실 감지
    if not has_short and dic.get("short_position", {}).get("entry_price", 0) > 0:
        old_entry_price = dic["short_position"]["entry_price"]
        old_amount = dic["short_position"]["amount"]
        
        # 수동 청산으로 간주하고 손실 처리
        # 현재가 기준으로 실제 손실 계산
        if coin_price > 0:
            # 숏 포지션: 가격 상승 시 손실
            pnl_pct = (old_entry_price - coin_price) / old_entry_price
            estimated_loss = old_amount * old_entry_price * pnl_pct
        else:
            # 현재가를 알 수 없는 경우 보수적으로 1% 손실로 가정
            estimated_loss = old_amount * old_entry_price * 0.01
        dic["today"] -= estimated_loss
        
        # 포지션 정보 초기화
        dic["short_position"] = {
            "entry_price": 0,
            "amount": 0
        }
        
        pnl_display = f"({pnl_pct*100:.2f}%)" if coin_price > 0 else "(추정 1%)"
        msg = f"⚠️ 숏 포지션 소실 감지 (수동 청산 추정) | 진입가: {old_entry_price:.2f}, 현재가: {coin_price:.2f}, 수량: {old_amount:.3f}, 손실: {estimated_loss:.2f}$ {pnl_display}"
        telegram_sender.SendMessage(msg)
        logger.warning(msg)
        
        # 즉시 JSON 저장
        with open(info_file_path, 'w') as outfile:
            json.dump(dic, outfile, indent=4, ensure_ascii=False)
    
    # 롱 포지션 소실 감지
    if not has_long and dic.get("long_position", {}).get("entry_price", 0) > 0:
        old_entry_price = dic["long_position"]["entry_price"]
        old_amount = dic["long_position"]["amount"]
        
        # 수동 청산으로 간주하고 손실 처리
        # 현재가 기준으로 실제 손실 계산
        if coin_price > 0:
            # 롱 포지션: 가격 하락 시 손실
            pnl_pct = (coin_price - old_entry_price) / old_entry_price
            estimated_loss = old_amount * old_entry_price * pnl_pct
        else:
            # 현재가를 알 수 없는 경우 보수적으로 1% 손실로 가정
            estimated_loss = old_amount * old_entry_price * 0.01
        dic["today"] -= estimated_loss
        
        # 포지션 정보 초기화
        dic["long_position"] = {
            "entry_price": 0,
            "amount": 0
        }
        
        pnl_display = f"({pnl_pct*100:.2f}%)" if coin_price > 0 else "(추정 1%)"
        msg = f"⚠️ 롱 포지션 소실 감지 (수동 청산 추정) | 진입가: {old_entry_price:.2f}, 현재가: {coin_price:.2f}, 수량: {old_amount:.3f}, 손실: {estimated_loss:.2f}$ {pnl_display}"
        telegram_sender.SendMessage(msg)
        logger.warning(msg)
        
        # 즉시 JSON 저장
        with open(info_file_path, 'w') as outfile:
            json.dump(dic, outfile, indent=4, ensure_ascii=False)
    
    # ==================== 진입 로직 (백테스트와 동일) ====================
    # 숏 진입: 숏 신호 + 숏 포지션 없을 때 (백테스트와 동일)
    if not has_short and current_row is not None and current_row['short_signal']:
        data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', first_amount, None, {'positionSide': 'SHORT'})
        entry_price = float(data['average'])
        
        # 포지션 정보 저장
        dic["short_position"] = {
            "entry_price": entry_price,
            "amount": first_amount
        }
        
        msg = f"🔻 숏 진입 | 가격: {entry_price:.2f}, 수량: {first_amount:.3f}"
        telegram_sender.SendMessage(msg)
        logger.info(msg)
    
    # 롱 진입: 롱 신호 + 롱 포지션 없을 때 (백테스트와 동일)
    if not has_long and current_row is not None and current_row['long_signal']:
        data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', first_amount, None, {'positionSide': 'LONG'})
        entry_price = float(data['average'])
        
        # 포지션 정보 저장
        dic["long_position"] = {
            "entry_price": entry_price,
            "amount": first_amount
        }
        
        msg = f"🔺 롱 진입 | 가격: {entry_price:.2f}, 수량: {first_amount:.3f}"
        telegram_sender.SendMessage(msg)
        logger.info(msg)
    
    # ==================== 청산 로직 (백테스트와 완전 동일) ====================
    
    # 숏 포지션 체크 및 청산 (백테스트와 동일한 로직)
    if has_short and entryPrice_s > 0:
        pnl_pct = (entryPrice_s - coin_price) / entryPrice_s
        logger.info(f"🔍 숏 PnL 체크: 진입가 {entryPrice_s:.2f}, 현재가 {coin_price:.2f}, 수익률 {pnl_pct*100:.2f}%")
        
        # 청산 조건: 반대 신호 또는 RSI 극값 (백테스트와 동일)
        should_close = False
        close_reason = None
        
        # 1. 반대 신호 (롱 신호) 발생
        if current_row is not None and current_row.get('long_signal', False):
            should_close = True
            close_reason = "opposite_signal"
        # 2. RSI 극값 도달
        elif current_row is not None and current_row.get('rsi', 50) < dic.get("params", {}).get("rsi_extreme_low", RSI_EXTREME_LOW):
            should_close = True
            close_reason = "rsi_extreme"
        
        # 청산 실행
        if should_close:
            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', round(abs(amt_s), 3), None, {'positionSide': 'SHORT'})
            close_price = float(data['average'])
            profit = (entryPrice_s - close_price) * abs(amt_s) - (close_price * abs(amt_s) * charge * 2)
            
            dic["today"] += profit
            dic["short_position"] = {
                "entry_price": 0,
                "amount": 0
            }
            
            msg = f"✅ 숏 청산 ({close_reason}) | 진입: {entryPrice_s:.2f} → 청산: {close_price:.2f} | 수익: {profit:.2f}$ ({pnl_pct*100:.2f}%)"
            telegram_sender.SendMessage(msg)
            logger.info(msg)
    
    # 롱 포지션 체크 및 청산 (백테스트와 동일한 로직)
    if has_long and entryPrice_l > 0:
        pnl_pct = (coin_price - entryPrice_l) / entryPrice_l
        logger.info(f"🔍 롱 PnL 체크: 진입가 {entryPrice_l:.2f}, 현재가 {coin_price:.2f}, 수익률 {pnl_pct*100:.2f}%")
        
        # 청산 조건: 반대 신호 또는 RSI 극값 (백테스트와 동일)
        should_close = False
        close_reason = None
        
        # 1. 반대 신호 (숏 신호) 발생
        if current_row is not None and current_row.get('short_signal', False):
            should_close = True
            close_reason = "opposite_signal"
        # 2. RSI 극값 도달
        elif current_row is not None and current_row.get('rsi', 50) > dic.get("params", {}).get("rsi_extreme_high", RSI_EXTREME_HIGH):
            should_close = True
            close_reason = "rsi_extreme"
        
        # 청산 실행
        if should_close:
            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', round(abs(amt_l), 3), None, {'positionSide': 'LONG'})
            close_price = float(data['average'])
            profit = (close_price - entryPrice_l) * abs(amt_l) - (close_price * abs(amt_l) * charge * 2)
            
            dic["today"] += profit
            dic["long_position"] = {
                "entry_price": 0,
                "amount": 0
            }
            
            msg = f"✅ 롱 청산 ({close_reason}) | 진입: {entryPrice_l:.2f} → 청산: {close_price:.2f} | 수익: {profit:.2f}$ ({pnl_pct*100:.2f}%)"
            telegram_sender.SendMessage(msg)
            logger.info(msg)

    logger.info("\n-- END --------------------------------------------------------------------------------------------\n")
    
    # 캔들 데이터 정리
    cleanup_dataframes(df)
    cleanup_memory()
    
    # JSON 저장
    with open(info_file_path, 'w') as outfile:
        json.dump(dic, outfile, indent=4, ensure_ascii=False)

# 최종 메모리 정리
final_memory = cleanup_memory()

# 정리
try:
    if 'binanceX' in locals():
        del binanceX
except:
    pass

gc.collect()

logger.info(f"=== MA DCC Bot 종료 (최종 메모리: {final_memory:.2f} MB) ===")




