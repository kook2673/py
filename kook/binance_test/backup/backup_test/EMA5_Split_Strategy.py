# -*- coding: utf-8 -*-
"""
EMA 5개 + 구간 시분할(롱/숏) 전략 백테스트 (바이낸스 선물용)

- 신호:
  - 롱: EMA가 짧은 순서대로 위로 정렬 (ema[0] > ema[1] > ... > ema[4])
  - 숏: EMA가 짧은 순서대로 아래로 정렬 (ema[0] < ema[1] < ... < ema[4])
- 시분할:
  - 동일 신호가 유지되면 일정 바 간격(SPLIT_INTERVAL_BARS)마다 1트랜치씩 총 SPLIT_COUNT회 진입
  - 반대 신호 발생 시 해당 포지션 전량 청산 후 반대 방향으로 시분할 재개
- 선물 가정(단순화 모델):
  - 증거금 = 진입 명목가 / 레버리지, 진입/청산 시 수수료 차감
  - 현금(cash) = 가용 증거금 잔액, 포트폴리오 평가 = 현금 + 미실현손익
"""

import os
import re
import glob
import json
import math
import logging
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ========= 파라미터 =========
SYMBOLS = ["BTCUSDT"]
TIMEFRAME = "1m"         # '1m','3m','5m','15m','1h','4h','1d' 등 데이터 폴더에 맞춰 사용
EMA_PERIODS = [5, 10, 20, 60, 120]
SPLIT_COUNT = 5
SPLIT_INTERVAL_BARS = 60  # 동일 신호 유지 시 바 간격
INITIAL_CAPITAL = 10_000.0 # USDT
FEE_RATE = 0.0004          # 선물 테이커 수수료 가정(예시)
LEVERAGE = 5.0
MAX_EXPOSURE = 1.0         # 심볼당 목표 노출 상한(1.0 = 총자본 100% 노출)
BAR_LIMIT = 200_000        # 로드할 최대 바 수(메모리 보호용). 0이면 전체
RANDOM_SEED = 42
# 보호 로직
ATR_WINDOW = 14
ATR_SL_MULT = 2.0          # 손절: 2 * ATR
TP_MULT = 3.0              # 익절: 3 * ATR (포지션 방향 기준)
# ===========================

np.random.seed(RANDOM_SEED)

# ========= 로깅/출력 =========
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(SOURCE_DIR, "logs")
CHARTS_DIR = os.path.join(SOURCE_DIR, "charts")
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = os.path.join(LOGS_DIR, f"EMA5_Split_Strategy_{timestamp}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
)
# ===========================


def try_read_csv(path: str) -> pd.DataFrame | None:
    try:
        if not os.path.exists(path):
            return None
        # 다양한 포맷을 최대한 수용
        df = pd.read_csv(path)
        # 타임스탬프 컬럼 탐색
        dt_col = None
        for c in ["timestamp", "open_time", "openTime", "date", "time"]:
            if c in df.columns:
                dt_col = c
                break
        if dt_col is None:
            # 인덱스가 날짜인 경우 시도
            if df.index.name in ("timestamp", "date"):
                df.index = pd.to_datetime(df.index)
            else:
                # 실패
                return None
        else:
            df[dt_col] = pd.to_datetime(df[dt_col])
            df = df.set_index(dt_col)

        # 컬럼 표준화
        rename_map = {}
        for col in df.columns:
            lc = str(col).lower()
            if lc in ("open", "high", "low", "close", "volume"):
                rename_map[col] = lc
            elif lc in ("vol", "qty"):
                rename_map[col] = "volume"
        if rename_map:
            df = df.rename(columns=rename_map)

        need_cols = {"open", "high", "low", "close", "volume"}
        if not need_cols.issubset(set(map(str.lower, df.columns))):
            # 일부 파일은 대문자일 수 있으니 재시도
            up_map = {c: c.lower() for c in df.columns}
            df = df.rename(columns=up_map)
        if not need_cols.issubset(set(df.columns)):
            return None

        df = df[["open", "high", "low", "close", "volume"]].copy()
        df = df.sort_index()
        if BAR_LIMIT and BAR_LIMIT > 0 and len(df) > BAR_LIMIT:
            df = df.iloc[-BAR_LIMIT:]
        return df
    except Exception as e:
        logging.warning(f"CSV 읽기 실패: {path} | {e}")
        return None


