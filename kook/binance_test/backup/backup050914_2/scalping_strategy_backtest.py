#-*-coding:utf-8 -*-
'''
비트코인 선물 스캘핑 전략 백테스트
===============================

=== 전략 개요 ===
스캘핑 전략은 매우 짧은 시간 내에 작은 가격 변동을 이용하여 수익을 추구하는 전략입니다.
1분봉 데이터를 활용하여 고빈도 거래를 수행합니다.

=== 진입 조건 ===
1. RSI 반전: RSI < 30 (과매도) / RSI > 70 (과매수)
2. 볼린저 밴드 반전: 가격이 하단/상단 밴드 터치 후 반전
3. 스토캐스틱 반전: %K < 20 (과매도) / %K > 80 (과매수)
4. 거래량 확인: 평균 대비 1.0배 이상
5. 변동성 확인: ATR이 평균 대비 높을 때
6. 모멘텀 확인: 단기 모멘텀 반전

=== 청산 조건 ===
1. 빠른 수익 실현: 0.5% 수익 시 즉시 청산
2. 손절매: 진입가 대비 -0.3% (매우 타이트한 손절)
3. 시간 기반 청산: 30분 후 강제 청산
4. 반대 신호: 반대 방향 신호 발생 시 청산

=== 리스크 관리 ===
- 포지션 사이징: ATR 기반 동적 조정
- 최대 손실 제한: 계좌의 0.5% 이하
- 매우 빠른 진입/청산으로 리스크 최소화
- 연속 손실 시 거래 중단
'''

import os
import sys

# Windows에서 이모지 출력을 위한 인코딩 설정
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# 표준 출력 인코딩 강제 설정
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

