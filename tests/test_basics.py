"""네트워크 없이 도는 단위 테스트 (순수 함수만 검증)."""

import json

from finance_mcp import _http, edgar, market_data, portfolio


def test_http_get_honors_no_verify(monkeypatch):
    """_http.get이 NO_VERIFY 값에 따라 verify를 정확히 넘기는지 (DART SSL 버그 회귀 방지)."""
    captured = {}

    def fake_get(url, **kwargs):
        captured.clear()
        captured.update(kwargs)
        captured["url"] = url

        class _Resp:
            def raise_for_status(self):
                pass

        return _Resp()

    monkeypatch.setattr(_http.httpx, "get", fake_get)

    monkeypatch.setattr(_http, "NO_VERIFY", True)
    _http.get("https://x", params={"a": 1})
    assert captured["verify"] is False  # NO_VERIFY=참 → 검증 끔

    monkeypatch.setattr(_http, "NO_VERIFY", False)
    _http.get("https://x")
    assert captured["verify"] is True  # 기본 → 검증 켬


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


def test_format_quarterly():
    records = [
        {"period": "2026-06-30", "매출": 109_417_000_000.0, "영업이익": 35_695_000_000.0, "희석EPS": 2.02},
        {"period": "2026-03-31", "매출": 111_184_000_000.0, "희석EPS": 2.01},
    ]
    out = market_data.format_quarterly(records, "aapl")
    assert out.startswith("[AAPL 분기 재무")
    assert "최근 2개 분기" in out
    assert "- 2026-06-30:" in out
    assert "매출 109,417,000,000" in out  # ≥1e6 → 콤마 포맷
    assert "희석EPS 2.02" in out  # 소수 → %.4g


def test_format_quarterly_empty():
    out = market_data.format_quarterly([], "ZZZZ")
    assert "분기 재무 데이터 없음" in out


def test_extract_quarterly():
    import pandas as pd

    cols = [pd.Timestamp("2026-06-30"), pd.Timestamp("2026-03-31"), pd.Timestamp("2025-12-31")]
    df = pd.DataFrame(
        {
            cols[0]: [109_417_000_000.0, 35_695_000_000.0, 2.02],
            cols[1]: [111_184_000_000.0, 35_885_000_000.0, float("nan")],  # EPS 결측
            cols[2]: [143_756_000_000.0, 50_852_000_000.0, 2.84],
        },
        index=["Total Revenue", "Operating Income", "Diluted EPS"],
    )
    recs = market_data.extract_quarterly(df, n=2)
    assert len(recs) == 2  # 최근 2개 분기만
    assert recs[0]["period"] == "2026-06-30"
    assert recs[0]["매출"] == 109_417_000_000.0
    assert recs[0]["희석EPS"] == 2.02
    assert "희석EPS" not in recs[1]  # NaN은 제외


def test_extract_quarterly_empty():
    assert market_data.extract_quarterly(None) == []


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
