# -*- coding: utf-8 -*-
"""
16분할 롱/숏 독립 물타기 전략 시스템

=== 핵심 규칙 ===

1. 자본 분산 (16분할)
   - 총 자본을 16분할로 나누어 관리
   - 롱 포지션: 최대 8분할 (1+1+2+4+8)
   - 숏 포지션: 최대 8분할 (1+1+2+4+8)
   - 각 분할당 자본: division_capital = capital / 16

2. 진입 조건 (BB + RSI 전략)
   - 롱 진입: 하단 볼린저 밴드 터치 + RSI 과매도 (close <= bb_lower AND rsi < 30)
   - 숏 진입: 상단 볼린저 밴드 터치 + RSI 과매수 (close >= bb_upper AND rsi > 70)
   - 각각 1분할로 진입

3. 물타기 로직 (1,1,2,4,8 분할)
   - 롱 물타기: 가격 5% 하락 시 추가 매수
   - 숏 물타기: 가격 5% 상승 시 추가 매수
   - 물타기 분할: [1, 1, 2, 4, 8] 순서로 진행
   - 최대 5단계까지 물타기 가능

4. 수익 실현 규칙

   A. 물타기 안했을 때 (진입 1만):
      - 0.3% 수익 시 → 50% 매도
      - 나머지 50% → 트레일링 스탑

   B. 물타기 했을 때 (진입 + 물타기):
      - 0.1% 수익 시 → 가진 것의 50% 매도
      - 0.3% 수익 시 → 가진 것의 50% 매도 (나머지 50%의 50%)
      - 나머지 25% → 트레일링 스탑

5. 손절매 조건
   - 롱: 5단계 물타기 후 25% 하락 시 손절
   - 숏: 5단계 물타기 후 25% 상승 시 손절

6. 거래 로그 시각화
   - 진입: 흰색 동그라미 (white_circle)
   - 수익 실현: 초록색 동그라미 (green_circle)
   - 손실 청산: 빨간색 동그라미 (red_circle)

7. 레버리지 및 수수료
   - 레버리지: 1배 (설정 가능)
   - 수수료: 0.05% (설정 가능)
   - 실제 사용 자본 = 거래 금액 / 레버리지

=== 예시 시나리오 ===

롱 포지션 (물타기 했을 때):
1. 진입: 1분할 (3.125% 자본)
2. 물타기1: 1분할 추가 (총 6.25% 자본)
3. 물타기2: 2분할 추가 (총 12.5% 자본)
4. 물타기3: 4분할 추가 (총 25% 자본)
5. 물타기4: 8분할 추가 (총 50% 자본)
6. 수익 실현: 0.1%에서 50% → 0.3%에서 25% → 나머지 25% 트레일링

숏 포지션 (물타기 안했을 때):
1. 진입: 1분할 (3.125% 자본)
2. 수익 실현: 0.3%에서 50% → 나머지 50% 트레일링

=== 설정 파일 ===
- leverage: 레버리지 배수
- enable_long_short: 롱/숏 양방향 거래 활성화
- enable_technical_exit: 기술적 지표 기반 청산 활성화
- profit_targets: 수익 실현 목표 설정
- stop_loss: 손절매 임계값 설정
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
import json

class WaterBot:
    """물타기 봇 시스템"""
    
    def __init__(self, config_file: str = "water_bot.json"):
        self.config_file = config_file
        self.trade_log = []  # 거래내역 로그
        self.load_config()
    
    def load_config(self):
        """설정 파일 로드"""
        default_config = {
            "initial_capital": 10000,
            "trading_fee": 0.0005,
            "leverage": 1,  # 레버리지 1배
            "enable_long_short": False,  # 롱/숏 양방향 거래 (물타기 전략에서는 롱 집중)
            "enable_technical_exit": False,  # 기술적 지표 기반 청산 (물타기 전략에 부적합)
            "slides": {
                "entry": 1,
                "martingale1": 1,
                "martingale2": 2,
                "martingale4": 4,
                "martingale8": 8
            },
            "profit_targets": {
                "partial_sell_threshold": 0.002,  # 물타기 후 0.1% 수익 시 50% 매도
                "second_partial_sell_threshold": 0.004,  # 두 번째 50% 매도 (0.3%)
                "trailing_stop_activation": 0.004,  # 0.3% 이상 수익 시 트레일링 스탑 활성화
                "trailing_stop_base": 0.004,  # 기본 트레일링 스탑 0.3%
                "trailing_stop_multiplier": 0.5  # 추가 수익의 50%
            },
            "stop_loss": {
                "martingale4_threshold": 0.85,  # 4단계 15% 하락 시 손절
                "martingale5_threshold": 0.75   # 5단계 25% 하락 시 손절
            },
            "technical_indicators": {
                "rsi_period": 14,
                "rsi_oversold": 30,
                "rsi_overbought": 70,
                "bb_period": 20,
                "bb_std": 2.0,
                "ma_period": 20,
                "ema_short": 5,
                "ema_long": 20
            }
        }
        
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = default_config
            self.save_config()
        
        # 설정값을 인스턴스 변수로 설정
        self.initial_capital = self.config["initial_capital"]
        self.trading_fee = self.config["trading_fee"]
        self.leverage = self.config.get("leverage", 1)
        self.enable_long_short = self.config.get("enable_long_short", False)
        self.enable_technical_exit = self.config.get("enable_technical_exit", False)
        self.slides = self.config["slides"]
        self.profit_targets = self.config["profit_targets"]
        self.stop_loss = self.config["stop_loss"]
        self.technical_indicators = self.config["technical_indicators"]
    
    def save_config(self):
        """설정 파일 저장"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)
    
    def log_trade(self, trade_data: dict):
        """거래내역 로그 저장"""
        # 거래 타입 분류
        action = trade_data.get('action', '')
        profit_loss = trade_data.get('profit', 0)
        
        if 'ENTRY' in action:
            trade_data['type'] = 'entry'
        elif 'MARTINGALE' in action:
            trade_data['type'] = 'martingale'
        elif 'PROFIT' in action or 'TRAILING' in action:
            trade_data['type'] = 'profit_exit'
        elif 'LOSS' in action or 'STOP' in action:
            trade_data['type'] = 'loss_exit'
        elif 'SELL' in action:
            # 부분 매도의 경우 실제 수익/손실에 따라 분류
            if profit_loss > 0:
                trade_data['type'] = 'profit_exit'
            else:
                trade_data['type'] = 'loss_exit'
        else:
            trade_data['type'] = 'other'
        
        # 진입가격과 청산가격 설정
        if 'ENTRY' in action:
            trade_data['entry_price'] = trade_data.get('price', 0)
            trade_data['exit_price'] = 0
        else:
            trade_data['entry_price'] = 0
            trade_data['exit_price'] = trade_data.get('price', 0)
        
        # 수량 정보
        trade_data['quantity'] = trade_data.get('shares', 0)
        
        # 포지션 정보
        trade_data['position'] = trade_data.get('direction', 'N/A')
        
        # 물타기 레벨
        trade_data['martingale_level'] = trade_data.get('slide_level', 0)
        
        self.trade_log.append(trade_data)
    
    def save_trade_log(self, filename: str = None):
        """거래내역 로그 파일 저장"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"trade_log_{timestamp}.json"
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(script_dir, 'logs', filename)
        
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
        # with open(log_path, 'w', encoding='utf-8') as f:
        #     json.dump(self.trade_log, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"📝 거래내역 로그 저장: {log_path}")
        return log_path
    
    def save_detailed_trade_log(self, filename: str = None):
        """상세 거래 로그 파일 저장 (텍스트 형식)"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"detailed_trade_log_{timestamp}.log"
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(script_dir, 'logs', filename)
        
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("상세 거래 로그\n")
            f.write("=" * 80 + "\n")
            f.write(f"초기 자본: ${self.initial_capital:,.2f}\n")
            f.write(f"수수료율: {self.trading_fee * 100:.3f}%\n")
            f.write(f"레버리지: {self.leverage}배\n")
            f.write(f"총 거래 횟수: {len(self.trade_log)}회\n")
            f.write("=" * 80 + "\n\n")
            
            for i, trade in enumerate(self.trade_log, 1):
                f.write(f"[거래 #{i}] {trade.get('timestamp', 'N/A')}\n")
                f.write("-" * 60 + "\n")
                
                # 거래 타입에 따른 색상 구분
                action = trade.get('action', '')
                profit_loss = trade.get('profit', 0)
                
                if 'ENTRY' in action:
                    f.write("⚪ 진입 (흰색) - ENTRY\n")
                elif 'MARTINGALE' in action:
                    f.write("🟡 물타기 (노란색) - MARTINGALE\n")
                elif 'PROFIT' in action:
                    f.write("🟢 수익 청산 (초록색) - PROFIT EXIT\n")
                elif 'TRAILING' in action:
                    # 트레일링 스탑의 경우 실제 수익/손실에 따라 분류
                    if profit_loss > 0:
                        f.write("🟢 수익 청산 (초록색) - PROFIT EXIT\n")
                    else:
                        f.write("🔴 손실 청산 (빨간색) - LOSS EXIT\n")
                elif 'LOSS' in action or 'STOP' in action:
                    f.write("🔴 손실 청산 (빨간색) - LOSS EXIT\n")
                elif 'SELL' in action:
                    # 부분 매도의 경우 실제 수익/손실에 따라 분류
                    if profit_loss > 0:
                        f.write("🟢 수익 청산 (초록색) - PROFIT EXIT\n")
                    else:
                        f.write("🔴 손실 청산 (빨간색) - LOSS EXIT\n")
                else:
                    f.write(f"⚪ 기타 거래 - {action}\n")
                
                # 기본 정보
                f.write(f"거래 유형: {action}\n")
                f.write(f"방향: {trade.get('direction', 'N/A')}\n")
                f.write(f"현재가격: ${trade.get('price', 0):,.2f}\n")
                avg_price = trade.get('avg_price', 0)
                if avg_price > 0:
                    f.write(f"평균가격: ${avg_price:,.2f}\n")
                f.write(f"수량: {trade.get('shares', 0):,.6f}\n")
                f.write(f"분할: {trade.get('division', 'N/A')}\n")
                
                # 수수료 계산
                capital_used = trade.get('capital_used', 0)
                fee_amount = trade.get('fee', 0)
                net_amount = capital_used - fee_amount
                
                f.write(f"거래금액: ${capital_used:,.2f}\n")
                f.write(f"수수료: ${fee_amount:,.2f} ({self.trading_fee * 100:.3f}%)\n")
                f.write(f"수수료 차감 후 금액: ${net_amount:,.2f}\n")
                
                # 수익/손실 계산
                profit_loss = trade.get('profit', 0)
                if profit_loss != 0:
                    if profit_loss > 0:
                        f.write(f"💰 수익: +${profit_loss:,.2f}\n")
                    else:
                        f.write(f"💸 손실: ${profit_loss:,.2f}\n")
                
                # 물타기 정보
                slide_level = trade.get('slide_level', 0)
                if slide_level > 0:
                    f.write(f"물타기 단계: {slide_level}단계\n")
                
                # 레버리지 정보
                leverage = trade.get('leverage', 1)
                if leverage > 1:
                    f.write(f"레버리지: {leverage}배\n")
                
                # 추가 정보
                if trade.get('martingale_used'):
                    f.write(f"물타기 사용: {'예' if trade.get('martingale_used') else '아니오'}\n")
                
                if trade.get('target_threshold'):
                    f.write(f"목표 수익률: {trade.get('target_threshold') * 100:.2f}%\n")
                
                f.write("\n" + "=" * 80 + "\n\n")
        
        print(f"📝 상세 거래 로그 저장: {log_path}")
        return log_path
    
    def _check_martingale_profit_target(self, current_price: float, entry_price: float, slide_level: int) -> bool:
        """물타기 단계별 수익률 목표 체크"""
        # 0.5% 이상 수익 시 50% 매도
        return current_price >= entry_price * 1.005
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표 계산"""
        data = df.copy()
        
        # 설정에서 지표 파라미터 가져오기
        rsi_period = self.technical_indicators["rsi_period"]
        bb_period = self.technical_indicators["bb_period"]
        bb_std = self.technical_indicators["bb_std"]
        ma_period = self.technical_indicators["ma_period"]
        
        # 이동평균
        data['ma_5'] = data['close'].rolling(5).mean()
        data['ma_10'] = data['close'].rolling(10).mean()
        data['ma_20'] = data['close'].rolling(ma_period).mean()
        
        # 지수이동평균 (EMA)
        ema_short = self.technical_indicators["ema_short"]
        ema_long = self.technical_indicators["ema_long"]
        data['ema_5'] = data['close'].ewm(span=ema_short).mean()
        data['ema_20'] = data['close'].ewm(span=ema_long).mean()
        
        # RSI
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        data['rsi'] = 100 - (100 / (1 + rs))
        
        # 볼린저 밴드
        data['bb_mid'] = data['close'].rolling(bb_period).mean()
        data['bb_std'] = data['close'].rolling(bb_period).std()
        data['bb_upper'] = data['bb_mid'] + (data['bb_std'] * bb_std)
        data['bb_lower'] = data['bb_mid'] - (data['bb_std'] * bb_std)
        
        # 변동성
        data['volatility'] = data['close'].pct_change().rolling(20).std()
        
        # 가격 변화율
        data['price_change_1'] = data['close'].pct_change(1)
        data['price_change_5'] = data['close'].pct_change(5)
        
        return data
    
    def generate_martingale_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """물타기 전략 신호 생성"""
        data = df.copy()
        
        # 물타기 진입 조건: 가격 하락 시
        data['martingale_entry'] = 0
        data['martingale_exit'] = 0
        
        # 설정에서 임계값 가져오기
        rsi_oversold = self.technical_indicators["rsi_oversold"]
        rsi_overbought = self.technical_indicators["rsi_overbought"]
        
        # BB + RSI 전략 진입 조건: 하단 밴드 터치 + 과매도 시 롱 진입
        long_entry_condition = (data['close'] <= data['bb_lower']) & (data['rsi'] < rsi_oversold)
        data.loc[long_entry_condition, 'martingale_entry'] = 1
        
        # BB + RSI 전략 청산 조건: 상단 밴드 터치 + 과매수 시 숏 진입
        short_entry_condition = (data['close'] >= data['bb_upper']) & (data['rsi'] > rsi_overbought)
        data.loc[short_entry_condition, 'martingale_exit'] = 1
        
        return data
    
    
    def backtest_martingale_strategy(self, df: pd.DataFrame) -> dict:
        """물타기 전략 백테스트 (롱/숏 양방향, 레버리지 적용)"""
        print("🔄 물타기 전략 백테스트 시작...")
        print(f"📊 레버리지: {self.leverage}배")
        print(f"📊 롱/숏 양방향: {'활성화' if self.enable_long_short else '비활성화'}")
        
        capital = self.initial_capital
        total_capital_used = 0  # 레버리지 적용된 실제 사용 자본 추적
        trades = []
        equity_curve = []
        total_fees = 0
        
        # 롱 포지션 관리 (8분할)
        long_position = 0
        long_entry_price = 0
        long_total_cost = 0  # 총 투입 비용 (레버리지 적용된 실제 마진)
        long_slide_level = 0
        long_highest_price = 0
        long_trailing_stop_triggered = False
        long_partial_sell_done = False
        long_second_partial_sell_done = False  # 두 번째 50% 매도 완료 플래그
        long_last_martingale_time = None  # 마지막 물타기 시간
        
        # 숏 포지션 관리 (8분할)
        short_position = 0
        short_entry_price = 0
        short_total_cost = 0  # 총 투입 비용 (레버리지 적용된 실제 마진)
        short_slide_level = 0
        short_lowest_price = 0
        short_trailing_stop_triggered = False
        short_partial_sell_done = False
        short_second_partial_sell_done = False  # 두 번째 부분 매도 완료 플래그
        short_last_martingale_time = None  # 마지막 물타기 시간
        
        # 16분할 자본 분산 (각 분할당 자본)
        division_capital = capital / 16
        
        for i in range(len(df)):
            current_price = df['close'].iloc[i]
            current_time = df.index[i]
            
            # 롱 진입 신호 (과매도 조건) - 8분할 중 1분할 사용
            if (df['martingale_entry'].iloc[i] == 1 and long_position == 0 and (long_trailing_stop_triggered or long_slide_level == 0)):
                # 롱 진입 (1분할)
                long_slide_level = 1
                long_entry_price = current_price
                trade_value = division_capital * self.leverage  # 1분할 자본 사용
                fee = trade_value * self.trading_fee
                long_position = (trade_value - fee) / current_price
                long_total_cost = trade_value / self.leverage  # 실제 투입 마진
                capital -= long_total_cost
                total_capital_used += long_total_cost  # 실제 사용 자본 추적
                total_fees += fee
                
                trade_data = {
                    'timestamp': current_time,
                    'action': 'LONG_ENTRY_1/16',
                    'price': current_price,
                    'shares': long_position,
                    'slide_level': long_slide_level,
                    'capital_used': trade_value,
                    'fee': fee,
                    'leverage': self.leverage,
                    'direction': 'LONG',
                    'division': '1/8',
                    'visual_marker': 'white_circle',
                    'marker_color': 'white',
                    'entry_price': long_entry_price,
                    'avg_price': long_entry_price
                }
                trades.append(trade_data)
                self.log_trade(trade_data)
            
            # 숏 진입 신호 (과매수 조건) - 8분할 중 1분할 사용
            elif (self.enable_long_short and df['martingale_exit'].iloc[i] == 1 and 
                  short_position == 0):
                # 숏 진입 (1분할)
                short_slide_level = 1
                short_entry_price = current_price
                trade_value = division_capital * self.leverage  # 1분할 자본 사용
                fee = trade_value * self.trading_fee
                short_position = -(trade_value - fee) / current_price  # 음수로 숏 포지션
                short_total_cost = trade_value / self.leverage  # 실제 투입 마진
                capital -= short_total_cost
                total_capital_used += short_total_cost  # 실제 사용 자본 추적
                total_fees += fee
                
                trade_data = {
                    'timestamp': current_time,
                    'action': 'SHORT_ENTRY_1/16',
                    'price': current_price,
                    'shares': abs(short_position),
                    'slide_level': short_slide_level,
                    'capital_used': trade_value,
                    'fee': fee,
                    'leverage': self.leverage,
                    'direction': 'SHORT',
                    'division': '1/8',
                    'visual_marker': 'white_circle',
                    'marker_color': 'white',
                    'entry_price': short_entry_price,
                    'avg_price': short_entry_price
                }
                trades.append(trade_data)
                self.log_trade(trade_data)
            
            # 롱 물타기 (가격 하락 시) - 1,1,2,4 분할 사용
            elif (long_position > 0 and current_price < long_entry_price * 0.95):  # 5% 하락 시
                # 마지막 물타기로부터 최소 1시간(20캔들) 대기
                time_since_last_martingale = 20  # 3분봉 기준 1시간
                can_martingale = (long_last_martingale_time is None or 
                                (i - long_last_martingale_time) >= time_since_last_martingale)
                
                if long_slide_level < 5 and can_martingale:  # 최대 5단계까지
                    long_slide_level += 1
                    # 물타기 분할: 1,1,2,4,8
                    martingale_multipliers = [1, 1, 2, 4, 8]
                    multiplier = martingale_multipliers[long_slide_level - 1]
                    additional_value = division_capital * multiplier * self.leverage
                    fee = additional_value * self.trading_fee
                    additional_shares = (additional_value - fee) / current_price
                    long_position += additional_shares
                    additional_cost = additional_value / self.leverage  # 실제 투입 마진
                    long_total_cost += additional_cost  # 총 비용 누적
                    capital -= additional_cost
                    total_capital_used += additional_cost  # 실제 사용 자본 추적
                    total_fees += fee
                    
                    # 평균가격 계산 (가중평균)
                    total_shares = long_position
                    total_cost = long_total_cost * self.leverage
                    avg_price = total_cost / total_shares if total_shares > 0 else current_price
                    
                    # long_entry_price를 새로운 평균 가격으로 업데이트 (트레일링 스탑용)
                    long_entry_price = avg_price
                    
                    trade_data = {
                        'timestamp': current_time,
                        'action': f'LONG_MARTINGALE_{long_slide_level}',
                        'price': current_price,
                        'shares': additional_shares,
                        'slide_level': long_slide_level,
                        'capital_used': additional_value,
                        'fee': fee,
                        'leverage': self.leverage,
                        'direction': 'LONG',
                        'division': f'{multiplier}/8',
                        'visual_marker': 'white_circle',
                        'marker_color': 'white',
                        'entry_price': long_entry_price,
                        'avg_price': avg_price
                    }
                    trades.append(trade_data)
                    self.log_trade(trade_data)
                    
                    # 마지막 물타기 시간 기록
                    long_last_martingale_time = i
            
            # 숏 물타기 (가격 상승 시) - 1,1,2,4 분할 사용
            elif (short_position < 0 and current_price > short_entry_price * 1.05):  # 5% 상승 시
                # 마지막 물타기로부터 최소 1시간(20캔들) 대기
                time_since_last_martingale = 20  # 3분봉 기준 1시간
                can_martingale = (short_last_martingale_time is None or 
                                (i - short_last_martingale_time) >= time_since_last_martingale)
                
                if short_slide_level < 5 and can_martingale:  # 최대 5단계까지
                    short_slide_level += 1
                    # 물타기 분할: 1,1,2,4,8
                    martingale_multipliers = [1, 1, 2, 4, 8]
                    multiplier = martingale_multipliers[short_slide_level - 1]
                    additional_value = division_capital * multiplier * self.leverage
                    fee = additional_value * self.trading_fee
                    additional_shares = -(additional_value - fee) / current_price  # 음수로 숏 추가
                    short_position += additional_shares
                    additional_cost = additional_value / self.leverage  # 실제 투입 마진
                    short_total_cost += additional_cost  # 총 비용 누적
                    capital -= additional_cost
                    total_capital_used += additional_cost  # 실제 사용 자본 추적
                    total_fees += fee
                    
                    # 평균가격 계산 (가중평균)
                    total_shares = abs(short_position)
                    total_cost = short_total_cost * self.leverage
                    avg_price = total_cost / total_shares if total_shares > 0 else current_price
                    
                    # short_entry_price를 새로운 평균 가격으로 업데이트 (트레일링 스탑용)
                    short_entry_price = avg_price
                    
                    trade_data = {
                        'timestamp': current_time,
                        'action': f'SHORT_MARTINGALE_{short_slide_level}',
                        'price': current_price,
                        'shares': abs(additional_shares),
                        'slide_level': short_slide_level,
                        'capital_used': additional_value,
                        'fee': fee,
                        'leverage': self.leverage,
                        'direction': 'SHORT',
                        'division': f'{multiplier}/8',
                        'visual_marker': 'white_circle',
                        'marker_color': 'white',
                        'entry_price': short_entry_price,
                        'avg_price': avg_price
                    }
                    trades.append(trade_data)
                    self.log_trade(trade_data)
                    
                    # 마지막 물타기 시간 기록
                    short_last_martingale_time = i
            
            # 롱 포지션 4단계 손절 조건
            elif (long_position > 0 and long_slide_level >= 4 and long_slide_level < 5 and 
                  current_price < long_entry_price * self.stop_loss["martingale4_threshold"]):
                # 롱 손절매
                total_value = long_position * current_price
                fee = total_value * self.trading_fee
                net_value = total_value - fee
                capital += net_value
                total_fees += fee
                
                # 올바른 P&L 계산: 실제 투입 마진 대비 수익
                profit_loss = net_value - long_total_cost
                trade_data = {
                    'timestamp': current_time,
                    'action': 'LONG_STOP_LOSS_4',
                    'price': current_price,
                    'shares': long_position,
                    'slide_level': long_slide_level,
                    'profit': profit_loss,
                    'fee': fee,
                    'leverage': self.leverage,
                    'direction': 'LONG',
                    'division': '8/8',
                    'visual_marker': 'red_circle' if profit_loss < 0 else 'green_circle',
                    'marker_color': 'red' if profit_loss < 0 else 'green'
                }
                trades.append(trade_data)
                self.log_trade(trade_data)
                
                long_position = 0
                long_slide_level = 0
                long_entry_price = 0
                long_partial_sell_done = False
                long_second_partial_sell_done = False
                long_trailing_stop_triggered = False
            
            # 롱 포지션 5단계 손절 조건
            elif (long_position > 0 and long_slide_level >= 5 and 
                  current_price < long_entry_price * self.stop_loss["martingale5_threshold"]):
                # 롱 손절매
                total_value = long_position * current_price
                fee = total_value * self.trading_fee
                net_value = total_value - fee
                capital += net_value
                total_fees += fee
                
                # 올바른 P&L 계산: 실제 투입 마진 대비 수익
                profit_loss = net_value - long_total_cost
                trade_data = {
                    'timestamp': current_time,
                    'action': 'LONG_STOP_LOSS_5',
                    'price': current_price,
                    'shares': long_position,
                    'slide_level': long_slide_level,
                    'profit': profit_loss,
                    'fee': fee,
                    'leverage': self.leverage,
                    'direction': 'LONG',
                    'division': '8/8',
                    'visual_marker': 'red_circle' if profit_loss < 0 else 'green_circle',
                    'marker_color': 'red' if profit_loss < 0 else 'green'
                }
                trades.append(trade_data)
                self.log_trade(trade_data)
                
                long_position = 0
                long_slide_level = 0
                long_entry_price = 0
                long_partial_sell_done = False
                long_second_partial_sell_done = False
                long_trailing_stop_triggered = False
            
            # 숏 포지션 4단계 손절 조건
            elif (short_position < 0 and short_slide_level >= 4 and short_slide_level < 5 and 
                  current_price > short_entry_price * (2 - self.stop_loss["martingale4_threshold"])):
                # 숏 손절매
                total_value = abs(short_position) * current_price
                fee = total_value * self.trading_fee
                net_value = total_value - fee
                capital += net_value
                total_fees += fee
                
                # 숏 포지션 손절매 P&L 계산: 숏 포지션은 가격 하락 시 수익
                # 숏 포지션 수익 = (진입가격 - 현재가격) × 수량
                avg_entry_price = short_total_cost * self.leverage / abs(short_position) if short_position != 0 else short_entry_price
                price_profit = (avg_entry_price - current_price) * abs(short_position)
                profit_loss = price_profit - fee
                trade_data = {
                    'timestamp': current_time,
                    'action': 'SHORT_STOP_LOSS_4',
                    'price': current_price,
                    'shares': abs(short_position),
                    'slide_level': short_slide_level,
                    'profit': profit_loss,
                    'fee': fee,
                    'leverage': self.leverage,
                    'direction': 'SHORT',
                    'division': '8/8',
                    'visual_marker': 'red_circle' if profit_loss < 0 else 'green_circle',
                    'marker_color': 'red' if profit_loss < 0 else 'green'
                }
                trades.append(trade_data)
                self.log_trade(trade_data)
                
                short_position = 0
                short_slide_level = 0
                short_entry_price = 0
                short_partial_sell_done = False
                short_second_partial_sell_done = False
                short_trailing_stop_triggered = False
            
            # 숏 포지션 5단계 손절 조건
            elif (short_position < 0 and short_slide_level >= 5 and 
                  current_price > short_entry_price * (2 - self.stop_loss["martingale5_threshold"])):
                # 숏 손절매
                total_value = abs(short_position) * current_price
                fee = total_value * self.trading_fee
                net_value = total_value - fee
                capital += net_value
                total_fees += fee
                
                # 숏 포지션 손절매 P&L 계산: 숏 포지션은 가격 하락 시 수익
                # 숏 포지션 수익 = (진입가격 - 현재가격) × 수량
                avg_entry_price = short_total_cost * self.leverage / abs(short_position) if short_position != 0 else short_entry_price
                price_profit = (avg_entry_price - current_price) * abs(short_position)
                profit_loss = price_profit - fee
                trade_data = {
                    'timestamp': current_time,
                    'action': 'SHORT_STOP_LOSS_5',
                    'price': current_price,
                    'shares': abs(short_position),
                    'slide_level': short_slide_level,
                    'profit': profit_loss,
                    'fee': fee,
                    'leverage': self.leverage,
                    'direction': 'SHORT',
                    'division': '8/8',
                    'visual_marker': 'red_circle' if profit_loss < 0 else 'green_circle',
                    'marker_color': 'red' if profit_loss < 0 else 'green'
                }
                trades.append(trade_data)
                self.log_trade(trade_data)
                
                short_position = 0
                short_slide_level = 0
                short_entry_price = 0
                short_partial_sell_done = False
                short_second_partial_sell_done = False
                short_trailing_stop_triggered = False
            
            # 롱 포지션 수익 실현 (물타기 했을 때만)
            elif (long_position > 0 and not long_partial_sell_done and long_slide_level > 1):
                # 물타기를 했을 때만 0.1%에서 50% 매도
                target_multiplier = self.profit_targets["partial_sell_threshold"]  # 0.1%
                
                if current_price >= long_entry_price * (1 + target_multiplier):
                    # 첫 번째 50% 매도
                    sell_shares = long_position * 0.5
                    sell_value = sell_shares * current_price
                    fee = sell_value * self.trading_fee
                    net_value = sell_value - fee
                    capital += net_value
                    long_position -= sell_shares
                    total_fees += fee
                    long_partial_sell_done = True
                    long_highest_price = current_price
                    
                    # 부분 매도 시 P&L 계산: 매도 비율에 따른 실제 투입 마진 대비 수익
                    cost_ratio = sell_shares / (long_position + sell_shares)  # 매도 비율
                    profit_loss = net_value - (long_total_cost * self.leverage * cost_ratio)
                    
                    # 평균가격 계산
                    total_shares = long_position + sell_shares
                    total_cost = long_total_cost * self.leverage
                    avg_price = total_cost / total_shares if total_shares > 0 else current_price
                    
                    trade_data = {
                        'timestamp': current_time,
                        'action': f'LONG_PARTIAL_SELL_50%_LEVEL_{long_slide_level}',
                        'price': current_price,
                        'shares': sell_shares,
                        'slide_level': long_slide_level,
                        'profit': profit_loss,
                        'fee': fee,
                        'leverage': self.leverage,
                        'direction': 'LONG',
                        'division': f'{long_slide_level}/8',
                        'martingale_used': long_slide_level > 1,
                        'target_threshold': target_multiplier,
                        'visual_marker': 'green_circle',
                        'marker_color': 'green',
                        'entry_price': long_entry_price,
                        'avg_price': avg_price
                    }
                    trades.append(trade_data)
                    self.log_trade(trade_data)
            
            # 롱 포지션 두 번째 수익 실현 (물타기 했을 때만)
            if (long_position > 0 and long_partial_sell_done and not long_second_partial_sell_done and 
                long_slide_level > 1 and 
                current_price >= long_entry_price * (1 + self.profit_targets["second_partial_sell_threshold"]) and
                not long_trailing_stop_triggered):
                # 디버깅: 두 번째 50% 매도 조건 확인
                required_price = long_entry_price * (1 + self.profit_targets["second_partial_sell_threshold"])
                profit_pct = (current_price - long_entry_price) / long_entry_price * 100
                print(f"🔍 두 번째 50% 매도 조건 확인:")
                print(f"   현재가격: ${current_price:,.2f}")
                print(f"   진입가격: ${long_entry_price:,.2f}")
                print(f"   필요가격: ${required_price:,.2f}")
                print(f"   수익률: {profit_pct:.3f}%")
                print(f"   물타기단계: {long_slide_level}")
                print(f"   첫매도완료: {long_partial_sell_done}")
                print(f"   트레일링스탑: {long_trailing_stop_triggered}")
                # 두 번째 50% 매도 (가진 것의 50%)
                sell_shares = long_position * 0.5  # 가진 것의 50%
                sell_value = sell_shares * current_price
                fee = sell_value * self.trading_fee
                net_value = sell_value - fee
                capital += net_value
                long_position -= sell_shares  # 포지션 감소
                total_fees += fee
                long_second_partial_sell_done = True  # 두 번째 50% 매도 완료
                
                # 두 번째 부분 매도 시 P&L 계산: 매도 비율에 따른 실제 투입 마진 대비 수익
                cost_ratio = sell_shares / (long_position + sell_shares)  # 매도 비율
                profit_loss = net_value - (long_total_cost * self.leverage * cost_ratio)
                trade_data = {
                    'timestamp': current_time,
                    'action': f'LONG_PARTIAL_SELL_50%_LEVEL_{long_slide_level}_2ND',
                    'price': current_price,
                    'shares': sell_shares,
                    'slide_level': long_slide_level,
                    'profit': profit_loss,
                    'fee': fee,
                    'leverage': self.leverage,
                    'direction': 'LONG',
                    'division': f'{long_slide_level}/8',
                    'martingale_used': True,
                    'target_threshold': self.profit_targets["second_partial_sell_threshold"],
                    'visual_marker': 'green_circle',
                    'marker_color': 'green'
                }
                trades.append(trade_data)
                self.log_trade(trade_data)
                
                # 나머지 25%는 트레일링 스탑으로 관리
                # 포지션은 완전 청산하지 않고 트레일링 스탑으로 넘김
            
            # 숏 포지션 수익 실현 (물타기 했을 때만)
            elif (short_position < 0 and not short_partial_sell_done and short_slide_level > 1):
                # 물타기를 했을 때만 0.1%에서 50% 매도
                target_multiplier = self.profit_targets["partial_sell_threshold"]  # 0.1%
                
                if current_price <= short_entry_price * (1 - target_multiplier):
                    # 첫 번째 50% 매도
                    sell_shares = abs(short_position) * 0.5
                    sell_value = sell_shares * current_price
                    fee = sell_value * self.trading_fee
                    net_value = sell_value - fee
                    capital += net_value
                    short_position += sell_shares  # 숏 포지션 감소
                    total_fees += fee
                    short_partial_sell_done = True
                    short_lowest_price = current_price
                    
                    # 숏 부분 매도 시 P&L 계산: 숏 포지션은 가격 하락 시 수익
                    # 숏 포지션 수익 = (진입가격 - 현재가격) × 매도수량
                    avg_entry_price = short_total_cost * self.leverage / abs(short_position + sell_shares) if (short_position + sell_shares) != 0 else short_entry_price
                    price_profit = (avg_entry_price - current_price) * sell_shares
                    profit_loss = price_profit - fee
                    trade_data = {
                        'timestamp': current_time,
                        'action': f'SHORT_PARTIAL_SELL_50%_LEVEL_{short_slide_level}',
                        'price': current_price,
                        'shares': sell_shares,
                        'slide_level': short_slide_level,
                        'profit': profit_loss,
                        'fee': fee,
                        'leverage': self.leverage,
                        'direction': 'SHORT',
                        'division': f'{short_slide_level}/8',
                        'martingale_used': short_slide_level > 1,
                        'target_threshold': target_multiplier,
                        'visual_marker': 'green_circle',
                        'marker_color': 'green',
                        'avg_price': avg_entry_price
                    }
                    trades.append(trade_data)
                    self.log_trade(trade_data)
            
            # 숏 포지션 두 번째 수익 실현 (물타기 했을 때만, 한 번만 실행)
            elif (short_position < 0 and short_partial_sell_done and not short_second_partial_sell_done and 
                  short_slide_level > 1 and current_price <= short_entry_price * (1 - self.profit_targets["second_partial_sell_threshold"]) and
                  not short_trailing_stop_triggered):
                # 두 번째 50% 매도 (가진 것의 50%)
                sell_shares = abs(short_position) * 0.5  # 가진 것의 50%
                sell_value = sell_shares * current_price
                fee = sell_value * self.trading_fee
                net_value = sell_value - fee
                capital += net_value
                short_position += sell_shares  # 숏 포지션 감소
                total_fees += fee
                short_second_partial_sell_done = True  # 두 번째 부분 매도 완료
                
                # 숏 두 번째 부분 매도 시 P&L 계산: 숏 포지션은 가격 하락 시 수익
                # 숏 포지션 수익 = (진입가격 - 현재가격) × 매도수량
                avg_entry_price = short_total_cost * self.leverage / abs(short_position + sell_shares) if (short_position + sell_shares) != 0 else short_entry_price
                price_profit = (avg_entry_price - current_price) * sell_shares
                profit_loss = price_profit - fee
                trade_data = {
                    'timestamp': current_time,
                    'action': f'SHORT_PARTIAL_SELL_50%_LEVEL_{short_slide_level}_2ND',
                    'price': current_price,
                    'shares': sell_shares,
                    'slide_level': short_slide_level,
                    'profit': profit_loss,
                    'fee': fee,
                    'leverage': self.leverage,
                    'direction': 'SHORT',
                    'division': f'{short_slide_level}/8',
                    'martingale_used': True,
                    'target_threshold': self.profit_targets["second_partial_sell_threshold"],
                    'visual_marker': 'green_circle',
                    'marker_color': 'green',
                    'avg_price': avg_entry_price
                }
                trades.append(trade_data)
                self.log_trade(trade_data)
                
                # 나머지 25%는 트레일링 스탑으로 관리
                # 포지션은 완전 청산하지 않고 트레일링 스탑으로 넘김
            
            # 롱 포지션 트레일링 스탑 (독립적으로 실행)
            if (long_position > 0 and not long_trailing_stop_triggered):
                current_profit_pct = (current_price - long_entry_price) / long_entry_price
                
                # 롱 포지션이 있을 때는 현재 가격을 추적 (숏 포지션 거래와 관계없이)
                if current_profit_pct >= 0.003 and current_price > long_highest_price:
                    long_highest_price = current_price
                
                activation_threshold = self.profit_targets["trailing_stop_activation"]
                base_threshold = self.profit_targets["trailing_stop_base"]
                multiplier = self.profit_targets["trailing_stop_multiplier"]
                
                if current_profit_pct >= activation_threshold:
                    additional_profit = current_profit_pct - activation_threshold
                    stop_threshold = base_threshold + (additional_profit * multiplier)
                    stop_price = long_highest_price * (1 - stop_threshold)
                    
                    if current_price <= stop_price:
                        sell_value = long_position * current_price
                        fee = sell_value * self.trading_fee
                        net_value = sell_value - fee
                        capital += net_value
                        total_fees += fee
                        long_trailing_stop_triggered = True
                        
                        # 트레일링 스탑 P&L 계산: 나머지 50% 포지션의 실제 투입 비용 대비 수익
                        remaining_cost = long_total_cost * 0.5  # 나머지 50% 비용
                        profit_loss = net_value - remaining_cost
                        # 평균가격 계산: 전체 포지션의 평균 진입가격 (레버리지 적용)
                        total_shares = long_position
                        avg_price = (long_total_cost * self.leverage) / total_shares if total_shares > 0 else long_entry_price
                        
                        trade_data = {
                            'timestamp': current_time,
                            'action': f'LONG_TRAILING_STOP_PROFIT_{current_profit_pct:.3f}',
                            'price': current_price,
                            'shares': long_position,
                            'slide_level': long_slide_level,
                            'profit': profit_loss,
                            'fee': fee,
                            'leverage': self.leverage,
                            'direction': 'LONG',
                            'division': f'{long_slide_level}/8',
                            'visual_marker': 'green_circle' if profit_loss > 0 else 'red_circle',
                            'marker_color': 'green' if profit_loss > 0 else 'red',
                            'avg_price': avg_price
                        }
                        trades.append(trade_data)
                        self.log_trade(trade_data)
                        
                        long_position = 0
                        long_slide_level = 0
                        long_entry_price = 0
                        long_partial_sell_done = False
                        long_trailing_stop_triggered = False
            
            # 숏 포지션 트레일링 스탑 (독립적으로 실행)
            if (short_position < 0 and not short_trailing_stop_triggered):
                current_profit_pct = (short_entry_price - current_price) / short_entry_price
                
                if current_profit_pct >= 0.003 and current_price < short_lowest_price:
                    short_lowest_price = current_price
                
                activation_threshold = self.profit_targets["trailing_stop_activation"]
                base_threshold = self.profit_targets["trailing_stop_base"]
                multiplier = self.profit_targets["trailing_stop_multiplier"]
                
                if current_profit_pct >= activation_threshold:
                    additional_profit = current_profit_pct - activation_threshold
                    stop_threshold = base_threshold + (additional_profit * multiplier)
                    stop_price = short_lowest_price * (1 + stop_threshold)
                    
                    if current_price >= stop_price:
                        sell_value = abs(short_position) * current_price
                        fee = sell_value * self.trading_fee
                        net_value = sell_value - fee
                        capital += net_value
                        total_fees += fee
                        short_trailing_stop_triggered = True
                        
                        # 숏 포지션 트레일링 스탑 P&L 계산: 숏 포지션은 가격 하락 시 수익
                        # 숏 포지션 수익 = (진입가격 - 현재가격) × 수량
                        avg_entry_price = short_total_cost * self.leverage / abs(short_position) if short_position != 0 else short_entry_price
                        price_profit = (avg_entry_price - current_price) * abs(short_position)
                        profit_loss = price_profit - fee
                        trade_data = {
                            'timestamp': current_time,
                            'action': f'SHORT_TRAILING_STOP_PROFIT_{current_profit_pct:.3f}',
                            'price': current_price,
                            'shares': abs(short_position),
                            'slide_level': short_slide_level,
                            'profit': profit_loss,
                            'fee': fee,
                            'leverage': self.leverage,
                            'direction': 'SHORT',
                            'division': f'{short_slide_level}/8',
                            'visual_marker': 'green_circle',
                            'marker_color': 'green'
                        }
                        trades.append(trade_data)
                        self.log_trade(trade_data)
                        
                        short_position = 0
                        short_slide_level = 0
                        short_entry_price = 0
                        short_partial_sell_done = False
                        short_second_partial_sell_done = False
                        short_trailing_stop_triggered = False
            
            # 기술적 지표 기반 청산 (설정에서 활성화된 경우에만)
            elif (self.enable_technical_exit and df['martingale_exit'].iloc[i] == 1 and long_position > 0):
                # 롱 포지션 전체 청산
                total_value = long_position * current_price
                fee = total_value * self.trading_fee
                net_value = total_value - fee
                capital += net_value
                total_fees += fee
                
                # 기술적 지표 기반 청산 P&L 계산
                profit_loss = net_value - long_total_cost
                trade_data = {
                    'timestamp': current_time,
                    'action': 'LONG_TECHNICAL_EXIT',
                    'price': current_price,
                    'shares': long_position,
                    'slide_level': long_slide_level,
                    'profit': profit_loss,
                    'fee': fee,
                    'leverage': self.leverage,
                    'direction': 'LONG',
                    'visual_marker': 'red_circle' if profit_loss < 0 else 'green_circle',
                    'marker_color': 'red' if profit_loss < 0 else 'green'
                }
                trades.append(trade_data)
                self.log_trade(trade_data)
                
                long_position = 0
                long_slide_level = 0
                long_entry_price = 0
                long_partial_sell_done = False
                long_second_partial_sell_done = False
                long_trailing_stop_triggered = False
            
            elif (self.enable_technical_exit and df['martingale_entry'].iloc[i] == 1 and short_position < 0):
                # 숏 포지션 전체 청산
                total_value = abs(short_position) * current_price
                fee = total_value * self.trading_fee
                net_value = total_value - fee
                capital += net_value
                total_fees += fee
                
                # 숏 포지션 기술적 지표 기반 청산 P&L 계산
                avg_entry_price = short_total_cost * self.leverage / abs(short_position) if short_position != 0 else short_entry_price
                price_profit = (avg_entry_price - current_price) * abs(short_position)
                profit_loss = price_profit - fee
                trade_data = {
                    'timestamp': current_time,
                    'action': 'SHORT_TECHNICAL_EXIT',
                    'price': current_price,
                    'shares': abs(short_position),
                    'slide_level': short_slide_level,
                    'profit': profit_loss,
                    'fee': fee,
                    'leverage': self.leverage,
                    'direction': 'SHORT',
                    'visual_marker': 'red_circle' if profit_loss < 0 else 'green_circle',
                    'marker_color': 'red' if profit_loss < 0 else 'green'
                }
                trades.append(trade_data)
                self.log_trade(trade_data)
                
                short_position = 0
                short_slide_level = 0
                short_entry_price = 0
                short_partial_sell_done = False
                short_second_partial_sell_done = False
                short_trailing_stop_triggered = False
            
            # 자산 가치 계산 (롱/숏 포지션 모두 포함)
            long_value = long_position * current_price if long_position > 0 else 0
            short_value = abs(short_position) * current_price if short_position < 0 else 0
            current_equity = capital + long_value + short_value
            equity_curve.append(current_equity)
        
        # 최종 결과 계산 (롱/숏 포지션 모두 포함)
        final_long_value = long_position * df['close'].iloc[-1] if long_position > 0 else 0
        final_short_value = abs(short_position) * df['close'].iloc[-1] if short_position < 0 else 0
        final_capital = capital + final_long_value + final_short_value
        
        # 올바른 수익률 계산: 실제 투입한 마진 대비 수익률
        # 수정된 부분: initial_capital 기준으로 수익률 계산
        if self.initial_capital > 0:
            total_return = (final_capital - self.initial_capital) / self.initial_capital * 100
        else:
            total_return = 0
        
        # 승률 계산
        winning_trades = sum(1 for trade in trades if trade.get('profit', 0) > 0)
        total_trades = len(trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'strategy': 'martingale',
            'final_capital': final_capital,
            'total_return': total_return,
            'trades': trades,
            'equity_curve': equity_curve,
            'total_fees': total_fees,
            'win_rate': win_rate,
            'winning_trades': winning_trades,
            'total_trades': total_trades,
            'leverage': self.leverage,
            'total_capital_used': total_capital_used,
            'effective_leverage': total_capital_used / self.initial_capital if self.initial_capital > 0 else 1
        }
    
    
    def run_martingale_backtest(self, data: pd.DataFrame, initial_capital: float = None) -> dict:
        """물타기 전략 백테스트 실행"""
        # 초기 자본 설정 (매개변수로 전달된 경우 사용)
        if initial_capital is not None:
            self.initial_capital = initial_capital
            
        print("🚀 물타기 전략 백테스트 시작!")
        print("=" * 60)
        print(f"💰 초기 자본: ${self.initial_capital:,.2f}")
        print(f"📅 기간: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
        print(f"📊 데이터: {len(data):,}개 캔들")
        print("=" * 60)
        
        # 1. 기술적 지표 계산
        print("🔄 기술적 지표 계산 중...")
        data_with_indicators = self.calculate_technical_indicators(data)
        
        # 2. 물타기 전략 신호 생성
        print("🔄 물타기 전략 신호 생성 중...")
        data_martingale = self.generate_martingale_signals(data_with_indicators)
        
        # 3. 물타기 전략 백테스트 실행
        print("\n🔄 물타기 전략 백테스트 실행 중...")
        martingale_results = self.backtest_martingale_strategy(data_martingale)
        
        # 4. 결과 분석
        print("\n📊 물타기 전략 결과")
        print("=" * 60)
        
        print(f"🎯 물타기 전략:")
        print(f"   최종 자본: ${martingale_results['final_capital']:,.2f}")
        print(f"   수익률: {martingale_results['total_return']:.2f}%")
        print(f"   거래 횟수: {martingale_results.get('total_trades', 0)}회")
        print(f"   승률: {martingale_results.get('win_rate', 0):.1f}%")
        print(f"   총 수수료: ${martingale_results.get('total_fees', 0):,.2f}")
        print(f"   레버리지: {martingale_results.get('leverage', 1)}배")
        print(f"   실제 사용 자본: ${martingale_results.get('total_capital_used', 0):,.2f}")
        print(f"   유효 레버리지: {martingale_results.get('effective_leverage', 1):.2f}배")
        
        return martingale_results

def load_btc_data(year: int = 2024, month: int = 1) -> pd.DataFrame:
    """BTC 데이터 로드"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, 'data', 'BTCUSDT', '3m', f'BTCUSDT_3m_{year}.csv')
    
    if not os.path.exists(data_path):
        print(f"❌ 데이터 파일을 찾을 수 없습니다: {data_path}")
        return None
    
    print(f"📊 {year}년 {month}월 BTC 데이터 로드 중...")
    df = pd.read_csv(data_path, index_col='timestamp', parse_dates=True)
    
    # 월별 필터링
    if month is not None:
        df = df[df.index.month == month]
    
    print(f"✅ 데이터 로드 완료: {len(df):,}개 캔들")
    print(f"📅 기간: {df.index[0]} ~ {df.index[-1]}")
    
    return df

