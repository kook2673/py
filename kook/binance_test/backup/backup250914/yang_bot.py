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
    def __init__(self, initial_balance: float = 10000, leverage: int = 5):
        """
        바이낸스 양방향봇7 백테스트 클래스 (실제 거래봇과 동일한 전략)
        
        Args:
            initial_balance: 초기 자본금 (USDT)
            leverage: 레버리지 (40배)
        """
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.leverage = leverage
        
        # 전략 파라미터 (실제 거래봇과 동일)
        self.target_revenue_rate = 0.15  # 목표 수익률 0.15% (더 현실적으로 조정)
        self.charge = 0.08  # 수수료 0.08% (실제 거래봇과 동일)
        self.investment_ratio = 1  # 투자비율 100%
        self.divide = 400  # 400등분 (실제 거래봇과 동일)
        self.max_asset_units = 200  # 최대 자산 사용량을 200개로 제한 (더 보수적)
        self.water_rate = -0.3  # 물타기 비율
        
        # 트레일링스탑 파라미터 (MA 청산 대신 트레일링스탑만 사용)
        self.trailing_stop_enabled = True  # 트레일링스탑 활성화
        self.trailing_stop_trigger = 0.3  # 트레일링스탑 트리거 수익률 0.3%
        self.trailing_stop_distance = 0.15  # 트레일링스탑 거리 0.15%
        self.pair_profit_target = 0.8  # 한 쌍 목표 수익률 0.8%
        self.use_ma_exit = False  # MA 신호로 청산하지 않음
        
        # 포지션 관리 (실제 거래봇과 동일한 구조)
        self.slots = []  # 슬롯 리스트 (dic["item"]과 동일)
        self.slot_no = 0  # 슬롯 번호 (dic["no"]와 동일)
        self.total_invested_capital = 0  # 총 투자된 자본
        self.max_investment_ratio = 0  # 최대 투자 비율
        self.asset_units_used = 0  # 사용된 자산 단위 개수 (400개 제한)
        
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
        try:
            rolling_mean = df['close'].rolling(window=period).mean()
            if offset >= len(rolling_mean) or offset < 0:
                return df['close'].iloc[0]  # 기본값 반환
            return rolling_mean.iloc[offset]
        except:
            return df['close'].iloc[0]  # 오류 시 기본값 반환
    
    def get_first_amount(self, coin_price: float) -> float:
        """첫 매수 수량 계산 (실제 거래봇과 동일한 로직)"""
        # 레버리지에 따른 최대 매수 가능 수량 (실제 거래봇과 동일)
        max_amount = round((self.initial_balance * self.investment_ratio) / coin_price, 3) * self.leverage
        
        # 최대 매수수량의 1%에 해당하는 수량을 구한다 (400등분)
        one_percent_amount = max_amount / self.divide
        
        # 첫 매수 비중을 구한다 (실제 거래봇과 동일)
        first_amount = round((one_percent_amount * 1.0) - 0.0005, 3)
        
        # 최소 수량 체크 (0.001 BTC)
        if first_amount < 0.001:
            first_amount = 0.001
        
        return first_amount
    
    def calculate_revenue_rate(self, entry_price: float, current_price: float, is_short: bool) -> float:
        """수익률 계산"""
        if is_short:
            return (entry_price - current_price) / entry_price * 100.0
        else:
            return (current_price - entry_price) / entry_price * 100.0
    
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
        """새 슬롯 추가 (실제 거래봇과 동일한 로직)"""
        self.slot_no += 1
        
        # 실제 투자된 자본 계산 (실제 거래봇과 동일)
        invested_capital = (abs(amount) * price) / self.leverage
        
        # 사용된 자산 단위 개수 계산 (20달러 = 1개 단위)
        asset_units = invested_capital / 20
        
        # 자산 사용량 제한 체크 (더 보수적으로 제한)
        if self.asset_units_used + asset_units > self.max_asset_units:
            print(f"⚠️ 경고: 자산 사용량 한계 도달! ({self.asset_units_used:.1f}/{self.max_asset_units}개)")
            print(f"⚠️ 새로운 포지션 진입을 중단합니다.")
            print(f"🔍 디버깅: amount={amount}, price={price}, invested_capital={invested_capital:.2f}, asset_units={asset_units:.1f}")
            return  # 예외를 발생시키지 않고 단순히 리턴
        
        self.asset_units_used += asset_units
        self.total_invested_capital += invested_capital
        
        # 투자 비율 계산
        investment_ratio = (self.total_invested_capital / self.initial_balance) * 100
        self.max_investment_ratio = max(self.max_investment_ratio, investment_ratio)
        
        slot = {
            'no': self.slot_no,
            'type': slot_type,
            'price': price,
            'amt': round(amount, 3),  # 실제 거래봇과 동일하게 3자리 반올림
            'invested_capital': invested_capital,
            'position_value': abs(amount) * price,
            'asset_units': asset_units,
            'highest_profit': 0.0,  # 최고 수익률
            'trailing_stop_price': None,  # 트레일링스탑 가격
            'pair_id': None  # 쌍 포지션 ID
        }
        
        self.slots.append(slot)
    
    def remove_slot(self, index: int) -> Dict:
        """슬롯 제거"""
        removed_slot = self.slots.pop(index)
        # 투자된 자본에서 차감
        self.total_invested_capital -= removed_slot.get('invested_capital', 0)
        # 사용된 자산 단위에서 차감
        self.asset_units_used -= removed_slot.get('asset_units', 0)
        return removed_slot
    
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
    
    def update_trailing_stop(self, current_price: float) -> List[int]:
        """트레일링스탑 업데이트 및 청산할 슬롯 반환"""
        slots_to_close = []
        
        for i, slot in enumerate(self.slots):
            is_short = slot['amt'] < 0
            revenue_rate = self.calculate_revenue_rate(slot['price'], current_price, is_short)
            
            # 최고 수익률 업데이트
            if revenue_rate > slot['highest_profit']:
                self.slots[i]['highest_profit'] = revenue_rate
                
                # 트레일링스탑 트리거 조건 확인
                if revenue_rate >= self.trailing_stop_trigger:
                    if is_short:
                        # 숏 포지션: 가격이 하락할 때 트레일링스탑 설정
                        self.slots[i]['trailing_stop_price'] = current_price * (1 + self.trailing_stop_distance / 100)
                    else:
                        # 롱 포지션: 가격이 상승할 때 트레일링스탑 설정
                        self.slots[i]['trailing_stop_price'] = current_price * (1 - self.trailing_stop_distance / 100)
            
            # 트레일링스탑 가격이 설정되어 있고, 현재 가격이 트레일링스탑을 터치한 경우
            if slot['trailing_stop_price'] is not None:
                if is_short and current_price >= slot['trailing_stop_price']:
                    slots_to_close.append(i)
                elif not is_short and current_price <= slot['trailing_stop_price']:
                    slots_to_close.append(i)
        
        return slots_to_close
    
    def find_pair_slots(self) -> List[Tuple[int, int]]:
        """쌍 포지션 찾기 (같은 크기의 롱/숏 포지션)"""
        pairs = []
        used_indices = set()
        
        # 롱 포지션과 숏 포지션을 분리
        long_slots = [(i, slot) for i, slot in enumerate(self.slots) if slot['amt'] > 0 and i not in used_indices]
        short_slots = [(i, slot) for i, slot in enumerate(self.slots) if slot['amt'] < 0 and i not in used_indices]
        
        # 가장 비슷한 크기의 포지션끼리 매칭
        for long_idx, long_slot in long_slots:
            if long_idx in used_indices:
                continue
                
            best_match = None
            best_diff = float('inf')
            
            for short_idx, short_slot in short_slots:
                if short_idx in used_indices:
                    continue
                    
                # 크기 차이 계산
                size_diff = abs(long_slot['amt'] - abs(short_slot['amt']))
                
                # 가장 비슷한 크기 찾기 (0.01 이내)
                if size_diff < best_diff and size_diff < 0.01:
                    best_match = short_idx
                    best_diff = size_diff
            
            if best_match is not None:
                pairs.append((long_idx, best_match))
                used_indices.add(long_idx)
                used_indices.add(best_match)
        
        return pairs
    
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
        """MA 신호 체크 (실제 거래봇과 동일)"""
        if current_idx < 20:  # 충분한 데이터가 없으면 False
            return {'short_signal': False, 'long_signal': False, 'short_exit': False, 'long_exit': False}
        
        # MA 계산 (실제 거래봇과 동일한 방식)
        ma5 = [self.calculate_ma(df, 5, current_idx - 2),
               self.calculate_ma(df, 5, current_idx - 3),
               self.calculate_ma(df, 5, current_idx - 4)]
        ma20 = self.calculate_ma(df, 20, current_idx - 2)
        
        # 실제 거래봇의 신호 체크 로직
        # 숏 신호: 5일선이 20일선 위에 있는데 5일선이 하락추세로 꺾였을때
        short_signal = ma5[0] > ma20 and ma5[2] < ma5[1] and ma5[1] > ma5[0]
        
        # 롱 신호: 5일선이 20일선 아래에 있는데 5일선이 상승추세로 꺾였을때
        long_signal = ma5[0] < ma20 and ma5[2] > ma5[1] and ma5[1] < ma5[0]
        
        # 청산 신호 (실제 거래봇과 동일)
        short_exit = ma5[0] < ma20 and ma5[2] > ma5[1] and ma5[1] < ma5[0]
        long_exit = ma5[0] > ma20 and ma5[2] < ma5[1] and ma5[1] > ma5[0]
        
        return {
            'short_signal': short_signal,
            'long_signal': long_signal,
            'short_exit': short_exit,
            'long_exit': long_exit
        }
    
    
    
    
    
    def run_backtest(self, df: pd.DataFrame, start_date: str = None, end_date: str = None) -> Dict:
        """백테스트 실행 (실제 거래봇과 동일한 로직)"""
        print("백테스트 시작...")
        
        # 날짜 필터링
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
            
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
            
            # MA 계산 (실제 거래봇과 동일)
            if i < 20:  # 충분한 데이터가 없으면 스킵
                self.balance_history.append(self.current_balance)
                self.slot_count_history.append(len(self.slots))
                continue
                
            ma5 = [self.calculate_ma(df, 5, i - 2),
                   self.calculate_ma(df, 5, i - 3),
                   self.calculate_ma(df, 5, i - 4)]
            ma20 = self.calculate_ma(df, 20, i - 2)
            
            # 첫 매수 비중 계산
            first_amount = self.get_first_amount(current_price)
            
            # 트레일링스탑 체크 (기존 포지션이 있는 경우)
            if len(self.slots) > 0:
                slots_to_close = self.update_trailing_stop(current_price)
                if slots_to_close:
                    for idx in sorted(slots_to_close, reverse=True):
                        slot = self.slots[idx]
                        is_short = slot['amt'] < 0
                        revenue_rate = self.calculate_revenue_rate(slot['price'], current_price, is_short)
                        
                        # 청산 실행
                        fee = self.execute_trade('buy' if is_short else 'sell', abs(slot['amt']), current_price)
                        
                        # 선물 거래 손익 계산
                        if is_short:
                            my_rate_dollar = (slot['price'] - current_price) * abs(slot['amt']) - fee
                        else:
                            my_rate_dollar = (current_price - slot['price']) * abs(slot['amt']) - fee
                        
                        # 잔고에 손익 반영
                        self.current_balance += my_rate_dollar
                        
                        # 청산 표시
                        direction = "숏" if is_short else "롱"
                        profit_loss = "수익" if my_rate_dollar > 0 else "손실"
                        print(f"🎯 {direction} 트레일링스탑 청산: {current_price:.2f} USDT, {profit_loss}: {my_rate_dollar:.2f} USDT")
                        
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
                        
                        # 슬롯 제거
                        self.remove_slot(idx)
            
            # 쌍 포지션 체크 (같은 크기의 롱/숏 포지션이 있으면 쌍으로 청산)
            pairs = self.find_pair_slots()
            for long_idx, short_idx in pairs:
                long_slot = self.slots[long_idx]
                short_slot = self.slots[short_idx]
                
                # 롱 포지션 수익률
                long_revenue = self.calculate_revenue_rate(long_slot['price'], current_price, False)
                # 숏 포지션 수익률
                short_revenue = self.calculate_revenue_rate(short_slot['price'], current_price, True)
                
                # 쌍 포지션 총 수익률
                pair_total_revenue = (long_revenue + short_revenue) / 2
                
                # 쌍 포지션 목표 수익률 달성 시 청산
                if pair_total_revenue >= self.pair_profit_target:
                    # 롱 포지션 청산
                    fee_long = self.execute_trade('sell', abs(long_slot['amt']), current_price)
                    long_pnl = (current_price - long_slot['price']) * abs(long_slot['amt']) - fee_long
                    
                    # 숏 포지션 청산
                    fee_short = self.execute_trade('buy', abs(short_slot['amt']), current_price)
                    short_pnl = (short_slot['price'] - current_price) * abs(short_slot['amt']) - fee_short
                    
                    total_pnl = long_pnl + short_pnl
                    self.current_balance += total_pnl
                    
                    print(f"💎 쌍 포지션 청산: 롱 {long_revenue:.2f}%, 숏 {short_revenue:.2f}%, 총 {pair_total_revenue:.2f}%, 수익: {total_pnl:.2f} USDT")
                    
                    # 거래 기록
                    self.trades.append({
                        'time': current_time,
                        'side': 'close_pair',
                        'price': current_price,
                        'amount': abs(long_slot['amt']),
                        'revenue_rate': pair_total_revenue,
                        'pnl': total_pnl,
                        'slot_type': 'pair'
                    })
                    
                    if total_pnl > 0:
                        self.winning_trades += 1
                    else:
                        self.losing_trades += 1
                    
                    # 슬롯 제거 (큰 인덱스부터 제거)
                    self.remove_slot(max(long_idx, short_idx))
                    self.remove_slot(min(long_idx, short_idx))
            
            # 포지션이 없는 경우
            if len(self.slots) == 0:
                # 숏포지션 : 5일선이 20일선 위에 있는데 5일선이 하락추세로 꺾였을때
                if ma5[0] > ma20 and ma5[2] < ma5[1] and ma5[1] > ma5[0]:
                    self.add_slot(current_price, -first_amount, 'N')
                    self.execute_trade('sell', first_amount, current_price)
                    self.total_trades += 1
                    print(f"🔴 숏 진입: {current_price:.2f} USDT, 수량: {first_amount:.3f} BTC, 자산사용: {self.asset_units_used:.1f}/400개")
                
                # 롱포지션 : 5일선이 20일선 아래에 있는데 5일선이 상승추세로 꺾였을때
                if ma5[0] < ma20 and ma5[2] > ma5[1] and ma5[1] < ma5[0]:
                    self.add_slot(current_price, first_amount, 'N')
                    self.execute_trade('buy', first_amount, current_price)
                    self.total_trades += 1
                    print(f"🟢 롱 진입: {current_price:.2f} USDT, 수량: {first_amount:.3f} BTC, 자산사용: {self.asset_units_used:.1f}/400개")
            
            # 포지션이 있는 경우
            else:
                # 현재 포지션 분석 (실제 거래봇과 동일)
                amt_s2 = 0  # 숏 총합
                amt_l2 = 0  # 롱 총합
                amount_s = first_amount  # 숏 구매갯수 초기화
                amount_l = first_amount  # 롱 구매갯수 초기화
                
                max_revenue_index = None
                max_revenue = float('-inf')
                
                for j, item in enumerate(reversed(self.slots)):
                    revenue_rate = (current_price - item["price"]) / item["price"] * 100.0
                    if item["amt"] < 0:
                        revenue_rate = revenue_rate * -1.0
                        amt_s2 += abs(item["amt"])
                    else:
                        amt_l2 += abs(item["amt"])
                    
                    if revenue_rate > max_revenue:
                        max_revenue = revenue_rate
                        max_revenue_index = len(self.slots) - j - 1
                
                # 수량 조정 (실제 거래봇과 동일)
                amt = amt_l2 - amt_s2
                if amt < 0:  # 숏을 많이 가지고 있다는 얘기
                    if first_amount * 2 < abs(amt):
                        amount_l = round(abs(amt * 0.5) - 0.0005, 3)
                else:  # 롱을 많이 가지고 있다는 얘기
                    if first_amount * 2 < abs(amt):
                        amount_s = round(abs(amt * 0.5) - 0.0005, 3)
                
                
                # 마지막 포지션이 수익이 나지 않고 멀어졌을 경우 새로운 포지션 (더 엄격한 조건)
                if max_revenue < -(self.target_revenue_rate * 5):  # 5배로 더 엄격하게
                    # 숏포지션 : 5일선이 하락추세로 꺾였을때
                    if ma5[2] < ma5[1] and ma5[1] > ma5[0]:
                        self.add_slot(current_price, -amount_s, 'N')
                        self.execute_trade('sell', amount_s, current_price)
                        self.total_trades += 1
                        print(f"🔴 숏 추가: {current_price:.2f} USDT, 수량: {amount_s:.3f} BTC, 자산사용: {self.asset_units_used:.1f}/400개")
                    
                    # 롱포지션 : 5일선이 상승추세로 꺾였을때
                    if ma5[2] > ma5[1] and ma5[1] < ma5[0]:
                        self.add_slot(current_price, amount_l, 'N')
                        self.execute_trade('buy', amount_l, current_price)
                        self.total_trades += 1
                        print(f"🟢 롱 추가: {current_price:.2f} USDT, 수량: {amount_l:.3f} BTC, 자산사용: {self.asset_units_used:.1f}/400개")
                
                # 손실이 클 때만 추가 포지션 진입 (트레일링스탑으로 청산하므로 간단하게)
                elif max_revenue < -(self.target_revenue_rate * 2):  # 2배 손실 시에만
                    # 숏포지션 : 5일선이 하락추세로 꺾였을때
                    if ma5[2] < ma5[1] and ma5[1] > ma5[0]:
                        self.add_slot(current_price, -amount_s, 'N')
                        self.execute_trade('sell', amount_s, current_price)
                        self.total_trades += 1
                        print(f"🔴 숏 추가: {current_price:.2f} USDT, 수량: {amount_s:.3f} BTC")
                    
                    # 롱포지션 : 5일선이 상승추세로 꺾였을때
                    if ma5[2] > ma5[1] and ma5[1] < ma5[0]:
                        self.add_slot(current_price, amount_l, 'N')
                        self.execute_trade('buy', amount_l, current_price)
                        self.total_trades += 1
                        print(f"🟢 롱 추가: {current_price:.2f} USDT, 수량: {amount_l:.3f} BTC")
            
            # 기록 저장 (매 루프마다)
            self.balance_history.append(self.current_balance)
            self.slot_count_history.append(len(self.slots))
            
            # 매 1000번째 루프마다 슬롯 개수 출력
            if i % 1000 == 0 and i > 0:
                # 현재 포지션의 미실현 손익 계산
                unrealized_pnl = 0
                for slot in self.slots:
                    is_short = slot['amt'] < 0
                    if is_short:
                        unrealized_pnl += (slot['price'] - current_price) * abs(slot['amt'])
                    else:
                        unrealized_pnl += (current_price - slot['price']) * abs(slot['amt'])
                
                total_balance = self.current_balance + unrealized_pnl
                
                # 실제 투자 비율 계산
                current_investment_ratio = (self.total_invested_capital / self.initial_balance) * 100
                slots_used_ratio = (len(self.slots) / self.divide) * 100
                
                # 총 포지션 가치 계산
                total_position_value = sum(slot.get('position_value', 0) for slot in self.slots)
                
                print(f"진행률: {i/len(df)*100:.1f}% - 슬롯: {len(self.slots)}개, 자산사용: {self.asset_units_used:.1f}개/{self.max_asset_units}개, 실제투자: {self.total_invested_capital:.2f} USDT ({current_investment_ratio:.2f}%), 포지션가치: {total_position_value:.2f} USDT, 잔고: {self.current_balance:.2f} USDT, 총자산: {total_balance:.2f} USDT (미실현: {unrealized_pnl:.2f})")
            
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
            "total_invested_capital": self.total_invested_capital,
            "max_investment_ratio": self.max_investment_ratio,
            "current_investment_ratio": (self.total_invested_capital / self.initial_balance) * 100,
            "current_slots": current_slots_info
        }
    
    def plot_results(self, df: pd.DataFrame):
        """결과 시각화"""
        fig, axes = plt.subplots(3, 1, figsize=(15, 12))
        
        # 가격 차트
        axes[0].plot(df.index, df['close'], label='BTC Price', alpha=0.7)
        axes[0].set_title(f'BTC Price - {df.index[0].strftime("%Y-%m-%d")} ~ {df.index[-1].strftime("%Y-%m-%d")}')
        axes[0].set_ylabel('Price (USDT)')
        axes[0].legend()
        axes[0].grid(True)
        
        # 잔고 변화 (날짜 인덱스 사용)
        axes[1].plot(df.index, self.balance_history, label='Balance', color='green')
        axes[1].axhline(y=self.initial_balance, color='red', linestyle='--', alpha=0.7, label=f'Initial Balance ({self.initial_balance:,.0f} USDT)')
        axes[1].set_title('Balance History')
        axes[1].set_ylabel('Balance (USDT)')
        axes[1].legend()
        axes[1].grid(True)
        
        # 슬롯 수 변화 (날짜 인덱스 사용)
        axes[2].plot(df.index, self.slot_count_history, label='Slot Count', color='orange')
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
        df = pd.read_csv(r'c:\work\GitHub\py\kook\binance\data\BTC_USDT\1m\2024-01.csv')
        
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
        dates = pd.date_range('2024-01-01', '2024-01-31', freq='1min')
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
    
    # 백테스트 실행 (실제 거래봇과 동일한 파라미터)
    bot = BinanceYangBot7Backtest(initial_balance=10000, leverage=40)
    results = bot.run_backtest(df)
    
    print("\n=== 백테스트 결과 ===")
    print(f"백테스트 기간: 2024년 1월 1일 ~ 2024년 1월 31일 (1개월)")
    print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
    print(f"최종 자본: {results['final_balance']:,.0f} USDT (수수료 + 실현손익만 반영)")
    print(f"총 자산: {results['total_balance']:,.0f} USDT (미실현 손익 포함)")
    print(f"미실현 손익: {results['unrealized_pnl']:,.0f} USDT")
    print(f"총 손익: {results['total_pnl']:,.0f} USDT")
    print(f"총 수익률: {results['total_return']:.2f}%")
    print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
    print(f"총 거래 횟수: {results['total_trades']}회")
    print(f"승률: {results['win_rate']:.2f}%")
    print(f"최대 사용 슬롯: {results['max_slots_used']}개")
    print(f"현재 슬롯 수: {results['final_slot_count']}개")
    print(f"실제 투자된 자본: {results['total_invested_capital']:,.2f} USDT")
    print(f"현재 투자 비율: {results['current_investment_ratio']:.2f}%")
    print(f"최대 투자 비율: {results['max_investment_ratio']:.2f}%")
    print(f"자산 사용량: {bot.asset_units_used:.1f}/{bot.max_asset_units}개")
    
    # 현재 슬롯 리스트 출력
    if results['current_slots']:
        print("\n=== 현재 보유 슬롯 ===")
        for slot in results['current_slots']:
            direction = "숏" if slot['is_short'] else "롱"
            print(f"슬롯 #{slot['no']} ({slot['type']}): {direction} {slot['price']:.2f} USDT, 수량: {slot['amount']:.3f}")
    else:
        print("\n=== 현재 보유 슬롯 ===")
        print("보유 중인 슬롯이 없습니다.")
    
    # 결과 시각화
    bot.plot_results(df)
