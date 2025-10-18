# -*- coding: utf-8 -*-
"""
전략4: 상한가(급등) 추종 - 다음날/당일 트레일링 라이브 전략

목적
- 장중 급등(상한가 근접) 종목을 1분 주기로 모니터링하여, 조건 충족 시 신속히 분할 진입하고 트레일링 스탑으로 리스크 관리.
- 상한가 도달 시 익일부터 완화된 트레일링으로 수익 극대화, 미도달 시 14:30 강제 청산으로 변동성 관리.

데이터 소스
- KIS 순위 등락 API로 등락률 상위 종목을 주기적으로 조회합니다.
  문서: https://apiportal.koreainvestment.com/apiservice-apiservice?/uapi/domestic-stock/v1/ranking/fluctuation
- KIS 시세 조회 API로 종목별 현재가/고가/저가/등락률/거래량/거래대금/시총을 스냅샷으로 조회합니다.

종목 선정 로직(분당 루프)
1) 1차 관찰군: 등락률 ≥ 20% (관찰 리스트에 추가)
2) 1차 필터: 최소가(기본 1,000원) 이상, 제외목록 미포함, VI/특수상태 배제, 당일상장 제외, 섹터 과집중 제한(섹터당 최대 N)
3) 스코어링: 시가총액(mcap) → 거래대금(tval) → 거래량(vol) 내림차순 정렬
4) 상위 N개만 최종 후보로 추립니다(이미 보유 중이거나 슬롯이 차면 건너뜀)
5) 최종 진입 조건: 등락률 ≥ 25% 충족 시 진입 (상단근접도 조건 제거됨)

자산 배분 / 체결
- 전략 배분율: allocation_rate(기본 10%) = 총자산 × 배분율
- 동시 보유 최대: max_parallel_positions(기본 3). per-position 예산 = 전략예산 / 최대보유수
- 최소 1주 규칙, 예산 부족 시 잔여예산 내 수량으로 조정(1주 미만이면 스킵)
- 주문 방식: 매수 지정가 = 현재가 × 1.02, 매도 시장가 (기존 지정가 0.99에서 변경)

청산 규칙(리스크 관리)
- 20% 이하 매도: 등락률이 20% 이하로 떨어지면 즉시 매도
- Intraday 트레일링: 진입 당일 고점 대비 하락률 intraday_trail_pct(기본 5%) 이탈 시 청산
- Limit Up 도달: 등락률 ≥ 29%로 판단 시 nextday 모드 전환(익일부터 트레일 기준 적용)
- Next-day 트레일링: 익일 고점 대비 하락률 nextday_trail_pct(기본 7%) 이탈 시 청산
- 14:30 강제 청산: 상한가 미도달 상태(mode != nextday)에서 14:30 이후에는 당일 전량 청산

상태 관리/복구
- LimitUpNextDay_state.json으로 관찰 리스트 및 보유 상태 유지
  - positions[code]: { mode: intraday|nextday, hi: 당일/익일 고점, entry_date, last_day }
- 분당 크론 실행 간 상태 이어받기 및 업데이트

로그/리포트/알림
- LimitUpNextDay_trades.csv: 체결 로그(date, action, code, qty, price, pnl)
- LimitUpNextDay_daily.csv: 일일 스냅샷(date, equity, cash, invested_value, n_positions)
- 텔레그램: 주문 결과 메시지(성공/실패), 청산 시 손익 이모지(🟢/🔴/⚪) 포함
- 요약 리포트: 종목별 손익, 현재/초기 분배금, 총 투자금액, 누적 실현손익 등

설정 키(기본값)
- allocation_rate=0.10, max_candidates=30, min_watch_pct=0.20, entry_pct=0.25
- intraday_trail_pct=0.05, nextday_trail_pct=0.07
- max_parallel_positions=3, buy_price_offset=1.02, min_price=1000
- exclude_codes=[], max_per_sector=1, sector_map={}
- fluct_tr_id="FHPST01700000" (순위 등락 API TR_ID, 실계정 환경에 맞게 변경 가능)

파일 경로(스크립트 기준)
- 설정: LimitUpNextDay_config.json
- 레저: LimitUpNextDay_positions.json
- 상태: LimitUpNextDay_state.json
- 로그: logs/LimitUpNextDay_trades.csv, logs/LimitUpNextDay_daily.csv

스케줄(예시)
- 리눅스 cron(한국시간): 09:01~15:20 매 1분 실행
  */1 0-6 * * 1-5 /usr/bin/python3 /path/to/kook/kis/LimitUpNextDay.py >> /path/to/kook/kis/logs/cron_limitup.log 2>&1
- 윈도우 작업 스케줄러: 평일 09:01 시작, 1분 간격 반복, 15:20에 종료. 휴장일은 내부 IsMarketOpen으로 자체 종료.

주의사항
- 실계정 TR_ID/필드명은 증권사 문서에 따라 상이할 수 있으므로 config로 주입/조정하십시오.
- 과도한 추격 리스크를 줄이기 위해 VI/섹터 제한/예산 분할을 함께 사용합니다.
- 당일 상장 종목은 전일 종가가 없어 등락률 계산이 부정확할 수 있으므로 제외합니다.
"""

import os
import sys
import json
import time
import logging
import gc
import psutil
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
import itertools
import requests
import pandas as pd

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

BOT_NAME = "LimitUpNextDay"
PortfolioName = "[상따전략]"

# 일별 로그 파일명 구성
today_str_for_log = time.strftime("%Y-%m-%d")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, f'{BOT_NAME}_{today_str_for_log}.log'), mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

ENABLE_ORDER_EXECUTION = True

config_file_path = os.path.join(script_dir, f'{BOT_NAME}_config.json')
positions_file_path = os.path.join(script_dir, f"{BOT_NAME}_positions.json")
trades_csv_path = os.path.join(logs_dir, f"{BOT_NAME}_trades.csv")
state_file_path = os.path.join(script_dir, f"{BOT_NAME}_state.json")


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

