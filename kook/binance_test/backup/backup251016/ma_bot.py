"""
MA + DCC(던키안 채널) 최적화 및 백테스트 시스템

=== 주요 기능 ===
1. 이동평균(MA) 전략
   - 단기/장기 이동평균 교차 신호
   - RSI 과매수/과매도 필터
   - 볼륨 필터링

2. 던키안 채널(DCC) 전략
   - 변동성 기반 채널 지표
   - 상단/하단 돌파 신호
   - 채널 내 위치 기반 매매

3. 결합 전략
   - MA + DCC 동시 신호 확인
   - 더 정확한 진입/청산 타이밍
   - 리스크 감소 효과

=== 던키안 채널(DCC) 인디케이터 ===
던키안 채널은 가격의 변동성을 측정하는 채널 지표입니다.

계산 방법:
- 상단선: 최근 N일간의 최고가
- 하단선: 최근 N일간의 최저가  
- 중간선: (상단선 + 하단선) / 2
- 채널 폭: 상단선 - 하단선
- 가격 위치: (현재가 - 하단선) / (상단선 - 하단선)

매매 신호:
- 매수: 상단 돌파 또는 중간선 위 + 상단 70% 이상
- 매도: 하단 이탈 또는 중간선 아래 + 하단 30% 이하

=== 백테스트 시스템 ===
- 3년치 데이터로 최적 파라미터 탐색 (2021-2023)
- 마지막 1년치로 백테스트 실행 (2024)
- 롱/숏 분리 최적화
- 양방향 매매 지원
- 실시간 성과 추적

=== 사용 가능한 전략 ===
1. MA 전용: 기존 이동평균 전략
2. DCC 전용: 던키안 채널 전용 전략  
3. 결합 전략: MA + DCC 동시 사용 (권장)

=== 설정 파일 ===
- ma_bot.json: 전략 파라미터 설정
- optimal_params: 최적화된 파라미터 저장
- use_saved_params: 저장된 파라미터 사용 여부
"""

import pandas as pd
import numpy as np
import itertools
from datetime import datetime, timedelta
import warnings
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
warnings.filterwarnings('ignore')

# 한글 폰트 설정
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

