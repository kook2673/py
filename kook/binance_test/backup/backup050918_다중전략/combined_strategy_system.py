#!/usr/bin/env python3
#-*-coding:utf-8 -*-

"""
8개 전략을 2개씩 조합한 4개 전략 시스템
=====================================

기존 8개 전략을 2개씩 합쳐서 4개의 강력한 조합 전략 생성:
1. 트렌드 조합: 모멘텀 + 이동평균
2. 스캘핑 조합: 스캘핑 + MACD  
3. 숏 모멘텀 조합: 숏 모멘텀 + 숏 스캘핑
4. 숏 트렌드 조합: 트렌드 숏 + 볼린저 밴드 숏

=== 사용법 ===
python combined_strategy_system.py --start 2023-01-01 --end 2023-12-31 --capital 100000
"""

import os
import sys
import pandas as pd
import numpy as np
import argparse
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Windows에서 이모지 출력을 위한 인코딩 설정
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

class CombinedStrategySystem:
    """8개 전략을 2개씩 조합한 4개 전략 시스템"""
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.trading_fee = 0.0006  # 0.06% 수수료
        self.leverage = 3.0  # 3배 레버리지
        
        # 4개 조합 전략별 자본 (동일 분배)
        self.strategy_capitals = {
            'trend_combo': initial_capital * 0.25,      # 모멘텀 + 이동평균
            'scalping_combo': initial_capital * 0.25,   # 스캘핑 + MACD
            'short_momentum_combo': initial_capital * 0.25,  # 숏 모멘텀 + 숏 스캘핑
            'short_trend_combo': initial_capital * 0.25  # 트렌드 숏 + 볼린저 밴드 숏
        }
        
        # 전략별 포지션
        self.strategy_positions = {
            'trend_combo': 0.0,
            'scalping_combo': 0.0,
            'short_momentum_combo': 0.0,
            'short_trend_combo': 0.0
        }
        
        # 전략별 거래 기록
        self.strategy_trades = {
            'trend_combo': [],
            'scalping_combo': [],
            'short_momentum_combo': [],
            'short_trend_combo': []
        }
        
        # 포트폴리오 기록
        self.portfolio_history = {
            'timestamps': [],
            'prices': [],
            'portfolio_values': []
        }
    
    # === 개별 전략 함수들 ===
    
    def momentum_strategy(self, data: pd.DataFrame, i: int) -> int:
        """모멘텀 전략 (롱 전용)"""
        if i < 20:
            return 0
            
        current_price = data['close'].iloc[i]
        past_price = data['close'].iloc[i-20]
        momentum = (current_price - past_price) / past_price
        
        if momentum > 0.02:
            return 1
        elif momentum < -0.02:
            return -1
        else:
            return 0
    
    def moving_average_strategy(self, data: pd.DataFrame, i: int) -> int:
        """이동평균 전략"""
        if i < 50:
            return 0
            
        ma_short = data['close'].rolling(window=20).mean()
        ma_long = data['close'].rolling(window=50).mean()
        
        if i < 1:
            return 0
            
        # 골든크로스/데드크로스 신호
        if (ma_short.iloc[i] > ma_long.iloc[i] and 
            ma_short.iloc[i-1] <= ma_long.iloc[i-1]):
            return 1
        elif (ma_short.iloc[i] < ma_long.iloc[i] and 
              ma_short.iloc[i-1] >= ma_long.iloc[i-1]):
            return -1
        else:
            return 0
    
    def scalping_strategy(self, data: pd.DataFrame, i: int) -> int:
        """스캘핑 전략 (단기 변동성 활용)"""
        if i < 5:
            return 0
            
        recent_data = data['close'].iloc[i-5:i+1]
        volatility = recent_data.pct_change().dropna().std()
        
        current_price = data['close'].iloc[i]
        past_price = data['close'].iloc[i-5]
        price_change = (current_price - past_price) / past_price
        
        if volatility > 0.01 and price_change > 0.005:
            return 1
        elif volatility > 0.01 and price_change < -0.005:
            return -1
        else:
            return 0
    
    def macd_strategy(self, data: pd.DataFrame, i: int) -> int:
        """MACD 전략"""
        if i < 50:
            return 0
            
        # MACD 계산
        ema_fast = data['close'].ewm(span=12).mean()
        ema_slow = data['close'].ewm(span=26).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=9).mean()
        histogram = macd_line - signal_line
        
        if i < 1:
            return 0
            
        # MACD 크로스오버 신호
        if (macd_line.iloc[i] > signal_line.iloc[i] and 
            macd_line.iloc[i-1] <= signal_line.iloc[i-1] and
            histogram.iloc[i] > 0):
            return 1
        elif (macd_line.iloc[i] < signal_line.iloc[i] and 
              macd_line.iloc[i-1] >= signal_line.iloc[i-1] and
              histogram.iloc[i] < 0):
            return -1
        else:
            return 0
    
    def short_momentum_strategy(self, data: pd.DataFrame, i: int) -> int:
        """숏 모멘텀 전략 (숏 전용)"""
        if i < 20:
            return 0
            
        current_price = data['close'].iloc[i]
        past_price = data['close'].iloc[i-20]
        momentum = (current_price - past_price) / past_price
        
        if momentum < -0.02:  # 하락 모멘텀일 때 숏
            return -1
        else:
            return 0
    
    def short_scalping_strategy(self, data: pd.DataFrame, i: int) -> int:
        """숏 스캘핑 전략 (숏 전용)"""
        if i < 5:
            return 0
            
        recent_data = data['close'].iloc[i-5:i+1]
        volatility = recent_data.pct_change().dropna().std()
        
        current_price = data['close'].iloc[i]
        past_price = data['close'].iloc[i-5]
        price_change = (current_price - past_price) / past_price
        
        if volatility > 0.01 and price_change < -0.005:  # 하락일 때만 숏
            return -1
        else:
            return 0
    
    def trend_short_strategy(self, data: pd.DataFrame, i: int) -> int:
        """트렌드 숏 전략"""
        if i < 50:
            return 0
            
        ma_short = data['close'].rolling(window=20).mean()
        ma_long = data['close'].rolling(window=50).mean()
        
        if i < 1:
            return 0
            
        # 하락 트렌드일 때 숏
        if (ma_short.iloc[i] < ma_long.iloc[i] and 
            ma_short.iloc[i-1] >= ma_long.iloc[i-1]):
            return -1
        else:
            return 0
    
    def bb_short_strategy(self, data: pd.DataFrame, i: int) -> int:
        """볼린저 밴드 숏 전략"""
        if i < 20:
            return 0
            
        # 볼린저 밴드 계산
        ma = data['close'].rolling(window=20).mean()
        std = data['close'].rolling(window=20).std()
        upper_band = ma + (std * 2)
        lower_band = ma - (std * 2)
        
        current_price = data['close'].iloc[i]
        
        # 상단 밴드 터치 시 숏
        if current_price >= upper_band.iloc[i]:
            return -1
        else:
            return 0
    
    # === 조합 전략 함수들 ===
    
    def trend_combo_strategy(self, data: pd.DataFrame, i: int) -> int:
        """트렌드 조합: 모멘텀 + 이동평균"""
        momentum_signal = self.momentum_strategy(data, i)
        ma_signal = self.moving_average_strategy(data, i)
        
        # 두 전략이 모두 같은 방향이면 신호, 아니면 0
        if momentum_signal == ma_signal and momentum_signal != 0:
            return momentum_signal
        else:
            return 0
    
    def scalping_combo_strategy(self, data: pd.DataFrame, i: int) -> int:
        """스캘핑 조합: 스캘핑 + MACD"""
        scalping_signal = self.scalping_strategy(data, i)
        macd_signal = self.macd_strategy(data, i)
        
        # 두 전략이 모두 같은 방향이면 신호, 아니면 0
        if scalping_signal == macd_signal and scalping_signal != 0:
            return scalping_signal
        else:
            return 0
    
    def short_momentum_combo_strategy(self, data: pd.DataFrame, i: int) -> int:
        """숏 모멘텀 조합: 숏 모멘텀 + 숏 스캘핑"""
        short_momentum_signal = self.short_momentum_strategy(data, i)
        short_scalping_signal = self.short_scalping_strategy(data, i)
        
        # 둘 중 하나라도 숏 신호가 있으면 숏
        if short_momentum_signal == -1 or short_scalping_signal == -1:
            return -1
        else:
            return 0
    
    def short_trend_combo_strategy(self, data: pd.DataFrame, i: int) -> int:
        """숏 트렌드 조합: 트렌드 숏 + 볼린저 밴드 숏"""
        trend_short_signal = self.trend_short_strategy(data, i)
        bb_short_signal = self.bb_short_strategy(data, i)
        
        # 둘 중 하나라도 숏 신호가 있으면 숏
        if trend_short_signal == -1 or bb_short_signal == -1:
            return -1
        else:
            return 0
    
    def run_backtest(self, data: pd.DataFrame, start_date: str, end_date: str):
        """백테스트 실행"""
        print(f"🚀 조합 전략 백테스트 시작!")
        print(f"📅 기간: {start_date} ~ {end_date}")
        print(f"💰 초기 자본: ${self.initial_capital:,.0f}")
        print("=" * 80)
        
        # 데이터 필터링
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        filtered_data = data[(data.index >= start_dt) & (data.index <= end_dt)]
        
        if len(filtered_data) == 0:
            print("❌ 필터링된 데이터가 없습니다.")
            return
        
        print(f"📊 백테스트 데이터: {len(filtered_data)}개 캔들")
        
        # 조합 전략별 실행
        strategies = {
            'trend_combo': self.trend_combo_strategy,
            'scalping_combo': self.scalping_combo_strategy,
            'short_momentum_combo': self.short_momentum_combo_strategy,
            'short_trend_combo': self.short_trend_combo_strategy
        }
        
        for strategy_name, strategy_func in strategies.items():
            print(f"\n🔍 {strategy_name.upper()} 전략 실행 중...")
            
            # 전략별 백테스트
            self._run_single_strategy(filtered_data, strategy_name, strategy_func)
        
        # 전체 포트폴리오 결과 계산
        self._calculate_portfolio_results()
    
    def _run_single_strategy(self, data: pd.DataFrame, strategy_name: str, strategy_func):
        """개별 전략 백테스트"""
        cash = self.strategy_capitals[strategy_name]
        position = 0.0
        trades = []
        
        for i in range(len(data)):
            current_price = data['close'].iloc[i]
            current_time = data.index[i]
            
            # 신호 생성
            signal = strategy_func(data, i)
            
            if signal != 0:
                if signal == 1 and position == 0:  # 매수
                    gross_value = cash
                    fee = gross_value * self.trading_fee
                    net_value = gross_value - fee
                    shares = net_value / current_price
                    
                    position = shares
                    cash = 0
                    
                    trades.append({
                        'timestamp': current_time,
                        'action': 'BUY',
                        'price': current_price,
                        'shares': shares,
                        'fee': fee
                    })
                    
                elif signal == -1 and position > 0:  # 매도
                    gross_value = position * current_price
                    fee = gross_value * self.trading_fee
                    net_value = gross_value - fee
                    
                    cash = net_value
                    position = 0
                    
                    trades.append({
                        'timestamp': current_time,
                        'action': 'SELL',
                        'price': current_price,
                        'shares': position,
                        'fee': fee
                    })
            
            # 포트폴리오 가치 기록
            portfolio_value = cash + (position * current_price)
            self.portfolio_history['timestamps'].append(current_time)
            self.portfolio_history['prices'].append(current_price)
            self.portfolio_history['portfolio_values'].append(portfolio_value)
        
        # 전략별 결과 저장
        self.strategy_trades[strategy_name] = trades
        self.strategy_positions[strategy_name] = position
        
        # 결과 출력
        if trades:
            final_value = cash + (position * data['close'].iloc[-1])
            total_return = (final_value - self.strategy_capitals[strategy_name]) / self.strategy_capitals[strategy_name] * 100
            
            print(f"   💰 최종 자본: ${final_value:,.2f}")
            print(f"   📈 수익률: {total_return:+.2f}%")
            print(f"   📊 거래수: {len(trades)}회")
        else:
            print(f"   ❌ 거래 없음")
    
    def _calculate_portfolio_results(self):
        """전체 포트폴리오 결과 계산"""
        print(f"\n🏆 전체 포트폴리오 결과")
        print("=" * 80)
        
        total_final_value = 0
        total_trades = 0
        
        for strategy_name in self.strategy_capitals.keys():
            trades = self.strategy_trades[strategy_name]
            if trades:
                # 마지막 거래에서 포지션 정리
                final_trade = trades[-1]
                if final_trade['action'] == 'BUY':
                    # 포지션을 정리하지 않았으므로 현재 가격으로 계산
                    current_price = self.portfolio_history['prices'][-1]
                    final_value = self.strategy_positions[strategy_name] * current_price
                else:
                    final_value = self.strategy_capitals[strategy_name]
            else:
                final_value = self.strategy_capitals[strategy_name]
            
            total_final_value += final_value
            total_trades += len(trades)
            
            print(f"📊 {strategy_name}: ${final_value:,.2f} ({len(trades)}회 거래)")
        
        total_return = (total_final_value - self.initial_capital) / self.initial_capital * 100
        
        print(f"\n💰 총 자본: ${total_final_value:,.2f}")
        print(f"📈 총 수익률: {total_return:+.2f}%")
        print(f"📊 총 거래수: {total_trades}회")

