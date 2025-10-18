#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MA 적응형 롱/숏 전략 시스템
- 6개 전략 x 롱/숏 = 12개 전략
- MA 10일~100일 기반으로 롱/숏 비율 동적 조정 (0:100 ~ 100:0)
- 성과 기반 동적 자본 배분
"""

import pandas as pd
import numpy as np
import argparse
from datetime import datetime
import os
import json

class MAAdaptiveStrategySystem:
    """MA 적응형 롱/숏 전략 시스템"""
    
    def __init__(self, initial_capital: float = 100000, enabled_strategies: list = None, config_file: str = None):
        self.initial_capital = initial_capital
        self.trading_fee = 0.001  # 0.04% 수수료 (낮춤)
        self.leverage = 2.0  # 2배 레버리지 (안전하게)
        self.stop_loss_pct = 0.08  # 8% 손절라인 (완화)
        self.take_profit_pct = 0.12  # 12% 익절라인 추가
        
        # 설정 파일에서 전략 로드
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.enabled_strategies = config.get('enabled_strategies', [])
                self.strategy_descriptions = config.get('strategy_descriptions', {})
        elif enabled_strategies is not None:
            self.enabled_strategies = enabled_strategies
            self.strategy_descriptions = {}
        else:
            # 기본값: 모든 전략
            self.enabled_strategies = [
                'momentum_long', 'momentum_short',
                'scalping_long', 'scalping_short',
                'macd_long', 'macd_short',
                'moving_average_long', 'moving_average_short',
                'trend_long', 'trend_short',
                'bb_long', 'bb_short'
            ]
            self.strategy_descriptions = {}
        
        # 전략별 자본 (활성화된 전략만)
        # 초기에는 균등 배분, 이후 성과에 따라 동적 조정
        self.strategy_capitals = {}
        if self.enabled_strategies:
            equal_weight = 1.0 / len(self.enabled_strategies)
            for strategy in self.enabled_strategies:
                self.strategy_capitals[strategy] = self.initial_capital * equal_weight
        
        # 전략별 거래 기록 (활성화된 전략만)
        self.strategy_trades = {}
        for strategy in self.enabled_strategies:
            self.strategy_trades[strategy] = []
        
        # 전략별 성과 추적 (동적 자본 배분용) - 활성화된 전략만
        self.strategy_performance = {}
        for strategy in self.enabled_strategies:
            self.strategy_performance[strategy] = {'trades': 0, 'wins': 0, 'total_return': 0}
        
    def calculate_ma_long_short_ratio(self, data: pd.DataFrame) -> tuple:
        """MA 기반 롱/숏 비율 계산 (0:100 ~ 100:0)"""
        df = data.copy()
        
        # MA 10일, 20일, 30일, 40일, 50일, 60일, 70일, 80일, 90일, 100일
        ma_periods = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        ma_values = {}
        
        for period in ma_periods:
            ma_values[f'ma{period}'] = df['close'].rolling(window=period).mean()
        
        # 현재 가격이 각 MA 위에 있는지 확인
        above_ma_count = 0
        for period in ma_periods:
            above_ma_count += (df['close'] > ma_values[f'ma{period}']).astype(int)
        
        # 0~10개 MA 위에 있으면 0~100% 롱 비율
        long_ratio = (above_ma_count / len(ma_periods)) * 100
        short_ratio = 100 - long_ratio
        
        return long_ratio, short_ratio

    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """모든 전략의 신호를 벡터화로 계산"""
        df = data.copy()
        
        # MA 기반 롱/숏 비율 계산
        long_ratio, short_ratio = self.calculate_ma_long_short_ratio(df)
        df['long_ratio'] = long_ratio
        df['short_ratio'] = short_ratio
        
        # MA 비율을 0~1 범위로 정규화 (거래 확률용)
        df['long_probability'] = long_ratio / 100.0
        df['short_probability'] = short_ratio / 100.0
        
        # 1. 모멘텀 전략 신호
        df['momentum_20'] = df['close'].pct_change(20)
        
        # 모멘텀 롱 신호 (MA 비율 적용) - 조건 완화
        df['momentum_long_signal'] = 0
        momentum_long_condition = df['momentum_20'] > 0.01  # 0.02 -> 0.01로 완화
        # MA 비율에 따라 진입 확률 조절 (확률 증가)
        momentum_long_entry = momentum_long_condition & (np.random.random(len(df)) < (df['long_probability'] * 1.5).clip(0, 1))
        df.loc[momentum_long_entry, 'momentum_long_signal'] = 1
        df.loc[df['momentum_20'] < -0.01, 'momentum_long_signal'] = -1  # 0.02 -> 0.01로 완화
        
        # 모멘텀 숏 신호 (MA 비율 적용) - 조건 완화
        df['momentum_short_signal'] = 0
        momentum_short_condition = df['momentum_20'] < -0.01  # 0.02 -> 0.01로 완화
        # MA 비율에 따라 진입 확률 조절 (확률 증가)
        momentum_short_entry = momentum_short_condition & (np.random.random(len(df)) < (df['short_probability'] * 1.5).clip(0, 1))
        df.loc[momentum_short_entry, 'momentum_short_signal'] = 1
        df.loc[df['momentum_20'] > 0.01, 'momentum_short_signal'] = -1  # 0.02 -> 0.01로 완화
        
        # 2. 스캘핑 전략 신호
        df['volatility_5'] = df['close'].pct_change().rolling(5).std()
        df['price_change_5'] = df['close'].pct_change(5)
        
        # 스캘핑 롱 신호 (MA 비율 적용)
        df['scalping_long_signal'] = 0
        scalping_long_buy_condition = (df['volatility_5'] > 0.005) & (df['price_change_5'] > 0.003)
        # MA 비율에 따라 진입 확률 조절
        scalping_long_buy = scalping_long_buy_condition & (np.random.random(len(df)) < df['long_probability'])
        scalping_long_sell = (df['volatility_5'] > 0.005) & (df['price_change_5'] < -0.003)
        df.loc[scalping_long_buy, 'scalping_long_signal'] = 1
        df.loc[scalping_long_sell, 'scalping_long_signal'] = -1
        
        # 스캘핑 숏 신호 (MA 비율 적용)
        df['scalping_short_signal'] = 0
        scalping_short_buy_condition = (df['volatility_5'] > 0.012) & (df['price_change_5'] < -0.008)
        # MA 비율에 따라 진입 확률 조절
        scalping_short_buy = scalping_short_buy_condition & (np.random.random(len(df)) < df['short_probability'])
        scalping_short_sell = (df['volatility_5'] > 0.005) & (df['price_change_5'] > 0.003)
        df.loc[scalping_short_buy, 'scalping_short_signal'] = 1
        df.loc[scalping_short_sell, 'scalping_short_signal'] = -1
        
        # 3. MACD 전략 신호
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        macd = ema12 - ema26
        macd_signal = macd.ewm(span=9).mean()
        macd_cross_up = (macd > macd_signal) & (macd.shift(1) <= macd_signal.shift(1))
        macd_cross_down = (macd < macd_signal) & (macd.shift(1) >= macd_signal.shift(1))
        
        # MACD 롱 신호 (MA 비율 적용)
        df['macd_long_signal'] = 0
        macd_long_entry = macd_cross_up & (np.random.random(len(df)) < df['long_probability'])
        df.loc[macd_long_entry, 'macd_long_signal'] = 1
        df.loc[macd_cross_down, 'macd_long_signal'] = -1
        
        # MACD 숏 신호 (MA 비율 적용)
        df['macd_short_signal'] = 0
        macd_short_entry = macd_cross_down & (np.random.random(len(df)) < df['short_probability'])
        df.loc[macd_short_entry, 'macd_short_signal'] = 1
        df.loc[macd_cross_up, 'macd_short_signal'] = -1
        
        # 4. 이동평균 전략 신호
        ma20 = df['close'].rolling(window=20).mean()
        ma50 = df['close'].rolling(window=50).mean()
        ma100 = df['close'].rolling(window=100).mean()
        
        df['ma20'] = ma20
        df['ma50'] = ma50
        df['ma100'] = ma100
        df['ma_cross_up'] = (ma20 > ma50) & (ma20.shift(1) <= ma50.shift(1))
        df['ma_cross_down'] = (ma20 < ma50) & (ma20.shift(1) >= ma50.shift(1))
        
        # 이동평균 롱 신호 (MA 비율 적용)
        df['moving_average_long_signal'] = 0
        ma_long_entry = df['ma_cross_up'] & (np.random.random(len(df)) < df['long_probability'])
        df.loc[ma_long_entry, 'moving_average_long_signal'] = 1
        df.loc[df['ma_cross_down'], 'moving_average_long_signal'] = -1
        
        # 이동평균 숏 신호 (MA 비율 적용)
        df['moving_average_short_signal'] = 0
        ma_short_entry = df['ma_cross_down'] & (np.random.random(len(df)) < df['short_probability'])
        df.loc[ma_short_entry, 'moving_average_short_signal'] = 1
        df.loc[df['ma_cross_up'], 'moving_average_short_signal'] = -1
        
        # 5. 트렌드 전략 신호
        # 트렌드 롱 신호 (상승 트렌드) - MA 비율 적용
        df['trend_long_signal'] = 0
        strong_uptrend = (df['ma20'] > df['ma50']) & (df['ma50'] > df['ma100'])
        price_above_ma20 = df['close'] > df['ma20']
        positive_momentum = df['momentum_20'] > 0.01
        
        trend_long_condition = strong_uptrend & price_above_ma20 & positive_momentum
        trend_long_entry = trend_long_condition & (np.random.random(len(df)) < df['long_probability'])
        trend_long_exit = (df['ma20'] < df['ma50']) | (df['close'] < df['ma20'])
        df.loc[trend_long_entry, 'trend_long_signal'] = 1
        df.loc[trend_long_exit, 'trend_long_signal'] = -1
        
        # 트렌드 숏 신호 (하락 트렌드) - MA 비율 적용
        df['trend_short_signal'] = 0
        strong_downtrend = (df['ma20'] < df['ma50']) & (df['ma50'] < df['ma100'])
        price_below_ma20 = df['close'] < df['ma20']
        negative_momentum = df['momentum_20'] < -0.01
        
        trend_short_condition = strong_downtrend & price_below_ma20 & negative_momentum
        trend_short_entry = trend_short_condition & (np.random.random(len(df)) < df['short_probability'])
        trend_short_exit = (df['ma20'] > df['ma50']) | (df['close'] > df['ma20'])
        df.loc[trend_short_entry, 'trend_short_signal'] = 1
        df.loc[trend_short_exit, 'trend_short_signal'] = -1
        
        # 6. 볼린저 밴드 전략 신호
        df['bb_upper'] = df['close'].rolling(20).mean() + (df['close'].rolling(20).std() * 2)
        df['bb_lower'] = df['close'].rolling(20).mean() - (df['close'].rolling(20).std() * 2)
        df['bb_middle'] = df['close'].rolling(20).mean()
        
        # 볼린저 밴드 롱 신호 (MA 비율 적용)
        df['bb_long_signal'] = 0
        bb_long_condition = df['close'] <= df['bb_lower']  # 하단 밴드 터치 시 롱 진입
        bb_long_entry = bb_long_condition & (np.random.random(len(df)) < df['long_probability'])
        bb_long_exit = df['close'] >= df['bb_upper']   # 상단 밴드 터치 시 롱 청산
        df.loc[bb_long_entry, 'bb_long_signal'] = 1
        df.loc[bb_long_exit, 'bb_long_signal'] = -1
        
        # 볼린저 밴드 숏 신호 (MA 비율 적용)
        df['bb_short_signal'] = 0
        bb_short_condition = df['close'] >= df['bb_upper']  # 상단 밴드 터치 시 숏 진입
        bb_short_entry = bb_short_condition & (np.random.random(len(df)) < df['short_probability'])
        bb_short_exit = df['close'] <= df['bb_lower']   # 하단 밴드 터치 시 숏 청산
        df.loc[bb_short_entry, 'bb_short_signal'] = 1
        df.loc[bb_short_exit, 'bb_short_signal'] = -1
        
        return df
    
    def check_stop_loss(self, position: float, entry_price: float, current_price: float, is_short: bool) -> bool:
        """손절라인 체크"""
        if position == 0:
            return False
        
        if is_short:
            # 숏 포지션: 가격이 올라가면 손실
            loss_pct = (current_price - entry_price) / entry_price
        else:
            # 롱 포지션: 가격이 내려가면 손실
            loss_pct = (entry_price - current_price) / entry_price
        
        return loss_pct >= self.stop_loss_pct
    
    def check_take_profit(self, position: float, entry_price: float, current_price: float, is_short: bool) -> bool:
        """익절라인 체크"""
        if position == 0:
            return False
        
        if is_short:
            # 숏 포지션: 가격이 내려가면 수익
            profit_pct = (entry_price - current_price) / entry_price
        else:
            # 롱 포지션: 가격이 올라가면 수익
            profit_pct = (current_price - entry_price) / entry_price
        
        return profit_pct >= self.take_profit_pct
    
    def backtest_strategy(self, data: pd.DataFrame, strategy_name: str) -> dict:
        """개별 전략 백테스트"""
        signal_col = f'{strategy_name}_signal'
        signals = data[signal_col].values
        prices = data['close'].values
        timestamps = data.index
        
        capital = self.strategy_capitals[strategy_name]
        position = 0
        entry_price = 0
        trades = []
        
        # 숏 전략 여부 확인
        is_short_strategy = strategy_name.endswith('_short')
        
        for i in range(len(signals)):
            current_price = prices[i]
            current_time = timestamps[i]
            signal = signals[i]
            
            # 손절/익절라인 체크
            if position != 0:
                is_short = position < 0
                
                # 익절라인 체크 (손절보다 우선)
                if self.check_take_profit(position, entry_price, current_price, is_short):
                    # 익절라인 도달 - 강제 청산
                    if is_short:
                        gross_value = abs(position) * current_price
                        fee = gross_value * self.trading_fee
                        net_value = gross_value - fee
                        pnl = (entry_price - current_price) * abs(position)
                        original_capital = capital * self.leverage
                        capital_change = pnl - fee  # 수수료 차감
                        new_capital = max(0, original_capital + capital_change)
                        action = 'TAKE_PROFIT_SHORT'
                    else:
                        gross_value = position * current_price
                        fee = gross_value * self.trading_fee
                        net_value = gross_value - fee
                        pnl = (current_price - entry_price) * position
                        original_capital = capital * self.leverage
                        capital_change = pnl - fee  # 수수료 차감
                        new_capital = max(0, original_capital + capital_change)
                        action = 'TAKE_PROFIT_LONG'
                    
                    capital = new_capital
                    position = 0
                    entry_price = 0
                    
                    trades.append({
                        'timestamp': current_time,
                        'action': action,
                        'price': current_price,
                        'shares': abs(position),
                        'leverage': self.leverage,
                        'gross_value': gross_value,
                        'fee': fee,
                        'net_value': net_value,
                        'capital_change': capital_change
                    })
                    continue
                
                # 손절라인 체크
                elif self.check_stop_loss(position, entry_price, current_price, is_short):
                    # 손절라인 도달 - 강제 청산
                    if is_short:
                        gross_value = abs(position) * current_price
                        fee = gross_value * self.trading_fee
                        net_value = gross_value - fee
                        pnl = (entry_price - current_price) * abs(position)
                        original_capital = capital * self.leverage
                        capital_change = pnl - fee  # 수수료 차감
                        new_capital = max(0, original_capital + capital_change)
                        action = 'STOP_LOSS_SHORT'
                    else:
                        gross_value = position * current_price
                        fee = gross_value * self.trading_fee
                        net_value = gross_value - fee
                        pnl = (current_price - entry_price) * position
                        original_capital = capital * self.leverage
                        capital_change = pnl - fee  # 수수료 차감
                        new_capital = max(0, original_capital + capital_change)
                        action = 'STOP_LOSS_LONG'
                    
                    capital = new_capital
                    position = 0
                    entry_price = 0
                    
                    trades.append({
                        'timestamp': current_time,
                        'action': action,
                        'price': current_price,
                        'shares': abs(position),
                        'leverage': self.leverage,
                        'gross_value': gross_value,
                        'fee': fee,
                        'net_value': net_value,
                        'capital_change': capital_change
                    })
                    continue
            
            if signal == 1 and position == 0:  # 매수 (롱) 또는 숏 매수
                leveraged_value = capital * self.leverage
                fee = leveraged_value * self.trading_fee
                net_value = leveraged_value - fee
                shares = net_value / current_price
                
                if is_short_strategy:
                    position = -shares  # 음수 = 숏 포지션
                    action = 'SHORT_SELL'
                else:
                    position = shares   # 양수 = 롱 포지션
                    action = 'BUY'
                
                entry_price = current_price
                capital = 0
                
                trades.append({
                    'timestamp': current_time,
                    'action': action,
                    'price': current_price,
                    'shares': abs(shares),
                    'leverage': self.leverage,
                    'leveraged_value': leveraged_value,
                    'fee': fee,
                    'net_value': net_value
                })
                
            elif signal == -1 and position != 0:  # 매도 (롱) 또는 숏 매도
                if is_short_strategy:
                    # 숏 포지션 청산
                    gross_value = abs(position) * current_price
                    fee = gross_value * self.trading_fee
                    net_value = gross_value - fee
                    
                    # 숏 포지션 수익 계산
                    pnl = (entry_price - current_price) * abs(position)
                    original_capital = leveraged_value / self.leverage
                    capital_change = pnl - fee  # 수수료 차감
                    new_capital = max(0, original_capital + capital_change)
                    action = 'SHORT_COVER'
                else:
                    # 롱 포지션 청산
                    gross_value = position * current_price
                    fee = gross_value * self.trading_fee
                    net_value = gross_value - fee
                    
                    # 롱 포지션 수익 계산
                    pnl = (current_price - entry_price) * position
                    original_capital = leveraged_value / self.leverage
                    capital_change = pnl - fee  # 수수료 차감
                    new_capital = max(0, original_capital + capital_change)
                    action = 'SELL'
                
                capital = new_capital
                position = 0
                entry_price = 0
                
                trades.append({
                    'timestamp': current_time,
                    'action': action,
                    'price': current_price,
                    'shares': abs(position),
                    'leverage': self.leverage,
                    'gross_value': gross_value,
                    'fee': fee,
                    'net_value': net_value,
                    'capital_change': capital_change
                })
        
        # 최종 포지션 청산
        if position != 0:
            final_price = prices[-1]
            final_time = timestamps[-1]
            
            if is_short_strategy:
                gross_value = abs(position) * final_price
                fee = gross_value * self.trading_fee
                net_value = gross_value - fee
                pnl = (entry_price - final_price) * abs(position)
                original_capital = leveraged_value / self.leverage
                capital_change = pnl - fee  # 수수료 차감
                new_capital = max(0, original_capital + capital_change)
                action = 'FINAL_SHORT_COVER'
            else:
                gross_value = position * final_price
                fee = gross_value * self.trading_fee
                net_value = gross_value - fee
                pnl = (final_price - entry_price) * position
                original_capital = leveraged_value / self.leverage
                capital_change = pnl - fee  # 수수료 차감
                new_capital = max(0, original_capital + capital_change)
                action = 'FINAL_SELL'
            
            capital = new_capital
            
            trades.append({
                'timestamp': final_time,
                'action': action,
                'price': final_price,
                'shares': abs(position),
                'leverage': self.leverage,
                'gross_value': gross_value,
                'fee': fee,
                'net_value': net_value,
                'capital_change': capital_change
            })
        
        # 성과 업데이트
        total_trades = len(trades)
        winning_trades = sum(1 for trade in trades if trade.get('capital_change', 0) > 0)
        total_return = (capital - self.strategy_capitals[strategy_name]) / self.strategy_capitals[strategy_name]
        
        self.strategy_performance[strategy_name] = {
            'trades': total_trades,
            'wins': winning_trades,
            'total_return': total_return
        }
        
        return {
            'final_capital': capital,
            'trades': trades,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'total_return': total_return
        }
    
    def rebalance_capitals(self):
        """성과 기반 자본 재배분"""
        # 각 전략의 성과를 기반으로 가중치 계산
        total_performance = sum(max(0, perf['total_return']) for perf in self.strategy_performance.values())
        
        if total_performance > 0:
            # 양의 수익을 낸 전략들에만 자본 재배분
            for strategy_name, performance in self.strategy_performance.items():
                if performance['total_return'] > 0:
                    weight = performance['total_return'] / total_performance
                    self.strategy_capitals[strategy_name] = self.initial_capital * weight * 0.8  # 80% 재배분
                else:
                    self.strategy_capitals[strategy_name] = self.initial_capital * 0.02  # 2% 최소 보장
    
    def run_continuous_backtest(self, start_year: int, end_year: int):
        """연속 백테스트 실행 (여러 연도) - 성과 누적"""
        print("🚀 MA 적응형 롱/숏 전략 시스템 연속 백테스트 시작!")
        print("=" * 80)
        print(f"💰 초기 자본: ${self.initial_capital:,.2f}")
        print(f"📊 전략 수: {len(self.enabled_strategies)}개")
        strategy_names = []
        for strategy in self.enabled_strategies:
            desc = self.strategy_descriptions.get(strategy, strategy)
            strategy_names.append(f"{strategy}({desc})")
        print(f"🎯 활성화된 전략: {', '.join(strategy_names)}")
        print(f"⚡ 레버리지: {self.leverage}배")
        print(f"💸 수수료: {self.trading_fee*100:.2f}%")
        print(f"📅 기간: {start_year}년 ~ {end_year}년")
        print("=" * 80)
        
        all_results = {}
        total_initial_capital = self.initial_capital
        current_capital = self.initial_capital
        
        # 전략별 누적 성과 추적 (연속성 유지) - 활성화된 전략만
        cumulative_performance = {}
        for strategy in self.enabled_strategies:
            cumulative_performance[strategy] = {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0}
        
        for year in range(start_year, end_year + 1):
            print(f"\n📅 {year}년 백테스트 시작...")
            print("-" * 60)
            
            # 데이터 로드
            data = load_data('BTCUSDT', year)
            if data is None:
                print(f"❌ {year}년 데이터를 찾을 수 없습니다. 건너뜁니다.")
                continue
            
            # 성과 기반 자본 배분 (첫 해가 아닌 경우)
            if year > start_year:
                self.rebalance_capitals_from_performance(cumulative_performance, current_capital)
            else:
                # 첫 해는 균등 배분 (활성화된 전략만)
                equal_weight = 1.0 / len(self.enabled_strategies)
                for strategy in self.enabled_strategies:
                    self.strategy_capitals[strategy] = current_capital * equal_weight
            
            # 현재 자본으로 초기 자본 업데이트
            self.initial_capital = current_capital
            
            # 백테스트 실행
            year_results = self.run_single_year_backtest(data, year)
            all_results[year] = year_results
            
            # 누적 성과 업데이트
            for strategy_name, result in year_results.items():
                cumulative_performance[strategy_name]['total_trades'] += result['total_trades']
                cumulative_performance[strategy_name]['total_wins'] += result['winning_trades']
                cumulative_performance[strategy_name]['total_return'] += result['total_return']
                cumulative_performance[strategy_name]['years'] += 1
            
            # 다음 해를 위한 자본 업데이트
            year_final_capital = sum(result['final_capital'] for result in year_results.values())
            current_capital = year_final_capital
            
            print(f"💰 {year}년 최종 자본: ${year_final_capital:,.2f}")
            print(f"📈 {year}년 수익률: {((year_final_capital - self.initial_capital) / self.initial_capital * 100):.2f}%")
            
            # 전략별 자본 배분 현황 출력
            self.print_capital_allocation(year)
        
        # 전체 결과 분석
        self.analyze_continuous_results(all_results, total_initial_capital, current_capital)
        return all_results

    def run_single_year_backtest(self, data: pd.DataFrame, year: int):
        """단일 연도 백테스트"""
        print(f"🔄 1단계: {year}년 신호 계산 중...")
        data_with_signals = self.calculate_signals(data)
        print("✅ 신호 계산 완료!")
        
        # MA 비율 분석
        self.analyze_ma_ratios(data_with_signals, year)
        
        print(f"🔄 2단계: {year}년 전략별 백테스트 중...")
        results = {}
        
        for strategy in self.enabled_strategies:
            results[strategy] = self.backtest_strategy(data_with_signals, strategy)
        
        print("✅ 모든 전략 백테스트 완료!")
        return results

    def analyze_ma_ratios(self, data: pd.DataFrame, year: int):
        """MA 비율 분석 및 출력"""
        # 롱/숏 비율 통계
        long_ratios = data['long_ratio'].dropna()
        short_ratios = data['short_ratio'].dropna()
        
        print(f"📊 {year}년 MA 기반 롱/숏 비율 분석 (거래 빈도 조절):")
        print(f"   롱 비율: 평균 {long_ratios.mean():.1f}%, 최대 {long_ratios.max():.1f}%, 최소 {long_ratios.min():.1f}%")
        print(f"   숏 비율: 평균 {short_ratios.mean():.1f}%, 최대 {short_ratios.max():.1f}%, 최소 {short_ratios.min():.1f}%")
        print(f"   💡 MA 비율에 따라 롱/숏 전략의 진입 빈도가 조절됩니다!")
        
        # 비율 분포
        long_high = (long_ratios >= 70).sum()  # 70% 이상 롱
        long_medium = ((long_ratios >= 30) & (long_ratios < 70)).sum()  # 30-70% 롱
        long_low = (long_ratios < 30).sum()  # 30% 미만 롱
        
        print(f"   롱 비율 분포: 높음(70%+) {long_high:,}회, 중간(30-70%) {long_medium:,}회, 낮음(30%-) {long_low:,}회")

    def run_backtest(self, data: pd.DataFrame, start_date: str = None, end_date: str = None):
        """백테스트 실행"""
        print("🚀 MA 적응형 롱/숏 전략 시스템 백테스트 시작!")
        print("=" * 60)
        print(f"💰 초기 자본: ${self.initial_capital:,.2f}")
        print(f"📊 전략 수: {len(self.enabled_strategies)}개")
        strategy_names = []
        for strategy in self.enabled_strategies:
            desc = self.strategy_descriptions.get(strategy, strategy)
            strategy_names.append(f"{strategy}({desc})")
        print(f"🎯 활성화된 전략: {', '.join(strategy_names)}")
        print(f"⚡ 레버리지: {self.leverage}배")
        print(f"💸 수수료: {self.trading_fee*100:.2f}%")
        
        # 날짜 필터링
        if start_date:
            data = data[data.index >= start_date]
        if end_date:
            data = data[data.index <= end_date]
        
        print(f"📅 기간: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
        print(f"📊 백테스트 데이터: {len(data):,}개 캔들")
        print("=" * 60)
        
        # 1단계: 신호 계산
        print("🔄 1단계: 신호 계산 중...")
        data_with_signals = self.calculate_signals(data)
        print("✅ 신호 계산 완료!")
        
        # 2단계: 각 전략별 백테스트
        print("🔄 2단계: 전략별 백테스트 중...")
        results = {}
        
        for strategy in self.enabled_strategies:
            print(f"   📊 {strategy} 전략 처리 중...")
            results[strategy] = self.backtest_strategy(data_with_signals, strategy)
        
        print("✅ 모든 전략 백테스트 완료!")
        
        # 3단계: 성과 분석
        print("\n🔄 3단계: 성과 분석 중...")
        self.analyze_results(results, data)
        
        return results
    
    def analyze_results(self, results: dict, data: pd.DataFrame):
        """결과 분석 및 출력"""
        print("\n📊 포트폴리오 성과 분석")
        print("=" * 60)
        
        # 전체 성과 계산
        total_initial_capital = self.initial_capital
        total_final_capital = sum(result['final_capital'] for result in results.values())
        total_return = (total_final_capital - total_initial_capital) / total_initial_capital
        
        print(f"💰 초기 자본: ${total_initial_capital:,.2f}")
        print(f"💰 최종 자본: ${total_final_capital:,.2f}")
        print(f"📈 총 수익률: {total_return*100:.2f}%")
        
        # 전략별 성과
        print(f"\n🎯 전략별 성과 (수수료 {self.trading_fee*100:.2f}% 적용)")
        print(f"📅 백테스트 기간: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
        print(f"📊 총 데이터: {len(data):,}개 캔들")
        print("-" * 60)
        
        # 성과 순으로 정렬
        strategy_performance = []
        for strategy_name, result in results.items():
            strategy_performance.append({
                'name': strategy_name,
                'trades': result['total_trades'],
                'win_rate': result['win_rate'] * 100,
                'return': result['total_return'] * 100,
                'final_capital': result['final_capital']
            })
        
        strategy_performance.sort(key=lambda x: x['return'], reverse=True)
        
        for perf in strategy_performance:
            print(f"{perf['name']:<20}: 거래 {perf['trades']:3d}회, 승률 {perf['win_rate']:5.1f}%, "
                  f"수익률 {perf['return']:7.2f}%, 최종자본 ${perf['final_capital']:8.2f}")
        
        print(f"\n🎉 백테스트 완료!")
        print(f"💰 최종 수익률: {total_return*100:.2f}%")

    def analyze_continuous_results(self, all_results: dict, initial_capital: float, final_capital: float):
        """연속 백테스트 결과 분석"""
        print("\n" + "=" * 80)
        print("📊 연속 백테스트 전체 결과 분석")
        print("=" * 80)
        
        # 전체 성과
        total_return = (final_capital - initial_capital) / initial_capital
        print(f"💰 초기 자본: ${initial_capital:,.2f}")
        print(f"💰 최종 자본: ${final_capital:,.2f}")
        print(f"📈 전체 수익률: {total_return*100:.2f}%")
        
        # 연도별 성과
        print(f"\n📅 연도별 성과:")
        print("-" * 60)
        for year, results in all_results.items():
            year_capital = sum(result['final_capital'] for result in results.values())
            if year == min(all_results.keys()):
                year_return = (year_capital - initial_capital) / initial_capital
            else:
                prev_year = year - 1
                if prev_year in all_results:
                    prev_capital = sum(result['final_capital'] for result in all_results[prev_year].values())
                    year_return = (year_capital - prev_capital) / prev_capital
                else:
                    year_return = 0
            
            print(f"{year}년: ${year_capital:,.2f} ({year_return*100:+.2f}%)")
        
        # 전략별 전체 성과 (연도별 평균)
        print(f"\n🎯 전략별 전체 성과 (연도별 평균):")
        print("-" * 60)
        
        strategy_totals = {}
        for year, results in all_results.items():
            for strategy_name, result in results.items():
                if strategy_name not in strategy_totals:
                    strategy_totals[strategy_name] = {
                        'total_trades': 0,
                        'total_wins': 0,
                        'total_return': 0,
                        'years': 0
                    }
                
                strategy_totals[strategy_name]['total_trades'] += result['total_trades']
                strategy_totals[strategy_name]['total_wins'] += result['winning_trades']
                strategy_totals[strategy_name]['total_return'] += result['total_return']
                strategy_totals[strategy_name]['years'] += 1
        
        # 평균 계산 및 정렬
        strategy_avg = []
        for strategy_name, totals in strategy_totals.items():
            avg_trades = totals['total_trades'] / totals['years']
            avg_wins = totals['total_wins'] / totals['years']
            avg_return = totals['total_return'] / totals['years']
            avg_win_rate = avg_wins / avg_trades if avg_trades > 0 else 0
            
            strategy_avg.append({
                'name': strategy_name,
                'trades': avg_trades,
                'win_rate': avg_win_rate * 100,
                'return': avg_return * 100
            })
        
        strategy_avg.sort(key=lambda x: x['return'], reverse=True)
        
        for perf in strategy_avg:
            print(f"{perf['name']:<20}: 거래 {perf['trades']:5.1f}회, 승률 {perf['win_rate']:5.1f}%, "
                  f"수익률 {perf['return']:7.2f}%")
        
        print(f"\n🎉 연속 백테스트 완료!")
        print(f"💰 전체 수익률: {total_return*100:.2f}%")

    def rebalance_capitals_from_performance(self, cumulative_performance: dict, current_capital: float):
        """누적 성과를 기반으로 자본 재배분 (하이브리드 접근법)"""
        # 최근 성과에 더 가중치를 주는 방식 (최근 1년 성과 70%, 전체 성과 30%)
        recent_performance = {}
        total_recent_positive = 0
        
        for strategy_name, performance in cumulative_performance.items():
            if performance['years'] > 0:
                # 최근 1년 성과 (마지막 해의 성과)
                recent_return = performance['total_return'] / performance['years']
                if recent_return > 0:
                    recent_performance[strategy_name] = recent_return
                    total_recent_positive += recent_return
        
        if total_recent_positive > 0:
            # 하이브리드 배분: 50% 성과 기반, 50% 균등 배분
            for strategy_name in self.strategy_capitals.keys():
                if strategy_name in recent_performance:
                    # 성과 기반 배분 (50%)
                    performance_weight = recent_performance[strategy_name] / total_recent_positive
                    performance_capital = current_capital * 0.5 * performance_weight
                    # 균등 배분 (50%)
                    equal_capital = current_capital * 0.5 / len(self.strategy_capitals)
                    self.strategy_capitals[strategy_name] = performance_capital + equal_capital
                else:
                    # 성과가 없는 전략은 균등 배분만
                    self.strategy_capitals[strategy_name] = current_capital * 0.5 / len(self.strategy_capitals)
        else:
            # 모든 전략이 손실이면 균등 배분
            equal_capital = current_capital / len(self.strategy_capitals)
            for strategy_name in self.strategy_capitals.keys():
                self.strategy_capitals[strategy_name] = equal_capital

    def print_capital_allocation(self, year: int):
        """전략별 자본 배분 현황 출력"""
        print(f"📊 {year}년 전략별 자본 배분:")
        total_capital = sum(self.strategy_capitals.values())
        
        # 성과 순으로 정렬
        sorted_strategies = sorted(self.strategy_capitals.items(), 
                                 key=lambda x: x[1], reverse=True)
        
        for strategy_name, capital in sorted_strategies[:6]:  # 상위 6개만 출력
            percentage = (capital / total_capital) * 100
            print(f"   {strategy_name:<20}: ${capital:8,.0f} ({percentage:5.1f}%)")
        
        if len(sorted_strategies) > 6:
            print(f"   ... 기타 {len(sorted_strategies) - 6}개 전략")

def load_data(symbol: str, year: int) -> pd.DataFrame:
    """데이터 로드"""
    filename = f"data/{symbol}/5m/{symbol}_5m_{year}.csv"
    if not os.path.exists(filename):
        print(f"❌ 파일을 찾을 수 없습니다: {filename}")
        return None
    
    print(f"📊 {symbol} {year}년 데이터 로드 중...")
    df = pd.read_csv(filename)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df = df.sort_index()
    
    print(f"✅ 데이터 로드 성공: {len(df):,}개 캔들")
    print(f"📅 기간: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"💰 가격 범위: ${df['close'].min():.2f} ~ ${df['close'].max():.2f}")
    
    return df

def main():
    parser = argparse.ArgumentParser(description='MA 적응형 롱/숏 전략 시스템 백테스트')
    parser.add_argument('--symbol', default='BTCUSDT', help='거래 심볼 (기본값: BTCUSDT)')
    parser.add_argument('--year', type=int, default=2024, help='백테스트 연도 (기본값: 2022)')
    parser.add_argument('--start-year', type=int, help='연속 백테스트 시작 연도')
    parser.add_argument('--end-year', type=int, help='연속 백테스트 종료 연도')
    parser.add_argument('--capital', type=float, default=100000, help='초기 자본 (기본값: 100000)')
    parser.add_argument('--start', help='시작 날짜 (YYYY-MM-DD)')
    parser.add_argument('--end', help='종료 날짜 (YYYY-MM-DD)')
    parser.add_argument('--config', default='strategy_config.json', help='전략 설정 파일 (기본값: strategy_config.json)')
    parser.add_argument('--strategies', nargs='+', help='활성화할 전략 목록 (예: --strategies momentum_long momentum_short)')
    parser.add_argument('--list-strategies', action='store_true', help='사용 가능한 전략 목록 출력')
    
    args = parser.parse_args()
    
    # 사용 가능한 전략 목록 출력
    if args.list_strategies:
        print("📋 사용 가능한 전략 목록:")
        print("-" * 50)
        all_strategies = [
            'momentum_long', 'momentum_short',
            'scalping_long', 'scalping_short',
            'macd_long', 'macd_short',
            'moving_average_long', 'moving_average_short',
            'trend_long', 'trend_short',
            'bb_long', 'bb_short'
        ]
        descriptions = {
            'momentum_long': '모멘텀 롱 전략',
            'momentum_short': '모멘텀 숏 전략',
            'scalping_long': '스캘핑 롱 전략',
            'scalping_short': '스캘핑 숏 전략',
            'macd_long': 'MACD 롱 전략',
            'macd_short': 'MACD 숏 전략',
            'moving_average_long': '이동평균 롱 전략',
            'moving_average_short': '이동평균 숏 전략',
            'trend_long': '트렌드 롱 전략',
            'trend_short': '트렌드 숏 전략',
            'bb_long': '볼린저밴드 롱 전략',
            'bb_short': '볼린저밴드 숏 전략'
        }
        for strategy in all_strategies:
            print(f"  {strategy:<20}: {descriptions[strategy]}")
        return
    
    # 백테스트 실행
    if args.strategies:
        strategy_system = MAAdaptiveStrategySystem(initial_capital=args.capital, enabled_strategies=args.strategies)
    else:
        strategy_system = MAAdaptiveStrategySystem(initial_capital=args.capital, config_file=args.config)
    
    # 연속 백테스트인지 확인
    if args.start_year and args.end_year:
        # 연속 백테스트 실행
        results = strategy_system.run_continuous_backtest(args.start_year, args.end_year)
    else:
        # 단일 연도 백테스트 실행
        data = load_data(args.symbol, args.year)
        if data is None:
            return
        results = strategy_system.run_backtest(data, args.start, args.end)

if __name__ == "__main__":
    main()
