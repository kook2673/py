"""
비트코인 추세 추종 + 양방향 매매 봇 (2024년 실제 데이터)

=== 전략 개요 ===
- 추세 추종에 편승하면 단방향 매매 (롱 또는 숏)
- 추세 이탈하면 양방향 매매로 전환
- 2024년 비트코인 1분 데이터 사용
- 구매/판매 수수료 각 0.05% 적용

=== 핵심 로직 ===
1. 추세 감지: 이동평균선 교차 + RSI + 볼린저 밴드
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

class BTCTrendFollowingBot:
    """비트코인 추세 추종 + 양방향 매매 봇"""
    
    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = {'long': None, 'short': None}  # 포지션 정보
        self.trades = []
        
        # 수수료 설정
        self.buy_fee = 0.0005  # 0.05%
        self.sell_fee = 0.0005  # 0.05%
        
        # 전략 파라미터
        self.params = {
            'ma_short': 20,      # 단기 이동평균
            'ma_long': 50,       # 장기 이동평균
            'rsi_period': 14,    # RSI 기간
            'bb_period': 20,     # 볼린저 밴드 기간
            'bb_std': 2,         # 볼린저 밴드 표준편차
            'dc_period': 25,     # 돈키안 채널 기간
            'trend_threshold': 0.02,  # 추세 강도 임계값
            'position_size': 0.5,     # 포지션 크기 (자본의 50%)
            'stop_loss': 0.03,        # 손절 3%
            'take_profit': 0.05,      # 익절 5%
            'trailing_stop': 0.005,   # 트레일링스탑 0.%
        }
    
    def load_btc_data(self, start_year=2018, end_year=2025):
        """비트코인 데이터 로드 (여러 연도)"""
        all_data = []
        
        for year in range(start_year, end_year + 1):
            data_path = f"data/BTCUSDT/1m/BTCUSDT_1m_{year}.csv"
            try:
                if os.path.exists(data_path):
                    df = pd.read_csv(data_path)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    all_data.append(df)
                    print(f"비트코인 {year}년 데이터 로드 완료: {len(df)}개 캔들")
                else:
                    print(f"경고: {year}년 데이터 파일을 찾을 수 없습니다: {data_path}")
            except Exception as e:
                print(f"경고: {year}년 데이터 로드 실패: {e}")
        
        if not all_data:
            raise FileNotFoundError("로드할 수 있는 데이터가 없습니다.")
        
        # 모든 데이터 합치기
        combined_df = pd.concat(all_data, ignore_index=True)
        combined_df = combined_df.sort_values('timestamp').reset_index(drop=True)
        
        print(f"전체 기간: {combined_df['timestamp'].min()} ~ {combined_df['timestamp'].max()}")
        return combined_df
    
    def calculate_indicators(self, data):
        """기술적 지표 계산"""
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
        df['trend_strength'] = abs(df['ma_short'] - df['ma_long']) / df['ma_long']
        
        # 추세 방향
        df['trend_direction'] = np.where(df['ma_short'] > df['ma_long'], 1, -1)
        
        return df
    
    def detect_trend_mode(self, df):
        """추세 모드 감지"""
        if len(df) < self.params['ma_long']:
            return 'unknown'
        
        current = df.iloc[-1]
        trend_strength = current['trend_strength']
        trend_direction = current['trend_direction']
        rsi = current['rsi']
        
        # 강한 추세 감지
        if trend_strength > self.params['trend_threshold']:
            if trend_direction > 0 and rsi < 70:  # 상승 추세
                return 'strong_uptrend'
            elif trend_direction < 0 and rsi > 30:  # 하락 추세
                return 'strong_downtrend'
        
        # 약한 추세 또는 횡보
        return 'sideways'
    
    def generate_signals(self, df, trend_mode):
        """신호 생성"""
        current = df.iloc[-1]
        
        signals = {
            'long_signal': False,
            'short_signal': False,
            'trend_mode': trend_mode
        }
        
        if trend_mode == 'strong_uptrend':
            # 상승 추세: 롱만 신호 (돈키안 채널 추가)
            signals['long_signal'] = (
                current['close'] > current['ma_short'] and
                current['rsi'] < 70 and
                current['close'] > current['bb_lower'] and
                current['close'] > current['dc_middle'] and
                current['close'] > current['dc_low'] * 1.02  # 돈키안 하단 돌파
            )
            
        elif trend_mode == 'strong_downtrend':
            # 하락 추세: 숏만 신호 (돈키안 채널 추가)
            signals['short_signal'] = (
                current['close'] < current['ma_short'] and
                current['rsi'] > 30 and
                current['close'] < current['bb_upper'] and
                current['close'] < current['dc_middle'] and
                current['close'] < current['dc_high'] * 0.98  # 돈키안 상단 돌파
            )
            
        elif trend_mode == 'sideways':
            # 횡보: 양방향 신호 (돈키안 채널 추가)
            signals['long_signal'] = (
                current['close'] > current['bb_lower'] and
                current['rsi'] < 50 and
                current['close'] > current['dc_middle'] and
                current['close'] > current['dc_low'] * 1.01
            )
            signals['short_signal'] = (
                current['close'] < current['bb_upper'] and
                current['rsi'] > 50 and
                current['close'] < current['dc_middle'] and
                current['close'] < current['dc_high'] * 0.99
            )
        
        return signals
    
    def calculate_position_size(self, price):
        """포지션 크기 계산"""
        available_capital = self.current_capital * self.params['position_size']
        return available_capital / price
    
    def open_position(self, position_type, price, timestamp):
        """포지션 진입"""
        position_size = self.calculate_position_size(price)
        
        # 수수료 계산 (거래 금액의 0.05%)
        trade_amount = position_size * price
        fee = trade_amount * self.buy_fee
        
        if self.current_capital < fee:
            return False
        
        position = {
            'type': position_type,
            'entry_price': price,
            'size': position_size,
            'entry_time': timestamp,
            'fee': fee,
            'trailing_stop_price': None
        }
        
        self.positions[position_type] = position
        self.current_capital -= fee
        
        print(f"[{timestamp}] BTC {position_type.upper()} 진입 - 가격: {price:.2f}, 수수료: {fee:.2f}, 자본: ${self.current_capital:.2f}")
        return True
    
    def close_position(self, position_type, price, timestamp, reason):
        """포지션 청산"""
        position = self.positions[position_type]
        if not position:
            return
        
        # PnL 계산
        if position_type == 'long':
            pnl = (price - position['entry_price']) * position['size']
        else:  # short
            pnl = (position['entry_price'] - price) * position['size']
        
        # 청산 수수료 (거래 금액의 0.05%)
        exit_trade_amount = position['size'] * price
        exit_fee = exit_trade_amount * self.sell_fee
        net_pnl = pnl - exit_fee
        
        # 자본 업데이트
        self.current_capital += net_pnl
        
        # 거래 기록
        trade = {
            'type': position_type,
            'entry_time': position['entry_time'],
            'exit_time': timestamp,
            'entry_price': position['entry_price'],
            'exit_price': price,
            'size': position['size'],
            'pnl': net_pnl,
            'gross_pnl': pnl,
            'entry_fee': position['fee'],
            'exit_fee': exit_fee,
            'total_fee': position['fee'] + exit_fee,
            'exit_reason': reason,
            'duration': (pd.to_datetime(timestamp) - pd.to_datetime(position['entry_time'])).total_seconds() / 3600  # 시간
        }
        
        self.trades.append(trade)
        
        # 포지션 제거
        self.positions[position_type] = None
        
        pnl_pct = (net_pnl / (position['entry_price'] * position['size'])) * 100
        print(f"[{timestamp}] BTC {position_type.upper()} 청산 - 가격: {price:.2f}, PnL: {net_pnl:.2f} ({pnl_pct:.2f}%), 이유: {reason}, 자본: ${self.current_capital:.2f}")
    
    def update_trailing_stop(self, position_type, current_price):
        """트레일링스탑 업데이트"""
        position = self.positions[position_type]
        if not position:
            return
        
        if position_type == 'long':
            # 롱 포지션: 가격이 상승하면 트레일링스탑 상향 조정
            if position['trailing_stop_price'] is None:
                position['trailing_stop_price'] = current_price * (1 - self.params['trailing_stop'])
            else:
                new_trailing_stop = current_price * (1 - self.params['trailing_stop'])
                if new_trailing_stop > position['trailing_stop_price']:
                    position['trailing_stop_price'] = new_trailing_stop
        
        else:  # short
            # 숏 포지션: 가격이 하락하면 트레일링스탑 하향 조정
            if position['trailing_stop_price'] is None:
                position['trailing_stop_price'] = current_price * (1 + self.params['trailing_stop'])
            else:
                new_trailing_stop = current_price * (1 + self.params['trailing_stop'])
                if new_trailing_stop < position['trailing_stop_price']:
                    position['trailing_stop_price'] = new_trailing_stop
    
    def check_exit_conditions(self, position_type, current_price, current_time, signals):
        """청산 조건 확인"""
        position = self.positions[position_type]
        if not position:
            return False, None
        
        # 트레일링스탑 업데이트
        self.update_trailing_stop(position_type, current_price)
        
        # 손절/익절 확인
        if position_type == 'long':
            # 롱 포지션 청산 조건
            if current_price <= position['entry_price'] * (1 - self.params['stop_loss']):
                return True, f"손절 ({self.params['stop_loss']*100:.1f}%)"
            
            if current_price >= position['entry_price'] * (1 + self.params['take_profit']):
                return True, f"익절 ({self.params['take_profit']*100:.1f}%)"
            
            # 트레일링스탑
            if (position['trailing_stop_price'] and 
                current_price <= position['trailing_stop_price']):
                return True, f"트레일링스탑 ({self.params['trailing_stop']*100:.1f}%)"
            
            # 반대 신호 (추세 추종 모드에서만)
            if signals['trend_mode'] in ['strong_uptrend', 'strong_downtrend'] and signals['short_signal']:
                return True, "반대 신호"
        
        else:  # short
            # 숏 포지션 청산 조건
            if current_price >= position['entry_price'] * (1 + self.params['stop_loss']):
                return True, f"손절 ({self.params['stop_loss']*100:.1f}%)"
            
            if current_price <= position['entry_price'] * (1 - self.params['take_profit']):
                return True, f"익절 ({self.params['take_profit']*100:.1f}%)"
            
            # 트레일링스탑
            if (position['trailing_stop_price'] and 
                current_price >= position['trailing_stop_price']):
                return True, f"트레일링스탑 ({self.params['trailing_stop']*100:.1f}%)"
            
            # 반대 신호 (추세 추종 모드에서만)
            if signals['trend_mode'] in ['strong_uptrend', 'strong_downtrend'] and signals['long_signal']:
                return True, "반대 신호"
        
        return False, None
    
    def process_data(self, data, start_idx=50):
        """데이터 처리 및 백테스트"""
        print("백테스트 시작...")
        
        # 지표 계산
        df = self.calculate_indicators(data)
        
        # 백테스트 실행
        for i in range(start_idx, len(df)):
            current_time = df.index[i]
            current_data = df.iloc[:i+1]
            current_price = current_data['close'].iloc[-1]
            
            # 추세 모드 감지
            trend_mode = self.detect_trend_mode(current_data)
            
            # 신호 생성
            signals = self.generate_signals(current_data, trend_mode)
            
            # 기존 포지션 청산 조건 확인
            for position_type in ['long', 'short']:
                if self.positions[position_type]:
                    should_exit, reason = self.check_exit_conditions(
                        position_type, current_price, current_time, signals
                    )
                    if should_exit:
                        self.close_position(position_type, current_price, current_time, reason)
            
            # 새 포지션 진입
            if signals['long_signal'] and not self.positions['long']:
                self.open_position('long', current_price, current_time)
            
            if signals['short_signal'] and not self.positions['short']:
                self.open_position('short', current_price, current_time)
    
    def get_performance_stats(self):
        """성과 통계"""
        if not self.trades:
            return {
                'total_return': 0,
                'total_trades': 0,
                'win_rate': 0,
                'max_drawdown': 0,
                'total_fees': 0
            }
        
        trades_df = pd.DataFrame(self.trades)
        
        # 기본 통계
        total_return = (self.current_capital - self.initial_capital) / self.initial_capital * 100
        total_trades = len(self.trades)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        total_fees = trades_df['total_fee'].sum()
        
        # 최대 낙폭 계산
        capital_series = [self.initial_capital]
        for trade in self.trades:
            capital_series.append(capital_series[-1] + trade['pnl'])
        
        capital_series = np.array(capital_series)
        running_max = np.maximum.accumulate(capital_series)
        drawdown = (capital_series - running_max) / running_max * 100
        max_drawdown = np.min(drawdown)
        
        return {
            'total_return': total_return,
            'final_capital': self.current_capital,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'total_fees': total_fees,
            'avg_trade_duration': trades_df['duration'].mean() if total_trades > 0 else 0
        }
    
    def print_performance(self):
        """성과 출력"""
        stats = self.get_performance_stats()
        
        print("\n" + "="*60)
        print("비트코인 추세 추종 + 양방향 매매 봇 성과 (2024년)")
        print("="*60)
        print(f"초기 자본: ${self.initial_capital:,.2f}")
        print(f"최종 자본: ${stats['final_capital']:,.2f}")
        print(f"총 수익률: {stats['total_return']:.2f}%")
        print(f"총 거래 수: {stats['total_trades']}회")
        print(f"승률: {stats['win_rate']:.1f}%")
        print(f"최대 낙폭: {stats['max_drawdown']:.2f}%")
        print(f"총 수수료: ${stats['total_fees']:.2f}")
        print(f"평균 보유 시간: {stats['avg_trade_duration']:.1f}시간")
        
        # 연도별 성과 분석
        self.print_yearly_performance()
        
        # 거래 유형별 성과
        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            type_performance = trades_df.groupby('type')['pnl'].agg(['sum', 'count']).round(2)
            type_performance.columns = ['총_PnL', '거래수']
            type_performance['승률'] = (trades_df.groupby('type').apply(
                lambda x: (x['pnl'] > 0).sum() / len(x) * 100
            )).round(1)
            
            print(f"\n거래 유형별 성과:")
            print(type_performance)
    
    def print_yearly_performance(self):
        """연도별 성과 출력"""
        print(f"\n연도별 성과 분석:")
        print("-" * 80)
        
        # 연도별로 거래 그룹화
        yearly_trades = {}
        for trade in self.trades:
            # entry_time이 정수인 경우 datetime으로 변환
            if isinstance(trade['entry_time'], int):
                entry_time = pd.to_datetime(trade['entry_time'], unit='s')
            else:
                entry_time = trade['entry_time']
            year = entry_time.year
            if year not in yearly_trades:
                yearly_trades[year] = []
            yearly_trades[year].append(trade)
        
        # 연도별 성과 계산
        yearly_performance = []
        for year in sorted(yearly_trades.keys()):
            trades = yearly_trades[year]
            total_pnl = sum(t['pnl'] for t in trades)
            total_fees = sum(t['total_fee'] for t in trades)
            winning_trades = [t for t in trades if t['pnl'] > 0]
            win_rate = (len(winning_trades) / len(trades)) * 100 if trades else 0
            
            yearly_performance.append({
                'year': year,
                'trades': len(trades),
                'pnl': total_pnl,
                'fees': total_fees,
                'win_rate': win_rate
            })
        
        # 연도별 성과 출력
        for perf in yearly_performance:
            print(f"{perf['year']}년: 거래 {perf['trades']}회, PnL ${perf['pnl']:.2f}, "
                  f"수수료 ${perf['fees']:.2f}, 승률 {perf['win_rate']:.1f}%")


def main():
    """메인 실행 함수"""
    print("=== 비트코인 추세 추종 + 양방향 매매 봇 (2024년) ===")
    
    # 봇 초기화
    bot = BTCTrendFollowingBot(initial_capital=10000)
    
    # 비트코인 데이터 로드 (2024년만)
    data = bot.load_btc_data(2024, 2024)
    
    if data.empty:
        print("데이터를 로드할 수 없습니다.")
        return
    
    # 백테스트 실행
    bot.process_data(data)
    
    # 성과 출력
    bot.print_performance()
    
    # 결과 저장
    results = {
        'strategy': 'btc_trend_following_bidirectional',
        'period': '2024',
        'performance': bot.get_performance_stats(),
        'trades': bot.trades
    }
    
    with open('btc_trend_following_results_2024.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n결과가 btc_trend_following_results_2024.json에 저장되었습니다.")


if __name__ == "__main__":
    main()
