#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
비트코인 선물 3배 레버리지 전략
ETFStrength.py의 전략을 바이낸스 선물에 적용

1) 전략 개요
- 대상: BTCUSDT 선물 (3배 레버리지)
- 신호: ATR 기반 트레일링 스탑 + 모멘텀 신호
- 배분: 총자산의 20%를 전략 예산으로 사용
- 실행: 매일 스케줄 가능
- 주문: 시장가 주문 (선물 특성상)
- 레저: 포지션별 수량/평단/실현손익 분리 관리

2) 신호 생성
- 상승 신호: 가격 상승률 + 거래량 + ATR 조건
- 하락 신호: 가격 하락률 + 거래량 + ATR 조건
- ATR 트레일링 스탑으로 손절/익절

3) 파일
- btc_futures_config.json: 전략 전용 설정
- btc_futures_positions.json: 포지션 관리
- logs/btc_futures_trades.csv, logs/btc_futures_daily.csv: 거래/일일 로그
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

# 바이낸스 API 관련 모듈 (기존 코드 참조)
try:
    from kook.binance.myBinance import BinanceAPI
except ImportError:
    print("바이낸스 API 모듈을 찾을 수 없습니다. 기본 설정으로 진행합니다.")
    BinanceAPI = None

script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)

BOT_NAME = "BTCFutures"
PortfolioName = "[비트코인선물3배전략]"

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
positions_file_path = os.path.join(script_dir, f"{BOT_NAME}_positions.json")
trades_csv_path = os.path.join(logs_dir, f"{BOT_NAME}_trades.csv")
daily_csv_path = os.path.join(logs_dir, f"{BOT_NAME}_daily.csv")

# 전략 설정
SYMBOL = 'BTCUSDT'
LEVERAGE = 3.0  # 3배 레버리지

# ========================= 메모리 관리 유틸리티 =========================
def cleanup_memory():
    """메모리 정리 함수"""
    try:
        collected = gc.collect()
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        logging.info(f"메모리 정리 완료: {collected}개 객체 수집, 현재 사용량: {memory_mb:.2f} MB")
        return memory_mb
    except Exception as e:
        logging.warning(f"메모리 정리 중 오류: {e}")
        return 0

