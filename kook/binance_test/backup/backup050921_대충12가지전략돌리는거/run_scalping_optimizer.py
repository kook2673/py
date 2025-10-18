#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
스켈핑 최적화 도구 실행 스크립트
- 백테스트 실행
- 실시간 모니터링
- 결과 분석
"""

import sys
import os
import argparse
import time
from scalping_optimizer import ScalpingOptimizer, ScalpingParams
from scalping_monitor import ScalpingMonitor

def run_backtest():
    """백테스트 실행"""
    print("🚀 스켈핑 백테스트 시작")
    print("=" * 60)
    
    # 최적화 도구 생성
    optimizer = ScalpingOptimizer(initial_balance=10000)
    
    # 데이터 파일 찾기
    data_files = [
        "data/BTCUSDT/5m/BTCUSDT_5m_2024.csv",
        "data/BTCUSDT/1m/BTCUSDT_1m_2024.csv",
        "../data/BTCUSDT/5m/BTCUSDT_5m_2024.csv",
        "BTCUSDT_5m_2024.csv"
    ]
    
    df = None
    for data_file in data_files:
        if os.path.exists(data_file):
            df = optimizer.load_data(data_file)
            if df is not None:
                print(f"✅ 데이터 로드 완료: {data_file}")
                break
    
    if df is None:
        print("❌ 데이터 파일을 찾을 수 없습니다.")
        return
    
    # 데이터 샘플링 (빠른 테스트)
    if len(df) > 20000:
        df = df.iloc[::len(df)//20000].copy()
        print(f"📊 데이터 샘플링: {len(df):,}개 캔들")
    
    # 파라미터 최적화
    print("\n🔍 파라미터 최적화 중...")
    optimal_params = optimizer.optimize_parameters(df)
    
    print(f"✅ 최적 파라미터:")
    print(f"   목표 수익: {optimal_params.target_profit*100:.1f}%")
    print(f"   최대 수익: {optimal_params.max_profit*100:.1f}%")
    print(f"   손절: {optimal_params.stop_loss*100:.1f}%")
    print(f"   포지션 크기: {optimal_params.position_size*100:.1f}%")
    print(f"   분할 비율: {optimal_params.split_ratio}")
    
    # 최적화된 파라미터로 백테스트 실행
    print("\n📊 최적화된 백테스트 실행 중...")
    results = optimizer.execute_split_scalping(df, optimal_params)
    
    # 결과 출력
    print("\n" + "=" * 60)
    print("📈 스켈핑 백테스트 결과 (1배 기준 0.3~0.5% 수익률)")
    print("=" * 60)
    print(f"총 수익률: {results.get('total_return', 0):.2f}%")
    print(f"총 거래: {results.get('total_trades', 0):,}회")
    print(f"승률: {results.get('win_rate', 0):.1f}%")
    print(f"평균 수익: ${results.get('avg_win', 0):.2f}")
    print(f"평균 손실: ${results.get('avg_loss', 0):.2f}")
    print(f"수익 팩터: {results.get('profit_factor', 0):.2f}")
    print(f"최대 낙폭: {results.get('max_drawdown', 0):.2f}%")
    print(f"최종 자본: ${results.get('final_balance', 0):,.2f}")
    print("-" * 60)
    print("📊 분할매매 분석")
    print("-" * 60)
    print(f"일일 승률: {results.get('daily_win_rate', 0):.1f}%")
    print(f"수익 일수: {results.get('profitable_days', 0)}일")
    print(f"총 거래 일수: {results.get('total_days', 0)}일")
    print("=" * 60)
    
    # 차트 생성
    optimizer.plot_results(results, "scalping_optimizer_results.png")
    
    # 결과 저장
    optimizer.save_results(results, "scalping_optimizer_results.json")
    
    print("✅ 백테스트 완료!")

def run_monitor():
    """실시간 모니터링 실행"""
    print("🚀 스켈핑 실시간 모니터링 시작")
    print("=" * 60)
    
    # 모니터 생성
    monitor = ScalpingMonitor(initial_balance=10000)
    
    # 모니터링 시작
    monitor.start_monitoring(symbol="BTCUSDT", interval=60)
    
    try:
        # 상태 모니터링 루프
        while True:
            time.sleep(30)  # 30초마다 상태 출력
            monitor.print_status()
            
    except KeyboardInterrupt:
        print("\n🛑 사용자에 의해 중지됨")
        monitor.stop_monitoring()
        
        # 최종 결과 저장
        monitor.save_results("scalping_monitor_results.json")
        
        print("📊 최종 성과:")
        final_performance = monitor.get_performance_summary()
        print(f"최종 자본: ${final_performance.get('current_balance', 0):,.2f}")
        print(f"총 수익률: {final_performance.get('total_return', 0):.2f}%")
        print(f"총 거래: {final_performance.get('total_trades', 0)}회")
        print(f"승률: {final_performance.get('win_rate', 0):.1f}%")
        
        print("✅ 모니터링 완료!")

def run_quick_test():
    """빠른 테스트 실행"""
    print("🚀 스켈핑 빠른 테스트 시작")
    print("=" * 60)
    
    # 기본 파라미터로 테스트
    params = ScalpingParams(
        target_profit=0.003,  # 0.3%
        max_profit=0.005,     # 0.5%
        stop_loss=0.001,      # 0.1%
        position_size=0.1,    # 10%
        split_ratio=[0.4, 0.4, 0.2]
    )
    
    # 최적화 도구 생성
    optimizer = ScalpingOptimizer(initial_balance=10000)
    
    # 데이터 파일 찾기
    data_files = [
        "data/BTCUSDT/5m/BTCUSDT_5m_2024.csv",
        "data/BTCUSDT/1m/BTCUSDT_1m_2024.csv",
        "../data/BTCUSDT/5m/BTCUSDT_5m_2024.csv",
        "BTCUSDT_5m_2024.csv"
    ]
    
    df = None
    for data_file in data_files:
        if os.path.exists(data_file):
            df = optimizer.load_data(data_file)
            if df is not None:
                print(f"✅ 데이터 로드 완료: {data_file}")
                break
    
    if df is None:
        print("❌ 데이터 파일을 찾을 수 없습니다.")
        return
    
    # 데이터 샘플링 (빠른 테스트)
    if len(df) > 10000:
        df = df.iloc[::len(df)//10000].copy()
        print(f"📊 데이터 샘플링: {len(df):,}개 캔들")
    
    # 백테스트 실행
    print("\n📊 빠른 백테스트 실행 중...")
    results = optimizer.execute_split_scalping(df, params)
    
    # 결과 출력
    print("\n" + "=" * 60)
    print("📈 빠른 테스트 결과")
    print("=" * 60)
    print(f"총 수익률: {results.get('total_return', 0):.2f}%")
    print(f"총 거래: {results.get('total_trades', 0):,}회")
    print(f"승률: {results.get('win_rate', 0):.1f}%")
    print(f"평균 수익: ${results.get('avg_win', 0):.2f}")
    print(f"평균 손실: ${results.get('avg_loss', 0):.2f}")
    print(f"수익 팩터: {results.get('profit_factor', 0):.2f}")
    print(f"최대 낙폭: {results.get('max_drawdown', 0):.2f}%")
    print(f"최종 자본: ${results.get('final_balance', 0):,.2f}")
    print("=" * 60)
    
    # 결과 저장
    optimizer.save_results(results, "scalping_quick_test_results.json")
    
    print("✅ 빠른 테스트 완료!")

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='스켈핑 최적화 도구')
    parser.add_argument('mode', choices=['backtest', 'monitor', 'quick'], 
                       help='실행 모드: backtest(백테스트), monitor(실시간모니터링), quick(빠른테스트)')
    
    args = parser.parse_args()
    
    if args.mode == 'backtest':
        run_backtest()
    elif args.mode == 'monitor':
        run_monitor()
    elif args.mode == 'quick':
        run_quick_test()

if __name__ == "__main__":
    main()
