import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import numpy as np

# 한글 폰트 설정
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

def load_btc_data():
    """비트코인 데이터 로드"""
    try:
        df = pd.read_csv('data/BTCUSDT/5m/BTCUSDT_5m_2018.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        print(f"데이터 로드 오류: {e}")
        return None

def plot_btc_2018():
    """2018년 비트코인 차트 그리기"""
    df = load_btc_data()
    if df is None:
        return
    
    # 2018년 데이터만 필터링
    df_2018 = df.loc['2018-01-01':'2018-12-31'].copy()
    
    if len(df_2018) == 0:
        print("2018년 데이터가 없습니다.")
        return
    
    # 일봉 데이터로 변환 (OHLCV 집계)
    daily_data = df_2018.resample('D').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    # 차트 생성
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), gridspec_kw={'height_ratios': [3, 1]})
    
    # 가격 차트
    ax1.plot(daily_data.index, daily_data['close'], linewidth=2, color='#f7931a', label='BTC Price')
    ax1.fill_between(daily_data.index, daily_data['low'], daily_data['high'], alpha=0.3, color='#f7931a')
    
    # 주요 구간 표시
    ax1.axvspan(pd.Timestamp('2018-01-01'), pd.Timestamp('2018-02-28'), alpha=0.2, color='red', label='Q1 2018 (Crash)')
    ax1.axvspan(pd.Timestamp('2018-03-01'), pd.Timestamp('2018-05-31'), alpha=0.2, color='orange', label='Q2 2018 (Recovery)')
    ax1.axvspan(pd.Timestamp('2018-06-01'), pd.Timestamp('2018-08-31'), alpha=0.2, color='yellow', label='Q3 2018 (Sideways)')
    ax1.axvspan(pd.Timestamp('2018-09-01'), pd.Timestamp('2018-12-31'), alpha=0.2, color='purple', label='Q4 2018 (Bear Market)')
    
    # 주요 가격 레벨 표시
    max_price = daily_data['high'].max()
    min_price = daily_data['low'].min()
    ax1.axhline(y=max_price, color='red', linestyle='--', alpha=0.7, label=f'Max: ${max_price:,.0f}')
    ax1.axhline(y=min_price, color='green', linestyle='--', alpha=0.7, label=f'Min: ${min_price:,.0f}')
    
    ax1.set_title('Bitcoin Price Chart 2018', fontsize=16, fontweight='bold')
    ax1.set_ylabel('Price (USDT)', fontsize=12)
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # 볼륨 차트
    ax2.bar(daily_data.index, daily_data['volume'], color='#f7931a', alpha=0.7)
    ax2.set_ylabel('Volume', fontsize=12)
    ax2.set_xlabel('Date', fontsize=12)
    ax2.grid(True, alpha=0.3)
    
    # x축 날짜 포맷
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # 통계 정보 출력
    print(f"\n=== 2018년 비트코인 통계 ===")
    print(f"시작가: ${daily_data['open'].iloc[0]:,.2f}")
    print(f"종료가: ${daily_data['close'].iloc[-1]:,.2f}")
    print(f"최고가: ${max_price:,.2f}")
    print(f"최저가: ${min_price:,.2f}")
    print(f"연간 수익률: {((daily_data['close'].iloc[-1] / daily_data['open'].iloc[0]) - 1) * 100:.2f}%")
    print(f"최대 낙폭: {((max_price - min_price) / max_price) * 100:.2f}%")
    
    # 분기별 수익률
    quarters = [
        ('Q1 2018', '2018-01-01', '2018-03-31'),
        ('Q2 2018', '2018-04-01', '2018-06-30'),
        ('Q3 2018', '2018-07-01', '2018-09-30'),
        ('Q4 2018', '2018-10-01', '2018-12-31')
    ]
    
    print(f"\n=== 분기별 수익률 ===")
    for quarter, start, end in quarters:
        try:
            q_data = daily_data.loc[start:end]
            if len(q_data) > 0:
                q_return = ((q_data['close'].iloc[-1] / q_data['open'].iloc[0]) - 1) * 100
                print(f"{quarter}: {q_return:.2f}%")
        except:
            print(f"{quarter}: 데이터 없음")
    
    plt.savefig('btc_2018_chart.png', dpi=300, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    plot_btc_2018()
