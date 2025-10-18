import pandas as pd
import numpy as np
import os
import json
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/backtest_2025.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Backtest2025:
    def __init__(self):
        self.optimal_params = None
        self.results = {}
        
    def load_optimal_parameters(self):
        """최적화된 파라미터 로드"""
        try:
            with open('results/optimal_parameters.json', 'r', encoding='utf-8') as f:
                self.optimal_params = json.load(f)
            logger.info("✅ 최적화된 파라미터 로드 완료")
            return True
        except Exception as e:
            logger.error(f"❌ 파라미터 로드 실패: {e}")
            return False
    
    def load_2025_data(self, month):
        """2025년 특정 월의 3분 데이터 로드"""
        file_path = f'data/BTCUSDT/3m/BTCUSDT_3m_2025.csv'
        if not os.path.exists(file_path):
            logger.warning(f"2025년 데이터 파일이 없습니다: {file_path}")
            return None
            
        df = pd.read_csv(file_path)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        
        # 특정 월만 필터링
        start_date = f'2025-{month:02d}-01'
        if month == 12:
            end_date = f'2026-01-01'
        else:
            end_date = f'2025-{month+1:02d}-01'
            
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
    
    def calculate_scalping_signals(self, df, strategy_type, params):
        """스캘핑 신호 계산"""
        
        # 1. 기본 지표들
        df['volatility_5'] = df['close'].pct_change().rolling(5).std()
        df['price_change_5'] = df['close'].pct_change(5)
        
        # 2. 거래량 지표들
        df['volume_ma_10'] = df['volume'].rolling(10).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma_10']
        
        # 3. RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        if strategy_type == 'long':
            # 롱 진입 조건
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
            
            df['scalping_signal'] = 0
            df.loc[long_conditions, 'scalping_signal'] = 1
            df.loc[long_exit_conditions, 'scalping_signal'] = -1
            
        elif strategy_type == 'short':
            # 숏 진입 조건
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
            
            df['scalping_signal'] = 0
            df.loc[short_conditions, 'scalping_signal'] = 1
            df.loc[short_exit_conditions, 'scalping_signal'] = -1
        
        # 신호 변화점 찾기
        df['entry_signal'] = (df['scalping_signal'] == 1) & (df['scalping_signal'].shift(1) == 0)
        df['exit_signal'] = (df['scalping_signal'] == -1) & (df['scalping_signal'].shift(1) == 0)
        
        return df
    
    def backtest_strategy(self, df, params, strategy_type, market_condition):
        """전략 백테스트"""
        try:
            # 스캘핑 신호 계산
            df = self.calculate_scalping_signals(df, strategy_type, params)
            
            balance = 10000
            trades = 0
            wins = 0
            position = 0
            entry_price = 0
            highest_profit = 0  # 트레일링 스탑용
            trade_log = []
            
            for i in range(len(df)):
                current_price = df['close'].iloc[i]
                entry_signal = df['entry_signal'].iloc[i]
                exit_signal = df['exit_signal'].iloc[i]
                current_time = df.index[i]
                
                # 포지션 진입
                if entry_signal and position == 0:
                    position = 1
                    entry_price = current_price
                    highest_profit = 0
                    trades += 1
                    trade_log.append({
                        'time': current_time,
                        'action': 'ENTRY',
                        'price': current_price,
                        'balance': balance
                    })
                
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
                                balance *= (1 + current_profit * 0.10)  # 10% 포지션
                                if current_profit > 0:
                                    wins += 1
                                trade_log.append({
                                    'time': current_time,
                                    'action': 'EXIT_TRAILING',
                                    'price': current_price,
                                    'profit': current_profit,
                                    'balance': balance
                                })
                                position = 0
                                entry_price = 0
                                highest_profit = 0
                                continue
                        
                        # 손절 체크
                        elif current_profit <= -params['stop_loss_pct']:
                            balance *= (1 + current_profit * 0.10)  # 10% 포지션
                            trade_log.append({
                                'time': current_time,
                                'action': 'EXIT_STOPLOSS',
                                'price': current_price,
                                'profit': current_profit,
                                'balance': balance
                            })
                            position = 0
                            entry_price = 0
                            highest_profit = 0
                            continue
                        
                        # 신호 기반 청산
                        elif exit_signal:
                            balance *= (1 + current_profit * 0.10)  # 10% 포지션
                            if current_profit > 0:
                                wins += 1
                            trade_log.append({
                                'time': current_time,
                                'action': 'EXIT_SIGNAL',
                                'price': current_price,
                                'profit': current_profit,
                                'balance': balance
                            })
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
                                balance *= (1 + current_profit * 0.10)  # 10% 포지션
                                if current_profit > 0:
                                    wins += 1
                                trade_log.append({
                                    'time': current_time,
                                    'action': 'EXIT_TRAILING',
                                    'price': current_price,
                                    'profit': current_profit,
                                    'balance': balance
                                })
                                position = 0
                                entry_price = 0
                                highest_profit = 0
                                continue
                        
                        # 손절 체크
                        elif current_profit <= -params['stop_loss_pct']:
                            balance *= (1 + current_profit * 0.10)  # 10% 포지션
                            trade_log.append({
                                'time': current_time,
                                'action': 'EXIT_STOPLOSS',
                                'price': current_price,
                                'profit': current_profit,
                                'balance': balance
                            })
                            position = 0
                            entry_price = 0
                            highest_profit = 0
                            continue
                        
                        # 신호 기반 청산
                        elif exit_signal:
                            balance *= (1 + current_profit * 0.10)  # 10% 포지션
                            if current_profit > 0:
                                wins += 1
                            trade_log.append({
                                'time': current_time,
                                'action': 'EXIT_SIGNAL',
                                'price': current_price,
                                'profit': current_profit,
                                'balance': balance
                            })
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
                
                balance *= (1 + final_profit * 0.10)  # 10% 포지션
                if final_profit > 0:
                    wins += 1
                trade_log.append({
                    'time': df.index[-1],
                    'action': 'EXIT_FINAL',
                    'price': final_price,
                    'profit': final_profit,
                    'balance': balance
                })
            
            if trades == 0:
                return None
                
            win_rate = wins / trades
            total_return = (balance - 10000) / 10000
            
            return {
                'total_return': total_return,
                'win_rate': win_rate,
                'trades': trades,
                'balance': balance,
                'trade_log': trade_log
            }
            
        except Exception as e:
            logger.debug(f"백테스트 실패: {e}")
            return None
    
    def run_2025_backtest(self):
        """2025년 전체 백테스트 실행"""
        if not self.optimal_params:
            logger.error("최적화된 파라미터가 없습니다")
            return False
        
        logger.info("🚀 2025년 백테스트 시작")
        
        # 2025년 1월부터 12월까지
        for month in range(1, 13):
            logger.info(f"\n{'='*60}")
            logger.info(f"2025년 {month}월 백테스트")
            logger.info(f"{'='*60}")
            
            # 월별 데이터 로드
            df = self.load_2025_data(month)
            if df is None or len(df) < 100:
                logger.warning(f"{month}월 데이터 부족")
                continue
            
            # 시장 상황 감지
            market_condition = self.detect_market_condition(df)
            logger.info(f"시장 상황: {market_condition}")
            
            # 롱/숏 전략 각각 백테스트
            for strategy_type in ['long', 'short']:
                # 파라미터 선택 (현재는 sideways만 있음)
                params = self.optimal_params[f'{strategy_type}_sideways']['parameters']
                
                result = self.backtest_strategy(df, params, strategy_type, market_condition)
                if result:
                    self.results[f'{month:02d}_{strategy_type}'] = {
                        'month': month,
                        'strategy_type': strategy_type,
                        'market_condition': market_condition,
                        'total_return': result['total_return'],
                        'win_rate': result['win_rate'],
                        'trades': result['trades'],
                        'balance': result['balance']
                    }
                    logger.info(f"✅ {month}월 {strategy_type}: 수익률 {result['total_return']*100:.2f}%, 승률 {result['win_rate']*100:.1f}%, 거래수 {result['trades']}")
                else:
                    logger.warning(f"❌ {month}월 {strategy_type} 백테스트 실패")
        
        # 결과 저장
        self.save_results()
        return True
    
    def save_results(self):
        """결과 저장"""
        os.makedirs('results', exist_ok=True)
        
        # 백테스트 결과 저장
        with open('results/backtest_2025_results.json', 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        # 통계 계산
        if self.results:
            total_return = sum(r['total_return'] for r in self.results.values())
            avg_win_rate = sum(r['win_rate'] for r in self.results.values()) / len(self.results)
            total_trades = sum(r['trades'] for r in self.results.values())
            
            summary = {
                'total_return': total_return,
                'avg_win_rate': avg_win_rate,
                'total_trades': total_trades,
                'monthly_results': self.results
            }
            
            with open('results/backtest_2025_summary.json', 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            logger.info(f"\n🎉 2025년 백테스트 완료!")
            logger.info(f"총 수익률: {total_return*100:.2f}%")
            logger.info(f"평균 승률: {avg_win_rate*100:.1f}%")
            logger.info(f"총 거래수: {total_trades}")

def main():
    """메인 함수"""
    logger.info("🚀 2025년 백테스트 시작")
    
    backtest = Backtest2025()
    
    # 1. 최적화된 파라미터 로드
    if not backtest.load_optimal_parameters():
        return False
    
    # 2. 2025년 백테스트 실행
    success = backtest.run_2025_backtest()
    
    if success:
        logger.info("✅ 2025년 백테스트 완료!")
        return True
    else:
        logger.error("❌ 백테스트 실패")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("✅ 2025년 백테스트 완료!")
    else:
        print("❌ 백테스트 실패")
