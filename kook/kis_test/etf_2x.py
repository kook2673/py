"""
ETF 강도(상승/하락) 기반 매매 전략 - MA 제거 버전

개요:
- MA 없이 일중 강도와 거래량만으로 시그널 생성
- 강하게 오르면 레버리지 매수, 강하게 내리면 인버스 매수(방향성 일치)
- 트레일링 스탑(퍼센트 또는 ATR)로 리스크 관리, EOD 체결 가정

대상:
- KOSPI 계열: 122630(레버리지), 252670(인버스2X)
- KOSDAQ 계열: 233740(코스닥레버리지), 251340(코스닥인버스)

특징 지표(EOD 근사):
- pct = 종가 수익률, vol_ratio = 거래량/20일 평균, close_to_range = (종가-저가)/(고가-저가)
- 강상승: pct>=up_pct & close_to_range>=up_ctr & vol_ratio>=up_vol
- 강하락: pct<=-down_pct & close_to_range<=(1-down_ctr) & vol_ratio>=down_vol
"""

# -*- coding: utf-8 -*-

import os
import io
import sys
import glob
import logging
import pandas as pd
import numpy as np
from tqdm import tqdm
import talib

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, 'etf_strength_strategy.log')

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file_path, mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data', 'etf_index')

ASSETS = {
    'KOSPI': {'long': '122630', 'short': '252670'},
    'KOSDAQ': {'long': '233740', 'short': '251340'},
}


def load_etf(code: str) -> pd.DataFrame:
    paths = glob.glob(os.path.join(DATA_DIR, f"{code}_*.csv"))
    if not paths:
        logging.error(f"ETF 데이터 파일을 찾을 수 없습니다: {code}")
        return pd.DataFrame()
    df = pd.read_csv(paths[0], parse_dates=['date'])
    df.columns = [c.lower() for c in df.columns]
    return df.set_index('date').sort_index()


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out['pct'] = out['close'].pct_change()
    rng = (out['high'] - out['low']).replace(0, np.nan)
    out['close_to_range'] = ((out['close'] - out['low']) / rng).clip(0, 1)
    out['vol_ma20'] = out['volume'].rolling(20).mean()
    out['vol_ratio'] = out['volume'] / out['vol_ma20']
    out['atr'] = talib.ATR(out['high'], out['low'], out['close'], timeperiod=14)
    return out


