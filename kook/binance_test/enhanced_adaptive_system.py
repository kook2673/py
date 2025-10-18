"""
향상된 적응형 트레이딩 시스템

=== 주요 개선사항 ===
1. 연속 손실 중단 조건 제거
2. DC 체크 강화 (마지막에 DC 조건 확인)
3. 더 많은 전략 옵션

=== 지원 전략 ===
- MA + DC (기존)
- MACD + DC (기존)
- BB + DC (기존)
- ~~통합 전략~~ (거래량 적어서 주석처리)
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class MarketStateDetector:
    """시장 상태 감지 클래스"""
    
    def __init__(self):
        self.trend_periods = [20, 50, 100]
        self.volatility_period = 20
        self.momentum_period = 14
    
    def detect_trend(self, data):
        """트렌드 상태 감지"""
        if len(data) < max(self.trend_periods):
            return 'unknown'
        
        short_trend = data['close'].iloc[-self.trend_periods[0]:].pct_change().mean()
        mid_trend = data['close'].iloc[-self.trend_periods[1]:].pct_change().mean()
        long_trend = data['close'].iloc[-self.trend_periods[2]:].pct_change().mean()
        
        trend_strength = (short_trend + mid_trend + long_trend) / 3
        
        if trend_strength > 0.001:
            return 'strong_uptrend'
        elif trend_strength > 0.0005:
            return 'uptrend'
        elif trend_strength < -0.001:
            return 'strong_downtrend'
        elif trend_strength < -0.0005:
            return 'downtrend'
        else:
            return 'sideways'
    
    def detect_volatility(self, data):
        """변동성 상태 감지"""
        if len(data) < self.volatility_period:
            return 'unknown'
        
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift())
        low_close = np.abs(data['low'] - data['close'].shift())
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = true_range.rolling(self.volatility_period).mean()
        current_atr = atr.iloc[-1]
        avg_atr = atr.mean()
        
        volatility_ratio = current_atr / avg_atr
        
        if volatility_ratio > 1.5:
            return 'high_volatility'
        elif volatility_ratio > 1.2:
            return 'medium_volatility'
        else:
            return 'low_volatility'
    
    def detect_momentum(self, data):
        """모멘텀 상태 감지"""
        if len(data) < self.momentum_period:
            return 'unknown'
        
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.momentum_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.momentum_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]
        
        ema_fast = data['close'].ewm(span=12).mean()
        ema_slow = data['close'].ewm(span=26).mean()
        macd_line = ema_fast - ema_slow
        macd_signal = macd_line.ewm(span=9).mean()
        macd_histogram = macd_line - macd_signal
        
        current_macd = macd_histogram.iloc[-1]
        
        if current_rsi > 70 and current_macd > 0:
            return 'strong_bullish'
        elif current_rsi > 60 and current_macd > 0:
            return 'bullish'
        elif current_rsi < 30 and current_macd < 0:
            return 'strong_bearish'
        elif current_rsi < 40 and current_macd < 0:
            return 'bearish'
        else:
            return 'neutral'
    
    def get_market_state(self, data):
        """종합 시장 상태 분석"""
        trend = self.detect_trend(data)
        volatility = self.detect_volatility(data)
        momentum = self.detect_momentum(data)
        
        return {
            'trend': trend,
            'volatility': volatility,
            'momentum': momentum,
            'timestamp': data.index[-1]
        }

class StrategySelector:
    """전략 자동 선택기 (향상된 버전)"""
    
    def __init__(self):
        self.strategies = {
            'ma_dc': 'MA + DC',
            'macd_dc': 'MACD + DC', 
            'bb_dc': 'BB + DC',
            'momentum_dc': 'Momentum + DC',
            'trend_dc': 'Trend + DC',
            'stoch_dc': 'Stochastic + DC',
            'williams_dc': 'Williams %R + DC',
            'cci_dc': 'CCI + DC',
            'combination_dc': 'Combination + DC'
        }
        
        # 시장 상태별 최적 전략 매핑 (2018년 하락장 특화)
        self.strategy_mapping = {
            # 강한 하락장 특화 (2018년 최적화)
            ('strong_downtrend', 'low_volatility', 'strong_bearish'): 'stoch_dc',    # 과매도 반등
            ('strong_downtrend', 'high_volatility', 'strong_bearish'): 'bb_dc',     # 변동성 활용
            ('downtrend', 'medium_volatility', 'bearish'): 'momentum_dc',          # 하락 모멘텀
            ('downtrend', 'high_volatility', 'bearish'): 'cci_dc',                 # 강한 하락 신호
            
            # 횡보장 (하락 중 반등)
            ('sideways', 'high_volatility', 'neutral'): 'bb_dc',                    # 변동성 활용
            ('sideways', 'medium_volatility', 'neutral'): 'stoch_dc',              # 과매수/과매도
            ('sideways', 'low_volatility', 'neutral'): 'combination_dc',           # 신중한 진입
            
            # 상승장 (드물지만 반등 시)
            ('strong_uptrend', 'low_volatility', 'strong_bullish'): 'trend_dc',
            ('uptrend', 'medium_volatility', 'bullish'): 'momentum_dc',
            ('uptrend', 'high_volatility', 'bullish'): 'macd_dc',
            
            # 특수 상황들
            ('strong_uptrend', 'high_volatility', 'strong_bullish'): 'cci_dc',
            ('uptrend', 'low_volatility', 'bullish'): 'williams_dc',
            ('downtrend', 'low_volatility', 'bearish'): 'ma_dc',                    # 기본 전략
            ('sideways', 'high_volatility', 'bullish'): 'combination_dc',
            ('sideways', 'high_volatility', 'bearish'): 'combination_dc'
        }
    
    def select_strategy(self, market_state):
        """시장 상태에 따른 전략 선택"""
        state_key = (market_state['trend'], market_state['volatility'], market_state['momentum'])
        
        if state_key in self.strategy_mapping:
            return self.strategy_mapping[state_key]
        
        # 부분 매칭 시도
        for (trend, vol, mom), strategy in self.strategy_mapping.items():
            if (market_state['trend'] == trend or 
                market_state['volatility'] == vol or 
                market_state['momentum'] == mom):
                return strategy
        
        return 'ma_dc'  # 기본 전략

class EnhancedAdaptiveTradingSystem:
    """향상된 적응형 트레이딩 시스템"""
    
    def __init__(self):
        self.market_detector = MarketStateDetector()
        self.strategy_selector = StrategySelector()
        
        # 전략별 파라미터 (9개 전략)
        self.strategy_params = {
            'ma_dc': {
                'sma_short': [3, 6, 9, 12, 15],
                'sma_long': [20, 30, 40, 50],
                'dc_period': [20, 25, 30]
            },
            'macd_dc': {
                'macd_fast': [8, 12, 16],
                'macd_slow': [21, 26, 34],
                'macd_signal': [7, 9, 12],
                'dc_period': [20, 25, 30]
            },
            'bb_dc': {
                'bb_period': [15, 20, 25],
                'bb_std': [1.5, 2.0, 2.5],
                'dc_period': [20, 25, 30]
            },
            'momentum_dc': {
                'momentum_period': [15, 20, 25],
                'momentum_threshold': [0.005, 0.01, 0.015],  # 하락장에서 더 민감하게
                'dc_period': [20, 25, 30]
            },
            'trend_dc': {
                'ma_short': [10, 15, 20],
                'ma_medium': [30, 40, 50],
                'ma_long': [60, 80, 100],
                'dc_period': [20, 25, 30]
            },
            'stoch_dc': {
                'stoch_k': [10, 14, 18],
                'stoch_d': [3, 5, 7],
                'stoch_oversold': [15, 20, 25],      # 하락장에서 더 민감하게
                'stoch_overbought': [75, 80, 85],    # 하락장에서 더 보수적으로
                'dc_period': [20, 25, 30]
            },
            'williams_dc': {
                'williams_period': [10, 14, 18],
                'williams_oversold': [-80, -75, -70],
                'williams_overbought': [-20, -25, -30],
                'dc_period': [20, 25, 30]
            },
            'cci_dc': {
                'cci_period': [15, 20, 25],
                'cci_oversold': [-80, -100, -120],    # 하락장에서 더 민감하게
                'cci_overbought': [120, 150, 180],    # 하락장에서 더 보수적으로
                'dc_period': [20, 25, 30]
            },
            'combination_dc': {
                'min_signals': [2, 3, 4],
                'signal_threshold': [0.6, 0.7, 0.8],
                'dc_period': [20, 25, 30]
            }
        }
        
        self.data = None
    
    def load_data(self, file_path):
        """데이터 로드"""
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            self.data = df
            return True
        return False
    
    def calculate_indicators(self, data, strategy, params):
        """지표 계산 (향상된 버전)"""
        df = data.copy()
        
        if strategy == 'ma_dc':
            df['sma_short'] = df['close'].rolling(params['sma_short']).mean()
            df['sma_long'] = df['close'].rolling(params['sma_long']).mean()
            
        elif strategy == 'macd_dc':
            ema_fast = df['close'].ewm(span=params['macd_fast']).mean()
            ema_slow = df['close'].ewm(span=params['macd_slow']).mean()
            df['macd_line'] = ema_fast - ema_slow
            df['macd_signal'] = df['macd_line'].ewm(span=params['macd_signal']).mean()
            
        elif strategy == 'bb_dc':
            df['bb_middle'] = df['close'].rolling(params['bb_period']).mean()
            bb_std_val = df['close'].rolling(params['bb_period']).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std_val * params['bb_std'])
            df['bb_lower'] = df['bb_middle'] - (bb_std_val * params['bb_std'])
            
        elif strategy == 'momentum_dc':
            df['momentum'] = df['close'].pct_change(params['momentum_period'])
            
        elif strategy == 'trend_dc':
            df['ma_short'] = df['close'].rolling(params['ma_short']).mean()
            df['ma_medium'] = df['close'].rolling(params['ma_medium']).mean()
            df['ma_long'] = df['close'].rolling(params['ma_long']).mean()
            
        elif strategy == 'stoch_dc':
            # Stochastic 계산
            low_min = df['low'].rolling(params['stoch_k']).min()
            high_max = df['high'].rolling(params['stoch_k']).max()
            df['stoch_k'] = 100 * (df['close'] - low_min) / (high_max - low_min)
            df['stoch_d'] = df['stoch_k'].rolling(params['stoch_d']).mean()
            
        elif strategy == 'williams_dc':
            # Williams %R 계산
            high_max = df['high'].rolling(params['williams_period']).max()
            low_min = df['low'].rolling(params['williams_period']).min()
            df['williams_r'] = -100 * (high_max - df['close']) / (high_max - low_min)
            
        elif strategy == 'cci_dc':
            # CCI 계산
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            sma_tp = typical_price.rolling(params['cci_period']).mean()
            mad = typical_price.rolling(params['cci_period']).apply(lambda x: np.mean(np.abs(x - x.mean())))
            df['cci'] = (typical_price - sma_tp) / (0.015 * mad)
            
        elif strategy == 'combination_dc':
            # 조합 전략용 기본 지표들
            df['sma_short'] = df['close'].rolling(10).mean()
            df['sma_long'] = df['close'].rolling(30).mean()
            
            ema_fast = df['close'].ewm(span=12).mean()
            ema_slow = df['close'].ewm(span=26).mean()
            df['macd_line'] = ema_fast - ema_slow
            df['macd_signal'] = df['macd_line'].ewm(span=9).mean()
            
            df['bb_middle'] = df['close'].rolling(20).mean()
            bb_std_val = df['close'].rolling(20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std_val * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std_val * 2)
            
        # elif strategy == 'integrated':  # 거래량 적어서 주석처리
        #     # 모든 지표 계산
        #     df['sma_short'] = df['close'].rolling(params['sma_short']).mean()
        #     df['sma_long'] = df['close'].rolling(params['sma_long']).mean()
        #     
        #     ema_fast = df['close'].ewm(span=params['macd_fast']).mean()
        #     ema_slow = df['close'].ewm(span=params['macd_slow']).mean()
        #     df['macd_line'] = ema_fast - ema_slow
        #     df['macd_signal'] = df['macd_line'].ewm(span=params['macd_signal']).mean()
        #     
        #     df['bb_middle'] = df['close'].rolling(params['bb_period']).mean()
        #     bb_std_val = df['close'].rolling(params['bb_period']).std()
        #     df['bb_upper'] = df['bb_middle'] + (bb_std_val * params['bb_std'])
        #     df['bb_lower'] = df['bb_middle'] - (bb_std_val * params['bb_std'])
        
        # 공통 지표 (DC, RSI) - DC 체크 강화
        df['dc_high'] = df['high'].rolling(params['dc_period']).max()
        df['dc_low'] = df['low'].rolling(params['dc_period']).min()
        df['dc_middle'] = (df['dc_high'] + df['dc_low']) / 2
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def generate_signals(self, df, strategy, params):
        """신호 생성 (DC 체크 강화)"""
        # 공통 DC 및 RSI 신호
        long_dc_signal = (df['close'] > df['dc_middle']) & (df['close'] > df['dc_low'] * 1.02)
        short_dc_signal = (df['close'] < df['dc_middle']) & (df['close'] < df['dc_high'] * 0.98)
        long_rsi_signal = df['rsi'] < 70
        short_rsi_signal = df['rsi'] > 30
        
        if strategy == 'ma_dc':
            long_ma_signal = (df['sma_short'] > df['sma_long']) & (df['sma_short'].shift(1) <= df['sma_long'].shift(1))
            short_ma_signal = (df['sma_short'] < df['sma_long']) & (df['sma_short'].shift(1) >= df['sma_long'].shift(1))
            
        elif strategy == 'macd_dc':
            long_ma_signal = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
            short_ma_signal = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
            
        elif strategy == 'bb_dc':
            long_ma_signal = (df['close'] <= df['bb_lower'] * 1.01)
            short_ma_signal = (df['close'] >= df['bb_upper'] * 0.99)
            
        elif strategy == 'momentum_dc':
            # 모멘텀 + DC 돌파 (트렌드 추종)
            momentum_long = df['momentum'] > params['momentum_threshold']
            momentum_short = df['momentum'] < -params['momentum_threshold']
            long_ma_signal = momentum_long & long_dc_signal
            short_ma_signal = momentum_short & short_dc_signal
            
        elif strategy == 'trend_dc':
            # 다중 MA 트렌드 + DC 돌파 (트렌드 추종)
            trend_long = (df['ma_short'] > df['ma_medium']) & (df['ma_medium'] > df['ma_long'])
            trend_short = (df['ma_short'] < df['ma_medium']) & (df['ma_medium'] < df['ma_long'])
            long_ma_signal = trend_long & long_dc_signal
            short_ma_signal = trend_short & short_dc_signal
            
        elif strategy == 'stoch_dc':
            # Stochastic만 (오실레이터 특성, DC 제거)
            long_ma_signal = (df['stoch_k'] < params['stoch_oversold']) & (df['stoch_d'] < params['stoch_oversold'])
            short_ma_signal = (df['stoch_k'] > params['stoch_overbought']) & (df['stoch_d'] > params['stoch_overbought'])
            
        elif strategy == 'williams_dc':
            # Williams %R만 (오실레이터 특성, DC 제거)
            long_ma_signal = df['williams_r'] < params['williams_oversold']
            short_ma_signal = df['williams_r'] > params['williams_overbought']
            
        elif strategy == 'cci_dc':
            # CCI만 (트렌드 강도 측정, DC 제거)
            long_ma_signal = df['cci'] < params['cci_oversold']
            short_ma_signal = df['cci'] > params['cci_overbought']
            
        elif strategy == 'combination_dc':
            # 조합 전략: 여러 신호의 합의 (DC 제거, 신호 합의만)
            ma_signal = (df['sma_short'] > df['sma_long']).astype(int)
            macd_signal = (df['macd_line'] > df['macd_signal']).astype(int)
            bb_signal = (df['close'] <= df['bb_lower']).astype(int)
            
            signal_count = ma_signal + macd_signal + bb_signal
            min_signals = params['min_signals']
            
            long_ma_signal = signal_count >= min_signals
            short_ma_signal = signal_count <= (3 - min_signals)
            
        # elif strategy == 'integrated':  # 거래량 적어서 주석처리
        #     # 통합 전략: 모든 지표의 합의
        #     long_ma_signal_base = (df['sma_short'] > df['sma_long']) & (df['sma_short'].shift(1) <= df['sma_long'].shift(1))
        #     short_ma_signal_base = (df['sma_short'] < df['sma_long']) & (df['sma_short'].shift(1) >= df['sma_long'].shift(1))
        #     
        #     long_macd_signal = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
        #     short_macd_signal = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
        #     
        #     long_bb_signal = (df['close'] <= df['bb_lower'] * 1.01)
        #     short_bb_signal = (df['close'] >= df['bb_upper'] * 0.99)
        #     
        #     # 통합 신호 (2개 이상의 지표가 동의할 때)
        #     long_ma_signal = (long_ma_signal_base.astype(int) + long_macd_signal.astype(int) + long_bb_signal.astype(int)) >= 2
        #     short_ma_signal = (short_ma_signal_base.astype(int) + short_macd_signal.astype(int) + short_bb_signal.astype(int)) >= 2
        
        # 최종 신호 (전략별 DC 적용)
        if strategy in ['ma_dc', 'macd_dc', 'momentum_dc', 'trend_dc']:
            # DC 필수 전략들
            df['long_signal'] = long_ma_signal & long_dc_signal & long_rsi_signal
            df['short_signal'] = short_ma_signal & short_dc_signal & short_rsi_signal
        else:
            # DC 제거 전략들 (bb_dc, stoch_dc, williams_dc, cci_dc, combination_dc)
            df['long_signal'] = long_ma_signal & long_rsi_signal
            df['short_signal'] = short_ma_signal & short_rsi_signal
        
        return df
    
    def run_enhanced_backtest(self, start_date, end_date, initial_capital=10000):
        """향상된 백테스트 실행 (연속 손실 중단 제거)"""
        print("=== 향상된 적응형 트레이딩 시스템 백테스트 시작 ===")
        
        # 데이터 필터링
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        mask = (self.data.index >= start_dt) & (self.data.index <= end_dt)
        test_data = self.data[mask].copy()
        
        if len(test_data) == 0:
            print("테스트 데이터가 없습니다.")
            return None
        
        print(f"테스트 기간: {start_date} ~ {end_date}")
        print(f"데이터 길이: {len(test_data)}개 캔들")
        
        # 백테스트 실행
        results = []
        current_capital = initial_capital
        position = None
        entry_price = 0
        trades = []
        
        # 윈도우 크기
        window_size = 100
        
        for i in range(window_size, len(test_data)):
            # 현재 시점 데이터
            current_data = test_data.iloc[:i+1]
            
            # 시장 상태 분석
            market_state = self.market_detector.get_market_state(current_data)
            
            # 전략 선택
            selected_strategy = self.strategy_selector.select_strategy(market_state)
            
            # 파라미터 선택 (첫 번째 값 사용)
            base_params = self.strategy_params[selected_strategy]
            params = {k: v[0] for k, v in base_params.items()}
            
            # 지표 계산 및 신호 생성
            df_with_indicators = self.calculate_indicators(current_data, selected_strategy, params)
            df_with_signals = self.generate_signals(df_with_indicators, selected_strategy, params)
            
            # 현재 신호
            current_row = df_with_signals.iloc[-1]
            
            # 포지션 관리
            if position is None:
                # 진입 신호
                if current_row['long_signal']:
                    position = 'long'
                    entry_price = current_row['close']
                    print(f"{current_row.name}: 롱 진입 (전략: {selected_strategy}, 가격: {entry_price:.2f})")
                elif current_row['short_signal']:
                    position = 'short'
                    entry_price = current_row['close']
                    print(f"{current_row.name}: 숏 진입 (전략: {selected_strategy}, 가격: {entry_price:.2f})")
            
            else:
                # 청산 신호
                should_exit = False
                exit_reason = ""
                
                if position == 'long':
                    if current_row['short_signal']:
                        should_exit = True
                        exit_reason = "숏 신호"
                    elif current_row['rsi'] > 80:
                        should_exit = True
                        exit_reason = "RSI 과매수"
                    elif current_row['close'] <= entry_price * 0.97:  # 3% 손절
                        should_exit = True
                        exit_reason = "손절매"
                
                elif position == 'short':
                    if current_row['long_signal']:
                        should_exit = True
                        exit_reason = "롱 신호"
                    elif current_row['rsi'] < 20:
                        should_exit = True
                        exit_reason = "RSI 과매도"
                    elif current_row['close'] >= entry_price * 1.03:  # 3% 손절
                        should_exit = True
                        exit_reason = "손절매"
                
                if should_exit:
                    # 거래 실행
                    exit_price = current_row['close']
                    pnl = self._calculate_pnl(entry_price, exit_price, current_capital, position)
                    current_capital += pnl
                    
                    # 수수료 계산
                    fee_rate = 0.0005
                    if position == 'long':
                        entry_fee = entry_price * fee_rate
                        exit_fee = exit_price * fee_rate
                    else:
                        entry_fee = entry_price * fee_rate
                        exit_fee = exit_price * fee_rate
                    total_fee = entry_fee + exit_fee
                    
                    trades.append({
                        'entry_time': entry_price,
                        'exit_time': exit_price,
                        'position': position,
                        'pnl': pnl,
                        'strategy': selected_strategy,
                        'exit_reason': exit_reason,
                        'entry_fee': entry_fee,
                        'exit_fee': exit_fee,
                        'total_fee': total_fee
                    })
                    
                    # PnL에 따른 색상 표시 (수수료 정보 포함)
                    if pnl > 0:
                        print(f"{current_row.name}: {position} 청산 🟢 ({exit_reason}, PnL: {pnl:.2f}, 수수료: {total_fee:.2f}, 자본: {current_capital:.2f})")
                    else:
                        print(f"{current_row.name}: {position} 청산 🔴 ({exit_reason}, PnL: {pnl:.2f}, 수수료: {total_fee:.2f}, 자본: {current_capital:.2f})")
                    
                    position = None
        
        # 결과 계산
        total_return = (current_capital - initial_capital) / initial_capital * 100
        winning_trades = len([t for t in trades if t['pnl'] > 0])
        win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0
        
        # 최대 낙폭 계산
        max_drawdown = self._calculate_max_drawdown(initial_capital, trades)
        
        result = {
            'total_return': total_return,
            'final_capital': current_capital,
            'total_trades': len(trades),
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'trades': trades
        }
        
        return result
    
    def _calculate_pnl(self, entry_price, exit_price, capital, position_type):
        """PnL 계산 (수수료 포함)"""
        fee_rate = 0.0005  # 0.05% 수수료
        
        if position_type == 'long':
            # 롱 포지션: 매수 시 수수료 지불, 매도 시 수수료 지불
            entry_with_fee = entry_price * (1 + fee_rate)  # 매수 시 수수료
            exit_with_fee = exit_price * (1 - fee_rate)    # 매도 시 수수료
            amount = capital / entry_with_fee
            pnl = (exit_with_fee - entry_with_fee) * amount
        else:  # short
            # 숏 포지션: 매도 시 수수료 지불, 매수 시 수수료 지불
            entry_with_fee = entry_price * (1 - fee_rate)  # 매도 시 수수료
            exit_with_fee = exit_price * (1 + fee_rate)    # 매수 시 수수료
            amount = capital / entry_with_fee
            pnl = (entry_with_fee - exit_with_fee) * amount
        
        return pnl
    
    def _calculate_max_drawdown(self, initial_capital, trades):
        """최대 낙폭 계산"""
        if not trades:
            return 0.0
        
        capital_series = [initial_capital]
        for trade in trades:
            capital_series.append(capital_series[-1] + trade['pnl'])
        
        capital_series = np.array(capital_series)
        peak = np.maximum.accumulate(capital_series)
        drawdown = (peak - capital_series) / peak * 100
        
        return np.max(drawdown)

def main():
    """메인 실행 함수"""
    print("=== 향상된 적응형 트레이딩 시스템 ===")
    
    # 시스템 초기화
    system = EnhancedAdaptiveTradingSystem()
    
    # 데이터 로드
    data_files = [
        "data/BTCUSDT/5m/BTCUSDT_5m_2024.csv"
    ]
    
    all_data = []
    for file_path in data_files:
        if system.load_data(file_path):
            all_data.append(system.data)
            print(f"데이터 로드 완료: {file_path}")
    
    if all_data:
        system.data = pd.concat(all_data, ignore_index=False).sort_index()
        print(f"전체 데이터: {len(system.data)}개 캔들")
        
        # 향상된 시스템 테스트
        result = system.run_enhanced_backtest('2024-01-01', '2024-12-31')
        
        if result:
            print(f"\n향상된 시스템 결과:")
            print(f"  총 수익률: {result['total_return']:.2f}%")
            print(f"  최종 자본: {result['final_capital']:.2f}")
            print(f"  총 거래: {result['total_trades']}회")
            print(f"  승률: {result['win_rate']:.2f}%")
            print(f"  최대 낙폭: {result['max_drawdown']:.2f}%")
            
            # 전략별 거래 분포
            strategy_trades = {}
            for trade in result['trades']:
                strategy = trade['strategy']
                if strategy not in strategy_trades:
                    strategy_trades[strategy] = 0
                strategy_trades[strategy] += 1
            
            print(f"\n전략별 거래 분포:")
            for strategy, count in strategy_trades.items():
                percentage = (count / result['total_trades']) * 100
                print(f"  {strategy}: {count}회 ({percentage:.1f}%)")
            
            # 결과 저장
            output = {
                'system_type': 'Enhanced Adaptive Trading System',
                'test_period': '2024-01-01 ~ 2024-12-31',
                'improvements': [
                    '연속 손실 중단 조건 제거',
                    '스켈핑 전략 추가',
                    'DC 체크 강화',
                    '더 많은 전략 옵션'
                ],
                'result': result,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open('enhanced_adaptive_results.json', 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            print(f"\n결과가 enhanced_adaptive_results.json에 저장되었습니다.")
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
