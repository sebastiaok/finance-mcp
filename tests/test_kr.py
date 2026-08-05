"""2주차 KR 모듈 단위 테스트 (네트워크·API 키 불필요)."""

from finance_mcp import dart, krx

SAMPLE_CORPCODE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<result>
  <list>
    <corp_code>00126380</corp_code>
    <corp_name>\xec\x82\xbc\xec\x84\xb1\xec\xa0\x84\xec\x9e\x90</corp_name>
    <stock_code>005930</stock_code>
    <modify_date>20260101</modify_date>
  </list>
  <list>
    <corp_code>00999999</corp_code>
    <corp_name>\xeb\xb9\x84\xec\x83\x81\xec\x9e\xa5\xed\x9a\x8c\xec\x82\xac</corp_name>
    <stock_code> </stock_code>
    <modify_date>20260101</modify_date>
  </list>
</result>"""


def test_parse_corp_codes_listed_only():
    mapping = dart.parse_corp_codes(SAMPLE_CORPCODE_XML)
    assert "005930" in mapping
    assert mapping["005930"]["corp_code"] == "00126380"
    assert len(mapping) == 1  # 비상장사(stock_code 공백)는 제외


def test_extract_disclosures():
    payload = {
        "status": "000",
        "list": [
            {"rcept_dt": "20260630", "report_nm": "반기보고서", "flr_nm": "삼성전자", "rcept_no": "20260630000001"},
            {"rcept_dt": "20260501", "report_nm": "주요사항보고서", "flr_nm": "삼성전자", "rcept_no": "20260501000002"},
        ],
    }
    rows = dart.extract_disclosures(payload, limit=1)
    assert len(rows) == 1
    assert rows[0]["title"] == "반기보고서"
    assert "rcpNo=20260630000001" in rows[0]["url"]


def test_extract_disclosures_no_result():
    assert dart.extract_disclosures({"status": "013", "message": "조회된 데이타가 없습니다."}) == []


def test_extract_financials_filters_and_dedupes():
    payload = {
        "status": "000",
        "list": [
            {"sj_div": "BS", "account_nm": "자산총계", "thstrm_amount": "1"},
            {"sj_div": "IS", "account_nm": "매출액", "thstrm_amount": "300", "frmtrm_amount": "280", "thstrm_nm": "제57기"},
            {"sj_div": "IS", "account_nm": "영업이익", "thstrm_amount": "50", "frmtrm_amount": "40", "thstrm_nm": "제57기"},
            {"sj_div": "CIS", "account_nm": "매출액", "thstrm_amount": "999"},
            {"sj_div": "IS", "account_nm": "당기순이익", "thstrm_amount": "35", "frmtrm_amount": "30", "thstrm_nm": "제57기"},
        ],
    }
    rows = dart.extract_financials(payload)
    accounts = [r["account"] for r in rows]
    assert accounts == ["매출액", "영업이익", "당기순이익"]  # BS 제외, 중복 매출액 1회만
    assert rows[0]["current"] == "300"


def test_extract_financials_quarterly_fields():
    """분기 리포트: frmtrm_amount는 비고 frmtrm_q_amount(전년동기)에 비교값, 순이익은 '분기순이익' 표기."""
    payload = {
        "status": "000",
        "list": [
            {"sj_div": "IS", "account_nm": "매출액", "thstrm_amount": "133", "frmtrm_amount": "",
             "frmtrm_q_amount": "79", "thstrm_nm": "제 58 기 1분기"},
            {"sj_div": "IS", "account_nm": "분기순이익", "thstrm_amount": "47", "frmtrm_amount": "",
             "frmtrm_q_amount": "8", "thstrm_nm": "제 58 기 1분기"},
            {"sj_div": "CIS", "account_nm": "분기순이익", "thstrm_amount": "47", "frmtrm_q_amount": "8"},  # 중복 → 제외
        ],
    }
    rows = dart.extract_financials(payload)
    accounts = [r["account"] for r in rows]
    assert accounts == ["매출액", "분기순이익"]  # 분기순이익 매칭됨, CIS 중복 제외
    assert rows[0]["previous"] == "79"  # frmtrm 비었으면 frmtrm_q로 폴백
    assert rows[1]["account"] == "분기순이익"


def test_format_financials_empty():
    out = dart.format_financials("삼성전자", [], "005930")
    assert "데이터 없음" in out


def test_format_financials_quarterly_label_and_note():
    rows = [
        {"account": "매출액", "current": "790000", "previous": "740000", "period": "제 57 기 3분기"},
        {"account": "영업이익", "current": "90000", "previous": "83000", "period": "제 57 기 3분기"},
    ]
    out = dart.format_financials("삼성전자", rows, "005930", note=dart._QUARTERLY_NOTE)
    assert "제 57 기 3분기" in out  # 기간 라벨이 헤더에 그대로 노출
    assert "누적 기준" in out  # 분기 누적 주의 문구
    assert "매출액: 당기 790000 / 전기 740000" in out


def test_reprt_quarterly_codes():
    assert dart.REPRT_QUARTERLY == {"q1": "11013", "half": "11012", "q3": "11014"}


def test_quarterly_candidates_order():
    from datetime import date

    cands = dart._quarterly_candidates(date(2026, 8, 5))
    # 올해(2026) 3분기→반기→1분기 먼저, 그다음 작년(2025) 순
    assert cands[0] == (2026, "11014")
    assert cands[2] == (2026, "11013")
    assert cands[3] == (2025, "11014")
    assert len(cands) == 6


def test_format_quote_kr():
    out = krx.format_quote_kr(
        "005930",
        "삼성전자",
        {"종가": 72500, "거래량": 12345678},
        {"PER": 13.5, "PBR": 1.2, "DIV": 2.1},
        432_000_000_000_000,
        "2026-07-03",
    )
    assert out.startswith("[005930 삼성전자]")
    assert "종가: 72,500" in out
    assert "PER: 13.5" in out


def test_format_quote_kr_empty():
    out = krx.format_quote_kr("000000", "", {}, {}, None, "-")
    assert "데이터 없음" in out
