#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
비트코인 2024년도 상승 조건 분석 도구
- 2024년 비트코인 가격 데이터 분석
- 상승 패턴 및 조건 분석
- 기술적 지표 분석
- 시각화를 통한 패턴 확인
"""

import sys
import os
import pandas as pd
import numpy as np
import datetime as dt
from typing import Dict, List, Tuple, Optional
import logging
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from scipy import stats
import warnings
import pickle
import json
warnings.filterwarnings('ignore')

# 머신러닝 라이브러리
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.preprocessing import StandardScaler

# XGBoost 라이브러리 (선택적)
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("XGBoost가 설치되지 않았습니다. Random Forest와 Gradient Boosting만 사용합니다.")

# 한글 폰트 설정
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Bitcoin2024Analyzer:
    def __init__(self, data_path: str = None, train_data_path: str = None):
        """
        비트코인 2024년 분석기
        
        Args:
            data_path: 테스트 데이터 파일 경로 (2024년)
            train_data_path: 학습 데이터 파일 경로 (2023년)
        """
        self.data_path = data_path
        self.train_data_path = train_data_path
        self.df = None
        self.train_df = None
        self.analysis_results = {}
        self.ml_models = {}
        self.scaler = StandardScaler()
        
    def load_data(self, symbol: str = "BTCUSDT", interval: str = "5m"):
        """
        비트코인 데이터 로드
        
        Args:
            symbol: 거래 심볼
            interval: 시간 간격
        """
        try:
            # 실제 데이터 파일 경로 설정
            if self.data_path and os.path.exists(self.data_path):
                data_file = self.data_path
            else:
                # 기본 데이터 파일 경로
                data_file = f"data/{symbol}/{interval}/{symbol}_{interval}_2024.csv"
                
            if os.path.exists(data_file):
                # 실제 CSV 파일 로드
                self.df = pd.read_csv(data_file)
                logger.info(f"실제 데이터 로드 완료: {len(self.df)}개 레코드")
                logger.info(f"데이터 기간: {self.df['timestamp'].min()} ~ {self.df['timestamp'].max()}")
            else:
                logger.warning(f"데이터 파일을 찾을 수 없습니다: {data_file}")
                logger.info("샘플 데이터를 생성합니다...")
                # 2024년 데이터 생성 (실제 API 연동 시 교체)
                self.df = self._generate_sample_data()
                logger.info(f"샘플 데이터 생성 완료: {len(self.df)}개 레코드")
            
            # 데이터 전처리
            self._preprocess_data()
            logger.info("데이터 전처리 완료")
            
        except Exception as e:
            logger.error(f"데이터 로드 실패: {e}")
            raise
    
    def load_training_data(self):
        """단일 연도 학습 데이터 로드"""
        try:
            if self.train_data_path and os.path.exists(self.train_data_path):
                self.train_df = pd.read_csv(self.train_data_path)
                logger.info(f"학습 데이터 로드 완료: {len(self.train_df)}개 레코드")
                logger.info(f"학습 데이터 기간: {self.train_df['timestamp'].min()} ~ {self.train_df['timestamp'].max()}")
                
                # 학습 데이터 전처리
                self._preprocess_training_data()
                logger.info("학습 데이터 전처리 완료")
            else:
                logger.warning("학습 데이터 파일을 찾을 수 없습니다.")
                
        except Exception as e:
            logger.error(f"학습 데이터 로드 실패: {e}")
            raise
    
    def load_multiple_years_training_data(self, data_paths):
        """다년도 학습 데이터 로드"""
        try:
            all_train_data = []
            
            for i, data_path in enumerate(data_paths):
                if os.path.exists(data_path):
                    year_data = pd.read_csv(data_path)
                    year_data['year'] = year_data['timestamp'].str[:4]
                    all_train_data.append(year_data)
                    logger.info(f"{data_path} 로드 완료: {len(year_data)}개 레코드")
                else:
                    logger.warning(f"데이터 파일을 찾을 수 없습니다: {data_path}")
            
            if all_train_data:
                # 모든 연도 데이터 합치기
                self.train_df = pd.concat(all_train_data, ignore_index=True)
                logger.info(f"다년도 학습 데이터 통합 완료: {len(self.train_df)}개 레코드")
                logger.info(f"학습 데이터 기간: {self.train_df['timestamp'].min()} ~ {self.train_df['timestamp'].max()}")
                
                # 학습 데이터 전처리
                self._preprocess_training_data()
                logger.info("다년도 학습 데이터 전처리 완료")
            else:
                logger.error("로드할 수 있는 학습 데이터가 없습니다.")
                
        except Exception as e:
            logger.error(f"다년도 학습 데이터 로드 실패: {e}")
            raise
    
    def _generate_sample_data(self):
        """2024년 비트코인 샘플 데이터 생성"""
        # 2024년 1월 1일부터 12월 31일까지 1시간 데이터
        start_date = dt.datetime(2024, 1, 1)
        end_date = dt.datetime(2024, 12, 31, 23, 59, 59)
        
        # 시간 인덱스 생성
        date_range = pd.date_range(start=start_date, end=end_date, freq='1H')
        
        # 기본 가격 설정 (2024년 비트코인 가격 범위 반영)
        base_price = 45000  # 2024년 초기 가격
        price_data = []
        current_price = base_price
        
        for i, timestamp in enumerate(date_range):
            # 트렌드와 변동성 반영
            trend = np.sin(i / (365 * 24) * 2 * np.pi) * 0.1  # 연간 사이클
            volatility = np.random.normal(0, 0.02)  # 2% 변동성
            momentum = np.random.normal(0, 0.001)  # 모멘텀
            
            # 가격 변화
            price_change = trend + volatility + momentum
            current_price *= (1 + price_change)
            
            # OHLC 데이터 생성
            high = current_price * (1 + abs(np.random.normal(0, 0.01)))
            low = current_price * (1 - abs(np.random.normal(0, 0.01)))
            open_price = current_price * (1 + np.random.normal(0, 0.005))
            close_price = current_price
            
            # 거래량 (가격 변동과 연관)
            volume = np.random.exponential(1000) * (1 + abs(price_change) * 10)
            
            price_data.append({
                'timestamp': timestamp,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close_price,
                'volume': volume
            })
        
        return pd.DataFrame(price_data)
    
    def _preprocess_data(self):
        """데이터 전처리"""
        if self.df is None:
            return
            
        # 타임스탬프를 datetime으로 변환
        if 'timestamp' in self.df.columns:
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
            self.df.set_index('timestamp', inplace=True)
        
        # 2024년 데이터만 필터링
        self.df = self.df[self.df.index.year == 2024]
        
        # 기술적 지표 계산
        self._calculate_technical_indicators()
        
        # 상승/하락 구간 분류
        self._classify_market_conditions()
    
    def _calculate_technical_indicators(self):
        """기술적 지표 계산"""
        # 이동평균선
        self.df['MA_5'] = self.df['close'].rolling(window=5).mean()
        self.df['MA_20'] = self.df['close'].rolling(window=20).mean()
        self.df['MA_50'] = self.df['close'].rolling(window=50).mean()
        self.df['MA_200'] = self.df['close'].rolling(window=200).mean()
        
        # RSI (14일)
        self.df['RSI'] = self._calculate_rsi(self.df['close'], 14)
        
        # 볼린저 밴드
        bb_period = 20
        bb_std = 2
        self.df['BB_middle'] = self.df['close'].rolling(window=bb_period).mean()
        bb_std_val = self.df['close'].rolling(window=bb_period).std()
        self.df['BB_upper'] = self.df['BB_middle'] + (bb_std_val * bb_std)
        self.df['BB_lower'] = self.df['BB_middle'] - (bb_std_val * bb_std)
        
        # MACD
        exp1 = self.df['close'].ewm(span=12).mean()
        exp2 = self.df['close'].ewm(span=26).mean()
        self.df['MACD'] = exp1 - exp2
        self.df['MACD_signal'] = self.df['MACD'].ewm(span=9).mean()
        self.df['MACD_histogram'] = self.df['MACD'] - self.df['MACD_signal']
        
        # 스토캐스틱
        self.df['Stoch_K'], self.df['Stoch_D'] = self._calculate_stochastic(14, 3, self.df)
        
        # 거래량 지표
        self.df['Volume_MA'] = self.df['volume'].rolling(window=20).mean()
        self.df['Volume_ratio'] = self.df['volume'] / self.df['Volume_MA']
        
        # 가격 변화율 (5분봉 기준)
        self.df['Price_change'] = self.df['close'].pct_change()
        self.df['Price_change_5m'] = self.df['close'].pct_change(1)  # 5분 변화율
        self.df['Price_change_1h'] = self.df['close'].pct_change(12)  # 1시간 변화율 (12 * 5분)
        self.df['Price_change_4h'] = self.df['close'].pct_change(48)  # 4시간 변화율 (48 * 5분)
        self.df['Price_change_24h'] = self.df['close'].pct_change(288)  # 24시간 변화율 (288 * 5분)
    
    def _calculate_rsi(self, prices, period=14):
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_stochastic(self, k_period=14, d_period=3, data=None):
        """스토캐스틱 계산"""
        if data is None:
            data = self.df
        low_min = data['low'].rolling(window=k_period).min()
        high_max = data['high'].rolling(window=k_period).max()
        k_percent = 100 * ((data['close'] - low_min) / (high_max - low_min))
        d_percent = k_percent.rolling(window=d_period).mean()
        return k_percent, d_percent
    
    def _classify_market_conditions(self):
        """시장 상황 분류"""
        # 상승/하락 구간 분류
        self.df['Price_trend'] = np.where(
            self.df['close'] > self.df['close'].shift(1), 1, -1
        )
        
        # 강한 상승/하락 구간 (5% 이상)
        self.df['Strong_up'] = np.where(
            self.df['Price_change_24h'] > 0.05, 1, 0
        )
        self.df['Strong_down'] = np.where(
            self.df['Price_change_24h'] < -0.05, 1, 0
        )
        
        # 지지/저항 레벨
        self.df['Support'] = self.df['low'].rolling(window=20).min()
        self.df['Resistance'] = self.df['high'].rolling(window=20).max()
        
        # 돌파 신호
        self.df['Breakout_up'] = np.where(
            (self.df['close'] > self.df['Resistance'].shift(1)) & 
            (self.df['close'].shift(1) <= self.df['Resistance'].shift(1)), 1, 0
        )
        self.df['Breakout_down'] = np.where(
            (self.df['close'] < self.df['Support'].shift(1)) & 
            (self.df['close'].shift(1) >= self.df['Support'].shift(1)), 1, 0
        )
    
    def _preprocess_training_data(self):
        """학습 데이터 전처리"""
        if self.train_df is None:
            return
            
        # 타임스탬프를 datetime으로 변환
        if 'timestamp' in self.train_df.columns:
            self.train_df['timestamp'] = pd.to_datetime(self.train_df['timestamp'])
            self.train_df.set_index('timestamp', inplace=True)
        
        # 2023년 데이터만 필터링
        self.train_df = self.train_df[self.train_df.index.year == 2023]
        
        # 기술적 지표 계산
        self._calculate_technical_indicators_for_training()
        
        # 상승/하락 구간 분류
        self._classify_market_conditions_for_training()
    
    def _calculate_technical_indicators_for_training(self):
        """학습 데이터용 기술적 지표 계산"""
        # 이동평균선
        self.train_df['MA_5'] = self.train_df['close'].rolling(window=5).mean()
        self.train_df['MA_20'] = self.train_df['close'].rolling(window=20).mean()
        self.train_df['MA_50'] = self.train_df['close'].rolling(window=50).mean()
        self.train_df['MA_200'] = self.train_df['close'].rolling(window=200).mean()
        
        # RSI (14일)
        self.train_df['RSI'] = self._calculate_rsi(self.train_df['close'], 14)
        
        # 볼린저 밴드
        bb_period = 20
        bb_std = 2
        self.train_df['BB_middle'] = self.train_df['close'].rolling(window=bb_period).mean()
        bb_std_val = self.train_df['close'].rolling(window=bb_period).std()
        self.train_df['BB_upper'] = self.train_df['BB_middle'] + (bb_std_val * bb_std)
        self.train_df['BB_lower'] = self.train_df['BB_middle'] - (bb_std_val * bb_std)
        
        # MACD
        exp1 = self.train_df['close'].ewm(span=12).mean()
        exp2 = self.train_df['close'].ewm(span=26).mean()
        self.train_df['MACD'] = exp1 - exp2
        self.train_df['MACD_signal'] = self.train_df['MACD'].ewm(span=9).mean()
        self.train_df['MACD_histogram'] = self.train_df['MACD'] - self.train_df['MACD_signal']
        
        # 스토캐스틱
        self.train_df['Stoch_K'], self.train_df['Stoch_D'] = self._calculate_stochastic(14, 3, self.train_df)
        
        # 거래량 지표
        self.train_df['Volume_MA'] = self.train_df['volume'].rolling(window=20).mean()
        self.train_df['Volume_ratio'] = self.train_df['volume'] / self.train_df['Volume_MA']
        
        # 가격 변화율 (5분봉 기준)
        self.train_df['Price_change'] = self.train_df['close'].pct_change()
        self.train_df['Price_change_5m'] = self.train_df['close'].pct_change(1)
        self.train_df['Price_change_1h'] = self.train_df['close'].pct_change(12)
        self.train_df['Price_change_4h'] = self.train_df['close'].pct_change(48)
        self.train_df['Price_change_24h'] = self.train_df['close'].pct_change(288)
    
    def _classify_market_conditions_for_training(self):
        """학습 데이터용 시장 상황 분류"""
        # 상승/하락 구간 분류
        self.train_df['Price_trend'] = np.where(
            self.train_df['close'] > self.train_df['close'].shift(1), 1, -1
        )
        
        # 강한 상승/하락 구간 (5% 이상)
        self.train_df['Strong_up'] = np.where(
            self.train_df['Price_change_24h'] > 0.05, 1, 0
        )
        self.train_df['Strong_down'] = np.where(
            self.train_df['Price_change_24h'] < -0.05, 1, 0
        )
        
        # 지지/저항 레벨
        self.train_df['Support'] = self.train_df['low'].rolling(window=20).min()
        self.train_df['Resistance'] = self.train_df['high'].rolling(window=20).max()
        
        # 돌파 신호
        self.train_df['Breakout_up'] = np.where(
            (self.train_df['close'] > self.train_df['Resistance'].shift(1)) & 
            (self.train_df['close'].shift(1) <= self.train_df['Resistance'].shift(1)), 1, 0
        )
        self.train_df['Breakout_down'] = np.where(
            (self.train_df['close'] < self.train_df['Support'].shift(1)) & 
            (self.train_df['close'].shift(1) >= self.train_df['Support'].shift(1)), 1, 0
        )
    
    def analyze_uptrend_conditions(self):
        """상승 조건 분석"""
        logger.info("상승 조건 분석 시작...")
        
        # 5분봉 데이터에 맞는 상승 구간 식별
        # 1시간 기준 1% 이상 상승 또는 4시간 기준 2% 이상 상승
        uptrend_mask = (self.df['Price_change_1h'] > 0.01) | (self.df['Price_change_4h'] > 0.02)
        uptrend_data = self.df[uptrend_mask].copy()
        
        if len(uptrend_data) == 0:
            logger.warning("상승 구간이 충분하지 않습니다.")
            return {}
        
        # 상승 조건 분석
        analysis = {}
        
        # 1. 기술적 지표 조건
        analysis['technical_conditions'] = {
            'rsi_oversold': len(uptrend_data[uptrend_data['RSI'] < 30]) / len(uptrend_data),
            'rsi_overbought': len(uptrend_data[uptrend_data['RSI'] > 70]) / len(uptrend_data),
            'ma_golden_cross': len(uptrend_data[uptrend_data['MA_5'] > uptrend_data['MA_20']]) / len(uptrend_data),
            'macd_bullish': len(uptrend_data[uptrend_data['MACD'] > uptrend_data['MACD_signal']]) / len(uptrend_data),
            'stoch_oversold': len(uptrend_data[uptrend_data['Stoch_K'] < 20]) / len(uptrend_data)
        }
        
        # 2. 거래량 조건
        analysis['volume_conditions'] = {
            'high_volume': len(uptrend_data[uptrend_data['Volume_ratio'] > 1.5]) / len(uptrend_data),
            'avg_volume_ratio': uptrend_data['Volume_ratio'].mean(),
            'volume_trend': uptrend_data['Volume_ratio'].corr(uptrend_data['Price_change_24h'])
        }
        
        # 3. 가격 패턴 조건
        analysis['price_patterns'] = {
            'breakout_frequency': uptrend_data['Breakout_up'].sum() / len(uptrend_data),
            'support_bounce': len(uptrend_data[
                (uptrend_data['close'] > uptrend_data['Support'] * 1.01) &
                (uptrend_data['close'].shift(1) <= uptrend_data['Support'].shift(1) * 1.01)
            ]) / len(uptrend_data),
            'resistance_break': len(uptrend_data[
                (uptrend_data['close'] > uptrend_data['Resistance'].shift(1)) &
                (uptrend_data['close'].shift(1) <= uptrend_data['Resistance'].shift(1))
            ]) / len(uptrend_data)
        }
        
        # 4. 시간대별 상승 패턴 (5분봉 기준)
        uptrend_data['hour'] = uptrend_data.index.hour
        hourly_analysis = uptrend_data.groupby('hour').agg({
            'Price_change_1h': ['count', 'mean', 'std'],
            'Price_change_4h': ['count', 'mean', 'std'],
            'Volume_ratio': 'mean',
            'RSI': 'mean'
        }).round(4)
        
        analysis['hourly_patterns'] = hourly_analysis
        
        # 5. 상관관계 분석 (5분봉 기준)
        correlation_analysis = uptrend_data[[
            'RSI', 'MACD', 'Stoch_K', 'Volume_ratio', 'Price_change_1h', 'Price_change_4h'
        ]].corr()
        
        analysis['correlations'] = correlation_analysis['Price_change_1h'].drop('Price_change_1h')
        
        self.analysis_results = analysis
        logger.info("상승 조건 분석 완료")
        
        return analysis
    
    def train_ml_models(self):
        """2023년 데이터로 머신러닝 모델 학습"""
        if self.train_df is None:
            logger.error("학습 데이터가 없습니다. 먼저 load_training_data()를 실행하세요.")
            return
        
        logger.info("머신러닝 모델 학습 시작...")
        
        # 특성 선택 (상승 예측을 위한 지표들)
        feature_columns = [
            'RSI', 'MACD', 'MACD_signal', 'MACD_histogram', 'Stoch_K', 'Stoch_D',
            'Volume_ratio', 'Price_change_5m', 'Price_change_1h', 'Price_change_4h',
            'MA_5', 'MA_20', 'MA_50', 'BB_upper', 'BB_lower', 'BB_middle',
            'Breakout_up', 'Breakout_down'
        ]
        
        # 타겟 변수 생성 (1시간 후 상승 여부)
        self.train_df['target'] = np.where(
            self.train_df['Price_change_1h'].shift(-12) > 0.01, 1, 0  # 1시간 후 1% 이상 상승
        )
        
        # 결측값 제거
        train_data = self.train_df[feature_columns + ['target']].dropna()
        
        if len(train_data) == 0:
            logger.error("학습할 데이터가 없습니다.")
            return
        
        X = train_data[feature_columns]
        y = train_data['target']
        
        # 데이터 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # 데이터 정규화
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # 모델 학습
        models = {
            'RandomForest': RandomForestClassifier(n_estimators=100, random_state=42),
            'GradientBoosting': GradientBoostingClassifier(n_estimators=100, random_state=42)
        }
        
        # XGBoost가 사용 가능한 경우에만 추가
        if XGBOOST_AVAILABLE:
            models['XGBoost'] = xgb.XGBClassifier(n_estimators=100, random_state=42)
        
        model_results = {}
        
        for name, model in models.items():
            logger.info(f"{name} 모델 학습 중...")
            
            # 모델 학습
            if name == 'XGBoost':
                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)
                y_pred_proba = model.predict_proba(X_test)[:, 1]
            else:
                model.fit(X_train_scaled, y_train)
                y_pred = model.predict(X_test_scaled)
                y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
            
            # 성능 평가
            accuracy = accuracy_score(y_test, y_pred)
            cross_val_scores = cross_val_score(model, X_train_scaled if name != 'XGBoost' else X_train, 
                                             y_train, cv=5, scoring='accuracy')
            
            model_results[name] = {
                'model': model,
                'accuracy': accuracy,
                'cv_mean': cross_val_scores.mean(),
                'cv_std': cross_val_scores.std(),
                'predictions': y_pred,
                'probabilities': y_pred_proba
            }
            
            logger.info(f"{name} - 정확도: {accuracy:.4f}, CV 평균: {cross_val_scores.mean():.4f} ± {cross_val_scores.std():.4f}")
        
        # 최고 성능 모델 선택
        best_model_name = max(model_results.keys(), key=lambda x: model_results[x]['accuracy'])
        self.ml_models = model_results
        
        logger.info(f"최고 성능 모델: {best_model_name} (정확도: {model_results[best_model_name]['accuracy']:.4f})")
        
        # 특성 중요도 분석
        if best_model_name in ['RandomForest', 'GradientBoosting']:
            feature_importance = pd.DataFrame({
                'feature': feature_columns,
                'importance': model_results[best_model_name]['model'].feature_importances_
            }).sort_values('importance', ascending=False)
            
            logger.info("특성 중요도 (상위 10개):")
            for idx, row in feature_importance.head(10).iterrows():
                logger.info(f"  {row['feature']}: {row['importance']:.4f}")
        
        return model_results
    
    def test_on_2024_data(self):
        """2024년 데이터로 모델 테스트"""
        if not self.ml_models:
            logger.error("학습된 모델이 없습니다. 먼저 train_ml_models()를 실행하세요.")
            return
        
        if self.df is None:
            logger.error("2024년 테스트 데이터가 없습니다. 먼저 load_data()를 실행하세요.")
            return
        
        logger.info("2024년 데이터로 모델 테스트 시작...")
        
        # 특성 선택 (학습과 동일)
        feature_columns = [
            'RSI', 'MACD', 'MACD_signal', 'MACD_histogram', 'Stoch_K', 'Stoch_D',
            'Volume_ratio', 'Price_change_5m', 'Price_change_1h', 'Price_change_4h',
            'MA_5', 'MA_20', 'MA_50', 'BB_upper', 'BB_lower', 'BB_middle',
            'Breakout_up', 'Breakout_down'
        ]
        
        # 실제 타겟 생성 (1시간 후 상승 여부)
        self.df['actual_target'] = np.where(
            self.df['Price_change_1h'].shift(-12) > 0.01, 1, 0
        )
        
        # 결측값 제거
        test_data = self.df[feature_columns + ['actual_target']].dropna()
        
        if len(test_data) == 0:
            logger.error("테스트할 데이터가 없습니다.")
            return
        
        X_test = test_data[feature_columns]
        y_actual = test_data['actual_target']
        
        test_results = {}
        
        for model_name, model_info in self.ml_models.items():
            model = model_info['model']
            
            # 예측 수행
            if model_name == 'XGBoost':
                y_pred = model.predict(X_test)
                y_pred_proba = model.predict_proba(X_test)[:, 1]
            else:
                X_test_scaled = self.scaler.transform(X_test)
                y_pred = model.predict(X_test_scaled)
                y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
            
            # 성능 평가
            accuracy = accuracy_score(y_actual, y_pred)
            
            test_results[model_name] = {
                'accuracy': accuracy,
                'predictions': y_pred,
                'probabilities': y_pred_proba,
                'actual': y_actual
            }
            
            logger.info(f"{model_name} 2024년 테스트 정확도: {accuracy:.4f}")
        
        # 백테스팅 결과 계산
        self._calculate_backtest_results(test_results)
        
        return test_results
    
    def _calculate_backtest_results(self, test_results):
        """백테스팅 결과 계산"""
        logger.info("백테스팅 결과 계산 중...")
        
        # 실제 상승 구간 식별
        actual_uptrend = self.df['actual_target'] == 1
        uptrend_count = actual_uptrend.sum()
        total_count = len(self.df.dropna())
        
        logger.info(f"2024년 실제 상승 구간: {uptrend_count}개 / {total_count}개 ({uptrend_count/total_count:.2%})")
        
        # 각 모델별 성능 분석
        for model_name, results in test_results.items():
            predictions = results['predictions']
            probabilities = results['probabilities']
            actual = results['actual']
            
            # 예측 상승 구간
            predicted_uptrend = predictions == 1
            predicted_count = predicted_uptrend.sum()
            
            # 정확도 분석
            true_positives = ((predictions == 1) & (actual == 1)).sum()
            false_positives = ((predictions == 1) & (actual == 0)).sum()
            false_negatives = ((predictions == 0) & (actual == 1)).sum()
            true_negatives = ((predictions == 0) & (actual == 0)).sum()
            
            precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
            recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
            f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            logger.info(f"\n{model_name} 상세 성능:")
            logger.info(f"  예측 상승 구간: {predicted_count}개")
            logger.info(f"  정밀도: {precision:.4f}")
            logger.info(f"  재현율: {recall:.4f}")
            logger.info(f"  F1 점수: {f1_score:.4f}")
        
        return test_results
    
    def analyze_overfitting_risk(self):
        """과적화 위험 분석"""
        if not self.ml_models or self.train_df is None:
            logger.error("학습된 모델이나 학습 데이터가 없습니다.")
            return
        
        logger.info("과적화 위험 분석 시작...")
        
        # 1. 학습 데이터 크기 분석
        train_size = len(self.train_df)
        test_size = len(self.df) if self.df is not None else 0
        
        logger.info(f"학습 데이터 크기: {train_size:,}개")
        logger.info(f"테스트 데이터 크기: {test_size:,}개")
        logger.info(f"학습/테스트 비율: {train_size/test_size:.2f}:1")
        
        # 2. 연도별 데이터 분포 분석
        if 'year' in self.train_df.columns:
            year_distribution = self.train_df['year'].value_counts().sort_index()
            logger.info("연도별 학습 데이터 분포:")
            for year, count in year_distribution.items():
                logger.info(f"  {year}년: {count:,}개 ({count/train_size:.1%})")
        
        # 3. 상승 구간 비율 분석
        if 'target' in self.train_df.columns:
            train_uptrend_ratio = self.train_df['target'].mean()
            logger.info(f"학습 데이터 상승 구간 비율: {train_uptrend_ratio:.2%}")
            
            if self.df is not None and 'actual_target' in self.df.columns:
                test_uptrend_ratio = self.df['actual_target'].mean()
                logger.info(f"테스트 데이터 상승 구간 비율: {test_uptrend_ratio:.2%}")
                
                # 분포 차이 분석
                distribution_diff = abs(train_uptrend_ratio - test_uptrend_ratio)
                logger.info(f"상승 구간 비율 차이: {distribution_diff:.2%}")
                
                if distribution_diff > 0.05:  # 5% 이상 차이
                    logger.warning("⚠️ 학습과 테스트 데이터의 상승 구간 비율이 크게 다릅니다!")
                    logger.warning("   이는 시장 환경 변화나 데이터 편향을 의미할 수 있습니다.")
        
        # 4. 모델 복잡도 분석
        for model_name, model_info in self.ml_models.items():
            model = model_info['model']
            
            if hasattr(model, 'n_estimators'):
                logger.info(f"{model_name} 트리 개수: {model.n_estimators}")
            if hasattr(model, 'max_depth'):
                logger.info(f"{model_name} 최대 깊이: {model.max_depth}")
            if hasattr(model, 'max_features'):
                logger.info(f"{model_name} 최대 특성 수: {model.max_features}")
        
        # 5. 교차 검증 성능 vs 테스트 성능 비교
        if self.ml_models:
            logger.info("\n과적화 검증 - 학습 vs 테스트 성능 비교:")
            for model_name, model_info in self.ml_models.items():
                train_cv_score = model_info.get('cv_mean', 0)
                test_accuracy = model_info.get('accuracy', 0)
                
                performance_gap = train_cv_score - test_accuracy
                logger.info(f"{model_name}:")
                logger.info(f"  학습 CV 점수: {train_cv_score:.4f}")
                logger.info(f"  테스트 정확도: {test_accuracy:.4f}")
                logger.info(f"  성능 차이: {performance_gap:.4f}")
                
                if performance_gap > 0.05:  # 5% 이상 차이
                    logger.warning(f"  ⚠️ {model_name}에서 과적화 징후 발견!")
                    logger.warning(f"     학습 성능이 테스트 성능보다 {performance_gap:.1%} 높습니다.")
                elif performance_gap < -0.02:  # -2% 이하 차이
                    logger.info(f"  ✅ {model_name}는 일반화가 잘 되고 있습니다.")
                else:
                    logger.info(f"  ✅ {model_name}는 적절한 성능을 보입니다.")
        
        logger.info("과적화 위험 분석 완료")
    
    def save_models(self, save_dir="models"):
        """학습된 모델들을 파일로 저장"""
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        for model_name, model_info in self.ml_models.items():
            # 모델 저장
            model_path = os.path.join(save_dir, f"{model_name}_model.pkl")
            with open(model_path, 'wb') as f:
                pickle.dump(model_info['model'], f)
            
            # 스케일러 저장 (XGBoost 제외)
            if model_name != 'XGBoost':
                scaler_path = os.path.join(save_dir, f"{model_name}_scaler.pkl")
                with open(scaler_path, 'wb') as f:
                    pickle.dump(self.scaler, f)
            
            # 모델 메타데이터 저장
            metadata = {
                'model_name': model_name,
                'accuracy': model_info['accuracy'],
                'cv_mean': model_info['cv_mean'],
                'cv_std': model_info['cv_std'],
                'feature_columns': [
                    'RSI', 'MACD', 'MACD_signal', 'MACD_histogram', 'Stoch_K', 'Stoch_D',
                    'Volume_ratio', 'Price_change_5m', 'Price_change_1h', 'Price_change_4h',
                    'MA_5', 'MA_20', 'MA_50', 'BB_upper', 'BB_lower', 'BB_middle',
                    'Breakout_up', 'Breakout_down'
                ],
                'target_threshold': 0.01,  # 1% 상승 임계값
                'prediction_horizon': 12  # 1시간 후 예측 (12 * 5분)
            }
            
            metadata_path = os.path.join(save_dir, f"{model_name}_metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"{model_name} 모델 저장 완료: {model_path}")
    
    def load_models(self, save_dir="models"):
        """저장된 모델들을 로드"""
        loaded_models = {}
        
        for model_name in ['RandomForest', 'GradientBoosting', 'XGBoost']:
            model_path = os.path.join(save_dir, f"{model_name}_model.pkl")
            metadata_path = os.path.join(save_dir, f"{model_name}_metadata.json")
            
            if os.path.exists(model_path) and os.path.exists(metadata_path):
                # 모델 로드
                with open(model_path, 'rb') as f:
                    model = pickle.load(f)
                
                # 메타데이터 로드
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                # 스케일러 로드 (XGBoost 제외)
                scaler = None
                if model_name != 'XGBoost':
                    scaler_path = os.path.join(save_dir, f"{model_name}_scaler.pkl")
                    if os.path.exists(scaler_path):
                        with open(scaler_path, 'rb') as f:
                            scaler = pickle.load(f)
                
                loaded_models[model_name] = {
                    'model': model,
                    'scaler': scaler,
                    'metadata': metadata
                }
                
                logger.info(f"{model_name} 모델 로드 완료")
        
        return loaded_models
    
    def create_ensemble_model(self, individual_models):
        """개별 모델들을 앙상블로 조합"""
        class EnsembleModel:
            def __init__(self, models, weights=None):
                self.models = models
                self.weights = weights or [1.0] * len(models)
                self.weights = np.array(self.weights) / sum(self.weights)
            
            def predict_proba(self, X):
                predictions = []
                for i, (model_name, model_info) in enumerate(self.models.items()):
                    model = model_info['model']
                    scaler = model_info.get('scaler')
                    
                    if model_name == 'XGBoost':
                        pred = model.predict_proba(X)
                    else:
                        if scaler:
                            X_scaled = scaler.transform(X)
                        else:
                            X_scaled = X
                        pred = model.predict_proba(X_scaled)
                    
                    predictions.append(pred * self.weights[i])
                
                return np.sum(predictions, axis=0)
            
            def predict(self, X):
                proba = self.predict_proba(X)
                return (proba[:, 1] > 0.5).astype(int)
        
        return EnsembleModel(individual_models)
    
    def backtest_trading(self, initial_balance=10000, commission_rate=0.0005):
        """실제 백테스팅 거래 시뮬레이션"""
        logger.info("백테스팅 거래 시뮬레이션 시작...")
        
        if not self.ml_models:
            logger.error("학습된 모델이 없습니다.")
            return
        
        # 거래 시뮬레이션 변수
        balance = initial_balance
        position = 0  # 보유 수량
        position_value = 0  # 포지션 가치
        trades = []
        equity_curve = []
        
        # 트레일링 스탑 설정
        trailing_stop_activation = 0.003  # 0.3% 수익 달성시 트레일링 스탑 활성화
        trailing_stop_distance = 0.002   # 0.2% 트레일링 스탑 거리
        highest_price = 0
        
        # 특성 컬럼
        feature_columns = [
            'RSI', 'MACD', 'MACD_signal', 'MACD_histogram', 'Stoch_K', 'Stoch_D',
            'Volume_ratio', 'Price_change_5m', 'Price_change_1h', 'Price_change_4h',
            'MA_5', 'MA_20', 'MA_50', 'BB_upper', 'BB_lower', 'BB_middle',
            'Breakout_up', 'Breakout_down'
        ]
        
        # 앙상블 모델 생성
        ensemble_model = self.create_ensemble_model(self.ml_models)
        
        for i, (timestamp, row) in enumerate(self.df.iterrows()):
            current_price = row['close']
            
            # 트레일링 스탑 체크
            if position > 0:
                if current_price > highest_price:
                    highest_price = current_price
                
                # 트레일링 스탑 활성화 조건
                profit_rate = (current_price - position_value / position) / (position_value / position)
                if profit_rate > trailing_stop_activation:
                    # 트레일링 스탑 체크
                    if current_price < highest_price * (1 - trailing_stop_distance):
                        # 매도 실행
                        sell_price = current_price * (1 - commission_rate)
                        balance += position * sell_price
                        
                        trades.append({
                            'timestamp': timestamp,
                            'action': 'SELL',
                            'price': sell_price,
                            'quantity': position,
                            'balance': balance,
                            'reason': 'Trailing Stop'
                        })
                        
                        position = 0
                        position_value = 0
                        highest_price = 0
            
            # 모델 예측 (충분한 데이터가 있을 때만)
            if i >= 200:  # 200개 데이터 이후부터 예측
                try:
                    # 특성 데이터 준비
                    features = row[feature_columns].values.reshape(1, -1)
                    
                    # 앙상블 모델 예측
                    prediction = ensemble_model.predict(features)[0]
                    probability = ensemble_model.predict_proba(features)[0][1]
                    
                    # 매수 신호 (예측이 상승이고 확률이 0.6 이상)
                    if prediction == 1 and probability > 0.6 and position == 0:
                        # 매수 실행
                        buy_price = current_price * (1 + commission_rate)
                        position = balance * 0.1 / buy_price  # 10% 자본으로 매수
                        position_value = position * buy_price
                        balance -= position_value
                        highest_price = current_price
                        
                        trades.append({
                            'timestamp': timestamp,
                            'action': 'BUY',
                            'price': buy_price,
                            'quantity': position,
                            'balance': balance,
                            'probability': probability
                        })
                    
                    # 매도 신호 (예측이 하락이고 확률이 0.4 이하)
                    elif prediction == 0 and probability < 0.4 and position > 0:
                        # 매도 실행
                        sell_price = current_price * (1 - commission_rate)
                        balance += position * sell_price
                        
                        trades.append({
                            'timestamp': timestamp,
                            'action': 'SELL',
                            'price': sell_price,
                            'quantity': position,
                            'balance': balance,
                            'probability': probability
                        })
                        
                        position = 0
                        position_value = 0
                        highest_price = 0
                
                except Exception as e:
                    logger.warning(f"예측 오류 at {timestamp}: {e}")
                    continue
            
            # 현재 자산 가치 계산
            current_equity = balance + (position * current_price if position > 0 else 0)
            equity_curve.append({
                'timestamp': timestamp,
                'balance': balance,
                'position': position,
                'position_value': position * current_price if position > 0 else 0,
                'total_equity': current_equity,
                'price': current_price
            })
        
        # 최종 정리 (포지션이 남아있으면 마지막 가격으로 매도)
        if position > 0:
            final_price = self.df['close'].iloc[-1]
            sell_price = final_price * (1 - commission_rate)
            balance += position * sell_price
            
            trades.append({
                'timestamp': self.df.index[-1],
                'action': 'SELL',
                'price': sell_price,
                'quantity': position,
                'balance': balance,
                'reason': 'Final Close'
            })
        
        # 백테스팅 결과 계산
        final_balance = balance
        total_return = (final_balance - initial_balance) / initial_balance
        
        # 거래 통계
        buy_trades = [t for t in trades if t['action'] == 'BUY']
        sell_trades = [t for t in trades if t['action'] == 'SELL']
        
        # 수익성 거래 계산
        profitable_trades = 0
        total_trades = min(len(buy_trades), len(sell_trades))
        
        for i in range(total_trades):
            buy_price = buy_trades[i]['price']
            sell_price = sell_trades[i]['price']
            if sell_price > buy_price:
                profitable_trades += 1
        
        win_rate = profitable_trades / total_trades if total_trades > 0 else 0
        
        # 결과 저장
        backtest_results = {
            'initial_balance': initial_balance,
            'final_balance': final_balance,
            'total_return': total_return,
            'total_trades': total_trades,
            'profitable_trades': profitable_trades,
            'win_rate': win_rate,
            'trades': trades,
            'equity_curve': equity_curve
        }
        
        logger.info(f"백테스팅 완료:")
        logger.info(f"  초기 자본: ${initial_balance:,.2f}")
        logger.info(f"  최종 자본: ${final_balance:,.2f}")
        logger.info(f"  총 수익률: {total_return:.2%}")
        logger.info(f"  총 거래 횟수: {total_trades}")
        logger.info(f"  수익 거래: {profitable_trades}")
        logger.info(f"  승률: {win_rate:.2%}")
        
        return backtest_results
    
    def create_visualizations(self):
        """시각화 생성"""
        logger.info("시각화 생성 시작...")
        
        # 그래프 스타일 설정
        plt.style.use('seaborn-v0_8')
        fig = plt.figure(figsize=(20, 24))
        
        # 1. 가격 차트 (메인)
        ax1 = plt.subplot(4, 2, 1)
        ax1.plot(self.df.index, self.df['close'], label='BTC Price', linewidth=1, alpha=0.8)
        ax1.plot(self.df.index, self.df['MA_20'], label='MA 20', alpha=0.7)
        ax1.plot(self.df.index, self.df['MA_50'], label='MA 50', alpha=0.7)
        ax1.plot(self.df.index, self.df['MA_200'], label='MA 200', alpha=0.7)
        
        # 상승 구간 하이라이트 (5분봉 기준)
        uptrend_mask = (self.df['Price_change_1h'] > 0.01) | (self.df['Price_change_4h'] > 0.02)
        ax1.scatter(self.df[uptrend_mask].index, self.df[uptrend_mask]['close'], 
                   color='red', alpha=0.6, s=5, label='Strong Uptrend')
        
        ax1.set_title('Bitcoin Price 2024 with Moving Averages', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Price (USDT)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. RSI 차트
        ax2 = plt.subplot(4, 2, 2)
        ax2.plot(self.df.index, self.df['RSI'], label='RSI', color='purple', linewidth=1)
        ax2.axhline(y=70, color='r', linestyle='--', alpha=0.7, label='Overbought')
        ax2.axhline(y=30, color='g', linestyle='--', alpha=0.7, label='Oversold')
        ax2.fill_between(self.df.index, 30, 70, alpha=0.1, color='gray')
        ax2.set_title('RSI (14) - Momentum Indicator', fontsize=14, fontweight='bold')
        ax2.set_ylabel('RSI')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. MACD 차트
        ax3 = plt.subplot(4, 2, 3)
        ax3.plot(self.df.index, self.df['MACD'], label='MACD', color='blue', linewidth=1)
        ax3.plot(self.df.index, self.df['MACD_signal'], label='Signal', color='red', linewidth=1)
        ax3.bar(self.df.index, self.df['MACD_histogram'], label='Histogram', alpha=0.6, width=0.8)
        ax3.set_title('MACD - Trend Following', fontsize=14, fontweight='bold')
        ax3.set_ylabel('MACD')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 4. 볼린저 밴드
        ax4 = plt.subplot(4, 2, 4)
        ax4.plot(self.df.index, self.df['close'], label='Price', linewidth=1)
        ax4.plot(self.df.index, self.df['BB_upper'], label='BB Upper', color='red', alpha=0.7)
        ax4.plot(self.df.index, self.df['BB_middle'], label='BB Middle', color='orange', alpha=0.7)
        ax4.plot(self.df.index, self.df['BB_lower'], label='BB Lower', color='green', alpha=0.7)
        ax4.fill_between(self.df.index, self.df['BB_lower'], self.df['BB_upper'], alpha=0.1, color='gray')
        ax4.set_title('Bollinger Bands - Volatility', fontsize=14, fontweight='bold')
        ax4.set_ylabel('Price (USDT)')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        # 5. 거래량 차트
        ax5 = plt.subplot(4, 2, 5)
        ax5.bar(self.df.index, self.df['volume'], alpha=0.6, width=0.8, color='orange')
        ax5.plot(self.df.index, self.df['Volume_MA'], color='red', linewidth=2, label='Volume MA')
        ax5.set_title('Trading Volume', fontsize=14, fontweight='bold')
        ax5.set_ylabel('Volume')
        ax5.legend()
        ax5.grid(True, alpha=0.3)
        
        # 6. 가격 변화율 히스토그램 (5분봉 기준)
        ax6 = plt.subplot(4, 2, 6)
        price_changes = self.df['Price_change_1h'].dropna()
        ax6.hist(price_changes, bins=50, alpha=0.7, color='skyblue', edgecolor='black')
        ax6.axvline(price_changes.mean(), color='red', linestyle='--', label=f'Mean: {price_changes.mean():.4f}')
        ax6.axvline(0.01, color='green', linestyle='--', label='1% Threshold')
        ax6.set_title('1h Price Change Distribution (5m bars)', fontsize=14, fontweight='bold')
        ax6.set_xlabel('Price Change (%)')
        ax6.set_ylabel('Frequency')
        ax6.legend()
        ax6.grid(True, alpha=0.3)
        
        # 7. 시간대별 상승 패턴 (5분봉 기준)
        if 'hourly_patterns' in self.analysis_results:
            ax7 = plt.subplot(4, 2, 7)
            hourly_data = self.analysis_results['hourly_patterns']
            hours = range(24)
            avg_changes = [hourly_data.loc[h, ('Price_change_1h', 'mean')] if h in hourly_data.index else 0 for h in hours]
            ax7.bar(hours, avg_changes, alpha=0.7, color='lightcoral')
            ax7.set_title('Average 1h Price Change by Hour (5m bars)', fontsize=14, fontweight='bold')
            ax7.set_xlabel('Hour of Day')
            ax7.set_ylabel('Avg Price Change (%)')
            ax7.grid(True, alpha=0.3)
        
        # 8. 상관관계 히트맵
        ax8 = plt.subplot(4, 2, 8)
        if 'correlations' in self.analysis_results:
            corr_data = self.analysis_results['correlations'].to_frame()
            sns.heatmap(corr_data, annot=True, cmap='RdYlBu_r', center=0, ax=ax8)
            ax8.set_title('Correlation with Price Change', fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        plt.show()
        
        logger.info("시각화 생성 완료")
    
    def create_backtest_visualizations(self, backtest_results):
        """백테스팅 결과 시각화"""
        if not backtest_results:
            logger.warning("백테스팅 결과가 없습니다.")
            return
        
        logger.info("백테스팅 결과 시각화 생성 중...")
        
        # 백테스팅 결과 데이터 준비
        equity_df = pd.DataFrame(backtest_results['equity_curve'])
        equity_df['timestamp'] = pd.to_datetime(equity_df['timestamp'])
        equity_df.set_index('timestamp', inplace=True)
        
        # 거래 데이터 준비
        trades_df = pd.DataFrame(backtest_results['trades'])
        if not trades_df.empty:
            trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
            buy_trades = trades_df[trades_df['action'] == 'BUY']
            sell_trades = trades_df[trades_df['action'] == 'SELL']
        
        # 그래프 생성
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Bitcoin 2024 Backtesting Results', fontsize=16, fontweight='bold')
        
        # 1. 가격 차트와 거래 신호
        ax1 = axes[0, 0]
        ax1.plot(equity_df.index, equity_df['price'], label='BTC Price', linewidth=1, alpha=0.8)
        
        if not buy_trades.empty:
            ax1.scatter(buy_trades['timestamp'], buy_trades['price'], 
                       color='green', marker='^', s=50, label='Buy Signals', alpha=0.7)
        if not sell_trades.empty:
            ax1.scatter(sell_trades['timestamp'], sell_trades['price'], 
                       color='red', marker='v', s=50, label='Sell Signals', alpha=0.7)
        
        ax1.set_title('Price Chart with Trading Signals')
        ax1.set_ylabel('Price (USDT)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. 자산 가치 변화
        ax2 = axes[0, 1]
        ax2.plot(equity_df.index, equity_df['total_equity'], 
                label='Total Equity', linewidth=2, color='blue')
        ax2.plot(equity_df.index, equity_df['balance'], 
                label='Cash Balance', linewidth=1, color='orange', alpha=0.7)
        ax2.plot(equity_df.index, equity_df['position_value'], 
                label='Position Value', linewidth=1, color='green', alpha=0.7)
        
        ax2.set_title('Portfolio Value Over Time')
        ax2.set_ylabel('Value (USDT)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. 수익률 차트
        ax3 = axes[1, 0]
        initial_balance = backtest_results['initial_balance']
        returns = (equity_df['total_equity'] - initial_balance) / initial_balance * 100
        ax3.plot(equity_df.index, returns, linewidth=2, color='purple')
        ax3.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        
        ax3.set_title('Cumulative Returns (%)')
        ax3.set_ylabel('Returns (%)')
        ax3.grid(True, alpha=0.3)
        
        # 4. 거래 통계
        ax4 = axes[1, 1]
        stats_data = {
            'Total Return': f"{backtest_results['total_return']:.2%}",
            'Total Trades': backtest_results['total_trades'],
            'Win Rate': f"{backtest_results['win_rate']:.2%}",
            'Final Balance': f"${backtest_results['final_balance']:,.2f}"
        }
        
        y_pos = np.arange(len(stats_data))
        ax4.barh(y_pos, [1, 1, 1, 1], alpha=0.3)
        ax4.set_yticks(y_pos)
        ax4.set_yticklabels(list(stats_data.keys()))
        
        # 통계 값 표시
        for i, (key, value) in enumerate(stats_data.items()):
            ax4.text(0.5, i, value, ha='center', va='center', fontweight='bold')
        
        ax4.set_title('Trading Statistics')
        ax4.set_xlim(0, 1)
        ax4.set_xticks([])
        
        plt.tight_layout()
        plt.show()
        
        logger.info("백테스팅 시각화 완료")
    
    def print_analysis_summary(self):
        """분석 결과 요약 출력"""
        if not self.analysis_results:
            logger.warning("분석 결과가 없습니다. 먼저 analyze_uptrend_conditions()를 실행하세요.")
            return
        
        print("\n" + "="*60)
        print("비트코인 2024년 상승 조건 분석 결과")
        print("="*60)
        
        # 기술적 지표 조건
        tech_conditions = self.analysis_results.get('technical_conditions', {})
        print("\n📊 기술적 지표 조건:")
        print(f"  • RSI 과매도 구간에서 상승: {tech_conditions.get('rsi_oversold', 0):.1%}")
        print(f"  • RSI 과매수 구간에서 상승: {tech_conditions.get('rsi_overbought', 0):.1%}")
        print(f"  • 골든크로스 (MA5 > MA20): {tech_conditions.get('ma_golden_cross', 0):.1%}")
        print(f"  • MACD 상승 신호: {tech_conditions.get('macd_bullish', 0):.1%}")
        print(f"  • 스토캐스틱 과매도: {tech_conditions.get('stoch_oversold', 0):.1%}")
        
        # 거래량 조건
        volume_conditions = self.analysis_results.get('volume_conditions', {})
        print("\n📈 거래량 조건:")
        print(f"  • 고거래량 상승: {volume_conditions.get('high_volume', 0):.1%}")
        print(f"  • 평균 거래량 비율: {volume_conditions.get('avg_volume_ratio', 0):.2f}")
        print(f"  • 거래량-가격 상관관계: {volume_conditions.get('volume_trend', 0):.3f}")
        
        # 가격 패턴 조건
        price_patterns = self.analysis_results.get('price_patterns', {})
        print("\n🎯 가격 패턴 조건:")
        print(f"  • 저항선 돌파 빈도: {price_patterns.get('breakout_frequency', 0):.1%}")
        print(f"  • 지지선 바운스: {price_patterns.get('support_bounce', 0):.1%}")
        print(f"  • 저항선 돌파: {price_patterns.get('resistance_break', 0):.1%}")
        
        # 상관관계 분석
        correlations = self.analysis_results.get('correlations', {})
        print("\n🔗 지표별 상관관계 (가격 변화율 기준):")
        for indicator, corr in correlations.items():
            print(f"  • {indicator}: {corr:.3f}")
        
        print("\n" + "="*60)
        print("분석 완료! 그래프를 확인하여 패턴을 시각적으로 확인하세요.")
        print("="*60)

def main():
    """메인 실행 함수"""
    print("비트코인 다년도 학습 → 2024년 테스트 분석 시작...")
    
    # 데이터 파일 경로 설정 (여러 연도)
    train_data_paths = [
        "C:/work/GitHub/py/kook/binance_test/data/BTCUSDT/5m/BTCUSDT_5m_2023.csv",
        "C:/work/GitHub/py/kook/binance_test/data/BTCUSDT/5m/BTCUSDT_5m_2022.csv",
        "C:/work/GitHub/py/kook/binance_test/data/BTCUSDT/5m/BTCUSDT_5m_2021.csv"
    ]
    test_data_path = "C:/work/GitHub/py/kook/binance_test/data/BTCUSDT/5m/BTCUSDT_5m_2024.csv"
    
    # 분석기 초기화
    analyzer = Bitcoin2024Analyzer(data_path=test_data_path)
    
    try:
        # 1. 다년도 학습 데이터 로드
        print("\n[1] 다년도 학습 데이터 로드 중...")
        analyzer.load_multiple_years_training_data(train_data_paths)
        
        # 2. 2024년 테스트 데이터 로드
        print("\n[2] 2024년 테스트 데이터 로드 중...")
        analyzer.load_data()
        
        # 3. 머신러닝 모델 학습
        print("\n[3] 머신러닝 모델 학습 중...")
        train_results = analyzer.train_ml_models()
        
        # 4. 2024년 데이터로 모델 테스트
        print("\n[4] 2024년 데이터로 모델 테스트 중...")
        test_results = analyzer.test_on_2024_data()
        
        # 5. 과적화 위험 분석
        print("\n[5] 과적화 위험 분석 중...")
        analyzer.analyze_overfitting_risk()
        
        # 6. 상승 조건 분석
        print("\n[6] 상승 조건 분석 중...")
        analysis_results = analyzer.analyze_uptrend_conditions()
        
        # 7. 시각화 생성
        print("\n[7] 시각화 생성 중...")
        analyzer.create_visualizations()
        
        # 8. 모델 저장
        print("\n[8] 모델 저장 중...")
        analyzer.save_models()
        
        # 9. 실제 백테스팅 거래 시뮬레이션
        print("\n[9] 실제 백테스팅 거래 시뮬레이션 중...")
        backtest_results = analyzer.backtest_trading(initial_balance=10000, commission_rate=0.0005)
        
        # 10. 백테스팅 결과 시각화
        print("\n[10] 백테스팅 결과 시각화 중...")
        analyzer.create_backtest_visualizations(backtest_results)
        
        # 11. 분석 결과 출력
        print("\n[11] 분석 결과 출력 중...")
        analyzer.print_analysis_summary()
        
        # 12. 머신러닝 결과 요약
        print("\n" + "="*60)
        print("머신러닝 모델 성능 요약")
        print("="*60)
        
        if test_results:
            for model_name, results in test_results.items():
                print(f"\n{model_name}:")
                print(f"  - 2024년 테스트 정확도: {results['accuracy']:.4f}")
                print(f"  - 예측 상승 구간: {(results['predictions'] == 1).sum()}개")
                print(f"  - 실제 상승 구간: {(results['actual'] == 1).sum()}개")
        
        # 13. 백테스팅 결과 요약
        if backtest_results:
            print("\n" + "="*60)
            print("백테스팅 거래 결과 요약")
            print("="*60)
            print(f"초기 자본: ${backtest_results['initial_balance']:,.2f}")
            print(f"최종 자본: ${backtest_results['final_balance']:,.2f}")
            print(f"총 수익률: {backtest_results['total_return']:.2%}")
            print(f"총 거래 횟수: {backtest_results['total_trades']}")
            print(f"수익 거래: {backtest_results['profitable_trades']}")
            print(f"승률: {backtest_results['win_rate']:.2%}")
        
        print("\n" + "="*60)
        print("분석 완료! 다년도 패턴으로 2024년 상승을 예측하고 실제 거래 수익을 계산했습니다.")
        print("="*60)
        
    except Exception as e:
        logger.error(f"분석 중 오류 발생: {e}")
        raise

if __name__ == "__main__":
    main()
