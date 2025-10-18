#-*-coding:utf-8 -*-
'''
바이낸스 선물거래 HMA 더블 이동평균 전략 최적화
3배 레버리지, 롱 포지션만, HMA 사용으로 빠른 신호
자산의 50%는 4시간 전략, 50%는 1일 전략으로 병행

최적 HMA 이평선 조합을 찾아서 JSON 파일로 저장

관련 포스팅
https://blog.naver.com/zacra/223720037831

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.
'''

import ccxt
import myBinance
import ende_key  #암복호화키
import my_key    #바이낸스 시크릿 액세스키

import time
import pandas as pd
import json
import datetime
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
import os

def calculate_hma(df, period):
    """Hull Moving Average 계산"""
    # WMA(Weighted Moving Average) 계산
    def wma(data, period):
        weights = np.arange(1, period + 1)
        return np.average(data, weights=weights)
    
    # HMA 계산
    half_period = int(period / 2)
    sqrt_period = int(np.sqrt(period))
    
    # 1단계: half_period 기간의 WMA
    wma1 = df['close'].rolling(half_period).apply(lambda x: wma(x, half_period))
    
    # 2단계: period 기간의 WMA
    wma2 = df['close'].rolling(period).apply(lambda x: wma(x, period))
    
    # 3단계: 2*WMA1 - WMA2
    raw_hma = 2 * wma1 - wma2
    
    # 4단계: sqrt_period 기간의 WMA
    hma = raw_hma.rolling(sqrt_period).apply(lambda x: wma(x, sqrt_period))
    
    return hma

