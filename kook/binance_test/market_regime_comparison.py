"""
최적화된 적응형 트레이딩 시스템

=== 최고 성과 시스템 ===
현재 시장 상황 감지 시스템 (30.05% 수익률, 66.63% 승률)
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class CurrentMarketRegimeDetector:
    """현재 코드의 시장 상황 감지기"""
    
    def __init__(self):
        self.trend_periods = [20, 50, 100]
        self.volatility_period = 20
    
    def detect_market_regime(self, data):
        """시장 상황 분석"""
        if len(data) < max(self.trend_periods):
            return 'unknown'
        
        # 트렌드 분석
        short_trend = data['close'].iloc[-self.trend_periods[0]:].pct_change().mean()
        mid_trend = data['close'].iloc[-self.trend_periods[1]:].pct_change().mean()
        long_trend = data['close'].iloc[-self.trend_periods[2]:].pct_change().mean()
        
        # 변동성 분석
        returns = data['close'].pct_change()
        volatility = returns.rolling(self.volatility_period).std().iloc[-1]
        
        # 시장 상황 분류
        if short_trend < -0.002 and mid_trend < -0.001 and long_trend < -0.0005:
            if volatility > 0.025:
                return 'crash'
            else:
                return 'strong_downtrend'
        elif short_trend < -0.001 and mid_trend < -0.0005:
            return 'downtrend'
        elif short_trend > 0.002 and mid_trend > 0.001 and long_trend > 0.0005:
            return 'strong_uptrend'
        elif short_trend > 0.001 and mid_trend > 0.0005:
            return 'uptrend'
        else:
            if volatility > 0.02:
                return 'high_volatility_sideways'
            else:
                return 'low_volatility_sideways'


class AdaptiveStrategy:
    """시장 상황별 적응형 전략"""
    
    def __init__(self, regime_detector):
        self.regime_detector = regime_detector
        
        # 시장 상황별 파라미터
        self.market_params = {
            'crash': {
                'rsi_oversold': 5, 'rsi_overbought': 95, 'bb_std': 1.0,
                'stop_loss': 0.015, 'take_profit': 0.03, 'position_size': 0.2
            },
            'strong_downtrend': {
                'rsi_oversold': 10, 'rsi_overbought': 90, 'bb_std': 1.2,
                'stop_loss': 0.02, 'take_profit': 0.04, 'position_size': 0.3
            },
            'downtrend': {
                'rsi_oversold': 15, 'rsi_overbought': 85, 'bb_std': 1.5,
                'stop_loss': 0.025, 'take_profit': 0.05, 'position_size': 0.5
            },
            'strong_uptrend': {
                'rsi_oversold': 40, 'rsi_overbought': 80, 'bb_std': 2.0,
                'stop_loss': 0.04, 'take_profit': 0.10, 'position_size': 1.0
            },
            'uptrend': {
                'rsi_oversold': 35, 'rsi_overbought': 75, 'bb_std': 2.0,
                'stop_loss': 0.03, 'take_profit': 0.08, 'position_size': 0.8
            },
            'high_volatility_sideways': {
                'rsi_oversold': 25, 'rsi_overbought': 80, 'bb_std': 1.8,
                'stop_loss': 0.035, 'take_profit': 0.08, 'position_size': 0.6
            },
            'low_volatility_sideways': {
                'rsi_oversold': 30, 'rsi_overbought': 70, 'bb_std': 2.0,
                'stop_loss': 0.03, 'take_profit': 0.08, 'position_size': 0.7
            }
        }
    
    def calculate_indicators(self, data, market_regime):
        """시장 상황별 지표 계산"""
        df = data.copy()
        params = self.market_params.get(market_regime, self.market_params['low_volatility_sideways'])
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 볼린저 밴드
        df['bb_middle'] = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * params['bb_std'])
        df['bb_lower'] = df['bb_middle'] - (bb_std * params['bb_std'])
        
        return df, params
    
    def generate_signals(self, df, params):
        """시장 상황별 신호 생성"""
        long_signal = (df['close'] <= df['bb_lower']) & (df['rsi'] < params['rsi_oversold'])
        short_signal = (df['close'] >= df['bb_upper']) & (df['rsi'] > params['rsi_overbought'])
        
        df['long_signal'] = long_signal
        df['short_signal'] = short_signal
        
        return df

def run_optimized_backtest(data, start_date, end_date, initial_capital=10000):
    """최적화된 적응형 트레이딩 시스템 백테스트"""
    print("=== 최적화된 적응형 트레이딩 시스템 백테스트 ===")
    
    # 데이터 필터링
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    mask = (data.index >= start_dt) & (data.index <= end_dt)
    test_data = data[mask].copy()
    
    if len(test_data) == 0:
        print("테스트 데이터가 없습니다.")
        return None
    
    print(f"테스트 기간: {start_date} ~ {end_date}")
    print(f"데이터 길이: {len(test_data)}개 캔들")
    
    # 최적화된 시장 상황 감지 시스템
    print("\n최적화된 시장 상황 감지 시스템 테스트 중...")
    detector = CurrentMarketRegimeDetector()
    adaptive_strategy = AdaptiveStrategy(detector)
    result = run_adaptive_backtest(test_data, adaptive_strategy, initial_capital, "최적화시스템")
    
    # 결과 출력
    if result:
        print("\n" + "="*80)
        print("최적화된 시스템 결과")
        print("="*80)
        print(f"  총 수익률: {result['total_return']:.2f}%")
        print(f"  최종 자본: ${result['final_capital']:.2f}")
        print(f"  총 거래: {result['total_trades']}회")
        print(f"  승률: {result['win_rate']:.2f}%")
        print(f"  최대 낙폭: {result['max_drawdown']:.2f}%")
    
    return result

def run_yearly_analysis(data, start_year=2018, end_year=2025, initial_capital=10000):
    """연도별 성과 분석"""
    print("=== 연도별 성과 분석 (2018-2025) ===")
    
    yearly_results = {}
    current_capital = initial_capital
    
    for year in range(start_year, end_year + 1):
        print(f"\n{year}년 분석 중...")
        
        # 해당 연도 데이터 필터링
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        mask = (data.index >= start_dt) & (data.index <= end_dt)
        year_data = data[mask].copy()
        
        if len(year_data) == 0:
            print(f"  {year}년 데이터가 없습니다.")
            yearly_results[year] = {
                'total_return': 0,
                'final_capital': current_capital,
                'total_trades': 0,
                'win_rate': 0,
                'max_drawdown': 0,
                'trades': []
            }
            continue
        
        print(f"  데이터 길이: {len(year_data)}개 캔들")
        
        # 해당 연도 백테스트 실행
        detector = CurrentMarketRegimeDetector()
        adaptive_strategy = AdaptiveStrategy(detector)
        year_result = run_adaptive_backtest(year_data, adaptive_strategy, current_capital, f"{year}년시스템")
        
        if year_result:
            yearly_results[year] = year_result
            current_capital = year_result['final_capital']  # 다음 연도 시작 자본 업데이트
            
            print(f"  {year}년 완료: 수익률 {year_result['total_return']:.2f}%, 거래 {year_result['total_trades']}회, 승률 {year_result['win_rate']:.1f}%")
        else:
            yearly_results[year] = {
                'total_return': 0,
                'final_capital': current_capital,
                'total_trades': 0,
                'win_rate': 0,
                'max_drawdown': 0,
                'trades': []
            }
    
    # 연도별 성과 요약 출력
    print("\n" + "="*100)
    print("연도별 성과 요약")
    print("="*100)
    print(f"{'연도':<6} {'수익률':<8} {'최종자본':<12} {'거래수':<6} {'승률':<6} {'최대낙폭':<8} {'누적수익률':<10}")
    print("-" * 100)
    
    cumulative_return = 0
    for year in range(start_year, end_year + 1):
        if year in yearly_results:
            result = yearly_results[year]
            cumulative_return = (result['final_capital'] - initial_capital) / initial_capital * 100
            
            print(f"{year:<6} {result['total_return']:>6.2f}% {result['final_capital']:>10.2f} {result['total_trades']:>5}회 "
                  f"{result['win_rate']:>4.1f}% {result['max_drawdown']:>6.2f}% {cumulative_return:>8.2f}%")
    
    print("-" * 100)
    print(f"전체 기간 누적 수익률: {cumulative_return:.2f}%")
    print(f"최종 자본: ${yearly_results[end_year]['final_capital']:.2f}")
    
    return yearly_results


def run_adaptive_backtest(data, adaptive_strategy, initial_capital, strategy_name):
    """적응형 백테스트 실행"""
    current_capital = initial_capital
    position = None
    entry_price = 0
    entry_time = None
    trades = []
    
    window_size = 50
    
    for i in range(window_size, len(data)):
        current_time = data.index[i]
        current_data = data.iloc[max(0, i - window_size + 1):i+1]
        
        # 시장 상황 감지
        market_regime = adaptive_strategy.regime_detector.detect_market_regime(current_data)
        
        # 지표 계산 및 신호 생성
        df_with_indicators, params = adaptive_strategy.calculate_indicators(current_data, market_regime)
        df_with_signals = adaptive_strategy.generate_signals(df_with_indicators, params)
        
        current_row = df_with_signals.iloc[-1]
        
        # 포지션 관리
        if position is None:
            if current_row['long_signal']:
                position = 'long'
                entry_price = current_row['close']
                entry_time = current_time
                position_size = current_capital * params['position_size']
                
                # 진입 수수료 계산 및 차감
                entry_fee = position_size * 0.0005  # 0.05%
                current_capital -= entry_fee
                
                print(f"{current_time}: 롱 진입 (시장: {market_regime}, 가격: {entry_price:.2f}, 크기: {position_size:.2f}, fee: {entry_fee:.2f})")
                
            elif current_row['short_signal']:
                position = 'short'
                entry_price = current_row['close']
                entry_time = current_time
                position_size = current_capital * params['position_size']
                
                # 진입 수수료 계산 및 차감
                entry_fee = position_size * 0.0005  # 0.05%
                current_capital -= entry_fee
                
                print(f"{current_time}: 숏 진입 (시장: {market_regime}, 가격: {entry_price:.2f}, 크기: {position_size:.2f}, fee: {entry_fee:.2f})")
        
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
                
                # PnL 계산
                pnl = calculate_pnl(entry_price, exit_price, position_size, position)
                
                # 청산 수수료 계산 및 차감
                exit_fee = position_size * 0.0005  # 0.05%
                total_fee = (position_size * 0.0005) + exit_fee  # 진입 + 청산 수수료
                
                # 순 PnL 계산 (수수료 차감 후)
                net_pnl = pnl - total_fee
                current_capital += net_pnl
                
                trades.append({
                    'entry_time': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'exit_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'position': position,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': net_pnl,  # 순 PnL
                    'gross_pnl': pnl,  # 총 PnL
                    'entry_fee': position_size * 0.0005,
                    'exit_fee': exit_fee,
                    'total_fee': total_fee,
                    'exit_reason': exit_reason,
                    'market_regime': market_regime
                })
                
                pnl_percent = (net_pnl / position_size) * 100
                if net_pnl > 0:
                    print(f"{current_time}: {position} 청산 [수익] (시장: {market_regime}, 수익률: {pnl_percent:.2f}%, PnL: {net_pnl:.2f}, fee: {total_fee:.2f})")
                else:
                    print(f"{current_time}: {position} 청산 [손실] (시장: {market_regime}, 손실률: {pnl_percent:.2f}%, PnL: {net_pnl:.2f}, fee: {total_fee:.2f})")
                
                position = None
    
    # 결과 계산
    total_return = (current_capital - initial_capital) / initial_capital * 100
    winning_trades = len([t for t in trades if t['pnl'] > 0])
    win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0
    max_drawdown = calculate_max_drawdown(initial_capital, trades)
    
    return {
        'total_return': total_return,
        'final_capital': current_capital,
        'total_trades': len(trades),
        'win_rate': win_rate,
        'max_drawdown': max_drawdown,
        'trades': trades
    }

def calculate_pnl(entry_price, exit_price, capital, position_type):
    """PnL 계산"""
    if position_type == 'long':
        return (exit_price - entry_price) / entry_price * capital
    else:  # short
        return (entry_price - exit_price) / entry_price * capital

def calculate_max_drawdown(initial_capital, trades):
    """최대 낙폭 계산"""
    if not trades:
        return 0.0
    
    capital_series = [initial_capital]
    for trade in trades:
        capital_series.append(capital_series[-1] + trade['pnl'])
    
    capital_series = np.array(capital_series)
    peak = np.maximum.accumulate(capital_series)
    drawdown = (peak - capital_series) / peak * 100
    
    return np.max(drawdown)

def main():
    """메인 실행 함수"""
    print("=== 최적화된 적응형 트레이딩 시스템 (2018-2025) ===")
    
    # 2018-2025년 데이터 로드
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
    
    if all_data:
        combined_data = pd.concat(all_data, ignore_index=False).sort_index()
        print(f"전체 데이터: {len(combined_data)}개 캔들")
        print(f"데이터 기간: {combined_data.index.min()} ~ {combined_data.index.max()}")
        
        # 연도별 성과 분석 실행
        yearly_results = run_yearly_analysis(combined_data, 2018, 2025)
        
        if yearly_results:
            # 결과 저장
            output = {
                'system_type': 'Optimized Adaptive Trading System',
                'test_period': '2018-01-01 ~ 2025-12-31',
                'yearly_results': yearly_results,
                'summary': {
                    'total_years': len([y for y in yearly_results.values() if y['total_trades'] > 0]),
                    'total_trades': sum([y['total_trades'] for y in yearly_results.values()]),
                    'final_capital': yearly_results[2025]['final_capital'],
                    'total_return': (yearly_results[2025]['final_capital'] - 10000) / 10000 * 100
                },
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open('yearly_analysis_results.json', 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            print(f"\n결과가 yearly_analysis_results.json에 저장되었습니다.")
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
