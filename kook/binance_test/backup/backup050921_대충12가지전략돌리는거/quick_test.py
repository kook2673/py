#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
빠른 테스트용 스크립트
"""

import os
import pandas as pd
from advanced_ma_ml_bot import AdvancedMAMLBot

def main():
    print("🚀 빠른 테스트 시작!")
    
    # 데이터 파일 찾기
    data_files = [
        'data/BTCUSDT/5m/BTCUSDT_5m_2024.csv',
        'data/BTCUSDT/1m/BTCUSDT_1m_2024.csv',
        '../data/BTCUSDT/5m/BTCUSDT_5m_2024.csv',
        'BTCUSDT_5m_2024.csv'
    ]
    
    data_file = None
    for file_path in data_files:
        if os.path.exists(file_path):
            data_file = file_path
            break
    
    if not data_file:
        print("❌ 데이터 파일을 찾을 수 없습니다!")
        print("다음 경로 중 하나에 데이터 파일이 있는지 확인해주세요:")
        for path in data_files:
            print(f"  - {path}")
        return
    
    print(f"📊 데이터 파일: {data_file}")
    
    # 봇 생성
    bot = AdvancedMAMLBot(initial_balance=10000, leverage=20)
    
    try:
        # 데이터 로드
        print("📊 데이터 로드 중...")
        df = pd.read_csv(data_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        print(f"✅ 데이터 로드 완료: {len(df):,}개 캔들")
        
        # 백테스트 실행
        print("🔄 백테스트 실행 중...")
        results = bot.run_backtest(df, start_date='2024-01-01', end_date='2024-01-31')
        
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
