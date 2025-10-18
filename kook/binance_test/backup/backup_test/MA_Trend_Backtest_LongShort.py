'''

분할 진입 비율은 ATR을 접목하고, 2차 함수를 이용하여 비선형으로, 일종의 로그 그래프 형태로 진입하기 때문에 당일의 가격 변동폭에 따라서 달라져서 딱 얼마라고 규정짓지 않습니다.
드이어, Machine Learning도 도입하여 프로그램 돌리기 시작했습니다. ㅎ

로직은 다른거 하나 없이 이평선 두개로만 신호트리거로 썼는데...
머신러닝과 오토튜닝, 데이터 임계치 자동튜닝 등을 로직에 담다 보니 시간이 많이 소요되었네요

특별할 것도 없어요 그냥 이동평균선 두개만 세팅해서 현재가가 이평선 위로 돌파하면 매수, 아래로 돌파하면 매도...간단한 로직이예요 ㅋ

아...로직 자체는 단순한데, 매매코드에 파라미터 오토튜닝, 피처데이터 머신러니, 환경변수 주기적인 모니터링및 리파인 등 여러가지를 추가하느라 영혼까지 갈아넣은겁니다. ㅋ

즉, 그냥 단순하게 이동평균선 고정이 아니라 주기적으로 이동평균선을 오토튜닝해서 재설정 해 주고, 볼린저밴드, 스토캐스틱, macd 등 21가지 보조지표를 반복학습 하고, 그 반복학습 한 곌과값으로 한 달에 한번씩 자동으로 적용하고, 임계값을 또 튜닝하는...
좀 많이 복잡한 로직이라...다 만들고 나니까 라인수가 3,000줄이 넘어가네요 ㅋ

이미 백테 하고 과최적화, 룩어헤드바이어스 다 잡은 베스트 파라미터로 최초 실행...
한달 후부터 다시 오토튜닝과 머신러닝 드리프트모니터링 이렇게 3가지를 돌리는 구조라서...

레버리지 10배

저는 그냥 실행만 해 두면 지가 알아서 다 돌아가도록 세팅해서, 처음 백테 할 때 슬리피지, 펀비 다 반영하게 만들어서...
말 그대로 파라미터와 피처임계치 설정까지 자동 튜닝하게 만들었어요 ㅎ
'''


#-*-coding:utf-8 -*-
import os
import sys
import json
import glob
import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams

# 한글 폰트 설정
rcParams['font.family'] = 'DejaVu Sans'
rcParams['axes.unicode_minus'] = False

def calculate_ma(df, period):
    """Simple Moving Average 계산"""
    return df['close'].rolling(period).mean()

