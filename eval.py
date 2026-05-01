"""Evaluation runner for sql-agent.

Reads test cases from eval_cases/cases.yaml, runs each question through
the agent, applies the appropriate check, and prints a report.
"""

import re
import yaml
from pathlib import Path
from agent import run_agent


CASES_PATH = Path("eval_cases/cases.yaml")


def check_regex(answer: str, pattern: str) -> bool:
    """Pass if the answer matches the pattern."""
    return bool(re.search(pattern, answer))


def check_regex_all(answer: str, patterns: list[str]) -> bool:
    """Pass if the answer matches all patterns."""
    return all(re.search(p, answer) for p in patterns)


def check_regex_any(answer: str, patterns: list[str]) -> bool:
    """Pass if the answer matches at least one pattern."""
    return any(re.search(p, answer) for p in patterns)


def check_regex_none(answer: str, patterns: list[str]) -> bool:
    """Pass if the answer matches none of the patterns."""
    return not any(re.search(p, answer) for p in patterns)


def evaluate_case(case: dict, answer: str) -> bool:
    """Apply the right check for the case's method."""
    method = case["method"]
    if method == "regex":
        return check_regex(answer, case["pattern"])
    elif method == "regex_all":
        return check_regex_all(answer, case["patterns"])
    elif method == "regex_any":
        return check_regex_any(answer, case["patterns"])
    elif method == "regex_none":
        return check_regex_none(answer, case["patterns"])
    else:
        raise ValueError(f"Unknown method: {method}")


def main():
    with open(CASES_PATH) as f:
        cases = yaml.safe_load(f)

    results = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['id']}... ", end="", flush=True)
        try:
            answer = run_agent(case["question"], chat_history=[])
            passed = evaluate_case(case, answer)
            status = "PASS" if passed else "FAIL"
            print(status)
            results.append({
                "id": case["id"],
                "category": case["category"],
                "passed": passed,
                "answer": answer,
            })
            print(f"  → {answer[:200]}")
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "id": case["id"],
                "category": case["category"],
                "passed": False,
                "answer": f"<exception: {e}>",
            })
            print(f"  → {answer[:200]}")

    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    print(f"Overall: {passed}/{total} ({passed/total*100:.0f}%)")

    by_cat = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r["passed"])
    print("\nBy category:")
    for cat, vals in sorted(by_cat.items()):
        p = sum(vals)
        t = len(vals)
        print(f"  {cat}: {p}/{t}")

    fails = [r for r in results if not r["passed"]]
    if fails:
        print("\nFailures:")
        for r in fails:
            print(f"  - {r['id']} ({r['category']})")
            print(f"    answer: {r['answer'][:200]}")


if __name__ == "__main__":
    main()