def GetOhlcv(binance, Ticker, period, count=1000, since=None):
    """OHLCV 데이터를 가져오는 함수"""
    try:
        if since:
            ohlcv_data = binance.fetch_ohlcv(Ticker, period, since=since, limit=count)
        else:
            ohlcv_data = binance.fetch_ohlcv(Ticker, period, limit=count)
        
        if not ohlcv_data:
            return pd.DataFrame()
        
        # DataFrame으로 변환
        df = pd.DataFrame(ohlcv_data, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
        df.set_index('datetime', inplace=True)
        
        return df
    except Exception as e:
        print(f"데이터 가져오기 오류: {e}")
        return pd.DataFrame()

def calculate_moving_averages(df, ma1, ma2):
    """HMA 이동평균선 계산"""
    df[f'{ma1}hma'] = calculate_hma(df, ma1)
    df[f'{ma2}hma'] = calculate_hma(df, ma2)
    return df

def backtest_strategy(df, ma1, ma2, initial_capital=10000, leverage=3, fee=0.0004):
    """
    HMA 더블 이동평균 전략 백테스트
    """
    # HMA 이동평균선 계산
    df = calculate_moving_averages(df, ma1, ma2)
    df.dropna(inplace=True)
    
    # 백테스트 변수 초기화
    position = 0  # 0: 없음, 1: 롱
    entry_price = 0
    entry_time = None
    capital = initial_capital
    equity_curve = []
    trades = []
    
    for i in range(2, len(df)):
        current_price = df['close'].iloc[i]
        current_time = df.index[i]
        
        # HMA 이동평균선 값
        ma1_current = df[f'{ma1}hma'].iloc[i]
        ma1_prev = df[f'{ma1}hma'].iloc[i-1]
        ma1_prev2 = df[f'{ma1}hma'].iloc[i-2]
        
        ma2_current = df[f'{ma2}hma'].iloc[i]
        ma2_prev = df[f'{ma2}hma'].iloc[i-1]
        ma2_prev2 = df[f'{ma2}hma'].iloc[i-2]
        
        close_prev = df['close'].iloc[i-1]
        
        # 포지션이 없는 경우 - 매수 신호 확인
        if position == 0:
            # 골든 크로스: 단기 HMA가 장기 HMA를 상향 돌파하고 둘 다 상승중
            if (close_prev >= ma1_prev and ma1_prev2 <= ma1_prev and 
                close_prev >= ma2_prev and ma2_prev2 <= ma2_prev):
                
                position = 1
                entry_price = current_price
                entry_time = current_time
                
                # 레버리지 적용
                position_size = (capital * leverage) / current_price
                
        # 롱 포지션 보유 중 - 매도 신호 확인
        elif position == 1:
            # 데드 크로스: 단기 HMA가 장기 HMA를 하향 돌파하거나 둘 중 하나라도 하락중
            if (close_prev < ma1_prev and ma1_prev2 > ma1_prev) or (close_prev < ma2_prev and ma2_prev2 > ma2_prev):
                
                # 수익률 계산
                pnl = (current_price - entry_price) / entry_price * leverage
                pnl_amount = capital * pnl
                
                # 수수료 차감
                total_fee = (entry_price + current_price) * position_size * fee
                net_pnl = pnl_amount - total_fee
                
                capital += net_pnl
                
                # 거래 기록
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'pnl': net_pnl,
                    'pnl_pct': pnl * 100
                })
                
                position = 0
                entry_price = 0
                entry_time = None
        
        # 자산 곡선 기록
        if position == 1:
            # 현재 포지션의 미실현 손익 계산
            unrealized_pnl = (current_price - entry_price) / entry_price * leverage
            unrealized_pnl_amount = (initial_capital * leverage) * unrealized_pnl
            current_equity = capital + unrealized_pnl_amount
        else:
            current_equity = capital
            
        equity_curve.append({
            'time': current_time,
            'equity': current_equity,
            'price': current_price
        })
    
    # 마지막 포지션이 열려있다면 강제 청산
    if position == 1:
        final_price = df['close'].iloc[-1]
        pnl = (final_price - entry_price) / entry_price * leverage
        pnl_amount = capital * pnl
        total_fee = (entry_price + final_price) * ((capital * leverage) / entry_price) * fee
        net_pnl = pnl_amount - total_fee
        capital += net_pnl
        
        trades.append({
            'entry_time': entry_time,
            'exit_time': df.index[-1],
            'entry_price': entry_price,
            'exit_price': final_price,
            'pnl': net_pnl,
            'pnl_pct': pnl * 100
        })
    
    # 결과 계산
    total_return = (capital - initial_capital) / initial_capital * 100
    final_equity = capital
    
    # MDD 계산
    equity_values = [e['equity'] for e in equity_curve]
    peak = equity_values[0]
    mdd = 0
    
    for equity in equity_values:
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak * 100
        if drawdown > mdd:
            mdd = drawdown
    
    return {
        'total_return': total_return,
        'final_equity': final_equity,
        'initial_capital': initial_capital,
        'equity_curve': equity_curve,
        'trades': trades,
        'mdd': mdd,
        'trade_count': len(trades),
        'win_trades': len([t for t in trades if t['pnl'] > 0]),
        'ma1': ma1,
        'ma2': ma2
    }

