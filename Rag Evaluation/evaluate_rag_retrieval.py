from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rag.service import retrieve_knowledge


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_GOLDEN = SCRIPT_DIR / "golden_cases.json"
DEFAULT_REPORT = SCRIPT_DIR / "last_retrieval_report.txt"

ALLOWED_STATUSES = frozenset({"ok", "empty", "empty_query", "out_of_scope"})


def is_emergency_keyword_query(query: str) -> bool:
    q = query.lower()
    patterns = (
        r"\bchest\s+pain\b",
        r"\btrouble\s+breathing\b",
        r"\bdifficulty\s+breathing\b",
        r"\bshort(ness)?\s+of\s+breath\b",
        r"\bcan'?t\s+breathe\b",
        r"\bcannot\s+breathe\b",
        r"\bsudden\s+weakness\b",
        r"\bface\s+drooping\b",
        r"\bfacial\s+drooping\b",
        r"\bsevere\s+bleeding\b",
        r"\bsuicidal\b",
        r"\bhurt\s+myself\b",
        r"\bstroke\b",
        r"\b911\b",
    )
    return any(re.search(p, q) for p in patterns)


def _match_one(
    m: dict[str, Any],
    source_file: str | None,
    section: str | None,
    section_contains: str | None,
) -> bool:
    if source_file and m.get("source_file") != source_file:
        return False
    sec = (m.get("section") or "").strip()
    if section is not None and sec != section:
        return False
    if section_contains is not None and section_contains.lower() not in sec.lower():
        return False
    return True


def _find_best_rank(
    matches: list[dict[str, Any]],
    rule: dict[str, Any],
    max_rank: int,
) -> int | None:
    cap = min(max_rank, len(matches))
    for i in range(cap):
        m = matches[i]
        if _match_one(
            m,
            rule.get("source_file"),
            rule.get("section"),
            rule.get("section_contains"),
        ):
            return i + 1
    return None


def _passes_retrieval_expectation(
    result: dict[str, Any],
    expect: dict[str, Any],
) -> tuple[bool, str]:
    status = result.get("status")
    if status != expect.get("status"):
        return False, f"status: got {status!r}, want {expect.get('status')!r}"

    max_rank = int(expect.get("max_rank", 3))
    matches: list[dict[str, Any]] = list(result.get("matches") or [])

    if expect.get("status") != "ok":
        if matches:
            return False, f"expected no matches for status {status!r}, got {len(matches)}"
        return True, "ok"

    any_of = expect.get("any_of")
    if any_of:
        best: int | None = None
        for rule in any_of:
            r = _find_best_rank(matches, rule, max_rank)
            if r is not None and (best is None or r < best):
                best = r
        if best is None:
            return False, f"no any_of rule matched within top {max_rank}"
        return True, f"matched any_of at rank {best}"

    rule = {
        "source_file": expect.get("source_file"),
        "section": expect.get("section"),
        "section_contains": expect.get("section_contains"),
    }
    rank = _find_best_rank(matches, rule, max_rank)
    if rank is None:
        return False, (
            f"expected chunk not in top {max_rank}: "
            f"file={expect.get('source_file')!r} section={expect.get('section')!r} "
            f"section_contains={expect.get('section_contains')!r}"
        )
    return True, f"matched at rank {rank}"


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    detail: str


def _expectation_summary(expect: dict[str, Any]) -> str:
    if expect.get("emergency_keyword_detected"):
        return "expect: emergency keywords in query (no RAG retrieval for this case)"
    parts: list[str] = []
    st = expect.get("status")
    if st is not None:
        parts.append(f"status={st!r}")
    if expect.get("any_of"):
        rules = []
        for r in expect["any_of"]:
            sf = r.get("source_file")
            sec = r.get("section")
            sc = r.get("section_contains")
            if sec is not None:
                rules.append(f"{sf} — section {sec!r}")
            elif sc is not None:
                rules.append(f"{sf} — section contains {sc!r}")
            else:
                rules.append(str(r))
        parts.append("any_of:\n    " + "\n    ".join(rules))
    else:
        if expect.get("source_file"):
            parts.append(f"file={expect['source_file']!r}")
        if expect.get("section") is not None:
            parts.append(f"section={expect['section']!r}")
        if expect.get("section_contains") is not None:
            parts.append(f"section_contains={expect['section_contains']!r}")
        mr = expect.get("max_rank")
        if mr is not None:
            parts.append(f"max_rank={mr}")
    return "expect:\n  " + ("\n  ".join(parts) if parts else "  (no expect fields)")


