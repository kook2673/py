#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
고도화된 이동평균선 + 머신러닝 봇 실행 스크립트
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

def load_data(start_date: str = '2023-01-01', end_date: str = '2024-12-31'):
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

def run_optimization_phase():
    """최적화 단계 실행"""
    logger.info("=== 1단계: 최적화 단계 ===")
    
    # 데이터 로드 (2023년 데이터)
    df = load_data('2023-01-01', '2023-12-31')
    
    # 봇 생성
    bot = AdvancedMAMLBot(initial_balance=10000, leverage=20)
    
    # 동적 포지션 사이즈 설정
    bot.base_position_size = 0.05      # 기본 포지션 사이즈
    bot.increased_position_size = 0.1  # 실패 시 포지션 사이즈
    bot.current_position_size = 0.05   # 현재 포지션 사이즈 초기화
    logger.info(f"동적 포지션 사이즈 설정: 기본={bot.base_position_size}, 증가={bot.increased_position_size}")
    
    # 파라미터 오토튜닝
    logger.info("파라미터 오토튜닝 시작...")
    tune_result = bot.auto_tune_parameters(df)
    logger.info(f"파라미터 튜닝 완료: {tune_result['best_score']:.4f}")
    
    # 머신러닝 모델 훈련
    logger.info("머신러닝 모델 훈련 시작...")
    train_result = bot.train_ml_model(df)
    logger.info(f"모델 훈련 완료: {train_result['model_name']}, CV Score: {train_result['cv_score']:.4f}")
    
    # 모델 저장
    bot.save_model('optimized_model.pkl')
    
    return bot

def run_live_trading_phase():
    """실제 거래 단계 실행"""
    logger.info("=== 2단계: 실제 거래 단계 ===")
    
    # 데이터 로드 (2024년 데이터)
    df = load_data('2024-01-01', '2024-12-31')
    
    # 최적화된 모델 로드
    bot = AdvancedMAMLBot(initial_balance=10000, leverage=20)
    
    # 동적 포지션 사이즈 설정
    bot.base_position_size = 0.05      # 기본 포지션 사이즈
    bot.increased_position_size = 0.1  # 실패 시 포지션 사이즈
    bot.current_position_size = 0.05   # 현재 포지션 사이즈 초기화
    logger.info(f"동적 포지션 사이즈 설정: 기본={bot.base_position_size}, 증가={bot.increased_position_size}")
    
    if not bot.load_model('optimized_model.pkl'):
        logger.error("최적화된 모델 로드 실패")
        return None
    
    # 백테스트 실행 (월별 재학습 포함)
    logger.info("백테스트 실행 (월별 재학습 포함)...")
    results = bot.run_backtest(df, start_date='2024-01-01', end_date='2024-12-31')
    
    return results

def run_quick_test():
    """빠른 테스트 실행 (올바른 학습/테스트 분리)"""
    logger.info("=== 빠른 테스트 실행 ===")
    
    # 학습 데이터 로드 (2024년 1월 1일~15일)
    train_df = load_data('2024-01-01', '2024-01-15')
    
    # 테스트 데이터 로드 (2024년 1월 16일~31일)
    test_df = load_data('2024-01-16', '2024-01-31')
    
    # 봇 생성
    bot = AdvancedMAMLBot(initial_balance=10000, leverage=20)
    
    # 동적 포지션 사이즈 설정
    bot.base_position_size = 0.05      # 기본 포지션 사이즈
    bot.increased_position_size = 0.1  # 실패 시 포지션 사이즈
    bot.current_position_size = 0.05   # 현재 포지션 사이즈 초기화
    logger.info(f"동적 포지션 사이즈 설정: 기본={bot.base_position_size}, 증가={bot.increased_position_size}")
    
    # 빠른 파라미터 튜닝 (적은 조합)
    logger.info("빠른 파라미터 튜닝...")
    bot.params['ma_short'] = 5
    bot.params['ma_long'] = 20
    bot.params['stop_loss_pct'] = 0.01
    bot.params['take_profit_pct'] = 0.03
    bot.params['trailing_stop_pct'] = 0.03  # 트레일링 스탑 2%
    bot.params['trailing_stop_activation_pct'] = 0.015  # 트레일링 스탑 활성화 1%
    bot.params['max_positions'] = 2
    
    # 머신러닝 모델 훈련 (학습 데이터만 사용)
    logger.info("머신러닝 모델 훈련 (1월 1일~15일 데이터)...")
    train_result = bot.train_ml_model(train_df)
    
    # 백테스트 실행 (테스트 데이터만 사용)
    logger.info("백테스트 실행 (1월 16일~31일 데이터)...")
    results = bot.run_backtest(test_df, start_date='2024-01-16', end_date='2024-01-31')
    
    return results

