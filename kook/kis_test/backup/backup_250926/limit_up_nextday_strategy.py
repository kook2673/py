"""
상따(상한가 추격) 전략 - 백테스트

가정/개요:
- 전일 상한가를 기록한 종목을 다음날 시가(또는 종가)로 매수.
- 다음날(혹은 보유일 N) 매도, 또는 간단한 하락 지표(전일대비/단기 이동평균 하회 등)로 매도.
- EOD 데이터 기반. 체결은 T+1 시가/종가로 선택.

데이터 전제:
- 코스피/코스닥 전체 종목 CSV가 `data/kospi100`/`data/kosdaq100` 외 확장 필요. 파일명 규칙: {TICKER}_....csv, index=date, columns=[open, high, low, close, volume].

주의: 실제 상한가 판정은 거래소 규정/정지/VI 등 고려가 필요하나, 백테스트 간소화를 위해 전일 등락률이 +29% 이상으로 상한가 근사.
"""

# -*- coding: utf-8 -*-

import os
import io
import sys
import glob
import pandas as pd
import numpy as np
import logging
from tqdm import tqdm

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, 'limitup_strategy.log')

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file_path, mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)


def load_all_stocks(data_dir: str):
    patterns = [
        os.path.join(data_dir, 'kospi100', '*.csv'),
        os.path.join(data_dir, 'kosdaq100', '*.csv'),
    ]
    files = []
    for p in patterns:
        files.extend(glob.glob(p))
    if not files:
        logging.error('종목 CSV를 찾을 수 없습니다.')
        return {}

    universe = {}
    for f in files:
        try:
            ticker = os.path.basename(f).split('_')[0]
            df = pd.read_csv(f, index_col='date', parse_dates=True)
            df.columns = [c.lower() for c in df.columns]
            universe[ticker] = df
        except Exception as e:
            logging.warning(f'로드 실패: {f} - {e}')
    return universe