def load_data(symbol: str = 'BTCUSDT', start_year: int = 2023, end_year: int = 2023) -> pd.DataFrame:
    """데이터 로드"""
    print(f"📊 {symbol} {start_year}년 데이터 로드 중...")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    all_data = []
    
    for year in range(start_year, end_year + 1):
        data_path = os.path.join(script_dir, "data", symbol, "1h", f"{symbol}_1h_{year}.csv")
        
        if os.path.exists(data_path):
            try:
                year_data = pd.read_csv(data_path)
                year_data['timestamp'] = pd.to_datetime(year_data['timestamp'])
                year_data.set_index('timestamp', inplace=True)
                all_data.append(year_data)
                print(f"   ✅ {year}년 데이터 로드: {len(year_data)}개 캔들")
            except Exception as e:
                print(f"   ❌ {year}년 데이터 로드 실패: {e}")
        else:
            print(f"   ⚠️ {year}년 데이터 파일 없음: {data_path}")
    
    if not all_data:
        print(f"❌ 로드된 데이터가 없습니다.")
        return None
    
    # 모든 데이터 합치기
    combined_data = pd.concat(all_data, ignore_index=False)
    combined_data = combined_data.sort_index()
    
    print(f"✅ 전체 데이터 로드 성공: {len(combined_data)}개 캔들")
    print(f"📅 기간: {combined_data.index[0].strftime('%Y-%m-%d')} ~ {combined_data.index[-1].strftime('%Y-%m-%d')}")
    print(f"💰 가격 범위: ${combined_data['close'].min():.2f} ~ ${combined_data['close'].max():.2f}")
    
    return combined_data

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='8개 전략을 2개씩 조합한 4개 전략 시스템')
    parser.add_argument('--symbol', default='BTCUSDT', help='거래 심볼 (기본값: BTCUSDT)')
    parser.add_argument('--start', default='2022-01-01', help='시작 날짜 (기본값: 2023-01-01)')
    parser.add_argument('--end', default='2022-12-31', help='종료 날짜 (기본값: 2023-12-31)')
    parser.add_argument('--capital', type=float, default=100000, help='초기 자본 (기본값: 100000)')
    
    args = parser.parse_args()
    
    # 데이터 로드
    data = load_data(args.symbol, int(args.start[:4]), int(args.end[:4]))
    if data is None:
        return
    
    # 전략 시스템 생성 및 실행
    strategy_system = CombinedStrategySystem(args.capital)
    strategy_system.run_backtest(data, args.start, args.end)

if __name__ == "__main__":
    main()

