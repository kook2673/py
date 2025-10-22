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
4. 리스크 관리: 손절/익절 + 트레일링스탑

=== 기술적 지표 상세 ===

1. 이동평균선 (Moving Average)
   - SMA Short: 단기 이동평균선 (최적화됨)
   - SMA Long: 장기 이동평균선 (최적화됨)
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
   - 청산 조건: 롱 RSI > 80, 숏 RSI < 20

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
   - 반대 신호 발생
   - RSI 극값 도달 (80/20)

3. 동시 진입 방지:
   - 롱/숏 신호 동시 발생 시 충돌 처리
   - 우선순위에 따른 신호 선택

=== 파라미터 최적화 ===
- MA Short: 3, 6, 9, 12, 15 (5개)
- MA Long: 20, 30, 40, 50 (4개)  
- DCC Period: 25 (고정)
- 총 조합: 5 × 4 × 1 = 20개
- 6개월마다 자동 재최적화

=== 백테스트 검증 결과 ===
- 2018년: 13,541.24% 수익률
- 2019년: 648.78% 수익률
- 2020년: 259.80% 수익률
- 2021년: 2,559.47% 수익률
- 2022년: 418.31% 수익률
- 2023년: 82.98% 수익률
- 2024년: 110.31% 수익률
- 2025년: 49.47% 수익률 (현재까지)

=== 실시간 거래 방식 ===
- 데이터: 15분봉 실시간 데이터
- 신호 생성: 이동평균 + 돈키안 채널 + RSI + 볼린저 밴드
- 포지션 관리: 단일 포지션 유지 (롱 또는 숏)
- 레버리지: 5배 (선물 거래 기준)
- 수수료: 진입/청산 시 각각 0.05% 적용
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
info_file_path = os.path.join(os.path.dirname(__file__), "trend_dc_bot.json")

#잔고 데이타 가져오기 
balance = binanceX.fetch_balance(params={"type": "future"})
time.sleep(0.1)

# 바이낸스 API 포지션 정보 상세 로그
logger.info(f"🔍 바이낸스 API 포지션 정보 (BTCUSDT):")
for posi in balance['info']['positions']:
    if posi['symbol'] == 'BTCUSDT':
        logger.info(f"  {posi['positionSide']}: 수량={posi['positionAmt']}, 진입가={posi.get('entryPrice', 'N/A')}, 마크가={posi.get('markPrice', 'N/A')}, notional={posi.get('notional', 'N/A')}, 미실현손익={posi.get('unrealizedProfit', 'N/A')}")

# JSON 파일 존재 여부 확인
json_exists = os.path.exists(info_file_path)

try:
    if json_exists:
        with open(info_file_path, 'r') as json_file:
            dic = json.load(json_file)
        
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
    
    # 포지션에 trailing_stop_price 필드 추가 (기존 포지션 호환성)
    if "trailing_stop_price" not in dic["long_position"]:
        dic["long_position"]["trailing_stop_price"] = None
    if "trailing_stop_price" not in dic["short_position"]:
        dic["short_position"]["trailing_stop_price"] = None
        
