# -*- coding: utf-8 -*-
"""
전략2: 레버리지/인버스 ETF 강도 기반 리밸런싱 (라이브)

1) 전략 개요
- 대상: KOSPI/KOSDAQ 레버리지·인버스 ETF
  · KOSPI: 122630(레버리지), 252670(인버스2X)
  · KOSDAQ: 233740(레버리지), 251340(인버스)
- 배분: 총자산의 20%를 전략 예산으로 사용(기본), 시장/포지션별 균등 배분
- 실행: 매일 스케줄 가능(기본), 설정에 따라 주간 리밸런싱도 가능
- 주문: 지정가 유사 방식(매수=현재가×1.01, 매도=현재가×0.99)
- 레저: 전략별로 수량/평단/실현손익 분리 관리

2) 신호/측면
- 간단화를 위해 설정 기반 포지션(side) 선택 방식을 사용
  · cfg.target_sides.KOSPI in ['long','short','none']
  · cfg.target_sides.KOSDAQ in ['long','short','none']
- 추후, etf_strength 백테스트 로직의 조건(up_pct, up_ctr, up_vol 등)과 연계 가능

3) 진입 옵션
- entry_at_open: true/false - 시가 진입 여부 (true: 시가, false: 현재가×1.01)
- entry_same_day: true/false - 같은 날 진입 여부 (true: 오늘신호→오늘진입, false: 오늘신호→다음날시가진입)

4) 파일
- ETFStrength_config.json: 전략 전용 설정
  { "allocation_rate": 0.20, "rebalance_period": "daily|weekly",
    "rebalance_day": "MON", "rebalance_after_time": "14:50",
    "target_sides": {"KOSPI": "long", "KOSDAQ": "none"} }
- ETFStrength_positions.json: positions{code:{qty,avg}}, realized_profit
- logs/ETFStrength_trades.csv, logs/ETFStrength_daily.csv: 거래/일일 로그

5) 크론탭 예시(KST, 주중 매일 14:55 실행)
  SHELL=/bin/bash
  PATH=/usr/local/bin:/usr/bin:/bin
  55 14 * * 1-5 /usr/bin/python3 /path/to/kook/kis/ETFStrength.py >> /path/to/kook/kis/logs/cron_etf_strength.log 2>&1
"""

import os
import sys
import json
import time
import logging
import gc
import psutil
from datetime import datetime, timedelta
from typing import Optional, Tuple
import pandas as pd
import numpy as np

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

BOT_NAME = "ETFStrength"
PortfolioName = "[코스피닥2배롱숏전략]"
# NAME_MAP_FILE 제거 - code_name_map.py 사용

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, f'{BOT_NAME}.log'), mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

ENABLE_ORDER_EXECUTION = True

# 파일 경로
config_file_path = os.path.join(script_dir, f'{BOT_NAME}_config.json')
positions_file_path = os.path.join(script_dir, f"{BOT_NAME}_positions.json")
trades_csv_path = os.path.join(logs_dir, f"{BOT_NAME}_trades.csv")
daily_csv_path = os.path.join(logs_dir, f"{BOT_NAME}_daily.csv")

ASSETS = {
    'KOSPI': {'long': '122630', 'short': '252670'},
    'KOSDAQ': {'long': '233740', 'short': '251340'},
}


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


# _load_name_map, _save_name_map 함수 제거 - code_name_map.py 사용

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


