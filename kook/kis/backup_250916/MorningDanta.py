# -*- coding: utf-8 -*-
"""
아침 모멘텀 단타 전략 (8시-10시)

목적
- 8:00~8:40: NXT 단타 (전날 상승한 종목 위주)
- 9:00~9:10: 아침 단타 1 (상승 종목 + 트레일링 스탑)
- 9:10~10:00: 아침 단타 2 (이평선 하락 + 트레일링 스탑)

NXT 단타 (8:00~8:40)
- 아침 8시부터 8시 40분까지 강한 상승 모멘텀을 보이는 종목 단타
- 등락률 3% 이상 종목 중에서 추가 상승 모멘텀 확인
- 트레일링 스탑으로 수익 보호

아침 단타 1 (9:00~9:10)
- 아침 9시부터 9시 10분까지 상승하는 종목 모니터링
- 강한 상승 모멘텀을 보이는 종목에 단타 진입
- 트레일링 스탑으로 수익 보호

아침 단타 2 (9:10~10:00)
- 9시 10분부터 10시까지 이평선 기반 단타
- 이평선 하락 전환 시 전량 매도
- 트레일링 스탑으로 수익 보호

데이터 소스
- KIS 순위 등락 API로 등락률 상위 종목을 1분마다 조회
- KIS 시세 조회 API로 종목별 실시간 데이터 수집
- 1분봉 데이터를 활용한 모멘텀 분석

종목 선정 로직 (1분마다 실행)
1) 1차 관찰군: 등락률 ≥ 3% (아침 상승 종목)
2) 1차 필터: 최소가 1,000원 이상, 제외목록 미포함, VI/특수상태 배제
3) 모멘텀 분석: 최근 5분간 지속적인 상승 패턴 확인
4) 거래량 분석: 평균 거래량 대비 1.5배 이상 증가
5) 최종 진입 조건: 등락률 ≥ 5% AND 모멘텀 점수 ≥ 70점

매수 조건
- 현재가 대비 1.02배 지정가 주문 (빠른 체결)
- 최대 동시 보유: 5개 종목
- 종목당 최대 투자금액: 총자산의 10%

매도 조건
- 모든 단타: 트레일링 스탑 + 이평선 하락
- 트레일링 스탑: 고점 대비 -1.5% 하락 시 전량 매도
- 이평선 하락: 1분봉 10봉 이평선 하락 전환 시 전량 매도
- 손절가: 진입가 대비 -2% 도달 시 전량 매도
- 시간 제한: NXT단타(8:40), 아침단타1(9:10), 아침단타2(10:00) 강제 청산

리스크 관리
- 최대 손실: 일일 총 손실 한도 2%
- 포지션 크기: 종목당 최대 10% (총자산 대비)
- 시간 제한: 각 전략별 강제 청산으로 변동성 리스크 회피
"""

import os
import sys
import json
import time
import logging
import gc
import psutil
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import requests
import pandas as pd
import numpy as np

PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

import KIS_Common as Common
import KIS_API_Helper_KR as KisKR
import telegram_sender as telegram

Common.SetChangeMode("REAL")

script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)

BOT_NAME = "MorningDanta"
PortfolioName = "[아침단타]"

# 로깅 설정
today_str_for_log = time.strftime("%Y-%m-%d")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, f"{BOT_NAME}_{today_str_for_log}.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# ========================= 메모리 관리 유틸리티 =========================
def cleanup_memory():
    """메모리 정리 함수"""
    try:
        # 가비지 컬렉션 강제 실행
        collected = gc.collect()
        
        # 메모리 사용량 확인
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        logging.info(f"메모리 정리 완료: {collected}개 객체 수집, 현재 사용량: {memory_mb:.2f} MB")
        return memory_mb
    except Exception as e:
        logging.warning(f"메모리 정리 중 오류: {e}")
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

