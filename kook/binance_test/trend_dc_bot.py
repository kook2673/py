"""
비트코인 추세 추종 + 양방향 매매 봇 (판다스 최적화 버전)

=== 전략 개요 ===
- 추세 추종에 편승하면 단방향 매매 (롱 또는 숏)
- 추세 이탈하면 양방향 매매로 전환
- 2024년 비트코인 1분 데이터 사용
- 구매/판매 수수료 각 0.05% 적용
- 판다스 벡터화 연산으로 최적화

=== 핵심 로직 ===
1. 추세 감지: 이동평균선 교차 + RSI + 볼린저 밴드 + 돈키안 채널
2. 추세 추종 모드: 강한 추세일 때 단방향 매매
3. 양방향 모드: 추세가 약하거나 횡보일 때 양방향 매매
4. 리스크 관리: 손절/익절 + 트레일링스탑
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class BTCTrendFollowingBotOptimized:
    """비트코인 추세 추종 + 양방향 매매 봇 (판다스 최적화)"""
    
    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = {'long': None, 'short': None}
        self.trades = []
        
        # 수수료 설정
        self.buy_fee = 0.0005  # 0.05%
        self.sell_fee = 0.0005  # 0.05%
        
        # 전략 파라미터
        self.params = {
            'ma_short': 20,
            'ma_long': 50,
            'rsi_period': 14,
            'bb_period': 20,
            'bb_std': 2,
            'dc_period': 25,
            'trend_threshold': 0.02,
            'position_size': 0.5,
            'stop_loss': 0.02,
            'take_profit': 0.03,
            'trailing_stop': 0.005,
        }
    
    def load_btc_data(self, year=2024):
        """비트코인 데이터 로드 (지정된 연도)"""
        data_dir = f"data/BTCUSDT/1m"
        if not os.path.exists(data_dir):
            print(f"데이터 디렉토리가 없습니다: {data_dir}")
            return None
        
        # 지정된 연도 데이터 파일 찾기
        file_name = f"BTCUSDT_1m_{year}.csv"
        file_path = os.path.join(data_dir, file_name)
        
        if not os.path.exists(file_path):
            print(f"{year}년 데이터 파일이 없습니다: {file_path}")
            return None
        
        print(f"비트코인 {year}년 데이터 로드 중...")
        
        try:
            # 파일 읽기
            data = pd.read_csv(file_path)
            
            # 컬럼명 정리
            data.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            
            # 타임스탬프를 datetime으로 변환
            data['timestamp'] = pd.to_datetime(data['timestamp'])
            data = data.set_index('timestamp')
            
            # 중복 제거 및 정렬
            data = data.drop_duplicates().sort_index()
            
            print(f"비트코인 {year}년 데이터 로드 완료: {len(data):,}개 캔들")
            print(f"전체 기간: {data.index[0]} ~ {data.index[-1]}")
            
            return data
            
        except Exception as e:
            print(f"파일 읽기 오류: {e}")
            return None
    
    def calculate_indicators(self, data):
        """기술적 지표 계산 (벡터화)"""
        df = data.copy()
        
        # 이동평균선
        df['ma_short'] = df['close'].rolling(window=self.params['ma_short']).mean()
        df['ma_long'] = df['close'].rolling(window=self.params['ma_long']).mean()
        
        # RSI 계산
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.params['rsi_period']).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.params['rsi_period']).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 볼린저 밴드
        df['bb_middle'] = df['close'].rolling(window=self.params['bb_period']).mean()
        bb_std = df['close'].rolling(window=self.params['bb_period']).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * self.params['bb_std'])
        df['bb_lower'] = df['bb_middle'] - (bb_std * self.params['bb_std'])
        
        # 돈키안 채널
        df['dc_high'] = df['high'].rolling(window=self.params['dc_period']).max()
        df['dc_low'] = df['low'].rolling(window=self.params['dc_period']).min()
        df['dc_middle'] = (df['dc_high'] + df['dc_low']) / 2
        
        # 추세 강도 계산
        df['trend_strength'] = (df['ma_short'] - df['ma_long']) / df['ma_long']
        
        return df
    
    def get_signals_vectorized(self, data):
        """신호 생성 (벡터화)"""
        df = data.copy()
        
        # 기본 신호 초기화
        df['long_signal'] = False
        df['short_signal'] = False
        df['trend_mode'] = 'sideways'
        
        # 추세 모드 결정
        strong_uptrend = (df['trend_strength'] > self.params['trend_threshold']) & (df['rsi'] > 50)
        strong_downtrend = (df['trend_strength'] < -self.params['trend_threshold']) & (df['rsi'] < 50)
        
        df.loc[strong_uptrend, 'trend_mode'] = 'uptrend'
        df.loc[strong_downtrend, 'trend_mode'] = 'downtrend'
        
        # 롱 신호 조건
        long_conditions = (
            (df['close'] > df['ma_short']) &  # 단기 이평 위
            (df['close'] > df['dc_middle']) &  # 돈키안 중간선 위
            (df['close'] > df['dc_low'] * 1.02) &  # 돈키안 하단 +2% 위
            (df['rsi'] > 30) &  # RSI 과매도 아님
            (df['close'] > df['bb_lower'])  # 볼린저 하단 위
        )
        
        # 숏 신호 조건
        short_conditions = (
            (df['close'] < df['ma_short']) &  # 단기 이평 아래
            (df['close'] < df['dc_middle']) &  # 돈키안 중간선 아래
            (df['close'] < df['dc_high'] * 0.98) &  # 돈키안 상단 -2% 아래
            (df['rsi'] < 70) &  # RSI 과매수 아님
            (df['close'] < df['bb_upper'])  # 볼린저 상단 아래
        )
        
        # 추세 모드에 따른 신호 적용
        # 강한 상승 추세: 롱만
        df.loc[strong_uptrend & long_conditions, 'long_signal'] = True
        
        # 강한 하락 추세: 숏만
        df.loc[strong_downtrend & short_conditions, 'short_signal'] = True
        
        # 횡보/약한 추세: 양방향
        sideways_conditions = df['trend_mode'] == 'sideways'
        df.loc[sideways_conditions & long_conditions, 'long_signal'] = True
        df.loc[sideways_conditions & short_conditions, 'short_signal'] = True
        
        return df
    
    def backtest_vectorized(self, data):
        """백테스팅 실행 (벡터화)"""
        print("백테스팅 시작...")
        
        # 로그 파일 설정
        log_filename = f"trading_log_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.txt"
        log_file = open(log_filename, 'w', encoding='utf-8')
        log_file.write("=== 비트코인 추세 추종 + 양방향 매매 봇 거래 로그 ===\n")
        log_file.write(f"시작 시간: {pd.Timestamp.now()}\n")
        log_file.write(f"초기 자본: ${self.initial_capital:,.2f}\n")
        log_file.write("=" * 80 + "\n\n")
        
        # 신호가 있는 행만 처리
        signal_data = data[data['long_signal'] | data['short_signal']].copy()
        
        current_capital = self.initial_capital
        positions = {'long': None, 'short': None}
        trades = []
        trading_stopped = False
        
        for idx, row in signal_data.iterrows():
            # 자본이 음수이면 거래 중단
            if current_capital <= 0 and not trading_stopped:
                log_msg = f"[{idx}] 자본 부족으로 거래 중단 - 자본: ${current_capital:.2f}"
                print(log_msg)
                log_file.write(log_msg + "\n")
                trading_stopped = True
                break
            
            timestamp = idx
            price = row['close']
            
            # 롱 신호 처리
            if row['long_signal'] and positions['long'] is None and not trading_stopped:
                if self._open_position('long', price, timestamp, current_capital, positions, trades, log_file):
                    current_capital = positions['long']['capital_after']
                    # 자본이 음수가 되면 거래 중단
                    if current_capital <= 0:
                        log_msg = f"[{timestamp}] 자본 부족으로 거래 중단 - 자본: ${current_capital:.2f}"
                        print(log_msg)
                        log_file.write(log_msg + "\n")
                        trading_stopped = True
                        break
            
            # 숏 신호 처리
            if row['short_signal'] and positions['short'] is None and not trading_stopped:
                if self._open_position('short', price, timestamp, current_capital, positions, trades, log_file):
                    current_capital = positions['short']['capital_after']
                    # 자본이 음수가 되면 거래 중단
                    if current_capital <= 0:
                        log_msg = f"[{timestamp}] 자본 부족으로 거래 중단 - 자본: ${current_capital:.2f}"
                        print(log_msg)
                        log_file.write(log_msg + "\n")
                        trading_stopped = True
                        break
            
            # 포지션 청산 체크
            if positions['long'] and not trading_stopped:
                if self._check_exit_conditions('long', price, timestamp, positions, trades, log_file):
                    current_capital = positions['long']['capital_after']
                    positions['long'] = None
                    # 자본이 음수가 되면 거래 중단
                    if current_capital <= 0:
                        log_msg = f"[{timestamp}] 자본 부족으로 거래 중단 - 자본: ${current_capital:.2f}"
                        print(log_msg)
                        log_file.write(log_msg + "\n")
                        trading_stopped = True
                        break
            
            if positions['short'] and not trading_stopped:
                if self._check_exit_conditions('short', price, timestamp, positions, trades, log_file):
                    current_capital = positions['short']['capital_after']
                    positions['short'] = None
                    # 자본이 음수가 되면 거래 중단
                    if current_capital <= 0:
                        log_msg = f"[{timestamp}] 자본 부족으로 거래 중단 - 자본: ${current_capital:.2f}"
                        print(log_msg)
                        log_file.write(log_msg + "\n")
                        trading_stopped = True
                        break
        
        # 최종 자본 업데이트
        self.current_capital = current_capital
        self.trades = trades
        
        # 로그 파일 마무리
        log_file.write("\n" + "=" * 80 + "\n")
        log_file.write(f"백테스팅 종료 시간: {pd.Timestamp.now()}\n")
        log_file.write(f"최종 자본: ${current_capital:,.2f}\n")
        log_file.write(f"총 거래 수: {len(trades)}회\n")
        if trading_stopped:
            log_file.write("거래가 중단되었습니다.\n")
        log_file.close()
        
        if trading_stopped:
            print(f"거래가 중단되었습니다. 최종 자본: ${current_capital:.2f}")
        
        print(f"거래 로그가 '{log_filename}' 파일에 저장되었습니다.")
        
        return trades
    
    def _open_position(self, position_type, price, timestamp, current_capital, positions, trades, log_file):
        """포지션 진입"""
        # 자본이 0 이하이면 거래 중단
        if current_capital <= 0:
            log_msg = f"[{timestamp}] 자본 부족으로 거래 중단 - 자본: ${current_capital:.2f}"
            print(log_msg)
            log_file.write(log_msg + "\n")
            return False
        
        # 포지션 크기 계산
        position_size = current_capital * self.params['position_size'] / price
        
        # 진입 수수료
        fee = position_size * price * self.buy_fee
        
        # 수수료가 자본보다 크면 거래 불가
        if fee >= current_capital:
            log_msg = f"[{timestamp}] 수수료 부족으로 거래 불가 - 수수료: ${fee:.2f}, 자본: ${current_capital:.2f}"
            print(log_msg)
            log_file.write(log_msg + "\n")
            return False
        
        # 포지션 정보 저장
        positions[position_type] = {
            'entry_price': price,
            'size': position_size,
            'entry_time': timestamp,
            'fee': fee,
            'trailing_stop_price': None,
            'capital_after': current_capital - fee
        }
        
        log_msg = f"[{timestamp}] BTC {position_type.upper()} 진입 - 가격: {price:.2f}, 수수료: {fee:.2f}, 자본: ${current_capital - fee:.2f}"
        print(log_msg)
        log_file.write(log_msg + "\n")
        return True
    
    def _get_dynamic_trailing_stop(self, pnl_pct):
        """수익률에 따른 동적 트레일링스탑 비율 계산"""
        if pnl_pct >= 0.03:  # 5.0% 이상
            return 0.0001
        elif pnl_pct >= 0.025:  # 4.0% 이상
            return 0.0005
        elif pnl_pct >= 0.02:  # 3.0% 이상
            return 0.001
        elif pnl_pct >= 0.015:  # 2.0% 이상
            return 0.002
        elif pnl_pct >= 0.01:  # 1.0% 이상
            return 0.003
        elif pnl_pct >= 0.005:  # 0.5% 이상
            return 0.005
        else:
            return None  # 트레일링스탑 비활성화
    
    def _check_exit_conditions(self, position_type, price, timestamp, positions, trades, log_file):
        """청산 조건 체크 (동적 트레일링스탑 적용)"""
        position = positions[position_type]
        if not position:
            return False
        
        # PnL 계산
        if position_type == 'long':
            pnl = (price - position['entry_price']) * position['size']
        else:  # short
            pnl = (position['entry_price'] - price) * position['size']
        
        pnl_pct = pnl / (position['entry_price'] * position['size'])
        
        # 청산 조건 체크
        exit_reason = None
        
        # 손절
        if pnl_pct <= -self.params['stop_loss']:
            exit_reason = f"손절 ({self.params['stop_loss']*100:.1f}%)"
        
        # 익절 제거 (트레일링스탑만 사용)
        
        # 동적 트레일링스탑
        else:
            # 현재 수익률에 따른 트레일링스탑 비율 계산
            trailing_stop_ratio = self._get_dynamic_trailing_stop(pnl_pct)
            
            if trailing_stop_ratio is not None:  # 트레일링스탑 활성화 조건 만족
                if position['trailing_stop_price'] is None:
                    # 트레일링스탑 초기 설정
                    if position_type == 'long':
                        position['trailing_stop_price'] = price * (1 - trailing_stop_ratio)
                    else:  # short
                        position['trailing_stop_price'] = price * (1 + trailing_stop_ratio)
                    
                    log_msg = f"[{timestamp}] 트레일링스탑 활성화 - 수익률: {pnl_pct*100:.2f}%, 비율: {trailing_stop_ratio*100:.3f}%, 가격: {position['trailing_stop_price']:.2f}"
                    log_file.write(log_msg + "\n")
                else:
                    # 트레일링스탑 업데이트 (더 유리한 방향으로만)
                    if position_type == 'long':
                        new_trailing = price * (1 - trailing_stop_ratio)
                        if new_trailing > position['trailing_stop_price']:
                            old_trailing = position['trailing_stop_price']
                            position['trailing_stop_price'] = new_trailing
                            log_msg = f"[{timestamp}] 롱 트레일링스탑 업데이트 - {old_trailing:.2f} → {new_trailing:.2f} (비율: {trailing_stop_ratio*100:.3f}%)"
                            log_file.write(log_msg + "\n")
                    else:  # short
                        new_trailing = price * (1 + trailing_stop_ratio)
                        if new_trailing < position['trailing_stop_price']:
                            old_trailing = position['trailing_stop_price']
                            position['trailing_stop_price'] = new_trailing
                            log_msg = f"[{timestamp}] 숏 트레일링스탑 업데이트 - {old_trailing:.2f} → {new_trailing:.2f} (비율: {trailing_stop_ratio*100:.3f}%)"
                            log_file.write(log_msg + "\n")
                
                # 트레일링스탑 체크
                if position_type == 'long' and price <= position['trailing_stop_price']:
                    exit_reason = f"트레일링스탑 ({trailing_stop_ratio*100:.3f}%)"
                elif position_type == 'short' and price >= position['trailing_stop_price']:
                    exit_reason = f"트레일링스탑 ({trailing_stop_ratio*100:.3f}%)"
        
        if exit_reason:
            self._close_position(position_type, price, timestamp, exit_reason, position, trades, log_file)
            return True
        
        return False
    
    def _close_position(self, position_type, price, timestamp, reason, position, trades, log_file):
        """포지션 청산"""
        # PnL 계산
        if position_type == 'long':
            pnl = (price - position['entry_price']) * position['size']
        else:  # short
            pnl = (position['entry_price'] - price) * position['size']
        
        # 청산 수수료
        exit_trade_amount = position['size'] * price
        exit_fee = exit_trade_amount * self.sell_fee
        net_pnl = pnl - exit_fee
        
        # 자본 업데이트
        new_capital = position['capital_after'] + net_pnl
        position['capital_after'] = new_capital
        
        pnl_pct = net_pnl / (position['entry_price'] * position['size'])
        
        # 거래 기록
        trade = {
            'entry_time': position['entry_time'],
            'exit_time': timestamp,
            'position_type': position_type,
            'entry_price': position['entry_price'],
            'exit_price': price,
            'size': position['size'],
            'pnl': net_pnl,
            'pnl_pct': pnl_pct,
            'entry_fee': position['fee'],
            'exit_fee': exit_fee,
            'reason': reason
        }
        trades.append(trade)
        
        log_msg = f"[{timestamp}] BTC {position_type.upper()} 청산 - 가격: {price:.2f}, PnL: {net_pnl:.2f} ({pnl_pct:.2f}%), 이유: {reason}, 자본: ${new_capital:.2f}"
        print(log_msg)
        log_file.write(log_msg + "\n")
    
    def print_performance(self, year=None):
        """성과 출력"""
        if not self.trades:
            print("거래 기록이 없습니다.")
            return
        
        total_return = (self.current_capital - self.initial_capital) / self.initial_capital * 100
        total_trades = len(self.trades)
        winning_trades = len([t for t in self.trades if t['pnl'] > 0])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        # 최대 낙폭 계산
        capital_series = [self.initial_capital]
        for trade in self.trades:
            capital_series.append(capital_series[-1] + trade['pnl'])
        
        peak = capital_series[0]
        max_dd = 0
        for capital in capital_series:
            if capital > peak:
                peak = capital
            dd = (peak - capital) / peak
            if dd > max_dd:
                max_dd = dd
        
        # 총 수수료
        total_fees = sum(t['entry_fee'] + t['exit_fee'] for t in self.trades)
        
        # 평균 보유 시간
        durations = []
        for trade in self.trades:
            if isinstance(trade['entry_time'], int):
                entry_time = pd.to_datetime(trade['entry_time'], unit='s')
            else:
                entry_time = trade['entry_time']
            if isinstance(trade['exit_time'], int):
                exit_time = pd.to_datetime(trade['exit_time'], unit='s')
            else:
                exit_time = trade['exit_time']
            duration = (exit_time - entry_time).total_seconds() / 3600  # 시간 단위
            durations.append(duration)
        
        avg_duration = np.mean(durations) if durations else 0
        
        year_text = f" ({year}년)" if year else ""
        print(f"\n비트코인 추세 추종 + 양방향 매매 봇 성과{year_text}")
        print("=" * 60)
        print(f"초기 자본: ${self.initial_capital:,.2f}")
        print(f"최종 자본: ${self.current_capital:,.2f}")
        print(f"총 수익률: {total_return:.2f}%")
        print(f"총 거래 수: {total_trades}회")
        print(f"승률: {win_rate:.1f}%")
        print(f"최대 낙폭: -{max_dd*100:.2f}%")
        print(f"총 수수료: ${total_fees:.2f}")
        print(f"평균 보유 시간: {avg_duration:.1f}시간")
        
        # 연도별 성과 (여러 연도 테스트 시에만)
        if not year:
            self.print_yearly_performance()
    
    def print_yearly_performance(self):
        """연도별 성과 출력"""
        if not self.trades:
            return
        
        print(f"\n연도별 성과 분석:")
        print("-" * 80)
        
        # 연도별로 거래 그룹화
        yearly_trades = {}
        for trade in self.trades:
            if isinstance(trade['entry_time'], int):
                entry_time = pd.to_datetime(trade['entry_time'], unit='s')
            else:
                entry_time = trade['entry_time']
            year = entry_time.year
            if year not in yearly_trades:
                yearly_trades[year] = []
            yearly_trades[year].append(trade)
        
        # 연도별 성과 계산
        for year in sorted(yearly_trades.keys()):
            trades = yearly_trades[year]
            total_pnl = sum(t['pnl'] for t in trades)
            winning_trades = len([t for t in trades if t['pnl'] > 0])
            win_rate = winning_trades / len(trades) * 100 if trades else 0
            
            print(f"{year}년: 거래 {len(trades)}회, PnL ${total_pnl:.2f}, 승률 {win_rate:.1f}%")

def test_single_year(year):
    """단일 연도 테스트"""
    print(f"=== {year}년 비트코인 추세 추종 + 양방향 매매 봇 테스트 ===")
    
    # 봇 초기화
    bot = BTCTrendFollowingBotOptimized(initial_capital=10000)
    
    # 데이터 로드
    data = bot.load_btc_data(year)
    if data is None:
        print(f"{year}년 데이터 로드 실패")
        return None
    
    # 기술적 지표 계산
    print("기술적 지표 계산 중...")
    data_with_indicators = bot.calculate_indicators(data)
    
    # 신호 생성
    print("신호 생성 중...")
    data_with_signals = bot.get_signals_vectorized(data_with_indicators)
    
    # 백테스팅 실행
    trades = bot.backtest_vectorized(data_with_signals)
    
    # 성과 출력
    bot.print_performance(year)
    
    # 결과 저장
    results = {
        'year': year,
        'initial_capital': bot.initial_capital,
        'final_capital': bot.current_capital,
        'total_trades': len(trades),
        'trades': trades
    }
    
    filename = f'btc_trend_following_results_{year}.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n결과가 '{filename}'에 저장되었습니다.")
    return results

def test_multiple_years(start_year, end_year):
    """여러 연도 테스트"""
    print(f"=== {start_year}-{end_year}년 비트코인 추세 추종 + 양방향 매매 봇 테스트 ===")
    
    all_results = {}
    total_initial_capital = 10000
    current_capital = total_initial_capital
    
    for year in range(start_year, end_year + 1):
        print(f"\n{'='*80}")
        print(f"{year}년 테스트 시작")
        print(f"{'='*80}")
        
        # 봇 초기화 (이전 연도 결과를 다음 연도 초기 자본으로 사용)
        bot = BTCTrendFollowingBotOptimized(initial_capital=current_capital)
        
        # 데이터 로드
        data = bot.load_btc_data(year)
        if data is None:
            print(f"{year}년 데이터 로드 실패 - 건너뜀")
            continue
        
        # 기술적 지표 계산
        print("기술적 지표 계산 중...")
        data_with_indicators = bot.calculate_indicators(data)
        
        # 신호 생성
        print("신호 생성 중...")
        data_with_signals = bot.get_signals_vectorized(data_with_indicators)
        
        # 백테스팅 실행
        trades = bot.backtest_vectorized(data_with_signals)
        
        # 성과 출력
        bot.print_performance(year)
        
        # 결과 저장
        year_return = (bot.current_capital - bot.initial_capital) / bot.initial_capital * 100
        all_results[year] = {
            'initial_capital': bot.initial_capital,
            'final_capital': bot.current_capital,
            'return_pct': year_return,
            'total_trades': len(trades),
            'trades': trades
        }
        
        # 다음 연도를 위한 자본 업데이트
        current_capital = bot.current_capital
        
        print(f"{year}년 수익률: {year_return:.2f}%")
        print(f"누적 자본: ${current_capital:.2f}")
    
    # 전체 성과 요약
    total_return = (current_capital - total_initial_capital) / total_initial_capital * 100
    print(f"\n{'='*80}")
    print(f"전체 기간 성과 요약 ({start_year}-{end_year})")
    print(f"{'='*80}")
    print(f"초기 자본: ${total_initial_capital:,.2f}")
    print(f"최종 자본: ${current_capital:,.2f}")
    print(f"총 수익률: {total_return:.2f}%")
    print(f"연평균 수익률: {(current_capital/total_initial_capital)**(1/(end_year-start_year+1))-1:.2f}%")
    
    # 연도별 성과 요약
    print(f"\n연도별 성과:")
    for year, result in all_results.items():
        print(f"{year}년: {result['return_pct']:.2f}% (거래 {result['total_trades']}회)")
    
    # 결과 저장
    filename = f'btc_trend_following_results_{start_year}_{end_year}.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n결과가 '{filename}'에 저장되었습니다.")
    return all_results

def main():
    """메인 실행 함수"""
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "multi":
            # 여러 연도 테스트
            start_year = int(sys.argv[2]) if len(sys.argv) > 2 else 2018
            end_year = int(sys.argv[3]) if len(sys.argv) > 3 else 2024
            test_multiple_years(start_year, end_year)
        else:
            # 단일 연도 테스트
            year = int(sys.argv[1])
            test_single_year(year)
    else:
        # 기본: 2024년 테스트
        test_single_year(2024)

if __name__ == "__main__":
    main()
