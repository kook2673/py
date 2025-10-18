# -*- coding: utf-8 -*-
"""
빠른 적응형 트레이딩 시스템 (벡터화 연산)

=== 주요 개선사항 ===
1. 판다스 벡터화 연산 사용
2. 루프 최소화
3. 배치 처리
4. 메모리 효율성 개선
"""

import pandas as pd
import numpy as np
import json
import os
import sys
import io
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class FastMarketStateDetector:
    """빠른 시장 상태 감지 클래스 (벡터화)"""
    
    def __init__(self):
        self.trend_periods = [20, 50, 100]
        self.volatility_period = 20
        self.momentum_period = 14
    
    def detect_market_states_vectorized(self, data):
        """벡터화된 시장 상태 감지"""
        df = data.copy()
        
        # 트렌드 계산 (벡터화)
        for period in self.trend_periods:
            df[f'trend_{period}'] = df['close'].pct_change(period)
        
        # 변동성 계산 (ATR)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        df['atr'] = true_range.rolling(self.volatility_period).mean()
        df['volatility_ratio'] = df['atr'] / df['atr'].rolling(100).mean()
        
        # 모멘텀 계산 (RSI + MACD)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.momentum_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.momentum_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        ema_fast = df['close'].ewm(span=12).mean()
        ema_slow = df['close'].ewm(span=26).mean()
        df['macd_line'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd_line'].ewm(span=9).mean()
        df['macd_histogram'] = df['macd_line'] - df['macd_signal']
        
        # 시장 상태 분류 (벡터화)
        df['trend'] = self._classify_trend_vectorized(df)
        df['volatility'] = self._classify_volatility_vectorized(df)
        df['momentum'] = self._classify_momentum_vectorized(df)
        
        return df
    
    def _classify_trend_vectorized(self, df):
        """벡터화된 트렌드 분류"""
        trend_strength = (df['trend_20'] + df['trend_50'] + df['trend_100']) / 3
        
        conditions = [
            trend_strength > 0.001,
            trend_strength > 0.0005,
            trend_strength < -0.001,
            trend_strength < -0.0005
        ]
        
        choices = ['strong_uptrend', 'uptrend', 'strong_downtrend', 'downtrend']
        
        return np.select(conditions, choices, default='sideways')
    
    def _classify_volatility_vectorized(self, df):
        """벡터화된 변동성 분류"""
        conditions = [
            df['volatility_ratio'] > 1.5,
            df['volatility_ratio'] > 1.2
        ]
        
        choices = ['high_volatility', 'medium_volatility']
        
        return np.select(conditions, choices, default='low_volatility')
    
    def _classify_momentum_vectorized(self, df):
        """벡터화된 모멘텀 분류"""
        conditions = [
            (df['rsi'] > 70) & (df['macd_histogram'] > 0),
            (df['rsi'] > 60) & (df['macd_histogram'] > 0),
            (df['rsi'] < 30) & (df['macd_histogram'] < 0),
            (df['rsi'] < 40) & (df['macd_histogram'] < 0)
        ]
        
        choices = ['strong_bullish', 'bullish', 'strong_bearish', 'bearish']
        
        return np.select(conditions, choices, default='neutral')

class FastStrategySelector:
    """빠른 전략 선택기"""
    
    def __init__(self):
        self.strategy_mapping = {
            ('strong_uptrend', 'low_volatility', 'strong_bullish'): 'ma_dc',
            ('strong_downtrend', 'low_volatility', 'strong_bearish'): 'ma_dc',
            ('uptrend', 'medium_volatility', 'bullish'): 'macd_dc',
            ('downtrend', 'medium_volatility', 'bearish'): 'macd_dc',
            ('sideways', 'high_volatility', 'neutral'): 'bb_dc',
            ('uptrend', 'high_volatility', 'bullish'): 'stoch_dc',
            ('downtrend', 'high_volatility', 'bearish'): 'stoch_dc',
            ('sideways', 'medium_volatility', 'neutral'): 'scalping_dc',
            ('uptrend', 'medium_volatility', 'strong_bullish'): 'rsi_dc',
            ('downtrend', 'medium_volatility', 'strong_bearish'): 'rsi_dc',
            ('sideways', 'low_volatility', 'neutral'): 'integrated',
            ('uptrend', 'low_volatility', 'bullish'): 'cci_dc',
            ('downtrend', 'low_volatility', 'bearish'): 'cci_dc'
        }
    
    def select_strategies_vectorized(self, df):
        """벡터화된 전략 선택"""
        state_keys = list(zip(df['trend'], df['volatility'], df['momentum']))
        
        # 전략 매핑을 DataFrame으로 변환
        mapping_df = pd.DataFrame(list(self.strategy_mapping.items()), 
                               columns=['state', 'strategy'])
        mapping_df[['trend', 'volatility', 'momentum']] = pd.DataFrame(mapping_df['state'].tolist())
        
        # 병합을 통한 전략 선택
        df_with_strategies = df.merge(mapping_df, on=['trend', 'volatility', 'momentum'], how='left')
        df_with_strategies['strategy'] = df_with_strategies['strategy'].fillna('ma_dc')
        
        return df_with_strategies['strategy']

class FastAdaptiveTradingSystem:
    """빠른 적응형 트레이딩 시스템"""
    
    def __init__(self):
        self.market_detector = FastMarketStateDetector()
        self.strategy_selector = FastStrategySelector()
        self.data = None
        
        # 전략별 파라미터 (간소화)
        self.strategy_params = {
            'ma_dc': {'sma_short': 12, 'sma_long': 30, 'dc_period': 25},
            'macd_dc': {'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9, 'dc_period': 25},
            'bb_dc': {'bb_period': 20, 'bb_std': 2.0, 'dc_period': 25},
            'scalping_dc': {'sma_short': 5, 'sma_long': 15, 'dc_period': 20},
            'stoch_dc': {'stoch_k': 14, 'stoch_d': 3, 'dc_period': 25},
            'rsi_dc': {'rsi_period': 14, 'dc_period': 25},
            'cci_dc': {'cci_period': 14, 'dc_period': 25},
            'integrated': {'dc_period': 25}
        }
    
    def load_data(self, file_path):
        """데이터 로드"""
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            self.data = df
            return True
        return False
    
    def calculate_all_indicators_vectorized(self, data):
        """모든 지표를 한번에 계산 (벡터화)"""
        df = data.copy()
        
        # 공통 지표들
        df['sma_short'] = df['close'].rolling(12).mean()
        df['sma_long'] = df['close'].rolling(30).mean()
        
        # MACD
        ema_fast = df['close'].ewm(span=12).mean()
        ema_slow = df['close'].ewm(span=26).mean()
        df['macd_line'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd_line'].ewm(span=9).mean()
        
        # BB
        df['bb_middle'] = df['close'].rolling(20).mean()
        bb_std_val = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std_val * 2.0)
        df['bb_lower'] = df['bb_middle'] - (bb_std_val * 2.0)
        
        # 스토캐스틱
        low_min = df['low'].rolling(14).min()
        high_max = df['high'].rolling(14).max()
        df['stoch_k'] = 100 * (df['close'] - low_min) / (high_max - low_min)
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # CCI
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        sma_tp = typical_price.rolling(14).mean()
        mad = typical_price.rolling(14).apply(lambda x: np.mean(np.abs(x - x.mean())))
        df['cci'] = (typical_price - sma_tp) / (0.015 * mad)
        
        # DC
        df['dc_high'] = df['high'].rolling(25).max()
        df['dc_low'] = df['low'].rolling(25).min()
        df['dc_middle'] = (df['dc_high'] + df['dc_low']) / 2
        
        return df
    
    def generate_all_signals_vectorized(self, df):
        """모든 전략의 신호를 한번에 생성 (벡터화)"""
        # MA 신호
        ma_long_signal = (df['sma_short'] > df['sma_long']) & (df['sma_short'].shift(1) <= df['sma_long'].shift(1))
        ma_short_signal = (df['sma_short'] < df['sma_long']) & (df['sma_short'].shift(1) >= df['sma_long'].shift(1))
        
        # MACD 신호
        macd_long_signal = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
        macd_short_signal = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
        
        # BB 신호
        bb_long_signal = df['close'] <= df['bb_lower'] * 1.01
        bb_short_signal = df['close'] >= df['bb_upper'] * 0.99
        
        # 스토캐스틱 신호
        stoch_long_signal = (df['stoch_k'] < 20) & (df['stoch_k'].shift(1) >= 20)
        stoch_short_signal = (df['stoch_k'] > 80) & (df['stoch_k'].shift(1) <= 80)
        
        # RSI 신호
        rsi_long_signal = (df['rsi'] < 30) & (df['rsi'].shift(1) >= 30)
        rsi_short_signal = (df['rsi'] > 70) & (df['rsi'].shift(1) <= 70)
        
        # CCI 신호
        cci_long_signal = (df['cci'] < -100) & (df['cci'].shift(1) >= -100)
        cci_short_signal = (df['cci'] > 100) & (df['cci'].shift(1) <= 100)
        
        # DC 조건
        long_dc_signal = (df['close'] > df['dc_middle']) & (df['close'] > df['dc_low'] * 1.02)
        short_dc_signal = (df['close'] < df['dc_middle']) & (df['close'] < df['dc_high'] * 0.98)
        
        # RSI 필터
        long_rsi_signal = df['rsi'] < 70
        short_rsi_signal = df['rsi'] > 30
        
        # 전략별 신호 매핑
        strategy_signals = {
            'ma_dc': (ma_long_signal, ma_short_signal),
            'macd_dc': (macd_long_signal, macd_short_signal),
            'bb_dc': (bb_long_signal, bb_short_signal),
            'scalping_dc': (ma_long_signal, ma_short_signal),  # 빠른 MA
            'stoch_dc': (stoch_long_signal, stoch_short_signal),
            'rsi_dc': (rsi_long_signal, rsi_short_signal),
            'cci_dc': (cci_long_signal, cci_short_signal),
            'integrated': (ma_long_signal & macd_long_signal, ma_short_signal & macd_short_signal)
        }
        
        return strategy_signals, long_dc_signal, short_dc_signal, long_rsi_signal, short_rsi_signal
    
    def run_fast_backtest(self, start_date, end_date, initial_capital=10000):
        """빠른 백테스트 실행 (벡터화)"""
        print("=== 빠른 적응형 트레이딩 시스템 백테스트 시작 ===")
        
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
        
        # 윈도우 크기
        window_size = 100
        total_iterations = len(test_data) - window_size
        
        print(f"처리할 데이터: {total_iterations}개 (윈도우 크기: {window_size})")
        print("=" * 50)
        
        # 벡터화된 처리
        all_results = []
        
        for i in range(window_size, len(test_data)):
            # 진행률 표시
            progress = (i - window_size + 1) / total_iterations * 100
            if (i - window_size + 1) % 1000 == 0 or progress >= 100:
                print(f"진행률: {progress:.1f}% ({i - window_size + 1}/{total_iterations}) - {test_data.index[i]}")
            
            current_data = test_data.iloc[:i+1]
            
            # 시장 상태 분석 (벡터화)
            market_data = self.market_detector.detect_market_states_vectorized(current_data)
            current_state = market_data.iloc[-1]
            
            # 전략 선택
            state_key = (current_state['trend'], current_state['volatility'], current_state['momentum'])
            selected_strategy = self.strategy_selector.strategy_mapping.get(state_key, 'ma_dc')
            
            # 지표 계산
            df_with_indicators = self.calculate_all_indicators_vectorized(current_data)
            
            # 신호 생성
            strategy_signals, long_dc, short_dc, long_rsi, short_rsi = self.generate_all_signals_vectorized(df_with_indicators)
            
            # 현재 신호
            current_row = df_with_indicators.iloc[-1]
            long_signal, short_signal = strategy_signals[selected_strategy]
            
            # DC + RSI 필터 적용
            final_long = long_signal.iloc[-1] & long_dc.iloc[-1] & long_rsi.iloc[-1]
            final_short = short_signal.iloc[-1] & short_dc.iloc[-1] & short_rsi.iloc[-1]
            
            all_results.append({
                'timestamp': current_row.name,
                'strategy': selected_strategy,
                'long_signal': final_long,
                'short_signal': final_short,
                'close': current_row['close']
            })
        
        print("=" * 50)
        print("신호 생성 완료! 거래 시뮬레이션 시작...")
        
        # 거래 시뮬레이션 (벡터화)
        print(f"거래 시뮬레이션 중... (총 {len(all_results)}개 신호 분석)")
        results_df = pd.DataFrame(all_results)
        trades = self._simulate_trades_vectorized(results_df, initial_capital)
        
        print("=" * 50)
        print("결과 계산 중...")
        
        # 결과 계산
        if len(trades) > 0:
            total_return = (trades['final_capital'].iloc[-1] - initial_capital) / initial_capital * 100
            winning_trades = len(trades[trades['pnl'] > 0])
            win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0
            max_drawdown = self._calculate_max_drawdown_vectorized(trades, initial_capital)
        else:
            total_return = 0.0
            win_rate = 0.0
            max_drawdown = 0.0
        
        result = {
            'total_return': total_return,
            'final_capital': trades['final_capital'].iloc[-1] if len(trades) > 0 else initial_capital,
            'total_trades': len(trades),
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'trades': trades.to_dict('records') if len(trades) > 0 else []
        }
        
        print("백테스트 완료!")
        return result
    
    def _simulate_trades_vectorized(self, results_df, initial_capital):
        """벡터화된 거래 시뮬레이션"""
        print(f"거래 시뮬레이션 시작... (총 {len(results_df)}개 신호)")
        
        trades = []
        capital = initial_capital
        position = None
        entry_price = 0
        trade_count = 0
        
        for idx, row in results_df.iterrows():
            if position is None:
                if row['long_signal']:
                    position = 'long'
                    entry_price = row['close']
                    print(f"{row['timestamp']}: 롱 진입 (가격: {entry_price:.2f}, 전략: {row['strategy']})")
                elif row['short_signal']:
                    position = 'short'
                    entry_price = row['close']
                    print(f"{row['timestamp']}: 숏 진입 (가격: {entry_price:.2f}, 전략: {row['strategy']})")
            else:
                should_exit = False
                exit_reason = ""
                
                if position == 'long' and (row['short_signal'] or row['close'] <= entry_price * 0.95):
                    should_exit = True
                    exit_reason = "숏 신호" if row['short_signal'] else "손절매"
                elif position == 'short' and (row['long_signal'] or row['close'] >= entry_price * 1.05):
                    should_exit = True
                    exit_reason = "롱 신호" if row['long_signal'] else "손절매"
                
                if should_exit:
                    trade_count += 1
                    pnl = self._calculate_pnl_fast(entry_price, row['close'], capital, position)
                    capital += pnl
                    
                    trades.append({
                        'entry_time': entry_price,
                        'exit_time': row['close'],
                        'position': position,
                        'pnl': pnl,
                        'strategy': row['strategy'],
                        'exit_reason': exit_reason,
                        'final_capital': capital
                    })
                    
                    if pnl > 0:
                        print(f"{row['timestamp']}: {position} 청산 🟢 ({exit_reason}, PnL: {pnl:.2f}, 자본: {capital:.2f})")
                    else:
                        print(f"{row['timestamp']}: {position} 청산 🔴 ({exit_reason}, PnL: {pnl:.2f}, 자본: {capital:.2f})")
                    
                    position = None
            
            # 진행률 표시 (거래가 있을 때만)
            if trade_count > 0 and trade_count % 10 == 0:
                print(f"  → 거래 완료: {trade_count}회")
        
        print(f"거래 시뮬레이션 완료! 총 {trade_count}회 거래")
        return pd.DataFrame(trades)
    
    def _calculate_pnl_fast(self, entry_price, exit_price, capital, position_type):
        """빠른 PnL 계산"""
        fee_rate = 0.0005
        
        if position_type == 'long':
            entry_with_fee = entry_price * (1 + fee_rate)
            exit_with_fee = exit_price * (1 - fee_rate)
            amount = capital / entry_with_fee
            pnl = (exit_with_fee - entry_with_fee) * amount
        else:
            entry_with_fee = entry_price * (1 - fee_rate)
            exit_with_fee = exit_price * (1 + fee_rate)
            amount = capital / entry_with_fee
            pnl = (entry_with_fee - exit_with_fee) * amount
        
        return pnl
    
    def _calculate_max_drawdown_vectorized(self, trades, initial_capital):
        """벡터화된 최대 낙폭 계산"""
        if len(trades) == 0:
            return 0.0
        
        capital_series = trades['final_capital'].values
        peak = np.maximum.accumulate(capital_series)
        drawdown = (peak - capital_series) / peak * 100
        
        return np.max(drawdown)

def main():
    """메인 실행 함수"""
    print("=== 빠른 적응형 트레이딩 시스템 ===")
    print("시스템 초기화 중...")
    
    # 시스템 초기화
    system = FastAdaptiveTradingSystem()
    print("시스템 초기화 완료")
    
    # 데이터 로드 시도
    data_files = [
        "data/BTCUSDT/5m/BTCUSDT_5m_2024.csv",
        "data/BTCUSDT/1m/BTCUSDT_1m_2024.csv",
        "data/BTCUSDT/3m/BTCUSDT_3m_2024.csv"
    ]
    
    data_loaded = False
    for file_path in data_files:
        if system.load_data(file_path):
            print(f"데이터 로드 완료: {file_path} ({len(system.data)}개 캔들)")
            data_loaded = True
            break
    
    if not data_loaded:
        print("데이터 파일을 찾을 수 없습니다.")
        print("사용 가능한 데이터 파일:")
        for file_path in data_files:
            print(f"  - {file_path}")
        print("데이터 파일을 준비한 후 다시 실행해주세요.")
        return
    
    if data_loaded:
        # 빠른 백테스트 실행
        result = system.run_fast_backtest('2024-01-01', '2024-12-31')
        
        if result:
            print(f"\n빠른 시스템 결과:")
            print(f"  총 수익률: {result['total_return']:.2f}%")
            print(f"  최종 자본: {result['final_capital']:.2f}")
            print(f"  총 거래: {result['total_trades']}회")
            print(f"  승률: {result['win_rate']:.2f}%")
            print(f"  최대 낙폭: {result['max_drawdown']:.2f}%")
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
