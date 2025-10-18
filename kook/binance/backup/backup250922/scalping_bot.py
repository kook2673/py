'''
########################################################################################################################
#   Live Scalping ML Trading Bot for Binance Futures (By kook) - 단타 머신러닝 라이브 트레이딩 봇
#
#   === 개요 ===
#   이 봇은 매월 1일에 자동으로 단타용 머신러닝 모델을 학습하고, 
#   학습된 모델을 사용하여 실시간 단타 트레이딩을 수행합니다.
#
#   === 작동 원리 ===
#   1.  **매월 1일 자동 학습**: 이전 달 데이터로 단타용 모델 학습
#   2.  **모델 자동 로드**: 학습된 모델을 자동으로 로드하여 사용
#   3.  **실시간 데이터 수집**: 1분봉 데이터 수집 및 단타용 특성 생성
#   4.  **단타 신호 생성**: 학습된 모델로 단타 매수/매도/보유 신호 생성
#   5.  **거래 실행**: 단타 전용 파라미터로 롱/숏 포지션 진입/청산
#   6.  **리스크 관리**: 단타용 ATR 기반 동적 손절매 적용
#   7.  **상태 저장**: 포지션 정보를 JSON 파일에 저장
#
#   === 실행 주기 ===
#   - crontab: "* * * * *" (1분마다 실행)
#   - 매월 1일: 자동 모델 재학습
#
#   === 의존성 ===
#   - advanced_ma_ml_bot.py: 단타용 머신러닝 모델 학습
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
import warnings
import myBinance
import ende_key
import my_key
import telegram_sender as line_alert
import subprocess
from pathlib import Path
import talib
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from typing import Dict, List, Tuple, Optional, Any

# AdvancedMAMLBot 클래스는 아래에 직접 구현

# ========================= 전역 설정 변수 =========================
DEFAULT_LEVERAGE = 10  # 단타용 레버리지
INVESTMENT_RATIO = 0.01  # 투자 비율 (자산의 1%)
COIN_CHARGE = 0.0005  # 단타용 수수료 (0.05%)
ACTIVE_COINS = ['BTC/USDT']

# 단타용 동적 포지션 사이즈 관리
BASE_POSITION_RATIO = 0.01  # 기본 포지션 비율 (1%)
INCREASED_POSITION_RATIO = 0.02  # 실패 시 포지션 비율 (2%)

# 단타용 파라미터
SCALPING_PARAMS = {
    'ma_short': 2,  # 매우 짧은 이동평균
    'ma_long': 8,   # 짧은 이동평균
    'stop_loss_pct': 0.003,  # 0.3% 스탑로스
    'take_profit_pct': 0.008,  # 0.8% 익절
    'trailing_stop_pct': 0.005,  # 0.5% 트레일링 스탑
    'trailing_stop_activation_pct': 0.003,  # 0.3% 트레일링 활성화
    'position_size': 0.15,  # 15% 포지션 크기
    'max_positions': 4,  # 더 많은 포지션 허용
    'max_long_positions': 2,
    'max_short_positions': 2,
    'rsi_period': 7,  # 더 빠른 RSI
    'stoch_k': 7,     # 더 빠른 스토캐스틱
    'stoch_d': 3,     # 스토캐스틱 D
    'bb_period': 10,  # 더 빠른 볼린저밴드
    'bb_std': 2.0,    # 볼린저밴드 표준편차
    'macd_fast': 5,   # 더 빠른 MACD
    'macd_slow': 13,
    'macd_signal': 4,
    'atr_period': 14,
    'adx_period': 14,
    'cci_period': 20,
    'williams_period': 14,
    'mfi_period': 14,
    'obv_period': 10,
    'roc_period': 10,
    'momentum_period': 10,
    'kama_period': 30,
    'trix_period': 14,
    'ultosc_period1': 7,
    'ultosc_period2': 14,
    'ultosc_period3': 28,
    'aroon_period': 14,
    'dx_period': 14,
    'minus_di_period': 14,
    'plus_di_period': 14,
    'ppo_fast': 12,
    'ppo_slow': 26,
    'ppo_signal': 9
}

# ========================= 로깅 설정 =========================
def setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    today = dt.datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"scalping_bot_{today}.log")
    trade_log_file = os.path.join(log_dir, "scalping_bot_trades.log")
    
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
def load_live_data(binanceX, symbol: str = 'BTC/USDT', days: int = 60):
    """바이낸스 API를 사용해서 실시간 데이터 로드 (5분봉, 2달)"""
    logger.info(f"=== {symbol} 실시간 데이터 로드 시작 ({days}일, 5분봉) ===")
    
    try:
        # 현재 시간부터 30일 전까지의 데이터 요청
        end_time = int(dt.datetime.now().timestamp() * 1000)
        start_time = end_time - (days * 24 * 60 * 60 * 1000)  # 30일 전
        
        logger.info(f"데이터 요청 기간: {dt.datetime.fromtimestamp(start_time/1000)} ~ {dt.datetime.fromtimestamp(end_time/1000)}")
        
        # 5분봉 데이터 요청 (최대 1000개씩)
        all_data = []
        current_start = start_time
        
        while current_start < end_time:
            try:
                # 1000개씩 요청 (약 83.3시간 = 3.5일)
                ohlcv = binanceX.fetch_ohlcv(symbol, '5m', since=current_start, limit=1000)
                
                if not ohlcv:
                    break
                
                # DataFrame으로 변환
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df = df.set_index('timestamp')
                
                all_data.append(df)
                logger.info(f"로드 완료: {df.index[0]} ~ {df.index[-1]} ({len(df)}개 데이터)")
                
                # 다음 배치를 위해 시작 시간 업데이트
                current_start = int(df.index[-1].timestamp() * 1000) + 300000  # 5분 추가
                
                # API 제한 방지
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"데이터 요청 실패: {e}")
                break
        
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
        
    except Exception as e:
        logger.error(f"실시간 데이터 로드 실패: {e}")
        raise

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

# ========================= AdvancedMAMLBot 클래스 =========================
class AdvancedMAMLBot:
    """단타용 머신러닝 봇 클래스 (scalping_january_test.py에서 가져옴)"""
    
    def __init__(self, initial_balance: float = 10000, leverage: int = 20):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.leverage = leverage
        
        # 단타용 파라미터 설정
        self.params = {
            'ma_short': 2,  # 매우 짧은 이동평균
            'ma_long': 8,   # 짧은 이동평균
            'stop_loss_pct': 0.003,  # 0.3% 스탑로스
            'take_profit_pct': 0.008,  # 0.8% 익절
            'trailing_stop_pct': 0.005,  # 0.5% 트레일링 스탑
            'trailing_stop_activation_pct': 0.003,  # 0.3% 트레일링 활성화
            'position_size': 0.15,  # 15% 포지션 크기
            'max_positions': 4,  # 더 많은 포지션 허용
            'max_long_positions': 2,
            'max_short_positions': 2,
            'rsi_period': 7,  # 더 빠른 RSI
            'stoch_k': 7,     # 더 빠른 스토캐스틱
            'stoch_d': 3,     # 스토캐스틱 D
            'bb_period': 10,  # 더 빠른 볼린저밴드
            'bb_std': 2.0,    # 볼린저밴드 표준편차
            'macd_fast': 5,   # 더 빠른 MACD
            'macd_slow': 13,
            'macd_signal': 4,
            'atr_period': 14,
            'adx_period': 14,
            'cci_period': 20,
            'williams_period': 14,
            'mfi_period': 14,
            'obv_period': 10,
            'roc_period': 10,
            'momentum_period': 10,
            'kama_period': 30,
            'trix_period': 14,
            'ultosc_period1': 7,
            'ultosc_period2': 14,
            'ultosc_period3': 28,
            'aroon_period': 14,
            'dx_period': 14,
            'minus_di_period': 14,
            'plus_di_period': 14,
            'ppo_fast': 12,
            'ppo_slow': 26,
            'ppo_signal': 9
        }
        
        # 고정 보조지표 파라미터
        self.fixed_indicators = {
            'rsi2_period': 2,
            'bop_period': 14,
            'minus_dm_period': 14,
            'plus_dm_period': 14
        }
        
        # 머신러닝 모델
        self.ml_model = None
        self.scaler = StandardScaler()
        self.feature_importance = None
        
        # 포지션 관리
        self.positions = []
        self.position_id = 0
        
        # 성과 추적
        self.trades = []
        self.daily_pnl = []
        self.balance_history = []
        
        # 백테스트 설정
        self.slippage = 0.0005  # 0.05% 슬리피지
        self.commission = 0.0005  # 0.05% 수수료 (매수/매도 각각)
        
        # 통계
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.max_drawdown = 0
        self.peak_balance = initial_balance
        
        # 동적 포지션 사이즈 관리
        self.current_position_size = 0.1
        self.base_position_size = 0.1
        self.increased_position_size = 0.2
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        
        # 스캘핑 모드 설정
        self._scalping_mode = True
        
        logger.info(f"단타용 봇 초기화 완료 - 초기자본: ${initial_balance:,.2f}")
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """21가지 보조지표 계산"""
        df = df.copy()
        
        # 모든 지표 파라미터 통합
        all_indicators = {**self.params, **self.fixed_indicators}
        
        # 1. 이동평균선
        if all_indicators['ma_short'] > 0:
            df['ma_short'] = talib.SMA(df['close'], timeperiod=all_indicators['ma_short'])
        else:
            df['ma_short'] = 0
            
        if all_indicators['ma_long'] > 0:
            df['ma_long'] = talib.SMA(df['close'], timeperiod=all_indicators['ma_long'])
        else:
            df['ma_long'] = 0
        
        # 2. 볼린저밴드
        if all_indicators['bb_period'] > 0 and all_indicators['bb_std'] > 0:
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
                df['close'], timeperiod=all_indicators['bb_period'], nbdevup=all_indicators['bb_std'], 
                nbdevdn=all_indicators['bb_std'], matype=0
            )
        else:
            df['bb_upper'] = df['bb_middle'] = df['bb_lower'] = 0
        
        # 3. RSI
        if all_indicators['rsi_period'] > 0:
            df['rsi'] = talib.RSI(df['close'], timeperiod=all_indicators['rsi_period'])
        else:
            df['rsi'] = 50
        
        # 4. 스토캐스틱
        if all_indicators['stoch_k'] > 0:
            df['stoch_k'], df['stoch_d'] = talib.STOCH(
                df['high'], df['low'], df['close'], 
                fastk_period=all_indicators['stoch_k'], slowk_period=3, slowd_period=all_indicators['stoch_d']
            )
        else:
            df['stoch_k'] = df['stoch_d'] = 50
        
        # 5. MACD
        if all_indicators['macd_fast'] > 0 and all_indicators['macd_slow'] > 0 and all_indicators['macd_signal'] > 0:
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(
                df['close'], fastperiod=all_indicators['macd_fast'], 
                slowperiod=all_indicators['macd_slow'], signalperiod=all_indicators['macd_signal']
            )
        else:
            df['macd'] = df['macd_signal'] = df['macd_hist'] = 0
        
        # 6. ATR
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=all_indicators['atr_period'])
        
        # 7. ADX
        df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=all_indicators['adx_period'])
        
        # 8. CCI
        df['cci'] = talib.CCI(df['high'], df['low'], df['close'], timeperiod=all_indicators['cci_period'])
        
        # 9. Williams %R
        df['williams_r'] = talib.WILLR(df['high'], df['low'], df['close'], timeperiod=all_indicators['williams_period'])
        
        # 10. MFI
        df['mfi'] = talib.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=all_indicators['mfi_period'])
        
        # 11. OBV
        df['obv'] = talib.OBV(df['close'], df['volume'])
        df['obv_ma'] = talib.SMA(df['obv'], timeperiod=all_indicators['obv_period'])
        
        # 12. ROC
        df['roc'] = talib.ROC(df['close'], timeperiod=all_indicators['roc_period'])
        
        # 13. Momentum
        df['momentum'] = talib.MOM(df['close'], timeperiod=all_indicators['momentum_period'])
        
        # 14. KAMA
        df['kama'] = talib.KAMA(df['close'], timeperiod=all_indicators['kama_period'])
        
        # 15. TRIX
        df['trix'] = talib.TRIX(df['close'], timeperiod=all_indicators['trix_period'])
        
        # 16. Ultimate Oscillator
        df['ultosc'] = talib.ULTOSC(
            df['high'], df['low'], df['close'], 
            timeperiod1=all_indicators['ultosc_period1'], 
            timeperiod2=all_indicators['ultosc_period2'], 
            timeperiod3=all_indicators['ultosc_period3']
        )
        
        # 17. Aroon
        df['aroon_up'], df['aroon_down'] = talib.AROON(
            df['high'], df['low'], timeperiod=all_indicators['aroon_period']
        )
        
        # 18. BOP
        df['bop'] = talib.BOP(df['open'], df['high'], df['low'], df['close'])
        
        # 19. DX
        df['dx'] = talib.DX(df['high'], df['low'], df['close'], timeperiod=all_indicators['dx_period'])
        
        # 20. MINUS_DI, PLUS_DI
        df['minus_di'] = talib.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=all_indicators['minus_di_period'])
        df['plus_di'] = talib.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=all_indicators['plus_di_period'])
        
        # 21. PPO
        df['ppo'] = talib.PPO(df['close'], fastperiod=all_indicators['ppo_fast'], slowperiod=all_indicators['ppo_slow'])
        
        return df
    
    def create_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """머신러닝용 피처 생성"""
        df = self.calculate_technical_indicators(df)
        
        # 기본 피처
        features = [
            'ma_short', 'ma_long', 'bb_upper', 'bb_middle', 'bb_lower',
            'rsi', 'stoch_k', 'stoch_d', 'macd', 'macd_signal', 'macd_hist',
            'atr', 'adx', 'cci', 'williams_r', 'mfi', 'obv', 'obv_ma',
            'roc', 'momentum', 'kama', 'trix', 'ultosc', 'aroon_up', 'aroon_down',
            'bop', 'dx', 'minus_di', 'plus_di', 'ppo'
        ]
        
        # 파생 피처 생성
        df['ma_cross'] = (df['ma_short'] > df['ma_long']).astype(int)
        
        # 볼린저밴드 위치
        bb_range = df['bb_upper'] - df['bb_lower']
        df['bb_position'] = np.where(
            bb_range != 0, 
            (df['close'] - df['bb_lower']) / bb_range, 
            0.5
        )
        
        df['rsi_oversold'] = (df['rsi'] < 30).astype(int)
        df['rsi_overbought'] = (df['rsi'] > 70).astype(int)
        df['stoch_oversold'] = (df['stoch_k'] < 20).astype(int)
        df['stoch_overbought'] = (df['stoch_k'] > 80).astype(int)
        df['macd_bullish'] = (df['macd'] > df['macd_signal']).astype(int)
        df['macd_bearish'] = (df['macd'] < df['macd_signal']).astype(int)
        
        # 가격 변화율
        df['price_change_1'] = df['close'].pct_change(1)
        df['price_change_5'] = df['close'].pct_change(5)
        df['price_change_10'] = df['close'].pct_change(10)
        
        # 볼륨 변화율
        df['volume_change_1'] = df['volume'].pct_change(1)
        df['volume_change_5'] = df['volume'].pct_change(5)
        
        # 변동성
        df['volatility_5'] = df['close'].rolling(5).std()
        df['volatility_20'] = df['close'].rolling(20).std()
        
        # 추가 피처
        features.extend([
            'ma_cross', 'bb_position', 'rsi_oversold', 'rsi_overbought',
            'stoch_oversold', 'stoch_overbought', 'macd_bullish', 'macd_bearish',
            'price_change_1', 'price_change_5', 'price_change_10',
            'volume_change_1', 'volume_change_5', 'volatility_5', 'volatility_20'
        ])
        
        # NaN/Inf 값 처리
        for feature in features:
            if feature in df.columns:
                df[feature] = df[feature].replace([np.inf, -np.inf], np.nan)
                
                if 'change' in feature or 'pct_change' in feature:
                    df[feature] = df[feature].ffill()
                    df[feature] = df[feature].fillna(0)
                elif 'volatility' in feature or 'std' in feature:
                    median_val = df[feature].median()
                    df[feature] = df[feature].fillna(median_val if not pd.isna(median_val) else 0)
                elif 'bb_position' in feature:
                    df[feature] = df[feature].fillna(0.5)
                elif 'rsi' in feature or 'stoch' in feature:
                    df[feature] = df[feature].fillna(50)
                elif 'oversold' in feature or 'overbought' in feature or 'bullish' in feature or 'bearish' in feature:
                    df[feature] = df[feature].fillna(0)
                else:
                    median_val = df[feature].median()
                    df[feature] = df[feature].fillna(median_val if not pd.isna(median_val) else 0)
        
        return df, features
    
    def create_labels(self, df: pd.DataFrame, lookforward: int = 5, scalping_mode: bool = True) -> pd.Series:
        """단타용 라벨링 전략"""
        labels = pd.Series(0, index=df.index)
        
        # 미래 가격 데이터 계산
        future_prices = df['close'].shift(-lookforward)
        current_prices = df['close']
        
        # 각 시점에서 lookforward 기간 동안의 최고가/최저가 계산
        max_prices = []
        min_prices = []
        
        for i in range(len(df)):
            if i + lookforward < len(df):
                future_window = df['close'].iloc[i:i+lookforward+1]
                max_price = future_window.max()
                min_price = future_window.min()
            else:
                max_price = current_prices.iloc[i]
                min_price = current_prices.iloc[i]
            
            max_prices.append(max_price)
            min_prices.append(min_price)
        
        max_prices = pd.Series(max_prices, index=df.index)
        min_prices = pd.Series(min_prices, index=df.index)
        
        # 단타용 라벨링 전략
        for i in range(len(df)):
            if i + lookforward >= len(df):
                continue
                
            current_price = current_prices.iloc[i]
            max_price = max_prices.iloc[i]
            min_price = min_prices.iloc[i]
            
            # 상승/하락 비율 계산
            max_gain = (max_price - current_price) / current_price
            max_loss = (current_price - min_price) / current_price
            
            # 단타용 라벨링 (더 작은 수익 목표)
            long_condition = (max_gain >= 0.005) and (max_loss <= 0.002)
            short_condition = (max_loss >= 0.005) and (max_gain <= 0.002)
            strong_long_condition = (max_gain >= 0.01) and (max_loss <= 0.001)
            strong_short_condition = (max_loss >= 0.01) and (max_gain <= 0.001)
            
            # 라벨 할당
            if strong_long_condition:
                labels.iloc[i] = 2  # 강한 롱 신호
            elif strong_short_condition:
                labels.iloc[i] = -2  # 강한 숏 신호
            elif long_condition:
                labels.iloc[i] = 1   # 일반 롱 신호
            elif short_condition:
                labels.iloc[i] = -1  # 일반 숏 신호
            else:
                labels.iloc[i] = 0   # 횡보
        
        return labels
    
    def train_ml_model(self, df: pd.DataFrame) -> Dict:
        """머신러닝 모델 훈련"""
        logger.info("머신러닝 모델 훈련 시작...")
        
        # 피처 및 라벨 생성
        df_features, features = self.create_features(df)
        labels = self.create_labels(df_features, scalping_mode=True)
        
        # 결측값 제거
        valid_idx = ~(df_features[features].isna().any(axis=1) | labels.isna())
        X = df_features[features].loc[valid_idx]
        y = labels.loc[valid_idx]
        
        if len(X) < 1000:
            logger.warning("훈련 데이터가 부족합니다.")
            return {'error': '훈련 데이터 부족'}
        
        # 클래스 분포 확인
        class_counts = y.value_counts()
        logger.info(f"클래스 분포: {dict(class_counts)}")
        
        # 최소 클래스 샘플 수 확인
        min_class_count = class_counts.min()
        if min_class_count < 2:
            logger.warning(f"최소 클래스 샘플 수가 부족합니다: {min_class_count}개")
            # 2클래스로 단순화 (강한 신호만 제거)
            logger.info("2클래스로 단순화하여 재시도합니다...")
            y_simplified = y.copy()
            y_simplified[y_simplified == 2] = 1   # 강한 롱 → 일반 롱
            y_simplified[y_simplified == -2] = -1  # 강한 숏 → 일반 숏
            y = y_simplified
            
            # 다시 클래스 분포 확인
            class_counts = y.value_counts()
            logger.info(f"단순화된 클래스 분포: {dict(class_counts)}")
            
            min_class_count = class_counts.min()
            if min_class_count < 2:
                logger.error(f"단순화 후에도 클래스 불균형: {min_class_count}개")
                return {'error': f'클래스 불균형: 최소 클래스 {min_class_count}개'}
        
        # 훈련/테스트 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # 피처 스케일링
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # 여러 모델 테스트
        models = {
            'RandomForest': RandomForestClassifier(n_estimators=100, random_state=42),
            'GradientBoosting': GradientBoostingClassifier(n_estimators=100, random_state=42),
            'LogisticRegression': LogisticRegression(random_state=42, max_iter=1000),
            'SVM': SVC(random_state=42, probability=True)
        }
        
        best_model = None
        best_score = 0
        best_name = ""
        
        for name, model in models.items():
            cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5)
            avg_score = cv_scores.mean()
            
            logger.info(f"{name} CV Score: {avg_score:.4f}")
            
            if avg_score > best_score:
                best_score = avg_score
                best_model = model
                best_name = name
        
        # 최고 모델 훈련
        best_model.fit(X_train_scaled, y_train)
        
        # 테스트 성능 평가
        y_pred = best_model.predict(X_test_scaled)
        y_pred_proba = best_model.predict_proba(X_test_scaled)[:, 1]
        
        # 피처 중요도
        if hasattr(best_model, 'feature_importances_'):
            self.feature_importance = dict(zip(features, best_model.feature_importances_))
        
        # 모델 저장
        self.ml_model = best_model
        
        result = {
            'model_name': best_name,
            'cv_score': best_score,
            'test_accuracy': (y_pred == y_test).mean(),
            'classification_report': classification_report(y_test, y_pred, output_dict=True),
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
            'feature_importance': self.feature_importance,
            'n_features': len(features),
            'n_samples': len(X)
        }
        
        logger.info(f"모델 훈련 완료: {best_name}, CV Score: {best_score:.4f}")
        return result
    
    def generate_signal(self, df: pd.DataFrame, features: List[str]) -> Dict:
        """거래 신호 생성"""
        if self.ml_model is None:
            return {'action': 'hold', 'confidence': 0}
        
        # 최근 데이터로 예측
        recent_data = df[features].tail(1)
        
        if recent_data.isna().any().any():
            return {'action': 'hold', 'confidence': 0}
        
        # 피처 스케일링
        recent_scaled = self.scaler.transform(recent_data)
        
        # 예측
        prediction = self.ml_model.predict(recent_scaled)[0]
        prediction_proba = self.ml_model.predict_proba(recent_scaled)[0]
        
        # 다중 클래스 분류에서 올바른 신뢰도 계산
        if len(prediction_proba) == 2:  # 2클래스 (0, 1)
            confidence = prediction_proba[1] if prediction == 1 else prediction_proba[0]
        else:  # 5클래스 (-2, -1, 0, 1, 2)
            # 클래스 인덱스 매핑: -2=0, -1=1, 0=2, 1=3, 2=4
            class_mapping = {-2: 0, -1: 1, 0: 2, 1: 3, 2: 4}
            pred_idx = class_mapping.get(prediction, 2)
            confidence = prediction_proba[pred_idx] if pred_idx < len(prediction_proba) else max(prediction_proba)
        
        # 디버깅을 위한 상세 로그
        logger.info(f"ML 예측 상세: prediction={prediction}, confidence={confidence:.3f}, proba={prediction_proba}")
        
        # 이동평균선 신호 확인
        ma_short = df['ma_short'].iloc[-1]
        ma_long = df['ma_long'].iloc[-1]
        current_price = df['close'].iloc[-1]
        
        ma_signal = 0
        if ma_short > 0 and ma_long > 0:
            if current_price > ma_short > ma_long:
                ma_signal = 1
            elif current_price < ma_short < ma_long:
                ma_signal = -1
        
        # 이동평균선 신호 디버깅
        logger.info(f"이동평균선 신호: ma_short={ma_short:.2f}, ma_long={ma_long:.2f}, current_price={current_price:.2f}, ma_signal={ma_signal}")
        
        # 신호 생성 (2클래스 또는 5클래스 모두 지원)
        # 백테스트와 동일한 신뢰도 임계값 사용
        if prediction == 2 and (ma_signal >= 0 or (ma_short == 0 and ma_long == 0)) and confidence > 0.6:
            return {'action': 'buy', 'confidence': confidence, 'signal_strength': 'strong'}
        elif prediction == -2 and (ma_signal <= 0 or (ma_short == 0 and ma_long == 0)) and confidence > 0.6:
            return {'action': 'sell', 'confidence': confidence, 'signal_strength': 'strong'}
        elif prediction == 1 and (ma_signal >= 0 or (ma_short == 0 and ma_long == 0)) and confidence > 0.55:
            return {'action': 'buy', 'confidence': confidence, 'signal_strength': 'normal'}
        elif prediction == -1 and (ma_signal <= 0 or (ma_short == 0 and ma_long == 0)) and confidence > 0.55:
            return {'action': 'sell', 'confidence': confidence, 'signal_strength': 'normal'}
        else:
            return {'action': 'hold', 'confidence': confidence, 'signal_strength': 'none'}

# ========================= 모델 학습 및 관리 =========================
def should_retrain_model(dic):
    """매월 1일인지 확인하여 모델 재학습 필요 여부 판단"""
    today = dt.datetime.now()
    
    # 매월 1일인지 확인
    if today.day != 1:
        return False
    
    # scalping_bot.json에서 마지막 학습 날짜 확인
    try:
        model_info = dic.get('scalping_model_info', {})
        last_train_date_str = model_info.get('last_train_date')
        
        if not last_train_date_str:
            return True
        
        last_train_date = dt.datetime.fromisoformat(last_train_date_str)
        
        # 이번 달 1일보다 이전에 학습했으면 재학습 필요
        current_month_first = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return last_train_date < current_month_first
        
    except Exception as e:
        logger.warning(f"마지막 학습 날짜 확인 실패: {e}")
        return True

def train_scalping_model(binanceX):
    """단타용 모델 학습 (실시간 데이터 사용)"""
    logger.info("=== 단타용 모델 학습 시작 ===")
    
    try:
        # 실시간 데이터 로드 (최근 30일)
        df = load_live_data(binanceX, 'BTC/USDT', days=30)
        
        # AdvancedMAMLBot으로 단타용 모델 학습
        bot = AdvancedMAMLBot(initial_balance=10000, leverage=DEFAULT_LEVERAGE)
        
        # 단타용 파라미터 설정
        bot.params.update(SCALPING_PARAMS)
        bot._scalping_mode = True
        
        # 모델 학습
        train_result = bot.train_ml_model(df)
        
        if 'error' in train_result:
            logger.error(f"모델 학습 실패: {train_result['error']}")
            return False
        
        # 모델 저장
        model_dir = os.path.dirname(__file__)
        model_file = os.path.join(model_dir, "scalping_model.pkl")
        scaler_file = os.path.join(model_dir, "scalping_scaler.pkl")
        model_info_file = os.path.join(model_dir, "scalping_model_info.json")
        
        # 모델과 스케일러 저장
        joblib.dump(bot.ml_model, model_file)
        joblib.dump(bot.scaler, scaler_file)
        
        # 모델 정보 저장
        model_info = {
            'model_name': train_result.get('model_name', 'Unknown'),
            'accuracy': train_result.get('test_accuracy', 0),
            'cv_score': train_result.get('cv_score', 0),
            'n_features': train_result.get('n_features', 0),
            'n_samples': train_result.get('n_samples', 0),
            'train_period': f"최근 60일 (5분봉)",
            'last_update': dt.datetime.now().isoformat(),
            'feature_importance': train_result.get('feature_importance', {})
        }
        
        with open(model_info_file, 'w', encoding='utf-8') as f:
            json.dump(model_info, f, indent=2, ensure_ascii=False)
        
        # scalping_bot.json에 학습 정보 저장 (별도 파일 생성하지 않음)
        # 이 정보는 메인 실행 부분에서 dic에 저장됨
        
        logger.info(f"✅ 단타용 모델 학습 완료: {model_info['model_name']}")
        logger.info(f"   - 정확도: {model_info['accuracy']:.4f}")
        logger.info(f"   - CV Score: {model_info['cv_score']:.4f}")
        logger.info(f"   - 학습 기간: {model_info['train_period']}")
        
        # 텔레그램 알림
        line_alert.SendMessage(f"🤖📊 단타용 모델 학습 완료\n- 모델: {model_info['model_name']}\n- 정확도: {model_info['accuracy']:.4f}\n- 학습 기간: {model_info['train_period']}")
        
        return True
        
    except Exception as e:
        logger.error(f"모델 학습 실패: {e}")
        line_alert.SendMessage(f"🚨[Scalping Bot] 모델 학습 실패: {e}")
        return False

def load_scalping_model():
    """단타용 모델 로드"""
    model_dir = os.path.dirname(__file__)
    model_file = os.path.join(model_dir, "scalping_model.pkl")
    scaler_file = os.path.join(model_dir, "scalping_scaler.pkl")
    model_info_file = os.path.join(model_dir, "scalping_model_info.json")
    
    if not all([os.path.exists(model_file), os.path.exists(scaler_file), os.path.exists(model_info_file)]):
        logger.error("❌ 단타용 모델 파일이 없습니다.")
        return None, None, None
    
    try:
        # scikit-learn 버전 불일치 경고 억제
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
            # 모델과 스케일러 로드
            ml_model = joblib.load(model_file)
            scaler = joblib.load(scaler_file)
        
        # 모델 정보 로드
        with open(model_info_file, 'r', encoding='utf-8') as f:
            model_info = json.load(f)
        
        logger.info(f"✅ 단타용 모델 로드 성공: {model_info.get('model_name', 'Unknown')}")
        logger.info(f"   - 정확도: {model_info.get('accuracy', 'Unknown')}")
        logger.info(f"   - 최종 업데이트: {model_info.get('last_update', 'Unknown')}")
        logger.info(f"   - 학습 기간: {model_info.get('train_period', 'Unknown')}")
        
        return ml_model, scaler, model_info
        
    except Exception as e:
        logger.error(f"❌ 단타용 모델 로드 실패: {e}")
        return None, None, None

# ========================= 메인 실행 코드 =========================
if __name__ == "__main__":
    logger.info("=== Live Scalping ML Trading Bot 시작 ===")
    
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
    info_file_path = os.path.join(os.path.dirname(__file__), "scalping_bot.json")
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
            "scalping_model_info": {"name": None, "last_update": None, "accuracy": None},
            "position_tracking": {
                "current_ratio": BASE_POSITION_RATIO,  # 현재 포지션 비율
                "consecutive_losses": 0,  # 연속 손실 횟수
                "consecutive_wins": 0     # 연속 승리 횟수
            }
        }

    # --- 모델 학습 또는 로드 ---
    ml_model = None
    scaler = None
    model_info = None
    
    if should_retrain_model(dic):
        logger.info("📚 매월 1일 - 단타용 모델 재학습 시작")
        if train_scalping_model(binanceX):
            ml_model, scaler, model_info = load_scalping_model()
            # 학습 완료 후 scalping_bot.json에 정보 저장
            dic['scalping_model_info'] = {
                'name': model_info.get('model_name'),
                'last_update': model_info.get('last_update'),
                'accuracy': model_info.get('accuracy'),
                'train_period': model_info.get('train_period'),
                'last_train_date': model_info.get('last_update')
            }
        else:
            logger.error("모델 학습 실패, 기존 모델 로드 시도")
            ml_model, scaler, model_info = load_scalping_model()
    else:
        logger.info("📖 기존 단타용 모델 로드")
        ml_model, scaler, model_info = load_scalping_model()
    
    if ml_model is None or scaler is None:
        logger.warning("⚠️ 단타용 모델이 없습니다. 새로 학습을 시작합니다.")
        line_alert.SendMessage("⚠️[Scalping Bot] 단타용 모델이 없어 새로 학습을 시작합니다.")
        
        # 모델 학습 시도
        if train_scalping_model(binanceX):
            ml_model, scaler, model_info = load_scalping_model()
            if ml_model is None or scaler is None:
                logger.error("❌ 모델 학습 후에도 로드할 수 없습니다.")
                line_alert.SendMessage("🚨[Scalping Bot] 모델 학습 후에도 로드할 수 없습니다.")
                sys.exit(1)
        else:
            logger.error("❌ 모델 학습에 실패했습니다.")
            line_alert.SendMessage("🚨[Scalping Bot] 모델 학습에 실패했습니다.")
            sys.exit(1)
    
    for Target_Coin_Ticker in ACTIVE_COINS:
        logger.info(f"=== {Target_Coin_Ticker} | 단타용 ML 모델: {model_info.get('name')} ===")
        
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

        # 데이터 수집 (최근 200개 캔들, 5분봉)
        df = myBinance.GetOhlcv(binanceX, Target_Coin_Ticker, '5m', 200)
        coin_price = df['close'].iloc[-1]
        
        logger.info(f"현재 {Target_Coin_Ticker} 가격: {coin_price:.2f} USDT")
        
        # 메모리 사용량 모니터링
        initial_memory = cleanup_memory()
        
        # ATR 계산 (손절가 설정용)
        try:
            import talib
            last_atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14).iloc[-1]
        except:
            last_atr = None
        
        # AdvancedMAMLBot을 사용한 단타 신호 예측
        bot = None
        df_features = None
        features = None
        signal = None
        
        try:
            # 봇 생성 (모델과 스케일러가 이미 로드됨)
            bot = AdvancedMAMLBot(initial_balance=10000, leverage=DEFAULT_LEVERAGE)
            bot.ml_model = ml_model
            bot.scaler = scaler
            bot.params.update(SCALPING_PARAMS)
            bot._scalping_mode = True
            
            # 피처 생성 및 신호 예측
            df_features, features = bot.create_features(df)
            signal = bot.generate_signal(df_features, features)
            
            # 예측 결과를 거래 신호로 변환
            action = signal['action']
            confidence = signal['confidence']
            reason = f"Scalping_ML_{model_info.get('name')}_{action.upper()}"
                
            logger.info(f"단타 ML 예측: {action} (신뢰도: {confidence:.3f})")
                
        except Exception as e:
            log_error(f"단타 ML 예측 실패: {e}", traceback.format_exc())
            action = 'hold'
            reason = "단타 ML 예측 실패"
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
                
                log_trade_action('SL_LONG', Target_Coin_Ticker, 'long', exit_price, close_qty, 'Scalping_ATR_StopLoss', profit, profit_rate)
                profit_emoji = '🟢' if profit > 0 else ('🔴' if profit < 0 else '⚪')
                line_alert.SendMessage(f"{profit_emoji} 롱 포지션 손절(단타+ATR)\n- 코인: {Target_Coin_Ticker}\n- 청산가: {exit_price:.2f}\n- 수량: {close_qty}\n- 수익: {profit:.2f} USDT ({profit_rate:.2f}%)\n- 시작금액: {dic['start_money']:.2f} USDT\n- 현재금액: {dic['my_money']:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")
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
                
                log_trade_action('SL_SHORT', Target_Coin_Ticker, 'short', exit_price, close_qty, 'Scalping_ATR_StopLoss', profit, profit_rate)
                profit_emoji = '🟢' if profit > 0 else ('🔴' if profit < 0 else '⚪')
                line_alert.SendMessage(f"{profit_emoji} 숏 포지션 손절(단타+ATR)\n- 코인: {Target_Coin_Ticker}\n- 청산가: {exit_price:.2f}\n- 수량: {close_qty}\n- 수익: {profit:.2f} USDT ({profit_rate:.2f}%)\n- 시작금액: {dic['start_money']:.2f} USDT\n- 현재금액: {dic['my_money']:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")
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
                        
                        log_trade_action('SELL_SHORT', Target_Coin_Ticker, 'short', exit_price, close_qty, "단타 포지션 전환", profit, profit_rate)
                        
                        profit_emoji = "🟢" if profit > 0 else ("🔴" if profit < 0 else "⚪")
                        line_alert.SendMessage(f"{profit_emoji} 숏 포지션 청산(단타)\n- 코인: {Target_Coin_Ticker}\n- 청산가: {exit_price:.2f}\n- 수량: {close_qty}\n- 수익: {profit:.2f} USDT ({profit_rate:.2f}%)\n- 시작금액: {dic['start_money']:.2f} USDT\n- 현재금액: {dic['my_money']:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")
                        
                        short_data['position'] = 0
                        short_data['entry_price'] = 0
                        short_data['position_size'] = 0
                        short_data['stop_loss_price'] = 0
                except Exception as e:
                    log_error(f"숏 포지션 청산 실패: {e}", traceback.format_exc())
                    
            if long_position == 0:
                logger.info("신규 진입: 롱 포지션 주문 (단타)")
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
                    line_alert.SendMessage(f"⚡📈 롱 포지션 진입(단타)\n- 코인: {Target_Coin_Ticker}\n- 가격: {entry_price:.2f}\n- 수량: {position_size}\n- 모델: {model_info.get('name')}")

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
                        
                        log_trade_action('SELL_LONG', Target_Coin_Ticker, 'long', exit_price, close_qty, "단타 포지션 전환", profit, profit_rate)
                        
                        profit_emoji = "🟢" if profit > 0 else ("🔴" if profit < 0 else "⚪")
                        line_alert.SendMessage(f"{profit_emoji} 롱 포지션 청산(단타)\n- 코인: {Target_Coin_Ticker}\n- 청산가: {exit_price:.2f}\n- 수량: {close_qty}\n- 수익: {profit:.2f} USDT ({profit_rate:.2f}%)\n- 시작금액: {dic['start_money']:.2f} USDT\n- 현재금액: {dic['my_money']:.2f} USDT\n- 총손익률: {total_profit_rate:.2f}%")
                        
                        long_data['position'] = 0
                        long_data['entry_price'] = 0
                        long_data['position_size'] = 0
                        long_data['stop_loss_price'] = 0
                except Exception as e:
                    log_error(f"롱 포지션 청산 실패: {e}", traceback.format_exc())

            if short_position == 0:
                logger.info("신규 진입: 숏 포지션 주문 (단타)")
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
                    line_alert.SendMessage(f"⚡📉 숏 포지션 진입(단타)\n- 코인: {Target_Coin_Ticker}\n- 가격: {entry_price:.2f}\n- 수량: {position_size}\n- 모델: {model_info.get('name')}")

                except Exception as e:
                    log_error(f"숏 포지션 진입 실패: {e}", traceback.format_exc())
        
        # 포지션 정보 파일에 저장
        with open(info_file_path, 'w', encoding='utf-8') as f:
            json.dump(dic, f, indent=4)
        
        # 각 코인 처리 후 메모리 정리
        cleanup_dataframes(df, df_features)
        cleanup_variables(
            bot=bot, df_features=df_features, features=features, signal=signal
        )
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
    
    logger.info(f"=== Live Scalping ML Trading Bot 종료 (최종 메모리: {final_memory:.2f} MB) ===")
