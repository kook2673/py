"""
다중 코인 백테스트 스크립트
- 비트코인, 이더리움, 도지, 솔라나, XRP
- 2024년, 2025년 1분봉 데이터 사용
- 동적 트레일링스탑 적용
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from trend_dc_bot import BTCTrendFollowingBotOptimized

class MultiCoinBacktest:
    """다중 코인 백테스트 클래스"""
    
    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        self.results = {}
        
        # 테스트할 코인 목록
        self.coins = ['BTCUSDT', 'ETHUSDT', 'DOGEUSDT', 'SOLUSDT', 'XRPUSDT']
        
        # 테스트할 연도
        self.years = [2024, 2025]
        
        # 데이터 디렉토리
        self.data_dir = "data"
        
        # 시간프레임 설정 (모든 코인을 1분봉으로 설정)
        self.timeframes = {
            'BTCUSDT': '1m',  # BTC는 1분봉
            'ETHUSDT': '1m',  # ETH도 1분봉
            'DOGEUSDT': '1m', # DOGE도 1분봉
            'SOLUSDT': '1m',  # SOL도 1분봉
            'XRPUSDT': '1m'   # XRP도 1분봉
        }
        
    def load_coin_data(self, coin, year):
        """특정 코인의 연도별 데이터 로드"""
        # 코인별 시간프레임 결정
        timeframe = self.timeframes.get(coin, '1m')
        data_dir = f"{self.data_dir}/{coin}/{timeframe}"
        
        if not os.path.exists(data_dir):
            print(f"데이터 디렉토리가 없습니다: {data_dir}")
            return None
        
        # 데이터 파일 찾기
        file_name = f"{coin}_{timeframe}_{year}.csv"
        file_path = os.path.join(data_dir, file_name)
        
        if not os.path.exists(file_path):
            print(f"{coin} {year}년 데이터 파일이 없습니다: {file_path}")
            return None
        
        print(f"{coin} {year}년 데이터 로드 중... ({timeframe}봉)")
        
        try:
            # 파일 읽기
            data = pd.read_csv(file_path)
            
            # 컬럼명 정리
            data.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            
            # 타임스탬프를 datetime으로 변환
            data['timestamp'] = pd.to_datetime(data['timestamp'])
            data = data.set_index('timestamp')
            
            # 중복 제거 및 정렬
            data = data.drop_duplicates().sort_index()
            
            print(f"{coin} {year}년 데이터 로드 완료: {len(data):,}개 캔들 ({timeframe}봉)")
            print(f"전체 기간: {data.index[0]} ~ {data.index[-1]}")
            
            return data
            
        except Exception as e:
            print(f"파일 읽기 오류: {e}")
            return None
    
    def run_single_test(self, coin, year):
        """단일 코인/연도 테스트 실행"""
        print(f"\n{'='*80}")
        print(f"{coin} {year}년 백테스트 시작")
        print(f"{'='*80}")
        
        # 봇 초기화
        bot = BTCTrendFollowingBotOptimized(initial_capital=self.initial_capital)
        
        # 데이터 로드
        data = self.load_coin_data(coin, year)
        if data is None:
            print(f"{coin} {year}년 데이터 로드 실패")
            return None
        
        # 기술적 지표 계산
        print("기술적 지표 계산 중...")
        data_with_indicators = bot.calculate_indicators(data)
        
        # 신호 생성
        print("신호 생성 중...")
        data_with_signals = bot.get_signals_vectorized(data_with_indicators)
        
        # 백테스팅 실행
        trades = bot.backtest_vectorized(data_with_signals)
        
        # 성과 계산
        total_return = (bot.current_capital - bot.initial_capital) / bot.initial_capital * 100
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t['pnl'] > 0])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        # 최대 낙폭 계산
        capital_series = [bot.initial_capital]
        for trade in trades:
            capital_series.append(capital_series[-1] + trade['pnl'])
        
        peak = capital_series[0]
        max_dd = 0
        for capital in capital_series:
            if capital > peak:
                peak = capital
            dd = (peak - capital) / peak
            if dd > max_dd:
                max_dd = dd
        
        # 총 수수료
        total_fees = sum(t['entry_fee'] + t['exit_fee'] for t in trades)
        
        # 평균 보유 시간
        durations = []
        for trade in trades:
            # 진입 거래는 제외 (exit_time이 None)
            if trade['exit_time'] is None:
                continue
                
            if isinstance(trade['entry_time'], int):
                entry_time = pd.to_datetime(trade['entry_time'], unit='s')
            else:
                entry_time = trade['entry_time']
            if isinstance(trade['exit_time'], int):
                exit_time = pd.to_datetime(trade['exit_time'], unit='s')
            else:
                exit_time = trade['exit_time']
            duration = (exit_time - entry_time).total_seconds() / 3600  # 시간 단위
            durations.append(duration)
        
        avg_duration = np.mean(durations) if durations else 0
        
        # 결과 저장
        result = {
            'coin': coin,
            'year': year,
            'initial_capital': bot.initial_capital,
            'final_capital': bot.current_capital,
            'total_return': total_return,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': win_rate,
            'max_drawdown': max_dd * 100,
            'total_fees': total_fees,
            'avg_duration_hours': avg_duration,
            'trades': trades
        }
        
        # 성과 출력
        print(f"\n{coin} {year}년 백테스트 결과:")
        print("-" * 60)
        print(f"초기 자본: ${bot.initial_capital:,.2f}")
        print(f"최종 자본: ${bot.current_capital:,.2f}")
        print(f"총 수익률: {total_return:.2f}%")
        print(f"총 거래 수: {total_trades}회")
        print(f"승률: {win_rate:.1f}%")
        print(f"최대 낙폭: -{max_dd*100:.2f}%")
        print(f"총 수수료: ${total_fees:.2f}")
        print(f"평균 보유 시간: {avg_duration:.1f}시간")
        
        return result
    
    def run_all_tests(self):
        """모든 코인/연도 조합 테스트 실행"""
        print("=" * 100)
        print("다중 코인 백테스트 시작")
        print("=" * 100)
        print(f"테스트 코인: {', '.join(self.coins)}")
        print(f"테스트 연도: {', '.join(map(str, self.years))}")
        print(f"초기 자본: ${self.initial_capital:,}")
        print("=" * 100)
        
        all_results = {}
        
        for coin in self.coins:
            all_results[coin] = {}
            
            for year in self.years:
                try:
                    result = self.run_single_test(coin, year)
                    if result:
                        all_results[coin][year] = result
                        
                        # 결과를 개별 파일로 저장
                        filename = f'backtest_results_{coin}_{year}.json'
                        with open(filename, 'w', encoding='utf-8') as f:
                            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
                        print(f"결과가 '{filename}'에 저장되었습니다.")
                        
                except Exception as e:
                    print(f"❌ {coin} {year}년 테스트 실패: {e}")
                    continue
        
        # 전체 결과 저장
        filename = f'multi_coin_backtest_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
        
        # 전체 결과 요약 출력
        self.print_summary(all_results)
        
        return all_results
    
    def print_summary(self, all_results):
        """전체 결과 요약 출력"""
        print("\n" + "=" * 100)
        print("전체 백테스트 결과 요약")
        print("=" * 100)
        
        # 코인별 요약
        for coin in self.coins:
            if coin in all_results:
                print(f"\n{coin} 결과:")
                print("-" * 50)
                
                coin_returns = []
                for year in self.years:
                    if year in all_results[coin]:
                        result = all_results[coin][year]
                        print(f"{year}년: {result['total_return']:.2f}% (거래 {result['total_trades']}회, 승률 {result['win_rate']:.1f}%)")
                        coin_returns.append(result['total_return'])
                
                if coin_returns:
                    avg_return = np.mean(coin_returns)
                    print(f"평균 수익률: {avg_return:.2f}%")
        
        # 연도별 요약
        print(f"\n연도별 요약:")
        print("-" * 50)
        
        for year in self.years:
            year_returns = []
            for coin in self.coins:
                if coin in all_results and year in all_results[coin]:
                    year_returns.append(all_results[coin][year]['total_return'])
            
            if year_returns:
                avg_return = np.mean(year_returns)
                print(f"{year}년 평균: {avg_return:.2f}% ({len(year_returns)}개 코인)")
        
        # 최고/최저 성과
        all_returns = []
        for coin in all_results:
            for year in all_results[coin]:
                all_returns.append((coin, year, all_results[coin][year]['total_return']))
        
        if all_returns:
            best = max(all_returns, key=lambda x: x[2])
            worst = min(all_returns, key=lambda x: x[2])
            
            print(f"\n최고 성과: {best[0]} {best[1]}년 ({best[2]:.2f}%)")
            print(f"최저 성과: {worst[0]} {worst[1]}년 ({worst[2]:.2f}%)")

def main():
    """메인 실행 함수"""
    print("다중 코인 백테스트 시작")
    
    # 백테스트 실행
    backtest = MultiCoinBacktest(initial_capital=10000)
    results = backtest.run_all_tests()
    
    print("\n모든 백테스트 완료!")
    print("개별 결과 파일과 전체 요약 파일이 생성되었습니다.")

if __name__ == "__main__":
    main()
