#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2018-2024년 연속 백테스트 실행 스크립트
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
from advanced_ma_ml_bot_fast import AdvancedMAMLBotFast

def main():
    parser = argparse.ArgumentParser(description='2018-2024년 연속 백테스트 실행')
    parser.add_argument('--start-year', type=int, default=2018, help='시작 연도 (기본값: 2018)')
    parser.add_argument('--end-year', type=int, default=2024, help='종료 연도 (기본값: 2024)')
    parser.add_argument('--balance', type=float, default=10000, help='초기 자본 (기본값: 10000)')
    parser.add_argument('--leverage', type=int, default=20, help='레버리지 (기본값: 20)')
    parser.add_argument('--data-dir', default='data/BTCUSDT/5m', help='데이터 디렉토리')
    
    args = parser.parse_args()
    
    print("🚀 2018-2024년 연속 백테스트 시작!")
    print("=" * 80)
    print(f"💰 초기 자본: ${args.balance:,.0f} USDT")
    print(f"⚡ 레버리지: {args.leverage}배")
    print(f"📅 기간: {args.start_year}년 ~ {args.end_year}년")
    print(f"📁 데이터 디렉토리: {args.data_dir}")
    print("=" * 80)
    
    # 봇 생성
    bot = AdvancedMAMLBotFast(initial_balance=args.balance, leverage=args.leverage)
    
    # 연속 백테스트 실행
    try:
        results = bot.run_continuous_backtest(args.start_year, args.end_year)
        
        if 'error' in results:
            print(f"❌ 백테스트 실패: {results['error']}")
            return
        
        # 결과 요약
        print("\n" + "=" * 80)
        print("🎯 최종 요약")
        print("=" * 80)
        print(f"📈 전체 수익률: {results['total_return']:.2f}%")
        print(f"📊 평균 연간 수익률: {results['avg_yearly_return']:.2f}%")
        print(f"📉 최대 낙폭: {results['max_drawdown']:.2f}%")
        print(f"📊 평균 샤프 비율: {results['avg_sharpe_ratio']:.2f}")
        print(f"📊 총 거래 횟수: {results['total_trades']:,}회")
        print(f"📊 평균 승률: {results['avg_win_rate']:.1f}%")
        print(f"📅 처리된 연도: {results['num_years']}개")
        
        # 연도별 수익률 분석
        print(f"\n📊 연도별 수익률 분석:")
        yearly_returns = [r['total_return'] for r in results['yearly_results']]
        positive_years = sum(1 for r in yearly_returns if r > 0)
        negative_years = sum(1 for r in yearly_returns if r < 0)
        
        print(f"   - 수익 연도: {positive_years}개")
        print(f"   - 손실 연도: {negative_years}개")
        print(f"   - 최고 수익률: {max(yearly_returns):.2f}%")
        print(f"   - 최저 수익률: {min(yearly_returns):.2f}%")
        
        # 연도별 수익률 차트 (간단한 텍스트)
        print(f"\n📈 연도별 수익률 차트:")
        max_return = max(yearly_returns)
        min_return = min(yearly_returns)
        range_return = max_return - min_return
        
        for result in results['yearly_results']:
            year = result['year']
            return_pct = result['total_return']
            
            # 간단한 막대 차트 (텍스트)
            if range_return > 0:
                bar_length = int((return_pct - min_return) / range_return * 50)
            else:
                bar_length = 25
            
            bar = "█" * max(0, bar_length) + "░" * max(0, 50 - bar_length)
            print(f"   {year}: {bar} {return_pct:>6.1f}%")
        
        print(f"\n✅ 연속 백테스트 완료!")
        
    except Exception as e:
        print(f"❌ 실행 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
