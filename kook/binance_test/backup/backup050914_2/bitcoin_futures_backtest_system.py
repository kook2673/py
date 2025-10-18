#-*-coding:utf-8 -*-
'''
비트코인 선물 종합 백테스트 시스템
=====================================

=== 지원 전략 ===
1. 변동성 돌파 전략 (Volatility Breakout)
2. 모멘텀 전략 (Momentum Strategy)  
3. 스윙 트레이딩 (Swing Trading)
4. 브레이크아웃 전략 (Breakout Strategy)
5. 스캘핑 전략 (Scalping Strategy)

=== 공통 기능 ===
- 다중 시간프레임 지원 (1분, 5분, 15분, 1시간, 4시간, 1일)
- 레버리지 거래 시뮬레이션
- 수수료 및 슬리피지 반영
- 리스크 관리 (손절매, 익절매)
- 상세한 성과 분석 및 시각화
- 실매매 연동 가능한 구조

=== 사용법 ===
python bitcoin_futures_backtest_system.py --strategy volatility --period 1h --start 2024-01-01 --end 2024-12-31
'''

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import os
import glob
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

class BitcoinFuturesBacktester:
    """비트코인 선물 백테스트 시스템"""
    
    def __init__(self, initial_capital: float = 10000, leverage: float = 10, fee: float = 0.001):
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.fee = fee
        self.current_capital = initial_capital
        self.position = None
        self.trades = []
        self.equity_curve = []
        
    def load_data(self, data_dir: str, start_date: str, end_date: str, timeframe: str = '1m') -> pd.DataFrame:
        """데이터 로드"""
        print(f"📊 데이터 로드 중... ({timeframe}봉, {start_date} ~ {end_date})")
        
        # 데이터 디렉토리 경로
        btc_data_dir = os.path.join(data_dir, 'BTC_USDT', timeframe)
        
        if not os.path.exists(btc_data_dir):
            raise FileNotFoundError(f"데이터 디렉토리를 찾을 수 없습니다: {btc_data_dir}")
        
        # 기간별 파일 로드
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        all_data = []
        current_date = start_dt
        
        while current_date <= end_dt:
            year = current_date.year
            month = current_date.month
            
            # 파일 패턴 생성
            file_pattern = os.path.join(btc_data_dir, f"{year}-{month:02d}.csv")
            
            if os.path.exists(file_pattern):
                try:
                    df = pd.read_csv(file_pattern)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df = df.set_index('timestamp')
                    all_data.append(df)
                    print(f"✅ {year}-{month:02d} 로드 완료: {len(df)}개 캔들")
                except Exception as e:
                    print(f"❌ {file_pattern} 로드 실패: {e}")
            
            # 다음 달로 이동
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1, day=1)
        
        if not all_data:
            raise ValueError("로드된 데이터가 없습니다.")
        
        # 모든 데이터 합치기
        combined_df = pd.concat(all_data, ignore_index=False)
        combined_df = combined_df.sort_index()
        combined_df = combined_df.drop_duplicates()
        
        # 기간 필터링
        combined_df = combined_df[(combined_df.index >= start_dt) & (combined_df.index <= end_dt)]
        
        print(f"✅ 전체 데이터 로드 완료: {len(combined_df)}개 캔들")
        print(f"📅 기간: {combined_df.index[0]} ~ {combined_df.index[-1]}")
        
        return combined_df
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표 계산"""
        print("🔧 기술적 지표 계산 중...")
        
        # 이동평균선
        df['ma_5'] = df['close'].rolling(5).mean()
        df['ma_10'] = df['close'].rolling(10).mean()
        df['ma_20'] = df['close'].rolling(20).mean()
        df['ma_50'] = df['close'].rolling(50).mean()
        df['ma_200'] = df['close'].rolling(200).mean()
        
        # ATR (Average True Range)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        df['atr'] = true_range.rolling(14).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['close'].ewm(span=12).mean()
        exp2 = df['close'].ewm(span=26).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # 볼린저 밴드
        df['bb_middle'] = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # 스토캐스틱
        low_14 = df['low'].rolling(14).min()
        high_14 = df['high'].rolling(14).max()
        df['stoch_k'] = 100 * (df['close'] - low_14) / (high_14 - low_14)
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()
        
        # 모멘텀 지표
        df['momentum_5'] = df['close'].pct_change(5)
        df['momentum_10'] = df['close'].pct_change(10)
        df['momentum_20'] = df['close'].pct_change(20)
        
        # 변동성 지표
        df['volatility'] = df['close'].rolling(20).std()
        df['volatility_ratio'] = df['volatility'] / df['volatility'].rolling(50).mean()
        
        # 거래량 지표
        df['volume_ma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # 가격 채널 (지지/저항)
        df['high_20'] = df['high'].rolling(20).max()
        df['low_20'] = df['low'].rolling(20).min()
        df['price_channel_position'] = (df['close'] - df['low_20']) / (df['high_20'] - df['low_20'])
        
        print("✅ 기술적 지표 계산 완료")
        return df
    
    def volatility_breakout_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        """변동성 돌파 전략"""
        print("📈 변동성 돌파 전략 실행 중...")
        
        # 변동성 돌파 신호 생성
        df['volatility_signal'] = 0
        
        # 상승 돌파: 전일 고가 + ATR * k
        df['breakout_upper'] = df['high'].shift(1) + df['atr'].shift(1) * 0.5
        df['breakout_lower'] = df['low'].shift(1) - df['atr'].shift(1) * 0.5
        
        # 진입 신호
        long_condition = (df['close'] > df['breakout_upper']) & (df['volume_ratio'] > 1.2)
        short_condition = (df['close'] < df['breakout_lower']) & (df['volume_ratio'] > 1.2)
        
        df.loc[long_condition, 'volatility_signal'] = 1
        df.loc[short_condition, 'volatility_signal'] = -1
        
        # 청산 신호 (ATR 기반 손절/익절)
        df['volatility_exit'] = 0
        
        return df
    
    def momentum_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        """모멘텀 전략"""
        print("📈 모멘텀 전략 실행 중...")
        
        # 모멘텀 신호 생성
        df['momentum_signal'] = 0
        
        # MA 크로스오버 + 모멘텀 조건
        ma_cross_up = (df['ma_5'] > df['ma_20']) & (df['ma_5'].shift(1) <= df['ma_20'].shift(1))
        ma_cross_down = (df['ma_5'] < df['ma_20']) & (df['ma_5'].shift(1) >= df['ma_20'].shift(1))
        
        # 모멘텀 조건
        momentum_up = (df['momentum_5'] > 0) & (df['momentum_10'] > 0) & (df['rsi'] > 50)
        momentum_down = (df['momentum_5'] < 0) & (df['momentum_10'] < 0) & (df['rsi'] < 50)
        
        # 진입 신호
        long_condition = ma_cross_up & momentum_up & (df['volume_ratio'] > 1.1)
        short_condition = ma_cross_down & momentum_down & (df['volume_ratio'] > 1.1)
        
        df.loc[long_condition, 'momentum_signal'] = 1
        df.loc[short_condition, 'momentum_signal'] = -1
        
        return df
    
    def swing_trading_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        """스윙 트레이딩 전략"""
        print("📈 스윙 트레이딩 전략 실행 중...")
        
        # 스윙 신호 생성
        df['swing_signal'] = 0
        
        # 추세 확인 (200MA)
        uptrend = df['close'] > df['ma_200']
        downtrend = df['close'] < df['ma_200']
        
        # 스윙 진입 조건
        swing_long = (df['ma_10'] > df['ma_50']) & (df['close'] > df['ma_10']) & uptrend & (df['rsi'] < 70)
        swing_short = (df['ma_10'] < df['ma_50']) & (df['close'] < df['ma_10']) & downtrend & (df['rsi'] > 30)
        
        df.loc[swing_long, 'swing_signal'] = 1
        df.loc[swing_short, 'swing_signal'] = -1
        
        return df
    
    def breakout_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        """브레이크아웃 전략"""
        print("📈 브레이크아웃 전략 실행 중...")
        
        # 브레이크아웃 신호 생성
        df['breakout_signal'] = 0
        
        # 지지/저항선 계산
        df['resistance'] = df['high'].rolling(20).max()
        df['support'] = df['low'].rolling(20).min()
        
        # 브레이크아웃 조건
        resistance_break = (df['close'] > df['resistance'].shift(1)) & (df['volume_ratio'] > 1.5)
        support_break = (df['close'] < df['support'].shift(1)) & (df['volume_ratio'] > 1.5)
        
        df.loc[resistance_break, 'breakout_signal'] = 1
        df.loc[support_break, 'breakout_signal'] = -1
        
        return df
    
    def scalping_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        """스캘핑 전략"""
        print("📈 스캘핑 전략 실행 중...")
        
        # 스캘핑 신호 생성
        df['scalping_signal'] = 0
        
        # 단기 신호 (1분봉 기준)
        # RSI 과매도/과매수 반전
        rsi_oversold = (df['rsi'] < 30) & (df['rsi'].shift(1) >= 30)
        rsi_overbought = (df['rsi'] > 70) & (df['rsi'].shift(1) <= 70)
        
        # 볼린저 밴드 반전
        bb_oversold = (df['close'] < df['bb_lower']) & (df['close'].shift(1) >= df['bb_lower'].shift(1))
        bb_overbought = (df['close'] > df['bb_upper']) & (df['close'].shift(1) <= df['bb_upper'].shift(1))
        
        # 스토캐스틱 반전
        stoch_oversold = (df['stoch_k'] < 20) & (df['stoch_k'].shift(1) >= 20)
        stoch_overbought = (df['stoch_k'] > 80) & (df['stoch_k'].shift(1) <= 80)
        
        # 진입 조건 (여러 조건 중 하나라도 만족)
        long_condition = (rsi_oversold | bb_oversold | stoch_oversold) & (df['volume_ratio'] > 1.0)
        short_condition = (rsi_overbought | bb_overbought | stoch_overbought) & (df['volume_ratio'] > 1.0)
        
        df.loc[long_condition, 'scalping_signal'] = 1
        df.loc[short_condition, 'scalping_signal'] = -1
        
        return df
    
    def run_backtest(self, df: pd.DataFrame, strategy_name: str) -> Dict:
        """백테스트 실행"""
        print(f"🚀 {strategy_name} 백테스트 실행 중...")
        
        # 전략별 신호 생성
        if strategy_name == 'volatility':
            df = self.volatility_breakout_strategy(df)
            signal_col = 'volatility_signal'
        elif strategy_name == 'momentum':
            df = self.momentum_strategy(df)
            signal_col = 'momentum_signal'
        elif strategy_name == 'swing':
            df = self.swing_trading_strategy(df)
            signal_col = 'swing_signal'
        elif strategy_name == 'breakout':
            df = self.breakout_strategy(df)
            signal_col = 'breakout_signal'
        elif strategy_name == 'scalping':
            df = self.scalping_strategy(df)
            signal_col = 'scalping_signal'
        else:
            raise ValueError(f"지원하지 않는 전략: {strategy_name}")
        
        # 백테스트 실행
        position = 0  # 0: 없음, 1: 롱, -1: 숏
        entry_price = 0
        entry_time = None
        stop_loss = 0
        take_profit = 0
        
        trades = []
        equity_curve = []
        
        for i in range(len(df)):
            current_time = df.index[i]
            current_price = df['close'].iloc[i]
            signal = df[signal_col].iloc[i]
            
            # 포지션이 없는 경우
            if position == 0:
                if signal == 1:  # 롱 진입
                    position = 1
                    entry_price = current_price
                    entry_time = current_time
                    stop_loss = entry_price * (1 - 0.02)  # 2% 손절
                    take_profit = entry_price * (1 + 0.04)  # 4% 익절
                    
                elif signal == -1:  # 숏 진입
                    position = -1
                    entry_price = current_price
                    entry_time = current_time
                    stop_loss = entry_price * (1 + 0.02)  # 2% 손절
                    take_profit = entry_price * (1 - 0.04)  # 4% 익절
            
            # 포지션이 있는 경우
            else:
                # 손절/익절 체크
                if position == 1:  # 롱 포지션
                    if current_price <= stop_loss:
                        # 손절
                        pnl = (current_price - entry_price) / entry_price * self.leverage * (1 - self.fee)
                        self.current_capital *= (1 + pnl)
                        
                        trades.append({
                            'type': 'LONG_LOSS',
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'pnl': pnl,
                            'return_pct': pnl * 100
                        })
                        
                        position = 0
                        
                    elif current_price >= take_profit:
                        # 익절
                        pnl = (current_price - entry_price) / entry_price * self.leverage * (1 - self.fee)
                        self.current_capital *= (1 + pnl)
                        
                        trades.append({
                            'type': 'LONG_PROFIT',
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'pnl': pnl,
                            'return_pct': pnl * 100
                        })
                        
                        position = 0
                
                elif position == -1:  # 숏 포지션
                    if current_price >= stop_loss:
                        # 손절
                        pnl = (entry_price - current_price) / entry_price * self.leverage * (1 - self.fee)
                        self.current_capital *= (1 + pnl)
                        
                        trades.append({
                            'type': 'SHORT_LOSS',
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'pnl': pnl,
                            'return_pct': pnl * 100
                        })
                        
                        position = 0
                        
                    elif current_price <= take_profit:
                        # 익절
                        pnl = (entry_price - current_price) / entry_price * self.leverage * (1 - self.fee)
                        self.current_capital *= (1 + pnl)
                        
                        trades.append({
                            'type': 'SHORT_PROFIT',
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'pnl': pnl,
                            'return_pct': pnl * 100
                        })
                        
                        position = 0
            
            # 자산 곡선 기록
            equity_curve.append({
                'time': current_time,
                'equity': self.current_capital,
                'price': current_price,
                'position': position
            })
        
        # 마지막 포지션 청산
        if position != 0:
            final_price = df['close'].iloc[-1]
            if position == 1:
                pnl = (final_price - entry_price) / entry_price * self.leverage * (1 - self.fee)
            else:
                pnl = (entry_price - final_price) / entry_price * self.leverage * (1 - self.fee)
            
            self.current_capital *= (1 + pnl)
            
            trades.append({
                'type': 'FINAL_EXIT',
                'entry_time': entry_time,
                'exit_time': df.index[-1],
                'entry_price': entry_price,
                'exit_price': final_price,
                'pnl': pnl,
                'return_pct': pnl * 100
            })
        
        # 성과 계산
        total_return = (self.current_capital - self.initial_capital) / self.initial_capital * 100
        
        # MDD 계산
        peak = self.initial_capital
        mdd = 0
        for point in equity_curve:
            if point['equity'] > peak:
                peak = point['equity']
            drawdown = (peak - point['equity']) / peak * 100
            if drawdown > mdd:
                mdd = drawdown
        
        # 거래 통계
        profitable_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] < 0]
        
        win_rate = len(profitable_trades) / len(trades) * 100 if trades else 0
        avg_profit = np.mean([t['pnl'] for t in profitable_trades]) * 100 if profitable_trades else 0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) * 100 if losing_trades else 0
        
        result = {
            'strategy': strategy_name,
            'total_return': total_return,
            'final_capital': self.current_capital,
            'mdd': mdd,
            'trades': trades,
            'equity_curve': equity_curve,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'total_trades': len(trades),
            'profitable_trades': len(profitable_trades),
            'losing_trades': len(losing_trades)
        }
        
        return result
    
    def create_visualization(self, result: Dict, df: pd.DataFrame, strategy_name: str, save_path: str):
        """시각화 생성"""
        print(f"📊 {strategy_name} 시각화 생성 중...")
        
        fig, axes = plt.subplots(4, 1, figsize=(20, 16))
        
        # 1. 가격 차트 + 거래 신호
        ax1 = axes[0]
        ax1.plot(df.index, df['close'], 'k-', linewidth=1, alpha=0.8, label='BTC Price')
        
        # 거래 내역 표시
        for trade in result['trades']:
            if 'LONG' in trade['type']:
                ax1.scatter(trade['entry_time'], trade['entry_price'], color='green', marker='^', s=100, alpha=0.8)
                ax1.scatter(trade['exit_time'], trade['exit_price'], color='red', marker='v', s=100, alpha=0.8)
            else:
                ax1.scatter(trade['entry_time'], trade['entry_price'], color='red', marker='v', s=100, alpha=0.8)
                ax1.scatter(trade['exit_time'], trade['exit_price'], color='green', marker='^', s=100, alpha=0.8)
        
        ax1.set_title(f'{strategy_name.upper()} 전략 - 가격 차트 및 거래 신호', fontsize=14, fontweight='bold')
        ax1.set_ylabel('가격 (USDT)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. 자산 곡선
        ax2 = axes[1]
        times = [point['time'] for point in result['equity_curve']]
        equities = [point['equity'] for point in result['equity_curve']]
        
        ax2.plot(times, equities, 'b-', linewidth=2, label='자산 곡선')
        ax2.axhline(y=self.initial_capital, color='black', linestyle='--', alpha=0.7, label='초기 자본')
        
        ax2.set_title('자산 곡선', fontsize=14, fontweight='bold')
        ax2.set_ylabel('자산 (USDT)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. 거래별 수익률
        ax3 = axes[2]
        if result['trades']:
            trade_returns = [trade['return_pct'] for trade in result['trades']]
            colors = ['green' if ret > 0 else 'red' for ret in trade_returns]
            
            bars = ax3.bar(range(len(trade_returns)), trade_returns, color=colors, alpha=0.7)
            
            # 수익률 값 표시
            for i, (bar, ret) in enumerate(zip(bars, trade_returns)):
                height = bar.get_height()
                ax3.text(bar.get_x() + bar.get_width()/2., height + (0.1 if height > 0 else -0.1),
                        f'{ret:.1f}%', ha='center', va='bottom' if height > 0 else 'top', fontsize=8)
        
        ax3.set_title('거래별 수익률', fontsize=14, fontweight='bold')
        ax3.set_ylabel('수익률 (%)')
        ax3.set_xlabel('거래 순서')
        ax3.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax3.grid(True, alpha=0.3)
        
        # 4. MDD
        ax4 = axes[3]
        if result['equity_curve']:
            peak = self.initial_capital
            mdd_values = []
            
            for point in result['equity_curve']:
                if point['equity'] > peak:
                    peak = point['equity']
                drawdown = (peak - point['equity']) / peak * 100
                mdd_values.append(drawdown)
            
            ax4.fill_between(times, mdd_values, 0, alpha=0.3, color='red', label='MDD')
            ax4.plot(times, mdd_values, 'r-', linewidth=1, alpha=0.8)
            
            # 최대 MDD 표시
            max_mdd = max(mdd_values)
            max_mdd_idx = mdd_values.index(max_mdd)
            ax4.scatter(times[max_mdd_idx], max_mdd, color='darkred', s=100, zorder=5,
                       label=f'최대 MDD: {max_mdd:.2f}%')
        
        ax4.set_title('MDD (Maximum Drawdown)', fontsize=14, fontweight='bold')
        ax4.set_ylabel('MDD (%)')
        ax4.set_xlabel('시간')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        ax4.invert_yaxis()
        
        # x축 날짜 포맷
        for ax in axes:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=7))
            ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ 시각화 저장 완료: {save_path}")

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='비트코인 선물 백테스트 시스템')
    parser.add_argument('--strategy', choices=['volatility', 'momentum', 'swing', 'breakout', 'scalping'], 
                       default='volatility', help='백테스트할 전략 선택')
    parser.add_argument('--period', choices=['1m', '5m', '15m', '1h', '4h', '1d'], 
                       default='1h', help='시간프레임 선택')
    parser.add_argument('--start', default='2024-01-01', help='시작 날짜 (YYYY-MM-DD)')
    parser.add_argument('--end', default='2024-12-31', help='종료 날짜 (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=10000, help='초기 자본')
    parser.add_argument('--leverage', type=float, default=10, help='레버리지')
    
    args = parser.parse_args()
    
    print("🚀 비트코인 선물 백테스트 시스템 시작!")
    print("=" * 60)
    print(f"📊 전략: {args.strategy}")
    print(f"⏰ 시간프레임: {args.period}")
    print(f"📅 기간: {args.start} ~ {args.end}")
    print(f"💰 초기 자본: {args.capital:,} USDT")
    print(f"⚡ 레버리지: {args.leverage}배")
    
    # 백테스터 생성
    backtester = BitcoinFuturesBacktester(
        initial_capital=args.capital,
        leverage=args.leverage
    )
    
    try:
        # 데이터 로드
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        df = backtester.load_data(data_dir, args.start, args.end, args.period)
        
        # 기술적 지표 계산
        df = backtester.calculate_technical_indicators(df)
        
        # 백테스트 실행
        result = backtester.run_backtest(df, args.strategy)
        
        # 결과 출력
        print("\n" + "=" * 60)
        print("📈 백테스트 결과")
        print("=" * 60)
        print(f"📊 전략: {result['strategy'].upper()}")
        print(f"💰 최종 자본: {result['final_capital']:,.2f} USDT")
        print(f"📈 총 수익률: {result['total_return']:.2f}%")
        print(f"📉 최대 MDD: {result['mdd']:.2f}%")
        print(f"🔄 총 거래 수: {result['total_trades']}회")
        print(f"✅ 수익 거래: {result['profitable_trades']}회")
        print(f"❌ 손실 거래: {result['losing_trades']}회")
        print(f"🎯 승률: {result['win_rate']:.1f}%")
        print(f"📈 평균 수익: {result['avg_profit']:.2f}%")
        print(f"📉 평균 손실: {result['avg_loss']:.2f}%")
        
        # 결과 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = os.path.join(os.path.dirname(__file__), 'logs')
        os.makedirs(result_dir, exist_ok=True)
        
        # JSON 결과 저장
        result_file = os.path.join(result_dir, f"{args.strategy}_backtest_{timestamp}.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        # 시각화 저장
        graph_file = os.path.join(result_dir, f"{args.strategy}_backtest_{timestamp}.png")
        backtester.create_visualization(result, df, args.strategy, graph_file)
        
        print(f"\n💾 결과 저장 완료:")
        print(f"📄 JSON: {result_file}")
        print(f"📊 그래프: {graph_file}")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
