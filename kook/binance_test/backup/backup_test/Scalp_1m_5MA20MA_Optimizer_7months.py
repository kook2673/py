# -*- coding: utf-8 -*-
"""
1분/3분/5분 스캘핑(일반화 MA) 최적화 스크립트 - 7개월 통합 버전
- 2025년 1월부터 7월까지 모든 데이터를 합산하여 최적화
- 빠른/느린 MA 기간, 손절 비율, 거래량 배수, 필터 최소 통과 개수, 타임프레임(1/3/5분)을 그리드 탐색
- 병렬 처리 지원 (멀티프로세스)
- 진행상태를 JSON에 저장하여, 중단 후 재실행 시 이어서 진행
- 개별 전략 결과를 로깅하고, 최종 종합 결과 CSV/JSON으로 저장

사용법:
  python Scalp_1m_5MA20MA_Optimizer_7months.py
"""

import os
import json
import glob
from datetime import datetime
import itertools
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

import numpy as np
import pandas as pd

from Scalp_1m_5MA20MA_Backtest import backtest

# 로그 파일 경로 (스크립트 위치 기준)
script_dir = os.path.dirname(os.path.abspath(__file__))
PROGRESS_FILE = os.path.join(script_dir, 'logs', 'Scalp_Opt_7months_Progress.json')
RESULTS_CSV = os.path.join(script_dir, 'logs', 'Scalp_Opt_7months_Results.csv')
RESULTS_JSON = os.path.join(script_dir, 'logs', 'Scalp_Opt_7months_Results.json')
REALTIME_LOG = os.path.join(script_dir, 'logs', 'Scalp_Opt_7months_Realtime.log')
# 플러스 결과만 저장하는 파일들
POSITIVE_RESULTS_CSV = os.path.join(script_dir, 'logs', 'Scalp_Opt_7months_Positive_Results.csv')
POSITIVE_RESULTS_JSON = os.path.join(script_dir, 'logs', 'Scalp_Opt_7months_Positive_Results.json')

# 워커 프로세스가 공유할 데이터프레임 (각 워커에서 1회만 로드)
_SHARED_DF = None


def _init_worker(data_dir: str):
    """워커 초기화: 7개월 데이터를 한 번에 로드"""
    global _SHARED_DF
    try:
        print(f"📥 워커에서 7개월 데이터 로드 중...")
        
        # 2025년 1월부터 7월까지 모든 CSV 파일 찾기
        all_files = []
        for month in range(1, 8):
            month_pattern = f'2025-{month:02d}.csv'
            files = glob.glob(os.path.join(data_dir, month_pattern))
            all_files.extend(files)
        
        if not all_files:
            raise RuntimeError(f"데이터 파일을 찾을 수 없습니다: {data_dir}")
        
        print(f"📁 총 {len(all_files)}개 파일 발견")
        
        # 모든 파일을 순서대로 로드하고 합치기
        dfs = []
        for f in sorted(all_files):
            month_name = os.path.basename(f).split('.')[0]
            print(f"📖 {month_name} 데이터 로드 중...")
            df = pd.read_csv(f, index_col='timestamp', parse_dates=True)
            dfs.append(df)
            print(f"✅ {month_name}: {len(df):,}개 데이터 로드 완료")
        
        # 모든 데이터를 하나로 합치기
        _SHARED_DF = pd.concat(dfs).sort_index().drop_duplicates()
        print(f"🎉 7개월 통합 데이터 로드 완료: 총 {len(_SHARED_DF):,}개 데이터")
        
    except Exception as e:
        _SHARED_DF = None
        raise RuntimeError(f'워커 데이터 로드 실패: {e}')


