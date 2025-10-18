#-*-coding:utf-8 -*-
'''
머신러닝 모델 학습 스크립트 (ML Scalping Bot용)

=== 스크립트 개요 ===
이 스크립트는 `ML_Scalping.py` 라이브 트레이딩 봇에서 사용할 머신러닝 모델을 학습하고 저장하는 역할을 합니다.
Random Forest 분류 모델을 사용하여 특정 시점 이후의 가격 방향(상승/하락)을 예측하도록 학습합니다.

=== 프로세스 ===
1.  **데이터 수집**: `ccxt` 라이브러리를 통해 바이낸스에서 지정된 코인(`TARGET_COIN`)의 과거 1분봉 데이터를 대량으로 다운로드합니다.
2.  **피처 엔지니어링**: 다운로드한 데이터에 다음과 같은 다양한 기술적 분석 지표를 계산하여 모델이 학습할 피처(feature)를 생성합니다.
    - **RSI (Relative Strength Index)**
    - **Bollinger Bands**
    - **MACD (Moving Average Convergence Divergence)**
    - **Momentum (가격 변화율)**
3.  **레이블 생성**: 미래 가격(예: 5분 후)이 현재 가격보다 상승했는지 또는 하락했는지에 따라 '상승'(1) 또는 '하락'(0) 레이블을 생성합니다. 이는 모델이 예측해야 할 정답 역할을 합니다.
4.  **모델 학습**: 준비된 피처와 레이블을 사용하여 `RandomForestClassifier` 모델을 학습시킵니다.
5.  **모델 저장**: 학습이 완료된 모델은 `joblib`을 사용하여 `ml_model.pkl` 파일로 저장됩니다. 이 파일은 라이브 트레이딩 봇에서 사용됩니다.

=== 사용 방법 ===
1.  스크립트를 직접 실행합니다: `python ML_Scalping_train_model.py`
2.  실행이 완료되면 스크립트와 동일한 디렉토리에 `ml_model.pkl` 파일이 생성됩니다.

=== 권장 실행 주기 ===
- 시장의 최신 패턴을 모델에 반영하기 위해 **최소 주 1회 이상 이 스크립트를 실행**하여 모델을 주기적으로 재학습하고 업데이트하는 것을 강력히 권장합니다.
'''

import os
import pandas as pd
import numpy as np
import talib
from sklearn.ensemble import RandomForestClassifier
import joblib  # scikit-learn 모델 저장/로드를 위한 라이브러리
import ccxt

# --- 설정 ---
TARGET_COIN = 'BTC/USDT'
TIMEFRAME = '1m'
DATA_LIMIT = 43200  # 다운로드할 데이터 개수 (예: 30일 = 30 * 24 * 60 = 43200)
MODEL_FILE_NAME = 'ml_model.pkl'
LABEL_LOOKAHEAD = 5  # 몇 분 뒤의 가격을 예측할 것인가
FEE = 0.001

# myBinance.py나 다른 키 관리 파일이 있다면 그쪽을 import해서 사용하세요.
# 여기서는 설명을 위해 직접 키를 입력하는 형태를 가정합니다.
# binance = ccxt.binance({ 'apiKey': 'YOUR_API_KEY', 'secret': 'YOUR_SECRET_KEY' })
binance = ccxt.binance() # Public API로 데이터만 가져올 경우

def download_data(symbol, timeframe, limit):
    """바이낸스에서 OHLCV 데이터를 다운로드합니다."""
    try:
        print(f"바이낸스에서 {symbol} {timeframe} 데이터 다운로드 중... (최대 {limit}개)")
        binance = ccxt.binance()
        ohlcv = binance.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        print("데이터 다운로드 완료.")
        return df
    except Exception as e:
        print(f"데이터 다운로드 중 오류 발생: {e}")
        return None

def add_features(ohlcv_df):
    """백테스팅과 동일한 방법으로 특징(Feature) 추가"""
    print("특징(Feature) 생성 중...")
    
    # RSI
    ohlcv_df['rsi'] = talib.RSI(ohlcv_df['close'], timeperiod=14)
    
    # 볼린저 밴드
    upper, middle, lower = talib.BBANDS(ohlcv_df['close'], timeperiod=20)
    ohlcv_df['bb_upper'] = upper
    ohlcv_df['bb_lower'] = lower
    ohlcv_df['bb_width'] = (upper - lower) / middle
    ohlcv_df['bb_position'] = (ohlcv_df['close'] - lower) / (upper - lower)

    # MACD
    macd, macdsignal, macdhist = talib.MACD(ohlcv_df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
    ohlcv_df['macd'] = macd
    ohlcv_df['macdsignal'] = macdsignal
    
    # 모멘텀
    ohlcv_df['momentum'] = ohlcv_df['close'].pct_change(periods=5)
    
    print("특징 생성 완료.")
    return ohlcv_df

def add_labels(df):
    """예측할 정답(Label) 추가"""
    print("정답(Label) 생성 중...")
    df['future_price'] = df['close'].shift(-LABEL_LOOKAHEAD)
    df['price_change_pct'] = (df['future_price'] - df['close']) / df['close']
    
    # 목표: 0.1% (수수료 감안) 이상 변동 시에만 레이블링
    df['label'] = 0
    df.loc[df['price_change_pct'] > FEE, 'label'] = 1  # 상승
    # 하락 조건은 따로 지정하지 않음 (상승이 아니면 0)

    print("정답 생성 완료.")
    return df.drop(columns=['future_price', 'price_change_pct'])

def train_and_save_model():
    """데이터를 다운로드, 전처리, 학습하고 모델을 저장하는 메인 함수"""
    
    # 1. 데이터 다운로드
    df = download_data(TARGET_COIN, TIMEFRAME, DATA_LIMIT)
    if df is None or df.empty:
        print("데이터를 가져오지 못해 모델 학습을 중단합니다.")
        return

    # 2. 특징 및 레이블 추가
    df = add_features(df)
    df = add_labels(df)
    
    # 3. 불필요한 데이터 제거 및 준비
    df.dropna(inplace=True)
    
    if len(df) < 100: # 최소 학습 데이터 수 확인
        print("오류: 모델을 훈련하기에 데이터가 충분하지 않습니다.")
        return
        
    features = [col for col in df.columns if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'label']]
    X = df[features]
    y = df['label']
    
    # 4. 모델 학습
    print("모델 학습 중...")
    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X, y)
    print("모델 학습 완료.")
    
    # 5. 모델 저장
    try:
        model_path = os.path.join(os.path.dirname(__file__), MODEL_FILE_NAME)
        joblib.dump(model, model_path)
        print(f"모델이 '{model_path}'에 성공적으로 저장되었습니다.")
    except Exception as e:
        print(f"모델 저장 중 오류 발생: {e}")

if __name__ == "__main__":
    train_and_save_model()
