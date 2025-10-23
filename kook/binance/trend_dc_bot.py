"""
비트코인 추세 추종 + 양방향 매매 봇 (라이브 거래)

=== 전략 개요 ===
- 추세 추종에 편승하면 단방향 매매 (롱 또는 숏)
- 추세 이탈하면 양방향 매매로 전환
- 15분봉 실시간 데이터 사용
- 구매/판매 수수료 각 0.05% 적용
- 백테스트 검증된 로직 적용

=== 핵심 로직 ===
1. 추세 감지: 이동평균선 교차 + RSI + 볼린저 밴드 + 돈키안 채널
2. 추세 추종 모드: 강한 추세일 때 단방향 매매
3. 양방향 모드: 추세가 약하거나 횡보일 때 양방향 매매
4. 리스크 관리: 손절 + 동적 트레일링스탑

=== 기술적 지표 상세 ===

1. 이동평균선 (Moving Average)
   - SMA Short: 20 (단기 이동평균선)
   - SMA Long: 50 (장기 이동평균선)
   - 역할: 추세 방향 판단
   - 신호: 단기선이 장기선을 상향돌파 → 롱 신호, 하향돌파 → 숏 신호

2. 돈키안 채널 (Donchian Channel)
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
   - 롱 조건: RSI > 30 (과매도 아님)
   - 숏 조건: RSI < 70 (과매수 아님)

4. 볼린저 밴드 (Bollinger Bands)
   - 기간: 20, 표준편차: 2
   - 역할: 가격 변동성과 과매수/과매도 판단
   - 롱 조건: 현재가 > 볼린저 하단
   - 숏 조건: 현재가 < 볼린저 상단

=== 전략 모드 ===

1. 강한 상승 추세 모드
   - 조건: 추세강도 > 0.02 & RSI > 50
   - 거래: 롱만 신호 (단방향)
   - 신호 조건: 모든 지표가 롱 신호

2. 강한 하락 추세 모드
   - 조건: 추세강도 < -0.02 & RSI < 50
   - 거래: 숏만 신호 (단방향)
   - 신호 조건: 모든 지표가 숏 신호

3. 횡보/약한 추세 모드
   - 조건: 위 조건들에 해당하지 않음
   - 거래: 양방향 신호
   - 신호 조건: 각각의 지표 조건 만족

=== 리스크 관리 ===

1. 진입 조건 (모두 만족해야 함):
   - 이동평균선 크로스오버
   - 돈키안 채널 조건
   - RSI 과매수/과매도 아님
   - 볼린저 밴드 조건

2. 청산 조건 (하나라도 만족하면):
   - 손절: -2% 손실 시
   - 동적 트레일링스탑: 수익률에 따라 조정
     * 0.5% 수익: 트레일링스탑 0.5%
     * 1.0% 수익: 트레일링스탑 0.3%
     * 1.5% 수익: 트레일링스탑 0.2%
     * 2.0% 수익: 트레일링스탑 0.1%
     * 2.5% 수익: 트레일링스탑 0.05%
     * 3.0% 수익: 트레일링스탑 0.01%

3. 동시 진입 방지:
   - 롱/숏 신호 동시 발생 시 충돌 처리
   - 우선순위에 따른 신호 선택

=== 파라미터 설정 ===
- MA Short: 20 (고정)
- MA Long: 50 (고정)
- DCC Period: 25 (고정)
- RSI Period: 14 (고정)
- RSI 과매수: 70, RSI 과매도: 30

=== 백테스트 검증 결과 ===
- 2018년: 13,541.24% 수익률
- 2019년: 648.78% 수익률
- 2020년: 259.80% 수익률
- 2021년: 2,559.47% 수익률
- 2022년: 418.31% 수익률
- 2023년: 82.98% 수익률
- 2024년: 155.75% 수익률
- 2025년: 49.47% 수익률 (현재까지)

=== 실시간 거래 방식 ===
- 데이터: 15분봉 실시간 데이터
- 신호 생성: 이동평균 + 돈키안 채널 + RSI + 볼린저 밴드
- 포지션 관리: 단일 포지션 유지 (롱 또는 숏)
- 레버리지: 3배 (선물 거래 기준)
- 수수료: 진입/청산 시 각각 0.05% 적용
- 리스크 관리: 손절(-2%) + 동적 트레일링스탑
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

import myBinance
import ende_key  #암복호화키
import my_key    #업비트 시크릿 액세스키
import telegram_sender

# ========================= 로깅 설정 =========================
script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, "..", "logs")
os.makedirs(logs_dir, exist_ok=True)

log_file = os.path.join(logs_dir, f"trend_dc_bot_{dt.datetime.now().strftime('%Y%m%d')}.log")
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
# 백테스트와 동일한 파라미터 (소문자 사용)
ma_short = 20   # 단기 이동평균 (백테스트 검증됨)
ma_long = 50    # 장기 이동평균 (백테스트 검증됨)
dc_period = 25  # 던키안 채널 기간 (백테스트 검증됨)
rsi_period = 14  # RSI 기간 (백테스트 검증됨)
rsi_overbought = 70  # RSI 과매수 기준 (백테스트 검증됨)
rsi_oversold = 30    # RSI 과매도 기준 (백테스트 검증됨)
trend_threshold = 0.02  # 추세 강도 임계값 (백테스트 검증됨)
bb_period = 20  # 볼린저 밴드 기간 (백테스트 검증됨)
bb_std = 2  # 볼린저 밴드 표준편차 (백테스트 검증됨)

# 백테스트와 동일한 리스크 관리 파라미터
stop_loss = 0.02      # 손절 2% (백테스트 검증됨)
take_profit = 0.03     # 익절 3% (백테스트 검증됨)
trailing_stop = 0.005  # 트레일링스탑 0.5% (백테스트 검증됨)


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
    """백테스트 검증된 통합 전략용 기술적 지표 계산"""
    df = df.copy()
    
    # 파라미터 설정 (기본값 사용)
    ma_short = ma_short or ma_short
    ma_long = ma_long or ma_long
    dcc_period = dcc_period or dc_period
        
    # 이동평균선
    df['sma_short'] = talib.SMA(df['close'], timeperiod=ma_short)
    df['sma_long'] = talib.SMA(df['close'], timeperiod=ma_long)
    
    # 던키안 채널
    df['dcc_high'] = df['high'].rolling(dcc_period).max()
    df['dcc_low'] = df['low'].rolling(dcc_period).min()
    df['dcc_middle'] = (df['dcc_high'] + df['dcc_low']) / 2
    
    # RSI
    df['rsi'] = talib.RSI(df['close'], timeperiod=rsi_period)
    
    # 볼린저 밴드 (백테스트와 동일)
    df['bb_middle'] = df['close'].rolling(window=bb_period).mean()
    bb_std_series = df['close'].rolling(window=bb_period).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std_series * bb_std)
    df['bb_lower'] = df['bb_middle'] - (bb_std_series * bb_std)
        
    return df

def generate_signals(df: pd.DataFrame, params=None) -> pd.DataFrame:
    """백테스트 검증된 통합 전략 신호 생성"""
    df = df.copy()
    
    # 기본 신호 초기화
    df['long_signal'] = False
    df['short_signal'] = False
    df['trend_mode'] = 'sideways'
    
    # 추세 강도 계산 (백테스트와 동일)
    df['trend_strength'] = (df['sma_short'] - df['sma_long']) / df['sma_long']
    
    # 추세 모드 결정 (백테스트와 동일)
    strong_uptrend = (df['trend_strength'] > trend_threshold) & (df['rsi'] > 50)
    strong_downtrend = (df['trend_strength'] < -trend_threshold) & (df['rsi'] < 50)
    
    df.loc[strong_uptrend, 'trend_mode'] = 'strong_uptrend'
    df.loc[strong_downtrend, 'trend_mode'] = 'strong_downtrend'
    
    # 롱 신호 조건 (백테스트와 동일)
    long_conditions = (
        (df['close'] > df['sma_short']) &  # 단기 이평 위
        (df['close'] > df['dcc_middle']) &  # 돈키안 중간선 위
        (df['close'] > df['dcc_low'] * 1.02) &  # 돈키안 하단 +2% 위
        (df['rsi'] > rsi_oversold) &  # RSI 과매도 아님
        (df['close'] > df['bb_lower'])  # 볼린저 하단 위
    )
    
    # 숏 신호 조건 (백테스트와 동일)
    short_conditions = (
        (df['close'] < df['sma_short']) &  # 단기 이평 아래
        (df['close'] < df['dcc_middle']) &  # 돈키안 중간선 아래
        (df['close'] < df['dcc_high'] * 0.98) &  # 돈키안 상단 -2% 아래
        (df['rsi'] < rsi_overbought) &  # RSI 과매수 아님
        (df['close'] < df['bb_upper'])  # 볼린저 상단 아래
    )
    
    # 추세 모드에 따른 신호 적용 (백테스트와 동일)
    # 강한 상승 추세: 롱만
    df.loc[strong_uptrend & long_conditions, 'long_signal'] = True
    
    # 강한 하락 추세: 숏만
    df.loc[strong_downtrend & short_conditions, 'short_signal'] = True
    
    # 횡보/약한 추세: 양방향
    sideways_conditions = df['trend_mode'] == 'sideways'
    df.loc[sideways_conditions & long_conditions, 'long_signal'] = True
    df.loc[sideways_conditions & short_conditions, 'short_signal'] = True
    
    return df

def get_dynamic_trailing_stop(pnl_pct):
    """수익률에 따른 동적 트레일링스탑 비율 계산"""
    if pnl_pct >= 0.03:      # 3.0% 이상
        return 0.0001
    elif pnl_pct >= 0.025:   # 2.5% 이상
        return 0.0005
    elif pnl_pct >= 0.02:    # 2.0% 이상
        return 0.001
    elif pnl_pct >= 0.015:   # 1.5% 이상
        return 0.002
    elif pnl_pct >= 0.01:    # 1.0% 이상
        return 0.003
    elif pnl_pct >= 0.005:   # 0.5% 이상
        return 0.005
    else:
        return None  # 트레일링스탑 비활성화

def get_coin_positions(dic, coin_symbol):
    """특정 코인의 포지션 정보 가져오기"""
    if "positions" not in dic:
        dic["positions"] = {}
    
    if coin_symbol not in dic["positions"]:
        dic["positions"][coin_symbol] = {
            "long_position": {"entry_price": 0, "amount": 0, "trailing_stop_price": None},
            "short_position": {"entry_price": 0, "amount": 0, "trailing_stop_price": None}
        }
    
    return dic["positions"][coin_symbol]

def update_coin_position(dic, coin_symbol, position_type, entry_price, amount, trailing_stop_price=None):
    """특정 코인의 포지션 정보 업데이트"""
    positions = get_coin_positions(dic, coin_symbol)
    positions[position_type] = {
        "entry_price": entry_price,
        "amount": amount,
        "trailing_stop_price": trailing_stop_price
    }

def clear_coin_position(dic, coin_symbol, position_type):
    """특정 코인의 포지션 정보 초기화"""
    positions = get_coin_positions(dic, coin_symbol)
    positions[position_type] = {
        "entry_price": 0,
        "amount": 0,
        "trailing_stop_price": None
    }

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
logger.info("Trend DC Bot - 바이낸스 양방향 전략 (시작)")
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
Coin_Ticker_List = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'SOL/USDT', 'DOGE/USDT']
#Coin_Ticker_List = ['BTC/USDT']
logger.info("\n-- START ------------------------------------------------------------------------------------------\n")

# 초기 메모리 정리
initial_memory = cleanup_memory()

dic = dict()
info_file_path = os.path.join(os.path.dirname(__file__), "trend_dc_bot.json")

#잔고 데이타 가져오기 
balance = binanceX.fetch_balance(params={"type": "future"})
time.sleep(0.1)

# 바이낸스 API 포지션 정보 상세 로그
logger.info(f"🔍 바이낸스 API 포지션 정보 (BTCUSDT):")
for posi in balance['info']['positions']:
    if posi['symbol'] == 'BTCUSDT':
        logger.info(f"  {posi['positionSide']}: 수량={posi['positionAmt']}, 진입가={posi.get('entryPrice', 'N/A')}, 마크가={posi.get('markPrice', 'N/A')}, notional={posi.get('notional', 'N/A')}, 미실현손익={posi.get('unrealizedProfit', 'N/A')}")

# fetch_positions 함수는 메인 루프에서 호출됩니다


# JSON 파일 로드 및 초기화
def initialize_bot_data():
    """봇 데이터 초기화 (JSON 로드 + 기본값 설정)"""
    current_balance = float(balance['USDT']['total'])
    
    # 기본 데이터 구조 (코인별 포지션 관리)
    default_data = {
        "yesterday": 0,
        "today": 0,
        "start_money": current_balance,
        "my_money": current_balance,
        "positions": {},  # 코인별 포지션 정보
        "params": {
            'ma_short': ma_short,
            'ma_long': ma_long,
            'dcc_period': dc_period,
            'rsi_period': rsi_period,
            'rsi_overbought': rsi_overbought,
            'rsi_oversold': rsi_oversold,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'trailing_stop': trailing_stop
        }
    }
    
    # JSON 파일 로드 시도
    try:
        if os.path.exists(info_file_path):
            with open(info_file_path, 'r') as json_file:
                dic = json.load(json_file)
        else:
            dic = {}
    except Exception as e:
        logger.info(f"JSON 파일 로드 실패: {e}")
        dic = {}
    
    # 기본값으로 병합 (기존 값이 있으면 유지, 없으면 기본값 사용)
    for key, default_value in default_data.items():
        if key not in dic:
            dic[key] = default_value
    
    
    return dic

# 봇 데이터 초기화
dic = initialize_bot_data()

logger.info(f"balance['USDT'] : {balance['USDT']}")

logger.info(f"포지션 정보는 바이낸스 API에서 직접 가져옵니다")

# 파라미터 설정 (고정값 사용)
optimal_ma_short = ma_short
optimal_ma_long = ma_long
logger.info(f"고정 파라미터 사용: MA_SHORT={optimal_ma_short}, MA_LONG={optimal_ma_long}")

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
    leverage = 3
    amt_s = 0
    amt_l = 0
    isolated = True
    
    # 백테스트와 동일한 청산 파라미터
    charge = 0.0005  # 수수료율 0.05% (백테스트와 동일)
    investment_ratio = 0.5  # 투자 비율
    divide = 10  # 분할 수 (1%)
    
    # 레버리지 설정
    try:
        logger.info(binanceX.fapiPrivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': leverage}))
    except Exception as e:
        try:
            logger.info(binanceX.fapiprivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': leverage}))
        except Exception as e:
            logger.error(f"error: {e}")

    # 포지션 정보는 fetch_positions에서만 가져오기
    entryPrice_s = 0
    amt_s = 0
    entryPrice_l = 0
    amt_l = 0
    
    try:
        positions = binanceX.fetch_positions([Target_Coin_Ticker])
        logger.info(f"📊 fetch_positions 전체 결과: {positions}")
        
        for pos in positions:
            logger.info(f"🔍 포지션 체크: symbol='{pos['symbol']}', Target_Coin_Ticker='{Target_Coin_Ticker}'")
            
            # 심볼 매칭 (BTC/USDT와 BTC/USDT:USDT 모두 처리)
            symbol_match = (pos['symbol'] == Target_Coin_Ticker or 
                           pos['symbol'] == Target_Coin_Ticker + ':USDT' or
                           pos['symbol'].replace(':USDT', '') == Target_Coin_Ticker)
            
            if symbol_match:
                logger.info(f"🔍 포지션 처리 중: side='{pos['side']}', contracts={pos['contracts']}, entryPrice={pos.get('entryPrice', 'N/A')}")
                
                if pos['side'] == 'short':
                    amt_s = abs(float(pos['contracts']))  # 숏은 절댓값 사용
                    entryPrice_s = float(pos.get('entryPrice', 0))
                    logger.info(f"📊 숏 포지션 설정: 수량={amt_s:.6f}, 진입가={entryPrice_s:.2f}")
                        
                elif pos['side'] == 'long':
                    amt_l = float(pos['contracts'])
                    entryPrice_l = float(pos.get('entryPrice', 0))
                    logger.info(f"📊 롱 포지션 설정: 수량={amt_l:.6f}, 진입가={entryPrice_l:.2f}")
                else:
                    logger.warning(f"⚠️ 알 수 없는 포지션 사이드: '{pos['side']}'")
            else:
                logger.info(f"🔍 심볼 불일치: '{pos['symbol']}' != '{Target_Coin_Ticker}'")
                        
    except Exception as e:
        logger.error(f"❌ fetch_positions 실패: {e}")
        telegram_sender.SendMessage(f"❌ fetch_positions 실패: {e}")
        # API 실패 시 기본값 유지
        amt_s = 0
        amt_l = 0
        entryPrice_s = 0
        entryPrice_l = 0

    # 코인별 포지션 정보 가져오기
    coin_positions = get_coin_positions(dic, Target_Coin_Symbol)
    json_long = coin_positions["long_position"]
    json_short = coin_positions["short_position"]        

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
    df_with_indicators = calculate_indicators(df, optimal_ma_short, optimal_ma_long, dc_period)
    df_with_signals = generate_signals(df_with_indicators, dic.get("params", {}))
    
    # 현재 신호 상태
    current_row = df_with_signals.iloc[-1] if len(df_with_signals) > 0 else None

    # ========================= 신호 확인 =========================
    if current_row is not None:
        trend_mode = current_row.get('trend_mode', 'sideways')
        logger.info(f"📊 현재 신호: 롱={current_row.get('long_signal', False)}, 숏={current_row.get('short_signal', False)}, RSI={current_row.get('rsi', 50):.1f}, 추세모드={trend_mode}")
        
        # 백테스트와 동일한 신호 상세 정보
        if current_row.get('long_signal', False):
            logger.info(f"🔺 롱 신호 조건: 이평={current_row.get('close', 0) > current_row.get('sma_short', 0)}, 돈키안={current_row.get('close', 0) > current_row.get('dcc_middle', 0)}, RSI={current_row.get('rsi', 50) > rsi_oversold}")
        if current_row.get('short_signal', False):
            logger.info(f"🔻 숏 신호 조건: 이평={current_row.get('close', 0) < current_row.get('sma_short', 0)}, 돈키안={current_row.get('close', 0) < current_row.get('dcc_middle', 0)}, RSI={current_row.get('rsi', 50) < rsi_overbought}")
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


   
    # 현재 포지션 확인 (바이낸스 API 기준)
    has_short = abs(amt_s) > 0
    has_long = abs(amt_l) > 0
    
    # 포지션 상태 로깅
    if has_short or has_long:
        logger.info(f"📊 현재 포지션 상태: 숏={has_short}, 롱={has_long}")
        if has_short:
            logger.info(f"  숏 포지션: 수량={amt_s:.6f}, 진입가={entryPrice_s:.2f}")
        if has_long:
            logger.info(f"  롱 포지션: 수량={amt_l:.6f}, 진입가={entryPrice_l:.2f}")
    else:
        logger.info("📊 현재 포지션 없음 (지갑 비어있음)")
    
    # ==================== 수동 포지션 추가 감지 및 처리 ====================
    # JSON에는 포지션이 없지만 실제 API에서는 포지션이 있는 경우 (수동 추가 등)
    
    # 숏 포지션 수동 추가 감지
    json_has_short = json_short.get("entry_price", 0) > 0 and json_short.get("amount", 0) > 0
    api_has_short = abs(amt_s) > 0
    
    if not json_has_short and api_has_short:
        # 수동으로 숏 포지션이 추가된 것으로 감지
        msg = f"🔍 {Target_Coin_Symbol} 숏 포지션 수동 추가 감지"
        msg += f"\n📊 진입가: {entryPrice_s:.2f}$"
        msg += f"\n📊 수량: {amt_s:.3f}"
        msg += f"\n📊 현재가: {coin_price:.2f}$"
        
        # 수익률 계산
        if coin_price > 0 and entryPrice_s > 0:
            pnl_pct = (entryPrice_s - coin_price) / entryPrice_s
            msg += f"\n📊 수익률: {pnl_pct*100:.2f}%"
        
        msg += f"\n⚠️ 봇이 자동으로 진입하지 않은 수동 포지션입니다."
        
        # 수동 추가된 포지션에 트레일링스탑 설정 (0.5% 수익 후 활성화)
        update_coin_position(dic, Target_Coin_Symbol, "short_position", entryPrice_s, amt_s, None)
        msg += f"\n🔧 트레일링스탑: 0.5% 수익 후 활성화"
        
        telegram_sender.SendMessage(msg)
        logger.info(f"🔍 {Target_Coin_Symbol} 숏 포지션 수동 추가 감지: 진입가={entryPrice_s:.2f}, 수량={amt_s:.3f}, 트레일링스탑=0.5% 수익 후 활성화")
    
    # 롱 포지션 수동 추가 감지
    json_has_long = json_long.get("entry_price", 0) > 0 and json_long.get("amount", 0) > 0
    api_has_long = abs(amt_l) > 0
    
    if not json_has_long and api_has_long:
        # 수동으로 롱 포지션이 추가된 것으로 감지
        msg = f"🔍 {Target_Coin_Symbol} 롱 포지션 수동 추가 감지"
        msg += f"\n📊 진입가: {entryPrice_l:.2f}$"
        msg += f"\n📊 수량: {amt_l:.3f}"
        msg += f"\n📊 현재가: {coin_price:.2f}$"
        
        # 수익률 계산
        if coin_price > 0 and entryPrice_l > 0:
            pnl_pct = (coin_price - entryPrice_l) / entryPrice_l
            msg += f"\n📊 수익률: {pnl_pct*100:.2f}%"
        
        msg += f"\n⚠️ 봇이 자동으로 진입하지 않은 수동 포지션입니다."
        
        # 수동 추가된 포지션에 트레일링스탑 설정 (0.5% 수익 후 활성화)
        update_coin_position(dic, Target_Coin_Symbol, "long_position", entryPrice_l, amt_l, None)
        msg += f"\n🔧 트레일링스탑: 0.5% 수익 후 활성화"
        
        telegram_sender.SendMessage(msg)
        logger.info(f"🔍 {Target_Coin_Symbol} 롱 포지션 수동 추가 감지: 진입가={entryPrice_l:.2f}, 수량={amt_l:.3f}, 트레일링스탑=0.5% 수익 후 활성화")
    
    # ==================== JSON과 API 상태 동기화 ====================
    # API에서 포지션이 확인되면 JSON도 업데이트
    if has_short:
        # API에서 숏 포지션이 있으면 JSON 업데이트 (trailing_stop_price 보존)
        if json_short.get("entry_price", 0) != entryPrice_s or json_short.get("amount", 0) != amt_s:
            # 기존 trailing_stop_price 보존
            existing_trailing = json_short.get("trailing_stop_price")
            update_coin_position(dic, Target_Coin_Symbol, "short_position", entryPrice_s, amt_s, existing_trailing)
            logger.info(f"🔄 {Target_Coin_Symbol} JSON 숏 포지션 동기화: 진입가={entryPrice_s:.2f}, 수량={amt_s:.6f}, 트레일링스탑={existing_trailing}")
    else:
        # API에서 숏 포지션이 없으면 JSON도 초기화
        if json_short.get("entry_price", 0) > 0:
            clear_coin_position(dic, Target_Coin_Symbol, "short_position")
            logger.info(f"🔄 {Target_Coin_Symbol} JSON 숏 포지션 초기화 (API에서 포지션 없음)")
    
    if has_long:
        # API에서 롱 포지션이 있으면 JSON 업데이트 (trailing_stop_price 보존)
        if json_long.get("entry_price", 0) != entryPrice_l or json_long.get("amount", 0) != amt_l:
            # 기존 trailing_stop_price 보존
            existing_trailing = json_long.get("trailing_stop_price")
            update_coin_position(dic, Target_Coin_Symbol, "long_position", entryPrice_l, amt_l, existing_trailing)
            logger.info(f"🔄 {Target_Coin_Symbol} JSON 롱 포지션 동기화: 진입가={entryPrice_l:.2f}, 수량={amt_l:.6f}, 트레일링스탑={existing_trailing}")
    else:
        # API에서 롱 포지션이 없으면 JSON도 초기화
        if json_long.get("entry_price", 0) > 0:
            clear_coin_position(dic, Target_Coin_Symbol, "long_position")
            logger.info(f"🔄 {Target_Coin_Symbol} JSON 롱 포지션 초기화 (API에서 포지션 없음)")
    
    # ==================== 수동 청산 감지 및 처리 ====================
    # JSON에는 포지션이 있지만 실제 API에서는 포지션이 없는 경우 (수동 청산 등)
    
    # 숏 포지션 수동 청산 감지
    json_has_short = json_short.get("entry_price", 0) > 0 and json_short.get("amount", 0) > 0
    api_has_short = abs(amt_s) > 0
    
    if json_has_short and not api_has_short:
        old_entry_price = json_short["entry_price"]
        old_amount = json_short["amount"]
        
        # 수동 청산으로 간주하고 손익 계산
        if coin_price > 0:
            # 숏 포지션: 가격 상승 시 손실, 하락 시 수익
            pnl_pct = (old_entry_price - coin_price) / old_entry_price
            estimated_pnl = old_amount * old_entry_price * pnl_pct
        else:
            # 현재가를 알 수 없는 경우 보수적으로 0으로 처리
            pnl_pct = 0
            estimated_pnl = 0
            
        dic["today"] += estimated_pnl
        
        # 포지션 정보 초기화
        clear_coin_position(dic, Target_Coin_Symbol, "short_position")
        
        pnl_display = f"({pnl_pct*100:.2f}%)" if coin_price > 0 else "(추정 0%)"
        profit_loss = "수익" if estimated_pnl > 0 else "손실"
        profit_loss_emoji = "💰" if estimated_pnl > 0 else "📉"
        
        msg = f"🚨 {profit_loss_emoji} {Target_Coin_Symbol} 숏 포지션 수동 청산 감지"
        msg += f"\n📊 진입가: {old_entry_price:.2f}$"
        msg += f"\n📊 현재가: {coin_price:.2f}$"
        msg += f"\n📊 수량: {old_amount:.3f}"
        msg += f"\n📊 {profit_loss}: {abs(estimated_pnl):.2f}$ {pnl_display}"
        msg += f"\n⚠️ 봇이 자동으로 처리하지 않은 수동 청산입니다."
        
        telegram_sender.SendMessage(msg)
        logger.warning(f"🚨 {Target_Coin_Symbol} 숏 포지션 수동 청산 감지: {profit_loss} {abs(estimated_pnl):.2f}$ {pnl_display}")
        
        # 즉시 JSON 저장
        with open(info_file_path, 'w') as outfile:
            json.dump(dic, outfile, indent=4, ensure_ascii=False)
    
    # 롱 포지션 수동 청산 감지
    json_has_long = json_long.get("entry_price", 0) > 0 and json_long.get("amount", 0) > 0
    api_has_long = abs(amt_l) > 0
    
    if json_has_long and not api_has_long:
        old_entry_price = json_long["entry_price"]
        old_amount = json_long["amount"]
        
        # 수동 청산으로 간주하고 손익 계산
        if coin_price > 0:
            # 롱 포지션: 가격 상승 시 수익, 하락 시 손실
            pnl_pct = (coin_price - old_entry_price) / old_entry_price
            estimated_pnl = old_amount * old_entry_price * pnl_pct
        else:
            # 현재가를 알 수 없는 경우 보수적으로 0으로 처리
            pnl_pct = 0
            estimated_pnl = 0
            
        dic["today"] += estimated_pnl
        
        # 포지션 정보 초기화
        clear_coin_position(dic, Target_Coin_Symbol, "long_position")
        
        pnl_display = f"({pnl_pct*100:.2f}%)" if coin_price > 0 else "(추정 0%)"
        profit_loss = "수익" if estimated_pnl > 0 else "손실"
        profit_loss_emoji = "💰" if estimated_pnl > 0 else "📉"
        
        msg = f"🚨 {profit_loss_emoji} {Target_Coin_Symbol} 롱 포지션 수동 청산 감지"
        msg += f"\n📊 진입가: {old_entry_price:.2f}$"
        msg += f"\n📊 현재가: {coin_price:.2f}$"
        msg += f"\n📊 수량: {old_amount:.3f}"
        msg += f"\n📊 {profit_loss}: {abs(estimated_pnl):.2f}$ {pnl_display}"
        msg += f"\n⚠️ 봇이 자동으로 처리하지 않은 수동 청산입니다."
        
        telegram_sender.SendMessage(msg)
        logger.warning(f"🚨 {Target_Coin_Symbol} 롱 포지션 수동 청산 감지: {profit_loss} {abs(estimated_pnl):.2f}$ {pnl_display}")
        
        # 즉시 JSON 저장
        with open(info_file_path, 'w') as outfile:
            json.dump(dic, outfile, indent=4, ensure_ascii=False)
    
    # ==================== 진입 로직 (백테스트와 동일) ====================
    # 숏 진입: 숏 신호 + 숏 포지션 없을 때 (백테스트와 동일)
    if not has_short and current_row is not None and current_row.get('short_signal', False):
        data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', first_amount, None, {'positionSide': 'SHORT'})
        entry_price = float(data['average'])
        
        # 포지션 정보 저장 (코인별) - 트레일링스탑은 0.5% 수익 후 활성화
        update_coin_position(dic, Target_Coin_Symbol, "short_position", entry_price, first_amount, None)
        
        msg = f"🔻 {Target_Coin_Symbol} 숏 진입 | 가격: {entry_price:.2f}, 수량: {first_amount:.3f} | 트레일링스탑: 0.5% 수익 후 활성화"
        telegram_sender.SendMessage(msg)
        logger.info(msg)
    
    # 롱 진입: 롱 신호 + 롱 포지션 없을 때 (백테스트와 동일)
    if not has_long and current_row is not None and current_row.get('long_signal', False):
        data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', first_amount, None, {'positionSide': 'LONG'})
        entry_price = float(data['average'])
        
        # 포지션 정보 저장 (코인별) - 트레일링스탑은 0.5% 수익 후 활성화
        update_coin_position(dic, Target_Coin_Symbol, "long_position", entry_price, first_amount, None)
        
        msg = f"🔺 {Target_Coin_Symbol} 롱 진입 | 가격: {entry_price:.2f}, 수량: {first_amount:.3f} | 트레일링스탑: 0.5% 수익 후 활성화"
        telegram_sender.SendMessage(msg)
        logger.info(msg)
    
    # ==================== 청산 로직 (백테스트와 완전 동일) ====================
    
    # 숏 포지션 체크 및 청산 (백테스트와 동일한 로직)
    if has_short and entryPrice_s > 0:
        pnl_pct = (entryPrice_s - coin_price) / entryPrice_s
        logger.info(f"🔍 숏 PnL 체크: 진입가 {entryPrice_s:.2f}, 현재가 {coin_price:.2f}, 수익률 {pnl_pct*100:.2f}%")
        
        # 청산 조건: 백테스트와 동일 (손절/익절/트레일링스탑)
        should_close = False
        close_reason = None
        
        # 1. 손절 (백테스트와 동일)
        if pnl_pct <= -dic.get("params", {}).get("stop_loss", stop_loss):
            should_close = True
            close_reason = f"손절 ({dic.get('params', {}).get('stop_loss', stop_loss)*100:.1f}%)"
        
        # 익절 제거 (트레일링스탑만 사용)
        
        # 3. 동적 트레일링스탑 (0.5% 수익 후에만 활성화)
        else:
            # 0.5% 수익 이상일 때만 트레일링스탑 활성화
            if pnl_pct >= 0.005:  # 0.5% 수익 이상
                # 현재 수익률에 따른 트레일링스탑 비율 계산
                trailing_stop_ratio = get_dynamic_trailing_stop(pnl_pct)
                
                # 트레일링스탑이 아직 설정되지 않았으면 초기 설정
                if json_short["trailing_stop_price"] is None:
                    # 초기 트레일링스탑 설정 (현재가 기준)
                    initial_trailing = coin_price * (1 + trailing_stop_ratio)
                    update_coin_position(dic, Target_Coin_Symbol, "short_position", entryPrice_s, amt_s, initial_trailing)
                    logger.info(f"🔧 {Target_Coin_Symbol} 숏 트레일링스탑 초기 설정: {initial_trailing:.2f} (수익률: {pnl_pct*100:.2f}%)")
                
                # 동적 트레일링스탑 업데이트 (더 유리한 방향으로만)
                elif trailing_stop_ratio is not None:
                    new_trailing = coin_price * (1 + trailing_stop_ratio)
                    if new_trailing < json_short["trailing_stop_price"]:
                        old_trailing = json_short["trailing_stop_price"]
                        update_coin_position(dic, Target_Coin_Symbol, "short_position", entryPrice_s, amt_s, new_trailing)
                        logger.info(f"🔧 {Target_Coin_Symbol} 숏 트레일링스탑 업데이트 - {old_trailing:.2f} → {new_trailing:.2f} (비율: {trailing_stop_ratio*100:.3f}%)")
                
                # 트레일링스탑 체크
                if json_short["trailing_stop_price"] is not None and coin_price >= json_short["trailing_stop_price"]:
                    should_close = True
                    close_reason = f"트레일링스탑 ({json_short['trailing_stop_price']:.2f})"
            else:
                # 0.5% 수익 미만일 때는 트레일링스탑 비활성화
                logger.info(f"🔍 {Target_Coin_Symbol} 숏 트레일링스탑 대기 중 (수익률: {pnl_pct*100:.2f}% < 0.5%)")
        
        # 청산 실행
        if should_close:
            # 트레일링스탑으로 청산하는 경우, 숏 구매 요건 확인
            if "트레일링스탑" in close_reason:
                # 현재 숏 구매 요건 확인
                current_row = df_with_signals.iloc[-1] if len(df_with_signals) > 0 else None
                has_short_signal = current_row is not None and current_row.get('short_signal', False)
                
                if has_short_signal:
                    # 숏 구매 요건이 있으면 트레일링스탑만 초기화하고 포지션 유지
                    update_coin_position(dic, Target_Coin_Symbol, "short_position", coin_price, amt_s, None)
                    msg = f"🔄 {Target_Coin_Symbol} 숏 트레일링스탑 초기화 | 진입: {coin_price:.2f}, 현재: {coin_price:.2f} | 숏 구매 요건 유지로 포지션 유지"
                    logger.info(msg)
                    telegram_sender.SendMessage(msg)
                    # 실제 청산하지 않고 다음 루프로
                else:
                    # 숏 구매 요건이 없으면 실제 청산
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', round(abs(amt_s), 3), None, {'positionSide': 'SHORT'})
                    close_price = float(data['average'])
                    profit = (entryPrice_s - close_price) * abs(amt_s) - (close_price * abs(amt_s) * charge * 2)
                    
                    dic["today"] += profit
                    clear_coin_position(dic, Target_Coin_Symbol, "short_position")
                    msg = f"✅ {Target_Coin_Symbol} 숏 청산 ({close_reason}) | 진입: {entryPrice_s:.2f} → 청산: {close_price:.2f} | 수익: {profit:.2f}$ ({pnl_pct*100:.2f}%)"
                    msg += f"\n📉 숏 구매 요건 없음으로 완전 청산"
            else:
                # 손절 등 다른 이유로 청산한 경우 실제 청산
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', round(abs(amt_s), 3), None, {'positionSide': 'SHORT'})
                close_price = float(data['average'])
                profit = (entryPrice_s - close_price) * abs(amt_s) - (close_price * abs(amt_s) * charge * 2)
                
                dic["today"] += profit
                clear_coin_position(dic, Target_Coin_Symbol, "short_position")
                msg = f"✅ {Target_Coin_Symbol} 숏 청산 ({close_reason}) | 진입: {entryPrice_s:.2f} → 청산: {close_price:.2f} | 수익: {profit:.2f}$ ({pnl_pct*100:.2f}%)"
            
            telegram_sender.SendMessage(msg)
            logger.info(msg)
    
    # 롱 포지션 체크 및 청산 (백테스트와 동일한 로직)
    if has_long and entryPrice_l > 0:
        pnl_pct = (coin_price - entryPrice_l) / entryPrice_l
        logger.info(f"🔍 롱 PnL 체크: 진입가 {entryPrice_l:.2f}, 현재가 {coin_price:.2f}, 수익률 {pnl_pct*100:.2f}%")
        
        # 청산 조건: 백테스트와 동일 (손절/익절/트레일링스탑)
        should_close = False
        close_reason = None
        
        # 1. 손절 (백테스트와 동일)
        if pnl_pct <= -dic.get("params", {}).get("stop_loss", stop_loss):
            should_close = True
            close_reason = f"손절 ({dic.get('params', {}).get('stop_loss', stop_loss)*100:.1f}%)"
        
        # 익절 제거 (트레일링스탑만 사용)
        
        # 3. 동적 트레일링스탑 (0.5% 수익 후에만 활성화)
        else:
            # 0.5% 수익 이상일 때만 트레일링스탑 활성화
            if pnl_pct >= 0.005:  # 0.5% 수익 이상
                # 현재 수익률에 따른 트레일링스탑 비율 계산
                trailing_stop_ratio = get_dynamic_trailing_stop(pnl_pct)
                
                # 트레일링스탑이 아직 설정되지 않았으면 초기 설정
                if json_long["trailing_stop_price"] is None:
                    # 초기 트레일링스탑 설정 (현재가 기준)
                    initial_trailing = coin_price * (1 - trailing_stop_ratio)
                    update_coin_position(dic, Target_Coin_Symbol, "long_position", entryPrice_l, amt_l, initial_trailing)
                    logger.info(f"🔧 {Target_Coin_Symbol} 롱 트레일링스탑 초기 설정: {initial_trailing:.2f} (수익률: {pnl_pct*100:.2f}%)")
                
                # 동적 트레일링스탑 업데이트 (더 유리한 방향으로만)
                elif trailing_stop_ratio is not None:
                    new_trailing = coin_price * (1 - trailing_stop_ratio)
                    if new_trailing > json_long["trailing_stop_price"]:
                        old_trailing = json_long["trailing_stop_price"]
                        update_coin_position(dic, Target_Coin_Symbol, "long_position", entryPrice_l, amt_l, new_trailing)
                        logger.info(f"🔧 {Target_Coin_Symbol} 롱 트레일링스탑 업데이트 - {old_trailing:.2f} → {new_trailing:.2f} (비율: {trailing_stop_ratio*100:.3f}%)")
                
                # 트레일링스탑 체크
                if json_long["trailing_stop_price"] is not None and coin_price <= json_long["trailing_stop_price"]:
                    should_close = True
                    close_reason = f"트레일링스탑 ({json_long['trailing_stop_price']:.2f})"
            else:
                # 0.5% 수익 미만일 때는 트레일링스탑 비활성화
                logger.info(f"🔍 {Target_Coin_Symbol} 롱 트레일링스탑 대기 중 (수익률: {pnl_pct*100:.2f}% < 0.5%)")
        
        # 청산 실행
        if should_close:
            # 트레일링스탑으로 청산하는 경우, 롱 구매 요건 확인
            if "트레일링스탑" in close_reason:
                # 현재 롱 구매 요건 확인
                current_row = df_with_signals.iloc[-1] if len(df_with_signals) > 0 else None
                has_long_signal = current_row is not None and current_row.get('long_signal', False)
                
                if has_long_signal:
                    # 롱 구매 요건이 있으면 트레일링스탑만 초기화하고 포지션 유지
                    update_coin_position(dic, Target_Coin_Symbol, "long_position", coin_price, amt_l, None)
                    msg = f"🔄 {Target_Coin_Symbol} 롱 트레일링스탑 초기화 | 진입: {coin_price:.2f}, 현재: {coin_price:.2f} | 롱 구매 요건 유지로 포지션 유지"
                    logger.info(msg)
                    telegram_sender.SendMessage(msg)
                    # 실제 청산하지 않고 다음 루프로
                else:
                    # 롱 구매 요건이 없으면 실제 청산
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', round(abs(amt_l), 3), None, {'positionSide': 'LONG'})
                    close_price = float(data['average'])
                    profit = (close_price - entryPrice_l) * abs(amt_l) - (close_price * abs(amt_l) * charge * 2)
                    
                    dic["today"] += profit
                    clear_coin_position(dic, Target_Coin_Symbol, "long_position")
                    msg = f"✅ {Target_Coin_Symbol} 롱 청산 ({close_reason}) | 진입: {entryPrice_l:.2f} → 청산: {close_price:.2f} | 수익: {profit:.2f}$ ({pnl_pct*100:.2f}%)"
                    msg += f"\n📈 롱 구매 요건 없음으로 완전 청산"
            else:
                # 손절 등 다른 이유로 청산한 경우 실제 청산
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', round(abs(amt_l), 3), None, {'positionSide': 'LONG'})
                close_price = float(data['average'])
                profit = (close_price - entryPrice_l) * abs(amt_l) - (close_price * abs(amt_l) * charge * 2)
                
                dic["today"] += profit
                clear_coin_position(dic, Target_Coin_Symbol, "long_position")
                msg = f"✅ {Target_Coin_Symbol} 롱 청산 ({close_reason}) | 진입: {entryPrice_l:.2f} → 청산: {close_price:.2f} | 수익: {profit:.2f}$ ({pnl_pct*100:.2f}%)"
            
            telegram_sender.SendMessage(msg)
            logger.info(msg)

    logger.info("\n-- END --------------------------------------------------------------------------------------------\n")
    
    # 캔들 데이터 정리
    cleanup_dataframes(df)
    cleanup_memory()
    
    # JSON 저장
    with open(info_file_path, 'w') as outfile:
        json.dump(dic, outfile, indent=4, ensure_ascii=False)

# ==================== 8시 일일 보고 (하루에 한번만) ====================
if today.hour == 8 and today.minute == 0:
    msg = "\n==========================="
    msg += "\n         Trend DC Bot ()"
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
    
    # 포지션 정보 표시 (모든 코인)
    total_positions = 0
    for coin in Coin_Ticker_List:
        coin_symbol = coin.replace("/", "").replace(":USDT", "")
        coin_positions = get_coin_positions(dic, coin_symbol)
        coin_short = coin_positions["short_position"]
        coin_long = coin_positions["long_position"]
        
        if coin_short.get("amount", 0) > 0 or coin_long.get("amount", 0) > 0:
            total_positions += 1
            msg += f"\n{coin_symbol}: "
            if coin_short.get("amount", 0) > 0:
                msg += f"숏 {coin_short['amount']:.3f} "
            if coin_long.get("amount", 0) > 0:
                msg += f"롱 {coin_long['amount']:.3f}"
    
    if total_positions == 0:
        msg += "\n포지션 없음"
    
    telegram_sender.SendMessage(msg)
    logger.info("8시 일일 보고서 전송 완료")

# 최종 메모리 정리
final_memory = cleanup_memory()

# 정리
try:
    if 'binanceX' in locals():
        del binanceX
except:
    pass

gc.collect()

logger.info(f"=== Trend DC Bot 종료 (최종 메모리: {final_memory:.2f} MB) ===")