def _run_single(params):
    """워커에서 실행될 단일 조합 실행 함수.
    params: (fast_w, slow_w, sl, vm, mfc, tfm)
    """
    global _SHARED_DF
    fast_w, slow_w, sl, vm, mfc, tfm = params

    key = f'f{fast_w}_s{slow_w}_sl{sl}_vm{vm}_mfc{mfc}_tfm{tfm}'

    if _SHARED_DF is None:
        raise RuntimeError('Shared DF not initialized in worker')

    # 7개월 통합 데이터로 백테스트 실행
    result = backtest(
        _SHARED_DF,
        stop_loss_pct=sl,
        fee=0.0005,
        leverage=10,
        volume_window=20,
        volume_multiplier=vm,
        min_pass_filters=mfc,
        risk_fraction=1.0,
        fast_ma_window=fast_w,
        slow_ma_window=slow_w,
        timeframe_minutes=tfm,
    )

    out = {
        'key': key,
        'fast_ma': fast_w,
        'slow_ma': slow_w,
        'stop_loss_pct': sl,
        'volume_multiplier': vm,
        'min_pass_filters': mfc,
        'timeframe_minutes': tfm,
        'total_return': result['total_return'],
        'mdd': result['mdd'],
        'final_capital': result['final_capital'],
        'trades': len([t for t in result['trades'] if t['type'] != 'LONG_ENTRY']),
        'win_rate': calculate_win_rate(result['trades']),
        'avg_trade_return': calculate_avg_trade_return(result['trades']),
        'max_consecutive_losses': calculate_max_consecutive_losses(result['trades']),
        'sharpe_ratio': calculate_sharpe_ratio(result['trades']),
        'data_points': len(_SHARED_DF),
        'test_period': '2025-01 to 2025-07'
    }
    return out


def calculate_win_rate(trades):
    """승률 계산"""
    if not trades:
        return 0.0
    
    winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
    return len(winning_trades) / len(trades) * 100


def calculate_avg_trade_return(trades):
    """평균 거래 수익률 계산"""
    if not trades:
        return 0.0
    
    total_pnl = sum(t.get('pnl', 0) for t in trades)
    return total_pnl / len(trades)


def calculate_max_consecutive_losses(trades):
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