class ScalpingStrategyBacktester:
    """스캘핑 전략 백테스터"""
    
    def __init__(self, initial_capital: float = 10000, leverage: float = 20, fee: float = 0.001):
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.fee = fee
        self.current_capital = initial_capital
        self.position = None
        self.trades = []
        self.equity_curve = []
        self.consecutive_losses = 0
        self.max_consecutive_losses = 10
        
    def load_data(self, data_dir: str, start_date: str, end_date: str, timeframe: str = '1m') -> pd.DataFrame:
        """데이터 로드"""
        print(f"📊 데이터 로드 중... ({timeframe}봉, {start_date} ~ {end_date})")
        
        btc_data_dir = os.path.join(data_dir, 'BTCUSDT', timeframe)
        
        if not os.path.exists(btc_data_dir):
            raise FileNotFoundError(f"데이터 디렉토리를 찾을 수 없습니다: {btc_data_dir}")
        
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        all_data = []
        current_date = start_dt
        
        # 연도별 파일 로드
        current_year = start_dt.year
        end_year = end_dt.year
        
        while current_year <= end_year:
            file_pattern = os.path.join(btc_data_dir, f"BTCUSDT_1m_{current_year}.csv")
            
            if os.path.exists(file_pattern):
                try:
                    df = pd.read_csv(file_pattern)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df = df.set_index('timestamp')
                    all_data.append(df)
                    print(f"✅ {current_year} 로드 완료: {len(df)}개 캔들")
                except Exception as e:
                    print(f"❌ {file_pattern} 로드 실패: {e}")
            
            current_year += 1
        
        if not all_data:
            raise ValueError("로드된 데이터가 없습니다.")
        
        combined_df = pd.concat(all_data, ignore_index=False)
        combined_df = combined_df.sort_index()
        combined_df = combined_df.drop_duplicates()
        combined_df = combined_df[(combined_df.index >= start_dt) & (combined_df.index <= end_dt)]
        
        print(f"✅ 전체 데이터 로드 완료: {len(combined_df)}개 캔들")
        print(f"📅 기간: {combined_df.index[0]} ~ {combined_df.index[-1]}")
        
        return combined_df
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표 계산"""
        print("🔧 기술적 지표 계산 중...")
        
        # 이동평균선
        df['ma_5'] = df['close'].rolling(5).mean()
        df['ma_10'] = df['close'].rolling(10).mean()
        df['ma_20'] = df['close'].rolling(20).mean()
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        df['atr'] = true_range.rolling(14).mean()
        df['atr_ma'] = df['atr'].rolling(20).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 스토캐스틱
        low_14 = df['low'].rolling(14).min()
        high_14 = df['high'].rolling(14).max()
        df['stoch_k'] = 100 * (df['close'] - low_14) / (high_14 - low_14)
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()
        
        # 볼린저 밴드
        df['bb_middle'] = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # 거래량 지표
        df['volume_ma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # 변동성 지표
        df['volatility'] = df['close'].rolling(20).std()
        df['volatility_ratio'] = df['volatility'] / df['volatility'].rolling(50).mean()
        
        # 모멘텀 지표
        df['momentum_1'] = df['close'].pct_change(1)
        df['momentum_3'] = df['close'].pct_change(3)
        df['momentum_5'] = df['close'].pct_change(5)
        
        # 가격 채널
        df['high_5'] = df['high'].rolling(5).max()
        df['low_5'] = df['low'].rolling(5).min()
        df['price_channel_position'] = (df['close'] - df['low_5']) / (df['high_5'] - df['low_5'])
        
        print("✅ 기술적 지표 계산 완료")
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """스캘핑 신호 생성"""
        print("📈 스캘핑 신호 생성 중...")
        
        df['signal'] = 0
        df['signal_strength'] = 0.0
        df['signal_type'] = 0  # 1: RSI 반전, 2: BB 반전, 3: 스토캐스틱 반전
        
        for i in range(1, len(df)):
            current_price = df['close'].iloc[i]
            rsi = df['rsi'].iloc[i]
            rsi_prev = df['rsi'].iloc[i-1]
            bb_position = df['bb_position'].iloc[i]
            bb_position_prev = df['bb_position'].iloc[i-1]
            stoch_k = df['stoch_k'].iloc[i]
            stoch_k_prev = df['stoch_k'].iloc[i-1]
            volume_ratio = df['volume_ratio'].iloc[i]
            volatility_ratio = df['volatility_ratio'].iloc[i]
            momentum_1 = df['momentum_1'].iloc[i]
            momentum_3 = df['momentum_3'].iloc[i]
            
            # RSI 반전 신호
            rsi_oversold_reversal = (rsi < 30 and rsi_prev >= 30) and (momentum_1 > 0)
            rsi_overbought_reversal = (rsi > 70 and rsi_prev <= 70) and (momentum_1 < 0)
            
            # 볼린저 밴드 반전 신호
            bb_oversold_reversal = (bb_position < 0.2 and bb_position_prev >= 0.2) and (momentum_1 > 0)
            bb_overbought_reversal = (bb_position > 0.8 and bb_position_prev <= 0.8) and (momentum_1 < 0)
            
            # 스토캐스틱 반전 신호
            stoch_oversold_reversal = (stoch_k < 20 and stoch_k_prev >= 20) and (momentum_1 > 0)
            stoch_overbought_reversal = (stoch_k > 80 and stoch_k_prev <= 80) and (momentum_1 < 0)
            
            # 상승 신호 조건
            if ((rsi_oversold_reversal or bb_oversold_reversal or stoch_oversold_reversal) and
                volume_ratio > 1.0 and  # 거래량 확인
                volatility_ratio > 0.8 and  # 변동성 확인
                momentum_3 > 0):  # 단기 모멘텀 확인
                
                # 신호 강도 계산
                rsi_strength = (30 - rsi) / 30 if rsi_oversold_reversal else 0
                bb_strength = (0.2 - bb_position) / 0.2 if bb_oversold_reversal else 0
                stoch_strength = (20 - stoch_k) / 20 if stoch_oversold_reversal else 0
                volume_strength = min(volume_ratio / 2.0, 1.0)
                volatility_strength = min(volatility_ratio, 1.0)
                momentum_strength = min(momentum_3 * 100, 1.0)
                
                signal_strength = (max(rsi_strength, bb_strength, stoch_strength) * 0.4 + 
                                 volume_strength * 0.2 + volatility_strength * 0.2 + momentum_strength * 0.2)
                
                # 신호 타입 결정
                if rsi_oversold_reversal:
                    signal_type = 1
                elif bb_oversold_reversal:
                    signal_type = 2
                else:
                    signal_type = 3
                
                df.iloc[i, df.columns.get_loc('signal')] = 1
                df.iloc[i, df.columns.get_loc('signal_strength')] = signal_strength
                df.iloc[i, df.columns.get_loc('signal_type')] = signal_type
            
            # 하락 신호 조건
            elif ((rsi_overbought_reversal or bb_overbought_reversal or stoch_overbought_reversal) and
                  volume_ratio > 1.0 and  # 거래량 확인
                  volatility_ratio > 0.8 and  # 변동성 확인
                  momentum_3 < 0):  # 단기 모멘텀 확인
                
                # 신호 강도 계산
                rsi_strength = (rsi - 70) / 30 if rsi_overbought_reversal else 0
                bb_strength = (bb_position - 0.8) / 0.2 if bb_overbought_reversal else 0
                stoch_strength = (stoch_k - 80) / 20 if stoch_overbought_reversal else 0
                volume_strength = min(volume_ratio / 2.0, 1.0)
                volatility_strength = min(volatility_ratio, 1.0)
                momentum_strength = min(abs(momentum_3) * 100, 1.0)
                
                signal_strength = (max(rsi_strength, bb_strength, stoch_strength) * 0.4 + 
                                 volume_strength * 0.2 + volatility_strength * 0.2 + momentum_strength * 0.2)
                
                # 신호 타입 결정
                if rsi_overbought_reversal:
                    signal_type = 1
                elif bb_overbought_reversal:
                    signal_type = 2
                else:
                    signal_type = 3
                
                df.iloc[i, df.columns.get_loc('signal')] = -1
                df.iloc[i, df.columns.get_loc('signal_strength')] = signal_strength
                df.iloc[i, df.columns.get_loc('signal_type')] = signal_type
        
        # 신호 필터링 (너무 빈번한 신호 제거)
        df['signal_filtered'] = df['signal']
        for i in range(1, len(df)):
            if df['signal'].iloc[i] != 0 and df['signal'].iloc[i-1] != 0:
                df.iloc[i, df.columns.get_loc('signal_filtered')] = 0
        
        print(f"✅ 신호 생성 완료: {len(df[df['signal_filtered'] != 0])}개 신호")
        return df
    
    def calculate_position_size(self, current_price: float, atr: float, signal_strength: float, 
                              signal_type: int, consecutive_losses: int) -> float:
        """포지션 사이즈 계산"""
        # 기본 리스크: 계좌의 0.5%
        base_risk = self.current_capital * 0.005
        
        # ATR 기반 포지션 사이즈
        atr_risk = atr * 1.5  # ATR의 1.5배를 리스크로 설정
        position_size = base_risk / atr_risk
        
        # 신호 강도에 따른 조정
        position_size *= (0.7 + signal_strength * 0.3)  # 0.7 ~ 1.0 배
        
        # 신호 타입에 따른 조정
        if signal_type == 1:  # RSI 반전
            position_size *= 1.1
        elif signal_type == 2:  # BB 반전
            position_size *= 1.05
        else:  # 스토캐스틱 반전
            position_size *= 1.0
        
        # 연속 손실에 따른 조정
        if consecutive_losses > 0:
            position_size *= (1 - consecutive_losses * 0.05)  # 연속 손실마다 5% 감소
        
        # 레버리지 적용
        position_size *= self.leverage
        
        # 최대 포지션 제한 (계좌의 10%)
        max_position = self.current_capital * 0.1 * self.leverage / current_price
        position_size = min(position_size, max_position)
        
        return max(0, position_size)
    
    def run_backtest(self, df: pd.DataFrame) -> Dict:
        """백테스트 실행"""
        print("🚀 스캘핑 전략 백테스트 실행 중...")
        
        position = 0  # 0: 없음, 1: 롱, -1: 숏
        entry_price = 0
        entry_time = None
        entry_atr = 0
        stop_loss = 0
        take_profit = 0
        position_size = 0
        max_hold_time = 30  # 최대 보유 시간 (분)
        
        trades = []
        equity_curve = []
        
        for i in range(len(df)):
            current_time = df.index[i]
            current_price = df['close'].iloc[i]
            signal = df['signal_filtered'].iloc[i]
            signal_strength = df['signal_strength'].iloc[i]
            signal_type = df['signal_type'].iloc[i]
            atr = df['atr'].iloc[i]
            
            # 포지션이 없는 경우
            if position == 0:
                # 연속 손실 제한 체크
                if self.consecutive_losses >= self.max_consecutive_losses:
                    continue
                
                if signal == 1:  # 롱 진입
                    position = 1
                    entry_price = current_price
                    entry_time = current_time
                    entry_atr = atr
                    position_size = self.calculate_position_size(current_price, atr, signal_strength, 
                                                              signal_type, self.consecutive_losses)
                    
                    # 매우 타이트한 손절/익절 설정
                    stop_loss = entry_price * (1 - 0.003)  # 0.3% 손절
                    take_profit = entry_price * (1 + 0.005)  # 0.5% 익절
                    
                    print(f"🟢 롱 진입: {current_time} | 가격: {current_price:.0f} | 크기: {position_size:.3f} | 타입: {signal_type}")
                    
                elif signal == -1:  # 숏 진입
                    position = -1
                    entry_price = current_price
                    entry_time = current_time
                    entry_atr = atr
                    position_size = self.calculate_position_size(current_price, atr, signal_strength, 
                                                              signal_type, self.consecutive_losses)
                    
                    # 매우 타이트한 손절/익절 설정
                    stop_loss = entry_price * (1 + 0.003)  # 0.3% 손절
                    take_profit = entry_price * (1 - 0.005)  # 0.5% 익절
                    
                    print(f"🔴 숏 진입: {current_time} | 가격: {current_price:.0f} | 크기: {position_size:.3f} | 타입: {signal_type}")
            
            # 포지션이 있는 경우
            else:
                # 시간 기반 청산 체크
                if entry_time and (current_time - entry_time).total_seconds() / 60 > max_hold_time:
                    # 시간 초과 청산
                    if position == 1:
                        pnl = (current_price - entry_price) / entry_price * self.leverage * (1 - self.fee)
                    else:
                        pnl = (entry_price - current_price) / entry_price * self.leverage * (1 - self.fee)
                    
                    self.current_capital *= (1 + pnl)
                    
                    trades.append({
                        'type': 'TIME_EXIT',
                        'position': 'LONG' if position == 1 else 'SHORT',
                        'entry_time': entry_time,
                        'exit_time': current_time,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'position_size': position_size,
                        'pnl': pnl,
                        'return_pct': pnl * 100,
                        'hold_time_minutes': (current_time - entry_time).total_seconds() / 60
                    })
                    
                    print(f"⏰ 시간 초과 청산: {current_time} | {position_size:.3f} | 수익률: {pnl*100:.2f}%")
                    
                    position = 0
                    continue
                
                # 반대 신호 체크
                if signal != 0 and signal != position:
                    # 반대 신호 청산
                    if position == 1:
                        pnl = (current_price - entry_price) / entry_price * self.leverage * (1 - self.fee)
                    else:
                        pnl = (entry_price - current_price) / entry_price * self.leverage * (1 - self.fee)
                    
                    self.current_capital *= (1 + pnl)
                    
                    trades.append({
                        'type': 'OPPOSITE_SIGNAL',
                        'position': 'LONG' if position == 1 else 'SHORT',
                        'entry_time': entry_time,
                        'exit_time': current_time,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'position_size': position_size,
                        'pnl': pnl,
                        'return_pct': pnl * 100,
                        'hold_time_minutes': (current_time - entry_time).total_seconds() / 60
                    })
                    
                    print(f"🔄 반대 신호 청산: {current_time} | {position_size:.3f} | 수익률: {pnl*100:.2f}%")
                    
                    position = 0
                    continue
                
                # 손절/익절 체크
                if position == 1:  # 롱 포지션
                    if current_price <= stop_loss:
                        # 손절
                        pnl = (current_price - entry_price) / entry_price * self.leverage * (1 - self.fee)
                        self.current_capital *= (1 + pnl)
                        self.consecutive_losses += 1
                        
                        trades.append({
                            'type': 'STOP_LOSS',
                            'position': 'LONG',
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'position_size': position_size,
                            'pnl': pnl,
                            'return_pct': pnl * 100,
                            'hold_time_minutes': (current_time - entry_time).total_seconds() / 60
                        })
                        
                        print(f"🔴 롱 손절: {current_time} | 가격: {current_price:.0f} | 수익률: {pnl*100:.2f}% | 연속손실: {self.consecutive_losses}")
                        
                        position = 0
                        
                    elif current_price >= take_profit:
                        # 익절
                        pnl = (current_price - entry_price) / entry_price * self.leverage * (1 - self.fee)
                        self.current_capital *= (1 + pnl)
                        self.consecutive_losses = 0  # 연속 손실 리셋
                        
                        trades.append({
                            'type': 'TAKE_PROFIT',
                            'position': 'LONG',
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'position_size': position_size,
                            'pnl': pnl,
                            'return_pct': pnl * 100,
                            'hold_time_minutes': (current_time - entry_time).total_seconds() / 60
                        })
                        
                        print(f"🟢 롱 익절: {current_time} | 가격: {current_price:.0f} | 수익률: {pnl*100:.2f}%")
                        
                        position = 0
                
                elif position == -1:  # 숏 포지션
                    if current_price >= stop_loss:
                        # 손절
                        pnl = (entry_price - current_price) / entry_price * self.leverage * (1 - self.fee)
                        self.current_capital *= (1 + pnl)
                        self.consecutive_losses += 1
                        
                        trades.append({
                            'type': 'STOP_LOSS',
                            'position': 'SHORT',
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'position_size': position_size,
                            'pnl': pnl,
                            'return_pct': pnl * 100,
                            'hold_time_minutes': (current_time - entry_time).total_seconds() / 60
                        })
                        
                        print(f"🔴 숏 손절: {current_time} | 가격: {current_price:.0f} | 수익률: {pnl*100:.2f}% | 연속손실: {self.consecutive_losses}")
                        
                        position = 0
                        
                    elif current_price <= take_profit:
                        # 익절
                        pnl = (entry_price - current_price) / entry_price * self.leverage * (1 - self.fee)
                        self.current_capital *= (1 + pnl)
                        self.consecutive_losses = 0  # 연속 손실 리셋
                        
                        trades.append({
                            'type': 'TAKE_PROFIT',
                            'position': 'SHORT',
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'position_size': position_size,
                            'pnl': pnl,
                            'return_pct': pnl * 100,
                            'hold_time_minutes': (current_time - entry_time).total_seconds() / 60
                        })
                        
                        print(f"🟢 숏 익절: {current_time} | 가격: {current_price:.0f} | 수익률: {pnl*100:.2f}%")
                        
                        position = 0
            
            # 자산 곡선 기록
            equity_curve.append({
                'time': current_time,
                'equity': self.current_capital,
                'price': current_price,
                'position': position,
                'atr': atr
            })
        
        # 마지막 포지션 청산
        if position != 0:
            final_price = df['close'].iloc[-1]
            if position == 1:
                pnl = (final_price - entry_price) / entry_price * self.leverage * (1 - self.fee)
            else:
                pnl = (entry_price - final_price) / entry_price * self.leverage * (1 - self.fee)
            
            self.current_capital *= (1 + pnl)
            
            trades.append({
                'type': 'FINAL_EXIT',
                'position': 'LONG' if position == 1 else 'SHORT',
                'entry_time': entry_time,
                'exit_time': df.index[-1],
                'entry_price': entry_price,
                'exit_price': final_price,
                'position_size': position_size,
                'pnl': pnl,
                'return_pct': pnl * 100,
                'hold_time_minutes': (df.index[-1] - entry_time).total_seconds() / 60
            })
        
        # 성과 계산
        total_return = (self.current_capital - self.initial_capital) / self.initial_capital * 100
        
        # MDD 계산
        peak = self.initial_capital
        mdd = 0
        for point in equity_curve:
            if point['equity'] > peak:
                peak = point['equity']
            drawdown = (peak - point['equity']) / peak * 100
            if drawdown > mdd:
                mdd = drawdown
        
        # 거래 통계
        profitable_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] < 0]
        
        win_rate = len(profitable_trades) / len(trades) * 100 if trades else 0
        avg_profit = np.mean([t['pnl'] for t in profitable_trades]) * 100 if profitable_trades else 0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) * 100 if losing_trades else 0
        
        # 평균 보유 시간
        avg_hold_time = np.mean([t['hold_time_minutes'] for t in trades]) if trades else 0
        
        result = {
            'strategy': 'scalping',
            'total_return': total_return,
            'final_capital': self.current_capital,
            'mdd': mdd,
            'trades': trades,
            'equity_curve': equity_curve,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'total_trades': len(trades),
            'profitable_trades': len(profitable_trades),
            'losing_trades': len(losing_trades),
            'avg_hold_time_minutes': avg_hold_time,
            'consecutive_losses': self.consecutive_losses
        }
        
        return result
    
    def create_visualization(self, result: Dict, df: pd.DataFrame, save_path: str):
        """시각화 생성"""
        print("📊 시각화 생성 중...")
        
        fig, axes = plt.subplots(6, 1, figsize=(20, 24))
        
        # 1. 가격 차트 + 이동평균선 + 거래 신호
        ax1 = axes[0]
        ax1.plot(df.index, df['close'], 'k-', linewidth=0.5, alpha=0.8, label='BTC Price')
        ax1.plot(df.index, df['ma_5'], 'r-', linewidth=1, alpha=0.7, label='5MA')
        ax1.plot(df.index, df['ma_10'], 'b-', linewidth=1, alpha=0.7, label='10MA')
        
        # 거래 내역 표시
        for trade in result['trades']:
            if trade['position'] == 'LONG':
                ax1.scatter(trade['entry_time'], trade['entry_price'], color='green', marker='^', s=50, alpha=0.8)
                ax1.scatter(trade['exit_time'], trade['exit_price'], color='red', marker='v', s=50, alpha=0.8)
            else:
                ax1.scatter(trade['entry_time'], trade['entry_price'], color='red', marker='v', s=50, alpha=0.8)
                ax1.scatter(trade['exit_time'], trade['exit_price'], color='green', marker='^', s=50, alpha=0.8)
        
        ax1.set_title('스캘핑 전략 - 가격 차트 및 거래 신호', fontsize=14, fontweight='bold')
        ax1.set_ylabel('가격 (USDT)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. RSI
        ax2 = axes[1]
        ax2.plot(df.index, df['rsi'], 'b-', linewidth=1, alpha=0.8, label='RSI')
        ax2.axhline(y=50, color='black', linestyle='--', alpha=0.5)
        ax2.axhline(y=70, color='red', linestyle='--', alpha=0.5, label='과매수')
        ax2.axhline(y=30, color='green', linestyle='--', alpha=0.5, label='과매도')
        ax2.fill_between(df.index, 70, 100, alpha=0.1, color='red')
        ax2.fill_between(df.index, 0, 30, alpha=0.1, color='green')
        
        ax2.set_title('RSI 지표', fontsize=14, fontweight='bold')
        ax2.set_ylabel('RSI')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. 스토캐스틱
        ax3 = axes[2]
        ax3.plot(df.index, df['stoch_k'], 'b-', linewidth=1, alpha=0.8, label='%K')
        ax3.plot(df.index, df['stoch_d'], 'r-', linewidth=1, alpha=0.8, label='%D')
        ax3.axhline(y=50, color='black', linestyle='--', alpha=0.5)
        ax3.axhline(y=80, color='red', linestyle='--', alpha=0.5, label='과매수')
        ax3.axhline(y=20, color='green', linestyle='--', alpha=0.5, label='과매도')
        ax3.fill_between(df.index, 80, 100, alpha=0.1, color='red')
        ax3.fill_between(df.index, 0, 20, alpha=0.1, color='green')
        
        ax3.set_title('스토캐스틱 지표', fontsize=14, fontweight='bold')
        ax3.set_ylabel('스토캐스틱')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 4. 볼린저 밴드
        ax4 = axes[3]
        ax4.plot(df.index, df['close'], 'k-', linewidth=0.5, alpha=0.8, label='BTC Price')
        ax4.plot(df.index, df['bb_upper'], 'r--', linewidth=1, alpha=0.6, label='BB Upper')
        ax4.plot(df.index, df['bb_middle'], 'b-', linewidth=1, alpha=0.6, label='BB Middle')
        ax4.plot(df.index, df['bb_lower'], 'r--', linewidth=1, alpha=0.6, label='BB Lower')
        ax4.fill_between(df.index, df['bb_upper'], df['bb_lower'], alpha=0.1, color='blue')
        
        ax4.set_title('볼린저 밴드', fontsize=14, fontweight='bold')
        ax4.set_ylabel('가격 (USDT)')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        # 5. 자산 곡선
        ax5 = axes[4]
        times = [point['time'] for point in result['equity_curve']]
        equities = [point['equity'] for point in result['equity_curve']]
        
        ax5.plot(times, equities, 'b-', linewidth=2, label='자산 곡선')
        ax5.axhline(y=self.initial_capital, color='black', linestyle='--', alpha=0.7, label='초기 자본')
        
        ax5.set_title('자산 곡선', fontsize=14, fontweight='bold')
        ax5.set_ylabel('자산 (USDT)')
        ax5.legend()
        ax5.grid(True, alpha=0.3)
        
        # 6. MDD
        ax6 = axes[5]
        if result['equity_curve']:
            peak = self.initial_capital
            mdd_values = []
            
            for point in result['equity_curve']:
                if point['equity'] > peak:
                    peak = point['equity']
                drawdown = (peak - point['equity']) / peak * 100
                mdd_values.append(drawdown)
            
            ax6.fill_between(times, mdd_values, 0, alpha=0.3, color='red', label='MDD')
            ax6.plot(times, mdd_values, 'r-', linewidth=1, alpha=0.8)
            
            # 최대 MDD 표시
            max_mdd = max(mdd_values)
            max_mdd_idx = mdd_values.index(max_mdd)
            ax6.scatter(times[max_mdd_idx], max_mdd, color='darkred', s=100, zorder=5,
                       label=f'최대 MDD: {max_mdd:.2f}%')
        
        ax6.set_title('MDD (Maximum Drawdown)', fontsize=14, fontweight='bold')
        ax6.set_ylabel('MDD (%)')
        ax6.set_xlabel('시간')
        ax6.legend()
        ax6.grid(True, alpha=0.3)
        ax6.invert_yaxis()
        
        # x축 날짜 포맷
        for ax in axes:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
            ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ 시각화 저장 완료: {save_path}")

def main():
    """메인 함수"""
    print("🚀 비트코인 선물 스캘핑 전략 백테스트 시작!")
    print("=" * 60)
    
    try:
        # 백테스터 생성
        backtester = ScalpingStrategyBacktester(
            initial_capital=10000,
            leverage=20
        )
        
        # 데이터 로드
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        df = backtester.load_data(data_dir, '2024-01-01', '2024-12-31', '1m')
        
        # 기술적 지표 계산
        df = backtester.calculate_indicators(df)
        
        # 신호 생성
        df = backtester.generate_signals(df)
        
        # 백테스트 실행
        result = backtester.run_backtest(df)
        
        # 결과 출력
        print("\n" + "=" * 60)
        print("📈 스캘핑 전략 백테스트 결과")
        print("=" * 60)
        print(f"💰 최종 자본: {result['final_capital']:,.2f} USDT")
        print(f"📈 총 수익률: {result['total_return']:.2f}%")
        print(f"📉 최대 MDD: {result['mdd']:.2f}%")
        print(f"🔄 총 거래 수: {result['total_trades']}회")
        print(f"✅ 수익 거래: {result['profitable_trades']}회")
        print(f"❌ 손실 거래: {result['losing_trades']}회")
        print(f"🎯 승률: {result['win_rate']:.1f}%")
        print(f"📈 평균 수익: {result['avg_profit']:.2f}%")
        print(f"📉 평균 손실: {result['avg_loss']:.2f}%")
        print(f"⏰ 평균 보유 시간: {result['avg_hold_time_minutes']:.1f}분")
        print(f"🔄 연속 손실: {result['consecutive_losses']}회")
        
        # 결과 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = os.path.join(os.path.dirname(__file__), 'logs')
        os.makedirs(result_dir, exist_ok=True)
        
        # JSON 결과 저장
        result_file = os.path.join(result_dir, f"scalping_backtest_{timestamp}.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        # 시각화 저장
        graph_file = os.path.join(result_dir, f"scalping_backtest_{timestamp}.png")
        backtester.create_visualization(result, df, graph_file)
        
        print(f"\n💾 결과 저장 완료:")
        print(f"📄 JSON: {result_file}")
        print(f"📊 그래프: {graph_file}")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
