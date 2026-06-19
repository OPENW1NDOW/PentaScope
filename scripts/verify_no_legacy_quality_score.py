"""spec v4 验收 8 — 影响面回归检查（cycle3/M8）。

旧三项 + cap 机制的 6 个符号必须在 src/ 下无遗留引用：
- calc_source_coverage
- calc_confidence_avg
- calc_inspector_pass_rate
- _QUALITY_SCORE_CAP_ON_PLACEHOLDER
- _detect_placeholder_warnings
- _check_warnings_prefix

CI 跑：python scripts/verify_no_legacy_quality_score.py
退出码 0 = 全清；非 0 = 有遗留引用，CI fail。
"""
import sys
from pathlib import Path

LEGACY_SYMBOLS = [
    "calc_source_coverage",
    "calc_confidence_avg",
    "calc_inspector_pass_rate",
    "_QUALITY_SCORE_CAP_ON_PLACEHOLDER",
    "_detect_placeholder_warnings",
    "_check_warnings_prefix",
]

SEARCH_DIRS = ["src", "tests"]


def main():
    repo_root = Path(__file__).parent.parent
    found_issues = []

    for search_dir in SEARCH_DIRS:
        target = repo_root / search_dir
        if not target.exists():
            continue
        for py_file in target.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue
            for symbol in LEGACY_SYMBOLS:
                if symbol in content:
                    for lineno, line in enumerate(content.splitlines(), 1):
                        if symbol in line:
                            found_issues.append((py_file, lineno, symbol, line.strip()))

    if found_issues:
        print("[FAIL] legacy quality_score symbols still referenced:")
        for path, lineno, symbol, line in found_issues:
            print(f"  {path}:{lineno}  [{symbol}]  {line}")
        sys.exit(1)
    else:
        print("[PASS] no legacy quality_score symbols found (spec v4 verification 8)")
        sys.exit(0)


if __name__ == "__main__":
    main()
