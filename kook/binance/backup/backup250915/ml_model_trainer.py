'''
########################################################################################################################
#   ML Model Trainer for Binance Futures (By kook) - 머신러닝 모델 생성 봇
#
#   === 개요 ===
#   이 봇은 보름(15일)마다 실행되어 최근 15일치 데이터로 머신러닝 모델을 학습하고 저장합니다.
#   저장된 모델은 live_ml_bot.py에서 로드하여 실시간 트레이딩에 사용됩니다.
#   run_advanced_bot_simple.py와 동일한 AdvancedMAMLBot 클래스를 사용합니다.
#
#   === 작동 원리 ===
#   1.  **데이터 수집**: 현재 시간 기준으로 15일치 1분봉 데이터 수집
#   2.  **모델 학습**: AdvancedMAMLBot 클래스를 사용한 머신러닝 모델 학습
#   3.  **백테스팅**: 학습된 모델로 15일치 백테스팅 수행
#   4.  **모델 저장**: 최적 모델을 best_ml_model.json에 저장
#
#   === 실행 주기 ===
#   - crontab: "0 3 1,15 * *" (매월 1일, 15일 새벽 3시)
#
########################################################################################################################
'''

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import pandas as pd
import numpy as np
import json
import datetime as dt
import logging
import traceback
import joblib
import ccxt
import myBinance
import ende_key
import my_key
import telegram_sender as line_alert

# AdvancedMAMLBot 클래스 임포트 (로컬 파일)
from AdvancedMAMLBot import AdvancedMAMLBot

# ========================= 로깅 설정 =========================
def setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    today = dt.datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"ml_trainer_{today}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logging.getLogger('ccxt').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)

logger = setup_logging()

# ========================= 설정 변수 =========================
ACTIVE_COINS = ['BTC/USDT']
TRAINING_DAYS = 15  # 15일치 데이터 사용

# ========================= 바이낸스 데이터 수집 함수 =========================
def get_binance_data(symbol='BTCUSDT', interval='1m', days=15):
    """바이낸스 API에서 직접 데이터 가져오기"""
    try:
        # 암호화된 키 복호화
        simpleEnDecrypt = myBinance.SimpleEnDecrypt(ende_key.ende_key)
        Binance_AccessKey = simpleEnDecrypt.decrypt(my_key.binance_access)
        Binance_ScretKey = simpleEnDecrypt.decrypt(my_key.binance_secret)
        
        # 바이낸스 클라이언트 초기화
        binanceX = ccxt.binance(config={
            'apiKey': Binance_AccessKey,
            'secret': Binance_ScretKey,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })
        
        # 15일치 데이터를 위해 충분한 캔들 수 계산 (1분봉 기준)
        # 15일 * 24시간 * 60분 = 21,600개 캔들
        candle_count = days * 24 * 60
        
        logger.info(f"바이낸스에서 데이터 수집 중...")
        logger.info(f"심볼: {symbol}, 기간: {days}일치 ({candle_count}개 캔들)")
        
        # 바이낸스 API로 데이터 가져오기
        df = myBinance.GetOhlcv(binanceX, symbol, interval, candle_count)
        
        if df is None or df.empty:
            raise ValueError("바이낸스에서 데이터를 가져올 수 없습니다.")
        
        logger.info(f"바이낸스 데이터 수집 완료: {len(df)}개 캔들")
        logger.info(f"데이터 기간: {df.index[0]} ~ {df.index[-1]}")
        
        return df
        
    except Exception as e:
        logger.error(f"바이낸스 데이터 수집 실패: {e}")
        raise