def load_positions():
    if not os.path.exists(positions_file_path):
        return {"positions": {}, "realized_profit": 0.0, "initial_allocation": None}
    try:
        with open(positions_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"positions": {}, "realized_profit": 0.0, "initial_allocation": None}


def save_positions(ledger: dict):
    try:
        with open(positions_file_path, 'w', encoding='utf-8') as f:
            json.dump(ledger, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def record_trade(date_str: str, action: str, code: str, qty: int, price: float, pnl: float | None, name: str = ""):
    import csv
    header = ["date", "action", "code", "name", "qty", "price", "pnl", "pnl_pct", "icon"]
    write_header = not os.path.exists(trades_csv_path)
    
    # 종목명 가져오기
    if not name:
        try:
            from code_name_map import get_name
            name = get_name(code) or code
        except Exception:
            name = code
    
    # 수익률 계산
    pnl_pct = None
    if pnl is not None and action == 'SELL':
        # 매도 시에만 수익률 계산 (매수 가격은 평균가로 추정)
        try:
            ledger = load_positions()
            avg_price = float(ledger.get('positions', {}).get(code, {}).get('avg', 0))
            if avg_price > 0:
                pnl_pct = round((pnl / (avg_price * qty)) * 100, 2)
        except Exception:
            pnl_pct = None
    
    # 색상 아이콘 결정
    icon = ""
    if pnl is not None:
        if pnl > 0:
            icon = "🟢"
        elif pnl < 0:
            icon = "🔴"
        else:
            icon = "⚪"
    
    try:
        with open(trades_csv_path, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(header)
            w.writerow([
                date_str, 
                action, 
                code, 
                name,
                qty, 
                round(price, 4), 
                (None if pnl is None else round(pnl, 2)),
                pnl_pct,
                icon
            ])
        logging.info(f"[거래기록] {action} 기록 완료: {name}({code}) {qty}주 @ {price:,.0f}원")
    except Exception as e:
        logging.error(f"[거래기록] {action} 기록 실패: {name}({code}) - {e}")




def format_kis_order_message(portfolio_name: str, action_kor: str, name: str, data, order_px: float | None = None) -> str:
    try:
        if isinstance(data, dict):
            rt = str(data.get('rt_cd', ''))
            msg_cd = str(data.get('msg_cd', ''))
            msg1 = str(data.get('msg1', ''))
            output = data.get('output', {})
            out = None
            if isinstance(output, list) and len(output) > 0:
                out = output[0]
            elif isinstance(output, dict):
                out = output
            ord_unpr = None
            if isinstance(out, dict):
                ord_unpr = out.get('ORD_UNPR') or out.get('ord_unpr') or out.get('ORD_PRIC') or out.get('order_price')
            if ord_unpr is None:
                ord_unpr = data.get('ORD_UNPR') or data.get('ord_unpr') or data.get('price')
            if ord_unpr is None and order_px is not None:
                ord_unpr = order_px
            status = '성공' if rt == '0' else '실패'
            return f"{portfolio_name} : {action_kor}{status} : {name} : code={msg_cd} msg={msg1} price={ord_unpr}"
        return f"{portfolio_name} : {action_kor}주문 : {name} : {data}"
    except Exception:
        return f"{portfolio_name} : {action_kor}주문 : {name} : {data}"


def _fmt_won(n: float, signed: bool = False) -> str:
    try:
        if signed:
            return f"{n:+,.0f}원"
        return f"{n:,.0f}원"
    except Exception:
        return str(n)


def send_summary_report(portfolio_name: str, ledger: dict, current_allocation: float, initial_allocation: float, name_map: Dict[str, str]) -> None:
    try:
        positions = ledger.get('positions', {})
        lines = []
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        win_cnt = lose_cnt = flat_cnt = 0
        invested_value_now = 0.0
        cost_basis = 0.0
        for code, pos in positions.items():
            qty = int(pos.get('qty', 0))
            status = pos.get('status', '')
            if qty <= 0:
                continue
            
            # 구매중 상태는 표시하지 않음
            if status == '구매중':
                continue
                
            avg = float(pos.get('avg', 0.0))
            cur = float(KisKR.GetCurrentPrice(code))
            now_val = qty * cur
            invested_value_now += now_val
            cost_basis += qty * avg
            pnl_abs = (cur - avg) * qty
            pnl_pct = ((cur / avg) - 1.0) * 100.0 if avg > 0 else 0.0
            icon = '🟢' if pnl_abs > 0 else ('🔴' if pnl_abs < 0 else '⚪')
            if pnl_abs > 0:
                win_cnt += 1
            elif pnl_abs < 0:
                lose_cnt += 1
            else:
                flat_cnt += 1
            name = name_map.get(code, code)
            lines.append(f"{icon} {name}({qty}주)\n   {_fmt_won(now_val)}({_fmt_won(pnl_abs, signed=True)}:{pnl_pct:+.2f}%)")
        current_profit = invested_value_now - cost_basis
        current_profit_pct = (current_profit / cost_basis * 100.0) if cost_basis > 0 else 0.0
        realized = float(ledger.get('realized_profit', 0.0))
        header = [
            f"📊 {portfolio_name}",
            f"상세 수익 현황 ({ts})",
            "==================================",
        ]
        footer = [
            "==================================",
            f"💰 초기 분배금: {_fmt_won(initial_allocation)}",
            f"💰 현재 분배금: {_fmt_won(current_allocation)}",
            f"💰 총 투자금액: {_fmt_won(cost_basis)}",
            f"📈 현재 수익금: {_fmt_won(current_profit)}({current_profit_pct:+.2f}%)",
            f"📊 누적 판매 수익금: {_fmt_won(realized)}",
            f"📊 종목별 현황: 수익 {win_cnt}개, 손실 {lose_cnt}개, 손익없음 {flat_cnt}개",
        ]
        msg = "\n".join(header + lines + footer)
        telegram.send(msg)
    except Exception:
        pass


def _kis_headers(tr_id: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {Common.GetToken(Common.GetNowDist())}",
        "appKey": Common.GetAppKey(Common.GetNowDist()),
        "appSecret": Common.GetAppSecret(Common.GetNowDist()),
        "tr_id": tr_id,
        "tr_cont": "N",  # API 문서 요구사항
        "custtype": "P",  # 개인 고객 구분 추가 (일부 엔드포인트 호환성)
        "seq_no": "",  # API 문서 요구사항
    }


def _fetch_top_movers_kis(limit: int = 10, sort_type: str = "0") -> List[Dict[str, str]]:
    # KIS 순위 등락 API 사용 시도, 실패 시 빈 리스트
    max_retries = 3
    for attempt in range(max_retries):
        try:
            base = Common.GetUrlBase(Common.GetNowDist())
            path = "uapi/domestic-stock/v1/ranking/fluctuation"
            url = f"{base}/{path}"
            # 설정에서 tr_id 로드
            try:
                with open(config_file_path, 'r', encoding='utf-8') as cf:
                    _cfg = json.load(cf)
                tr_id = _cfg.get('fluct_tr_id', 'FHPST01700000')
            except Exception:
                tr_id = 'FHPST01700000'
            headers = _kis_headers(tr_id=tr_id)
            safe_limit = max(1, min(int(limit), 50))  # 최대 50개까지 조회 가능
            # KIS 문서 기준 파라미터(_code 접미 포함) + 하위호환 키 병행 전송
            params = {
                # 필수 파라미터들 (API 문서 기준)
                "fid_rsfl_rate2": "",              # 공백 입력 시 전체 (~ 비율)
                "fid_cond_mrkt_div_code": "J",     # 시장구분코드 (J:KRX)
                "fid_cond_scr_div_code": "20170",  # Unique key(20170)
                "fid_input_iscd": "0000",         # 0000(전체)
                "fid_rank_sort_cls_code": sort_type,     # 0:상승율순, 1:하락율순, 4:변동율
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
                "fid_rank_sort_cls": sort_type,          # 구버전 키 병행
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
            
            out = []
            for it in items:
                code = it.get('rsym') or it.get('mksc_shrn_iscd') or it.get('symb') or it.get('stck_shrn_iscd')
                name = it.get('rsym_nm') or it.get('hts_kor_isnm') or it.get('itemnm') or code
                pct = it.get('prdy_ctrt') or it.get('rate') or it.get('fluctuation_rate')
                try:
                    pct_f = float(str(pct).replace('%',''))
                except Exception:
                    pct_f = 0.0
                if code:
                    out.append({'code': code, 'name': name, 'pct': pct_f})
            
            logging.info(f"KIS API 성공: {len(out)}개 종목 조회됨")
            return out
            
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

def _get_discovery_candidates(cfg: dict, state: dict, limit: int) -> List[Dict[str, str]]:
    # 10~30분 간격 캐시. KIS API를 사용하여 상한가 종목 선별
    try:
        refresh_min = int(cfg.get('discovery_refresh_min', 10))
    except Exception:
        refresh_min = 10
    refresh_min = max(1, min(refresh_min, 60))
    now_ts = time.time()
    last_ts = float(state.get('last_discovery_ts', 0.0) or 0.0)
    cached = state.get('last_candidates')
    if cached and (now_ts - last_ts) < refresh_min * 60:
        return cached[: max(1, int(limit))]

    # KIS API를 사용하여 상한가 종목 선별 (상승률 순만 사용)
    movers: List[Dict[str, str]] = []
    
    # 상승률 순 조회 (30개)
    movers = _fetch_top_movers_kis(limit=30, sort_type="0")
    
    if movers:
        # 수익률 기준으로 내림차순 정렬
        sorted_stocks = sorted(movers, key=lambda x: x.get('pct', 0), reverse=True)
        
        # 20% 이상 종목들을 모두 후보로 고려 (상한가 종목 포함)
        high_pct_stocks = [s for s in sorted_stocks if s.get('pct', 0) >= 20.0]
        
        # 20% 이상 종목들 상세 로그 출력
        logging.info(f"20% 이상 종목 {len(high_pct_stocks)}개 발견:")
        for i, stock in enumerate(high_pct_stocks, 1):
            logging.info(f"  {i}. {stock.get('name', 'N/A')} ({stock.get('code', 'N/A')}) - {stock.get('pct', 0):.2f}%")
        
        if high_pct_stocks:
            movers = high_pct_stocks[:limit]
        else:
            movers = sorted_stocks[:limit]
        state['last_discovery_source'] = 'KIS_API'
    else:
        # KIS API 실패 시 빈 리스트 반환
        logging.warning("KIS API 조회 실패, 빈 리스트 반환")
        state['last_discovery_source'] = 'FAILED'

    if movers:
        state['last_candidates'] = movers
        state['last_discovery_ts'] = now_ts
    return movers




def initialize_and_check_conditions():
    """프로그램 실행 전 초기화 및 조건 체크"""
    # 잔고 조회 하면서 토큰 발급
    balance = KisKR.GetBalance()
    
    # 실행 가드
    now = datetime.now()
    if now.weekday() >= 5:
        msg = f"{PortfolioName}({now.strftime('%Y-%m-%d')})\n주말(토/일)에는 실행하지 않습니다."
        sys.exit(0)

    # 평일 장 마감(15:30) 이후에는 실행하지 않고 조용히 종료
    # 테스트를 위해 임시 비활성화
    if now.hour > 15 or (now.hour == 15 and now.minute > 30):
        print(f"장 마감 후 종료: {now.hour}:{now.minute}")
        sys.exit(0)

    is_market_open = KisKR.IsMarketOpen()
    current_date = time.strftime("%Y-%m-%d")
    if not is_market_open:
        logging.info(f"날짜 {current_date} : 장이 닫혀있습니다.")
        #telegram.send(f"{PortfolioName}({current_date})\n장이 닫혀있습니다.")
        sys.exit(0)
    else:
        logging.info(f"날짜 {current_date} : 장이 열려있습니다.")
        # 실행할 때마다 알림 과다 방지를 위해 주석 처리
        # telegram.send(f"{PortfolioName}({current_date})\n장이 열려있습니다.")
    
    return balance, current_date



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
    # 0) 초기화 및 조건 체크
    now = datetime.now()
    logging.info(f"[시작] LimitUpNextDay 전략 실행 - {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # KOSPIDrawdown 포지션 체크
    if check_kospi_drawdown_positions():
        logging.info("KOSPIDrawdown 전략이 포지션을 보유 중입니다. 상따전략을 중단합니다.")
        return
    
    Balance, current_date = initialize_and_check_conditions()
    print(Balance, current_date)
    
    # 설정
    try:
        with open(config_file_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {
            "allocation_rate": 0.10,
            "max_candidates": 10,
            "min_watch_pct": 0.15,
            "entry_pct": 0.20,
            "max_parallel_positions": 3,
            "buy_price_offset": 1.02,
            "intraday_trail_pct": 0.05,
            "nextday_trail_pct": 0.07,
            "min_price": 1000,
            "exclude_codes": [],
            "max_per_sector": 1,
            "sector_map": {},
            "fluct_tr_id": "FHPST01700000",
        }
        logging.warning(f"설정 파일이 없어 기본값으로 실행합니다: {config_file_path}")
    except Exception as e:
        logging.error(f"설정 로딩 실패: {e}")
        telegram.send(f"{PortfolioName} 설정 로딩 실패. 종료")
        sys.exit(1)

    # 예산 산정
    total_equity = float(Balance['TotalMoney'])
    InvestRate = float(cfg.get('allocation_rate', 0.10))
    TotalMoney = total_equity * InvestRate
    ledger = load_positions()
    if ledger.get('initial_allocation') is None:
        ledger['initial_allocation'] = TotalMoney
        save_positions(ledger)

    # 상태 로드(분당 실행 지속 관리)
    try:
        if os.path.exists(state_file_path):
            with open(state_file_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
        else:
            state = {"watched": []}
    except Exception:
        state = {"watched": []}

    # 현재 보유 평가/일일 기록 및 오픈 포지션 수
    did_trade = False  # 이 실행에서 매수/매도 발생 여부

    invested_value = 0.0
    for code, pos in ledger.get('positions', {}).items():
        if int(pos.get('qty', 0)) > 0:
            invested_value += int(pos['qty']) * KisKR.GetCurrentPrice(code)
    cash = max(0.0, TotalMoney - invested_value)

    # 보유 종목 관리

    def _sell_all(code: str, qty: int, px: float, name: str, reason: str = ""):
        # 시장가로 매도 전환
        logging.info(f"[매도] {name}({code}) {qty}주 매도 시작 - 이유: {reason}")
        logging.info(f"[매도상세] 종목: {name}({code}), 수량: {qty}주, 예상가격: {px:,.0f}원, 사유: {reason}")
        try:
            data = KisKR.MakeSellMarketOrder(code, qty)
            logging.info(f"[매도] {name}({code}) 시장가 매도 주문 성공")
        except Exception as e:
            logging.error(f"[매도] {name}({code}) 시장가 매도 주문 실패: {e}")
            data = None
        # 기존 지정가 매도 코드
        # data = KisKR.MakeSellLimitOrder(code, qty, px)
        pos = ledger['positions'].get(code, {"qty": 0, "avg": 0.0})
        avg = float(pos.get('avg', 0.0))
        # 매도가(px)를 사용하여 손익 계산
        pnl = (px - avg) * qty
        pos['qty'] = max(0, int(pos.get('qty', 0)) - qty)
        if pos['qty'] == 0:
            pos['avg'] = 0.0
        ledger['positions'][code] = pos
        ledger['realized_profit'] = float(ledger.get('realized_profit', 0.0)) + pnl
        save_positions(ledger)
        logging.info(f"[매도] {name}({code}) 거래 기록 시작 - qty: {qty}, px: {px:,.0f}, pnl: {pnl:,.0f}")
        record_trade(current_date, 'SELL', code, qty, px, pnl, name)
        logging.info(f"[매도] {name}({code}) 매도 완료 - 평단: {avg:,.0f}원, 매도가: {px:,.0f}원, 손익: {pnl:,.0f}원")
        try:
            icon = '🟢' if pnl > 0 else ('🔴' if pnl < 0 else '⚪')
            msg = format_kis_order_message(PortfolioName, '매도', name, data, order_px=px)
            reason_text = reason if reason else '전략 규칙에 따른 매도'
            logging.info(f"[텔레그램] {name}({code}) 매도 메시지 전송: {reason_text}")
            telegram.send(f"{icon} {msg}\n이유: {reason_text}")
        except Exception as e:
            logging.error(f"[텔레그램] {name}({code}) 매도 메시지 전송 실패: {e}")
        # 매도 발생
        nonlocal did_trade
        did_trade = True

    # 상태 구조 보정
    if 'positions' not in state:
        state['positions'] = {}
    
    # name_map 초기화 (sync_positions_with_actual_holdings에서 사용)
    name_map: Dict[str, str] = {}
    
    def sync_positions_with_actual_holdings(ledger: dict) -> dict:
        """실제 보유 자산과 JSON 파일을 동기화합니다. (Momentum20.py 방식)"""
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
                    # 종목명 가져오기
                    stock_name = item.get('StockName', '') or name_map.get(code, code)
                    actual_positions[code] = {
                        'qty': qty,
                        'avg': avg_price,
                        'status': '보유중',
                        'name': stock_name
                    }
            
            # JSON 파일의 포지션과 비교
            json_positions = ledger.get('positions', {})
            sync_changes = []
            
            # 1. JSON에 있지만 실제로는 없는 종목 (매도 성공)
            codes_to_remove = []
            for code, pos in json_positions.items():
                if code not in actual_positions:
                    if pos.get('status') == '구매중':
                        sync_changes.append(f"미체결: {code} {name_map.get(code, code)} (JSON: {pos.get('qty', 0)}주)")
                        pos['status'] = '미체결'
                        json_positions[code] = pos
                    elif pos.get('status') == '보유중':
                        # 상한가 종목(nextday 모드)은 API 조회 실패일 가능성이 높으므로 안전장치 적용
                        if pos.get('mode') == 'nextday' or pos.get('next_day_trail') == True:
                            logging.warning(f"[포지션동기화] 상한가 종목 {code} {name_map.get(code, code)} API 조회 실패 - 매도 처리하지 않음")
                            sync_changes.append(f"API 조회 실패: {code} {name_map.get(code, code)} (상한가 종목, 매도 처리 안함)")
                            continue
                        else:
                            sync_changes.append(f"매도 완료: {code} {name_map.get(code, code)} (JSON: {pos.get('qty', 0)}주)")
                            codes_to_remove.append(code)
            
            # 제거할 종목들을 JSON에서 제거
            for code in codes_to_remove:
                json_positions.pop(code, None)
            
            # 2. JSON에 있는 종목만 처리 (이 전략이 매수한 종목의 체결 확인)
            for code, json_pos in json_positions.items():
                if code in actual_positions:
                    # 실제 보유 중인 종목: 수량이나 평단이 다르면 업데이트
                    actual_pos = actual_positions[code]
                    if (json_pos.get('qty', 0) != actual_pos['qty'] or 
                        abs(json_pos.get('avg', 0) - actual_pos['avg']) > 0.01):
                        sync_changes.append(
                            f"부분 체결: {code} {name_map.get(code, code)} "
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
                            sync_changes.append(f"보유 확인: {code} {name_map.get(code, code)} {actual_pos['qty']}주")
                            json_positions[code]['status'] = '보유중'
                else:
                    # JSON에 있지만 실제로는 없는 종목 (이미 처리됨)
                    pass
            
            # 변경사항이 있으면 로그 출력 및 저장
            if sync_changes:
                logging.info("[LimitUp] 포지션 동기화 완료:")
                for change in sync_changes:
                    logging.info(f"  - {change}")
                
                # 텔레그램 메시지 전송
                for change in sync_changes:
                    if "보유 확인" in change:
                        try:
                            telegram.send(f"✅ {PortfolioName} : {change}")
                        except Exception:
                            pass
                    elif "매도 완료" in change:
                        try:
                            telegram.send(f"🔴 {PortfolioName} : {change}")
                        except Exception:
                            pass
                
                # JSON 파일 업데이트
                ledger['positions'] = json_positions
                save_positions(ledger)
            else:
                logging.info("[LimitUp] 포지션 동기화: 변경사항 없음")
            
            return ledger
            
        except Exception as e:
            logging.error(f"포지션 동기화 실패: {e}")
            return ledger
    
    # 실제 보유 종목 확인 및 동기화
    ledger = sync_positions_with_actual_holdings(ledger)

    # 15:20 이후 미체결 종목 삭제 처리
    now_hm = time.strftime('%H:%M')
    if now_hm >= '15:20':
        removed_unfilled = []
        for code, pos in list(ledger.get('positions', {}).items()):
            status = pos.get('status', '')
            if status in ['구매중', '미체결']:
                name = name_map.get(code, code)
                removed_unfilled.append(f"{name}({code})")
                # positions.json에서 제거
                ledger['positions'].pop(code, None)
                # state에서도 제거
                state['positions'].pop(code, None)
                logging.info(f"[마감정리] 미체결 종목 삭제: {name}({code}) - 상태: {status}")
        
        if removed_unfilled:
            save_positions(ledger)
            try:
                telegram.send(f"🧹 {PortfolioName} 마감 정리: 미체결 종목 {len(removed_unfilled)}개 삭제\n" + 
                            "\n".join(removed_unfilled))
            except Exception as e:
                logging.error(f"미체결 종목 삭제 알림 전송 실패: {e}")

    # 보유 종목 관리: 보유중 상태일 때만 매도 검토
    for code, pos in list(ledger.get('positions', {}).items()):
        qty = int(pos.get('qty', 0))
        status = pos.get('status', '')
        
        # 보유중이 아니면 건너뜀
        if status != '보유중' or qty <= 0:
            if status == '구매중':
                logging.info(f"구매중: {name_map.get(code, code)}({code}) - 체결 대기")
            elif status == '미체결':
                logging.info(f"미체결: {name_map.get(code, code)}({code}) - 매수 실패")
            continue
            
        # 현재가 조회 (KisKR.GetCurrentPrice 사용)
        try:
            cur = float(KisKR.GetCurrentPrice(code))
            if cur <= 0:
                continue
        except Exception:
            continue
            
        # KIS API로 현재 등락률 조회 (매수 조건과 동일한 기준)
        try:
            # KIS API로 현재 등락률 조회
            movers = _fetch_top_movers_kis(limit=50, sort_type="0")
            pct_now = 0.0
            for mover in movers:
                if mover.get('code') == code:
                    pct_now = float(mover.get('pct', 0.0))
                    break
            
            # KIS API에서 찾지 못한 경우 진입가 기준으로 계산
            if pct_now == 0.0:
                avg_price = float(pos.get('avg', 0.0))
                if avg_price > 0:
                    pct_now = ((cur - avg_price) / avg_price) * 100.0
                else:
                    pct_now = 0.0
        except Exception as e:
            logging.debug(f"{code} KIS API 등락률 조회 실패, 진입가 기준으로 계산: {e}")
            # KIS API 조회 실패 시 진입가 기준으로 계산
            avg_price = float(pos.get('avg', 0.0))
            if avg_price > 0:
                pct_now = ((cur - avg_price) / avg_price) * 100.0
            else:
                pct_now = 0.0
            
        # 고가/저가는 간단히 현재가 기준으로 설정
        high = cur * 1.1  # 임시 고가 (10% 상승 가정)
        low = cur * 0.9   # 임시 저가 (10% 하락 가정)
        # 포지션에서 종목명 가져오기, 없으면 name_map에서, 그것도 없으면 코드 사용
        name = pos.get('name') or name_map.get(code, code)
        
        # 상태 가져오기/초기화
        sp = state['positions'].get(code, None)
        if sp is None:
            sp = {
                "entry_date": current_date, 
                "mode": "intraday", 
                "hi": cur, 
                "next_day_trail": False, 
                "last_day": current_date
            }
        
        # 상한가 판단: 등락률 29% 이상으로 간주
        try:
            if pct_now >= 29.0:
                sp['next_day_trail'] = True
                sp['mode'] = 'nextday'
                logging.info(f"상한가 도달: {name}({code}) {pct_now:.2f}% -> nextday 모드 전환")
        except Exception:
            pass
        
        # 일자 변경 시 nextday 모드면 hi 리셋
        if sp.get('mode') == 'nextday' and sp.get('last_day') != current_date:
            sp['hi'] = cur
            sp['last_day'] = current_date
            logging.info(f"다음날 모드: {name}({code}) 고점 리셋")
        
        # hi 업데이트
        sp['hi'] = max(float(sp.get('hi', 0.0)), cur, high)
        
        # 새로운 전략: 현재 등락률 15% 이하 시 매도
        if pct_now <= 15.0:
            logging.info(f"[보유관리] {name}({code}) 현재 등락률 {pct_now:.2f}% <= 15% - 매도 조건 충족")
            sell_px = cur * 0.99
            reason = f"등락률 15% 이하로 하락하여 매도 (현재: {pct_now:.2f}% <= 15%)"
            logging.info(f"[매도사유] {name}({code}): {reason}")
            _sell_all(code, qty, sell_px, name, reason=reason)
            state['positions'].pop(code, None)
            continue
        
        
        # 15:20 강제 청산: 상한가 미도달 상태(mode != nextday)에서 15:20 이후에는 당일 전량 청산
        now_hm = time.strftime('%H:%M')
        if now_hm >= '15:20' and sp.get('mode') != 'nextday':
            logging.info(f"[보유관리] {name}({code}) 15:20 강제 청산 조건 충족 - 현재시간: {now_hm}, mode: {sp.get('mode')}")
            sell_px = cur * 0.99
            reason = f"15:20 강제 청산 (상한가 미도달로 당일 전량 매도, mode: {sp.get('mode')})"
            logging.info(f"[매도사유] {name}({code}): {reason}")
            _sell_all(code, qty, sell_px, name, reason=reason)
            state['positions'].pop(code, None)
            continue
        
        # 현재 등락률 15% 이상이면 유지
        if pct_now > 15.0:
            # 상태 저장 반영
            state['positions'][code] = sp
            logging.info(f"[보유관리] {name}({code}) 보유 유지 - 현재 등락률 {pct_now:.2f}% (15% 이상), mode: {sp.get('mode')}")

    # 이미 최대 포지션이면 스캔 없이 종료
    max_pos = int(cfg.get('max_parallel_positions', 3))
    open_positions = sum(1 for p in ledger.get('positions', {}).values() if int(p.get('qty', 0)) > 0)
    if open_positions >= max_pos:
        logging.info(f"최대 포지션({max_pos}) 보유 중, 스캔 건너뜀")
        # 요약은 조건부 전송
        try:
            now_hm = time.strftime('%H:%M')
            last_summary_date = state.get('last_summary_date') if isinstance(state, dict) else None
            if now_hm >= '15:20' and last_summary_date != current_date:
                send_summary_report(
                    PortfolioName,
                    ledger,
                    current_allocation=TotalMoney,
                    initial_allocation=float(ledger.get('initial_allocation') or TotalMoney),
                    name_map={},
                )
                state['last_summary_date'] = current_date
                with open(state_file_path, 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return

    if not ENABLE_ORDER_EXECUTION:
        logging.info('매매 실행 비활성화')
        return

    if not KisKR.IsMarketOpen():
        logging.info('장이 열려있지 않습니다.')
        return

    # KIS 로부터 내 계좌 정보를 읽어온다!
    try:
        # 지갑 잔고와 포지션 동기화
        Common.sync_positions_with_wallet(BOT_NAME)
        
    except Exception as e:
        logging.error(f"계좌 동기화 실패: {e}")
        telegram.send(f"{PortfolioName} 계좌 동기화 실패. 종료")
        sys.exit(1)

    # 후보 조회(캐시 사용: NAVER 고정, 주기 설정)
    movers = _get_discovery_candidates(cfg, state, limit=int(cfg.get('max_candidates', 30)))
    if not movers:
        logging.info('등락률 순위 조회 실패/빈 목록')
        # 요약은 조건부 전송
        try:
            now_hm = time.strftime('%H:%M')
            last_summary_date = state.get('last_summary_date') if isinstance(state, dict) else None
            if now_hm >= '15:20' and last_summary_date != current_date:
                send_summary_report(
                    PortfolioName,
                    ledger,
                    current_allocation=TotalMoney,
                    initial_allocation=float(ledger.get('initial_allocation') or TotalMoney),
                    name_map={},
                )
                state['last_summary_date'] = current_date
                with open(state_file_path, 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return
    
    logging.info(f"후보 종목 {len(movers)}개 조회됨")
    for i, mover in enumerate(movers[:5], 1):  # 상위 5개만 로그
        logging.info(f"  {i}. {mover.get('name', 'N/A')} ({mover.get('code', 'N/A')}) - {mover.get('pct', 0):.2f}%")
    
    # 텔레그램으로 후보 종목 정보 전송
    try:
        top_stocks_msg = f"📊 {PortfolioName} 후보 종목 {len(movers)}개 조회됨\n"
        for i, mover in enumerate(movers[:5], 1):
            pct = mover.get('pct', 0)
            emoji = "🔥" if pct >= 29.0 else "⬆️" if pct > 0 else "⬇️" if pct < 0 else "➖"
            top_stocks_msg += f"{i}. {emoji} {mover.get('name', 'N/A')} ({mover.get('code', 'N/A')}) - {pct:.2f}%\n"
        #telegram.send(top_stocks_msg)
    except Exception as e:
        logging.warning(f"텔레그램 후보 종목 전송 실패: {e}")

    min_watch_pct = float(cfg.get('min_watch_pct', 0.20)) * 100.0 if cfg.get('min_watch_pct', 0.20) < 1 else float(cfg.get('min_watch_pct', 20.0))
    entry_pct = float(cfg.get('entry_pct', 0.25)) * 100.0 if cfg.get('entry_pct', 0.25) < 1 else float(cfg.get('entry_pct', 25.0))
    buy_off = float(cfg.get('buy_price_offset', 1.02))
    
    logging.info(f"매수 조건: 관찰={min_watch_pct:.1f}%, 진입={entry_pct:.1f}%, 매도=15% 이하, 가격오프셋={buy_off:.2f}")
    
    # 텔레그램으로 매수 조건 정보 전송
    try:
        conditions_msg = f"⚙️ {PortfolioName} 전략 조건\n"
        conditions_msg += f"관찰 시작: {min_watch_pct:.1f}%\n"
        conditions_msg += f"진입 조건: {entry_pct:.1f}%\n"
        conditions_msg += f"매도 조건: 15% 이하\n"
        conditions_msg += f"가격오프셋: {buy_off:.2f}\n"
        conditions_msg += f"최대포지션: {max_pos}개"
        #telegram.send(conditions_msg)
    except Exception as e:
        logging.warning(f"텔레그램 전략 조건 전송 실패: {e}")

    budget_used = invested_value
    name_map: Dict[str, str] = {}

    # 섹터 과집중 제한 준비
    sector_map = cfg.get('sector_map', {})
    max_per_sector = int(cfg.get('max_per_sector', 1))
    sector_count: Dict[str, int] = {}

    min_price = float(cfg.get('min_price', 1000))
    exclude_codes = set(cfg.get('exclude_codes', []))

    # 1차 후보 스코어링용 버퍼
    scored: List[Dict[str, object]] = []
    logging.info(f"스코어링 시작: {len(movers)}개 후보 종목 처리")
    for mv in movers:
        if open_positions >= max_pos:
            logging.info('목표 포지션 찼음. 추가 스캔 중지')
            break
        code = mv['code']
        name = mv.get('name', code)
        pct = float(mv.get('pct', 0.0))
        name_map[code] = name

        if pct < min_watch_pct:
            logging.info(f"{name}({code}) 관찰 조건 미충족: {pct:.2f}% < {min_watch_pct:.1f}%")
            continue

        # 현재가 조회 (KisKR.GetCurrentPrice 사용)
        try:
            cur = float(KisKR.GetCurrentPrice(code))
            if cur <= 0:
                logging.info(f"{name}({code}) 현재가 조회 실패: {cur}")
                continue
        except Exception as e:
            logging.info(f"{name}({code}) 현재가 조회 실패: {e}")
            continue
        
        
        # 고가/저가/등락률은 간단히 현재가 기준으로 설정
        high = cur * 1.1  # 임시 고가 (10% 상승 가정)
        low = cur * 0.9   # 임시 저가 (10% 하락 가정)
        pct = float(mv.get('pct', 0.0))  # 이미 계산된 등락률 사용
        # 가격/제외/VI/정지 등 기초 필터
        if cur < min_price or code in exclude_codes:
            logging.info(f"{name}({code}) 가격/제외 필터: {cur} < {min_price} 또는 제외목록")
            continue
        
        # 31% 이상 종목은 매수 금지 (상한가 초과)
        if pct > 30.0:
            logging.info(f"{name}({code}) 31% 이상 종목으로 매수 금지: {pct:.2f}%")
            continue

        # 섹터 과집중 제한
        sector = sector_map.get(code, None)
        if sector is not None:
            if sector_count.get(sector, 0) >= max_per_sector:
                logging.info(f"{name}({code}) 섹터 과집중 제한: {sector}")
                continue

        # 관찰군 등록
        if pct >= min_watch_pct and code not in state.get('watched', []):
            state['watched'].append(code)
            logging.info(f"관찰군 추가: {name}({code}) {pct:.2f}%")

        # 1차 후보에 스코어 저장(시총/거래대금/거래량)
        scored.append({
            'code': code,
            'name': name,
            'pct': pct,
            'mcap': 0.0,  # 시총 정보 없음
            'tval': 0.0,  # 거래대금 정보 없음
            'vol': 0.0,   # 거래량 정보 없음
            'cur': cur,
            'sector': sector,
        })
        logging.info(f"후보 추가: {name}({code}) {pct:.2f}% 현재가={cur:,.0f}원")

    # 시총(내림차순) → 거래대금 → 거래량 우선 정렬 후 상위 후보만 사용
    if scored:
        scored.sort(key=lambda x: (x['mcap'], x['tval'], x['vol']), reverse=True)
        scored = scored[:max(0, max_pos - open_positions)]
        logging.info(f"스코어링 완료: {len(scored)}개 후보 선정")

    # 15:20 이후 매수 금지 체크
    now_hm = time.strftime('%H:%M')
    if now_hm >= '15:00':
        logging.info(f"[진입검토] 15:20 이후 매수 금지 - 현재시간: {now_hm}")
        return

    # 진입 루프(선정된 상위 후보만)
    for item in scored:
        if open_positions >= max_pos:
            break
        code = item['code']; name = item['name']; cur = float(item['cur'])
        pct = float(item['pct'])
        sector = item['sector']

        logging.info(f"[진입검토] {name}({code}) 등락률: {pct:.2f}% (진입조건: {entry_pct:.1f}% 이상)")
        
        # 새로운 진입 조건: 25% 이상이면 구매
        if pct >= entry_pct:  # CTR 조건 제거, 25% 이상만 체크
            if int(ledger.get('positions', {}).get(code, {}).get('qty', 0)) > 0:
                logging.info(f"[진입검토] {name}({code}) 이미 보유 중 - 건너뜀")
                continue
            
            logging.info(f"[진입검토] {name}({code}) 진입 조건 충족 - 등락률 {pct:.2f}% >= {entry_pct:.1f}%")
            
            # 29% 이상(상한가 근처)에서는 시장가 매수, 그 외에는 지정가 매수
            if pct >= 29.0:
                px = cur  # 시장가 매수 (현재가 기준)
                order_type = "시장가"
                logging.info(f"상한가 근처 매수: {name}({code}) {px:,.0f}원 (현재가: {cur:,.0f}원, 등락률: {pct:.2f}%) - {order_type}")
            else:
                px = cur * buy_off  # 현재가 × 1.02 (지정가)
                order_type = "지정가"
                logging.info(f"일반 매수: {name}({code}) {px:,.0f}원 (현재가: {cur:,.0f}원, 등락률: {pct:.2f}%) - {order_type}")
                
            if px <= 0:
                logging.warning(f"잘못된 가격: {name}({code}) {px}")
                continue
                
            # per-position 목표 예산
            per_budget = TotalMoney / max_pos
            qty = max(1, int(per_budget / px))
            need = qty * px
            
            if budget_used + need > TotalMoney:
                remain = TotalMoney - budget_used
                adj = int(remain / px)
                if adj < 1:
                    logging.warning(f"예산 부족: {name}({code}) 필요={need:,.0f}, 잔여={remain:,.0f}")
                    continue
                qty = adj
                need = qty * px

            logging.info(f"[매수] {name}({code}) {qty}주 @ {px:,.0f}원 (총 {need:,.0f}원) - 신규 진입 - {order_type}")
            
            # 29% 이상에서는 시장가 매수, 그 외에는 지정가 매수
            if pct >= 29.0:
                data = KisKR.MakeBuyMarketOrder(code, qty)
                logging.info(f"[매수] {name}({code}) 시장가 매수 주문 실행")
            else:
                data = KisKR.MakeBuyLimitOrder(code, qty, px)
                logging.info(f"[매수] {name}({code}) 지정가 매수 주문 실행")
            try:
                msg = format_kis_order_message(PortfolioName, '매수', name, data, order_px=px)
                logging.info(f"[텔레그램] {name}({code}) 매수 메시지 전송")
                telegram.send(msg)
                logging.info(f"[텔레그램] {name}({code}) 텔레그램 전송 완료: {msg}")
            except Exception as e:
                logging.error(f"[텔레그램] {name}({code}) 텔레그램 전송 실패: {e}")

            pos = ledger['positions'].get(code, {"qty": 0, "avg": 0.0, "status": "구매중"})
            old_qty = int(pos.get('qty', 0))
            old_avg = float(pos.get('avg', 0.0))
            new_qty = old_qty + qty
            new_avg = px if new_qty == 0 else ((old_avg * old_qty + px * qty) / max(1, new_qty))
            ledger['positions'][code] = {
                "qty": new_qty, 
                "avg": new_avg, 
                "status": "구매중",  # 매수 주문 후 구매중 상태로 설정
                "name": name  # 종목명 저장
            }
            save_positions(ledger)
            logging.info(f"[매수] {name}({code}) 거래 기록 시작 - qty: {qty}, px: {px:,.0f}")
            record_trade(current_date, 'BUY', code, qty, px, None, name)
            
            # 구매중 메시지 전송
            try:
                telegram.send(f"🔄 {PortfolioName} : {name}({code}) 구매중 - {qty}주 @ {px:,.0f}원")
            except Exception:
                pass

            open_positions += 1
            budget_used += need
            if sector is not None:
                sector_count[sector] = sector_count.get(sector, 0) + 1
            # 매수 발생
            did_trade = True
            logging.info(f"매수 완료: {name}({code}) {new_qty}주 평균 {new_avg:,.0f}원")
        else:
            logging.info(f"진입 조건 미충족: {name}({code}) {pct:.2f}% < {entry_pct:.1f}% (25% 미만)")

    # 리포트: 실행할 때마다 보내지 않도록 제어
    try:
        now_hm = time.strftime('%H:%M')
        last_summary_date = state.get('last_summary_date') if isinstance(state, dict) else None
        should_send = False
        # 거래 발생 시 즉시 1회 허용
        if did_trade:
            should_send = True
        # 또는 마감 무렵 1회(예: 15:20 이후 하루 1회)
        elif now_hm >= '15:20' and last_summary_date != current_date:
            should_send = True
            state['last_summary_date'] = current_date
        if should_send:
            send_summary_report(PortfolioName, ledger, TotalMoney, float(ledger.get('initial_allocation') or TotalMoney), name_map)
    except Exception:
        pass

    # 상태 저장
    try:
        with open(state_file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    
    # 메모리 정리
    cleanup_memory()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.exception(f"{BOT_NAME} 실행 오류: {e}")
        telegram.send(f"{PortfolioName} 실행 오류: {e}")


