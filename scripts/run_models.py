"""Run the model phases through the claude CLI, caching every raw response.

Each call is `claude -p --model <m> --output-format json --system-prompt <s> --tools ""`
with the user prompt on stdin. The raw CLI output is written to raw/<model>/<kind>-<row>.json
before anything parses it, and a cached file is never re-requested. Every attempt, cached or
not, is logged in results/call_log.csv. The runner stops at 390 attempted calls and stops at
once if the CLI reports an authentication failure.

usage: python scripts/run_models.py [phase1|defects|control|all]
"""
import csv
import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from labelgate import prompts
from labelgate.adapters import medcalc
from labelgate.checks import grounding

CALL_CAP = 390
LOG = ROOT / "results/call_log.csv"
LOG_FIELDS = ["time", "model", "kind", "row", "status", "seconds", "path"]


class AuthError(RuntimeError):
    pass


def attempts_so_far():
    if not LOG.exists():
        return 0
    with open(LOG, newline="") as f:
        return sum(1 for r in csv.DictReader(f) if r["status"] != "cached")


def log(model, kind, row, status, seconds, path):
    new = not LOG.exists()
    with open(LOG, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new:
            writer.writeheader()
        writer.writerow({"time": datetime.datetime.now().isoformat(timespec="seconds"), "model": model,
                         "kind": kind, "row": row, "status": status, "seconds": seconds, "path": path})


def call(model, system, user, path, kind, row):
    if path.exists():
        log(model, kind, row, "cached", 0, path.relative_to(ROOT))
        return json.loads(path.read_text())
    if attempts_so_far() >= CALL_CAP:
        raise SystemExit(f"call cap of {CALL_CAP} reached")
    cmd = ["claude", "-p", "--model", model, "--output-format", "json", "--system-prompt", system,
           "--tools", "", "--no-session-persistence", "--strict-mcp-config"]
    start = datetime.datetime.now()
    proc = subprocess.run(cmd, input=user, capture_output=True, text=True, timeout=600, cwd=ROOT / "raw")
    seconds = round((datetime.datetime.now() - start).total_seconds(), 1)
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        log(model, kind, row, "bad_output", seconds, "")
        print(f"{model} {kind} {row}: unreadable CLI output: {proc.stdout[:200]} {proc.stderr[:200]}")
        return None
    if out.get("is_error"):
        message = str(out.get("result", ""))
        log(model, kind, row, "error", seconds, "")
        if "authenticate" in message.lower() or "oauth" in message.lower():
            raise AuthError(message)
        print(f"{model} {kind} {row}: {message[:200]}")
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"model": model, "kind": kind, "row": row, "system": system, "user": user, "cli": out}
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1))
    log(model, kind, row, "ok", seconds, path.relative_to(ROOT))
    return record


def run(phase, samples, tasks):
    jobs = []
    if phase in ("phase1", "all"):
        for row in samples["phase1"]:
            names = sorted({name for name, _ in grounding.numeric_inputs(tasks[("ver_train", row)])})
            user = prompts.extract_user(tasks[("ver_train", row)].source_text, names)
            jobs.append(("sonnet", prompts.EXTRACT_SYSTEM, user, "extract", "ver_train", row))
    if phase in ("defects", "all"):
        for model in ("haiku", "sonnet", "opus"):
            for d in samples["defects"]:
                jobs.append((model, None, None, "calc", d["dataset"], d["row"]))
    if phase in ("control", "all"):
        for model in ("haiku", "sonnet"):
            for row in samples["control"]:
                jobs.append((model, None, None, "calc", "ver_train", row))
    for model, system, user, kind, dataset, row in jobs:
        task = tasks[(dataset, row)]
        if kind == "calc":
            system = prompts.ZERO_SHOT_SYSTEM
            user = prompts.zero_shot_user(task.source_text, task.meta["question"])
        path = medcalc.raw_path(ROOT, model, kind, dataset, row)
        call(model, system, user, path, kind, path.stem.split("-", 1)[1])


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"
    samples = json.loads((ROOT / "results/samples.json").read_text())
    tasks = medcalc.load_splits(ROOT / "data")
    (ROOT / "raw").mkdir(exist_ok=True)
    try:
        run(phase, samples, tasks)
    except AuthError as err:
        raise SystemExit(f"stopped: the claude CLI could not authenticate ({err}). Run `claude` once in a terminal, log in, then rerun.")


if __name__ == "__main__":
    main()
