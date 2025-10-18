# -*- coding: utf-8 -*-
"""
전략3: KOSPI 드로우다운 피라미딩 - KODEX200 레버리지(122630)

1) 전략 개요
- 지표: KOSPI의 1년 고점 대비 드로우다운(%)
- 진입: 드로우다운이 임계치에 도달할 때마다 설정된 비율로 누적 매수(피라미딩)
  · 기본 임계치: -15, -20, -25, -30, -35 (%)
  · 누적 비중: 10%, 10%, 20%, 40%, 20% (합 100% = 전략 배정금의 100%)
- 대상: 122630 KODEX 레버리지(2x)
- 청산: 옵션 선택
  · recover: KOSPI가 1년 고점(±버퍼) 회복 시 전량 매도
  · take_profit: ETF 평균단가 대비 설정 수익률 도달 시 전량 매도
  · trailing_atr: ATR 기반 트레일링 스탑(베스트: atr_mult=3.2, dd_window=252)
- 배분: 총자산의 20%를 전략 예산으로 사용(기본)

2) 스케줄/주문
- 실행: 기본 daily, rebalance_after_time 이후에만 트리거 확인/체결
- 주문: 지정가 유사(매수=현재가×1.01, 매도=현재가×0.99)
- 레저: 전략별(수량/평단/실현손익/초기분배금/진입단계 기록)

3) 파일
- KOSPIDrawdown_config.json: 전략 설정
  {
    "allocation_rate": 0.20,
    "rebalance_period": "daily",
    "rebalance_after_time": "14:50",
    "thresholds": [-15, -20, -25, -30, -35],
    "units": [0.10, 0.10, 0.20, 0.40, 0.20],
    "exit_mode": "recover",  # recover | take_profit
    "recover_buffer_pct": 0.0,
    "take_profit_pct": 0.05,
    "use_trailing_stop": true,
    "atr_mult": 3.2,
    "dd_window": 252
  }
- KOSPIDrawdown_positions.json: { positions:{"122630":{qty,avg}}, realized_profit, initial_allocation, filled_stages:[] }
- logs/KOSPIDrawdown_trades.csv, logs/KOSPIDrawdown_daily.csv

주의: 실제 주문은 ENABLE_ORDER_EXECUTION=True에서만 실행됩니다.
"""

import os
import sys
import json
import time
import logging
import gc
import psutil
from datetime import datetime, timedelta
from typing import Tuple

PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

import KIS_Common as Common
import KIS_API_Helper_KR as KisKR
import telegram_sender as telegram
from code_name_map import get_name, set_name

Common.SetChangeMode("REAL")

script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)

BOT_NAME = "KOSPIDrawdown"
PortfolioName = "[KOSPI하락시2배롱전략]"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, f'{BOT_NAME}.log'), mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

ENABLE_ORDER_EXECUTION = True

# 경로들
config_file_path = os.path.join(script_dir, f'{BOT_NAME}_config.json')
positions_file_path = os.path.join(script_dir, f"{BOT_NAME}_positions.json")
trades_csv_path = os.path.join(logs_dir, f"{BOT_NAME}_trades.csv")
daily_csv_path = os.path.join(logs_dir, f"{BOT_NAME}_daily.csv")

ETF_CODE = "122630"  # KODEX 레버리지
ETF_NAME = get_name(ETF_CODE, fallback="KODEX 레버리지")


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
        return {"positions": {}, "realized_profit": 0.0, "initial_allocation": None, "filled_stages": [], "entry_date": None}
    try:
        with open(positions_file_path, 'r', encoding='utf-8') as f:
            d = json.load(f)
            if 'filled_stages' not in d:
                d['filled_stages'] = []
            if 'initial_allocation' not in d:
                d['initial_allocation'] = None
            if 'entry_date' not in d:
                d['entry_date'] = None
            if 'positions' not in d:
                d['positions'] = {}
            if 'realized_profit' not in d:
                d['realized_profit'] = 0.0
            return d
    except Exception:
        return {"positions": {}, "realized_profit": 0.0, "initial_allocation": None, "filled_stages": [], "entry_date": None}


