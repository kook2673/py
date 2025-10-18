# -*- coding: utf-8 -*-
"""
스캘핑 1분봉 선물 전략 (BTCUSDT)

전략 개요:
- 기준 차트: 1분봉
- 이동평균: 5MA(단기), 20MA(중기)
- 진입(롱):
  1) 5MA < 20MA 상태(하락 구간)에서 5MA의 기울기가 음수→양수로 전환(상승 전환)
  2) 직전 2개 캔들이 연속 상승(2연속 양봉: close > open)
  3) 거래량이 평소 대비 증가(현재 volume > 평소 평균 * volume_multiplier)
  4) 20가지 추세 추종 필터 중 min_pass_filters 이상 충족
- 청산(롱):
  1) 진입 후 -stop_loss_pct(기본 0.1%) 도달 시 손절(분봉의 low로 체크)
  2) 5MA > 20MA 상태에서 5MA 기울기가 음수(하락 곡선)일 때 익절/청산
- 수수료: 왕복 0.05% (fee=0.0005)
- 레버리지: 기본 10배 (설정 가능)
- 포지션: 롱 전용

주의사항:
- 룩어헤드 방지: 모든 신호는 해당 분까지의 정보만 사용
- 필터는 추세 추종 성격의 20가지 조건을 제공하며, 유연하게 가중치/최소통과개수 조정 가능

사용법:
  python Scalp_1m_5MA20MA_Backtest.py

설정 변경:
  - main() 내부의 설정 블록에서 기간(csv_pattern), 손절, 레버리지, 수수료, 필터통과개수, 거래량 배수 등을 조정하십시오.
"""

import os
import glob
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# =========================
# 지표 유틸리티
# =========================

def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).mean()

def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False, min_periods=window).mean()

def wma(series: pd.Series, window: int) -> pd.Series:
    if window <= 0:
        return pd.Series(index=series.index, dtype=float)
    weights = np.arange(1, window + 1)
    return series.rolling(window).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

def hma(series: pd.Series, window: int) -> pd.Series:
    # HMA = WMA(2*WMA(n/2) - WMA(n), sqrt(n))
    n = int(window)
    if n <= 1:
        return series.copy()*np.nan
    half = max(1, n // 2)
    sqrt_n = max(1, int(np.sqrt(n)))
    wma_half = wma(series, half)
    wma_full = wma(series, n)
    hull = 2 * wma_half - wma_full
    return wma(hull, sqrt_n)

def vwap(df: pd.DataFrame, window: int) -> pd.Series:
    # 근사 VWAP: Σ(price*volume)/Σ(volume) 롤링
    pv = df['close'] * df['volume']
    num = pv.rolling(window, min_periods=window).sum()
    den = df['volume'].rolling(window, min_periods=window).sum()
    return num / (den.replace(0, np.nan))

def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(window, min_periods=window).mean()

def macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def adx_di(df: pd.DataFrame, window: int = 14):
    high = df['high']
    low = df['low']
    close = df['close']
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = pd.concat([
        (high - low),
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr_val = tr.rolling(window, min_periods=window).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(window, min_periods=window).sum() / atr_val.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(window, min_periods=window).sum() / atr_val.replace(0, np.nan)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.rolling(window, min_periods=window).mean()
    return adx, plus_di, minus_di

def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0):
    atr_val = atr(df, period)
    hl2 = (df['high'] + df['low']) / 2.0
    upperband = hl2 + multiplier * atr_val
    lowerband = hl2 - multiplier * atr_val
    st = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)  # +1 bullish, -1 bearish
    for i in range(len(df)):
        if i == 0:
            st.iloc[i] = upperband.iloc[i]
            direction.iloc[i] = -1
        else:
            if df['close'].iloc[i] > st.iloc[i-1]:
                st.iloc[i] = min(upperband.iloc[i], st.iloc[i-1])
                direction.iloc[i] = +1
            else:
                st.iloc[i] = max(lowerband.iloc[i], st.iloc[i-1])
                direction.iloc[i] = -1
    return st, direction

def parabolic_sar(df: pd.DataFrame, af_step=0.02, af_max=0.2):
    high = df['high'].values
    low = df['low'].values
    length = len(df)
    psar = np.zeros(length)
    bull = True
    af = af_step
    ep = low[0]
    psar[0] = low[0]
    for i in range(1, length):
        psar[i] = psar[i-1] + af * (ep - psar[i-1])
        if bull:
            if low[i] < psar[i]:
                bull = False
                psar[i] = ep
                af = af_step
                ep = low[i]
            else:
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + af_step, af_max)
        else:
            if high[i] > psar[i]:
                bull = True
                psar[i] = ep
                af = af_step
                ep = high[i]
            else:
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + af_step, af_max)
    return pd.Series(psar, index=df.index)

