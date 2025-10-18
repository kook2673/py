#-*-coding:utf-8 -*-
'''
바이낸스 선물거래 1시간봉 MA 전략 백테스트
MA_Trend_Optimizer_1h.json에서 최근 500캔들로 최적화된 MA 파라미터를 불러와 대상 월을 검증(워크-포워드)합니다.

=== 전략 개요(개선 버전) ===
1) MA 크로스오버: 빠른 MA가 느린 MA를 상/하향 돌파할 때 신호 생성
2) 레짐/필터: 아래 조건을 모두 만족할 때만 진입 시도
   - 롱: 종가 > SMA200, 빠른 MA 기울기(5) > 0, ATR(24)/종가 ≥ 최소 변동성
   - 숏: 종가 < SMA200, 빠른 MA 기울기(5) < 0, ATR(24)/종가 ≥ 최소 변동성
3) 리스크 관리: ATR 기반 초기 손절 및 트레일링 스톱, 타임 스톱(최대 보유 봉수)
4) 에쿼티 서킷브레이커: 일 손실/월 손실 한도 도달 시 신규 진입 중단

=== 기본 진입/청산 ===
- 진입: 레짐 통과 + MA 크로스오버 발생 시
- 청산: 반대 크로스오버 OR ATR 스톱(초기/트레일링) OR 타임 스톱

=== 기본 설정 ===
- 레버리지: 7배 (백테스트 표시용)
- 초기 자본: 10,000 USDT
- 수수료: 0.1% (진입/청산 각각)
- 양방향 거래: 롱/숏 모두 지원
'''

import pandas as pd
import json
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import os
import glob

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# ===== 리스크/필터 기본값 =====
ATR_PERIOD = 24
SMA_REGIME = 200
SLOPE_WINDOW = 5
MIN_VOL_PCT = 0.003  # 완화: ATR/Close 최소 비율(예: 0.3%)
STOP_INIT_MULT = 2.5
STOP_TRAIL_MULT = 2.0  # 완화: 트레일링 폭 확대
TIME_STOP_BARS = 72  # 완화: 최대 보유 72봉(3일)
DAILY_LOSS_LIMIT = 0.03  # -3% 손실 시 해당 일 신규진입 중단
MONTHLY_LOSS_LIMIT = 0.10  # -10% 손실 시 월간 거래 중단

# 진입 밴드 설정(빠른 MA에서 k*ATR 이상 이탈 시 진입)
USE_ENTRY_BAND = True
ENTRY_BAND_K = 0.3

# ATR 포지션 사이징(고정 %리스크)
USE_ATR_POSITION_SIZING = True
RISK_PER_TRADE = 0.0075  # 0.75%/트레이드

