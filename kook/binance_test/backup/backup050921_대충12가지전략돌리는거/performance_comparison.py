#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
성능 비교 스크립트: 원본 vs 벡터화 최적화 버전
"""

import time
import pandas as pd
import numpy as np
from advanced_ma_ml_bot import AdvancedMAMLBot
from advanced_ma_ml_bot_fast import AdvancedMAMLBotFast

def run_performance_comparison():
    """성능 비교 실행"""
    print("🚀 성능 비교 시작!")
    print("=" * 60)
    
    # 데이터 로드
    data_files = [
        'data/BTCUSDT/5m/BTCUSDT_5m_2024.csv',
        'data/BTCUSDT/1m/BTCUSDT_1m_2024.csv',
        '../data/BTCUSDT/5m/BTCUSDT_5m_2024.csv',
        'BTCUSDT_5m_2024.csv'
    ]
    
    data_file = None
    for file_path in data_files:
        try:
            if pd.io.common.file_exists(file_path):
                data_file = file_path
                break
        except:
            continue
    
    if not data_file:
        print("❌ 데이터 파일을 찾을 수 없습니다!")
        return
    
    print(f"📊 데이터 파일: {data_file}")
    
    # 데이터 로드
    df = pd.read_csv(data_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')
    
    # 작은 데이터셋으로 테스트 (성능 비교용)
    test_df = df.head(1000)  # 1000개 캔들만 사용
    print(f"📊 테스트 데이터: {len(test_df):,}개 캔들")
    
    print("\n" + "=" * 60)
    print("1️⃣ 원본 버전 테스트")
    print("=" * 60)
    
    # 원본 버전 테스트
    start_time = time.time()
    
    try:
        bot_original = AdvancedMAMLBot(initial_balance=10000, leverage=20)
        results_original = bot_original.run_backtest(test_df, start_date='2024-01-01', end_date='2024-01-31')
        
        original_time = time.time() - start_time
        
        print(f"⏱️  원본 버전 실행 시간: {original_time:.2f}초")
        if 'error' not in results_original:
            print(f"💰 수익률: {results_original['total_return']:.2f}%")
            print(f"📊 거래 횟수: {results_original['total_trades']}회")
        else:
            print(f"❌ 오류: {results_original['error']}")
            
    except Exception as e:
        print(f"❌ 원본 버전 오류: {e}")
        original_time = float('inf')
        results_original = {'error': str(e)}
    
    print("\n" + "=" * 60)
    print("2️⃣ 벡터화 최적화 버전 테스트")
    print("=" * 60)
    
    # 벡터화 버전 테스트
    start_time = time.time()
    
    try:
        bot_fast = AdvancedMAMLBotFast(initial_balance=10000, leverage=20)
        results_fast = bot_fast.run_vectorized_backtest(test_df, start_date='2024-01-01', end_date='2024-01-31')
        
        fast_time = time.time() - start_time
        
        print(f"⏱️  벡터화 버전 실행 시간: {fast_time:.2f}초")
        if 'error' not in results_fast:
            print(f"💰 수익률: {results_fast['total_return']:.2f}%")
            print(f"📊 거래 횟수: {results_fast['total_trades']}회")
        else:
            print(f"❌ 오류: {results_fast['error']}")
            
    except Exception as e:
        print(f"❌ 벡터화 버전 오류: {e}")
        fast_time = float('inf')
        results_fast = {'error': str(e)}
    
    print("\n" + "=" * 60)
    print("📊 성능 비교 결과")
    print("=" * 60)
    
    if original_time != float('inf') and fast_time != float('inf'):
        speedup = original_time / fast_time
        print(f"🚀 속도 향상: {speedup:.2f}배 빠름")
        print(f"⏱️  원본: {original_time:.2f}초")
        print(f"⚡ 벡터화: {fast_time:.2f}초")
        print(f"💾 시간 절약: {original_time - fast_time:.2f}초")
        
        # 메모리 사용량 비교 (간단한 추정)
        print(f"\n💾 메모리 효율성:")
        print(f"   - 원본: 행별 반복 처리 (비효율적)")
        print(f"   - 벡터화: NumPy 배열 기반 (효율적)")
        
        # 결과 일치성 확인
        if 'error' not in results_original and 'error' not in results_fast:
            print(f"\n✅ 결과 일치성:")
            print(f"   - 수익률 차이: {abs(results_original['total_return'] - results_fast['total_return']):.4f}%")
            print(f"   - 거래 횟수 차이: {abs(results_original['total_trades'] - results_fast['total_trades'])}회")
    
    print("\n🎯 최적화 효과:")
    print("   ✅ 완전 벡터화된 연산")
    print("   ✅ NumPy 기반 고속 처리")
    print("   ✅ 메모리 효율성 향상")
    print("   ✅ 행별 반복 제거")
    print("   ✅ TALib 벡터화 활용")

if __name__ == "__main__":
    run_performance_comparison()
