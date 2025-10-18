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
        logging.FileHandler('logs/scalping_optimizer.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ScalpingOptimizer:
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
    
    def calculate_scalping_signals(self, df, strategy_type, params=None):
        """스캘핑 신호 계산 (롱/숏) - 거래량 및 추가 지표 포함"""
        
        # 기본 파라미터 설정
        if params is None:
            params = {
                'volume_ratio_min': 1.2,
                'rsi_long_max': 70,
                'rsi_short_min': 30,
                'volatility_min': 0.002
            }
        
        # 1. 기본 지표들
        df['volatility_5'] = df['close'].pct_change().rolling(5).std()
        df['price_change_5'] = df['close'].pct_change(5)
        
        # 2. 거래량 지표들
        df['volume_ma_10'] = df['volume'].rolling(10).mean()  # 10일 평균 거래량
        df['volume_ratio'] = df['volume'] / df['volume_ma_10']  # 거래량 비율
        df['volume_spike'] = df['volume_ratio'] > 1.5  # 거래량 급증 (1.5배 이상)
        
        # 3. RSI (과매수/과매도)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 4. MACD (모멘텀)
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # 5. 볼린저 밴드 (변동성)
        df['bb_middle'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # 6. 이동평균 (추세)
        df['ma_5'] = df['close'].rolling(5).mean()
        df['ma_20'] = df['close'].rolling(20).mean()
        df['ma_trend'] = (df['ma_5'] > df['ma_20']).astype(int)
        
        # 7. 가격 모멘텀
        df['momentum_3'] = df['close'].pct_change(3)  # 3분 모멘텀
        df['momentum_5'] = df['close'].pct_change(5)  # 5분 모멘텀
        
        if strategy_type == 'long':
            # 스캘핑 롱 신호 (거래수 제한)
            df['scalping_signal'] = 0
            
            # 롱 진입 조건 (거래수 제한 추가)
            long_conditions = (
                (df['price_change_5'] > 0.001) &  # 가격 상승 (0.1%)
                (df['volume_ratio'] > params['volume_ratio_min']) &  # 거래량 조건
                (df['rsi'] < params['rsi_long_max']) &  # RSI 조건
                (df['volatility_5'] > params['volatility_min'])  # 변동성 조건
            )
            
            # 롱 청산 조건
            long_exit_conditions = (
                (df['price_change_5'] < -0.001)  # 가격 하락 (0.1%)
            ) | (
                (df['rsi'] > 85)  # 과매수
            )
            
            df.loc[long_conditions, 'scalping_signal'] = 1
            df.loc[long_exit_conditions, 'scalping_signal'] = -1
            
        elif strategy_type == 'short':
            # 스캘핑 숏 신호 (거래수 제한)
            df['scalping_signal'] = 0
            
            # 숏 진입 조건 (거래수 제한 추가)
            short_conditions = (
                (df['price_change_5'] < -0.001) &  # 가격 하락 (0.1%)
                (df['volume_ratio'] > params['volume_ratio_min']) &  # 거래량 조건
                (df['rsi'] > params['rsi_short_min']) &  # RSI 조건
                (df['volatility_5'] > params['volatility_min'])  # 변동성 조건
            )
            
            # 숏 청산 조건
            short_exit_conditions = (
                (df['price_change_5'] > 0.001)  # 가격 상승 (0.1%)
            ) | (
                (df['rsi'] < 15)  # 과매도
            )
            
            df.loc[short_conditions, 'scalping_signal'] = 1
            df.loc[short_exit_conditions, 'scalping_signal'] = -1
        
        # 신호 변화점 찾기
        df['entry_signal'] = (df['scalping_signal'] == 1) & (df['scalping_signal'].shift(1) == 0)
        df['exit_signal'] = (df['scalping_signal'] == -1) & (df['scalping_signal'].shift(1) == 0)
        
        return df
    
    def test_scalping_strategy(self, df, params, strategy_type, market_condition):
        """스캘핑 전략 테스트 (트레일링 스탑 포함)"""
        try:
            # 스캘핑 신호 계산
            df = self.calculate_scalping_signals(df, strategy_type, params)
            
            balance = 10000
            trades = 0
            wins = 0
            position = 0
            entry_price = 0
            highest_profit = 0  # 트레일링 스탑용
            
            for i in range(len(df)):
                current_price = df['close'].iloc[i]
                entry_signal = df['entry_signal'].iloc[i]
                exit_signal = df['exit_signal'].iloc[i]
                
                # 포지션 진입
                if entry_signal and position == 0:
                    position = 1
                    entry_price = current_price
                    highest_profit = 0
                    trades += 1
                
                # 포지션 청산 체크
                elif position != 0:
                    if strategy_type == 'long':
                        # 롱 포지션
                        current_profit = (current_price - entry_price) / entry_price
                        
                        # 익절 체크 (0.3% 이상)
                        if current_profit >= 0.003:
                            # 트레일링 스탑 체크
                            if current_profit > highest_profit:
                                highest_profit = current_profit
                            
                            # 트레일링 스탑: 50% 하락 허용
                            trailing_stop_threshold = highest_profit * 0.5
                            if current_profit <= trailing_stop_threshold:
                                # 청산
                                balance *= (1 + current_profit * params['position_size'])
                                if current_profit > 0:
                                    wins += 1
                                position = 0
                                entry_price = 0
                                highest_profit = 0
                                continue
                        
                        # 손절 체크
                        elif current_profit <= -params['stop_loss_pct']:
                            balance *= (1 + current_profit * params['position_size'])
                            position = 0
                            entry_price = 0
                            highest_profit = 0
                            continue
                        
                        # 신호 기반 청산
                        elif exit_signal:
                            balance *= (1 + current_profit * params['position_size'])
                            if current_profit > 0:
                                wins += 1
                            position = 0
                            entry_price = 0
                            highest_profit = 0
                    
                    elif strategy_type == 'short':
                        # 숏 포지션
                        current_profit = (entry_price - current_price) / entry_price
                        
                        # 익절 체크 (0.3% 이상)
                        if current_profit >= 0.003:
                            # 트레일링 스탑 체크
                            if current_profit > highest_profit:
                                highest_profit = current_profit
                            
                            # 트레일링 스탑: 50% 하락 허용
                            trailing_stop_threshold = highest_profit * 0.5
                            if current_profit <= trailing_stop_threshold:
                                # 청산
                                balance *= (1 + current_profit * params['position_size'])
                                if current_profit > 0:
                                    wins += 1
                                position = 0
                                entry_price = 0
                                highest_profit = 0
                                continue
                        
                        # 손절 체크
                        elif current_profit <= -params['stop_loss_pct']:
                            balance *= (1 + current_profit * params['position_size'])
                            position = 0
                            entry_price = 0
                            highest_profit = 0
                            continue
                        
                        # 신호 기반 청산
                        elif exit_signal:
                            balance *= (1 + current_profit * params['position_size'])
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
                
                balance *= (1 + final_profit * params['position_size'])
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
    
    def optimize_scalping_strategy(self, year, month, strategy_type, market_condition):
        """스캘핑 전략 최적화 (시장 상황별)"""
        logger.info(f"=== {year}년 {month}월 {strategy_type} {market_condition} 최적화 시작 ===")
        
        # 월별 데이터 로드
        df = self.load_monthly_data(year, month)
        if df is None or len(df) < 100:
            logger.warning(f"{year}년 {month}월 데이터 부족")
            return None
        
        # 파라미터 범위 (시장 상황별) - 포지션 사이즈 10% 고정
        if market_condition == 'bullish':
            param_ranges = {
                'stop_loss_pct': [0.001, 0.002, 0.003],
                'volume_ratio_min': [1.0, 1.2, 1.5],
                'rsi_long_max': [60, 70, 80],
                'rsi_short_min': [20, 30, 40],
                'volatility_min': [0.001, 0.002, 0.003]
            }
        elif market_condition == 'bearish':
            param_ranges = {
                'stop_loss_pct': [0.002, 0.003, 0.005],
                'volume_ratio_min': [1.0, 1.2, 1.5],
                'rsi_long_max': [60, 70, 80],
                'rsi_short_min': [20, 30, 40],
                'volatility_min': [0.001, 0.002, 0.003]
            }
        else:  # sideways
            param_ranges = {
                'stop_loss_pct': [0.001, 0.002, 0.003, 0.005],
                'volume_ratio_min': [1.0, 1.2, 1.5],
                'rsi_long_max': [60, 70, 80],
                'rsi_short_min': [20, 30, 40],
                'volatility_min': [0.001, 0.002, 0.003]
            }
        
        best_result = None
        best_params = None
        total_combinations = 1
        for values in param_ranges.values():
            total_combinations *= len(values)
        
        logger.info(f"총 {total_combinations}개 조합 테스트")
        
        # 모든 조합 테스트 (포지션 사이즈 10% 고정)
        from itertools import product
        for i, (sl, vol, rsi_l, rsi_s, vol_min) in enumerate(product(
            param_ranges['stop_loss_pct'],
            param_ranges['volume_ratio_min'],
            param_ranges['rsi_long_max'],
            param_ranges['rsi_short_min'],
            param_ranges['volatility_min']
        )):
            if i % 50 == 0:  # 50개씩 표시
                logger.info(f"진행률: {i+1}/{total_combinations} ({(i+1)/total_combinations*100:.1f}%)")
            
            params = {
                'stop_loss_pct': sl,
                'position_size': 0.10,  # 10% 고정
                'volume_ratio_min': vol,
                'rsi_long_max': rsi_l,
                'rsi_short_min': rsi_s,
                'volatility_min': vol_min
            }
            
            result = self.test_scalping_strategy(df, params, strategy_type, market_condition)
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
    
    def optimize_all_strategies(self):
        """모든 전략 최적화 (월별, 시장별, 롱/숏별)"""
        results = []
        
        # 2024년 1월부터 12월까지
        for month in range(1, 13):
            logger.info(f"\n{'='*60}")
            logger.info(f"2024년 {month}월 최적화 시작")
            logger.info(f"{'='*60}")
            
            # 월별 데이터 로드
            df = self.load_monthly_data(2024, month)
            if df is None or len(df) < 100:
                logger.warning(f"{month}월 데이터 부족")
                continue
            
            # 시장 상황 감지
            market_condition = self.detect_market_condition(df)
            logger.info(f"시장 상황: {market_condition}")
            
            # 롱/숏 전략 각각 최적화
            for strategy_type in ['long', 'short']:
                result = self.optimize_scalping_strategy(2024, month, strategy_type, market_condition)
                if result:
                    results.append(result)
                    logger.info(f"✅ {month}월 {strategy_type} {market_condition} 최적화 완료!")
                    
                    # 개별 결과 즉시 저장
                    os.makedirs('results', exist_ok=True)
                    filename = f'results/month_{month:02d}_{strategy_type}_{market_condition}_result.json'
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    logger.info(f"📁 {filename} 저장 완료")
                else:
                    logger.warning(f"❌ {month}월 {strategy_type} {market_condition} 최적화 실패")
        
        # 전체 결과 저장
        with open('results/scalping_optimization_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n🎉 총 {len(results)}개 전략 최적화 완료!")
        return results

def main():
    """메인 함수"""
    logger.info("🚀 스캘핑 전략 최적화 시작")
    
    optimizer = ScalpingOptimizer()
    results = optimizer.optimize_all_strategies()
    
    if results:
        logger.info("✅ 최적화 완료!")
        
        # 시장별, 전략별 평균 파라미터 계산
        market_strategy_params = {}
        for result in results:
            market = result['market_condition']
            strategy = result['strategy_type']
            key = f"{market}_{strategy}"
            
            if key not in market_strategy_params:
                market_strategy_params[key] = []
            market_strategy_params[key].append(result['best_params'])
        
        # 시장별, 전략별 최적 파라미터 저장
        final_params = {}
        for key, params_list in market_strategy_params.items():
            if params_list:
                # 평균 파라미터 계산
                avg_params = {}
                for param_key in params_list[0].keys():
                    values = [p[param_key] for p in params_list]
                    avg_params[param_key] = np.mean(values)
                
                final_params[key] = avg_params
                logger.info(f"{key} 최적 파라미터: {avg_params}")
        
        # 최종 파라미터 저장
        with open('results/final_scalping_params.json', 'w', encoding='utf-8') as f:
            json.dump(final_params, f, ensure_ascii=False, indent=2)
        
        return True
    else:
        logger.error("❌ 최적화 실패")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("✅ 스캘핑 전략 최적화 완료!")
    else:
        print("❌ 최적화 실패")
