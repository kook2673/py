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
        logging.FileHandler('logs/pandas_optimizer.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PandasOptimizer:
    def __init__(self):
        self.best_params = {}
        
    def load_monthly_data(self, year, month):
        """특정 월의 1분 데이터 로드"""
        file_path = f'data/BTCUSDT/1m/BTCUSDT_1m_{year}.csv'
        if not os.path.exists(file_path):
            return None
            
        df = pd.read_csv(file_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
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
    
    def test_pandas_vectorized(self, df, params):
        """pandas 벡터화 연산으로 초고속 테스트"""
        try:
            # 이동평균 계산 (벡터화)
            df['ma_short'] = df['close'].rolling(params['ma_short']).mean()
            df['ma_long'] = df['close'].rolling(params['ma_long']).mean()
            
            # RSI 계산 (벡터화)
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # 매매 신호 생성 (벡터화) - MA + RSI 조합
            df['buy_signal'] = ((df['ma_short'] > df['ma_long']) & (df['rsi'] < 70)).astype(int)
            df['sell_signal'] = ((df['ma_short'] < df['ma_long']) & (df['rsi'] > 30)).astype(int)
            
            # 신호 변화점 찾기
            df['buy_entry'] = (df['buy_signal'] == 1) & (df['buy_signal'].shift(1) == 0)
            df['sell_entry'] = (df['sell_signal'] == 1) & (df['sell_signal'].shift(1) == 0)
            
            # 거래 시뮬레이션
            balance = 10000
            trades = 0
            wins = 0
            
            # 매수 거래
            buy_entries = df[df['buy_entry']].index
            for entry_idx in buy_entries:
                entry_price = df.loc[entry_idx, 'close']
                trades += 1
                
                # 5개 캔들 후 체크
                exit_idx = df.index[df.index.get_loc(entry_idx) + 5] if df.index.get_loc(entry_idx) + 5 < len(df) else df.index[-1]
                exit_price = df.loc[exit_idx, 'close']
                profit_pct = (exit_price - entry_price) / entry_price
                
                if profit_pct >= params['take_profit_pct']:
                    wins += 1
                    balance *= (1 + profit_pct * params['position_size'])
                elif profit_pct <= -params['stop_loss_pct']:
                    balance *= (1 + profit_pct * params['position_size'])
            
            # 매도 거래
            sell_entries = df[df['sell_entry']].index
            for entry_idx in sell_entries:
                entry_price = df.loc[entry_idx, 'close']
                trades += 1
                
                # 5개 캔들 후 체크
                exit_idx = df.index[df.index.get_loc(entry_idx) + 5] if df.index.get_loc(entry_idx) + 5 < len(df) else df.index[-1]
                exit_price = df.loc[exit_idx, 'close']
                profit_pct = (entry_price - exit_price) / entry_price
                
                if profit_pct >= params['take_profit_pct']:
                    wins += 1
                    balance *= (1 + profit_pct * params['position_size'])
                elif profit_pct <= -params['stop_loss_pct']:
                    balance *= (1 + profit_pct * params['position_size'])
            
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
    
    def optimize_month(self, year, month):
        """특정 월 최적화"""
        logger.info(f"=== {year}년 {month}월 최적화 시작 ===")
        
        # 월별 데이터 로드
        df = self.load_monthly_data(year, month)
        if df is None or len(df) < 100:
            logger.warning(f"{year}년 {month}월 데이터 부족")
            return None
        
        # 시장 상황 감지
        market_condition = self.detect_market_condition(df)
        logger.info(f"시장 상황: {market_condition}")
        
        # 파라미터 범위 (수수료 고려)
        param_ranges = {
            'take_profit_pct': [0.003, 0.005, 0.008, 0.010],  # 0.2% 이상
            'stop_loss_pct': [0.001, 0.002, 0.003, 0.005],
            'position_size': [0.10],  # 10%로 고정
            'ma_short': [3, 5, 8, 10, 12, 15],
            'ma_long': [8, 10, 15, 20, 25, 30]
        }
        
        best_result = None
        best_params = None
        total_combinations = 1
        for values in param_ranges.values():
            total_combinations *= len(values)
        
        logger.info(f"총 {total_combinations}개 조합 테스트")
        
        # 모든 조합 테스트
        from itertools import product
        for i, (tp, sl, pos, ma_s, ma_l) in enumerate(product(
            param_ranges['take_profit_pct'],
            param_ranges['stop_loss_pct'],
            param_ranges['position_size'],
            param_ranges['ma_short'],
            param_ranges['ma_long']
        )):
            if i % 50 == 0:  # 50개씩 표시
                logger.info(f"진행률: {i+1}/{total_combinations} ({(i+1)/total_combinations*100:.1f}%)")
            
            params = {
                'take_profit_pct': tp,
                'stop_loss_pct': sl,
                'position_size': pos,
                'ma_short': ma_s,
                'ma_long': ma_l
            }
            
            result = self.test_pandas_vectorized(df, params)
            if result and result['trades'] > 0:
                if best_result is None or result['total_return'] > best_result['total_return']:
                    best_result = result
                    best_params = params
        
        if best_result:
            logger.info(f"최적 결과: 수익률 {best_result['total_return']*100:.2f}%, 승률 {best_result['win_rate']*100:.1f}%, 거래수 {best_result['trades']}")
            return {
                'year': year,
                'month': month,
                'market_condition': market_condition,
                'best_params': best_params,
                'best_result': best_result
            }
        
        return None
    
    def optimize_all_months(self):
        """모든 월 최적화"""
        results = []
        
        # 2024년 1월부터 12월까지
        for month in range(1, 13):
            logger.info(f"\n{'='*50}")
            logger.info(f"2024년 {month}월 최적화 시작")
            logger.info(f"{'='*50}")
            
            result = self.optimize_month(2024, month)
            if result:
                results.append(result)
                logger.info(f"✅ {month}월 최적화 완료!")
                
                # 월별 결과 즉시 저장
                os.makedirs('results', exist_ok=True)
                with open(f'results/month_{month:02d}_result.json', 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                logger.info(f"📁 {month}월 결과 저장 완료")
            else:
                logger.warning(f"❌ {month}월 최적화 실패")
        
        # 전체 결과 저장
        with open('results/pandas_optimization_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n🎉 총 {len(results)}개 월 최적화 완료!")
        return results

def main():
    """메인 함수"""
    logger.info("🚀 Pandas 벡터화 최적화 시작")
    
    optimizer = PandasOptimizer()
    results = optimizer.optimize_all_months()
    
    if results:
        logger.info("✅ 최적화 완료!")
        
        # 시장별 평균 파라미터 계산
        market_params = {}
        for result in results:
            market = result['market_condition']
            if market not in market_params:
                market_params[market] = []
            market_params[market].append(result['best_params'])
        
        # 시장별 최적 파라미터 저장
        final_params = {}
        for market, params_list in market_params.items():
            if params_list:
                # 평균 파라미터 계산
                avg_params = {}
                for key in params_list[0].keys():
                    values = [p[key] for p in params_list]
                    if key in ['take_profit_pct', 'stop_loss_pct', 'position_size']:
                        avg_params[key] = np.mean(values)
                    else:
                        avg_params[key] = int(np.round(np.mean(values)))
                
                final_params[market] = avg_params
                logger.info(f"{market} 시장 최적 파라미터: {avg_params}")
        
        # 최종 파라미터 저장
        with open('results/final_pandas_params.json', 'w', encoding='utf-8') as f:
            json.dump(final_params, f, ensure_ascii=False, indent=2)
        
        return True
    else:
        logger.error("❌ 최적화 실패")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("✅ Pandas 벡터화 최적화 완료!")
    else:
        print("❌ 최적화 실패")