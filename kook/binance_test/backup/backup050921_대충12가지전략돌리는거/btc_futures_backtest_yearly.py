#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
비트코인 선물 3배 레버리지 전략 - 연도별 백테스팅
ETFStrength.py의 전략을 바이낸스 선물에 적용하여 연도별로 백테스팅

1) 전략 개요
- 대상: BTCUSDT 선물 (3배 레버리지)
- 신호: ATR 기반 트레일링 스탑 + 모멘텀 신호
- 배분: 총자산의 20%를 전략 예산으로 사용
- 데이터: 연도별 1일 데이터 사용 (2018-2025)

2) 신호 생성
- 상승 신호: 가격 상승률 + 거래량 + ATR 조건
- 하락 신호: 가격 하락률 + 거래량 + ATR 조건
- ATR 트레일링 스탑으로 손절/익절
"""

import os
import sys
import json
import time
import logging
import gc
import psutil
from datetime import datetime, timedelta
from typing import Optional, Tuple
import pandas as pd
import numpy as np

# 상위 디렉토리를 sys.path에 추가
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)

BOT_NAME = "BTCFuturesYearly"
PortfolioName = "[비트코인선물3배전략-연도별]"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, f'{BOT_NAME}.log'), mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 파일 경로
config_file_path = os.path.join(script_dir, f'{BOT_NAME}_config.json')
trades_csv_path = os.path.join(logs_dir, f"{BOT_NAME}_trades.csv")
daily_csv_path = os.path.join(logs_dir, f"{BOT_NAME}_daily.csv")
results_csv_path = os.path.join(logs_dir, f"{BOT_NAME}_results.csv")

# 전략 설정
SYMBOL = 'BTCUSDT'
LEVERAGE = 5.0  # 5배 레버리지
TRADING_FEE = 0.0006  # 0.06% 수수료 (바이낸스 선물)

def load_yearly_data(year: int, interval: str = '1d') -> Optional[pd.DataFrame]:
    """연도별 데이터 로드"""
    try:
        data_dir = os.path.join(script_dir, "data", "BTCUSDT", interval)
        filename = f"BTCUSDT_{interval}_{year}.csv"
        filepath = os.path.join(data_dir, filename)
        
        if not os.path.exists(filepath):
            logging.warning(f"데이터 파일이 없습니다: {filepath}")
            return None
        
        df = pd.read_csv(filepath, index_col=0, parse_dates=True)
        logging.info(f"{year}년 {interval} 데이터 로드 완료: {len(df)}개 (기간: {df.index[0]} ~ {df.index[-1]})")
        return df
        
    except Exception as e:
        logging.error(f"{year}년 {interval} 데이터 로드 실패: {e}")
        return None

def prepare_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """기술적 지표 계산"""
    out = df.copy()
    
    # 기본 지표
    out['pct'] = out['close'].pct_change()
    rng = (out['high'] - out['low']).replace(0, np.nan)
    out['close_to_range'] = ((out['close'] - out['low']) / rng).clip(0, 1)
    out['vol_ma20'] = out['volume'].rolling(20).mean()
    out['vol_ratio'] = out['volume'] / out['vol_ma20']
    
    # ATR 계산
    try:
        import talib
        out['atr'] = talib.ATR(out['high'], out['low'], out['close'], timeperiod=14)
    except Exception:
        # 간이 ATR 계산
        tr = []
        prev_close = out['close'].iloc[0]
        for i in range(1, len(out)):
            cur_high = out['high'].iloc[i]
            cur_low = out['low'].iloc[i]
            tr.append(max(cur_high - cur_low, abs(cur_high - prev_close), abs(cur_low - prev_close)))
            prev_close = out['close'].iloc[i]
        
        out['atr'] = np.nan
        if len(tr) > 0:
            out.loc[out.index[1]:, 'atr'] = pd.Series(tr, index=out.index[1:]).rolling(14).mean()
    
    return out

def calculate_ma_long_short_ratio(df: pd.DataFrame) -> tuple:
    """MA 기반 롱/숏 비율 계산 (0:100 ~ 100:0)"""
    # MA 10일, 20일, 30일, 40일, 50일, 60일, 70일, 80일, 90일, 100일
    ma_periods = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    ma_values = {}
    
    for period in ma_periods:
        ma_values[f'ma{period}'] = df['close'].rolling(window=period).mean()
    
    # 현재 가격이 각 MA 위에 있는지 확인
    above_ma_count = 0
    for period in ma_periods:
        above_ma_count += (df['close'] > ma_values[f'ma{period}']).astype(int)
    
    # 0~10개 MA 위에 있으면 0~100% 롱 비율
    long_ratio = (above_ma_count / len(ma_periods)) * 100
    short_ratio = 100 - long_ratio
    
    return long_ratio, short_ratio

def calculate_all_signals(df: pd.DataFrame, params: dict) -> dict:
    """12개 전략의 모든 신호 계산"""
    signals = {}
    
    # MA 기반 롱/숏 비율 계산
    long_ratio, short_ratio = calculate_ma_long_short_ratio(df)
    df['long_ratio'] = long_ratio
    df['short_ratio'] = short_ratio
    df['long_probability'] = long_ratio / 100.0
    df['short_probability'] = short_ratio / 100.0
    
    # 1. 모멘텀 전략 신호
    df['momentum_20'] = df['close'].pct_change(20)
    
    # 모멘텀 롱 신호
    momentum_long_condition = df['momentum_20'] > 0.02
    momentum_long_entry = momentum_long_condition & (np.random.random(len(df)) < df['long_probability'])
    signals['momentum_long'] = (momentum_long_entry & (df['momentum_20'] > 0.02)).astype(int)
    
    # 모멘텀 숏 신호
    momentum_short_condition = df['momentum_20'] < -0.02
    momentum_short_entry = momentum_short_condition & (np.random.random(len(df)) < df['short_probability'])
    signals['momentum_short'] = (momentum_short_entry & (df['momentum_20'] < -0.02)).astype(int)
    
    # 2. 스캘핑 전략 신호
    df['volatility_5'] = df['close'].pct_change().rolling(5).std()
    df['price_change_5'] = df['close'].pct_change(5)
    
    # 스캘핑 롱 신호
    scalping_long_condition = (df['volatility_5'] > 0.005) & (df['price_change_5'] > 0.003)
    scalping_long_entry = scalping_long_condition & (np.random.random(len(df)) < df['long_probability'])
    signals['scalping_long'] = scalping_long_entry.astype(int)
    
    # 스캘핑 숏 신호
    scalping_short_condition = (df['volatility_5'] > 0.012) & (df['price_change_5'] < -0.008)
    scalping_short_entry = scalping_short_condition & (np.random.random(len(df)) < df['short_probability'])
    signals['scalping_short'] = scalping_short_entry.astype(int)
    
    # 3. MACD 전략 신호
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9).mean()
    macd_cross_up = (macd > macd_signal) & (macd.shift(1) <= macd_signal.shift(1))
    macd_cross_down = (macd < macd_signal) & (macd.shift(1) >= macd_signal.shift(1))
    
    # MACD 롱 신호
    macd_long_entry = macd_cross_up & (np.random.random(len(df)) < df['long_probability'])
    signals['macd_long'] = macd_long_entry.astype(int)
    
    # MACD 숏 신호
    macd_short_entry = macd_cross_down & (np.random.random(len(df)) < df['short_probability'])
    signals['macd_short'] = macd_short_entry.astype(int)
    
    # 4. 이동평균 전략 신호
    ma20 = df['close'].rolling(window=20).mean()
    ma50 = df['close'].rolling(window=50).mean()
    ma100 = df['close'].rolling(window=100).mean()
    
    df['ma20'] = ma20
    df['ma50'] = ma50
    df['ma100'] = ma100
    ma_cross_up = (ma20 > ma50) & (ma20.shift(1) <= ma50.shift(1))
    ma_cross_down = (ma20 < ma50) & (ma20.shift(1) >= ma50.shift(1))
    
    # 이동평균 롱 신호
    ma_long_entry = ma_cross_up & (np.random.random(len(df)) < df['long_probability'])
    signals['moving_average_long'] = ma_long_entry.astype(int)
    
    # 이동평균 숏 신호
    ma_short_entry = ma_cross_down & (np.random.random(len(df)) < df['short_probability'])
    signals['moving_average_short'] = ma_short_entry.astype(int)
    
    # 5. 트렌드 전략 신호
    strong_uptrend = (ma20 > ma50) & (ma50 > ma100)
    price_above_ma20 = df['close'] > ma20
    positive_momentum = df['momentum_20'] > 0.01
    
    trend_long_condition = strong_uptrend & price_above_ma20 & positive_momentum
    trend_long_entry = trend_long_condition & (np.random.random(len(df)) < df['long_probability'])
    signals['trend_long'] = trend_long_entry.astype(int)
    
    strong_downtrend = (ma20 < ma50) & (ma50 < ma100)
    price_below_ma20 = df['close'] < ma20
    negative_momentum = df['momentum_20'] < -0.01
    
    trend_short_condition = strong_downtrend & price_below_ma20 & negative_momentum
    trend_short_entry = trend_short_condition & (np.random.random(len(df)) < df['short_probability'])
    signals['trend_short'] = trend_short_entry.astype(int)
    
    # 6. 볼린저 밴드 전략 신호
    df['bb_upper'] = df['close'].rolling(20).mean() + (df['close'].rolling(20).std() * 2)
    df['bb_lower'] = df['close'].rolling(20).mean() - (df['close'].rolling(20).std() * 2)
    
    # 볼린저 밴드 롱 신호
    bb_long_condition = df['close'] <= df['bb_lower']
    bb_long_entry = bb_long_condition & (np.random.random(len(df)) < df['long_probability'])
    signals['bb_long'] = bb_long_entry.astype(int)
    
    # 볼린저 밴드 숏 신호
    bb_short_condition = df['close'] >= df['bb_upper']
    bb_short_entry = bb_short_condition & (np.random.random(len(df)) < df['short_probability'])
    signals['bb_short'] = bb_short_entry.astype(int)
    
    return signals

def get_signal(df: pd.DataFrame, params: dict) -> Optional[str]:
    """기존 매매 신호 생성 (호환성 유지)"""
    if df.empty:
        return None
    
    # 최신 데이터
    latest = df.iloc[-1]
    
    # 상승 신호 조건
    up_signal = (
        latest['pct'] >= params['up_pct'] and
        latest['close_to_range'] >= params['up_ctr'] and
        latest['vol_ratio'] >= params['up_vol']
    )
    
    # 하락 신호 조건
    down_signal = (
        latest['pct'] <= -params['down_pct'] and
        latest['close_to_range'] <= (1 - params['down_ctr']) and
        latest['vol_ratio'] >= params['down_vol']
    )
    
    if up_signal:
        return 'long'
    elif down_signal:
        return 'short'
    else:
        return None

def check_atr_stop(df: pd.DataFrame, atr_mult: float, highest_price: float) -> Tuple[bool, float, float]:
    """ATR 트레일링 스탑 조건 확인"""
    if df.empty:
        return False, 0.0, highest_price
    
    latest = df.iloc[-1]
    today_high = float(latest['high'])
    today_low = float(latest['low'])
    atr = float(latest['atr']) if not np.isnan(latest['atr']) else 0.0
    
    if atr <= 0:
        return False, 0.0, highest_price
    
    new_high = max(highest_price, today_high)
    stop_price = new_high - atr_mult * atr
    triggered = today_low <= stop_price
    
    return triggered, stop_price, new_high

def update_trade_result(ledger: dict, pnl: float) -> None:
    """거래 결과 추적"""
    try:
        if pnl > 0:
            ledger['last_trade_result'] = 'win'
            ledger['consecutive_wins'] = ledger.get('consecutive_wins', 0) + 1
            ledger['consecutive_losses'] = 0
        else:
            ledger['last_trade_result'] = 'loss'
            ledger['consecutive_losses'] = ledger.get('consecutive_losses', 0) + 1
            ledger['consecutive_wins'] = 0
    except Exception:
        pass

def get_position_multiplier(ledger: dict) -> float:
    """역방향 사이징을 위한 포지션 배수 계산"""
    try:
        last_result = ledger.get('last_trade_result')
        if last_result == 'win':
            return 0.5  # 승리 후 공격적
        elif last_result == 'loss':
            return 1.0  # 패배 후 보수적
        else:
            return 1.0  # 첫 거래 또는 결과 없음
    except Exception:
        return 1.0

def run_yearly_backtest(year: int, initial_capital: float = 10000, params: dict = None, verbose: bool = True):
    """특정 연도의 백테스팅 실행"""
    print(f"\n=== {year}년 백테스팅 ===")
    
    # 데이터 로드
    df = load_yearly_data(year, '1d')
    if df is None:
        print(f"{year}년 데이터를 찾을 수 없습니다.")
        return None
    
    # 지표 계산
    df = prepare_indicators(df)
    
    # 기본 파라미터 (원래 설정)
    if params is None:
        params = {
            'up_pct': 0.005,      # 0.5% 상승
            'up_ctr': 0.5,        # 상승 시 close_to_range 50% 이상
            'up_vol': 1.0,        # 거래량 1배 이상
            'down_pct': 0.01,     # 1% 하락
            'down_ctr': 0.6,      # 하락 시 close_to_range 40% 이하
            'down_vol': 0.7,      # 거래량 0.7배 이상
            'atr_mult': 2.5       # ATR 2.5배 트레일링 스탑
        }
    
    # 백테스트 설정
    allocation_rate = 1.00  # 100% 할당
    total_capital = initial_capital
    strategy_capital = total_capital * allocation_rate
    
    # 포지션 관리
    ledger = {
        "positions": {},
        "realized_profit": 0.0,
        "initial_allocation": strategy_capital,
        "last_trade_result": None,
        "consecutive_wins": 0,
        "consecutive_losses": 0
    }
    
    # 백테스트 실행
    trades = []
    daily_equity = []
    
    for i in range(20, len(df)):  # 20일 이후부터 시작 (지표 계산용)
        current_date = df.index[i]
        current_price = df.iloc[i]['close']
        
        # 현재 포지션 평가
        invested_value = 0.0
        for symbol, pos in ledger['positions'].items():
            qty = float(pos.get('qty', 0))
            if qty > 0:
                invested_value += qty * current_price
        
        # 일일 기록
        cash = max(0.0, strategy_capital - invested_value)
        equity = invested_value + cash
        daily_equity.append({
            'date': current_date,
            'equity': equity,
            'cash': cash,
            'invested_value': invested_value,
            'n_positions': sum(1 for p in ledger['positions'].values() if float(p.get('qty', 0)) > 0)
        })
        
        # 신호 생성 (과거 데이터 사용)
        signal_data = df.iloc[:i+1]
        signal = get_signal(signal_data, params)
        
        if signal in ['long', 'short']:
            # 포지션 크기 계산 (역방향 사이징 적용)
            position_multiplier = get_position_multiplier(ledger)
            target_value = strategy_capital * position_multiplier
            
            # 기존 포지션 정리
            for symbol in list(ledger['positions'].keys()):
                pos = ledger['positions'][symbol]
                qty = float(pos.get('qty', 0))
                if qty > 0:
                    # 매도 (수수료 반영) - 원래 계산 방식
                    gross_pnl = (current_price - float(pos.get('avg', 0))) * qty
                    sell_fee = current_price * qty * TRADING_FEE
                    net_pnl = gross_pnl - sell_fee
                    ledger['realized_profit'] += net_pnl
                    update_trade_result(ledger, net_pnl)
                    
                    trades.append({
                        'date': current_date,
                        'action': 'SELL',
                        'symbol': symbol,
                        'qty': qty,
                        'price': current_price,
                        'pnl': net_pnl,
                        'fee': sell_fee,
                        'side': pos.get('side', 'long')
                    })
                    
                    del ledger['positions'][symbol]
            
            # 새 포지션 진입 (수수료 반영)
            qty = target_value / current_price
            buy_fee = current_price * qty * TRADING_FEE
            # 수수료를 고려한 실제 투자금액
            actual_investment = target_value + buy_fee
            
            ledger['positions'][SYMBOL] = {
                'qty': qty,
                'avg': current_price,
                'hi': current_price,
                'side': signal,
                'entry_date': current_date,
                'buy_fee': buy_fee
            }
            
            trades.append({
                'date': current_date,
                'action': 'BUY',
                'symbol': SYMBOL,
                'qty': qty,
                'price': current_price,
                'pnl': None,
                'fee': buy_fee
            })
        
        # ATR 트레일링 스탑 체크
        for symbol, pos in list(ledger['positions'].items()):
            qty = float(pos.get('qty', 0))
            if qty > 0:
                highest_price = float(pos.get('hi', current_price))
                triggered, stop_price, new_hi = check_atr_stop(signal_data, params['atr_mult'], highest_price)
                
                pos['hi'] = new_hi
                
                if triggered:
                    # 트레일링 스탑 매도 (수수료 반영) - 원래 계산 방식
                    gross_pnl = (current_price - float(pos.get('avg', 0))) * qty
                    sell_fee = current_price * qty * TRADING_FEE
                    net_pnl = gross_pnl - sell_fee
                    ledger['realized_profit'] += net_pnl
                    update_trade_result(ledger, net_pnl)
                    
                    trades.append({
                        'date': current_date,
                        'action': 'SELL_TS',
                        'symbol': symbol,
                        'qty': qty,
                        'price': current_price,
                        'pnl': net_pnl,
                        'fee': sell_fee,
                        'side': pos.get('side', 'long')
                    })
                    
                    del ledger['positions'][symbol]
    
    # 결과 계산
    final_equity = daily_equity[-1]['equity'] if daily_equity else strategy_capital
    total_return = (final_equity - strategy_capital) / strategy_capital * 100
    
    # 거래 통계
    total_pnl = sum(t['pnl'] for t in trades if t['pnl'] is not None)
    total_fees = sum(t.get('fee', 0) for t in trades if 'fee' in t)
    win_trades = [t for t in trades if t['pnl'] is not None and t['pnl'] > 0]
    lose_trades = [t for t in trades if t['pnl'] is not None and t['pnl'] < 0]
    win_rate = len(win_trades) / (len(win_trades) + len(lose_trades)) * 100 if (len(win_trades) + len(lose_trades)) > 0 else 0
    
    avg_win = sum(t['pnl'] for t in win_trades) / len(win_trades) if win_trades else 0
    avg_loss = sum(t['pnl'] for t in lose_trades) / len(lose_trades) if lose_trades else 0
    
    # 롱/숏별 승률 계산
    long_trades = [t for t in trades if t.get('side') == 'long']
    short_trades = [t for t in trades if t.get('side') == 'short']
    
    long_win_rate = 0
    short_win_rate = 0
    long_avg_win = 0
    long_avg_loss = 0
    short_avg_win = 0
    short_avg_loss = 0
    
    if long_trades:
        long_wins = [t for t in long_trades if t.get('pnl', 0) > 0]
        long_losses = [t for t in long_trades if t.get('pnl', 0) < 0]
        long_win_rate = len(long_wins) / len(long_trades) * 100 if long_trades else 0
        long_avg_win = sum(t.get('pnl', 0) for t in long_wins) / len(long_wins) if long_wins else 0
        long_avg_loss = sum(t.get('pnl', 0) for t in long_losses) / len(long_losses) if long_losses else 0
        
    if short_trades:
        short_wins = [t for t in short_trades if t.get('pnl', 0) > 0]
        short_losses = [t for t in short_trades if t.get('pnl', 0) < 0]
        short_win_rate = len(short_wins) / len(short_trades) * 100 if short_trades else 0
        short_avg_win = sum(t.get('pnl', 0) for t in short_wins) / len(short_wins) if short_wins else 0
        short_avg_loss = sum(t.get('pnl', 0) for t in short_losses) / len(short_losses) if short_losses else 0
    
    # 결과 출력 (verbose가 True일 때만)
    if verbose:
        print(f"기간: {df.index[20]} ~ {df.index[-1]}")
        print(f"초기 자본: ${initial_capital:,.2f}")
        print(f"전략 자본: ${strategy_capital:,.2f}")
        print(f"최종 자본: ${final_equity:,.2f}")
        print(f"총 수익률: {total_return:+.2f}%")
        print(f"총 거래 수: {len(trades)}")
        print(f"총 손익: ${total_pnl:,.2f}")
        print(f"총 수수료: ${total_fees:,.2f}")
        print(f"승률: {win_rate:.1f}% ({len(win_trades)}/{len(win_trades) + len(lose_trades)})")
        if win_trades:
            print(f"평균 승리: ${avg_win:,.2f}")
        if lose_trades:
            print(f"평균 손실: ${avg_loss:,.2f}")
        
        # 롱/숏별 승률 출력
        print(f"\n=== 롱/숏별 분석 ===")
        print(f"롱 거래: {len(long_trades)}회, 승률: {long_win_rate:.1f}%")
        if long_trades:
            print(f"  평균 승리: ${long_avg_win:,.2f}, 평균 손실: ${long_avg_loss:,.2f}")
        print(f"숏 거래: {len(short_trades)}회, 승률: {short_win_rate:.1f}%")
        if short_trades:
            print(f"  평균 승리: ${short_avg_win:,.2f}, 평균 손실: ${short_avg_loss:,.2f}")
    
    return {
        'year': year,
        'start_date': df.index[50],
        'end_date': df.index[-1],
        'initial_capital': initial_capital,
        'strategy_capital': strategy_capital,
        'final_equity': final_equity,
        'total_return': total_return,
        'total_trades': len(trades),
        'total_pnl': total_pnl,
        'win_rate': win_rate,
        'win_trades': len(win_trades),
        'lose_trades': len(lose_trades),
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'trades': trades,
        'daily_equity': daily_equity,
        'ledger': ledger
    }

def grid_search_optimization(start_year: int = 2018, end_year: int = 2021, initial_capital: float = 10000):
    """파라미터 그리드 서치를 통한 최적화"""
    print("=== 파라미터 그리드 서치 최적화 ===")
    
    # 파라미터 그리드 정의 (더 공격적인 범위)
    param_grid = {
        'up_pct': [0.003, 0.005, 0.008, 0.01, 0.015, 0.02],  # 0.3%, 0.5%, 0.8%, 1.0%, 1.5%, 2.0%
        'up_ctr': [0.3, 0.4, 0.5, 0.6, 0.7],                # 30%, 40%, 50%, 60%, 70%
        'up_vol': [0.8, 1.0, 1.2, 1.5, 2.0],                # 0.8배, 1.0배, 1.2배, 1.5배, 2.0배
        'down_pct': [0.005, 0.008, 0.01, 0.015, 0.02, 0.025], # 0.5%, 0.8%, 1.0%, 1.5%, 2.0%, 2.5%
        'down_ctr': [0.3, 0.4, 0.5, 0.6, 0.7],              # 30%, 40%, 50%, 60%, 70%
        'down_vol': [0.6, 0.7, 0.8, 1.0, 1.2],              # 0.6배, 0.7배, 0.8배, 1.0배, 1.2배
        'atr_mult': [1.5, 2.0, 2.5, 3.0, 3.5]               # 1.5배, 2.0배, 2.5배, 3.0배, 3.5배
    }
    
    best_params = None
    best_score = -float('inf')
    best_result = None
    results = []
    
    total_combinations = 1
    for values in param_grid.values():
        total_combinations *= len(values)
    
    print(f"총 {total_combinations:,}개 조합을 테스트합니다...")
    
    combination_count = 0
    
    # 그리드 서치 실행
    for up_pct in param_grid['up_pct']:
        for up_ctr in param_grid['up_ctr']:
            for up_vol in param_grid['up_vol']:
                for down_pct in param_grid['down_pct']:
                    for down_ctr in param_grid['down_ctr']:
                        for down_vol in param_grid['down_vol']:
                            for atr_mult in param_grid['atr_mult']:
                                combination_count += 1
                                
                                params = {
                                    'up_pct': up_pct,
                                    'up_ctr': up_ctr,
                                    'up_vol': up_vol,
                                    'down_pct': down_pct,
                                    'down_ctr': down_ctr,
                                    'down_vol': down_vol,
                                    'atr_mult': atr_mult
                                }
                                
                                # 각 연도별 백테스팅 실행
                                year_results = []
                                total_return = 0
                                total_trades = 0
                                total_pnl = 0
                                win_rate = 0
                                
                                for year in range(start_year, end_year + 1):
                                    try:
                                        result = run_yearly_backtest(year, initial_capital, params, verbose=False)
                                        if result:
                                            year_results.append(result)
                                            total_return += result['total_return']
                                            total_trades += result['total_trades']
                                            total_pnl += result['total_pnl']
                                            win_rate += result['win_rate']
                                    except Exception as e:
                                        print(f"연도 {year} 오류: {e}")
                                        continue
                                
                                if year_results:
                                    avg_return = total_return / len(year_results)
                                    avg_win_rate = win_rate / len(year_results)
                                    
                                    # 점수 계산 (수익률 + 승률 + 거래수 가중치)
                                    score = avg_return + (avg_win_rate * 0.1) + (total_trades * 0.001)
                                    
                                    result_summary = {
                                        'params': params,
                                        'avg_return': avg_return,
                                        'avg_win_rate': avg_win_rate,
                                        'total_trades': total_trades,
                                        'total_pnl': total_pnl,
                                        'score': score,
                                        'year_results': year_results
                                    }
                                    
                                    results.append(result_summary)
                                    
                                    if score > best_score:
                                        best_score = score
                                        best_params = params
                                        best_result = result_summary
                                
                                if combination_count % 100 == 0:
                                    print(f"진행률: {combination_count:,}/{total_combinations:,} ({combination_count/total_combinations*100:.1f}%)")
    
    # 결과 정렬 (점수 기준)
    results.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"\n=== 최적화 완료 ===")
    print(f"테스트된 조합: {len(results):,}개")
    print(f"최고 점수: {best_score:.2f}")
    print(f"\n=== 최적 파라미터 ===")
    for key, value in best_params.items():
        print(f"{key}: {value}")
    
    print(f"\n=== 상위 10개 결과 ===")
    for i, result in enumerate(results[:10]):
        print(f"{i+1:2d}. 점수: {result['score']:6.2f} | "
              f"평균수익률: {result['avg_return']:6.2f}% | "
              f"평균승률: {result['avg_win_rate']:5.1f}% | "
              f"총거래수: {result['total_trades']:4d} | "
              f"총손익: ${result['total_pnl']:8,.0f}")
    
    # 결과를 CSV 파일로 저장
    save_optimization_results(results, best_params)
    
    return best_params, results

def save_optimization_results(results, best_params):
    """최적화 결과를 CSV 파일로 저장"""
    try:
        import csv
        from datetime import datetime
        
        # 결과 파일 경로
        results_file = "logs/optimization_results.csv"
        
        with open(results_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 헤더 작성
            writer.writerow([
                '순위', '점수', '평균수익률(%)', '평균승률(%)', '총거래수', '총손익($)',
                'up_pct', 'up_ctr', 'up_vol', 'down_pct', 'down_ctr', 'down_vol', 'atr_mult'
            ])
            
            # 결과 데이터 작성
            for i, result in enumerate(results):
                params = result['params']
                writer.writerow([
                    i + 1,
                    f"{result['score']:.2f}",
                    f"{result['avg_return']:.2f}",
                    f"{result['avg_win_rate']:.1f}",
                    result['total_trades'],
                    f"{result['total_pnl']:,.0f}",
                    params['up_pct'],
                    params['up_ctr'],
                    params['up_vol'],
                    params['down_pct'],
                    params['down_ctr'],
                    params['down_vol'],
                    params['atr_mult']
                ])
        
        print(f"\n최적화 결과가 저장되었습니다: {results_file}")
        
        # 최적 파라미터 별도 저장
        best_params_file = "logs/best_parameters.json"
        import json
        with open(best_params_file, 'w', encoding='utf-8') as f:
            json.dump(best_params, f, indent=2, ensure_ascii=False)
        
        print(f"최적 파라미터가 저장되었습니다: {best_params_file}")
        
    except Exception as e:
        print(f"결과 저장 실패: {e}")

def run_all_years_backtest(start_year: int = 2018, end_year: int = 2025, initial_capital: float = 10000, params: dict = None):
    """모든 연도에 대해 백테스팅 실행"""
    print("=== 비트코인 선물 5배 레버리지 전략 - 연도별 백테스팅 ===")
    
    # 파라미터 설정
    if params is None:
        # 기본 파라미터 (원래 설정)
        params = {
            'up_pct': 0.005,      # 0.5% 상승
            'up_ctr': 0.5,        # 상승 시 close_to_range 50% 이상
            'up_vol': 1.0,        # 거래량 1배 이상
            'down_pct': 0.01,     # 1% 하락
            'down_ctr': 0.6,      # 하락 시 close_to_range 40% 이하
            'down_vol': 0.7,      # 거래량 0.7배 이상
            'atr_mult': 2.5       # ATR 2.5배 트레일링 스탑
        }
    
    all_results = []
    
    for year in range(start_year, end_year + 1):
        result = run_yearly_backtest(year, initial_capital, params)
        if result:
            all_results.append(result)
    
    # 전체 결과 요약
    if all_results:
        print(f"\n=== 전체 결과 요약 ({start_year}-{end_year}) ===")
        
        total_years = len(all_results)
        profitable_years = sum(1 for r in all_results if r['total_return'] > 0)
        avg_return = sum(r['total_return'] for r in all_results) / total_years
        best_year = max(all_results, key=lambda x: x['total_return'])
        worst_year = min(all_results, key=lambda x: x['total_return'])
        
        total_trades = sum(r['total_trades'] for r in all_results)
        total_pnl = sum(r['total_pnl'] for r in all_results)
        avg_win_rate = sum(r['win_rate'] for r in all_results) / total_years
        
        print(f"총 연도: {total_years}년")
        print(f"수익 연도: {profitable_years}년 ({profitable_years/total_years*100:.1f}%)")
        print(f"평균 수익률: {avg_return:+.2f}%")
        print(f"최고 수익률: {best_year['year']}년 {best_year['total_return']:+.2f}%")
        print(f"최저 수익률: {worst_year['year']}년 {worst_year['total_return']:+.2f}%")
        print(f"총 거래 수: {total_trades}")
        print(f"총 손익: ${total_pnl:,.2f}")
        print(f"평균 승률: {avg_win_rate:.1f}%")
        
        # 연도별 상세 결과
        print(f"\n=== 연도별 상세 결과 ===")
        print(f"{'연도':<6} {'수익률':<8} {'거래수':<6} {'승률':<6} {'총손익':<10}")
        print("-" * 40)
        for result in all_results:
            print(f"{result['year']:<6} {result['total_return']:>+7.2f}% {result['total_trades']:<6} {result['win_rate']:>5.1f}% ${result['total_pnl']:>8,.0f}")
        
        # 결과를 CSV로 저장
        save_results_to_csv(all_results)
        
        return all_results
    else:
        print("백테스트 결과가 없습니다.")
        return []

def save_results_to_csv(results: list):
    """결과를 CSV 파일로 저장"""
    try:
        import csv
        header = [
            'year', 'start_date', 'end_date', 'initial_capital', 'strategy_capital',
            'final_equity', 'total_return', 'total_trades', 'total_pnl',
            'win_rate', 'win_trades', 'lose_trades', 'avg_win', 'avg_loss'
        ]
        
        with open(results_csv_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(header)
            for result in results:
                w.writerow([
                    result['year'],
                    result['start_date'].strftime('%Y-%m-%d'),
                    result['end_date'].strftime('%Y-%m-%d'),
                    result['initial_capital'],
                    result['strategy_capital'],
                    result['final_equity'],
                    result['total_return'],
                    result['total_trades'],
                    result['total_pnl'],
                    result['win_rate'],
                    result['win_trades'],
                    result['lose_trades'],
                    result['avg_win'],
                    result['avg_loss']
                ])
        
        print(f"\n결과가 저장되었습니다: {results_csv_path}")
        
    except Exception as e:
        logging.error(f"결과 저장 실패: {e}")

def run_12_strategies_backtest(year: int, initial_capital: float = 770):
    """12개 전략 백테스트 실행"""
    print(f"\n=== {year}년 12개 전략 백테스팅 ===")
    
    # 데이터 로드
    df = load_yearly_data(year, '1d')
    if df is None:
        return None
    
    # 지표 계산
    df = prepare_indicators(df)
    
    # 12개 전략 신호 계산
    print("12개 전략 신호 계산 중...")
    all_signals = calculate_all_signals(df, {})
    
    # 전략별 자본 배분 (균등 배분)
    strategy_capitals = {
        'momentum_long': initial_capital * 0.0833,
        'momentum_short': initial_capital * 0.0833,
        'scalping_long': initial_capital * 0.0833,
        'scalping_short': initial_capital * 0.0833,
        'macd_long': initial_capital * 0.0833,
        'macd_short': initial_capital * 0.0833,
        'moving_average_long': initial_capital * 0.0833,
        'moving_average_short': initial_capital * 0.0833,
        'trend_long': initial_capital * 0.0833,
        'trend_short': initial_capital * 0.0833,
        'bb_long': initial_capital * 0.0833,
        'bb_short': initial_capital * 0.0833
    }
    
    # 전략별 백테스트 실행
    results = {}
    total_final_capital = 0
    
    for strategy_name in strategy_capitals.keys():
        print(f"  {strategy_name} 전략 실행 중...")
        
        # 해당 전략의 신호 사용
        signals = all_signals[strategy_name]
        capital = strategy_capitals[strategy_name]
        trades = []
        position = 0
        entry_price = 0
        
        # 숏 전략 여부 확인
        is_short_strategy = strategy_name.endswith('_short')
        
        for i in range(20, len(df)):  # 20일 이후부터 시작
            current_price = df.iloc[i]['close']
            current_date = df.index[i]
            signal = signals.iloc[i] if i < len(signals) else 0
            
            if signal == 1 and position == 0:  # 진입
                # 레버리지 적용
                leveraged_value = capital * LEVERAGE
                fee = leveraged_value * TRADING_FEE
                net_value = leveraged_value - fee
                qty = net_value / current_price
                
                if is_short_strategy:
                    position = -qty  # 숏 포지션
                    action = 'SHORT_SELL'
                else:
                    position = qty   # 롱 포지션
                    action = 'BUY'
                
                entry_price = current_price
                capital = 0  # 모든 자본 사용
                
                trades.append({
                    'date': current_date,
                    'action': action,
                    'price': current_price,
                    'qty': abs(qty),
                    'fee': fee,
                    'side': 'short' if is_short_strategy else 'long'
                })
                
            elif signal == 0 and position != 0:  # 청산
                if is_short_strategy:
                    # 숏 포지션 청산
                    gross_value = abs(position) * current_price
                    fee = gross_value * TRADING_FEE
                    net_value = gross_value - fee
                    pnl = (entry_price - current_price) * abs(position)
                    capital = max(0, (leveraged_value / LEVERAGE) + pnl - fee)
                    action = 'SHORT_COVER'
                else:
                    # 롱 포지션 청산
                    gross_value = position * current_price
                    fee = gross_value * TRADING_FEE
                    net_value = gross_value - fee
                    pnl = (current_price - entry_price) * position
                    capital = max(0, (leveraged_value / LEVERAGE) + pnl - fee)
                    action = 'SELL'
                
                position = 0
                entry_price = 0
                
                trades.append({
                    'date': current_date,
                    'action': action,
                    'price': current_price,
                    'qty': abs(position),
                    'pnl': pnl,
                    'fee': fee,
                    'side': 'short' if is_short_strategy else 'long'
                })
        
        # 최종 포지션 청산
        if position != 0:
            final_price = df.iloc[-1]['close']
            final_date = df.index[-1]
            
            if is_short_strategy:
                gross_value = abs(position) * final_price
                fee = gross_value * TRADING_FEE
                pnl = (entry_price - final_price) * abs(position)
                capital = max(0, (leveraged_value / LEVERAGE) + pnl - fee)
                action = 'FINAL_SHORT_COVER'
            else:
                gross_value = position * final_price
                fee = gross_value * TRADING_FEE
                pnl = (final_price - entry_price) * position
                capital = max(0, (leveraged_value / LEVERAGE) + pnl - fee)
                action = 'FINAL_SELL'
            
            trades.append({
                'date': final_date,
                'action': action,
                'price': final_price,
                'qty': abs(position),
                'pnl': pnl,
                'fee': fee,
                'side': 'short' if is_short_strategy else 'long'
            })
        
        # 결과 계산
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        total_return = (capital - strategy_capitals[strategy_name]) / strategy_capitals[strategy_name] * 100
        
        results[strategy_name] = {
            'final_capital': capital,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': win_rate,
            'total_return': total_return,
            'trades': trades
        }
        
        total_final_capital += capital
    
    # 전체 결과 출력
    print(f"\n=== {year}년 12개 전략 결과 ===")
    print(f"초기 자본: ${initial_capital:,.2f}")
    print(f"최종 자본: ${total_final_capital:,.2f}")
    print(f"총 수익률: {((total_final_capital - initial_capital) / initial_capital * 100):.2f}%")
    
    # 전략별 성과 출력
    print(f"\n전략별 성과:")
    for strategy_name, result in results.items():
        print(f"{strategy_name:<20}: 수익률 {result['total_return']:6.2f}%, "
              f"승률 {result['win_rate']:5.1f}%, 거래 {result['total_trades']:3d}회")
    
    return results

def run_12_strategies_backtest(year: int, initial_capital: float = 770):
    """12개 전략 백테스팅 실행 (롱/숏 분리)"""
    print(f"\n=== {year}년 12개 전략 백테스팅 (롱/숏 분리형) ===")
    
    # 데이터 로드
    df = load_yearly_data(year, '1d')
    if df is None:
        return None
    
    # 지표 계산
    df = prepare_indicators(df)
    
    # 12개 전략 신호 계산
    print("12개 전략 신호 계산 중...")
    all_signals = calculate_all_signals(df, {})
    
    # 12개 전략 (롱/숏 분리)
    strategies = [
        'momentum_long', 'momentum_short',
        'scalping_long', 'scalping_short', 
        'macd_long', 'macd_short',
        'moving_average_long', 'moving_average_short',
        'trend_long', 'trend_short',
        'bb_long', 'bb_short'
    ]
    
    # 전략별 자본 배분 (균등 배분)
    strategy_capitals = {strategy: initial_capital * 0.0833 for strategy in strategies}  # 1/12
    
    # 전략별 백테스트 실행
    results = {}
    total_final_capital = 0
    
    for strategy_name in strategies:
        print(f"  {strategy_name} 전략 실행 중...")
        
        # 해당 전략의 신호 사용
        signals = all_signals[strategy_name]
        capital = strategy_capitals[strategy_name]
        trades = []
        position = 0
        entry_price = 0
        
        # 숏 전략 여부 확인
        is_short_strategy = strategy_name.endswith('_short')
        
        for i in range(20, len(df)):  # 20일 이후부터 시작
            current_price = df.iloc[i]['close']
            current_date = df.index[i]
            signal = signals.iloc[i] if i < len(signals) else 0
            
            if signal == 1 and position == 0:  # 진입
                # 레버리지 적용
                leveraged_value = capital * LEVERAGE
                fee = leveraged_value * TRADING_FEE
                net_value = leveraged_value - fee
                qty = net_value / current_price
                
                if is_short_strategy:
                    position = -qty  # 숏 포지션
                    action = 'SHORT_SELL'
                else:
                    position = qty   # 롱 포지션
                    action = 'BUY'
                
                entry_price = current_price
                capital = 0  # 모든 자본 사용
                
                trades.append({
                    'date': current_date,
                    'action': action,
                    'price': current_price,
                    'qty': abs(qty),
                    'fee': fee,
                    'side': 'short' if is_short_strategy else 'long'
                })
                
            elif signal == 0 and position != 0:  # 청산
                if is_short_strategy:
                    # 숏 포지션 청산
                    gross_value = abs(position) * current_price
                    fee = gross_value * TRADING_FEE
                    net_value = gross_value - fee
                    pnl = (entry_price - current_price) * abs(position)
                    capital = max(0, (leveraged_value / LEVERAGE) + pnl - fee)
                    action = 'SHORT_COVER'
                else:
                    # 롱 포지션 청산
                    gross_value = position * current_price
                    fee = gross_value * TRADING_FEE
                    net_value = gross_value - fee
                    pnl = (current_price - entry_price) * position
                    capital = max(0, (leveraged_value / LEVERAGE) + pnl - fee)
                    action = 'SELL'
                
                position = 0
                entry_price = 0
                
                trades.append({
                    'date': current_date,
                    'action': action,
                    'price': current_price,
                    'qty': abs(position),
                    'pnl': pnl,
                    'fee': fee,
                    'side': 'short' if is_short_strategy else 'long'
                })
        
        # 최종 포지션 청산
        if position != 0:
            final_price = df.iloc[-1]['close']
            final_date = df.index[-1]
            
            if is_short_strategy:
                gross_value = abs(position) * final_price
                fee = gross_value * TRADING_FEE
                pnl = (entry_price - final_price) * abs(position)
                capital = max(0, (leveraged_value / LEVERAGE) + pnl - fee)
                action = 'FINAL_SHORT_COVER'
            else:
                gross_value = position * final_price
                fee = gross_value * TRADING_FEE
                pnl = (final_price - entry_price) * position
                capital = max(0, (leveraged_value / LEVERAGE) + pnl - fee)
                action = 'FINAL_SELL'
            
            trades.append({
                'date': final_date,
                'action': action,
                'price': final_price,
                'qty': abs(position),
                'pnl': pnl,
                'fee': fee,
                'side': 'short' if is_short_strategy else 'long'
            })
        
        # 결과 계산
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        total_return = (capital - strategy_capitals[strategy_name]) / strategy_capitals[strategy_name] * 100
        
        results[strategy_name] = {
            'final_capital': capital,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': win_rate,
            'total_return': total_return,
            'trades': trades
        }
        
        total_final_capital += capital
    
    # 전체 결과 출력
    print(f"\n=== {year}년 12개 전략 결과 ===")
    print(f"초기 자본: ${initial_capital:,.2f}")
    print(f"최종 자본: ${total_final_capital:,.2f}")
    
    # 0으로 나누기 방지
    if initial_capital > 0:
        total_return = ((total_final_capital - initial_capital) / initial_capital * 100)
        print(f"총 수익률: {total_return:.2f}%")
    else:
        print(f"총 수익률: -100.00% (자본 소진)")
    
    # 전략별 성과 출력
    print(f"\n전략별 성과 (롱/숏 분리형):")
    for strategy_name, result in results.items():
        print(f"{strategy_name:<20}: 수익률 {result['total_return']:6.2f}%, "
              f"승률 {result['win_rate']:5.1f}%, 거래 {result['total_trades']:3d}회")
    
    return results

def main():
    """메인 실행 함수"""
    print("=== 비트코인 선물 5배 레버리지 12개 전략 백테스팅 (롱/숏 분리형) ===")
    
    # 12개 전략으로 2018-2021년 테스트
    all_results = {}
    total_initial = 770
    current_capital = 770
    
    for year in range(2018, 2022):
        if current_capital <= 0:
            print(f"\n{year}년: 자본이 소진되어 백테스팅을 중단합니다.")
            break
            
        results = run_12_strategies_backtest(year, current_capital)
        if results:
            all_results[year] = results
            year_final = sum(r['final_capital'] for r in results.values())
            current_capital = year_final
            print(f"\n{year}년 최종 자본: ${year_final:,.2f}")
            
            # 자본이 0이 되면 다음 연도로 넘어가지 않음
            if year_final <= 0:
                print(f"자본이 소진되어 백테스팅을 중단합니다.")
                break
    
    # 전체 결과
    if all_results:
        # 마지막 연도의 결과 사용
        last_year = max(all_results.keys())
        final_capital = sum(r['final_capital'] for r in all_results[last_year].values())
        total_return = (final_capital - total_initial) / total_initial * 100
        print(f"\n=== 전체 결과 ===")
        print(f"초기 자본: ${total_initial:,.2f}")
        print(f"최종 자본: ${final_capital:,.2f}")
        print(f"총 수익률: {total_return:.2f}%")
        years_count = last_year - 2018 + 1
        print(f"백테스팅 기간: 2018년 ~ {last_year}년 ({years_count}년)")
        print(f"연평균 수익률: {total_return/years_count:.2f}%")
        
        # 연도별 전략 성과 요약
        print(f"\n=== 연도별 전략 성과 요약 ===")
        strategy_names = ['momentum_long', 'momentum_short', 'scalping_long', 'scalping_short', 
                         'macd_long', 'macd_short', 'moving_average_long', 'moving_average_short',
                         'trend_long', 'trend_short', 'bb_long', 'bb_short']
        
        for strategy in strategy_names:
            print(f"\n{strategy} 전략:")
            for year in range(2018, 2022):
                if year in all_results and strategy in all_results[year]:
                    result = all_results[year][strategy]
                    print(f"  {year}년: 수익률 {result['total_return']:6.2f}%, "
                          f"승률 {result['win_rate']:5.1f}%, 거래 {result['total_trades']:3d}회")
    else:
        print("백테스팅 실행에 실패했습니다.")

if __name__ == '__main__':
    main()