def sync_positions_with_actual_holdings(ledger: dict) -> dict:
    """실제 보유 자산과 JSON 파일을 동기화합니다. 
    - ETFStrength 전략 종목만 처리 (다른 전략 종목은 추가하지 않음)
    - 갯수 조정 없음 (현재 보유 갯수 기준으로 동기화)
    """
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
        
        # JSON 파일의 포지션과 비교 (ETFStrength 전략 종목만)
        json_positions = ledger.get('positions', {})
        sync_changes = []
        
        # 1. JSON에 있지만 실제로는 없는 종목 (매도 성공)
        codes_to_remove = []
        for code, pos in json_positions.items():
            if code not in actual_positions:
                sync_changes.append(f"매도 완료: {code} {get_name(code)} (JSON: {pos.get('qty', 0)}주)")
                codes_to_remove.append(code)
        
        # 제거할 종목들을 JSON에서 제거
        for code in codes_to_remove:
            json_positions.pop(code, None)
        
        # 2. JSON에 있는 종목만 업데이트 (다른 전략 종목은 절대 추가하지 않음)
        for code, pos in json_positions.items():
            if code in actual_positions:
                actual_pos = actual_positions[code]
                json_qty = pos.get('qty', 0)
                actual_qty = actual_pos['qty']
                
                # 현재 보유 갯수보다 크면 인정, 작으면 불인정
                if actual_qty >= json_qty:
                    # 수량이나 평단이 다르면 업데이트
                    if (json_qty != actual_qty or 
                        abs(pos.get('avg', 0) - actual_pos['avg']) > 0.01):
                        sync_changes.append(
                            f"부분 체결: {code} {get_name(code)} "
                            f"(JSON: {json_qty}주@{pos.get('avg', 0):,.0f}원 → "
                            f"실제: {actual_qty}주@{actual_pos['avg']:,.0f}원)"
                        )
                        # 실제 값으로 업데이트
                        json_positions[code]['qty'] = actual_qty
                        json_positions[code]['avg'] = actual_pos['avg']
                        json_positions[code]['name'] = get_name(code)  # 종목명 업데이트
                        json_positions[code]['status'] = '보유중'  # 상태를 보유중으로 설정
                else:
                    # 실제 보유 갯수가 JSON보다 작으면 무시 (다른 전략에서 매도했을 가능성)
                    sync_changes.append(
                        f"갯수 부족 무시: {code} {get_name(code)} "
                        f"(JSON: {json_qty}주, 실제: {actual_qty}주) - 다른 전략 매도 가능성"
                    )
        
        # 변경사항이 있으면 로그 출력 및 저장
        if sync_changes:
            logging.info("[ETFStrength] 포지션 동기화 완료:")
            for change in sync_changes:
                logging.info(f"  - {change}")
            
            # JSON 파일 업데이트
            ledger['positions'] = json_positions
            save_positions(ledger)
        else:
            logging.info("[ETFStrength] 포지션 동기화: 변경사항 없음")
        
        return ledger
        
    except Exception as e:
        logging.error(f"포지션 동기화 실패: {e}")
        return ledger


def prune_zero_positions(ledger: dict) -> None:
    try:
        positions = ledger.get('positions', {})
        to_delete = [code for code, p in positions.items() if int(p.get('qty', 0)) <= 0]
        for code in to_delete:
            positions.pop(code, None)
        ledger['positions'] = positions
    except Exception:
        pass


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


# =============================================================================
# 시그널/ATR 트레일링 유틸 (pykrx 사용)
# =============================================================================
def _ymd(days_ago: int) -> str:
    return (datetime.now() - timedelta(days=days_ago)).strftime('%Y%m%d')


def _load_etf_hist(code: str, days: int = 400) -> Optional[pd.DataFrame]:
    try:
        from pykrx import stock as pykrx_stock
        start = _ymd(days)
        end = datetime.now().strftime('%Y%m%d')
        df = pykrx_stock.get_market_ohlcv_by_date(start, end, code)
        if df is None or df.empty:
            return None
        df = df.rename(columns={'시가': 'open', '고가': 'high', '저가': 'low', '종가': 'close', '거래량': 'volume'})
        return df[['open','high','low','close','volume']].astype(float)
    except Exception as e:
        logging.warning(f"ETF 히스토리 로드 실패({code}): {e}")
        return None