def aroon(series: pd.Series, period: int = 25):
    highs = series.rolling(period, min_periods=period).apply(lambda x: period - 1 - np.argmax(x), raw=True)
    lows = series.rolling(period, min_periods=period).apply(lambda x: period - 1 - np.argmin(x), raw=True)
    aroon_up = 100 * (period - highs) / period
    aroon_down = 100 * (period - lows) / period
    return aroon_up, aroon_down

def stochastic(df: pd.DataFrame, k_period=14, d_period=3):
    low_min = df['low'].rolling(k_period, min_periods=k_period).min()
    high_max = df['high'].rolling(k_period, min_periods=k_period).max()
    k = 100 * (df['close'] - low_min) / (high_max - low_min).replace(0, np.nan)
    d = k.rolling(d_period, min_periods=d_period).mean()
    return k, d

# =========================
# 20가지 추세 추종 필터 계산
# =========================
"""
추세 추종 필터 상세 설명 (현재 22개; 필요 시 20개로 조정 가능)

1) sma50_pos: 종가가 SMA(50) 위에 있으면 True. 중기 상승 추세 여부.
2) ema50_pos: 종가가 EMA(50) 위에 있으면 True. 지수 가중 중기 추세 확인.
3) sma5_slope_up: SMA(5)의 기울기 > 0. 초단기 평균이 상승 중인지.
4) sma20_slope_up: SMA(20)의 기울기 > 0. 단기 추세 상승 여부.
5) ema12_slope_up: EMA(12)의 기울기 > 0. MACD 구성요소의 빠른선 성격.
6) ema26_slope_up: EMA(26)의 기울기 > 0. MACD 구성요소의 느린선 성격.
7) macd_gt_signal: MACD 라인 > 시그널 라인. 모멘텀 상승 전개.
8) macd_hist_rising: MACD 히스토그램 증가(> 전 봉). 모멘텀 강화.
9) adx_trending: ADX(14) > 20. 추세 강도 존재.
10) plus_gt_minus: +DI > -DI. 상승 추세 우위.
11) supertrend_bull: 슈퍼트렌드 방향 +1. 추세 추종형 지표의 상승 상태.
12) psar_below_price: PSAR이 가격 아래. 추세 상승에 우호적.
13) price_above_donchian_mid: 종가 > 돈치안 채널 중선(20기). 박스 상단 편중.
14) keltner_basis_up: 켈트너 채널 기준선(EMA20) 상승. 추세 기울기 상승.
15) cci_pos: CCI(20) > 0. 평균 대비 가격이 높은 상태.
16) roc9_pos: ROC(9) > 0. 9기 수익률 양수.
17) mom10_pos: Momentum(10) > 0. 10기 가격 변화 양수.
18) ha_two_bull: Heikin-Ashi 두 봉 연속 양봉. 완만한 추세 전개.
19) aroon_up_gt_down: Aroon Up > Aroon Down. 최근 고점 갱신 우위.
20) vwma20_slope_up: VWAP 기반 가중 평균(20)의 기울기 > 0.
21) stoch_k_gt_d: Stochastic %K > %D. 단기 상승 우위 시그널.
22) stoch_k_rising: Stochastic %K 증가(> 전 봉). 단기 모멘텀 강화.

각 필터는 Boolean으로 계산되며, true 개수 합(=trend_pass_count)이
min_pass_filters 이상일 때 진입 조건을 보조합니다.
"""

