"""
rsi 매매 봇
알트전략 : 한종목당 3달러씩 진입
레버리지 50배
양방향은 아니고 단방향으로 진행
물타기 3회 진행
30분봉
롱, 숏 둘다 사용
한종목당 1달러로 매수
크로스모드 사용

전에도 한번 글을 올리긴 했었는데~ 저도 꿈에그린님하고 비슷한 생각으로... 스탑로스 없이 쭉 진행해보고 있습니다~ 몇달 진행해보고 1달러 매수에서 최근에 3달라 매수로 수정해봤네요~
그렇지요...게만아님 코드보고 수정했어요~ 초보인 제가 단순 rsi 보조지표를 참고해서 만든ㅋㅋ;;; 손절은 없고요~ 양방향은 아닙니다
네...역추세라서 반대 rsi 수익 조건되면 매도되는걸로 잡았어요
물타기 계속은 아니고요... 3번 하는걸로 로직을 짜긴했습니다~

질문 : 매수는 rsi로 딱 잡는데, 매도는 포지션스위칭할때 하시나요?
답변 : 매도도 rsi 조건 확인하고 매도됩니다~

질문 : 익절의 %트가 지정인가요?? 아님 포지션 종료도 RSI의 신호로만 하시나요?
답변 : rsi 신호로만 하는걸로 되어있어요~ 그래서 500% 먹을때도 있고 20%먹을때도 있고 그러네요...

질문 : 동시에여러종목 비중나눠서 들어가시는건가요?
답변 : 아닙니다... 같은 금액 한종목당 1달러로 매수

질문 : 30분봉상 조건넘는 rsi로 3개연달아나와도 3번연속 물타기하시나요?
답변 : 아뇨... 3번 연속 물타기 안되는 조건입니다ㅎ 

질문 : 어느정도 시간텀을두시는군요
질문 : 아니면 퍼센트로두셧나?
답변 : 1차 매수, 2차 매수, 3차 매수 조건들이 조금씩 달라요~, 퍼센트도 조건 부분에 포함되고요~
"""
"""
RSI 매매 봇

핵심 특징:
1. RSI 역추세 전략 (과매도에서 롱, 과매수에서 숏)
2. 3달러 진입, 50배 레버리지
3. 물타기 3회 (조건이 각각 다름)
4. 손절 없음, RSI 신호로만 청산
5. 30분봉 기준
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class RSIBot:
    """RSI 매매 봇"""
    
    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = {'long': None, 'short': None}
        self.trades = []
        
        # 수수료 설정 (바이낸스 기준)
        self.buy_fee = 0.0005  # 0.05%
        self.sell_fee = 0.0005  # 0.05%
        
        # 실제 전략 파라미터 (설명 기반)
        self.params = {
            'rsi_period': 14,
            'rsi_oversold': 30,      # 과매도 기준
            'rsi_overbought': 70,    # 과매수 기준
            
            # 포지션 관리
            'position_size_usd': 1,   # 3달러 진입
            'leverage': 50,          # 50배 레버리지
            'max_averaging': 3,      # 최대 물타기 3회
            
            # 물타기 조건 (가격 하락률만 체크)
            'averaging_conditions': [
                {'price_drop': 0.03},  # 1차: 5% 하락
                {'price_drop': 0.03},  # 2차: 5% 하락  
                {'price_drop': 0.03}   # 3차: 5% 하락
            ],
            
            'timeframe': '30m'
        }
    
    def load_sol_data(self, year=2025):
        """데이터 로드"""
        data_dir = f"data/SOLUSDT/1m"
        if not os.path.exists(data_dir):
            print(f"데이터 디렉토리가 없습니다: {data_dir}")
            return None
        
        file_name = f"SOLUSDT_1m_{year}.csv"
        file_path = os.path.join(data_dir, file_name)
        
        if not os.path.exists(file_path):
            print(f"{year}년 데이터 파일이 없습니다: {file_path}")
            return None
        
        print(f"솔라나 {year}년 데이터 로드 중...")
        
        try:
            data = pd.read_csv(file_path)
            data.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            data['timestamp'] = pd.to_datetime(data['timestamp'])
            data = data.set_index('timestamp')
            data = data.drop_duplicates().sort_index()
            
            # 30분봉으로 리샘플링
            data_30m = data.resample('30T').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            print(f"솔라나 {year}년 30분봉 데이터 로드 완료: {len(data_30m):,}개 캔들")
            print(f"전체 기간: {data_30m.index[0]} ~ {data_30m.index[-1]}")
            
            return data_30m
            
        except Exception as e:
            print(f"파일 읽기 오류: {e}")
            return None
    
    def calculate_rsi(self, data):
        """RSI 계산"""
        df = data.copy()
        
        # RSI 계산
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.params['rsi_period']).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.params['rsi_period']).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def get_trading_signals(self, data):
        """거래 신호 생성 (실제 전략 기반)"""
        df = data.copy()
        
        # 신호 초기화
        df['long_signal'] = False
        df['short_signal'] = False
        df['long_exit_signal'] = False
        df['short_exit_signal'] = False
        
        # 롱 진입: RSI가 과매도에서 회복
        df['long_signal'] = (
            (df['rsi'] > self.params['rsi_oversold']) & 
            (df['rsi'].shift(1) <= self.params['rsi_oversold'])
        )
        
        # 숏 진입: RSI가 과매수에서 하락
        df['short_signal'] = (
            (df['rsi'] < self.params['rsi_overbought']) & 
            (df['rsi'].shift(1) >= self.params['rsi_overbought'])
        )
        
        # 롱 청산: RSI가 과매수(80) 이상이면서 수익일 때만 청산 (반대쪽 신호)
        df['long_exit_signal'] = df['rsi'] >= self.params['rsi_overbought']
        
        # 숏 청산: RSI가 과매도(20) 이하이면서 수익일 때만 청산 (반대쪽 신호)
        df['short_exit_signal'] = df['rsi'] <= self.params['rsi_oversold']
        
        return df
    
    def backtest_strategy(self, data):
        """백테스팅 실행 (실제 전략 구현)"""
        print("RSI 전략 백테스팅 시작...")
        
        # 로그 파일 설정
        log_filename = f"rsi_bot_log_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.txt"
        log_file = open(log_filename, 'w', encoding='utf-8')
        log_file.write("=== RSI 매매 봇 거래 로그 ===\n")
        log_file.write(f"시작 시간: {pd.Timestamp.now()}\n")
        log_file.write(f"초기 자본: ${self.initial_capital:,.2f}\n")
        log_file.write("=" * 80 + "\n\n")
        
        current_capital = self.initial_capital
        positions = {'long': None, 'short': None}
        trades = []
        daily_pnl = {}
        
        for idx, row in data.iterrows():
            timestamp = idx
            price = row['close']
            rsi = row['rsi']
            
            # 자본이 음수이면 거래 중단
            if current_capital <= 0:
                break
            
            # 롱 포지션 처리
            if row['long_signal'] and positions['long'] is None and current_capital > 100:
                if self._open_long_position(price, timestamp, current_capital, positions, log_file):
                    current_capital = positions['long']['capital_after']
            
            # 숏 포지션 처리
            if row['short_signal'] and positions['short'] is None and current_capital > 100:
                if self._open_short_position(price, timestamp, current_capital, positions, log_file):
                    current_capital = positions['short']['capital_after']
            
            # 롱 포지션 청산 체크 (RSI 과매수 + 수익일 때만)
            if positions['long'] and row['long_exit_signal']:
                # 수익인지 확인
                long_pnl = (price - positions['long']['entry_price']) * positions['long']['total_size']
                if long_pnl > 0:  # 수익일 때만 청산
                    if self._close_position('long', price, timestamp, positions, trades, log_file):
                        current_capital = positions['long']['capital_after']
                        positions['long'] = None
            
            # 숏 포지션 청산 체크 (RSI 과매도 + 수익일 때만)
            if positions['short'] and row['short_exit_signal']:
                # 수익인지 확인
                short_pnl = (positions['short']['entry_price'] - price) * positions['short']['total_size']
                if short_pnl > 0:  # 수익일 때만 청산
                    if self._close_position('short', price, timestamp, positions, trades, log_file):
                        current_capital = positions['short']['capital_after']
                        positions['short'] = None
            
            # 물타기 로직 (실제 조건 기반)
            if positions['long']:
                self._check_averaging('long', price, timestamp, positions, log_file, rsi)
            if positions['short']:
                self._check_averaging('short', price, timestamp, positions, log_file, rsi)
            
            # 일별 PnL 기록
            date_str = timestamp.strftime('%Y-%m-%d')
            if date_str not in daily_pnl:
                daily_pnl[date_str] = 0
        
        # 최종 자본 업데이트
        self.current_capital = current_capital
        self.trades = trades
        
        # 로그 파일 마무리
        log_file.write("\n" + "=" * 80 + "\n")
        log_file.write(f"백테스팅 종료 시간: {pd.Timestamp.now()}\n")
        log_file.write(f"최종 자본: ${current_capital:,.2f}\n")
        log_file.write(f"총 거래 수: {len(trades)}회\n")
        log_file.close()
        
        print(f"거래 로그가 '{log_filename}' 파일에 저장되었습니다.")
        
        return trades, daily_pnl
    
    def _open_long_position(self, price, timestamp, current_capital, positions, log_file):
        """롱 포지션 진입"""
        if current_capital <= 0:
            return False
        
        # 포지션 크기 계산 (3달러, 50배 레버리지)
        position_size_usd = self.params['position_size_usd'] * self.params['leverage']
        position_size = position_size_usd / price
        
        # 진입 수수료
        fee = position_size_usd * self.buy_fee
        
        if fee >= current_capital:
            return False
        
        # 포지션 정보 저장
        positions['long'] = {
            'entry_price': price,
            'size': position_size,
            'entry_time': timestamp,
            'fee': fee,
            'capital_after': current_capital - fee,
            'averaging_count': 0,
            'total_size': position_size,
            'total_cost': position_size_usd + fee,
            'averaging_prices': [price],  # 물타기 가격 기록
            'averaging_times': [timestamp]  # 물타기 시간 기록
        }
        
        log_msg = f"[{timestamp}] SOL LONG 진입 - 가격: {price:.4f}, 크기: {position_size:.6f}, 수수료: {fee:.2f}, 자본: ${current_capital - fee:.2f}"
        print(log_msg)
        log_file.write(log_msg + "\n")
        return True
    
    def _open_short_position(self, price, timestamp, current_capital, positions, log_file):
        """숏 포지션 진입"""
        if current_capital <= 0:
            return False
        
        # 포지션 크기 계산 (3달러, 50배 레버리지)
        position_size_usd = self.params['position_size_usd'] * self.params['leverage']
        position_size = position_size_usd / price
        
        # 진입 수수료
        fee = position_size_usd * self.buy_fee
        
        if fee >= current_capital:
            return False
        
        # 포지션 정보 저장
        positions['short'] = {
            'entry_price': price,
            'size': position_size,
            'entry_time': timestamp,
            'fee': fee,
            'capital_after': current_capital - fee,
            'averaging_count': 0,
            'total_size': position_size,
            'total_cost': position_size_usd + fee,
            'averaging_prices': [price],  # 물타기 가격 기록
            'averaging_times': [timestamp]  # 물타기 시간 기록
        }
        
        log_msg = f"[{timestamp}] SOL SHORT 진입 - 가격: {price:.4f}, 크기: {position_size:.6f}, 수수료: {fee:.2f}, 자본: ${current_capital - fee:.2f}"
        print(log_msg)
        log_file.write(log_msg + "\n")
        return True
    
    def _check_averaging(self, position_type, price, timestamp, positions, log_file, rsi):
        """물타기 체크 (실제 조건 기반)"""
        position = positions[position_type]
        if not position or position['averaging_count'] >= self.params['max_averaging']:
            return
        
        # 물타기 조건 체크
        averaging_condition = self.params['averaging_conditions'][position['averaging_count']]
        
        # 손실률 계산
        if position_type == 'long':
            loss_pct = (position['entry_price'] - price) / position['entry_price']
        else:  # short
            loss_pct = (price - position['entry_price']) / position['entry_price']
        
        # 물타기 조건: 롱일 때는 -5% 이상 하락 + RSI 30 이하
        if position_type == 'long':
            if loss_pct >= averaging_condition['price_drop'] and rsi <= self.params['rsi_oversold']:
                # 물타기 실행
                additional_size = self.params['position_size_usd'] * self.params['leverage'] / price
                additional_fee = self.params['position_size_usd'] * self.params['leverage'] * self.buy_fee
                
                # 포지션 업데이트
                position['total_size'] += additional_size
                position['total_cost'] += self.params['position_size_usd'] * self.params['leverage'] + additional_fee
                position['averaging_count'] += 1
                position['capital_after'] -= additional_fee
                position['averaging_prices'].append(price)
                position['averaging_times'].append(timestamp)
                
                log_msg = f"[{timestamp}] {position_type.upper()} 물타기 #{position['averaging_count']} - 가격: {price:.4f}, 추가크기: {additional_size:.6f}, 손실률: {loss_pct*100:.2f}%, RSI: {rsi:.2f}"
                print(log_msg)
                log_file.write(log_msg + "\n")
        
        # 숏일 때는 -5% 이상 하락 + RSI 70 이상
        elif position_type == 'short':
            if loss_pct >= averaging_condition['price_drop'] and rsi >= self.params['rsi_overbought']:
                # 물타기 실행
                additional_size = self.params['position_size_usd'] * self.params['leverage'] / price
                additional_fee = self.params['position_size_usd'] * self.params['leverage'] * self.buy_fee
                
                # 포지션 업데이트
                position['total_size'] += additional_size
                position['total_cost'] += self.params['position_size_usd'] * self.params['leverage'] + additional_fee
                position['averaging_count'] += 1
                position['capital_after'] -= additional_fee
                position['averaging_prices'].append(price)
                position['averaging_times'].append(timestamp)
                
                log_msg = f"[{timestamp}] {position_type.upper()} 물타기 #{position['averaging_count']} - 가격: {price:.4f}, 추가크기: {additional_size:.6f}, 손실률: {loss_pct*100:.2f}%, RSI: {rsi:.2f}"
                print(log_msg)
                log_file.write(log_msg + "\n")
    
    def _close_position(self, position_type, price, timestamp, positions, trades, log_file):
        """포지션 청산"""
        position = positions[position_type]
        if not position:
            return False
        
        # PnL 계산
        if position_type == 'long':
            pnl = (price - position['entry_price']) * position['total_size']
        else:  # short
            pnl = (position['entry_price'] - price) * position['total_size']
        
        # 청산 수수료
        exit_trade_amount = position['total_size'] * price
        exit_fee = exit_trade_amount * self.sell_fee
        net_pnl = pnl - exit_fee
        
        # 자본 업데이트
        new_capital = position['capital_after'] + net_pnl
        position['capital_after'] = new_capital
        
        pnl_pct = net_pnl / position['total_cost'] if position['total_cost'] > 0 else 0
        
        # 거래 기록
        trade = {
            'entry_time': position['entry_time'],
            'exit_time': timestamp,
            'position_type': position_type,
            'entry_price': position['entry_price'],
            'exit_price': price,
            'size': position['total_size'],
            'pnl': net_pnl,
            'pnl_pct': pnl_pct,
            'averaging_count': position['averaging_count'],
            'total_cost': position['total_cost'],
            'averaging_prices': position['averaging_prices'],
            'averaging_times': position['averaging_times']
        }
        trades.append(trade)
        
        log_msg = f"[{timestamp}] SOL {position_type.upper()} 청산 - 가격: {price:.4f}, PnL: {net_pnl:.2f} ({pnl_pct:.2f}%), 물타기: {position['averaging_count']}회, 자본: ${new_capital:.2f}"
        print(log_msg)
        log_file.write(log_msg + "\n")
        
        return True
    
    def print_performance(self, year=None):
        """성과 출력"""
        if not self.trades:
            print("거래 기록이 없습니다.")
            return
        
        total_return = (self.current_capital - self.initial_capital) / self.initial_capital * 100
        total_trades = len(self.trades)
        winning_trades = len([t for t in self.trades if t['pnl'] > 0])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        # 평균 수익/손실
        winning_pnl = [t['pnl'] for t in self.trades if t['pnl'] > 0]
        losing_pnl = [t['pnl'] for t in self.trades if t['pnl'] <= 0]
        
        avg_win = np.mean(winning_pnl) if winning_pnl else 0
        avg_loss = np.mean(losing_pnl) if losing_pnl else 0
        
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
        total_fees = sum(t.get('entry_fee', 0) + t.get('exit_fee', 0) for t in self.trades)
        
        year_text = f" ({year}년)" if year else ""
        print(f"\RSI 매매 봇 성과{year_text}")
        print("=" * 60)
        print(f"초기 자본: ${self.initial_capital:,.2f}")
        print(f"최종 자본: ${self.current_capital:,.2f}")
        print(f"총 수익률: {total_return:.2f}%")
        print(f"총 거래 수: {total_trades}회")
        print(f"승률: {win_rate:.1f}%")
        print(f"평균 수익: ${avg_win:.2f}")
        print(f"평균 손실: ${avg_loss:.2f}")
        print(f"최대 낙폭: -{max_dd*100:.2f}%")
        print(f"총 수수료: ${total_fees:.2f}")
        
        # 일별 수익 분석
        self._analyze_daily_performance()
        
        # 물타기 분석
        self._analyze_averaging_performance()
    
    def _analyze_daily_performance(self):
        """일별 성과 분석"""
        if not self.trades:
            return
        
        daily_pnl = {}
        for trade in self.trades:
            date_str = trade['exit_time'].strftime('%Y-%m-%d')
            if date_str not in daily_pnl:
                daily_pnl[date_str] = 0
            daily_pnl[date_str] += trade['pnl']
        
        # 일별 수익 통계
        daily_values = list(daily_pnl.values())
        positive_days = len([v for v in daily_values if v > 0])
        total_days = len(daily_values)
        
        print(f"\n일별 성과 분석:")
        print(f"거래일 수: {total_days}일")
        print(f"수익일 수: {positive_days}일")
        print(f"수익일 비율: {positive_days/total_days*100:.1f}%")
        print(f"평균 일일 수익: ${np.mean(daily_values):.2f}")
        print(f"최대 일일 수익: ${max(daily_values):.2f}")
        print(f"최소 일일 수익: ${min(daily_values):.2f}")
    
    def _analyze_averaging_performance(self):
        """물타기 성과 분석"""
        if not self.trades:
            return
        
        # 물타기별 성과
        no_averaging = [t for t in self.trades if t['averaging_count'] == 0]
        one_averaging = [t for t in self.trades if t['averaging_count'] == 1]
        two_averaging = [t for t in self.trades if t['averaging_count'] == 2]
        three_averaging = [t for t in self.trades if t['averaging_count'] == 3]
        
        print(f"\n물타기 성과 분석:")
        print(f"물타기 없음: {len(no_averaging)}회, 평균 PnL: ${np.mean([t['pnl'] for t in no_averaging]):.2f}")
        print(f"1회 물타기: {len(one_averaging)}회, 평균 PnL: ${np.mean([t['pnl'] for t in one_averaging]):.2f}")
        print(f"2회 물타기: {len(two_averaging)}회, 평균 PnL: ${np.mean([t['pnl'] for t in two_averaging]):.2f}")
        print(f"3회 물타기: {len(three_averaging)}회, 평균 PnL: ${np.mean([t['pnl'] for t in three_averaging]):.2f}")

def test_sol_rsi_strategy(year=2025):
    """RSI 전략 테스트"""
    print(f"=== {year}년 RSI 매매 봇 테스트 ===")
    
    # 봇 초기화
    bot = RSIBot(initial_capital=10000)
    
    # 데이터 로드
    data = bot.load_sol_data(year)
    if data is None:
        print(f"{year}년 솔라나 데이터 로드 실패")
        return None
    
    # RSI 계산
    print("RSI 계산 중...")
    data_with_rsi = bot.calculate_rsi(data)
    
    # 거래 신호 생성
    print("거래 신호 생성 중...")
    data_with_signals = bot.get_trading_signals(data_with_rsi)
    
    # 백테스팅 실행
    trades, daily_pnl = bot.backtest_strategy(data_with_signals)
    
    # 성과 출력
    bot.print_performance(year)
    
    # 결과 저장
    results = {
        'year': year,
        'initial_capital': bot.initial_capital,
        'final_capital': bot.current_capital,
        'total_trades': len(trades),
        'trades': trades,
        'daily_pnl': daily_pnl
    }
    
    filename = f'rsi_bot_results_{year}.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n결과가 '{filename}'에 저장되었습니다.")
    return results

if __name__ == "__main__":
    # 2025년 솔라나 데이터로 테스트
    test_sol_rsi_strategy(2025)