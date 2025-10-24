"""
간단한 RSI 봇 그리드 테스트
기존 rsi_bot.py를 직접 수정하여 테스트
"""

import subprocess
import json
import os
from datetime import datetime

def test_parameter_combination(rsi_oversold, rsi_overbought, averaging_conditions, rsi_exit_oversold=40, rsi_exit_overbought=60):
    """특정 파라미터 조합을 테스트"""
    
    # rsi_bot.py 파일을 읽어서 파라미터 수정
    with open('rsi_bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 파라미터 수정
    content = content.replace(
        f"'rsi_oversold': {content.split('rsi_oversold')[1].split(',')[0].split(':')[1].strip()},",
        f"'rsi_oversold': {rsi_oversold},"
    )
    
    content = content.replace(
        f"'rsi_overbought': {content.split('rsi_overbought')[1].split(',')[0].split(':')[1].strip()},",
        f"'rsi_overbought': {rsi_overbought},"
    )
    
    # 물타기 조건 수정
    for i, condition in enumerate(averaging_conditions):
        old_condition = f"{{'price_drop': {content.split('price_drop')[i+1].split('}')[0].split(':')[1].strip()}}}"
        new_condition = f"{{'price_drop': {condition['price_drop']}}}"
        content = content.replace(old_condition, new_condition)
    
    # 청산 조건 수정
    content = content.replace(
        f"'rsi_exit_oversold': {content.split('rsi_exit_oversold')[1].split(',')[0].split(':')[1].strip()},",
        f"'rsi_exit_oversold': {rsi_exit_oversold},"
    )
    
    content = content.replace(
        f"'rsi_exit_overbought': {content.split('rsi_exit_overbought')[1].split(',')[0].split(':')[1].strip()},",
        f"'rsi_exit_overbought': {rsi_exit_overbought},"
    )
    
    # 임시 파일로 저장
    with open('temp_rsi_bot.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    try:
        # 실행
        result = subprocess.run(['python', 'temp_rsi_bot.py'], 
                              capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
                        # 결과에서 수익률 추출
                        output = result.stdout
                        if '총 수익률:' in output:
                            return_line = [line for line in output.split('\n') if '총 수익률:' in line][0]
                            return_pct = float(return_line.split(':')[1].split('%')[0].strip())
                            
                            # 승률 추출
                            win_rate_line = [line for line in output.split('\n') if '승률:' in line][0]
                            win_rate = float(win_rate_line.split(':')[1].split('%')[0].strip())
                            
                            # 거래 수 추출
                            trades_line = [line for line in output.split('\n') if '총 거래 수:' in line][0]
                            total_trades = int(trades_line.split(':')[1].split('회')[0].strip())
                            
                            return {
                                'rsi_oversold': rsi_oversold,
                                'rsi_overbought': rsi_overbought,
                                'rsi_exit_oversold': rsi_exit_oversold,
                                'rsi_exit_overbought': rsi_exit_overbought,
                                'averaging_conditions': averaging_conditions,
                                'total_return': return_pct,
                                'win_rate': win_rate,
                                'total_trades': total_trades,
                                'success': True
                            }
        
        return {
            'rsi_oversold': rsi_oversold,
            'rsi_overbought': rsi_overbought,
            'rsi_exit_oversold': rsi_exit_oversold,
            'rsi_exit_overbought': rsi_exit_overbought,
            'averaging_conditions': averaging_conditions,
            'total_return': -999,
            'win_rate': 0,
            'total_trades': 0,
            'success': False,
            'error': result.stderr
        }
        
    except Exception as e:
        return {
            'rsi_oversold': rsi_oversold,
            'rsi_overbought': rsi_overbought,
            'rsi_exit_oversold': rsi_exit_oversold,
            'rsi_exit_overbought': rsi_exit_overbought,
            'averaging_conditions': averaging_conditions,
            'total_return': -999,
            'win_rate': 0,
            'total_trades': 0,
            'success': False,
            'error': str(e)
        }
    finally:
        # 임시 파일 삭제
        if os.path.exists('temp_rsi_bot.py'):
            os.remove('temp_rsi_bot.py')

def main():
    """메인 실행 함수"""
    print("🚀 간단한 RSI 봇 그리드 테스트 시작")
    print("=" * 50)
    
    results = []
    
    # 테스트할 파라미터 조합 (더 일찍 판매하는 조건 포함)
    test_combinations = [
        # 기존 조합
        (20, 80, [{'price_drop': 0.01}, {'price_drop': 0.01}, {'price_drop': 0.01}]),
        (25, 75, [{'price_drop': 0.01}, {'price_drop': 0.01}, {'price_drop': 0.01}]),
        (30, 70, [{'price_drop': 0.01}, {'price_drop': 0.01}, {'price_drop': 0.01}]),
        (20, 80, [{'price_drop': 0.02}, {'price_drop': 0.05}, {'price_drop': 0.10}]),
        (25, 75, [{'price_drop': 0.02}, {'price_drop': 0.05}, {'price_drop': 0.10}]),
        (30, 70, [{'price_drop': 0.02}, {'price_drop': 0.05}, {'price_drop': 0.10}]),
        
        # 더 극단적인 청산 조건 테스트
        (20, 80, [{'price_drop': 0.02}, {'price_drop': 0.05}, {'price_drop': 0.10}], 30, 70),  # RSI 30/70 청산
        (25, 75, [{'price_drop': 0.02}, {'price_drop': 0.05}, {'price_drop': 0.10}], 30, 70),  # RSI 30/70 청산
        (30, 70, [{'price_drop': 0.02}, {'price_drop': 0.05}, {'price_drop': 0.10}], 30, 70),  # RSI 30/70 청산
        (20, 80, [{'price_drop': 0.02}, {'price_drop': 0.05}, {'price_drop': 0.10}], 35, 65),  # RSI 35/65 청산
        (25, 75, [{'price_drop': 0.02}, {'price_drop': 0.05}, {'price_drop': 0.10}], 35, 65),  # RSI 35/65 청산
        (30, 70, [{'price_drop': 0.02}, {'price_drop': 0.05}, {'price_drop': 0.10}], 35, 65),  # RSI 35/65 청산
    ]
    
    total_combinations = len(test_combinations)
    
    for i, combination in enumerate(test_combinations, 1):
        if len(combination) == 3:
            rsi_oversold, rsi_overbought, averaging_conditions = combination
            rsi_exit_oversold, rsi_exit_overbought = 40, 60  # 기본값
        else:
            rsi_oversold, rsi_overbought, averaging_conditions, rsi_exit_oversold, rsi_exit_overbought = combination
        
        print(f"\n[{i}/{total_combinations}] 테스트 중...")
        print(f"RSI: {rsi_oversold}/{rsi_overbought}, 청산: {rsi_exit_oversold}/{rsi_exit_overbought}, 물타기: {[c['price_drop']*100 for c in averaging_conditions]}%")
        
        result = test_parameter_combination(rsi_oversold, rsi_overbought, averaging_conditions, rsi_exit_oversold, rsi_exit_overbought)
        results.append(result)
        
        if result['success']:
            print(f"✅ 성공! 수익률: {result['total_return']:.2f}%, 승률: {result['win_rate']:.1f}%")
        else:
            print(f"❌ 실패: {result.get('error', 'Unknown error')}")
    
    # 결과 정렬
    successful_results = [r for r in results if r['success']]
    successful_results.sort(key=lambda x: x['total_return'], reverse=True)
    
    # 결과 출력
    print(f"\n🏆 성공한 조합 {len(successful_results)}개:")
    print("=" * 80)
    
    for i, result in enumerate(successful_results, 1):
        averaging_str = [f"{c['price_drop']*100:.1f}%" for c in result['averaging_conditions']]
        print(f"{i:2d}. RSI: {result['rsi_oversold']:2d}/{result['rsi_overbought']:2d} | "
              f"청산: {result['rsi_exit_oversold']:2d}/{result['rsi_exit_overbought']:2d} | "
              f"물타기: {averaging_str} | "
              f"수익률: {result['total_return']:6.2f}% | "
              f"승률: {result['win_rate']:5.1f}% | "
              f"거래수: {result['total_trades']:3d}")
    
    # 수익이 나는 조합만 출력
    profitable = [r for r in successful_results if r['total_return'] > 0]
    
    if profitable:
        print(f"\n💰 수익 조합 {len(profitable)}개:")
        print("=" * 80)
        
        for i, result in enumerate(profitable, 1):
            averaging_str = [f"{c['price_drop']*100:.1f}%" for c in result['averaging_conditions']]
            print(f"{i:2d}. RSI: {result['rsi_oversold']:2d}/{result['rsi_overbought']:2d} | "
                  f"청산: {result['rsi_exit_oversold']:2d}/{result['rsi_exit_overbought']:2d} | "
                  f"물타기: {averaging_str} | "
                  f"수익률: {result['total_return']:6.2f}% | "
                  f"승률: {result['win_rate']:5.1f}% | "
                  f"거래수: {result['total_trades']:3d}")
    else:
        print("\n❌ 수익이 나는 조합이 없습니다.")
    
    # 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"simple_grid_test_results_{timestamp}.json"
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n결과가 저장되었습니다: {results_file}")
    print(f"✅ 테스트 완료! 총 {len(results)}개 조합 테스트")

if __name__ == "__main__":
    main()
