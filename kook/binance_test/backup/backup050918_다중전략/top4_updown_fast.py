#!/usr/bin/env python3
#-*-coding:utf-8 -*-

"""
상위 4개 전략 포트폴리오 시스템 (벡터화 버전 - 롱/숏 혼합)
=======================================================

판다스 벡터화를 사용하여 훨씬 빠른 백테스트
- 모멘텀: 롱 전용
- 스캘핑: 양방향
- MACD: 롱 전용  
- 이동평균: 양방향
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

class Top4StrategySystemFast:
    """상위 4개 전략 포트폴리오 시스템 (벡터화 버전 - 롱/숏 혼합)"""
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.base_capital_per_strategy = initial_capital / 4  # 기본 4등분
        self.trading_fee = 0.0006  # 0.06% 수수료
        self.leverage = 5.0  # 5배 레버리지
        
        # 전략별 거래 기록
        self.strategy_trades = {
            'momentum': [],
            'scalping': [],
            'macd': [],
            'moving_average': []
        }
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """모든 전략의 신호를 벡터화로 계산"""
        df = data.copy()
        
        # 1. 모멘텀 전략 신호 (롱 전용)
        df['momentum_20'] = df['close'].pct_change(20)
        df['momentum_signal'] = 0
        df.loc[df['momentum_20'] > 0.02, 'momentum_signal'] = 1
        df.loc[df['momentum_20'] < -0.02, 'momentum_signal'] = -1
        
        # 2. 스캘핑 전략 신호 (양방향)
        df['volatility_5'] = df['close'].pct_change().rolling(5).std()
        df['price_change_5'] = df['close'].pct_change(5)
        df['scalping_signal'] = 0
        scalping_buy = (df['volatility_5'] > 0.005) & (df['price_change_5'] > 0.003)
        scalping_sell = (df['volatility_5'] > 0.005) & (df['price_change_5'] < -0.003)
        df.loc[scalping_buy, 'scalping_signal'] = 1
        df.loc[scalping_sell, 'scalping_signal'] = -1
        
        # 3. MACD 전략 신호 (롱 전용)
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        
        df['macd'] = macd_line
        df['macd_signal'] = signal_line
        df['macd_cross_up'] = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
        df['macd_cross_down'] = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))
        
        df['macd_signal'] = 0
        df.loc[df['macd_cross_up'], 'macd_signal'] = 1
        df.loc[df['macd_cross_down'], 'macd_signal'] = -1
        
        # 4. 이동평균 전략 신호 (양방향)
        ma20 = df['close'].rolling(window=20).mean()
        ma50 = df['close'].rolling(window=50).mean()
        
        df['ma20'] = ma20
        df['ma50'] = ma50
        df['ma_cross_up'] = (ma20 > ma50) & (ma20.shift(1) <= ma50.shift(1))
        df['ma_cross_down'] = (ma20 < ma50) & (ma20.shift(1) >= ma50.shift(1))
        
        df['moving_average_signal'] = 0
        df.loc[df['ma_cross_up'], 'moving_average_signal'] = 1
        df.loc[df['ma_cross_down'], 'moving_average_signal'] = -1
        
        return df
    
    def backtest_strategy(self, data: pd.DataFrame, strategy_name: str) -> dict:
        """개별 전략 백테스트 (벡터화 - 롱/숏 혼합)"""
        signal_col = f'{strategy_name}_signal'
        signals = data[signal_col].values
        prices = data['close'].values
        timestamps = data.index
        
        # 전략별 거래 방식 결정
        is_long_only = strategy_name in ['momentum', 'macd']
        
        capital = self.base_capital_per_strategy
        position = 0  # 양수=롱, 음수=숏, 0=포지션없음
        entry_price = 0
        trades = []
        
        for i in range(len(signals)):
            current_price = prices[i]
            current_time = timestamps[i]
            signal = signals[i]
            
            if signal == 1:  # 매수 신호
                if position == 0:  # 포지션 없음 -> 롱 진입
                    leveraged_value = capital * self.leverage
                    fee = leveraged_value * self.trading_fee
                    net_value = leveraged_value - fee
                    shares = net_value / current_price
                    
                    position = shares  # 양수 = 롱 포지션
                    entry_price = current_price
                    capital = 0
                    
                    trades.append({
                        'timestamp': current_time,
                        'action': 'BUY_LONG',
                        'price': current_price,
                        'shares': shares,
                        'leverage': self.leverage,
                        'leveraged_value': leveraged_value,
                        'fee': fee,
                        'net_value': net_value,
                        'position_type': 'LONG'
                    })
                    
                elif position < 0:  # 숏 포지션 보유 -> 숏 청산 후 롱 진입
                    # 1단계: 숏 포지션 청산
                    short_shares = abs(position)
                    gross_value = short_shares * current_price
                    fee = gross_value * self.trading_fee
                    net_value = gross_value - fee
                    
                    # 숏 포지션 수익 계산
                    last_short_trade = next((t for t in reversed(trades) if t['action'] == 'SELL_SHORT'), None)
                    if last_short_trade:
                        entry_price_short = last_short_trade['price']
                        pnl_shares = (entry_price_short - current_price) * short_shares
                        original_capital = last_short_trade['leveraged_value'] / self.leverage
                        new_capital = max(0, original_capital + pnl_shares)
                    else:
                        new_capital = capital
                    
                    capital = new_capital
                    position = 0
                    
                    # 숏 청산 기록
                    trades.append({
                        'timestamp': current_time,
                        'action': 'COVER_SHORT',
                        'price': current_price,
                        'shares': short_shares,
                        'leverage': self.leverage,
                        'gross_value': gross_value,
                        'fee': fee,
                        'net_value': net_value,
                        'position_type': 'SHORT',
                        'capital_change': new_capital - (last_short_trade['leveraged_value'] / self.leverage) if last_short_trade else 0
                    })
                    
                    # 2단계: 롱 포지션 진입
                    if new_capital > 0:
                        leveraged_value = new_capital * self.leverage
                        fee = leveraged_value * self.trading_fee
                        net_value = leveraged_value - fee
                        shares = net_value / current_price
                        
                        position = shares
                        entry_price = current_price
                        capital = 0
                        
                        trades.append({
                            'timestamp': current_time,
                            'action': 'BUY_LONG',
                            'price': current_price,
                            'shares': shares,
                            'leverage': self.leverage,
                            'leveraged_value': leveraged_value,
                            'fee': fee,
                            'net_value': net_value,
                            'position_type': 'LONG'
                        })
            
            elif signal == -1:  # 매도 신호
                if position == 0:  # 포지션 없음
                    if is_long_only:
                        # 롱 전용 전략: 포지션 없을 때 매도 신호는 무시
                        continue
                    else:
                        # 양방향 전략: 숏 진입
                        leveraged_value = capital * self.leverage
                        fee = leveraged_value * self.trading_fee
                        net_value = leveraged_value - fee
                        shares = -(net_value / current_price)  # 음수 = 숏 포지션
                        
                        position = shares
                        entry_price = current_price
                        capital = 0
                        
                        trades.append({
                            'timestamp': current_time,
                            'action': 'SELL_SHORT',
                            'price': current_price,
                            'shares': abs(shares),
                            'leverage': self.leverage,
                            'leveraged_value': leveraged_value,
                            'fee': fee,
                            'net_value': net_value,
                            'position_type': 'SHORT'
                        })
                
                elif position > 0:  # 롱 포지션 보유
                    if is_long_only:
                        # 롱 전용 전략: 롱 청산만
                        gross_value = position * current_price
                        fee = gross_value * self.trading_fee
                        net_value = gross_value - fee
                        
                        # 롱 포지션 수익 계산
                        last_buy_trade = next((t for t in reversed(trades) if t['action'] == 'BUY_LONG'), None)
                        if last_buy_trade:
                            entry_price_long = last_buy_trade['price']
                            pnl_shares = (current_price - entry_price_long) * position
                            original_capital = last_buy_trade['leveraged_value'] / self.leverage
                            new_capital = max(0, original_capital + pnl_shares)
                        else:
                            new_capital = capital
                        
                        capital = new_capital
                        position = 0
                        
                        trades.append({
                            'timestamp': current_time,
                            'action': 'SELL_LONG',
                            'price': current_price,
                            'shares': position,
                            'leverage': self.leverage,
                            'gross_value': gross_value,
                            'fee': fee,
                            'net_value': net_value,
                            'position_type': 'LONG',
                            'capital_change': new_capital - (last_buy_trade['leveraged_value'] / self.leverage) if last_buy_trade else 0
                        })
                    else:
                        # 양방향 전략: 롱 청산 후 숏 진입
                        # 1단계: 롱 포지션 청산
                        gross_value = position * current_price
                        fee = gross_value * self.trading_fee
                        net_value = gross_value - fee
                        
                        # 롱 포지션 수익 계산
                        last_buy_trade = next((t for t in reversed(trades) if t['action'] == 'BUY_LONG'), None)
                        if last_buy_trade:
                            entry_price_long = last_buy_trade['price']
                            pnl_shares = (current_price - entry_price_long) * position
                            original_capital = last_buy_trade['leveraged_value'] / self.leverage
                            new_capital = max(0, original_capital + pnl_shares)
                        else:
                            new_capital = capital
                        
                        capital = new_capital
                        position = 0
                        
                        # 롱 청산 기록
                        trades.append({
                            'timestamp': current_time,
                            'action': 'SELL_LONG',
                            'price': current_price,
                            'shares': position,
                            'leverage': self.leverage,
                            'gross_value': gross_value,
                            'fee': fee,
                            'net_value': net_value,
                            'position_type': 'LONG',
                            'capital_change': new_capital - (last_buy_trade['leveraged_value'] / self.leverage) if last_buy_trade else 0
                        })
                        
                        # 2단계: 숏 포지션 진입
                        if new_capital > 0:
                            leveraged_value = new_capital * self.leverage
                            fee = leveraged_value * self.trading_fee
                            net_value = leveraged_value - fee
                            shares = -(net_value / current_price)  # 음수 = 숏 포지션
                            
                            position = shares
                            entry_price = current_price
                            capital = 0
                            
                            trades.append({
                                'timestamp': current_time,
                                'action': 'SELL_SHORT',
                                'price': current_price,
                                'shares': abs(shares),
                                'leverage': self.leverage,
                                'leveraged_value': leveraged_value,
                                'fee': fee,
                                'net_value': net_value,
                                'position_type': 'SHORT'
                            })
        
        # 최종 포지션 청산
        if position != 0:
            final_price = prices[-1]
            final_time = timestamps[-1]
            
            if position > 0:  # 롱 포지션 청산
                gross_value = position * final_price
                fee = gross_value * self.trading_fee
                net_value = gross_value - fee
                
                last_buy_trade = next((t for t in reversed(trades) if t['action'] == 'BUY_LONG'), None)
                if last_buy_trade:
                    entry_price_long = last_buy_trade['price']
                    pnl_shares = (final_price - entry_price_long) * position
                    original_capital = last_buy_trade['leveraged_value'] / self.leverage
                    new_capital = max(0, original_capital + pnl_shares)
                else:
                    new_capital = capital
                
                capital = new_capital
                
                trades.append({
                    'timestamp': final_time,
                    'action': 'SELL_LONG',
                    'price': final_price,
                    'shares': position,
                    'leverage': self.leverage,
                    'gross_value': gross_value,
                    'fee': fee,
                    'net_value': net_value,
                    'position_type': 'LONG',
                    'capital_change': new_capital - (last_buy_trade['leveraged_value'] / self.leverage) if last_buy_trade else 0
                })
                
            elif position < 0:  # 숏 포지션 청산
                short_shares = abs(position)
                gross_value = short_shares * final_price
                fee = gross_value * self.trading_fee
                net_value = gross_value - fee
                
                last_short_trade = next((t for t in reversed(trades) if t['action'] == 'SELL_SHORT'), None)
                if last_short_trade:
                    entry_price_short = last_short_trade['price']
                    pnl_shares = (entry_price_short - final_price) * short_shares
                    original_capital = last_short_trade['leveraged_value'] / self.leverage
                    new_capital = max(0, original_capital + pnl_shares)
                else:
                    new_capital = capital
                
                capital = new_capital
                
                trades.append({
                    'timestamp': final_time,
                    'action': 'COVER_SHORT',
                    'price': final_price,
                    'shares': short_shares,
                    'leverage': self.leverage,
                    'gross_value': gross_value,
                    'fee': fee,
                    'net_value': net_value,
                    'position_type': 'SHORT',
                    'capital_change': new_capital - (last_short_trade['leveraged_value'] / self.leverage) if last_short_trade else 0
                })
        
        return {
            'final_capital': capital,
            'trades': trades,
            'strategy_name': strategy_name
        }
    
    def run_backtest(self, data: pd.DataFrame, start_date: str = None, end_date: str = None):
        """백테스트 실행 (벡터화)"""
        print("🚀 상위 4개 전략 포트폴리오 백테스트 시작! (벡터화 버전 - 롱/숏 혼합)")
        print("=" * 70)
        print(f"💰 초기 자본: ${self.initial_capital:,.2f}")
        print(f"📊 전략별 자본: ${self.base_capital_per_strategy:,.2f}")
        print(f"⚡ 레버리지: {self.leverage}배")
        print(f"💸 수수료: {self.trading_fee*100:.2f}%")
        print(f"🔄 전략 구성: 모멘텀(롱전용), 스캘핑(양방향), MACD(롱전용), 이평(양방향)")
        print("=" * 70)
        
        # 날짜 필터링
        if start_date:
            data = data[data.index >= start_date]
        if end_date:
            data = data[data.index <= end_date]
        
        print(f"📅 기간: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
        print(f"📊 백테스트 데이터: {len(data)}개 캔들")
        print("=" * 70)
        
        # 1단계: 모든 신호 벡터화 계산
        print("🔄 1단계: 신호 계산 중...")
        data_with_signals = self.calculate_signals(data)
        print("✅ 신호 계산 완료!")
        
        # 2단계: 각 전략별 백테스트
        print("🔄 2단계: 전략별 백테스트 중...")
        strategies = ['momentum', 'scalping', 'macd', 'moving_average']
        results = {}
        
        for strategy in strategies:
            print(f"   📊 {strategy} 전략 처리 중...")
            results[strategy] = self.backtest_strategy(data_with_signals, strategy)
        
        print("✅ 모든 전략 백테스트 완료!")
        
        # 3단계: 결과 분석
        return self.analyze_results(results)
    
    def analyze_results(self, results: dict):
        """결과 분석"""
        print("\n📊 포트폴리오 성과 분석")
        print("=" * 60)
        
        total_final_capital = sum(result['final_capital'] for result in results.values())
        total_return = (total_final_capital - self.initial_capital) / self.initial_capital * 100
        
        print(f"💰 초기 자본: ${self.initial_capital:,.2f}")
        print(f"💰 최종 자본: ${total_final_capital:,.2f}")
        print(f"📈 총 수익률: {total_return:.2f}%")
        
        print("\n🎯 전략별 성과 (수수료 0.06% 적용, 혼합 전략)")
        print("-" * 80)
        
        strategy_types = {
            'momentum': '(롱전용)',
            'scalping': '(양방향)', 
            'macd': '(롱전용)',
            'moving_average': '(양방향)'
        }
        
        strategy_performance = {}
        for strategy_name, result in results.items():
            trades = result['trades']
            final_capital = result['final_capital']
            
            if trades:
                # 롱/숏 거래 분석
                long_trades = [t for t in trades if t['action'] in ['BUY_LONG', 'SELL_LONG']]
                short_trades = [t for t in trades if t['action'] in ['SELL_SHORT', 'COVER_SHORT']]
                
                total_trades = 0
                winning_trades = 0
                long_count = 0
                short_count = 0
                
                # 롱 포지션 거래 분석
                for i in range(0, len(long_trades), 2):
                    if i + 1 < len(long_trades):
                        buy_trade = long_trades[i]
                        sell_trade = long_trades[i + 1]
                        if buy_trade['action'] == 'BUY_LONG' and sell_trade['action'] == 'SELL_LONG':
                            pnl = sell_trade.get('capital_change', 0)
                            if pnl > 0:
                                winning_trades += 1
                            total_trades += 1
                            long_count += 1
                
                # 숏 포지션 거래 분석
                for i in range(0, len(short_trades), 2):
                    if i + 1 < len(short_trades):
                        short_trade = short_trades[i]
                        cover_trade = short_trades[i + 1]
                        if short_trade['action'] == 'SELL_SHORT' and cover_trade['action'] == 'COVER_SHORT':
                            pnl = cover_trade.get('capital_change', 0)
                            if pnl > 0:
                                winning_trades += 1
                            total_trades += 1
                            short_count += 1
                
                win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
                strategy_return = (final_capital - self.base_capital_per_strategy) / self.base_capital_per_strategy * 100
                
                strategy_performance[strategy_name] = {
                    'total_trades': total_trades,
                    'long_trades': long_count,
                    'short_trades': short_count,
                    'winning_trades': winning_trades,
                    'win_rate': win_rate,
                    'strategy_return': strategy_return,
                    'final_capital': final_capital
                }
                
                strategy_type = strategy_types.get(strategy_name, '')
                print(f"{strategy_name:15} {strategy_type:8} : 거래 {total_trades:3d}회 "
                      f"(롱 {long_count:2d}회, 숏 {short_count:2d}회), "
                      f"승률 {win_rate:5.1f}%, "
                      f"수익률 {strategy_return:6.2f}%, "
                      f"최종자본 ${final_capital:8,.2f}")
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': total_final_capital,
            'total_return': total_return,
            'strategy_performance': strategy_performance
        }

def load_data(symbol: str = 'BTCUSDT', year: int = 2023) -> pd.DataFrame:
    """데이터 로드"""
    print(f"📊 {symbol} {year}년 데이터 로드 중...")
    
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
    parser = argparse.ArgumentParser(description='상위 4개 전략 포트폴리오 백테스트 (벡터화 - 롱/숏 혼합)')
    parser.add_argument('--symbol', default='BTCUSDT', help='거래 심볼 (기본값: BTCUSDT)')
    parser.add_argument('--year', type=int, default=2024, help='백테스트 연도 (기본값: 2023)')
    parser.add_argument('--capital', type=float, default=100000, help='초기 자본 (기본값: 100000)')
    parser.add_argument('--start', help='시작 날짜 (YYYY-MM-DD)')
    parser.add_argument('--end', help='종료 날짜 (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    if args.start:
        year = int(args.start.split('-')[0])
    else:
        year = args.year
    
    data = load_data(args.symbol, year)
    if data is None:
        return
    
    system = Top4StrategySystemFast(initial_capital=args.capital)
    results = system.run_backtest(data, args.start, args.end)
    
    if results:
        print(f"\n🎉 {args.symbol} {args.year}년 백테스트 완료!")
        print(f"💰 최종 수익률: {results['total_return']:.2f}%")

if __name__ == "__main__":
    main()
