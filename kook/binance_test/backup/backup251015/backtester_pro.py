"""
ProBacktester: XGBoost 예측 신호 + ATR 기반 TP/SL/트레일링 스탑으로
BTCUSDT 4h 데이터 백테스트 수행.

실행 예시 (PowerShell):
  python -m kook.binance_test.backtester_pro --data-root kook/binance_test/data/BTCUSDT/4h \
    --model-dir models/BTCH4_xgb --start-year 2019 --end-year 2024
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

import numpy as np
import pandas as pd
from xgboost import XGBClassifier
import joblib


FEATURES_KEY = "features"


def read_csv_year(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    ts_col = "timestamp" if "timestamp" in df.columns else ("datetime" if "datetime" in df.columns else None)
    if ts_col is None:
        raise KeyError("timestamp/datetime column not found")
    df["timestamp"] = pd.to_datetime(df[ts_col])  # 4h
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def load_ohlcv_range(data_root: str, years: List[int]) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for y in years:
        f = os.path.join(data_root, f"BTCUSDT_4h_{y}.csv")
        if not os.path.exists(f):
            raise FileNotFoundError(f)
        frames.append(read_csv_year(f))
    return pd.concat(frames, axis=0, ignore_index=True)


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = np.where(delta > 0, delta, 0.0)
    down = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(up).rolling(period).mean()
    roll_down = pd.Series(down).rolling(period).mean()
    rs = roll_up / (roll_down + 1e-12)
    return 100 - (100 / (1 + rs))


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["close"]
    high = out["high"]
    low = out["low"]
    out["ret1"] = close.pct_change().fillna(0.0)
    out["ema_20"] = ema(close, 20)
    out["ema_50"] = ema(close, 50)
    out["ema_spread"] = out["ema_20"] - out["ema_50"]
    out["rsi_14"] = rsi(close, 14)
    tr1 = (high - low).abs()
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    out["tr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    out["atr_14"] = out["tr"].rolling(14).mean()
    return out


@dataclass
class Position:
    side: int  # 1=long, -1=short (본 예시는 long-only)
    entry: float
    size: float
    tp: float
    sl: float
    trail: Optional[float] = None


class ProBacktester:
    def __init__(self, model_dir: str, model_name: str = "xgb") -> None:
        self.model_dir = model_dir
        self.model_name = model_name.lower()
        self.model: Optional[object] = None
        self.scaler_stats = None
        self.feature_cols: List[str] = []
        self.idx_to_label: Optional[Dict[int, int]] = None

    def _load_artifacts_automatically(self) -> None:
        subdir = os.path.join(self.model_dir, self.model_name)
        # 모델 로드
        if self.model_name == "xgb":
            model = XGBClassifier()
            model.load_model(os.path.join(subdir, "model.json"))
            self.model = model
        else:
            self.model = joblib.load(os.path.join(subdir, "model.joblib"))
        # 스케일러/피처
        stats = np.load(os.path.join(subdir, "scaler.npy"), allow_pickle=True).item()
        self.scaler_stats = stats
        self.feature_cols = list(stats[FEATURES_KEY])
        # 레이블 매핑 메타데이터 (인코딩 복원)
        meta_path = os.path.join(subdir, "metadata.json")
        if os.path.exists(meta_path):
            import json
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            label_map = meta.get("label_map")
            if label_map is not None:
                self.idx_to_label = {i: int(v) for i, v in enumerate(label_map)}

    def _scale(self, X: np.ndarray) -> np.ndarray:
        mean = self.scaler_stats["mean"]
        scale = self.scaler_stats["scale"]
        return (X - mean) / (scale + 1e-12)

    def _predict_signals(self, df: pd.DataFrame) -> np.ndarray:
        X = df[self.feature_cols].astype(np.float32).values
        Xs = self._scale(X)
        preds = self.model.predict(Xs).astype(int)
        # 인코딩 복원: [0,1,2] -> [-1,0,1]
        if self.idx_to_label is not None:
            mapper = np.vectorize(lambda k: self.idx_to_label.get(int(k), int(k)))
            return mapper(preds).astype(int)
        return preds

    def run(self, df: pd.DataFrame, tp_k: float = 1.5, sl_k: float = 1.0, trail_k: float = 1.0,
            fee_rate: float = 0.0005,
            breakeven_atr: float = 1.0,
            time_exit_bars: int = 24,
            atr_regime_enabled: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame]:
        self._load_artifacts_automatically()
        equity = 1_000.0
        cash = equity
        pos: Optional[Position] = None
        records: List[Tuple[pd.Timestamp, str, float, float, float]] = []  # ts, event, price, pnl, fee
        equity_series: List[Tuple[pd.Timestamp, float]] = []

        # 벡터화 예측 후, 미래데이터 누수 방지: 신호를 한 캔들 시프트하여 다음 캔들 시가로 진입
        signals = self._predict_signals(df)
        signals_shifted = np.roll(signals, 1)
        signals_shifted[0] = 0

        # ATR 레짐 경계값 (저/중/고)
        if atr_regime_enabled:
            q_low, q_high = df["atr_14"].quantile([0.33, 0.66])
        else:
            q_low = q_high = None

        for i in range(1, len(df)):
            prev_row = df.iloc[i - 1]
            row = df.iloc[i]
            price_close = float(row["close"])  # 평가/청산 기준
            price_open = float(row["open"])   # 진입 가격
            atr_prev = float(prev_row["atr_14"])  # 리스크/TP/SL 산정은 과거 ATR로

            # 포지션 상태 업데이트(트레일링)
            if pos is not None:
                if pos.side == 1:
                    new_trail = price_close - trail_k * atr_prev
                    pos.trail = max(pos.trail or pos.sl, new_trail)
                    # 브레이크이븐: 진입가 + breakeven_atr*ATR 도달 시 SL을 진입가로 올림
                    if price_close >= pos.entry + breakeven_atr * atr_prev:
                        pos.sl = max(pos.sl, pos.entry)
                    # 손절/트레일/익절 체크 (종가 기준)
                    if price_close <= pos.trail or price_close <= pos.sl or price_close >= pos.tp:
                        exit_price = price_close if price_close >= pos.tp else price_close
                        pnl = (exit_price - pos.entry) * pos.size
                        sell_fee = exit_price * pos.size * fee_rate
                        cash += pnl - sell_fee
                        records.append((row["timestamp"], "EXIT", exit_price, pnl, sell_fee))
                        pos = None
                        bars_held = 0

            # 평가자산 기록
            equity = cash + (pos.size * (price_close - pos.entry) if pos is not None else 0.0)
            equity_series.append((row["timestamp"], float(equity)))

            # 시그널 예측 및 진입 (다음 캔들 시가 진입)
            signal = int(signals_shifted[i])
            if pos is None and signal == 1 and atr_prev > 0:
                risk_unit = cash * 0.02
                size = max(risk_unit / max(atr_prev, 1e-8), 0.0)
                entry = price_open
                # ATR 레짐별 SL 조정
                sl_k_eff = sl_k
                if atr_regime_enabled:
                    if atr_prev <= q_low:
                        sl_k_eff = sl_k * 0.8  # 저변동: 타이트
                    elif atr_prev >= q_high:
                        sl_k_eff = sl_k * 1.2  # 고변동: 넉넉
                tp = entry + tp_k * atr_prev
                sl = entry - sl_k_eff * atr_prev
                trail = entry - trail_k * atr_prev
                buy_fee = entry * size * fee_rate
                cash -= buy_fee
                pos = Position(side=1, entry=entry, size=size, tp=tp, sl=sl, trail=trail)
                records.append((row["timestamp"], "ENTRY", entry, 0.0, buy_fee))
                bars_held = 0

            # 시간 기반 청산
            if pos is not None:
                bars_held += 1
                if time_exit_bars > 0 and bars_held >= time_exit_bars:
                    exit_price = price_close
                    pnl = (exit_price - pos.entry) * pos.size
                    sell_fee = exit_price * pos.size * fee_rate
                    cash += pnl - sell_fee
                    records.append((row["timestamp"], "TIME_EXIT", exit_price, pnl, sell_fee))
                    pos = None
                    bars_held = 0

        pnl_total = cash - 1_000.0
        out = pd.DataFrame(records, columns=["timestamp", "event", "price", "pnl", "fee"])
        eq = pd.DataFrame(equity_series, columns=["timestamp", "equity"]) if equity_series else pd.DataFrame(columns=["timestamp", "equity"])
        out.attrs["pnl_total"] = pnl_total
        return out, eq


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--model", default="xgb", help="xgb|rf|gbc")
    ap.add_argument("--models", default="", help="콤마구분: xgb,rf,gbc (지정시 다중 실행)")
    ap.add_argument("--start-year", type=int, default=2019)
    ap.add_argument("--end-year", type=int, default=2024)
    ap.add_argument("--tp-k", type=float, default=1.5)
    ap.add_argument("--sl-k", type=float, default=1.0)
    ap.add_argument("--trail-k", type=float, default=1.0)
    ap.add_argument("--fee-rate", type=float, default=0.0005)
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--grid", action="store_true", help="2023 검증 구간에서 SL/TP/Trail/BE/TimeExit 그리드 탐색")
    ap.add_argument("--val-year", type=int, default=2023)
    args = ap.parse_args()

    years = list(range(args.start_year, args.end_year + 1))
    df = load_ohlcv_range(args.data_root, years)
    df = build_features(df).dropna().reset_index(drop=True)

    multi = [m.strip() for m in args.models.split(",") if m.strip()]

    # 그리드 서치 경로: val-year에서 최적 파라미터 찾고, 테스트 구간에서 재평가
    if args.grid and multi:
        import itertools
        # 검증 데이터
        df_val = load_ohlcv_range(args.data_root, [args.val_year])
        df_val = build_features(df_val).dropna().reset_index(drop=True)
        # 테스트 데이터(사용자 지정 기간)
        years = list(range(args.start_year, args.end_year + 1))
        df_test = load_ohlcv_range(args.data_root, years)
        df_test = build_features(df_test).dropna().reset_index(drop=True)

        # 경량 그리드
        sl_grid = [0.8, 1.0, 1.2]
        tp_grid = [1.3, 1.6]
        trail_grid = [0.8, 1.0]
        be_grid = [0.5, 1.0]
        time_grid = [0, 24]
        combos = list(itertools.product(sl_grid, tp_grid, trail_grid, be_grid, time_grid))

        best_params_by_model = {}
        for m in multi:
            best = None
            bt = ProBacktester(args.model_dir, m)
            for sl_k, tp_k, trail_k, be_atr, t_exit in combos:
                events, _ = bt.run(
                    df_val,
                    tp_k=tp_k,
                    sl_k=sl_k,
                    trail_k=trail_k,
                    fee_rate=args.fee_rate,
                    breakeven_atr=be_atr,
                    time_exit_bars=t_exit,
                    atr_regime_enabled=True,
                )
                score = events.attrs.get("pnl_total", 0.0)
                if (best is None) or (score > best[0]):
                    best = (score, {
                        "sl_k": sl_k,
                        "tp_k": tp_k,
                        "trail_k": trail_k,
                        "breakeven_atr": be_atr,
                        "time_exit_bars": t_exit,
                    })
            best_params_by_model[m] = best[1]

        # 테스트 데이터에서 최적 파라미터로 실행
        summaries = []
        for m in multi:
            p = best_params_by_model[m]
            bt = ProBacktester(args.model_dir, m)
            events, eq = bt.run(
                df_test,
                tp_k=p["tp_k"],
                sl_k=p["sl_k"],
                trail_k=p["trail_k"],
                fee_rate=args.fee_rate,
                breakeven_atr=p["breakeven_atr"],
                time_exit_bars=p["time_exit_bars"],
                atr_regime_enabled=True,
            )
            num_trades = int((events["event"] == "ENTRY").sum()) if not events.empty else 0
            summaries.append({
                "model": m,
                "pnl_total": events.attrs.get("pnl_total", 0.0),
                "trades": num_trades,
                "best_params": p,
            })

        for s in summaries:
            print(s)
        return
    if not multi:
        bt = ProBacktester(args.model_dir, args.model)
        events, equity_df = bt.run(df, tp_k=args.tp_k, sl_k=args.sl_k, trail_k=args.trail_k, fee_rate=args.fee_rate)
        num_trades = int((events["event"] == "ENTRY").sum()) if not events.empty else 0
        print(events.tail())
        print({
            "model": args.model,
            "trades": num_trades,
            "pnl_total": events.attrs.get("pnl_total", 0.0),
        })

        if args.plot:
            import matplotlib.pyplot as plt

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
            ax1.plot(df["timestamp"], df["close"], color="black", linewidth=1.0, label="BTCUSDT Close")
            ax1.set_ylabel("Price")
            ax1.legend(loc="upper left")

            if not equity_df.empty:
                ax2.plot(equity_df["timestamp"], equity_df["equity"], label=f"{args.model.upper()} Equity")
            ax2.set_ylabel("Equity")
            ax2.set_xlabel("Time")
            ax2.legend(loc="upper left")
            plt.tight_layout()
            plt.show()
        return

    # 다중 모델 실행
    summaries = []
    curves = []
    for m in multi:
        bt = ProBacktester(args.model_dir, m)
        events, eq = bt.run(df, tp_k=args.tp_k, sl_k=args.sl_k, trail_k=args.trail_k, fee_rate=args.fee_rate)
        num_trades = int((events["event"] == "ENTRY").sum()) if not events.empty else 0
        summaries.append({
            "model": m,
            "trades": num_trades,
            "pnl_total": events.attrs.get("pnl_total", 0.0),
        })
        curves.append((m, eq))

    # 요약 출력
    for s in summaries:
        print(s)

    if args.plot:
        import matplotlib.pyplot as plt
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        ax1.plot(df["timestamp"], df["close"], color="black", linewidth=1.0, label="BTCUSDT Close")
        ax1.set_ylabel("Price")
        ax1.legend(loc="upper left")
        for m, eq in curves:
            if not eq.empty:
                ax2.plot(eq["timestamp"], eq["equity"], label=f"{m.upper()} Equity")
        ax2.set_ylabel("Equity")
        ax2.set_xlabel("Time")
        ax2.legend(loc="upper left")
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()