def find_binance_data(symbol: str, timeframe: str) -> pd.DataFrame | None:
    # 후보 경로들 (존재하는 것부터 사용)
    candidates = [
        os.path.join(SOURCE_DIR, "data", symbol, timeframe, f"{symbol}_{timeframe}_ALL.csv"),
        os.path.join(SOURCE_DIR, "data", symbol, timeframe, f"{symbol}_{timeframe}.csv"),
        os.path.join(SOURCE_DIR, "data", symbol, f"{symbol}_{timeframe}.csv"),
        # 레거시(BTC_USDT 폴더 구조)
        os.path.join(SOURCE_DIR, "data", symbol.replace("USDT", "_USDT"), timeframe, f"{symbol}_{timeframe}.csv"),
        os.path.join(SOURCE_DIR, "data", symbol.replace("USDT", "_USDT"), timeframe, "2025-01.csv"),
    ]

    for p in candidates:
        df = try_read_csv(p)
        if df is not None:
            logging.info(f"데이터 로드: {p} | 바 수: {len(df):,}")
            return df

    # 마지막 시도: 글롭 검색
    pattern = os.path.join(SOURCE_DIR, "data", "**", symbol + "*" + timeframe + "*.csv")
    for p in glob.glob(pattern, recursive=True):
        df = try_read_csv(p)
        if df is not None:
            logging.info(f"데이터 로드: {p} | 바 수: {len(df):,}")
            return df

    logging.error(f"데이터 파일을 찾을 수 없습니다: {symbol} {timeframe}")
    return None


