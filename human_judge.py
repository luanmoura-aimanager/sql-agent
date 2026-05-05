"""Human judgment CLI for calibration.

Walks through each calibration case, shows question + criterion + answer,
and asks for pass/fail verdict. Saves judgments incrementally so progress
isn't lost if interrupted.
"""

import json
from pathlib import Path


OUTPUTS_FILE = Path("eval_cases/calibration_outputs.json")
JUDGMENTS_FILE = Path("eval_cases/human_judgments.json")


def main():
    with open(OUTPUTS_FILE) as f:
        outputs = json.load(f)

    if JUDGMENTS_FILE.exists():
        with open(JUDGMENTS_FILE) as f:
            judgments = json.load(f)
    else:
        judgments = {}

    pending = [o for o in outputs if o["id"] not in judgments]

    print(f"Total: {len(outputs)} | Done: {len(judgments)} | Pending: {len(pending)}")
    print("Commands: p=pass, f=fail, s=skip, q=quit (saves and exits)\n")

    for i, case in enumerate(pending, 1):
        print("=" * 60)
        print(f"[{i}/{len(pending)}] {case['id']}")
        print("=" * 60)
        print(f"\nQUESTION:\n  {case['question']}")
        print(f"\nCRITERION:\n  {case['criterion']}")
        print(f"\nANSWER:\n  {case['answer']}\n")

        while True:
            verdict = input("Verdict [p/f/s/q]: ").strip().lower()
            if verdict in ("p", "f", "s", "q"):
                break
            print("Invalid. Use p/f/s/q.")

        if verdict == "q":
            print(f"\nExiting. {len(judgments)} judgments saved.")
            return

        if verdict == "s":
            print("  → skipped\n")
            continue

        reason = input("Reason (optional, enter to skip): ").strip()

        judgments[case["id"]] = {
            "passed": verdict == "p",
            "reason": reason,
        }

        with open(JUDGMENTS_FILE, "w") as f:
            json.dump(judgments, f, indent=2, ensure_ascii=False)

        print(f"  → saved ({len(judgments)} total)\n")

    print(f"\nDone. {len(judgments)}/{len(outputs)} cases judged.")


if __name__ == "__main__":
    main()
