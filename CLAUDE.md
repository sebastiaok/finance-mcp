# finance-mcp — 클로드 작업 지시문

## 프로젝트 개요
US/KR 주식 리서치 MCP 서버. 학습 목적 사이드 프로젝트 (5주 로드맵의 1단계).
2단계에서 Claude Agent SDK 기반 어닝콜 멀티 에이전트가 이 서버를 도구로 사용한다.
문서(로드맵·진행로그)는 Obsidian 볼트에서 관리한다:
- 로드맵: `/Users/a05034/Documents/Obsidian Vault/21_VibeCoding/프로젝트/리서치MCP서버/00_로드맵.md`
- 진행로그: `/Users/a05034/Documents/Obsidian Vault/21_VibeCoding/프로젝트/리서치MCP서버/01_진행로그.md`

## 아키텍처 규칙
- 네트워크 호출(fetch_*)과 포맷팅(format_*, extract_*)을 반드시 분리한다. 포맷터는 순수 함수 — 단위 테스트 대상.
- 도구는 시장 중립 인터페이스: `market: str = "US"` 파라미터로 US/KR 분기. KR 미구현 시 명확한 안내 문자열 반환 (에러 X).
- 도구 출력은 에이전트가 파싱하기 좋은 `key: value` 라인 형식. JSON 덤프 금지.
- 도구 docstring은 한국어로, Args 설명 포함 — 이것이 MCP 스키마가 되어 에이전트 성능을 좌우한다.
- SEC 요청에는 반드시 식별 가능한 User-Agent 사용 (edgar.py의 USER_AGENT).

## 환경 변수
- `FINANCE_MCP_NO_VERIFY=1` — SSL 검증 비활성화 (회사 프록시/자체 서명 인증서 환경). 플래그 파싱은 `_http.py` 한 곳에서 관리하며 yfinance(curl_cffi)·SEC EDGAR·DART(httpx) 전 경로에 적용된다.
- `FINANCE_MCP_USER_AGENT` — SEC EDGAR User-Agent (이메일 포함 필수).
- `.env` 파일에 설정해두면 편리. (`.gitignore`에 포함)

## 개발 명령어
```bash
uv sync                            # 의존성 설치
uv run pytest                      # 테스트 (네트워크 불필요)
uv run finance-mcp                 # 서버 실행 (stdio)
uv run fastmcp dev inspector src/finance_mcp/server.py   # MCP Inspector로 디버깅
```

## 하지 말 것
- 자동 매매·투자 조언 기능 추가 금지 (분석·사실 수집까지만)
- 테스트에 실제 네트워크 호출 넣지 않기
- 웹 UI 만들지 않기 (범위 밖)

## 진행 로그 규칙
작업 세션이 끝나면 위 진행로그 파일에 날짜·작업 내용·배운 점·다음 할 일을 한 줄씩 추가한다.
