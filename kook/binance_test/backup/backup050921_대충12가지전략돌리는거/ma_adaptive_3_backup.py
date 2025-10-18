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

class MAAdaptiveStrategySystem:
    """MA 적응형 롱/숏 전략 시스템"""
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.trading_fee = 0.0006  # 0.06% 수수료
        self.leverage = 5.0  # 5배 레버리지 (고배율)
        self.stop_loss_pct = 0.15  # 15% 손절라인
        
        # 전략별 자본 (3개 최고 전략만 활성화)
        # 초기에는 균등 배분, 이후 성과에 따라 동적 조정
        self.strategy_capitals = {
            'moving_average_long': self.initial_capital * 0.3333,  # 이동평균 롱 (33.4% 기여도)
            'macd_long': self.initial_capital * 0.3333,            # MACD 롱 (27.4% 기여도)
            'bb_short': self.initial_capital * 0.3333              # 볼린저밴드 숏 (1,018.53%)
        }
        
        # 전략별 거래 기록 (3개 최고 전략만)
        self.strategy_trades = {
            'moving_average_long': [],
            'macd_long': [],
            'bb_short': []
        }
        
        # 전략별 성과 추적 (동적 자본 배분용) - 3개 최고 전략만
        self.strategy_performance = {
            'moving_average_long': {'trades': 0, 'wins': 0, 'total_return': 0},
            'macd_long': {'trades': 0, 'wins': 0, 'total_return': 0},
            'bb_short': {'trades': 0, 'wins': 0, 'total_return': 0}
        }
        
    def calculate_ma_long_short_ratio(self, data: pd.DataFrame) -> tuple:
        """MA 기반 롱/숏 비율 계산 (0:100 ~ 100:0)"""
        df = data.copy()
        
        # MA 20일, 50일, 100일, 200일 (표준 MA 기간)
        ma_periods = [20, 50, 100, 200]
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

    def create_deterministic_random(self, length: int, probability: float) -> np.ndarray:
        """일정 비율로 true가 나오는 결정적 랜덤 배열 생성
        
        Args:
            length: 배열 길이
            probability: true가 나올 확률 (0.0 ~ 1.0)
            
        Returns:
            boolean 배열 (정확히 probability * length 개의 True)
        """
        if probability <= 0:
            return np.zeros(length, dtype=bool)
        elif probability >= 1:
            return np.ones(length, dtype=bool)
        
        # 정확한 개수 계산
        true_count = int(round(probability * length))
        true_count = max(0, min(true_count, length))  # 0과 length 사이로 제한
        
        # 랜덤하게 배치
        result = np.zeros(length, dtype=bool)
        if true_count > 0:
            # 균등하게 분산된 인덱스 생성
            indices = np.linspace(0, length-1, true_count, dtype=int)
            # 약간의 랜덤성을 위해 셔플
            np.random.shuffle(indices)
            result[indices] = True
        
        return result

    def create_deterministic_random_vectorized(self, probabilities: np.ndarray) -> np.ndarray:
        """벡터화된 확률 배열에 대해 일정 비율로 true가 나오는 랜덤 배열 생성
        
        Args:
            probabilities: 각 포인트별 확률 배열 (0.0 ~ 1.0)
            
        Returns:
            boolean 배열 (각 포인트별로 정확한 확률에 따라 True/False)
        """
        length = len(probabilities)
        result = np.zeros(length, dtype=bool)
        
        # 각 확률 구간별로 처리
        for i, prob in enumerate(probabilities):
            if prob <= 0:
                result[i] = False
            elif prob >= 1:
                result[i] = True
            else:
                # 모든 확률에 대해 진짜 랜덤 사용
                # 1% 확률이면 100번 중 평균 1번 True (랜덤하게)
                result[i] = np.random.random() < prob
        
        return result

    def create_true_random_with_ratio(self, length: int, target_ratio: float) -> np.ndarray:
        """진짜 랜덤하지만 일정 비율로 true가 나오는 배열 생성
        
        Args:
            length: 배열 길이
            target_ratio: 목표 True 비율 (0.0 ~ 1.0)
            
        Returns:
            boolean 배열 (목표 비율에 가깝게 True가 랜덤하게 분포)
        """
        if target_ratio <= 0:
            return np.zeros(length, dtype=bool)
        elif target_ratio >= 1:
            return np.ones(length, dtype=bool)
        
        # 목표 개수 계산
        target_count = int(round(target_ratio * length))
        target_count = max(0, min(target_count, length))
        
        # 랜덤하게 True 위치 선택
        all_indices = np.arange(length)
        np.random.shuffle(all_indices)
        true_indices = all_indices[:target_count]
        
        result = np.zeros(length, dtype=bool)
        result[true_indices] = True
        
        return result

    def test_deterministic_random(self, length: int = 1000, probability: float = 0.01):
        """랜덤 함수 테스트 - 두 방식 비교"""
        print(f"🧪 랜덤 함수 테스트 (길이: {length}, 확률: {probability*100:.1f}%)")
        
        # 방식 1: 정확한 개수로 결정적 배치
        result1 = self.create_deterministic_random(length, probability)
        true_count1 = np.sum(result1)
        actual_prob1 = true_count1 / length
        
        print(f"   방식1 (정확한 개수): 예상 {probability*100:.1f}%, 실제 {actual_prob1*100:.2f}% (True 개수: {true_count1})")
        
        # 방식 2: 벡터화된 랜덤 (진짜 랜덤)
        probabilities = np.full(length, probability)
        result2 = self.create_deterministic_random_vectorized(probabilities)
        true_count2 = np.sum(result2)
        actual_prob2 = true_count2 / length
        
        print(f"   방식2 (진짜 랜덤): 예상 {probability*100:.1f}%, 실제 {actual_prob2*100:.2f}% (True 개수: {true_count2})")
        
        # 방식 3: 진짜 랜덤하지만 일정 비율
        result3 = self.create_true_random_with_ratio(length, probability)
        true_count3 = np.sum(result3)
        actual_prob3 = true_count3 / length
        
        print(f"   방식3 (랜덤+비율): 예상 {probability*100:.1f}%, 실제 {actual_prob3*100:.2f}% (True 개수: {true_count3})")
        
        # 1% 확률 테스트 (100번 중 1번)
        if probability == 0.01:
            expected_count = length // 100
            print(f"   💡 1% 확률: 예상 {expected_count}개")
            print(f"      방식1: {true_count1}개, 방식2: {true_count2}개, 방식3: {true_count3}개")
        
        return result1, result2, result3

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
        
        # 모멘텀 롱 신호 (MA 비율 적용)
        df['momentum_long_signal'] = 0
        momentum_long_condition = df['momentum_20'] > 0.02
        # MA 비율에 따라 진입 확률 조절 (방식2: 진짜 랜덤)
        momentum_long_random = self.create_deterministic_random_vectorized(df['long_probability'].values)
        momentum_long_entry = momentum_long_condition & momentum_long_random
        df.loc[momentum_long_entry, 'momentum_long_signal'] = 1
        df.loc[df['momentum_20'] < -0.02, 'momentum_long_signal'] = -1
        
        # 모멘텀 숏 신호 (MA 비율 적용)
        df['momentum_short_signal'] = 0
        momentum_short_condition = df['momentum_20'] < -0.02
        # MA 비율에 따라 진입 확률 조절 (방식2: 진짜 랜덤)
        momentum_short_random = self.create_deterministic_random_vectorized(df['short_probability'].values)
        momentum_short_entry = momentum_short_condition & momentum_short_random
        df.loc[momentum_short_entry, 'momentum_short_signal'] = 1
        df.loc[df['momentum_20'] > 0.02, 'momentum_short_signal'] = -1
        
        # 2. 스캘핑 전략 신호
        df['volatility_5'] = df['close'].pct_change().rolling(5).std()
        df['price_change_5'] = df['close'].pct_change(5)
        
        # 스캘핑 롱 신호 (MA 비율 적용)
        df['scalping_long_signal'] = 0
        scalping_long_buy_condition = (df['volatility_5'] > 0.005) & (df['price_change_5'] > 0.003)
        # MA 비율에 따라 진입 확률 조절 (방식2: 진짜 랜덤)
        scalping_long_random = self.create_deterministic_random_vectorized(df['long_probability'].values)
        scalping_long_buy = scalping_long_buy_condition & scalping_long_random
        scalping_long_sell = (df['volatility_5'] > 0.005) & (df['price_change_5'] < -0.003)
        df.loc[scalping_long_buy, 'scalping_long_signal'] = 1
        df.loc[scalping_long_sell, 'scalping_long_signal'] = -1
        
        # 스캘핑 숏 신호 (MA 비율 적용)
        df['scalping_short_signal'] = 0
        scalping_short_buy_condition = (df['volatility_5'] > 0.012) & (df['price_change_5'] < -0.008)
        # MA 비율에 따라 진입 확률 조절 (방식2: 진짜 랜덤)
        scalping_short_random = self.create_deterministic_random_vectorized(df['short_probability'].values)
        scalping_short_buy = scalping_short_buy_condition & scalping_short_random
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
        macd_long_random = self.create_deterministic_random_vectorized(df['long_probability'].values)
        macd_long_entry = macd_cross_up & macd_long_random
        df.loc[macd_long_entry, 'macd_long_signal'] = 1
        df.loc[macd_cross_down, 'macd_long_signal'] = -1
        
        # MACD 숏 신호 (MA 비율 적용)
        df['macd_short_signal'] = 0
        macd_short_random = self.create_deterministic_random_vectorized(df['short_probability'].values)
        macd_short_entry = macd_cross_down & macd_short_random
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
        ma_long_random = self.create_deterministic_random_vectorized(df['long_probability'].values)
        ma_long_entry = df['ma_cross_up'] & ma_long_random
        df.loc[ma_long_entry, 'moving_average_long_signal'] = 1
        df.loc[df['ma_cross_down'], 'moving_average_long_signal'] = -1
        
        # 이동평균 숏 신호 (MA 비율 적용)
        df['moving_average_short_signal'] = 0
        ma_short_random = self.create_deterministic_random_vectorized(df['short_probability'].values)
        ma_short_entry = df['ma_cross_down'] & ma_short_random
        df.loc[ma_short_entry, 'moving_average_short_signal'] = 1
        df.loc[df['ma_cross_up'], 'moving_average_short_signal'] = -1
        
        # 5. 트렌드 전략 신호
        # 트렌드 롱 신호 (상승 트렌드) - MA 비율 적용
        df['trend_long_signal'] = 0
        strong_uptrend = (df['ma20'] > df['ma50']) & (df['ma50'] > df['ma100'])
        price_above_ma20 = df['close'] > df['ma20']
        positive_momentum = df['momentum_20'] > 0.01
        
        trend_long_condition = strong_uptrend & price_above_ma20 & positive_momentum
        trend_long_random = self.create_deterministic_random_vectorized(df['long_probability'].values)
        trend_long_entry = trend_long_condition & trend_long_random
        trend_long_exit = (df['ma20'] < df['ma50']) | (df['close'] < df['ma20'])
        df.loc[trend_long_entry, 'trend_long_signal'] = 1
        df.loc[trend_long_exit, 'trend_long_signal'] = -1
        
        # 트렌드 숏 신호 (하락 트렌드) - MA 비율 적용
        df['trend_short_signal'] = 0
        strong_downtrend = (df['ma20'] < df['ma50']) & (df['ma50'] < df['ma100'])
        price_below_ma20 = df['close'] < df['ma20']
        negative_momentum = df['momentum_20'] < -0.01
        
        trend_short_condition = strong_downtrend & price_below_ma20 & negative_momentum
        trend_short_random = self.create_deterministic_random_vectorized(df['short_probability'].values)
        trend_short_entry = trend_short_condition & trend_short_random
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
        bb_long_random = self.create_deterministic_random_vectorized(df['long_probability'].values)
        bb_long_entry = bb_long_condition & bb_long_random
        bb_long_exit = df['close'] >= df['bb_upper']   # 상단 밴드 터치 시 롱 청산
        df.loc[bb_long_entry, 'bb_long_signal'] = 1
        df.loc[bb_long_exit, 'bb_long_signal'] = -1
        
        # 볼린저 밴드 숏 신호 (MA 비율 적용)
        df['bb_short_signal'] = 0
        bb_short_condition = df['close'] >= df['bb_upper']  # 상단 밴드 터치 시 숏 진입
        bb_short_random = self.create_deterministic_random_vectorized(df['short_probability'].values)
        bb_short_entry = bb_short_condition & bb_short_random
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
            
            # 손절라인 체크
            if position != 0:
                is_short = position < 0
                if self.check_stop_loss(position, entry_price, current_price, is_short):
                    # 손절라인 도달 - 강제 청산
                    if is_short:
                        gross_value = abs(position) * current_price
                        fee = gross_value * self.trading_fee
                        net_value = gross_value - fee
                        pnl = (entry_price - current_price) * abs(position)
                        original_capital = capital * self.leverage
                        capital_change = pnl
                        new_capital = max(0, original_capital + capital_change)
                        action = 'STOP_LOSS_SHORT'
                    else:
                        gross_value = position * current_price
                        fee = gross_value * self.trading_fee
                        net_value = gross_value - fee
                        pnl = (current_price - entry_price) * position
                        original_capital = capital * self.leverage
                        capital_change = pnl
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
                        'capital_change': capital_change,
                        'entry_price': entry_price
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
                    'net_value': net_value,
                    'entry_price': current_price
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
                    capital_change = pnl
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
                    capital_change = pnl
                    new_capital = max(0, original_capital + capital_change)
                    action = 'SELL'
                
                capital = new_capital
                position = 0
                entry_price = 0
                
                # 이전 거래에서 진입가 찾기
                prev_entry_price = 0
                for trade in reversed(trades):
                    if trade['action'] in ['BUY', 'SHORT_SELL']:
                        prev_entry_price = trade['price']
                        break
                
                trades.append({
                    'timestamp': current_time,
                    'action': action,
                    'price': current_price,
                    'shares': abs(position),
                    'leverage': self.leverage,
                    'gross_value': gross_value,
                    'fee': fee,
                    'net_value': net_value,
                    'capital_change': capital_change,
                    'entry_price': prev_entry_price
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
                capital_change = pnl
                new_capital = max(0, original_capital + capital_change)
                action = 'FINAL_SHORT_COVER'
            else:
                gross_value = position * final_price
                fee = gross_value * self.trading_fee
                net_value = gross_value - fee
                pnl = (final_price - entry_price) * position
                original_capital = leveraged_value / self.leverage
                capital_change = pnl
                new_capital = max(0, original_capital + capital_change)
                action = 'FINAL_SELL'
            
            capital = new_capital
            
            # 이전 거래에서 진입가 찾기
            prev_entry_price = 0
            for trade in reversed(trades):
                if trade['action'] in ['BUY', 'SHORT_SELL']:
                    prev_entry_price = trade['price']
                    break
            
            trades.append({
                'timestamp': final_time,
                'action': action,
                'price': final_price,
                'shares': abs(position),
                'leverage': self.leverage,
                'gross_value': gross_value,
                'fee': fee,
                'net_value': net_value,
                'capital_change': capital_change,
                'entry_price': prev_entry_price
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
        print(f"📊 전략 수: 3개 (최고 전략만)")
        print(f"⚡ 레버리지: {self.leverage}배")
        print(f"💸 수수료: {self.trading_fee*100:.2f}%")
        print(f"📅 기간: {start_year}년 ~ {end_year}년")
        print("=" * 80)
        
        all_results = {}
        total_initial_capital = self.initial_capital
        current_capital = self.initial_capital
        
        # 전략별 누적 성과 추적 (연속성 유지) - 3개 최고 전략만
        cumulative_performance = {
            'moving_average_long': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0},
            'macd_long': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0},
            'bb_short': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0}
        }
        
        for year in range(start_year, end_year + 1):
            print(f"\n📅 {year}년 백테스트 시작...")
            print("-" * 60)
            
            # 데이터 로드
            data = load_data('BTCUSDT', year)
            if data is None:
                print(f"❌ {year}년 데이터를 찾을 수 없습니다. 건너뜁니다.")
                continue
            
            # 매년 균등 배분 (성과 기반 배분 비활성화)
            self.strategy_capitals = {
                'moving_average_long': current_capital * 0.3333,
                'macd_long': current_capital * 0.3333,
                'bb_short': current_capital * 0.3333
            }
            
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
        strategies = [
            'moving_average_long',
            'macd_long',
            'bb_short'
        ]
        results = {}
        
        for strategy in strategies:
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
        print(f"📊 전략 수: 3개 (최고 전략만)")
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
        strategies = [
            'moving_average_long',
            'macd_long',
            'bb_short'
        ]
        results = {}
        
        for strategy in strategies:
            print(f"   📊 {strategy} 전략 처리 중...")
            results[strategy] = self.backtest_strategy(data_with_signals, strategy)
        
        print("✅ 모든 전략 백테스트 완료!")
        
        # 3단계: 성과 분석
        print("\n🔄 3단계: 성과 분석 중...")
        self.analyze_results(results, data)
        
        # 4단계: 거래 기록 출력
        #print("\n🔄 4단계: 거래 기록 분석 중...")
        self.print_trade_records(results)
        
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

    def print_trade_records(self, results: dict):
        """거래 기록 출력 및 파일 저장"""
        #print("\n📋 전략별 거래 기록")
        #print("=" * 80)
        
        # 거래 기록 파일 저장
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        trade_file = f"trade_records.txt"
        
        with open(trade_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("MA 적응형 롱/숏 전략 시스템 - 거래 기록\n")
            f.write(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
        
        for strategy_name, result in results.items():
            trades = result.get('trades', [])
            if not trades:
                print(f"\n{strategy_name}: 거래 기록 없음")
                continue
                
            #print(f"\n🎯 {strategy_name} 전략 거래 기록 ({len(trades)}회)")
            #print("-" * 80)
            
            # 파일에 기록
            with open(trade_file, 'a', encoding='utf-8') as f:
                f.write(f"\n🎯 {strategy_name} 전략 거래 기록 ({len(trades)}회)\n")
                f.write("-" * 80 + "\n")
            
            # 최근 10개 거래만 화면 출력 (너무 많으면 생략)
            recent_trades = trades[-10:] if len(trades) > 10 else trades
            
            for i, trade in enumerate(recent_trades, 1):
                timestamp = trade.get('timestamp', 'N/A')
                action = trade.get('action', 'N/A')
                price = trade.get('price', 0)
                shares = trade.get('shares', 0)
                capital_change = trade.get('capital_change', 0)
                
                # 수익/손실 표시 (승패 동그라미 + 퍼센트)
                if capital_change > 0:
                    pnl_symbol = "🟢"  # 승리 - 초록색 동그라미
                    # 수익률 퍼센트 계산 (가격 변동률)
                    entry_price = trade.get('entry_price', 0)
                    if entry_price > 0 and price > 0:
                        price_change_pct = ((price - entry_price) / entry_price) * 100
                        pnl_text = f"{capital_change:+.2f} ({price_change_pct:+.2f}%)"
                    else:
                        pnl_text = f"{capital_change:+.2f}"
                elif capital_change < 0:
                    pnl_symbol = "🔴"  # 패배 - 빨간색 동그라미
                    # 수익률 퍼센트 계산 (가격 변동률)
                    entry_price = trade.get('entry_price', 0)
                    if entry_price > 0 and price > 0:
                        price_change_pct = ((price - entry_price) / entry_price) * 100
                        pnl_text = f"{capital_change:+.2f} ({price_change_pct:+.2f}%)"
                    else:
                        pnl_text = f"{capital_change:+.2f}"
                else:
                    pnl_symbol = "⚪"  # 무승부 - 흰색 동그라미
                    pnl_text = "0.00"
                
                #print(f"{i:2d}. {timestamp} | {action:<15} | ${price:8.2f} | {shares:8.2f}주 | {pnl_symbol} {pnl_text}")
            
            # if len(trades) > 10:
            #     print(f"... (총 {len(trades)}개 거래 중 최근 10개만 표시)")
            
            # 거래 통계
            winning_trades = [t for t in trades if t.get('capital_change', 0) > 0]
            losing_trades = [t for t in trades if t.get('capital_change', 0) < 0]
            
            #print(f"   📊 승리: {len(winning_trades)}회, 패배: {len(losing_trades)}회")
            if winning_trades:
                avg_win = sum(t.get('capital_change', 0) for t in winning_trades) / len(winning_trades)
                #print(f"   📈 평균 승리: ${avg_win:.2f}")
            if losing_trades:
                avg_loss = sum(t.get('capital_change', 0) for t in losing_trades) / len(losing_trades)
                #print(f"   📉 평균 패배: ${avg_loss:.2f}")
            
            # 파일에 모든 거래 기록 저장
            with open(trade_file, 'a', encoding='utf-8') as f:
                f.write(f"전체 거래 기록 ({len(trades)}회):\n")
                f.write("순번 | 시간                | 액션            | 가격      | 수량      | 수익/손실\n")
                f.write("-" * 80 + "\n")
                
                for i, trade in enumerate(trades, 1):
                    timestamp = trade.get('timestamp', 'N/A')
                    action = trade.get('action', 'N/A')
                    price = trade.get('price', 0)
                    shares = trade.get('shares', 0)
                    capital_change = trade.get('capital_change', 0)
                    
                    # 승패 동그라미 + 퍼센트 추가
                    if capital_change > 0:
                        pnl_symbol = "🟢"
                        entry_price = trade.get('entry_price', 0)
                        if entry_price > 0 and price > 0:
                            price_change_pct = ((price - entry_price) / entry_price) * 100
                            pnl_text = f"{pnl_symbol} {capital_change:+8.2f} ({price_change_pct:+5.2f}%)"
                        else:
                            pnl_text = f"{pnl_symbol} {capital_change:+8.2f}"
                    elif capital_change < 0:
                        pnl_symbol = "🔴"
                        entry_price = trade.get('entry_price', 0)
                        if entry_price > 0 and price > 0:
                            price_change_pct = ((price - entry_price) / entry_price) * 100
                            pnl_text = f"{pnl_symbol} {capital_change:+8.2f} ({price_change_pct:+5.2f}%)"
                        else:
                            pnl_text = f"{pnl_symbol} {capital_change:+8.2f}"
                    else:
                        pnl_symbol = "⚪"
                        pnl_text = f"{pnl_symbol} {capital_change:+8.2f}"
                    
                    f.write(f"{i:4d} | {str(timestamp):<19} | {action:<15} | ${price:8.2f} | {shares:8.2f} | {pnl_text}\n")
                
                f.write(f"\n거래 통계:\n")
                f.write(f"승리: {len(winning_trades)}회, 패배: {len(losing_trades)}회\n")
                if winning_trades:
                    avg_win = sum(t.get('capital_change', 0) for t in winning_trades) / len(winning_trades)
                    f.write(f"평균 승리: ${avg_win:.2f}\n")
                if losing_trades:
                    avg_loss = sum(t.get('capital_change', 0) for t in losing_trades) / len(losing_trades)
                    f.write(f"평균 패배: ${avg_loss:.2f}\n")
                f.write("\n" + "=" * 80 + "\n\n")
        
        print(f"\n💾 거래 기록이 파일로 저장되었습니다: {trade_file}")

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
    parser.add_argument('--year', type=int, default=2023, help='백테스트 연도 (기본값: 2022)')
    parser.add_argument('--start-year', type=int, help='연속 백테스트 시작 연도')
    parser.add_argument('--end-year', type=int, help='연속 백테스트 종료 연도')
    parser.add_argument('--capital', type=float, default=100000, help='초기 자본 (기본값: 100000)')
    parser.add_argument('--start', help='시작 날짜 (YYYY-MM-DD)')
    parser.add_argument('--end', help='종료 날짜 (YYYY-MM-DD)')
    parser.add_argument('--test-random', action='store_true', help='랜덤 함수 테스트 실행')
    
    args = parser.parse_args()
    
    # 백테스트 실행
    strategy_system = MAAdaptiveStrategySystem(initial_capital=args.capital)
    
    # 랜덤 함수 테스트
    if args.test_random:
        print("🧪 결정적 랜덤 함수 테스트 시작!")
        print("=" * 60)
        
        # 1% 확률 테스트 (100번 중 1번)
        strategy_system.test_deterministic_random(1000, 0.01)
        print()
        
        # 5% 확률 테스트 (100번 중 5번)
        strategy_system.test_deterministic_random(1000, 0.05)
        print()
        
        # 10% 확률 테스트 (100번 중 10번)
        strategy_system.test_deterministic_random(1000, 0.10)
        print()
        
        # 0.1% 확률 테스트 (1000번 중 1번)
        strategy_system.test_deterministic_random(1000, 0.001)
        print()
        
        print("✅ 랜덤 함수 테스트 완료!")
        return
    
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
