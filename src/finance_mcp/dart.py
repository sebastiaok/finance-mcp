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

from finance_mcp import _http

BASE = "https://opendart.fss.or.kr/api"
VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

# 사업보고서=11011, 반기=11012, 1분기=11013, 3분기=11014
REPRT_ANNUAL = "11011"
REPRT_QUARTERLY = {"q1": "11013", "half": "11012", "q3": "11014"}

# 분기 수치 해석 주의: DART 분기 재무의 당기(thstrm)는 사업연도 누적 기준일 수 있음.
_QUARTERLY_NOTE = "※ 분기 수치는 사업연도 누적 기준(당기=올해 누적 / 전기=전년 동기 누적)일 수 있음."

# 손익계산서에서 뽑을 핵심 계정 (연결 기준)
# 계정명은 공백을 제거해 비교한다(extract_financials). DART 표기: "법인세비용차감전순이익".
# 순이익은 보고서 종류에 따라 표기가 다름: 연간=당기순이익 / 분기=분기순이익 / 반기=반기순이익.
_KEY_ACCOUNTS = ["매출액", "영업이익", "법인세비용차감전순이익", "당기순이익", "분기순이익", "반기순이익"]


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
    resp = _http.get(f"{BASE}/corpCode.xml", params={"crtfc_key": _api_key()}, timeout=60)
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
    resp = _http.get(f"{BASE}/list.json", params=params, timeout=30)
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
            # 전기 비교값: 연간은 frmtrm_amount(전기), 분기·반기는 그게 비고 frmtrm_q_amount(전년 동기)에 담긴다.
            previous = item.get("frmtrm_amount") or item.get("frmtrm_q_amount") or ""
            rows.append(
                {
                    "account": item.get("account_nm", "").strip(),
                    "current": item.get("thstrm_amount", ""),
                    "previous": previous,
                    "period": item.get("thstrm_nm", ""),
                }
            )
    return rows


def _fetch_statement(corp_code: str, year: int, reprt_code: str) -> list[dict]:
    """단일 (사업연도, 보고서코드)의 핵심 손익 계정. 연결(CFS) 우선, 없으면 별도(OFS) 폴백.

    데이터 없음(status 013 등)이면 빈 리스트 — 호출부에서 다른 연도/분기로 폴백하기 좋게.
    """
    for fs_div in ("CFS", "OFS"):
        params = {
            "crtfc_key": _api_key(),
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": reprt_code,
            "fs_div": fs_div,
        }
        resp = _http.get(f"{BASE}/fnlttSinglAcntAll.json", params=params, timeout=30)
        resp.raise_for_status()
        rows = extract_financials(resp.json())
        if rows:
            return rows
    return []


def annual_financials(ticker: str, year: int | None = None) -> tuple[str, list[dict]]:
    """사업보고서 기준 연간 재무 요약. 연결(CFS) 우선, 없으면 별도(OFS) 폴백.

    Returns: (corp_name, rows)
    """
    corp = lookup_corp(ticker)
    if corp is None:
        raise ValueError(f"DART에서 티커를 찾을 수 없음: {ticker}")
    bsns_year = year or date.today().year - 1
    return corp["corp_name"], _fetch_statement(corp["corp_code"], bsns_year, REPRT_ANNUAL)


def _quarterly_candidates(today: date | None = None) -> list[tuple[int, str]]:
    """최신순 (사업연도, reprt_code) 후보. 공시 지연 대응으로 여러 개를 순차 probe한다.

    순수 함수(테스트 대상). 올해 3분기→반기→1분기, 없으면 작년 순으로 내려간다.
    """
    year = (today or date.today()).year
    codes = [REPRT_QUARTERLY["q3"], REPRT_QUARTERLY["half"], REPRT_QUARTERLY["q1"]]
    return [(yr, code) for yr in (year, year - 1) for code in codes]


def latest_quarterly(ticker: str) -> tuple[str, list[dict]]:
    """가장 최근 제출된 분기 재무를 찾아 반환. 연결(CFS) 우선.

    Returns: (corp_name, rows). 최신순 후보를 순차 조회해 데이터가 있는 첫 분기를 채택.
    """
    corp = lookup_corp(ticker)
    if corp is None:
        raise ValueError(f"DART에서 티커를 찾을 수 없음: {ticker}")
    for year, reprt_code in _quarterly_candidates():
        rows = _fetch_statement(corp["corp_code"], year, reprt_code)
        if rows:
            return corp["corp_name"], rows
    return corp["corp_name"], []


def format_disclosures(rows: list[dict], ticker: str) -> str:
    if not rows:
        return f"{ticker}: 조건에 맞는 공시 없음."
    lines = [f"[{ticker} 최근 공시 (DART)]"]
    lines += [f"- {r['date']} | {r['title']} | 제출: {r['submitter']} | {r['url']}" for r in rows]
    return "\n".join(lines)


def format_financials(corp_name: str, rows: list[dict], ticker: str, note: str = "") -> str:
    """연간·분기 공용 포맷터. 기간 라벨(rows[0]['period'], 예 "제 57 기 3분기")이 스스로 명시.

    note: 분기 조회 시 누적 기준 주의 문구 등을 헤더 아래 한 줄로 덧붙일 때 사용.
    """
    if not rows:
        return f"{ticker}({corp_name}): 재무제표 데이터 없음 — 보고서 미제출 기간일 수 있음."
    lines = [f"[{ticker} {corp_name} 재무 (DART, {rows[0]['period']})]"]
    if note:
        lines.append(note)
    for r in rows:
        lines.append(f"{r['account']}: 당기 {r['current']} / 전기 {r['previous']}")
    return "\n".join(lines)
