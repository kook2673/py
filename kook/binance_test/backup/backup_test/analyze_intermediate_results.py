# -*- coding: utf-8 -*-
"""
중간 결과 파일 분석 스크립트
- extended_backtest_intermediate_*.csv 파일들을 분석
- 7개월 합산 수익률 계산
- 최고 성과 전략 찾기

사용법:
  python analyze_intermediate_results.py
"""

import os
import glob
import pandas as pd
import json
from datetime import datetime

def analyze_intermediate_results():
    """중간 결과 파일들을 분석하여 7개월 합산 수익률 계산"""
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(script_dir, 'logs', 'extended_backtest')
    
    # 중간 결과 파일들 찾기
    intermediate_files = glob.glob(os.path.join(logs_dir, 'extended_backtest_intermediate_*.csv'))
    if not intermediate_files:
        print("❌ 중간 결과 파일을 찾을 수 없습니다.")
        return
    
    print(f"📁 중간 결과 파일 {len(intermediate_files)}개 발견")
    
    # 파일들을 번호 순으로 정렬
    intermediate_files.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))
    
    all_results = []
    
    # 모든 파일의 결과를 합치기
    for file_path in intermediate_files:
        file_num = os.path.basename(file_path).split('_')[-1].split('.')[0]
        print(f"📖 {file_num}번 파일 읽는 중...")
        
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            all_results.append(df)
            print(f"✅ {len(df)}개 결과 로드 완료")
        except Exception as e:
            print(f"⚠️ {file_num}번 파일 읽기 실패: {e}")
    
    if not all_results:
        print("❌ 로드된 결과가 없습니다.")
        return
    
    # 모든 결과를 하나로 합치기
    combined_df = pd.concat(all_results, ignore_index=True)
    print(f"\n📊 총 {len(combined_df):,}개 결과 로드 완료")
    
    # 전략별로 7개월 합산 수익률 계산
    strategy_summary = {}
    
    for _, row in combined_df.iterrows():
        strategy_key = row['strategy_key']
        month = row['month']
        total_return = row['total_return']
        original_return = row['original_return']
        
        if strategy_key not in strategy_summary:
            strategy_summary[strategy_key] = {
                'rank': row['strategy_rank'],
                'months': set(),
                'monthly_returns': {},
                'total_cumulative_return': 0,
                'avg_monthly_return': 0,
                'max_mdd': 0,
                'total_trades': 0,
                'original_return': original_return,
                'win_rate': 0,
                'sharpe_ratio': 0
            }
        
        summary = strategy_summary[strategy_key]
        summary['months'].add(month)
        summary['monthly_returns'][month] = total_return
        summary['total_cumulative_return'] += total_return
        summary['max_mdd'] = max(summary['max_mdd'], row['mdd'])
        summary['total_trades'] += row['trades']
        summary['win_rate'] += row['win_rate']
        summary['sharpe_ratio'] += row['sharpe_ratio']
    
    # 평균 계산 및 정리
    for strategy_key, summary in strategy_summary.items():
        summary['months'] = len(summary['months'])
        summary['avg_monthly_return'] = summary['total_cumulative_return'] / summary['months']
        summary['win_rate'] = summary['win_rate'] / summary['months']
        summary['sharpe_ratio'] = summary['sharpe_ratio'] / summary['months']
        
        # 월별 수익률을 정렬된 리스트로 변환
        summary['monthly_returns_list'] = [
            summary['monthly_returns'].get(f'2025-{i:02d}', 0) 
            for i in range(1, 8)
        ]
    
    # 7개월 합산 수익률 기준으로 정렬
    sorted_strategies = sorted(
        strategy_summary.items(), 
        key=lambda x: x[1]['total_cumulative_return'], 
        reverse=True
    )
    
    print(f"\n🏆 7개월 합산 수익률 TOP 20 전략:")
    print("=" * 120)
    print(f"{'순위':<4} {'원래순위':<6} {'전략키':<35} {'3월수익률':<10} {'7개월합산':<10} {'월평균':<10} {'최대MDD':<8} {'총거래수':<8} {'월별수익률'}")
    print("-" * 120)
    
    for i, (strategy_key, summary) in enumerate(sorted_strategies[:20], 1):
        monthly_returns_str = ' '.join([f"{r:+6.1f}%" for r in summary['monthly_returns_list']])
        print(f"{i:2d}.  {summary['rank']:4d}    {strategy_key:<35} {summary['original_return']:+8.2f}% {summary['total_cumulative_return']:+8.2f}% {summary['avg_monthly_return']:+8.2f}% {summary['max_mdd']:6.2f}% {summary['total_trades']:8d} {monthly_returns_str}")
    
    print("-" * 120)
    
    # 양수 수익률 전략만 필터링
    positive_strategies = [
        (key, summary) for key, summary in strategy_summary.items() 
        if summary['total_cumulative_return'] > 0
    ]
    
    if positive_strategies:
        print(f"\n💰 7개월 합산 수익률이 양수인 전략: {len(positive_strategies)}개")
        print("=" * 80)
        
        positive_sorted = sorted(positive_strategies, key=lambda x: x[1]['total_cumulative_return'], reverse=True)
        
        for i, (strategy_key, summary) in enumerate(positive_sorted[:10], 1):
            monthly_returns_str = ' '.join([f"{r:+6.1f}%" for r in summary['monthly_returns_list']])
            print(f"{i:2d}. {strategy_key:<35} {summary['total_cumulative_return']:+8.2f}% {monthly_returns_str}")
        
        print("-" * 80)
        
        # 최고 성과 전략 상세 분석
        best_strategy = positive_sorted[0]
        print(f"\n🥇 최고 성과 전략: {best_strategy[0]}")
        print(f"   3월 수익률: {best_strategy[1]['original_return']:+.2f}%")
        print(f"   7개월 합산: {best_strategy[1]['total_cumulative_return']:+.2f}%")
        print(f"   월평균 수익률: {best_strategy[1]['avg_monthly_return']:+.2f}%")
        print(f"   최대 MDD: {best_strategy[1]['max_mdd']:.2f}%")
        print(f"   총 거래 수: {best_strategy[1]['total_trades']:,}개")
        print(f"   월별 수익률:")
        months = ['1월', '2월', '3월', '4월', '5월', '6월', '7월']
        for month, ret in zip(months, best_strategy[1]['monthly_returns_list']):
            print(f"     {month}: {ret:+.2f}%")
    
    else:
        print("\n⚠️ 7개월 합산 수익률이 양수인 전략이 없습니다.")
    
    # 결과 저장
    save_analysis_results(strategy_summary, sorted_strategies, positive_strategies)
    
    return strategy_summary, sorted_strategies, positive_strategies