def backtest_combined_strategy(df_1d, df_4h, ma1_1d, ma2_1d, ma1_4h, ma2_4h, 
                              initial_capital=10000, leverage=3, fee=0.0004):
    """
    1일 + 4시간 병행 HMA 전략 백테스트
    자산의 50%는 1일 전략, 50%는 4시간 전략
    """
    # 각 전략별 백테스트 실행
    strategy_1d = backtest_strategy(df_1d.copy(), ma1_1d, ma2_1d, 
                                   initial_capital * 0.5, leverage, fee)
    strategy_4h = backtest_strategy(df_4h.copy(), ma1_4h, ma2_4h, 
                                   initial_capital * 0.5, leverage, fee)
    
    # 통합 결과 계산
    total_final_equity = strategy_1d['final_equity'] + strategy_4h['final_equity']
    total_return = (total_final_equity - initial_capital) / initial_capital * 100
    
    # 통합 자산 곡선 생성 (1일 데이터 기준으로)
    combined_equity_curve = []
    
    for i, row in df_1d.iterrows():
        # 1일 전략의 해당 시점 자산
        equity_1d = strategy_1d['initial_capital']
        for trade in strategy_1d['trades']:
            if trade['entry_time'] <= i <= trade['exit_time']:
                # 거래 중인 경우 미실현 손익 계산
                pnl = (row['close'] - trade['entry_price']) / trade['entry_price'] * leverage
                equity_1d = strategy_1d['initial_capital'] * (1 + pnl)
                break
        
        # 4시간 전략의 해당 시점 자산 (가장 가까운 4시간 데이터 사용)
        equity_4h = strategy_4h['initial_capital']
        for trade in strategy_4h['trades']:
            if trade['entry_time'] <= i <= trade['exit_time']:
                # 거래 중인 경우 미실현 손익 계산
                pnl = (row['close'] - trade['entry_price']) / trade['entry_price'] * leverage
                equity_4h = strategy_4h['initial_capital'] * (1 + pnl)
                break
        
        combined_equity = equity_1d + equity_4h
        combined_equity_curve.append({
            'time': i,
            'equity': combined_equity,
            'price': row['close']
        })
    
    # 통합 MDD 계산
    equity_values = [e['equity'] for e in combined_equity_curve]
    peak = equity_values[0]
    mdd = 0
    
    for equity in equity_values:
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak * 100
        if drawdown > mdd:
            mdd = drawdown
    
    return {
        'total_return': total_return,
        'final_equity': total_final_equity,
        'initial_capital': initial_capital,
        'equity_curve': combined_equity_curve,
        'strategy_1d': strategy_1d,
        'strategy_4h': strategy_4h,
        'mdd': mdd,
        'trade_count': strategy_1d['trade_count'] + strategy_4h['trade_count'],
        'win_trades': strategy_1d['win_trades'] + strategy_4h['win_trades'],
        'ma1_1d': ma1_1d,
        'ma2_1d': ma2_1d,
        'ma1_4h': ma1_4h,
        'ma2_4h': ma2_4h
    }

def test_1d_strategy(args):
    """1일 전략만 테스트 (멀티프로세싱용)"""
    df, ma1, ma2, initial_capital, leverage = args
    
    try:
        result = backtest_strategy(df, ma1, ma2, initial_capital, leverage)
        
        # 점수 계산 (수익률 + MDD 고려, MDD에 더 큰 가중치)
        score = result['total_return'] - result['mdd'] * 0.8
        
        return {
            'score': score,
            'result': result,
            'params': (ma1, ma2)
        }
    except Exception as e:
        return {
            'score': -float('inf'),
            'result': None,
            'params': (ma1, ma2),
            'error': str(e)
        }

def test_4h_strategy(args):
    """4시간 전략만 테스트 (멀티프로세싱용)"""
    df, ma1, ma2, initial_capital, leverage = args
    
    try:
        result = backtest_strategy(df, ma1, ma2, initial_capital, leverage)
        
        # 점수 계산 (수익률 + MDD 고려, MDD에 더 큰 가중치)
        score = result['total_return'] - result['mdd'] * 0.8
        
        return {
            'score': score,
            'result': result,
            'params': (ma1, ma2)
        }
    except Exception as e:
        return {
            'score': -float('inf'),
            'result': None,
            'params': (ma1, ma2),
            'error': str(e)
        }

