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
        logging.FileHandler('logs/simple_multi_strategy.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SimpleMultiStrategy:
    def __init__(self):
        self.results = {}
        
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
    
    def test_bb_strategy(self, df):
        """볼린저 밴드 전략 테스트"""
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
        
        # 롱 신호 (하단 터치 후 반등)
        long_conditions = (
            (df['close'] <= df['bb_lower']) &
            (df['rsi'] < 30) &
            (df['close'].shift(1) > df['bb_lower'].shift(1))
        )
        
        # 숏 신호 (상단 터치 후 하락)
        short_conditions = (
            (df['close'] >= df['bb_upper']) &
            (df['rsi'] > 70) &
            (df['close'].shift(1) < df['bb_upper'].shift(1))
        )
        
        df['long_signal'] = 0
        df['short_signal'] = 0
        df.loc[long_conditions, 'long_signal'] = 1
        df.loc[short_conditions, 'short_signal'] = 1
        
        return self.backtest_signals(df, 'bb')
    
    def test_macd_strategy(self, df):
        """MACD 전략 테스트"""
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
                
                # 익절 체크 (0.3% 이상)
                if current_profit >= 0.003:
                    if current_profit > highest_profit:
                        highest_profit = current_profit
                    
                    # 트레일링 스탑: 50% 하락 허용
                    trailing_stop_threshold = highest_profit * 0.5
                    if current_profit <= trailing_stop_threshold:
                        balance *= (1 + current_profit * 0.10)
                        if current_profit > 0:
                            wins += 1
                        position = 0
                        entry_price = 0
                        highest_profit = 0
                        continue
                
                # 손절 체크 (0.5%)
                elif current_profit <= -0.005:
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
    
    def test_all_strategies(self, year, month):
        """모든 전략 테스트"""
        logger.info(f"\n{'='*60}")
        logger.info(f"{year}년 {month}월 전략 테스트")
        logger.info(f"{'='*60}")
        
        df = self.load_data(year, month)
        if df is None or len(df) < 100:
            logger.warning(f"{year}년 {month}월 데이터 부족")
            return None
        
        results = {}
        
        # 각 전략 테스트
        strategies = ['scalping', 'bb', 'macd']
        for strategy in strategies:
            if strategy == 'scalping':
                result = self.test_scalping_strategy(df.copy())
            elif strategy == 'bb':
                result = self.test_bb_strategy(df.copy())
            elif strategy == 'macd':
                result = self.test_macd_strategy(df.copy())
            
            if result:
                results[strategy] = result
                logger.info(f"✅ {strategy}: 수익률 {result['total_return']*100:.2f}%, 승률 {result['win_rate']*100:.1f}%, 거래수 {result['trades']}")
            else:
                logger.warning(f"❌ {strategy} 테스트 실패")
        
        return results
    
    def run_comparison(self, start_year=2024, end_year=2024):
        """전략 비교 실행"""
        logger.info("🚀 다중 전략 비교 시작")
        
        all_results = {}
        
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                month_results = self.test_all_strategies(year, month)
                if month_results:
                    all_results[f'{year}_{month:02d}'] = month_results
        
        # 결과 저장
        with open('results/strategy_comparison.json', 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        
        # 통계 계산
        self.calculate_statistics(all_results)
        
        return all_results
    
    def calculate_statistics(self, all_results):
        """통계 계산"""
        strategy_stats = {}
        
        for strategy in ['scalping', 'bb', 'macd']:
            returns = []
            win_rates = []
            trades = []
            
            for month_key, month_results in all_results.items():
                if strategy in month_results:
                    result = month_results[strategy]
                    returns.append(result['total_return'])
                    win_rates.append(result['win_rate'])
                    trades.append(result['trades'])
            
            if returns:
                strategy_stats[strategy] = {
                    'avg_return': np.mean(returns),
                    'std_return': np.std(returns),
                    'avg_win_rate': np.mean(win_rates),
                    'avg_trades': np.mean(trades),
                    'total_trades': sum(trades),
                    'months': len(returns)
                }
        
        # 결과 출력
        logger.info("\n=== 전략별 통계 ===")
        for strategy, stats in strategy_stats.items():
            logger.info(f"{strategy}:")
            logger.info(f"  평균 수익률: {stats['avg_return']*100:.2f}% ± {stats['std_return']*100:.2f}%")
            logger.info(f"  평균 승률: {stats['avg_win_rate']*100:.1f}%")
            logger.info(f"  평균 거래수: {stats['avg_trades']:.1f}")
            logger.info(f"  총 거래수: {stats['total_trades']}")
            logger.info(f"  테스트 월수: {stats['months']}")
        
        # 최고 전략 찾기
        best_strategy = max(strategy_stats.keys(), key=lambda x: strategy_stats[x]['avg_return'])
        logger.info(f"\n🏆 최고 전략: {best_strategy} (수익률: {strategy_stats[best_strategy]['avg_return']*100:.2f}%)")

def main():
    """메인 함수"""
    logger.info("🚀 간단한 다중 전략 비교 시작")
    
    optimizer = SimpleMultiStrategy()
    results = optimizer.run_comparison()
    
    if results:
        logger.info("✅ 전략 비교 완료!")
        return True
    else:
        logger.error("❌ 비교 실패")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("✅ 전략 비교 완료!")
    else:
        print("❌ 비교 실패")
