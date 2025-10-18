import pandas as pd
import numpy as np
import os
import logging
from datetime import datetime
import json
from itertools import product

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/multi_strategy_optimizer.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MultiStrategyOptimizer:
    def __init__(self):
        self.best_params = {}
        
    def load_monthly_data(self, year, month):
        """특정 월의 3분 데이터 로드"""
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
    
    def detect_market_condition(self, df):
        """시장 상황 감지"""
        if len(df) < 20:
            return 'sideways'
            
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        current_price = df['close'].iloc[-1]
        price_change = (current_price - ma20) / ma20
        
        if price_change > 0.02:
            return 'bullish'
        elif price_change < -0.02:
            return 'bearish'
        else:
            return 'sideways'
    
    def calculate_scalping_signals(self, df, params):
        """스캘핑 전략 신호 계산"""
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
            (df['price_change_5'] > params['price_change_min']) &
            (df['volume_ratio'] > params['volume_ratio_min']) &
            (df['rsi'] < params['rsi_long_max']) &
            (df['rsi'] > params['rsi_long_min']) &
            (df['volatility_5'] > params['volatility_min'])
        )
        
        # 숏 신호
        short_conditions = (
            (df['price_change_5'] < -params['price_change_min']) &
            (df['volume_ratio'] > params['volume_ratio_min']) &
            (df['rsi'] > params['rsi_short_min']) &
            (df['rsi'] < params['rsi_short_max']) &
            (df['volatility_5'] > params['volatility_min'])
        )
        
        df['scalping_long_signal'] = 0
        df['scalping_short_signal'] = 0
        df.loc[long_conditions, 'scalping_long_signal'] = 1
        df.loc[short_conditions, 'scalping_short_signal'] = 1
        
        return df
    
    def calculate_bb_signals(self, df, params):
        """볼린저 밴드 전략 신호 계산"""
        # 볼린저 밴드 계산
        df['bb_middle'] = df['close'].rolling(params['bb_period']).mean()
        df['bb_std'] = df['close'].rolling(params['bb_period']).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * params['bb_std_mult'])
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * params['bb_std_mult'])
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 롱 신호 (하단 터치 후 반등)
        long_conditions = (
            (df['close'] <= df['bb_lower']) &  # 하단 터치
            (df['rsi'] < params['rsi_oversold']) &  # 과매도
            (df['close'].shift(1) > df['bb_lower'].shift(1))  # 이전봉은 밴드 안
        )
        
        # 숏 신호 (상단 터치 후 하락)
        short_conditions = (
            (df['close'] >= df['bb_upper']) &  # 상단 터치
            (df['rsi'] > params['rsi_overbought']) &  # 과매수
            (df['close'].shift(1) < df['bb_upper'].shift(1))  # 이전봉은 밴드 안
        )
        
        df['bb_long_signal'] = 0
        df['bb_short_signal'] = 0
        df.loc[long_conditions, 'bb_long_signal'] = 1
        df.loc[short_conditions, 'bb_short_signal'] = 1
        
        return df
    
    def calculate_macd_signals(self, df, params):
        """MACD 전략 신호 계산"""
        # MACD 계산
        ema12 = df['close'].ewm(span=params['macd_fast']).mean()
        ema26 = df['close'].ewm(span=params['macd_slow']).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=params['macd_signal_period']).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 롱 신호 (MACD 골든크로스)
        long_conditions = (
            (df['macd'] > df['macd_signal']) &  # MACD > Signal
            (df['macd'].shift(1) <= df['macd_signal'].shift(1)) &  # 이전봉은 크로스 전
            (df['rsi'] > params['rsi_min']) &  # RSI 조건
            (df['rsi'] < params['rsi_max'])
        )
        
        # 숏 신호 (MACD 데드크로스)
        short_conditions = (
            (df['macd'] < df['macd_signal']) &  # MACD < Signal
            (df['macd'].shift(1) >= df['macd_signal'].shift(1)) &  # 이전봉은 크로스 전
            (df['rsi'] > params['rsi_min']) &  # RSI 조건
            (df['rsi'] < params['rsi_max'])
        )
        
        df['macd_long_signal'] = 0
        df['macd_short_signal'] = 0
        df.loc[long_conditions, 'macd_long_signal'] = 1
        df.loc[short_conditions, 'macd_short_signal'] = 1
        
        return df
    
    def test_strategy(self, df, strategy_name, params, strategy_type):
        """전략 테스트"""
        try:
            # 전략별 신호 계산
            if strategy_name == 'scalping':
                df = self.calculate_scalping_signals(df, params)
                long_signal_col = 'scalping_long_signal'
                short_signal_col = 'scalping_short_signal'
            elif strategy_name == 'bb':
                df = self.calculate_bb_signals(df, params)
                long_signal_col = 'bb_long_signal'
                short_signal_col = 'bb_short_signal'
            elif strategy_name == 'macd':
                df = self.calculate_macd_signals(df, params)
                long_signal_col = 'macd_long_signal'
                short_signal_col = 'macd_short_signal'
            else:
                return None
            
            balance = 10000
            trades = 0
            wins = 0
            position = 0
            entry_price = 0
            highest_profit = 0
            
            for i in range(len(df)):
                current_price = df['close'].iloc[i]
                
                if strategy_type == 'long':
                    signal = df[long_signal_col].iloc[i]
                else:
                    signal = df[short_signal_col].iloc[i]
                
                # 포지션 진입
                if signal == 1 and position == 0:
                    position = 1
                    entry_price = current_price
                    highest_profit = 0
                    trades += 1
                
                # 포지션 청산 체크
                elif position != 0:
                    if strategy_type == 'long':
                        current_profit = (current_price - entry_price) / entry_price
                    else:
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
                    
                    # 손절 체크
                    elif current_profit <= -params['stop_loss_pct']:
                        balance *= (1 + current_profit * 0.10)
                        position = 0
                        entry_price = 0
                        highest_profit = 0
                        continue
                    
                    # 신호 기반 청산 (반대 신호)
                    elif strategy_type == 'long' and df[short_signal_col].iloc[i] == 1:
                        balance *= (1 + current_profit * 0.10)
                        if current_profit > 0:
                            wins += 1
                        position = 0
                        entry_price = 0
                        highest_profit = 0
                    elif strategy_type == 'short' and df[long_signal_col].iloc[i] == 1:
                        balance *= (1 + current_profit * 0.10)
                        if current_profit > 0:
                            wins += 1
                        position = 0
                        entry_price = 0
                        highest_profit = 0
            
            # 최종 포지션 청산
            if position != 0:
                final_price = df['close'].iloc[-1]
                if strategy_type == 'long':
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
                'total_return': total_return,
                'win_rate': win_rate,
                'trades': trades,
                'balance': balance
            }
            
        except Exception as e:
            logger.debug(f"테스트 실패: {e}")
            return None
    
    def optimize_strategy(self, year, month, strategy_name, strategy_type, market_condition):
        """전략 최적화"""
        logger.info(f"=== {year}년 {month}월 {strategy_name} {strategy_type} {market_condition} 최적화 시작 ===")
        
        df = self.load_monthly_data(year, month)
        if df is None or len(df) < 100:
            logger.warning(f"{year}년 {month}월 데이터 부족")
            return None
        
        # 전략별 파라미터 범위 (조합 수 줄임)
        if strategy_name == 'scalping':
            param_ranges = {
                'stop_loss_pct': [0.002, 0.003],  # 2개
                'price_change_min': [0.001, 0.002],  # 2개
                'volume_ratio_min': [1.2, 1.5],  # 2개
                'rsi_long_max': [70, 80],  # 2개
                'rsi_long_min': [30, 40],  # 2개
                'rsi_short_max': [80, 90],  # 2개
                'rsi_short_min': [20, 30],  # 2개
                'volatility_min': [0.002, 0.003]  # 2개
            }
        elif strategy_name == 'bb':
            param_ranges = {
                'stop_loss_pct': [0.003, 0.005],  # 2개
                'bb_period': [20, 25],  # 2개
                'bb_std_mult': [2.0, 2.5],  # 2개
                'rsi_oversold': [30, 40],  # 2개
                'rsi_overbought': [60, 70]  # 2개
            }
        elif strategy_name == 'macd':
            param_ranges = {
                'stop_loss_pct': [0.003, 0.005],  # 2개
                'macd_fast': [12, 16],  # 2개
                'macd_slow': [26, 32],  # 2개
                'macd_signal_period': [9, 11],  # 2개
                'rsi_min': [30, 40],  # 2개
                'rsi_max': [60, 70]  # 2개
            }
        
        best_result = None
        best_params = None
        total_combinations = 1
        for values in param_ranges.values():
            total_combinations *= len(values)
        
        logger.info(f"총 {total_combinations}개 조합 테스트")
        
        # 모든 조합 테스트
        for i, params_tuple in enumerate(product(*param_ranges.values())):
            if i % 50 == 0:
                logger.info(f"진행률: {i+1}/{total_combinations} ({(i+1)/total_combinations*100:.1f}%)")
            
            params = dict(zip(param_ranges.keys(), params_tuple))
            
            result = self.test_strategy(df, strategy_name, params, strategy_type)
            if result and result['trades'] > 0:
                if best_result is None or result['total_return'] > best_result['total_return']:
                    best_result = result
                    best_params = params
        
        if best_result:
            logger.info(f"최적 결과: 수익률 {best_result['total_return']*100:.2f}%, 승률 {best_result['win_rate']*100:.1f}%, 거래수 {best_result['trades']}")
            return {
                'year': year,
                'month': month,
                'strategy_name': strategy_name,
                'strategy_type': strategy_type,
                'market_condition': market_condition,
                'best_params': best_params,
                'best_result': best_result
            }
        
        return None
    
    def run_monthly_optimization(self, start_year=2018, end_year=2024):
        """월별 최적화 실행"""
        results = []
        
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                logger.info(f"\n{'='*60}")
                logger.info(f"{year}년 {month}월 최적화 시작")
                logger.info(f"{'='*60}")
                
                df = self.load_monthly_data(year, month)
                if df is None or len(df) < 100:
                    logger.warning(f"{year}년 {month}월 데이터 부족")
                    continue
                
                market_condition = self.detect_market_condition(df)
                logger.info(f"시장 상황: {market_condition}")
                
                # 각 전략별로 최적화
                for strategy_name in ['scalping', 'bb', 'macd']:
                    for strategy_type in ['long', 'short']:
                        result = self.optimize_strategy(year, month, strategy_name, strategy_type, market_condition)
                        if result:
                            results.append(result)
                            logger.info(f"✅ {year}년 {month}월 {strategy_name} {strategy_type} {market_condition} 최적화 완료!")
                            
                            # 개별 결과 즉시 저장
                            os.makedirs('results', exist_ok=True)
                            filename = f'results/{year}_{month:02d}_{strategy_name}_{strategy_type}_{market_condition}_result.json'
                            with open(filename, 'w', encoding='utf-8') as f:
                                json.dump(result, f, ensure_ascii=False, indent=2)
                        else:
                            logger.warning(f"❌ {year}년 {month}월 {strategy_name} {strategy_type} {market_condition} 최적화 실패")
        
        # 전체 결과 저장
        with open('results/multi_strategy_optimization_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n🎉 총 {len(results)}개 전략 최적화 완료!")
        return results

def main():
    """메인 함수"""
    logger.info("🚀 다중 전략 최적화 시작 (스캘핑, BB, MACD)")
    
    optimizer = MultiStrategyOptimizer()
    results = optimizer.run_monthly_optimization()
    
    if results:
        logger.info("✅ 다중 전략 최적화 완료!")
        return True
    else:
        logger.error("❌ 최적화 실패")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("✅ 다중 전략 최적화 완료!")
    else:
        print("❌ 최적화 실패")
