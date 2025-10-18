"""
통합 전략 백테스트 시스템 (MACD + DCC + MA + DCC)

=== 지원 전략 ===
1. MACD + DCC 전략
2. MA + DCC 전략

=== 지원 시간프레임 ===
- 10분봉 (10T)
- 15분봉 (15T) 
- 30분봉 (30T)
- 1시간봉 (1H)
- 4시간봉 (4H)

=== 통합 전략 특징 ===
- 두 전략이 동시에 신호를 생성
- 신호 충돌 시 우선순위 적용
- 각 전략별 성능 추적
- 시간프레임별 성능 비교
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class IntegratedStrategyBacktest:
    def __init__(self):
        self.data = None
        self.optimization_data = None  # 2024년 데이터
        self.test_data = None  # 2025년 데이터
        
        # 시간프레임 설정
        self.timeframes = {
            '10분봉': '10T',
            '15분봉': '15T', 
            '30분봉': '30T',
            '1시간봉': '1H',
            '4시간봉': '4H'
        }
        
        # 전략별 최적 파라미터
        self.macd_params = {
            'macd_fast': 12,
            'macd_slow': 24,
            'macd_signal': 11,
            'dcc_period': 25
        }
        
        self.ma_params = {
            'sma_short': 6,
            'sma_long': 20,
            'dcc_period': 25
        }
    
    def load_data(self):
        """데이터 로드"""
        print("데이터 로딩 중...")
        
        # 2024년 데이터 (최적화용)
        optimization_file = "data/BTCUSDT/5m/BTCUSDT_5m_2024.csv"
        if os.path.exists(optimization_file):
            df = pd.read_csv(optimization_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            self.optimization_data = df
            print(f"최적화용 데이터 로드: {len(self.optimization_data)}개 캔들")
        else:
            print("2024년 데이터 파일을 찾을 수 없습니다.")
            return
        
        # 2025년 데이터 (테스트용)
        test_file = "data/BTCUSDT/5m/BTCUSDT_5m_2025.csv"
        if os.path.exists(test_file):
            df = pd.read_csv(test_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            self.test_data = df
            print(f"테스트용 데이터 로드: {len(self.test_data)}개 캔들")
        else:
            print("2025년 데이터 파일을 찾을 수 없습니다.")
            return
    
    def resample_data(self, data, timeframe):
        """데이터 리샘플링"""
        if timeframe == '5T':  # 5분봉은 리샘플링 없음
            return data
        
        resampled = data.resample(timeframe).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        return resampled
    
    def calculate_macd_indicators(self, data):
        """MACD 지표 계산"""
        df = data.copy()
        
        # MACD 계산
        ema_fast = df['close'].ewm(span=self.macd_params['macd_fast']).mean()
        ema_slow = df['close'].ewm(span=self.macd_params['macd_slow']).mean()
        df['macd_line'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd_line'].ewm(span=self.macd_params['macd_signal']).mean()
        df['macd_histogram'] = df['macd_line'] - df['macd_signal']
        
        # 던키안 채널
        df['dcc_high'] = df['high'].rolling(self.macd_params['dcc_period']).max()
        df['dcc_low'] = df['low'].rolling(self.macd_params['dcc_period']).min()
        df['dcc_middle'] = (df['dcc_high'] + df['dcc_low']) / 2
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def calculate_ma_indicators(self, data):
        """MA 지표 계산"""
        df = data.copy()
        
        # 이동평균
        df['sma_short'] = df['close'].rolling(self.ma_params['sma_short']).mean()
        df['sma_long'] = df['close'].rolling(self.ma_params['sma_long']).mean()
        
        # 던키안 채널
        df['dcc_high'] = df['high'].rolling(self.ma_params['dcc_period']).max()
        df['dcc_low'] = df['low'].rolling(self.ma_params['dcc_period']).min()
        df['dcc_middle'] = (df['dcc_high'] + df['dcc_low']) / 2
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def generate_macd_signals(self, df):
        """MACD + DCC 신호 생성"""
        # 롱 신호
        long_macd_signal = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
        long_dcc_signal = (df['close'] > df['dcc_middle']) & (df['close'] > df['dcc_low'] * 1.02)
        long_rsi_signal = df['rsi'] < 70
        
        # 숏 신호
        short_macd_signal = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
        short_dcc_signal = (df['close'] < df['dcc_middle']) & (df['close'] < df['dcc_high'] * 0.98)
        short_rsi_signal = df['rsi'] > 30
        
        # 최종 신호
        long_signal = long_macd_signal & long_dcc_signal & long_rsi_signal
        short_signal = short_macd_signal & short_dcc_signal & short_rsi_signal
        
        df['macd_long_signal'] = long_signal
        df['macd_short_signal'] = short_signal
        
        return df
    
    def generate_ma_signals(self, df):
        """MA + DCC 신호 생성"""
        # 롱 신호
        long_ma_signal = (df['sma_short'] > df['sma_long']) & (df['sma_short'].shift(1) <= df['sma_long'].shift(1))
        long_dcc_signal = (df['close'] > df['dcc_middle']) & (df['close'] > df['dcc_low'] * 1.02)
        long_rsi_signal = df['rsi'] < 70
        
        # 숏 신호
        short_ma_signal = (df['sma_short'] < df['sma_long']) & (df['sma_short'].shift(1) >= df['sma_long'].shift(1))
        short_dcc_signal = (df['close'] < df['dcc_middle']) & (df['close'] < df['dcc_high'] * 0.98)
        short_rsi_signal = df['rsi'] > 30
        
        # 최종 신호
        long_signal = long_ma_signal & long_dcc_signal & long_rsi_signal
        short_signal = short_ma_signal & short_dcc_signal & short_rsi_signal
        
        df['ma_long_signal'] = long_signal
        df['ma_short_signal'] = short_signal
        
        return df
    
    def generate_integrated_signals(self, df):
        """통합 신호 생성 (두 전략 결합)"""
        # MACD 전략 신호
        macd_long = df['macd_long_signal']
        macd_short = df['macd_short_signal']
        
        # MA 전략 신호
        ma_long = df['ma_long_signal']
        ma_short = df['ma_short_signal']
        
        # 통합 신호 (OR 조건)
        integrated_long = macd_long | ma_long
        integrated_short = macd_short | ma_short
        
        # 동시 진입 방지
        conflict_mask = integrated_long & integrated_short
        integrated_long = integrated_long & ~conflict_mask
        integrated_short = integrated_short & ~conflict_mask
        
        df['integrated_long_signal'] = integrated_long
        df['integrated_short_signal'] = integrated_short
        df['conflict_count'] = conflict_mask.sum()
        
        return df
    
    def run_backtest(self, data, strategy_type='integrated', initial_capital=10000, leverage_ratio=1.0):
        """백테스트 실행"""
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
        
        # 신호 선택
        if strategy_type == 'macd':
            long_signal = df['macd_long_signal']
            short_signal = df['macd_short_signal']
        elif strategy_type == 'ma':
            long_signal = df['ma_long_signal']
            short_signal = df['ma_short_signal']
        else:  # integrated
            long_signal = df['integrated_long_signal']
            short_signal = df['integrated_short_signal']
        
        # 포지션 상태 추적
        position = None
        entry_price = 0
        trades = []
        capital = initial_capital
        
        for i, (timestamp, row) in enumerate(df.iterrows()):
            # 진입 신호
            if position is None:
                if long_signal.iloc[i]:
                    position = 'long'
                    entry_price = row['close']
                elif short_signal.iloc[i]:
                    position = 'short'
                    entry_price = row['close']
            
            # 청산 신호
            elif position == 'long':
                if short_signal.iloc[i] or row['rsi'] > 80:
                    # 롱 청산
                    exit_price = row['close']
                    pnl = self._calculate_pnl(entry_price, exit_price, capital, leverage_ratio, 'long')
                    capital += pnl
                    trades.append({'type': 'long', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl})
                    position = None
                    
            elif position == 'short':
                if long_signal.iloc[i] or row['rsi'] < 20:
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
            # 롱 거래: 진입 시 수수료 포함, 청산 시 수수료 차감
            entry_with_fee = entry_price * (1 + fee_rate)
            exit_with_fee = exit_price * (1 - fee_rate)
            amount = leveraged_capital / entry_with_fee
            pnl = (exit_with_fee - entry_with_fee) * amount
        else:  # short
            # 숏 거래: 진입 시 수수료 차감, 청산 시 수수료 포함
            entry_with_fee = entry_price * (1 - fee_rate)
            exit_with_fee = exit_price * (1 + fee_rate)
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
    
    def test_all_timeframes(self):
        """모든 시간프레임에서 테스트"""
        print("=== 통합 전략 다중 시간프레임 백테스트 ===")
        
        if self.test_data is None:
            print("테스트 데이터가 없습니다.")
            return None
        
        results = {}
        
        for timeframe_name, timeframe_code in self.timeframes.items():
            print(f"\n--- {timeframe_name} 테스트 ---")
            
            # 데이터 리샘플링
            test_data = self.resample_data(self.test_data, timeframe_code)
            print(f"리샘플링 완료: {len(test_data)}개 캔들")
            
            # 지표 계산
            macd_data = self.calculate_macd_indicators(test_data)
            ma_data = self.calculate_ma_indicators(test_data)
            
            # 신호 생성
            macd_data = self.generate_macd_signals(macd_data)
            ma_data = self.generate_ma_signals(ma_data)
            
            # 통합 데이터 생성
            integrated_data = macd_data.copy()
            integrated_data['ma_long_signal'] = ma_data['ma_long_signal']
            integrated_data['ma_short_signal'] = ma_data['ma_short_signal']
            integrated_data = self.generate_integrated_signals(integrated_data)
            
            # 각 전략별 백테스트
            macd_result = self.run_backtest(integrated_data, 'macd')
            ma_result = self.run_backtest(integrated_data, 'ma')
            integrated_result = self.run_backtest(integrated_data, 'integrated')
            
            # 결과 저장
            results[timeframe_name] = {
                'timeframe': timeframe_code,
                'macd_strategy': macd_result,
                'ma_strategy': ma_result,
                'integrated_strategy': integrated_result
            }
            
            # 결과 출력
            print(f"MACD + DCC: 수익률 {macd_result['total_return']:.2f}%, 승률 {macd_result['win_rate']:.2f}%, MDD {macd_result['max_drawdown']:.2f}%")
            print(f"MA + DCC: 수익률 {ma_result['total_return']:.2f}%, 승률 {ma_result['win_rate']:.2f}%, MDD {ma_result['max_drawdown']:.2f}%")
            print(f"통합 전략: 수익률 {integrated_result['total_return']:.2f}%, 승률 {integrated_result['win_rate']:.2f}%, MDD {integrated_result['max_drawdown']:.2f}%")
        
        return results
    
    def save_results(self, results):
        """결과 저장"""
        output = {
            'test_period': '2025년 전체',
            'strategy_types': ['MACD + DCC', 'MA + DCC', '통합 전략'],
            'timeframes_tested': list(self.timeframes.keys()),
            'results': results,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open('integrated_strategy_results.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n결과가 integrated_strategy_results.json에 저장되었습니다.")

def main():
    """메인 실행 함수"""
    print("=== 통합 전략 다중 시간프레임 백테스트 시스템 ===")
    
    # 시스템 초기화
    system = IntegratedStrategyBacktest()
    
    # 데이터 로드
    system.load_data()
    
    # 모든 시간프레임에서 테스트
    results = system.test_all_timeframes()
    
    if results:
        # 결과 저장
        system.save_results(results)
        
        # 최종 요약
        print("\n=== 최종 요약 ===")
        for timeframe, data in results.items():
            print(f"\n{timeframe}:")
            print(f"  MACD + DCC: {data['macd_strategy']['total_return']:.2f}%")
            print(f"  MA + DCC: {data['ma_strategy']['total_return']:.2f}%")
            print(f"  통합 전략: {data['integrated_strategy']['total_return']:.2f}%")
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
