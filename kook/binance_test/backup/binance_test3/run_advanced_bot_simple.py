#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
간단한 슬라이딩 윈도우 테스트 - 원래 로직 사용
"""

import sys
import os
import pandas as pd
import numpy as np
import datetime as dt
from advanced_ma_ml_bot import AdvancedMAMLBot
import logging
import joblib
import json
from typing import Dict, List, Optional

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
        
        # 다음 달로 이동 (안전한 방법)
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
        else:
            # 다음 달의 1일로 이동하여 날짜 범위 오류 방지
            try:
                current_date = current_date.replace(month=current_date.month + 1, day=1)
            except ValueError:
                # 해당 월의 마지막 날로 이동
                import calendar
                last_day = calendar.monthrange(current_date.year, current_date.month + 1)[1]
                current_date = current_date.replace(month=current_date.month + 1, day=last_day)
    
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

class TrainedModelLoader:
    """훈련된 모델 로더 클래스"""
    def __init__(self, models_dir="models"):
        self.models_dir = models_dir
        self.model_cache = {}
        self.model_info_cache = {}
    
    def load_model(self, model_name: str) -> Optional[Dict]:
        """훈련된 모델과 스케일러 로드"""
        if model_name in self.model_cache:
            return self.model_cache[model_name]
        
        # 모델 파일 경로 찾기
        model_file = self._find_model_file(model_name)
        if not model_file:
            logger.warning(f"❌ {model_name} 모델 파일을 찾을 수 없습니다.")
            return None
        
        try:
            # 모델 로드
            model = joblib.load(model_file)
            
            # 스케일러 파일도 찾아서 로드
            scaler_file = model_file.replace('ml_model_', 'scaler_')
            scaler = None
            if os.path.exists(scaler_file):
                scaler = joblib.load(scaler_file)
                logger.info(f"✅ {model_name} 스케일러 로드 완료")
            else:
                logger.warning(f"⚠️ {model_name} 스케일러 파일을 찾을 수 없습니다: {scaler_file}")
            
            # 모델 정보도 로드
            info_file = model_file.replace('.joblib', '.json')
            model_info = None
            if os.path.exists(info_file):
                with open(info_file, 'r', encoding='utf-8') as f:
                    model_info = json.load(f)
                self.model_info_cache[model_name] = model_info
            
            # 모델과 스케일러를 딕셔너리로 반환
            result = {
                'model': model,
                'scaler': scaler,
                'model_info': model_info
            }
            
            self.model_cache[model_name] = result
            logger.info(f"✅ {model_name} 모델 로드 완료")
            return result
            
        except Exception as e:
            logger.error(f"❌ {model_name} 모델 로드 실패: {e}")
            return None
    
    def _find_model_file(self, model_name: str) -> Optional[str]:
        """모델 파일 경로 찾기"""
        if not os.path.exists(self.models_dir):
            return None
        
        # 모델 파일 패턴 매칭 (ml_model_ 접두사 포함)
        for file in os.listdir(self.models_dir):
            if file == f"ml_model_{model_name}.joblib":
                return os.path.join(self.models_dir, file)
        return None
    
    def get_model_info(self, model_name: str) -> Optional[Dict]:
        """모델 정보 조회"""
        return self.model_info_cache.get(model_name)
    
    def list_available_models(self) -> List[str]:
        """사용 가능한 모델 목록 조회"""
        if not os.path.exists(self.models_dir):
            logger.warning(f"모델 디렉토리가 존재하지 않습니다: {self.models_dir}")
            return []
        
        models = []
        all_files = os.listdir(self.models_dir)
        logger.info(f"모델 디렉토리 파일들: {all_files}")
        
        for file in all_files:
            if file.startswith("ml_model_") and file.endswith('.joblib'):
                # 파일명에서 기간 추출 (ml_model_ 접두사 제거)
                period = file.replace("ml_model_", "").replace(".joblib", "")
                models.append(period)
                logger.info(f"모델 발견: {file} -> {period}")
        
        logger.info(f"최종 모델 목록: {sorted(models)}")
        return sorted(models)

def run_sliding_window_test():
    """15일 단위 슬라이딩 윈도우 테스트 (1월~3월) - 기존 모델 로드 사용"""
    logger.info("=== 15일 단위 슬라이딩 윈도우 테스트 (기존 모델 로드) ===")
    
    # 모델 로더 초기화 (절대 경로로 models 디렉토리 지정)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    models_path = os.path.join(current_dir, "models")
    model_loader = TrainedModelLoader(models_dir=models_path)
    logger.info(f"모델 디렉토리: {models_path}")
    
    # 사용 가능한 모델 목록 확인
    available_models = model_loader.list_available_models()
    logger.info(f"사용 가능한 모델: {available_models}")
    
    # 모델 파일 직접 확인
    models_dir = "models"
    if os.path.exists(models_dir):
        all_files = os.listdir(models_dir)
        model_files = [f for f in all_files if f.startswith("ml_model_") and f.endswith('.joblib')]
        logger.info(f"실제 모델 파일들: {model_files}")
    
    # 전체 결과 저장
    all_results = []
    all_trades = []
    total_balance = 10000
    
    # 기간별 테스트 (15일 단위 슬라이딩 윈도우) - 모델 파일명 직접 지정
    test_periods = [
        {
            'name': '기간 1',
            'train_start': '2024-01-01',
            'train_end': '2024-01-15',
            'test_start': '2024-01-16',
            'test_end': '2024-01-30',
            'model_name': '2024-01-01_2024-01-15'
        },
        {
            'name': '기간 2',
            'train_start': '2024-01-16',
            'train_end': '2024-01-30',
            'test_start': '2024-01-31',
            'test_end': '2024-02-14',
            'model_name': '2024-01-16_2024-01-30'
        },
        {
            'name': '기간 3',
            'train_start': '2024-01-31',
            'train_end': '2024-02-14',
            'test_start': '2024-02-15',
            'test_end': '2024-02-28',
            'model_name': '2024-01-31_2024-02-14'
        },
        {
            'name': '기간 4',
            'train_start': '2024-02-15',
            'train_end': '2024-02-28',
            'test_start': '2024-03-01',
            'test_end': '2024-03-15',
            'model_name': '2024-02-15_2024-02-28'  # 가장 가까운 모델 사용
        },
        {
            'name': '기간 5',
            'train_start': '2024-03-01',
            'train_end': '2024-03-15',
            'test_start': '2024-03-16',
            'test_end': '2024-03-31',
            'model_name': '2024-03-01_2024-03-15'  # 가장 가까운 모델 사용
        }
    ]
    
    for period in test_periods:
        logger.info(f"\n=== {period['name']} ===")
        logger.info(f"학습: {period['train_start']} ~ {period['train_end']}")
        logger.info(f"테스트: {period['test_start']} ~ {period['test_end']}")
        
        try:
            # 학습 데이터 로드
            train_df = load_data(period['train_start'], period['train_end'])
            # 테스트 데이터 로드
            test_df = load_data(period['test_start'], period['test_end'])
            
            # 봇 생성 (원래 run_quick_test 방식)
            bot = AdvancedMAMLBot(initial_balance=total_balance, leverage=20)
            
            # 동적 포지션 사이즈 설정
            bot.base_position_size = 0.05
            bot.increased_position_size = 0.1
            bot.current_position_size = 0.05
            
            # 기본 파라미터 설정 (더 보수적)
            bot.params['ma_short'] = 5
            bot.params['ma_long'] = 20
            bot.params['stop_loss_pct'] = 0.001
            bot.params['take_profit_pct'] = 0.003
            bot.params['trailing_stop_pct'] = 0.001
            bot.params['trailing_stop_activation_pct'] = 0.003
            bot.params['max_positions'] = 1  # 최대 포지션 수를 1개로 제한
            
            # 지정된 모델명으로 직접 로드
            model_name = period['model_name']
            logger.info(f"{period['name']}: 모델 로드 시도 - {model_name}")
            
            model_data = model_loader.load_model(model_name)
            
            if model_data is not None:
                # 모델과 스케일러를 봇에 설정
                bot.ml_model = model_data['model']
                bot.scaler = model_data['scaler']
                
                model_info = model_data.get('model_info')
                if model_info:
                    logger.info(f"{period['name']}: 모델 정보 - {model_info.get('model_name', 'Unknown')}")
                    logger.info(f"{period['name']}: 훈련일 - {model_info.get('train_date', 'Unknown')}")
                
                logger.info(f"{period['name']}: 모델 로드 성공 - {type(bot.ml_model).__name__}")
                if bot.scaler is not None:
                    logger.info(f"{period['name']}: 스케일러 로드 성공 - {type(bot.scaler).__name__}")
            else:
                # 모델이 없으면 새로 훈련하고 지정된 이름으로 저장
                logger.warning(f"{period['name']}: 모델 없음, 새로 훈련 후 저장...")
                train_result = bot.train_ml_model(train_df)
                
                if 'error' in train_result:
                    logger.error(f"{period['name']}: 모델 훈련 실패")
                    continue
                
                logger.info(f"{period['name']}: 새 모델 훈련 완료")
                
                # 지정된 모델명으로 저장
                try:
                    model_file = os.path.join("models", f"ml_model_{model_name}.joblib")
                    scaler_file = os.path.join("models", f"scaler_{model_name}.joblib")
                    model_info_file = os.path.join("models", f"model_info_{model_name}.json")
                    bot.save_ml_model(model_file, scaler_file, model_info_file)
                    logger.info(f"{period['name']}: 모델 저장 완료 - {model_name}")
                except Exception as e:
                    logger.warning(f"{period['name']}: 모델 저장 실패 - {e}")
            
            # 백테스트 실행 (테스트 데이터만 사용)
            logger.info(f"{period['name']}: 백테스트 실행 중...")
            results = bot.run_backtest(test_df, 
                                     start_date=period['test_start'], 
                                     end_date=period['test_end'])
            
            if 'error' in results:
                logger.error(f"{period['name']}: 백테스트 실패 - {results['error']}")
                continue
            
            # 결과 저장
            period_result = {
                'period': period['name'],
                'train_start': period['train_start'],
                'train_end': period['train_end'],
                'test_start': period['test_start'],
                'test_end': period['test_end'],
                'initial_balance': results['initial_balance'],
                'final_balance': results['final_balance'],
                'total_return': results['total_return'],
                'max_drawdown': results['max_drawdown'],
                'sharpe_ratio': results['sharpe_ratio'],
                'win_rate': results['win_rate'],
                'profit_factor': results['profit_factor'],
                'total_trades': results['total_trades'],
                'trades': results['trades']
            }
            
            all_results.append(period_result)
            all_trades.extend(results['trades'])
            
            # 다음 기간을 위한 잔고 업데이트
            total_balance = results['final_balance']
            
            # 상세 결과 분석
            winning_trades = sum(1 for trade in results['trades'] if trade['pnl'] > 0)
            losing_trades = sum(1 for trade in results['trades'] if trade['pnl'] < 0)
            avg_win = np.mean([trade['pnl'] for trade in results['trades'] if trade['pnl'] > 0]) if winning_trades > 0 else 0
            avg_loss = np.mean([trade['pnl'] for trade in results['trades'] if trade['pnl'] < 0]) if losing_trades > 0 else 0
            
            logger.info(f"{period['name']} 결과: 수익률 {results['total_return']:.2f}%, "
                       f"거래 {results['total_trades']}회, 승률 {results['win_rate']:.2f}%")
            logger.info(f"{period['name']} 상세: 승리 {winning_trades}회, 손실 {losing_trades}회, "
                       f"평균승리 {avg_win:.2f}, 평균손실 {avg_loss:.2f}")
            
        except Exception as e:
            logger.error(f"{period['name']}: 오류 발생 - {e}")
    
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
    print("=== 간단한 슬라이딩 윈도우 테스트 (기존 모델 로드) ===")
    print("15일 단위로 학습하고 15일 단위로 테스트")
    print("1월~3월까지 5개 기간 테스트")
    print("기존 훈련된 모델을 우선적으로 로드하여 사용")
    print()
    
    try:
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
                for period in results['period_results']:
                    print(f"{period['period']}: {period['test_start']} ~ {period['test_end']} | "
                          f"수익률: {period['total_return']:.2f}% | 거래: {period['total_trades']}회 | "
                          f"승률: {period['win_rate']:.2f}%")
        else:
            print("슬라이딩 윈도우 테스트 실행 실패")
            if results and 'error' in results:
                print(f"오류: {results['error']}")
        
        print("\n실행 완료!")
        
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
