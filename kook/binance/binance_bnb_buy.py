"""
BNB 수수료 구매 스크립트

이 스크립트는 바이낸스 선물 계정의 USDT를 현물 계정으로 전송하여,
수수료 지불에 사용될 BNB 코인을 자동으로 구매합니다.
"""

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
import ccxt
import time
import myBinance
import ende_key
import my_key

# ========================= BNB 구매 함수 =========================
def buy_bnb_for_fees(binance_futures_instance, Binance_AccessKey, Binance_ScretKey):
    """
    선물 계정의 USDT를 사용하여 현물 계정에서 BNB를 구매합니다 (수수료 목적).
    """
    print("BNB 수수료용 구매 로직 시작")
    try:
        # 1. 현물용 바이낸스 객체 생성
        binance_spot = ccxt.binance(config={
            'apiKey': Binance_AccessKey,
            'secret': Binance_ScretKey,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            }
        })

        # 2. 선물 계정 BNB 잔액 확인
        futures_balance = binance_futures_instance.fetch_balance()
        bnb_balance = futures_balance.get('BNB', {}).get('free', 0.0)
        
        bnb_price = binance_spot.fetch_ticker('BNB/USDT')['last']
        bnb_value_in_usdt = bnb_balance * bnb_price
        
        print(f"현재 현물 BNB 잔액: {bnb_balance:.4f} BNB ({bnb_value_in_usdt:.2f} USDT)")

        # 3. BNB 잔액이 임계값(예: 5 USDT) 미만이면 구매 진행
        if bnb_value_in_usdt < 3.0:
            print("BNB 잔액이 3 USDT 미만이므로 구매를 시도합니다.")
            
            # 4. 선물 -> 현물로 USDT 이체
            transfer_amount = 11.0  # 바이낸스 최소 주문금액이 보통 $10 이므로 약간 여유있게
            print(f"{transfer_amount} USDT를 선물 지갑에서 현물 지갑으로 이체합니다.")
            
            try:
                # CCXT의 통합 transfer 함수 사용. from/to 파라미터는 'future', 'spot' 등 거래소마다 다를 수 있습니다.
                # 바이낸스의 경우 USD-M 선물은 'future', 현물은 'spot' 또는 'main'을 사용합니다.
                # https://docs.ccxt.com/en/latest/manual.html#unified-api-transfers
                transfer_result = binance_futures_instance.transfer('USDT', transfer_amount, 'future', 'spot')
                print(f"USDT 이체 성공: {transfer_result}")
                
                # 이체 후 잔고 반영을 위해 잠시 대기
                time.sleep(5)

            except Exception as e:
                print(f"오류: 선물 -> 현물 USDT 이체 실패 | 상세: {e}")
                return

            # 5. 현물 시장에서 BNB 매수
            try:
                # 이체된 USDT로 구매할 BNB 수량 계산 (수수료 감안하여 99.5%만 사용)
                usdt_to_use = transfer_amount * 0.995
                amount_to_buy = usdt_to_use / bnb_price
                
                # 최소 주문 수량 확인 및 조정
                market = binance_spot.market('BNB/USDT')
                min_amount = market['limits']['amount']['min']
                if amount_to_buy < min_amount:
                    print(f"경고: 계산된 구매수량 {amount_to_buy}이 최소주문수량 {min_amount}보다 작아 조정합니다.")
                    amount_to_buy = min_amount
                
                # 수량 정밀도에 맞춰 조정
                amount_to_buy = binance_spot.amount_to_precision('BNB/USDT', amount_to_buy)

                print(f"BNB {amount_to_buy}개를 시장가로 매수합니다.")
                
                order = binance_spot.create_market_buy_order('BNB/USDT', amount_to_buy)
                
                print(f"BNB 매수 성공: {order}")

                # 6. 구매한 BNB를 현물 -> 선물 지갑으로 이체
                try:
                    # order 객체에서 실제 체결된 수량을 가져옵니다.
                    filled_amount = order.get('filled')
                    if filled_amount and filled_amount > 0:
                        print(f"구매한 BNB {filled_amount}개를 현물 지갑에서 선물 지갑으로 이체합니다.")
                        
                        # 이체 전 잠시 대기 (매수 체결 후 잔고 반영 시간)
                        time.sleep(3)
                        
                        # CCXT의 transfer 함수를 사용하여 현물(spot)에서 선물(future)로 BNB 이체
                        transfer_bnb_result = binance_futures_instance.transfer('BNB', filled_amount, 'spot', 'future')
                        print(f"BNB 이체 성공: {transfer_bnb_result}")
                    else:
                        print(f"BNB가 구매되지 않았거나 체결 수량을 확인할 수 없어 이체를 건겁니다. Order: {order}")

                except Exception as e:
                    print(f"현물 -> 선물 BNB 이체 실패", e)

            except Exception as e:
                print(f"오류: 현물 BNB 매수 실패 | 상세: {e}")

        else:
            print("BNB 잔액이 충분하여 구매하지 않습니다.")

    except Exception as e:
        print(f"오류: BNB 구매 로직 실행 중 오류 발생 | 상세: {e}")

# ========================= 메인 실행 로직 =========================
if __name__ == '__main__':
    print("=== BNB 수수료 구매 스크립트 시작 ===")

    # 키 복호화 및 바이낸스 선물 객체 생성
    try:
        simpleEnDecrypt = myBinance.SimpleEnDecrypt(ende_key.ende_key)
        Binance_AccessKey = simpleEnDecrypt.decrypt(my_key.binance_access)
        Binance_ScretKey = simpleEnDecrypt.decrypt(my_key.binance_secret)
                
        binanceX = ccxt.binance(config={
            'apiKey': Binance_AccessKey, 
            'secret': Binance_ScretKey,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                        'adjustForTimeDifference': True,
                    }
                })
            
            # 시간 동기화
        binanceX.load_time_difference() 
        
    except Exception as e:
        print(f"오류: 바이낸스 객체 생성 또는 키 복호화 실패 | 상세: {e}")
        sys.exit(1)

    # BNB 구매 함수 실행
    buy_bnb_for_fees(binanceX, Binance_AccessKey, Binance_ScretKey)
    
    print("=== BNB 수수료 구매 스크립트 종료 ===")
