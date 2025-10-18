# -*- coding: utf-8 -*-
"""
수익률이 양수인 결과만 추출하여 최고수익률 기준으로 정렬하는 스크립트
- 기존 결과 파일에서 수익률 > 0인 결과만 필터링
- 최고수익률 기준 내림차순 정렬
- 별도 CSV/JSON 파일로 저장

사용법:
  python extract_profitable_results.py
"""

import os
import pandas as pd
import json
from datetime import datetime

def extract_profitable_results():
    """수익률이 양수인 결과만 추출하여 저장"""
    
    # 파일 경로 설정
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_csv = os.path.join(script_dir, 'logs', 'Scalp_Opt_Results.csv')
    output_csv = os.path.join(script_dir, 'logs', 'Profitable_Results_Sorted.csv')
    output_json = os.path.join(script_dir, 'logs', 'Profitable_Results_Sorted.json')
    
    print(f"📁 입력 파일: {input_csv}")
    print(f"📁 출력 CSV: {output_csv}")
    print(f"📁 출력 JSON: {output_json}")
    print("=" * 60)
    
    # 파일 존재 확인
    if not os.path.exists(input_csv):
        print(f"❌ 입력 파일을 찾을 수 없습니다: {input_csv}")
        return
    
    try:
        # CSV 파일 읽기
        print("📖 결과 파일 읽는 중...")
        df = pd.read_csv(input_csv, encoding='utf-8-sig')
        print(f"✅ 총 {len(df):,}개 결과 로드 완료")
        
        # 컬럼명 확인 및 수정
        print("\n📊 컬럼 정보:")
        print(df.columns.tolist())
        
        # 수익률 컬럼 찾기 (total_return 또는 유사한 컬럼)
        return_col = None
        for col in df.columns:
            if 'return' in col.lower() or 'profit' in col.lower():
                return_col = col
                break
        
        if return_col is None:
            print("❌ 수익률 컬럼을 찾을 수 없습니다.")
            print("사용 가능한 컬럼:", df.columns.tolist())
            return
        
        print(f"💰 수익률 컬럼: {return_col}")
        
        # 수익률이 양수인 결과만 필터링
        print(f"\n🔍 수익률 > 0인 결과 필터링 중...")
        profitable_df = df[df[return_col] > 0].copy()
        
        if len(profitable_df) == 0:
            print("⚠️ 수익률이 양수인 결과가 없습니다.")
            return
        
        print(f"✅ 수익률 양수 결과: {len(profitable_df):,}개")
        
        # 최고수익률 기준으로 내림차순 정렬
        print(f"\n📈 최고수익률 기준으로 정렬 중...")
        profitable_df_sorted = profitable_df.sort_values(by=return_col, ascending=False)
        
        # 상위 10개 결과 미리보기
        print(f"\n🏆 상위 10개 수익률 전략:")
        print("=" * 80)
        for i, (idx, row) in enumerate(profitable_df_sorted.head(10).iterrows(), 1):
            print(f"{i:2d}. {row[return_col]:+.2f}% | ", end="")
            
            # 주요 파라미터 출력
            if 'fast_ma' in row and 'slow_ma' in row:
                print(f"f={row['fast_ma']}, s={row['slow_ma']}, ", end="")
            if 'timeframe_minutes' in row:
                print(f"tf={row['timeframe_minutes']}m, ", end="")
            if 'stop_loss_pct' in row:
                print(f"sl={row['stop_loss_pct']*100:.2f}%, ", end="")
            if 'volume_multiplier' in row:
                print(f"vm={row['volume_multiplier']:.2f}, ", end="")
            if 'min_pass_filters' in row:
                print(f"mfc={row['min_pass_filters']:02d}")
            print()
        
        # 통계 정보
        print(f"\n📊 수익률 통계:")
        print("=" * 40)
        print(f"총 결과 수: {len(df):,}개")
        print(f"수익률 양수: {len(profitable_df):,}개")
        print(f"수익률 음수: {len(df) - len(profitable_df):,}개")
        print(f"수익률 양수 비율: {len(profitable_df)/len(df)*100:.1f}%")
        print(f"최고 수익률: {profitable_df_sorted[return_col].max():+.2f}%")
        print(f"최저 수익률: {profitable_df_sorted[return_col].min():+.2f}%")
        print(f"평균 수익률: {profitable_df_sorted[return_col].mean():+.2f}%")
        
        # CSV 파일로 저장
        print(f"\n💾 CSV 파일 저장 중...")
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        profitable_df_sorted.to_csv(output_csv, index=False, encoding='utf-8-sig')
        print(f"✅ CSV 저장 완료: {output_csv}")
        
        # JSON 파일로 저장 (요약 정보 포함)
        print(f"💾 JSON 파일 저장 중...")
        summary = {
            'extraction_time': datetime.now().isoformat(),
            'total_results': len(df),
            'profitable_results': len(profitable_df),
            'profit_ratio': len(profitable_df)/len(df)*100,
            'best_return': profitable_df_sorted[return_col].max(),
            'worst_return': profitable_df_sorted[return_col].min(),
            'avg_return': profitable_df_sorted[return_col].mean(),
            'top_10_strategies': profitable_df_sorted.head(10).to_dict('records'),
            'all_profitable_results': profitable_df_sorted.to_dict('records')
        }
        
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON 저장 완료: {output_json}")
        
        # 파일 크기 비교
        input_size = os.path.getsize(input_csv) / (1024*1024)  # MB
        output_size = os.path.getsize(output_csv) / (1024*1024)  # MB
        
        print(f"\n📁 파일 크기 비교:")
        print(f"입력 파일: {input_size:.1f} MB")
        print(f"출력 파일: {output_size:.1f} MB")
        print(f"압축률: {(1 - output_size/input_size)*100:.1f}%")
        
        print(f"\n🎉 수익률 양수 결과 추출 완료!")
        print(f"📊 총 {len(profitable_df):,}개 전략을 최고수익률 순으로 정렬하여 저장했습니다.")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    extract_profitable_results()
