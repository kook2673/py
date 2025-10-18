# -*- coding: utf-8 -*-
"""
순차적 확장 백테스트 스크립트
- Profitable_Results_Sorted.csv의 순서대로 전략들을 테스트
- 2025년 1월부터 7월까지 각 전략별로 백테스트 수행
- 결과를 순서대로 정리하여 저장

사용법:
  python sequential_backtest.py
"""

import os
import glob
import pandas as pd
import json
from datetime import datetime
from Scalp_1m_5MA20MA_Backtest import backtest

class SequentialBacktester:
    """순차적 확장 백테스트 클래스"""
    
    def __init__(self, max_strategies=10):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.script_dir, 'data', 'BTC_USDT', '1m')
        self.results_dir = os.path.join(self.script_dir, 'logs', 'sequential_backtest')
        
        # 백테스트 설정
        self.backtest_config = {
            'fee': 0.0005,
            'leverage': 10,
            'volume_window': 20,
            'risk_fraction': 1.0
        }
        
        # 확장 기간 설정
        self.periods = [
            '2025-01', '2025-02', '2025-03', '2025-04',
            '2025-05', '2025-06', '2025-07'
        ]
        
        # 최대 테스트할 전략 수
        self.max_strategies = max_strategies
        
        os.makedirs(self.results_dir, exist_ok=True)
        
        print(f"✅ 순차적 백테스트 준비 완료 (최대 {max_strategies}개 전략)")
    
    def load_profitable_strategies(self):
        """수익률 양수 전략 목록 로드"""
        try:
            csv_path = os.path.join(self.script_dir, 'logs', 'Profitable_Results_Sorted.csv')
            if not os.path.exists(csv_path):
                print(f"❌ 수익률 양수 결과 파일을 찾을 수 없습니다: {csv_path}")
                return []
            
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            print(f"✅ {len(df):,}개 수익률 양수 전략 로드 완료")
            
            # 상위 전략만 선택
            top_strategies = df.head(self.max_strategies)
            print(f"📊 상위 {len(top_strategies)}개 전략 선택됨")
            
            return top_strategies.to_dict('records')
            
        except Exception as e:
            print(f"❌ 전략 로드 실패: {e}")
            return []
    
    def parse_strategy_key(self, key):
        """전략 키를 파라미터로 파싱"""
        try:
            # 예: f17_s35_sl0.0015_vm1.2_mfc2_tfm5
            parts = key.split('_')
            
            strategy = {
                'fast_ma': int(parts[0][1:]),  # f17 -> 17
                'slow_ma': int(parts[1][1:]),  # s35 -> 35
                'stop_loss_pct': float(parts[2][2:]),  # sl0.0015 -> 0.0015
                'volume_multiplier': float(parts[3][2:]),  # vm1.2 -> 1.2
                'min_pass_filters': int(parts[4][3:]),  # mfc2 -> 2
                'timeframe_minutes': int(parts[5][3:])  # tfm5 -> 5
            }
            
            return strategy
            
        except Exception as e:
            print(f"❌ 전략 키 파싱 실패: {key} - {e}")
            return None
    
    def load_monthly_data(self, month_pattern):
        """월별 데이터 로드"""
        try:
            files = glob.glob(os.path.join(self.data_dir, f'{month_pattern}.csv'))
            if not files:
                print(f"⚠️ {month_pattern} 데이터 파일을 찾을 수 없습니다.")
                return None
            
            dfs = []
            for f in sorted(files):
                df = pd.read_csv(f, index_col='timestamp', parse_dates=True)
                dfs.append(df)
            
            if not dfs:
                return None
            
            combined_df = pd.concat(dfs).sort_index().drop_duplicates()
            print(f"✅ {month_pattern}: {len(combined_df):,}개 데이터 로드 완료")
            return combined_df
            
        except Exception as e:
            print(f"❌ {month_pattern} 데이터 로드 실패: {e}")
            return None
    
    def run_strategy_backtest(self, strategy_data, month_pattern, data_df):
        """단일 전략 백테스트 실행"""
        try:
            # 전략 파라미터 파싱
            strategy_params = self.parse_strategy_key(strategy_data['key'])
            if strategy_params is None:
                return None
            
            print(f"🔄 {month_pattern} 백테스트 실행 중... ({strategy_data['key']})")
            
            result = backtest(
                data_df,
                stop_loss_pct=strategy_params['stop_loss_pct'],
                fee=self.backtest_config['fee'],
                leverage=self.backtest_config['leverage'],
                volume_window=self.backtest_config['volume_window'],
                volume_multiplier=strategy_params['volume_multiplier'],
                min_pass_filters=strategy_params['min_pass_filters'],
                risk_fraction=self.backtest_config['risk_fraction'],
                fast_ma_window=strategy_params['fast_ma'],
                slow_ma_window=strategy_params['slow_ma'],
                timeframe_minutes=strategy_params['timeframe_minutes'],
            )
            
            # 결과 정리
            backtest_result = {
                'strategy_key': strategy_data['key'],
                'month': month_pattern,
                'data_points': len(data_df),
                'total_return': result['total_return'],
                'mdd': result['mdd'],
                'final_capital': result['final_capital'],
                'trades': len([t for t in result['trades'] if t['type'] != 'LONG_ENTRY']),
                'win_rate': self.calculate_win_rate(result['trades']),
                'avg_trade_return': self.calculate_avg_trade_return(result['trades']),
                'max_consecutive_losses': self.calculate_max_consecutive_losses(result['trades']),
                'sharpe_ratio': self.calculate_sharpe_ratio(result['trades']),
                'original_return': strategy_data['total_return'],
                'performance_vs_original': result['total_return'] - strategy_data['total_return'],
                'backtest_time': datetime.now().isoformat()
            }
            
            print(f"✅ {month_pattern} 완료: {backtest_result['total_return']:+.2f}% | MDD: {backtest_result['mdd']:.2f}%")
            return backtest_result
            
        except Exception as e:
            print(f"❌ {month_pattern} 백테스트 실패: {e}")
            return None
    
    def calculate_win_rate(self, trades):
        """승률 계산"""
        if not trades:
            return 0.0
        
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        return len(winning_trades) / len(trades) * 100
    
    def calculate_avg_trade_return(self, trades):
        """평균 거래 수익률 계산"""
        if not trades:
            return 0.0
        
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        return total_pnl / len(trades)
    
    def calculate_max_consecutive_losses(self, trades):
        """최대 연속 손실 계산"""
        if not trades:
            return 0
        
        max_consecutive = 0
        current_consecutive = 0
        
        for trade in trades:
            if trade.get('pnl', 0) < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def calculate_sharpe_ratio(self, trades):
        """샤프 비율 계산 (간단한 버전)"""
        if not trades:
            return 0.0
        
        returns = [t.get('pnl', 0) for t in trades]
        if not returns:
            return 0.0
        
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        
        if variance == 0:
            return 0.0
        
        return avg_return / (variance ** 0.5)
    
    def run_sequential_backtest(self):
        """순차적 백테스트 실행"""
        print("🚀 순차적 확장 백테스트 시작")
        print("=" * 60)
        
        # 수익률 양수 전략 로드
        strategies = self.load_profitable_strategies()
        if not strategies:
            print("❌ 테스트할 전략이 없습니다.")
            return
        
        all_results = []
        available_months = []
        
        # 각 전략별로 월별 백테스트 실행
        for i, strategy in enumerate(strategies, 1):
            print(f"\n🎯 전략 {i}/{len(strategies)}: {strategy['key']}")
            print(f"   3월 수익률: {strategy['total_return']:+.2f}%")
            print("-" * 50)
            
            strategy_results = []
            
            for month in self.periods:
                print(f"\n📅 {month} 처리 중...")
                
                data_df = self.load_monthly_data(month)
                if data_df is not None:
                    result = self.run_strategy_backtest(strategy, month, data_df)
                    if result:
                        strategy_results.append(result)
                        if month not in available_months:
                            available_months.append(month)
                else:
                    print(f"⚠️ {month} 데이터 없음 - 건너뜀")
            
            all_results.extend(strategy_results)
            
            # 중간 결과 저장
            if i % 5 == 0 or i == len(strategies):
                self.save_intermediate_results(all_results, i, len(strategies))
        
        if not all_results:
            print("❌ 백테스트 결과가 없습니다.")
            return
        
        # 최종 결과 저장 및 분석
        self.save_final_results(all_results, available_months)
        self.analyze_results(all_results, strategies)
    
    def save_intermediate_results(self, results, current, total):
        """중간 결과 저장"""
        try:
            csv_path = os.path.join(self.results_dir, f'sequential_backtest_intermediate_{current}.csv')
            df_results = pd.DataFrame(results)
            df_results.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"\n💾 중간 결과 저장 완료: {csv_path} ({current}/{total})")
            
        except Exception as e:
            print(f"⚠️ 중간 결과 저장 실패: {e}")
    
    def save_final_results(self, results, available_months):
        """최종 결과 저장"""
        try:
            # CSV 저장
            csv_path = os.path.join(self.results_dir, 'sequential_backtest_final_results.csv')
            df_results = pd.DataFrame(results)
            df_results.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"\n💾 최종 CSV 저장 완료: {csv_path}")
            
            # JSON 저장
            json_path = os.path.join(self.results_dir, 'sequential_backtest_final_results.json')
            summary = {
                'total_strategies': len(set(r['strategy_key'] for r in results)),
                'total_results': len(results),
                'available_months': available_months,
                'total_months': len(available_months),
                'results': results,
                'summary': {
                    'avg_return': sum(r['total_return'] for r in results) / len(results),
                    'max_return': max(r['total_return'] for r in results),
                    'min_return': min(r['total_return'] for r in results),
                    'avg_mdd': sum(r['mdd'] for r in results) / len(results),
                    'total_trades': sum(r['trades'] for r in results)
                },
                'generated_time': datetime.now().isoformat()
            }
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            print(f"💾 최종 JSON 저장 완료: {json_path}")
            
        except Exception as e:
            print(f"⚠️ 최종 결과 저장 실패: {e}")
    
    def analyze_results(self, results, original_strategies):
        """결과 분석"""
        print(f"\n📊 순차적 백테스트 결과 분석:")
        print("=" * 60)
        
        # 전략별 성과 요약
        strategy_summary = {}
        for result in results:
            strategy_key = result['strategy_key']
            if strategy_key not in strategy_summary:
                strategy_summary[strategy_key] = {
                    'months': 0,
                    'total_return': 0,
                    'avg_return': 0,
                    'max_mdd': 0,
                    'total_trades': 0,
                    'original_return': result['original_return']
                }
            
            summary = strategy_summary[strategy_key]
            summary['months'] += 1
            summary['total_return'] += result['total_return']
            summary['max_mdd'] = max(summary['max_mdd'], result['mdd'])
            summary['total_trades'] += result['trades']
        
        # 평균 계산
        for strategy_key, summary in strategy_summary.items():
            summary['avg_return'] = summary['total_return'] / summary['months']
        
        # 성과 순위 (평균 수익률 기준)
        sorted_strategies = sorted(strategy_summary.items(), key=lambda x: x[1]['avg_return'], reverse=True)
        
        print(f"\n🏆 전략별 성과 순위 (2025년 1-7월 평균):")
        print("=" * 80)
        print(f"{'순위':<4} {'전략키':<35} {'3월수익률':<10} {'평균수익률':<10} {'최대MDD':<8} {'총거래수':<8}")
        print("-" * 80)
        
        for i, (strategy_key, summary) in enumerate(sorted_strategies, 1):
            print(f"{i:2d}.  {strategy_key:<35} {summary['original_return']:+8.2f}% {summary['avg_return']:+8.2f}% {summary['max_mdd']:6.2f}% {summary['total_trades']:8d}")
        
        print("-" * 80)
        
        # 최고 성과 전략
        best_strategy = sorted_strategies[0]
        print(f"\n🥇 최고 성과 전략: {best_strategy[0]}")
        print(f"   3월 수익률: {best_strategy[1]['original_return']:+.2f}%")
        print(f"   1-7월 평균: {best_strategy[1]['avg_return']:+.2f}%")
        print(f"   최대 MDD: {best_strategy[1]['max_mdd']:.2f}%")
        print(f"   총 거래 수: {best_strategy[1]['total_trades']:,}개")

def main():
    """메인 실행 함수"""
    print("🚀 순차적 확장 백테스트 시작")
    print("=" * 50)
    
    # 상위 10개 전략으로 백테스트 실행
    backtester = SequentialBacktester(max_strategies=10)
    backtester.run_sequential_backtest()

if __name__ == '__main__':
    main()
