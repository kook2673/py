# -*- coding: utf-8 -*-
"""
24분할 롱/숏 독립 물타기 전략 시스템 (수익률 개선 버전)

=== 핵심 규칙 ===

1. 자본 분산 (24분할)
   - 총 자본을 24분할로 나누어 관리
   - 각 분할당 자본: division_capital = capital / 24
   - 롱/숏 포지션이 사용하는 분할의 총합은 24를 초과할 수 없음

2. 진입 조건 (MA5, MA20 전략)
   - 롱 진입: 5일선이 20일선 아래에 있는데 5일선이 상승추세로 꺾였을 때
   - 숏 진입: 5일선이 20일선 위에 있는데 5일선이 하락추세로 꺾였을 때
   - 각각 1분할로 진입

3. 물타기 로직 (1,1,2,4,8 분할)
   - 물타기 분할: [1, 1, 2, 4, 8] 순서로 진행 (총 5단계)
   - [개선] 변동성 기반 물타기: ATR 지표를 사용하여 동적으로 물타기 간격을 조정
   - [개선] 동적 쿨다운: 손실률에 따라 물타기 간 최소 대기 시간 단축

4. 수익 실현 규칙
    - 0.3% 수익 시 → 50% 매도
    - 나머지 50% → 트레일링 스탑

5. 손절매 조건
   - 롱: 5단계 물타기 후 25% 하락 시 손절
   - 숏: 5단계 물타기 후 25% 상승 시 손절

6. 기타
   - 레버리지: 1배 (설정 가능)
   - 수수료: 0.05% (설정 가능)
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
from dataclasses import dataclass, field
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from typing import List, Dict

# --- 1. 설정 클래스 정의 ---
@dataclass
class StrategyConfig:
    """전략의 핵심 파라미터를 관리하는 데이터 클래스"""
    initial_capital: float = 10000.0
    leverage: int = 2  # 레버리지 5배로 설정
    fee_rate: float = 0.0005  # 0.05%
    
    total_divisions: int = 24
    split_ratios: List[int] = field(default_factory=lambda: [1, 1, 2, 4, 8])
    
    # 기술적 지표
    ma_short: int = 5
    ma_long: int = 20
    atr_period: int = 14
    
    # 물타기 조건
    use_volatility_based_scaling: bool = True
    atr_multiplier: float = 2.0  # ATR에 곱해줄 값으로 물타기 간격 조절
    dynamic_cooldown_candles: int = 5 # 손실 시 물타기 쿨다운 (캔들 수)
    base_cooldown_candles: int = 20
    
    # 수익 실현 조건
    partial_take_profit_pct: float = 0.003 # 0.3%
    trailing_stop_activation_pct: float = 0.005 # 0.5%
    trailing_stop_callback_pct: float = 0.002 # 0.2%

    # 손절 조건
    stop_loss_pct: float = 0.25

@dataclass
class Position:
    """롱 또는 숏 포지션의 상태를 관리하는 데이터 클래스"""
    is_active: bool = False
    quantity: float = 0.0
    avg_price: float = 0.0
    total_cost: float = 0.0  # 실제 투입된 자본 (수수료 제외)
    level: int = 0
    
    # 수익 실현 및 리스크 관리
    highest_price: float = 0.0
    lowest_price: float = float('inf')
    is_trailing_stop_active: bool = False
    partial_exit_done: bool = False
    
    last_trade_idx: int = -1 # 마지막 거래 캔들 인덱스
    
    # 청산 리스크 관리
    liquidation_price: float = 0.0  # 청산 가격
    max_risk_pct: float = 0.0  # 최대 청산 위험도 (0~1, 1에 가까울수록 위험)

# ==============================================================================
# 새로 작성된 코드
# ==============================================================================
class WaterBot:
    """24분할 물타기 전략을 실행하는 봇 클래스 (신규 버전)"""

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.trade_log = []
        self.equity_curve = []
        
        # 자본 관리
        self.current_capital = config.initial_capital
        self.division_size = config.initial_capital / config.total_divisions
        self.available_divisions = config.total_divisions
        
        # 포지션 상태
        self.long_pos = Position()
        self.short_pos = Position()
        
        # 청산 리스크 추적
        self.max_long_liquidation_risk = 0.0
        self.max_short_liquidation_risk = 0.0
        self.liquidation_warning_count = 0  # 청산 위험 경고 횟수

    def _calculate_liquidation_price(self, pos_type: str, avg_price: float) -> float:
        """청산 가격을 계산합니다.
        
        청산 공식:
        - 롱: 청산가 = 진입가 * (1 - (1/레버리지) * 0.95)  # 0.95는 안전 마진
        - 숏: 청산가 = 진입가 * (1 + (1/레버리지) * 0.95)
        """
        safety_margin = 0.95  # 유지보증금률 고려 (실제보다 약간 보수적으로)
        
        if pos_type == 'LONG':
            return avg_price * (1 - (1 / self.config.leverage) * safety_margin)
        else:  # SHORT
            return avg_price * (1 + (1 / self.config.leverage) * safety_margin)
    
    def _check_liquidation_risk(self, pos_type: str, pos: Position, current_price: float) -> float:
        """청산 리스크를 계산합니다. (0~1 범위, 1에 가까울수록 위험)"""
        if not pos.is_active:
            return 0.0
        
        liq_price = pos.liquidation_price
        
        if pos_type == 'LONG':
            # 롱: 현재가가 청산가에 가까울수록 위험
            if current_price <= liq_price:
                return 1.0  # 청산!
            price_buffer = pos.avg_price - liq_price
            price_from_liq = current_price - liq_price
            risk = 1.0 - (price_from_liq / price_buffer) if price_buffer > 0 else 1.0
        else:  # SHORT
            # 숏: 현재가가 청산가에 가까울수록 위험
            if current_price >= liq_price:
                return 1.0  # 청산!
            price_buffer = liq_price - pos.avg_price
            price_from_liq = liq_price - current_price
            risk = 1.0 - (price_from_liq / price_buffer) if price_buffer > 0 else 1.0
        
        return max(0.0, min(1.0, risk))

    def _log_trade(self, timestamp, trade_type, position, price, qty, pnl, fee, details):
        """거래 내역을 기록합니다."""
        self.trade_log.append({
            "timestamp": timestamp,
            "type": trade_type,
            "position": position,
            "price": price,
            "quantity": qty,
            "pnl": pnl,
            "fee": fee,
            "details": details
        })

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표와 거래 신호를 계산합니다."""
        df['ma_short'] = df['close'].rolling(window=self.config.ma_short).mean()
        df['ma_long'] = df['close'].rolling(window=self.config.ma_long).mean()

        # ATR 계산
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=self.config.atr_period).mean()
        df['atr_pct'] = (df['atr'] / df['close'])
        
        # 이동평균선의 이전 값들을 계산
        df['ma_short_prev'] = df['ma_short'].shift(1)
        df['ma_short_prev2'] = df['ma_short'].shift(2)
        
        # 진입 신호 생성
        df['long_signal'] = (
            (df['ma_short'] < df['ma_long']) &
            (df['ma_short_prev2'] > df['ma_short_prev']) &
            (df['ma_short_prev'] < df['ma_short'])
        )
        df['short_signal'] = (
            (df['ma_short'] > df['ma_long']) &
            (df['ma_short_prev2'] < df['ma_short_prev']) &
            (df['ma_short_prev'] > df['ma_short'])
        )
        
        return df.dropna()

    def run_backtest(self, df: pd.DataFrame):
        """전략 백테스팅을 실행합니다."""
        data = self._calculate_indicators(df)

        for i in range(len(data)):
            row = data.iloc[i]
            current_price = row['close']
            timestamp = data.index[i]
            
            # 롱 포지션 관리
            if self.long_pos.is_active:
                # 청산 리스크 체크
                risk = self._check_liquidation_risk('LONG', self.long_pos, current_price)
                self.long_pos.max_risk_pct = max(self.long_pos.max_risk_pct, risk)
                self.max_long_liquidation_risk = max(self.max_long_liquidation_risk, risk)
                
                if risk >= 0.8:  # 청산 위험 80% 이상
                    self.liquidation_warning_count += 1
                
                self._manage_position('LONG', self.long_pos, row, i, timestamp)
            # 신규 롱 포지션 진입
            elif row['long_signal']:
                self._open_position('LONG', current_price, i, timestamp)

            # 숏 포지션 관리
            if self.short_pos.is_active:
                # 청산 리스크 체크
                risk = self._check_liquidation_risk('SHORT', self.short_pos, current_price)
                self.short_pos.max_risk_pct = max(self.short_pos.max_risk_pct, risk)
                self.max_short_liquidation_risk = max(self.max_short_liquidation_risk, risk)
                
                if risk >= 0.8:  # 청산 위험 80% 이상
                    self.liquidation_warning_count += 1
                
                self._manage_position('SHORT', self.short_pos, row, i, timestamp)
            # 신규 숏 포지션 진입
            elif row['short_signal']:
                self._open_position('SHORT', current_price, i, timestamp)

            # 자산 가치 기록
            self._update_equity(current_price)

        return self.trade_log, data
    
    def _open_position(self, position_type: str, price: float, index: int, timestamp):
        """신규 포지션을 개시합니다."""
        
        pos = self.long_pos if position_type == 'LONG' else self.short_pos
        if pos.is_active: return

        split_ratio = self.config.split_ratios[0]
        if self.available_divisions < split_ratio:
            # print(f"자본 부족으로 {position_type} 진입 실패")
            return

        self.available_divisions -= split_ratio
        
        cost = self.division_size * split_ratio
        amount_to_trade = cost * self.config.leverage
        fee = amount_to_trade * self.config.fee_rate
        quantity = (amount_to_trade - fee) / price
        if position_type == 'SHORT':
            quantity *= -1

        # 자본에서 투입 비용(담보) + 수수료 차감
        self.current_capital -= (cost + fee)

        pos.is_active = True
        pos.level = 1
        pos.quantity = quantity
        pos.avg_price = price
        pos.total_cost = cost  # 담보 금액만 기록 (수수료 제외)
        pos.last_trade_idx = index
        pos.highest_price = price if position_type == 'LONG' else 0
        pos.lowest_price = price if position_type == 'SHORT' else float('inf')
        pos.partial_exit_done = False
        pos.is_trailing_stop_active = False
        
        # 청산 가격 계산
        pos.liquidation_price = self._calculate_liquidation_price(position_type, price)

        self._log_trade(timestamp, 'ENTRY', position_type, price, abs(quantity), 0, fee, f"Level 1 Entry")

    def _update_equity(self, current_price: float):
        """현재 가격 기준으로 총 자산 가치를 계산하고 기록합니다."""
        long_pnl = 0
        if self.long_pos.is_active:
            # quantity는 이미 레버리지가 적용된 값이므로 여기서 다시 곱하면 안됨
            long_pnl = (current_price - self.long_pos.avg_price) * self.long_pos.quantity

        short_pnl = 0
        if self.short_pos.is_active:
            # quantity는 이미 레버리지가 적용된 값이므로 여기서 다시 곱하면 안됨
            short_pnl = (self.short_pos.avg_price - current_price) * abs(self.short_pos.quantity)
            
        # current_capital은 이미 포지션 투입 비용이 차감된 상태
        # 따라서 현재 자본 + 포지션에 투입된 자본 + 미실현 손익 = 총 자산
        occupied_capital = self.long_pos.total_cost + self.short_pos.total_cost
        
        total_equity = self.current_capital + occupied_capital + long_pnl + short_pnl
        self.equity_curve.append(total_equity)

    def _manage_position(self, pos_type: str, pos: Position, row: pd.Series, index: int, timestamp):
        """활성화된 포지션을 관리합니다 (물타기, 익절, 손절)."""
        current_price = row['close']
        
        # 1. 물타기 (Averaging Down)
        self._check_and_execute_averaging_down(pos_type, pos, row, index, timestamp)
        
        # 2. 익절 및 트레일링 스탑
        self._check_take_profit_and_trailing_stop(pos_type, pos, row, index, timestamp)
        
        # 3. 손절
        self._check_stop_loss(pos_type, pos, row, index, timestamp)
        
    def _check_and_execute_averaging_down(self, pos_type: str, pos: Position, row: pd.Series, index: int, timestamp):
        """물타기 조건을 확인하고 실행합니다."""
        if pos.level >= len(self.config.split_ratios):
            return # 최대 레벨 도달

        # 동적 물타기 간격 설정
        atr_pct = row['atr_pct']
        threshold = atr_pct * self.config.atr_multiplier if self.config.use_volatility_based_scaling else 0.05 # 기본값 5%

        price_condition = False
        if pos_type == 'LONG':
            price_condition = row['close'] <= pos.avg_price * (1 - threshold)
        else: # SHORT
            price_condition = row['close'] >= pos.avg_price * (1 + threshold)

        if not price_condition:
            return

        # 동적 쿨다운 확인
        loss_pct = abs(row['close'] - pos.avg_price) / pos.avg_price
        cooldown = self.config.dynamic_cooldown_candles if loss_pct > 0.02 else self.config.base_cooldown_candles
        
        if index - pos.last_trade_idx < cooldown:
            return

        # 물타기 실행
        next_level = pos.level
        split_ratio = self.config.split_ratios[next_level]
        
        if self.available_divisions < split_ratio:
            return # 자본 부족

        self.available_divisions -= split_ratio
        
        cost = self.division_size * split_ratio
        amount_to_trade = cost * self.config.leverage
        fee = amount_to_trade * self.config.fee_rate
        additional_quantity = (amount_to_trade - fee) / row['close']
        
        if pos_type == 'SHORT':
            additional_quantity *= -1

        # 자본에서 투입 비용(담보) + 수수료 차감
        self.current_capital -= (cost + fee)

        # 포지션 업데이트
        new_total_quantity = pos.quantity + additional_quantity
        new_total_cost = pos.total_cost + cost  # 담보 금액만 누적 (수수료 제외)
        pos.avg_price = ((pos.quantity * pos.avg_price) + (additional_quantity * row['close'])) / new_total_quantity
        pos.quantity = new_total_quantity
        pos.total_cost = new_total_cost
        pos.level += 1
        pos.last_trade_idx = index
        
        # 평균 진입가가 변경되었으므로 청산 가격 재계산
        pos.liquidation_price = self._calculate_liquidation_price(pos_type, pos.avg_price)
        
        self._log_trade(timestamp, 'AVG_DOWN', pos_type, row['close'], abs(additional_quantity), 0, fee, f"Level {pos.level}")

    def _check_take_profit_and_trailing_stop(self, pos_type: str, pos: Position, row: pd.Series, index: int, timestamp):
        """익절 및 트레일링 스탑 조건을 확인하고 실행합니다."""
        current_price = row['close']
        profit_pct = 0
        
        if pos_type == 'LONG':
            profit_pct = (current_price - pos.avg_price) / pos.avg_price
            if not pos.is_trailing_stop_active:
                pos.highest_price = max(pos.highest_price, current_price)
        else: # SHORT
            profit_pct = (pos.avg_price - current_price) / pos.avg_price
            if not pos.is_trailing_stop_active:
                pos.lowest_price = min(pos.lowest_price, current_price)

        # 부분 익절
        if not pos.partial_exit_done and profit_pct >= self.config.partial_take_profit_pct:
            self._close_position(pos_type, pos, current_price, timestamp, 0.5, 'PARTIAL_TP')
            pos.partial_exit_done = True
            pos.is_trailing_stop_active = True # 부분 익절 후 바로 트레일링 스탑 활성화
        
        # 트레일링 스탑 활성화
        if not pos.is_trailing_stop_active and profit_pct >= self.config.trailing_stop_activation_pct:
            pos.is_trailing_stop_active = True

        # 트레일링 스탑 실행
        if pos.is_trailing_stop_active:
            stop_price = 0
            if pos_type == 'LONG':
                stop_price = pos.highest_price * (1 - self.config.trailing_stop_callback_pct)
                if current_price < stop_price:
                    self._close_position(pos_type, pos, current_price, timestamp, 1.0, 'TRAILING_STOP')
            else: # SHORT
                stop_price = pos.lowest_price * (1 + self.config.trailing_stop_callback_pct)
                if current_price > stop_price:
                    self._close_position(pos_type, pos, current_price, timestamp, 1.0, 'TRAILING_STOP')

    def _check_stop_loss(self, pos_type: str, pos: Position, row: pd.Series, index: int, timestamp):
        """손절 조건을 확인하고 실행합니다."""
        if pos.level < len(self.config.split_ratios):
            return # 최대 레벨에서만 손절

        loss_pct = 0
        current_price = row['close']
        if pos_type == 'LONG':
            loss_pct = (pos.avg_price - current_price) / pos.avg_price
        else: # SHORT
            loss_pct = (current_price - pos.avg_price) / pos.avg_price
        
        if loss_pct >= self.config.stop_loss_pct:
            self._close_position(pos_type, pos, current_price, timestamp, 1.0, 'STOP_LOSS')

    def _close_position(self, pos_type: str, pos: Position, price: float, timestamp, size_pct: float, close_reason: str):
        """포지션을 부분 또는 전체 청산합니다."""
        if not pos.is_active: return

        # 청산할 수량 계산 (절대값으로 통일)
        close_quantity = abs(pos.quantity) * size_pct
        
        # PnL 계산 (quantity는 이미 레버리지가 적용된 값)
        pnl = 0
        if pos_type == 'LONG':
            pnl = (price - pos.avg_price) * close_quantity
        else: # SHORT
            pnl = (pos.avg_price - price) * close_quantity
        
        # trade_value와 fee 계산 (close_quantity는 이미 레버리지 적용된 수량)
        trade_value = close_quantity * price
        fee = trade_value * self.config.fee_rate
        net_pnl = pnl - fee

        # 자본 업데이트
        closed_cost = pos.total_cost * size_pct
        self.current_capital += closed_cost + net_pnl
        
        # 사용된 분할 반환
        released_divisions = 0
        if size_pct == 1.0: # 전체 청산
            for i in range(pos.level):
                released_divisions += self.config.split_ratios[i]
        else: # 부분 청산 (비율에 따라 대략적으로 계산)
            # 여기서는 간단하게 절반만 반환하는 것으로 가정. 더 정교한 계산이 필요할 수 있음.
            for i in range(pos.level):
                released_divisions += self.config.split_ratios[i]
            released_divisions = round(released_divisions * size_pct)
        
        self.available_divisions += released_divisions


        self._log_trade(timestamp, close_reason, pos_type, price, close_quantity, net_pnl, fee, f"Level {pos.level}")

        # 포지션 상태 업데이트
        if size_pct == 1.0:
            pos.is_active = False
            pos.quantity = 0
            pos.avg_price = 0
            pos.total_cost = 0
            pos.level = 0
            pos.highest_price = 0
            pos.lowest_price = float('inf')
            pos.is_trailing_stop_active = False
            pos.partial_exit_done = False
            pos.last_trade_idx = -1
        else:
            # 부분 청산: 수량 감소 (LONG은 양수, SHORT는 음수이므로 부호를 고려)
            if pos_type == 'LONG':
                pos.quantity -= close_quantity
            else: # SHORT (pos.quantity는 음수, close_quantity는 양수)
                pos.quantity += close_quantity  # 음수를 0에 가깝게 만듦
            pos.total_cost -= closed_cost

    def get_results(self):
        """백테스팅 최종 결과를 반환합니다."""
        final_equity = self.equity_curve[-1] if self.equity_curve else self.config.initial_capital
        total_return_pct = (final_equity - self.config.initial_capital) / self.config.initial_capital * 100
        
        exit_trades = [t for t in self.trade_log if t['type'] not in ['ENTRY', 'AVG_DOWN']]
        total_trades = len(exit_trades)
        winning_trades = len([t for t in exit_trades if t['pnl'] > 0])
        losing_trades = total_trades - winning_trades
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        stop_loss_count = len([t for t in self.trade_log if t['type'] == 'STOP_LOSS'])

        return {
            "final_equity": final_equity,
            "total_return_pct": total_return_pct,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "stop_loss_count": stop_loss_count,
            "max_long_liquidation_risk": self.max_long_liquidation_risk,
            "max_short_liquidation_risk": self.max_short_liquidation_risk,
            "liquidation_warning_count": self.liquidation_warning_count
        }

    def save_trade_log(self, file_path: str):
        """거래 로그를 JSON 파일로 저장합니다."""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # JSON 직렬화를 위해 Timestamp를 문자열로 변환
            serializable_log = []
            for record in self.trade_log:
                new_record = record.copy()
                if isinstance(new_record['timestamp'], pd.Timestamp):
                    new_record['timestamp'] = new_record['timestamp'].isoformat()
                serializable_log.append(new_record)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_log, f, indent=4, ensure_ascii=False)
            print(f"💾 거래 로그를 '{file_path}'에 저장했습니다.")
        except Exception as e:
            print(f"❌ 거래 로그 저장 중 오류 발생: {e}")

