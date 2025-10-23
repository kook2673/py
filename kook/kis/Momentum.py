# -*- coding: utf-8 -*-
"""
전략: 코스피/코스닥 시총 Top100 중 모멘텀 Top30 일간 리밸런싱 (라이브)

1) 전략 개요
- 유니버스: 코스피100 + 코스닥100(월 1회 상위시총 스냅샷 저장)
- 선정: 내부 신호(모멘텀)로 상위 30개 후보 선정
- 배분: 총자산의 40%를 전략 예산으로 사용, 종목별 균등(1/30) 목표, 최소 1주 규칙
- 실행: 매일 스케줄 실행하되, '일간 리밸런싱'으로 실 매매 수행

2) 리밸런싱/주문 규칙
- 최대 30종목까지 매수 성공 보장: 예산/체결 사유로 건너뛰면 다음 후보(31, 32...)를 연속 시도
- 최소 1주 규칙: 1/30 예산으로 1주 미만이면 1주로 보정(단, 총예산 40%는 절대 초과 금지)
- 매도 → 매수 순서 실행, 체결 후 전략 레저(수량/평단/실현손익) 업데이트

3) 데이터/로그 파일
- Momentum_config.json: 전략 전용 설정(배분율, 최대 보유수, 월간 업데이트일, 일간 요일/시각 등)
- Momentum_positions.json: 전략 원장(positions{code:{qty,avg}}, realized_profit)
- logs/Momentum_trades.csv: 체결 로그(date, action, code, qty, price, pnl)
- logs/Momentum_daily.csv: 일일 스냅샷(date, equity, cash, invested_value, n_positions)
- Momentum_stock_list.json: 월 1회 상위시총 리스트만 저장(지표/MA 미포함)

4) 일간 리밸런싱 스케줄
- 설정: rebalance_period='daily', rebalance_after_time='14:50' (예시)
- 동작: 매일 실행하되, 지정 시각 조건 충족 시에만 매매
- 주말/휴장 보정: 주말에는 실행하지 않음

5) 크론탭 예시(서버 KST 기준, 주중 매일 14:55 실행)
  SHELL=/bin/bash
  PATH=/usr/local/bin:/usr/bin:/bin
  55 14 * * 1-5 /usr/bin/python3 /path/to/kook/kis/Momentum.py >> /path/to/kook/kis/logs/cron.log 2>&1

주의: 실제 주문은 ENABLE_ORDER_EXECUTION=True에서만 실행됩니다.

-------------------------------------------------------------------------------
[라이브/백테스트 정합성 및 구현 상세]

- 라이브 신호 계산 기준: 당일 데이터 기준(shift 제거)
  · 이동평균(5/20), 거래대금/거래량 MA(20/60), Average_Momentum 모두 당일 종가 기반으로 계산
  · RSI도 당일 값 사용(EOD 체결 가정)
  · crossing(static/crossing) 판정은 Average_Momentum_prev(전일값) 대비로 수행

- 시장 필터: KOSPI 200MA 상회 시 신규 매수 허용
  · 듀얼 MA(200/50) 필터는 라이브에서 활성화

- 후보 선정/랭킹: 유동성(거래대금) 필터 → Average_Momentum 임계 통과 후
  · 다중 팩터(percentile rank): ma_slope, price_ma, price_change, volume, rsi 가중합
  · 상위 N개(MAX_BUY_STOCKS) 선택

- 포지션 사이징/리밸런싱: 균등 분할 방식 목표 수량 산정 → 목표-현재 차이로 부분 매도/매수
  · 모멘텀 붕괴/고정비율 손절 우선 처리 후 리밸런싱 매도/매수 수행
  · 슬리피지: slippage_bps(bps)로 매수/매도 체결가에 대칭 적용

- 실행 주기: 일간 리밸런싱(daily)
  · 같은 주 중복 실행 방지용 플래그 파일: Momentum_weekly_done.flag
  · 주중 매일 실행

- 유니버스 소스: 네이버 시총 상위 스냅샷(JSON) 사용
  · 파일: Momentum_stock_list.json, 월 1회 갱신

- 관련 백테스트 파일(참고): kook/kis_wfo/turtle_strategy_backtester.py
  · 기본은 전일 기준(shift) 계산 설계. 라이브와 1:1 비교 시 백테스터도 당일 값 옵션화 필요

-------------------------------------------------------------------------------
"""

import os
import sys
import json
import time
import logging
import gc
import psutil
from datetime import datetime, timedelta
import pprint
import requests
import math

# 상위 디렉토리(kook)를 PYTHONPATH에 추가 후 공용 모듈 임포트
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

import KIS_Common as Common
import KIS_API_Helper_KR as KisKR
import telegram_sender as telegram
import pandas as pd
import numpy as np
import talib
from code_name_map import get_name, set_name


# 기존 템플릿에서 사용하는 보조 모듈들 재사용 (필요 시 함수화하여 연결)


# =============================================================================
# 기본/로그 설정
# =============================================================================
Common.SetChangeMode("REAL")

script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)

BOT_NAME = "Momentum"
PortfolioName = "[주식Top30]"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, f'{BOT_NAME}.log'), mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

ENABLE_ORDER_EXECUTION = True

# 파일 경로들
# 전략 전용 설정 파일
config_file_path = os.path.join(script_dir, 'Momentum_config.json')
positions_file_path = os.path.join(script_dir, f"{BOT_NAME}_positions.json")     # 전략별 레저(수량/평단/손익)
trades_csv_path = os.path.join(logs_dir, f"{BOT_NAME}_trades.csv")
daily_csv_path = os.path.join(logs_dir, f"{BOT_NAME}_daily.csv")


# =============================================================================
# 레저(전략별 보유) 유틸
# =============================================================================
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
        return {"positions": {}}
    try:
        with open(positions_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"레저 로딩 실패: {e}")
        return {"positions": {}}


def save_positions(ledger: dict):
    try:
        with open(positions_file_path, 'w', encoding='utf-8') as f:
            json.dump(ledger, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"레저 저장 실패: {e}")


