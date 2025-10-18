'''
########################################################################################################################
#   Adaptive Trading Bot for Binance Futures (By kook) - 최적화 분리 버전
#
#   === 개요 ===
#   이 봇은 정적(static)인 단일 전략에 의존하는 대신, 주기적으로 시장 상황을 학습하여
#   가장 성공적인 거래 전략을 스스로 선택하고 적용하는 '적응형(Adaptive)' 트레이딩 봇입니다.
#   Walk-Forward Optimization(WFO) 개념을 라이브 트레이딩에 접목하여, 변화하는 시장에 능동적으로 대응하는 것을 목표로 합니다.
#
#   === 새로운 아키텍처 (최적화 분리) ===
#   기존의 단일 파일 구조에서 최적화와 거래 실행을 분리하여 안정성과 효율성을 향상시켰습니다:
#
#   1.  **optimizer.py** (새로 생성):
#       - 역할: 주기적으로(일요일, 수요일 새벽 3시) 최적의 거래 전략을 찾아 'best_strategy.json' 파일에 저장
#       - 실행 주기: crontab으로 일주일에 2번 (0 3 * * 0,3)
#       - 최적화 방식: 최근 30일 데이터로 다중 전략 백테스트 후 최고 성과 전략 선정
#       - 지원 전략: RSI, 볼린저밴드+ADX, MACD+ADX, 스토캐스틱
#       - 결과 저장: best_strategy.json 파일에 전략명, 파라미터, 업데이트 시간 저장
#
#   2.  **Adaptive_Bot.py** (현재 파일 - 거래 실행 전용):
#       - 역할: 1분마다 실행되어 best_strategy.json에서 전략을 로드하고 실시간 거래 실행
#       - 실행 주기: crontab으로 1분마다 (* * * * *)
#       - 전략 로드: optimizer.py가 생성한 best_strategy.json 파일에서 전략 정보 읽기
#       - 거래 실행: 로드된 전략으로 실시간 시장 신호 생성 및 주문 실행
#       - 오류 처리: best_strategy.json 파일이 없거나 손상된 경우 거래 중단 및 알림
#
#   3.  **strategy_platform.py** (기존 파일):
#       - 역할: 백테스팅 플랫폼 및 다양한 거래 전략 클래스 제공
#       - 사용처: optimizer.py에서 백테스팅용, Adaptive_Bot.py에서 실거래용
#
#   4.  **walk_forward_optimizer.py** (기존 파일):
#       - 역할: 백테스팅 전용 WFO 분석 도구 (그래프 생성 포함)
#       - 사용처: 전략 성과 분석 및 백테스팅 결과 시각화
#
#   === 핵심 작동 원리 ===
#   1.  **전략 최적화 (Optimizer)**:
#       - optimizer.py가 일주일에 2번 실행되어 최근 30일 데이터로 다중 전략 백테스트 수행
#       - 최고 성과 전략과 파라미터를 best_strategy.json 파일에 저장
#       - 텔레그램으로 최적화 완료 알림 전송
#
#   2.  **전략 로드 (Strategy Loading)**:
#       - Adaptive_Bot.py가 실행될 때마다 best_strategy.json 파일에서 전략 정보 로드
#       - 파일이 없거나 손상된 경우 거래 중단 및 오류 로그 기록
#       - 전략 로드 성공 시 로그에 전략명, 파라미터, 최종 업데이트 시간 출력
#
#   3.  **라이브 거래 실행 (Live Trading)**:
#       - 로드된 전략으로 실시간 시장 데이터 분석 및 거래 신호 생성
#       - 롱/숏 포지션 자동 진입/청산 및 포지션 전환
#       - ATR 기반 동적 손절매로 리스크 관리
#       - 모든 거래 내역을 로그 파일과 텔레그램으로 기록
#
#   4.  **상태 저장 및 관리**:
#       - 포지션 정보, 거래 내역 등은 Adaptive_Bot.json 파일에 저장
#       - 전략 정보는 best_strategy.json 파일에서 별도 관리
#       - 봇 재시작 시에도 연속성 유지
#
#   === 크론탭 설정 ===
#   webserver/crontab_config.json 파일에서 다음과 같이 설정:
#   
#   1. Adaptive_Bot.py: "* * * * *" (1분마다 실행)
#   2. optimizer.py: "0 3 * * 0,3" (일요일, 수요일 새벽 3시)
#
#   === 기대 효과 ===
#   - 최적화와 거래 실행의 분리로 안정성 향상
#   - 무거운 최적화 작업이 실시간 거래에 영향 주지 않음
#   - 전략 파일 손상 시에도 안전하게 거래 중단
#   - 일주일에 2번의 최적화로 시장 변화에 더 빠르게 대응
#   - 각 파일의 역할이 명확하여 유지보수성 향상
#
#   === 의존성 ===
#   - strategy_platform.py: 백테스팅 및 전략 클래스
#   - best_strategy.json: optimizer.py가 생성하는 최적 전략 정보
#   - myBinance.py: 바이낸스 API 연동
#   - telegram_sender.py: 텔레그램 알림
#
 ========================= 지원 전략 상세 설명 =========================
# 이 봇에서 사용할 수 있는 전략들의 상세한 설명입니다.
#
# 1. RsiMeanReversion (RSI 평균 회귀 전략)
#    - 기본 개념: RSI(Relative Strength Index) 지표를 사용하여 과매수/과매도 상태를 판단
#    - 작동 원리: 
#      * RSI > 70 (과매수): 숏(매도) 포지션 진입 → 가격이 평균으로 돌아올 것을 기대
#      * RSI < 30 (과매도): 롱(매수) 포지션 진입 → 가격이 평균으로 돌아올 것을 기대
#    - ATR(평균진폭) 활용: 1.5x ATR로 동적 손절매 설정
#    - 장점: 횡보장에서 효과적, 명확한 진입/청산 기준
#    - 단점: 강한 추세장에서는 추세를 거스르는 포지션으로 손실 위험
#    - 적합한 시장: 변동성이 높은 횡보장, RSI가 30-70 구간에서 움직이는 시장
#
# 2. BollingerBandADXStrategy (볼린저밴드 + ADX 전략)
#    - 기본 개념: 볼린저밴드의 상단/하단 밴드와 ADX(평균방향지수)를 결합
#    - 작동 원리:
#      * 가격이 상단 밴드 터치 + ADX > 25 (강한 추세): 숏 포지션 진입
#      * 가격이 하단 밴드 터치 + ADX > 25 (강한 추세): 롱 포지션 진입
#    - 장점: 추세의 강도를 고려한 진입, 밴드 기반 명확한 진입점
#    - 단점: 밴드가 좁아질 때(저변동성) 신호 부족
#    - 적합한 시장: 추세가 명확한 시장, 변동성이 적당한 시장
#
# 3. MacdADXStrategy (MACD + ADX 전략)
#    - 기본 개념: MACD(이동평균수렴확산)와 ADX를 결합한 추세 추종 전략
#    - 작동 원리:
#      * MACD 골든크로스 + ADX > 25: 롱 포지션 진입
#      * MACD 데드크로스 + ADX > 25: 숏 포지션 진입
#    - 장점: 추세 추종으로 큰 수익 가능, ADX로 추세 강도 확인
#    - 단점: 횡보장에서 잦은 신호, 추세 전환점에서 지연
#    - 적합한 시장: 강한 추세가 지속되는 시장, 방향성이 명확한 시장
#
# 4. StochasticStrategy (스토캐스틱 전략)
#    - 기본 개념: 스토캐스틱 오실레이터의 %K, %D 값을 활용한 반전 신호
#    - 작동 원리:
#      * %K < 20 (과매도): 롱 포지션 진입
#      * %K > 80 (과매수): 숏 포지션 진입
#    - 장점: 빠른 반전 신호, 과매수/과매도 판단 정확
#    - 단점: 잦은 신호, 노이즈에 민감
#    - 적합한 시장: 단기 변동성이 큰 시장, 명확한 지지/저항선이 있는 시장
#
# ========================= 전략 선택 기준 =========================
# optimizer.py는 최근 30일 데이터로 각 전략을 백테스팅하여
# 가장 높은 수익률을 보인 전략을 자동으로 선택합니다.
# 현재 선택된 전략: RsiMeanReversion(1.5x ATR)
# - RSI 윈도우: 14 (14일 기준 RSI 계산)
# - 과매수 임계값: 70 (RSI > 70에서 숏 진입)
# - 과매도 임계값: 25 (RSI < 25에서 롱 진입)
# - ATR 배수: 1.5 (평균진폭의 1.5배로 손절매)
#
# ========================= 백테스팅 플랫폼 및 전략 임포트 =========================
########################################################################################################################
'''

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
import ccxt
import time
import datetime as dt
import logging
import traceback
import myBinance
import ende_key
import my_key
import telegram_sender as line_alert
import numpy as np
import json
import itertools
import pandas as pd
import talib