def backtest_limit_up_nextday(
    universe: dict,
    start: str,
    end: str,
    limit_up_thresh: float = 0.29, # 전일 대비 +29% 이상을 상한가 근사
    buy_at_open: bool = True,      # True: T+1 시가 체결, False: T+1 종가 체결
    buy_same_day: bool = False,    # True: 상따 당일 종가 체결
    sell_mode: str = 'fall',    # 'nextday' | 'fall' | 'hold_n'
    hold_days: int = 1,            # sell_mode=='hold_n'일 때 보유 일수
    fall_indicator: str = 'prevclose', # 'prevclose' | 'ma3'
    fee_bps: float = 1.5,          # 편의상 왕복이 아닌, 매수/매도 각각 1.5bps
    slippage_bps: float = 5.0,     # 체결 슬리피지 가정
    capital_per_trade: float = 5_000_000,
    same_day_exit_on_fall: bool = False, # 매수를 시가로 한 날, 종가 하락 신호면 당일 청산
    same_day_intraday_reversal: bool = False, # 매수 당일 고점 대비 되돌림으로 청산
    intraday_up_arm_pct: float = 0.005,      # 매수가 대비 +0.5% 상승 시 트레일링 무장
    intraday_trail_from_high_pct: float = 0.01, # 고점 대비 -1.0% 되돌림 시 청산
    # 상단 근접도/강도 기반 당일 후보 선별 (EOD 근사)
    near_limit_max_gap_pct: float = 0.03,   # 이론상 상한가까지 남은 거리 <= 3%p
    min_close_to_range: float = 0.7,        # 당일 종가가 일중 범위 상단에 가까운 정도(0~1)
    min_volume_ratio: float = 2.0,          # 거래량/20일 평균 거래량 배수
):
    # 공통 날짜 축
    any_df = next(iter(universe.values()))
    dates = any_df.index
    dates = dates[(dates >= pd.to_datetime(start)) & (dates <= pd.to_datetime(end))]

    trade_logs = []
    equity_curve = pd.Series(index=dates, dtype=float)
    cash = 100_000_000.0
    position = None  # {'ticker':..., 'buy_date':..., 'buy_price':..., 'qty':...}

    # 사전 계산: 각 종목의 전일 대비 수익률로 상한가 근사
    for ticker, df in universe.items():
        df['pct'] = df['close'].pct_change()
        df['prev_close'] = df['close'].shift(1)
        df['ma3'] = df['close'].rolling(3).mean()
        # 이론상 상한가(30%)와 상단 근접도, 종가의 일중 위치, 거래량 배수
        df['limit_price_th'] = df['prev_close'] * 1.30
        rng = (df['high'] - df['low']).replace(0, np.nan)
        df['close_to_range'] = ((df['close'] - df['low']) / rng).clip(0, 1)
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma20']

    for date in tqdm(dates, desc='LimitUp Backtest'):
        # 평가
        if position is not None:
            tdf = universe[position['ticker']]
            if date in tdf.index:
                equity_curve.loc[date] = cash + position['qty'] * tdf.loc[date, 'close']
            else:
                equity_curve.loc[date] = cash
        else:
            equity_curve.loc[date] = cash

        # 당일 매도 조건
        if position is not None:
            tdf = universe[position['ticker']]
            if date in tdf.index:
                sell = False
                # 안전한 매도 체결가 선택 (우선 open/close 중 유효가로)
                raw_sell = tdf.loc[date, 'open'] if buy_at_open else tdf.loc[date, 'close']
                if pd.isna(raw_sell) or raw_sell <= 0 or not np.isfinite(raw_sell):
                    alt = tdf.loc[date, 'close'] if buy_at_open else tdf.loc[date, 'open']
                    raw_sell = alt if (pd.notna(alt) and alt > 0 and np.isfinite(alt)) else np.nan
                if pd.isna(raw_sell) or raw_sell <= 0 or not np.isfinite(raw_sell):
                    # 당일 유효 체결가 없으면 매도 판단 보류
                    equity_curve.loc[date] = cash + position['qty'] * tdf.loc[date, 'close']
                    continue
                sell_price = raw_sell * (1 - slippage_bps/10000.0)

                # (옵션) 인트라데이 반전 청산: 매수 당일 고점 대비 되돌림 발생 시 당일 청산 (OHLC 근사)
                if same_day_intraday_reversal and position is not None and (date == position['buy_date']) and buy_at_open and not buy_same_day:
                    day_high = tdf.loc[date, 'high'] if date in tdf.index else np.nan
                    day_low = tdf.loc[date, 'low'] if date in tdf.index else np.nan
                    if pd.notna(day_high) and pd.notna(day_low) and day_high > 0 and day_low > 0:
                        armed = day_high >= position['buy_price'] * (1 + intraday_up_arm_pct)
                        if armed:
                            trail_stop = day_high * (1 - intraday_trail_from_high_pct)
                            if day_low <= trail_stop:
                                sell_price = trail_stop * (1 - slippage_bps/10000.0)
                                sell = True
                                sell_reason_intraday = True
                            else:
                                sell_reason_intraday = False
                        else:
                            sell_reason_intraday = False
                    else:
                        sell_reason_intraday = False
                else:
                    sell_reason_intraday = False

                if sell_mode == 'nextday':
                    if (date - position['buy_date']).days >= 1:
                        sell = True
                elif sell_mode == 'hold_n':
                    if (date - position['buy_date']).days >= hold_days:
                        sell = True
                elif sell_mode == 'fall':
                    if fall_indicator == 'prevclose' and tdf.loc[date, 'close'] < tdf.loc[date, 'prev_close']:
                        sell = True
                    elif fall_indicator == 'ma3' and tdf.loc[date, 'close'] < tdf.loc[date, 'ma3']:
                        sell = True

                if sell:
                    qty = position['qty']
                    pnl = (sell_price - position['buy_price']) * qty
                    cash += qty * sell_price * (1 - fee_bps/10000.0)
                    trade_logs.append({
                        'date': date, 'side': 'SELL', 'ticker': position['ticker'],
                        'price': sell_price, 'qty': qty, 'pnl': pnl,
                        'reason': ('intraday_reversal' if sell_reason_intraday else sell_mode)
                    })
                    position = None

        # 당일 매수: 전일 상한가 근사 종목을 오늘 체결
        # 포지션 하나만 운영(간단화). 확장 시 동시 다수 보유로 수정 가능
        if position is None:
            candidates = []
            for ticker, df in universe.items():
                if date not in df.index:
                    continue
                if buy_same_day:
                    # 당일 상단 근접 & 강도 조건 (EOD 근사)
                    if pd.notna(df.loc[date, 'prev_close']) and pd.notna(df.loc[date, 'high']):
                        gap_pct = (df.loc[date, 'limit_price_th'] - df.loc[date, 'high']) / df.loc[date, 'prev_close']
                    else:
                        gap_pct = np.inf
                    ctr_ok = pd.notna(df.loc[date, 'close_to_range']) and df.loc[date, 'close_to_range'] >= min_close_to_range
                    vr_ok = pd.notna(df.loc[date, 'vol_ratio']) and df.loc[date, 'vol_ratio'] >= min_volume_ratio
                    near_ok = (gap_pct <= near_limit_max_gap_pct) if np.isfinite(gap_pct) else False
                    if near_ok and ctr_ok and vr_ok:
                        candidates.append(ticker)
                else:
                    prev_idx = df.index.get_loc(date)
                    prev_date = df.index[prev_idx - 1] if prev_idx > 0 else None
                    if prev_date is None:
                        continue
                    if pd.notna(df.loc[prev_date, 'pct']) and df.loc[prev_date, 'pct'] >= limit_up_thresh:
                        candidates.append(ticker)

            if candidates:
                # 간단히 가장 거래대금 큰 종목 선택
                best = None
                best_amount = -1
                for t in candidates:
                    df = universe[t]
                    amt = df.loc[date, 'close'] * df.loc[date, 'volume'] if date in df.index else 0
                    if amt > best_amount:
                        best = t
                        best_amount = amt

                if best is not None:
                    bdf = universe[best]
                    if date in bdf.index:
                        # 상따 당일 모드이면 종가로, 그 외에는 기존 규칙 적용
                        if buy_same_day:
                            raw_buy = bdf.loc[date, 'close']
                        else:
                            raw_buy = bdf.loc[date, 'open'] if buy_at_open else bdf.loc[date, 'close']
                        if pd.isna(raw_buy) or raw_buy <= 0 or not np.isfinite(raw_buy):
                            alt = bdf.loc[date, 'close'] if buy_at_open else bdf.loc[date, 'open']
                            raw_buy = alt if (pd.notna(alt) and alt > 0 and np.isfinite(alt)) else np.nan
                        if pd.isna(raw_buy) or raw_buy <= 0 or not np.isfinite(raw_buy):
                            # 유효한 체결가 없으면 매수 스킵
                            continue
                        buy_price = raw_buy * (1 + slippage_bps/10000.0)
                        if buy_price <= 0 or not np.isfinite(buy_price):
                            continue
                        qty = int(capital_per_trade // buy_price) if buy_price > 0 else 0
                        if qty > 0 and cash >= qty * buy_price * (1 + fee_bps/10000.0):
                            cash -= qty * buy_price * (1 + fee_bps/10000.0)
                            position = {
                                'ticker': best,
                                'buy_date': date,
                                'buy_price': buy_price,
                                'qty': qty,
                            }
                            trade_logs.append({'date': date, 'side': 'BUY', 'ticker': best, 'price': buy_price, 'qty': qty})

                            # (옵션) 같은 날 상태로 매도: 시가 매수(buy_at_open)이고 same_day_exit_on_fall이면
                            if same_day_exit_on_fall and not buy_same_day and buy_at_open:
                                # 종가 기반 하락 신호 체크
                                close_price = bdf.loc[date, 'close'] if date in bdf.index else np.nan
                                if pd.notna(close_price) and close_price > 0 and np.isfinite(close_price):
                                    fall = False
                                    if fall_indicator == 'prevclose' and close_price < bdf.loc[date, 'prev_close']:
                                        fall = True
                                    elif fall_indicator == 'ma3' and close_price < bdf.loc[date, 'ma3']:
                                        fall = True
                                    if fall:
                                        sell_price_same_day = close_price * (1 - slippage_bps/10000.0)
                                        pnl = (sell_price_same_day - position['buy_price']) * qty
                                        cash += qty * sell_price_same_day * (1 - fee_bps/10000.0)
                                        trade_logs.append({'date': date, 'side': 'SELL', 'ticker': best, 'price': sell_price_same_day, 'qty': qty, 'pnl': pnl, 'reason': 'same_day_fall'})
                                        position = None

    return equity_curve, pd.DataFrame(trade_logs)


if __name__ == '__main__':
    DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
    START = '2018-01-01'
    END = '2025-09-01'

    universe = load_all_stocks(DATA_DIR)
    if not universe:
        sys.exit(1)

    equity, trades = backtest_limit_up_nextday(
        universe,
        START,
        END,
        limit_up_thresh=0.29,
        buy_at_open=True,
        buy_same_day=True,
        sell_mode='fall',
        hold_days=1,
        fall_indicator='prevclose',
        fee_bps=1.5,
        slippage_bps=5.0,
        capital_per_trade=5_000_000,
        same_day_exit_on_fall=False,
        same_day_intraday_reversal=True,
        intraday_up_arm_pct=0.005,
        intraday_trail_from_high_pct=0.01,
    )

    # 간단 결과 출력
    if not equity.empty:
        total_return = (equity.iloc[-1] / equity.iloc[0] - 1) * 100 if equity.iloc[0] > 0 else 0
        logging.info(f"Total Return: {total_return:.2f}%  Trades: {len(trades)}")
        eq_path = os.path.join(log_dir, 'limitup_equity.csv')
        tr_path = os.path.join(log_dir, 'limitup_trades.csv')
        equity.to_csv(eq_path, header=['equity'])
        trades.to_csv(tr_path, index=False)
        logging.info(f"Saved: {eq_path}, {tr_path}")


