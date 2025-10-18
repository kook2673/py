# -*- coding: utf-8 -*-
"""
확장 가능한 모듈식 백테스팅 플랫폼

이 스크립트는 다양한 트레이딩 전략을 쉽게 추가하고 테스트할 수 있는 프레임워크를 제공합니다.
각 전략은 'Strategy' 클래스를 상속받아 자신만의 로직을 구현하며,
'run_backtest' 함수는 이 전략을 받아 백테스트를 수행하고 결과를 반환합니다.

주요 구성 요소:
1. Strategy (기반 클래스): 모든 전략의 뼈대가 되는 추상 클래스.
   - _add_indicators(): 전략에 필요한 지표를 계산하고 데이터프레임에 추가.
   - generate_signals(): 지표를 바탕으로 매수/매도/중립 신호를 생성.

2. RsiMeanReversion (전략 예시): RSI 지표를 활용한 반전 매매 전략.
   - 과매도 구간(예: RSI < 30)에서 매수하고, 과매수 구간(예: RSI > 70)에서 매도.

3. run_backtest (백테스팅 엔진):
   - 지정된 전략과 파라미터로 백테스트를 실행.
   - 거래 수수료, 레버리지, 손절/익절 로직을 포함.
   - 최종 수익률, MDD, 승률 등 주요 성과 지표를 계산하여 반환.

새로운 전략 추가 방법:
1. 'Strategy' 클래스를 상속받는 새로운 클래스를 만듭니다.
2. '_add_indicators' 메서드에 해당 전략에 필요한 지표 계산 로직을 추가합니다.
   (예: 볼린저 밴드, MACD 등)
3. 'generate_signals' 메서드에 지표를 활용한 자신만의 매수/매도 신호 생성 로직을 구현합니다.
4. 스크립트 하단의 if __name__ == '__main__': 블록에서
   새로운 전략 클래스와 파라미터를 지정하여 'run_backtest'를 호출하면 됩니다.
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
import talib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score


class Strategy:
    """모든 전략의 기반이 되는 부모 클래스"""
    def __init__(self, df: pd.DataFrame, params: dict, **kwargs):
        self.df = df.copy()
        self.params = params
        # kwargs를 통해 model 같은 추가 인수를 받을 수 있지만, 기본 클래스에서는 사용하지 않음
        self._add_indicators()

    def _add_indicators(self):
        """전략에 필요한 지표를 계산하고 데이터프레임에 추가하는 메서드 (자식 클래스에서 구현 필요)"""
        raise NotImplementedError("'_add_indicators' 메서드를 구현해야 합니다.")

    def generate_signals(self) -> pd.Series:
        """지표를 바탕으로 매매 신호를 생성하는 메서드 (자식 클래스에서 구현 필요)"""
        raise NotImplementedError("'generate_signals' 메서드를 구현해야 합니다.")


class RsiMeanReversion(Strategy):
    """
    RSI 지표를 활용한 반전 매매(Mean-Reversion) 전략
    - 과매도 구간에서 롱 포지션 진입
    - 과매수 구간에서 포지션 종료
    """
    def _add_indicators(self):
        """RSI 지표를 계산하여 'rsi' 컬럼으로 추가"""
        self.df['rsi'] = talib.RSI(self.df['close'], timeperiod=self.params.get('rsi_window', 14))

    def generate_signals(self) -> pd.Series:
        """RSI 값에 따라 'buy', 'sell', 'hold' 신호를 생성"""
        signals = pd.Series(index=self.df.index, data='hold')
        
        oversold_threshold = self.params.get('oversold_threshold', 30)
        overbought_threshold = self.params.get('overbought_threshold', 70)

        # 'buy' 신호: RSI가 과매도 임계값 아래로 내려갔을 때
        signals[self.df['rsi'] < oversold_threshold] = 'buy'
        
        # 'sell' 신호: RSI가 과매수 임계값 위로 올라갔을 때
        signals[self.df['rsi'] > overbought_threshold] = 'sell'
        
        return signals


class BollingerBandStrategy(Strategy):
    """
    볼린저 밴드를 활용한 전략 예시 (돌파 매매)
    - 가격이 상단 밴드를 돌파(상승 돌파)하면 롱 포지션 진입
    - 가격이 중간 밴드로 회귀하면 포지션 종료
    """
    def _add_indicators(self):
        """볼린저 밴드 지표를 계산하여 컬럼으로 추가"""
        window = self.params.get('window', 20)
        std_dev = self.params.get('std_dev', 2)
        
        self.df['bb_mid'] = self.df['close'].rolling(window=window).mean()
        self.df['bb_std'] = self.df['close'].rolling(window=window).std()
        self.df['bb_upper'] = self.df['bb_mid'] + (self.df['bb_std'] * std_dev)
        self.df['bb_lower'] = self.df['bb_mid'] - (self.df['bb_std'] * std_dev)

    def generate_signals(self) -> pd.Series:
        """볼린저 밴드 값에 따라 'buy', 'sell', 'hold' 신호를 생성"""
        signals = pd.Series(index=self.df.index, data='hold')

        # 'buy' 신호: 종가가 상단 밴드를 돌파했을 때
        signals[self.df['close'] > self.df['bb_upper']] = 'buy'
        
        # 'sell' 신호: 종가가 중간 밴드 아래로 내려왔을 때
        signals[self.df['close'] < self.df['bb_mid']] = 'sell'
        
        return signals


class MacdStrategy(Strategy):
    """
    MACD 지표를 활용한 추세추종 전략
    - 골든크로스 (MACD선이 신호선을 상향 돌파) 시 롱 포지션 진입
    - 데드크로스 (MACD선이 신호선을 하향 돌파) 시 포지션 종료
    """
    def _add_indicators(self):
        """MACD 지표를 계산하여 컬럼으로 추가"""
        fastperiod = self.params.get('fastperiod', 12)
        slowperiod = self.params.get('slowperiod', 26)
        signalperiod = self.params.get('signalperiod', 9)

        # talib.MACD 함수는 macd, macdsignal, macdhist 세 개의 Series를 반환
        self.df['macd'], self.df['macdsignal'], self.df['macdhist'] = talib.MACD(
            self.df['close'],
            fastperiod=fastperiod,
            slowperiod=slowperiod,
            signalperiod=signalperiod
        )

    def generate_signals(self) -> pd.Series:
        """MACD 교차에 따라 'buy', 'sell', 'hold' 신호를 생성"""
        signals = pd.Series(index=self.df.index, data='hold')

        # 'buy' 신호 (골든크로스): macdhist가 양수로 전환될 때
        # (macd가 signal을 막 돌파한 시점)
        signals[(self.df['macdhist'] > 0) & (self.df['macdhist'].shift(1) <= 0)] = 'buy'
        
        # 'sell' 신호 (데드크로스): macdhist가 음수로 전환될 때
        # (macd가 signal 아래로 막 내려간 시점)
        signals[(self.df['macdhist'] < 0) & (self.df['macdhist'].shift(1) >= 0)] = 'sell'
        
        return signals


class StochasticStrategy(Strategy):
    """
    스토캐스틱 오실레이터를 활용한 역추세 전략
    - 과매도 구간에서 골든크로스 발생 시 롱 포지션 진입
    - 과매수 구간에서 데드크로스 발생 시 포지션 종료
    """
    def _add_indicators(self):
        """스토캐스틱 지표(%K, %D)를 계산하여 컬럼으로 추가"""
        self.df['slowk'], self.df['slowd'] = talib.STOCH(
            self.df['high'],
            self.df['low'],
            self.df['close'],
            fastk_period=self.params.get('fastk_period', 14),
            slowk_period=self.params.get('slowk_period', 3),
            slowd_period=self.params.get('slowd_period', 3)
        )

    def generate_signals(self) -> pd.Series:
        """스토캐스틱 값에 따라 'buy', 'sell', 'hold' 신호를 생성"""
        signals = pd.Series(index=self.df.index, data='hold')
        
        oversold = self.params.get('oversold', 20)
        overbought = self.params.get('overbought', 80)

        # 'buy' 신호: 과매도 구간에서 slowk가 slowd를 상향 돌파 (골든크로스)
        buy_cond = (self.df['slowk'] > self.df['slowd']) & (self.df['slowk'].shift(1) <= self.df['slowd'].shift(1))
        buy_cond &= (self.df['slowd'] < oversold)
        signals[buy_cond] = 'buy'
        
        # 'sell' 신호: 과매수 구간에서 slowk가 slowd를 하향 돌파 (데드크로스)
        sell_cond = (self.df['slowk'] < self.df['slowd']) & (self.df['slowk'].shift(1) >= self.df['slowd'].shift(1))
        sell_cond &= (self.df['slowd'] > overbought)
        signals[sell_cond] = 'sell'
        
        return signals


class BollingerBandADXStrategy(BollingerBandStrategy):
    """볼린저 밴드 전략에 ADX 필터를 추가하여 추세가 강할 때만 진입"""
    def _add_indicators(self):
        super()._add_indicators()
        self.df['adx'] = talib.ADX(self.df['high'], self.df['low'], self.df['close'], timeperiod=14)

    def generate_signals(self) -> pd.Series:
        original_signals = super().generate_signals()
        adx_threshold = self.params.get('adx_threshold', 25)
        
        # ADX가 임계값 이상일 때만 원래 신호를 허용
        strong_trend = self.df['adx'] > adx_threshold
        filtered_signals = original_signals.where(strong_trend, 'hold')
        
        return filtered_signals


class MacdADXStrategy(MacdStrategy):
    """MACD 전략에 ADX 필터를 추가하여 추세가 강할 때만 진입"""
    def _add_indicators(self):
        super()._add_indicators()
        self.df['adx'] = talib.ADX(self.df['high'], self.df['low'], self.df['close'], timeperiod=14)

    def generate_signals(self) -> pd.Series:
        original_signals = super().generate_signals()
        adx_threshold = self.params.get('adx_threshold', 25)
        
        # ADX가 임계값 이상일 때만 원래 신호를 허용
        strong_trend = self.df['adx'] > adx_threshold
        filtered_signals = original_signals.where(strong_trend, 'hold')
        
        return filtered_signals


class MachineLearningStrategy(Strategy):
    """
    다양한 기술적 지표를 특징(Feature)으로 사용하는 머신러닝 기반 전략
    - 랜덤 포레스트 분류 모델을 사용하여 미래 가격 방향(상승/하락)을 예측
    """
    def __init__(self, df: pd.DataFrame, params: dict, model: object = None):
        super().__init__(df, params)
        self.model = model # 외부에서 학습된 모델을 저장

    def _add_indicators(self):
        """모델 학습에 사용할 여러 기술적 지표(특징)들을 계산"""
        self.df['rsi'] = talib.RSI(self.df['close'], timeperiod=14)
        
        # 볼린저 밴드
        self.df['bb_mid'] = self.df['close'].rolling(window=20).mean()
        self.df['bb_std'] = self.df['close'].rolling(window=20).std()
        self.df['bb_upper'] = self.df['bb_mid'] + (self.df['bb_std'] * 2)
        
        # MACD
        self.df['macd'], self.df['macdsignal'], self.df['macdhist'] = talib.MACD(
            self.df['close'], fastperiod=12, slowperiod=26, signalperiod=9
        )
        
        # 가격 변화율(Momentum)
        self.df['momentum'] = self.df['close'].pct_change(periods=10)

    def _create_labels(self):
        """미래 가격 방향에 대한 정답(Label) 데이터 생성"""
        future_period = self.params.get('future_period', 10) # 10분 후의 방향을 예측
        
        # N분 후의 가격과 현재 가격을 비교하여 방향성 결정
        self.df['future_price'] = self.df['close'].shift(-future_period)
        self.df['target'] = np.where(self.df['future_price'] > self.df['close'], 1, 0) # 상승: 1, 하락: 0

    def generate_signals(self) -> pd.Series:
        """모델을 훈련하고, 예측 결과를 바탕으로 매매 신호를 생성"""
        self._create_labels()
        
        # 사용할 특징 목록
        features = ['rsi', 'bb_mid', 'bb_std', 'macd', 'macdsignal', 'macdhist', 'momentum']
        
        # NaN 값이 있는 행 제거 및 데이터 분할
        df_clean = self.df.dropna()
        X = df_clean[features]
        y = df_clean['target']

        if len(df_clean) < 100:
             print("경고: 머신러닝 모델을 훈련하기에 데이터가 너무 적습니다.")
             return pd.Series(index=self.df.index, data='hold')

        # 중요: Look-ahead bias 방지를 위해, 과거 데이터로만 훈련하고 미래를 예측
        # 여기서는 데이터를 70% 훈련, 30% 테스트(예측)로 분할
        split_point = int(len(X) * 0.7)
        X_train, X_test = X[:split_point], X[split_point:]
        y_train, y_test = y[:split_point], y[split_point:]
        
        print(f"ML 모델 훈련 시작... (훈련 데이터: {len(X_train)}개, 테스트 데이터: {len(X_test)}개)")

        # 모델 생성 및 훈련
        model = RandomForestClassifier(
            n_estimators=self.params.get('n_estimators', 100),
            random_state=42,
            n_jobs=-1 # 모든 CPU 코어 사용
        )
        model.fit(X_train, y_train)

        # 훈련 데이터에 대한 정확도 (참고용)
        train_pred = model.predict(X_train)
        print(f"  - 모델 훈련 정확도: {accuracy_score(y_train, train_pred) * 100:.2f}%")
        
        # 테스트 데이터(미래)에 대한 예측 수행
        predictions = model.predict(X_test)
        
        # 예측 결과를 신호로 변환
        signals = pd.Series(index=self.df.index, data='hold')
        test_indices = X_test.index
        
        signals.loc[test_indices[predictions == 1]] = 'buy'
        signals.loc[test_indices[predictions == 0]] = 'sell'
        
        return signals


def run_backtest(
    df_original: pd.DataFrame, 
    strategy_class: type, 
    strategy_params: dict,
    trade_type: str = 'long_and_short', # 'long_only', 'short_only', 'long_and_short'
    initial_capital: float = 10000.0,
    fee: float = 0.001,
    leverage: float = 1.0,
    trade_ratio: float = 0.9, # 한 거래에 투입할 자산 비율 (오버플로우 방지)
    atr_stop_loss_multiplier: float = None, # ATR 기반 손절매
    take_profit_pct: float = None,
    trailing_stop_pct: float = None, # 퍼센트 기반 트레일링 스탑 (예: 0.03 = 3%)
    trailing_stop_mode: str = 'fixed', # 'fixed' | 'atr' (ATR 기반 가변 비율)
    trailing_stop_min: float = 0.01, # 트레일링 스탑 최소 비율 (1%)
    trailing_stop_max: float = 0.05, # 트레일링 스탑 최대 비율 (5%)
    cooldown_bars: int = 5, # 청산 후 재진입 쿨다운 (바 수)
    min_hold_bars: int = 0, # 최소 보유 기간 (바 수)
    model: object = None, # 외부에서 학습된 모델을 전달받기 위한 파라미터
    trades_output_csv: str = None # 거래 내역을 CSV로 저장할 경로 (선택)
) -> dict:
    """
    범용 백테스팅 엔진

    Args:
        df_original (pd.DataFrame): 원본 시계열 데이터 (OHLCV 포함)
        strategy_class (type): 사용할 전략의 클래스 (예: RsiMeanReversion)
        strategy_params (dict): 전략에 전달할 파라미터 딕셔너리
        trade_type (str): 거래 유형. 'long_only', 'short_only', 'long_and_short'
        initial_capital (float): 초기 자본금
        fee (float): 거래 수수료 (진입/청산 시 각각 적용)
        leverage (float): 레버리지 배율
        trade_ratio (float): 한 거래에 투입할 자산 비율 (오버플로우 방지)
        atr_stop_loss_multiplier (float, optional): ATR 값에 곱할 배수 (예: 2.0)
        take_profit_pct (float, optional): 익절매 비율 (예: 0.05는 5%)
        trailing_stop_pct (float, optional): 트레일링 스탑 비율 (예: 0.03는 3%)
        trailing_stop_mode (str, optional): 'fixed' 고정 %, 'atr'는 ATR/가격 비율을 곱한 가변 %
        trailing_stop_min (float, optional): 트레일링 스탑 최소 비율 (하한)
        trailing_stop_max (float, optional): 트레일링 스탑 최대 비율 (상한)
        cooldown_bars (int, optional): 청산 후 재진입 쿨다운 (바 수)
        model (object, optional): 사전 학습된 머신러닝 모델
        trades_output_csv (str, optional): 거래 내역을 CSV로 저장할 파일 경로

    Returns:
        dict: 백테스트 결과 (총 수익률, MDD, 거래 내역 등)
    """
    
    # 전략 객체 생성 및 신호 생성
    strategy = strategy_class(df_original, strategy_params, model=model)
    signals = strategy.generate_signals()
    df = strategy.df

    # ATR 계산 (손절/트레일링에 사용)
    need_atr = (atr_stop_loss_multiplier is not None) or (trailing_stop_pct is not None and trailing_stop_mode == 'atr')
    if need_atr:
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)

    # 변수 초기화
    capital = initial_capital
    position_size = 0  # 보유 수량
    entry_price = 0
    stop_loss_price = 0 # ATR 기반 동적 손절가
    # 트레일링 스탑용 워터마크 및 가격
    high_watermark = -np.inf
    low_watermark = np.inf
    trailing_stop_price = None
    equity_curve = []
    trades = []
    
    position_type = None  # None, 'long', 'short'
    entry_bar_idx = -1    # 진입 바 인덱스
    exit_bar_idx = -1     # 청산 바 인덱스

    for i in range(len(df)):
        current_price = df['close'].iloc[i]
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]
        signal = signals.iloc[i]

        stop_loss_triggered = False
        # --- 0-a. 포지션 보유 중 워터마크 갱신 (트레일링 스탑용) ---
        if position_type is not None:
            if position_type == 'long':
                high_watermark = max(high_watermark, current_high)
            elif position_type == 'short':
                low_watermark = min(low_watermark, current_low)

        # --- 0-b. 손절/트레일링 스탑 확인 ---
        if position_type is not None:
            exit_reason = None
            exit_price = None

            # 1) ATR 고정 손절
            if atr_stop_loss_multiplier is not None:
                if position_type == 'long' and current_low <= stop_loss_price:
                    exit_reason = 'stop_loss'
                    exit_price = stop_loss_price
                elif position_type == 'short' and current_high >= stop_loss_price:
                    exit_reason = 'stop_loss'
                    exit_price = stop_loss_price

            # 2) 퍼센트 기반 트레일링 스탑 (고정 또는 ATR 가변)
            if exit_reason is None and trailing_stop_pct is not None:
                # 현재 바에서 적용할 트레일링 비율
                trail_frac = None
                trail_mode = trailing_stop_mode  # 트레일링 스탑 모드 저장 (로그용)
                if trailing_stop_mode == 'fixed':
                    trail_frac = float(trailing_stop_pct)
                    # 하한/상한 클램프 적용
                    if trailing_stop_min is not None:
                        trail_frac = max(trail_frac, trailing_stop_min)
                    if trailing_stop_max is not None:
                        trail_frac = min(trail_frac, trailing_stop_max)
                elif trailing_stop_mode == 'atr':
                    if 'atr' in df.columns and not np.isnan(df['atr'].iloc[i]) and df['atr'].iloc[i] > 0 and current_price > 0:
                        # ATR을 현재가격으로 나눈 비율에 배수를 곱하여 가변 % 산출
                        trail_frac = float(trailing_stop_pct) * (df['atr'].iloc[i] / current_price)
                        # 하한/상한 클램프 적용
                        if trailing_stop_min is not None:
                            trail_frac = max(trail_frac, trailing_stop_min)
                        if trailing_stop_max is not None:
                            trail_frac = min(trail_frac, trailing_stop_max)
                
                if trail_frac is not None and trail_frac > 0:
                    if position_type == 'long' and np.isfinite(high_watermark):
                        trailing_stop_price = high_watermark * (1.0 - trail_frac)
                        if current_low <= trailing_stop_price:
                            exit_reason = f'trailing_stop_{trail_mode}'
                            exit_price = trailing_stop_price
                    elif position_type == 'short' and np.isfinite(low_watermark):
                        trailing_stop_price = low_watermark * (1.0 + trail_frac)
                        if current_high >= trailing_stop_price:
                            exit_reason = f'trailing_stop_{trail_mode}'
                            exit_price = trailing_stop_price

            if exit_reason is not None:
                pnl = 0
                if position_type == 'long':
                    pnl = (exit_price - entry_price) * position_size * (1 - (fee * 2))
                else: # short
                    pnl = (entry_price - exit_price) * position_size * (1 - (fee * 2))

                capital += pnl

                last_trade = trades[-1]
                last_trade.update({
                    'exit_time': df.index[i], 'exit_price': exit_price, 'pnl': pnl,
                    'pnl_pct': ((exit_price / entry_price) - 1) * 100 if position_type == 'long' else ((entry_price / exit_price) - 1) * 100,
                    'exit_reason': exit_reason
                })
                position_type = None
                exit_bar_idx = i  # 청산 바 인덱스 기록
                stop_loss_triggered = True

        if not stop_loss_triggered:
            # --- 1. 롱 포지션 종료 또는 숏 포지션 진입/종료 ---
            if position_type == 'long' and signal == 'sell':
                # 롱 포지션 종료
                pnl = (current_price - entry_price) * position_size * (1 - (fee * 2))
                capital += pnl
                
                last_trade = trades[-1]
                last_trade.update({
                    'exit_time': df.index[i], 'exit_price': current_price, 'pnl': pnl,
                    'pnl_pct': ((current_price / entry_price) - 1) * 100,
                    'exit_reason': 'signal_sell'
                })
                position_type = None
                exit_bar_idx = i  # 청산 바 인덱스 기록
                
                # trade_type이 'long_and_short'이면 바로 숏 진입
                if trade_type == 'long_and_short':
                    signal = 'sell' # 아래 로직에서 숏 진입을 위해 signal을 유지
                else:
                    signal = 'hold' # 롱 전용 모드에서는 숏 진입 방지

            # --- 2. 숏 포지션 종료 또는 롱 포지션 진입/종료 ---
            if position_type == 'short' and signal == 'buy':
                # 숏 포지션 종료
                pnl = (entry_price - current_price) * position_size * (1 - (fee * 2))
                capital += pnl
                
                last_trade = trades[-1]
                last_trade.update({
                    'exit_time': df.index[i], 'exit_price': current_price, 'pnl': pnl,
                    'pnl_pct': ((entry_price / current_price) - 1) * 100,
                    'exit_reason': 'signal_buy'
                })
                position_type = None
                exit_bar_idx = i  # 청산 바 인덱스 기록

                # trade_type이 'long_and_short'이면 바로 롱 진입
                if trade_type == 'long_and_short':
                    signal = 'buy' # 아래 로직에서 롱 진입을 위해 signal을 유지
                else:
                    signal = 'hold' # 숏 전용 모드에서는 롱 진입 방지

            # --- 3. 신규 포지션 진입 ---
            if position_type is None:
                trade_capital = capital * trade_ratio

                # 롱 포지션 신규 진입
                if signal == 'buy' and trade_type in ['long_only', 'long_and_short']:
                    entry_price = current_price
                    position_size = (trade_capital * leverage) / entry_price
                    entry_bar_idx = i  # 진입 바 인덱스 기록
                    position_type = 'long'
                    trades.append({
                        'entry_time': df.index[i], 'entry_price': entry_price, 'type': 'LONG'
                    })
                    if atr_stop_loss_multiplier is not None and 'atr' in df.columns:
                        stop_loss_price = entry_price - (df['atr'].iloc[i] * atr_stop_loss_multiplier)
                    # 트레일링 초기화
                    high_watermark = current_high
                    low_watermark = np.inf


                # 숏 포지션 신규 진입
                elif signal == 'sell' and trade_type in ['short_only', 'long_and_short']:
                    entry_price = current_price
                    position_size = (trade_capital * leverage) / entry_price
                    entry_bar_idx = i  # 진입 바 인덱스 기록
                    position_type = 'short'
                    trades.append({
                        'entry_time': df.index[i], 'entry_price': entry_price, 'type': 'SHORT'
                    })
                    if atr_stop_loss_multiplier is not None and 'atr' in df.columns:
                        stop_loss_price = entry_price + (df['atr'].iloc[i] * atr_stop_loss_multiplier)
                    # 트레일링 초기화
                    low_watermark = current_low
                    high_watermark = -np.inf

        # 매일의 자산 가치 기록
        current_equity = capital
        if position_type == 'long':
            current_equity += (current_price - entry_price) * position_size
        elif position_type == 'short':
            current_equity += (entry_price - current_price) * position_size
        equity_curve.append(current_equity)

    # 최종 결과 계산
    equity_df = pd.Series(equity_curve, index=df.index)
    total_return = (equity_df.iloc[-1] / initial_capital - 1) * 100
    
    # MDD 계산
    peak = equity_df.expanding(min_periods=1).max()
    drawdown = (equity_df - peak) / peak
    mdd = drawdown.min() * 100

    # 승률 계산
    winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
    win_rate = (len(winning_trades) / len(trades)) * 100 if trades else 0

    # 거래 내역을 CSV로 저장 (옵션)
    if trades_output_csv:
        try:
            out_dir = os.path.dirname(trades_output_csv)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            pd.DataFrame(trades).to_csv(trades_output_csv, index=False, encoding='utf-8-sig')
        except Exception:
            pass

    return {
        'strategy': strategy_class.__name__,
        'params': strategy_params,
        'total_return_pct': total_return,
        'mdd_pct': mdd,
        'num_trades': len(trades),
        'win_rate_pct': win_rate,
        'initial_capital': initial_capital,
        'final_capital': equity_df.iloc[-1],
        'trades': trades,
        'equity_curve': equity_df
    }


if __name__ == '__main__':
    # --- 백테스트 실행 설정 ---

    # 1. 데이터 로드
    #    - 주의: 실제 데이터 경로로 수정해야 합니다.
    #    - Scalp_1m_5MA20MA_Optimizer_7months.py에서 사용하는 경로를 참고했습니다.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 경로 수정: binance_test2 폴더 기준으로 상위 폴더의 binance_test 폴더를 바라보도록 변경
    data_path = os.path.abspath(os.path.join(script_dir, '..', 'binance_test', 'data', 'BTC_USDT', '1m', '2025-01.csv'))

    print(f"데이터 로드 중: {data_path}")
    
    try:
        df_btc = pd.read_csv(data_path, index_col='timestamp', parse_dates=True)
        print(f"데이터 로드 완료. 총 {len(df_btc):,}개 데이터")
    except FileNotFoundError:
        print(f"오류: 데이터 파일을 찾을 수 없습니다. '{data_path}' 경로를 확인해주세요.")
        print("테스트를 위해 임의의 데이터를 생성합니다.")
        # 파일이 없을 경우를 대비한 샘플 데이터 생성
        date_range = pd.to_datetime(pd.date_range(start='2025-01-01', periods=43200, freq='T'))
        price_data = 10000 + np.random.randn(43200).cumsum()
        df_btc = pd.DataFrame({
            'open': price_data,
            'high': price_data,
            'low': price_data,
            'close': price_data,
            'volume': np.random.randint(100, 1000, 43200)
        }, index=pd.Series(date_range, name='timestamp'))


    # 2. 실행할 전략과 파라미터 정의
    #    - 여기서 다른 전략(예: 볼린저 밴드)으로 교체하거나, 파라미터를 변경하여 테스트할 수 있습니다.
    
    # --- 테스트 #1: RSI 전략 ---
    strategy_to_test_1 = RsiMeanReversion
    params_to_test_1 = {
        'rsi_window': 14,
        'oversold_threshold': 30,
        'overbought_threshold': 70
    }
    
    # --- 테스트 #2: 볼린저 밴드 전략 ---
    strategy_to_test_2 = BollingerBandStrategy
    params_to_test_2 = {
        'window': 20,
        'std_dev': 2
    }

    # --- 테스트 #3: MACD 전략 ---
    strategy_to_test_3 = MacdStrategy
    params_to_test_3 = {
        'fastperiod': 12,
        'slowperiod': 26,
        'signalperiod': 9
    }

    # --- 테스트 #4: 머신러닝 전략 ---
    strategy_to_test_4 = MachineLearningStrategy
    params_to_test_4 = {
        'future_period': 10,
        'n_estimators': 100
    }

    # --- 실행할 테스트 선택 ---
    strategy_to_run = strategy_to_test_4
    params_to_run = params_to_test_4


    # 3. 백테스트 실행
    print(f"\n전략 '{strategy_to_run.__name__}' 백테스트 실행...")
    print(f"파라미터: {params_to_run}")
    
    # 거래 내역 CSV 저장 경로
    logs_dir = os.path.join(script_dir, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    trades_csv_path = os.path.join(logs_dir, 'Backtest_Trades.csv')

    results = run_backtest(
        df_original=df_btc,
        strategy_class=strategy_to_run,
        strategy_params=params_to_run,
        trade_type='long_and_short', # 거래 유형 선택
        initial_capital=10000,
        fee=0.001,
        leverage=10, # 옵티마이저와 동일하게 10배로 설정하여 테스트
        trade_ratio=0.9, # 자본의 90%만 거래에 사용
        atr_stop_loss_multiplier=2.0,     # ATR 2배 손절
        take_profit_pct=0.05,    # 5% 익절
        trades_output_csv=trades_csv_path
    )

    # 4. 결과 출력
    print("\n--- 백테스트 결과 ---")
    print(f"전략: {results['strategy']} (파라미터: {results['params']})")
    print(f"테스트 기간: {df_btc.index[0]} ~ {df_btc.index[-1]}")
    print("-" * 25)
    print(f"초기 자본: ${results['initial_capital']:,.2f}")
    print(f"최종 자본: ${results['final_capital']:,.2f}")
    print(f"총 수익률: {results['total_return_pct']:.2f}%")
    print(f"최대 낙폭 (MDD): {results['mdd_pct']:.2f}%")
    print(f"총 거래 횟수: {results['num_trades']}회")
    print(f"승률: {results['win_rate_pct']:.2f}%")
    print("-" * 25)

    # 거래 내역 상위 5개 출력
    if results['trades']:
        print("\n--- 최근 거래 내역 (5건) ---")
        trades_df = pd.DataFrame(results['trades'])
        print(trades_df.tail().to_string(index=False))

    # # 자산 변화 그래프 (matplotlib 필요)
    # try:
    #     import matplotlib.pyplot as plt
    #     print("\n자산 변화 그래프를 출력합니다...")
    #     results['equity_curve'].plot(title='Equity Curve', figsize=(12, 6))
    #     plt.xlabel('Date')
    #     plt.ylabel('Equity Value ($)')
    #     plt.grid(True)
    #     plt.show()
    # except ImportError:
    #     print("\n그래프를 보려면 'matplotlib' 라이브러리를 설치하세요. (pip install matplotlib)")
