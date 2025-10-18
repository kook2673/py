"""
통합 전략 최적화 시스템 (15분봉)

=== 사용된 기술적 지표 및 전략 ===

1. 이동평균선 (Moving Average)
   - SMA Short: 단기 이동평균선 (3, 6, 9, 12, 15)
   - SMA Long: 장기 이동평균선 (20, 30, 40, 50)
   - 역할: 추세 방향 판단
   - 신호: 단기선이 장기선을 상향돌파 → 롱 신호, 하향돌파 → 숏 신호

2. 던키안 채널 (Donchian Channel)
   - DCC Period: 25 (고정)
   - DCC High: 25기간 최고가
   - DCC Low: 25기간 최저가
   - DCC Middle: (최고가 + 최저가) / 2
   - 역할: 변동성과 돌파 신호 판단
   - 롱 조건: 현재가 > DCC Middle & 현재가 > DCC Low * 1.02
   - 숏 조건: 현재가 < DCC Middle & 현재가 < DCC High * 0.98

3. RSI (Relative Strength Index)
   - 기간: 14 (고정)
   - 계산: RSI = 100 - (100 / (1 + RS))
   - RS = 평균 상승폭 / 평균 하락폭
   - 역할: 과매수/과매도 구간 판단
   - 롱 조건: RSI < 70 (과매수 아님)
   - 숏 조건: RSI > 30 (과매도 아님)
   - 청산 조건: 롱 RSI > 80, 숏 RSI < 20

4. 통합 전략 특징
   - 롱/숏 동시 진입 방지: 충돌 신호 시 우선순위 적용
   - 볼륨 필터 제거: 2025년 시장 특성 고려
   - 수수료 고려: 진입/청산 시 각각 0.05% 수수료 적용
   - 레버리지: 1.0배 (현물 거래 기준)

5. 백테스트 방식
   - 데이터: 2024년 최적화, 2025년 테스트
   - 리샘플링: 5분봉 → 15분봉
   - 최적화 기준: 수익률 - 최대낙폭 (샤프 비율 고려)
   - 포지션 관리: 단일 포지션 유지 (롱 또는 숏)

6. 리스크 관리
   - 최대 낙폭(MDD) 추적
   - 승률 계산
   - 거래 빈도 모니터링
   - 롱/숏 거래 비율 분석

=== 파라미터 최적화 범위 ===
- SMA Short: 3, 6, 9, 12, 15 (5개)
- SMA Long: 20, 30, 40, 50 (4개)  
- DCC Period: 25 (고정)
- 총 조합: 5 × 4 × 1 = 20개

=== 전략 로직 ===
1. 진입 조건 (모두 만족해야 함):
   - 이동평균선 크로스오버
   - 던키안 채널 조건
   - RSI 과매수/과매도 아님

2. 청산 조건 (하나라도 만족하면):
   - 반대 신호 발생
   - RSI 극값 도달 (80/20)

3. 동시 진입 방지:
   - 롱/숏 신호 동시 발생 시 충돌 처리
   - 우선순위에 따른 신호 선택
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class SeparateLongShortOptimize:
    def __init__(self, enable_tuning=True):
        self.data = None
        self.optimization_data = None  # 2024년 데이터
        self.test_data = None  # 2025년 데이터
        self.best_long_params = None
        self.best_short_params = None
        self.enable_tuning = enable_tuning  # 튜닝 활성화 여부
        
        # 최적 파라미터 (튜닝 비활성화 시 사용)
        self.optimal_params = self.load_optimal_params()
    
    def load_optimal_params(self):
        """최적 파라미터 로드"""
        try:
            with open('ma_dcc_backtest_results.json', 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            # combined_optimal에서 파라미터 추출
            if 'combined_optimal' in results and 'params' in results['combined_optimal']:
                params = results['combined_optimal']['params'].copy()
                print(f"최적 파라미터 로드됨: {params}")
                return params
            else:
                print("최적 파라미터를 찾을 수 없습니다. 기본값 사용.")
                return self.get_default_params()
                
        except FileNotFoundError:
            print("결과 파일을 찾을 수 없습니다. 기본값 사용.")
            return self.get_default_params()
        except Exception as e:
            print(f"파라미터 로드 오류: {e}. 기본값 사용.")
            return self.get_default_params()
    
    def get_default_params(self):
        """기본 파라미터 반환"""
        return {
            'sma_short': 6,
            'sma_long': 20,
            'dcc_period': 25
        }
        
    def load_data(self):
        """데이터 로드 - 2024년(최적화용), 2025년(테스트용)"""
        print("데이터 로딩 중...")
        
        # 2024년 데이터 (최적화용)
        optimization_file = "data/BTCUSDT/5m/BTCUSDT_5m_2024.csv"
        if os.path.exists(optimization_file):
            df = pd.read_csv(optimization_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            self.optimization_data = df
            print(f"최적화용 데이터 로드: {optimization_file}")
            print(f"최적화용 데이터 (2024년): {len(self.optimization_data)}개 캔들")
            print(f"기간: {self.optimization_data.index.min()} ~ {self.optimization_data.index.max()}")
        else:
            print("2024년 데이터 파일을 찾을 수 없습니다.")
            return
        
        # 2025년 데이터 (테스트용)
        test_file = "data/BTCUSDT/5m/BTCUSDT_5m_2025.csv"
        if os.path.exists(test_file):
            df = pd.read_csv(test_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            self.test_data = df
            print(f"테스트용 데이터 (2025년): {len(self.test_data)}개 캔들")
            print(f"기간: {self.test_data.index.min()} ~ {self.test_data.index.max()}")
        else:
            print("2025년 데이터 파일을 찾을 수 없습니다.")
            return
        
        # 5분봉을 15분봉으로 리샘플링
        print("5분봉을 15분봉으로 리샘플링 중...")
        
        if self.optimization_data is not None:
            self.optimization_data = self.optimization_data.resample('15T').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            print(f"최적화용 리샘플링 완료: {len(self.optimization_data)}개 캔들")
        
        if self.test_data is not None:
            self.test_data = self.test_data.resample('15T').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            print(f"테스트용 리샘플링 완료: {len(self.test_data)}개 캔들")
    
    def calculate_indicators(self, data, sma_short, sma_long, dcc_period, volume_threshold=1.0):
        """기술적 지표 계산"""
        df = data.copy()
        
        # 이동평균
        df['sma_short'] = df['close'].rolling(sma_short).mean()
        df['sma_long'] = df['close'].rolling(sma_long).mean()
        
        # 던키안 채널
        df['dcc_high'] = df['high'].rolling(dcc_period).max()
        df['dcc_low'] = df['low'].rolling(dcc_period).min()
        df['dcc_middle'] = (df['dcc_high'] + df['dcc_low']) / 2
        
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 볼륨 필터링
        df['volume_ma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        df['volume_filter'] = df['volume_ratio'] >= volume_threshold
        
        return df
    
    def generate_combined_signals(self, df):
        """롱/숏 통합 신호 생성 (볼륨 필터 없음)"""
        # 롱 신호
        long_ma_signal = (df['sma_short'] > df['sma_long']) & (df['sma_short'].shift(1) <= df['sma_long'].shift(1))
        long_dcc_signal = (df['close'] > df['dcc_middle']) & (df['close'] > df['dcc_low'] * 1.02)
        long_rsi_signal = df['rsi'] < 70
        
        # 숏 신호
        short_ma_signal = (df['sma_short'] < df['sma_long']) & (df['sma_short'].shift(1) >= df['sma_long'].shift(1))
        short_dcc_signal = (df['close'] < df['dcc_middle']) & (df['close'] < df['dcc_high'] * 0.98)
        short_rsi_signal = df['rsi'] > 30
        
        # 최종 신호 (볼륨 필터 제거)
        long_signal = long_ma_signal & long_dcc_signal & long_rsi_signal
        short_signal = short_ma_signal & short_dcc_signal & short_rsi_signal
        
        # 동시 진입 방지
        conflict_mask = long_signal & short_signal
        long_signal = long_signal & ~conflict_mask
        short_signal = short_signal & ~conflict_mask
        
        df['long_signal'] = long_signal
        df['short_signal'] = short_signal
        df['conflict_count'] = conflict_mask.sum()
        
        return df
    
    def run_combined_backtest(self, data, initial_capital=10000, leverage_ratio=1.0):
        """통합 전략 백테스트 실행"""
        df = data.copy()
        df = df.dropna()
        
        if len(df) == 0:
            return {
                'total_return': 0.0,
                'final_capital': initial_capital,
                'total_trades': 0,
                'win_rate': 0.0,
                'max_drawdown': 0.0,
                'long_trades': 0,
                'short_trades': 0
            }
        
        # 포지션 상태 추적
        position = None
        entry_price = 0
        trades = []
        capital = initial_capital
        
        for i, (timestamp, row) in enumerate(df.iterrows()):
            # 진입 신호
            if position is None:
                if row['long_signal']:
                    position = 'long'
                    entry_price = row['close']
                elif row['short_signal']:
                    position = 'short'
                    entry_price = row['close']
            
            # 청산 신호
            elif position == 'long':
                if row['short_signal'] or row['rsi'] > 80:
                    # 롱 청산
                    exit_price = row['close']
                    pnl = self._calculate_pnl(entry_price, exit_price, capital, leverage_ratio, 'long')
                    capital += pnl
                    trades.append({'type': 'long', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl})
                    position = None
                    
            elif position == 'short':
                if row['long_signal'] or row['rsi'] < 20:
                    # 숏 청산
                    exit_price = row['close']
                    pnl = self._calculate_pnl(entry_price, exit_price, capital, leverage_ratio, 'short')
                    capital += pnl
                    trades.append({'type': 'short', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl})
                    position = None
        
        # 결과 계산
        if len(trades) > 0:
            total_return = (capital - initial_capital) / initial_capital * 100
            winning_trades = len([t for t in trades if t['pnl'] > 0])
            win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0
            max_drawdown = self._calculate_max_drawdown(initial_capital, trades)
            long_trades = len([t for t in trades if t['type'] == 'long'])
            short_trades = len([t for t in trades if t['type'] == 'short'])
        else:
            total_return = 0.0
            win_rate = 0.0
            max_drawdown = 0.0
            long_trades = 0
            short_trades = 0
        
        return {
            'total_return': total_return,
            'final_capital': capital,
            'total_trades': len(trades),
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'long_trades': long_trades,
            'short_trades': short_trades
        }
    
    def _calculate_pnl(self, entry_price, exit_price, capital, leverage_ratio, position_type):
        """PnL 계산 (수수료 포함)"""
        fee_rate = 0.0005  # 0.05% 수수료
        leveraged_capital = capital * leverage_ratio
        
        if position_type == 'long':
            # 롱 거래: 진입 시 수수료 차감, 청산 시 수수료 차감
            entry_with_fee = entry_price * (1 + fee_rate)  # 진입 시 수수료 포함
            exit_with_fee = exit_price * (1 - fee_rate)    # 청산 시 수수료 차감
            amount = leveraged_capital / entry_with_fee
            pnl = (exit_with_fee - entry_with_fee) * amount
        else:  # short
            # 숏 거래: 진입 시 수수료 차감, 청산 시 수수료 포함
            entry_with_fee = entry_price * (1 - fee_rate)  # 진입 시 수수료 차감
            exit_with_fee = exit_price * (1 + fee_rate)    # 청산 시 수수료 포함
            amount = leveraged_capital / entry_with_fee
            pnl = (entry_with_fee - exit_with_fee) * amount
        
        return pnl
    
    def _calculate_max_drawdown(self, initial_capital, trades):
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
    
    def optimize_combined_parameters(self):
        """통합 전략 파라미터 최적화 (볼륨 필터 없음)"""
        print("=== 통합 전략 파라미터 최적화 시작 ===")
        
        if not self.enable_tuning:
            print("튜닝 비활성화됨. 최적 파라미터 사용:")
            print(f"MA_SHORT: {self.optimal_params['sma_short']}")
            print(f"MA_LONG: {self.optimal_params['sma_long']}")
            print(f"DCC_PERIOD: {self.optimal_params['dcc_period']}")
            
            # 최적 파라미터로 결과 반환
            return {
                'total_return': 0.0,
                'final_capital': 10000,
                'total_trades': 0,
                'win_rate': 0.0,
                'max_drawdown': 0.0,
                'long_trades': 0,
                'short_trades': 0,
                'params': self.optimal_params
            }
        
        if self.optimization_data is None:
            print("최적화용 데이터가 없습니다.")
            return None
        
        best_result = None
        best_score = -999999
        
        # 파라미터 범위 (통합 전략)
        sma_short_range = range(3, 16, 3)  # 3, 6, 9, 12, 15
        sma_long_range = range(20, 41, 10)  # 20, 30, 40, 50
        dcc_period_range = [25]  # 25로 고정
        
        total_combinations = len(sma_short_range) * len(sma_long_range) * len(dcc_period_range)
        print(f"총 {total_combinations}개 조합 테스트 중...")
        
        combination_count = 0
        for sma_short in sma_short_range:
            for sma_long in sma_long_range:
                if sma_short >= sma_long:
                    continue
                    
                for dcc_period in dcc_period_range:
                    combination_count += 1
                    
                    if combination_count % 20 == 0:
                        print(f"진행률: {combination_count}/{total_combinations}")
                    
                    try:
                        # 지표 계산 (볼륨 필터 제거)
                        df = self.calculate_indicators(
                            self.optimization_data, 
                            sma_short, sma_long, 
                            dcc_period, volume_threshold=1.0  # 사용하지 않음
                        )
                        df = self.generate_combined_signals(df)
                        
                        # 백테스트 실행
                        result = self.run_combined_backtest(df)
                        
                        # 점수 계산 (수익률 - 최대낙폭)
                        score = result['total_return'] - result['max_drawdown']
                        
                        if score > best_score:
                            best_score = score
                            best_result = result.copy()
                            best_result['params'] = {
                                'sma_short': sma_short,
                                'sma_long': sma_long,
                                'dcc_period': dcc_period
                            }
                            
                            print(f"새로운 최고 점수: {score:.2f} (수익률: {result['total_return']:.2f}%, MDD: {result['max_drawdown']:.2f}%)")
                            
                    except Exception as e:
                        continue
        
        print(f"\n=== 통합 전략 최적화 완료 ===")
        if best_result:
            print(f"최적 파라미터: {best_result['params']}")
            print(f"수익률: {best_result['total_return']:.2f}%")
            print(f"승률: {best_result['win_rate']:.2f}%")
            print(f"최대낙폭: {best_result['max_drawdown']:.2f}%")
            print(f"총 거래 수: {best_result['total_trades']} (롱: {best_result['long_trades']}, 숏: {best_result['short_trades']})")
            
            self.best_long_params = best_result['params']  # 통합 파라미터 저장
        
        return best_result
    
    
    def test_combined_on_2025(self):
        """2025년 전체 데이터로 통합 전략 테스트"""
        print("\n=== 2025년 전체 데이터로 통합 전략 백테스트 ===")
        
        if self.test_data is None:
            print("2025년 테스트 데이터가 없습니다.")
            return None
        
        if self.best_long_params is None and self.enable_tuning:
            print("최적 파라미터가 없습니다.")
            return None
        
        # 통합 전략 테스트
        print("통합 전략 테스트...")
        if not self.enable_tuning:
            # 튜닝 비활성화 시 최적 파라미터 사용
            params = self.optimal_params
        else:
            # 튜닝 활성화 시 최적화된 파라미터 사용
            params = self.best_long_params
            
        df_combined = self.calculate_indicators(
            self.test_data,
            params['sma_short'],
            params['sma_long'],
            params['dcc_period'],
            volume_threshold=1.0  # 사용하지 않음
        )
        df_combined = self.generate_combined_signals(df_combined)
        combined_result = self.run_combined_backtest(df_combined)
        
        print(f"\n=== 2025년 통합 전략 테스트 결과 ===")
        print(f"수익률: {combined_result['total_return']:.2f}%")
        print(f"승률: {combined_result['win_rate']:.2f}%")
        print(f"최대낙폭: {combined_result['max_drawdown']:.2f}%")
        print(f"총 거래 수: {combined_result['total_trades']} (롱: {combined_result['long_trades']}, 숏: {combined_result['short_trades']})")
        
        return {
            'combined_result': combined_result,
            'params': params
        }

def main():
    """메인 실행 함수"""
    print("=== 2024년 통합 전략 최적화 + 2025년 백테스트 시스템 ===")
    
    # 튜닝 옵션 설정 (False로 설정하면 최적 파라미터 사용)
    enable_tuning = False  # True: 최적화 실행, False: 최적 파라미터 사용
    
    # 시스템 초기화
    system = SeparateLongShortOptimize(enable_tuning=enable_tuning)
    
    # 데이터 로드
    system.load_data()
    
    # 통합 전략 최적화
    combined_optimal = system.optimize_combined_parameters()
    
    # 2025년 전체 통합 전략 테스트
    if combined_optimal:
        test_result = system.test_combined_on_2025()
        
        # 결과 저장
        results = {
            'optimization_period': '2024년',
            'test_period': '2025년 전체',
            'strategy_type': '통합 전략 (볼륨 필터 없음)',
            'combined_optimal': combined_optimal,
            'test_result': test_result,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open('ma_dcc_backtest_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n결과가 ma_dcc_backtest_results.json에 저장되었습니다.")
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
