# -*- coding: utf-8 -*-
import sys
import os

# 한글 출력을 위한 인코딩 설정
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

'''
📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.

주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!
'''
import pyupbit
import myUpbit
import pandas as pd
import time
import json
import gc
import psutil

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import telegram_sender as line_alert

Upbit_AccessKey = "OPj8hp8zWyWxnR1jyMG9oG2MRcKxy84sHSTZKrof"
Upbit_ScretKey =  "wgZuuM4hJeJUDoaL5iKSjxcaiIpHmoSs4N1VfKvA"

# 코인 정보 파일 경로
coin_info_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Ma_Double_Upbit_1d4h_Bot.json")

# ========================= 메모리 관리 유틸리티 =========================
def cleanup_memory():
    """메모리 정리 함수"""
    try:
        # 가비지 컬렉션 강제 실행
        collected = gc.collect()
        
        # 메모리 사용량 확인
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        print(f"메모리 정리 완료: {collected}개 객체 수집, 현재 사용량: {memory_mb:.2f} MB")
        return memory_mb
    except Exception as e:
        print(f"메모리 정리 중 오류: {e}")
        return 0

def cleanup_dataframes(*dataframes):
    """데이터프레임들 명시적 삭제"""
    for df in dataframes:
        if df is not None:
            try:
                del df
            except:
                pass

def cleanup_variables(**kwargs):
    """변수들 명시적 삭제"""
    for var_name, var_value in kwargs.items():
        if var_value is not None:
            try:
                del var_value
            except:
                pass

# 코인 정보 파일에서 코인 목록과 설정값 읽기
def load_coin_data():
    """코인 정보 파일에서 코인 목록과 설정값을 한 번에 읽어옴"""
    try:
        with open(coin_info_file_path, 'r', encoding='utf-8') as f:
            coin_info = json.load(f)
            tickers = coin_info.get("tickers", [])
            settings = coin_info.get("default_settings", {})
            
            if not tickers:
                raise ValueError("코인 목록이 비어있습니다")
            if not settings:
                raise ValueError("코인 설정값이 비어있습니다")
                
            return tickers, settings
            
    except FileNotFoundError:
        print(f"❌ 에러: 코인 정보 파일을 찾을 수 없습니다: {coin_info_file_path}")
        print("프로그램을 종료합니다.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ 에러: JSON 파일 형식이 잘못되었습니다: {e}")
        print("프로그램을 종료합니다.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 에러: 코인 정보 파일 읽기 실패: {e}")
        print("프로그램을 종료합니다.")
        sys.exit(1)

# 코인 정보 파일에서 코인 목록과 설정값 로드
Tickers, coin_settings = load_coin_data()

print(f"로드된 코인 목록: {Tickers}")
print(f"로드된 코인 설정값: {coin_settings}")

InvestCoinList = list()

# JSON 파일에서 읽어온 설정값으로 InvestCoinList 구성
for ticker in Tickers:
    if ticker not in coin_settings:
        print(f"❌ 에러: {ticker}의 설정값이 없습니다")
        print("프로그램을 종료합니다.")
        sys.exit(1)
        
    settings = coin_settings[ticker]
    InvestCoinList.append({
        "coin_ticker": ticker,
        "small_ma": settings["small_ma"],
        "big_ma": settings["big_ma"],
        "invest_rate": settings["invest_rate"]
    })
    print(f"{ticker} 설정값: small_ma={settings['small_ma']}, big_ma={settings['big_ma']}, invest_rate={settings['invest_rate']}")

#업비트 객체를 만든다
upbit = pyupbit.Upbit(Upbit_AccessKey, Upbit_ScretKey)

BOT_NAME = "DoubleMa_1d4h_Upbit"

#포트폴리오 이름
PortfolioName = "더블이동평균코인전략_1d4h_업비트"

limitDiv = 2000 #10일 거래대금 평균의 1/2000을 주문 상한으로 정의!


#리밸런싱이 가능한지 여부를 판단! (즉 매매여부 판단 )
Is_Rebalance_Go = False


#최소 매수 금액
minmunMoney = 5500

