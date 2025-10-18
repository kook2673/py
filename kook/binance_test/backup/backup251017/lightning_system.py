# -*- coding: utf-8 -*-
"""
번개 속도 트레이딩 시스템

=== 핵심 원리 ===
1. 모든 계산을 한번에 (진짜 벡터화)
2. 루프 최소화 (거의 제로)
3. 메모리 효율성 극대화
4. 단순화된 로직
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

class LightningTradingSystem:
    """번개 속도 트레이딩 시스템"""
    
    def __init__(self):
        self.data = None
    
    def load_data(self, file_path):
        """데이터 로드"""
        try:
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            self.data = df
            return True
        except:
            return False
    
    def run_lightning_backtest(self, start_date, end_date, initial_capital=10000):
        """번개 속도 백테스트"""
        print("=== 번개 속도 트레이딩 시스템 ===")
        
        # 데이터 필터링
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        mask = (self.data.index >= start_dt) & (self.data.index <= end_dt)
        df = self.data[mask].copy()
        
        if len(df) == 0:
            print("데이터가 없습니다.")
            return None
        
        print(f"데이터: {len(df)}개 캔들")
        
        # 1. 모든 지표를 한번에 계산 (진짜 벡터화)
        print("지표 계산 중...")
        df = self._calculate_all_indicators_lightning(df)
        
        # 2. 모든 신호를 한번에 생성 (진짜 벡터화)
        print("신호 생성 중...")
        df = self._generate_all_signals_lightning(df)
        
        # 3. 거래 시뮬레이션 (벡터화)
        print("거래 시뮬레이션 중...")
        result = self._simulate_trades_lightning(df, initial_capital)
        
        print("완료!")
        return result
    
    def _calculate_all_indicators_lightning(self, df):
        """번개 속도 지표 계산"""
        # 기본 이동평균
        df['sma_12'] = df['close'].rolling(12).mean()
        df['sma_30'] = df['close'].rolling(30).mean()
        
        # MACD
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        df['macd_line'] = ema_12 - ema_26
        df['macd_signal'] = df['macd_line'].ewm(span=9).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2.0)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2.0)
        
        # Donchian Channels
        df['dc_high'] = df['high'].rolling(25).max()
        df['dc_low'] = df['low'].rolling(25).min()
        df['dc_middle'] = (df['dc_high'] + df['dc_low']) / 2
        
        return df
    
    def _generate_all_signals_lightning(self, df):
        """번개 속도 신호 생성"""
        # MA 신호
        df['ma_long'] = (df['sma_12'] > df['sma_30']) & (df['sma_12'].shift(1) <= df['sma_30'].shift(1))
        df['ma_short'] = (df['sma_12'] < df['sma_30']) & (df['sma_12'].shift(1) >= df['sma_30'].shift(1))
        
        # MACD 신호
        df['macd_long'] = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
        df['macd_short'] = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
        
        # RSI 신호
        df['rsi_long'] = (df['rsi'] < 30) & (df['rsi'].shift(1) >= 30)
        df['rsi_short'] = (df['rsi'] > 70) & (df['rsi'].shift(1) <= 70)
        
        # BB 신호
        df['bb_long'] = df['close'] <= df['bb_lower'] * 1.01
        df['bb_short'] = df['close'] >= df['bb_upper'] * 0.99
        
        # DC 조건
        df['long_dc'] = (df['close'] > df['dc_middle']) & (df['close'] > df['dc_low'] * 1.02)
        df['short_dc'] = (df['close'] < df['dc_middle']) & (df['close'] < df['dc_high'] * 0.98)
        
        # RSI 필터
        df['long_rsi_filter'] = df['rsi'] < 70
        df['short_rsi_filter'] = df['rsi'] > 30
        
        # 최종 신호 (간단한 조합)
        df['final_long'] = (df['ma_long'] | df['macd_long'] | df['rsi_long'] | df['bb_long']) & df['long_dc'] & df['long_rsi_filter']
        df['final_short'] = (df['ma_short'] | df['macd_short'] | df['rsi_short'] | df['bb_short']) & df['short_dc'] & df['short_rsi_filter']
        
        return df
    
    def _simulate_trades_lightning(self, df, initial_capital):
        """번개 속도 거래 시뮬레이션"""
        # 벡터화된 거래 시뮬레이션
        capital = initial_capital
        trades = []
        
        # 포지션 상태 추적
        position = None
        entry_price = 0
        entry_idx = 0
        
        for i in range(len(df)):
            current_price = df['close'].iloc[i]
            long_signal = df['final_long'].iloc[i]
            short_signal = df['final_short'].iloc[i]
            
            if position is None:
                if long_signal:
                    position = 'long'
                    entry_price = current_price
                    entry_idx = i
                elif short_signal:
                    position = 'short'
                    entry_price = current_price
                    entry_idx = i
            else:
                should_exit = False
                exit_reason = ""
                
                if position == 'long':
                    if short_signal:
                        should_exit = True
                        exit_reason = "숏 신호"
                    elif current_price <= entry_price * 0.97:
                        should_exit = True
                        exit_reason = "손절매"
                elif position == 'short':
                    if long_signal:
                        should_exit = True
                        exit_reason = "롱 신호"
                    elif current_price >= entry_price * 1.03:
                        should_exit = True
                        exit_reason = "손절매"
                
                if should_exit:
                    pnl = self._calculate_pnl_lightning(entry_price, current_price, capital, position)
                    capital += pnl
                    
                    trades.append({
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'position': position,
                        'pnl': pnl,
                        'exit_reason': exit_reason,
                        'final_capital': capital
                    })
                    
                    position = None
        
        # 결과 계산
        if len(trades) > 0:
            total_return = (capital - initial_capital) / initial_capital * 100
            winning_trades = len([t for t in trades if t['pnl'] > 0])
            win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0
            
            # 최대 낙폭 계산
            capital_series = [t['final_capital'] for t in trades]
            peak = np.maximum.accumulate(capital_series)
            drawdown = (peak - capital_series) / peak * 100
            max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
        else:
            total_return = 0.0
            win_rate = 0.0
            max_drawdown = 0.0
        
        result = {
            'total_return': total_return,
            'final_capital': capital,
            'total_trades': len(trades),
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'trades': trades
        }
        
        return result
    
    def _calculate_pnl_lightning(self, entry_price, exit_price, capital, position_type):
        """번개 속도 PnL 계산"""
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

def main():
    """메인 실행 함수"""
    print("=== 번개 속도 트레이딩 시스템 ===")
    
    # 시스템 초기화
    system = LightningTradingSystem()
    
    # 데이터 로드
    data_files = [
        "data/BTCUSDT/5m/BTCUSDT_5m_2024.csv",
        "data/BTCUSDT/1m/BTCUSDT_1m_2024.csv",
        "data/BTCUSDT/3m/BTCUSDT_3m_2024.csv"
    ]
    
    data_loaded = False
    for file_path in data_files:
        if system.load_data(file_path):
            print(f"데이터 로드: {file_path} ({len(system.data)}개 캔들)")
            data_loaded = True
            break
    
    if not data_loaded:
        print("데이터 파일을 찾을 수 없습니다.")
        return
    
    # 번개 속도 백테스트 실행
    result = system.run_lightning_backtest('2024-01-01', '2024-12-31')
    
    if result:
        print(f"\n번개 속도 결과:")
        print(f"  총 수익률: {result['total_return']:.2f}%")
        print(f"  최종 자본: {result['final_capital']:.2f}")
        print(f"  총 거래: {result['total_trades']}회")
        print(f"  승률: {result['win_rate']:.2f}%")
        print(f"  최대 낙폭: {result['max_drawdown']:.2f}%")
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
