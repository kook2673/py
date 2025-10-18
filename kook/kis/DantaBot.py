# -*- coding: utf-8 -*-
"""
단타 전용 봇 (DantaBot)

전략 구성:
1. NXT 단타 (8:00~8:30): 전날 1분봉 MA 기반, 8시30분 강제 청산
2. 아침 단타 1 (9:00~9:10): 상승 모멘텀 종목
3. 아침 단타 2 (9:10~9:50): 이평선 기반 단타
4. 거래량 급등 단타 (9:00~15:30): 실시간 거래량 급등 종목 선별

특징:
- 아침단타와 완전 분리된 독립적 관리
- 전날 1분봉 데이터 활용한 MA 기반 손절
- 실시간 거래량 급등 종목 선별
- 각 전략별 독립적인 포지션 관리.
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

BOT_NAME = "DantaBot"
PortfolioName = "[단타봇]"

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

# ========================= 설정 관리 =========================
def load_config() -> dict:
    """설정 파일 로드"""
    config_path = os.path.join(script_dir, f"{BOT_NAME}_config.json")
    default_config = {
        # 기본 설정
        "allocation_rate": 0.2,  # 총자산의 20% 할당
        "max_parallel_positions": 10,  # 최대 동시 보유 8개
        "min_price": 1000,  # 최소 주가 1,000원
        "max_price": 200000,  # 최대 주가 200,000원
        "exclude_codes": [],  # 제외 종목 코드
        
        # NXT 단타 설정 (8:00~8:30)
        "nxt": {
            "enabled": True,
            "min_change_rate": 2.0,  # 최소 등락률 (시가대비)
            "entry_pct": 2.0,  # 진입 등락률 (시가대비)
            "stop_loss_pct": 2.0,  # 손절률
            "trailing_stop_pct": 1.5,  # 트레일링 스탑 (고정)
            "force_close_time": "08:30",  # 강제 청산 시간
            "buy_minutes": [1, 2],  # 매수 가능 분 (8시 1분, 2분)
            "max_candidates": 5,  # 최대 후보 종목 수
            "max_positions": 2  # 최대 보유 포지션 수 (하루 2개 제한)
        },
        
        # 아침 단타 설정 (9:00~9:30)
        "morning": {
            "enabled": True,
            "min_change_rate": 2.0,  # 최소 등락률 (시가대비)
            "entry_pct": 2.0,  # 진입 등락률 (시가대비)
            "stop_loss_pct": 2.0,  # 손절률
            "trailing_stop_pct": 1.5,  # 트레일링 스탑 (고정)
            "force_close_time": "09:30",  # 강제 청산 시간
            "buy_minutes": [1, 2],  # 매수 가능 분 (9시 1분, 2분)
            "momentum_threshold": 60,  # 모멘텀 임계값
            "max_candidates": 5,  # 최대 후보 종목 수
            "max_positions": 2  # 최대 보유 포지션 수 (하루 2개 제한)
        },
        
        # 모멘텀 관찰 설정 (9:00~15:30)
        "momentum_observer": {
            "enabled": True,
            "min_pct": 3.0,  # 최소 상승률 (관찰)
            "max_pct": 30.0,  # 최대 상승률
            "entry_pct": 5.0,  # 진입 등락률 (5% 이상에서 구매)
            "stop_loss_pct": 3.0,  # 손절률
            "trailing_stop": {
                "profit_ratio": 0.5,  # 순수익의 50% 아래로 떨어지면 매도
                "min_pct": 1.0,  # 최소 1%
                "max_pct": 10.0  # 최대 10%
            },
            "partial_sell": {
                "2%_up": 0.10,
                "3%_up": 0.20,
                "4%_up": 0.30,
                "5%_up": 0.50,
                "trailing_stop": True
            },
            "max_candidates": 10,  # 최대 후보 종목 수
            "max_positions": 3  # 최대 보유 포지션 수
        },
        
        # 3% 급등 매수 전략 (9:00~15:30)
        "spike_3pct": {
            "enabled": True,
            "min_spike_pct": 3.0,  # 1분봉에서 최소 3% 상승
            "stop_loss_pct": 1.0,  # 손절률
            "trailing_stop": {
                "profit_ratio": 0.5,  # 순수익의 50% 아래로 떨어지면 매도
                "min_pct": 1.0,  # 최소 1%
                "max_pct": 10.0  # 최대 10%
            },
            "partial_sell": {
                "2%_up": 0.10,
                "3%_up": 0.20,
                "4%_up": 0.30,
                "5%_up": 0.50,
                "trailing_stop": True
            },
            "max_candidates": 20,  # 최대 후보 종목 수
            "max_positions": 5  # 최대 보유 포지션 수
        },
                
        # 공통 설정
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
        "initial_allocation": None,
        "total_positions": 0,  # 총 포지션 수 (다른 전략 포함)
        "danta_positions": 0   # 단타봇 포지션 수
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
        "sold_today": [],  # 오늘 판매한 종목 목록
        "volume_data": {},  # 거래량 데이터 저장
        "nxt_rankings": [],  # NXT 단타 순위 추적
        "morning_rankings": [],  # 아침 단타 순위 추적
        "nxt_last_buy_time": "",  # NXT 마지막 매수 시간
        "morning_last_buy_time": "",  # 아침 단타 마지막 매수 시간
        "nxt_cleared": False,  # NXT 정리 완료 여부
        "morning_cleared": False,  # 아침 단타 정리 완료 여부
        "momentum_cleared": False,  # 모멘텀 관찰 정리 완료 여부
        "momentum_watch_list": []  # 모멘텀 관찰 종목 목록
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

def sync_positions_with_actual_holdings(positions: dict) -> dict:
    """실제 보유 자산과 포지션 동기화"""
    try:
        # 실제 보유 자산 조회
        actual_holdings = KisKR.GetMyStockList()
        if not actual_holdings or not isinstance(actual_holdings, list):
            logging.warning("실제 보유 자산 조회 실패, 기존 포지션 유지")
            return positions
            
        actual_positions = {}
        
        # 보유 종목 정보 추출
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
        json_positions = positions.get('positions', {})
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
        
        # 2. JSON에 있는 종목 처리 (구매중 → 보유중 확인)
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
        
        # 3. 실제 보유 자산 중 JSON에 없는 종목 추가 (다른 전략에서 매수한 종목)
        # 외부에서 구매한 종목을 자동으로 리스트에 추가하지 않음
        # for code, actual_pos in actual_positions.items():
        #     if code not in json_positions:
        #         # 다른 전략에서 매수한 종목을 JSON에 추가 (중복 매수 방지용)
        #         json_positions[code] = {
        #             'qty': actual_pos['qty'],
        #             'avg': actual_pos['avg'],
        #             'status': '보유중',
        #             'strategy': '외부매수',  # 다른 전략에서 매수한 종목임을 표시
        #             'name': f"외부매수종목_{code}"
        #         }
        #         sync_changes.append(f"외부 매수 종목 추가: {code} {actual_pos['qty']}주 (중복 매수 방지)")
        
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
            positions['positions'] = json_positions
            save_positions(positions)
        else:
            logging.info(f"[{BOT_NAME}] 포지션 동기화: 변경사항 없음")
        
        # 포지션 수 업데이트
        positions['danta_positions'] = len([p for p in json_positions.values() if p.get('strategy', '') and not p.get('strategy', '').startswith('외부매수')])
        positions['total_positions'] = len(actual_positions)
        
        return positions
        
    except Exception as e:
        logging.error(f"포지션 동기화 실패: {e}")
        return positions

# ========================= 보고서 생성 =========================
def generate_strategy_report(strategy: str, positions: dict, config: dict) -> str:
    """전략별 보고서 생성"""
    try:
        strategy_positions = []
        total_pnl = 0.0
        total_trades = 0
        
        for code, pos in positions.get('positions', {}).items():
            if pos.get('strategy') == strategy:
                strategy_positions.append(pos)
                total_trades += 1
                # PnL 계산 (간단한 예시)
                entry_price = float(pos.get('entry_price', 0))
                current_price = float(pos.get('avg', entry_price))
                qty = int(pos.get('qty', 0))
                pnl = (current_price - entry_price) * qty
                total_pnl += pnl
        
        # 보고서 생성
        report = f"📊 {strategy} 전략 보고서\n"
        report += f"⏰ 시간: {datetime.now().strftime('%H:%M:%S')}\n"
        report += f"📈 총 거래: {total_trades}건\n"
        report += f"💰 예상 손익: {total_pnl:,.0f}원\n"
        
        if strategy_positions:
            report += f"\n📋 보유 종목 ({len(strategy_positions)}개):\n"
            for pos in strategy_positions:
                name = pos.get('name', '')
                code = pos.get('code', '')
                qty = int(pos.get('qty', 0))
                entry_price = float(pos.get('entry_price', 0))
                current_price = float(pos.get('avg', entry_price))
                pnl = (current_price - entry_price) * qty
                pnl_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                
                emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                report += f"{emoji} {name}({code}) {qty}주 @ {current_price:,.0f}원 ({pnl_pct:+.1f}%)\n"
        else:
            report += "\n📋 보유 종목: 없음\n"
        
        return report
        
    except Exception as e:
        logging.error(f"보고서 생성 실패: {e}")
        return f"❌ {strategy} 보고서 생성 실패: {str(e)}"

# ========================= 설정 헬퍼 =========================
def get_strategy_config(strategy: str, config: dict = None) -> dict:
    """전략별 설정 반환"""
    strategy_map = {
        'NXT단타': 'nxt',
        '아침단타': 'morning', 
        '모멘텀관찰': 'momentum_observer'
    }
    
    config_key = strategy_map.get(strategy, 'nxt')
    
    if config and config_key in config:
        strategy_config = config[config_key]
        return {
            'trailing_stop_pct': strategy_config.get('trailing_stop_pct', 2.0),
            'stop_loss_pct': strategy_config.get('stop_loss_pct', 2.0),
            'force_close_time': strategy_config.get('force_close_time', '15:30')
        }
    
    # 기본값
    return {
        'trailing_stop_pct': 2.0,
        'stop_loss_pct': 2.0,
        'force_close_time': '15:30'
    }

# ========================= 상한가 종목 처리 =========================
def handle_limit_up_positions(positions: dict, state: dict, config: dict):
    """전날 상한가로 남아있던 종목들 처리"""
    try:
        positions_to_remove = []
        
        for code, pos in positions.get('positions', {}).items():
            strategy = pos.get('strategy', '')
            status = pos.get('status', '')
            
            # 단타봇 종목이고 보유중인 경우만 처리
            if strategy and not strategy.startswith('외부매수') and status == '보유중':
                try:
                    # 현재 상한가 여부 확인
                    if not is_limit_up(code):
                        # 상한가가 아닌 경우 (다음날 상한가 해제) - 트레일링 스탑으로 처리
                        logging.info(f"상한가 해제 확인: {pos.get('name', code)}({code}) - 트레일링 스탑 적용")
                        
                        # 현재가 조회
                        current_price = 0
                        try:
                            price_result = KisKR.GetCurrentPrice(code)
                            if isinstance(price_result, dict):
                                current_price = float(price_result.get('price', 0))
                            else:
                                current_price = float(price_result)
                        except Exception as e:
                            logging.debug(f"{code} 현재가 조회 실패: {e}")
                            continue
                        
                        if current_price > 0:
                            # 트레일링 스탑 조건 확인
                            entry_price = float(pos.get('entry_price', 0))
                            high_price = float(pos.get('high_price', entry_price))
                            
                            # 고가 업데이트
                            if current_price > high_price:
                                pos['high_price'] = current_price
                                high_price = current_price
                                logging.info(f"상한가 해제 후 고가 업데이트: {pos.get('name', code)}({code}) - {high_price:,.0f}원")
                            
                            # 트레일링 스탑 계산 (전략별 설정 사용)
                            strategy_config = get_strategy_config(strategy, config)
                            trail_threshold = -strategy_config.get('trailing_stop_pct', 2.0)
                            
                            # 현재가가 고가에서 트레일링 스탑만큼 하락했는지 확인
                            trail_loss_pct = ((current_price - high_price) / high_price) * 100
                            
                            if trail_loss_pct <= trail_threshold:
                                # 트레일링 스탑 매도 실행
                                name = pos.get('name', code)
                                qty = int(pos.get('qty', 0))
                                
                                if qty > 0:
                                    sell_success = place_sell_order(
                                        code, name, qty, current_price, 
                                        f"상한가해제_트레일링스탑_{trail_loss_pct:.1f}%", strategy, 
                                        {"sell_price_offset": 0.99}
                                    )
                                    
                                    if sell_success:
                                        positions_to_remove.append(code)
                                        logging.info(f"상한가 해제 트레일링 스탑 매도 완료: {name}({code}) - {trail_loss_pct:.1f}%")
                                    else:
                                        logging.warning(f"상한가 해제 트레일링 스탑 매도 실패: {name}({code})")
                            else:
                                logging.info(f"상한가 해제 종목 관찰 중: {pos.get('name', code)}({code}) - 트레일링: {trail_loss_pct:.1f}% (임계값: {trail_threshold:.1f}%)")
                    
                except Exception as e:
                    logging.error(f"상한가 종목 처리 오류 {code}: {e}")
                    continue
        
        # 매도 완료된 종목들 제거
        for code in positions_to_remove:
            if code in positions.get('positions', {}):
                del positions['positions'][code]
                logging.info(f"상한가 해제 종목 제거: {code}")
        
        if positions_to_remove:
            save_positions(positions)
            logging.info(f"상한가 해제 처리 완료: {len(positions_to_remove)}개 종목")
        
    except Exception as e:
        logging.error(f"상한가 종목 처리 실패: {e}")

# ========================= 시간 관리 =========================
def is_market_open() -> bool:
    """장중 여부 확인"""
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
    nxt_open = ((nxt_premarket_start <= current_time <= nxt_premarket_end) or
                (nxt_main_start <= current_time <= nxt_main_end) or
                (nxt_after_start <= current_time <= nxt_after_end))
    
    # KRX 거래소 시간대 확인
    krx_open = (krx_start <= current_time <= krx_end)
    
    return nxt_open or krx_open

def is_strategy_time(strategy: str) -> bool:
    """전략별 실행 시간 확인"""
    now = datetime.now()
    current_time = now.time()
    
    if strategy == "nxt":
        start_time = datetime.strptime("08:00", "%H:%M").time()
        end_time = datetime.strptime("08:30", "%H:%M").time()
        return start_time <= current_time <= end_time
    
    elif strategy == "morning":
        start_time = datetime.strptime("09:00", "%H:%M").time()
        end_time = datetime.strptime("09:30", "%H:%M").time()
        return start_time <= current_time <= end_time
        
    elif strategy == "momentum_observer":
        start_time = datetime.strptime("09:00", "%H:%M").time()
        end_time = datetime.strptime("14:30", "%H:%M").time()
        return start_time <= current_time <= end_time
    
    elif strategy == "spike_3pct":
        start_time = datetime.strptime("09:00", "%H:%M").time()
        end_time = datetime.strptime("15:30", "%H:%M").time()
        return start_time <= current_time <= end_time
    
    return False

def is_time_after(target_time_str: str) -> bool:
    """현재 시간이 지정된 시간 이후인지 확인"""
    try:
        now = datetime.now()
        current_time = now.time()
        target_time = datetime.strptime(target_time_str, "%H:%M").time()
        return current_time >= target_time
    except Exception as e:
        logging.error(f"시간 비교 오류: {e}")
        return False

def is_force_close_time(strategy: str) -> bool:
    """전략별 강제 청산 시간 확인 (지연 실행 고려)"""
    now = datetime.now()
    current_time = now.time()
    
    if strategy == "nxt":
        # 8시 30분 이후면 강제 청산
        force_time = datetime.strptime("08:30", "%H:%M").time()
        return current_time >= force_time
    
    elif strategy == "morning":
        # 9시 30분 이후면 강제 청산
        force_time = datetime.strptime("09:30", "%H:%M").time()
        return current_time >= force_time
    
    
    elif strategy == "momentum_observer":
        # 15시 20분 이후면 강제 청산 (상한가 제외)
        force_time = datetime.strptime("15:20", "%H:%M").time()
        if current_time >= force_time:
            # 상한가가 아닌 경우에만 매도
            return True
        return False
    
    elif strategy == "spike_3pct":
        # 15시 20분 이후면 강제 청산 (상한가 제외)
        force_time = datetime.strptime("15:20", "%H:%M").time()
        if current_time >= force_time:
            # 상한가가 아닌 경우에만 매도
            return True
        return False
    
    return False

def is_buy_time(strategy: str, config: dict) -> bool:
    """전략별 매수 시간 확인 (분 단위 제한)"""
    now = datetime.now()
    current_time = now.time()
    current_minute = now.minute
    
    strategy_config = config.get(strategy, {})
    buy_minutes = strategy_config.get('buy_minutes', [])
    
    if strategy == "nxt":
        # 8시 1분, 8시 2분에만 매수 (설정값 사용)
        start_time = datetime.strptime("08:00", "%H:%M").time()
        end_time = datetime.strptime("08:30", "%H:%M").time()
        is_time_range = start_time <= current_time <= end_time
        is_buy_minute = current_minute in buy_minutes
        
        logging.info(f"NXT 매수 시간 확인: 현재시간={current_time}, 분={current_minute}, 시간범위={is_time_range}, 매수분={buy_minutes}, 매수분확인={is_buy_minute}")
        
        return (is_time_range and is_buy_minute)
    
    elif strategy == "morning":
        # 9시 1분, 9시 2분에만 매수 (설정값 사용)
        start_time = datetime.strptime("09:00", "%H:%M").time()
        end_time = datetime.strptime("09:30", "%H:%M").time()
        return (start_time <= current_time <= end_time and current_minute in buy_minutes)
    
    elif strategy == "momentum_observer":
        # 모멘텀 관찰: 9시~14시 30분 (분 단위 제한 없음)
        start_time = datetime.strptime("09:00", "%H:%M").time()
        end_time = datetime.strptime("14:30", "%H:%M").time()
        return start_time <= current_time <= end_time
    
    elif strategy == "spike_3pct":
        # 3% 급등 매수: 9시~15시 30분 (분 단위 제한 없음)
        start_time = datetime.strptime("09:00", "%H:%M").time()
        end_time = datetime.strptime("15:30", "%H:%M").time()
        return start_time <= current_time <= end_time
    
    return False


# ========================= 데이터 수집 =========================
def get_stock_open_price(code: str) -> float:
    """개별 종목의 시가 정보 조회"""
    try:
        base = Common.GetUrlBase(Common.GetNowDist())
        path = "uapi/domestic-stock/v1/quotations/inquire-price"
        url = f"{base}/{path}"
        
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {Common.GetToken(Common.GetNowDist())}",
            "appKey": Common.GetAppKey(Common.GetNowDist()),
            "appSecret": Common.GetAppSecret(Common.GetNowDist()),
            "tr_id": "FHKST01010100",
            "tr_cont": "N",
            "custtype": "P",
        }
        
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": code,
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data.get('rt_cd') == '0' and 'output' in data:
            output = data['output']
            open_price = float(output.get('stck_oprc', 0))  # 시가
            return open_price
        else:
            logging.debug(f"시가 조회 실패 - {code}: {data.get('msg1', 'Unknown error')}")
            return 0
            
    except Exception as e:
        logging.debug(f"시가 조회 오류 - {code}: {e}")
        return 0

def get_previous_day_1min_data(code: str, days_back: int = 1) -> pd.DataFrame:
    """전날 1분봉 데이터 수집 (MA 계산용)"""
    try:
        from pykrx import stock as pykrx_stock
        
        # 전날 날짜 계산
        target_date = datetime.now() - timedelta(days=days_back)
        target_date_str = target_date.strftime('%Y%m%d')
        
        # 1분봉 데이터 수집 (pykrx는 1분봉을 직접 지원하지 않으므로 일봉으로 근사)
        df = pykrx_stock.get_market_ohlcv_by_date(
            target_date_str, target_date_str, code, adjusted=False
        )
        
        if df is None or df.empty:
            return pd.DataFrame()
        
        # 일봉 데이터를 1분봉으로 근사 (시가, 고가, 저가, 종가, 거래량)
        df = df.reset_index()
        df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        
        # MA 계산
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        
        return df
        
    except Exception as e:
        logging.debug(f"{code} 전날 데이터 수집 실패: {e}")
        return pd.DataFrame()

def get_current_1min_data(code: str, periods: int = 20) -> Dict:
    """현재 1분봉 데이터 수집 (실시간 MA 계산용)"""
    try:
        prices = []
        volumes = []
        
        for i in range(periods):
            try:
                # 현재가 조회
                price_result = KisKR.GetCurrentPrice(code)
                if isinstance(price_result, dict):
                    price = float(price_result.get('price', 0))
                else:
                    price = float(price_result)
                
                # 거래량 조회
                vol_result = KisKR.GetCurrentVolume(code)
                if isinstance(vol_result, dict):
                    volume = float(vol_result.get('volume', 0))
                else:
                    volume = float(vol_result)
                
                if price > 0:
                    prices.append(price)
                    volumes.append(volume)
                
                time.sleep(0.1)  # API 호출 제한 고려
                
            except Exception as e:
                logging.debug(f"{code} 실시간 데이터 수집 실패: {e}")
                continue
        
        if len(prices) < 5:
            return {"ma5": 0, "ma20": 0, "current_price": 0, "current_volume": 0, "data_points": 0}
        
        # MA 계산
        ma5 = np.mean(prices[-5:]) if len(prices) >= 5 else np.mean(prices)
        ma20 = np.mean(prices[-20:]) if len(prices) >= 20 else np.mean(prices)
        
        # MA 기울기 계산 (최근 3개 데이터 포인트 기준)
        ma5_slope = 0
        ma20_slope = 0
        
        if len(prices) >= 3:
            # MA5 기울기 (최근 3개 포인트)
            recent_ma5_values = []
            for i in range(min(3, len(prices))):
                start_idx = max(0, len(prices) - 3 + i - 4)
                end_idx = len(prices) - 3 + i + 1
                if end_idx - start_idx >= 5:
                    recent_ma5 = np.mean(prices[start_idx:end_idx])
                    recent_ma5_values.append(recent_ma5)
            
            if len(recent_ma5_values) >= 3:
                ma5_slope = (recent_ma5_values[-1] - recent_ma5_values[0]) / 2  # 2분간 변화량
            
            # MA20 기울기 (최근 3개 포인트)
            recent_ma20_values = []
            for i in range(min(3, len(prices))):
                start_idx = max(0, len(prices) - 3 + i - 19)
                end_idx = len(prices) - 3 + i + 1
                if end_idx - start_idx >= 20:
                    recent_ma20 = np.mean(prices[start_idx:end_idx])
                    recent_ma20_values.append(recent_ma20)
            
            if len(recent_ma20_values) >= 3:
                ma20_slope = (recent_ma20_values[-1] - recent_ma20_values[0]) / 2  # 2분간 변화량
        
        return {
            "ma5": ma5,
            "ma20": ma20,
            "current_price": prices[-1],
            "current_volume": volumes[-1] if volumes else 0,
            "data_points": len(prices),
            "ma5_slope": ma5_slope,
            "ma20_slope": ma20_slope
        }
        
    except Exception as e:
        logging.debug(f"{code} 실시간 MA 계산 실패: {e}")
        return {"ma5": 0, "ma20": 0, "current_price": 0, "current_volume": 0, "data_points": 0}

def calculate_volume_ratio(code: str, current_volume: float, periods: int = 10) -> float:
    """거래량 비율 계산 (1분봉 데이터 기반)"""
    try:
        logging.info(f"{code} 거래량 비율 계산 시작: 현재거래량={current_volume:,.0f}, periods={periods}")
        if current_volume <= 0:
            logging.info(f"{code} 현재거래량이 0 이하, 0.0 반환")
            return 0.0
        
        # 1분봉 데이터 조회 (필요한 개수만 가져옴)
        minute_data = KisKR.GetOhlcvMinute(code, '1T', periods + 5)  # 여유분 5개 추가
        
        if minute_data is None or len(minute_data) < periods:
            logging.info(f"{code} 1분봉 데이터 부족: {len(minute_data) if minute_data is not None else 0}개, 기본값 1.5배 사용")
            return 1.5
        
        # 최근 periods개 1분봉의 거래량과 가격 추출 (pandas DataFrame)
        volumes = []
        prices = []
        try:
            # pandas DataFrame에서 최근 periods개 데이터의 거래량과 가격 추출
            recent_data = minute_data.tail(periods)
            volumes = recent_data['volume'].tolist()
            prices = recent_data['close'].tolist()
            # 0보다 큰 거래량만 필터링
            volumes = [v for v in volumes if v > 0]
            logging.info(f"{code} DataFrame에서 거래량 추출: {len(volumes)}개")
            for i, vol in enumerate(volumes):
                logging.info(f"{code} 거래량 [{i+1}]: {vol:,.0f}")
        except Exception as e:
            logging.info(f"{code} DataFrame 거래량 추출 실패: {e}")
            return 1.5
        
        if len(volumes) < 3:
            logging.info(f"{code} 유효한 거래량 데이터 부족: {len(volumes)}개, 기본값 1.5배 사용")
            return 1.5
        
        # 평균 거래량 계산 (현재 제외)
        avg_volume = np.mean(volumes[:-1]) if len(volumes) > 1 else volumes[0]
        
        if avg_volume <= 0:
            logging.info(f"{code} 평균 거래량이 0 이하, 기본값 1.5배 사용")
            return 1.5
        
        ratio = current_volume / avg_volume
        
        # 1분봉 상승률 계산 (최근 1분과 이전 1분 비교)
        price_change_pct = 0.0
        if len(prices) >= 2:
            current_price = prices[-1]
            prev_price = prices[-2]
            if prev_price > 0:
                price_change_pct = ((current_price - prev_price) / prev_price) * 100
        
        logging.info(f"{code} 거래량 비율 (1분봉 {len(volumes)}개): {current_volume:,.0f} / {avg_volume:,.0f} = {ratio:.2f}배, 1분봉 상승률: {price_change_pct:+.2f}%")
        
        return ratio
        
    except Exception as e:
        logging.info(f"{code} 1분봉 거래량 비율 계산 실패: {e}")
        return 1.5  # 기본값 반환

# ========================= 변동률 연속상승 전략 =========================
def get_volatility_consecutive_candidates(config: dict) -> List[Dict]:
    """변동률 상위 종목 중 3번 연속 상승 + 거래대금 증가 패턴 찾기"""
    try:
        # 변동률 순위로 상위 종목 조회
        stocks = fetch_rising_stocks(config.get('max_candidates', 30), "J", "4")  # J: KRX, 4: 변동율순
        logging.info(f"변동률 상위 종목 조회 결과: {len(stocks)}개 종목")
        
        candidates = []
        
        for i, stock in enumerate(stocks):
            code = stock.get('code', '')
            name = stock.get('name', '')
            current_price = float(stock.get('price', 0))
            current_pct = float(stock.get('pct', 0))
            current_volume = float(stock.get('volume', 0))
            
            logging.info(f"변동률 {i+1}위: {code} {name} - 가격: {current_price:,.0f}원, 변동률: {current_pct:.2f}%, 거래량: {current_volume:,.0f}")
            
            if not code or not name or current_price <= 0:
                continue
                
            try:
                # 1분봉 데이터 가져오기
                df = KisKR.GetOhlcvMinute(code, '1T', 50)  # 최근 50분 데이터
                
                if df is not None and not df.empty:
                    # 9시 이후 데이터만 필터링
                    df['datetime'] = pd.to_datetime(df.index, format='%H%M%S')
                    df = df[df['datetime'].dt.hour >= 9].copy()
                    df = df.sort_values('datetime')  # 시간순 정렬
                    
                    if len(df) >= 6:  # 최소 6분 데이터 필요
                        # 3번 연속 상승 패턴 찾기
                        pattern = find_consecutive_rise_pattern(df, current_price, current_volume, config)
                        
                        if pattern:
                            logging.info(f"✅ {name}({code}) - 3번 연속 상승 패턴 발견!")
                            logging.info(f"   구매 시점: {pattern['buy_time'].strftime('%H:%M')} (가격: {pattern['buy_price']:,}원)")
                            logging.info(f"   연속 상승률: {[f'{x:+.2f}%' for x in pattern['consecutive_changes']]}")
                            logging.info(f"   거래대금 증가: {pattern['volume_increase']:+.1f}%")
                            
                            candidates.append({
                                'code': code,
                                'name': name,
                                'price': pattern['buy_price'],
                                'pct': current_pct,
                                'volume': current_volume,
                                'strategy': '변동률연속상승',
                                'pattern': pattern
                            })
                        else:
                            logging.info(f"❌ {name}({code}) - 3번 연속 상승 패턴 없음")
                    else:
                        logging.info(f"❌ {name}({code}) - 데이터 부족 (6분 미만)")
                else:
                    logging.info(f"❌ {name}({code}) - 1분봉 데이터 없음")
                    
            except Exception as e:
                logging.error(f"❌ {name}({code}) - 오류 발생: {e}")
        
        logging.info(f"변동률 연속상승 후보: {len(candidates)}개")
        return candidates
        
    except Exception as e:
        logging.error(f"변동률 연속상승 후보 조회 실패: {e}")
        return []

def find_consecutive_rise_pattern(df, current_price, current_volume, config):
    """연속 상승 패턴 찾기 (3분 연속 상승)"""
    try:
        consecutive_periods = config.get('consecutive_rise_periods', 3)
        min_volume_increase = config.get('min_volume_increase', 20.0)
        
        if len(df) < consecutive_periods + 1:
            return None
            
        # 최근 consecutive_periods + 1분 데이터 확인
        recent_data = df.tail(consecutive_periods + 1).copy()
        
        # 연속 상승 확인
        consecutive_rises = 0
        consecutive_changes = []
        
        for i in range(1, len(recent_data)):
            prev_price = recent_data.iloc[i-1]['close']
            curr_price = recent_data.iloc[i]['close']
            change_pct = ((curr_price - prev_price) / prev_price) * 100
            
            if change_pct > 0:  # 상승
                consecutive_rises += 1
                consecutive_changes.append(change_pct)
            else:
                break  # 연속 상승 중단
        
        # 3분 연속 상승 확인
        if consecutive_rises >= consecutive_periods:
            # 거래대금 증가 확인
            volume_increase = 0
            if len(consecutive_changes) >= 2:
                start_volume = recent_data.iloc[0]['volume']
                end_volume = recent_data.iloc[consecutive_periods]['volume']
                volume_increase = ((end_volume - start_volume) / start_volume) * 100
            
            if volume_increase >= min_volume_increase:
                buy_time = recent_data.index[consecutive_periods]
                buy_price = recent_data.iloc[consecutive_periods]['close']
                
                return {
                    'buy_time': buy_time,
                    'buy_price': buy_price,
                    'consecutive_changes': consecutive_changes[:consecutive_periods],
                    'volume_increase': volume_increase
                }
        
        return None
        
    except Exception as e:
        logging.error(f"연속 상승 패턴 분석 오류: {e}")
        return None


def analyze_volatility_consecutive_candidates(candidates: List[Dict], config: dict, state: dict) -> List[Dict]:
    """변동률 연속상승 후보 분석 (거래대금 기준 상위 선택)"""
    selected_candidates = []
    
    if not candidates:
        logging.info("변동률 연속상승 후보 없음")
        return selected_candidates
    
    logging.info(f"변동률 연속상승 후보 분석 시작: {len(candidates)}개 종목")
    
    # 거래대금 기준으로 정렬
    sorted_candidates = sorted(candidates, key=lambda x: x['price'] * x['volume'], reverse=True)
    
    for i, stock in enumerate(sorted_candidates[:config.get('max_positions', 2)]):
        code = stock['code']
        name = stock['name']
        price = stock['price']
        pct = stock['pct']
        volume = stock['volume']
        pattern = stock['pattern']
        
        # 기본 필터링
        if price < config.get('min_price', 500) or price > config.get('max_price', 200000):
            logging.info(f"변동률연속상승 {name}({code}) - 가격 범위 벗어남: {price:,.0f}원")
            continue
        
        # 거래대금 확인
        volume_amount = price * volume
        if volume_amount < config.get('min_volume_amount', 500000000):
            logging.info(f"변동률연속상승 {name}({code}) - 거래대금 부족: {volume_amount:,.0f}원 < 5억")
            continue
        
        selected_candidates.append({
            'code': code,
            'name': name,
            'price': price,
            'pct': pct,
            'volume': volume,
            'strategy': '변동률연속상승',
            'pattern': pattern,
            'rank': i + 1
        })
        
        logging.info(f"변동률연속상승 후보 {i+1}: {name}({code}) - 가격: {price:,.0f}원, 변동률: {pct:.2f}%, 거래량: {volume:,.0f}주, 거래대금: {volume_amount:,.0f}원, 거래대금증가: {pattern['volume_increase']:+.1f}%")
    
    logging.info(f"변동률 연속상승 최종 후보: {len(selected_candidates)}개")
    return selected_candidates

def analyze_morning_candidates(rankings: List[Dict], config: dict, state: dict) -> List[Dict]:
    """아침 단타 후보 분석 (거래량 기준 상위 2개 선택)"""
    candidates = []
    morning_config = config.get('morning', {})
    
    logging.info(f"아침단타 후보 분석 시작: {len(rankings)}개 종목")
    
    # 시가대비 2% 이상인 종목들만 필터링
    filtered_rankings = []
    for ranking in rankings:
        try:
            code = ranking.get('code', '')
            name = ranking.get('name', '')
            price = ranking.get('price', 0)
            pct = ranking.get('pct', 0)
            
            # 시가대비 +1% 이상만 구매
            if pct < 1.0:
                logging.info(f"아침단타 {name}({code}) - 상승률 부족: {pct:.1f}% < 1.0%")
                continue
            
            # 가격 필터링
            min_price = config.get('min_price', 1000)
            max_price = config.get('max_price', 200000)
            if price < min_price or price > max_price:
                logging.info(f"아침단타 {name}({code}) - 가격 범위 초과: {price:,.0f}원")
                continue
            
            # 거래대금 필터링
            current_volume = ranking.get('volume', 0)
            volume_amount = price * current_volume
            min_volume_amount = morning_config.get('min_volume_amount', 500000000)
            if volume_amount < min_volume_amount:
                logging.info(f"아침단타 {name}({code}) - 거래대금 부족: {volume_amount:,.0f}원 < 5억")
                continue
            
            # 필터링 통과한 종목 추가
            filtered_rankings.append({
                'code': code,
                'name': name,
                'price': price,
                'pct': pct,
                'volume': current_volume,
                'volume_amount': volume_amount,
                'open_price': ranking.get('open_price', 0),
                'rank': ranking.get('rank', 0)
            })
            
        except Exception as e:
            logging.debug(f"아침단타 후보 분석 오류 {code}: {e}")
            continue
    
    # 거래량 기준으로 정렬 (거래량이 높은 순)
    filtered_rankings.sort(key=lambda x: x.get('volume', 0), reverse=True)
    
    # 상위 2개만 선택
    top_2_by_volume = filtered_rankings[:2]
    
    # 현재 순위와 이전 순위 비교
    current_codes = [r['code'] for r in top_2_by_volume]
    previous_codes = [r['code'] for r in state.get('morning_rankings', [])]
    
    # 새로운 종목들 (이전 순위에 없던 종목)
    new_codes = [code for code in current_codes if code not in previous_codes]
    logging.info(f"이전 순위: {previous_codes}")
    logging.info(f"현재 거래량 상위 2개: {current_codes}")
    logging.info(f"새로운 종목: {new_codes}")
    
    for ranking in top_2_by_volume:
        code = ranking.get('code', '')
        name = ranking.get('name', '')
        price = ranking.get('price', 0)
        pct = ranking.get('pct', 0)
        volume = ranking.get('volume', 0)
        volume_amount = ranking.get('volume_amount', 0)
        open_price = ranking.get('open_price', 0)
        
        # 새로운 종목이거나 순위가 변경된 종목
        if code in new_codes:
            candidates.append({
                'code': code,
                'name': name,
                'price': price,
                'pct': pct,
                'volume': volume,
                'volume_amount': volume_amount,
                'open_price': open_price,
                'rank': ranking.get('rank', 0),
                'strategy': '아침단타',
                'is_new': True
            })
            
            logging.info(f"아침단타 신규 후보 (거래량 기준): {name}({code}) - 거래량: {volume:,.0f}, 등락률: {pct:.1f}%, 거래대금: {volume_amount:,.0f}원")
        else:
            logging.info(f"아침단타 {name}({code}) - 기존 종목으로 제외")
    
    logging.info(f"아침단타 최종 후보 (거래량 상위 2개 중): {len(candidates)}개")
    return candidates

# ========================= 모멘텀 관찰 전략 =========================
def update_momentum_watch_list(stocks: List[Dict], config: dict, state: dict) -> List[Dict]:
    """모멘텀 관찰 리스트 (즉시 구매 전략으로 변경되어 더 이상 사용하지 않음)"""
    # 즉시 구매 전략으로 변경되어 관찰 리스트는 더 이상 사용하지 않음
    return []

def get_spike_3pct_candidates(config: dict) -> List[Dict]:
    """3% 급등 매수 후보 조회"""
    try:
        # 상승률 상위 종목 조회
        stocks = fetch_rising_stocks(config.get('max_candidates', 20), "J", "2")  # J: KRX, 2: 시가대비상승율
        logging.info(f"3% 급등 매수 후보 조회: {len(stocks)}개 종목")
        
        candidates = []
        min_spike_pct = config.get('min_spike_pct', 3.0)
        
        for stock in stocks:
            code = stock.get('code', '')
            name = stock.get('name', '')
            current_price = float(stock.get('price', 0))
            current_pct = float(stock.get('pct', 0))
            
            if not code or not name or current_price <= 0:
                continue
                
            try:
                # 1분봉 데이터 가져오기
                df = KisKR.GetOhlcvMinute(code, '1T', 50)  # 최근 50분 데이터
                
                if df is not None and not df.empty:
                    # 9시 이후 데이터만 필터링
                    df['datetime'] = pd.to_datetime(df.index, format='%H%M%S')
                    df = df[df['datetime'].dt.hour >= 9].copy()
                    df = df.sort_values('datetime')
                    
                    if len(df) >= 2:
                        # 1분봉에서 3% 이상 상승한 구간 찾기
                        for i in range(1, len(df)):
                            prev_price = df.iloc[i-1]['close']
                            curr_price = df.iloc[i]['close']
                            minute_change = ((curr_price - prev_price) / prev_price) * 100
                            
                            if minute_change >= min_spike_pct:
                                spike_time = df.iloc[i]['datetime'].strftime('%H:%M')
                                
                                logging.info(f"✅ 3% 급등 발견: {name}({code}) - {spike_time}에 {minute_change:.2f}% 상승")
                                
                                candidates.append({
                                    'code': code,
                                    'name': name,
                                    'price': curr_price,  # 급등 직후 가격으로 매수
                                    'pct': current_pct,
                                    'volume': stock.get('volume', 0),
                                    'strategy': '3%급등매수',
                                    'spike_time': spike_time,
                                    'spike_change': minute_change
                                })
                                break  # 첫 번째 3% 상승만 기록
                                
            except Exception as e:
                logging.debug(f"3% 급등 분석 실패 {code}: {e}")
                continue
        
        logging.info(f"3% 급등 매수 후보: {len(candidates)}개")
        return candidates
        
    except Exception as e:
        logging.error(f"3% 급등 매수 후보 조회 실패: {e}")
        return []

def analyze_momentum_observer_candidates(stocks: List[Dict], config: dict, state: dict) -> List[Dict]:
    """모멘텀 관찰 전략: 0~10% 구간에서 관찰하다가 상승 + 거래량 급증 시 구매"""
    candidates = []
    momentum_config = config.get('momentum_observer', {})
    
    # 시작 시간 체크 (9시 30분 이후에만 작동)
    start_time_str = momentum_config.get('start_time', '09:30')
    if not is_time_after(start_time_str):
        logging.debug(f"모멘텀 관찰: 시작 시간 대기 중 ({start_time_str} 이후 작동)")
        return candidates
    
    # 종료 시간 체크 (14시 30분 이후에는 구매하지 않음)
    end_time_str = momentum_config.get('end_time', '14:30')
    if is_time_after(end_time_str):
        logging.debug(f"모멘텀 관찰: 종료 시간 도달 ({end_time_str} 이후 구매 중단)")
        return candidates
    
    watch_min_pct = momentum_config.get('watch_min_pct', 0.0)  # 관찰 최소 상승률 0%
    watch_max_pct = momentum_config.get('watch_max_pct', 10.0)  # 관찰 최대 상승률 10%
    entry_pct = momentum_config.get('entry_pct', 2.0)  # 진입 상승률 2%
    max_pct = momentum_config.get('max_pct', 30.0)  # 최대 상승률 30%
    
    # 관찰 리스트 업데이트 (0~10% 구간 종목들)
    watch_list = state.get('momentum_watch_list', {})
    if isinstance(watch_list, list):
        watch_list = {}  # 리스트인 경우 딕셔너리로 초기화
    current_time = datetime.now()
    
    # 상위 100개 종목 중에서 관찰 대상 찾기
    for stock in stocks[:100]:  # 상위 100개 확인
        try:
            code = stock.get('code', '')
            name = stock.get('name', '')
            price = float(stock.get('price', 0))
            pct = float(stock.get('pct', 0))
            current_volume = float(stock.get('volume', 0))
            
            # 기본 필터링
            if price < config['min_price'] or price > config['max_price']:
                continue
            
            if code in config.get('exclude_codes', []):
                continue
            
            # 거래대금 확인
            volume_amount = price * current_volume
            if volume_amount < momentum_config.get('min_volume_amount', 1000000000):
                continue
            
            # 관찰 구간 확인 (-5%~10%, 종가대비)
            if watch_min_pct <= pct <= watch_max_pct:
                # 거래량 비율 계산
                volume_ratio = calculate_volume_ratio(code, current_volume, momentum_config.get('volume_periods', 5))
                
                # 관찰 리스트에 추가/업데이트
                if code not in watch_list:
                    watch_list[code] = {
                        'name': name,
                        'price': price,
                        'pct': pct,
                        'volume': current_volume,
                        'volume_ratio': volume_ratio,
                        'first_seen': current_time.isoformat(),
                        'last_seen': current_time.isoformat(),
                        'max_pct': pct,
                        'max_volume_ratio': volume_ratio
                    }
                    logging.info(f"모멘텀 관찰 대상 추가: {name}({code}) - 종가대비: {pct:.1f}%, 거래량비율: {volume_ratio:.1f}배")
                else:
                    # 기존 관찰 대상 업데이트
                    watch_list[code]['last_seen'] = current_time.isoformat()
                    watch_list[code]['max_pct'] = max(watch_list[code]['max_pct'], pct)
                    watch_list[code]['max_volume_ratio'] = max(watch_list[code]['max_volume_ratio'], volume_ratio)
                    watch_list[code]['price'] = price
                    watch_list[code]['pct'] = pct
                    watch_list[code]['volume'] = current_volume
                    watch_list[code]['volume_ratio'] = volume_ratio
            
            # 구매 조건 확인 (관찰 리스트에 있는 종목 중에서)
            if code in watch_list:
                watch_data = watch_list[code]
                watch_pct = watch_data['pct']  # 관찰 시점의 상승률
                watch_volume_ratio = watch_data.get('volume_ratio', 1.0)  # 관찰 시점의 거래량 비율
                
                # 10% 이상 상승한 종목은 관찰 리스트에서 제거하고 구매하지 않음
                if pct >= 10.0:
                    logging.info(f"모멘텀 관찰 제외: {name}({code}) - 10% 이상 상승 ({pct:.1f}%) - 관찰 리스트에서 제거")
                    del watch_list[code]
                    continue
                
                # 관찰 시점 이후 상승 확인 (1% 이상)
                pct_increase = pct - watch_pct
                logging.info(f"모멘텀 관찰 {name}({code}) - 관찰시점: {watch_pct:.1f}%, 현재: {pct:.1f}%, 상승폭: {pct_increase:.1f}%, 진입조건: {entry_pct}%")
                if pct_increase >= entry_pct:
                    # 거래량 급증 확인 (현재 거래량 비율이 관찰 시점보다 높아야 함)
                    current_volume_ratio = calculate_volume_ratio(code, current_volume, momentum_config.get('volume_periods', 5))
                    volume_ratio_threshold = momentum_config.get('volume_ratio_threshold', 50.0)
                    
                    logging.info(f"모멘텀 관찰 {name}({code}) - 거래량비율: 현재 {current_volume_ratio:.1f}배, 관찰시점 {watch_volume_ratio:.1f}배, 기준 {volume_ratio_threshold:.1f}배")
                    
                    # 진입 조건: 상승률 + 거래량 증가
                    entry_condition_met = False
                    entry_type = ""
                    
                    if pct_increase >= entry_pct:
                        # 상승률 조건 만족 시 거래량 조건 확인
                        if current_volume_ratio >= volume_ratio_threshold and current_volume_ratio > watch_volume_ratio:
                            entry_condition_met = True
                            entry_type = f"{pct_increase:.1f}%상승+거래량증가"
                            logging.info(f"모멘텀 관찰 {name}({code}) - 구매 조건 만족! {entry_type}")
                        else:
                            logging.info(f"모멘텀 관찰 {name}({code}) - 거래량 조건 미만족: 현재 {current_volume_ratio:.1f}배 < 기준 {volume_ratio_threshold:.1f}배 또는 관찰시점 {watch_volume_ratio:.1f}배 이하")
                    else:
                        logging.info(f"모멘텀 관찰 {name}({code}) - 상승률 조건 미만족: {pct_increase:.1f}% < {entry_pct}%")
                    
                    if entry_condition_met:
                        # 구매 후보로 추가
                        candidates.append({
                            'code': code,
                            'name': name,
                            'price': price,
                            'pct': pct,
                            'volume_ratio': current_volume_ratio,
                            'volume_amount': volume_amount,
                            'strategy': '모멘텀관찰',
                            'watch_duration': (current_time - datetime.fromisoformat(watch_data['first_seen'])).total_seconds() / 60,  # 분 단위
                            'max_pct_observed': watch_data['max_pct'],
                            'watch_volume_ratio': watch_volume_ratio,
                            'max_volume_ratio_observed': watch_data.get('max_volume_ratio', watch_volume_ratio),
                            'entry_type': entry_type
                        })
                        
                        logging.info(f"모멘텀 구매 신호: {name}({code}) - {entry_type} - 관찰시점: {watch_pct:.1f}% → 현재: {pct:.1f}% (상승: {pct_increase:.1f}%), 거래량비율: {watch_volume_ratio:.1f}배 → {current_volume_ratio:.1f}배")
                        
                        # 구매 후 관찰 리스트에서 제거
                        del watch_list[code]
                    else:
                        logging.debug(f"모멘텀 관찰: {name}({code}) - 상승률 {pct_increase:.1f}% 달성했지만 거래량 부족 (현재: {current_volume_ratio:.1f}배, 관찰시점: {watch_volume_ratio:.1f}배)")
        
        except Exception as e:
            logging.debug(f"모멘텀 관찰 분석 오류 {code}: {e}")
            continue
    
    # 관찰 리스트 업데이트 (state에 저장)
    state['momentum_watch_list'] = watch_list
    
    # 오래된 관찰 대상 제거 (30분 이상 관찰된 종목)
    expired_codes = []
    for code, data in watch_list.items():
        first_seen = datetime.fromisoformat(data['first_seen'])
        if (current_time - first_seen).total_seconds() > 1800:  # 30분
            expired_codes.append(code)
    
    for code in expired_codes:
        del watch_list[code]
        logging.debug(f"모멘텀 관찰 만료: {code} (30분 초과)")
    
    return candidates


# ========================= 매도 조건 확인 =========================
def is_limit_up(code: str) -> bool:
    """상한가 여부 확인"""
    try:
        price_result = KisKR.GetCurrentPrice(code)
        if isinstance(price_result, dict):
            current_price = float(price_result.get('price', 0))
            prev_price = float(price_result.get('prev_price', 0))
        else:
            current_price = float(price_result)
            prev_price = current_price * 0.9  # 근사치
        
        if prev_price > 0:
            pct = ((current_price - prev_price) / prev_price) * 100
            return pct >= 29.5  # 상한가 근처 (29.5% 이상)
        
        return False
    except Exception as e:
        logging.debug(f"{code} 상한가 확인 실패: {e}")
        return False

# ========================= 매수/매도 로직 =========================
def should_buy(stock: Dict, config: dict, strategy: str) -> bool:
    """매수 조건 확인"""
    strategy_config = config.get(strategy, {})
    pct = stock.get('pct', 0)
    score = stock.get('score', 0)
    code = stock.get('code', '')
    
    # entry_pct가 없으면 기본값 2.0 사용
    entry_pct = strategy_config.get('entry_pct', 2.0)
    if pct < entry_pct:
        return False
    
    # momentum_observer 전략은 이미 필터링이 완료되었으므로 score 체크 생략
    if strategy != "momentum_observer":
        if score < strategy_config.get('momentum_threshold', 50):
            return False
    
    # MA5 꺾임 확인 (매수 방지)
    try:
        ma_data = get_current_1min_data(code, 20)
        if ma_data['data_points'] >= 5:
            ma5 = ma_data['ma5']
            ma20 = ma_data['ma20']
            ma5_slope = ma_data.get('ma5_slope', 0)
            
            # MA5가 MA20 아래에 있거나 급격히 하락 중이면 매수 금지
            if ma5 < ma20:
                logging.info(f"{code} - 매수 금지: MA5({ma5:.0f}) < MA20({ma20:.0f})")
                return False
            
            # MA5 기울기가 급격히 하락 중이면 매수 금지
            ma_config = strategy_config.get('ma_stop_loss', {})
            slope_threshold = ma_config.get('slope_threshold', 5.0)
            if ma5_slope < -slope_threshold:
                logging.info(f"{code} - 매수 금지: MA5 급격한 하락 (기울기: {ma5_slope:.1f})")
                return False
        else:
            logging.warning(f"{code} - MA 분석 불가 (데이터 부족: {ma_data['data_points']}개), 매수 진행")
    except Exception as e:
        logging.debug(f"{code} MA 분석 실패: {e}, 매수 진행")
    
    return True

def should_sell(position: dict, current_price: float, config: dict) -> Tuple[bool, str]:
    """매도 조건 확인"""
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
    
    # 전략별 강제 청산 시간 확인
    now = datetime.now()
    current_time = now.time()
    
    if strategy == 'NXT단타':
        # NXT 단타: 8시 30분 이후 강제 청산 (지연 실행 고려)
        if is_force_close_time("nxt"):
            logging.info(f"{code} - NXT 단타 강제 청산 (08:30 이후)")
            return True, "nxt_force_close"
        
        # NXT 단타: MA 기반 손절
        try:
            ma_data = get_current_1min_data(code, 20)
            if ma_data['data_points'] >= 5:
                ma5 = ma_data['ma5']
                ma20 = ma_data['ma20']
                ma5_slope = ma_data.get('ma5_slope', 0)
                ma20_slope = ma_data.get('ma20_slope', 0)
                current_price = ma_data['current_price']
                
                # 상세한 MA 정보 로그
                logging.info(f"{code} - MA 분석: 현재가={current_price:.0f}, MA5={ma5:.0f}(기울기:{ma5_slope:.1f}), MA20={ma20:.0f}(기울기:{ma20_slope:.1f})")
                
                # MA5가 MA20보다 작아질 때 손절
                if ma5 < ma20:
                    # 기울기 기반 손절 전략
                    nxt_config = config.get('nxt', {})
                    ma_config = nxt_config.get('ma_stop_loss', {})
                    slope_threshold = ma_config.get('slope_threshold', 5.0)
                    
                    if abs(ma5_slope) > slope_threshold:
                        # 기울기가 높음 (급격한 변화) - 즉시 손절
                        logging.info(f"{code} - MA5 < MA20 손절 (급격한 변화, MA5기울기: {ma5_slope:.1f})")
                        return True, "ma_cross_down_steep"
                    else:
                        # 기울기가 낮음 (완만한 변화) - 트레일링 스탑 사용
                        logging.info(f"{code} - MA5 < MA20이지만 완만한 변화 (MA5기울기: {ma5_slope:.1f}), 트레일링 스탑 사용")
                        # 트레일링 스탑은 아래쪽에서 처리됨
            else:
                logging.warning(f"{code} - MA 분석 불가 (데이터 부족: {ma_data['data_points']}개)")
        except Exception as e:
            logging.error(f"{code} MA 분석 실패: {e}")
        
        # NXT 단타: 5% 이상 수익 시 50% 매도
        if current_pnl_pct >= 5.0:
            # 부분 매도 여부 확인 (이미 부분 매도했는지)
            partial_sold = position.get('partial_sold_5pct', False)
            
            logging.info(f"{code} - 수익률 {current_pnl_pct:.2f}% 달성, 부분매도 상태: {partial_sold}")
            
            if not partial_sold:
                logging.info(f"{code} - 5% 수익 달성, 50% 부분 매도 시작")
                # 부분 매도 실행
                partial_qty = qty // 2  # 50% 매도
                remaining_qty = qty - partial_qty
                
                logging.info(f"{code} - 부분매도 계획: 전체{qty}주 → 매도{partial_qty}주, 잔여{remaining_qty}주")
                
                if partial_qty > 0:
                    try:
                        name = position.get('name', code)
                        sell_price = current_price * config.get('sell_price_offset', 0.99)
                        
                        logging.info(f"{code} - 부분매도 주문: {partial_qty}주, 가격: {sell_price:.0f}원 (현재가: {current_price:.0f})")
                        
                        # 부분 매도 주문 실행
                        result = KisKR.MakeSellLimitOrder(code, partial_qty, sell_price)
                        
                        if result:
                            # 포지션 업데이트
                            position['qty'] = remaining_qty
                            position['partial_sold_5pct'] = True
                            
                            # 손익 계산
                            pnl = (sell_price - entry_price) * partial_qty
                            remaining_pnl = (current_price - entry_price) * remaining_qty
                            
                            logging.info(f"{code} - 부분 매도 완료: {partial_qty}주 매도, 실현손익: {pnl:,.0f}원")
                            logging.info(f"{code} - 잔여 포지션: {remaining_qty}주, 미실현손익: {remaining_pnl:,.0f}원")
                            
                            # 나머지는 트레일링 스탑으로 관리
                            return False, "partial_sell_completed"
                        else:
                            logging.error(f"{code} - 부분 매도 주문 실패")
                    except Exception as e:
                        logging.error(f"{code} - 부분 매도 실행 오류: {e}")
                else:
                    logging.warning(f"{code} - 부분매도 수량이 0주입니다")
                return False, "partial_sell_failed"
            else:
                logging.info(f"{code} - 이미 5% 부분매도 완료, 잔여 포지션 트레일링 스탑 적용")
    
    elif strategy == '아침단타':
        # 아침 단타: 9시 30분 이후 강제 청산 (상한가 제외, 지연 실행 고려)
        if is_force_close_time("morning"):
            # 상한가가 아닌 경우에만 매도
            if not is_limit_up(code):
                logging.info(f"{code} - 아침단타 강제 청산 (09:30 이후)")
                return True, "morning_force_close"
            else:
                logging.info(f"{code} - 상한가로 인한 매도 보류")
                return False, ""
        
        # 모든 전략: MA 기반 손절
        try:
            ma_data = get_current_1min_data(code, 20)
            if ma_data['data_points'] >= 5:
                ma5 = ma_data['ma5']
                ma20 = ma_data['ma20']
                ma5_slope = ma_data.get('ma5_slope', 0)
                ma20_slope = ma_data.get('ma20_slope', 0)
                current_price = ma_data['current_price']
                
                # 상세한 MA 정보 로그
                logging.info(f"{code} - MA 분석: 현재가={current_price:.0f}, MA5={ma5:.0f}(기울기:{ma5_slope:.1f}), MA20={ma20:.0f}(기울기:{ma20_slope:.1f})")
                
                # MA5가 MA20보다 작아질 때 손절
                if ma5 < ma20:
                    # 전략별 MA 설정 가져오기
                    if strategy == '아침단타':
                        strategy_config = config.get('morning', {})
                    elif strategy == 'NXT단타':
                        strategy_config = config.get('nxt', {})
                    elif strategy == '모멘텀관찰':
                        strategy_config = config.get('momentum_observer', {})
                    else:
                        strategy_config = config.get('morning', {})  # 기본값
                    
                    ma_config = strategy_config.get('ma_stop_loss', {})
                    slope_threshold = ma_config.get('slope_threshold', 5.0)
                    
                    if abs(ma5_slope) > slope_threshold:
                        # 기울기가 높음 (급격한 변화) - 즉시 손절
                        logging.info(f"{code} - {strategy} MA5 < MA20 손절 (급격한 변화, MA5기울기: {ma5_slope:.1f})")
                        return True, "ma_cross_down_steep"
                    else:
                        # 기울기가 낮음 (완만한 변화) - 트레일링 스탑 사용
                        logging.info(f"{code} - {strategy} MA5 < MA20이지만 완만한 변화 (MA5기울기: {ma5_slope:.1f}), 트레일링 스탑 사용")
                        # 트레일링 스탑은 아래쪽에서 처리됨
            else:
                logging.warning(f"{code} - MA 분석 불가 (데이터 부족: {ma_data['data_points']}개)")
        except Exception as e:
            logging.error(f"{code} MA 분석 실패: {e}")
        
        # 아침 단타: 5% 이상 수익 시 50% 매도
        if current_pnl_pct >= 5.0:
            # 부분 매도 여부 확인 (이미 부분 매도했는지)
            partial_sold = position.get('partial_sold_5pct', False)
            
            logging.info(f"{code} - 수익률 {current_pnl_pct:.2f}% 달성, 부분매도 상태: {partial_sold}")
            
            if not partial_sold:
                logging.info(f"{code} - 5% 수익 달성, 50% 부분 매도 시작")
                # 부분 매도 실행
                partial_qty = qty // 2  # 50% 매도
                remaining_qty = qty - partial_qty
                
                logging.info(f"{code} - 부분매도 계획: 전체{qty}주 → 매도{partial_qty}주, 잔여{remaining_qty}주")
                
                if partial_qty > 0:
                    try:
                        name = position.get('name', code)
                        sell_price = current_price * config.get('sell_price_offset', 0.99)
                        
                        logging.info(f"{code} - 부분매도 주문: {partial_qty}주, 가격: {sell_price:.0f}원 (현재가: {current_price:.0f})")
                        
                        # 부분 매도 주문 실행
                        result = KisKR.MakeSellLimitOrder(code, partial_qty, sell_price)
                        
                        if result:
                            # 포지션 업데이트
                            position['qty'] = remaining_qty
                            position['partial_sold_5pct'] = True
                            
                            # 손익 계산
                            pnl = (sell_price - entry_price) * partial_qty
                            remaining_pnl = (current_price - entry_price) * remaining_qty
                            
                            logging.info(f"{code} - 부분 매도 완료: {partial_qty}주 매도, 실현손익: {pnl:,.0f}원")
                            logging.info(f"{code} - 잔여 포지션: {remaining_qty}주, 미실현손익: {remaining_pnl:,.0f}원")
                            
                            # 나머지는 트레일링 스탑으로 관리
                            return False, "partial_sell_completed"
                        else:
                            logging.error(f"{code} - 부분 매도 주문 실패")
                    except Exception as e:
                        logging.error(f"{code} - 부분 매도 실행 오류: {e}")
                else:
                    logging.warning(f"{code} - 부분매도 수량이 0주입니다")
                return False, "partial_sell_failed"
            else:
                logging.info(f"{code} - 이미 5% 부분매도 완료, 잔여 포지션 트레일링 스탑 적용")
    
    elif strategy == '모멘텀관찰':
        # 모멘텀 관찰: 15시 20분 이후 강제 청산 (상한가 제외, 지연 실행 고려)
        if is_force_close_time("momentum_observer"):
            # 상한가가 아닌 경우에만 매도
            if not is_limit_up(code):
                logging.info(f"{code} - 모멘텀관찰 강제 청산 (15:20 이후)")
                return True, "momentum_observer_force_close"
            else:
                logging.info(f"{code} - 상한가로 인한 매도 보류")
                return False, ""
    
    # 트레일링 스탑 (전략별 동적 적용)
    if high_price > 0:
        trail_loss_pct = ((current_price - high_price) / high_price) * 100
        
        # 전략별 트레일링 스탑 계산 (수익 3% 이상일 때만 발동)
        current_profit_pct = ((current_price - entry_price) / entry_price) * 100
        
        # 트레일링 스탑은 최고가 수익률이 3% 이상일 때만 발동
        high_profit_pct = ((high_price - entry_price) / entry_price) * 100
        if high_profit_pct >= 3.0:
            if strategy == '모멘텀관찰':
                # 모멘텀 관찰: 최고가가 높아질수록 더 여유롭게 트레일링 스탑 적용
                
                # 모멘텀 관찰 설정 키 매핑
                config_key = 'momentum_observer'
                trailing_config = config.get(config_key, {}).get('trailing_stop', {})
                
                # 트레일링 스탑 비율 설정
                profit_ratio = trailing_config.get('profit_ratio', 0.5)  # 기본 50%
                min_pct = trailing_config.get('min_pct', 1.0)  # 최소 1%
                max_pct = trailing_config.get('max_pct', 10.0)  # 최대 10%
                
                # 최고가에서의 하락률 계산
                trail_loss_pct = ((current_price - high_price) / high_price) * 100
                
                # 트레일링 스탑 임계값 계산 (최고가 기준)
                if high_profit_pct > 0:
                    # 수익이 있을 때: 최고가 수익률의 50% 하락 시 매도 (더 여유롭게)
                    profit_threshold = high_profit_pct * profit_ratio
                    profit_threshold = max(min_pct, min(profit_threshold, max_pct))
                    
                    # 현재가가 최고가에서 profit_threshold만큼 하락했는지 확인
                    if trail_loss_pct <= -profit_threshold:
                        logging.info(f"{code} - {strategy} 트레일링 스탑 (현재수익: {current_profit_pct:.2f}%, 최고가: {high_profit_pct:.2f}%, 하락: {trail_loss_pct:.2f}%, 임계값: -{profit_threshold:.2f}%)")
                        return True, "trailing_stop"
            else:
                # NXT 단타, 아침단타: 설정된 고정 트레일링 스탑
                strategy_config = config.get(strategy.lower(), {})
                trail_threshold = -strategy_config.get('trailing_stop_pct', 2.0)
                
                if trail_loss_pct <= trail_threshold:
                    logging.info(f"{code} - {strategy} 트레일링 스탑 (현재수익: {current_profit_pct:.2f}%, 하락: {trail_loss_pct:.2f}%)")
                    return True, "trailing_stop"
        else:
            # 수익이 3% 미만일 때는 트레일링 스탑 비활성화
            logging.debug(f"{code} - 트레일링 스탑 비활성화 (현재수익: {current_profit_pct:.2f}% < 3%)")
    
    # 손절가 (설정값 사용)
    strategy_config = config.get(strategy.lower(), {})
    stop_loss_pct = -strategy_config.get('stop_loss_pct', 3.0)  # 기본값을 3%로 변경
    
    if current_pnl_pct <= stop_loss_pct:
        logging.info(f"{code} - 손절가 ({current_pnl_pct:.2f}%)")
        return True, "stop_loss"
    
    return False, ""

# ========================= 주문 실행 =========================
def calculate_position_size(code: str, price: float, config: dict, balance: float) -> int:
    """포지션 크기 계산 (자동 균등 분할)"""
    try:
        # allocation_rate와 max_parallel_positions를 사용하여 자동 계산
        allocation_rate = config.get('allocation_rate', 0.2)
        max_positions = config.get('max_parallel_positions', 10)
        
        # 총 할당 금액을 최대 종목 수로 나누어 종목당 금액 계산
        total_allocation = balance * allocation_rate
        position_size_pct = allocation_rate / max_positions
        max_position_value = balance * position_size_pct
        
        buy_price = price * config['buy_price_offset']
        qty = int(max_position_value / buy_price)
        return max(1, qty)
    except Exception as e:
        logging.error(f"포지션 크기 계산 실패: {e}")
        return 0

def place_buy_order(code: str, name: str, qty: int, price: float, strategy: str, config: dict, volume_ratio: float = 0.0) -> bool:
    """매수 주문 실행"""
    try:
        buy_price = price * config['buy_price_offset']
        
        # NXT 단타는 NXT 거래소, 나머지는 KRX 거래소
        exchange = "NXT" if strategy == "NXT단타" else "KRX"
        
        result = KisKR.MakeBuyLimitOrder(
            stockcode=code,
            amt=qty,
            price=buy_price,
            adjustAmt=False,
            ErrLog="YES",
            EXCG_ID_DVSN_CD=exchange
        )
        
        if result:
            logging.info(f"{strategy} 매수 성공: {name}({code}) {qty}주 @ {buy_price:,.0f}원")
            
            # 모멘텀 관찰 전략의 경우 거래량 비율 정보 추가
            if strategy == "모멘텀관찰" and volume_ratio > 0:
                momentum_config = config.get('momentum_observer', {})
                volume_ratio_threshold = momentum_config.get('volume_ratio_threshold', 50.0)
                telegram.send(f"⚪ {strategy} 매수: {name}({code}) {qty}주 @ {buy_price:,.0f}원 (거래량비율: {volume_ratio:.1f}배, 기준: {volume_ratio_threshold:.1f}배)")
            else:
                telegram.send(f"⚪ {strategy} 매수: {name}({code}) {qty}주 @ {buy_price:,.0f}원")
            return True
        else:
            logging.warning(f"{strategy} 매수 실패: {name}({code})")
            return False
            
    except Exception as e:
        logging.error(f"{strategy} 매수 주문 오류: {e}")
        return False

def check_partial_sell(code: str, current_price: float, positions: dict, config: dict) -> None:
    """단계적 매도 체크 및 실행"""
    try:
        if code not in positions['positions']:
            return
            
        pos = positions['positions'][code]
        entry_price = pos.get('entry_price', 0)
        remaining_qty = pos.get('sell_status', {}).get('remaining_qty', pos.get('qty', 0))
        strategy = pos.get('strategy', '')
        
        if entry_price <= 0 or remaining_qty <= 0:
            return
            
        # 상승률 계산
        profit_pct = ((current_price - entry_price) / entry_price) * 100
        
        # 전략별 partial_sell 설정 가져오기
        if strategy == '아침단타':
            strategy_config = config.get('morning', {})
            partial_sell_config = strategy_config.get('partial_sell', {})
        elif strategy == 'NXT단타':
            strategy_config = config.get('nxt', {})
            partial_sell_config = strategy_config.get('partial_sell', {})
        elif strategy == '모멘텀관찰':
            strategy_config = config.get('momentum_observer', {})
            partial_sell_config = strategy_config.get('partial_sell', {})
        else:
            # 기본 설정 사용 (fallback)
            partial_sell_config = {
                "2%_up": 0.10,
                "3%_up": 0.20,
                "4%_up": 0.30,
                "5%_up": 0.50,
                "trailing_stop": True
            }
            
        sell_status = pos.get('sell_status', {})
        
        # 2% 상승 시 10% 매도 (남은 수량의 10%)
        if profit_pct >= 2.0 and not sell_status.get('2%_sold', False):
            sell_qty = int(remaining_qty * partial_sell_config.get('2%_up', 0.1))
            if sell_qty >= 1:  # 1주 이상일 때만 매도
                execute_partial_sell(code, pos, sell_qty, current_price, "2% 상승 매도", config)
                sell_status['2%_sold'] = True
                sell_status['remaining_qty'] -= sell_qty
            else:
                logging.debug(f"{code} 2% 매도: 수량 부족 ({sell_qty}주) - 패스")
                sell_status['2%_sold'] = True  # 패스해도 해당 단계는 완료로 처리
                
        # 3% 상승 시 20% 매도 (남은 수량의 20%)
        if profit_pct >= 3.0 and not sell_status.get('3%_sold', False):
            sell_qty = int(remaining_qty * partial_sell_config.get('3%_up', 0.2))
            if sell_qty >= 1:  # 1주 이상일 때만 매도
                execute_partial_sell(code, pos, sell_qty, current_price, "3% 상승 매도", config)
                sell_status['3%_sold'] = True
                sell_status['remaining_qty'] -= sell_qty
            else:
                logging.debug(f"{code} 3% 매도: 수량 부족 ({sell_qty}주) - 패스")
                sell_status['3%_sold'] = True  # 패스해도 해당 단계는 완료로 처리
                
        # 4% 상승 시 30% 매도 (남은 수량의 30%)
        if profit_pct >= 4.0 and not sell_status.get('4%_sold', False):
            sell_qty = int(remaining_qty * partial_sell_config.get('4%_up', 0.3))
            if sell_qty >= 1:  # 1주 이상일 때만 매도
                execute_partial_sell(code, pos, sell_qty, current_price, "4% 상승 매도", config)
                sell_status['4%_sold'] = True
                sell_status['remaining_qty'] -= sell_qty
            else:
                logging.debug(f"{code} 4% 매도: 수량 부족 ({sell_qty}주) - 패스")
                sell_status['4%_sold'] = True  # 패스해도 해당 단계는 완료로 처리
                
        # 5% 상승 시 50% 매도 (남은 수량의 50%)
        if profit_pct >= 5.0 and not sell_status.get('5%_sold', False):
            sell_qty = int(remaining_qty * partial_sell_config.get('5%_up', 0.5))
            if sell_qty >= 1:  # 1주 이상일 때만 매도
                execute_partial_sell(code, pos, sell_qty, current_price, "5% 상승 매도", config)
                sell_status['5%_sold'] = True
                sell_status['remaining_qty'] -= sell_qty
            else:
                logging.debug(f"{code} 5% 매도: 수량 부족 ({sell_qty}주) - 패스")
                sell_status['5%_sold'] = True  # 패스해도 해당 단계는 완료로 처리
                
        # 고가 업데이트
        if current_price > pos.get('high_price', 0):
            pos['high_price'] = current_price
            
    except Exception as e:
        logging.error(f"단계적 매도 체크 실패 {code}: {e}")


def execute_partial_sell(code: str, pos: dict, qty: int, price: float, reason: str, config: dict) -> None:
    """부분 매도 실행"""
    try:
        name = pos.get('name', code)
        sell_price = price * config.get('sell_price_offset', 0.99)
        
        # 매도 주문 실행
        result = KisKR.MakeSellLimitOrder(code, qty, sell_price)
        
        if result:
            # 손익 계산
            entry_price = pos.get('entry_price', 0)
            pnl = (sell_price - entry_price) * qty
            
            # 포지션 업데이트
            pos['qty'] = max(0, pos.get('qty', 0) - qty)
            
            # 거래 기록 (간단한 로깅)
            logging.info(f"거래 기록: {datetime.now().strftime('%Y-%m-%d')} SELL {code} {qty}주 @ {sell_price:,.0f}원 (손익: {pnl:+,.0f}원)")
            
            icon = '🟢' if pnl > 0 else ('🔴' if pnl < 0 else '⚪')
            logging.info(f"{icon} [부분매도] {name}({code}) {qty}주 @ {sell_price:,.0f}원 ({reason}, 손익: {pnl:+,.0f}원)")
            
            # 텔레그램 알림
            try:
                pnl_pct = ((sell_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                emoji = '🟢' if pnl > 0 else ('🔴' if pnl < 0 else '⚪')
                msg = f"{emoji} {reason}\n{name}({code}) {qty}주 @ {sell_price:,.0f}원\n손익: {pnl:+,.0f}원 ({pnl_pct:+.2f}%)"
                telegram.send(msg)
            except Exception:
                pass
                
    except Exception as e:
        logging.error(f"부분 매도 실행 실패 {code}: {e}")


def place_sell_order(code: str, name: str, qty: int, price: float, reason: str, strategy: str, config: dict, position: dict = None) -> bool:
    """매도 주문 실행"""
    try:
        sell_price = price * config['sell_price_offset']
        
        # NXT 단타는 NXT 거래소, 나머지는 KRX 거래소
        exchange = "NXT" if strategy == "NXT단타" else "KRX"
        
        result = KisKR.MakeSellLimitOrder(
            stockcode=code,
            amt=qty,
            price=sell_price,
            ErrLog="YES",
            EXCG_ID_DVSN_CD=exchange
        )
        
        if result:
            # 손익 계산
            entry_price = float(position.get('entry_price', 0)) if position else 0
            pnl = (sell_price - entry_price) * qty
            pnl_pct = ((sell_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            
            # 수익/손실에 따라 이모지 결정
            if pnl > 0:
                emoji = "🟢"  # 초록색 동그라미 (수익)
            elif pnl < 0:
                emoji = "🔴"  # 빨간색 동그라미 (손실)
            else:
                emoji = "⚪"  # 흰색 동그라미 (기타)
            
            logging.info(f"{strategy} 매도 성공: {name}({code}) {qty}주 @ {sell_price:,.0f}원 ({reason})")
            telegram.send(f"{emoji} {strategy} 매도: {name}({code}) {qty}주 @ {sell_price:,.0f}원\n손익: {pnl:+,.0f}원 ({pnl_pct:+.2f}%) ({reason})")
            return True
        else:
            logging.warning(f"{strategy} 매도 실패: {name}({code})")
            return False
            
    except Exception as e:
        logging.error(f"{strategy} 매도 주문 오류: {e}")
        return False

# ========================= 상승 종목 조회 =========================
def fetch_rising_stocks(limit: int = 100, market_code: str = "J", sort_type: str = "2") -> List[Dict[str, str]]:
    """상승 종목 조회"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            base = Common.GetUrlBase(Common.GetNowDist())
            path = "uapi/domestic-stock/v1/ranking/fluctuation"
            url = f"{base}/{path}"
            
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {Common.GetToken(Common.GetNowDist())}",
                "appKey": Common.GetAppKey(Common.GetNowDist()),
                "appSecret": Common.GetAppSecret(Common.GetNowDist()),
                "tr_id": "FHPST01700000",
                "tr_cont": "N",
                "custtype": "P",
                "seq_no": "",
            }
            
            safe_limit = max(1, min(int(limit), 50))
            
            # 정렬 타입 설정
            # 0:상승율순, 1:하락율순, 2:시가대비상승율, 3:시가대비하락율, 4:변동율
            
            params = {
                "fid_rsfl_rate2": "",              # 공백 입력 시 전체 (~ 비율)
                "fid_cond_mrkt_div_code": market_code,     # 시장구분코드 (J:KRX, NX:NXT)
                "fid_cond_scr_div_code": "20170",  # Unique key(20170)
                "fid_input_iscd": "0000",         # 0000(전체)
                "fid_rank_sort_cls_code": sort_type,     # 0:상승율순 1:하락율순 2:시가대비상승율 3:시가대비하락율 4:변동율
                "fid_input_cnt_1": "0", # 0:전체, 누적일수 입력
                "fid_prc_cls_code": "0",           # 0:전체 (시가대비상승율 정렬시)
                "fid_input_price_1": "",           # 공백 입력 시 전체 (가격~)
                "fid_input_price_2": "",           # 공백 입력 시 전체 (~ 가격)
                "fid_vol_cnt": "",                 # 공백 입력 시 전체 (거래량~)
                "fid_trgt_cls_code": "0",          # 0:전체
                "fid_trgt_exls_cls_code": "0",     # 0:전체
                "fid_div_cls_code": "0",           # 0:전체
                "fid_rsfl_rate1": "",              # 공백 입력 시 전체 (비율~)
                
                # 하위호환 키 (기존 코드와의 호환성)
                "fid_rank_sort_cls": sort_type,          # 구버전 키 병행
                "fid_prc_cls": "1",                # 구버전 키 병행
                "fid_trgt_cls": "0",               # 구버전 키 병행
            }
            
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code != 200:
                logging.warning(f"KIS fluctuation HTTP {res.status_code} (시도 {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return []
            
            js = res.json()
            rt_cd = str(js.get('rt_cd', '0'))
            if rt_cd not in ['0', '1']:
                logging.warning(f"KIS API 응답 오류: rt_cd={rt_cd}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return []
            
            items = js.get('output') or js.get('output1') or js.get('output2') or []
            if not isinstance(items, list) or len(items) == 0:
                logging.warning(f"KIS fluctuation empty output")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return []
            
            stocks = []
            for item in items[:safe_limit]:
                code = item.get('rsym') or item.get('mksc_shrn_iscd') or item.get('symb') or item.get('stck_shrn_iscd')
                name = item.get('rsym_nm') or item.get('hts_kor_isnm') or item.get('itemnm') or code
                
                # 시가대비 상승률 계산
                current_price = float(item.get('stck_prpr', 0))
                
                # API에서 제공하는 시가대비 등락률 직접 사용
                oprc_vrss_prpr_rate = float(item.get('oprc_vrss_prpr_rate', 0))  # 시가대비 등락률
                prdy_ctrt = float(str(item.get('prdy_ctrt', 0)).replace('%',''))  # 종가대비 등락률
                
                # 디버깅: API 응답 필드 확인
                if code in ['109820', '450140']:  # 상위 2개 종목만 디버깅
                    logging.info(f"API 응답 디버깅 - {code}: {item}")
                
                # 시가대비 등락률이 있으면 사용, 없으면 종가대비 사용
                if oprc_vrss_prpr_rate != 0:
                    pct = oprc_vrss_prpr_rate
                    logging.debug(f"{code} - 시가대비: {pct:.2f}%, 종가대비: {prdy_ctrt:.2f}%")
                else:
                    # 시가대비 등락률 직접 계산 시도
                    open_price = float(item.get('stck_oprc', 0))  # 시가
                    if open_price > 0 and current_price > 0:
                        calculated_pct = ((current_price - open_price) / open_price) * 100
                        pct = calculated_pct
                        # 거래량과 거래대금 계산
                        volume = item.get('acml_vol') or item.get('volume') or 0
                        volume_int = int(volume) if volume else 0
                        amount = current_price * volume_int
                        
                        logging.info(f"{code} - 시가대비 직접 계산: {pct:.2f}% (시가: {open_price}, 현재: {current_price}, 거래량: {volume_int:,}주, 거래대금: {amount:,.0f}원)")
                    else:
                        # 개별 종목 시가 정보 조회 시도
                        try:
                            open_price = get_stock_open_price(code)
                            if open_price > 0 and current_price > 0:
                                calculated_pct = ((current_price - open_price) / open_price) * 100
                                pct = calculated_pct
                                # 거래량과 거래대금 계산
                                volume = item.get('acml_vol') or item.get('volume') or 0
                                volume_int = int(volume) if volume else 0
                                amount = current_price * volume_int
                                
                                logging.info(f"{code} - 개별 조회 시가대비 계산: {pct:.2f}% (시가: {open_price}, 현재: {current_price}, 거래량: {volume_int:,}주, 거래대금: {amount:,.0f}원)")
                            else:
                                pct = prdy_ctrt
                                logging.warning(f"{code} - 시가 정보 조회 실패, 종가대비 사용: {pct:.2f}%")
                        except Exception as e:
                            pct = prdy_ctrt
                            logging.warning(f"{code} - 시가 정보 조회 오류: {e}, 종가대비 사용: {pct:.2f}%")
                
                price = current_price
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
            
        except Exception as e:
            logging.warning(f"KIS fluctuation API 실패 (시도 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
    
    logging.error("KIS API 최대 재시도 횟수 초과")
    return []

# ========================= 메인 실행 =========================
def main():
    """메인 실행 함수"""
    try:
        # 현재 시간 확인
        now = datetime.now()
        current_time = now.time()
        
        # 장중 여부 확인
        market_is_open = is_market_open()
        if not market_is_open:
            logging.info("장외 시간입니다.")
            return
        
        # 설정 및 상태 로드
        config = load_config()
        positions = load_positions()
        state = load_state()
        
        # 장중 상태 업데이트
        state['market_open'] = market_is_open
        
        # 하루가 바뀌면 판매한 종목 목록 초기화 및 상한가 종목 처리
        today = datetime.now().strftime('%Y-%m-%d')
        if state.get('last_update_date') != today:
            state['sold_today'] = []
            state['nxt_cleared'] = False
            state['morning_cleared'] = False
            state['momentum_cleared'] = False
            state['last_update_date'] = today
            logging.info(f"새로운 거래일 시작: {today} - 판매한 종목 목록 및 정리 상태 초기화")
            
            # 전날 상한가로 남아있던 종목들 처리
            handle_limit_up_positions(positions, state, config)
        
        # 실제 보유 자산과 포지션 동기화
        positions = sync_positions_with_actual_holdings(positions)
        
        # 잔고 조회
        try:
            balance_result = KisKR.GetBalance()
            if isinstance(balance_result, dict):
                balance = float(balance_result.get('TotalMoney', 0))
            else:
                balance = float(balance_result)
            logging.info(f"총 자산: {balance:,.0f}원")
        except Exception as e:
            logging.error(f"잔고 조회 중 오류: {e}")
            return
            
        if balance <= 0:
            logging.error(f"잔고 조회 실패 또는 잔고 없음: {balance}")
            return
        
        logging.info(f"=== {BOT_NAME} 전략 시작 ===")
        logging.info(f"현재 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 보유 포지션 관리 (보유중 상태만 매도 검토)
        active_positions = 0
        danta_positions = 0  # 단타봇 포지션 수 (구매중 + 보유중)
        
        for code, pos in list(positions.get('positions', {}).items()):
            status = pos.get('status', '')
            qty = int(pos.get('qty', 0))
            strategy = pos.get('strategy', '')
            
            # 단타봇 포지션인지 확인 (외부매수 제외)
            if strategy and not strategy.startswith('외부매수'):
                danta_positions += 1
                
                # 보유중이 아니면 건너뜀
                if status != '보유중' or qty <= 0:
                    if status == '구매중':
                        logging.info(f"구매중: {code} - 체결 대기")
                    elif status == '미체결':
                        logging.info(f"미체결: {code} - 매수 실패")
                    continue
                
                active_positions += 1
                
                # 단계적 매도 체크 (보유중인 종목만)
                try:
                    price_result = KisKR.GetCurrentPrice(code)
                    if isinstance(price_result, dict):
                        current_price = float(price_result.get('price', 0))
                    else:
                        current_price = float(price_result)
                    if current_price > 0:
                        check_partial_sell(code, current_price, positions, config)
                except Exception as e:
                    logging.debug(f"단계적 매도 체크 실패 {code}: {e}")
            
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
                    
                    # 매도 주문 실행
                    sell_success = place_sell_order(code, name, qty, current_price, sell_reason, strategy, config, pos)
                    
                    if sell_success:
                        # 포지션 제거
                        del positions['positions'][code]
                        active_positions -= 1
                        
                        # 오늘 판매한 종목에 추가
                        if code not in [item.get('code') for item in state.get('sold_today', [])]:
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
        
        # 신규 진입 검토 (전략별 포지션 수 기준)
        strategy_max_positions = 0
        if is_strategy_time("nxt") and config.get('nxt', {}).get('enabled', True):
            strategy_max_positions = config.get('nxt', {}).get('max_positions', 3)
        elif is_strategy_time("morning") and config.get('morning', {}).get('enabled', True):
            strategy_max_positions = config.get('morning', {}).get('max_positions', 3)
        elif is_strategy_time("momentum_observer") and config.get('momentum_observer', {}).get('enabled', True):
            strategy_max_positions = config.get('momentum_observer', {}).get('max_positions', 3)
        elif is_strategy_time("spike_3pct") and config.get('spike_3pct', {}).get('enabled', True):
            strategy_max_positions = config.get('spike_3pct', {}).get('max_positions', 5)
        
        if danta_positions < strategy_max_positions:
            # 전략별 실행
            if is_strategy_time("nxt") and config.get('nxt', {}).get('enabled', True):
                # NXT 변동률 연속상승 전략 (8:00~8:30)
                logging.info("=== NXT 변동률 연속상승 전략 실행 (8:00~8:30) ===")
                
                # 설정된 분에만 매수 (지연 실행 고려)
                if is_buy_time("nxt", config):
                    logging.info("NXT 매수 시간 확인됨 - 변동률 상위 종목 조회 시작")
                    candidates = get_volatility_consecutive_candidates(config.get('nxt', {}))
                    if candidates:
                        selected_candidates = analyze_volatility_consecutive_candidates(candidates, config.get('nxt', {}), state)
                        strategy_name = "NXT변동률연속상승"
                        strategy_key = "nxt"
                        logging.info(f"NXT 변동률 연속상승 후보 분석 완료: {len(selected_candidates)}개")
                        candidates = selected_candidates
                    else:
                        candidates = []
                        logging.info("NXT 변동률 연속상승 후보 없음")
                else:
                    candidates = []
                    logging.info("NXT 매수 시간 아님 - 후보 없음")
                    
            elif is_strategy_time("volatility_consecutive") and config.get('volatility_consecutive', {}).get('enabled', True):
                # 변동률 연속상승 전략 (9:00~15:00)
                logging.info("=== 변동률 연속상승 전략 실행 (9:00~15:00) ===")
                
                # 설정된 분에만 매수 (지연 실행 고려)
                if is_buy_time("volatility_consecutive", config):
                    logging.info("변동률 연속상승 매수 시간 확인됨 - 변동률 상위 종목 조회 시작")
                    candidates = get_volatility_consecutive_candidates(config.get('volatility_consecutive', {}))
                    if candidates:
                        selected_candidates = analyze_volatility_consecutive_candidates(candidates, config.get('volatility_consecutive', {}), state)
                        strategy_name = "변동률연속상승"
                        strategy_key = "volatility_consecutive"
                        logging.info(f"변동률 연속상승 후보 분석 완료: {len(selected_candidates)}개")
                        candidates = selected_candidates
                    else:
                        candidates = []
                        logging.info("변동률 연속상승 후보 없음")
                else:
                    candidates = []
                    logging.info("변동률 연속상승 매수 시간 아님 - 후보 없음")
                    
            elif is_strategy_time("momentum_observer") and config.get('momentum_observer', {}).get('enabled', True):
                # 모멘텀 관찰 전략 (9:00~14:30)
                logging.info("=== 모멘텀 관찰 전략 실행 (9:00~14:30) ===")
                
                # 상위 100개 종목 조회
                stocks = fetch_rising_stocks(100, "J", "2")  # J: KRX, 2: 시가대비상승율
                if stocks:
                    candidates = analyze_momentum_observer_candidates(stocks, config, state)
                    strategy_name = "모멘텀관찰"
                    strategy_key = "momentum_observer"
                    logging.info(f"모멘텀 관찰 후보 분석 완료: {len(candidates)}개")
                else:
                    candidates = []
                    logging.info("모멘텀 관찰 후보 없음")
                    
            elif is_strategy_time("spike_3pct") and config.get('spike_3pct', {}).get('enabled', True):
                # 3% 급등 매수 전략 (9:00~15:30)
                logging.info("=== 3% 급등 매수 전략 실행 (9:00~15:30) ===")
                
                candidates = get_spike_3pct_candidates(config.get('spike_3pct', {}))
                strategy_name = "3%급등매수"
                strategy_key = "spike_3pct"
                logging.info(f"3% 급등 매수 후보 분석 완료: {len(candidates)}개")
            else:
                logging.info("실행할 전략이 없습니다.")
                return
            
            if candidates:
                logging.info(f"{strategy_name} 후보 종목: {len(candidates)}개")
                
                # 상위 후보들에 대해 진입 검토
                for stock in candidates:
                    code = stock.get('code', '')
                    name = stock.get('name', '')
                    price = stock.get('price', 0)
                    
                    # 이미 보유 중인지 확인
                    if code in positions.get('positions', {}):
                        continue
                    
                    # 오늘 판매한 종목인지 확인
                    sold_today = state.get('sold_today', [])
                    if any(item.get('code') == code for item in sold_today):
                        logging.info(f"오늘 이미 판매한 종목: {name}({code}) - 건너뜀")
                        continue
                    
                    # 실제 보유 자산에서도 확인
                    try:
                        actual_holdings = KisKR.GetMyStockList()
                        if actual_holdings and isinstance(actual_holdings, list):
                            for item in actual_holdings:
                                if item.get('StockCode') == code and int(item.get('StockAmt', 0)) > 0:
                                    logging.info(f"실제 보유 중인 종목: {name}({code}) - 건너뜀")
                                    continue
                    except Exception as e:
                        logging.debug(f"실제 보유 자산 확인 실패: {e}")
                    
                    # 매수 조건 확인
                    if not should_buy(stock, config, strategy_key):
                        continue
                    
                    # 포지션 크기 계산
                    qty = calculate_position_size(code, price, config, balance)
                    if qty <= 0:
                        continue
                    
                    # 매수 주문 실행
                    volume_ratio = stock.get('volume_ratio', 0.0) if strategy_name == "모멘텀관찰" else 0.0
                    order_success = place_buy_order(code, name, qty, price, strategy_name, config, volume_ratio)
                    
                    if order_success:
                        # 포지션 등록 (구매중 상태로 시작)
                        positions['positions'][code] = {
                            'name': name,
                            'qty': qty,
                            'avg': price * config['buy_price_offset'],
                            'entry_price': price * config['buy_price_offset'],
                            'high_price': price * config['buy_price_offset'],
                            'entry_time': now.strftime('%H:%M:%S'),
                            'status': '구매중',  # 구매중 상태로 시작
                            'strategy': strategy_name,
                            'sell_status': {
                                '2%_sold': False,
                                '3%_sold': False,
                                '4%_sold': False,
                                '5%_sold': False,
                                'remaining_qty': qty
                            }
                        }
                        
                        danta_positions += 1
                        logging.info(f"{strategy_name} 신규 진입: {name}({code}) {qty}주 @ {price * config['buy_price_offset']:,.0f}원 (구매중)")
                        
                        # 최대 보유 수에 도달하면 중단
                        if danta_positions >= strategy_max_positions:
                            logging.info(f"최대 포지션 수 도달: {danta_positions}/{strategy_max_positions} - 신규 진입 중단")
                            break
        
        # 정리 시간 체크 및 리스트 초기화 (지연 실행 고려)
        current_time = now.time()
        
        # NXT 단타 정리 (8시 30분 이후)
        if is_force_close_time("nxt") and not state.get('nxt_cleared', False):
            logging.info("NXT 단타 정리 완료 - 순위 리스트 초기화")
            
            # NXT 단타 보고서 발송
            try:
                nxt_report = generate_strategy_report("NXT단타", positions, config)
                telegram.send(nxt_report)
                logging.info("NXT 단타 보고서 발송 완료")
            except Exception as e:
                logging.error(f"NXT 단타 보고서 발송 실패: {e}")
            
            state['nxt_rankings'] = []
            state['nxt_cleared'] = True
            
        # 아침 단타 정리 (9시 30분 이후)
        if is_force_close_time("morning") and not state.get('morning_cleared', False):
            logging.info("아침 단타 정리 완료 - 순위 리스트 초기화")
            
            # 아침 단타 보고서 발송
            try:
                morning_report = generate_strategy_report("아침단타", positions, config)
                telegram.send(morning_report)
                logging.info("아침 단타 보고서 발송 완료")
            except Exception as e:
                logging.error(f"아침 단타 보고서 발송 실패: {e}")
            
            state['morning_rankings'] = []
            state['morning_cleared'] = True
            
        # 모멘텀 관찰 정리 (15시 30분 이후)
        if is_force_close_time("momentum_observer") and not state.get('momentum_cleared', False):
            logging.info("모멘텀 관찰 정리 완료")
            
            # 모멘텀 관찰 보고서 발송
            try:
                momentum_report = generate_strategy_report("모멘텀관찰", positions, config)
                telegram.send(momentum_report)
                logging.info("모멘텀 관찰 보고서 발송 완료")
            except Exception as e:
                logging.error(f"모멘텀 관찰 보고서 발송 실패: {e}")
            
            state['momentum_cleared'] = True
        
        # 3% 급등 매수 정리 (15시 30분 이후)
        if is_force_close_time("spike_3pct") and not state.get('spike_3pct_cleared', False):
            logging.info("3% 급등 매수 정리 완료")
            
            # 3% 급등 매수 보고서 발송
            try:
                spike_report = generate_strategy_report("3%급등매수", positions, config)
                telegram.send(spike_report)
                logging.info("3% 급등 매수 보고서 발송 완료")
            except Exception as e:
                logging.error(f"3% 급등 매수 보고서 발송 실패: {e}")
            
            state['spike_3pct_cleared'] = True
        
        # 상태 저장
        state['strategy_active'] = True
        state['last_update'] = now.strftime('%Y-%m-%d %H:%M:%S')
        
        save_positions(positions)
        save_state(state)
        
        logging.info(f"=== {BOT_NAME} 전략 완료 ===")
        logging.info(f"단타봇 보유중 포지션: {active_positions}개")
        logging.info(f"단타봇 전체 포지션: {danta_positions}개 (구매중+보유중)")
        logging.info(f"현재 전략 최대 포지션: {strategy_max_positions}개")
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logging.error(f"메인 실행 오류: {e}")
        logging.error(f"상세 오류: {error_detail}")
        telegram.send(f"❌ {BOT_NAME} 오류: {str(e)}")

def execute_trade(stock, config, state, balance):
    """실제 거래 실행"""
    try:
        code = stock['code']
        name = stock['name']
        price = stock['price']
        strategy = stock['strategy']
        
        # 포지션 크기 계산
        position_size = calculate_position_size(code, price, config, balance)
        
        if position_size <= 0:
            logging.info(f"{strategy} {name}({code}) - 포지션 크기 0, 거래 건너뜀")
            return False
        
        # 매수 주문
        buy_result = place_buy_order(code, name, position_size, price, strategy, config)
        
        if buy_result:
            # 포지션 상태 저장
            state['positions'][code] = {
                'name': name,
                'strategy': strategy,
                'buy_price': price,
                'quantity': position_size,
                'buy_time': datetime.now(),
                'stop_loss_price': price * (1 - config.get('stop_loss_pct', 1.0) / 100),
                'take_profit_price': price * (1 + config.get('take_profit_pct', 3.0) / 100),
                'remaining_quantity': position_size,  # 남은 수량
                'sold_quantity': 0,  # 매도한 수량
                'max_price': price,  # 최고가 추적
                'trailing_stop_price': price * 0.99  # 트레일링스탑 가격
            }
            
            logging.info(f"✅ {strategy} {name}({code}) - 매수 완료: {price:,.0f}원, 수량: {position_size:,.0f}주")
            return True
        else:
            logging.error(f"❌ {strategy} {name}({code}) - 매수 실패")
            return False
            
    except Exception as e:
        logging.error(f"거래 실행 오류: {e}")
        return False

def get_current_price(code):
    """현재 가격 조회"""
    try:
        # KIS API를 통해 현재가 조회
        current_price = KisKR.get_current_price(code)
        return current_price
    except Exception as e:
        logging.error(f"현재가 조회 오류 ({code}): {e}")
        return 0

def close_position(code, state):
    """포지션 완전 청산"""
    try:
        if code in state['positions']:
            position = state['positions'][code]
            remaining_qty = position.get('remaining_quantity', 0)
            
            if remaining_qty > 0:
                # 현재가로 전량 매도
                current_price = get_current_price(code)
                if current_price > 0:
                    place_sell_order(code, position['name'], remaining_qty, current_price, "포지션청산", position['strategy'], {}, position)
                    logging.info(f"포지션 청산: {position['name']}({code}) - {remaining_qty:,.0f}주")
            
            # 포지션 제거
            del state['positions'][code]
            
    except Exception as e:
        logging.error(f"포지션 청산 오류 ({code}): {e}")

def check_exit_conditions(state):
    """매도 조건 확인 (분할매도 + 트레일링스탑)"""
    try:
        current_time = datetime.now()
        positions_to_close = []
        
        for code, position in state['positions'].items():
            name = position['name']
            strategy = position['strategy']
            buy_price = position['buy_price']
            quantity = position['quantity']
            remaining_quantity = position['remaining_quantity']
            
            if remaining_quantity <= 0:
                continue
                
            # 현재 가격 조회
            current_price = get_current_price(code)
            if current_price <= 0:
                continue
            
            # 수익률 계산
            profit_pct = ((current_price - buy_price) / buy_price) * 100
            
            # 최고가 업데이트
            if current_price > position['max_price']:
                position['max_price'] = current_price
                # 트레일링스탑 가격 업데이트 (최고가 대비 1% 하락)
                position['trailing_stop_price'] = current_price * 0.99
            
            # 손절 확인
            if current_price <= position['stop_loss_price']:
                logging.info(f" {strategy} {name}({code}) - 손절: {profit_pct:+.2f}%")
                positions_to_close.append(code)
                continue
            
            # 분할매도 확인
            if profit_pct >= 2.0 and position['sold_quantity'] == 0:
                # 2% 도달 시 10% 매도
                sell_quantity = int(quantity * 0.1)
                if sell_quantity > 0:
                    place_sell_order(code, name, sell_quantity, current_price, "2%분할매도", strategy, {}, position)
                    position['sold_quantity'] += sell_quantity
                    position['remaining_quantity'] -= sell_quantity
                    logging.info(f" {strategy} {name}({code}) - 2% 분할매도: {sell_quantity:,.0f}주")
            
            elif profit_pct >= 3.0 and position['sold_quantity'] < quantity * 0.3:
                # 3% 도달 시 20% 매도 (총 30%)
                sell_quantity = int(quantity * 0.2)
                if sell_quantity > 0:
                    place_sell_order(code, name, sell_quantity, current_price, "3%분할매도", strategy, {}, position)
                    position['sold_quantity'] += sell_quantity
                    position['remaining_quantity'] -= sell_quantity
                    logging.info(f" {strategy} {name}({code}) - 3% 분할매도: {sell_quantity:,.0f}주")
            
            elif profit_pct >= 4.0 and position['sold_quantity'] < quantity * 0.6:
                # 4% 도달 시 30% 매도 (총 60%)
                sell_quantity = int(quantity * 0.3)
                if sell_quantity > 0:
                    place_sell_order(code, name, sell_quantity, current_price, "4%분할매도", strategy, {}, position)
                    position['sold_quantity'] += sell_quantity
                    position['remaining_quantity'] -= sell_quantity
                    logging.info(f" {strategy} {name}({code}) - 4% 분할매도: {sell_quantity:,.0f}주")
            
            elif profit_pct >= 5.0 and position['sold_quantity'] < quantity * 0.8:
                # 5% 도달 시 50% 매도 (총 80%)
                sell_quantity = int(quantity * 0.5)
                if sell_quantity > 0:
                    place_sell_order(code, name, sell_quantity, current_price, "5%분할매도", strategy, {}, position)
                    position['sold_quantity'] += sell_quantity
                    position['remaining_quantity'] -= sell_quantity
                    logging.info(f" {strategy} {name}({code}) - 5% 분할매도: {sell_quantity:,.0f}주")
            
            # 트레일링스탑 확인 (나머지 20%)
            elif current_price <= position['trailing_stop_price']:
                logging.info(f" {strategy} {name}({code}) - 트레일링스탑: {profit_pct:+.2f}%")
                positions_to_close.append(code)
                continue
            
            # 상한가 확인 (30% 상승)
            if profit_pct >= 30.0:
                logging.info(f" {strategy} {name}({code}) - 상한가 도달: {profit_pct:+.2f}%")
                # 상한가 시에는 매도하지 않고 보유
                continue
        
        # 포지션 청산
        for code in positions_to_close:
            close_position(code, state)
            
    except Exception as e:
        logging.error(f"매도 조건 확인 오류: {e}")

def test_nxt_rankings():
    """NXT 종목 조회 테스트 함수"""
    print("=" * 50)
    print("NXT 종목 조회 테스트 시작")
    print(f"테스트 시간: {datetime.now()}")
    print("=" * 50)
    
    # NXT 종목 조회
    rankings = get_nxt_rankings()
    
    print("\n" + "=" * 50)
    print("조회 결과 요약")
    print("=" * 50)
    
    if rankings:
        print(f"총 {len(rankings)}개 종목 조회됨:")
        for ranking in rankings:
            print(f"  {ranking['rank']}위: {ranking['name']}({ranking['code']}) - {ranking['price']:,.0f}원 ({ranking['pct']:+.2f}%)")
    else:
        print("조회된 종목이 없습니다.")
    
    print("\n테스트 완료!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_nxt_rankings()
    else:
        main()