class MABot:
    def __init__(self, symbol='BTCUSDT', start_date='2021-01-01', end_date='2024-12-31'):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.data = None
        self.optimization_results = []
        self.config = self.load_config()
    
    def load_config(self):
        """설정 파일 로드"""
        import json
        import os
        
        config_file = "ma_bot.json"
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                print(f"설정 파일 로드 완료: {config_file}")
                return config
            else:
                print(f"설정 파일이 없습니다: {config_file}")
                return self.get_default_config()
        except Exception as e:
            print(f"설정 파일 로드 실패: {e}")
            return self.get_default_config()
    
    def get_default_config(self):
        """기본 설정 반환"""
        return {
            "use_saved_params": False,
            "optimize_params": True,
            "data_settings": {
                "timeframe": "5m",
                "resample_to": "4H",
                "start_date": "2021-01-01",
                "end_date": "2024-12-31"
            },
            "leverage_settings": {
                "use_leverage": True,
                "leverage_ratio": 2.0,
                "max_leverage": 5.0
            },
            "strategy_settings": {
                "use_volume_filter": True,
                "volume_threshold_range": [0.5, 0.8, 1.0, 1.2, 1.5, 2.0],
                "sma_short_range": [5, 8, 11, 14, 17, 20],
                "sma_long_range": [20, 30, 40, 50, 60, 70, 80],
                "rsi_overbought": 70,
                "rsi_oversold": 30,
                "rsi_strong_overbought": 80,
                "rsi_strong_oversold": 20
            },
            "risk_settings": {
                "initial_capital": 10000,
                "position_size_ratio": 0.475,
                "stop_loss_ratio": 0.05,
                "use_rapid_decline_stop": True
            },
            "backtest_settings": {
                "train_period": "2021-2023",
                "test_period": "2024",
                "save_results": True,
                "generate_plots": True
            }
        }
        
    def load_data(self):
        """로컬 CSV 데이터 로딩"""
        print(f"데이터 로딩 중... ({self.start_date} ~ {self.end_date})")
        
        try:
            import glob
            
            # 데이터 폴더 경로
            data_folder = "data/BTCUSDT/5m"
            csv_files = glob.glob(f"{data_folder}/BTCUSDT_5m_*.csv")
            csv_files.sort()
            
            all_data = []
            
            for file_path in csv_files:
                # 파일명에서 연도 추출
                year = file_path.split('_')[-1].split('.')[0]
                
                # 요청된 기간에 해당하는 파일만 로드
                if int(year) >= int(self.start_date[:4]) and int(year) <= int(self.end_date[:4]):
                    print(f"로딩 중: {file_path}")
                    df_year = pd.read_csv(file_path)
                    print(f"Columns in {file_path}: {df_year.columns.tolist()}")
                    
                    # 컬럼명 통일 (timestamp 또는 datetime)
                    if 'timestamp' in df_year.columns:
                        time_col = 'timestamp'
                    elif 'datetime' in df_year.columns:
                        time_col = 'datetime'
                    else:
                        print(f"시간 컬럼을 찾을 수 없습니다: {df_year.columns.tolist()}")
                        continue
                    
                    df_year[time_col] = pd.to_datetime(df_year[time_col])
                    df_year.set_index(time_col, inplace=True)
                    all_data.append(df_year)
            
            if not all_data:
                print("해당 기간의 데이터 파일을 찾을 수 없습니다.")
                return False
            
            # 모든 연도 데이터 합치기
            self.data = pd.concat(all_data, ignore_index=False)
            self.data.sort_index(inplace=True)
            
            # 요청된 기간으로 필터링
            start_dt = pd.to_datetime(self.start_date)
            end_dt = pd.to_datetime(self.end_date)
            self.data = self.data[(self.data.index >= start_dt) & (self.data.index <= end_dt)]
            
            # 5분봉을 설정된 시간봉으로 리샘플링
            resample_to = self.config.get('data_settings', {}).get('resample_to', '4H')
            print(f"리샘플링 중: 5분봉 → {resample_to}봉")
            
            self.data = self.data.resample(resample_to).agg({
                'open': 'first',
                'high': 'max', 
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            print(f"데이터 로딩 완료: {len(self.data)}개 캔들 ({resample_to}봉)")
            return True
            
        except Exception as e:
            print(f"데이터 로딩 실패: {e}")
            return False
    
    def calculate_indicators(self, sma_short, sma_long):
        """지표 계산"""
        # SMA 지표들
        self.data['sma_short'] = self.data['close'].rolling(window=sma_short).mean()
        self.data['sma_long'] = self.data['close'].rolling(window=sma_long).mean()
        
        # RSI
        delta = self.data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        self.data['rsi'] = 100 - (100 / (1 + rs))
        
        # ATR
        high_low = self.data['high'] - self.data['low']
        high_close = np.abs(self.data['high'] - self.data['close'].shift())
        low_close = np.abs(self.data['low'] - self.data['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        self.data['atr'] = true_range.rolling(14).mean()
    
    def calculate_dunkeyan_channel(self, period=20):
        """던키안 채널 인디케이터 계산"""
        # 던키안 채널 계산
        self.data['dcc_upper'] = self.data['high'].rolling(window=period).max()
        self.data['dcc_lower'] = self.data['low'].rolling(window=period).min()
        self.data['dcc_middle'] = (self.data['dcc_upper'] + self.data['dcc_lower']) / 2
        
        # 채널 폭 계산
        self.data['dcc_width'] = self.data['dcc_upper'] - self.data['dcc_lower']
        
        # 가격의 채널 내 위치 (0~1, 0=하단, 1=상단)
        self.data['dcc_position'] = (self.data['close'] - self.data['dcc_lower']) / (self.data['dcc_upper'] - self.data['dcc_lower'])
        
        # 채널 돌파 여부
        self.data['dcc_breakout_up'] = self.data['close'] > self.data['dcc_upper'].shift(1)
        self.data['dcc_breakout_down'] = self.data['close'] < self.data['dcc_lower'].shift(1)
        
        return self.data[['dcc_upper', 'dcc_lower', 'dcc_middle', 'dcc_width', 'dcc_position', 'dcc_breakout_up', 'dcc_breakout_down']]
    
    def apply_leverage(self, pnl, leverage_ratio=1.0):
        """레버리지 적용"""
        return pnl * leverage_ratio
    
    def calculate_position_size_with_leverage(self, capital, price, leverage_ratio=1.0):
        """레버리지를 적용한 포지션 크기 계산"""
        if leverage_ratio > 1.0:
            # 레버리지 적용: 더 큰 포지션 크기, 하지만 실제 사용 자본은 적음
            available_capital = capital * leverage_ratio
            position_size = available_capital / price
            actual_capital_used = capital  # 실제로는 원래 자본만 사용
            return position_size, actual_capital_used
        else:
            # 레버리지 없음
            available_capital = capital
            position_size = available_capital / price
            return position_size, available_capital
    
    def get_leverage_settings(self):
        """레버리지 설정 가져오기"""
        leverage_settings = self.config.get('leverage_settings', {})
        return {
            'use_leverage': leverage_settings.get('use_leverage', False),
            'leverage_ratio': leverage_settings.get('leverage_ratio', 1.0),
            'max_leverage': leverage_settings.get('max_leverage', 5.0)
        }
    
    def calculate_trade_statistics(self, trades):
        """거래 통계 계산 (손절, 익절, 급락 손절 포함)"""
        if not trades:
            return {
                'stop_loss_count': 0,
                'take_profit_count': 0,
                'stop_loss_rate': 0.0,
                'take_profit_rate': 0.0,
                'avg_loss': 0.0,
                'avg_profit': 0.0,
                'crash_stop_count': 0,
                'crash_stop_rate': 0.0,
                'normal_stop_count': 0,
                'normal_stop_rate': 0.0
            }
        
        stop_loss_count = 0
        take_profit_count = 0
        crash_stop_count = 0  # 급락 손절
        normal_stop_count = 0  # 일반 손절
        total_loss = 0
        total_profit = 0
        crash_loss = 0
        normal_loss = 0
        
        for trade in trades:
            if 'pnl' in trade and trade['pnl'] is not None:
                pnl = trade['pnl']
                if pnl < 0:  # 손실
                    stop_loss_count += 1
                    total_loss += pnl
                    
                    # 급락 손절 판단 (1시간 기준 -5% 이상 하락)
                    if 'entry_price' in trade and 'exit_price' in trade:
                        price_change = (trade['exit_price'] - trade['entry_price']) / trade['entry_price']
                        if price_change <= -0.05:  # -5% 이상 하락
                            crash_stop_count += 1
                            crash_loss += pnl
                        else:
                            normal_stop_count += 1
                            normal_loss += pnl
                    else:
                        # 가격 정보가 없으면 일반 손절로 분류
                        normal_stop_count += 1
                        normal_loss += pnl
                        
                elif pnl > 0:  # 수익
                    take_profit_count += 1
                    total_profit += pnl
        
        total_trades = len(trades)
        stop_loss_rate = (stop_loss_count / total_trades * 100) if total_trades > 0 else 0
        take_profit_rate = (take_profit_count / total_trades * 100) if total_trades > 0 else 0
        crash_stop_rate = (crash_stop_count / total_trades * 100) if total_trades > 0 else 0
        normal_stop_rate = (normal_stop_count / total_trades * 100) if total_trades > 0 else 0
        
        avg_loss = (total_loss / stop_loss_count) if stop_loss_count > 0 else 0
        avg_profit = (total_profit / take_profit_count) if take_profit_count > 0 else 0
        avg_crash_loss = (crash_loss / crash_stop_count) if crash_stop_count > 0 else 0
        avg_normal_loss = (normal_loss / normal_stop_count) if normal_stop_count > 0 else 0
        
        return {
            'stop_loss_count': stop_loss_count,
            'take_profit_count': take_profit_count,
            'stop_loss_rate': stop_loss_rate,
            'take_profit_rate': take_profit_rate,
            'avg_loss': avg_loss,
            'avg_profit': avg_profit,
            'crash_stop_count': crash_stop_count,
            'crash_stop_rate': crash_stop_rate,
            'normal_stop_count': normal_stop_count,
            'normal_stop_rate': normal_stop_rate,
            'avg_crash_loss': avg_crash_loss,
            'avg_normal_loss': avg_normal_loss
        }
    
    def generate_dcc_signals(self, dcc_period=20, breakout_threshold=0.02):
        """던키안 채널 기반 매매 신호 생성"""
        # 던키안 채널 계산
        self.calculate_dunkeyan_channel(dcc_period)
        
        price = self.data['close']
        dcc_upper = self.data['dcc_upper']
        dcc_lower = self.data['dcc_lower']
        dcc_middle = self.data['dcc_middle']
        dcc_position = self.data['dcc_position']
        dcc_breakout_up = self.data['dcc_breakout_up']
        dcc_breakout_down = self.data['dcc_breakout_down']
        
        # 던키안 채널 매수 조건
        dcc_buy_condition = (
            (dcc_breakout_up) |  # 상단 돌파
            ((price > dcc_middle) & (dcc_position > 0.7))  # 중간선 위 + 상단 70% 이상
        )
        
        # 던키안 채널 매도 조건
        dcc_sell_condition = (
            (dcc_breakout_down) |  # 하단 이탈
            ((price < dcc_middle) & (dcc_position < 0.3))  # 중간선 아래 + 하단 30% 이하
        )
        
        # 신호 생성
        signals = pd.Series(0, index=self.data.index)
        signals[dcc_buy_condition] = 1
        signals[dcc_sell_condition] = -1
        
        # 연속된 신호 제거 (변화점만 유지)
        signal_changes = signals.diff() != 0
        signal_changes.iloc[0] = True
        
        # 변화점이 아닌 곳은 0으로 설정
        signals[~signal_changes] = 0
        
        # 이전 신호 유지
        signals = signals.replace(0, method='ffill').fillna(0)
        
        return signals
    
    def generate_combined_signals(self, sma_short, sma_long, dcc_period=20, use_dcc=True):
        """이동평균 + 던키안 채널 결합 신호 생성"""
        # 기본 이동평균 신호
        price = self.data['close']
        sma_short_series = self.data['sma_short']
        sma_long_series = self.data['sma_long']
        rsi = self.data['rsi']
        
        # 이동평균 매수 조건
        ma_buy_condition = (
            (price > sma_long_series) &
            (sma_short_series > sma_long_series) &
            (rsi < 70)
        )
        
        # 이동평균 매도 조건
        ma_sell_condition = (
            (price < sma_long_series) |
            (sma_short_series < sma_long_series) |
            (rsi > 80)
        )
        
        if use_dcc:
            # 던키안 채널 신호
            dcc_signals = self.generate_dcc_signals(dcc_period)
            
            # 결합 신호 (둘 다 매수/매도일 때만 신호 생성)
            combined_signals = pd.Series(0, index=self.data.index)
            
            # 매수: MA 매수 + DCC 매수
            combined_buy = ma_buy_condition & (dcc_signals == 1)
            combined_signals[combined_buy] = 1
            
            # 매도: MA 매도 또는 DCC 매도
            combined_sell = ma_sell_condition | (dcc_signals == -1)
            combined_signals[combined_sell] = -1
            
            # 신호 정리
            signal_changes = combined_signals.diff() != 0
            signal_changes.iloc[0] = True
            combined_signals[~signal_changes] = 0
            combined_signals = combined_signals.replace(0, method='ffill').fillna(0)
            
            return combined_signals
        else:
            # 기존 이동평균만 사용
            signals = pd.Series(0, index=self.data.index)
            signals[ma_buy_condition] = 1
            signals[ma_sell_condition] = -1
            
            signal_changes = signals.diff() != 0
            signal_changes.iloc[0] = True
            signals[~signal_changes] = 0
            signals = signals.replace(0, method='ffill').fillna(0)
            
            return signals
    
    def generate_signals(self, sma_short, sma_long):
        """매매 신호 생성"""
        price = self.data['close']
        sma_short_series = self.data['sma_short']
        sma_long_series = self.data['sma_long']
        rsi = self.data['rsi']
        
        # 매수 조건 (벡터화)
        buy_condition = (
            (price > sma_long_series) &  # 가격이 장기선 위
            (sma_short_series > sma_long_series) &  # 단기선이 장기선 위
            (rsi < 70)  # RSI 과매수 아님
        )
        
        # 매도 조건 (벡터화)
        sell_condition = (
            (price < sma_long_series) |  # 가격이 장기선 아래
            (sma_short_series < sma_long_series) |  # 단기선이 장기선 아래
            (rsi > 80)  # RSI 과매수
        )
        
        # 신호 생성 (벡터화)
        signals = pd.Series(0, index=self.data.index)
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        
        # 연속된 신호 제거 (변화점만 유지)
        signal_changes = signals.diff() != 0
        signal_changes.iloc[0] = True  # 첫 번째는 항상 변화
        
        # 변화점이 아닌 곳은 0으로 설정
        signals[~signal_changes] = 0
        
        # 이전 신호 유지 (벡터화)
        signals = signals.replace(0, method='ffill').fillna(0)
        
        return signals
    
    def run_backtest(self, sma_short, sma_long, start_idx, end_idx):
        """백테스트 실행"""
        # 데이터 슬라이싱
        test_data = self.data.iloc[start_idx:end_idx].copy()
        
        # 지표 계산
        test_data['sma_short'] = test_data['close'].rolling(window=sma_short).mean()
        test_data['sma_long'] = test_data['close'].rolling(window=sma_long).mean()
        
        # RSI 계산
        delta = test_data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        test_data['rsi'] = 100 - (100 / (1 + rs))
        
        # 신호 생성
        price = test_data['close']
        sma_short_series = test_data['sma_short']
        sma_long_series = test_data['sma_long']
        rsi = test_data['rsi']
        
        buy_condition = (
            (price > sma_long_series) &
            (sma_short_series > sma_long_series) &
            (rsi < 70)
        )
        
        sell_condition = (
            (price < sma_long_series) |
            (sma_short_series < sma_long_series) |
            (rsi > 80)
        )
        
        signals = pd.Series(0, index=test_data.index)
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        
        # 신호 정리
        signal_changes = signals.diff() != 0
        signal_changes.iloc[0] = True
        signals[~signal_changes] = 0
        signals = signals.replace(0, method='ffill').fillna(0)
        
        # 백테스트 실행
        initial_capital = 10000
        capital = initial_capital
        position_size = 0
        entry_price = 0
        trades = []
        
        # 신호 변화점 찾기
        buy_signals = (signals == 1) & signal_changes
        sell_signals = (signals == -1) & signal_changes
        
        buy_indices = test_data[buy_signals].index
        sell_indices = test_data[sell_signals].index
        
        # 모든 이벤트를 시간순으로 정렬
        all_events = []
        for idx in buy_indices:
            all_events.append((idx, 'buy', test_data.loc[idx, 'close']))
        for idx in sell_indices:
            all_events.append((idx, 'sell', test_data.loc[idx, 'close']))
        
        all_events.sort(key=lambda x: x[0])
        
        for timestamp, action, price in all_events:
            if action == 'buy' and position_size == 0:
                # 매수
                available_capital = capital * 0.95
                position_size = available_capital / price
                entry_price = price
                capital -= available_capital
                
            elif action == 'sell' and position_size > 0:
                # 매도
                pnl = (price - entry_price) * position_size
                capital += position_size * price
                
                trades.append({
                    'entry_price': entry_price,
                    'exit_price': price,
                    'pnl': pnl
                })
                
                position_size = 0
                entry_price = 0
        
        # 최종 포지션 청산
        if position_size > 0:
            final_price = test_data['close'].iloc[-1]
            pnl = (final_price - entry_price) * position_size
            capital += position_size * final_price
            
            trades.append({
                'entry_price': entry_price,
                'exit_price': final_price,
                'pnl': pnl
            })
        
        # 성과 계산
        total_return = (capital - initial_capital) / initial_capital * 100
        
        if trades:
            trades_df = pd.DataFrame(trades)
            winning_trades = trades_df[trades_df['pnl'] > 0]
            win_rate = len(winning_trades) / len(trades_df) * 100
            
            # 최대 낙폭 계산
            pnl_values = trades_df['pnl'].values
            cumulative_pnl = np.cumsum(pnl_values)
            capital_history = initial_capital + cumulative_pnl
            
            peak = np.maximum.accumulate(capital_history)
            drawdown = (peak - capital_history) / peak * 100
            max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
        else:
            win_rate = 0
            max_dd = 0
        
        return {
            'sma_short': sma_short,
            'sma_long': sma_long,
            'total_return': total_return,
            'win_rate': win_rate,
            'max_drawdown': max_dd,
            'total_trades': len(trades),
            'final_capital': capital
        }
    
    def run_dcc_backtest(self, dcc_period=20, start_idx=0, end_idx=None):
        """던키안 채널 전용 백테스트"""
        if end_idx is None:
            end_idx = len(self.data)
            
        # 데이터 슬라이싱
        test_data = self.data.iloc[start_idx:end_idx].copy()
        
        # 던키안 채널 계산
        test_data['dcc_upper'] = test_data['high'].rolling(window=dcc_period).max()
        test_data['dcc_lower'] = test_data['low'].rolling(window=dcc_period).min()
        test_data['dcc_middle'] = (test_data['dcc_upper'] + test_data['dcc_lower']) / 2
        test_data['dcc_position'] = (test_data['close'] - test_data['dcc_lower']) / (test_data['dcc_upper'] - test_data['dcc_lower'])
        
        # 던키안 채널 신호 생성
        price = test_data['close']
        dcc_upper = test_data['dcc_upper']
        dcc_lower = test_data['dcc_lower']
        dcc_middle = test_data['dcc_middle']
        dcc_position = test_data['dcc_position']
        
        # 매수 조건: 상단 돌파 또는 중간선 위 + 상단 70% 이상
        buy_condition = (
            (price > dcc_upper.shift(1)) |  # 상단 돌파
            ((price > dcc_middle) & (dcc_position > 0.7))  # 중간선 위 + 상단 70% 이상
        )
        
        # 매도 조건: 하단 이탈 또는 중간선 아래 + 하단 30% 이하
        sell_condition = (
            (price < dcc_lower.shift(1)) |  # 하단 이탈
            ((price < dcc_middle) & (dcc_position < 0.3))  # 중간선 아래 + 하단 30% 이하
        )
        
        signals = pd.Series(0, index=test_data.index)
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        
        # 신호 정리
        signal_changes = signals.diff() != 0
        signal_changes.iloc[0] = True
        signals[~signal_changes] = 0
        signals = signals.replace(0, method='ffill').fillna(0)
        
        # 백테스트 실행
        initial_capital = 10000
        capital = initial_capital
        position_size = 0
        entry_price = 0
        trades = []
        
        # 신호 변화점 찾기
        buy_signals = (signals == 1) & signal_changes
        sell_signals = (signals == -1) & signal_changes
        
        buy_indices = test_data[buy_signals].index
        sell_indices = test_data[sell_signals].index
        
        # 모든 이벤트를 시간순으로 정렬
        all_events = []
        for idx in buy_indices:
            all_events.append((idx, 'buy', test_data.loc[idx, 'close']))
        for idx in sell_indices:
            all_events.append((idx, 'sell', test_data.loc[idx, 'close']))
        
        all_events.sort(key=lambda x: x[0])
        
        for timestamp, action, price in all_events:
            if action == 'buy' and position_size == 0:
                # 매수
                available_capital = capital * 0.95
                position_size = available_capital / price
                entry_price = price
                capital -= available_capital
                
            elif action == 'sell' and position_size > 0:
                # 매도
                pnl = (price - entry_price) * position_size
                capital += position_size * price
                
                trades.append({
                    'entry_price': entry_price,
                    'exit_price': price,
                    'pnl': pnl
                })
                
                position_size = 0
                entry_price = 0
        
        # 최종 포지션 청산
        if position_size > 0:
            final_price = test_data['close'].iloc[-1]
            pnl = (final_price - entry_price) * position_size
            capital += position_size * final_price
            
            trades.append({
                'entry_price': entry_price,
                'exit_price': final_price,
                'pnl': pnl
            })
        
        # 성과 계산
        total_return = (capital - initial_capital) / initial_capital * 100
        
        if trades:
            trades_df = pd.DataFrame(trades)
            winning_trades = trades_df[trades_df['pnl'] > 0]
            win_rate = len(winning_trades) / len(trades_df) * 100
            
            # 최대 낙폭 계산
            pnl_values = trades_df['pnl'].values
            cumulative_pnl = np.cumsum(pnl_values)
            capital_history = initial_capital + cumulative_pnl
            
            peak = np.maximum.accumulate(capital_history)
            drawdown = (peak - capital_history) / peak * 100
            max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
        else:
            win_rate = 0
            max_dd = 0
        
        return {
            'dcc_period': dcc_period,
            'total_return': total_return,
            'win_rate': win_rate,
            'max_drawdown': max_dd,
            'total_trades': len(trades),
            'final_capital': capital
        }
    
    def run_combined_backtest(self, sma_short, sma_long, dcc_period=20, start_idx=0, end_idx=None):
        """이동평균 + 던키안 채널 결합 백테스트"""
        if end_idx is None:
            end_idx = len(self.data)
            
        # 데이터 슬라이싱
        test_data = self.data.iloc[start_idx:end_idx].copy()
        
        # 지표 계산
        test_data['sma_short'] = test_data['close'].rolling(window=sma_short).mean()
        test_data['sma_long'] = test_data['close'].rolling(window=sma_long).mean()
        
        # RSI 계산
        delta = test_data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        test_data['rsi'] = 100 - (100 / (1 + rs))
        
        # 던키안 채널 계산
        test_data['dcc_upper'] = test_data['high'].rolling(window=dcc_period).max()
        test_data['dcc_lower'] = test_data['low'].rolling(window=dcc_period).min()
        test_data['dcc_middle'] = (test_data['dcc_upper'] + test_data['dcc_lower']) / 2
        test_data['dcc_position'] = (test_data['close'] - test_data['dcc_lower']) / (test_data['dcc_upper'] - test_data['dcc_lower'])
        
        # 결합 신호 생성
        price = test_data['close']
        sma_short_series = test_data['sma_short']
        sma_long_series = test_data['sma_long']
        rsi = test_data['rsi']
        dcc_upper = test_data['dcc_upper']
        dcc_lower = test_data['dcc_lower']
        dcc_middle = test_data['dcc_middle']
        dcc_position = test_data['dcc_position']
        
        # 이동평균 조건
        ma_buy_condition = (
            (price > sma_long_series) &
            (sma_short_series > sma_long_series) &
            (rsi < 70)
        )
        
        ma_sell_condition = (
            (price < sma_long_series) |
            (sma_short_series < sma_long_series) |
            (rsi > 80)
        )
        
        # 던키안 채널 조건
        dcc_buy_condition = (
            (price > dcc_upper.shift(1)) |  # 상단 돌파
            ((price > dcc_middle) & (dcc_position > 0.7))  # 중간선 위 + 상단 70% 이상
        )
        
        dcc_sell_condition = (
            (price < dcc_lower.shift(1)) |  # 하단 이탈
            ((price < dcc_middle) & (dcc_position < 0.3))  # 중간선 아래 + 하단 30% 이하
        )
        
        # 결합 신호 (둘 다 매수일 때만 매수, 하나라도 매도일 때 매도)
        combined_buy = ma_buy_condition & dcc_buy_condition
        combined_sell = ma_sell_condition | dcc_sell_condition
        
        signals = pd.Series(0, index=test_data.index)
        signals[combined_buy] = 1
        signals[combined_sell] = -1
        
        # 신호 정리
        signal_changes = signals.diff() != 0
        signal_changes.iloc[0] = True
        signals[~signal_changes] = 0
        signals = signals.replace(0, method='ffill').fillna(0)
        
        # 백테스트 실행
        initial_capital = 10000
        capital = initial_capital
        position_size = 0
        entry_price = 0
        trades = []
        
        # 신호 변화점 찾기
        buy_signals = (signals == 1) & signal_changes
        sell_signals = (signals == -1) & signal_changes
        
        buy_indices = test_data[buy_signals].index
        sell_indices = test_data[sell_signals].index
        
        # 모든 이벤트를 시간순으로 정렬
        all_events = []
        for idx in buy_indices:
            all_events.append((idx, 'buy', test_data.loc[idx, 'close']))
        for idx in sell_indices:
            all_events.append((idx, 'sell', test_data.loc[idx, 'close']))
        
        all_events.sort(key=lambda x: x[0])
        
        for timestamp, action, price in all_events:
            if action == 'buy' and position_size == 0:
                # 매수
                available_capital = capital * 0.95
                position_size = available_capital / price
                entry_price = price
                capital -= available_capital
                
            elif action == 'sell' and position_size > 0:
                # 매도
                pnl = (price - entry_price) * position_size
                capital += position_size * price
                
                trades.append({
                    'entry_price': entry_price,
                    'exit_price': price,
                    'pnl': pnl
                })
                
                position_size = 0
                entry_price = 0
        
        # 최종 포지션 청산
        if position_size > 0:
            final_price = test_data['close'].iloc[-1]
            pnl = (final_price - entry_price) * position_size
            capital += position_size * final_price
            
            trades.append({
                'entry_price': entry_price,
                'exit_price': final_price,
                'pnl': pnl
            })
        
        # 성과 계산
        total_return = (capital - initial_capital) / initial_capital * 100
        
        if trades:
            trades_df = pd.DataFrame(trades)
            winning_trades = trades_df[trades_df['pnl'] > 0]
            win_rate = len(winning_trades) / len(trades_df) * 100
            
            # 최대 낙폭 계산
            pnl_values = trades_df['pnl'].values
            cumulative_pnl = np.cumsum(pnl_values)
            capital_history = initial_capital + cumulative_pnl
            
            peak = np.maximum.accumulate(capital_history)
            drawdown = (peak - capital_history) / peak * 100
            max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
        else:
            win_rate = 0
            max_dd = 0
        
        return {
            'sma_short': sma_short,
            'sma_long': sma_long,
            'dcc_period': dcc_period,
            'total_return': total_return,
            'win_rate': win_rate,
            'max_drawdown': max_dd,
            'total_trades': len(trades),
            'final_capital': capital
        }
    
    def run_combined_longshort_backtest(self, long_sma_short, long_sma_long, short_sma_short, short_sma_long, dcc_period=20, start_idx=0, end_idx=None, leverage_ratio=1.0):
        """이동평균 + 던키안 채널 결합 양방향 백테스트"""
        if end_idx is None:
            end_idx = len(self.data)
            
        # 데이터 슬라이싱
        test_data = self.data.iloc[start_idx:end_idx].copy()
        
        # 롱용 지표 계산
        test_data['long_sma_short'] = test_data['close'].rolling(window=long_sma_short).mean()
        test_data['long_sma_long'] = test_data['close'].rolling(window=long_sma_long).mean()
        
        # 숏용 지표 계산
        test_data['short_sma_short'] = test_data['close'].rolling(window=short_sma_short).mean()
        test_data['short_sma_long'] = test_data['close'].rolling(window=short_sma_long).mean()
        
        # RSI 계산
        delta = test_data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        test_data['rsi'] = 100 - (100 / (1 + rs))
        
        # 던키안 채널 계산
        test_data['dcc_upper'] = test_data['high'].rolling(window=dcc_period).max()
        test_data['dcc_lower'] = test_data['low'].rolling(window=dcc_period).min()
        test_data['dcc_middle'] = (test_data['dcc_upper'] + test_data['dcc_lower']) / 2
        test_data['dcc_position'] = (test_data['close'] - test_data['dcc_lower']) / (test_data['dcc_upper'] - test_data['dcc_lower'])
        
        # 결합 신호 생성
        price = test_data['close']
        long_sma_short_series = test_data['long_sma_short']
        long_sma_long_series = test_data['long_sma_long']
        short_sma_short_series = test_data['short_sma_short']
        short_sma_long_series = test_data['short_sma_long']
        rsi = test_data['rsi']
        dcc_upper = test_data['dcc_upper']
        dcc_lower = test_data['dcc_lower']
        dcc_middle = test_data['dcc_middle']
        dcc_position = test_data['dcc_position']
        
        # 롱 매수 조건 (MA + DCC 결합)
        long_buy_condition = (
            (price > long_sma_long_series) &  # 롱 MA 상승
            (long_sma_short_series > long_sma_long_series) &
            (rsi < 70) &
            (
                (price > dcc_upper.shift(1)) |  # DCC 상단 돌파
                ((price > dcc_middle) & (dcc_position > 0.7))  # DCC 중간선 위 + 상단 70% 이상
            )
        )
        
        # 롱 매도 조건
        long_sell_condition = (
            (price < long_sma_long_series) |  # 롱 MA 하락
            (long_sma_short_series < long_sma_long_series) |
            (rsi > 80) |
            (price < dcc_lower.shift(1)) |  # DCC 하단 이탈
            ((price < dcc_middle) & (dcc_position < 0.3))  # DCC 중간선 아래 + 하단 30% 이하
        )
        
        # 숏 매수 조건 (숏 포지션 진입)
        short_condition = (
            (price < short_sma_long_series) &  # 숏 MA 하락
            (short_sma_short_series < short_sma_long_series) &
            (rsi > 30) &
            (
                (price < dcc_lower.shift(1)) |  # DCC 하단 이탈
                ((price < dcc_middle) & (dcc_position < 0.3))  # DCC 중간선 아래 + 하단 30% 이하
            )
        )
        
        # 숏 매도 조건 (숏 포지션 청산)
        short_cover_condition = (
            (price > short_sma_long_series) |  # 숏 MA 상승
            (short_sma_short_series > short_sma_long_series) |
            (rsi < 20) |
            (price > dcc_upper.shift(1)) |  # DCC 상단 돌파
            ((price > dcc_middle) & (dcc_position > 0.7))  # DCC 중간선 위 + 상단 70% 이상
        )
        
        # 신호 생성
        long_signals = pd.Series(0, index=test_data.index)
        long_signals[long_buy_condition] = 1
        long_signals[long_sell_condition] = -1
        
        short_signals = pd.Series(0, index=test_data.index)
        short_signals[short_condition] = -1  # 숏 포지션
        short_signals[short_cover_condition] = 1  # 숏 청산
        
        # 신호 정리
        long_signal_changes = long_signals.diff() != 0
        long_signal_changes.iloc[0] = True
        long_signals[~long_signal_changes] = 0
        long_signals = long_signals.replace(0, method='ffill').fillna(0)
        
        short_signal_changes = short_signals.diff() != 0
        short_signal_changes.iloc[0] = True
        short_signals[~short_signal_changes] = 0
        short_signals = short_signals.replace(0, method='ffill').fillna(0)
        
        # 양방향 백테스트 실행
        initial_capital = 10000
        capital = initial_capital
        long_position_size = 0
        short_position_size = 0
        long_entry_price = 0
        short_entry_price = 0
        trades = []
        
        # 거래 로그 저장을 위한 리스트
        trade_log = []
        
        # 자본금 추적을 위한 변수들
        capital_history = [initial_capital]
        dates = [test_data.index[0]]
        
        # 모든 신호 이벤트 수집
        all_events = []
        
        # 롱 신호 이벤트
        long_buy_signals = (long_signals == 1) & long_signal_changes
        long_sell_signals = (long_signals == -1) & long_signal_changes
        for idx in test_data[long_buy_signals].index:
            all_events.append((idx, 'long_buy', test_data.loc[idx, 'close']))
        for idx in test_data[long_sell_signals].index:
            all_events.append((idx, 'long_sell', test_data.loc[idx, 'close']))
        
        # 숏 신호 이벤트
        short_signals_events = (short_signals == -1) & short_signal_changes
        short_cover_signals = (short_signals == 1) & short_signal_changes
        for idx in test_data[short_signals_events].index:
            all_events.append((idx, 'short_enter', test_data.loc[idx, 'close']))
        for idx in test_data[short_cover_signals].index:
            all_events.append((idx, 'short_cover', test_data.loc[idx, 'close']))
        
        all_events.sort(key=lambda x: x[0])
        
        for timestamp, action, price in all_events:
            if action == 'long_buy' and long_position_size == 0:
                # 롱 매수
                available_capital = capital * 0.475  # 절반만 롱에 사용
                long_position_size = available_capital / price
                long_entry_price = price
                capital -= available_capital
                
                # 거래 로그 기록
                trade_record = {
                    'timestamp': timestamp,
                    'entry_price': price,
                    'exit_price': None,
                    'pnl': None,
                    'type': 'long',
                    'action': 'entry'
                }
                trade_log.append(trade_record)
                
                # 자본금 추적
                capital_history.append(capital)
                dates.append(timestamp)
                
            elif action == 'long_sell' and long_position_size > 0:
                # 롱 매도
                pnl = (price - long_entry_price) * long_position_size
                capital += long_position_size * price
                
                trade_record = {
                    'timestamp': timestamp,
                    'entry_price': long_entry_price,
                    'exit_price': price,
                    'pnl': pnl,
                    'type': 'long',
                    'action': 'exit'
                }
                trades.append(trade_record)
                trade_log.append(trade_record)
                
                long_position_size = 0
                long_entry_price = 0
                
                # 자본금 추적
                capital_history.append(capital)
                dates.append(timestamp)
                
            elif action == 'short_enter' and short_position_size == 0:
                # 숏 포지션 진입
                available_capital = capital * 0.475  # 절반만 숏에 사용
                short_position_size = available_capital / price
                short_entry_price = price
                capital += available_capital  # 숏은 현금을 받음
                
                # 거래 로그 기록
                trade_record = {
                    'timestamp': timestamp,
                    'entry_price': price,
                    'exit_price': None,
                    'pnl': None,
                    'type': 'short',
                    'action': 'entry'
                }
                trade_log.append(trade_record)
                
                # 자본금 추적
                capital_history.append(capital)
                dates.append(timestamp)
                
            elif action == 'short_cover' and short_position_size > 0:
                # 숏 포지션 청산
                pnl = (short_entry_price - price) * short_position_size
                capital -= short_position_size * price
                
                trade_record = {
                    'timestamp': timestamp,
                    'entry_price': short_entry_price,
                    'exit_price': price,
                    'pnl': pnl,
                    'type': 'short',
                    'action': 'exit'
                }
                trades.append(trade_record)
                trade_log.append(trade_record)
                
                short_position_size = 0
                short_entry_price = 0
                
                # 자본금 추적
                capital_history.append(capital)
                dates.append(timestamp)
        
        # 최종 포지션 청산
        final_price = test_data['close'].iloc[-1]
        
        if long_position_size > 0:
            pnl = (final_price - long_entry_price) * long_position_size
            capital += long_position_size * final_price
            
            trades.append({
                'entry_price': long_entry_price,
                'exit_price': final_price,
                'pnl': pnl,
                'type': 'long'
            })
        
        if short_position_size > 0:
            pnl = (short_entry_price - final_price) * short_position_size
            capital -= short_position_size * final_price
            
            trades.append({
                'entry_price': short_entry_price,
                'exit_price': final_price,
                'pnl': pnl,
                'type': 'short'
            })
        
        # 성과 계산
        total_return = (capital - initial_capital) / initial_capital * 100
        
        if trades:
            trades_df = pd.DataFrame(trades)
            winning_trades = trades_df[trades_df['pnl'] > 0]
            win_rate = len(winning_trades) / len(trades_df) * 100
            
            # 롱/숏 분리 통계
            long_trades = trades_df[trades_df['type'] == 'long']
            short_trades = trades_df[trades_df['type'] == 'short']
            
            long_win_rate = len(long_trades[long_trades['pnl'] > 0]) / len(long_trades) * 100 if len(long_trades) > 0 else 0
            short_win_rate = len(short_trades[short_trades['pnl'] > 0]) / len(short_trades) * 100 if len(short_trades) > 0 else 0
            
            # 최대 낙폭 계산
            pnl_values = trades_df['pnl'].values
            cumulative_pnl = np.cumsum(pnl_values)
            capital_history = initial_capital + cumulative_pnl
            
            peak = np.maximum.accumulate(capital_history)
            drawdown = (peak - capital_history) / peak * 100
            max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
        else:
            win_rate = 0
            long_win_rate = 0
            short_win_rate = 0
            max_dd = 0
        
        # 거래 통계 계산 (손절/익절)
        trade_stats = self.calculate_trade_statistics(trades)
        
        # 거래 로그를 파일로 저장 (최종 백테스트에서만)
        if hasattr(self, 'save_trade_log_enabled') and self.save_trade_log_enabled:
            self.save_trade_log(trade_log)
        
        return {
            'long_sma_short': long_sma_short,
            'long_sma_long': long_sma_long,
            'short_sma_short': short_sma_short,
            'short_sma_long': short_sma_long,
            'dcc_period': dcc_period,
            'total_return': total_return,
            'win_rate': win_rate,
            'long_win_rate': long_win_rate,
            'short_win_rate': short_win_rate,
            'max_drawdown': max_dd,
            'total_trades': len(trades),
            'long_trades': len(trades_df[trades_df['type'] == 'long']) if trades else 0,
            'short_trades': len(trades_df[trades_df['type'] == 'short']) if trades else 0,
            'final_capital': capital,
            'capital_history': capital_history,
            'dates': dates,
            # 손절/익절 통계 추가
            'stop_loss_count': trade_stats['stop_loss_count'],
            'take_profit_count': trade_stats['take_profit_count'],
            'stop_loss_rate': trade_stats['stop_loss_rate'],
            'take_profit_rate': trade_stats['take_profit_rate'],
            'avg_loss': trade_stats['avg_loss'],
            'avg_profit': trade_stats['avg_profit'],
            # 급락 손절 통계 추가
            'crash_stop_count': trade_stats['crash_stop_count'],
            'crash_stop_rate': trade_stats['crash_stop_rate'],
            'normal_stop_count': trade_stats['normal_stop_count'],
            'normal_stop_rate': trade_stats['normal_stop_rate'],
            'avg_crash_loss': trade_stats['avg_crash_loss'],
            'avg_normal_loss': trade_stats['avg_normal_loss']
        }
    
    def run_backtest_long(self, sma_short, sma_long, start_idx, end_idx):
        """롱 전용 백테스트 실행"""
        # 데이터 슬라이싱
        test_data = self.data.iloc[start_idx:end_idx].copy()
        
        # 지표 계산
        test_data['sma_short'] = test_data['close'].rolling(window=sma_short).mean()
        test_data['sma_long'] = test_data['close'].rolling(window=sma_long).mean()
        
        # RSI 계산
        delta = test_data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        test_data['rsi'] = 100 - (100 / (1 + rs))
        
        # 롱 전용 신호 생성
        price = test_data['close']
        sma_short_series = test_data['sma_short']
        sma_long_series = test_data['sma_long']
        rsi = test_data['rsi']
        
        # 롱 매수 조건
        buy_condition = (
            (price > sma_long_series) &
            (sma_short_series > sma_long_series) &
            (rsi < 70)
        )
        
        # 롱 매도 조건
        sell_condition = (
            (price < sma_long_series) |
            (sma_short_series < sma_long_series) |
            (rsi > 80)
        )
        
        signals = pd.Series(0, index=test_data.index)
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        
        # 신호 정리
        signal_changes = signals.diff() != 0
        signal_changes.iloc[0] = True
        signals[~signal_changes] = 0
        signals = signals.replace(0, method='ffill').fillna(0)
        
        # 롱 전용 백테스트 실행
        initial_capital = 10000
        capital = initial_capital
        position_size = 0
        entry_price = 0
        trades = []
        
        # 신호 변화점 찾기
        buy_signals = (signals == 1) & signal_changes
        sell_signals = (signals == -1) & signal_changes
        
        buy_indices = test_data[buy_signals].index
        sell_indices = test_data[sell_signals].index
        
        # 모든 이벤트를 시간순으로 정렬
        all_events = []
        for idx in buy_indices:
            all_events.append((idx, 'buy', test_data.loc[idx, 'close']))
        for idx in sell_indices:
            all_events.append((idx, 'sell', test_data.loc[idx, 'close']))
        
        all_events.sort(key=lambda x: x[0])
        
        # 수수료 설정
        fee_buy = self.config.get('risk_settings', {}).get('trading_fee_buy', 0.0005)
        fee_sell = self.config.get('risk_settings', {}).get('trading_fee_sell', 0.0005)
        
        for timestamp, action, price in all_events:
            if action == 'buy' and position_size == 0:
                # 롱 매수 (수수료 적용)
                available_capital = capital * 0.95
                position_size = available_capital / (price * (1 + fee_buy))
                entry_price = price
                capital -= available_capital
                
            elif action == 'sell' and position_size > 0:
                # 롱 매도 (수수료 적용)
                sell_price = price * (1 - fee_sell)
                pnl = (sell_price - entry_price) * position_size
                capital += position_size * sell_price
                
                trades.append({
                    'entry_price': entry_price,
                    'exit_price': price,
                    'pnl': pnl,
                    'type': 'long'
                })
                
                position_size = 0
                entry_price = 0
        
        # 최종 포지션 청산
        if position_size > 0:
            final_price = test_data['close'].iloc[-1]
            pnl = (final_price - entry_price) * position_size
            capital += position_size * final_price
            
            trades.append({
                'entry_price': entry_price,
                'exit_price': final_price,
                'pnl': pnl,
                'type': 'long'
            })
        
        # 성과 계산
        total_return = (capital - initial_capital) / initial_capital * 100
        
        if trades:
            trades_df = pd.DataFrame(trades)
            winning_trades = trades_df[trades_df['pnl'] > 0]
            win_rate = len(winning_trades) / len(trades_df) * 100
            
            # 최대 낙폭 계산
            pnl_values = trades_df['pnl'].values
            cumulative_pnl = np.cumsum(pnl_values)
            capital_history = initial_capital + cumulative_pnl
            
            peak = np.maximum.accumulate(capital_history)
            drawdown = (peak - capital_history) / peak * 100
            max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
        else:
            win_rate = 0
            max_dd = 0
        
        return {
            'sma_short': sma_short,
            'sma_long': sma_long,
            'total_return': total_return,
            'win_rate': win_rate,
            'max_drawdown': max_dd,
            'total_trades': len(trades),
            'final_capital': capital
        }
    
    def run_backtest_short(self, sma_short, sma_long, start_idx, end_idx):
        """숏 전용 백테스트 실행"""
        # 데이터 슬라이싱
        test_data = self.data.iloc[start_idx:end_idx].copy()
        
        # 지표 계산
        test_data['sma_short'] = test_data['close'].rolling(window=sma_short).mean()
        test_data['sma_long'] = test_data['close'].rolling(window=sma_long).mean()
        
        # RSI 계산
        delta = test_data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        test_data['rsi'] = 100 - (100 / (1 + rs))
        
        # 숏 전용 신호 생성
        price = test_data['close']
        sma_short_series = test_data['sma_short']
        sma_long_series = test_data['sma_long']
        rsi = test_data['rsi']
        
        # 숏 매수 조건 (숏 포지션 진입)
        short_condition = (
            (price < sma_long_series) &
            (sma_short_series < sma_long_series) &
            (rsi > 30)
        )
        
        # 숏 매도 조건 (숏 포지션 청산)
        cover_condition = (
            (price > sma_long_series) |
            (sma_short_series > sma_long_series) |
            (rsi < 20)
        )
        
        signals = pd.Series(0, index=test_data.index)
        signals[short_condition] = -1  # 숏 포지션
        signals[cover_condition] = 1   # 숏 청산
        
        # 신호 정리
        signal_changes = signals.diff() != 0
        signal_changes.iloc[0] = True
        signals[~signal_changes] = 0
        signals = signals.replace(0, method='ffill').fillna(0)
        
        # 숏 전용 백테스트 실행
        initial_capital = 10000
        capital = initial_capital
        position_size = 0
        entry_price = 0
        trades = []
        
        # 신호 변화점 찾기
        short_signals = (signals == -1) & signal_changes
        cover_signals = (signals == 1) & signal_changes
        
        short_indices = test_data[short_signals].index
        cover_indices = test_data[cover_signals].index
        
        # 모든 이벤트를 시간순으로 정렬
        all_events = []
        for idx in short_indices:
            all_events.append((idx, 'short', test_data.loc[idx, 'close']))
        for idx in cover_indices:
            all_events.append((idx, 'cover', test_data.loc[idx, 'close']))
        
        all_events.sort(key=lambda x: x[0])
        
        for timestamp, action, price in all_events:
            if action == 'short' and position_size == 0:
                # 숏 포지션 진입
                available_capital = capital * 0.95
                position_size = available_capital / price
                entry_price = price
                capital += available_capital  # 숏은 현금을 받음
                
            elif action == 'cover' and position_size > 0:
                # 숏 포지션 청산
                pnl = (entry_price - price) * position_size  # 숏은 가격이 내려야 수익
                capital -= position_size * price  # 숏 청산 시 현금 지불
                
                trades.append({
                    'entry_price': entry_price,
                    'exit_price': price,
                    'pnl': pnl,
                    'type': 'short'
                })
                
                position_size = 0
                entry_price = 0
        
        # 최종 포지션 청산
        if position_size > 0:
            final_price = test_data['close'].iloc[-1]
            pnl = (entry_price - final_price) * position_size
            capital -= position_size * final_price
            
            trades.append({
                'entry_price': entry_price,
                'exit_price': final_price,
                'pnl': pnl,
                'type': 'short'
            })
        
        # 성과 계산
        total_return = (capital - initial_capital) / initial_capital * 100
        
        if trades:
            trades_df = pd.DataFrame(trades)
            winning_trades = trades_df[trades_df['pnl'] > 0]
            win_rate = len(winning_trades) / len(trades_df) * 100
            
            # 최대 낙폭 계산
            pnl_values = trades_df['pnl'].values
            cumulative_pnl = np.cumsum(pnl_values)
            capital_history = initial_capital + cumulative_pnl
            
            peak = np.maximum.accumulate(capital_history)
            drawdown = (peak - capital_history) / peak * 100
            max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
        else:
            win_rate = 0
            max_dd = 0
        
        return {
            'sma_short': sma_short,
            'sma_long': sma_long,
            'total_return': total_return,
            'win_rate': win_rate,
            'max_drawdown': max_dd,
            'total_trades': len(trades),
            'final_capital': capital
        }
    
    def optimize_ma_parameters_long(self):
        """롱 전용 MA 파라미터 최적화 (3년치 데이터)"""
        print("=== 롱 전용 MA 파라미터 최적화 시작 ===")
        
        # 3년치 데이터 (2021-2023)
        train_start = pd.to_datetime('2021-01-01')
        train_end = pd.to_datetime('2023-12-31')
        
        train_data = self.data[(self.data.index >= train_start) & (self.data.index <= train_end)]
        train_start_idx = train_data.index[0]
        train_end_idx = train_data.index[-1]
        
        print(f"훈련 데이터: {len(train_data)}개 캔들")
        
        # MA 파라미터 조합 (1시간봉에 맞게 조정)
        sma_short_range = range(5, 21, 3)  # 5, 8, 11, 14, 17, 20
        sma_long_range = range(20, 81, 10)  # 20, 30, 40, 50, 60, 70, 80
        
        # 볼륨 필터 임계값 범위
        volume_threshold_range = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]  # 평균 볼륨 대비 비율
        
        best_result = None
        best_score = -np.inf
        
        total_combinations = len(sma_short_range) * len(sma_long_range) * len(volume_threshold_range)
        current_combination = 0
        
        for sma_short in sma_short_range:
            for sma_long in sma_long_range:
                if sma_short >= sma_long:
                    continue
                    
                for volume_threshold in volume_threshold_range:
                    current_combination += 1
                    print(f"진행률: {current_combination}/{total_combinations} - 롱 SMA({sma_short}, {sma_long}), 볼륨({volume_threshold})")
                    
                    try:
                        result = self.run_backtest_long_with_volume(sma_short, sma_long, volume_threshold,
                                                                  train_data.index.get_loc(train_start_idx), 
                                                                  train_data.index.get_loc(train_end_idx))
                        
                        # 점수 계산 (수익률 - 최대낙폭)
                        score = result['total_return'] - result['max_drawdown']
                        
                        if score > best_score:
                            best_score = score
                            best_result = result
                            print(f"  → 새로운 최고 점수: {score:.2f}% (수익률: {result['total_return']:.2f}%, MDD: {result['max_drawdown']:.2f}%)")
                        
                        self.optimization_results.append(result)
                        
                    except Exception as e:
                        print(f"  → 오류: {e}")
                        continue
        
        print(f"\n=== 롱 최적화 완료 ===")
        print(f"최적 파라미터: SMA({best_result['sma_short']}, {best_result['sma_long']})")
        print(f"볼륨 임계값: {best_result['volume_threshold']}")
        print(f"최고 점수: {best_score:.2f}%")
        print(f"수익률: {best_result['total_return']:.2f}%")
        print(f"최대낙폭: {best_result['max_drawdown']:.2f}%")
        print(f"승률: {best_result['win_rate']:.2f}%")
        
        # 최적값 저장
        self.save_optimal_params('long', best_result)
        
        return best_result
    
    def run_backtest_long_with_volume(self, sma_short, sma_long, volume_threshold, start_idx, end_idx):
        """볼륨 필터가 포함된 롱 전용 백테스트 실행"""
        # 데이터 슬라이싱
        test_data = self.data.iloc[start_idx:end_idx].copy()
        
        # 지표 계산
        test_data['sma_short'] = test_data['close'].rolling(window=sma_short).mean()
        test_data['sma_long'] = test_data['close'].rolling(window=sma_long).mean()
        
        # 볼륨 필터 계산 (평균 볼륨 대비 비율)
        test_data['volume_avg'] = test_data['volume'].rolling(window=20).mean()
        test_data['volume_ratio'] = test_data['volume'] / test_data['volume_avg']
        
        # RSI 계산
        delta = test_data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        test_data['rsi'] = 100 - (100 / (1 + rs))
        
        # 롱 전용 신호 생성 (볼륨 필터 포함)
        price = test_data['close']
        sma_short_series = test_data['sma_short']
        sma_long_series = test_data['sma_long']
        rsi = test_data['rsi']
        volume_ratio = test_data['volume_ratio']
        
        # 롱 매수 조건 (볼륨 필터 추가)
        buy_condition = (
            (price > sma_long_series) &
            (sma_short_series > sma_long_series) &
            (rsi < 70) &
            (volume_ratio >= volume_threshold)  # 볼륨 필터
        )
        
        # 롱 매도 조건
        sell_condition = (
            (price < sma_long_series) |
            (sma_short_series < sma_long_series) |
            (rsi > 80)
        )
        
        signals = pd.Series(0, index=test_data.index)
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        
        # 신호 정리
        signal_changes = signals.diff() != 0
        signal_changes.iloc[0] = True
        signals[~signal_changes] = 0
        signals = signals.replace(0, method='ffill').fillna(0)
        
        # 롱 전용 백테스트 실행
        initial_capital = 10000
        capital = initial_capital
        position_size = 0
        entry_price = 0
        trades = []
        
        # 신호 변화점 찾기
        buy_signals = (signals == 1) & signal_changes
        sell_signals = (signals == -1) & signal_changes
        
        buy_indices = test_data[buy_signals].index
        sell_indices = test_data[sell_signals].index
        
        # 모든 이벤트를 시간순으로 정렬
        all_events = []
        for idx in buy_indices:
            all_events.append((idx, 'buy', test_data.loc[idx, 'close']))
        for idx in sell_indices:
            all_events.append((idx, 'sell', test_data.loc[idx, 'close']))
        
        all_events.sort(key=lambda x: x[0])
        
        # 수수료 설정
        fee_buy = self.config.get('risk_settings', {}).get('trading_fee_buy', 0.0005)
        fee_sell = self.config.get('risk_settings', {}).get('trading_fee_sell', 0.0005)
        
        for timestamp, action, price in all_events:
            if action == 'buy' and position_size == 0:
                # 롱 매수 (수수료 적용)
                available_capital = capital * 0.95
                position_size = available_capital / (price * (1 + fee_buy))
                entry_price = price
                capital -= available_capital
                
            elif action == 'sell' and position_size > 0:
                # 롱 매도 (수수료 적용)
                sell_price = price * (1 - fee_sell)
                pnl = (sell_price - entry_price) * position_size
                capital += position_size * sell_price
                
                trades.append({
                    'entry_price': entry_price,
                    'exit_price': price,
                    'pnl': pnl,
                    'type': 'long'
                })
                
                position_size = 0
                entry_price = 0
        
        # 최종 포지션 청산
        if position_size > 0:
            final_price = test_data['close'].iloc[-1]
            pnl = (final_price - entry_price) * position_size
            capital += position_size * final_price
            
            trades.append({
                'entry_price': entry_price,
                'exit_price': final_price,
                'pnl': pnl,
                'type': 'long'
            })
        
        # 성과 계산
        total_return = (capital - initial_capital) / initial_capital * 100
        
        if trades:
            trades_df = pd.DataFrame(trades)
            winning_trades = trades_df[trades_df['pnl'] > 0]
            win_rate = len(winning_trades) / len(trades_df) * 100
            
            # 최대 낙폭 계산
            pnl_values = trades_df['pnl'].values
            cumulative_pnl = np.cumsum(pnl_values)
            capital_history = initial_capital + cumulative_pnl
            
            peak = np.maximum.accumulate(capital_history)
            drawdown = (peak - capital_history) / peak * 100
            max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
        else:
            win_rate = 0
            max_dd = 0
        
        return {
            'sma_short': sma_short,
            'sma_long': sma_long,
            'volume_threshold': volume_threshold,
            'total_return': total_return,
            'win_rate': win_rate,
            'max_drawdown': max_dd,
            'total_trades': len(trades),
            'final_capital': capital
        }
    
    def save_optimal_params(self, strategy_type, params):
        """최적 파라미터를 ma_bot.json에 저장"""
        import json
        import os
        
        try:
            # 기존 설정 파일 읽기
            with open('ma_bot.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # optimal_params 섹션에 저장
            if 'optimal_params' not in config:
                config['optimal_params'] = {}
            
            # 큰 배열들은 제외하고 저장 (JSON 파일 크기 제한)
            params_to_save = params.copy()
            if 'capital_history' in params_to_save:
                del params_to_save['capital_history']
            if 'dates' in params_to_save:
                del params_to_save['dates']
            
            config['optimal_params'][strategy_type] = params_to_save
            
            # 파일에 저장
            with open('ma_bot.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            print(f"최적 파라미터 저장 완료: ma_bot.json의 {strategy_type} 섹션")
        except Exception as e:
            print(f"파라미터 저장 실패: {e}")

    def save_optimal_params_to_json(self, params, return_rate):
        """최적 파라미터와 수익률을 JSON에 저장"""
        try:
            with open('ma_bot.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # combined_longshort 섹션이 없으면 생성
            if 'combined_longshort' not in config:
                config['combined_longshort'] = {}
            
            # 최적 파라미터와 수익률 저장
            config['combined_longshort']['optimal_params'] = params
            config['combined_longshort']['optimal_return'] = return_rate
            config['combined_longshort']['last_updated'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with open('ma_bot.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 최적 파라미터가 JSON에 저장되었습니다!")
            print(f"   📊 수익률: {return_rate:.2f}%")
            print(f"   📅 저장 시간: {config['combined_longshort']['last_updated']}")
            
        except Exception as e:
            print(f"❌ JSON 저장 실패: {e}")
    
    def load_optimal_params(self, strategy_type):
        """최적 파라미터를 ma_bot.json에서 불러오기"""
        try:
            # 통합된 설정에서 optimal_params 섹션 읽기
            if 'optimal_params' in self.config and strategy_type in self.config['optimal_params']:
                params = self.config['optimal_params'][strategy_type]
                print(f"최적 파라미터 불러오기 완료: ma_bot.json의 {strategy_type} 섹션")
                return params
            else:
                print(f"저장된 {strategy_type} 파라미터가 없습니다.")
                return None
        except Exception as e:
            print(f"파라미터 불러오기 실패: {e}")
            return None
    
    def optimize_ma_parameters_short(self):
        """숏 전용 MA 파라미터 최적화 (3년치 데이터)"""
        print("=== 숏 전용 MA 파라미터 최적화 시작 ===")
        
        # 3년치 데이터 (2021-2023)
        train_start = pd.to_datetime('2021-01-01')
        train_end = pd.to_datetime('2023-12-31')
        
        train_data = self.data[(self.data.index >= train_start) & (self.data.index <= train_end)]
        train_start_idx = train_data.index[0]
        train_end_idx = train_data.index[-1]
        
        print(f"훈련 데이터: {len(train_data)}개 캔들")
        
        # MA 파라미터 조합 (4시간봉에 맞게 조정)
        sma_short_range = range(4, 30, 2)  # 3, 5, 7, 9, 11, 13, 15
        sma_long_range = range(40, 120, 5)  # 10, 15, 20, 25, 30, 35, 40, 45, 50
        volume_threshold_range = [0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 2.0, 3.0]
        
        best_result = None
        best_score = -np.inf
        
        total_combinations = len(sma_short_range) * len(sma_long_range) * len(volume_threshold_range)
        current_combination = 0
        
        for sma_short in sma_short_range:
            for sma_long in sma_long_range:
                if sma_short >= sma_long:
                    continue
                    
                for volume_threshold in volume_threshold_range:
                    current_combination += 1
                    print(f"진행률: {current_combination}/{total_combinations} - 숏 SMA({sma_short}, {sma_long}), 볼륨({volume_threshold})")
                    
                    try:
                        result = self.run_backtest_short_with_volume(sma_short, sma_long, volume_threshold)
                        
                        # 점수 계산 (수익률 - 최대낙폭)
                        score = result['total_return'] - result['max_drawdown']
                        
                        if score > best_score:
                            best_score = score
                            best_result = result
                            print(f"  → 새로운 최고 점수: {score:.2f}% (수익률: {result['total_return']:.2f}%, MDD: {result['max_drawdown']:.2f}%)")
                        
                        self.optimization_results.append(result)
                        
                    except Exception as e:
                        print(f"  → 오류: {e}")
                        continue
        
        print(f"\n=== 숏 최적화 완료 ===")
        print(f"최적 파라미터: SMA({best_result['sma_short']}, {best_result['sma_long']})")
        print(f"최고 점수: {best_score:.2f}%")
        print(f"수익률: {best_result['total_return']:.2f}%")
        print(f"최대낙폭: {best_result['max_drawdown']:.2f}%")
        print(f"승률: {best_result['win_rate']:.2f}%")
        
        return best_result
    
    def optimize_dcc_parameters(self):
        """던키안 채널 파라미터 최적화"""
        print("=== 던키안 채널 파라미터 최적화 시작 ===")
        
        # 최적화 중에는 거래 로그 저장 비활성화
        self.save_trade_log_enabled = False
        
        # 3년치 데이터 (2021-2023)
        train_start = pd.to_datetime('2021-01-01')
        train_end = pd.to_datetime('2023-12-31')
        
        train_data = self.data[(self.data.index >= train_start) & (self.data.index <= train_end)]
        train_start_idx = train_data.index[0]
        train_end_idx = train_data.index[-1]
        
        print(f"훈련 데이터: {len(train_data)}개 캔들")
        
        # DCC 파라미터 범위
        dcc_period_range = range(10, 51, 5)  # 10, 15, 20, 25, 30, 35, 40, 45, 50
        
        best_result = None
        best_score = -np.inf
        
        total_combinations = len(dcc_period_range)
        current_combination = 0
        
        for dcc_period in dcc_period_range:
            current_combination += 1
            print(f"진행률: {current_combination}/{total_combinations} - DCC Period: {dcc_period}")
            
            try:
                result = self.run_dcc_backtest(
                    dcc_period,
                    self.data.index.get_loc(train_start_idx), 
                    self.data.index.get_loc(train_end_idx)
                )
                
                # 점수 계산 (수익률 - 최대낙폭)
                score = result['total_return'] - result['max_drawdown']
                
                if score > best_score:
                    best_score = score
                    best_result = result
                    print(f"  → 새로운 최고 점수: {score:.2f}% (수익률: {result['total_return']:.2f}%, MDD: {result['max_drawdown']:.2f}%)")
                
                self.optimization_results.append(result)
                
            except Exception as e:
                print(f"  → 오류: {e}")
                continue
        
        print(f"\n=== DCC 최적화 완료 ===")
        print(f"최적 파라미터: DCC Period {best_result['dcc_period']}")
        print(f"최고 점수: {best_score:.2f}%")
        print(f"수익률: {best_result['total_return']:.2f}%")
        print(f"최대낙폭: {best_result['max_drawdown']:.2f}%")
        print(f"승률: {best_result['win_rate']:.2f}%")
        
        # 최적값 저장
        self.save_optimal_params('dcc', best_result)
        
        return best_result
    
    def optimize_combined_parameters(self):
        """이동평균 + 던키안 채널 결합 파라미터 최적화"""
        print("=== 결합 전략 파라미터 최적화 시작 ===")
        
        # 최적화 중에는 거래 로그 저장 비활성화
        self.save_trade_log_enabled = False
        
        # 3년치 데이터 (2021-2023)
        train_start = pd.to_datetime('2021-01-01')
        train_end = pd.to_datetime('2023-12-31')
        
        train_data = self.data[(self.data.index >= train_start) & (self.data.index <= train_end)]
        train_start_idx = train_data.index[0]
        train_end_idx = train_data.index[-1]
        
        print(f"훈련 데이터: {len(train_data)}개 캔들")
        
        # 파라미터 범위
        sma_short_range = range(5, 21, 3)  # 5, 8, 11, 14, 17, 20
        sma_long_range = range(20, 81, 10)  # 20, 30, 40, 50, 60, 70, 80
        dcc_period_range = range(15, 41, 5)  # 15, 20, 25, 30, 35, 40
        
        best_result = None
        best_score = -np.inf
        
        total_combinations = len(sma_short_range) * len(sma_long_range) * len(dcc_period_range)
        current_combination = 0
        
        for sma_short in sma_short_range:
            for sma_long in sma_long_range:
                if sma_short >= sma_long:
                    continue
                    
                for dcc_period in dcc_period_range:
                    current_combination += 1
                    print(f"진행률: {current_combination}/{total_combinations} - SMA({sma_short}, {sma_long}), DCC({dcc_period})")
                    
                    try:
                        result = self.run_combined_backtest(
                            sma_short, sma_long, dcc_period,
                            self.data.index.get_loc(train_start_idx), 
                            self.data.index.get_loc(train_end_idx)
                        )
                        
                        # 점수 계산 (수익률 - 최대낙폭)
                        score = result['total_return'] - result['max_drawdown']
                        
                        if score > best_score:
                            best_score = score
                            best_result = result
                            print(f"  → 새로운 최고 점수: {score:.2f}% (수익률: {result['total_return']:.2f}%, MDD: {result['max_drawdown']:.2f}%)")
                        
                        self.optimization_results.append(result)
                        
                    except Exception as e:
                        print(f"  → 오류: {e}")
                        continue
        
        print(f"\n=== 결합 전략 최적화 완료 ===")
        print(f"최적 파라미터: SMA({best_result['sma_short']}, {best_result['sma_long']}), DCC({best_result['dcc_period']})")
        print(f"최고 점수: {best_score:.2f}%")
        print(f"수익률: {best_result['total_return']:.2f}%")
        print(f"최대낙폭: {best_result['max_drawdown']:.2f}%")
        print(f"승률: {best_result['win_rate']:.2f}%")
        
        # 최적값 저장
        self.save_optimal_params('combined', best_result)
        
        return best_result
    
    def optimize_combined_longshort_parameters(self):
        """이동평균 + 던키안 채널 결합 양방향 파라미터 최적화"""
        print("=== 결합 양방향 전략 파라미터 최적화 시작 ===")
        
        # 최적화 중에는 거래 로그 저장 비활성화
        self.save_trade_log_enabled = False
        
        # 3년치 데이터 (2021-2023)
        train_start = pd.to_datetime('2021-01-01')
        train_end = pd.to_datetime('2023-12-31')
        
        train_data = self.data[(self.data.index >= train_start) & (self.data.index <= train_end)]
        train_start_idx = train_data.index[0]
        train_end_idx = train_data.index[-1]
        
        print(f"훈련 데이터: {len(train_data)}개 캔들")
        
        # 파라미터 범위 (간소화하여 실행 시간 단축)
        long_sma_short_range = range(5, 16, 3)  # 5, 8, 11, 14
        long_sma_long_range = range(20, 51, 10)  # 20, 30, 40, 50
        short_sma_short_range = range(4, 15, 3)  # 4, 7, 10, 13
        short_sma_long_range = range(15, 46, 10)  # 15, 25, 35, 45
        dcc_period_range = range(15, 36, 5)  # 15, 20, 25, 30, 35
        
        best_result = None
        best_score = -np.inf
        
        total_combinations = (len(long_sma_short_range) * len(long_sma_long_range) * 
                             len(short_sma_short_range) * len(short_sma_long_range) * 
                             len(dcc_period_range))
        current_combination = 0
        
        for long_sma_short in long_sma_short_range:
            for long_sma_long in long_sma_long_range:
                if long_sma_short >= long_sma_long:
                    continue
                    
                for short_sma_short in short_sma_short_range:
                    for short_sma_long in short_sma_long_range:
                        if short_sma_short >= short_sma_long:
                            continue
                            
                        for dcc_period in dcc_period_range:
                            current_combination += 1
                            print(f"진행률: {current_combination}/{total_combinations} - Long({long_sma_short}, {long_sma_long}), Short({short_sma_short}, {short_sma_long}), DCC({dcc_period})")
                            
                            try:
                                result = self.run_combined_longshort_backtest(
                                    long_sma_short, long_sma_long, short_sma_short, short_sma_long, dcc_period,
                                    self.data.index.get_loc(train_start_idx), 
                                    self.data.index.get_loc(train_end_idx)
                                )
                                
                                # 점수 계산 (수익률 - 최대낙폭)
                                score = result['total_return'] - result['max_drawdown']
                                
                                if score > best_score:
                                    best_score = score
                                    best_result = result
                                    print(f"  → 새로운 최고 점수: {score:.2f}% (수익률: {result['total_return']:.2f}%, MDD: {result['max_drawdown']:.2f}%)")
                                
                                self.optimization_results.append(result)
                                
                            except Exception as e:
                                print(f"  → 오류: {e}")
                                continue
        
        print(f"\n=== 결합 양방향 전략 최적화 완료 ===")
        print(f"최적 파라미터:")
        print(f"  롱: SMA({best_result['long_sma_short']}, {best_result['long_sma_long']})")
        print(f"  숏: SMA({best_result['short_sma_short']}, {best_result['short_sma_long']})")
        print(f"  DCC: {best_result['dcc_period']}")
        print(f"최고 점수: {best_score:.2f}%")
        print(f"수익률: {best_result['total_return']:.2f}%")
        print(f"최대낙폭: {best_result['max_drawdown']:.2f}%")
        print(f"전체 승률: {best_result['win_rate']:.2f}%")
        print(f"롱 승률: {best_result['long_win_rate']:.2f}%")
        print(f"숏 승률: {best_result['short_win_rate']:.2f}%")
        
        # 최적값 저장
        self.save_optimal_params('combined_longshort', best_result)
        
        # 최적 파라미터를 JSON에 저장
        best_params = {
            'long_sma_short': best_result['long_sma_short'],
            'long_sma_long': best_result['long_sma_long'],
            'short_sma_short': best_result['short_sma_short'],
            'short_sma_long': best_result['short_sma_long'],
            'dcc_period': best_result['dcc_period']
        }
        self.save_optimal_params_to_json(best_params, best_result['total_return'])
        
        return best_result
    
    def run_backtest_longshort(self, long_params, short_params, start_idx, end_idx):
        """양방향 매매 백테스트 실행"""
        # 데이터 슬라이싱
        test_data = self.data.iloc[start_idx:end_idx].copy()
        
        # 롱용 지표 계산
        test_data['long_sma_short'] = test_data['close'].rolling(window=long_params['sma_short']).mean()
        test_data['long_sma_long'] = test_data['close'].rolling(window=long_params['sma_long']).mean()
        
        # 숏용 지표 계산
        test_data['short_sma_short'] = test_data['close'].rolling(window=short_params['sma_short']).mean()
        test_data['short_sma_long'] = test_data['close'].rolling(window=short_params['sma_long']).mean()
        
        # RSI 계산
        delta = test_data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        test_data['rsi'] = 100 - (100 / (1 + rs))
        
        # 롱 신호 생성
        price = test_data['close']
        long_sma_short = test_data['long_sma_short']
        long_sma_long = test_data['long_sma_long']
        short_sma_short = test_data['short_sma_short']
        short_sma_long = test_data['short_sma_long']
        rsi = test_data['rsi']
        
        # 롱 매수 조건
        long_buy_condition = (
            (price > long_sma_long) &
            (long_sma_short > long_sma_long) &
            (rsi < 70)
        )
        
        # 롱 매도 조건
        long_sell_condition = (
            (price < long_sma_long) |
            (long_sma_short < long_sma_long) |
            (rsi > 80)
        )
        
        # 숏 매수 조건 (숏 포지션 진입)
        short_condition = (
            (price < short_sma_long) &
            (short_sma_short < short_sma_long) &
            (rsi > 30)
        )
        
        # 숏 매도 조건 (숏 포지션 청산)
        short_cover_condition = (
            (price > short_sma_long) |
            (short_sma_short > short_sma_long) |
            (rsi < 20)
        )
        
        # 신호 생성
        long_signals = pd.Series(0, index=test_data.index)
        long_signals[long_buy_condition] = 1
        long_signals[long_sell_condition] = -1
        
        short_signals = pd.Series(0, index=test_data.index)
        short_signals[short_condition] = -1  # 숏 포지션
        short_signals[short_cover_condition] = 1  # 숏 청산
        
        # 신호 정리
        long_signal_changes = long_signals.diff() != 0
        long_signal_changes.iloc[0] = True
        long_signals[~long_signal_changes] = 0
        long_signals = long_signals.replace(0, method='ffill').fillna(0)
        
        short_signal_changes = short_signals.diff() != 0
        short_signal_changes.iloc[0] = True
        short_signals[~short_signal_changes] = 0
        short_signals = short_signals.replace(0, method='ffill').fillna(0)
        
        # 양방향 백테스트 실행
        initial_capital = 10000
        capital = initial_capital
        long_position_size = 0
        short_position_size = 0
        long_entry_price = 0
        short_entry_price = 0
        trades = []
        
        # 거래 로그 저장을 위한 리스트
        trade_log = []
        
        # 자본금 추적을 위한 변수들
        capital_history = [initial_capital]
        dates = [test_data.index[0]]
        
        # 모든 신호 이벤트 수집
        all_events = []
        
        # 롱 신호 이벤트
        long_buy_signals = (long_signals == 1) & long_signal_changes
        long_sell_signals = (long_signals == -1) & long_signal_changes
        for idx in test_data[long_buy_signals].index:
            all_events.append((idx, 'long_buy', test_data.loc[idx, 'close']))
        for idx in test_data[long_sell_signals].index:
            all_events.append((idx, 'long_sell', test_data.loc[idx, 'close']))
        
        # 숏 신호 이벤트
        short_signals_events = (short_signals == -1) & short_signal_changes
        short_cover_signals = (short_signals == 1) & short_signal_changes
        for idx in test_data[short_signals_events].index:
            all_events.append((idx, 'short_enter', test_data.loc[idx, 'close']))
        for idx in test_data[short_cover_signals].index:
            all_events.append((idx, 'short_cover', test_data.loc[idx, 'close']))
        
        all_events.sort(key=lambda x: x[0])
        
        for timestamp, action, price in all_events:
            if action == 'long_buy' and long_position_size == 0:
                # 롱 매수
                available_capital = capital * 0.475  # 절반만 롱에 사용
                long_position_size = available_capital / price
                long_entry_price = price
                capital -= available_capital
                
                # 거래 로그 기록
                trade_record = {
                    'timestamp': timestamp,
                    'entry_price': price,
                    'exit_price': None,
                    'pnl': None,
                    'type': 'long',
                    'action': 'entry'
                }
                trade_log.append(trade_record)
                
                # 자본금 추적
                capital_history.append(capital)
                dates.append(timestamp)
                
            elif action == 'long_sell' and long_position_size > 0:
                # 롱 매도
                pnl = (price - long_entry_price) * long_position_size
                capital += long_position_size * price
                
                trade_record = {
                    'timestamp': timestamp,
                    'entry_price': long_entry_price,
                    'exit_price': price,
                    'pnl': pnl,
                    'type': 'long',
                    'action': 'exit'
                }
                trades.append(trade_record)
                trade_log.append(trade_record)
                
                long_position_size = 0
                long_entry_price = 0
                
                # 자본금 추적
                capital_history.append(capital)
                dates.append(timestamp)
                
            elif action == 'short_enter' and short_position_size == 0:
                # 숏 포지션 진입
                available_capital = capital * 0.475  # 절반만 숏에 사용
                short_position_size = available_capital / price
                short_entry_price = price
                capital += available_capital  # 숏은 현금을 받음
                
                # 거래 로그 기록
                trade_record = {
                    'timestamp': timestamp,
                    'entry_price': price,
                    'exit_price': None,
                    'pnl': None,
                    'type': 'short',
                    'action': 'entry'
                }
                trade_log.append(trade_record)
                
                # 자본금 추적
                capital_history.append(capital)
                dates.append(timestamp)
                
            elif action == 'short_cover' and short_position_size > 0:
                # 숏 포지션 청산
                pnl = (short_entry_price - price) * short_position_size
                capital -= short_position_size * price
                
                trade_record = {
                    'timestamp': timestamp,
                    'entry_price': short_entry_price,
                    'exit_price': price,
                    'pnl': pnl,
                    'type': 'short',
                    'action': 'exit'
                }
                trades.append(trade_record)
                trade_log.append(trade_record)
                
                short_position_size = 0
                short_entry_price = 0
                
                # 자본금 추적
                capital_history.append(capital)
                dates.append(timestamp)
        
        # 최종 포지션 청산
        final_price = test_data['close'].iloc[-1]
        
        if long_position_size > 0:
            pnl = (final_price - long_entry_price) * long_position_size
            capital += long_position_size * final_price
            
            trades.append({
                'entry_price': long_entry_price,
                'exit_price': final_price,
                'pnl': pnl,
                'type': 'long'
            })
        
        if short_position_size > 0:
            pnl = (short_entry_price - final_price) * short_position_size
            capital -= short_position_size * final_price
            
            trades.append({
                'entry_price': short_entry_price,
                'exit_price': final_price,
                'pnl': pnl,
                'type': 'short'
            })
        
        # 성과 계산
        total_return = (capital - initial_capital) / initial_capital * 100
        
        if trades:
            trades_df = pd.DataFrame(trades)
            winning_trades = trades_df[trades_df['pnl'] > 0]
            win_rate = len(winning_trades) / len(trades_df) * 100
            
            # 롱/숏 분리 통계
            long_trades = trades_df[trades_df['type'] == 'long']
            short_trades = trades_df[trades_df['type'] == 'short']
            
            long_win_rate = len(long_trades[long_trades['pnl'] > 0]) / len(long_trades) * 100 if len(long_trades) > 0 else 0
            short_win_rate = len(short_trades[short_trades['pnl'] > 0]) / len(short_trades) * 100 if len(short_trades) > 0 else 0
            
            # 최대 낙폭 계산
            pnl_values = trades_df['pnl'].values
            cumulative_pnl = np.cumsum(pnl_values)
            capital_history = initial_capital + cumulative_pnl
            
            peak = np.maximum.accumulate(capital_history)
            drawdown = (peak - capital_history) / peak * 100
            max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
        else:
            win_rate = 0
            long_win_rate = 0
            short_win_rate = 0
            max_dd = 0
        
        # 거래 로그를 파일로 저장
        self.save_trade_log(trade_log)
        
        return {
            'long_params': long_params,
            'short_params': short_params,
            'total_return': total_return,
            'win_rate': win_rate,
            'long_win_rate': long_win_rate,
            'short_win_rate': short_win_rate,
            'max_drawdown': max_dd,
            'total_trades': len(trades),
            'long_trades': len(trades_df[trades_df['type'] == 'long']) if trades else 0,
            'short_trades': len(trades_df[trades_df['type'] == 'short']) if trades else 0,
            'final_capital': capital,
            'capital_history': capital_history,
            'dates': dates
        }
    
    def save_trade_log(self, trade_log):
        """거래 로그를 CSV 파일로 저장"""
        if not trade_log:
            return
            
        import pandas as pd
        from datetime import datetime
        
        # 거래 로그를 DataFrame으로 변환
        df = pd.DataFrame(trade_log)
        
        # 타임스탬프를 문자열로 변환
        if 'timestamp' in df.columns:
            df['timestamp'] = df['timestamp'].astype(str)
        
        # 파일명 생성 (현재 시간 포함)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trade_log_{timestamp}.csv"
        
        # CSV 파일로 저장
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"거래 로그가 저장되었습니다: {filename}")
        
        # 거래 요약 출력
        print("\n=== 거래 로그 요약 ===")
        print(f"총 거래 수: {len(trade_log)}")
        
        # 롱/숏 분리 통계
        long_trades = [t for t in trade_log if t['type'] == 'long']
        short_trades = [t for t in trade_log if t['type'] == 'short']
        
        print(f"롱 거래: {len(long_trades)}회")
        print(f"숏 거래: {len(short_trades)}회")
        
        # 수익 거래 통계 (pnl이 None이 아닌 경우만)
        profitable_trades = [t for t in trade_log if t.get('pnl') is not None and t.get('pnl', 0) > 0]
        print(f"수익 거래: {len(profitable_trades)}회")
        
        if profitable_trades:
            avg_profit = sum(t['pnl'] for t in profitable_trades) / len(profitable_trades)
            print(f"평균 수익: ${avg_profit:.2f}")
        
        # 손실 거래 통계 (pnl이 None이 아닌 경우만)
        loss_trades = [t for t in trade_log if t.get('pnl') is not None and t.get('pnl', 0) < 0]
        if loss_trades:
            avg_loss = sum(t['pnl'] for t in loss_trades) / len(loss_trades)
            print(f"평균 손실: ${avg_loss:.2f}")
    
    def test_on_final_year(self, best_params):
        """마지막 1년치로 백테스트"""
        print("\n=== 마지막 1년치 백테스트 ===")
        
        # 마지막 1년치 데이터 (2024)
        test_start = pd.to_datetime('2024-01-01')
        test_end = pd.to_datetime('2024-12-31')
        
        test_data = self.data[(self.data.index >= test_start) & (self.data.index <= test_end)]
        test_start_idx = test_data.index[0]
        test_end_idx = test_data.index[-1]
        
        print(f"테스트 데이터: {len(test_data)}개 캔들")
        
        # 최적 파라미터로 백테스트
        result = self.run_backtest(best_params['sma_short'], best_params['sma_long'],
                                 self.data.index.get_loc(test_start_idx),
                                 self.data.index.get_loc(test_end_idx))
        
        print(f"\n=== 최종 백테스트 결과 ===")
        print(f"테스트 기간: 2024년 (1년)")
        print(f"MA 파라미터: SMA({best_params['sma_short']}, {best_params['sma_long']})")
        print(f"초기 자본금: $10,000")
        print(f"최종 자본금: ${result['final_capital']:,.2f}")
        print(f"총 수익률: {result['total_return']:.2f}%")
        print(f"총 거래 수: {result['total_trades']}")
        print(f"승률: {result['win_rate']:.2f}%")
        print(f"최대 낙폭: {result['max_drawdown']:.2f}%")
        
        return result
    
    def calculate_rsi(self, prices, period=14):
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def run_backtest_short_with_volume(self, sma_short, sma_long, volume_threshold):
        """숏 전용 백테스트 (볼륨 필터 포함)"""
        # 훈련 데이터 준비
        train_data = self.data[(self.data.index >= '2021-01-01') & (self.data.index < '2024-01-01')].copy()
        
        if len(train_data) < max(sma_long, 50):
            return None
            
        # SMA 계산
        sma_short_series = train_data['close'].rolling(window=sma_short).mean()
        sma_long_series = train_data['close'].rolling(window=sma_long).mean()
        
        # RSI 계산
        rsi = self.calculate_rsi(train_data['close'])
        
        # 볼륨 평균 계산 (20일)
        volume_avg = train_data['volume'].rolling(window=20).mean()
        volume_ratio = train_data['volume'] / volume_avg
        
        # 초기 자본
        initial_capital = 10000
        capital = initial_capital
        position_size = 0
        entry_price = 0
        trades = []
        
        # 수수료 설정
        fee_buy = self.config.get('risk_settings', {}).get('trading_fee_buy', 0.0005)
        fee_sell = self.config.get('risk_settings', {}).get('trading_fee_sell', 0.0005)
        
        for i in range(max(sma_long, 50), len(train_data)):
            current_price = train_data['close'].iloc[i]
            current_rsi = rsi.iloc[i]
            current_volume_ratio = volume_ratio.iloc[i]
            
            # 숏 진입 조건: 가격이 장기 MA 아래, 단기 MA가 장기 MA 아래, RSI > 30, 볼륨 필터
            short_condition = (
                (current_price < sma_long_series.iloc[i]) & 
                (sma_short_series.iloc[i] < sma_long_series.iloc[i]) & 
                (current_rsi > 30) &
                (current_volume_ratio >= volume_threshold)
            )
            
            # 숏 청산 조건: 가격이 장기 MA 위, 단기 MA가 장기 MA 위, RSI < 20
            cover_condition = (
                (current_price > sma_long_series.iloc[i]) | 
                (sma_short_series.iloc[i] > sma_long_series.iloc[i]) | 
                (current_rsi < 20)
            )
            
            if position_size == 0 and short_condition:
                # 숏 진입 (수수료 적용)
                available_capital = capital * 0.95  # 5% 여유
                position_size = available_capital / (current_price * (1 + fee_buy))
                entry_price = current_price
                capital += available_capital  # 숏 진입 시 현금 받음
                
                trades.append({
                    'timestamp': train_data.index[i],
                    'type': 'short',
                    'action': 'entry',
                    'price': current_price,
                    'size': position_size,
                    'capital': capital
                })
                
            elif position_size > 0 and cover_condition:
                # 숏 청산 (수수료 적용)
                sell_price = current_price * (1 - fee_sell)
                pnl = (entry_price - sell_price) * position_size
                capital -= position_size * sell_price  # 숏 청산 시 현금 지불
                
                trades.append({
                    'timestamp': train_data.index[i],
                    'type': 'short',
                    'action': 'exit',
                    'price': current_price,
                    'size': position_size,
                    'pnl': pnl,
                    'capital': capital
                })
                
                position_size = 0
                entry_price = 0
        
        # 최종 포지션 청산 (수수료 적용)
        if position_size > 0:
            final_price = train_data['close'].iloc[-1]
            sell_price = final_price * (1 - fee_sell)
            pnl = (entry_price - sell_price) * position_size
            capital -= position_size * sell_price
            
            trades.append({
                'timestamp': train_data.index[-1],
                'type': 'short',
                'action': 'final_exit',
                'price': final_price,
                'size': position_size,
                'pnl': pnl,
                'capital': capital
            })
        
        # 결과 계산
        total_return = ((capital - initial_capital) / initial_capital) * 100
        
        if trades:
            profitable_trades = [t for t in trades if t.get('pnl', 0) > 0]
            win_rate = (len(profitable_trades) / len([t for t in trades if 'pnl' in t])) * 100 if trades else 0
            
            # 최대 낙폭 계산
            capital_history = [initial_capital]
            for trade in trades:
                if 'capital' in trade:
                    capital_history.append(trade['capital'])
            
            max_capital = initial_capital
            max_drawdown = 0
            for cap in capital_history:
                if cap > max_capital:
                    max_capital = cap
                drawdown = (max_capital - cap) / max_capital * 100
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        else:
            win_rate = 0
            max_drawdown = 0
        
        result = {
            'sma_short': sma_short,
            'sma_long': sma_long,
            'volume_threshold': volume_threshold,
            'total_return': total_return,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'total_trades': len([t for t in trades if 'pnl' in t]),
            'final_capital': capital
        }
        
        return result
    
    def run(self, strategy_type='combined'):
        """전체 실행 - 다양한 전략 지원"""
        print("=== MA + DCC 통합 백테스트 시스템 ===")
        print(f"선택된 전략: {strategy_type}")
        
        # 1. 데이터 로딩
        if not self.load_data():
            return False
        
        if strategy_type == 'combined_longshort':
            # 결합 양방향 전략 (MA + DCC)
            print("\n=== 결합 양방향 전략 실행 ===")
            
            # 레버리지 설정 확인
            leverage_settings = self.config.get('leverage_settings', {})
            print(f"레버리지 설정: {leverage_settings}")
            print(f"레버리지 사용: {leverage_settings.get('use_leverage', False)}")
            print(f"레버리지 비율: {leverage_settings.get('leverage_ratio', 1.0)}배")
            
            best_combined_longshort_params = self.optimize_combined_longshort_parameters()
            
            # 최종 백테스트에서만 거래 로그 저장 활성화
            self.save_trade_log_enabled = True
            
            # 2024년 백테스트
            test_start = pd.to_datetime('2024-01-01')
            test_end = pd.to_datetime('2024-12-31')
            test_data = self.data[(self.data.index >= test_start) & (self.data.index <= test_end)]
            test_start_idx = test_data.index[0]
            test_end_idx = test_data.index[-1]
            
            # 레버리지 설정 전달
            leverage_ratio = leverage_settings.get('leverage_ratio', 1.0)
            
            final_result = self.run_combined_longshort_backtest(
                best_combined_longshort_params['long_sma_short'],
                best_combined_longshort_params['long_sma_long'],
                best_combined_longshort_params['short_sma_short'],
                best_combined_longshort_params['short_sma_long'],
                best_combined_longshort_params['dcc_period'],
                self.data.index.get_loc(test_start_idx),
                self.data.index.get_loc(test_end_idx),
                leverage_ratio  # 레버리지 비율 전달
            )
            
            print(f"\n=== 결합 양방향 전략 최종 결과 (2024년) ===")
            print(f"롱 SMA: ({final_result['long_sma_short']}, {final_result['long_sma_long']})")
            print(f"숏 SMA: ({final_result['short_sma_short']}, {final_result['short_sma_long']})")
            print(f"DCC Period: {final_result['dcc_period']}")
            print(f"초기 자본금: $10,000")
            print(f"최종 자본금: ${final_result['final_capital']:,.2f}")
            print(f"총 수익률: {final_result['total_return']:.2f}%")
            print(f"총 거래 수: {final_result['total_trades']} (롱: {final_result['long_trades']}, 숏: {final_result['short_trades']})")
            print(f"전체 승률: {final_result['win_rate']:.2f}%")
            print(f"롱 승률: {final_result['long_win_rate']:.2f}%")
            print(f"숏 승률: {final_result['short_win_rate']:.2f}%")
            print(f"최대 낙폭: {final_result['max_drawdown']:.2f}%")
            
            # 손절/익절 통계 출력
            print(f"\n=== 거래 통계 ===")
            print(f"전체 손절: {final_result['stop_loss_count']}회 ({final_result['stop_loss_rate']:.1f}%)")
            print(f"  ├ 급락 손절: {final_result['crash_stop_count']}회 ({final_result['crash_stop_rate']:.1f}%) - 평균 ${final_result['avg_crash_loss']:,.0f}")
            print(f"  └ 일반 손절: {final_result['normal_stop_count']}회 ({final_result['normal_stop_rate']:.1f}%) - 평균 ${final_result['avg_normal_loss']:,.0f}")
            print(f"익절 횟수: {final_result['take_profit_count']}회 ({final_result['take_profit_rate']:.1f}%) - 평균 ${final_result['avg_profit']:,.0f}")
            
            # 그래프 생성
            long_params = {
                'long_sma_short': final_result['long_sma_short'],
                'long_sma_long': final_result['long_sma_long']
            }
            short_params = {
                'short_sma_short': final_result['short_sma_short'],
                'short_sma_long': final_result['short_sma_long']
            }
            self.plot_combined_longshort_results(test_data, long_params, short_params, final_result['dcc_period'], final_result)
            
            return final_result
            
        else:
            # 기존 롱/숏 분리 전략
            print("\n=== 기존 롱/숏 분리 전략 실행 ===")
        
        # 2. 설정에 따른 파라미터 처리
        if self.config.get('use_saved_params', False):
            # 통합 설정 파일에서 파라미터 사용
            if 'optimal_params' in self.config:
                print("\n=== 저장된 최적 파라미터 사용 ===")
                best_long_params = self.config['optimal_params']['long']
                best_short_params = self.config['optimal_params']['short']
                
                print(f"롱 파라미터: SMA({best_long_params['sma_short']}, {best_long_params['sma_long']}), 볼륨({best_long_params['volume_threshold']})")
                print(f"숏 파라미터: SMA({best_short_params['sma_short']}, {best_short_params['sma_long']}), 볼륨({best_short_params['volume_threshold']})")
            else:
                print("설정 파일에 최적 파라미터가 없습니다. 최적화를 진행합니다.")
                # 3. 롱 전용 최적화
                print("\n" + "="*50)
                best_long_params = self.optimize_ma_parameters_long()
                
                # 4. 숏 전용 최적화
                print("\n" + "="*50)
                best_short_params = self.optimize_ma_parameters_short()
        else:
            # 최적화 실행
            print("\n=== 파라미터 최적화 실행 ===")
            # 3. 롱 전용 최적화
            print("\n" + "="*50)
            best_long_params = self.optimize_ma_parameters_long()
            
            # 4. 숏 전용 최적화
            print("\n" + "="*50)
            best_short_params = self.optimize_ma_parameters_short()
        
        # 4. 양방향 매매 백테스트 (2024년)
        print("\n" + "="*50)
        print("=== 2024년 양방향 매매 백테스트 ===")
        
        # 2024년 데이터
        test_start = pd.to_datetime('2024-01-01')
        test_end = pd.to_datetime('2024-12-31')
        
        test_data = self.data[(self.data.index >= test_start) & (self.data.index <= test_end)]
        test_start_idx = test_data.index[0]
        test_end_idx = test_data.index[-1]
        
        print(f"테스트 데이터: {len(test_data)}개 캔들")
        
        # 양방향 매매 백테스트
        final_result = self.run_backtest_longshort(
            best_long_params, 
            best_short_params,
            self.data.index.get_loc(test_start_idx),
            self.data.index.get_loc(test_end_idx)
        )
        
        # 결과 출력
        print(f"\n=== 최종 양방향 매매 결과 (2024년) ===")
        print(f"롱 파라미터: SMA({best_long_params['sma_short']}, {best_long_params['sma_long']})")
        print(f"숏 파라미터: SMA({best_short_params['sma_short']}, {best_short_params['sma_long']})")
        print(f"초기 자본금: $10,000")
        print(f"최종 자본금: ${final_result['final_capital']:,.2f}")
        print(f"총 수익률: {final_result['total_return']:.2f}%")
        print(f"총 거래 수: {final_result['total_trades']} (롱: {final_result['long_trades']}, 숏: {final_result['short_trades']})")
        print(f"전체 승률: {final_result['win_rate']:.2f}%")
        print(f"롱 승률: {final_result['long_win_rate']:.2f}%")
        print(f"숏 승률: {final_result['short_win_rate']:.2f}%")
        print(f"최대 낙폭: {final_result['max_drawdown']:.2f}%")
        
        # 그래프 생성
        self.plot_results(test_data, best_long_params, best_short_params, final_result)
        
        return final_result
    
    def plot_results(self, test_data, long_params, short_params, result):
        """결과 그래프 생성"""
        print("\n=== 그래프 생성 중... ===")
        
        # 지표 계산
        test_data = test_data.copy()
        test_data['long_sma_short'] = test_data['close'].rolling(window=long_params['sma_short']).mean()
        test_data['long_sma_long'] = test_data['close'].rolling(window=long_params['sma_long']).mean()
        test_data['short_sma_short'] = test_data['close'].rolling(window=short_params['sma_short']).mean()
        test_data['short_sma_long'] = test_data['close'].rolling(window=short_params['sma_long']).mean()
        
        # RSI 계산
        delta = test_data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        test_data['rsi'] = 100 - (100 / (1 + rs))
        
        # 신호 생성
        price = test_data['close']
        long_sma_short = test_data['long_sma_short']
        long_sma_long = test_data['long_sma_long']
        short_sma_short = test_data['short_sma_short']
        short_sma_long = test_data['short_sma_long']
        rsi = test_data['rsi']
        
        # 롱 신호
        long_buy_condition = (
            (price > long_sma_long) &
            (long_sma_short > long_sma_long) &
            (rsi < 70)
        )
        long_sell_condition = (
            (price < long_sma_long) |
            (long_sma_short < long_sma_long) |
            (rsi > 80)
        )
        
        # 숏 신호
        short_condition = (
            (price < short_sma_long) &
            (short_sma_short < short_sma_long) &
            (rsi > 30)
        )
        short_cover_condition = (
            (price > short_sma_long) |
            (short_sma_short > short_sma_long) |
            (rsi < 20)
        )
        
        # 그래프 생성
        fig, axes = plt.subplots(2, 1, figsize=(15, 10))
        fig.suptitle('BTCUSDT 2024년 롱/숏 분리 최적화 백테스트 결과', fontsize=16, fontweight='bold')
        
        # 1. 가격 차트와 MA
        ax1 = axes[0]
        ax1.plot(test_data.index, test_data['close'], label='BTC Price', linewidth=2, color='black')
        ax1.plot(test_data.index, test_data['long_sma_short'], label=f'Long SMA({long_params["sma_short"]})', alpha=0.7, color='blue')
        ax1.plot(test_data.index, test_data['long_sma_long'], label=f'Long SMA({long_params["sma_long"]})', alpha=0.7, color='red')
        ax1.plot(test_data.index, test_data['short_sma_short'], label=f'Short SMA({short_params["sma_short"]})', alpha=0.7, color='green')
        ax1.plot(test_data.index, test_data['short_sma_long'], label=f'Short SMA({short_params["sma_long"]})', alpha=0.7, color='orange')
        
        # 롱 매수/매도 신호
        long_buy_points = test_data[long_buy_condition]
        long_sell_points = test_data[long_sell_condition]
        ax1.scatter(long_buy_points.index, long_buy_points['close'], color='blue', marker='^', s=100, label='Long Buy', zorder=5)
        ax1.scatter(long_sell_points.index, long_sell_points['close'], color='red', marker='v', s=100, label='Long Sell', zorder=5)
        
        # 숏 매수/매도 신호
        short_points = test_data[short_condition]
        short_cover_points = test_data[short_cover_condition]
        ax1.scatter(short_points.index, short_points['close'], color='green', marker='s', s=100, label='Short Enter', zorder=5)
        ax1.scatter(short_cover_points.index, short_cover_points['close'], color='orange', marker='D', s=100, label='Short Cover', zorder=5)
        
        ax1.set_title('Price Chart with MA Signals')
        ax1.set_ylabel('Price (USDT)')
        ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # 2. 자본금 변화 차트
        ax2 = axes[1]
        
        # 실제 거래 시뮬레이션을 통한 자본금 추적
        initial_capital = 10000
        capital = initial_capital
        long_position_size = 0
        short_position_size = 0
        long_entry_price = 0
        short_entry_price = 0
        
        # 자본금 추적을 위한 변수들
        capital_history = [initial_capital]
        dates = [test_data.index[0]]
        
        # 실제 거래 시뮬레이션
        for i in range(1, len(test_data)):
            current_price = test_data['close'].iloc[i]
            current_date = test_data.index[i]
            
            # 롱 신호 확인
            if i >= long_params['sma_long']:
                long_sma_short = test_data['close'].iloc[i-long_params['sma_short']+1:i+1].mean()
                long_sma_long = test_data['close'].iloc[i-long_params['sma_long']+1:i+1].mean()
                
                # RSI 계산
                if i >= 14:
                    delta = test_data['close'].iloc[i-13:i+1].diff()
                    gain = (delta.where(delta > 0, 0)).mean()
                    loss = (-delta.where(delta < 0, 0)).mean()
                    rsi = 100 - (100 / (1 + gain / loss)) if loss != 0 else 50
                else:
                    rsi = 50
                
                # 롱 매수 조건
                if (current_price > long_sma_long and 
                    long_sma_short > long_sma_long and 
                    rsi < 70 and 
                    long_position_size == 0):
                    # 롱 매수
                    available_capital = capital * 0.475
                    long_position_size = available_capital / current_price
                    long_entry_price = current_price
                    capital -= available_capital
                
                # 롱 매도 조건
                elif ((current_price < long_sma_long or 
                       long_sma_short < long_sma_long or 
                       rsi > 80) and 
                      long_position_size > 0):
                    # 롱 매도
                    pnl = (current_price - long_entry_price) * long_position_size
                    capital += long_position_size * current_price
                    long_position_size = 0
                    long_entry_price = 0
                
                # 급격한 하락 감지 및 손절 (롱 포지션)
                elif long_position_size > 0:
                    # 5분봉 데이터로 급격한 하락 감지
                    if i >= 12:  # 1시간 = 12개 5분봉
                        # 최근 1시간 동안의 최고가 대비 현재가 하락률
                        recent_high = test_data['high'].iloc[i-12:i+1].max()
                        drop_ratio = (recent_high - current_price) / recent_high
                        
                        # 5% 이상 하락 시 손절
                        if drop_ratio > 0.05:
                            pnl = (current_price - long_entry_price) * long_position_size
                            capital += long_position_size * current_price
                            long_position_size = 0
                            long_entry_price = 0
            
            # 숏 신호 확인
            if i >= short_params['sma_long']:
                short_sma_short = test_data['close'].iloc[i-short_params['sma_short']+1:i+1].mean()
                short_sma_long = test_data['close'].iloc[i-short_params['sma_long']+1:i+1].mean()
                
                # RSI 계산
                if i >= 14:
                    delta = test_data['close'].iloc[i-13:i+1].diff()
                    gain = (delta.where(delta > 0, 0)).mean()
                    loss = (-delta.where(delta < 0, 0)).mean()
                    rsi = 100 - (100 / (1 + gain / loss)) if loss != 0 else 50
                else:
                    rsi = 50
                
                # 숏 진입 조건
                if (current_price < short_sma_long and 
                    short_sma_short < short_sma_long and 
                    rsi > 30 and 
                    short_position_size == 0):
                    # 숏 진입
                    available_capital = capital * 0.475
                    short_position_size = available_capital / current_price
                    short_entry_price = current_price
                    capital += available_capital
                
                # 숏 청산 조건
                elif ((current_price > short_sma_long or 
                       short_sma_short > short_sma_long or 
                       rsi < 20) and 
                      short_position_size > 0):
                    # 숏 청산
                    pnl = (short_entry_price - current_price) * short_position_size
                    capital -= short_position_size * current_price
                    short_position_size = 0
                    short_entry_price = 0
                
                # 급격한 상승 감지 및 손절 (숏 포지션)
                elif short_position_size > 0:
                    # 5분봉 데이터로 급격한 상승 감지
                    if i >= 12:  # 1시간 = 12개 5분봉
                        # 최근 1시간 동안의 최저가 대비 현재가 상승률
                        recent_low = test_data['low'].iloc[i-12:i+1].min()
                        rise_ratio = (current_price - recent_low) / recent_low
                        
                        # 5% 이상 상승 시 손절
                        if rise_ratio > 0.05:
                            pnl = (short_entry_price - current_price) * short_position_size
                            capital -= short_position_size * current_price
                            short_position_size = 0
                            short_entry_price = 0
            
            # 현재 포트폴리오 가치 계산
            portfolio_value = capital
            if long_position_size > 0:
                portfolio_value += long_position_size * current_price
            if short_position_size > 0:
                portfolio_value -= short_position_size * current_price
            
            capital_history.append(portfolio_value)
            dates.append(current_date)
        
        ax2.plot(dates, capital_history, label='Portfolio Value', linewidth=2, color='darkgreen')
        ax2.axhline(y=10000, color='gray', linestyle='--', alpha=0.7, label='Initial Capital ($10,000)')
        ax2.axhline(y=result['final_capital'], color='red', linestyle='--', alpha=0.7, label=f'Final Capital (${result["final_capital"]:,.0f})')
        ax2.set_title('Portfolio Value Over Time')
        ax2.set_ylabel('Portfolio Value (USDT)')
        ax2.set_xlabel('Date')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 결과 텍스트 추가
        result_text = f"""
Results Summary:
Total Return: {result['total_return']:.2f}%
Total Trades: {result['total_trades']} (Long: {result['long_trades']}, Short: {result['short_trades']})
Win Rate: {result['win_rate']:.2f}% (Long: {result['long_win_rate']:.2f}%, Short: {result['short_win_rate']:.2f}%)
Max Drawdown: {result['max_drawdown']:.2f}%
Final Capital: ${result['final_capital']:,.2f}
        """
        
        ax2.text(0.02, 0.98, result_text, transform=ax2.transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        # 날짜 포맷팅
        for ax in axes:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        plt.savefig('btc_longshort_backtest_2024.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        print("그래프가 'btc_longshort_backtest_2024.png'로 저장되었습니다.")
    
    def plot_combined_longshort_results(self, test_data, long_params, short_params, dcc_period, result):
        """결합 양방향 전략 결과 그래프 생성"""
        print("\n=== 결합 양방향 전략 그래프 생성 중... ===")
        
        # 지표 계산
        test_data = test_data.copy()
        test_data['long_sma_short'] = test_data['close'].rolling(window=long_params['long_sma_short']).mean()
        test_data['long_sma_long'] = test_data['close'].rolling(window=long_params['long_sma_long']).mean()
        test_data['short_sma_short'] = test_data['close'].rolling(window=short_params['short_sma_short']).mean()
        test_data['short_sma_long'] = test_data['close'].rolling(window=short_params['short_sma_long']).mean()
        
        # RSI 계산
        delta = test_data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        test_data['rsi'] = 100 - (100 / (1 + rs))
        
        # 던키안 채널 계산
        test_data['dcc_upper'] = test_data['high'].rolling(window=dcc_period).max()
        test_data['dcc_lower'] = test_data['low'].rolling(window=dcc_period).min()
        test_data['dcc_middle'] = (test_data['dcc_upper'] + test_data['dcc_lower']) / 2
        
        # 신호 생성
        price = test_data['close']
        long_sma_short = test_data['long_sma_short']
        long_sma_long = test_data['long_sma_long']
        short_sma_short = test_data['short_sma_short']
        short_sma_long = test_data['short_sma_long']
        rsi = test_data['rsi']
        dcc_upper = test_data['dcc_upper']
        dcc_lower = test_data['dcc_lower']
        dcc_middle = test_data['dcc_middle']
        dcc_position = (test_data['close'] - test_data['dcc_lower']) / (test_data['dcc_upper'] - test_data['dcc_lower'])
        
        # 롱 신호
        long_buy_condition = (
            (price > long_sma_long) &
            (long_sma_short > long_sma_long) &
            (rsi < 70) &
            (
                (price > dcc_upper.shift(1)) |
                ((price > dcc_middle) & (dcc_position > 0.7))
            )
        )
        long_sell_condition = (
            (price < long_sma_long) |
            (long_sma_short < long_sma_long) |
            (rsi > 80) |
            (price < dcc_lower.shift(1)) |
            ((price < dcc_middle) & (dcc_position < 0.3))
        )
        
        # 숏 신호
        short_condition = (
            (price < short_sma_long) &
            (short_sma_short < short_sma_long) &
            (rsi > 30) &
            (
                (price < dcc_lower.shift(1)) |
                ((price < dcc_middle) & (dcc_position < 0.3))
            )
        )
        short_cover_condition = (
            (price > short_sma_long) |
            (short_sma_short > short_sma_long) |
            (rsi < 20) |
            (price > dcc_upper.shift(1)) |
            ((price > dcc_middle) & (dcc_position > 0.7))
        )
        
        # 그래프 생성
        fig, axes = plt.subplots(3, 1, figsize=(15, 12))
        fig.suptitle('BTCUSDT 2024년 결합 양방향 전략 백테스트 결과', fontsize=16, fontweight='bold')
        
        # 1. 가격 차트와 지표
        ax1 = axes[0]
        ax1.plot(test_data.index, test_data['close'], label='BTC Price', linewidth=2, color='black')
        ax1.plot(test_data.index, test_data['long_sma_short'], label=f'Long SMA({long_params["long_sma_short"]})', alpha=0.7, color='blue')
        ax1.plot(test_data.index, test_data['long_sma_long'], label=f'Long SMA({long_params["long_sma_long"]})', alpha=0.7, color='red')
        ax1.plot(test_data.index, test_data['short_sma_short'], label=f'Short SMA({short_params["short_sma_short"]})', alpha=0.7, color='green')
        ax1.plot(test_data.index, test_data['short_sma_long'], label=f'Short SMA({short_params["short_sma_long"]})', alpha=0.7, color='orange')
        ax1.plot(test_data.index, test_data['dcc_upper'], label=f'DCC Upper({dcc_period})', alpha=0.5, color='purple', linestyle='--')
        ax1.plot(test_data.index, test_data['dcc_lower'], label=f'DCC Lower({dcc_period})', alpha=0.5, color='purple', linestyle='--')
        ax1.plot(test_data.index, test_data['dcc_middle'], label=f'DCC Middle({dcc_period})', alpha=0.5, color='purple', linestyle=':')
        
        # 롱 매수/매도 신호
        long_buy_points = test_data[long_buy_condition]
        long_sell_points = test_data[long_sell_condition]
        ax1.scatter(long_buy_points.index, long_buy_points['close'], color='blue', marker='^', s=100, label='Long Buy', zorder=5)
        ax1.scatter(long_sell_points.index, long_sell_points['close'], color='red', marker='v', s=100, label='Long Sell', zorder=5)
        
        # 숏 매수/매도 신호
        short_points = test_data[short_condition]
        short_cover_points = test_data[short_cover_condition]
        ax1.scatter(short_points.index, short_points['close'], color='green', marker='s', s=100, label='Short Enter', zorder=5)
        ax1.scatter(short_cover_points.index, short_cover_points['close'], color='orange', marker='D', s=100, label='Short Cover', zorder=5)
        
        ax1.set_title('Price Chart with Combined MA + DCC Signals')
        ax1.set_ylabel('Price (USDT)')
        ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # 2. RSI 차트
        ax2 = axes[1]
        ax2.plot(test_data.index, test_data['rsi'], label='RSI', color='purple', linewidth=1)
        ax2.axhline(y=70, color='red', linestyle='--', alpha=0.7, label='Overbought (70)')
        ax2.axhline(y=30, color='green', linestyle='--', alpha=0.7, label='Oversold (30)')
        ax2.axhline(y=80, color='darkred', linestyle='--', alpha=0.7, label='Strong Overbought (80)')
        ax2.axhline(y=20, color='darkgreen', linestyle='--', alpha=0.7, label='Strong Oversold (20)')
        ax2.set_title('RSI Indicator')
        ax2.set_ylabel('RSI')
        ax2.set_ylim(0, 100)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. 자본금 변화 차트 (실제 거래 추적)
        ax3 = axes[2]
        
        # 실제 거래 시뮬레이션을 통한 자본금 추적
        initial_capital = 10000
        capital = initial_capital
        long_position_size = 0
        short_position_size = 0
        long_entry_price = 0
        short_entry_price = 0
        
        # 자본금 추적을 위한 변수들
        capital_history = [initial_capital]
        dates = [test_data.index[0]]
        
        # 실제 거래 시뮬레이션
        for i in range(1, len(test_data)):
            current_price = test_data['close'].iloc[i]
            current_date = test_data.index[i]
            
            # 롱 신호 확인
            if i >= long_params['long_sma_long']:
                long_sma_short = test_data['close'].iloc[i-long_params['long_sma_short']+1:i+1].mean()
                long_sma_long = test_data['close'].iloc[i-long_params['long_sma_long']+1:i+1].mean()
                
                # RSI 계산
                if i >= 14:
                    delta = test_data['close'].iloc[i-13:i+1].diff()
                    gain = (delta.where(delta > 0, 0)).mean()
                    loss = (-delta.where(delta < 0, 0)).mean()
                    rsi = 100 - (100 / (1 + gain / loss)) if loss != 0 else 50
                else:
                    rsi = 50
                
                # DCC 계산
                if i >= result['dcc_period']:
                    dcc_upper = test_data['high'].iloc[i-result['dcc_period']+1:i+1].max()
                    dcc_lower = test_data['low'].iloc[i-result['dcc_period']+1:i+1].min()
                    dcc_middle = (dcc_upper + dcc_lower) / 2
                    dcc_position = (current_price - dcc_lower) / (dcc_upper - dcc_lower) if dcc_upper != dcc_lower else 0.5
                else:
                    dcc_upper = current_price
                    dcc_lower = current_price
                    dcc_middle = current_price
                    dcc_position = 0.5
                
                # 롱 매수 조건
                if (current_price > long_sma_long and 
                    long_sma_short > long_sma_long and 
                    rsi < 70 and 
                    (current_price > dcc_upper or (current_price > dcc_middle and dcc_position > 0.7)) and
                    long_position_size == 0):
                    # 롱 매수
                    available_capital = capital * 0.475
                    long_position_size = available_capital / current_price
                    long_entry_price = current_price
                    capital -= available_capital
                
                # 롱 매도 조건
                elif ((current_price < long_sma_long or 
                       long_sma_short < long_sma_long or 
                       rsi > 80 or
                       current_price < dcc_lower or 
                       (current_price < dcc_middle and dcc_position < 0.3)) and 
                      long_position_size > 0):
                    # 롱 매도
                    pnl = (current_price - long_entry_price) * long_position_size
                    capital += long_position_size * current_price
                    long_position_size = 0
                    long_entry_price = 0
            
            # 숏 신호 확인
            if i >= short_params['short_sma_long']:
                short_sma_short = test_data['close'].iloc[i-short_params['short_sma_short']+1:i+1].mean()
                short_sma_long = test_data['close'].iloc[i-short_params['short_sma_long']+1:i+1].mean()
                
                # RSI 계산
                if i >= 14:
                    delta = test_data['close'].iloc[i-13:i+1].diff()
                    gain = (delta.where(delta > 0, 0)).mean()
                    loss = (-delta.where(delta < 0, 0)).mean()
                    rsi = 100 - (100 / (1 + gain / loss)) if loss != 0 else 50
                else:
                    rsi = 50
                
                # DCC 계산
                if i >= result['dcc_period']:
                    dcc_upper = test_data['high'].iloc[i-result['dcc_period']+1:i+1].max()
                    dcc_lower = test_data['low'].iloc[i-result['dcc_period']+1:i+1].min()
                    dcc_middle = (dcc_upper + dcc_lower) / 2
                    dcc_position = (current_price - dcc_lower) / (dcc_upper - dcc_lower) if dcc_upper != dcc_lower else 0.5
                else:
                    dcc_upper = current_price
                    dcc_lower = current_price
                    dcc_middle = current_price
                    dcc_position = 0.5
                
                # 숏 진입 조건
                if (current_price < short_sma_long and 
                    short_sma_short < short_sma_long and 
                    rsi > 30 and 
                    (current_price < dcc_lower or (current_price < dcc_middle and dcc_position < 0.3)) and
                    short_position_size == 0):
                    # 숏 진입
                    available_capital = capital * 0.475
                    short_position_size = available_capital / current_price
                    short_entry_price = current_price
                    capital += available_capital
                
                # 숏 청산 조건
                elif ((current_price > short_sma_long or 
                       short_sma_short > short_sma_long or 
                       rsi < 20 or
                       current_price > dcc_upper or 
                       (current_price > dcc_middle and dcc_position > 0.7)) and 
                      short_position_size > 0):
                    # 숏 청산
                    pnl = (short_entry_price - current_price) * short_position_size
                    capital -= short_position_size * current_price
                    short_position_size = 0
                    short_entry_price = 0
            
            # 현재 포트폴리오 가치 계산
            portfolio_value = capital
            if long_position_size > 0:
                portfolio_value += long_position_size * current_price
            if short_position_size > 0:
                portfolio_value -= short_position_size * current_price
            
            capital_history.append(portfolio_value)
            dates.append(current_date)
        
        # 그래프 그리기
        ax3.plot(dates, capital_history, label='Portfolio Value', linewidth=2, color='darkgreen')
        
        ax3.axhline(y=10000, color='gray', linestyle='--', alpha=0.7, label='Initial Capital ($10,000)')
        ax3.axhline(y=result['final_capital'], color='red', linestyle='--', alpha=0.7, label=f'Final Capital (${result["final_capital"]:,.0f})')
        ax3.set_title('Portfolio Value Over Time')
        ax3.set_ylabel('Portfolio Value (USDT)')
        ax3.set_xlabel('Date')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 결과 텍스트 추가
        result_text = f"""
Results Summary:
Total Return: {result['total_return']:.2f}%
Total Trades: {result['total_trades']} (Long: {result['long_trades']}, Short: {result['short_trades']})
Win Rate: {result['win_rate']:.2f}% (Long: {result['long_win_rate']:.2f}%, Short: {result['short_win_rate']:.2f}%)
Max Drawdown: {result['max_drawdown']:.2f}%
Final Capital: ${result['final_capital']:,.2f}

Trade Statistics:
Stop Loss: {result['stop_loss_count']} ({result['stop_loss_rate']:.1f}%) | Avg Loss: ${result['avg_loss']:,.0f}
  ├ Crash Stop: {result['crash_stop_count']} ({result['crash_stop_rate']:.1f}%) | Avg: ${result['avg_crash_loss']:,.0f}
  └ Normal Stop: {result['normal_stop_count']} ({result['normal_stop_rate']:.1f}%) | Avg: ${result['avg_normal_loss']:,.0f}
Take Profit: {result['take_profit_count']} ({result['take_profit_rate']:.1f}%) | Avg Profit: ${result['avg_profit']:,.0f}

Parameters:
Long SMA: ({long_params['long_sma_short']}, {long_params['long_sma_long']})
Short SMA: ({short_params['short_sma_short']}, {short_params['short_sma_long']})
DCC Period: {dcc_period}
        """
        
        ax3.text(0.02, 0.98, result_text, transform=ax3.transAxes, fontsize=9,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        # 날짜 포맷팅
        for ax in axes:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        plt.savefig('btc_combined_longshort_backtest_2024.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        print("그래프가 'btc_combined_longshort_backtest_2024.png'로 저장되었습니다.")
    
    def run_leveraged_backtest(self):
        """레버리지가 제대로 적용된 백테스트 실행"""
        # 레버리지 설정 가져오기
        leverage_settings = self.get_leverage_settings()
        leverage_ratio = leverage_settings['leverage_ratio']
        
        print(f"레버리지 비율: {leverage_ratio}배")
        
        # 최적 파라미터 가져오기
        optimal_params = self.config.get('optimal_params', {}).get('combined_longshort', {})
        
        if not optimal_params:
            print("최적 파라미터가 없습니다. 기본값을 사용합니다.")
            optimal_params = {
                'long_sma_short': 8,
                'long_sma_long': 30,
                'short_sma_short': 7,
                'short_sma_long': 15,
                'dcc_period': 15
            }
        
        # 테스트 기간 설정
        test_start = pd.to_datetime('2024-01-01')
        test_end = pd.to_datetime('2024-12-31')
        test_data = self.data[(self.data.index >= test_start) & (self.data.index <= test_end)]
        test_start_idx = test_data.index[0]
        test_end_idx = test_data.index[-1]
        
        # 레버리지 적용 백테스트 실행
        result = self.run_combined_longshort_backtest_with_leverage(
            optimal_params['long_sma_short'],
            optimal_params['long_sma_long'],
            optimal_params['short_sma_short'],
            optimal_params['short_sma_long'],
            optimal_params['dcc_period'],
            self.data.index.get_loc(test_start_idx),
            self.data.index.get_loc(test_end_idx),
            leverage_ratio
        )
        
        print(f"\n=== 레버리지 {leverage_ratio}배 적용 결과 ===")
        print(f"총 수익률: {result['total_return']:.2f}%")
        print(f"승률: {result['win_rate']:.2f}%")
        print(f"최대 낙폭: {result['max_drawdown']:.2f}%")
        print(f"총 거래 수: {result['total_trades']}")
        print(f"최종 자본: {result['final_capital']:,.0f}")
        
        return result
    
    def run_combined_longshort_backtest_with_leverage(self, long_sma_short, long_sma_long, short_sma_short, short_sma_long, dcc_period=20, start_idx=0, end_idx=None, leverage_ratio=1.0):
        """레버리지가 제대로 적용된 이동평균 + 던키안 채널 결합 양방향 백테스트"""
        if end_idx is None:
            end_idx = len(self.data)
            
        # 데이터 슬라이싱
        test_data = self.data.iloc[start_idx:end_idx].copy()
        
        # 롱용 지표 계산
        test_data['long_sma_short'] = test_data['close'].rolling(window=long_sma_short).mean()
        test_data['long_sma_long'] = test_data['close'].rolling(window=long_sma_long).mean()
        
        # 숏용 지표 계산
        test_data['short_sma_short'] = test_data['close'].rolling(window=short_sma_short).mean()
        test_data['short_sma_long'] = test_data['close'].rolling(window=short_sma_long).mean()
        
        # RSI 계산
        delta = test_data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        test_data['rsi'] = 100 - (100 / (1 + rs))
        
        # 던키안 채널 계산
        test_data['dcc_upper'] = test_data['high'].rolling(window=dcc_period).max()
        test_data['dcc_lower'] = test_data['low'].rolling(window=dcc_period).min()
        test_data['dcc_middle'] = (test_data['dcc_upper'] + test_data['dcc_lower']) / 2
        test_data['dcc_position'] = (test_data['close'] - test_data['dcc_lower']) / (test_data['dcc_upper'] - test_data['dcc_lower'])
        
        # 결합 신호 생성
        price = test_data['close']
        long_sma_short_series = test_data['long_sma_short']
        long_sma_long_series = test_data['long_sma_long']
        short_sma_short_series = test_data['short_sma_short']
        short_sma_long_series = test_data['short_sma_long']
        rsi = test_data['rsi']
        dcc_upper = test_data['dcc_upper']
        dcc_lower = test_data['dcc_lower']
        dcc_middle = test_data['dcc_middle']
        dcc_position = test_data['dcc_position']
        
        # 롱 매수 조건 (MA + DCC 결합)
        long_buy_condition = (
            (price > long_sma_long_series) &  # 롱 MA 상승
            (long_sma_short_series > long_sma_long_series) &
            (rsi < 70) &
            (
                (price > dcc_upper.shift(1)) |  # DCC 상단 돌파
                ((price > dcc_middle) & (dcc_position > 0.7))  # DCC 중간선 위 + 상단 70% 이상
            )
        )
        
        # 롱 매도 조건
        long_sell_condition = (
            (price < long_sma_long_series) |  # 롱 MA 하락
            (long_sma_short_series < long_sma_long_series) |
            (rsi > 80) |
            (price < dcc_lower.shift(1)) |  # DCC 하단 이탈
            ((price < dcc_middle) & (dcc_position < 0.3))  # DCC 중간선 아래 + 하단 30% 이하
        )
        
        # 숏 매수 조건 (숏 포지션 진입)
        short_condition = (
            (price < short_sma_long_series) &  # 숏 MA 하락
            (short_sma_short_series < short_sma_long_series) &
            (rsi > 30) &
            (
                (price < dcc_lower.shift(1)) |  # DCC 하단 이탈
                ((price < dcc_middle) & (dcc_position < 0.3))  # DCC 중간선 아래 + 하단 30% 이하
            )
        )
        
        # 숏 매도 조건 (숏 포지션 청산)
        short_cover_condition = (
            (price > short_sma_long_series) |  # 숏 MA 상승
            (short_sma_short_series > short_sma_long_series) |
            (rsi < 20) |
            (price > dcc_upper.shift(1)) |  # DCC 상단 돌파
            ((price > dcc_middle) & (dcc_position > 0.7))  # DCC 중간선 위 + 상단 70% 이상
        )
        
        # 신호 생성
        long_signals = pd.Series(0, index=test_data.index)
        long_signals[long_buy_condition] = 1
        long_signals[long_sell_condition] = -1
        
        short_signals = pd.Series(0, index=test_data.index)
        short_signals[short_condition] = -1  # 숏 포지션
        short_signals[short_cover_condition] = 1  # 숏 청산
        
        # 신호 정리
        long_signal_changes = long_signals.diff() != 0
        long_signal_changes.iloc[0] = True
        long_signals[~long_signal_changes] = 0
        long_signals = long_signals.replace(0, method='ffill').fillna(0)
        
        short_signal_changes = short_signals.diff() != 0
        short_signal_changes.iloc[0] = True
        short_signals[~short_signal_changes] = 0
        short_signals = short_signals.replace(0, method='ffill').fillna(0)
        
        # 양방향 백테스트 실행 (레버리지 적용)
        initial_capital = 10000
        capital = initial_capital
        long_position_size = 0
        short_position_size = 0
        long_entry_price = 0
        short_entry_price = 0
        trades = []
        
        # 거래 로그 저장을 위한 리스트
        trade_log = []
        
        # 자본금 추적을 위한 변수들
        capital_history = [initial_capital]
        dates = [test_data.index[0]]
        
        # 모든 신호 이벤트 수집
        all_events = []
        
        # 롱 신호 이벤트
        long_buy_signals = (long_signals == 1) & long_signal_changes
        long_sell_signals = (long_signals == -1) & long_signal_changes
        for idx in test_data[long_buy_signals].index:
            all_events.append((idx, 'long_buy', test_data.loc[idx, 'close']))
        for idx in test_data[long_sell_signals].index:
            all_events.append((idx, 'long_sell', test_data.loc[idx, 'close']))
        
        # 숏 신호 이벤트
        short_signals_events = (short_signals == -1) & short_signal_changes
        short_cover_signals = (short_signals == 1) & short_signal_changes
        for idx in test_data[short_signals_events].index:
            all_events.append((idx, 'short_enter', test_data.loc[idx, 'close']))
        for idx in test_data[short_cover_signals].index:
            all_events.append((idx, 'short_cover', test_data.loc[idx, 'close']))
        
        all_events.sort(key=lambda x: x[0])
        
        for timestamp, action, price in all_events:
            if action == 'long_buy' and long_position_size == 0:
                # 롱 매수 (레버리지 적용)
                base_capital = capital * 0.475  # 절반만 롱에 사용
                available_capital = base_capital * leverage_ratio  # 레버리지 적용
                long_position_size = available_capital / price
                long_entry_price = price
                capital -= base_capital  # 실제로는 원래 자본만 차감
                
                # 거래 로그 기록
                trade_record = {
                    'timestamp': timestamp,
                    'entry_price': price,
                    'exit_price': None,
                    'pnl': None,
                    'type': 'long',
                    'action': 'entry',
                    'leverage': leverage_ratio
                }
                trade_log.append(trade_record)
                
                # 자본금 추적
                capital_history.append(capital)
                dates.append(timestamp)
                
            elif action == 'long_sell' and long_position_size > 0:
                # 롱 매도 (레버리지 적용)
                pnl = (price - long_entry_price) * long_position_size
                # 레버리지는 이미 포지션 크기에 반영되었으므로 그대로 사용
                capital += pnl
                
                trade_record = {
                    'timestamp': timestamp,
                    'entry_price': long_entry_price,
                    'exit_price': price,
                    'pnl': pnl,
                    'type': 'long',
                    'action': 'exit',
                    'leverage': leverage_ratio
                }
                trades.append(trade_record)
                trade_log.append(trade_record)
                
                long_position_size = 0
                long_entry_price = 0
                
                # 자본금 추적
                capital_history.append(capital)
                dates.append(timestamp)
                
            elif action == 'short_enter' and short_position_size == 0:
                # 숏 포지션 진입 (레버리지 적용)
                base_capital = capital * 0.475  # 절반만 숏에 사용
                available_capital = base_capital * leverage_ratio  # 레버리지 적용
                short_position_size = available_capital / price
                short_entry_price = price
                capital += base_capital  # 숏은 현금을 받음 (실제 자본만)
                
                # 거래 로그 기록
                trade_record = {
                    'timestamp': timestamp,
                    'entry_price': price,
                    'exit_price': None,
                    'pnl': None,
                    'type': 'short',
                    'action': 'entry',
                    'leverage': leverage_ratio
                }
                trade_log.append(trade_record)
                
                # 자본금 추적
                capital_history.append(capital)
                dates.append(timestamp)
                
            elif action == 'short_cover' and short_position_size > 0:
                # 숏 포지션 청산 (레버리지 적용)
                pnl = (short_entry_price - price) * short_position_size
                # 레버리지는 이미 포지션 크기에 반영되었으므로 그대로 사용
                capital -= short_position_size * price  # 숏 청산 시 현금 지출
                capital += pnl  # 수익 추가
                
                trade_record = {
                    'timestamp': timestamp,
                    'entry_price': short_entry_price,
                    'exit_price': price,
                    'pnl': pnl,
                    'type': 'short',
                    'action': 'exit',
                    'leverage': leverage_ratio
                }
                trades.append(trade_record)
                trade_log.append(trade_record)
                
                short_position_size = 0
                short_entry_price = 0
                
                # 자본금 추적
                capital_history.append(capital)
                dates.append(timestamp)
        
        # 최종 포지션 청산
        final_price = test_data['close'].iloc[-1]
        
        if long_position_size > 0:
            pnl = (final_price - long_entry_price) * long_position_size
            pnl_with_leverage = self.apply_leverage(pnl, leverage_ratio)
            capital += pnl_with_leverage
            
            trades.append({
                'entry_price': long_entry_price,
                'exit_price': final_price,
                'pnl': pnl_with_leverage,
                'type': 'long',
                'action': 'final_exit',
                'leverage': leverage_ratio
            })
        
        if short_position_size > 0:
            pnl = (short_entry_price - final_price) * short_position_size
            pnl_with_leverage = self.apply_leverage(pnl, leverage_ratio)
            capital -= short_position_size * final_price
            capital += pnl_with_leverage
            
            trades.append({
                'entry_price': short_entry_price,
                'exit_price': final_price,
                'pnl': pnl_with_leverage,
                'type': 'short',
                'action': 'final_exit',
                'leverage': leverage_ratio
            })
        
        # 거래 통계 계산
        if trades:
            trades_df = pd.DataFrame(trades)
            
            # 최대 낙폭 계산
            pnl_values = trades_df['pnl'].values
            cumulative_pnl = np.cumsum(pnl_values)
            capital_history = initial_capital + cumulative_pnl
            
            peak = np.maximum.accumulate(capital_history)
            drawdown = (peak - capital_history) / peak * 100
            max_dd = np.max(drawdown)
            
            # 롱/숏 거래 분리
            long_trades = trades_df[trades_df['type'] == 'long']
            short_trades = trades_df[trades_df['type'] == 'short']
            
            # 승률 계산
            total_trades = len(trades_df)
            winning_trades = len(trades_df[trades_df['pnl'] > 0])
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            # 롱/숏 승률
            long_winning = len(long_trades[long_trades['pnl'] > 0])
            long_win_rate = (long_winning / len(long_trades) * 100) if len(long_trades) > 0 else 0
            
            short_winning = len(short_trades[short_trades['pnl'] > 0])
            short_win_rate = (short_winning / len(short_trades) * 100) if len(short_trades) > 0 else 0
            
            # 손절/익절 통계
            stop_loss_count = len(trades_df[trades_df['pnl'] < 0])
            take_profit_count = len(trades_df[trades_df['pnl'] > 0])
            stop_loss_rate = (stop_loss_count / total_trades * 100) if total_trades > 0 else 0
            take_profit_rate = (take_profit_count / total_trades * 100) if total_trades > 0 else 0
            
            # 평균 손익
            avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if stop_loss_count > 0 else 0
            avg_profit = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if take_profit_count > 0 else 0
            
            # 급락 손절 통계
            crash_threshold = -500  # 급락 손절 기준
            crash_stop_count = len(trades_df[trades_df['pnl'] < crash_threshold])
            crash_stop_rate = (crash_stop_count / total_trades * 100) if total_trades > 0 else 0
            normal_stop_count = stop_loss_count - crash_stop_count
            normal_stop_rate = (normal_stop_count / total_trades * 100) if total_trades > 0 else 0
            
            # 급락/일반 손절 평균
            crash_losses = trades_df[trades_df['pnl'] < crash_threshold]['pnl']
            normal_losses = trades_df[(trades_df['pnl'] < 0) & (trades_df['pnl'] >= crash_threshold)]['pnl']
            avg_crash_loss = crash_losses.mean() if len(crash_losses) > 0 else 0
            avg_normal_loss = normal_losses.mean() if len(normal_losses) > 0 else 0
        else:
            max_dd = 0
            win_rate = 0
            long_win_rate = 0
            short_win_rate = 0
            stop_loss_count = 0
            take_profit_count = 0
            stop_loss_rate = 0
            take_profit_rate = 0
            avg_loss = 0
            avg_profit = 0
            crash_stop_count = 0
            crash_stop_rate = 0
            normal_stop_count = 0
            normal_stop_rate = 0
            avg_crash_loss = 0
            avg_normal_loss = 0
        
        # 총 수익률 계산
        total_return = ((capital - initial_capital) / initial_capital) * 100
        
        return {
            'long_sma_short': long_sma_short,
            'long_sma_long': long_sma_long,
            'short_sma_short': short_sma_short,
            'short_sma_long': short_sma_long,
            'dcc_period': dcc_period,
            'leverage_ratio': leverage_ratio,
            'total_return': total_return,
            'win_rate': win_rate,
            'long_win_rate': long_win_rate,
            'short_win_rate': short_win_rate,
            'max_drawdown': max_dd,
            'total_trades': len(trades),
            'long_trades': len([t for t in trades if t['type'] == 'long']),
            'short_trades': len([t for t in trades if t['type'] == 'short']),
            'final_capital': capital,
            'stop_loss_count': stop_loss_count,
            'take_profit_count': take_profit_count,
            'stop_loss_rate': stop_loss_rate,
            'take_profit_rate': take_profit_rate,
            'avg_loss': avg_loss,
            'avg_profit': avg_profit,
            'crash_stop_count': crash_stop_count,
            'crash_stop_rate': crash_stop_rate,
            'normal_stop_count': normal_stop_count,
            'normal_stop_rate': normal_stop_rate,
            'avg_crash_loss': avg_crash_loss,
            'avg_normal_loss': avg_normal_loss
        }

if __name__ == "__main__":
    # 최적화 및 백테스트 실행
    mabot = MABot(
        symbol='BTCUSDT',
        start_date='2021-01-01',
        end_date='2024-12-31'
    )
    
    # 결합 양방향 전략 (MA + DCC) 실행
    strategy = 'combined_longshort'
    results = mabot.run(strategy_type=strategy)
    
    # 레버리지 적용 백테스트 실행
    print("\n=== 레버리지 적용 백테스트 실행 ===")
    leverage_results = mabot.run_leveraged_backtest()