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
from tqdm import tqdm # Added for multi-strategy backtest progress bar
import logging

# 로깅 기본 설정 (실행 스크립트에서 더 상세한 설정을 덮어쓸 수 있음)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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


# =============================================================================
# 포트폴리오 백테스팅을 위한 새로운 클래스 및 함수
# =============================================================================

class PortfolioStrategy:
    """모든 포트폴리오 전략의 기반이 되는 추상 기본 클래스입니다."""
    def __init__(self, tickers, params):
        self.is_event_driven = False
        self.tickers = tickers
        self.params = params
        self.universe_with_indicators = {}
        # __init__ 단계에서는 데이터를 알 수 없으므로, 이 호출은 제거합니다.
        # 지표 계산은 run_multi_strategy_backtest에서 데이터를 전달받아 수행합니다.

    def _add_indicators(self, universe_dfs):
        """
        주어진 데이터프레임에 전략에 필요한 기술적 지표를 추가합니다.
        """
        raise NotImplementedError("'_add_indicators' 메서드를 구현해야 합니다.")

    def generate_signals(self, date, current_portfolio: dict) -> list:
        """
        특정 날짜를 기준으로 매수/매도할 종목을 결정.
        Args:
            date (pd.Timestamp): 현재 날짜
            current_portfolio (dict): 현재 보유중인 포트폴리오 {'종목코드': 수량}
        Returns:
            list: 다음 리밸런싱 시점에 보유해야 할 종목 코드 리스트
        """
        raise NotImplementedError("'generate_signals' 메서드를 구현해야 합니다.")


