"""Evaluation runner for sql-agent.

Reads test cases from eval_cases/cases.yaml, runs each question through
the agent, applies the appropriate check, and prints a report.
"""

import re
import yaml
from pathlib import Path
from agent import run_agent
import json
from anthropic import Anthropic

client = Anthropic()
JUDGE_MODEL = "claude-sonnet-4-5"  # juiz forte (mais caro), agente é haiku

JUDGE_PROMPT = """
    You are an impartial evaluator. Your job is to decide whether an
    answer fulfills a given criterion.

    You will receive:
    - QUESTION: the original question that was asked
    - ANSWER: the response that needs to be evaluated
    - CRITERION: the rule that determines whether the answer is acceptable

    Your task: judge whether the ANSWER fulfills the CRITERION, given the
    QUESTION as context. Be strict — if the criterion is partially met or
    ambiguously met, the answer fails.

    Respond ONLY with a JSON object in this exact format, no other text:

    {
    "reasoning": "<one or two sentences explaining your decision>",
    "passed": <true or false>
    }
"""


def _extract_json(raw: str) -> str:
    """Strip markdown code fences if present."""
    raw = raw.strip()
    if raw.startswith("```"):
        # Remove first line (```json or ```) and last line (```)
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])
    return raw


def check_llm_judge(question: str, answer: str, criterion: str) -> tuple[bool, str]:
    """Pass if the LLM judge decides the answer fulfills the criterion.

    Returns (passed, reasoning) so the caller can log the judge's rationale.
    """
    user_message = f"QUESTION: {question}\n\nANSWER: {answer}\n\nCRITERION: {criterion}"

    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=500,
        system=JUDGE_PROMPT,
        messages=[
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": "{"},   # ← prefill
        ],
    )
    raw = "{" + response.content[0].text  # prepend o prefill
    verdict = json.loads(_extract_json(raw))
    return verdict["passed"], verdict["reasoning"]

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


def evaluate_case(case: dict, answer: str) -> tuple[bool, str]:
    """Apply the right check for the case's method.
    Returns (passed, reasoning). Reasoning is empty for regex methods."""
    method = case["method"]
    if method == "regex":
        return check_regex(answer, case["pattern"]), ""
    elif method == "regex_all":
        return check_regex_all(answer, case["patterns"]), ""
    elif method == "regex_any":
        return check_regex_any(answer, case["patterns"]), ""
    elif method == "regex_none":
        return check_regex_none(answer, case["patterns"]), ""
    elif method == "llm_judge":
        return check_llm_judge(case["question"], answer, case["criteria"])
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
            passed, reasoning = evaluate_case(case, answer)
            status = "PASS" if passed else "FAIL"
            print(status)
            results.append({
                "id": case["id"],
                "category": case["category"],
                "passed": passed,
                "answer": answer,
                "reasoning": reasoning
            })
            print(f"  → {answer[:200]}")
            if reasoning:
                print(f"  judge: {reasoning}")
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "id": case["id"],
                "category": case["category"],
                "passed": False,
                "answer": f"<exception: {e}>",
                "reasoning": ""
            })
            print(f"  → {answer[:200] if 'answer' in locals() else '(no answer)'}")

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