def record_trade(date_str: str, action: str, stock_code: str, qty: int, price: float, pnl: float | None):
    import csv
    header = ["date", "action", "code", "qty", "price", "pnl"]
    write_header = not os.path.exists(trades_csv_path)
    try:
        with open(trades_csv_path, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(header)
            w.writerow([date_str, action, stock_code, qty, round(price, 4), (None if pnl is None else round(pnl, 2))])
    except Exception as e:
        logging.error(f"거래 로그 저장 실패: {e}")


def record_daily(date_str: str, equity: float, cash: float, invested_value: float, n_positions: int):
    import csv
    header = ["date", "equity", "cash", "invested_value", "n_positions"]
    write_header = not os.path.exists(daily_csv_path)
    try:
        with open(daily_csv_path, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(header)
            w.writerow([date_str, round(equity, 2), round(cash, 2), round(invested_value, 2), n_positions])
    except Exception as e:
        logging.error(f"일일 리포트 저장 실패: {e}")


# =============================================================================
# KIS 주문 응답 포맷팅 (텔레그램용)
# =============================================================================
def format_kis_order_message(portfolio_name: str, action_kor: str, stock_name: str, data, order_px: float | None = None) -> str:
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
            # 주문단가 추출(응답에 없으면 호출측 px 사용)
            ord_unpr = None
            if isinstance(out, dict):
                ord_unpr = out.get('ORD_UNPR') or out.get('ord_unpr') or out.get('ORD_PRIC') or out.get('order_price')
            if ord_unpr is None:
                ord_unpr = data.get('ORD_UNPR') or data.get('ord_unpr') or data.get('price')
            if ord_unpr is None and order_px is not None:
                ord_unpr = order_px
            status = '성공' if rt == '0' else '실패'
            return f"{portfolio_name} : {action_kor}{status} : {stock_name} : code={msg_cd} msg={msg1} price={ord_unpr}"
        # dict가 아니면 원본 출력
        return f"{portfolio_name} : {action_kor}주문 : {stock_name} : {data}"
    except Exception:
        return f"{portfolio_name} : {action_kor}주문 : {stock_name} : {data}"

# =============================================================================
# 레저 정리 유틸: 수량 0 종목 제거
# =============================================================================
def prune_zero_positions(ledger: dict) -> None:
    try:
        positions = ledger.get('positions', {})
        to_delete = [code for code, p in positions.items() if int(p.get('qty', 0)) <= 0]
        for code in to_delete:
            positions.pop(code, None)
        ledger['positions'] = positions
    except Exception as e:
        logging.warning(f"레저 정리 중 경고: {e}")


def check_and_cleanup_pending_positions(ledger: dict, current_date: str) -> None:
    """구매중 상태의 포지션을 체크하고 다음날 삭제합니다."""
    try:
        positions = ledger.get('positions', {})
        positions_to_remove = []
        
        for code, pos in positions.items():
            status = pos.get('status', '')
            buy_date = pos.get('buy_date', '')
            
            # 구매중 상태이고 구매일이 오늘이 아닌 경우 삭제
            if status == '구매중' and buy_date != current_date:
                positions_to_remove.append(code)
                logging.info(f"구매중 포지션 삭제: {code} {pos.get('name', '')} (구매일: {buy_date})")
        
        # 삭제할 포지션들을 제거
        for code in positions_to_remove:
            positions.pop(code, None)
            
        if positions_to_remove:
            ledger['positions'] = positions
            logging.info(f"총 {len(positions_to_remove)}개의 구매중 포지션을 삭제했습니다.")
            
    except Exception as e:
        logging.warning(f"구매중 포지션 정리 중 경고: {e}")


def update_pending_to_held_positions(ledger: dict) -> None:
    """구매중 상태의 포지션을 실제 보유 자산과 동기화하여 보유중으로 변경합니다."""
    try:
        # 실제 보유 자산 조회
        actual_holdings = KisKR.GetMyStockList()
        if not actual_holdings or not isinstance(actual_holdings, list):
            return
            
        positions = ledger.get('positions', {})
        actual_positions = {}
        
        # 실제 보유 종목 정보 추출
        for item in actual_holdings:
            code = item.get('StockCode', '')
            qty = int(item.get('StockAmt', 0))
            avg_price = float(item.get('StockAvgPrice', 0))
            
            if qty > 0 and code:
                actual_positions[code] = {
                    'qty': qty,
                    'avg': avg_price
                }
        
        # 구매중 상태인 포지션들을 실제 보유 자산과 비교
        for code, pos in positions.items():
            if pos.get('status') == '구매중' and code in actual_positions:
                # 실제로 보유 중이면 보유중으로 상태 변경
                actual_pos = actual_positions[code]
                pos['qty'] = actual_pos['qty']
                pos['avg'] = actual_pos['avg']
                pos['status'] = '보유중'
                pos['name'] = get_name(code)  # 종목명도 업데이트
                logging.info(f"구매중 → 보유중 변경: {code} {pos.get('name', '')} {actual_pos['qty']}주")
                
    except Exception as e:
        logging.warning(f"구매중 포지션 상태 업데이트 중 경고: {e}")


def sync_positions_with_actual_holdings(ledger: dict, cfg: dict = None) -> dict:
    """실제 보유 자산과 JSON 파일을 동기화합니다. (Momentum 전략 종목만 처리)"""
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
                    'avg': avg_price
                }
        
        # JSON 파일의 포지션과 비교 (Momentum 전략 종목만)
        json_positions = ledger.get('positions', {})
        sync_changes = []
        
        # 1. JSON에 있지만 실제로는 없는 종목 (이미 매도됨)
        codes_to_remove = []
        for code, pos in json_positions.items():
            if code not in actual_positions:
                qty = pos.get('qty', 0)
                avg_price = pos.get('avg', 0)
                status = pos.get('status', '보유중')
                sync_changes.append(f"이미 매도됨: {code} {get_name(code)} (JSON: {qty}주@{avg_price:,.0f}원, 상태: {status})")
                codes_to_remove.append(code)
        
        # 제거할 종목들을 JSON에서 제거
        for code in codes_to_remove:
            removed_pos = json_positions.pop(code, None)
            if removed_pos:
                # 매도 완료 시 realized_profit에 손익 반영 (선택적)
                if cfg is not None:
                    try:
                        current_price = float(KisKR.GetCurrentPrice(code))
                        avg_price = float(removed_pos.get('avg', 0))
                        qty = int(removed_pos.get('qty', 0))
                        if avg_price > 0 and qty > 0:
                            pnl = (current_price - avg_price) * qty
                            if abs(pnl) > 0.01:  # 1원 이상 차이만 반영
                                cfg['realized_profit'] = float(cfg.get('realized_profit', 0.0)) + pnl
                                logging.info(f"매도 완료 손익 반영: {code} {pnl:+,.0f}원")
                    except Exception as e:
                        logging.warning(f"매도 완료 손익 계산 실패 {code}: {e}")
        
        # 2. JSON에 있는 종목만 업데이트 (다른 전략 종목은 추가하지 않음)
        for code, pos in json_positions.items():
            if code in actual_positions:
                actual_pos = actual_positions[code]
                json_qty = pos.get('qty', 0)
                actual_qty = actual_pos['qty']
                json_avg = pos.get('avg', 0)
                actual_avg = actual_pos['avg']
                
                # 수량이 작아진 경우만 부분 매도로 간주하여 동기화
                if json_qty > actual_qty:
                    sync_changes.append(
                        f"부분 매도: {code} {get_name(code)} "
                        f"(JSON: {json_qty}주@{json_avg:,.0f}원 → "
                        f"실제: {actual_qty}주@{actual_avg:,.0f}원)"
                    )
                    # 실제 값으로 업데이트 (수량 감소)
                    json_positions[code]['qty'] = actual_qty
                    json_positions[code]['avg'] = actual_avg
                    json_positions[code]['name'] = get_name(code)
                    json_positions[code]['status'] = '보유중'
                # 수량이 같고 평단가만 다른 경우 (소수점 오차 등)
                elif json_qty == actual_qty and abs(json_avg - actual_avg) > 0.01:
                    sync_changes.append(
                        f"평단가 동기화: {code} {get_name(code)} "
                        f"(JSON: {json_avg:,.0f}원 → 실제: {actual_avg:,.0f}원)"
                    )
                    # 평단가만 업데이트
                    json_positions[code]['avg'] = actual_avg
                    json_positions[code]['name'] = get_name(code)
                    json_positions[code]['status'] = '보유중'
                # 수량이 커진 경우는 무시 (다른 전략이나 수동 매수)
                elif json_qty < actual_qty:
                    sync_changes.append(
                        f"수량 증가 무시: {code} {get_name(code)} "
                        f"(JSON: {json_qty}주 → 실제: {actual_qty}주, 다른 전략/수동매수로 추정)"
                    )
        
        # 변경사항이 있으면 로그 출력 및 저장
        if sync_changes:
            logging.info("[Momentum] 포지션 동기화 완료:")
            for change in sync_changes:
                logging.info(f"  - {change}")
            
            # JSON 파일 업데이트
            ledger['positions'] = json_positions
            save_positions(ledger)
            
            # 설정 파일도 업데이트 (realized_profit 변경사항 반영)
            if cfg is not None:
                try:
                    with open(config_file_path, 'w', encoding='utf-8') as f:
                        json.dump(cfg, f, ensure_ascii=False, indent=4)
                except Exception as e:
                    logging.warning(f"설정 파일 업데이트 실패: {e}")
        else:
            logging.info("[Momentum] 포지션 동기화: 변경사항 없음")
        
        return ledger
        
    except Exception as e:
        logging.error(f"포지션 동기화 실패: {e}")
        return ledger
# =============================================================================
# 요약 텔레그램 리포트
# =============================================================================
def _fmt_won(n: float, signed: bool = False) -> str:
    try:
        if signed:
            return f"{n:+,.0f}원"
        return f"{n:,.0f}원"
    except Exception:
        return str(n)


def send_summary_report(portfolio_name: str, ledger: dict, current_allocation: float, initial_allocation: float, name_map: dict[str, str], realized_profit: float = 0.0, total_asset_info: dict = None) -> None:
    try:
        positions = ledger.get('positions', {})
        lines = []
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # per-position
        win_cnt = 0
        lose_cnt = 0
        flat_cnt = 0
        invested_value_now = 0.0
        cost_basis = 0.0

        for code, pos in positions.items():
            qty = int(pos.get('qty', 0))
            if qty <= 0:
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
            # 종목명 표기: name_map → KIS 조회 → 코드 순서로 폴백
            try:
                display_name = name_map.get(code)
                if not display_name:
                    display_name = get_name(code)
                if not display_name:
                    display_name = code
            except Exception:
                display_name = name_map.get(code, code)
            lines.append(f"{icon} {display_name}({qty}주)\n   {_fmt_won(now_val)}({_fmt_won(pnl_abs, signed=True)}:{pnl_pct:+.2f}%)")

        # 현재 수익(미실현): 평가손익
        current_profit = invested_value_now - cost_basis
        current_profit_pct = (current_profit / cost_basis * 100.0) if cost_basis > 0 else 0.0
        realized = realized_profit

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
        
        # 전자산 정보 추가
        if total_asset_info:
            footer.extend([
                "==================================",
                f"🏦 자산 현황:",
                f"💰 초기전자산1: {_fmt_won(total_asset_info.get('initial_asset_1', 0))}",
                f"💰 초기전자산2: {_fmt_won(total_asset_info.get('initial_asset_2', 0))}",
                f"💰 현재 전자산: {_fmt_won(total_asset_info.get('current_total_asset', 0))}",
                f"📈 수익률계산1: {_fmt_won(total_asset_info.get('profit_1', 0), signed=True)} ({total_asset_info.get('return_1', 0):+.2f}%)",
                f"📈 수익률계산2: {_fmt_won(total_asset_info.get('profit_2', 0), signed=True)} ({total_asset_info.get('return_2', 0):+.2f}%)",
            ])
        msg = "\n".join(header + lines + footer)
        telegram.send(msg)
    except Exception as e:
        logging.warning(f"요약 리포트 전송 실패: {e}")


# =============================================================================
# 신규 추가: 전략 로직 (백테스터 기반)
# =============================================================================
def _get_ohlcv_pykrx(code: str, days: int = 400) -> pd.DataFrame | None:
    """pykrx를 사용하여 OHLVCV 데이터를 가져옵니다."""
    try:
        from pykrx import stock as pykrx_stock
        start = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        end = datetime.now().strftime('%Y%m%d')
        df = pykrx_stock.get_market_ohlcv_by_date(start, end, code)
        if df is None or df.empty:
            return None
        df.rename(columns={'시가': 'open', '고가': 'high', '저가': 'low', '종가': 'close', '거래량': 'volume'}, inplace=True)
        return df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    except Exception as e:
        logging.warning(f"pykrx OHLVCV 조회 실패 {code}: {e}")
        return None

def _calculate_indicators_for_stock(df: pd.DataFrame) -> pd.DataFrame:
    """라이브: 당일 데이터 기준으로 지표 계산(shift 제거), 종가 체결 가정"""
    if df is None or df.empty:
        return pd.DataFrame()

    # 전일 종가(변화율 계산용)
    df['prev_close'] = df['close'].shift(1)

    # 이동평균선(당일 값), 이전일 MA (기울기용)
    df['5ma'] = df['close'].rolling(window=5).mean()
    df['20ma'] = df['close'].rolling(window=20).mean()
    df['5ma_prev'] = df['5ma'].shift(1)
    df['20ma_prev'] = df['20ma'].shift(1)

    # 거래대금/거래량 이동평균(당일 값)
    df['volume_ma'] = (df['volume'] * df['close']).rolling(window=20).mean()
    df['volume_ma20'] = df['volume'].rolling(window=20).mean()
    df['volume_ma60'] = df['volume'].rolling(window=60).mean()

    # RSI (당일 값)
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)
    # ATR 제거 - 균등 분할 방식 사용

    # 평균 모멘텀(당일 종가 vs 과거 종가 비교), 전일 모멘텀 값
    momentum_periods = [i * 20 for i in range(1, 11)]  # 20..200
    for period in momentum_periods:
        df[f'Momentum_{period}'] = (df['close'] > df['close'].shift(1 + period)).astype(int)
    momentum_columns = [f'Momentum_{period}' for period in momentum_periods]
    df['Average_Momentum'] = df[momentum_columns].sum(axis=1) / len(momentum_periods)
    df['Average_Momentum_prev'] = df['Average_Momentum'].shift(1)

    return df.dropna()

