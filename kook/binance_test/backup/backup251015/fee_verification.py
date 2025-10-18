"""
수수료 계산 검증
- 실제 비트코인 거래 시나리오로 테스트
"""

def verify_fee_calculation():
    """수수료 계산 검증"""
    print("=== 비트코인 수수료 계산 검증 ===")
    
    # 시나리오: $10,000으로 비트코인 구매/판매
    btc_price = 50000  # BTC 가격 $50,000
    usd_amount = 10000  # $10,000
    fee_rate = 0.0005  # 0.05%
    
    print(f"BTC 가격: ${btc_price:,}")
    print(f"거래 금액: ${usd_amount:,}")
    print(f"수수료율: {fee_rate * 100}%")
    
    # 매수
    btc_amount = usd_amount / btc_price
    buy_fee_usd = usd_amount * fee_rate
    buy_fee_btc = btc_amount * fee_rate
    
    print(f"\n=== 매수 ===")
    print(f"구매 BTC: {btc_amount:.6f} BTC")
    print(f"매수 수수료: ${buy_fee_usd:.2f} ({buy_fee_btc:.6f} BTC)")
    print(f"실제 구매 비용: ${usd_amount + buy_fee_usd:.2f}")
    
    # 매도 (같은 가격)
    sell_amount_usd = btc_amount * btc_price
    sell_fee_usd = sell_amount_usd * fee_rate
    sell_fee_btc = btc_amount * fee_rate
    
    print(f"\n=== 매도 ===")
    print(f"판매 금액: ${sell_amount_usd:.2f}")
    print(f"매도 수수료: ${sell_fee_usd:.2f} ({sell_fee_btc:.6f} BTC)")
    print(f"실제 수령 금액: ${sell_amount_usd - sell_fee_usd:.2f}")
    
    # 손익 계산
    total_cost = usd_amount + buy_fee_usd
    net_proceeds = sell_amount_usd - sell_fee_usd
    pnl = net_proceeds - total_cost
    total_fees = buy_fee_usd + sell_fee_usd
    
    print(f"\n=== 손익 ===")
    print(f"총 비용: ${total_cost:.2f}")
    print(f"순 수익: ${net_proceeds:.2f}")
    print(f"손익: ${pnl:.2f}")
    print(f"총 수수료: ${total_fees:.2f}")
    print(f"수수료 비율: {total_fees/usd_amount*100:.3f}%")
    
    # 1000회 거래 시뮬레이션
    print(f"\n=== 1000회 거래 시뮬레이션 ===")
    total_fees_1000 = total_fees * 1000
    print(f"1000회 거래 총 수수료: ${total_fees_1000:.2f}")
    print(f"수수료 비율: {total_fees_1000/usd_amount*100:.1f}%")

if __name__ == "__main__":
    verify_fee_calculation()