def run_sliding_window_test():
    """15일 단위 슬라이딩 윈도우 테스트 (1월~3월) - 간단 버전"""
    logger.info("=== 15일 단위 슬라이딩 윈도우 테스트 (간단 버전) ===")
    
    # 1월~3월 데이터 로드
    df = load_data('2024-01-01', '2024-03-31')
    
    # 전체 결과 저장
    all_results = []
    all_trades = []
    total_balance = 10000
    
    # 날짜 범위 생성
    current_date = pd.to_datetime('2024-01-01')
    end_date = pd.to_datetime('2024-03-31')
    
    period_count = 0
    
    while current_date < end_date:
        period_count += 1
        
        # 학습 기간 설정 (15일)
        train_start = current_date
        train_end = current_date + pd.Timedelta(days=14)
        
        # 테스트 기간 설정 (15일)
        test_start = train_end + pd.Timedelta(days=1)
        test_end = test_start + pd.Timedelta(days=14)
        
        # 테스트 기간이 종료일을 넘으면 조정
        if test_end > end_date:
            test_end = end_date
        
        # 데이터가 충분한지 확인
        if test_end <= test_start:
            break
            
        logger.info(f"\n=== 기간 {period_count} ===")
        logger.info(f"학습: {train_start.strftime('%Y-%m-%d')} ~ {train_end.strftime('%Y-%m-%d')}")
        logger.info(f"테스트: {test_start.strftime('%Y-%m-%d')} ~ {test_end.strftime('%Y-%m-%d')}")
        
        # 학습 데이터 추출
        train_df = df[(df.index >= train_start) & (df.index <= train_end)]
        test_df = df[(df.index >= test_start) & (df.index <= test_end)]
        
        if len(train_df) < 100 or len(test_df) < 50:
            logger.warning(f"기간 {period_count}: 데이터 부족으로 건너뜀")
            current_date = test_end + pd.Timedelta(days=1)
            continue
        
        # 봇 생성 (각 기간마다 새로운 봇)
        period_bot = AdvancedMAMLBot(initial_balance=total_balance, leverage=20)
        period_bot.base_position_size = 0.05
        period_bot.increased_position_size = 0.1
        period_bot.current_position_size = 0.05
        
        # 기본 파라미터 설정 (더 관대한 설정)
        period_bot.params['ma_short'] = 5
        period_bot.params['ma_long'] = 20
        period_bot.params['stop_loss_pct'] = 0.01
        period_bot.params['take_profit_pct'] = 0.03
        period_bot.params['trailing_stop_pct'] = 0.03
        period_bot.params['trailing_stop_activation_pct'] = 0.015
        period_bot.params['max_positions'] = 2
        
        # 월별 재학습 비활성화
        period_bot.last_retrain_date = None
        
        try:
            # 학습 데이터로 모델 훈련
            logger.info(f"기간 {period_count}: 모델 훈련 중...")
            train_result = period_bot.train_ml_model(train_df)
            
            if 'error' in train_result:
                logger.error(f"기간 {period_count}: 모델 훈련 실패")
                current_date = test_end + pd.Timedelta(days=1)
                continue
            
            # 신호 생성 테스트
            logger.info(f"기간 {period_count}: 신호 생성 테스트...")
            df_features, features = period_bot.create_features(test_df)
            
            # 여러 시점에서 신호 확인
            for i in range(min(5, len(df_features))):
                test_signal = period_bot.generate_signal(df_features.iloc[:i+100], features)
                logger.info(f"기간 {period_count}: 시점 {i} 신호 - {test_signal}")
            
            # 테스트 데이터로 백테스트 실행
            logger.info(f"기간 {period_count}: 백테스트 실행 중...")
            test_result = period_bot.run_backtest(test_df, 
                                                start_date=test_start.strftime('%Y-%m-%d'),
                                                end_date=test_end.strftime('%Y-%m-%d'))
            
            if 'error' in test_result:
                logger.error(f"기간 {period_count}: 백테스트 실패 - {test_result['error']}")
                current_date = test_end + pd.Timedelta(days=1)
                continue
            
            # 결과 저장
            period_result = {
                'period': period_count,
                'train_start': train_start.strftime('%Y-%m-%d'),
                'train_end': train_end.strftime('%Y-%m-%d'),
                'test_start': test_start.strftime('%Y-%m-%d'),
                'test_end': test_end.strftime('%Y-%m-%d'),
                'initial_balance': test_result['initial_balance'],
                'final_balance': test_result['final_balance'],
                'total_return': test_result['total_return'],
                'max_drawdown': test_result['max_drawdown'],
                'sharpe_ratio': test_result['sharpe_ratio'],
                'win_rate': test_result['win_rate'],
                'profit_factor': test_result['profit_factor'],
                'total_trades': test_result['total_trades'],
                'trades': test_result['trades']
            }
            
            all_results.append(period_result)
            all_trades.extend(test_result['trades'])
            
            # 다음 기간을 위한 잔고 업데이트
            total_balance = test_result['final_balance']
            
            logger.info(f"기간 {period_count} 결과: 수익률 {test_result['total_return']:.2f}%, "
                       f"거래 {test_result['total_trades']}회, 승률 {test_result['win_rate']:.2f}%")
            
        except Exception as e:
            logger.error(f"기간 {period_count}: 오류 발생 - {e}")
        
        # 다음 기간으로 이동
        current_date = test_end + pd.Timedelta(days=1)
    
    # 전체 결과 집계
    if not all_results:
        return {"error": "유효한 백테스트 결과가 없습니다."}
    
    # 전체 통계 계산
    total_pnl = total_balance - 10000
    total_return = (total_pnl / 10000) * 100
    
    # 최대 낙폭 계산
    peak = 10000
    max_dd = 0
    for result in all_results:
        if result['final_balance'] > peak:
            peak = result['final_balance']
        dd = (peak - result['final_balance']) / peak * 100
        max_dd = max(max_dd, dd)
    
    # 승률 계산
    total_trades = sum(r['total_trades'] for r in all_results)
    winning_trades = sum(1 for trade in all_trades if trade['pnl'] > 0)
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # 수익 팩터 계산
    winning_trades_pnl = [t['pnl'] for t in all_trades if t['pnl'] > 0]
    losing_trades_pnl = [t['pnl'] for t in all_trades if t['pnl'] < 0]
    avg_win = np.mean(winning_trades_pnl) if winning_trades_pnl else 0
    avg_loss = np.mean(losing_trades_pnl) if losing_trades_pnl else 0
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
    
    # 샤프 비율 계산
    returns = [r['total_return'] for r in all_results]
    sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if returns and np.std(returns) > 0 else 0
    
    return {
        "initial_balance": 10000,
        "final_balance": total_balance,
        "total_pnl": total_pnl,
        "total_return": total_return,
        "max_drawdown": max_dd,
        "sharpe_ratio": sharpe_ratio,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": total_trades - winning_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "trades": all_trades,
        "period_results": all_results,
        "num_periods": len(all_results)
    }

