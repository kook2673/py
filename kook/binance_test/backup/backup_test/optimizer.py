# -*- coding: utf-8 -*-
"""
1분/3분/5분 스캘핑(일반화 MA) 최적화 스크립트 - 모듈화 버전
- 빠른/느린 MA 기간, 손절 비율, 거래량 배수, 필터 최소 통과 개수, 타임프레임(1/3/5분)을 그리드 탐색
- 병렬 처리 지원 (멀티프로세스)
- 진행상태를 JSON에 저장하여, 중단 후 재실행 시 이어서 진행
- 개별 전략 결과를 로깅하고, 최종 종합 결과 CSV/JSON으로 저장
- 수익률이 양수인 결과만 별도 파일로 저장
- 메모리 효율적인 배치 처리 지원

사용법:
  python optimizer.py
"""

import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
import gc
import os
import queue
import threading
import time

from config import DATA_DIR, CSV_PATTERN, MAX_WORKERS_LIMIT
from utils import (
    load_progress, save_progress, log_realtime, 
    generate_param_grid, save_results, save_final_results, save_profitable_results,
    load_all_results_from_intermediate_files # 새로 추가
)
from worker import get_worker_initializer, get_single_runner


def results_writer_thread(q, progress):
    """결과를 파일에 쓰는 스레드"""
    log_realtime("📝 파일 쓰기 스레드 시작")
    BATCH_SAVE_SIZE = 1000  # 1000개씩 모아서 파일에 쓰기
    
    results_to_save = []
    
    while True:
        try:
            # 1초 타임아웃으로 주기적으로 체크
            result = q.get(timeout=1)
            
            if result is None:  # 종료 신호
                if results_to_save:
                    log_realtime(f"💾 쓰기 스레드: 마지막 남은 결과 {len(results_to_save)}개 저장")
                    save_results(results_to_save, progress, is_final=False)
                log_realtime("📝 파일 쓰기 스레드 종료")
                break

            results_to_save.append(result)

            if len(results_to_save) >= BATCH_SAVE_SIZE:
                log_realtime(f"💾 쓰기 스레드: 결과 {len(results_to_save)}개 저장")
                save_results(results_to_save, progress, is_final=False)
                results_to_save.clear()

        except queue.Empty:
            # 큐가 비어있으면 계속 대기
            continue
        except Exception as e:
            log_realtime(f"❌ 쓰기 스레드 오류: {e}")


def main():
    """메인 최적화 실행 함수"""
    log_realtime('🚀 스캘핑 최적화 시작 (병렬, 재개 지원) - 모듈화 버전')
    log_realtime('=' * 60)

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
    max_workers = max(1, min((multiprocessing.cpu_count() or 2) - 1, MAX_WORKERS_LIMIT))
    log_realtime(f'병렬 워커 수: {max_workers}개')

    # 결과를 처리할 큐와 파일 쓰기 스레드 설정
    results_queue = queue.Queue()
    writer_thread = threading.Thread(
        target=results_writer_thread, 
        args=(results_queue, progress)
    )
    writer_thread.start()

    # 워커 초기화(데이터 1회 로드)
    with ProcessPoolExecutor(
        max_workers=max_workers, 
        initializer=get_worker_initializer(), 
        initargs=(DATA_DIR, CSV_PATTERN)
    ) as ex:
        futures = {ex.submit(get_single_runner(), p): p for p in pending}
        
        total_pending = len(pending)
        for i, fut in enumerate(as_completed(futures), start=1):
            params = futures[fut]
            try:
                out = fut.result()
                results_queue.put(out)  # 결과를 큐에 넣음
                done_set.add(out['key'])

                # 진행중 출력
                sign = '🟢' if out['total_return'] > 0 else '🔴'
                log_realtime(
                    f"{sign} {i}/{total_pending} | "
                    f"tf={out['timeframe_minutes']}m, "
                    f"f={out['fast_ma']}, s={out['slow_ma']}, "
                    f"sl={out['stop_loss_pct']*100:.2f}%, "
                    f"vm={out['volume_multiplier']:.2f}, "
                    f"mfc={out['min_pass_filters']:02d} => "
                    f"ret={out['total_return']:+.2f}% MDD={out['mdd']:.2f}%"
                )

            except Exception as e:
                # 오류난 조합도 키 기록해 중복 시도 방지
                f, s, sl, vm, mfc, tfm = params
                key = f'f{f}_s{s}_sl{sl}_vm{vm}_mfc{mfc}_tfm{tfm}'
                log_realtime(f'❌ 오류: {key} - {e}')
                done_set.add(key)

            # 체크포인트 저장(증분) - 매 100개마다
            if i % 100 == 0:
                progress['done_keys'] = list(done_set)
                progress['last_time'] = datetime.now().isoformat()
                progress['total'] = total
                save_progress(progress)
    
    # 모든 작업이 끝나면 쓰레드 종료 신호 전송
    results_queue.put(None)
    writer_thread.join() # 쓰레드가 끝날 때까지 대기

    log_realtime("\n✅ 모든 백테스트 완료. 최종 결과 분석 시작...")
    
    # 최종 요약
    all_results = load_all_results_from_intermediate_files()

    if all_results:
        # 최종 결과는 all_results를 사용해 한번만 저장
        best_by_return, best_by_mdd = save_final_results(all_results)
        log_realtime('=' * 60)
        log_realtime(f'총 처리된 조합: {len(all_results):,}개')
        log_realtime('수익률 최고 전략:')
        log_realtime(str(best_by_return))
        log_realtime('\nMDD 최소 전략:')
        log_realtime(str(best_by_mdd))
        
        # 수익률이 양수인 결과만 별도 저장
        log_realtime('\n💰 수익률 양수 결과 분석:')
        log_realtime('=' * 40)
        profitable_results, summary = save_profitable_results(all_results)
        
        if profitable_results:
            log_realtime(f'\n📊 수익률 양수 전략 TOP 5:')
            for i, result in enumerate(profitable_results[:5], 1):
                log_realtime(
                    f"{i:2d}. {result['total_return']:+.2f}% | "
                    f"tf={result['timeframe_minutes']}m, "
                    f"f={result['fast_ma']}, s={result['slow_ma']}, "
                    f"sl={result['stop_loss_pct']*100:.2f}%, "
                    f"vm={result['volume_multiplier']:.2f}, "
                    f"mfc={result['min_pass_filters']:02d}"
                )
    else:
        log_realtime('❌ 결과 없음')


if __name__ == '__main__':
    main()
