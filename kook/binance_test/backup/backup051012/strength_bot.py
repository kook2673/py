#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
비트코인 선물 강도 기반 추세추종 전략

개요:
- ETF 강도 전략을 비트코인 선물에 적용
- 강한 상승 시 롱, 강한 하락 시 숏 (추세 추종)
- ATR 기반 트레일링 스탑으로 리스크 관리
- 동적 포지션 사이징 (승리시 감소, 패배시 증가)

규칙:
- 규칙1: 미래데이터를 사용하지 않는다
- 규칙2: 랜덤데이터를 사용하지 않고 과거 csv파일을 로드해서 사용한다
- 규칙3: 살때 0.05%수수료, 팔때 0.05%수수료를 꼭 적용해야 한다
- 규칙4: 트레일링 스탑 포함을 한다
- 규칙5: 이겼을때 self.position_size = 0.1배, 졌을때 self.position_size = 0.2배로 한다
- 규칙6: 백테스트 다 돌리고 비트코인가격 그래프와 수익률 그래프를 보여준다

특징 지표:
- pct = 종가 수익률, vol_ratio = 거래량/20일 평균, close_to_range = (종가-저가)/(고가-저가)
- 강상승: pct>=up_pct & close_to_range>=up_ctr & vol_ratio>=up_vol
- 강하락: pct<=-down_pct & close_to_range<=(1-down_ctr) & vol_ratio>=down_vol
"""

import os
import sys
import pandas as pd
import numpy as np
import logging
import datetime as dt
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class BTCFuturesStrengthStrategy:
    """비트코인 선물 강도 기반 추세추종 전략"""
    
    def __init__(self, 
                 initial_capital: float = 10000,
                 leverage: int = 1,              # 규칙에 따라 1배로 제한
                 up_pct: float = 0.01,           # +1% 이상 (더 민감하게)
                 up_ctr: float = 0.6,            # 상단 근접도 0.6 이상 (완화)
                 up_vol: float = 1.2,            # 거래량 배수 1.2배 이상 (완화)
                 down_pct: float = 0.01,         # -1% 이상 하락 (더 민감하게)
                 down_ctr: float = 0.6,          # 하단 근접 기준(1-down_ctr 이하) (완화)
                 down_vol: float = 1.2,          # 거래량 배수 1.2배 이상 (완화)
                 atr_mult: float = 2.0,          # ATR 트레일링 스탑 승수
                 commission_rate: float = 0.0005, # 규칙3: 0.05% 수수료
                 position_fraction: float = 0.8,  # 자본 중 투자 비율
                 dynamic_sizing: bool = True,     # 동적 포지션 사이징
                 win_multiplier: float = 0.1,     # 규칙5: 승리시 0.1배
                 loss_multiplier: float = 0.2):   # 규칙5: 패배시 0.2배
        
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.leverage = leverage
        self.commission_rate = commission_rate
        self.position_fraction = position_fraction
        
        # 강도 지표 파라미터
        self.up_pct = up_pct
        self.up_ctr = up_ctr
        self.up_vol = up_vol
        self.down_pct = down_pct
        self.down_ctr = down_ctr
        self.down_vol = down_vol
        
        # 리스크 관리
        self.atr_mult = atr_mult
        self.dynamic_sizing = dynamic_sizing
        self.win_multiplier = win_multiplier
        self.loss_multiplier = loss_multiplier
        
        # 포지션 관리
        self.position = None  # {'side': 'long'|'short', 'qty': float, 'entry_price': float, 'highest_price': float, 'lowest_price': float}
        self.trades = []
        self.equity_curve = []
        
        # 동적 포지션 사이징을 위한 변수들 (규칙5)
        self.position_size = self.win_multiplier  # 현재 포지션 사이즈 (0.1배로 시작)
        self.last_trade_result = None  # 마지막 거래 결과 ('win' or 'loss')
        self.consecutive_wins = 0      # 연속 승리 횟수
        self.consecutive_losses = 0    # 연속 패배 횟수
        
        # 통계
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.max_drawdown = 0
        self.peak_capital = initial_capital
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표 계산"""
        df = df.copy()
        
        # 기본 지표
        df['pct'] = df['close'].pct_change()
        
        # 가격 위치 (고가-저가 범위 내 위치)
        price_range = (df['high'] - df['low']).replace(0, np.nan)
        df['close_to_range'] = ((df['close'] - df['low']) / price_range).clip(0, 1)
        
        # 거래량 비율
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma20']
        
        # ATR (변동성 기반 손절)
        df['atr'] = self._calculate_atr(df['high'], df['low'], df['close'], timeperiod=14)
        
        # 이동평균선 (추가 확인용)
        df['ma_20'] = df['close'].rolling(20).mean()
        df['ma_50'] = df['close'].rolling(50).mean()
        
        return df
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, timeperiod: int = 14):
        """ATR (Average True Range) 계산"""
        # True Range 계산
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR 계산 (지수이동평균)
        atr = true_range.ewm(span=timeperiod).mean()
        
        return atr
    
    def generate_signal(self, df: pd.DataFrame, current_idx: int) -> Dict:
        """강도 기반 신호 생성"""
        if current_idx < 20:  # 충분한 데이터 확보
            return {'action': 'hold', 'confidence': 0}
        
        current_data = df.iloc[:current_idx+1]
        current_price = current_data['close'].iloc[-1]
        current_atr = current_data['atr'].iloc[-1]
        
        # 강도 지표 계산
        pct = current_data['pct'].iloc[-1]
        close_to_range = current_data['close_to_range'].iloc[-1]
        vol_ratio = current_data['vol_ratio'].iloc[-1]
        
        # 강상승 신호
        up_signal = (pct >= self.up_pct) and (close_to_range >= self.up_ctr) and (vol_ratio >= self.up_vol)
        
        # 강하락 신호
        down_signal = (pct <= -self.down_pct) and (close_to_range <= (1 - self.down_ctr)) and (vol_ratio >= self.down_vol)
        
        if up_signal:
            return {
                'action': 'buy',
                'confidence': 0.8,
                'target_price': current_price * (1 + self.up_pct * 2),  # 2배 수익 목표
                'stop_loss': current_price - (current_atr * self.atr_mult)
            }
        elif down_signal:
            return {
                'action': 'sell',
                'confidence': 0.8,
                'target_price': current_price * (1 - self.down_pct * 2),  # 2배 수익 목표
                'stop_loss': current_price + (current_atr * self.atr_mult)
            }
        
        return {'action': 'hold', 'confidence': 0}
    
    def open_position(self, side: str, price: float, timestamp: dt.datetime, signal: Dict):
        """포지션 오픈 (규칙3: 0.05% 수수료 적용)"""
        # 포지션 크기 계산 (규칙5: 동적 포지션 사이징)
        position_value = self.current_capital * self.position_size * self.leverage
        qty = position_value / price
        
        # 매수 수수료 계산 및 적용 (규칙3: 0.05%)
        buy_commission = position_value * self.commission_rate
        self.current_capital -= buy_commission
        
        # 포지션 생성
        self.position = {
            'side': side,
            'qty': qty,
            'entry_price': price,
            'highest_price': price if side == 'long' else price,
            'lowest_price': price if side == 'short' else price,
            'timestamp': timestamp,
            'target_price': signal['target_price'],
            'stop_loss': signal['stop_loss'],
            'buy_commission': buy_commission
        }
        
        self.total_trades += 1
        
        logger.info(f"포지션 오픈: {side} {qty:.4f} @ {price:.2f} (수수료: {buy_commission:.2f} USDT, 포지션사이즈: {self.position_size:.1%})")
    
    def close_position(self, price: float, reason: str):
        """포지션 청산 (규칙3: 0.05% 수수료 적용, 규칙5: 동적 포지션 사이징)"""
        if not self.position:
            return
        
        # 손익 계산
        if self.position['side'] == 'long':
            pnl = (price - self.position['entry_price']) * self.position['qty']
        else:  # short
            pnl = (self.position['entry_price'] - price) * self.position['qty']
        
        # 매도 수수료 계산 및 적용 (규칙3: 0.05%)
        sell_value = price * self.position['qty']
        sell_commission = sell_value * self.commission_rate
        total_commission = self.position['buy_commission'] + sell_commission
        
        # 순손익 계산
        net_pnl = pnl - total_commission
        
        # 자본 업데이트
        self.current_capital += net_pnl
        
        # 거래 기록
        trade_record = {
            'timestamp': self.position['timestamp'],
            'side': self.position['side'],
            'entry_price': self.position['entry_price'],
            'exit_price': price,
            'qty': self.position['qty'],
            'pnl': pnl,
            'net_pnl': net_pnl,
            'total_commission': total_commission,
            'reason': reason
        }
        
        self.trades.append(trade_record)
        
        # 거래 결과 추적 및 포지션 사이즈 조정 (규칙5)
        if net_pnl > 0:
            self.last_trade_result = 'win'
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            self.winning_trades += 1
            # 규칙5: 이겼을때 0.1배
            self.position_size = self.win_multiplier
            logger.info(f"승리! 포지션 사이즈를 {self.position_size:.1%}로 조정")
        else:
            self.last_trade_result = 'loss'
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            self.losing_trades += 1
            # 규칙5: 졌을때 0.2배
            self.position_size = self.loss_multiplier
            logger.info(f"패배! 포지션 사이즈를 {self.position_size:.1%}로 조정")
        
        logger.info(f"포지션 청산: {self.position['side']} {self.position['qty']:.4f} @ {price:.2f}, PnL: {pnl:.2f} USDT, 순손익: {net_pnl:.2f} USDT, 이유: {reason}")
        
        # 포지션 초기화
        self.position = None
    
    def check_exit_conditions(self, current_price: float, current_atr: float) -> Optional[str]:
        """청산 조건 체크 (규칙4: 트레일링 스탑 포함)"""
        if not self.position:
            return None
        
        if self.position['side'] == 'long':
            # 최고가 업데이트
            if current_price > self.position['highest_price']:
                self.position['highest_price'] = current_price
            
            # ATR 트레일링 스탑 (규칙4)
            trailing_stop = self.position['highest_price'] - (current_atr * self.atr_mult)
            if current_price <= trailing_stop:
                return 'trailing_stop'
            
            # 익절
            if current_price >= self.position['target_price']:
                return 'take_profit'
            
            # 손절
            if current_price <= self.position['stop_loss']:
                return 'stop_loss'
        
        else:  # short
            # 최저가 업데이트
            if current_price < self.position['lowest_price']:
                self.position['lowest_price'] = current_price
            
            # ATR 트레일링 스탑 (규칙4)
            trailing_stop = self.position['lowest_price'] + (current_atr * self.atr_mult)
            if current_price >= trailing_stop:
                return 'trailing_stop'
            
            # 익절
            if current_price <= self.position['target_price']:
                return 'take_profit'
            
            # 손절
            if current_price >= self.position['stop_loss']:
                return 'stop_loss'
        
        return None
    
    def run_backtest_vectorized(self, df: pd.DataFrame, start_date: str = None, end_date: str = None) -> Dict:
        """벡터화된 백테스트 실행 (규칙1: 미래데이터 사용 안함, 규칙2: CSV 파일 사용)"""
        logger.info("비트코인 선물 강도 전략 벡터화 백테스트 시작...")
        
        # 날짜 필터링
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        # 기술적 지표 계산
        df = self.calculate_technical_indicators(df)
        
        # 벡터화된 신호 생성
        signals = self._generate_signals_vectorized(df)
        
        # 벡터화된 백테스트 실행
        results = self._run_vectorized_backtest(df, signals)
        
        return results
    
    def _generate_signals_vectorized(self, df: pd.DataFrame) -> pd.DataFrame:
        """벡터화된 신호 생성"""
        df_signals = df.copy()
        
        # 강상승 신호 (벡터화)
        up_signal = (
            (df_signals['pct'] >= self.up_pct) & 
            (df_signals['close_to_range'] >= self.up_ctr) & 
            (df_signals['vol_ratio'] >= self.up_vol)
        )
        
        # 강하락 신호 (벡터화)
        down_signal = (
            (df_signals['pct'] <= -self.down_pct) & 
            (df_signals['close_to_range'] <= (1 - self.down_ctr)) & 
            (df_signals['vol_ratio'] >= self.down_vol)
        )
        
        # 신호 컬럼 생성
        df_signals['signal'] = 0
        df_signals.loc[up_signal, 'signal'] = 1  # 매수
        df_signals.loc[down_signal, 'signal'] = -1  # 매도
        
        # 목표가와 손절가 계산
        df_signals['target_price'] = np.nan
        df_signals['stop_loss'] = np.nan
        
        # 매수 신호의 목표가와 손절가
        buy_mask = df_signals['signal'] == 1
        df_signals.loc[buy_mask, 'target_price'] = df_signals.loc[buy_mask, 'close'] * (1 + self.up_pct * 2)
        df_signals.loc[buy_mask, 'stop_loss'] = df_signals.loc[buy_mask, 'close'] - (df_signals.loc[buy_mask, 'atr'] * self.atr_mult)
        
        # 매도 신호의 목표가와 손절가
        sell_mask = df_signals['signal'] == -1
        df_signals.loc[sell_mask, 'target_price'] = df_signals.loc[sell_mask, 'close'] * (1 - self.down_pct * 2)
        df_signals.loc[sell_mask, 'stop_loss'] = df_signals.loc[sell_mask, 'close'] + (df_signals.loc[sell_mask, 'atr'] * self.atr_mult)
        
        return df_signals
    
    def _run_vectorized_backtest(self, df: pd.DataFrame, signals_df: pd.DataFrame) -> Dict:
        """벡터화된 백테스트 실행"""
        # 초기화
        current_capital = self.initial_capital
        position_size = self.win_multiplier
        position = None
        trades = []
        equity_curve = []
        
        # 통계 변수
        total_trades = 0
        winning_trades = 0
        losing_trades = 0
        max_drawdown = 0
        peak_capital = self.initial_capital
        
        # 포지션 추적을 위한 배열
        position_side = np.zeros(len(df), dtype=int)  # 0: 없음, 1: 롱, -1: 숏
        position_qty = np.zeros(len(df))
        position_entry_price = np.zeros(len(df))
        position_highest_price = np.zeros(len(df))
        position_lowest_price = np.zeros(len(df))
        position_target_price = np.zeros(len(df))
        position_stop_loss = np.zeros(len(df))
        
        # 자본 곡선
        equity_values = np.zeros(len(df))
        
        # 벡터화된 백테스트 루프
        for i in range(20, len(df)):  # 충분한 데이터 확보를 위해 20부터 시작
            current_price = df['close'].iloc[i]
            current_atr = df['atr'].iloc[i]
            current_time = df.index[i]
            
            # 현재 포지션 상태
            if i > 0:
                current_position_side = position_side[i-1]
                current_position_qty = position_qty[i-1]
                current_position_entry_price = position_entry_price[i-1]
                current_position_highest_price = position_highest_price[i-1]
                current_position_lowest_price = position_lowest_price[i-1]
                current_position_target_price = position_target_price[i-1]
                current_position_stop_loss = position_stop_loss[i-1]
            else:
                current_position_side = 0
                current_position_qty = 0
                current_position_entry_price = 0
                current_position_highest_price = 0
                current_position_lowest_price = 0
                current_position_target_price = 0
                current_position_stop_loss = 0
            
            # 청산 조건 체크 (벡터화)
            exit_reason = None
            if current_position_side != 0:
                if current_position_side == 1:  # 롱 포지션
                    # 최고가 업데이트
                    if current_price > current_position_highest_price:
                        current_position_highest_price = current_price
                    
                    # ATR 트레일링 스탑
                    trailing_stop = current_position_highest_price - (current_atr * self.atr_mult)
                    if current_price <= trailing_stop:
                        exit_reason = 'trailing_stop'
                    # 익절
                    elif current_price >= current_position_target_price:
                        exit_reason = 'take_profit'
                    # 손절
                    elif current_price <= current_position_stop_loss:
                        exit_reason = 'stop_loss'
                
                else:  # 숏 포지션
                    # 최저가 업데이트
                    if current_price < current_position_lowest_price:
                        current_position_lowest_price = current_price
                    
                    # ATR 트레일링 스탑
                    trailing_stop = current_position_lowest_price + (current_atr * self.atr_mult)
                    if current_price >= trailing_stop:
                        exit_reason = 'trailing_stop'
                    # 익절
                    elif current_price <= current_position_target_price:
                        exit_reason = 'take_profit'
                    # 손절
                    elif current_price >= current_position_stop_loss:
                        exit_reason = 'stop_loss'
                
                # 포지션 청산
                if exit_reason:
                    # 손익 계산
                    if current_position_side == 1:
                        pnl = (current_price - current_position_entry_price) * current_position_qty
                    else:
                        pnl = (current_position_entry_price - current_price) * current_position_qty
                    
                    # 수수료 계산
                    position_value = current_position_entry_price * current_position_qty
                    buy_commission = position_value * self.commission_rate
                    sell_value = current_price * current_position_qty
                    sell_commission = sell_value * self.commission_rate
                    total_commission = buy_commission + sell_commission
                    
                    # 순손익 계산
                    net_pnl = pnl - total_commission
                    current_capital += net_pnl
                    
                    # 거래 기록
                    trade_record = {
                        'timestamp': current_time,
                        'side': 'long' if current_position_side == 1 else 'short',
                        'entry_price': current_position_entry_price,
                        'exit_price': current_price,
                        'qty': current_position_qty,
                        'pnl': pnl,
                        'net_pnl': net_pnl,
                        'total_commission': total_commission,
                        'reason': exit_reason
                    }
                    trades.append(trade_record)
                    
                    # 포지션 사이즈 조정 (규칙5)
                    if net_pnl > 0:
                        winning_trades += 1
                        position_size = self.win_multiplier  # 0.1배
                    else:
                        losing_trades += 1
                        position_size = self.loss_multiplier  # 0.2배
                    
                    total_trades += 1
                    
                    # 포지션 초기화
                    current_position_side = 0
                    current_position_qty = 0
                    current_position_entry_price = 0
                    current_position_highest_price = 0
                    current_position_lowest_price = 0
                    current_position_target_price = 0
                    current_position_stop_loss = 0
            
            # 새로운 신호 생성 (최대 1개 포지션)
            if current_position_side == 0:
                signal = signals_df['signal'].iloc[i]
                
                if signal == 1:  # 매수
                    # 포지션 크기 계산
                    position_value = current_capital * position_size * self.leverage
                    qty = position_value / current_price
                    
                    # 수수료 계산
                    buy_commission = position_value * self.commission_rate
                    current_capital -= buy_commission
                    
                    # 포지션 설정
                    current_position_side = 1
                    current_position_qty = qty
                    current_position_entry_price = current_price
                    current_position_highest_price = current_price
                    current_position_lowest_price = current_price
                    current_position_target_price = signals_df['target_price'].iloc[i]
                    current_position_stop_loss = signals_df['stop_loss'].iloc[i]
                    
                elif signal == -1:  # 매도
                    # 포지션 크기 계산
                    position_value = current_capital * position_size * self.leverage
                    qty = position_value / current_price
                    
                    # 수수료 계산
                    buy_commission = position_value * self.commission_rate
                    current_capital -= buy_commission
                    
                    # 포지션 설정
                    current_position_side = -1
                    current_position_qty = qty
                    current_position_entry_price = current_price
                    current_position_highest_price = current_price
                    current_position_lowest_price = current_price
                    current_position_target_price = signals_df['target_price'].iloc[i]
                    current_position_stop_loss = signals_df['stop_loss'].iloc[i]
            
            # 포지션 상태 업데이트
            position_side[i] = current_position_side
            position_qty[i] = current_position_qty
            position_entry_price[i] = current_position_entry_price
            position_highest_price[i] = current_position_highest_price
            position_lowest_price[i] = current_position_lowest_price
            position_target_price[i] = current_position_target_price
            position_stop_loss[i] = current_position_stop_loss
            
            # 자본 곡선 업데이트
            if current_position_side != 0:
                if current_position_side == 1:
                    unrealized_pnl = (current_price - current_position_entry_price) * current_position_qty
                else:
                    unrealized_pnl = (current_position_entry_price - current_price) * current_position_qty
                current_equity = current_capital + unrealized_pnl
            else:
                current_equity = current_capital
            
            equity_values[i] = current_equity
            
            # 최대 낙폭 계산
            if current_equity > peak_capital:
                peak_capital = current_equity
            
            drawdown = (peak_capital - current_equity) / peak_capital * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        # 최종 포지션 청산
        if position_side[-1] != 0:
            final_price = df['close'].iloc[-1]
            final_position_side = position_side[-1]
            final_position_qty = position_qty[-1]
            final_position_entry_price = position_entry_price[-1]
            
            # 손익 계산
            if final_position_side == 1:
                pnl = (final_price - final_position_entry_price) * final_position_qty
            else:
                pnl = (final_position_entry_price - final_price) * final_position_qty
            
            # 수수료 계산
            position_value = final_position_entry_price * final_position_qty
            buy_commission = position_value * self.commission_rate
            sell_value = final_price * final_position_qty
            sell_commission = sell_value * self.commission_rate
            total_commission = buy_commission + sell_commission
            
            # 순손익 계산
            net_pnl = pnl - total_commission
            current_capital += net_pnl
            
            # 거래 기록
            trade_record = {
                'timestamp': df.index[-1],
                'side': 'long' if final_position_side == 1 else 'short',
                'entry_price': final_position_entry_price,
                'exit_price': final_price,
                'qty': final_position_qty,
                'pnl': pnl,
                'net_pnl': net_pnl,
                'total_commission': total_commission,
                'reason': 'end_of_data'
            }
            trades.append(trade_record)
            
            # 포지션 사이즈 조정
            if net_pnl > 0:
                winning_trades += 1
            else:
                losing_trades += 1
            
            total_trades += 1
        
        # 결과 계산
        total_pnl = current_capital - self.initial_capital
        total_return = (total_pnl / self.initial_capital) * 100
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        # 평균 수익/손실
        winning_trade_pnls = [t['net_pnl'] for t in trades if t['net_pnl'] > 0]
        losing_trade_pnls = [t['net_pnl'] for t in trades if t['net_pnl'] < 0]
        
        avg_win = np.mean(winning_trade_pnls) if winning_trade_pnls else 0
        avg_loss = np.mean(losing_trade_pnls) if losing_trade_pnls else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        
        return {
            "initial_capital": self.initial_capital,
            "final_capital": current_capital,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "trades": trades,
            "equity_curve": equity_values[20:].tolist()  # 20부터 시작한 부분만
        }
    
    def run_backtest(self, df: pd.DataFrame, start_date: str = None, end_date: str = None) -> Dict:
        """백테스트 실행 (벡터화 버전 사용)"""
        return self.run_backtest_vectorized(df, start_date, end_date)
    
    def calculate_results(self) -> Dict:
        """백테스트 결과 계산"""
        if not self.trades:
            return {"error": "거래 기록이 없습니다."}
        
        total_pnl = self.current_capital - self.initial_capital
        total_return = (total_pnl / self.initial_capital) * 100
        
        win_rate = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        
        # 평균 수익/손실
        winning_trades = [t['net_pnl'] for t in self.trades if t['net_pnl'] > 0]
        losing_trades = [t['net_pnl'] for t in self.trades if t['net_pnl'] < 0]
        
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = np.mean(losing_trades) if losing_trades else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        
        return {
            "initial_capital": self.initial_capital,
            "final_capital": self.current_capital,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "max_drawdown": self.max_drawdown,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "trades": self.trades,
            "equity_curve": self.equity_curve
        }
    
    def plot_results(self, df: pd.DataFrame, results: Dict):
        """백테스트 결과 그래프 표시 (규칙6: 비트코인가격 그래프와 수익률 그래프)"""
        # 한글 폰트 설정
        plt.rcParams['font.family'] = 'DejaVu Sans'
        plt.rcParams['axes.unicode_minus'] = False
        
        # 그래프 생성
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))
        
        # 1. 비트코인 가격과 거래 포인트 (규칙6)
        ax1.plot(df.index, df['close'], label='BTC Price', linewidth=1, alpha=0.8)
        
        # 거래 포인트 표시
        for trade in results['trades']:
            if trade['side'] == 'long':
                ax1.scatter(trade['timestamp'], trade['entry_price'], color='green', marker='^', s=50, alpha=0.7)
                ax1.scatter(trade['timestamp'], trade['exit_price'], color='lightgreen', marker='v', s=30, alpha=0.7)
            else:
                ax1.scatter(trade['timestamp'], trade['entry_price'], color='red', marker='v', s=50, alpha=0.7)
                ax1.scatter(trade['timestamp'], trade['exit_price'], color='lightcoral', marker='^', s=30, alpha=0.7)
        
        ax1.set_title('비트코인 선물 강도 전략 - 가격과 거래 포인트', fontsize=14, fontweight='bold')
        ax1.set_ylabel('가격 (USDT)', fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. 누적 수익률 그래프 (규칙6)
        if results['equity_curve']:
            # 자본 곡선을 수익률로 변환
            equity_curve = np.array(results['equity_curve'])
            returns = (equity_curve - self.initial_capital) / self.initial_capital * 100
            
            ax2.plot(df.index[20:20+len(returns)], returns, label='누적 수익률 (%)', linewidth=2, color='blue')
            ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
            ax2.fill_between(df.index[20:20+len(returns)], returns, 0, 
                           where=[x >= 0 for x in returns], 
                           color='green', alpha=0.3, label='수익 구간')
            ax2.fill_between(df.index[20:20+len(returns)], returns, 0, 
                           where=[x < 0 for x in returns], 
                           color='red', alpha=0.3, label='손실 구간')
        
        ax2.set_title('비트코인 선물 강도 전략 - 누적 수익률', fontsize=14, fontweight='bold')
        ax2.set_xlabel('시간', fontsize=12)
        ax2.set_ylabel('수익률 (%)', fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # x축 날짜 포맷
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        plt.show()
        
        # 결과 요약 출력
        print(f"\n=== 비트코인 선물 강도 전략 결과 요약 ===")
        print(f"총 거래 횟수: {results['total_trades']}회")
        print(f"승률: {results['win_rate']:.2f}%")
        print(f"총 수익률: {results['total_return']:.2f}%")
        print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
        print(f"수익 팩터: {results['profit_factor']:.2f}")
        print(f"평균 수익: {results['avg_win']:.2f} USDT")
        print(f"평균 손실: {results['avg_loss']:.2f} USDT")

# 현재 베스트 파라미터 (2023년 최적화 결과)
best_params_2023 = {
    'up_pct': 0.015,
    'up_ctr': 0.1,
    'up_vol': 0.8,
    'down_pct': 0.015,
    'down_ctr': 0.5,
    'down_vol': 2.0,
    'atr_mult': 2.0
}

def optimize_parameters_2023():
    """2023년 데이터로 파라미터 최적화 (벡터화 버전)"""
    print("=== 2023년 데이터로 파라미터 최적화 시작 (벡터화) ===")
    
    # 최적화할 파라미터 범위 (거래 빈도 극대화 + 세밀한 최적화를 위해 5개씩 다양하게 설정)
    up_pcts = [0.008, 0.012, 0.015]     # 0.3%, 0.5%, 0.8%, 1.2%, 1.5%
    up_ctrs = [0.05, 0.1, 0.15, 0.2, 0.25]            # 5%, 10%, 15%, 20%, 25%
    up_vols = [0.8, 0.9, 1.0, 1.1]               # 0.6배, 0.7배, 0.8배, 0.9배, 1.0배
    down_pcts = [0.008, 0.012, 0.015]   # 0.3%, 0.5%, 0.8%, 1.2%, 1.5%
    down_ctrs = [0.05, 0.1, 0.15, 0.2, 0.25]          # 5%, 10%, 15%, 20%, 25%
    down_vols = [0.8, 0.9, 1.0, 1.1]             # 0.6배, 0.7배, 0.8배, 0.9배, 1.0배
    atr_mults = [1.2, 1.5, 2.0, 2.5]             # ATR 승수 (5개)
    
    best_params = None
    best_return = -float('inf')
    best_trades = 0
    results = []
    
    # 2023년 데이터 로드
    try:
        csv_path_2023 = os.path.join(os.path.dirname(__file__), 'data', 'BTCUSDT', '5m', 'BTCUSDT_5m_2023.csv')
        df_2023 = pd.read_csv(csv_path_2023)
        df_2023['timestamp'] = pd.to_datetime(df_2023['timestamp'])
        df_2023 = df_2023.set_index('timestamp')
        df_2023 = df_2023.sort_index()
        print(f"2023년 데이터 로드 완료: {len(df_2023)}개 캔들")
    except Exception as e:
        print(f"2023년 데이터 로드 실패: {e}")
        return None
    
    total_combinations = len(up_pcts) * len(up_ctrs) * len(up_vols) * len(down_pcts) * len(down_ctrs) * len(down_vols) * len(atr_mults)
    current_combination = 0
    
    print(f"총 {total_combinations}개 조합 테스트 중... (벡터화로 빠른 처리)")
    
    # 벡터화된 최적화를 위한 파라미터 조합 생성
    import itertools
    param_combinations = list(itertools.product(up_pcts, up_ctrs, up_vols, down_pcts, down_ctrs, down_vols, atr_mults))
    
    for up_pct, up_ctr, up_vol, down_pct, down_ctr, down_vol, atr_mult in param_combinations:
        current_combination += 1
        
        # 전략 생성
        strategy = BTCFuturesStrengthStrategy(
            initial_capital=10000,
            leverage=1,
            up_pct=up_pct,
            up_ctr=up_ctr,
            up_vol=up_vol,
            down_pct=down_pct,
            down_ctr=down_ctr,
            down_vol=down_vol,
            atr_mult=atr_mult,
            commission_rate=0.0005,
            dynamic_sizing=True,
            win_multiplier=0.1,
            loss_multiplier=0.2
        )
        
        # 2023년 백테스트 (벡터화 버전 사용)
        results_2023 = strategy.run_backtest_vectorized(df_2023, start_date='2023-01-01', end_date='2023-12-31')
        
        if 'error' not in results_2023 and results_2023['total_trades'] >= 4:  # 최소 4번 거래
            results.append({
                'up_pct': up_pct,
                'up_ctr': up_ctr,
                'up_vol': up_vol,
                'down_pct': down_pct,
                'down_ctr': down_ctr,
                'down_vol': down_vol,
                'atr_mult': atr_mult,
                'total_return': results_2023['total_return'],
                'total_trades': results_2023['total_trades'],
                'win_rate': results_2023['win_rate'],
                'max_drawdown': results_2023['max_drawdown']
            })
            
            # 최고 성과 업데이트 (거래 횟수와 수익률 모두 고려)
            score = results_2023['total_return'] * (1 + results_2023['total_trades'] / 100)  # 거래 횟수 보너스
            if score > best_return:
                best_return = score
                best_trades = results_2023['total_trades']
                best_params = {
                    'up_pct': up_pct,
                    'up_ctr': up_ctr,
                    'up_vol': up_vol,
                    'down_pct': down_pct,
                    'down_ctr': down_ctr,
                    'down_vol': down_vol,
                    'atr_mult': atr_mult
                }
        
        if current_combination % 200 == 0:
            print(f"진행률: {current_combination}/{total_combinations} ({current_combination/total_combinations*100:.1f}%) - 현재 최고: {best_return:.2f}%")
    
    print(f"\n=== 2023년 최적화 완료 ===")
    print(f"테스트된 조합: {len(results)}개")
    print(f"최적 파라미터: {best_params}")
    print(f"최고 수익률: {best_return:.2f}%")
    print(f"최고 거래 횟수: {best_trades}회")
    
    # 상위 10개 결과 출력
    if results:
        sorted_results = sorted(results, key=lambda x: x['total_return'], reverse=True)
        print(f"\n=== 상위 10개 결과 ===")
        for i, result in enumerate(sorted_results[:10]):
            print(f"{i+1}. 수익률: {result['total_return']:.2f}%, 거래: {result['total_trades']}회, 승률: {result['win_rate']:.1f}%")
            print(f"   파라미터: up_pct={result['up_pct']}, up_ctr={result['up_ctr']}, up_vol={result['up_vol']}")
            print(f"            down_pct={result['down_pct']}, down_ctr={result['down_ctr']}, down_vol={result['down_vol']}, atr_mult={result['atr_mult']}")
    
    return best_params

def test_optimized_strategy_2024(best_params=None):
    """최적화된 파라미터로 2024년 테스트"""
    if not best_params:
        best_params = best_params_2023  # 기본값으로 현재 베스트 파라미터 사용
        print("기본 베스트 파라미터를 사용합니다.")
    
    print(f"\n=== 최적화된 파라미터로 2024년 테스트 ===")
    print(f"사용할 파라미터: {best_params}")
    
    # 최적화된 전략 생성
    strategy = BTCFuturesStrengthStrategy(
        initial_capital=10000,
        leverage=1,
        **best_params,
        commission_rate=0.0005,
        dynamic_sizing=True,
        win_multiplier=0.1,
        loss_multiplier=0.2
    )
    
    # 2024년 데이터 로드
    try:
        csv_path_2024 = os.path.join(os.path.dirname(__file__), 'data', 'BTCUSDT', '5m', 'BTCUSDT_5m_2024.csv')
        df_2024 = pd.read_csv(csv_path_2024)
        df_2024['timestamp'] = pd.to_datetime(df_2024['timestamp'])
        df_2024 = df_2024.set_index('timestamp')
        df_2024 = df_2024.sort_index()
        print(f"2024년 데이터 로드 완료: {len(df_2024)}개 캔들")
    except Exception as e:
        print(f"2024년 데이터 로드 실패: {e}")
        return
    
    # 2024년 백테스트 (벡터화 버전 사용)
    results_2024 = strategy.run_backtest_vectorized(df_2024, start_date='2024-01-01', end_date='2024-12-31')
    
    if 'error' in results_2024:
        print(f"2024년 백테스트 오류: {results_2024['error']}")
        return
    
    print(f"\n=== 2024년 테스트 결과 ===")
    print(f"총 거래 횟수: {results_2024['total_trades']}회")
    print(f"승률: {results_2024['win_rate']:.2f}%")
    print(f"총 수익률: {results_2024['total_return']:.2f}%")
    print(f"최대 낙폭: {results_2024['max_drawdown']:.2f}%")
    print(f"수익 팩터: {results_2024['profit_factor']:.2f}")
    print(f"평균 수익: {results_2024['avg_win']:.2f} USDT")
    print(f"평균 손실: {results_2024['avg_loss']:.2f} USDT")
    
    # 그래프 표시
    print("\n그래프를 생성 중...")
    strategy.plot_results(df_2024, results_2024)

def main():
    """메인 실행 함수 - 베스트 파라미터 사용 또는 새로 최적화 선택"""
    print("=== 비트코인 선물 강도 전략 ===")
    print("1. 베스트 파라미터로 2024년 테스트 (빠름)")
    print("2. 2023년 데이터로 새로 최적화 후 2024년 테스트 (느림)")
    
    while True:
        choice = input("\n선택하세요 (1 또는 2): ").strip()
        
        if choice == "1":
            print("\n베스트 파라미터를 사용하여 2024년 테스트를 시작합니다...")
            test_optimized_strategy_2024()  # 기본값으로 best_params_2023 사용
            break
            
        elif choice == "2":
            print("\n2023년 데이터로 새로 최적화를 시작합니다...")
            best_params = optimize_parameters_2023()
            test_optimized_strategy_2024(best_params)
            break
            
        else:
            print("잘못된 선택입니다. 1 또는 2를 입력해주세요.")

# 사용 예시
if __name__ == "__main__":
    main()
