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
        logging.FileHandler('logs/improved_optimizer.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ImprovedOptimizer:
    def __init__(self):
        self.best_params = {}
        
    def load_data(self, year, month, timeframe='3m'):
        """특정 월의 데이터 로드"""
        file_path = f'data/BTCUSDT/{timeframe}/BTCUSDT_{timeframe}_{year}.csv'
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
        """시장 상황 감지 (개선된 버전)"""
        if len(df) < 50:
            return 'sideways'
            
        # 20일, 50일 이동평균
        ma20 = df['close'].rolling(20).mean()
        ma50 = df['close'].rolling(50).mean()
        
        # 최근 10일간의 추세
        recent_trend = (ma20.iloc[-10:].iloc[-1] - ma20.iloc[-10:].iloc[0]) / ma20.iloc[-10:].iloc[0]
        current_price = df['close'].iloc[-1]
        
        # 변동성 체크
        volatility = df['close'].pct_change().rolling(20).std().iloc[-1]
        
        # 시장 상황 판단
        if recent_trend > 0.05 and current_price > ma50.iloc[-1] and volatility > 0.02:
            return 'bullish'
        elif recent_trend < -0.05 and current_price < ma50.iloc[-1] and volatility > 0.02:
            return 'bearish'
        else:
            return 'sideways'
    
    def calculate_advanced_signals(self, df, strategy_type, params):
        """개선된 신호 계산"""
        
        # 1. 기본 지표들
        df['volatility_5'] = df['close'].pct_change().rolling(5).std()
        df['volatility_20'] = df['close'].pct_change().rolling(20).std()
        df['price_change_3'] = df['close'].pct_change(3)
        df['price_change_5'] = df['close'].pct_change(5)
        df['price_change_10'] = df['close'].pct_change(10)
        
        # 2. 거래량 지표들
        df['volume_ma_10'] = df['volume'].rolling(10).mean()
        df['volume_ma_20'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma_10']
        df['volume_trend'] = df['volume_ma_10'] / df['volume_ma_20']
        
        # 3. RSI (다중 기간)
        for period in [14, 21]:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            df[f'rsi_{period}'] = 100 - (100 / (1 + rs))
        
        # 4. MACD
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # 5. 볼린저 밴드
        df['bb_middle'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # 6. 이동평균 (다중 기간)
        for period in [5, 10, 20, 50]:
            df[f'ma_{period}'] = df['close'].rolling(period).mean()
        
        # 7. 모멘텀 지표
        df['momentum_3'] = df['close'].pct_change(3)
        df['momentum_5'] = df['close'].pct_change(5)
        df['momentum_10'] = df['close'].pct_change(10)
        
        # 8. 가격 위치
        df['price_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        if strategy_type == 'long':
            # 롱 진입 조건 (더 정교한 조건)
            long_conditions = (
                (df['price_change_5'] > params['price_change_min']) &  # 가격 상승
                (df['volume_ratio'] > params['volume_ratio_min']) &  # 거래량 증가
                (df['rsi_14'] < params['rsi_long_max']) &  # RSI 과매수 아님
                (df['rsi_14'] > params['rsi_long_min']) &  # RSI 과매도 아님
                (df['volatility_5'] > params['volatility_min']) &  # 충분한 변동성
                (df['macd'] > df['macd_signal']) &  # MACD 상승
                (df['ma_5'] > df['ma_20']) &  # 단기 이평 > 장기 이평
                (df['bb_position'] < 0.8)  # 볼린저 밴드 상단 근처 아님
            )
            
            # 롱 청산 조건
            long_exit_conditions = (
                (df['price_change_5'] < -params['price_change_min']) |  # 가격 하락
                (df['rsi_14'] > 85) |  # 과매수
                (df['macd'] < df['macd_signal']) |  # MACD 하락
                (df['bb_position'] > 0.9)  # 볼린저 밴드 상단 터치
            )
            
            df['scalping_signal'] = 0
            df.loc[long_conditions, 'scalping_signal'] = 1
            df.loc[long_exit_conditions, 'scalping_signal'] = -1
            
        elif strategy_type == 'short':
            # 숏 진입 조건 (더 정교한 조건)
            short_conditions = (
                (df['price_change_5'] < -params['price_change_min']) &  # 가격 하락
                (df['volume_ratio'] > params['volume_ratio_min']) &  # 거래량 증가
                (df['rsi_14'] > params['rsi_short_min']) &  # RSI 과매도 아님
                (df['rsi_14'] < params['rsi_short_max']) &  # RSI 과매수 아님
                (df['volatility_5'] > params['volatility_min']) &  # 충분한 변동성
                (df['macd'] < df['macd_signal']) &  # MACD 하락
                (df['ma_5'] < df['ma_20']) &  # 단기 이평 < 장기 이평
                (df['bb_position'] > 0.2)  # 볼린저 밴드 하단 근처 아님
            )
            
            # 숏 청산 조건
            short_exit_conditions = (
                (df['price_change_5'] > params['price_change_min']) |  # 가격 상승
                (df['rsi_14'] < 15) |  # 과매도
                (df['macd'] > df['macd_signal']) |  # MACD 상승
                (df['bb_position'] < 0.1)  # 볼린저 밴드 하단 터치
            )
            
            df['scalping_signal'] = 0
            df.loc[short_conditions, 'scalping_signal'] = 1
            df.loc[short_exit_conditions, 'scalping_signal'] = -1
        
        # 신호 변화점 찾기
        df['entry_signal'] = (df['scalping_signal'] == 1) & (df['scalping_signal'].shift(1) == 0)
        df['exit_signal'] = (df['scalping_signal'] == -1) & (df['scalping_signal'].shift(1) == 0)
        
        return df
    
    def test_strategy(self, df, params, strategy_type, market_condition):
        """전략 테스트"""
        try:
            df = self.calculate_advanced_signals(df, strategy_type, params)
            
            balance = 10000
            trades = 0
            wins = 0
            position = 0
            entry_price = 0
            highest_profit = 0
            
            for i in range(len(df)):
                current_price = df['close'].iloc[i]
                entry_signal = df['entry_signal'].iloc[i]
                exit_signal = df['exit_signal'].iloc[i]
                
                if entry_signal and position == 0:
                    position = 1
                    entry_price = current_price
                    highest_profit = 0
                    trades += 1
                
                elif position != 0:
                    if strategy_type == 'long':
                        current_profit = (current_price - entry_price) / entry_price
                        
                        if current_profit >= 0.003:  # 0.3% 익절
                            if current_profit > highest_profit:
                                highest_profit = current_profit
                            
                            trailing_stop_threshold = highest_profit * 0.5
                            if current_profit <= trailing_stop_threshold:
                                balance *= (1 + current_profit * 0.10)
                                if current_profit > 0:
                                    wins += 1
                                position = 0
                                entry_price = 0
                                highest_profit = 0
                                continue
                        
                        elif current_profit <= -params['stop_loss_pct']:
                            balance *= (1 + current_profit * 0.10)
                            position = 0
                            entry_price = 0
                            highest_profit = 0
                            continue
                        
                        elif exit_signal:
                            balance *= (1 + current_profit * 0.10)
                            if current_profit > 0:
                                wins += 1
                            position = 0
                            entry_price = 0
                            highest_profit = 0
                    
                    elif strategy_type == 'short':
                        current_profit = (entry_price - current_price) / entry_price
                        
                        if current_profit >= 0.003:  # 0.3% 익절
                            if current_profit > highest_profit:
                                highest_profit = current_profit
                            
                            trailing_stop_threshold = highest_profit * 0.5
                            if current_profit <= trailing_stop_threshold:
                                balance *= (1 + current_profit * 0.10)
                                if current_profit > 0:
                                    wins += 1
                                position = 0
                                entry_price = 0
                                highest_profit = 0
                                continue
                        
                        elif current_profit <= -params['stop_loss_pct']:
                            balance *= (1 + current_profit * 0.10)
                            position = 0
                            entry_price = 0
                            highest_profit = 0
                            continue
                        
                        elif exit_signal:
                            balance *= (1 + current_profit * 0.10)
                            if current_profit > 0:
                                wins += 1
                            position = 0
                            entry_price = 0
                            highest_profit = 0
            
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
    
    def optimize_strategy(self, year, month, strategy_type, market_condition):
        """전략 최적화 (개선된 파라미터 범위)"""
        logger.info(f"=== {year}년 {month}월 {strategy_type} {market_condition} 최적화 시작 ===")
        
        df = self.load_data(year, month, '3m')
        if df is None or len(df) < 100:
            logger.warning(f"{year}년 {month}월 데이터 부족")
            return None
        
        # 시장 상황별 파라미터 범위 (더 세분화)
        if market_condition == 'bullish':
            param_ranges = {
                'stop_loss_pct': [0.001, 0.002, 0.003, 0.005],
                'price_change_min': [0.0005, 0.001, 0.002],
                'volume_ratio_min': [1.0, 1.2, 1.5, 2.0],
                'rsi_long_max': [60, 70, 80],
                'rsi_long_min': [30, 40, 50],
                'rsi_short_max': [70, 80, 90],
                'rsi_short_min': [10, 20, 30],
                'volatility_min': [0.001, 0.002, 0.003, 0.005]
            }
        elif market_condition == 'bearish':
            param_ranges = {
                'stop_loss_pct': [0.002, 0.003, 0.005, 0.008],
                'price_change_min': [0.001, 0.002, 0.003],
                'volume_ratio_min': [1.2, 1.5, 2.0, 2.5],
                'rsi_long_max': [50, 60, 70],
                'rsi_long_min': [20, 30, 40],
                'rsi_short_max': [80, 90, 95],
                'rsi_short_min': [5, 15, 25],
                'volatility_min': [0.002, 0.003, 0.005, 0.008]
            }
        else:  # sideways
            param_ranges = {
                'stop_loss_pct': [0.001, 0.002, 0.003, 0.005, 0.008],
                'price_change_min': [0.0005, 0.001, 0.002, 0.003],
                'volume_ratio_min': [1.0, 1.2, 1.5, 2.0],
                'rsi_long_max': [60, 70, 80, 85],
                'rsi_long_min': [15, 25, 35, 45],
                'rsi_short_max': [70, 80, 85, 90],
                'rsi_short_min': [10, 20, 30, 40],
                'volatility_min': [0.001, 0.002, 0.003, 0.005]
            }
        
        best_result = None
        best_params = None
        total_combinations = 1
        for values in param_ranges.values():
            total_combinations *= len(values)
        
        logger.info(f"총 {total_combinations}개 조합 테스트")
        
        # 샘플링으로 조합 수 줄이기 (너무 많으면)
        if total_combinations > 10000:
            sample_size = 10000
            logger.info(f"조합이 너무 많아 {sample_size}개만 샘플링")
        else:
            sample_size = total_combinations
        
        # 모든 조합 테스트
        combinations = list(product(*param_ranges.values()))
        if len(combinations) > sample_size:
            import random
            combinations = random.sample(combinations, sample_size)
        
        for i, params_tuple in enumerate(combinations):
            if i % 100 == 0:
                logger.info(f"진행률: {i+1}/{len(combinations)} ({(i+1)/len(combinations)*100:.1f}%)")
            
            params = dict(zip(param_ranges.keys(), params_tuple))
            
            result = self.test_strategy(df, params, strategy_type, market_condition)
            if result and result['trades'] > 0:
                if best_result is None or result['total_return'] > best_result['total_return']:
                    best_result = result
                    best_params = params
        
        if best_result:
            logger.info(f"최적 결과: 수익률 {best_result['total_return']*100:.2f}%, 승률 {best_result['win_rate']*100:.1f}%, 거래수 {best_result['trades']}")
            return {
                'year': year,
                'month': month,
                'strategy_type': strategy_type,
                'market_condition': market_condition,
                'best_params': best_params,
                'best_result': best_result
            }
        
        return None
    
    def run_improved_optimization(self):
        """개선된 최적화 실행 (2018-2024년 전체 데이터 사용)"""
        results = []
        
        # 2018년부터 2024년까지 모든 데이터 사용
        for year in range(2018, 2025):
            for month in range(1, 13):
                logger.info(f"\n{'='*60}")
                logger.info(f"{year}년 {month}월 최적화 시작")
                logger.info(f"{'='*60}")
                
                df = self.load_data(year, month, '3m')
                if df is None or len(df) < 100:
                    logger.warning(f"{year}년 {month}월 데이터 부족")
                    continue
                
                market_condition = self.detect_market_condition(df)
                logger.info(f"시장 상황: {market_condition}")
                
                for strategy_type in ['long', 'short']:
                    result = self.optimize_strategy(year, month, strategy_type, market_condition)
                    if result:
                        results.append(result)
                        logger.info(f"✅ {year}년 {month}월 {strategy_type} {market_condition} 최적화 완료!")
                    else:
                        logger.warning(f"❌ {year}년 {month}월 {strategy_type} {market_condition} 최적화 실패")
        
        # 결과 저장
        with open('results/improved_optimization_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n🎉 총 {len(results)}개 전략 최적화 완료!")
        return results

def main():
    """메인 함수"""
    logger.info("🚀 개선된 최적화 시작 (2018-2024년 전체 데이터)")
    
    optimizer = ImprovedOptimizer()
    results = optimizer.run_improved_optimization()
    
    if results:
        logger.info("✅ 개선된 최적화 완료!")
        return True
    else:
        logger.error("❌ 최적화 실패")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("✅ 개선된 최적화 완료!")
    else:
        print("❌ 최적화 실패")