def _prepare_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out['pct'] = out['close'].pct_change()
    rng = (out['high'] - out['low']).replace(0, np.nan)
    out['close_to_range'] = ((out['close'] - out['low']) / rng).clip(0, 1)
    out['vol_ma20'] = out['volume'].rolling(20).mean()
    out['vol_ratio'] = out['volume'] / out['vol_ma20']
    # ATR(14)
    try:
        import talib
        out['atr'] = talib.ATR(out['high'], out['low'], out['close'], timeperiod=14)
    except Exception:
        # 간이 ATR
        tr = []
        prev_close = out['close'].iloc[0]
        for i in range(1, len(out)):
            cur_high = out['high'].iloc[i]
            cur_low = out['low'].iloc[i]
            tr.append(max(cur_high - cur_low, abs(cur_high - prev_close), abs(cur_low - prev_close)))
            prev_close = out['close'].iloc[i]
        out['atr'] = np.nan
        if len(tr) > 0:
            out.loc[out.index[1]:, 'atr'] = pd.Series(tr, index=out.index[1:]).rolling(14).mean()
    return out


def _yesterday_signal(market: str, params: dict) -> Optional[str]:
    codes = ASSETS[market]
    df_long = _load_etf_hist(codes['long'])
    df_short = _load_etf_hist(codes['short'])
    if df_long is None or df_short is None:
        return None
    L = _prepare_indicators(df_long).dropna().copy()
    S = _prepare_indicators(df_short).dropna().copy()
    if L.empty or S.empty:
        return None
    # 어제 시그널 → 오늘 진입(next_close 기본)
    y = min(L.index.max(), S.index.max())
    try:
        y_idx = L.index.get_loc(y)
    except Exception:
        return None
    if y_idx < 1:
        return None
    rowL = L.iloc[y_idx]
    up_signal = (rowL['pct'] >= params['up_pct']) and (rowL['close_to_range'] >= params['up_ctr']) and (rowL['vol_ratio'] >= params['up_vol'])
    down_signal = (rowL['pct'] <= -params['down_pct']) and (rowL['close_to_range'] <= (1 - params['down_ctr'])) and (rowL['vol_ratio'] >= params['down_vol'])
    if up_signal:
        return 'long'
    if down_signal:
        return 'short'
    return None


def _get_intraday_snapshot_kis(code: str) -> Optional[dict]:
    try:
        base = Common.GetUrlBase(Common.GetNowDist())
        path = "uapi/domestic-stock/v1/quotations/inquire-price"
        url = f"{base}/{path}"
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {Common.GetToken(Common.GetNowDist())}",
            "appKey": Common.GetAppKey(Common.GetNowDist()),
            "appSecret": Common.GetAppSecret(Common.GetNowDist()),
            "tr_id": "FHKST01010200",
        }
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
        import requests
        res = requests.get(url, headers=headers, params=params, timeout=3)
        if res.status_code != 200:
            return None
        js = res.json()
        if str(js.get('rt_cd')) != '0':
            return None
        o = js.get('output', {}) or js.get('output1', {}) or {}
        def f(key):
            v = o.get(key)
            try:
                return float(v)
            except Exception:
                try:
                    return float(str(v).replace(',', ''))
                except Exception:
                    return 0.0
        info = {
            'cur': f('stck_prpr'),
            'high': f('stck_hgpr'),
            'low': f('stck_lwpr'),
            'pct': f('prdy_ctrt'),
            'vol': f('acml_vol'),
            'prev_close': f('stck_prdy_cprc') if 'stck_prdy_cprc' in o else 0.0,
        }
        return info
    except Exception:
        return None