def compute_trend_filters(df: pd.DataFrame) -> pd.DataFrame:
    close = df['close']
    open_ = df['open']

    filters = pd.DataFrame(index=df.index)

    # 1) SMA/EMA/VWMA, 기울기/상대위치
    filters['sma50_pos'] = (close > sma(close, 50))
    filters['ema50_pos'] = (close > ema(close, 50))
    filters['sma5_slope_up'] = sma(close, 5).diff() > 0
    filters['sma20_slope_up'] = sma(close, 20).diff() > 0
    filters['ema12_slope_up'] = ema(close, 12).diff() > 0
    filters['ema26_slope_up'] = ema(close, 26).diff() > 0

    # 2) MACD
    macd_line, signal_line, hist = macd(close)
    filters['macd_gt_signal'] = macd_line > signal_line
    filters['macd_hist_rising'] = hist.diff() > 0

    # 3) ADX/DI
    adx_val, plus_di, minus_di = adx_di(df)
    filters['adx_trending'] = adx_val > 20
    filters['plus_gt_minus'] = plus_di > minus_di

    # 4) Supertrend, PSAR
    st_val, st_dir = supertrend(df, period=10, multiplier=3.0)
    psar_val = parabolic_sar(df)
    filters['supertrend_bull'] = st_dir == 1
    filters['psar_below_price'] = psar_val < close

    # 5) Donchian, Keltner basis slope
    n_dc = 20
    donchian_mid = (df['high'].rolling(n_dc, min_periods=n_dc).max() + df['low'].rolling(n_dc, min_periods=n_dc).min()) / 2
    filters['price_above_donchian_mid'] = close > donchian_mid
    ema20 = ema(close, 20)
    atr20 = atr(df, 20)
    keltner_basis = ema20
    filters['keltner_basis_up'] = keltner_basis.diff() > 0

    # 6) CCI, ROC, Momentum
    tp = (df['high'] + df['low'] + df['close']) / 3
    cci = (tp - tp.rolling(20, min_periods=20).mean()) / (0.015 * tp.rolling(20, min_periods=20).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True))
    filters['cci_pos'] = cci > 0
    filters['roc9_pos'] = close.pct_change(9) > 0
    filters['mom10_pos'] = close.diff(10) > 0

    # 7) Heikin-Ashi 2연속 양봉
    ha_close = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    ha_open = ha_close.shift(1).combine(ha_close.shift(2), func=lambda a, b: (a if pd.notna(a) else 0 + b if pd.notna(b) else 0) / 2)
    ha_open = ha_open.fillna(df['open'])
    ha_bull = (ha_close > ha_open)
    filters['ha_two_bull'] = (ha_bull) & (ha_bull.shift(1))

    # 8) Aroon, VWMA slope
    aroon_up, aroon_down = aroon(close, 25)
    filters['aroon_up_gt_down'] = aroon_up > aroon_down
    vwma20 = vwap(df, 20)
    filters['vwma20_slope_up'] = vwma20.diff() > 0

    # 9) Stochastic trend
    k, d = stochastic(df, 14, 3)
    filters['stoch_k_gt_d'] = k > d
    filters['stoch_k_rising'] = k.diff() > 0

    return filters.fillna(False)

# =========================
# 백테스트 로직 (롱 전용)
# =========================

