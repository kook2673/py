import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import pandas as pd
import numpy as np
import datetime as dt
import json
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

class BinanceYangBot7Backtest:
    def __init__(self, initial_balance: float = 10000, leverage: int = 20):
        """
        바이낸스 양방향봇7 백테스트 클래스
        
        Args:
            initial_balance: 초기 자본금 (USDT)
            leverage: 레버리지 (5배로 완화)
        """
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.leverage = leverage
        
        # 전략 파라미터
        self.target_revenue_rate = 0.3  # 목표 수익률 0.3%
        self.charge = 0.1  # 수수료 0.08%
        self.investment_ratio = 0.5  # 투자비율 50%로 완화
        self.divide = 400  # 400등분
        self.water_rate = -0.3  # 물타기 비율
        
        # 포지션 관리 (실제 바이낸스 방식)
        self.long_position = {'amount': 0.0, 'enter_price': 0.0}  # 롱 포지션
        self.short_position = {'amount': 0.0, 'enter_price': 0.0}  # 숏 포지션
        self.slots = []  # 슬롯 리스트 (내부 논리용)
        self.slot_no = 0  # 슬롯 번호
        
        # 성과 추적
        self.trades = []  # 거래 기록
        self.daily_pnl = []  # 일별 손익
        self.balance_history = []  # 잔고 변화
        self.slot_count_history = []  # 슬롯 수 변화
        
        # 통계
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.max_drawdown = 0
        self.peak_balance = initial_balance
        
    def calculate_ma(self, df: pd.DataFrame, period: int, offset: int = 0) -> float:
        """이동평균 계산"""
        return df['close'].rolling(window=period).mean().iloc[offset]
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14, offset: int = 0) -> float:
        """ATR (Average True Range) 계산 - 변동성 측정"""
        if offset + period >= len(df):
            return 0.0
        
        high = df['high'].iloc[offset:offset+period]
        low = df['low'].iloc[offset:offset+period]
        close = df['close'].iloc[offset:offset+period]
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.mean()
        return atr
    
    def calculate_bb_width(self, df: pd.DataFrame, period: int = 20, std: float = 2.0, offset: int = 0) -> float:
        """볼린저 밴드 폭 계산"""
        if offset + period >= len(df):
            return 0.0
        
        close_data = df['close'].iloc[offset:offset+period]
        sma = close_data.mean()
        std_dev = close_data.std()
        
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        
        bb_width = (upper_band - lower_band) / sma * 100
        return bb_width
    
    def calculate_sideways_volatility(self, df: pd.DataFrame, current_idx: int, atr_period: int = 14, bb_period: int = 20) -> float:
        """횡보 변동성 측정 (파형크기)"""
        if current_idx < max(atr_period, bb_period):
            return 0.0
        
        # ATR 계산
        atr = self.calculate_atr(df, atr_period, current_idx - atr_period)
        
        # BB Width 계산  
        bb_width = self.calculate_bb_width(df, bb_period, 2.0, current_idx - bb_period)
        
        # 현재 가격 대비 변동성
        current_price = df['close'].iloc[current_idx]
        atr_pct = (atr / current_price) * 100
        
        # 횡보 점수 (낮을수록 횡보, 높을수록 트렌드)
        sideways_score = (atr_pct + bb_width) / 2
        
        return sideways_score
    
    
    def calculate_ma_slope_score(self, df: pd.DataFrame, current_idx: int) -> float:
        """이동평균선 기울기 점수 계산"""
        if current_idx < 5:
            return 0.0
        
        # 5일, 10일, 20일, 60일, 120일선 기울기 계산
        ma5_slope = (self.calculate_ma(df, 5, current_idx) - self.calculate_ma(df, 5, current_idx-5)) / 5
        ma10_slope = (self.calculate_ma(df, 10, current_idx) - self.calculate_ma(df, 10, current_idx-5)) / 5
        ma20_slope = (self.calculate_ma(df, 20, current_idx) - self.calculate_ma(df, 20, current_idx-5)) / 5
        ma60_slope = (self.calculate_ma(df, 60, current_idx) - self.calculate_ma(df, 60, current_idx-5)) / 5
        ma120_slope = (self.calculate_ma(df, 120, current_idx) - self.calculate_ma(df, 120, current_idx-5)) / 5
        
        # 가중평균으로 최종 기울기 점수
        slope_score = (ma5_slope * 0.4 + ma10_slope * 0.3 + ma20_slope * 0.2 + 
                      ma60_slope * 0.1 + ma120_slope * 0.1)
        
        return slope_score
    
    def calculate_ma_alignment_score(self, df: pd.DataFrame, current_idx: int) -> float:
        """이동평균선 배열 점수 계산"""
        if current_idx < 120:
            return 0.0
        
        current_price = df['close'].iloc[current_idx]
        ma5 = self.calculate_ma(df, 5, current_idx)
        ma10 = self.calculate_ma(df, 10, current_idx)
        ma20 = self.calculate_ma(df, 20, current_idx)
        ma60 = self.calculate_ma(df, 60, current_idx)
        ma120 = self.calculate_ma(df, 120, current_idx)
        
        # 상승 추세: price > ma5 > ma10 > ma20 > ma60 > ma120
        if current_price > ma5 > ma10 > ma20 > ma60 > ma120:
            return 1.0  # 강한 상승
        elif current_price > ma5 > ma10 > ma20 > ma60:
            return 0.7  # 중간 상승
        elif current_price > ma5 > ma10:
            return 0.3  # 약한 상승
        elif current_price < ma5 < ma10 < ma20 < ma60 < ma120:
            return -1.0  # 강한 하락
        elif current_price < ma5 < ma10 < ma20 < ma60:
            return -0.7  # 중간 하락
        elif current_price < ma5 < ma10:
            return -0.3  # 약한 하락
        else:
            return 0.0  # 횡보
    
    def calculate_price_position_score(self, df: pd.DataFrame, current_idx: int) -> float:
        """가격 위치 점수 계산"""
        if current_idx < 60:
            return 0.0
        
        current_price = df['close'].iloc[current_idx]
        ma20 = self.calculate_ma(df, 20, current_idx)
        ma60 = self.calculate_ma(df, 60, current_idx)
        
        # 20일선 대비 위치
        ma20_ratio = (current_price / ma20 - 1) * 100
        
        # 60일선 대비 위치  
        ma60_ratio = (current_price / ma60 - 1) * 100
        
        # 위치 점수 계산
        position_score = (ma20_ratio * 0.6 + ma60_ratio * 0.4) / 100
        
        return position_score
    
    def calculate_slot_imbalance_score(self) -> float:
        """슬롯 불균형 점수 계산"""
        if not self.slots:
            return 0.0
        
        long_count = len([s for s in self.slots if s['amt'] > 0])
        short_count = len([s for s in self.slots if s['amt'] < 0])
        total_count = len(self.slots)
        
        # 롱/숏 비율 불균형 점수
        imbalance_ratio = (long_count - short_count) / total_count
        
        return imbalance_ratio
    
    def calculate_momentum_score(self, df: pd.DataFrame, current_idx: int) -> float:
        """모멘텀 점수 계산 (기존 Average_Momentum 활용)"""
        if current_idx < 100:
            return 0.0
        
        # 10일마다 총 100일 평균모멘텀스코어 계산
        specific_days = [i * 10 for i in range(1, 11)]  # 10, 20, 30, ..., 100일
        
        momentum_scores = []
        for day in specific_days:
            if current_idx >= day:
                prev_close = df['close'].iloc[current_idx - day]
                current_close = df['close'].iloc[current_idx]
                momentum_scores.append(1 if prev_close > current_close else 0)
        
        if not momentum_scores:
            return 0.0
        
        # 평균 모멘텀 점수 (0.0 ~ 1.0)
        avg_momentum = sum(momentum_scores) / len(momentum_scores)
        
        # 0.0 ~ 1.0 범위를 -1.0 ~ +1.0으로 변환
        return (avg_momentum - 0.5) * 2
    
    def calculate_trend_score(self, df: pd.DataFrame, current_idx: int) -> float:
        """최종 추세 점수 계산"""
        # 1. 모멘텀 점수 (30%)
        momentum_score = self.calculate_momentum_score(df, current_idx)
        
        # 2. 이동평균선 기울기 점수 (40%)
        slope_score = self.calculate_ma_slope_score(df, current_idx)
        
        # 3. 이동평균선 배열 점수 (20%)
        alignment_score = self.calculate_ma_alignment_score(df, current_idx)
        
        # 4. 슬롯 불균형 점수 (10%)
        imbalance_score = self.calculate_slot_imbalance_score()
        
        # 최종 추세 점수 (-1.0 ~ +1.0)
        trend_score = (momentum_score * 0.3 + slope_score * 0.4 + 
                      alignment_score * 0.2 + imbalance_score * 0.1)
        
        return trend_score
    
    def get_first_amount(self, coin_price: float) -> float:
        """첫 매수 비중 계산 (선물 거래) - 100분할 기준"""
        # 전체 자본의 0.25% 사용 (레버리지 5배 적용)
        # 400분할이므로 0.25%씩 사용
        position_value = self.current_balance * 0.0025 * self.leverage
        first_amount = position_value / coin_price
        
        return max(round(first_amount, 3), 0.001)  # 최소 수량
    
    def calculate_revenue_rate(self, entry_price: float, current_price: float, is_short: bool) -> float:
        """수익률 계산"""
        if is_short:
            return (entry_price - current_price) / entry_price * 100.0
        else:
            return (current_price - entry_price) / entry_price * 100.0
    
    def check_liquidation(self, current_price: float) -> bool:
        """청산 체크 (마진 레벨 100% 기준)"""
        liquidation_triggered = False
        
        # 롱 포지션 청산 체크 (마진 레벨 100% 이하 시 청산)
        if self.long_position['amount'] > 0:
            # 마진 레벨 계산: (계정 잔고 + 미실현 손익) / 마진 요구량
            position_value = self.long_position['amount'] * current_price
            unrealized_pnl = (current_price - self.long_position['enter_price']) * self.long_position['amount']
            margin_required = position_value / self.leverage
            margin_level = (self.current_balance + unrealized_pnl) / margin_required
            
            if margin_level <= 1.0:  # 마진 레벨 100% 이하 시 청산
                # 청산 손실 계산
                liquidation_loss = (self.long_position['enter_price'] - current_price) * self.long_position['amount']
                fee = current_price * self.long_position['amount'] * self.charge * 0.01
                total_loss = liquidation_loss + fee
                
                # 자산에서 손실 차감
                self.current_balance -= total_loss
                
                # 손실률 계산
                long_pnl_rate = self.calculate_revenue_rate(self.long_position['enter_price'], current_price, False)
                
                # 거래 기록 추가
                trade = {
                    'time': current_price,  # 임시로 가격 사용
                    'side': 'liquidation_long',
                    'price': current_price,
                    'amount': self.long_position['amount'],
                    'revenue_rate': long_pnl_rate,
                    'pnl': -total_loss,
                    'slot_type': 'LIQUIDATION'
                }
                self.trades.append(trade)
                self.losing_trades += 1
                self.total_trades += 1
                
                print(f"🚨 롱 포지션 청산! 가격: {current_price:.2f}, 마진레벨: {margin_level:.2f}, 손실률: {long_pnl_rate:.2f}%, 손실: {total_loss:.2f} USDT")
                self.long_position = {'amount': 0.0, 'enter_price': 0.0}
                liquidation_triggered = True
        
        # 숏 포지션 청산 체크 (마진 레벨 100% 이하 시 청산)
        if self.short_position['amount'] > 0:
            # 마진 레벨 계산: (계정 잔고 + 미실현 손익) / 마진 요구량
            position_value = self.short_position['amount'] * current_price
            unrealized_pnl = (self.short_position['enter_price'] - current_price) * self.short_position['amount']
            margin_required = position_value / self.leverage
            margin_level = (self.current_balance + unrealized_pnl) / margin_required
            
            if margin_level <= 1.0:  # 마진 레벨 100% 이하 시 청산
                # 청산 손실 계산
                liquidation_loss = (current_price - self.short_position['enter_price']) * self.short_position['amount']
                fee = current_price * self.short_position['amount'] * self.charge * 0.01
                total_loss = liquidation_loss + fee
                
                # 자산에서 손실 차감
                self.current_balance -= total_loss
                
                # 손실률 계산
                short_pnl_rate = self.calculate_revenue_rate(self.short_position['enter_price'], current_price, True)
                
                # 거래 기록 추가
                trade = {
                    'time': current_price,  # 임시로 가격 사용
                    'side': 'liquidation_short',
                    'price': current_price,
                    'amount': self.short_position['amount'],
                    'revenue_rate': short_pnl_rate,
                    'pnl': -total_loss,
                    'slot_type': 'LIQUIDATION'
                }
                self.trades.append(trade)
                self.losing_trades += 1
                self.total_trades += 1
                
                print(f"🚨 숏 포지션 청산! 가격: {current_price:.2f}, 마진레벨: {margin_level:.2f}, 손실률: {short_pnl_rate:.2f}%, 손실: {total_loss:.2f} USDT")
                self.short_position = {'amount': 0.0, 'enter_price': 0.0}
                liquidation_triggered = True
        
        return liquidation_triggered
    
    def update_position_average_price(self, is_long: bool, new_amount: float, new_price: float):
        """포지션 평균가 업데이트"""
        if is_long:
            if self.long_position['amount'] == 0:
                # 새로운 롱 포지션
                self.long_position = {'amount': new_amount, 'enter_price': new_price}
            else:
                # 기존 롱 포지션에 추가
                total_value = (self.long_position['amount'] * self.long_position['enter_price'] + 
                             new_amount * new_price)
                total_amount = self.long_position['amount'] + new_amount
                self.long_position['enter_price'] = total_value / total_amount
                self.long_position['amount'] = total_amount
        else:
            if self.short_position['amount'] == 0:
                # 새로운 숏 포지션
                self.short_position = {'amount': new_amount, 'enter_price': new_price}
            else:
                # 기존 숏 포지션에 추가
                total_value = (self.short_position['amount'] * self.short_position['enter_price'] + 
                             new_amount * new_price)
                total_amount = self.short_position['amount'] + new_amount
                self.short_position['enter_price'] = total_value / total_amount
                self.short_position['amount'] = total_amount
    
    def get_max_revenue_info(self, current_price: float) -> Tuple[int, float]:
        """최대 수익률 슬롯 정보 반환"""
        max_revenue = float('-inf')
        max_revenue_index = None
        
        for i, slot in enumerate(self.slots):
            is_short = slot['amt'] < 0
            revenue_rate = self.calculate_revenue_rate(slot['price'], current_price, is_short)
            
            if revenue_rate > max_revenue:
                max_revenue = revenue_rate
                max_revenue_index = i
                
        return max_revenue_index, max_revenue
    
    def add_slot(self, price: float, amount: float, slot_type: str) -> None:
        """새 슬롯 추가"""
        self.slot_no += 1
        slot = {
            'no': self.slot_no,
            'type': slot_type,
            'price': price,
            'amt': amount
        }
        self.slots.append(slot)
    
    def remove_slot(self, index: int) -> Dict:
        """슬롯 제거"""
        return self.slots.pop(index)
    
    def update_slot_prices_with_cap(self, cap: float) -> None:
        """수익 발생 시 슬롯 가격 조정 (물타기 효과)"""
        if len(self.slots) == 0 or cap <= 0:
            return
            
        cap_per_slot = cap / len(self.slots)
        
        for i, slot in enumerate(self.slots):
            if slot['amt'] > 0:  # 롱 포지션
                self.slots[i]['price'] = round(((slot['price'] * abs(slot['amt'])) - cap_per_slot) / abs(slot['amt']), 2)
            else:  # 숏 포지션
                self.slots[i]['price'] = round(((slot['price'] * abs(slot['amt'])) + cap_per_slot) / abs(slot['amt']), 2)
    
    def execute_trade(self, side: str, amount: float, price: float, fee: float = None) -> float:
        """거래 실행 시뮬레이션 (선물 거래)"""
        if fee is None:
            fee = price * abs(amount) * self.charge * 0.01
        
        # 선물 거래에서는 실제 현금이 나가지 않음
        # 포지션만 생성/청산하고, 손익은 청산 시에만 실현
        # 수수료만 차감
        self.current_balance -= fee
            
        return fee
    
    def check_ma_signals(self, df: pd.DataFrame, current_idx: int) -> Dict[str, bool]:
        """MA 신호 체크 (첨부 소스 기준)"""
        if current_idx < 20:  # 충분한 데이터가 없으면 False
            return {'short_signal': False, 'long_signal': False, 'short_exit': False, 'long_exit': False}
        
        # MA 계산 (첨부 소스와 동일한 방식)
        ma5 = [self.calculate_ma(df, 5, current_idx - 2),
               self.calculate_ma(df, 5, current_idx - 3),
               self.calculate_ma(df, 5, current_idx - 4)]
        ma20 = self.calculate_ma(df, 20, current_idx - 2)
        
        # 신호 체크 (첨부 소스와 동일)
        short_signal = ma5[0] > ma20 and ma5[2] < ma5[1] and ma5[1] > ma5[0]
        long_signal = ma5[0] < ma20 and ma5[2] > ma5[1] and ma5[1] < ma5[0]
        short_exit = ma5[0] < ma20 and ma5[2] > ma5[1] and ma5[1] < ma5[0]
        long_exit = ma5[0] > ma20 and ma5[2] < ma5[1] and ma5[1] > ma5[0]
        
        return {
            'short_signal': short_signal,
            'long_signal': long_signal,
            'short_exit': short_exit,
            'long_exit': long_exit
        }
    
    # 이벤트 관련 함수 제거
    
    def run_backtest(self, df: pd.DataFrame, start_date: str = None, end_date: str = None, sample_rate: int = 1) -> Dict:
        """백테스트 실행"""
        print("백테스트 시작...")
        
        # 날짜 필터링
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        # 데이터 샘플링 (속도 향상)
        if sample_rate > 1:
            df = df.iloc[::sample_rate]
            print(f"데이터 샘플링 적용: {sample_rate}분봉 사용")
            
        # 날짜 인덱스 유지 (reset_index 제거)
        print(f"백테스트 데이터 기간: {df.index[0]} ~ {df.index[-1]}")
        print(f"총 데이터 포인트: {len(df)}개")
        
        # 초기화
        self.current_balance = self.initial_balance
        self.slots = []
        self.slot_no = 0
        self.trades = []
        self.daily_pnl = []
        self.balance_history = []
        self.slot_count_history = []
        
        for i in range(len(df)):
            current_price = df['close'].iloc[i]
            current_time = df.index[i]
            
            # 청산 체크 (매 봉마다 체크)
            liquidation_triggered = self.check_liquidation(current_price)
            if liquidation_triggered:
                # 청산 시 모든 슬롯 초기화
                self.slots = []
                continue
            
            # 시간 정보 (일*100 + 시간)
            time_info = int(current_time.day * 100 + current_time.hour)
            
            # 추세 점수 계산
            trend_score = self.calculate_trend_score(df, i)
            
            # 파형크기 계산 (횡보 변동성)
            sideways_volatility = self.calculate_sideways_volatility(df, i)
            
            # 파형크기 기반 수익구간 변환
            # 횡보일 때는 낮은 수익률, 트렌드일 때는 높은 수익률
            if sideways_volatility < 2.0:  # 횡보 (파형크기 작음)
                dynamic_target_revenue = self.target_revenue_rate * 0.5  # 0.15%
            elif sideways_volatility < 4.0:  # 중간 변동성
                dynamic_target_revenue = self.target_revenue_rate * 1.0  # 0.24%
            else:  # 강한 트렌드 (파형크기 큼)
                dynamic_target_revenue = self.target_revenue_rate * 1.5  # 0.45%
            
            # MA 신호 체크
            ma_signals = self.check_ma_signals(df, i)
            
            # 첫 매수 비중 계산
            first_amount = self.get_first_amount(current_price)
            
            # 포지션이 없는 경우
            if len(self.slots) == 0:
                # 방향성 감지 기반 진입 결정
                if ma_signals['short_signal'] and trend_score < -0.3:  # 하락 신호 + 하락 추세
                    self.add_slot(current_price, -first_amount, 'N')
                    self.execute_trade('sell', first_amount, current_price)
                    self.update_position_average_price(False, first_amount, current_price)  # 숏 포지션 평균가 업데이트
                    self.total_trades += 1
                    print(f"🟢 첫 숏 진입! 가격: {current_price:.2f}, 수량: {first_amount:.3f}, 추세점수: {trend_score:.3f}, 파형크기: {sideways_volatility:.2f}")
                    
                elif ma_signals['long_signal'] and trend_score > 0.3:  # 상승 신호 + 상승 추세
                    self.add_slot(current_price, first_amount, 'N')
                    self.execute_trade('buy', first_amount, current_price)
                    self.update_position_average_price(True, first_amount, current_price)  # 롱 포지션 평균가 업데이트
                    self.total_trades += 1
                    print(f"🔴 첫 롱 진입! 가격: {current_price:.2f}, 수량: {first_amount:.3f}, 추세점수: {trend_score:.3f}, 파형크기: {sideways_volatility:.2f}")
            
            # 포지션이 있는 경우
            else:
                # 현재 포지션 분석
                amt_s2 = sum(abs(slot['amt']) for slot in self.slots if slot['amt'] < 0)
                amt_l2 = sum(abs(slot['amt']) for slot in self.slots if slot['amt'] > 0)
                
                # 최대 수익률 정보
                max_revenue_index, max_revenue = self.get_max_revenue_info(current_price)
                
                # 방향성 감지 기반 전략
                if abs(trend_score) > 0.7:  # 강한 추세 (한방향으로 움직임)
                    # 강한 추세에서는 반대 방향 진입 금지
                    if trend_score > 0.7:  # 강한 상승 추세
                        # 롱 포지션만 유지, 숏 포지션 청산
                        if amt_s2 > 0:  # 숏 포지션이 있으면 청산
                            # 숏 포지션 청산 로직 (기존 청산 로직 활용)
                            pass
                    elif trend_score < -0.7:  # 강한 하락 추세
                        # 숏 포지션만 유지, 롱 포지션 청산
                        if amt_l2 > 0:  # 롱 포지션이 있으면 청산
                            # 롱 포지션 청산 로직 (기존 청산 로직 활용)
                            pass
                else:  # 횡보 (-0.7 < trend_score < 0.7)
                    # 기존 로직 유지 - 횡보에서는 양방향 거래 허용
                    if max_revenue < -(self.target_revenue_rate * 3):
                        if (ma_signals['short_signal'] and trend_score < -0.3 and 
                            amt_l2 > amt_s2):  # 하락 신호 + 롱 포지션 많음
                            amount_s = first_amount
                            if first_amount * 2 < abs(amt_l2 - amt_s2):
                                amount_s = round(abs((amt_l2 - amt_s2) * 0.5) - 0.0005, 3)
                            
                            self.add_slot(current_price, -amount_s, 'N')
                            self.execute_trade('sell', amount_s, current_price)
                            self.update_position_average_price(False, amount_s, current_price)
                            self.total_trades += 1
                            print(f"🟢 횡보 숏 진입! 가격: {current_price:.2f}, 수량: {amount_s:.3f}, 슬롯수: {len(self.slots)}, 추세점수: {trend_score:.3f}")
                            
                        elif (ma_signals['long_signal'] and trend_score > 0.3 and 
                              amt_s2 > amt_l2):  # 상승 신호 + 숏 포지션 많음
                            amount_l = first_amount
                            if first_amount * 2 < abs(amt_s2 - amt_l2):
                                amount_l = round(abs((amt_s2 - amt_l2) * 0.5) - 0.0005, 3)
                            
                            self.add_slot(current_price, amount_l, 'N')
                            self.execute_trade('buy', amount_l, current_price)
                            self.update_position_average_price(True, amount_l, current_price)
                            self.total_trades += 1
                            print(f"🔴 횡보 롱 진입! 가격: {current_price:.2f}, 수량: {amount_l:.3f}, 슬롯수: {len(self.slots)}, 추세점수: {trend_score:.3f}")
                
                    # 반대 방향 진입 (횡보에서만)
                    elif max_revenue < -self.target_revenue_rate:
                        if (max_revenue_index is not None and 
                            self.slots[max_revenue_index]['amt'] < 0 and 
                            ma_signals['long_signal'] and trend_score > 0.3):  # 숏 포지션 손실 + 상승 신호
                            amount_l = first_amount
                            if amt_s2 > amt_l2 and first_amount * 2 < abs(amt_s2 - amt_l2):
                                amount_l = round(abs((amt_s2 - amt_l2) * 0.5) - 0.0005, 3)
                            
                            self.add_slot(current_price, amount_l, 'N')
                            self.execute_trade('buy', amount_l, current_price)
                            self.update_position_average_price(True, amount_l, current_price)
                            self.total_trades += 1
                            print(f"🔴 반대 롱 진입! 가격: {current_price:.2f}, 수량: {amount_l:.3f}, 슬롯수: {len(self.slots)}, 추세점수: {trend_score:.3f}")
                            
                        elif (max_revenue_index is not None and 
                              self.slots[max_revenue_index]['amt'] > 0 and 
                              ma_signals['short_signal'] and trend_score < -0.3):  # 롱 포지션 손실 + 하락 신호
                            amount_s = first_amount
                            if amt_l2 > amt_s2 and first_amount * 2 < abs(amt_l2 - amt_s2):
                                amount_s = round(abs((amt_l2 - amt_s2) * 0.5) - 0.0005, 3)
                            
                            self.add_slot(current_price, -amount_s, 'N')
                            self.execute_trade('sell', amount_s, current_price)
                            self.update_position_average_price(False, amount_s, current_price)
                            self.total_trades += 1
                            print(f"🟢 반대 숏 진입! 가격: {current_price:.2f}, 수량: {amount_s:.3f}, 슬롯수: {len(self.slots)}, 추세점수: {trend_score:.3f}")
                
                # 수익 확인 및 청산 (동적 수익률 적용)
                if max_revenue >= -dynamic_target_revenue:
                    cap = 0.0
                    isbuy = None
                    remove_indices = []
                    
                    for j, slot in enumerate(reversed(self.slots)):
                        is_short = slot['amt'] < 0
                        revenue_rate = self.calculate_revenue_rate(slot['price'], current_price, is_short)
                        
                        # 청산 조건 체크 (수익률 우선, MA 신호는 보조)
                        should_close = False
                        if is_short and revenue_rate >= dynamic_target_revenue:
                            # 숏 포지션: 수익률 달성 시 청산 (MA 신호는 참고만)
                            should_close = True
                            isbuy = "long"
                        elif not is_short and revenue_rate >= dynamic_target_revenue:
                            # 롱 포지션: 수익률 달성 시 청산 (MA 신호는 참고만)
                            should_close = True
                            isbuy = "short"
                        
                        if should_close:
                            # 청산 실행
                            fee = self.execute_trade('buy' if is_short else 'sell', abs(slot['amt']), current_price)
                            
                            # 선물 거래 손익 계산 (레버리지는 이미 수량에 반영됨)
                            if is_short:
                                # 숏 포지션 청산: (진입가 - 청산가) * 수량
                                my_rate_dollar = (slot['price'] - current_price) * abs(slot['amt'])
                            else:
                                # 롱 포지션 청산: (청산가 - 진입가) * 수량
                                my_rate_dollar = (current_price - slot['price']) * abs(slot['amt'])
                            
                            # 수수료 차감
                            my_rate_dollar -= fee
                            
                            # 잔고에 손익 반영
                            self.current_balance += my_rate_dollar
                            
                            # 청산 print
                            direction = "숏" if is_short else "롱"
                            print(f"💰 {direction} 청산! 가격: {current_price:.2f}, 수익률: {revenue_rate:.2f}%, 손익: {my_rate_dollar:.2f} USDT, 슬롯수: {len(self.slots)}")
                            
                            if len(self.slots) > 1:
                                my_rate_dollar = my_rate_dollar / 2
                                cap += my_rate_dollar
                            
                            # 거래 기록
                            trade = {
                                'time': current_time,
                                'side': 'close_short' if is_short else 'close_long',
                                'price': current_price,
                                'amount': abs(slot['amt']),
                                'revenue_rate': revenue_rate,
                                'pnl': my_rate_dollar,
                                'slot_type': slot['type']
                            }
                            self.trades.append(trade)
                            
                            if my_rate_dollar > 0:
                                self.winning_trades += 1
                            else:
                                self.losing_trades += 1
                            
                            remove_indices.append(len(self.slots) - j - 1)
                    
                    # 슬롯 제거
                    for idx in sorted(remove_indices, reverse=True):
                        self.remove_slot(idx)
                    
                    # 물타기 효과 적용
                    if cap > 0:
                        self.update_slot_prices_with_cap(cap)
                    
                    # 반대 포지션 진입
                    if isbuy and len(self.slots) > 0:
                        # 최대 수익률 재계산
                        max_revenue_index, max_revenue = self.get_max_revenue_info(current_price)
                        
                        target_revenue_rate2 = -(dynamic_target_revenue * 3) if isbuy == "short" else -dynamic_target_revenue
                        
                        # 방향성 감지: 강한 추세에서는 반대 진입 금지
                        if max_revenue < target_revenue_rate2 and abs(trend_score) <= 0.7:  # 횡보에서만 반대 진입
                            if isbuy == "short":
                                amount_s = first_amount
                                if amt_s2 > amt_l2 and first_amount * 2 < abs(amt_s2 - amt_l2):
                                    amount_s = round(abs((amt_s2 - amt_l2) * 0.5) - 0.0005, 3)
                                
                                self.add_slot(current_price, -amount_s, 'N')
                                self.execute_trade('sell', amount_s, current_price)
                                self.update_position_average_price(False, amount_s, current_price)
                                self.total_trades += 1
                                print(f"🟢 청산후 숏 진입! 가격: {current_price:.2f}, 수량: {amount_s:.3f}, 슬롯수: {len(self.slots)}")
                                
                            elif isbuy == "long":
                                amount_l = first_amount
                                if amt_l2 > amt_s2 and first_amount * 2 < abs(amt_l2 - amt_s2):
                                    amount_l = round(abs((amt_l2 - amt_s2) * 0.5) - 0.0005, 3)
                                
                                self.add_slot(current_price, amount_l, 'N')
                                self.execute_trade('buy', amount_l, current_price)
                                self.update_position_average_price(True, amount_l, current_price)
                                self.total_trades += 1
                                print(f"🔴 청산후 롱 진입! 가격: {current_price:.2f}, 수량: {amount_l:.3f}, 슬롯수: {len(self.slots)}")
            
            # 이벤트 관련 코드 제거
            
            # 손절 로직 제거 - 마진 콜만 체크
            if len(self.slots) > 0:
                # 마진 콜 체크만 유지
                total_margin_required = sum(abs(slot['amt']) * current_price / self.leverage for slot in self.slots)
                # 마진의 50% 이하로 떨어지면 강제 청산
                if self.current_balance < total_margin_required * 0.5:  
                    print(f"마진 콜 발생! 잔고: {self.current_balance:.2f}, 필요 마진: {total_margin_required:.2f}")
                    # 모든 포지션 강제 청산
                    for slot in self.slots:
                        is_short = slot['amt'] < 0
                        fee = self.execute_trade('buy' if is_short else 'sell', abs(slot['amt']), current_price)
                        
                        if is_short:
                            pnl = (slot['price'] - current_price) * abs(slot['amt']) - fee
                        else:
                            pnl = (current_price - slot['price']) * abs(slot['amt']) - fee
                        
                        self.current_balance += pnl
                    
                    self.slots = []
            
            # 기록 저장 (매 루프마다)
            self.balance_history.append(self.current_balance)
            self.slot_count_history.append(len(self.slots))
            
            # 매 5000번째 루프마다 슬롯 개수 출력 (속도 향상)
            if i % 5000 == 0 and i > 0:
                used_divisions = len(self.slots) / self.divide * 100  # 400등분 중 사용률
                
                # 현재 포지션의 미실현 손익 계산
                unrealized_pnl = 0
                for slot in self.slots:
                    is_short = slot['amt'] < 0
                    if is_short:
                        unrealized_pnl += (slot['price'] - current_price) * abs(slot['amt'])
                    else:
                        unrealized_pnl += (current_price - slot['price']) * abs(slot['amt'])
                
                total_balance = self.current_balance + unrealized_pnl
                print(f"진행률: {i/len(df)*100:.1f}% - 현재 슬롯: {len(self.slots)}개 (400중 {len(self.slots)}개 사용), 잔고: {self.current_balance:.2f} USDT, 총자산: {total_balance:.2f} USDT (미실현: {unrealized_pnl:.2f}), 추세점수: {trend_score:.3f}, 파형크기: {sideways_volatility:.2f}, 동적수익률: {dynamic_target_revenue:.3f}%")
            
            # 최대 낙폭 계산
            if self.current_balance > self.peak_balance:
                self.peak_balance = self.current_balance
            else:
                drawdown = (self.peak_balance - self.current_balance) / self.peak_balance * 100
                self.max_drawdown = max(self.max_drawdown, drawdown)
        
        print("백테스트 완료!")
        final_price = df['close'].iloc[-1] if len(df) > 0 else 0
        return self.get_results(final_price)
    
    def get_results(self, final_price: float = None) -> Dict:
        """백테스트 결과 반환"""
        if not self.trades:
            return {"error": "거래 기록이 없습니다."}
        
        total_pnl = self.current_balance - self.initial_balance
        total_return = (total_pnl / self.initial_balance) * 100
        
        win_rate = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        
        # 현재 슬롯 정보 계산
        current_slots_info = []
        unrealized_pnl = 0
        for slot in self.slots:
            is_short = slot['amt'] < 0
            current_slots_info.append({
                'no': slot['no'],
                'type': slot['type'],
                'price': slot['price'],
                'amount': slot['amt'],
                'is_short': is_short
            })
            
            # 미실현 손익 계산 (마지막 가격 기준)
            if final_price is not None:
                if is_short:
                    unrealized_pnl += (slot['price'] - final_price) * abs(slot['amt'])
                else:
                    unrealized_pnl += (final_price - slot['price']) * abs(slot['amt'])
        
        total_balance = self.current_balance + unrealized_pnl
        
        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.current_balance,
            "total_balance": total_balance,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "max_drawdown": self.max_drawdown,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "final_slot_count": len(self.slots),
            "max_slots_used": max(self.slot_count_history) if self.slot_count_history else 0,
            "current_slots": current_slots_info,
            "long_position": self.long_position,
            "short_position": self.short_position
        }
    
    def plot_results(self, df: pd.DataFrame, sample_rate: int = 1):
        """결과 시각화"""
        fig, axes = plt.subplots(3, 1, figsize=(15, 12))
        
        # 데이터 샘플링 적용 (백테스트와 동일하게)
        if sample_rate > 1:
            df_plot = df.iloc[::sample_rate]
        else:
            df_plot = df
        
        # 가격 차트
        axes[0].plot(df_plot.index, df_plot['close'], label='BTC Price', alpha=0.7)
        axes[0].set_title(f'BTC Price - {df_plot.index[0].strftime("%Y-%m-%d")} ~ {df_plot.index[-1].strftime("%Y-%m-%d")}')
        axes[0].set_ylabel('Price (USDT)')
        axes[0].legend()
        axes[0].grid(True)
        
        # 잔고 변화 (샘플링된 데이터 사용)
        axes[1].plot(df_plot.index, self.balance_history, label='Balance', color='green')
        axes[1].axhline(y=self.initial_balance, color='red', linestyle='--', alpha=0.7, label=f'Initial Balance ({self.initial_balance:,.0f} USDT)')
        axes[1].set_title('Balance History')
        axes[1].set_ylabel('Balance (USDT)')
        axes[1].legend()
        axes[1].grid(True)
        
        # 슬롯 수 변화 (샘플링된 데이터 사용)
        axes[2].plot(df_plot.index, self.slot_count_history, label='Slot Count', color='orange')
        axes[2].set_title('Slot Count History')
        axes[2].set_ylabel('Number of Slots')
        axes[2].set_xlabel('Date')
        axes[2].legend()
        axes[2].grid(True)
        
        # X축 날짜 포맷팅
        for ax in axes:
            ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.show()