def _get_kospi_index_ohlcv(days: int = 400) -> pd.DataFrame | None:
    """pykrx 지수 API로 KOSPI 지수 OHLCV를 조회합니다.
    - 우선 지수 티커 코드('1001' = KOSPI)를 사용하고, 실패 시 이름 기반 시도.
    """
    try:
        from pykrx import stock as pykrx_stock
        start = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        end = datetime.now().strftime('%Y%m%d')
        candidates = ["1001", "코스피", "KOSPI"]
        last_err = None
        for tk in candidates:
            try:
                df = pykrx_stock.get_index_ohlcv_by_date(start, end, tk)
                if df is None or df.empty:
                    continue
                # 컬럼 정규화: 일부 환경에서 열 이름이 다를 수 있으므로 안전 변환
                rename_map = {
                    '시가': 'open', '고가': 'high', '저가': 'low', '종가': 'close', '거래량': 'volume',
                    'OPNPRC_IDX': 'open', 'HGPRC_IDX': 'high', 'LWPRC_IDX': 'low', 'CLSPRC_IDX': 'close',
                    'ACC_TRDVOL': 'volume'
                }
                df = df.rename(columns=rename_map)
                # 필수 컬럼만 취득 가능하면 반환
                needed = [c for c in ['open','high','low','close','volume'] if c in df.columns]
                if len(needed) < 4 or 'close' not in needed:
                    continue
                return df[needed].astype(float)
            except Exception as _e:
                last_err = _e
                continue
        if last_err:
            raise last_err
        return None
    except Exception as e:
        logging.warning(f"KOSPI 지수 조회 실패(pykrx index): {e}")
        return None


def _get_kospi_market_regime(use_dual_ma_filter: bool = False) -> bool:
    """KOSPI 지수가 200일 이평선 위에 있는지 확인합니다."""
    kospi_df = _get_kospi_index_ohlcv()
    if kospi_df is None or len(kospi_df) < 200:
        logging.warning("KOSPI 지수 데이터 부족으로 시장 필터 OFF")
        return True  # 데이터 없으면 보수적으로 ON

    kospi_df['200ma'] = kospi_df['close'].rolling(window=200).mean()
    last_close = float(kospi_df['close'].iloc[-1])
    last_200ma = float(kospi_df['200ma'].iloc[-1])

    is_bull = last_close > last_200ma
    
    # 듀얼 MA 필터 적용
    if use_dual_ma_filter:
        kospi_df['50ma'] = kospi_df['close'].rolling(window=50).mean()
        last_50ma = float(kospi_df['50ma'].iloc[-1])
        is_bull = is_bull and (last_close > last_50ma)
        logging.info(f"듀얼 MA 필터: KOSPI 현재({last_close:,.2f}) > 200MA({last_200ma:,.2f}) & 50MA({last_50ma:,.2f}) -> {'상승장' if is_bull else '하락장'}")
    else:
        logging.info(f"시장 필터: KOSPI 현재({last_close:,.2f}) > 200MA({last_200ma:,.2f}) -> {'상승장' if is_bull else '하락장'}")
    
    return is_bull