#내가 가진 잔고 데이터를 다 가져온다.
balances = upbit.get_balances()

TotalMoney = myUpbit.GetTotalMoney(balances) #총 원금 (총 투자원금+ 남은 원화)
TotalRealMoney = myUpbit.GetTotalRealMoney(balances) #총 평가금액

print("TotalMoney", TotalMoney)
print("TotalRealMoney", TotalRealMoney)
#투자 비중 -> 1.0 : 100%  0.5 : 50%   0.1 : 10%
InvestRate = 1.0 #투자 비중은 자금사정에 맞게 수정하세요!

##########################################################################
InvestTotalMoney = TotalMoney * InvestRate 
##########################################################################

print("InvestTotalMoney:", InvestTotalMoney)



#####################################################################################################################################
#####################################################################################################################################
#####################################################################################################################################


#####################################################################################################################################
#####################################################################################################################################
#####################################################################################################################################



#이평선 정보를 읽어온다
CoinFindMaList = list()

#파일 경로입니다.
coinfindma_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FindDoubleMaList_Upbit.json")
#coinfindma_file_path = "/var/autobot/FindDoubleMaList_Upbit.json"
try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(coinfindma_file_path, 'r') as json_file:
        CoinFindMaList = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")
    
    
    
#이평선 정보를 읽어온다
CoinFindMa4hList = list()

#파일 경로입니다.
coinfind4hma_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FindDoubleMaList_Upbit_4h.json")
#coinfind4hma_file_path = "/var/autobot/FindDoubleMaList_Upbit_4h.json"
try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(coinfind4hma_file_path, 'r') as json_file:
        CoinFindMa4hList = json.load(json_file)

except Exception as e:
    print("Exception ", e)


##########################################################



#현재 투자중 상태인 리스트! 
CoinInvestList = list()

#파일 경로입니다.
invest_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), BOT_NAME+"_CoinInvestList.json")
#invest_file_path = "/var/autobot/"+BOT_NAME+"_CoinInvestList.json"
try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(invest_file_path, 'r') as json_file:
        CoinInvestList = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")
    
    
    
#현재 투자중 상태인 리스트! 
CoinInvest_4h_List = list()

#파일 경로입니다.
invest_4h_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), BOT_NAME+"_CoinInvest_List_4h.json")
#invest_4h_file_path = "/var/autobot/"+BOT_NAME+"_CoinInvest_List_4h.json"
try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(invest_4h_file_path, 'r') as json_file:
        CoinInvest_4h_List = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")


##########################################################



#투자 코인 리스트
MyPortfolioList = list()

#리밸런싱 즉 이번에 매매를 해야 되는 코인리스트!
Rebalance_coin = list()

