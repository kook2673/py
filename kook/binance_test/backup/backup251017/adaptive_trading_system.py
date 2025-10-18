"""
시장 반응형 자동 튜닝 트레이딩 시스템

=== 주요 기능 ===
1. 시장 상태 실시간 감지 (트렌드, 변동성, 모멘텀)
2. 동적 파라미터 자동 조정
3. 멀티 전략 자동 선택 (MA+DC, MACD+DC, BB+DC, 통합전략)
4. 리스크 관리 자동화
5. 성과 기반 자동 튜닝

=== 지원 전략 ===
- MA + DC (기존)
- MACD + DC
- BB + DC  
- 통합 전략 (모든 지표 조합)
- 시장 상황별 특화 전략
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
        self.trend_periods = [20, 50, 100]  # 트렌드 분석 기간
        self.volatility_period = 20  # 변동성 분석 기간
        self.momentum_period = 14  # 모멘텀 분석 기간
    
    def detect_trend(self, data):
        """트렌드 상태 감지"""
        if len(data) < max(self.trend_periods):
            return 'unknown'
        
        # 단기/중기/장기 트렌드 분석
        short_trend = data['close'].iloc[-self.trend_periods[0]:].pct_change().mean()
        mid_trend = data['close'].iloc[-self.trend_periods[1]:].pct_change().mean()
        long_trend = data['close'].iloc[-self.trend_periods[2]:].pct_change().mean()
        
        # 트렌드 강도 계산
        trend_strength = (short_trend + mid_trend + long_trend) / 3
        
        if trend_strength > 0.001:  # 0.1% 이상 상승
            return 'strong_uptrend'
        elif trend_strength > 0.0005:  # 0.05% 이상 상승
            return 'uptrend'
        elif trend_strength < -0.001:  # 0.1% 이상 하락
            return 'strong_downtrend'
        elif trend_strength < -0.0005:  # 0.05% 이상 하락
            return 'downtrend'
        else:
            return 'sideways'
    
    def detect_volatility(self, data):
        """변동성 상태 감지"""
        if len(data) < self.volatility_period:
            return 'unknown'
        
        # ATR 기반 변동성 계산
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
        
        # RSI 기반 모멘텀
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.momentum_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.momentum_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]
        
        # MACD 기반 모멘텀
        ema_fast = data['close'].ewm(span=12).mean()
        ema_slow = data['close'].ewm(span=26).mean()
        macd_line = ema_fast - ema_slow
        macd_signal = macd_line.ewm(span=9).mean()
        macd_histogram = macd_line - macd_signal
        
        current_macd = macd_histogram.iloc[-1]
        
        # 모멘텀 상태 판단
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

class AdaptiveParameterTuner:
    """적응형 파라미터 튜너"""
    
    def __init__(self):
        self.performance_history = []
        self.parameter_history = []
        self.adaptation_threshold = -5.0  # 5% 이상 손실시 파라미터 조정
        
    def update_performance(self, performance, parameters):
        """성과 업데이트"""
        self.performance_history.append(performance)
        self.parameter_history.append(parameters)
        
        # 최근 10개 성과만 유지
        if len(self.performance_history) > 10:
            self.performance_history = self.performance_history[-10:]
            self.parameter_history = self.parameter_history[-10:]
    
    def should_adapt(self):
        """파라미터 조정 필요 여부 판단"""
        if len(self.performance_history) < 3:
            return False
        
        # 최근 3개 성과가 모두 임계값 이하인 경우
        recent_performance = self.performance_history[-3:]
        return all(p < self.adaptation_threshold for p in recent_performance)
    
    def get_adaptive_parameters(self, base_params, market_state):
        """시장 상태에 따른 적응형 파라미터 생성"""
        adapted_params = base_params.copy()
        
        # 트렌드에 따른 조정
        if market_state['trend'] in ['strong_uptrend', 'strong_downtrend']:
            # 강한 트렌드: 더 민감한 파라미터
            if 'sma_short' in adapted_params:
                adapted_params['sma_short'] = max(3, adapted_params['sma_short'] - 2)
            if 'sma_long' in adapted_params:
                adapted_params['sma_long'] = max(10, adapted_params['sma_long'] - 5)
        elif market_state['trend'] == 'sideways':
            # 횡보: 더 안정적인 파라미터
            if 'sma_short' in adapted_params:
                adapted_params['sma_short'] = min(20, adapted_params['sma_short'] + 3)
            if 'sma_long' in adapted_params:
                adapted_params['sma_long'] = min(60, adapted_params['sma_long'] + 10)
        
        # 변동성에 따른 조정
        if market_state['volatility'] == 'high_volatility':
            # 고변동성: 더 큰 DC 기간
            if 'dc_period' in adapted_params:
                adapted_params['dc_period'] = min(50, adapted_params['dc_period'] + 10)
        elif market_state['volatility'] == 'low_volatility':
            # 저변동성: 더 작은 DC 기간
            if 'dc_period' in adapted_params:
                adapted_params['dc_period'] = max(15, adapted_params['dc_period'] - 5)
        
        return adapted_params

class StrategySelector:
    """전략 자동 선택기"""
    
    def __init__(self):
        self.strategies = {
            'ma_dc': 'MA + DC',
            'macd_dc': 'MACD + DC', 
            'bb_dc': 'BB + DC',
            'integrated': '통합 전략'
        }
        
        # 시장 상태별 최적 전략 매핑
        self.strategy_mapping = {
            ('strong_uptrend', 'low_volatility', 'strong_bullish'): 'ma_dc',
            ('strong_downtrend', 'low_volatility', 'strong_bearish'): 'ma_dc',
            ('uptrend', 'medium_volatility', 'bullish'): 'macd_dc',
            ('downtrend', 'medium_volatility', 'bearish'): 'macd_dc',
            ('sideways', 'high_volatility', 'neutral'): 'bb_dc',
            ('sideways', 'medium_volatility', 'neutral'): 'integrated'
        }
    
    def select_strategy(self, market_state):
        """시장 상태에 따른 전략 선택"""
        state_key = (market_state['trend'], market_state['volatility'], market_state['momentum'])
        
        # 정확한 매칭이 있는 경우
        if state_key in self.strategy_mapping:
            return self.strategy_mapping[state_key]
        
        # 부분 매칭 시도
        for (trend, vol, mom), strategy in self.strategy_mapping.items():
            if (market_state['trend'] == trend or 
                market_state['volatility'] == vol or 
                market_state['momentum'] == mom):
                return strategy
        
        # 기본 전략 (MA + DC)
        return 'ma_dc'

class RiskManager:
    """리스크 관리자"""
    
    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.max_drawdown = 0.0
        self.consecutive_losses = 0
        self.max_consecutive_losses = 3
        
    def update_capital(self, new_capital):
        """자본 업데이트"""
        self.current_capital = new_capital
        
        # 최대 낙폭 계산
        current_drawdown = (self.initial_capital - self.current_capital) / self.initial_capital * 100
        self.max_drawdown = max(self.max_drawdown, current_drawdown)
    
    def update_trade_result(self, is_winning):
        """거래 결과 업데이트"""
        if is_winning:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
    
    def get_position_size(self, base_size=1.0):
        """포지션 크기 조정"""
        # 연속 손실에 따른 크기 감소
        if self.consecutive_losses >= self.max_consecutive_losses:
            return base_size * 0.5  # 50% 감소
        
        # 최대 낙폭에 따른 크기 조정
        if self.max_drawdown > 20:  # 20% 이상 낙폭
            return base_size * 0.3  # 30%로 감소
        elif self.max_drawdown > 10:  # 10% 이상 낙폭
            return base_size * 0.7  # 70%로 감소
        
        return base_size
    
    def should_stop_trading(self):
        """거래 중단 여부 판단"""
        return (self.max_drawdown > 30 or  # 30% 이상 낙폭
                self.consecutive_losses >= 5)  # 5회 연속 손실

class AdaptiveTradingSystem:
    """적응형 트레이딩 시스템 메인 클래스"""
    
    def __init__(self):
        self.market_detector = MarketStateDetector()
        self.parameter_tuner = AdaptiveParameterTuner()
        self.strategy_selector = StrategySelector()
        self.risk_manager = RiskManager()
        
        # 전략별 기본 파라미터
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
            'integrated': {
                'sma_short': [6, 9, 12],
                'sma_long': [25, 30, 40],
                'macd_fast': [10, 12, 14],
                'macd_slow': [21, 26, 30],
                'macd_signal': [8, 9, 10],
                'bb_period': [18, 20, 22],
                'bb_std': [1.8, 2.0, 2.2],
                'dc_period': [22, 25, 28]
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
        """지표 계산"""
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
            
        elif strategy == 'integrated':
            # 모든 지표 계산
            df['sma_short'] = df['close'].rolling(params['sma_short']).mean()
            df['sma_long'] = df['close'].rolling(params['sma_long']).mean()
            
            ema_fast = df['close'].ewm(span=params['macd_fast']).mean()
            ema_slow = df['close'].ewm(span=params['macd_slow']).mean()
            df['macd_line'] = ema_fast - ema_slow
            df['macd_signal'] = df['macd_line'].ewm(span=params['macd_signal']).mean()
            
            df['bb_middle'] = df['close'].rolling(params['bb_period']).mean()
            bb_std_val = df['close'].rolling(params['bb_period']).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std_val * params['bb_std'])
            df['bb_lower'] = df['bb_middle'] - (bb_std_val * params['bb_std'])
        
        # 공통 지표 (DC, RSI)
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
    
    def generate_signals(self, df, strategy):
        """신호 생성"""
        # 공통 DC 및 RSI 신호 (모든 전략에서 사용)
        long_dc_signal = (df['close'] > df['dc_middle']) & (df['close'] > df['dc_low'] * 1.02)
        short_dc_signal = (df['close'] < df['dc_middle']) & (df['close'] < df['dc_high'] * 0.98)
        long_rsi_signal = df['rsi'] < 70
        short_rsi_signal = df['rsi'] > 30
        
        if strategy == 'ma_dc':
            # MA + DC 신호
            long_ma_signal = (df['sma_short'] > df['sma_long']) & (df['sma_short'].shift(1) <= df['sma_long'].shift(1))
            short_ma_signal = (df['sma_short'] < df['sma_long']) & (df['sma_short'].shift(1) >= df['sma_long'].shift(1))
            
        elif strategy == 'macd_dc':
            # MACD + DC 신호
            long_ma_signal = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
            short_ma_signal = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
            
        elif strategy == 'bb_dc':
            # BB + DC 신호
            long_ma_signal = (df['close'] <= df['bb_lower'] * 1.01)
            short_ma_signal = (df['close'] >= df['bb_upper'] * 0.99)
            
        elif strategy == 'integrated':
            # 통합 전략: 모든 지표의 합의
            # MA 신호
            long_ma_signal_base = (df['sma_short'] > df['sma_long']) & (df['sma_short'].shift(1) <= df['sma_long'].shift(1))
            short_ma_signal_base = (df['sma_short'] < df['sma_long']) & (df['sma_short'].shift(1) >= df['sma_long'].shift(1))
            
            # MACD 신호
            long_macd_signal = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
            short_macd_signal = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
            
            # BB 신호
            long_bb_signal = (df['close'] <= df['bb_lower'] * 1.01)
            short_bb_signal = (df['close'] >= df['bb_upper'] * 0.99)
            
            # 통합 신호 (2개 이상의 지표가 동의할 때)
            long_ma_signal = (long_ma_signal_base.astype(int) + long_macd_signal.astype(int) + long_bb_signal.astype(int)) >= 2
            short_ma_signal = (short_ma_signal_base.astype(int) + short_macd_signal.astype(int) + short_bb_signal.astype(int)) >= 2
        
        # 최종 신호
        df['long_signal'] = long_ma_signal & long_dc_signal & long_rsi_signal
        df['short_signal'] = short_ma_signal & short_dc_signal & short_rsi_signal
        
        return df
    
    def run_adaptive_backtest(self, start_date, end_date, initial_capital=10000):
        """적응형 백테스트 실행"""
        print("=== 적응형 트레이딩 시스템 백테스트 시작 ===")
        
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
        
        # 윈도우 크기 (시장 상태 분석용)
        window_size = 100
        
        for i in range(window_size, len(test_data)):
            # 현재 시점 데이터
            current_data = test_data.iloc[:i+1]
            
            # 시장 상태 분석
            market_state = self.market_detector.get_market_state(current_data)
            
            # 전략 선택
            selected_strategy = self.strategy_selector.select_strategy(market_state)
            
            # 파라미터 적응
            base_params = self.strategy_params[selected_strategy]
            adapted_params = self.parameter_tuner.get_adaptive_parameters(
                {k: v[0] for k, v in base_params.items()}, market_state
            )
            
            # 지표 계산 및 신호 생성
            df_with_indicators = self.calculate_indicators(current_data, selected_strategy, adapted_params)
            df_with_signals = self.generate_signals(df_with_indicators, selected_strategy)
            
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
                    elif current_row['close'] <= entry_price * 0.95:  # 5% 손절
                        should_exit = True
                        exit_reason = "손절매"
                
                elif position == 'short':
                    if current_row['long_signal']:
                        should_exit = True
                        exit_reason = "롱 신호"
                    elif current_row['rsi'] < 20:
                        should_exit = True
                        exit_reason = "RSI 과매도"
                    elif current_row['close'] >= entry_price * 1.05:  # 5% 손절
                        should_exit = True
                        exit_reason = "손절매"
                
                if should_exit:
                    # 거래 실행
                    exit_price = current_row['close']
                    pnl = self._calculate_pnl(entry_price, exit_price, current_capital, position)
                    current_capital += pnl
                    
                    is_winning = pnl > 0
                    self.risk_manager.update_trade_result(is_winning)
                    self.risk_manager.update_capital(current_capital)
                    
                    trades.append({
                        'entry_time': entry_price,
                        'exit_time': exit_price,
                        'position': position,
                        'pnl': pnl,
                        'strategy': selected_strategy,
                        'exit_reason': exit_reason
                    })
                    
                    print(f"{current_row.name}: {position} 청산 ({exit_reason}, PnL: {pnl:.2f}, 자본: {current_capital:.2f})")
                    
                    position = None
            
            # 리스크 관리 체크
            if self.risk_manager.should_stop_trading():
                print(f"리스크 관리에 의해 거래 중단 (최대낙폭: {self.risk_manager.max_drawdown:.2f}%)")
                break
        
        # 결과 계산
        total_return = (current_capital - initial_capital) / initial_capital * 100
        winning_trades = len([t for t in trades if t['pnl'] > 0])
        win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0
        
        result = {
            'total_return': total_return,
            'final_capital': current_capital,
            'total_trades': len(trades),
            'win_rate': win_rate,
            'max_drawdown': self.risk_manager.max_drawdown,
            'trades': trades
        }
        
        return result
    
    def _calculate_pnl(self, entry_price, exit_price, capital, position_type):
        """PnL 계산"""
        fee_rate = 0.001  # 0.1% 수수료
        
        if position_type == 'long':
            entry_with_fee = entry_price * (1 + fee_rate)
            exit_with_fee = exit_price * (1 - fee_rate)
            amount = capital / entry_with_fee
            pnl = (exit_with_fee - entry_with_fee) * amount
        else:  # short
            entry_with_fee = entry_price * (1 - fee_rate)
            exit_with_fee = exit_price * (1 + fee_rate)
            amount = capital / entry_with_fee
            pnl = (entry_with_fee - exit_with_fee) * amount
        
        return pnl
    
    def run_comparison_test(self, start_date, end_date):
        """기존 WFO와 적응형 시스템 비교 테스트"""
        print("\n=== 적응형 시스템 vs 기존 WFO 비교 ===")
        
        # 적응형 시스템 테스트
        adaptive_result = self.run_adaptive_backtest(start_date, end_date)
        
        if adaptive_result:
            print(f"\n적응형 시스템 결과:")
            print(f"  총 수익률: {adaptive_result['total_return']:.2f}%")
            print(f"  최종 자본: {adaptive_result['final_capital']:.2f}")
            print(f"  총 거래: {adaptive_result['total_trades']}회")
            print(f"  승률: {adaptive_result['win_rate']:.2f}%")
            print(f"  최대 낙폭: {adaptive_result['max_drawdown']:.2f}%")
        
        return adaptive_result

def main():
    """메인 실행 함수"""
    print("=== 시장 반응형 자동 튜닝 트레이딩 시스템 ===")
    
    # 시스템 초기화
    system = AdaptiveTradingSystem()
    
    # 데이터 로드 (2024년 데이터 사용)
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
        
        # 적응형 시스템 테스트
        result = system.run_comparison_test('2024-01-01', '2024-12-31')
        
        if result:
            # 결과 저장
            output = {
                'system_type': 'Adaptive Trading System',
                'test_period': '2024-01-01 ~ 2024-12-31',
                'result': result,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open('adaptive_trading_results.json', 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            print(f"\n결과가 adaptive_trading_results.json에 저장되었습니다.")
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