class MovingAverageMomentumStrategy(PortfolioStrategy):
    """
    코스피 100, 코스닥 100 종목을 대상으로 다음의 강화된 규칙에 따라 투자하는 전략:
    - 매수 조건: 
        1. stock_list.json에 명시된 종목별 최적 MA값 기준 골든크로스 '상태'
        2. 단기 MA 상승 추세
        3. 평균 모멘텀 점수 1.0
    - 종목 선정:
        - 위 매수 조건을 만족하는 종목들을 대상으로 우선순위 점수를 계산
        - 우선순위 점수 = (MA 기울기 점수) + (가격-MA20 이격도 점수) + (최근 가격 변동성 점수)
        - 점수가 가장 높은 상위 N개 종목 (예: 30개)을 최종 투자 대상으로 선정
    """
    def __init__(self, tickers, params):
        super().__init__(tickers, params)
        self.max_buy_stocks = params.get('max_buy_stocks', 30)
        # stock_list.json에서 로드한 종목별 파라미터
        self.stock_specific_params = params.get('stock_specific_params', {})
        logging.info(f"MA_Momentum: {len(self.stock_specific_params)}개 종목의 특정 파라미터를 로드했습니다.")
        logging.info(f"MA_Momentum: 최대 보유 종목 수: {self.max_buy_stocks}")

    def _add_indicators(self, universe_dfs):
        logging.info("MA_MomentumStrategy: 기술적 지표 계산 중...")
        
        # 필요한 모든 MA 기간을 수집 (중복 제거)
        required_ma_periods = {5, 20} # 우선순위 점수 계산용
        for ticker_params in self.stock_specific_params.values():
            if ticker_params and 'small_ma' in ticker_params and 'big_ma' in ticker_params:
                try:
                    required_ma_periods.add(int(ticker_params['small_ma']))
                    required_ma_periods.add(int(ticker_params['big_ma']))
                except (ValueError, TypeError):
                    continue

        new_universe_with_indicators = {}
        for ticker, df in universe_dfs.items():
            if df.empty:
                continue
            
            df = df.copy() # SettingWithCopyWarning 방지를 위해 복사본 사용
            # 1. 이동평균선 계산 (필요한 것들만)
            for period in required_ma_periods:
                if period > 0 and len(df) >= period:
                    df[f'ma{period}'] = df['close'].rolling(window=period).mean()
                    df[f'ma{period}_before'] = df[f'ma{period}'].shift(1)
                    df[f'ma{period}_before2'] = df[f'ma{period}'].shift(2)

            # 2. 평균 모멘텀 지표 계산 (20일 간격, 10개 구간)
            momentum_periods = [i * 20 for i in range(1, 11)] # 20, 40, ..., 200
            momentum_columns = []
            
            # 전일 종가 데이터
            prev_close = df['close'].shift(1)

            for period in momentum_periods:
                if len(df) > period:
                    col_name = f'momentum_{period}'
                    df[col_name] = (prev_close > df['close'].shift(period + 1)).astype(int)
                    momentum_columns.append(col_name)

            if momentum_columns:
                df['Average_Momentum'] = df[momentum_columns].mean(axis=1)
            else:
                df['Average_Momentum'] = 0.0

            # 3. 우선순위 점수 계산
            # MA 기울기 점수
            ma5_slope = (df.get('ma5_before', 0) - df.get('ma5_before2', 0))
            ma20_slope = (df.get('ma20_before', 0) - df.get('ma20_before2', 0))
            ma_slope_score = (ma5_slope * 0.7 + ma20_slope * 0.3) * 1000

            # 가격 대비 MA20 위치
            price_ma20_ratio = (df['close'] / df.get('ma20_before', 1) - 1) * 100

            # 최근 가격 변동성
            price_change_rate = (df['close'].pct_change() * 100) * 50

            df['priority_score'] = ma_slope_score + price_ma20_ratio + price_change_rate

            new_universe_with_indicators[ticker] = df.copy()

        return new_universe_with_indicators

    def generate_signals(self, date, portfolio):
        potential_buy_stocks = []

        for ticker in self.tickers:
            # 해당 종목의 특정 파라미터 가져오기
            params = self.stock_specific_params.get(ticker)
            if not params or 'small_ma' not in params or 'big_ma' not in params or not params['small_ma'] or not params['big_ma']:
                continue
                
            small_ma = int(params['small_ma'])
            big_ma = int(params['big_ma'])

            df = self.universe_with_indicators.get(ticker)
            if df is None or date not in df.index:
                continue

            # 최신 데이터 (리밸런싱 날짜 기준)
            latest_data = df.loc[date]
            
            # 필요한 컬럼명 생성
            short_ma_col = f'ma{small_ma}_before'
            long_ma_col = f'ma{big_ma}_before'
            short_ma_col2 = f'ma{small_ma}_before2'

            # 데이터 유효성 검사
            required_cols = [short_ma_col, long_ma_col, short_ma_col2, 'Average_Momentum', 'priority_score']
            if any(col not in latest_data or pd.isna(latest_data[col]) for col in required_cols):
                continue
            
            # 매수 조건 확인
            # 1. 골든크로스 '상태'
            is_golden_cross = latest_data[short_ma_col] > latest_data[long_ma_col]
            # 2. 단기 MA 상승 추세
            is_short_ma_rising = latest_data[short_ma_col] > latest_data[short_ma_col2]
            # 3. 평균 모멘텀 점수 1.0
            is_momentum_perfect = latest_data['Average_Momentum'] == 1.0
            
            if is_golden_cross and is_short_ma_rising and is_momentum_perfect:
                potential_buy_stocks.append({
                    'ticker': ticker,
                    'priority_score': latest_data['priority_score']
                })
        
        # 우선순위 점수로 정렬
        potential_buy_stocks.sort(key=lambda x: x['priority_score'], reverse=True)
        
        # 상위 N개 종목 선택
        target_tickers = [stock['ticker'] for stock in potential_buy_stocks[:self.max_buy_stocks]]
        
        return target_tickers