for coin_info in InvestCoinList:

    coin_ticker = coin_info['coin_ticker']
    
    #각 Invest_1d_Rate +  Invest_4h_Rate의 값이 최소0에서 최대 1.0이 된다!
    Invest_1d_Rate = 0
    Invest_4h_Rate = 0
    
    
    
    asset = dict()
    asset['coin_ticker'] = coin_ticker       #종목코드
    
    ####################################################################################################
    ####################################################################################################
    ####################################################################################################
    time.sleep(0.2)
    df = pyupbit.get_ohlcv(coin_ticker,interval="day",count=250) #일봉 
    
    
    #거래대금 10일 평균 계산
    df['value_ma'] = df['value'].rolling(window=10).mean()
    asset['value10ma'] = float(df['value_ma'].iloc[-2])
    
    small_ma = coin_info['small_ma']
    big_ma = coin_info['big_ma']
    

    
    #일봉 기준 이평선 가져오기!
    for maData in CoinFindMaList:
        if maData['coin_ticker'] == coin_ticker:
            #pprint.pprint(maData)
            if maData['RevenueRate'] > 0:
                small_ma,big_ma = maData['ma_str'].split()
            break

    print(small_ma, big_ma)

    df['small_ma'] = df['close'].rolling(int(small_ma)).mean()
    df['big_ma'] = df['close'].rolling(int(big_ma)).mean()
    
    PrevClosePrice = df['close'].iloc[-2]
    df.dropna(inplace=True) #데이터 없는건 날린다!
    

    if coin_ticker not in CoinInvestList:
        if (PrevClosePrice >= df['small_ma'].iloc[-2] and df['small_ma'].iloc[-3] <= df['small_ma'].iloc[-2]) and (PrevClosePrice >= df['big_ma'].iloc[-2] and df['big_ma'].iloc[-3] <= df['big_ma'].iloc[-2]):
            Invest_1d_Rate = 0.5
            
            CoinInvestList.append(coin_ticker)
                    
            #파일에 저장
            with open(invest_file_path, 'w') as outfile:
                json.dump(CoinInvestList, outfile)
                
            Rebalance_coin.append(coin_ticker)
            Is_Rebalance_Go = True
            
    if coin_ticker in CoinInvestList and myUpbit.IsHasCoin(balances,coin_ticker) == True:
        Invest_1d_Rate = 0.5
        if (PrevClosePrice < df['small_ma'].iloc[-2] and df['small_ma'].iloc[-3] > df['small_ma'].iloc[-2]) or (PrevClosePrice < df['big_ma'].iloc[-2] and df['big_ma'].iloc[-3] > df['big_ma'].iloc[-2]):
            Invest_1d_Rate = 0

            CoinInvestList.remove(coin_ticker)
            #파일에 저장
            with open(invest_file_path, 'w') as outfile:
                json.dump(CoinInvestList, outfile)
                
            Rebalance_coin.append(coin_ticker)
            Is_Rebalance_Go = True
                
    ####################################################################################################
    ####################################################################################################
    ####################################################################################################
    
    time.sleep(0.2)
    df = pyupbit.get_ohlcv(coin_ticker,interval="minute240",count=250) #4시간봉 
    small_ma = coin_info['small_ma']
    big_ma = coin_info['big_ma']
    
    #일봉 기준 이평선 가져오기!
    for maData in CoinFindMa4hList:
        if maData['coin_ticker'] == coin_ticker:
            #pprint.pprint(maData)
            if maData['RevenueRate'] > 0:
                small_ma,big_ma = maData['ma_str'].split()
            break


    df['small_ma'] = df['close'].rolling(int(small_ma)).mean()
    df['big_ma'] = df['close'].rolling(int(big_ma)).mean()
    
    PrevClosePrice = df['close'].iloc[-2]
    df.dropna(inplace=True) #데이터 없는건 날린다!
    

    if coin_ticker not in CoinInvest_4h_List:
        if (PrevClosePrice >= df['small_ma'].iloc[-2] and df['small_ma'].iloc[-3] <= df['small_ma'].iloc[-2]) and (PrevClosePrice >= df['big_ma'].iloc[-2] and df['big_ma'].iloc[-3] <= df['big_ma'].iloc[-2]):
            Invest_4h_Rate = 0.5
            
            CoinInvest_4h_List.append(coin_ticker)
                    
            #파일에 저장
            with open(invest_4h_file_path, 'w') as outfile:
                json.dump(CoinInvest_4h_List, outfile)
                
            Rebalance_coin.append(coin_ticker)
            Is_Rebalance_Go = True
            
    if coin_ticker in CoinInvest_4h_List and myUpbit.IsHasCoin(balances,coin_ticker) == True:
        Invest_4h_Rate = 0.5
        if (PrevClosePrice < df['small_ma'].iloc[-2] and df['small_ma'].iloc[-3] > df['small_ma'].iloc[-2]) or (PrevClosePrice < df['big_ma'].iloc[-2] and df['big_ma'].iloc[-3] > df['big_ma'].iloc[-2]):
            Invest_4h_Rate = 0

            CoinInvest_4h_List.remove(coin_ticker)
            #파일에 저장
            with open(invest_4h_file_path, 'w') as outfile:
                json.dump(CoinInvest_4h_List, outfile)
                
            Rebalance_coin.append(coin_ticker)
            Is_Rebalance_Go = True
    ####################################################################################################
    ####################################################################################################
    ####################################################################################################
    
    asset['coin_target_rate'] = coin_info['invest_rate'] * (Invest_1d_Rate +  Invest_4h_Rate)
    asset['coin_rebalance_amt'] = 0  #리밸런싱 수량

    
    print(coin_ticker, "일봉 기준으로 세팅된 투자 비중:", Invest_1d_Rate)
    print(coin_ticker, "4시간봉 기준으로 세팅된 투자 비중:", Invest_4h_Rate)
    print(coin_ticker, "최종 투자 비중:", (Invest_1d_Rate +  Invest_4h_Rate), ", 포트폴리오 대비 투자 비중:",asset['coin_target_rate'])
    
 
    '''
    if myUpbit.IsHasCoin(balances,coin_ticker) == True:
        
        TargetTotalMoney = InvestTotalMoney * 0.995

        #현재 코인의 총 매수금액
        NowCoinTotalMoney = myUpbit.GetCoinNowRealMoney(balances,coin_ticker)
        
        print(NowCoinTotalMoney, " / ", TargetTotalMoney)

        Rate = NowCoinTotalMoney / TargetTotalMoney
        print("--------------> coin_ticker rate : ", Rate, asset['coin_target_rate'] )

        
        #코인 목표 비중과 현재 비중이 다르다.
        if Rate != asset['coin_target_rate']:

            #갭을 구한다!!!
            GapRate =  asset['coin_target_rate'] - Rate
            print("--------------> coin_ticker Gaprate : ", GapRate)


            GapMoney = TargetTotalMoney * abs(GapRate)
            
            if GapMoney >= minmunMoney and abs(GapRate) >= (asset['coin_target_rate'] / 10.0): 
                
                print(coin_ticker, "목표 비중에 10%이상 차이가 발생하여 리밸런싱!!")
                
                Rebalance_coin.append(coin_ticker)
                Is_Rebalance_Go = True
    '''
    

    
    print("일봉 기준 매수 코인..")
    print(CoinInvestList)
    print("4h 기준 매수 코인..")
    print(CoinInvest_4h_List)
    
    MyPortfolioList.append(asset)