def _truncate(text: str, max_chars: int) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1].rstrip() + "…"


def format_case_report(
    case: dict[str, Any],
    cr: CaseResult,
    result: dict[str, Any] | None,
    *,
    verbose: bool,
    snippet_chars: int = 800,
) -> str:
    case_id = cr.case_id
    query = str(case.get("query", ""))
    expect = case.get("expect") or {}
    lines = [
        "=" * 72,
        f"case: {case_id}",
        f"result: {'PASS' if cr.passed else 'FAIL'} — {cr.detail}",
        "",
        f"query:\n  {query}",
        "",
        _expectation_summary(expect),
        "",
    ]
    if result is None:
        lines.append("(no retrieval payload for this case type)")
    else:
        matches: list[dict[str, Any]] = list(result.get("matches") or [])
        if not matches:
            lines.append("retrieved chunks: (none)")
        else:
            lines.append("retrieved chunks (vector index):")
            for i, m in enumerate(matches, start=1):
                src = m.get("source_file", "")
                sec = (m.get("section") or "").strip()
                score = m.get("score")
                body = m.get("snippet") or m.get("content") or ""
                lines.append(f"  [{i}] {src} — {sec!r}  score={score}")
                lines.append(f"      {_truncate(str(body), snippet_chars)}")
        if verbose:
            lines.append("")
            lines.append("raw retrieval (truncated JSON):")
            lines.append(json.dumps(result, indent=2)[:12000])
    return "\n".join(lines)


def load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("golden_cases.json must be a JSON array")
    return data


def run_case(case: dict[str, Any]) -> tuple[CaseResult, dict[str, Any] | None]:
    case_id = str(case.get("id", "<missing id>"))
    query = case.get("query", "")
    expect = case.get("expect") or {}
    top_k = int(case.get("top_k", 4))

    if expect.get("emergency_keyword_detected"):
        ok = is_emergency_keyword_query(str(query))
        detail = "emergency keywords detected" if ok else "emergency keywords not detected"
        return CaseResult(case_id, ok, detail), None

    result = retrieve_knowledge(query=str(query), top_k=top_k)
    ok, detail = _passes_retrieval_expectation(result, expect)
    return CaseResult(case_id, ok, detail), result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Human-readable report path")
    parser.add_argument("--no-report", action="store_true", dest="no_report")
    parser.add_argument("--verbose", action="store_true", help="Include truncated JSON in the report file")
    parser.add_argument("--fail-fast", action="store_true", dest="fail_fast")
    args = parser.parse_args()

    cases = load_cases(args.golden)
    results: list[CaseResult] = []
    report_sections: list[str] = []

    header = (
        f"RAG retrieval evaluation\n"
        f"golden: {args.golden.resolve()}\n"
        f"generated: {datetime.now(timezone.utc).isoformat()}\n"
    )
    report_sections.append(header)

    for case in cases:
        expect = case.get("expect") or {}
        status_expect = expect.get("status")
        if status_expect is not None and status_expect not in ALLOWED_STATUSES:
            print(f"Invalid status in case {case.get('id')!r}: {status_expect!r}", file=sys.stderr)
            return 2
        if expect.get("emergency_keyword_detected") and status_expect is not None:
            print(
                f"Case {case.get('id')!r}: do not combine emergency_keyword_detected with status",
                file=sys.stderr,
            )
            return 2

        cr, retrieval = run_case(case)
        results.append(cr)
        flag = "PASS" if cr.passed else "FAIL"
        print(f"[{flag}] {cr.case_id}: {cr.detail}")

        if not args.no_report:
            report_sections.append(format_case_report(case, cr, retrieval, verbose=args.verbose))

        if args.fail_fast and not cr.passed:
            break

    failed = [r for r in results if not r.passed]
    print(f"\nSummary: {len(results) - len(failed)}/{len(results)} passed")

    if not args.no_report:
        try:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text("\n\n".join(report_sections) + "\n", encoding="utf-8")
        except OSError as e:
            print(f"Could not write report file {args.report}: {e}", file=sys.stderr)
            return 2

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
