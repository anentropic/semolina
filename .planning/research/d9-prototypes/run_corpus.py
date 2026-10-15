"""
Run the D9 corpus once per alternative and print a case x alternative table. Throwaway.

Run from the repository root:

    uv run --with griffe --with astroid python .planning/research/d9-prototypes/run_corpus.py

Each alternative runs ``tests/unit/codegen/test_check_accuracy_corpus.py`` with
``--runxfail`` (so a strict xfail reports its real outcome) and the ``d9plugin`` patches
selected by ``D9_ALT``. Results land in ``results.json`` and ``results.md`` next to this file.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = "tests/unit/codegen/test_check_accuracy_corpus.py"

ALTERNATIVES = {
    "today": "",
    "A": "A",
    "A+": "A+",
    "B": "B",
    "A+B": "A,B",
    "A++B": "A+,B",
    "G griffe": "G",
    "G astroid": "GA",
    "C": "C",
    "R": "R",
    "E": "E",
    "G+R+E": "G,R,E",
    "A++B+R+E": "A+,B,R,E",
}


def run(alt: str) -> dict[str, str]:
    env = {**os.environ, "D9_ALT": alt, "PYTHONPATH": str(HERE)}
    cmd = [sys.executable, "-m", "pytest", CORPUS, "--runxfail", "-p", "d9plugin", "-p", "no:randomly",
           "-p", "no:cacheprovider", "-q", "-rA", "-o", "addopts="]
    out = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False).stdout
    results: dict[str, str] = {}
    for line in out.splitlines():
        m = re.match(r"^(PASSED|FAILED|ERROR) \S+::(\w+)::(\w+)", line)
        if m:
            results[f"{m.group(2)}::{m.group(3)}"] = m.group(1)
    if not results:
        print(out[-3000:])
    return results


def main() -> None:
    wanted = sys.argv[1:] or list(ALTERNATIVES)
    table = {name: run(ALTERNATIVES[name]) for name in wanted}
    (HERE / "results.json").write_text(json.dumps(table, indent=2), encoding="utf-8")
    tests = list(next(iter(table.values())))
    names = list(table)
    lines = ["| test | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for test in tests:
        cells = ["ok" if table[n].get(test) == "PASSED" else "-" for n in names]
        lines.append(f"| {test} | " + " | ".join(cells) + " |")
    (HERE / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