Rebalance_coin = list(set(Rebalance_coin)) #중복제거

strResult = "-- 현재 포트폴리오 상황 --\n"

#매수된 자산의 총합!
total_coin_money = 0

#현재 평가금액 기준으로 각 자산이 몇 주씩 매수해야 되는지 계산한다 (포트폴리오 비중에 따라) 이게 바로 리밸런싱 목표치가 됩니다.
for coin_info in MyPortfolioList:

    #내코인 코드
    coin_ticker = coin_info['coin_ticker']
    

    #현재가!
    CurrentPrice = pyupbit.get_current_price(coin_ticker)
    time.sleep(0.2)



 

    print("##### coin_ticker: ", coin_ticker)

    
    #매수할 자산 보유할 자산의 비중을 넣어준다!
    coin_target_rate = float(coin_info['coin_target_rate']) 


        
    coin_eval_totalmoney = myUpbit.GetCoinNowRealMoney(balances,coin_ticker)
        
    #코인의 총 평가금액을 더해준다
    total_coin_money += coin_eval_totalmoney

    #현재 비중
    coin_now_rate = 0
    
    coin_amt = upbit.get_balance(coin_ticker) #현재 수량
    

    #잔고에 있는 경우 즉 이미 매수된 코인의 경우
    if myUpbit.IsHasCoin(balances,coin_ticker) == True:


        coin_now_rate = round((coin_eval_totalmoney / InvestTotalMoney),3)

        print("---> NowRate:", round(coin_now_rate * 100.0,2), "%")

        if coin_ticker in Rebalance_coin:

            if coin_target_rate == 0:
                
                
                
                coin_info['coin_rebalance_amt'] = -coin_amt
                print("!!!!!!!!! SELL")
                
            else:
                #목표한 비중이 다르다면!!
                if coin_now_rate != coin_target_rate:


                    #갭을 구한다!!!
                    GapRate = coin_target_rate - coin_now_rate


                    #그래서 그 갭만큼의 금액을 구한다
                    GapMoney = InvestTotalMoney * abs(GapRate) 
                    #현재가로 나눠서 몇주를 매매해야 되는지 계산한다
                    GapAmt = GapMoney / CurrentPrice


                    #갭이 음수라면! 비중이 더 많으니 팔아야 되는 상황!!! 
                    if GapRate < 0:

                        coin_info['coin_rebalance_amt'] = -GapAmt

                    #갭이 양수라면 비중이 더 적으니 사야되는 상황!
                    else:  
                        coin_info['coin_rebalance_amt'] = GapAmt

    #잔고에 없는 경우
    else:
        if coin_ticker in Rebalance_coin:
            print("---> NowRate: 0%")
            if coin_target_rate > 0:
                # 비중대로 매수할 총 금액을 계산한다 
                BuyMoney = InvestTotalMoney * coin_target_rate
                #매수할 수량을 계산한다!
                BuyAmt = BuyMoney / CurrentPrice
                coin_info['coin_rebalance_amt'] = BuyAmt

        
    #메시지랑 로그를 만들기 위한 문자열 
    line_data = ("=== " + coin_ticker + " === \n비중: " + str(round(coin_now_rate * 100.0,2)) + "/" + str(round(coin_target_rate * 100.0,2)) 
                + "% \n총평가금액: " + str(round(coin_eval_totalmoney,2)) 
                + "\n현재보유수량: " + str(coin_amt) 
                + "\n리밸런싱수량: " + str(coin_info['coin_rebalance_amt']))
    
    # 코인을 보유하고 있을 때만 수익률 표시
    if myUpbit.IsHasCoin(balances,coin_ticker):
        revenue_rate = myUpbit.GetRevenueRate(balances,coin_ticker)
        line_data += "\n수익률: " + str(round(revenue_rate,2)) + "%"
              
    # 개별 메시지 전송 제거 - 통합 메시지로 변경
    strResult += line_data

