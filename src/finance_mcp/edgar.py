"""SEC EDGAR API 클라이언트.

- 티커 → CIK 매핑: https://www.sec.gov/files/company_tickers.json (모듈 캐시)
- 공시 목록: https://data.sec.gov/submissions/CIK{10자리}.json
- SEC는 식별 가능한 User-Agent를 요구한다.
"""

from __future__ import annotations

import os

import httpx

from finance_mcp import _http

USER_AGENT = os.environ.get(
    "FINANCE_MCP_USER_AGENT", "finance-mcp/0.1 (personal research; contact via GitHub)"
)
TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

_HEADERS = {"User-Agent": USER_AGENT}
_cik_cache: dict[str, str] = {}


def _http_get(url: str, timeout: int = 30) -> httpx.Response:
    """SEC용 GET (식별 User-Agent 포함). SSL 검증 토글은 _http에서 관리."""
    resp = _http.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp


def pad_cik(cik: int | str) -> str:
    """CIK를 EDGAR가 요구하는 10자리 zero-padded 문자열로 변환."""
    return str(cik).zfill(10)


def lookup_cik(ticker: str) -> str | None:
    """티커로 10자리 CIK 조회. 최초 1회만 네트워크 호출 후 캐시."""
    if not _cik_cache:
        resp = _http_get(TICKER_URL)
        for row in resp.json().values():
            _cik_cache[row["ticker"].upper()] = pad_cik(row["cik_str"])
    return _cik_cache.get(ticker.upper())


def extract_filings(
    submissions: dict, cik: str, form_type: str | None = None, limit: int = 10
) -> list[dict]:
    """submissions API 응답에서 공시 목록 추출 (순수 함수 — 테스트 대상).

    Returns: [{"form", "date", "title", "url"}, ...] 최신순.
    """
    recent = submissions["filings"]["recent"]
    rows: list[dict] = []
    for form, date, accession, doc, desc in zip(
        recent["form"],
        recent["filingDate"],
        recent["accessionNumber"],
        recent["primaryDocument"],
        recent.get("primaryDocDescription", [""] * len(recent["form"])),
    ):
        if form_type and form.upper() != form_type.upper():
            continue
        acc_nodash = accession.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nodash}/{doc}"
        rows.append({"form": form, "date": date, "title": desc or form, "url": url})
        if len(rows) >= limit:
            break
    return rows


def recent_filings(ticker: str, form_type: str | None = None, limit: int = 10) -> list[dict]:
    """티커의 최근 SEC 공시 목록."""
    cik = lookup_cik(ticker)
    if cik is None:
        raise ValueError(f"미국 시장에서 티커를 찾을 수 없음: {ticker}")
    resp = _http_get(SUBMISSIONS_URL.format(cik=cik))
    return extract_filings(resp.json(), cik, form_type, limit)