class TurtleStrategy(PortfolioStrategy):
    """
    고전적인 추세 추종 전략인 터틀 트레이딩을 개선하여 구현합니다.
    - 진입: N일 신고가 돌파 시 매수 (단, 시장이 상승 추세일 때만)
    - 청산: M일 신저가 돌파 시 매도
    - 손절: 2-ATR 기반의 명확한 손절매 규칙 적용
    - 포지션 사이징: ATR 기반으로 변동성을 조절하여 리스크 균등화
    """
    def __init__(self, tickers, params):
        super().__init__(tickers, params)
        # WFO를 통해 최적화될 파라미터
        self.entry_period = params.get('entry_period', 20)
        self.exit_period = params.get('exit_period', 10)
        self.atr_period = params.get('atr_period', 20)
        # 리스크 관리 파라미터
        self.risk_per_trade = params.get('risk_per_trade', 0.01) # 전체 자본의 1%를 1회 거래의 최대 손실로 제한
        self.max_positions = params.get('max_positions', 10) # 최대 동시 보유 종목 수
        self.stop_loss_atr_multiplier = params.get('stop_loss_atr_multiplier', 2.0) # N * ATR 손절
        logging.info(f"TurtleStrategy Improved: Entry={self.entry_period}, Exit={self.exit_period}, ATR={self.atr_period}, MaxPositions={self.max_positions}")

    def _add_indicators(self, universe_dfs):
        logging.info("TurtleStrategy: 기술적 지표 계산 중...")
        new_universe_with_indicators = {}

        # KOSPI 추세 필터용 지표 추가
        if 'KOSPI' in universe_dfs:
            kospi_df = universe_dfs['KOSPI'].copy()
            kospi_df['ma200'] = kospi_df['close'].rolling(window=200).mean()
            new_universe_with_indicators['KOSPI'] = kospi_df

        for ticker, df in universe_dfs.items():
            if df.empty or ticker == 'KOSPI':
                continue

            df = df.copy() # SettingWithCopyWarning 방지를 위해 복사본 사용
            # ATR 계산
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=self.atr_period)

            # N일 신고가/신저가 계산 (오늘 가격을 포함하여 계산)
            df[f'rolling_high_{self.entry_period}'] = df['high'].rolling(window=self.entry_period).max()
            df[f'rolling_low_{self.exit_period}'] = df['low'].rolling(window=self.exit_period).min()
            
            new_universe_with_indicators[ticker] = df.copy()
        
        return new_universe_with_indicators

    def generate_signals(self, date, portfolio, strategy_capital):
        """
        개선된 터틀 로직에 따라 매수/매도할 '종목과 수량'을 결정합니다.
        """
        target_quantities = {} # 최종 목표: {'ticker': quantity}
        
        # --- 1. 추세 필터 확인 ---
        kospi_df = self.universe_with_indicators.get('KOSPI')
        if kospi_df is None or date not in kospi_df.index:
            logging.warning(f"[{date.date()}] KOSPI 데이터가 없어 추세 필터를 적용할 수 없습니다. 매수를 진행하지 않습니다.")
            return {} # 하락장으로 간주하고 매수 안함
            
        kospi_latest = kospi_df.loc[date]
        if pd.isna(kospi_latest['ma200']) or kospi_latest['close'] < kospi_latest['ma200']:
            # KOSPI가 200일선 아래면 하락장으로 판단, 신규 진입 안함 (기존 보유 종목 청산은 진행)
            pass
        else:
            # --- 2. 진입 신호 확인 (상승장일 때만) ---
            potential_buys = []
            
            # 현재 보유 종목 수가 최대치 미만일 때만 신규 진입 탐색
            if len(portfolio) < self.max_positions:
                for ticker in self.tickers:
                    if ticker in portfolio: continue # 이미 보유 중이면 제외

                    df = self.universe_with_indicators.get(ticker)
                    if df is None or date not in df.index: continue

                    latest_data = df.loc[date]
                    # 어제의 N일 신고가
                    yesterday_high = df[f'rolling_high_{self.entry_period}'].shift(1).loc[date]
                    
                    # 오늘 종가가 어제의 N일 신고가를 돌파했는지 확인
                    if pd.notna(yesterday_high) and latest_data['close'] > yesterday_high:
                        potential_buys.append(ticker)

            # --- 3. 포지션 사이징 및 최종 매수 결정 ---
            for ticker in potential_buys:
                # 최대 보유 종목 수 재확인
                if len(target_quantities) + len(portfolio) >= self.max_positions:
                    break

                df = self.universe_with_indicators.get(ticker)
                latest_data = df.loc[date]
                atr = latest_data.get('atr')
                
                if pd.notna(atr) and atr > 0:
                    # 1N = (1% of Portfolio) / ATR
                    dollar_volatility = atr * 1 # 1은 계약단위, 주식에서는 1주
                    position_size_unit = (strategy_capital * self.risk_per_trade) / dollar_volatility
                    
                    target_quantities[ticker] = int(position_size_unit)

        # --- 4. 청산 신호 확인 및 기존 포지션 유지 ---
        for ticker, holding in portfolio.items():
            if ticker in target_quantities: continue # 이미 새로운 매수 수량이 결정된 종목은 제외

            df = self.universe_with_indicators.get(ticker)
            if df is None or date not in df.index:
                target_quantities[ticker] = holding['quantity'] # 데이터 없으면 일단 유지
                continue

            latest_data = df.loc[date]
            # 어제의 M일 신저가
            yesterday_low = df[f'rolling_low_{self.exit_period}'].shift(1).loc[date]

            if pd.notna(yesterday_low) and latest_data['close'] < yesterday_low:
                target_quantities[ticker] = 0 # 청산 신호
            else:
                target_quantities[ticker] = holding['quantity'] # 유지

        return target_quantities