def load_optimized_parameters(json_file, target_month=None):
    """최적화된 파라미터 로드"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            params = json.load(f)
        print(f"✅ 최적화된 파라미터 로드 완료: {json_file}")
        
        if target_month:
            # 특정 월의 파라미터 로드
            if target_month in params and params[target_month].get('long_strategy'):
                month_params = params[target_month]
                if month_params['long_strategy'].get('ma1') and month_params['long_strategy'].get('ma2'):
                    print(f"📅 사용할 파라미터: {target_month}월")
                    return month_params, target_month
                else:
                    print(f"❌ {target_month}월에 유효한 MA 파라미터가 없습니다.")
                    return None, None
            else:
                print(f"❌ {target_month}월 파라미터를 찾을 수 없습니다.")
                return None, None
        else:
            # 첫 번째 유효한 월의 파라미터 로드 (기존 방식)
            for month, month_params in params.items():
                if month_params.get('long_strategy') and month_params['long_strategy'].get('ma1') and month_params['long_strategy'].get('ma2'):
                    print(f"📅 사용할 파라미터: {month}월")
                    return month_params, month
        
        print("❌ 사용할 수 있는 파라미터가 없습니다.")
        return None, None
        
    except Exception as e:
        print(f"❌ 파라미터 로드 실패: {e}")
        return None, None

def load_1h_data(data_dir, target_month=None):
    """1시간봉 데이터 로드"""
    if target_month:
        print(f"📊 {target_month}월 1시간봉 데이터 로드 중...")
    else:
        print("📊 1시간봉 데이터 로드 중...")
    
    if target_month:
        # 특정 월의 데이터만 로드
        year = target_month.split('_')[0]
        month = target_month.split('_')[1]
        
        # 해당 월의 시작일과 종료일 계산
        start_date = f"{year}-{month.zfill(2)}-01"
        if month == "12":
            end_date = f"{int(year)+1}-01-01"
        else:
            end_date = f"{year}-{str(int(month)+1).zfill(2)}-01"
        
        print(f"📅 데이터 기간: {start_date} ~ {end_date}")
        
        # 연도별 파일에서 해당 월 데이터만 추출
        csv_files = []
        for year_file in [2024, 2025]:
            year_file_path = os.path.join(data_dir, f'BTCUSDT_1h_{year_file}.csv')
            if os.path.exists(year_file_path):
                csv_files.append(year_file_path)
        
        if not csv_files:
            print("❌ 1시간봉 데이터 파일을 찾을 수 없습니다.")
            return None
        
        # 해당 월의 데이터만 필터링
        all_dataframes = []
        total_candles = 0
        
        for csv_file in sorted(csv_files):
            try:
                file_name = os.path.basename(csv_file)
                print(f"📖 {file_name}에서 {target_month}월 데이터 추출 중...")
                
                # CSV 파일 읽기
                df = pd.read_csv(csv_file, index_col='timestamp', parse_dates=True)
                
                # 해당 월의 데이터만 필터링
                month_data = df[(df.index >= start_date) & (df.index < end_date)]
                
                if not month_data.empty:
                    print(f"   - {target_month}월 캔들 수: {len(month_data):,}개")
                    print(f"   - 기간: {month_data.index[0]} ~ {month_data.index[-1]}")
                    
                    all_dataframes.append(month_data)
                    total_candles += len(month_data)
                
            except Exception as e:
                print(f"   ❌ 파일 읽기 실패: {e}")
                continue
        
        if not all_dataframes:
            print(f"❌ {target_month}월 데이터를 찾을 수 없습니다.")
            return None
        
        # 데이터 병합
        print(f"\n🔄 {target_month}월 데이터 병합 중...")
        df_1h = pd.concat(all_dataframes, axis=0, ignore_index=False)
        
        # 중복 제거 및 정렬
        df_1h = df_1h[~df_1h.index.duplicated(keep='last')]
        df_1h = df_1h.sort_index()
        
        print(f"✅ {target_month}월 데이터 로드 완료: {len(df_1h):,}개 캔들")
        print(f"기간: {df_1h.index[0]} ~ {df_1h.index[-1]}")
        
        return df_1h
    
    else:
        # 기존 방식: 전체 데이터 로드
        csv_files = []
        for year in [2024, 2025]:
            year_file = os.path.join(data_dir, f'BTCUSDT_1h_{year}.csv')
            if os.path.exists(year_file):
                csv_files.append(year_file)
        
        if not csv_files:
            print("❌ 1시간봉 데이터 파일을 찾을 수 없습니다.")
            return None
        
        # 모든 데이터 로드 및 병합
        all_dataframes = []
        total_candles = 0
        
        for csv_file in sorted(csv_files):
            try:
                file_name = os.path.basename(csv_file)
                print(f"📖 {file_name} 읽는 중...")
                
                # CSV 파일 읽기
                df = pd.read_csv(csv_file, index_col='timestamp', parse_dates=True)
                
                print(f"   - 캔들 수: {len(df):,}개")
                print(f"   - 기간: {df.index[0]} ~ {df.index[-1]}")
                
                all_dataframes.append(df)
                total_candles += len(df)
                
            except Exception as e:
                print(f"   ❌ 파일 읽기 실패: {e}")
                continue
        
        if not all_dataframes:
            print("❌ 읽을 수 있는 데이터가 없습니다.")
            return None
        
        # 모든 데이터 병합
        print(f"\n🔄 {len(all_dataframes)}개 파일 병합 중...")
        df_1h = pd.concat(all_dataframes, axis=0, ignore_index=False)
        
        # 중복 제거 및 정렬
        df_1h = df_1h[~df_1h.index.duplicated(keep='last')]
        df_1h = df_1h.sort_index()
        
        print(f"✅ 데이터 병합 완료: {len(df_1h):,}개 캔들 (중복 제거 전: {total_candles:,}개)")
        print(f"기간: {df_1h.index[0]} ~ {df_1h.index[-1]}")
        
        return df_1h

def calculate_ma_indicators(df, ma1, ma2):
    """MA 지표 계산"""
    df[f'ma_{ma1}'] = df['close'].rolling(ma1).mean()
    df[f'ma_{ma2}'] = df['close'].rolling(ma2).mean()
    # 레짐용 SMA200, ATR, 변동성 비율, 빠른 MA 기울기
    if SMA_REGIME not in [ma1, ma2]:
        df[f'ma_{SMA_REGIME}'] = df['close'].rolling(SMA_REGIME).mean()
    df['atr'] = (
        pd.concat([
            (df['high'] - df['low']).abs(),
            (df['high'] - df['close'].shift()).abs(),
            (df['low'] - df['close'].shift()).abs()
        ], axis=1).max(axis=1)
    ).rolling(ATR_PERIOD).mean()
    df['vol_pct'] = df['atr'] / df['close']
    df['ma_fast_slope'] = df[f'ma_{ma1}'].diff(SLOPE_WINDOW) / SLOPE_WINDOW
    
    # MA 크로스오버 신호
    df['ma_cross'] = np.where(df[f'ma_{ma1}'] > df[f'ma_{ma2}'], 1, -1)
    df['ma_cross_signal'] = df['ma_cross'].diff()
    # 레짐 필터: 롱/숏 각각
    slow_col = f'ma_{SMA_REGIME}' if f'ma_{SMA_REGIME}' in df.columns else f'ma_{ma2}'
    df['regime_long'] = (df['close'] > df[slow_col]) & (df['ma_fast_slope'] > 0) & (df['vol_pct'] >= MIN_VOL_PCT)
    df['regime_short'] = (df['close'] < df[slow_col]) & (df['ma_fast_slope'] < 0) & (df['vol_pct'] >= MIN_VOL_PCT)
    # 진입 밴드(선택): 빠른 MA에서 k*ATR 이상 이탈 시만 진입 허용
    if USE_ENTRY_BAND:
        df['band_long_ok'] = df['close'] > (df[f'ma_{ma1}'] + ENTRY_BAND_K * df['atr'])
        df['band_short_ok'] = df['close'] < (df[f'ma_{ma1}'] - ENTRY_BAND_K * df['atr'])
    else:
        df['band_long_ok'] = True
        df['band_short_ok'] = True
    
    return df

def backtest_ma_strategy(df, params, initial_capital=10000, leverage=7, fee=0.001):
    """MA 전략 백테스트"""
    print("🔄 MA 전략 백테스트 실행 중...")
    
    # 파라미터 추출
    ma1 = params['long_strategy']['ma1']
    ma2 = params['long_strategy']['ma2']
    
    print(f"📊 MA 설정: MA{ma1} / MA{ma2}")
    
    # MA 지표 계산
    df = calculate_ma_indicators(df, ma1, ma2)
    df.dropna(inplace=True)
    
    if len(df) < max(ma1, ma2) + 10:
        print("❌ 데이터가 부족합니다.")
        return None
    
    # 백테스트 변수 초기화
    position = 0  # 0: 없음, 1: 롱, -1: 숏
    entry_price = 0
    entry_time = None
    entry_idx = None
    position_size = 0
    stop_price = None
    trail_price = None
    
    total_capital = initial_capital
    equity_curve = []
    trades = []
    trading_enabled = True
    allow_new_trades_today = True
    month_start_equity = initial_capital
    current_day = None
    daily_start_equity = initial_capital
    peak_equity = initial_capital
    
    # 실제 백테스트 시작 인덱스 (MA 계산용 데이터 제외)
    start_idx = max(ma1, ma2) + 1
    
    for i in range(start_idx, len(df)):
        current_price = df['close'].iloc[i]
        current_time = df.index[i]
        # 일자 변경 체크 및 데일리 리셋
        if current_day is None or current_time.date() != current_day:
            current_day = current_time.date()
            daily_start_equity = total_capital
            allow_new_trades_today = True
        
        # 현재 MA 크로스오버 신호
        cross_signal = df['ma_cross_signal'].iloc[i]
        atr_now = df['atr'].iloc[i] if 'atr' in df.columns else None
        regime_long = bool(df['regime_long'].iloc[i]) if 'regime_long' in df.columns else True
        regime_short = bool(df['regime_short'].iloc[i]) if 'regime_short' in df.columns else True
        
        # 진입 신호 확인
        if position == 0 and trading_enabled and allow_new_trades_today:  # 포지션 없음
            if cross_signal == 2 and regime_long and bool(df['band_long_ok'].iloc[i]):  # 상향 돌파 → 롱
                # 롱 진입
                position = 1
                entry_price = current_price
                entry_time = current_time
                entry_idx = i
                if USE_ATR_POSITION_SIZING and atr_now is not None and not np.isnan(atr_now) and atr_now > 0:
                    stop_distance = STOP_INIT_MULT * atr_now
                    dollar_risk = total_capital * RISK_PER_TRADE
                    position_size = (dollar_risk / stop_distance) * leverage
                else:
                    position_size = (total_capital * leverage) / current_price
                if atr_now is not None and not np.isnan(atr_now):
                    stop_price = entry_price - STOP_INIT_MULT * atr_now
                    trail_price = entry_price - STOP_TRAIL_MULT * atr_now
                
                print(f"🟢 롱 진입: {current_time} | 가격: {current_price:.0f} | MA{ma1}: {df[f'ma_{ma1}'].iloc[i]:.0f} | MA{ma2}: {df[f'ma_{ma2}'].iloc[i]:.0f}")
                
            elif cross_signal == -2 and regime_short and bool(df['band_short_ok'].iloc[i]):  # 하향 돌파 → 숏
                # 숏 진입
                position = -1
                entry_price = current_price
                entry_time = current_time
                entry_idx = i
                if USE_ATR_POSITION_SIZING and atr_now is not None and not np.isnan(atr_now) and atr_now > 0:
                    stop_distance = STOP_INIT_MULT * atr_now
                    dollar_risk = total_capital * RISK_PER_TRADE
                    position_size = (dollar_risk / stop_distance) * leverage
                else:
                    position_size = (total_capital * leverage) / current_price
                if atr_now is not None and not np.isnan(atr_now):
                    stop_price = entry_price + STOP_INIT_MULT * atr_now
                    trail_price = entry_price + STOP_TRAIL_MULT * atr_now
                
                print(f"🔴 숏 진입: {current_time} | 가격: {current_price:.0f} | MA{ma1}: {df[f'ma_{ma1}'].iloc[i]:.0f} | MA{ma2}: {df[f'ma_{ma2}'].iloc[i]:.0f}")
        
        # 포지션 관리 및 청산
        elif position == 1:  # 롱 포지션
            # 트레일링 업데이트
            if atr_now is not None and not np.isnan(atr_now):
                trail_price = max(trail_price, current_price - STOP_TRAIL_MULT * atr_now) if trail_price is not None else current_price - STOP_TRAIL_MULT * atr_now
            time_stop_hit = (entry_idx is not None) and ((i - entry_idx) >= TIME_STOP_BARS)
            stop_hit = (stop_price is not None) and (current_price <= stop_price)
            trail_hit = (trail_price is not None) and (current_price <= trail_price)
            exit_by = None
            if stop_hit:
                exit_by = 'ATR_STOP'
            if trail_hit and exit_by is None:
                exit_by = 'TRAIL_STOP'
            if time_stop_hit and exit_by is None:
                exit_by = 'TIME_STOP'
            if cross_signal == -2 and exit_by is None:  # 반대 신호
                exit_by = 'MA_크로스오버'
            if exit_by is not None:
                # 수익률 계산
                pnl = (current_price - entry_price) / entry_price * leverage
                pnl_amount = total_capital * pnl
                total_fee = (entry_price + current_price) * position_size * fee
                net_pnl = pnl_amount - total_fee
                
                # 자본 업데이트
                total_capital += net_pnl
                
                # 거래 기록
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'pnl': net_pnl,
                    'pnl_pct': pnl * 100,
                    'position_type': 'LONG',
                    'close_reason': exit_by
                })
                
                # 자산 곡선 기록
                equity_curve.append({
                    'time': current_time,
                    'equity': total_capital,
                    'price': current_price,
                    'pnl_display': f"롱청산({exit_by}): {entry_price:.0f} → {current_price:.0f} | 수익: {pnl*100:.2f}% | {net_pnl:.0f} USDT"
                })
                
                print(f"🟢 롱 청산: {current_time} | 진입: {entry_price:.0f} | 청산: {current_price:.0f} | 수익: {pnl*100:.2f}% | {net_pnl:.0f} USDT")
                
                # 변수 초기화
                position = 0
                entry_price = 0
                entry_time = None
                entry_idx = None
                position_size = 0
                stop_price = None
                trail_price = None
                # 손실 한도 체크
                daily_pnl_pct = (total_capital - daily_start_equity) / daily_start_equity if daily_start_equity > 0 else 0
                month_pnl_pct = (total_capital - month_start_equity) / month_start_equity if month_start_equity > 0 else 0
                if daily_pnl_pct <= -DAILY_LOSS_LIMIT:
                    allow_new_trades_today = False
                if month_pnl_pct <= -MONTHLY_LOSS_LIMIT:
                    trading_enabled = False
        
        elif position == -1:  # 숏 포지션
            # 트레일링 업데이트
            if atr_now is not None and not np.isnan(atr_now):
                trail_price = min(trail_price, current_price + STOP_TRAIL_MULT * atr_now) if trail_price is not None else current_price + STOP_TRAIL_MULT * atr_now
            time_stop_hit = (entry_idx is not None) and ((i - entry_idx) >= TIME_STOP_BARS)
            stop_hit = (stop_price is not None) and (current_price >= stop_price)
            trail_hit = (trail_price is not None) and (current_price >= trail_price)
            exit_by = None
            if stop_hit:
                exit_by = 'ATR_STOP'
            if trail_hit and exit_by is None:
                exit_by = 'TRAIL_STOP'
            if time_stop_hit and exit_by is None:
                exit_by = 'TIME_STOP'
            if cross_signal == 2 and exit_by is None:  # 반대 신호
                exit_by = 'MA_크로스오버'
            if exit_by is not None:
                # 수익률 계산
                pnl = (entry_price - current_price) / entry_price * leverage
                pnl_amount = total_capital * pnl
                total_fee = (entry_price + current_price) * position_size * fee
                net_pnl = pnl_amount - total_fee
                
                # 자본 업데이트
                total_capital += net_pnl
                
                # 거래 기록
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'pnl': net_pnl,
                    'pnl_pct': pnl * 100,
                    'position_type': 'SHORT',
                    'close_reason': exit_by
                })
                
                # 자산 곡선 기록
                equity_curve.append({
                    'time': current_time,
                    'equity': total_capital,
                    'price': current_price,
                    'pnl_display': f"숏청산({exit_by}): {entry_price:.0f} → {current_price:.0f} | 수익: {pnl*100:.2f}% | {net_pnl:.0f} USDT"
                })
                
                print(f"🔴 숏 청산: {current_time} | 진입: {entry_price:.0f} | 청산: {current_price:.0f} | 수익: {pnl*100:.2f}% | {net_pnl:.0f} USDT")
                
                # 변수 초기화
                position = 0
                entry_price = 0
                entry_time = None
                entry_idx = None
                position_size = 0
                stop_price = None
                trail_price = None
                # 손실 한도 체크
                daily_pnl_pct = (total_capital - daily_start_equity) / daily_start_equity if daily_start_equity > 0 else 0
                month_pnl_pct = (total_capital - month_start_equity) / month_start_equity if month_start_equity > 0 else 0
                if daily_pnl_pct <= -DAILY_LOSS_LIMIT:
                    allow_new_trades_today = False
                if month_pnl_pct <= -MONTHLY_LOSS_LIMIT:
                    trading_enabled = False
        
        # 진입 시 자산 곡선 기록
        if position != 0 and current_time == entry_time:
            equity_curve.append({
                'time': current_time,
                'equity': total_capital,
                'price': current_price,
                'pnl_display': f"{'롱' if position == 1 else '숏'}진입: {entry_price:.0f} | 미실현: 0.00%"
            })
    
    # 마지막 포지션 강제 청산
    if position != 0:
        final_price = df['close'].iloc[-1]
        if position == 1:  # 롱
            pnl = (final_price - entry_price) / entry_price * leverage
        else:  # 숏
            pnl = (entry_price - final_price) / entry_price * leverage
        
        pnl_amount = total_capital * pnl
        total_fee = (entry_price + final_price) * position_size * fee
        net_pnl = pnl_amount - total_fee
        total_capital += net_pnl
        
        trades.append({
            'entry_time': entry_time,
            'exit_time': df.index[-1],
            'entry_price': entry_price,
            'exit_price': final_price,
            'pnl': net_pnl,
            'pnl_pct': pnl * 100,
            'close_reason': 'FORCE_CLOSE',
            'position_type': 'LONG' if position == 1 else 'SHORT'
        })
    
    # 결과 계산
    if not equity_curve:
        total_return = 0
        final_equity = initial_capital
    else:
        final_equity = total_capital
        total_return = (final_equity - initial_capital) / initial_capital * 100
    
    # MDD 계산
    if not equity_curve:
        mdd = 0
    else:
        equity_values = [e['equity'] for e in equity_curve]
        peak = equity_values[0]
        mdd = 0
        
        for equity in equity_values:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak * 100
            if drawdown > mdd:
                mdd = drawdown
    
    return {
        'total_return': total_return,
        'final_equity': final_equity,
        'initial_capital': initial_capital,
        'equity_curve': equity_curve,
        'trades': trades,
        'mdd': mdd,
        'trade_count': len(trades),
        'win_trades': len([t for t in trades if t['pnl'] > 0]),
        'strategy_type': 'MA_CROSSOVER_1H',
        'ma1': ma1,
        'ma2': ma2
    }

def plot_backtest_results(df, backtest_result, ticker):
    """백테스트 결과를 그래프로 표시"""
    if not backtest_result or not backtest_result['equity_curve']:
        return None
    
    # 데이터 준비
    equity_curve = backtest_result['equity_curve']
    times = [e['time'] for e in equity_curve]
    equity_values = [e['equity'] for e in equity_curve]
    prices = [e['price'] for e in equity_curve]
    
    # 거래 신호 표시
    trades = backtest_result['trades']
    long_entries = []
    long_prices = []
    short_entries = []
    short_prices = []
    exits = []
    exit_prices = []
    
    for trade in trades:
        if trade['position_type'] == 'LONG':
            long_entries.append(trade['entry_time'])
            long_prices.append(trade['entry_price'])
        else:
            short_entries.append(trade['entry_time'])
            short_prices.append(trade['entry_price'])
        
        exits.append(trade['exit_time'])
        exit_prices.append(trade['exit_price'])
    
    # 그래프 생성
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(20, 12))
    
    # 첫 번째 그래프: 비트코인 가격과 MA, 매매 신호
    if not df.empty:
        # equity_curve의 시간 범위에 맞는 데이터만 필터링
        start_time = min(times)
        end_time = max(times)
        chart_data = df[(df.index >= start_time) & (df.index <= end_time)]
        
        if not chart_data.empty:
            ax1.plot(chart_data.index, chart_data['close'], 
                    label='BTC/USDT 1H', linewidth=1, color='lightblue', alpha=0.8)
            
            # MA 라인 표시
            ma1 = backtest_result['ma1']
            ma2 = backtest_result['ma2']
            if f'ma_{ma1}' in chart_data.columns:
                ax1.plot(chart_data.index, chart_data[f'ma_{ma1}'], 
                        label=f'MA{ma1}', linewidth=2, color='orange', alpha=0.8)
            if f'ma_{ma2}' in chart_data.columns:
                ax1.plot(chart_data.index, chart_data[f'ma_{ma2}'], 
                        label=f'MA{ma2}', linewidth=2, color='red', alpha=0.8)
    
    # equity_curve의 가격 데이터
    ax1.plot(times, prices, label='거래 가격', linewidth=2, color='darkblue', alpha=0.9)
    
    # 매매 신호 표시
    if long_entries:
        ax1.scatter(long_entries, long_prices, color='green', marker='^', s=150, 
                   label='롱 진입', zorder=10, alpha=1.0, edgecolors='darkgreen', linewidth=2)
    if short_entries:
        ax1.scatter(short_entries, short_prices, color='red', marker='v', s=150, 
                   label='숏 진입', zorder=10, alpha=1.0, edgecolors='darkred', linewidth=2)
    if exits:
        ax1.scatter(exits, exit_prices, color='black', marker='o', s=100, 
                   label='청산', zorder=10, alpha=1.0, edgecolors='black', linewidth=1)
    
    ax1.set_ylabel('가격 (USDT)', fontsize=12)
    ax1.set_title(f'{ticker} - 1시간봉 가격 차트 및 MA 전략 신호', fontsize=14)
    ax1.legend()
    ax1.grid(True, alpha=0.4)
    
    # 두 번째 그래프: 자산 곡선과 MDD
    ax2.plot(times, equity_values, label='자산 곡선', linewidth=3, color='darkgreen', alpha=0.9)
    
    # 초기 자본선
    initial_capital = equity_values[0] if equity_values else 10000
    ax2.axhline(y=initial_capital, color='red', linestyle='--', alpha=0.8, 
                label=f'초기 자본: {initial_capital:.0f}', linewidth=2)
    
    # MDD 표시
    if backtest_result['mdd'] > 0:
        peak_value = max(equity_values)
        ax2.axhline(y=peak_value, color='orange', linestyle=':', alpha=0.8, 
                   label=f'피크: {peak_value:.0f}', linewidth=2)
    
    ax2.set_ylabel('자산 (USDT)', fontsize=12)
    ax2.set_title(f'자산 곡선 (수익률: {backtest_result["total_return"]:.2f}%, MDD: {backtest_result["mdd"]:.2f}%)', fontsize=14)
    ax2.legend()
    ax2.grid(True, alpha=0.4)
    
    # x축 날짜 포맷 설정
    for ax in [ax1, ax2]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=7))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    
    # logs 폴더에 그래프 이미지 저장
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    image_filename = f'MA_Trend_1H_{ticker.replace("/", "_")}_{timestamp}.png'
    image_filepath = os.path.join(logs_dir, image_filename)
    
    plt.savefig(image_filepath, dpi=300, bbox_inches='tight')
    print(f"백테스트 결과 그래프가 {image_filepath}에 저장되었습니다.")
    
    return fig

def main():
    """메인 함수"""
    print("바이낸스 선물거래 1시간봉 MA 전략 백테스트 시작!")
    print("MA_Trend_Optimizer_1h.json에서 최적화된 파라미터를 불러옵니다.")
    
    # 백테스트할 월 설정 (None이면 전체 기간)
    target_month = "2024_02"  # 예: 2024_01, 2024_02, 2024_03 등
    
    if target_month:
        print(f"🎯 {target_month}월 백테스트 실행")
    else:
        print("🎯 전체 기간 백테스트 실행")
    
    # 최적화된 파라미터 로드
    json_file = 'MA_Trend_Optimizer_1h.json'
    if not os.path.exists(json_file):
        print(f"❌ {json_file} 파일을 찾을 수 없습니다.")
        print("먼저 MA_Trend_Optimizer.py를 실행하여 최적화된 파라미터를 생성하세요.")
        return
    
    params, month_used = load_optimized_parameters(json_file, target_month)
    if not params:
        return
    
    # 백테스트 설정
    ticker = 'BTC/USDT'
    initial_capital = 10000
    leverage = 7  # 스윙 전략 권장
    
    if target_month:
        print(f"\n{ticker} {target_month}월 1시간봉 데이터 로드 중...")
    else:
        print(f"\n{ticker} 1시간봉 데이터 로드 중...")
    
    # 1시간봉 데이터 로드
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, 'data', 'BTCUSDT', '1h')
    
    df_1h = load_1h_data(data_dir, target_month)
    if df_1h is None:
        return
    
    # 백테스트 실행
    print(f"\n{'='*60}")
    if target_month:
        print(f"{target_month}월 1시간봉 MA 전략 백테스트 실행 중...")
    else:
        print("1시간봉 MA 전략 백테스트 실행 중...")
    
    backtest_result = backtest_ma_strategy(df_1h, params, initial_capital, leverage)
    
    if backtest_result:
        # 결과 출력
        print(f"\n{'='*60}")
        print("백테스트 완료!")
        print(f"\n=== 백테스트 결과 ===")
        if target_month:
            print(f"테스트 기간: {target_month}월")
        print(f"사용 파라미터: {month_used}월")
        print(f"전략: MA{backtest_result['ma1']} / MA{backtest_result['ma2']} 크로스오버")
        print(f"초기 자본: {initial_capital:,.0f} USDT")
        print(f"최종 자본: {backtest_result['final_equity']:,.0f} USDT")
        print(f"총 수익률: {backtest_result['total_return']:.2f}%")
        print(f"최대 MDD: {backtest_result['mdd']:.2f}%")
        print(f"총 거래 횟수: {backtest_result['trade_count']}회")
        
        if backtest_result['trade_count'] > 0:
            win_rate = backtest_result['win_trades'] / backtest_result['trade_count'] * 100
            print(f"승률: {win_rate:.1f}%")
            
            # 평균 수익/손실
            profits = [t['pnl'] for t in backtest_result['trades'] if t['pnl'] > 0]
            losses = [t['pnl'] for t in backtest_result['trades'] if t['pnl'] < 0]
            
            if profits:
                avg_profit = sum(profits) / len(profits)
                print(f"평균 수익: {avg_profit:.0f} USDT")
            if losses:
                avg_loss = sum(losses) / len(losses)
                print(f"평균 손실: {avg_loss:.0f} USDT")
        
        # 결과를 파일로 저장
        final_results = {
            'ticker': ticker,
            'backtest_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'strategy_type': 'MA_CROSSOVER_1H',
            'strategy_description': f'MA{backtest_result["ma1"]} / MA{backtest_result["ma2"]} 크로스오버 전략',
            'initial_capital': initial_capital,
            'leverage': leverage,
            'target_month': target_month,
            'parameters_month': month_used,
            'backtest_period': {
                'start_date': df_1h.index[0].strftime('%Y-%m-%d'),
                'end_date': df_1h.index[-1].strftime('%Y-%m-%d'),
                'data_points': len(df_1h)
            },
            'backtest_result': backtest_result
        }
        
        if target_month:
            filename = f'MA_Trend_1H_{target_month}_{ticker.replace("/", "_")}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        else:
            filename = f'MA_Trend_1H_{ticker.replace("/", "_")}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        # logs 폴더에 저장
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        
        filepath = os.path.join(logs_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(final_results, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n최종 결과가 {filepath}에 저장되었습니다.")
        
        # 그래프 생성
        print("\n백테스트 결과 그래프 생성 중...")
        fig = plot_backtest_results(df_1h, backtest_result, ticker)
        if fig:
            plt.close(fig)  # 메모리 절약을 위해 그래프 닫기
    
    else:
        print("백테스트 실패")

if __name__ == "__main__":
    main()
