'''
########################################################################################################################
#   Live ML Trading Bot for Binance Futures (By kook) - 머신러닝 라이브 트레이딩 봇
#
#   === 개요 ===
#   이 봇은 ml_model_trainer.py에서 생성된 머신러닝 모델을 로드하여 실시간 트레이딩을 수행합니다.
#   Adaptive_Bot.py의 구조를 참고하여 머신러닝 기반으로 개선된 버전입니다.
#
#   === 작동 원리 ===
#   1.  **모델 로드**: best_ml_model.json에서 최신 머신러닝 모델 로드
#   2.  **실시간 데이터 수집**: 1분봉 데이터 수집 및 특성 생성
#   3.  **예측 수행**: 로드된 모델로 매수/매도/보유 신호 생성
#   4.  **거래 실행**: 예측 결과에 따라 롱/숏 포지션 진입/청산
#   5.  **리스크 관리**: ATR 기반 동적 손절매 적용
#   6.  **상태 저장**: 포지션 정보를 JSON 파일에 저장
#
#   === 실행 주기 ===
#   - crontab: "* * * * *" (1분마다 실행)
#
#   === 의존성 ===
#   - best_ml_model.json: ml_model_trainer.py가 생성하는 최적 모델 정보
#   - myBinance.py: 바이낸스 API 연동
#   - telegram_sender.py: 텔레그램 알림
#
########################################################################################################################
'''

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import ccxt
import pandas as pd
import numpy as np
import json
import datetime as dt
import logging
import traceback
import joblib
import time
import gc
import psutil
import myBinance
import ende_key
import my_key
import telegram_sender as line_alert

# AdvancedMAMLBot 클래스 임포트 (로컬 파일)
from AdvancedMAMLBot import AdvancedMAMLBot

# ========================= 전역 설정 변수 =========================
DEFAULT_LEVERAGE = 50  # 안전한 레버리지로 변경
INVESTMENT_RATIO = 0.01  # 투자 비율 (자산의 1%)
COIN_CHARGE = 0.001  # 수수료 설정
ACTIVE_COINS = ['BTC/USDT']

# 동적 포지션 사이즈 관리
BASE_POSITION_RATIO = 0.01  # 기본 포지션 비율 (1%)
INCREASED_POSITION_RATIO = 0.02  # 실패 시 포지션 비율 (2%)

# ========================= 로깅 설정 =========================
def setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    today = dt.datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"ml_bot_{today}.log")
    trade_log_file = os.path.join(log_dir, "ml_bot_trades.log")
    
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

# ========================= 데이터 로드 함수 =========================
def load_data(start_date: str, end_date: str):
    """데이터 로드 (run_advanced_bot_simple.py와 동일)"""
    data_path = r'c:\work\GitHub\py\kook\binance\data\BTC_USDT\1m'
    
    all_data = []
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    # 월별 파일 로드
    current_date = start_dt
    while current_date <= end_dt:
        year = current_date.year
        month = current_date.month
        
        # 파일 경로 생성
        file_pattern = os.path.join(data_path, f"{year}-{month:02d}.csv")
        
        if os.path.exists(file_pattern):
            try:
                df = pd.read_csv(file_pattern)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.set_index('timestamp')
                all_data.append(df)
                logger.info(f"로드 완료: {year}-{month:02d} ({len(df)}개 데이터)")
            except Exception as e:
                logger.error(f"파일 로드 실패: {file_pattern} - {e}")
        else:
            logger.warning(f"파일 없음: {file_pattern}")
        
        # 다음 달로 이동
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
        else:
            try:
                current_date = current_date.replace(month=current_date.month + 1, day=1)
            except ValueError:
                import calendar
                last_day = calendar.monthrange(current_date.year, current_date.month + 1)[1]
                current_date = current_date.replace(month=current_date.month + 1, day=last_day)
    
    if not all_data:
        raise ValueError("로드된 데이터가 없습니다.")
    
    # 모든 데이터 합치기
    combined_df = pd.concat(all_data, ignore_index=False)
    combined_df = combined_df.sort_index()
    
    # 중복 제거
    combined_df = combined_df[~combined_df.index.duplicated(keep='first')]
    
    logger.info(f"총 데이터 로드 완료: {len(combined_df)}개 데이터 포인트")
    logger.info(f"데이터 기간: {combined_df.index[0]} ~ {combined_df.index[-1]}")
    
    return combined_df