def backtest_strategy(df, ma1, ma2, initial_capital, leverage, fee=0.001, strategy_type='LONG', trend_params=None, use_trend=True):
    """MA + 추세 + 볼륨 필터 하이브리드 백테스트 전략"""
    if len(df) < max(ma1, ma2):
        return None
    
    # 기본 지표 계산
    df['momentum_5'] = df['close'].pct_change(5)
    df['momentum_10'] = df['close'].pct_change(10)
    df['trend_direction'] = np.where(df['close'] > df['close'].shift(1), 1, -1)
    df['trend_continuity'] = df['trend_direction'].rolling(5).sum()
    df['bb_upper'] = df['close'].rolling(20).mean() + 2 * df['close'].rolling(20).std()
    df['bb_lower'] = df['close'].rolling(20).mean() - 2 * df['close'].rolling(20).std()
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # RSI 계산
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df.dropna(inplace=True)
    
    # MA 계산
    df[f'ma_{ma1}'] = df['close'].rolling(ma1).mean()
    df[f'ma_{ma2}'] = df['close'].rolling(ma2).mean()
    
    # 기본 파라미터
    if trend_params is None:
        trend_params = {
            'trend_continuity_min': 4,
            'rsi_oversold': 25,
            'rsi_overbought': 90,
            'momentum_period': 5
        }
    
    # 전략 변수
    position = 0  # 0: 없음, 1: 롱, -1: 숏
    entry_price = 0
    entry_time = None
    capital = initial_capital
    trades = []
    equity_curve = []
    
    # 백테스트 실행
    for i in range(max(ma1, ma2), len(df)):
        current_time = df.index[i]
        current_price = df['close'].iloc[i]
        close_prev = df['close'].iloc[i-1]
        
        # MA 신호
        ma1_prev = df[f'ma_{ma1}'].iloc[i-1]
        ma2_prev = df[f'ma_{ma2}'].iloc[i-1]
        ma1_prev2 = df[f'ma_{ma1}'].iloc[i-2]
        ma2_prev2 = df[f'ma_{ma2}'].iloc[i-2]
        
        # 추세 신호 (하이브리드 모드일 때)
        trend_signal = 0
        if use_trend and i >= 20:
            momentum_5 = df['momentum_5'].iloc[i]
            momentum_10 = df['momentum_10'].iloc[i]
            trend_continuity = df['trend_continuity'].iloc[i]
            bb_position = df['bb_position'].iloc[i]
            rsi = df['rsi'].iloc[i]
            
            # JSON에서 가져온 추세 파라미터 사용
            if trend_params:
                trend_continuity_min = trend_params.get('trend_continuity_min', 2)
                rsi_oversold = trend_params.get('rsi_oversold', 50)
                rsi_overbought = trend_params.get('rsi_overbought', 80)
                momentum_period = trend_params.get('momentum_period', 5)
            else:
                # 기본값 (fallback)
                trend_continuity_min = 2
                rsi_oversold = 50
                rsi_overbought = 80
                momentum_period = 5
            
            # 추세 신호 생성 (JSON 파라미터 기반)
            if (momentum_5 > 0 and momentum_10 > 0 and  # 모멘텀 양수
                trend_continuity >= trend_continuity_min and  # JSON에서 가져온 연속 상승 기준
                bb_position > 0.3 and                     # 볼린저 밴드 0.3 이상
                rsi > rsi_oversold and                    # JSON에서 가져온 RSI 과매도 기준
                rsi < rsi_overbought):                    # JSON에서 가져온 RSI 과매수 기준
                trend_signal = 1  # 상승 추세
        
        # 롱 진입 신호 (MA + 추세 조합)
        if strategy_type == 'LONG' and position == 0:
            # 볼륨 필터
            volume_filter = False
            if i >= 20:
                current_volume = df['volume'].iloc[i] if 'volume' in df.columns else 1000
                avg_volume = df['volume'].rolling(20).mean().iloc[i] if 'volume' in df.columns else 1000
                volume_filter = current_volume > avg_volume * 1.2
            
            # MA 신호
            ma_signal = (close_prev >= ma1_prev and ma1_prev2 <= ma1_prev and 
                        close_prev >= ma2_prev and ma2_prev2 <= ma2_prev)
            
            # 추세 신호와 조합 - 추세 전략 우선
            if use_trend:
                # 추세 전략이 활성화되면 더 유연한 진입 조건
                if trend_signal == 1:
                    # 추세 신호가 있으면 MA 조건 완화 또는 추세만으로 진입
                    entry_condition = ((close_prev >= ma1_prev or close_prev >= ma2_prev) or 
                                     (trend_continuity >= 3 and momentum_5 > 0 and momentum_10 > 0)) and (i < 20 or volume_filter)
                else:
                    # 추세 신호가 없으면 기존 MA 조건
                    entry_condition = ma_signal and (i < 20 or volume_filter)
            else:
                entry_condition = ma_signal and (i < 20 or volume_filter)
            
            if entry_condition:
                position = 1
                entry_price = current_price
                entry_time = current_time
        
        # 숏 진입 신호 (MA + 추세 조합)
        elif strategy_type == 'SHORT' and position == 0:
            # 볼륨 필터
            volume_filter = False
            if i >= 20:
                current_volume = df['volume'].iloc[i] if 'volume' in df.columns else 1000
                avg_volume = df['volume'].rolling(20).mean().iloc[i] if 'volume' in df.columns else 1000
                volume_filter = current_volume > avg_volume * 1.2
            
            # MA 신호
            ma_signal_short = (close_prev <= ma1_prev and ma1_prev2 >= ma1_prev and 
                              close_prev <= ma2_prev and ma2_prev2 >= ma2_prev)
            
            # 추세 신호와 조합 - 추세 전략 우선
            if use_trend:
                # 추세 전략이 활성화되면 더 유연한 진입 조건
                if trend_signal == 1:
                    # 추세 신호가 있으면 MA 조건 완화 또는 추세만으로 진입
                    entry_condition = ((close_prev <= ma1_prev or close_prev <= ma2_prev) or 
                                     (trend_continuity <= -3 and momentum_5 < 0 and momentum_10 < 0)) and (i < 20 or volume_filter)
                else:
                    # 추세 신호가 없으면 기존 MA 조건
                    entry_condition = ma_signal_short and (i < 20 or volume_filter)
            else:
                entry_condition = ma_signal_short and (i < 20 or volume_filter)
            
            if entry_condition:
                position = -1
                entry_price = current_price
                entry_time = current_time
        
        # 롱 포지션 청산
        elif strategy_type == 'LONG' and position == 1:
            # 롱 청산: MA 데드크로스 또는 손절
            if (close_prev < ma1_prev and ma1_prev2 > ma1_prev) or \
               (close_prev < ma2_prev and ma2_prev2 > ma2_prev) or \
               (current_price <= entry_price * 0.95):  # 5% 손절
                exit_price = current_price
                pnl = (exit_price - entry_price) / entry_price * leverage
                capital *= (1 + pnl - fee * 2)  # 진입/청산 수수료
                
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'capital': capital
                })
                
                position = 0
                entry_price = 0
                entry_time = None
        
        # 숏 포지션 청산
        elif strategy_type == 'SHORT' and position == -1:
            # 숏 청산: MA 골든크로스 또는 손절
            if (close_prev > ma1_prev and ma1_prev2 < ma1_prev) or \
               (close_prev > ma2_prev and ma2_prev2 < ma2_prev) or \
               (current_price >= entry_price * 1.05):  # 5% 손절
                exit_price = current_price
                pnl = (entry_price - exit_price) / entry_price * leverage
                capital *= (1 + pnl - fee * 2)  # 진입/청산 수수료
                
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'capital': capital
                })
                
                position = 0
                entry_price = 0
                entry_time = None
        
        # 자산 곡선 기록
        equity_curve.append({
            'time': current_time,
            'equity': capital,
            'price': current_price
        })
    
    # 마지막 포지션 청산
    if position != 0:
        exit_price = df['close'].iloc[-1]
        if strategy_type == 'LONG':
            pnl = (exit_price - entry_price) / entry_price * leverage
        else:
            pnl = (entry_price - exit_price) / entry_price * leverage
        
        capital *= (1 + pnl - fee)
        trades.append({
            'entry_time': entry_time,
            'exit_time': df.index[-1],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'capital': capital
        })
    
    # 결과 계산
    total_return = (capital - initial_capital) / initial_capital * 100
    
    # MDD 계산
    peak = initial_capital
    mdd = 0
    for point in equity_curve:
        if point['equity'] > peak:
            peak = point['equity']
        drawdown = (peak - point['equity']) / peak * 100
        if drawdown > mdd:
            mdd = drawdown
    
    return {
        'total_return': total_return,
        'final_capital': capital,
        'trades': trades,
        'equity_curve': equity_curve,
        'mdd': mdd,
        'trade_count': len(trades)
    }