# ========================= 메인 실행 코드 =========================
if __name__ == "__main__":
    logger.info("=== ML Model Trainer 시작 (AdvancedMAMLBot 사용) ===")
    
    try:
        # 바이낸스에서 15일치 실시간 데이터 수집
        logger.info(f"현재 시간 기준 15일치 데이터 수집 시작")
        
        # 바이낸스에서 데이터 수집
        train_df = get_binance_data('BTCUSDT', '1m', TRAINING_DAYS)
        
        # 봇 생성 (run_advanced_bot_simple.py와 동일)
        bot = AdvancedMAMLBot(initial_balance=10000, leverage=50)
        
        # 동적 포지션 사이즈 설정
        bot.base_position_size = 0.05
        bot.increased_position_size = 0.1
        bot.current_position_size = 0.05
        
        logger.info("=== 파라미터 튜닝 시작 ===")
        # 1단계: 파라미터 튜닝
        tune_result = bot.auto_tune_parameters(train_df, n_trials=50)  # 50번 튜닝
        logger.info(f"파라미터 튜닝 완료 - 최고 점수: {tune_result['best_score']:.4f}")
        # 최적 파라미터 상세 출력
        logger.info("최적 파라미터 상세:")
        logger.info(f"  📊 이동평균: 단기={bot.params['ma_short']}, 장기={bot.params['ma_long']}")
        logger.info(f"  💰 거래설정: 스탑로스={bot.params['stop_loss_pct']:.3f}, 익절={bot.params['take_profit_pct']:.3f}")
        logger.info(f"  📈 보조지표: BB={bot.params['bb_period']}/{bot.params['bb_std']}, RSI={bot.params['rsi_period']}, MACD={bot.params['macd_fast']}/{bot.params['macd_slow']}")
        logger.info(f"  🎯 트레일링: {bot.params['trailing_stop_pct']:.3f} (활성화: {bot.params['trailing_stop_activation_pct']:.3f})")
        
        logger.info("=== 모델 훈련 시작 ===")
        # 2단계: 최적 파라미터로 모델 훈련
        train_result = bot.train_ml_model(train_df)
        
        if 'error' in train_result:
            logger.error(f"모델 훈련 실패: {train_result['error']}")
            raise Exception(f"모델 훈련 실패: {train_result['error']}")
        
        logger.info("모델 훈련 완료")
        
        # 모델 저장
        model_dir = os.path.join(os.path.dirname(__file__), "models")
        os.makedirs(model_dir, exist_ok=True)
        
        # 모델 파일명 (현재 날짜 기준)
        current_date = dt.datetime.now().strftime("%Y%m%d")
        model_file = os.path.join(model_dir, f"best_ml_model_{current_date}.joblib")
        scaler_file = os.path.join(model_dir, f"ml_scaler_{current_date}.joblib")
        model_info_file = os.path.join(model_dir, f"ml_model_info_{current_date}.json")
        
        # 모델 저장
        bot.save_ml_model(model_file, scaler_file, model_info_file)
        logger.info(f"모델 저장 완료: {model_file}")
        
        # 모델 정보 생성 (JSON 직렬화를 위해 타입 변환)
        model_info = {
            'model_name': 'AdvancedMAMLBot',
            'training_date': current_date,
            'training_days': int(TRAINING_DAYS),
            'start_date': train_df.index[0].strftime('%Y-%m-%d'),
            'end_date': train_df.index[-1].strftime('%Y-%m-%d'),
            'accuracy': float(tune_result['best_score']),
            'data_points': int(len(train_df)),
            'params': {k: v.item() if hasattr(v, 'item') else v 
                      for k, v in bot.params.items()}
        }
        
        # 최신 모델 정보를 고정 파일명으로 저장
        best_model_file = os.path.join(os.path.dirname(__file__), "best_ml_model.json")
        best_model_info = {
            'model_file': model_file,
            'scaler_file': scaler_file,
            'model_info_file': model_info_file,
            'last_update': dt.datetime.now().isoformat(),
            'coin': 'BTC/USDT',
            'training_date': current_date,
            'model_info': model_info
        }
        
        with open(best_model_file, 'w', encoding='utf-8') as f:
            json.dump(best_model_info, f, indent=4, ensure_ascii=False)
        
        # 텔레그램 알림
        message = f"🤖 ML 모델 학습 완료 (AdvancedMAMLBot)\n\n"
        message += f"📅 학습 날짜: {current_date}\n"
        message += f"📊 학습 기간: {train_df.index[0].strftime('%Y-%m-%d')} ~ {train_df.index[-1].strftime('%Y-%m-%d')} (최근 15일)\n"
        message += f"🎯 파라미터 점수: {tune_result['best_score']:.4f}\n"
        message += f"📈 학습 데이터: {len(train_df)}개 (바이낸스 실시간)\n"
        message += f"🔧 모델: {train_result.get('model_name', 'Unknown')}\n"
        message += f"💾 저장 파일: best_ml_model.json"
        
        line_alert.SendMessage(message)
        
    except Exception as e:
        error_msg = f"ML 모델 학습 실패: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        line_alert.SendMessage(f"🚨 {error_msg}")
    
    logger.info("=== ML Model Trainer 종료 ===")