def test_parameter_combination(args):
    """최종 조합 테스트 (멀티프로세싱용)"""
    df_1d, df_4h, ma1_1d, ma2_1d, ma1_4h, ma2_4h, initial_capital, leverage = args
    
    try:
        result = backtest_combined_strategy(
            df_1d, df_4h, 
            ma1_1d, ma2_1d, ma1_4h, ma2_4h, 
            initial_capital, leverage
        )
        
        # 점수 계산 (수익률 + MDD 고려, MDD에 더 큰 가중치)
        score = result['total_return'] - result['mdd'] * 0.8
        
        return {
            'score': score,
            'result': result,
            'params': (ma1_1d, ma2_1d, ma1_4h, ma2_4h)
        }
    except Exception as e:
        return {
            'score': -float('inf'),
            'result': None,
            'params': (ma1_1d, ma2_1d, ma1_4h, ma2_4h),
            'error': str(e)
        }

def optimize_hma_parameters(df_1d, df_4h, initial_capital=10000, leverage=3, max_workers=4):
    """HMA 파라미터 최적화 - 1일과 4시간 전략을 따로 최적화"""
    print("HMA 파라미터 최적화 시작...")
    
    # HMA 이평선 범위 설정
    ma1_range_1d = range(5, 21)      # 1일 전략 단기 HMA
    ma2_range_1d = range(20, 201)    # 1일 전략 장기 HMA
    ma1_range_4h = range(3, 21)      # 4시간 전략 단기 HMA
    ma2_range_4h = range(10, 101)    # 4시간 전략 장기 HMA
    
    print("=== 1단계: 1일 전략 최적화 ===")
    # 1일 전략만 최적화 (2중 포문)
    combinations_1d = []
    for ma1 in ma1_range_1d:
        for ma2 in ma2_range_1d:
            if ma1 < ma2:  # 단기 < 장기 조건
                combinations_1d.append((df_1d, ma1, ma2, initial_capital * 0.5, leverage))
    
    print(f"1일 전략: {len(combinations_1d)}개 조합 테스트 중...")
    
    # 1일 전략 백테스트 실행
    results_1d = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_params = {executor.submit(test_1d_strategy, combo): combo for combo in combinations_1d}
        
        completed = 0
        for future in as_completed(future_to_params):
            completed += 1
            if completed % 50 == 0:
                print(f"1일 전략 진행률: {completed}/{len(combinations_1d)} ({completed/len(combinations_1d)*100:.1f}%)")
            
            try:
                result = future.result()
                if result['score'] > -float('inf'):
                    results_1d.append(result)
            except Exception as e:
                print(f"1일 전략 백테스트 오류: {e}")
                continue
    
    # 1일 전략 상위 20개 선택
    results_1d.sort(key=lambda x: x['score'], reverse=True)
    top_1d = results_1d[:20]
    print(f"1일 전략 상위 20개 선택 완료")
    
    print("\n=== 2단계: 4시간 전략 최적화 ===")
    # 4시간 전략만 최적화 (2중 포문)
    combinations_4h = []
    for ma1 in ma1_range_4h:
        for ma2 in ma2_range_4h:
            if ma1 < ma2:  # 단기 < 장기 조건
                combinations_4h.append((df_4h, ma1, ma2, initial_capital * 0.5, leverage))
    
    print(f"4시간 전략: {len(combinations_4h)}개 조합 테스트 중...")
    
    # 4시간 전략 백테스트 실행
    results_4h = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_params = {executor.submit(test_4h_strategy, combo): combo for combo in combinations_4h}
        
        completed = 0
        for future in as_completed(future_to_params):
            completed += 1
            if completed % 50 == 0:
                print(f"4시간 전략 진행률: {completed}/{len(combinations_4h)} ({completed/len(combinations_4h)*100:.1f}%)")
            
            try:
                result = future.result()
                if result['score'] > -float('inf'):
                    results_4h.append(result)
            except Exception as e:
                print(f"4시간 전략 백테스트 오류: {e}")
                continue
    
    # 4시간 전략 상위 20개 선택
    results_4h.sort(key=lambda x: x['score'], reverse=True)
    top_4h = results_4h[:20]
    print(f"4시간 전략 상위 20개 선택 완료")
    
    print("\n=== 3단계: 최적 조합 찾기 ===")
    # 상위 결과들을 조합해서 최종 테스트
    combinations_final = []
    for result_1d in top_1d:
        for result_4h in top_4h:
            combinations_final.append((
                df_1d, df_4h,
                result_1d['result']['ma1'], result_1d['result']['ma2'],
                result_4h['result']['ma1'], result_4h['result']['ma2'],
                initial_capital, leverage
            ))
    
    print(f"최종 조합: {len(combinations_final)}개 테스트 중...")
    
    # 최종 조합 백테스트 실행
    best_result = None
    best_score = -float('inf')
    all_results = []
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_params = {executor.submit(test_parameter_combination, combo): combo for combo in combinations_final}
        
        completed = 0
        for future in as_completed(future_to_params):
            completed += 1
            if completed % 20 == 0:
                print(f"최종 조합 진행률: {completed}/{len(combinations_final)} ({completed/len(combinations_final)*100:.1f}%)")
            
            try:
                result_data = future.result()
                if result_data['score'] > best_score:
                    best_score = result_data['score']
                    best_result = result_data['result']
                
                if result_data['score'] > -float('inf'):
                    all_results.append(result_data)
                    
            except Exception as e:
                print(f"최종 조합 백테스트 오류: {e}")
                continue
    
    # 상위 결과 정렬
    all_results.sort(key=lambda x: x['score'], reverse=True)
    top_results = all_results[:100]
    
    return best_result, top_results

