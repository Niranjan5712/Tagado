#!/usr/bin/env python3
"""Fail if AI SDKs or AI API key names appear in dependency/example env files."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PACKAGE_PATTERNS = [
    re.compile(r"\bopenai\b", re.I),
    re.compile(r"\banthropic\b", re.I),
    re.compile(r"\blangchain\b", re.I),
    re.compile(r"\bllamaindex\b", re.I),
    re.compile(r"@ai-sdk/", re.I),
    re.compile(r"\bai\s*==", re.I),
]

FORBIDDEN_ENV_PATTERNS = [
    re.compile(r"OPENAI_API_KEY", re.I),
    re.compile(r"ANTHROPIC_API_KEY", re.I),
    re.compile(r"GOOGLE_API_KEY", re.I),
    re.compile(r"AZURE_OPENAI", re.I),
]

SCAN_FILES = [
    ROOT / "backend" / "requirements.txt",
    ROOT / "frontend" / "package.json",
    ROOT / ".env.example",
]


def main() -> int:
    failures: list[str] = []
    for path in SCAN_FILES:
        if not path.exists():
            failures.append(f"missing file: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        patterns = FORBIDDEN_ENV_PATTERNS if path.name.startswith(".env") else FORBIDDEN_PACKAGE_PATTERNS
        # package.json: also block common AI SDK names
        if path.name == "package.json":
            patterns = FORBIDDEN_PACKAGE_PATTERNS
        for pattern in patterns:
            if pattern.search(text):
                failures.append(f"{path.relative_to(ROOT)} matches {pattern.pattern}")

    if failures:
        print("check_no_ai FAILED:")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("check_no_ai OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