# ========================= 메모리 관리 유틸리티 =========================
def cleanup_memory():
    """메모리 정리 함수"""
    try:
        # 가비지 컬렉션 강제 실행
        collected = gc.collect()
        
        # 메모리 사용량 확인
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        logger.info(f"메모리 정리 완료: {collected}개 객체 수집, 현재 사용량: {memory_mb:.2f} MB")
        return memory_mb
    except Exception as e:
        logger.warning(f"메모리 정리 중 오류: {e}")
        return 0

def cleanup_dataframes(*dataframes):
    """데이터프레임들 명시적 삭제"""
    for df in dataframes:
        if df is not None:
            try:
                del df
            except:
                pass

def cleanup_variables(**kwargs):
    """변수들 명시적 삭제"""
    for var_name, var_value in kwargs.items():
        if var_value is not None:
            try:
                del var_value
            except:
                pass

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

# ========================= 동적 포지션 사이즈 관리 =========================
def adjust_position_ratio(dic, trade_result):
    """거래 결과에 따른 포지션 비율 조정"""
    tracking = dic['position_tracking']
    
    if trade_result == 'win':
        # 승리 시: 연속 승리 카운트 증가, 연속 손실 리셋
        tracking['consecutive_wins'] += 1
        tracking['consecutive_losses'] = 0
        
        # 연속 승리 시 기본 포지션 비율로 복원
        if tracking['consecutive_wins'] >= 1:
            tracking['current_ratio'] = BASE_POSITION_RATIO
            logger.info(f"승리! 포지션 비율을 기본값으로 복원: {tracking['current_ratio']:.3f}")
            
    elif trade_result == 'loss':
        # 손실 시: 연속 손실 카운트 증가, 연속 승리 리셋
        tracking['consecutive_losses'] += 1
        tracking['consecutive_wins'] = 0
        
        # 연속 손실 시 포지션 비율 증가
        if tracking['consecutive_losses'] >= 1:
            tracking['current_ratio'] = INCREASED_POSITION_RATIO
            logger.info(f"손실! 포지션 비율을 증가: {tracking['current_ratio']:.3f}")

def get_current_position_ratio(dic):
    """현재 포지션 비율 반환"""
    return dic['position_tracking']['current_ratio']

def calculate_position_size(dic, coin_price):
    """동적 포지션 사이즈 계산"""
    current_ratio = get_current_position_ratio(dic)
    position_size = round((dic['my_money'] * current_ratio * DEFAULT_LEVERAGE) / coin_price, 3)
    return position_size

