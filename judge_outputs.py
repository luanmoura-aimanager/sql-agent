"""Run the LLM judge on the 30 calibration cases.

Reads agent outputs from calibration_outputs.json and the LATEST criteria
from calibration_set.yaml — keeping criteria as the single source of truth.
"""

import json
import yaml
from pathlib import Path
from eval import check_llm_judge


CALIBRATION_SET = Path("eval_cases/calibration_set.yaml")
OUTPUTS_FILE = Path("eval_cases/calibration_outputs.json")
JUDGMENTS_FILE = Path("eval_cases/judge_judgments.json")


def main():
    with open(OUTPUTS_FILE) as f:
        outputs = json.load(f)
    with open(CALIBRATION_SET) as f:
        cases_yaml = {c["id"]: c for c in yaml.safe_load(f)}

    judgments = {}
    for i, case in enumerate(outputs, 1):
        case_id = case["id"]
        criterion = cases_yaml[case_id]["criterion"]   # ← do YAML, fonte única

        print(f"[{i}/{len(outputs)}] {case_id}...", end=" ", flush=True)
        try:
            passed, reason = check_llm_judge(
                case["question"], case["answer"], criterion
            )
            judgments[case_id] = {"passed": passed, "reason": reason}
            print("PASS" if passed else "FAIL")
        except Exception as e:
            print(f"ERROR: {e}")
            judgments[case_id] = {
                "passed": False,
                "reason": f"<exception: {e}>",
            }

    with open(JUDGMENTS_FILE, "w") as f:
        json.dump(judgments, f, indent=2, ensure_ascii=False)

    total = len(judgments)
    passed = sum(1 for j in judgments.values() if j["passed"])
    print(f"\nSaved {total} judgments. Pass rate: {passed}/{total} ({passed/total*100:.0f}%)")


if __name__ == "__main__":
    main()
