#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
고도화된 이동평균선 + 머신러닝 자동매매봇 (벡터화 최적화 버전)
- 완전 벡터화된 백테스트
- NumPy 기반 고속 연산
- 메모리 효율성 최적화
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
script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)

log_file = os.path.join(logs_dir, "advanced_ma_ml_bot_fast.log")
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AdvancedMAMLBotFast:
    def __init__(self, initial_balance: float = 10000, leverage: int = 20):
        """고도화된 MA+ML 봇 (벡터화 최적화 버전)"""
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.leverage = leverage
        
        # 기본 파라미터
        self.params = {
            'ma_short': 5,
            'ma_long': 20,
            'position_size': 0.05,
            'stop_loss_pct': 0.01,
            'take_profit_pct': 0.03,
            'trailing_stop_pct': 0.02,
            'trailing_stop_activation_pct': 0.01,
            'max_positions': 2,
            'max_long_positions': 1,
            'max_short_positions': 1,
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
            'ppo_signal': 9
        }
        
        # 머신러닝 모델
        self.ml_model = None
        self.scaler = StandardScaler()
        self.feature_importance = None
        
        # 백테스트 설정
        self.slippage = 0.0005
        self.commission = 0.0005
        
        # 통계
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.max_drawdown = 0
        self.peak_balance = initial_balance
        
    def calculate_technical_indicators_vectorized(self, df: pd.DataFrame) -> pd.DataFrame:
        """21가지 보조지표 벡터화 계산"""
        df = df.copy()
        
        # TALib를 사용한 벡터화 계산
        if self.params['ma_short'] > 0:
            df['ma_short'] = talib.SMA(df['close'], timeperiod=self.params['ma_short'])
        else:
            df['ma_short'] = 0
            
        if self.params['ma_long'] > 0:
            df['ma_long'] = talib.SMA(df['close'], timeperiod=self.params['ma_long'])
        else:
            df['ma_long'] = 0
        
        # 볼린저밴드
        if self.params['bb_period'] > 0 and self.params['bb_std'] > 0:
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
                df['close'], timeperiod=self.params['bb_period'], 
                nbdevup=self.params['bb_std'], nbdevdn=self.params['bb_std'], matype=0
            )
        else:
            df['bb_upper'] = df['bb_middle'] = df['bb_lower'] = 0
        
        # RSI
        if self.params['rsi_period'] > 0:
            df['rsi'] = talib.RSI(df['close'], timeperiod=self.params['rsi_period'])
        else:
            df['rsi'] = 50
        
        # 스토캐스틱
        if self.params['stoch_k'] > 0:
            df['stoch_k'], df['stoch_d'] = talib.STOCH(
                df['high'], df['low'], df['close'], 
                fastk_period=self.params['stoch_k'], slowk_period=3, slowd_period=self.params['stoch_d']
            )
        else:
            df['stoch_k'] = df['stoch_d'] = 50
        
        # MACD
        if self.params['macd_fast'] > 0 and self.params['macd_slow'] > 0 and self.params['macd_signal'] > 0:
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(
                df['close'], fastperiod=self.params['macd_fast'], 
                slowperiod=self.params['macd_slow'], signalperiod=self.params['macd_signal']
            )
        else:
            df['macd'] = df['macd_signal'] = df['macd_hist'] = 0
        
        # 기타 지표들 (벡터화)
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=self.params['atr_period'])
        df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=self.params['adx_period'])
        df['cci'] = talib.CCI(df['high'], df['low'], df['close'], timeperiod=self.params['cci_period'])
        df['williams_r'] = talib.WILLR(df['high'], df['low'], df['close'], timeperiod=self.params['williams_period'])
        df['mfi'] = talib.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=self.params['mfi_period'])
        df['obv'] = talib.OBV(df['close'], df['volume'])
        df['obv_ma'] = talib.SMA(df['obv'], timeperiod=self.params['obv_period'])
        df['roc'] = talib.ROC(df['close'], timeperiod=self.params['roc_period'])
        df['momentum'] = talib.MOM(df['close'], timeperiod=self.params['momentum_period'])
        df['kama'] = talib.KAMA(df['close'], timeperiod=self.params['kama_period'])
        df['trix'] = talib.TRIX(df['close'], timeperiod=self.params['trix_period'])
        df['ultosc'] = talib.ULTOSC(
            df['high'], df['low'], df['close'], 
            timeperiod1=self.params['ultosc_period1'], 
            timeperiod2=self.params['ultosc_period2'], 
            timeperiod3=self.params['ultosc_period3']
        )
        df['aroon_up'], df['aroon_down'] = talib.AROON(df['high'], df['low'], timeperiod=self.params['aroon_period'])
        df['bop'] = talib.BOP(df['open'], df['high'], df['low'], df['close'])
        df['dx'] = talib.DX(df['high'], df['low'], df['close'], timeperiod=self.params['dx_period'])
        df['minus_di'] = talib.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=self.params['minus_di_period'])
        df['plus_di'] = talib.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=self.params['plus_di_period'])
        df['ppo'] = talib.PPO(df['close'], fastperiod=self.params['ppo_fast'], slowperiod=self.params['ppo_slow'])
        
        return df
    
    def create_features_vectorized(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """벡터화된 피처 생성"""
        df = self.calculate_technical_indicators_vectorized(df)
        
        # 기본 피처
        features = [
            'ma_short', 'ma_long', 'bb_upper', 'bb_middle', 'bb_lower',
            'rsi', 'stoch_k', 'stoch_d', 'macd', 'macd_signal', 'macd_hist',
            'atr', 'adx', 'cci', 'williams_r', 'mfi', 'obv', 'obv_ma',
            'roc', 'momentum', 'kama', 'trix', 'ultosc', 'aroon_up', 'aroon_down',
            'bop', 'dx', 'minus_di', 'plus_di', 'ppo'
        ]
        
        # 벡터화된 파생 피처 생성
        df['ma_cross'] = (df['ma_short'] > df['ma_long']).astype(int)
        
        # 볼린저밴드 위치 (벡터화)
        bb_range = df['bb_upper'] - df['bb_lower']
        df['bb_position'] = np.where(
            bb_range != 0, 
            (df['close'] - df['bb_lower']) / bb_range, 
            0.5
        )
        
        # 벡터화된 조건부 피처
        df['rsi_oversold'] = (df['rsi'] < 30).astype(int)
        df['rsi_overbought'] = (df['rsi'] > 70).astype(int)
        df['stoch_oversold'] = (df['stoch_k'] < 20).astype(int)
        df['stoch_overbought'] = (df['stoch_k'] > 80).astype(int)
        df['macd_bullish'] = (df['macd'] > df['macd_signal']).astype(int)
        df['macd_bearish'] = (df['macd'] < df['macd_signal']).astype(int)
        
        # 가격 변화율 (벡터화)
        df['price_change_1'] = df['close'].pct_change(1)
        df['price_change_5'] = df['close'].pct_change(5)
        df['price_change_10'] = df['close'].pct_change(10)
        
        # 볼륨 변화율 (벡터화)
        df['volume_change_1'] = df['volume'].pct_change(1)
        df['volume_change_5'] = df['volume'].pct_change(5)
        
        # 변동성 (벡터화)
        df['volatility_5'] = df['close'].rolling(5).std()
        df['volatility_20'] = df['close'].rolling(20).std()
        
        # 추가 피처
        features.extend([
            'ma_cross', 'bb_position', 'rsi_oversold', 'rsi_overbought',
            'stoch_oversold', 'stoch_overbought', 'macd_bullish', 'macd_bearish',
            'price_change_1', 'price_change_5', 'price_change_10',
            'volume_change_1', 'volume_change_5', 'volatility_5', 'volatility_20'
        ])
        
        # NaN/Inf 값 처리 (벡터화)
        for feature in features:
            if feature in df.columns:
                df[feature] = df[feature].replace([np.inf, -np.inf], np.nan)
                df[feature] = df[feature].fillna(0)
        
        return df, features
    
    def create_labels_vectorized(self, df: pd.DataFrame, lookforward: int = 5) -> pd.Series:
        """벡터화된 라벨 생성"""
        # 미래 수익률 계산 (벡터화)
        future_returns = df['close'].shift(-lookforward) / df['close'] - 1
        
        # 라벨 생성 (벡터화)
        up_threshold = 0.005
        down_threshold = -0.005
        
        labels = pd.Series(0, index=df.index)
        labels[future_returns > up_threshold] = 1
        labels[future_returns < down_threshold] = -1
        
        return labels
    
    def train_ml_model_vectorized(self, df: pd.DataFrame) -> Dict:
        """벡터화된 머신러닝 모델 훈련"""
        logger.info("벡터화된 머신러닝 모델 훈련 시작...")
        
        # 피처 및 라벨 생성
        df_features, features = self.create_features_vectorized(df)
        labels = self.create_labels_vectorized(df_features)
        
        # 결측값 제거 (벡터화)
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
        
        # 모델 훈련
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train_scaled, y_train)
        
        # 성능 평가
        y_pred = model.predict(X_test_scaled)
        accuracy = (y_pred == y_test).mean()
        
        # 피처 중요도
        self.feature_importance = dict(zip(features, model.feature_importances_))
        
        # 모델 저장
        self.ml_model = model
        
        logger.info(f"벡터화된 모델 훈련 완료: 정확도 {accuracy:.4f}")
        return {
            'accuracy': accuracy,
            'feature_importance': self.feature_importance,
            'n_features': len(features),
            'n_samples': len(X)
        }
    
    def run_vectorized_backtest(self, df: pd.DataFrame, start_date: str = None, end_date: str = None, skip_training: bool = False) -> Dict:
        """완전 벡터화된 백테스트"""
        logger.info("벡터화된 백테스트 시작...")
        
        # 날짜 필터링
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        # 피처 생성
        df_features, features = self.create_features_vectorized(df)
        
        # 머신러닝 모델 훈련 (skip_training이 False이고 모델이 없을 때만)
        if not skip_training and self.ml_model is None:
            logger.info("초기 머신러닝 모델 훈련...")
            train_result = self.train_ml_model_vectorized(df_features)
            if 'error' in train_result:
                logger.error(f"모델 훈련 실패: {train_result['error']}")
                return train_result
        
        # 벡터화된 백테스트 실행
        results = self._execute_vectorized_backtest(df_features, features)
        
        return results
    
    def _execute_vectorized_backtest(self, df: pd.DataFrame, features: List[str]) -> Dict:
        """벡터화된 백테스트 실행 (핵심 로직)"""
        n = len(df)
        
        # NumPy 배열로 변환 (메모리 효율성)
        prices = df['close'].values
        timestamps = df.index.values
        
        # 신호 생성 (벡터화)
        signals = self._generate_signals_vectorized(df, features)
        
        # 포지션 관리 (벡터화)
        positions = self._manage_positions_vectorized(prices, signals, timestamps)
        
        # 결과 계산
        results = self._calculate_vectorized_results(positions, prices, timestamps)
        
        return results
    
    def _generate_signals_vectorized(self, df: pd.DataFrame, features: List[str]) -> np.ndarray:
        """벡터화된 신호 생성"""
        if self.ml_model is None:
            return np.zeros(len(df))
        
        # 피처 스케일링
        X = df[features].values
        X_scaled = self.scaler.transform(X)
        
        # 예측 (벡터화)
        predictions = self.ml_model.predict(X_scaled)
        probabilities = self.ml_model.predict_proba(X_scaled)
        confidences = np.max(probabilities, axis=1)
        
        # 이동평균선 신호 (벡터화)
        ma_short = df['ma_short'].values
        ma_long = df['ma_long'].values
        current_price = df['close'].values
        
        # 벡터화된 이동평균선 신호
        ma_signal = np.zeros(len(df))
        if np.any(ma_short > 0) and np.any(ma_long > 0):
            ma_signal = np.where(
                (current_price > ma_short) & (ma_short > ma_long), 1,
                np.where(
                    (current_price < ma_short) & (ma_short < ma_long), -1, 0
                )
            )
        
        # 최종 신호 (벡터화)
        final_signals = np.zeros(len(df))
        
        # 롱 신호
        long_condition = (predictions == 1) & (ma_signal >= 0) & (confidences > 0.55)
        final_signals[long_condition] = 1
        
        # 숏 신호
        short_condition = (predictions == -1) & (ma_signal <= 0) & (confidences > 0.55)
        final_signals[short_condition] = -1
        
        return final_signals
    
    def _manage_positions_vectorized(self, prices: np.ndarray, signals: np.ndarray, timestamps: np.ndarray) -> List[Dict]:
        """벡터화된 포지션 관리"""
        positions = []
        n = len(prices)
        
        # 포지션 상태 추적
        position_state = 0  # 0: 없음, 1: 롱, -1: 숏
        entry_price = 0
        entry_idx = 0
        
        for i in range(1, n):
            current_price = prices[i]
            signal = signals[i]
            
            # 포지션 청산 체크 (벡터화)
            if position_state != 0:
                # 스탑로스/익절 체크
                if position_state == 1:  # 롱 포지션
                    pnl_pct = (current_price - entry_price) / entry_price
                    if pnl_pct <= -self.params['stop_loss_pct'] or pnl_pct >= self.params['take_profit_pct']:
                        # 롱 포지션 청산
                        positions.append({
                            'side': 'buy',
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'entry_time': timestamps[entry_idx],
                            'exit_time': timestamps[i],
                            'pnl': (current_price - entry_price) * (self.current_balance * self.params['position_size'] * self.leverage / entry_price),
                            'reason': 'stop_loss' if pnl_pct <= -self.params['stop_loss_pct'] else 'take_profit'
                        })
                        position_state = 0
                        
                elif position_state == -1:  # 숏 포지션
                    pnl_pct = (entry_price - current_price) / entry_price
                    if pnl_pct <= -self.params['stop_loss_pct'] or pnl_pct >= self.params['take_profit_pct']:
                        # 숏 포지션 청산
                        positions.append({
                            'side': 'sell',
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'entry_time': timestamps[entry_idx],
                            'exit_time': timestamps[i],
                            'pnl': (entry_price - current_price) * (self.current_balance * self.params['position_size'] * self.leverage / entry_price),
                            'reason': 'stop_loss' if pnl_pct <= -self.params['stop_loss_pct'] else 'take_profit'
                        })
                        position_state = 0
            
            # 새로운 포지션 진입
            if position_state == 0 and signal != 0:
                position_state = signal
                entry_price = current_price
                entry_idx = i
        
        return positions
    
    def _calculate_vectorized_results(self, positions: List[Dict], prices: np.ndarray, timestamps: np.ndarray) -> Dict:
        """벡터화된 결과 계산"""
        if not positions:
            return {"error": "거래 기록이 없습니다."}
        
        # 통계 계산 (벡터화)
        pnls = np.array([pos['pnl'] for pos in positions])
        total_pnl = np.sum(pnls)
        total_return = (total_pnl / self.initial_balance) * 100
        
        # 승률 계산
        winning_trades = np.sum(pnls > 0)
        total_trades = len(pnls)
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        # 평균 수익/손실
        winning_pnls = pnls[pnls > 0]
        losing_pnls = pnls[pnls < 0]
        avg_win = np.mean(winning_pnls) if len(winning_pnls) > 0 else 0
        avg_loss = np.mean(losing_pnls) if len(losing_pnls) > 0 else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        
        # 최대 낙폭 계산 (벡터화)
        cumulative_pnl = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative_pnl)
        drawdowns = running_max - cumulative_pnl
        max_drawdown = np.max(drawdowns) / self.initial_balance * 100 if len(drawdowns) > 0 else 0
        
        # 샤프 비율 (간단한 버전)
        returns = np.diff(cumulative_pnl) / self.initial_balance
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 and np.std(returns) > 0 else 0
        
        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.initial_balance + total_pnl,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "trades": positions
        }
    
    def run_continuous_backtest(self, start_year: int, end_year: int) -> Dict:
        """연속 백테스트 실행 (2018-2024) - 올바른 백테스트 구조"""
        logger.info(f"연속 백테스트 시작: {start_year}년 ~ {end_year}년")
        print(f"🚀 연속 백테스트 시작: {start_year}년 ~ {end_year}년")
        print("=" * 80)
        
        all_results = {}
        total_initial_capital = self.initial_balance
        current_capital = self.initial_balance
        
        # 연도별 결과 저장
        yearly_results = []
        
        # 전체 데이터 로드 (훈련용 + 테스트용)
        print("📊 전체 데이터 로드 중...")
        all_data = []
        for year in range(start_year, end_year + 1):
            data_files = [
                f'data/BTCUSDT/5m/BTCUSDT_5m_{year}.csv',
                f'data/BTCUSDT/1m/BTCUSDT_1m_{year}.csv',
                f'../data/BTCUSDT/5m/BTCUSDT_5m_{year}.csv',
                f'BTCUSDT_5m_{year}.csv'
            ]
            
            data_file = None
            for file_path in data_files:
                if os.path.exists(file_path):
                    data_file = file_path
                    break
            
            if data_file:
                df = pd.read_csv(data_file)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.set_index('timestamp')
                all_data.append(df)
                print(f"   ✅ {year}년 데이터 로드: {len(df):,}개 캔들")
            else:
                print(f"   ❌ {year}년 데이터를 찾을 수 없습니다.")
        
        if not all_data:
            return {"error": "유효한 데이터가 없습니다."}
        
        # 전체 데이터 합치기
        combined_data = pd.concat(all_data, ignore_index=False)
        combined_data = combined_data.sort_index()
        print(f"📊 전체 데이터: {len(combined_data):,}개 캔들")
        
        # 초기 모델 훈련 (첫 해 이전 데이터로)
        print(f"\n🤖 초기 모델 훈련 중...")
        initial_bot = AdvancedMAMLBotFast(initial_balance=current_capital, leverage=self.leverage)
        
        # 첫 해 이전 데이터로 훈련 (예: 2018년 테스트하려면 2017년 이전 데이터로 훈련)
        if start_year > 2017:
            # 2017년 데이터가 있으면 사용, 없으면 첫 해의 첫 3개월로 훈련
            train_data = combined_data[combined_data.index < f'{start_year}-04-01']
        else:
            train_data = combined_data[combined_data.index < f'{start_year}-04-01']
        
        if len(train_data) < 1000:
            print("⚠️ 훈련 데이터가 부족합니다. 첫 해의 첫 3개월로 훈련합니다.")
            train_data = combined_data[combined_data.index < f'{start_year}-07-01']
        
        print(f"   📊 훈련 데이터: {len(train_data):,}개 캔들")
        
        # 초기 모델 훈련
        train_result = initial_bot.train_ml_model_vectorized(train_data)
        if 'error' in train_result:
            print(f"❌ 초기 모델 훈련 실패: {train_result['error']}")
            return train_result
        
        print(f"   ✅ 초기 모델 훈련 완료: 정확도 {train_result['accuracy']:.4f}")
        
        # 연도별 백테스트 실행
        for year in range(start_year, end_year + 1):
            print(f"\n📅 {year}년 백테스트 시작...")
            print("-" * 60)
            
            # 해당 연도 데이터 필터링
            year_data = combined_data[combined_data.index.year == year]
            if len(year_data) == 0:
                print(f"❌ {year}년 데이터가 없습니다. 건너뜁니다.")
                continue
            
            print(f"📊 {year}년 데이터: {len(year_data):,}개 캔들")
            
            try:
                # 봇 초기화 (훈련된 모델 복사)
                year_bot = AdvancedMAMLBotFast(initial_balance=current_capital, leverage=self.leverage)
                year_bot.ml_model = initial_bot.ml_model
                year_bot.scaler = initial_bot.scaler
                year_bot.feature_importance = initial_bot.feature_importance
                
                # 백테스트 실행 (모델 재훈련 없이)
                year_result = year_bot.run_vectorized_backtest(year_data, skip_training=True)
                
                if 'error' in year_result:
                    print(f"❌ {year}년 백테스트 실패: {year_result['error']}")
                    continue
                
                # 결과 저장
                all_results[year] = year_result
                yearly_results.append({
                    'year': year,
                    'initial_balance': year_result['initial_balance'],
                    'final_balance': year_result['final_balance'],
                    'total_return': year_result['total_return'],
                    'max_drawdown': year_result['max_drawdown'],
                    'sharpe_ratio': year_result['sharpe_ratio'],
                    'win_rate': year_result['win_rate'],
                    'total_trades': year_result['total_trades'],
                    'profit_factor': year_result['profit_factor']
                })
                
                # 다음 연도를 위한 자본 업데이트
                current_capital = year_result['final_balance']
                
                print(f"💰 {year}년 최종 자본: ${year_result['final_balance']:,.2f}")
                print(f"📈 {year}년 수익률: {year_result['total_return']:.2f}%")
                print(f"📊 {year}년 거래: {year_result['total_trades']}회, 승률: {year_result['win_rate']:.1f}%")
                
            except Exception as e:
                print(f"❌ {year}년 처리 중 오류: {e}")
                continue
        
        # 전체 결과 분석
        if not yearly_results:
            return {"error": "유효한 백테스트 결과가 없습니다."}
        
        # 전체 통계 계산
        total_pnl = current_capital - total_initial_capital
        total_return = (total_pnl / total_initial_capital) * 100
        
        # 연도별 수익률 계산
        yearly_returns = [result['total_return'] for result in yearly_results]
        avg_yearly_return = np.mean(yearly_returns)
        
        # 최대 낙폭 계산
        peak = total_initial_capital
        max_dd = 0
        for result in yearly_results:
            if result['final_balance'] > peak:
                peak = result['final_balance']
            dd = (peak - result['final_balance']) / peak * 100
            max_dd = max(max_dd, dd)
        
        # 전체 거래 통계
        total_trades = sum(result['total_trades'] for result in yearly_results)
        avg_win_rate = np.mean([result['win_rate'] for result in yearly_results])
        avg_sharpe = np.mean([result['sharpe_ratio'] for result in yearly_results])
        
        # 결과 출력
        print("\n" + "=" * 80)
        print("📊 연속 백테스트 전체 결과")
        print("=" * 80)
        print(f"💰 초기 자본: ${total_initial_capital:,.2f}")
        print(f"💰 최종 자본: ${current_capital:,.2f}")
        print(f"📈 전체 수익률: {total_return:.2f}%")
        print(f"📊 평균 연간 수익률: {avg_yearly_return:.2f}%")
        print(f"📉 최대 낙폭: {max_dd:.2f}%")
        print(f"📊 평균 샤프 비율: {avg_sharpe:.2f}")
        print(f"📊 총 거래 횟수: {total_trades:,}회")
        print(f"📊 평균 승률: {avg_win_rate:.1f}%")
        
        print(f"\n📅 연도별 상세 결과:")
        print("-" * 80)
        print(f"{'연도':<6} {'초기자본':<12} {'최종자본':<12} {'수익률':<8} {'거래수':<8} {'승률':<8} {'샤프비율':<8}")
        print("-" * 80)
        
        for result in yearly_results:
            print(f"{result['year']:<6} "
                  f"${result['initial_balance']:,.0f}    "
                  f"${result['final_balance']:,.0f}    "
                  f"{result['total_return']:>6.1f}%  "
                  f"{result['total_trades']:>6}회  "
                  f"{result['win_rate']:>6.1f}%  "
                  f"{result['sharpe_ratio']:>6.2f}")
        
        return {
            "initial_balance": total_initial_capital,
            "final_balance": current_capital,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "avg_yearly_return": avg_yearly_return,
            "max_drawdown": max_dd,
            "avg_sharpe_ratio": avg_sharpe,
            "total_trades": total_trades,
            "avg_win_rate": avg_win_rate,
            "yearly_results": yearly_results,
            "all_results": all_results,
            "num_years": len(yearly_results)
        }

# 사용 예시
if __name__ == "__main__":
    # 봇 생성
    bot = AdvancedMAMLBotFast(initial_balance=10000, leverage=20)
    
    # 데이터 로드
    try:
        data_file = 'data/BTCUSDT/5m/BTCUSDT_5m_2024.csv'
        if not os.path.exists(data_file):
            data_file = 'data/BTCUSDT/1m/BTCUSDT_1m_2024.csv'
        
        df = pd.read_csv(data_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        
        # 벡터화된 백테스트 실행
        results = bot.run_vectorized_backtest(df, start_date='2024-01-01', end_date='2024-01-31')
        
        print("\n=== 벡터화된 백테스트 결과 ===")
        print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
        print(f"최종 자본: {results['final_balance']:,.0f} USDT")
        print(f"총 수익률: {results['total_return']:.2f}%")
        print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
        print(f"샤프 비율: {results['sharpe_ratio']:.2f}")
        print(f"승률: {results['win_rate']:.2f}%")
        print(f"수익 팩터: {results['profit_factor']:.2f}")
        print(f"총 거래 횟수: {results['total_trades']}회")
        
    except Exception as e:
        print(f"백테스트 실행 오류: {e}")
        import traceback
        traceback.print_exc()
