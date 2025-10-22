"""
================================================================================
바이낸스 양방향 무한매수봇 + 머신러닝 (Binance Bidirectional Bot with ML)
================================================================================

📌 개요:
    이 봇은 기존의 양방향 무한매수 전략에 머신러닝 예측 기능을 추가한 
    고도화 버전입니다. 5일선/20일선 기반 이동평균 전략과 21가지 보조지표를 
    활용한 ML 예측을 결합하여 진입/청산 정확도를 향상시킵니다.

🎯 주요 기능:

    1️⃣ 단순 양방향 전략 (백테스트와 동일)
       - 롱(Long) 최대 1개 + 숏(Short) 최대 1개
       - ML 신호로 진입, 익절/손절로 청산
       - 청산 후 다시 진입 가능
    
    2️⃣ 머신러닝 신호 (신규)
       - 21가지 보조지표 활용 (RSI, MACD, 볼린저밴드, ADX 등)
       - 4가지 ML 모델 자동 선택 (RandomForest, GradientBoosting, LR, SVM)
       - 신뢰도 기반 필터링 (55% 이상일 때만 ML 신호 사용)
       - ML이 주도하고 MA로 확인하여 진입 정확도 향상
    
    3️⃣ 자동 재훈련 시스템 (신규)
       - 매일 새벽 4시 자동 재훈련 (설정 변경 가능)
       - 최근 15일치 1시간봉 데이터로 학습
       - 모델 자동 저장/로드로 재시작 시에도 이어서 사용

📊 21가지 보조지표:
    1. 이동평균선 (MA Short, MA Long)
    2. 볼린저밴드 (Bollinger Bands - Upper, Middle, Lower)
    3. RSI (Relative Strength Index) - 과매수/과매도
    4. 스토캐스틱 (Stochastic K, D) - 모멘텀
    5. MACD (Moving Average Convergence Divergence) - 추세 전환
    6. ATR (Average True Range) - 변동성
    7. ADX (Average Directional Index) - 추세 강도
    8. CCI (Commodity Channel Index) - 가격 편차
    9. Williams %R - 과매수/과매도
    10. MFI (Money Flow Index) - 자금 흐름
    11. OBV (On Balance Volume) - 거래량 분석
    12. ROC (Rate of Change) - 가격 변화율
    13. Momentum - 모멘텀
    14. TRIX - 추세
    15. ULTOSC (Ultimate Oscillator) - 다중 시간대 오실레이터
    16. AROON (Up, Down) - 추세 발생 시점
    17. BOP (Balance of Power) - 매수/매도 압력
    18. PPO (Percentage Price Oscillator) - 가격 오실레이터

🤖 ML 동작 방식 (백테스트와 동일):

    [포지션 없을 때]
    1. ML 예측 수행 (1시간봉 데이터 분석)
    2. ML 신뢰도가 55% 이상인지 체크
    3. MA 신호로 보조 확인:
       - ML: 매수 & 신뢰도 > 55% & MA 상승추세(≥0) → ✅ 롱 진입
       - ML: 매도 & 신뢰도 > 55% & MA 하락추세(≤0) → ✅ 숏 진입
       - 조건 불만족 → ❌ 진입 안함
    
    [포지션 있을 때]
    - 익절/손절: 기존 로직 그대로 (MA 기반)
    - 추가 진입: ML 주도 + MA 보조 확인
    - 역방향 진입: ML 주도 + MA 보조 확인

⚙️ 설정 파라미터 (파일 상단에서 조정 가능):

    ML_RETRAIN_INTERVAL_DAYS = 1
        - 재훈련 주기 (일)
        - 권장: 1일 (빠른 시장 대응)
        - 대안: 3일 (안정적), 7일 (가장 안정적)
    
    ML_TRAINING_WINDOW_DAYS = 15
        - 훈련 데이터 기간 (일)
        - 권장: 15일 유지 (충분한 학습 데이터)
        - 너무 짧으면 불안정, 너무 길면 과거 패턴 과다 학습
    
    ML_CONFIDENCE_THRESHOLD = 0.55
        - ML 신호 신뢰도 임계값 (0~1)
        - 0.55: 백테스트 검증값 (권장)
        - 0.60: 보수적 (더 확실한 신호만)
        - 0.50: 공격적 (더 많은 거래)

📁 생성되는 파일:

    1. ml_bot.json
       - 봇 상태 저장 (포지션, 수익, ML 훈련 일자 등)
    
    2. ml_model.pkl
       - 훈련된 ML 모델 (최고 성능 모델 자동 저장)
    
    3. ml_scaler.pkl
       - 데이터 정규화 스케일러
    
    4. logs/ml_bot_YYYYMMDD.log
       - 실행 로그 (거래, ML 예측, 재훈련 등)
       - 하루 단위로 로그 파일 생성

💡 거래 예시 (백테스트와 동일 로직):

    [예시 1 - ML과 MA 모두 일치]
    ML: 매수 예측, 신뢰도 68% ✅
    MA: 5일선 > 20일선 (상승 추세) ✅
    결과: ✅ 롱 진입! (ML 주도, MA 확인)
    
    [예시 2 - ML이 손실을 방지하는 경우]
    ML: 매수 예측, 신뢰도 72% ✅
    MA: 5일선 < 20일선 (하락 추세) ❌
    결과: ❌ 진입 안함! (MA가 반대 신호)
    
    [예시 3 - ML 신뢰도가 낮을 때]
    ML: 매수 예측, 신뢰도 48% ❌ (55% 미만)
    MA: 5일선 > 20일선 (상승 추세) ✅
    결과: ❌ 진입 안함 (ML 신뢰도 부족)

🔄 실행 흐름:

    1. 시작 시 저장된 ML 모델 로드 (없으면 자동 훈련)
    2. 매 실행마다:
       - 잔고 확인
       - 포지션 확인
       - 3% 수익 달성 시 전체 청산 체크
       - MA 계산 (1분봉)
       - ML 예측 (1시간봉)
       - 거래 로직 실행 (MA + ML 결합)
    3. 매일 새벽 4시:
       - 자동 재훈련 실행
       - 텔레그램 알림 발송

📦 의존 라이브러리:

    - ccxt: 바이낸스 거래소 API
    - talib: 보조지표 계산
    - scikit-learn: 머신러닝 모델
    - pandas, numpy: 데이터 처리
    - joblib: 모델 저장/로드
    - psutil: 메모리 관리

⚠️ 주의사항:

    1. 초기 실행 시 자동으로 모델을 훈련합니다 (5~10분 소요)
    2. ML 훈련 시 메모리 사용량이 증가하므로 서버 메모리 확인 필요
    3. 최소 15일치 1시간봉 데이터 필요 (거래소에서 자동 수집)
    4. 레버리지 20배 사용으로 리스크 관리 중요
    5. 실전 투입 전 충분한 페이퍼 트레이딩 권장

🔗 관련 파일:

    - myBinance.py: 바이낸스 거래 공통 함수
    - ende_key.py: 암복호화 키
    - my_key.py: API 키 (암호화됨)
    - telegram_sender.py: 텔레그램 알림

📝 버전 정보:

    - 기반: yang_bot.py (양방향 무한매수봇)
    - ML 추가: 2025-10-02
    - 작성자: AutoTrading System

================================================================================
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
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
import joblib

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

# ========================= ML 설정 =========================
ML_RETRAIN_INTERVAL_DAYS = 1  # 재훈련 주기 (일) - 1일 권장, 3일, 7일 등으로 조정 가능
ML_TRAINING_WINDOW_DAYS = 15  # 훈련 데이터 기간 (일)
ML_CONFIDENCE_THRESHOLD = 0.55  # ML 신호 신뢰도 임계값 (백테스트와 동일)
DRIFT_THRESHOLD = 0.1 # 드리프트 감지 임계값

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

# ========================= ML 예측 클래스 =========================
class MLPredictor:
    """머신러닝 예측 클래스"""
    def __init__(self, params: dict):
        self.params = params
        self.model = None
        self.scaler = StandardScaler()
        self.last_train_date = None
        self.feature_importance = None
        self.baseline_performance = None
        self.drift_threshold = DRIFT_THRESHOLD
        self.model_file = os.path.join(script_dir, "ml_model.pkl")
        self.scaler_file = os.path.join(script_dir, "ml_scaler.pkl")
        
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """21가지 보조지표 계산 (0일 때 비활성화)"""
        df = df.copy()
        
        p = self.params

        # 1. 이동평균선
        df['ma_short'] = talib.SMA(df['close'], timeperiod=p.get('ma_short', 5)) if p.get('ma_short', 5) > 0 else 0
        df['ma_long'] = talib.SMA(df['close'], timeperiod=p.get('ma_long', 20)) if p.get('ma_long', 20) > 0 else 0
        
        # 2. 볼린저밴드
        if p.get('bb_period', 20) > 0 and p.get('bb_std', 2.0) > 0:
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
                df['close'], timeperiod=p.get('bb_period', 20), nbdevup=p.get('bb_std', 2.0), 
                nbdevdn=p.get('bb_std', 2.0), matype=0)
        else:
            df['bb_upper'] = df['bb_middle'] = df['bb_lower'] = 0
        
        # 3. RSI
        df['rsi'] = talib.RSI(df['close'], timeperiod=p.get('rsi_period', 14)) if p.get('rsi_period', 14) > 0 else 50
        
        # 4. 스토캐스틱
        if p.get('stoch_k', 14) > 0:
            df['stoch_k'], df['stoch_d'] = talib.STOCH(df['high'], df['low'], df['close'], 
                                                     fastk_period=p.get('stoch_k', 14), slowk_period=3, 
                                                     slowd_period=p.get('stoch_d', 3))
        else:
            df['stoch_k'] = df['stoch_d'] = 50
            
        # 5. MACD
        if p.get('macd_fast', 12) > 0 and p.get('macd_slow', 26) > 0 and p.get('macd_signal', 9) > 0:
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(
                df['close'], fastperiod=p.get('macd_fast', 12), 
                slowperiod=p.get('macd_slow', 26), signalperiod=p.get('macd_signal', 9))
        else:
            df['macd'] = df['macd_signal'] = df['macd_hist'] = 0

        # 6. ATR, 7. ADX, 8. CCI, ... (나머지 지표 추가)
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=p.get('atr_period', 14))
        df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=p.get('adx_period', 14))
        df['cci'] = talib.CCI(df['high'], df['low'], df['close'], timeperiod=p.get('cci_period', 20))
        df['williams_r'] = talib.WILLR(df['high'], df['low'], df['close'], timeperiod=p.get('williams_period', 14))
        df['mfi'] = talib.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=p.get('mfi_period', 14))
        df['obv'] = talib.OBV(df['close'], df['volume'])
        df['obv_ma'] = talib.SMA(df['obv'], timeperiod=p.get('obv_period', 10))
        df['roc'] = talib.ROC(df['close'], timeperiod=p.get('roc_period', 10))
        df['momentum'] = talib.MOM(df['close'], timeperiod=p.get('momentum_period', 10))
        df['kama'] = talib.KAMA(df['close'], timeperiod=p.get('kama_period', 30))
        df['trix'] = talib.TRIX(df['close'], timeperiod=p.get('trix_period', 14))
        df['ultosc'] = talib.ULTOSC(df['high'], df['low'], df['close'], 
                                   timeperiod1=p.get('ultosc_period1', 7), 
                                   timeperiod2=p.get('ultosc_period2', 14), 
                                   timeperiod3=p.get('ultosc_period3', 28))
        df['aroon_up'], df['aroon_down'] = talib.AROON(df['high'], df['low'], timeperiod=p.get('aroon_period', 14))
        df['bop'] = talib.BOP(df['open'], df['high'], df['low'], df['close'])
        df['dx'] = talib.DX(df['high'], df['low'], df['close'], timeperiod=p.get('dx_period', 14))
        df['minus_di'] = talib.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=p.get('minus_di_period', 14))
        df['plus_di'] = talib.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=p.get('plus_di_period', 14))
        df['ppo'] = talib.PPO(df['close'], fastperiod=p.get('ppo_fast', 12), slowperiod=p.get('ppo_slow', 26))
        
        return df

    def create_features(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
        """머신러닝용 고급 피처 생성"""
        df = self.calculate_technical_indicators(df)
        
        features = [
            'ma_short', 'ma_long', 'bb_upper', 'bb_middle', 'bb_lower',
            'rsi', 'stoch_k', 'stoch_d', 'macd', 'macd_signal', 'macd_hist',
            'atr', 'adx', 'cci', 'williams_r', 'mfi', 'obv', 'obv_ma',
            'roc', 'momentum', 'kama', 'trix', 'ultosc', 'aroon_up', 'aroon_down',
            'bop', 'dx', 'minus_di', 'plus_di', 'ppo'
        ]
        
        # 파생 피처 생성
        df['ma_cross'] = (df['ma_short'] > df['ma_long']).astype(int)
        bb_range = df['bb_upper'] - df['bb_lower']
        df['bb_position'] = np.where(bb_range != 0, (df['close'] - df['bb_lower']) / bb_range, 0.5)
        df['rsi_oversold'] = (df['rsi'] < 30).astype(int)
        df['rsi_overbought'] = (df['rsi'] > 70).astype(int)
        df['stoch_oversold'] = (df['stoch_k'] < 20).astype(int)
        df['stoch_overbought'] = (df['stoch_k'] > 80).astype(int)
        df['macd_bullish'] = (df['macd'] > df['macd_signal']).astype(int)
        df['macd_bearish'] = (df['macd'] < df['macd_signal']).astype(int)
        
        df['price_change_1'] = df['close'].pct_change(1)
        df['price_change_5'] = df['close'].pct_change(5)
        df['volume_change_1'] = df['volume'].pct_change(1)
        df['volatility_5'] = df['close'].rolling(5).std()
        
        features.extend([
            'ma_cross', 'bb_position', 'rsi_oversold', 'rsi_overbought',
            'stoch_oversold', 'stoch_overbought', 'macd_bullish', 'macd_bearish',
            'price_change_1', 'price_change_5', 'volume_change_1', 'volatility_5'
        ])
        
        # NaN/Inf 값 처리
        for feature in features:
            if feature in df.columns:
                df[feature] = df[feature].replace([np.inf, -np.inf], np.nan)
                df[feature] = df[feature].fillna(0)
        
        return df, features
    
    def create_labels(self, df: pd.DataFrame, lookforward: int = 5) -> pd.Series:
        """미래 수익률 기반 라벨 생성 (개선된 버전)"""
        future_returns = df['close'].shift(-lookforward) / df['close'] - 1
        
        up_threshold = 0.005
        down_threshold = -0.005
        
        labels = pd.Series(0, index=df.index)
        labels[future_returns > up_threshold] = 1
        labels[future_returns < down_threshold] = -1
        
        return labels
    
    def train_model(self, df: pd.DataFrame) -> bool:
        """모델 훈련"""
        try:
            logger.info("ML 모델 훈련 시작...")
            
            df_features, features = self.create_features(df)
            labels = self.create_labels(df_features)
            
            valid_idx = ~(df_features[features].isna().any(axis=1) | labels.isna())
            X = df_features.loc[valid_idx, features]
            y = labels.loc[valid_idx]
            
            if len(X) < 100:
                logger.warning("훈련 데이터가 부족합니다.")
                return False
            
            X_scaled = self.scaler.fit_transform(X)
            
            models = {
                'RandomForest': RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1),
                'GradientBoosting': GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42),
                'LogisticRegression': LogisticRegression(max_iter=1000, random_state=42, n_jobs=-1),
                'SVM': SVC(kernel='rbf', probability=True, random_state=42)
            }
            
            best_model = None
            best_score = -1
            best_model_name = ""
            
            for name, model in models.items():
                try:
                    scores = cross_val_score(model, X_scaled, y, cv=3, scoring='accuracy', n_jobs=-1)
                    score = scores.mean()
                    logger.info(f"{name} CV Score: {score:.4f}")
                    
                    if score > best_score:
                        best_score = score
                        best_model = model
                        best_model_name = name
                except Exception as e:
                    logger.error(f"{name} 훈련 오류: {e}")
            
            if best_model is None:
                logger.error("모든 모델 훈련 실패")
                return False
            
            best_model.fit(X_scaled, y)
            self.model = best_model
            self.last_train_date = dt.datetime.now()
            
            # 피처 중요도 및 베이스라인 저장
            if hasattr(best_model, 'feature_importances_'):
                self.feature_importance = dict(zip(features, best_model.feature_importances_))
            
            # 베이스라인 성능 설정
            y_pred_proba = best_model.predict_proba(X_scaled)[:, 1]
            self.baseline_performance = {
                'mean_prediction': np.mean(y_pred_proba),
                'std_prediction': np.std(y_pred_proba)
            }
            logger.info(f"성능 베이스라인 설정: {self.baseline_performance}")

            logger.info(f"✅ 최고 모델: {best_model_name}, 정확도: {best_score:.4f}")
            
            joblib.dump(self.model, self.model_file)
            joblib.dump(self.scaler, self.scaler_file)
            logger.info(f"모델 저장 완료: {self.model_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"모델 훈련 오류: {e}")
            return False
    
    def load_model(self) -> bool:
        """저장된 모델 로드"""
        try:
            if os.path.exists(self.model_file) and os.path.exists(self.scaler_file):
                # scikit-learn 버전 불일치 경고 억제
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
                    warnings.filterwarnings("ignore", message=".*InconsistentVersionWarning.*")
                    self.model = joblib.load(self.model_file)
                    self.scaler = joblib.load(self.scaler_file)
                logger.info("✅ 저장된 모델 로드 완료")
                return True
            return False
        except Exception as e:
            logger.error(f"모델 로드 오류: {e}")
            return False
    
    def predict(self, df: pd.DataFrame) -> dict:
        """예측 수행"""
        try:
            if self.model is None:
                return {'action': 'hold', 'confidence': 0.0}
            
            df_features, features = self.create_features(df)
            
            if df_features.empty:
                return {'action': 'hold', 'confidence': 0.0}
            
            X_last = df_features.iloc[-1:][features]
            
            if X_last.isna().any().any():
                logger.warning("예측을 위한 최신 데이터에 NaN 값이 포함되어 있습니다.")
                return {'action': 'hold', 'confidence': 0.0}

            X_scaled = self.scaler.transform(X_last)
            
            prediction = self.model.predict(X_scaled)[0]
            probabilities = self.model.predict_proba(X_scaled)[0]
            confidence = probabilities.max()
            
            action = 'hold'
            if prediction == 1:
                action = 'buy'
            elif prediction == -1:
                action = 'sell'
            
            return {'action': action, 'confidence': confidence}
            
        except Exception as e:
            logger.error(f"예측 오류: {e}")
            return {'action': 'hold', 'confidence': 0.0}

    def evaluate_parameters(self, df: pd.DataFrame) -> float:
        """파라미터 평가 (간단한 백테스트)"""
        # 간단한 백테스트로 파라미터 평가
        df_features = self.calculate_technical_indicators(df.copy())
        
        # 이동평균선 크로스 신호 (0일 때는 비활성화)
        if self.params['ma_short'] > 0 and self.params['ma_long'] > 0:
            df_features['ma_cross_up'] = (
                (df_features['ma_short'] > df_features['ma_long']) & 
                (df_features['ma_short'].shift(1) <= df_features['ma_long'].shift(1))
            )
            df_features['ma_cross_down'] = (
                (df_features['ma_short'] < df_features['ma_long']) & 
                (df_features['ma_short'].shift(1) >= df_features['ma_long'].shift(1))
            )
        else:
            # 이동평균선이 비활성화된 경우
            df_features['ma_cross_up'] = False
            df_features['ma_cross_down'] = False
        
        # 간단한 수익률 계산
        returns = []
        position = 0  # 0: 없음, 1: 롱, -1: 숏
        
        for i in range(1, len(df_features)):
            if df_features['ma_cross_up'].iloc[i] and position <= 0:
                position = 1
            elif df_features['ma_cross_down'].iloc[i] and position >= 0:
                if position == 1:
                    # 롱 포지션 청산
                    ret = (df_features['close'].iloc[i] / df_features['close'].iloc[i-1]) - 1
                    returns.append(ret)
                position = -1
            elif position == -1:
                # 숏 포지션 청산
                ret = (df_features['close'].iloc[i-1] / df_features['close'].iloc[i]) - 1
                returns.append(ret)
                position = 0
        
        if not returns:
            return 0
        
        # 샤프 비율 계산
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        sharpe_ratio = mean_return / std_return if std_return > 0 else 0
        
        # 승률 계산
        winning_trades = sum(1 for r in returns if r > 0)
        win_rate = winning_trades / len(returns) if returns else 0
        
        # 복합 점수
        win_rate_bonus = (win_rate - 0.5) * 2 if win_rate > 0.5 else 0
        composite_score = sharpe_ratio + win_rate_bonus
        
        return composite_score

    def auto_tune_parameters(self, df: pd.DataFrame, n_trials: int = 30) -> dict:
        """파라미터 오토튜닝"""
        logger.info(f"파라미터 오토튜닝 시작... (n_trials={n_trials})")
        
        param_ranges = {
            'ma_short': [0, 3, 5, 7, 10, 12],
            'ma_long': [0, 15, 20, 25, 30, 50],
            'stop_loss_pct': [0.01, 0.015, 0.02],
            'take_profit_pct': [0.02, 0.025, 0.03],
            'trailing_stop_pct': [0.01, 0.015, 0.02],
            'trailing_stop_activation_pct': [0.005, 0.01]
        }
        
        best_params = self.params.copy()
        best_score = float('-inf')
        
        np.random.seed(42)
        
        for trial in range(n_trials):
            test_params = self.params.copy()
            for param, values in param_ranges.items():
                test_params[param] = np.random.choice(values).item()
            
            old_params = self.params.copy()
            self.params = test_params
            
            try:
                score = self.evaluate_parameters(df)
                if score > best_score:
                    best_score = score
                    best_params = test_params.copy()
            except Exception as e:
                logger.warning(f"Trial {trial+1} failed: {e}")
            
            self.params = old_params
        
        logger.info(f"파라미터 튜닝 완료. 최고 점수: {best_score:.4f}")
        return {
            'best_params': best_params,
            'best_score': best_score
        }

    def detect_drift(self, df: pd.DataFrame) -> dict:
        """드리프트 감지"""
        if not self.model or not self.baseline_performance:
            return {'drift_detected': False, 'reason': '모델 또는 베이스라인 없음'}
        
        try:
            df_features, features = self.create_features(df)
            recent_data = df_features[features].tail(100)
            
            if len(recent_data) < 100:
                return {'drift_detected': False, 'reason': '데이터 부족'}
            
            recent_scaled = self.scaler.transform(recent_data)
            predictions = self.model.predict_proba(recent_scaled)[:, 1]
            
            mean_pred = np.mean(predictions)
            std_pred = np.std(predictions)
            
            baseline_mean = self.baseline_performance.get('mean_prediction', 0.5)
            baseline_std = self.baseline_performance.get('std_prediction', 0.1)
            
            mean_drift = abs(mean_pred - baseline_mean) / baseline_std if baseline_std > 0 else 0
            std_drift = abs(std_pred - baseline_std) / baseline_std if baseline_std > 0 else 0
            
            drift_detected = mean_drift > self.drift_threshold or std_drift > self.drift_threshold
            
            return {
                'drift_detected': drift_detected,
                'mean_drift': mean_drift,
                'std_drift': std_drift
            }
        except Exception as e:
            logger.error(f"드리프트 감지 오류: {e}")
            return {'drift_detected': False, 'reason': f'오류: {e}'}

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
logger.info("ML Bot - 바이낸스 양방향 무한매수봇 + 머신러닝 (시작)")
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
info_file_path = os.path.join(os.path.dirname(__file__), "ml_bot.json")

#잔고 데이타 가져오기 
balance = binanceX.fetch_balance(params={"type": "future"})
time.sleep(0.1)

try:
    with open(info_file_path, 'r') as json_file:
        dic = json.load(json_file)
    
    # 파라미터 호환성 체크
    if "params" not in dic:
        dic["params"] = {
            'ma_short': 5, 'ma_long': 20, 'stop_loss_pct': 0.01, 'take_profit_pct': 0.03,
            'trailing_stop_pct': 0.02, 'trailing_stop_activation_pct': 0.01,
            'bb_period': 20, 'bb_std': 2.0, 'rsi_period': 14, 'stoch_k': 14, 'stoch_d': 3,
            'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9, 'atr_period': 14, 'adx_period': 14,
            'cci_period': 20, 'williams_period': 14, 'mfi_period': 14, 'obv_period': 10, 'roc_period': 10,
            'momentum_period': 10, 'kama_period': 30, 'trix_period': 14, 'ultosc_period1': 7,
            'ultosc_period2': 14, 'ultosc_period3': 28, 'aroon_period': 14, 'bop_period': 14,
            'dx_period': 14, 'minus_di_period': 14, 'plus_di_period': 14, 'ppo_fast': 12, 'ppo_slow': 26
        }
    if "baseline_performance" not in dic:
        dic["baseline_performance"] = None
        
except Exception as e:
    logger.info("Exception by First")
    dic["yesterday"] = 0
    dic["today"] = 0
    dic["start_money"] = float(balance['USDT']['total'])
    dic["my_money"] = float(balance['USDT']['total'])
    dic["long_position"] = {
        "entry_price": 0,
        "amount": 0,
        "highest_price": 0,
        "trailing_stop_activated": False
    }
    dic["short_position"] = {
        "entry_price": 0,
        "amount": 0,
        "lowest_price": 0,
        "trailing_stop_activated": False
    }
    dic["long_position_multiplier"] = 1.0
    dic["short_position_multiplier"] = 1.0
    dic["last_ml_train_date"] = None
    dic["params"] = {
        'ma_short': 5, 'ma_long': 20, 'stop_loss_pct': 0.01, 'take_profit_pct': 0.03,
        'trailing_stop_pct': 0.02, 'trailing_stop_activation_pct': 0.01,
        'bb_period': 20, 'bb_std': 2.0, 'rsi_period': 14, 'stoch_k': 14, 'stoch_d': 3,
        'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9, 'atr_period': 14, 'adx_period': 14,
        'cci_period': 20, 'williams_period': 14, 'mfi_period': 14, 'obv_period': 10, 'roc_period': 10,
        'momentum_period': 10, 'kama_period': 30, 'trix_period': 14, 'ultosc_period1': 7,
        'ultosc_period2': 14, 'ultosc_period3': 28, 'aroon_period': 14, 'bop_period': 14,
        'dx_period': 14, 'minus_di_period': 14, 'plus_di_period': 14, 'ppo_fast': 12, 'ppo_slow': 26
    }
    dic["baseline_performance"] = None
    
    with open(info_file_path, 'w') as outfile:
        json.dump(dic, outfile, indent=4, ensure_ascii=False)

# ML Predictor 초기화 (dic 로드 이후)
ml_predictor = MLPredictor(params=dic.get("params"))

# ML 관련 정보 로드
last_ml_train_date_str = dic.get("last_ml_train_date", None)
if last_ml_train_date_str:
    ml_predictor.last_train_date = dt.datetime.fromisoformat(last_ml_train_date_str)
if dic.get("baseline_performance"):
    ml_predictor.baseline_performance = dic.get("baseline_performance")

logger.info(f"balance['USDT'] : {balance['USDT']}")

logger.info(f"포지션 정보는 바이낸스 API에서 직접 가져옵니다")

# ML 모델 로드 또는 훈련
model_loaded = ml_predictor.load_model()

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
    
    # ========================= ML 재훈련 체크 (새벽 4시 이후 날짜 확인) =========================
    needs_retrain = False
    
    # 모델이 없거나 마지막 훈련 날짜가 없으면 훈련 필요
    if not ml_predictor.load_model() or ml_predictor.last_train_date is None:
        needs_retrain = True
        logger.info("🔄 초기 ML 모델 훈련 필요")
    # 재훈련 주기 체크 (4시 이후에 날짜 확인)
    elif today.hour >= 4:
        days_since_train = (today.date() - ml_predictor.last_train_date.date()).days
        if days_since_train >= ML_RETRAIN_INTERVAL_DAYS:
            needs_retrain = True
            logger.info(f"🔄 ML 모델 재훈련 필요 (마지막 훈련: {days_since_train}일 전, 현재: {today.strftime('%Y-%m-%d %H:%M')})")
    
    # 재훈련 실행
    if needs_retrain:
        try:
            logger.info(f"📊 ML 훈련 데이터 수집 중... (최근 {ML_TRAINING_WINDOW_DAYS}일)")
            
            # 1시간봉 데이터 가져오기
            training_df = myBinance.GetOhlcv(binanceX, Target_Coin_Ticker, '1h')
            
            # 최근 N일치만 사용
            hours_needed = ML_TRAINING_WINDOW_DAYS * 24
            if len(training_df) > hours_needed:
                training_df = training_df.tail(hours_needed)
            
            logger.info(f"📊 훈련 데이터: {len(training_df)}개 캔들")
            
            # 드리프트 감지 (재훈련 전)
            if ml_predictor.model:
                logger.info("🔍 드리프트 감지 시작...")
                drift_result = ml_predictor.detect_drift(training_df.copy())
                if drift_result.get('drift_detected'):
                    msg = f"🚨 ML 모델 드리프트 감지됨!\n(평균: {drift_result['mean_drift']:.2f}, 표준편차: {drift_result['std_drift']:.2f})\n재훈련을 즉시 실행합니다."
                    logger.info(msg)
                    telegram_sender.SendMessage(msg)
                else:
                    logger.info("✅ 드리프트 감지되지 않음.")

            # 파라미터 오토튜닝 실행
            logger.info("⚙️ 파라미터 오토튜닝 시작...")
            tuning_result = ml_predictor.auto_tune_parameters(training_df.copy())
            if tuning_result and tuning_result.get('best_params'):
                dic['params'] = tuning_result['best_params']
                ml_predictor.params = tuning_result['best_params'] # Predictor의 파라미터도 업데이트
                logger.info(f"⚙️ 오토튜닝 완료. 최적 파라미터 적용: {dic['params']}")
                #telegram_sender.SendMessage(f"⚙️ 파라미터 오토튜닝 완료\n점수: {tuning_result['best_score']:.4f}")
            else:
                logger.warning("⚠️ 오토튜닝 실패. 기존 파라미터 유지.")
                telegram_sender.SendMessage(f"⚠️ 오토튜닝 실패. 기존 파라미터 유지.")

            # 훈련 실행
            if ml_predictor.train_model(training_df):
                dic["last_ml_train_date"] = dt.datetime.now().isoformat()
                dic["feature_importance"] = ml_predictor.feature_importance
                dic["baseline_performance"] = ml_predictor.baseline_performance
                logger.info("✅ ML 모델 훈련 완료")
                #telegram_sender.SendMessage(f"🤖 ML 모델 재훈련 완료\n📅 {today.strftime('%Y-%m-%d %H:%M')}\n📊 데이터: {len(training_df)}개 캔들")
            else:
                logger.warning("⚠️ ML 모델 훈련 실패")
                telegram_sender.SendMessage(f"⚠️ ML 모델 훈련 실패")
            
            # 메모리 정리
            cleanup_dataframes(training_df)
            cleanup_memory()
            
        except Exception as e:
            logger.error(f"ML 훈련 오류: {e}")

    #변수 셋팅
    leverage = 20
    amt_s = 0
    amt_l = 0
    isolated = True
    
    # 백테스트와 동일한 청산 파라미터 (json에서 로드)
    params = dic.get('params', {})
    stop_loss_pct = params.get('stop_loss_pct', 0.01)
    take_profit_pct = params.get('take_profit_pct', 0.03)
    trailing_stop_pct = params.get('trailing_stop_pct', 0.02)
    trailing_stop_activation_pct = params.get('trailing_stop_activation_pct', 0.01)
    
    charge = 0.001  # 수수료율 (Maker + Taker)
    investment_ratio = 1.0  # 투자 비율
    divide = 100  # 분할 수 (1%)
    
    # 포지션 사이즈 배수 (백테스트와 동일)
    base_position_multiplier = 1.0    # 기본 1배 (1%)
    increased_position_multiplier = 2.0  # 손실 시 2배 (2%)
    
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
    
    # 캔들 정보 가져오기 (1분봉)
    df = myBinance.GetOhlcv(binanceX, Target_Coin_Ticker, '1m')

    # 이동평균선 계산
    params = dic.get('params', {})
    ma_short_period = params.get('ma_short', 5)
    ma_long_period = params.get('ma_long', 20)

    ma_short_value = myBinance.GetMA(df, ma_short_period, -2) if ma_short_period > 0 else 0
    ma_long_value = myBinance.GetMA(df, ma_long_period, -2) if ma_long_period > 0 else 0

    # ========================= ML 예측 =========================
    ml_signal = {'action': 'hold', 'confidence': 0.0}
    if ml_predictor.model is not None:
        try:
            # 1시간봉 데이터로 ML 예측
            df_1h = myBinance.GetOhlcv(binanceX, Target_Coin_Ticker, '1h')
            ml_signal = ml_predictor.predict(df_1h)
            logger.info(f"🤖 ML 신호: {ml_signal['action']} (신뢰도: {ml_signal['confidence']:.2%})")
            cleanup_dataframes(df_1h)
        except Exception as e:
            logger.error(f"ML 예측 오류: {e}")
    
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
        msg += "\n         ML Bot (양방향 + 머신러닝)"
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
        if ml_predictor.last_train_date:
            days_since = (today - ml_predictor.last_train_date).days
            msg += f"\n🤖 ML 모델: {days_since}일 전 훈련"
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

    # ========================= 거래 로직 (백테스트와 완전 동일) =========================
    # 단순 양방향 전략: 롱 1개 + 숏 1개 동시 보유 가능
    
    # MA 신호 계산 (백테스트와 완전 동일)
    ma_signal = 0
    if ma_short_period > 0 and ma_long_period > 0:
        if coin_price > ma_short_value > ma_long_value:
            ma_signal = 1
        elif coin_price < ma_short_value < ma_long_value:
            ma_signal = -1
    
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
            "lowest_price": 0,
            "trailing_stop_activated": False
        }
        
        # 포지션 사이즈 배수 조정 (손실로 간주)
        dic["short_position_multiplier"] = increased_position_multiplier
        
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
            "highest_price": 0,
            "trailing_stop_activated": False
        }
        
        # 포지션 사이즈 배수 조정 (손실로 간주)
        dic["long_position_multiplier"] = increased_position_multiplier
        
        pnl_display = f"({pnl_pct*100:.2f}%)" if coin_price > 0 else "(추정 1%)"
        msg = f"⚠️ 롱 포지션 소실 감지 (수동 청산 추정) | 진입가: {old_entry_price:.2f}, 현재가: {coin_price:.2f}, 수량: {old_amount:.3f}, 손실: {estimated_loss:.2f}$ {pnl_display}"
        telegram_sender.SendMessage(msg)
        logger.warning(msg)
        
        # 즉시 JSON 저장
        with open(info_file_path, 'w') as outfile:
            json.dump(dic, outfile, indent=4, ensure_ascii=False)
    
    # ==================== 진입 로직 (백테스트와 동일) ====================
    # 파라미터 가져오기
    ma_short = dic.get("params", {}).get("ma_short", 5)
    ma_long = dic.get("params", {}).get("ma_long", 20)
    
    # 포지션 사이즈 배수 가져오기
    short_multiplier = dic.get("short_position_multiplier", 1.0)
    long_multiplier = dic.get("long_position_multiplier", 1.0)
    
    # 숏 진입: ML 매도 신호 + MA 확인 + 숏 포지션 없을 때
    if not has_short:
        should_short = (ml_signal['action'] == 'sell' and 
                       (ma_signal <= 0 or (ma_short == 0 and ma_long == 0)) and 
                       ml_signal['confidence'] > ML_CONFIDENCE_THRESHOLD)
        
        if should_short:
            # 배수 적용
            short_amount = round(first_amount * short_multiplier, 3)
            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', short_amount, None, {'positionSide': 'SHORT'})
            entry_price = float(data['average'])
            
            # 트레일링 스탑 정보 초기화
            dic["short_position"] = {
                "entry_price": entry_price,
                "amount": short_amount,
                "lowest_price": entry_price,
                "trailing_stop_activated": False
            }
            
            msg = f"🔻 숏 진입 | 가격: {entry_price:.2f}, 수량: {short_amount:.3f} (x{short_multiplier}) (ML: {ml_signal['confidence']:.1%}, MA: {ma_signal})"
            telegram_sender.SendMessage(msg)
            logger.info(msg)
    
    # 롱 진입: ML 매수 신호 + MA 확인 + 롱 포지션 없을 때
    if not has_long:
        should_long = (ml_signal['action'] == 'buy' and 
                      (ma_signal >= 0 or (ma_short == 0 and ma_long == 0)) and 
                      ml_signal['confidence'] > ML_CONFIDENCE_THRESHOLD)
        
        if should_long:
            # 배수 적용
            long_amount = round(first_amount * long_multiplier, 3)
            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', long_amount, None, {'positionSide': 'LONG'})
            entry_price = float(data['average'])
            
            # 트레일링 스탑 정보 초기화
            dic["long_position"] = {
                "entry_price": entry_price,
                "amount": long_amount,
                "highest_price": entry_price,
                "trailing_stop_activated": False
            }
            
            msg = f"🔺 롱 진입 | 가격: {entry_price:.2f}, 수량: {long_amount:.3f} (x{long_multiplier}) (ML: {ml_signal['confidence']:.1%}, MA: {ma_signal})"
            telegram_sender.SendMessage(msg)
            logger.info(msg)
    
    # ==================== 청산 로직 (백테스트와 완전 동일) ====================
    
    # 숏 포지션 체크 및 청산
    if has_short and entryPrice_s > 0:
        pnl_pct = (entryPrice_s - coin_price) / entryPrice_s
        logger.info(f"🔍 숏 PnL 체크: 진입가 {entryPrice_s:.2f}, 현재가 {coin_price:.2f}, 수익률 {pnl_pct*100:.2f}%")
        
        # 트레일링 스탑 업데이트
        short_pos = dic.get("short_position", {})
        if short_pos:
            lowest_price = short_pos.get("lowest_price", entryPrice_s)
            trailing_activated = short_pos.get("trailing_stop_activated", False)
            
            # 최저가 업데이트 (숏은 가격이 낮을수록 좋음)
            if coin_price < lowest_price:
                dic["short_position"]["lowest_price"] = coin_price
                lowest_price = coin_price
                logger.info(f"숏 최저가 업데이트: {coin_price:.2f} (이전: {short_pos.get('lowest_price', entryPrice_s):.2f})")
                
                # 즉시 JSON 저장
                with open(info_file_path, 'w') as outfile:
                    json.dump(dic, outfile, indent=4, ensure_ascii=False)
            
            # 트레일링 스탑 활성화 체크 (0.5% 수익)
            if pnl_pct >= trailing_stop_activation_pct and not trailing_activated:
                dic["short_position"]["trailing_stop_activated"] = True
                trailing_activated = True
                logger.info(f"🔒 숏 트레일링 스탑 활성화! (수익률: {pnl_pct*100:.2f}%)")
                
                # 즉시 JSON 저장
                with open(info_file_path, 'w') as outfile:
                    json.dump(dic, outfile, indent=4, ensure_ascii=False)
            elif pnl_pct >= trailing_stop_activation_pct:
                logger.info(f"숏 트레일링 스탑 이미 활성화됨 (수익률: {pnl_pct*100:.2f}%)")
            else:
                logger.info(f"숏 트레일링 스탑 대기 중 (수익률: {pnl_pct*100:.2f}%, 필요: {trailing_stop_activation_pct*100:.1f}%)")
            
            # 청산 조건 체크
            close_reason = None
            close_price = None
            
            # 1. 스탑로스: -1% 손실
            if pnl_pct <= -stop_loss_pct:
                close_reason = "stop_loss"
            # 2. 익절: +3% 수익
            elif pnl_pct >= take_profit_pct:
                close_reason = "take_profit"
            # 3. 트레일링 스탑: 저점 대비 2% 상승
            elif trailing_activated and lowest_price > 0:
                trailing_stop_price = lowest_price * (1 + trailing_stop_pct)
                if coin_price >= trailing_stop_price:
                    close_reason = "trailing_stop"
            
            # 청산 실행
            if close_reason:
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', round(abs(amt_s), 3), None, {'positionSide': 'SHORT'})
                close_price = float(data['average'])
                profit = (entryPrice_s - close_price) * abs(amt_s) - (close_price * abs(amt_s) * charge * 2)
                
                dic["today"] += profit
                dic["short_position"] = {
                    "entry_price": 0,
                    "amount": 0,
                    "lowest_price": 0,
                    "trailing_stop_activated": False
                }
                
                # 포지션 사이즈 배수 조정 (백테스트와 동일)
                if profit > 0:
                    # 승리 → 기본 배수로 복원
                    dic["short_position_multiplier"] = base_position_multiplier
                    logger.info(f"숏 승리! 배수 복원: x{base_position_multiplier}")
                else:
                    # 손실 → 배수 증가
                    dic["short_position_multiplier"] = increased_position_multiplier
                    logger.info(f"숏 손실! 배수 증가: x{increased_position_multiplier}")
                
                msg = f"✅ 숏 청산 ({close_reason}) | 진입: {entryPrice_s:.2f} → 청산: {close_price:.2f} | 수익: {profit:.2f}$ ({pnl_pct*100:.2f}%)"
                telegram_sender.SendMessage(msg)
                logger.info(msg)
    
    # 롱 포지션 체크 및 청산
    if has_long and entryPrice_l > 0:
        pnl_pct = (coin_price - entryPrice_l) / entryPrice_l
        logger.info(f"🔍 롱 PnL 체크: 진입가 {entryPrice_l:.2f}, 현재가 {coin_price:.2f}, 수익률 {pnl_pct*100:.2f}%")
        
        # 트레일링 스탑 업데이트
        long_pos = dic.get("long_position", {})
        if long_pos:
            highest_price = long_pos.get("highest_price", entryPrice_l)
            trailing_activated = long_pos.get("trailing_stop_activated", False)
            
            # 최고가 업데이트 (롱은 가격이 높을수록 좋음)
            if coin_price > highest_price:
                dic["long_position"]["highest_price"] = coin_price
                highest_price = coin_price
                logger.info(f"롱 최고가 업데이트: {coin_price:.2f} (이전: {long_pos.get('highest_price', entryPrice_l):.2f})")
                
                # 즉시 JSON 저장
                with open(info_file_path, 'w') as outfile:
                    json.dump(dic, outfile, indent=4, ensure_ascii=False)
            
            # 트레일링 스탑 활성화 체크 (0.5% 수익)
            if pnl_pct >= trailing_stop_activation_pct and not trailing_activated:
                dic["long_position"]["trailing_stop_activated"] = True
                trailing_activated = True
                logger.info(f"🔒 롱 트레일링 스탑 활성화! (수익률: {pnl_pct*100:.2f}%)")
                
                # 즉시 JSON 저장
                with open(info_file_path, 'w') as outfile:
                    json.dump(dic, outfile, indent=4, ensure_ascii=False)
            elif pnl_pct >= trailing_stop_activation_pct:
                logger.info(f"롱 트레일링 스탑 이미 활성화됨 (수익률: {pnl_pct*100:.2f}%)")
            else:
                logger.info(f"롱 트레일링 스탑 대기 중 (수익률: {pnl_pct*100:.2f}%, 필요: {trailing_stop_activation_pct*100:.1f}%)")
            
            # 청산 조건 체크
            close_reason = None
            close_price = None
            
            # 1. 스탑로스: -1% 손실
            if pnl_pct <= -stop_loss_pct:
                close_reason = "stop_loss"
            # 2. 익절: +3% 수익
            elif pnl_pct >= take_profit_pct:
                close_reason = "take_profit"
            # 3. 트레일링 스탑: 고점 대비 2% 하락
            elif trailing_activated and highest_price > 0:
                trailing_stop_price = highest_price * (1 - trailing_stop_pct)
                if coin_price <= trailing_stop_price:
                    close_reason = "trailing_stop"
            
            # 청산 실행
            if close_reason:
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', round(abs(amt_l), 3), None, {'positionSide': 'LONG'})
                close_price = float(data['average'])
                profit = (close_price - entryPrice_l) * abs(amt_l) - (close_price * abs(amt_l) * charge * 2)
                
                dic["today"] += profit
                dic["long_position"] = {
                    "entry_price": 0,
                    "amount": 0,
                    "highest_price": 0,
                    "trailing_stop_activated": False
                }
                
                # 포지션 사이즈 배수 조정 (백테스트와 동일)
                if profit > 0:
                    # 승리 → 기본 배수로 복원
                    dic["long_position_multiplier"] = base_position_multiplier
                    logger.info(f"롱 승리! 배수 복원: x{base_position_multiplier}")
                else:
                    # 손실 → 배수 증가
                    dic["long_position_multiplier"] = increased_position_multiplier
                    logger.info(f"롱 손실! 배수 증가: x{increased_position_multiplier}")
                
                msg = f"✅ 롱 청산 ({close_reason}) | 진입: {entryPrice_l:.2f} → 청산: {close_price:.2f} | 수익: {profit:.2f}$ ({pnl_pct*100:.2f}%)"
                telegram_sender.SendMessage(msg)
                logger.info(msg)

    logger.info("\n-- END --------------------------------------------------------------------------------------------\n")
    
    # 캔들 데이터 정리
    cleanup_dataframes(df)
    cleanup_memory()
    
    # JSON 저장
    if ml_predictor.last_train_date:
        dic["last_ml_train_date"] = ml_predictor.last_train_date.isoformat()
    
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

logger.info(f"=== ML Bot 종료 (최종 메모리: {final_memory:.2f} MB) ===")