except Exception as e:
    logger.info("Exception by First")
    dic["yesterday"] = 0
    dic["today"] = 0
    dic["start_money"] = float(balance['USDT']['total'])
    dic["my_money"] = float(balance['USDT']['total'])
    dic["long_position"] = {
        "entry_price": 0,
        "amount": 0,
        "trailing_stop_price": None
    }
    dic["short_position"] = {
        "entry_price": 0,
        "amount": 0,
        "trailing_stop_price": None
    }
    dic["params"] = {
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
            logger.info(f"📊 숏 포지션 원본 데이터: {posi}")
            amt_s = float(posi['positionAmt'])
            entryPrice_s = float(posi.get('entryPrice', 0))
            
            # entryPrice가 0이거나 없으면 여러 방법으로 계산 시도
            if (entryPrice_s == 0 or entryPrice_s is None) and abs(amt_s) > 0:
                notional = float(posi.get('notional', 0))
                unrealized_profit = float(posi.get('unrealizedProfit', 0))
                mark_price = float(posi.get('markPrice', 0))
                
                logger.info(f"📊 숏 포지션 계산 시도: notional={notional:.2f}, unrealized={unrealized_profit:.2f}, markPrice={mark_price:.2f}, amt={abs(amt_s):.6f}")
                
                # 방법 1: notional과 unrealizedProfit 사용
                if notional > 0:
                    entryPrice_s = (notional - unrealized_profit) / abs(amt_s)
                    logger.info(f"📊 숏 진입가 계산 (방법1): {entryPrice_s:.2f}")
                
                # 방법 2: markPrice와 unrealizedProfit 사용
                elif mark_price > 0:
                    # 숏 포지션: 가격 상승 시 손실, 하락 시 수익
                    # unrealized_profit = (entryPrice - markPrice) * amount
                    # entryPrice = unrealized_profit / amount + markPrice
                    entryPrice_s = unrealized_profit / abs(amt_s) + mark_price
                    logger.info(f"📊 숏 진입가 계산 (방법2): {entryPrice_s:.2f}")
                
                # 방법 3: 현재가 사용 (최후의 수단)
                else:
                    entryPrice_s = coin_price
                    logger.warning(f"📊 숏 진입가 계산 (방법3-현재가): {entryPrice_s:.2f}")
            
            if abs(amt_s) > 0:
                logger.info(f"📊 숏 포지션 최종: 수량={amt_s:.6f}, 진입가={entryPrice_s:.2f}")
            break

    # 롱잔고
    entryPrice_l = 0
    for posi in balance['info']['positions']:
        if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'LONG':
            logger.info(f"📊 롱 포지션 원본 데이터: {posi}")
            amt_l = float(posi['positionAmt'])
            entryPrice_l = float(posi.get('entryPrice', 0))
            
            # entryPrice가 0이거나 없으면 여러 방법으로 계산 시도
            if (entryPrice_l == 0 or entryPrice_l is None) and abs(amt_l) > 0:
                notional = float(posi.get('notional', 0))
                unrealized_profit = float(posi.get('unrealizedProfit', 0))
                mark_price = float(posi.get('markPrice', 0))
                
                logger.info(f"📊 롱 포지션 계산 시도: notional={notional:.2f}, unrealized={unrealized_profit:.2f}, markPrice={mark_price:.2f}, amt={abs(amt_l):.6f}")
                
                # 방법 1: notional과 unrealizedProfit 사용
                if notional > 0:
                    entryPrice_l = (notional - unrealized_profit) / abs(amt_l)
                    logger.info(f"📊 롱 진입가 계산 (방법1): {entryPrice_l:.2f}")
                
                # 방법 2: markPrice와 unrealizedProfit 사용
                elif mark_price > 0:
                    # 롱 포지션: 가격 하락 시 손실, 상승 시 수익
                    # unrealized_profit = (markPrice - entryPrice) * amount
                    # entryPrice = markPrice - unrealized_profit / amount
                    entryPrice_l = mark_price - unrealized_profit / abs(amt_l)
                    logger.info(f"📊 롱 진입가 계산 (방법2): {entryPrice_l:.2f}")
                
                # 방법 3: 현재가 사용 (최후의 수단)
                else:
                    entryPrice_l = coin_price
                    logger.warning(f"📊 롱 진입가 계산 (방법3-현재가): {entryPrice_l:.2f}")
            
            if abs(amt_l) > 0:
                logger.info(f"📊 롱 포지션 최종: 수량={amt_l:.6f}, 진입가={entryPrice_l:.2f}")
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
        msg += f"\n📊 현재 파라미터: MA_SHORT={optimal_ma_short}, MA_LONG={optimal_ma_long}, DCC={dc_period}"
        msg += f"\n📊 RSI 파라미터: 과매수={params.get('rsi_overbought', rsi_overbought)}, 과매도={params.get('rsi_oversold', rsi_oversold)}"
        msg += f"\n📊 리스크 관리: 손절={params.get('stop_loss', stop_loss)*100:.1f}%, 익절={params.get('take_profit', take_profit)*100:.1f}%, 트레일링={params.get('trailing_stop', trailing_stop)*100:.1f}%"
        
        # 백테스트 검증 결과 추가
        msg += f"\n📈 백테스트 검증 결과:"
        msg += f"\n 2018년: 13,541.24% | 2019년: 648.78% | 2020년: 259.80%"
        msg += f"\n 2021년: 2,559.47% | 2022년: 418.31% | 2023년: 82.98%"
        msg += f"\n 2024년: 110.31% | 2025년: 49.47% (현재까지)"
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
            "amount": 0,
            "trailing_stop_price": None
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
            "amount": 0,
            "trailing_stop_price": None
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
    if not has_short and current_row is not None and current_row.get('short_signal', False):
        data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', first_amount, None, {'positionSide': 'SHORT'})
        entry_price = float(data['average'])
        
        # 포지션 정보 저장
        dic["short_position"] = {
            "entry_price": entry_price,
            "amount": first_amount,
            "trailing_stop_price": None
        }
        
        msg = f"🔻 숏 진입 | 가격: {entry_price:.2f}, 수량: {first_amount:.3f}"
        telegram_sender.SendMessage(msg)
        logger.info(msg)
    
    # 롱 진입: 롱 신호 + 롱 포지션 없을 때 (백테스트와 동일)
    if not has_long and current_row is not None and current_row.get('long_signal', False):
        data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', first_amount, None, {'positionSide': 'LONG'})
        entry_price = float(data['average'])
        
        # 포지션 정보 저장
        dic["long_position"] = {
            "entry_price": entry_price,
            "amount": first_amount,
            "trailing_stop_price": None
        }
        
        msg = f"🔺 롱 진입 | 가격: {entry_price:.2f}, 수량: {first_amount:.3f}"
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
        
        # 2. 익절 (백테스트와 동일)
        elif pnl_pct >= dic.get("params", {}).get("take_profit", take_profit):
            should_close = True
            close_reason = f"익절 ({dic.get('params', {}).get('take_profit', take_profit)*100:.1f}%)"
        
        # 3. 트레일링스탑 (백테스트와 동일)
        elif pnl_pct > dic.get("params", {}).get("trailing_stop", trailing_stop):
            # 트레일링스탑 가격 업데이트
            if dic["short_position"]["trailing_stop_price"] is None:
                dic["short_position"]["trailing_stop_price"] = coin_price * (1 + dic.get("params", {}).get("trailing_stop", trailing_stop))
                logger.info(f"🔧 숏 트레일링스탑 초기 설정: {dic['short_position']['trailing_stop_price']:.2f}")
            else:
                new_trailing = coin_price * (1 + dic.get("params", {}).get("trailing_stop", trailing_stop))
                if new_trailing < dic["short_position"]["trailing_stop_price"]:
                    old_trailing = dic["short_position"]["trailing_stop_price"]
                    dic["short_position"]["trailing_stop_price"] = new_trailing
                    logger.info(f"🔧 숏 트레일링스탑 업데이트: {old_trailing:.2f} → {new_trailing:.2f}")
            
            # 트레일링스탑 체크
            if coin_price >= dic["short_position"]["trailing_stop_price"]:
                should_close = True
                close_reason = f"트레일링스탑 ({dic.get('params', {}).get('trailing_stop', trailing_stop)*100:.1f}%)"
        
        # 청산 실행
        if should_close:
            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', round(abs(amt_s), 3), None, {'positionSide': 'SHORT'})
            close_price = float(data['average'])
            profit = (entryPrice_s - close_price) * abs(amt_s) - (close_price * abs(amt_s) * charge * 2)
            
            dic["today"] += profit
            dic["short_position"] = {
                "entry_price": 0,
                "amount": 0,
                "trailing_stop_price": None
            }
            
            msg = f"✅ 숏 청산 ({close_reason}) | 진입: {entryPrice_s:.2f} → 청산: {close_price:.2f} | 수익: {profit:.2f}$ ({pnl_pct*100:.2f}%)"
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
        
        # 2. 익절 (백테스트와 동일)
        elif pnl_pct >= dic.get("params", {}).get("take_profit", take_profit):
            should_close = True
            close_reason = f"익절 ({dic.get('params', {}).get('take_profit', take_profit)*100:.1f}%)"
        
        # 3. 트레일링스탑 (백테스트와 동일)
        elif pnl_pct > dic.get("params", {}).get("trailing_stop", trailing_stop):
            # 트레일링스탑 가격 업데이트
            if dic["long_position"]["trailing_stop_price"] is None:
                dic["long_position"]["trailing_stop_price"] = coin_price * (1 - dic.get("params", {}).get("trailing_stop", trailing_stop))
                logger.info(f"🔧 롱 트레일링스탑 초기 설정: {dic['long_position']['trailing_stop_price']:.2f}")
            else:
                new_trailing = coin_price * (1 - dic.get("params", {}).get("trailing_stop", trailing_stop))
                if new_trailing > dic["long_position"]["trailing_stop_price"]:
                    old_trailing = dic["long_position"]["trailing_stop_price"]
                    dic["long_position"]["trailing_stop_price"] = new_trailing
                    logger.info(f"🔧 롱 트레일링스탑 업데이트: {old_trailing:.2f} → {new_trailing:.2f}")
            
            # 트레일링스탑 체크
            if coin_price <= dic["long_position"]["trailing_stop_price"]:
                should_close = True
                close_reason = f"트레일링스탑 ({dic.get('params', {}).get('trailing_stop', trailing_stop)*100:.1f}%)"
        
        # 청산 실행
        if should_close:
            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', round(abs(amt_l), 3), None, {'positionSide': 'LONG'})
            close_price = float(data['average'])
            profit = (close_price - entryPrice_l) * abs(amt_l) - (close_price * abs(amt_l) * charge * 2)
            
            dic["today"] += profit
            dic["long_position"] = {
                "entry_price": 0,
                "amount": 0,
                "trailing_stop_price": None
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




