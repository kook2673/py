#!/usr/bin/env python3
#-*-coding:utf-8 -*-

"""
상위 4개 전략 포트폴리오 시스템
==============================

성과가 좋은 4개 전략만 선별하여 자산을 4등분해서 운용:
1. 모멘텀 전략 (수익률 51.72%, 승률 33.4%)
2. 스캘핑 전략 (수익률 68.78%, 승률 48.1%) 
3. MACD 전략 (수익률 24.98%, 승률 47.3%)
4. 이동평균 전략 (수익률 41.33%, 승률 48.9%)

=== 사용법 ===
python top4_strategy_system.py --start 2023-01-01 --end 2023-12-31 --capital 100000
"""

import os
import sys
import pandas as pd
import numpy as np
import argparse
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns

# Windows에서 이모지 출력을 위한 인코딩 설정
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

class Top4StrategySystem:
    """상위 4개 전략 포트폴리오 시스템"""
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.base_capital_per_strategy = initial_capital / 4  # 기본 4등분
        self.trading_fee = 0.0006  # 0.06% 수수료
        self.leverage = 5.0  # 1배 레버리지 (레버리지 없음)
        
        # 전략별 자본 (고정 4등분)
        self.strategy_capitals = {
            'momentum': self.base_capital_per_strategy,
            'scalping': self.base_capital_per_strategy, 
            'macd': self.base_capital_per_strategy,
            'moving_average': self.base_capital_per_strategy
        }
        
        # 전략별 포지션
        self.strategy_positions = {
            'momentum': 0.0,
            'scalping': 0.0,
            'macd': 0.0,
            'moving_average': 0.0
        }
        
        # 전략별 거래 기록
        self.strategy_trades = {
            'momentum': [],
            'scalping': [],
            'macd': [],
            'moving_average': []
        }
        
        # 포트폴리오 기록 (메모리 최적화를 위해 딕셔너리로 변경)
        self.portfolio_history = {
            'timestamps': [],
            'prices': [],
            'portfolio_values': []
        }
        
    def momentum_strategy(self, data: pd.DataFrame, i: int) -> int:
        """모멘텀 전략"""
        if i < 20:
            return 0
            
        # 20일 모멘텀 계산
        current_price = data['close'].iloc[i]
        past_price = data['close'].iloc[i-20]
        momentum = (current_price - past_price) / past_price
        
        # 모멘텀 > 0.02이면 매수, < -0.02이면 매도
        if momentum > 0.02:
            return 1  # 매수
        elif momentum < -0.02:
            return -1  # 매도
        else:
            return 0  # 보유
    
    def scalping_strategy(self, data: pd.DataFrame, i: int) -> int:
        """스캘핑 전략 (단기 변동성 활용)"""
        if i < 5:
            return 0
            
        # 5시간 변동성 계산
        recent_data = data['close'].iloc[i-5:i+1]
        volatility = recent_data.pct_change().std()
        
        # 현재 가격과 5시간 전 가격 비교
        current_price = data['close'].iloc[i]
        past_price = data['close'].iloc[i-5]
        price_change = (current_price - past_price) / past_price
        
        # 변동성이 높고 상승하면 매수, 하락하면 매도
        # 조건을 완화하여 더 많은 거래 기회 제공
        if volatility > 0.005 and price_change > 0.003:  # 조건 완화
            return 1  # 매수
        elif volatility > 0.005 and price_change < -0.003:  # 조건 완화
            return -1  # 매도
        else:
            return 0  # 보유
    
    def macd_strategy(self, data: pd.DataFrame, i: int) -> int:
        """MACD 전략"""
        if i < 26:
            return 0
            
        # MACD 계산
        ema12 = data['close'].ewm(span=12).mean()
        ema26 = data['close'].ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        
        current_macd = macd_line.iloc[i]
        current_signal = signal_line.iloc[i]
        prev_macd = macd_line.iloc[i-1]
        prev_signal = signal_line.iloc[i-1]
        
        # MACD가 시그널을 상향돌파하면 매수
        if current_macd > current_signal and prev_macd <= prev_signal:
            return 1  # 매수
        # MACD가 시그널을 하향돌파하면 매도
        elif current_macd < current_signal and prev_macd >= prev_signal:
            return -1  # 매도
        else:
            return 0  # 보유
    
    def moving_average_strategy(self, data: pd.DataFrame, i: int) -> int:
        """이동평균 전략"""
        if i < 50:
            return 0
            
        # 단기(20)와 장기(50) 이동평균
        ma20 = data['close'].rolling(window=20).mean()
        ma50 = data['close'].rolling(window=50).mean()
        
        current_ma20 = ma20.iloc[i]
        current_ma50 = ma50.iloc[i]
        prev_ma20 = ma20.iloc[i-1]
        prev_ma50 = ma50.iloc[i-1]
        
        # 단기 이평이 장기 이평을 상향돌파하면 매수
        if current_ma20 > current_ma50 and prev_ma20 <= prev_ma50:
            return 1  # 매수
        # 단기 이평이 장기 이평을 하향돌파하면 매도
        elif current_ma20 < current_ma50 and prev_ma20 >= prev_ma50:
            return -1  # 매도
        else:
            return 0  # 보유
    

    def execute_trade(self, strategy_name: str, signal: int, price: float, timestamp: pd.Timestamp):
        """거래 실행 (5배 레버리지 + 수수료 적용)"""
        current_position = self.strategy_positions[strategy_name]
        current_capital = self.strategy_capitals[strategy_name]
        
        if signal == 1 and current_position == 0:  # 매수
            # 레버리지를 적용한 거래 금액 계산
            leveraged_value = current_capital * self.leverage
            fee = leveraged_value * self.trading_fee
            net_value = leveraged_value - fee
            shares = net_value / price
            
            self.strategy_positions[strategy_name] = shares
            self.strategy_capitals[strategy_name] = 0  # 모든 자본을 사용
            
            self.strategy_trades[strategy_name].append({
                'timestamp': timestamp,
                'action': 'BUY',
                'price': price,
                'shares': shares,
                'leverage': self.leverage,
                'leveraged_value': leveraged_value,
                'fee': fee,
                'net_value': net_value
            })
            
        elif signal == -1 and current_position > 0:  # 매도
            # 매도 금액 계산
            gross_value = current_position * price
            fee = gross_value * self.trading_fee
            net_value = gross_value - fee
            
            # 레버리지 수익/손실 계산
            if self.strategy_trades[strategy_name]:
                last_buy = [t for t in self.strategy_trades[strategy_name] if t['action'] == 'BUY'][-1]
                buy_cost = last_buy['leveraged_value']  # 레버리지 적용된 매수 비용
                pnl = (net_value - buy_cost)  # 레버리지 수익/손실
                
                # 실제 자본 변화 = 레버리지 수익/손실을 원래 자본에 반영
                original_capital = buy_cost / self.leverage  # 원래 투자 자본
                capital_change = pnl  # 레버리지 수익/손실
                new_capital = original_capital + capital_change
            else:
                new_capital = current_capital
            
            # 자본이 마이너스가 되지 않도록 보호
            new_capital = max(0, new_capital)
            self.strategy_capitals[strategy_name] = new_capital
            self.strategy_positions[strategy_name] = 0
            
            
            self.strategy_trades[strategy_name].append({
                'timestamp': timestamp,
                'action': 'SELL',
                'price': price,
                'shares': current_position,
                'leverage': self.leverage,
                'gross_value': gross_value,
                'fee': fee,
                'net_value': net_value,
                'capital_change': capital_change if self.strategy_trades[strategy_name] else 0
            })
    
    def calculate_portfolio_value(self, current_price: float) -> float:
        """현재 포트폴리오 가치 계산"""
        total_value = 0
        
        for strategy_name in self.strategy_capitals:
            # 현금 자본
            cash_value = self.strategy_capitals[strategy_name]
            # 주식 가치
            stock_value = self.strategy_positions[strategy_name] * current_price
            total_value += cash_value + stock_value
            
        return total_value
    
    def run_backtest(self, data: pd.DataFrame, start_date: str = None, end_date: str = None):
        """백테스트 실행"""
        print("🚀 상위 4개 전략 포트폴리오 백테스트 시작!")
        print("=" * 60)
        print(f"💰 초기 자본: ${self.initial_capital:,.2f}")
        print(f"📊 전략별 자본: ${self.base_capital_per_strategy:,.2f}")
        print(f"⚡ 레버리지: {self.leverage}배")
        print(f"💸 수수료: {self.trading_fee*100:.2f}%")
        print(f"📅 기간: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
        print("=" * 60)
        
        # 날짜 필터링
        if start_date:
            data = data[data.index >= start_date]
        if end_date:
            data = data[data.index <= end_date]
        
        print(f"📊 백테스트 데이터: {len(data)}개 캔들")
        
        # 진행률 표시 간격 계산 (데이터 크기에 따라 조정)
        progress_interval = max(100, len(data) // 100)  # 최소 100개, 최대 100번 표시
        
        try:
            # 각 시점에서 전략 실행
            for i in range(len(data)):
                current_price = data['close'].iloc[i]
                current_time = data.index[i]
                
                # 각 전략별로 신호 생성 및 거래 실행
                strategies = {
                    'momentum': self.momentum_strategy,
                    'scalping': self.scalping_strategy,
                    'macd': self.macd_strategy,
                    'moving_average': self.moving_average_strategy
                }
                
                for strategy_name, strategy_func in strategies.items():
                    signal = strategy_func(data, i)
                    if signal != 0:
                        self.execute_trade(strategy_name, signal, current_price, current_time)
                
                # 포트폴리오 가치 기록 (메모리 최적화를 위해 샘플링)
                portfolio_value = self.calculate_portfolio_value(current_price)
                if i % 10 == 0 or i == len(data) - 1:  # 10개마다 또는 마지막에만 기록
                    self.portfolio_history['timestamps'].append(current_time)
                    self.portfolio_history['prices'].append(current_price)
                    self.portfolio_history['portfolio_values'].append(portfolio_value)
                
                # 진행률 표시
                if i % progress_interval == 0 or i == len(data) - 1:
                    progress = (i + 1) / len(data) * 100
                    print(f"\r🔄 진행률: {progress:.1f}% ({i+1}/{len(data)}) - 포트폴리오: ${portfolio_value:,.2f}", end='', flush=True)
            
            print("\n✅ 백테스트 완료!")
            return self.analyze_results()
            
        except KeyboardInterrupt:
            print("\n⚠️ 사용자에 의해 백테스트가 중단되었습니다.")
            print(f"📊 현재까지 처리된 데이터: {i+1}/{len(data)}개 캔들")
            if self.portfolio_history:
                print("📈 부분 결과를 분석합니다...")
                return self.analyze_results()
            else:
                print("❌ 분석할 데이터가 없습니다.")
                return None
    
    def analyze_results(self):
        """결과 분석"""
        if not self.portfolio_history['timestamps']:
            return None
        
        # 딕셔너리에서 DataFrame 생성
        df = pd.DataFrame({
            'timestamp': self.portfolio_history['timestamps'],
            'price': self.portfolio_history['prices'],
            'portfolio_value': self.portfolio_history['portfolio_values']
        })
        df.set_index('timestamp', inplace=True)
        
        # 기본 통계
        initial_value = self.initial_capital
        final_value = df['portfolio_value'].iloc[-1]
        total_return = (final_value - initial_value) / initial_value * 100
        
        # 최대 낙폭 계산
        df['cummax'] = df['portfolio_value'].cummax()
        df['drawdown'] = (df['portfolio_value'] - df['cummax']) / df['cummax']
        max_drawdown = df['drawdown'].min() * 100
        
        # 샤프 비율 계산
        returns = df['portfolio_value'].pct_change().dropna()
        sharpe_ratio = returns.mean() / returns.std() * np.sqrt(8760) if returns.std() > 0 else 0
        
        # 전략별 성과 분석
        strategy_performance = {}
        for strategy_name in self.strategy_trades:
            trades = self.strategy_trades[strategy_name]
            if trades:
                # 거래 수익률 계산
                total_trades = len(trades)
                winning_trades = 0
                total_pnl = 0
                
                for i in range(0, len(trades), 2):
                    if i + 1 < len(trades):
                        buy_trade = trades[i]
                        sell_trade = trades[i + 1]
                        if buy_trade['action'] == 'BUY' and sell_trade['action'] == 'SELL':
                            # 레버리지를 고려한 실제 수익률 계산
                            buy_cost = buy_trade['leveraged_value']  # 레버리지 적용된 매수 비용
                            sell_revenue = sell_trade['net_value']  # 매도 시 순 수익 (수수료 제외)
                            leveraged_pnl = (sell_revenue - buy_cost) / buy_cost  # 레버리지 수익률
                            actual_pnl = leveraged_pnl / self.leverage  # 실제 자본 대비 수익률
                            total_pnl += actual_pnl
                            if actual_pnl > 0:
                                winning_trades += 1
                
                win_rate = (winning_trades / (total_trades // 2)) * 100 if total_trades > 0 else 0
                avg_return = (total_pnl / (total_trades // 2)) * 100 if total_trades > 0 else 0
                
                strategy_performance[strategy_name] = {
                    'total_trades': total_trades // 2,
                    'winning_trades': winning_trades,
                    'win_rate': win_rate,
                    'avg_return': avg_return,
                    'total_signals': total_trades  # 전체 신호 수 (매수+매도)
                }
        
        # 결과 출력
        print("\n📊 포트폴리오 성과 분석")
        print("=" * 60)
        print(f"💰 초기 자본: ${initial_value:,.2f}")
        print(f"💰 최종 자본: ${final_value:,.2f}")
        print(f"📈 총 수익률: {total_return:.2f}%")
        print(f"📉 최대 낙폭: {max_drawdown:.2f}%")
        print(f"📊 샤프 비율: {sharpe_ratio:.2f}")
        
        print("\n🎯 전략별 성과 (수수료 0.06% 적용)")
        print("-" * 60)
        for strategy_name, perf in strategy_performance.items():
            print(f"{strategy_name:15} : 거래 {perf['total_trades']:3d}회, "
                  f"신호 {perf['total_signals']:3d}회, "
                  f"승률 {perf['win_rate']:5.1f}%, "
                  f"평균수익 {perf['avg_return']:6.2f}%")
        
        return {
            'initial_capital': initial_value,
            'final_capital': final_value,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'strategy_performance': strategy_performance,
            'portfolio_history': df
        }

def load_data(symbol: str = 'BTCUSDT', year: int = 2023) -> pd.DataFrame:
    """데이터 로드"""
    print(f"📊 {symbol} {year}년 데이터 로드 중...")
    
    # 스크립트 위치 기준으로 상대 경로 설정
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, "data", symbol, "5m", f"{symbol}_5m_{year}.csv")
    
    if not os.path.exists(data_path):
        print(f"❌ 데이터 파일을 찾을 수 없습니다: {data_path}")
        return None
    
    try:
        data = pd.read_csv(data_path)
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        data.set_index('timestamp', inplace=True)
        
        print(f"✅ 데이터 로드 성공: {len(data)}개 캔들")
        print(f"📅 기간: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
        print(f"💰 가격 범위: ${data['close'].min():.2f} ~ ${data['close'].max():.2f}")
        
        return data
        
    except Exception as e:
        print(f"❌ 데이터 로드 실패: {e}")
        return None

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='상위 4개 전략 포트폴리오 백테스트')
    parser.add_argument('--symbol', default='BTCUSDT', help='거래 심볼 (기본값: BTCUSDT)')
    parser.add_argument('--year', type=int, default=2023, help='백테스트 연도 (기본값: 2023)')
    parser.add_argument('--capital', type=float, default=100000, help='초기 자본 (기본값: 100000)')
    parser.add_argument('--start', help='시작 날짜 (YYYY-MM-DD)')
    parser.add_argument('--end', help='종료 날짜 (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # 시작 날짜에서 연도 추출
    if args.start:
        year = int(args.start.split('-')[0])
    else:
        year = args.year
    
    # 데이터 로드
    data = load_data(args.symbol, year)
    if data is None:
        return
    
    # 백테스트 실행
    system = Top4StrategySystem(initial_capital=args.capital)
    results = system.run_backtest(data, args.start, args.end)
    
    if results:
        print(f"\n🎉 {args.symbol} {args.year}년 백테스트 완료!")
        print(f"💰 최종 수익률: {results['total_return']:.2f}%")

if __name__ == "__main__":
    main()
