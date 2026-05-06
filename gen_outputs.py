"""Generate agent outputs for the 30 calibration cases.

Reads eval_cases/calibration_set.yaml, runs each question through the agent,
saves the (question, criterion, answer) tuples to calibration_outputs.json.
"""

import json
import yaml
from pathlib import Path
from agent import run_agent


CALIBRATION_SET = Path("eval_cases/calibration_set.yaml")
OUTPUTS_FILE = Path("eval_cases/calibration_outputs.json")


def main():
    with open(CALIBRATION_SET) as f:
        cases = yaml.safe_load(f)

    outputs = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['id']}...", end=" ", flush=True)
        try:
            answer = run_agent(case["question"], chat_history=[])
            outputs.append({
                "id": case["id"],
                "question": case["question"],
                "criterion": case["criterion"],
                "answer": answer,
            })
            print("OK")
        except Exception as e:
            print(f"ERROR: {e}")
            outputs.append({
                "id": case["id"],
                "question": case["question"],
                "criterion": case["criterion"],
                "answer": f"<exception: {e}>",
            })

    OUTPUTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUTS_FILE, "w") as f:
        json.dump(outputs, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(outputs)} outputs to {OUTPUTS_FILE}")


if __name__ == "__main__":
    main()
