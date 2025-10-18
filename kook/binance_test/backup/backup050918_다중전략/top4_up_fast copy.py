#!/usr/bin/env python3
#-*-coding:utf-8 -*-

"""
상위 4개 전략 포트폴리오 시스템 (벡터화 버전)
==========================================

판다스 벡터화를 사용하여 훨씬 빠른 백테스트
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
    """상위 4개 전략 포트폴리오 시스템 (벡터화 버전)"""
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.base_capital_per_strategy = initial_capital / 4  # 기본 4등분
        self.trading_fee = 0.0006  # 0.06% 수수료
        self.leverage = 3.0  # 3배 레버리지 (안전하게)
        self.stop_loss_pct = 0.15  # 15% 손절라인
        
        # 전략별 자본 (성과 기반 가중치)
        # 트렌드 숏 40%, 기타 숏 20%, 롱 전략 40%
        self.strategy_capitals = {
            'momentum': self.initial_capital * 0.10,        # 롱 모멘텀
            'scalping': self.initial_capital * 0.10,        # 롱 스캘핑
            'macd': self.initial_capital * 0.10,            # 롱 MACD
            'moving_average': self.initial_capital * 0.10,  # 롱 이동평균
            'short_scalping': self.initial_capital * 0.05,  # 숏 스캘핑 (감소)
            'short_momentum': self.initial_capital * 0.05,  # 숏 모멘텀 (감소)
            'trend_short': self.initial_capital * 0.40,     # 트렌드 숏 (대폭 증가)
            'bb_short': self.initial_capital * 0.10         # 볼린저 밴드 숏
        }
        
        # 전략별 거래 기록
        self.strategy_trades = {
            'momentum': [],
            'scalping': [],
            'macd': [],
            'moving_average': [],
            'short_scalping': [],
            'short_momentum': [],
            'trend_short': [],
            'bb_short': []
        }
        
    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """모든 전략의 신호를 벡터화로 계산"""
        df = data.copy()
        
        # 1. 모멘텀 전략 신호
        df['momentum_20'] = df['close'].pct_change(20)
        df['momentum_signal'] = 0
        df.loc[df['momentum_20'] > 0.02, 'momentum_signal'] = 1
        df.loc[df['momentum_20'] < -0.02, 'momentum_signal'] = -1
        
        # 2. 스캘핑 전략 신호
        df['volatility_5'] = df['close'].pct_change().rolling(5).std()
        df['price_change_5'] = df['close'].pct_change(5)
        df['scalping_signal'] = 0
        scalping_buy = (df['volatility_5'] > 0.005) & (df['price_change_5'] > 0.003)
        scalping_sell = (df['volatility_5'] > 0.005) & (df['price_change_5'] < -0.003)
        df.loc[scalping_buy, 'scalping_signal'] = 1
        df.loc[scalping_sell, 'scalping_signal'] = -1
        
        # 3. MACD 전략 신호
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
        
        # 4. 이동평균 전략 신호
        ma20 = df['close'].rolling(window=20).mean()
        ma50 = df['close'].rolling(window=50).mean()
        ma100 = df['close'].rolling(window=100).mean()
        
        df['ma20'] = ma20
        df['ma50'] = ma50
        df['ma100'] = ma100
        df['ma_cross_up'] = (ma20 > ma50) & (ma20.shift(1) <= ma50.shift(1))
        df['ma_cross_down'] = (ma20 < ma50) & (ma20.shift(1) >= ma50.shift(1))
        
        df['moving_average_signal'] = 0
        df.loc[df['ma_cross_up'], 'moving_average_signal'] = 1
        df.loc[df['ma_cross_down'], 'moving_average_signal'] = -1
        
        # 5. 숏 스캘핑 전략 신호 (하락장 대응)
        df['short_scalping_signal'] = 0
        short_scalping_entry = (df['volatility_5'] > 0.005) & (df['price_change_5'] < -0.003)
        short_scalping_exit = (df['volatility_5'] > 0.005) & (df['price_change_5'] > 0.003)
        df.loc[short_scalping_entry, 'short_scalping_signal'] = 1  # 숏 진입
        df.loc[short_scalping_exit, 'short_scalping_signal'] = -1  # 숏 청산
        
        # 6. 숏 모멘텀 전략 신호 (하락장 대응)
        df['short_momentum_signal'] = 0
        df.loc[df['momentum_20'] < -0.02, 'short_momentum_signal'] = 1  # 숏 진입
        df.loc[df['momentum_20'] > 0.02, 'short_momentum_signal'] = -1  # 숏 청산
        
        # 7. 트렌드 추종 숏 전략 (하락장 특화) - 강화 버전
        df['trend_short_signal'] = 0
        # 더 엄격한 하락 트렌드 조건: MA20 < MA50 < MA100
        strong_downtrend = (df['ma20'] < df['ma50']) & (df['ma50'] < df['ma100'])
        # 가격이 MA20 아래에 있고, 모멘텀도 하락
        price_below_ma20 = df['close'] < df['ma20']
        negative_momentum = df['momentum_20'] < -0.01  # 1% 이상 하락 모멘텀
        
        trend_short_entry = strong_downtrend & price_below_ma20 & negative_momentum
        # 트렌드 전환 또는 가격이 MA20 위로 올라가면 숏 청산
        trend_short_exit = (df['ma20'] > df['ma50']) | (df['close'] > df['ma20'])
        df.loc[trend_short_entry, 'trend_short_signal'] = 1  # 숏 진입
        df.loc[trend_short_exit, 'trend_short_signal'] = -1  # 숏 청산
        
        # 8. 볼린저 밴드 숏 전략 (하락장 특화)
        df['bb_upper'] = df['close'].rolling(20).mean() + (df['close'].rolling(20).std() * 2)
        df['bb_lower'] = df['close'].rolling(20).mean() - (df['close'].rolling(20).std() * 2)
        df['bb_short_signal'] = 0
        # 상단 밴드 터치 시 숏 진입, 하단 밴드 터치 시 숏 청산
        bb_short_entry = df['close'] >= df['bb_upper']
        bb_short_exit = df['close'] <= df['bb_lower']
        df.loc[bb_short_entry, 'bb_short_signal'] = 1  # 숏 진입
        df.loc[bb_short_exit, 'bb_short_signal'] = -1  # 숏 청산
        
        return df
    
    def check_stop_loss(self, position: float, entry_price: float, current_price: float, is_short: bool) -> bool:
        """손절라인 체크"""
        if position == 0:
            return False
        
        if is_short:
            # 숏 포지션: 가격이 올라가면 손실
            loss_pct = (current_price - entry_price) / entry_price
        else:
            # 롱 포지션: 가격이 내려가면 손실
            loss_pct = (entry_price - current_price) / entry_price
        
        return loss_pct >= self.stop_loss_pct
    
    def backtest_strategy(self, data: pd.DataFrame, strategy_name: str) -> dict:
        """개별 전략 백테스트 (벡터화)"""
        signal_col = f'{strategy_name}_signal'
        signals = data[signal_col].values
        prices = data['close'].values
        timestamps = data.index
        
        capital = self.strategy_capitals[strategy_name]
        position = 0
        entry_price = 0
        leveraged_value = 0  # 초기화 추가
        trades = []
        
        # 숏 전략 여부 확인
        is_short_strategy = strategy_name.startswith('short_')
        
        for i in range(len(signals)):
            current_price = prices[i]
            current_time = timestamps[i]
            signal = signals[i]
            
            # 손절라인 체크
            if position != 0:
                is_short = position < 0
                if self.check_stop_loss(position, entry_price, current_price, is_short):
                    # 손절라인 도달 - 강제 청산
                    if is_short:
                        gross_value = abs(position) * current_price
                        fee = gross_value * self.trading_fee
                        net_value = gross_value - fee
                        pnl = (entry_price - current_price) * abs(position)
                        original_capital = leveraged_value / self.leverage
                        capital_change = pnl
                        new_capital = max(0, original_capital + capital_change)
                        action = 'STOP_LOSS_SHORT'
                    else:
                        gross_value = position * current_price
                        fee = gross_value * self.trading_fee
                        net_value = gross_value - fee
                        pnl = (current_price - entry_price) * position
                        original_capital = leveraged_value / self.leverage
                        capital_change = pnl
                        new_capital = max(0, original_capital + capital_change)
                        action = 'STOP_LOSS_LONG'
                    
                    capital = new_capital
                    position = 0
                    entry_price = 0
                    
                    trades.append({
                        'timestamp': current_time,
                        'action': action,
                        'price': current_price,
                        'shares': abs(position),
                        'leverage': self.leverage,
                        'gross_value': gross_value,
                        'fee': fee,
                        'net_value': net_value,
                        'capital_change': capital_change
                    })
                    continue
            
            if signal == 1 and position == 0:  # 매수 (롱) 또는 숏 매수
                leveraged_value = capital * self.leverage
                fee = leveraged_value * self.trading_fee
                net_value = leveraged_value - fee
                shares = net_value / current_price
                
                if is_short_strategy:
                    position = -shares  # 음수 = 숏 포지션
                    action = 'SHORT_SELL'
                else:
                    position = shares   # 양수 = 롱 포지션
                    action = 'BUY'
                
                entry_price = current_price
                capital = 0
                
                trades.append({
                    'timestamp': current_time,
                    'action': action,
                    'price': current_price,
                    'shares': abs(shares),
                    'leverage': self.leverage,
                    'leveraged_value': leveraged_value,
                    'fee': fee,
                    'net_value': net_value
                })
                
            elif signal == -1 and position != 0:  # 매도 (롱) 또는 숏 매도
                if is_short_strategy:
                    # 숏 포지션 청산
                    gross_value = abs(position) * current_price
                    fee = gross_value * self.trading_fee
                    net_value = gross_value - fee
                    
                    # 숏 포지션 수익 계산
                    pnl = (entry_price - current_price) * abs(position)
                    original_capital = leveraged_value / self.leverage
                    capital_change = pnl
                    new_capital = max(0, original_capital + capital_change)
                    action = 'SHORT_COVER'
                else:
                    # 롱 포지션 청산
                    gross_value = position * current_price
                    fee = gross_value * self.trading_fee
                    net_value = gross_value - fee
                    
                    # 롱 포지션 수익 계산
                    pnl = (current_price - entry_price) * position
                    original_capital = leveraged_value / self.leverage
                    capital_change = pnl
                    new_capital = max(0, original_capital + capital_change)
                    action = 'SELL'
                
                capital = new_capital
                position = 0
                entry_price = 0
                
                trades.append({
                    'timestamp': current_time,
                    'action': action,
                    'price': current_price,
                    'shares': abs(position),
                    'leverage': self.leverage,
                    'gross_value': gross_value,
                    'fee': fee,
                    'net_value': net_value,
                    'capital_change': capital_change
                })
        
        # 최종 포지션 청산
        if position != 0:
            final_price = prices[-1]
            final_time = timestamps[-1]
            
            if position > 0:  # 롱 포지션
                gross_value = position * final_price
                fee = gross_value * self.trading_fee
                net_value = gross_value - fee
                
                # 롱 포지션 수익 계산
                pnl = (final_price - entry_price) * position
                original_capital = leveraged_value / self.leverage
                capital_change = pnl
                new_capital = max(0, original_capital + capital_change)
                action = 'SELL'
            else:  # 숏 포지션
                gross_value = abs(position) * final_price
                fee = gross_value * self.trading_fee
                net_value = gross_value - fee
                
                # 숏 포지션 수익 계산
                pnl = (entry_price - final_price) * abs(position)
                original_capital = leveraged_value / self.leverage
                capital_change = pnl
                new_capital = max(0, original_capital + capital_change)
                action = 'SHORT_COVER'
            
            capital = new_capital
            
            trades.append({
                'timestamp': final_time,
                'action': action,
                'price': final_price,
                'shares': abs(position),
                'leverage': self.leverage,
                'gross_value': gross_value,
                'fee': fee,
                'net_value': net_value,
                'capital_change': capital_change
            })
        
        return {
            'final_capital': capital,
            'trades': trades,
            'strategy_name': strategy_name
        }
    
    def run_backtest(self, data: pd.DataFrame, start_date: str = None, end_date: str = None):
        """백테스트 실행 (벡터화)"""
        print("🚀 상위 4개 전략 포트폴리오 백테스트 시작! (벡터화 버전)")
        print("=" * 60)
        print(f"💰 초기 자본: ${self.initial_capital:,.2f}")
        print(f"📊 롱 전략: 스캘핑 ${self.strategy_capitals['scalping']:,.0f}, 모멘텀 ${self.strategy_capitals['momentum']:,.0f}, MACD ${self.strategy_capitals['macd']:,.0f}, 이평 ${self.strategy_capitals['moving_average']:,.0f}")
        print(f"📊 숏 전략: 숏스캘핑 ${self.strategy_capitals['short_scalping']:,.0f}, 숏모멘텀 ${self.strategy_capitals['short_momentum']:,.0f}, 트렌드숏 ${self.strategy_capitals['trend_short']:,.0f}, BB숏 ${self.strategy_capitals['bb_short']:,.0f}")
        print(f"⚡ 레버리지: {self.leverage}배")
        print(f"💸 수수료: {self.trading_fee*100:.2f}%")
        
        # 날짜 필터링
        if start_date:
            data = data[data.index >= start_date]
        if end_date:
            data = data[data.index <= end_date]
        
        print(f"📅 기간: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
        print(f"📊 백테스트 데이터: {len(data)}개 캔들")
        print("=" * 60)
        
        # 1단계: 모든 신호 벡터화 계산
        print("🔄 1단계: 신호 계산 중...")
        data_with_signals = self.calculate_signals(data)
        print("✅ 신호 계산 완료!")
        
        # 2단계: 각 전략별 백테스트
        print("🔄 2단계: 전략별 백테스트 중...")
        strategies = ['momentum', 'scalping', 'macd', 'moving_average', 'short_scalping', 'short_momentum', 'trend_short', 'bb_short']
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
        
        print("\n🎯 전략별 성과 (수수료 0.06% 적용)")
        print("-" * 60)
        
        strategy_performance = {}
        for strategy_name, result in results.items():
            trades = result['trades']
            final_capital = result['final_capital']
            
            if trades:
                # 거래 수익률 계산
                total_trades = len(trades) // 2
                winning_trades = 0
                total_pnl = 0
                
                for i in range(0, len(trades), 2):
                    if i + 1 < len(trades):
                        buy_trade = trades[i]
                        sell_trade = trades[i + 1]
                        if buy_trade['action'] == 'BUY' and sell_trade['action'] == 'SELL':
                            pnl = sell_trade.get('capital_change', 0)
                            if pnl != 0:
                                buy_cost_capital = buy_trade['leveraged_value'] / self.leverage
                                actual_pnl = pnl / buy_cost_capital
                                total_pnl += actual_pnl
                                if actual_pnl > 0:
                                    winning_trades += 1
                
                win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
                initial_capital_strategy = self.strategy_capitals[strategy_name]
                strategy_return = (final_capital - initial_capital_strategy) / initial_capital_strategy * 100
                
                strategy_performance[strategy_name] = {
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'win_rate': win_rate,
                    'strategy_return': strategy_return,
                    'final_capital': final_capital
                }
                
                print(f"{strategy_name:15} : 거래 {total_trades:3d}회, "
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
    parser = argparse.ArgumentParser(description='상위 4개 전략 포트폴리오 백테스트 (벡터화)')
    parser.add_argument('--symbol', default='BTCUSDT', help='거래 심볼 (기본값: BTCUSDT)')
    parser.add_argument('--year', type=int, default=2022, help='백테스트 연도 (기본값: 2023)')
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
    system = Top4StrategySystemFast(initial_capital=args.capital)
    results = system.run_backtest(data, args.start, args.end)
    
    if results:
        print(f"\n🎉 {args.symbol} {args.year}년 백테스트 완료!")
        print(f"💰 최종 수익률: {results['total_return']:.2f}%")

if __name__ == "__main__":
    main()