def calculate_sharpe_ratio(trades):
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


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_progress(progress: dict):
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    # 백업 저장
    try:
        if os.path.exists(PROGRESS_FILE):
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            os.replace(PROGRESS_FILE, PROGRESS_FILE + f'.bak_{ts}')
    except Exception:
        pass
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def log_realtime(message: str):
    """실시간 진행상황을 파일과 콘솔에 동시 출력"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}] {message}"
    
    # 콘솔 출력
    print(log_message)
    
    # 파일에 저장
    try:
        os.makedirs(os.path.dirname(REALTIME_LOG), exist_ok=True)
        with open(REALTIME_LOG, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')
    except Exception as e:
        print(f"⚠️ 실시간 로그 저장 실패: {e}")


def generate_param_grid():
    # 조정 가능: 범위를 넓히면 시간이 급증
    fast_windows = list(range(3, 21))        # 3~20
    slow_windows = list(range(20, 61, 5))    # 20~60 step=5
    # 손절 비율을 더 촘촘하게: 0.03%~0.30% 근처 구간 포함
    stop_losses = [0.0003, 0.0005, 0.0007, 0.0010, 0.0015, 0.0020, 0.0030]
    vol_multipliers = [1.0, 1.1, 1.2, 1.3]
    min_filter_counts = list(range(0, 11, 2))
    timeframes = [1, 3, 5]  # 1분, 3분, 5분 탐색

    # fast < slow 조합만 사용
    combos = [(f, s) for f in fast_windows for s in slow_windows if f < s]

    # (f, s, sl, vm, mfc, tfm) 튜플 목록 반환
    grid = [
        (f, s, sl, vm, mfc, tfm)
        for (f, s), sl, vm, mfc, tfm in itertools.product(
            combos, stop_losses, vol_multipliers, min_filter_counts, timeframes
        )
    ]
    return grid


def main():
    log_realtime('🚀 스캘핑 최적화 시작 (7개월 통합 데이터, 병렬, 재개 지원)')
    log_realtime('=' * 70)

    # 데이터 경로 (워커 초기화용)
    data_dir = os.path.join(script_dir, 'data', 'BTC_USDT', '1m')
    
    # 7개월 데이터 존재 확인
    available_months = []
    for month in range(1, 8):
        month_pattern = f'2025-{month:02d}.csv'
        files = glob.glob(os.path.join(data_dir, month_pattern))
        if files:
            available_months.append(f'2025-{month:02d}')
    
    if not available_months:
        log_realtime(f"❌ 7개월 데이터를 찾을 수 없습니다: {data_dir}")
        return
    
    log_realtime(f"📅 사용 가능한 월: {', '.join(available_months)}")
    log_realtime(f"📊 총 {len(available_months)}개 월 데이터로 최적화 진행")

    # 파라미터 그리드
    grid = generate_param_grid()
    total = len(grid)
    log_realtime(f'총 조합 수: {total:,}개')

    # 진행상태 불러오기
    progress = load_progress()
    done_set = set(progress.get('done_keys', []))

    # 미완료 조합만 필터링
    pending = []
    for f, s, sl, vm, mfc, tfm in grid:
        key = f'f{f}_s{s}_sl{sl}_vm{vm}_mfc{mfc}_tfm{tfm}'
        if key not in done_set:
            pending.append((f, s, sl, vm, mfc, tfm))
    log_realtime(f'대기 작업: {len(pending):,}개 (이미 완료: {len(done_set):,}개)')

    if not pending:
        log_realtime('✅ 진행할 작업이 없습니다. (모두 완료)')
        return

    # 워커 수 결정 (7800X3D 8코어 16스레드에 최적화)
    max_workers = max(1, min((multiprocessing.cpu_count() or 2) - 1, 13))
    log_realtime(f'병렬 워커 수: {max_workers}개')

    results = []

    # 워커 초기화(7개월 데이터 1회 로드)
    with ProcessPoolExecutor(max_workers=max_workers, initializer=_init_worker, initargs=(data_dir,)) as ex:
        futures = {ex.submit(_run_single, p): p for p in pending}
        for i, fut in enumerate(as_completed(futures), start=1):
            params = futures[fut]
            try:
                out = fut.result()
                results.append(out)
                done_set.add(out['key'])

                # 진행중 출력
                sign = '🟢' if out['total_return'] > 0 else '🔴'
                log_realtime(f"{sign} {i}/{len(pending)} | tf={out['timeframe_minutes']}m, f={out['fast_ma']}, s={out['slow_ma']}, sl={out['stop_loss_pct']*100:.2f}%, vm={out['volume_multiplier']:.2f}, mfc={out['min_pass_filters']:02d} => ret={out['total_return']:+.2f}% MDD={out['mdd']:.2f}%")

            except Exception as e:
                # 오류난 조합도 키 기록해 중복 시도 방지
                f, s, sl, vm, mfc, tfm = params
                key = f'f{f}_s{s}_sl{sl}_vm{vm}_mfc{mfc}_tfm{tfm}'
                log_realtime(f'❌ 오류: {key} - {e}')
                done_set.add(key)

            # 체크포인트 저장(증분)
            if i % 100 == 0 or i == len(pending):
                progress['done_keys'] = list(done_set)
                progress['last_time'] = datetime.now().isoformat()
                progress['total'] = total
                progress['completed'] = i
                save_progress(progress)

            # 중간 결과 저장
            if i % 1000 == 0 or i == len(pending):
                try:
                    os.makedirs(os.path.dirname(RESULTS_CSV), exist_ok=True)
                    
                    # 전체 결과 저장
                    pd.DataFrame(results).to_csv(RESULTS_CSV, index=False, encoding='utf-8-sig')
                    with open(RESULTS_JSON, 'w', encoding='utf-8') as f:
                        json.dump({'results': results}, f, ensure_ascii=False, indent=2)
                    
                    # 플러스 결과만 따로 저장
                    positive_results = [r for r in results if r['total_return'] > 0]
                    if positive_results:
                        pd.DataFrame(positive_results).to_csv(POSITIVE_RESULTS_CSV, index=False, encoding='utf-8-sig')
                        with open(POSITIVE_RESULTS_JSON, 'w', encoding='utf-8') as f:
                            json.dump({
                                'positive_results': positive_results,
                                'count': len(positive_results),
                                'last_updated': datetime.now().isoformat()
                            }, f, ensure_ascii=False, indent=2)
                        log_realtime(f'💾 중간 결과 저장 완료: {i:,}개 (플러스: {len(positive_results):,}개)')
                    else:
                        log_realtime(f'💾 중간 결과 저장 완료: {i:,}개 (플러스: 0개)')
                        
                except Exception as e:
                    log_realtime(f'⚠️ 중간결과 저장 실패: {e}')

    # 최종 요약
    if results:
        df_r = pd.DataFrame(results)
        
        # 수익률 기준 정렬
        df_sorted = df_r.sort_values('total_return', ascending=False)
        
        # 상위 전략들
        top_strategies = df_sorted.head(10)
        
        log_realtime('\n✅ 최적화 완료')
        log_realtime('=' * 70)
        log_realtime(f'📊 7개월 통합 데이터 최적화 결과 요약:')
        log_realtime(f'총 테스트 전략: {len(results):,}개')
        log_realtime(f'양수 수익률 전략: {len(df_r[df_r["total_return"] > 0]):,}개')
        log_realtime(f'음수 수익률 전략: {len(df_r[df_r["total_return"] <= 0]):,}개')
        
        log_realtime('\n🏆 TOP 10 전략 (7개월 통합 수익률):')
        log_realtime('=' * 100)
        log_realtime(f"{'순위':<4} {'전략키':<35} {'수익률':<10} {'MDD':<8} {'거래수':<8} {'승률':<8} {'샤프비율':<8}")
        log_realtime('-' * 100)
        
        for i, (_, row) in enumerate(top_strategies.iterrows(), 1):
            log_realtime(f"{i:2d}.  {row['key']:<35} {row['total_return']:+8.2f}% {row['mdd']:6.2f}% {row['trades']:8d} {row['win_rate']:6.1f}% {row['sharpe_ratio']:7.2f}")
        
        log_realtime('-' * 100)
        
        # 최고 성과 전략 상세 분석
        best_strategy = df_sorted.iloc[0]
        log_realtime(f'\n🥇 최고 성과 전략: {best_strategy["key"]}')
        log_realtime(f'   7개월 통합 수익률: {best_strategy["total_return"]:+.2f}%')
        log_realtime(f'   최대 MDD: {best_strategy["mdd"]:.2f}%')
        log_realtime(f'   총 거래 수: {best_strategy["trades"]:,}개')
        log_realtime(f'   승률: {best_strategy["win_rate"]:.1f}%')
        log_realtime(f'   샤프 비율: {best_strategy["sharpe_ratio"]:.2f}')
        
        # 최종 저장
        df_sorted.to_csv(RESULTS_CSV, index=False, encoding='utf-8-sig')
        with open(RESULTS_JSON, 'w', encoding='utf-8') as f:
            json.dump({
                'results': results,
                'summary': {
                    'total_strategies': len(results),
                    'positive_strategies': len(df_r[df_r["total_return"] > 0]),
                    'top_10_strategies': top_strategies.to_dict('records'),
                    'best_strategy': best_strategy.to_dict()
                },
                'test_period': '2025-01 to 2025-07',
                'generated_time': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        
        # 플러스 결과만 따로 최종 저장
        positive_results = [r for r in results if r['total_return'] > 0]
        if positive_results:
            df_positive = pd.DataFrame(positive_results).sort_values('total_return', ascending=False)
            df_positive.to_csv(POSITIVE_RESULTS_CSV, index=False, encoding='utf-8-sig')
            with open(POSITIVE_RESULTS_JSON, 'w', encoding='utf-8') as f:
                json.dump({
                    'positive_results': positive_results,
                    'count': len(positive_results),
                    'top_10_positive': df_positive.head(10).to_dict('records'),
                    'best_positive': df_positive.iloc[0].to_dict() if len(df_positive) > 0 else None,
                    'test_period': '2025-01 to 2025-07',
                    'generated_time': datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
        
        log_realtime(f'\n💾 최종 결과 저장 완료:')
        log_realtime(f'   전체 CSV: {RESULTS_CSV}')
        log_realtime(f'   전체 JSON: {RESULTS_JSON}')
        if positive_results:
            log_realtime(f'   플러스 CSV: {POSITIVE_RESULTS_CSV}')
            log_realtime(f'   플러스 JSON: {POSITIVE_RESULTS_JSON}')
            log_realtime(f'   플러스 전략 수: {len(positive_results):,}개')
        
    else:
        log_realtime('❌ 결과 없음')


if __name__ == '__main__':
    main()