class KospidaqHybridStrategy(PortfolioStrategy):
    """
    KODEX 코스피/코스닥 레버리지/인버스 ETF 4종목에 대해
    WFO로 찾은 최적의 MA값을 이용해 골든크로스 '상태'일 때 투자하는 전략
    """
    def __init__(self, tickers, params):
        super().__init__(tickers, params)
        self.optimal_params = params

    def _add_indicators(self, universe_dfs):
        logging.info("KospidaqHybridStrategy: 지표 계산 시작...")
        new_universe_with_indicators = {}
        ma_periods = {3, 5, 10, 20, 60, 120}
        
        for ticker in self.tickers:
            if ticker in universe_dfs:
                df = universe_dfs[ticker].copy()
                for period in ma_periods:
                    if len(df) >= period:
                        df[f'ma{period}'] = df['close'].rolling(window=period).mean()
                        df[f'ma{period}_before'] = df[f'ma{period}'].shift(1)
                        df[f'ma{period}_before2'] = df[f'ma{period}'].shift(2)
                new_universe_with_indicators[ticker] = df.dropna()
        return new_universe_with_indicators

    def generate_signals(self, date, portfolio):
        """
        WFO를 통해 찾은 최적의 MA 조합으로 골든크로스 '상태' 신호를 생성합니다.
        """
        target_tickers = []

        if not self.optimal_params:
            logging.warning("KospidaqHybridStrategy: 최적 파라미터가 설정되지 않아 매매 신호를 생성할 수 없습니다.")
            return []

        for ticker in self.tickers:
            if ticker not in self.universe_with_indicators:
                continue

            df = self.universe_with_indicators[ticker]
            if date not in df.index:
                continue

            # 해당 ticker의 최적 ma 값을 가져옴
            params = self.optimal_params.get(ticker)
            if not params or 'small_ma' not in params or 'big_ma' not in params:
                continue

            short_ma_col = f"ma{params['small_ma']}_before"
            long_ma_col = f"ma{params['big_ma']}_before"

            # 데이터프레임에 해당 ma 컬럼이 있는지 확인
            if short_ma_col not in df.columns or long_ma_col not in df.columns:
                continue

            # 이전 날짜의 인덱스를 찾음
            current_date_idx = df.index.get_loc(date)
            if current_date_idx < 1:
                continue
            
            prev_day_data = df.iloc[current_date_idx - 1]

            # 골든 크로스 '상태' 조건 체크 (리밸런싱 날짜 기준 전일)
            short_ma_prev = prev_day_data.get(short_ma_col)
            long_ma_prev = prev_day_data.get(long_ma_col)

            if pd.notna(short_ma_prev) and pd.notna(long_ma_prev):
                if short_ma_prev > long_ma_prev:
                    target_tickers.append(ticker)

        return target_tickers


class SafeAssetRebalancingStrategy(PortfolioStrategy):
    """
    안전 자산(채권, 금 등) 포트폴리오를 주기적으로 리밸런싱하는 전략.
    RSI와 이격도를 활용하여 과매수/과매도 상태를 판단하고 비중을 조절.
    """
    def _add_indicators(self, universe_dfs):
        logging.info("SafeAssetRebalancingStrategy: 지표 계산 시작...")
        new_universe_with_indicators = {}
        for ticker in self.tickers:
            if ticker in universe_dfs:
                df = universe_dfs[ticker].copy()
                # RSI 계산
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df['rsi'] = 100 - (100 / (1 + rs))
                
                # 20일 이평선 및 이격도 계산
                df['ma20'] = df['close'].rolling(window=20).mean()
                df['disparity'] = (df['close'] / df['ma20']) * 100
                new_universe_with_indicators[ticker] = df.dropna()
        return new_universe_with_indicators

    def generate_signals(self, date, portfolio):
        """RSI < 70 이고, 이격도 < 105 인 종목만 보유 (필터링)"""
        target_tickers = []

        for ticker in self.params.get('universe', []):
            if ticker in self.universe_with_indicators:
                df = self.universe_with_indicators[ticker]
                if date in df.index:
                    today = df.loc[date]
                    params_for_ticker = self.params.get(ticker, {})
                    small_ma = today[f"{params_for_ticker.get('small_ma', 5)}ma"]
                    big_ma = today[f"{params_for_ticker.get('big_ma', 20)}ma"]
                    small_ma_yesterday = today[f"{params_for_ticker.get('small_ma', 5)}ma_before2"]
                    
                    is_investing = ticker in portfolio
                    
                    # 매수 조건
                    buy_condition = small_ma > big_ma and small_ma_yesterday < small_ma

                    # 매도 조건
                    sell_condition = small_ma < big_ma and small_ma_yesterday > small_ma
                    
                    if is_investing:
                        if not sell_condition:
                            target_tickers.append(ticker) # 보유 유지
                    else:
                        if buy_condition:
                            target_tickers.append(ticker) # 신규 매수

        return target_tickers