def load_optimized_parameters(json_file_path):
    """최적화된 파라미터 로드"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"파라미터 파일 로드 실패: {e}")
        return None

def main():
    # 스크립트 디렉토리
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 파라미터 파일 경로
    json_file_path = os.path.join(script_dir, 'MA_Trend_Backtest.json')
    
    # 최적화된 파라미터 로드
    monthly_parameters = load_optimized_parameters(json_file_path)
    if not monthly_parameters:
        print("파라미터를 로드할 수 없습니다.")
        return
    
    # 월별 파라미터를 수동으로 2024년 1월부터 순서대로 정렬
    sorted_monthly_parameters = {}
    
    # 2024년 1월부터 2025년 8월까지 순서대로 정렬
    ordered_months = []
    for year in [2024, 2025]:
        for month in range(1, 13):
            if year == 2025 and month > 8:  # 2025년 8월까지만
                break
            month_key = f"{year}_{month:02d}"
            if month_key in monthly_parameters:
                ordered_months.append(month_key)
    
    # 순서대로 딕셔너리 생성
    for month_key in ordered_months:
        sorted_monthly_parameters[month_key] = monthly_parameters[month_key]
    
    monthly_parameters = sorted_monthly_parameters
    print(f"📅 수동 정렬된 월별 파라미터: {list(monthly_parameters.keys())}")
    print(f"📊 총 {len(monthly_parameters)}개월 백테스트 예정")
    
    # 백테스트 설정
    ticker = 'BTC/USDT'
    initial_capital = 10000  # 기본값
    leverage = 5  # 기본값
    
    print(f"\n{ticker} 로컬 CSV 데이터 로드 중...")
    
    # 2024년부터 현재까지의 CSV 파일들 로드
    data_dir = os.path.join(script_dir, 'data', 'BTCUSDT', '4h')
    
    # 2024년부터 2025년까지의 CSV 파일들 찾기
    csv_files = []
    for year in [2024, 2025]:
        csv_pattern = f'BTCUSDT_4h_{year}.csv'
        year_files = glob.glob(os.path.join(data_dir, csv_pattern))
        csv_files.extend(year_files)
    
    if not csv_files:
        print(f"❌ CSV 파일을 찾을 수 없습니다.")
        print(f"📁 데이터 디렉토리: {data_dir}")
        print("먼저 필요한 데이터를 다운로드하세요.")
        return
    
    # 모든 CSV 파일을 하나로 합치기
    all_data = []
    for csv_file in sorted(csv_files):
        try:
            df = pd.read_csv(csv_file, index_col='datetime', parse_dates=True)
            all_data.append(df)
            print(f"✅ {os.path.basename(csv_file)} 로드 완료: {len(df)}개 캔들")
        except Exception as e:
            print(f"❌ {csv_file} 로드 실패: {e}")
    
    if not all_data:
        print("데이터를 가져올 수 없습니다.")
        return
    
    # 모든 데이터 합치기
    df_4h = pd.concat(all_data, ignore_index=False)
    df_4h = df_4h.sort_index()  # 시간순 정렬
    
    print(f"✅ 전체 데이터 로드 완료: {len(df_4h)}개 캔들")
    print(f"기간: {df_4h.index[0]} ~ {df_4h.index[-1]}")
    
    # 월간별 백테스트 결과 저장
    monthly_backtest_results = []
    
    # 각 월별로 백테스트 진행 (연속성 유지)
    current_capital = initial_capital  # 첫 달은 10000으로 시작
    for month_key, params in monthly_parameters.items():
        # 유효한 월별 키인지 확인 (YYYY_MM 형식)
        if not month_key.replace('_', '').isdigit() or month_key.count('_') != 1:
            print(f"⚠️ 유효하지 않은 키를 건너뜁니다: {month_key}")
            continue
            
        try:
            year, month = month_key.split('_')
            year = int(year)
            month = int(month)
        except ValueError:
            print(f"⚠️ 키 형식 오류를 건너뜁니다: {month_key}")
            continue
        
        # 해당 월의 데이터 추출 (정확히 1개월만)
        month_start_date = datetime.datetime(year, month, 1)
        if month == 12:
            month_end_date = datetime.datetime(year + 1, 1, 1) - datetime.timedelta(seconds=1)
        else:
            month_end_date = datetime.datetime(year, month + 1, 1) - datetime.timedelta(seconds=1)
        
        month_df = df_4h[(df_4h.index >= month_start_date) & (df_4h.index < month_end_date)]
        
        if len(month_df) < 10:  # 최소 10개 캔들 이상
            print(f"⚠️ {year}년 {month:02d}월 데이터가 부족하여 건너뜁니다. ({len(month_df)}개 캔들)")
            continue
        
        # 파라미터 추출
        long_params = params.get('long_strategy', {})
        short_params = params.get('short_strategy', {})
        
        if not long_params or not short_params:
            print(f"⚠️ {year}년 {month:02d}월 파라미터가 부족하여 건너뜁니다.")
            continue
        
        ma1_long = long_params['ma1']
        ma2_long = long_params['ma2']
        trend_params_long = long_params.get('trend_params', {})
        
        ma1_short = short_params['ma1']
        ma2_short = short_params['ma2']
        trend_params_short = short_params.get('trend_params', {})
        
        print(f"\n{'='*60}")
        # 진행률을 현재 처리 중인 월의 인덱스로 계산
        current_month_index = list(monthly_parameters.keys()).index(month_key) + 1
        print(f"진행률: {current_month_index}/{len(monthly_parameters)} 월")
        print(f"기간: {year}년 {month:02d}월")
        print(f"롱 전략: MA1={ma1_long}, MA2={ma2_long}, 추세={trend_params_long}")
        print(f"숏 전략: MA1={ma1_short}, MA2={ma2_short}, 추세={trend_params_short}")
        
        # 현재 자본을 롱/숏 50:50으로 분할
        long_capital = current_capital * 0.5
        short_capital = current_capital * 0.5
        
        print(f"현재 자본: {current_capital:.2f} USDT")
        print(f"전략: 롱 50% + 숏 50% (MA + 추세)")
        print(f"롱 자본: {long_capital:.2f} USDT")
        print(f"숏 자본: {short_capital:.2f} USDT")
        print()
        
        # 롱 전략 백테스트
        print("📈 롱 전략 백테스트 (자본: {:.2f} USDT)".format(long_capital))
        long_result = backtest_strategy(month_df, ma1_long, ma2_long, long_capital, leverage, 
                                       fee=0.001, strategy_type='LONG', trend_params=trend_params_long, use_trend=True)
        
        # 숏 전략 백테스트  
        print("📉 숏 전략 백테스트 (자본: {:.2f} USDT)".format(short_capital))
        short_result = backtest_strategy(month_df, ma1_short, ma2_short, short_capital, leverage, 
                                        fee=0.001, strategy_type='SHORT', trend_params=trend_params_short, use_trend=True)
        
        if long_result and short_result:
            # 롱/숏 결과 합산
            combined_equity_curve = []
            combined_trades = []
            
            # 월별 데이터에서 가격 정보 추출
            month_prices = month_df['close'].to_dict()
            
            # 시간순으로 정렬된 모든 시간대 생성 (중복 제거)
            all_times = sorted(set(month_df.index))
            
            # 각 시간대별로 롱/숏 자산 계산
            for current_time in all_times:
                current_price = month_prices.get(current_time, 0)
                
                # 롱 전략 자산 계산
                long_equity = long_capital
                long_entry_price = 0
                long_exit_price = 0
                if long_result['equity_curve']:
                    # 해당 시간대의 롱 자산 찾기
                    long_point = next((p for p in long_result['equity_curve'] if p['time'] == current_time), None)
                    if long_point:
                        long_equity = long_point['equity']
                
                # 숏 전략 자산 계산
                short_equity = short_capital
                short_entry_price = 0
                short_exit_price = 0
                if short_result['equity_curve']:
                    # 해당 시간대의 숏 자산 찾기
                    short_point = next((p for p in short_result['equity_curve'] if p['time'] == current_time), None)
                    if short_point:
                        short_equity = short_point['equity']
                
                # 현재 시간대의 롱/숏 진입가와 청산가 계산
                if long_result['trades']:
                    # 현재 시간 이전의 가장 최근 롱 거래 찾기
                    long_trades_before = [t for t in long_result['trades'] if t['entry_time'] <= current_time]
                    if long_trades_before:
                        latest_long_trade = max(long_trades_before, key=lambda x: x['entry_time'])
                        long_entry_price = latest_long_trade['entry_price']
                        
                        # 현재 시간이 진입 시간과 청산 시간 사이에 있는지 확인
                        if latest_long_trade['entry_time'] <= current_time < latest_long_trade['exit_time']:
                            # 아직 청산되지 않은 경우 (진입 후, 청산 전)
                            long_exit_price = current_price
                        else:
                            # 이미 청산된 경우
                            long_exit_price = latest_long_trade['exit_price']
                    else:
                        long_entry_price = 0
                        long_exit_price = 0
                else:
                    long_entry_price = 0
                    long_exit_price = 0
                
                if short_result['trades']:
                    # 현재 시간 이전의 가장 최근 숏 거래 찾기
                    short_trades_before = [t for t in short_result['trades'] if t['entry_time'] <= current_time]
                    if short_trades_before:
                        latest_short_trade = max(short_trades_before, key=lambda x: x['entry_time'])
                        short_entry_price = latest_short_trade['entry_price']
                        
                        # 현재 시간이 진입 시간과 청산 시간 사이에 있는지 확인
                        if latest_short_trade['entry_time'] <= current_time < latest_short_trade['exit_time']:
                            # 아직 청산되지 않은 경우 (진입 후, 청산 전)
                            short_exit_price = current_price
                        else:
                            # 이미 청산된 경우
                            short_exit_price = latest_short_trade['exit_price']
                    else:
                        short_entry_price = 0
                        short_exit_price = 0
                else:
                    short_entry_price = 0
                    short_exit_price = 0
                
                # pnl_display에 진입가와 매수/청산 정보 추가
                if long_entry_price > 0:
                    if long_exit_price > 0 and long_exit_price != long_entry_price:
                        # 이미 청산된 경우
                        if current_time >= latest_long_trade['exit_time']:
                            # 청산 직후에는 수익률과 수익금 표시
                            long_pnl = (long_exit_price - long_entry_price) / long_entry_price * 100
                            long_profit = (long_exit_price - long_entry_price) * leverage * (long_capital / long_entry_price)
                            long_info = f"롱청산:{long_pnl:+.1f}%({long_profit:+.0f})"
                        else:
                            # 아직 청산되지 않은 경우
                            long_info = f"롱진입:{long_entry_price:.0f}→{long_exit_price:.0f}"
                    else:
                        long_info = f"롱진입:{long_entry_price:.0f}"
                else:
                    long_info = "롱:대기"
                
                if short_entry_price > 0:
                    if short_exit_price > 0 and short_exit_price != short_entry_price:
                        # 이미 청산된 경우
                        if current_time >= latest_short_trade['exit_time']:
                            # 청산 직후에는 수익률과 수익금 표시
                            short_pnl = (short_entry_price - short_exit_price) / short_entry_price * 100
                            short_profit = (short_entry_price - short_exit_price) * leverage * (short_capital / short_entry_price)
                            short_info = f"숏청산:{short_pnl:+.1f}%({short_profit:+.0f})"
                        else:
                            # 아직 청산되지 않은 경우
                            short_info = f"숏진입:{short_entry_price:.0f}→{short_exit_price:.0f}"
                    else:
                        short_info = f"숏진입:{short_entry_price:.0f}"
                else:
                    short_info = "숏:대기"
                
                # 합산 자산 계산
                combined_equity = long_equity + short_equity
                
                # pnl_display 생성
                pnl_display = f"{long_info} | {short_info} | 합산:{combined_equity:.0f}"
                
                combined_equity_curve.append({
                    'time': current_time,
                    'equity': combined_equity,
                    'long_equity': long_equity,
                    'short_equity': short_equity,
                    'price': current_price,
                    'pnl_display': pnl_display,
                    'long_entry_price': long_entry_price,
                    'long_exit_price': long_exit_price,
                    'short_entry_price': short_entry_price,
                    'short_exit_price': short_exit_price
                })
            
            # 합산 거래 내역
            combined_trades = long_result['trades'] + short_result['trades']
            combined_trades.sort(key=lambda x: x['entry_time'])
            
            # 월별 결과 계산
            month_start_equity = combined_equity_curve[0]['equity'] if combined_equity_curve else current_capital
            month_end_equity = combined_equity_curve[-1]['equity'] if combined_equity_curve else current_capital
            month_return = (month_end_equity - month_start_equity) / month_start_equity * 100
            
            # MDD 계산
            peak = month_start_equity
            month_mdd = 0
            for point in combined_equity_curve:
                if point['equity'] > peak:
                    peak = point['equity']
                drawdown = (peak - point['equity']) / peak * 100
                if drawdown > month_mdd:
                    month_mdd = drawdown
            
            # 승률 계산
            if combined_trades:
                winning_trades = [t for t in combined_trades if t['pnl'] > 0]
                win_rate = len(winning_trades) / len(combined_trades) * 100
            else:
                win_rate = 0
            
            # 가격 변화
            month_start_price = month_df['close'].iloc[0]
            month_end_price = month_df['close'].iloc[-1]
            price_change = (month_end_price - month_start_price) / month_start_price * 100
            
            # 롱 전략 평균 진입가
            if long_result['trades']:
                long_avg_entry = sum(t['entry_price'] for t in long_result['trades']) / len(long_result['trades'])
                print(f"  롱 평균 진입가: {long_avg_entry:.0f} USDT")
            
            print(f"  가격 변화: {month_start_price:.0f} → {month_end_price:.0f} ({price_change:+.2f}%)")
            print(f"  승률: {win_rate:.1f}%")
            
            # 다음 달 초기 자본 업데이트
            current_capital = month_end_equity
            print(f"  다음 달 초기 자본: {current_capital:.2f} USDT")
            
            # 월별 결과 저장
            monthly_backtest_results.append({
                'month': month_key,
                'year': year,
                'month_num': month,
                'long_return': long_result['total_return'],
                'short_return': short_result['total_return'],
                'combined_return': month_return,
                'long_mdd': long_result['mdd'],
                'short_mdd': short_result['mdd'],
                'combined_mdd': month_mdd,
                'long_trades': long_result['trade_count'],
                'short_trades': short_result['trade_count'],
                'combined_trades': len(combined_trades),
                'win_rate': win_rate,
                'start_capital': month_start_equity,
                'end_capital': month_end_equity,
                'start_price': month_start_price,
                'end_price': month_end_price,
                'equity_curve': combined_equity_curve,
                'trades': combined_trades
            })
            
        else:
            print("백테스트 실패")
            # 실패한 경우에도 다음 달 초기 자본 유지
            monthly_backtest_results.append({
                'month': month_key,
                'year': year,
                'month_num': month,
                'long_return': 0,
                'short_return': 0,
                'combined_return': 0,
                'long_mdd': 0,
                'short_mdd': 0,
                'combined_mdd': 0,
                'long_trades': 0,
                'short_trades': 0,
                'combined_trades': 0,
                'win_rate': 0,
                'start_capital': current_capital,
                'end_capital': current_capital,
                'start_price': month_df['close'].iloc[0] if len(month_df) > 0 else 0,
                'end_price': month_df['close'].iloc[-1] if len(month_df) > 0 else 0,
                'equity_curve': [],
                'trades': []
            })
    
    print("\n============================================================")
    print("월간 백테스트 완료!")
    
    # 전체 성과 요약
    if monthly_backtest_results:
        total_months = len(monthly_backtest_results)
        profitable_months = len([r for r in monthly_backtest_results if r['combined_return'] > 0])
        total_return = (current_capital - initial_capital) / initial_capital * 100
        avg_monthly_return = total_return / total_months
        
        # 전체 MDD 계산
        all_equity_points = []
        for result in monthly_backtest_results:
            all_equity_points.extend(result['equity_curve'])
        
        all_equity_points.sort(key=lambda x: x['time'])
        
        peak = initial_capital
        total_mdd = 0
        for point in all_equity_points:
            if point['equity'] > peak:
                peak = point['equity']
            drawdown = (peak - point['equity']) / peak * 100
            if drawdown > total_mdd:
                total_mdd = drawdown
        
        print("\n=== 전체 성과 요약 ===")
        print(f"사용 전략: 롱 50% + 숏 50% (MA + 추세)")
        print(f"총 개월: {total_months}개월")
        print(f"수익 개월: {profitable_months}개월 ({profitable_months/total_months*100:.1f}%)")
        print(f"총 수익률: {total_return:.2f}%")
        print(f"평균 월간 수익률: {avg_monthly_return:.2f}%")
        print(f"최대 MDD: {total_mdd:.2f}%")
        
        # 전략별 성과
        long_total_return = sum(r['long_return'] for r in monthly_backtest_results)
        short_total_return = sum(r['short_return'] for r in monthly_backtest_results)
        long_avg_return = long_total_return / total_months
        short_avg_return = short_total_return / total_months
        
        print("\n=== 전략별 성과 ===")
        print(f"롱 전략: 총 수익률={long_total_return:.2f}%, 평균={long_avg_return:.2f}%")
        print(f"숏 전략: 총 수익률={short_total_return:.2f}%, 평균={short_avg_return:.2f}%")
        
        # 월간별 파라미터 변화
        print("\n=== 월간별 파라미터 변화 ===")
        for result in monthly_backtest_results:
            month_key = result['month']
            year = result['year']
            month = result['month_num']
            long_return = result['long_return']
            short_return = result['short_return']
            combined_return = result['combined_return']
            
            if month_key in monthly_parameters:
                params = monthly_parameters[month_key]
                long_params = params.get('long_strategy', {})
                short_params = params.get('short_strategy', {})
                
                ma1_long = long_params.get('ma1', 'N/A')
                ma2_long = long_params.get('ma2', 'N/A')
                ma1_short = short_params.get('ma1', 'N/A')
                ma2_short = short_params.get('ma2', 'N/A')
                
                print(f"{year}-{month:02d}: 롱(MA1={ma1_long}, MA2={ma2_long}), 숏(MA1={ma1_short}, MA2={ma2_short}), 합산={combined_return:.2f}%")
        
        # 결과 저장
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        result_filename = f"MA_Trend_Backtest_LongShort_Result_BTC_USDT_{timestamp}.json"
        result_path = os.path.join(script_dir, 'logs', result_filename)
        
        # 로그 디렉토리 생성
        os.makedirs(os.path.dirname(result_path), exist_ok=True)
        
        # 결과 데이터 구성
        result_data = {
            'backtest_period': {
                'start_date': monthly_backtest_results[0]['start_price'],
                'end_date': monthly_backtest_results[-1]['end_price'],
                'total_months': total_months
            },
            'performance_summary': {
                'total_return': total_return,
                'avg_monthly_return': avg_monthly_return,
                'profitable_months': profitable_months,
                'total_mdd': total_mdd,
                'final_capital': current_capital
            },
            'strategy_performance': {
                'long_total_return': long_total_return,
                'short_total_return': short_total_return,
                'long_avg_return': long_avg_return,
                'short_avg_return': short_avg_return
            },
            'monthly_results': monthly_backtest_results,
            'all_equity_curve': all_equity_points
        }
        
        # JSON 파일로 저장
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n최종 결과가 {result_path}에 저장되었습니다.")
        
        # 그래프 생성
        print("\n전체 기간 백테스트 결과 그래프 생성 중...")
        try:
            # 전체 데이터 준비
            all_times = [point['time'] for point in all_equity_points]
            all_equities = [point['equity'] for point in all_equity_points]
            all_prices = [point['price'] for point in all_equity_points]
            
            # 롱/숏 개별 자산 추출
            long_equities = []
            short_equities = []
            for result in monthly_backtest_results:
                if result['equity_curve']:
                    for point in result['equity_curve']:
                        long_equities.append(point.get('long_equity', 0))
                        short_equities.append(point.get('short_equity', 0))
            
            # 거래 내역 추출
            all_trades = []
            for result in monthly_backtest_results:
                all_trades.extend(result['trades'])
            
            # MA 데이터 준비 (4시간 데이터에서)
            ma_data = {}
            for month_key in monthly_parameters:
                if month_key in monthly_parameters:
                    params = monthly_parameters[month_key]
                    long_params = params.get('long_strategy', {})
                    short_params = params.get('short_strategy', {})
                    
                    # 해당 월의 데이터 찾기
                    for result in monthly_backtest_results:
                        if result['month'] == month_key and result['equity_curve']:
                            month_df = df_4h[(df_4h.index >= result['equity_curve'][0]['time']) & 
                                           (df_4h.index <= result['equity_curve'][-1]['time'])]
                            
                            if len(month_df) > 0:
                                ma1_long = long_params.get('ma1', 20)
                                ma2_long = long_params.get('ma2', 50)
                                ma1_short = short_params.get('ma1', 20)
                                ma2_short = short_params.get('ma2', 50)
                                
                                month_df[f'ma_{ma1_long}_long'] = month_df['close'].rolling(ma1_long).mean()
                                month_df[f'ma_{ma2_long}_long'] = month_df['close'].rolling(ma2_long).mean()
                                month_df[f'ma_{ma1_short}_short'] = month_df['close'].rolling(ma1_short).mean()
                                month_df[f'ma_{ma2_short}_short'] = month_df['close'].rolling(ma2_short).mean()
                                
                                ma_data[month_key] = month_df
                            break
            
            # 4개 서브플롯 생성
            fig, axes = plt.subplots(4, 1, figsize=(20, 16))
            
            # 1. 비트코인 4시간 데이터 + 거래내역 + MA
            ax1 = axes[0]
            
            # 전체 4시간 데이터 플롯
            df_4h_filtered = df_4h[(df_4h.index >= all_times[0]) & (df_4h.index <= all_times[-1])]
            ax1.plot(df_4h_filtered.index, df_4h_filtered['close'], 'k-', linewidth=1, alpha=0.8, label='BTC 4H')
            
            # MA 선들 플롯 (월별로 다른 색상)
            colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
            for i, (month_key, month_df) in enumerate(ma_data.items()):
                if len(month_df) > 0:
                    color = colors[i % len(colors)]
                    ma1_long = monthly_parameters[month_key]['long_strategy'].get('ma1', 20)
                    ma2_long = monthly_parameters[month_key]['long_strategy'].get('ma2', 50)
                    
                    ax1.plot(month_df.index, month_df[f'ma_{ma1_long}_long'], 
                            color=color, linewidth=1, alpha=0.6, linestyle='--')
                    ax1.plot(month_df.index, month_df[f'ma_{ma2_long}_long'], 
                            color=color, linewidth=1, alpha=0.6, linestyle=':')
            
            # 거래 내역 화살표 표시
            for trade in all_trades:
                if 'entry_time' in trade and 'exit_time' in trade:
                    # 진입 지점 (녹색 화살표 위)
                    ax1.scatter(trade['entry_time'], trade['entry_price'], 
                               color='green', marker='^', s=100, alpha=0.8, zorder=5)
                    # 청산 지점 (빨간색 화살표 아래)
                    ax1.scatter(trade['exit_time'], trade['exit_price'], 
                               color='red', marker='v', s=100, alpha=0.8, zorder=5)
                    
                    # 진입-청산 선 연결
                    ax1.plot([trade['entry_time'], trade['exit_time']], 
                            [trade['entry_price'], trade['exit_price']], 
                            'k-', alpha=0.5, linewidth=1)
            
            ax1.set_title('BTC 4시간 데이터 + 거래내역 + MA 이동평균선', fontsize=14, fontweight='bold')
            ax1.set_ylabel('가격 (USDT)', fontsize=12)
            ax1.legend(['BTC 4H', 'MA1 (롱)', 'MA2 (롱)'], loc='upper left')
            ax1.grid(True, alpha=0.3)
            
            # 2. 거래내역 상세
            ax2 = axes[1]
            
            # 거래별 수익률 표시
            trade_times = [trade['entry_time'] for trade in all_trades]
            trade_returns = [trade['pnl'] * 100 for trade in all_trades]  # 퍼센트로 변환
            
            colors = ['green' if ret > 0 else 'red' for ret in trade_returns]
            bars = ax2.bar(range(len(trade_times)), trade_returns, color=colors, alpha=0.7)
            
            # 수익률 값 표시
            for i, (bar, ret) in enumerate(zip(bars, trade_returns)):
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height + (0.1 if height > 0 else -0.1),
                        f'{ret:.1f}%', ha='center', va='bottom' if height > 0 else 'top')
            
            ax2.set_title('거래별 수익률', fontsize=14, fontweight='bold')
            ax2.set_ylabel('수익률 (%)', fontsize=12)
            ax2.set_xlabel('거래 순서', fontsize=12)
            ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
            ax2.grid(True, alpha=0.3)
            
            # 3. 자산증감현황
            ax3 = axes[2]
            
            # 롱/숏/합산 자산 곡선
            ax3.plot(all_times, all_equities, 'b-', linewidth=2, label='합산 자산', alpha=0.8)
            
            # 롱/숏 개별 자산 (월별로 구분)
            if long_equities and short_equities:
                ax3.plot(all_times[:len(long_equities)], long_equities, 'g-', linewidth=1, 
                        label='롱 자산', alpha=0.6)
                ax3.plot(all_times[:len(short_equities)], short_equities, 'r-', linewidth=1, 
                        label='숏 자산', alpha=0.6)
            
            ax3.axhline(y=initial_capital, color='black', linestyle='--', alpha=0.7, label='초기 자본')
            ax3.set_title('자산증감현황 (롱/숏/합산)', fontsize=14, fontweight='bold')
            ax3.set_ylabel('자산 (USDT)', fontsize=12)
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            
            # 4. MDD 현황
            ax4 = axes[3]
            
            # MDD 계산 및 플롯
            peak = initial_capital
            mdd_values = []
            mdd_times = []
            
            for i, equity in enumerate(all_equities):
                if equity > peak:
                    peak = equity
                drawdown = (peak - equity) / peak * 100
                mdd_values.append(drawdown)
                mdd_times.append(all_times[i])
            
            ax4.fill_between(mdd_times, mdd_values, 0, alpha=0.3, color='red', label='MDD')
            ax4.plot(mdd_times, mdd_values, 'r-', linewidth=1, alpha=0.8)
            
            # 최대 MDD 지점 표시
            max_mdd_idx = np.argmax(mdd_values)
            max_mdd = mdd_values[max_mdd_idx]
            max_mdd_time = mdd_times[max_mdd_idx]
            
            ax4.scatter(max_mdd_time, max_mdd, color='darkred', s=100, zorder=5, 
                       label=f'최대 MDD: {max_mdd:.2f}%')
            ax4.text(max_mdd_time, max_mdd + 0.5, f'{max_mdd:.2f}%', 
                     ha='center', va='bottom', fontweight='bold')
            
            ax4.set_title('MDD (Maximum Drawdown) 현황', fontsize=14, fontweight='bold')
            ax4.set_ylabel('MDD (%)', fontsize=12)
            ax4.set_xlabel('시간', fontsize=12)
            ax4.legend()
            ax4.grid(True, alpha=0.3)
            ax4.invert_yaxis()  # MDD는 위에서 아래로 표시
            
            # x축 날짜 포맷 (모든 서브플롯에 적용)
            for ax in axes:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
                ax.tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            
            # 그래프 저장
            graph_filename = f"MA_Trend_Backtest_LongShort_Graph_BTC_USDT_{timestamp}.png"
            graph_path = os.path.join(script_dir, 'logs', graph_filename)
            plt.savefig(graph_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"📊 개선된 그래프가 {graph_path}에 저장되었습니다.")
            
        except Exception as e:
            print(f"그래프 생성 실패: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