def load_config() -> dict:
    """설정 파일 로드"""
    config_path = os.path.join(script_dir, f"{BOT_NAME}_config.json")
    default_config = {
        "allocation_rate": 0.1,  # 총자산의 10% 할당
        "max_parallel_positions": 5,  # 최대 동시 보유 5개
        "position_size_pct": 0.02,  # 종목당 2% (총자산 대비)
        "min_watch_pct": 3.0,  # 최소 관찰 등락률 3%
        "min_change_rate": 3.0,  # 최소 등락률 3%
        "entry_pct": 5.0,  # 진입 등락률 5%
        "target_profit_1": 3.0,  # 1차 목표 수익률 3%
        "target_profit_2": 5.0,  # 2차 목표 수익률 5%
        "stop_loss_pct": 2.0,  # 손절률 2%
        "trailing_stop_pct": 1.5,  # 트레일링 스탑 1.5%
        "max_daily_loss_pct": 2.0,  # 일일 최대 손실 2%
        "min_price": 1000,  # 최소 주가 1,000원
        "max_price": 200000,  # 최대 주가 200,000원
        "min_volume_ratio": 1.5,  # 평균 거래량 대비 최소 1.5배
        "momentum_periods": 5,  # 모멘텀 분석 기간 (분)
        "momentum_threshold": 70,  # 모멘텀 점수 임계값
        "max_candidates": 10,  # 최대 후보 종목 수
        "force_close_time": "10:30",  # 강제 청산 시간
        "exclude_codes": [],  # 제외 종목 코드
        "buy_price_offset": 1.02,  # 매수 지정가 오프셋
        "sell_price_offset": 0.99,  # 매도 지정가 오프셋
        "fluct_tr_id": "FHPST01700000"
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        except Exception as e:
            logging.warning(f"설정 파일 로드 실패, 기본값 사용: {e}")
    else:
        # 기본 설정 파일 생성
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        logging.info(f"기본 설정 파일 생성: {config_path}")
    
    return default_config

def load_positions() -> dict:
    """포지션 정보 로드"""
    positions_path = os.path.join(script_dir, f"{BOT_NAME}_positions.json")
    default_positions = {
        "positions": {},
        "daily_pnl": 0.0,
        "daily_trades": 0,
        "last_update": "",
        "realized_profit": 0.0,
        "initial_allocation": None
    }
    
    if os.path.exists(positions_path):
        try:
            with open(positions_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"포지션 파일 로드 실패, 기본값 사용: {e}")
    
    return default_positions

def save_positions(positions: dict):
    """포지션 정보 저장"""
    positions_path = os.path.join(script_dir, f"{BOT_NAME}_positions.json")
    try:
        with open(positions_path, 'w', encoding='utf-8') as f:
            json.dump(positions, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"포지션 파일 저장 실패: {e}")

def load_state() -> dict:
    """상태 정보 로드"""
    state_path = os.path.join(script_dir, f"{BOT_NAME}_state.json")
    default_state = {
        "watching_codes": [],
        "last_discovery_ts": 0.0,
        "last_candidates": [],
        "market_open": False,
        "strategy_active": False,
        "sold_today": []  # 오늘 판매한 종목 목록
    }
    
    if os.path.exists(state_path):
        try:
            with open(state_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"상태 파일 로드 실패, 기본값 사용: {e}")
    
    return default_state

def save_state(state: dict):
    """상태 정보 저장"""
    state_path = os.path.join(script_dir, f"{BOT_NAME}_state.json")
    try:
        with open(state_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"상태 파일 저장 실패: {e}")

def is_market_open() -> bool:
    """장중 여부 확인 (NXT + KRX 거래소)"""
    now = datetime.now()
    weekday = now.weekday()
    
    # 주말 제외
    if weekday >= 5:
        return False
    
    current_time = now.time()
    
    # NXT 거래소 운영 시간
    nxt_premarket_start = datetime.strptime("08:00", "%H:%M").time()
    nxt_premarket_end = datetime.strptime("08:50", "%H:%M").time()
    nxt_main_start = datetime.strptime("09:00", "%H:%M").time()
    nxt_main_end = datetime.strptime("15:20", "%H:%M").time()
    nxt_after_start = datetime.strptime("15:40", "%H:%M").time()
    nxt_after_end = datetime.strptime("20:00", "%H:%M").time()
    
    # KRX 거래소 운영 시간
    krx_start = datetime.strptime("09:00", "%H:%M").time()
    krx_end = datetime.strptime("15:30", "%H:%M").time()
    
    # NXT 거래소 시간대 확인
    nxt_open = ((nxt_premarket_start <= current_time <= nxt_premarket_end) or  # 프리마켓: 08:00~08:50
                (nxt_main_start <= current_time <= nxt_main_end) or           # 메인마켓: 09:00~15:20
                (nxt_after_start <= current_time <= nxt_after_end))           # 애프터마켓: 15:40~20:00
    
    # KRX 거래소 시간대 확인
    krx_open = (krx_start <= current_time <= krx_end)  # 09:00~15:30
    
    return nxt_open or krx_open

def is_strategy_time() -> bool:
    """전략 실행 시간 확인 (8:00-10:00)"""
    now = datetime.now()
    current_time = now.time()
    strategy_start = datetime.strptime("08:00", "%H:%M").time()
    strategy_end = datetime.strptime("10:00", "%H:%M").time()
    
    return strategy_start <= current_time <= strategy_end

def is_nxt_strategy_time() -> bool:
    """NXT 단타 시간 (8:00-8:40)"""
    now = datetime.now()
    current_time = now.time()
    strategy_start = datetime.strptime("08:00", "%H:%M").time()
    strategy_end = datetime.strptime("08:40", "%H:%M").time()
    
    return strategy_start <= current_time <= strategy_end

def is_morning_strategy_1_time() -> bool:
    """아침 단타 1 시간 (9:00-9:10)"""
    now = datetime.now()
    current_time = now.time()
    strategy_start = datetime.strptime("09:00", "%H:%M").time()
    strategy_end = datetime.strptime("09:10", "%H:%M").time()
    
    return strategy_start <= current_time <= strategy_end

def is_morning_strategy_2_time() -> bool:
    """아침 단타 2 시간 (9:10-10:00)"""
    now = datetime.now()
    current_time = now.time()
    strategy_start = datetime.strptime("09:10", "%H:%M").time()
    strategy_end = datetime.strptime("10:00", "%H:%M").time()
    
    return strategy_start <= current_time <= strategy_end

def is_force_close_time() -> bool:
    """10시 강제 청산 시간 확인"""
    now = datetime.now()
    current_time = now.time()
    force_close_time = datetime.strptime("10:00", "%H:%M").time()
    return current_time >= force_close_time

def is_nxt_force_close_time() -> bool:
    """NXT 8시40분 강제 청산 시간 확인"""
    now = datetime.now()
    current_time = now.time()
    nxt_force_close_time = datetime.strptime("08:40", "%H:%M").time()
    return current_time >= nxt_force_close_time

def force_close_nxt_positions(positions: dict, config: dict) -> list:
    """NXT 8시40분 강제 청산 - NXT 단타 포지션만 매도"""
    closed_positions = []
    
    for code, pos in list(positions.get('positions', {}).items()):
        status = pos.get('status', '')
        qty = int(pos.get('qty', 0))
        name = pos.get('name', code)
        strategy = pos.get('strategy', '')
        
        # NXT 단타가 아니거나 보유중이 아니면 건너뜀
        if strategy != 'NXT단타' or status != '보유중' or qty <= 0:
            continue
            
        try:
            # 현재가 조회
            try:
                price_result = KisKR.GetCurrentPrice(code)
                if isinstance(price_result, dict):
                    current_price = float(price_result.get('price', 0))
                else:
                    current_price = float(price_result)
                if current_price <= 0:
                    logging.warning(f"{code} - 현재가 조회 실패")
                    continue
            except Exception as e:
                logging.warning(f"{code} - 현재가 조회 오류: {e}")
                continue
            
            # NXT 거래소 매도 주문 실행
            sell_success = place_sell_order_nxt(code, name, qty, current_price, "NXT8시40분강제청산", config)
            
            if sell_success:
                # 포지션 정보 저장 (결과 보고용)
                entry_price = float(pos.get('avg', 0))
                pnl = (current_price - entry_price) * qty
                pnl_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                
                closed_positions.append({
                    'code': code,
                    'name': name,
                    'strategy': strategy,
                    'qty': qty,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'entry_time': pos.get('entry_time', ''),
                    'exit_time': datetime.now().strftime('%H:%M:%S')
                })
                
                # 포지션 제거
                del positions['positions'][code]
                
                # 거래 로그
                log_trade("SELL", code, name, qty, current_price, pnl)
                
                logging.info(f"NXT 강제 청산: {name}({code}) {qty}주 @ {current_price:,.0f}원 (PnL: {pnl:,.0f}원, {pnl_pct:+.2f}%)")
            else:
                logging.warning(f"NXT 강제 청산 실패: {name}({code})")
                
        except Exception as e:
            logging.error(f"NXT 강제 청산 오류 {code}: {e}")
    
    return closed_positions

def force_close_all_positions(positions: dict, config: dict) -> dict:
    """10시 강제 청산 - 모든 포지션 매도"""
    closed_positions = []
    
    for code, pos in list(positions.get('positions', {}).items()):
        status = pos.get('status', '')
        qty = int(pos.get('qty', 0))
        name = pos.get('name', code)
        strategy = pos.get('strategy', '')
        
        # 보유중이 아니면 건너뜀
        if status != '보유중' or qty <= 0:
            continue
            
        try:
            # 현재가 조회
            try:
                price_result = KisKR.GetCurrentPrice(code)
                if isinstance(price_result, dict):
                    current_price = float(price_result.get('price', 0))
                else:
                    current_price = float(price_result)
                if current_price <= 0:
                    logging.warning(f"{code} - 현재가 조회 실패")
                    continue
            except Exception as e:
                logging.warning(f"{code} - 현재가 조회 오류: {e}")
                continue
            
            # 전략에 따라 거래소 선택
            use_nxt_for_sell = (strategy == 'NXT단타')
            
            # 매도 주문 실행
            if use_nxt_for_sell:
                sell_success = place_sell_order_nxt(code, name, qty, current_price, "10시강제청산", config)
            else:
                sell_success = place_sell_order(code, name, qty, current_price, "10시강제청산", config)
            
            if sell_success:
                # 포지션 정보 저장 (결과 보고용)
                entry_price = float(pos.get('avg', 0))
                pnl = (current_price - entry_price) * qty
                pnl_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                
                closed_positions.append({
                    'code': code,
                    'name': name,
                    'strategy': strategy,
                    'qty': qty,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'entry_time': pos.get('entry_time', ''),
                    'exit_time': datetime.now().strftime('%H:%M:%S')
                })
                
                # 포지션 제거
                del positions['positions'][code]
                
                # 거래 로그
                log_trade("SELL", code, name, qty, current_price, pnl)
                
                # 오늘 판매한 종목에 추가 (재구매 방지)
                today = datetime.now().strftime('%Y-%m-%d')
                if code not in [item.get('code') for item in closed_positions]:
                    closed_positions.append({
                        'code': code,
                        'name': name,
                        'strategy': strategy,
                        'qty': qty,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'entry_time': pos.get('entry_time', ''),
                        'exit_time': datetime.now().strftime('%H:%M:%S'),
                        'sell_date': today,
                        'reason': '10시강제청산'
                    })
                
                logging.info(f"10시 강제 청산: {name}({code}) {qty}주 @ {current_price:,.0f}원 (PnL: {pnl:,.0f}원, {pnl_pct:+.2f}%)")
            else:
                logging.warning(f"10시 강제 청산 실패: {name}({code})")
                
        except Exception as e:
            logging.error(f"10시 강제 청산 오류 {code}: {e}")
    
    return closed_positions

def _fmt_won(amount: float, signed: bool = False) -> str:
    """금액 포맷팅"""
    if signed and amount > 0:
        return f"+{amount:,.0f}원"
    elif signed and amount < 0:
        return f"{amount:,.0f}원"
    else:
        return f"{amount:,.0f}원"

def generate_daily_report(closed_positions: list, balance: float) -> str:
    """일일 거래 결과 보고서 생성"""
    if not closed_positions:
        return "📊 아침 단타 봇\n일일 거래 결과 보고서\n==================================\n❌ 거래 내역이 없습니다.\n=================================="
    
    # 통계 계산
    total_trades = len(closed_positions)
    winning_trades = len([p for p in closed_positions if p['pnl'] > 0])
    losing_trades = len([p for p in closed_positions if p['pnl'] < 0])
    flat_trades = len([p for p in closed_positions if p['pnl'] == 0])
    total_pnl = sum(p['pnl'] for p in closed_positions)
    total_pnl_pct = (total_pnl / balance) * 100 if balance > 0 else 0
    
    # 전략별 통계
    strategy_stats = {}
    for pos in closed_positions:
        strategy = pos['strategy']
        if strategy not in strategy_stats:
            strategy_stats[strategy] = {'count': 0, 'pnl': 0, 'wins': 0}
        strategy_stats[strategy]['count'] += 1
        strategy_stats[strategy]['pnl'] += pos['pnl']
        if pos['pnl'] > 0:
            strategy_stats[strategy]['wins'] += 1
    
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 헤더
    header = [
        "📊 아침 단타 봇",
        f"일일 거래 결과 보고서 ({ts})",
        "==================================",
    ]
    
    # 상세 거래 내역
    lines = []
    for pos in closed_positions:
        icon = "🟢" if pos['pnl'] > 0 else ("🔴" if pos['pnl'] < 0 else "⚪")
        lines.append(f"{icon} {pos['name']}({pos['code']}) - {pos['strategy']}")
        lines.append(f"   진입: {pos['entry_time']} @ {_fmt_won(pos['entry_price'])}")
        lines.append(f"   청산: {pos['exit_time']} @ {_fmt_won(pos['exit_price'])}")
        lines.append(f"   수익: {_fmt_won(pos['pnl'], signed=True)}({pos['pnl_pct']:+.2f}%)")
        lines.append("")
    
    # 푸터
    footer = [
        "==================================",
        f"💰 총 자산: {_fmt_won(balance)}",
        f"📈 총 거래수: {total_trades}건",
        f"📊 수익: {winning_trades}개, 손실: {losing_trades}개, 손익없음: {flat_trades}개",
        f"🎯 승률: {(winning_trades/total_trades*100):.1f}%",
        f"💰 총 수익금: {_fmt_won(total_pnl, signed=True)}({total_pnl_pct:+.2f}%)",
    ]
    
    # 전략별 성과 추가
    if strategy_stats:
        footer.append("")
        footer.append("📋 전략별 성과:")
        for strategy, stats in strategy_stats.items():
            win_rate = (stats['wins'] / stats['count'] * 100) if stats['count'] > 0 else 0
            footer.append(f"  • {strategy}: {stats['count']}건, {_fmt_won(stats['pnl'], signed=True)}, 승률 {win_rate:.1f}%")
    
    return "\n".join(header + lines + footer)

def send_daily_report(closed_positions: list, balance: float):
    """일일 거래 결과 보고서 전송"""
    try:
        report = generate_daily_report(closed_positions, balance)
        telegram.send(report)
        logging.info("일일 거래 결과 보고서 전송 완료")
    except Exception as e:
        logging.error(f"일일 거래 결과 보고서 전송 실패: {e}")


def get_momentum_score(code: str, periods: int = 10) -> float:
    """모멘텀 점수 계산 (0-100)"""
    try:
        # 1분봉 이평선 데이터 수집
        ma_data = get_1min_ma_data(code, periods)
        
        if ma_data["trend"] == "unknown":
            return 0.0
        
        # 모멘텀 점수 계산
        base_score = 0
        
        # 1. 이평선 상승 전환 (40점)
        if ma_data["trend"] in ["uptrend", "reversal"]:
            base_score += 40
        
        # 2. 5봉 이평선 위에 위치 (30점)
        if ma_data["current_price"] > ma_data["ma5"]:
            base_score += 30
        
        # 3. 이평선 위에서의 강도 (30점)
        if ma_data["strength"] > 0:
            strength_score = min(30, ma_data["strength"] * 10)  # 1% = 10점
            base_score += strength_score
        
        return min(100, base_score)
        
    except Exception as e:
        logging.debug(f"{code} 모멘텀 점수 계산 실패: {e}")
        return 0.0

def get_volume_ratio(code: str) -> float:
    """평균 거래량 대비 현재 거래량 비율 계산"""
    try:
        # 현재 거래량 조회
        vol_result = KisKR.GetCurrentVolume(code)
        if isinstance(vol_result, dict):
            current_vol = float(vol_result.get('volume', 0))
        else:
            current_vol = float(vol_result)
        if current_vol <= 0:
            return 0.0
        
        # 최근 20일 평균 거래량 조회 (pykrx 사용)
        from pykrx import stock as pykrx_stock
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        
        df = pykrx_stock.get_market_ohlcv_by_date(start_date, end_date, code)
        if df is None or df.empty:
            return 0.0
        
        avg_volume = df['거래량'].mean()
        if avg_volume <= 0:
            return 0.0
        
        return current_vol / avg_volume
        
    except Exception as e:
        logging.debug(f"{code} 거래량 비율 계산 실패: {e}")
        return 0.0

def fetch_rising_stocks(limit: int = 50, market_code: str = "J") -> List[Dict[str, str]]:
    """상승 종목 조회 (LimitUpNextDay.py와 동일한 방식)"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            base = Common.GetUrlBase(Common.GetNowDist())
            path = "uapi/domestic-stock/v1/ranking/fluctuation"
            url = f"{base}/{path}"
            
            # KIS 문서 기준 파라미터(_code 접미 포함) + 하위호환 키 병행 전송
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {Common.GetToken(Common.GetNowDist())}",
                "appKey": Common.GetAppKey(Common.GetNowDist()),
                "appSecret": Common.GetAppSecret(Common.GetNowDist()),
                "tr_id": "FHPST01700000",
                "tr_cont": "N",  # API 문서 요구사항
                "custtype": "P",  # 개인 고객 구분 추가 (일부 엔드포인트 호환성)
                "seq_no": "",  # API 문서 요구사항
            }
            
            safe_limit = max(1, min(int(limit), 50))  # 최대 50개까지 조회 가능
            params = {
                # 필수 파라미터들 (API 문서 기준)
                "fid_rsfl_rate2": "",              # 공백 입력 시 전체 (~ 비율)
                "fid_cond_mrkt_div_code": market_code,     # 시장구분코드 (J:KRX, NX:NXT)
                "fid_cond_scr_div_code": "20170",  # Unique key(20170)
                "fid_input_iscd": "0000",         # 0000(전체)
                "fid_rank_sort_cls_code": "0",     # 0:상승율순 1:하락율순 2:시가대비상승율 3:시가대비하락율 4:변동율
                "fid_input_cnt_1": "0", # 0:전체, 누적일수 입력
                "fid_prc_cls_code": "1",           # 1:종가대비 (상승율순일때)
                "fid_input_price_1": "",           # 공백 입력 시 전체 (가격~)
                "fid_input_price_2": "",           # 공백 입력 시 전체 (~ 가격)
                "fid_vol_cnt": "",                 # 공백 입력 시 전체 (거래량~)
                "fid_trgt_cls_code": "0",          # 0:전체
                "fid_trgt_exls_cls_code": "0",     # 0:전체
                "fid_div_cls_code": "0",           # 0:전체
                "fid_rsfl_rate1": "",              # 공백 입력 시 전체 (비율~)
                
                # 하위호환 키 (기존 코드와의 호환성)
                "fid_rank_sort_cls": "0",          # 구버전 키 병행
                "fid_prc_cls": "1",                # 구버전 키 병행
                "fid_trgt_cls": "0",               # 구버전 키 병행
            }
            
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code != 200:
                logging.warning(f"KIS fluctuation HTTP {res.status_code} (시도 {attempt+1}/{max_retries}): {res.text[:200]}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # 재시도 전 대기
                    continue
                return []
            
            js = res.json()
            logging.info(f"KIS API 응답 (시도 {attempt+1}): rt_cd={js.get('rt_cd')}, msg_cd={js.get('msg_cd')}")
            
            # rt_cd 체크를 더 유연하게 처리
            rt_cd = str(js.get('rt_cd', '0'))
            if rt_cd not in ['0', '1']:  # 0: 성공, 1: 성공(일부 데이터)
                logging.warning(f"KIS API 응답 오류: rt_cd={rt_cd}, msg1={js.get('msg1', '')}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return []
            
            items = js.get('output') or js.get('output1') or js.get('output2') or []
            if not isinstance(items, list) or len(items) == 0:
                logging.warning(f"KIS fluctuation empty output: {js}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return []
            
            stocks = []
            for item in items[:safe_limit]:
                code = item.get('rsym') or item.get('mksc_shrn_iscd') or item.get('symb') or item.get('stck_shrn_iscd')
                name = item.get('rsym_nm') or item.get('hts_kor_isnm') or item.get('itemnm') or code
                pct = item.get('prdy_ctrt') or item.get('rate') or item.get('fluctuation_rate')
                price = item.get('stck_prpr') or item.get('price') or 0
                volume = item.get('acml_vol') or item.get('volume') or 0
                
                try:
                    pct_f = float(str(pct).replace('%',''))
                    price_f = float(price)
                    volume_f = float(volume)
                except Exception:
                    pct_f = 0.0
                    price_f = 0.0
                    volume_f = 0.0
                
                if code and name and price_f > 0:
                    stocks.append({
                        'code': code,
                        'name': name,
                        'pct': pct_f,
                        'price': price_f,
                        'volume': volume_f
                    })
            
            logging.info(f"KIS API 성공: {len(stocks)}개 종목 조회됨")
            return stocks
            
        except requests.exceptions.ConnectionError as e:
            logging.warning(f"KIS API 연결 오류 (시도 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
        except Exception as e:
            logging.warning(f"KIS fluctuation API 실패 (시도 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
    
    logging.error("KIS API 최대 재시도 횟수 초과")
    return []

def get_market_index_trend() -> Dict:
    """시장 지수 추세 분석"""
    try:
        # 코스피 지수 조회 (실제로는 대표 종목으로 근사)
        # 삼성전자, SK하이닉스, LG화학 등 대형주들의 평균으로 시장 추세 파악
        market_codes = ["005930", "000660", "051910", "035420", "207940"]  # 삼성전자, SK하이닉스, LG화학, NAVER, 삼성바이오로직스
        
        market_trends = []
        for code in market_codes:
            ma_data = get_1min_ma_data(code, 10)
            if ma_data["trend"] != "unknown":
                market_trends.append(ma_data["trend"])
        
        if not market_trends:
            return {"trend": "unknown", "strength": 0, "confidence": 0}
        
        # 시장 전체 추세 판단
        uptrend_count = market_trends.count("uptrend") + market_trends.count("reversal")
        downtrend_count = market_trends.count("downtrend")
        
        if uptrend_count > downtrend_count:
            market_trend = "uptrend"
            confidence = uptrend_count / len(market_trends)
        elif downtrend_count > uptrend_count:
            market_trend = "downtrend"
            confidence = downtrend_count / len(market_trends)
        else:
            market_trend = "sideways"
            confidence = 0.5
        
        return {
            "trend": market_trend,
            "strength": confidence,
            "confidence": confidence,
            "sample_size": len(market_trends)
        }
        
    except Exception as e:
        logging.debug(f"시장 지수 추세 분석 실패: {e}")
        return {"trend": "unknown", "strength": 0, "confidence": 0}

def analyze_momentum_candidates(stocks: List[Dict], config: dict) -> List[Dict]:
    """NXT 단타용 모멘텀 후보 분석"""
    candidates = []
    
    for stock in stocks:
        try:
            code = stock.get('code', '')
            name = stock.get('name', '')
            price = float(stock.get('price', 0))
            pct = float(stock.get('pct', 0))
            
            # 기본 필터링
            if price < config['min_price'] or pct < config.get('min_change_rate', 3.0):
                continue
            
            # 제외 종목 확인
            if code in config.get('exclude_codes', []):
                continue
            
            # 모멘텀 점수 계산
            momentum_score = get_momentum_score(code, config.get('momentum_periods', 5))
            if momentum_score < config['momentum_threshold']:
                continue
            
            # 거래량 비율 확인 (간단 계산)
            current_volume = float(stock.get('volume', 0))
            # 간단한 거래량 비율 계산 (현재 거래량을 기준으로)
            volume_ratio = min(3.0, current_volume / 100000) if current_volume > 0 else 0.0
            if volume_ratio < 0.5:  # 최소 거래량 체크
                continue
            
            # 종합 점수 계산
            total_score = (pct * 0.4) + (momentum_score * 0.4) + (volume_ratio * 0.2)
            
            candidates.append({
                'code': code,
                'name': name,
                'price': price,
                'pct': pct,
                'momentum_score': momentum_score,
                'volume_ratio': volume_ratio,
                'total_score': total_score,
                'strategy': 'NXT단타'
            })
            
        except Exception as e:
            logging.debug(f"모멘텀 분석 오류 {code}: {e}")
            continue
    
    # 종합 점수 기준 정렬
    candidates.sort(key=lambda x: x['total_score'], reverse=True)
    return candidates

def analyze_nxt_candidates(candidates: List[Dict], config: dict) -> List[Dict]:
    """NXT 단타 전략: 강한 상승 모멘텀 종목 분석 (8:00-8:40)"""
    filtered_candidates = []
    
    for stock in candidates:
        code = stock.get('code', '')
        name = stock.get('name', '')
        pct = stock.get('pct', 0)
        price = stock.get('price', 0)
        volume_ratio = stock.get('volume_ratio', 0)
        
        #print(stock)
        #print(f"NXT 단타 후보: {name}({code}) - 등락률: {pct:.1f}%, 거래량: {volume_ratio:.1f}배, 가격: {price:.0f}원")
        # NXT 단타 필터링 조건 (완화)
        if pct < 3.0:  # 5%에서 3%로 완화
            continue
            
        # 거래량 비율 체크 비활성화 (pykrx 오류로 인해)
        # if volume_ratio < 1.1:
        #     continue
            
        if price < config['min_price'] or price > config.get('max_price', 200000):
            continue
        
        # NXT 단타 모멘텀 점수 계산
        momentum_score = 0
        
        # 등락률 점수 (0-40점)
        if pct >= 5.0:
            momentum_score += 40
        elif pct >= 4.0:
            momentum_score += 30
        elif pct >= 3.0:
            momentum_score += 20
        elif pct >= 2.0:
            momentum_score += 10
        
        # 거래량 점수 (0-30점)
        if volume_ratio >= 1.2:
            momentum_score += 30
        elif volume_ratio >= 1.1:
            momentum_score += 20
        elif volume_ratio >= 1.0:
            momentum_score += 10
        
        # 가격대 점수 (0-30점)
        if 10000 <= price <= 50000:
            momentum_score += 20
        elif 5000 <= price < 10000 or 50000 < price <= 100000:
            momentum_score += 20
        elif 1000 <= price < 5000 or 100000 < price <= 200000:
            momentum_score += 20
        
        # 최소 점수 이상만 선별 (완화)
        if momentum_score >= 50:  # 70점에서 50점으로 완화
            stock['momentum_score'] = momentum_score
            filtered_candidates.append(stock)
    
    # 모멘텀 점수 순으로 정렬
    filtered_candidates.sort(key=lambda x: x.get('momentum_score', 0), reverse=True)
    
    return filtered_candidates[:config.get('max_candidates', 10)]

def analyze_gap_up_candidates(candidates: List[Dict], config: dict) -> List[Dict]:
    """시초가 전략: 갭상승 + 거래량 급증 종목 분석"""
    filtered_candidates = []
    
    for stock in candidates:
        code = stock.get('code', '')
        name = stock.get('name', '')
        pct = stock.get('pct', 0)
        price = stock.get('price', 0)
        
        # 시초가 전략 조건
        if pct < 3.0:  # 갭상승 3% 이상
            continue
        
        if price < config['min_price']:
            continue
        
        if code in config.get('exclude_codes', []):
            continue
        
        # 거래량 급증 확인
        volume_ratio = get_volume_ratio(code)
        if volume_ratio < 2.0:  # 평균 대비 2배 이상
            continue
        
        # 시초가 전략 점수 계산
        gap_score = min(30, pct * 5)  # 갭상승률 (30점 만점)
        volume_score = min(30, volume_ratio * 10)  # 거래량 (30점 만점)
        price_score = min(20, (price / 1000) * 2)  # 가격대 (20점 만점)
        momentum_score = min(20, pct * 3)  # 모멘텀 (20점 만점)
        
        total_score = gap_score + volume_score + price_score + momentum_score
        
        stock['gap_score'] = gap_score
        stock['volume_ratio'] = volume_ratio
        stock['total_score'] = total_score
        stock['strategy'] = 'gap_up'
        
        filtered_candidates.append(stock)
        
        logging.info(f"시초가 후보: {name}({code}) - 점수: {total_score:.1f}, 갭: {pct:.1f}%, 거래량: {volume_ratio:.1f}배")
    
    # 점수 순으로 정렬
    filtered_candidates.sort(key=lambda x: x['total_score'], reverse=True)
    
    return filtered_candidates

def analyze_trend_capture_candidates(candidates: List[Dict], config: dict) -> List[Dict]:
    """초기 추세 포착 전략: 눌림목 공략 + 이평선 지지 종목 분석"""
    filtered_candidates = []
    
    # 시장 전체 추세 확인
    market_trend = get_market_index_trend()
    logging.info(f"시장 추세: {market_trend['trend']} (신뢰도: {market_trend['confidence']:.2f})")
    
    for stock in candidates:
        code = stock.get('code', '')
        name = stock.get('name', '')
        pct = stock.get('pct', 0)
        price = stock.get('price', 0)
        
        # 기본 필터링
        if pct < config['min_watch_pct']:
            continue
        
        if price < config['min_price']:
            continue
        
        if code in config.get('exclude_codes', []):
            continue
        
        # 시장 추세와 일치하는 종목만 선별
        if market_trend['trend'] == 'downtrend' and market_trend['confidence'] > 0.6:
            logging.debug(f"{name}({code}) - 시장 하락 추세로 제외")
            continue
        
        # 1분봉 이평선 분석 (10봉으로 빠른 분석)
        ma_data = get_1min_ma_data(code, 10)
        if ma_data["trend"] == "unknown":
            continue
        
        # 이평선 지지 확인
        if ma_data["trend"] not in ["uptrend", "reversal"]:
            continue
        
        # 모멘텀 점수 계산
        momentum_score = get_momentum_score(code, 10)  # 10분봉으로 빠른 분석
        if momentum_score < 50:  # 임계값 낮춤
            continue
        
        # 거래량 비율 확인
        volume_ratio = get_volume_ratio(code)
        if volume_ratio < config['min_volume_ratio']:
            continue
        
        # 추세 포착 전략 점수 계산
        pct_score = min(25, pct * 3)  # 상승률 (25점)
        momentum_score_pct = momentum_score * 0.3  # 모멘텀 (30점)
        volume_score = min(25, volume_ratio * 8)  # 거래량 (25점)
        ma_score = 20 if ma_data["trend"] in ["uptrend", "reversal"] else 0  # 이평선 (20점)
        
        total_score = pct_score + momentum_score_pct + volume_score + ma_score
        
        stock['momentum_score'] = momentum_score
        stock['volume_ratio'] = volume_ratio
        stock['ma_trend'] = ma_data["trend"]
        stock['ma_strength'] = ma_data["strength"]
        stock['total_score'] = total_score
        stock['strategy'] = 'trend_capture'
        
        filtered_candidates.append(stock)
        
        logging.info(f"추세 포착 후보: {name}({code}) - 점수: {total_score:.1f}, 이평선: {ma_data['trend']}, 모멘텀: {momentum_score:.1f}")
    
    # 점수 순으로 정렬
    filtered_candidates.sort(key=lambda x: x['total_score'], reverse=True)
    
    return filtered_candidates

def get_1min_ma_data(code: str, periods: int = 10) -> Dict:
    """1분봉 기준 이평선 데이터 수집 및 분석"""
    try:
        # 최근 periods분간의 가격 데이터 수집
        prices = []
        for i in range(periods):
            try:
                price_result = KisKR.GetCurrentPrice(code)
                # price_result가 딕셔너리인 경우 처리
                if isinstance(price_result, dict):
                    price = float(price_result.get('price', 0))
                else:
                    price = float(price_result)
                if price > 0:
                    prices.append(price)
                time.sleep(0.05)  # API 호출 제한 고려
            except Exception as e:
                logging.debug(f"{code} 가격 조회 실패: {e}")
                continue
        
        if len(prices) < periods:
            return {"ma10": 0, "ma5": 0, "trend": "unknown", "strength": 0}
        
        # 10봉 이평선 계산
        ma10 = np.mean(prices[-10:]) if len(prices) >= 10 else np.mean(prices)
        
        # 5봉 이평선 계산
        ma5 = np.mean(prices[-5:]) if len(prices) >= 5 else np.mean(prices)
        
        # 현재가
        current_price = prices[-1]
        
        # 추세 분석
        trend = "unknown"
        if ma5 > ma10 and current_price > ma10:
            trend = "uptrend"
        elif ma5 < ma10 and current_price < ma10:
            trend = "downtrend"
        elif ma5 > ma10 and current_price < ma10:
            trend = "pullback"
        elif ma5 < ma10 and current_price > ma10:
            trend = "reversal"
        
        # 강도 계산
        strength = 0
        if trend == "uptrend":
            strength = ((current_price - ma10) / ma10) * 100
        elif trend == "reversal":
            strength = ((current_price - ma10) / ma10) * 100
        
        return {
            "ma10": ma10,
            "ma5": ma5,
            "current_price": current_price,
            "trend": trend,
            "strength": strength,
            "data_points": len(prices)
        }
        
    except Exception as e:
        logging.debug(f"{code} 1분봉 이평선 분석 실패: {e}")
        return {"ma10": 0, "ma5": 0, "trend": "unknown", "strength": 0}

def should_buy(stock: Dict, config: dict) -> bool:
    """매수 조건 확인"""
    pct = stock.get('pct', 0)
    momentum_score = stock.get('momentum_score', 0)
    strategy = stock.get('strategy', '')
    
    # 거래량 비율 계산 (모든 전략에서 공통으로 사용)
    current_volume = float(stock.get('volume', 0))
    volume_ratio = min(3.0, current_volume / 100000) if current_volume > 0 else 0.0
    
    # NXT 단타는 별도 조건 적용
    if strategy == 'NXT단타':
        return pct >= 3.0 and momentum_score >= 50 and volume_ratio >= 0.5
    
    # 기존 전략들은 설정 파일 조건 사용
    if pct < config['entry_pct']:
        return False
    
    if momentum_score < config['momentum_threshold']:
        return False
    
    if volume_ratio < config['min_volume_ratio']:
        return False
    
    return True

def calculate_position_size(code: str, price: float, config: dict, balance: float) -> int:
    """포지션 크기 계산"""
    try:
        # 종목당 최대 투자금액
        max_position_value = balance * config['position_size_pct']
        
        # 매수 가격 (지정가)
        buy_price = price * config['buy_price_offset']
        
        # 수량 계산
        qty = int(max_position_value / buy_price)
        
        # 최소 1주
        return max(1, qty)
        
    except Exception as e:
        logging.error(f"포지션 크기 계산 실패: {e}")
        return 0

def place_buy_order(code: str, name: str, qty: int, price: float, config: dict) -> bool:
    """매수 주문 실행 (KRX 거래소)"""
    try:
        buy_price = price * config['buy_price_offset']
        
        # 매수 주문
        result = KisKR.MakeBuyLimitOrder(
            stockcode=code,
            amt=qty,
            price=buy_price,
            adjustAmt=False,
            ErrLog="YES",
            EXCG_ID_DVSN_CD="KRX"  # KRX 거래소 명시
        )
        
        if result:
            logging.info(f"매수 주문 성공: {name}({code}) {qty}주 @ {buy_price:,.0f}원")
            telegram.send(f"🟢 매수: {name}({code}) {qty}주 @ {buy_price:,.0f}원")
            return True
        else:
            logging.warning(f"매수 주문 실패: {name}({code})")
            return False
            
    except Exception as e:
        logging.error(f"매수 주문 오류: {e}")
        return False

def place_buy_order_nxt(code: str, name: str, qty: int, price: float, config: dict) -> bool:
    """매수 주문 실행 (NXT 거래소)"""
    try:
        buy_price = price * config['buy_price_offset']
        
        # NXT 거래소 매수 주문
        result = KisKR.MakeBuyLimitOrder(
            stockcode=code,
            amt=qty,
            price=buy_price,
            adjustAmt=False,
            ErrLog="YES",
            EXCG_ID_DVSN_CD="NXT"  # NXT 거래소 지정
        )
        
        if result:
            logging.info(f"NXT 매수 주문 성공: {name}({code}) {qty}주 @ {buy_price:,.0f}원")
            telegram.send(f"🟢 NXT 매수: {name}({code}) {qty}주 @ {buy_price:,.0f}원")
            return True
        else:
            logging.warning(f"NXT 매수 주문 실패: {name}({code})")
            return False
            
    except Exception as e:
        logging.error(f"NXT 매수 주문 오류: {e}")
        return False

def should_sell(position: dict, current_price: float, config: dict) -> Tuple[bool, str]:
    """매도 조건 확인 - 이평선 하락 + 트레일링 스탑"""
    entry_price = float(position.get('entry_price', 0))
    qty = int(position.get('qty', 0))
    high_price = float(position.get('high_price', entry_price))
    code = position.get('code', '')
    strategy = position.get('strategy', '')
    
    if entry_price <= 0 or qty <= 0:
        return False, ""
    
    # 현재 수익률 계산
    current_pnl_pct = ((current_price - entry_price) / entry_price) * 100
    
    # 고가 업데이트
    if current_price > high_price:
        position['high_price'] = current_price
        high_price = current_price
    
    # NXT 단타 강제 청산 (8:40)
    if strategy == 'NXT단타':
        now = datetime.now()
        current_time = now.time()
        nxt_end_time = datetime.strptime("08:40", "%H:%M").time()
        if current_time >= nxt_end_time:
            logging.info(f"{code} - NXT 단타 강제 청산 (8:40)")
            return True, "nxt_force_close"
    
    # 아침 단타 1 강제 청산 (9:10)
    if strategy == '아침단타1':
        now = datetime.now()
        current_time = now.time()
        morning1_end_time = datetime.strptime("09:10", "%H:%M").time()
        if current_time >= morning1_end_time:
            logging.info(f"{code} - 아침 단타 1 강제 청산 (9:10)")
            return True, "morning1_force_close"
    
    # 아침 단타 2 강제 청산 (10:00)
    if strategy == '아침단타2':
        now = datetime.now()
        current_time = now.time()
        morning2_end_time = datetime.strptime("10:00", "%H:%M").time()
        if current_time >= morning2_end_time:
            logging.info(f"{code} - 아침 단타 2 강제 청산 (10:00)")
            return True, "morning2_force_close"
    
    # 1. 1분봉 이평선 하락 전환 확인 (최우선)
    try:
        ma_data = get_1min_ma_data(code, 10)
        if ma_data["trend"] == "downtrend":
            logging.info(f"{code} - 1분봉 이평선 하락 전환으로 매도 신호")
            return True, "ma_downtrend"
        
        # 5봉 이평선이 10봉 이평선을 하향 돌파
        ma5 = ma_data.get("ma5", 0)
        ma10 = ma_data.get("ma10", 0)
        if isinstance(ma5, (int, float)) and isinstance(ma10, (int, float)) and isinstance(current_price, (int, float)):
            if ma5 < ma10 and current_price < ma10:
                logging.info(f"{code} - 5봉 이평선 하향 돌파로 매도 신호")
                return True, "ma_cross_down"
    except Exception as e:
        logging.debug(f"{code} 이평선 분석 실패: {e}")
    
    # 2. 트레일링 스탑 (고점 대비 하락률)
    if high_price > 0:
        trail_loss_pct = ((current_price - high_price) / high_price) * 100
        if trail_loss_pct <= -config['trailing_stop_pct']:
            logging.info(f"{code} - 트레일링 스탑으로 매도 신호 (고점 대비 {trail_loss_pct:.2f}% 하락)")
            return True, "trailing_stop"
    
    # 3. 손절가 (진입가 대비 하락률)
    if current_pnl_pct <= -config['stop_loss_pct']:
        logging.info(f"{code} - 손절가로 매도 신호 (진입가 대비 {current_pnl_pct:.2f}% 하락)")
        return True, "stop_loss"
    
    return False, ""

def place_sell_order(code: str, name: str, qty: int, price: float, reason: str, config: dict) -> bool:
    """매도 주문 실행 (KRX 거래소)"""
    try:
        sell_price = price * config['sell_price_offset']
        
        # 매도 주문
        result = KisKR.MakeSellLimitOrder(
            stockcode=code,
            amt=qty,
            price=sell_price,
            ErrLog="YES",
            EXCG_ID_DVSN_CD="KRX"  # KRX 거래소 명시
        )
        
        if result:
            pnl = (price - float(price)) * qty  # 실제로는 진입가 필요
            emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
            logging.info(f"매도 주문 성공: {name}({code}) {qty}주 @ {sell_price:,.0f}원 ({reason})")
            telegram.send(f"{emoji} 매도: {name}({code}) {qty}주 @ {sell_price:,.0f}원 ({reason})")
            return True
        else:
            logging.warning(f"매도 주문 실패: {name}({code})")
            return False
            
    except Exception as e:
        logging.error(f"매도 주문 오류: {e}")
        return False

def place_sell_order_nxt(code: str, name: str, qty: int, price: float, reason: str, config: dict) -> bool:
    """매도 주문 실행 (NXT 거래소)"""
    try:
        sell_price = price * config['sell_price_offset']
        
        # NXT 거래소 매도 주문
        result = KisKR.MakeSellLimitOrder(
            stockcode=code,
            amt=qty,
            price=sell_price,
            ErrLog="YES",
            EXCG_ID_DVSN_CD="NXT"  # NXT 거래소 지정
        )
        
        if result:
            pnl = (price - float(price)) * qty  # 실제로는 진입가 필요
            emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
            logging.info(f"NXT 매도 주문 성공: {name}({code}) {qty}주 @ {sell_price:,.0f}원 ({reason})")
            telegram.send(f"{emoji} NXT 매도: {name}({code}) {qty}주 @ {sell_price:,.0f}원 ({reason})")
            return True
        else:
            logging.warning(f"NXT 매도 주문 실패: {name}({code})")
            return False
            
    except Exception as e:
        logging.error(f"NXT 매도 주문 오류: {e}")
        return False

def sync_positions_with_actual_holdings(ledger: dict) -> dict:
    """실제 보유 자산과 JSON 파일을 동기화합니다."""
    try:
        # 실제 보유 자산 조회
        actual_holdings = KisKR.GetMyStockList()
        if not actual_holdings or not isinstance(actual_holdings, list):
            logging.warning("실제 보유 자산 조회 실패, 기존 포지션 유지")
            return ledger
            
        actual_positions = {}
        
        # 보유 종목 정보 추출 (GetMyStockList 응답 형식)
        for item in actual_holdings:
            code = item.get('StockCode', '')
            qty = int(item.get('StockAmt', 0))
            avg_price = float(item.get('StockAvgPrice', 0))
            
            if qty > 0 and code:
                actual_positions[code] = {
                    'qty': qty,
                    'avg': avg_price,
                    'status': '보유중'
                }
        
        # JSON 파일의 포지션과 비교
        json_positions = ledger.get('positions', {})
        sync_changes = []
        
        # 1. JSON에 있지만 실제로는 없는 종목 (매도 성공)
        codes_to_remove = []
        for code, pos in json_positions.items():
            if code not in actual_positions:
                if pos.get('status') == '구매중':
                    sync_changes.append(f"미체결: {code} (JSON: {pos.get('qty', 0)}주)")
                    pos['status'] = '미체결'
                    json_positions[code] = pos
                elif pos.get('status') == '보유중':
                    sync_changes.append(f"매도 완료: {code} (JSON: {pos.get('qty', 0)}주)")
                    codes_to_remove.append(code)
        
        # 제거할 종목들을 JSON에서 제거
        for code in codes_to_remove:
            json_positions.pop(code, None)
        
        # 2. JSON에 있는 종목 처리 (이 전략이 매수한 종목의 체결 확인)
        for code, json_pos in json_positions.items():
            if code in actual_positions:
                # 실제 보유 중인 종목: 수량이나 평단이 다르면 업데이트
                actual_pos = actual_positions[code]
                if (json_pos.get('qty', 0) != actual_pos['qty'] or 
                    abs(json_pos.get('avg', 0) - actual_pos['avg']) > 0.01):
                    sync_changes.append(
                        f"부분 체결: {code} "
                        f"(JSON: {json_pos.get('qty', 0)}주@{json_pos.get('avg', 0):,.0f}원 → "
                        f"실제: {actual_pos['qty']}주@{actual_pos['avg']:,.0f}원)"
                    )
                    # 실제 값으로 업데이트
                    json_positions[code]['qty'] = actual_pos['qty']
                    json_positions[code]['avg'] = actual_pos['avg']
                    json_positions[code]['status'] = '보유중'
                else:
                    # 상태만 업데이트 (구매중 → 보유중)
                    if json_pos.get('status') == '구매중':
                        sync_changes.append(f"보유 확인: {code} {actual_pos['qty']}주")
                        json_positions[code]['status'] = '보유중'
            else:
                # JSON에 있지만 실제로는 없는 종목 (이미 처리됨)
                pass
        
        # 3. 실제 보유 자산 중 JSON에 없는 종목 추가 (다른 전략에서 매수한 종목)
        for code, actual_pos in actual_positions.items():
            if code not in json_positions:
                # 다른 전략에서 매수한 종목을 JSON에 추가 (중복 매수 방지용)
                json_positions[code] = {
                    'qty': actual_pos['qty'],
                    'avg': actual_pos['avg'],
                    'status': '보유중',
                    'strategy': '외부매수',  # 다른 전략에서 매수한 종목임을 표시
                    'name': f"외부매수종목_{code}"
                }
                sync_changes.append(f"외부 매수 종목 추가: {code} {actual_pos['qty']}주 (중복 매수 방지)")
        
        # 변경사항이 있으면 로그 출력 및 저장
        if sync_changes:
            logging.info(f"[{BOT_NAME}] 포지션 동기화 완료:")
            for change in sync_changes:
                logging.info(f"  - {change}")
            
            # 텔레그램 메시지 전송
            for change in sync_changes:
                if "보유 확인" in change:
                    try:
                        telegram.send(f"✅ {BOT_NAME} : {change}")
                    except Exception:
                        pass
                elif "매도 완료" in change:
                    try:
                        telegram.send(f"🔴 {BOT_NAME} : {change}")
                    except Exception:
                        pass
            
            # JSON 파일 업데이트
            ledger['positions'] = json_positions
            save_positions(ledger)
        else:
            logging.info(f"[{BOT_NAME}] 포지션 동기화: 변경사항 없음")
        
        return ledger
        
    except Exception as e:
        logging.error(f"포지션 동기화 실패: {e}")
        return ledger

def log_trade(action: str, code: str, name: str, qty: int, price: float, pnl: float = 0.0):
    """거래 로그 기록"""
    try:
        log_file = os.path.join(logs_dir, f"{BOT_NAME}_trades.csv")
        
        # CSV 헤더 확인
        if not os.path.exists(log_file):
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("date,action,code,name,qty,price,pnl\n")
        
        # 거래 로그 추가
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')},{action},{code},{name},{qty},{price:.2f},{pnl:.2f}\n")
            
    except Exception as e:
        logging.error(f"거래 로그 기록 실패: {e}")

def check_kospi_drawdown_positions():
    """KOSPIDrawdown 포지션 체크"""
    try:
        kospi_positions_file = os.path.join(os.path.dirname(__file__), 'KOSPIDrawdown_positions.json')
        if os.path.exists(kospi_positions_file):
            with open(kospi_positions_file, 'r', encoding='utf-8') as f:
                kospi_data = json.load(f)
                positions = kospi_data.get('positions', {})
                # 포지션이 있는지 확인
                for code, pos in positions.items():
                    if int(pos.get('qty', 0)) > 0:
                        return True
        return False
    except Exception as e:
        logging.debug(f"KOSPIDrawdown 포지션 체크 실패: {e}")
        return False

def main():
    """메인 실행 함수"""
    try:
        # KOSPIDrawdown 포지션 체크
        if check_kospi_drawdown_positions():
            logging.info("KOSPIDrawdown 전략이 포지션을 보유 중입니다. 모닝단타 전략을 중단합니다.")
            return
        
        # 현재 시간 확인
        now = datetime.now()
        current_time = now.time()
        
        # 장중 여부 확인
        if not is_market_open():
            logging.info("장외 시간입니다.")
            return
        
        # 전략 실행 시간 확인 (8:00-10:00)
        if not is_strategy_time():
            logging.info("전략 실행 시간이 아닙니다. (8:00-10:00)")
            return
        
        # 설정 및 상태 로드
        config = load_config()
        positions = load_positions()
        state = load_state()
        
        # 하루가 바뀌면 판매한 종목 목록 초기화
        today = datetime.now().strftime('%Y-%m-%d')
        if state.get('last_update_date') != today:
            state['sold_today'] = []
            state['last_update_date'] = today
            logging.info(f"새로운 거래일 시작: {today} - 판매한 종목 목록 초기화")
        
        # 잔고 조회
        try:
            balance_result = KisKR.GetBalance()
            logging.info(f"잔고 조회 결과 타입: {type(balance_result)}, 값: {balance_result}")
            
            if isinstance(balance_result, dict):
                # KIS API 잔고 정보에서 총 자산 사용
                balance = float(balance_result.get('TotalMoney', 0))  # 총 자산
                total_money = float(balance_result.get('TotalMoney', 0))  # 총 자산
                stock_money = float(balance_result.get('StockMoney', 0))  # 주식 평가금액
                remain_money = float(balance_result.get('RemainMoney', 0))  # 현금 잔고
                logging.info(f"총 자산: {balance:,.0f}원, 현금 잔고: {remain_money:,.0f}원, 주식 평가금액: {stock_money:,.0f}원")
            else:
                balance = float(balance_result)
                
            logging.info(f"최종 잔고: {balance:,.0f}원")
            
        except Exception as e:
            logging.error(f"잔고 조회 중 오류: {e}")
            return
            
        if balance <= 0:
            logging.error(f"잔고 조회 실패 또는 잔고 없음: {balance}")
            return
        
        # 실제 보유 자산과 포지션 동기화
        positions = sync_positions_with_actual_holdings(positions)
        
        # NXT 8시40분 강제 청산 확인
        if is_nxt_force_close_time():
            logging.info("=== NXT 8시40분 강제 청산 시작 ===")
            nxt_closed_positions = force_close_nxt_positions(positions, config)
            if nxt_closed_positions:
                logging.info(f"NXT 강제 청산 완료: {len(nxt_closed_positions)}개 포지션")
                # NXT 강제 청산한 종목들을 오늘 판매한 종목에 추가
                for pos in nxt_closed_positions:
                    code = pos['code']
                    name = pos['name']
                    if code not in [item.get('code') for item in state.get('sold_today', [])]:
                        state['sold_today'].append({
                            'code': code,
                            'name': name,
                            'sell_date': datetime.now().strftime('%Y-%m-%d'),
                            'sell_time': pos['exit_time'],
                            'reason': 'NXT8시40분강제청산'
                        })
                        logging.info(f"판매한 종목 기록: {name}({code}) - 재구매 방지")
            else:
                logging.info("NXT 강제 청산할 포지션이 없습니다.")
        
        # 10시 강제 청산 확인
        if is_force_close_time():
            logging.info("=== 10시 강제 청산 시작 ===")
            closed_positions = force_close_all_positions(positions, config)
            if closed_positions:
                # 결과 보고서 전송
                send_daily_report(closed_positions, balance)
                logging.info(f"10시 강제 청산 완료: {len(closed_positions)}개 포지션")
            else:
                logging.info("10시 강제 청산할 포지션이 없습니다.")
            return
        
        logging.info(f"=== {BOT_NAME} 전략 시작 ===")
        logging.info(f"현재 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"총 자산: {balance:,.0f}원")
        
        # 보유 포지션 관리 (보유중 상태만 매도 검토)
        active_positions = 0
        for code, pos in list(positions.get('positions', {}).items()):
            status = pos.get('status', '')
            qty = int(pos.get('qty', 0))
            
            # 보유중이 아니면 건너뜀
            if status != '보유중' or qty <= 0:
                if status == '구매중':
                    logging.info(f"구매중: {code} - 체결 대기")
                elif status == '미체결':
                    logging.info(f"미체결: {code} - 매수 실패")
                continue
            
            active_positions += 1
            
            # 현재가 조회
            try:
                price_result = KisKR.GetCurrentPrice(code)
                if isinstance(price_result, dict):
                    current_price = float(price_result.get('price', 0))
                else:
                    current_price = float(price_result)
                if current_price <= 0:
                    continue
                
                # 매도 조건 확인
                should_sell_flag, sell_reason = should_sell(pos, current_price, config)
                if should_sell_flag:
                    name = pos.get('name', code)
                    strategy = pos.get('strategy', '')
                    
                    # 전략에 따라 거래소 선택
                    use_nxt_for_sell = (strategy == 'NXT단타')
                    
                    # 매도 주문 실행 (거래소에 따라 분기)
                    if use_nxt_for_sell:
                        sell_success = place_sell_order_nxt(code, name, qty, current_price, sell_reason, config)
                    else:
                        sell_success = place_sell_order(code, name, qty, current_price, sell_reason, config)
                    
                    if sell_success:
                        # 포지션 제거
                        del positions['positions'][code]
                        active_positions -= 1
                        
                        # 거래 로그
                        entry_price = float(pos.get('avg', 0))
                        pnl = (current_price - entry_price) * qty
                        log_trade("SELL", code, name, qty, current_price, pnl)
                        
                        # 오늘 판매한 종목에 추가 (재구매 방지)
                        today = datetime.now().strftime('%Y-%m-%d')
                        if code not in state.get('sold_today', []):
                            state['sold_today'].append({
                                'code': code,
                                'name': name,
                                'sell_date': today,
                                'sell_time': datetime.now().strftime('%H:%M:%S'),
                                'reason': sell_reason
                            })
                            logging.info(f"판매한 종목 기록: {name}({code}) - 재구매 방지")
                        
            except Exception as e:
                logging.error(f"포지션 관리 오류 {code}: {e}")
        
        # 신규 진입 검토
        if active_positions < config['max_parallel_positions']:
            # 시간대별 전략 적용 및 상승 종목 조회
            if is_nxt_strategy_time():
                # 8:00-8:40: NXT 단타 전략 (NXT 거래소)
                logging.info("=== NXT 단타 전략 실행 (8:00-8:40) - NXT 거래소 ===")
                rising_stocks = fetch_rising_stocks(50, "NX")  # NXT 거래소 종목 조회 (50개)
                if not rising_stocks:
                    logging.warning("NXT 상승 종목 조회 실패")
                    return
                candidates = analyze_nxt_candidates(rising_stocks, config)
                strategy_name = "NXT단타"
                use_nxt_exchange = True
            elif is_morning_strategy_1_time():
                # 9:00-9:10: 아침 단타 1 전략 (KRX 거래소)
                logging.info("=== 아침 단타 1 전략 실행 (9:00-9:10) - KRX 거래소 ===")
                rising_stocks = fetch_rising_stocks(50, "J")  # KRX 거래소 종목 조회
                if not rising_stocks:
                    logging.warning("KRX 상승 종목 조회 실패")
                    return
                candidates = analyze_gap_up_candidates(rising_stocks, config)
                strategy_name = "아침단타1"
                use_nxt_exchange = False
            elif is_morning_strategy_2_time():
                # 9:10-10:00: 아침 단타 2 전략 (KRX 거래소)
                logging.info("=== 아침 단타 2 전략 실행 (9:10-10:00) - KRX 거래소 ===")
                rising_stocks = fetch_rising_stocks(50, "J")  # KRX 거래소 종목 조회
                if not rising_stocks:
                    logging.warning("KRX 상승 종목 조회 실패")
                    return
                candidates = analyze_trend_capture_candidates(rising_stocks, config)
                strategy_name = "아침단타2"
                use_nxt_exchange = False
            else:
                logging.info("전략 실행 시간이 아닙니다.")
                return
            
            logging.info(f"{strategy_name} 전략 후보 종목: {len(candidates)}개")
            
            # 상위 후보들에 대해 진입 검토
            for stock in candidates[:10]:  # 상위 10개만 검토
                code = stock.get('code', '')
                name = stock.get('name', '')
                price = stock.get('price', 0)
                pct = stock.get('pct', 0)
                strategy_type = stock.get('strategy', '')
                
                # 이미 보유 중인지 확인 (JSON 파일 + 실제 보유 자산)
                if code in positions.get('positions', {}):
                    logging.info(f"이미 JSON에 등록된 종목: {name}({code}) - 건너뜀")
                    continue
                
                # 오늘 판매한 종목인지 확인 (재구매 방지)
                sold_today = state.get('sold_today', [])
                for sold_item in sold_today:
                    if sold_item.get('code') == code:
                        logging.info(f"오늘 이미 판매한 종목: {name}({code}) - {sold_item.get('sell_time')} 판매 - 재구매 방지")
                        continue
                
                # 실제 보유 자산에서도 확인
                is_already_held = False
                try:
                    actual_holdings = KisKR.GetMyStockList()
                    if actual_holdings and isinstance(actual_holdings, list):
                        for item in actual_holdings:
                            if item.get('StockCode') == code and int(item.get('StockAmt', 0)) > 0:
                                logging.info(f"실제 보유 중인 종목: {name}({code}) {item.get('StockAmt', 0)}주 - 건너뜀")
                                is_already_held = True
                                break
                except Exception as e:
                    logging.debug(f"실제 보유 자산 확인 실패: {e}")
                    # 확인 실패 시에도 안전하게 진행
                
                if is_already_held:
                    continue
                
                # 매수 조건 확인
                if not should_buy(stock, config):
                    logging.debug(f"매수 조건 미충족: {name}({code}) - 건너뜀")
                    continue
                
                # 최종 매수 전 로깅
                logging.info(f"매수 검토 중: {name}({code}) - 가격: {price:,.0f}원, 등락률: {pct:.2f}%")
                
                # 포지션 크기 계산
                qty = calculate_position_size(code, price, config, balance)
                if qty <= 0:
                    continue
                
                # 매수 주문 실행 전 최종 중복 확인
                is_final_duplicate = False
                try:
                    final_check = KisKR.GetMyStockList()
                    if final_check and isinstance(final_check, list):
                        for item in final_check:
                            if item.get('StockCode') == code and int(item.get('StockAmt', 0)) > 0:
                                logging.warning(f"매수 직전 중복 확인: {name}({code}) 이미 보유 중 - 매수 취소")
                                is_final_duplicate = True
                                break
                except Exception as e:
                    logging.debug(f"최종 중복 확인 실패: {e}")
                
                if is_final_duplicate:
                    continue
                
                # 매수 주문 실행 (거래소에 따라 분기)
                order_success = False
                if use_nxt_exchange:
                    # NXT 거래소 매수 주문
                    order_success = place_buy_order_nxt(code, name, qty, price, config)
                else:
                    # KRX 거래소 매수 주문
                    order_success = place_buy_order(code, name, qty, price, config)
                
                if order_success:
                    # 포지션 등록 (구매중 상태로 시작)
                    positions['positions'][code] = {
                        'name': name,
                        'qty': qty,
                        'avg': price * config['buy_price_offset'],  # 평균가
                        'entry_price': price * config['buy_price_offset'],
                        'high_price': price * config['buy_price_offset'],
                        'entry_time': now.strftime('%H:%M:%S'),
                        'status': '구매중',  # 구매중 상태로 시작
                        'strategy': strategy_name,  # 전략 타입 추가
                        'sold_50pct': False
                    }
                    
                    # 거래 로그
                    log_trade("BUY", code, name, qty, price * config['buy_price_offset'])
                    
                    active_positions += 1
                    logging.info(f"{strategy_name} 신규 진입: {name}({code}) {qty}주 @ {price * config['buy_price_offset']:,.0f}원 (구매중)")
                    
                    # 최대 보유 수에 도달하면 중단
                    if active_positions >= config['max_parallel_positions']:
                        break
        
        # 상태 저장
        state['strategy_active'] = True
        state['last_update'] = now.strftime('%Y-%m-%d %H:%M:%S')
        
        save_positions(positions)
        save_state(state)
        
        # 메모리 정리
        cleanup_memory()
        
        logging.info(f"=== {BOT_NAME} 전략 완료 ===")
        logging.info(f"활성 포지션: {active_positions}개")
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logging.error(f"메인 실행 오류: {e}")
        logging.error(f"상세 오류: {error_detail}")
        telegram.SendMessage(f"❌ {BOT_NAME} 오류: {str(e)}")

if __name__ == "__main__":
    main()
