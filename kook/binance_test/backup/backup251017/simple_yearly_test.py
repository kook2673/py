"""
간단한 연도별 테스트 (2018-2025)
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# 향상된 적응형 시스템 import
from enhanced_adaptive_system import EnhancedAdaptiveTradingSystem

def test_single_year(year):
    """단일 연도 테스트"""
    print(f"\n=== {year}년 테스트 ===")
    
    # 시스템 초기화
    system = EnhancedAdaptiveTradingSystem()
    
    # 데이터 로드
    file_path = f"data/BTCUSDT/5m/BTCUSDT_5m_{year}.csv"
    if not os.path.exists(file_path):
        print(f"{year}년 데이터 파일이 없습니다.")
        return None
    
    if not system.load_data(file_path):
        print(f"{year}년 데이터 로드 실패")
        return None
    
    print(f"데이터 로드 완료: {len(system.data)}개 캔들")
    
    # 백테스트 실행
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    result = system.run_enhanced_backtest(start_date, end_date)
    
    if result:
        print(f"\n{year}년 결과:")
        print(f"  수익률: {result['total_return']:.2f}%")
        print(f"  거래수: {result['total_trades']}회")
        print(f"  승률: {result['win_rate']:.2f}%")
        print(f"  최대낙폭: {result['max_drawdown']:.2f}%")
        print(f"  최종자본: {result['final_capital']:.2f}")
        
        # 전략별 분포
        strategy_trades = {}
        for trade in result['trades']:
            strategy = trade['strategy']
            if strategy not in strategy_trades:
                strategy_trades[strategy] = 0
            strategy_trades[strategy] += 1
        
        print(f"  전략별 거래: {strategy_trades}")
        
        return result
    
    return None

def main():
    """메인 실행"""
    print("=== 연도별 성과 분석 (2018-2025) ===")
    
    results = {}
    
    # 각 연도별 테스트
    for year in range(2018, 2026):
        result = test_single_year(year)
        if result:
            results[year] = result
    
    # 종합 결과
    if results:
        print("\n" + "="*60)
        print("📊 연도별 성과 요약")
        print("="*60)
        print(f"{'연도':<6} {'수익률(%)':<10} {'거래수':<8} {'승률(%)':<8} {'MDD(%)':<8}")
        print("-" * 50)
        
        total_return = 0
        total_trades = 0
        years_count = 0
        
        for year, result in results.items():
            print(f"{year:<6} {result['total_return']:<10.2f} {result['total_trades']:<8} "
                  f"{result['win_rate']:<8.2f} {result['max_drawdown']:<8.2f}")
            
            total_return += result['total_return']
            total_trades += result['total_trades']
            years_count += 1
        
        print("-" * 50)
        
        if years_count > 0:
            avg_return = total_return / years_count
            print(f"평균 수익률: {avg_return:.2f}%")
            print(f"총 거래수: {total_trades}회")
            
            # 최고/최저 성과
            best_year = max(results.items(), key=lambda x: x[1]['total_return'])
            worst_year = min(results.items(), key=lambda x: x[1]['total_return'])
            
            print(f"최고 성과: {best_year[0]}년 ({best_year[1]['total_return']:.2f}%)")
            print(f"최저 성과: {worst_year[0]}년 ({worst_year[1]['total_return']:.2f}%)")
        
        # 결과 저장
        output = {
            'analysis_type': 'Yearly Performance Analysis',
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'results': results
        }
        
        with open('yearly_results.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n결과가 yearly_results.json에 저장되었습니다.")
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