def _today_signal(market: str, params: dict) -> Optional[str]:
    codes = ASSETS[market]
    # 롱 ETF의 과거 지표(특히 vol_ma20)만 활용하여 오늘 유동성 기준을 계산
    df_long = _load_etf_hist(codes['long'])
    if df_long is None or df_long.empty:
        return None
    L = _prepare_indicators(df_long).dropna().copy()
    if L.empty:
        return None
    vol_ma20 = float(L.iloc[-1]['vol_ma20']) if 'vol_ma20' in L.columns else 0.0
    snap_long = _get_intraday_snapshot_kis(codes['long'])
    if not snap_long:
        return None
    cur = float(snap_long.get('cur', 0.0)); high = float(snap_long.get('high', 0.0)); low = float(snap_long.get('low', 0.0))
    pct_today_ratio = float(snap_long.get('pct', 0.0)) / 100.0  # API는 % 단위
    vol_today = float(snap_long.get('vol', 0.0))
    rng = max(high - low, 1e-9)
    close_to_range = max(0.0, min(1.0, (cur - low) / rng)) if rng > 0 else 0.0
    vol_ratio = (vol_today / vol_ma20) if vol_ma20 > 0 else 0.0
    up_signal = (pct_today_ratio >= params['up_pct']) and (close_to_range >= params['up_ctr']) and (vol_ratio >= params['up_vol'])
    down_signal = (pct_today_ratio <= -params['down_pct']) and (close_to_range <= (1 - params['down_ctr'])) and (vol_ratio >= params['down_vol'])
    if up_signal:
        return 'long'
    if down_signal:
        return 'short'
    return None


def _check_atr_stop(code: str, atr_mult: float, highest_price: float) -> Tuple[bool, float, float]:
    """ATR 트레일링 스탑 조건 확인.
    
    Returns:
        Tuple[bool, float, float]: (트리거 여부, 계산된 스탑 가격, 당일 고가로 업데이트된 새 high 값)
    """
    df = _load_etf_hist(code)
    if df is None or df.empty:
        return False, 0.0, highest_price
    D = _prepare_indicators(df).dropna()
    if D.empty:
        return False, 0.0, highest_price

    today_row = D.iloc[-1]
    today_high = float(today_row['high'])
    today_low = float(today_row['low'])
    atr = float(today_row['atr']) if 'atr' in today_row and not np.isnan(today_row['atr']) else 0.0

    if atr <= 0:
        return False, 0.0, highest_price

    new_high = max(highest_price, today_high)
    stop_price = new_high - atr_mult * atr
    triggered = today_low <= stop_price
    
    return triggered, stop_price, new_high


