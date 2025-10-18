#-*-coding:utf-8 -*-
'''
다중 전략 포트폴리오 관리 시스템
=====================================

=== 주요 기능 ===
1. 10개 전략을 동시에 실행
2. 자산을 100등분하여 각 전략에 동적 배분
3. 승률 기반 전략 활성화/비활성화
4. 실시간 성과 모니터링 및 리밸런싱
5. 백테스트 및 시각화

=== 지원 전략 ===
1. 변동성 돌파 전략 (Volatility Breakout)
2. 모멘텀 전략 (Momentum Strategy)
3. 스윙 트레이딩 (Swing Trading)
4. 브레이크아웃 전략 (Breakout Strategy)
5. 스캘핑 전략 (Scalping Strategy)
6. RSI 전략 (RSI Strategy)
7. MACD 전략 (MACD Strategy)
8. 볼린저밴드 전략 (Bollinger Bands)
9. 이평선 전략 (Moving Average)
10. 스토캐스틱 전략 (Stochastic)

=== 사용법 ===
python multi_strategy_portfolio_manager.py --start 2024-01-01 --end 2024-12-31 --capital 100000
'''

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import os
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import warnings
warnings.filterwarnings('ignore')

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

class StrategyBase:
    """전략 기본 클래스"""
    
    def __init__(self, name: str, timeframe: str = '1h'):
        self.name = name
        self.timeframe = timeframe
        self.is_active = True
        self.performance_history = []
        self.current_allocation = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_return = 0.0
        self.max_drawdown = 0.0
        self.win_rate = 0.0
        self.sharpe_ratio = 0.0
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """매매 신호 계산 (하위 클래스에서 구현)"""
        raise NotImplementedError
        
    def calculate_performance(self, data: pd.DataFrame, signals: pd.DataFrame) -> Dict[str, float]:
        """성과 계산"""
        if len(signals) == 0:
            return {
                'total_return': 0.0,
                'max_drawdown': 0.0,
                'win_rate': 0.0,
                'sharpe_ratio': 0.0,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0
            }
        
        # 간단한 성과 계산 (실제로는 더 복잡한 로직 필요)
        returns = data['close'].pct_change()
        signal_returns = returns * signals['signal'].shift(1)
        signal_returns = signal_returns.dropna()
        
        total_return = signal_returns.sum() * 100
        win_rate = (signal_returns > 0).mean() * 100
        total_trades = len(signal_returns)
        winning_trades = (signal_returns > 0).sum()
        losing_trades = total_trades - winning_trades
        
        # 최대 낙폭 계산
        cumulative_returns = (1 + signal_returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        max_drawdown = drawdown.min() * 100
        
        # 샤프 비율 계산
        if signal_returns.std() > 0:
            sharpe_ratio = signal_returns.mean() / signal_returns.std() * np.sqrt(252)
        else:
            sharpe_ratio = 0.0
            
        return {
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'sharpe_ratio': sharpe_ratio,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades
        }
        
    def update_performance(self, performance: Dict[str, float]):
        """성과 업데이트"""
        self.total_return = performance['total_return']
        self.max_drawdown = performance['max_drawdown']
        self.win_rate = performance['win_rate']
        self.sharpe_ratio = performance['sharpe_ratio']
        self.total_trades = performance['total_trades']
        self.winning_trades = performance['winning_trades']
        self.losing_trades = performance['losing_trades']
        
        self.performance_history.append({
            'timestamp': datetime.now(),
            'total_return': self.total_return,
            'win_rate': self.win_rate,
            'sharpe_ratio': self.sharpe_ratio
        })

class VolatilityBreakoutStrategy(StrategyBase):
    """변동성 돌파 전략"""
    
    def __init__(self, lookback_period: int = 20, k: float = 0.5):
        super().__init__("변동성돌파", "1h")
        self.lookback_period = lookback_period
        self.k = k
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        
        # 변동성 계산
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift(1))
        low_close = np.abs(data['low'] - data['close'].shift(1))
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = true_range.rolling(window=self.lookback_period).mean()
        
        # 돌파 레벨 계산
        upper_band = data['close'].shift(1) + self.k * atr
        lower_band = data['close'].shift(1) - self.k * atr
        
        # 매수/매도 신호
        signals.loc[data['close'] > upper_band, 'signal'] = 1
        signals.loc[data['close'] < lower_band, 'signal'] = -1
        
        return signals

