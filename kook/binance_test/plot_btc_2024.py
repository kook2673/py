"""
2024년 비트코인 가격 차트 그리기
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import numpy as np

# 한글 폰트 설정
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

def plot_btc_2024():
    """2024년 비트코인 가격 차트"""
    
    # 데이터 로드
    try:
        df = pd.read_csv("data/BTCUSDT/5m/BTCUSDT_5m_2024.csv")
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        # 2024년 데이터만 필터링
        df_2024 = df[(df.index >= '2024-01-01') & (df.index <= '2024-12-31')]
        
        if len(df_2024) == 0:
            print("2024년 데이터가 없습니다.")
            return
        
        print(f"2024년 데이터: {len(df_2024)}개 캔들")
        print(f"시작일: {df_2024.index[0]}")
        print(f"종료일: {df_2024.index[-1]}")
        
        # 그래프 생성
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12))
        
        # 1. 가격 차트 (일봉으로 리샘플링)
        daily_data = df_2024.resample('D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        # 캔들스틱 차트
        for i, (date, row) in enumerate(daily_data.iterrows()):
            color = 'green' if row['close'] >= row['open'] else 'red'
            alpha = 0.7
            
            # 몸통
            ax1.bar(date, abs(row['close'] - row['open']), 
                   bottom=min(row['open'], row['close']), 
                   color=color, alpha=alpha, width=0.8)
            
            # 위꼬리
            ax1.plot([date, date], [row['high'], max(row['open'], row['close'])], 
                    color=color, alpha=alpha, linewidth=1)
            
            # 아래꼬리
            ax1.plot([date, date], [min(row['open'], row['close']), row['low']], 
                    color=color, alpha=alpha, linewidth=1)
        
        # 이동평균선 추가
        daily_data['MA20'] = daily_data['close'].rolling(20).mean()
        daily_data['MA50'] = daily_data['close'].rolling(50).mean()
        daily_data['MA200'] = daily_data['close'].rolling(200).mean()
        
        ax1.plot(daily_data.index, daily_data['MA20'], label='MA20', color='orange', linewidth=1)
        ax1.plot(daily_data.index, daily_data['MA50'], label='MA50', color='blue', linewidth=1)
        ax1.plot(daily_data.index, daily_data['MA200'], label='MA200', color='purple', linewidth=1)
        
        ax1.set_title('Bitcoin Price Chart 2024 (Daily)', fontsize=16, fontweight='bold')
        ax1.set_ylabel('Price (USDT)', fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # x축 날짜 포맷
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
        
        # 2. 거래량 차트
        ax2.bar(daily_data.index, daily_data['volume'], color='lightblue', alpha=0.7)
        ax2.set_title('Trading Volume 2024 (Daily)', fontsize=16, fontweight='bold')
        ax2.set_ylabel('Volume', fontsize=12)
        ax2.set_xlabel('Date', fontsize=12)
        ax2.grid(True, alpha=0.3)
        
        # x축 날짜 포맷
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
        
        # 통계 정보 추가
        start_price = daily_data['close'].iloc[0]
        end_price = daily_data['close'].iloc[-1]
        max_price = daily_data['high'].max()
        min_price = daily_data['low'].min()
        total_return = (end_price - start_price) / start_price * 100
        
        stats_text = f"""
2024년 비트코인 통계:
• 시작가: ${start_price:,.0f}
• 종료가: ${end_price:,.0f}
• 최고가: ${max_price:,.0f}
• 최저가: ${min_price:,.0f}
• 총 수익률: {total_return:.1f}%
• 최대 낙폭: {((max_price - min_price) / max_price * 100):.1f}%
        """
        
        ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes, 
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        plt.tight_layout()
        plt.savefig('btc_2024_chart.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        print(f"\n2024년 비트코인 통계:")
        print(f"시작가: ${start_price:,.0f}")
        print(f"종료가: ${end_price:,.0f}")
        print(f"최고가: ${max_price:,.0f}")
        print(f"최저가: ${min_price:,.0f}")
        print(f"총 수익률: {total_return:.1f}%")
        print(f"최대 낙폭: {((max_price - min_price) / max_price * 100):.1f}%")
        
    except FileNotFoundError:
        print("데이터 파일을 찾을 수 없습니다: data/BTCUSDT/5m/BTCUSDT_5m_2024.csv")
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    plot_btc_2024()
