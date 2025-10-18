# -*- coding: utf-8 -*-
"""
초고속 적응형 트레이딩 시스템 (진짜 벡터화)

=== 핵심 개선사항 ===
1. 모든 지표를 한번에 계산
2. 모든 신호를 한번에 생성
3. 루프 최소화
4. 메모리 효율성 극대화
"""

import pandas as pd
import numpy as np
import json
import os
import sys
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class UltraFastTradingSystem:
    """초고속 트레이딩 시스템"""
    
    def __init__(self):
        self.data = None
        
        # 전략 매핑 (간소화)
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
    
    def load_data(self, file_path):
        """데이터 로드"""
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            self.data = df
            return True
        return False
    
    def calculate_all_indicators_ultra_fast(self, data):
        """모든 지표를 한번에 계산 (진짜 벡터화)"""
        df = data.copy()
        
        # 1. 기본 이동평균
        df['sma_12'] = df['close'].rolling(12).mean()
        df['sma_30'] = df['close'].rolling(30).mean()
        df['sma_5'] = df['close'].rolling(5).mean()
        df['sma_15'] = df['close'].rolling(15).mean()
        
        # 2. MACD
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        df['macd_line'] = ema_12 - ema_26
        df['macd_signal'] = df['macd_line'].ewm(span=9).mean()
        df['macd_histogram'] = df['macd_line'] - df['macd_signal']
        
        # 3. Bollinger Bands
        df['bb_middle'] = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2.0)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2.0)
        
        # 4. RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 5. Stochastic
        low_14 = df['low'].rolling(14).min()
        high_14 = df['high'].rolling(14).max()
        df['stoch_k'] = 100 * (df['close'] - low_14) / (high_14 - low_14)
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()
        
        # 6. CCI
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        sma_tp = typical_price.rolling(14).mean()
        mad = typical_price.rolling(14).apply(lambda x: np.mean(np.abs(x - x.mean())))
        df['cci'] = (typical_price - sma_tp) / (0.015 * mad)
        
        # 7. Donchian Channels
        df['dc_high'] = df['high'].rolling(25).max()
        df['dc_low'] = df['low'].rolling(25).min()
        df['dc_middle'] = (df['dc_high'] + df['dc_low']) / 2
        
        # 8. ATR for volatility
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        df['atr'] = true_range.rolling(20).mean()
        df['volatility_ratio'] = df['atr'] / df['atr'].rolling(100).mean()
        
        # 9. 트렌드 계산
        df['trend_20'] = df['close'].pct_change(20)
        df['trend_50'] = df['close'].pct_change(50)
        df['trend_100'] = df['close'].pct_change(100)
        
        return df
    
    def detect_market_states_ultra_fast(self, df):
        """시장 상태를 한번에 감지 (벡터화)"""
        # 트렌드 분류
        trend_strength = (df['trend_20'] + df['trend_50'] + df['trend_100']) / 3
        df['trend'] = np.select([
            trend_strength > 0.001,
            trend_strength > 0.0005,
            trend_strength < -0.001,
            trend_strength < -0.0005
        ], ['strong_uptrend', 'uptrend', 'strong_downtrend', 'downtrend'], default='sideways')
        
        # 변동성 분류
        df['volatility'] = np.select([
            df['volatility_ratio'] > 1.5,
            df['volatility_ratio'] > 1.2
        ], ['high_volatility', 'medium_volatility'], default='low_volatility')
        
        # 모멘텀 분류
        df['momentum'] = np.select([
            (df['rsi'] > 70) & (df['macd_histogram'] > 0),
            (df['rsi'] > 60) & (df['macd_histogram'] > 0),
            (df['rsi'] < 30) & (df['macd_histogram'] < 0),
            (df['rsi'] < 40) & (df['macd_histogram'] < 0)
        ], ['strong_bullish', 'bullish', 'strong_bearish', 'bearish'], default='neutral')
        
        return df
    
    def generate_all_signals_ultra_fast(self, df):
        """모든 신호를 한번에 생성 (벡터화)"""
        # MA 신호
        ma_long = (df['sma_12'] > df['sma_30']) & (df['sma_12'].shift(1) <= df['sma_30'].shift(1))
        ma_short = (df['sma_12'] < df['sma_30']) & (df['sma_12'].shift(1) >= df['sma_30'].shift(1))
        
        # MACD 신호
        macd_long = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
        macd_short = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
        
        # BB 신호
        bb_long = df['close'] <= df['bb_lower'] * 1.01
        bb_short = df['close'] >= df['bb_upper'] * 0.99
        
        # RSI 신호
        rsi_long = (df['rsi'] < 30) & (df['rsi'].shift(1) >= 30)
        rsi_short = (df['rsi'] > 70) & (df['rsi'].shift(1) <= 70)
        
        # Stochastic 신호
        stoch_long = (df['stoch_k'] < 20) & (df['stoch_k'].shift(1) >= 20)
        stoch_short = (df['stoch_k'] > 80) & (df['stoch_k'].shift(1) <= 80)
        
        # CCI 신호
        cci_long = (df['cci'] < -100) & (df['cci'].shift(1) >= -100)
        cci_short = (df['cci'] > 100) & (df['cci'].shift(1) <= 100)
        
        # DC 조건
        long_dc = (df['close'] > df['dc_middle']) & (df['close'] > df['dc_low'] * 1.02)
        short_dc = (df['close'] < df['dc_middle']) & (df['close'] < df['dc_high'] * 0.98)
        
        # RSI 필터
        long_rsi_filter = df['rsi'] < 70
        short_rsi_filter = df['rsi'] > 30
        
        # 전략별 신호 매핑
        signals = {}
        for strategy, (long_sig, short_sig) in [
            ('ma_dc', (ma_long, ma_short)),
            ('macd_dc', (macd_long, macd_short)),
            ('bb_dc', (bb_long, bb_short)),
            ('rsi_dc', (rsi_long, rsi_short)),
            ('stoch_dc', (stoch_long, stoch_short)),
            ('cci_dc', (cci_long, cci_short)),
            ('scalping_dc', (ma_long, ma_short)),  # 빠른 MA
            ('integrated', (ma_long & macd_long, ma_short & macd_short))
        ]:
            signals[f'{strategy}_long'] = long_sig & long_dc & long_rsi_filter
            signals[f'{strategy}_short'] = short_sig & short_dc & short_rsi_filter
        
        return signals
    
    def run_ultra_fast_backtest(self, start_date, end_date, initial_capital=10000):
        """초고속 백테스트 실행"""
        print("=== 초고속 적응형 트레이딩 시스템 백테스트 시작 ===")
        
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
        
        print("모든 지표 계산 중...")
        # 모든 지표를 한번에 계산
        df_with_indicators = self.calculate_all_indicators_ultra_fast(test_data)
        
        print("시장 상태 분석 중...")
        # 시장 상태를 한번에 감지
        df_with_states = self.detect_market_states_ultra_fast(df_with_indicators)
        
        print("신호 생성 중...")
        # 모든 신호를 한번에 생성
        signals = self.generate_all_signals_ultra_fast(df_with_states)
        
        print("거래 시뮬레이션 중...")
        # 거래 시뮬레이션
        trades = self._simulate_trades_ultra_fast(df_with_states, signals, initial_capital)
        
        # 결과 계산
        if len(trades) > 0:
            total_return = (trades['final_capital'].iloc[-1] - initial_capital) / initial_capital * 100
            winning_trades = len(trades[trades['pnl'] > 0])
            win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0
            max_drawdown = self._calculate_max_drawdown_ultra_fast(trades, initial_capital)
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
    
    def _simulate_trades_ultra_fast(self, df, signals, initial_capital):
        """초고속 거래 시뮬레이션"""
        trades = []
        capital = initial_capital
        position = None
        entry_price = 0
        trade_count = 0
        
        for i in range(len(df)):
            current_row = df.iloc[i]
            timestamp = current_row.name
            
            # 시장 상태에 따른 전략 선택
            state_key = (current_row['trend'], current_row['volatility'], current_row['momentum'])
            selected_strategy = self.strategy_mapping.get(state_key, 'ma_dc')
            
            # 현재 신호 확인
            long_signal = signals.get(f'{selected_strategy}_long', pd.Series([False] * len(df))).iloc[i]
            short_signal = signals.get(f'{selected_strategy}_short', pd.Series([False] * len(df))).iloc[i]
            
            if position is None:
                if long_signal:
                    position = 'long'
                    entry_price = current_row['close']
                    print(f"{timestamp}: 롱 진입 (가격: {entry_price:.2f}, 전략: {selected_strategy})")
                elif short_signal:
                    position = 'short'
                    entry_price = current_row['close']
                    print(f"{timestamp}: 숏 진입 (가격: {entry_price:.2f}, 전략: {selected_strategy})")
            else:
                should_exit = False
                exit_reason = ""
                
                if position == 'long' and (short_signal or current_row['close'] <= entry_price * 0.95):
                    should_exit = True
                    exit_reason = "숏 신호" if short_signal else "손절매"
                elif position == 'short' and (long_signal or current_row['close'] >= entry_price * 1.05):
                    should_exit = True
                    exit_reason = "롱 신호" if long_signal else "손절매"
                
                if should_exit:
                    trade_count += 1
                    pnl = self._calculate_pnl_ultra_fast(entry_price, current_row['close'], capital, position)
                    capital += pnl
                    
                    trades.append({
                        'entry_time': entry_price,
                        'exit_time': current_row['close'],
                        'position': position,
                        'pnl': pnl,
                        'strategy': selected_strategy,
                        'exit_reason': exit_reason,
                        'final_capital': capital
                    })
                    
                    if pnl > 0:
                        print(f"{timestamp}: {position} 청산 [수익] ({exit_reason}, PnL: {pnl:.2f}, 자본: {capital:.2f})")
                    else:
                        print(f"{timestamp}: {position} 청산 [손실] ({exit_reason}, PnL: {pnl:.2f}, 자본: {capital:.2f})")
                    
                    position = None
            
            # 진행률 표시
            if i % 10000 == 0:
                print(f"진행률: {i/len(df)*100:.1f}% ({i}/{len(df)})")
        
        print(f"거래 시뮬레이션 완료! 총 {trade_count}회 거래")
        return pd.DataFrame(trades)
    
    def _calculate_pnl_ultra_fast(self, entry_price, exit_price, capital, position_type):
        """초고속 PnL 계산"""
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
    
    def _calculate_max_drawdown_ultra_fast(self, trades, initial_capital):
        """초고속 최대 낙폭 계산"""
        if len(trades) == 0:
            return 0.0
        
        capital_series = trades['final_capital'].values
        peak = np.maximum.accumulate(capital_series)
        drawdown = (peak - capital_series) / peak * 100
        
        return np.max(drawdown)

def main():
    """메인 실행 함수"""
    print("=== 초고속 적응형 트레이딩 시스템 ===")
    
    # 시스템 초기화
    system = UltraFastTradingSystem()
    
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
        # 초고속 백테스트 실행
        result = system.run_ultra_fast_backtest('2024-01-01', '2024-12-31')
        
        if result:
            print(f"\n초고속 시스템 결과:")
            print(f"  총 수익률: {result['total_return']:.2f}%")
            print(f"  최종 자본: {result['final_capital']:.2f}")
            print(f"  총 거래: {result['total_trades']}회")
            print(f"  승률: {result['win_rate']:.2f}%")
            print(f"  최대 낙폭: {result['max_drawdown']:.2f}%")
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