class MomentumStrategy(StrategyBase):
    """모멘텀 전략"""
    
    def __init__(self, short_period: int = 12, long_period: int = 26):
        super().__init__("모멘텀", "1h")
        self.short_period = short_period
        self.long_period = long_period
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        
        # 모멘텀 계산
        momentum = data['close'].pct_change(self.short_period)
        
        # 이동평균
        ma_short = data['close'].rolling(window=self.short_period).mean()
        ma_long = data['close'].rolling(window=self.long_period).mean()
        
        # 매수/매도 신호
        signals.loc[(momentum > 0) & (ma_short > ma_long), 'signal'] = 1
        signals.loc[(momentum < 0) & (ma_short < ma_long), 'signal'] = -1
        
        return signals

class SwingTradingStrategy(StrategyBase):
    """스윙 트레이딩 전략"""
    
    def __init__(self, swing_period: int = 5):
        super().__init__("스윙", "4h")
        self.swing_period = swing_period
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        
        # 스윙 고점/저점 계산
        swing_high = data['high'].rolling(window=self.swing_period).max()
        swing_low = data['low'].rolling(window=self.swing_period).min()
        
        # 매수/매도 신호
        signals.loc[data['close'] > swing_high.shift(1), 'signal'] = 1
        signals.loc[data['close'] < swing_low.shift(1), 'signal'] = -1
        
        return signals

class BreakoutStrategy(StrategyBase):
    """브레이크아웃 전략"""
    
    def __init__(self, lookback_period: int = 20):
        super().__init__("브레이크아웃", "1h")
        self.lookback_period = lookback_period
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        
        # 저항선/지지선 계산
        resistance = data['high'].rolling(window=self.lookback_period).max()
        support = data['low'].rolling(window=self.lookback_period).min()
        
        # 매수/매도 신호
        signals.loc[data['close'] > resistance.shift(1), 'signal'] = 1
        signals.loc[data['close'] < support.shift(1), 'signal'] = -1
        
        return signals

class ScalpingStrategy(StrategyBase):
    """스캘핑 전략"""
    
    def __init__(self, short_ma: int = 5, long_ma: int = 20):
        super().__init__("스캘핑", "1m")
        self.short_ma = short_ma
        self.long_ma = long_ma
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        
        # 단기/장기 이동평균
        ma_short = data['close'].rolling(window=self.short_ma).mean()
        ma_long = data['close'].rolling(window=self.long_ma).mean()
        
        # 매수/매도 신호
        signals.loc[ma_short > ma_long, 'signal'] = 1
        signals.loc[ma_short < ma_long, 'signal'] = -1
        
        return signals

class RSIStrategy(StrategyBase):
    """RSI 전략"""
    
    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70):
        super().__init__("RSI", "1h")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        
        # RSI 계산
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # 매수/매도 신호
        signals.loc[rsi < self.oversold, 'signal'] = 1
        signals.loc[rsi > self.overbought, 'signal'] = -1
        
        return signals

class MACDStrategy(StrategyBase):
    """MACD 전략"""
    
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        super().__init__("MACD", "1h")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        
        # MACD 계산
        ema_fast = data['close'].ewm(span=self.fast_period).mean()
        ema_slow = data['close'].ewm(span=self.slow_period).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=self.signal_period).mean()
        
        # 매수/매도 신호
        signals.loc[macd > signal_line, 'signal'] = 1
        signals.loc[macd < signal_line, 'signal'] = -1
        
        return signals

class BollingerBandsStrategy(StrategyBase):
    """볼린저밴드 전략"""
    
    def __init__(self, period: int = 20, std_dev: float = 2):
        super().__init__("볼린저밴드", "1h")
        self.period = period
        self.std_dev = std_dev
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        
        # 볼린저밴드 계산
        sma = data['close'].rolling(window=self.period).mean()
        std = data['close'].rolling(window=self.period).std()
        upper_band = sma + (std * self.std_dev)
        lower_band = sma - (std * self.std_dev)
        
        # 매수/매도 신호
        signals.loc[data['close'] < lower_band, 'signal'] = 1
        signals.loc[data['close'] > upper_band, 'signal'] = -1
        
        return signals

