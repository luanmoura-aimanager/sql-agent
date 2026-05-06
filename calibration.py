"""Compute Cohen's kappa between human and LLM judge, list disagreements.

Criteria are read from calibration_set.yaml (single source of truth) so they
stay in sync when the YAML is updated, without needing to regenerate
calibration_outputs.json.
"""

import json
import yaml
from pathlib import Path


HUMAN_FILE = Path("eval_cases/human_judgments.json")
JUDGE_FILE = Path("eval_cases/judge_judgments.json")
OUTPUTS_FILE = Path("eval_cases/calibration_outputs.json")
CALIBRATION_SET = Path("eval_cases/calibration_set.yaml")


def cohens_kappa(human, judge):
    """Cohen's kappa for binary pass/fail ratings."""
    n = len(human)
    a = sum(1 for k in human if human[k] and judge[k])             # both pass
    b = sum(1 for k in human if not human[k] and not judge[k])     # both fail
    c = sum(1 for k in human if human[k] and not judge[k])         # judge stricter
    d = sum(1 for k in human if not human[k] and judge[k])         # judge more lenient

    po = (a + b) / n
    p_h_pass = (a + c) / n
    p_h_fail = (b + d) / n
    p_j_pass = (a + d) / n
    p_j_fail = (b + c) / n
    pe = p_h_pass * p_j_pass + p_h_fail * p_j_fail

    if pe == 1:
        kappa = 1.0 if po == 1 else 0.0
    else:
        kappa = (po - pe) / (1 - pe)

    return {
        "n": n,
        "matrix": {"both_pass": a, "both_fail": b,
                   "human_pass_judge_fail": c, "human_fail_judge_pass": d},
        "po": po, "pe": pe, "kappa": kappa,
    }


def interpret(k):
    if k < 0:    return "abaixo do acaso (pior que aleatório)"
    if k < 0.2:  return "ligeira"
    if k < 0.4:  return "razoável"
    if k < 0.6:  return "moderada"
    if k < 0.8:  return "substancial"
    return "quase perfeita"


def main():
    with open(HUMAN_FILE) as f:
        human_raw = json.load(f)
    with open(JUDGE_FILE) as f:
        judge_raw = json.load(f)
    with open(OUTPUTS_FILE) as f:
        outputs = json.load(f)
    with open(CALIBRATION_SET) as f:
        cases_yaml = {c["id"]: c for c in yaml.safe_load(f)}

    common = sorted(set(human_raw) & set(judge_raw))
    human = {k: human_raw[k]["passed"] for k in common}
    judge = {k: judge_raw[k]["passed"] for k in common}

    r = cohens_kappa(human, judge)
    m = r["matrix"]

    print(f"=== CALIBRATION REPORT ===\n")
    print(f"N: {r['n']} cases\n")
    print("Agreement matrix:")
    print(f"  both pass:               {m['both_pass']}")
    print(f"  both fail:               {m['both_fail']}")
    print(f"  human pass + judge fail: {m['human_pass_judge_fail']}  (juiz mais severo)")
    print(f"  human fail + judge pass: {m['human_fail_judge_pass']}  (juiz mais generoso)")
    print()
    print(f"Observed agreement (po): {r['po']:.3f}  ({m['both_pass']+m['both_fail']}/{r['n']})")
    print(f"Expected by chance (pe): {r['pe']:.3f}")
    print(f"Cohen's kappa (κ):       {r['kappa']:.3f}  ({interpret(r['kappa'])})")
    print()

    disagreements = [k for k in common if human[k] != judge[k]]
    if not disagreements:
        print("No disagreements.")
        return

    outputs_by_id = {o["id"]: o for o in outputs}
    print(f"=== DISAGREEMENTS ({len(disagreements)}) ===\n")

    for case_id in disagreements:
        case = outputs_by_id[case_id]
        criterion = cases_yaml[case_id]["criterion"]
        h, j = human_raw[case_id], judge_raw[case_id]
        h_v = "PASS" if h["passed"] else "FAIL"
        j_v = "PASS" if j["passed"] else "FAIL"

        print(f"--- {case_id} ---")
        print(f"  question:  {case['question']}")
        print(f"  criterion: {criterion[:140]}")
        print(f"  answer:    {case['answer'][:200]}")
        print(f"  HUMAN {h_v}: {h.get('reason', '(no reason)')}")
        print(f"  JUDGE {j_v}: {j.get('reason', '(no reason)')}")
        print()


if __name__ == "__main__":
    main()