def load_positions():
    """포지션 데이터 로드"""
    if not os.path.exists(positions_file_path):
        return {
            "positions": {}, 
            "realized_profit": 0.0, 
            "initial_allocation": None, 
            "last_trade_result": None, 
            "consecutive_wins": 0, 
            "consecutive_losses": 0
        }
    try:
        with open(positions_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'last_trade_result' not in data:
                data['last_trade_result'] = None
            if 'consecutive_wins' not in data:
                data['consecutive_wins'] = 0
            if 'consecutive_losses' not in data:
                data['consecutive_losses'] = 0
            return data
    except Exception:
        return {
            "positions": {}, 
            "realized_profit": 0.0, 
            "initial_allocation": None, 
            "last_trade_result": None, 
            "consecutive_wins": 0, 
            "consecutive_losses": 0
        }

def save_positions(ledger: dict):
    """포지션 데이터 저장"""
    try:
        with open(positions_file_path, 'w', encoding='utf-8') as f:
            json.dump(ledger, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def record_trade(date_str: str, action: str, symbol: str, qty: float, price: float, pnl: float | None):
    """거래 기록 저장"""
    import csv
    header = ["date", "action", "symbol", "qty", "price", "pnl"]
    write_header = not os.path.exists(trades_csv_path)
    try:
        with open(trades_csv_path, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(header)
            w.writerow([date_str, action, symbol, round(qty, 6), round(price, 4), (None if pnl is None else round(pnl, 2))])
    except Exception:
        pass

def record_daily(date_str: str, equity: float, cash: float, invested_value: float, n_positions: int):
    """일일 기록 저장"""
    import csv
    header = ["date", "equity", "cash", "invested_value", "n_positions"]
    write_header = not os.path.exists(daily_csv_path)
    try:
        with open(daily_csv_path, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(header)
            w.writerow([date_str, round(equity, 2), round(cash, 2), round(invested_value, 2), n_positions])
    except Exception:
        pass

# ========================= 데이터 로딩 및 지표 계산 =========================
def load_btc_data(days: int = 400) -> Optional[pd.DataFrame]:
    """비트코인 1일 데이터 로드"""
    try:
        data_dir = os.path.join(script_dir, "data", "BTCUSDT", "1d")
        csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
        
        if not csv_files:
            logging.error("비트코인 1일 데이터 파일을 찾을 수 없습니다.")
            return None
        
        # 가장 최근 파일 로드
        latest_file = sorted(csv_files)[-1]
        filepath = os.path.join(data_dir, latest_file)
        
        df = pd.read_csv(filepath, index_col=0, parse_dates=True)
        df = df.tail(days)  # 최근 N일 데이터만 사용
        
        logging.info(f"비트코인 데이터 로드 완료: {len(df)}개 (기간: {df.index[0]} ~ {df.index[-1]})")
        return df
        
    except Exception as e:
        logging.error(f"비트코인 데이터 로드 실패: {e}")
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

def get_signal(df: pd.DataFrame, params: dict) -> Optional[str]:
    """매매 신호 생성"""
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

# ========================= 포지션 관리 =========================
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

# ========================= 텔레그램 리포트 =========================
def send_summary_report(portfolio_name: str, ledger: dict, current_allocation: float, initial_allocation: float):
    """요약 리포트 전송"""
    try:
        positions = ledger.get('positions', {})
        lines = []
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        win_cnt = 0
        lose_cnt = 0
        flat_cnt = 0
        invested_value_now = 0.0
        cost_basis = 0.0
        
        for symbol, pos in positions.items():
            qty = float(pos.get('qty', 0))
            if qty <= 0:
                continue
                
            avg = float(pos.get('avg', 0.0))
            # 현재 가격 조회 (실제 구현에서는 API 호출)
            cur = float(pos.get('current_price', avg))  # 임시로 평단가 사용
            now_val = qty * cur
            invested_value_now += now_val
            cost_basis += qty * avg
            pnl_abs = (cur - avg) * qty
            pnl_pct = ((cur / avg) - 1.0) * 100.0 if avg > 0 else 0.0
            
            icon = '🟢' if pnl_abs > 0 else ('🔴' if pnl_abs < 0 else '⚪')
            if pnl_abs > 0:
                win_cnt += 1
            elif pnl_abs < 0:
                lose_cnt += 1
            else:
                flat_cnt += 1
                
            lines.append(f"{icon} {symbol}({qty:.6f})\n   ${now_val:,.2f}({pnl_abs:+,.2f}:{pnl_pct:+.2f}%)")
        
        current_profit = invested_value_now - cost_basis
        current_profit_pct = (current_profit / cost_basis * 100.0) if cost_basis > 0 else 0.0
        realized = float(ledger.get('realized_profit', 0.0))
        
        header = [
            f"📊 {portfolio_name}",
            f"상세 수익 현황 ({ts})",
            "==================================",
        ]
        
        # 역방향 사이징 정보
        sizing_info = ""
        if ledger.get('last_trade_result'):
            multiplier = 1.2 if ledger['last_trade_result'] == 'win' else 0.8
            sizing_info = f"🎯 역방향사이징: {multiplier:.1f}배 ({'승리후공격적' if ledger['last_trade_result'] == 'win' else '패배후보수적'})"
        
        footer = [
            "==================================",
            f"💰 초기 분배금: ${initial_allocation:,.2f}",
            f"💰 현재 분배금: ${current_allocation:,.2f}",
            f"💰 총 투자금액: ${cost_basis:,.2f}",
            f"📈 현재 수익금: ${current_profit:,.2f}({current_profit_pct:+.2f}%)",
            f"📊 누적 판매 수익금: ${realized:,.2f}",
            f"📊 포지션 현황: 수익 {win_cnt}개, 손실 {lose_cnt}개, 손익없음 {flat_cnt}개",
        ]
        
        if sizing_info:
            footer.append(sizing_info)
            
        msg = "\n".join(header + lines + footer)
        print(msg)  # 텔레그램 대신 콘솔 출력
        
    except Exception as e:
        logging.error(f"요약 리포트 생성 실패: {e}")

# ========================= 백테스팅 함수 =========================
def run_backtest(start_date: str = None, end_date: str = None, initial_capital: float = 10000):
    """백테스팅 실행"""
    print("=== 비트코인 선물 3배 레버리지 전략 백테스팅 ===")
    
    # 데이터 로드
    df = load_btc_data(400)
    if df is None:
        print("데이터 로드를 실패했습니다.")
        return
    
    # 지표 계산
    df = prepare_indicators(df)
    
    # 백테스트 파라미터 (ETFStrength.py의 베스트 파라미터 기반)
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
    allocation_rate = 0.20  # 20% 할당
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
                    # 매도
                    pnl = (current_price - float(pos.get('avg', 0))) * qty
                    ledger['realized_profit'] += pnl
                    update_trade_result(ledger, pnl)
                    
                    trades.append({
                        'date': current_date,
                        'action': 'SELL',
                        'symbol': symbol,
                        'qty': qty,
                        'price': current_price,
                        'pnl': pnl
                    })
                    
                    del ledger['positions'][symbol]
            
            # 새 포지션 진입
            qty = target_value / current_price
            ledger['positions'][SYMBOL] = {
                'qty': qty,
                'avg': current_price,
                'hi': current_price,
                'side': signal,
                'entry_date': current_date
            }
            
            trades.append({
                'date': current_date,
                'action': 'BUY',
                'symbol': SYMBOL,
                'qty': qty,
                'price': current_price,
                'pnl': None
            })
        
        # ATR 트레일링 스탑 체크
        for symbol, pos in list(ledger['positions'].items()):
            qty = float(pos.get('qty', 0))
            if qty > 0:
                highest_price = float(pos.get('hi', current_price))
                triggered, stop_price, new_hi = check_atr_stop(signal_data, params['atr_mult'], highest_price)
                
                pos['hi'] = new_hi
                
                if triggered:
                    # 트레일링 스탑 매도
                    pnl = (current_price - float(pos.get('avg', 0))) * qty
                    ledger['realized_profit'] += pnl
                    update_trade_result(ledger, pnl)
                    
                    trades.append({
                        'date': current_date,
                        'action': 'SELL_TS',
                        'symbol': symbol,
                        'qty': qty,
                        'price': current_price,
                        'pnl': pnl
                    })
                    
                    del ledger['positions'][symbol]
    
    # 결과 출력
    print(f"\n=== 백테스트 결과 ===")
    print(f"기간: {df.index[20]} ~ {df.index[-1]}")
    print(f"초기 자본: ${initial_capital:,.2f}")
    print(f"전략 자본: ${strategy_capital:,.2f}")
    print(f"총 거래 수: {len(trades)}")
    
    if trades:
        total_pnl = sum(t['pnl'] for t in trades if t['pnl'] is not None)
        win_trades = [t for t in trades if t['pnl'] is not None and t['pnl'] > 0]
        lose_trades = [t for t in trades if t['pnl'] is not None and t['pnl'] < 0]
        
        print(f"총 손익: ${total_pnl:,.2f}")
        print(f"승률: {len(win_trades)}/{len(win_trades) + len(lose_trades)} ({len(win_trades)/(len(win_trades) + len(lose_trades))*100:.1f}%)")
        
        if win_trades:
            avg_win = sum(t['pnl'] for t in win_trades) / len(win_trades)
            print(f"평균 승리: ${avg_win:,.2f}")
        
        if lose_trades:
            avg_loss = sum(t['pnl'] for t in lose_trades) / len(lose_trades)
            print(f"평균 손실: ${avg_loss:,.2f}")
    
    # 최종 포지션 상태
    final_equity = daily_equity[-1]['equity'] if daily_equity else strategy_capital
    total_return = (final_equity - strategy_capital) / strategy_capital * 100
    print(f"최종 자본: ${final_equity:,.2f}")
    print(f"총 수익률: {total_return:+.2f}%")
    
    # 요약 리포트
    send_summary_report(PortfolioName, ledger, strategy_capital, strategy_capital)
    
    return {
        'trades': trades,
        'daily_equity': daily_equity,
        'final_equity': final_equity,
        'total_return': total_return,
        'ledger': ledger
    }

def main():
    """메인 실행 함수"""
    print("=== 비트코인 선물 3배 레버리지 전략 ===")
    
    # 백테스트 실행
    result = run_backtest(initial_capital=10000)
    
    if result:
        print("\n백테스트가 완료되었습니다.")
    else:
        print("백테스트 실행에 실패했습니다.")

if __name__ == '__main__':
    main()