# =============================================================================
# 월 1회 스톡리스트 업데이트 (MA 미저장, 리스트만 저장) - 로컬 구현
# =============================================================================
def _get_top_market_cap_stocks_local(count: int = 100) -> dict:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0 Safari/537.36'
    }
    result = {'kospi': [], 'kosdaq': []}
    try:
        kospi_url = f"https://m.stock.naver.com/api/stocks/marketValue/KOSPI?page=1&pageSize={count}"
        r1 = requests.get(kospi_url, headers=headers, timeout=10)
        r1.raise_for_status()
        for s in r1.json().get('stocks', []) or []:
            code = s.get('itemCode')
            name = s.get('stockName')
            if code:
                result['kospi'].append({'stock_code': code, 'stock_name': name, 'market_value': s.get('marketValue', '0')})
    except Exception as e:
        logging.warning(f"KOSPI 상위 시총 조회 실패: {e}")
    try:
        kosdaq_url = f"https://m.stock.naver.com/api/stocks/marketValue/KOSDAQ?page=1&pageSize={count}"
        r2 = requests.get(kosdaq_url, headers=headers, timeout=10)
        r2.raise_for_status()
        for s in r2.json().get('stocks', []) or []:
            code = s.get('itemCode')
            name = s.get('stockName')
            if code:
                result['kosdaq'].append({'stock_code': code, 'stock_name': name, 'market_value': s.get('marketValue', '0')})
    except Exception as e:
        logging.warning(f"KOSDAQ 상위 시총 조회 실패: {e}")
    return result


def monthly_update_stock_list_if_due(cfg: dict) -> None:
    try:
        update_day = int(cfg.get('monthly_update_day', 1))
    except Exception:
        update_day = 1

    today = datetime.now()
    if today.day != update_day:
        return

    try:
        caps = _get_top_market_cap_stocks_local(count=100)
        out = {
            "last_updated": today.strftime("%Y-%m-%d %H:%M:%S"),
            "kospi": caps.get('kospi', []),
            "kosdaq": caps.get('kosdaq', []),
        }
        target_path = os.path.join(script_dir, 'Momentum_stock_list.json')
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        logging.info(f"월간 스톡리스트 업데이트 완료: {target_path} (KOSPI {len(out['kospi'])}, KOSDAQ {len(out['kosdaq'])})")
        try:
            telegram.send(f"{PortfolioName}\n월간 스톡리스트 업데이트 완료\nKOSPI {len(out['kospi'])}, KOSDAQ {len(out['kosdaq'])}")
        except Exception:
            pass
    except Exception as e:
        logging.error(f"월간 스톡리스트 업데이트 실패: {e}")


def ensure_stock_list_exists(min_count_per_market: int = 50) -> None:
    """스톡리스트 파일이 없거나 비어 있으면 즉시 생성합니다."""
    try:
        target_path = os.path.join(script_dir, 'Momentum_stock_list.json')
        need_generate = False
        js = None
        if not os.path.exists(target_path):
            need_generate = True
        else:
            try:
                with open(target_path, 'r', encoding='utf-8') as f:
                    js = json.load(f)
                kc = len(js.get('kospi', []) or [])
                kd = len(js.get('kosdaq', []) or [])
                if kc < min_count_per_market or kd < min_count_per_market:
                    need_generate = True
            except Exception:
                need_generate = True
        if need_generate:
            caps = _get_top_market_cap_stocks_local(count=100)
            out = {
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "kospi": caps.get('kospi', []),
                "kosdaq": caps.get('kosdaq', []),
            }
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            logging.info(f"스톡리스트 즉시 생성 완료: {target_path} (KOSPI {len(out['kospi'])}, KOSDAQ {len(out['kosdaq'])})")
    except Exception as e:
        logging.warning(f"스톡리스트 즉시 생성 실패: {e}")

def initialize_and_check_conditions():
    """프로그램 실행 전 초기화 및 조건 체크"""
    # 잔고 조회 하면서 토큰 발급
    balance = KisKR.GetBalance()
    
    # 실행 가드(주말/장상태)
    now = datetime.now()
    if now.weekday() >= 5:
        msg = f"{PortfolioName}({now.strftime('%Y-%m-%d')})\n주말(토/일)에는 실행하지 않습니다."
        logging.info(msg)
        sys.exit(0)

    is_market_open = KisKR.IsMarketOpen()
    current_date = time.strftime("%Y-%m-%d")
    if not is_market_open:
        logging.info(f"날짜 {current_date} : 장이 닫혀있습니다.")
        telegram.send(f"{PortfolioName}({current_date})\n장이 닫혀있습니다.")
        sys.exit(0)
    else:
        logging.info(f"날짜 {current_date} : 장이 열려있습니다.")
        #telegram.send(f"{PortfolioName}({current_date})\n장이 열려있습니다.")
    
    return balance, current_date, is_market_open


