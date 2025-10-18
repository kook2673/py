# -*- coding: utf-8 -*-
"""
1분/3분/5분 스캘핑(일반화 MA) 최적화 스크립트 - 배치 처리 최적화 버전
- 메모리 효율적인 배치 처리로 대용량 데이터 처리
- 증분 저장으로 I/O 부하 최소화
- 진행상태 압축 저장으로 성능 향상

사용법:
  python optimizer_batch.py
"""

import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
import gc
import os

from config import DATA_DIR, CSV_PATTERN, MAX_WORKERS_LIMIT
from utils import (
    load_progress, save_progress, log_realtime, 
    generate_param_grid, save_profitable_results
)
from worker import get_worker_initializer, get_single_runner


class BatchOptimizer:
    """배치 처리 최적화 클래스"""
    
    def __init__(self, batch_size=1000):
        self.batch_size = batch_size
        self.results = []
        self.total_processed = 0
        
    def save_batch_results(self, batch_results: list, batch_num: int):
        """배치 결과를 증분 저장"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            batch_dir = os.path.join(script_dir, 'logs', 'batch_results')
            os.makedirs(batch_dir, exist_ok=True)
            
            # 배치별 CSV 저장
            batch_csv = os.path.join(batch_dir, f'batch_{batch_num:04d}.csv')
            import pandas as pd
            df_batch = pd.DataFrame(batch_results)
            df_batch.to_csv(batch_csv, index=False, encoding='utf-8-sig')
            
            # 배치별 JSON 저장
            batch_json = os.path.join(batch_dir, f'batch_{batch_num:04d}.json')
            import json
            with open(batch_json, 'w', encoding='utf-8') as f:
                json.dump({'batch_num': batch_num, 'results': batch_results}, f, ensure_ascii=False, indent=2)
            
            log_realtime(f'💾 배치 {batch_num} 저장 완료: {len(batch_results):,}개 결과')
            
        except Exception as e:
            log_realtime(f'⚠️ 배치 {batch_num} 저장 실패: {e}')
    
    def merge_all_batches(self):
        """모든 배치 결과를 병합하여 최종 저장"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            batch_dir = os.path.join(script_dir, 'logs', 'batch_results')
            
            if not os.path.exists(batch_dir):
                log_realtime('⚠️ 배치 결과 디렉토리가 없습니다.')
                return
            
            # 모든 배치 파일 찾기
            batch_files = [f for f in os.listdir(batch_dir) if f.endswith('.csv')]
            batch_files.sort()
            
            all_results = []
            for batch_file in batch_files:
                batch_path = os.path.join(batch_dir, batch_file)
                import pandas as pd
                df_batch = pd.read_csv(batch_path, encoding='utf-8-sig')
                all_results.extend(df_batch.to_dict('records'))
            
            log_realtime(f'🔄 배치 결과 병합 완료: 총 {len(all_results):,}개')
            
            # 최종 결과 저장
            from utils import save_final_results, save_profitable_results
            
            best_by_return, best_by_mdd = save_final_results(all_results)
            
            # 수익률 양수 결과 저장
            profitable_results, summary = save_profitable_results(all_results)
            
            return all_results, profitable_results
            
        except Exception as e:
            log_realtime(f'⚠️ 배치 병합 실패: {e}')
            return None, None
    
    def process_batch(self, batch_params, batch_num, max_workers):
        """배치 단위로 처리"""
        batch_results = []
        
        with ProcessPoolExecutor(
            max_workers=max_workers, 
            initializer=get_worker_initializer(), 
            initargs=(DATA_DIR, CSV_PATTERN)
        ) as ex:
            futures = {ex.submit(get_single_runner(), p): p for p in batch_params}
            
            for i, fut in enumerate(as_completed(futures), start=1):
                params = futures[fut]
                try:
                    out = fut.result()
                    batch_results.append(out)
                    
                    # 진행상황 출력
                    sign = '🟢' if out['total_return'] > 0 else '🔴'
                    log_realtime(
                        f"{sign} 배치{batch_num} | {i}/{len(batch_params)} | "
                        f"tf={out['timeframe_minutes']}m, "
                        f"f={out['fast_ma']}, s={out['slow_ma']}, "
                        f"sl={out['stop_loss_pct']*100:.2f}%, "
                        f"vm={out['volume_multiplier']:.2f}, "
                        f"mfc={out['min_pass_filters']:02d} => "
                        f"ret={out['total_return']:+.2f}% MDD={out['mdd']:.2f}%"
                    )
                    
                except Exception as e:
                    f, s, sl, vm, mfc, tfm = params
                    key = f'f{f}_s{s}_sl{sl}_vm{vm}_mfc{mfc}_tfm{tfm}'
                    log_realtime(f'❌ 오류: {key} - {e}')
                
                # 메모리 정리 (100개마다)
                if i % 100 == 0:
                    gc.collect()
        
        return batch_results


def main():
    """메인 최적화 실행 함수"""
    log_realtime('🚀 스캘핑 최적화 시작 (배치 처리 최적화 버전)')
    log_realtime('=' * 60)
    
    # 배치 크기 설정 (메모리 효율성)
    BATCH_SIZE = 1000  # 1000개씩 처리
    
    # 파라미터 그리드
    grid = generate_param_grid()
    total = len(grid)
    log_realtime(f'총 조합 수: {total:,}개')
    log_realtime(f'배치 크기: {BATCH_SIZE:,}개')
    log_realtime(f'총 배치 수: {total // BATCH_SIZE + (1 if total % BATCH_SIZE else 0):,}개')
    
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
    
    # 워커 수 결정
    max_workers = max(1, min((multiprocessing.cpu_count() or 2) - 1, MAX_WORKERS_LIMIT))
    log_realtime(f'병렬 워커 수: {max_workers}개')
    
    # 배치 처리 시작
    optimizer = BatchOptimizer(batch_size=BATCH_SIZE)
    batch_num = 1
    
    for i in range(0, len(pending), BATCH_SIZE):
        batch_params = pending[i:i + BATCH_SIZE]
        log_realtime(f'\n📦 배치 {batch_num} 처리 시작: {len(batch_params):,}개')
        log_realtime('=' * 50)
        
        # 배치 처리
        batch_results = optimizer.process_batch(batch_params, batch_num, max_workers)
        
        # 배치 결과 저장
        optimizer.save_batch_results(batch_results, batch_num)
        
        # 진행상태 업데이트
        for result in batch_results:
            done_set.add(result['key'])
        
        progress['done_keys'] = list(done_set)
        progress['last_time'] = datetime.now().isoformat()
        progress['total'] = total
        progress['batches_completed'] = batch_num
        save_progress(progress)
        
        # 메모리 정리
        del batch_results
        gc.collect()
        
        log_realtime(f'✅ 배치 {batch_num} 완료 | 총 진행률: {len(done_set)/total*100:.1f}%')
        batch_num += 1
    
    # 모든 배치 병합
    log_realtime('\n🔄 모든 배치 결과 병합 중...')
    all_results, profitable_results = optimizer.merge_all_batches()
    
    if all_results:
        log_realtime('\n✅ 최적화 완료')
        log_realtime('=' * 60)
        log_realtime(f'총 처리된 조합: {len(all_results):,}개')
        log_realtime(f'수익률 양수 전략: {len(profitable_results) if profitable_results else 0:,}개')
    else:
        log_realtime('❌ 결과 병합 실패')


if __name__ == '__main__':
    main()