# 백테스팅 플랫폼 및 전략 임포트
# (경로가 올바른지 확인 필요)
try:
    from strategy_platform import run_backtest, RsiMeanReversion, BollingerBandADXStrategy, MacdADXStrategy, StochasticStrategy
except ImportError:
    print("경고: strategy_platform을 찾을 수 없습니다. 상위 폴더를 경로에 추가합니다.")
    # 이 경로 추가는 VSCode 등의 환경에서 직접 실행 시 필요할 수 있음
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from strategy_platform import run_backtest, RsiMeanReversion, BollingerBandADXStrategy, MacdADXStrategy, StochasticStrategy

# ========================= 전역 설정 변수 =========================
DEFAULT_LEVERAGE = 10
INVESTMENT_RATIO = 0.01  # 투자 비율을 90%로 상향
ASSET_SPLIT = 1
COIN_CHARGE = 0.001 # 수수료 설정
# 투자할 코인 리스트
ACTIVE_COINS = ['BTC/USDT']

# ========================= 로깅 시스템 설정 =========================
def setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    today = dt.datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"Adaptive_Bot_{today}.log")
    trade_log_file = os.path.join(log_dir, "Adaptive_Bot_list.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    trade_logger = logging.getLogger('trade_logger')
    trade_logger.setLevel(logging.INFO)
    trade_logger.handlers = []
    trade_logger.propagate = False
    trade_logger.addHandler(logging.FileHandler(trade_log_file, encoding='utf-8'))
    
    logging.getLogger('ccxt').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return logging.getLogger(__name__), trade_logger

logger, trade_logger = setup_logging()

# ========================= 로깅 유틸리티 =========================
def log_trade_action(action_type, coin_ticker, position_side, price, quantity, reason="", profit=0, profit_rate=0):
    try:
        # 수익/손실에 따른 색상 버튼 생성
        if profit > 0:
            profit_button = "🟢"  # 초록색 동그라미 (수익)
        elif profit < 0:
            profit_button = "🔴"  # 빨간색 동그라미 (손실)
        else:
            profit_button = "⚪"  # 흰색 동그라미 (수익/손실 없음)
        
        trade_record = {
            "timestamp": dt.datetime.now().isoformat(), 
            "profit_button": profit_button,
            "action": action_type, 
            "coin": coin_ticker,
            "position": position_side, 
            "price": round(price, 2), 
            "quantity": round(quantity, 3),
            "reason": reason, 
            "profit_usdt": round(profit, 2) if profit != 0 else 0,
            "profit_rate": round(profit_rate, 2) if profit_rate != 0 else 0
        }
        trade_logger.info(json.dumps(trade_record, ensure_ascii=False))
    except Exception as e:
        logger.error(f"거래 기록 로깅 실패: {e}")

def log_error(error_msg, error_detail=None):
    logger.error(f"오류: {error_msg}")
    if error_detail:
        logger.error(f"상세: {error_detail}")

# ========================= 메인 실행 코드 =========================
if __name__ == "__main__":
    simpleEnDecrypt = myBinance.SimpleEnDecrypt(ende_key.ende_key)
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
        safety_margin = -1000
        final_offset = original_offset + safety_margin
        binanceX.options['timeDifference'] = final_offset
        logger.info(f"서버 시간 동기화 완료: 오프셋 {final_offset}ms")
    except Exception as e:
        logger.critical(f"시간 동기화 실패: {e}")
        sys.exit(1)

    # 설정파일 json로드.
    info_file_path = os.path.join(os.path.dirname(__file__), "Adaptive_Bot.json")
    try:
        with open(info_file_path, 'r', encoding='utf-8') as f:
            dic = json.load(f)
        
        # 매 실행 시 실제 잔고를 가져와서 my_money 업데이트
        try:
            current_balance = binanceX.fetch_balance(params={"type": "future"})['USDT']['total']
            old_money = dic['my_money']
            dic['my_money'] = current_balance
            logger.info(f"잔고 업데이트: {old_money:.2f} USDT → {current_balance:.2f} USDT")
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"잔고 조회 실패, 기존 값 유지: {e}")
            
    except FileNotFoundError:
        logger.info("설정 파일이 없어 새로 생성합니다.")
        balance = binanceX.fetch_balance(params={"type": "future"})['USDT']['total']
        time.sleep(0.1)
        dic = {
            "start_money": balance, "my_money": balance,
            "coins": {
                "BTC/USDT": {
                    "long": {"position": 0, "entry_price": 0, "position_size": 0, "stop_loss_price": 0},
                    "short": {"position": 0, "entry_price": 0, "position_size": 0, "stop_loss_price": 0}
                }
            },
            "strategy_info": {"name": None, "params": {}, "last_update": None}
        }

    # --- 전략 정보 로드 (optimizer.py에서 생성된 best_strategy.json 파일에서 로드) ---
    best_strategy_file = os.path.join(os.path.dirname(__file__), "best_strategy.json")
    
    if not os.path.exists(best_strategy_file):
        logger.error("❌ best_strategy.json 파일이 없습니다. optimizer.py를 먼저 실행해주세요.")
        line_alert.SendMessage("🚨[Adaptive_Bot] best_strategy.json 파일이 없습니다. optimizer.py를 먼저 실행해주세요.")
        sys.exit(1)
    
    try:
        with open(best_strategy_file, 'r', encoding='utf-8') as f:
            best_strategy_data = json.load(f)
        
        strategy_name = best_strategy_data.get('name')
        strategy_params = best_strategy_data.get('params')
        last_update = best_strategy_data.get('last_update')
        
        if not all([strategy_name, strategy_params, last_update]):
            logger.error("❌ best_strategy.json 파일의 데이터가 불완전합니다.")
            line_alert.SendMessage("🚨[Adaptive_Bot] best_strategy.json 파일의 데이터가 불완전합니다.")
            sys.exit(1)
            
        logger.info(f"✅ 전략 로드 성공: {strategy_name}")
        logger.info(f"   - 파라미터: {strategy_params}")
        logger.info(f"   - 최종 업데이트: {last_update}")
        
        # 전략 정보를 dic에 저장 (기존 코드와의 호환성을 위해)
        strategy_info = {
            'name': strategy_name,
            'params': strategy_params,
            'last_update': last_update
        }
        dic['strategy_info'] = strategy_info
        
    except Exception as e:
        logger.error(f"❌ best_strategy.json 파일 로드 실패: {e}")
        line_alert.SendMessage(f"🚨[Adaptive_Bot] best_strategy.json 파일 로드 실패: {e}")
        sys.exit(1)
    
    active_strategy_name = strategy_info.get('name')
    active_params = strategy_info.get('params')
    
    if not active_strategy_name:
        logger.error("활성화된 전략이 없습니다. 프로그램을 종료합니다.")
        sys.exit(1)

    for Target_Coin_Ticker in ACTIVE_COINS:
        logger.info(f"=== {Target_Coin_Ticker} | 활성 전략: {active_strategy_name} ===")
        
        Target_Coin_Symbol = Target_Coin_Ticker.replace("/", "")

        # 레버리지 설정
        try:
            leverage_result = binanceX.fapiPrivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': DEFAULT_LEVERAGE})
            logger.info(f"{Target_Coin_Symbol} 레버리지 설정 성공: {DEFAULT_LEVERAGE}배")
        except Exception as e:
            try:
                leverage_result = binanceX.fapiprivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': DEFAULT_LEVERAGE})
                logger.info(f"{Target_Coin_Symbol} 레버리지 설정 성공 (대체): {DEFAULT_LEVERAGE}배")
            except Exception as e2:
                error_msg = f"{Target_Coin_Symbol} 레버리지 설정 실패: {e2}"
                log_error(error_msg)
                continue

        df = myBinance.GetOhlcv(binanceX, Target_Coin_Ticker, '1m', 200)
        coin_price = df['close'].iloc[-1]
        # ATR 계산 (백테스트와 동일: 14)
        try:
            atr_series = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            last_atr = float(atr_series.iloc[-1])
        except Exception:
            last_atr = None
        atr_multiplier = active_params.get('atr_multiplier', 2.0)
        
        long_data = dic['coins'][Target_Coin_Ticker]['long']
        short_data = dic['coins'][Target_Coin_Ticker]['short']
        long_position = long_data['position']
        short_position = short_data['position']
        long_sl_price = long_data.get('stop_loss_price', 0)
        short_sl_price = short_data.get('stop_loss_price', 0)

        # --- ATR 기반 손절 체크 (백테스트 로직 우선 적용) ---
        sl_triggered = False
        try:
            # 롱 포지션 손절: 현재 캔들의 low가 손절가 이하
            if long_position == 1 and long_sl_price and df['low'].iloc[-1] <= long_sl_price:
                close_qty = long_data.get('position_size', 0)
                if close_qty > 0:
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', close_qty, None, {'positionSide': 'LONG'})
                    exit_price = float(data.get('average', coin_price))
                else:
                    exit_price = coin_price
                # 수수료 적용한 수익 계산
                profit = (exit_price - long_data['entry_price']) * close_qty * (1 - (COIN_CHARGE * 2))
                profit_rate = (exit_price - long_data['entry_price']) / long_data['entry_price'] * 100.0 if long_data['entry_price'] else 0
                
                # 자금 업데이트
                dic['my_money'] += profit
                total_profit_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100.0
                
                
                log_trade_action('SL_LONG', Target_Coin_Ticker, 'long', exit_price, close_qty, 'stop_loss', profit, profit_rate)
                profit_emoji = '🟢' if profit > 0 else ('🔴' if profit < 0 else '⚪')
                line_alert.SendMessage(f"{profit_emoji} 롱 포지션 손절(ATR)\n- 코인: {Target_Coin_Ticker}\n- 청산가: {exit_price:.2f}\n- 수량: {close_qty}\n- 수익: {profit:.2f} USDT ({profit_rate:.2f}%)\n- 시작금액: {dic['start_money']:.2f} USDT\n- 현재금액: {dic['my_money']:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")
                long_data['position'] = 0
                long_data['entry_price'] = 0
                long_data['position_size'] = 0
                long_data['stop_loss_price'] = 0
                sl_triggered = True

            # 숏 포지션 손절: 현재 캔들의 high가 손절가 이상
            if not sl_triggered and short_position == 1 and short_sl_price and df['high'].iloc[-1] >= short_sl_price:
                close_qty = short_data.get('position_size', 0)
                if close_qty > 0:
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', close_qty, None, {'positionSide': 'SHORT'})
                    exit_price = float(data.get('average', coin_price))
                else:
                    exit_price = coin_price
                # 수수료 적용한 수익 계산
                profit = (short_data['entry_price'] - exit_price) * close_qty * (1 - (COIN_CHARGE * 2))
                profit_rate = (short_data['entry_price'] - exit_price) / short_data['entry_price'] * 100.0 if short_data['entry_price'] else 0
                
                # 자금 업데이트
                dic['my_money'] += profit
                total_profit_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100.0
                
                
                log_trade_action('SL_SHORT', Target_Coin_Ticker, 'short', exit_price, close_qty, 'stop_loss', profit, profit_rate)
                profit_emoji = '🟢' if profit > 0 else ('🔴' if profit < 0 else '⚪')
                line_alert.SendMessage(f"{profit_emoji} 숏 포지션 손절(ATR)\n- 코인: {Target_Coin_Ticker}\n- 청산가: {exit_price:.2f}\n- 수량: {close_qty}\n- 수익: {profit:.2f} USDT ({profit_rate:.2f}%)\n- 시작금액: {dic['start_money']:.2f} USDT\n- 현재금액: {dic['my_money']:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")
                short_data['position'] = 0
                short_data['entry_price'] = 0
                short_data['position_size'] = 0
                short_data['stop_loss_price'] = 0
                sl_triggered = True
        except Exception as e:
            log_error(f"손절 처리 실패: {e}", traceback.format_exc())

        if sl_triggered:
            with open(info_file_path, 'w', encoding='utf-8') as f:
                json.dump(dic, f, indent=4)
            continue

        try:
            strategy_class = eval(active_strategy_name)
            strategy = strategy_class(df, active_params)
            signals = strategy.generate_signals()
            action = signals.iloc[-1]
            reason = f"{active_strategy_name}({active_params.get('atr_multiplier', 'N/A')}x ATR)"
            logger.info(f"신호: {action} | 사유: {reason}")
        except Exception as e:
            log_error(f"신호 생성 오류: {e}", traceback.format_exc())
            action = 'hold'

        position_size = round((dic['my_money'] * INVESTMENT_RATIO * DEFAULT_LEVERAGE) / coin_price, 3)
        minimum_amount = myBinance.GetMinimumAmount(binanceX, Target_Coin_Ticker)
        if position_size < minimum_amount:
            position_size = minimum_amount
            logger.info(f"최소 주문 수량 적용: {position_size}")

        # --- 주문 실행 로직 ---
        if action == 'buy':
            if short_position == 1:
                logger.info("포지션 전환: 숏 포지션 청산")
                try:
                    # 현재 보유 수량으로 전량 청산
                    close_qty = short_data.get('position_size', 0)
                    if close_qty > 0:
                        data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', close_qty, None, {'positionSide': 'SHORT'})
                        exit_price = float(data.get('average', coin_price))
                        
                        # 수수료 적용한 수익 계산
                        profit = (short_data['entry_price'] - exit_price) * close_qty * (1 - (COIN_CHARGE * 2))
                        profit_rate = (short_data['entry_price'] - exit_price) / short_data['entry_price'] * 100.0
                        
                        # 자금 업데이트
                        dic['my_money'] += profit
                        total_profit_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100.0
                        
                        
                        log_trade_action('SELL_SHORT', Target_Coin_Ticker, 'short', exit_price, close_qty, "포지션 전환", profit, profit_rate)
                        
                        # 수익/손실에 따른 색상 동그라미
                        if profit > 0:
                            profit_emoji = "🟢"  # 초록색 동그라미 (수익)
                        elif profit < 0:
                            profit_emoji = "🔴"  # 빨간색 동그라미 (손실)
                        else:
                            profit_emoji = "⚪"  # 흰색 동그라미 (수익/손실 없음)
                        
                        line_alert.SendMessage(f"{profit_emoji} 숏 포지션 청산\n- 코인: {Target_Coin_Ticker}\n- 청산가: {exit_price:.2f}\n- 수량: {close_qty}\n- 수익: {profit:.2f} USDT ({profit_rate:.2f}%)\n- 시작금액: {dic['start_money']:.2f} USDT\n- 현재금액: {dic['my_money']:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")
                        
                        # 포지션 정보 초기화
                        short_data['position'] = 0
                        short_data['entry_price'] = 0
                        short_data['position_size'] = 0
                        short_data['stop_loss_price'] = 0
                except Exception as e:
                    log_error(f"숏 포지션 청산 실패: {e}", traceback.format_exc())
                    
            if long_position == 0:
                logger.info("신규 진입: 롱 포지션 주문")
                try:
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', position_size, None, {'positionSide': 'LONG'})
                    entry_price = float(data.get('average', coin_price))
                    
                    # 포지션 정보 업데이트
                    long_data['position'] = 1
                    long_data['entry_price'] = entry_price
                    long_data['position_size'] = position_size
                    # ATR 손절가 설정
                    if last_atr:
                        long_data['stop_loss_price'] = entry_price - (last_atr * atr_multiplier)
                    
                    log_trade_action('BUY_LONG', Target_Coin_Ticker, 'long', entry_price, position_size, reason)
                    line_alert.SendMessage(f"📈 롱 포지션 진입\n- 코인: {Target_Coin_Ticker}\n- 가격: {entry_price:.2f}\n- 수량: {position_size}")

                except Exception as e:
                    log_error(f"롱 포지션 진입 실패: {e}", traceback.format_exc())
        
        elif action == 'sell':
            if long_position == 1:
                logger.info("포지션 전환: 롱 포지션 청산")
                try:
                    close_qty = long_data.get('position_size', 0)
                    if close_qty > 0:
                        data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', close_qty, None, {'positionSide': 'LONG'})
                        exit_price = float(data.get('average', coin_price))
                        
                        # 수수료 적용한 수익 계산
                        profit = (exit_price - long_data['entry_price']) * close_qty * (1 - (COIN_CHARGE * 2))
                        profit_rate = (exit_price - long_data['entry_price']) / long_data['entry_price'] * 100.0
                        
                        # 자금 업데이트
                        dic['my_money'] += profit
                        total_profit_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100.0
                        
                        
                        log_trade_action('SELL_LONG', Target_Coin_Ticker, 'long', exit_price, close_qty, "포지션 전환", profit, profit_rate)
                        
                        # 수익/손실에 따른 색상 동그라미
                        if profit > 0:
                            profit_emoji = "🟢"  # 초록색 동그라미 (수익)
                        elif profit < 0:
                            profit_emoji = "🔴"  # 빨간색 동그라미 (손실)
                        else:
                            profit_emoji = "⚪"  # 흰색 동그라미 (수익/손실 없음)
                        
                        line_alert.SendMessage(f"{profit_emoji} 롱 포지션 청산\n- 코인: {Target_Coin_Ticker}\n- 청산가: {exit_price:.2f}\n- 수량: {close_qty}\n- 수익: {profit:.2f} USDT ({profit_rate:.2f}%)\n- 시작금액: {dic['start_money']:.2f} USDT\n- 현재금액: {dic['my_money']:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")
                        
                        # 포지션 정보 초기화
                        long_data['position'] = 0
                        long_data['entry_price'] = 0
                        long_data['position_size'] = 0
                        long_data['stop_loss_price'] = 0
                except Exception as e:
                    log_error(f"롱 포지션 청산 실패: {e}", traceback.format_exc())

            if short_position == 0:
                logger.info("신규 진입: 숏 포지션 주문")
                try:
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', position_size, None, {'positionSide': 'SHORT'})
                    entry_price = float(data.get('average', coin_price))

                    # 포지션 정보 업데이트
                    short_data['position'] = 1
                    short_data['entry_price'] = entry_price
                    short_data['position_size'] = position_size
                    # ATR 손절가 설정
                    if last_atr:
                        short_data['stop_loss_price'] = entry_price + (last_atr * atr_multiplier)
                    
                    log_trade_action('BUY_SHORT', Target_Coin_Ticker, 'short', entry_price, position_size, reason)
                    line_alert.SendMessage(f"📉 숏 포지션 진입\n- 코인: {Target_Coin_Ticker}\n- 가격: {entry_price:.2f}\n- 수량: {position_size}")

                except Exception as e:
                    log_error(f"숏 포지션 진입 실패: {e}", traceback.format_exc())
        
        # 포지션 정보 파일에 저장
        with open(info_file_path, 'w', encoding='utf-8') as f:
            json.dump(dic, f, indent=4)

    logger.info("=== Adaptive Trading Bot 종료 ===")