def initialize_and_check_conditions():
    """프로그램 실행 전 초기화 및 조건 체크"""
    # 잔고 조회 하면서 토큰 발급
    balance = KisKR.GetBalance()
    
    # 실행 가드: 주말/장상태 알림 후 종료
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
        with open(config_file_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {
            "allocation_rate": 0.20,
            "rebalance_period": "daily",
            "rebalance_day": "MON",
            "rebalance_after_time": "14:50",
            "target_sides": {"KOSPI": "long", "KOSDAQ": "none"}
        }
        logging.warning(f"설정 파일이 없어 기본값으로 실행합니다: {config_file_path}")
    except Exception as e:
        logging.error(f"{config_file_path} 로딩 실패: {e}")
        telegram.send(f"{PortfolioName} 설정 로딩 실패. 프로그램 종료")
        sys.exit(1)

    # 2) 예산 산정
    total_equity = float(Balance['TotalMoney'])
    InvestRate = float(cfg.get('allocation_rate', 0.20))
    TotalMoney = total_equity * InvestRate
    logging.info(f"총 평가금액: {total_equity:,.0f}원, 전략2 할당: {TotalMoney:,.0f}원 ({InvestRate*100:.1f}%)")

    # 초기 분배금: 최초 실행 시 고정 저장, 이후 변하지 않음
    ledger = load_positions()
    if ledger.get('initial_allocation') is None:
        ledger['initial_allocation'] = TotalMoney
        save_positions(ledger)
    
    # 구매중 포지션 상태 업데이트 (구매중 → 보유중)
    update_pending_to_held_positions(ledger)
    
    # 구매중 포지션 정리 (다음날 삭제)
    check_and_cleanup_pending_positions(ledger, current_date)
    
    # 실제 보유 자산과 JSON 파일 동기화
    ledger = sync_positions_with_actual_holdings(ledger)

    # 3) 주간 리밸런싱 옵션
    rebalance_period = str(cfg.get('rebalance_period', 'daily')).lower()
    rebalance_day = str(cfg.get('rebalance_day', 'MON')).upper()
    rebalance_after_time = str(cfg.get('rebalance_after_time', '14:50'))
    weekday_map = {0: 'MON', 1: 'TUE', 2: 'WED', 3: 'THU', 4: 'FRI', 5: 'SAT', 6: 'SUN'}
    today_wd = weekday_map.get(datetime.now().weekday())
    now_hm = time.strftime('%H:%M')
    if rebalance_period == 'weekly':
        weekly_flag_path = os.path.join(script_dir, f'{BOT_NAME}_weekly_done.flag')
        week_id = datetime.now().strftime('%G-%V')
        last_done_week = None
        if os.path.exists(weekly_flag_path):
            try:
                with open(weekly_flag_path, 'r', encoding='utf-8') as f:
                    last_done_week = f.read().strip()
            except Exception:
                last_done_week = None
        if last_done_week == week_id:
            logging.info('이번 주 이미 리밸런싱 완료')
            return
        if not ((today_wd == rebalance_day and now_hm >= rebalance_after_time and KisKR.IsMarketOpen()) or
                (today_wd != rebalance_day and now_hm >= rebalance_after_time and KisKR.IsMarketOpen())):
            logging.info('주간 조건 미충족으로 오늘은 리밸런싱하지 않음')
            return

    # 4) 포지션 대상 결정 (백테스트 베스트 파라미터 기반 시그널)
    # 베스트(백테스트 검증) 파라미터 - 그리드 최고 수익률 기준
    best_params = {
        'KOSPI': {'up_pct': 0.005, 'up_ctr': 0.5, 'up_vol': 1.0, 'down_pct': 0.01, 'down_ctr': 0.6, 'down_vol': 0.7, 'atr_mult': 2.5, 'entry_at_open': True, 'entry_same_day': True},
        'KOSDAQ': {'up_pct': 0.005, 'up_ctr': 0.5, 'up_vol': 1.0, 'down_pct': 0.01, 'down_ctr': 0.7, 'down_vol': 0.8, 'atr_mult': 2.0, 'entry_at_open': True, 'entry_same_day': True},
    }
    # 설정 파일로 override 가능
    cfg_best = cfg.get('best_params', {})
    for mkt in ['KOSPI', 'KOSDAQ']:
        if mkt in cfg_best:
            best_params[mkt].update(cfg_best[mkt])

    targets = []  # [(code, name)] — 오늘 운용 대상(시그널 결과)
    chosen_side = {}
    for market in ['KOSPI', 'KOSDAQ']:
        params = best_params[market]
        # 오늘 신호 기반 진입 (백테스트와 동일)
        side = _today_signal(market, params)
        
        # target_sides 설정 확인
        target_side = cfg.get('target_sides', {}).get(market, 'long')
        
        if side in ['long', 'short']:
            # target_sides가 'both'인 경우 시그널에 따라, 아니면 설정된 방향만
            if target_side == 'both':
                # 양방향: 시그널에 따라 롱/숏 선택
                code = ASSETS[market][side]
                name = get_name(code, f"{market}-{side.upper()}")
                set_name(code, name)
                targets.append((code, name))
                chosen_side[market] = side
            elif target_side == side:
                # 설정된 방향과 시그널이 일치하는 경우만
                code = ASSETS[market][side]
                name = get_name(code, f"{market}-{side.upper()}")
                set_name(code, name)
                targets.append((code, name))
                chosen_side[market] = side

    if not targets:
        logging.info('대상 없음(target_sides 설정 확인). 종료합니다.')
        # 항상 일일 스냅샷/요약 전송
        try:
            invested_value = 0.0
            for code, pos in ledger.get('positions', {}).items():
                qty = int(pos.get('qty', 0))
                if qty > 0:
                    invested_value += qty * KisKR.GetCurrentPrice(code)
            strategy_cash = max(0.0, TotalMoney - invested_value)
            record_daily(
                current_date,
                invested_value + strategy_cash,
                strategy_cash,
                invested_value,
                sum(1 for p in ledger.get('positions', {}).values() if int(p.get('qty', 0)) > 0)
            )
            send_summary_report(
                PortfolioName,
                ledger,
                current_allocation=TotalMoney,
                initial_allocation=float(ledger.get('initial_allocation') or TotalMoney),
                name_map={},
            )
        except Exception:
            pass
        return

    # 5) 레저 로딩 및 평가
    # 위에서 로드/초기화된 ledger 재사용
    invested_value = 0.0
    for code, _ in targets:
        pos = ledger.get('positions', {}).get(code, {})
        qty = int(pos.get('qty', 0))
        if qty > 0:
            invested_value += qty * KisKR.GetCurrentPrice(code)

    record_daily(current_date, invested_value + max(0.0, TotalMoney - invested_value),
                 max(0.0, TotalMoney - invested_value), invested_value,
                 sum(1 for p in ledger.get('positions', {}).values() if int(p.get('qty', 0)) > 0))

    if not ENABLE_ORDER_EXECUTION:
        logging.info('매매 실행 비활성화')
        return

    if not KisKR.IsMarketOpen():
        logging.info('장이 열려있지 않습니다.')
        return

    # =========================================================================
    # 6) ATR 트레일링 스탑 실행 (리밸런싱보다 우선)
    # =========================================================================
    sell_count = 0
    pruned_by_ts = []  # TS로 매도된 코드 목록
    for held_code, pos in list(ledger.get('positions', {}).items()):
        if int(pos.get('qty', 0)) <= 0:
            continue

        # 적절한 atr_mult 찾기
        market = None
        for m, sides in ASSETS.items():
            if held_code in sides.values():
                market = m
                break
        
        if not market:
            continue

        atr_mult = best_params[market].get('atr_mult', 3.0)
        current_hi = float(pos.get('hi', 0.0))

        triggered, stop_price, new_hi = _check_atr_stop(held_code, atr_mult, current_hi)
        pos['hi'] = new_hi  # 항상 최신 high 값으로 업데이트

        if triggered:
            logging.info(f"ATR Trailing Stop Triggered for {held_code} at {stop_price:,.0f}")
            qty_to_sell = int(pos.get('qty', 0))
            # 시장가 매도 전환
            try:
                data = KisKR.MakeSellMarketOrder(held_code, qty_to_sell)
            except Exception:
                data = None
            approx_px = float(KisKR.GetCurrentPrice(held_code))
            pnl = (approx_px - float(pos.get('avg', 0.0))) * qty_to_sell
            pos['qty'] = 0
            pos['avg'] = 0.0
            pos['hi'] = 0.0
            ledger['realized_profit'] = float(ledger.get('realized_profit', 0.0)) + pnl
            
            record_trade(current_date, 'SELL_TS', held_code, qty_to_sell, approx_px, pnl)
            
            try:
                display_name = get_name(held_code)
                msg = format_kis_order_message(PortfolioName, '매도(TS)', display_name, data, order_px=approx_px)
                icon = '🟢' if pnl > 0 else ('🔴' if pnl < 0 else '⚪')
                reason = f"ATR 추적손절 발동 (stop={stop_price:,.0f}, mult={atr_mult})"
                telegram.send(f"{icon} {msg}\n이유: {reason}")
            except Exception:
                pass
            
            sell_count += 1
            pruned_by_ts.append(held_code)
    
    # TS 매도 후 포지션 즉시 저장
    if sell_count > 0:
        save_positions(ledger)

    # =========================================================================
    # 7) 균등 배분으로 수량 산정(시장별 50:50, 시장 내 1종목만 운용)
    # =========================================================================
    unit_rate = 1.0 / len(targets) if targets else 0
    budget_used = 0  # TS 매도 후 남은 투자금 재계산
    for code, pos in ledger.get('positions', {}).items():
        if int(pos.get('qty', 0)) > 0:
             budget_used += int(pos.get('qty', 0)) * KisKR.GetCurrentPrice(code)

    buy_count = 0
    
    # 우선 기존 보유 중 아닌 ETF는 매수, 보유 중인데 대상에서 빠지면 매도(단순화)
    target_codes = {c for c, _ in targets}

    # 매도: 보유 중이지만 대상에 포함되지 않은 코드 전량 매도
    # (TS로 이미 매도된 종목은 제외)
    for held_code, pos in list(ledger.get('positions', {}).items()):
        if int(pos.get('qty', 0)) > 0 and held_code not in target_codes and held_code not in pruned_by_ts:
            qty = int(pos.get('qty', 0))
            try:
                data = KisKR.MakeSellMarketOrder(held_code, qty)
            except Exception:
                data = None
            approx_px = float(KisKR.GetCurrentPrice(held_code))
            pnl = (approx_px - float(pos.get('avg', 0.0))) * qty
            pos['qty'] = 0
            pos['avg'] = 0.0
            ledger['positions'][held_code] = pos
            ledger['realized_profit'] = float(ledger.get('realized_profit', 0.0)) + pnl
            
            save_positions(ledger)
            record_trade(current_date, 'SELL', held_code, qty, approx_px, pnl)
            try:
                display_name = get_name(held_code)
                msg = format_kis_order_message(PortfolioName, '매도', display_name, data, order_px=approx_px)
                icon = '🟢' if pnl > 0 else ('🔴' if pnl < 0 else '⚪')
                reason = '리밸런싱 제외 대상'
                telegram.send(f"{icon} {msg}\n이유: {reason}")
            except Exception:
                pass
            sell_count += 1

    # 매수/보유 리밸런싱(균등 목표 + 역방향 사이징)
    for code, name in targets:
        # 시가 진입 옵션 확인
        market = None
        for m, sides in ASSETS.items():
            if code in sides.values():
                market = m
                break
        
        entry_at_open = best_params.get(market, {}).get('entry_at_open', False) if market else False
        
        if entry_at_open:
            # 시가 진입: 시가 조회
            try:
                base = Common.GetUrlBase(Common.GetNowDist())
                path = "uapi/domestic-stock/v1/quotations/inquire-price"
                url = f"{base}/{path}"
                headers = {
                    "Content-Type": "application/json",
                    "authorization": f"Bearer {Common.GetToken(Common.GetNowDist())}",
                    "appKey": Common.GetAppKey(Common.GetNowDist()),
                    "appSecret": Common.GetAppSecret(Common.GetNowDist()),
                    "tr_id": "FHKST01010200",
                }
                params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
                import requests
                res = requests.get(url, headers=headers, params=params, timeout=3)
                if res.status_code == 200:
                    js = res.json()
                    if str(js.get('rt_cd')) == '0':
                        output = js.get('output', {}) or js.get('output1', {}) or {}
                        px = float(output.get('stck_oprc', 0))  # 시가
                        if px <= 0:
                            px = KisKR.GetCurrentPrice(code)  # 시가가 없으면 현재가
                    else:
                        px = KisKR.GetCurrentPrice(code)
                else:
                    px = KisKR.GetCurrentPrice(code)
            except Exception:
                px = KisKR.GetCurrentPrice(code)
        else:
            # 기존 방식: 현재가 × 1.01
            px = KisKR.GetCurrentPrice(code) * 1.01
            
        if px is None or px <= 0:
            continue
        
        desired_money = TotalMoney * unit_rate
        
        pos = ledger.get('positions', {}).get(code, {"qty": 0, "avg": 0.0})
        now_qty = int(pos.get('qty', 0))
        now_val = now_qty * px
        gap_money = desired_money - now_val
        qty = int(abs(gap_money) / px)
        if qty < 1:
            continue
        if gap_money > 0:
            # 매수
            need = qty * px
            if budget_used + need > TotalMoney:
                remain = TotalMoney - budget_used
                adj = int(remain / px)
                if adj < 1:
                    continue
                qty = adj
                need = qty * px
            if entry_at_open:
                # 시가 진입: 시장가 주문
                data = KisKR.MakeBuyMarketOrder(code, qty)
            else:
                # 기존 방식: 지정가 주문
                data = KisKR.MakeBuyLimitOrder(code, qty, px)
            try:
                msg = format_kis_order_message(PortfolioName, '매수', name, data, order_px=px)
                telegram.send(msg)
            except Exception:
                pass
            # 레저 업데이트 (구매중 상태로 설정)
            old_qty = now_qty
            old_avg = float(pos.get('avg', 0.0))
            new_qty = old_qty + qty
            new_avg = px if new_qty == 0 else ((old_avg * old_qty + px * qty) / max(1, new_qty))
            pos['qty'] = new_qty
            pos['avg'] = new_avg
            pos['status'] = '구매중'  # 매수 주문 후 구매중 상태
            pos['buy_date'] = current_date  # 구매중 날짜 기록
            pos['name'] = get_name(code)  # 종목명 설정
            # 'hi' 초기화 또는 업데이트
            pos['hi'] = px if old_qty == 0 else max(float(pos.get('hi', 0.0)), px)
            ledger['positions'][code] = pos
            save_positions(ledger)
            record_trade(current_date, 'BUY', code, qty, px, None)
            budget_used += need
            buy_count += 1
        else:
            # 매도(목표 이하로 과다 보유 시 일부 매도)
            sell_qty = qty
            try:
                data = KisKR.MakeSellMarketOrder(code, sell_qty)
            except Exception:
                data = None
            approx_px = float(KisKR.GetCurrentPrice(code))
            pnl = (approx_px - float(pos.get('avg', 0.0))) * sell_qty
            pos['qty'] = max(0, int(pos.get('qty', 0)) - sell_qty)
            if pos['qty'] == 0:
                pos['avg'] = 0.0
            ledger['positions'][code] = pos
            ledger['realized_profit'] = float(ledger.get('realized_profit', 0.0)) + pnl
            
            save_positions(ledger)
            record_trade(current_date, 'SELL', code, sell_qty, approx_px, pnl)
            try:
                display_name = get_name(held_code, fallback=name)
                msg = format_kis_order_message(PortfolioName, '매도', display_name, data, order_px=approx_px)
                icon = '🟢' if pnl > 0 else ('🔴' if pnl < 0 else '⚪')
                reason = '리밸런싱 비중 축소'
                telegram.send(f"{icon} {msg}\n이유: {reason}")
            except Exception:
                pass
            sell_count += 1

    prune_zero_positions(ledger)
    save_positions(ledger)

    # 요약 리포트 전송
    try:
        name_map = {}
        for code, name in targets:
            name_map[code] = name
            # code_name_map.py에 저장
            set_name(code, name)
        send_summary_report(
            PortfolioName,
            ledger,
            current_allocation=TotalMoney,
            initial_allocation=float(ledger.get('initial_allocation') or TotalMoney),
            name_map=name_map,
        )
    except Exception:
        pass

    if rebalance_period == 'weekly' and (buy_count > 0 or sell_count > 0):
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
        Common.sync_positions_with_wallet(PortfolioName)

        main()
    except Exception as e:
        logging.exception(f"{BOT_NAME} 실행 오류: {e}")
        telegram.send(f"{PortfolioName} 실행 오류: {e}")