def main():
    """메인 실행 함수"""
    print("🚀 물타기 봇 시스템 시작!")
    print("부분 매도 + 트레일링 스탑 전략")
    print("=" * 60)
    
    # 데이터 로드
    data = load_btc_data(2024, 1)
    if data is None:
        print("❌ 데이터 로드 실패")
        return
    
    # 물타기 봇 초기화
    bot = WaterBot()
    
    # 백테스트 실행
    results = bot.run_martingale_backtest(data)
    
    # 거래내역 로그 저장
    trade_log_file = bot.save_trade_log()
    detailed_log_file = bot.save_detailed_trade_log()
    
    # 결과 저장
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results_file = os.path.join(script_dir, 'logs', 'water_bot_results.json')
    
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            'final_capital': results['final_capital'],
            'total_return': results['total_return'],
            'trades_count': results.get('total_trades', 0),
            'win_rate': results.get('win_rate', 0),
            'total_fees': results.get('total_fees', 0),
            'leverage': bot.leverage,
            'long_short_enabled': bot.enable_long_short,
            'trade_log_file': trade_log_file,
            'detailed_log_file': detailed_log_file
        }, f, indent=2, ensure_ascii=False)
    
    #print(f"\n💾 결과 저장 완료: {results_file}")
    #print(f"📝 거래내역 로그 (JSON): {trade_log_file}")
    #print(f"📝 상세 거래 로그 (TEXT): {detailed_log_file}")
    #print("🎉 물타기 봇 분석 완료!")

if __name__ == "__main__":
    main()