class KospiDipBuyingStrategy(PortfolioStrategy):
    """
    코스피 지수가 1년 고점 대비 일정 비율 이상 하락했을 때 분할 매수하는 이벤트 기반 전략.
    """
    def __init__(self, tickers, params):
        super().__init__(tickers, params)
        self.is_event_driven = True
        self.target_etf = '122630' # KODEX 레버리지

    def _add_indicators(self, universe_dfs):
        logging.info("KospiDipBuyingStrategy: 지표 계산 시작...")
        new_universe_with_indicators = universe_dfs.copy()
        if 'KOSPI' in universe_dfs:
            kospi_df = universe_dfs['KOSPI'].copy()
            kospi_df['rolling_high_1y'] = kospi_df['close'].rolling(window=252).max()
            kospi_df['dd_pct'] = (kospi_df['close'] / kospi_df['rolling_high_1y'] - 1) * 100
            new_universe_with_indicators['KOSPI'] = kospi_df
        return new_universe_with_indicators

    def generate_signals(self, date, portfolio, custom_state):
        """
        KOSPI DD%에 따라 KODEX 200 레버리지 ETF를 분할 매수/전량 매도합니다.
        """
        target_portfolio = {} # {'ticker': 비중}
        kospi_df = self.universe_with_indicators['KOSPI']
        
        if date not in kospi_df.index:
            return current_portfolio # 데이터 없으면 현재 포트폴리오 유지

        today = kospi_df.loc[date]
        dd_pct = today['dd_pct']

        # 매수 로직
        current_weight = custom_state.get('current_weight', 0.0)
        target_weight = 0.0
        
        if -0.20 < dd_pct <= -0.15: target_weight = 0.1
        elif -0.25 < dd_pct <= -0.20: target_weight = 0.2
        elif -0.30 < dd_pct <= -0.25: target_weight = 0.4
        elif -0.35 < dd_pct <= -0.30: target_weight = 0.8
        elif dd_pct <= -0.35: target_weight = 1.0

        # 새롭게 더 높은 비중으로 진입해야 할 때만 목표 설정
        if target_weight > current_weight:
            target_portfolio[self.target_etf] = target_weight
            custom_state['current_weight'] = target_weight

        # 매도 로직 (하락률이 -10% 이상으로 회복되면 전량 매도)
        elif current_weight > 0 and dd_pct > -0.10:
             target_portfolio[self.target_etf] = 0.0 # 전량 매도 신호
             custom_state['current_weight'] = 0.0

        else: # 그 외의 경우 현재 보유 비중 유지
             target_portfolio[self.target_etf] = current_weight

        return target_portfolio


