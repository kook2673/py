"""
KOSPI 드로우다운(1년 고점 대비 하락폭) 기반 122630(코덱스 레버리지) 분할매수 전략

1) 전략 개요
- 목적: KOSPI가 고점 대비 하락할수록 레버리지 ETF를 점차적으로 매수하여 평균단가를 낮추고, 지수 정상화/추세 회복 시 수익을 실현.
- 체결 가정: 장마감 직전(종가 근처) 체결. 슬리피지(bps)로 체결가 보정 가능.

2) 매수 규칙(디폴트 Ladder, 총 10유닛 = 100%)
- 기준 창: 1년(252 영업일) 고점의 전일값(high_1y)
- 드로우다운 dd = close / high_1y - 1.0 (전일 기준 고정)
- dd가 아래 임계에 도달할 때 해당 유닛 수를 매수(각 유닛 금액 = 총자본/10)
  - -15%: 1유닛
  - -20%: 1유닛
  - -25%: 2유닛
  - -30%: 4유닛
  - -35%: 2유닛
- 파라미터로 유닛 수와 임계(계단)를 자유롭게 조정 가능(ladder, unit_splits)

3) 매도 규칙(권장 베스트 설정)
- 정상가 회복 전량 매도(NormalizeExit): KOSPI 종가 >= high_1y × (1 + buffer)
- ATR 트레일링 스탑(ETF 기준): 최고가-ATR×배수 로 동적 손절가 상향 고정. 권장 배수 3.2x
- 권장 조합: NormalizeExit + ATR 3.2x + buffer 0.00% + DD 252
- 선택 옵션: 고정 TP(평균단가 대비), KOSPI 평균 모멘텀 청산, RSI 기반 익절(비권장/연구용)

4) 사용 지표 및 데이터
- KOSPI: 1년 고점(high_1y), 드로우다운(dd), (옵션) Average_Momentum(20~200일 10개 구간 전일 기준)
- ETF(122630): ATR(기본 20), RSI(기본 14)
- 데이터 파일: data/etf_index/KOSPI_*.csv, data/etf_index/122630_KODEX 레버리지.csv
- 거래일 교집합으로 동기화하여 사용(휴장 자동 스킵)

5) 실행 주기
- 하루 1회, 장마감 이후(EOD) 체크 권장. 예: 평일 15:40~16:10 KST 사이 실행.

6) 주요 파라미터 요약
- unit_splits: 총 유닛 수(기본 10)
- ladder: [(임계dd, 유닛수), ...] 형태(기본 [-0.15, -0.20, -0.25, -0.30, -0.35])
- dd_window: 드로우다운 창 길이(기본 252)
- slippage_bps: 체결가 슬리피지(bps)
- normalize_exit, normalize_buffer_pct: 정상가 회복 청산 및 버퍼
- use_trailing_stop, trailing_stop_atr_multiplier, atr_period: ATR 트레일링 스탑 설정
- use_kospi_momentum_exit, momentum_exit_threshold: KOSPI 평균 모멘텀 청산
- use_rsi_take_profit, rsi_take_profit_threshold, min_profit_for_rsi: RSI 기반 익절

7) 출력/로그
- 시나리오별 자산곡선 CSV/PNG: logs/kospi_dd_equity_{Scenario}.csv/.png
- 요약표 CSV: logs/kospi_dd_results.csv (CAGR 기준 정렬)
- 실행 로그: logs/kospi_dd_strategy.log

주의
- 본 전략은 EOD 데이터 기반. 실거래 자동화 시 마감 데이터 확정 후 실행하십시오.
- 레버리지 상품의 특성을 고려하여 최대 낙폭(MDD) 관리와 주문 슬리피지 설정에 유의하십시오.
"""

# -*- coding: utf-8 -*-

import os
import io
import sys
import pandas as pd
import numpy as np
import logging
import talib
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, 'kospi_dd_strategy.log')

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file_path, mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)


def load_series(data_dir: str, kospi_pattern: str = 'etf_index/KOSPI_*.csv', etf_filename: str = 'etf_index/122630_KODEX 레버리지.csv'):
    kospi_path = None
    for p in [os.path.join(data_dir, kospi_pattern.replace('*', k)) for k in ['코스피 지수']]:
        if os.path.exists(p):
            kospi_path = p
            break
    if kospi_path is None:
        # fallback: glob 첫 파일
        import glob
        matches = glob.glob(os.path.join(data_dir, 'etf_index', 'KOSPI_*.csv'))
        if not matches:
            logging.error('KOSPI 지수 데이터를 찾을 수 없습니다.')
            return None, None
        kospi_path = matches[0]

    etf_path = os.path.join(data_dir, etf_filename)
    if not os.path.exists(etf_path):
        logging.error('122630 ETF 데이터를 찾을 수 없습니다.')
        return None, None

    kospi = pd.read_csv(kospi_path, index_col='date', parse_dates=True)
    kospi.columns = [c.lower() for c in kospi.columns]
    etf = pd.read_csv(etf_path, index_col='date', parse_dates=True)
    etf.columns = [c.lower() for c in etf.columns]

    # 공통 거래일 교집합으로 정렬
    common = kospi.index.intersection(etf.index)
    kospi = kospi.loc[common].sort_index()
    etf = etf.loc[common].sort_index()
    return kospi, etf


