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
    def __init__(self, initial_balance: float = 10000, leverage: int = 40):
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
        self.target_revenue_rate = 0.3  # 목표 수익률 0.3%
        self.charge = 0.08  # 수수료 0.08%
        self.investment_ratio = 1  # 투자비율 100%
        self.divide = 400  # 400등분
        self.water_rate = -0.3  # 물타기 비율
        
        # 포지션 관리
        self.slots = []  # 슬롯 리스트
        self.slot_no = 0  # 슬롯 번호
        self.events = []  # 이벤트 리스트
        
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
    
    def get_first_amount(self, coin_price: float) -> float:
        """첫 매수 비중 계산 (실제 거래봇과 동일)"""
        # 최대 매수 가능 수량 (레버리지 40배 적용)
        max_amount = (self.current_balance * self.investment_ratio * self.leverage) / coin_price
        
        # 400분할 중 1%에 해당하는 수량
        one_percent_amount = max_amount / self.divide
        
        # 첫 매수 비중 (1%)
        first_amount = round((one_percent_amount * 1.0) - 0.0005, 3)
        
        return max(first_amount, 0.001)  # 최소 수량
    
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
    
    def check_event(self, df: pd.DataFrame, current_idx: int, current_time) -> bool:
        """이벤트 체크 (실제 거래봇과 동일)"""
        if current_idx < 2:  # 1시간 데이터가 없으면 False
            return False
        
        # 시간 정보 (일*100 + 시간)
        time_info = int(current_time.day * 100 + current_time.hour)
        
        # 해당 시간대에 이벤트가 있는지 체크
        for event in self.events:
            if event["type"] == "E" and event["time"] == time_info:
                return True
        
        return False
    
    def add_event(self, price: float, amount: float, time_info: int) -> None:
        """이벤트 추가"""
        self.slot_no += 1
        event = {
            'no': self.slot_no,
            'type': 'E',
            'price': price,
            'amt': amount,
            'time': time_info
        }
        self.events.append(event)
        self.slots.append(event)
    
    def clean_old_events(self, current_time) -> None:
        """오래된 이벤트 정리"""
        time_info = int(current_time.day * 100 + current_time.hour)
        
        # 이벤트 정리 (실제 거래봇과 동일한 로직)
        for i in range(len(self.events) - 1, -1, -1):
            delidx = i
            for slot in self.slots:
                if slot["type"] == "E":
                    if self.events[i]["time"] == slot["time"]:
                        delidx = -1
            
            if delidx > -1 and self.events[i]["time"] != time_info:
                del self.events[i]
    
    def run_backtest(self, df: pd.DataFrame, start_date: str = None, end_date: str = None) -> Dict:
        """백테스트 실행"""
        print("백테스트 시작...")
        
        # 날짜 필터링
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
            
        # 날짜 인덱스 유지 (reset_index 제거)
        print(f"백테스트 데이터 기간: {df.index[0]} ~ {df.index[-1]}")
        print(f"총 데이터 포인트: {len(df)}개")
        
        # 초기화
        self.current_balance = self.initial_balance
        self.slots = []
        self.slot_no = 0
        self.events = []
        self.trades = []
        self.daily_pnl = []
        self.balance_history = []
        self.slot_count_history = []
        
        for i in range(len(df)):
            current_price = df['close'].iloc[i]
            current_time = df.index[i]
            
            # 시간 정보 (일*100 + 시간)
            time_info = int(current_time.day * 100 + current_time.hour)
            
            # MA 신호 체크
            ma_signals = self.check_ma_signals(df, i)
            
            # 첫 매수 비중 계산
            first_amount = self.get_first_amount(current_price)
            
            # 이벤트 정리
            self.clean_old_events(current_time)
            
            # 포지션이 없는 경우
            if len(self.slots) == 0:
                # 숏포지션 : 5일선이 20일선 위에 있는데 5일선이 하락추세로 꺾였을때
                if ma_signals['short_signal']:
                    self.add_slot(current_price, -first_amount, 'N')
                    self.execute_trade('sell', first_amount, current_price)
                    self.total_trades += 1
                
                # 롱포지션 : 5일선이 20일선 아래에 있는데 5일선이 상승추세로 꺾였을때
                if ma_signals['long_signal']:
                    self.add_slot(current_price, first_amount, 'N')
                    self.execute_trade('buy', first_amount, current_price)
                    self.total_trades += 1
            
            # 포지션이 있는 경우
            else:
                # 현재 포지션 분석
                amt_s2 = sum(abs(slot['amt']) for slot in self.slots if slot['amt'] < 0)
                amt_l2 = sum(abs(slot['amt']) for slot in self.slots if slot['amt'] > 0)
                
                # 최대 수익률 정보
                max_revenue_index, max_revenue = self.get_max_revenue_info(current_price)
                
                # 이벤트 체크 (실제 거래봇과 동일)
                bEvent = self.check_event(df, i, current_time)
                
                # 이벤트가 없는 경우 1시간봉 기준 1.3% 이상 변동시 이벤트 추가
                if not bEvent and current_time.minute > 0:
                    if i >= 2:  # 1시간 데이터가 있는지 확인
                        # 1시간봉 변동률 계산
                        per = (df['close'].iloc[i] / df['open'].iloc[i-1]) - 1
                        
                        if abs(per) >= 0.013:  # 1.3% 이상 변동
                            amount = round(((amt_l2 + amt_s2) / 2) - 0.0005, 3)
                            if amount < first_amount * 10:
                                amount = first_amount * 10
                            
                            if per > 0:  # 롱을 구매
                                self.add_event(current_price, amount, time_info)
                                self.execute_trade('buy', amount, current_price)
                                self.total_trades += 1
                            else:  # 숏을 구매
                                self.add_event(current_price, -amount, time_info)
                                self.execute_trade('sell', amount, current_price)
                                self.total_trades += 1
                
                # 마지막 포지션이 수익이 나지 않고 멀어졌을 경우 새로운 포지션
                if max_revenue < -(self.target_revenue_rate * 3):
                    # 숏포지션 : 5일선이 하락추세로 꺾였을때
                    if ma_signals['short_signal']:
                        amount_s = first_amount
                        if first_amount * 2 < abs(amt_l2 - amt_s2):
                            amount_s = round(abs((amt_l2 - amt_s2) * 0.5) - 0.0005, 3)
                        
                        self.add_slot(current_price, -amount_s, 'N')
                        self.execute_trade('sell', amount_s, current_price)
                        self.total_trades += 1
                    
                    # 롱포지션 : 5일선이 상승추세로 꺾였을때
                    if ma_signals['long_signal']:
                        amount_l = first_amount
                        if first_amount * 2 < abs(amt_s2 - amt_l2):
                            amount_l = round(abs((amt_s2 - amt_l2) * 0.5) - 0.0005, 3)
                        
                        self.add_slot(current_price, amount_l, 'N')
                        self.execute_trade('buy', amount_l, current_price)
                        self.total_trades += 1
                
                # 마지막이 숏이고 롱을 사야 하는 순간
                elif (max_revenue < -self.target_revenue_rate and 
                      max_revenue_index is not None and 
                      self.slots[max_revenue_index]['amt'] < 0 and 
                      ma_signals['long_signal']):
                    amount_l = first_amount
                    if first_amount * 2 < abs(amt_l2 - amt_s2):
                        amount_l = round(abs((amt_l2 - amt_s2) * 0.5) - 0.0005, 3)
                    
                    self.add_slot(current_price, amount_l, 'N')
                    self.execute_trade('buy', amount_l, current_price)
                    self.total_trades += 1
                
                # 마지막이 롱이고 숏을 사야 하는 순간
                elif (max_revenue < -self.target_revenue_rate and 
                      max_revenue_index is not None and 
                      self.slots[max_revenue_index]['amt'] > 0 and 
                      ma_signals['short_signal']):
                    amount_s = first_amount
                    if first_amount * 2 < abs(amt_s2 - amt_l2):
                        amount_s = round(abs((amt_s2 - amt_l2) * 0.5) - 0.0005, 3)
                    
                    self.add_slot(current_price, -amount_s, 'N')
                    self.execute_trade('sell', amount_s, current_price)
                    self.total_trades += 1
                
                # 수익이 났는지 확인
                else:
                    cap = 0.0
                    isbuy = None
                    remove_indices = []
                    
                    for j, slot in enumerate(reversed(self.slots)):
                        is_short = slot['amt'] < 0
                        revenue_rate = self.calculate_revenue_rate(slot['price'], current_price, is_short)
                        
                        # 청산 조건 체크 (실제 거래봇과 동일)
                        should_close = False
                        if is_short and ma_signals['short_exit'] and revenue_rate >= self.target_revenue_rate:
                            should_close = True
                            isbuy = "long"
                        elif not is_short and ma_signals['long_exit'] and revenue_rate >= self.target_revenue_rate:
                            should_close = True
                            isbuy = "short"
                        
                        if should_close:
                            # 청산 실행
                            fee = self.execute_trade('buy' if is_short else 'sell', abs(slot['amt']), current_price)
                            
                            # 선물 거래 손익 계산
                            if is_short:
                                my_rate_dollar = (slot['price'] - current_price) * abs(slot['amt']) - fee
                            else:
                                my_rate_dollar = (current_price - slot['price']) * abs(slot['amt']) - fee
                            
                            # 잔고에 손익 반영
                            self.current_balance += my_rate_dollar
                            
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
                        max_revenue_index, max_revenue = self.get_max_revenue_info(current_price)
                        
                        target_revenue_rate2 = -(self.target_revenue_rate * 3) if isbuy == "short" else -self.target_revenue_rate
                        
                        if max_revenue < target_revenue_rate2:
                            if isbuy == "short":
                                amount_s = first_amount
                                if amt_s2 > amt_l2 and first_amount * 2 < abs(amt_s2 - amt_l2):
                                    amount_s = round(abs((amt_s2 - amt_l2) * 0.5) - 0.0005, 3)
                                
                                self.add_slot(current_price, -amount_s, 'N')
                                self.execute_trade('sell', amount_s, current_price)
                                self.total_trades += 1
                                
                            elif isbuy == "long":
                                amount_l = first_amount
                                if amt_l2 > amt_s2 and first_amount * 2 < abs(amt_l2 - amt_s2):
                                    amount_l = round(abs((amt_l2 - amt_s2) * 0.5) - 0.0005, 3)
                                
                                self.add_slot(current_price, amount_l, 'N')
                                self.execute_trade('buy', amount_l, current_price)
                                self.total_trades += 1
            
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
                print(f"진행률: {i/len(df)*100:.1f}% - 현재 슬롯: {len(self.slots)}개 (400중 {len(self.slots)}개 사용), 잔고: {self.current_balance:.2f} USDT, 총자산: {total_balance:.2f} USDT (미실현: {unrealized_pnl:.2f})")
            
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
    
    # 백테스트 실행
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
    print(f"최대 사용 슬롯: {results['max_slots_used']}개 (400중 {results['max_slots_used']}개 사용)")
    print(f"현재 슬롯 수: {results['final_slot_count']}개 (400중 {results['final_slot_count']}개 사용)")
    
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
