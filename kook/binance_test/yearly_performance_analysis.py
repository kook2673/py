"""
연도별 성과 분석 시스템 (2018-2025)

=== 주요 기능 ===
1. 각 연도별 개별 백테스트
2. 연도별 성과 비교
3. 연도별 전략 분포 분석
4. 전체 기간 통합 분석
"""

import pandas as pd
import numpy as np
import json
import os
import sys
import io
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


# 향상된 적응형 시스템 import
from enhanced_adaptive_system import EnhancedAdaptiveTradingSystem

class YearlyPerformanceAnalyzer:
    """연도별 성과 분석기"""
    
    def __init__(self):
        self.system = EnhancedAdaptiveTradingSystem()
        self.yearly_results = {}
        self.all_data = None
        
    def load_all_years_data(self):
        """모든 연도 데이터 로드"""
        print("=== 전체 연도 데이터 로딩 ===")
        
        all_data = []
        for year in range(2018, 2026):  # 2018~2025
            file_path = f"data/BTCUSDT/5m/BTCUSDT_5m_{year}.csv"
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
                all_data.append(df)
                print(f"{year}년 데이터 로드: {len(df)}개 캔들")
            else:
                print(f"{year}년 데이터 파일을 찾을 수 없습니다.")
        
        if all_data:
            self.all_data = pd.concat(all_data, ignore_index=False).sort_index()
            print(f"전체 데이터: {len(self.all_data)}개 캔들")
            print(f"기간: {self.all_data.index.min()} ~ {self.all_data.index.max()}")
            return True
        return False
    
    def run_yearly_backtest(self, year):
        """특정 연도 백테스트 실행"""
        print(f"\n=== {year}년 백테스트 시작 ===")
        
        # 해당 연도 데이터 필터링
        year_data = self.all_data[self.all_data.index.year == year].copy()
        
        if len(year_data) == 0:
            print(f"{year}년 데이터가 없습니다.")
            return None
        
        # 시스템에 데이터 설정
        self.system.data = year_data
        
        # 백테스트 실행
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        
        result = self.system.run_enhanced_backtest(start_date, end_date)
        
        if result:
            # 연도 정보 추가
            result['year'] = year
            result['data_points'] = len(year_data)
            result['start_date'] = year_data.index.min().strftime('%Y-%m-%d')
            result['end_date'] = year_data.index.max().strftime('%Y-%m-%d')
            
            # 전략별 거래 분포
            strategy_trades = {}
            for trade in result['trades']:
                strategy = trade['strategy']
                if strategy not in strategy_trades:
                    strategy_trades[strategy] = 0
                strategy_trades[strategy] += 1
            
            result['strategy_distribution'] = strategy_trades
            
            print(f"{year}년 결과:")
            print(f"  수익률: {result['total_return']:.2f}%")
            print(f"  거래수: {result['total_trades']}회")
            print(f"  승률: {result['win_rate']:.2f}%")
            print(f"  최대낙폭: {result['max_drawdown']:.2f}%")
            
            return result
        
        return None
    
    def analyze_all_years(self):
        """모든 연도 분석"""
        print("=== 연도별 성과 분석 시작 ===")
        
        if not self.load_all_years_data():
            print("데이터 로드 실패")
            return None
        
        yearly_results = {}
        
        for year in range(2018, 2026):
            result = self.run_yearly_backtest(year)
            if result:
                yearly_results[year] = result
        
        self.yearly_results = yearly_results
        return yearly_results
    
    def generate_summary_report(self):
        """종합 요약 보고서 생성"""
        if not self.yearly_results:
            print("분석 결과가 없습니다.")
            return
        
        print("\n" + "="*60)
        print("📊 연도별 성과 종합 보고서")
        print("="*60)
        
        # 연도별 요약 테이블
        print("\n📈 연도별 성과 요약")
        print("-" * 80)
        print(f"{'연도':<6} {'수익률(%)':<10} {'거래수':<8} {'승률(%)':<8} {'MDD(%)':<8} {'최종자본':<12}")
        print("-" * 80)
        
        total_return = 0
        total_trades = 0
        total_win_rate = 0
        years_count = 0
        
        for year, result in self.yearly_results.items():
            print(f"{year:<6} {result['total_return']:<10.2f} {result['total_trades']:<8} "
                  f"{result['win_rate']:<8.2f} {result['max_drawdown']:<8.2f} {result['final_capital']:<12.2f}")
            
            total_return += result['total_return']
            total_trades += result['total_trades']
            total_win_rate += result['win_rate']
            years_count += 1
        
        print("-" * 80)
        
        # 평균 성과
        if years_count > 0:
            avg_return = total_return / years_count
            avg_win_rate = total_win_rate / years_count
            
            print(f"\n📊 평균 성과:")
            print(f"  평균 수익률: {avg_return:.2f}%")
            print(f"  총 거래수: {total_trades}회")
            print(f"  평균 승률: {avg_win_rate:.2f}%")
        
        # 최고/최저 성과
        best_year = max(self.yearly_results.items(), key=lambda x: x[1]['total_return'])
        worst_year = min(self.yearly_results.items(), key=lambda x: x[1]['total_return'])
        
        print(f"\n🏆 최고 성과: {best_year[0]}년 ({best_year[1]['total_return']:.2f}%)")
        print(f"📉 최저 성과: {worst_year[0]}년 ({worst_year[1]['total_return']:.2f}%)")
        
        # 전략별 사용 빈도
        print(f"\n🎯 전략별 사용 빈도:")
        strategy_usage = {}
        for year, result in self.yearly_results.items():
            for strategy, count in result['strategy_distribution'].items():
                if strategy not in strategy_usage:
                    strategy_usage[strategy] = 0
                strategy_usage[strategy] += count
        
        for strategy, count in sorted(strategy_usage.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / sum(strategy_usage.values())) * 100
            print(f"  {strategy}: {count}회 ({percentage:.1f}%)")
        
        return self.yearly_results
    
    def save_detailed_results(self):
        """상세 결과 저장"""
        if not self.yearly_results:
            return
        
        output = {
            'analysis_type': 'Yearly Performance Analysis (2018-2025)',
            'system_type': 'Enhanced Adaptive Trading System',
            'fee_rate': '0.05% per trade',
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'yearly_results': self.yearly_results,
            'summary': {
                'total_years': len(self.yearly_results),
                'total_trades': sum(r['total_trades'] for r in self.yearly_results.values()),
                'avg_return': sum(r['total_return'] for r in self.yearly_results.values()) / len(self.yearly_results),
                'best_year': max(self.yearly_results.items(), key=lambda x: x[1]['total_return'])[0],
                'worst_year': min(self.yearly_results.items(), key=lambda x: x[1]['total_return'])[0]
            }
        }
        
        with open('yearly_performance_results.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 상세 결과가 yearly_performance_results.json에 저장되었습니다.")

def main():
    """메인 실행 함수"""
    print("=== Yearly Performance Analysis (2018-2025) ===")
    
    try:
        # 분석기 초기화
        analyzer = YearlyPerformanceAnalyzer()
        
        # 모든 연도 분석
        results = analyzer.analyze_all_years()
        
        if results:
            # 종합 보고서 생성
            analyzer.generate_summary_report()
            
            # 상세 결과 저장
            analyzer.save_detailed_results()
        
        print("\n=== Analysis Complete ===")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
