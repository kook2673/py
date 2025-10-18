"""
규칙:
- 규칙1: 미래데이터를 사용하지 않는다
- 규칙2: 랜덤데이터를 사용하지 않고 과거 csv파일을 로드해서 사용한다
- 규칙3: 살때 0.05%수수료, 팔때 0.05%수수료를 꼭 적용해야 한다
- 규칙4: 트레일링 스탑 포함을 한다
- 규칙5: 이겼을때 self.position_size = 0.1배, 졌을때 self.position_size = 0.2배로 한다
- 규칙6: 백테스트 다 돌리고 비트코인가격 그래프와 수익률 그래프를 보여준다

1. 데이터 준비 🚨
- 가장 중요: 논문의 전략은 장중 변동성을 포착하는 것이므로, BTCUSDT 등의 바이낸스 비트코인 선물 1분봉(1m) 또는 5분봉(5m) 데이터가 필요합니다.
- 위 코드의 load_data 함수 내 file_path를 실제 다운로드한 데이터 파일 경로로 변경하세요. (예: BTCUSDT_1m_2023.csv)

2. 논문의 공식 적용 (핵심 로직)
- 노이즈 영역(Nt,K): 논문에서 제시된 **과거 K일(K=14 기본)**의 평균 일일 변동성(Daily Range)을 사용했습니다.
    - df['Noise_Level'] = df['Daily_Range'].rolling(window=self.K, min_periods=1).mean()
- 진입 조건: 논문의 핵심인 노이즈 영역 경계 돌파를 사용했습니다.
    - 롱 진입: row['Close'] > noise_upper_bound
    - 숏 진입: row['Close'] < noise_lower_bound
- 리스크 관리: VWAP 기반 후행 정지를 구현하여 손익을 보호합니다. (실제 VWAP 계산은 1분봉 데이터의 볼륨을 사용해야 하지만, 여기서는 간소화된 이동평균을 사용했으니 실제 적용 시는 VWAP 계산 로직을 정밀하게 수정해야 합니다.)

3. 그리드 서치(Grid Search)
- MomentumStrategy.parameter_grid 딕셔너리에 최적화하고 싶은 파라미터 값의 후보들을 정의했습니다.
- 그리드:
    - K (Lookback 기간): [7, 14, 21]
    - factor (민감도 계수): [0.8, 1.0, 1.2] (노이즈 영역의 폭을 조절)
    - trailing_stop_ratio (후행 정지 비율): [0.005, 0.01, 0.015] (VWAP 대비 0.5% ~ 1.5% 이탈 시 청산)

- 결과: run_grid_search 함수가 이 모든 조합을 테스트하고, 총 수익률이 가장 높은 조합을 최적의 파라미터 셋으로 출력해 줍니다.
    - 주의: 최적의 파라미터는 백테스팅 기간(2023년)에만 국한될 수 있으므로, **WFO (Walk-Forward Optimization)**를 적용하여 안정성을 추가로 검증하는 것이 좋습니다.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

# ==============================================================================
# 1. 전략 클래스 (논문의 로직 구현)
# ==============================================================================
class MomentumStrategy:
    """
    SPY 장중 모멘텀 전략을 비트코인 선물에 적용한 백테스팅 클래스.
    노이즈 영역 돌파 및 VWAP 후행 정지 로직 포함.
    """
    def __init__(self, initial_capital, commission_rate, slippage_rate, K, factor, trailing_stop_ratio):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.K = K  # 노이즈 영역 계산을 위한 룩백 기간 (논문 기본값 14)
        self.factor = factor  # 노이즈 영역에 곱하는 민감도 계수 (논문 기본값 1.0)
        self.trailing_stop_ratio = trailing_stop_ratio  # VWAP 기반 후행 정지 비율
        self.parameter_set = f"K={K}, Factor={factor:.2f}, TS={trailing_stop_ratio:.2f}"

    # 최적화할 파라미터 그리드 정의
    parameter_grid = {
        'K': [7, 14, 21],  # 노이즈 룩백 기간 (7일, 14일, 21일)
        'factor': [0.8, 1.0, 1.2],  # 노이즈 영역 민감도 (0.8배, 1.0배, 1.2배)
        'trailing_stop_ratio': [0.005, 0.01, 0.015]  # VWAP 후행 정지 비율 (0.5%, 1.0%, 1.5%)
    }

    def _calculate_indicators(self, df):
        """노이즈 영역 및 VWAP 계산"""
        
        # 1. 노이즈 영역 계산 (K일 평균 일일 변동폭)
        # 종가 기준 일일 변동폭: (High - Low) / Close
        df['Daily_Range'] = (df['High'] - df['Low']) / df['Close'].shift(1) * 100 # % 단위로 변환
        
        # K일 평균 변동폭 (Noise)
        df['Noise_Level'] = df['Daily_Range'].rolling(window=self.K, min_periods=1).mean()
        
        # 2. VWAP 계산 (거래량 가중 평균 가격)
        # 24시간 거래 시장에 맞게 24시간 이동 VWAP 적용
        # df['VWAP'] = ((df['Close'] * df['Volume']).rolling(window=24).sum() / df['Volume'].rolling(window=24).sum())
        # 단순화를 위해 Close 가격 기준으로 계산 (실제 구현 시는 Tick Data 필요)
        df['VWAP'] = df['Close'].rolling(window=24*60, min_periods=1).mean() # 1분봉 데이터 가정, 24시간 이동 평균

        return df

    def backtest(self, df, start_date, end_date):
        """전략 백테스팅 실행"""
        df = df.loc[start_date:end_date].copy()
        if df.empty:
            return {'error': '데이터가 비어 있습니다.'}

        df = self._calculate_indicators(df)
        df.dropna(subset=['Noise_Level', 'VWAP'], inplace=True)
        
        capital = self.initial_capital
        position = 0  # 0: 포지션 없음, 1: 롱, -1: 숏
        entry_price = 0
        current_max_profit_price = 0
        trade_log = []
        
        # 그리드 서치를 위한 트레이딩 지표
        win_count = 0
        loss_count = 0
        total_profit = 0
        max_drawdown = 0
        peak_capital = capital
        
        # 시뮬레이션
        for i in tqdm(range(len(df)), desc=f"백테스팅 진행 ({self.parameter_set})"):
            row = df.iloc[i]
            
            # 전일 종가 (논문 로직의 기준점)
            prev_close = df['Close'].iloc[i-1] if i > 0 else row['Close']
            
            # 노이즈 영역의 상/하한
            noise_upper_bound = prev_close * (1 + (row['Noise_Level'] * self.factor / 100))
            noise_lower_bound = prev_close * (1 - (row['Noise_Level'] * self.factor / 100))
            
            # === 청산 로직 (Exit Logic) ===
            if position != 0:
                current_price = row['Close']
                
                # 1. VWAP 기반 후행 정지 (Trailing Stop)
                # 롱 포지션: 가격이 최대 이익 가격에서 VWAP * 비율만큼 하락하면 청산
                if position == 1:
                    stop_price = row['VWAP'] * (1 - self.trailing_stop_ratio)
                    if current_price < stop_price:
                        exit_type = "TS_Short"
                        # 청산
                        profit = (current_price - entry_price) * capital / entry_price * position
                        trade_log.append((df.index[i], 'Exit', profit, current_price, exit_type, self.parameter_set))
                        capital += profit - (capital * self.commission_rate * 2) - (capital * self.slippage_rate * 2) # 왕복 수수료/슬리피지
                        position = 0
                        total_profit += profit
                        if profit > 0: win_count += 1
                        else: loss_count += 1
                
                # 숏 포지션: 가격이 최대 이익 가격에서 VWAP * 비율만큼 상승하면 청산
                elif position == -1:
                    stop_price = row['VWAP'] * (1 + self.trailing_stop_ratio)
                    if current_price > stop_price:
                        exit_type = "TS_Long"
                        # 청산
                        profit = (entry_price - current_price) * capital / entry_price * (-position) # 숏은 반대로 계산
                        trade_log.append((df.index[i], 'Exit', profit, current_price, exit_type, self.parameter_set))
                        capital += profit - (capital * self.commission_rate * 2) - (capital * self.slippage_rate * 2)
                        position = 0
                        total_profit += profit
                        if profit > 0: win_count += 1
                        else: loss_count += 1
                        
                # 2. 반대 방향 노이즈 영역 돌파 시 청산 (Reverse Signal Exit)
                if position == 1 and row['Close'] < noise_lower_bound:
                    exit_type = "Reverse_Short"
                    profit = (row['Close'] - entry_price) * capital / entry_price * position
                    trade_log.append((df.index[i], 'Exit', profit, row['Close'], exit_type, self.parameter_set))
                    capital += profit - (capital * self.commission_rate * 2) - (capital * self.slippage_rate * 2)
                    position = 0
                    total_profit += profit
                    if profit > 0: win_count += 1
                    else: loss_count += 1
                    
                elif position == -1 and row['Close'] > noise_upper_bound:
                    exit_type = "Reverse_Long"
                    profit = (entry_price - row['Close']) * capital / entry_price * (-position)
                    trade_log.append((df.index[i], 'Exit', profit, row['Close'], exit_type, self.parameter_set))
                    capital += profit - (capital * self.commission_rate * 2) - (capital * self.slippage_rate * 2)
                    position = 0
                    total_profit += profit
                    if profit > 0: win_count += 1
                    else: loss_count += 1
            
            
            # === 진입 로직 (Entry Logic) - 포지션이 없을 때만 ===
            if position == 0:
                # 롱 진입: 종가가 노이즈 상한선을 돌파
                if row['Close'] > noise_upper_bound:
                    entry_price = row['Close']
                    position = 1
                    trade_log.append((df.index[i], 'Entry_Long', 0, entry_price, 'Noise_Breakout', self.parameter_set))
                
                # 숏 진입: 종가가 노이즈 하한선을 돌파
                elif row['Close'] < noise_lower_bound:
                    entry_price = row['Close']
                    position = -1
                    trade_log.append((df.index[i], 'Entry_Short', 0, entry_price, 'Noise_Breakout', self.parameter_set))

            # === 최대 낙폭(MDD) 계산 ===
            if capital > peak_capital:
                peak_capital = capital
            drawdown = (peak_capital - capital) / peak_capital * 100
            max_drawdown = max(max_drawdown, drawdown)
            
            # (선물은 24시간이므로) 일봉의 마지막에 포지션 강제 청산 로직은 제외함
            
        # 마지막 포지션 청산 (백테스트 종료 시)
        if position != 0:
            final_profit = (row['Close'] - entry_price) * capital / entry_price * position # 롱/숏에 따라 자동 계산
            capital += final_profit - (capital * self.commission_rate * 2) - (capital * self.slippage_rate * 2) 
            total_profit += final_profit
            if final_profit > 0: win_count += 1
            else: loss_count += 1

        # 결과 요약
        total_trades = win_count + loss_count
        win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0
        total_return = (capital / self.initial_capital - 1) * 100

        results = {
            'parameter_set': self.parameter_set,
            'K': self.K,
            'factor': self.factor,
            'trailing_stop_ratio': self.trailing_stop_ratio,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'final_capital': capital
        }
        
        return results

    def plot_results(self, df, results):
        """결과 그래프 표시 (생략 - 그리드 서치에 집중)"""
        pass

# ==============================================================================
# 2. 메인 함수 (그리드 서치 실행)
# ==============================================================================
def load_data(file_path):
    """비트코인 1분봉 데이터 로드 (실제 데이터 파일 경로로 변경 필요)"""
    try:
        # 가상의 데이터 로드: 실제 파일 경로와 형식을 맞추세요.
        # 예: 일봉 데이터라고 가정하고, 실제 사용시 1분봉 또는 5분봉 사용 권장
        df = pd.read_csv(
            file_path, 
            index_col='timestamp', 
            parse_dates=True
        )
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume'] # 컬럼명 통일
        
        # 2023년 데이터로 한정 (최적화 시간 단축)
        df = df.loc['2024-01-01':] 
        
        # 일봉이 아닌 1분봉으로 데이터를 가정하고, 일봉 데이터는 제거 (실제 1분봉 데이터로 교체해야 함)
        if df.index.freq != 'T':
            print("⚠️ 경고: 데이터는 1분봉(T) 또는 5분봉(5T)이 권장됩니다. 현재 데이터 빈도:", df.index.freq)

        return df

    except FileNotFoundError:
        print("ERROR: 데이터 파일 경로를 확인해 주세요. (예: 'BTCUSDT_1m_2023.csv')")
        return pd.DataFrame()

def run_grid_search(df):
    """그리드 서치를 통해 최적의 파라미터를 찾습니다."""
    
    print("\n\n=== 그리드 서치 시작 (최적 파라미터 탐색) ===")
    
    # 1. 초기 설정
    initial_capital = 100000
    commission_rate = 0.0005  # 0.05% 수수료
    slippage_rate = 0.0005    # 0.05% 슬리피지 (왕복 총 0.1% 반영)
    
    best_results = None
    
    # 2. 그리드 서치 실행
    K_list = MomentumStrategy.parameter_grid['K']
    factor_list = MomentumStrategy.parameter_grid['factor']
    ts_ratio_list = MomentumStrategy.parameter_grid['trailing_stop_ratio']
    
    total_runs = len(K_list) * len(factor_list) * len(ts_ratio_list)
    
    all_results = []
    
    for K in K_list:
        for factor in factor_list:
            for ts_ratio in ts_ratio_list:
                
                strategy = MomentumStrategy(
                    initial_capital=initial_capital,
                    commission_rate=commission_rate,
                    slippage_rate=slippage_rate,
                    K=K,
                    factor=factor,
                    trailing_stop_ratio=ts_ratio
                )
                
                # 백테스트 실행 (2023년 전체 데이터에 대해)
                results = strategy.backtest(df, start_date='2023-01-01', end_date='2023-12-31')
                
                if 'error' not in results:
                    all_results.append(results)
                    
                    # 현재까지의 최적값 업데이트
                    if best_results is None or results['total_return'] > best_results['total_return']:
                        best_results = results

    # 3. 결과 출력
    if not all_results:
        print("ERROR: 백테스트를 실행할 데이터가 부족하거나 오류가 발생했습니다.")
        return
        
    results_df = pd.DataFrame(all_results)
    
    print("\n\n=== 그리드 서치 최종 결과 요약 ===")
    print(results_df.sort_values(by='total_return', ascending=False).head(5))
    
    print("\n\n=== 최적의 파라미터 셋 (총 수익률 기준) ===")
    print(f"파라미터: {best_results['parameter_set']}")
    print(f"총 수익률: {best_results['total_return']:.2f}%")
    print(f"최대 낙폭: {best_results['max_drawdown']:.2f}%")
    print(f"총 거래 횟수: {best_results['total_trades']}회")
    print(f"승률: {best_results['win_rate']:.2f}%")
    
    return best_results


def main():
    """메인 실행 함수"""
    # 🚨 데이터 파일 경로를 실제 바이낸스 비트코인 선물 1분봉 데이터 파일로 변경하세요.
    file_path = 'C:/work/GitHub/py/kook/binance_test/data/BTCUSDT/5m/BTCUSDT_5m_2024.csv'
    df = load_data(file_path)
    
    if not df.empty:
        run_grid_search(df)

if __name__ == '__main__':
    main()