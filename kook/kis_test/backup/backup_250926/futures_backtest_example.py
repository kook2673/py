
# -*- coding: utf-8 -*-
"""
국내 선물 백테스트 프레임워크 예시 (이동평균 교차 전략)

이 스크립트는 다운로드한 선물 분봉 데이터를 사용하여 간단한 백테스트를 수행하는
기본적인 구조를 제공합니다.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# --- 백테스트 설정 ---
# 이전에 다운로드한 데이터 파일 경로
DATA_FILE_PATH = "kook/kis_wfo/futures_data_101U4_1min.csv"
# 단기 이동평균선 기간
SHORT_WINDOW = 20
# 장기 이동평균선 기간
LONG_WINDOW = 60
# 초기 자본금
INITIAL_CAPITAL = 100_000_000
# 거래 수수료 (선물 계약당 %가 아닌 금액으로 설정하는 경우가 많으나, 여기서는 비율로 가정)
# KIS 선물 수수료는 약 0.003% 수준
COMMISSION_RATE = 0.00003
# --------------------


def run_backtest(data: pd.DataFrame, initial_capital: float, short_window: int, long_window: int, commission: float):
    """
    백테스트를 실행하고 결과를 반환합니다.
    """
    print("--- 백테스트를 시작합니다 ---")
    
    # 1. 시그널 생성
    signals = pd.DataFrame(index=data.index)
    signals['price'] = data['close']
    signals['short_ma'] = data['close'].rolling(window=short_window, min_periods=1).mean()
    signals['long_ma'] = data['close'].rolling(window=long_window, min_periods=1).mean()
    
    # 단기 이평선이 장기 이평선을 상향 돌파하면 매수(1), 하향 돌파하면 매도(-1)
    signals['signal'] = 0.0
    signals['signal'][short_window:] = np.where(
        signals['short_ma'][short_window:] > signals['long_ma'][short_window:], 1.0, 0.0
    )
    signals['positions'] = signals['signal'].diff()

    print(f"총 {len(signals[signals['positions'] != 0])}개의 매매 시그널이 생성되었습니다.")

    # 2. 포트폴리오 계산
    portfolio = pd.DataFrame(index=signals.index).fillna(0.0)
    portfolio['holdings'] = 0.0  # 보유 계약 수
    portfolio['cash'] = initial_capital
    portfolio['total'] = initial_capital
    portfolio['returns'] = 0.0

    # 선물 1계약에 필요한 증거금 (단순화를 위해 현재 가격의 일정 비율로 가정)
    # 실제로는 증거금률에 따라 변동됩니다. 여기서는 약 15%로 가정.
    margin_per_contract = data['close'][0] * 250000 * 0.15 # KOSPI200 선물 승수 = 250,000원

    for i in range(1, len(portfolio)):
        # 이전 상태를 현재로 복사
        portfolio.loc[portfolio.index[i], 'cash'] = portfolio.loc[portfolio.index[i-1], 'cash']
        portfolio.loc[portfolio.index[i], 'holdings'] = portfolio.loc[portfolio.index[i-1], 'holdings']

        price = signals['price'][i]
        signal = signals['positions'][i]

        if signal == 1.0: # 매수 시그널
            if portfolio['holdings'][i-1] == 0: # 현재 포지션이 없을 때만 진입
                # 현재 현금으로 살 수 있는 최대 계약 수 (증거금 기준)
                available_contracts = int(portfolio['cash'][i-1] / margin_per_contract)
                if available_contracts > 0:
                    # 1계약만 진입
                    contracts_to_buy = 1
                    cost = contracts_to_buy * price * 250000 * commission
                    
                    portfolio.loc[portfolio.index[i], 'cash'] -= cost
                    portfolio.loc[portfolio.index[i], 'holdings'] = contracts_to_buy
                    print(f"{portfolio.index[i]}: 매수 진입 (1계약) @ {price}")

        elif signal == -1.0: # 매도 시그널
            if portfolio['holdings'][i-1] > 0: # 보유하고 있을 때만 청산
                contracts_held = portfolio['holdings'][i-1]
                cost = contracts_held * price * 250000 * commission
                
                portfolio.loc[portfolio.index[i], 'cash'] -= cost
                portfolio.loc[portfolio.index[i], 'holdings'] = 0
                print(f"{portfolio.index[i]}: 매도 청산 ({contracts_held}계약) @ {price}")

        # 포트폴리오 가치 업데이트
        # 선물 평가가치 = (현재가 - 진입가) * 계약수 * 승수
        # 단순화를 위해, 여기서는 총 자산을 (현금 + (보유 계약수 * 현재가치))로 계산합니다.
        # 이는 주식 백테스트와 유사한 방식이며, 정확한 선물 손익 계산과는 차이가 있습니다.
        position_value = portfolio['holdings'][i] * price * 250000
        # 이 백테스트에서는 레버리지 효과를 직접 반영하지 않고, 총 자산 변화 추이만 봅니다.
        # 'total'은 보유 포지션의 명목가치(notional value)가 아닌, '만약 이 돈으로 주식을 샀다면' 정도의 개념으로 해석.
        # 이는 PNL을 계산하기 위함.
        
        # 이전 스텝 대비 자산 변화 계산 (PNL)
        prev_price = signals['price'][i-1]
        pnl = portfolio['holdings'][i-1] * (price - prev_price) * 250000
        portfolio.loc[portfolio.index[i], 'cash'] += pnl

        portfolio.loc[portfolio.index[i], 'total'] = portfolio['cash'][i]
        
    portfolio['returns'] = portfolio['total'].pct_change()
    
    return portfolio, signals

def print_performance(portfolio: pd.DataFrame, initial_capital: float):
    """
    백테스트 성과를 출력합니다.
    """
    print("\n--- 백테스트 성과 ---")
    
    final_value = portfolio['total'].iloc[-1]
    total_return = (final_value / initial_capital) - 1
    
    print(f"최종 자산: {final_value:,.0f} 원")
    print(f"초기 자본: {initial_capital:,.0f} 원")
    print(f"총 수익률: {total_return:.2%}")
    
    # MDD (최대 낙폭) 계산
    portfolio['peak'] = portfolio['total'].cummax()
    portfolio['drawdown'] = (portfolio['total'] - portfolio['peak']) / portfolio['peak']
    max_drawdown = portfolio['drawdown'].min()
    print(f"최대 낙폭 (MDD): {max_drawdown:.2%}")

    # 승률 계산 (간단하게)
    trades = signals[signals['positions'] != 0]
    wins = 0
    trade_count = 0
    for i in range(len(trades)):
        if trades['positions'][i] == 1.0: # 진입
            entry_price = trades['price'][i]
            # 다음 청산 시점 찾기
            if i + 1 < len(trades) and trades['positions'][i+1] == -1.0:
                exit_price = trades['price'][i+1]
                if exit_price > entry_price:
                    wins += 1
                trade_count += 1
    
    win_rate = (wins / trade_count) * 100 if trade_count > 0 else 0
    print(f"승률: {win_rate:.2f}% ({wins}/{trade_count})")


def plot_results(portfolio: pd.DataFrame, signals: pd.DataFrame):
    """
    백테스트 결과를 시각화합니다.
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12), sharex=True)
    
    # 1. 자산 곡선 및 MDD
    ax1.plot(portfolio.index, portfolio['total'], label='Portfolio Value')
    ax1.set_title('Portfolio Value and Drawdown')
    ax1.set_ylabel('Total Value (KRW)')
    ax1.legend()
    
    ax1_twin = ax1.twinx()
    ax1_twin.fill_between(portfolio.index, portfolio['drawdown'] * 100, 0, color='red', alpha=0.3)
    ax1_twin.set_ylabel('Drawdown (%)', color='red')
    
    # 2. 가격 및 매매 시점
    ax2.plot(signals.index, signals['price'], label='Price')
    ax2.plot(signals.index, signals['short_ma'], label=f'MA {SHORT_WINDOW}', linestyle='--')
    ax2.plot(signals.index, signals['long_ma'], label=f'MA {LONG_WINDOW}', linestyle='--')
    
    # 매수/매도 시점 표시
    ax2.plot(signals[signals['positions'] == 1.0].index, 
             signals.short_ma[signals['positions'] == 1.0],
             '^', markersize=10, color='g', label='Buy Signal')
             
    ax2.plot(signals[signals['positions'] == -1.0].index, 
             signals.short_ma[signals['positions'] == -1.0],
             'v', markersize=10, color='r', label='Sell Signal')

    ax2.set_title('Futures Price, MAs, and Trading Signals')
    ax2.set_ylabel('Price')
    ax2.set_xlabel('Date')
    ax2.legend()
    
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    # 데이터 파일 존재 여부 확인
    if not os.path.exists(DATA_FILE_PATH):
        print(f"데이터 파일이 없습니다: {DATA_FILE_PATH}")
        print("먼저 `download_futures_data.py`를 실행하여 데이터를 다운로드하세요.")
    else:
        # 1. 데이터 로드
        futures_data = pd.read_csv(DATA_FILE_PATH, index_col='datetime', parse_dates=True)
        print(f"총 {len(futures_data)}개의 데이터 포인트를 로드했습니다.")
        
        # 2. 백테스트 실행
        portfolio, signals = run_backtest(
            data=futures_data,
            initial_capital=INITIAL_CAPITAL,
            short_window=SHORT_WINDOW,
            long_window=LONG_WINDOW,
            commission=COMMISSION_RATE
        )
        
        # 3. 성과 출력
        print_performance(portfolio, INITIAL_CAPITAL)
        
        # 4. 결과 시각화
        plot_results(portfolio, signals)
