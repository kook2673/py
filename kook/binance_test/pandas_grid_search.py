"""
판다스 벡터화를 활용한 그리드 서치 최적화 (체크포인트 지원)

사용법:
    python pandas_grid_search.py                    # 기본 실행 (스마트 모드)
    python pandas_grid_search.py --mode complete    # 완전 검색 모드
    python pandas_grid_search.py --mode smart       # 스마트 검색 모드 (기본)
    python pandas_grid_search.py --mode normal      # 일반 검색 모드
    python pandas_grid_search.py --clear            # 체크포인트 삭제 후 처음부터
    python pandas_grid_search.py --combinations 200 # 조합 수 조정

특징:
- 각 시장 상황 완료 후 자동으로 체크포인트 저장
- 중단 후 재시작 시 완료된 시장 상황은 건너뛰기
- Ctrl+C로 안전하게 중단 가능
- 2018-2025년 데이터로 최적화
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import warnings
from itertools import product
warnings.filterwarnings('ignore')

# 기존 클래스들 import
import sys
sys.path.append('.')
from market_regime_comparison import CurrentMarketRegimeDetector, AdaptiveStrategy, calculate_pnl, calculate_max_drawdown

class PandasGridSearchOptimizer:
    """판다스 벡터화를 활용한 그리드 서치 최적화 클래스"""
    
    def __init__(self, checkpoint_file="optimization_checkpoint.json"):
        self.detector = CurrentMarketRegimeDetector()
        self.checkpoint_file = checkpoint_file
        self.completed_regimes = set()
        self.optimized_params = {}
        self.all_results = {}
        
        # 각 시장 상황별 튜닝할 파라미터 범위 정의 (완전한 그리드 서치를 위한 확장)
        self.parameter_ranges = {
            'crash': {
                'rsi_oversold': [10, 15, 20, 25, 30],
                'rsi_overbought': [70, 75, 80, 85, 90],
                'ma_short': [2, 3, 5, 7, 10],
                'ma_long': [8, 10, 12, 15, 20],
                'stop_loss': [0.005, 0.01, 0.015, 0.02, 0.025],
                'take_profit': [0.02, 0.025, 0.03, 0.04, 0.05],
                'position_size': [0.1, 0.15, 0.2, 0.25, 0.3]
            },
            'strong_downtrend': {
                'rsi_oversold': [15, 20, 25, 30, 35],
                'rsi_overbought': [65, 70, 75, 80, 85],
                'ma_short': [3, 5, 7, 10, 12],
                'ma_long': [10, 12, 15, 18, 22],
                'stop_loss': [0.01, 0.015, 0.02, 0.025, 0.03],
                'take_profit': [0.025, 0.03, 0.04, 0.05, 0.06],
                'position_size': [0.2, 0.25, 0.3, 0.35, 0.4]
            },
            'downtrend': {
                'rsi_oversold': [20, 25, 30, 35, 40],
                'rsi_overbought': [60, 65, 70, 75, 80],
                'ma_short': [5, 6, 8, 10, 12],
                'ma_long': [15, 18, 20, 25, 30],
                'stop_loss': [0.015, 0.02, 0.025, 0.03, 0.035],
                'take_profit': [0.035, 0.04, 0.05, 0.06, 0.07],
                'position_size': [0.3, 0.4, 0.5, 0.6, 0.7]
            },
            'strong_uptrend': {
                'rsi_oversold': [30, 35, 40, 45, 50],
                'rsi_overbought': [70, 75, 80, 85, 90],
                'ma_short': [6, 8, 10, 12, 15],
                'ma_long': [20, 25, 30, 35, 40],
                'stop_loss': [0.025, 0.03, 0.04, 0.05, 0.06],
                'take_profit': [0.06, 0.08, 0.10, 0.12, 0.15],
                'position_size': [0.6, 0.8, 1.0, 1.0, 1.0]
            },
            'uptrend': {
                'rsi_oversold': [25, 30, 35, 40, 45],
                'rsi_overbought': [65, 70, 75, 80, 85],
                'ma_short': [8, 10, 12, 15, 18],
                'ma_long': [25, 30, 35, 40, 45],
                'stop_loss': [0.02, 0.025, 0.03, 0.035, 0.04],
                'take_profit': [0.05, 0.06, 0.08, 0.10, 0.12],
                'position_size': [0.5, 0.7, 0.8, 0.9, 1.0]
            },
            'high_volatility_sideways': {
                'rsi_oversold': [15, 20, 25, 30, 35],
                'rsi_overbought': [65, 70, 75, 80, 85],
                'ma_short': [3, 4, 6, 8, 10],
                'ma_long': [12, 15, 18, 22, 25],
                'stop_loss': [0.02, 0.025, 0.035, 0.045, 0.055],
                'take_profit': [0.05, 0.06, 0.08, 0.10, 0.12],
                'position_size': [0.4, 0.5, 0.6, 0.7, 0.8]
            },
            'low_volatility_sideways': {
                'rsi_oversold': [20, 25, 30, 35, 40],
                'rsi_overbought': [60, 65, 70, 75, 80],
                'ma_short': [10, 12, 15, 18, 20],
                'ma_long': [30, 35, 40, 45, 50],
                'stop_loss': [0.02, 0.025, 0.03, 0.035, 0.04],
                'take_profit': [0.05, 0.06, 0.08, 0.10, 0.12],
                'position_size': [0.5, 0.6, 0.7, 0.8, 0.9]
            }
        }
    
    def vectorized_backtest(self, data, regime, params, initial_capital=10000):
        """판다스 벡터화를 활용한 백테스트"""
        df = data.copy()
        window_size = 50
        
        # 시장 상황 감지 (벡터화)
        market_regimes = []
        for i in range(window_size, len(df)):
            current_data = df.iloc[max(0, i - window_size + 1):i+1]
            regime_detected = self.detector.detect_market_regime(current_data)
            market_regimes.append(regime_detected)
        
        df['market_regime'] = pd.Series(market_regimes, index=df.index[window_size:])
        
        # 해당 시장 상황의 데이터만 필터링
        regime_mask = df['market_regime'] == regime
        regime_data = df[regime_mask].copy()
        
        if len(regime_data) < 20:
            return None
        
        # 지표 계산 (벡터화)
        regime_data = self.calculate_indicators_vectorized(regime_data, params)
        
        # 신호 생성 (벡터화)
        regime_data = self.generate_signals_vectorized(regime_data, params)
        
        # 거래 시뮬레이션 (벡터화된 부분 + 순차 처리)
        return self.simulate_trades_vectorized(regime_data, params, initial_capital)
    
    def calculate_indicators_vectorized(self, df, params):
        """벡터화된 지표 계산"""
        # RSI 계산
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Moving Average
        df['ma_short'] = df['close'].rolling(params['ma_short']).mean()
        df['ma_long'] = df['close'].rolling(params['ma_long']).mean()
        
        # Donchian Channel
        dc_period = 45
        df['dc_high'] = df['high'].rolling(dc_period).max()
        df['dc_low'] = df['low'].rolling(dc_period).min()
        df['dc_middle'] = (df['dc_high'] + df['dc_low']) / 2
        
        return df
    
    def generate_signals_vectorized(self, df, params):
        """벡터화된 신호 생성"""
        # Moving Average 신호
        df['ma_long_signal'] = df['ma_short'] > df['ma_long']
        df['ma_short_signal'] = df['ma_short'] < df['ma_long']
        
        # RSI 신호
        df['rsi_long_signal'] = df['rsi'] < params['rsi_oversold']
        df['rsi_short_signal'] = df['rsi'] > params['rsi_overbought']
        
        # Donchian Channel 신호
        df['dc_long_signal'] = (df['close'] > df['dc_middle']) & (df['close'] > df['dc_low'] * 1.02)
        df['dc_short_signal'] = (df['close'] < df['dc_middle']) & (df['close'] < df['dc_high'] * 0.98)
        
        # 신호 결합
        df['long_signal'] = df['ma_long_signal'] & df['rsi_long_signal'] & df['dc_long_signal']
        df['short_signal'] = df['ma_short_signal'] & df['rsi_short_signal'] & df['dc_short_signal']
        
        return df
    
    def simulate_trades_vectorized(self, df, params, initial_capital):
        """벡터화된 거래 시뮬레이션"""
        current_capital = initial_capital
        position = None
        entry_price = 0
        entry_time = None
        trades = []
        
        # 신호가 있는 인덱스만 처리
        signal_indices = df[df['long_signal'] | df['short_signal']].index
        
        for current_time in signal_indices:
            current_row = df.loc[current_time]
            
            if position is None:
                if current_row['long_signal']:
                    position = 'long'
                    entry_price = current_row['close']
                    entry_time = current_time
                    position_size = current_capital * params['position_size']
                    
                    entry_fee = position_size * 0.0005
                    current_capital -= entry_fee
                    
                elif current_row['short_signal']:
                    position = 'short'
                    entry_price = current_row['close']
                    entry_time = current_time
                    position_size = current_capital * params['position_size']
                    
                    entry_fee = position_size * 0.0005
                    current_capital -= entry_fee
            
            elif position is not None:
                should_exit = False
                exit_reason = ""
                
                if position == 'long':
                    if current_row['short_signal']:
                        should_exit = True
                        exit_reason = "숏 신호"
                    elif current_row['close'] <= entry_price * (1 - params['stop_loss']):
                        should_exit = True
                        exit_reason = f"{params['stop_loss']*100:.0f}% 손절매"
                    elif current_row['close'] >= entry_price * (1 + params['take_profit']):
                        should_exit = True
                        exit_reason = f"{params['take_profit']*100:.0f}% 익절"
                
                elif position == 'short':
                    if current_row['long_signal']:
                        should_exit = True
                        exit_reason = "롱 신호"
                    elif current_row['close'] >= entry_price * (1 + params['stop_loss']):
                        should_exit = True
                        exit_reason = f"{params['stop_loss']*100:.0f}% 손절매"
                    elif current_row['close'] <= entry_price * (1 - params['take_profit']):
                        should_exit = True
                        exit_reason = f"{params['take_profit']*100:.0f}% 익절"
                
                if should_exit:
                    exit_price = current_row['close']
                    position_size = current_capital * params['position_size']
                    
                    pnl = calculate_pnl(entry_price, exit_price, position_size, position)
                    exit_fee = position_size * 0.0005
                    net_pnl = pnl - exit_fee
                    current_capital += net_pnl
                    
                    trades.append({
                        'entry_time': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'exit_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'position': position,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl': net_pnl,
                        'gross_pnl': pnl,
                        'entry_fee': position_size * 0.0005,
                        'exit_fee': exit_fee,
                        'total_fee': (position_size * 0.0005) + exit_fee,
                        'exit_reason': exit_reason
                    })
                    
                    position = None
        
        # 결과 계산 (더 정교한 성능 지표)
        total_return = (current_capital - initial_capital) / initial_capital * 100
        winning_trades = len([t for t in trades if t['pnl'] > 0])
        losing_trades = len([t for t in trades if t['pnl'] < 0])
        win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0
        
        # 평균 수익/손실 계산
        avg_win = np.mean([t['pnl'] for t in trades if t['pnl'] > 0]) if winning_trades > 0 else 0
        avg_loss = np.mean([t['pnl'] for t in trades if t['pnl'] < 0]) if losing_trades > 0 else 0
        profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 and avg_loss != 0 else float('inf')
        
        # 최대 연속 승리/패배
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0
        
        for trade in trades:
            if trade['pnl'] > 0:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)
        
        # 샤프 비율 계산 (간단한 버전)
        returns = [t['pnl'] / initial_capital for t in trades]
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 and np.std(returns) > 0 else 0
        
        max_drawdown = calculate_max_drawdown(initial_capital, trades)
        
        return {
            'total_return': total_return,
            'final_capital': current_capital,
            'total_trades': len(trades),
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses,
            'sharpe_ratio': sharpe_ratio,
            'trades': trades
        }
    
    def evaluate_single_params(self, args):
        """단일 파라미터 조합 평가 (멀티프로세싱용)"""
        data, regime, params = args
        try:
            result = self.vectorized_backtest(data, regime, params)
            if result and result['total_trades'] > 0:
                # 더 정교한 점수 계산 (다중 지표 가중 평균)
                score = (
                    result['total_return'] * 0.25 +           # 수익률
                    result['win_rate'] * 0.20 +              # 승률
                    result['profit_factor'] * 0.15 +         # 수익 팩터
                    result['sharpe_ratio'] * 0.15 +          # 샤프 비율
                    -result['max_drawdown'] * 0.15 +         # 최대 낙폭 (음수)
                    min(result['total_trades'] / 10, 1) * 10  # 거래 빈도 (정규화)
                )
                
                return {
                    'score': score,
                    'total_return': result['total_return'],
                    'win_rate': result['win_rate'],
                    'max_drawdown': result['max_drawdown'],
                    'profit_factor': result['profit_factor'],
                    'sharpe_ratio': result['sharpe_ratio'],
                    'total_trades': result['total_trades'],
                    'avg_win': result['avg_win'],
                    'avg_loss': result['avg_loss'],
                    'max_consecutive_wins': result['max_consecutive_wins'],
                    'max_consecutive_losses': result['max_consecutive_losses'],
                    'params': params
                }
        except Exception as e:
            print(f"평가 오류 ({regime}): {e}")
        return None
    
    
    def evaluate_parameters(self, data, regime, param_combinations):
        """파라미터 조합 평가 (순차 처리)"""
        print(f"{regime} 시장 상황: {len(param_combinations)}개 조합 평가 중...")
        
        results = []
        for i, params in enumerate(param_combinations):
            if (i + 1) % 50 == 0:
                print(f"  진행률: {i+1}/{len(param_combinations)} ({((i+1)/len(param_combinations)*100):.1f}%)")
            
            result = self.evaluate_single_params((data, regime, params))
            if result:
                results.append(result)
        
        # 정렬
        results.sort(key=lambda x: x['score'], reverse=True)
        return results
    
    def optimize_regime_pandas(self, data, regime, max_combinations=100):
        """판다스 벡터화를 활용한 시장 상황 최적화"""
        print(f"\n=== {regime.upper()} 시장 상황 최적화 (판다스 벡터화) ===")
        
        # 파라미터 조합 생성
        ranges = self.parameter_ranges[regime]
        keys = list(ranges.keys())
        values = list(ranges.values())
        
        all_combinations = list(product(*values))
        param_combinations = [dict(zip(keys, combo)) for combo in all_combinations]
        
        print(f"총 {len(param_combinations)}개의 조합 생성")
        
        # 너무 많은 조합이면 랜덤 샘플링
        if len(param_combinations) > max_combinations:
            import random
            param_combinations = random.sample(param_combinations, max_combinations)
            print(f"랜덤 샘플링으로 {max_combinations}개 조합 선택")
        
        # 파라미터 평가
        results = self.evaluate_parameters(data, regime, param_combinations)
        
        if not results:
            print(f"{regime} 시장 상황에 대한 유효한 결과가 없습니다.")
            return None, []
        
        best_result = results[0]
        print(f"\n{regime.upper()} 최적화 완료!")
        print(f"최고 점수: {best_result['score']:.4f}")
        print(f"수익률: {best_result['total_return']:.2f}%, 승률: {best_result['win_rate']:.2f}%, 낙폭: {best_result['max_drawdown']:.2f}%")
        print(f"최적 파라미터: {best_result['params']}")
        
        return best_result['params'], results[:10]  # 상위 10개 결과 반환
    
    def complete_grid_search(self, data, regime, use_all_combinations=True):
        """완전한 그리드 서치 (모든 조합 검사)"""
        print(f"\n=== {regime.upper()} 완전한 그리드 서치 ===")
        
        ranges = self.parameter_ranges[regime]
        keys = list(ranges.keys())
        values = list(ranges.values())
        
        all_combinations = list(product(*values))
        param_combinations = [dict(zip(keys, combo)) for combo in all_combinations]
        
        print(f"총 {len(param_combinations)}개의 조합을 완전 검사합니다.")
        
        # 모든 조합 평가
        results = self.evaluate_parameters(data, regime, param_combinations)
        
        if not results:
            print(f"{regime} 시장 상황에 대한 유효한 결과가 없습니다.")
            return None, []
        
        best_result = results[0]
        print(f"\n{regime.upper()} 완전 그리드 서치 완료!")
        print(f"최고 점수: {best_result['score']:.4f}")
        print(f"수익률: {best_result['total_return']:.2f}%, 승률: {best_result['win_rate']:.2f}%")
        print(f"수익팩터: {best_result['profit_factor']:.2f}, 샤프비율: {best_result['sharpe_ratio']:.2f}")
        print(f"최대낙폭: {best_result['max_drawdown']:.2f}%, 거래수: {best_result['total_trades']}")
        print(f"최적 파라미터: {best_result['params']}")
        
        return best_result['params'], results[:20]  # 상위 20개 결과 반환
    
    def smart_grid_search(self, data, regime, max_combinations=200):
        """스마트 그리드 서치 (단계적 세밀화)"""
        print(f"\n=== {regime.upper()} 스마트 그리드 서치 ===")
        
        # 1단계: 넓은 범위로 빠른 검색
        print("1단계: 넓은 범위 빠른 검색...")
        coarse_ranges = {}
        for key, values in self.parameter_ranges[regime].items():
            # 5개 값에서 3개만 선택 (첫번째, 중간, 마지막)
            if len(values) >= 3:
                coarse_ranges[key] = [values[0], values[len(values)//2], values[-1]]
            else:
                coarse_ranges[key] = values
        
        coarse_combinations = list(product(*coarse_ranges.values()))
        coarse_params = [dict(zip(coarse_ranges.keys(), combo)) for combo in coarse_combinations]
        
        coarse_results = self.evaluate_parameters(data, regime, coarse_params)
        
        if not coarse_results:
            print(f"{regime} 시장 상황에 대한 유효한 결과가 없습니다.")
            return None, []
        
        # 상위 20% 결과에서 최적 파라미터 범위 추출
        top_20_percent = max(1, len(coarse_results) // 5)
        top_results = coarse_results[:top_20_percent]
        
        print(f"1단계 완료: {len(coarse_results)}개 조합 중 상위 {top_20_percent}개 선택")
        
        # 2단계: 최적 범위 주변 세밀 검색
        print("2단계: 최적 범위 주변 세밀 검색...")
        refined_ranges = {}
        
        for key in self.parameter_ranges[regime].keys():
            values = self.parameter_ranges[regime][key]
            top_values = [r['params'][key] for r in top_results]
            
            # 최적값들의 범위를 찾아서 그 주변에서 세밀하게 검색
            min_val = min(top_values)
            max_val = max(top_values)
            
            # 원래 범위에서 최적 범위와 겹치는 부분만 선택
            refined_values = [v for v in values if min_val <= v <= max_val]
            
            # 최소 3개는 유지
            if len(refined_values) < 3:
                # 원래 범위에서 최적값 주변 3개 선택
                optimal_val = np.median(top_values)
                distances = [(abs(v - optimal_val), v) for v in values]
                distances.sort()
                refined_values = [v for _, v in distances[:3]]
            
            refined_ranges[key] = refined_values
        
        refined_combinations = list(product(*refined_ranges.values()))
        refined_params = [dict(zip(refined_ranges.keys(), combo)) for combo in refined_combinations]
        
        # 너무 많으면 랜덤 샘플링
        if len(refined_params) > max_combinations:
            import random
            refined_params = random.sample(refined_params, max_combinations)
            print(f"랜덤 샘플링으로 {max_combinations}개 조합 선택")
        
        refined_results = self.evaluate_parameters(data, regime, refined_params)
        
        # 1단계와 2단계 결과 합치고 정렬
        all_results = coarse_results + refined_results
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        best_result = all_results[0]
        print(f"\n{regime.upper()} 스마트 그리드 서치 완료!")
        print(f"최고 점수: {best_result['score']:.4f}")
        print(f"수익률: {best_result['total_return']:.2f}%, 승률: {best_result['win_rate']:.2f}%")
        print(f"수익팩터: {best_result['profit_factor']:.2f}, 샤프비율: {best_result['sharpe_ratio']:.2f}")
        print(f"최대낙폭: {best_result['max_drawdown']:.2f}%, 거래수: {best_result['total_trades']}")
        print(f"최적 파라미터: {best_result['params']}")
        
        return best_result['params'], all_results[:20]
    
    def optimize_all_regimes_pandas(self, data, max_combinations_per_regime=50, search_mode='smart', resume=True):
        """모든 시장 상황에 대한 판다스 벡터화 최적화 (체크포인트 지원)"""
        print("=== 전체 시장 상황 최적화 (판다스 벡터화) ===")
        print(f"검색 모드: {search_mode}")
        print(f"재시작 모드: {'ON' if resume else 'OFF'}")
        
        # 체크포인트 로드
        if resume:
            self.load_checkpoint()
        
        regimes = list(self.parameter_ranges.keys())
        total_regimes = len(regimes)
        completed_count = len(self.completed_regimes)
        
        print(f"전체 시장 상황: {total_regimes}개")
        print(f"완료된 시장 상황: {completed_count}개")
        print(f"남은 시장 상황: {total_regimes - completed_count}개")
        
        for i, regime in enumerate(regimes, 1):
            # 이미 완료된 시장 상황은 건너뛰기
            if self.is_regime_completed(regime):
                print(f"\n{'='*60}")
                print(f"[{i}/{total_regimes}] {regime.upper()} 시장 상황 (이미 완료됨)")
                print(f"{'='*60}")
                continue
            
            print(f"\n{'='*60}")
            print(f"[{i}/{total_regimes}] {regime.upper()} 시장 상황 최적화")
            print(f"{'='*60}")
            
            try:
                if search_mode == 'complete':
                    best_params, top_results = self.complete_grid_search(data, regime)
                elif search_mode == 'smart':
                    best_params, top_results = self.smart_grid_search(data, regime, max_combinations_per_regime)
                else:  # 'normal'
                    best_params, top_results = self.optimize_regime_pandas(data, regime, max_combinations_per_regime)
                
                if best_params:
                    self.optimized_params[regime] = best_params
                    self.all_results[regime] = top_results
                    self.completed_regimes.add(regime)
                    
                    # 각 시장 상황 완료 후 체크포인트 저장
                    self.save_checkpoint()
                    print(f"✅ {regime.upper()} 완료 및 체크포인트 저장됨")
                else:
                    print(f"❌ {regime.upper()} 최적화 실패")
                    
            except KeyboardInterrupt:
                print(f"\n⚠️ 사용자에 의해 중단됨. 현재까지의 진행 상황이 저장되었습니다.")
                self.save_checkpoint()
                break
            except Exception as e:
                print(f"❌ {regime.upper()} 최적화 중 오류 발생: {e}")
                continue
        
        print(f"\n=== 최적화 진행 상황 ===")
        print(f"완료된 시장 상황: {len(self.completed_regimes)}/{total_regimes}")
        print(f"완료율: {len(self.completed_regimes)/total_regimes*100:.1f}%")
        
        return self.optimized_params, self.all_results
    
    def save_results(self, optimized_params, all_results, filename="pandas_grid_search_results.json"):
        """최적화 결과 저장"""
        output = {
            'optimized_parameters': optimized_params,
            'top_results': all_results,
            'optimization_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'description': '판다스 벡터화를 활용한 시장 상황별 파라미터 그리드 서치 최적화 결과'
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n최적화 결과가 {filename}에 저장되었습니다.")
    
    def print_optimization_summary(self, optimized_params, all_results):
        """최적화 결과 요약 출력"""
        print("\n" + "="*80)
        print("최적화된 파라미터 요약 (판다스 벡터화)")
        print("="*80)
        
        for regime, params in optimized_params.items():
            print(f"\n{regime.upper()}:")
            for key, value in params.items():
                print(f"  {key}: {value}")
            
            # 해당 시장 상황의 상위 결과들 출력
            if regime in all_results and all_results[regime]:
                print(f"  상위 결과들:")
                for i, result in enumerate(all_results[regime][:3], 1):
                    print(f"    {i}위: 점수={result['score']:.2f}, 수익률={result['total_return']:.2f}%, "
                          f"승률={result['win_rate']:.2f}%, 낙폭={result['max_drawdown']:.2f}%")
    
    def analyze_parameter_sensitivity(self, all_results):
        """파라미터 민감도 분석"""
        print("\n" + "="*80)
        print("파라미터 민감도 분석")
        print("="*80)
        
        for regime, results in all_results.items():
            if not results:
                continue
                
            print(f"\n{regime.upper()} 시장 상황:")
            
            # 각 파라미터별 최적값 분포 분석
            param_stats = {}
            for result in results:
                for param, value in result['params'].items():
                    if param not in param_stats:
                        param_stats[param] = []
                    param_stats[param].append(value)
            
            for param, values in param_stats.items():
                unique_values = list(set(values))
                value_counts = {v: values.count(v) for v in unique_values}
                most_common = max(value_counts, key=value_counts.get)
                print(f"  {param}: 최빈값={most_common} (빈도={value_counts[most_common]}/{len(values)})")
    
    def generate_optimization_report(self, optimized_params, all_results, filename="optimization_report.txt"):
        """최적화 보고서 생성"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("그리드 서치 최적화 보고서\n")
            f.write("="*80 + "\n")
            f.write(f"생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # 각 시장 상황별 최적 파라미터
            f.write("1. 최적 파라미터\n")
            f.write("-" * 40 + "\n")
            for regime, params in optimized_params.items():
                f.write(f"\n{regime.upper()}:\n")
                for key, value in params.items():
                    f.write(f"  {key}: {value}\n")
            
            # 각 시장 상황별 상위 결과
            f.write("\n2. 상위 결과 분석\n")
            f.write("-" * 40 + "\n")
            for regime, results in all_results.items():
                if not results:
                    continue
                f.write(f"\n{regime.upper()}:\n")
                for i, result in enumerate(results[:5], 1):
                    f.write(f"  {i}위: 점수={result['score']:.2f}, 수익률={result['total_return']:.2f}%, "
                           f"승률={result['win_rate']:.2f}%, 낙폭={result['max_drawdown']:.2f}%, "
                           f"수익팩터={result['profit_factor']:.2f}, 샤프비율={result['sharpe_ratio']:.2f}\n")
            
            # 파라미터 민감도 분석
            f.write("\n3. 파라미터 민감도 분석\n")
            f.write("-" * 40 + "\n")
            for regime, results in all_results.items():
                if not results:
                    continue
                    
                f.write(f"\n{regime.upper()}:\n")
                
                param_stats = {}
                for result in results:
                    for param, value in result['params'].items():
                        if param not in param_stats:
                            param_stats[param] = []
                        param_stats[param].append(value)
                
                for param, values in param_stats.items():
                    unique_values = list(set(values))
                    value_counts = {v: values.count(v) for v in unique_values}
                    most_common = max(value_counts, key=value_counts.get)
                    f.write(f"  {param}: 최빈값={most_common} (빈도={value_counts[most_common]}/{len(values)})\n")
        
        print(f"\n최적화 보고서가 {filename}에 저장되었습니다.")
    
    def save_checkpoint(self):
        """현재 진행 상황을 체크포인트로 저장"""
        checkpoint_data = {
            'completed_regimes': list(self.completed_regimes),
            'optimized_params': self.optimized_params,
            'all_results': self.all_results,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
        
        print(f"체크포인트 저장됨: {self.checkpoint_file}")
    
    def load_checkpoint(self):
        """저장된 체크포인트에서 진행 상황 복원"""
        if not os.path.exists(self.checkpoint_file):
            print("체크포인트 파일이 없습니다. 처음부터 시작합니다.")
            return False
        
        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            self.completed_regimes = set(checkpoint_data.get('completed_regimes', []))
            self.optimized_params = checkpoint_data.get('optimized_params', {})
            self.all_results = checkpoint_data.get('all_results', {})
            
            print(f"체크포인트 로드됨: {checkpoint_data.get('timestamp', '알 수 없음')}")
            print(f"완료된 시장 상황: {list(self.completed_regimes)}")
            return True
            
        except Exception as e:
            print(f"체크포인트 로드 실패: {e}")
            return False
    
    def clear_checkpoint(self):
        """체크포인트 파일 삭제"""
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)
            print(f"체크포인트 파일 삭제됨: {self.checkpoint_file}")
    
    def is_regime_completed(self, regime):
        """특정 시장 상황이 이미 완료되었는지 확인"""
        return regime in self.completed_regimes

def main():
    """메인 실행 함수"""
    print("=== 판다스 벡터화 그리드 서치 최적화 (체크포인트 지원) ===")
    
    # 명령행 인수 처리
    import argparse
    parser = argparse.ArgumentParser(description='그리드 서치 최적화')
    parser.add_argument('--mode', choices=['complete', 'smart', 'normal'], default='smart',
                       help='검색 모드 (default: smart)')
    parser.add_argument('--resume', action='store_true', default=True,
                       help='이전 진행 상황에서 재시작 (default: True)')
    parser.add_argument('--clear', action='store_true',
                       help='체크포인트 파일 삭제 후 처음부터 시작')
    parser.add_argument('--combinations', type=int, default=100,
                       help='시장 상황당 최대 조합 수 (default: 100)')
    
    args = parser.parse_args()
    
    # 체크포인트 파일명 설정
    checkpoint_file = f"optimization_checkpoint_{args.mode}.json"
    optimizer = PandasGridSearchOptimizer(checkpoint_file)
    
    # 체크포인트 삭제 옵션
    if args.clear:
        optimizer.clear_checkpoint()
        print("체크포인트가 삭제되었습니다. 처음부터 시작합니다.")
    
    # 데이터 로드 (2018-2025년 데이터로 최적화)
    data_files = [
        "data/BTCUSDT/5m/BTCUSDT_5m_2018.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2019.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2020.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2021.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2022.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2023.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2024.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2025.csv"
    ]
    
    all_data = []
    for file_path in data_files:
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            all_data.append(df)
            print(f"데이터 로드 완료: {file_path}")
        else:
            print(f"데이터 파일 없음: {file_path}")
    
    if not all_data:
        print("데이터를 로드할 수 없습니다.")
        return
    
    combined_data = pd.concat(all_data, ignore_index=False).sort_index()
    print(f"전체 데이터: {len(combined_data)}개 캔들")
    print(f"데이터 기간: {combined_data.index.min()} ~ {combined_data.index.max()}")
    
    # 최적화 실행
    try:
        optimized_params, all_results = optimizer.optimize_all_regimes_pandas(
            combined_data, 
            max_combinations_per_regime=args.combinations,
            search_mode=args.mode,
            resume=args.resume
        )
        
        # 최종 결과 저장
        optimizer.save_results(optimized_params, all_results)
        
        # 요약 출력
        optimizer.print_optimization_summary(optimized_params, all_results)
        
        # 파라미터 민감도 분석
        optimizer.analyze_parameter_sensitivity(all_results)
        
        # 최적화 보고서 생성
        optimizer.generate_optimization_report(optimized_params, all_results)
        
        print("\n=== 최적화 완료 ===")
        print(f"검색 모드: {args.mode}")
        print(f"데이터 기간: 2018-2025년 ({len(combined_data)}개 캔들)")
        print("결과 파일: pandas_grid_search_results.json")
        print("보고서 파일: optimization_report.txt")
        print(f"체크포인트 파일: {checkpoint_file}")
        
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단됨. 현재까지의 진행 상황이 저장되었습니다.")
        optimizer.save_checkpoint()
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        optimizer.save_checkpoint()

if __name__ == "__main__":
    main()

