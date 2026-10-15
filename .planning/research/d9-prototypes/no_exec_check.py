"""
Does each reader run the user's code? And how long does it take? Throwaway measurement.

Run from the repository root:

    uv run --with griffe --with astroid python .planning/research/d9-prototypes/no_exec_check.py

Builds a three-module package in a temporary directory: ``app/models.py`` declares a model
whose base is in ``app/base.py`` and whose ``view=`` constant is in ``app/names.py``, with
fields spelled ``M[Optional[Decimal]]()``, ``semolina.Metric[None | int]()`` and
``region: Dimension[str] = Dimension[str]()``. Every module writes a marker file when it is
executed. Each reader then reads ``app/models.py`` and the markers are counted.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

MARK = "import pathlib; pathlib.Path(__file__).with_suffix('.ran').write_text('x')\n"

FILES = {
    "app/__init__.py": "",
    "app/names.py": MARK + 'SALES_VIEW = "type_fidelity_view"\n',
    "app/base.py": MARK
    + "from semolina import Dimension, SemanticView\n\n\n"
    + "class Commerce(SemanticView, abstract=True):\n"
    + "    region: Dimension[str] = Dimension[str]()\n",
    "app/models.py": MARK
    + "from decimal import Decimal\nfrom typing import Optional\n\nimport semolina\n"
    + "from semolina import Metric as M\n\nfrom app.base import Commerce\n"
    + "from app.names import SALES_VIEW\n\n\n"
    + "class Sales(Commerce, view=SALES_VIEW):\n"
    + "    total_order_value = M[Optional[Decimal]]()\n"
    + "    n_order_totals = semolina.Metric[None | int]()\n",
}


def main() -> None:
    import reader_a
    import reader_astroid
    import reader_c
    import reader_griffe

    readers = {
        "A+ (text, follows imports)": reader_a.make_reader(follow_imports=True, normalise=True),
        "G griffe": reader_griffe.read_committed_model,
        "G astroid": reader_astroid.read_committed_model,
        "C subprocess import": reader_c.read_committed_model,
    }
    for label, read in readers.items():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in FILES.items():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(text, encoding="utf-8")
            old = Path.cwd()
            os.chdir(root)
            try:
                start = time.perf_counter()
                models = read(root / "app/models.py")
                elapsed = time.perf_counter() - start
            finally:
                os.chdir(old)
            ran = sorted(p.stem for p in root.rglob("*.ran"))
            m = models[0]
            fields = {n: f.annotation for n, f in m.fields.items()}
            print(f"{label}: view={m.view_name!r} fields={fields} ran={ran} time={elapsed:.2f}s")


if __name__ == "__main__":
    main()
