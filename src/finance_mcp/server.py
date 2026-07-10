"""finance-mcp 서버 엔트리포인트.

실행: `finance-mcp` 또는 `python -m finance_mcp.server` (stdio 트랜스포트)

도구 스키마 설계 원칙:
- docstring과 파라미터 설명이 곧 에이전트의 도구 선택 성능을 좌우한다.
- market 파라미터로 US/KR 분기. KR 재무·공시는 DART_API_KEY 환경변수 필요.
"""

from __future__ import annotations

from fastmcp import FastMCP

from finance_mcp import dart, edgar, krx, market_data, portfolio

mcp = FastMCP(
    "finance-mcp",
    instructions=(
        "미국/한국 주식 리서치 도구 모음. 시세·재무 요약은 get_quote/get_financials, "
        "공시 원문이 필요하면 get_filings, 최근 이슈는 get_news를 사용하라. "
        "사용자 보유 종목은 portfolio://holdings 리소스에 있다. "
        "투자 조언이 아닌 사실 수집·분석 목적의 도구다."
    ),
)


@mcp.tool()
def get_quote(ticker: str, market: str = "US") -> str:
    """종목의 현재가와 밸류에이션 지표(PER, PBR, 시총, 52주 범위 등)를 요약한다.

    Args:
        ticker: 종목 티커 (US: AAPL / KR: 6자리 종목코드, 예 005930)
        market: "US"(yfinance) 또는 "KR"(KRX)
    """
    if market.upper() == "KR":
        return krx.fetch_quote_kr(ticker)
    return market_data.fetch_quote(ticker)


@mcp.tool()
def get_financials(ticker: str, market: str = "US") -> str:
    """종목의 핵심 재무 지표(매출·마진·현금흐름·부채·ROE)를 요약한다.

    Args:
        ticker: 종목 티커 (US: AAPL / KR: 6자리 종목코드, 예 005930)
        market: "US"(yfinance TTM) 또는 "KR"(DART 사업보고서 연간 — DART_API_KEY 필요)
    """
    if market.upper() == "KR":
        corp_name, rows = dart.annual_financials(ticker)
        return dart.format_financials(corp_name, rows, ticker)
    return market_data.fetch_financials(ticker)


@mcp.tool()
def get_filings(ticker: str, form_type: str = "", limit: int = 10, market: str = "US") -> str:
    """종목의 최근 공시 목록(종류, 날짜, 원문 URL)을 반환한다. US는 SEC EDGAR, KR은 DART.

    Args:
        ticker: 종목 티커 (US: AAPL / KR: 6자리 종목코드, 예 005930)
        form_type: US 전용 필터 (예: "10-K", "10-Q", "8-K"). 빈 문자열이면 전체.
        limit: 최대 건수 (기본 10)
        market: "US"(EDGAR) 또는 "KR"(DART — DART_API_KEY 필요)
    """
    if market.upper() == "KR":
        rows = dart.recent_disclosures(ticker, limit)
        return dart.format_disclosures(rows, ticker)
    rows = edgar.recent_filings(ticker, form_type or None, limit)
    if not rows:
        return f"{ticker.upper()}: 조건에 맞는 공시 없음."
    lines = [f"[{ticker.upper()} 최근 공시]"]
    lines += [f"- {r['date']} | {r['form']} | {r['title']} | {r['url']}" for r in rows]
    return "\n".join(lines)


@mcp.tool()
def get_news(ticker: str, limit: int = 8) -> str:
    """종목 관련 최근 뉴스 헤드라인과 링크를 반환한다.

    Args:
        ticker: 종목 티커. KR 종목은 야후 형식 접미사 포함 (예: 005930.KS, 코스닥은 .KQ)
        limit: 최대 건수 (기본 8)
    """
    return market_data.fetch_news(ticker, limit)


@mcp.resource("portfolio://holdings")
def holdings() -> str:
    """사용자의 보유 종목 목록 (티커, 시장, 수량, 평단, 메모)."""
    return portfolio.format_holdings(portfolio.load_holdings())


def main() -> None:
    mcp.run()  # 기본 stdio 트랜스포트


if __name__ == "__main__":
    main()
