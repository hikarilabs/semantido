"""Run the probe against every semantido release and tabulate the result.

Builds a git worktree per tag, installs each release in turn, runs probe.py
under it, and renders the comparison. Deterministic and offline — no LLM, no
API key, no database.

    python run_timeline.py                    # all tags
    python run_timeline.py --tags v0.5.0 v0.5.3
    python run_timeline.py --report-only      # re-render results.jsonl

Because it force-reinstalls semantido repeatedly, run it in a throwaway
virtualenv. It restores the newest tag at the end, but an editable install of
your working tree will need reinstating by hand.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WORKTREES = Path("/tmp/semantido-timeline-worktrees")
RESULTS = HERE / "results.jsonl"

DEFAULT_TAGS = ["v0.4.0", "v0.4.1", "v0.5.0", "v0.5.1", "v0.5.2", "v0.5.3"]

PROBE_JOINS = ["figi = ric", "isin = ric", "isin = isin"]


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def prepare_worktrees(tags: list[str]) -> None:
    WORKTREES.mkdir(parents=True, exist_ok=True)
    for tag in tags:
        target = WORKTREES / tag
        if not target.exists():
            sh(["git", "worktree", "add", "-q", "-f", str(target), tag], cwd=REPO)


def run_tag(tag: str) -> dict:
    sh(
        [
            sys.executable, "-m", "pip", "install", "-q",
            "--break-system-packages", "--no-deps", "--force-reinstall",
            str(WORKTREES / tag),
        ]
    )
    proc = sh([sys.executable, str(HERE / "probe.py")])
    line = (proc.stdout or "").strip().splitlines()
    if not line:
        return {"version": tag, "error": (proc.stderr or "no output")[:200]}
    return json.loads(line[-1])


def render(rows: list[dict]) -> None:
    def cell(joins: dict, key: str) -> str:
        v = joins.get(key)
        if v is None:
            return "n/a"
        return "+".join(v) if v else "silent"

    head = (
        f"{'release':<9}{'concepts':>9}{'grain':>7}{'md tok':>8}  "
        f"{'checks':<14}" + "".join(f"{j:<15}" for j in PROBE_JOINS)
    )
    print("\n" + head)
    print("-" * len(head))
    for r in rows:
        if "error" in r:
            print(f"{r['version']:<9}  ERROR: {r['error'][:60]}")
            continue
        checks = r.get("checks", [])
        rng = f"{checks[0]}-{checks[-1]}" if checks else "—"
        joins = r.get("joins", {})
        print(
            f"{r['version']:<9}{r['concepts']:>9}{r['grain_declared']:>7}"
            f"{r['markdown_tokens']:>8}  {rng:<14}"
            + "".join(f"{cell(joins, j):<15}" for j in PROBE_JOINS)
        )

    print(
        "\n  Read the last column. Across every release ever shipped, the "
        "join that\n  returns twelve wrong rows has never been caught. The "
        "one caught in 0.5.0\n  returns an empty set. That column is the "
        "roadmap."
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="*", default=DEFAULT_TAGS)
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    if args.report_only:
        render([json.loads(x) for x in RESULTS.read_text().splitlines() if x.strip()])
        return

    prepare_worktrees(args.tags)
    rows = []
    for tag in args.tags:
        print(f"  probing {tag} ...", flush=True)
        rows.append(run_tag(tag))
    RESULTS.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    render(rows)


if __name__ == "__main__":
    main()
