"""yfinance 래퍼 + 포맷터.

네트워크 호출(fetch_*)과 포맷팅(format_*)을 분리한다.
포맷터는 순수 함수라 네트워크 없이 테스트 가능.
에이전트가 읽기 좋게 key: value 라인 형식으로 출력한다.
"""

from __future__ import annotations

import yfinance as yf

from finance_mcp import _http


def _make_ticker(ticker: str) -> yf.Ticker:
    """yfinance Ticker를 생성. 회사 프록시 등 SSL 문제 시 FINANCE_MCP_NO_VERIFY=1."""
    if _http.NO_VERIFY:
        from curl_cffi.requests import Session
        return yf.Ticker(ticker, session=Session(verify=False, impersonate="chrome"))
    return yf.Ticker(ticker)

_QUOTE_FIELDS = [
    ("longName", "종목명"),
    ("currentPrice", "현재가"),
    ("currency", "통화"),
    ("marketCap", "시가총액"),
    ("trailingPE", "PER(TTM)"),
    ("forwardPE", "PER(fwd)"),
    ("priceToBook", "PBR"),
    ("dividendYield", "배당수익률"),
    ("fiftyTwoWeekLow", "52주 최저"),
    ("fiftyTwoWeekHigh", "52주 최고"),
    ("recommendationKey", "애널리스트 컨센서스"),
]

_FIN_FIELDS = [
    ("totalRevenue", "매출(TTM)"),
    ("revenueGrowth", "매출 성장률(YoY)"),
    ("grossMargins", "매출총이익률"),
    ("operatingMargins", "영업이익률"),
    ("profitMargins", "순이익률"),
    ("freeCashflow", "잉여현금흐름"),
    ("totalCash", "현금성 자산"),
    ("totalDebt", "총부채"),
    ("returnOnEquity", "ROE"),
]

# 분기 손익계산서(quarterly_income_stmt)에서 뽑을 행 (yfinance 인덱스 라벨 → 한글)
_QFIN_ROWS = [
    ("Total Revenue", "매출"),
    ("Gross Profit", "매출총이익"),
    ("Operating Income", "영업이익"),
    ("Net Income", "순이익"),
    ("Diluted EPS", "희석EPS"),
]


def _fmt_num(value: object) -> str:
    if isinstance(value, (int, float)) and abs(value) >= 1_000_000:
        return f"{value:,.0f}"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def format_fields(info: dict, fields: list[tuple[str, str]], ticker: str) -> str:
    lines = [f"[{ticker.upper()}]"]
    for key, label in fields:
        value = info.get(key)
        if value is not None:
            lines.append(f"{label}: {_fmt_num(value)}")
    if len(lines) == 1:
        lines.append("데이터 없음 — 티커를 확인하세요.")
    return "\n".join(lines)


def extract_quarterly(stmt: object, n: int = 5) -> list[dict]:
    """quarterly_income_stmt(DataFrame)에서 최근 n개 분기 × 핵심 행을 plain 레코드로 추출.

    stmt: yfinance DataFrame (컬럼=분기말 Timestamp 최신순, 인덱스=계정명 영문 라벨).
    None/빈 DataFrame이면 빈 리스트. pandas 의존은 이 함수 안에 가둔다(포맷터는 순수).
    반환: [{"period": "2026-06-30", "매출": 109417000000.0, ...}, ...] (최신 분기 먼저)
    """
    if stmt is None or getattr(stmt, "empty", True):
        return []
    records = []
    for col in list(stmt.columns)[:n]:
        period = col.date().isoformat() if hasattr(col, "date") else str(col)
        rec: dict = {"period": period}
        for key, label in _QFIN_ROWS:
            if key in stmt.index:
                val = stmt.loc[key, col]
                if val is not None and val == val:  # NaN(val != val) 제외
                    rec[label] = float(val)
        records.append(rec)
    return records


def format_quarterly(records: list[dict], ticker: str) -> str:
    """분기 레코드를 에이전트가 읽기 좋은 라인 형식으로 포맷 (순수 함수).

    최신순으로 나열하므로 같은 항목을 위→아래로 훑으면 전분기·전년동기(4분기 전) 흐름이 보인다.
    """
    if not records:
        return f"[{ticker.upper()}] 분기 재무 데이터 없음 — 티커를 확인하세요."
    lines = [f"[{ticker.upper()} 분기 재무 (yfinance 손익, 최근 {len(records)}개 분기 · 최신순)]"]
    for rec in records:
        vals = [f"{k} {_fmt_num(v)}" for k, v in rec.items() if k != "period"]
        body = " | ".join(vals) if vals else "데이터 없음"
        lines.append(f"- {rec['period']}: {body}")
    return "\n".join(lines)


def format_news(items: list[dict], ticker: str) -> str:
    lines = [f"[{ticker.upper()} 최근 뉴스]"]
    for item in items:
        content = item.get("content", item)  # yfinance 버전에 따라 구조가 다름
        title = content.get("title", "(제목 없음)")
        pub = content.get("pubDate") or content.get("providerPublishTime", "")
        url = (content.get("canonicalUrl") or {}).get("url") or content.get("link", "")
        lines.append(f"- {pub} | {title} | {url}")
    if len(lines) == 1:
        lines.append("뉴스 없음.")
    return "\n".join(lines)


def fetch_quote(ticker: str) -> str:
    info = _make_ticker(ticker).info or {}
    return format_fields(info, _QUOTE_FIELDS, ticker)


def fetch_financials(ticker: str) -> str:
    info = _make_ticker(ticker).info or {}
    return format_fields(info, _FIN_FIELDS, ticker)


def fetch_financials_quarterly(ticker: str, quarters: int = 5) -> str:
    stmt = _make_ticker(ticker).quarterly_income_stmt
    return format_quarterly(extract_quarterly(stmt, quarters), ticker)


def fetch_news(ticker: str, limit: int = 8) -> str:
    items = (_make_ticker(ticker).news or [])[:limit]
    return format_news(items, ticker)
