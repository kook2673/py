# -*- coding: utf-8 -*-
"""
확장 백테스트 전략 설정 파일
- 최고 수익률 전략들을 등급별로 관리
- 새로운 전략 쉽게 추가 가능
- 백테스트 기간 및 설정 관리
"""

# 백테스트 기간 설정
BACKTEST_PERIODS = [
    '2025-01', '2025-02', '2025-03', '2025-04',
    '2025-05', '2025-06', '2025-07'
]

# 백테스트 기본 설정
BACKTEST_CONFIG = {
    'fee': 0.0005,
    'leverage': 10,
    'volume_window': 20,
    'risk_fraction': 1.0
}

# 전략 등급별 설정 (수익률 기준)
STRATEGY_GRADES = {
    'S급': {  # 40% 이상
        'name': 'S급 전략 (40% 이상)',
        'strategies': [
            {
                'id': 'S001',
                'name': '최고 수익률 전략',
                'fast_ma': 17,
                'slow_ma': 35,
                'stop_loss_pct': 0.0015,
                'volume_multiplier': 1.2,
                'min_pass_filters': 2,
                'timeframe_minutes': 5,
                'expected_return': 42.42,
                'description': '3월 데이터 기준 최고 수익률 전략'
            }
        ]
    },
    
    'A급': {  # 30-40%
        'name': 'A급 전략 (30-40%)',
        'strategies': [
            {
                'id': 'A001',
                'name': '고수익 안정 전략',
                'fast_ma': 17,
                'slow_ma': 35,
                'stop_loss_pct': 0.002,
                'volume_multiplier': 1.2,
                'min_pass_filters': 0,
                'timeframe_minutes': 5,
                'expected_return': 42.28,
                'description': '손절 0.2%로 안정성 향상'
            },
            {
                'id': 'A002',
                'name': '거래량 배수 전략',
                'fast_ma': 17,
                'slow_ma': 35,
                'stop_loss_pct': 0.002,
                'volume_multiplier': 1.3,
                'min_pass_filters': 6,
                'timeframe_minutes': 5,
                'expected_return': 41.82,
                'description': '거래량 배수 1.3으로 수익성 향상'
            }
        ]
    },
    
    'B급': {  # 20-30%
        'name': 'B급 전략 (20-30%)',
        'strategies': [
            {
                'id': 'B001',
                'name': '안전 손절 전략',
                'fast_ma': 17,
                'slow_ma': 35,
                'stop_loss_pct': 0.001,
                'volume_multiplier': 1.2,
                'min_pass_filters': 8,
                'timeframe_minutes': 5,
                'expected_return': 39.87,
                'description': '손절 0.1%로 리스크 최소화'
            },
            {
                'id': 'B002',
                'name': '필터 강화 전략',
                'fast_ma': 17,
                'slow_ma': 20,
                'stop_loss_pct': 0.002,
                'volume_multiplier': 1.2,
                'min_pass_filters': 10,
                'timeframe_minutes': 5,
                'expected_return': 34.16,
                'description': '필터 강화로 신호 품질 향상'
            }
        ]
    }
}

# 데이터 경로 설정
DATA_PATHS = {
    'base_dir': 'data/BTC_USDT/1m',
    'file_pattern': '{month}.csv',
    'results_dir': 'logs/extended_backtest'
}

# 성과 분석 지표
PERFORMANCE_METRICS = {
    'return_thresholds': {
        'excellent': 30.0,  # 30% 이상
        'good': 20.0,       # 20-30%
        'fair': 10.0,       # 10-20%
        'poor': 0.0         # 0-10%
    },
    'mdd_thresholds': {
        'excellent': 15.0,  # 15% 이하
        'good': 25.0,       # 15-25%
        'fair': 35.0,       # 25-35%
        'poor': 50.0        # 35% 이상
    },
    'win_rate_thresholds': {
        'excellent': 60.0,  # 60% 이상
        'good': 50.0,       # 50-60%
        'fair': 40.0,       # 40-50%
        'poor': 30.0        # 40% 이하
    }
}

# 확장 설정
EXPANSION_CONFIG = {
    'auto_add_strategies': True,  # 자동으로 새 전략 추가
    'min_performance': 20.0,      # 최소 성과 기준 (20%)
    'max_strategies_per_grade': 10,  # 등급별 최대 전략 수
    'performance_update_frequency': 'monthly'  # 성과 업데이트 주기
}

def get_strategy_by_id(strategy_id):
    """ID로 전략 찾기"""
    for grade, grade_info in STRATEGY_GRADES.items():
        for strategy in grade_info['strategies']:
            if strategy['id'] == strategy_id:
                return strategy, grade
    return None, None

def get_strategies_by_grade(grade):
    """등급별 전략 목록 반환"""
    if grade in STRATEGY_GRADES:
        return STRATEGY_GRADES[grade]['strategies']
    return []

def add_new_strategy(grade, strategy_params):
    """새로운 전략 추가"""
    if grade not in STRATEGY_GRADES:
        print(f"❌ 알 수 없는 등급: {grade}")
        return False
    
    # ID 자동 생성
    existing_ids = [s['id'] for s in STRATEGY_GRADES[grade]['strategies']]
    base_id = grade[0]  # S, A, B
    counter = len(existing_ids) + 1
    new_id = f"{base_id}{counter:03d}"
    
    # 새 전략 추가
    new_strategy = {
        'id': new_id,
        'name': strategy_params.get('name', f'새로운 {grade}급 전략'),
        'fast_ma': strategy_params['fast_ma'],
        'slow_ma': strategy_params['slow_ma'],
        'stop_loss_pct': strategy_params['stop_loss_pct'],
        'volume_multiplier': strategy_params['volume_multiplier'],
        'min_pass_filters': strategy_params['min_pass_filters'],
        'timeframe_minutes': strategy_params['timeframe_minutes'],
        'expected_return': strategy_params.get('expected_return', 0.0),
        'description': strategy_params.get('description', '사용자 정의 전략'),
        'added_time': '2025-08-30'
    }
    
    STRATEGY_GRADES[grade]['strategies'].append(new_strategy)
    print(f"✅ {grade}급 전략 추가됨: {new_id}")
    return True

def get_all_strategies():
    """모든 전략 목록 반환"""
    all_strategies = []
    for grade, grade_info in STRATEGY_GRADES.items():
        for strategy in grade_info['strategies']:
            strategy_copy = strategy.copy()
            strategy_copy['grade'] = grade
            all_strategies.append(strategy_copy)
    return all_strategies

def print_strategy_summary():
    """전략 요약 출력"""
    print("📊 전략 등급별 요약")
    print("=" * 50)
    
    for grade, grade_info in STRATEGY_GRADES.items():
        print(f"\n{grade}: {grade_info['name']}")
        print(f"전략 수: {len(grade_info['strategies'])}개")
        
        for strategy in grade_info['strategies']:
            print(f"  {strategy['id']}: {strategy['name']}")
            print(f"    예상 수익률: {strategy['expected_return']:.2f}%")
            print(f"    파라미터: f={strategy['fast_ma']}, s={strategy['slow_ma']}, sl={strategy['stop_loss_pct']*100:.2f}%")

if __name__ == '__main__':
    print_strategy_summary()
