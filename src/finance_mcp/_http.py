"""공통 HTTP 설정 — SSL 검증 토글(FINANCE_MCP_NO_VERIFY)을 한 곳에서 관리.

회사 프록시(SKCC root CA 등)·자체 서명 인증서 환경에서는 Python이 SSL 검증에 실패한다.
FINANCE_MCP_NO_VERIFY=1 이면 검증을 끈다. 이 플래그의 파싱을 여기 한 곳으로 모아
edgar.py·dart.py·market_data.py가 제각각 파싱하던 중복(과 DART 누락 버그)을 없앤다.
"""

from __future__ import annotations

import os

import httpx

# 참(1/true/yes)이면 SSL 검증을 건너뛴다.
NO_VERIFY = os.environ.get("FINANCE_MCP_NO_VERIFY", "").lower() in ("1", "true", "yes")


def get(
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    timeout: int = 30,
) -> httpx.Response:
    """httpx GET 래퍼. NO_VERIFY면 SSL 검증을 끈다. raise_for_status는 호출부에서."""
    return httpx.get(url, headers=headers, params=params, timeout=timeout, verify=not NO_VERIFY)
