#-*-coding:utf-8 -*-
'''
비트코인 선물 모든 전략 백테스트 실행 스크립트
==========================================

=== 지원 전략 ===
1. 변동성 돌파 전략 (Volatility Breakout)
2. 모멘텀 전략 (Momentum Strategy)  
3. 스윙 트레이딩 (Swing Trading)
4. 브레이크아웃 전략 (Breakout Strategy)
5. 스캘핑 전략 (Scalping Strategy)

=== 사용법 ===
python run_all_strategies.py --start 2024-01-01 --end 2024-12-31 --capital 10000
'''

import os
import sys

# Windows에서 이모지 출력을 위한 인코딩 설정
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# 표준 출력 인코딩 강제 설정
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

import argparse
import subprocess
import json
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

def run_strategy(strategy_name: str, start_date: str, end_date: str, capital: float):
    """개별 전략 실행"""
    print(f"\n🚀 {strategy_name} 전략 실행 중...")
    print("=" * 50)
    
    # 전략별 파라미터 설정
    strategy_params = {
        'volatility': {
            'script': 'volatility_breakout_backtest.py',
            'timeframe': '1h',
            'leverage': 10
        },
        'momentum': {
            'script': 'momentum_strategy_backtest.py',
            'timeframe': '1h',
            'leverage': 10
        },
        'swing': {
            'script': 'swing_trading_backtest.py',
            'timeframe': '4h',
            'leverage': 5
        },
        'breakout': {
            'script': 'breakout_strategy_backtest.py',
            'timeframe': '1h',
            'leverage': 10
        },
        'scalping': {
            'script': 'scalping_strategy_backtest.py',
            'timeframe': '1m',
            'leverage': 20
        }
    }
    
    if strategy_name not in strategy_params:
        print(f"❌ 지원하지 않는 전략: {strategy_name}")
        return None
    
    params = strategy_params[strategy_name]
    script_path = os.path.join(os.path.dirname(__file__), params['script'])
    
    try:
        # 환경 변수 설정
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        
        # 전략 실행
        result = subprocess.run([
            sys.executable, script_path
        ], capture_output=True, text=True, cwd=os.path.dirname(__file__), 
           encoding='utf-8', errors='replace', env=env)
        
        if result.returncode == 0:
            print(f"✅ {strategy_name} 전략 실행 완료")
            return True
        else:
            print(f"❌ {strategy_name} 전략 실행 실패:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ {strategy_name} 전략 실행 중 오류: {e}")
        return False

def collect_results():
    """결과 수집 및 분석"""
    print("\n📊 결과 수집 및 분석 중...")
    
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    if not os.path.exists(logs_dir):
        print("❌ 로그 디렉토리를 찾을 수 없습니다.")
        return None
    
    # 최신 결과 파일들 찾기
    strategy_files = {
        'volatility': None,
        'momentum': None,
        'swing': None,
        'breakout': None,
        'scalping': None
    }
    
    for file in os.listdir(logs_dir):
        if file.endswith('.json'):
            for strategy in strategy_files.keys():
                if strategy in file and strategy_files[strategy] is None:
                    strategy_files[strategy] = os.path.join(logs_dir, file)
                    break
    
    # 결과 데이터 수집
    results = {}
    for strategy, file_path in strategy_files.items():
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    results[strategy] = data
                    print(f"✅ {strategy} 결과 로드 완료")
            except Exception as e:
                print(f"❌ {strategy} 결과 로드 실패: {e}")
        else:
            print(f"⚠️ {strategy} 결과 파일을 찾을 수 없습니다.")
    
    return results

