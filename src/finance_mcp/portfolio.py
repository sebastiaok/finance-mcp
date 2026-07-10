"""포트폴리오 리소스: portfolio.json 로드.

경로 우선순위: 환경변수 FINANCE_MCP_PORTFOLIO > 프로젝트 루트의 portfolio.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "portfolio.json"


def load_holdings(path: str | Path | None = None) -> list[dict]:
    p = Path(path or os.environ.get("FINANCE_MCP_PORTFOLIO") or DEFAULT_PATH)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def format_holdings(holdings: list[dict]) -> str:
    if not holdings:
        return "포트폴리오 비어 있음 (portfolio.json 없음)."
    lines = ["[보유 종목]"]
    for h in holdings:
        lines.append(
            f"- {h.get('ticker', '?')} ({h.get('market', 'US')}) | "
            f"수량 {h.get('shares', 0)} | 평단 {h.get('avg_cost', '?')} | "
            f"메모: {h.get('note', '')}"
        )
    return "\n".join(lines)