def main():
    global IsMarketOpen
    
    # 0) 초기화 및 조건 체크
    Balance, current_date, IsMarketOpen = initialize_and_check_conditions()

    # 전략 전용 설정 로딩
    try:
        with open(config_file_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {
            "allocation_rate": 0.60, 
            "max_buy_stocks": 15,  # 베스트: 15개
            "exclude_stock_codes": [],
            "momentum_threshold": 0.65,  # 베스트: 0.65
            "momentum_sl_threshold": 0.5,  # 베스트: 0.5
            "min_volume_threshold": 500_000_000,
            "use_dual_ma_filter": False,  # 베스트: False
            "rebalance_period": "daily",  # 베스트: daily
            "use_trailing_stop": False,
            "use_pyramiding": False,  # 베스트: False
            "max_units_per_position": 4,  # 베스트: 4
            "score_weights": {'ma_slope': 0.3, 'price_ma': 0.2, 'price_change': 0.2, 'volume': 0.15, 'rsi': 0.15},  # 베스트: score_weights_set 0
            "slippage_bps": 0.0,
            "test_type": "crossing",  # 베스트: crossing
            "use_market_filter": True,  # 베스트: True
            "initial_portfolio_mode": False,  # 초기 포트폴리오 구성 모드
            "initial_threshold_reduction": 0.1  # 초기 구성 시 임계값 감소폭
        }
        logging.warning(f"설정 파일이 없어 기본값으로 실행합니다: {config_file_path}")
    except Exception as e:
        logging.error(f"{config_file_path} 로딩 실패: {e}")
        telegram.send(f"{PortfolioName} 설정 로딩 실패. 프로그램 종료")
        sys.exit(1)

    # 월 1회: 코스피100/코스닥100 리스트만 stock_list.json에 갱신 (MA 값 저장 없음)
    monthly_update_stock_list_if_due(cfg)

    # 투자 비중: 매일 총자산의 40% 동적 배분 (전략 전용 설정 기반)
    total_equity = float(Balance['TotalMoney'])
    InvestRate = float(cfg.get('allocation_rate', 0.40))
    TotalMoney = total_equity * InvestRate
    logging.info(f"총 평가금액: {total_equity:,.0f}원, 전략1 할당: {TotalMoney:,.0f}원 ({InvestRate*100:.0f}%)")

    # 초기 분배금: 설정 파일에서 관리
    ledger = load_positions()
    initial_allocation = float(cfg.get('initial_allocation', 0.0))
    
    # 최초 실행 시 초기 분배금 설정
    if initial_allocation == 0.0:
        cfg['initial_allocation'] = TotalMoney
        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)
        initial_allocation = TotalMoney
        logging.info(f"초기 분배금 설정: {initial_allocation:,.0f}원")
    
    # 초기전자산1: 실제 투입금액 설정 (최초 실행 시, 현재 자산으로 설정)
    initial_asset_1 = float(cfg.get('initial_asset_1', 0.0))
    if initial_asset_1 == 0.0:
        # 실제 투입금액을 현재 자산으로 설정
        initial_asset_1 = total_equity
        cfg['initial_asset_1'] = initial_asset_1
        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)
        logging.info(f"초기전자산1 설정: {initial_asset_1:,.0f}원")
    
    # 초기전자산2: 현재 자산 기준 설정 (최초 실행 시, 현재 자산으로 설정)
    initial_asset_2 = float(cfg.get('initial_asset_2', 0.0))
    if initial_asset_2 == 0.0:
        # 현재 자산을 현재 자산으로 설정
        initial_asset_2 = total_equity
        cfg['initial_asset_2'] = initial_asset_2
        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)
        logging.info(f"초기전자산2 설정: {initial_asset_2:,.0f}원")
    
    # 현재 전자산 업데이트
    cfg['current_total_asset'] = total_equity
    with open(config_file_path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)
    
    # 수익률계산1: 초기전자산1(실제 투입금액) 대비 수익률
    return_1 = ((total_equity - initial_asset_1) / initial_asset_1 * 100) if initial_asset_1 > 0 else 0.0
    profit_1 = total_equity - initial_asset_1
    
    # 수익률계산2: 초기전자산2(현재 자산 기준) 대비 수익률
    return_2 = ((total_equity - initial_asset_2) / initial_asset_2 * 100) if initial_asset_2 > 0 else 0.0
    profit_2 = total_equity - initial_asset_2
    
    logging.info(f"자산 현황:")
    logging.info(f"  초기전자산1: {initial_asset_1:,.0f}원 → 현재: {total_equity:,.0f}원 (수익률: {return_1:+.2f}%, 수익금: {profit_1:+,.0f}원)")
    logging.info(f"  초기전자산2: {initial_asset_2:,.0f}원 → 현재: {total_equity:,.0f}원 (수익률: {return_2:+.2f}%, 수익금: {profit_2:+,.0f}원)")
    
    # 구매중 포지션 상태 업데이트 (구매중 → 보유중)
    update_pending_to_held_positions(ledger)
    
    # 상태 변경사항을 JSON 파일에 즉시 저장
    save_positions(ledger)
    
    # 구매중 포지션 정리 (다음날 삭제)
    check_and_cleanup_pending_positions(ledger, current_date)
    
    # 실제 보유 자산과 JSON 파일 동기화
    ledger = sync_positions_with_actual_holdings(ledger, cfg)

    # 제외 종목 (전략 전용 설정)
    exclude_stock_codes = list(cfg.get('exclude_stock_codes', []))

    # 주간 리밸런싱 조건 체크
    rebalance_period = str(cfg.get('rebalance_period', 'weekly')).lower()
    rebalance_day = str(cfg.get('rebalance_day', 'MON')).upper()  # MON/TUE/WED/THU/FRI
    rebalance_after_time = str(cfg.get('rebalance_after_time', '10:50'))  # HH:MM (KST)

    # 오늘 요일/시간
    weekday_map = {0: 'MON', 1: 'TUE', 2: 'WED', 3: 'THU', 4: 'FRI', 5: 'SAT', 6: 'SUN'}
    today_wd = weekday_map.get(datetime.now().weekday())
    now_hm = time.strftime('%H:%M')

    # 이번 주 실행 여부 파일(간단 플래그)
    weekly_flag_path = os.path.join(script_dir, f'{BOT_NAME}_weekly_done.flag')
    week_id = datetime.now().strftime('%G-%V')  # ISO 연-주차
    need_rebalance_today = False

    if rebalance_period == 'weekly':
        # 월요일 휴장 보정: 지정 요일에 장이 닫혀 있으면 다음 거래일로 이월
        if today_wd in ['SAT', 'SUN']:
            logging.info('주말은 리밸런싱을 시도하지 않습니다.')
            return
        # 지정 요일이 아니면: 월요일이 쉬었고 화요일인 경우에도 IsMarketOpen을 본 시점에만 허용
        target_wd = rebalance_day
        # 플래그 파일에 기록된 주차와 비교
        last_done_week = None
        if os.path.exists(weekly_flag_path):
            try:
                with open(weekly_flag_path, 'r', encoding='utf-8') as f:
                    last_done_week = f.read().strip()
            except Exception:
                last_done_week = None

        # 아직 이번 주 미실행
        if last_done_week != week_id:
            # 기본: 지정 요일 && 지정 시각 이후 && 장 열림
            base_ok = (today_wd == target_wd and now_hm >= rebalance_after_time and KisKR.IsMarketOpen())
            # 대체: 지정 요일에 휴장 → 다음 거래일(장 열림 && 지정 시각 이후)
            alt_ok = (today_wd != target_wd and now_hm >= rebalance_after_time and KisKR.IsMarketOpen())
            need_rebalance_today = base_ok or alt_ok
    elif rebalance_period == 'daily':
        # 일간 리밸런싱: 주중 매일 실행
        if today_wd in ['SAT', 'SUN']:
            logging.info('주말은 리밸런싱을 시도하지 않습니다.')
            return
        # 주중이면 지정 시각 이후에 실행
        need_rebalance_today = (now_hm >= rebalance_after_time and KisKR.IsMarketOpen())

        if not need_rebalance_today:
            logging.info('주간 조건 미충족으로 오늘은 리밸런싱을 실행하지 않습니다.')
            # 항상 일일 스냅샷/요약 전송
            try:
                # 현재 보유 평가
                invested_value = 0.0
                for code, pos in ledger.get('positions', {}).items():
                    qty = int(pos.get('qty', 0))
                    if qty > 0:
                        invested_value += qty * float(KisKR.GetCurrentPrice(code))
                strategy_cash = max(0.0, TotalMoney - invested_value)
                record_daily(current_date, strategy_cash + invested_value, strategy_cash, invested_value,
                             sum(1 for p in ledger.get('positions', {}).values() if int(p.get('qty', 0)) > 0))
                # 전자산 정보 구성
                total_asset_info = {
                    'initial_asset_1': initial_asset_1,
                    'initial_asset_2': initial_asset_2,
                    'current_total_asset': total_equity,
                    'profit_1': profit_1,
                    'return_1': return_1,
                    'profit_2': profit_2,
                    'return_2': return_2
                }
                
                send_summary_report(
                    PortfolioName,
                    ledger,
                    current_allocation=TotalMoney,
                    initial_allocation=float(ledger.get('initial_allocation') or TotalMoney),
                    name_map={},
                    total_asset_info=total_asset_info
                )
                
                # current_allocation 값을 설정 파일에 저장
                try:
                    cfg['current_allocation'] = TotalMoney
                    with open(config_file_path, 'w', encoding='utf-8') as f:
                        json.dump(cfg, f, ensure_ascii=False, indent=4)
                except Exception as e:
                    logging.warning(f"current_allocation 저장 실패: {e}")
            except Exception:
                pass
            return

    # 유니버스/지표/신호 계산: 기존 템플릿 파일 구조를 따르므로 동일 변수명 사용
    # 템플릿 코드가 매우 길어 재사용: import 없이 로직을 간소화할 수 없으므로,
    # 본 파일에서는 핵심—보유수량 레저와 자산배분/체결/리포트—만 오버라이드한다는 전제로,
    # 템플릿과 동일한 함수/변수명을 가정한다.
    #
    # 실제 구현에서는 템플릿의 주요 블록을 함수화하여 공용모듈로 빼는 것이 바람직.

    # 템플릿의 MyPortfolioList, MyStockList 등은
    # 여기서 재사용하기 어렵기 때문에 핵심 리밸런싱/주문 직전 단계에서 레저 기반으로 계산을 대체한다.

    # 간소화: 템플릿의 신호 산출을 그대로 활용하기 위해, 기존 파일을 실행 흐름 상 호출하는 것은
    # 구조적으로 복잡하므로, 본 전략은 템플릿 로직과 동일 파일 구조를 가정한 최소 침습 편집을 권장.
    #
    # 따라서, 전략1은 우선 레저/배분/주문/리포팅 골격만 제공하고

    # 방어: 필요 변수 기본값
    MyPortfolioList = []            # 각 종목: {'stock_code','stock_name','stock_target_rate','status','stock_rebalance_amt'}
    MAX_BUY_STOCKS = int(cfg.get('max_buy_stocks', 30))

    def _load_universe_from_json() -> list[dict]:
        path = os.path.join(script_dir, 'Momentum_stock_list.json')
        try:
            if not os.path.exists(path):
                ensure_stock_list_exists()
            else:
                # 존재하지만 비거나 부족하면 보강
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        js_probe = json.load(f)
                    kc = len(js_probe.get('kospi', []) or [])
                    kd = len(js_probe.get('kosdaq', []) or [])
                    if kc < 50 or kd < 50:
                        ensure_stock_list_exists()
                except Exception:
                    ensure_stock_list_exists()
            with open(path, 'r', encoding='utf-8') as f:
                js = json.load(f)
            arr = []
            for mkt in ['kospi', 'kosdaq']:
                for it in js.get(mkt, []) or []:
                    code = it.get('stock_code') or it.get('code')
                    name = it.get('stock_name') or it.get('name') or code
                    if code:
                        arr.append({'code': code, 'name': name})
            return arr
        except Exception as e:
            logging.warning(f"유니버스 로드 실패: {e}")
            return []

    def _compute_target_list_v2(cfg: dict) -> list[dict]:
        """백테스터 기반의 다중 팩터 랭킹 로직(static / crossing 선택)"""
        universe = _load_universe_from_json()
        if not universe:
            return []
        
        ex = set(exclude_stock_codes)
        cand = [u for u in universe if u['code'] not in ex]
        
        scored_candidates = []
        for u in cand:
            df_full = _get_ohlcv_pykrx(u['code'])
            if df_full is None or df_full.empty:
                continue
            
            df_indicators = _calculate_indicators_for_stock(df_full)
            if df_indicators.empty:
                continue
            
            last = df_indicators.iloc[-1]
            prev = df_indicators.iloc[-2] if len(df_indicators) > 1 else last
            
            # 1차 필터: 거래대금 및 모멘텀 점수
            if last.get('volume_ma', 0) < cfg.get('min_volume_threshold', 5e8):
                continue

            test_type = str(cfg.get('test_type', 'crossing')).lower()  # 'static' or 'crossing'
            momentum_threshold = cfg.get('momentum_threshold', 0.75)
            am = float(last.get('Average_Momentum', 0))
            am_prev = float(last.get('Average_Momentum_prev', am))
            pass_momentum = False
            if test_type == 'static':
                pass_momentum = am >= momentum_threshold
            else:  # crossing
                pass_momentum = (am_prev < momentum_threshold) and (am >= momentum_threshold)
            if not pass_momentum:
                try:
                    logging.debug(
                        f"[Momentum] 제외: {u['code']} {u['name']} AM={am:.3f}, AM_prev={am_prev:.3f}, "
                        f"thr={momentum_threshold:.2f}, type={test_type}, vol_ma={last.get('volume_ma', 0):,.0f}"
                    )
                except Exception:
                    pass
                continue
            
            # 팩터 값 추출(당일 값 기준)
            ma5 = last.get('5ma', 0)
            ma20 = last.get('20ma', 0)
            ma5_prev = last.get('5ma_prev', ma5)
            ma20_prev = last.get('20ma_prev', ma20)
            close_now = last.get('close', 0)
            prev_close = df_indicators['close'].iloc[-2] if len(df_indicators) > 1 else close_now

            ma_slope = ((ma5 - ma5_prev) * 0.7 + (ma20 - ma20_prev) * 0.3)
            price_ma_ratio = (close_now / ma20 - 1) if ma20 > 0 else 0
            price_change = (close_now / prev_close - 1) if prev_close > 0 else 0
            volume_ratio = (last.get('volume_ma20', 0) / last.get('volume_ma60', 1)) if last.get('volume_ma60', 0) else 1.0
            
            scored_candidates.append({
                'code': u['code'], 'name': u['name'],
                'ma_slope': ma_slope, 'price_ma': price_ma_ratio, 'price_change': price_change,
                'volume': volume_ratio, 'rsi': last.get('rsi', 50)
            })

        if not scored_candidates:
            return []

        # 팩터별 순위(Percentile Rank) 계산 후 가중 합산
        scores_df = pd.DataFrame(scored_candidates)
        weights = cfg.get('score_weights', {})
        
        final_scores = pd.Series(0.0, index=scores_df.index)
        for factor, weight in weights.items():
            if factor in scores_df.columns:
                final_scores += scores_df[factor].rank(pct=True) * weight
        
        scores_df['final_score'] = final_scores
        scores_df.sort_values(by='final_score', ascending=False, inplace=True)
        try:
            top_preview = scores_df.head(min(10, len(scores_df)))[['code', 'name', 'final_score']]
            logging.info(f"[Momentum] 후보 상위 미리보기:\n{top_preview.to_string(index=False)}")
        except Exception:
            pass
        
        return scores_df.to_dict('records')

    # 리밸런싱일에만 신호 산출
    buy_targets = []
    if need_rebalance_today:
        # 현재 보유 종목 수 확인
        positions = ledger.get('positions', {})
        current_holdings_count = sum(1 for p in positions.values() if int(p.get('qty', 0)) > 0)
        
        # 초기 포트폴리오 구성: 보유 종목이 거의 없을 때는 시장 필터 우회
        initial_mode = cfg.get('initial_portfolio_mode', True)
        threshold_reduction = cfg.get('initial_threshold_reduction', 0.1)
        
        if current_holdings_count < MAX_BUY_STOCKS * 0.3 and initial_mode:  # 30% 미만 보유 시
            logging.info(f"초기 포트폴리오 구성 모드: 현재 보유 {current_holdings_count}개, 목표 {MAX_BUY_STOCKS}개")
            # 초기 구성 시에는 모멘텀 임계값을 낮춰서 더 많은 종목 선택
            temp_cfg = cfg.copy()
            temp_cfg['momentum_threshold'] = max(0.5, cfg.get('momentum_threshold', 0.65) - threshold_reduction)
            buy_targets = _compute_target_list_v2(temp_cfg)[:MAX_BUY_STOCKS]
            logging.info(f"초기 구성용 낮춘 임계값: {temp_cfg['momentum_threshold']:.2f} (원래: {cfg.get('momentum_threshold', 0.65):.2f})")
            
            # 초기 구성 완료 후 플래그 비활성화
            if len(buy_targets) >= MAX_BUY_STOCKS * 0.8:  # 80% 이상 채워지면
                cfg['initial_portfolio_mode'] = False
                with open(config_file_path, 'w', encoding='utf-8') as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=4)
                logging.info("초기 포트폴리오 구성 완료, 일반 모드로 전환")
        else:
            # 정상 리밸런싱: 시장 필터 적용
            is_bull_market = _get_kospi_market_regime(cfg.get('use_dual_ma_filter', False))
            if not is_bull_market:
                logging.info("하락장 필터 활성화, 신규 매수를 진행하지 않습니다.")
                # 하락장에서는 보유 종목 전량 매도 (선택적)
                # 여기서는 신규 매수만 중단하는 것으로 구현
            else:
                buy_targets = _compute_target_list_v2(cfg)[:MAX_BUY_STOCKS]

        target_codes = {t['code'] for t in buy_targets}
        positions = ledger.get('positions', {})
        held_codes = {c for c, p in positions.items() if int(p.get('qty', 0)) > 0}

        # 매도 대상: (보유 중 && 목표에 없음) OR (모멘텀/ATR 손절)
        sell_targets = []
        


    # --------------------------- 레저/체결/리포트 블록 ---------------------------
    # 위에서 로드/초기화된 ledger 재사용

    # 현재가/전략 보유 평가
    invested_value = 0.0
    for stock_info in MyPortfolioList:
        code = stock_info['stock_code']
        qty = int(ledger.get('positions', {}).get(code, {}).get('qty', 0))
        if qty > 0:
            px = KisKR.GetCurrentPrice(code)
            invested_value += qty * px

    # 설정 파일 업데이트 (필요시)

    strategy_cash = max(0.0, TotalMoney - invested_value)
    record_daily(current_date, strategy_cash + invested_value, strategy_cash, invested_value, 
                 sum(1 for p in ledger.get('positions', {}).values() if int(p.get('qty', 0)) > 0))

    if not ENABLE_ORDER_EXECUTION:
        logging.info("매매 실행이 비활성화되어 있습니다.")
        return

    if not IsMarketOpen:
        logging.info("장이 열려있지 않습니다.")
        return

    # === 리밸런싱 실행 (목표 수량 기반 부분 매도/매수, crossing 지원) ===
    if need_rebalance_today:
        # 1) 시장 필터
        is_bull_market = _get_kospi_market_regime(cfg.get('use_dual_ma_filter', False))
        if not is_bull_market:
            logging.info("하락장 필터 활성화, 신규 매수 없음")
            buy_targets = []
        else:
            buy_targets = _compute_target_list_v2(cfg)[:MAX_BUY_STOCKS]
        # 2) 목표 수량 산정(균등 분할 방식)
        target_qty_map: dict[str, int] = {}
        for t in buy_targets:
            code = t['code']
            current_price = float(KisKR.GetCurrentPrice(code))
            if current_price > 0:
                # 균등 분할: 총자본을 최대 보유 종목수로 나눈 금액으로 매수
                position_size_money = TotalMoney / MAX_BUY_STOCKS
                qty = int(position_size_money / current_price)
                if qty > 0:
                    target_qty_map[code] = qty

        # 3) 현재 보유와 비교하여 매도/매수 수량 계산
        positions = ledger.get('positions', {})
        held_codes = {c for c, p in positions.items() if int(p.get('qty', 0)) > 0}
        current_holdings_count = len(held_codes)

        # 슬리피지 설정(bps)
        slippage_bps = float(cfg.get('slippage_bps', 0.0))
        def sell_px(px: float) -> float:
            return px * (1 - (slippage_bps / 10000.0)) if slippage_bps != 0 else px
        def buy_px(px: float) -> float:
            return px * (1 + (slippage_bps / 10000.0)) if slippage_bps != 0 else px

        # 3-1) 매도(비중 축소/전량 청산)
        sell_count = 0
        for code in list(held_codes):
            pos_info = positions.get(code, {})
            cur_qty = int(pos_info.get('qty', 0))
            # 손절/모멘텀 붕괴 우선
            df_full = _get_ohlcv_pykrx(code)
            if df_full is not None and not df_full.empty:
                df_ind = _calculate_indicators_for_stock(df_full)
                if not df_ind.empty:
                    last = df_ind.iloc[-1]
                    # 손절 조건만 체크 (리밸런싱 매도는 하지 않음)
                    tgt_qty = cur_qty  # 기본적으로 현재 수량 유지
                    
                    # 모멘텀 붕괴 손절
                    if last.get('Average_Momentum', 1.0) < cfg.get('momentum_sl_threshold', 0.5):
                        tgt_qty = 0
                        logging.info(f"[Momentum] 모멘텀 붕괴 손절: {code} {get_name(code)} AM={last.get('Average_Momentum', 0):.3f}")
                    
                    # 고정 비율 손절 (10% 하락 시 손절)
                    if tgt_qty > 0:
                        avg_price = float(pos_info.get('avg', 0) or 0)
                        if avg_price > 0:
                            stop_price = avg_price * 0.9  # 10% 하락 시 손절
                            if last.get('low', float('inf')) <= stop_price:
                                tgt_qty = 0
                                logging.info(f"[Momentum] 고정비율 손절: {code} {get_name(code)} 현재가={last.get('low', 0):,.0f} <= 손절가={stop_price:,.0f}")
                else:
                    tgt_qty = cur_qty  # 데이터 없으면 현재 수량 유지
            else:
                tgt_qty = cur_qty  # 데이터 없으면 현재 수량 유지

            diff = cur_qty - tgt_qty
            if diff > 0:
                # 시장가 매도 전환
                try:
                    data = KisKR.MakeSellMarketOrder(code, diff)
                    px = float(KisKR.GetCurrentPrice(code))  # 근사 체결가로 현재가 사용
                except Exception:
                    data = None
                    px = float(KisKR.GetCurrentPrice(code))
                avg = float(pos_info.get('avg', 0.0))
                pnl = (px - avg) * diff
                # 레저 업데이트(부분 매도)
                positions[code]['qty'] = cur_qty - diff
                if positions[code]['qty'] <= 0:
                    positions.pop(code, None)
                # realized_profit을 설정 파일에서 관리
                cfg['realized_profit'] = float(cfg.get('realized_profit', 0.0)) + pnl
                with open(config_file_path, 'w', encoding='utf-8') as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=4)
                
                # 매도 로그 및 동그라미 표시
                stock_name = get_name(code)
                icon = '🟢' if pnl > 0 else ('🔴' if pnl < 0 else '⚪')
                logging.info(f"{icon} [매도] {stock_name}({code}) {diff}주 @ {px:,.0f}원 (손익: {pnl:+,.0f}원)")
                record_trade(current_date, 'SELL', code, diff, px, pnl)

        # 4) 빈 슬롯 계산
        available_slots = MAX_BUY_STOCKS - current_holdings_count
        
        logging.info(f"[Momentum] 현재 보유: {current_holdings_count}개, 빈 슬롯: {available_slots}개")

        # 5) 매도 실행 (조건부 매도만)
        sell_count = 0
        for code in held_codes:
            pos_info = positions.get(code, {})
            cur_qty = int(pos_info.get('qty', 0))
            if cur_qty <= 0:
                continue
                
            df_full = _get_ohlcv_pykrx(code)
            if df_full is None: continue
            df_indicators = _calculate_indicators_for_stock(df_full)
            if df_indicators.empty: continue
            
            last = df_indicators.iloc[-1]
            sell_reason = None
            
            # 모멘텀 붕괴 체크
            if last.get('Average_Momentum', 1.0) < cfg.get('momentum_sl_threshold', 0.5):
                sell_reason = "모멘텀 붕괴"
            
            # 고정 비율 손절 체크 (10% 하락 시 손절)
            if not sell_reason:
                avg_price = float(pos_info.get('avg', 0) or 0)
                if avg_price > 0:
                    stop_price = avg_price * 0.9  # 10% 하락 시 손절
                    if last.get('low', float('inf')) <= stop_price:
                        sell_reason = "고정비율 손절"
            
            if sell_reason:
                # 시장가 매도
                try:
                    data = KisKR.MakeSellMarketOrder(code, cur_qty)
                    px = float(KisKR.GetCurrentPrice(code))
                except Exception:
                    data = None
                    px = float(KisKR.GetCurrentPrice(code))
                
                avg = float(pos_info.get('avg', 0.0))
                pnl = (px - avg) * cur_qty
                
                # 레저 업데이트
                positions[code]['qty'] = 0
                if positions[code]['qty'] <= 0:
                    positions.pop(code, None)
                # realized_profit을 설정 파일에서 관리
                cfg['realized_profit'] = float(cfg.get('realized_profit', 0.0)) + pnl
                with open(config_file_path, 'w', encoding='utf-8') as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=4)
                
                # 매도 로그 및 동그라미 표시
                stock_name = get_name(code)
                icon = '🟢' if pnl > 0 else ('🔴' if pnl < 0 else '⚪')
                logging.info(f"{icon} [매도] {stock_name}({code}) {cur_qty}주 @ {px:,.0f}원 (손익: {pnl:+,.0f}원)")
                record_trade(current_date, 'SELL', code, cur_qty, px, pnl)
                
                try:
                    msg = format_kis_order_message(PortfolioName, '매도', stock_name, data, order_px=px)
                    # 매도 사유 구성
                    reason = []
                    
                    #if int(target_qty_map.get(code, 0)) == 0:
                    #    reason.append('리밸런싱 제외')
                    
                    # 손절/모멘텀 붕괴 여부는 직전 판정 기반
                    try:
                        df_full2 = _get_ohlcv_pykrx(code)
                        if df_full2 is not None and not df_full2.empty:
                            df_ind2 = _calculate_indicators_for_stock(df_full2)
                            if not df_ind2.empty:
                                last2 = df_ind2.iloc[-1]
                                if last2.get('Average_Momentum', 1.0) < cfg.get('momentum_sl_threshold', 0.5):
                                    reason.append('모멘텀 붕괴')
                    except Exception:
                        pass
                    reason_text = ' / '.join(reason) if reason else '리밸런싱 비중 축소'
                    # 수익금/수익률 계산
                    avg_price = float(positions.get(code, {}).get('avg', 0.0))
                    pnl_pct = (px / avg_price - 1) * 100 if avg_price > 0 else 0
                    telegram.send(f"{icon} {msg}\n이유: {reason_text}\n수익: {pnl:,.0f}원 ({pnl_pct:+.2f}%)")
                except Exception:
                    pass
                sell_count += 1

        if sell_count > 0:
            save_positions(ledger)
            time.sleep(1.0)

        # 3-2) 매수(비중 확대/신규 진입)
        ledger = load_positions()
        positions = ledger.get('positions', {})
        # 현재 투자금 계산
        invested_value = 0.0
        for code, pos in positions.items():
            qty_i = int(pos.get('qty', 0))
            if qty_i > 0:
                invested_value += qty_i * float(KisKR.GetCurrentPrice(code))
        budget_left = max(0.0, TotalMoney - invested_value)

        buy_count = 0
        for code, tgt_qty in target_qty_map.items():
            cur_qty = int(positions.get(code, {}).get('qty', 0))
            diff = tgt_qty - cur_qty
            if diff <= 0:
                continue
            px_now = float(KisKR.GetCurrentPrice(code))
            px = buy_px(px_now)
            need = diff * px
            if need > budget_left:
                continue
            data = KisKR.MakeBuyLimitOrder(code, diff, px)
            # 레저 업데이트(평단 갱신, 고정 비율 손절가 설정)
            try:
                df_full = _get_ohlcv_pykrx(code)
                if df_full is not None and not df_full.empty:
                    last_buy = _calculate_indicators_for_stock(df_full).iloc[-1]
                    try:
                        am_b = float(last_buy.get('Average_Momentum', 0) or 0)
                        am_prev_b = float(last_buy.get('Average_Momentum_prev', am_b) or am_b)
                        logging.info(
                            f"[Momentum] 매수: {code} {get_name(code)} qty={diff}, px={px:,.0f}, "
                            f"AM={am_b:.3f}, AM_prev={am_prev_b:.3f}, thr={cfg.get('momentum_threshold', 0.75):.2f}, "
                            f"type={str(cfg.get('test_type', 'crossing')).lower()}"
                        )
                    except Exception:
                        pass
            except Exception:
                pass
            # 고정 비율 손절가 설정 (매수가 대비 10% 하락 시 손절)
            stop_loss_price = px * 0.9
            # 종목명 가져오기
            stock_name = get_name(code)
            
            if code in positions and cur_qty > 0:
                old_qty = cur_qty
                old_avg = float(positions[code].get('avg', px))
                new_avg = ((old_avg * old_qty) + (px * diff)) / (old_qty + diff)
                positions[code]['qty'] = old_qty + diff
                positions[code]['avg'] = new_avg
                positions[code]['name'] = stock_name
                positions[code]['status'] = '구매중'  # 매수 주문 후 구매중 상태
                positions[code]['buy_date'] = current_date  # 구매중 날짜 기록
                if stop_loss_price > 0:
                    positions[code]['stop_loss_price'] = stop_loss_price
            else:
                positions[code] = {
                    "qty": diff, 
                    "avg": px, 
                    "name": stock_name,
                    "status": '구매중',  # 매수 주문 후 구매중 상태
                    "buy_date": current_date  # 구매중 날짜 기록
                }
                if stop_loss_price > 0:
                    positions[code]['stop_loss_price'] = stop_loss_price
            # 매수 로그 및 동그라미 표시
            stock_name = get_name(code)
            logging.info(f"⚪ [매수] {stock_name}({code}) {diff}주 @ {px:,.0f}원")
            record_trade(current_date, 'BUY', code, diff, px, None)
            budget_left -= need
            buy_count += 1

        if buy_count > 0:
            ledger['positions'] = positions
            save_positions(ledger)
        prune_zero_positions(ledger)
        save_positions(ledger)

    # 요약 리포트 전송
    try:
        # 이름 매핑: 현재 포트폴리오 목록 사용 가능 시 적용
        name_map = {}
        for item in MyPortfolioList:
            name_map[item.get('stock_code')] = item.get('stock_name', item.get('stock_code'))
        # 전자산 정보 구성
        total_asset_info = {
            'initial_asset_1': initial_asset_1,
            'initial_asset_2': initial_asset_2,
            'current_total_asset': total_equity,
            'profit_1': profit_1,
            'return_1': return_1,
            'profit_2': profit_2,
            'return_2': return_2
        }
        
        send_summary_report(
            PortfolioName,
            ledger,
            current_allocation=TotalMoney,
            initial_allocation=initial_allocation,
            name_map=name_map,
            realized_profit=float(cfg.get('realized_profit', 0.0)),
            total_asset_info=total_asset_info
        )
        
        # current_allocation 값을 설정 파일에 저장
        try:
            cfg['current_allocation'] = TotalMoney
            with open(config_file_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.warning(f"current_allocation 저장 실패: {e}")
    except Exception:
        pass

    # 주간 리밸런싱 완료 플래그 기록
    try:
        with open(os.path.join(script_dir, f'{BOT_NAME}_weekly_done.flag'), 'w', encoding='utf-8') as f:
            f.write(datetime.now().strftime('%G-%V'))
    except Exception:
        pass
    
    # 메모리 정리
    cleanup_memory()


if __name__ == '__main__':
    try:
        # 지갑 잔고와 포지션 동기화
        Common.sync_positions_with_wallet(BOT_NAME)

        main()
    except Exception as e:
        logging.exception(f"{BOT_NAME} 실행 오류: {e}")
        telegram.send(f"{PortfolioName} 실행 오류: {e}")