def backtest(df_1m: pd.DataFrame,
             stop_loss_pct: float = 0.001,  # 0.1%
             fee: float = 0.0005,
             leverage: int = 10,
             volume_window: int = 20,
             volume_multiplier: float = 1.2,
             min_pass_filters: int = 6,
             risk_fraction: float = 1.0,
             fast_ma_window: int = 5,
             slow_ma_window: int = 20,
             timeframe_minutes: int = 1):
    """1분/3분 스캘핑 백테스트 (롱 전용)

    stop_loss_pct: 손절 퍼센트(절대), 0.001 = -0.1%
    fee: 왕복 수수료 비율 (0.0005 = 0.05%)
    leverage: 레버리지 배수
    volume_window: 평소 거래량 산출 기간
    volume_multiplier: 평소 대비 증가 배수(> 평균*배수)
    min_pass_filters: 20개 필터 중 최소 충족 개수 (0이면 필터 미사용과 유사)
    risk_fraction: 진입시 자본의 비중(0~1)
    fast_ma_window: 진입/청산에 쓰는 빠른 MA 기간 (기본 5)
    slow_ma_window: 진입/청산에 쓰는 느린 MA 기간 (기본 20)
    timeframe_minutes: 캔들 타임프레임(1 또는 3 등 분 단위)
    """
    df = df_1m.copy()
    df = df.sort_index()

    # 타임프레임 리샘플링 (분단위)
    if timeframe_minutes and timeframe_minutes > 1:
        df = df.resample(f'{timeframe_minutes}T').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()

    # 기본 지표 (파라미터화)
    df['ma_fast'] = sma(df['close'], fast_ma_window)
    df['ma_slow'] = sma(df['close'], slow_ma_window)
    df['ma_fast_slope'] = df['ma_fast'].diff()
    df['ma_slow_slope'] = df['ma_slow'].diff()

    # 2연속 상승봉
    df['bull_candle'] = df['close'] > df['open']
    df['two_bull'] = df['bull_candle'] & df['bull_candle'].shift(1)

    # 거래량 필터
    df['vol_avg'] = df['volume'].rolling(volume_window, min_periods=volume_window).mean()
    df['vol_spike'] = df['volume'] > (df['vol_avg'] * volume_multiplier)

    # 20개 추세 필터
    filters = compute_trend_filters(df)
    df['trend_pass_count'] = filters.sum(axis=1)

    # 상태
    initial_capital = 10000.0
    capital = initial_capital
    position = 0  # 0: 없음, 1: 롱 보유
    entry_price = None
    entry_time = None

    trades = []
    equity_curve = []

    index_list = df.index
    for i in range(len(df)):
        t = index_list[i]
        row = df.iloc[i]

        price = float(row['close'])
        low = float(row['low'])

        ma_fast = row['ma_fast']
        ma_slow = row['ma_slow']
        ma_fast_slope = row['ma_fast_slope']
        prev_fast_slope = df['ma_fast_slope'].iloc[i-1] if i > 0 else np.nan

        # 기록 (에쿼티)
        equity_curve.append({'time': t, 'equity': capital, 'price': price, 'pos': position})

        # 아직 MA 계산 불가 시 스킵
        if np.isnan(ma_fast) or np.isnan(ma_slow) or np.isnan(ma_fast_slope):
            continue

        # 청산 로직 (보유 중)
        if position == 1:
            # 손절 (-stop_loss_pct): 캔들 low로 체크
            if low <= entry_price * (1 - stop_loss_pct):
                exit_price = entry_price * (1 - stop_loss_pct)
                gross_ret = (exit_price - entry_price) / entry_price
                pnl = gross_ret * leverage * capital * risk_fraction
                pnl_after_fee = pnl - (2 * fee * leverage * capital * risk_fraction)
                capital += pnl_after_fee
                trades.append({
                    'type': 'LONG_STOP',
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'exit_time': t,
                    'exit_price': exit_price,
                    'return_pct': gross_ret * 100,
                    'pnl': pnl_after_fee,
                    'capital_after': capital
                })
                position = 0
                entry_price = None
                entry_time = None
                continue

            # 빠른MA > 느린MA & 빠른MA 하락 곡선(기울기<0) 시 청산
            if (ma_fast > ma_slow) and (ma_fast_slope < 0):
                exit_price = price
                gross_ret = (exit_price - entry_price) / entry_price
                pnl = gross_ret * leverage * capital * risk_fraction
                pnl_after_fee = pnl - (2 * fee * leverage * capital * risk_fraction)
                capital += pnl_after_fee
                trades.append({
                    'type': 'LONG_EXIT',
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'exit_time': t,
                    'exit_price': exit_price,
                    'return_pct': gross_ret * 100,
                    'pnl': pnl_after_fee,
                    'capital_after': capital
                })
                position = 0
                entry_price = None
                entry_time = None
                continue

        # 진입 로직 (미보유)
        if position == 0:
            # 조건: 빠른MA < 느린MA, 빠른MA 기울기 음수→양수 전환, 2연속 양봉, 거래량 스파이크, 필터 통과
            cond_ma_relation = (ma_fast < ma_slow)
            cond_turn_up = (prev_fast_slope is not np.nan) and (prev_fast_slope <= 0) and (ma_fast_slope > 0)
            cond_two_bull = bool(row['two_bull'])
            cond_vol = bool(row['vol_spike'])
            cond_filters = (row['trend_pass_count'] >= min_pass_filters)

            if cond_ma_relation and cond_turn_up and cond_two_bull and cond_vol and cond_filters:
                position = 1
                entry_price = price
                entry_time = t
                trades.append({
                    'type': 'LONG_ENTRY',
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'info': {
                        'trend_pass': int(row['trend_pass_count']),
                        'fast_ma_window': fast_ma_window,
                        'slow_ma_window': slow_ma_window,
                        'timeframe_minutes': timeframe_minutes
                    }
                })
                continue

    # 마지막 캔들에서 포지션 정리(시장가 청산)
    if position == 1:
        exit_price = float(df['close'].iloc[-1])
        gross_ret = (exit_price - entry_price) / entry_price
        pnl = gross_ret * leverage * capital * risk_fraction
        pnl_after_fee = pnl - (2 * fee * leverage * capital * risk_fraction)
        capital += pnl_after_fee
        trades.append({
            'type': 'LONG_FINAL',
            'entry_time': entry_time,
            'entry_price': entry_price,
            'exit_time': df.index[-1],
            'exit_price': exit_price,
            'return_pct': gross_ret * 100,
            'pnl': pnl_after_fee,
            'capital_after': capital
        })

    total_return = (capital - initial_capital) / initial_capital * 100

    # MDD 계산
    peak = initial_capital
    mdd = 0.0
    for p in equity_curve:
        eq = p['equity']
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > mdd:
            mdd = dd

    return {
        'initial_capital': initial_capital,
        'final_capital': capital,
        'total_return': total_return,
        'mdd': mdd,
        'trades': trades,
        'equity_curve': equity_curve,
        'fast_ma_window': fast_ma_window,
        'slow_ma_window': slow_ma_window,
        'min_pass_filters': min_pass_filters,
        'timeframe_minutes': timeframe_minutes
    }