##########################################################
print("--------------리밸런싱 해야 되는 수량-------------")

data_str = "\n" + PortfolioName + "\n" +  strResult + "\n포트폴리오할당금액: " + str(round(InvestTotalMoney,2)) + "\n매수한자산총액: " + str(round(total_coin_money,2))

#결과를 출력해 줍니다!
print(data_str)

#if Is_Rebalance_Go == True:
#    line_alert.SendMessage("\n포트폴리오할당금액: " + str(round(InvestTotalMoney,2)) + "\n매수한자산총액: " + str(round(total_coin_money,2)))
print("--------------------------------------------")


#'''
#리밸런싱이 가능한 상태
if Is_Rebalance_Go == True:
    # 통합 메시지용 변수들
    sell_messages = []
    buy_messages = []
    
    print("------------------리밸런싱 시작  ---------------------")
    print("--------------매도 (리밸런싱 수량이 마이너스인거)---------------------")
    for coin_info in MyPortfolioList:

        #내코인 코드
        coin_ticker = coin_info['coin_ticker']
        rebalance_amt = coin_info['coin_rebalance_amt']

        #리밸런싱 수량이 마이너스인 것을 찾아 매도 한다!
        if rebalance_amt < 0:
            #매도 전 수익률 계산
            revenue_rate = myUpbit.GetRevenueRate(balances,coin_ticker)
            balances = myUpbit.SellCoinMarket(upbit,coin_ticker,abs(rebalance_amt))
            
            # 수익률에 따른 색상 이모지 선택
            if revenue_rate >= 0:
                color_emoji = "🟢"  # 양수 수익률 - 초록색
            else:
                color_emoji = "🔴"  # 음수 수익률 - 빨간색
            
            sell_messages.append(f"{color_emoji} {coin_ticker}: {abs(rebalance_amt):.6f}개 매도 (수익률: {revenue_rate:+.2f}%)")
            

    print("--------------------------------------------")

    print("--------------매수 ---------------------")
    for coin_info in MyPortfolioList:
        #내코인 코드
        coin_ticker = coin_info['coin_ticker']
        rebalance_amt = coin_info['coin_rebalance_amt']

        #리밸런싱 수량이 플러스인 것을 찾아 매수 한다!
        if rebalance_amt > 0:
            CurrentPrice = pyupbit.get_current_price(coin_ticker)
            
            BuyMoney = abs(rebalance_amt) * CurrentPrice
            
            #거래대금 제한 로직 추가
            Value10Ma = coin_info['value10ma']
            if BuyMoney > Value10Ma / limitDiv:
                BuyMoney = Value10Ma / limitDiv

            #원화 잔고를 가져온다
            won = float(upbit.get_balance("KRW"))
            print("# Remain Won :", won)
            time.sleep(0.004)
            
            if BuyMoney > won:
                BuyMoney = won * 0.99 #수수료 및 슬리피지 고려

            if BuyMoney >= minmunMoney:
                balances = myUpbit.BuyCoinMarket(upbit,coin_ticker,BuyMoney)
                # 매수가격 계산 (실제 매수된 수량으로 나누어 정확한 단가 계산)
                actual_buy_amt = abs(rebalance_amt)
                buy_price = BuyMoney / actual_buy_amt if actual_buy_amt > 0 else CurrentPrice
                buy_messages.append(f"🟢 {coin_ticker}: {actual_buy_amt:.6f}개 매수 (단가: {buy_price:,.0f}원)")

    # 통합 메시지 생성 및 전송
    if sell_messages or buy_messages:
        message = f"📊 {PortfolioName} 리밸런싱 완료!\n\n"
        
        if sell_messages:
            message += "📉 매도 내역:\n" + "\n".join(sell_messages) + "\n\n"
        
        if buy_messages:
            message += "📈 매수 내역:\n" + "\n".join(buy_messages) + "\n\n"
        
        message += f"💰 포트폴리오 할당금액: {InvestTotalMoney:,.0f}원\n"
        message += f"💎 매수한 자산총액: {total_coin_money:,.0f}원"
        
        line_alert.SendMessage(message)
    
    print("------------------리밸런싱 끝---------------------")

