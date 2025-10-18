# -*- coding: utf-8 -*-
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
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.leverage = leverage
        
        # 전략 파라미터
        self.target_revenue_rate = 0.3  # 목표 수익률 0.3%
        self.charge = 0.1  # 수수료 0.08%
        self.investment_ratio = 0.5  # 투자비율 50%로 완화
        self.divide = 400  # 400등분
        self.water_rate = -0.3  # 물타기 비율
        
        # 포지션 관리
        self.slots = []  # 슬롯 리스트
        self.events = []  # 이벤트 리스트
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
        
    def get_first_amount(self, coin_price: float) -> float:
        """첫 매수 비중 계산 (선물 거래) - 더 보수적 접근"""
        # 전체 자본의 0.2%만 사용 (레버리지 5배 적용)
        # 이는 실제 노출이 1%가 되도록 함
        position_value = self.current_balance * 0.002 * self.leverage
        first_amount = position_value / coin_price
        
        return max(round(first_amount, 3), 0.001)  # 최소 수량
    
    def calculate_revenue_rate(self, entry_price: float, current_price: float, is_short: bool) -> float:
        """수익률 계산"""
        if is_short:
            return (entry_price - current_price) / entry_price * 100.0
        else:
            return (current_price - entry_price) / entry_price * 100.0
    
    def execute_trade(self, side: str, amount: float, price: float, fee: float = None) -> float:
        """거래 실행 시뮬레이션 (선물 거래)"""
        if fee is None:
            fee = price * abs(amount) * self.charge * 0.01
        
        # 선물 거래에서는 실제 현금이 나가지 않음
        # 포지션만 생성/청산하고, 손익은 청산 시에만 실현
        # 수수료만 차감
        self.current_balance -= fee
            
        return fee
    
    def add_slot(self, price: float, amount: float, slot_type: str, time_info: int = None) -> None:
        """새 슬롯 추가"""
        self.slot_no += 1
        slot = {
            'no': self.slot_no,
            'type': slot_type,
            'price': price,
            'amt': amount,
            'time': time_info
        }
        self.slots.append(slot)
        
        if slot_type == 'E' and time_info:
            self.events.append(slot.copy())
    
    def run_simple_backtest(self, df: pd.DataFrame) -> Dict:
        """간단한 백테스트 실행"""
        print("간단한 백테스트 시작...")
        
        # 초기화
        self.current_balance = self.initial_balance
        self.slots = []
        self.events = []
        self.slot_no = 0
        self.trades = []
        self.balance_history = []
        self.slot_count_history = []
        
        # 간단한 전략: 가격이 1% 이상 변동하면 포지션 진입
        for i in range(1, len(df)):
            current_price = df['close'].iloc[i]
            prev_price = df['close'].iloc[i-1]
            
            price_change = (current_price - prev_price) / prev_price
            
            # 1% 이상 상승하면 롱 포지션
            if price_change > 0.01 and len(self.slots) == 0:
                amount = self.get_first_amount(current_price)
                self.add_slot(current_price, amount, 'N')
                self.execute_trade('buy', amount, current_price)
                self.total_trades += 1
                print(f"롱 포지션 진입: {current_price:.2f}, 수량: {amount:.3f}")
            
            # 1% 이상 하락하면 숏 포지션
            elif price_change < -0.01 and len(self.slots) == 0:
                amount = self.get_first_amount(current_price)
                self.add_slot(current_price, -amount, 'N')
                self.execute_trade('sell', amount, current_price)
                self.total_trades += 1
                print(f"숏 포지션 진입: {current_price:.2f}, 수량: {amount:.3f}")
            
            # 포지션이 있고 0.5% 이상 반대 방향으로 움직이면 청산
            elif len(self.slots) > 0:
                slot = self.slots[0]
                is_short = slot['amt'] < 0
                revenue_rate = self.calculate_revenue_rate(slot['price'], current_price, is_short)
                
                if (is_short and price_change > 0.005) or (not is_short and price_change < -0.005):
                    # 청산 실행
                    fee = self.execute_trade('buy' if is_short else 'sell', abs(slot['amt']), current_price)
                    
                    # 손익 계산
                    if is_short:
                        pnl = (slot['price'] - current_price) * abs(slot['amt']) - fee
                    else:
                        pnl = (current_price - slot['price']) * abs(slot['amt']) - fee
                    
                    self.current_balance += pnl
                    
                    print(f"포지션 청산: {current_price:.2f}, 손익: {pnl:.2f}")
                    
                    if pnl > 0:
                        self.winning_trades += 1
                    else:
                        self.losing_trades += 1
                    
                    self.slots = []
            
            # 기록 저장
            self.balance_history.append(self.current_balance)
            self.slot_count_history.append(len(self.slots))
        
        print("백테스트 완료!")
        return self.get_results()
    
    def get_results(self) -> Dict:
        """백테스트 결과 반환"""
        total_pnl = self.current_balance - self.initial_balance
        total_return = (total_pnl / self.initial_balance) * 100
        
        win_rate = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        
        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.current_balance,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "final_slot_count": len(self.slots),
            "max_slots_used": max(self.slot_count_history) if self.slot_count_history else 0
        }

# 테스트 실행
if __name__ == "__main__":
    # 가상 데이터 생성
    print("가상 데이터 생성 중...")
    dates = pd.date_range('2024-01-01', '2024-01-31', freq='1min')
    np.random.seed(42)
    
    price_changes = np.random.normal(0, 0.001, len(dates))
    prices = [42000]  # BTC 시작 가격
    
    for change in price_changes[1:]:
        prices.append(prices[-1] * (1 + change))
    
    df = pd.DataFrame({
        'open': prices,
        'high': [p * (1 + abs(np.random.normal(0, 0.002))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.002))) for p in prices],
        'close': prices,
        'volume': np.random.uniform(1000, 10000, len(dates))
    }, index=dates)
    
    print(f"데이터 생성 완료: {len(df)}개 데이터 포인트")
    print(f"가격 범위: {df['close'].min():.2f} ~ {df['close'].max():.2f} USDT")
    
    # 백테스트 실행
    bot = BinanceYangBot7Backtest(initial_balance=10000, leverage=5)
    results = bot.run_simple_backtest(df)
    
    print("\n=== 백테스트 결과 ===")
    print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
    print(f"최종 자본: {results['final_balance']:,.0f} USDT")
    print(f"총 손익: {results['total_pnl']:,.0f} USDT")
    print(f"총 수익률: {results['total_return']:.2f}%")
    print(f"총 거래 횟수: {results['total_trades']}회")
    print(f"승률: {results['win_rate']:.2f}%")
    print(f"최대 사용 슬롯: {results['max_slots_used']}개")
