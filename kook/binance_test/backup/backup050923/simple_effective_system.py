import pandas as pd
import numpy as np
import os
import logging
from datetime import datetime
import json

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/simple_effective.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SimpleEffectiveSystem:
    def __init__(self):
        self.strategies = ['bb', 'macd', 'scalping']  # BB가 가장 좋았으므로 우선순위
        self.performance_history = {}
        
    def load_data(self, year, month):
        """3분 데이터 로드"""
        file_path = f'data/BTCUSDT/3m/BTCUSDT_3m_{year}.csv'
        if not os.path.exists(file_path):
            return None
            
        df = pd.read_csv(file_path)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        
        # 특정 월만 필터링
        start_date = f'{year}-{month:02d}-01'
        if month == 12:
            end_date = f'{year+1}-01-01'
        else:
            end_date = f'{year}-{month+1:02d}-01'
            
        month_df = df[(df.index >= start_date) & (df.index < end_date)]
        return month_df
    
    def test_bb_strategy(self, df):
        """BB 전략 테스트 (고정 파라미터)"""
        # 볼린저 밴드
        df['bb_middle'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 롱 신호 (하단 근접 + RSI 과매도)
        long_conditions = (
            (df['close'] <= df['bb_lower'] * 1.01) &  # 하단 밴드 근처
            (df['rsi'] < 35) &  # RSI 과매도
            (df['close'].pct_change() > 0)  # 상승 모멘텀
        )
        
        # 숏 신호 (상단 근접 + RSI 과매수)
        short_conditions = (
            (df['close'] >= df['bb_upper'] * 0.99) &  # 상단 밴드 근처
            (df['rsi'] > 65) &  # RSI 과매수
            (df['close'].pct_change() < 0)  # 하락 모멘텀
        )
        
        df['long_signal'] = 0
        df['short_signal'] = 0
        df.loc[long_conditions, 'long_signal'] = 1
        df.loc[short_conditions, 'short_signal'] = 1
        
        return self.backtest_signals(df, 'bb')
    
    def test_macd_strategy(self, df):
        """MACD 전략 테스트 (고정 파라미터)"""
        # MACD
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 롱 신호 (골든크로스)
        long_conditions = (
            (df['macd'] > df['macd_signal']) &
            (df['macd'].shift(1) <= df['macd_signal'].shift(1)) &
            (df['rsi'] > 30) &
            (df['rsi'] < 70)
        )
        
        # 숏 신호 (데드크로스)
        short_conditions = (
            (df['macd'] < df['macd_signal']) &
            (df['macd'].shift(1) >= df['macd_signal'].shift(1)) &
            (df['rsi'] > 30) &
            (df['rsi'] < 70)
        )
        
        df['long_signal'] = 0
        df['short_signal'] = 0
        df.loc[long_conditions, 'long_signal'] = 1
        df.loc[short_conditions, 'short_signal'] = 1
        
        return self.backtest_signals(df, 'macd')
    
    def test_scalping_strategy(self, df):
        """스캘핑 전략 테스트 (고정 파라미터)"""
        # 기본 지표들
        df['volatility_5'] = df['close'].pct_change().rolling(5).std()
        df['price_change_5'] = df['close'].pct_change(5)
        df['volume_ma_10'] = df['volume'].rolling(10).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma_10']
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 롱 신호
        long_conditions = (
            (df['price_change_5'] > 0.001) &
            (df['volume_ratio'] > 1.2) &
            (df['rsi'] < 70) &
            (df['rsi'] > 30) &
            (df['volatility_5'] > 0.002)
        )
        
        # 숏 신호
        short_conditions = (
            (df['price_change_5'] < -0.001) &
            (df['volume_ratio'] > 1.2) &
            (df['rsi'] > 30) &
            (df['rsi'] < 80) &
            (df['volatility_5'] > 0.002)
        )
        
        df['long_signal'] = 0
        df['short_signal'] = 0
        df.loc[long_conditions, 'long_signal'] = 1
        df.loc[short_conditions, 'short_signal'] = 1
        
        return self.backtest_signals(df, 'scalping')
    
    def backtest_signals(self, df, strategy_name):
        """신호 백테스트"""
        balance = 10000
        trades = 0
        wins = 0
        position = 0
        entry_price = 0
        highest_profit = 0
        
        for i in range(len(df)):
            current_price = df['close'].iloc[i]
            long_signal = df['long_signal'].iloc[i]
            short_signal = df['short_signal'].iloc[i]
            
            # 롱 포지션
            if long_signal == 1 and position == 0:
                position = 1
                entry_price = current_price
                highest_profit = 0
                trades += 1
            
            # 숏 포지션
            elif short_signal == 1 and position == 0:
                position = -1
                entry_price = current_price
                highest_profit = 0
                trades += 1
            
            # 포지션 청산
            elif position != 0:
                if position == 1:  # 롱 포지션
                    current_profit = (current_price - entry_price) / entry_price
                else:  # 숏 포지션
                    current_profit = (entry_price - current_price) / entry_price
                
                # 익절 체크 (0.2% 이상)
                if current_profit >= 0.002:
                    if current_profit > highest_profit:
                        highest_profit = current_profit
                    
                    # 트레일링 스탑: 30% 하락 허용
                    trailing_stop_threshold = highest_profit * 0.3
                    if current_profit <= trailing_stop_threshold:
                        balance *= (1 + current_profit * 0.10)
                        if current_profit > 0:
                            wins += 1
                        position = 0
                        entry_price = 0
                        highest_profit = 0
                        continue
                
                # 손절 체크 (0.3%)
                elif current_profit <= -0.003:
                    balance *= (1 + current_profit * 0.10)
                    position = 0
                    entry_price = 0
                    highest_profit = 0
                    continue
                
                # 반대 신호로 청산
                elif (position == 1 and short_signal == 1) or (position == -1 and long_signal == 1):
                    balance *= (1 + current_profit * 0.10)
                    if current_profit > 0:
                        wins += 1
                    position = 0
                    entry_price = 0
                    highest_profit = 0
        
        # 최종 포지션 청산
        if position != 0:
            final_price = df['close'].iloc[-1]
            if position == 1:
                final_profit = (final_price - entry_price) / entry_price
            else:
                final_profit = (entry_price - final_price) / entry_price
            
            balance *= (1 + final_profit * 0.10)
            if final_profit > 0:
                wins += 1
        
        if trades == 0:
            return None
            
        win_rate = wins / trades
        total_return = (balance - 10000) / 10000
        
        return {
            'strategy_name': strategy_name,
            'total_return': total_return,
            'win_rate': win_rate,
            'trades': trades,
            'balance': balance
        }
    
    def adaptive_allocation(self, year=2025):
        """적응형 자산 배분 (성과 기반)"""
        logger.info(f"🚀 {year}년 적응형 자산 배분 시작")
        
        # 초기 자산 배분 (더 공격적)
        allocation = {
            'bb': 0.08,      # 8%
            'macd': 0.05,    # 5%
            'scalping': 0.05 # 5%
        }
        
        total_balance = 10000
        monthly_results = {}
        
        for month in range(1, 13):
            logger.info(f"\n{'='*60}")
            logger.info(f"{year}년 {month}월 적응형 배분")
            logger.info(f"{'='*60}")
            
            df = self.load_data(year, month)
            if df is None or len(df) < 100:
                logger.warning(f"{year}년 {month}월 데이터 부족")
                continue
            
            # 각 전략별 성과 계산
            strategy_performance = {}
            for strategy in self.strategies:
                if strategy == 'bb':
                    result = self.test_bb_strategy(df.copy())
                elif strategy == 'macd':
                    result = self.test_macd_strategy(df.copy())
                elif strategy == 'scalping':
                    result = self.test_scalping_strategy(df.copy())
                
                if result:
                    strategy_performance[strategy] = result
                    logger.info(f"{strategy}: 수익률 {result['total_return']*100:.2f}%, 승률 {result['win_rate']*100:.1f}%, 거래수 {result['trades']}")
            
            # 자산 배분 업데이트 (성과 기반)
            if strategy_performance:
                # 성과가 좋은 전략에 더 많은 자산 배분
                total_positive_return = sum(max(0, perf['total_return']) for perf in strategy_performance.values())
                
                if total_positive_return > 0:
                    for strategy, perf in strategy_performance.items():
                        if perf['total_return'] > 0:
                            # 성과에 비례하여 배분 증가
                            performance_ratio = perf['total_return'] / total_positive_return
                            new_allocation = min(0.10, 0.02 + performance_ratio * 0.08)  # 최소 2%, 최대 10%
                            allocation[strategy] = new_allocation
                        else:
                            allocation[strategy] = 0.02  # 최소 2%
                
                # 실제 거래 실행
                month_return = 0
                for strategy, perf in strategy_performance.items():
                    if strategy in allocation:
                        strategy_return = perf['total_return'] * allocation[strategy]
                        month_return += strategy_return
                        logger.info(f"{strategy}: {allocation[strategy]*100:.1f}% 배분, 기여 수익률 {strategy_return*100:.2f}%")
                
                total_balance *= (1 + month_return)
                logger.info(f"월 수익률: {month_return*100:.2f}%, 총 자산: {total_balance:.2f}")
                
                monthly_results[month] = {
                    'allocation': allocation.copy(),
                    'strategy_performance': strategy_performance,
                    'month_return': month_return,
                    'total_balance': total_balance
                }
        
        # 최종 결과 저장
        final_result = {
            'year': year,
            'initial_balance': 10000,
            'final_balance': total_balance,
            'total_return': (total_balance - 10000) / 10000,
            'monthly_results': monthly_results
        }
        
        with open(f'results/adaptive_allocation_{year}.json', 'w', encoding='utf-8') as f:
            json.dump(final_result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n🎉 {year}년 적응형 배분 완료!")
        logger.info(f"초기 자산: 10,000")
        logger.info(f"최종 자산: {total_balance:.2f}")
        logger.info(f"총 수익률: {(total_balance-10000)/10000*100:.2f}%")
        
        return final_result

def main():
    """메인 함수"""
    logger.info("🚀 간단하고 효과적인 시스템 시작")
    
    system = SimpleEffectiveSystem()
    result = system.adaptive_allocation(2025)
    
    if result:
        logger.info("✅ 적응형 배분 완료!")
        return True
    else:
        logger.error("❌ 시스템 실패")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("✅ 간단하고 효과적인 시스템 완료!")
    else:
        print("❌ 시스템 실패")