# =========================
# 시각화
# =========================

def plot_results(df: pd.DataFrame, result: dict, save_path: str):
    # 타임프레임에 맞춰 리샘플링
    tfm = int(result.get('timeframe_minutes', 1) or 1)
    if tfm > 1:
        df_plot = df.resample(f'{tfm}T').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna().copy()
    else:
        df_plot = df.copy()

    fig, axes = plt.subplots(3, 1, figsize=(20, 14))

    ax1 = axes[0]
    ax1.plot(df_plot.index, df_plot['close'], 'k-', linewidth=0.6, label=f'Price {tfm}m')
    # 동적 MA 표기
    fast_w = result.get('fast_ma_window', 5)
    slow_w = result.get('slow_ma_window', 20)
    df_plot['_ma_fast'] = sma(df_plot['close'], fast_w)
    df_plot['_ma_slow'] = sma(df_plot['close'], slow_w)
    ax1.plot(df_plot.index, df_plot['_ma_fast'], 'g-', linewidth=1.0, label=f'MA{fast_w}')
    ax1.plot(df_plot.index, df_plot['_ma_slow'], 'r-', linewidth=1.0, label=f'MA{slow_w}')

    for t in result['trades']:
        if t['type'] == 'LONG_ENTRY':
            ax1.scatter(t['entry_time'], t['entry_price'], color='green', marker='^', s=80)
        elif t['type'] in ('LONG_EXIT', 'LONG_STOP', 'LONG_FINAL'):
            ax1.scatter(t['exit_time'], t['exit_price'], color='red', marker='v', s=80)

    ax1.set_title(f'Price & Dynamic MA (Entries/Exits) - {tfm}m')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2 = axes[1]
    eq_times = [p['time'] for p in result['equity_curve']]
    eq_vals = [p['equity'] for p in result['equity_curve']]
    ax2.plot(eq_times, eq_vals, 'b-', linewidth=1.2, label='Equity')
    ax2.axhline(y=result['initial_capital'], linestyle='--', color='gray', label='Initial')
    ax2.set_title('Equity Curve')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    ax3 = axes[2]
    ax3.bar(df_plot.index, df_plot['volume'], color='gray', alpha=0.4, label='Volume')
    vol_avg_window = 20
    ax3.plot(df_plot.index, df_plot['volume'].rolling(vol_avg_window, min_periods=vol_avg_window).mean(), color='orange', linewidth=1.0, label='Vol Avg')
    ax3.set_title('Volume')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=7))
        ax.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()

