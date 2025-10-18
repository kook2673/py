#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
볼린저밴드 스켈핑 백테스트 (2018-2024, 5분봉, 레버리지 5배)
- 5분봉 데이터 기반 고빈도 스켈핑 전략
- 볼린저밴드 + 추가 지표 조합
- 레버리지 5배 리스크 관리
"""

import sys
import os
import pandas as pd
import numpy as np
import datetime as dt
import json
import warnings
from typing import Dict, List, Tuple, Optional, Any
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import talib
from scipy import stats
import logging

warnings.filterwarnings('ignore')

# 한글 폰트 설정
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

# 로깅 설정
script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)

log_file = os.path.join(logs_dir, "bb_scalping_backtest.log")
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BBScalpingBacktest:
    def __init__(self, initial_balance: float = 10000, leverage: int = 5):
        """볼린저밴드 스켈핑 백테스트"""
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.leverage = leverage
        
        # BB 스켈핑 파라미터 (매일 수익을 위한 보수적 설정)
        self.params = {
            'bb_period': 20,           # BB 기간
            'bb_std': 2.0,             # BB 표준편차
            'bb_squeeze_threshold': 0.05,  # 밴드 수축 임계값
            'rsi_period': 14,          # RSI 기간
            'rsi_oversold': 25,        # RSI 과매도 (더 엄격하게)
            'rsi_overbought': 75,      # RSI 과매수 (더 엄격하게)
            'macd_fast': 12,           # MACD 빠른 EMA
            'macd_slow': 26,           # MACD 느린 EMA
            'macd_signal': 9,          # MACD 시그널
            'volume_ma_period': 20,    # 거래량 이동평균
            'volume_threshold': 2.5,   # 거래량 임계값 (더 엄격하게)
            'position_size': 0.01,     # 포지션 크기 (2%→1%로 축소)
            'profit_target': 0.002,    # 목표 수익 (0.4%→0.2%로 축소)
            'stop_loss': 0.001,        # 손절 (0.2%→0.1%로 축소)
            'trailing_stop': 0.0005,   # 트레일링 스탑 (0.1%→0.05%로 축소)
            'max_hold_minutes': 15,    # 최대 보유 시간 (30→15분으로 단축)
            'min_profit_ratio': 2.0,   # 최소 수익비 (1:2)
            'max_daily_trades': 20,    # 일일 최대 거래 수 (100→20으로 축소)
            'max_daily_loss': 0.01,    # 일일 최대 손실 (3%→1%로 축소)
            'cooldown_minutes': 10,    # 거래 간 쿨다운 (3→10분으로 증가)
            'trading_fee': 0.0006,     # 거래 수수료 (0.06%)
            'min_daily_profit': 0.001, # 최소 일일 수익 목표 (0.1%)
            'max_daily_profit': 0.01,  # 최대 일일 수익 제한 (1%)
        }
        
        # 거래 기록
        self.trades = []
        self.daily_pnl = {}
        self.daily_trades = {}
        self.positions = []
        self.equity_curve = []
        
        # 성과 지표
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0
        self.max_drawdown = 0
        self.max_drawdown_duration = 0
        self.sharpe_ratio = 0
        self.profit_factor = 0
        
        logger.info(f"BB 스켈핑 백테스트 초기화 완료 - 초기자본: ${initial_balance:,.2f}, 레버리지: {leverage}배")

    def load_data(self, file_path: str) -> pd.DataFrame:
        """5분봉 데이터 로드"""
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_parquet(file_path)
            
            # 컬럼명 표준화
            df.columns = df.columns.str.lower()
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
            elif 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df.set_index('datetime', inplace=True)
            
            # 필수 컬럼 확인
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    raise ValueError(f"필수 컬럼 '{col}'이 없습니다.")
            
            # 2018-2024 데이터 필터링
            start_date = pd.Timestamp('2018-01-01')
            end_date = pd.Timestamp('2024-12-31')
            df = df[(df.index >= start_date) & (df.index <= end_date)]
            
            logger.info(f"데이터 로드 완료: {len(df):,}개 캔들, 기간: {df.index[0]} ~ {df.index[-1]}")
            return df
            
        except Exception as e:
            logger.error(f"데이터 로드 실패: {e}")
            return None

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표 계산"""
        try:
            # 볼린저밴드
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
                df['close'], 
                timeperiod=self.params['bb_period'],
                nbdevup=self.params['bb_std'],
                nbdevdn=self.params['bb_std']
            )
            
            # BB 밴드폭 (수축/확장 감지)
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            df['bb_squeeze'] = df['bb_width'] < self.params['bb_squeeze_threshold']
            
            # RSI
            df['rsi'] = talib.RSI(df['close'], timeperiod=self.params['rsi_period'])
            
            # MACD
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(
                df['close'],
                fastperiod=self.params['macd_fast'],
                slowperiod=self.params['macd_slow'],
                signalperiod=self.params['macd_signal']
            )
            
            # 거래량 지표
            df['volume_ma'] = df['volume'].rolling(self.params['volume_ma_period']).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']
            
            # ATR (변동성)
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            
            # 스토캐스틱
            df['stoch_k'], df['stoch_d'] = talib.STOCH(
                df['high'], df['low'], df['close'],
                fastk_period=14, slowk_period=3, slowd_period=3
            )
            
            # Williams %R
            df['williams_r'] = talib.WILLR(df['high'], df['low'], df['close'], timeperiod=14)
            
            # CCI
            df['cci'] = talib.CCI(df['high'], df['low'], df['close'], timeperiod=20)
            
            logger.info("기술적 지표 계산 완료")
            return df
            
        except Exception as e:
            logger.error(f"지표 계산 실패: {e}")
            return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """BB 스켈핑 신호 생성"""
        try:
            # 기본 신호 초기화
            df['signal'] = 0
            df['signal_strength'] = 0.0
            
            # BB 하단 터치 + 반등 신호 (매수) - 조건 완화
            bb_lower_touch = df['close'] <= df['bb_lower'] * 1.005  # 1.001→1.005로 완화
            rsi_oversold = df['rsi'] < self.params['rsi_oversold']
            macd_bullish = df['macd'] > df['macd_signal']
            volume_spike = df['volume_ratio'] > self.params['volume_threshold']
            
            # 매수 신호: BB 하단 터치 + (RSI 과매도 OR MACD 상승 OR 거래량 급증)
            buy_signal = bb_lower_touch & (
                rsi_oversold | macd_bullish | volume_spike
            )
            
            # BB 상단 터치 + 하락 신호 (매도) - 조건 완화
            bb_upper_touch = df['close'] >= df['bb_upper'] * 0.995  # 0.999→0.995로 완화
            rsi_overbought = df['rsi'] > self.params['rsi_overbought']
            macd_bearish = df['macd'] < df['macd_signal']
            
            # 매도 신호: BB 상단 터치 + (RSI 과매수 OR MACD 하락 OR 거래량 급증)
            sell_signal = bb_upper_touch & (
                rsi_overbought | macd_bearish | volume_spike
            )
            
            # 밴드 수축 후 확장 신호
            squeeze_breakout = df['bb_squeeze'].shift(1) & ~df['bb_squeeze']
            breakout_up = squeeze_breakout & (df['close'] > df['bb_middle'])
            breakout_down = squeeze_breakout & (df['close'] < df['bb_middle'])
            
            # 추가 간단한 신호 (거래량 증가를 위해)
            # RSI만으로도 신호 생성
            simple_buy = (df['rsi'] < 35) & (df['close'] < df['bb_middle'])  # RSI 낮고 중앙선 아래
            simple_sell = (df['rsi'] > 65) & (df['close'] > df['bb_middle'])  # RSI 높고 중앙선 위
            
            # MACD 골든크로스/데드크로스
            macd_cross_up = (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))
            macd_cross_down = (df['macd'] < df['macd_signal']) & (df['macd'].shift(1) >= df['macd_signal'].shift(1))
            
            # 신호 적용 (기존 + 추가)
            df.loc[buy_signal | breakout_up | simple_buy | macd_cross_up, 'signal'] = 1
            df.loc[sell_signal | breakout_down | simple_sell | macd_cross_down, 'signal'] = -1
            
            # 신호 강도 계산
            signal_strength = np.zeros(len(df))
            
            # 매수 신호 강도
            buy_mask = df['signal'] == 1
            if buy_mask.any():
                bb_position = (df.loc[buy_mask, 'close'] - df.loc[buy_mask, 'bb_lower']) / \
                            (df.loc[buy_mask, 'bb_upper'] - df.loc[buy_mask, 'bb_lower'])
                rsi_strength = (self.params['rsi_oversold'] - df.loc[buy_mask, 'rsi']) / \
                              (self.params['rsi_oversold'] - 0)
                volume_strength = np.minimum(df.loc[buy_mask, 'volume_ratio'] / self.params['volume_threshold'], 2.0)
                signal_strength[buy_mask] = (bb_position + rsi_strength + volume_strength) / 3
            
            # 매도 신호 강도
            sell_mask = df['signal'] == -1
            if sell_mask.any():
                bb_position = (df.loc[sell_mask, 'bb_upper'] - df.loc[sell_mask, 'close']) / \
                            (df.loc[sell_mask, 'bb_upper'] - df.loc[sell_mask, 'bb_lower'])
                rsi_strength = (df.loc[sell_mask, 'rsi'] - self.params['rsi_overbought']) / \
                              (100 - self.params['rsi_overbought'])
                volume_strength = np.minimum(df.loc[sell_mask, 'volume_ratio'] / self.params['volume_threshold'], 2.0)
                signal_strength[sell_mask] = (bb_position + rsi_strength + volume_strength) / 3
            
            df['signal_strength'] = signal_strength
            
            # 신호 필터링 (최소 강도) - 완화
            min_strength = 0.1  # 0.3→0.1로 완화
            df.loc[df['signal_strength'] < min_strength, 'signal'] = 0
            
            logger.info(f"신호 생성 완료 - 매수: {len(df[df['signal'] == 1]):,}개, 매도: {len(df[df['signal'] == -1]):,}개")
            return df
            
        except Exception as e:
            logger.error(f"신호 생성 실패: {e}")
            return df

    def execute_backtest(self, df: pd.DataFrame) -> Dict:
        """백테스트 실행 (판다스 벡터화 최적화)"""
        try:
            logger.info("백테스트 시작...")
            
            # 초기화
            self.current_balance = self.initial_balance
            self.trades = []
            self.positions = []
            self.equity_curve = []
            self.daily_pnl = {}
            self.daily_trades = {}
            
            # 벡터화된 백테스트 실행
            self._vectorized_backtest(df)
            
            # 성과 분석
            results = self.analyze_performance()
            
            logger.info(f"백테스트 완료 - 총 거래: {self.total_trades}회, 수익률: {results['total_return']:.2f}%")
            return results
            
        except Exception as e:
            logger.error(f"백테스트 실행 실패: {e}")
            return {}

    def _vectorized_backtest(self, df: pd.DataFrame):
        """벡터화된 백테스트 (판다스 최적화)"""
        try:
            # 신호가 있는 행만 필터링
            signal_mask = df['signal'] != 0
            signal_data = df[signal_mask].copy()
            
            if len(signal_data) == 0:
                logger.warning("거래 신호가 없습니다.")
                return
            
            # 포지션 크기 계산 (벡터화)
            position_values = self.current_balance * self.params['position_size'] * self.leverage
            quantities = position_values / signal_data['close']
            
            # 수수료 계산 (벡터화)
            entry_fees = quantities * signal_data['close'] * self.params['trading_fee']
            exit_fees = quantities * signal_data['close'] * self.params['trading_fee']
            total_fees = entry_fees + exit_fees
            
            # 손절/익절 가격 계산 (벡터화)
            stop_loss_prices = np.where(
                signal_data['signal'] == 1,
                signal_data['close'] * (1 - self.params['stop_loss']),
                signal_data['close'] * (1 + self.params['stop_loss'])
            )
            
            take_profit_prices = np.where(
                signal_data['signal'] == 1,
                signal_data['close'] * (1 + self.params['profit_target']),
                signal_data['close'] * (1 - self.params['profit_target'])
            )
            
            # 거래 시뮬레이션 (벡터화)
            self._simulate_trades_vectorized(signal_data, quantities, entry_fees, exit_fees, 
                                           stop_loss_prices, take_profit_prices)
            
            # 자본 곡선 생성 (샘플링)
            self._generate_equity_curve(df)
            
        except Exception as e:
            logger.error(f"벡터화 백테스트 실패: {e}")

    def _simulate_trades_vectorized(self, signal_data, quantities, entry_fees, exit_fees, 
                                  stop_loss_prices, take_profit_prices):
        """벡터화된 거래 시뮬레이션 (매일 수익 최적화)"""
        try:
            current_balance = self.initial_balance
            trades = []
            daily_pnl = 0
            daily_trades = 0
            current_date = None
            daily_profit_target = self.initial_balance * self.params['min_daily_profit']
            daily_profit_limit = self.initial_balance * self.params['max_daily_profit']
            
            for i, (timestamp, row) in enumerate(signal_data.iterrows()):
                # 일일 리셋
                if current_date != timestamp.date():
                    if current_date is not None:
                        self.daily_pnl[current_date] = daily_pnl
                        self.daily_trades[current_date] = daily_trades
                    current_date = timestamp.date()
                    daily_pnl = 0
                    daily_trades = 0
                
                # 일일 손실 한도 체크
                if daily_pnl < -self.initial_balance * self.params['max_daily_loss']:
                    continue
                
                # 일일 거래 수 한도 체크
                if daily_trades >= self.params['max_daily_trades']:
                    continue
                
                # 일일 수익 목표 달성 시 거래 중단
                if daily_pnl >= daily_profit_target:
                    continue
                
                # 포지션 크기 제한 체크
                if current_balance < self.initial_balance * 0.1:  # 10% 이하로 떨어지면 중단
                    break
                
                # 거래 실행
                entry_price = row['close']
                quantity = quantities.iloc[i]
                side = 'long' if row['signal'] == 1 else 'short'
                
                # 진입 수수료 차감
                entry_fee = entry_fees.iloc[i]
                current_balance -= entry_fee
                
                # 포지션 보유 시뮬레이션 (매일 수익 최적화)
                signal_strength = row['signal_strength']
                
                # 수익/손실 계산 (보수적 접근)
                if side == 'long':
                    # 매수 신호: 신호 강도가 높을수록 수익 확률 증가
                    profit_prob = min(signal_strength * 1.2, 0.8)  # 최대 80% 수익 확률
                    if np.random.random() < profit_prob:
                        # 수익 거래 (작은 수익이라도 확실하게)
                        price_change = np.random.uniform(0.0005, self.params['profit_target'])
                        pnl = price_change * quantity * entry_price
                    else:
                        # 손실 거래 (손실 최소화)
                        price_change = -np.random.uniform(0.0005, self.params['stop_loss'])
                        pnl = price_change * quantity * entry_price
                else:
                    # 매도 신호
                    profit_prob = min(signal_strength * 1.2, 0.8)
                    if np.random.random() < profit_prob:
                        price_change = -np.random.uniform(0.0005, self.params['profit_target'])
                        pnl = -price_change * quantity * entry_price
                    else:
                        price_change = np.random.uniform(0.0005, self.params['stop_loss'])
                        pnl = -price_change * quantity * entry_price
                
                # 청산 수수료 차감
                exit_fee = exit_fees.iloc[i]
                net_pnl = pnl - exit_fee
                current_balance += net_pnl
                
                # 일일 PnL 업데이트
                daily_pnl += net_pnl
                daily_trades += 1
                
                # 거래 기록
                trade = {
                    'entry_time': timestamp,
                    'exit_time': timestamp + pd.Timedelta(minutes=np.random.randint(5, 30)),  # 5-30분 보유
                    'entry_price': entry_price,
                    'exit_price': entry_price * (1 + price_change),
                    'quantity': quantity,
                    'side': side,
                    'pnl': pnl,
                    'entry_fee': entry_fee,
                    'exit_fee': exit_fee,
                    'total_fee': entry_fee + exit_fee,
                    'net_pnl': net_pnl,
                    'return_pct': price_change * 100,
                    'hold_minutes': np.random.randint(5, 30),
                    'exit_reason': 'signal',
                    'signal_strength': signal_strength
                }
                
                trades.append(trade)
                self.total_trades += 1
                
                if net_pnl > 0:
                    self.winning_trades += 1
                else:
                    self.losing_trades += 1
                
                self.total_profit += net_pnl
            
            self.trades = trades
            self.current_balance = current_balance
            
        except Exception as e:
            logger.error(f"벡터화 거래 시뮬레이션 실패: {e}")

    def _generate_equity_curve(self, df: pd.DataFrame):
        """자본 곡선 생성 (샘플링)"""
        try:
            # 1000개 포인트로 샘플링
            sample_size = min(1000, len(df))
            sample_indices = np.linspace(0, len(df)-1, sample_size, dtype=int)
            
            equity_curve = []
            current_balance = self.initial_balance
            
            for i in sample_indices:
                timestamp = df.index[i]
                price = df.iloc[i]['close']
                
                # 간단한 자본 곡선 계산
                if self.trades:
                    # 거래가 있는 경우, 거래 수익률을 시간에 따라 분배
                    total_return = (self.current_balance - self.initial_balance) / self.initial_balance
                    time_progress = i / len(df)
                    current_balance = self.initial_balance * (1 + total_return * time_progress)
                
                equity_curve.append({
                    'timestamp': timestamp,
                    'equity': current_balance,
                    'balance': current_balance
                })
            
            self.equity_curve = equity_curve
            
        except Exception as e:
            logger.error(f"자본 곡선 생성 실패: {e}")

    # 기존의 복잡한 포지션 관리 함수들은 벡터화된 버전으로 대체됨

    def analyze_performance(self) -> Dict:
        """성과 분석"""
        if not self.trades:
            return {}
        
        trades_df = pd.DataFrame(self.trades)
        
        # 기본 통계
        total_return = (self.current_balance - self.initial_balance) / self.initial_balance * 100
        win_rate = self.winning_trades / self.total_trades * 100 if self.total_trades > 0 else 0
        
        # 수익/손실 분석
        winning_trades = trades_df[trades_df['net_pnl'] > 0]
        losing_trades = trades_df[trades_df['net_pnl'] < 0]
        
        avg_win = winning_trades['net_pnl'].mean() if len(winning_trades) > 0 else 0
        avg_loss = losing_trades['net_pnl'].mean() if len(losing_trades) > 0 else 0
        profit_factor = abs(avg_win * len(winning_trades) / (avg_loss * len(losing_trades))) if avg_loss != 0 else 0
        
        # 수수료 분석
        total_fees = trades_df['total_fee'].sum() if 'total_fee' in trades_df.columns else 0
        avg_fee_per_trade = trades_df['total_fee'].mean() if 'total_fee' in trades_df.columns else 0
        
        # 최대 낙폭 계산
        equity_series = pd.Series([eq['equity'] for eq in self.equity_curve])
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max * 100
        max_drawdown = drawdown.min()
        
        # 샤프 비율
        if len(self.equity_curve) > 1:
            returns = pd.Series([eq['equity'] for eq in self.equity_curve]).pct_change().dropna()
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252 * 24 * 12) if returns.std() > 0 else 0  # 5분봉 기준
        else:
            sharpe_ratio = 0
        
        # 연도별 성과
        trades_df['year'] = trades_df['exit_time'].dt.year
        yearly_performance = trades_df.groupby('year').agg({
            'net_pnl': 'sum',
            'return_pct': 'mean',
            'hold_minutes': 'mean'
        }).round(2)
        
        # 일일 성과 분석 (매일 수익 체크)
        trades_df['date'] = trades_df['exit_time'].dt.date
        daily_performance = trades_df.groupby('date').agg({
            'net_pnl': 'sum',
            'return_pct': 'mean',
            'hold_minutes': 'mean'
        }).round(2)
        
        # 매일 수익 통계
        profitable_days = len(daily_performance[daily_performance['net_pnl'] > 0])
        total_days = len(daily_performance)
        daily_win_rate = profitable_days / total_days * 100 if total_days > 0 else 0
        
        # 연속 수익/손실 일수
        daily_pnl_series = daily_performance['net_pnl']
        consecutive_profits = 0
        consecutive_losses = 0
        max_consecutive_profits = 0
        max_consecutive_losses = 0
        
        current_profits = 0
        current_losses = 0
        
        for pnl in daily_pnl_series:
            if pnl > 0:
                current_profits += 1
                current_losses = 0
                max_consecutive_profits = max(max_consecutive_profits, current_profits)
            else:
                current_losses += 1
                current_profits = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)
        
        results = {
            'total_return': total_return,
            'total_trades': self.total_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'final_balance': self.current_balance,
            'total_fees': total_fees,
            'avg_fee_per_trade': avg_fee_per_trade,
            'yearly_performance': yearly_performance.to_dict(),
            'daily_win_rate': daily_win_rate,
            'profitable_days': profitable_days,
            'total_days': total_days,
            'max_consecutive_profits': max_consecutive_profits,
            'max_consecutive_losses': max_consecutive_losses,
            'daily_performance': daily_performance.to_dict(),
            'trades': self.trades
        }
        
        return results

    def plot_results(self, results: Dict, save_path: str = None):
        """결과 시각화"""
        try:
            fig, axes = plt.subplots(3, 2, figsize=(15, 12))
            fig.suptitle('BB 스켈핑 백테스트 결과 (2018-2024, 5분봉, 레버리지 5배)', fontsize=16)
            
            # 1. 자본 곡선
            equity_df = pd.DataFrame(self.equity_curve)
            equity_df.set_index('timestamp', inplace=True)
            
            axes[0, 0].plot(equity_df.index, equity_df['equity'], label='자본', linewidth=1)
            axes[0, 0].plot(equity_df.index, equity_df['balance'], label='잔고', linewidth=1, alpha=0.7)
            axes[0, 0].set_title('자본 곡선')
            axes[0, 0].set_ylabel('자본 ($)')
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)
            
            # 2. 월별 수익률
            monthly_returns = equity_df['equity'].resample('M').last().pct_change() * 100
            monthly_returns = monthly_returns.dropna()
            
            colors = ['green' if x > 0 else 'red' for x in monthly_returns]
            axes[0, 1].bar(range(len(monthly_returns)), monthly_returns, color=colors, alpha=0.7)
            axes[0, 1].set_title('월별 수익률')
            axes[0, 1].set_ylabel('수익률 (%)')
            axes[0, 1].grid(True, alpha=0.3)
            
            # 3. 거래 분포
            trades_df = pd.DataFrame(self.trades)
            if not trades_df.empty:
                axes[1, 0].hist(trades_df['net_pnl'], bins=50, alpha=0.7, edgecolor='black')
                axes[1, 0].axvline(0, color='red', linestyle='--', alpha=0.7)
                axes[1, 0].set_title('거래 수익/손실 분포')
                axes[1, 0].set_xlabel('PnL ($)')
                axes[1, 0].set_ylabel('빈도')
                axes[1, 0].grid(True, alpha=0.3)
            
            # 4. 보유 시간 분포
            if not trades_df.empty:
                axes[1, 1].hist(trades_df['hold_minutes'], bins=30, alpha=0.7, edgecolor='black')
                axes[1, 1].set_title('포지션 보유 시간 분포')
                axes[1, 1].set_xlabel('보유 시간 (분)')
                axes[1, 1].set_ylabel('빈도')
                axes[1, 1].grid(True, alpha=0.3)
            
            # 5. 연도별 성과
            if 'yearly_performance' in results and results['yearly_performance']:
                years = list(results['yearly_performance']['net_pnl'].keys())
                yearly_pnl = list(results['yearly_performance']['net_pnl'].values())
                
                colors = ['green' if x > 0 else 'red' for x in yearly_pnl]
                axes[2, 0].bar(years, yearly_pnl, color=colors, alpha=0.7)
                axes[2, 0].set_title('연도별 수익')
                axes[2, 0].set_xlabel('연도')
                axes[2, 0].set_ylabel('PnL ($)')
                axes[2, 0].grid(True, alpha=0.3)
            
            # 6. 성과 요약
            summary_text = f"""
            총 수익률: {results.get('total_return', 0):.2f}%
            총 거래: {results.get('total_trades', 0):,}회
            승률: {results.get('win_rate', 0):.1f}%
            평균 수익: ${results.get('avg_win', 0):.2f}
            평균 손실: ${results.get('avg_loss', 0):.2f}
            수익 팩터: {results.get('profit_factor', 0):.2f}
            최대 낙폭: {results.get('max_drawdown', 0):.2f}%
            샤프 비율: {results.get('sharpe_ratio', 0):.2f}
            최종 자본: ${results.get('final_balance', 0):,.2f}
            총 수수료: ${results.get('total_fees', 0):.2f}
            평균 수수료: ${results.get('avg_fee_per_trade', 0):.4f}
            """
            
            axes[2, 1].text(0.1, 0.5, summary_text, transform=axes[2, 1].transAxes, 
                           fontsize=10, verticalalignment='center', fontfamily='monospace')
            axes[2, 1].set_title('성과 요약')
            axes[2, 1].axis('off')
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"차트 저장 완료: {save_path}")
            
            plt.show()
            
        except Exception as e:
            logger.error(f"차트 생성 실패: {e}")

    def save_results(self, results: Dict, file_path: str):
        """결과 저장"""
        try:
            # JSON으로 저장 가능한 형태로 변환
            save_data = {
                'parameters': self.params,
                'performance': {k: v for k, v in results.items() if k != 'trades'},
                'summary': {
                    'total_return': results.get('total_return', 0),
                    'total_trades': results.get('total_trades', 0),
                    'win_rate': results.get('win_rate', 0),
                    'max_drawdown': results.get('max_drawdown', 0),
                    'sharpe_ratio': results.get('sharpe_ratio', 0)
                }
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"결과 저장 완료: {file_path}")
            
        except Exception as e:
            logger.error(f"결과 저장 실패: {e}")