# ========================= 메인 실행 코드 =========================
if __name__ == "__main__":
    logger.info("=== Live ML Trading Bot 시작 ===")
    
    # 바이낸스 API 설정
    simpleEnDecrypt = myBinance.SimpleEnDecrypt(ende_key.ende_key)
    Binance_AccessKey = simpleEnDecrypt.decrypt(my_key.binance_access)
    Binance_ScretKey = simpleEnDecrypt.decrypt(my_key.binance_secret)
    
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

    # 설정파일 json로드
    info_file_path = os.path.join(os.path.dirname(__file__), "ml_bot.json")
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
            "ml_model_info": {"name": None, "last_update": None, "accuracy": None},
            "position_tracking": {
                "current_ratio": BASE_POSITION_RATIO,  # 현재 포지션 비율
                "consecutive_losses": 0,  # 연속 손실 횟수
                "consecutive_wins": 0     # 연속 승리 횟수
            }
        }

    # --- ML 모델 로드 (ml_model_trainer.py에서 생성된 best_ml_model.json에서 로드) ---
    model_dir = os.path.dirname(__file__)
    best_ml_model_file = os.path.join(model_dir, "best_ml_model.json")
    
    if not os.path.exists(best_ml_model_file):
        logger.error("❌ best_ml_model.json 파일이 없습니다. ml_model_trainer.py를 먼저 실행해주세요.")
        line_alert.SendMessage("🚨[Live ML Bot] best_ml_model.json 파일이 없습니다. ml_model_trainer.py를 먼저 실행해주세요.")
        sys.exit(1)
    
    logger.info(f"📁 사용할 모델 파일: best_ml_model.json")
    
    try:
        with open(best_ml_model_file, 'r', encoding='utf-8') as f:
            best_ml_model_data = json.load(f)
        
        model_file = best_ml_model_data.get('model_file')
        scaler_file = best_ml_model_data.get('scaler_file')
        model_info = best_ml_model_data.get('model_info', {})
        last_update = best_ml_model_data.get('last_update')
        
        if not all([model_file, scaler_file, last_update]):
            logger.error("❌ best_ml_model.json 파일의 데이터가 불완전합니다.")
            line_alert.SendMessage("🚨[Live ML Bot] best_ml_model.json 파일의 데이터가 불완전합니다.")
            sys.exit(1)
        
        # 모델과 스케일러 로드
        if not os.path.exists(model_file) or not os.path.exists(scaler_file):
            logger.error(f"❌ 모델 파일이 없습니다: {model_file} 또는 {scaler_file}")
            line_alert.SendMessage("🚨[Live ML Bot] 모델 파일이 없습니다.")
            sys.exit(1)
        
        ml_model = joblib.load(model_file)
        scaler = joblib.load(scaler_file)
        
        logger.info(f"✅ ML 모델 로드 성공: {model_info.get('model_name', 'Unknown')}")
        logger.info(f"   - 정확도: {model_info.get('accuracy', 'Unknown')}")
        logger.info(f"   - 최종 업데이트: {last_update}")
        logger.info(f"   - 백테스트 수익률: {model_info.get('backtest_return', 'Unknown')}")
        
        # ML 모델 정보를 dic에 저장
        ml_model_info = {
            'name': model_info.get('model_name'),
            'last_update': last_update,
            'accuracy': model_info.get('accuracy'),
            'backtest_return': model_info.get('backtest_return')
        }
        dic['ml_model_info'] = ml_model_info
        
    except Exception as e:
        logger.error(f"❌ ML 모델 로드 실패: {e}")
        line_alert.SendMessage(f"🚨[Live ML Bot] ML 모델 로드 실패: {e}")
        sys.exit(1)
    
    for Target_Coin_Ticker in ACTIVE_COINS:
        logger.info(f"=== {Target_Coin_Ticker} | ML 모델: {ml_model_info.get('name')} ===")
        
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

        # 데이터 수집 (최근 200개 캔들)
        df = myBinance.GetOhlcv(binanceX, Target_Coin_Ticker, '1m', 200)
        coin_price = df['close'].iloc[-1]
        
        # 메모리 사용량 모니터링
        initial_memory = cleanup_memory()
        
        # ATR 계산 (손절가 설정용)
        try:
            import talib
            last_atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14).iloc[-1]
        except:
            last_atr = None
        
        # AdvancedMAMLBot을 사용한 예측
        bot = None
        df_features = None
        features = None
        signal = None
        
        try:
            # 봇 생성 (모델과 스케일러가 이미 로드됨)
            bot = AdvancedMAMLBot(initial_balance=10000, leverage=DEFAULT_LEVERAGE)
            bot.ml_model = ml_model
            bot.scaler = scaler
            
            # 피처 생성 및 신호 예측
            df_features, features = bot.create_features(df)
            signal = bot.generate_signal(df_features, features)
            
            # 예측 결과를 거래 신호로 변환
            action = signal['action']
            confidence = signal['confidence']
            reason = f"ML_{ml_model_info.get('name')}_{action.upper()}"
                
            logger.info(f"ML 예측: {action} (신뢰도: {confidence:.3f})")
                
        except Exception as e:
            log_error(f"ML 예측 실패: {e}", traceback.format_exc())
            action = 'hold'
            reason = "ML 예측 실패"
        finally:
            # ML 예측 관련 변수들 정리
            cleanup_variables(bot=bot, df_features=df_features, features=features, signal=signal)

        long_data = dic['coins'][Target_Coin_Ticker]['long']
        short_data = dic['coins'][Target_Coin_Ticker]['short']
        long_position = long_data['position']
        short_position = short_data['position']
        long_sl_price = long_data.get('stop_loss_price', 0)
        short_sl_price = short_data.get('stop_loss_price', 0)

        # --- ATR 기반 손절 체크 ---
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
                
                # 거래 결과에 따른 포지션 비율 조정
                trade_result = 'win' if profit > 0 else 'loss'
                adjust_position_ratio(dic, trade_result)
                
                log_trade_action('SL_LONG', Target_Coin_Ticker, 'long', exit_price, close_qty, 'ML_ATR_StopLoss', profit, profit_rate)
                profit_emoji = '🟢' if profit > 0 else ('🔴' if profit < 0 else '⚪')
                line_alert.SendMessage(f"{profit_emoji} 롱 포지션 손절(ML+ATR)\n- 코인: {Target_Coin_Ticker}\n- 청산가: {exit_price:.2f}\n- 수량: {close_qty}\n- 수익: {profit:.2f} USDT ({profit_rate:.2f}%)\n- 시작금액: {dic['start_money']:.2f} USDT\n- 현재금액: {dic['my_money']:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")
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
                
                # 거래 결과에 따른 포지션 비율 조정
                trade_result = 'win' if profit > 0 else 'loss'
                adjust_position_ratio(dic, trade_result)
                
                log_trade_action('SL_SHORT', Target_Coin_Ticker, 'short', exit_price, close_qty, 'ML_ATR_StopLoss', profit, profit_rate)
                profit_emoji = '🟢' if profit > 0 else ('🔴' if profit < 0 else '⚪')
                line_alert.SendMessage(f"{profit_emoji} 숏 포지션 손절(ML+ATR)\n- 코인: {Target_Coin_Ticker}\n- 청산가: {exit_price:.2f}\n- 수량: {close_qty}\n- 수익: {profit:.2f} USDT ({profit_rate:.2f}%)\n- 시작금액: {dic['start_money']:.2f} USDT\n- 현재금액: {dic['my_money']:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")
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

        # 동적 포지션 크기 계산
        position_size = calculate_position_size(dic, coin_price)
        minimum_amount = myBinance.GetMinimumAmount(binanceX, Target_Coin_Ticker)
        if position_size < minimum_amount:
            position_size = minimum_amount
            logger.info(f"최소 주문 수량 적용: {position_size}")
        
        # 현재 포지션 비율 로깅
        current_ratio = get_current_position_ratio(dic)
        logger.info(f"현재 포지션 비율: {current_ratio:.3f} ({current_ratio*100:.1f}%)")

        # --- 주문 실행 로직 ---
        if action == 'buy':
            if short_position == 1:
                logger.info("포지션 전환: 숏 포지션 청산")
                try:
                    close_qty = short_data.get('position_size', 0)
                    if close_qty > 0:
                        data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', close_qty, None, {'positionSide': 'SHORT'})
                        exit_price = float(data.get('average', coin_price))
                        
                        profit = (short_data['entry_price'] - exit_price) * close_qty * (1 - (COIN_CHARGE * 2))
                        profit_rate = (short_data['entry_price'] - exit_price) / short_data['entry_price'] * 100.0
                        
                        dic['my_money'] += profit
                        total_profit_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100.0
                        
                        # 거래 결과에 따른 포지션 비율 조정
                        trade_result = 'win' if profit > 0 else 'loss'
                        adjust_position_ratio(dic, trade_result)
                        
                        log_trade_action('SELL_SHORT', Target_Coin_Ticker, 'short', exit_price, close_qty, "ML 포지션 전환", profit, profit_rate)
                        
                        profit_emoji = "🟢" if profit > 0 else ("🔴" if profit < 0 else "⚪")
                        line_alert.SendMessage(f"{profit_emoji} 숏 포지션 청산(ML)\n- 코인: {Target_Coin_Ticker}\n- 청산가: {exit_price:.2f}\n- 수량: {close_qty}\n- 수익: {profit:.2f} USDT ({profit_rate:.2f}%)\n- 시작금액: {dic['start_money']:.2f} USDT\n- 현재금액: {dic['my_money']:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")
                        
                        short_data['position'] = 0
                        short_data['entry_price'] = 0
                        short_data['position_size'] = 0
                        short_data['stop_loss_price'] = 0
                except Exception as e:
                    log_error(f"숏 포지션 청산 실패: {e}", traceback.format_exc())
                    
            if long_position == 0:
                logger.info("신규 진입: 롱 포지션 주문 (ML)")
                try:
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', position_size, None, {'positionSide': 'LONG'})
                    entry_price = float(data.get('average', coin_price))
                    
                    long_data['position'] = 1
                    long_data['entry_price'] = entry_price
                    long_data['position_size'] = position_size
                    # ATR 손절가 설정
                    if last_atr:
                        long_data['stop_loss_price'] = entry_price - (last_atr * 2.0)  # 2x ATR
                    
                    log_trade_action('BUY_LONG', Target_Coin_Ticker, 'long', entry_price, position_size, reason)
                    line_alert.SendMessage(f"🤖📈 롱 포지션 진입(ML)\n- 코인: {Target_Coin_Ticker}\n- 가격: {entry_price:.2f}\n- 수량: {position_size}\n- 모델: {ml_model_info.get('name')}")

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
                        
                        profit = (exit_price - long_data['entry_price']) * close_qty * (1 - (COIN_CHARGE * 2))
                        profit_rate = (exit_price - long_data['entry_price']) / long_data['entry_price'] * 100.0
                        
                        dic['my_money'] += profit
                        total_profit_rate = (dic['my_money'] - dic['start_money']) / dic['start_money'] * 100.0
                        
                        # 거래 결과에 따른 포지션 비율 조정
                        trade_result = 'win' if profit > 0 else 'loss'
                        adjust_position_ratio(dic, trade_result)
                        
                        log_trade_action('SELL_LONG', Target_Coin_Ticker, 'long', exit_price, close_qty, "ML 포지션 전환", profit, profit_rate)
                        
                        profit_emoji = "🟢" if profit > 0 else ("🔴" if profit < 0 else "⚪")
                        line_alert.SendMessage(f"{profit_emoji} 롱 포지션 청산(ML)\n- 코인: {Target_Coin_Ticker}\n- 청산가: {exit_price:.2f}\n- 수량: {close_qty}\n- 수익: {profit:.2f} USDT ({profit_rate:.2f}%)\n- 시작금액: {dic['start_money']:.2f} USDT\n- 현재금액: {dic['my_money']:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")
                        
                        long_data['position'] = 0
                        long_data['entry_price'] = 0
                        long_data['position_size'] = 0
                        long_data['stop_loss_price'] = 0
                except Exception as e:
                    log_error(f"롱 포지션 청산 실패: {e}", traceback.format_exc())

            if short_position == 0:
                logger.info("신규 진입: 숏 포지션 주문 (ML)")
                try:
                    data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', position_size, None, {'positionSide': 'SHORT'})
                    entry_price = float(data.get('average', coin_price))

                    short_data['position'] = 1
                    short_data['entry_price'] = entry_price
                    short_data['position_size'] = position_size
                    # ATR 손절가 설정
                    if last_atr:
                        short_data['stop_loss_price'] = entry_price + (last_atr * 2.0)  # 2x ATR
                    
                    log_trade_action('BUY_SHORT', Target_Coin_Ticker, 'short', entry_price, position_size, reason)
                    line_alert.SendMessage(f"🤖📉 숏 포지션 진입(ML)\n- 코인: {Target_Coin_Ticker}\n- 가격: {entry_price:.2f}\n- 수량: {position_size}\n- 모델: {ml_model_info.get('name')}")

                except Exception as e:
                    log_error(f"숏 포지션 진입 실패: {e}", traceback.format_exc())
        
        # 포지션 정보 파일에 저장
        with open(info_file_path, 'w', encoding='utf-8') as f:
            json.dump(dic, f, indent=4)
        
        # 각 코인 처리 후 메모리 정리
        cleanup_dataframes(df)
        cleanup_memory()

    # 최종 메모리 정리
    logger.info("=== 최종 메모리 정리 시작 ===")
    final_memory = cleanup_memory()
    
    # API 연결 정리
    try:
        if 'binanceX' in locals():
            del binanceX
    except:
        pass
    
    # 전역 변수들 정리
    cleanup_variables(
        ml_model=ml_model,
        scaler=scaler,
        dic=dic,
        simpleEnDecrypt=simpleEnDecrypt
    )
    
    # 최종 가비지 컬렉션
    gc.collect()
    
    logger.info(f"=== Live ML Trading Bot 종료 (최종 메모리: {final_memory:.2f} MB) ===")
