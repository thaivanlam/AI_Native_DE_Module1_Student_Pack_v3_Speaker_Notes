"""Exercise B8 checkpoint recovery against the configured PostgreSQL and API.

Run from the project root: python scripts/demo_checkpoint.py
Requires the Mock API and PostgreSQL to be running. Successful runs perform
normal upserts, refresh the mart, and update the real pipeline checkpoint.
"""
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "metadata" / "pipeline_state.json"
EVIDENCE = ROOT / "docs" / "evidence" / "08-checkpoint.txt"


def main():
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE.open("w", encoding="utf-8") as evidence:
        def record(message):
            print(message, file=evidence, flush=True)

        def snapshot(label):
            content = STATE.read_bytes()
            record(f"\n{label}\n{content.decode('utf-8')}")
            return content

        def run(*args, expected=0):
            record("\n$ python -m src.pipeline " + " ".join(args))
            result = subprocess.run(
                [sys.executable, "-m", "src.pipeline", *args], cwd=ROOT,
                capture_output=True, encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            record(result.stdout + result.stderr)
            record(f"Exit code: {result.returncode}")
            assert result.returncode == expected, f"Unexpected exit code; see {EVIDENCE}"

        record("B8 / Bai 3: real PostgreSQL + Mock API, no mocked pipeline stages.")
        before = snapshot("STATE BEFORE FAILURE")
        missing = ROOT / "data" / "__checkpoint_missing_batch__"
        assert not missing.exists()
        run("--source", "file", "--input-dir", str(missing), expected=1)
        assert snapshot("STATE AFTER FAILURE") == before
        record("PASS: failed run exits 1; checkpoint bytes are unchanged.")

        run("--source", "both", "--refresh-mart")
        after = json.loads(snapshot("STATE AFTER SUCCESS"))
        assert after["last_run_id"] != json.loads(before).get("last_run_id")
        assert after["status"] == "success" and after["last_source"] == "both"
        record("PASS: Core, reconciliation, report and mart complete before checkpoint changes.")

        run("--source", "api", "--refresh-mart")
        resumed = json.loads(snapshot("STATE AFTER API RESUME"))
        for name, watermark in after["api_watermarks"].items():
            raw = ROOT / "data" / "raw" / resumed["last_run_id"] / f"{name}.json"
            payload = json.loads(raw.read_text(encoding="utf-8"))
            assert payload["updated_after"] == watermark
            record(f"PASS: {name} resumed with updated_after={watermark}; fetched={payload['total']}")
        record("Empty increments retain their previous watermark; only loaded valid rows can advance it.")

        before_skip = STATE.read_bytes()
        run("--source", "file", "--skip-processed-file")
        assert snapshot("STATE AFTER FILE SKIP") == before_skip
        record("PASS: processed file batch skipped, exit 0, checkpoint unchanged.")
    print(f"Checkpoint evidence: {EVIDENCE}")


if __name__ == "__main__":
    main()
