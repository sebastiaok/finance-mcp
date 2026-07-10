"""네트워크 없이 도는 단위 테스트 (순수 함수만 검증)."""

import json

from finance_mcp import edgar, market_data, portfolio


def test_pad_cik():
    assert edgar.pad_cik(320193) == "0000320193"
    assert edgar.pad_cik("320193") == "0000320193"


def _fake_submissions():
    return {
        "filings": {
            "recent": {
                "form": ["8-K", "10-Q", "10-K", "4"],
                "filingDate": ["2026-07-01", "2026-05-02", "2025-11-01", "2025-10-15"],
                "accessionNumber": [
                    "0000320193-26-000010",
                    "0000320193-26-000008",
                    "0000320193-25-000106",
                    "0000320193-25-000100",
                ],
                "primaryDocument": ["a.htm", "b.htm", "c.htm", "d.xml"],
                "primaryDocDescription": ["8-K", "10-Q", "10-K", "FORM 4"],
            }
        }
    }


def test_extract_filings_all():
    rows = edgar.extract_filings(_fake_submissions(), "0000320193")
    assert len(rows) == 4
    assert rows[0]["form"] == "8-K"
    assert rows[0]["url"] == "https://www.sec.gov/Archives/edgar/data/320193/000032019326000010/a.htm"


def test_extract_filings_filter_and_limit():
    rows = edgar.extract_filings(_fake_submissions(), "0000320193", form_type="10-q")
    assert [r["form"] for r in rows] == ["10-Q"]
    rows = edgar.extract_filings(_fake_submissions(), "0000320193", limit=2)
    assert len(rows) == 2


def test_format_fields():
    info = {"longName": "Apple Inc.", "currentPrice": 231.5, "marketCap": 3_500_000_000_000}
    out = market_data.format_fields(info, market_data._QUOTE_FIELDS, "aapl")
    assert out.startswith("[AAPL]")
    assert "종목명: Apple Inc." in out
    assert "시가총액: 3,500,000,000,000" in out


def test_format_fields_empty():
    out = market_data.format_fields({}, market_data._QUOTE_FIELDS, "ZZZZ")
    assert "데이터 없음" in out


def test_format_news_both_shapes():
    new_shape = [{"content": {"title": "T1", "pubDate": "2026-07-01", "canonicalUrl": {"url": "http://x"}}}]
    old_shape = [{"title": "T2", "providerPublishTime": 1700000000, "link": "http://y"}]
    assert "T1" in market_data.format_news(new_shape, "AAPL")
    assert "T2" in market_data.format_news(old_shape, "AAPL")


def test_portfolio_load_and_format(tmp_path):
    p = tmp_path / "portfolio.json"
    p.write_text(json.dumps([{"ticker": "AAPL", "market": "US", "shares": 1, "avg_cost": 100}]), encoding="utf-8")
    holdings = portfolio.load_holdings(p)
    out = portfolio.format_holdings(holdings)
    assert "AAPL" in out


def test_portfolio_missing_file(tmp_path):
    assert portfolio.load_holdings(tmp_path / "nope.json") == []
    assert "비어 있음" in portfolio.format_holdings([])