def main():
    """메인 실행 함수"""
    print("=== 고도화된 이동평균선 + 머신러닝 봇 ===")
    print("1. 이동평균선 2개 기반 신호 트리거")
    print("2. 21가지 보조지표 머신러닝 피처")
    print("3. 파라미터 오토튜닝")
    print("4. 드리프트 모니터링 및 리파인")
    print("5. 월별 자동 재학습")
    print("6. 슬리피지, 펀딩비 반영 백테스트")
    print("7. 스탑로스 시스템")
    print("8. 동적 포지션 사이즈 시스템 (기본 0.05, 실패시 0.1, 성공시 0.05 복원)")
    print("9. 15일 단위 슬라이딩 윈도우 테스트 (1월~3월)")
    print()
    
    try:
        # 실행 모드 선택
        mode = input("실행 모드를 선택하세요 (1: 전체 최적화, 2: 빠른 테스트, 3: 슬라이딩 윈도우): ").strip()
        
        if mode == "1":
            # 전체 최적화 실행
            logger.info("전체 최적화 모드 선택")
            
            # 1단계: 최적화
            bot = run_optimization_phase()
            
            # 2단계: 실제 거래
            results = run_live_trading_phase()
            
            if results:
                print("\n=== 최종 결과 ===")
                print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
                print(f"최종 자본: {results['final_balance']:,.0f} USDT")
                print(f"총 수익률: {results['total_return']:.2f}%")
                print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
                print(f"샤프 비율: {results['sharpe_ratio']:.2f}")
                print(f"승률: {results['win_rate']:.2f}%")
                print(f"수익 팩터: {results['profit_factor']:.2f}")
                print(f"총 거래 횟수: {results['total_trades']}회")
                print(f"동적 포지션 사이즈: 기본={bot.base_position_size}, 증가={bot.increased_position_size}")
                
                # 거래 분석
                if results['trades']:
                    print(f"\n=== 거래 분석 ===")
                    reasons = {}
                    for trade in results['trades']:
                        reason = trade.get('reason', 'unknown')
                        reasons[reason] = reasons.get(reason, 0) + 1
                    
                    # 한글 표시 매핑
                    reason_names = {
                        'stop_loss': '스탑로스',
                        'take_profit': '익절',
                        'trailing_stop': '트레일링 스탑',
                        'signal': '신호',
                        'unknown': '기타'
                    }
                    
                    for reason, count in reasons.items():
                        display_name = reason_names.get(reason, reason)
                        print(f"{display_name}: {count}회")
        
        elif mode == "2":
            # 빠른 테스트 실행
            logger.info("빠른 테스트 모드 선택")
            
            results = run_quick_test()
            
            if results:
                print("\n=== 빠른 테스트 결과 ===")
                print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
                print(f"최종 자본: {results['final_balance']:,.0f} USDT")
                print(f"총 수익률: {results['total_return']:.2f}%")
                print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
                print(f"샤프 비율: {results['sharpe_ratio']:.2f}")
                print(f"승률: {results['win_rate']:.2f}%")
                print(f"수익 팩터: {results['profit_factor']:.2f}")
                print(f"총 거래 횟수: {results['total_trades']}회")
                print(f"동적 포지션 사이즈: 기본=0.05, 증가=0.1")
                
                # 거래 분석
                if results['trades']:
                    print(f"\n=== 거래 분석 ===")
                    reasons = {}
                    for trade in results['trades']:
                        reason = trade.get('reason', 'unknown')
                        reasons[reason] = reasons.get(reason, 0) + 1
                    
                    # 한글 표시 매핑
                    reason_names = {
                        'stop_loss': '스탑로스',
                        'take_profit': '익절',
                        'trailing_stop': '트레일링 스탑',
                        'signal': '신호',
                        'unknown': '기타'
                    }
                    
                    for reason, count in reasons.items():
                        display_name = reason_names.get(reason, reason)
                        print(f"{display_name}: {count}회")
        
        elif mode == "3":
            # 슬라이딩 윈도우 테스트 실행
            logger.info("슬라이딩 윈도우 테스트 모드 선택")
            
            results = run_sliding_window_test()
            
            if results and 'error' not in results:
                print("\n=== 슬라이딩 윈도우 테스트 결과 ===")
                print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
                print(f"최종 자본: {results['final_balance']:,.0f} USDT")
                print(f"총 수익률: {results['total_return']:.2f}%")
                print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
                print(f"샤프 비율: {results['sharpe_ratio']:.2f}")
                print(f"승률: {results['win_rate']:.2f}%")
                print(f"수익 팩터: {results['profit_factor']:.2f}")
                print(f"총 거래 횟수: {results['total_trades']}회")
                print(f"테스트 기간 수: {results['num_periods']}개")
                print(f"동적 포지션 사이즈: 기본=0.05, 증가=0.1")
                
                # 기간별 결과 분석
                if 'period_results' in results and results['period_results']:
                    print(f"\n=== 기간별 결과 분석 ===")
                    period_returns = [p['total_return'] for p in results['period_results']]
                    positive_periods = sum(1 for r in period_returns if r > 0)
                    negative_periods = sum(1 for r in period_returns if r < 0)
                    
                    print(f"수익 기간: {positive_periods}개")
                    print(f"손실 기간: {negative_periods}개")
                    print(f"평균 기간 수익률: {np.mean(period_returns):.2f}%")
                    print(f"최고 기간 수익률: {max(period_returns):.2f}%")
                    print(f"최저 기간 수익률: {min(period_returns):.2f}%")
                    
                    # 기간별 상세 결과
                    print(f"\n=== 기간별 상세 결과 ===")
                    for i, period in enumerate(results['period_results'][:10]):  # 처음 10개 기간만 표시
                        print(f"기간 {period['period']}: {period['test_start']} ~ {period['test_end']} | "
                              f"수익률: {period['total_return']:.2f}% | 거래: {period['total_trades']}회 | "
                              f"승률: {period['win_rate']:.2f}%")
                    
                    if len(results['period_results']) > 10:
                        print(f"... (총 {len(results['period_results'])}개 기간 중 10개만 표시)")
                
                # 거래 분석
                if results['trades']:
                    print(f"\n=== 거래 분석 ===")
                    reasons = {}
                    for trade in results['trades']:
                        reason = trade.get('reason', 'unknown')
                        reasons[reason] = reasons.get(reason, 0) + 1
                    
                    # 한글 표시 매핑
                    reason_names = {
                        'stop_loss': '스탑로스',
                        'take_profit': '익절',
                        'trailing_stop': '트레일링 스탑',
                        'signal': '신호',
                        'unknown': '기타'
                    }
                    
                    for reason, count in reasons.items():
                        display_name = reason_names.get(reason, reason)
                        print(f"{display_name}: {count}회")
            else:
                print("슬라이딩 윈도우 테스트 실행 실패")
                if results and 'error' in results:
                    print(f"오류: {results['error']}")
        
        else:
            print("잘못된 모드 선택입니다.")
            return
        
        print("\n실행 완료!")
        
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