def load_data_new(file_path: str) -> pd.DataFrame:
    """CSV 데이터를 로드하고 전처리합니다."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {file_path}")
    
    df = pd.read_csv(file_path, index_col='timestamp', parse_dates=True)
    return df

def plot_results_new(df: pd.DataFrame, trade_log: list, equity_curve: list, title: str):
    """백테스팅 결과를 시각화합니다."""
    fig = plt.figure(figsize=(15, 10))
    gs = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1])

    # 1. Price Chart with Trades
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(df.index, df['close'], label='Close Price', color='skyblue', linewidth=1)
    ax1.set_title(title, fontsize=16)
    ax1.set_ylabel('Price (USDT)')
    ax1.legend(loc='upper left')
    ax1.grid(True, which='both', linestyle='--', linewidth=0.5)

    # Plotting trade markers
    entry_long = [t for t in trade_log if t['type'] == 'ENTRY' and t['position'] == 'LONG']
    entry_short = [t for t in trade_log if t['type'] == 'ENTRY' and t['position'] == 'SHORT']
    avg_down = [t for t in trade_log if t['type'] == 'AVG_DOWN']
    exit_profit = [t for t in trade_log if t['pnl'] > 0 and t['type'] != 'ENTRY' and t['type'] != 'AVG_DOWN']
    exit_loss = [t for t in trade_log if t['pnl'] <= 0 and t['type'] != 'ENTRY' and t['type'] != 'AVG_DOWN']

    ax1.plot([t['timestamp'] for t in entry_long], [t['price'] for t in entry_long], '^', color='lime', markersize=6, label='Long Entry')
    ax1.plot([t['timestamp'] for t in entry_short], [t['price'] for t in entry_short], 'v', color='red', markersize=6, label='Short Entry')
    ax1.plot([t['timestamp'] for t in avg_down], [t['price'] for t in avg_down], 'o', color='white', markersize=5, markeredgecolor='black', label='Avg Down')
    ax1.plot([t['timestamp'] for t in exit_profit], [t['price'] for t in exit_profit], 'o', color='green', markersize=6, label='Take Profit')
    ax1.plot([t['timestamp'] for t in exit_loss], [t['price'] for t in exit_loss], 'x', color='magenta', markersize=6, label='Stop Loss')
    
    # 2. Equity Curve
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax2.plot(df.index, equity_curve, label='Equity Curve', color='orange')
    ax2.set_ylabel('Equity (USDT)')
    ax2.grid(True, which='both', linestyle='--', linewidth=0.5)
    
    plt.tight_layout()
    plt.show()


def main():
    """메인 실행 함수 (신규 버전)"""
    try:
        config = StrategyConfig()
        
        # 데이터 경로 설정 - 사용자의 프로젝트 구조에 맞게 수정이 필요할 수 있습니다.
        data_path = 'data/BTCUSDT/3m/BTCUSDT_3m_2024.csv'
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, data_path)
        
        df = load_data_new(file_path)
        # df = df[df.index.month == 1]  # 특정 월만 테스트하려면 주석 해제

        bot = WaterBot(config)
        trade_log, backtest_df = bot.run_backtest(df)
        results = bot.get_results()

        print("\n" + "="*50)
        print("📊 백테스트 결과")
        print("="*50)
        start_date = backtest_df.index[0].strftime('%Y-%m-%d')
        end_date = backtest_df.index[-1].strftime('%Y-%m-%d')
        print(f"기간: {start_date} ~ {end_date}")
        print(f"레버리지: {config.leverage}배")
        print(f"\n💰 수익 결과:")
        print(f"  최종 자산: ${results['final_equity']:,.2f}")
        print(f"  총 수익률: {results['total_return_pct']:.2f}%")
        print(f"\n📈 거래 통계:")
        print(f"  총 거래: {results['total_trades']}회")
        print(f"  승: {results['winning_trades']}회 ({results['win_rate']:.2f}%)")
        print(f"  패: {results['losing_trades']}회")
        print(f"  손절: {results['stop_loss_count']}회")
        print(f"\n⚠️ 청산 리스크:")
        print(f"  최대 롱 청산 위험도: {results['max_long_liquidation_risk']*100:.1f}%")
        print(f"  최대 숏 청산 위험도: {results['max_short_liquidation_risk']*100:.1f}%")
        print(f"  청산 위험 경고(80%+): {results['liquidation_warning_count']}회")
        
        # 청산 위험도에 따른 경고 메시지
        max_risk = max(results['max_long_liquidation_risk'], results['max_short_liquidation_risk'])
        if max_risk >= 1.0:
            print(f"\n🚨 청산 발생! 레버리지를 낮추세요!")
        elif max_risk >= 0.8:
            print(f"\n⚠️ 청산 위험 매우 높음! 레버리지 조정 필요!")
        elif max_risk >= 0.5:
            print(f"\n⚠️ 청산 위험 주의! 리스크 관리 필요!")
        else:
            print(f"\n✅ 청산 위험 낮음 - 안정적인 레버리지 수준")
        
        print("="*50 + "\n")
        
        # 거래 로그 저장
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(script_dir, 'logs', f'trade_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        bot.save_trade_log(log_path)

        # Plot results
        if bot.equity_curve:
             plot_results_new(backtest_df, trade_log, bot.equity_curve, "WaterBot Backtest Results")
        else:
            print("No trades were made, skipping plot.")
        
    except Exception as e:
        print(f"오류 발생: {e}")

# ==============================================================================

def load_btc_data(year: int = 2024, month: int = 1) -> pd.DataFrame:
    """BTC 데이터 로드"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, 'data', 'BTCUSDT', '3m', f'BTCUSDT_3m_{year}.csv')
    
    if not os.path.exists(data_path):
        print(f"❌ 데이터 파일을 찾을 수 없습니다: {data_path}")
        return None
    
    print(f"📊 {year}년 {month}월 BTC 데이터 로드 중...")
    # 'open', 'high', 'low', 'close', 'volume' 열이 포함되어 있다고 가정합니다.
    df = pd.read_csv(data_path, index_col='timestamp', parse_dates=True)
    
    # 월별 필터링
    if month is not None:
        df = df[df.index.month == month]
    
    print(f"✅ 데이터 로드 완료: {len(df):,}개 캔들")
    print(f"📅 기간: {df.index[0]} ~ {df.index[-1]}")
    
    return df

if __name__ == "__main__":
    main()