"""
디테일한 MA 최적화 시스템
- 더 정밀한 파라미터 탐색
- 상세한 성과 분석
- 시각화 및 리포트 생성
"""

import pandas as pd
import numpy as np
import itertools
from datetime import datetime, timedelta
import warnings
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
warnings.filterwarnings('ignore')

class DetailedMAOptimizer:
    def __init__(self, symbol='BTCUSDT', start_date='2021-01-01', end_date='2024-12-31'):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.data = None
        self.optimization_results = []
        self.best_params = None
        
    def load_data(self):
        """로컬 CSV 데이터 로딩"""
        print(f"데이터 로딩 중... ({self.start_date} ~ {self.end_date})")
        
        try:
            import glob
            
            # 데이터 폴더 경로
            data_folder = "data/BTCUSDT/5m"
            csv_files = glob.glob(f"{data_folder}/BTCUSDT_5m_*.csv")
            csv_files.sort()
            
            all_data = []
            
            for file_path in csv_files:
                # 파일명에서 연도 추출
                year = file_path.split('_')[-1].split('.')[0]
                
                # 요청된 기간에 해당하는 파일만 로드
                if int(year) >= int(self.start_date[:4]) and int(year) <= int(self.end_date[:4]):
                    print(f"로딩 중: {file_path}")
                    df_year = pd.read_csv(file_path)
                    df_year['timestamp'] = pd.to_datetime(df_year['timestamp'])
                    df_year.set_index('timestamp', inplace=True)
                    all_data.append(df_year)
            
            if not all_data:
                print("해당 기간의 데이터 파일을 찾을 수 없습니다.")
                return False
            
            # 모든 연도 데이터 합치기
            self.data = pd.concat(all_data, ignore_index=False)
            self.data.sort_index(inplace=True)
            
            # 요청된 기간으로 필터링
            start_dt = pd.to_datetime(self.start_date)
            end_dt = pd.to_datetime(self.end_date)
            self.data = self.data[(self.data.index >= start_dt) & (self.data.index <= end_dt)]
            
            print(f"데이터 로딩 완료: {len(self.data)}개 캔들 (5분봉)")
            return True
            
        except Exception as e:
            print(f"데이터 로딩 실패: {e}")
            return False
    
    def calculate_advanced_indicators(self, sma_short, sma_long):
        """고급 지표 계산"""
        # 기본 SMA
        self.data['sma_short'] = self.data['close'].rolling(window=sma_short).mean()
        self.data['sma_long'] = self.data['close'].rolling(window=sma_long).mean()
        
        # RSI (14기간)
        delta = self.data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        self.data['rsi'] = 100 - (100 / (1 + rs))
        
        # ATR (14기간)
        high_low = self.data['high'] - self.data['low']
        high_close = np.abs(self.data['high'] - self.data['close'].shift())
        low_close = np.abs(self.data['low'] - self.data['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        self.data['atr'] = true_range.rolling(14).mean()
        
        # 볼린저 밴드
        bb_period = 20
        bb_std = 2
        self.data['bb_middle'] = self.data['close'].rolling(bb_period).mean()
        bb_std_val = self.data['close'].rolling(bb_period).std()
        self.data['bb_upper'] = self.data['bb_middle'] + (bb_std_val * bb_std)
        self.data['bb_lower'] = self.data['bb_middle'] - (bb_std_val * bb_std)
        
        # MACD
        ema_12 = self.data['close'].ewm(span=12).mean()
        ema_26 = self.data['close'].ewm(span=26).mean()
        self.data['macd'] = ema_12 - ema_26
        self.data['macd_signal'] = self.data['macd'].ewm(span=9).mean()
        self.data['macd_histogram'] = self.data['macd'] - self.data['macd_signal']
        
        # 스토캐스틱
        low_14 = self.data['low'].rolling(14).min()
        high_14 = self.data['high'].rolling(14).max()
        self.data['stoch_k'] = 100 * (self.data['close'] - low_14) / (high_14 - low_14)
        self.data['stoch_d'] = self.data['stoch_k'].rolling(3).mean()
        
        # 거래량 지표
        self.data['volume_sma'] = self.data['volume'].rolling(20).mean()
        self.data['volume_ratio'] = self.data['volume'] / self.data['volume_sma']
    
    def generate_advanced_signals(self, sma_short, sma_long):
        """고급 매매 신호 생성 (BB 지표 강화)"""
        price = self.data['close']
        sma_short_series = self.data['sma_short']
        sma_long_series = self.data['sma_long']
        rsi = self.data['rsi']
        bb_upper = self.data['bb_upper']
        bb_lower = self.data['bb_lower']
        bb_middle = self.data['bb_middle']
        macd = self.data['macd']
        macd_signal = self.data['macd_signal']
        stoch_k = self.data['stoch_k']
        stoch_d = self.data['stoch_d']
        volume_ratio = self.data['volume_ratio']
        
        # BB 지표 추가 계산 (NaN 처리)
        bb_width = ((bb_upper - bb_lower) / bb_middle).fillna(0)  # BB 폭 (변동성)
        bb_position = ((price - bb_lower) / (bb_upper - bb_lower)).fillna(0.5)  # BB 내 위치 (0-1)
        
        # BB 밴드 터치 감지 (NaN 처리)
        bb_lower_touch = ((price <= bb_lower * 1.02) & (price > bb_lower * 0.98)).fillna(False)  # 하단 터치
        bb_upper_touch = ((price >= bb_upper * 0.98) & (price < bb_upper * 1.02)).fillna(False)  # 상단 터치
        
        # BB 밴드 수축/확장 감지 (NaN 처리)
        bb_width_mean = bb_width.rolling(20).mean()
        bb_squeeze = (bb_width < bb_width_mean * 0.8).fillna(False)  # 밴드 수축
        bb_expansion = (bb_width > bb_width_mean * 1.2).fillna(False)  # 밴드 확장
        
        # 매수 조건 (BB 지표 강화)
        buy_condition = (
            # 기본 MA 조건
            (price > sma_long_series) &  # 가격이 장기선 위
            (sma_short_series > sma_long_series) &  # 단기선이 장기선 위
            
            # BB 지표 조건 (강화)
            (
                # 하단 터치 + 반등
                (bb_lower_touch & (price > price.shift(1))) |
                # BB 하단 근처 + RSI 과매도
                (bb_position < 0.2 & rsi < 40) |
                # BB 중앙선 돌파
                (price > bb_middle & price.shift(1) <= bb_middle)
            ) &
            
            # 추가 필터
            (rsi > 25) & (rsi < 75) &  # RSI 적정 범위
            (macd > macd_signal) &  # MACD 골든크로스
            (stoch_k > 15) & (stoch_k < 85) &  # 스토캐스틱 적정 범위
            (volume_ratio > 1.1) &  # 거래량 증가
            (~bb_squeeze)  # 밴드 수축 시 거래 안함
        )
        
        # 매도 조건 (BB 지표 강화)
        sell_condition = (
            # 기본 MA 조건
            (price < sma_long_series) |  # 가격이 장기선 아래
            (sma_short_series < sma_long_series) |  # 단기선이 장기선 아래
            
            # BB 지표 조건 (강화)
            (
                # 상단 터치 + 하락
                (bb_upper_touch & (price < price.shift(1))) |
                # BB 상단 근처 + RSI 과매수
                (bb_position > 0.8 & rsi > 60) |
                # BB 중앙선 이탈
                (price < bb_middle & price.shift(1) >= bb_middle)
            ) |
            
            # 추가 필터
            (rsi > 85) |  # RSI 과매수
            (macd < macd_signal) |  # MACD 데드크로스
            (stoch_k > 85)  # 스토캐스틱 과매수
        )
        
        # 신호 생성
        signals = pd.Series(0, index=self.data.index)
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        
        # 신호 정리
        signal_changes = signals.diff() != 0
        signal_changes.iloc[0] = True
        signals[~signal_changes] = 0
        signals = signals.replace(0, method='ffill').fillna(0)
        
        return signals
    
    def calculate_detailed_metrics(self, trades_df, initial_capital, final_capital):
        """상세한 성과 지표 계산"""
        if len(trades_df) == 0:
            return {
                'total_return': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'sortino_ratio': 0,
                'calmar_ratio': 0,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'max_win': 0,
                'max_loss': 0,
                'avg_trade_duration': 0
            }
        
        # 기본 통계
        total_return = (final_capital - initial_capital) / initial_capital * 100
        
        # 거래 통계
        winning_trades = trades_df[trades_df['pnl'] > 0]
        losing_trades = trades_df[trades_df['pnl'] < 0]
        
        win_rate = len(winning_trades) / len(trades_df) * 100
        avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
        avg_loss = losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0
        
        # 수익 팩터
        total_wins = winning_trades['pnl'].sum() if len(winning_trades) > 0 else 0
        total_losses = abs(losing_trades['pnl'].sum()) if len(losing_trades) > 0 else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # 최대 낙폭
        pnl_values = trades_df['pnl'].values
        cumulative_pnl = np.cumsum(pnl_values)
        capital_history = initial_capital + cumulative_pnl
        
        peak = np.maximum.accumulate(capital_history)
        drawdown = (peak - capital_history) / peak * 100
        max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
        
        # 샤프 비율 (간단한 계산)
        if len(pnl_values) > 1:
            returns = pnl_values / initial_capital
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe_ratio = 0
        
        # 소르티노 비율
        if len(pnl_values) > 1:
            negative_returns = returns[returns < 0]
            sortino_ratio = np.mean(returns) / np.std(negative_returns) * np.sqrt(252) if len(negative_returns) > 0 and np.std(negative_returns) > 0 else 0
        else:
            sortino_ratio = 0
        
        # 칼마 비율
        calmar_ratio = total_return / max_dd if max_dd > 0 else 0
        
        # 최대 수익/손실
        max_win = winning_trades['pnl'].max() if len(winning_trades) > 0 else 0
        max_loss = losing_trades['pnl'].min() if len(losing_trades) > 0 else 0
        
        # 평균 거래 기간
        if 'duration' in trades_df.columns:
            avg_trade_duration = trades_df['duration'].mean()
        else:
            avg_trade_duration = 0
        
        return {
            'total_return': total_return,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_dd,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'total_trades': len(trades_df),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'max_win': max_win,
            'max_loss': max_loss,
            'avg_trade_duration': avg_trade_duration
        }
    
    def run_detailed_backtest(self, sma_short, sma_long, start_idx, end_idx):
        """상세한 백테스트 실행 (수수료 포함)"""
        # 데이터 슬라이싱
        test_data = self.data.iloc[start_idx:end_idx].copy()
        
        # 고급 지표 계산
        self.calculate_advanced_indicators(sma_short, sma_long)
        
        # 고급 신호 생성
        signals = self.generate_advanced_signals(sma_short, sma_long)
        
        # 백테스트 실행 (수수료 포함)
        initial_capital = 10000
        capital = initial_capital
        position_size = 0
        entry_price = 0
        entry_time = None
        trades = []
        
        # 수수료 설정 (올바른 계산)
        BUY_FEE_RATE = 0.0005  # 0.05% = 0.0005
        SELL_FEE_RATE = 0.0005  # 0.05% = 0.0005
        
        # 신호 변화점 찾기
        signal_changes = signals.diff() != 0
        signal_changes.iloc[0] = True
        
        buy_signals = (signals == 1) & signal_changes
        sell_signals = (signals == -1) & signal_changes
        
        buy_indices = test_data[buy_signals].index
        sell_indices = test_data[sell_signals].index
        
        # 모든 이벤트를 시간순으로 정렬
        all_events = []
        for idx in buy_indices:
            all_events.append((idx, 'buy', test_data.loc[idx, 'close']))
        for idx in sell_indices:
            all_events.append((idx, 'sell', test_data.loc[idx, 'close']))
        
        all_events.sort(key=lambda x: x[0])
        
        # 거래 추적 변수
        buy_fee = 0
        
        for timestamp, action, price in all_events:
            if action == 'buy' and position_size == 0:
                # 매수 (수수료 포함) - 올바른 계산
                available_capital = capital * 0.95
                buy_fee = available_capital * BUY_FEE_RATE  # 매수 수수료
                net_capital = available_capital - buy_fee
                position_size = net_capital / price
                
                entry_price = price
                entry_time = timestamp
                capital -= available_capital  # 수수료 포함한 전체 금액
                
            elif action == 'sell' and position_size > 0:
                # 매도 (수수료 포함) - 올바른 계산
                gross_proceeds = position_size * price
                sell_fee = gross_proceeds * SELL_FEE_RATE  # 매도 수수료
                net_proceeds = gross_proceeds - sell_fee
                
                # PnL 계산: 매도 수익 - 매수 비용 (수수료 포함)
                buy_cost = position_size * entry_price + buy_fee
                pnl = net_proceeds - buy_cost
                capital += net_proceeds
                
                duration = (timestamp - entry_time).total_seconds() / 3600  # 시간 단위
                
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': timestamp,
                    'entry_price': entry_price,
                    'exit_price': price,
                    'pnl': pnl,
                    'duration': duration,
                    'buy_fee': buy_fee,
                    'sell_fee': sell_fee
                })
                
                position_size = 0
                entry_price = 0
                entry_time = None
                buy_fee = 0  # 리셋
        
        # 최종 포지션 청산 (수수료 포함)
        if position_size > 0:
            final_price = test_data['close'].iloc[-1]
            final_time = test_data.index[-1]
            
            gross_proceeds = position_size * final_price
            sell_fee = gross_proceeds * SELL_FEE_RATE  # 매도 수수료
            net_proceeds = gross_proceeds - sell_fee
            
            # PnL 계산: 매도 수익 - 매수 비용 (수수료 포함)
            buy_cost = position_size * entry_price + buy_fee
            pnl = net_proceeds - buy_cost
            capital += net_proceeds
            
            duration = (final_time - entry_time).total_seconds() / 3600
            
            trades.append({
                'entry_time': entry_time,
                'exit_time': final_time,
                'entry_price': entry_price,
                'exit_price': final_price,
                'pnl': pnl,
                'duration': duration,
                'buy_fee': buy_fee,
                'sell_fee': sell_fee
            })
        
        # 상세한 성과 지표 계산
        trades_df = pd.DataFrame(trades)
        metrics = self.calculate_detailed_metrics(trades_df, initial_capital, capital)
        
        return {
            'sma_short': sma_short,
            'sma_long': sma_long,
            'final_capital': capital,
            'trades': trades,
            **metrics
        }
    
    def optimize_ma_parameters_detailed(self):
        """디테일한 MA 파라미터 최적화"""
        print("=== 디테일한 MA 파라미터 최적화 시작 ===")
        
        # 3년치 데이터 (2021-2023)
        train_start = pd.to_datetime('2021-01-01')
        train_end = pd.to_datetime('2023-12-31')
        
        train_data = self.data[(self.data.index >= train_start) & (self.data.index <= train_end)]
        train_start_idx = self.data.index.get_loc(train_data.index[0])
        train_end_idx = self.data.index.get_loc(train_data.index[-1])
        
        print(f"훈련 데이터: {len(train_data)}개 캔들")
        
        # 더 정밀한 MA 파라미터 조합
        sma_short_range = range(5, 31, 1)  # 5, 6, 7, ..., 30
        sma_long_range = range(20, 121, 5)  # 20, 25, 30, ..., 120
        
        best_result = None
        best_score = -np.inf
        
        total_combinations = len(sma_short_range) * len(sma_long_range)
        current_combination = 0
        
        print(f"총 {total_combinations}개 조합 테스트 예정...")
        
        for sma_short in sma_short_range:
            for sma_long in sma_long_range:
                if sma_short >= sma_long:
                    continue
                    
                current_combination += 1
                
                if current_combination % 50 == 0:
                    print(f"진행률: {current_combination}/{total_combinations} ({current_combination/total_combinations*100:.1f}%)")
                
                try:
                    result = self.run_detailed_backtest(sma_short, sma_long, train_start_idx, train_end_idx)
                    
                    # 복합 점수 계산 (여러 지표 고려)
                    score = (
                        result['total_return'] * 0.3 +  # 수익률 30%
                        (100 - result['max_drawdown']) * 0.2 +  # 낙폭 20%
                        result['win_rate'] * 0.2 +  # 승률 20%
                        result['profit_factor'] * 10 * 0.15 +  # 수익팩터 15%
                        result['sharpe_ratio'] * 10 * 0.15  # 샤프비율 15%
                    )
                    
                    if score > best_score:
                        best_score = score
                        best_result = result
                        print(f"  → 새로운 최고 점수: {score:.2f}")
                        print(f"    SMA({sma_short}, {sma_long}) - 수익률: {result['total_return']:.2f}%, MDD: {result['max_drawdown']:.2f}%, 승률: {result['win_rate']:.2f}%")
                    
                    self.optimization_results.append(result)
                    
                except Exception as e:
                    print(f"  → 오류 (SMA {sma_short}, {sma_long}): {e}")
                    continue
        
        print(f"\n=== 최적화 완료 ===")
        print(f"최적 파라미터: SMA({best_result['sma_short']}, {best_result['sma_long']})")
        print(f"최고 점수: {best_score:.2f}")
        print(f"수익률: {best_result['total_return']:.2f}%")
        print(f"최대낙폭: {best_result['max_drawdown']:.2f}%")
        print(f"승률: {best_result['win_rate']:.2f}%")
        print(f"수익팩터: {best_result['profit_factor']:.2f}")
        print(f"샤프비율: {best_result['sharpe_ratio']:.2f}")
        
        self.best_params = best_result
        return best_result
    
    def test_on_final_year_detailed(self):
        """마지막 1년치 상세 백테스트"""
        print("\n=== 마지막 1년치 상세 백테스트 ===")
        
        # 마지막 1년치 데이터 (2024)
        test_start = pd.to_datetime('2024-01-01')
        test_end = pd.to_datetime('2024-12-31')
        
        test_data = self.data[(self.data.index >= test_start) & (self.data.index <= test_end)]
        test_start_idx = self.data.index.get_loc(test_data.index[0])
        test_end_idx = self.data.index.get_loc(test_data.index[-1])
        
        print(f"테스트 데이터: {len(test_data)}개 캔들")
        
        # 최적 파라미터로 백테스트
        result = self.run_detailed_backtest(
            self.best_params['sma_short'], 
            self.best_params['sma_long'],
            test_start_idx,
            test_end_idx
        )
        
        print(f"\n=== 최종 상세 백테스트 결과 ===")
        print(f"테스트 기간: 2024년 (1년)")
        print(f"MA 파라미터: SMA({result['sma_short']}, {result['sma_long']})")
        print(f"초기 자본금: $10,000")
        print(f"최종 자본금: ${result['final_capital']:,.2f}")
        print(f"총 수익률: {result['total_return']:.2f}%")
        print(f"총 거래 수: {result['total_trades']}")
        print(f"승률: {result['win_rate']:.2f}%")
        print(f"평균 수익: ${result['avg_win']:.2f}")
        print(f"평균 손실: ${result['avg_loss']:.2f}")
        print(f"수익 팩터: {result['profit_factor']:.2f}")
        print(f"최대 낙폭: {result['max_drawdown']:.2f}%")
        print(f"샤프 비율: {result['sharpe_ratio']:.2f}")
        print(f"소르티노 비율: {result['sortino_ratio']:.2f}")
        print(f"칼마 비율: {result['calmar_ratio']:.2f}")
        print(f"최대 수익: ${result['max_win']:.2f}")
        print(f"최대 손실: ${result['max_loss']:.2f}")
        print(f"평균 거래 기간: {result['avg_trade_duration']:.1f}시간")
        
        # 수수료 분석
        if result['trades']:
            trades_df = pd.DataFrame(result['trades'])
            total_buy_fees = trades_df['buy_fee'].sum() if 'buy_fee' in trades_df.columns else 0
            total_sell_fees = trades_df['sell_fee'].sum() if 'sell_fee' in trades_df.columns else 0
            total_fees = total_buy_fees + total_sell_fees
            
            print(f"\n=== 수수료 분석 ===")
            print(f"총 매수 수수료: ${total_buy_fees:.2f}")
            print(f"총 매도 수수료: ${total_sell_fees:.2f}")
            print(f"총 수수료: ${total_fees:.2f}")
            print(f"수수료 비율: {total_fees / 10000 * 100:.2f}%")
        
        return result
    
    def generate_optimization_report(self):
        """최적화 리포트 생성"""
        if not self.optimization_results:
            print("최적화 결과가 없습니다.")
            return
        
        print("\n=== 최적화 결과 분석 ===")
        
        # 결과를 DataFrame으로 변환
        results_df = pd.DataFrame(self.optimization_results)
        
        # 상위 10개 결과
        top_10 = results_df.nlargest(10, 'total_return')
        
        print("\n상위 10개 결과:")
        print(top_10[['sma_short', 'sma_long', 'total_return', 'max_drawdown', 'win_rate', 'profit_factor']].to_string())
        
        # 통계 분석
        print(f"\n통계 분석:")
        print(f"평균 수익률: {results_df['total_return'].mean():.2f}%")
        print(f"수익률 표준편차: {results_df['total_return'].std():.2f}%")
        print(f"최고 수익률: {results_df['total_return'].max():.2f}%")
        print(f"최저 수익률: {results_df['total_return'].min():.2f}%")
        print(f"양수 수익률 비율: {(results_df['total_return'] > 0).mean() * 100:.1f}%")
        
        # 파라미터별 성과 분석
        print(f"\n파라미터별 성과:")
        short_ma_performance = results_df.groupby('sma_short')['total_return'].mean().sort_values(ascending=False)
        print(f"단기 MA 상위 5개: {short_ma_performance.head().to_dict()}")
        
        long_ma_performance = results_df.groupby('sma_long')['total_return'].mean().sort_values(ascending=False)
        print(f"장기 MA 상위 5개: {long_ma_performance.head().to_dict()}")
    
    def run(self):
        """전체 실행"""
        print("=== 디테일한 MA 최적화 및 백테스트 시스템 ===")
        
        # 1. 데이터 로딩
        if not self.load_data():
            return False
        
        # 2. 디테일한 MA 파라미터 최적화
        best_params = self.optimize_ma_parameters_detailed()
        
        # 3. 최적화 리포트 생성
        self.generate_optimization_report()
        
        # 4. 마지막 1년치 상세 백테스트
        final_result = self.test_on_final_year_detailed()
        
        return final_result

if __name__ == "__main__":
    # 디테일한 최적화 및 백테스트 실행
    optimizer = DetailedMAOptimizer(
        symbol='BTCUSDT',
        start_date='2021-01-01',
        end_date='2024-12-31'
    )
    
    results = optimizer.run()
