#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
고도화된 MA+ML 봇 실행 스크립트
"""

import os
import sys
import argparse
import pandas as pd
from advanced_ma_ml_bot import AdvancedMAMLBot

def main():
    parser = argparse.ArgumentParser(description='고도화된 MA+ML 자동매매봇 실행')
    parser.add_argument('--data', required=True, help='데이터 파일 경로')
    parser.add_argument('--start-date', default='2024-01-01', help='시작 날짜 (YYYY-MM-DD)')
    parser.add_argument('--end-date', default='2024-01-31', help='종료 날짜 (YYYY-MM-DD)')
    parser.add_argument('--balance', type=float, default=10000, help='초기 자본 (기본값: 10000)')
    parser.add_argument('--leverage', type=int, default=20, help='레버리지 (기본값: 20)')
    parser.add_argument('--sliding-window', action='store_true', help='슬라이딩 윈도우 백테스트 실행')
    parser.add_argument('--train-days', type=int, default=15, help='학습 기간 (일)')
    parser.add_argument('--test-days', type=int, default=15, help='테스트 기간 (일)')
    parser.add_argument('--auto-tune', action='store_true', help='파라미터 오토튜닝 실행')
    parser.add_argument('--tune-trials', type=int, default=50, help='튜닝 시도 횟수')
    
    args = parser.parse_args()
    
    # 데이터 파일 존재 확인
    if not os.path.exists(args.data):
        print(f"❌ 데이터 파일을 찾을 수 없습니다: {args.data}")
        return
    
    print("🚀 고도화된 MA+ML 자동매매봇 시작!")
    print("=" * 60)
    print(f"📊 데이터 파일: {args.data}")
    print(f"💰 초기 자본: {args.balance:,.0f} USDT")
    print(f"⚡ 레버리지: {args.leverage}배")
    print(f"📅 기간: {args.start_date} ~ {args.end_date}")
    print("=" * 60)
    
    # 봇 생성
    bot = AdvancedMAMLBot(initial_balance=args.balance, leverage=args.leverage)
    
    try:
        # 데이터 로드
        print("📊 데이터 로드 중...")
        df = pd.read_csv(args.data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        print(f"✅ 데이터 로드 완료: {len(df):,}개 캔들")
        
        if args.sliding_window:
            # 슬라이딩 윈도우 백테스트
            print(f"🔄 슬라이딩 윈도우 백테스트 실행...")
            print(f"   학습 기간: {args.train_days}일")
            print(f"   테스트 기간: {args.test_days}일")
            
            results = bot.run_sliding_window_backtest(
                df, 
                train_days=args.train_days,
                test_days=args.test_days,
                start_date=args.start_date,
                end_date=args.end_date
            )
            
            if 'error' in results:
                print(f"❌ 슬라이딩 윈도우 백테스트 실패: {results['error']}")
                return
            
            print("\n=== 슬라이딩 윈도우 백테스트 결과 ===")
            print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
            print(f"최종 자본: {results['final_balance']:,.0f} USDT")
            print(f"총 수익률: {results['total_return']:.2f}%")
            print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
            print(f"샤프 비율: {results['sharpe_ratio']:.2f}")
            print(f"승률: {results['win_rate']:.2f}%")
            print(f"수익 팩터: {results['profit_factor']:.2f}")
            print(f"총 거래 횟수: {results['total_trades']}회")
            print(f"기간 수: {results['num_periods']}개")
            
        else:
            # 일반 백테스트
            if args.auto_tune:
                print("🔧 파라미터 오토튜닝 실행...")
                tune_result = bot.auto_tune_parameters(df, n_trials=args.tune_trials)
                print(f"✅ 튜닝 완료: 최고 점수 {tune_result['best_score']:.4f}")
            
            print("🔄 백테스트 실행 중...")
            results = bot.run_backtest(df, start_date=args.start_date, end_date=args.end_date)
            
            if 'error' in results:
                print(f"❌ 백테스트 실패: {results['error']}")
                return
            
            print("\n=== 백테스트 결과 ===")
            print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
            print(f"최종 자본: {results['final_balance']:,.0f} USDT")
            print(f"총 수익률: {results['total_return']:.2f}%")
            print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
            print(f"샤프 비율: {results['sharpe_ratio']:.2f}")
            print(f"승률: {results['win_rate']:.2f}%")
            print(f"수익 팩터: {results['profit_factor']:.2f}")
            print(f"총 거래 횟수: {results['total_trades']}회")
        
        # 모델 저장
        print("\n💾 모델 저장 중...")
        bot.save_model()
        print("✅ 모델 저장 완료!")
        
    except Exception as e:
        print(f"❌ 실행 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