def create_comparison_chart(results: dict):
    """전략 비교 차트 생성"""
    print("📊 전략 비교 차트 생성 중...")
    
    if not results:
        print("❌ 비교할 결과가 없습니다.")
        return
    
    # 데이터 준비
    strategies = list(results.keys())
    total_returns = [results[s]['total_return'] for s in strategies]
    mdd_values = [results[s]['mdd'] for s in strategies]
    win_rates = [results[s]['win_rate'] for s in strategies]
    total_trades = [results[s]['total_trades'] for s in strategies]
    
    # 차트 생성
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    # 1. 총 수익률 비교
    ax1 = axes[0, 0]
    bars1 = ax1.bar(strategies, total_returns, color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'])
    ax1.set_title('전략별 총 수익률 비교', fontsize=14, fontweight='bold')
    ax1.set_ylabel('수익률 (%)')
    ax1.axhline(y=0, color='black', linestyle='-', alpha=0.5)
    
    # 수익률 값 표시
    for bar, value in zip(bars1, total_returns):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + (1 if height > 0 else -1),
                f'{value:.1f}%', ha='center', va='bottom' if height > 0 else 'top')
    
    # 2. 최대 MDD 비교
    ax2 = axes[0, 1]
    bars2 = ax2.bar(strategies, mdd_values, color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'])
    ax2.set_title('전략별 최대 MDD 비교', fontsize=14, fontweight='bold')
    ax2.set_ylabel('MDD (%)')
    ax2.invert_yaxis()  # MDD는 낮을수록 좋음
    
    # MDD 값 표시
    for bar, value in zip(bars2, mdd_values):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height - 0.5,
                f'{value:.1f}%', ha='center', va='top')
    
    # 3. 승률 비교
    ax3 = axes[1, 0]
    bars3 = ax3.bar(strategies, win_rates, color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'])
    ax3.set_title('전략별 승률 비교', fontsize=14, fontweight='bold')
    ax3.set_ylabel('승률 (%)')
    ax3.set_ylim(0, 100)
    
    # 승률 값 표시
    for bar, value in zip(bars3, win_rates):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{value:.1f}%', ha='center', va='bottom')
    
    # 4. 총 거래 수 비교
    ax4 = axes[1, 1]
    bars4 = ax4.bar(strategies, total_trades, color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'])
    ax4.set_title('전략별 총 거래 수 비교', fontsize=14, fontweight='bold')
    ax4.set_ylabel('거래 수')
    
    # 거래 수 값 표시
    for bar, value in zip(bars4, total_trades):
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height + max(total_trades) * 0.01,
                f'{value}', ha='center', va='bottom')
    
    plt.tight_layout()
    
    # 차트 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chart_path = os.path.join(os.path.dirname(__file__), 'logs', f'strategy_comparison_{timestamp}.png')
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ 비교 차트 저장 완료: {chart_path}")

def create_summary_report(results: dict):
    """요약 보고서 생성"""
    print("📋 요약 보고서 생성 중...")
    
    if not results:
        print("❌ 보고서를 생성할 결과가 없습니다.")
        return
    
    # 보고서 데이터 준비
    report_data = []
    for strategy, data in results.items():
        report_data.append({
            '전략': strategy.upper(),
            '총수익률(%)': f"{data['total_return']:.2f}",
            '최종자본(USDT)': f"{data['final_capital']:,.2f}",
            '최대MDD(%)': f"{data['mdd']:.2f}",
            '총거래수': data['total_trades'],
            '수익거래수': data['profitable_trades'],
            '손실거래수': data['losing_trades'],
            '승률(%)': f"{data['win_rate']:.1f}",
            '평균수익(%)': f"{data['avg_profit']:.2f}",
            '평균손실(%)': f"{data['avg_loss']:.2f}"
        })
    
    # DataFrame 생성
    df_report = pd.DataFrame(report_data)
    
    # 보고서 출력
    print("\n" + "=" * 100)
    print("📈 비트코인 선물 전략 백테스트 결과 요약")
    print("=" * 100)
    print(df_report.to_string(index=False))
    
    # 최고 성과 전략 찾기
    best_return_strategy = max(results.keys(), key=lambda x: results[x]['total_return'])
    best_mdd_strategy = min(results.keys(), key=lambda x: results[x]['mdd'])
    best_winrate_strategy = max(results.keys(), key=lambda x: results[x]['win_rate'])
    
    print(f"\n🏆 최고 수익률 전략: {best_return_strategy.upper()} ({results[best_return_strategy]['total_return']:.2f}%)")
    print(f"🛡️ 최저 MDD 전략: {best_mdd_strategy.upper()} ({results[best_mdd_strategy]['mdd']:.2f}%)")
    print(f"🎯 최고 승률 전략: {best_winrate_strategy.upper()} ({results[best_winrate_strategy]['win_rate']:.1f}%)")
    
    # CSV 파일로 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(os.path.dirname(__file__), 'logs', f'strategy_summary_{timestamp}.csv')
    df_report.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"\n💾 요약 보고서 저장 완료: {csv_path}")

def main():
    """메인 함수"""
    print("run_all_strategies.py 시작...")
    
    parser = argparse.ArgumentParser(description='비트코인 선물 모든 전략 백테스트 실행')
    parser.add_argument('--start', default='2024-01-01', help='시작 날짜 (YYYY-MM-DD)')
    parser.add_argument('--end', default='2024-12-31', help='종료 날짜 (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=10000, help='초기 자본')
    parser.add_argument('--strategies', nargs='+', 
                       choices=['volatility', 'momentum', 'swing', 'breakout', 'scalping'],
                       default=['volatility', 'momentum', 'swing', 'breakout', 'scalping'],
                       help='실행할 전략 선택')
    
    print("인수 파싱 중...")
    args = parser.parse_args()
    print(f"파싱된 인수: {args}")
    
    print("🚀 비트코인 선물 모든 전략 백테스트 시작!")
    print("=" * 60)
    print(f"📅 기간: {args.start} ~ {args.end}")
    print(f"💰 초기 자본: {args.capital:,} USDT")
    print(f"📊 실행 전략: {', '.join(args.strategies)}")
    
    # 로그 디렉토리 생성
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # 각 전략 실행
    success_count = 0
    for strategy in args.strategies:
        if run_strategy(strategy, args.start, args.end, args.capital):
            success_count += 1
    
    print(f"\n✅ {success_count}/{len(args.strategies)} 전략 실행 완료")
    
    # 결과 수집 및 분석
    results = collect_results()
    
    if results:
        # 비교 차트 생성
        create_comparison_chart(results)
        
        # 요약 보고서 생성
        create_summary_report(results)
        
        print(f"\n🎉 모든 작업이 완료되었습니다!")
        print(f"📁 결과 파일들은 {logs_dir} 디렉토리에 저장되었습니다.")
    else:
        print("❌ 결과를 수집할 수 없습니다.")

if __name__ == "__main__":
    main()