def compute_ema_signals(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    out = df.copy()
    for p in periods:
        out[f"ema_{p}"] = out["close"].ewm(span=p, adjust=False).mean()
    # ATR 계산 (손절/익절용)
    high = out['high']
    low = out['low']
    close = out['close']
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    out['atr'] = tr.ewm(span=ATR_WINDOW, adjust=False).mean()
    out["long_stack"] = 1
    out["short_stack"] = 1
    for i in range(len(periods) - 1):
        p1, p2 = periods[i], periods[i + 1]
        out["long_stack"] = out["long_stack"] & (out[f"ema_{p1}"] > out[f"ema_{p2}"])
        out["short_stack"] = out["short_stack"] & (out[f"ema_{p1}"] < out[f"ema_{p2}"])
    out["signal"] = 0
    out.loc[out["long_stack"] == 1, "signal"] = 1
    out.loc[out["short_stack"] == 1, "signal"] = -1
    return out


def align_data(data_map: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    dates = set()
    for df in data_map.values():
        dates.update(pd.to_datetime(df.index))
    dates = sorted(list(dates))
    return pd.DatetimeIndex(dates)


def get_name(code: str) -> str:
    return code


def backtest():
    cash = float(INITIAL_CAPITAL)  # 가용 증거금

    # 데이터 로드 및 신호 계산
    data_map: dict[str, pd.DataFrame] = {}
    for sym in SYMBOLS:
        df = find_binance_data(sym, TIMEFRAME)
        if df is None or len(df) == 0:
            logging.warning(f"{sym} 데이터 없음 → 제외")
            continue
        df = compute_ema_signals(df, EMA_PERIODS)
        df["name"] = get_name(sym)
        df.dropna(inplace=True)
        data_map[sym] = df

    if not data_map:
        logging.error("유효한 데이터가 없습니다.")
        return

    calendar = align_data(data_map)

    # 심볼 상태
    per_symbol = {}
    equal_weight = 1.0 / len(data_map)
    target_exposure_value = INITIAL_CAPITAL * MAX_EXPOSURE * equal_weight
    tranche_value = target_exposure_value / SPLIT_COUNT

    for sym in data_map.keys():
        per_symbol[sym] = {
            "side": 0,               # -1(short), 0(flat), 1(long)
            "qty": 0.0,              # 양수: 롱 수량, 음수: 숏 수량(절대값은 계약 수량)
            "avg_price": 0.0,        # 가중 평균 진입가
            "tranches": 0,           # 현재 방향으로 진입한 트랜치 수
            "last_entry_idx": None,  # 최근 진입 바 인덱스
            "used_margin": 0.0,      # 현재 포지션에 사용 중인 증거금 추정치
        }

    equity_curve = []

    for bar_idx, date in enumerate(calendar):
        prices_today = {}
        signals_today = {}

        for sym, df in data_map.items():
            if date not in df.index:
                continue
            row = df.loc[date]
            prices_today[sym] = float(row["close"])
            signals_today[sym] = int(row["signal"])

        # 진입/청산
        for sym, state in per_symbol.items():
            if sym not in prices_today:
                continue
            price = prices_today[sym]
            signal = signals_today.get(sym, 0)

            # 반대 신호 감지 → 전량 청산
            if state["side"] != 0 and np.sign(signal) != 0 and np.sign(signal) != state["side"]:
                if state["qty"] != 0.0:
                    close_qty = abs(state["qty"])  # 전량
                    # 실현 손익 계산
                    pnl = close_qty * (price - state["avg_price"]) * state["side"]
                    fee = abs(close_qty * price) * FEE_RATE
                    margin_release = (abs(close_qty) * state["avg_price"]) / LEVERAGE
                    cash += pnl + margin_release - fee
                    logging.info(f"{date} {sym} 전량 청산 qty={close_qty} @ {price:.2f} pnl={pnl:.2f} fee={fee:.2f}")
                # 상태 초기화
                state["side"] = 0
                state["qty"] = 0.0
                state["avg_price"] = 0.0
                state["tranches"] = 0
                state["last_entry_idx"] = None
                state["used_margin"] = 0.0

            # 동일 방향 신호 유지 → 시분할 진입
            if signal != 0:
                # FLAT → 첫 트랜치 진입
                if state["side"] == 0:
                    # 최소 수량(소수 수량 허용)
                    min_qty = 0.001 if "BTC" in sym else 0.01
                    raw_qty = tranche_value / price
                    # 거래 최소단위에 맞춰 내림
                    qty = math.floor(raw_qty / min_qty) * min_qty
                    if qty < min_qty:
                        qty = min_qty
                    notional = qty * price
                    fee = notional * FEE_RATE
                    need_margin = notional / LEVERAGE
                    if cash >= need_margin + fee:
                        cash -= (need_margin + fee)
                        state["side"] = signal
                        state["qty"] = qty if signal == 1 else -qty
                        state["avg_price"] = price
                        state["tranches"] = 1
                        state["last_entry_idx"] = bar_idx
                        state["used_margin"] += need_margin
                        logging.info(f"{date} {sym} {'롱' if signal==1 else '숏'} 1차 진입 qty={qty} @ {price:.2f} fee={fee:.2f}")
                else:
                    # 동일 방향 + 간격 충족 + 트랜치 여유
                    bars_ok = (
                        state["last_entry_idx"] is None
                        or (bar_idx - state["last_entry_idx"]) >= SPLIT_INTERVAL_BARS
                    )
                    if state["tranches"] < SPLIT_COUNT and bars_ok and state["side"] == signal:
                        min_qty = 0.001 if "BTC" in sym else 0.01
                        raw_qty = tranche_value / price
                        qty = math.floor(raw_qty / min_qty) * min_qty
                        if qty < min_qty:
                            qty = min_qty
                        notional = qty * price
                        fee = notional * FEE_RATE
                        need_margin = notional / LEVERAGE
                        if cash >= need_margin + fee:
                            cash -= (need_margin + fee)
                            # 평균 단가 갱신
                            cur_qty_abs = abs(state["qty"]) if state["qty"] != 0 else 0
                            new_qty_abs = cur_qty_abs + qty
                            state["avg_price"] = (
                                (state["avg_price"] * cur_qty_abs + qty * price) / new_qty_abs
                            ) if new_qty_abs > 0 else price
                            state["qty"] += qty if signal == 1 else -qty
                            state["tranches"] += 1
                            state["last_entry_idx"] = bar_idx
                            state["used_margin"] += need_margin
                            logging.info(f"{date} {sym} {'롱' if signal==1 else '숏'} 추가({state['tranches']}/{SPLIT_COUNT}) qty={qty} @ {price:.2f}")

        # ATR 기반 손절/익절 체크 (포지션 유지 중)
        for sym, state in per_symbol.items():
            if sym not in prices_today:
                continue
            if state["qty"] == 0.0:
                continue
            df = data_map[sym]
            if date not in df.index:
                continue
            row = df.loc[date]
            price = float(row['close'])
            atr = float(row.get('atr', np.nan))
            if not np.isfinite(atr) or atr <= 0:
                continue
            entry = state["avg_price"]
            side = 1 if state["qty"] > 0 else -1
            # 손절/익절 레벨
            if side == 1:
                stop = entry - ATR_SL_MULT * atr
                tp = entry + TP_MULT * atr
                hit_sl = price <= stop
                hit_tp = price >= tp
            else:
                stop = entry + ATR_SL_MULT * atr
                tp = entry - TP_MULT * atr
                hit_sl = price >= stop
                hit_tp = price <= tp

            if hit_sl or hit_tp:
                close_qty = abs(state["qty"])  # 전량 청산
                pnl = close_qty * (price - entry) * side
                fee = abs(close_qty * price) * FEE_RATE
                margin_release = (abs(close_qty) * entry) / LEVERAGE
                cash += pnl + margin_release - fee
                logging.info(f"{date} {sym} {'SL' if hit_sl else 'TP'} 청산 qty={close_qty} @ {price:.2f} pnl={pnl:.2f} fee={fee:.2f} atr={atr:.4f}")
                # 상태 초기화
                state["side"] = 0
                state["qty"] = 0.0
                state["avg_price"] = 0.0
                state["tranches"] = 0
                state["last_entry_idx"] = None
                state["used_margin"] = 0.0

        # 포트폴리오 평가 (미실현 손익 포함)
        equity = cash
        for sym, state in per_symbol.items():
            if sym in prices_today and state["qty"] != 0.0:
                price = prices_today[sym]
                qty_abs = abs(state["qty"])
                side = 1 if state["qty"] > 0 else -1
                unrealized = qty_abs * (price - state["avg_price"]) * side
                equity += unrealized
        equity_curve.append({"date": date, "equity": equity, "cash": cash})

    eq_df = pd.DataFrame(equity_curve).set_index("date")
    eq_df["ror"] = eq_df["equity"].pct_change().fillna(0) + 1
    eq_df["cum_ror"] = eq_df["ror"].cumprod()
    eq_df["hwm"] = eq_df["cum_ror"].cummax()
    eq_df["dd"] = eq_df["cum_ror"] / eq_df["hwm"] - 1.0
    eq_df["mdd"] = eq_df["dd"].cummin()

    initial = float(INITIAL_CAPITAL)
    final = float(eq_df["equity"].iloc[-1])
    revenue_rate = (eq_df["cum_ror"].iloc[-1] - 1.0) * 100.0
    mdd = float(eq_df["mdd"].min() * 100.0)

    logging.info(f"기간: {eq_df.index[0]} ~ {eq_df.index[-1]}")
    logging.info(f"초기자금: {initial:,.0f}, 최종자금: {final:,.0f}, 수익률: {revenue_rate:.2f}%, MDD: {mdd:.2f}%")

    results = {
        "strategy": "EMA5_Split_Futures",
        "timestamp": timestamp,
        "params": {
            "symbols": SYMBOLS,
            "timeframe": TIMEFRAME,
            "ema_periods": EMA_PERIODS,
            "split_count": SPLIT_COUNT,
            "split_interval_bars": SPLIT_INTERVAL_BARS,
            "fee_rate": FEE_RATE,
            "leverage": LEVERAGE,
            "max_exposure": MAX_EXPOSURE,
            "initial_capital": INITIAL_CAPITAL,
        },
        "summary": {
            "start": str(eq_df.index[0]),
            "end": str(eq_df.index[-1]),
            "initial": initial,
            "final": final,
            "revenue_rate_pct": round(revenue_rate, 2),
            "mdd_pct": round(mdd, 2),
        },
    }

    with open(os.path.join(LOGS_DIR, f"EMA5_Split_Strategy_{timestamp}.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    try:
        fig, axs = plt.subplots(2, 1, figsize=(12, 8))
        axs[0].plot(eq_df.index, eq_df["cum_ror"] * 100, label="Cumulative Return (%)")
        axs[0].set_title("Cumulative Return")
        axs[0].legend()
        axs[1].plot(eq_df.index, eq_df["mdd"] * 100, label="MDD (%)")
        axs[1].plot(eq_df.index, eq_df["dd"] * 100, label="Drawdown (%)", alpha=0.6)
        axs[1].set_title("Drawdown / MDD")
        axs[1].legend()
        plt.tight_layout()
        chart_path = os.path.join(CHARTS_DIR, f"EMA5_Split_Strategy_{timestamp}.png")
        plt.savefig(chart_path, dpi=200, bbox_inches="tight")
        plt.close()
        logging.info(f"차트 저장: {chart_path}")
    except Exception as e:
        logging.error(f"차트 저장 오류: {e}")

    print("\n=== 결과 요약 ===")
    print(f"기간: {results['summary']['start']} ~ {results['summary']['end']}")
    print(f"초기자금: {initial:,.0f} → 최종자금: {final:,.0f}")
    print(f"수익률: {results['summary']['revenue_rate_pct']:.2f}% | MDD: {results['summary']['mdd_pct']:.2f}%")
    print(f"로그: {log_path}")


if __name__ == "__main__":
    backtest()


