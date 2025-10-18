import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import pandas as pd
import numpy as np
import datetime as dt
import json
import math
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

class WaterStrategyBotV2:
    def __init__(self, initial_balance: float = 10000, leverage: int = 10):
        """
        물타기 전략 봇 V2 (롱/숏 각 1개씩만 관리)
        
        Args:
            initial_balance: 초기 자본금 (USDT)
            leverage: 레버리지 (10배)
        """
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.leverage = leverage
        
        # 전략 파라미터
        self.charge = 0.05  # 수수료 0.1% (왕복 0.2%)
        self.divide = 514  # 200등분 (롱 100 + 숏 100)
        self.water_profit_ratio = 0.5  # 수익의 50%를 물타기에 사용
        
        # 물타기 시퀀스 (-5% 단위로 8번)
        self.water_levels = [-5, -5, -5, -5, -5, -5, -5, -5]  # -5% 단위로 8번
        self.max_water_level = 8  # 최대 물타기 횟수
        
        # 포지션 관리 (롱/숏 각 1개씩만)
        self.long_position = None  # 롱 포지션 (1개만)
        self.short_position = None  # 숏 포지션 (1개만)
        self.slot_no = 0  # 슬롯 번호
        
        # 성과 추적
        self.trades = []
        self.balance_history = []
        self.long_water_level_history = []
        self.short_water_level_history = []
        
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
                return df['close'].iloc[0]
            return rolling_mean.iloc[offset]
        except:
            return df['close'].iloc[0]
    
    def get_first_amount(self, coin_price: float) -> float:
        """첫 매수 수량 계산 (200등분 중 1등분)"""
        # 200등분 중 1등분 = 10,000 / 200 = 50 USDT
        one_division_amount = self.initial_balance / self.divide
        raw_amount = one_division_amount / coin_price
        
        # 0.001 단위로 올림
        first_amount = math.ceil(raw_amount * 1000) / 1000
        
        if first_amount < 0.001:
            first_amount = 0.001
        
        return first_amount
    
    def calculate_revenue_rate(self, entry_price: float, current_price: float, is_short: bool) -> float:
        """수익률 계산"""
        if is_short:
            return (entry_price - current_price) / entry_price * 100.0
        else:
            return (current_price - entry_price) / entry_price * 100.0
    
    def add_position(self, side: str, price: float, amount: float, water_level: int = 0) -> bool:
        """포지션 추가 (각 방향당 1개씩만)"""
        self.slot_no += 1
        
        slot = {
            'no': self.slot_no,
            'side': side,
            'price': price,  # 현재 진입 가격
            'base_price': price,  # 물타기 조정된 평균 단가
            'amt': round(amount, 3),
            'water_level': water_level,
            'invested_capital': (abs(amount) * price) / self.leverage,
            'position_value': abs(amount) * price,
            'highest_profit': 0.0
        }
        
        if side == "long":
            self.long_position = slot
        else:
            self.short_position = slot
            
        return True
    
    def remove_position(self, side: str) -> Dict:
        """포지션 제거"""
        if side == "long":
            removed_slot = self.long_position
            self.long_position = None
        else:
            removed_slot = self.short_position
            self.short_position = None
        return removed_slot
    
    def check_ma_signals(self, df: pd.DataFrame, current_idx: int) -> Dict[str, bool]:
        """MA 신호 체크 (미리 계산된 값 사용)"""
        if current_idx < 20:
            return {'short_signal': False, 'long_signal': False, 'short_exit': False, 'long_exit': False}
        
        # 미리 계산된 값 사용 (훨씬 빠름)
        return {
            'short_signal': df['short_signal'].iloc[current_idx],
            'long_signal': df['long_signal'].iloc[current_idx],
            'short_exit': df['short_exit'].iloc[current_idx],
            'long_exit': df['long_exit'].iloc[current_idx]
        }
    
    def execute_trade(self, side: str, amount: float, price: float) -> float:
        """거래 실행 시뮬레이션"""
        fee = price * abs(amount) * self.charge * 0.01
        # 모든 거래에서 수수료를 잔고에서 차감 (라이브 환경과 동일)
        self.current_balance -= fee
        return fee
    
    def close_position(self, slot: Dict, current_price: float) -> float:
        """포지션 청산"""
        is_short = slot['side'] == 'short'
        revenue_rate = self.calculate_revenue_rate(slot['price'], current_price, is_short)
        
        # 청산 실행 (수수료 차감)
        fee = self.execute_trade('buy' if is_short else 'sell', abs(slot['amt']), current_price)
        
        # 손익 계산 (수수료는 이미 잔고에서 차감됨)
        if is_short:
            pnl = (slot['price'] - current_price) * abs(slot['amt'])
        else:
            pnl = (current_price - slot['price']) * abs(slot['amt'])
        
        # 잔고에 반영 (순수익만, 수수료는 이미 차감됨)
        self.current_balance += pnl
        
        # 거래 기록
        trade = {
            'time': current_price,  # 간단히 가격으로 대체
            'side': f'close_{slot["side"]}',
            'price': current_price,
            'amount': abs(slot['amt']),
            'revenue_rate': revenue_rate,
            'pnl': pnl,
            'water_level': slot['water_level']
        }
        self.trades.append(trade)
        
        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
            
        return pnl
    
    def check_exit_conditions(self, current_price: float, ma_signals: Dict[str, bool]) -> List[str]:
        """청산 조건 체크 (0.3% 이상 수익 + 반대 신호)"""
        positions_to_close = []
        
        # 롱 포지션 체크
        if self.long_position is not None:
            slot = self.long_position
            revenue_rate = self.calculate_revenue_rate(slot['base_price'], current_price, False)
            
            # 최고 수익률 업데이트
            if revenue_rate > slot['highest_profit']:
                self.long_position['highest_profit'] = revenue_rate
            
            # 청산 조건: 0.4% 이상 수익 + 숏 신호
            if revenue_rate >= 0.4 and ma_signals['short_signal']:
                positions_to_close.append('long')
        
        # 숏 포지션 체크
        if self.short_position is not None:
            slot = self.short_position
            revenue_rate = self.calculate_revenue_rate(slot['base_price'], current_price, True)
            
            # 최고 수익률 업데이트
            if revenue_rate > slot['highest_profit']:
                self.short_position['highest_profit'] = revenue_rate
            
            # 청산 조건: 0.4% 이상 수익 + 롱 신호
            if revenue_rate >= 0.4 and ma_signals['long_signal']:
                positions_to_close.append('short')
        
        return positions_to_close
    
    def apply_water_effect(self, profit: float, current_price: float):
        """물타기 효과 적용 (수익의 50%를 손실 중인 포지션 가격 조정에 사용)"""
        if profit <= 0 or (self.long_position is None and self.short_position is None):
            return
            
        water_amount = profit * self.water_profit_ratio
        # 물타기 사용분을 잔고에서 차감
        self.current_balance -= water_amount
        
        loss_slots = 0  # 손실 중인 포지션 수
        
        # 손실 중인 포지션만 카운트
        if self.long_position:
            long_revenue_rate = self.calculate_revenue_rate(self.long_position['price'], current_price, False)
            if long_revenue_rate <= 0:  # 0% 이하 손실
                loss_slots += 1
                
        if self.short_position:
            short_revenue_rate = self.calculate_revenue_rate(self.short_position['price'], current_price, True)
            if short_revenue_rate <= 0:  # 0% 이하 손실
                loss_slots += 1
        
        if loss_slots == 0:
            return  # 손실 중인 포지션이 없으면 물타기 안함
            
        water_per_slot = water_amount / loss_slots
        
        # 롱 포지션 가격 조정 (손실 중일 때만)
        if self.long_position:
            long_revenue_rate = self.calculate_revenue_rate(self.long_position['base_price'], current_price, False)
            if long_revenue_rate <= 0:  # 0% 이하 손실일 때만
                # base_price를 조정 (평균 단가 개선)
                self.long_position['base_price'] = round(((self.long_position['base_price'] * abs(self.long_position['amt'])) - water_per_slot) / abs(self.long_position['amt']), 2)
        
        # 숏 포지션 가격 조정 (손실 중일 때만)
        if self.short_position:
            short_revenue_rate = self.calculate_revenue_rate(self.short_position['base_price'], current_price, True)
            if short_revenue_rate <= 0:  # 0% 이하 손실일 때만
                # base_price를 조정 (평균 단가 개선)
                self.short_position['base_price'] = round(((self.short_position['base_price'] * abs(self.short_position['amt'])) + water_per_slot) / abs(self.short_position['amt']), 2)
    
    def run_backtest(self, df: pd.DataFrame, start_date: str = None, end_date: str = None) -> Dict:
        """백테스트 실행"""
        print("물타기 전략 V2 백테스트 시작...")
        
        # 날짜 필터링
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        # 판다스로 미리 계산 (성능 최적화)
        print("📊 기술적 지표 미리 계산 중...")
        
        # 이동평균 계산
        df['ma5'] = df['close'].rolling(window=5, min_periods=1).mean()
        df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
        
        # MA 신호 미리 계산 (벡터화)
        df['ma5_shift1'] = df['ma5'].shift(1)
        df['ma5_shift2'] = df['ma5'].shift(2)
        df['ma5_shift3'] = df['ma5'].shift(3)
        
        # 진입/청산 신호 미리 계산 (벡터화)
        df['long_signal'] = (
            (df['ma5'] < df['ma20']) & 
            (df['ma5_shift3'] > df['ma5_shift2']) & 
            (df['ma5_shift2'] < df['ma5_shift1'])
        ).fillna(False)
        
        df['short_signal'] = (
            (df['ma5'] > df['ma20']) & 
            (df['ma5_shift3'] < df['ma5_shift2']) & 
            (df['ma5_shift2'] > df['ma5_shift1'])
        ).fillna(False)
        
        df['long_exit'] = (
            (df['ma5'] > df['ma20']) & 
            (df['ma5_shift3'] < df['ma5_shift2']) & 
            (df['ma5_shift2'] > df['ma5_shift1'])
        ).fillna(False)
        
        df['short_exit'] = (
            (df['ma5'] < df['ma20']) & 
            (df['ma5_shift3'] > df['ma5_shift2']) & 
            (df['ma5_shift2'] < df['ma5_shift1'])
        ).fillna(False)
        
        # 수익률 계산도 미리 계산 (벡터화)
        print("📈 수익률 계산 미리 계산 중...")
        df['price_change'] = df['close'].pct_change() * 100
        
        # 불필요한 컬럼 제거 (메모리 절약)
        df.drop(['ma5_shift1', 'ma5_shift2', 'ma5_shift3'], axis=1, inplace=True)
        
        print(f"📅 백테스트 데이터 기간: {df.index[0].strftime('%Y년 %m월 %d일 %H시 %M분')} ~ {df.index[-1].strftime('%Y년 %m월 %d일 %H시 %M분')}")
        print(f"📊 총 데이터 포인트: {len(df):,}개")
        print(f"⏱️ 테스트 기간: {(df.index[-1] - df.index[0]).days}일")
        print("=" * 60)
        
        # 초기화
        self.current_balance = self.initial_balance
        self.long_position = None
        self.short_position = None
        self.slot_no = 0
        self.trades = []
        self.balance_history = []
        self.long_water_level_history = []
        self.short_water_level_history = []
        
        for i in range(len(df)):
            current_price = df['close'].iloc[i]
            current_time = df.index[i]
            
            # MA 계산 (미리 계산된 값 사용)
            if i < 20:
                self.balance_history.append(self.current_balance)
                self.long_water_level_history.append(0)
                self.short_water_level_history.append(0)
                continue
                
            # 미리 계산된 신호 사용 (훨씬 빠름)
            ma_signals = self.check_ma_signals(df, i)
            first_amount = self.get_first_amount(current_price)
            
            # 청산 조건 체크 (0.3% 이상 수익 + 반대 신호)
            positions_to_close = self.check_exit_conditions(current_price, ma_signals)
            total_profit = 0
            
            for side in positions_to_close:
                if side == "long" and self.long_position:
                    slot = self.long_position
                elif side == "short" and self.short_position:
                    slot = self.short_position
                else:
                    continue
                
                profit = self.close_position(slot, current_price)
                total_profit += profit
                
                # 수익의 50% 계산
                water_profit = profit * self.water_profit_ratio
                net_profit = profit - water_profit
                
                current_time = df.index[i] if 'df' in locals() else "Unknown"
                print(f"[{current_time.strftime('%m-%d %H:%M')}] 🎯 {side} 청산: {current_price:.2f} USDT, 총수익: {profit:.2f} USDT (순수익: {net_profit:.2f}, 물타기: {water_profit:.2f})")
                
                # 포지션 제거
                self.remove_position(side)
            
            # 물타기 효과 적용 (손실 중인 포지션에만)
            if total_profit > 0:
                self.apply_water_effect(total_profit, current_price)
                
                # 물타기 적용 후 잔고 및 총자산 출력
                unrealized_pnl = 0
                if self.long_position:
                    long_revenue_rate = self.calculate_revenue_rate(self.long_position['base_price'], current_price, False)
                    unrealized_pnl += (current_price - self.long_position['base_price']) * abs(self.long_position['amt'])
                if self.short_position:
                    short_revenue_rate = self.calculate_revenue_rate(self.short_position['base_price'], current_price, True)
                    unrealized_pnl += (self.short_position['base_price'] - current_price) * abs(self.short_position['amt'])
                
                total_balance = self.current_balance + unrealized_pnl
                print(f"💰 잔고: {self.current_balance:.2f} USDT, 총자산: {total_balance:.2f} USDT (미실현: {unrealized_pnl:.2f})")
            
            # 롱 진입 로직 (독립적)
            if ma_signals['long_signal'] and self.long_position is None:
                if self.add_position("long", current_price, first_amount, 0):
                    self.execute_trade('buy', first_amount, current_price)
                    self.total_trades += 1
                    current_time = df.index[i]
                    print(f"[{current_time.strftime('%m-%d %H:%M')}] 🟢 롱 진입: {current_price:.2f} USDT, 수량: {first_amount:.3f} BTC, 잔고: {self.current_balance:.2f} USDT")
            
            # 숏 진입 로직 (독립적)
            if ma_signals['short_signal'] and self.short_position is None:
                if self.add_position("short", current_price, first_amount, 0):
                    self.execute_trade('sell', first_amount, current_price)
                    self.total_trades += 1
                    current_time = df.index[i]
                    print(f"[{current_time.strftime('%m-%d %H:%M')}] 🔴 숏 진입: {current_price:.2f} USDT, 수량: {first_amount:.3f} BTC, 잔고: {self.current_balance:.2f} USDT")
            
            # 롱 물타기 체크 (독립적)
            if self.long_position is not None:
                revenue_rate = self.calculate_revenue_rate(self.long_position['base_price'], current_price, False)
                water_level = self.long_position['water_level']
                
                # -5% 단위로 물타기 (총 8번)
                if (revenue_rate <= self.water_levels[water_level] and 
                    water_level < self.max_water_level):
                    
                    water_amount = first_amount * (2 ** water_level)  # 1, 2, 4, 8, 16, 32, 64, 128
                    if self.add_position("long", current_price, water_amount, water_level + 1):
                        self.execute_trade('buy', water_amount, current_price)
                        self.total_trades += 1
                        current_time = df.index[i]
                        print(f"[{current_time.strftime('%m-%d %H:%M')}] 🟢 롱 물타기 L{water_level + 1}: {current_price:.2f} USDT, 수량: {water_amount:.3f} BTC, 잔고: {self.current_balance:.2f} USDT")
            
            # 숏 물타기 체크 (독립적)
            if self.short_position is not None:
                revenue_rate = self.calculate_revenue_rate(self.short_position['base_price'], current_price, True)
                water_level = self.short_position['water_level']
                
                # -5% 단위로 물타기 (총 8번)
                if (revenue_rate <= self.water_levels[water_level] and 
                    water_level < self.max_water_level):
                    
                    water_amount = first_amount * (2 ** water_level)  # 1, 2, 4, 8, 16, 32, 64, 128
                    if self.add_position("short", current_price, water_amount, water_level + 1):
                        self.execute_trade('sell', water_amount, current_price)
                        self.total_trades += 1
                        current_time = df.index[i]
                        print(f"[{current_time.strftime('%m-%d %H:%M')}] 🔴 숏 물타기 L{water_level + 1}: {current_price:.2f} USDT, 수량: {water_amount:.3f} BTC, 잔고: {self.current_balance:.2f} USDT")
            
            # 기록 저장
            self.balance_history.append(self.current_balance)
            self.long_water_level_history.append(self.long_position['water_level'] if self.long_position else 0)
            self.short_water_level_history.append(self.short_position['water_level'] if self.short_position else 0)
            
            # 진행률 출력 (1분봉이므로 적절한 간격으로)
            if i % 10000 == 0 and i > 0:
                # 미실현 손익 계산 (물타기 적용된 base_price로 계산)
                unrealized_pnl = 0
                if self.long_position:
                    unrealized_pnl += (current_price - self.long_position['base_price']) * abs(self.long_position['amt'])
                if self.short_position:
                    unrealized_pnl += (self.short_position['base_price'] - current_price) * abs(self.short_position['amt'])
                
                total_balance = self.current_balance + unrealized_pnl
                
                long_level = self.long_position['water_level'] if self.long_position else 0
                short_level = self.short_position['water_level'] if self.short_position else 0
                
                print(f"진행률: {i/len(df)*100:.1f}% - 롱: L{long_level}, 숏: L{short_level}, 잔고: {self.current_balance:.2f} USDT, 총자산: {total_balance:.2f} USDT (미실현: {unrealized_pnl:.2f})")
            
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
        
        # 미실현 손익 계산 (물타기 적용된 base_price로 계산)
        unrealized_pnl = 0
        if final_price is not None:
            if self.long_position:
                unrealized_pnl += (final_price - self.long_position['base_price']) * abs(self.long_position['amt'])
            if self.short_position:
                unrealized_pnl += (self.short_position['base_price'] - final_price) * abs(self.short_position['amt'])
        
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
            "final_long_level": self.long_position['water_level'] if self.long_position else 0,
            "final_short_level": self.short_position['water_level'] if self.short_position else 0,
            "max_long_level": max(self.long_water_level_history) if self.long_water_level_history else 0,
            "max_short_level": max(self.short_water_level_history) if self.short_water_level_history else 0
        }
    
    def plot_results(self, df: pd.DataFrame):
        """결과 시각화"""
        fig, axes = plt.subplots(4, 1, figsize=(15, 16))
        
        # 가격 차트
        axes[0].plot(df.index, df['close'], label='BTC Price', alpha=0.7)
        axes[0].set_title(f'BTC Price - {df.index[0].strftime("%Y-%m-%d")} ~ {df.index[-1].strftime("%Y-%m-%d")}')
        axes[0].set_ylabel('Price (USDT)')
        axes[0].legend()
        axes[0].grid(True)
        
        # 잔고 변화
        axes[1].plot(df.index, self.balance_history, label='Balance', color='green')
        axes[1].axhline(y=self.initial_balance, color='red', linestyle='--', alpha=0.7, label=f'Initial Balance ({self.initial_balance:,.0f} USDT)')
        axes[1].set_title('Balance History')
        axes[1].set_ylabel('Balance (USDT)')
        axes[1].legend()
        axes[1].grid(True)
        
        # 롱 물타기 레벨
        axes[2].plot(df.index, self.long_water_level_history, label='Long Water Level', color='blue')
        axes[2].set_title('Long Water Level')
        axes[2].set_ylabel('Water Level')
        axes[2].legend()
        axes[2].grid(True)
        
        # 숏 물타기 레벨
        axes[3].plot(df.index, self.short_water_level_history, label='Short Water Level', color='red')
        axes[3].set_title('Short Water Level')
        axes[3].set_ylabel('Water Level')
        axes[3].set_xlabel('Date')
        axes[3].legend()
        axes[3].grid(True)
        
        # X축 날짜 포맷팅
        for ax in axes:
            ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.show()