# 현재 자산 상태를 JSON 파일에 업데이트
try:
    # JSON 파일 읽기
    with open(coin_info_file_path, 'r', encoding='utf-8') as f:
        coin_info = json.load(f)
    
    # 초기 자본과 현재 자본 계산
    initial_capital = coin_info.get('initial_capital', 1037766)
    current_capital = TotalRealMoney
    
    # 수익률 계산
    if initial_capital > 0:
        profit_rate = ((current_capital - initial_capital) / initial_capital) * 100
    else:
        profit_rate = 0
    
    # 수익금 계산
    profit_amount = current_capital - initial_capital
    
    # 기본 정보 업데이트
    coin_info['current_capital'] = round(current_capital, 2)
    coin_info['profit_rate'] = round(profit_rate, 2)
    coin_info['last_updated'] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # 실제 보유코인 정보 가져오기
    print("📊 실제 보유코인 정보 업데이트 중...")
    balances = upbit.get_balances()
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # coin_details 초기화
    if 'coin_details' not in coin_info:
        coin_info['coin_details'] = {}
    
    coin_details = coin_info['coin_details']
    total_invested = 0
    total_current_value = 0
    
    # 실제 보유코인만 처리
    for balance in balances:
        currency = balance['currency']
        if currency == 'KRW':
            continue  # 원화는 제외
        
        ticker = f"KRW-{currency}"
        quantity = float(balance['balance'])
        avg_buy_price = float(balance['avg_buy_price'])
        
        if quantity > 0:
            # 현재가 조회
            try:
                current_price = pyupbit.get_current_price(ticker)
                if current_price:
                    # 투자 금액과 현재 가치 계산
                    invested_amount = quantity * avg_buy_price
                    current_value = quantity * current_price
                    
                    # 손익 계산
                    profit_loss = current_value - invested_amount
                    profit_rate = (profit_loss / invested_amount * 100) if invested_amount > 0 else 0
                    
                    # 총계에 추가
                    total_invested += invested_amount
                    total_current_value += current_value
                    
                    # 코인별 상세 정보 업데이트
                    coin_details[ticker] = {
                        'current_price': current_price,
                        'quantity': quantity,
                        'total_value': current_value,
                        'profit_loss': round(profit_loss, 2),
                        'profit_rate': round(profit_rate, 2),
                        'avg_buy_price': avg_buy_price,
                        'investment_date': coin_details.get(ticker, {}).get('investment_date', time.strftime("%Y-%m-%d")),
                        'peak_price': coin_details.get(ticker, {}).get('peak_price', current_price),
                        'peak_date': coin_details.get(ticker, {}).get('peak_date', current_time),
                        'mdd': coin_details.get(ticker, {}).get('mdd', 0),
                        'mdd_date': coin_details.get(ticker, {}).get('mdd_date', current_time),
                        'last_trade': current_time,
                        'status': '보유중'
                    }
                    
                    # 최고점 및 MDD 업데이트
                    peak_price = coin_details[ticker]['peak_price']
                    if current_price > peak_price:
                        coin_details[ticker]['peak_price'] = current_price
                        coin_details[ticker]['peak_date'] = current_time
                    
                    # MDD 계산
                    if peak_price > 0:
                        mdd = ((current_price - peak_price) / peak_price) * 100
                        if mdd < coin_details[ticker]['mdd']:
                            coin_details[ticker]['mdd'] = round(mdd, 2)
                            coin_details[ticker]['mdd_date'] = current_time
                    
                    print(f"✅ {ticker}: {quantity}개, 수익률 {profit_rate:.2f}%")
                    
            except Exception as e:
                print(f"⚠️ {ticker} 정보 업데이트 실패: {e}")
                continue
    
    # 포트폴리오 요약 정보 업데이트
    if 'portfolio_summary' not in coin_info:
        coin_info['portfolio_summary'] = {}
    
    portfolio_summary = coin_info['portfolio_summary']
    portfolio_summary['total_invested'] = total_invested
    portfolio_summary['total_current_value'] = total_current_value
    portfolio_summary['total_profit_loss'] = round(profit_amount, 2)
    portfolio_summary['total_profit_rate'] = round(profit_rate, 2)
    portfolio_summary['last_rebalance'] = current_time
    
    # 포트폴리오 최고점 및 MDD 업데이트
    portfolio_peak_value = portfolio_summary.get('portfolio_peak_value', total_current_value)
    if total_current_value > portfolio_peak_value:
        portfolio_summary['portfolio_peak_value'] = total_current_value
        portfolio_summary['portfolio_peak_date'] = current_time
    
    if portfolio_peak_value > 0:
        portfolio_mdd = ((total_current_value - portfolio_peak_value) / portfolio_peak_value) * 100
        if portfolio_mdd < portfolio_summary.get('portfolio_mdd', 0):
            portfolio_summary['portfolio_mdd'] = round(portfolio_mdd, 2)
            portfolio_summary['portfolio_mdd_date'] = current_time
    
    # 거래 이력 업데이트 (간단한 예시)
    if 'trading_history' not in coin_info:
        coin_info['trading_history'] = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'avg_profit_per_trade': 0,
            'largest_gain': 0,
            'largest_loss': 0
        }
    
    # JSON 파일에 저장
    with open(coin_info_file_path, 'w', encoding='utf-8') as f:
        json.dump(coin_info, f, ensure_ascii=False, indent=2)
    
    print(f"✅ JSON 파일 업데이트 완료:")
    print(f"   초기 자본: {initial_capital:,}원")
    print(f"   현재 자본: {current_capital:,.2f}원")
    print(f"   수익금: {profit_amount:+,.2f}원")
    print(f"   수익률: {profit_rate:.2f}%")
    print(f"   실제 보유 코인: {len(coin_details)}개")
    print(f"   총 투자금액: {total_invested:,.0f}원")
    print(f"   포트폴리오 MDD: {portfolio_summary.get('portfolio_mdd', 0):.2f}%")
    
except Exception as e:
    print(f"❌ JSON 파일 업데이트 실패: {e}")
    import traceback
    traceback.print_exc()

# 메모리 정리
cleanup_memory()

#'''