class MovingAverageStrategy(StrategyBase):
    """이동평균 전략"""
    
    def __init__(self, short_period: int = 10, long_period: int = 30):
        super().__init__("이동평균", "1h")
        self.short_period = short_period
        self.long_period = long_period
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        
        # 이동평균 계산
        ma_short = data['close'].rolling(window=self.short_period).mean()
        ma_long = data['close'].rolling(window=self.long_period).mean()
        
        # 매수/매도 신호
        signals.loc[ma_short > ma_long, 'signal'] = 1
        signals.loc[ma_short < ma_long, 'signal'] = -1
        
        return signals

class StochasticStrategy(StrategyBase):
    """스토캐스틱 전략"""
    
    def __init__(self, k_period: int = 14, d_period: int = 3, oversold: float = 20, overbought: float = 80):
        super().__init__("스토캐스틱", "1h")
        self.k_period = k_period
        self.d_period = d_period
        self.oversold = oversold
        self.overbought = overbought
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        
        # 스토캐스틱 계산
        lowest_low = data['low'].rolling(window=self.k_period).min()
        highest_high = data['high'].rolling(window=self.k_period).max()
        k_percent = 100 * ((data['close'] - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=self.d_period).mean()
        
        # 매수/매도 신호
        signals.loc[(k_percent < self.oversold) & (d_percent < self.oversold), 'signal'] = 1
        signals.loc[(k_percent > self.overbought) & (d_percent > self.overbought), 'signal'] = -1
        
        return signals

class MultiStrategyPortfolioManager:
    """다중 전략 포트폴리오 관리자"""
    
    def __init__(self, initial_capital: float = 100000, rebalance_frequency: int = 24):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.rebalance_frequency = rebalance_frequency  # 리밸런싱 주기 (시간)
        self.strategies = {}
        self.portfolio_history = []
        self.allocation_history = []
        
        # 전략 초기화
        self._initialize_strategies()
        
    def _initialize_strategies(self):
        """전략들 초기화"""
        self.strategies = {
            'volatility': VolatilityBreakoutStrategy(),
            'momentum': MomentumStrategy(),
            'swing': SwingTradingStrategy(),
            'breakout': BreakoutStrategy(),
            'scalping': ScalpingStrategy(),
            'rsi': RSIStrategy(),
            'macd': MACDStrategy(),
            'bollinger': BollingerBandsStrategy(),
            'ma': MovingAverageStrategy(),
            'stochastic': StochasticStrategy()
        }
        
        # 초기 자본을 100등분하여 각 전략에 균등 배분
        initial_allocation = 1.0 / len(self.strategies)
        for strategy in self.strategies.values():
            strategy.current_allocation = initial_allocation
            
    def load_data(self, symbol: str = 'BTCUSDT', timeframe: str = '1h', 
                  start_date: str = '2024-01-01', end_date: str = '2024-12-31') -> pd.DataFrame:
        """데이터 로드"""
        data_path = f"data/{symbol}/{timeframe}/{symbol}_{timeframe}_2024.csv"
        
        if not os.path.exists(data_path):
            print(f"❌ 데이터 파일을 찾을 수 없습니다: {data_path}")
            return None
            
        try:
            data = pd.read_csv(data_path)
            data['timestamp'] = pd.to_datetime(data['timestamp'])
            data.set_index('timestamp', inplace=True)
            
            # 필요한 컬럼 확인
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in data.columns for col in required_columns):
                print(f"❌ 필요한 컬럼이 없습니다: {required_columns}")
                return None
                
            print(f"✅ 데이터 로드 완료: {len(data)}개 캔들")
            return data
            
        except Exception as e:
            print(f"❌ 데이터 로드 실패: {e}")
            return None
            
    def calculate_strategy_signals(self, data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """모든 전략의 신호 계산"""
        signals = {}
        
        for name, strategy in self.strategies.items():
            if strategy.is_active:
                try:
                    signals[name] = strategy.calculate_signals(data)
                    print(f"✅ {strategy.name} 전략 신호 계산 완료")
                except Exception as e:
                    print(f"❌ {strategy.name} 전략 신호 계산 실패: {e}")
                    signals[name] = pd.DataFrame(index=data.index)
                    signals[name]['signal'] = 0
            else:
                signals[name] = pd.DataFrame(index=data.index)
                signals[name]['signal'] = 0
                
        return signals
        
    def calculate_portfolio_performance(self, data: pd.DataFrame, signals: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """포트폴리오 전체 성과 계산"""
        portfolio_returns = pd.Series(0, index=data.index)
        
        for name, strategy in self.strategies.items():
            if strategy.is_active and name in signals:
                # 전략별 수익률 계산
                strategy_returns = data['close'].pct_change() * signals[name]['signal'].shift(1)
                strategy_returns = strategy_returns.fillna(0)
                
                # 할당된 비중만큼 포트폴리오 수익률에 반영
                portfolio_returns += strategy_returns * strategy.current_allocation
                
        return portfolio_returns
        
    def rebalance_portfolio(self, data: pd.DataFrame, signals: Dict[str, pd.DataFrame]):
        """포트폴리오 리밸런싱"""
        print("\n🔄 포트폴리오 리밸런싱 중...")
        
        # 각 전략의 성과 계산
        for name, strategy in self.strategies.items():
            if strategy.is_active and name in signals:
                performance = strategy.calculate_performance(data, signals[name])
                strategy.update_performance(performance)
                
        # 성과 기반 자본 재배분
        self._reallocate_capital()
        
        # 리밸런싱 기록
        self.allocation_history.append({
            'timestamp': datetime.now(),
            'allocations': {name: s.current_allocation for name, s in self.strategies.items()}
        })
        
    def _reallocate_capital(self):
        """자본 재배분 로직"""
        # 활성화된 전략들의 성과 점수 계산
        active_strategies = {name: strategy for name, strategy in self.strategies.items() if strategy.is_active}
        
        if not active_strategies:
            return
            
        # 성과 점수 계산 (수익률, 승률, 샤프비율 가중평균)
        performance_scores = {}
        for name, strategy in active_strategies.items():
            # 정규화된 성과 점수 (0-1 범위)
            return_score = max(0, min(1, (strategy.total_return + 50) / 100))  # -50% ~ +50% 범위를 0-1로 정규화
            winrate_score = strategy.win_rate / 100
            sharpe_score = max(0, min(1, (strategy.sharpe_ratio + 2) / 4))  # -2 ~ +2 범위를 0-1로 정규화
            
            # 가중평균 (수익률 50%, 승률 30%, 샤프비율 20%)
            performance_scores[name] = (return_score * 0.5 + winrate_score * 0.3 + sharpe_score * 0.2)
            
        # 성과가 좋은 전략은 더 많은 자본 배분, 나쁜 전략은 적은 자본 배분
        total_score = sum(performance_scores.values())
        
        if total_score > 0:
            for name, strategy in active_strategies.items():
                # 성과 점수에 비례하여 자본 배분 (최소 1%, 최대 20%)
                new_allocation = max(0.01, min(0.20, performance_scores[name] / total_score))
                strategy.current_allocation = new_allocation
                
        # 비활성화된 전략들의 자본을 활성화된 전략들에게 재분배
        inactive_capital = sum(s.current_allocation for s in self.strategies.values() if not s.is_active)
        if inactive_capital > 0:
            active_count = len(active_strategies)
            if active_count > 0:
                additional_allocation = inactive_capital / active_count
                for strategy in active_strategies.values():
                    strategy.current_allocation += additional_allocation
                    
        # 전체 자본이 100%가 되도록 정규화
        total_allocation = sum(s.current_allocation for s in self.strategies.values())
        if total_allocation > 0:
            for strategy in self.strategies.values():
                strategy.current_allocation /= total_allocation
                
    def check_strategy_activation(self):
        """전략 활성화/비활성화 체크"""
        print("\n🔍 전략 활성화 상태 체크 중...")
        
        for name, strategy in self.strategies.items():
            if strategy.is_active:
                # 활성화된 전략이 성과가 50% 이하로 떨어지면 비활성화
                if strategy.total_return < -50 or strategy.win_rate < 30:
                    strategy.is_active = False
                    strategy.current_allocation = 0.0
                    print(f"⚠️ {strategy.name} 전략 비활성화 (성과 부족)")
            else:
                # 비활성화된 전략이 일정 기간 후 다시 활성화 고려
                if len(strategy.performance_history) > 0:
                    recent_performance = strategy.performance_history[-1]
                    if recent_performance['total_return'] > 0 and recent_performance['win_rate'] > 50:
                        strategy.is_active = True
                        strategy.current_allocation = 0.01  # 최소 자본으로 시작
                        print(f"✅ {strategy.name} 전략 재활성화")
                        
    def run_backtest(self, symbol: str = 'BTCUSDT', timeframe: str = '1h',
                    start_date: str = '2024-01-01', end_date: str = '2024-12-31'):
        """백테스트 실행"""
        print("🚀 다중 전략 포트폴리오 백테스트 시작!")
        print("=" * 60)
        
        # 데이터 로드
        data = self.load_data(symbol, timeframe, start_date, end_date)
        if data is None:
            return
            
        # 백테스트 실행
        portfolio_returns = []
        rebalance_count = 0
        
        for i in range(0, len(data), self.rebalance_frequency):
            current_data = data.iloc[:i+self.rebalance_frequency]
            
            if len(current_data) < 50:  # 최소 데이터 요구사항
                continue
                
            # 전략 신호 계산
            signals = self.calculate_strategy_signals(current_data)
            
            # 포트폴리오 성과 계산
            if i == 0:
                portfolio_returns = self.calculate_portfolio_performance(current_data, signals)
            else:
                current_returns = self.calculate_portfolio_performance(current_data, signals)
                portfolio_returns = pd.concat([portfolio_returns, current_returns])
                
            # 리밸런싱 (주기적으로)
            if i % (self.rebalance_frequency * 7) == 0:  # 주간 리밸런싱
                self.rebalance_portfolio(current_data, signals)
                self.check_strategy_activation()
                rebalance_count += 1
                
        # 최종 성과 계산
        self._calculate_final_performance(portfolio_returns)
        
        # 결과 저장
        self._save_results(symbol, timeframe, start_date, end_date)
        
        print(f"\n✅ 백테스트 완료!")
        print(f"📊 리밸런싱 횟수: {rebalance_count}")
        print(f"💰 최종 자본: {self.current_capital:,.2f} USDT")
        print(f"📈 총 수익률: {self.total_return:.2f}%")
        print(f"📉 최대 낙폭: {self.max_drawdown:.2f}%")
        
    def _calculate_final_performance(self, portfolio_returns: pd.Series):
        """최종 성과 계산"""
        portfolio_returns = portfolio_returns.dropna()
        
        # 총 수익률
        self.total_return = (portfolio_returns.sum()) * 100
        
        # 최대 낙폭
        cumulative_returns = (1 + portfolio_returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        self.max_drawdown = drawdown.min() * 100
        
        # 샤프 비율
        if portfolio_returns.std() > 0:
            self.sharpe_ratio = portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252)
        else:
            self.sharpe_ratio = 0.0
            
        # 승률
        self.win_rate = (portfolio_returns > 0).mean() * 100
        
    def _save_results(self, symbol: str, timeframe: str, start_date: str, end_date: str):
        """결과 저장"""
        # 로그 디렉토리 생성
        logs_dir = "logs"
        os.makedirs(logs_dir, exist_ok=True)
        
        # 전략별 성과 저장
        strategy_performance = {}
        for name, strategy in self.strategies.items():
            strategy_performance[name] = {
                'name': strategy.name,
                'is_active': strategy.is_active,
                'current_allocation': strategy.current_allocation,
                'total_return': strategy.total_return,
                'max_drawdown': strategy.max_drawdown,
                'win_rate': strategy.win_rate,
                'sharpe_ratio': strategy.sharpe_ratio,
                'total_trades': strategy.total_trades,
                'winning_trades': strategy.winning_trades,
                'losing_trades': strategy.losing_trades
            }
            
        # 포트폴리오 전체 성과
        portfolio_performance = {
            'symbol': symbol,
            'timeframe': timeframe,
            'start_date': start_date,
            'end_date': end_date,
            'initial_capital': self.initial_capital,
            'final_capital': self.current_capital,
            'total_return': self.total_return,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': self.sharpe_ratio,
            'win_rate': self.win_rate,
            'strategy_performance': strategy_performance
        }
        
        # JSON 파일로 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = os.path.join(logs_dir, f"multi_strategy_portfolio_{timestamp}.json")
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(portfolio_performance, f, ensure_ascii=False, indent=2, default=str)
            
        print(f"💾 결과 저장 완료: {result_file}")
        
    def create_performance_chart(self):
        """성과 차트 생성"""
        print("📊 성과 차트 생성 중...")
        
        # 전략별 성과 비교
        strategy_names = [s.name for s in self.strategies.values()]
        strategy_returns = [s.total_return for s in self.strategies.values()]
        strategy_winrates = [s.win_rate for s in self.strategies.values()]
        strategy_allocations = [s.current_allocation * 100 for s in self.strategies.values()]
        
        # 차트 생성
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # 1. 전략별 수익률
        ax1 = axes[0, 0]
        bars1 = ax1.bar(strategy_names, strategy_returns, color='skyblue')
        ax1.set_title('전략별 수익률', fontsize=14, fontweight='bold')
        ax1.set_ylabel('수익률 (%)')
        ax1.axhline(y=0, color='red', linestyle='--', alpha=0.7)
        ax1.tick_params(axis='x', rotation=45)
        
        # 2. 전략별 승률
        ax2 = axes[0, 1]
        bars2 = ax2.bar(strategy_names, strategy_winrates, color='lightgreen')
        ax2.set_title('전략별 승률', fontsize=14, fontweight='bold')
        ax2.set_ylabel('승률 (%)')
        ax2.set_ylim(0, 100)
        ax2.tick_params(axis='x', rotation=45)
        
        # 3. 전략별 자본 배분
        ax3 = axes[1, 0]
        bars3 = ax3.bar(strategy_names, strategy_allocations, color='orange')
        ax3.set_title('전략별 자본 배분', fontsize=14, fontweight='bold')
        ax3.set_ylabel('배분 비율 (%)')
        ax3.tick_params(axis='x', rotation=45)
        
        # 4. 활성화 상태
        ax4 = axes[1, 1]
        active_status = [1 if s.is_active else 0 for s in self.strategies.values()]
        bars4 = ax4.bar(strategy_names, active_status, color=['red' if not s.is_active else 'green' for s in self.strategies.values()])
        ax4.set_title('전략 활성화 상태', fontsize=14, fontweight='bold')
        ax4.set_ylabel('활성화 (1) / 비활성화 (0)')
        ax4.set_ylim(0, 1.2)
        ax4.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        
        # 차트 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chart_path = f"logs/multi_strategy_performance_{timestamp}.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ 차트 저장 완료: {chart_path}")

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='다중 전략 포트폴리오 관리 시스템')
    parser.add_argument('--symbol', default='BTCUSDT', help='거래 심볼')
    parser.add_argument('--timeframe', default='1h', help='시간프레임')
    parser.add_argument('--start', default='2024-01-01', help='시작 날짜')
    parser.add_argument('--end', default='2024-12-31', help='종료 날짜')
    parser.add_argument('--capital', type=float, default=100000, help='초기 자본')
    parser.add_argument('--rebalance', type=int, default=24, help='리밸런싱 주기 (시간)')
    
    args = parser.parse_args()
    
    # 포트폴리오 관리자 생성
    portfolio_manager = MultiStrategyPortfolioManager(
        initial_capital=args.capital,
        rebalance_frequency=args.rebalance
    )
    
    # 백테스트 실행
    portfolio_manager.run_backtest(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start_date=args.start,
        end_date=args.end
    )
    
    # 성과 차트 생성
    portfolio_manager.create_performance_chart()

if __name__ == "__main__":
    main()
