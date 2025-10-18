#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
- 규칙1 : 미래데이터를 사용하지 않는다.
- 규칙2 : 랜덤데이터를 사용하지 않고 과거 csv파일을 로드해서 사용한다.
- 규칙3 : 살때 0.05%수수료, 팔때 0.05%수수료를 꼭 적용해야 한다.

🚀 하루 2% 수익률 목표 백테스트 봇 (트레일링 스탑 포함)
- 레버리지 1배
- 수익 2% : 손절 1% 비율
- 트레일링 스탑: 2% 수익 달성시 활성화
- 2024년 BTC 데이터 사용
"""

import sys
import os
import pandas as pd
import numpy as np
import datetime as dt
import talib
from typing import Dict, List, Tuple, Optional
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Simple1PercentBot:
    def __init__(self, initial_balance: float = 10000, leverage: int = 1):
        """
        하루 2% 수익률 목표 백테스트 봇 (트레일링 스탑 포함)
        
        Args:
            initial_balance: 초기 자본금 (USDT)
            leverage: 레버리지 (1배로 제한)
        """
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.leverage = leverage
        
        # 거래 파라미터 (개선된 버전)
        self.target_profit_rate = 0.008   # 0.8% 수익 목표 (수수료 고려)
        self.max_daily_loss = 0.004       # 0.4% 최대 손실
        self.trailing_stop_activation = 0.006  # 0.6% 수익 달성시 트레일링 스탑 활성화
        self.position_size = 0.15         # 자본의 15% 포지션 (증가)
        self.commission_rate = 0.0005    # 0.05% 수수료 (매수/매도 각각)
        self.atr_stop_multiplier = 2.0   # ATR 기반 손절을 위한 승수
        
        # 신호 조건 (완화)
        self.min_signal_threshold = 2    # 최소 2개 신호 일치 (완화)
        
        # 포지션 관리
        self.positions = []
        self.trades = []
        self.daily_pnl = []
        
        # 통계
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.max_drawdown = 0
        self.peak_balance = initial_balance
        
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표 계산"""
        df = df.copy()
        
        # 이동평균선
        df['ma_5'] = talib.SMA(df['close'], timeperiod=5)
        df['ma_20'] = talib.SMA(df['close'], timeperiod=20)
        df['ma_50'] = talib.SMA(df['close'], timeperiod=50)
        
        # RSI
        df['rsi'] = talib.RSI(df['close'], timeperiod=14)
        
        # ATR (변동성)
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        
        # 볼린저밴드
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
            df['close'], timeperiod=20, nbdevup=2, nbdevdn=2
        )
        
        # MACD
        df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(
            df['close'], fastperiod=12, slowperiod=26, signalperiod=9
        )
        
        return df
    
    def generate_signal(self, df: pd.DataFrame, current_idx: int) -> Dict:
        """거래 신호 생성"""
        if current_idx < 50:  # 충분한 데이터 확보
            return {'action': 'hold', 'confidence': 0}
        
        current_data = df.iloc[:current_idx+1]
        current_price = current_data['close'].iloc[-1]
        current_atr = current_data['atr'].iloc[-1]
        
        # 전략 1: 이동평균선 크로스
        ma_signal = self._ma_cross_signal(current_data)
        
        # 전략 2: RSI 과매수/과매도
        rsi_signal = self._rsi_signal(current_data)
        
        # 전략 3: 변동성 돌파
        volatility_signal = self._volatility_breakout_signal(current_data)
        
        # 전략 4: 볼린저밴드
        bb_signal = self._bollinger_bands_signal(current_data)
        
        # 신호 투표
        signals = [ma_signal, rsi_signal, volatility_signal, bb_signal]
        buy_signals = sum(1 for s in signals if s['action'] == 'buy')
        sell_signals = sum(1 for s in signals if s['action'] == 'sell')
        
        # 3개 이상 신호가 일치할 때 거래 (조건 강화)
        if buy_signals >= self.min_signal_threshold:
            return {
                'action': 'buy',
                'confidence': buy_signals / 4,
                'target_price': current_price * (1 + self.target_profit_rate),
                'stop_loss': current_price - (current_atr * self.atr_stop_multiplier)
            }
        elif sell_signals >= self.min_signal_threshold:
            return {
                'action': 'sell',
                'confidence': sell_signals / 4,
                'target_price': current_price * (1 - self.target_profit_rate),
                'stop_loss': current_price + (current_atr * self.atr_stop_multiplier)
            }
        else:
            return {'action': 'hold', 'confidence': 0}
    
    def _ma_cross_signal(self, df: pd.DataFrame) -> Dict:
        """이동평균선 크로스 신호 (개선된 버전)"""
        if len(df) < 2:
            return {'action': 'hold', 'confidence': 0}
        
        ma_5 = df['ma_5'].iloc[-1]
        ma_20 = df['ma_20'].iloc[-1]
        ma_5_prev = df['ma_5'].iloc[-2]
        ma_20_prev = df['ma_20'].iloc[-2]
        current_price = df['close'].iloc[-1]
        
        # 강한 골든크로스 (상승 신호) - 가격도 함께 상승
        if (ma_5 > ma_20 and ma_5_prev <= ma_20_prev and 
            current_price > ma_5 and current_price > ma_20):
            return {'action': 'buy', 'confidence': 0.9}
        # 강한 데드크로스 (하락 신호) - 가격도 함께 하락
        elif (ma_5 < ma_20 and ma_5_prev >= ma_20_prev and 
              current_price < ma_5 and current_price < ma_20):
            return {'action': 'sell', 'confidence': 0.9}
        
        return {'action': 'hold', 'confidence': 0}
    
    def _rsi_signal(self, df: pd.DataFrame) -> Dict:
        """RSI 신호 (완화된 버전)"""
        if len(df) < 2:
            return {'action': 'hold', 'confidence': 0}
        
        rsi = df['rsi'].iloc[-1]
        rsi_prev = df['rsi'].iloc[-2]
        
        # RSI 과매도에서 회복 (조건 완화)
        if rsi < 40 and rsi > rsi_prev:
            return {'action': 'buy', 'confidence': 0.6}
        # RSI 과매수에서 하락 (조건 완화)
        elif rsi > 60 and rsi < rsi_prev:
            return {'action': 'sell', 'confidence': 0.6}
        
        return {'action': 'hold', 'confidence': 0}
    
    def _volatility_breakout_signal(self, df: pd.DataFrame) -> Dict:
        """변동성 돌파 신호"""
        if len(df) < 20:
            return {'action': 'hold', 'confidence': 0}
        
        current_price = df['close'].iloc[-1]
        high_20 = df['high'].rolling(20).max().iloc[-2]
        low_20 = df['low'].rolling(20).min().iloc[-2]
        
        # 상승 돌파
        if current_price > high_20:
            return {'action': 'buy', 'confidence': 0.6}
        # 하락 돌파
        elif current_price < low_20:
            return {'action': 'sell', 'confidence': 0.6}
        
        return {'action': 'hold', 'confidence': 0}
    
    def _bollinger_bands_signal(self, df: pd.DataFrame) -> Dict:
        """볼린저밴드 신호 (수정된 버전 - 평균 회귀)"""
        if len(df) < 2 or 'bb_upper' not in df.columns or df['bb_upper'].isnull().all():
            return {'action': 'hold', 'confidence': 0}
        
        current_price = df['close'].iloc[-1]
        
        # 하단 밴드 하향 돌파 후 다시 안으로 들어올 때 (매수)
        if df['close'].iloc[-2] < df['bb_lower'].iloc[-2] and current_price > df['bb_lower'].iloc[-1]:
            return {'action': 'buy', 'confidence': 0.7}
        # 상단 밴드 상향 돌파 후 다시 안으로 들어올 때 (매도)
        elif df['close'].iloc[-2] > df['bb_upper'].iloc[-2] and current_price < df['bb_upper'].iloc[-1]:
            return {'action': 'sell', 'confidence': 0.7}
        
        return {'action': 'hold', 'confidence': 0}
    
    def open_position(self, side: str, price: float, timestamp: dt.datetime, signal: Dict):
        """포지션 오픈 (수수료 적용)"""
        # 포지션 크기 계산
        position_value = self.current_balance * self.position_size * self.leverage
        amount = position_value / price
        
        # 매수 수수료 계산 및 적용
        buy_commission = position_value * self.commission_rate
        self.current_balance -= buy_commission
        
        # 포지션 생성
        position = {
            'id': len(self.positions) + 1,
            'side': side,
            'amount': amount,
            'price': price,
            'timestamp': timestamp,
            'target_price': signal['target_price'],
            'stop_loss': signal['stop_loss'],
            'trailing_stop_activated': False,
            'highest_price': price if side == 'buy' else price,
            'lowest_price': price if side == 'sell' else price,
            'buy_commission': buy_commission
        }
        
        self.positions.append(position)
        self.total_trades += 1
        
        logger.info(f"포지션 오픈: {side} {amount:.4f} @ {price:.2f} (수수료: {buy_commission:.2f} USDT)")
    
    def close_position(self, position: Dict, price: float, reason: str):
        """포지션 청산 (수수료 적용)"""
        # 반대 거래 실행
        opposite_side = 'sell' if position['side'] == 'buy' else 'buy'
        
        # 손익 계산
        if position['side'] == 'buy':
            pnl = (price - position['price']) * position['amount']
        else:
            pnl = (position['price'] - price) * position['amount']
        
        # 매도 수수료 계산 및 적용
        sell_value = price * position['amount']
        sell_commission = sell_value * self.commission_rate
        total_commission = position.get('buy_commission', 0) + sell_commission
        
        # 수수료를 제외한 순손익 계산
        net_pnl = pnl - total_commission
        
        # 잔고 업데이트
        self.current_balance += net_pnl
        
        # 거래 기록
        trade_record = {
            'id': position['id'],
            'side': position['side'],
            'amount': position['amount'],
            'entry_price': position['price'],
            'exit_price': price,
            'pnl': pnl,
            'net_pnl': net_pnl,
            'total_commission': total_commission,
            'reason': reason,
            'timestamp': dt.datetime.now()
        }
        
        self.trades.append(trade_record)
        
        if net_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        logger.info(f"포지션 청산: {position['side']} {position['amount']:.4f} @ {price:.2f}, PnL: {pnl:.2f} USDT, 순손익: {net_pnl:.2f} USDT (수수료: {total_commission:.2f} USDT), 이유: {reason}")
    
    def check_exit_conditions(self, position: Dict, current_price: float) -> Optional[str]:
        """청산 조건 체크 (트레일링 스탑 포함)"""
        if position['side'] == 'buy':
            # 최고가 업데이트
            if current_price > position['highest_price']:
                position['highest_price'] = current_price
                
                # 트레일링 스탑 활성화 체크 (2% 수익 달성시)
                profit_pct = (current_price - position['price']) / position['price']
                if profit_pct >= self.trailing_stop_activation and not position['trailing_stop_activated']:
                    position['trailing_stop_activated'] = True
                    logger.info(f"트레일링 스탑 활성화: {profit_pct:.2%} 수익 달성")
            
            # 트레일링 스탑이 활성화된 경우
            if position['trailing_stop_activated']:
                # 현재가가 최고가에서 1% 하락시 청산
                trailing_stop_price = position['highest_price'] * (1 - 0.01)
                if current_price <= trailing_stop_price:
                    return 'trailing_stop'
            
            # 익절
            if current_price >= position['target_price']:
                return 'take_profit'
            # 손절
            elif current_price <= position['stop_loss']:
                return 'stop_loss'
        else:
            # 최저가 업데이트
            if current_price < position['lowest_price']:
                position['lowest_price'] = current_price
                
                # 트레일링 스탑 활성화 체크 (2% 수익 달성시)
                profit_pct = (position['price'] - current_price) / position['price']
                if profit_pct >= self.trailing_stop_activation and not position['trailing_stop_activated']:
                    position['trailing_stop_activated'] = True
                    logger.info(f"트레일링 스탑 활성화: {profit_pct:.2%} 수익 달성")
            
            # 트레일링 스탑이 활성화된 경우
            if position['trailing_stop_activated']:
                # 현재가가 최저가에서 1% 상승시 청산
                trailing_stop_price = position['lowest_price'] * (1 + 0.01)
                if current_price >= trailing_stop_price:
                    return 'trailing_stop'
            
            # 익절
            if current_price <= position['target_price']:
                return 'take_profit'
            # 손절
            elif current_price >= position['stop_loss']:
                return 'stop_loss'
        
        return None
    
    def run_backtest(self, df: pd.DataFrame, start_date: str = None, end_date: str = None) -> Dict:
        """백테스트 실행"""
        logger.info("백테스트 시작...")
        
        # 날짜 필터링
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        # 초기화
        self.current_balance = self.initial_balance
        self.positions = []
        self.trades = []
        self.daily_pnl = []
        
        # 기술적 지표 계산
        df = self.calculate_technical_indicators(df)
        
        # 백테스트 실행
        for i in range(50, len(df)):  # 충분한 데이터 확보 후 시작
            current_price = df['close'].iloc[i]
            current_time = df.index[i]
            
            # 청산 조건 체크
            positions_to_close = []
            for j, position in enumerate(self.positions):
                exit_reason = self.check_exit_conditions(position, current_price)
                if exit_reason:
                    positions_to_close.append((j, exit_reason))
            
            # 포지션 청산
            for j, exit_reason in reversed(positions_to_close):
                position = self.positions.pop(j)
                self.close_position(position, current_price, exit_reason)
            
            # 새로운 신호 생성 (최대 1개 포지션)
            if len(self.positions) == 0:
                signal = self.generate_signal(df, i)
                
                if signal['action'] == 'buy':
                    self.open_position('buy', current_price, current_time, signal)
                elif signal['action'] == 'sell':
                    self.open_position('sell', current_price, current_time, signal)
        
        # 최종 결과 계산
        return self.calculate_results()
    
    def calculate_results(self) -> Dict:
        """백테스트 결과 계산"""
        if not self.trades:
            return {"error": "거래 기록이 없습니다."}
        
        total_pnl = self.current_balance - self.initial_balance
        total_return = (total_pnl / self.initial_balance) * 100
        
        win_rate = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        
        # 평균 수익/손실
        winning_trades = [t['pnl'] for t in self.trades if t['pnl'] > 0]
        losing_trades = [t['pnl'] for t in self.trades if t['pnl'] < 0]
        
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = np.mean(losing_trades) if losing_trades else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        
        # 최대 낙폭
        peak = self.initial_balance
        max_dd = 0
        running_balance = self.initial_balance
        
        for trade in self.trades:
            running_balance += trade['pnl']
            if running_balance > peak:
                peak = running_balance
            dd = (peak - running_balance) / peak * 100
            max_dd = max(max_dd, dd)
        
        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.current_balance,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "max_drawdown": max_dd,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "trades": self.trades
        }

