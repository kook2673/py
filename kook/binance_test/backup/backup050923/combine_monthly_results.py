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
        logging.FileHandler('logs/combine_results.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MonthlyResultsCombiner:
    def __init__(self):
        self.results = []
        
    def load_monthly_results(self):
        """월별 결과 파일들 로드"""
        results_dir = 'results'
        monthly_files = [f for f in os.listdir(results_dir) if f.startswith('month_') and f.endswith('.json')]
        
        logger.info(f"총 {len(monthly_files)}개 월별 결과 파일 발견")
        
        for file in monthly_files:
            file_path = os.path.join(results_dir, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.results.append(data)
                    logger.info(f"✅ {file} 로드 완료")
            except Exception as e:
                logger.error(f"❌ {file} 로드 실패: {e}")
        
        logger.info(f"총 {len(self.results)}개 결과 로드 완료")
        return self.results
    
    def analyze_results(self):
        """결과 분석 및 통계"""
        if not self.results:
            logger.error("로드된 결과가 없습니다")
            return None
        
        # 데이터프레임으로 변환
        df_data = []
        for result in self.results:
            df_data.append({
                'month': result['month'],
                'strategy_type': result['strategy_type'],
                'market_condition': result['market_condition'],
                'total_return': result['best_result']['total_return'],
                'win_rate': result['best_result']['win_rate'],
                'trades': result['best_result']['trades'],
                'stop_loss_pct': result['best_params']['stop_loss_pct'],
                'volume_ratio_min': result['best_params']['volume_ratio_min'],
                'rsi_long_max': result['best_params']['rsi_long_max'],
                'rsi_short_min': result['best_params']['rsi_short_min'],
                'volatility_min': result['best_params']['volatility_min']
            })
        
        df = pd.DataFrame(df_data)
        
        # 기본 통계
        logger.info("\n=== 전체 통계 ===")
        logger.info(f"총 거래 수: {df['trades'].sum()}")
        logger.info(f"평균 수익률: {df['total_return'].mean()*100:.2f}%")
        logger.info(f"평균 승률: {df['win_rate'].mean()*100:.1f}%")
        logger.info(f"평균 거래수: {df['trades'].mean():.1f}")
        
        # 전략별 통계
        logger.info("\n=== 전략별 통계 ===")
        strategy_stats = df.groupby('strategy_type').agg({
            'total_return': ['mean', 'std'],
            'win_rate': ['mean', 'std'],
            'trades': ['mean', 'sum']
        }).round(4)
        logger.info(str(strategy_stats))
        
        # 월별 통계
        logger.info("\n=== 월별 통계 ===")
        monthly_stats = df.groupby('month').agg({
            'total_return': 'mean',
            'win_rate': 'mean',
            'trades': 'sum'
        }).round(4)
        logger.info(str(monthly_stats))
        
        return df
    
    def find_optimal_parameters(self):
        """최적 파라미터 찾기"""
        if not self.results:
            return None
        
        # 전략별, 시장상황별로 그룹화
        strategy_groups = {}
        for result in self.results:
            key = f"{result['strategy_type']}_{result['market_condition']}"
            if key not in strategy_groups:
                strategy_groups[key] = []
            strategy_groups[key].append(result)
        
        optimal_params = {}
        
        for group_name, group_results in strategy_groups.items():
            logger.info(f"\n=== {group_name} 최적화 ===")
            
            # 수익률 기준으로 정렬
            sorted_results = sorted(group_results, key=lambda x: x['best_result']['total_return'], reverse=True)
            
            # 상위 30% 결과들의 평균 파라미터 계산
            top_count = max(1, len(sorted_results) // 3)
            top_results = sorted_results[:top_count]
            
            avg_params = {}
            for param_key in ['stop_loss_pct', 'volume_ratio_min', 'rsi_long_max', 'rsi_short_min', 'volatility_min']:
                values = [r['best_params'][param_key] for r in top_results]
                avg_params[param_key] = np.mean(values)
            
            # 통계 정보
            returns = [r['best_result']['total_return'] for r in top_results]
            win_rates = [r['best_result']['win_rate'] for r in top_results]
            trades = [r['best_result']['trades'] for r in top_results]
            
            logger.info(f"상위 {top_count}개 결과 평균:")
            logger.info(f"  수익률: {np.mean(returns)*100:.2f}% ± {np.std(returns)*100:.2f}%")
            logger.info(f"  승률: {np.mean(win_rates)*100:.1f}% ± {np.std(win_rates)*100:.1f}%")
            logger.info(f"  거래수: {np.mean(trades):.1f} ± {np.std(trades):.1f}")
            logger.info(f"  최적 파라미터: {avg_params}")
            
            optimal_params[group_name] = {
                'parameters': avg_params,
                'statistics': {
                    'avg_return': np.mean(returns),
                    'std_return': np.std(returns),
                    'avg_win_rate': np.mean(win_rates),
                    'avg_trades': np.mean(trades),
                    'sample_count': top_count
                }
            }
        
        return optimal_params
    
    def save_combined_results(self, optimal_params, df):
        """결합된 결과 저장"""
        os.makedirs('results', exist_ok=True)
        
        # 최적 파라미터 저장
        with open('results/optimal_parameters.json', 'w', encoding='utf-8') as f:
            json.dump(optimal_params, f, ensure_ascii=False, indent=2)
        
        # 상세 통계 저장
        df.to_csv('results/monthly_statistics.csv', index=False, encoding='utf-8-sig')
        
        # 요약 보고서 생성
        report = {
            'summary': {
                'total_months': len(df),
                'total_trades': int(df['trades'].sum()),
                'avg_monthly_return': float(df['total_return'].mean()),
                'avg_win_rate': float(df['win_rate'].mean()),
                'avg_monthly_trades': float(df['trades'].mean())
            },
            'optimal_parameters': optimal_params
        }
        
        with open('results/combined_analysis_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info("📁 결과 파일 저장 완료:")
        logger.info("  - results/optimal_parameters.json")
        logger.info("  - results/monthly_statistics.csv")
        logger.info("  - results/combined_analysis_report.json")

def main():
    """메인 함수"""
    logger.info("🚀 월별 최적화 결과 결합 시작")
    
    combiner = MonthlyResultsCombiner()
    
    # 1. 월별 결과 로드
    results = combiner.load_monthly_results()
    if not results:
        logger.error("❌ 로드할 결과가 없습니다")
        return False
    
    # 2. 결과 분석
    df = combiner.analyze_results()
    if df is None:
        logger.error("❌ 분석 실패")
        return False
    
    # 3. 최적 파라미터 찾기
    optimal_params = combiner.find_optimal_parameters()
    if optimal_params is None:
        logger.error("❌ 최적 파라미터 찾기 실패")
        return False
    
    # 4. 결과 저장
    combiner.save_combined_results(optimal_params, df)
    
    logger.info("✅ 월별 결과 결합 완료!")
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("✅ 월별 최적화 결과 결합 완료!")
    else:
        print("❌ 결합 실패")
