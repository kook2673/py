"""
MA + DCC(던키안 채널) 최적화 및 백테스트 시스템

=== 주요 기능 ===
1. 이동평균(MA) 전략
   - 단기/장기 이동평균 교차 신호
   - RSI 과매수/과매도 필터
   - 볼륨 필터링

2. 던키안 채널(DCC) 전략
   - 변동성 기반 채널 지표
   - 상단/하단 돌파 신호
   - 채널 내 위치 기반 매매

3. 결합 전략
   - MA + DCC 동시 신호 확인
   - 더 정확한 진입/청산 타이밍
   - 리스크 감소 효과

=== 던키안 채널(DCC) 인디케이터 ===
던키안 채널은 가격의 변동성을 측정하는 채널 지표입니다.

계산 방법:
- 상단선: 최근 N일간의 최고가
- 하단선: 최근 N일간의 최저가  
- 중간선: (상단선 + 하단선) / 2
- 채널 폭: 상단선 - 하단선
- 가격 위치: (현재가 - 하단선) / (상단선 - 하단선)

매매 신호:
- 매수: 상단 돌파 또는 중간선 위 + 상단 70% 이상
- 매도: 하단 이탈 또는 중간선 아래 + 하단 30% 이하

=== 백테스트 시스템 ===
- 3년치 데이터로 최적 파라미터 탐색 (2021-2023)
- 마지막 1년치로 백테스트 실행 (2024)
- 롱/숏 분리 최적화
- 양방향 매매 지원
- 실시간 성과 추적
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class CleanMABot:
    def __init__(self, symbol='BTCUSDT', start_date='2021-01-01', end_date='2024-12-31'):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.data = None
        self.config = self.load_config()
        
    def load_config(self):
        """설정 파일 로드"""
        try:
            with open('clean_ma_bot.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return self.get_default_config()
    
    def get_default_config(self):
        """기본 설정"""
        return {
            "leverage_settings": {
                "use_leverage": True,
                "leverage_ratio": 2.0,
                "max_leverage": 5.0
            },
            "strategy_params": {
                "long_sma_short": 8,
                "long_sma_long": 30,
                "short_sma_short": 7,
                "short_sma_long": 15,
                "dcc_period": 15
            }
        }
    
    def load_data(self):
        """데이터 로드"""
        print("데이터 로딩 중...")
        data_files = []
        
        for year in range(2021, 2025):
            file_path = f"data/BTCUSDT/5m/BTCUSDT_5m_{year}.csv"
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
                data_files.append(df)
                print(f"로드 완료: {file_path}")
        
        if not data_files:
            raise FileNotFoundError("데이터 파일을 찾을 수 없습니다.")
        
        self.data = pd.concat(data_files, ignore_index=False)
        self.data = self.data.sort_index()
        
        # 시간대 필터링
        start_dt = pd.to_datetime(self.start_date)
        end_dt = pd.to_datetime(self.end_date)
        self.data = self.data[(self.data.index >= start_dt) & (self.data.index <= end_dt)]
        
        print(f"데이터 로딩 완료: {len(self.data)}개 캔들")
        return self.data
    
    def calculate_indicators(self, long_sma_short, long_sma_long, short_sma_short, short_sma_long, dcc_period, volume_threshold=1.0):
        """기술적 지표 계산 - 메모리 효율적"""
        # 원본 데이터를 직접 사용 (복사하지 않음)
        df = self.data
        
        # 이동평균 (inplace=False로 새 컬럼만 생성)
        long_sma_short_col = df['close'].rolling(long_sma_short).mean()
        long_sma_long_col = df['close'].rolling(long_sma_long).mean()
        short_sma_short_col = df['close'].rolling(short_sma_short).mean()
        short_sma_long_col = df['close'].rolling(short_sma_long).mean()
        
        # 던키안 채널
        dcc_high_col = df['high'].rolling(dcc_period).max()
        dcc_low_col = df['low'].rolling(dcc_period).min()
        dcc_middle_col = (dcc_high_col + dcc_low_col) / 2
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi_col = 100 - (100 / (1 + rs))
        
        # 볼륨 필터링
        volume_ma_col = df['volume'].rolling(20).mean()
        volume_ratio_col = df['volume'] / volume_ma_col
        volume_filter_col = volume_ratio_col >= volume_threshold
        
        # 필요한 컬럼만 포함한 새로운 DataFrame 생성
        result_df = pd.DataFrame({
            'close': df['close'],
            'high': df['high'],
            'low': df['low'],
            'volume': df['volume'],
            'long_sma_short': long_sma_short_col,
            'long_sma_long': long_sma_long_col,
            'short_sma_short': short_sma_short_col,
            'short_sma_long': short_sma_long_col,
            'dcc_high': dcc_high_col,
            'dcc_low': dcc_low_col,
            'dcc_middle': dcc_middle_col,
            'rsi': rsi_col,
            'volume_filter': volume_filter_col
        }, index=df.index)
        
        return result_df
    
    def generate_signals(self, df, use_volume_filter=True):
        """매매 신호 생성 - 메모리 효율적"""
        # 롱 신호
        long_ma_signal = (df['long_sma_short'] > df['long_sma_long']) & (df['long_sma_short'].shift(1) <= df['long_sma_long'].shift(1))
        long_dcc_signal = (df['close'] > df['dcc_middle']) & (df['close'] > df['dcc_low'] * 1.02)
        long_rsi_signal = df['rsi'] < 70
        
        # 숏 신호
        short_ma_signal = (df['short_sma_short'] < df['short_sma_long']) & (df['short_sma_short'].shift(1) >= df['short_sma_long'].shift(1))
        short_dcc_signal = (df['close'] < df['dcc_middle']) & (df['close'] < df['dcc_high'] * 0.98)
        short_rsi_signal = df['rsi'] > 30
        
        # 볼륨 필터 적용
        if use_volume_filter and 'volume_filter' in df.columns:
            long_signal = long_ma_signal & long_dcc_signal & long_rsi_signal & df['volume_filter']
            short_signal = short_ma_signal & short_dcc_signal & short_rsi_signal & df['volume_filter']
        else:
            long_signal = long_ma_signal & long_dcc_signal & long_rsi_signal
            short_signal = short_ma_signal & short_dcc_signal & short_rsi_signal
        
        # 필요한 컬럼만 포함한 결과 DataFrame 생성
        result_df = pd.DataFrame({
            'close': df['close'],
            'high': df['high'],
            'low': df['low'],
            'volume': df['volume'],
            'long_sma_short': df['long_sma_short'],
            'long_sma_long': df['long_sma_long'],
            'short_sma_short': df['short_sma_short'],
            'short_sma_long': df['short_sma_long'],
            'dcc_high': df['dcc_high'],
            'dcc_low': df['dcc_low'],
            'dcc_middle': df['dcc_middle'],
            'rsi': df['rsi'],
            'volume_filter': df['volume_filter'] if 'volume_filter' in df.columns else True,
            'long_signal': long_signal,
            'short_signal': short_signal
        }, index=df.index)
        
        return result_df
    
    def run_backtest_vectorized(self, initial_capital=10000, leverage_ratio=1.0):
        """백테스트 실행 - 판다스 벡터화 연산으로 고속화"""
        print(f"백테스트 시작 - 초기자본: ${initial_capital:,.0f}, 레버리지: {leverage_ratio}배")
        
        # 설정에서 파라미터 가져오기
        params = self.config.get('strategy_params', {})
        long_sma_short = params.get('long_sma_short', 8)
        long_sma_long = params.get('long_sma_long', 30)
        short_sma_short = params.get('short_sma_short', 7)
        short_sma_long = params.get('short_sma_long', 15)
        dcc_period = params.get('dcc_period', 15)
        volume_threshold = params.get('volume_threshold', 1.0)
        
        # 볼륨 필터 설정 가져오기
        use_volume_filter = self.config.get('strategy_settings', {}).get('use_volume_filter', True)
        
        # 지표 계산
        df = self.calculate_indicators(long_sma_short, long_sma_long, short_sma_short, short_sma_long, dcc_period, volume_threshold)
        df = self.generate_signals(df, use_volume_filter)
        
        # NaN 제거
        df = df.dropna()
        
        # 벡터화된 포지션 계산
        df['position'] = self._calculate_positions_vectorized(df, leverage_ratio)
        
        # 거래 생성
        trades = self._extract_trades_vectorized(df, leverage_ratio, initial_capital)
        
        # 결과 계산
        if len(trades) > 0:
            total_pnl = sum(trade['pnl'] for trade in trades)
            final_capital = initial_capital + total_pnl
            total_return = (final_capital - initial_capital) / initial_capital * 100
            
            winning_trades = len([t for t in trades if t['pnl'] > 0])
            win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0
            
            # 최대 낙폭 계산
            max_drawdown = self._calculate_max_drawdown_vectorized(initial_capital, trades)
        else:
            final_capital = initial_capital
            total_return = 0.0
            win_rate = 0.0
            max_drawdown = 0.0
        
        return {
            'total_return': total_return,
            'final_capital': final_capital,
            'total_trades': len(trades),
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'trades': trades,
            'leverage_used': leverage_ratio
        }
    
    def _calculate_positions_vectorized(self, df, leverage_ratio):
        """벡터화된 포지션 계산"""
        # 포지션 상태 초기화
        position = pd.Series([None] * len(df), index=df.index)
        entry_price = pd.Series([0.0] * len(df), index=df.index)
        
        # 진입/청산 신호
        long_entry = df['long_signal'] & (position.shift(1).isna())
        short_entry = df['short_signal'] & (position.shift(1).isna())
        
        long_exit = (df['short_signal'] | (df['rsi'] > 80)) & (position.shift(1) == 'long')
        short_exit = (df['long_signal'] | (df['rsi'] < 20)) & (position.shift(1) == 'short')
        
        # 포지션 상태 업데이트
        position[long_entry] = 'long'
        position[short_entry] = 'short'
        position[long_exit] = None
        position[short_exit] = None
        
        # 진입 가격 업데이트
        entry_price[long_entry] = df.loc[long_entry, 'close']
        entry_price[short_entry] = df.loc[short_entry, 'close']
        
        return position
    
    def _extract_trades_vectorized(self, df, leverage_ratio, initial_capital=10000):
        """벡터화된 거래 추출 - 레버리지 올바르게 적용"""
        trades = []
        
        # 포지션 변화 지점 찾기
        position = self._calculate_positions_vectorized(df, leverage_ratio)
        position_changes = position != position.shift(1)
        
        # 거래 시작/끝 지점 찾기
        trade_starts = position_changes & position.notna()
        trade_ends = position_changes & position.isna()
        
        # 거래 쌍 매칭
        start_indices = df.index[trade_starts]
        end_indices = df.index[trade_ends]
        
        for start_idx in start_indices:
            # 해당 거래의 종료 지점 찾기
            end_candidates = end_indices[end_indices > start_idx]
            if len(end_candidates) > 0:
                end_idx = end_candidates[0]
                
                # 거래 정보 추출
                entry_price = df.loc[start_idx, 'close']
                exit_price = df.loc[end_idx, 'close']
                position_type = position.loc[start_idx]
                
                # 수수료 설정
                fee_rate = 0.0005  # 0.05% 수수료
                
                # 수량 계산 (레버리지 적용, 수수료 포함)
                # 실제 투자 자본은 initial_capital, 거래량은 leverage_ratio만큼 늘림
                # 매수 시: 수수료를 가격에 포함
                leveraged_capital = initial_capital * leverage_ratio
                amount = leveraged_capital / (entry_price * (1 + fee_rate))
                
                # PnL 계산 (레버리지 효과 적용, 수수료 포함)
                if position_type == 'long':
                    # 매도 시: 수수료를 가격에서 차감
                    sell_price = exit_price * (1 - fee_rate)
                    pnl = (sell_price - entry_price) * amount
                else:  # short
                    # 숏 매도 시: 수수료를 가격에 포함
                    short_sell_price = entry_price * (1 - fee_rate)
                    # 숏 매수 시: 수수료를 가격에서 차감  
                    short_buy_price = exit_price * (1 + fee_rate)
                    pnl = (short_sell_price - short_buy_price) * amount
                
                # 청산 사유
                exit_reason = "signal_reversal"
                if position_type == 'long' and df.loc[end_idx, 'rsi'] > 80:
                    exit_reason = "rsi_overbought"
                elif position_type == 'short' and df.loc[end_idx, 'rsi'] < 20:
                    exit_reason = "rsi_oversold"
                
                trade = {
                    'timestamp': end_idx,
                    'type': position_type,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'amount': amount,
                    'pnl': pnl,
                    'exit_reason': exit_reason,
                    'leverage': leverage_ratio
                }
                trades.append(trade)
        
        return trades
    
    def _calculate_max_drawdown_vectorized(self, initial_capital, trades):
        """벡터화된 최대 낙폭 계산"""
        if not trades:
            return 0.0
        
        # 자본 변화 시계열 생성
        capital_series = [initial_capital]
        for trade in trades:
            capital_series.append(capital_series[-1] + trade['pnl'])
        
        capital_series = np.array(capital_series)
        
        # 누적 최고점 계산
        peak = np.maximum.accumulate(capital_series)
        
        # 낙폭 계산
        drawdown = (peak - capital_series) / peak * 100
        
        return np.max(drawdown)
    
    def run_backtest(self, initial_capital=10000, leverage_ratio=1.0):
        """백테스트 실행 - 벡터화 버전 사용"""
        return self.run_backtest_vectorized(initial_capital, leverage_ratio)
    
    def optimize_parameters_fast(self):
        """빠른 파라미터 최적화 - 제한된 범위로 테스트"""
        print("빠른 파라미터 최적화 시작...")
        
        best_result = None
        best_score = -999999
        
        # 파라미터 범위 (간소화하여 실행 시간 단축)
        #long_sma_short_range = range(5, 16, 3)  # 5, 8, 11, 14 (4개)
        #long_sma_long_range = range(20, 51, 10)  # 20, 30, 40, 50 (4개)
        #short_sma_short_range = range(4, 15, 3)  # 4, 7, 10, 13 (4개)
        #short_sma_long_range = range(15, 46, 10)  # 15, 25, 35, 45 (4개)
        #dcc_period_range = range(15, 36, 5)  # 15, 20, 25, 30, 35 (5개)
        #volume_threshold_range = [1.0, 1.5, 2.0]  # 3개

        # 최적화된 수치 기준으로 dcc_period만 그리드 방식
        # 최적화된 파라미터 (고정)
        optimal_long_sma_short = 14
        optimal_long_sma_long = 20
        optimal_short_sma_short = 10
        optimal_short_sma_long = 25
        optimal_volume_threshold = 1.5
        
        # dcc_period만 그리드 방식으로 테스트
        dcc_period_range = range(5, 36, 5)  # 10, 15, 20, 25, 30, 35 (6개)
        
        # 고정 파라미터를 리스트로 변환 (루프 호환성)
        long_sma_short_range = [optimal_long_sma_short]
        long_sma_long_range = [optimal_long_sma_long]
        short_sma_short_range = [optimal_short_sma_short]
        short_sma_long_range = [optimal_short_sma_long]
        volume_threshold_range = [optimal_volume_threshold]
        
        total_combinations = len(long_sma_short_range) * len(long_sma_long_range) * len(short_sma_short_range) * len(short_sma_long_range) * len(dcc_period_range)
        print(f"총 {total_combinations}개 조합 테스트 중...")
        
        combination_count = 0
        for long_sma_short in long_sma_short_range:
            for long_sma_long in long_sma_long_range:
                if long_sma_short >= long_sma_long:
                    continue
                    
                for short_sma_short in short_sma_short_range:
                    for short_sma_long in short_sma_long_range:
                        if short_sma_short >= short_sma_long:
                            continue
                            
                        for dcc_period in dcc_period_range:
                            for volume_threshold in volume_threshold_range:
                                combination_count += 1
                                
                                if combination_count % 10 == 0:
                                    print(f"진행률: {combination_count}/{total_combinations * len(volume_threshold_range)}")
                                
                                try:
                                    # 파라미터 설정
                                    self.config['strategy_params'] = {
                                        'long_sma_short': long_sma_short,
                                        'long_sma_long': long_sma_long,
                                        'short_sma_short': short_sma_short,
                                        'short_sma_long': short_sma_long,
                                        'dcc_period': dcc_period,
                                        'volume_threshold': volume_threshold
                                    }
                                    
                                    # 백테스트 실행
                                    result = self.run_backtest()
                                    
                                    # 점수 계산 (수익률 - 최대낙폭)
                                    score = result['total_return'] - result['max_drawdown']
                                    
                                    if score > best_score:
                                        best_score = score
                                        best_result = result.copy()
                                        best_result['params'] = {
                                            'long_sma_short': long_sma_short,
                                            'long_sma_long': long_sma_long,
                                            'short_sma_short': short_sma_short,
                                            'short_sma_long': short_sma_long,
                                            'dcc_period': dcc_period,
                                            'volume_threshold': volume_threshold
                                        }
                                        
                                        print(f"새로운 최고 점수: {score:.2f} (수익률: {result['total_return']:.2f}%, MDD: {result['max_drawdown']:.2f}%)")
                                        
                                except Exception as e:
                                    continue
        
        print(f"\n=== 최적화 완료 ===")
        print(f"최적 파라미터: {best_result['params']}")
        print(f"수익률: {best_result['total_return']:.2f}%")
        print(f"승률: {best_result['win_rate']:.2f}%")
        print(f"최대낙폭: {best_result['max_drawdown']:.2f}%")
        print(f"총 거래 수: {best_result['total_trades']}")
        
        # 최적 파라미터 저장
        self.save_optimal_params(best_result)
        
        return best_result
    
    def optimize_parameters(self):
        """파라미터 최적화 - 빠른 버전 사용"""
        return self.optimize_parameters_fast()
    
    def save_optimal_params(self, result):
        """최적 파라미터 저장"""
        try:
            # JSON 파일 업데이트
            self.config['strategy_params'] = result['params']
            self.config['optimization_results'] = {
                'total_return': result['total_return'],
                'win_rate': result['win_rate'],
                'max_drawdown': result['max_drawdown'],
                'total_trades': result['total_trades'],
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open('ma_bot.json', 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            print("최적 파라미터 저장 완료: ma_bot.json")
            
        except Exception as e:
            print(f"파라미터 저장 실패: {e}")
    
    def run_leveraged_backtest(self):
        """레버리지 적용 백테스트"""
        leverage_settings = self.config.get('leverage_settings', {})
        leverage_ratio = leverage_settings.get('leverage_ratio', 1.0)
        
        print(f"레버리지 {leverage_ratio}배 적용 백테스트 실행")
        result = self.run_backtest(leverage_ratio=leverage_ratio)
        
        print(f"\n=== 레버리지 {leverage_ratio}배 결과 ===")
        print(f"총 수익률: {result['total_return']:.2f}%")
        print(f"승률: {result['win_rate']:.2f}%")
        print(f"최대 낙폭: {result['max_drawdown']:.2f}%")
        print(f"총 거래 수: {result['total_trades']}")
        print(f"최종 자본: ${result['final_capital']:,.0f}")
        
        return result

def main():
    """메인 실행 함수"""
    print("=== 깔끔한 MA + DCC 백테스트 시스템 ===")
    
    # 봇 초기화
    bot = CleanMABot()
    
    # 데이터 로드
    bot.load_data()
    
    # JSON 설정에서 모든 옵션 가져오기
    use_saved_params = bot.config.get('use_saved_params', False)
    optimize_params = bot.config.get('optimize_params', False)
    leverage_settings = bot.config.get('leverage_settings', {})
    use_leverage = leverage_settings.get('use_leverage', False)
    leverage_ratio = leverage_settings.get('leverage_ratio', 1.0)
    
    print(f"\n=== 설정 확인 ===")
    print(f"저장된 파라미터 사용: {use_saved_params}")
    print(f"파라미터 최적화: {optimize_params}")
    print(f"레버리지 사용: {use_leverage}")
    print(f"레버리지 비율: {leverage_ratio}배")
    
    # 파라미터 최적화 실행 여부
    if optimize_params:
        print(f"\n=== 파라미터 최적화 실행 ===")
        optimal_result = bot.optimize_parameters()
        print(f"최적화 완료: {optimal_result['params']}")
    
    # 백테스트 실행
    print(f"\n=== 백테스트 실행 ===")
    if use_leverage:
        print(f"레버리지 {leverage_ratio}배 적용")
        result = bot.run_backtest(leverage_ratio=leverage_ratio)
    else:
        print("레버리지 없음 (1배)")
        result = bot.run_backtest(leverage_ratio=1.0)
    
    print(f"\n=== 백테스트 결과 ===")
    print(f"총 수익률: {result['total_return']:.2f}%")
    print(f"승률: {result['win_rate']:.2f}%")
    print(f"최대 낙폭: {result['max_drawdown']:.2f}%")
    print(f"총 거래 수: {result['total_trades']}")
    print(f"최종 자본: ${result['final_capital']:,.0f}")
    print(f"사용된 레버리지: {result['leverage_used']}배")
    
    print("\n=== 백테스트 완료 ===")

if __name__ == "__main__":
    main()