def save_positions(ledger: dict):
    try:
        with open(positions_file_path, 'w', encoding='utf-8') as f:
            json.dump(ledger, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def record_trade(date_str: str, action: str, code: str, qty: int, price: float, pnl: float | None):
    import csv
    header = ["date", "action", "code", "qty", "price", "pnl"]
    write_header = not os.path.exists(trades_csv_path)
    try:
        with open(trades_csv_path, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(header)
            w.writerow([date_str, action, code, qty, round(price, 4), (None if pnl is None else round(pnl, 2))])
    except Exception:
        pass


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
    except Exception:
        pass


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


def prune_zero_positions(ledger: dict) -> None:
    try:
        positions = ledger.get('positions', {})
        to_delete = [code for code, p in positions.items() if int(p.get('qty', 0)) <= 0]
        for code in to_delete:
            positions.pop(code, None)
        ledger['positions'] = positions
    except Exception:
        pass


# 요약 리포트
def _fmt_won(n: float, signed: bool = False) -> str:
    try:
        if signed:
            return f"{n:+,.0f}원"
        return f"{n:,.0f}원"
    except Exception:
        return str(n)


def send_summary_report(portfolio_name: str, ledger: dict, current_allocation: float, initial_allocation: float, name_map: dict[str, str]) -> None:
    try:
        positions = ledger.get('positions', {})
        lines = []
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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
            name = name_map.get(code, code)
            lines.append(f"{icon} {name}({qty}주)\n   {_fmt_won(now_val)}({_fmt_won(pnl_abs, signed=True)}:{pnl_pct:+.2f}%)")

        current_profit = invested_value_now - cost_basis
        current_profit_pct = (current_profit / cost_basis * 100.0) if cost_basis > 0 else 0.0
        realized = float(ledger.get('realized_profit', 0.0))

        # KOSPI 정보 추가
        kospi_high, kospi_current, kospi_high_date = get_kospi_one_year_high_and_current()
        kospi_info = ""
        if kospi_high and kospi_current and kospi_high_date:
            kospi_dd = ((kospi_current - kospi_high) / kospi_high) * 100
            kospi_info = f"📈 KOSPI: {kospi_current:,.1f} (1년고점: {kospi_high:,.1f} ({kospi_high_date}), 드로우다운: {kospi_dd:+.2f}%)"

        header = [
            f"📊 {portfolio_name}",
            f"상세 수익 현황 ({ts})",
            "==================================",
        ]
        if kospi_info:
            header.append(kospi_info)
            header.append("==================================")
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


def _get_date_str(days_ago: int) -> str:
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y%m%d")


def get_kospi_one_year_high_and_current() -> tuple[float | None, float | None, str | None]:
    # 우선 pykrx로 KOSPI 지수 400영업일 조회 시도
    try:
        from pykrx import stock as pykrx_stock
        start = _get_date_str(400)
        end = datetime.now().strftime("%Y%m%d")
        df = pykrx_stock.get_index_ohlcv_by_date(start, end, "1001")
        if df is None or df.empty:
            raise RuntimeError("pykrx KOSPI 데이터 없음")
        closes = df['종가'].dropna()
        if closes.empty:
            raise RuntimeError("pykrx KOSPI 종가 없음")
        if len(closes) > 260:
            recent = closes.tail(260)
            one_year_high = float(recent.max())
            high_date = recent.idxmax().strftime('%Y-%m-%d')
        else:
            one_year_high = float(closes.max())
            high_date = closes.idxmax().strftime('%Y-%m-%d')
        current_close = float(closes.iloc[-1])
        return one_year_high, current_close, high_date
    except Exception as e:
        logging.warning(f"KOSPI 지수 조회 실패(pykrx): {e}")
        # 호출부에서 3개 변수 언팩을 기대하므로 3개 반환으로 보정
        return None, None, None


def _fetch_etf_ohlcv(code: str, start_yyyymmdd: str, end_yyyymmdd: str):
    try:
        from pykrx import stock as pykrx_stock
        df = pykrx_stock.get_market_ohlcv_by_date(start_yyyymmdd, end_yyyymmdd, code)
        return df
    except Exception as e:
        logging.warning(f"ETF OHLCV 조회 실패(pykrx): {e}")
        return None


def _compute_atr_from_df(df, window: int) -> float | None:
    try:
        import numpy as np
        high = df['고가'].astype(float).values
        low = df['저가'].astype(float).values
        close = df['종가'].astype(float).values
        if len(close) < window + 1:
            return None
        tr = []
        prev_close = close[0]
        for i in range(1, len(close)):
            cur_high = high[i]
            cur_low = low[i]
            tr.append(max(cur_high - cur_low, abs(cur_high - prev_close), abs(cur_low - prev_close)))
            prev_close = close[i]
        if len(tr) < window:
            return None
        atr = sum(tr[-window:]) / float(window)
        return float(atr)
    except Exception as e:
        logging.warning(f"ATR 계산 실패: {e}")
        return None


def initialize_and_check_conditions():
    """프로그램 실행 전 초기화 및 조건 체크"""
    # 잔고 조회 하면서 토큰 발급
    balance = KisKR.GetBalance()
    
    # 실행 가드: 주말/장상태
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
    
    return balance, current_date


def main():
    # 0) 초기화 및 조건 체크
    Balance, current_date = initialize_and_check_conditions()
    
    # 1) 설정 로딩
    try:
        if os.path.exists(config_file_path):
            with open(config_file_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        else:
            cfg = {
                "allocation_rate": 0.20,
                "rebalance_period": "daily",
                "rebalance_after_time": "14:50",
                "thresholds": [-15, -20, -25, -30, -35],
                "units": [0.10, 0.10, 0.20, 0.40, 0.20],
                "exit_mode": "recover",
                "recover_buffer_pct": 0.0,
                "take_profit_pct": 0.05,
            }
            logging.warning(f"설정 파일이 없어 기본값으로 실행합니다: {config_file_path}")
    except Exception as e:
        logging.error(f"{config_file_path} 로딩 실패: {e}")
        telegram.send(f"{PortfolioName} 설정 로딩 실패. 프로그램 종료")
        sys.exit(1)

    # 2) 총자산 및 전략 예산
    total_equity = float(Balance['TotalMoney'])
    InvestRate = float(cfg.get('allocation_rate', 0.20))
    TotalMoney = total_equity * InvestRate
    logging.info(f"총 평가금액: {total_equity:,.0f}원, 전략3 할당: {TotalMoney:,.0f}원 ({InvestRate*100:.1f}%)")

    ledger = load_positions()
    if ledger.get('initial_allocation') is None:
        ledger['initial_allocation'] = TotalMoney
        save_positions(ledger)

    # 3) 스케줄(데일리 after_time)
    rebalance_period = str(cfg.get('rebalance_period', 'daily')).lower()
    rebalance_after_time = str(cfg.get('rebalance_after_time', '14:50'))
    now_hm = time.strftime('%H:%M')
    if rebalance_period == 'daily':
        if now_hm < rebalance_after_time:
            logging.info('지정 시간 전이므로 오늘은 실행하지 않습니다.')
            # 항상 일일 스냅샷/요약 전송
            try:
                # 현재 보유 평가
                invested_value = 0.0
                pos = ledger.get('positions', {}).get(ETF_CODE, {"qty": 0, "avg": 0.0})
                held_qty = int(pos.get('qty', 0))
                if held_qty > 0:
                    invested_value = held_qty * KisKR.GetCurrentPrice(ETF_CODE)
                strategy_cash = max(0.0, TotalMoney - invested_value)
                record_daily(time.strftime("%Y-%m-%d"), strategy_cash + invested_value, strategy_cash, invested_value, 1 if held_qty > 0 else 0)
                send_summary_report(
                    PortfolioName,
                    ledger,
                    current_allocation=TotalMoney,
                    initial_allocation=float(ledger.get('initial_allocation') or TotalMoney),
                    name_map={ETF_CODE: ETF_NAME},
                )
            except Exception:
                pass
            return

    # 4) KOSPI 1년고점/현재, 드로우다운 계산
    one_year_high, current_index, high_date = get_kospi_one_year_high_and_current()
    if one_year_high is None or current_index is None or one_year_high <= 0:
        logging.warning('KOSPI 데이터 부족으로 오늘은 트리거 판단을 건너뜁니다.')
        return
    dd_pct = (current_index / one_year_high - 1.0) * 100.0
    try:
        high_date_str = str(high_date) if high_date else 'N/A'
    except Exception:
        high_date_str = 'N/A'
    logging.info(f"KOSPI 1Y High={one_year_high:,.2f} ({high_date_str}), Current={current_index:,.2f} ({dd_pct:+.2f}%)")

    thresholds = list(cfg.get('thresholds', [-15, -20, -25, -30, -35]))
    units = list(cfg.get('units', [0.10, 0.10, 0.20, 0.40, 0.20]))
    if len(thresholds) != len(units):
        logging.error('thresholds와 units 길이가 다릅니다.')
        return

    exit_mode = str(cfg.get('exit_mode', 'recover')).lower()
    recover_buffer_pct = float(cfg.get('recover_buffer_pct', 0.0))
    take_profit_pct = float(cfg.get('take_profit_pct', 0.05))
    use_trailing_stop = bool(cfg.get('use_trailing_stop', True))
    atr_mult = float(cfg.get('atr_mult', 3.2))
    dd_window = int(cfg.get('dd_window', 252))

    # 5) 현재 보유 평가
    invested_value = 0.0
    pos = ledger.get('positions', {}).get(ETF_CODE, {"qty": 0, "avg": 0.0})
    held_qty = int(pos.get('qty', 0))
    held_avg = float(pos.get('avg', 0.0))
    if held_qty > 0:
        invested_value = held_qty * KisKR.GetCurrentPrice(ETF_CODE)

    # 일일 리포트 기록(현금=예산-투자액 제한)
    strategy_cash = max(0.0, TotalMoney - invested_value)
    record_daily(time.strftime("%Y-%m-%d"), strategy_cash + invested_value, strategy_cash, invested_value, 1 if held_qty > 0 else 0)

    if not ENABLE_ORDER_EXECUTION:
        logging.info('매매 실행 비활성화')
        return
    if not KisKR.IsMarketOpen():
        logging.info('장이 열려있지 않습니다.')
        return

    # 6) 청산 조건 체크
    sold_any = False
    if held_qty > 0:
        if exit_mode == 'recover':
            recover_threshold = one_year_high * (1.0 - recover_buffer_pct)
            if current_index >= recover_threshold:
                # 시장가 매도 전환
                try:
                    data = KisKR.MakeSellMarketOrder(ETF_CODE, held_qty)
                except Exception:
                    data = None
                approx_px = float(KisKR.GetCurrentPrice(ETF_CODE))
                pnl = (approx_px - held_avg) * held_qty
                ledger['positions'][ETF_CODE] = {"qty": 0, "avg": 0.0}
                ledger['realized_profit'] = float(ledger.get('realized_profit', 0.0)) + pnl
                ledger['filled_stages'] = []  # 재시작을 위해 단계 리셋
                save_positions(ledger)
                record_trade(time.strftime("%Y-%m-%d"), 'SELL', ETF_CODE, held_qty, approx_px, pnl)
                try:
                    icon = '🟢' if pnl > 0 else ('🔴' if pnl < 0 else '⚪')
                    msg = format_kis_order_message(PortfolioName, '매도', ETF_NAME, data, order_px=approx_px)
                    reason = f"리커버 모드 청산 (1Y High 회복, buffer={recover_buffer_pct*100:.1f}%)"
                    telegram.send(f"{icon} {msg}\n이유: {reason}")
                except Exception:
                    pass
                sold_any = True
        elif exit_mode == 'take_profit':
            # ETF 가격 기준 수익률
            cur_px = KisKR.GetCurrentPrice(ETF_CODE)
            if held_avg > 0 and cur_px >= held_avg * (1.0 + take_profit_pct):
                try:
                    data = KisKR.MakeSellMarketOrder(ETF_CODE, held_qty)
                except Exception:
                    data = None
                approx_px = float(KisKR.GetCurrentPrice(ETF_CODE))
                pnl = (approx_px - held_avg) * held_qty
                ledger['positions'][ETF_CODE] = {"qty": 0, "avg": 0.0}
                ledger['realized_profit'] = float(ledger.get('realized_profit', 0.0)) + pnl
                ledger['filled_stages'] = []
                save_positions(ledger)
                record_trade(time.strftime("%Y-%m-%d"), 'SELL', ETF_CODE, held_qty, approx_px, pnl)
                try:
                    icon = '🟢' if pnl > 0 else ('🔴' if pnl < 0 else '⚪')
                    msg = format_kis_order_message(PortfolioName, '매도', ETF_NAME, data, order_px=approx_px)
                    reason = f"목표 수익률 달성 (take_profit={take_profit_pct*100:.1f}%)"
                    telegram.send(f"{icon} {msg}\n이유: {reason}")
                except Exception:
                    pass
                sold_any = True

        # ATR 트레일링 스탑(옵션)
        if not sold_any and use_trailing_stop:
            start = _get_date_str(dd_window + 20)
            end = datetime.now().strftime("%Y%m%d")
            df_etf = _fetch_etf_ohlcv(ETF_CODE, start, end)
            if df_etf is not None and not df_etf.empty:
                atr = _compute_atr_from_df(df_etf, window=min(14, max(5, len(df_etf)//20)))
                try:
                    cur_px = float(df_etf['종가'].astype(float).iloc[-1])
                except Exception:
                    cur_px = KisKR.GetCurrentPrice(ETF_CODE)
                if atr is not None and cur_px is not None and cur_px > 0:
                    stop_px = cur_px - atr_mult * atr
                    # 손절 조건: stop_px < avg 보다 현재가가 stop 아래라면 청산
                    if cur_px <= stop_px:
                        try:
                            data = KisKR.MakeSellMarketOrder(ETF_CODE, held_qty)
                        except Exception:
                            data = None
                        approx_px = float(KisKR.GetCurrentPrice(ETF_CODE))
                        pnl = (approx_px - held_avg) * held_qty
                        ledger['positions'][ETF_CODE] = {"qty": 0, "avg": 0.0}
                        ledger['realized_profit'] = float(ledger.get('realized_profit', 0.0)) + pnl
                        ledger['filled_stages'] = []
                        save_positions(ledger)
                        record_trade(time.strftime("%Y-%m-%d"), 'SELL', ETF_CODE, held_qty, approx_px, pnl)
                        try:
                            icon = '🟢' if pnl > 0 else ('🔴' if pnl < 0 else '⚪')
                            msg = format_kis_order_message(PortfolioName, '매도', ETF_NAME, data, order_px=approx_px)
                            reason = f"ATR 트레일링 스탑 (mult={atr_mult})"
                            telegram.send(f"{icon} {msg}\n이유: {reason}")
                        except Exception:
                            pass
                        sold_any = True

    if sold_any:
        prune_zero_positions(ledger)
        save_positions(ledger)

    # 7) 진입 단계 판단 및 누적 매수
    # 드로우다운이 특정 임계치 이하(더 큰 하락)면 해당 단계 활성
    active_stage_idxs = [i for i, th in enumerate(thresholds) if dd_pct <= th]
    filled_stages = set(ledger.get('filled_stages', []))

    buy_count = 0
    budget_used = 0.0
    # 현재 보유 평가 반영
    budget_used = invested_value

    for idx in active_stage_idxs:
        if idx in filled_stages:
            continue
        unit_rate = float(units[idx])
        if unit_rate <= 0:
            continue
        cur_px = KisKR.GetCurrentPrice(ETF_CODE) * 1.01
        if cur_px is None or cur_px <= 0:
            continue
        desired_money = TotalMoney * unit_rate
        qty = int(desired_money / cur_px)
        if qty < 1:
            qty = 1  # 최소 1주 규칙
        need = qty * cur_px
        if budget_used + need > TotalMoney:
            remain = TotalMoney - budget_used
            adj = int(remain / cur_px)
            if adj < 1:
                logging.info(f"예산 부족으로 단계{idx+1} 매수 취소")
                continue
            qty = adj
            need = qty * cur_px

        data = KisKR.MakeBuyLimitOrder(ETF_CODE, qty, cur_px)
        try:
            msg = format_kis_order_message(PortfolioName, '매수', ETF_NAME, data, order_px=cur_px)
            telegram.send(msg)
        except Exception:
            pass

        # 레저 업데이트
        old_qty = int(ledger['positions'].get(ETF_CODE, {}).get('qty', 0))
        old_avg = float(ledger['positions'].get(ETF_CODE, {}).get('avg', 0.0))
        new_qty = old_qty + qty
        new_avg = cur_px if new_qty == 0 else ((old_avg * old_qty + cur_px * qty) / max(1, new_qty))
        ledger['positions'][ETF_CODE] = {"qty": new_qty, "avg": new_avg}
        filled_stages.add(idx)
        ledger['filled_stages'] = sorted(list(filled_stages))
        save_positions(ledger)
        record_trade(time.strftime("%Y-%m-%d"), 'BUY', ETF_CODE, qty, cur_px, None)

        buy_count += 1
        budget_used += need

    prune_zero_positions(ledger)
    save_positions(ledger)

    # 요약 리포트 전송
    try:
        name_map = {ETF_CODE: ETF_NAME}
        send_summary_report(
            PortfolioName,
            ledger,
            current_allocation=TotalMoney,
            initial_allocation=float(ledger.get('initial_allocation') or TotalMoney),
            name_map=name_map,
        )
    except Exception:
        pass
    
    # 메모리 정리
    cleanup_memory()


if __name__ == '__main__':
    try:
        # 지갑 잔고와 포지션 동기화
        Common.sync_positions_with_wallet(PortfolioName)

        main()
    except Exception as e:
        logging.exception(f"{BOT_NAME} 실행 오류: {e}")
        telegram.send(f"{PortfolioName} 실행 오류: {e}")


