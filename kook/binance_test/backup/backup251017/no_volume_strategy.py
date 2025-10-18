"""
볼륨 필터 완전 제거 전략 테스트
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class NoVolumeStrategy:
    def __init__(self):
        self.test_data = None
        
    def load_2025_data(self):
        """2025년 데이터 로드"""
        print("2025년 데이터 로딩 중...")
        
        file_path = "data/BTCUSDT/5m/BTCUSDT_5m_2025.csv"
        if not os.path.exists(file_path):
            print(f"파일을 찾을 수 없습니다: {file_path}")
            return False
            
        df = pd.read_csv(file_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        print(f"원본 데이터: {len(df)}개 캔들")
        print(f"기간: {df.index.min()} ~ {df.index.max()}")
        
        # 5분봉을 10분봉으로 리샘플링
        print("5분봉을 10분봉으로 리샘플링 중...")
        self.test_data = df.resample('10T').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        print(f"리샘플링 완료: {len(self.test_data)}개 캔들")
        return True
    
    def calculate_indicators(self, data, sma_short, sma_long, dcc_period):
        """기술적 지표 계산 (볼륨 필터 제외)"""
        df = data.copy()
        
        # 이동평균
        df['sma_short'] = df['close'].rolling(sma_short).mean()
        df['sma_long'] = df['close'].rolling(sma_long).mean()
        
        # 던키안 채널
        df['dcc_high'] = df['high'].rolling(dcc_period).max()
        df['dcc_low'] = df['low'].rolling(dcc_period).min()
        df['dcc_middle'] = (df['dcc_high'] + df['dcc_low']) / 2
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 볼륨 지표 (참고용, 필터로 사용하지 않음)
        df['volume_ma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        return df
    
    def generate_no_volume_signals(self, df):
        """볼륨 필터 없는 신호 생성"""
        # 롱 신호 (볼륨 필터 제외)
        long_ma_signal = (df['sma_short'] > df['sma_long']) & (df['sma_short'].shift(1) <= df['sma_long'].shift(1))
        long_dcc_signal = (df['close'] > df['dcc_middle']) & (df['close'] > df['dcc_low'] * 1.02)
        long_rsi_signal = df['rsi'] < 70
        
        # 숏 신호 (볼륨 필터 제외)
        short_ma_signal = (df['sma_short'] < df['sma_long']) & (df['sma_short'].shift(1) >= df['sma_long'].shift(1))
        short_dcc_signal = (df['close'] < df['dcc_middle']) & (df['close'] < df['dcc_high'] * 0.98)
        short_rsi_signal = df['rsi'] > 30
        
        # 최종 신호 (볼륨 조건 제외)
        long_signal = long_ma_signal & long_dcc_signal & long_rsi_signal
        short_signal = short_ma_signal & short_dcc_signal & short_rsi_signal
        
        # 동시 진입 방지
        conflict_mask = long_signal & short_signal
        long_signal = long_signal & ~conflict_mask
        short_signal = short_signal & ~conflict_mask
        
        df['long_signal'] = long_signal
        df['short_signal'] = short_signal
        df['conflict_count'] = conflict_mask.sum()
        
        return df
    
    def run_combined_backtest(self, data, initial_capital=10000, leverage_ratio=1.0):
        """결합된 전략 백테스트 실행"""
        df = data.copy()
        df = df.dropna()
        
        if len(df) == 0:
            return {
                'total_return': 0.0,
                'final_capital': initial_capital,
                'total_trades': 0,
                'win_rate': 0.0,
                'max_drawdown': 0.0,
                'long_trades': 0,
                'short_trades': 0
            }
        
        # 포지션 상태 추적
        position = None
        entry_price = 0
        trades = []
        capital = initial_capital
        
        for i, (timestamp, row) in enumerate(df.iterrows()):
            # 진입 신호
            if position is None:
                if row['long_signal']:
                    position = 'long'
                    entry_price = row['close']
                elif row['short_signal']:
                    position = 'short'
                    entry_price = row['close']
            
            # 청산 신호
            elif position == 'long':
                if row['short_signal'] or row['rsi'] > 80:
                    # 롱 청산
                    exit_price = row['close']
                    pnl = self._calculate_pnl(entry_price, exit_price, capital, leverage_ratio, 'long')
                    capital += pnl
                    trades.append({'type': 'long', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl})
                    position = None
                    
            elif position == 'short':
                if row['long_signal'] or row['rsi'] < 20:
                    # 숏 청산
                    exit_price = row['close']
                    pnl = self._calculate_pnl(entry_price, exit_price, capital, leverage_ratio, 'short')
                    capital += pnl
                    trades.append({'type': 'short', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl})
                    position = None
        
        # 결과 계산
        if len(trades) > 0:
            total_return = (capital - initial_capital) / initial_capital * 100
            winning_trades = len([t for t in trades if t['pnl'] > 0])
            win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0
            max_drawdown = self._calculate_max_drawdown(initial_capital, trades)
            long_trades = len([t for t in trades if t['type'] == 'long'])
            short_trades = len([t for t in trades if t['type'] == 'short'])
        else:
            total_return = 0.0
            win_rate = 0.0
            max_drawdown = 0.0
            long_trades = 0
            short_trades = 0
        
        return {
            'total_return': total_return,
            'final_capital': capital,
            'total_trades': len(trades),
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'long_trades': long_trades,
            'short_trades': short_trades
        }
    
    def _calculate_pnl(self, entry_price, exit_price, capital, leverage_ratio, position_type):
        """PnL 계산 (수수료 포함)"""
        fee_rate = 0.0005  # 0.05% 수수료
        leveraged_capital = capital * leverage_ratio
        
        if position_type == 'long':
            # 롱 거래: 진입 시 수수료 차감, 청산 시 수수료 차감
            entry_with_fee = entry_price * (1 + fee_rate)  # 진입 시 수수료 포함
            exit_with_fee = exit_price * (1 - fee_rate)    # 청산 시 수수료 차감
            amount = leveraged_capital / entry_with_fee
            pnl = (exit_with_fee - entry_with_fee) * amount
        else:  # short
            # 숏 거래: 진입 시 수수료 차감, 청산 시 수수료 포함
            entry_with_fee = entry_price * (1 - fee_rate)  # 진입 시 수수료 차감
            exit_with_fee = exit_price * (1 + fee_rate)    # 청산 시 수수료 포함
            amount = leveraged_capital / entry_with_fee
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
    
    def test_integrated_strategy(self):
        """통합 전략 테스트 (볼륨 필터 없음)"""
        print("=== 통합 전략 테스트 (볼륨 필터 없음) ===")
        
        if self.test_data is None:
            print("테스트 데이터가 없습니다.")
            return
        
        # 2022-2024년 최적화된 롱 파라미터 (통합 사용)
        #long_params = {'sma_short': 8, 'sma_long': 40, 'dcc_period': 25}
        long_params = {'sma_short': 3, 'sma_long': 40, 'dcc_period': 25}
        
        print("통합 전략 실행 중...")
        
        # 통합 파라미터 사용 (롱 파라미터 기준)
        combined_df = self.calculate_indicators(
            self.test_data,
            long_params['sma_short'],
            long_params['sma_long'],
            long_params['dcc_period']
        )
        combined_df = self.generate_no_volume_signals(combined_df)
        
        # 백테스트 실행
        result = self.run_combined_backtest(combined_df)
        
        # 점수 계산
        score = result['total_return'] - result['max_drawdown']
        
        print(f"\n=== 통합 전략 결과 ===")
        print(f"수익률: {result['total_return']:.2f}%")
        print(f"승률: {result['win_rate']:.2f}%")
        print(f"최대낙폭: {result['max_drawdown']:.2f}%")
        print(f"총 거래: {result['total_trades']} (롱: {result['long_trades']}, 숏: {result['short_trades']})")
        print(f"점수: {score:.2f}")
        
        return result

def main():
    """메인 실행 함수"""
    print("=== 통합 전략 테스트 (볼륨 필터 없음) ===")
    
    # 시스템 초기화
    system = NoVolumeStrategy()
    
    # 데이터 로드
    if not system.load_2025_data():
        return
    
    # 통합 전략 테스트
    system.test_integrated_strategy()
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
