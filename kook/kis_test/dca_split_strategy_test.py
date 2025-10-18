# -*- coding: utf-8 -*-
"""
DCA vs 스플릿 vs DCA+스플릿 vs 단순보유 전략 비교 백테스팅

4가지 전략:
1. 단순 보유 (Buy & Hold): 초기 전액 매수 후 보유
2. DCA (Dollar Cost Averaging): 정기적으로 분할 매수
3. 스플릿 (Split): 하락 시 차수별 매수 + 목표가 도달 시 차수별 매도
4. DCA + 스플릿 (50:50): DCA 50% + 스플릿 50% 하이브리드
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


class BacktestStrategy:
    """백테스팅 전략 기본 클래스"""
    
    def __init__(self, df, initial_capital=10_000_000, name="Strategy"):
        """
        Args:
            df: 주가 데이터프레임 (date, open, high, low, close, volume)
            initial_capital: 초기 투자 금액
            name: 전략 이름
        """
        self.df = df.copy()
        self.df['date'] = pd.to_datetime(self.df['date'])
        self.df = self.df.sort_values('date').reset_index(drop=True)
        
        self.initial_capital = initial_capital
        self.name = name
        
        # 포트폴리오 상태
        self.cash = initial_capital
        self.shares = 0
        self.avg_price = 0
        
        # 거래 기록
        self.trades = []
        self.portfolio_values = []
        
    def get_portfolio_value(self, current_price):
        """현재 포트폴리오 총 가치"""
        return self.cash + (self.shares * current_price)
    
    def buy(self, date, price, amount_money):
        """매수"""
        if amount_money > self.cash:
            amount_money = self.cash
            
        if amount_money < 1000:  # 최소 매수 금액
            return 0
        
        shares_to_buy = amount_money / price
        
        # 평균 단가 계산
        total_cost = (self.shares * self.avg_price) + (shares_to_buy * price)
        self.shares += shares_to_buy
        self.avg_price = total_cost / self.shares if self.shares > 0 else 0
        
        self.cash -= amount_money
        
        self.trades.append({
            'date': date,
            'type': 'BUY',
            'price': price,
            'shares': shares_to_buy,
            'amount': amount_money,
            'avg_price': self.avg_price
        })
        
        return shares_to_buy
    
    def sell(self, date, price, shares_to_sell):
        """매도"""
        if shares_to_sell > self.shares:
            shares_to_sell = self.shares
            
        if shares_to_sell <= 0:
            return 0
        
        amount_money = shares_to_sell * price
        self.shares -= shares_to_sell
        self.cash += amount_money
        
        self.trades.append({
            'date': date,
            'type': 'SELL',
            'price': price,
            'shares': shares_to_sell,
            'amount': amount_money,
            'avg_price': self.avg_price
        })
        
        return amount_money
    
    def run(self):
        """백테스팅 실행 (하위 클래스에서 구현)"""
        raise NotImplementedError
    
    def get_results(self):
        """백테스팅 결과 반환"""
        if len(self.portfolio_values) == 0:
            return None
        
        final_value = self.portfolio_values[-1]['value']
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100
        
        # 일별 수익률 계산
        values = [pv['value'] for pv in self.portfolio_values]
        returns = pd.Series(values).pct_change().dropna()
        
        # MDD 계산
        cummax = pd.Series(values).cummax()
        drawdown = (pd.Series(values) - cummax) / cummax * 100
        mdd = drawdown.min()
        
        # 샤프 비율 (연율화, 무위험 수익률 0 가정)
        if len(returns) > 1 and returns.std() != 0:
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252)
        else:
            sharpe = 0
        
        return {
            'strategy': self.name,
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'mdd': mdd,
            'sharpe': sharpe,
            'total_trades': len(self.trades),
            'buy_count': len([t for t in self.trades if t['type'] == 'BUY']),
            'sell_count': len([t for t in self.trades if t['type'] == 'SELL']),
            'final_shares': self.shares,
            'final_cash': self.cash,
            'avg_price': self.avg_price
        }


class BuyAndHoldStrategy(BacktestStrategy):
    """전략 1: 단순 보유 (Buy & Hold)"""
    
    def __init__(self, df, initial_capital=10_000_000):
        super().__init__(df, initial_capital, "단순보유")
    
    def run(self):
        """초기에 전액 매수 후 보유"""
        first_date = self.df.iloc[0]['date']
        first_price = self.df.iloc[0]['close']
        
        # 첫날 전액 매수
        self.buy(first_date, first_price, self.initial_capital)
        
        # 포트폴리오 가치 기록
        for idx, row in self.df.iterrows():
            current_value = self.get_portfolio_value(row['close'])
            self.portfolio_values.append({
                'date': row['date'],
                'value': current_value,
                'price': row['close']
            })


class DCAStrategy(BacktestStrategy):
    """전략 2: DCA (Dollar Cost Averaging) - 정기 분할 매수"""
    
    def __init__(self, df, initial_capital=10_000_000, monthly_invest=None, invest_day=1):
        """
        Args:
            monthly_invest: 월별 투자 금액 (None이면 자동 계산)
            invest_day: 매월 투자 날짜 (1~28)
        """
        super().__init__(df, initial_capital, "DCA전략")
        
        # 전체 기간을 고려하여 월별 투자액 계산
        total_months = (self.df.iloc[-1]['date'].year - self.df.iloc[0]['date'].year) * 12 + \
                      (self.df.iloc[-1]['date'].month - self.df.iloc[0]['date'].month)
        
        if monthly_invest is None:
            # 전체 기간 동안 균등 분할
            self.monthly_invest = initial_capital / max(total_months, 1)
        else:
            self.monthly_invest = monthly_invest
            
        self.invest_day = invest_day
        self.last_invest_month = None
    
    def run(self):
        """매월 정기적으로 분할 매수"""
        for idx, row in self.df.iterrows():
            current_date = row['date']
            current_price = row['close']
            
            # 매월 invest_day에 매수
            if current_date.day >= self.invest_day:
                current_month = (current_date.year, current_date.month)
                
                if self.last_invest_month != current_month:
                    # 이번 달 첫 매수
                    if self.cash >= self.monthly_invest:
                        self.buy(current_date, current_price, self.monthly_invest)
                    elif self.cash > 1000:
                        # 남은 현금 전액 투자
                        self.buy(current_date, current_price, self.cash)
                    
                    self.last_invest_month = current_month
            
            # 포트폴리오 가치 기록
            current_value = self.get_portfolio_value(current_price)
            self.portfolio_values.append({
                'date': current_date,
                'value': current_value,
                'price': current_price
            })


class SplitStrategy(BacktestStrategy):
    """전략 3: 스플릿 전략 - 하락 시 차수별 매수"""
    
    def __init__(self, df, initial_capital=10_000_000):
        super().__init__(df, initial_capital, "스플릿전략")
        
        # 차수별 설정
        self.splits = [
            {'number': 1, 'trigger_rate': 0.0,   'invest_ratio': 0.15, 'target_rate': 5.0},   # 초기 진입
            {'number': 2, 'trigger_rate': -5.0,  'invest_ratio': 0.15, 'target_rate': 7.0},   # -5% 하락
            {'number': 3, 'trigger_rate': -10.0, 'invest_ratio': 0.20, 'target_rate': 10.0},  # -10% 하락
            {'number': 4, 'trigger_rate': -15.0, 'invest_ratio': 0.20, 'target_rate': 12.0},  # -15% 하락
            {'number': 5, 'trigger_rate': -20.0, 'invest_ratio': 0.30, 'target_rate': 15.0},  # -20% 하락
        ]
        
        # 차수별 상태 추적
        self.split_positions = {}
        for split in self.splits:
            self.split_positions[split['number']] = {
                'entered': False,
                'entry_price': 0,
                'shares': 0,
                'entry_date': None
            }
        
        self.base_price = None  # 기준가 (첫 종가)
    
    def run(self):
        """하락 시 차수별 매수, 상승 시 차수별 매도"""
        
        for idx, row in self.df.iterrows():
            current_date = row['date']
            current_price = row['close']
            
            # 기준가 설정 (첫날)
            if self.base_price is None:
                self.base_price = current_price
            
            # 기준가 대비 변동률 계산
            change_rate = (current_price - self.base_price) / self.base_price * 100
            
            # 차수별 진입 조건 확인
            for split in self.splits:
                split_num = split['number']
                position = self.split_positions[split_num]
                
                # 매수: 아직 진입하지 않았고, 트리거 조건 만족
                if not position['entered'] and change_rate <= split['trigger_rate']:
                    invest_amount = self.initial_capital * split['invest_ratio']
                    
                    if self.cash >= invest_amount:
                        shares_bought = self.buy(current_date, current_price, invest_amount)
                        
                        if shares_bought > 0:
                            position['entered'] = True
                            position['entry_price'] = current_price
                            position['shares'] = shares_bought
                            position['entry_date'] = current_date
                
                # 매도: 진입했고, 목표 수익률 달성
                elif position['entered'] and position['shares'] > 0:
                    profit_rate = (current_price - position['entry_price']) / position['entry_price'] * 100
                    
                    if profit_rate >= split['target_rate']:
                        self.sell(current_date, current_price, position['shares'])
                        
                        # 포지션 초기화 (재진입 가능하도록)
                        position['entered'] = False
                        position['entry_price'] = 0
                        position['shares'] = 0
                        
                        # 기준가 갱신 (익절 후)
                        self.base_price = current_price
            
            # 포트폴리오 가치 기록
            current_value = self.get_portfolio_value(current_price)
            self.portfolio_values.append({
                'date': current_date,
                'value': current_value,
                'price': current_price
            })


class HybridStrategy(BacktestStrategy):
    """전략 4: DCA + 스플릿 하이브리드 (50:50)"""
    
    def __init__(self, df, initial_capital=10_000_000, dca_ratio=0.5):
        """
        Args:
            dca_ratio: DCA에 할당할 비율 (기본 0.5 = 50%)
        """
        super().__init__(df, initial_capital, "DCA+스플릿(50:50)")
        
        self.dca_ratio = dca_ratio
        self.split_ratio = 1 - dca_ratio
        
        # DCA 파트
        self.dca_budget = initial_capital * dca_ratio
        self.dca_cash = self.dca_budget
        
        total_months = (self.df.iloc[-1]['date'].year - self.df.iloc[0]['date'].year) * 12 + \
                      (self.df.iloc[-1]['date'].month - self.df.iloc[0]['date'].month)
        self.monthly_invest = self.dca_budget / max(total_months, 1)
        self.last_invest_month = None
        
        # 스플릿 파트
        self.split_budget = initial_capital * self.split_ratio
        self.split_cash = self.split_budget
        
        self.splits = [
            {'number': 1, 'trigger_rate': 0.0,   'invest_ratio': 0.15, 'target_rate': 5.0},
            {'number': 2, 'trigger_rate': -5.0,  'invest_ratio': 0.15, 'target_rate': 7.0},
            {'number': 3, 'trigger_rate': -10.0, 'invest_ratio': 0.20, 'target_rate': 10.0},
            {'number': 4, 'trigger_rate': -15.0, 'invest_ratio': 0.20, 'target_rate': 12.0},
            {'number': 5, 'trigger_rate': -20.0, 'invest_ratio': 0.30, 'target_rate': 15.0},
        ]
        
        self.split_positions = {}
        for split in self.splits:
            self.split_positions[split['number']] = {
                'entered': False,
                'entry_price': 0,
                'shares': 0,
                'entry_date': None
            }
        
        self.base_price = None
        
        # 전체 현금은 DCA + 스플릿 현금의 합
        self.cash = self.dca_cash + self.split_cash
    
    def run(self):
        """DCA와 스플릿을 동시에 실행"""
        
        for idx, row in self.df.iterrows():
            current_date = row['date']
            current_price = row['close']
            
            # 기준가 설정
            if self.base_price is None:
                self.base_price = current_price
            
            # === DCA 파트 ===
            if current_date.day >= 1:  # 매월 1일
                current_month = (current_date.year, current_date.month)
                
                if self.last_invest_month != current_month:
                    if self.dca_cash >= self.monthly_invest:
                        shares_bought = self.monthly_invest / current_price
                        
                        # 매수 기록
                        total_cost = (self.shares * self.avg_price) + (shares_bought * current_price)
                        self.shares += shares_bought
                        self.avg_price = total_cost / self.shares if self.shares > 0 else 0
                        
                        self.dca_cash -= self.monthly_invest
                        self.cash = self.dca_cash + self.split_cash
                        
                        self.trades.append({
                            'date': current_date,
                            'type': 'BUY (DCA)',
                            'price': current_price,
                            'shares': shares_bought,
                            'amount': self.monthly_invest,
                            'avg_price': self.avg_price
                        })
                    
                    self.last_invest_month = current_month
            
            # === 스플릿 파트 ===
            change_rate = (current_price - self.base_price) / self.base_price * 100
            
            for split in self.splits:
                split_num = split['number']
                position = self.split_positions[split_num]
                
                # 매수
                if not position['entered'] and change_rate <= split['trigger_rate']:
                    invest_amount = self.split_budget * split['invest_ratio']
                    
                    if self.split_cash >= invest_amount:
                        shares_bought = invest_amount / current_price
                        
                        # 매수 기록
                        total_cost = (self.shares * self.avg_price) + (shares_bought * current_price)
                        self.shares += shares_bought
                        self.avg_price = total_cost / self.shares if self.shares > 0 else 0
                        
                        self.split_cash -= invest_amount
                        self.cash = self.dca_cash + self.split_cash
                        
                        position['entered'] = True
                        position['entry_price'] = current_price
                        position['shares'] = shares_bought
                        position['entry_date'] = current_date
                        
                        self.trades.append({
                            'date': current_date,
                            'type': f'BUY (Split {split_num})',
                            'price': current_price,
                            'shares': shares_bought,
                            'amount': invest_amount,
                            'avg_price': self.avg_price
                        })
                
                # 매도
                elif position['entered'] and position['shares'] > 0:
                    profit_rate = (current_price - position['entry_price']) / position['entry_price'] * 100
                    
                    if profit_rate >= split['target_rate']:
                        amount_received = position['shares'] * current_price
                        self.shares -= position['shares']
                        
                        self.split_cash += amount_received
                        self.cash = self.dca_cash + self.split_cash
                        
                        self.trades.append({
                            'date': current_date,
                            'type': f'SELL (Split {split_num})',
                            'price': current_price,
                            'shares': position['shares'],
                            'amount': amount_received,
                            'avg_price': self.avg_price
                        })
                        
                        # 포지션 초기화
                        position['entered'] = False
                        position['entry_price'] = 0
                        position['shares'] = 0
                        
                        # 기준가 갱신
                        self.base_price = current_price
            
            # 포트폴리오 가치 기록
            current_value = self.get_portfolio_value(current_price)
            self.portfolio_values.append({
                'date': current_date,
                'value': current_value,
                'price': current_price
            })


def run_backtest_comparison(csv_path, stock_name, initial_capital=10_000_000):
    """
    4가지 전략 백테스팅 비교
    
    Args:
        csv_path: CSV 파일 경로
        stock_name: 종목명
        initial_capital: 초기 투자금
    """
    print(f"\n{'='*80}")
    print(f"📊 [{stock_name}] 백테스팅 시작")
    print(f"{'='*80}")
    
    # 데이터 로드
    try:
        df = pd.read_csv(csv_path)
        print(f"✅ 데이터 로드 성공: {len(df)}개 데이터")
        print(f"   기간: {df['date'].min()} ~ {df['date'].max()}")
    except Exception as e:
        print(f"❌ 데이터 로드 실패: {e}")
        return None
    
    # 4가지 전략 실행
    strategies = [
        BuyAndHoldStrategy(df, initial_capital),
        DCAStrategy(df, initial_capital),
        SplitStrategy(df, initial_capital),
        HybridStrategy(df, initial_capital, dca_ratio=0.5)
    ]
    
    results = []
    
    for strategy in strategies:
        print(f"\n⏳ {strategy.name} 실행 중...")
        strategy.run()
        result = strategy.get_results()
        results.append(result)
        
        print(f"   최종 수익률: {result['total_return']:.2f}%")
        print(f"   MDD: {result['mdd']:.2f}%")
        print(f"   총 거래 횟수: {result['total_trades']}회")
    
    # 결과 비교표
    print(f"\n{'='*80}")
    print(f"📈 전략 비교 결과")
    print(f"{'='*80}")
    print(f"{'전략명':<20} {'최종자산':>15} {'수익률':>10} {'MDD':>10} {'샤프':>8} {'거래수':>8}")
    print(f"{'-'*80}")
    
    for result in results:
        print(f"{result['strategy']:<20} "
              f"{result['final_value']:>15,.0f}원 "
              f"{result['total_return']:>9.2f}% "
              f"{result['mdd']:>9.2f}% "
              f"{result['sharpe']:>7.2f} "
              f"{result['total_trades']:>7}회")
    
    # 최고 수익률 전략 찾기
    best_strategy = max(results, key=lambda x: x['total_return'])
    print(f"\n🏆 최고 수익률: {best_strategy['strategy']} ({best_strategy['total_return']:.2f}%)")
    
    # 그래프 그리기
    plot_comparison(strategies, stock_name)
    
    return results


def plot_comparison(strategies, stock_name):
    """전략 비교 그래프"""
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    
    # 1. 포트폴리오 가치 변화
    ax1 = axes[0]
    for strategy in strategies:
        dates = [pv['date'] for pv in strategy.portfolio_values]
        values = [pv['value'] for pv in strategy.portfolio_values]
        ax1.plot(dates, values, label=strategy.name, linewidth=2)
    
    ax1.set_title(f'{stock_name} - 전략별 포트폴리오 가치 변화', fontsize=14, fontweight='bold')
    ax1.set_xlabel('날짜', fontsize=12)
    ax1.set_ylabel('포트폴리오 가치 (원)', fontsize=12)
    ax1.legend(loc='best', fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.ticklabel_format(style='plain', axis='y')
    
    # 2. 수익률 비교 막대 그래프
    ax2 = axes[1]
    strategy_names = [s.name for s in strategies]
    returns = [(s.get_results()['total_return']) for s in strategies]
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    
    bars = ax2.bar(strategy_names, returns, color=colors, alpha=0.7)
    ax2.set_title(f'{stock_name} - 전략별 수익률 비교', fontsize=14, fontweight='bold')
    ax2.set_ylabel('수익률 (%)', fontsize=12)
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax2.grid(True, alpha=0.3, axis='y')
    
    # 막대 위에 수치 표시
    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%',
                ha='center', va='bottom' if height > 0 else 'top',
                fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    
    # 저장
    output_dir = os.path.join(os.path.dirname(__file__), 'results')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'strategy_comparison_{stock_name}.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 그래프 저장: {output_path}")
    
    plt.close()


def main():
    """메인 실행 함수"""
    print("="*80)
    print("🚀 DCA vs 스플릿 vs DCA+스플릿 vs 단순보유 전략 백테스팅")
    print("="*80)
    
    # 초기 투자금 설정
    INITIAL_CAPITAL = 10_000_000  # 1,000만원
    
    # 테스트할 종목 리스트
    test_stocks = [
        {
            'name': 'KODEX 200',
            'csv_path': 'data/etf_index/069500_KODEX 200.csv'
        },
        {
            'name': '현대차우',
            'csv_path': 'data/kospi100/005385_현대차우.csv'
        },
        {
            'name': '삼성전자우',
            'csv_path': 'data/kospi100/005935_삼성전자우.csv'
        }
    ]
    
    all_results = {}
    
    # 각 종목별 백테스팅
    for stock in test_stocks:
        csv_path = os.path.join(os.path.dirname(__file__), stock['csv_path'])
        
        if not os.path.exists(csv_path):
            print(f"\n❌ 파일을 찾을 수 없습니다: {csv_path}")
            continue
        
        results = run_backtest_comparison(csv_path, stock['name'], INITIAL_CAPITAL)
        
        if results:
            all_results[stock['name']] = results
    
    # 전체 요약
    print(f"\n{'='*80}")
    print(f"📊 전체 백테스팅 요약")
    print(f"{'='*80}")
    
    for stock_name, results in all_results.items():
        print(f"\n[{stock_name}]")
        best = max(results, key=lambda x: x['total_return'])
        worst = min(results, key=lambda x: x['total_return'])
        print(f"  🏆 최고: {best['strategy']} ({best['total_return']:.2f}%)")
        print(f"  📉 최저: {worst['strategy']} ({worst['total_return']:.2f}%)")
    
    print(f"\n{'='*80}")
    print("✅ 백테스팅 완료!")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()