def save_analysis_results(strategy_summary, sorted_strategies, positive_strategies):
    """분석 결과를 파일로 저장"""
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(script_dir, 'logs', 'extended_backtest')
    
    # CSV 저장
    csv_path = os.path.join(logs_dir, '7months_cumulative_analysis.csv')
    
    results_data = []
    for strategy_key, summary in strategy_summary.items():
        monthly_returns = summary['monthly_returns_list']
        results_data.append({
            'strategy_key': strategy_key,
            'original_rank': summary['rank'],
            'original_return': summary['original_return'],
            'total_cumulative_return': summary['total_cumulative_return'],
            'avg_monthly_return': summary['avg_monthly_return'],
            'months_tested': summary['months'],
            'max_mdd': summary['max_mdd'],
            'total_trades': summary['total_trades'],
            'avg_win_rate': summary['win_rate'],
            'avg_sharpe_ratio': summary['sharpe_ratio'],
            'jan_return': monthly_returns[0],
            'feb_return': monthly_returns[1],
            'mar_return': monthly_returns[2],
            'apr_return': monthly_returns[3],
            'may_return': monthly_returns[4],
            'jun_return': monthly_returns[5],
            'jul_return': monthly_returns[6]
        })
    
    df_results = pd.DataFrame(results_data)
    df_results = df_results.sort_values('total_cumulative_return', ascending=False)
    df_results.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"\n💾 분석 결과 CSV 저장 완료: {csv_path}")
    
    # JSON 저장
    json_path = os.path.join(logs_dir, '7months_cumulative_analysis.json')
    
    summary_data = {
        'analysis_time': datetime.now().isoformat(),
        'total_strategies': len(strategy_summary),
        'positive_strategies': len(positive_strategies),
        'top_10_strategies': [
            {
                'strategy_key': key,
                'rank': summary['rank'],
                'total_cumulative_return': summary['total_cumulative_return'],
                'avg_monthly_return': summary['avg_monthly_return']
            }
            for key, summary in sorted_strategies[:10]
        ],
        'positive_strategies': [
            {
                'strategy_key': key,
                'rank': summary['rank'],
                'total_cumulative_return': summary['total_cumulative_return'],
                'avg_monthly_return': summary['avg_monthly_return']
            }
            for key, summary in positive_strategies
        ],
        'all_strategies': strategy_summary
    }
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)
    print(f"💾 분석 결과 JSON 저장 완료: {json_path}")

def main():
    """메인 실행 함수"""
    print("🚀 중간 결과 분석 시작")
    print("=" * 50)
    
    analyze_intermediate_results()

if __name__ == '__main__':
    main()
