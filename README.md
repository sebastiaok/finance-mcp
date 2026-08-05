# finance-mcp

US/KR 주식 포트폴리오 리서치용 MCP 서버 (FastMCP, Python). 학습용 사이드 프로젝트.

> 이 서버를 도구로 쓰는 상위 프로젝트: [earnings-agent](https://github.com/sebastiaok/earnings-agent) —
> 이 서버를 붙인 멀티 에이전트로 단일 vs 팀 실적 리포트를 LLM-as-judge로 정량 비교(팀이 3종목 전부 우세, 차이는 강세/약세 균형 축).

## 도구

| 이름 | 설명 |
|---|---|
| `get_quote(ticker, market)` | 현재가·밸류에이션 요약 (yfinance) |
| `get_financials(ticker, market, period)` | 재무 요약. `period="annual"`(기본) / `period="quarterly"`(최근 분기·YoY) |
| `get_filings(ticker, form_type, limit, market)` | SEC 공시 목록 + 원문 URL |
| `get_news(ticker, limit)` | 최근 뉴스 헤드라인 |
| `portfolio://holdings` (리소스) | 보유 종목 목록 (portfolio.json) |

`market="US"`(기본, yfinance·SEC EDGAR) / `market="KR"`(DART·pykrx) 분기.

**분기 실적 (`get_financials(..., period="quarterly")`)** — 어닝 서프라이즈·YoY 확인용:
- US: `quarterly_income_stmt`에서 최근 5개 분기 손익(매출·매출총이익·영업이익·순이익·희석EPS)을 최신순 시계열로 반환. 같은 항목을 4행 아래(=전년 동기)와 비교하면 YoY가 보인다.
- KR: DART 최신 분기보고서(3분기 11014 → 반기 11012 → 1분기 11013 순으로 자동 탐색)의 4계정을 당기/전기(=전년 동기)로 반환. **분기 수치는 사업연도 누적 기준**일 수 있어 그 주의 문구를 함께 출력한다. (분기 순이익 계정은 DART에서 `분기순이익`/`반기순이익`으로 표기됨.)

**KR (6자리 종목코드, 예: `005930`)** — 2주차 실호출 검증 완료:
- `get_filings` / `get_financials` → DART OpenAPI (`DART_API_KEY` 필요). 최초 1회 corp_code 매핑을 다운로드해 캐시한다.
- `get_quote` → pykrx. 종가·거래량은 정상. **PER/PBR/EPS/BPS·시가총액은 KRX가 로그인(KRX_ID/KRX_PW)을 요구하도록 바뀌어 현재 조용히 생략됨** — 시세 조회 자체는 동작.

## 설치·실행

```bash
uv sync
uv run pytest              # 단위 테스트 (네트워크 불필요)
uv run finance-mcp         # stdio 서버 실행
```

MCP Inspector로 도구 직접 테스트:

```bash
uv run fastmcp dev src/finance_mcp/server.py
```

## Claude Desktop 연결

`claude_desktop_config.json`에 추가:

```json
{
  "mcpServers": {
    "finance-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "<이 폴더의 절대경로>", "finance-mcp"]
    }
  }
}
```

연결 후 확인: "AAPL 최근 10-Q 찾아서 요약해줘" → get_filings가 호출되면 성공.

## 설정

- `portfolio.json` — 보유 종목 (샘플 포함, 본인 것으로 교체)
- `FINANCE_MCP_PORTFOLIO` — portfolio.json 경로 오버라이드
- `FINANCE_MCP_USER_AGENT` — SEC 요청용 User-Agent (이메일 포함 권장)
- `FINANCE_MCP_NO_VERIFY` — `1`로 설정하면 SSL 검증 비활성화 (회사 프록시 등 자체 서명 인증서 환경용)
- `DART_API_KEY` — KR 공시·재무 조회용 DART OpenAPI 키 (https://opendart.fss.or.kr 무료 발급)
- `FINANCE_MCP_CACHE` — corp_code 매핑 캐시 경로 오버라이드 (기본 `~/.cache/finance-mcp`)
