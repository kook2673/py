#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
안전한 테스트 스크립트 - 보수적인 설정으로 테스트
"""

import sys
import os
import pandas as pd
import numpy as np
import datetime as dt
from advanced_ma_ml_bot import AdvancedMAMLBot
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_data(start_date: str = '2024-01-01', end_date: str = '2024-01-31'):
    """데이터 로드"""
    data_path = r'c:\work\GitHub\py\kook\binance\data\BTC_USDT\1m'
    
    all_data = []
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    # 월별 파일 로드
    current_date = start_dt
    while current_date <= end_dt:
        year = current_date.year
        month = current_date.month
        
        # 파일 경로 생성
        file_pattern = os.path.join(data_path, f"{year}-{month:02d}.csv")
        
        if os.path.exists(file_pattern):
            try:
                df = pd.read_csv(file_pattern)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.set_index('timestamp')
                all_data.append(df)
                logger.info(f"로드 완료: {year}-{month:02d} ({len(df)}개 데이터)")
            except Exception as e:
                logger.error(f"파일 로드 실패: {file_pattern} - {e}")
        else:
            logger.warning(f"파일 없음: {file_pattern}")
        
        # 다음 달로 이동
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)
    
    if not all_data:
        raise ValueError("로드된 데이터가 없습니다.")
    
    # 모든 데이터 합치기
    combined_df = pd.concat(all_data, ignore_index=False)
    combined_df = combined_df.sort_index()
    
    # 중복 제거
    combined_df = combined_df[~combined_df.index.duplicated(keep='first')]
    
    logger.info(f"총 데이터 로드 완료: {len(combined_df)}개 데이터 포인트")
    logger.info(f"데이터 기간: {combined_df.index[0]} ~ {combined_df.index[-1]}")
    
    return combined_df

def run_safe_test():
    """안전한 테스트 실행"""
    logger.info("=== 안전한 테스트 실행 ===")
    
    # 데이터 로드 (2024년 1월만)
    df = load_data('2024-01-01', '2024-01-31')
    
    # 봇 생성 (보수적인 설정)
    bot = AdvancedMAMLBot(initial_balance=10000, leverage=10)  # 레버리지 10배로 줄임
    
    # 보수적인 파라미터 설정
    bot.params.update({
        'ma_short': 10,           # 단기 이동평균 10으로 증가
        'ma_long': 30,            # 장기 이동평균 30으로 증가
        'position_size': 0.02,    # 포지션 크기 2%로 대폭 줄임
        'stop_loss_pct': 0.01,    # 스탑로스 1%로 줄임
        'take_profit_pct': 0.02,  # 익절 2%로 줄임
        'max_positions': 1,       # 최대 포지션 1개로 제한
    })
    
    logger.info("보수적인 파라미터 설정:")
    logger.info(f"  - 레버리지: {bot.leverage}배")
    logger.info(f"  - 포지션 크기: {bot.params['position_size']*100}%")
    logger.info(f"  - 스탑로스: {bot.params['stop_loss_pct']*100}%")
    logger.info(f"  - 익절: {bot.params['take_profit_pct']*100}%")
    logger.info(f"  - 최대 포지션: {bot.params['max_positions']}개")
    
    # 머신러닝 모델 훈련
    logger.info("머신러닝 모델 훈련...")
    train_result = bot.train_ml_model(df)
    
    if 'error' in train_result:
        logger.error(f"모델 훈련 실패: {train_result['error']}")
        return None
    
    logger.info(f"모델 훈련 완료: {train_result['model_name']}, CV Score: {train_result['cv_score']:.4f}")
    
    # 백테스트 실행
    logger.info("백테스트 실행...")
    results = bot.run_backtest(df, start_date='2024-01-01', end_date='2024-01-31')
    
    return results

def main():
    """메인 실행 함수"""
    print("=== 안전한 테스트 실행 ===")
    print("보수적인 설정으로 리스크를 최소화하여 테스트합니다.")
    print()
    
    try:
        results = run_safe_test()
        
        if results:
            print("\n=== 안전한 테스트 결과 ===")
            print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
            print(f"최종 자본: {results['final_balance']:,.0f} USDT")
            print(f"총 수익률: {results['total_return']:.2f}%")
            print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
            print(f"샤프 비율: {results['sharpe_ratio']:.2f}")
            print(f"승률: {results['win_rate']:.2f}%")
            print(f"수익 팩터: {results['profit_factor']:.2f}")
            print(f"총 거래 횟수: {results['total_trades']}회")
            
            # 거래 분석
            if results['trades']:
                print(f"\n=== 거래 분석 ===")
                reasons = {}
                for trade in results['trades']:
                    reason = trade.get('reason', 'unknown')
                    reasons[reason] = reasons.get(reason, 0) + 1
                
                for reason, count in reasons.items():
                    print(f"{reason}: {count}회")
                
                # 수익/손실 거래 분석
                winning_trades = [t for t in results['trades'] if t['pnl'] > 0]
                losing_trades = [t for t in results['trades'] if t['pnl'] < 0]
                
                if winning_trades:
                    avg_win = np.mean([t['pnl'] for t in winning_trades])
                    max_win = max([t['pnl'] for t in winning_trades])
                    print(f"\n수익 거래: {len(winning_trades)}회, 평균: {avg_win:.2f} USDT, 최대: {max_win:.2f} USDT")
                
                if losing_trades:
                    avg_loss = np.mean([t['pnl'] for t in losing_trades])
                    max_loss = min([t['pnl'] for t in losing_trades])
                    print(f"손실 거래: {len(losing_trades)}회, 평균: {avg_loss:.2f} USDT, 최대: {max_loss:.2f} USDT")
        
        print("\n안전한 테스트 완료!")
        
    except Exception as e:
        logger.error(f"테스트 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