# 사용 예시
if __name__ == "__main__":
    # 봇 생성
    bot = Simple1PercentBot(initial_balance=10000, leverage=1)
    
    # 테스트 기간 선택
    test_periods = {
        '1': {'name': '1개월', 'start': '2024-01-01', 'end': '2024-01-31'},
        '2': {'name': '3개월', 'start': '2024-01-01', 'end': '2024-03-31'},
        '3': {'name': '6개월', 'start': '2024-01-01', 'end': '2024-06-30'},
        '4': {'name': '1년', 'start': '2024-01-01', 'end': '2024-12-31'}
    }
    
    print("=== 테스트 기간 선택 ===")
    for key, period in test_periods.items():
        print(f"{key}. {period['name']} ({period['start']} ~ {period['end']})")
    
    # 기본값: 1개월 테스트
    selected_period = '1'
    print(f"\n선택된 기간: {test_periods[selected_period]['name']}")
    
    # 데이터 로드
    try:
        csv_path = os.path.join(os.path.dirname(__file__), 'data', 'BTCUSDT', '1m', 'BTCUSDT_1m_2024.csv')
        logger.info(f"CSV 파일 로드 중: {csv_path}")
        
        df = pd.read_csv(csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        df = df.sort_index()
        
        logger.info(f"데이터 기간: {df.index.min()} ~ {df.index.max()}")
        logger.info(f"데이터 개수: {len(df)}개")
        
        # 1분 데이터가 너무 클 경우 샘플링 (5분봉으로 변환)
        if len(df) > 100000:  # 10만개 이상이면 샘플링
            logger.info(f"데이터가 너무 큽니다 ({len(df)}개). 5분봉으로 샘플링합니다.")
            df = df.resample('5T').agg({
                'open': 'first',
                'high': 'max', 
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            logger.info(f"샘플링 후: {len(df)}개 행")
        
        # 선택된 기간으로 백테스트 실행
        selected = test_periods[selected_period]
        results = bot.run_backtest(df, start_date=selected['start'], end_date=selected['end'])
        
        print(f"\n=== {test_periods[selected_period]['name']} 백테스트 결과 ===")
        print(f"테스트 기간: {selected['start']} ~ {selected['end']}")
        
        if 'error' in results:
            print(f"백테스트 오류: {results['error']}")
        else:
            print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
            print(f"최종 자본: {results['final_balance']:,.0f} USDT")
            print(f"총 수익률: {results['total_return']:.2f}%")
            print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
            print(f"승률: {results['win_rate']:.2f}%")
            print(f"수익 팩터: {results['profit_factor']:.2f}")
            print(f"총 거래 횟수: {results['total_trades']}회")
            
            # 기간별 수익률 분석
            if results['total_trades'] > 0:
                # 테스트 기간에 따른 일수 계산
                start_date = pd.to_datetime(selected['start'])
                end_date = pd.to_datetime(selected['end'])
                days = (end_date - start_date).days + 1
                
                daily_return = results['total_return'] / days
                print(f"테스트 기간: {days}일")
                print(f"평균 일일 수익률: {daily_return:.3f}%")
                
                if daily_return >= 2.0:
                    print("목표 달성! 하루 2% 수익률 달성")
                else:
                    print(f"목표 미달성 (목표: 2%, 실제: {daily_return:.3f}%)")
        
    except Exception as e:
        logger.error(f"백테스트 실행 오류: {e}")
        print(f"백테스트 실행 오류: {e}")
        import traceback
        traceback.print_exc()