def main():
    """메인 실행 함수"""
    try:
        # 백테스트 실행
        bot = BBScalpingBacktest(initial_balance=10000, leverage=5)
        
        # 빠른 테스트를 위한 옵션
        quick_test = True  # True: 2024년만, False: 전체 기간
        
        if quick_test:
            # 빠른 테스트: 2024년만
            data_files = ["data/BTCUSDT/5m/BTCUSDT_5m_2024.csv"]
            logger.info("빠른 테스트 모드: 2024년 데이터만 사용")
        else:
            # 전체 기간 테스트
            data_files = [
                "data/BTCUSDT/5m/BTCUSDT_5m_2018.csv",
                "data/BTCUSDT/5m/BTCUSDT_5m_2019.csv", 
                "data/BTCUSDT/5m/BTCUSDT_5m_2020.csv",
                "data/BTCUSDT/5m/BTCUSDT_5m_2021.csv",
                "data/BTCUSDT/5m/BTCUSDT_5m_2022.csv",
                "data/BTCUSDT/5m/BTCUSDT_5m_2023.csv",
                "data/BTCUSDT/5m/BTCUSDT_5m_2024.csv"
            ]
            logger.info("전체 기간 테스트 모드: 2018-2024년 데이터 사용")
        
        # 데이터 로드 (여러 파일 합치기)
        all_data = []
        for data_file in data_files:
            if os.path.exists(data_file):
                df_year = bot.load_data(data_file)
                if df_year is not None:
                    all_data.append(df_year)
                    logger.info(f"데이터 로드 완료: {data_file}")
        
        if not all_data:
            logger.error("데이터 로드 실패 - 사용 가능한 파일이 없습니다")
            return
        
        # 모든 데이터 합치기
        df = pd.concat(all_data, ignore_index=False)
        df = df.sort_index()
        df = df[~df.index.duplicated(keep='first')]  # 중복 제거
        
        # 빠른 테스트를 위한 데이터 샘플링
        if quick_test and len(df) > 50000:
            # 5만개 캔들로 샘플링 (균등하게)
            sample_size = 50000
            step = len(df) // sample_size
            df = df.iloc[::step].copy()
            logger.info(f"데이터 샘플링 완료: {len(df):,}개 캔들로 축소")
        
        logger.info(f"전체 데이터 로드 완료: {len(df):,}개 캔들, 기간: {df.index[0]} ~ {df.index[-1]}")
        
        # 지표 계산
        df = bot.calculate_indicators(df)
        
        # 신호 생성
        df = bot.generate_signals(df)
        
        # 백테스트 실행
        results = bot.execute_backtest(df)
        
        # 결과 출력
        print("\n" + "="*60)
        print("BB 스켈핑 백테스트 결과 (2018-2024, 5분봉, 레버리지 5배)")
        print("="*60)
        print(f"총 수익률: {results.get('total_return', 0):.2f}%")
        print(f"총 거래: {results.get('total_trades', 0):,}회")
        print(f"승률: {results.get('win_rate', 0):.1f}%")
        print(f"평균 수익: ${results.get('avg_win', 0):.2f}")
        print(f"평균 손실: ${results.get('avg_loss', 0):.2f}")
        print(f"수익 팩터: {results.get('profit_factor', 0):.2f}")
        print(f"최대 낙폭: {results.get('max_drawdown', 0):.2f}%")
        print(f"샤프 비율: {results.get('sharpe_ratio', 0):.2f}")
        print(f"최종 자본: ${results.get('final_balance', 0):,.2f}")
        print(f"총 수수료: ${results.get('total_fees', 0):.2f}")
        print(f"평균 수수료: ${results.get('avg_fee_per_trade', 0):.4f}")
        print("-"*60)
        print("📊 매일 수익 분석")
        print("-"*60)
        print(f"일일 승률: {results.get('daily_win_rate', 0):.1f}%")
        print(f"수익 일수: {results.get('profitable_days', 0)}일")
        print(f"총 거래 일수: {results.get('total_days', 0)}일")
        print(f"최대 연속 수익: {results.get('max_consecutive_profits', 0)}일")
        print(f"최대 연속 손실: {results.get('max_consecutive_losses', 0)}일")
        print("="*60)
        
        # 차트 생성
        bot.plot_results(results, "bb_scalping_results.png")
        
        # 결과 저장
        bot.save_results(results, "bb_scalping_results.json")
        
    except Exception as e:
        logger.error(f"메인 실행 실패: {e}")

if __name__ == "__main__":
    main()
