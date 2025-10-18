# -*- coding: utf-8 -*-
"""
공용 코드↔이름 매핑 유틸

- 저장 위치: kook/code_name_map.json (전략 간 공유)
- 기능: 캐시 로드/저장, 코드명 미존재 시 KIS API로 조회 후 캐시 반영
"""

import os
import json

# KIS 헬퍼 임포트(전략들과 동일한 경로 해킹을 가정)
try:
    import KIS_API_Helper_KR as KisKR  # kook/ 아래에서 import됨
except Exception:
    KisKR = None


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_MAP_FILE = os.path.join(_BASE_DIR, "code_name_map.json")


def _load() -> dict:
    try:
        if os.path.exists(_MAP_FILE):
            with open(_MAP_FILE, 'r', encoding='utf-8') as f:
                m = json.load(f)
                if isinstance(m, dict):
                    return m
    except Exception:
        pass
    return {}


def _save(m: dict) -> None:
    try:
        with open(_MAP_FILE, 'w', encoding='utf-8') as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_name(code: str, fallback: str | None = None) -> str:
    """코드의 표시명을 반환. 없으면 통신으로 조회 후 캐시에 저장.
    fallback이 제공되면 조회 실패 시 fallback 사용.
    """
    m = _load()
    name = m.get(code)
    if name:
        return name
    # 통신으로 조회
    try:
        if KisKR is not None:
            fetched = KisKR.GetStockName(code)
            if fetched:
                m[code] = fetched
                _save(m)
                return fetched
    except Exception:
        pass
    # 폴백
    name = fallback or code
    try:
        m[code] = name
        _save(m)
    except Exception:
        pass
    return name


def set_name(code: str, name: str) -> None:
    """외부에서 이름을 알 경우 캐시에 저장."""
    try:
        m = _load()
        if not name:
            return
        if m.get(code) != name:
            m[code] = name
            _save(m)
    except Exception:
        pass


