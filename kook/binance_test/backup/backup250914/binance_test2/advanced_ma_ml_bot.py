#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
고도화된 이동평균선 + 머신러닝 자동매매봇
- 이동평균선 2개 기반 신호 트리거
- 21가지 보조지표 머신러닝 피처
- 파라미터 오토튜닝
- 드리프트 모니터링 및 리파인
- 월별 자동 재학습
- 슬리피지, 펀비 반영 백테스트
"""

import sys
import os
import pandas as pd
import numpy as np
import datetime as dt
import json
import warnings
from typing import Dict, List, Tuple, Optional, Any
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
import joblib
import talib
from scipy import stats
import logging

warnings.filterwarnings('ignore')

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AdvancedMAMLBot:
    def __init__(self, initial_balance: float = 10000, leverage: int = 20):
        """
        고도화된 이동평균선 + 머신러닝 자동매매봇
        
        Args:
            initial_balance: 초기 자본금 (USDT)
            leverage: 레버리지
        """
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.leverage = leverage
        
        # 기본 파라미터 (오토튜닝 대상)
        self.params = {
            # 이동평균선 파라미터
            'ma_short': 5,
            'ma_long': 20,
            
            # 거래 파라미터
            'position_size': 0.05,  # 포지션 크기 (자본의 5%)
            'stop_loss_pct': 0.01,  # 스탑로스 1%로 줄임
            'take_profit_pct': 0.03,  # 익절 2%로 줄임
            'trailing_stop_pct': 0.02,  # 트레일링 스탑 2%
            'trailing_stop_activation_pct': 0.01,  # 트레일링 스탑 활성화 임계값 1%
            'max_positions': 2,  # 최대 동시 포지션 수 (롱+숏 합계)
            'max_long_positions': 1,  # 최대 롱 포지션 수
            'max_short_positions': 1,  # 최대 숏 포지션 수
            
            # 보조지표 파라미터
            'bb_period': 20,
            'bb_std': 2.0,
            'rsi_period': 14,
            'stoch_k': 14,
            'stoch_d': 3,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
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
            'bop_period': 14,
            'dx_period': 14,
            'minus_di_period': 14,
            'plus_di_period': 14,
            'minus_dm_period': 14,
            'plus_dm_period': 14,
            'ppo_fast': 12,
            'ppo_slow': 26,
            'ppo_signal': 9,
            'roc_period': 10,
            'rsi2_period': 2,
            'trix_period': 14,
            'ultosc_period1': 7,
            'ultosc_period2': 14,
            'ultosc_period3': 28,
            'williams_period': 14
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
        
        # 드리프트 모니터링
        self.drift_threshold = 0.1  # 드리프트 임계값
        self.last_retrain_date = None
        self.performance_history = []
        
        # 백테스트 설정
        self.slippage = 0.0005  # 0.05% 슬리피지
        self.funding_rate = 0.0  # 펀딩비 제거
        self.commission = 0.0005  # 0.05% 수수료 (매수/매도 각각)
        
        # 통계
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.max_drawdown = 0
        self.peak_balance = initial_balance
        
        # 동적 포지션 사이즈 관리
        self.current_position_size = 0.05  # 현재 포지션 사이즈
        self.base_position_size = 0.05    # 기본 포지션 사이즈
        self.increased_position_size = 0.1 # 실패 시 포지션 사이즈
        self.consecutive_losses = 0        # 연속 손실 횟수
        self.consecutive_wins = 0          # 연속 승리 횟수
        
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """21가지 보조지표 계산"""
        df = df.copy()
        
        # 1. 이동평균선
        df['ma_short'] = talib.SMA(df['close'], timeperiod=self.params['ma_short'])
        df['ma_long'] = talib.SMA(df['close'], timeperiod=self.params['ma_long'])
        
        # 2. 볼린저밴드
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
            df['close'], timeperiod=self.params['bb_period'], nbdevup=self.params['bb_std'], 
            nbdevdn=self.params['bb_std'], matype=0
        )
        
        # 3. RSI
        df['rsi'] = talib.RSI(df['close'], timeperiod=self.params['rsi_period'])
        
        # 4. 스토캐스틱
        df['stoch_k'], df['stoch_d'] = talib.STOCH(
            df['high'], df['low'], df['close'], 
            fastk_period=self.params['stoch_k'], slowk_period=3, slowd_period=self.params['stoch_d']
        )
        
        # 5. MACD
        df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(
            df['close'], fastperiod=self.params['macd_fast'], 
            slowperiod=self.params['macd_slow'], signalperiod=self.params['macd_signal']
        )
        
        # 6. ATR (Average True Range)
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=self.params['atr_period'])
        
        # 7. ADX (Average Directional Index)
        df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=self.params['adx_period'])
        
        # 8. CCI (Commodity Channel Index)
        df['cci'] = talib.CCI(df['high'], df['low'], df['close'], timeperiod=self.params['cci_period'])
        
        # 9. Williams %R
        df['williams_r'] = talib.WILLR(df['high'], df['low'], df['close'], timeperiod=self.params['williams_period'])
        
        # 10. MFI (Money Flow Index)
        df['mfi'] = talib.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=self.params['mfi_period'])
        
        # 11. OBV (On Balance Volume)
        df['obv'] = talib.OBV(df['close'], df['volume'])
        df['obv_ma'] = talib.SMA(df['obv'], timeperiod=self.params['obv_period'])
        
        # 12. ROC (Rate of Change)
        df['roc'] = talib.ROC(df['close'], timeperiod=self.params['roc_period'])
        
        # 13. Momentum
        df['momentum'] = talib.MOM(df['close'], timeperiod=self.params['momentum_period'])
        
        # 14. KAMA (Kaufman's Adaptive Moving Average)
        df['kama'] = talib.KAMA(df['close'], timeperiod=self.params['kama_period'])
        
        # 15. TRIX
        df['trix'] = talib.TRIX(df['close'], timeperiod=self.params['trix_period'])
        
        # 16. Ultimate Oscillator
        df['ultosc'] = talib.ULTOSC(
            df['high'], df['low'], df['close'], 
            timeperiod1=self.params['ultosc_period1'], 
            timeperiod2=self.params['ultosc_period2'], 
            timeperiod3=self.params['ultosc_period3']
        )
        
        # 17. Aroon
        df['aroon_up'], df['aroon_down'] = talib.AROON(
            df['high'], df['low'], timeperiod=self.params['aroon_period']
        )
        
        # 18. BOP (Balance of Power)
        df['bop'] = talib.BOP(df['open'], df['high'], df['low'], df['close'])
        
        # 19. DX (Directional Movement Index)
        df['dx'] = talib.DX(df['high'], df['low'], df['close'], timeperiod=self.params['dx_period'])
        
        # 20. MINUS_DI, PLUS_DI
        df['minus_di'] = talib.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=self.params['minus_di_period'])
        df['plus_di'] = talib.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=self.params['plus_di_period'])
        
        # 21. PPO (Percentage Price Oscillator)
        df['ppo'] = talib.PPO(df['close'], fastperiod=self.params['ppo_fast'], slowperiod=self.params['ppo_slow'])
        
        return df
    
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
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
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
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
        
        return df, features
    
    def create_labels(self, df: pd.DataFrame, lookforward: int = 5) -> pd.Series:
        """미래 수익률 기반 라벨 생성 (개선된 버전)"""
        # 미래 수익률 계산
        future_returns = df['close'].shift(-lookforward) / df['close'] - 1
        
        # 라벨 생성 (3분류: 상승=1, 하락=-1, 횡보=0)
        up_threshold = 0.005   # 0.5% 이상 상승
        down_threshold = -0.005  # 0.5% 이상 하락
        
        labels = pd.Series(0, index=df.index)  # 기본값: 횡보
        labels[future_returns > up_threshold] = 1    # 상승
        labels[future_returns < down_threshold] = -1  # 하락
        
        return labels
    
    def train_ml_model(self, df: pd.DataFrame) -> Dict:
        """머신러닝 모델 훈련"""
        logger.info("머신러닝 모델 훈련 시작...")
        
        # 피처 및 라벨 생성
        df_features, features = self.create_features(df)
        labels = self.create_labels(df_features)
        
        # 결측값 제거
        valid_idx = ~(df_features[features].isna().any(axis=1) | labels.isna())
        X = df_features[features].loc[valid_idx]
        y = labels.loc[valid_idx]
        
        if len(X) < 1000:
            logger.warning("훈련 데이터가 부족합니다.")
            return {'error': '훈련 데이터 부족'}
        
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
            # 교차 검증
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
        
        # 피처 중요도 (RandomForest인 경우)
        if hasattr(best_model, 'feature_importances_'):
            self.feature_importance = dict(zip(features, best_model.feature_importances_))
        
        # 모델 저장
        self.ml_model = best_model
        
        # 결과 반환
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
    
    def auto_tune_parameters(self, df: pd.DataFrame) -> Dict:
        """파라미터 오토튜닝"""
        logger.info("파라미터 오토튜닝 시작...")
        
        # 튜닝할 파라미터 범위
        param_ranges = {
            'ma_short': [3, 5, 7, 10, 12],
            'ma_long': [15, 20, 25, 30, 50],
            'bb_period': [15, 20, 25],
            'bb_std': [1.5, 2.0, 2.5],
            'rsi_period': [10, 14, 18],
            'stoch_k': [10, 14, 18],
            'macd_fast': [8, 12, 16],
            'macd_slow': [20, 26, 32],
            'macd_signal': [7, 9, 11],
            'position_size': [0.05],  # 고정 포지션 사이즈
            'stop_loss_pct': [0.015, 0.02, 0.025, 0.03],
            'take_profit_pct': [0.025, 0.03, 0.035, 0.04],
            'trailing_stop_pct': [0.015, 0.02, 0.025, 0.03],
            'trailing_stop_activation_pct': [0.005, 0.01, 0.015, 0.02]
        }
        
        best_params = self.params.copy()
        best_score = float('-inf')
        
        # 랜덤 샘플링으로 파라미터 조합 테스트
        np.random.seed(42)
        n_trials = 50  # 테스트할 조합 수
        
        for trial in range(n_trials):
            # 랜덤 파라미터 선택
            test_params = self.params.copy()
            for param, values in param_ranges.items():
                test_params[param] = np.random.choice(values)
            
            # 파라미터 적용
            old_params = self.params.copy()
            self.params = test_params
            
            try:
                # 백테스트 실행
                score = self.evaluate_parameters(df)
                
                if score > best_score:
                    best_score = score
                    best_params = test_params.copy()
                    
                logger.info(f"Trial {trial+1}/{n_trials}: Score = {score:.4f}")
                
            except Exception as e:
                logger.warning(f"Trial {trial+1} failed: {e}")
            
            # 파라미터 복원
            self.params = old_params
        
        # 최적 파라미터 적용
        self.params = best_params
        
        logger.info(f"파라미터 튜닝 완료. 최고 점수: {best_score:.4f}")
        return {
            'best_params': best_params,
            'best_score': best_score,
            'n_trials': n_trials
        }
    
    def evaluate_parameters(self, df: pd.DataFrame) -> float:
        """파라미터 평가 (간단한 백테스트)"""
        # 간단한 백테스트로 파라미터 평가
        df_features, features = self.create_features(df)
        
        # 이동평균선 크로스 신호
        df_features['ma_cross_up'] = (
            (df_features['ma_short'] > df_features['ma_long']) & 
            (df_features['ma_short'].shift(1) <= df_features['ma_long'].shift(1))
        )
        df_features['ma_cross_down'] = (
            (df_features['ma_short'] < df_features['ma_long']) & 
            (df_features['ma_short'].shift(1) >= df_features['ma_long'].shift(1))
        )
        
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
        
        return sharpe_ratio
    
    def detect_drift(self, df: pd.DataFrame) -> Dict:
        """드리프트 감지"""
        logger.info("드리프트 감지 시작...")
        
        if not self.ml_model:
            return {'drift_detected': False, 'reason': 'No model available'}
        
        # 최근 데이터로 피처 생성
        df_features, features = self.create_features(df)
        
        # 최근 100개 데이터 포인트 사용
        recent_data = df_features[features].tail(100)
        
        if len(recent_data) < 100:
            return {'drift_detected': False, 'reason': 'Insufficient data'}
        
        # 피처 스케일링
        recent_scaled = self.scaler.transform(recent_data)
        
        # 예측 확률 계산
        predictions = self.ml_model.predict_proba(recent_scaled)[:, 1]
        
        # 드리프트 감지 (예측 확률의 분포 변화)
        mean_pred = np.mean(predictions)
        std_pred = np.std(predictions)
        
        # 기준값과 비교 (과거 성능 기준)
        if hasattr(self, 'baseline_performance'):
            baseline_mean = self.baseline_performance.get('mean_prediction', 0.5)
            baseline_std = self.baseline_performance.get('std_prediction', 0.1)
            
            # 드리프트 임계값
            mean_drift = abs(mean_pred - baseline_mean) / baseline_std
            std_drift = abs(std_pred - baseline_std) / baseline_std
            
            drift_detected = mean_drift > self.drift_threshold or std_drift > self.drift_threshold
            
            return {
                'drift_detected': drift_detected,
                'mean_drift': mean_drift,
                'std_drift': std_drift,
                'current_mean': mean_pred,
                'current_std': std_pred,
                'baseline_mean': baseline_mean,
                'baseline_std': baseline_std
            }
        else:
            # 기준값 설정
            self.baseline_performance = {
                'mean_prediction': mean_pred,
                'std_prediction': std_pred
            }
            
            return {
                'drift_detected': False,
                'reason': 'Baseline established',
                'baseline_mean': mean_pred,
                'baseline_std': std_pred
            }
    
    def should_retrain(self, current_date: dt.datetime) -> bool:
        """재학습 필요 여부 판단"""
        if self.last_retrain_date is None:
            return True
        
        # 한 달이 지났는지 확인
        days_since_retrain = (current_date - self.last_retrain_date).days
        return days_since_retrain >= 30
    
    def execute_trade(self, side: str, amount: float, price: float) -> Dict:
        """거래 실행 (슬리피지, 펀딩비, 수수료 반영)"""
        # 슬리피지 적용
        if side == 'buy':
            execution_price = price * (1 + self.slippage)
        else:
            execution_price = price * (1 - self.slippage)
        
        # 수수료 계산
        commission = execution_price * amount * self.commission
        
        # 거래 실행
        trade = {
            'id': self.position_id,
            'side': side,
            'amount': amount,
            'price': execution_price,
            'commission': commission,
            'timestamp': dt.datetime.now()
        }
        
        self.position_id += 1
        self.current_balance -= commission
        
        return trade
    
    def update_trailing_stop(self, position: Dict, current_price: float, df: pd.DataFrame = None, current_idx: int = None):
        """트레일링 스탑 업데이트"""
        side = position['side']
        
        # 변동성 기반 파라미터 가져오기
        if df is not None and current_idx is not None:
            adjusted_params = self.calculate_volatility_adjusted_params(df, current_idx)
            trailing_stop_activation_pct = adjusted_params['trailing_stop_activation_pct']
        else:
            trailing_stop_activation_pct = self.params['trailing_stop_activation_pct']
        
        if side == 'buy':  # 롱 포지션
            # 최고가 업데이트
            if position['highest_price'] is None or current_price > position['highest_price']:
                position['highest_price'] = current_price
                
                # 트레일링 스탑 활성화 체크
                entry_price = position['price']
                profit_pct = (current_price - entry_price) / entry_price
                if profit_pct >= trailing_stop_activation_pct:
                    position['trailing_stop_activated'] = True
                    
        else:  # 숏 포지션
            # 최저가 업데이트
            if position['lowest_price'] is None or current_price < position['lowest_price']:
                position['lowest_price'] = current_price
                
                # 트레일링 스탑 활성화 체크
                entry_price = position['price']
                profit_pct = (entry_price - current_price) / entry_price
                if profit_pct >= trailing_stop_activation_pct:
                    position['trailing_stop_activated'] = True

    def check_stop_loss_take_profit(self, position: Dict, current_price: float, df: pd.DataFrame = None, current_idx: int = None) -> Optional[str]:
        """스탑로스/익절/트레일링 스탑 체크"""
        entry_price = position['price']
        side = position['side']
        
        # 트레일링 스탑 업데이트
        self.update_trailing_stop(position, current_price, df, current_idx)
        
        # 변동성 기반 파라미터 가져오기
        if df is not None and current_idx is not None:
            adjusted_params = self.calculate_volatility_adjusted_params(df, current_idx)
            stop_loss_pct = adjusted_params['stop_loss_pct']
            take_profit_pct = adjusted_params['take_profit_pct']
            trailing_stop_pct = adjusted_params['trailing_stop_pct']
        else:
            stop_loss_pct = self.params['stop_loss_pct']
            take_profit_pct = self.params['take_profit_pct']
            trailing_stop_pct = self.params['trailing_stop_pct']
        
        if side == 'buy':  # 롱 포지션
            pnl_pct = (current_price - entry_price) / entry_price
            
            # 기본 스탑로스 체크
            if pnl_pct <= -stop_loss_pct:
                return 'stop_loss'
            
            # 기본 익절 체크
            if pnl_pct >= take_profit_pct:
                return 'take_profit'
            
            # 트레일링 스탑 체크
            if position['trailing_stop_activated'] and position['highest_price'] is not None:
                trailing_stop_price = position['highest_price'] * (1 - trailing_stop_pct)
                if current_price <= trailing_stop_price:
                    return 'trailing_stop'
                    
        else:  # 숏 포지션
            pnl_pct = (entry_price - current_price) / entry_price
            
            # 기본 스탑로스 체크
            if pnl_pct <= -stop_loss_pct:
                return 'stop_loss'
            
            # 기본 익절 체크
            if pnl_pct >= take_profit_pct:
                return 'take_profit'
            
            # 트레일링 스탑 체크
            if position['trailing_stop_activated'] and position['lowest_price'] is not None:
                trailing_stop_price = position['lowest_price'] * (1 + trailing_stop_pct)
                if current_price >= trailing_stop_price:
                    return 'trailing_stop'
        
        return None
    
    def adjust_position_size(self, trade_result: str):
        """거래 결과에 따른 포지션 사이즈 조정"""
        if trade_result == 'win':
            # 승리 시: 연속 승리 카운트 증가, 연속 손실 리셋
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            
            # 연속 승리 시 기본 포지션 사이즈로 복원
            if self.consecutive_wins >= 1:
                self.current_position_size = self.base_position_size
                logger.info(f"승리! 포지션 사이즈를 기본값으로 복원: {self.current_position_size}")
                
        elif trade_result == 'loss':
            # 손실 시: 연속 손실 카운트 증가, 연속 승리 리셋
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            
            # 연속 손실 시 포지션 사이즈 증가
            if self.consecutive_losses >= 1:
                self.current_position_size = self.increased_position_size
                logger.info(f"손실! 포지션 사이즈를 증가: {self.current_position_size}")
    
    def get_current_position_size(self) -> float:
        """현재 포지션 사이즈 반환"""
        return self.current_position_size
    
    def reset_position_size_tracking(self):
        """포지션 사이즈 추적 변수 초기화"""
        self.current_position_size = self.base_position_size
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        logger.info("포지션 사이즈 추적 변수 초기화")
    
    def run_sliding_window_backtest(self, df: pd.DataFrame, train_days: int = 15, test_days: int = 15, 
                                   start_date: str = '2024-01-01', end_date: str = '2024-03-31') -> Dict:
        """15일 단위 슬라이딩 윈도우 백테스트"""
        logger.info(f"슬라이딩 윈도우 백테스트 시작: {start_date} ~ {end_date}")
        logger.info(f"학습 기간: {train_days}일, 테스트 기간: {test_days}일")
        
        # 날짜 필터링
        df = df[(df.index >= start_date) & (df.index <= end_date)]
        
        # 전체 결과 저장
        all_results = []
        all_trades = []
        total_balance = self.initial_balance
        
        # 날짜 범위 생성
        current_date = pd.to_datetime(start_date)
        end_date_dt = pd.to_datetime(end_date)
        
        period_count = 0
        
        while current_date < end_date_dt:
            period_count += 1
            
            # 학습 기간 설정
            train_start = current_date
            train_end = current_date + pd.Timedelta(days=train_days-1)
            
            # 테스트 기간 설정
            test_start = train_end + pd.Timedelta(days=1)
            test_end = test_start + pd.Timedelta(days=test_days-1)
            
            # 테스트 기간이 종료일을 넘으면 조정
            if test_end > end_date_dt:
                test_end = end_date_dt
            
            # 데이터가 충분한지 확인
            if test_end <= test_start:
                break
                
            logger.info(f"\n=== 기간 {period_count} ===")
            logger.info(f"학습: {train_start.strftime('%Y-%m-%d')} ~ {train_end.strftime('%Y-%m-%d')}")
            logger.info(f"테스트: {test_start.strftime('%Y-%m-%d')} ~ {test_end.strftime('%Y-%m-%d')}")
            
            # 학습 데이터 추출
            train_df = df[(df.index >= train_start) & (df.index <= train_end)]
            test_df = df[(df.index >= test_start) & (df.index <= test_end)]
            
            if len(train_df) < 100 or len(test_df) < 50:
                logger.warning(f"기간 {period_count}: 데이터 부족으로 건너뜀")
                current_date = test_end + pd.Timedelta(days=1)
                continue
            
            # 봇 초기화 (각 기간마다 새로운 봇)
            period_bot = AdvancedMAMLBot(initial_balance=total_balance, leverage=self.leverage)
            period_bot.base_position_size = self.base_position_size
            period_bot.increased_position_size = self.increased_position_size
            period_bot.current_position_size = self.base_position_size
            
            # 기본 파라미터 설정
            period_bot.params['ma_short'] = 5
            period_bot.params['ma_long'] = 20
            period_bot.params['stop_loss_pct'] = 0.01
            period_bot.params['take_profit_pct'] = 0.03
            period_bot.params['trailing_stop_pct'] = 0.03
            period_bot.params['trailing_stop_activation_pct'] = 0.015
            period_bot.params['max_positions'] = 2
            
            # 월별 재학습 비활성화 (이미 각 기간마다 새로 학습하므로)
            period_bot.last_retrain_date = None
            
            # 학습 데이터로 모델 훈련
            logger.info(f"기간 {period_count}: 모델 훈련 중...")
            train_result = period_bot.train_ml_model(train_df)
            
            if 'error' in train_result:
                logger.error(f"기간 {period_count}: 모델 훈련 실패")
                current_date = test_end + pd.Timedelta(days=1)
                continue
            
            # 테스트 데이터로 백테스트 실행
            logger.info(f"기간 {period_count}: 백테스트 실행 중...")
            try:
                test_result = period_bot.run_backtest(test_df, 
                                                    start_date=test_start.strftime('%Y-%m-%d'),
                                                    end_date=test_end.strftime('%Y-%m-%d'))
                
                if 'error' in test_result:
                    logger.error(f"기간 {period_count}: 백테스트 실패 - {test_result['error']}")
                    current_date = test_end + pd.Timedelta(days=1)
                    continue
                    
            except Exception as e:
                logger.error(f"기간 {period_count}: 백테스트 실행 중 오류 발생 - {e}")
                current_date = test_end + pd.Timedelta(days=1)
                continue
            
            # 결과 저장
            period_result = {
                'period': period_count,
                'train_start': train_start.strftime('%Y-%m-%d'),
                'train_end': train_end.strftime('%Y-%m-%d'),
                'test_start': test_start.strftime('%Y-%m-%d'),
                'test_end': test_end.strftime('%Y-%m-%d'),
                'initial_balance': test_result['initial_balance'],
                'final_balance': test_result['final_balance'],
                'total_return': test_result['total_return'],
                'max_drawdown': test_result['max_drawdown'],
                'sharpe_ratio': test_result['sharpe_ratio'],
                'win_rate': test_result['win_rate'],
                'profit_factor': test_result['profit_factor'],
                'total_trades': test_result['total_trades'],
                'trades': test_result['trades']
            }
            
            all_results.append(period_result)
            all_trades.extend(test_result['trades'])
            
            # 다음 기간을 위한 잔고 업데이트
            total_balance = test_result['final_balance']
            
            logger.info(f"기간 {period_count} 결과: 수익률 {test_result['total_return']:.2f}%, "
                       f"거래 {test_result['total_trades']}회, 승률 {test_result['win_rate']:.2f}%")
            
            # 다음 기간으로 이동
            current_date = test_end + pd.Timedelta(days=1)
        
        # 전체 결과 집계
        if not all_results:
            return {"error": "유효한 백테스트 결과가 없습니다."}
        
        # 전체 통계 계산
        total_pnl = total_balance - self.initial_balance
        total_return = (total_pnl / self.initial_balance) * 100
        
        # 최대 낙폭 계산
        peak = self.initial_balance
        max_dd = 0
        for result in all_results:
            if result['final_balance'] > peak:
                peak = result['final_balance']
            dd = (peak - result['final_balance']) / peak * 100
            max_dd = max(max_dd, dd)
        
        # 승률 계산
        total_trades = sum(r['total_trades'] for r in all_results)
        winning_trades = sum(1 for trade in all_trades if trade['pnl'] > 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # 수익 팩터 계산
        winning_trades_pnl = [t['pnl'] for t in all_trades if t['pnl'] > 0]
        losing_trades_pnl = [t['pnl'] for t in all_trades if t['pnl'] < 0]
        avg_win = np.mean(winning_trades_pnl) if winning_trades_pnl else 0
        avg_loss = np.mean(losing_trades_pnl) if losing_trades_pnl else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        
        # 샤프 비율 계산 (간단한 버전)
        returns = [r['total_return'] for r in all_results]
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if returns and np.std(returns) > 0 else 0
        
        return {
            "initial_balance": self.initial_balance,
            "final_balance": total_balance,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "max_drawdown": max_dd,
            "sharpe_ratio": sharpe_ratio,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "trades": all_trades,
            "period_results": all_results,
            "num_periods": len(all_results)
        }
    
    def run_backtest(self, df: pd.DataFrame, start_date: str = None, end_date: str = None) -> Dict:
        """백테스트 실행"""
        logger.info("백테스트 시작...")
        
        # 날짜 필터링
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        # 초기화
        self.current_balance = self.initial_balance
        self.positions = []
        self.trades = []
        self.balance_history = []
        
        # 포지션 사이즈 추적 변수 초기화
        self.reset_position_size_tracking()
        
        # 피처 생성
        df_features, features = self.create_features(df)
        
        # 머신러닝 모델 훈련 (초기)
        if self.ml_model is None:
            logger.info("초기 머신러닝 모델 훈련...")
            train_result = self.train_ml_model(df_features)
            if 'error' in train_result:
                logger.error(f"모델 훈련 실패: {train_result['error']}")
                return train_result
        
        # 백테스트 실행
        for i in range(100, len(df_features)):  # 충분한 데이터 확보 후 시작
            current_price = df_features['close'].iloc[i]
            current_time = df_features.index[i]
            
            # 월별 재학습 체크
            if self.should_retrain(current_time):
                logger.info(f"월별 재학습 실행: {current_time}")
                
                # 드리프트 감지
                drift_result = self.detect_drift(df_features.iloc[:i+1])
                if drift_result.get('drift_detected', False):
                    logger.info("드리프트 감지됨. 모델 재훈련...")
                    self.train_ml_model(df_features.iloc[:i+1])
                
                # 파라미터 오토튜닝
                tune_result = self.auto_tune_parameters(df_features.iloc[:i+1])
                logger.info(f"파라미터 튜닝 완료: {tune_result['best_score']:.4f}")
                
                self.last_retrain_date = current_time
            
            # 스탑로스/익절 체크
            positions_to_close = []
            for j, position in enumerate(self.positions):
                close_reason = self.check_stop_loss_take_profit(position, current_price, df_features, i)
                if close_reason:
                    positions_to_close.append((j, close_reason))
            
            # 포지션 청산
            for j, close_reason in reversed(positions_to_close):
                position = self.positions.pop(j)
                self.close_position(position, current_price, close_reason)
            
            # 새로운 신호 생성 (롱/숏 개별 제한 체크)
            adjusted_params = self.calculate_volatility_adjusted_params(df_features, i)
            max_positions = adjusted_params['max_positions']
            max_long = adjusted_params['max_long_positions']
            max_short = adjusted_params['max_short_positions']
            
            # 현재 포지션 수 계산
            current_long_count = len([p for p in self.positions if p['side'] == 'buy'])
            current_short_count = len([p for p in self.positions if p['side'] == 'sell'])
            
            if len(self.positions) < max_positions:
                signal = self.generate_signal(df_features.iloc[:i+1], features)
                
                # 신호 생성 로깅 (처음 10번만)
                if i < 10:
                    logger.info(f"시점 {i}: 신호={signal}, 현재포지션={len(self.positions)}/{max_positions}, 롱={current_long_count}/{max_long}, 숏={current_short_count}/{max_short}")
                
                if signal['action'] == 'buy' and current_long_count < max_long:
                    logger.info(f"시점 {i}: 롱 포지션 오픈 - 신호={signal}")
                    self.open_position('buy', current_price, current_time, df_features, i)
                elif signal['action'] == 'sell' and current_short_count < max_short:
                    logger.info(f"시점 {i}: 숏 포지션 오픈 - 신호={signal}")
                    self.open_position('sell', current_price, current_time, df_features, i)
            
            # 펀딩비 제거됨 (더 이상 적용하지 않음)
            
            # 잔고 기록
            self.balance_history.append(self.current_balance)
        
        # 최종 결과 계산
        return self.calculate_results()
    
    def generate_signal(self, df: pd.DataFrame, features: List[str]) -> Dict:
        """거래 신호 생성 (개선된 버전)"""
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
        confidence = max(prediction_proba)
        
        # 이동평균선 신호도 확인
        ma_short = df['ma_short'].iloc[-1]
        ma_long = df['ma_long'].iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # 기본 이동평균선 신호
        ma_signal = 0
        if current_price > ma_short > ma_long:
            ma_signal = 1  # 상승 추세
        elif current_price < ma_short < ma_long:
            ma_signal = -1  # 하락 추세
        
        # 신호 생성 (머신러닝 + 이동평균선 조합)
        if prediction == 1 and ma_signal >= 0 and confidence > 0.6:
            return {'action': 'buy', 'confidence': confidence}
        elif prediction == -1 and ma_signal <= 0 and confidence > 0.6:
            return {'action': 'sell', 'confidence': confidence}
        else:
            return {'action': 'hold', 'confidence': confidence}
    
    def calculate_volatility_adjusted_params(self, df: pd.DataFrame, current_idx: int) -> Dict:
        """변동성 기반 모든 파라미터 조절 (동적 포지션 사이즈 적용)"""
        # 동적 포지션 사이즈 사용
        return {
            'position_size': self.get_current_position_size(),  # 동적 포지션 사이즈
            'stop_loss_pct': self.params['stop_loss_pct'],
            'take_profit_pct': self.params['take_profit_pct'],
            'trailing_stop_pct': self.params['trailing_stop_pct'],
            'trailing_stop_activation_pct': self.params['trailing_stop_activation_pct'],
            'max_positions': self.params['max_positions'],
            'max_long_positions': self.params['max_long_positions'],
            'max_short_positions': self.params['max_short_positions']
        }
    
    def open_position(self, side: str, price: float, timestamp: dt.datetime, df: pd.DataFrame = None, current_idx: int = None):
        """포지션 오픈 (동적 포지션 사이즈 적용)"""
        # 동적 포지션 사이즈 사용
        position_size = self.get_current_position_size()
        
        # 포지션 크기 계산
        position_value = self.current_balance * position_size * self.leverage
        amount = position_value / price
        
        # 거래 실행
        trade = self.execute_trade(side, amount, price)
        
        # 포지션 추가 (트레일링 스탑을 위한 최고가/최저가 초기화)
        position = {
            'id': trade['id'],
            'side': side,
            'amount': amount,
            'price': trade['price'],
            'timestamp': timestamp,
            'commission': trade['commission'],
            'highest_price': trade['price'] if side == 'buy' else None,  # 롱 포지션의 최고가
            'lowest_price': trade['price'] if side == 'sell' else None,  # 숏 포지션의 최저가
            'trailing_stop_activated': False  # 트레일링 스탑 활성화 여부
        }
        
        self.positions.append(position)
        self.total_trades += 1
        
        logger.info(f"포지션 오픈: {side} {amount:.4f} @ {trade['price']:.2f}")
    
    def close_position(self, position: Dict, price: float, reason: str):
        """포지션 청산"""
        # 반대 거래 실행
        opposite_side = 'sell' if position['side'] == 'buy' else 'buy'
        trade = self.execute_trade(opposite_side, position['amount'], price)
        
        # 손익 계산
        if position['side'] == 'buy':
            pnl = (price - position['price']) * position['amount'] - position['commission'] - trade['commission']
        else:
            pnl = (position['price'] - price) * position['amount'] - position['commission'] - trade['commission']
        
        # 잔고 업데이트
        self.current_balance += pnl
        
        # 거래 기록
        trade_record = {
            'id': position['id'],
            'side': position['side'],
            'amount': position['amount'],
            'entry_price': position['price'],
            'exit_price': price,
            'pnl': pnl,
            'reason': reason,
            'timestamp': dt.datetime.now()
        }
        
        self.trades.append(trade_record)
        
        if pnl > 0:
            self.winning_trades += 1
            # 승리 시 포지션 사이즈 조정
            self.adjust_position_size('win')
        else:
            self.losing_trades += 1
            # 손실 시 포지션 사이즈 조정
            self.adjust_position_size('loss')
        
        logger.info(f"포지션 청산: {position['side']} {position['amount']:.4f} @ {price:.2f}, PnL: {pnl:.2f}, 이유: {reason}, 현재 포지션 사이즈: {self.get_current_position_size()}")
    
    def apply_funding_fee(self):
        """펀딩비 적용 (현재 비활성화)"""
        # 펀딩비가 0으로 설정되어 있어서 실제로는 적용되지 않음
        pass
    
    def calculate_results(self) -> Dict:
        """백테스트 결과 계산"""
        if not self.trades:
            return {"error": "거래 기록이 없습니다."}
        
        total_pnl = self.current_balance - self.initial_balance
        total_return = (total_pnl / self.initial_balance) * 100
        
        win_rate = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        
        # 평균 수익/손실
        winning_trades = [t['pnl'] for t in self.trades if t['pnl'] > 0]
        losing_trades = [t['pnl'] for t in self.trades if t['pnl'] < 0]
        
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = np.mean(losing_trades) if losing_trades else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        
        # 최대 낙폭
        peak = self.initial_balance
        max_dd = 0
        for balance in self.balance_history:
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak * 100
            max_dd = max(max_dd, dd)
        
        # 샤프 비율
        returns = [self.balance_history[i] / self.balance_history[i-1] - 1 
                  for i in range(1, len(self.balance_history))]
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if returns and np.std(returns) > 0 else 0
        
        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.current_balance,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "max_drawdown": max_dd,
            "sharpe_ratio": sharpe_ratio,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "trades": self.trades,
            "balance_history": self.balance_history
        }
    
    def save_model(self, filename: str = 'advanced_ma_ml_model.pkl'):
        """모델 저장"""
        if self.ml_model is None:
            logger.warning("저장할 모델이 없습니다.")
            return
        
        model_data = {
            'model': self.ml_model,
            'scaler': self.scaler,
            'params': self.params,
            'feature_importance': self.feature_importance,
            'baseline_performance': getattr(self, 'baseline_performance', None)
        }
        
        filepath = os.path.join(os.path.dirname(__file__), filename)
        joblib.dump(model_data, filepath)
        logger.info(f"모델 저장 완료: {filepath}")
    
    def load_model(self, filename: str = 'advanced_ma_ml_model.pkl'):
        """모델 로드"""
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        if not os.path.exists(filepath):
            logger.warning(f"모델 파일이 존재하지 않습니다: {filepath}")
            return False
        
        try:
            model_data = joblib.load(filepath)
            self.ml_model = model_data['model']
            self.scaler = model_data['scaler']
            self.params = model_data['params']
            self.feature_importance = model_data.get('feature_importance')
            self.baseline_performance = model_data.get('baseline_performance')
            
            logger.info(f"모델 로드 완료: {filepath}")
            return True
        except Exception as e:
            logger.error(f"모델 로드 실패: {e}")
            return False

# 사용 예시
if __name__ == "__main__":
    # 봇 생성
    bot = AdvancedMAMLBot(initial_balance=10000, leverage=20)
    
    # 데이터 로드 (예시)
    try:
        df = pd.read_csv(r'c:\work\GitHub\py\kook\binance\data\BTC_USDT\1m\2024-01.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        
        # 백테스트 실행
        results = bot.run_backtest(df, start_date='2024-01-01', end_date='2024-01-31')
        
        print("\n=== 백테스트 결과 ===")
        print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
        print(f"최종 자본: {results['final_balance']:,.0f} USDT")
        print(f"총 수익률: {results['total_return']:.2f}%")
        print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
        print(f"샤프 비율: {results['sharpe_ratio']:.2f}")
        print(f"승률: {results['win_rate']:.2f}%")
        print(f"수익 팩터: {results['profit_factor']:.2f}")
        print(f"총 거래 횟수: {results['total_trades']}회")
        
        # 모델 저장
        bot.save_model()
        
    except Exception as e:
        print(f"백테스트 실행 오류: {e}")
        import traceback
        traceback.print_exc()