def run_portfolio_backtest(
    universe_dfs: dict,
    strategy_class: type,
    strategy_params: dict,
    initial_capital: float = 100_000_000, # 1억 원
    fee: float = 0.00015, # KIS 증권 수수료 (예시)
    tax: float = 0.002, # 증권거래세 (매도 시)
) -> dict:
    """
    포트폴리오 전략을 위한 범용 백테스팅 엔진
    """
    # 1. 전략 객체 생성 및 지표 계산
    strategy = strategy_class(universe_dfs, strategy_params)

    # 2. 백테스트 기간 설정 (모든 종목에 데이터가 있는 기간으로)
    common_index = None
    for df in universe_dfs.values():
        if common_index is None:
            common_index = df.index
        else:
            common_index = common_index.intersection(df.index)
    
    backtest_dates = common_index.sort_values()

    # 3. 변수 초기화
    capital = initial_capital
    portfolio = {}  # {'종목코드': {'수량': 10, '평단가': 50000}}
    equity_curve = []
    trades = []
    rebalancing_period = strategy_params.get('rebalancing_period', 1) # 리밸런싱 주기 (일)
    days_since_rebalance = 0

    # 4. 메인 백테스팅 루프
    for i, date in enumerate(backtest_dates):
        
        # 리밸런싱 주기 체크
        if i > 0 and (date.month != backtest_dates[i-1].month): # 매월 1회 리밸런싱
        # if days_since_rebalance < rebalancing_period:
        #     days_since_rebalance += 1
        # else:
            days_since_rebalance = 0 # 리밸런싱 실행

            # 현재 포트폴리오의 종목 코드 리스트
            current_holdings = {ticker: v['수량'] for ticker, v in portfolio.items()}
            
            # 전략으로부터 목표 포트폴리오 받기
            target_tickers = strategy.generate_signals(date, current_holdings)
            
            # 목표 비중에 따라 균등하게 투자 (Equal Weight)
            target_weight = 1.0 / len(target_tickers) if target_tickers else 0
            
            # 현재 자산 평가
            current_equity = capital
            for ticker, holding in portfolio.items():
                if date in universe_dfs[ticker].index:
                    current_price = universe_dfs[ticker].loc[date]['close']
                    current_equity += holding['수량'] * current_price
            
            # 매도 주문 생성 (목표 포트폴리오에 없는 종목)
            tickers_to_sell = [ticker for ticker in portfolio.keys() if ticker not in target_tickers]
            for ticker in tickers_to_sell:
                if date in universe_dfs[ticker].index:
                    price = universe_dfs[ticker].loc[date]['close']
                    quantity = portfolio[ticker]['수량']
                    sell_value = price * quantity
                    
                    capital += sell_value * (1 - fee - tax)
                    trades.append({'date': date, 'ticker': ticker, 'type': 'SELL', 'quantity': quantity, 'price': price})
                    del portfolio[ticker]

            # 매수/비중조절 주문 생성
            for ticker in target_tickers:
                target_value = current_equity * target_weight
                
                if date in universe_dfs[ticker].index:
                    price = universe_dfs[ticker].loc[date]['close']
                    current_value = portfolio.get(ticker, {}).get('수량', 0) * price
                    
                    value_diff = target_value - current_value
                    quantity_to_trade = int(value_diff / price)

                    if quantity_to_trade > 0: # 매수
                        trade_value = quantity_to_trade * price
                        capital -= trade_value * (1 + fee)
                        
                        if ticker in portfolio:
                            # 기존 보유 수량에 추가
                            total_quantity = portfolio[ticker]['수량'] + quantity_to_trade
                            total_cost = (portfolio[ticker]['평단가'] * portfolio[ticker]['수량']) + trade_value
                            portfolio[ticker]['평단가'] = total_cost / total_quantity
                            portfolio[ticker]['수량'] = total_quantity
                        else:
                            # 신규 매수
                            portfolio[ticker] = {'수량': quantity_to_trade, '평단가': price}
                        
                        trades.append({'date': date, 'ticker': ticker, 'type': 'BUY', 'quantity': quantity_to_trade, 'price': price})


        # 일별 자산 가치 기록
        equity = capital
        for ticker, holding in portfolio.items():
            if date in universe_dfs[ticker].index:
                price = universe_dfs[ticker].loc[date]['close']
                equity += holding['수량'] * price
        equity_curve.append({'date': date, 'equity': equity})

    # 5. 최종 결과 계산
    equity_df = pd.DataFrame(equity_curve).set_index('date')
    total_return = (equity_df['equity'].iloc[-1] / initial_capital - 1) * 100
    
    peak = equity_df['equity'].expanding(min_periods=1).max()
    drawdown = (equity_df['equity'] - peak) / peak
    mdd = drawdown.min() * 100

    return {
        'strategy': strategy_class.__name__,
        'params': strategy_params,
        'total_return_pct': total_return,
        'mdd_pct': mdd,
        'num_trades': len(trades),
        'initial_capital': initial_capital,
        'final_capital': equity_df['equity'].iloc[-1],
        'trades': trades,
        'equity_curve': equity_df
    }


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
    model: object = None # 외부에서 학습된 모델을 전달받기 위한 파라미터
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
        model (object, optional): 사전 학습된 머신러닝 모델

    Returns:
        dict: 백테스트 결과 (총 수익률, MDD, 거래 내역 등)
    """
    
    # 전략 객체 생성 및 신호 생성
    strategy = strategy_class(df_original, strategy_params, model=model)
    signals = strategy.generate_signals()
    df = strategy.df

    # ATR 계산 (손절/익절에 사용)
    if atr_stop_loss_multiplier is not None:
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)

    # 변수 초기화
    capital = initial_capital
    position_size = 0  # 보유 수량
    entry_price = 0
    stop_loss_price = 0 # ATR 기반 동적 손절가
    equity_curve = []
    trades = []
    
    position_type = None  # None, 'long', 'short'

    for i in range(len(df)):
        current_price = df['close'].iloc[i]
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]
        signal = signals.iloc[i]

        stop_loss_triggered = False
        # --- 0. 손절매(Stop-Loss) 확인 ---
        if position_type is not None and atr_stop_loss_multiplier is not None:
            exit_reason = None
            if position_type == 'long' and current_low <= stop_loss_price:
                exit_reason = 'stop_loss'
            elif position_type == 'short' and current_high >= stop_loss_price:
                exit_reason = 'stop_loss'
            
            if exit_reason:
                exit_price = stop_loss_price # SL 가격에 도달했다고 가정
                pnl = 0
                if position_type == 'long':
                    pnl = (exit_price - entry_price) * position_size * (1 - (fee * 2))
                else: # short
                    pnl = (entry_price - exit_price) * position_size * (1 - (fee * 2))
                
                capital += pnl
                
                last_trade = trades[-1]
                last_trade.update({
                    'exit_time': df.index[i], 'exit_price': exit_price, 'pnl': pnl,
                    'pnl_pct': ((exit_price / entry_price - 1) if position_type == 'long' else (entry_price / current_price - 1)) * 100,
                    'exit_reason': exit_reason
                })
                position_type = None
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
                    'exit_reason': 'signal'
                })
                position_type = None
                
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
                    'exit_reason': 'signal'
                })
                position_type = None

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
                    position_type = 'long'
                    trades.append({
                        'entry_time': df.index[i], 'entry_price': entry_price, 'type': 'LONG'
                    })
                    if atr_stop_loss_multiplier is not None and 'atr' in df.columns:
                        stop_loss_price = entry_price - (df['atr'].iloc[i] * atr_stop_loss_multiplier)


                # 숏 포지션 신규 진입
                elif signal == 'sell' and trade_type in ['short_only', 'long_and_short']:
                    entry_price = current_price
                    position_size = (trade_capital * leverage) / entry_price
                    position_type = 'short'
                    trades.append({
                        'entry_time': df.index[i], 'entry_price': entry_price, 'type': 'SHORT'
                    })
                    if atr_stop_loss_multiplier is not None and 'atr' in df.columns:
                        stop_loss_price = entry_price + (df['atr'].iloc[i] * atr_stop_loss_multiplier)

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


def run_multi_strategy_backtest(universe_dfs, strategy_configs, initial_capital, strategy_initial_capitals=None):
    """
    여러 전략을 동시에 실행하고 각 전략 및 전체 포트폴리오의 자산 변화를 추적하는 백테스터입니다.

    Args:
        universe_dfs (dict): 각 종목의 시계열 데이터를 담은 딕셔너리
        strategy_configs (dict): 전략 설정을 담은 딕셔너리
        initial_capital (float): 초기 자본금
        strategy_initial_capitals (dict, optional): 각 전략의 초기 자본금을 담은 딕셔너리

    Returns:
        tuple: 최종 자산 변화 곡선과 각 전략의 자산 변화 곡선
    """
    # 1. 전략 설정 초기화
    active_strategies = {name: config for name, config in strategy_configs.items() if config['capital_allocation'] > 0}
    if not active_strategies:
        logging.warning("모든 전략이 비활성화되었습니다. 백테스트를 진행할 전략이 없습니다.")
        return None, {}

    # 2. 전체 포트폴리오 자산 추적 데이터프레임 생성
    equity_df = pd.DataFrame(index=universe_dfs['KOSPI'].index, columns=['total_equity'] + [f'{name}_equity' for name in active_strategies.keys()])

    # 3. 전략 설정 초기화
    strategy_states = {}
    total_allocation = sum(config['capital_allocation'] for config in active_strategies.values() if config['capital_allocation'] > 0)

    # WFO의 연속적인 자본 흐름을 반영하기 위한 로직
    if strategy_initial_capitals:
        for strat_name in active_strategies:
            # 이전 기간에서 넘어온 자본이 있으면 사용, 없으면 초기 설정대로 배분
            start_capital = strategy_initial_capitals.get(strat_name, initial_capital * (active_strategies[strat_name]['capital_allocation'] / total_allocation))
            strategy_states[strat_name] = {
                'capital': start_capital,
                'equity_curve': pd.Series(dtype=np.float64),
                'custom_state': {}
            }
    else: # 첫번째 OOS 기간
        for strat_name, config in active_strategies.items():
            start_capital = initial_capital * (config['capital_allocation'] / total_allocation)
            strategy_states[strat_name] = {
                'capital': start_capital,
                'equity_curve': pd.Series(dtype=np.float64),
                'custom_state': {}
            }

    # 4. 백테스트 루프
    for date in tqdm(universe_dfs['KOSPI'].index, desc="Multi-Strategy Backtest"):
        # 현재 전체 포트폴리오 자산 계산
        current_total_equity = sum(state['capital'] for state in strategy_states.values())
        equity_df.loc[date, 'total_equity'] = current_total_equity

        # 각 전략별 자산 변화 계산
        for strat_name, state in strategy_states.items():
            strat = active_strategies[strat_name]['class']
            strat_params = active_strategies[strat_name]['params']
            strat_universe_tickers = active_strategies[strat_name]['universe']

            # 전략 인스턴스 생성
            strat_instance = strat(universe_dfs, strat_params)
            strat_instance.universe_with_indicators = strat_instance._add_indicators(universe_dfs)

            # 현재 전략의 총 자본 계산
            current_portfolio_value = sum(
                p['quantity'] * universe_dfs[ticker].loc[date, 'close']
                for ticker, p in state['portfolio'].items()
                if ticker in universe_dfs and date in universe_dfs[ticker].index
            )
            strategy_capital = state['capital'] + current_portfolio_value

            # 전략 신호 생성
            signals = strat_instance.generate_signals(date, state['portfolio'], state['custom_state'])

            # 거래 실행
            for ticker in signals:
                if ticker not in state['portfolio']:
                    # 신규 매수
                    quantity = int(strategy_capital * (signals[ticker] / 100))
                    if quantity > 0:
                        state['cash'] -= quantity * universe_dfs[ticker].loc[date, 'close']
                        state['portfolio'][ticker] = {'quantity': quantity, 'avg_price': universe_dfs[ticker].loc[date, 'close']}
                        logging.info(f"[{date.date()}] [{strat_name}] 매수(진입): {ticker}, 가격: {universe_dfs[ticker].loc[date, 'close']:,.0f}, 수량: {quantity}주")
                else:
                    # 기존 보유 종목 청산
                    current_qty = state['portfolio'][ticker]['quantity']
                    sell_qty = min(current_qty, quantity)
                    if sell_qty > 0:
                        state['cash'] += sell_qty * universe_dfs[ticker].loc[date, 'close']
                        state['portfolio'][ticker]['quantity'] -= sell_qty
                        logging.info(f"[{date.date()}] [{strat_name}] 매도(청산): {ticker}, 가격: {universe_dfs[ticker].loc[date, 'close']:,.0f}, 수량: {sell_qty}주")

            # 일별 자산 가치 계산
            state['equity_curve'].loc[date] = state['capital'] + state['cash']

        # 최종 자산 변화 계산
        equity_df.loc[date, 'total_equity'] = sum(state['capital'] + state['cash'] for state in strategy_states.values())

    # 5. 최종 결과 계산
    final_strategy_curves = {strat_name: state['equity_curve'] for strat_name, state in strategy_states.items()}
    compounded_equity = equity_df['total_equity'].cumsum() + initial_capital

    return compounded_equity, final_strategy_curves


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
        take_profit_pct=0.05    # 5% 익절
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
