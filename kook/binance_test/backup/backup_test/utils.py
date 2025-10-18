# -*- coding: utf-8 -*-
"""
스캘핑 최적화 유틸리티 함수들
"""

import os
import json
import glob
from datetime import datetime
import itertools
import pandas as pd
from config import (
    PROGRESS_FILE, RESULTS_CSV, RESULTS_JSON, REALTIME_LOG,
    FAST_WINDOWS, SLOW_WINDOWS, STOP_LOSSES, VOL_MULTIPLIERS, 
    MIN_FILTER_COUNTS, TIMEFRAMES
)


def load_progress():
    """진행상태 파일 불러오기"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_progress(progress: dict):
    """진행상태 파일 저장 (백업 포함)"""
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    # 백업 저장
    try:
        if os.path.exists(PROGRESS_FILE):
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            os.replace(PROGRESS_FILE, PROGRESS_FILE + f'.bak')
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
    """파라미터 그리드 생성"""
    # fast < slow 조합만 사용
    combos = [(f, s) for f in FAST_WINDOWS for s in SLOW_WINDOWS if f < s]

    # (f, s, sl, vm, mfc, tfm) 튜플 목록 반환
    grid = [
        (f, s, sl, vm, mfc, tfm)
        for (f, s), sl, vm, mfc, tfm in itertools.product(
            combos, STOP_LOSSES, VOL_MULTIPLIERS, MIN_FILTER_COUNTS, TIMEFRAMES
        )
    ]
    return grid


def save_results(results: list, progress: dict):
    """결과 저장 (CSV, JSON)"""
    try:
        os.makedirs(os.path.dirname(RESULTS_CSV), exist_ok=True)
        pd.DataFrame(results).to_csv(RESULTS_CSV, index=False, encoding='utf-8-sig')
        with open(RESULTS_JSON, 'w', encoding='utf-8') as f:
            json.dump({'results': results}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_realtime(f'⚠️ 중간결과 저장 실패: {e}')


def save_final_results(results: list):
    """최종 결과 저장"""
    if not results:
        return
    
    df_r = pd.DataFrame(results)
    best_by_return = df_r.loc[df_r['total_return'].idxmax()]
    best_by_mdd = df_r.loc[df_r['mdd'].idxmin()]
    
    # 최종 저장(덮어쓰기)
    df_r.to_csv(RESULTS_CSV, index=False, encoding='utf-8-sig')
    with open(RESULTS_JSON, 'w', encoding='utf-8') as f:
        json.dump({'results': results, 'summary': {
            'best_by_return': best_by_return.to_dict(),
            'best_by_mdd': best_by_mdd.to_dict(),
        }}, f, ensure_ascii=False, indent=2)
    
    return best_by_return, best_by_mdd


def save_profitable_results(results: list):
    """수익률이 양수인 결과만 별도 저장"""
    if not results:
        return
    
    # 수익률이 양수인 결과만 필터링
    profitable_results = [r for r in results if r['total_return'] > 0]
    
    if not profitable_results:
        log_realtime('⚠️ 수익률이 양수인 결과가 없습니다.')
        return
    
    # 수익률 기준으로 정렬 (높은 순)
    profitable_results.sort(key=lambda x: x['total_return'], reverse=True)
    
    # 파일 경로 설정
    script_dir = os.path.dirname(os.path.abspath(__file__))
    profitable_csv = os.path.join(script_dir, 'logs', 'Scalp_Opt_Profitable_Results.csv')
    profitable_json = os.path.join(script_dir, 'logs', 'Scalp_Opt_Profitable_Results.json')
    
    try:
        os.makedirs(os.path.dirname(profitable_csv), exist_ok=True)
        
        # CSV 저장
        df_profitable = pd.DataFrame(profitable_results)
        df_profitable.to_csv(profitable_csv, index=False, encoding='utf-8-sig')
        
        # JSON 저장 (요약 정보 포함)
        summary = {
            'total_profitable': len(profitable_results),
            'total_results': len(results),
            'profit_ratio': len(profitable_results) / len(results) * 100,
            'best_return': profitable_results[0]['total_return'],
            'avg_return': sum(r['total_return'] for r in profitable_results) / len(profitable_results),
            'results': profitable_results
        }
        
        with open(profitable_json, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        log_realtime(f'✅ 수익률 양수 결과 저장 완료: {len(profitable_results):,}개')
        log_realtime(f'   📊 수익률 비율: {summary["profit_ratio"]:.1f}%')
        log_realtime(f'   📈 최고 수익률: {summary["best_return"]:+.2f}%')
        log_realtime(f'   📊 평균 수익률: {summary["avg_return"]:+.2f}%')
        
        return profitable_results, summary
        
    except Exception as e:
        log_realtime(f'⚠️ 수익률 양수 결과 저장 실패: {e}')
        return None, None
