# -*- coding: utf-8 -*-
"""
번개 속도 트레이딩 시스템 - 연도별 성과 분석

=== 분석 기간 ===
2018년 ~ 2025년 (각 연도별)
"""

import pandas as pd
import numpy as np
import json
import os
import sys
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# lightning_system.py에서 클래스 import
from lightning_system import LightningTradingSystem

class LightningYearlyAnalyzer:
    """번개 속도 연도별 분석기"""
    
    def __init__(self):
        self.system = LightningTradingSystem()
        self.yearly_results = {}
        
    def load_all_years_data(self):
        """모든 연도 데이터 로드"""
        years = list(range(2018, 2026))  # 2018~2025
        data_files = []
        
        for year in years:
            # 5분봉 데이터 우선
            file_path = f"data/BTCUSDT/5m/BTCUSDT_5m_{year}.csv"
            if os.path.exists(file_path):
                data_files.append((year, file_path))
                print(f"데이터 파일 발견: {file_path}")
            else:
                # 1분봉 데이터 대체
                file_path = f"data/BTCUSDT/1m/BTCUSDT_1m_{year}.csv"
                if os.path.exists(file_path):
                    data_files.append((year, file_path))
                    print(f"데이터 파일 발견: {file_path}")
                else:
                    print(f"데이터 파일 없음: {year}년")
        
        return data_files
    
    def run_yearly_backtest(self, year, file_path):
        """특정 연도 백테스트 실행"""
        print(f"\n=== {year}년 분석 시작 ===")
        
        # 데이터 로드
        if not self.system.load_data(file_path):
            print(f"{year}년 데이터 로드 실패")
            return None
        
        print(f"데이터 로드 완료: {len(self.system.data)}개 캔들")
        
        # 연도별 백테스트 실행
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        
        result = self.system.run_lightning_backtest(start_date, end_date)
        
        if result:
            print(f"{year}년 결과:")
            print(f"  총 수익률: {result['total_return']:.2f}%")
            print(f"  최종 자본: {result['final_capital']:.2f}")
            print(f"  총 거래: {result['total_trades']}회")
            print(f"  승률: {result['win_rate']:.2f}%")
            print(f"  최대 낙폭: {result['max_drawdown']:.2f}%")
        
        return result
    
    def analyze_all_years(self):
        """모든 연도 분석"""
        print("=== 번개 속도 트레이딩 시스템 - 연도별 성과 분석 ===")
        
        # 모든 연도 데이터 로드
        data_files = self.load_all_years_data()
        
        if not data_files:
            print("분석할 데이터 파일이 없습니다.")
            return
        
        print(f"\n총 {len(data_files)}개 연도 데이터 발견")
        
        # 각 연도별 분석
        for year, file_path in data_files:
            try:
                result = self.run_yearly_backtest(year, file_path)
                if result:
                    self.yearly_results[year] = result
            except Exception as e:
                print(f"{year}년 분석 중 오류: {e}")
                continue
        
        # 전체 결과 요약
        self.generate_summary_report()
        
        # 상세 결과 저장
        self.save_detailed_results()
    
    def generate_summary_report(self):
        """요약 보고서 생성"""
        print("\n" + "="*60)
        print("번개 속도 트레이딩 시스템 - 연도별 성과 요약")
        print("="*60)
        
        if not self.yearly_results:
            print("분석 결과가 없습니다.")
            return
        
        # 연도별 결과 테이블
        print(f"{'연도':<6} {'수익률(%)':<10} {'최종자본':<12} {'거래수':<8} {'승률(%)':<10} {'최대낙폭(%)':<12}")
        print("-" * 70)
        
        total_return_sum = 0
        total_trades = 0
        winning_years = 0
        
        for year in sorted(self.yearly_results.keys()):
            result = self.yearly_results[year]
            total_return_sum += result['total_return']
            total_trades += result['total_trades']
            
            if result['total_return'] > 0:
                winning_years += 1
            
            print(f"{year:<6} {result['total_return']:<10.2f} {result['final_capital']:<12.2f} "
                  f"{result['total_trades']:<8} {result['win_rate']:<10.2f} {result['max_drawdown']:<12.2f}")
        
        # 전체 통계
        avg_return = total_return_sum / len(self.yearly_results)
        win_rate_years = (winning_years / len(self.yearly_results)) * 100
        
        print("-" * 70)
        print(f"평균 수익률: {avg_return:.2f}%")
        print(f"수익 연도: {winning_years}/{len(self.yearly_results)} ({win_rate_years:.1f}%)")
        print(f"총 거래: {total_trades}회")
        
        # 최고/최악 성과
        best_year = max(self.yearly_results.items(), key=lambda x: x[1]['total_return'])
        worst_year = min(self.yearly_results.items(), key=lambda x: x[1]['total_return'])
        
        print(f"\n최고 성과: {best_year[0]}년 ({best_year[1]['total_return']:.2f}%)")
        print(f"최악 성과: {worst_year[0]}년 ({worst_year[1]['total_return']:.2f}%)")
        
        # 연속 수익/손실 분석
        self.analyze_consecutive_performance()
    
    def analyze_consecutive_performance(self):
        """연속 성과 분석"""
        if len(self.yearly_results) < 2:
            return
        
        print(f"\n연속 성과 분석:")
        
        # 연도별 수익률 리스트
        returns = []
        for year in sorted(self.yearly_results.keys()):
            returns.append(self.yearly_results[year]['total_return'])
        
        # 연속 수익/손실 계산
        consecutive_wins = 0
        consecutive_losses = 0
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        
        current_wins = 0
        current_losses = 0
        
        for ret in returns:
            if ret > 0:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)
        
        print(f"최대 연속 수익: {max_consecutive_wins}년")
        print(f"최대 연속 손실: {max_consecutive_losses}년")
    
    def save_detailed_results(self):
        """상세 결과 저장"""
        if not self.yearly_results:
            return
        
        # JSON 파일로 저장
        output_file = "lightning_yearly_results.json"
        
        # JSON 직렬화 가능하도록 변환
        json_results = {}
        for year, result in self.yearly_results.items():
            json_results[str(year)] = {
                'total_return': result['total_return'],
                'final_capital': result['final_capital'],
                'total_trades': result['total_trades'],
                'win_rate': result['win_rate'],
                'max_drawdown': result['max_drawdown'],
                'trades_count': len(result['trades']) if 'trades' in result else 0
            }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_results, f, ensure_ascii=False, indent=2)
        
        print(f"\n상세 결과 저장: {output_file}")
        
        # CSV 파일로도 저장
        csv_file = "lightning_yearly_summary.csv"
        summary_data = []
        
        for year in sorted(self.yearly_results.keys()):
            result = self.yearly_results[year]
            summary_data.append({
                'year': year,
                'total_return': result['total_return'],
                'final_capital': result['final_capital'],
                'total_trades': result['total_trades'],
                'win_rate': result['win_rate'],
                'max_drawdown': result['max_drawdown']
            })
        
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_csv(csv_file, index=False, encoding='utf-8-sig')
        print(f"요약 결과 저장: {csv_file}")

def main():
    """메인 실행 함수"""
    print("=== 번개 속도 트레이딩 시스템 - 연도별 성과 분석 ===")
    
    # 분석기 초기화
    analyzer = LightningYearlyAnalyzer()
    
    # 모든 연도 분석 실행
    analyzer.analyze_all_years()
    
    print("\n=== 분석 완료 ===")

if __name__ == "__main__":
    main()
