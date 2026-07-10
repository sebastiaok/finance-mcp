# finance-mcp

US/KR 주식 포트폴리오 리서치용 MCP 서버 (FastMCP, Python). 학습용 사이드 프로젝트.

## 도구

| 이름 | 설명 |
|---|---|
| `get_quote(ticker, market)` | 현재가·밸류에이션 요약 (yfinance) |
| `get_financials(ticker, market)` | 매출·마진·현금흐름·부채 요약 |
| `get_filings(ticker, form_type, limit, market)` | SEC 공시 목록 + 원문 URL |
| `get_news(ticker, limit)` | 최근 뉴스 헤드라인 |
| `portfolio://holdings` (리소스) | 보유 종목 목록 (portfolio.json) |

KR(DART·pykrx)은 2주차 확장 예정 — `market="KR"` 파라미터 자리만 잡아둔 상태.

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
