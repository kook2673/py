"""
Walk-Forward Optimization (WFO) 백테스트 시스템

=== WFO 방식 ===
- 최적화: 1년 단위 (6개월 겹침)
- 백테스트: 6개월 단위
- 시간프레임: 10분봉 (통일)

=== 최적화/백테스트 일정 ===
1. 2018년 최적화 → 2019년 1월~6월 백테스트
2. 2018년 7월~2019년 6월 최적화 → 2019년 7월~12월 백테스트
3. 2019년 1월~2019년 12월 최적화 → 2020년 1월~6월 백테스트
4. 2019년 7월~2020년 6월 최적화 → 2020년 7월~12월 백테스트
... (이런 식으로 진행)

=== 지원 전략 ===
- MACD + DC
- MA + DC
- BB + DC
- 통합 전략 (MACD + MA + BB + DC)
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class WFOBacktest:
    def __init__(self):
        self.data = None
        self.timeframe = '10T'  # 10분봉으로 통일
        
        # MA 전략만 사용
        self.ma_grid = {
            'sma_short': [3, 6, 9, 12, 15],
            'sma_long': [20, 30, 40, 50],
            'dc_period': [25]
        }
        
        # BB 전략 삭제
        # self.bb_grid = {
        #     'bb_period': [15, 20, 25, 30],
        #     'bb_std': [1.5, 2.0, 2.5],
        #     'dc_period': [20, 25, 30]
        # }
        
        # WFO 일정 설정
        self.wfo_schedule = self._create_wfo_schedule()
    
    def _create_wfo_schedule(self):
        """WFO 일정 생성 (2년 학습 + 6개월 백테스트)"""
        schedule = []
        
        # 2020년 1월~6월부터 시작 (2018, 2019년 학습)
        test_periods = [
            {'year': 2020, 'start_month': 1, 'end_month': 6},
            {'year': 2020, 'start_month': 7, 'end_month': 12},
            {'year': 2021, 'start_month': 1, 'end_month': 6},
            {'year': 2021, 'start_month': 7, 'end_month': 12},
            {'year': 2022, 'start_month': 1, 'end_month': 6},
            {'year': 2022, 'start_month': 7, 'end_month': 12},
            {'year': 2023, 'start_month': 1, 'end_month': 6},
            {'year': 2023, 'start_month': 7, 'end_month': 12},
            {'year': 2024, 'start_month': 1, 'end_month': 6},
            {'year': 2024, 'start_month': 7, 'end_month': 12},
            {'year': 2025, 'start_month': 1, 'end_month': 6},
            {'year': 2025, 'start_month': 7, 'end_month': 12}
        ]
        
        for period in test_periods:
            year = period['year']
            start_month = period['start_month']
            end_month = period['end_month']
            
            # 2년 학습 기간 (테스트 기간 이전 2년)
            if start_month <= 6:
                # 상반기 테스트: 이전 2년 (예: 2020년 1-6월 테스트 → 2018-2019년 학습)
                opt_start = f'{year-2}-01-01'
                opt_end = f'{year-1}-12-31'
            else:
                # 하반기 테스트: 이전 2년 (예: 2020년 7-12월 테스트 → 2018년 7월-2020년 6월 학습)
                opt_start = f'{year-2}-07-01'
                opt_end = f'{year}-06-30'
            
            # 테스트 기간
            test_start = f'{year}-{start_month:02d}-01'
            if end_month == 12:
                test_end = f'{year}-12-31'
            else:
                test_end = f'{year}-{end_month:02d}-30'
            
            schedule.append({
                'optimization_start': opt_start,
                'optimization_end': opt_end,
                'test_start': test_start,
                'test_end': test_end,
                'period': f'{year}년 {start_month}월~{end_month}월'
            })
        
        return schedule
    
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
    
    def get_data_period(self, start_date, end_date):
        """특정 기간 데이터 추출"""
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        mask = (self.data.index >= start_dt) & (self.data.index <= end_dt)
        return self.data[mask].copy()
    
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
    
    def calculate_bb_indicators(self, data, bb_period, bb_std, dc_period):
        """BB 지표 계산"""
        df = data.copy()
        
        # 볼린저 밴드
        df['bb_middle'] = df['close'].rolling(bb_period).mean()
        bb_std_val = df['close'].rolling(bb_period).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std_val * bb_std)
        df['bb_lower'] = df['bb_middle'] - (bb_std_val * bb_std)
        
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
    
    def generate_macd_signals(self, df):
        """MACD + DCC 신호 생성"""
        # 롱 신호
        long_macd_signal = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
        long_dcc_signal = (df['close'] > df['dc_middle']) & (df['close'] > df['dc_low'] * 1.02)
        long_rsi_signal = df['rsi'] < 70
        
        # 숏 신호
        short_macd_signal = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
        short_dcc_signal = (df['close'] < df['dc_middle']) & (df['close'] < df['dc_high'] * 0.98)
        short_rsi_signal = df['rsi'] > 30
        
        # 최종 신호
        long_signal = long_macd_signal & long_dcc_signal & long_rsi_signal
        short_signal = short_macd_signal & short_dcc_signal & short_rsi_signal
        
        df['long_signal'] = long_signal
        df['short_signal'] = short_signal
        
        return df
    
    def generate_macd_signals_advanced(self, df, long_rsi_threshold=70, short_rsi_threshold=30, 
                                       long_dc_multiplier=1.02, short_dc_multiplier=0.98):
        """MACD + DC 신호 생성 (롱/숏 분리 파라미터)"""
        # 롱 신호
        long_macd_signal = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
        long_dc_signal = (df['close'] > df['dc_middle']) & (df['close'] > df['dc_low'] * long_dc_multiplier)
        long_rsi_signal = df['rsi'] < long_rsi_threshold
        
        # 숏 신호
        short_macd_signal = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
        short_dc_signal = (df['close'] < df['dc_middle']) & (df['close'] < df['dc_high'] * short_dc_multiplier)
        short_rsi_signal = df['rsi'] > short_rsi_threshold
        
        # 최종 신호
        long_signal = long_macd_signal & long_dc_signal & long_rsi_signal
        short_signal = short_macd_signal & short_dc_signal & short_rsi_signal
        
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
    
    def generate_ma_signals(self, df):
        """MA + DCC 신호 생성"""
        # 롱 신호
        long_ma_signal = (df['sma_short'] > df['sma_long']) & (df['sma_short'].shift(1) <= df['sma_long'].shift(1))
        long_dcc_signal = (df['close'] > df['dc_middle']) & (df['close'] > df['dc_low'] * 1.02)
        long_rsi_signal = df['rsi'] < 70
        
        # 숏 신호
        short_ma_signal = (df['sma_short'] < df['sma_long']) & (df['sma_short'].shift(1) >= df['sma_long'].shift(1))
        short_dcc_signal = (df['close'] < df['dc_middle']) & (df['close'] < df['dc_high'] * 0.98)
        short_rsi_signal = df['rsi'] > 30
        
        # 최종 신호
        long_signal = long_ma_signal & long_dcc_signal & long_rsi_signal
        short_signal = short_ma_signal & short_dcc_signal & short_rsi_signal
        
        df['long_signal'] = long_signal
        df['short_signal'] = short_signal
        
        return df
    
    def generate_bb_signals(self, df):
        """BB + DC 신호 생성 (개선된 버전)"""
        # 롱 신호: BB 하단 근처 + DC 조건 (더 관대하게)
        long_bb_signal = (df['close'] <= df['bb_lower'] * 1.01)  # BB 하단 근처
        long_dc_signal = (df['close'] > df['dc_middle'])  # DC 중간선 위
        long_rsi_signal = df['rsi'] < 75  # RSI 조건 완화
        
        # 숏 신호: BB 상단 근처 + DC 조건 (더 관대하게)
        short_bb_signal = (df['close'] >= df['bb_upper'] * 0.99)  # BB 상단 근처
        short_dc_signal = (df['close'] < df['dc_middle'])  # DC 중간선 아래
        short_rsi_signal = df['rsi'] > 25  # RSI 조건 완화
        
        # 최종 신호 (조건 완화)
        long_signal = long_bb_signal & long_dc_signal & long_rsi_signal
        short_signal = short_bb_signal & short_dc_signal & short_rsi_signal
        
        df['long_signal'] = long_signal
        df['short_signal'] = short_signal
        
        return df
    
    def run_backtest(self, data, initial_capital=10000, leverage_ratio=1.0, stop_loss_pct=5.0):
        """백테스트 실행 (손절매 포함)"""
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
    
    def optimize_macd_long_parameters(self, optimization_data):
        """MACD 롱 파라미터 최적화"""
        print("MACD 롱 파라미터 최적화 중...")
        
        best_result = None
        best_score = -999999
        
        total_combinations = (len(self.macd_long_grid['macd_fast']) * 
                            len(self.macd_long_grid['macd_slow']) * 
                            len(self.macd_long_grid['macd_signal']) * 
                            len(self.macd_long_grid['dc_period']) *
                            len(self.macd_long_grid['rsi_threshold']) *
                            len(self.macd_long_grid['dc_multiplier']) *
                            len(self.macd_long_grid['stop_loss_pct']))
        
        combination_count = 0
        
        # 전체 데이터 사용
        sample_data = optimization_data
        
        for macd_fast in self.macd_long_grid['macd_fast']:
            for macd_slow in self.macd_long_grid['macd_slow']:
                if macd_fast >= macd_slow:
                    continue
                    
                for macd_signal in self.macd_long_grid['macd_signal']:
                    for dc_period in self.macd_long_grid['dc_period']:
                        for rsi_threshold in self.macd_long_grid['rsi_threshold']:
                            for dc_multiplier in self.macd_long_grid['dc_multiplier']:
                                for stop_loss_pct in self.macd_long_grid['stop_loss_pct']:
                                    combination_count += 1
                                    
                                    if combination_count % 50 == 0:
                                        print(f"MACD 롱 최적화 진행률: {combination_count}/{total_combinations}")
                                    
                                    try:
                                        # 지표 계산
                                        df = self.calculate_macd_indicators(
                                            sample_data, macd_fast, macd_slow, macd_signal, dc_period
                                        )
                                        # 롱 전용 신호 생성
                                        df = self.generate_macd_long_signals(df, rsi_threshold, dc_multiplier)
                                        
                                        # 백테스트 실행 (손절매 포함)
                                        result = self.run_backtest(df, stop_loss_pct=stop_loss_pct)
                                        
                                        # 점수 계산 (수익률 - 최대낙폭)
                                        score = result['total_return'] - result['max_drawdown']
                                        
                                        if score > best_score:
                                            best_score = score
                                            best_result = result.copy()
                                            best_result['params'] = {
                                                'macd_fast': macd_fast,
                                                'macd_slow': macd_slow,
                                                'macd_signal': macd_signal,
                                                'dc_period': dc_period,
                                                'rsi_threshold': rsi_threshold,
                                                'dc_multiplier': dc_multiplier,
                                                'stop_loss_pct': stop_loss_pct
                                            }
                                
                                    except Exception as e:
                                        continue
        
        return best_result
    
    def optimize_macd_short_parameters(self, optimization_data):
        """MACD 숏 파라미터 최적화"""
        print("MACD 숏 파라미터 최적화 중...")
        
        best_result = None
        best_score = -999999
        
        total_combinations = (len(self.macd_short_grid['macd_fast']) * 
                            len(self.macd_short_grid['macd_slow']) * 
                            len(self.macd_short_grid['macd_signal']) * 
                            len(self.macd_short_grid['dc_period']) *
                            len(self.macd_short_grid['rsi_threshold']) *
                            len(self.macd_short_grid['dc_multiplier']))
        
        combination_count = 0
        
        # 전체 데이터 사용
        sample_data = optimization_data
        
        for macd_fast in self.macd_short_grid['macd_fast']:
            for macd_slow in self.macd_short_grid['macd_slow']:
                if macd_fast >= macd_slow:
                    continue
                    
                for macd_signal in self.macd_short_grid['macd_signal']:
                    for dc_period in self.macd_short_grid['dc_period']:
                        for rsi_threshold in self.macd_short_grid['rsi_threshold']:
                            for dc_multiplier in self.macd_short_grid['dc_multiplier']:
                                combination_count += 1
                                
                                if combination_count % 50 == 0:
                                    print(f"MACD 숏 최적화 진행률: {combination_count}/{total_combinations}")
                                
                                try:
                                    # 지표 계산
                                    df = self.calculate_macd_indicators(
                                        sample_data, macd_fast, macd_slow, macd_signal, dc_period
                                    )
                                    # 숏 전용 신호 생성
                                    df = self.generate_macd_short_signals(df, rsi_threshold, dc_multiplier)
                                    
                                    # 백테스트 실행
                                    result = self.run_backtest(df)
                                    
                                    # 점수 계산 (수익률 - 최대낙폭)
                                    score = result['total_return'] - result['max_drawdown']
                                    
                                    if score > best_score:
                                        best_score = score
                                        best_result = result.copy()
                                        best_result['params'] = {
                                            'macd_fast': macd_fast,
                                            'macd_slow': macd_slow,
                                            'macd_signal': macd_signal,
                                            'dc_period': dc_period,
                                            'rsi_threshold': rsi_threshold,
                                            'dc_multiplier': dc_multiplier
                                        }
                                
                                except Exception as e:
                                    continue
        
        return best_result
    
    def optimize_ma_parameters(self, optimization_data):
        """MA 파라미터 최적화 (최고 성적일 때만 표시)"""
        print("MA + DCC 파라미터 최적화 중...")
        
        best_result = None
        best_score = -999999
        
        total_combinations = (len(self.ma_grid['sma_short']) * 
                            len(self.ma_grid['sma_long']) * 
                            len(self.ma_grid['dc_period']))
        
        combination_count = 0
        
        # 전체 데이터 사용
        sample_data = optimization_data
        
        for sma_short in self.ma_grid['sma_short']:
            for sma_long in self.ma_grid['sma_long']:
                if sma_short >= sma_long:
                    continue
                    
                for dc_period in self.ma_grid['dc_period']:
                    combination_count += 1
                    
                    try:
                        # 지표 계산
                        df = self.calculate_ma_indicators(
                            sample_data, sma_short, sma_long, dc_period
                        )
                        df = self.generate_ma_signals(df)
                        
                        # 백테스트 실행
                        result = self.run_backtest(df)
                        
                        # 점수 계산 (수익률 - 최대낙폭)
                        score = result['total_return'] - result['max_drawdown']
                        
                        if score > best_score:
                            best_score = score
                            best_result = result.copy()
                            best_result['params'] = {
                                'sma_short': sma_short,
                                'sma_long': sma_long,
                                'dc_period': dc_period
                            }
                            
                            # 최고 성적일 때만 표시
                            print(f"새로운 최고 점수: {score:.2f} (수익률: {result['total_return']:.2f}%, MDD: {result['max_drawdown']:.2f}%)")
                            
                    except Exception as e:
                        continue
        
        return best_result
    
    def optimize_bb_parameters(self, optimization_data):
        """BB 파라미터 최적화 (조기 종료 포함)"""
        print("BB + DC 파라미터 최적화 중...")
        
        best_result = None
        best_score = -999999
        
        total_combinations = (len(self.bb_grid['bb_period']) * 
                            len(self.bb_grid['bb_std']) * 
                            len(self.bb_grid['dc_period']))
        
        combination_count = 0
        
        # 전체 데이터 사용
        sample_data = optimization_data
        
        for bb_period in self.bb_grid['bb_period']:
            for bb_std in self.bb_grid['bb_std']:
                for dc_period in self.bb_grid['dc_period']:
                    combination_count += 1
                    
                    if combination_count % 20 == 0:
                        print(f"BB 최적화 진행률: {combination_count}/{total_combinations}")
                    
                    try:
                        # 지표 계산 (샘플링된 데이터 사용)
                        df = self.calculate_bb_indicators(
                            sample_data, bb_period, bb_std, dc_period
                        )
                        df = self.generate_bb_signals(df)
                        
                        # 백테스트 실행
                        result = self.run_backtest(df)
                        
                        # 점수 계산 (수익률 - 최대낙폭)
                        score = result['total_return'] - result['max_drawdown']
                        
                        if score > best_score:
                            best_score = score
                            best_result = result.copy()
                            best_result['params'] = {
                                'bb_period': bb_period,
                                'bb_std': bb_std,
                                'dc_period': dc_period
                            }
                            
                    except Exception as e:
                        continue
        
        return best_result
    
    def run_wfo_backtest(self):
        """WFO 백테스트 실행"""
        print("=== Walk-Forward Optimization 백테스트 시작 ===")
        
        if not self.load_all_data():
            return None
        
        wfo_results = []
        
        for i, schedule in enumerate(self.wfo_schedule):
            print(f"\n--- {schedule['period']} ---")
            
            # 최적화 데이터 로드
            opt_data = self.get_data_period(schedule['optimization_start'], schedule['optimization_end'])
            print(f"최적화 기간: {schedule['optimization_start']} ~ {schedule['optimization_end']} ({len(opt_data)}개 캔들)")
            
            # 테스트 데이터 로드
            test_data = self.get_data_period(schedule['test_start'], schedule['test_end'])
            print(f"테스트 기간: {schedule['test_start']} ~ {schedule['test_end']} ({len(test_data)}개 캔들)")
            
            if len(opt_data) == 0 or len(test_data) == 0:
                print("데이터가 없어 건너뜁니다.")
                continue
            
            # MA 파라미터 최적화
            ma_optimal = self.optimize_ma_parameters(opt_data)
            
            # 최적화된 파라미터로 테스트 (None인 경우 기본값 사용)
            if not ma_optimal:
                print("MA 최적화 실패, 기본 파라미터 사용")
                ma_optimal = {'params': {'sma_short': 5, 'sma_long': 40, 'dc_period': 25}}
            
            # MA 전략 테스트
            ma_test_data = self.calculate_ma_indicators(
                test_data,
                ma_optimal['params']['sma_short'],
                ma_optimal['params']['sma_long'],
                ma_optimal['params']['dc_period']
            )
            ma_test_data = self.generate_ma_signals(ma_test_data)
            ma_test_result = self.run_backtest(ma_test_data)
            
            # 결과 저장
            period_result = {
                'period': schedule['period'],
                'optimization_period': f"{schedule['optimization_start']} ~ {schedule['optimization_end']}",
                'test_period': f"{schedule['test_start']} ~ {schedule['test_end']}",
                'ma_optimal_params': ma_optimal['params'],
                'ma_test_result': ma_test_result
            }
            
            wfo_results.append(period_result)
            
            print(f"MA 최적 파라미터: {ma_optimal['params']}")
            print(f"MA 테스트 결과: 수익률 {ma_test_result['total_return']:.2f}%, 승률 {ma_test_result['win_rate']:.2f}%, MDD {ma_test_result['max_drawdown']:.2f}%, 거래횟수 {ma_test_result['total_trades']}회")
        
        return wfo_results
    
    def save_results(self, results):
        """결과 저장"""
        output = {
            'wfo_type': 'Walk-Forward Optimization (MA + DC)',
            'timeframe': '10분봉',
            'optimization_period': '2년',
            'test_period': '6개월',
            'strategies': ['MA + DC'],
            'results': results,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open('wfo_backtest_results.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n결과가 wfo_backtest_results.json에 저장되었습니다.")

def main():
    """메인 실행 함수"""
    print("=== Walk-Forward Optimization 백테스트 시스템 ===")
    
    # WFO 시스템 초기화
    wfo = WFOBacktest()
    
    # WFO 백테스트 실행
    results = wfo.run_wfo_backtest()
    
    if results:
        # 결과 저장
        wfo.save_results(results)
        
        # 최종 요약 (MA 전략)
        print("\n=== WFO 백테스트 최종 요약 (MA + DC) ===")
        for result in results:
            print(f"\n{result['period']}:")
            print(f"  MA + DC: {result['ma_test_result']['total_return']:.2f}% (승률 {result['ma_test_result']['win_rate']:.2f}%, MDD {result['ma_test_result']['max_drawdown']:.2f}%, 거래 {result['ma_test_result']['total_trades']}회)")
            print(f"  최적 파라미터: {result['ma_optimal_params']}")
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