# 사용 예시
if __name__ == "__main__":
    # 실제 바이낸스 데이터 로드 (여러 월)
    try:
        print("실제 BTC 데이터 로딩 중...")
        
        # 2018~2024년 1분봉 데이터 (판다스 미리 계산으로 최적화)
        data_files = []
        for year in range(2018, 2025):
            for month in range(1, 13):
                data_files.append(f'c:\\work\\GitHub\\py\\kook\\binance\\data\\BTC_USDT\\1m\\{year}-{month:02d}.csv')
        
        df_list = []
        for file_path in data_files:
            try:
                temp_df = pd.read_csv(file_path)
                temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'])
                temp_df = temp_df.set_index('timestamp')
                df_list.append(temp_df)
                print(f"로드 완료: {file_path} - {len(temp_df)}개 데이터")
            except FileNotFoundError:
                print(f"파일 없음: {file_path}")
                continue
        
        if df_list:
            df = pd.concat(df_list, ignore_index=False)
            df = df.sort_index()  # 시간순 정렬
            
            # 1분봉 그대로 사용 (판다스 최적화로 충분히 빠름)
            print("1분봉 데이터 사용 (판다스 최적화 적용)")
            
        else:
            raise FileNotFoundError("데이터 파일을 찾을 수 없습니다.")
        
        print(f"실제 데이터 로드 완료: {len(df):,}개 데이터 포인트 (1분봉)")
        print(f"데이터 기간: {df.index[0].strftime('%Y년 %m월 %d일 %H시 %M분')} ~ {df.index[-1].strftime('%Y년 %m월 %d일 %H시 %M분')}")
        print(f"테스트 기간: {(df.index[-1] - df.index[0]).days}일")
        print(f"가격 범위: {df['close'].min():.2f} ~ {df['close'].max():.2f} USDT")
        
    except Exception as e:
        print(f"실제 데이터 로드 실패: {e}")
        print("가상 데이터를 생성합니다...")
        
        # 가상 데이터 생성 (백업) - 1분봉으로 생성
        dates = pd.date_range('2018-01-01', '2024-12-31', freq='1min')  # 1분봉으로 생성
        np.random.seed(42)
        
        price_changes = np.random.normal(0, 0.001, len(dates))
        prices = [10000]  # 2018년 초기 가격
        
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
    bot = WaterStrategyBotV2(initial_balance=10000, leverage=10)
    results = bot.run_backtest(df)
    
    print("\n=== 물타기 전략 V2 백테스트 결과 ===")
    print(f"백테스트 기간: {df.index[0].strftime('%Y년 %m월 %d일 %H시 %M분')} ~ {df.index[-1].strftime('%Y년 %m월 %d일 %H시 %M분')}")
    print(f"총 데이터 포인트: {len(df):,}개")
    print(f"테스트 기간: {(df.index[-1] - df.index[0]).days}일")
    print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
    print(f"최종 자본: {results['final_balance']:,.0f} USDT (수수료 + 실현손익만 반영)")
    print(f"총 자산: {results['total_balance']:,.0f} USDT (미실현 손익 포함)")
    print(f"미실현 손익: {results['unrealized_pnl']:,.0f} USDT")
    print(f"총 손익: {results['total_pnl']:,.0f} USDT")
    print(f"총 수익률: {results['total_return']:.2f}%")
    print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
    print(f"총 거래 횟수: {results['total_trades']}회")
    print(f"승률: {results['win_rate']:.2f}%")
    print(f"최대 롱 물타기 레벨: {results['max_long_level']}")
    print(f"최대 숏 물타기 레벨: {results['max_short_level']}")
    print(f"현재 롱 물타기 레벨: {results['final_long_level']}")
    print(f"현재 숏 물타기 레벨: {results['final_short_level']}")
    
    # 결과 시각화
    bot.plot_results(df)
