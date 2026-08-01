"""DART OpenAPI 클라이언트 (한국 공시·재무제표).

- API 키: 환경변수 DART_API_KEY (https://opendart.fss.or.kr 무료 발급)
- DART는 티커가 아닌 8자리 corp_code를 사용한다.
  corpCode.xml(zip)을 1회 다운로드해 {티커: corp_code} 매핑을 로컬 파일에 캐시한다.
  → EDGAR의 티커→CIK 캐시(edgar.py)와 동일한 문제·동일한 패턴.
- 순수 함수(parse_*, extract_*)와 네트워크 함수(fetch_*, recent_*)를 분리한다.
"""

from __future__ import annotations

import io
import json
import os
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, timedelta
from pathlib import Path

import httpx

BASE = "https://opendart.fss.or.kr/api"
VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

# 사업보고서=11011, 반기=11012, 1분기=11013, 3분기=11014
REPRT_ANNUAL = "11011"

# 손익계산서에서 뽑을 핵심 계정 (연결 기준)
# 계정명은 공백을 제거해 비교한다(extract_financials). DART 표기: "법인세비용차감전순이익".
_KEY_ACCOUNTS = ["매출액", "영업이익", "법인세비용차감전순이익", "당기순이익"]


def _cache_path() -> Path:
    base = os.environ.get("FINANCE_MCP_CACHE") or (Path.home() / ".cache" / "finance-mcp")
    return Path(base) / "corp_codes.json"


def _api_key() -> str:
    key = os.environ.get("DART_API_KEY")
    if not key:
        raise RuntimeError(
            "DART_API_KEY 환경변수가 필요합니다. https://opendart.fss.or.kr 에서 무료 발급."
        )
    return key


def parse_corp_codes(xml_bytes: bytes) -> dict[str, dict]:
    """CORPCODE.xml에서 {티커(6자리): {corp_code, corp_name}} 매핑 추출 (순수 함수).

    상장사만 남긴다 (stock_code가 있는 항목).
    """
    root = ET.fromstring(xml_bytes)
    out: dict[str, dict] = {}
    for el in root.iter("list"):
        stock_code = (el.findtext("stock_code") or "").strip()
        if stock_code:
            out[stock_code] = {
                "corp_code": (el.findtext("corp_code") or "").strip(),
                "corp_name": (el.findtext("corp_name") or "").strip(),
            }
    return out


def load_corp_codes(force_refresh: bool = False) -> dict[str, dict]:
    """티커→corp_code 매핑. 캐시 파일 우선, 없으면 다운로드 후 저장."""
    cache = _cache_path()
    if cache.exists() and not force_refresh:
        return json.loads(cache.read_text(encoding="utf-8"))
    resp = httpx.get(f"{BASE}/corpCode.xml", params={"crtfc_key": _api_key()}, timeout=60)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml_bytes = zf.read(zf.namelist()[0])
    mapping = parse_corp_codes(xml_bytes)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
    return mapping


def lookup_corp(ticker: str) -> dict | None:
    """6자리 티커(예: 005930)로 corp_code 조회."""
    return load_corp_codes().get(ticker.zfill(6))


def extract_disclosures(payload: dict, limit: int = 10) -> list[dict]:
    """list.json 응답에서 공시 목록 추출 (순수 함수 — 테스트 대상).

    status != "000"이면 빈 리스트 (013 = 조회 결과 없음).
    """
    if payload.get("status") != "000":
        return []
    rows = []
    for item in payload.get("list", [])[:limit]:
        rows.append(
            {
                "date": item.get("rcept_dt", ""),
                "title": item.get("report_nm", ""),
                "submitter": item.get("flr_nm", ""),
                "url": VIEWER.format(rcept_no=item.get("rcept_no", "")),
            }
        )
    return rows


def recent_disclosures(ticker: str, limit: int = 10, days: int = 365) -> list[dict]:
    """최근 N일간 공시 목록."""
    corp = lookup_corp(ticker)
    if corp is None:
        raise ValueError(f"DART에서 티커를 찾을 수 없음: {ticker} (6자리 종목코드 필요)")
    today = date.today()
    params = {
        "crtfc_key": _api_key(),
        "corp_code": corp["corp_code"],
        "bgn_de": (today - timedelta(days=days)).strftime("%Y%m%d"),
        "end_de": today.strftime("%Y%m%d"),
        "page_count": str(min(max(limit, 1), 100)),
    }
    resp = httpx.get(f"{BASE}/list.json", params=params, timeout=30)
    resp.raise_for_status()
    return extract_disclosures(resp.json(), limit)


def extract_financials(payload: dict) -> list[dict]:
    """fnlttSinglAcntAll.json 응답에서 핵심 손익 계정 추출 (순수 함수).

    sj_div가 IS(손익계산서) 또는 CIS(포괄손익계산서)인 항목 중
    _KEY_ACCOUNTS에 해당하는 계정만 반환. 계정명은 공백 차이가 있어 정규화 후 비교.
    """
    if payload.get("status") != "000":
        return []
    wanted = {a.replace(" ", "") for a in _KEY_ACCOUNTS}
    rows = []
    seen: set[str] = set()
    for item in payload.get("list", []):
        if item.get("sj_div") not in ("IS", "CIS"):
            continue
        name = (item.get("account_nm") or "").replace(" ", "")
        if name in wanted and name not in seen:
            seen.add(name)
            rows.append(
                {
                    "account": item.get("account_nm", "").strip(),
                    "current": item.get("thstrm_amount", ""),
                    "previous": item.get("frmtrm_amount", ""),
                    "period": item.get("thstrm_nm", ""),
                }
            )
    return rows


def annual_financials(ticker: str, year: int | None = None) -> tuple[str, list[dict]]:
    """사업보고서 기준 연간 재무 요약. 연결(CFS) 우선, 없으면 별도(OFS) 폴백.

    Returns: (corp_name, rows)
    """
    corp = lookup_corp(ticker)
    if corp is None:
        raise ValueError(f"DART에서 티커를 찾을 수 없음: {ticker}")
    bsns_year = year or date.today().year - 1
    for fs_div in ("CFS", "OFS"):
        params = {
            "crtfc_key": _api_key(),
            "corp_code": corp["corp_code"],
            "bsns_year": str(bsns_year),
            "reprt_code": REPRT_ANNUAL,
            "fs_div": fs_div,
        }
        resp = httpx.get(f"{BASE}/fnlttSinglAcntAll.json", params=params, timeout=30)
        resp.raise_for_status()
        rows = extract_financials(resp.json())
        if rows:
            return corp["corp_name"], rows
    return corp["corp_name"], []


def format_disclosures(rows: list[dict], ticker: str) -> str:
    if not rows:
        return f"{ticker}: 조건에 맞는 공시 없음."
    lines = [f"[{ticker} 최근 공시 (DART)]"]
    lines += [f"- {r['date']} | {r['title']} | 제출: {r['submitter']} | {r['url']}" for r in rows]
    return "\n".join(lines)


def format_financials(corp_name: str, rows: list[dict], ticker: str) -> str:
    if not rows:
        return f"{ticker}({corp_name}): 재무제표 데이터 없음 — 사업보고서 미제출 연도일 수 있음."
    lines = [f"[{ticker} {corp_name} 연간 재무 (DART, {rows[0]['period']})]"]
    for r in rows:
        lines.append(f"{r['account']}: 당기 {r['current']} / 전기 {r['previous']}")
    return "\n".join(lines)
