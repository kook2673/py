#-*-coding:utf-8 -*-
'''
머신러닝 실시간 추론 라이브러리 (ML Scalping Bot용)

=== 라이브러리 개요 ===
이 스크립트는 `ML_Scalping.py` 라이브 트레이딩 봇을 위한 보조 라이브러리입니다.
`ML_Scalping_train_model.py`를 통해 사전에 학습된 머신러닝 모델 (`.pkl` 파일)을 로드하고,
실시간으로 들어오는 캔들(OHLCV) 데이터로부터 거래 신호를 생성하는 역할을 담당합니다.

=== 주요 클래스: LiveMLStrategy ===
-   **`__init__(self, model_path)`**:
    -   생성자 함수로, 학습된 모델 파일의 경로를 입력받아 `joblib`을 사용해 모델을 메모리에 로드합니다.
    -   모델 로드에 실패할 경우 예외를 발생시켜 봇의 실행을 중단시킵니다.

-   **`_add_features(self, ohlcv_df)`**:
    -   입력된 실시간 OHLCV 데이터프레임에 대해 모델 학습 시 사용했던 것과 **동일한 피처 엔지니어링** 과정을 적용합니다.
    -   다음과 같은 모든 기술적 지표를 계산하여 데이터프레임에 추가합니다:
        - **RSI (Relative Strength Index)**
        - **Bollinger Bands**
        - **MACD (Moving Average Convergence Divergence)**
        - **Momentum (가격 변화율)**
    -   학습 과정과 피처 생성 방식이 일치해야 모델의 예측 정확성을 보장할 수 있습니다.

-   **`get_signal(self, ohlcv_df)`**:
    -   라이브 트레이딩 봇에서 직접 호출하는 메인 함수입니다.
    -   `_add_features`를 호출하여 필요한 피처를 계산한 후, 가장 최신 데이터를 추출합니다.
    -   로드된 모델의 `predict` 및 `predict_proba` 메서드를 사용하여 가격 방향(상승/하락)을 예측하고 해당 예측의 신뢰도(확률)를 계산합니다.
    -   예측 결과를 기반으로 'BUY_LONG_OR_SELL_SHORT' (상승 예측) 또는 'SELL_LONG_OR_BUY_SHORT' (하락 예측) 신호를 반환합니다.
'''

import os
import pandas as pd
import numpy as np
import talib
import joblib

class MLScalpingLib:
    def __init__(self, model_path):
        """
        클래스 초기화 시, 저장된 모델 파일을 불러와 메모리에 올립니다.
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {model_path}. 먼저 train_model.py를 실행하세요.")
        
        print(f"저장된 모델 로드 중: {model_path}")
        self.model = joblib.load(model_path)
        # 학습 스크립트와 동일한 피처 목록으로 수정
        self.features = ['rsi', 'bb_upper', 'bb_lower', 'bb_width', 'bb_position', 'macd', 'macdsignal', 'momentum']
        print("모델 로드 완료.")

    def _add_features(self, df):
        """
        모델 학습에 사용했던 것과 **완벽히 동일한** 방법으로 특징을 계산합니다.
        이 부분이 다르면 예측 결과가 왜곡될 수 있어 매우 중요합니다.
        """
        # RSI (동일)
        df['rsi'] = talib.RSI(df['close'], timeperiod=14)
        
        # 볼린저 밴드 (학습 스크립트와 동일하게 수정)
        upper, middle, lower = talib.BBANDS(df['close'], timeperiod=20)
        df['bb_upper'] = upper
        df['bb_lower'] = lower
        
        # 0으로 나누기 방지
        middle_safe = middle.replace(0, np.nan)
        df['bb_width'] = (upper - lower) / middle_safe
        
        bb_range = upper - lower
        bb_range_safe = bb_range.replace(0, np.nan)
        df['bb_position'] = (df['close'] - lower) / bb_range_safe

        # MACD (학습 스크립트와 동일하게 수정)
        macd, macdsignal, macdhist = talib.MACD(
            df['close'], fastperiod=12, slowperiod=26, signalperiod=9
        )
        df['macd'] = macd
        df['macdsignal'] = macdsignal
        
        # 모멘텀 (기간 10 -> 5로 수정)
        df['momentum'] = df['close'].pct_change(periods=5)
        return df

    def get_signal(self, df_live):
        """
        실시간으로 수신한 OHLCV 데이터프레임을 받아 매매 신호를 반환합니다.

        Args:
            df_live (pd.DataFrame): 최소 40개 이상의 행을 가진 OHLCV 데이터.
                                    (지표 계산에 필요한 최소 데이터 개수)

        Returns:
            tuple: (signal, probability)
                   - signal (str): 'BUY_LONG_OR_SELL_SHORT', 'SELL_LONG_OR_BUY_SHORT', 또는 None
                   - probability (float): 예측 신호의 확률
        """
        if len(df_live) < 40:
            # 각종 지표(MACD 26+9, BB 20 등)를 계산하기 위한 최소 데이터 확보
            return None, 0.0

        # 1. 특징 생성
        df_featured = self._add_features(df_live.copy())
        
        # 2. 최신 데이터 추출
        latest_features = df_featured.iloc[-1][self.features]
        
        # NaN 값이 있는지 확인
        if latest_features.isnull().any():
            print("경고: 최신 데이터의 특징(feature) 값에 NaN이 포함되어 있어 예측을 건너뜁니다.")
            return None, 0.0
            
        # 3. 모델 예측
        try:
            # 모델은 2D 배열을 기대하므로, 1개 행을 [[]]로 감싸서 전달
            prediction = self.model.predict([latest_features.values])
            probability_matrix = self.model.predict_proba([latest_features.values])
            
            # 예측된 클래스의 확률
            probability = probability_matrix[0][prediction[0]]
            
            # 4. 신호 변환 (ML_Scalping.py에서 사용하는 형식으로)
            if prediction[0] == 1: # 상승 예측
                signal = 'BUY_LONG_OR_SELL_SHORT'
            else: # 하락 예측 (0)
                signal = 'SELL_LONG_OR_BUY_SHORT'
            
            print(f"최신 데이터 예측 완료. 시간: {df_live.index[-1]}, 예측: {prediction[0]} -> 신호: {signal}, 확률: {probability*100:.2f}%")
            
            return signal, probability

        except Exception as e:
            # traceback을 포함하여 더 자세한 오류 로깅
            import traceback
            print(f"모델 예측 중 오류 발생: {e}\n{traceback.format_exc()}")
            return None, 0.0