# 사용 예시
if __name__ == "__main__":
    # 실제 바이낸스 데이터 로드
    try:
        print("실제 BTC 데이터 로딩 중...")
        # 1월~12월 데이터 로드
        dataframes = []
        months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
        
        for month in months:
            try:
                df_month = pd.read_csv(rf'c:\work\GitHub\py\kook\binance\data\BTC_USDT\1m\2024-{month}.csv')
                dataframes.append(df_month)
                print(f"2024-{month} 데이터 로드 완료: {len(df_month)}개")
            except FileNotFoundError:
                print(f"2024-{month} 데이터 파일을 찾을 수 없습니다.")
        
        # 데이터 합치기
        df = pd.concat(dataframes, ignore_index=True)
        
        # timestamp 컬럼을 datetime으로 변환하고 인덱스로 설정
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        
        print(f"실제 데이터 로드 완료: {len(df)}개 데이터 포인트")
        print(f"데이터 기간: {df.index[0]} ~ {df.index[-1]}")
        print(f"가격 범위: {df['close'].min():.2f} ~ {df['close'].max():.2f} USDT")
        
    except Exception as e:
        print(f"실제 데이터 로드 실패: {e}")
        print("가상 데이터를 생성합니다...")
        
        # 가상 데이터 생성 (백업)
        dates = pd.date_range('2024-01-01', '2024-12-31', freq='1min')
        np.random.seed(42)
        
        price_changes = np.random.normal(0, 0.001, len(dates))
        prices = [50000]
        
        for change in price_changes[1:]:
            prices.append(prices[-1] * (1 + change))
        
        df = pd.DataFrame({
            'open': prices,
            'high': [p * (1 + abs(np.random.normal(0, 0.002))) for p in prices],
            'low': [p * (1 - abs(np.random.normal(0, 0.002))) for p in prices],
            'close': prices,
            'volume': np.random.uniform(1000, 10000, len(dates))
        }, index=dates)
    
    # 백테스트 실행 (5분봉 샘플링으로 속도 향상)
    bot = BinanceYangBot7Backtest(initial_balance=10000, leverage=20)
    results = bot.run_backtest(df, sample_rate=5)  # 5분봉 사용
    
    print("\n=== 백테스트 결과 ===")
    print(f"백테스트 기간: 2024년 1월 1일 ~ 2024년 12월 31일 (1년)")
    print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
    print(f"최종 자본: {results['final_balance']:,.0f} USDT (수수료 + 실현손익만 반영)")
    print(f"총 자산: {results['total_balance']:,.0f} USDT (미실현 손익 포함)")
    print(f"미실현 손익: {results['unrealized_pnl']:,.0f} USDT")
    print(f"총 손익: {results['total_pnl']:,.0f} USDT")
    print(f"총 수익률: {results['total_return']:.2f}%")
    print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
    print(f"총 거래 횟수: {results['total_trades']}회")
    print(f"승률: {results['win_rate']:.2f}%")
    print(f"최대 사용 슬롯: {results['max_slots_used']}개 (100중 {results['max_slots_used']}개 사용)")
    print(f"현재 슬롯 수: {results['final_slot_count']}개 (100중 {results['final_slot_count']}개 사용)")
    
    # 실제 포지션 정보 출력
    print("\n=== 실제 포지션 현황 ===")
    if results['long_position']['amount'] > 0:
        long_pnl = (df['close'].iloc[-1] - results['long_position']['enter_price']) / results['long_position']['enter_price'] * 100
        print(f"롱 포지션: {results['long_position']['amount']:.3f}개, 평균가: {results['long_position']['enter_price']:.2f} USDT, 수익률: {long_pnl:.2f}%")
    else:
        print("롱 포지션: 없음")
    
    if results['short_position']['amount'] > 0:
        short_pnl = (results['short_position']['enter_price'] - df['close'].iloc[-1]) / results['short_position']['enter_price'] * 100
        print(f"숏 포지션: {results['short_position']['amount']:.3f}개, 평균가: {results['short_position']['enter_price']:.2f} USDT, 수익률: {short_pnl:.2f}%")
    else:
        print("숏 포지션: 없음")
    
    # 현재 슬롯 리스트 출력
    if results['current_slots']:
        print("\n=== 현재 보유 슬롯 ===")
        for slot in results['current_slots']:
            direction = "숏" if slot['is_short'] else "롱"
            print(f"슬롯 #{slot['no']} ({slot['type']}): {direction} {slot['price']:.2f} USDT, 수량: {slot['amount']:.3f}")
    else:
        print("\n=== 현재 보유 슬롯 ===")
        print("보유 중인 슬롯이 없습니다.")
    
    # 결과 시각화 (샘플링 비율 전달)
    bot.plot_results(df, sample_rate=5)