def backtest_etf_strength(
    market: str = 'KOSPI',
    start: str = '2018-01-01',
    end: str = '2025-09-01',
    up_pct: float = 0.03,            # +3% 이상
    up_ctr: float = 0.7,             # 상단 근접도 0.7 이상
    up_vol: float = 2.0,             # 거래량 배수 2배 이상
    down_pct: float = 0.03,          # -3% 이상 하락
    down_ctr: float = 0.7,           # 하단 근접 기준(1-down_ctr 이하)
    down_vol: float = 2.0,
    entry_at_open: bool = True,      # 시그널 다음날 시가 진입
    entry_same_day: bool = False,    # 시그널 당일 종가 진입
    use_trailing_atr: bool = True,   # ATR 트레일링
    atr_mult: float = 3.0,
    use_trailing_pct: bool = False,  # 퍼센트 트레일링
    trail_pct: float = 0.05,         # 5%
    fee_bps: float = 1.5,
    slippage_bps: float = 5.0,
    capital: float = 100_000_000,
    position_fraction: float = 1.0,  # 자본 중 투자 비율
    dynamic_sizing: bool = False,    # 동적 포지션 사이징
    win_multiplier: float = 1.0,     # 승리시 포지션 배수 (공격적)
    loss_multiplier: float = 0.5,    # 패배시 포지션 배수 (보수적)
):
    codes = ASSETS.get(market.upper())
    if not codes:
        raise ValueError('market은 KOSPI 또는 KOSDAQ이어야 합니다.')

    df_long = prepare(load_etf(codes['long']))
    df_short = prepare(load_etf(codes['short']))
    if df_long.empty or df_short.empty:
        logging.error('필수 ETF 데이터가 없습니다. data_downloader로 먼저 다운로드하세요.')
        return pd.Series(dtype=float), pd.DataFrame()

    dates = df_long.index.intersection(df_short.index)
    dates = dates[(dates >= pd.to_datetime(start)) & (dates <= pd.to_datetime(end))]

    cash = capital
    equity = pd.Series(index=dates, dtype=float)
    pos = None  # {'side': 'long'|'short', 'qty':int, 'avg':float, 'hi':float}
    trades = []
    
    # 동적 포지션 사이징을 위한 변수들
    last_trade_result = None  # 마지막 거래 결과 ('win' or 'loss')
    consecutive_wins = 0      # 연속 승리 횟수
    consecutive_losses = 0    # 연속 패배 횟수

    for date in tqdm(dates, desc=f"ETF Strength {market}"):
        L = df_long.loc[date]
        S = df_short.loc[date]

        # 평가
        mark = 0.0
        if pos is None:
            equity.loc[date] = cash
        else:
            px = (L['close'] if pos['side'] == 'long' else S['close'])
            equity.loc[date] = cash + pos['qty'] * px

        # 트레일링 청산
        if pos is not None:
            cur_df = (df_long if pos['side'] == 'long' else df_short)
            row = cur_df.loc[date]
            sell = False
            sell_px = row['open'] if entry_at_open else row['close']
            if pd.isna(sell_px) or sell_px <= 0:
                sell_px = row['close']
            if use_trailing_atr and pd.notna(row['atr']) and row['atr'] > 0:
                pos['hi'] = max(pos['hi'], row['high'])
                stop = pos['hi'] - atr_mult * row['atr']
                if row['low'] <= stop:
                    sell = True
                    sell_px = stop
            if use_trailing_pct:
                pos['hi'] = max(pos['hi'], row['high'])
                stop = pos['hi'] * (1 - trail_pct)
                if row['low'] <= stop:
                    sell = True
                    sell_px = stop
            if sell:
                sell_px *= (1 - slippage_bps/10000.0)
                pnl = (sell_px - pos['avg']) * pos['qty']
                cash += pos['qty'] * sell_px * (1 - fee_bps/10000.0)
                
                # 거래 결과 추적 (동적 포지션 사이징용)
                if dynamic_sizing:
                    if pnl > 0:
                        last_trade_result = 'win'
                        consecutive_wins += 1
                        consecutive_losses = 0
                    else:
                        last_trade_result = 'loss'
                        consecutive_losses += 1
                        consecutive_wins = 0
                
                trades.append({'date': date, 'side': 'SELL', 'ticker': codes[pos['side']], 'price': sell_px, 'qty': pos['qty'], 'pnl': pnl})
                pos = None
                equity.loc[date] = cash
                continue

        # 진입 신호
        if pos is None:
            up_signal = (L['pct'] >= up_pct) and (L['close_to_range'] >= up_ctr) and (L['vol_ratio'] >= up_vol)
            down_signal = (L['pct'] <= -down_pct) and (L['close_to_range'] <= (1 - down_ctr)) and (L['vol_ratio'] >= down_vol)

            enter_side = None
            if up_signal:
                enter_side = 'long'
            elif down_signal:
                enter_side = 'short'

            if enter_side is not None:
                # 동적 포지션 사이징 계산
                current_multiplier = 1.0
                if dynamic_sizing and last_trade_result is not None:
                    if last_trade_result == 'win':
                        current_multiplier = win_multiplier
                    else:  # loss
                        current_multiplier = loss_multiplier
                
                if entry_same_day:
                    # 당일 종가 진입
                    cur_df = (df_long if enter_side == 'long' else df_short)
                    row = cur_df.loc[date]
                    buy_px = row['close'] if pd.notna(row['close']) and row['close'] > 0 else row['open']
                    if pd.notna(buy_px) and buy_px > 0:
                        buy_px *= (1 + slippage_bps/10000.0)
                        available_capital = equity.loc[date]
                        qty = int((available_capital * position_fraction * current_multiplier) // buy_px)
                        if qty > 0:
                            cash -= qty * buy_px * (1 + fee_bps/10000.0)
                            pos = {'side': enter_side, 'qty': qty, 'avg': buy_px, 'hi': buy_px}
                            trades.append({'date': date, 'side': 'BUY', 'ticker': codes[enter_side], 'price': buy_px, 'qty': qty, 'entry_mode': 'same_close'})
                        else:
                            pos = None
                    else:
                        pos = None
                else:
                    # 다음날 진입 대기 (동적 사이징 정보도 저장)
                    pos = {'pending': enter_side, 'pend_date': date, 'multiplier': current_multiplier}

        # 대기 체결
        if pos is not None and 'pending' in pos:
            side = pos['pending']
            cur_df = (df_long if side == 'long' else df_short)
            # 다음 거래일
            idx = cur_df.index.get_loc(date)
            if idx + 1 < len(cur_df.index):
                nxt = cur_df.index[idx + 1]
                if nxt in dates:
                    row = cur_df.loc[nxt]
                    buy_px = row['open'] if entry_at_open else row['close']
                    if pd.isna(buy_px) or buy_px <= 0:
                        buy_px = row['close']
                    buy_px *= (1 + slippage_bps/10000.0)
                    # 동적 포지션 사이징 적용 (시그널 발생일의 자산을 기준으로)
                    multiplier = pos.get('multiplier', 1.0)
                    available_capital = equity.loc[date]
                    qty = int((available_capital * position_fraction * multiplier) // buy_px)
                    if qty > 0:
                        cash -= qty * buy_px * (1 + fee_bps/10000.0)
                        pos = {'side': side, 'qty': qty, 'avg': buy_px, 'hi': buy_px}
                        trades.append({'date': nxt, 'side': 'BUY', 'ticker': codes[side], 'price': buy_px, 'qty': qty, 'entry_mode': ('next_open' if entry_at_open else 'next_close')})
                    else:
                        pos = None

    return equity.dropna(), pd.DataFrame(trades)


if __name__ == '__main__':
    def evaluate(eq: pd.Series, trades: pd.DataFrame):
        trn = (eq.iloc[-1] / eq.iloc[0] - 1) * 100 if not eq.empty and eq.iloc[0] > 0 else 0.0
        sells = trades[trades['side'] == 'SELL'] if not trades.empty else pd.DataFrame()
        win_rate = (sells['pnl'] > 0).mean() * 100 if not sells.empty else 0.0
        return trn, win_rate, len(sells)

    # 기본 단일 실행 결과
    for market in ['KOSPI', 'KOSDAQ']:
        # 시장별 기본값(그리드 상위 수익률 조합 적용)
        # if market == 'KOSPI':
        #     base = {
        #         'up_pct': 0.015, 'up_ctr': 0.5, 'up_vol': 1.0,
        #         'down_pct': 0.03, 'down_ctr': 0.4, 'down_vol': 1.5,  # 최고성적: down_ctr 0.4
        #         'atr_mult': 2.5,
        #         'entry_at_open': False,   # next_close 체결
        #         'entry_same_day': False,
        #     }
        # else:  # KOSDAQ
        #     base = {
        #         'up_pct': 0.01, 'up_ctr': 0.4, 'up_vol': 1.0,  # 최고성적: up_ctr 0.4
        #         'down_pct': 0.005, 'down_ctr': 0.7, 'down_vol': 1.5,  # 최고성적: down_pct 0.005
        #         'atr_mult': 2.5,
        #         'entry_at_open': False,   # next_close 체결
        #         'entry_same_day': False,
        #     }
        if market == 'KOSPI':
            base = {
                'up_pct': 0.005, 'up_ctr': 0.5, 'up_vol': 1.0,  # 그리드 최고 수익률 305.37%
                'down_pct': 0.01, 'down_ctr': 0.6, 'down_vol': 0.7,
                'atr_mult': 2.5,
                'entry_at_open': True,    # next_open 체결
                'entry_same_day': False,
            }
        else:  # KOSDAQ
            base = {
                'up_pct': 0.005, 'up_ctr': 0.5, 'up_vol': 1.0,  # 그리드 최고 수익률 334.1%
                'down_pct': 0.01, 'down_ctr': 0.7, 'down_vol': 0.8,
                'atr_mult': 2.0,
                'entry_at_open': True,    # next_open 체결
                'entry_same_day': False,
            }

        # 기본 전략
        eq, tr = backtest_etf_strength(
            market=market, start='2018-01-01', end='2025-09-01',
            up_pct=base['up_pct'], up_ctr=base['up_ctr'], up_vol=base['up_vol'],
            down_pct=base['down_pct'], down_ctr=base['down_ctr'], down_vol=base['down_vol'],
            entry_at_open=base['entry_at_open'], entry_same_day=base['entry_same_day'],
            use_trailing_atr=True, atr_mult=base['atr_mult'],
            use_trailing_pct=False, trail_pct=0.05,
            capital=100_000_000, position_fraction=1.0, slippage_bps=0.0,
        )
        
        # 동적 포지션 사이징 1 (승리시 100%, 패배시 80%)
        eq_dyn_1, tr_dyn_1 = backtest_etf_strength(
            market=market, start='2018-01-01', end='2025-09-01',
            up_pct=base['up_pct'], up_ctr=base['up_ctr'], up_vol=base['up_vol'],
            down_pct=base['down_pct'], down_ctr=base['down_ctr'], down_vol=base['down_vol'],
            entry_at_open=base['entry_at_open'], entry_same_day=base['entry_same_day'],
            use_trailing_atr=True, atr_mult=base['atr_mult'],
            use_trailing_pct=False, trail_pct=0.05,
            capital=100_000_000, position_fraction=1.0, slippage_bps=0.0,
            dynamic_sizing=True, win_multiplier=1.0, loss_multiplier=0.8,
        )
        
        # 동적 포지션 사이징 2 (승리시 100%, 패배시 50%)
        eq_dyn_2, tr_dyn_2 = backtest_etf_strength(
            market=market, start='2018-01-01', end='2025-09-01',
            up_pct=base['up_pct'], up_ctr=base['up_ctr'], up_vol=base['up_vol'],
            down_pct=base['down_pct'], down_ctr=base['down_ctr'], down_vol=base['down_vol'],
            entry_at_open=base['entry_at_open'], entry_same_day=base['entry_same_day'],
            use_trailing_atr=True, atr_mult=base['atr_mult'],
            use_trailing_pct=False, trail_pct=0.05,
            capital=100_000_000, position_fraction=1.0, slippage_bps=0.0,
            dynamic_sizing=True, win_multiplier=1.0, loss_multiplier=0.5,
        )

        if not eq.empty:
            trn, winr, ntr = evaluate(eq, tr)
            logging.info(f"[{market}] 기본 전략 - Total Return: {trn:.2f}%  WinRate: {winr:.2f}%  Trades: {ntr}")
            eq.to_csv(os.path.join(log_dir, f'etf_strength_equity_{market}.csv'), header=['equity'])
            tr.to_csv(os.path.join(log_dir, f'etf_strength_trades_{market}.csv'), index=False)
            
            # 사이징 1 결과
            if not eq_dyn_1.empty:
                trn_dyn, winr_dyn, ntr_dyn = evaluate(eq_dyn_1, tr_dyn_1)
                logging.info(f"[{market}] 사이징(100%/80%) - Total Return: {trn_dyn:.2f}%  WinRate: {winr_dyn:.2f}%  Trades: {ntr_dyn}")
                eq_dyn_1.to_csv(os.path.join(log_dir, f'etf_strength_equity_{market}_dyn_100_80.csv'), header=['equity'])
                tr_dyn_1.to_csv(os.path.join(log_dir, f'etf_strength_trades_{market}_dyn_100_80.csv'), index=False)
                
                # 성과 비교
                return_diff = trn_dyn - trn
                logging.info(f"[{market}] 사이징(100%/80%) 효과: 수익률 {return_diff:+.2f}%p 차이")

            # 사이징 2 결과
            if not eq_dyn_2.empty:
                trn_con, winr_con, ntr_con = evaluate(eq_dyn_2, tr_dyn_2)
                logging.info(f"[{market}] 사이징(100%/50%) - Total Return: {trn_con:.2f}%  WinRate: {winr_con:.2f}%  Trades: {ntr_con}")
                eq_dyn_2.to_csv(os.path.join(log_dir, f'etf_strength_equity_{market}_dyn_100_50.csv'), header=['equity'])
                tr_dyn_2.to_csv(os.path.join(log_dir, f'etf_strength_trades_{market}_dyn_100_50.csv'), index=False)
                
                # 성과 비교
                return_diff_con = trn_con - trn
                logging.info(f"[{market}] 사이징(100%/50%) 효과: 수익률 {return_diff_con:+.2f}%p 차이")
            
            logging.info(f"[{market}] Saved equity/trades CSV.")

    # 승률 향상을 위한 파라미터 그리드 탐색(작은 그리드)
    # 필터 강화: 상단 근접/거래량 강화, 하락 진입은 거래량 강화
    up_pcts = [0.005]  # 더 낮은 가격변동률
    up_ctrs = [0.5, 0.6]  # 더 낮은 close_to_range
    up_vols = [1.0]  # 더 낮은 거래량 조건
    down_pcts = [0.01, 0.015]  # 더 낮은 가격변동률
    down_ctrs = [0.6, 0.7, 0.8]  # 더 넓은 범위
    down_vols = [0.7, 0.8, 0.9]  # 더 낮은 거래량 조건
    atr_mults = [2.0, 2.5]
    entry_modes = [
        {'entry_same_day': False, 'entry_at_open': True, 'lab': 'next_open'},
        {'entry_same_day': False, 'entry_at_open': False, 'lab': 'next_close'},
        {'entry_same_day': True, 'entry_at_open': True, 'lab': 'same_close'},
    ]

    for market in ['KOSPI', 'KOSDAQ']:
        rows = []
        for up_pct in up_pcts:
            for up_ctr in up_ctrs:
                for up_vol in up_vols:
                    for down_pct in down_pcts:
                        for down_ctr in down_ctrs:
                            for down_vol in down_vols:
                                for atr_mult in atr_mults:
                                    for em in entry_modes:
                                        eq, tr = backtest_etf_strength(
                                        market=market, start='2018-01-01', end='2025-09-01',
                                        up_pct=up_pct, up_ctr=up_ctr, up_vol=up_vol,
                                        down_pct=down_pct, down_ctr=down_ctr, down_vol=down_vol,
                                        entry_at_open=em['entry_at_open'], entry_same_day=em['entry_same_day'],
                                        use_trailing_atr=True, atr_mult=atr_mult,
                                        use_trailing_pct=False, trail_pct=0.05,
                                        capital=100_000_000, position_fraction=1.0, slippage_bps=0.0,
                                        )
                                        trn, winr, ntr = evaluate(eq, tr)
                                        rows.append({
                                            'market': market,
                                            'entry_mode': em['lab'],
                                            'up_pct': up_pct,
                                            'up_ctr': up_ctr,
                                            'up_vol': up_vol,
                                            'down_pct': down_pct,
                                            'down_ctr': down_ctr,
                                            'down_vol': down_vol,
                                            'atr_mult': atr_mult,
                                            'WinRate(%)': winr,
                                            'Trades': ntr,
                                            'TotalReturn(%)': trn,
                                        })
        if rows:
            df = pd.DataFrame(rows)
            # 승률 기준 정렬 저장
            df_win = df.sort_values(by=['WinRate(%)', 'Trades'], ascending=[False, False])
            out_csv = os.path.join(log_dir, f'etf_strength_grid_{market}.csv')
            df_win.to_csv(out_csv, index=False)
            logging.info(f"[{market}] Grid saved (by WinRate): {out_csv}")

            # 수익률 기준 정렬 저장 및 퍼센트 리스트 로그 출력
            df_ret = df.sort_values(by=['TotalReturn(%)'], ascending=False)
            out_csv_ret = os.path.join(log_dir, f'etf_strength_grid_{market}_by_return.csv')
            df_ret.to_csv(out_csv_ret, index=False)
            returns_list = [round(x, 2) for x in df_ret['TotalReturn(%)'].tolist()]
            logging.info(f"[{market}] Returns (desc): {returns_list}")