# =========================
# 메인
# =========================

def main():
    print('🚀 1/3분 스캘핑 5MA/20MA 백테스트 시작')
    print('=' * 60)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, 'data', 'BTC_USDT', '1m')

    # 기간 설정
    csv_pattern = '2025-03.csv'  # 필요 시 변경
    files = glob.glob(os.path.join(data_dir, csv_pattern))
    if not files:
        print(f'❌ 데이터 없음: {data_dir} / {csv_pattern}')
        return

    dfs = []
    for f in sorted(files):
        try:
            df = pd.read_csv(f, index_col='timestamp', parse_dates=True)
            dfs.append(df)
            print(f'✅ 로드: {os.path.basename(f)} ({len(df)})')
        except Exception as e:
            print(f'❌ 로드 실패: {f} - {e}')

    df_1m = pd.concat(dfs).sort_index()
    df_1m = df_1m.drop_duplicates()

    # 백테스트 파라미터
    stop_loss_pct = 0.001   # 0.1%
    fee = 0.0005            # 0.05%
    leverage = 10
    volume_window = 20
    volume_multiplier = 1.2
    min_pass_filters = 6
    risk_fraction = 1.0
    fast_ma_window = 5
    slow_ma_window = 20
    timeframe_minutes = 3   # 1 또는 3 등으로 설정

    # 실행
    result = backtest(df_1m,
                      stop_loss_pct=stop_loss_pct,
                      fee=fee,
                      leverage=leverage,
                      volume_window=volume_window,
                      volume_multiplier=volume_multiplier,
                      min_pass_filters=min_pass_filters,
                      risk_fraction=risk_fraction,
                      fast_ma_window=fast_ma_window,
                      slow_ma_window=slow_ma_window,
                      timeframe_minutes=timeframe_minutes)

    print('\n✅ 백테스트 완료')
    print('=' * 60)
    print(f"타임프레임: {timeframe_minutes}분")
    print(f"총 수익률: {result['total_return']:.2f}%")
    print(f"최종 자본: {result['final_capital']:.2f} USDT")
    print(f"MDD: {result['mdd']:.2f}%")
    print(f"거래 수: {len([t for t in result['trades'] if t['type']!='LONG_ENTRY'])}회")

    # 저장
    os.makedirs(os.path.join(script_dir, 'logs'), exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = os.path.join(script_dir, 'logs', f'Scalp_{timeframe_minutes}m_{fast_ma_window}-{slow_ma_window}_{ts}.json')
    png_path = os.path.join(script_dir, 'logs', f'Scalp_{timeframe_minutes}m_{fast_ma_window}-{slow_ma_window}_{ts}.png')

    # 결과 저장(JSON)
    try:
        import json
        out = {
            'parameters': {
                'stop_loss_pct': stop_loss_pct,
                'fee': fee,
                'leverage': leverage,
                'volume_window': volume_window,
                'volume_multiplier': volume_multiplier,
                'min_pass_filters': min_pass_filters,
                'risk_fraction': risk_fraction,
                'fast_ma_window': fast_ma_window,
                'slow_ma_window': slow_ma_window,
                'timeframe_minutes': timeframe_minutes
            },
            'performance': {
                'initial_capital': result['initial_capital'],
                'final_capital': result['final_capital'],
                'total_return': result['total_return'],
                'mdd': result['mdd']
            },
            'trades': result['trades']
        }
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2, default=str)
        print(f'💾 결과 저장: {json_path}')
    except Exception as e:
        print(f'❌ JSON 저장 실패: {e}')

    # 차트 저장
    try:
        plot_results(df_1m, result, png_path)
        print(f'🖼️ 차트 저장: {png_path}')
    except Exception as e:
        print(f'❌ 차트 저장 실패: {e}')

if __name__ == '__main__':
    main()
