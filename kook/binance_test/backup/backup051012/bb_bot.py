#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BB(볼린저 밴드) 롱숏 전략 봇
- 규칙1 : 미래데이터를 사용하지 않는다.
- 규칙2 : 랜덤데이터를 사용하지 않고 과거 csv파일을 로드해서 사용한다.
- 규칙3 : 살때 0.05%수수료, 팔때 0.05%수수료를 꼭 적용해야 한다.
- 규칙4 : 트레일링 스탑 포함을 한다.
- 규칙5 : 백테스트 다 돌리고 비트코인가격 그래프와 수익률 그래프를 보여준다.

- 규칙6 : 이겼을때 self.position_size = 0.1배, 졌을때 self.position_size = 0.2배로 한다.

볼린저 밴드 평균 회귀 전략:
- 하단 밴드 하향 돌파 후 다시 안으로 들어올 때 매수
- 상단 밴드 상향 돌파 후 다시 안으로 들어올 때 매도
"""

import sys
import os
import pandas as pd
import numpy as np
import datetime as dt
from typing import Dict, List, Tuple, Optional
import logging
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BBLongShortBot:
    def __init__(self, initial_balance: float = 10000, leverage: int = 1):
        """
        BB 롱숏 전략 봇
        
        Args:
            initial_balance: 초기 자본금 (USDT)
            leverage: 레버리지 (1배로 제한)
        """
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.leverage = leverage
        
        # 거래 파라미터
        self.target_profit_rate = 0.004   # 0.4% 수익 목표 (수수료 고려)
        self.max_daily_loss = 0.003       # 0.3% 최대 손실
        self.trailing_stop_activation = 0.003  # 0.3% 수익 달성시 트레일링 스탑 활성화
        self.position_size_win = 0.1      # 이겼을때 포지션 사이즈
        self.position_size_loss = 0.2     # 졌을때 포지션 사이즈
        self.position_size = self.position_size_win  # 현재 포지션 사이즈
        self.commission_rate = 0.0005     # 0.05% 수수료 (매수/매도 각각)
        self.atr_stop_multiplier = 2.0    # ATR 기반 손절을 위한 승수
        self.trailing_stop_pct = 0.005    # 최고가/최저가에서 0.5% 되돌릴 시 청산
        
        # 볼린저 밴드 파라미터
        self.bb_period = 20
        self.bb_std = 2
        
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
        """기술적 지표 계산 (볼린저 밴드 중심)"""
        df = df.copy()
        
        # 볼린저밴드 (직접 구현)
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = self._calculate_bollinger_bands(
            df['close'], timeperiod=self.bb_period, nbdevup=self.bb_std, nbdevdn=self.bb_std
        )
        
        # ATR (변동성 기반 손절) - 직접 구현
        df['atr'] = self._calculate_atr(df['high'], df['low'], df['close'], timeperiod=14)
        
        # 이동평균선 (추가 확인용) - 직접 구현
        df['ma_20'] = df['close'].rolling(window=20).mean()
        
        # 거래량 필터용 지표
        df['volume_ma_20'] = df['volume'].rolling(window=20).mean()  # 20주기 평균 거래량
        df['volume_ratio'] = df['volume'] / df['volume_ma_20']  # 현재 거래량 / 평균 거래량 비율
        
        return df
    
    def _calculate_bollinger_bands(self, prices: pd.Series, timeperiod: int = 20, nbdevup: float = 2, nbdevdn: float = 2):
        """볼린저 밴드 계산"""
        # 중간선 (이동평균)
        middle = prices.rolling(window=timeperiod).mean()
        
        # 표준편차
        std = prices.rolling(window=timeperiod).std()
        
        # 상단/하단 밴드
        upper = middle + (std * nbdevup)
        lower = middle - (std * nbdevdn)
        
        return upper, middle, lower
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, timeperiod: int = 14):
        """ATR (Average True Range) 계산"""
        # True Range 계산
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR 계산 (지수이동평균)
        atr = true_range.ewm(span=timeperiod).mean()
        
        return atr
    
    def generate_signal(self, df: pd.DataFrame, current_idx: int) -> Dict:
        """BB 롱숏 신호 생성"""
        if current_idx < 20:  # 거래량 MA 계산을 위한 충분한 데이터 확보
            return {'action': 'hold', 'confidence': 0}
        
        current_data = df.iloc[:current_idx+1]
        current_price = current_data['close'].iloc[-1]
        current_atr = current_data['atr'].iloc[-1]
        
        # BB 신호 생성
        bb_signal = self._bollinger_bands_signal(current_data)
        
        if bb_signal['action'] != 'hold':
            return {
                'action': bb_signal['action'],
                'confidence': bb_signal['confidence'],
                'target_price': current_price * (1 + self.target_profit_rate) if bb_signal['action'] == 'buy' else current_price * (1 - self.target_profit_rate),
                'stop_loss': current_price - (current_atr * self.atr_stop_multiplier) if bb_signal['action'] == 'buy' else current_price + (current_atr * self.atr_stop_multiplier)
            }
        
        return {'action': 'hold', 'confidence': 0}
    
    def _bollinger_bands_signal(self, df: pd.DataFrame) -> Dict:
        """볼린저밴드 신호 (단순 터치 + 거래량 필터)"""
        if len(df) < 20 or 'bb_upper' not in df.columns or df['bb_upper'].isnull().all():
            return {'action': 'hold', 'confidence': 0}
        
        current_price = df['close'].iloc[-1]
        volume_ratio = df['volume_ratio'].iloc[-1]
        
        # 거래량이 평균의 1.2배 이상일 때만 거래 (활발한 거래량)
        if volume_ratio < 1.2:
            return {'action': 'hold', 'confidence': 0}
        
        # 하단 밴드 터치 시 매수 (거래량 필터 적용)
        if current_price <= df['bb_lower'].iloc[-1]:
            return {'action': 'buy', 'confidence': 0.8}
        
        # 상단 밴드 터치 시 매도 (거래량 필터 적용)
        elif current_price >= df['bb_upper'].iloc[-1]:
            return {'action': 'sell', 'confidence': 0.8}
        
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
            # 이겼을때 포지션 사이즈를 작게 (0.1배)
            self.position_size = self.position_size_win
            logger.info(f"승리! 포지션 사이즈를 {self.position_size:.1%}로 조정")
        else:
            self.losing_trades += 1
            # 졌을때 포지션 사이즈를 크게 (0.2배)
            self.position_size = self.position_size_loss
            logger.info(f"패배! 포지션 사이즈를 {self.position_size:.1%}로 조정")
        
        logger.info(f"포지션 청산: {position['side']} {position['amount']:.4f} @ {price:.2f}, PnL: {pnl:.2f} USDT, 순손익: {net_pnl:.2f} USDT (수수료: {total_commission:.2f} USDT), 이유: {reason}")
    
    def check_exit_conditions(self, position: Dict, current_price: float) -> Optional[str]:
        """청산 조건 체크 (트레일링 스탑 포함)"""
        if position['side'] == 'buy':
            # 최고가 업데이트
            if current_price > position['highest_price']:
                position['highest_price'] = current_price
                
                # 트레일링 스탑 활성화 체크
                profit_pct = (current_price - position['price']) / position['price']
                if profit_pct >= self.trailing_stop_activation and not position['trailing_stop_activated']:
                    position['trailing_stop_activated'] = True
                    logger.info(f"트레일링 스탑 활성화: {profit_pct:.2%} 수익 달성")
            
            # 트레일링 스탑이 활성화된 경우
            if position['trailing_stop_activated']:
                trailing_stop_price = position['highest_price'] * (1 - self.trailing_stop_pct)
                if current_price <= trailing_stop_price:
                    return 'trailing_stop'
            
            # 익절
            if current_price >= position['target_price']:
                return 'take_profit'
            # 손절
            elif current_price <= position['stop_loss']:
                return 'stop_loss'
        else: # 'sell' side
            # 최저가 업데이트
            if current_price < position['lowest_price']:
                position['lowest_price'] = current_price
                
                # 트레일링 스탑 활성화 체크
                profit_pct = (position['price'] - current_price) / position['price']
                if profit_pct >= self.trailing_stop_activation and not position['trailing_stop_activated']:
                    position['trailing_stop_activated'] = True
                    logger.info(f"트레일링 스탑 활성화: {profit_pct:.2%} 수익 달성")
            
            # 트레일링 스탑이 활성화된 경우
            if position['trailing_stop_activated']:
                trailing_stop_price = position['lowest_price'] * (1 + self.trailing_stop_pct)
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
        logger.info("BB 롱숏 백테스트 시작...")
        
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
        for i in range(20, len(df)):  # 거래량 MA 계산을 위해 20부터 시작
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
    
    def plot_results(self, df: pd.DataFrame, results: Dict):
        """백테스트 결과 그래프 표시"""
        # 한글 폰트 설정
        plt.rcParams['font.family'] = 'DejaVu Sans'
        plt.rcParams['axes.unicode_minus'] = False
        
        # 볼린저 밴드 재계산 (원본 데이터에 없을 수 있음)
        df_plot = df.copy()
        df_plot['bb_upper'], df_plot['bb_middle'], df_plot['bb_lower'] = self._calculate_bollinger_bands(
            df_plot['close'], timeperiod=self.bb_period, nbdevup=self.bb_std, nbdevdn=self.bb_std
        )
        
        # 그래프 생성
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))
        
        # 1. 비트코인 가격과 볼린저 밴드 그래프
        ax1.plot(df_plot.index, df_plot['close'], label='BTC Price', linewidth=1, alpha=0.8)
        ax1.plot(df_plot.index, df_plot['bb_upper'], label='BB Upper', color='red', alpha=0.7, linestyle='--')
        ax1.plot(df_plot.index, df_plot['bb_middle'], label='BB Middle', color='blue', alpha=0.7)
        ax1.plot(df_plot.index, df_plot['bb_lower'], label='BB Lower', color='red', alpha=0.7, linestyle='--')
        
        # 거래 포인트 표시
        for trade in results['trades']:
            if trade['side'] == 'buy':
                ax1.scatter(trade['timestamp'], trade['entry_price'], color='green', marker='^', s=50, alpha=0.7)
                ax1.scatter(trade['timestamp'], trade['exit_price'], color='lightgreen', marker='v', s=30, alpha=0.7)
            else:
                ax1.scatter(trade['timestamp'], trade['entry_price'], color='red', marker='v', s=50, alpha=0.7)
                ax1.scatter(trade['timestamp'], trade['exit_price'], color='lightcoral', marker='^', s=30, alpha=0.7)
        
        ax1.set_title('BB 롱숏 전략 - 비트코인 가격과 볼린저 밴드', fontsize=14, fontweight='bold')
        ax1.set_ylabel('가격 (USDT)', fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. 누적 수익률 그래프
        if results['trades']:
            # 거래별 누적 수익률 계산
            cumulative_pnl = []
            cumulative_return = []
            running_balance = self.initial_balance
            
            for trade in results['trades']:
                running_balance += trade['net_pnl']
                cumulative_pnl.append(running_balance - self.initial_balance)
                cumulative_return.append((running_balance - self.initial_balance) / self.initial_balance * 100)
            
            trade_times = [trade['timestamp'] for trade in results['trades']]
            
            ax2.plot(trade_times, cumulative_return, label='누적 수익률 (%)', linewidth=2, color='blue')
            ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
            ax2.fill_between(trade_times, cumulative_return, 0, 
                           where=[x >= 0 for x in cumulative_return], 
                           color='green', alpha=0.3, label='수익 구간')
            ax2.fill_between(trade_times, cumulative_return, 0, 
                           where=[x < 0 for x in cumulative_return], 
                           color='red', alpha=0.3, label='손실 구간')
        
        ax2.set_title('BB 롱숏 전략 - 누적 수익률', fontsize=14, fontweight='bold')
        ax2.set_xlabel('시간', fontsize=12)
        ax2.set_ylabel('수익률 (%)', fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # x축 날짜 포맷
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        plt.show()
        
        # 결과 요약 출력
        print(f"\n=== BB 롱숏 전략 결과 요약 ===")
        print(f"총 거래 횟수: {results['total_trades']}회")
        print(f"승률: {results['win_rate']:.2f}%")
        print(f"총 수익률: {results['total_return']:.2f}%")
        print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
        print(f"수익 팩터: {results['profit_factor']:.2f}")
        print(f"평균 수익: {results['avg_win']:.2f} USDT")
        print(f"평균 손실: {results['avg_loss']:.2f} USDT")

# 사용 예시
if __name__ == "__main__":
    # 봇 생성
    bot = BBLongShortBot(initial_balance=10000, leverage=1)
    
    # 테스트 기간 선택
    test_periods = {
        '1': {'name': '1개월', 'start': '2024-01-01', 'end': '2024-01-31'},
        '2': {'name': '3개월', 'start': '2024-01-01', 'end': '2024-03-31'},
        '3': {'name': '6개월', 'start': '2024-01-01', 'end': '2024-06-30'},
        '4': {'name': '1년', 'start': '2024-01-01', 'end': '2024-12-31'}
    }
    
    print("=== BB 롱숏 전략 테스트 기간 선택 ===")
    for key, period in test_periods.items():
        print(f"{key}. {period['name']} ({period['start']} ~ {period['end']})")
    
    # 기본값: 1개월 테스트
    selected_period = '1'
    print(f"\n선택된 기간: {test_periods[selected_period]['name']}")
    
    # 데이터 로드 (5분봉 직접 사용)
    try:
        csv_path = os.path.join(os.path.dirname(__file__), 'data', 'BTCUSDT', '5m', 'BTCUSDT_5m_2024.csv')
        logger.info(f"CSV 파일 로드 중: {csv_path}")
        
        df = pd.read_csv(csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        df = df.sort_index()
        
        logger.info(f"데이터 기간: {df.index.min()} ~ {df.index.max()}")
        logger.info(f"데이터 개수: {len(df)}개 (5분봉)")
        
        # 선택된 기간으로 백테스트 실행
        selected = test_periods[selected_period]
        results = bot.run_backtest(df, start_date=selected['start'], end_date=selected['end'])
        
        print(f"\n=== BB 롱숏 전략 {test_periods[selected_period]['name']} 백테스트 결과 ===")
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
                
                # 그래프 표시
                print("\n그래프를 생성 중...")
                bot.plot_results(df, results)
        
    except Exception as e:
        logger.error(f"백테스트 실행 오류: {e}")
        print(f"백테스트 실행 오류: {e}")
        import traceback
        traceback.print_exc()
