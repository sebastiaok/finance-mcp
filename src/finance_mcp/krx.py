"""한국 시세 (pykrx 래퍼).

pykrx는 KRX 웹을 스크래핑하므로 느리고 깨질 수 있다 → 함수 안에서 lazy import
(서버 기동·테스트가 pykrx 설치 여부에 의존하지 않도록).

알려진 제약(2026-08 검증): OHLCV(종가·거래량)는 무인증 조회 가능하나,
get_market_fundamental_by_date(PER/PBR/EPS/BPS)·get_market_cap_by_date(시가총액)는
KRX가 로그인(KRX_ID/KRX_PW)을 요구하도록 바뀌어 무인증 시 빈 DataFrame으로 실패한다.
fetch_quote_kr은 이를 graceful하게 처리(빈 값 생략)하고 종가·거래량은 정상 반환한다.
"""

from __future__ import annotations

from datetime import date, timedelta


def format_quote_kr(
    ticker: str,
    name: str,
    ohlcv_row: dict,
    fundamental_row: dict,
    market_cap: float | None,
    as_of: str,
) -> str:
    """순수 포맷터 — 테스트 대상."""
    lines = [f"[{ticker} {name}] (기준일 {as_of})"]
    if ohlcv_row:
        lines.append(f"종가: {ohlcv_row.get('종가', '?'):,}")
        lines.append(f"거래량: {ohlcv_row.get('거래량', '?'):,}")
    if market_cap:
        lines.append(f"시가총액: {market_cap:,.0f}")
    for key, label in [("PER", "PER"), ("PBR", "PBR"), ("DIV", "배당수익률(%)"), ("EPS", "EPS"), ("BPS", "BPS")]:
        value = fundamental_row.get(key)
        if value is not None:
            lines.append(f"{label}: {value}")
    if len(lines) == 1:
        lines.append("데이터 없음 — 6자리 종목코드를 확인하세요.")
    return "\n".join(lines)


def fetch_quote_kr(ticker: str) -> str:
    """최근 영업일 기준 시세·밸류에이션. ticker는 6자리 종목코드 (예: 005930)."""
    from pykrx import stock  # lazy import

    ticker = ticker.zfill(6)
    today = date.today()
    start = (today - timedelta(days=14)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")

    name = stock.get_market_ticker_name(ticker)
    ohlcv = stock.get_market_ohlcv_by_date(start, end, ticker)
    fund = stock.get_market_fundamental_by_date(start, end, ticker)
    cap = stock.get_market_cap_by_date(start, end, ticker)

    if ohlcv.empty:
        return f"{ticker}: 시세 데이터 없음 — 종목코드를 확인하세요."

    as_of = ohlcv.index[-1].strftime("%Y-%m-%d")
    ohlcv_row = ohlcv.iloc[-1].to_dict()
    fund_row = fund.iloc[-1].to_dict() if not fund.empty else {}
    market_cap = float(cap.iloc[-1]["시가총액"]) if not cap.empty else None
    return format_quote_kr(ticker, name, ohlcv_row, fund_row, market_cap, as_of)