def backtest_drawdown_pyramid(
    kospi: pd.DataFrame,
    etf: pd.DataFrame,
    initial_capital: float = 100_000_000,
    unit_splits: int = 10,
    ladder: list | None = None,
    dd_window: int = 252,
    normalize_exit: bool = True,
    normalize_buffer_pct: float = 0.0,
    take_profit_pct: float | None = None,
    slippage_bps: float = 0.0,
    # 추가 지표 기반 청산 옵션
    use_trailing_stop: bool = False,
    trailing_stop_atr_multiplier: float = 3.0,
    atr_period: int = 20,
    use_kospi_momentum_exit: bool = False,
    momentum_exit_threshold: float = 0.4,
    use_rsi_take_profit: bool = False,
    rsi_period: int = 14,
    rsi_take_profit_threshold: float = 70.0,
    min_profit_for_rsi: float = 0.0,
):
    if ladder is None:
        # (threshold_drawdown_pct, allocation_units)
        ladder = [
            (-0.15, 1),
            (-0.20, 1),
            (-0.25, 2),
            (-0.30, 4),
            (-0.35, 2),
        ]
    total_units = sum(units for _, units in ladder)
    assert total_units == unit_splits, 'ladder 유닛 합이 unit_splits와 일치해야 합니다.'

    # 1년 고점 및 드로우다운 계산 (전일까지 기준)
    kospi = kospi.copy()
    kospi['high_1y'] = kospi['close'].rolling(dd_window).max().shift(1)
    kospi['dd'] = kospi['close'] / kospi['high_1y'] - 1.0

    # KOSPI 평균 모멘텀 지표 (전일 기준) - 선택적 사용
    if use_kospi_momentum_exit:
        momentum_periods = [i * 20 for i in range(1, 11)]  # 20,40,...,200
        for period in momentum_periods:
            kospi[f'Momentum_{period}'] = (kospi['close'].shift(1) > kospi['close'].shift(1 + period)).astype(int)
        momentum_cols = [f'Momentum_{p}' for p in momentum_periods]
        kospi['Average_Momentum'] = kospi[momentum_cols].sum(axis=1) / len(momentum_periods)

    # ETF 지표: ATR, RSI (당일 기반이지만 체결은 종가 근사)
    etf = etf.copy()
    etf['atr'] = talib.ATR(etf['high'], etf['low'], etf['close'], timeperiod=atr_period)
    etf['rsi'] = talib.RSI(etf['close'], timeperiod=rsi_period)

    cash = initial_capital
    qty = 0
    avg_price = 0.0
    equity_curve = pd.Series(index=kospi.index, dtype=float)

    # 현재까지 소진한 유닛 수
    used_units = 0
    unit_value = initial_capital / unit_splits

    # 트레일링 스탑 상태
    highest_price_since_buy = 0.0
    stop_loss_price = 0.0

    for date in kospi.index:
        if pd.isna(kospi.loc[date, 'high_1y']):
            equity_curve.loc[date] = cash + qty * etf.loc[date, 'close']
            continue

        # 체결 가격(슬리피지 반영)
        etf_close = etf.loc[date, 'close']
        buy_price = etf_close * (1 + slippage_bps / 10000.0) if slippage_bps else etf_close
        sell_price = etf_close * (1 - slippage_bps / 10000.0) if slippage_bps else etf_close

        # 1) 분할 매수 판단
        dd = kospi.loc[date, 'dd']
        for threshold, units in ladder:
            if used_units >= total_units:
                break
            # 아직 해당 계단이 미집행이고, 하락률이 임계 이하로 내려왔으면 집행
            # 계단 집행 수 = min(남은 유닛, 이번 계단 유닛)
            if dd <= threshold and used_units < total_units:
                to_use = min(units, total_units - used_units)
                spend = unit_value * to_use
                if cash >= spend:
                    buy_qty = int(spend // buy_price)
                    if buy_qty > 0:
                        spend = buy_qty * buy_price
                        new_total_cost = avg_price * qty + spend
                        qty += buy_qty
                        avg_price = new_total_cost / qty
                        cash -= spend
                        used_units += to_use
                        # 트레일링 초기화/업데이트
                        if pd.notna(etf.loc[date, 'high']):
                            highest_price_since_buy = max(highest_price_since_buy, etf.loc[date, 'high']) if qty > 0 else etf.loc[date, 'high']
                        stop_loss_price = 0.0
                        logging.info(f"[{date.date()}] BUY ladder {threshold*100:.0f}% x{to_use} units qty={buy_qty} price={buy_price:,.0f}")

        # 2) 청산 로직
        sell_all = False
        sell_reasons = []
        sell_price_override = None

        # ATR 트레일링 스탑 (ETF 기반)
        if qty > 0 and use_trailing_stop and pd.notna(etf.loc[date, 'atr']) and etf.loc[date, 'atr'] > 0:
            if pd.notna(etf.loc[date, 'high']):
                highest_price_since_buy = max(highest_price_since_buy, etf.loc[date, 'high'])
            ts_price = highest_price_since_buy - (etf.loc[date, 'atr'] * trailing_stop_atr_multiplier)
            stop_loss_price = max(stop_loss_price, ts_price) if stop_loss_price else ts_price
            if pd.notna(etf.loc[date, 'low']) and etf.loc[date, 'low'] < stop_loss_price:
                sell_all = True
                sell_price_override = stop_loss_price
                sell_reasons.append('ATR_TrailingStop')

        # 정상가 회복 청산 (KOSPI)
        if normalize_exit and kospi.loc[date, 'close'] >= kospi.loc[date, 'high_1y'] * (1 + normalize_buffer_pct):
            sell_all = True
            sell_reasons.append('NormalizeExit')

        # 수익 실현 청산 (고정 TP)
        if take_profit_pct is not None and qty > 0:
            pnl_pct = sell_price / avg_price - 1.0
            if pnl_pct >= take_profit_pct:
                sell_all = True
                sell_reasons.append(f'TakeProfit_{int(take_profit_pct*100)}%')

        # KOSPI 평균 모멘텀 청산
        if qty > 0 and use_kospi_momentum_exit and 'Average_Momentum' in kospi.columns:
            if pd.notna(kospi.loc[date, 'Average_Momentum']) and kospi.loc[date, 'Average_Momentum'] < momentum_exit_threshold:
                sell_all = True
                sell_reasons.append('KOSPI_MomentumExit')

        # RSI 기반 수익 실현 (ETF)
        if qty > 0 and use_rsi_take_profit and pd.notna(etf.loc[date, 'rsi']):
            pnl_pct_now = sell_price / avg_price - 1.0
            if etf.loc[date, 'rsi'] >= rsi_take_profit_threshold and pnl_pct_now >= min_profit_for_rsi:
                sell_all = True
                sell_reasons.append(f'RSI_TP_{int(rsi_take_profit_threshold)}')

        if sell_all and qty > 0:
            final_sell_price = sell_price_override if sell_price_override is not None else sell_price
            cash += qty * final_sell_price
            logging.info(f"[{date.date()}] SELL ALL qty={qty} price={final_sell_price:,.0f} reason={'+'.join(sell_reasons) if sell_reasons else 'N/A'}")
            qty = 0
            avg_price = 0.0
            used_units = 0
            highest_price_since_buy = 0.0
            stop_loss_price = 0.0

        equity_curve.loc[date] = cash + qty * etf_close

    return equity_curve


def calculate_performance(equity_curve: pd.Series):
    if equity_curve.empty or equity_curve.iloc[0] == 0:
        return 0.0, 0.0
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100
    roll_max = equity_curve.cummax()
    dd = equity_curve / roll_max - 1
    mdd = dd.min() * 100
    return total_return, mdd


def plot_equity(equity_curve: pd.Series, title: str, out_name: str | None = None):
    plt.figure(figsize=(12, 6))
    plt.plot(equity_curve.index, equity_curve, label='Equity')
    plt.title(title)
    plt.grid(True, linestyle='--', linewidth=0.5)
    plt.yscale('log')
    formatter = FuncFormatter(lambda y, _: f'{int(y):,}')
    plt.gca().yaxis.set_major_formatter(formatter)
    plt.tight_layout()
    if out_name is None:
        # 제목 기반 파일명 생성
        safe = (
            title.replace(' ', '_')
            .replace('%', '')
            .replace('/', '-')
            .replace(':', '-')
        )
        out_name = f"{safe}.png"
    out = os.path.join(log_dir, out_name)
    plt.savefig(out)
    logging.info(f"Saved plot: {out}")


if __name__ == '__main__':
    DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
    START = '2010-01-01'
    END = '2025-09-01'

    kospi, etf = load_series(DATA_DIR)
    if kospi is None or etf is None:
        sys.exit(1)

    kospi = kospi.loc[(kospi.index >= START) & (kospi.index <= END)]
    etf = etf.loc[kospi.index]

    # 다음 테스트(미세 튜닝): Normal buffer / ATR TS 배수(베스트 주변) / DD 창(252)
    buffers = [0.0, 0.0025, 0.005, 0.0075]  # 0.00%, 0.25%, 0.50%, 0.75%
    atr_multipliers = [2.8, 3.0, 3.2]
    dd_windows = [252]

    # 베스트(2위, buf=0.00, ATR 3.2x, DD 252)를 최우선으로 명시 실행
    scenarios = [{
        "name": "BEST_NormExit_ATR3.2x_buf0.00%_dd252",
        "normalize_exit": True, "normalize_buffer_pct": 0.0, "take_profit_pct": None,
        "use_trailing_stop": True, "use_kospi_momentum_exit": False, "use_rsi_take_profit": False,
        "atr_mult": 3.2, "dd_window": 252,
    }]
    # 1) Normalized Exit만 (버퍼/창 길이 변주)
    for buf in buffers:
        for ddw in dd_windows:
            scenarios.append({
                "name": f"NormExit_buf{buf*100:.2f}%_dd{ddw}",
                "normalize_exit": True, "normalize_buffer_pct": buf, "take_profit_pct": None,
                "use_trailing_stop": False, "use_kospi_momentum_exit": False, "use_rsi_take_profit": False,
                "dd_window": ddw,
            })

    # 2) Normalized Exit + ATR TS (배수/창 길이 변주, 버퍼는 0과 0.5%만)
    for mul in atr_multipliers:
        for buf in [0.0, 0.005]:
            for ddw in dd_windows:
                scenarios.append({
                    "name": f"NormExit_ATR{mul:.1f}x_buf{buf*100:.2f}%_dd{ddw}",
                    "normalize_exit": True, "normalize_buffer_pct": buf, "take_profit_pct": None,
                    "use_trailing_stop": True, "use_kospi_momentum_exit": False, "use_rsi_take_profit": False,
                    "atr_mult": mul, "dd_window": ddw,
                })

    results = []
    for sc in scenarios:
        equity = backtest_drawdown_pyramid(
            kospi,
            etf,
            initial_capital=100_000_000,
            unit_splits=10,
            ladder=[(-0.15,1),(-0.20,1),(-0.25,2),(-0.30,4),(-0.35,2)],
            dd_window=sc.get("dd_window", 252),
            normalize_exit=sc["normalize_exit"],
            normalize_buffer_pct=sc["normalize_buffer_pct"],
            take_profit_pct=sc["take_profit_pct"],
            slippage_bps=0.0,
            use_trailing_stop=sc.get("use_trailing_stop", False),
            trailing_stop_atr_multiplier=sc.get("atr_mult", 3.0),
            atr_period=20,
            use_kospi_momentum_exit=sc.get("use_kospi_momentum_exit", False),
            momentum_exit_threshold=0.4,
            use_rsi_take_profit=sc.get("use_rsi_take_profit", False),
            rsi_period=14,
            rsi_take_profit_threshold=70.0,
            min_profit_for_rsi=0.0,
        )

        tr, mdd = calculate_performance(equity)
        years = (equity.index[-1] - equity.index[0]).days / 365.25 if len(equity) > 1 else 0
        cagr = ((equity.iloc[-1] / equity.iloc[0]) ** (1/years) - 1) * 100 if years > 0 else 0.0
        logging.info(f"[{sc['name']}] Total Return: {tr:.2f}%  MDD: {mdd:.2f}%  CAGR: {cagr:.2f}%")

        # 저장: 시나리오별 Equity CSV/PNG
        eq_csv = os.path.join(log_dir, f"kospi_dd_equity_{sc['name']}.csv")
        equity.to_csv(eq_csv, header=['equity'])
        plot_equity(
            equity,
            f"KOSPI DD Ladder ({sc['name']}) TR {tr:.1f}% / MDD {mdd:.1f}% / CAGR {cagr:.1f}%",
            out_name=f"kospi_dd_equity_{sc['name']}.png",
        )

        results.append({
            'Scenario': sc['name'],
            'NormalizeExit': sc['normalize_exit'],
            'TakeProfitPct': sc['take_profit_pct'] if sc['take_profit_pct'] is not None else 0.0,
            'BufferPct': sc.get('normalize_buffer_pct', 0.0) * 100,
            'ATRx': sc.get('atr_mult', 0.0),
            'DDWindow': sc.get('dd_window', 252),
            'TotalReturn(%)': tr,
            'CAGR(%)': cagr,
            'MDD(%)': mdd,
        })

    # 요약표 저장
    if results:
        df = pd.DataFrame(results).sort_values(by='CAGR(%)', ascending=False)
        summary_csv = os.path.join(log_dir, 'kospi_dd_results.csv')
        df.to_csv(summary_csv, index=False)
        logging.info("\n=== KOSPI DD Ladder Summary (sorted by CAGR) ===\n" + df.to_string(index=False))
        logging.info(f"Saved summary: {summary_csv}")