def save_optimization_results(best_result, top_results, ticker, backtest_date):
    """최적화 결과를 JSON 파일로 저장"""
    
    # 최적 결과 데이터
    result_data = {
        'ticker': ticker,
        'strategy': 'HMA_Double_MA_Combined',
        'optimization_date': backtest_date,
        'best_combination': {
            '1d_strategy': {
                'ma1': best_result['ma1_1d'],
                'ma2': best_result['ma2_1d'],
                'total_return': best_result['strategy_1d']['total_return'],
                'mdd': best_result['strategy_1d']['mdd'],
                'trade_count': best_result['strategy_1d']['trade_count']
            },
            '4h_strategy': {
                'ma1': best_result['ma1_4h'],
                'ma2': best_result['ma2_4h'],
                'total_return': best_result['strategy_4h']['total_return'],
                'mdd': best_result['strategy_4h']['mdd'],
                'trade_count': best_result['strategy_4h']['trade_count']
            },
            'combined_result': {
                'total_return': best_result['total_return'],
                'final_equity': best_result['final_equity'],
                'mdd': best_result['mdd'],
                'trade_count': best_result['trade_count'],
                'win_rate': best_result['win_trades']/best_result['trade_count']*100 if best_result['trade_count'] > 0 else 0
            }
        },
        'top_100_combinations': []
    }
    
    # 상위 100개 결과 추가
    for i, result in enumerate(top_results):
        result_data['top_100_combinations'].append({
            'rank': i + 1,
            'score': result['score'],
            '1d_strategy': {
                'ma1': result['result']['ma1_1d'],
                'ma2': result['result']['ma2_1d'],
                'total_return': result['result']['strategy_1d']['total_return'],
                'mdd': result['result']['strategy_1d']['mdd']
            },
            '4h_strategy': {
                'ma1': result['result']['ma1_4h'],
                'ma2': result['result']['ma2_4h'],
                'total_return': result['result']['strategy_4h']['total_return'],
                'mdd': result['result']['strategy_4h']['mdd']
            },
            'combined_result': {
                'total_return': result['result']['total_return'],
                'mdd': result['result']['mdd']
            }
        })
    
    # 파일명 생성
    filename = f'HMA_Optimization_Results_{ticker.replace("/", "_")}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    # 현재 스크립트 파일의 디렉토리에 저장
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, filename)
    
    # 파일 저장
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"최적화 결과가 {filename}에 저장되었습니다.")
    return filename

