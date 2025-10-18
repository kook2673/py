"""
고정 파라미터 백테스트 시스템 (2018-2025 전체 기간)

=== 고정 파라미터 방식 ===
- 최적화 없이 고정된 안정적 파라미터 사용
- 전체 기간: 2018년 ~ 2025년
- 시간프레임: 10분봉
- 자본 추적: 만달러 시작 → 최종 자본 표시

=== 지원 전략 ===
- MACD + DC (롱/숏 분리)
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class FixedParamsBacktest:
    def __init__(self):
        self.data = None
        self.timeframe = '10T'  # 10분봉으로 통일
        
        # 고정 파라미터 (안정적 수치)
        self.macd_long_params = {
            'macd_fast': 12,  # 표준
            'macd_slow': 26,  # 표준
            'macd_signal': 9, # 표준
            'dc_period': 25,  # 기본
            'rsi_threshold': 70, # 기본
            'dc_multiplier': 1.02, # 기본
            'stop_loss_pct': 5  # 기본
        }
        
        self.macd_short_params = {
            'macd_fast': 12,  # 표준
            'macd_slow': 26,  # 표준
            'macd_signal': 9, # 표준
            'dc_period': 25,  # 기본
            'rsi_threshold': 30, # 기본
            'dc_multiplier': 0.98, # 기본
            'stop_loss_pct': 5  # 기본
        }
        
        # MA + DC 고정 파라미터
        self.ma_params = {
            'sma_short': 5,   # 단기 이동평균
            'sma_long': 40,   # 장기 이동평균
            'dc_period': 25,  # 던키안 채널 기간
            'stop_loss_pct': 5  # 손절매
        }
    
    def load_all_data(self):
        """모든 연도 데이터 로드"""
        print("전체 데이터 로딩 중...")
        
        all_data = []
        for year in range(2018, 2026):  # 2018~2025
            file_path = f"data/BTCUSDT/5m/BTCUSDT_5m_{year}.csv"
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
                all_data.append(df)
                print(f"{year}년 데이터 로드: {len(df)}개 캔들")
            else:
                print(f"{year}년 데이터 파일을 찾을 수 없습니다.")
        
        if all_data:
            self.data = pd.concat(all_data, ignore_index=False)
            self.data = self.data.sort_index()
            print(f"전체 데이터: {len(self.data)}개 캔들")
            print(f"기간: {self.data.index.min()} ~ {self.data.index.max()}")
            
            # 10분봉으로 리샘플링
            print("10분봉으로 리샘플링 중...")
            self.data = self.data.resample('10T').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            print(f"리샘플링 완료: {len(self.data)}개 캔들")
        else:
            print("데이터를 로드할 수 없습니다.")
            return False
        
        return True
    
    def calculate_macd_indicators(self, data, macd_fast, macd_slow, macd_signal, dc_period):
        """MACD 지표 계산"""
        df = data.copy()
        
        # MACD 계산
        ema_fast = df['close'].ewm(span=macd_fast).mean()
        ema_slow = df['close'].ewm(span=macd_slow).mean()
        df['macd_line'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd_line'].ewm(span=macd_signal).mean()
        df['macd_histogram'] = df['macd_line'] - df['macd_signal']
        
        # 던키안 채널
        df['dc_high'] = df['high'].rolling(dc_period).max()
        df['dc_low'] = df['low'].rolling(dc_period).min()
        df['dc_middle'] = (df['dc_high'] + df['dc_low']) / 2
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def calculate_ma_indicators(self, data, sma_short, sma_long, dc_period):
        """MA 지표 계산"""
        df = data.copy()
        
        # 이동평균
        df['sma_short'] = df['close'].rolling(sma_short).mean()
        df['sma_long'] = df['close'].rolling(sma_long).mean()
        
        # 던키안 채널
        df['dc_high'] = df['high'].rolling(dc_period).max()
        df['dc_low'] = df['low'].rolling(dc_period).min()
        df['dc_middle'] = (df['dc_high'] + df['dc_low']) / 2
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def generate_ma_signals(self, df):
        """MA + DC 신호 생성"""
        # 롱 신호
        long_ma_signal = (df['sma_short'] > df['sma_long']) & (df['sma_short'].shift(1) <= df['sma_long'].shift(1))
        long_dc_signal = (df['close'] > df['dc_middle']) & (df['close'] > df['dc_low'] * 1.02)
        long_rsi_signal = df['rsi'] < 70
        
        # 숏 신호
        short_ma_signal = (df['sma_short'] < df['sma_long']) & (df['sma_short'].shift(1) >= df['sma_long'].shift(1))
        short_dc_signal = (df['close'] < df['dc_middle']) & (df['close'] < df['dc_high'] * 0.98)
        short_rsi_signal = df['rsi'] > 30
        
        # 최종 신호
        long_signal = long_ma_signal & long_dc_signal & long_rsi_signal
        short_signal = short_ma_signal & short_dc_signal & short_rsi_signal
        
        df['long_signal'] = long_signal
        df['short_signal'] = short_signal
        
        return df
    
    def generate_macd_long_signals(self, df, rsi_threshold=70, dc_multiplier=1.02):
        """MACD 롱 전용 신호 생성"""
        # 롱 신호만 생성
        long_macd_signal = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
        long_dc_signal = (df['close'] > df['dc_middle']) & (df['close'] > df['dc_low'] * dc_multiplier)
        long_rsi_signal = df['rsi'] < rsi_threshold
        
        # 롱 신호만 활성화
        long_signal = long_macd_signal & long_dc_signal & long_rsi_signal
        short_signal = False  # 숏 신호 비활성화
        
        df['long_signal'] = long_signal
        df['short_signal'] = short_signal
        
        return df
    
    def generate_macd_short_signals(self, df, rsi_threshold=30, dc_multiplier=0.98):
        """MACD 숏 전용 신호 생성"""
        # 숏 신호만 생성
        short_macd_signal = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
        short_dc_signal = (df['close'] < df['dc_middle']) & (df['close'] < df['dc_high'] * dc_multiplier)
        short_rsi_signal = df['rsi'] > rsi_threshold
        
        # 숏 신호만 활성화
        long_signal = False  # 롱 신호 비활성화
        short_signal = short_macd_signal & short_dc_signal & short_rsi_signal
        
        df['long_signal'] = long_signal
        df['short_signal'] = short_signal
        
        return df
    
    def run_backtest(self, data, initial_capital=10000, leverage_ratio=1.0, stop_loss_pct=5.0):
        """백테스트 실행 (손절매 포함, 자본 추적)"""
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
                'short_trades': 0,
                'capital_history': [initial_capital]
            }
        
        # 포지션 상태 추적
        position = None
        entry_price = 0
        trades = []
        capital = initial_capital
        capital_history = [initial_capital]  # 자본 추적
        
        for i, (timestamp, row) in enumerate(df.iterrows()):
            # 진입 신호
            if position is None:
                if row['long_signal']:
                    position = 'long'
                    entry_price = row['close']
                elif row['short_signal']:
                    position = 'short'
                    entry_price = row['close']
            
            # 청산 신호 (손절매 포함)
            elif position == 'long':
                # 손절매 체크
                stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
                should_exit = (row['short_signal'] or row['rsi'] > 80 or row['close'] <= stop_loss_price)
                
                if should_exit:
                    # 롱 청산
                    exit_price = row['close']
                    pnl = self._calculate_pnl(entry_price, exit_price, capital, leverage_ratio, 'long')
                    capital += pnl
                    trades.append({'type': 'long', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl})
                    position = None
                    
            elif position == 'short':
                # 손절매 체크
                stop_loss_price = entry_price * (1 + stop_loss_pct / 100)
                should_exit = (row['long_signal'] or row['rsi'] < 20 or row['close'] >= stop_loss_price)
                
                if should_exit:
                    # 숏 청산
                    exit_price = row['close']
                    pnl = self._calculate_pnl(entry_price, exit_price, capital, leverage_ratio, 'short')
                    capital += pnl
                    trades.append({'type': 'short', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl})
                    position = None
            
            # 자본 추적 (매 캔들마다 기록)
            capital_history.append(capital)
        
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
            'short_trades': short_trades,
            'capital_history': capital_history
        }
    
    def _calculate_pnl(self, entry_price, exit_price, capital, leverage_ratio, position_type):
        """PnL 계산 (수수료 포함)"""
        fee_rate = 0.0005  # 0.05% 수수료
        leveraged_capital = capital * leverage_ratio
        
        if position_type == 'long':
            entry_with_fee = entry_price * (1 + fee_rate)
            exit_with_fee = exit_price * (1 - fee_rate)
            amount = leveraged_capital / entry_with_fee
            pnl = (exit_with_fee - entry_with_fee) * amount
        else:  # short
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
    
    def run_fixed_backtest(self):
        """고정 파라미터 백테스트 실행"""
        print("=== 고정 파라미터 백테스트 시작 ===")
        print(f"시작 자본: $10,000")
        
        if not self.load_all_data():
            return None
        
        # MACD 전략 주석처리
        # print(f"\n=== MACD 롱 전략 (고정 파라미터) ===")
        # print(f"파라미터: {self.macd_long_params}")
        # 
        # # MACD 롱 전략
        # macd_long_data = self.calculate_macd_indicators(
        #     self.data,
        #     self.macd_long_params['macd_fast'],
        #     self.macd_long_params['macd_slow'],
        #     self.macd_long_params['macd_signal'],
        #     self.macd_long_params['dc_period']
        # )
        # macd_long_data = self.generate_macd_long_signals(
        #     macd_long_data,
        #     self.macd_long_params['rsi_threshold'],
        #     self.macd_long_params['dc_multiplier']
        # )
        # macd_long_result = self.run_backtest(
        #     macd_long_data,
        #     stop_loss_pct=self.macd_long_params['stop_loss_pct']
        # )
        # 
        # print(f"\n=== MACD 숏 전략 (고정 파라미터) ===")
        # print(f"파라미터: {self.macd_short_params}")
        # 
        # # MACD 숏 전략
        # macd_short_data = self.calculate_macd_indicators(
        #     self.data,
        #     self.macd_short_params['macd_fast'],
        #     self.macd_short_params['macd_slow'],
        #     self.macd_short_params['macd_signal'],
        #     self.macd_short_params['dc_period']
        # )
        # macd_short_data = self.generate_macd_short_signals(
        #     macd_short_data,
        #     self.macd_short_params['rsi_threshold'],
        #     self.macd_short_params['dc_multiplier']
        # )
        # macd_short_result = self.run_backtest(
        #     macd_short_data,
        #     stop_loss_pct=self.macd_short_params['stop_loss_pct']
        # )
        
        print(f"\n=== MA + DC 전략 (고정 파라미터) ===")
        print(f"파라미터: {self.ma_params}")
        
        # MA + DC 전략
        ma_data = self.calculate_ma_indicators(
            self.data,
            self.ma_params['sma_short'],
            self.ma_params['sma_long'],
            self.ma_params['dc_period']
        )
        ma_data = self.generate_ma_signals(ma_data)
        ma_result = self.run_backtest(
            ma_data,
            stop_loss_pct=self.ma_params['stop_loss_pct']
        )
        
        # 연도별 성과 분석
        yearly_results = self.analyze_yearly_performance(ma_data)
        
        # 결과 출력
        print(f"\n=== MA + DC 전략 전체 기간 결과 ===")
        print(f"  최종 자본: ${ma_result['final_capital']:,.2f}")
        print(f"  수익률: {ma_result['total_return']:.2f}%")
        print(f"  승률: {ma_result['win_rate']:.2f}%")
        print(f"  거래횟수: {ma_result['total_trades']}회")
        print(f"  최대낙폭: {ma_result['max_drawdown']:.2f}%")
        
        # 연도별 성과 출력
        print(f"\n=== MA + DC 전략 연도별 성과 ===")
        for year, result in yearly_results.items():
            print(f"{year}년:")
            print(f"  최종 자본: ${result['final_capital']:,.2f}")
            print(f"  수익률: {result['total_return']:.2f}%")
            print(f"  승률: {result['win_rate']:.2f}%")
            print(f"  거래횟수: {result['total_trades']}회")
            print(f"  최대낙폭: {result['max_drawdown']:.2f}%")
            print()
        
        # 자본 추적 정보
        print(f"\n=== 자본 추적 ===")
        print(f"시작 자본: $10,000")
        print(f"MA + DC 최종 자본: ${ma_result['final_capital']:,.2f}")
        
        # 통합 결과
        combined_result = {
            'period': '2018-2025 전체 기간',
            'timeframe': '10분봉',
            'initial_capital': 10000,
            'ma_params': self.ma_params,
            'ma_result': ma_result,
            'yearly_results': yearly_results
        }
        
        return combined_result
    
    def analyze_yearly_performance(self, data):
        """연도별 성과 분석"""
        yearly_results = {}
        
        for year in range(2018, 2026):
            # 연도별 데이터 추출
            year_start = f'{year}-01-01'
            year_end = f'{year}-12-31'
            
            year_data = data[(data.index >= year_start) & (data.index <= year_end)]
            
            if len(year_data) == 0:
                continue
            
            # 연도별 백테스트 실행
            year_result = self.run_backtest(
                year_data,
                stop_loss_pct=self.ma_params['stop_loss_pct']
            )
            
            yearly_results[f'{year}'] = year_result
        
        return yearly_results
    
    def save_results(self, result):
        """결과 저장"""
        output = {
            'backtest_type': 'Fixed Parameters Backtest',
            'timeframe': '10분봉',
            'period': '2018-2025 전체 기간',
            'initial_capital': 10000,
            'strategies': ['MACD + DC (Long)', 'MACD + DC (Short)'],
            'result': result,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open('fixed_params_backtest_results.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n결과가 fixed_params_backtest_results.json에 저장되었습니다.")

def main():
    """메인 실행 함수"""
    print("=== 고정 파라미터 백테스트 시스템 ===")
    print("시작 자본: $10,000")
    print("기간: 2018년 ~ 2025년")
    print("시간프레임: 10분봉")
    
    # 고정 파라미터 백테스트 시스템 초기화
    backtest = FixedParamsBacktest()
    
    # 백테스트 실행
    result = backtest.run_fixed_backtest()
    
    if result:
        # 결과 저장
        backtest.save_results(result)
        
        # 최종 요약
        print(f"\n=== 최종 요약 ===")
        print(f"MA + DC 전체: ${result['ma_result']['final_capital']:,.2f} ({result['ma_result']['total_return']:.2f}%)")
        
        # 연도별 요약
        print(f"\n=== 연도별 요약 ===")
        for year, year_result in result['yearly_results'].items():
            print(f"{year}년: ${year_result['final_capital']:,.2f} ({year_result['total_return']:.2f}%)")
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()