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
        logging.FileHandler('logs/dynamic_allocation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DynamicAllocationSystem:
    def __init__(self):
        self.strategies = ['scalping', 'bb', 'macd']
        self.market_conditions = ['bullish', 'sideways', 'bearish']
        self.learned_params = {}
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
        
        # RSI 체크
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        # 거래량 체크
        volume_ma = df['volume'].rolling(20).mean().iloc[-1]
        current_volume = df['volume'].iloc[-1]
        volume_ratio = current_volume / volume_ma
        
        # 시장 상황 판단 (더 엄격한 조건)
        bullish_score = 0
        bearish_score = 0
        
        # 추세 점수
        if recent_trend > 0.03:
            bullish_score += 2
        elif recent_trend < -0.03:
            bearish_score += 2
        
        # 이동평균 점수
        if current_price > ma50.iloc[-1]:
            bullish_score += 1
        elif current_price < ma50.iloc[-1]:
            bearish_score += 1
        
        # RSI 점수
        if rsi > 60:
            bullish_score += 1
        elif rsi < 40:
            bearish_score += 1
        
        # 거래량 점수
        if volume_ratio > 1.2:
            if recent_trend > 0:
                bullish_score += 1
            elif recent_trend < 0:
                bearish_score += 1
        
        # 변동성 점수
        if volatility > 0.02:
            if recent_trend > 0:
                bullish_score += 1
            elif recent_trend < 0:
                bearish_score += 1
        
        # 최종 판단
        if bullish_score >= 4:
            return 'bullish'
        elif bearish_score >= 4:
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
        
        df['long_signal'] = 0
        df['short_signal'] = 0
        df.loc[long_conditions, 'long_signal'] = 1
        df.loc[short_conditions, 'short_signal'] = 1
        
        return df
    
    def calculate_bb_signals(self, df, params):
        """볼린저 밴드 전략 신호 계산"""
        # 볼린저 밴드
        df['bb_middle'] = df['close'].rolling(params['bb_period']).mean()
        df['bb_std'] = df['close'].rolling(params['bb_period']).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * params['bb_std_mult'])
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * params['bb_std_mult'])
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 롱 신호 (하단 터치 후 반등)
        long_conditions = (
            (df['close'] <= df['bb_lower']) &
            (df['rsi'] < params['rsi_oversold']) &
            (df['close'].shift(1) > df['bb_lower'].shift(1))
        )
        
        # 숏 신호 (상단 터치 후 하락)
        short_conditions = (
            (df['close'] >= df['bb_upper']) &
            (df['rsi'] > params['rsi_overbought']) &
            (df['close'].shift(1) < df['bb_upper'].shift(1))
        )
        
        df['long_signal'] = 0
        df['short_signal'] = 0
        df.loc[long_conditions, 'long_signal'] = 1
        df.loc[short_conditions, 'short_signal'] = 1
        
        return df
    
    def calculate_macd_signals(self, df, params):
        """MACD 전략 신호 계산"""
        # MACD
        ema12 = df['close'].ewm(span=params['macd_fast']).mean()
        ema26 = df['close'].ewm(span=params['macd_slow']).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=params['macd_signal_period']).mean()
        
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
            (df['rsi'] > params['rsi_min']) &
            (df['rsi'] < params['rsi_max'])
        )
        
        # 숏 신호 (데드크로스)
        short_conditions = (
            (df['macd'] < df['macd_signal']) &
            (df['macd'].shift(1) >= df['macd_signal'].shift(1)) &
            (df['rsi'] > params['rsi_min']) &
            (df['rsi'] < params['rsi_max'])
        )
        
        df['long_signal'] = 0
        df['short_signal'] = 0
        df.loc[long_conditions, 'long_signal'] = 1
        df.loc[short_conditions, 'short_signal'] = 1
        
        return df
    
    def test_strategy_with_params(self, df, strategy_name, params, strategy_type):
        """파라미터로 전략 테스트"""
        try:
            # 전략별 신호 계산
            if strategy_name == 'scalping':
                df = self.calculate_scalping_signals(df, params)
            elif strategy_name == 'bb':
                df = self.calculate_bb_signals(df, params)
            elif strategy_name == 'macd':
                df = self.calculate_macd_signals(df, params)
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
                    signal = df['long_signal'].iloc[i]
                else:
                    signal = df['short_signal'].iloc[i]
                
                # 포지션 진입
                if signal == 1 and position == 0:
                    position = 1 if strategy_type == 'long' else -1
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
                    
                    # 손절 체크
                    elif current_profit <= -params['stop_loss_pct']:
                        balance *= (1 + current_profit * 0.10)
                        position = 0
                        entry_price = 0
                        highest_profit = 0
                        continue
                    
                    # 반대 신호로 청산
                    elif (position == 1 and df['short_signal'].iloc[i] == 1) or \
                         (position == -1 and df['long_signal'].iloc[i] == 1):
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
                'total_return': total_return,
                'win_rate': win_rate,
                'trades': trades,
                'balance': balance
            }
            
        except Exception as e:
            logger.debug(f"테스트 실패: {e}")
            return None
    
    def optimize_strategy_for_market(self, year, month, strategy_name, market_condition):
        """시장 상황별 전략 최적화"""
        logger.info(f"=== {year}년 {month}월 {strategy_name} {market_condition} 최적화 ===")
        
        df = self.load_data(year, month)
        if df is None or len(df) < 100:
            return None
        
        # 시장 상황별 파라미터 범위
        if strategy_name == 'scalping':
            if market_condition == 'bullish':
                param_ranges = {
                    'stop_loss_pct': [0.001, 0.002],
                    'price_change_min': [0.0005, 0.001],
                    'volume_ratio_min': [1.0, 1.2],
                    'rsi_long_max': [70, 80],
                    'rsi_long_min': [30, 40],
                    'rsi_short_max': [80, 90],
                    'rsi_short_min': [20, 30],
                    'volatility_min': [0.001, 0.002]
                }
            elif market_condition == 'bearish':
                param_ranges = {
                    'stop_loss_pct': [0.002, 0.003],
                    'price_change_min': [0.001, 0.002],
                    'volume_ratio_min': [1.2, 1.5],
                    'rsi_long_max': [60, 70],
                    'rsi_long_min': [20, 30],
                    'rsi_short_max': [70, 80],
                    'rsi_short_min': [10, 20],
                    'volatility_min': [0.002, 0.003]
                }
            else:  # sideways
                param_ranges = {
                    'stop_loss_pct': [0.002, 0.003],
                    'price_change_min': [0.001, 0.002],
                    'volume_ratio_min': [1.2, 1.5],
                    'rsi_long_max': [70, 80],
                    'rsi_long_min': [30, 40],
                    'rsi_short_max': [80, 90],
                    'rsi_short_min': [20, 30],
                    'volatility_min': [0.002, 0.003]
                }
        
        elif strategy_name == 'bb':
            param_ranges = {
                'stop_loss_pct': [0.003, 0.005],
                'bb_period': [20, 25],
                'bb_std_mult': [2.0, 2.5],
                'rsi_oversold': [30, 40],
                'rsi_overbought': [60, 70]
            }
        
        elif strategy_name == 'macd':
            param_ranges = {
                'stop_loss_pct': [0.003, 0.005],
                'macd_fast': [12, 16],
                'macd_slow': [26, 32],
                'macd_signal_period': [9, 11],
                'rsi_min': [30, 40],
                'rsi_max': [60, 70]
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
            
            # 롱/숏 각각 테스트
            for strategy_type in ['long', 'short']:
                result = self.test_strategy_with_params(df, strategy_name, params, strategy_type)
                if result and result['trades'] > 0:
                    if best_result is None or result['total_return'] > best_result['total_return']:
                        best_result = result
                        best_params = params.copy()
                        best_params['strategy_type'] = strategy_type
        
        if best_result:
            logger.info(f"최적 결과: 수익률 {best_result['total_return']*100:.2f}%, 승률 {best_result['win_rate']*100:.1f}%, 거래수 {best_result['trades']}")
            return {
                'strategy_name': strategy_name,
                'market_condition': market_condition,
                'best_params': best_params,
                'best_result': best_result
            }
        
        return None
    
    def learn_optimal_parameters(self, start_year=2018, end_year=2024):
        """2018-2024년 최적 파라미터 학습"""
        logger.info("🚀 최적 파라미터 학습 시작 (2018-2024)")
        
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                logger.info(f"\n{'='*60}")
                logger.info(f"{year}년 {month}월 학습")
                logger.info(f"{'='*60}")
                
                df = self.load_data(year, month)
                if df is None or len(df) < 100:
                    logger.warning(f"{year}년 {month}월 데이터 부족")
                    continue
                
                market_condition = self.detect_market_condition(df)
                logger.info(f"시장 상황: {market_condition}")
                
                # 각 전략별로 최적화
                for strategy_name in self.strategies:
                    result = self.optimize_strategy_for_market(year, month, strategy_name, market_condition)
                    if result:
                        key = f"{strategy_name}_{market_condition}"
                        if key not in self.learned_params:
                            self.learned_params[key] = []
                        self.learned_params[key].append(result)
                        logger.info(f"✅ {strategy_name} {market_condition} 학습 완료")
        
        # 평균 파라미터 계산
        self.calculate_average_parameters()
        
        # 결과 저장
        with open('results/learned_parameters.json', 'w', encoding='utf-8') as f:
            json.dump(self.learned_params, f, ensure_ascii=False, indent=2)
        
        logger.info("✅ 학습 완료!")
        return self.learned_params
    
    def calculate_average_parameters(self):
        """평균 파라미터 계산"""
        logger.info("📊 평균 파라미터 계산 중...")
        
        for key, results in self.learned_params.items():
            if not results:
                continue
            
            # 상위 30% 결과들의 평균 파라미터 계산
            sorted_results = sorted(results, key=lambda x: x['best_result']['total_return'], reverse=True)
            top_count = max(1, len(sorted_results) // 3)
            top_results = sorted_results[:top_count]
            
            avg_params = {}
            for param_key in top_results[0]['best_params'].keys():
                if param_key != 'strategy_type':
                    values = [r['best_params'][param_key] for r in top_results]
                    avg_params[param_key] = np.mean(values)
            
            # 통계 정보
            returns = [r['best_result']['total_return'] for r in top_results]
            win_rates = [r['best_result']['win_rate'] for r in top_results]
            trades = [r['best_result']['trades'] for r in top_results]
            
            self.learned_params[key] = {
                'avg_params': avg_params,
                'strategy_type': top_results[0]['best_params']['strategy_type'],
                'statistics': {
                    'avg_return': np.mean(returns),
                    'std_return': np.std(returns),
                    'avg_win_rate': np.mean(win_rates),
                    'avg_trades': np.mean(trades),
                    'sample_count': top_count
                }
            }
            
            logger.info(f"{key}: 수익률 {np.mean(returns)*100:.2f}% ± {np.std(returns)*100:.2f}%, 승률 {np.mean(win_rates)*100:.1f}%")
    
    def test_dynamic_allocation(self, year=2025):
        """동적 자산 배분 테스트"""
        logger.info(f"🚀 {year}년 동적 자산 배분 테스트 시작")
        
        # 초기 자산 배분 (각 전략 1%씩)
        allocation = {
            'scalping_bullish': 0.01,
            'scalping_sideways': 0.01,
            'scalping_bearish': 0.01,
            'bb_bullish': 0.01,
            'bb_sideways': 0.01,
            'bb_bearish': 0.01,
            'macd_bullish': 0.01,
            'macd_sideways': 0.01,
            'macd_bearish': 0.01
        }
        
        total_balance = 10000
        monthly_results = {}
        
        for month in range(1, 13):
            logger.info(f"\n{'='*60}")
            logger.info(f"{year}년 {month}월 동적 배분 테스트")
            logger.info(f"{'='*60}")
            
            df = self.load_data(year, month)
            if df is None or len(df) < 100:
                logger.warning(f"{year}년 {month}월 데이터 부족")
                continue
            
            market_condition = self.detect_market_condition(df)
            logger.info(f"시장 상황: {market_condition}")
            
            # 현재 시장 상황에 맞는 전략들만 활성화
            active_strategies = [f"{strategy}_{market_condition}" for strategy in self.strategies]
            
            # 각 전략별 성과 계산
            strategy_performance = {}
            for strategy_key in active_strategies:
                if strategy_key in self.learned_params:
                    params = self.learned_params[strategy_key]['avg_params'].copy()
                    strategy_type = self.learned_params[strategy_key]['strategy_type']
                    strategy_name = strategy_key.split('_')[0]
                    
                    result = self.test_strategy_with_params(df, strategy_name, params, strategy_type)
                    if result:
                        strategy_performance[strategy_key] = result
                        logger.info(f"{strategy_key}: 수익률 {result['total_return']*100:.2f}%, 승률 {result['win_rate']*100:.1f}%")
            
            # 자산 배분 업데이트
            if strategy_performance:
                # 성과 기반으로 배분 조정
                total_performance = sum(perf['total_return'] for perf in strategy_performance.values())
                if total_performance > 0:
                    # 성과가 좋은 전략에 더 많은 자산 배분
                    for strategy_key, perf in strategy_performance.items():
                        if perf['total_return'] > 0:
                            # 성과에 비례하여 배분 증가 (최대 10%)
                            performance_ratio = perf['total_return'] / total_performance
                            new_allocation = min(0.10, 0.01 + performance_ratio * 0.09)
                            allocation[strategy_key] = new_allocation
                        else:
                            allocation[strategy_key] = 0.01  # 최소 1%
                
                # 실제 거래 실행
                month_return = 0
                for strategy_key, perf in strategy_performance.items():
                    if strategy_key in allocation:
                        strategy_return = perf['total_return'] * allocation[strategy_key]
                        month_return += strategy_return
                        logger.info(f"{strategy_key}: {allocation[strategy_key]*100:.1f}% 배분, 기여 수익률 {strategy_return*100:.2f}%")
                
                total_balance *= (1 + month_return)
                logger.info(f"월 수익률: {month_return*100:.2f}%, 총 자산: {total_balance:.2f}")
                
                monthly_results[month] = {
                    'market_condition': market_condition,
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
        
        with open(f'results/dynamic_allocation_{year}.json', 'w', encoding='utf-8') as f:
            json.dump(final_result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n🎉 {year}년 동적 배분 테스트 완료!")
        logger.info(f"초기 자산: 10,000")
        logger.info(f"최종 자산: {total_balance:.2f}")
        logger.info(f"총 수익률: {(total_balance-10000)/10000*100:.2f}%")
        
        return final_result

def main():
    """메인 함수"""
    logger.info("🚀 동적 자산 배분 시스템 시작")
    
    system = DynamicAllocationSystem()
    
    # 1. 2018-2024년 학습
    logger.info("1단계: 2018-2024년 최적 파라미터 학습")
    learned_params = system.learn_optimal_parameters()
    
    # 2. 2025년 동적 배분 테스트
    logger.info("2단계: 2025년 동적 자산 배분 테스트")
    result = system.test_dynamic_allocation(2025)
    
    logger.info("✅ 동적 자산 배분 시스템 완료!")
    return result

if __name__ == "__main__":
    result = main()
    if result:
        print("✅ 동적 자산 배분 시스템 완료!")
    else:
        print("❌ 시스템 실패")