def main():
    """메인 함수"""
    print("바이낸스 선물거래 HMA 더블 이동평균 전략 최적화 시작!")
    print("자산의 50%는 1일 전략, 50%는 4시간 전략으로 병행")
    
    # 암복호화 클래스 객체 생성
    simpleEnDecrypt = myBinance.SimpleEnDecrypt(ende_key.ende_key)
    
    # 암호화된 액세스키와 시크릿키를 읽어 복호화
    Binance_AccessKey = simpleEnDecrypt.decrypt(my_key.binance_access)
    Binance_ScretKey = simpleEnDecrypt.decrypt(my_key.binance_secret)
    
    # binance 객체 생성 (선물거래용)
    binanceX = ccxt.binance(config={
        'apiKey': Binance_AccessKey, 
        'secret': Binance_ScretKey,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future'  # 선물거래
        }
    })
    
    # 백테스트 설정
    ticker = "BTC/USDT"
    initial_capital = 10000  # 초기 자본
    leverage = 3  # 3배 레버리지
    
    # 2024년 데이터 가져오기
    start_date = datetime.datetime(2024, 1, 1)
    start_timestamp = int(start_date.timestamp() * 1000)
    
    print(f"{ticker} 2024년 데이터 수집 중...")
    
    # 1일봉 데이터
    df_1d = GetOhlcv(binanceX, ticker, '1d', count=400, since=start_timestamp)
    time.sleep(0.2)
    
    # 4시간봉 데이터
    df_4h = GetOhlcv(binanceX, ticker, '4h', count=400, since=start_timestamp)
    
    if df_1d.empty or df_4h.empty:
        print("데이터를 가져올 수 없습니다.")
        return
    
    print(f"1일봉 데이터 수집 완료: {len(df_1d)}개 캔들")
    print(f"4시간봉 데이터 수집 완료: {len(df_4h)}개 캔들")
    print(f"기간: {df_1d.index[0]} ~ {df_1d.index[-1]}")
    
    # HMA 파라미터 최적화 실행
    print("\nHMA 파라미터 최적화 시작...")
    best_result, top_results = optimize_hma_parameters(df_1d, df_4h, initial_capital, leverage)
    
    if best_result:
        print(f"\n=== 최적 HMA 이평선 조합 발견 ===")
        print(f"1일 전략 - 단기 HMA: {best_result['ma1_1d']}일, 장기 HMA: {best_result['ma2_1d']}일")
        print(f"4시간 전략 - 단기 HMA: {best_result['ma1_4h']}시간, 장기 HMA: {best_result['ma2_4h']}시간")
        print(f"총 수익률: {best_result['total_return']:.2f}%")
        print(f"최종 자산: {best_result['final_equity']:.2f} USDT")
        print(f"최대 낙폭 (MDD): {best_result['mdd']:.2f}%")
        print(f"총 거래 횟수: {best_result['trade_count']}회")
        print(f"승률: {best_result['win_trades']/best_result['trade_count']*100:.1f}%" if best_result['trade_count'] > 0 else "승률: 거래 없음")
        
        print(f"\n=== 개별 전략 결과 ===")
        print(f"1일 전략 - 수익률: {best_result['strategy_1d']['total_return']:.2f}%, MDD: {best_result['strategy_1d']['mdd']:.2f}%")
        print(f"4시간 전략 - 수익률: {best_result['strategy_4h']['total_return']:.2f}%, MDD: {best_result['strategy_4h']['mdd']:.2f}%")
        
        # 결과를 파일로 저장
        backtest_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        filename = save_optimization_results(best_result, top_results, ticker, backtest_date)
        
        print(f"\n최적화 완료! 결과가 {filename}에 저장되었습니다.")
        print("이제 HMA_Backtest.py를 사용하여 저장된 결과를 테스트할 수 있습니다.")
        
    else:
        print("적절한 HMA 이평선 조합을 찾을 수 없습니다.")

if __name__ == "__main__":
    main()
